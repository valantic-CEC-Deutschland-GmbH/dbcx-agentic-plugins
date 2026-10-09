#!/usr/bin/env python3
"""Evidence locators: resolve and check the places claims point at, across every evidence-base kind.
Usage: dbcx evidence resolve "<locator>" [...]        print what each locator points at (exists / missing / kind)
       dbcx evidence check <scope>                     every evidence cell of the scope's claims: dangling locators -> analysis/gauntlet/<scope>/dangling-evidence.md
       dbcx evidence bases                             the resolved evidence bases of this run with roles (from method + run.json)
       dbcx evidence quotes <scope|all> [--offline]    quote gate: look each claim's `quote` up word for word in the text its locators point at
                                                       -> analysis/gauntlet/<scope>/quotes.json; status per claim verified | partial | not_found | unreadable | no_quote
                                                       (extract_claims runs it for the critic pack; --offline skips web pages, PS-7 rows then check their stored quote only)
Quote lookup: fragments split at […] / … / ... / ' – ' / ' | ' / ' / ' / line breaks, each of >= 20 letters and digits; text and fragment compared as
lowercase letters and digits only (incl. äöüß). Text per locator: SRC-nnn#anchor -> the anchored block of corpus/text/SRC-nnn.md with one block before and
after (anchors are coarse: #L every 40 lines, #para every 12 paragraphs); PS-7-NNN -> the row's stored quote + its URL's page through safe_web
(help.sap.com via its content service); KB-n -> the entry text; Q-/A- -> the answer; a repository or run path -> the file, a :from-to range
honoured. Other locators (URL, workbook cell, HO-, C-, visual) carry no text for the check. `claims.quotes` off | warn | required (run config):
required makes a fact claim whose quote is not_found a blocking defect and a claim without a quote an imprecise one (score_aggregate).
Locator grammar: <path>[:<from>[-<to>]] into a repository or run folder | SRC-nnn[@rev]#<anchor> into the corpus | <file.xlsx>!<Sheet>!<Cell> | http(s)://... | PS-7-NNN (reference row) | HO-<type>#<id> (imported handover artefact row; an id the frozen snapshot lacks resolves through the consumed artefact's materialised target, e.g. HO-landscape#<id> -> state/landscape.json, HO-requirements-set#<id> -> state/requirements.json) | vendor:<path> (tolerated legacy alias - standard code is cited by its real path) | Q-<who>-N / A-<who>-N (an ANSWERED question of the register - what the client or the lead stated, carrying its weight) | KB-n / KB-H-n (an active entry of the run knowledge base, carrying its weight; a client-fact has client-evidence weight) | C-<scope>-NNN (a fact claim an assessment rests on: this scope's register, a final scope's analysis or the inventory handover - A9) | `visual, unverified`.
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, CORPUS_DIR, REF_DIR, PROJECT_DIR, STATUS_PATH, SCOPES_PATH, project, method, evidence_bases, scope_info, load_json, load_questions, relp

def resolve(loc, cfg=None, claim_ids=None):
    loc = (loc or "").strip().strip("`")
    if not loc: return ("empty", False, "")
    if loc.lower().startswith("visual"): return ("visual", True, "unverifiable by design - confidence low, client question expected")
    if re.match(r"https?://", loc): return ("url", True, "external - checked by the standard critic")
    if re.fullmatch(r"C-[\w.-]+-\d+", loc):   # an assessment lists the ids of the fact claims it rests on (analysis template)
        if claim_ids is None: return ("claim", True, "claim reference - register not loaded in this context")
        if loc in claim_ids: return ("claim", True, loc)
        return cross_scope_claim(loc)
    if re.fullmatch(r"[QA]-[\w-]*?-?\d+", loc) and not loc.startswith("C-"):
        # What the client or the lead stated is evidence about the client's own estate - the strongest kind for
        # facts no file can show (what production runs, who owns a fork). Only an ANSWERED question counts, and
        # the answer's weight travels with it: fact = client evidence, proposal = to be weighed against the code.
        q = next((x for x in load_questions() if x.get("id") == loc), None)
        if not q: return ("question", False, "no such question in state/QUESTIONS.json")
        ans = (q.get("answers") or [None])[-1] or q.get("answer") or {}
        if not ans.get("text") and not ans.get("option"): return ("question", False, "question is still open - an unanswered question is not evidence")
        return ("question", True, f"answered by {ans.get('by', '?')} [{ans.get('weight', '?')}]" + (f" - {q.get('qualification')}" if q.get("qualification") else ""))
    if re.fullmatch(r"KB-(?:H-)?\d+", loc):   # a knowledge-base entry is evidence with its own weight, like an answered question
        import kb; e = kb.find_entry(loc)
        if not e: return ("kb", False, "no such entry in state/KNOWLEDGE.json")
        if e.get("status") != "active": return ("kb", False, f"superseded by {e.get('superseded_by')} - cite the active entry")
        return ("kb", True, f"{e['type']} [{e['weight']}]" + (" - client-evidence weight" if e["type"] == "client-fact" else ""))
    m = re.match(r"(PS-7-\d+)", loc)
    if m:
        ref = os.path.join(REF_DIR, "platform-standard.md")
        ok = os.path.exists(ref) and m.group(1) in open(ref, encoding="utf-8").read(); return ("reference", ok, ref if ok else "no such reference row")
    m = re.match(r"(SRC-\d+)(?:@(\d+))?(?:#(\S+))?", loc)
    if m:
        sid = m.group(1) + (f"@{m.group(2)}" if m.group(2) else ""); fp = os.path.join(CORPUS_DIR, "text", f"{sid}.md")
        if not os.path.exists(fp): return ("corpus", False, f"no such source {sid} (dbcx corpus index)")
        if m.group(3) and f"{m.group(1)}#{m.group(3)} " not in open(fp, encoding="utf-8").read() and f"{m.group(1)}#{m.group(3)}" not in open(fp, encoding="utf-8").read(): return ("corpus", False, f"anchor #{m.group(3)} not in {sid}")
        return ("corpus", True, fp)
    m = re.match(r"HO-([\w-]+)#(\S+)", loc)
    if m:
        fp = os.path.join(ROOT, "input", "handover", f"{m.group(1)}.json")
        ok = os.path.exists(fp) and f'"{m.group(2)}"' in open(fp, encoding="utf-8").read()
        if not ok:   # an external import (a converted client file) resolves through the consumed artefact's materialised target
            tp = next((c.get("target") for c in ((method().get("artefacts") or {}).get("consumes") or []) if c.get("type") == m.group(1) and c.get("target")), None)
            tf = os.path.join(ROOT, tp) if tp else None
            if tf and os.path.exists(tf) and f'"{m.group(2)}"' in open(tf, encoding="utf-8").read(): return ("handover", True, tf)
        if not os.path.exists(fp): return ("handover", False, "no such imported artefact")
        return ("handover", ok, fp)
    m = re.match(r"(.+?\.xlsx)!([^!]+)!([A-Z]+\d+)$", loc)
    if m:
        for base in (ROOT, PROJECT_DIR):
            fp = m.group(1) if os.path.isabs(m.group(1)) else os.path.join(base, m.group(1))
            if os.path.exists(fp): return ("workbook", True, fp)
        return ("workbook", False, "workbook not found")
    path = re.sub(r":\d+(-\d+)?$", "", loc.replace("vendor:", ""))
    cands = [path] if os.path.isabs(path) else [os.path.join(ROOT, path), os.path.join(PROJECT_DIR, path)]
    for eb in evidence_bases(cfg):
        for r in eb.get("abs_roots", []): cands.append(os.path.join(r, path))
    for c in cands:
        if os.path.exists(c): return ("path", True, c)
    return ("path", False, "not found in run, project or any evidence base root")

FINAL_STATES = ("final", "passed", "failed-gauntlet")
def cross_scope_claim(loc):
    """`C-<other scope>-NNN` resolves when that scope is final (STATUS scope state final / passed /
    failed-gauntlet, or its inventory / consolidation phase done - the latter carries its open issues into the deliverable anyway) and its analysis holds the claim,
    or when the inventory handover lists the claim. Anything else stays dangling: an unscored claim is no evidence."""
    m = re.fullmatch(r"C-(.+)-(\d+)", loc); scope = m.group(1)
    try: js, md, kind, role, agent = scope_info(scope)
    except SystemExit: return ("claim", False, "no such claim in this scope")
    st = load_json(STATUS_PATH, {}) or {}
    from common import phase_for_scope
    ph = phase_for_scope(scope); ent = ((st.get("phases") or {}).get(ph) or {}) if ph else ((st.get("scopes") or {}).get(scope) or {})
    state = ent.get("status")
    if ph and (state == "done" or ent.get("passed")): state = "final"   # an inventory / consolidation phase closes as done
    if state in FINAL_STATES and os.path.exists(js) and any(c.get("id") == loc for c in (load_json(js, {}) or {}).get("claims", [])):
        return ("claim", True, f"cross-scope claim of {scope} ({state}): {relp(js, ROOT)}")
    try: from common import method; inv = method().get("inventory") or {}
    except SystemExit: inv = {}
    ho = os.path.join(ROOT, inv["handover"]) if inv.get("handover") else None
    if ho and os.path.exists(ho) and re.search(r"\*\*" + re.escape(loc) + r"\*\*", open(ho, encoding="utf-8").read()):
        return ("claim", True, f"handover claim ({inv['handover']})")
    if state and state not in FINAL_STATES: return ("claim", False, f"claim of {scope}, which is not final yet ({state}) - an unscored claim is not evidence; cite its locators or wait")
    return ("claim", False, f"no such claim in this scope, in a final scope's analysis or in the handover")

# ------------------------------------------------------------------ quote gate 
QUOTE_MODES = ("off", "warn", "required")
def quotes_mode(cfg=None):
    v = ((cfg or project()).get("claims") or {}).get("quotes", "off")
    if v not in QUOTE_MODES: sys.exit(f"claims.quotes must be one of {', '.join(QUOTE_MODES)}, not {v!r}")
    return v
def qnorm(s): return re.sub(r"[^0-9a-zäöüß]+", "", (s or "").lower())
def fragments(q):
    fr = [f.strip() for f in re.split(r"\[…\]|\[\.\.\.\]|…|\.\.\.|\s[–|]\s|\s/\s|\n|<br>", q or "") if len(qnorm(f)) >= 20]
    return fr or [(q or "").strip()]
def corpus_block(txt, sid, anchor):
    """the block an anchor opens (up to the next anchor comment) with one block before and after, anchor comments removed; None when the anchor is absent"""
    lines = txt.splitlines(); starts = [i for i, l in enumerate(lines) if l.startswith("<!-- SRC-")]
    k = next((n for n, i in enumerate(starts) if lines[i].startswith(f"<!-- {sid}#{anchor} -->")), None)
    if k is None: return None
    a = starts[max(0, k - 1)]; b = starts[k + 2] if k + 2 < len(starts) else len(lines)
    return re.sub(r"<!--.*?-->", " ", "\n".join(lines[a:b]))
def line_range(txt, loc):
    m = re.search(r":(\d+)(?:-(\d+))?$", loc)
    if not m: return txt
    lo = int(m.group(1)); hi = int(m.group(2) or lo); return "\n".join(txt.splitlines()[lo - 1:hi])

def locator_texts(loc, cfg, offline=False, cache=None):
    """([(label, text)], reason) - the text a quote is looked up in for one locator; an empty list carries the reason"""
    cache = {} if cache is None else cache; loc = (loc or "").strip().strip("`")
    if loc in cache: return cache[loc]
    if loc.lower().startswith("visual") or re.match(r"https?://", loc) or re.fullmatch(r"C-[\w.-]+-\d+", loc) or re.match(r"HO-", loc) or re.match(r".+?\.xlsx!", loc):
        out = ([], "")   # no text for the quote check
    else:
        kind, ok, info = resolve(loc, cfg, set())
        if not ok: out = ([], f"does not resolve ({info})")
        elif kind == "corpus":
            m = re.match(r"(SRC-\d+)(?:@\d+)?(?:#(\S+))?", loc); txt = open(info, encoding="utf-8").read()
            blk = corpus_block(txt, m.group(1), m.group(2)) if m.group(2) else re.sub(r"<!--.*?-->", " ", txt)
            out = ([(loc, blk)], "") if blk is not None else ([], f"anchor #{m.group(2)} not in {os.path.basename(info)}")
        elif kind == "reference":
            import reference; pid = re.match(r"PS-7-\d+", loc).group(0)
            try: row = next((c for _, c in reference.load()[4] if c and c[0] == pid), [])
            except SystemExit: row = []
            got, why = ([(f"{pid} (stored quote)", reference.quote_of(row))] if reference.quote_of(row) else []), []
            url = reference.norm(row)[3] if row else ""
            if re.match(r"https?://", url) and offline: why.append("page not fetched (--offline)")
            elif re.match(r"https?://", url):
                if "page:" + url not in cache:
                    try: import safe_web; cache["page:" + url] = (safe_web.page_text(url), "")
                    except (Exception, SystemExit) as ex: cache["page:" + url] = (None, f"{type(ex).__name__}: {ex}")
                page, err = cache["page:" + url]
                if page is not None: got.append((f"{pid} (page)", page))
                else: why.append(f"page unreadable ({err})")
            out = (got, "; ".join(why) or ("no stored quote and no URL" if not got else ""))
        elif kind == "kb":
            import kb; out = ([(loc, kb.find_entry(loc)["text"])], "")
        elif kind == "question":
            q = next(x for x in load_questions() if x.get("id") == loc); ans = (q.get("answers") or [None])[-1] or q.get("answer") or {}
            opt = next((o.get("text", "") for o in q.get("options") or [] if o.get("key") == ans.get("option")), "")
            out = ([(loc, " ".join(x for x in (ans.get("text"), opt) if x))], "")
        elif kind == "path" and os.path.isfile(info):
            out = ([(loc, line_range(open(info, encoding="utf-8", errors="ignore").read(), loc))], "")
        else: out = ([], f"no readable text ({kind}: {info})")
    cache[loc] = out; return out

def quote_check(c, cfg, offline=False, cache=None):
    """{status, quote, missing, at, unreadable} for one claim"""
    q = (c.get("quote") or "").strip()
    if not q: return {"status": "no_quote"}
    texts, unread = [], []
    for loc in c.get("evidence") or []:
        got, why = locator_texts(loc, cfg, offline, cache); texts += [(lab, qnorm(t)) for lab, t in got]
        if why: unread.append(f"{loc}: {why}")
    if not texts: return {"status": "unreadable", "quote": q, "unreadable": unread or ["no cited locator carries text (URL, workbook cell, handover row, claim id or visual only)"]}
    fr = fragments(q); miss = [f for f in fr if not any(qnorm(f) in t for _, t in texts)]
    at = list(dict.fromkeys(lab for lab, t in texts if any(qnorm(f) in t for f in fr)))
    st = "verified" if not miss else ("partial" if len(miss) < len(fr) else "not_found")
    return {"status": st, "quote": q, "fragments": len(fr), "missing": miss, "at": at, "unreadable": unread}

def quotes_scope(scope, cfg, offline=False, cache=None):
    """check every claim of the scope's converted analysis and write analysis/gauntlet/<scope>/quotes.json"""
    import hashlib, time
    js = scope_info(scope)[0]; data = load_json(js); cache = {} if cache is None else cache
    res = {c["id"]: dict(quote_check(c, cfg, offline, cache), type=c.get("type")) for c in data.get("claims", []) if c.get("id")}
    counts = {s: sum(1 for r in res.values() if r["status"] == s) for s in ("verified", "partial", "not_found", "unreadable", "no_quote")}
    out = {"scope": scope, "source": relp(js, ROOT), "source_sha256": hashlib.sha256(open(js, "rb").read()).hexdigest(), "mode": quotes_mode(cfg), "offline": offline,
           "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "counts": counts, "claims": res}
    fp = os.path.join(ROOT, "analysis", "gauntlet", scope, "quotes.json"); os.makedirs(os.path.dirname(fp), exist_ok=True)
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return out

def quote_section(q, ids=None):
    """the critic pack's quote block (ids = the claims of this pack variant)"""
    rows = [(cid, r) for cid, r in q["claims"].items() if ids is None or cid in ids]
    def line(cid, r):
        st = r["status"]
        if st == "verified": return f"- {cid}: verified at {', '.join(r['at'])}"
        if st == "partial": return f"- {cid}: partial - found at {', '.join(r['at'])}; not found: " + " / ".join(f'"{f}"' for f in r["missing"])
        if st == "not_found": return f"- {cid}: not_found - the quoted words are not at the cited locators" + (f" (unreadable: {'; '.join(r['unreadable'])})" if r.get("unreadable") else "")
        return f"- {cid}: unreadable - " + "; ".join(r.get("unreadable") or [])
    nq = [cid for cid, r in rows if r["status"] == "no_quote"]
    out = [f"## Quote check (claims.quotes = {q['mode']}; `analysis/gauntlet/{q['scope']}/quotes.json`)", "",
           "Mechanical: `verified at <locator>` means the quoted words stand there - judge whether they carry the statement (interpretation), not whether they exist. `not_found` / `partial`: the claim's quoted words (or some fragments) are not at its locators.", ""]
    out += [line(cid, r) for cid, r in rows if r["status"] != "no_quote"]
    if nq: out.append(f"- no quote ({len(nq)}): " + ", ".join(nq) + (" - each counts toward the imprecise share" if q["mode"] == "required" else ""))
    return "\n".join(out)

def all_scopes():
    m = method(); inv = (m.get("inventory") or {}).get("scope")
    names = list((load_json(SCOPES_PATH, {}) or {}).get("scopes", {}) if os.path.exists(SCOPES_PATH) else []) + list(m.get("consolidations") or {}) + ([inv] if inv else [])
    return [s for s in dict.fromkeys(names) if os.path.exists(scope_info(s, m)[0])]

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cfg = project()
    if a[0] == "resolve":
        for loc in a[1:]:
            kind, ok, info = resolve(loc, cfg); print(f"{'OK ' if ok else 'MISSING'} [{kind}] {loc} -> {info}")
    elif a[0] == "bases":
        for eb in evidence_bases(cfg): print(f"{eb['id']:16s} {eb.get('kind', ''):11s} roles={','.join(eb.get('roles', []))} external={eb.get('external')} roots={eb.get('abs_roots') or eb.get('domains', [])}")
    elif a[0] == "check":
        scope = a[1]; js = scope_info(scope)[0]; d = load_json(js); bad = []; n = 0
        claim_ids = {c.get("id") for c in d.get("claims", []) if c.get("id")}
        for c in d.get("claims", []):
            for ev in c.get("evidence", []) or []:
                n += 1; kind, ok, info = resolve(ev, cfg, claim_ids)
                if not ok: bad.append((c["id"], ev, kind, info))
        out = os.path.join(ROOT, "analysis", "gauntlet", scope, "dangling-evidence.md"); os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(f"# Dangling evidence: {scope} - {len(bad)} of {n} evidence cells do not resolve\n\nA claim whose evidence does not resolve cannot be checked by the client critic; it scores 4 at best (unsupported).\n\n" + "\n".join(f"- {cid}: `{ev}` [{k}] {info}" for cid, ev, k, info in bad) + "\n")
        print(f"{len(bad)}/{n} evidence cells dangling -> {relp(out, ROOT)}")
    elif a[0] == "quotes" and len(a) > 1:
        offline = "--offline" in a; cache = {}
        for scope in (all_scopes() if a[1] == "all" else [a[1]]):
            q = quotes_scope(scope, cfg, offline, cache); c = q["counts"]
            print(f"{scope}: " + ", ".join(f"{v} {k}" for k, v in c.items()) + f" -> analysis/gauntlet/{scope}/quotes.json")
            for cid, r in q["claims"].items():
                if r["status"] in ("partial", "not_found", "unreadable"): print(f"  {cid} {r['status']}" + (f": {' / '.join(r['missing'])[:160]}" if r.get("missing") else f": {'; '.join(r.get('unreadable') or [])[:160]}"))
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
