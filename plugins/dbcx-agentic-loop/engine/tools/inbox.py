#!/usr/bin/env python3
"""The run's inbox: what the engagement lead sent from the dashboard (or the CLI) while the loop runs - answers, hints, disputes, commands.
state/INBOX.jsonl is append-only (the dashboard server and this tool are its only writers); state/CONTROL.json holds the pause / checkpoint flags.
The PostToolUse hook tells the orchestrator about new entries after its next tool call; bounded polling (`dbcx inbox wait`) covers idle waits.

Usage: dbcx inbox list [--new]                      entries, unprocessed first
       dbcx inbox next                              the oldest unprocessed entry with the exact steps to apply it
       dbcx inbox apply <client_id|next> [--note ""]  do the deterministic part (register the answer / hint / fact), print what the orchestrator
                                                    still does by hand (SendMessage, amend round), mark the entry processed
       dbcx inbox done <client_id> "<outcome>"      mark processed without applying (the orchestrator handled it itself)
       dbcx inbox add <kind> <json>                 append an entry from the CLI (same shape as the dashboard writes)
       dbcx inbox wait --timeout <seconds>          wait a bounded time for an unprocessed entry (default 30, max 3600)
       dbcx inbox control [show | pause | resume | checkpoint | checkpoint-done | ack-pause]
Entry kinds: answer {id, option, text, weight fact|proposal} | analyst_hint {scope, claim_id?, text} | critic_fact {scope, claim_id, critic, text}
             critic_hint {scope, claim_id, critic, text} | knowledge {text, scopes?, weight?} (-> a knowledge-base candidate, never an entry)
             | keep {id} (the lead keeps the assumption: `dbcx questions keep` - closed, stays an assumption, nothing to route)
             | reopen {id} (undo a keep: `dbcx questions reopen`) | command {command: pause|resume|checkpoint}
             | gate_question_feedback {persona, question_id, round, intent dismiss|rephrase|other, text} (the lead on a gate key question: the
               orchestrator rewords, dismisses or keeps it with `dbcx gate question ... --feedback <client_id>`, which closes the entry; apply only prints the steps)
             | panel_edit {panel, row, column, action, text, reason} (an optional edit of a method panel's cell - tech-fit-estimation: an override
               of the impact matrix; apply hands it to methods/<m>/panels.py apply(entry, cfg), which records it; the next wave picks it up)
An answer or a keep to a question linked as a duplicate (`dbcx questions link`) is redirected to its primary and reaches the duplicate from there.
An answer whose id is a ruling (R-nn, `dbcx rulings`) is recorded with `dbcx rulings answer` (a knowledge-base decision; the weight is always fact).
Weights: fact = the lead knows it, client-evidence weight, binding for the critics; proposal = weighed against the client's documents by the critics.
"""
import os, sys, json, time, uuid, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, TOOLS, CLI, replace_file, INBOX_PATH, CONTROL_PATH, STATUS_PATH, load_inbox, load_control, load_json, save_json, scope_info, method, project, relp

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def append(entry):
    os.makedirs(os.path.dirname(INBOX_PATH), exist_ok=True); entry.setdefault("client_id", uuid.uuid4().hex); entry.setdefault("at", now()); entry.setdefault("processed", False); entry.setdefault("by", "lead"); entry.setdefault("channel", "cli")
    open(INBOX_PATH, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\n"); return entry
def rewrite(entries):
    tmp = INBOX_PATH + ".tmp"; open(tmp, "w", encoding="utf-8").write("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries)); replace_file(tmp, INBOX_PATH)
def mark(client_id, note):
    entries = load_inbox(); hit = False
    for e in entries:
        if e.get("client_id") == client_id: e["processed"] = True; e["processed_at"] = now(); e["outcome"] = note; hit = True
    if not hit: sys.exit(f"no inbox entry {client_id}")
    rewrite(entries)
def control(**kw):
    c = load_control(); c.update(kw); save_json(CONTROL_PATH, c); return c
def status_log(msg): subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "log", msg], cwd=ROOT, capture_output=True, text=True)
def running_agent(scope):
    st = load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}; agent = scope_info(scope, method())[4]
    for e in st.get("in_flight", []) or []:
        if not e.get("delivered") and e.get("agent") == agent: return agent
    return None
def running_critic(scope, critic):
    st = load_json(STATUS_PATH, {}) if os.path.exists(STATUS_PATH) else {}; name = f"critic-{critic}-{scope}"
    return name if any(not e.get("delivered") and e.get("agent") == name for e in st.get("in_flight", []) or []) else None
def last_round(scope):
    d = P("analysis", "gauntlet", scope)
    if not os.path.isdir(d): return 0
    rs = [int(f[5:-12]) for f in os.listdir(d) if f.startswith("round") and f.endswith("-result.json")]
    return max(rs) if rs else 0
def describe(e):
    k = e.get("kind"); t = e.get("text", "")
    if k == "answer": return f"answer to {e.get('id')}: option {e.get('option') or '-'} {t[:80]} [{e.get('weight')}]"
    if k == "command": return f"command {e.get('command')}"
    if k in ("keep", "reopen"): return f"{k} {e.get('id')}" + (": assumption kept, nothing to route" if k == "keep" else "")
    if k == "gate_question_feedback": return f"gate question feedback {e.get('persona')} {e.get('question_id')} (round {e.get('round')}, {e.get('intent')}): {t[:80]}"
    if k == "knowledge": return f"knowledge" + (f" [{', '.join(e['scopes'])}]" if e.get("scopes") else "") + f": {t[:80]}"
    if k == "panel_edit": return f"panel edit {e.get('panel')}: {e.get('row')} x {e.get('column')} {e.get('action')}" + (f": {t[:80]}" if t else "") + (f" ({e.get('reason')[:60]})" if e.get("reason") else "")
    return f"{k} {e.get('scope')}/{e.get('claim_id') or '-'}" + (f" -> critic-{e.get('critic')}" if e.get("critic") else "") + f": {t[:80]}"

def steps_for(e):
    """What applying this entry means - the deterministic part is done by `apply`, the rest is printed for the orchestrator."""
    k = e.get("kind"); out = []
    if k == "answer" and is_ruling(e.get("id")):
        out.append(f"{CLI} rulings answer {e.get('id')} \"<text>\" --channel dashboard" + (f" --option {e['option']}" if e.get("option") else "") + "   (done by apply)")
        out.append(f"the answer is a knowledge-base decision for every scope from now on; running agents: `{CLI} kb pending <agent>` before their next message")
    elif k == "answer":
        out.append(f"{CLI} questions answer {e.get('id')} \"<text>\" --by lead --weight {e.get('weight', 'proposal')} --channel dashboard" + (f" --option {e['option']}" if e.get("option") else "") + "   (done by apply)")
        out.append("then route like chat feedback: asker in an open round -> message the running agent (target state, not delta); asker final -> post-pass text correction; client question -> the Open_Questions sheet updates on the next build; an overruled assumption -> issue + rework brief; record with `dbcx questions applied <id> \"<note>\"`")
    elif k in ("keep", "reopen"):
        out.append(f"{CLI} questions {k} {e.get('id')}" + (" --channel dashboard" if k == "keep" else "") + "   (done by apply)")
        out.append("nothing to route: no SendMessage, no amend round, no re-score - the run keeps proceeding under its assumption (done by apply)" if k == "keep" else "reopened: the question is open again; answer it or keep it as usual   (done by apply)")
    elif k == "analyst_hint":
        ag = running_agent(e["scope"])
        out.append(f"appended to analysis/briefs/lead-hints-{e['scope']}.md (rendered into the next analyst brief as LEAD HINTS - hypotheses)   (done by apply)")
        out.append(f"SendMessage to {ag}: \"Lead hint (hypothesis - reproduce before adopting)" + (f" on {e['claim_id']}" if e.get("claim_id") else "") + f": {e.get('text', '')}\"" if ag else f"no analyst of {e['scope']} is running - the hint reaches the next rework brief automatically")
    elif k == "critic_fact":
        n = last_round(e["scope"]); cr = e.get("critic", "standard"); ag = running_critic(e["scope"], cr)
        out.append(f"appended to analysis/briefs/lead-facts-{e['scope']}.md (rendered into every critic brief of the scope as LEAD FACTS - binding)" + (" + reference row with provenance lead" if cr.startswith("standard") else "") + "   (done by apply)")
        target = ag or f"critic-{cr}-{e['scope']}"
        out.append(f"SendMessage to {target}" + ("" if ag else " (re-spawn it from its round brief first)") + f": \"LEAD FACT (binding for this engagement, overrules your source): {e.get('text', '')}. Re-score {e.get('claim_id')} of round {n} against it in analysis/gauntlet/{e['scope']}/round{n}-{cr}-amend.md (template critic-scores.md, ONLY that row; keep issue text, note the fact id).\"")
        out.append(f"{CLI} md_to_json critic analysis/gauntlet/{e['scope']}/round{n}-{cr}-amend.md  ->  {CLI} score_aggregate {e['scope']} {n} --amend {cr}   (recomputes round {n}; PASS = stop the reworking analyst (TaskStop) and mark the scope passed; FAIL = tell the analyst to leave {e.get('claim_id')} unchanged)")
    elif k == "critic_hint":
        cr = e.get("critic", "standard"); ag = running_critic(e["scope"], cr)
        target = ag or f"critic-{cr}-{e['scope']}"
        out.append(f"SendMessage to {target}: \"Lead asks you to re-check your evidence on {e.get('claim_id')}: {e.get('text', '')}. Your score stays yours; if your source proves wrong, say so in the next round's issue text.\"")
    elif k == "gate_question_feedback":
        per, qid, r = e.get("persona"), e.get("question_id"), e.get("round"); cid = e.get("client_id", "")[:8]
        x = next((q for q in load_json(f"analysis/gate/round{r}-{per}.json", {}).get("questions", []) if q.get("question_id") == qid), {})
        out.append(f"read {per}'s round {r} answer to {qid}: score {x.get('score', '-')}; answer: {x.get('answer') or '-'}; why not higher: {x.get('rationale') or '-'} (analysis/gate/round{r}-{per}.json)")
        out.append(f"the lead ({e.get('intent')}): {e.get('text', '')}")
        out.append("decide: reword (the question asks the wrong thing - write a better question yourself, NEVER paste the lead's wording) | dismiss (answered outside this study) | keep (unchanged, say why); the change applies from the next round whose persona briefs are not rendered yet")
        out.append(f"{CLI} gate question {per} {qid} --reword \"<your question>\" --why \"<reason>\" --feedback {cid}  |  --dismiss --why \"<reason>\" --feedback {cid}  |  --keep --why \"<reason>\" --feedback {cid}   (closes this entry)")
    elif k == "panel_edit":
        out.append("recorded by the method's panel (tech-fit-estimation: an override record in state/impact.json; the changed work package is marked for the next wave)   (done by apply)")
    elif k == "knowledge":
        out.append("registered as a knowledge-base candidate KC-n (source inbox)   (done by apply)")
        out.append(f"{CLI} kb promote KC-n --text \"<one statement in your words>\" --topic <topic> --applies-to <a,b|*>  or  {CLI} kb reject KC-n --reason \"...\" (single-scope knowledge stays a lead hint / lead fact)")
    elif k == "command":
        c = e.get("command")
        if c == "pause": out += ["PAUSE PROTOCOL: spawn nothing new (the Agent hook denies spawns while CONTROL.pause_requested is set); let in-flight agents finish and convert their outputs; `dbcx status verify`; write docs/RESUME.md (where we are, what is owed, exact next commands); `dbcx inbox control ack-pause`; end your turn with a 5-line summary. Resume = a fresh session in the run folder ('Execute the plan'), which clears the flag via `dbcx inbox control resume`."]
        elif c == "checkpoint": out += [f"CHECKPOINT: {CLI} progress  ->  {CLI} build_excel --all --interim  ->  {CLI} render brief progress --out  -> spawn progress-reporter (writes docs/PROGRESS_REPORT.md; the dashboard renders it)  ->  {CLI} inbox control checkpoint-done"]
        elif c == "resume": out += ["resume requested: `dbcx inbox control resume` clears the pause flag; continue with `dbcx status next`"]
    return out

def is_ruling(rid):
    import rulings; return bool(rid) and rulings.find(rid) is not None

def apply(e, note=""):
    k = e.get("kind"); t = now(); done = []
    if k == "gate_question_feedback":   # a decision only the orchestrator takes: `dbcx gate question ... --feedback` closes the entry
        print(f"OPEN {describe(e)}\n  YOUR STEPS:"); [print("   -", s) for s in steps_for(e)]; print(f"  the entry stays unprocessed until `{CLI} gate question` closes it"); return
    if k == "answer" and is_ruling(e.get("id")):   # the rulings sheet answered on the dashboard
        args = [sys.executable, os.path.join(TOOLS, "rulings.py"), "answer", e["id"]] + ([e["text"]] if e.get("text") else []) + (["--option", e["option"]] if e.get("option") else []) + ["--channel", e.get("channel", "dashboard")]
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True); done.append((r.stdout + r.stderr).strip())
    elif k in ("keep", "reopen"):
        from common import load_questions
        dup = next((q.get("duplicate_of") for q in load_questions() if q.get("id") == e.get("id") and q.get("duplicate_of")), None) if k == "keep" else None
        if dup: done.append(f"redirected {e['id']} -> {dup}"); print(f"redirected {e['id']} -> {dup}"); e = dict(e, id=dup)
        args = [sys.executable, os.path.join(TOOLS, "questions.py"), k, e.get("id", "")] + (["--by", e.get("by", "lead"), "--channel", e.get("channel", "dashboard")] if k == "keep" else [])
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True); done.append((r.stdout + r.stderr).strip())
        if r.returncode: sys.exit(f"{k} {e.get('id')} failed, entry left unprocessed: {(r.stdout + r.stderr).strip()}")
    elif k == "answer":
        from common import load_questions
        dup = next((q.get("duplicate_of") for q in load_questions() if q.get("id") == e.get("id") and q.get("duplicate_of")), None)
        if dup: done.append(f"redirected {e['id']} -> {dup}"); print(f"redirected {e['id']} -> {dup}"); e = dict(e, id=dup)   # a linked duplicate is answered through its primary
        args = [sys.executable, os.path.join(TOOLS, "questions.py"), "answer", e.get("id", ""), e.get("text") or "", "--by", e.get("by", "lead"), "--weight", e.get("weight", "proposal"), "--channel", e.get("channel", "dashboard")]
        if e.get("option"): args += ["--option", e["option"]]
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True); done.append((r.stdout + r.stderr).strip())
    elif k == "analyst_hint":
        fp = P("analysis", "briefs", f"lead-hints-{e['scope']}.md"); os.makedirs(os.path.dirname(fp), exist_ok=True)
        if not os.path.exists(fp): open(fp, "w", encoding="utf-8").write(f"# Lead hints for {e['scope']} (from the engagement lead via the dashboard; every hint is a hypothesis - reproduce before adopting; never quote the lead)\n\n")
        open(fp, "a", encoding="utf-8").write(f"- {e.get('at', t)}" + (f" [{e['claim_id']}]" if e.get("claim_id") else " [scope]") + f" {e.get('text', '').strip()}\n"); done.append(f"appended to {relp(fp, ROOT)}")
    elif k == "critic_fact":
        fp = P("analysis", "briefs", f"lead-facts-{e['scope']}.md"); os.makedirs(os.path.dirname(fp), exist_ok=True)
        if not os.path.exists(fp): open(fp, "w", encoding="utf-8").write(f"# Lead facts for {e['scope']} (stated by the engagement lead; BINDING for this engagement - score against them, they overrule contradicting external or documentary sources; record the conflict in `issue`)\n\n")
        line = f"- {e.get('at', t)} [{e.get('claim_id')}, critic-{e.get('critic')}] {e.get('text', '').strip()}"
        ref = ""
        if str(e.get("critic") or "").startswith("standard"):   # standard or a per-pack standard-<pack> critic
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "reference.py"), "add", "--fact", e.get("text", "").strip(), "--applies", "this engagement (lead statement)", "--url", f"lead:{e.get('at', t)}", "--provenance", "lead", "--affects", e.get("claim_id", ""), "--by", "lead"], cwd=ROOT, capture_output=True, text=True)
            out = (r.stdout + r.stderr).strip(); ref = out; done.append("reference: " + out[-200:])
            import re as _re; m = _re.search(r"(PS-7-\d+)", out); line += f" -> {m.group(1)}" if m else ""
        open(fp, "a", encoding="utf-8").write(line + "\n"); done.append(f"appended to {relp(fp, ROOT)}")
    elif k == "knowledge":
        import kb; c = kb.candidate_from_inbox(e); done.append(f"knowledge-base candidate {c['id']}")
    elif k == "panel_edit":
        from common import load_method_module
        mod = load_method_module("panels")
        if not (mod and hasattr(mod, "apply")): sys.exit(f"panel edit {e.get('client_id', '')[:8]}: this method has no editable panel - entry left unprocessed")
        try: done.append(mod.apply(e, project()))
        except Exception as ex: sys.exit(f"panel edit {e.get('client_id', '')[:8]} refused, entry left unprocessed: {ex} - nothing changed; close it with `{CLI} inbox done {e.get('client_id', '')[:8]} \"refused: <why>\"`")
    elif k == "command":
        c = e.get("command")
        if c == "pause": control(pause_requested=True, pause_requested_at=e.get("at", t)); done.append("CONTROL.pause_requested = true (the Agent hook denies new spawns)")
        elif c == "resume": control(pause_requested=False, resumed_at=t, pause_ack_at=None, paused_at=None); done.append("pause flag cleared")
        elif c == "checkpoint": control(checkpoint_requested_at=e.get("at", t)); done.append("CONTROL.checkpoint_requested_at set")
    steps = steps_for(e)
    mark(e["client_id"], note or "; ".join(done) or "applied")
    status_log(f"inbox {e.get('kind')} {e.get('client_id', '')[:8]} applied: {describe(e)[:120]}")
    print(f"APPLIED {describe(e)}"); [print("  done:", d) for d in done if d]
    rest = [s for s in steps if "(done by apply)" not in s]
    if rest: print("  YOUR STEPS:"); [print("   -", s) for s in rest]
    elif k == "keep": print("  NOTHING TO ROUTE: no SendMessage, no amend round, no re-score")

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]; entries = load_inbox()
    if cmd == "list":
        rows = [e for e in entries if not e.get("processed")] + ([] if "--new" in a else [e for e in entries if e.get("processed")])
        for e in rows: print(f"{'NEW ' if not e.get('processed') else 'done'} {e.get('client_id', '')[:8]} {e.get('at', '')} {describe(e)}" + (f"  -> {e.get('outcome', '')[:80]}" if e.get("processed") else ""))
        if not rows: print("(inbox empty)")
    elif cmd == "wait":
        timeout = int(a[a.index("--timeout") + 1]) if "--timeout" in a else 30
        if timeout < 0 or timeout > 3600: sys.exit("--timeout must be between 0 and 3600 seconds")
        deadline = time.monotonic() + timeout
        while True:
            new = [e for e in load_inbox() if not e.get("processed")]
            if new:
                print(json.dumps(new[0], ensure_ascii=False)); return
            if time.monotonic() >= deadline:
                print("timeout: no unprocessed inbox entries"); return
            time.sleep(min(1.0, max(0.05, deadline - time.monotonic())))
    elif cmd == "next":
        new = [e for e in entries if not e.get("processed")]
        if not new: print("no unprocessed inbox entries"); return
        e = new[0]; print(f"NEXT inbox entry {e['client_id'][:8]} ({e.get('at')}): {describe(e)}"); [print("  -", s) for s in steps_for(e)]; print(f"  apply with: {CLI} inbox apply {e['client_id']}   ({len(new) - 1} more waiting)")
    elif cmd == "apply":
        new = [e for e in entries if not e.get("processed")]
        if a[1] == "next":
            if not new: print("no unprocessed inbox entries"); return
            e = new[0]
        else:
            e = next((x for x in entries if x.get("client_id", "").startswith(a[1])), None)
            if not e: sys.exit(f"no inbox entry {a[1]}")
            if e.get("processed"): sys.exit(f"{a[1]} already processed ({e.get('outcome', '')})")
        apply(e, a[a.index("--note") + 1] if "--note" in a else "")
    elif cmd == "done":
        e = next((x for x in entries if x.get("client_id", "").startswith(a[1])), None)
        if not e: sys.exit(f"no inbox entry {a[1]}")
        mark(e["client_id"], a[2] if len(a) > 2 else "handled by the orchestrator"); status_log(f"inbox {e.get('kind')} {e['client_id'][:8]} done: {a[2] if len(a) > 2 else ''}"[:200]); print("ok")
    elif cmd == "add":
        body = json.loads(a[2]); body["kind"] = a[1]; e = append(body); print(f"queued {e['client_id'][:8]} {describe(e)}")
    elif cmd == "control":
        sub = a[1] if len(a) > 1 else "show"; t = now()
        if sub == "pause": c = control(pause_requested=True, pause_requested_at=t); append({"kind": "command", "command": "pause", "channel": "cli"}); status_log("pause requested (cli)")
        elif sub == "resume": c = control(pause_requested=False, resumed_at=t, pause_ack_at=None, paused_at=None); status_log("pause cleared - resumed")
        elif sub == "ack-pause": c = control(pause_ack_at=t, paused_at=t); status_log("pause acknowledged: no new spawns, state persisted")
        elif sub == "checkpoint": c = control(checkpoint_requested_at=t); append({"kind": "command", "command": "checkpoint", "channel": "cli"})
        elif sub == "checkpoint-done": c = control(checkpoint_done_at=t, checkpoint_requested_at=None); status_log("checkpoint written (progress report + interim workbooks)")
        else: c = load_control()
        print(json.dumps(c, indent=1))
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
