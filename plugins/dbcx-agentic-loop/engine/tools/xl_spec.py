"""Spec patches and spec validation (`dbcx build_excel --check`) - pure functions over the merged spec.

overrides/deliverables.<lang>.json may carry, applied after the deep merge (whole-list replacement keeps working):
  "patches": [{"deliverable": "D1", "sheet": "Plattform", "column": "<id or field>", "set": {...}},     # null values delete a key
              {"deliverable": "D3", "sheet": "Anforderungen", "remove_column": "<id or field>"},
              {"deliverable": "D1", "sheet": "X", "insert_column": {...}, "after": "<id or field>"},     # no `after`: appended
              {"deliverable": "D1", "sheet": "X", "set": {...}},  {"deliverable": "D1", "set": {...}},     # sheet / deliverable keys
              {"deliverable": "D1", "sheet": "Management_Summary", "append": {"kpis": [{...}]}}]         # appends to a list key of the sheet
A table column may carry "text_by_key": {"<row key>": "<text>"} (set via insert_column or column+set): for the rows whose row key (the
sheet's `row_key`, else the first column's field) matches, the cell shows that text instead of the bound field's value. Text columns only
(a column with `formula` is a patch error); unknown row keys are a build warning.
A method's deliverables.<lang>.json may carry "profile_patches": {"<profile>": [patch, ...]} - applied for runs of that profile, before the
run's own patches. A deliverable key "not_assessed": [<table sheet>, ...] marks sheets the run does not assess: every formula over one shows
the label `not_assessed` (matrix totals too, no chart over it), the README lists the sheet as not assessed.
"""
import copy, json, re

PH_RE = re.compile(r"\{(rng|col|cell|p|pt):([^}]+)\}")
KPI_RE = re.compile(r"\{kpi:([^}]+)\}")
SHEETREF_RE = re.compile(r"(?:'([^']+)'|\b([A-Za-z_][\w.]*))!\$?[A-Z]{1,3}\$?\d")
STATUS_KEYS = ("standard", "rework", "rebuild", "neutral", "assumption")


def col_key(c): return c.get("id") or c.get("field") or ("grundlage" if c.get("grundlage") else None)


def _find(cols, key): return next((i for i, c in enumerate(cols) if c.get("id") == key), None) if any(c.get("id") == key for c in cols) else next((i for i, c in enumerate(cols) if c.get("field") == key or col_key(c) == key), None)


def _set(target, upd):
    for k, v in (upd or {}).items():
        if v is None: target.pop(k, None)
        else: target[k] = copy.deepcopy(v)


def _tbk(c, where, errors):
    t = c.get("text_by_key")
    if t is None: return
    if not isinstance(t, dict) or not all(isinstance(x, str) for x in t.values()): errors.append(f"{where}: text_by_key must map row keys to texts")
    elif "formula" in c: errors.append(f"{where}: text_by_key on a column with `formula` (text columns only)")


def apply_patches(spec):
    """-> spec with `patches` applied; problems are listed in spec['_patch_errors'] (the build refuses, --check prints them)."""
    patches = spec.pop("patches", None) or []; errors = []
    for i, p in enumerate(patches, 1):
        where = f"patch #{i} ({p.get('deliverable')}/{p.get('sheet', '-')})"
        d = (spec.get("deliverables") or {}).get(p.get("deliverable"))
        if not isinstance(d, dict): errors.append(f"{where}: unknown deliverable"); continue
        if "sheet" not in p:
            if "set" in p: _set(d, p["set"])
            else: errors.append(f"{where}: a patch without `sheet` can only `set` deliverable keys")
            continue
        sh = next((s for s in d.get("sheets", []) if s.get("name") == p["sheet"]), None)
        if sh is None: errors.append(f"{where}: no such sheet"); continue
        cols = sh.setdefault("columns", []) if sh.get("type") == "table" or any(k in p for k in ("column", "remove_column", "insert_column")) else None
        if "remove_column" in p:
            j = _find(cols, p["remove_column"])
            if j is None: errors.append(f"{where}: remove_column '{p['remove_column']}' not found")
            else: del cols[j]
        elif "insert_column" in p:
            if "after" in p:
                j = _find(cols, p["after"])
                if j is None: errors.append(f"{where}: after '{p['after']}' not found"); continue
                cols.insert(j + 1, copy.deepcopy(p["insert_column"]))
            else: cols.append(copy.deepcopy(p["insert_column"]))
            _tbk(p["insert_column"], where, errors)
        elif "column" in p:
            j = _find(cols, p["column"])
            if j is None: errors.append(f"{where}: column '{p['column']}' not found")
            else: _set(cols[j], p.get("set")); _tbk(cols[j], where, errors)
        elif "append" in p:
            for k, items in (p["append"] or {}).items():
                if not isinstance(items, list): errors.append(f"{where}: append '{k}' needs a list of items")
                elif not isinstance(sh.get(k, []), list): errors.append(f"{where}: append '{k}': the sheet's '{k}' is not a list")
                else: sh.setdefault(k, []).extend(copy.deepcopy(items))
        elif "set" in p: _set(sh, p["set"])
        else: errors.append(f"{where}: no operation (set | remove_column | insert_column | append)")
    spec["_patch_errors"] = errors
    return spec


O_RE = re.compile(r"\{o\.([A-Za-z_][\w-]*)\}")
LABEL_PREFIX_RE = re.compile(r"^\{o\.label\}\s*[:·–—-]?\s*")
REPEAT_KEYS = ("columns", "rows", "kpis", "blocks", "headers", "sheets")
LABEL_KEYS = ("header", "headers", "label", "title")


def subst_option(v, o, single=False, key=None, prefix="o"):
    """{o.<key>} -> the option's value (unknown keys stay, --check reports them); with ONE option a leading '{o.label}: ' is
    dropped from headers / labels / titles, so a single-option workbook reads as before. prefix = the placeholder prefix of a
    further repeat set ({s.<key>} for `"repeat": "scenarios", "as": "s"`; no single-item prefix dropping there)."""
    rx = O_RE if prefix == "o" else re.compile(r"\{" + re.escape(prefix) + r"\.([A-Za-z_][\w-]*)\}")
    if isinstance(v, str):
        if single and key in LABEL_KEYS and prefix == "o": v = LABEL_PREFIX_RE.sub("", v)
        return rx.sub(lambda m: str(o[m.group(1)]) if m.group(1) in o else m.group(0), v)
    if isinstance(v, list):
        out = []
        for x in v:   # {"splice": "<prefix>.<key>"}: the item's own list (e.g. a sheet's generated columns) in place of the entry
            k = x.get("splice") if isinstance(x, dict) and set(x) == {"splice"} else None
            if isinstance(k, str) and k.startswith(prefix + ".") and isinstance(o.get(k[len(prefix) + 1:]), list): out += copy.deepcopy(o[k[len(prefix) + 1:]]); continue
            out.append(subst_option(x, o, single, key, prefix))
        return out
    if isinstance(v, dict): return {(subst_option(k, o, prefix=prefix) if isinstance(k, str) else k): subst_option(x, o, single, k, prefix) for k, x in v.items()}
    return v


def expand_repeats(spec, options, sets=None):
    """Every list entry {"repeat": "options", "columns"|"rows"|"kpis"|"blocks"|"headers"|"sheets": [...]} becomes the inner items once per
    option (option by option, so each option's copies stay one consecutive block), with {o.id|label|start|pack|...} substituted in
    every string; each copied dict carries `_option: <id>`. The options land in spec["_options"]; malformed repeats in
    spec["_repeat_errors"] (validate reports them). sets = further named lists {name: {"as": prefix, "items": [dict]}} (the method's
    `datasets.spec_context`): {"repeat": "<name>", ...} copies its items with {<prefix>.<key>} substituted (no `_option` mark); a list
    entry {"splice": "<prefix>.<key>"} inside a copied item is replaced by that set item's own list (a generated column list)."""
    opts = list(options or []); single = len(opts) == 1; errors = []; sets = sets or {}

    def body(x):
        if not isinstance(x, dict) or "repeat" not in x: return None
        keys = [k for k in REPEAT_KEYS if isinstance(x.get(k), list)]
        if (x["repeat"] != "options" and x["repeat"] not in sets) or len(keys) != 1 or set(x) - {"repeat", keys[0]}:
            errors.append(f"malformed repeat {json.dumps(x, ensure_ascii=False)[:120]} (expected {{\"repeat\": \"options\"" + "".join(f" | \"{n}\"" for n in sets) + ", \"columns|rows|kpis|blocks|headers\": [...]}})"); return None
        return x[keys[0]]

    def walk(v):
        if isinstance(v, dict): return {k: walk(x) for k, x in v.items()}
        if not isinstance(v, list): return v
        out = []
        for x in v:
            items = body(x)
            if items is None: out.append(walk(x)); continue
            if x["repeat"] != "options":
                st = sets[x["repeat"]]
                for o in st.get("items") or []:
                    for it in items: out.append(subst_option(walk(it), o, prefix=st.get("as") or x["repeat"][0]))
                continue
            for o in opts:
                for it in items:
                    y = subst_option(walk(it), o, single)
                    if isinstance(y, dict): y.setdefault("_option", o["id"])
                    out.append(y)
        return out

    out = walk(spec); out["_options"] = opts; out["_repeat_errors"] = errors
    for n, st in sets.items(): out[f"_{n}"] = list(st.get("items") or [])
    return out


WHEN_RE = re.compile(r"^!?[\w.-]+$")


def when_holds(expr, flags):
    """`when` of a spec item: "flag", "!flag" or a list of them (all must hold); an unknown flag is false"""
    return all((not flags.get(x[1:])) if x.startswith("!") else bool(flags.get(x)) for x in ([expr] if isinstance(expr, str) else list(expr or [])))


def rename_sheets(spec, renames):
    """renames {old: new} (a method hook, common.spec_context): every deliverable's sheet named <old> becomes <new>, and every reference
    follows - {rng:<old>.<col>} in any string, `not_assessed` entries. Applied to the merged spec BEFORE the repeat expansion, so a
    generated sheet (e.g. a client's pass-through sheet `{p.name}`) that carries <old> after the expansion keeps it, with its references"""
    if not renames: return spec
    out = copy.deepcopy(spec)
    for d in (out.get("deliverables") or {}).values():
        if not isinstance(d, dict): continue
        for sh in d.get("sheets") or []:
            if isinstance(sh, dict) and sh.get("name") in renames: sh["name"] = renames[sh["name"]]
        if isinstance(d.get("not_assessed"), list): d["not_assessed"] = [renames.get(x, x) for x in d["not_assessed"]]
    rx = re.compile(r"\{rng:(" + "|".join(re.escape(k) for k in renames) + r")\.")
    def walk(v):
        if isinstance(v, str): return rx.sub(lambda m: "{rng:" + renames[m.group(1)] + ".", v)
        if isinstance(v, list): return [walk(x) for x in v]
        if isinstance(v, dict): return {k: walk(x) for k, x in v.items()}
        return v
    return walk(out)


def apply_when(spec, flags):
    """A dict inside a list with `when` stays only while its condition holds (the key is removed); a dict with `when_set:
    [{"when": ..., "set": {...}}]` gets the keys of every holding entry (null deletes a key). A condition that still carries an
    unresolved repeat placeholder ({o.id} ...) waits for the pass after the expansion. A spec without both keys comes back unchanged."""
    def ready(e): return "{" not in json.dumps(e)
    def walk(v):
        if isinstance(v, dict):
            out = {k: walk(x) for k, x in v.items() if k != "when_set"}
            pend = []
            for ws in v.get("when_set") or []:
                if not ready(ws.get("when")): pend.append(ws)
                elif when_holds(ws.get("when"), flags): _set(out, walk(ws.get("set") or {}))
            if pend: out["when_set"] = pend
            return out
        if isinstance(v, list):
            return [walk(x) for x in v if not (isinstance(x, dict) and "when" in x and ready(x["when"]) and not when_holds(x["when"], flags))]
        return v
    def strip(v):   # resolved `when` keys leave the item
        if isinstance(v, dict): return {k: strip(x) for k, x in v.items() if not (k == "when" and ready(x))}
        if isinstance(v, list): return [strip(x) for x in v]
        return v
    return strip(walk(spec))


def is_confidence(c): f = str(c.get("field") or ""); return f == "confidence" or f.endswith("_confidence")


def is_internal(c):
    """`internal: true`, or a confidence-type field without an explicit `internal` (see confidence_defaults) - no confidence in any edition (§1.3)."""
    return bool(c.get("internal", is_confidence(c)))


def confidence_defaults(spec):
    """Resolve the confidence default once per spec: a confidence-type column nothing refers to becomes `internal`; one a KPI,
    overview or formula counts over is a result dimension and stays (-> notes, so the method can decide)."""
    notes = []
    for key, d in (spec.get("deliverables") or {}).items():
        text = json.dumps(d)
        for sh in d.get("sheets", []):
            for c in sh.get("columns", []) if sh.get("type") == "table" else []:
                if "internal" in c or not is_confidence(c): continue
                cid = col_key(c); used = f"{{rng:{sh['name']}.{cid}}}" in text or any(f"{{{k}:{cid}}}" in json.dumps(x.get("formula", "")) for x in sh["columns"] for k in ("cell", "col"))
                c["internal"] = not used
                if used: notes.append(f"{key}/{sh['name']}: confidence column '{c.get('header')}' kept (formulas count over it; mark it `internal: true` and drop those formulas to hide it)")
    return notes


def is_evidence(c): return bool(c.get("evidence", c.get("field") == "evidence" or str(c.get("field") or "").endswith("_evidence")))


def option_blocks(cols):
    """[[first index, last index, option id]] of the consecutive columns each option repeat produced (`_option`) - only when at
    least two options share the sheet (then the sheet gets band headers and its table header moves to row 2)"""
    segs = []
    for i, c in enumerate(cols):
        o = c.get("_option")
        if o and segs and segs[-1][2] == o and segs[-1][1] == i - 1: segs[-1][1] = i
        elif o: segs.append([i, i, o])
    return segs if len({s[2] for s in segs}) >= 2 else []


def decision_budget(sh):
    """None = the per-sheet budget (style max_decision_columns); `decision_budget: "per_block"` (limit 1) or {"per_block": n} =
    at most n decision columns per option block, the common columns keep the per-sheet budget"""
    b = sh.get("decision_budget")
    if b == "per_block": return 1
    return int(b["per_block"]) if isinstance(b, dict) and "per_block" in b else None


def budget_errors(sh, decisions, maxd):
    """decisions = [(option id | None, header)] of the sheet's decision columns -> [message] under the per-block budget"""
    per = decision_budget(sh) or 1; groups = {}
    for o, h in decisions: groups.setdefault(o, []).append(str(h))
    return [f"{len(hs)} decision columns in {'the common columns' if o is None else 'option block ' + o} ({', '.join(hs)}) - at most {maxd if o is None else per}"
            for o, hs in groups.items() if len(hs) > (maxd if o is None else per)]


def _ref(v, cfg):
    """'$a.b' -> (True, value) | (False, None); without cfg (pure check) -> (True, None)"""
    if cfg is None: return True, None
    cur = cfg
    for part in v[1:].split("."):
        if not isinstance(cur, dict) or part not in cur: return False, None
        cur = cur[part]
    return True, cur


def param_table_keys(t, cfg=None):
    """({column ids}, {first-column keys} | None when the rows come from configuration the check cannot see)"""
    cols = {h.get("id") if isinstance(h, dict) else h for h in t.get("headers", [])}; rows = t.get("rows", [])
    if isinstance(rows, str): rows = _ref(rows, cfg)[1] if cfg is not None else None
    if rows is None: return cols, None
    if isinstance(rows, dict): return cols, {str(k) for k in rows}
    first = next((h.get("id") if isinstance(h, dict) else h for h in t.get("headers", [])), None)
    return cols, {str(r[0] if isinstance(r, (list, tuple)) and r else r.get(first) if isinstance(r, dict) else r) for r in rows or []}


def validate(spec, key, datasets=(), data=None, summary=None, engine_sheets=(), cfg=None):
    """-> (errors, warnings, listing). data = {dataset: rows} (optional), summary = the Management Summary Markdown (optional),
    cfg = the run configuration (optional; then "$a.b" parameter values and table rows must resolve)."""
    d = spec["deliverables"][key]; st = spec.get("style", {}) or {}; E, W, out = [], [], []
    maxd = int(st.get("max_decision_columns", 2)); sheets = d.get("sheets", [])
    tables = {s["name"]: s for s in sheets if s.get("type") == "table"}
    params = {p["name"] for s in sheets if s.get("type") == "parameters" for p in s.get("rows", [])}
    ptables = {t.get("id"): param_table_keys(t, cfg) for s in sheets if s.get("type") == "parameters" for t in s.get("tables") or []}
    internal = {(n, col_key(c)) for n, s in tables.items() for c in s.get("columns", []) if is_internal(c)}
    full_only = {(n, col_key(c)) for n, s in tables.items() for c in s.get("columns", []) if c.get("edition") == "full"}   # column `edition: full`: not in the customer edition
    customer = {s["name"] for s in sheets if (s.get("edition") or ("full" if s.get("type") == "claims" else "both")) != "full"} | set(engine_sheets)
    names = [s.get("name") for s in sheets]
    for n in {x for x in names if names.count(x) > 1}: E.append(f"{key}: sheet name '{n}' used twice")
    E += [f"{key}: {e}" for e in spec.get("_repeat_errors", [])]
    E += [f"{key}: not_assessed names no table sheet '{n}'" for n in d.get("not_assessed") or [] if n not in tables]
    rh = d.get("resolve_handover")
    if rh is not None and not (isinstance(rh, bool) or (isinstance(rh, list) and all(isinstance(x, str) for x in rh))): E.append(f"{key}: resolve_handover must be true | false | [artefact types]")
    for where, s in _option_leftovers(d, key): E.append(f"{where}: '{s[:80]}' uses {{o.*}} outside a {{\"repeat\": \"options\"}} entry (or names no option key)")

    def check(s, where, sheet=None, from_internal=False, from_full=False):
        if not isinstance(s, str): return
        for kind, arg in PH_RE.findall(s):
            if kind == "rng":
                sh, _, cid = arg.partition(".")
                if sh not in tables or not any(col_key(c) == cid for c in tables[sh]["columns"]): E.append(f"{where}: {{rng:{arg}}} names no table column")
                elif (sh, cid) in internal and not from_internal: E.append(f"{where}: {{rng:{arg}}} points at an internal column (omitted from both editions)")
                elif (sh, cid) in full_only and not from_full: E.append(f"{where}: {{rng:{arg}}} points at a column of the full edition only")
            elif kind in ("col", "cell"):
                if not sheet or not any(col_key(c) == arg for c in tables.get(sheet, {}).get("columns", [])): E.append(f"{where}: {{{kind}:{arg}}} names no column of this sheet")
                elif (sheet, arg) in internal and not from_internal: E.append(f"{where}: {{{kind}:{arg}}} points at an internal column")
                elif (sheet, arg) in full_only and not from_full: E.append(f"{where}: {{{kind}:{arg}}} points at a column of the full edition only")
            elif kind == "p" and arg not in params: E.append(f"{where}: {{p:{arg}}} names no parameter")
            elif kind == "pt":
                tid, _, rest = arg.partition("."); cid, _, k = rest.partition(".")
                if tid not in ptables or cid not in ptables[tid][0]: E.append(f"{where}: {{pt:{arg}}} names no parameter table column")
                elif k and ptables[tid][1] is not None and k not in ptables[tid][1]: E.append(f"{where}: {{pt:{arg}}}: table '{tid}' has no row '{k}'")
        for a, b in SHEETREF_RE.findall(PH_RE.sub("", s)) if s.startswith("=") else []:
            if (a or b) not in customer: E.append(f"{where}: references sheet '{a or b}', which the customer edition does not contain")

    kpis = {}
    for s in sheets:
        t = s.get("type"); n = s.get("name"); ed = s.get("edition") or ("full" if t == "claims" else "both")
        out.append(f"  [{t}] {n}" + (f"  edition={ed}" if ed != "both" else "") + (f"  tab={s['tab']}" if s.get("tab") else "") + (f"  row_key={s['row_key']}" if s.get("row_key") else "") + (f"  dataset={s['dataset']}" if s.get("dataset") else ""))
        if s.get("class") not in (None, "mgmt", "overview"): E.append(f"{key}/{n}: class must be mgmt | overview (the hygiene checks of that sheet class)")
        if t == "table":
            if str(s.get("dataset")).partition(":")[0] not in datasets and datasets: E.append(f"{key}/{n}: unknown dataset '{s.get('dataset')}'")   # "<dataset>:<argument>": one dataset, several sheets
            cols = s.get("columns", []); ids = [col_key(c) for c in cols if col_key(c)]
            for x in {i for i in ids if ids.count(i) > 1}: E.append(f"{key}/{n}: column id '{x}' used twice")
            dec = [c for c in cols if c.get("emphasis") == "decision"]; num = [c for c in cols if c.get("scale") or c.get("databar")]
            if decision_budget(s) is not None: E += [f"{key}/{n}: {e}" for e in budget_errors(s, [(c.get("_option"), c.get("header", "?")) for c in dec], maxd)]
            elif len(dec) > maxd: E.append(f"{key}/{n}: {len(dec)} decision columns ({', '.join(c.get('header', '?') for c in dec)}) - at most {maxd} per sheet")
            if s.get("decision_budget") is not None and decision_budget(s) is None: E.append(f"{key}/{n}: decision_budget must be \"per_block\" or {{\"per_block\": n}}")
            if len(num) > 1: W.append(f"{key}/{n}: {len(num)} numeric emphases ({', '.join(c.get('header', '?') for c in num)}) - only the first is rendered")
            legacy = [c.get("header") for c in cols if (c.get("colors") or c.get("threshold_colors")) and c.get("emphasis") != "decision"]
            if legacy: W.append(f"{key}/{n}: legacy colours ignored on {len(legacy)} non-decision column(s): {', '.join(map(str, legacy))}")
            evid = [col_key(c) for c in cols if is_evidence(c)]
            rows = (data or {}).get(s.get("dataset")) if data else None
            for c in cols:
                if c.get("emphasis") not in (None, "decision", "support"): E.append(f"{key}/{n}/{c.get('header')}: emphasis must be decision | support")
                for v in (c.get("status") or {}).values():
                    if v not in STATUS_KEYS: E.append(f"{key}/{n}/{c.get('header')}: status '{v}' not in {', '.join(STATUS_KEYS)}")
                check(c.get("formula"), f"{key}/{n}/{c.get('header')}", n, is_internal(c), c.get("edition") == "full")
                if c.get("edition") not in (None, "both", "full"): E.append(f"{key}/{n}/{c.get('header')}: column edition must be full (or absent)")
                if c.get("grundlage"):
                    src = c.get("grundlage_from") or evid
                    if not src: E.append(f"{key}/{n}: Grundlage column without an evidence column (mark one `evidence: true` or set grundlage_from)")
                    for x in (c.get("grundlage_from") or []) + (c.get("grundlage_text_from") or []):
                        if x not in ids: E.append(f"{key}/{n}: grundlage_from / grundlage_text_from '{x}' names no column")
                    if c.get("grundlage_key") is not None and not re.fullmatch(r"[\w.]+(@[\w.-]+)?", str(c["grundlage_key"])): E.append(f"{key}/{n}: grundlage_key '{c['grundlage_key']}' must read <field>@<suffix> (e.g. req_id@brownfield) or <field> (the field holds the key)")
                if rows and c.get("field") and not any(isinstance(r, dict) and _has(r, c["field"]) for r in rows): W.append(f"{key}/{n}/{c.get('header')}: field '{c['field']}' is in no row of dataset {s.get('dataset')}")
            if s.get("row_key") and rows and not any(isinstance(r, dict) and _has(r, s["row_key"]) for r in rows): W.append(f"{key}/{n}: row_key '{s['row_key']}' is in no row")
            for i, c in enumerate(cols):
                fl = [x for x in ("internal", "evidence", "grundlage", "wrap", "label") if (is_evidence(c) if x == "evidence" else is_internal(c) if x == "internal" else c.get(x))]
                out.append(f"      {i + 1:>2} {col_key(c) or '-':28s} {str(c.get('header', ''))[:40]:40s} {c.get('emphasis', ''):8s} {('group=' + c['group']) if c.get('group') else ''} {' '.join(fl)}")
        elif t == "mgmt":
            for k in s.get("kpis", []):
                if k.get("id"): kpis[k["id"]] = k
                for f in ("label", "formula", "note"): check(k.get(f), f"{key}/{n}/kpi {k.get('id') or k.get('label')}")
        elif t == "overview":
            for b in s.get("blocks", []):
                per = (spec.get("_options") or [{}]) if b.get("rows_are") == "options" else [None]   # rows_are options: checked once per option
                for c in b.get("columns", []):
                    for o in per: check(subst_option(c.get("formula"), o) if o is not None else c.get("formula"), f"{key}/{n}/{b.get('title')}")
                    check(c.get("header"), f"{key}/{n}/{b.get('title')}")
                for kv in b.get("rows", []) if b.get("type") == "kv" else []: check(kv.get("formula"), f"{key}/{n}/{kv.get('label')}")
                ch = b.get("chart")
                if isinstance(ch, dict):
                    for v in (ch.get("status") or {}).values():
                        if v not in STATUS_KEYS: E.append(f"{key}/{n}/{b.get('title')}: chart status '{v}' unknown")
                    if ch.get("type", "pie") not in ("pie", "doughnut", "bar", "col", "stacked"): E.append(f"{key}/{n}: chart type '{ch.get('type')}' unknown")
        elif t == "parameters":
            for p in s.get("rows", []):
                check(p.get("meaning"), f"{key}/{n}/{p.get('name')}")
                if isinstance(p.get("value"), str) and p["value"].startswith("$") and not _ref(p["value"], cfg)[0]: E.append(f"{key}/{n}/{p.get('name')}: value {p['value']} names no configuration value")
            tids = [t.get("id") for t in s.get("tables") or []]
            for t in s.get("tables") or []:
                hid = [h.get("id") if isinstance(h, dict) else h for h in t.get("headers", [])]
                if not t.get("id") or "." in str(t.get("id")) or tids.count(t.get("id")) > 1: E.append(f"{key}/{n}: parameter table id '{t.get('id')}' missing, repeated or dotted")
                if not hid or any(not x or "." in str(x) for x in hid) or len(set(hid)) < len(hid): E.append(f"{key}/{n}/{t.get('id')}: table headers need unique, dot-free ids")
                if isinstance(t.get("rows"), str) and not (t["rows"].startswith("$") and _ref(t["rows"], cfg)[0]): E.append(f"{key}/{n}/{t.get('id')}: rows {t['rows']} names no configuration value")
                out.append(f"      table {t.get('id')}: {', '.join(map(str, hid))}")
    blocks = {b["id"] for s in sheets if s.get("type") == "overview" for b in s.get("blocks", []) if b.get("id")}
    for s in (x for x in sheets if x.get("type") == "mgmt"):
        tl = s.get("tiles") or []
        if tl and not 3 <= len(tl) <= 5: W.append(f"{key}: {len(tl)} tiles (3-5 expected; at most 5 are drawn)")
        for t_ in tl:
            if t_.get("kpi") not in kpis: E.append(f"{key}: tile names unknown KPI id '{t_.get('kpi')}'")
            if t_.get("status") and t_["status"] not in STATUS_KEYS: E.append(f"{key}: tile status '{t_['status']}' unknown")
        for ch in s.get("charts") or []:
            if ch.get("block") and ch["block"] not in blocks: E.append(f"{key}: chart names unknown overview block '{ch['block']}'")
            for k in ch.get("kpis") or []:
                if k not in kpis: E.append(f"{key}: chart names unknown KPI id '{k}'")
            if ch.get("type", "bar") not in ("pie", "doughnut", "bar", "col", "stacked"): E.append(f"{key}: chart type '{ch.get('type')}' unknown")
    for k in KPI_RE.findall(summary or ""):
        if k not in kpis: E.append(f"{key}: the Management Summary text uses {{kpi:{k}}}, but no KPI has that id")
    return E, W, out


def _option_leftovers(v, where):
    """[(where, string)] with an unresolved {o.*} (overview blocks with `rows_are: "options"` substitute per row at build time)"""
    if isinstance(v, str): return [(where, v)] if O_RE.search(v) else []
    if isinstance(v, list): return [x for i, it in enumerate(v) for x in _option_leftovers(it, f"{where}[{i}]")]
    if isinstance(v, dict) and v.get("rows_are") != "options":
        return [x for k, it in v.items() for x in _option_leftovers(it, f"{where}/{v['name']}.{k}" if isinstance(v.get("name"), str) else f"{where}.{k}")]
    return []


def _has(row, path):
    cur = row
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur: cur = cur[part]
        else: return False
    return True
