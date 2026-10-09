#!/usr/bin/env python3
"""The architect step of tech-fit-estimation: where the work of a gap goes. An analyst
estimates one system; a requirement it cannot solve there is a gap (coverage gap, gap_reason, optional route_suggestion, its own share sized).
After a wave whose analysts reported gaps, one architect agent with the customer's whole landscape decides all of them in one batch. Runs in
system mode only (run.json `systems`); nothing waits for it.

Usage: dbcx architect plan [--all] [--force]   the open gaps of the closed waves (every chunk of the wave final / failed-gauntlet / skipped;
                                           --all: of every converted analysis) -> one batch ARCHITECT-n in work/architect-plan.json and the
                                           skeleton analysis/architect/ARCHITECT-n.md (every gap, FINAL on a row's second visit). No gap: no
                                           batch. A row the architect decided twice already is guard-blocked (no third routing). Refused while
                                           the last batch waits for its agent (--force re-plans that batch)
       dbcx architect apply                the converted batches (analysis/architect/*.json) + the overrides -> state/architect.json: one
                                           decision per gap (overrule | route-estimated | route-landscape | reduce-to-standard), its status
                                           (applied | overridden | disputed) and the follow-up work packages (`changes`) for the next wave.
                                           Applied automatically; run it again after every gauntlet round of a batch
       dbcx architect show [--row R]       the decisions
       dbcx architect override <row>@<system> <decision> [--to <system | landscape id>] [--reason "..."] [--solution "..."]
                                           [--assumption "<the sentence the client confirms>"] [--by <name>] [--entry <inbox id>]
                                           an optional override (the dashboard view "Gap decisions" sends one through the inbox;
                                           `dbcx inbox apply` calls this); route-landscape and reduce-to-standard register --assumption as a
                                           client assumption (dbcx questions)
       dbcx architect changes [--json] [--all]   the follow-up work packages not yet picked up by a wave: new | withdrawn | re-brief with the
                                           brief note (same record shape as `dbcx impact changes`; `dbcx discover --pickup` consumes both)
`dbcx status next` names the step beside the waves (ALSO lines): a batch to plan, an agent to spawn, a result to apply, the batch's gauntlet.
"""
import hashlib, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); MDIR = os.path.dirname(HERE)
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
sys.path.insert(0, MDIR)
from common import RUN as ROOT, P, CLI, TOOLS, SCOPES_PATH, STATUS_PATH, load_json, save_json, project, relp
import tfe_model as TM
import gaps as G


def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def opt(a, k, d=""): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
def rel(p): return relp(p, ROOT).replace(os.sep, "/")
def sha(fp): return hashlib.sha256(open(fp, "rb").read()).hexdigest() if os.path.exists(fp) else None
def plan(): return load_json(P(G.ARCH_PLAN), {}) if os.path.exists(P(G.ARCH_PLAN)) else {}
def state(): return load_json(P(G.ARCH_PATH), {}) if os.path.exists(P(G.ARCH_PATH)) else {}
def impact(): return load_json(P(TM.IMPACT_PATH), {}) if os.path.exists(P(TM.IMPACT_PATH)) else {}
def md_of(scope): return P(G.ARCH_DIR, f"{scope}.md")
def js_of(scope): return P(G.ARCH_DIR, f"{scope}.json")
def stale(scope): return os.path.exists(md_of(scope)) and os.path.exists(js_of(scope)) and os.path.getmtime(md_of(scope)) > os.path.getmtime(js_of(scope)) + 1


def skeleton(b):
    """the batch's skeleton: one decision row per gap (decision, to, reasoning, solution, assumption to fill)"""
    n = b["scope"].rsplit("-", 1)[1]
    rows = [f"| {g['row']} | {g['system']} |  |  |  |  |  |" for g in b["gaps"]]
    final = [g["id"] for g in b["gaps"] if g.get("visit", 1) >= 2]
    return "\n".join([f"# Gap decisions (architect {b['scope']})", "", f"- **agent:** consolidate-architect-{n}", f"- **scope:** {b['scope']}", "- **status:** draft", "- **round:** 0", "",
                      "## Summary", "", "(3-5 sentences: gaps per reporting system, decisions per kind, the close calls" + (f"; FINAL decisions: {', '.join(final)}" if final else "") + ")", "",
                      "## Decisions", "", "| row_id | from_system | decision | to | reasoning | solution | assumption |", "|---|---|---|---|---|---|---|", *rows, "",
                      "## Assumptions taken", "", "| id | affects | question | reading_taken | assumption | why | if_not | alternatives |", "|---|---|---|---|---|---|---|---|", "",
                      "## Claims", "", "| id | type | statement | evidence | target | supersedes |", "|---|---|---|---|---|---|", ""])


def cmd_plan(cfg, a):
    pl = plan(); batches = list(pl.get("batches") or []); st = state(); last = batches[-1] if batches else None
    if last and not os.path.exists(js_of(last["scope"])):
        if "--force" not in a: sys.exit(f"REFUSED: {last['scope']} waits for its architect (no {rel(js_of(last['scope']))}) - finish it first, or `{CLI} architect plan --force` re-plans it")
        batches.pop(); pl = dict(pl, batches=batches)
    todo, blocked = G.open_gaps(cfg, st, pl, ROOT, all_scopes="--all" in a)
    for g in blocked: print(f"GUARD {g['id']}: the row reached the architect twice already - no third routing (the CHECK refuses this gap; the analyst estimates the final decision)")
    if not todo: print("no open gap" + (" of a closed wave" if "--all" not in a else "") + " - the architect step does not run" + (f" ({last['scope']} is the last batch)" if last else "")); return None
    scope = f"{G.ARCH_SCOPE}-{len(batches) + 1}"; waves = sorted({g["wave"] for g in todo if g.get("wave") is not None})
    b = {"scope": scope, "at": now(), "wave": waves[-1] if waves else None, "gaps": todo}
    save_json(P(G.ARCH_PLAN), {"batches": batches + [b]}); os.makedirs(P(G.ARCH_DIR), exist_ok=True)
    if not os.path.exists(md_of(scope)): open(md_of(scope), "w", encoding="utf-8").write(skeleton(b))
    fin = [g["id"] for g in todo if g["visit"] >= 2]
    print(f"{scope}: {len(todo)} gap(s) ({', '.join(g['id'] for g in todo)})" + (f"; FINAL (second visit): {', '.join(fin)}" if fin else "") + f"; skeleton {rel(md_of(scope))}")
    print("NEXT: " + (step_line(cfg) or "-")); return b


def recompute(cfg, overrides, fresh=True):
    """-> (doc, errors): the effective decisions of every converted batch and the overrides"""
    model = TM.system_model(cfg); land = G.landscape_ids(ROOT); pl = plan(); err = []; done = []
    for b in pl.get("batches") or []:
        if not os.path.exists(js_of(b["scope"])): continue
        if fresh and stale(b["scope"]): err.append(f"{b['scope']}: {rel(md_of(b['scope']))} is newer than its JSON - convert it again (`{CLI} md_to_json architect {rel(md_of(b['scope']))}`)"); continue
        d = load_json(js_of(b["scope"]), {}) or {}; done.append(dict(b, decisions=d.get("decisions") or []))
        got = {G.wp_key(x.get("row_id"), x.get("from_system")) for x in d.get("decisions") or []}
        err += [f"{b['scope']}: gap {g['id']} has no decision" for g in b["gaps"] if g["id"] not in got]
    if err: return None, err
    dis = TM.disputed_claims(ROOT, [b["scope"] for b in done], (cfg.get("scoring") or {}).get("pass_threshold", 8))
    dec = G.merge_decisions(done, overrides, model, land, dis)
    for d in dec: err += G.decision_errors(d, model, land)
    syss = [dict({k: s.get(k) for k in ("id", "label", "kind", "estimated_by", "owner_label", "depends_on")}, options=[o["id"] for o in s.get("options") or []]) for s in model["systems"]]
    doc = {"method": "tech-fit-estimation", "step": "architect", "systems": syss, "picks": [sc.get("pick") or {} for sc in model.get("scenarios") or []],
           "batches": [{"scope": b["scope"], "file": rel(js_of(b["scope"])), "sha256": sha(js_of(b["scope"])), "wave": b.get("wave"), "gaps": len(b["gaps"]), "gauntlet": gauntlet_state(b["scope"])} for b in done],
           "decisions": dec, "overrides": overrides}
    return doc, err


def gauntlet_state(scope):
    st = (load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}).get("steps", {}).get(scope) or {}
    return {"rounds": st.get("rounds", 0), "status": st.get("status") or "open", "passed": bool(st.get("passed"))}


def write(cfg, doc, cause):
    """state/architect.json with the follow-up changes against the previous state (AC-nnn, picked_up false until a wave takes them)"""
    old = state(); changes = list(old.get("changes") or []); imp = impact(); n = len(changes); new = []
    for f in G.followup_changes(old, doc, imp):
        n += 1; new.append(dict(f, id=f"AC-{n:03d}", cause=f"{f['cause']}; {cause}", at=now(), picked_up=False))
    doc.update(followups=G.followups(doc, imp), changes=changes + new, status="applied", applied_at=now()); save_json(P(G.ARCH_PATH), doc)
    return new


def summary(doc):
    by = {}
    for d in doc["decisions"]: by[d["decision"]] = by.get(d["decision"], 0) + 1
    st = {}
    for d in doc["decisions"]: st[d["status"]] = st.get(d["status"], 0) + 1
    return f"{len(doc['decisions'])} decision(s) ({', '.join(f'{k} {v}' for k, v in by.items()) or '-'}); status {', '.join(f'{k} {v}' for k, v in st.items()) or '-'}"


def cmd_apply(cfg):
    if not plan().get("batches"): sys.exit(f"REFUSED: no architect batch - `{CLI} architect plan` first (only after a wave with gaps)")
    doc, err = recompute(cfg, state().get("overrides") or [])
    if err: print(f"REFUSED ({len(err)} problem(s); state/architect.json unchanged):"); [print("  -", e) for e in err]; sys.exit(1)
    new = write(cfg, doc, "applied " + ", ".join(f"{b['scope']} round {b['gauntlet']['rounds']}" for b in doc["batches"]))
    print(f"{rel(P(G.ARCH_PATH))}: applied automatically - {summary(doc)}" + (f"; {len(new)} follow-up work package change(s) for the next wave" if new else ""))
    q = [b["scope"] for b in doc["batches"] if any(d["batch"] == b["scope"] and d.get("assumption") for d in doc["decisions"])]
    if q: print(f"client assumptions: `{CLI} questions import <batch>` for {', '.join(q)} (once per batch; the A-nn land on the Annahmen sheet)")
    print("NEXT: " + (step_line(cfg) or "; ".join(also_lines(cfg)) or "-"))


def override_error(cfg, gap, decision, to, reason, solution, assumption):
    """why an override cannot be recorded (None when it can) - the dashboard checks the same before it writes the inbox entry"""
    doc = state(); d = next((x for x in doc.get("decisions") or [] if x["id"] == gap), None)
    if not d: return f"{gap} is no decided gap of state/architect.json"
    if decision not in G.DECISIONS: return f"decision {decision} ({' | '.join(G.DECISIONS)})"
    to = to or (d["from_system"] if decision in ("overrule", "reduce-to-standard") else "")
    if not (reason or "").strip(): return "the reason is required (why the decision changes)"
    same = decision == d["decision"]
    x = dict(d, decision=decision, to=to, reasoning=reason, solution=solution or d["solution"], assumption=d.get("assumption", "") if same else "",
             assumption_question="x" if (assumption or "").strip() else (d.get("assumption_question", "") if same else ""))
    e = G.decision_errors(x, TM.system_model(cfg), G.landscape_ids(ROOT))
    if e: return e[0].split(": ", 1)[1]
    from lint_deliverable import code_terms
    bad = code_terms(" ".join(t for t in (solution, assumption) if t), [])[:1]
    if bad: return f"{bad[0][0]} '{bad[0][1]}' - customer language: what carries the work, never how in code"
    return None


def affects_of(doc, gap, decision, to):
    """the keys an override's client assumption affects: the receiving cell <row>@<to>; a reduction / overrule the gap's reporting work
    packages - the A-nn lands there only, never on the row's other systems or options"""
    d = next((x for x in doc.get("decisions") or [] if x["id"] == gap), None) or {}; row = gap.split("@")[0]
    if decision in ("overrule", "reduce-to-standard"): return ",".join(d.get("packages") or []) or f"{row}@{d.get('from_system') or gap.split('@', 1)[-1]}"
    return f"{row}@{to}"


def cmd_override(cfg, a):
    if len(a) < 3: sys.exit(__doc__)
    gap, decision = a[1], a[2]; to, reason, solution, assumption = opt(a, "--to"), opt(a, "--reason"), opt(a, "--solution"), opt(a, "--assumption")
    e = override_error(cfg, gap, decision, to, reason, solution, assumption)
    if e: sys.exit(f"REFUSED: {e}")
    doc0 = state(); ovs = list(doc0.get("overrides") or []); oid = f"AO-{len(ovs) + 1:03d}"; qid = ""
    if assumption.strip():
        qid = f"Q-{G.ARCH_SCOPE}-{oid}"; q = os.path.join(TOOLS, "questions.py")
        for args in (["add", G.ARCH_SCOPE, "client", assumption.strip(), "--id", qid, "--affects", affects_of(doc0, gap, decision, to), "--why", reason.strip()], ["assumption", qid, "--text", assumption.strip()]):
            r = subprocess.run([sys.executable, q, *args], cwd=ROOT, capture_output=True, text=True)
            if r.returncode: sys.exit(f"REFUSED: the client assumption was not registered: {(r.stdout + r.stderr).strip()[-300:]}")
    ovs.append({"id": oid, "gap": gap, "decision": decision, "to": to.strip(), "reason": reason.strip(), "solution": solution.strip(), "assumption_question": qid, "by": opt(a, "--by", "lead"), "at": now(),
                **({"entry": opt(a, "--entry")} if opt(a, "--entry") else {})})
    doc, err = recompute(cfg, ovs, fresh=False)
    if err: print(f"REFUSED ({len(err)} problem(s); state/architect.json unchanged):"); [print("  -", x) for x in err]; sys.exit(1)
    new = write(cfg, doc, f"override {oid}")
    print(f"{oid}: {gap} -> {decision}" + (f" {to}" if to else "") + f" recorded - {summary(doc)}" + (f"; follow-ups for the next wave: {', '.join(c['work_package'] + ' ' + c['change'] for c in new)}" if new else "") + (f"; client assumption {qid}" if qid else ""))
    return oid, new


def cmd_show(cfg, a):
    doc = state()
    if not doc: print(f"(no state/architect.json - {step_line(cfg) or 'no gap decided yet'})"); return
    r = opt(a, "--row"); print(f"architect decisions ({doc.get('status')}, {doc.get('applied_at')}): {summary(doc)}")
    for d in doc["decisions"]:
        if r and d["row"] != r: continue
        print(f"  {d['id']:22s} {d['decision']:18s} -> {d['to']:12s} {d['status']:10s} {d['batch']}" + (" FINAL" if d.get("final") else "") + f"  {(d.get('solution') or d.get('reasoning') or '')[:80]}")


def cmd_changes(cfg, a):
    ch = state().get("changes") or []; show = ch if "--all" in a else [c for c in ch if not c.get("picked_up")]
    if "--json" in a: print(json.dumps({"changes": show, "net": TM.net_changes(ch)}, ensure_ascii=False, indent=1)); return
    if not show: print("(no open follow-up work package)"); return
    for c in show: print(f"  {c['id']} {c['work_package']:24s} {c['change']:10s} {c['cause']} ({c['at']})" + (" [picked up]" if c.get("picked_up") else "") + f"\n      {c.get('brief_note', '')[:140]}")
    print("net per work package: " + ", ".join(f"{k} {v}" for k, v in TM.net_changes(ch).items()))


# ------------------------------------------------------------------ dbcx status next (method.json steps)
def step_line(cfg):
    """the architect step's next action beside the waves, None when nothing is to do (no `systems`, no wave planned, no open gap)"""
    if not TM.scope_step(cfg) or not os.path.exists(SCOPES_PATH): return None
    pl = plan(); last = (pl.get("batches") or [None])[-1]
    if last and (not os.path.exists(js_of(last["scope"])) or stale(last["scope"])):
        s = last["scope"]; return f"architect agent for {s} ({len(last['gaps'])} gap(s)): `{CLI} render brief architect {s} --out` -> spawn -> `{CLI} md_to_json architect {rel(md_of(s))}`; then `{CLI} architect apply`"
    done = {b["scope"]: b.get("sha256") for b in state().get("batches") or []}
    if any(done.get(b["scope"]) != sha(js_of(b["scope"])) for b in pl.get("batches") or []): return f"`{CLI} architect apply` (the batch decisions -> state/architect.json, applied automatically)"
    todo, _ = G.open_gaps(cfg, state(), pl, ROOT)
    if todo: return f"{len(todo)} gap(s) of a closed wave ({', '.join(g['id'] for g in todo[:6])}{' ...' if len(todo) > 6 else ''}): `{CLI} architect plan`, then the architect agent decides them in one batch"
    return None


def crit(cfg, scope):
    """the critics of an architect batch for the ALSO line (client + the standard critics of the receiving systems)"""
    try:
        from common import scope_critics
        return "|".join(scope_critics(scope, cfg)) if cfg.get("_method") else "client|standard"
    except Exception: return "client|standard"


def also_lines(cfg):
    """beside the later phases: the gauntlet of every batch (holds nothing), a result not applied yet, the follow-ups waiting for a wave"""
    if not TM.scope_step(cfg) or step_line(cfg): return []
    doc = state(); out = []
    for b in doc.get("batches") or []:
        s = b["scope"]; g = gauntlet_state(s); n = g["rounds"]
        if g != b.get("gauntlet"): out.append(f"`{CLI} architect apply` - the gauntlet of {s} has a new result (round {n}): a failed claim marks its decision disputed")
        if g["status"] == "rework": out.append(f"architect {s} rework round {n + 1} (holds nothing): `{CLI} render brief architect {s} --round {n + 1} --addendum <file> --out` -> `{CLI} md_to_json architect {rel(md_of(s))}` -> `{CLI} architect apply`")
        elif g["status"] not in ("passed", "final", "failed-gauntlet"): out.append(f"architect claims of {s}, gauntlet round {n + 1} (holds nothing): `{CLI} extract_claims {s}` -> `{CLI} render brief critic <{crit(cfg, s)}> {s} {n + 1} --out` -> `{CLI} score_aggregate {s} {n + 1}` -> `{CLI} architect apply`")
    net = TM.net_changes(doc.get("changes") or [])
    if net: out.append(f"{len(net)} follow-up work package(s) of the architect wait for the next wave ({', '.join(f'{k} {v}' for k, v in list(net.items())[:6])}{' ...' if len(net) > 6 else ''}; `{CLI} architect changes`; "
                       f"`{CLI} discover --pickup` puts them into follow-up chunks of the first wave that has not started - external cells become input cells, no chunk - then `{CLI} plan_waves`)")
    return out


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cfg = project()
    if a[0] in ("plan", "apply", "override") and not TM.scope_step(cfg): sys.exit("REFUSED: the architect step runs with run.json `systems` only - this run has none (no gaps, no architect)")
    if a[0] == "plan": cmd_plan(cfg, a)
    elif a[0] == "apply": cmd_apply(cfg)
    elif a[0] == "override": cmd_override(cfg, a)
    elif a[0] == "show": cmd_show(cfg, a)
    elif a[0] == "changes": cmd_changes(cfg, a)
    else: sys.exit(__doc__)


if __name__ == "__main__":
    main()
