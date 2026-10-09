#!/usr/bin/env python3
"""Rulings intake: the lead's cross-cutting decisions, collected in ONE sitting before the
first wave instead of questions arriving one by one during claim creation. state/RULINGS.json is the sheet (written only by this tool);
docs/RULINGS.md is a rendered read-only view; the dashboard shows the rulings as cards (filter Rulings) and its answers come back through
the inbox (`dbcx inbox apply` -> `rulings answer`). Every answer becomes a knowledge-base entry, so every later brief carries it.

Usage: dbcx rulings draft                         scaffold the sheet: topics from the method snippet `rulings_topics` ("topic: summary; ..."),
                                                  seeds from the inventory analysis (the corpus index when the method has none or it is not
                                                  converted yet), the scopes, the core knowledge-base entries and engagement.rules - never ask
                                                  what they already settle. Idempotent (a drafted sheet keeps its rulings)
       dbcx rulings add "<question>" --topic X [--topic-summary S] --option "A|text|consequence" ... --recommend A [--why "..."]
                                                  one cross-cutting decision question R-nn (target platforms, legacy systems and their end, scope
                                                  boundaries, integration principles, naming conventions); at least two options and a recommendation.
                                                  Fill 10-25. Topic kebab-case; a topic neither seeded nor in the knowledge base needs --topic-summary
       dbcx rulings show [R-nn]                   the sheet, or one ruling as JSON
       dbcx rulings answer R-nn ["<answer>"] [--option A] [--statement "<one statement>"] [--channel chat|dashboard]
                                                  the lead's answer -> knowledge-base entry type decision, core, applies_to *, by lead, weight fact,
                                                  topic = the ruling's topic, text = --statement (else "<question> -> <answer>"); answering again
                                                  (also after `done`) supersedes the ruling's previous entry
       dbcx rulings done                          close the sheet: every unanswered ruling -> knowledge-base entry type working-assumption with the
                                                  recommendation (core, applies_to *, by orchestrator, weight proposal)
       dbcx rulings skip --reason "..."           no rulings round for this run (recorded); answered rulings stay in the knowledge base
`dbcx status next` holds the first wave (a method without a scopes phase: the first gauntlet) until the sheet is done or skipped when
run.json human_input.rulings is `required`; with `optional` (the engine default) it prints a recommendation line only.
"""
import os, re, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, CLI, CORPUS_DIR, SCOPES_PATH, load_json, save_json, method, project, snippets, scope_info, relp

PATH = P("state", "RULINGS.json"); MD = P("docs", "RULINGS.md")
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def opt(a, k, d=""): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
def load(): return load_json(PATH, {}) if os.path.exists(PATH) else {}
def find(rid, sheet=None): return next((r for r in (sheet if sheet is not None else load()).get("rulings", []) if r.get("id") == rid), None)
def rel(p): return relp(p, ROOT)

def parse_topics(text):
    """'platforms: target platforms and legacy systems; master-data: ...' -> {topic: {summary}}"""
    out = {}
    for part in (text or "").split(";"):
        k, _, s = part.partition(":")
        if k.strip(): out[k.strip()] = {"summary": s.strip()}
    return out

def seeds():
    """what the orchestrator drafts from: the converted inventory, else the corpus index; the scopes; what is already settled"""
    m = method(); out = {}; inv = m.get("inventory")
    js = scope_info(inv["scope"], m)[0] if inv else None
    if js and os.path.exists(js):
        d = load_json(js, {}); out["inventory"] = rel(js) + " (" + ", ".join(f"{k} {len(v)}" for k, v in d.items() if isinstance(v, list) and v and isinstance(v[0], dict)) + ")"
    else:
        idx = load_json(os.path.join(CORPUS_DIR, "index.json"), {}) if os.path.exists(os.path.join(CORPUS_DIR, "index.json")) else {}
        out["corpus"] = f"{rel(os.path.join(CORPUS_DIR, 'index.json'))} ({len(idx.get('sources') or {})} sources)" if idx else "(no corpus index - `dbcx corpus index`)"
    if os.path.exists(SCOPES_PATH): out["scopes"] = f"{rel(SCOPES_PATH)} ({len((load_json(SCOPES_PATH, {}) or {}).get('scopes') or {})} scopes)"
    import kb; out["kb_core"] = [e["id"] for e in kb.active(kb.load()) if e.get("core")]
    out["engagement_rules"] = len((project().get("engagement") or {}).get("rules") or [])
    return out

def render(sheet):
    st = sheet.get("status", "-"); rs = sheet.get("rulings", [])
    lines = ["# Rulings", "", "Rendered view of state/RULINGS.json (edit with `dbcx rulings`, never by hand). Cross-cutting decisions the lead answers in one sitting; every answer becomes a knowledge-base entry (decision, applies to every scope).", "",
             f"Status: **{st}**" + (f" ({sheet['skip_reason']})" if sheet.get("skip_reason") else "") + f" · {sum(1 for r in rs if r['status'] == 'answered')} of {len(rs)} answered", ""]
    lines += ["Seeds: " + "; ".join(f"{k}: {(', '.join(v) or '-') if isinstance(v, list) else v}" for k, v in (sheet.get("seeds") or {}).items()), ""]
    cell = lambda v: str(v or "").replace("|", "/").replace("\n", " ")
    for t, tv in (sheet.get("topics") or {}).items():
        mine = [r for r in rs if r["topic"] == t]
        lines += [f"## {t}" + (f" - {tv.get('summary')}" if tv.get("summary") else ""), ""]
        if not mine: lines += ["(no ruling yet)", ""]; continue
        lines += ["| id | question | options | answer | status | KB |", "|---|---|---|---|---|---|"]
        for r in mine:
            a = (r.get("answers") or [None])[-1] or {}
            lines.append("| " + " | ".join(cell(x) for x in [r["id"], r["question"] + (f" (why: {r['why']})" if r.get("why") else ""), "; ".join(f"{o['key']}) {o['text']}" + (" (recommended)" if o.get("recommended") else "") for o in r["options"]),
                                                          (f"{a.get('option')}) " if a.get("option") else "") + (a.get("text") or ""), r["status"], r.get("kb")]) + " |")
        lines.append("")
    os.makedirs(os.path.dirname(MD), exist_ok=True); open(MD, "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    return "\n".join(lines)

def save(sheet): save_json(PATH, sheet); render(sheet)

def next_line(sheet=None):
    """the rulings step as `status next` prints it"""
    s = sheet if sheet is not None else load(); rs = s.get("rulings", [])
    if not s: return f"`{CLI} rulings draft`, then 10-25 cross-cutting questions with options and a recommendation (`{CLI} rulings add`), the lead answers them in one sitting (dashboard filter Rulings, or chat -> `{CLI} rulings answer`), `{CLI} rulings done` - or `{CLI} rulings skip --reason \"...\"`"
    if not rs: return f"sheet drafted, no ruling yet: fill 10-25 with `{CLI} rulings add` (seeds: docs/RULINGS.md)"
    n = sum(1 for r in rs if r["status"] == "answered")
    return f"{n} of {len(rs)} ruling(s) answered - the lead answers on the dashboard (filter Rulings) or in chat (`{CLI} rulings answer`); then `{CLI} rulings done` (unanswered -> working assumptions with the recommendation)"

def cards():
    """the rulings as question-shaped cards for the dashboard (kind ruling, to lead); none for a skipped sheet"""
    s = load(); out = []
    if s.get("status") == "skipped": return out
    for r in s.get("rulings", []):
        a = (r.get("answers") or [None])[-1]
        if r["status"] == "assumed": a = {"option": r["recommend"], "text": "working assumption: the recommendation", "weight": "proposal", "by": "orchestrator", "at": r["updated_at"], "status": "received"}
        out.append({"id": r["id"], "kind": "ruling", "from": "rulings", "to": "lead", "question": r["question"], "why": r.get("why", ""), "effect": f"becomes a knowledge-base entry (decision, core, applies to every scope; topic {r['topic']})",
                    "options": r["options"], "proceeding_under": r["recommend"], "affects": [], "status": "open" if r["status"] == "open" else "applied", "asked_at": r["asked_at"], "updated_at": r["updated_at"],
                    "answer": dict(a, weight=a.get("weight", "fact")) if a else None, "answers": r.get("answers") or []})
    return out

def kb_entry(sheet, r, text, typ, weight, by, t):
    import kb
    k = kb.load(); prev = r.get("kb") if (kb.find_entry(r.get("kb"), k) or {}).get("status") == "active" else None
    summary = ((sheet.get("topics") or {}).get(r["topic"]) or {}).get("summary") or r["topic"]
    e = kb.add_entry(k, text, r["topic"], ["*"], typ, weight, by, {"kind": "ruling", "ref": r["id"], "by": by, "at": t}, "" if r["topic"] in (k.get("topics") or {}) else summary, core=True, supersedes=prev)
    kb.save(k); r["kb"] = e["id"]; return e

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]; s = load()
    if cmd == "draft":
        tp = parse_topics(snippets().get("rulings_topics", "")); fresh = not s
        s = s or {"status": "draft", "drafted_at": now(), "topics": {}, "rulings": []}
        if s["status"] != "draft": sys.exit(f"REFUSED: the rulings sheet is {s['status']} - nothing to draft")
        for k, v in tp.items(): s["topics"].setdefault(k, v)
        s["seeds"] = seeds(); save(s)
        print(("drafted" if fresh else "re-seeded") + f" {rel(PATH)} + {rel(MD)}: {len(s['topics'])} topic(s) ({', '.join(s['topics']) or 'none - the method has no rulings_topics snippet'}), {len(s['rulings'])} ruling(s)")
        print("seeds: " + "; ".join(f"{k}: {(', '.join(v) or '-') if isinstance(v, list) else v}" for k, v in s["seeds"].items()))
        print(f"NEXT: read the seeds (not the client's raw material beyond the inventory / index), then 10-25 cross-cutting questions with `{CLI} rulings add \"...\" --topic X --option \"A|text|consequence\" --option \"B|...\" --recommend A` - no question the core entries or engagement.rules already settle")
    elif cmd == "add":
        if s.get("status") != "draft": sys.exit(f"REFUSED: " + (f"the rulings sheet is {s['status']}" if s else f"no rulings sheet - `{CLI} rulings draft` first"))
        import kb
        from questions import parse_option, opts_all
        text = a[1] if len(a) > 1 and not a[1].startswith("--") else ""; topic = opt(a, "--topic"); rec = opt(a, "--recommend")
        options = [parse_option(x, rec) for x in opts_all(a, "--option")]
        if not text.strip(): sys.exit("REFUSED: the question is empty")
        if not kb.TOPIC_RE.match(topic): sys.exit(f"REFUSED: --topic {topic!r} must be kebab-case (e.g. master-data)")
        if topic not in s["topics"] and topic not in (kb.load().get("topics") or {}) and not opt(a, "--topic-summary"): sys.exit(f"REFUSED: {topic} is a new topic - pass --topic-summary \"one line\"")
        if len(options) < 2 or sum(1 for o in options if o["recommended"]) != 1: sys.exit("REFUSED: a ruling needs at least two --option \"A|text|consequence\" and exactly one --recommend")
        if opt(a, "--topic-summary"): s["topics"].setdefault(topic, {"summary": opt(a, "--topic-summary")})
        else: s["topics"].setdefault(topic, {"summary": ((kb.load().get("topics") or {}).get(topic) or {}).get("summary", "")})
        n = max([int(r["id"][2:]) for r in s["rulings"]] + [0]) + 1; t = now()
        r = {"id": f"R-{n:02d}", "topic": topic, "question": text.strip(), "why": opt(a, "--why"), "options": options, "recommend": next(o["key"] for o in options if o["recommended"]),
             "status": "open", "answers": [], "kb": None, "asked_at": t, "updated_at": t}
        s["rulings"].append(r); save(s); print(f"{r['id']} [{topic}] {len(options)} options, recommended {r['recommend']} ({len(s['rulings'])} ruling(s) on the sheet)")
    elif cmd == "show":
        if not s: print(f"(no rulings sheet - {next_line(s)})"); return
        if len(a) > 1: print(json.dumps(find(a[1], s) or sys.exit(f"no such ruling {a[1]}"), indent=1, ensure_ascii=False)); return
        print(render(s))
        if not 10 <= len(s.get("rulings", [])) <= 25 and s.get("status") == "draft": print(f"note: {len(s.get('rulings', []))} ruling(s) - the sheet is meant for 10-25 cross-cutting questions")
    elif cmd == "answer":
        r = find(a[1], s) if len(a) > 1 else None
        if not r: sys.exit(f"no such ruling {a[1] if len(a) > 1 else ''}")
        if s.get("status") == "skipped": sys.exit("REFUSED: the rulings sheet was skipped - record the decision with `dbcx kb add ... --by lead`")
        o = opt(a, "--option"); text = a[2] if len(a) > 2 and not a[2].startswith("--") else ""
        ot = next((x["text"] for x in r["options"] if x["key"] == o), None)
        if o and ot is None: sys.exit(f"REFUSED: {r['id']} has no option {o} ({', '.join(x['key'] for x in r['options'])})")
        if not (o or text.strip()): sys.exit("REFUSED: choose --option or give the answer text")
        t = now(); ans = "; ".join(x for x in (ot, text.strip()) if x)
        e = kb_entry(s, r, opt(a, "--statement") or f"{r['question']} -> {ans}", "decision", "fact", "lead", t)
        r["answers"].append({"option": o, "text": text.strip(), "by": "lead", "weight": "fact", "at": t, "channel": opt(a, "--channel", "chat"), "kb": e["id"]})
        r.update({"status": "answered", "updated_at": t}); save(s)
        print(f"{r['id']}: answered ({ans[:80]}) -> {e['id']} [decision · fact, core, applies to *]" + (f"; {e['supersedes']} superseded" if e.get("supersedes") else ""))
    elif cmd == "done":
        if s.get("status") != "draft": sys.exit("REFUSED: " + (f"the rulings sheet is already {s['status']}" if s else f"no rulings sheet - `{CLI} rulings draft` or `{CLI} rulings skip --reason ...`"))
        if not s["rulings"]: sys.exit(f"REFUSED: the sheet holds no ruling - `{CLI} rulings add` or `{CLI} rulings skip --reason ...`")
        t = now(); assumed = []
        for r in s["rulings"]:
            if r["status"] != "open": continue
            rt = next(x["text"] for x in r["options"] if x["key"] == r["recommend"])
            e = kb_entry(s, r, f"Working assumption (the recommendation, not confirmed by the lead): {r['question']} -> {rt}", "working-assumption", "proposal", "orchestrator", t)
            r.update({"status": "assumed", "updated_at": t}); assumed.append(f"{r['id']}->{e['id']}")
        s.update({"status": "done", "done_at": t}); save(s)
        print(f"rulings done: {sum(1 for r in s['rulings'] if r['status'] == 'answered')} answered, {len(assumed)} working assumption(s)" + (f" ({', '.join(assumed)})" if assumed else "") + " - every brief carries them from now on")
    elif cmd == "skip":
        if s.get("status") in ("done", "skipped"): sys.exit(f"REFUSED: the rulings sheet is already {s['status']}")
        if not opt(a, "--reason"): sys.exit("REFUSED: --reason \"...\"")
        s = s or {"topics": {}, "rulings": []}; s.update({"status": "skipped", "skip_reason": opt(a, "--reason"), "skipped_at": now()}); save(s); print(f"rulings skipped ({s['skip_reason']})")
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
