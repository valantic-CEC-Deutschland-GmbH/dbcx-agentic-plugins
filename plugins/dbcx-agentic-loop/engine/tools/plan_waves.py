#!/usr/bin/env python3
"""Build the analysis waves from state/scopes.json (written by the method's discover tool) -> state/WAVES.json.
Usage: dbcx plan_waves [--max N] [--skip a,b] [--light a,b]
scopes.json contract: {"noun": "...", "scopes": {name: {"group": str, "depends_on": [names], "size": int, "light": bool|null, "light_reason": str, "skip": bool, "meta": {...}}}}
Wave rule (method.json scopes.wave_rule; a scopes.json `wave_rule` - written by the method's discover tool for this run - wins):
  dependency  a scope is scheduled only when every scope it depends on is in an earlier or the same wave; hubs (many transitive dependents) first
  after a scope's wave comes strictly AFTER the waves of every scope it depends on: level = max(the scope's optional `level`,
              1 + the level of each dependency); waves are filled per level up to max_agents_per_wave, largest first (tech-fit-estimation
              0.4.0: a dependent system's chunks after every chunk of its parent; follow-up chunks of a pickup carry a `level` after all others).
              Once state/STATUS.json registers scopes with a wave, those keep their wave (never renumbered); a new scope goes into the first
              wave that has not started (after its dependencies' waves), its overflow into a new wave after the last registered one
  group       scopes are ordered by group (in the order groups first appear), then by size; waves filled up to max_agents_per_wave
  parallel    all scopes are equal; waves filled up to max_agents_per_wave, largest first
Light pass: scopes.json `light` (method rule, e.g. dead unit or size < scoring.light_pass_size) or scoring.light_pass_scopes / --light.
Skipped: scopes.json `skip`, scoring.skip_scopes or --skip - not analysed at all.
"""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, WAVES_PATH, SCOPES_PATH, STATUS_PATH, project, method, load_json, scope_info

def registered(scopes):
    """{scope: wave} of the scopes state/STATUS.json already registered with a wave number (rule `after`: they keep it)"""
    st = (load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}).get("scopes") or {}
    return {k: v["wave"] for k, v in st.items() if k in scopes and isinstance(v, dict) and isinstance(v.get("wave"), int) and not isinstance(v.get("wave"), bool)}

def started(name):
    """a registered scope has begun: STATUS moved it past `open`, or its analysis exists"""
    v = ((load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}).get("scopes") or {}).get(name) or {}
    return v.get("status") not in (None, "open") or os.path.exists(scope_info(name)[0])

def keep_registered(scopes, order, deps, reg, maxw):
    """rule `after` once scopes are registered: a registered scope keeps its wave - registered waves are never renumbered, so STATUS,
    WAVES.json and the wave gate agree. A new scope goes into the first wave that has not started (no member began), and strictly after
    the waves of its dependencies; when that wave already holds max_agents_per_wave scopes, the overflow goes into a new wave appended
    after the last registered wave (filled up to max_agents_per_wave, then the next). -> [(wave, [scopes])]"""
    wave = dict(reg); last = max(reg.values()); members = defaultdict(list)
    for k in order:
        if k in reg: members[reg[k]].append(k)
    first_open = max([w + 1 for k, w in reg.items() if started(k)] + [min(reg.values())])
    for k in order:
        if k in reg: continue
        w = max([first_open] + [wave[d] + 1 for d in deps[k] if d in wave])
        if w <= last and len(members[w]) >= maxw: w = last + 1   # the first open wave is full: overflow behind the last registered wave
        while w > last and len(members[w]) >= maxw: w += 1
        wave[k] = w; members[w].append(k)
    return [(n, members[n]) for n in sorted(members) if members[n]]

def main():
    argv = sys.argv[1:]; p = project(); sc = p["scoring"]; m = method(); maxw = sc["max_agents_per_wave"]; rule = m["scopes"].get("wave_rule", "parallel")
    skip = set(sc.get("skip_scopes", []) or sc.get("skip_units", [])); light_cfg = set(sc.get("light_pass_scopes", []) or sc.get("light_pass_units", [])); light_size = sc.get("light_pass_size", sc.get("light_pass_loc", 1000))
    if "--max" in argv: maxw = int(argv[argv.index("--max") + 1])
    if "--skip" in argv: skip |= set(argv[argv.index("--skip") + 1].split(","))
    if "--light" in argv: light_cfg |= set(argv[argv.index("--light") + 1].split(","))
    if not os.path.exists(SCOPES_PATH): sys.exit(f"missing state/scopes.json - run the method's discover tool ({'discover' if str(m['scopes'].get('discover', '')).startswith('generic:') else m['scopes'].get('discover', 'discover')}) first")
    sj = load_json(SCOPES_PATH); allsc = sj["scopes"]; rule = sj.get("wave_rule") or rule
    skip |= {k for k, v in allsc.items() if v.get("skip")}
    scopes = {k: v for k, v in allsc.items() if k not in skip}
    deps = {k: [d for d in (v.get("depends_on") or []) if d in scopes] for k, v in scopes.items()}
    dependents = defaultdict(set)
    for k, ds in deps.items():
        for d in ds: dependents[d].add(k)
    def trans(k, seen=None):
        seen = seen if seen is not None else set()
        for d in dependents[k]:
            if d not in seen: seen.add(d); trans(d, seen)
        return seen
    core = {k: len(trans(k)) for k in scopes}; size = {k: int(scopes[k].get("size") or 0) for k in scopes}
    def light_reason(k):
        if k in light_cfg: return "listed in scoring.light_pass_scopes"
        if scopes[k].get("light") is True: return scopes[k].get("light_reason") or "method rule"
        if scopes[k].get("light") is None and size[k] and size[k] < light_size: return f"size {size[k]} < {light_size}"
        return ""
    if rule == "dependency":
        indeg = {k: len(deps[k]) for k in scopes}; level = {}
        frontier = sorted([k for k in scopes if indeg[k] == 0], key=lambda k: (-core[k], -size[k], k)); lvl = 0
        while frontier:
            nxt = []
            for k in frontier:
                level[k] = lvl
                for d in dependents[k]:
                    indeg[d] -= 1
                    if indeg[d] == 0: nxt.append(d)
            frontier = sorted(nxt, key=lambda k: (-core[k], -size[k], k)); lvl += 1
        cyc = [k for k in scopes if k not in level]
        for k in cyc: level[k] = lvl
        order = sorted(scopes, key=lambda k: (level[k], -core[k], -size[k], k))
    elif rule == "group":
        groups = []
        for k in scopes:
            g = scopes[k].get("group", "")
            if g not in groups: groups.append(g)
        order = sorted(scopes, key=lambda k: (groups.index(scopes[k].get("group", "")), -size[k], k)); cyc = []; level = {k: groups.index(scopes[k].get("group", "")) for k in scopes}
    elif rule == "after":
        level, cyc = {}, []
        def lv(k, stack=()):
            if k in level: return level[k]
            if k in stack: cyc.append(k); return 0
            x = max([int(scopes[k].get("level") or 0)] + [lv(d, stack + (k,)) + 1 for d in deps[k]]); level[k] = x; return x
        for k in scopes: lv(k)
        cyc = sorted(set(cyc)); order = sorted(scopes, key=lambda k: (level[k], -size[k], k))
    else:
        order = sorted(scopes, key=lambda k: (-size[k], k)); cyc = []; level = {k: 0 for k in scopes}
    reg = registered(scopes) if rule == "after" else {}
    if reg: numbered = keep_registered(scopes, order, deps, reg, maxw)
    else:
        waves, done, cur = [], set(), []
        for k in order:
            ok = all(d in done or d in cur for d in deps[k]) if rule == "dependency" else (not cur or level[cur[0]] == level[k]) if rule == "after" else True
            if len(cur) >= maxw or not ok:
                if cur: waves.append(cur); done |= set(cur); cur = []
            cur.append(k)
        if cur: waves.append(cur)
        numbered = [(i + 1, w) for i, w in enumerate(waves)]
    waves = [w for _, w in numbered]
    out = {"max_per_wave": maxw, "rule": rule, "noun": sj.get("noun", "scope"), "skipped": sorted(skip), "cycles": cyc,
           "light_rule": f"scopes.json light flag (method rule), or size < {light_size} when the method leaves it open, or listed in scoring.light_pass_scopes. Light scopes get the light gauntlet (models.critic_client_light, scoring.max_gauntlet_rounds_light)",
           "waves": [{"wave": n, "units": w, "scopes": w, "members": [{"name": k, "group": scopes[k].get("group", ""), "level": level[k], "transitive_dependents": core[k], "size": size[k], "depends_on": deps[k], "required_by": sorted(dependents[k]), "light_pass": bool(light_reason(k)), "light_reason": light_reason(k), "meta": scopes[k].get("meta", {})} for k in w]} for n, w in numbered]}
    os.makedirs(os.path.dirname(WAVES_PATH), exist_ok=True); json.dump(out, open(WAVES_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for w in out["waves"]: print(f"wave {w['wave']}: " + ", ".join(f"{x['name']}[{x['group']},dep={x['transitive_dependents']},size={x['size']}{(',light: ' + x['light_reason']) if x['light_pass'] else ''}]" for x in w["members"]))
    if skip: print("skipped (not analysed):", ", ".join(sorted(skip)))
    if cyc: print("WARNING dependency cycle among:", cyc)
    print(f"-> state/WAVES.json ({rule} rule, {len(waves)} waves)")
    import retrieval; retrieval.build_map(p)   # the corpus map right after discover (nothing without an indexed corpus; `render brief` refreshes it)

if __name__ == "__main__":
    main()
