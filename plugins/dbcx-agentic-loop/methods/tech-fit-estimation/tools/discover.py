#!/usr/bin/env python3
"""Scopes of the tech-fit-estimation method: chunks of the client's requirement list -> state/scopes.json
(consumed by `dbcx plan_waves`, `dbcx render`, `dbcx progress`, briefing.py).

Usage: dbcx discover [--min N] [--max N] [--light N] [--by epic|group-epic] [--dry-run]
Refused (except --dry-run) while the row classification of an imported code-analysis handover is open (`dbcx classify`): the
technical migration and refactoring rows it appends are chunked like every other row (their epic is the class label).

Chunking (defaults from method.json -> unit.min_chunk / max_chunk / light_chunk):
  * requirements are grouped by their `epic` field (state/requirements.json); rows without an epic form the chunk `epic-unassigned`
  * an epic with more than max_chunk requirements is split into parts of at most max_chunk (in list order)
  * epics with fewer than min_chunk requirements are merged, in list order, into mixed chunks of at most max_chunk
  * a chunk with at most light_chunk requirements is marked `light` (light gauntlet, sonnet analyst)
  * max_chunk and light_chunk are per option: with N options (run.json `options`) both are divided by N (max_chunk at least min_chunk),
    because every chunk is estimated for every option
Chunk NAMES are neutral (`epic-01`, `epic-02`, ...), never the epic text: a scope name reaches the hook's
"no client data to external services" check, and a domain word there would block every vendor-documentation query
(hooks/dbcx_hook.py H3). The epic names travel in `meta.EPICS` and reach every brief and the deliverable from there.

System mode (run.json `systems`, ) - the unit is the WORK PACKAGE
`<row>@<system>:<option>[@<parent option>]` = an affected impact cell (state/impact.json; before the scope step is applied, the
deterministic pre-fill) x every option of an agent-estimated system (x every parent option of a dependent system when the row touches the
parent too); systems estimated by a partner, the client or a team get no work package:
  dbcx discover [--dry-run] [--force]   chunks PER SYSTEM OPTION, as few as unit.context_budget allows (estimated tokens of the rows, their work
                                        packages, context rows and BASELINE; the rows take at most half): (group, epic) blocks first fit, small epics
                                        share a chunk, only an oversize epic is split; no division by the number of options (a chunk belongs to one
                                        option); light = at most unit.light_chunk work packages. Names <system>-NN (one option) or <system>-<option>-NN.
                                        A dependent system's chunks depend on every chunk of its parent; scopes.json `wave_rule: after` makes
                                        `dbcx plan_waves` put them in a later wave. Refused once a chunk started (use --pickup) unless --force.
  dbcx discover --pickup [--dry-run]    the next wave: the work packages of the current impact matrix against the planned ones and the
                                        architect's open follow-ups (state/architect.json `changes`, folded per package) - new -> follow-up chunks
                                        in the first wave that has not started (scopes.json `level`; a dependent system's follow-up after every
                                        chunk of its parent), withdrawn -> marked `withdrawn` (its estimation row is dropped), re-brief ->
                                        re-estimated in a follow-up chunk (the old package `superseded`), or updated in place while its chunk has
                                        not started (the architect's note on the package); an external or landscape cell of the architect is an
                                        input cell of the workbook, no chunk. Cascade: a re-briefed or withdrawn package re-briefs / withdraws the
                                        packages of its dependent systems for the same row (with that parent option); a dependent package whose
                                        parent package moves to a follow-up moves with it. Every open change of state/impact.json and
                                        state/architect.json is marked `picked_up`. Then `dbcx plan_waves` and register the new chunks.
"""
import os, sys

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, SCOPES_PATH, REQ_PATH, project, load_json, save_json, options, relp


def arg(name, default):
    a = sys.argv[1:]
    if name in a:
        v = a[a.index(name) + 1]
        return int(v) if v.isdigit() else v
    return default


def main():
    p = project()
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import tfe_model as TM
    if TM.system_mode(p): return system_main(p, TM)
    if "--pickup" in sys.argv: sys.exit("REFUSED: --pickup picks up work-package changes of a run with run.json `systems` - this run has none")
    u = p.get("unit", {}); n = len(options(p))   # every chunk is estimated for every option: the sizes are per option
    min_c = int(arg("--min", u.get("min_chunk", 5))); max_c = int(arg("--max", max(min_c, int(u.get("max_chunk", 25)) // n))); light_c = int(arg("--light", max(1, int(u.get("light_chunk", 8)) // n)))
    by = arg("--by", "epic")
    req = load_json(REQ_PATH, None)
    if not req or not req.get("requirements"):
        sys.exit(f"missing or empty {relp(REQ_PATH, ROOT)} - import the client's requirement list first (`dbcx requirements_to_json` or `dbcx handover import requirements-set`)")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import tfe_model as TM
    bad = TM.decision_errors(p, req["requirements"])
    if bad: sys.exit("REFUSED: " + "; ".join(bad))
    gone = TM.excluded(p); rows = [r for r in req["requirements"] if r["id"] not in gone]   # a merged or dropped row has no estimation row
    refs = TM.reference_ids(rows); rows = [r for r in rows if r["id"] not in refs]   # rows of a group with estimate: false are context only
    ierr, _ = TM.input_check(p)
    if ierr: sys.exit("REFUSED: input errors (dbcx build_excel --check lists them all): " + "; ".join(ierr))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from classify import hold_line   # the row classification comes first
    hold = hold_line(p)
    if hold and "--dry-run" not in sys.argv: sys.exit(f"REFUSED: the row classification is not done - {hold}")

    # group by epic (optionally by group+epic) in list order
    keyed = {}
    for r in rows:
        epic = (r.get("epic") or "").strip() or "unassigned"
        k = f"{r.get('group', '')} / {epic}" if by == "group-epic" else epic
        keyed.setdefault(k, []).append(r)

    # split large epics, then merge small ones
    parts = []          # [(label, [rows])]
    small = []
    for k, rs in keyed.items():
        if len(rs) > max_c:
            n = (len(rs) + max_c - 1) // max_c
            for i in range(n):
                sl = rs[i * max_c:(i + 1) * max_c]
                parts.append((f"{k} ({i + 1}/{n})", sl))
        elif len(rs) < min_c:
            small.append((k, rs))
        else:
            parts.append((k, rs))
    cur_lbl, cur_rows = [], []
    for k, rs in small:
        if cur_rows and len(cur_rows) + len(rs) > max_c:
            parts.append((" + ".join(cur_lbl), cur_rows)); cur_lbl, cur_rows = [], []
        cur_lbl.append(k); cur_rows = cur_rows + rs
    if cur_rows: parts.append((" + ".join(cur_lbl), cur_rows))

    scopes = {}
    for i, (label, rs) in enumerate(parts, 1):
        name = f"epic-{i:02d}"
        groups = sorted({(r.get("group") or "").strip() for r in rs if r.get("group")})
        releases = sorted({(r.get("phase") or "").strip() for r in rs if r.get("phase")})
        ids = [r["id"] for r in rs]
        light = len(rs) <= light_c
        scopes[name] = {
            "group": groups[0] if len(groups) == 1 else "mixed",
            "depends_on": [],
            "size": len(rs),
            "light": light,
            "light_reason": f"{len(rs)} requirements <= {light_c} (light chunk: essentials only, light gauntlet)" if light else "",
            "skip": False,
            "meta": {
                "EPICS": label,
                "REQUIREMENT COUNT": len(rs),
                "GROUPS": ", ".join(groups) or "-",
                "RELEASES": ", ".join(releases) or "-",
                "FIRST/LAST ID": f"{ids[0]} ... {ids[-1]}" if ids else "-",
                "req_ids": ids,
            },
        }
    out = {"noun": p.get("unit", {}).get("chunk_noun", "Epic chunk"), "method": "tech-fit-estimation",
           "source": f"{relp(REQ_PATH, ROOT)} ({len(rows)} requirements, {len(keyed)} epics; min {min_c} / max {max_c} per chunk, light <= {light_c})",
           "rule": "one chunk per epic; large epics split, small epics merged; chunk names are neutral (epic-NN), the epic text lives in meta.EPICS",
           "scopes": scopes}
    if "--dry-run" in sys.argv:
        for n, s in scopes.items(): print(f"{n}: {s['size']:3d} req  {'light' if s['light'] else 'full '}  {s['meta']['EPICS']}")
        print(f"DRY RUN: {len(scopes)} chunks over {len(rows)} requirements - nothing written"); return
    save_json(SCOPES_PATH, out)
    for n, s in scopes.items(): print(f"{n}: {s['size']:3d} req  {'light' if s['light'] else 'full '}  {s['meta']['EPICS']}")
    covered = sum(s["size"] for s in scopes.values())
    print(f"{len(scopes)} chunks over {covered} of {len(rows)} requirements -> state/scopes.json ({sum(1 for s in scopes.values() if s['light'])} light)" + (f"; {len(gone)} decided row(s) not chunked ({', '.join(sorted(gone))})" if gone else "")
          + (f"; {len(refs)} reference row(s) (estimate: false) not chunked" if refs else ""))
    if covered != len(rows): print(f"WARNING: {len(rows) - covered} requirements are in no chunk - they would reach the workbook as NOT ASSESSED")


def show(scopes):
    for n, s in scopes.items(): print(f"{n}: {s['size']:3d} wp  {'light' if s['light'] else 'full '}  {s['option_key']}  ~{s['tokens']} tokens  {s['meta']['EPICS']}" + (f"  after {', '.join(s['depends_on'])}" if s["depends_on"] else ""))


def refuse_inputs(p, TM, req):
    bad = TM.decision_errors(p, req["requirements"])
    if bad: sys.exit("REFUSED: " + "; ".join(bad))
    ierr, _ = TM.input_check(p)
    if ierr: sys.exit("REFUSED: input errors (dbcx build_excel --check lists them all): " + "; ".join(ierr))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from classify import hold_line   # the row classification comes first
    hold = hold_line(p)
    if hold and "--dry-run" not in sys.argv: sys.exit(f"REFUSED: the row classification is not done - {hold}")


def link_parents(scopes):
    """depends_on of a dependent system's chunk = every chunk of its parent system among these chunks (a discover; a pickup links its follow-ups to every chunk of the parent)"""
    for e in scopes.values():
        if e.get("parent_system"): e["depends_on"] = sorted(k for k, x in scopes.items() if x.get("system") == e["parent_system"])


def system_main(p, TM):
    """state/scopes.json of a multi-system run: chunks per system option over the work packages"""
    req = load_json(REQ_PATH, None)
    if not req or not req.get("requirements"):
        sys.exit(f"missing or empty {relp(REQ_PATH, ROOT)} - import the client's requirement list first (`dbcx requirements_to_json` or `dbcx handover import requirements-set`)")
    refuse_inputs(p, TM, req)
    if "--pickup" in sys.argv: return pickup(p, TM)
    model = TM.system_model(p); rows = TM.estimating_rows(p); u = p.get("unit", {}); light_c = int(arg("--light", int(u.get("light_chunk", 8))))
    old = load_json(SCOPES_PATH, None) if os.path.exists(SCOPES_PATH) else None
    if old and any(TM.started(ROOT, n) for n in (old.get("scopes") or {})) and "--force" not in sys.argv and "--dry-run" not in sys.argv:
        sys.exit("REFUSED: chunks of state/scopes.json have started - `dbcx discover --pickup` puts the changed work packages into the next wave (--force re-chunks everything)")
    cells, basis = TM.impact_basis(p, model, rows); wps = TM.work_package_list(model, cells, rows)
    scopes = TM.plan_system_chunks(p, model, rows, wps, light_c=light_c); link_parents(scopes)
    ext = [s["id"] for s in model["systems"] if s["estimated_by"] != "agents"]
    out = {"noun": u.get("chunk_noun", "Epic chunk"), "method": "tech-fit-estimation", "mode": "systems", "wave_rule": TM.WAVE_RULE,
           "source": f"{relp(REQ_PATH, ROOT)} ({len(rows)} estimating rows) x {basis['source']}: {len(wps)} work packages; context budget {TM.budget_of(p) * 2} (rows <= {TM.budget_of(p)}), light <= {light_c}",
           "rule": "chunks per system option, as few as the context budget allows (epics whole where they fit, small epics share a chunk, only an oversize epic is split); a dependent system's chunks after every chunk of its parent",
           "impact_basis": basis, "context_budget": TM.budget_of(p) * 2, "pickups": [], "scopes": scopes}
    show(scopes)
    if "--dry-run" in sys.argv: print(f"DRY RUN: {len(scopes)} chunks over {len(wps)} work packages - nothing written"); return
    save_json(SCOPES_PATH, out)
    rowsin = {w["row"] for w in wps}
    print(f"{len(scopes)} chunks over {len(wps)} work packages of {len(rowsin)} of {len(rows)} estimating rows -> state/scopes.json ({sum(1 for s in scopes.values() if s['light'])} light; work packages from {basis['source']})"
          + (f"; no work package for the systems estimated outside the agents ({', '.join(ext)})" if ext else ""))
    if basis["source"] == "pre-fill": print("NOTE: the scope step is not applied yet - the work packages rest on the pre-fill; `dbcx impact apply` and then `dbcx discover --pickup` bring the triage into the next wave")
    print("NEXT: `dbcx plan_waves` (rule after: the chunks of a dependent system come after every chunk of its parent), then register every chunk")


def pickup(p, TM):
    """`dbcx discover --pickup`: the changed work packages into the next wave (follow-up chunks), withdrawn ones marked, open changes picked up -
    the impact matrix's changes, the architect's follow-ups (state/architect.json `changes`) and their cascade to the
    dependent systems' packages of the same row"""
    sj = load_json(SCOPES_PATH, None) if os.path.exists(SCOPES_PATH) else None
    if not sj or sj.get("mode") != "systems": sys.exit("REFUSED: no work-package plan - `dbcx discover` first")
    import gaps as G
    model = TM.system_model(p); rows = TM.estimating_rows(p); light_c = int(p.get("unit", {}).get("light_chunk", 8))
    pend = TM.pending(p, model, sj); sc = sj["scopes"]; have = TM.planned(sj); want = TM.wanted(p, model); wpk = {}
    for k in list(have) + [w["key"] for w in pend["new"]]: wpk.setdefault(TM.parse_wp(k)["cell"], []).append(k)   # impact cell -> its packages, before the plan changes
    imp = TM.load(ROOT, TM.IMPACT_PATH, None) or {}; open_ch = [c for c in imp.get("changes") or [] if not c.get("picked_up")]
    ast = TM.load(ROOT, G.ARCH_PATH, None) or {}; open_ac = [c for c in ast.get("changes") or [] if not c.get("picked_up")]
    if not any(pend.values()) and not open_ch and not open_ac: print("(nothing to pick up - the planned work packages match the impact matrix and the architect's decisions)"); return
    status = load_json(os.path.join("state", "STATUS.json"), {}) if os.path.exists(os.path.join(ROOT, "state", "STATUS.json")) else {}
    now = __import__("time").strftime("%Y-%m-%dT%H:%M:%S"); n_pick = len(sj.get("pickups") or []) + 1; done = []

    # 1. one operation per work package: the impact matrix first, then the architect's net follow-up (its latest open record carries the note)
    ops = {w["key"]: {"op": "new", "wp": w} for w in pend["new"]}
    ops.update({w["key"]: {"op": "withdrawn", "chunk": n, "wp": w} for n, w in pend["withdrawn"]})
    ops.update({w["key"]: {"op": "re-brief", "chunk": n, "wp": w, "impact": t} for n, w, t in pend["re-brief"]})
    last = {c["work_package"]: c for c in open_ac}; external = []; cells = TM.work_packages(imp)
    for k, ch in TM.net_changes(open_ac).items():
        rec = last[k]; note = {"change": rec["id"], "decision": rec.get("decision"), "note": rec.get("brief_note") or "", "final": bool(rec.get("final")), "pickup": n_pick}
        if rec.get("external") or ":" not in k: external.append(k); continue   # an external / landscape cell: an input cell of the workbook, no chunk
        o, hit = ops.get(k), have.get(k)
        if o and o["op"] == "withdrawn": continue   # the lead removed the cell after the decision: the matrix wins
        if ch == "withdrawn" and not hit: continue
        if ch == "withdrawn" and k not in want: ops[k] = {"op": "withdrawn", "chunk": hit[0], "wp": hit[1], "architect": note}; continue
        if hit: ops[k] = dict(o or {"op": "re-brief", "chunk": hit[0], "wp": hit[1]}, architect=note)
        elif o: o["architect"] = note
        else:
            w = TM.parse_wp(k)
            ops[k] = {"op": "new", "architect": note, "wp": {"key": k, "row": w["row"], "system": w["system"], "option": w["option"], "parent": w["parent"], "value": TM.option_value(w["option"], w["parent"]),
                                                             "impact": cells.get(w["cell"], ""), **({} if k in want else {"origin": TM.ORIGIN_ARCHITECT})}}

    # 2. cascade: a re-briefed or withdrawn parent package re-briefs / withdraws its dependent systems' packages of the same row
    queue = [k for k, o in ops.items() if o["op"] != "new"]; n_casc = 0
    while queue:
        k = queue.pop(0); o = ops[k]
        for n, w in TM.dependent_packages(sj, model, k):
            if w["key"] in ops: continue
            gone = o["op"] == "withdrawn" and w["key"] not in want and w.get("origin") != TM.ORIGIN_ARCHITECT
            ops[w["key"]] = {"op": "withdrawn" if gone else "re-brief", "chunk": n, "wp": w, "cascade": {"parent": k, "change": o["op"], "pickup": n_pick}}; queue.append(w["key"]); n_casc += 1

    # 3. apply: withdrawn -> marked; re-brief -> in place while its chunk has not started and its parent stays put, else re-estimated in a
    # follow-up chunk; new -> a follow-up chunk. Parents first (a dependent package moves with its parent package)
    def entry_of(name, key): return next(w for w in TM.chunk_wps(sc[name], None) if w["key"] == key and w.get("status", TM.ACTIVE) == TM.ACTIVE)
    depth = {}
    for s in model["systems"]:
        x, d = s, 0
        while x.get("depends_on"): x = next(y for y in model["systems"] if y["id"] == x["depends_on"]); d += 1
        depth[s["id"]] = d
    follow, moved = [], set()
    for k, o in sorted(ops.items(), key=lambda kv: depth.get(kv[1]["wp"]["system"], 0)):
        extra = {x: o[x] for x in ("architect", "cascade") if o.get(x)}; why = " (architect)" if o.get("architect") else f" (cascade from {o['cascade']['parent']})" if o.get("cascade") else ""
        if o["op"] == "new": follow.append(dict(o["wp"], **extra)); moved.add(k); done.append(f"{k} new{why}"); continue
        e = entry_of(o["chunk"], k)
        if o["op"] == "withdrawn": e.update(status=TM.WITHDRAWN, at=now, pickup=n_pick, **extra); done.append(f"{k} withdrawn ({o['chunk']}){why}"); continue
        text = o.get("impact") if o.get("impact") is not None else e.get("impact") or ""; pk = TM.parent_key(e, model); st = TM.started(ROOT, o["chunk"], status)
        if st or pk in moved:
            e.update(status=TM.SUPERSEDED, at=now, pickup=n_pick); w2 = TM.parse_wp(k); moved.add(k)
            follow.append({"key": k, "row": w2["row"], "system": w2["system"], "option": w2["option"], "parent": w2["parent"], "value": e["value"], "impact": text,
                           **({"origin": e["origin"]} if e.get("origin") else {}), **({"previous": {"chunk": o["chunk"], "impact": e.get("impact") or ""}} if st else {}), **extra})
            done.append(f"{k} re-brief (re-estimated after {o['chunk']}){why}" if st else f"{k} re-brief (moved out of {o['chunk']} behind its parent's follow-up){why}")
        else: e.update(impact=text, **extra); done.append(f"{k} re-brief (in place: {o['chunk']} has not started){why}")
    new = {}
    if follow:   # the first wave that has not started: after every started chunk (a dependent system's follow-up also after every chunk of its parent)
        lv = TM.levels(sj); base = max([lv[n] + 1 for n in sc if TM.started(ROOT, n, status)] + [0])
        new = TM.plan_system_chunks(p, model, rows, follow, taken=list(sc), light_c=light_c, followup=n_pick)
        for x in new.values():
            x["level"] = base
            if x.get("parent_system"): x["depends_on"] = sorted(n for n, e in list(sc.items()) + list(new.items()) if e.get("system") == x["parent_system"] and not e.get("skip"))
    for n, e in sc.items():   # a chunk left without an active work package before it started is not analysed at all
        if not TM.chunk_wps(e) and not TM.started(ROOT, n, status) and not e.get("skip"): e.update(skip=True, skip_reason=f"every work package withdrawn or moved (pickup {n_pick})"); done.append(f"{n} skipped (nothing left)")
    for c in open_ch: c.update(picked_up=True, picked_up_at=now, pickup=n_pick, work_packages=wpk.get(c["work_package"], []))
    for c in open_ac: c.update(picked_up=True, picked_up_at=now, pickup=n_pick, **({"external_cell": True} if c["work_package"] in external else {}))
    if "--dry-run" in sys.argv:
        show(new); print("\n".join(done) or "(nothing to pick up)"); print(f"DRY RUN: pickup {n_pick} - nothing written"); return
    sc.update(new); sj.setdefault("pickups", []).append({"pickup": n_pick, "at": now, "new": len(pend["new"]), "withdrawn": len(pend["withdrawn"]), "re-brief": len(pend["re-brief"]),
                                                          "chunks": sorted(new), "changes": [c["id"] for c in open_ch], "architect_changes": [c["id"] for c in open_ac], "cascade": n_casc, "external": external})
    save_json(SCOPES_PATH, sj)
    if open_ch: save_json(TM.IMPACT_PATH, imp)
    if open_ac: save_json(G.ARCH_PATH, ast)
    show(new)
    print(f"pickup {n_pick}: {len(pend['new'])} new, {len(pend['withdrawn'])} withdrawn, {len(pend['re-brief'])} re-brief work package(s); {len(new)} follow-up chunk(s)"
          + (f" ({', '.join(sorted(new))})" if new else "") + f"; {len(open_ch)} change(s) of state/impact.json picked up"
          + (f"; {len(open_ac)} follow-up(s) of the architect picked up" if open_ac else "") + (f"; cascade: {n_casc} dependent work package(s)" if n_casc else "")
          + (f"; external input cell(s), no chunk: {', '.join(external)}" if external else ""))
    for x in done: print("  " + x)
    if new: print("NEXT: `dbcx plan_waves`, then register the follow-up chunk(s): " + ", ".join(f"`dbcx status scope {n} '{{\"wave\": <n>, \"status\": \"open\"}}'`" for n in sorted(new)))


if __name__ == "__main__":
    main()
