#!/usr/bin/env python3
"""The scope step of tech-fit-estimation: which systems of the run every
requirement row touches, with one impact text per system - decided before the estimation, by evidence, automatically. Runs in system
mode only (run.json `systems`); a run without `systems` has no scope step.

Usage: dbcx impact plan [--force]          the pre-fill (systems_field, interface ends, row classes) and the triage chunks: as few as the
                                           context budget allows (unit.context_budget) -> work/impact-plan.json and per chunk the skeleton
                                           analysis/triage/<TRIAGE | TRIAGE-n>.md with every row and its pre-filled systems
       dbcx impact apply                   merge pre-fill + the converted triage (analysis/triage/*.json) + the dashboard overrides ->
                                           state/impact.json; refused while a row is not covered, a system is unknown or an impact text is
                                           missing. Applied automatically: nothing waits for a person. Run it again after every triage
                                           gauntlet round (a failed claim marks its impacts `disputed`) and after a triage rework
       dbcx impact show [--system S] [--row R]   the matrix (row x system: source, status, impact text)
       dbcx impact override add|remove|edit <row> <system> [--impact "..."] [--reason "..."] [--by <name>] [--entry <inbox id>]
                                           an override record (the dashboard's "Impact per system" view sends the same through the inbox;
                                           `dbcx inbox apply` calls this); add / edit need the impact text, remove the reason
       dbcx impact changes [--json] [--all]   the impact cells (<row>@<system>) the impact matrix changed after `dbcx discover` planned the
                                           waves: new (a system added) | withdrawn (removed) | re-brief (impact text changed), each with the work
                                           packages <row>@<system>:<option>[@<parent option>] it maps to; `dbcx discover --pickup` puts them into
                                           the next wave and marks them picked_up
`dbcx status next` names the step before `dbcx discover` (it holds nothing: discover never waits for it) and, beside the waves, the triage
gauntlet (extract_claims / critics / score_aggregate on TRIAGE) and the open work-package changes.
"""
import hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); MDIR = os.path.dirname(HERE)
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
sys.path.insert(0, MDIR)
from common import RUN as ROOT, P, CLI, SCOPES_PATH, STATUS_PATH, WAVES_PATH, load_json, save_json, project, relp
import tfe_model as TM

ACTIONS = ("add", "remove", "edit")


def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def opt(a, k, d=""): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
def rel(p): return relp(p, ROOT).replace(os.sep, "/")
def sha(fp): return hashlib.sha256(open(fp, "rb").read()).hexdigest() if os.path.exists(fp) else None
def plan(): return load_json(P(TM.PLAN_PATH), {}) if os.path.exists(P(TM.PLAN_PATH)) else {}
def impact(): return load_json(P(TM.IMPACT_PATH), {}) if os.path.exists(P(TM.IMPACT_PATH)) else {}
def md_of(scope): return P(TM.TRIAGE_DIR, f"{scope}.md")
def js_of(scope): return P(TM.TRIAGE_DIR, f"{scope}.json")


def skeleton(part, by, model, lang):
    """the triage chunk's skeleton: every row with its pre-filled systems (affected yes, impact and reason to fill), a row without pre-fill once with
    an empty system"""
    lines = []
    for rid in part["rows"]:
        pre = TM.prefill(by[rid], model)
        lines += [f"| {rid} | {sid} | yes |  |  |" for sid in pre] or [f"| {rid} |  |  |  |  |"]
    agent = "consolidate-triage" + ("" if part["scope"] == TM.TRIAGE_SCOPE else "-" + part["scope"].rsplit("-", 1)[1])
    return "\n".join([f"# Impact per system (triage {part['scope']})", "", f"- **agent:** {agent}", f"- **scope:** {part['scope']}", "- **status:** draft", "- **round:** 0", "",
                      "## Summary", "", "(3-5 sentences: how many rows per system, the rows that touch no system, the close calls)", "",
                      "## Impacts", "", "| row_id | system | affected | impact | reason |", "|---|---|---|---|---|", *lines, "",
                      "## Claims", "", "| id | type | statement | evidence | target | supersedes |", "|---|---|---|---|---|---|", ""])


def cmd_plan(cfg, force):
    model = TM.system_model(cfg); rows = TM.estimating_rows(cfg)
    if not rows: sys.exit(f"REFUSED: no estimating row in state/requirements.json - import the requirement list first (`{CLI} requirements_to_json`)")
    old = plan(); parts = TM.triage_parts(cfg, rows)
    if old and not force and [r["id"] for r in rows] == [x for p in old.get("parts") or [] for x in p["rows"]]:
        parts = old["parts"]; print(f"{rel(P(TM.PLAN_PATH))}: unchanged ({len(parts)} chunk(s))")
    elif old and any(os.path.exists(js_of(p["scope"])) for p in old.get("parts") or []) and not force:
        sys.exit(f"REFUSED: the estimating rows changed since the plan and a triage file exists - `{CLI} impact plan --force` re-chunks (the agents' files stay; the CHECK lists the rows a chunk misses)")
    by = {r["id"]: r for r in rows}; lang = cfg["languages"]["deliverable"]; os.makedirs(P(TM.TRIAGE_DIR), exist_ok=True); wrote = []
    for p in parts:
        if not os.path.exists(md_of(p["scope"])): open(md_of(p["scope"]), "w", encoding="utf-8").write(skeleton(p, by, model, lang)); wrote.append(rel(md_of(p["scope"])))
    budget = int(((cfg.get("unit") or {}).get("context_budget")) or TM.CONTEXT_BUDGET)
    save_json(P(TM.PLAN_PATH), {"at": old.get("at") if old.get("parts") == parts else now(), "context_budget": budget, "parts": parts})
    pre = sum(1 for r in rows if TM.prefill(r, model))
    print(f"scope step: {len(rows)} estimating row(s), {pre} with a pre-fill; {len(parts)} triage chunk(s) under the context budget {budget} ({', '.join(p['scope'] + ' ' + str(len(p['rows'])) + ' rows ~' + str(p['tokens']) + ' tokens' for p in parts)})"
          + (f"; skeleton(s) {', '.join(wrote)}" if wrote else ""))
    print("NEXT: " + (step_line(cfg) or "-"))


def recompute(cfg, overrides, fresh=True):
    """-> (doc, errors): the effective matrix from the pre-fill, the converted triage of every chunk and the overrides"""
    model = TM.system_model(cfg); rows = TM.estimating_rows(cfg); pl = plan(); err = []
    for p in pl.get("parts") or []:
        md, js = md_of(p["scope"]), js_of(p["scope"])
        if not os.path.exists(js): err.append(f"{p['scope']}: no {rel(js)} - convert the triage agent's file (`{CLI} md_to_json triage {rel(md)}`)")
        elif fresh and os.path.exists(md) and os.path.getmtime(md) > os.path.getmtime(js) + 1: err.append(f"{p['scope']}: {rel(md)} is newer than its JSON - convert it again")
    if err: return None, err
    scopes = [p["scope"] for p in pl["parts"]]
    tri = TM.triage_rows(ROOT, pl); dis = TM.disputed_claims(ROOT, scopes, (cfg.get("scoring") or {}).get("pass_threshold", 8))
    planned = {x for p in pl["parts"] for x in p["rows"]}; miss = [r["id"] for r in rows if r["id"] not in planned]
    if miss: err.append(f"{len(miss)} estimating row(s) in no triage chunk ({', '.join(miss[:12])}) - `{CLI} impact plan --force`")
    cells, none = TM.merge_impact(cfg, model, rows, tri, overrides, dis)
    syss = [{k: s.get(k) for k in ("id", "label", "kind", "estimated_by", "owner_label")} for s in model["systems"]]
    doc = {"method": "tech-fit-estimation", "step": "scope", "systems": syss, "rows": [r["id"] for r in rows],
           "triage": [{"scope": s, "file": rel(js_of(s)), "sha256": sha(js_of(s)), "gauntlet": gauntlet_state(s)} for s in scopes],
           "cells": cells, "none": none, "overrides": overrides}
    return doc, err + TM.impact_errors(doc, cfg, model, rows)


def gauntlet_state(scope):
    """the triage chunk's claim gauntlet as STATUS records it (score_aggregate: STATUS steps.<scope>)"""
    st = (load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}).get("steps", {}).get(scope) or {}
    return {"rounds": st.get("rounds", 0), "status": st.get("status") or "open", "passed": bool(st.get("passed"))}


def write(cfg, doc, cause):
    """state/impact.json with the work-package changes against the previous matrix once discover planned the waves (state/scopes.json); the
    first matrix after a discover on the pre-fill is compared with the impact cells the planned work packages rest on"""
    old = impact(); changes = list(old.get("changes") or [])
    if not old and os.path.exists(SCOPES_PATH):
        sj = load_json(SCOPES_PATH, {}) or {}
        if sj.get("mode") == "systems": old = TM.planned_cells(sj)
    if old and os.path.exists(SCOPES_PATH):
        n = len(changes)
        for wp, ch in TM.wp_changes(old, doc):
            n += 1; row, system = wp.rsplit("@", 1)
            changes.append({"id": f"WC-{n:03d}", "work_package": wp, "row": row, "system": system, "change": ch, "cause": cause, "at": now(), "picked_up": False})
    doc.update(status="applied", applied_at=now(), changes=changes); save_json(P(TM.IMPACT_PATH), doc)
    return [c for c in changes if c not in (old.get("changes") or [])]


def mapping(cfg):
    """{impact cell <row>@<system>: [work package keys]} - the planned packages and those of the current matrix"""
    out = {}
    sj = load_json(SCOPES_PATH, {}) if os.path.exists(SCOPES_PATH) else {}
    if (sj or {}).get("mode") != "systems": return out
    model = TM.system_model(cfg); rows = TM.estimating_rows(cfg)
    keys = list(TM.planned(sj)) + [w["key"] for w in TM.work_package_list(model, TM.impact_basis(cfg, model, rows)[0], rows)]
    for k in dict.fromkeys(keys): out.setdefault(TM.parse_wp(k)["cell"], []).append(k)
    return out


def summary(doc):
    aff = [c for c in doc["cells"] if c["affected"]]; by = {}
    for c in aff: by[c["system"]] = by.get(c["system"], 0) + 1
    st = {}
    for c in doc["cells"]: st[c["status"]] = st.get(c["status"], 0) + 1
    return (f"{len(doc['rows'])} row(s): {len(aff)} impact(s) ({', '.join(f'{k} {v}' for k, v in by.items()) or '-'}), {len(doc['none'])} row(s) touch no system"
            + f"; status {', '.join(f'{k} {v}' for k, v in st.items())}")


def cmd_apply(cfg):
    if not plan(): sys.exit(f"REFUSED: no triage plan - `{CLI} impact plan` first")
    doc, err = recompute(cfg, impact().get("overrides") or [])
    if err: print(f"REFUSED ({len(err)} problem(s); state/impact.json unchanged):"); [print("  -", e) for e in err]; sys.exit(1)
    new = write(cfg, doc, "triage " + ", ".join(f"{t['scope']} round {t['gauntlet']['rounds']}" for t in doc["triage"]))
    print(f"{rel(P(TM.IMPACT_PATH))}: applied automatically - {summary(doc)}" + (f"; {len(new)} work-package change(s) for the next wave" if new else ""))
    print("NEXT: " + (step_line(cfg) or "; ".join(also_lines(cfg)) or f"`{CLI} discover`"))


def override_error(cfg, row, system, action, text, reason):
    """why an override cannot be recorded (None when it can) - the dashboard checks the same before it writes the inbox entry"""
    doc = impact()
    if not doc: return "no state/impact.json yet - the scope step has not been applied"
    if action not in ACTIONS: return f"action {action} (add | remove | edit)"
    if row not in doc.get("rows") or []: return f"{row} is no estimating row of the impact matrix"
    if system not in {s["id"] for s in doc.get("systems") or []}: return f"{system} is no system of this run"
    cur = next((c for c in doc.get("cells") or [] if c["row"] == row and c["system"] == system), None); aff = bool(cur and cur.get("affected"))
    if action == "add" and aff: return f"{row} already touches {system} - edit its impact text instead"
    if action in ("remove", "edit") and not aff: return f"{row} does not touch {system}"
    if action in ("add", "edit") and not (text or "").strip(): return "the impact text is required (what changes in that system)"
    if action == "edit" and (text or "").strip() == (cur.get("impact") or "").strip(): return "the impact text is unchanged"
    if action == "remove" and not (reason or "").strip(): return "a removal needs its reason"
    from lint_deliverable import code_terms
    bad = code_terms(text or "", [])[:1]
    if bad: return f"impact text: {bad[0][0]} '{bad[0][1]}' - customer language: what changes in the system, never how in code"
    return None


def cmd_override(cfg, a):
    if len(a) < 4: sys.exit(__doc__)
    action, row, system = a[1], a[2], a[3]; text, reason = opt(a, "--impact"), opt(a, "--reason")
    e = override_error(cfg, row, system, action, text, reason)
    if e: sys.exit(f"REFUSED: {e}")
    doc0 = impact(); ovs = list(doc0.get("overrides") or []); oid = f"OV-{len(ovs) + 1:03d}"
    ovs.append({"id": oid, "row": row, "system": system, "action": action, "impact": text.strip(), "reason": reason.strip(), "by": opt(a, "--by", "lead"), "at": now(), **({"entry": opt(a, "--entry")} if opt(a, "--entry") else {})})
    doc, err = recompute(cfg, ovs, fresh=False)
    if err: print(f"REFUSED ({len(err)} problem(s); state/impact.json unchanged):"); [print("  -", x) for x in err]; sys.exit(1)
    new = write(cfg, doc, f"override {oid}")
    print(f"{oid}: {row} x {system} {action} recorded - {summary(doc)}" + (f"; work package(s) marked for the next wave: {', '.join(c['work_package'] + ' ' + c['change'] for c in new)}" if new else "; nothing to re-plan (no wave planned yet)"))
    return oid, new


def cmd_show(cfg, a):
    doc = impact()
    if not doc: print(f"(no state/impact.json - {step_line(cfg) or 'the scope step does not apply to this run'})"); return
    s, r = opt(a, "--system"), opt(a, "--row")
    print(f"impact matrix ({doc.get('status')}, {doc.get('applied_at')}): {summary(doc)}")
    for c in doc["cells"]:
        if (s and c["system"] != s) or (r and c["row"] != r): continue
        print(f"  {c['row']:10s} {c['system']:12s} {'x' if c['affected'] else '-'} {c['source']:8s} {c['status']:10s} {(c.get('impact') or c.get('reason') or '')[:90]}")
    for rid, n in doc["none"].items():
        if not s and (not r or rid == r): print(f"  {rid:10s} {'none':12s} - {n['source']:8s} {'':10s} {n.get('reason', '')[:90]}")


def cmd_changes(cfg, a):
    ch = impact().get("changes") or []; show = ch if "--all" in a else [c for c in ch if not c.get("picked_up")]; mp = mapping(cfg)
    if "--json" in a: print(json.dumps({"changes": show, "net": TM.net_changes(ch), **({"work_packages": {c["work_package"]: mp.get(c["work_package"], []) for c in show}} if mp else {})}, ensure_ascii=False, indent=1)); return
    if not show: print("(no open work-package change)"); return
    for c in show: print(f"  {c['id']} {c['work_package']:24s} {c['change']:10s} {c['cause']} ({c['at']})" + (" [picked up]" if c.get("picked_up") else "") + (f" -> {', '.join(c.get('work_packages') or mp.get(c['work_package'], []))}" if mp else ""))
    print("net per work package: " + ", ".join(f"{k} {v}" for k, v in TM.net_changes(ch).items()))


# ------------------------------------------------------------------ dbcx status next (method.json steps)
def step_line(cfg):
    """the scope step's next action before discover, None when it is done or does not apply (no `systems`, no requirement list yet)"""
    if not TM.scope_step(cfg) or not os.path.exists(P("state", "requirements.json")): return None
    pl = plan()
    if not pl: return (f"scope step (pre-fill + triage, applied automatically): `{CLI} impact plan`, then per triage chunk `{CLI} render brief triage <chunk> --out` -> spawn the "
                       f"triage agent -> `{CLI} md_to_json triage analysis/triage/<chunk>.md`, then `{CLI} impact apply`")
    if [r["id"] for r in TM.estimating_rows(cfg)] != [x for p in pl.get("parts") or [] for x in p["rows"]]: return f"the estimating rows changed since the triage plan - `{CLI} impact plan --force`"
    todo = [p["scope"] for p in pl["parts"] if not os.path.exists(js_of(p["scope"])) or (os.path.exists(md_of(p["scope"])) and os.path.getmtime(md_of(p["scope"])) > os.path.getmtime(js_of(p["scope"])) + 1)]
    if todo: return "triage agent(s) for " + ", ".join(todo) + f": `{CLI} render brief triage <chunk> --out` -> spawn -> `{CLI} md_to_json triage analysis/triage/<chunk>.md`; then `{CLI} impact apply`"
    doc = impact(); done = {t["scope"]: t.get("sha256") for t in doc.get("triage") or []}
    if not doc or any(done.get(p["scope"]) != sha(js_of(p["scope"])) for p in pl["parts"]): return f"`{CLI} impact apply` (pre-fill + triage -> state/impact.json, applied automatically)"
    return None


def crit(cfg, scope):
    """the critics of a triage chunk for the ALSO line (client + the standard critics of the systems it names)"""
    try:
        from common import scope_critics
        return "|".join(scope_critics(scope, cfg)) if cfg.get("_method") else "client|standard"
    except Exception: return "client|standard"


def also_lines(cfg):
    """beside the later phases: the triage claims' gauntlet per chunk (holds nothing), a gauntlet result not applied yet, the open work-package changes"""
    if not TM.scope_step(cfg) or step_line(cfg): return []
    doc = impact(); out = []
    for t in doc.get("triage") or []:
        s = t["scope"]; g = gauntlet_state(s); n = g["rounds"]
        if g != t.get("gauntlet"): out.append(f"`{CLI} impact apply` - the triage gauntlet of {s} has a new result (round {n}): a failed claim marks its impacts disputed")
        if g["status"] == "rework": out.append(f"triage {s} rework round {n + 1} (holds nothing): `{CLI} render brief triage {s} --round {n + 1} --addendum <file> --out` -> the triage agent works through analysis/gauntlet/{s}/round{n}-issues.md -> `{CLI} md_to_json triage analysis/triage/{s}.md` -> `{CLI} impact apply` -> gauntlet round {n + 1}")
        elif g["status"] not in ("passed", "final", "failed-gauntlet"): out.append(f"triage claims of {s}, gauntlet round {n + 1} (parallel to the waves, holds nothing): `{CLI} extract_claims {s}` -> `{CLI} render brief critic <{crit(cfg, s)}> {s} {n + 1} --out` -> `{CLI} score_aggregate {s} {n + 1}` -> `{CLI} impact apply`")
    net = TM.net_changes(doc.get("changes") or []); sj = load_json(SCOPES_PATH, {}) if os.path.exists(SCOPES_PATH) else {}; wp4 = (sj or {}).get("mode") == "systems"
    if net: out.append(f"{len(net)} work-package change(s) of the impact matrix wait for the next wave ({', '.join(f'{k} {v}' for k, v in list(net.items())[:6])}{' ...' if len(net) > 6 else ''}; `{CLI} impact changes`"
                       + (f"; `{CLI} discover --pickup` puts them into follow-up chunks, then `{CLI} plan_waves`)" if wp4 else ")"))
    if wp4:   # chunks of a pickup that are not registered yet
        st = (load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}).get("scopes") or {}
        if st:
            new = [n for n, e in sj.get("scopes", {}).items() if n not in st and not e.get("skip")]
            wv = {m["name"]: w["wave"] for w in ((load_json(WAVES_PATH, {}) if os.path.exists(WAVES_PATH) else {}).get("waves") or []) for m in w.get("members") or []}
            if new and all(n in wv for n in new):   # planned already: the wave WAVES.json gives it (registered waves are never renumbered)
                out.append(f"{len(new)} chunk(s) of state/scopes.json not registered ({', '.join(new[:8])}): register them in the wave `{CLI} plan_waves` gave them - "
                           + ", ".join(f"`{CLI} status scope {n} '{{\"wave\": {wv[n]}, \"status\": \"open\"}}'`" for n in new[:8]))
            elif new: out.append(f"{len(new)} chunk(s) of state/scopes.json not registered ({', '.join(new[:8])}): `{CLI} plan_waves`, then `{CLI} status scope <name> '{{\"wave\": n, \"status\": \"open\"}}'`")
    return out


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cfg = project()
    if a[0] in ("plan", "apply", "override") and not TM.scope_step(cfg): sys.exit("REFUSED: the scope step runs with run.json `systems` only - this run has none (no scope step)")
    if a[0] == "plan": cmd_plan(cfg, "--force" in a)
    elif a[0] == "apply": cmd_apply(cfg)
    elif a[0] == "override": cmd_override(cfg, a)
    elif a[0] == "show": cmd_show(cfg, a)
    elif a[0] == "changes": cmd_changes(cfg, a)
    else: sys.exit(__doc__)


if __name__ == "__main__":
    main()
