#!/usr/bin/env python3
"""Claude Code hook entry point. The adapter normalizes events;
shared decisions live in policy.py. Invoked with the event name as argv[1]; reads hook input
JSON on stdin. Does nothing outside a run folder (no run.json in cwd or a parent) - so it never touches other projects.

Guardrails (deterministic; judgement rules stay in the agent definitions, file validity in the tools):
  H1  evidence bases are read-only: deny mutating Bash commands / Write / Edit targeting a read_only base root; deny rules.do_not_run commands.
  H2  closed artefacts: deny Write/Edit of analysis/gauntlet/*/round<n>-*.json whose checksum is recorded in round<n>-result.json, and Bash `md_to_json critic` on such a file.
  H3  no client data to external services: deny WebSearch/WebFetch whose query/url contains the client name, a scope name, an internal base root or a corpus/handover locator.
  H4  rendered briefs only: an Agent spawn of a dbcx-agentic-loop:* sub-agent must reference an existing analysis/briefs/*.md and pass the brief's MODEL as `model`; PostToolUse registers the agent in STATUS in_flight.
  H5  evidence-base access matrix: deny Read/Grep/Glob/Bash on a base's roots for a role the base does not list (run.json / method evidence_bases -> roles).
  H6  delivery test on SubagentStop: run every undelivered in_flight entry's check_cmd whose output files exist, mark DELIVERED/INVALID; on INVALID ask the sub-agent once to fix its file.
  H7  SessionStart / PreCompact: inject `dbcx status verify` + resume pointers.
  H8  text under review: PostToolUse Write/Edit of an analysis .md while a round is open (snapshot without result) -> DIRTY marker + warning.
  H9  shared run files (LEARNINGS, STATUS, ORCHESTRATOR_NOTES, RESUME, the knowledge base KNOWLEDGE.json / .md) are written by the orchestrator only: deny from
      sub-agents, and deny them the writing knowledge-base commands (`dbcx kb add|promote|reject|import-handover|export`; show|index|pending stay open)
      and the rulings sheet (state/RULINGS.json, docs/RULINGS.md; `dbcx rulings draft|add|answer|done|skip` - its answers are knowledge-base entries)
      and the conflict register (analysis/consolidated/CONFLICTS.json; `dbcx conflicts detect|route|resolve|undecidable|skip`; list|show stay open).
  H10 dashboard pause: while state/CONTROL.json has pause_requested, the orchestrator's Agent spawns are denied (graceful pause = finish in-flight, persist, end).
  H11 inbox: after any orchestrator tool call, new entries in state/INBOX.jsonl (answers, hints, disputes, commands from the dashboard) are announced once.
  H12 SessionStart: the dashboard server is started for the run and opened in the browser (startup / resume / clear, not compact).
  H13 activity: PreToolUse of an allowed sub-agent call appends {at, agent, id, tool, what} to state/ACTIVITY.jsonl, PostToolUse / PostToolUseFailure a bare done marker
      (engine/tools/activity.py) - the board's live line, busy-in-a-long-call and stall flag.
  H14 own methods: sub-agents do not write the method or override files - <engagement|run>/methods/**, <engagement|run>/overrides/**,
      the personal library <DBCX_HOME>/methods/** and the run's method folder (Write/Edit, shell write targets, interpreter writes, `dbcx override add|remove`);
      the deliverable editor keeps the run's overrides/deliverables.<lang>.json and labels.<lang>.json (its brief's tools). A run whose own method
      changed since `status init` (STATUS.json method_guard hash) denies every further sub-agent call; no stored hash (an older run) or a plugin method: no check.
      sub-agents get none of `dbcx method new|card|generate|confirm|save|install` (list and check stay open).
Sub-agent detection: hook input `agent_type`/`agent_name` when present, else the .meta.json beside a `.../subagents/agent-*.jsonl` transcript.
"""
import json, os, sys

EVENT = sys.argv[1] if len(sys.argv) > 1 else ""
try: INP = json.loads(sys.stdin.buffer.read().decode("utf-8"))   # not the locale codec (cp1252 on Windows)
except Exception: INP = {}

def find_run(start):
    cur = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, "run.json")): return cur
        parent = os.path.dirname(cur)
        if parent == cur: return None
        cur = parent

RUN = find_run(INP.get("cwd") or os.getcwd())
if not RUN: sys.exit(0)   # before any further import: this path runs on every tool call of every session outside a run
import re, subprocess, time
HOOKS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HOOKS)
from policy import Context as PolicyContext, WRITE_CALL_RE, bash_preprocess, canon, edit_paths, evaluate_basic, inside, mentions, mentions_roots, resolve_path, write_targets
from adapters import claude as claude_adapter
os.environ["DBCX_RUN"] = RUN
PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); TOOLS = os.path.join(PLUGIN, "engine", "tools"); sys.path.insert(0, TOOLS)
from runtime import HARNESS, package_version
NORMALIZED = claude_adapter.normalize(EVENT, INP)
try:
    import common
    CFG = common.project(); METHOD = CFG["_method"]; BASES = common.evidence_bases(CFG)
except Exception as e:
    if os.environ.get("DBCX_HOOK_DEBUG"): print(f"[dbcx hook] configuration could not be loaded: {e!r}", file=sys.stderr)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": EVENT, "additionalContext": f"[dbcx hook] configuration could not be loaded ({e}); guardrails inactive for this call"}})) if EVENT in ("SessionStart", "PreCompact") else None; sys.exit(0)

def P(*a): return os.path.join(RUN, *a)
def jload(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def heartbeat():
    """state/HOOKS.json: proof that the hook runs. Without it no hook event happens - no in_flight entry, no delivery test, no guard - and nothing on disk would say so. `dbcx hooks status`,
    `dbcx doctor` and `dbcx status verify` read this file and warn when no event was ever recorded."""
    try:
        import time
        fp = P("state", "HOOKS.json"); d = jload(fp, {}) or {}
        h = d.setdefault("harnesses", {}).setdefault(HARNESS, {}); now = time.strftime("%Y-%m-%dT%H:%M:%S")
        h.update({"plugin_root": PLUGIN, "version": package_version(), "last_event_at": now}); h.setdefault("first_event_at", now)
        ev = h.setdefault("events", {}); ev[EVENT] = ev.get(EVENT, 0) + 1
        if NORMALIZED.tool: tl = h.setdefault("tools", {}); tl[NORMALIZED.tool] = tl.get(NORMALIZED.tool, 0) + 1
        os.makedirs(os.path.dirname(fp), exist_ok=True); json.dump(d, open(fp, "w", encoding="utf-8"), indent=1)
    except Exception as e:
        if os.environ.get("DBCX_HOOK_DEBUG"): print(f"[dbcx hook] heartbeat failed: {e!r}", file=sys.stderr)
heartbeat()

CLIENT = (CFG.get("engagement", {}).get("client") or "").strip()
CLIENT_PUBLIC = bool((CFG.get("hook") or {}).get("client_name_public"))   # engagement.json / run.json -> hook.client_name_public: the client's public name may be used in web queries (public company research); scope names and locators stay blocked
SCOPE_NAMES = [] if (METHOD.get("hook") or {}).get("scope_names_public") else [u for u in (jload(common.SCOPES_PATH, {}) or {}).get("scopes", {}) if len(u) > 5]   # method.json hook.scope_names_public: scopes are public names (technologies), not client data
DO_NOT_RUN = [x for x in (CFG.get("rules", {}).get("do_not_run") or []) if x and not x.startswith("any ")]
for pk in common.packs_of(CFG, "platform"): DO_NOT_RUN += [x for x in pk.get("as_source", {}).get("do_not_run", []) if x and not x.startswith("any ")]
SHARED_FILES = ("docs/LEARNINGS.md", "state/STATUS.json", "docs/ORCHESTRATOR_NOTES.md", "docs/RESUME.md", "state/KNOWLEDGE.json", "docs/KNOWLEDGE.md", "state/RULINGS.json", "docs/RULINGS.md", "analysis/consolidated/CONFLICTS.json")
KB_WRITE_RE = re.compile(r"(?:\bdbcx(?:\.py)?[\"']?\s+kb|\bkb\.py)\s+(?:add|promote|reject|import-handover|export)\b|(?:\bdbcx(?:\.py)?[\"']?\s+rulings|\brulings\.py)\s+(?:draft|add|answer|done|skip)\b|(?:\bdbcx(?:\.py)?[\"']?\s+conflicts|\bconflicts\.py)\s+(?:detect|route|resolve|undecidable|skip)\b")   # H9: the curated run knowledge base, the rulings sheet that feeds it and the conflict register
RETRIEVAL_SETUP_RE = re.compile(r"(?:\bdbcx(?:\.py)?[\"']?\s+retrieval|\bretrieval\.py)\s+(?:enable|decline)\b|\bretrieval_backends(?:\.py)?[\"']?\s+fetch-model\b|\bretrieval_backends\b.*\bfetch_model\b")   # install + download are the orchestrator's, after the user's yes
CORPUS_CALL_RE = re.compile(r"(?:\bdbcx(?:\.py)?[\"']?\s+corpus|\bcorpus\.py|\bretrieval\.py)\s+(?:search|map|grep|show)\b")
KB_DENY = "the run knowledge base is curated by the orchestrator only. Put cross-scope knowledge into your report (Estate observations / Open questions) so the orchestrator can promote it; `dbcx kb show|index|pending` stay open to you."
CONFLICTS_DENY = "the conflict register is written by the orchestrator's `dbcx conflicts` only. Answer each conflict in your report (`CF-n: resolved by <claim id>` or `CF-n: undecidable - <reason>`); `dbcx conflicts list|show` stay open to you."
LIBRARY_METHODS = common.LIBRARY_METHODS_DIR   # H14: the personal library (<DBCX_HOME>/methods)
METHOD_ROOTS = list(dict.fromkeys(os.path.realpath(r) for r in [common.PP("methods"), P("methods"), common.PP("overrides"), P("overrides"), LIBRARY_METHODS] + ([METHOD["_dir"]] if METHOD.get("_dir") else [])))
METHOD_DENY = "method and override files are changed by the lead between runs, not by agents. Report the change you need in your final message."
OVERRIDE_WRITE_RE = re.compile(r"(?:\bdbcx(?:\.py)?[\"']?\s+override|\boverride\.py)\s+(?:add|remove)\b")
METHOD_CMD_RE = re.compile(r"(?:\bdbcx(?:\.py)?[\"']?\s+method|\bmethod\.py)\s+(?:new|card|generate|confirm|save|install)\b|\bmethod_generate\b")   # own methods are defined with the user, between runs
EDITOR_OVERRIDE_RE = re.compile(r"^(?:deliverables|labels)\.[\w-]+\.json$")   # engine/briefs/editor.md: the deliverable editor's run overrides
INTERNAL_ROOTS = [r for eb in BASES if not eb.get("external") and eb.get("privacy", True) for r in eb.get("abs_roots", [])]   # a run-folder base (engine bases: deliverables, deliverables/intern, work|state|docs, gate-io) may declare "privacy": false - it is not client evidence
READ_ONLY_ROOTS = [r for eb in BASES if eb.get("read_only", True) and eb.get("kind") in common.READ_ONLY_KINDS for r in eb.get("abs_roots", [])]   # + vendor-code, client-repo
# the claims register and the critics' scored JSON, using the run's OWN configured critic ids -
# frozen for every agent including the orchestrator (see policy.frozen_register_path).
_CRITICS = common.all_critics(CFG) or ["client", "standard"]   # + every scoring.phase_critics id
FROZEN_REGISTER_RE = re.compile(r"^claims.*\.(md|json)$|^round\d+-result\.json$|^round\d+-(?:" + "|".join(re.escape(c) for c in _CRITICS) + r")\.json$|\.pre-amend\d*\.json$")
POLICY = PolicyContext(RUN, CLIENT, CLIENT_PUBLIC, tuple(SCOPE_NAMES), tuple(DO_NOT_RUN), tuple(READ_ONLY_ROOTS), tuple(INTERNAL_ROOTS), FROZEN_REGISTER_RE)

def agent_identity():
    for k in ("agent_name", "agent_type", "agentName", "agentType", "agent_id"):
        if INP.get(k): return str(INP[k]), True
    tp = INP.get("transcript_path") or ""
    if "/subagents/" in tp.replace("\\", "/"):
        meta = jload(tp[:-6] + ".meta.json", {}) if tp.endswith(".jsonl") else {}
        return str(meta.get("name") or meta.get("agentType") or os.path.basename(tp)), True
    return "orchestrator", False

def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": common.cli_text("[dbcx guardrail] " + reason)}})); sys.exit(0)
def context(text, event):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": common.cli_text(text)}})); sys.exit(0)

def under(path, roots):
    if not path: return None
    ap = os.path.realpath(resolve_path(path, RUN))   # realpath, matching the realpath'd abs_roots (common.evidence_bases): a symlinked temp dir or checkout must not let a tool_input path dodge an evidence-base root by spelling
    for r in roots:
        if inside(ap, r): return r   # canon(): slash direction, case and Git Bash /c/ spellings on Windows
    return None
def denied_bases(role, path=None, text=None, agent=None):
    """bases the role may not read that the path lies in / the text mentions. Overlapping roots: the MOST SPECIFIC base decides
    (input/handover inside input/ is its own base), so a permitting inner base is never shadowed by a denying outer one. `agent`: a
    method brief kind's agent also reads the bases its kind grants (common.agent_reads)."""
    out = []
    if path:
        best = None
        for eb in BASES:
            r = under(path, eb.get("abs_roots", []))
            if r and (best is None or len(r) > len(best[1])): best = (eb, r)
        return [best[0]["id"]] if best and not common.role_may_read(role, best[0], agent, METHOD) else []
    if text:
        allowed_roots = [r for eb in BASES if common.role_may_read(role, eb, agent, METHOD) for r in eb.get("abs_roots", [])]
        for eb in BASES:
            if common.role_may_read(role, eb, agent, METHOD): continue
            for r in mentions_roots(text, eb.get("abs_roots", []), RUN, RUN):   # every spelling the run uses, incl. ../../<base>
                # the permitted-inner-base exception must recognise the inner root in ANY spelling too
                # (a relative `analysis/gate/round1-cto.md` was missed when only the absolute spelling
                # was tested against the raw text, denying a gate role its own permitted sub-base)
                if any(inside(a, r) and canon(a) != canon(r) and mentions_roots(text, [a], RUN, RUN) for a in allowed_roots): continue
                out.append(eb["id"]); break
    return out

def method_file(path, role):
    """H14: a path under the method / override / library roots - except the deliverable editor's own run override files"""
    if not under(path, METHOD_ROOTS): return False
    ap = os.path.realpath(resolve_path(path, RUN))
    return not (role == "editor" and canon(os.path.dirname(ap)) == canon(os.path.realpath(P("overrides"))) and EDITOR_OVERRIDE_RE.match(os.path.basename(ap)))
def method_changed():
    """H14: the stop text when this run's own method changed since `status init`; None without a stored hash or for a plugin method"""
    mg = (jload(P("state", "STATUS.json"), {}) or {}).get("method_guard") or {}
    if not mg.get("hash") or mg.get("source") == "plugin": return None
    import method_guard; r = method_guard.check(mg, METHOD)
    return r[1] if r and r[0] == "stop" else None

def closed_score_file(path):
    m = re.match(r"round(\d+)-(.+)\.json$", os.path.basename(path or ""))
    if not m or "analysis/gauntlet/" not in canon(path).replace(os.sep, "/"): return False
    res = jload(os.path.join(os.path.dirname(path), f"round{m.group(1)}-result.json"), {}) or {}
    return m.group(2) in (res.get("checksums") or {})

NOTIFIED = P("state", "INBOX.notified.json")
def inbox_notice(mark=True):
    """One line per unprocessed inbox entry the orchestrator has not been told about yet (+ a pause not yet acknowledged)."""
    entries = []
    try:
        for l in open(P("state", "INBOX.jsonl"), encoding="utf-8"):
            l = l.strip()
            if l: entries.append(json.loads(l))
    except Exception: entries = []
    seen = set(jload(NOTIFIED, []) or [])
    new = [e for e in entries if not e.get("processed") and e.get("client_id") not in seen]
    ctl = jload(P("state", "CONTROL.json"), {}) or {}
    pause_key = f"pause:{ctl.get('pause_requested_at')}" if ctl.get("pause_requested") and not ctl.get("pause_ack_at") else None
    lines = []
    for e in new:
        k = e.get("kind"); t = (e.get("text") or "")[:120]
        if k == "answer": lines.append(f"answer to {e.get('id')}: option {e.get('option') or '-'} {t} [{e.get('weight')}]")
        elif k == "command": lines.append(f"command {e.get('command')}")
        elif k == "keep": lines.append(f"keep {e.get('id')}: the lead keeps the assumption - `dbcx inbox apply` closes the question; nothing to route, no amend round, no re-score, start no round for it")
        elif k == "reopen": lines.append(f"reopen {e.get('id')}: a kept question is open again - `dbcx inbox apply` reopens it; nothing to route")
        elif k == "gate_question_feedback": lines.append(f"gate question feedback {e.get('persona')} {e.get('question_id')} (round {e.get('round')}, {e.get('intent')}): {t} - `dbcx inbox next` prints the steps; `dbcx gate question` closes it")
        else: lines.append(f"{k} {e.get('scope')}/{e.get('claim_id') or '-'}" + (f" -> critic-{e.get('critic')}" if e.get('critic') else "") + f": {t}")
    if pause_key and pause_key not in seen: lines.append(f"PAUSE requested from the dashboard at {ctl.get('pause_requested_at')}: spawn nothing new (denied by hook), finish in-flight work, `dbcx status verify`, write docs/RESUME.md, `dbcx inbox control ack-pause`, end your turn")
    if not lines: return ""
    if mark:
        try: json.dump(sorted(seen | {e.get("client_id") for e in new} | ({pause_key} if pause_key else set())), open(NOTIFIED, "w", encoding="utf-8"))
        except Exception: pass
    return "[dbcx inbox] new from the dashboard - apply with `dbcx inbox next` / `dbcx inbox apply <id>` at your next step (never interrupt a running conversion):\n- " + "\n- ".join(lines)

def brief_model(brief_path):
    try:
        m = re.search(r"^MODEL: (\S+)", open(brief_path, encoding="utf-8").read(), re.M); return m.group(1) if m else None
    except Exception: return None
def brief_runtime(brief_path):
    out = {}
    try: txt = open(brief_path, encoding="utf-8").read()
    except Exception: return out
    for key, field in (("MODEL", "model"), ("SPAWN MODEL", "spawn_model"), ("REASONING EFFORT", "reasoning_effort"), ("HARNESS", "harness"), ("PROVIDER", "provider")):
        m = re.search(r"^" + key + r": (\S+)", txt, re.M)
        if m: out[field] = m.group(1)
    return out
def brief_fields(brief_path):
    out = {}
    try: txt = open(brief_path, encoding="utf-8").read()
    except Exception: return out
    for key, fld in (("OUTPUT", "output"), ("CHECK", "check"), ("AGENT NAME", "agent")):
        m = re.search(r"^" + key + r": (.+)$", txt, re.M)
        if m: out[fld] = m.group(1).strip()
    return out

# ------------------------------------------------------------------ PreToolUse
def pre():
    tool = NORMALIZED.tool; ti = NORMALIZED.tool_input; name, sub = agent_identity(); role = common.role_of_agent(name, METHOD) if sub else "orchestrator"
    if sub:
        mc = method_changed()
        if mc: deny(mc)
    basic = evaluate_basic(NORMALIZED, POLICY)
    if not basic.allow: deny(basic.reason)
    if tool == "Bash":
        # do_not_run and the read-only guard are decided by evaluate_basic above - policy.py is the ONLY place a shell rule
        # lives. A second copy here re-denied redirects that policy had judged by their target.
        cmd = ti.get("command", "") or ""
        db = denied_bases(role, text=cmd, agent=name if sub else None)
        if sub and db: deny(f"{name} ({role}) has no access to evidence base(s) {', '.join(db)} by design (disjoint evidence bases keep the client-side and the standard-side critics honest). Route the question to the orchestrator; a conclusion from this role about that evidence carries no weight.")
        m = re.search(r"md_to_json(?:\.py)?\s+critic\s+(\S+\.md)", cmd)
        if m and "--force" not in cmd:
            jp = resolve_path(m.group(1)[:-3] + ".json", RUN)
            if closed_score_file(jp): deny(f"{common.relp(jp, RUN)} is CLOSED: score_aggregate recorded its checksum; re-converting drops the carried entries and breaks the build guard. If the Markdown really changed, convert with --force and re-run score_aggregate for this and every later round.")
        if sub and re.search(r"(>>?|tee)\s*\S*(LEARNINGS\.md|STATUS\.json|ORCHESTRATOR_NOTES\.md|(?:KNOWLEDGE|RULINGS)\.(?:json|md)|CONFLICTS\.json)", cmd): deny("shared run files are written by the orchestrator only (concurrent appends clobber). Put learnings and status facts in your final report.")
        if sub:   # H14: the targets evaluate_basic judges, against the method / override / library roots
            masked, risky = bash_preprocess(cmd)
            if METHOD_CMD_RE.search(cmd): deny(f"{name} ({role}): an own method is defined, changed, confirmed and stored by the lead with the user between runs (`dbcx method new|card|generate|confirm|save|install`). Report what the method needs in your final message.")
            if OVERRIDE_WRITE_RE.search(cmd) or any(method_file(t, role) for t in write_targets(masked, NORMALIZED.cwd or RUN)) or any(WRITE_CALL_RE.search(b) and mentions(b, METHOD_ROOTS) for b in risky): deny(f"{name} ({role}): " + METHOD_DENY)
        if sub and role != "orchestrator" and KB_WRITE_RE.search(cmd): deny(f"{name} ({role}): " + (CONFLICTS_DENY if re.search(r"conflicts(?:\.py)?\s", KB_WRITE_RE.search(cmd).group(0)) else KB_DENY))
        # corpus retrieval reads the corpus evidence base (its paths: corpus/search/** lies inside the corpus root, H5 above)
        if sub and RETRIEVAL_SETUP_RE.search(cmd): deny(f"{name} ({role}): installing the search model or recording the user's decision about it is the orchestrator's step after the user's answer. Report the need instead.")
        if sub and CORPUS_CALL_RE.search(cmd):
            db = denied_bases(role, path=os.path.join(common.CORPUS_DIR, "search"), agent=name)
            if db: deny(f"{name} ({role}) has no access to evidence base(s) {', '.join(db)} by design: `dbcx corpus search|map|grep|show` read the client's documents. Route the question to the orchestrator.")
    elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        paths = edit_paths(NORMALIZED) or [ti.get("file_path") or ti.get("notebook_path") or ""]
        for fp in paths:
            ap = resolve_path(fp, RUN)
            db = denied_bases(role, path=fp, agent=name if sub else None)
            if sub and db: deny(f"{name} ({role}) has no access to evidence base(s) {', '.join(db)} by design.")
            if closed_score_file(ap): deny(f"{common.relp(ap, RUN)} is a CLOSED score file (checksum recorded by score_aggregate). Scores are never edited by hand; a post-pass correction is text on the analysis, not on the scores.")
            # A8's full freeze (claims*.md/json, round*-result.json, round*-<critic>.json, *.pre-amend*.json,
            # for every agent incl. the orchestrator) is decided by evaluate_basic() above - not duplicated here.
            if sub and any(canon(ap).endswith(canon(s)) for s in SHARED_FILES): deny((CONFLICTS_DENY if os.path.basename(ap) == "CONFLICTS.json" else KB_DENY if os.path.basename(ap).startswith(("KNOWLEDGE.", "RULINGS.")) else "shared run files (LEARNINGS, STATUS, ORCHESTRATOR_NOTES, RESUME) are written by the orchestrator only. Report learnings and facts in your final message."))
            if sub and method_file(fp, role): deny(f"{name} ({role}): " + METHOD_DENY)
            if sub and inside(ap, P("deliverables")): deny("client deliverables are written by the orchestrator through `dbcx build_excel` only (this covers deliverables/intern/ too).")
            if sub and inside(ap, P("work", "render")): deny("work/render/ is written by `dbcx render_workbook` only.")
    elif tool in ("WebSearch", "WebFetch"):
        q = (ti.get("query") or "") + " " + (ti.get("url") or "") + " " + (ti.get("prompt") or ""); ql = q.lower()
        if CLIENT and len(CLIENT) > 2 and CLIENT.lower() in ql and not CLIENT_PUBLIC: deny(f"the client name must not reach an external service (query contains '{CLIENT}'). Ask the standard question generically (or set hook.client_name_public in engagement.json for public company research).")
        hit = next((u for u in SCOPE_NAMES if u.lower() in ql), None)
        if hit: deny(f"a scope name of the client ('{hit}') must not reach an external service. Describe the mechanism generically.")
        if mentions(q, INTERNAL_ROOTS): deny("an internal evidence path must not reach an external service.")
        if re.search(r"\bSRC-\d{3}|\bHO-[\w-]+#", q): deny("a corpus or handover locator must not reach an external service.")
    elif tool == "SendMessage":
        # the post-pass corrector has no evidence base by design; a peer message is how it obtained evidence
        # anyway (a stopped critic answered). Verification requests go through the orchestrator.
        if sub and role == "postpass": deny(f"{name} (post-pass corrector) does not message peers: you have no evidence access by design and a critic or analyst must not verify for you. List what you could not verify in your report; the orchestrator routes it.")
    elif tool in ("Read", "Grep", "Glob"):
        fp = ti.get("file_path") or ti.get("path") or ""
        db = denied_bases(role, path=fp, agent=name if sub else None) if fp else (denied_bases(role, text=ti.get("pattern", ""), agent=name if sub else None) if tool != "Read" else [])
        if sub and db: deny(f"{name} ({role}) has no access to evidence base(s) {', '.join(db)} by design. Route the question to the orchestrator.")
    elif tool == "Agent":
        st = ti.get("subagent_type") or ti.get("agent_type") or ""
        ctl = jload(P("state", "CONTROL.json"), {}) or {}
        if ctl.get("pause_requested") and not sub: deny(f"PAUSE requested from the dashboard at {ctl.get('pause_requested_at')}: no new agents. Finish the in-flight work, `dbcx status verify`, write docs/RESUME.md, `dbcx inbox control ack-pause`, then end your turn. A fresh session resumes with `dbcx inbox control resume`.")
        tracked = st.startswith(common.AGENT_PREFIX)
        if tracked:
            prompt = ti.get("prompt") or ti.get("message") or ""; m = re.search(r"(analysis[\\/]briefs[\\/][\w.\-]+\.md)", prompt)
            inline = "## CONTEXT" in prompt and "Follow your agent definition." in prompt
            if not m and not inline: deny("spawn a dbcx sub-agent only with a RENDERED brief: `dbcx render brief ... --out` writes analysis/briefs/<agent>.md - reference that path in the prompt (never retype header fields; addenda go to a file via --addendum).")
            if m:
                bp = P(m.group(1))
                if not os.path.exists(bp): deny(f"the referenced brief {m.group(1)} does not exist - render it first (dbcx render brief ... --out).")
                bfields = brief_fields(bp); spawn_name = ti.get("name") or ti.get("agent_name")
                if spawn_name and bfields.get("agent") and str(spawn_name) != bfields["agent"]:
                    # a wrong agent name loses the evidence-base scoping (role_of_agent keys
                    # off the name) and the in_flight/done-marker tracking for this spawn - deny before
                    # 70 minutes of unguarded work are spent under the wrong identity.
                    deny(f"spawn name {spawn_name!r} does not match the brief's AGENT NAME {bfields['agent']!r} ({m.group(1)}) - spawn with name=\"{bfields['agent']}\".")
                wanted = brief_runtime(bp); got = str(ti.get("model") or "").split("[")[0]
                if wanted.get("model"):
                    # MODEL is the Agent tool's alias; a brief rendered before the aliases pinned an id and carries SPAWN MODEL.
                    alias = wanted.get("spawn_model") or wanted["model"]
                    if got not in {wanted["model"], alias}: deny(f"pass model=\"{alias}\" ({'SPAWN MODEL' if alias != wanted['model'] else 'MODEL'} in {m.group(1)}); got {got!r}. Models are chosen per role for cost reasons (run.json -> models).")
    if sub:   # the board's live activity line and stall detection (engine/tools/activity.py); an allowed call only
        try: import activity; activity.record(RUN, name, INP.get("agent_id"), tool, ti); import retrieval; retrieval.stamp(RUN, name, INP.get("agent_id"), tool, ti)   # corpus calls per agent (metrics)
        except Exception as e:
            if os.environ.get("DBCX_HOOK_DEBUG"): print(f"[dbcx hook] activity not recorded: {e!r}", file=sys.stderr)
    sys.exit(0)

# ------------------------------------------------------------------ PostToolUse
def post():
    tool = NORMALIZED.tool; ti = NORMALIZED.tool_input; name, sub = agent_identity()
    if sub:   # the call's done marker (no content) - a call without one is still running (busy, not stalled)
        try: import activity; activity.record(RUN, name, INP.get("agent_id"), tool, None, end=True)
        except Exception as e:
            if os.environ.get("DBCX_HOOK_DEBUG"): print(f"[dbcx hook] activity not recorded: {e!r}", file=sys.stderr)
    if EVENT == "PostToolUseFailure": sys.exit(0)   # a failed call only closes its activity record
    if tool == "Agent":
        st = ti.get("subagent_type") or ti.get("agent_type") or ""
        if not st.startswith(common.AGENT_PREFIX): sys.exit(0)
        prompt = ti.get("prompt") or ti.get("message") or ""; m = re.search(r"(analysis[\\/]briefs[\\/][\w.\-]+\.md)", prompt)
        if not m: sys.exit(0)
        bf = brief_fields(P(m.group(1)))
        # identity comes from the BRIEF, not the spawn call - the PreToolUse check above
        # denies a mismatched spawn name, so the brief's own AGENT NAME is always the safe, stable key
        # to upsert on; a re-spawn of a delivered brief (a new round) registers again under that name.
        agent = bf.get("agent") or ti.get("name") or os.path.basename(m.group(1))[:-3]
        add = re.search(r"(analysis[\\/]briefs[\\/][\w.\-]*addendum[\w.\-]*\.md)", prompt)
        meta = jload(os.path.splitext(P(m.group(1)))[0] + ".meta.json", {}) or {}
        tr = INP.get("tool_response"); conv = (tr.get("agentId") if isinstance(tr, dict) else None) or INP.get("agent_id") or ""   # the harness's id of the spawned agent: its tool calls carry it as agent_id (activity)
        entry = {"agent": agent, "model": ti.get("model") or meta.get("model"), "provider": meta.get("provider"), "harness": meta.get("harness") or HARNESS, "reasoning_effort": meta.get("reasoning_effort"), "role": common.role_of_agent(agent, METHOD), "subagent_type": st, "conversation_id": conv, "brief_path": m.group(1), "brief_sha256": meta.get("sha256"), "addendum_path": add.group(1) if add else "", "output_files": [bf["output"].split()[0]] if bf.get("output") else [], "check_cmd": bf.get("check", "").split("  (")[0], "on_delivery": "convert with check_cmd (once), then continue per `dbcx status next`", "respawn": f"re-spawn {st} with the same brief path (a RESUME NOTE continues the file)"}
        subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "inflight", "add", json.dumps(entry)], cwd=RUN, capture_output=True, text=True)
        nt = inbox_notice()
        if nt: context(nt, "PostToolUse")
        sys.exit(0)
    if not sub:
        nt = inbox_notice()
        if nt and tool not in ("Write", "Edit", "MultiEdit"): context(nt, "PostToolUse")
    if tool in ("Write", "Edit", "MultiEdit"):
        for fp in edit_paths(NORMALIZED):
            ap = resolve_path(fp, RUN); rp = common.relp(ap, RUN)
            scope = common.scope_of_path(rp, METHOD) if rp.endswith(".md") else None
            if not scope: continue
            gd = P("analysis", "gauntlet", scope)
            if not os.path.isdir(gd): continue
            snaps = sorted(int(x.group(1)) for f in os.listdir(gd) for x in [re.match(r"claims-round(\d+)\.json", f)] if x)
            if snaps and not os.path.exists(os.path.join(gd, f"round{snaps[-1]}-result.json")):
                open(os.path.join(gd, "DIRTY"), "a", encoding="utf-8").write(f"{rp} edited by {name} while round {snaps[-1]} is open\n")
                context(f"[dbcx guardrail] {rp} changed while gauntlet round {snaps[-1]} of {scope} is OPEN (claims extracted, not yet aggregated). The critics may be scoring text that no longer exists. Tell the orchestrator exactly which claims/rows changed; the orchestrator re-runs `dbcx extract_claims {scope} --round {snaps[-1]}` (score_aggregate refuses while the DIRTY marker stands).", "PostToolUse")
    sys.exit(0)

# ------------------------------------------------------------------ SubagentStop
def _spawn_epoch(e):
    try: return time.mktime(time.strptime(e.get("spawned_at", ""), "%Y-%m-%dT%H:%M:%S"))
    except Exception: return None

def subagent_stop():
    # this must not sweep EVERY undelivered in_flight entry on ANY SubagentStop and mark an
    # entry delivered merely because its output file exists - one agent finishing would stamp every other
    # still-running agent delivered too. It judges only the agent that is
    # actually stopping, and accepts delivery only from an agent-written done marker (`dbcx status done`)
    # or a passing check_cmd on a file whose mtime is newer than the spawn (never file-existence alone).
    st = jload(P("state", "STATUS.json"), None)
    if not st: sys.exit(0)
    name, sub = agent_identity(); msgs = []; invalid_for_me = None
    e = next((x for x in (st.get("in_flight") or []) if x.get("agent") == name), None) if sub else None
    if e and not e.get("delivered"):
        outs = e.get("output_files") or []
        have = bool(outs) and all(os.path.exists(P(f)) for f in outs)
        done_marker = bool(e.get("done"))
        spawn_epoch = _spawn_epoch(e)
        fresh = have and (spawn_epoch is None or any(os.path.getmtime(P(f)) > spawn_epoch for f in outs))
        ok = None; out = ""
        if have and e.get("check_cmd") and (done_marker or fresh):
            cmd = e["check_cmd"].split("  (")[0]
            if "md_to_json" in cmd and "--out" not in cmd:
                import tempfile; cmd += " --out " + common.fwd(tempfile.mktemp(suffix=".json"))
            r = common.run_cli(cmd, cwd=RUN, capture_output=True, text=True, env=dict(os.environ, PATH=os.path.join(PLUGIN, "scripts") + os.pathsep + os.environ.get("PATH", ""))); out = (r.stdout + r.stderr).strip(); ok = r.returncode == 0 and "INVALID" not in out and "REFUSED" not in out
        delivered = done_marker or (fresh and ok is True)
        if ok is False:
            msgs.append(f"{name}: output present but check FAILED: {out[-400:]}"); invalid_for_me = out
        elif delivered:
            subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "inflight", "done", name], cwd=RUN, capture_output=True, text=True)
            subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "log", f"delivery test {name}: {'done marker' if done_marker else 'check OK on a file newer than the spawn'} (SubagentStop hook)"], cwd=RUN, capture_output=True, text=True)
            msgs.append(f"{name}: DELIVERED ({'done marker' if done_marker else 'check OK'}) - marked in STATUS")
        elif have:
            msgs.append(f"{name}: output on disk but not yet accepted - call `dbcx status done {name}` as your last step (or its check_cmd has not passed on a file newer than the spawn)")
    subprocess.run([sys.executable, os.path.join(TOOLS, "progress.py"), "--quiet"], cwd=RUN, capture_output=True, text=True, timeout=30)
    nt = inbox_notice(mark=False)
    if nt: msgs.append(nt.replace("\n", " "))
    if invalid_for_me and not INP.get("stop_hook_active"):
        print(json.dumps({"decision": "block", "reason": f"[dbcx guardrail] your output file does not pass its CHECK command yet - fix it before you finish:\n{invalid_for_me[-1200:]}"})); sys.exit(0)
    output = claude_adapter.successful_stop(msgs)
    if output: print(output)
    sys.exit(0)

# ------------------------------------------------------------------ SessionStart / PreCompact
def session_start(event):
    if not os.path.exists(P("state", "STATUS.json")):
        context(f"[dbcx-agentic-loop run detected at {RUN}, method {METHOD.get('name')}] No STATUS yet: this run has not started. Read CLAUDE.md and docs/PLAN.md; `dbcx check_fill` shows what is still open.", event)
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "verify"], cwd=RUN, capture_output=True, text=True)
    dash = ""
    if event == "SessionStart":
        src = INP.get("source") or "startup"
        try:
            d = subprocess.run([sys.executable, os.path.join(TOOLS, "dashboard.py"), "serve"] + (["--no-open"] if src == "compact" else []), cwd=RUN, capture_output=True, text=True, timeout=30)
            url = subprocess.run([sys.executable, os.path.join(TOOLS, "dashboard.py"), "url"], cwd=RUN, capture_output=True, text=True, timeout=10).stdout.strip()
            dash = f"\nDashboard (live progress, the lead's answers / hints / pause land in state/INBOX.jsonl): {url} - `dbcx dashboard open` reopens it. Arm a persistent Monitor on the inbox once per session so answers wake you while you wait for agents: `tail -n0 -F state/INBOX.jsonl` (description 'dashboard inbox'). New entries: `dbcx inbox next` then `dbcx inbox apply <id>`."
        except Exception as e: dash = f"\n(dashboard not started: {e})"
    ib = inbox_notice(mark=False)
    fb = subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "feedback", "list"], cwd=RUN, capture_output=True, text=True).stdout
    open_fb = [l for l in fb.splitlines() if "OPEN" in l]
    txt = (f"[dbcx-agentic-loop run detected at {RUN}, method {METHOD.get('name')}]\nLauncher of this session: {common.CLI} - a bare `dbcx` in run files and tool output means this command (older run files may name a replaced plugin version).\nResume from disk, never from memory: read docs/RESUME.md (if present) and docs/LEARNINGS.md section F, then `dbcx status next`. "
           "Do not re-spawn an agent whose output is on disk (delivery test below). Briefs are rendered to analysis/briefs/ and spawned by path; critic files are converted once.\n"
           + (r.stdout.strip() or "") + ("\nUnprocessed user feedback:\n" + "\n".join(open_fb) if open_fb else "") + dash + ("\n" + ib if ib else ""))
    context(txt[:6000], event)

if EVENT == "PreToolUse": pre()
elif EVENT in ("PostToolUse", "PostToolUseFailure"): post()
elif EVENT == "SubagentStop": subagent_stop()
elif EVENT in ("SessionStart", "PreCompact"): session_start(EVENT)
