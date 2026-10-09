#!/usr/bin/env python3
"""Own methods: list, derive, describe (method card), check, confirm, and the personal
library. An own method lives in <engagement>/methods/<name>/ (a single-run project: <run>/methods/); the personal library
<DBCX_HOME>/methods/<name>/ is a source for copies, never a lookup root.

Usage:
  dbcx method list [--json]                                  plugin, engagement and library methods with origin, version, origin type
  dbcx method new <name> --from <plugin method>              derived copy into <engagement>/methods/<name>/ + a method card pre-filled from it
  dbcx method card <name> [--init] [--set <path>=<json>]... [--postpone <path> --why "<why>"]... [--render] [--json]
                                                             create / answer / render the card (method-card.json -> METHOD-CARD.md); a
                                                             path is dotted with list indexes (result.workbooks[0].title; index = length appends);
                                                             a value that is no JSON is taken as text; any change resets `confirmed`
  dbcx method check <name> [--json]                          the method pack (files, keys, kinds, md_to_json --generate, build_excel --check,
                                                             discover, briefs, placeholders, critics, topics, guard keys, engine version, name
                                                             clash) and the card's completeness; exit 1 on an error
  dbcx method confirm <name>                                 the user said yes to the rendered card: confirmed = true (refused while a slot is open)
  dbcx method confirm <name> --guard                         the user accepted the guard-key warnings of `method check` (stored with their hash)
  dbcx method generate <name> [--closest <plugin method>]    card -> method pack (engine/tools/method_generate.py)
  dbcx method save <name>                                    the engagement's method (with its card) into the personal library (after a clean check)
  dbcx method install <name> [--update]                      a library method into this engagement (origin noted: library + library version);
                                                             --update replaces the copy, never while a run of it in this engagement is open
Sub-agents get none of new|card|generate|confirm|save|install (hook H14).
"""
import json, os, re, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import method_guard
from common import METHODS, KNOWLEDGE, LIBRARY_METHODS_DIR, TOOLS, CLI, PP, read_json, fwd
from runtime import package_version

CARD, CARD_MD = "method-card.json", "METHOD-CARD.md"
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$"); TOPIC_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
PHASE_TYPES = ("simple", "gauntlet", "scopes", "build", "gate")
GENERIC = ("list", "workbook", "folders", "inventory")
ENGINE_BRIEFS = os.path.join(common.ENGINE, "briefs")

def engine_mm(v=None):
    """MAJOR.MINOR of a version text ('0.13.2', '0.13.dev' -> '0.13'), None when it has none"""
    m = re.match(r"^(\d+)\.(\d+)", str(v if v is not None else package_version())); return f"{m.group(1)}.{m.group(2)}" if m else None
def vkey(v): return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:3]) or (0,)
def plugin_names(): return {n for n in os.listdir(METHODS) if os.path.exists(os.path.join(METHODS, n, "method.json"))} if os.path.isdir(METHODS) else set()
def personas():
    d = os.path.join(KNOWLEDGE, "personas"); return {f[:-3] for f in os.listdir(d) if f.endswith(".md") and f != "README.md"} if os.path.isdir(d) else set()

def project_dir():
    """the engagement folder (a single-run project: the run) - own methods are written only inside one"""
    if any(os.path.exists(PP(f)) for f in (common.PROJECT_FILE, common.RUN_FILE)): return common.PROJECT_DIR
    sys.exit(f"no engagement here: run this inside the engagement folder (engagement.json; `{CLI} init engagement` creates one)")
def own_dir(name):
    if not SLUG_RE.match(name or ""): sys.exit(f"method name '{name}' must match ^[a-z][a-z0-9-]*$ (e.g. supplier-assessment)")
    return os.path.join(project_dir(), "methods", name)
def find_dir(name):
    """a method folder for check / confirm: a path, $DBCX_METHOD_DIR (its folder name), this engagement's methods/<name>, or the plugin's"""
    if os.path.isdir(name) and any(os.path.exists(os.path.join(name, f)) for f in ("method.json", CARD)): return os.path.abspath(name)
    proj = common.PROJECT_DIR if any(os.path.exists(PP(f)) for f in (common.PROJECT_FILE, common.RUN_FILE)) else None
    env = os.path.abspath(os.path.expanduser(os.environ["DBCX_METHOD_DIR"])) if os.environ.get("DBCX_METHOD_DIR") else None
    for d in ([env] if env and os.path.basename(env) == name else []) + ([os.path.join(proj, "methods", name)] if proj else []) + [os.path.join(METHODS, name)]:
        if any(os.path.exists(os.path.join(d, f)) for f in ("method.json", CARD)): return d
    sys.exit(f"unknown method '{name}' (`{CLI} method list`)")
def is_plugin(d): return os.path.realpath(os.path.dirname(d)) == os.path.realpath(METHODS)
def load_method(d):
    m = read_json(os.path.join(d, "method.json")); m["_dir"] = d; m["_source"] = "plugin" if is_plugin(d) else "engagement"; m.setdefault("name", os.path.basename(d)); return m
def save_json(p, data):
    with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=1); f.write("\n")
def origin_type(d, m=None):
    """card origin.type, else method.json origin (text or {type}), plugin for a plugin method"""
    if is_plugin(d): return "plugin"
    c = read_json(os.path.join(d, CARD), {}) if os.path.exists(os.path.join(d, CARD)) else {}
    o = (c.get("origin") or {}).get("type") if isinstance(c.get("origin"), dict) else None
    mo = (m if m is not None else (read_json(os.path.join(d, "method.json"), {}) if os.path.exists(os.path.join(d, "method.json")) else {})).get("origin")
    return o if isinstance(o, str) else (mo.get("type") if isinstance(mo, dict) else mo) or "custom"

def origin_stamp(m):
    """run.json keys of `dbcx init run`: method_origin (custom | derived | plugin) and, for a copy installed from the library, its version"""
    if m.get("_source") == "plugin": return {"method_origin": "plugin"}
    out = {"method_origin": origin_type(m["_dir"], m)}; o = m.get("origin") if isinstance(m.get("origin"), dict) else {}
    if o.get("installed_from") == "library": out.update(method_installed_from="library", method_library_version=o.get("library_version", ""))
    return out

# ------------------------------------------------------------------ the method card (BRIEF-WAVE2 Contract 1 + amendment 1)
S, ANY = "text", "any"
def L(item, least=0): return ("list", item, least)
def E(*v): return ("enum", v)
FIELD = {"name": S, "type": E("s", "i", "n", "b", "l"), "enum?": L(ANY)}
IMPLICIT_FIELDS = {   # Amendment 2: the fields a topic form brings without naming them (the generator imports this; one definition)
    "rating": [{"name": "score", "type": "i"}, {"name": "rationale", "type": "s"}, {"name": "evidence", "type": "l"}, {"name": "confidence", "type": "s"}],
    "table": [{"name": "evidence", "type": "l"}]}
IMPLICIT_ASPECT = {"name": "aspect", "type": "s"}   # a rating topic without fields of its own rates one aspect per row
def implicit_fields(topic):
    """the implicit fields of a card topic by its form (IMPLICIT_FIELDS; + aspect for a rating topic without fields)"""
    form = topic.get("form") if isinstance(topic, dict) else None; own = topic.get("fields") if isinstance(topic, dict) else None
    return list(IMPLICIT_FIELDS.get(form, [])) + ([IMPLICIT_ASPECT] if form == "rating" and not (isinstance(own, list) and own) else [])
LANG_RE = re.compile(r"^[a-z]{2}(?:-[A-Za-z]{2})?$")
def is_text(v, empty=False):
    """a card text: a string, or {"<lang>": text} (Amendment 2)"""
    if isinstance(v, str): return empty or bool(v.strip())
    return isinstance(v, dict) and bool(v) and all(LANG_RE.match(str(k)) and isinstance(x, str) and (empty or x.strip()) for k, x in v.items())
def txt(v):
    """an identifier-like card text as one string (a {lang: text} gives its en text, else the first)"""
    return v if isinstance(v, str) else (v.get("en") or next(iter(v.values()), None)) if isinstance(v, dict) and is_text(v, True) else None
SPEC = {
    "card_version": E(1), "name": "slug", "display": S, "description": S, "languages": L(E("en", "de"), 1),
    "origin": {"type": E("custom", "derived"), "closest": "method?"},
    "fit": {"decision": S, "client_material": L(S, 1), "external_standards": L(S, 1), "table_shaped": "bool"},
    "result": {"personas": L("persona", 1), "key_questions": L(S, 1),
               "workbooks": L({"id": S, "title": S, "readers": L("persona", 1),
                               "sheets": L({"name": S, "row": S, "columns": L({"name": S, "kind": E("fact", "assessment", "formula"), "from": "from?", "formula?": S}, 1)}, 1),
                               "aggregates": L({"what": S, "formula_hint": S}), "parameters": L({"name": S, "default": ANY, "meaning": S})}, 1)},
    "unit": {"noun": S, "noun_plural": S, "source": E(*GENERIC, "tool"), "source_config": "source_config", "dependencies": E("independent", "dependent", "grouped"), "names_public": "bool"},
    "evidence": {"consumes": L({"type": S, "required": "bool"}), "client_reviewer": {"persona": S},
                 "standard_critics": L({"id": "critic_id", "persona": S, "sources": {"packs": L(S), "domains": L(S), "reference": "bool"}, "scores": "scores"}, 1),
                 "hints?": L(S)},
    "topics": L({"id": "topic_id", "title": S, "form": E("text", "list", "table", "rating"), "fields?": L(FIELD), "anchors?": "anchors", "rows?": E("one", "many")}, 1),   # required by form (Amendment 2): fields for table / rating, anchors for rating
    "analyst_rules": L(S), "init_fields": L({"key": S, "hint": S, "default": ANY}),
    "consolidations": L({"workbook": S, "view": E("ranking", "gap-list", "totals", "conflicts", "target-picture", "other"), "judgements": L(S)}),
    "run_options": {"lean": "bool", "human_step": "text?", "produces": L(S), "forbidden_terms": L(S)},
    "postponed": L(S), "storage": E("engagement", "library"), "confirmed": "bool",
    "library_cleared?": L(S)}   # the client-specific slots `method save` cleared in the library copy (answer them for the engagement)
NO_POSTPONE = ("card_version", "name", "confirmed")
SOURCE_CONFIG = {"workbook": ({"sheet", "column"}, {"group_column", "header_row"}), "folders": ({"root", "per"}, set()),
                 "inventory": (set(), {"table", "name", "group", "depends_on", "size"}), "tool": (set(), {"tool"})}

def postponed(v): return isinstance(v, dict) and set(v) == {"postponed"} and isinstance(v["postponed"], str) and v["postponed"].strip()
def skeleton(spec=SPEC):
    return {k.rstrip("?"): skeleton(v) if isinstance(v, dict) else None for k, v in spec.items() if not k.endswith("?")}

def card_issues(card, d=None):
    """(open slots, invalid slots as 'path: reason', warnings) of a card against Contract 1; a slot is answered when it holds a valid value
    or {"postponed": "<why>"}"""
    opened, bad, warn = [], [], []
    pn, ps = plugin_names(), personas()
    def walk(v, spec, path):
        if v is None:
            if spec in (ANY, "method?", "from?", "text?"): return
            opened.append(path); return
        if postponed(v) and path not in NO_POSTPONE: return
        if isinstance(spec, dict):
            if not isinstance(v, dict): bad.append(f"{path}: must be an object with {', '.join(k.rstrip('?') for k in spec)}"); return
            for k, sp in spec.items():
                key = k.rstrip("?")
                if (key in v and v[key] is not None) or not k.endswith("?"): walk(v.get(key), sp, f"{path}.{key}" if path else key)
            warn.extend(f"{path + '.' if path else ''}{k}: not a slot of the card (ignored)" for k in v if k not in {x.rstrip('?') for x in spec})
        elif isinstance(spec, tuple) and spec[0] == "list":
            if not isinstance(v, list): bad.append(f"{path}: must be a list"); return
            if len(v) < spec[2]: (opened.append(path) if not v else bad.append(f"{path}: needs at least {spec[2]} entries")); return
            for i, x in enumerate(v): walk(x, spec[1], f"{path}[{i}]")
        elif isinstance(spec, tuple) and spec[0] == "enum":
            if v not in spec[1]: bad.append(f"{path}: must be one of {', '.join(map(str, spec[1]))} (got {json.dumps(v)})")
        elif spec in (S, "text?"):
            if not is_text(v, spec == "text?"): bad.append(f'{path}: must be a text (or {{"<lang>": text}})')
        elif spec == "bool":
            if not isinstance(v, bool): bad.append(f"{path}: must be true or false")
        elif spec == "slug":
            if not isinstance(v, str) or not SLUG_RE.match(v): bad.append(f"{path}: must match ^[a-z][a-z0-9-]*$")
        elif spec == "method?":
            if v not in pn: bad.append(f"{path}: '{v}' is not a plugin method ({', '.join(sorted(pn))}) or null")
        elif spec == "persona":
            if not isinstance(v, str) or not ({v, v.replace("_", "-")} & ps): bad.append(f"{path}: '{v}' is not a persona of knowledge/personas ({', '.join(sorted(ps))})")
        elif spec in ("critic_id", "topic_id"):
            if not isinstance(v, str) or not (common.CRITIC_ID_RE if spec == "critic_id" else TOPIC_RE).match(v): bad.append(f"{path}: must match ^[a-z][a-z0-9-]*$")
        elif spec == "from?":
            if not isinstance(v, str) or not v.strip(): bad.append(f"{path}: must be <topic id>.<field>, <topic id> (text / list topic), inventory.<field>, <view>.<field> or null")
        elif spec == "scores":
            tp = v.get("topics") if isinstance(v, dict) else None
            if v != "all" and not (isinstance(tp, list) and tp and all(isinstance(t, str) and t.strip() for t in tp)): bad.append(f'{path}: must be "all" or {{"topics": ["<topic id>", ...]}}')
        elif spec == "anchors":
            if not isinstance(v, dict) or not v or not all(re.fullmatch(r"\d+", str(k)) and 0 <= int(k) <= 10 and isinstance(x, str) and x.strip() for k, x in v.items()):
                bad.append(f'{path}: must be {{"0": "...", "5": "...", "10": "..."}} (score anchors 0-10 with a text each)')
        elif spec == "source_config":
            pass   # checked with unit.source below
    if not isinstance(card, dict): return [], ["the card is not a JSON object"], []
    walk(card, SPEC, "")
    # cross-references, only between answered slots
    def ans(*p):
        v = card
        for k in p: v = v.get(k) if isinstance(v, dict) else None
        return None if v is None or postponed(v) else v
    topics = [t for t in ans("topics") or [] if isinstance(t, dict)]; tids = [t.get("id") for t in topics if isinstance(t.get("id"), str)]
    for i, t in enumerate(topics):   # Amendment 2: completeness by form
        if t.get("form") in ("table", "rating") and t.get("fields") is None: opened.append(f"topics[{i}].fields")
        if t.get("form") == "rating" and t.get("anchors") is None: opened.append(f"topics[{i}].anchors")
    fields = {t["id"]: {txt(f.get("name")) for f in (t.get("fields") if isinstance(t.get("fields"), list) else []) + implicit_fields(t) if isinstance(f, dict)}
              for t in topics if isinstance(t.get("id"), str) and not postponed(t.get("fields"))}
    form = {t["id"]: t.get("form") for t in topics if isinstance(t.get("id"), str)}
    views = {c.get("view") for c in ans("consolidations") or [] if isinstance(c, dict) and isinstance(c.get("view"), str)}
    for x in sorted({t for t in tids if tids.count(t) > 1 and t}): bad.append(f"topics: id '{x}' used twice")
    wbs = [w for w in ans("result", "workbooks") or [] if isinstance(w, dict)]; wids = [txt(w.get("id")) for w in wbs if txt(w.get("id"))]
    for x in sorted({w for w in wids if wids.count(w) > 1 and w}): bad.append(f"result.workbooks: id '{x}' used twice")
    for i, w in enumerate(wbs):
        for j, sh in enumerate(w.get("sheets") or [] if isinstance(w.get("sheets"), list) else []):
            for k, c in enumerate((sh or {}).get("columns") or [] if isinstance((sh or {}).get("columns"), list) else []):
                f = c.get("from") if isinstance(c, dict) else None
                where = f"result.workbooks[{i}].sheets[{j}].columns[{k}].from"
                if not isinstance(f, str) or not f.strip() or not topics: continue
                t, fld = f.split(".", 1) if "." in f else (f, None)
                if fld is not None and (t == "inventory" or t in views): continue   # Amendment 2: an inventory field, a consolidation view's field
                if fld is None and t == "summary": continue   # the summary text section every generated kind has (method_generate)
                if t not in tids: bad.append(f"{where}: topic '{t}' is not in topics ({', '.join(tids)})" + (f"; views: {', '.join(sorted(views))}" if views else "")); continue
                if fld is None and form.get(t) not in ("text", "list"): bad.append(f"{where}: topic '{t}' is a {form.get(t)} topic - name its field (<topic id>.<field>)")
                elif fld is not None and t in fields and fld not in fields[t]: bad.append(f"{where}: topic '{t}' has no field '{fld}' (fields: {', '.join(sorted(x for x in fields[t] if x))})")
    for i, c in enumerate(ans("consolidations") or []):
        if isinstance(c, dict) and txt(c.get("workbook")) and wids and txt(c["workbook"]) not in wids: bad.append(f"consolidations[{i}].workbook: '{c['workbook']}' is not a workbook id ({', '.join(map(str, wids))})")
    crit = [c for c in ans("evidence", "standard_critics") or [] if isinstance(c, dict)]; cids = [c.get("id") for c in crit if isinstance(c.get("id"), str)]
    for x in sorted({c for c in cids if cids.count(c) > 1 and c}): bad.append(f"evidence.standard_critics: id '{x}' used twice")
    for i, c in enumerate(crit):
        tp = (c.get("scores") or {}).get("topics") if isinstance(c.get("scores"), dict) else None
        for t in tp or []:
            if tids and t not in tids: bad.append(f"evidence.standard_critics[{i}].scores: topic '{t}' is not in topics ({', '.join(map(str, tids))})")
        for p in ((c.get("sources") or {}).get("packs") or []) if isinstance(c.get("sources"), dict) else []:
            if isinstance(p, str) and not common.pack_dir(p): bad.append(f"evidence.standard_critics[{i}].sources.packs: '{p}' is not a knowledge pack")
    if topics and crit and not any(c.get("scores") == "all" or postponed(c.get("scores")) for c in crit):
        covered = {t for c in crit if isinstance(c.get("scores"), dict) for t in c["scores"].get("topics") or []}
        for t in tids:
            if t and t not in covered: bad.append(f"topics: '{t}' has no standard critic (add it to a critic's scores.topics, or give one critic scores \"all\")")
    src, sc = ans("unit", "source"), (card.get("unit") or {}).get("source_config") if isinstance(card.get("unit"), dict) else None
    if src in GENERIC + ("tool",) and sc is not None and not postponed(sc):
        if src == "list":
            if not isinstance(sc, list): bad.append("unit.source_config: must be a list of unit names (or []) for source list")
        else:
            need, opt = SOURCE_CONFIG[src]
            if not isinstance(sc, dict): bad.append(f"unit.source_config: must be an object for source {src} ({', '.join(sorted(need | opt))})")
            else:
                if need - set(sc): bad.append(f"unit.source_config: source {src} needs {', '.join(sorted(need - set(sc)))}")
                if set(sc) - need - opt: bad.append(f"unit.source_config: source {src} takes no {', '.join(sorted(set(sc) - need - opt))}")
                if src == "folders" and sc.get("per") not in ("folder", "document"): bad.append('unit.source_config.per: must be "folder" or "document"')
                if src == "tool" and d and not os.path.exists(os.path.join(d, "tools", f"{sc.get('tool') or 'discover'}.py")): bad.append(f"unit.source_config.tool: the method has no tools/{sc.get('tool') or 'discover'}.py")
    if d and isinstance(card.get("name"), str) and card["name"] != os.path.basename(d): bad.append(f"name: '{card['name']}' differs from the method folder '{os.path.basename(d)}'")
    if isinstance(card.get("name"), str) and card["name"] in pn: bad.append(f"name: '{card['name']}' is the name of a plugin method - an own method needs its own name")
    return opened, bad, warn

def read_card(d):
    p = os.path.join(d, CARD)
    if not os.path.exists(p): return None
    try: return read_json(p)
    except ValueError as e: return {"_malformed": f"{CARD} is no valid JSON ({e})"}

def path_tokens(path):
    toks = re.findall(r"[^.\[\]]+", path)
    if not toks or "".join(f"[{t}]" if t.isdigit() else f".{t}" for t in toks).lstrip(".").replace(".[", "[") != path.replace(".[", "[").strip(): sys.exit(f"bad card path '{path}' (e.g. result.workbooks[0].sheets[1].row)")
    return [int(t) if t.isdigit() else t for t in toks]
def set_path(card, path, value):
    toks = path_tokens(path); cur = card
    for i, t in enumerate(toks):
        last = i == len(toks) - 1; nxt = None if last else ([] if isinstance(toks[i + 1], int) else {})
        if isinstance(t, int):
            if not isinstance(cur, list): sys.exit(f"card path '{path}': '{toks[i - 1]}' is no list")
            if t > len(cur): sys.exit(f"card path '{path}': index {t} - the list has {len(cur)} entries (index {len(cur)} appends)")
            if t == len(cur): cur.append(value if last else nxt)
            elif last: cur[t] = value
            elif not isinstance(cur[t], (dict, list)): cur[t] = nxt
        else:
            if not isinstance(cur, dict): sys.exit(f"card path '{path}': '{t}' below a value that is no object")
            if last: cur[t] = value
            elif not isinstance(cur.get(t), (dict, list)): cur[t] = nxt
        if not last: cur = cur[t]

def write_card(d, card):
    """method-card.json + METHOD-CARD.md; a file whose content is unchanged is not rewritten"""
    os.makedirs(d, exist_ok=True)
    for f, text in ((CARD, json.dumps(card, ensure_ascii=False, indent=1) + "\n"), (CARD_MD, render_card(card, d))):
        p = os.path.join(d, f)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as h:
                if h.read() == text: continue
        with open(p, "w", encoding="utf-8") as h: h.write(text)

def render_card(c, d=None):
    """METHOD-CARD.md: the human rendering of method-card.json (never edited by hand)"""
    def v(x):
        if x is None: return "*open*"
        if postponed(x): return f"*postponed: {x['postponed']}*"
        if isinstance(x, dict) and is_text(x, True): return " / ".join(f"{k}: {t}" for k, t in x.items()) if len(x) > 1 else next(iter(x.values()))
        if isinstance(x, bool): return "yes" if x else "no"
        if isinstance(x, list): return ", ".join(v(i) if isinstance(i, (dict, list)) else str(i) for i in x) or "none"
        if isinstance(x, dict): return "; ".join(f"{k}: {v(i)}" for k, i in x.items()) or "none"
        return str(x)
    def g(o, *p):
        for k in p: o = o.get(k) if isinstance(o, dict) and not postponed(o) else (o if postponed(o) else None)
        return o
    def rows(x): return x if isinstance(x, list) else []
    op, bad, _ = card_issues(c, d)
    out = [f"# Method card: {v(c.get('display'))}", "", "<!-- rendered from method-card.json by `dbcx method card --render`; never edit by hand -->", "",
           f"- **Name:** {v(c.get('name'))}", f"- **Origin:** {v(g(c, 'origin', 'type'))}" + (f" (closest plugin method: {g(c, 'origin', 'closest')})" if g(c, "origin", "closest") else ""),
           f"- **Languages:** {v(c.get('languages'))}", f"- **Stored:** {v(c.get('storage'))}", f"- **Confirmed:** {v(c.get('confirmed'))}",
           f"- **Status:** " + ("complete" if not op and not bad else f"{len(op)} open, {len(bad)} invalid"), "", "## What it does", "", v(c.get("description")), "",
           "## Fit", "", f"- **Decision it supports:** {v(g(c, 'fit', 'decision'))}", f"- **Client material:** {v(g(c, 'fit', 'client_material'))}",
           f"- **External standards:** {v(g(c, 'fit', 'external_standards'))}", f"- **Result is table-shaped:** {v(g(c, 'fit', 'table_shaped'))}", "",
           "## Result", "", f"- **Readers (personas):** {v(g(c, 'result', 'personas'))}", "- **Key questions:**"]
    out += [f"  - {q}" for q in rows(g(c, "result", "key_questions"))] or [f"  - {v(g(c, 'result', 'key_questions'))}"]
    wbs = g(c, "result", "workbooks")
    if not isinstance(wbs, list): out += ["", f"Workbooks: {v(wbs)}"]
    for w in rows(wbs):
        w = w if isinstance(w, dict) else {}
        out += ["", f"### Workbook {v(w.get('id'))}: {v(w.get('title'))}", "", f"Readers: {v(w.get('readers'))}"]
        shs = w.get("sheets")
        if not isinstance(shs, list): out += [f"Sheets: {v(shs)}"]
        for sh in rows(shs):
            sh = sh if isinstance(sh, dict) else {}
            out += ["", f"**Sheet {v(sh.get('name'))}** - one row is: {v(sh.get('row'))}", "", "| Column | Kind | From | Formula |", "|---|---|---|---|"]
            out += [f"| {v(x.get('name'))} | {v(x.get('kind'))} | {v(x.get('from')) if x.get('from') is not None else '-'} | {x.get('formula') or '-'} |" for x in rows(sh.get("columns")) if isinstance(x, dict)]
            if not isinstance(sh.get("columns"), list): out += [f"| {v(sh.get('columns'))} | | | |"]
        out += ["", "Aggregates: " + ("; ".join(f"{v(x.get('what'))} ({v(x.get('formula_hint'))})" for x in rows(w.get("aggregates")) if isinstance(x, dict)) or v(w.get("aggregates"))),
                "Parameters: " + ("; ".join(f"{v(x.get('name'))} = {json.dumps(x.get('default'))} ({v(x.get('meaning'))})" for x in rows(w.get("parameters")) if isinstance(x, dict)) or v(w.get("parameters")))]
    u = c.get("unit")
    out += ["", "## Unit of analysis", "", f"- **One unit is a:** {v(g(c, 'unit', 'noun'))} (plural {v(g(c, 'unit', 'noun_plural'))})", f"- **Units come from:** {v(g(c, 'unit', 'source'))} {json.dumps(g(c, 'unit', 'source_config'), ensure_ascii=False) if g(c, 'unit', 'source_config') is not None else ''}".rstrip(),
            f"- **Dependencies between units:** {v(g(c, 'unit', 'dependencies'))}", f"- **Unit names are public:** {v(g(c, 'unit', 'names_public'))}"] if not postponed(u) else ["", "## Unit of analysis", "", v(u)]
    out += ["", "## Evidence", "", "- **Consumes:** " + ("; ".join(f"{x.get('type')} ({'required' if x.get('required') else 'optional'})" for x in rows(g(c, "evidence", "consumes")) if isinstance(x, dict)) or v(g(c, "evidence", "consumes"))),
            f"- **Client-side reviewer:** {v(g(c, 'evidence', 'client_reviewer', 'persona'))}", f"- **Hints for finding the material:** {v(g(c, 'evidence', 'hints')) if g(c, 'evidence', 'hints') is not None else 'none'}", "- **Standard-side critics:**"]
    sc = g(c, "evidence", "standard_critics")
    out += [f"  - **{v(x.get('id'))}**: {v(x.get('persona'))} - sources {v(x.get('sources'))}; scores {v(x.get('scores'))}" for x in rows(sc) if isinstance(x, dict)] or [f"  - {v(sc)}"]
    out += ["", "## Topics the analyst fills", ""]
    tps = c.get("topics")
    if not isinstance(tps, list): out += [v(tps)]
    for t in rows(tps):
        t = t if isinstance(t, dict) else {}
        out += [f"### {v(t.get('id'))}: {v(t.get('title'))} ({v(t.get('form'))})", "", "Fields: " + ("; ".join(f"{v(f.get('name'))} ({v(f.get('type'))}{', one of ' + ', '.join(map(str, f['enum'])) if isinstance(f.get('enum'), list) else ''})" for f in rows(t.get("fields")) if isinstance(f, dict)) or v(t.get("fields"))),
                *(["Score anchors: " + ("; ".join(f"{k} = {x}" for k, x in t["anchors"].items()) if isinstance(t.get("anchors"), dict) and not postponed(t.get("anchors")) else v(t.get("anchors")))] if t.get("form") == "rating" or t.get("anchors") is not None else []),
                *([f"Implicit fields: {', '.join(f['name'] for f in implicit_fields(t))}"] if implicit_fields(t) else []), ""]
    out += ["## Rules for the analyst", ""] + ([f"- {r}" for r in rows(c.get("analyst_rules"))] or [v(c.get("analyst_rules"))])
    out += ["", "## Asked at the start of a run", ""] + ([f"- `{v(x.get('key'))}`: {v(x.get('hint'))}" + (f" (default {json.dumps(x.get('default'))})" if x.get("default") is not None else "") for x in rows(c.get("init_fields")) if isinstance(x, dict)] or [v(c.get("init_fields"))])
    out += ["", "## Consolidations", ""] + ([f"- workbook {v(x.get('workbook'))}, view {v(x.get('view'))}: {v(x.get('judgements'))}" for x in rows(c.get("consolidations")) if isinstance(x, dict)] or [v(c.get("consolidations"))])
    ro = c.get("run_options")
    out += ["", "## Run options", ""] + ([f"- **Lean profile:** {v(g(c, 'run_options', 'lean'))}", f"- **Human step:** {v(g(c, 'run_options', 'human_step')) if g(c, 'run_options', 'human_step') is not None else 'none'}",
                                          f"- **Produces for later runs:** {v(g(c, 'run_options', 'produces'))}", f"- **Words the deliverables avoid:** {v(g(c, 'run_options', 'forbidden_terms'))}"] if not postponed(ro) else [v(ro)])
    if rows(c.get("library_cleared")): out += ["", "## Removed for the library", "", "Client-specific answers removed for the library - answer them for this engagement:"] + [f"- {x}" for x in c["library_cleared"]]
    out += ["", "## After the first run", ""] + ([f"- {x}" for x in rows(c.get("postponed"))] or [v(c.get("postponed"))])
    if op or bad: out += ["", "## Still open", ""] + [f"- {p}" for p in op] + [f"- {b}" for b in bad]
    return "\n".join(out).rstrip() + "\n"

def derived_card(name, src, d):
    """a card pre-filled from the copied plugin method (origin derived); slots the copy cannot answer stay open"""
    m = read_json(os.path.join(d, "method.json")); df = m.get("defaults") or {}; unit = df.get("unit") or {}
    kinds = (read_json(os.path.join(d, "kinds.json"), {}).get("kinds") or {}); sk = kinds.get((m.get("scopes") or {}).get("kind")) or {}
    langs = [l for l in ("en", "de") if os.path.exists(os.path.join(d, f"deliverables.{l}.json"))]
    gp = [p for p in (df.get("scoring") or {}).get("gate_personas") or [] if {p, p.replace("_", "-")} & personas()] or None
    def topic(s):
        fs = [{"name": n, "type": (f.get("t") if isinstance(f, dict) else f)} | ({"enum": f["enum"]} if isinstance(f, dict) and f.get("enum") else {}) for n, f in (s.get("fields") or {}).items()]
        return {"id": s["key"], "title": s.get("heading") or s["key"], "form": {"table": "table", "list": "list"}.get(s["type"], "text"), "fields": fs, "anchors": None}
    wbs = []
    for D, x in (read_json(os.path.join(d, f"deliverables.{langs[0]}.json"), {}).get("deliverables") or {} if langs else {}).items():
        shs = [{"name": s.get("name"), "row": None, "columns": [{"name": str(col.get("header") or col.get("id") or col.get("field") or "?").replace("{unit.noun}", unit.get("noun") or "Unit"), "kind": "formula" if col.get("formula") else "fact", "from": None} for col in s.get("columns") or []]}
               for s in x.get("sheets") or [] if s.get("type") == "table" and s.get("columns")]
        wbs.append({"id": D, "title": x.get("title") or D, "readers": gp, "sheets": shs, "aggregates": None, "parameters": None})
    declared = [dict(e) for e in ((m.get("critics") or {}).get("standard") or []) if isinstance(e, dict) and set(e) != {"id"}]
    crit = declared or [{"id": "standard", "persona": (m.get("briefs") or {}).get("critic_standard_persona") or "the independent expert of the external standard of this method",
                         "sources": {"packs": [], "domains": [], "reference": True}, "scores": "all"}]
    disc = str((m.get("scopes") or {}).get("discover") or "")
    c = skeleton()
    c.update({"card_version": 1, "name": name, "display": m.get("display") or name, "description": m.get("description") or None, "languages": langs or None,
              "origin": {"type": "derived", "closest": src}, "analyst_rules": None, "postponed": [], "confirmed": False,
              "topics": [topic(s) for s in sk.get("sections") or [] if isinstance(s, dict) and s.get("key") and s["key"] != "open_questions"] or None,
              "init_fields": [{"key": k, "hint": h if isinstance(h, str) else h.get("hint", k), "default": None} for k, h in (m.get("init_fields") or {}).items()],
              "consolidations": [{"workbook": x.get("deliverable"), "view": "other", "judgements": None} for x in (m.get("consolidations") or {}).values() if x.get("deliverable")]})
    c["result"].update(personas=gp, workbooks=wbs or None)
    c["unit"].update(noun=unit.get("noun"), noun_plural=unit.get("noun_plural"), names_public=bool((m.get("hook") or {}).get("scope_names_public")),
                     **({"source": disc.split(":", 1)[1], "source_config": df.get((m.get("scopes") or {}).get("state_key") or "units")} if disc.startswith("generic:") else {"source": "tool", "source_config": {"tool": disc or "discover"}}))
    c["evidence"].update(consumes=[{"type": x["type"], "required": bool(x.get("required"))} for x in (m.get("artefacts") or {}).get("consumes") or []], standard_critics=crit)
    c["run_options"].update(lean="lean" in (m.get("profiles") or {}), human_step=None, produces=[x["type"] for x in (m.get("artefacts") or {}).get("produces") or []], forbidden_terms=list((m.get("lint") or {}).get("forbidden_terms") or []))
    return c

# ------------------------------------------------------------------ check (design §3.2 / §3.3)
PH_RE = re.compile(r"\{(?:list:)?[a-z_][a-z0-9_]*(?:\.[A-Za-z0-9_]+)+\}")

def known_briefs(m):
    """role text names render.role_text reads for this method: engine roles, consolidate-<X>, method brief kinds, + .<profile> variants"""
    base = {f[:-3] for f in os.listdir(ENGINE_BRIEFS) if f.endswith(".md")} | {f"consolidate-{x}" for x in m.get("consolidations") or {}}
    base |= {(x.get("text") if isinstance(x.get("text"), str) else None) or k for k, x in (((m.get("briefs") or {}).get("extra_kinds")) or {}).items() if isinstance(x, dict)}
    return base, {"full", "lean"} | set(m.get("profiles") or {})

def topic_gaps(m, kinds):
    """'<kind>.<section>' of every claim-bearing kind no declared standard critic scores (only when every declared critic names topics)"""
    decl = [e for e in ((m.get("critics") or {}).get("standard") or []) if isinstance(e, dict)]
    if not decl or any(e.get("id") == "standard" or e.get("scores", "all") == "all" for e in decl): return []
    tops = {str(t).strip().lower() for e in decl for t in ((e.get("scores") or {}).get("topics") or [])}
    inv = m.get("inventory") or {}
    ks = [((m.get("scopes") or {}).get("kind"), [p.get("deliverable") for p in m.get("phases") or [] if p.get("type") == "scopes"])] + ([(inv.get("kind"), [p.get("deliverable") for p in m.get("phases") or [] if p.get("scope") == inv.get("scope")])] if inv else [])
    ks += [(c.get("kind"), [c.get("deliverable")]) for c in (m.get("consolidations") or {}).values()]
    out = []
    for k, ds in ks:
        if not k or k not in kinds or k.lower() in tops or any(str(D).lower() in tops for D in ds if D): continue
        for s in kinds[k].get("sections") or []:
            key = s.get("key") if isinstance(s, dict) else None
            if key and key != "open_questions" and not ({key.lower(), f"{k}.{key}".lower()} & tops): out.append(f"{k}.{key}")   # open questions are no claims
    return out

def static_checks(d, errs, warns):
    m = None; name = os.path.basename(d)
    if not os.path.exists(os.path.join(d, "method.json")): errs.append("method.json is missing" + (f" - the card is there: `{CLI} method generate {name}` after `{CLI} method confirm {name}`" if os.path.exists(os.path.join(d, CARD)) else "")); return None
    try: m = load_method(d)
    except ValueError as e: errs.append(f"method.json is no valid JSON ({e})"); return None
    own = not is_plugin(d)
    for f in ("kinds.json", "deliverables.en.json", "plan.md"):
        if not os.path.exists(os.path.join(d, f)): errs.append(f"required file {f} is missing")
    for k in ("name", "display", "version", "description", "scopes", "phases", "evidence_bases"):
        if not m.get(k): errs.append(f"method.json: required key `{k}` is missing or empty")
    if m.get("name") and m["name"] != name: errs.append(f"method.json: name '{m['name']}' differs from the folder name '{name}'")
    for i, p in enumerate(m.get("phases") or []):
        if not isinstance(p, dict) or not p.get("id") or p.get("type") not in PHASE_TYPES: errs.append(f"method.json: phases[{i}] needs an id and a type of {', '.join(PHASE_TYPES)}")
    if own:
        o = m.get("origin"); ot = o.get("type") if isinstance(o, dict) else o
        if ot not in ("custom", "derived"): errs.append('method.json: `origin` must be "custom" or "derived" (an own method says where it comes from)')
        if ot == "derived" and not (isinstance(o, dict) and (((o.get("derived_from") or {}).get("method")) or o.get("closest") in plugin_names())): errs.append("method.json: origin derived needs derived_from {method, version, plugin_version} (or closest = the plugin method)")
        e, pe = engine_mm(m.get("engine") or ""), engine_mm()
        if not e: errs.append(f"method.json: `engine` must name the engine MAJOR.MINOR it was written for (this plugin: {pe})")
        elif e != pe:
            if e.split(".")[0] != pe.split(".")[0] or vkey(e) > vkey(pe): errs.append(f"engine version mismatch: the method was written for engine {e}, this plugin is {pe} - update the plugin or adapt the method and set `engine` to {pe}")
            else: warns.append(f"the method was written for engine {e}, this plugin is {pe} - the smoke test shows whether it still runs; then set `engine` to {pe}")
    if name in plugin_names() and own or (own and m.get("name") in plugin_names()): errs.append(f"name clash: '{name}' is the name of a plugin method - give your method a new name (folder and method.json name)")
    proj = common.PROJECT_DIR if any(os.path.exists(PP(f)) for f in (common.PROJECT_FILE, common.RUN_FILE)) else None
    if own and proj and name in common.method_clashes(proj) and not any("name clash" in x for x in errs): errs.append(f"name clash: {common.method_clashes(proj)[name]} reuses a plugin method's name")
    # kinds
    kinds = {}
    if os.path.exists(os.path.join(d, "kinds.json")):
        try: kinds = read_json(os.path.join(d, "kinds.json")).get("kinds") or {}
        except (ValueError, AttributeError) as e: errs.append(f"kinds.json is no valid JSON object ({e})")
        if not isinstance(kinds, dict) or not kinds: errs.append('kinds.json: no kinds (`{"kinds": {<kind>: {...}}}`)'); kinds = {}
        need = [("scopes.kind", (m.get("scopes") or {}).get("kind"))] + ([("inventory.kind", m["inventory"].get("kind"))] if m.get("inventory") else []) + [(f"consolidations.{x}.kind", c.get("kind")) for x, c in (m.get("consolidations") or {}).items()]
        for where, k in need:
            if k and k not in kinds: errs.append(f"method.json {where}: kind '{k}' is not in kinds.json ({', '.join(kinds) or 'none'})")
            elif not k: errs.append(f"method.json {where} is missing")
        for k, v in kinds.items():
            if not isinstance(v, dict) or not isinstance(v.get("sections"), list): errs.append(f"kinds.json: kind '{k}' has no sections list")
    # discover, datasets, smoke
    disc = str((m.get("scopes") or {}).get("discover") or "")
    if disc.startswith("generic:"):
        if disc[8:] not in GENERIC: errs.append(f"scopes.discover '{disc}' is no generic provider (generic:{' | generic:'.join(GENERIC)})")
        elif disc == "generic:inventory" and not m.get("inventory"): errs.append("scopes.discover generic:inventory needs an inventory phase (method.json `inventory`)")
    elif not disc: errs.append("scopes.discover is missing (a method tool name, or generic:list | workbook | folders | inventory)")
    elif not os.path.exists(os.path.join(d, "tools", f"{disc}.py")): errs.append(f"scopes.discover '{disc}': the method has no tools/{disc}.py (or use a generic provider: generic:{' | generic:'.join(GENERIC)})")
    if not os.path.exists(os.path.join(d, "datasets.py")) and m.get("datasets") != "generic": errs.append('no datasets: add datasets.py or declare "datasets": "generic"')
    if not os.path.exists(os.path.join(d, "smoke.sh")) and not disc.startswith("generic:"): errs.append("no smoke test: add smoke.sh (the generic smoke covers only a generic discover)")
    # briefs
    known, profs = known_briefs(m)
    bd = os.path.join(d, "briefs")
    for f in sorted(os.listdir(bd)) if os.path.isdir(bd) else []:
        if not f.endswith(".md"): continue
        parts = f[:-3].split("."); role = parts[0]
        if role not in known: errs.append(f"briefs/{f}: no role reads it - role texts are {', '.join(sorted(known))} (+ .<profile>.md)")
        elif len(parts) > 1 and (len(parts) > 2 or parts[1] not in profs): errs.append(f"briefs/{f}: '{parts[1]}' is no profile of this method ({', '.join(sorted(profs))})")
    # declared critics (§3.3)
    try: dc = common.declared_standard_critics({"_method": m})
    except SystemExit as e: errs.append(str(e)); dc = []
    for x in dc:
        for p in x["sources"]["packs"]:
            if not common.pack_dir(p): errs.append(f"method.json critics.standard ({x['id']}): sources.packs '{p}' is not a knowledge pack")
    for g in topic_gaps(m, kinds): errs.append(f"topic {g} has no standard critic: add it to a critic's scores.topics in method.json critics.standard, or give one critic scores \"all\"")
    rep = method_guard.guard_report(m)
    for w in rep["warnings"]:
        if "would read client material" in w: errs.append(w)
    gw = [w for w in rep["warnings"] if "would read client material" not in w]
    if gw:
        conf = method_guard.guard_confirmation(m)
        if own and not conf: errs.append(f"guard keys looser than the plugin's methods, not yet confirmed by the user: show them the warnings below; after their yes `{CLI} method confirm {name} --guard`")
        warns.extend(("(confirmed by the user) " if own and conf else "") + w for w in gw)
    return m

def run_checks(d, m, errs, warns):
    """the checks that need a run: a throw-away run of the method per deliverable language (init, md_to_json --generate, placeholders,
    build_excel --check --all); the method is found through DBCX_METHOD_DIR, so the run lies outside every engagement"""
    langs = [l for l in ("en", "de") if os.path.exists(os.path.join(d, f"deliverables.{l}.json"))]
    tmp = tempfile.mkdtemp(prefix="dbcx-method-check-")
    env = {k: v for k, v in os.environ.items() if k not in ("DBCX_RUN", "DBCX_PROJECT", "DBCX_METHOD")}; env["DBCX_METHOD_DIR"] = d
    env["DBCX_TOOLS"] = TOOLS; env["PYTHONPATH"] = os.pathsep.join([TOOLS] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
    def tail(r): return " | ".join([l for l in (r.stderr.strip() + "\n" + r.stdout.strip()).splitlines() if l.strip()][-3:])[-600:]
    try:
        for lang in langs:
            rd = os.path.join(tmp, f"run-{lang}"); rn = dict(env, DBCX_RUN=rd)
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "init.py"), "run", "--method", os.path.basename(d), "--dir", rd, "--lang", lang, "--client", "Check Client", "--consultancy", "Check Consulting"], cwd=tmp, env=env, capture_output=True, text=True)
            if r.returncode or not os.path.exists(os.path.join(rd, "run.json")): errs.append(f"dbcx init run failed ({lang}): {tail(r)}"); return
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "md_to_json.py"), "--generate"], cwd=rd, env=rn, capture_output=True, text=True)
            if r.returncode: errs.append(f"md_to_json --generate failed: {tail(r)}"); continue
            if lang == langs[0]:
                r = subprocess.run([sys.executable, os.path.abspath(__file__), "_placeholders", d], cwd=rd, env=rn, capture_output=True, text=True)
                try: errs.extend(json.loads(r.stdout or "[]"))
                except ValueError: errs.append(f"placeholder check failed: {tail(r)}")
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "build_excel.py"), "--check", "--all"], cwd=rd, env=rn, capture_output=True, text=True)
            if r.returncode: errs.append(f"build_excel --check ({lang}) failed: {tail(r)}")
    finally: shutil.rmtree(tmp, ignore_errors=True)

def placeholders(d):
    """(inside the throw-away run) every {a.b} of the role texts, plan.md and the method's brief rows / head fields / personas / snippets that
    the run's merged configuration leaves unresolved"""
    cfg = common.project(); m = cfg["_method"]; out = []
    texts = [(f"briefs/{f}", open(os.path.join(d, "briefs", f), encoding="utf-8").read()) for f in sorted(os.listdir(os.path.join(d, "briefs"))) if f.endswith(".md")] if os.path.isdir(os.path.join(d, "briefs")) else []
    if os.path.exists(os.path.join(d, "plan.md")): texts.append(("plan.md", open(os.path.join(d, "plan.md"), encoding="utf-8").read()))
    texts += [(f"method.json briefs.rows ({r[0]})", r[1]) for r in (m.get("briefs") or {}).get("rows") or [] if len(r) > 1 and isinstance(r[1], str)]
    texts += [(f"method.json consolidations.{x}.head_fields", v) for x, c in (m.get("consolidations") or {}).items() for v in (c.get("head_fields") or {}).values() if isinstance(v, str)]
    texts += [(f"method.json critics.standard ({e.get('id')}).persona", e.get("persona")) for e in ((m.get("critics") or {}).get("standard") or []) if isinstance(e, dict) and isinstance(e.get("persona"), str)]
    texts += [(f"method.json snippets.{k}", v) for k, v in (m.get("snippets") or {}).items() if isinstance(v, str)] + [("method.json research_topics", m.get("research_topics") or "")]
    def val(k):
        v = cfg
        for p in k.split("."): v = v.get(p) if isinstance(v, dict) else None
        return v
    for where, t in texts:
        miss = sorted(set(PH_RE.findall(common.fmt(t, cfg))))
        lst = [x for x in miss if not x.startswith("{list:") and isinstance(val(x[1:-1]), list)]
        if lst: out.append(f"{where}: {', '.join(lst)} hold a list - write {', '.join('{list:' + x[1:] for x in lst)}")
        miss = [x for x in miss if x not in lst]
        if miss: out.append(f"{where}: placeholder(s) {', '.join(miss)} resolve to nothing in a run's configuration - add the key to method.json defaults (or init_fields), or fix the name")
    return out

def check(name, as_json=False):
    d = find_dir(name); errs, warns = [], []
    m = static_checks(d, errs, warns)
    card = read_card(d); op = []
    if card is not None:
        if card.get("_malformed"): errs.append(card["_malformed"])
        else:
            op, bad, cw = card_issues(card, d); warns.extend(f"card: {w}" for w in cw)
            if op: errs.append(f"card: {len(op)} slot(s) not answered: {', '.join(op)} - answer or postpone each (`{CLI} method card {os.path.basename(d)} --set <path>=<json>` / `--postpone <path> --why ...`)")
            errs.extend(f"card: {b}" for b in bad)
    elif m and not is_plugin(d) and origin_type(d, m) == "custom": warns.append(f"no method card ({CARD}) - a custom method keeps its card next to it")
    if m and not any(e.startswith(("method.json", "required file", "kinds.json", "name clash", "engine version")) for e in errs): run_checks(d, m, errs, warns)
    res = {"method": os.path.basename(d), "dir": fwd(d), "source": "plugin" if is_plugin(d) else "engagement", "errors": errs, "warnings": warns, "card_open": op}
    if as_json: print(json.dumps(res, indent=1, ensure_ascii=False))
    else:
        for e in errs: print("ERROR:", e)
        for w in warns: print("WARNING:", w)
        print(f"method check {res['method']}: {len(errs)} error(s), {len(warns)} warning(s)" + ("" if errs else f" - next: `{CLI} smoke {res['method']}`"))
    return res

# ------------------------------------------------------------------ commands
def opt(a, flag, default=None):
    return a[a.index(flag) + 1] if flag in a and a.index(flag) + 1 < len(a) else default
def opts(a, flag): return [a[i + 1] for i, x in enumerate(a[:-1]) if x == flag]

def cmd_list(a):
    proj = common.PROJECT_DIR if any(os.path.exists(PP(f)) for f in (common.PROJECT_FILE, common.RUN_FILE)) else None
    rows = []
    for n, e in common.method_index(proj).items():
        m = read_json(os.path.join(e["dir"], "method.json"), {})
        rows.append({"name": n, "where": e["source"], "version": m.get("version", ""), "origin": origin_type(e["dir"], m), "display": m.get("display", ""), "dir": fwd(e["dir"])})
    for n, d in common.method_clashes(proj).items(): rows.append({"name": n, "where": "refused", "version": "", "origin": "", "display": "own method reuses a plugin method's name", "dir": fwd(d)})
    if proj and os.path.isdir(os.path.join(proj, "methods")):   # a method that has only its card so far
        for n in sorted(os.listdir(os.path.join(proj, "methods"))):
            d = os.path.join(proj, "methods", n)
            if os.path.exists(os.path.join(d, CARD)) and not os.path.exists(os.path.join(d, "method.json")):
                c = read_card(d) or {}; rows.append({"name": n, "where": "engagement", "version": "", "origin": origin_type(d), "display": f"{c.get('display') or n} (card only, not generated yet)", "dir": fwd(d)})
    for n in sorted(os.listdir(LIBRARY_METHODS_DIR)) if os.path.isdir(LIBRARY_METHODS_DIR) else []:
        d = os.path.join(LIBRARY_METHODS_DIR, n)
        if os.path.exists(os.path.join(d, "method.json")):
            m = read_json(os.path.join(d, "method.json"), {}); rows.append({"name": n, "where": "library", "version": m.get("version", ""), "origin": origin_type(d, m), "display": m.get("display", ""), "dir": fwd(d)})
    if "--json" in a: print(json.dumps(rows, indent=1, ensure_ascii=False)); return
    for r in rows: print(f"{r['name']:24s} {r['where']:10s} {r['version']:8s} {r['origin']:8s} {r['display']}")

def cmd_new(a):
    name, src = a[0] if a else None, opt(a, "--from")
    if not name or not src: sys.exit("usage: dbcx method new <name> --from <plugin method>")
    d = own_dir(name)
    if src not in plugin_names(): sys.exit(f"--from '{src}' is not a plugin method ({', '.join(sorted(plugin_names()))})")
    if name in plugin_names(): sys.exit(f"REFUSED: '{name}' is the name of a plugin method - an own method needs its own name (e.g. '{name}-own')")
    if os.path.exists(d): sys.exit(f"REFUSED: {d} exists already - change it with `{CLI} method card {name}`, or choose another name")
    sd = os.path.join(METHODS, src); shutil.copytree(sd, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    m = read_json(os.path.join(d, "method.json")); sv = m.get("version", "")
    m.update(name=name, version="0.1.0", engine=engine_mm(), origin={"type": "derived", "derived_from": {"method": src, "version": sv, "plugin_version": package_version()}})
    sm = re.compile(r"(\bsmoke\s+)" + re.escape(src) + r"\b")
    for p in m.get("phases") or []:
        if isinstance(p.get("hint"), str): p["hint"] = sm.sub(lambda x: x.group(1) + name, p["hint"])
    save_json(os.path.join(d, "method.json"), m)
    for f, rx in (("plan.md", sm), ("smoke.sh", re.compile(r"(--method\s+)" + re.escape(src) + r"\b"))):   # the toy run initialises the copy, the plan smokes it
        p = os.path.join(d, f)
        if os.path.exists(p):
            t = open(p, encoding="utf-8").read(); open(p, "w", encoding="utf-8").write(rx.sub(lambda x: x.group(1) + name, t))
    write_card(d, derived_card(name, src, d))
    op, bad, _ = card_issues(read_card(d), d)
    print(f"created {fwd(d)} (derived from {src} {sv}) with its method card ({len(op)} slot(s) to answer)\nnext: answer the card (`{CLI} method card {name}`), change the copy, then `{CLI} method check {name}` and `{CLI} smoke {name}`")

def parse_value(s):
    try: return json.loads(s)
    except ValueError: return s

def cmd_card(a):
    name = a[0] if a and not a[0].startswith("--") else None
    if not name: sys.exit("usage: dbcx method card <name> [--init] [--set <path>=<json>]... [--postpone <path> --why <why>]... [--render] [--json]")
    proj_d = os.path.join(common.PROJECT_DIR, "methods", name)
    d = own_dir(name) if "--init" in a or not os.path.exists(os.path.join(proj_d, CARD)) else proj_d
    card = read_card(d)
    if card is not None and card.get("_malformed"): sys.exit(f"{card['_malformed']} - fix the file ({fwd(os.path.join(d, CARD))}) or delete it and start again with --init")
    if card is None:
        if "--init" not in a: sys.exit(f"{name} has no method card yet: `{CLI} method card {name} --init` (a new own method), or `{CLI} method new {name} --from <plugin method>` (a derived one)")
        if name in plugin_names(): sys.exit(f"REFUSED: '{name}' is the name of a plugin method - an own method needs its own name (e.g. '{name}-own')")
        card = skeleton(); card.update(card_version=1, name=name, origin={"type": "custom", "closest": None}, postponed=[], confirmed=False); changed = True
    else: changed = False
    sets, pps, whys = opts(a, "--set"), opts(a, "--postpone"), opts(a, "--why")
    if len(whys) != len(pps): sys.exit("every --postpone <path> needs its --why \"<why>\"")
    for s in sets:
        if "=" not in s: sys.exit(f"--set {s}: expected <path>=<json>")
        p, v = s.split("=", 1); path_tokens(p)
        if p in ("confirmed",): sys.exit(f"`confirmed` is set by `{CLI} method confirm {name}` after the user's yes")
        set_path(card, p, parse_value(v)); changed = True
    for p, w in zip(pps, whys):
        if p in NO_POSTPONE: sys.exit(f"{p} cannot be postponed")
        if not w.strip(): sys.exit(f"--postpone {p}: the --why must say why")
        set_path(card, p, {"postponed": w}); changed = True
    content = [p for p in [s.split("=", 1)[0] for s in sets] + pps if p != "storage"]   # the storage answer comes last and needs no new confirmation
    if changed and content and card.get("confirmed"): card["confirmed"] = False; print("the card changed after its confirmation: confirmed is false again (show the user the card, then `method confirm`)")
    if changed and (sets or pps): refuse_open(name, "a card change")
    if changed or "--render" in a or not os.path.exists(os.path.join(d, CARD_MD)): write_card(d, card)
    if "--render" in a and "--json" not in a: print(open(os.path.join(d, CARD_MD), encoding="utf-8").read())
    op, bad, warn = card_issues(card, d)
    if "--json" in a: print(json.dumps({"card": card, "open": op, "invalid": bad, "warnings": warn, "file": fwd(os.path.join(d, CARD)), "rendered": fwd(os.path.join(d, CARD_MD))}, indent=1, ensure_ascii=False)); return
    for b in bad: print("INVALID:", b)
    for w in warn: print("WARNING:", w)
    print(f"card {name}: {len(op)} open, {len(bad)} invalid" + (f" - open: {', '.join(op[:12])}{' ...' if len(op) > 12 else ''}" if op else "") + f"\nrendered: {fwd(os.path.join(d, CARD_MD))}")

def cmd_confirm(a):
    name = a[0] if a else sys.exit("usage: dbcx method confirm <name> [--guard]")
    d = find_dir(name)
    if is_plugin(d): sys.exit(f"{name} is a plugin method - nothing to confirm")
    refuse_open(name, "a confirmation")
    if "--guard" in a:
        m = load_method(d); rec = method_guard.confirm_guard(m)
        print(f"guard keys of {name} confirmed ({len(rec['warnings'])} warning(s) accepted, stored with their hash in {method_guard.GUARD_FILE})"); return
    card = read_card(d)
    if card is None or card.get("_malformed"): sys.exit((card or {}).get("_malformed") or f"{name} has no method card")
    op, bad, _ = card_issues(card, d)
    if op or bad: sys.exit(f"REFUSED: the card is not complete - {len(op)} open slot(s) ({', '.join(op[:8])}), {len(bad)} invalid ({'; '.join(bad[:4])}). Answer or postpone each, render it again and show it to the user.")
    card["confirmed"] = True; write_card(d, card); print(f"card {name} confirmed" + (f" - next: `{CLI} method generate {name}`" if not os.path.exists(os.path.join(d, "method.json")) else ""))

def cmd_generate(a):
    gen = os.path.join(TOOLS, "method_generate.py")
    if not os.path.exists(gen): sys.exit("`dbcx method generate` is not available in this plugin version (engine/tools/method_generate.py is missing)")
    sys.exit(subprocess.call([sys.executable, gen] + a))

def open_runs(name):
    """runs of this engagement that use the method and are not finished: STATUS.json exists (status init), no docs/FINAL_REPORT.md, and a gate
    not passed (a method without a gate: a phase not done); [] outside an engagement (a method found through DBCX_METHOD_DIR)"""
    if not any(os.path.exists(PP(f)) for f in (common.PROJECT_FILE, common.RUN_FILE)): return []
    proj = common.PROJECT_DIR; out = []
    dirs = {os.path.join(proj, r.get("dir", "")) for r in (read_json(os.path.join(proj, common.PROJECT_FILE), {}) if os.path.exists(os.path.join(proj, common.PROJECT_FILE)) else {}).get("runs") or []}
    dirs |= {os.path.join(proj, "runs", x) for x in (os.listdir(os.path.join(proj, "runs")) if os.path.isdir(os.path.join(proj, "runs")) else [])} | {proj}
    for rd in sorted(dirs):
        rj, st = os.path.join(rd, common.RUN_FILE), os.path.join(rd, "state", "STATUS.json")
        if not (os.path.exists(rj) and os.path.exists(st)) or read_json(rj, {}).get("method") != name or os.path.exists(os.path.join(rd, "docs", "FINAL_REPORT.md")): continue
        ph = (read_json(st, {}).get("phases") or {}).values(); gates = [p for p in ph if p.get("type") == "gate"]
        done = all(p.get("passed") for p in gates) if gates else all(p.get("status") == "done" or p.get("passed") for p in ph)
        if not done: out.append(fwd(os.path.relpath(rd, proj)))
    return out

def refuse_open(name, what):
    """a method folder changes between runs, never during one (the run's method hash, method_guard): refuse while a run of it is open"""
    runs = open_runs(name)
    if runs: sys.exit(f"REFUSED: {what} changes the method folder of {name}, and run(s) of it in this engagement are not finished ({', '.join(runs)}) - a method changes between runs, never during one. Finish the run first (docs/FINAL_REPORT.md), or start a new run after the change.")

def copy_method(src, dst):
    tmp = dst + ".installing"; shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    if os.path.exists(dst): shutil.rmtree(dst)
    os.replace(tmp, dst)

def library_scrub(d):
    """the client-specific answers of a library copy (card + the method.json keys generated from them) -> cleared; the cleared card
    slots. Unit names of source list, the folder root, init-field defaults, corpus hints; structure keys (sheet, column, field names) stay."""
    card = read_card(d); mp = os.path.join(d, "method.json"); m = read_json(mp, {}) if os.path.exists(mp) else {}; out = []
    key = (m.get("scopes") or {}).get("state_key") or "units"; df = m.setdefault("defaults", {})
    if card and not card.get("_malformed"):
        u = card.get("unit") if isinstance(card.get("unit"), dict) else {}; sc = u.get("source_config")
        if u.get("source") == "list" and isinstance(sc, list) and sc: u["source_config"] = []; out.append("unit.source_config (unit names)")
        if isinstance(sc, dict) and sc.pop("root", None) is not None: out.append("unit.source_config.root (folder)")
        for i, f in enumerate(card.get("init_fields") if isinstance(card.get("init_fields"), list) else []):
            if isinstance(f, dict) and f.get("default") is not None:
                f["default"] = None; out.append(f"init_fields[{i}].default ({f.get('key')})")
                cur, parts = df, str(f.get("key") or "").split(".")   # the generator wrote the default into method.json defaults: ask it at init again
                for p_ in parts[:-1]: cur = cur.get(p_) if isinstance(cur, dict) else None
                if isinstance(cur, dict) and parts[-1] in cur: cur.pop(parts[-1]); m.setdefault("init_fields", {})[f["key"]] = txt(f.get("hint")) or f["key"]
        ev = card.get("evidence") if isinstance(card.get("evidence"), dict) else {}
        if isinstance(ev.get("hints"), list) and ev["hints"]: ev["hints"] = []; out.append("evidence.hints")
        if out: card["library_cleared"] = out; write_card(d, card)
    if isinstance(df.get(key), list) and df[key]: df[key] = []; out.append(f"method.json defaults.{key} (unit names)")
    if isinstance(df.get(key), dict) and df[key].pop("root", None) is not None:
        m.setdefault("init_fields", {})[f"{key}.root"] = "the folder under input/ that holds the units (one sub-folder or document per unit)"
        if "unit.source_config.root (folder)" not in out: out.append(f"method.json defaults.{key}.root (folder)")
    sn = m.get("snippets") or {}
    if sn.pop("corpus_hints", None) is not None:
        for ks in ((m.get("briefs") or {}).get("notes_keys") or {}).values():
            if isinstance(ks, list) and "corpus_hints" in ks: ks.remove("corpus_hints")
        if "evidence.hints" not in out: out.append("method.json snippets.corpus_hints")
    if m: save_json(mp, m)
    return out

def client_hits(d):
    """lines of the library copy that name the client - the client name of engagement.json / run.json (and its core without the legal
    form) and the terms registered with `dbcx learn anonymise add` (the learnings export's mapping)"""
    import learn_export
    terms = sorted({t for t, _ in learn_export.mapping() if t and len(t.strip()) >= 3}, key=len, reverse=True)
    if not terms: return []
    rx = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(t) for t in terms) + r")(?![A-Za-z0-9])", re.I); hits = []
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in sorted(files):
            p = os.path.join(root, f); rel = fwd(os.path.relpath(p, d))
            if rx.search(rel): hits.append(f"{rel} (file name)")
            try: text = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError): continue
            hits += [f"{rel}:{i}: {line.strip()[:120]}" for i, line in enumerate(text.splitlines(), 1) if rx.search(line)]
    return hits

def cmd_save(a):
    name = a[0] if a else sys.exit("usage: dbcx method save <name>")
    d = own_dir(name)
    if not os.path.exists(os.path.join(d, "method.json")): sys.exit(f"{name} is not a method of this engagement ({fwd(d)})")
    res = check(name)
    if res["errors"]: sys.exit(f"REFUSED: `method check {name}` reports {len(res['errors'])} error(s) - fix them first; the library keeps checked methods only")
    lib = os.path.join(LIBRARY_METHODS_DIR, name); mine = read_json(os.path.join(d, "method.json")).get("version", "")
    if os.path.exists(os.path.join(lib, "method.json")):
        theirs = read_json(os.path.join(lib, "method.json")).get("version", "")
        if vkey(theirs) > vkey(mine): sys.exit(f"REFUSED: your library has {name} {theirs}, newer than this engagement's {mine} - `{CLI} method install {name} --update` first, or raise `version` in method.json")
    card = read_card(d)
    if card and not card.get("_malformed") and card.get("storage") != "library" and not open_runs(name): card["storage"] = "library"; write_card(d, card)   # the engagement copy says so too, between runs
    os.makedirs(LIBRARY_METHODS_DIR, exist_ok=True); tmp = lib + ".saving"; shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(d, tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))   # prepared beside the library copy, swapped in when clean
    lc = read_card(tmp)
    if lc and not lc.get("_malformed") and lc.get("storage") != "library": lc["storage"] = "library"; write_card(tmp, lc)
    m = read_json(os.path.join(tmp, "method.json"))
    if isinstance(m.get("origin"), dict) and m["origin"].pop("installed_from", None): m["origin"].pop("library_version", None); save_json(os.path.join(tmp, "method.json"), m)
    cleared = library_scrub(tmp); hits = client_hits(tmp)
    if hits:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(f"REFUSED: the method names the client in {len(hits)} place(s) - the library goes to other clients' engagements. Write these generically (the engagement's method stays as it is), then save again:\n  " + "\n  ".join(hits[:20]) + ("\n  ..." if len(hits) > 20 else ""))
    if os.path.exists(lib): shutil.rmtree(lib)
    os.replace(tmp, lib)
    print(f"saved {name} {mine} to your library ({fwd(lib)}); another engagement uses it with `{CLI} method install {name}`"
          + (f"\nclient-specific answers removed for the library (this engagement's copy keeps them): {', '.join(cleared)}" if cleared else ""))

def cmd_install(a):
    name = a[0] if a else sys.exit("usage: dbcx method install <name> [--update]")
    lib = os.path.join(LIBRARY_METHODS_DIR, name); d = own_dir(name)
    if not os.path.exists(os.path.join(lib, "method.json")): sys.exit(f"your library has no method '{name}' (`{CLI} method list`)")
    if name in plugin_names(): sys.exit(f"REFUSED: '{name}' is the name of a plugin method")
    lv = read_json(os.path.join(lib, "method.json")).get("version", "")
    if os.path.exists(d):
        if "--update" not in a: sys.exit(f"REFUSED: {name} is already in this engagement ({fwd(d)}) - `{CLI} method install {name} --update` replaces it between runs")
        refuse_open(name, "install --update")
        ev = read_json(os.path.join(d, "method.json"), {}).get("version", "") if os.path.exists(os.path.join(d, "method.json")) else ""
        if vkey(ev) > vkey(lv): sys.exit(f"REFUSED: this engagement's {name} {ev} is newer than your library's {lv} - `{CLI} method save {name}` keeps it")
    os.makedirs(os.path.dirname(d), exist_ok=True); copy_method(lib, d)
    m = read_json(os.path.join(d, "method.json")); o = m.get("origin") if isinstance(m.get("origin"), dict) else {"type": m.get("origin") or origin_type(d, m)}
    o.update(installed_from="library", library_version=lv, installed=time.strftime("%Y-%m-%d")); m["origin"] = o; save_json(os.path.join(d, "method.json"), m)
    print(f"installed {name} {lv} from your library into {fwd(d)}\nnext: `{CLI} method check {name}`, `{CLI} smoke {name}`, then `{CLI} init run --method {name}`")

# ------------------------------------------------------------------ doctor (information only)
def doctor_lines(proj=None):
    """'your method <x> is based on <plugin method> <v>; the plugin now has <v2>' and 'your library has a newer version of <x>'"""
    out = []
    for n, e in common.method_index(proj).items():
        if e["source"] != "engagement": continue
        m = read_json(os.path.join(e["dir"], "method.json"), {}); o = m.get("origin") if isinstance(m.get("origin"), dict) else {}
        base = o.get("derived_from") or {}
        if base.get("method") in plugin_names():
            now = read_json(os.path.join(METHODS, base["method"], "method.json"), {}).get("version", "")
            if now and now != base.get("version"): out.append(f"your method {n} is based on {base['method']} {base.get('version') or '?'}; the plugin now has {now}")
        lib = os.path.join(LIBRARY_METHODS_DIR, n, "method.json")
        if os.path.exists(lib) and vkey(read_json(lib, {}).get("version")) > vkey(m.get("version")):
            out.append(f"your library has a newer version of {n} ({read_json(lib, {}).get('version')}; this engagement has {m.get('version') or '?'}) - `dbcx method install {n} --update` between runs")
    return out

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"): print(__doc__); return
    cmd, rest = a[0], a[1:]
    if cmd == "_placeholders": print(json.dumps(placeholders(rest[0]))); return
    if cmd == "check": sys.exit(1 if check(rest[0] if rest else sys.exit("usage: dbcx method check <name> [--json]"), "--json" in rest)["errors"] else 0)
    fn = {"list": cmd_list, "new": cmd_new, "card": cmd_card, "confirm": cmd_confirm, "generate": cmd_generate, "save": cmd_save, "install": cmd_install}.get(cmd)
    if not fn: sys.exit(f"unknown method command '{cmd}' (dbcx method help)")
    fn(rest)

if __name__ == "__main__": main()
