#!/usr/bin/env python3
"""Deterministic progress picture of a run -> state/PROGRESS.json (+ a short console summary). No LLM.
Usage: dbcx progress [--json]
Per deliverable a completion percentage with the FORMULA shown, derived from the method's phases:
  gauntlet phase (one scope)  = 0.30 analysis drafted + 0.60 gauntlet passed + 0.10 workbook built
  scopes phase (many scopes)  = 0.90 * share of analysed scopes final (size-weighted from state/scopes.json) + 0.10 workbook built
  several phases, one deliverable (waves + a consolidation, e.g. tech-fit-estimation D1) = mean of the phases' shares above
                                without the workbook + 0.10 workbook built (a later phase adds to the earlier ones, never replaces them)
  gate                        = passed ? 100 : (finished rounds + share of reviews in for the running round) / max_gate_rounds * 60
                                + (share of key-question and verifier scores >= threshold in the last finished round) * 40, capped at 99
  overall                     = mean of the enabled deliverables (gate excluded)
Also written: `analysts` - one row per gauntlet scope (wave, state, rounds with per-critic averages, false verdicts, claims <= 2, claims, running agent)
for the dashboard (`dbcx dashboard`), which re-reads this file on a timer. Called with --quiet by score_aggregate, the SubagentStop hook and status changes.
The progress-reporter agent turns the picture into docs/PROGRESS_REPORT.md (narrative, on request / checkpoint); `dbcx build_excel --all --interim` builds checkpoint workbooks.
"""
import os, sys, json, glob, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, STATUS_PATH, SCOPES_PATH, WAVES_PATH, project, method, load_json, scope_info, load_questions, replace_file

def pct(x): return int(round(100 * max(0.0, min(1.0, x))))
FINAL = ("final", "passed", "passed-rework-ordered")
def ts(path): return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(path))) if path and os.path.exists(path) else None

def rounds_of(scope):
    """Per aggregated round: pass, averages, false verdicts, claims scored <= 2, issue count, amendments - from round<n>-result.json."""
    gd = os.path.join(ROOT, "analysis", "gauntlet", scope); out = []
    if not os.path.isdir(gd): return out, 0, None
    for f in sorted(glob.glob(os.path.join(gd, "round*-result.json")), key=lambda x: int(re.search(r"round(\d+)", x).group(1))):
        r = load_json(f, {}); cr = r.get("critics", {})
        out.append({"round": r.get("round"), "passed": bool(r.get("passed")), "scores": {c: v.get("avg") for c, v in cr.items()}, "false_verdicts": sum(len(v.get("false_verdicts", []) or []) for v in cr.values()),
                    "low": sum(int(v.get("false_claims", 0) or 0) for v in cr.values()), "issues": int(r.get("issue_count", 0) or 0), "amended": bool(r.get("amendments")), "at": r.get("aggregated_at")})
    reg = load_json(os.path.join(gd, "claims.json"), {"claims": []}) if os.path.exists(os.path.join(gd, "claims.json")) else {"claims": []}
    return out, len(reg.get("claims", [])), gd

def analysts_view(st, m, p):
    """One row per gauntlet scope for the dashboard: inventory (wave 0), analysed scopes (their wave), consolidations (wave 99)."""
    sc = p["scoring"]; maxr = sc["max_gauntlet_rounds"]; maxl = sc.get("max_gauntlet_rounds_light", maxr)
    waves = load_json(WAVES_PATH, {}) if os.path.exists(WAVES_PATH) else {}
    light = {mem.get("name") for w in waves.get("waves", []) for mem in w.get("members", []) if mem.get("light_pass")}
    inflight = {e.get("agent") for e in st.get("in_flight", []) or [] if not e.get("delivered")}
    rows = []
    def add(scope, wave, state, group):
        if any(r["scope"] == scope for r in rows): return   # a scope has exactly one row: a phase scope wrongly also registered in scopes[] must not appear twice
        js, md, kind, role, agent = scope_info(scope, m); rounds, claims, gd = rounds_of(scope); lt = scope in light
        latest = max([x for x in [ts(md), ts(os.path.join(gd, f"round{rounds[-1]['round']}-result.json")) if rounds and gd else None] if x] or [None])
        rows.append({"scope": scope, "wave": wave, "group": group, "state": state or "open", "light": lt, "max_rounds": maxl if lt else maxr, "claims": claims, "agent": agent if agent in inflight else None, "rounds": rounds, "updated_at": latest, "drafted": os.path.exists(md)})
    for ph in m.get("phases", []):
        if ph.get("type") != "gauntlet" or not ph.get("scope"): continue
        e = st.get("phases", {}).get(ph["id"], {})
        if not e.get("enabled", True): continue
        inv = m.get("inventory") or {}
        # Phases and scopes speak different vocabularies: a finished PHASE says "done", a finished SCOPE says
        # "final". The rows are read with the scope vocabulary, so translate here - otherwise a passed inventory
        # is classified as still running for the rest of the run.
        state = e.get("status", "open")
        if state == "done": state = "final" if e.get("passed", True) else "failed-gauntlet"
        add(ph["scope"], 0 if ph["scope"] == inv.get("scope") else 99, state, "inventory" if ph["scope"] == inv.get("scope") else "consolidation")
    for name, v in sorted(st.get("scopes", {}).items(), key=lambda kv: (kv[1].get("wave") or 999, kv[0])):
        if v.get("status") == "skipped": continue
        add(name, v.get("wave") or 1, v.get("status", "open"), "scope")
    return rows

def gate_share(e, p):
    """passed = 1; else (finished rounds + reviews in / reviews of the running round) / max * 0.6 + share of the last finished round's scores >= threshold * 0.4, at most 0.99.
    The reviews of a round: hygiene, every persona, the verifier; a round runs once its hygiene report or a gate brief exists."""
    import gate as G
    if e.get("passed"): return 1.0
    sc = p["scoring"]; maxg = G.max_rounds(p); th = sc.get("pass_threshold", 8); gd = os.path.join(ROOT, "analysis", "gate")
    done = sorted(int(re.search(r"round(\d+)-", f).group(1)) for f in glob.glob(os.path.join(gd, "round*-result.json")))
    n = (done[-1] if done else 0) + 1; run = 0.0
    if os.path.exists(os.path.join(gd, f"round{n}-hygiene.json")) or n in G.started_rounds():
        nodes = ["hygiene"] + list(sc.get("gate_personas") or []) + ["verifier"]
        run = sum(1 for x in nodes if os.path.exists(os.path.join(gd, f"round{n}-{x}.json"))) / len(nodes)
    scores = load_json(os.path.join(gd, f"round{done[-1]}-result.json"), {}).get("scores", []) if done else []
    ok = sum(1 for x in scores if x["score"] >= th) / len(scores) if scores else 0
    return min(0.99, (len(done) + run) / maxg * 0.6 + ok * 0.4)

def main(write=True):
    p = project(); m = method(); st = load_json(STATUS_PATH, None)
    if not st:
        if not write: return None
        sys.exit("no state/STATUS.json - run dbcx status init")
    ph = st["phases"]; scopes = st.get("scopes", {}); sj = load_json(SCOPES_PATH, {"scopes": {}})
    prev = load_json("state/PROGRESS.json", {}) or {}
    deliv = {k: os.path.exists(os.path.join(ROOT, "deliverables", v["file"])) for k, v in p.get("deliverables", {}).items() if isinstance(v, dict) and v.get("enabled") and v.get("file")}
    by_state = {}
    for u, v in scopes.items(): by_state[v.get("status", "open")] = by_state.get(v.get("status", "open"), 0) + 1
    analysed = {u: v for u, v in scopes.items() if v.get("status") != "skipped"}
    def size(u): return max(1, int((sj["scopes"].get(u) or {}).get("size") or 1))
    tot = sum(size(u) for u in analysed) or 1; fin = sum(size(u) for u, v in analysed.items() if v.get("status") in FINAL)
    drafted = sum(1 for u in analysed if os.path.exists(scope_info(u, m)[1]))
    parts = {}; formulas = {}; work = {}; gate_pf = None   # work: deliverable -> [(share without the workbook, formula part, phase label)] of every phase feeding it
    for phase in m["phases"]:
        e = ph.get(phase["id"], {})
        if not e.get("enabled", True): continue
        d = phase.get("deliverable")
        if phase["type"] == "gauntlet" and d:
            md = scope_info(phase["scope"], m)[1]
            work.setdefault(d, []).append((0.30 * os.path.exists(md) + 0.60 * bool(e.get("passed")), "0.30 analysis drafted + 0.60 gauntlet passed", phase["scope"]))
        elif phase["type"] == "scopes" and d:
            work.setdefault(d, []).append((0.9 * (fin / tot if analysed else 0), "0.90 * size-weighted share of analysed scopes final", "scopes"))
        elif phase["type"] == "gate":
            gate_pf = (pct(gate_share(e, p)), "passed ? 100 : (finished rounds + share of reviews in for the running round) / max rounds * 60 + share of key-question and verifier scores >= threshold in the last finished round * 40 (capped at 99)")
    for d, ws in work.items():   # one phase: its formula; several (waves + consolidation of one deliverable): their mean, so the consolidation adds to the waves
        parts[d] = pct(sum(w[0] for w in ws) / len(ws) + 0.10 * deliv.get(d, False))
        formulas[d] = (ws[0][1] if len(ws) == 1 else "mean of its phases (" + "; ".join(f"{w[2]}: {w[1]}" for w in ws) + ")") + " + 0.10 workbook built"
    if gate_pf: parts["final_gate"], formulas["final_gate"] = gate_pf   # after the deliverables, as before
    for d, v in p.get("deliverables", {}).items():
        if isinstance(v, dict) and v.get("enabled") and d not in parts and d in m.get("deliverable_sources", {}):
            srcs = [f for pat in m["deliverable_sources"][d] for f in glob.glob(os.path.join(ROOT, pat))]
            parts[d] = pct(0.5 * bool(srcs) + 0.5 * deliv.get(d, False)); formulas[d] = "0.5 source present + 0.5 workbook built"
    claims_total = 0; claims_passed = 0; rounds_run = 0; scopes_passed = []
    for gd in sorted(glob.glob(os.path.join(ROOT, "analysis", "gauntlet", "*"))):
        scope = os.path.basename(gd); results = sorted(glob.glob(os.path.join(gd, "round*-result.json"))); rounds_run += len(results)
        if not results: continue
        last = load_json(results[-1], {}); reg = load_json(os.path.join(gd, "claims.json"), {"claims": []}); claims_total += len(reg["claims"])
        if last.get("passed"): claims_passed += len(reg["claims"]); scopes_passed.append(scope)
    prev_passed = set(prev.get("scopes_passed", []))
    dl_parts = {k: v for k, v in parts.items() if k != "final_gate"}
    overall = int(round(sum(dl_parts.values()) / max(1, len(dl_parts))))
    notes_owed = 0
    for gd in glob.glob(os.path.join(ROOT, "analysis", "gauntlet", "*")):
        results = sorted(glob.glob(os.path.join(gd, "round*-result.json")))
        if results: notes_owed += len(load_json(results[-1], {}).get("notes_on_passing_claims", []))
    open_issues = [i for i in st.get("open_issues", []) if i.get("status") == "open"]
    inflight = [e for e in st.get("in_flight", []) if not e.get("delivered")]
    fb = [x for x in st.get("feedback", []) if not x.get("processed")]
    _q = [q for q in load_questions() if q.get("status") == "open"]; qs = len(_q); cq = sum(1 for q in _q if q.get("to", "").lower() == "client")
    timeline = [{"t": h["t"], "msg": h["msg"][:140]} for h in st.get("history", []) if re.search(r"PASS|FAIL|spawned|delivered|built|phase|wave|import|export", h["msg"], re.I)][-25:]
    analysts = analysts_view(st, m, p)
    def cls(x): return "done" if x["state"] in FINAL else "failed" if x["state"] == "failed-gauntlet" else "planned" if x["state"] == "open" else "running"
    counts = {k: sum(1 for x in analysts if cls(x) == k) for k in ("done", "running", "planned", "failed")}
    qs_all = load_questions()
    out = {"computed_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "run": st.get("run"), "method": st.get("method"), "client": p.get("engagement", {}).get("client", ""), "pass_threshold": st.get("pass_threshold", p["scoring"]["pass_threshold"]), "overall_pct": overall, "per_deliverable_pct": parts,
           "analysts": analysts, "counts": counts, "questions_open": sum(1 for q in qs_all if q.get("status") == "open"), "questions_total": len(qs_all), "formulas": dict(formulas, overall="mean of the deliverable percentages (gate excluded)"),
           "scopes": {"total": len(scopes), "analysed": len(analysed), "by_state": by_state, "drafted": drafted, "final_size_share": round(fin / tot, 3) if analysed else 0, "final": sorted(u for u, v in analysed.items() if v.get("status") in FINAL), "open": sorted(u for u, v in analysed.items() if v.get("status") not in FINAL + ("failed-gauntlet",))},
           "claims": {"total_in_registers": claims_total, "in_passed_scopes": claims_passed}, "gauntlet_rounds_run": rounds_run, "scopes_passed": sorted(scopes_passed), "scopes_passed_since_last_progress": sorted(set(scopes_passed) - prev_passed),
           "phases": {k: v.get("status") for k, v in ph.items()}, "deliverables_built": deliv, "owed": {"post_pass_notes": notes_owed, "open_issues": len(open_issues), "in_flight_agents": [e.get("agent") for e in inflight], "open_questions": qs, "open_client_questions": cq, "unprocessed_feedback": len(fb)},
           "assumptions": len(st.get("assumptions", [])), "timeline": timeline, "previous_progress_at": prev.get("computed_at")}
    if not write: return out
    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True); tmp = os.path.join(ROOT, "state", "PROGRESS.json.tmp"); json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); replace_file(tmp, os.path.join(ROOT, "state", "PROGRESS.json"))
    if "--json" in sys.argv: print(json.dumps(out, indent=1, ensure_ascii=False)); return
    if "--quiet" in sys.argv: return
    print(f"PROGRESS {overall} % overall - " + ", ".join(f"{k} {v} %" for k, v in parts.items()))
    print(f"  scopes: {len(out['scopes']['final'])}/{len(analysed)} final ({int(out['scopes']['final_size_share'] * 100)} % of size), states {by_state}; claims in passed scopes {claims_passed}/{claims_total}; rounds run {rounds_run}")
    print(f"  owed: {notes_owed} post-pass notes, {len(open_issues)} open issues, {qs} open questions ({cq} to the client), {len(inflight)} in-flight agents, {len(fb)} unprocessed feedback; passed since last progress: {out['scopes_passed_since_last_progress'] or '-'}")
    print(f"  analysts: {counts['done']} done, {counts['running']} running, {counts['planned']} planned, {counts['failed']} failed of {len(analysts)}")
    print("  -> state/PROGRESS.json (the dashboard re-reads it; narrative: `dbcx render brief progress --out` -> progress-reporter; checkpoint workbooks: dbcx build_excel --all --interim)")

if __name__ == "__main__":
    main()
