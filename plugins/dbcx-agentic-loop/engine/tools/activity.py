#!/usr/bin/env python3
"""Live agent activity: the PreToolUse hook appends one compact record per sub-agent tool call to state/ACTIVITY.jsonl
({at, agent, id, tool, what}); the dashboard's run board and `dbcx status` read it back per in-flight agent and flag an agent stalled after
activity.stall_minutes without a sign of life (last activity, last output write or the spawn, whichever is latest; an agent that reported
done is not stalled). PostToolUse appends a bare done marker ({at, agent, id, tool, end: 1}): a call without one is still running and the agent
counts as busy in that tool, not stalled, until activity.max_call_minutes. `what` is a short plain-language line built from the tool input - a file's basename, a Grep pattern cut short, the
dbcx tool a Bash command runs - never file contents or a full command line. The file is capped (the older half is dropped past MAX_BYTES).
No command line of its own; imported by hooks/dbcx_hook.py, dashboard.py and status.py.
"""
import json, os, re, time

MAX_BYTES = 512 * 1024; TAIL_BYTES = 256 * 1024
DBCX = {"md_to_json": "checking its claims", "extract_claims": "extracting the claims", "safe_web": "looking up the standard documentation", "evidence": "checking the evidence",
        "score_aggregate": "aggregating the scores", "build_excel": "building a workbook", "render_workbook": "rendering a workbook", "lint_deliverable": "checking the deliverable",
        "corpus": "searching the corpus", "grep_scopes": "searching the scopes", "reference": "reading the reference facts", "questions": "filing a question", "kb": "reading the knowledge base",
        "conflicts": "reading the conflicts", "rulings": "reading the rulings", "render": "rendering a brief", "gate": "reading the gate questions", "rows": "reading the rows", "postpass": "applying a text correction"}
SHELL = {"grep": "searching the files", "rg": "searching the files", "find": "listing files", "ls": "listing files", "cat": "reading a file", "head": "reading a file", "tail": "reading a file",
         "sed": "reading a file", "wc": "counting lines", "git": "reading the version history", "jq": "reading a JSON file", "python3": "running a script", "python": "running a script"}

def _base(p): return os.path.basename(str(p or "").rstrip("/\\")) or "a file"
def _cut(s, n=40): s = " ".join(str(s or "").split()); return s if len(s) <= n else s[:n - 1] + "…"

def summary(tool, ti):
    """plain-language line for one tool call; never file contents, never a full command"""
    ti = ti or {}
    if tool == "Read": return f"reading {_base(ti.get('file_path'))}"
    if tool == "Write": return f"writing {_base(ti.get('file_path'))}"
    if tool in ("Edit", "MultiEdit", "NotebookEdit"): return f"editing {_base(ti.get('file_path') or ti.get('notebook_path'))}"
    if tool == "Grep": return f"searching for “{_cut(ti.get('pattern'))}”"
    if tool == "Glob": return f"listing {_cut(ti.get('pattern'))}"
    if tool == "WebSearch": return "searching the web"
    if tool == "WebFetch": m = re.match(r"https?://([^/:?#]+)", ti.get("url") or ""); return f"reading a page on {m.group(1)}" if m else "reading a web page"
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if re.search(r"\bstatus(?:\.py)?[\"']?\s+done\b", cmd): return "reporting done"
        sub = re.findall(r"\bdbcx(?:\.py)?[\"']?\s+([a-z_]+)", cmd); tools = sub + re.findall(r"[\\/]([a-z_]+)\.py\b", cmd)
        hit = next((t for t in tools if t in DBCX), None)
        if hit or sub: return DBCX[hit] if hit else f"running dbcx {sub[0]}"
        w = os.path.basename((cmd.split() or [""])[0])
        return SHELL.get(w, "running a shell command")
    if tool == "Agent": return "starting a helper agent"
    if tool == "SendMessage": return "sending a message"
    if tool.startswith("mcp__"): return "using a connected tool"
    return f"using {tool}"

def record(run, agent, agent_id, tool, ti, end=False):
    """append one record (PreToolUse: with `what`; PostToolUse: end=True, a bare done marker); drops the older half once the file passes MAX_BYTES"""
    fp = os.path.join(run, "state", "ACTIVITY.jsonl"); r = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": agent, "id": agent_id or "", "tool": tool}
    line = json.dumps(dict(r, end=1) if end else dict(r, what=summary(tool, ti)), ensure_ascii=False) + "\n"
    try:
        if os.path.getsize(fp) > MAX_BYTES:
            keep = open(fp, encoding="utf-8").read().splitlines(True); open(fp, "w", encoding="utf-8").writelines(keep[len(keep) // 2:])
    except OSError: pass
    with open(fp, "a", encoding="utf-8") as f: f.write(line)

def load(run):
    """the newest records (the file's last TAIL_BYTES), oldest first"""
    fp = os.path.join(run, "state", "ACTIVITY.jsonl"); out = []
    try:
        with open(fp, "rb") as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - TAIL_BYTES)); raw = f.read().decode("utf-8", "replace").splitlines()
    except OSError: return out
    for l in raw[1:] if n > TAIL_BYTES else raw:
        try: out.append(json.loads(l))
        except ValueError: pass
    return out

def _epoch(iso):
    try: return time.mktime(time.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError): return None

def _mine(e, r, types):
    """a record belongs to in_flight entry e: the harness's agent id, else the agent name, else the sub-agent type when only one entry has it"""
    if r.get("id") and r["id"] == e.get("conversation_id"): return True
    if r.get("agent") == e.get("agent"): return True
    st = e.get("subagent_type")
    return bool(st) and r.get("agent") == st and types.get(st) == 1 and (_epoch(r.get("at")) or 0) >= (_epoch(e.get("spawned_at")) or 0)

def per_agent(run, entries, stall_minutes, now=None, last_write=None, recent=4, max_call_minutes=60):
    """{agent: {activity_at, activity, recent, stalled, silent_min, busy_tool, busy_min}} for the undelivered in_flight entries; last_write(e) -> iso or None.
    A last call with a Pre record and no Post yet is open: the agent is busy in that tool (a build, a long scan), not stalled, up to max_call_minutes."""
    now = time.time() if now is None else now; recs = load(run); out = {}
    live = [e for e in entries if not e.get("delivered")]; types = {}
    for e in live: types[e.get("subagent_type")] = types.get(e.get("subagent_type"), 0) + 1
    for e in live:
        mine = [r for r in recs if _mine(e, r, types) and (_epoch(r.get("at")) or 0) >= (_epoch(e.get("spawned_at")) or 0)]
        calls = [r for r in mine if not r.get("end")]; last = calls[-1] if calls else None; seen = mine[-1] if mine else None
        beat = max([t for t in (_epoch(seen and seen.get("at")), _epoch(last_write(e) if last_write else None), _epoch(e.get("spawned_at"))) if t] or [None])
        silent = (now - beat) / 60 if beat else None
        busy = (now - _epoch(seen["at"])) / 60 if seen and not seen.get("end") and _epoch(seen.get("at")) else None   # the last record is a call without its done marker
        busy = busy if busy is not None and busy < max_call_minutes else None
        out[e.get("agent")] = {"activity_at": last and last.get("at"), "activity": last and last.get("what"), "recent": [r.get("what") for r in reversed(calls[-recent:])],
                               "stalled": bool(silent is not None and silent >= stall_minutes and busy is None and not e.get("done")), "silent_min": int(silent) if silent is not None else None,
                               "busy_tool": seen.get("tool") if busy is not None else None, "busy_min": int(busy) if busy is not None else None}
    return out

def stall_minutes(cfg): return float((cfg.get("activity") or {}).get("stall_minutes") or 15)
def max_call_minutes(cfg): return float((cfg.get("activity") or {}).get("max_call_minutes") or 60)
