#!/usr/bin/env python3
"""The run dashboard: a local HTTP server (127.0.0.1, token in the URL) that shows the run's progress live and takes the lead's answers,
hints, disputes and the pause / checkpoint commands into the inbox. Read-only towards the run except state/INBOX.jsonl (append) and
state/CONTROL.json (pause / checkpoint flags). Started by the SessionStart hook; the browser opens on session start.

Usage: dbcx dashboard serve [--port N] [--no-open]   start the server for this run in the background (idempotent) and print the URL
       dbcx dashboard open                           open the dashboard in the default browser
       dbcx dashboard status | url | stop           is it running / the URL / stop it
       dbcx dashboard state [--scope <name>]        print the composed JSON the page reads (smoke tests, debugging)
Internal: dbcx dashboard --foreground --port N       the server process itself
Data: state/PROGRESS.json shape computed fresh per request (never written here), state/QUESTIONS.json (released questions only - 0.11
      human_input.release batched), state/RULINGS.json (the rulings sheet as cards of kind ruling), state/CONTROL.json, state/INBOX.jsonl,
      state/STATUS.json (history tail, in-flight agents, assumptions), state/ACTIVITY.jsonl (live agent activity, stall flag), docs/PROGRESS_REPORT.md (narrative), analysis/gauntlet/<scope>/* (claims, scores),
      analysis/gate/round<n>-hygiene.json, -<persona>.json, -verifier.json, -result.json, -fixplan.json + STATUS phases.<gate>.question_changes /
      decisions + INBOX gate_question_feedback (the final gate section, one lane per round); a method's panels (methods/<m>/panels.py, 0.12 -
      tech-fit-estimation: "Impact per system" from state/impact.json) with their unprocessed panel_edit entries (an optional cell edit the lead sends).
"""
import os, re, sys, glob, json, time, secrets, socket, subprocess, threading, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, TOOLS, ENGINE, CLI, STATUS_PATH, INBOX_PATH, CONTROL_PATH, DASHBOARD_PATH, load_json, save_json, load_questions, load_control, load_inbox, project, method, scope_info, scope_critics, role_of_agent
from runtime import HARNESS, resolve_model
import activity

HTML = os.path.join(ENGINE, "dashboard", "dashboard.html")
LOCK = threading.Lock()
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def cfg(): return load_json(DASHBOARD_PATH, {}) if os.path.exists(DASHBOARD_PATH) else {}
def alive(pid):
    try: os.kill(int(pid), 0); return True
    except Exception: return False
def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3); return s.connect_ex(("127.0.0.1", int(port))) == 0
def free_port(start=8765):
    for p in range(start, start + 50):
        if not port_open(p): return p
    return start

# ------------------------------------------------------------------ composition
def progress_now():
    import progress
    try: return progress.main(write=False)
    except SystemExit as e: return {"error": str(e)}
    except Exception as e: return {"error": f"progress: {e}"}

def narrative():
    fp = P("docs", "PROGRESS_REPORT.md")
    if not os.path.exists(fp): return {"as_of": None, "md": ""}
    return {"as_of": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(fp))), "md": open(fp, encoding="utf-8").read()[:120000]}

# ---- final gate section (gate board): one lane per round, nodes hygiene / personas / verifier, the round's own questions, issues and fix plan
SEV = ("blocker", "major", "minor")
LIFE = re.compile(r"^\s*(Nicht behoben|Not fixed|Teilweise behoben|Partly fixed|Partially fixed)\s*[:–-]\s*", re.I)


def _gload(p):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return None


def life_of(text):
    """(new | again | partly, text without the persona's own prefix)"""
    m = LIFE.match(text or "")
    return ("again" if m.group(1).lower().startswith(("nicht", "not")) else "partly", text[m.end():]) if m else ("new", text or "")


def persona_name(p, persona):
    """the persona file's `name:` (knowledge/personas or a configured directory), else the id"""
    import render
    fp = render.persona_file(p, persona); fp = fp if os.path.isabs(fp) else P(fp)
    try: m = re.search(r"^name:\s*(.+)$", open(fp, encoding="utf-8").read(4000), re.M)
    except Exception: m = None
    return m.group(1).strip() if m else persona.replace("_", " ").capitalize()


def gate_state(p, agents):
    """state()["gate"]; `agents` = board()'s undelivered in-flight agents with their activity"""
    import gate as G, lint_deliverable as LD
    sc = p["scoring"]; personas = sc.get("gate_personas") or []; th = float(sc.get("pass_threshold", 8)); floor = sc.get("gate_question_floor", 7)
    gd = P("analysis", "gate"); by_file = {f: k for k, f in G.enabled(p).items()}
    dk = lambda x: by_file.get(os.path.basename(str(x or "")), (re.match(r"D\d+", str(x or "")) or [str(x or "")])[0])
    nums = {int(m.group(1)) for f in glob.glob(os.path.join(gd, "round*-*.json")) if (m := re.search(r"round(\d+)-", os.path.basename(f)))} | G.started_rounds()
    nums = sorted(n for n in nums if n > 0); current = nums[-1] if nums else None
    changes = G.question_changes(p); decs = G.decisions(p)
    ag = lambda name, n: next((a for a in agents if a.get("agent") == name and (a.get("round") or current) == n), None)
    agent_of = lambda a: {"agent": a["agent"], "activity": a.get("activity"), "since": a.get("activity_at") or a.get("spawned_at"), "stalled": bool(a.get("stalled"))} if a else None
    rounds = []; prev = {}
    for n in nums:
        res = _gload(os.path.join(gd, f"round{n}-result.json")); plan = _gload(os.path.join(gd, f"round{n}-fixplan.json")) or {}
        in_cluster = {i: c for c in plan.get("clusters", []) for i in c.get("issues", [])}
        h = _gload(os.path.join(gd, f"round{n}-hygiene.json"))
        if h:
            fs = h.get("findings", []) or []
            checks = [{"id": c, "label": LD.CHECK_DOC.get(c, (c, ""))[0], "doc": LD.CHECK_DOC.get(c, (c, ""))[1], "severity": LD.CHECKS.get(c, "error"), "count": k,
                       "warnings": k if LD.CHECKS.get(c) == "warning" else 0, "passed": LD.CHECKS.get(c) == "warning" or not k,
                       "findings": [{"file": x.get("file"), "where": x.get("where"), "text": x.get("text")} for x in fs if x.get("check") == c][:100]} for c, k in (h.get("counts") or {}).items()]
            nodes = [{"id": "hygiene", "kind": "hygiene", "status": "passed" if h.get("passed") else "failed", "errors": h.get("errors", 0), "warnings": h.get("warnings", 0), "checks": checks}]
        else: nodes = [{"id": "hygiene", "kind": "hygiene", "status": "queued", "errors": None, "warnings": None, "checks": []}]
        for per in personas:
            d = _gload(os.path.join(gd, f"round{n}-{per}.json")); a = ag(f"gate-{per}", n); kq = G.key_questions(p, per, n)
            got = {q.get("question_id"): q for q in (d or {}).get("questions", [])}; pv = prev.get(per) or {}
            qs = []
            for q in kq:
                x = got.get(q["id"]) or {}; s_ = x.get("score") if isinstance(x.get("score"), (int, float)) else None; ps = pv.get("scores", {}).get(q["id"])
                ch = next((c for c in reversed(changes) if c["persona"] == per and c["question_id"] == q["id"] and c["action"] == "reword" and c["from_round"] == n), None)
                qs.append({"id": q["id"], "text": q["text"], "score": s_, "delta": round(s_ - ps, 2) if s_ is not None and ps is not None else None, "answer": x.get("answer"), "rationale": x.get("rationale"), "where": x.get("where"),
                           "change": {"action": ch["action"], "why": ch.get("why"), "feedback_text": ch.get("feedback_text"), "prev_text": next((y["text"] for y in G.key_questions(p, per, n - 1) if y["id"] == q["id"]), None)} if ch else None})
            sc_ = [q["score"] for q in qs if q["score"] is not None]; mean = round(sum(sc_) / len(sc_), 2) if sc_ else None
            iss = []
            for i in (d or {}).get("issues", []) or []:
                life, text = life_of(i.get("issue")); c = in_cluster.get(f"{per}:{i.get('id')}") or {}
                iss.append({"id": i.get("id"), "severity": i.get("severity"), "q": i.get("question_id"), "where": f"{dk(i.get('deliverable'))} {i.get('location', '')}".strip(), "text": text, "proposed": i.get("proposed_change"),
                            "life": life, "cluster": c.get("id"), "decision": c.get("decision")})
            status = ("passed" if mean is not None and mean >= th and min(sc_) >= floor and not any(i["severity"] == "blocker" for i in iss) else "failed") if d else "reviewing" if a else "queued"
            nodes.append({"id": per, "kind": "persona", "status": status, "mean": mean, "delta": round(mean - pv["mean"], 2) if mean is not None and pv.get("mean") is not None else None,
                          "board": (d.get("board_test") or {}).get("forward_unchanged") if d else None, "missing": (d or {}).get("missing") or [], "questions": qs, "issues": iss, "agent": agent_of(a)})
            if d: prev[per] = {"mean": mean, "scores": {q["id"]: q["score"] for q in qs if q["score"] is not None}}
        v = _gload(os.path.join(gd, f"round{n}-verifier.json")); a = ag("gate-verifier", n)
        vs = {dk(x.get("deliverable")): x.get("score") for x in (v or {}).get("scores", [])}
        nodes.append({"id": "verifier", "kind": "verifier", "status": ("passed" if vs and min(vs.values()) >= th else "failed") if v else "reviewing" if a else "queued", "scores": vs,
                      "samples": len((v or {}).get("samples", [])), "rationale": {dk(x.get("deliverable")): x.get("rationale") for x in (v or {}).get("scores", [])},
                      "defects": [{"id": x.get("id"), "severity": x.get("severity"), "where": f"{dk(x.get('deliverable'))} {x.get('location', '')}".strip(), "text": x.get("defect")} for x in (v or {}).get("defects", [])], "agent": agent_of(a)})
        rounds.append({"round": n, "done": res is not None,
                       "result": {"passed": bool(res.get("passed")), "criteria": res.get("criteria") or {}, "persona_means": res.get("persona_means") or {}, "min_question": res.get("min_question"),
                                  "blockers": len(res.get("blockers") or []), "majors_open": len(res.get("majors_without_decision") or []), "clusters": res.get("clusters")} if res else None,
                       "nodes": nodes,
                       "fixplan": {"clusters": [{"id": c.get("id"), "severity": c.get("severity"), "kind": c.get("kind"), "raised_by": c.get("raised_by") or [], "questions": c.get("questions") or [], "mechanism": c.get("mechanism"),
                                                 "title": life_of(c.get("title"))[1], "proposed": " / ".join(c.get("proposed_changes") or []), "unchanged_since": c.get("unchanged_since"), "decision": c.get("decision")} for c in plan.get("clusters", [])]} if plan else None})
    last = rounds[-1] if rounds else None; maxr = G.max_rounds(p); ed = next((a for a in agents if a.get("agent") == "deliverable-editor"), None)
    if not last: phase = "fixing" if ed else "waiting"
    elif last["done"]: phase = "passed" if last["result"]["passed"] else "exhausted" if sum(1 for r in rounds if r["done"]) >= maxr else "fixing"
    else:
        st_ = [x["status"] for x in last["nodes"] if x["kind"] != "hygiene"]
        phase = "verdict" if all(x in ("passed", "failed") for x in st_) else "reviewing" if any(x != "queued" for x in st_) else "fixing" if ed else "waiting"
    fb = [{"client_id": e.get("client_id"), "persona": e.get("persona"), "question_id": e.get("question_id"), "round": e.get("round"), "intent": e.get("intent"), "text": e.get("text"), "at": e.get("at"),
           "processed": bool(e.get("processed")), "outcome": e.get("outcome"),
           "change": next(({k: c.get(k) for k in ("action", "text", "why", "from_round")} for c in changes if c.get("feedback") == e.get("client_id")), None)} for e in load_inbox() if e.get("kind") == "gate_question_feedback"]
    return {"rule": {"threshold": th, "floor": floor}, "max_rounds": maxr, "personas": list(personas), "names": {x: persona_name(p, x) for x in personas}, "current": current, "phase": phase,
            "editor": {"agent": ed["agent"], "activity": ed.get("activity"), "since": ed.get("activity_at") or ed.get("spawned_at")} if ed else None, "feedback": fb,
            "changes": [{k: c.get(k) for k in ("persona", "question_id", "action", "text", "why", "from_round", "at")} for c in changes], "rounds": rounds}


def gate_panel(p, agents=()):
    """state()["gate"]: never raises - a broken or missing gate file shows as an empty section, not a broken dashboard"""
    try: return gate_state(p, list(agents))
    except Exception as e:
        sc = p.get("scoring", {})
        return {"rule": {"threshold": float(sc.get("pass_threshold", 8)), "floor": sc.get("gate_question_floor", 7)}, "max_rounds": int(sc.get("max_gate_rounds", 3)), "personas": list(sc.get("gate_personas") or []), "names": {},
                "current": None, "phase": "waiting", "editor": None, "feedback": [], "changes": [], "rounds": [], "error": f"{type(e).__name__}: {e}"}

def knowledge_panel():
    """state()["knowledge"]: the run knowledge base read-only, active entries grouped by topic (kb.py's order and definition of active); never raises"""
    try:
        import kb as KB
        k = KB.load(); es = k.get("entries", []); topics = k.get("topics") or {}; act = KB.active(k)
        return {"total": len(act), "candidates_open": sum(1 for c in k.get("candidates", []) if c.get("status") == "open"),
                "topics": [{"name": t, "summary": (topics.get(t) or {}).get("summary", ""), "active": sum(1 for e in act if e["topic"] == t), "superseded": sum(1 for e in es if e["topic"] == t and e.get("status") == "superseded"),
                            "entries": [{"id": e["id"], "type": e.get("type"), "weight": e.get("weight"), "by": (e.get("source") or {}).get("by"), "applies_to": e.get("applies_to") or [], "core": bool(e.get("core")), "text": e.get("text", ""),
                                         "source": {"kind": (e.get("source") or {}).get("kind"), "ref": (e.get("source") or {}).get("ref")}} for e in act if e["topic"] == t]}
                           for t in dict.fromkeys(e["topic"] for e in act)]}
    except Exception as e:
        return {"total": 0, "candidates_open": 0, "topics": [], "error": f"{type(e).__name__}: {e}"}

# ---- method panels: a method's own view of run state (tech-fit-estimation: "Impact per system"), with optional cell edits
def method_panels(p):
    """state()["panels"]: methods/<m>/panels.py panels(cfg) -> [{id, title, subtitle, status {label, tone}, columns [{id, label, note}], rows [{id,
    title, group, note, cells [{column, on, text, source, status, reason, claims}]}], edit {actions, ...}, legend, changes}] - read-only towards the
    run; the engine adds `pending` (the panel's unprocessed panel_edit inbox entries). [] without the hook; never raises"""
    try:
        import common as C
        mod = C.load_method_module("panels")
        if not (mod and hasattr(mod, "panels")): return []
        out = mod.panels(p) or []; ib = [e for e in load_inbox() if e.get("kind") == "panel_edit" and not e.get("processed")]
        for x in out: x["pending"] = [{k: e.get(k) for k in ("client_id", "row", "column", "action", "text", "reason", "at")} for e in ib if e.get("panel") == x.get("id")]
        return out
    except Exception as e:
        return [{"id": "_error", "title": "Method view", "error": f"{type(e).__name__}: {e}", "columns": [], "rows": [], "pending": []}]

# ---- run board: stage column per scope row, agents on their scopes, deliverable strips - composed read-only from existing run state
def _mtime(rel):
    fp = P(rel); return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(fp))) if rel and os.path.exists(fp) else None

STAGE = {"open": "queued", "analysing": "analysing", "rework": "analysing", "passed-rework-ordered": "analysing", "gauntlet": "critique", "failed-gauntlet": "critique", "passed": "passed"}
def board(pg, p, st):
    """adds stage / failed / rework / cur / partial / feeds to every pg["analysts"] row and returns {agents, deliverables}; never raises.
    A final row sits in Consolidated once its content is merged (a consolidation itself, every consolidation final, or every workbook it feeds built),
    else in Passed. The agents are the undelivered in_flight entries with their last activity (state/ACTIVITY.jsonl), the last write of their
    output files and the stalled flag (activity.stall_minutes without either)."""
    try:
        m = method(); rows = pg.get("analysts", []); built = pg.get("deliverables_built") or {}
        scopes_d = [ph["deliverable"] for ph in m.get("phases", []) if ph.get("type") == "scopes" and ph.get("deliverable")]
        own = {ph["scope"]: ph["deliverable"] for ph in m.get("phases", []) if ph.get("type") == "gauntlet" and ph.get("scope") and ph.get("deliverable")}
        cons = [a for a in rows if a["group"] == "consolidation"]; cons_final = bool(cons) and all(a["state"] in ("final", "passed") for a in cons)   # a passed consolidation is merged (tech-fit keeps it at passed)
        for a in rows:
            s = a["state"]; n = len(a["rounds"])
            a["feeds"] = ([own[a["scope"]]] if a["scope"] in own else []) if a["group"] != "scope" else scopes_d + [own[c["scope"]] for c in cons if c["scope"] in own]
            merged = a["group"] == "consolidation" or cons_final or (bool(a["feeds"]) and all(built.get(d) for d in a["feeds"]))
            a["stage"] = "consolidated" if a["group"] == "consolidation" and s in ("final", "passed") else STAGE.get(s) or ("consolidated" if s == "final" and merged else "passed" if s == "final" else "queued")
            a["failed"] = s == "failed-gauntlet"; a["rework"] = s in ("rework", "passed-rework-ordered") or (s == "analysing" and n > 0)
            a["cur"] = n + 1 if s in ("analysing", "rework", "gauntlet") else None; a["partial"] = None
            if s == "gauntlet":   # critic files of the round being scored, before score_aggregate wrote its result
                part = {}
                for c in scope_critics(a["scope"], p):
                    fp = P("analysis", "gauntlet", a["scope"], f"round{n + 1}-{c}.json")
                    sc = [x.get("score") for x in (load_json(fp, {}) if os.path.exists(fp) else {}).get("scores", []) if isinstance(x.get("score"), (int, float))]
                    if sc: part[c] = round(sum(sc) / len(sc), 2)
                a["partial"] = part or None
        own_agent = {scope_info(a["scope"], m)[4].lower(): a["scope"] for a in rows}; names = sorted((a["scope"] for a in rows), key=len, reverse=True)
        def scope_of(agent):
            low = (agent or "").lower()
            if low in own_agent: return own_agent[low]
            if low.startswith(("gate-", "deliverable-editor")): return "_gate"
            return next((s for s in names if low.endswith("-" + s.lower())), None)
        agents = []; fl = st.get("in_flight", []) or []
        lw = lambda e: max([t for t in map(_mtime, [x for x in e.get("output_files") or [] if x]) if t] or [None])
        act = activity.per_agent(ROOT, fl, activity.stall_minutes(p), last_write=lw, max_call_minutes=activity.max_call_minutes(p))   # live activity + stalled flag (state/ACTIVITY.jsonl)
        for e in fl:
            if e.get("delivered"): continue
            outs = [x for x in e.get("output_files") or [] if x]; ac = act.get(e.get("agent")) or {}
            agents.append({"agent": e.get("agent"), "role": e.get("role") or role_of_agent(e.get("agent")), "scope": scope_of(e.get("agent")), "round": e.get("round"), "spawned_at": e.get("spawned_at"),
                           "model": e.get("model"), "reasoning_effort": e.get("reasoning_effort"), "output_files": outs, "last_write_at": lw(e), "done_at": (e.get("done") or {}).get("at"),
                           "activity_at": ac.get("activity_at"), "activity": ac.get("activity"), "recent": ac.get("recent") or [], "stalled": bool(ac.get("stalled")), "silent_min": ac.get("silent_min"), "busy_tool": ac.get("busy_tool"), "busy_min": ac.get("busy_min")})
        dl = []
        for d, v in (p.get("deliverables") or {}).items():
            if not (isinstance(v, dict) and v.get("enabled")) or d not in (pg.get("per_deliverable_pct") or {}): continue
            name = v.get("title") or v.get("name") or re.sub(r"^D\d+[_ ]", "", os.path.splitext(v.get("file") or d)[0]).replace("_", " ")
            dl.append({"id": d, "name": name, "pct": pg["per_deliverable_pct"][d], "formula": (pg.get("formulas") or {}).get(d, ""), "built": bool(built.get(d)),
                       "scopes": [a["scope"] for a in rows if d in a["feeds"] and a["group"] != "consolidation"], "consolidations": [a["scope"] for a in rows if d in a["feeds"] and a["group"] == "consolidation"]})
        return {"agents": agents, "deliverables": dl}
    except Exception as e:
        return {"agents": [], "deliverables": [], "board_error": f"{type(e).__name__}: {e}"}

def state():
    pg = progress_now() or {}
    if pg.get("error"): pg = {"error": pg["error"], "analysts": [], "counts": {"done": 0, "running": 0, "planned": 0, "failed": 0}, "per_deliverable_pct": {}, "formulas": {}, "claims": {"total_in_registers": 0, "in_passed_scopes": 0}, "overall_pct": 0}
    st = load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}
    import rulings
    p = project(); qs = [q for q in load_questions() if q.get("released") is not False] + rulings.cards(); inbox = load_inbox(); ctrl = load_control()
    pending = {}
    for e in inbox:
        if e.get("kind") in ("answer", "keep", "reopen") and not e.get("processed"): pending[e.get("id")] = e
    for q in qs:
        pe = pending.get(q["id"])
        q["pending"] = {k: pe.get(k) for k in ("kind", "option", "text", "weight", "at")} if pe else None
    for a in pg.get("analysts", []) if "phase_critics" in p["scoring"] else []:
        if not scope_critics(a["scope"], p): a["check"] = "deterministic"   # no critic by design: passes on CHECK + quotes + locators
    orchestrator = resolve_model(p, "orchestrator"); bd = board(pg, p, st); mp = method_panels(p)
    return {**pg, **bd, **({"panels": mp} if mp else {}), "run": st.get("run") or os.path.basename(ROOT), "method": st.get("method") or p.get("_method", {}).get("name"), "client": p.get("engagement", {}).get("client", ""), "pass_threshold": p["scoring"]["pass_threshold"],
            "runtime": {"harness": HARNESS, "provider": orchestrator.provider, "model": orchestrator.model, "reasoning_effort": orchestrator.reasoning_effort},
            "questions": qs, "assumptions": (st.get("assumptions") or [])[-12:], "in_flight": [e for e in st.get("in_flight", []) or [] if not e.get("delivered")],
            "history": [{"t": h.get("t"), "msg": h.get("msg", "")[:220]} for h in (st.get("history") or [])[-10:]], "control": ctrl,
            "inbox": {"total": len(inbox), "unprocessed": sum(1 for e in inbox if not e.get("processed")), "recent": [{k: e.get(k) for k in ("client_id", "kind", "at", "processed", "outcome", "scope", "claim_id", "id", "command")} for e in inbox[-8:]]},
            "narrative": narrative(), "gate": gate_panel(p, bd.get("agents") or []), "knowledge": knowledge_panel(), "server": {"mode": "live", "time": now(), "run_dir": ROOT, "url": cfg().get("url", "")}}

def scope_detail(name):
    p = project(); m = method(); th = p["scoring"]["pass_threshold"]; gd = P("analysis", "gauntlet", name); critics = scope_critics(name, p)
    pg = progress_now() or {}; a = next((x for x in pg.get("analysts", []) if x["scope"] == name), None)
    out = {"scope": name, "threshold": th, "analyst": a, "claims_total": 0, "below": [], "passing": [], "scope_hints": [], "hints": []}
    if not os.path.isdir(gd): return out
    reg = load_json(os.path.join(gd, "claims.json"), {"claims": []}) if os.path.exists(os.path.join(gd, "claims.json")) else {"claims": []}
    rounds = sorted(int(f[5:-12]) for f in os.listdir(gd) if f.startswith("round") and f.endswith("-result.json"))
    scores = {}
    for r in rounds:
        for c in critics:
            fp = os.path.join(gd, f"round{r}-{c}.json")
            if os.path.exists(fp): scores.setdefault(r, {})[c] = {x["claim_id"]: x for x in load_json(fp, {}).get("scores", [])}
    hints = [e for e in load_inbox() if e.get("kind") in ("analyst_hint", "critic_fact", "critic_hint") and e.get("scope") == name]
    for h in hints: h["status"] = "applied" if h.get("processed") else "received"; h["note"] = h.get("outcome", "")
    out["scope_hints"] = [h for h in hints if not h.get("claim_id")]
    claims = []
    for c in reg.get("claims", []):
        hist = []; last = None
        for r in rounds:
            row = {}
            for cr in critics:
                x = (scores.get(r, {}).get(cr) or {}).get(c["id"])
                if x: row[cr] = x
            if row:
                hist.append({"round": r, **{cr: row[cr]["score"] for cr in row}}); last = (r, row)
        if not last:
            if not critics and "phase_critics" in p["scoring"]: claims.append({"id": c["id"], "statement": c.get("statement", ""), "below": False, "check": "deterministic"})   # no critic by design (lean inventory): CHECK + quotes + locators
            continue
        r, row = last; mn = min(v["score"] for v in row.values()); blocking = any(v.get("verdict") == "false" for v in row.values())
        low_rounds = sum(1 for h in hist if min(v for k, v in h.items() if k != "round") < th)
        claims.append({"id": c["id"], "statement": c.get("statement", ""), "round": r, "min_score": mn, "below": mn < th or blocking, "blocking": blocking, "recurring_rounds": low_rounds, "history": hist,
                       "critics": {cr: {k: row[cr].get(k) for k in ("score", "verdict", "issue", "counter_evidence", "fix_hint", "accept_if", "carried_from_round", "amended_from", "amendment")} for cr in row},
                       "hints": [h for h in hints if h.get("claim_id") == c["id"]]})
    import conflicts
    claims += [{"id": k, "statement": v.get("statement", ""), "below": False, "check": "conflict resolution (quote checked)"} for k, v in conflicts.resolved_claims(name).items() if k not in {c["id"] for c in claims}]   # added after the scope's gauntlet
    out["claims_total"] = len(claims)
    out["below"] = sorted([c for c in claims if c["below"]], key=lambda c: (not c["blocking"], c["min_score"], -c["recurring_rounds"]))
    out["passing"] = [c for c in claims if not c["below"]]
    return out

# ------------------------------------------------------------------ writes (inbox append, control flags)
def inbox_append(entry):
    with LOCK:
        entries = load_inbox()
        if entry.get("client_id") and any(e.get("client_id") == entry["client_id"] for e in entries): return {"ok": True, "duplicate": True}
        entry["client_id"] = entry.get("client_id") or uuid.uuid4().hex; entry.update({"at": now(), "processed": False, "by": "lead", "channel": "dashboard"})
        os.makedirs(os.path.dirname(INBOX_PATH), exist_ok=True); open(INBOX_PATH, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True, "entry": entry}
def control_set(**kw):
    with LOCK:
        c = load_control(); c.update(kw); save_json(CONTROL_PATH, c); return c

def answer(body):
    import rulings
    qs = load_questions() + rulings.cards(); q = next((x for x in qs if x["id"] == body.get("id")), None)
    if not q: return 404, {"error": "no such question"}
    if body.get("kind") in ("keep", "reopen"):   # keep the assumption (closed, nothing to route) / undo it - one click, no weight
        if q.get("kind") == "ruling": return 400, {"error": "a ruling is answered, not kept"}
        if (body["kind"] == "keep") == (q.get("status") == "closed"): return 400, {"error": f"{q['id']} is {q.get('status')}"}
        return 200, inbox_append({"client_id": body.get("client_id"), "kind": body["kind"], "id": q["id"]})
    if not (body.get("option") or (body.get("text") or "").strip()): return 400, {"error": "choose an option or write an answer"}
    return 200, inbox_append({"client_id": body.get("client_id"), "kind": "answer", "id": q["id"], "option": body.get("option") or "", "text": (body.get("text") or "").strip(), "weight": "fact" if q.get("kind") == "ruling" else body.get("weight", "proposal")})
def gate_feedback(body, text):
    """the lead's feedback on a key question of a gate round: persona configured, the question asked in that round, an intent, a text"""
    import gate as G
    p = project(); per = body.get("persona"); qid = body.get("question_id"); intent = body.get("intent")
    try: rnd = int(body.get("round"))
    except (TypeError, ValueError): return 400, {"error": "round required"}
    if per not in (p["scoring"].get("gate_personas") or []): return 400, {"error": f"{per} is not a gate persona"}
    if intent not in ("dismiss", "rephrase", "other"): return 400, {"error": "intent dismiss|rephrase|other"}
    if not any(q["id"] == qid for q in G.key_questions(p, per, rnd)): return 400, {"error": f"{per} is not asked {qid} in round {rnd}"}
    return 200, inbox_append({"client_id": body.get("client_id"), "kind": "gate_question_feedback", "persona": per, "question_id": qid, "round": rnd, "intent": intent, "text": text})
def panel_edit(body):
    """an optional edit of a method panel's cell (tech-fit-estimation: an override of the impact matrix) - checked by the method's panels.check,
    applied by `dbcx inbox apply` through panels.apply; nothing waits for it"""
    import common as C
    mod = C.load_method_module("panels")
    if not (mod and hasattr(mod, "check")): return 400, {"error": "this method has no editable panel"}
    e = {k: body.get(k) for k in ("panel", "row", "column", "action")}; e["text"] = (body.get("text") or "").strip(); e["reason"] = (body.get("reason") or "").strip()
    err = mod.check(e, project())
    if err: return 400, {"error": err}
    return 200, inbox_append(dict(e, client_id=body.get("client_id"), kind="panel_edit"))
def generic(body):
    kind = body.get("kind"); text = (body.get("text") or "").strip()
    if kind == "panel_edit": return panel_edit(body)
    if kind not in ("analyst_hint", "critic_fact", "critic_hint", "knowledge", "gate_question_feedback") or not text: return 400, {"error": "kind and text required"}
    if kind == "gate_question_feedback": return gate_feedback(body, text)
    if kind == "knowledge": return 200, inbox_append({"client_id": body.get("client_id"), "kind": kind, "scopes": [x for x in body.get("scopes") or [] if x], "text": text})   # a knowledge-base candidate once applied
    return 200, inbox_append({"client_id": body.get("client_id"), "kind": kind, "scope": body.get("scope"), "claim_id": body.get("claim_id") or None, "critic": body.get("critic") or None, "text": text})
def command(body):
    c = body.get("command")
    if c not in ("pause", "resume", "checkpoint"): return 400, {"error": "command pause|resume|checkpoint"}
    t = now()
    if c == "pause": control_set(pause_requested=True, pause_requested_at=t, pause_ack_at=None, paused_at=None)
    elif c == "resume": control_set(pause_requested=False, resumed_at=t, pause_ack_at=None, paused_at=None)
    elif c == "checkpoint": control_set(checkpoint_requested_at=t)
    return 200, inbox_append({"client_id": body.get("client_id"), "kind": "command", "command": c})

# ------------------------------------------------------------------ http
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, obj, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def authed(self):
        qs = parse_qs(urlparse(self.path).query); return (self.headers.get("X-Token") or (qs.get("t") or [""])[0]) == TOKEN
    def do_GET(self):
        u = urlparse(self.path)
        try:
            if not self.authed():
                if u.path == "/": return self.send(403, b"<!doctype html><meta charset=utf-8><body style='font:15px system-ui;padding:40px;max-width:520px'><h2>Run dashboard</h2><p>This link is missing its access token. Open the URL exactly as <code>dbcx dashboard url</code> prints it (it ends in <code>?t=...</code>).</p>", "text/html")
                return self.send(403, {"error": "token missing or wrong - dbcx dashboard url"})
            if u.path == "/": return self.send(200, open(HTML, "rb").read(), "text/html")
            if u.path == "/api/state": return self.send(200, state())
            if u.path == "/api/scope": return self.send(200, scope_detail((parse_qs(u.query).get("name") or [""])[0]))
            self.send(404, {"error": "not found"})
        except Exception as e: self.send(500, {"error": f"{type(e).__name__}: {e}"})
    def do_POST(self):
        u = urlparse(self.path)
        try:
            if not self.authed(): return self.send(403, {"error": "token missing or wrong"})
            n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/answer": return self.send(*answer(body))
            if u.path == "/api/inbox": return self.send(*generic(body))
            if u.path == "/api/command": return self.send(*command(body))
            self.send(404, {"error": "not found"})
        except Exception as e: self.send(500, {"error": f"{type(e).__name__}: {e}"})

def serve_foreground(port):
    global TOKEN
    c = cfg(); TOKEN = c.get("token") or secrets.token_urlsafe(12)
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    save_json(DASHBOARD_PATH, dict(c, token=TOKEN, port=port, pid=os.getpid(), url=f"http://127.0.0.1:{port}/?t={TOKEN}", started_at=now(), run_dir=ROOT, engine=ENGINE))
    print(f"dashboard {ROOT}: http://127.0.0.1:{port}/?t={TOKEN}", flush=True)
    srv.serve_forever()

def running():
    """A live pid on an open port is not enough: a server started from a package that has since moved or
    been deleted keeps answering, and serves nothing but file-not-found for its own assets (it holds the
    code in memory but reads the page from disk). Such a process is not this dashboard - restart it."""
    c = cfg()
    if not (c.get("pid") and alive(c["pid"]) and c.get("port") and port_open(c["port"])): return False
    return c.get("engine") == ENGINE

def serve(a):
    if running(): print(f"dashboard already running: {cfg()['url']}"); return cfg()["url"]
    c = cfg(); port = int(a[a.index("--port") + 1]) if "--port" in a else (c.get("port") if c.get("port") and not port_open(c["port"]) else free_port())
    os.makedirs(P("state"), exist_ok=True); log = open(P("state", "dashboard.log"), "a")
    env = dict(os.environ, DBCX_RUN=ROOT)
    pr = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--foreground", "--port", str(port)], cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True, env=env)
    for _ in range(40):
        if port_open(port) and cfg().get("pid") == pr.pid: break
        time.sleep(0.1)
    url = cfg().get("url") or f"http://127.0.0.1:{port}/"
    print(f"dashboard started (pid {pr.pid}): {url}"); return url

def main():
    global TOKEN
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] == "--foreground": serve_foreground(int(a[a.index("--port") + 1]) if "--port" in a else free_port()); return
    cmd = a[0]
    if cmd == "serve":
        url = serve(a)
        if "--no-open" not in a and url and os.environ.get("DBCX_NO_OPEN") != "1": webbrowser.open(url)   # DBCX_NO_OPEN=1 (tests) opens no browser
    elif cmd == "open":
        if not running(): serve(a)
        if os.environ.get("DBCX_NO_OPEN") != "1": webbrowser.open(cfg()["url"])
        print(cfg()["url"])
    elif cmd == "url": print(cfg().get("url") or "(not started - dbcx dashboard serve)")
    elif cmd == "status": print(("running: " + cfg()["url"]) if running() else "not running" + (f" (last url {cfg().get('url')})" if cfg().get("url") else ""))
    elif cmd == "stop":
        c = cfg()
        if c.get("pid") and alive(c["pid"]): os.kill(int(c["pid"]), 15); print(f"stopped pid {c['pid']}")
        else: print("not running")
    elif cmd == "state":
        TOKEN = cfg().get("token", "")
        print(json.dumps(scope_detail(a[a.index("--scope") + 1]) if "--scope" in a else state(), indent=1, ensure_ascii=False, default=str))
    else: sys.exit(__doc__)

TOKEN = None
if __name__ == "__main__":
    main()
