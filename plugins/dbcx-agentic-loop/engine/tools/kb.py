#!/usr/bin/env python3
"""The run knowledge base: knowledge that matters to MORE THAN ONE scope, curated by the orchestrator.
state/KNOWLEDGE.json is the register (written only by this tool); docs/KNOWLEDGE.md is a rendered read-only view. Single-scope knowledge
stays a lead hint, a lead fact or a routed question. Every entry is ONE statement in the orchestrator's words; the source is linked, not copied.

Usage: dbcx kb add --text T --topic X [--topic-summary S] --applies-to A,B|* --type client-fact|decision|working-assumption|cross-scope-finding
                   [--weight fact|proposal] [--by lead|client|orchestrator] [--core] [--standard] [--source-ref R] [--supersedes KB-n]
                                                  new entry KB-NNN. Refused: `applies_to` naming exactly one scope or an unknown id (scopes.json,
                                                  consolidations, the inventory scope), a topic that is not kebab-case, a new topic without
                                                  --topic-summary, --standard on a text that fails the external-leak check (safe_web / hook H3).
                                                  client-fact forces weight fact; --by client forces type client-fact. Default weight: fact for
                                                  client-fact / decision, proposal otherwise; default --by orchestrator. source.kind: answer (--source-ref
                                                  is a question id), finding (a claim id), else lead (`dbcx rulings` writes kind ruling). --supersedes
                                                  marks the old entry superseded.
       dbcx kb promote KC-n --text T --topic X [--topic-summary S] --applies-to ... [--core] [--standard]
                                                  candidate -> entry; type / weight / by / source come from the answer (or the inbox entry)
       dbcx kb reject KC-n --reason R             candidate closed
       dbcx kb show [--scope S] [--role R] [--topic X] [--core] [--all]
                                                  --scope/--role: the KNOWLEDGE BASE block a brief for that scope / role would contain (role default:
                                                  consolidate for a consolidation, inventory for the inventory scope, else analyst); --topic: one topic
                                                  in full; --core: the core entries; --all: every entry incl. superseded; no flag: the index
       dbcx kb pending <agent>                    active entries relevant to the agent's scope / role created after its latest brief
                                                  (analysis/briefs/<agent>[-rN].meta.json) - send them to the running agent as ONE message
       dbcx kb index                              topics with count and summary, open candidates, warnings (never blocking)
       dbcx kb export [--label "..."]             release active entries + topics as the engine handover type knowledge-base
       dbcx kb import-handover <file> [--as-global]
                                                  import a knowledge-base handover as entries KB-H-n (source.kind handover, ids stable); an entry
                                                  naming a scope this run does not have is listed, not imported - --as-global imports it as ["*"]
Candidates KC-n come from `dbcx questions answer` (the answer touches >= 2 scopes) and `dbcx inbox apply` (kind knowledge);
`dbcx status verify` lists open ones as owed work. Thresholds: method.json -> knowledge {full_max 20, core_warn 15, topic_warn 15, dedup_floor 0.15}.
"""
import os, re, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, KNOWLEDGE_PATH, SCOPES_PATH, CLI, load_json, save_json, load_questions, method, relp

TYPES = ("client-fact", "decision", "working-assumption", "cross-scope-finding"); WEIGHTS = ("fact", "proposal"); BYS = ("lead", "client", "orchestrator")
DEFAULTS = {"full_max": 20, "core_warn": 15, "topic_warn": 15, "dedup_floor": 0.15}
KB_ROLES = ("analyst", "inventory", "critic-client", "critic-standard", "consolidate")
TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def opt(a, k, d=""): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d

def load(): return load_json(KNOWLEDGE_PATH, {"entries": [], "topics": {}, "candidates": []}) if os.path.exists(KNOWLEDGE_PATH) else {"entries": [], "topics": {}, "candidates": []}
def save(kb): save_json(KNOWLEDGE_PATH, kb); render_md(kb)
def active(kb): return [e for e in kb.get("entries", []) if e.get("status") == "active"]
def find_entry(eid, kb=None): return next((e for e in (kb or load()).get("entries", []) if e.get("id") == eid), None)
def _method():
    try: return method()
    except SystemExit: return {}
def thresholds(m=None): return {**DEFAULTS, **((m if m is not None else _method()).get("knowledge") or {})}
def scopes(): return set((load_json(SCOPES_PATH, {}) or {}).get("scopes", {})) if os.path.exists(SCOPES_PATH) else set()
def scope_ids(m=None):
    """every id an entry may name: the scopes of state/scopes.json, the consolidations and the inventory scope"""
    m = m if m is not None else _method(); inv = (m.get("inventory") or {}).get("scope")
    return scopes() | set(m.get("consolidations") or {}) | ({inv} if inv else set())

def relevant(e, scope, m):
    """applies_to contains * or the scope; a consolidation also takes every entry naming one of its input scopes"""
    at = e.get("applies_to") or []
    if "*" in at or scope in at: return True
    return scope in (m.get("consolidations") or {}) and bool(set(at) & scopes())

def line(e): return f"- [{e['id']} · {e['type']} · {e['weight']}] {e['text']}"
def heading(kb, t, lvl="###"): s = ((kb.get("topics") or {}).get(t) or {}).get("summary", ""); return f"{lvl} {t}" + (f" - {s}" if s else "")
def grouped(kb, es, lvl="###"):
    out = []
    for t in dict.fromkeys(e["topic"] for e in es): out += [heading(kb, t, lvl)] + [line(e) for e in es if e["topic"] == t]
    return out

SEMANTICS = {"critic": "Semantics: client-fact / fact entries are BINDING like a lead fact - score the claims against them and never mark a claim false on the strength of a source they overrule; working-assumption / proposal entries: weigh them against the evidence. A claim may cite `KB-n` as a locator (kind kb, the entry's weight; a client-fact carries client-evidence weight).",
             "writer": "Semantics: client-fact / fact entries are givens for your work; working-assumption / proposal entries: weigh them against the evidence. Cite an entry as the locator `KB-n` (kind kb, the entry's weight; a client-fact carries client-evidence weight)."}
INSTRUCTION = "Before raising a question, check this block and the index; if an index topic may hold the answer, run `dbcx kb show --topic X`. Do not ask what is answered here; cite the KB id instead."

def brief_block(role, scope, m=None, kb=None):
    """## KNOWLEDGE BASE of a brief (analyst, inventory, critic-client, consolidate; critic-standard: standard entries only; "" otherwise
    and when there is neither a relevant entry nor an index line - an empty knowledge base leaves every brief byte-identical).
    Full mode: the relevant entries by topic; tiered mode (> full_max active entries): the relevant core entries, then the relevant
    non-core entries by topic. Both modes end with the index of the topics that hold no entry for this brief."""
    if role not in KB_ROLES: return ""
    m = m if m is not None else _method(); kb = kb or load(); act = active(kb)
    pool = [e for e in act if e.get("standard")] if role == "critic-standard" else act
    rel = [e for e in pool if relevant(e, scope, m)]; seen = {e["topic"] for e in rel}
    idx = [t for t in dict.fromkeys(e["topic"] for e in pool) if t not in seen]   # topics with no entry for this brief, in both modes
    if not (rel or idx): return ""
    if len(act) <= thresholds(m)["full_max"]: body = grouped(kb, rel)
    else:
        core = [e for e in rel if e.get("core")]; mine = [e for e in rel if not e.get("core")]
        body = (["### Core"] + [line(e) for e in core] if core else []) + (["### Your topics"] + grouped(kb, mine, "####") if mine else [])
    if idx: body += ["### Index (topics without an entry for this brief - `dbcx kb show --topic X` prints one in full)"] + [f"- {t} · {sum(1 for e in pool if e['topic'] == t)} entries · {((kb.get('topics') or {}).get(t) or {}).get('summary', '')}" for t in idx]
    head = ["## KNOWLEDGE BASE (cross-scope knowledge curated by the orchestrator" + (", cleared for the standard side" if role == "critic-standard" else "") + ")",
            SEMANTICS["critic" if role.startswith("critic-") else "writer"]] + ([INSTRUCTION] if role in ("analyst", "inventory", "consolidate") else [])
    return "\n".join(head + body)

def warnings(kb, th):
    act = active(kb); out = []; own = [e for e in act if (e.get("source") or {}).get("kind") != "ruling"]   # rulings are core and * by design - the warnings count the rest
    core = sum(1 for e in own if e.get("core"))
    if core > th["core_warn"]: out.append(f"{core} core entries (> {th['core_warn']}): merge or supersede core entries")
    for t in dict.fromkeys(e["topic"] for e in act):
        n = sum(1 for e in act if e["topic"] == t)
        if n > th["topic_warn"]: out.append(f"topic {t} has {n} entries (> {th['topic_warn']}): split topic {t}")
        if not ((kb.get("topics") or {}).get(t) or {}).get("summary"): out.append(f"topic {t} has no summary")
    star = sum(1 for e in own if "*" in (e.get("applies_to") or []))
    if own and star > len(own) / 2: out.append(f"{star} of {len(own)} active entries apply to *: check applies_to")
    return out

def render_md(kb):
    act = active(kb); old = [e for e in kb.get("entries", []) if e.get("status") != "active"]; oc = [c for c in kb.get("candidates", []) if c.get("status") == "open"]
    lines = ["# Knowledge base", "", "Rendered view of state/KNOWLEDGE.json (edit with `dbcx kb`, never by hand).", ""]
    for t in dict.fromkeys(e["topic"] for e in act): lines += [heading(kb, t, "##")] + [line(e) + f" (applies to {', '.join(e['applies_to'])}{', core' if e.get('core') else ''}{', standard' if e.get('standard') else ''})" for e in act if e["topic"] == t]
    if old: lines += ["", "## Superseded"] + [f"- {e['id']} -> {e.get('superseded_by') or '-'}: {e['text']}" for e in old]
    if oc: lines += ["", "## Open candidates"] + [f"- {c['id']} ({c.get('question') or (c.get('source') or {}).get('kind')}; affects {', '.join(c.get('affects') or []) or '-'})" for c in oc]
    fp = P("docs", "KNOWLEDGE.md"); os.makedirs(os.path.dirname(fp), exist_ok=True); open(fp, "w", encoding="utf-8").write("\n".join(lines) + "\n")

def parse_applies(spec_): ids = [x.strip() for x in (spec_ or "").replace(";", ",").split(",") if x.strip()]; return ["*"] if "*" in ids else list(dict.fromkeys(ids))

def add_entry(kb, text, topic, applies, typ, weight, by, source, summary="", core=False, standard=False, supersedes=None, m=None):
    """the admission rules of §2; exits REFUSED on a violation, returns the new entry (not yet saved)"""
    m = m if m is not None else _method()
    if not text.strip(): sys.exit("REFUSED: --text is empty")
    if typ not in TYPES: sys.exit(f"REFUSED: --type must be one of {', '.join(TYPES)}")
    if by not in BYS: sys.exit(f"REFUSED: --by must be one of {', '.join(BYS)}")
    if by == "client": typ = "client-fact"
    weight = weight or ("fact" if typ in ("client-fact", "decision") else "proposal")
    if typ == "client-fact": weight = "fact"
    if weight not in WEIGHTS: sys.exit("REFUSED: --weight fact|proposal")
    if not TOPIC_RE.match(topic or ""): sys.exit(f"REFUSED: topic {topic!r} must be kebab-case (e.g. erp-integration)")
    if topic not in (kb.get("topics") or {}) and not summary: sys.exit(f"REFUSED: {topic} is a new topic - pass --topic-summary \"one line\" once")
    if not applies: sys.exit("REFUSED: --applies-to A,B or *")
    if applies != ["*"]:
        unknown = [x for x in applies if x not in scope_ids(m)]
        if unknown: sys.exit(f"REFUSED: unknown scope id(s) {', '.join(unknown)} (state/scopes.json, consolidations, inventory scope)")
        if len(applies) < 2: sys.exit(f"REFUSED: {applies[0]} is one scope - single-scope knowledge stays a lead hint / lead fact / routed question, the knowledge base holds what matters to >= 2 scopes or *")
    if standard:
        import safe_web; from common import project
        why = safe_web.privacy_reasons(text, project())
        if why: sys.exit(f"REFUSED: --standard needs a text that passes the external-leak check ({', '.join(why)})")
    old = find_entry(supersedes, kb) if supersedes else None
    if supersedes and (not old or old.get("status") != "active"): sys.exit(f"REFUSED: --supersedes {supersedes} is no active entry")
    n = max([int(x["id"][3:]) for x in kb.get("entries", []) if re.fullmatch(r"KB-\d+", x.get("id", ""))] + [0]) + 1; t = now()
    e = {"id": f"KB-{n:03d}", "text": text.strip(), "type": typ, "weight": weight, "topic": topic, "applies_to": applies, "core": bool(core), "standard": bool(standard),
         "source": source, "status": "active", "supersedes": supersedes or None, "superseded_by": None, "created_at": t, "updated_at": t}
    if summary: kb.setdefault("topics", {})[topic] = {"summary": summary}
    if old: old.update({"status": "superseded", "superseded_by": e["id"], "updated_at": t})
    kb.setdefault("entries", []).append(e); return e

# ------------------------------------------------------------------ candidates (questions answer, inbox apply)
def _candidate(kb, **kw):
    kb.setdefault("candidates", []); c = {"id": f"KC-{len(kb['candidates']) + 1:03d}", "question": None, "answer_at": None, "affects": [], "status": "open", "kb": None, "reason": ""}
    c.update(kw); kb["candidates"].append(c); return c

def candidate_from_answer(q, ans, dups=()):
    """§4: a candidate when affects ∪ {from, to} minus {client, lead} - united over the question and its linked duplicates - holds
    >= 2 scopes or *, or from != to are both scopes; idempotent per (question id, answer at). Returns the candidate or None."""
    ids = scope_ids(); names = set().union(*((set(x.get("affects") or []) | {x.get("from"), x.get("to")}) for x in [q, *dups])) - {"client", "lead", None, ""}
    hit = sorted(x for x in names if x in ids)
    if "*" not in names and len(hit) < 2 and not (q.get("from") != q.get("to") and q.get("from") in ids and q.get("to") in ids): return None
    kb = load(); c = next((x for x in kb.get("candidates", []) if x.get("question") == q["id"] and x.get("answer_at") == ans.get("at")), None)
    if c: return c
    c = _candidate(kb, question=q["id"], answer_at=ans.get("at"), affects=["*"] if "*" in names else hit); save(kb); return c

def candidate_from_inbox(e):
    kb = load(); c = next((x for x in kb.get("candidates", []) if (x.get("source") or {}).get("ref") == e.get("client_id")), None)
    if c: return c
    c = _candidate(kb, affects=[s for s in e.get("scopes") or [] if s], source={"kind": "inbox", "ref": e.get("client_id"), "by": e.get("by", "lead"), "at": e.get("at")}, text=e.get("text", ""), weight=e.get("weight", "proposal"))
    save(kb); return c

# ------------------------------------------------------------------ related on intake (questions add / import): a ranking, not a threshold
LOCATOR_TOKEN = re.compile(r"src\d*|[pr]\d+|\d+")
def tokens(t): return [w for w in re.findall(r"\w+", (t or "").lower()) if len(w) > 2 and not LOCATOR_TOKEN.fullmatch(w)]
def related(q, questions):
    """§4: the top-3 tf-idf cosine neighbours of a new question among the active entries and the questions of OTHER scopes (open or
    answered) with cosine >= knowledge.dedup_floor; idf over every question of the register plus the active entry texts. The engine
    proposes, the orchestrator decides (`dbcx questions link`, `--from-kb`) - measured: the true duplicate was in the top-3 in 17 of 17."""
    import math
    from collections import Counter
    ents = active(load()); docs = [x.get("question") or "" for x in questions] + [e["text"] for e in ents]
    df = Counter(w for d in docs for w in set(tokens(d))); n = len(docs)
    def vec(t): tf = Counter(tokens(t)); v = {w: c * math.log((1 + n) / (1 + df.get(w, 0))) + c for w, c in tf.items()}; nv = math.sqrt(sum(x * x for x in v.values())); return {w: x / nv for w, x in v.items()} if nv else {}
    qv = vec(q.get("question")); cands = [(e["id"], e["text"]) for e in ents] + [(x["id"], x.get("question") or "") for x in questions if x.get("id") != q.get("id") and x.get("from") != q.get("from")]
    scored = sorted(((cid, sum(qv.get(w, 0) * x for w, x in vec(t).items())) for cid, t in cands), key=lambda r: -r[1])
    return [{"id": cid, "score": round(sc, 2)} for cid, sc in scored[:3] if sc >= thresholds()["dedup_floor"]]

# ------------------------------------------------------------------ pending (running agents)
def agent_target(agent, m):
    """(brief role, scope) of an agent name, or (role, None) for a role without a knowledge-base block"""
    from common import role_of_agent
    role = role_of_agent(agent, m); ids = scope_ids(m); inv = m.get("inventory") or {}
    if role == "inventory": return "inventory", inv.get("scope")
    if role == "consolidator": return "consolidate", next((x for x in m.get("consolidations") or {} if f"consolidate-{x.lower()}" == agent), None)
    if role == "analyst":
        for pre in ((m.get("scopes") or {}).get("agent_prefix", "analyst-"), "analyst-", "unit-"):
            if agent.startswith(pre): return "analyst", agent[len(pre):]
    if role in ("critic-client", "critic-standard"):
        rest = re.sub(r"^critic-(client|standard|platform)-", "", agent)
        return role, rest if rest in ids else next((s for s in sorted(ids, key=len, reverse=True) if rest.endswith("-" + s)), rest)
    return role, None

def pending(agent):
    import glob
    m = _method(); role, scope = agent_target(agent, m)
    if role not in KB_ROLES or not scope: print(f"{agent} ({role}) gets no knowledge-base block - nothing to send"); return []
    metas = [f for f in glob.glob(P("analysis", "briefs", "*.meta.json")) if re.fullmatch(re.escape(agent) + r"(-r\d+|-conflicts)?\.meta\.json", os.path.basename(f))]
    if not metas: sys.exit(f"no brief of {agent} under analysis/briefs/ - render it (`{CLI} render brief ... --out`); its KNOWLEDGE BASE block carries every entry")
    latest = max(metas, key=os.path.getmtime); since = int(os.path.getmtime(latest))
    kb = load(); pool = [e for e in active(kb) if e.get("standard")] if role == "critic-standard" else active(kb)
    shown = open(latest[:-len(".meta.json")] + ".md", encoding="utf-8").read() if os.path.exists(latest[:-len(".meta.json")] + ".md") else ""   # same second as the brief: an entry it already carries is not pending
    new = [e for e in pool if relevant(e, scope, m) and time.mktime(time.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%S")) >= since and f"[{e['id']} " not in shown]
    if not new: print(f"no knowledge-base entry for {agent} created after {relp(latest, ROOT)}"); return []
    print(f"{len(new)} knowledge-base entr{'y' if len(new) == 1 else 'ies'} for {agent} created after {relp(latest, ROOT)} - send them to the running agent as ONE message:")
    print("KNOWLEDGE BASE (new since your brief; " + SEMANTICS["critic" if role.startswith("critic-") else "writer"][len("Semantics: "):] + ")\n" + "\n".join(line(e) for e in new))
    return new

# ------------------------------------------------------------------ handover
def export_data():
    kb = load(); act = active(kb); return {"entries": act, "topics": {t: v for t, v in (kb.get("topics") or {}).items() if any(e["topic"] == t for e in act)}}

def import_handover(path, as_global):
    env = json.load(open(path, encoding="utf-8")); data = env.get("data") if isinstance(env.get("data"), dict) else env
    if env.get("artefact_type") not in (None, "knowledge-base") or not isinstance(data.get("entries"), list): sys.exit(f"{path} is no knowledge-base artefact ({CLI} kb export)")
    kb = load(); ids = scope_ids(); have = {e["id"] for e in kb.get("entries", [])}; new, listed, cleared = [], [], []
    for e in data["entries"]:
        if e.get("status") != "active": continue
        nid = e["id"] if e["id"].startswith("KB-H-") else "KB-H-" + e["id"][3:]
        if nid in have: continue
        at = e.get("applies_to") or ["*"]; unknown = [x for x in at if x != "*" and x not in ids]
        if unknown and not as_global: listed.append(f"{e['id']} (unknown here: {', '.join(unknown)})"); continue
        x = dict(e, id=nid, applies_to=["*"] if unknown else at, supersedes=None, superseded_by=None, updated_at=now(),
                 source={"kind": "handover", "ref": f"{env.get('run', '')}:{e['id']}", "by": (e.get("source") or {}).get("by", "orchestrator"), "at": (e.get("source") or {}).get("at")})
        if x.get("standard"):
            import safe_web; from common import project
            if safe_web.privacy_reasons(x["text"], project()): x["standard"] = False; cleared.append(nid)
        kb.setdefault("entries", []).append(x); new.append(nid)
        if e.get("topic") and e["topic"] not in kb.setdefault("topics", {}): kb["topics"][e["topic"]] = (data.get("topics") or {}).get(e["topic"]) or {"summary": ""}
    save(kb); print(f"import-handover: {len(new)} new entr{'y' if len(new) == 1 else 'ies'} ({', '.join(new) or '-'}) from {env.get('run') or os.path.basename(path)}")
    if cleared: print(f"standard flag removed (text fails the external-leak check in this run): {', '.join(cleared)}")
    if listed: print(f"NOT imported - scopes this run does not have ({len(listed)}; re-add with the right applies_to, or --as-global): " + "; ".join(listed))

# ------------------------------------------------------------------ CLI
def show_index(kb, th):
    act = active(kb)
    for t in dict.fromkeys(e["topic"] for e in act): print(f"{t:30s} {sum(1 for e in act if e['topic'] == t):3d} entries  {((kb.get('topics') or {}).get(t) or {}).get('summary', '')}")
    oc = [c for c in kb.get("candidates", []) if c.get("status") == "open"]
    print(f"{len(act)} active entr{'y' if len(act) == 1 else 'ies'} ({'full' if len(act) <= th['full_max'] else 'tiered'} mode, full_max {th['full_max']}), {len(oc)} open candidate(s)" + (": " + ", ".join(f"{c['id']} ({c.get('question') or 'inbox'})" for c in oc) if oc else ""))
    for w in warnings(kb, th): print("WARNING:", w)

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]; kb = load()
    if cmd == "add":
        ref = opt(a, "--source-ref") or None
        kind = "answer" if ref and any(q.get("id") == ref for q in load_questions()) else ("finding" if ref and re.fullmatch(r"C-[\w.-]+-\d+", ref) else "lead")
        by = opt(a, "--by", "orchestrator")
        e = add_entry(kb, opt(a, "--text"), opt(a, "--topic"), parse_applies(opt(a, "--applies-to")), opt(a, "--type"), opt(a, "--weight"), by, {"kind": kind, "ref": ref, "by": by, "at": now()},
                      opt(a, "--topic-summary"), "--core" in a, "--standard" in a, opt(a, "--supersedes") or None)
        save(kb); print(f"{e['id']} [{e['type']} · {e['weight']}] topic {e['topic']}, applies to {', '.join(e['applies_to'])}" + (" (core)" if e["core"] else "") + (" (standard)" if e["standard"] else "") + (f"; {e['supersedes']} superseded" if e["supersedes"] else ""))
    elif cmd == "promote":
        c = next((x for x in kb.get("candidates", []) if x.get("id") == a[1]), None)
        if not c or c.get("status") != "open": sys.exit(f"REFUSED: {a[1]} is no open candidate")
        from questions import type_of
        if c.get("question"):
            q = next((x for x in load_questions() if x.get("id") == c["question"]), None) or sys.exit(f"REFUSED: question {c['question']} not in the register")
            ans = next((x for x in q.get("answers") or [] if x.get("at") == c.get("answer_at")), None) or q.get("answer") or {}
            by = ans.get("by") if ans.get("by") in ("lead", "client") else "orchestrator"; w = ans.get("weight", "proposal"); typ = ans.get("type") or type_of(ans.get("by"), w)
            src = {"kind": "answer", "ref": q["id"], "by": by, "at": c.get("answer_at")}
        else:
            src = dict(c.get("source") or {}); by = src.get("by") if src.get("by") in BYS else "lead"; w = c.get("weight", "proposal"); typ = type_of(by, w); src["by"] = by
        e = add_entry(kb, opt(a, "--text"), opt(a, "--topic"), parse_applies(opt(a, "--applies-to")), typ, w, by, src, opt(a, "--topic-summary"), "--core" in a, "--standard" in a)
        c.update({"status": "promoted", "kb": e["id"]}); save(kb); print(f"{c['id']} -> {e['id']} [{e['type']} · {e['weight']}] topic {e['topic']}, applies to {', '.join(e['applies_to'])}")
    elif cmd == "reject":
        c = next((x for x in kb.get("candidates", []) if x.get("id") == a[1]), None)
        if not c or c.get("status") != "open": sys.exit(f"REFUSED: {a[1]} is no open candidate")
        if not opt(a, "--reason"): sys.exit("REFUSED: --reason R")
        c.update({"status": "rejected", "reason": opt(a, "--reason")}); save(kb); print(f"{c['id']}: rejected")
    elif cmd == "show":
        if "--topic" in a:
            t = opt(a, "--topic"); es = [e for e in active(kb) if e["topic"] == t]
            print("\n".join([heading(kb, t)] + [line(e) for e in es]) if es else f"(no active entry in topic {t})")
        elif "--core" in a: print("\n".join(line(e) for e in active(kb) if e.get("core")) or "(no core entry)")
        elif "--all" in a: print("\n".join(grouped(kb, active(kb)) + [f"- [{e['id']} · superseded by {e.get('superseded_by')}] {e['text']}" for e in kb.get("entries", []) if e.get("status") != "active"]) or "(knowledge base empty)")
        elif "--scope" in a or "--role" in a:
            m = _method(); s = opt(a, "--scope"); inv = (m.get("inventory") or {}).get("scope")
            role = {"consolidator": "consolidate"}.get(opt(a, "--role"), opt(a, "--role")) or ("consolidate" if s in (m.get("consolidations") or {}) else ("inventory" if s == inv else "analyst"))
            print(brief_block(role, s or inv, m, kb) or f"(no KNOWLEDGE BASE block for a {role} brief of {s})")
        else: show_index(kb, thresholds())
    elif cmd == "pending": pending(a[1])
    elif cmd == "index": show_index(kb, thresholds())
    elif cmd == "export":
        import handover; handover.export("knowledge-base", opt(a, "--label"))
    elif cmd == "import-handover": import_handover(a[1], "--as-global" in a)
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
