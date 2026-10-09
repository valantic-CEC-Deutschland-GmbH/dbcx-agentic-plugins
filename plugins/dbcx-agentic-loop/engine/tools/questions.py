#!/usr/bin/env python3
"""Questions as state, not prose. The register is state/QUESTIONS.json (dashboard cards, Open_Questions sheet, briefs); docs/questions/<from>.md
is a rendered read-only view. Every question carries proposed answers (options) with one recommended, and the assumption the asker proceeds under.

Kinds: client_question (to = client: only the client can answer; a deliverable, never blocks the run), scope_question (to = another scope; routed by the
orchestrator), assumption (to = lead: a decision the orchestrator took that the lead may overrule), trade_off (to = lead: a choice an agent put to the orchestrator).

Usage: dbcx questions add <from> <to|client|lead> "<question>" [--id Q-x] [--kind k] [--why "..."] [--effect "which decision the answer moves"]
                          [--option "A|text|consequence" ...] [--recommend A] [--proceed A]            (repeat --option per proposed answer)
       dbcx questions import <scope>              register the open_questions rows of a scope's converted analysis (idempotent by id); parses
                                                  "Options: A) ... (recommended) B) ...; proceeding under A" from the question text; also the rows of an
                                                  `assumptions_taken` section (engine marker ASSUMPTIONS, opt-in) as client-directed assumptions: id
                                                  Q-<scope>-<row id>, option A = reading_taken (recommended, proceeding), B.. = alternatives,
                                                  `assumption` / `if_not` / `why` / `affects` from the row - never an open question
       dbcx questions answer <id> "<answer>" --by <who> [--option A] [--weight fact|proposal] [--qualification "..."] [--channel chat|dashboard|analysis]
                                                  -> answered_draft. weight fact = client-evidence weight (the lead knows it); proposal = weighed against client evidence.
                                                  An answer touching >= 2 scopes becomes a knowledge-base candidate KC-n (`dbcx kb promote|reject`)
       dbcx questions answer <id> --from-kb KB-n  answer from an active knowledge-base entry (by orchestrator, the entry's weight and type, channel kb)
       dbcx questions link <dup> <primary>        mark <dup> as a duplicate (`duplicate_of`): answering <primary> appends the same answer verbatim (channel
                                                  duplicate, same weight / type) to every linked duplicate not answered yet; the knowledge-base candidate
                                                  check unites affects/from/to over both; a linked duplicate cannot be answered directly
       dbcx questions unlink <dup>                remove the link
       dbcx questions scored <id> <round>         the round in which the answering scope's claims behind the answer passed -> answered_scored
       dbcx questions forward <id>                forwarded to the asker (only from answered_scored)
       dbcx questions applied <id> "<note>"       the orchestrator incorporated the answer (dashboard shows the note)
       dbcx questions keep <id> [--by lead] [--channel chat|dashboard]
                                                  the lead keeps the assumption: status closed, resolution "assumption_kept". No answer is added,
                                                  so the type stays what it was (an Annahme in the deliverables, never a fact or decision);
                                                  proceeding_under and any answer the run found stay as they are; nothing is re-analysed or
                                                  re-scored. Linked duplicates not answered yet are kept with it; a duplicate itself is refused
       dbcx questions reopen <id>                 undo a keep: the status the question had before it was kept (default open)
       dbcx questions edit <id> [--question "..."] [--why "..."] [--effect "..."] [--to <unit|client|lead>] [--kind k]
                          [--option "A|text|consequence" ...] [--recommend A] [--proceed A] [--note "why"]
                                                  correct the CLIENT-FACING text or the routing of a registered question (wrong language,
                                                  wrong wording, misrouted to the client). Status, answer, scored_in_round, answered_by,
                                                  qualification, affects and asked_at are left untouched; the previous values are kept in
                                                  `corrections` so a reader can see the text was corrected. Scores are never touched by this.
       dbcx questions affects <id> <a,b,c>        the scopes/deliverables an answer still moves. The dashboard marks a question SETTLED BY
                                                  ASSUMPTION once every one of them is final: answering it then corrects text, it does not reopen
                                                  a scope. No entry means unknown, and unknown counts as live - a question never falls silent
                                                  because nobody recorded what it touches.
       dbcx questions status <id> <status>        set the status directly (open|answered_draft|answered_scored|forwarded|applied), for a
                                                  correction the normal transitions do not cover.
       dbcx questions assumption <id> --text "Die Analyse geht davon aus, dass ..." [--if-not "..."]
                                                  customer wording for the Annahmen sheet (K4): `assumption` (the confirm/deny sentence) and
                                                  `if_not` (what changes when the client says no) - both empty by default, and a customer
                                                  edition must not ship the default wording.
       dbcx questions normalize-affects           fills `affects` from ids found in `effect` (FR-/TR-/NR- requirements, F- features, MT- tasks,
                                                  and any unit name in state/scopes.json) for every question whose `affects` is still empty;
                                                  reports the ones that still have none afterwards.
       dbcx questions assumptions [--assign]       --assign gives every client-directed question (to == client) a stable `assumption_id`
                                                  (A-nn) it keeps forever, in register order (the order the questions were added - not asked_at,
                                                  whose one-second resolution swapped ids between runs), idempotent (an already-assigned
                                                  question is never renumbered); without --assign, lists the current id -> assumption_id map.
       dbcx questions import-assumptions <xlsx>   reads a returned "Annahmen" sheet (columns: Nr. [=assumption_id], Annahme, Warum wir davon
                                                  ausgehen, Falls nicht zutreffend, Betroffen, Zutreffend? (<client>), Anmerkung <client>):
                                                  ja -> a client-fact answer; nein/teilweise -> a client-fact answer PLUS the row's `affects`
                                                  printed as a re-analysis list. A row with no Nr. match or an empty verdict is skipped.
       dbcx questions import-handover <file>      materialise a client-assumptions handover (`dbcx handover export client-assumptions` of an
                                                  earlier run) into this register: assumption_id (A-nn), wording, affects, options and answers[]
                                                  kept (an answer by the client stays a client fact), `imported_from` recorded; idempotent (a row
                                                  imported before only gains answers it lacks). Refused when an A-nn or a question id is already
                                                  taken by one of this run's own questions - import before assigning own ids; this run's own new
                                                  assumptions then number on after the highest imported A-nn.
       dbcx questions release --scope S[,S2] | --all
                                                  human_input.release batched: `add` and `import` store new questions with `released: false` (the
                                                  dashboard and the workbooks show released questions only); release a batch at the wave gate / phase
                                                  end `dbcx status next` names, after reviewing its `related` neighbours and linking duplicates.
                                                  --scope = the asking scope(s) (`from`). A final build refuses while a question is unreleased
       dbcx questions show <id> | list [--open | --forwardable | --client | --lead | --assumptions | --unreleased | --json] | migrate | render
Rule: an answer is forwarded only from a passed round; forward the qualification with it, or a downstream reader treats an upper bound as a count.
Related on intake: `add` and `import` rank every new question against the active knowledge-base entries and the questions of other scopes
(tf-idf cosine, locator tokens ignored) and record the top 3 with cosine >= method.json knowledge.dedup_floor (0.15) as `related: [{id, score}]`
- a proposal, no automatic action.
"""
import os, re, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, QUESTIONS_PATH, QUESTION_KINDS, SCOPES_PATH, load_questions, _legacy_questions, save_json, scope_info, method, project, TOOLS, CLI, relp

QD = P("docs", "questions")
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")

def type_of(by, weight):
    """decision | working-assumption | client-fact. `by == client` always wins - the client's own
    word is a fact regardless of how the answer was weighted before it arrived."""
    if by == "client": return "client-fact"
    return "decision" if weight == "fact" else "working-assumption"

def migrate_answers(q):
    """the legacy single `answer` becomes the first (and, until answered again, only) entry of the
    never-overwritten `answers` list; `answer` keeps being written as the LATEST entry so every older
    reader (render(), the dashboard, build_excel) still works unchanged."""
    if q.get("answers"):
        for a_ in q["answers"]: a_.setdefault("type", type_of(a_.get("by"), a_.get("weight")))
        q["answer"] = q["answers"][-1]
    else:
        legacy = q.get("answer"); q["answers"] = []
        if legacy:
            a_ = dict(legacy); a_.setdefault("type", type_of(a_.get("by"), a_.get("weight")))
            q["answers"].append(a_); q["answer"] = a_
    return q

def load():
    if not os.path.exists(QUESTIONS_PATH) and os.listdir(QD) if os.path.isdir(QD) else False: migrate(quiet=True)
    qs = load_questions() if os.path.exists(QUESTIONS_PATH) else []
    return {"questions": [migrate_answers(q) for q in qs]}
def save(reg):
    for q in reg["questions"]: q.pop("_legacy_file", None)
    save_json(QUESTIONS_PATH, reg); render(reg)
def find(reg, qid):
    q = next((x for x in reg["questions"] if x.get("id") == qid), None)
    if not q: sys.exit(f"no such question id {qid}")
    return q
def opt(a, k, d=""): return a[a.index(k) + 1] if k in a else d
def parse_affects(spec_):
    """The scopes and deliverables an answer still moves. Empty means unknown, and unknown counts as LIVE:
    a question must never fall silent because nobody recorded what it touches."""
    return [x.strip() for x in (spec_ or "").replace(";", ",").split(",") if x.strip()]
def opts_all(a, k): return [a[i + 1] for i, x in enumerate(a) if x == k and i + 1 < len(a)]
def parse_option(spec_, recommend):
    parts = [x.strip() for x in spec_.split("|")]
    key = parts[0]; text = parts[1] if len(parts) > 1 else ""; cons = parts[2] if len(parts) > 2 else ""
    rec = key == recommend or text.lower().endswith("(recommended)")
    return {"key": key, "text": re.sub(r"\s*\(recommended\)\s*$", "", text, flags=re.I), "recommended": rec, "consequence": cons}
def kind_of(to, given):
    if given:
        if given not in QUESTION_KINDS: sys.exit(f"kind must be one of {', '.join(QUESTION_KINDS)}")
        return given
    return "client_question" if to.lower() == "client" else ("trade_off" if to.lower() == "lead" else "scope_question")
def next_id(reg, frm, kind):
    pre = {"assumption": "A", "trade_off": "T"}.get(kind, "Q")
    n = sum(1 for q in reg["questions"] if q.get("from") == frm and q["id"].startswith(pre + "-")) + 1
    while any(q["id"] == f"{pre}-{frm}-{n:03d}" for q in reg["questions"]): n += 1
    return f"{pre}-{frm}-{n:03d}"

def hold(new):
    """under human_input.release batched a new question waits for `questions release`; live (the default) writes no flag at all"""
    if (project().get("human_input") or {}).get("release", "live") != "batched": return ""
    for q in new: q["released"] = False
    return f" - batched: {len(new)} unreleased until `{CLI} questions release`" if new else ""

def relate(reg, new):
    """related on intake: the top-3 tf-idf neighbours of each new question (active knowledge-base entries, questions of other
    scopes) - a proposal for the orchestrator (`questions link`, `--from-kb`), never an automatic action"""
    import kb
    for q in new:
        rel = kb.related(q, reg["questions"])
        if rel: q["related"] = rel; print(f"{q['id']}: related " + ", ".join(f"{r['id']} ({r['score']})" for r in rel) + f" - a duplicate: `{CLI} questions link {q['id']} <primary>`; answered by an entry: `{CLI} questions answer {q['id']} --from-kb KB-n`")

OPTS_RE = re.compile(r"\boptions?\s*:\s*(.+)$", re.I | re.S)
def parse_inline_options(text):
    """'... Options: A) shared tenant (recommended) B) dedicated; proceeding under A' -> (clean question, options, proceeding)."""
    m = OPTS_RE.search(text)
    if not m: return text.strip(), [], ""
    q = text[:m.start()].strip().rstrip(";,.") ; tail = m.group(1)
    proc = re.search(r"proceed(?:ing)?\s+(?:under\s+)?([A-Z])\b", tail, re.I); tail_opts = re.sub(r"[;,.]?\s*proceed(?:ing)?\s+(?:under\s+)?[A-Z]\b.*$", "", tail, flags=re.I | re.S)
    items = re.split(r"(?:^|\s)(?=[A-Z][\)\.:]\s)", tail_opts.strip())
    options = []
    for it in items:
        mm = re.match(r"([A-Z])[\)\.:]\s*(.+)$", it.strip(), re.S)
        if not mm: continue
        t = mm.group(2).strip().rstrip(";,"); rec = bool(re.search(r"\(recommended\)", t, re.I))
        options.append({"key": mm.group(1), "text": re.sub(r"\s*\(recommended\)", "", t, flags=re.I).strip(), "recommended": rec, "consequence": ""})
    if options and not any(o["recommended"] for o in options) and proc: [o.__setitem__("recommended", True) for o in options if o["key"] == proc.group(1).upper()]
    return q, options, (proc.group(1).upper() if proc else (next((o["key"] for o in options if o["recommended"]), "")))

def render(reg=None):
    reg = reg or {"questions": load_questions()}; os.makedirs(QD, exist_ok=True)
    by = {}
    for q in reg["questions"]: by.setdefault(q.get("from", "unknown"), []).append(q)
    for frm, qs in by.items():
        lines = [f"# Questions from {frm}", "", "Rendered view of state/QUESTIONS.json (edit with `dbcx questions`, never by hand).", "", "| id | kind | to | question | options | proceeding under | answered_by | scored_in_round | qualification | answer | status |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for q in qs:
            o = "; ".join(f"{x['key']}) {x['text']}" + (" (recommended)" if x.get("recommended") else "") for x in q.get("options", []))
            ans = q.get("answer") or {}; at = (f"{ans.get('option')}) " if ans.get("option") else "") + (ans.get("text") or "") + (f" [{ans.get('weight')}]" if ans else "")
            cell = lambda v: str(v or "").replace("|", "/").replace("\n", " ")
            lines.append("| " + " | ".join(cell(x) for x in [q["id"], q.get("kind"), q.get("to"), q.get("question") + (f" (why: {q['why']})" if q.get("why") else "") + (f" (effect of the answer: {q['effect']})" if q.get("effect") else ""), o, q.get("proceeding_under"), q.get("answered_by"), q.get("scored_in_round"), q.get("qualification"), at, q.get("status")]) + " |")
        open(os.path.join(QD, f"{frm}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return len(by)

def migrate(quiet=False):
    if os.path.exists(QUESTIONS_PATH): print("state/QUESTIONS.json exists - nothing to migrate") if not quiet else None; return
    legacy = _legacy_questions(); reg = {"questions": []}
    for q in legacy:
        q.pop("_legacy_file", None); q["asked_at"] = q["asked_at"] or now(); q["updated_at"] = q["updated_at"] or q["asked_at"]; reg["questions"].append(q)
    save_json(QUESTIONS_PATH, reg); render(reg)
    if not quiet: print(f"migrated {len(legacy)} question(s) from docs/questions/*.md into state/QUESTIONS.json; the Markdown files are now rendered views. Add proposed answers to open ones with `dbcx questions add` (new) or leave them - the dashboard shows them without options.")

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    os.makedirs(QD, exist_ok=True); cmd = a[0]
    if cmd == "migrate": migrate(); return
    if cmd == "render": print(f"rendered {render()} file(s) under docs/questions/"); return
    reg = load()
    if cmd == "add":
        frm, to, text = a[1], a[2], a[3]; kind = kind_of(to, opt(a, "--kind")); t = now()
        options = [parse_option(x, opt(a, "--recommend")) for x in opts_all(a, "--option")]
        if not options:
            text, options, proc = parse_inline_options(text)
        else: proc = opt(a, "--proceed") or next((o["key"] for o in options if o["recommended"]), "")
        qid = opt(a, "--id") or next_id(reg, frm, kind)
        if any(q["id"] == qid for q in reg["questions"]): sys.exit(f"{qid} exists")
        reg["questions"].append({"id": qid, "kind": kind, "from": frm, "to": to, "question": text, "why": opt(a, "--why"), "effect": opt(a, "--effect"), "options": options, "proceeding_under": opt(a, "--proceed") or proc,
                                 "affects": parse_affects(opt(a, "--affects")),
                                 "status": "open", "asked_at": t, "updated_at": t, "answered_by": "", "scored_in_round": "", "qualification": "", "answer": None, "answers": [],
                                 "assumption": "", "if_not": "", "assumption_id": ""})
        relate(reg, reg["questions"][-1:]); held = hold(reg["questions"][-1:]); save(reg); print(f"{qid} -> {to} ({kind}, open" + (f", {len(options)} options, proceeding under {opt(a, '--proceed') or proc}" if options else ", no options - the dashboard shows a free-text field only") + ")" + held)
    elif cmd == "import":
        scope = a[1]; js = scope_info(scope, method())[0]
        if not os.path.exists(js): sys.exit(f"{relp(js, ROOT)} missing - convert the analysis first (md_to_json)")
        rows = json.load(open(js, encoding="utf-8")).get("open_questions", []) or []; n = 0; t = now(); unrouted = []; before = len(reg["questions"])
        for r in rows:
            qid = r.get("id") or ""; to = (r.get("to") or r.get("to_unit") or "").strip()   # the unit template names the column to_unit
            if not qid or any(q["id"] == qid for q in reg["questions"]): continue
            if not to: unrouted.append(qid); continue   # never default to `client` - that turned every unrouted scope question into a client deliverable row
            text, options, proc = parse_inline_options(r.get("question", ""))
            first_answer = {"option": "", "text": r["answer"], "weight": "proposal", "by": scope, "at": t, "channel": "analysis", "status": "received", "type": type_of(scope, "proposal")} if r.get("answer") else None
            reg["questions"].append({"id": qid, "kind": kind_of(to, None), "from": scope, "to": to, "question": text, "why": r.get("why_needed") or r.get("why") or "", "effect": r.get("effect") or r.get("why_needed") or "", "options": options, "proceeding_under": proc,
                                     "affects": parse_affects(r.get("affects") or ""),   # the analyst names what the answer still moves; empty = live
                                     "status": "open" if (r.get("status") or "open") == "open" else r.get("status"), "asked_at": t, "updated_at": t, "answered_by": "", "scored_in_round": "", "qualification": "",
                                     "answer": first_answer, "answers": [first_answer] if first_answer else [], "assumption": "", "if_not": "", "assumption_id": ""}); n += 1
        taken = json.load(open(js, encoding="utf-8")).get("assumptions_taken") or []; na = 0   # lead decision 8: readings taken, registered as assumptions
        for r in taken:
            qid = f"Q-{scope}-{r.get('id') or ''}"
            if not r.get("id") or any(q["id"] == qid for q in reg["questions"]): continue
            opts = [{"key": "A", "text": r.get("reading_taken", ""), "recommended": True, "consequence": ""}] + [{"key": chr(66 + i), "text": x, "recommended": False, "consequence": r.get("if_not", "")} for i, x in enumerate(r.get("alternatives") or [])]
            reg["questions"].append({"id": qid, "kind": "client_question", "from": scope, "to": "client", "question": r.get("question", ""), "why": r.get("why", ""), "effect": r.get("if_not", ""), "options": opts, "proceeding_under": "A",
                                     "affects": parse_affects(";".join(r["affects"]) if isinstance(r.get("affects"), list) else r.get("affects") or ""), "status": "open", "asked_at": t, "updated_at": t, "answered_by": "", "scored_in_round": "", "qualification": "",
                                     "answer": None, "answers": [], "assumption": r.get("assumption", ""), "if_not": r.get("if_not", ""), "assumption_id": ""}); na += 1
        relate(reg, reg["questions"][before:]); held = hold(reg["questions"][before:]); save(reg); print(f"imported {n} new question(s) from {scope} ({len(rows)} rows in the analysis)" + (f"; {na} new assumption(s) from its {len(taken)} assumptions_taken row(s)" if taken else "") + held)
        if unrouted: sys.exit(f"REFUSED {len(unrouted)} row(s) without a target ({', '.join(unrouted)}): fill `to_unit` (a unit name, `client` or `lead`) in the analysis and re-import - nothing defaults to the client")
    elif cmd == "answer":
        q = find(reg, a[1]); t = now(); e = None
        if q.get("duplicate_of"): sys.exit(f"REFUSED: {q['id']} is linked as a duplicate of {q['duplicate_of']} - answer {q['duplicate_of']} (the answer reaches {q['id']} verbatim) or `{CLI} questions unlink {q['id']}` first")
        if "--from-kb" in a:   # the answer is an active knowledge-base entry - its weight and type travel with it
            import kb; e = kb.find_entry(opt(a, "--from-kb"))
            if not e or e.get("status") != "active": sys.exit(f"REFUSED: {opt(a, '--from-kb')} is no active knowledge-base entry")
        w = e["weight"] if e else opt(a, "--weight", "proposal")
        if w not in ("fact", "proposal"): sys.exit("--weight fact|proposal")
        by = "orchestrator" if e else opt(a, "--by", "lead")
        entry = {"option": opt(a, "--option"), "text": e["text"] if e else a[2], "weight": w, "by": by, "at": t, "channel": "kb" if e else opt(a, "--channel", "chat"), "status": "received", "type": e["type"] if e else type_of(by, w)}
        if e: entry["kb"] = e["id"]
        q.setdefault("answers", []).append(entry); q["answer"] = entry   # answers[] is never overwritten; `answer` mirrors the latest
        if q.pop("resolution", None): q.pop("kept", None)   # an answer after a keep replaces the keep
        q.update({"answered_by": by if e else opt(a, "--by", q.get("answered_by") or "lead"), "qualification": opt(a, "--qualification", q.get("qualification", "") or ("client-evidence weight (lead states it as fact)" if w == "fact" else "proposal - weigh against client evidence")), "status": "answered_draft", "updated_at": t})
        dups = [x for x in reg["questions"] if x.get("duplicate_of") == q["id"]]
        for d in dups:   # §4: a linked duplicate that is not answered yet gets the same answer verbatim
            if d.get("answers"): continue
            de = dict(entry, channel="duplicate", duplicate_of=q["id"]); d["answers"] = [de]; d["answer"] = de
            d.update({"answered_by": q["answered_by"], "qualification": q["qualification"], "status": "answered_draft", "updated_at": t}); print(f"{d['id']}: answered_draft (duplicate of {q['id']}, same answer)")
        save(reg); print(f"{q['id']}: answered_draft ({w}, type {entry['type']}, {len(q['answers'])} answer(s) on record; qualification: {q['qualification']})")
        if not e:
            import kb; c = kb.candidate_from_answer(q, entry, dups)
            if c: print(f"{c['id']}: knowledge-base candidate (affects {', '.join(c['affects'])}) - `{CLI} kb promote {c['id']} --text \"<one statement>\" --topic <topic> --applies-to <a,b|*>` or `{CLI} kb reject {c['id']} --reason \"...\"`")
    elif cmd == "link":
        d, pq = find(reg, a[1]), find(reg, a[2])
        if d["id"] == pq["id"] or pq.get("duplicate_of"): sys.exit(f"REFUSED: link a duplicate to a primary that is not itself a duplicate ({pq['id']} -> {pq.get('duplicate_of') or pq['id']})")
        if any(x.get("duplicate_of") == d["id"] for x in reg["questions"]): sys.exit(f"REFUSED: {d['id']} is the primary of other duplicates - link those to {pq['id']} first")
        d["duplicate_of"] = pq["id"]; d["updated_at"] = now(); save(reg); print(f"{d['id']}: duplicate of {pq['id']}" + (" (already answered - keeps its own answers)" if d.get("answers") else " - the next answer to " + pq["id"] + " reaches it verbatim"))
    elif cmd == "unlink":
        d = find(reg, a[1])
        if not d.pop("duplicate_of", None): sys.exit(f"{d['id']} is not linked")
        d["updated_at"] = now(); save(reg); print(f"{d['id']}: unlinked")
    elif cmd == "scored":
        q = find(reg, a[1]); q.update({"scored_in_round": a[2], "status": "answered_scored", "updated_at": now()}); save(reg); print(f"{q['id']}: answered_scored")
    elif cmd == "forward":
        q = find(reg, a[1])
        if q.get("status") != "answered_scored": sys.exit(f"REFUSED: {q['id']} is {q.get('status')} - forward only from a passed round (answered_scored). If the asker is already final, apply the answer as a post-pass text correction and record it in FINAL_REPORT.")
        q.update({"status": "forwarded", "updated_at": now()}); save(reg); print(f"{q['id']}: forwarded" + (f" (qualification: {q['qualification']})" if q.get("qualification") else ""))
    elif cmd == "affects":
        q = find(reg, a[1]); q["affects"] = parse_affects(" ".join(a[2:])); q["updated_at"] = now(); save(reg)
        print(f"{q['id']}: affects {', '.join(q['affects']) or '(unknown - counts as live)'}")
    elif cmd == "status":
        q = find(reg, a[1]); newstatus = a[2]
        known = ("open", "answered_draft", "answered_scored", "forwarded", "applied", "closed")
        if newstatus not in known: print(f"note: {newstatus!r} is not one of the usual statuses ({', '.join(known)}) - set anyway")
        q["status"] = newstatus; q["updated_at"] = now(); save(reg); print(f"{q['id']}: status -> {newstatus}")
    elif cmd == "assumption":
        q = find(reg, a[1])
        if "--text" not in a and "--if-not" not in a: sys.exit('dbcx questions assumption <id> --text "..." [--if-not "..."]')
        if "--text" in a: q["assumption"] = opt(a, "--text")
        if "--if-not" in a: q["if_not"] = opt(a, "--if-not")
        q["updated_at"] = now(); save(reg)
        print(f"{q['id']}: assumption wording set" + (", if_not set" if "--if-not" in a else ""))
    elif cmd == "normalize-affects":
        req = re.compile(r"\b(?:FR|TR|NR)-\d+\b"); feat = re.compile(r"\bF-\d+\b"); task = re.compile(r"\bMT-\d+\b")
        units = []
        try: units = sorted((json.load(open(SCOPES_PATH, encoding="utf-8")).get("scopes") or {}).keys(), key=len, reverse=True)
        except Exception: pass
        filled = 0; still_none = []
        for q in reg["questions"]:
            if q.get("affects"): continue
            text = q.get("effect") or ""
            found = sorted(set(req.findall(text)) | set(feat.findall(text)) | set(task.findall(text)) | {u for u in units if len(u) > 2 and re.search(r"(?<![\w.-])" + re.escape(u) + r"(?![\w.-])", text)})
            if found: q["affects"] = found; q["updated_at"] = now(); filled += 1
            else: still_none.append(q["id"])
        save(reg); print(f"normalize-affects: filled {filled} question(s) from `effect`")
        if still_none: print(f"still no affects ({len(still_none)}): {', '.join(still_none)}")
    elif cmd == "assumptions":
        client_qs = [q for q in reg["questions"] if q.get("to", "").lower() == "client"]
        if "--assign" in a:
            existing = [int(m.group(1)) for q in client_qs for m in [re.match(r"A-(\d+)$", q.get("assumption_id") or "")] if m]
            nxt = max(existing, default=0) + 1
            pending = [q for q in client_qs if not q.get("assumption_id")]   # register order: deterministic, asked_at ties within a second
            for q in pending: q["assumption_id"] = f"A-{nxt:02d}"; q["updated_at"] = now(); nxt += 1
            save(reg); print(f"assigned {len(pending)} new assumption id(s); {len(client_qs)} client-directed question(s) total")
        else:
            for q in sorted(client_qs, key=lambda q: (q.get("assumption_id") or "~", q["id"])):
                print(f"{q.get('assumption_id') or '(unassigned)':14s} {q['id']:22s} {q.get('question', '')[:80]}")
    elif cmd == "import-handover":
        env = json.load(open(a[1], encoding="utf-8")); rows = (env.get("data") if isinstance(env.get("data"), dict) else env).get("assumptions")
        if env.get("artefact_type") not in (None, "client-assumptions") or not isinstance(rows, list): sys.exit(f"{a[1]} is no client-assumptions artefact (dbcx handover export client-assumptions)")
        src = {"run": env.get("run", ""), "released": env.get("released", ""), "file": os.path.basename(a[1])}
        own = {q["id"]: q for q in reg["questions"]}; aid = {q.get("assumption_id"): q["id"] for q in reg["questions"] if q.get("assumption_id")}
        clash = [f"{r['assumption_id']} ({r['id']} / this run's {aid[r['assumption_id']]})" for r in rows if aid.get(r.get("assumption_id"), r.get("id")) != r.get("id")]
        clash += [f"{r['id']} (a question of this run)" for r in rows if r.get("id") in own and not own[r["id"]].get("imported_from")]
        if clash: sys.exit("REFUSED (nothing imported): taken by this run's own questions: " + "; ".join(clash) + " - import the handover before this run assigns its own assumption ids")
        new = merged = 0; t = now()
        for r in rows:
            q = own.get(r["id"]); ans = [dict(x) for x in r.get("answers") or []]
            if q:
                have = {(x.get("by"), x.get("at"), x.get("text")) for x in q.get("answers") or []}; add = [x for x in ans if (x.get("by"), x.get("at"), x.get("text")) not in have]
                if add: q.setdefault("answers", []).extend(add); q["answer"] = q["answers"][-1]; q["updated_at"] = t; merged += 1
                continue
            reg["questions"].append({"id": r["id"], "kind": "client_question", "from": r.get("from") or "handover", "to": "client", "question": r.get("question", ""), "why": r.get("why", ""), "effect": r.get("effect", ""),
                                     "options": r.get("options") or [], "proceeding_under": r.get("proceeding_under", ""), "affects": r.get("affects") or [], "status": r.get("status") or "open", "asked_at": t, "updated_at": t,
                                     "answered_by": (ans[-1].get("by") or "") if ans else "", "scored_in_round": "", "qualification": "", "answer": ans[-1] if ans else None, "answers": ans,
                                     "assumption": r.get("assumption", ""), "if_not": r.get("if_not", ""), "assumption_id": r.get("assumption_id", ""), "imported_from": src}); new += 1
        save(reg); print(f"import-handover: {new} new assumption(s), {merged} gained answers, {len(rows) - new - merged} unchanged (from {src['run'] or src['file']})")
    elif cmd == "import-assumptions":
        import openpyxl
        path = a[1]; wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb["Annahmen"] if "Annahmen" in wb.sheetnames else wb.active
        headers = [str(c.value or "").strip() for c in next(ws.iter_rows(min_row=1, max_row=1))]
        def col(prefix): return next((i for i, h in enumerate(headers) if h.lower().startswith(prefix.lower())), None)
        ci_nr, ci_verdict, ci_note = col("Nr"), col("Zutreffend"), col("Anmerkung")
        if ci_nr is None or ci_verdict is None: sys.exit('the "Annahmen" sheet needs a "Nr." and a "Zutreffend?" column')
        by_aid = {q["assumption_id"]: q for q in reg["questions"] if q.get("assumption_id")}
        from common import labels, fmt
        client = fmt(labels().get("basis_client", "")).strip()   # "Angabe <client>", the label the deliverables cite a client answer with
        confirmed = 0; reanalysis = []
        for row in ws.iter_rows(min_row=2):
            nr = str(row[ci_nr].value or "").strip()
            if not nr or nr not in by_aid: continue
            verdict = str(row[ci_verdict].value or "").strip().lower()
            if verdict not in ("ja", "nein", "teilweise"): continue
            q = by_aid[nr]; note = str(row[ci_note].value or "").strip() if ci_note is not None and row[ci_note].value else ""; t = now()
            entry = {"option": "", "text": note or f"{client}: {verdict}.", "weight": "fact", "by": "client", "at": t, "channel": "import-assumptions", "status": "received", "type": "client-fact"}
            q.setdefault("answers", []).append(entry); q["answer"] = entry
            q.update({"answered_by": "client", "status": "answered_draft", "updated_at": t})
            if verdict == "ja": confirmed += 1
            else: reanalysis.append((q["id"], nr, verdict, q.get("affects") or []))
        save(reg); print(f"import-assumptions: {confirmed} confirmed (ja), {len(reanalysis)} need re-analysis (nein/teilweise)")
        if reanalysis:
            print("re-analysis list:")
            for qid, nr, verdict, affects in reanalysis:
                print(f"  {nr} ({qid}) [{verdict}] affects: {', '.join(affects) if affects else '(none recorded - run normalize-affects first)'}")
    elif cmd == "applied":
        q = find(reg, a[1]); t = now()
        upd = {"status": "applied", "applied_at": t, "applied_note": a[2] if len(a) > 2 else ""}
        if q.get("answer"): q["answer"].update(upd)
        if q.get("answers"): q["answers"][-1].update(upd)   # keep `answer` and the list's latest entry in sync (they may be separate dicts after a JSON round-trip)
        if q.get("status") in ("open", "answered_draft"): q["status"] = "applied"
        q["updated_at"] = t; save(reg); print(f"{q['id']}: applied")
    elif cmd == "keep":   # the lead keeps the assumption: closed, no answer added, nothing to route
        q = find(reg, a[1]); t = now()
        if q.get("duplicate_of"): sys.exit(f"REFUSED: {q['id']} is linked as a duplicate of {q['duplicate_of']} - keep {q['duplicate_of']} (it reaches {q['id']}) or `{CLI} questions unlink {q['id']}` first")
        if q.get("status") == "closed": sys.exit(f"{q['id']} is already closed ({q.get('resolution', '')}) - `{CLI} questions reopen {q['id']}` first")
        kept = {"at": t, "by": opt(a, "--by", "lead"), "channel": opt(a, "--channel", "chat")}
        dups = [x for x in reg["questions"] if x.get("duplicate_of") == q["id"] and not x.get("answers") and x.get("status") != "closed"]
        for x in [q] + dups:
            x.update({"kept": dict(kept, status_before=x.get("status") or "open", **({"via": q["id"]} if x is not q else {})), "resolution": "assumption_kept", "status": "closed", "updated_at": t})
        save(reg); print(f"{q['id']}: closed - assumption kept (proceeding under {q.get('proceeding_under') or '-'}, {len(q.get('answers') or [])} answer(s) on record unchanged)" + "".join(f"\n{d['id']}: closed (duplicate of {q['id']})" for d in dups))
    elif cmd == "reopen":
        q = find(reg, a[1]); t = now()
        if q.get("status") != "closed" or not q.get("kept"): sys.exit(f"REFUSED: {q['id']} is {q.get('status')} - only a kept question can be reopened")
        for x in [q] + [x for x in reg["questions"] if (x.get("kept") or {}).get("via") == q["id"] and x.get("status") == "closed"]:
            k = x.pop("kept"); x.pop("resolution", None); x.setdefault("reopened", []).append({"at": t, "kept_at": k.get("at")}); x.update({"status": k.get("status_before") or "open", "updated_at": t}); print(f"{x['id']}: reopened ({x['status']})")
        save(reg)
    elif cmd == "edit":
        # The client-facing wording and the routing of a registered question are correctable; its
        # scoring history is not. Status, answer, scored_in_round, answered_by, qualification,
        # affects, asked_at and from stay exactly as they were.
        q = find(reg, a[1]); t = now(); before = json.loads(json.dumps(q)); changed = []
        if "--question" in a: q["question"] = opt(a, "--question")
        if "--why" in a: q["why"] = opt(a, "--why")
        if "--effect" in a: q["effect"] = opt(a, "--effect")
        if "--to" in a:
            q["to"] = opt(a, "--to")
            # routing decides the kind unless the caller pins it: a question moved off `client`
            # becomes a scope_question and stops being a deliverable row.
            q["kind"] = kind_of(q["to"], opt(a, "--kind"))
        elif "--kind" in a:
            q["kind"] = kind_of(q.get("to", ""), opt(a, "--kind"))
        if opts_all(a, "--option"):
            q["options"] = [parse_option(x, opt(a, "--recommend")) for x in opts_all(a, "--option")]
        if "--proceed" in a: q["proceeding_under"] = opt(a, "--proceed")
        elif opts_all(a, "--option"): q["proceeding_under"] = next((o["key"] for o in q["options"] if o["recommended"]), q.get("proceeding_under", ""))
        for f in ("question", "why", "effect", "to", "kind", "options", "proceeding_under"):
            if before.get(f) != q.get(f): changed.append(f)
        if not changed: sys.exit(f"REFUSED: nothing to change on {q['id']} - pass at least one of --question --why --effect --to --kind --option --proceed")
        q.setdefault("corrections", []).append({"at": t, "fields": changed, "note": opt(a, "--note"), "was": {f: before.get(f) for f in changed}})
        q["updated_at"] = t; save(reg)
        print(f"{q['id']}: corrected {', '.join(changed)} (status {q.get('status')} unchanged, answer and scores untouched)"
              + (f" -> now {q['kind']} to {q['to']}" if ("to" in changed or "kind" in changed) else ""))
    elif cmd == "release":
        un = [q for q in reg["questions"] if q.get("released") is False]; sc = set(parse_affects(",".join(opts_all(a, "--scope"))))
        if "--all" not in a and not sc: sys.exit(f"{CLI} questions release --scope S[,S2] | --all")
        sel = un if "--all" in a else [q for q in un if q.get("from") in sc]; t = now()
        for q in sel: q.update({"released": True, "released_at": t})
        save(reg); unlinked = [q["id"] for q in sel if q.get("related") and not q.get("duplicate_of")]
        print(f"released {len(sel)} question(s); {len(un) - len(sel)} still unreleased" + (f"; with `related` neighbours and no link (reviewed?): {', '.join(unlinked)}" if unlinked else ""))
    elif cmd == "show":
        print(json.dumps(find(reg, a[1]), indent=1, ensure_ascii=False))
    elif cmd == "list":
        rows = reg["questions"]
        if "--assumptions" in a:
            for q in [q for q in rows if q.get("to", "").lower() == "client"]:
                wording = "custom" if q.get("assumption") else "default"
                print(f"{q['id']:22s} {q.get('assumption_id') or '-':8s} wording={wording:8s} if_not={'set' if q.get('if_not') else 'missing'}  {q.get('question', '')[:60]}")
            return
        if "--open" in a: rows = [q for q in rows if q.get("status") == "open"]
        if "--forwardable" in a: rows = [q for q in rows if q.get("status") == "answered_scored"]
        if "--client" in a: rows = [q for q in rows if q.get("to", "").lower() == "client"]
        if "--lead" in a: rows = [q for q in rows if q.get("to", "").lower() == "lead"]
        if "--unreleased" in a: rows = [q for q in rows if q.get("released") is False]
        if "--json" in a: print(json.dumps(rows, indent=1, ensure_ascii=False)); return
        for q in rows: print(f"{q['id']:26s} {q.get('status', ''):15s} {q.get('kind', ''):15s} {q.get('from', ''):22s} -> {q.get('to', ''):14s} {q.get('question', '')[:70]}" + (f"  [{len(q.get('options', []))} opt, rec {next((o['key'] for o in q.get('options', []) if o.get('recommended')), '-')}]" if q.get("options") else ""))
        if not rows: print("(no questions match)")
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
