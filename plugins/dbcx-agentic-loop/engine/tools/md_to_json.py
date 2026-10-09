#!/usr/bin/env python3
"""Convert an agent's Markdown analysis document into validated JSON, or (re)generate templates and schemas.

Usage:
  dbcx md_to_json <kind> <file.md> [--out file.json]   kind = an engine_spec.json or method kinds.json kind (unit | inventory | D3 | D4 | critic | gate | verifier | postpass ...)
  dbcx md_to_json --generate                            write <project>/templates/*.md and <project>/schemas/*.json from the spec

Markdown conventions (templates/*.md):
  * '## <Heading>' sections exactly as in the template (case-insensitive; text after ':' in the heading is ignored).
  * key/value sections: lines '- **key:** value'.  table sections: a Markdown table whose header uses the field names;
    column order is free, unknown columns are ignored, missing columns are empty.
  * No raw '|' inside cells (escape as backslash-pipe or use '/'; a pipe inside a `code span` is kept), no line breaks inside cells (use '<br>'). Lists use ';'. Booleans: yes/no/true/false/ja/nein/oui/non.
  * WARNING for a cell that looks like a shell command (pipe to grep/rg/find, `$(`, `&&`), for a placeholder row
    (none / - / n/a / other) and for a table section with neither rows nor a sentence under its heading saying why.
  * free text sections: everything under the heading until the next '## '.
Enum tokens stay English; free text is written in the deliverable language (run.json languages.deliverable).

Guards (v0.4): HTML comments are stripped only OUTSIDE table rows - a literal '<!--' inside a cell is kept and reported;
a table row whose cell count differs from its header is reported with file line and both counts (surplus cells are folded
into the last column, never dropped); a critic file with two rows for one claim_id is INVALID; `md_to_json critic` refuses
to overwrite a round<n>-<critic>.json whose checksum is recorded in round<n>-result.json (score_aggregate ran) unless --force.
Atomic-claim rules: WARNING per claim whose statement exceeds scoring.claim_max_statement_chars (350), carries more than
scoring.claim_max_figures (2) figures, or names more than one target / a target that is not D<n>/<Sheet>[#row ids] (or not a sheet the method lists in method.json claims.targets).
Row ids: every table row gets a stable `rid` and `claimed_by` (the ids of the claims whose target
names the row: `D2/Patched#<rid>` or `<kind>/<section>#<rid>`, several ids separated by ','); the top-level `claimed_rows` map also
lists kv sections. WARNING per target ref that names no row, per uncovered must-claim cell (method.json claims.must_claim), and when
the register exceeds the derived claim cap (must-claim rows + scoring.claim_cap_reserve, bounded by the fixed cap).
Quote column: the optional claims column `quote` is kept only when filled (a claim without one converts exactly as before);
WARNING per quote with fewer than 20 letters and digits. `dbcx evidence quotes <scope>` checks it against the cited locators.
Method rules: methods/<m>/validate.py `check(kind, data, cfg) -> [error]` runs after the row ids; its errors make the file INVALID (an entry
starting with "WARNING " is printed as a warning instead). A field or section with `omit_empty: true` is left out of the JSON while empty.
Exit code: 0 = OK (warnings possible, printed as 'WARNING ...'), 1 = INVALID / refused.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, TEMPLATES_DIR, SCHEMAS_DIR, SPEC as SPEC_DIR, spec, project, method, scope_of_path, relp, canon_number
import validate, hashlib

WARNINGS = []
def warn(msg):
    WARNINGS.append(msg)

TPL = TEMPLATES_DIR; SCHEMAS = SCHEMAS_DIR
TRUE = ("yes", "true", "ja", "y", "1", "x", "oui", "si", "sí")

def conv(v, t):
    v = (v or "").strip()
    if v in ("", "-", "null", "None", "n/a"):
        return [] if t == "l" else (0 if t == "i" else (False if t == "b" else ("" if t == "s" else None)))
    if t == "i":
        try: return int(float(v))
        except ValueError: return v
    if t == "f":   # a number with decimals (an own method's card type n)
        try: return float(v.replace(",", ".")) if v.count(",") == 1 and "." not in v else float(v)
        except ValueError: return v
    if t == "b": return v.lower() in TRUE
    if t == "l": return [x.strip() for x in v.split(";") if x.strip()]
    return v

def split_row(line):
    """cells of a table row; an escaped pipe and a pipe inside a `code span` (e.g. a regex alternation) stay in the cell"""
    line = line.strip()
    if line.startswith("|"): line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"): line = line[:-1]
    cells, cur, code, i = [], "", False, 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and line[i + 1:i + 2] == "|": cur += "|"; i += 2; continue
        if ch == "`": code = not code
        if ch == "|" and not code: cells.append(cur.strip()); cur = ""
        else: cur += ch
        i += 1
    if code: return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line)]   # an unbalanced backtick is a literal: plain split
    return cells + [cur.strip()]

_SHELL = re.compile(r"\|\s*(?:grep|rg|find|wc|awk|sed|sort|uniq|head|tail|xargs|cut)\b|\$\(|&&|(?:^|[\s`])(?:grep|rg|find|awk|sed|xargs|wc|sort|uniq|cut|head|tail)\s+-{1,2}\w")   # judged per cell: a pipe survives only inside a code span
_PLACEHOLDER = re.compile(r"^(?:[-–—]+|none|keine?s?|n/?a|nothing|nichts|not applicable|nicht zutreffend|entfällt|\(none\)|\(keine\)|tbd)\.?$", re.I)

def strip_comments(md):
    """Remove HTML comments outside table rows. Inside a table row ('|...') a literal '<!--' is content - keep it."""
    SENT = "\x00LT\x00"; out = []
    for n, line in enumerate(md.splitlines(), 1):
        if line.lstrip().startswith("|") and "<!--" in line:
            warn(f"line {n}: literal '<!--' inside a table cell kept as content (write it as '<!- -' if it was not meant literally)")
            line = line.replace("<!--", SENT)
        out.append(line)
    md = re.sub(r"<!--.*?-->", "", "\n".join(out), flags=re.S)
    return md.replace(SENT, "<!--")

def parse_sections(md):
    md = strip_comments(md)
    head, sections, cur = [], {}, None
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = re.sub(r"[:：].*$", "", m.group(1)).strip().lower(); sections[cur] = []; continue
        (sections[cur] if cur else head).append(line)
    return head, sections

def parse_kv(lines, fields):
    out = {}
    for line in lines:
        m = re.match(r"^\s*[-*]\s*\*\*([^*]+?)\*\*\s*:?\s*(.*)$", line) or re.match(r"^\s*[-*]\s*([\w ]+?)\s*:\s*(.*)$", line)
        if m: out[m.group(1).strip().rstrip(":").strip().lower().replace(" ", "_")] = m.group(2).strip()
    return {k: conv(out.get(k), f["t"]) for k, f in fields.items()}

def parse_table(lines, fields, heading=""):
    rows = [l for l in lines if l.strip().startswith("|")]
    if len(rows) < 2: return []
    hdr = [h.lower().replace(" ", "_") for h in split_row(rows[0])]
    out = []
    for r in rows[2:]:
        cells = split_row(r)
        if all(c == "" for c in cells): continue
        if len(cells) > len(hdr):   # never drop the surplus - fold it into the last column and say so
            warn(f"table '{heading}': row has {len(cells)} cells, header {len(hdr)} - surplus folded into '{hdr[-1]}': {r.strip()[:90]}")
            cells = cells[:len(hdr) - 1] + [" / ".join(c for c in cells[len(hdr) - 1:] if c)]
        elif len(cells) < len(hdr):
            warn(f"table '{heading}': row has {len(cells)} cells, header {len(hdr)} - missing cells read as empty: {r.strip()[:90]}")
        sh = next((mm for mm in (_SHELL.search(c) for c in cells) if mm), None)
        if sh: warn(f"table '{heading}': a cell looks like a shell command ({sh.group(0).strip()}): {r.strip()[:90]} - commands never go into table cells (a pipe splits the row, the reader cannot rerun it); write the result in the cell and publish the command in the analysis' commands/notes text")
        filled = [c for c in cells if c]
        if filled and all(_PLACEHOLDER.match(c) for c in filled): warn(f"table '{heading}': placeholder row ({r.strip()[:70]}) - an empty table has no rows; say why in one sentence under the heading")
        rec = dict(zip(hdr, cells + [""] * (len(hdr) - len(cells))))
        unknown = [h for h in hdr if h and h not in fields]
        if unknown and r is rows[2]: warn(f"table '{heading}': columns not in the template are ignored: {', '.join(unknown)}")
        out.append({k: conv(rec.get(k), f["t"]) for k, f in fields.items()})
    return out

def parse_text(lines): return "\n".join(lines).strip()
def parse_list(lines): return [re.sub(r"^\s*[-*]\s*", "", l).strip() for l in lines if re.match(r"^\s*[-*]\s+\S", l)]

def set_path(obj, path, val):
    parts = path.split("."); cur = obj
    for p in parts[:-1]: cur = cur.setdefault(p, {})
    cur[parts[-1]] = val

def convert(kind, md, SPEC):
    k = SPEC[kind]; head, sections = parse_sections(md)
    data = parse_kv(head, k["head"]); missing = []
    for s in k["sections"]:
        lines = sections.get(s["heading"].lower())
        if lines is None:
            if not s.get("optional"): missing.append(s["heading"])   # an optional section (e.g. Rows without claim) is not 'missing'
            lines = []
        typ = s["type"]
        if typ == "table":
            val = parse_table(lines, s["fields"], s["heading"])
            prose = [l for l in lines if l.strip() and not l.lstrip().startswith("|")]
            if not val and s["heading"].lower() in sections and not prose and s["key"] not in ("claims", "open_questions"):
                warn(f"table '{s['heading']}' has no rows and no sentence saying why - an empty table is fine (never a placeholder row), but state the reason under the heading")
        elif typ == "kv": val = parse_kv(lines, s["fields"])
        elif typ == "list": val = parse_list(lines)
        else: val = parse_text(lines)
        if s.get("omit_empty") and not val: continue   # an optional section a method added later: absent until it has content (older JSON unchanged)
        set_path(data, s["key"], val)
    # nullable strings: '' -> None; optional ints on non-aggregate rows dropped
    for s in k["sections"]:
        if s["type"] != "table": continue
        rows = data.get(s["key"], [])
        for row in rows:
            for fname, f in s["fields"].items():
                if f["t"] == "n" and row.get(fname) == "": row[fname] = None
                if f["t"] == "s" and f.get("enum") and row.get(fname) not in f["enum"] and canon_number(row.get(fname)) in f["enum"]: row[fname] = canon_number(row[fname])   # "0,25" -> the label "0.25"
            if s["key"] == "code_units" and row.get("kind") != "aggregate": row.pop("count", None)
            if s["key"] == "claims" and not row.get("quote"): row.pop("quote", None)   # optional column - a claim without a quote keeps its earlier JSON
            for fname, f in s["fields"].items():   # field `omit_empty: true`: kept only when filled (a column a method added later leaves older rows unchanged)
                if f.get("omit_empty") and row.get(fname) in ("", [], None, False): row.pop(fname, None)
    if kind == "critic":
        ids = [x.get("claim_id") for x in data.get("scores", [])]; dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup: data["_duplicate_claim_ids"] = dup
    if kind == "gate":
        iss = data.pop("_issues", [])
        for d in data.get("deliverables", []):
            d["issues"] = [{kk: vv for kk, vv in i.items() if kk != "deliverable"} for i in iss if i["deliverable"] == d["deliverable"]]
    return data, missing

# ------------------------------------------------------------------ atomic-claim rules (engine_spec.json claim_rules; run.json scoring overrides)
_ID_LIKE = re.compile(r"[A-Za-z_][\w.-]*-\d+[\w.-]*|\S+:\d+(?:-\d+)?\b|\b\d+(?:\.\d+){1,}\b|\b(?:19|20)\d{2}\b|\bv\d+\b")
def count_figures(text):
    """Figures = numbers a critic must reproduce. Ids (FR-012, C-D3-074), file:line locators, dotted versions (2211.17), years and v-tags are not figures."""
    t = _ID_LIKE.sub(" ", text or "")
    return len(re.findall(r"(?<![\w.,])\d+(?:[.,]\d+)?(?:\s?%)?(?![\w])", t))
def claim_rule_warnings(data, proj):
    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(claims, list) or not claims: return
    rules = json.load(open(os.path.join(SPEC_DIR, "engine_spec.json"), encoding="utf-8")).get("claim_rules", {}); sc = proj.get("scoring", {})
    max_chars = int(sc.get("claim_max_statement_chars", rules.get("max_statement_chars", 350))); max_fig = int(sc.get("claim_max_figures", rules.get("max_figures", 2)))
    pat = re.compile(rules.get("target_pattern", r"^(D\d+|[A-Za-z][\w-]*)/[A-Za-z][\w-]*([#:].+)?$")); allowed = None
    try: allowed = (method().get("claims") or {}).get("targets")
    except SystemExit: allowed = None
    n_long = n_fig = n_tgt = 0
    for c in claims:
        cid = c.get("id", "?"); st = c.get("statement") or ""; tg = (c.get("target") or "").strip()
        if c.get("quote") and len(__import__("evidence").qnorm(c["quote"])) < 20: warn(f"claim {cid}: quote has fewer than 20 letters and digits - quote a whole phrase from a cited locator (`dbcx evidence quotes` looks it up word for word)")
        if len(st) > max_chars: n_long += 1; warn(f"claim {cid}: statement has {len(st)} chars (> {max_chars}) - split it into one proposition per claim")
        nf = count_figures(st)
        if nf > max_fig: n_fig += 1; warn(f"claim {cid}: statement carries {nf} figures (> {max_fig}) - one counted figure and its basis per claim; every figure a critic must reproduce is a separate claim")
        parts = [x.strip() for x in re.split(r"\s*;\s*", tg) if x.strip()]
        if len(parts) > 1 and rules.get("single_target", True): n_tgt += 1; warn(f"claim {cid}: {len(parts)} targets ({tg}) - a claim feeds exactly one sheet; the same fact needed on two sheets is two claims or one sheet")
        elif tg and not pat.match(tg): n_tgt += 1; warn(f"claim {cid}: target '{tg}' is not of the form D<n>/<Sheet>[#<row id>[,<row id>]] or <kind>/<section>#<row id>")
        elif allowed and tg and re.match(r"D\d+/", tg) and re.split(r"\s*[#:]", tg)[0] not in allowed: n_tgt += 1; warn(f"claim {cid}: target sheet '{re.split(r'[#:]', tg)[0]}' is not a sheet of this method's deliverables ({', '.join(allowed)}) - a claim that feeds no sheet is dropped or re-homed")
    if n_long or n_fig or n_tgt: warn(f"atomic-claim rules: {n_long} over-long, {n_fig} multi-figure, {n_tgt} target defects of {len(claims)} claims (rules: <= {max_chars} chars, <= {max_fig} figures, one target)")

# ------------------------------------------------------------------ row ids, claimed_by, must-claim cells
def fixed_cap(scope, proj):
    """the earlier fixed claim cap of a scope (upper bound of the derived cap)"""
    from common import WAVES_PATH, load_json, is_consolidated
    sc = proj.get("scoring", {})
    try:
        if is_consolidated(scope): return sc.get("max_claims_consolidated", 120)
    except SystemExit: pass
    light = scope and any(mm.get("light_pass") for w in load_json(WAVES_PATH, {"waves": []}).get("waves", []) for mm in w.get("members", []) if mm.get("name") == scope)
    return sc.get("max_claims_light", 10) if light else sc.get("max_claims", 40)

def row_ids(kind, data, SPEC, proj, scope=None):
    """assign rid + claimed_by and warn about unresolved target refs, uncovered must-claim cells and the derived cap"""
    if not isinstance(data, dict) or "claims" not in data: return None
    import rows
    try: m = method()
    except SystemExit: m = {}
    res = rows.analyse(kind, data, SPEC, m, scope); data["claimed_rows"] = rows.annotate(res)
    for d in res["dups"]: warn(f"row id {d} occurs more than once in its section - the repeats are numbered ~2, ~3; give the rows distinct keys")
    for cid, ref in res["unresolved"][:30]: warn(f"claim {cid}: target row '{ref}' names no row of this analysis - target the row by its rid (the .json shows it) or its exact key value")
    if res["must_cells"] is not None:
        un = res["must_uncovered"]
        if un: warn(f"must-claim cells without a claim: {len(un)} of {len(res['must_cells'])} (" + "; ".join(f"{s}#{r}.{f}" for s, r, f, _ in un[:12]) + (" ..." if len(un) > 12 else "") + ") - a client-visible verdict needs a claim that targets its row")
        bound = fixed_cap(scope, proj); cap = rows.derived_cap(len(res["must_rows"]), bound, proj.get("scoring", {})); n = len(data.get("claims") or [])
        if n > cap: warn(f"{n} claims exceed the derived claim cap of {cap} ({len(res['must_rows'])} must-claim rows + reserve, at most {bound}) - claims go to the verdict rows first")
    return res

# ------------------------------------------------------------------ evidence cells
_LEXICAL = re.compile(r"\.\.\.|\u2026|\(|\)|\bdbcx\s|\bgrep\b|\bwc\b|, ")
def evidence_warnings(data, proj):
    """Dangling evidence surfaces at the analyst's own CHECK - regardless of which brief it read - instead of first in the
    critic's dangling report a round later. Warnings only; the resolver (evidence.py) decides what resolves."""
    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(claims, list) or not claims: return
    try: import evidence
    except Exception: return
    ids = {c.get("id") for c in claims if c.get("id")}; n = 0
    for c in claims:
        for ev in c.get("evidence") or []:
            try: kind, ok, info = evidence.resolve(ev, proj, ids)
            except Exception: continue
            if ok: continue
            n += 1; hint = " - an evidence cell is an ADDRESS a tool resolves: no ellipsis, parenthesis, comma or tool invocation; the explanation belongs in the statement" if _LEXICAL.search(ev or "") else ""
            warn(f"claim {c.get('id', '?')}: evidence `{ev}` does not resolve [{kind}: {info}]{hint}")
    if n: warn(f"dangling evidence: {n} cell(s) do not resolve - a claim whose evidence a critic cannot open scores 4 at best; fix the cells before you report")

# ------------------------------------------------------------------ generation
def field_schema(f):
    t = f["t"]
    if t == "l": return {"type": "array", "items": {"type": "string"}}
    if t == "i": s = {"type": "integer"}
    elif t == "b": s = {"type": "boolean"}
    elif t == "n": s = {"type": ["string", "null"]}
    elif t == "f": s = {"type": ["number", "null"]}
    else: s = {"type": "string"}
    if "enum" in f:
        s = {"enum": f["enum"]} if t != "n" else {"enum": list(f["enum"]) + ([None] if None not in f["enum"] else [])}
    return s

def obj_schema(fields):
    return {"type": "object", "properties": {n: field_schema(f) for n, f in fields.items()}, "required": [n for n, f in fields.items() if f.get("req")]}

def schema(kind, k):
    props = {n: field_schema(f) for n, f in k["head"].items()}; req = [n for n, f in k["head"].items() if f.get("req")]
    for s in k["sections"]:
        key = s["key"]
        if s["type"] == "table": sub = {"type": "array", "items": obj_schema(s["fields"])}
        elif s["type"] == "kv": sub = obj_schema(s["fields"])
        elif s["type"] == "list": sub = {"type": "array", "items": {"type": "string"}}
        else: sub = {"type": "string"}
        if key == "_issues": continue
        if "." in key:
            top, leaf = key.split(".", 1)
            props.setdefault(top, {"type": "object", "properties": {}, "required": []})["properties"][leaf] = sub
            if s.get("req"): props[top]["required"].append(leaf)
        else:
            props[key] = sub
            if s.get("req"): req.append(key)
    if kind == "gate" and any(s["key"] == "_issues" for s in k["sections"]):   # legacy (<= 0.7) per-deliverable gate shape
        iss = [s for s in k["sections"] if s["key"] == "_issues"][0]
        fields = {n: f for n, f in iss["fields"].items() if n != "deliverable"}
        props["deliverables"]["items"]["properties"]["issues"] = {"type": "array", "items": obj_schema(fields)}
        props["deliverables"]["items"]["required"].append("issues")
    return {"$schema": "http://json-schema.org/draft-07/schema#", "title": k["title"], "type": "object", "properties": props, "required": req}

def enum_help(fields, already=""):
    parts = [f"{n} = {' | '.join('(empty)' if e is None else str(e) for e in f['enum'])}" for n, f in fields.items() if f.get("enum") and f["t"] != "i" and not re.search(r"\b" + re.escape(n) + r"\s*[=:]", already)]
    return "; ".join(parts)

def template(kind, k, conventions, lang):
    out = [f"# {k['title']}", ""]
    out += [f"- **{n}:** " for n in k["head"]]
    hh = "; ".join(x for x in [k.get("head_help", ""), enum_help(k["head"], k.get("head_help", ""))] if x)
    if hh: out.append(f"\n<!-- {hh} -->")
    out.append("")
    for s in k["sections"]:
        out.append(f"## {s['heading']}"); out.append("")
        help_ = "; ".join(x for x in [s.get("help", ""), enum_help(s.get("fields") or {}, s.get("help", ""))] if x)
        if help_: out.append(f"<!-- {help_} -->")
        if s["type"] == "table":
            fs = list(s["fields"]); out.append("| " + " | ".join(fs) + " |"); out.append("|" + "---|" * len(fs)); out.append("| " + " | ".join("" for _ in fs) + " |")
        elif s["type"] == "kv": out += [f"- **{n}:** " for n in s["fields"]]
        elif s["type"] == "list": out.append("- ")
        else: out.append("(text)")
        out.append("")
    out.append(f"<!-- Conventions: {conventions}; free text language: {lang}. Check with: dbcx md_to_json {kind} <file.md> -->")
    return "\n".join(out)

def generate():
    proj = project(); SPEC, conventions = spec(proj); lang = proj["languages"]["deliverable"]
    os.makedirs(TPL, exist_ok=True); os.makedirs(SCHEMAS, exist_ok=True)
    for kind, k in SPEC.items():
        open(os.path.join(TPL, k["file"]), "w", encoding="utf-8").write(template(kind, k, conventions, lang))
        json.dump(schema(kind, k), open(os.path.join(SCHEMAS, k["file"].replace(".md", ".schema.json")), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("generated", relp(os.path.join(TPL, k["file"]), ROOT), "+ schema")

def method_check(kind, data, proj):
    """methods/<m>/validate.py `check(kind, data, cfg) -> [error]`, called after the row ids are assigned (rules a schema cannot
    state: vocabulary by option start, sizes, positions, lookup budgets). Absent file = no rules; its errors fail the CHECK like
    schema errors, and a crashing rule is reported as one."""
    d = (proj.get("_method") or {}).get("_dir"); p = os.path.join(d or "", "validate.py")
    if not d or not os.path.exists(p): return []
    import importlib.util
    try:
        sp = importlib.util.spec_from_file_location("dbcx_method_validate", p); mod = importlib.util.module_from_spec(sp); sp.loader.exec_module(mod)
        return [str(e) for e in (mod.check(kind, data, proj) or [])]
    except Exception as ex: return [f"method rule check {relp(p, os.path.dirname(os.path.dirname(d)))} failed: {type(ex).__name__}: {ex}"]

def closed_score_file(json_path):
    """True when round<n>-result.json beside json_path records a checksum for it (the round was aggregated)."""
    m = re.match(r"round(\d+)-(.+)\.json$", os.path.basename(json_path))
    if not m: return False
    res = os.path.join(os.path.dirname(json_path), f"round{m.group(1)}-result.json")
    if not os.path.exists(res) or not os.path.exists(json_path): return False
    try: return m.group(2) in (json.load(open(res, encoding="utf-8")).get("checksums") or {})
    except Exception: return False

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] == "--generate": generate(); return
    kind, path = a[0], a[1]
    proj = project(); SPEC, _ = spec(proj)
    if kind not in SPEC: sys.exit(f"unknown kind {kind}; known: {', '.join(SPEC)}")
    out = a[a.index("--out") + 1] if "--out" in a else os.path.splitext(path)[0] + ".json"
    rel = relp(out, ROOT)
    if kind == "critic" and "--force" not in a and closed_score_file(out):
        print(f"REFUSED {rel}: `dbcx score_aggregate` already ran on this round and recorded this file's checksum (round<n>-result.json). Re-converting would drop the carried entries and break the build guard. If the critic really changed its Markdown: re-run `dbcx score_aggregate <scope> <round>` for this and every later round after converting with --force."); sys.exit(1)
    data, missing = convert(kind, open(path, encoding="utf-8").read(), SPEC)
    dup = data.pop("_duplicate_claim_ids", None)
    try: scope = scope_of_path(relp(os.path.abspath(path), ROOT))
    except SystemExit: scope = None
    claim_rule_warnings(data, proj); row_ids(kind, data, SPEC, proj, scope); evidence_warnings(data, proj)
    mc = method_check(kind, data, proj)   # a rule's "WARNING ..." entry is printed, not refused
    errs = validate.check_data(schema(kind, SPEC[kind]), data) + [e for e in mc if not e.startswith("WARNING ")]
    for w_ in (e for e in mc if e.startswith("WARNING ")): warn(w_[len("WARNING "):])
    if dup: errs.append("duplicate claim_id rows in Scores: " + ", ".join(dup) + " (one row per claim; replace, do not append)")
    if errs:
        print(f"INVALID {rel} (nothing written)"); [print("   ", e) for e in errs[:60]]
        for w in WARNINGS: print("WARNING", w)
        if missing: print("WARNING missing sections:", ", ".join(missing))
        sys.exit(1)
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if missing: print("WARNING missing sections:", ", ".join(missing))
    for w in WARNINGS: print("WARNING", w)
    print(f"OK {rel}" + (f" ({len(WARNINGS)} warning(s) - read them, they mean content was folded, kept or ignored)" if WARNINGS else ""))

if __name__ == "__main__":
    main()
