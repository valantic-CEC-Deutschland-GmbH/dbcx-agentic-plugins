#!/usr/bin/env python3
"""Corpus retrieval: profile, search index, search, corpus map and the read/search strategy
per unit. Chosen by the engine and the agents, never configured by the user and never mentioned to them (skills/run/SKILL.md).

Usage: dbcx corpus profile [--json]                          corpus/PROFILE.json: per source tokens, language, extraction quality, origin, date,
                                                             identical copies and near-duplicates (built by `dbcx corpus index`)
       dbcx corpus search "<query>" ["<query>" ...] [--scope <id>] [--k N] [--json]
                                                             ranked locators SRC-nnn#anchor with a short snippet (keyword BM25, fused with the
                                                             meaning-based index when a local embedding backend exists); --scope limits the search
                                                             to the unit's mapped sources. Several queries (arguments, or one per line) run in one
                                                             call, fused by reciprocal rank; --json names per hit the queries that found it.
                                                             A snippet is a pointer, never evidence: open the locator.
       dbcx corpus map [<scope>] [--refresh]                 state/CORPUS_MAP.json: per unit the ranked sources and anchors (query = unit name, the
                                                             unit's fields in state/scopes.json, run config retrieval.topics; retrieval.boost
                                                             {"<scope>|*": [SRC-id | input path prefix]} always maps a source); the inventory reads
                                                             the whole corpus, a consolidation the union of the units. Writes the strategy per unit to
                                                             state/RETRIEVAL.json: `read` while the mapped sources fit retrieval.read_budget_tokens, else
                                                             `search`. Rebuilt when the corpus, the scopes or the settings changed (also by `render brief`).
       dbcx corpus map --set <scope> read|search             the orchestrator's override of one unit's strategy (kept across rebuilds)
       dbcx corpus metrics                                   refresh the counts in state/RETRIEVAL.json: corpus calls per agent (stamped by the hook in
                                                             state/RETRIEVAL.calls.jsonl) and the critics' `found_via` per unit
       dbcx retrieval assess [--lang en|de] [--json]       after `corpus index` (run skill, prepare): semantic not-needed | available | declined |
                                                             recommended - only `recommended` prints the question for the user (engine/spec/retrieval_ask.<lang>.json)
       dbcx retrieval enable                                 the user said yes: install model2vec (setup's install path), fetch the model, build the
                                                             meaning-based index; a failure keeps keyword search, records `failed` and a learning (B)
       dbcx retrieval decline                                the user said no: engagement.json retrieval.semantic = declined (+ date, corpus size);
                                                             asked again only once the corpus has more than doubled
Search index: corpus/search/keyword.json (+ blocks/<SRC>.json per-source cache keyed by sha256; semantic/ when a backend exists). The hook
treats `dbcx corpus search|map|grep|show` and corpus/search/** as reading the corpus evidence base.
"""
import os, sys, json, re, glob, hashlib, time, zlib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CORPUS_DIR, ENGINE, TOOLS, RUN, P, PP, PROJECT_FILE, RUN_FILE, SCOPES_PATH, STATUS_PATH, project, scope_info, is_consolidated, all_critics, load_json, read_json, atomic_save_json, relp, evidence_bases, role_may_read, role_of_agent
import retrieval_backends as RB

INDEX = os.path.join(CORPUS_DIR, "index.json"); TEXT = os.path.join(CORPUS_DIR, "text"); PROFILE = os.path.join(CORPUS_DIR, "PROFILE.json")
SEARCH = os.path.join(CORPUS_DIR, "search"); BLOCKS = os.path.join(SEARCH, "blocks"); KEYWORD = os.path.join(SEARCH, "keyword.json"); SEMANTIC = os.path.join(SEARCH, "semantic")
MAP_PATH = P("state", "CORPUS_MAP.json"); STRATEGY_PATH = P("state", "RETRIEVAL.json"); CALLS_PATH = P("state", "RETRIEVAL.calls.jsonl")
ANCHOR = re.compile(r"<!-- (SRC-\d+#.+?) -->")
MAP_REL, MAP_MAX, MAP_ANCHORS = 0.3, 20, 3   # a source is mapped when its score reaches 30 % of the unit's best source; at most 20 sources, 3 anchors each
MAP_SEM_REL, MAP_SEM_DEPTH = 0.8, 200          # semantic side of the map: a source whose best block reaches 80 % of the best cosine, among the top 200 blocks
MAP_SEM_LANG_FLOOR = 0.6                       # several corpus languages: each language is cut against its own best cosine, if that reaches 60 % of the overall best

def jload(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError): return d
def jsave(p, d): os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] if os.path.exists(p) else None

def semantic():
    try: return RB.semantic_backend()
    except Exception: return None   # offline, proxy, missing package: keyword search only, silently

# ------------------------------------------------------------------ profile + index (run by `dbcx corpus index`)
def blocks_of(sid):
    """[(locator, text)] of one source: every anchor comment opens a block (the text after it on the same line belongs to it)"""
    fp = os.path.join(TEXT, f"{sid}.md"); out = []; cur = None; buf = []
    if not os.path.exists(fp): return out
    for l in open(fp, encoding="utf-8"):
        m = ANCHOR.match(l)
        if m:
            if cur: out.append((cur, "".join(buf)))
            cur, buf = m.group(1), [l[m.end():]]
        elif cur: buf.append(l)
    if cur: out.append((cur, "".join(buf)))
    return out

DE = set("der die das und ist nicht mit für fuer auf den von zu wird werden ein eine bei sind dem des auch oder sich".split())
EN = set("the and is not with for on of to will be an at are this that from by which have has".split())
def language(text):
    ws = re.findall(r"[a-zäöüß]+", text[:80000].lower()); n = len(ws) or 1
    de = sum(w in DE for w in ws) / n; en = sum(w in EN for w in ws) / n
    if max(de, en) < 0.02: return "unknown"
    if min(de, en) > 0.4 * max(de, en): return "mixed (de/en)"
    return "de" if de > en else "en"

DATE = re.compile(r"(?<!\d)(20\d\d)[-_.](0[1-9]|1[0-2])(?:[-_.](0[1-9]|[12]\d|3[01]))?(?!\d)")
def date_of(path, text):
    for s, src in ((path, "path"), (text[:3000], "text")):
        m = DATE.search(s or "")
        if m: return "-".join(x for x in m.groups() if x), src
    return None, None

def sketch(text, k=64):
    """bottom-k sketch of the word 5-shingles: near-duplicate check without keeping the text"""
    ws = RB.tokens(text); return sorted({zlib.crc32(" ".join(ws[i:i + 5]).encode()) for i in range(max(1, len(ws) - 4))})[:k]
def similarity(a, b, k=64):
    u = sorted(set(a) | set(b))[:k]; sa, sb = set(a), set(b)
    return sum(1 for h in u if h in sa and h in sb) / len(u) if u else 0.0

def build(quiet=False):
    """corpus/search/ (incremental per source sha256) and corpus/PROFILE.json from corpus/index.json + corpus/text/"""
    idx = jload(INDEX, {"sources": {}}); os.makedirs(BLOCKS, exist_ok=True); caches = {}; redone = 0
    for sid, e in idx["sources"].items():
        if e.get("quality") == "unextractable": continue
        cp = os.path.join(BLOCKS, f"{sid}.json"); c = jload(cp)
        if not c or (c.get("sha"), c.get("revision")) != (e.get("sha256"), e.get("revision")):
            bl = blocks_of(sid); txt = "".join(t for _, t in bl); d, ds = date_of(e.get("path", ""), txt)
            c = {"sha": e.get("sha256"), "revision": e.get("revision"), "tokens": max(1, round(len(txt) / 4)), "language": language(txt), "date": d, "date_from": ds,
                 "sketch": sketch(txt), "blocks": [[loc, len(RB.tokens(t)), RB.term_counts(t)] for loc, t in bl]}
            jsave(cp, c); redone += 1
        caches[sid] = c
    for f in glob.glob(os.path.join(BLOCKS, "*.json")):
        if os.path.basename(f)[:-5] not in caches: os.remove(f)
    kw = RB.merge(caches); jsave(KEYWORD, kw)
    sb = semantic(); sem = None
    if sb:   # the backend embeds new and revised sources into its own files; a failure leaves keyword search alone
        try:
            st = jload(os.path.join(SEMANTIC, "state.json"), {}) or {}; st = st if st.get("name") == sb.name else {"name": sb.name, "sources": {}}
            for sid, c in caches.items():
                if st["sources"].get(sid) != c["sha"]: sb.index(sid, c["sha"], blocks_of(sid), SEMANTIC); st["sources"][sid] = c["sha"]
            for sid in [s for s in st["sources"] if s not in caches]: sb.drop(sid, SEMANTIC); st["sources"].pop(sid)
            jsave(os.path.join(SEMANTIC, "state.json"), st); sem = sb.name
        except Exception as ex: sem = None; print(f"semantic index skipped ({type(ex).__name__}); keyword search only", file=sys.stderr) if not quiet else None
    srcs = {}; ids = sorted(caches)
    for sid, e in idx["sources"].items():
        c = caches.get(sid) or {}
        srcs[sid] = {"title": e.get("title"), "path": e.get("path"), "type": e.get("type"), "revision": e.get("revision"), "tokens": c.get("tokens", 0), "language": c.get("language"),
                     "quality": e.get("quality"), "origin": e.get("origin"), "client_approved": e.get("client_approved"), "date": c.get("date"), "blocks": len(c.get("blocks") or [])}
        if e.get("aliases"): srcs[sid]["identical_copies"] = e["aliases"]
    for i, a in enumerate(ids):   # near-duplicates: the same document extracted twice (a PDF and its Word original, a re-saved export)
        for b in ids[i + 1:]:
            ta, tb = caches[a]["tokens"], caches[b]["tokens"]
            if min(ta, tb) >= 50 and min(ta, tb) / max(ta, tb) >= 0.75 and similarity(caches[a]["sketch"], caches[b]["sketch"]) >= 0.8: srcs[b].setdefault("near_duplicate_of", a)
    def count(key, f=lambda v: v): return dict(Counter(str(f(v.get(key))) for v in srcs.values()))
    prof = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "totals": {"sources": len(srcs), "tokens": sum(v["tokens"] for v in srcs.values()), "blocks": kw["N"],
            "by_language": count("language"), "by_quality": count("quality", lambda q: (q or "?").split(" ")[0]), "by_origin": count("origin", lambda o: o or "unknown"),
            "identical_copies": sum(len(v.get("identical_copies") or []) for v in srcs.values()), "near_duplicates": sum(1 for v in srcs.values() if v.get("near_duplicate_of"))},
            "search": {"keyword": {"blocks": kw["N"], "terms": len(kw["postings"])}, "semantic": sem}, "sources": srcs}
    open(PROFILE, "w", encoding="utf-8").write(json.dumps(prof, ensure_ascii=False, indent=1))
    if not quiet: print(f"search index: {kw['N']} blocks over {len(caches)} sources ({redone} re-tokenised), ~{prof['totals']['tokens']} tokens -> {relp(SEARCH, RUN)}/, {relp(PROFILE, RUN)}")
    return prof

def ensure_index():
    """the search index of an indexed corpus (built here when an older run indexed the corpus without one); False without a corpus"""
    if not os.path.exists(INDEX): return False
    if not os.path.exists(KEYWORD) or not os.path.exists(PROFILE) or os.path.getmtime(KEYWORD) < os.path.getmtime(INDEX): build(quiet=True)
    return True

# ------------------------------------------------------------------ search
def snippet(text, q, n=200):
    lines = [" ".join(l.split()) for l in text.splitlines() if l.strip() and not l.lstrip().startswith("<!--")] or [" ".join(text.split())]
    best = max(lines, key=lambda l: len(set(RB.tokens(l)) & q))
    return best if len(best) <= n else best[:n - 1] + "…"

def search(queries, scope=None, k=10, cfg=None):
    """[{locator, score, title, snippet, units, queries}] best first. Several queries (a list, or one text with one query per line) run in
    ONE call - the semantic backend is loaded once - each query's keyword and semantic rankings fused by reciprocal rank, the queries' lists
    interleaved (best rank across the queries, so each query keeps its own top hits), each hit naming the queries that found it"""
    qs = [q.strip() for x in ([queries] if isinstance(queries, str) else queries) for q in str(x).splitlines() if q.strip()]
    if not qs or not ensure_index(): return []
    kw = jload(KEYWORD); prof = jload(PROFILE, {}) or {}; allowed = None
    if scope:
        allowed = {s["id"] for s in unit_entry(scope, cfg)["sources"]} or None
    sb = semantic(); n = max(3 * k, 30); lists = []
    for text in qs:
        ranked = [(kw["blocks"][bi][0], s) for bi, s in sorted(RB.bm25(kw, RB.term_counts(text), allowed=allowed).items(), key=lambda x: -x[1])[:n]]
        if sb:
            try:
                sem = [(loc, s) for loc, s in sb.search(text, n, SEMANTIC) if allowed is None or loc.split("#", 1)[0] in allowed]
                ranked = RB.fuse([ranked, sem]) if ranked else sem
            except Exception: pass
        lists.append(ranked)
    ranked = lists[0] if len(lists) == 1 else RB.interleave(lists)
    found = {}
    for qi, x in enumerate(lists):
        for loc, _ in x: found.setdefault(loc, []).append(qs[qi])
    units = {}
    for u, e in ((jload(MAP_PATH, {}) or {}).get("units") or {}).items():
        if e.get("kind") == "unit":
            for s in e["sources"]: units.setdefault(s["id"], []).append(u)
    terms = {t for q in qs for t in RB.tokens(q)}; out, texts = [], {}
    for loc, s in ranked[:k]:
        sid = loc.split("#", 1)[0]
        if sid not in texts: texts[sid] = dict(blocks_of(sid))
        out.append({"locator": loc, "score": round(s, 4), "title": ((prof.get("sources") or {}).get(sid) or {}).get("title", ""), "snippet": snippet(texts[sid].get(loc, ""), terms), "units": units.get(sid, []), "queries": found.get(loc, [])})
    return out

LANG_NAMES = {"de": "German", "en": "English"}
def corpus_languages():
    """the corpus languages from corpus/PROFILE.json, most sources first (a mixed source counts for both)"""
    c = {}
    for lang, n in (((jload(PROFILE, {}) or {}).get("totals") or {}).get("by_language") or {}).items():
        for x in (("de", "en") if lang.startswith("mixed") else (lang,)):
            if x in LANG_NAMES: c[x] = c.get(x, 0) + n
    return [LANG_NAMES[x] for x, _ in sorted(c.items(), key=lambda kv: -kv[1])]

# ------------------------------------------------------------------ corpus map + strategy per unit
def settings(cfg):
    r = (cfg or {}).get("retrieval") or {}
    return {"read_budget_tokens": int(r.get("read_budget_tokens") or 60000), "topics": r.get("topics") or [], "boost": r.get("boost") or {}}

def unit_parts(name, entry, st):
    """(text, weight) of a unit's map query: its name, title fields, group, meta values and the run's retrieval.topics"""
    return ([(re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("-", " ").replace("_", " "), 3)] + [(entry.get(k), 2) for k in ("title", "label", "display", "description")]
            + [(entry.get("group"), 1)] + [(v, 1) for v in (entry.get("meta") or {}).values()] + [(t, 0.5) for t in st["topics"]])

def unit_query(name, entry, st):
    w = {}
    for text, weight in unit_parts(name, entry, st):
        for t in RB.tokens(text if isinstance(text, str) else ""): w[t] = max(w.get(t, 0), weight)
    return w

def unit_text(name, entry, st): return " ".join(t for t, _ in unit_parts(name, entry, st) if isinstance(t, str) and t.strip())

def rank_sources(kw, prof, query, boost=(), text=None, sb=None):
    """the unit's sources: summed score of each source's best anchor blocks; mapped when >= MAP_REL of the best source, a boosted source always.
    With a semantic backend (sb + the query `text`) the semantic ranking of the sources (best block cosine, >= MAP_SEM_REL of the best) is fused
    with the keyword ranking by reciprocal rank, as in search(): a source in the other language reaches the unit too"""
    srcs = prof.get("sources") or {}
    def boosted(sid): p = srcs.get(sid, {}).get("path") or ""; return any(b == sid or p == b or p.startswith(str(b).rstrip("/") + "/") for b in boost)
    per = {}
    for bi, s in RB.bm25(kw, query).items():
        loc = kw["blocks"][bi][0]; per.setdefault(loc.split("#", 1)[0], []).append((s, loc))
    for sid, e in srcs.items():
        if e.get("quality") != "unextractable" and boosted(sid): per.setdefault(sid, [])
    scored = [(sum(s for s, _ in sorted(h, reverse=True)[:MAP_ANCHORS]), sid, [loc for _, loc in sorted(h, reverse=True)[:MAP_ANCHORS]]) for sid, h in per.items()]
    best = max((s for s, _, _ in scored), default=0.0); out = []
    for s, sid, anchors in scored:
        b = boosted(sid)
        if not b and (best <= 0 or s < MAP_REL * best): continue
        out.append({"id": sid, "title": srcs.get(sid, {}).get("title"), "score": round(s + (best if b else 0), 3), "tokens": srcs.get(sid, {}).get("tokens", 0), "anchors": anchors})
    out = sorted(out, key=lambda x: (-x["score"], x["id"]))
    if not (sb and text): return out[:MAP_MAX]
    try: hits = sb.search(text, MAP_SEM_DEPTH, SEMANTIC)
    except Exception: return out[:MAP_MAX]
    sem = {}
    for loc, c in hits:
        sid = loc.split("#", 1)[0]
        if sid in srcs and srcs[sid].get("quality") != "unextractable": sem.setdefault(sid, []).append((c, loc))
    top = max((h[0][0] for h in sem.values()), default=0.0)
    def langs(sid): l = srcs[sid].get("language") or ""; return ["de", "en"] if l.startswith("mixed") else [l] if l in ("de", "en") else []
    found = {l for sid in sem for l in langs(sid)}
    def cut(sid):   # the model prefers the query's language, so with several corpus languages each is cut against its own best
        if len(found) < 2 or not langs(sid): return MAP_SEM_REL * top
        ltop = max(h[0][0] for x, h in sem.items() if set(langs(x)) & set(langs(sid)))
        return MAP_SEM_REL * ltop if ltop >= MAP_SEM_LANG_FLOOR * top else float("inf")   # a language with nothing relevant gets no semantic candidates
    sem_rank = sorted(((h[0][0], sid) for sid, h in sem.items() if top > 0 and h[0][0] >= cut(sid)), key=lambda x: (-x[0], x[1]))
    by = {x["id"]: x for x in out}
    for c, sid in sem_rank:
        by.setdefault(sid, {"id": sid, "title": srcs[sid].get("title"), "tokens": srcs[sid].get("tokens", 0), "anchors": [loc for _, loc in sem[sid][:MAP_ANCHORS]]})
    fused = RB.fuse([[(x["id"], x["score"]) for x in out], [(sid, c) for c, sid in sem_rank]])
    groups = {}   # several languages among the candidates: round robin by language (best first within each) before the MAP_MAX cut
    for sid, f in fused:
        for l in langs(sid) or [next((langs(x)[0] for x, _ in fused if langs(x)), "")]: groups.setdefault(l, []).append((sid, f))
    if len([l for l in groups if l]) >= 2: fused = RB.interleave(list(groups.values()))
    return [dict(by[sid], score=round(f, 4)) for sid, f in fused][:MAP_MAX]

def all_sources(prof):
    return [{"id": sid, "title": e.get("title"), "score": 0, "tokens": e.get("tokens", 0), "anchors": []} for sid, e in sorted((prof.get("sources") or {}).items()) if e.get("quality") != "unextractable"]

def fingerprint(cfg):
    return {"corpus": sha_file(INDEX), "scopes": sha_file(SCOPES_PATH), "settings": hashlib.sha256(json.dumps(settings(cfg), sort_keys=True).encode()).hexdigest()[:16]}

def build_map(cfg=None, quiet=False):
    """state/CORPUS_MAP.json + state/RETRIEVAL.json; None without an indexed corpus"""
    if not ensure_index(): return None
    cfg = cfg or project(); m = cfg["_method"]; st = settings(cfg); kw = jload(KEYWORD); prof = jload(PROFILE, {}) or {}; units = {}; sb = semantic()
    for name, e in ((load_json(SCOPES_PATH, {}) or {}).get("scopes") or {}).items():
        if e.get("skip"): continue
        units[name] = {"kind": "unit", "sources": rank_sources(kw, prof, unit_query(name, e, st), list(st["boost"].get(name, [])) + list(st["boost"].get("*", [])), unit_text(name, e, st), sb)}
    union = {}
    for e in units.values():
        for s in e["sources"]:
            if s["id"] not in union or s["score"] > union[s["id"]]["score"]: union[s["id"]] = s
    inv = (m.get("inventory") or {}).get("scope")
    if inv: units[inv] = {"kind": "inventory", "sources": all_sources(prof)}
    for c in (m.get("consolidations") or {}):
        units[c] = {"kind": "consolidation", "sources": sorted(union.values(), key=lambda x: -x["score"]) if union else all_sources(prof)}
    total = (prof.get("totals") or {}).get("tokens", 0)
    for e in units.values(): e["mapped_tokens"] = sum(s["tokens"] for s in e["sources"])
    mp = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "fingerprint": fingerprint(cfg), "corpus_tokens": total, "units": units}
    atomic_save_json(MAP_PATH, mp)
    old = (load_json(STRATEGY_PATH, {}) or {}).get("units") or {}; ru = {}
    for u, e in units.items():
        o = old.get(u) or {}; engine = "read" if e["sources"] and e["mapped_tokens"] <= st["read_budget_tokens"] else "search"
        ru[u] = {"kind": e["kind"], "strategy": o["strategy"] if o.get("set_by") == "orchestrator" else engine, "engine_strategy": engine, "set_by": o.get("set_by") or "engine",
                 "mapped_tokens": e["mapped_tokens"], "share": round(e["mapped_tokens"] / total, 3) if total else 0.0, "sources": len(e["sources"])}
    atomic_save_json(STRATEGY_PATH, {"updated_at": mp["built_at"], "read_budget_tokens": st["read_budget_tokens"], "corpus_tokens": total, "semantic": (prof.get("search") or {}).get("semantic"), "units": ru})
    metrics(cfg)
    if not quiet: print(f"corpus map: {len(units)} unit(s), " + ", ".join(f"{k} {sum(1 for x in ru.values() if x['strategy'] == k)}" for k in ("read", "search")) + f" (read budget {st['read_budget_tokens']} tokens) -> {relp(MAP_PATH, RUN)}, {relp(STRATEGY_PATH, RUN)}")
    return mp

def current_map(cfg=None):
    """the map, rebuilt when the corpus, the scopes or the settings changed since it was written"""
    cfg = cfg or project(); mp = load_json(MAP_PATH, {}) or {}
    if not mp or mp.get("fingerprint") != fingerprint(cfg) or not os.path.exists(STRATEGY_PATH): mp = build_map(cfg, quiet=True) or {}
    return mp

def unit_entry(scope, cfg=None):
    """the map entry of a scope; a scope outside the map (a method brief kind's chunk) maps like a consolidation, else from its name"""
    cfg = cfg or project(); mp = current_map(cfg); e = (mp.get("units") or {}).get(scope)
    if e: return e
    if not ensure_index(): return {"kind": "unit", "sources": [], "mapped_tokens": 0}
    prof = jload(PROFILE, {}) or {}
    if is_consolidated(scope, cfg["_method"]):
        us = [x for x in (mp.get("units") or {}).values() if x.get("kind") == "unit"]
        srcs = list({s["id"]: s for x in us for s in x["sources"]}.values()) if us else all_sources(prof)
    else: srcs = rank_sources(jload(KEYWORD), prof, unit_query(scope, {}, settings(cfg)), (), unit_text(scope, {}, settings(cfg)), semantic())
    return {"kind": "consolidation" if is_consolidated(scope, cfg["_method"]) else "unit", "sources": srcs, "mapped_tokens": sum(s["tokens"] for s in srcs)}

def strategy_of(scope, cfg=None):
    cfg = cfg or project(); e = unit_entry(scope, cfg); r = ((load_json(STRATEGY_PATH, {}) or {}).get("units") or {}).get(scope)
    return (r or {}).get("strategy") or ("read" if e["sources"] and e["mapped_tokens"] <= settings(cfg)["read_budget_tokens"] else "search"), e

def set_strategy(scope, value):
    if value not in ("read", "search"): sys.exit("strategy is read | search")
    current_map(); d = load_json(STRATEGY_PATH, {}) or {}; u = (d.get("units") or {}).get(scope)
    if not u: sys.exit(f"{scope} is not in the corpus map ({relp(MAP_PATH, RUN)})")
    u.update({"strategy": value, "set_by": "orchestrator"}); atomic_save_json(STRATEGY_PATH, d); print(f"{scope}: strategy {value} (set by the orchestrator, kept across rebuilds)")

# ------------------------------------------------------------------ metrics (calls stamped by the hook, found_via from the critics)
def call_kind(tool, ti):
    """the retrieval tool a sub-agent call uses on the corpus (search | grep | read | map) or None"""
    ti = ti or {}; corpus_text = re.escape(os.path.join("corpus", "text").replace(os.sep, "/"))
    if tool == "Bash":
        cmd = (ti.get("command") or "").replace("\\", "/")
        m = re.search(r"(?:\bdbcx(?:\.py)?[\"']?\s+corpus|\bcorpus\.py|\bretrieval\.py)\s+(search|map|grep|show)\b", cmd)
        if m: return {"show": "read"}.get(m.group(1), m.group(1))
        if re.search(r"\b(?:grep|rg)\b[^|;&]*" + corpus_text, cmd): return "grep"
        if re.search(r"\b(?:cat|sed|head|tail|less)\b[^|;&]*" + corpus_text + r"/SRC-", cmd): return "read"
        return None
    path = (ti.get("file_path") or ti.get("path") or "").replace("\\", "/")
    if tool == "Read" and re.search(corpus_text + r"/SRC-[^/]+\.md$", path): return "read"
    if tool in ("Grep", "Glob") and re.search(r"(?:^|/)corpus(?:/text)?/?$|" + corpus_text, path): return "grep"
    return None

def stamp(run, agent, agent_id, tool, ti):
    """hook (PreToolUse of an allowed sub-agent call): one line per corpus retrieval call -> state/RETRIEVAL.calls.jsonl"""
    k = call_kind(tool, ti)
    if not k: return
    with open(os.path.join(run, "state", "RETRIEVAL.calls.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": agent, "id": agent_id or "", "via": k}) + "\n")

def metrics(cfg=None):
    """counts in state/RETRIEVAL.json: calls per unit and agent, the critics' found_via per unit"""
    d = load_json(STRATEGY_PATH, {}) or {}
    if not d.get("units"): return d
    cfg = cfg or project(); m = cfg["_method"]; owner = {}
    for u in d["units"]:
        try: owner[scope_info(u, m)[4]] = u
        except Exception: pass
        for c in all_critics(cfg): owner[f"critic-{c}-{u}"] = u
    conv = {x.get("conversation_id"): x.get("agent") for x in ((load_json(STATUS_PATH, {}) or {}).get("in_flight") or []) if x.get("conversation_id")}
    for u in d["units"].values(): u["calls"] = {}; u["found_via"] = {}
    other = {}
    try: lines = open(CALLS_PATH, encoding="utf-8").read().splitlines()
    except OSError: lines = []
    for l in lines:
        try: r = json.loads(l)
        except ValueError: continue
        a = r.get("agent") or ""; a = a if a in owner else conv.get(r.get("id"), a); u = owner.get(a)
        tgt = d["units"][u]["calls"] if u else other; c = tgt.setdefault(a, {}); c[r["via"]] = c.get(r["via"], 0) + 1
    for u, e in d["units"].items():
        for f in glob.glob(P("analysis", "gauntlet", u, "round*-*.json")):
            x = jload(f, {})
            for row in (x.get("scores") if isinstance(x, dict) else None) or []:
                v = row.get("found_via") if isinstance(row, dict) else None
                if v: e["found_via"][v] = e["found_via"].get(v, 0) + 1
    d["other_calls"] = other; atomic_save_json(STRATEGY_PATH, d); return d

# ------------------------------------------------------------------ brief blocks (render.py: `render brief ... --out`)
def corpus_bases(cfg):
    cd = os.path.realpath(CORPUS_DIR)
    return [eb for eb in evidence_bases(cfg) if any(cd == r or cd.startswith(r.rstrip(os.sep) + os.sep) for r in eb.get("abs_roots", []))]

def how_to(role):
    """engine/briefs/retrieval.md: the general part, plus the client critic's part after the `<!-- critic-client -->` line"""
    with open(os.path.join(ENGINE, "briefs", "retrieval.md"), encoding="utf-8") as f: gen, _, crit = f.read().partition("<!-- critic-client -->")
    ls = corpus_languages() or ["German", "English"]   # a query in each corpus language plus a synonym is the largest recall gain
    langs = (f"this corpus is {' and '.join(ls)}" if len(ls) > 1 else f"this corpus is {ls[0]}; add the other language where the client's material mixes them") + " - one query per language and one with a synonym"
    return (gen.strip() + ("\n" + crit.strip() if role == "critic-client" else "")).replace("{corpus_languages}", langs).strip()

def sources_block(cfg, scope):
    strat, e = strategy_of(scope, cfg); total = (jload(PROFILE, {}) or {}).get("totals", {}).get("tokens", 0); prof = (jload(PROFILE, {}) or {}).get("sources") or {}
    head = f"## SOURCES FOR THIS UNIT (strategy: {strat}; mapped ~{e['mapped_tokens']} of ~{total} tokens in the corpus)"
    if not e["sources"]: return head + "\nNo source mentions this unit by name - work search-first (`dbcx corpus search`) and grep for its identifiers."
    rule = ("read these sources in full (corpus/text/<id>.md) before you write; search and grep the rest of the corpus for counter-evidence and what they miss."
            if strat == "read" else "too much to read in full: start from these sources and anchors, work search-first, and open each anchor you rely on.")
    rows = [f"- {s['id']} {s.get('title') or ''} (~{s['tokens']} tokens" + "".join(f"; {k} {prof.get(s['id'], {}).get(k)}" for k in ("language", "origin", "date") if prof.get(s["id"], {}).get(k)) + ")"
            + (" - anchors: " + ", ".join("#" + a.split("#", 1)[1] for a in s["anchors"]) if s["anchors"] else "") for s in e["sources"][:MAP_MAX if strat == "read" else 12]]
    return head + "\n" + rule + "\n" + "\n".join(rows)

def brief_blocks(cfg, txt, agent):
    """HOW TO FIND EVIDENCE (+ SOURCES FOR THIS UNIT for a brief with a SCOPE row) before the brief's last line, for a role that reads the
    corpus evidence base; the brief is unchanged without an indexed corpus or for a role without corpus access"""
    if not os.path.exists(INDEX): return txt
    m = cfg["_method"]; role = role_of_agent(agent, m)
    if not any(role_may_read(role, eb, agent, m) for eb in corpus_bases(cfg)): return txt
    sc = re.search(r"^SCOPE: (\S+)", txt, re.M)
    add = "\n\n".join([how_to(role)] + ([sources_block(cfg, sc.group(1))] if sc else []))
    head, sep, tail = txt.rpartition("\n\nFollow your agent definition.")
    return head + "\n\n" + add + sep + tail if sep else txt + "\n\n" + add

# ------------------------------------------------------------------ the semantic backend: assessed by the engine, confirmed by the user (prepare)
def decision_file(): return PP(PROJECT_FILE) if os.path.exists(PP(PROJECT_FILE)) else P(RUN_FILE)

def assess(cfg=None, lang=None):
    """not-needed (no corpus, or the whole corpus fits the read budget) | available (model2vec + model installed: used silently) |
    declined (the user said no, or the install failed, for a corpus at most twice today's size) | recommended (ask the user once:
    `message` in the user's language from engine/spec/retrieval_ask.<lang>.json)"""
    cfg = cfg or project(); st = settings(cfg); prof = jload(PROFILE, {}) if ensure_index() else {}
    t = (prof or {}).get("totals") or {}; tokens = t.get("tokens", 0); docs = sum(1 for v in ((prof or {}).get("sources") or {}).values() if v.get("tokens"))
    r = {"corpus_tokens": tokens, "documents": docs, "pages": round(tokens / 500), "read_budget_tokens": st["read_budget_tokens"], "package": RB.package_ready(), "model": RB.model_ready()}
    d = (cfg.get("retrieval") or {}); prior = d.get("semantic") if d.get("semantic") in ("declined", "failed") else None
    if not prof: r["semantic"] = "not-needed"; r["reason"] = "no indexed corpus"
    elif r["package"] and r["model"]: r["semantic"] = "available"
    elif tokens <= st["read_budget_tokens"]: r["semantic"] = "not-needed"; r["reason"] = "the whole corpus fits the read budget"
    elif prior and tokens <= 2 * int(d.get("corpus_tokens") or 0): r["semantic"] = "declined"; r["reason"] = f"{prior} on {d.get('decided_on')} at ~{d.get('corpus_tokens')} tokens; asked again once the corpus is more than twice that size"
    else:
        r["semantic"] = "recommended"; r["download_mb"] = RB.DOWNLOAD_MB + (0 if r["package"] else 22)   # the model (+ ~22 MB of wheels when the package is missing)
        lang = lang or (cfg.get("languages") or {}).get("chat") or "en"; fp = os.path.join(ENGINE, "spec", f"retrieval_ask.{lang}.json")
        tpl = jload(fp if os.path.exists(fp) else os.path.join(ENGINE, "spec", "retrieval_ask.en.json"), {})
        r["message"] = tpl["message"].format(documents=docs, pages=r["pages"], download_mb=r["download_mb"])
    return r

def record_decision(value, cfg=None):
    """retrieval.semantic = declined | failed (+ date and corpus size) in engagement.json (run.json of a single-run project)"""
    a = assess(cfg); fp = decision_file(); d = jload(fp, {}) or {}
    d.setdefault("retrieval", {}).update({"semantic": value, "decided_on": time.strftime("%Y-%m-%d"), "corpus_tokens": a["corpus_tokens"], "documents": a["documents"]})
    with open(fp, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
    return fp

def say(msg): print(msg, flush=True)

def enable(cfg=None):
    """install the soft package into the plugin's Python environment (setup.py's install path), fetch the model, build the semantic
    index; on any failure: keyword search stays, the decision `failed` is recorded and a learning goes to the maintainer (section B)"""
    import setup, subprocess
    try:
        target, info = setup.install()
        if "model2vec" not in info.get("have", []): raise RuntimeError("the search package could not be installed")
        if not RB.model_ready():
            r = subprocess.run([target, os.path.join(TOOLS, "retrieval_backends.py"), "fetch-model"], text=True)
            if r.returncode != 0: raise RuntimeError("the search model could not be downloaded or converted")
        else: say("step: the search model is already on this computer")
        say("step: building the meaning-based index of the corpus")
        r = subprocess.run([target, os.path.join(TOOLS, "retrieval.py"), "build"], text=True, cwd=RUN, env=dict(os.environ, DBCX_RUN=RUN))
        if r.returncode != 0: raise RuntimeError("the meaning-based index could not be built")
        say("ready: meaning-based search is on for this engagement")
        return True
    except (Exception, SystemExit) as e:
        why = str(e).replace("FAILED: ", "")[-300:] or type(e).__name__
        try: record_decision("failed", cfg)
        except Exception: pass
        subprocess.run([sys.executable, os.path.join(TOOLS, "learn.py"), "add", "--section", "B", "--title", "semantic search could not be set up", "--what", f"`dbcx retrieval enable` failed: {why}",
                        "--evidence", f"{sys.platform}, Python {sys.version.split()[0]}, model {RB.MODEL_REPO}@{RB.MODEL_REV[:7]}", "--generalises", "machines behind a proxy, offline or on a platform without wheels run with keyword search only",
                        "--proposal", "check the download path (huggingface.co + its CDN, HTTPS_PROXY / SSL_CERT_FILE) and the wheel availability for this platform", "--touches", "engine/tools/retrieval_backends.py"],
                       cwd=RUN, capture_output=True, text=True)
        say(f"Meaning-based search could not be set up ({why.splitlines()[-1] if why.strip() else 'unknown error'}); the run continues with keyword search.")
        return False

# ------------------------------------------------------------------ CLI (dispatched from corpus.py)
def main(a):
    cmd = a[0]; js = "--json" in a; a = [x for x in a if x != "--json"]
    def opt(f, d=None): return a[a.index(f) + 1] if f in a and a.index(f) + 1 < len(a) else d
    if cmd == "profile":
        if not ensure_index(): sys.exit("no corpus yet (dbcx corpus index)")
        prof = jload(PROFILE)
        if js: print(json.dumps(prof, ensure_ascii=False, indent=1)); return
        t = prof["totals"]; print(f"{t['sources']} sources, ~{t['tokens']} tokens, {t['blocks']} blocks; languages {t['by_language']}; quality {t['by_quality']}; origin {t['by_origin']}; identical copies {t['identical_copies']}, near-duplicates {t['near_duplicates']}")
        for sid, v in prof["sources"].items(): print(f"{sid:8s} {v['tokens']:>8d} {str(v.get('language') or '-'):14s} {str(v.get('quality') or '-')[:12]:12s} {str(v.get('origin') or '-'):12s} {str(v.get('date') or '-'):10s} {v.get('path')}" + (f"  (near-duplicate of {v['near_duplicate_of']})" if v.get("near_duplicate_of") else ""))
    elif cmd == "search":
        qs = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] not in ("--scope", "--k")]
        if not qs: sys.exit("usage: dbcx corpus search \"<query>\" [\"<query>\" ...] [--scope <id>] [--k N] [--json]")
        res = search(qs, opt("--scope"), int(opt("--k", 10)))
        if js: print(json.dumps(res, ensure_ascii=False, indent=1)); return
        many = len([q for x in qs for q in x.splitlines() if q.strip()]) > 1
        for r in res: print(f"{r['locator']}  [{r['title']}]" + (f"  (mapped to: {', '.join(r['units'])})" if r["units"] else "") + (f"  (found by: {' | '.join(r['queries'])})" if many else "") + f"\n    {r['snippet']}")
        print(f"{len(res)} result(s) - snippets are pointers: open the locator before you cite it")
    elif cmd == "map":
        if "--set" in a: set_strategy(opt("--set"), a[a.index("--set") + 2] if a.index("--set") + 2 < len(a) else ""); return
        cfg = project(); pos = [x for x in a[1:] if not x.startswith("--")]
        mp = build_map(cfg, quiet=bool(pos)) if "--refresh" in a or not pos else current_map(cfg)
        if not mp: sys.exit("no corpus yet (dbcx corpus index)")
        if pos:
            strat, e = strategy_of(pos[0], cfg)
            if js: print(json.dumps(dict(e, strategy=strat), ensure_ascii=False, indent=1)); return
            print(f"{pos[0]}: strategy {strat}, ~{e['mapped_tokens']} tokens mapped")
            for s in e["sources"]: print(f"  {s['id']} {s.get('title') or ''} (~{s['tokens']} tokens, score {s['score']})" + (": " + ", ".join(s["anchors"]) if s["anchors"] else ""))
        elif js: print(json.dumps(mp, ensure_ascii=False, indent=1))
    elif cmd == "assess":
        r = assess(lang=opt("--lang"))
        if js: print(json.dumps(r, ensure_ascii=False, indent=1)); return
        print(f"semantic: {r['semantic']}" + (f" ({r['reason']})" if r.get("reason") else "")); print(r["message"]) if r.get("message") else None
    elif cmd == "enable": sys.exit(0 if enable() else 3)
    elif cmd == "decline": print(f"recorded: keyword search only for this engagement ({relp(record_decision('declined'), RUN)})")
    elif cmd == "build": build()
    elif cmd == "metrics":
        d = metrics()
        print(json.dumps({u: {k: v[k] for k in ("strategy", "share", "calls", "found_via") if k in v} for u, v in (d.get("units") or {}).items()}, ensure_ascii=False, indent=1) if d.get("units") else "no corpus map yet (dbcx corpus map)")
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main(sys.argv[1:] or ["help"])
