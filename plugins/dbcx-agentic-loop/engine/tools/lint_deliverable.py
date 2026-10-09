#!/usr/bin/env python3
"""Client-facing wording guard: no process or versioning language in the workbooks - a client sees one version-free deliverable.

Usage: dbcx lint_deliverable [D0 D1 D2 D3 D4 | <file.xlsx> ...] [--json] [--fix-list]
       dbcx lint_deliverable --standalone [--all | D1 ... | <file.xlsx> ...] [--edition customer|full|both] [--round <n>] [--json] [--fix-list]
Scans every cell of the given workbooks (default: every built deliverable) for the terms in run.json -> lint.forbidden_terms (engine defaults + method lint)
(regex, case-insensitive), skipping matches covered by lint.allow_terms. Prints Sheet!Cell + the offending text; exit 1 on hits.
The same check runs inside `dbcx build_excel` (refuse without --allow-process-language) and can be run on the analysis Markdown
with --md <file.md> to catch the wording before it is built. The client does not care how we worked: a statement is an absolute,
present-tense fact; the history belongs in the claim's `history` column (never exported) and in analysis/gauntlet/.

--standalone is the final gate's hygiene layer on the recalculated customer edition (default --all customer
workbooks): process vocabulary DE + EN, internal locators, dangling C-/Q-/PS-7- ids, references to sheets not in the workbook, raw keys,
bound columns >= 95 % empty, typed numbers or a placeholder in the summary, literal aggregates, formula errors and reconciliation (cached values only -
a WARNING without them), Grundlage proofs ([Qn] -> Quellen with a title in the deliverable language, A-nn -> Annahmen without the default
wording and with reason and consequence filled, Code -> repository locator; "Angabe <client>" needs no proof row), emphasis budget, header tiers, freeze, filter, print setup, tab colours. --round <n> writes
analysis/gate/round<n>-hygiene.json + .md (the gate briefs refuse while it fails). Exit 1 on any error.
"""
import os, re, sys, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, project, relp

def rules(p):
    L = p.get("lint", {}); forb = [re.compile(x, re.I) for x in L.get("forbidden_terms", [])]; allow = [re.compile(re.escape(x), re.I) for x in L.get("allow_terms", [])]
    return forb, allow

def hits_in(text, forb, allow):
    out = []
    for rx in forb:
        for m in rx.finditer(text):
            ctx = text[max(0, m.start() - 25): m.end() + 25]
            if any(a.search(ctx) for a in allow): continue
            out.append((m.group(0), text[max(0, m.start() - 60): m.end() + 60].replace("\n", " ")))
    return out

def lint_xlsx(path, forb, allow):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True); out = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and not c.value.startswith("="):
                    for term, ctx in hits_in(c.value, forb, allow): out.append({"file": os.path.basename(path), "where": f"{ws.title}!{c.coordinate}", "term": term, "context": ctx})
    return out

def lint_md(path, forb, allow):
    out = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if line.startswith("<!--") or not line.strip(): continue
        for term, ctx in hits_in(line, forb, allow): out.append({"file": relp(path, ROOT), "where": f"line {n}", "term": term, "context": ctx})
    return out

# ------------------------------------------------------------------ hygiene layer (G2, DESIGN §9 layer 1): --standalone
# The customer edition must stand on its own: no process vocabulary (DE + EN), no internal locators or dangling ids, every
# aggregate a formula that reconciles, every basis label backed by its proof, format rules kept. Binary: any error fails.
HYGIENE_TERMS = [   # whole words with their inflections only: a compound ("Prüfergebnis", "Korrekturvorschlag", "Gesprächsrunde") is subject matter
    r"\bRunden?\b", r"\bkorrigiert(e|en|er|es)?\b", r"\bKorrektur(en)?\b", r"\bPrüfer(in|innen|n|s)?\b", r"\bPrüfer-Scores?\b", r"\bKritiker(in|innen|n|s)?\b",
    r"\bGutachter(in|innen|n|s)?\b", r"\bSA[ -](Kunde|Plattform)\b", r"\bBewertungen-?urteil(e|en|s)?\b", r"\b(durch den|vom|dem) Bewertungen\b", r"\bOrchestrators?\b",
    r"\bAnalyst(en|in|innen)?\b", r"\bPost-?Pass\b", r"\bGauntlet\b", r"\b(Prüfer|Kritiker|Gutachter|Reviewer|Critic|Ø)[- ]Scores?\b", r"\bScores?[ -](SA|Kunde|Plattform|Kritiker|Prüfer|client|standard|critic|reviewer)\b", r"\bKonfidenz(en)?\b", r"\bconfidence\b", r"\breviewers?\b", r"\bclaim[ -]?ids?\b"]
HEADER_TERMS = [r"\((Formel|formula)\)", r"^Abgleich$", r"^Reconciliation$"]
INTERNAL_LOC = re.compile(r"(?<![\w./-])(?:state|work|analysis|tools|docs|templates|schemas|overrides)/[\w./-]+|(?<![\w/.-])[A-Za-z_][\w-]*\.py\b|\bdbcx\b|\b(?:STATUS|QUESTIONS|WAVES)\.json\b")
REPO_LOC = re.compile(r"(?<![\w@-])[\w.@~-]+(?:/[\w.@~-]+)+\.[A-Za-z][A-Za-z0-9]{0,7}(?::\d+(?:-\d+)?)?")
try: from xl_transform import is_repo_locator   # the build's own rule (a path with '/' - directories included - or a file name): one rule for both
except Exception: is_repo_locator = lambda e: bool(REPO_LOC.search(e))
RUN_SHORTHAND = re.compile(r"\bAS-\d|\bKB-\d|HO-[\w-]+#|\bcode-analysis:")   # scope-local assumption ids, knowledge-base ids, handover locators: the customer edition resolves or drops them
ID_TOKENS = re.compile(r"\bC-[\w.-]+?-\d{2,}\b|\bQ-[A-Za-z0-9][\w-]*\b|\bPS-7-\d+\b")
SOURCE_REF = re.compile(r"\[Q(\d+)\]"); ASSUMPTION_REF = re.compile(r"\bA-(\d{2,})\b")
SNAKE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
SHEET_MENTION = re.compile(r"\b(?:Blatt|Blättern|Tabellenblatt|Reiter|[Ss]heet)\s+[„\"'»]?([A-ZÄÖÜ][\w-]*)")
FORMULA_SHEET = re.compile(r"(?:'([^']+)'|([A-Za-zÄÖÜäöü_][\w.]*))!\$?[A-Z]{1,3}\$?\d")
NUMBER = re.compile(r"(?<![\w.,/:#-])(\d{1,3}(?:[. ]\d{3})+|\d+)(?:,\d+)?\s?(%|Prozent|percent)?(?![\w.,:/-]*\d)(?![\w-])")
ERRORS = ("#REF!", "#DIV/0!", "#NAME?", "#VALUE!", "#N/A", "#NUM!", "#NULL!")
SKIP_SHEETS = re.compile(r"^(README|Management|Uebersicht|Übersicht|Overview|Quellen|Sources|Parameter|INTERIM)", re.I)
LOCATOR_HEADERS = re.compile(r"Evidenz|Evidence|Datei|File|Pfad|Path|Fundstelle|Location|Adresse|Address|URL|Quelle|Source|Nachweis", re.I)
INPUT_HEADERS = re.compile(r"Zutreffend|Anmerkung|Kundenentscheidung|Entscheidung des Kunden|client decision|Applies\?|Comment|Kommentar")
STOP = {"de": {"der", "die", "das", "und", "ist", "nicht", "mit", "für", "den", "dem", "des", "ein", "eine", "wird", "werden", "auf", "im", "zu", "von", "sind", "oder", "auch", "als", "bei"},
        "en": {"the", "and", "is", "not", "with", "for", "of", "to", "in", "are", "or", "be", "this", "that", "which", "from", "by", "on", "an", "as", "it", "its", "has", "have"}}
# code vocabulary (method lint `code_vocabulary: true`, e.g. an estimate for product owners): texts say WHAT is used or built, never HOW in
# code - the same patterns the method's CHECK applies to the analysis fields (methods/<m>/validate.py imports code_terms)
CODE_EXT = r"(?:java|ts|js|xml|jsp|impex|properties|groovy|html|scss)"
PRODUCT_JS = r"(?:Node|Vue|Next|Nuxt|Express|Angular|React|Chart|Three|Ember|Backbone)\.js\b"   # product names, not files
CODE_PATTERNS = (
    ("file", re.compile(rf"(?<![\w@./-])(?!{PRODUCT_JS})[\w@.-]*[A-Za-z0-9_]\.{CODE_EXT}\b(?::\d+(?:-\d+)?)?")),
    ("path:line", re.compile(r"(?:[\w@.-]+/)+[\w@.-]+:\d+(?:-\d+)?|(?<![\w.])[\w-]+\.[A-Za-z]{1,8}:\d+(?:-\d+)?\b")),
    ("path", re.compile(r"(?<![\w/])(?:[a-z0-9_.@-]+/){2,}[a-z0-9_.@-]+")),
    ("line number", re.compile(r"\b(?:line|lines|Zeile|Zeilen)\s+\d+", re.I)),
    ("package", re.compile(r"\b(?:com|de|org)\.[a-z]\w*(?:\.[a-z]\w*)+\b")),
    ("class name", re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)*(?:Service|Facade|Controller|Populator|Converter|Strategy|Dao|Interceptor|Handler|Component|Module|Resolver|Listener|Job|Action|Filter|Adapter)s?\b")),
)

def code_terms(text, units=()):
    """[(kind, match)] of code vocabulary in a text: file names / extensions, path:line, repository paths, 'line NN', package names,
    class-like identifiers (CamelCase ending in Service, Facade, Controller, ...), and the run's custom unit names (`units`)"""
    t = str(text or ""); out = [(k, m.group(0)) for k, rx in CODE_PATTERNS for m in rx.finditer(t)]
    out += [("unit name", u) for u in units if u and len(u) >= 4 and re.search(r"(?<![\w-])" + re.escape(u) + r"(?![\w-])", t)]
    return out

def unit_names(root=None):
    """custom unit names of the code-inventory handover (input/handover/code-inventory.json) - code vocabulary in client text"""
    fp = os.path.join(root or ROOT, "input", "handover", "code-inventory.json")
    try: env = json.load(open(fp, encoding="utf-8"))
    except Exception: return []
    inv = (env.get("data", env) if isinstance(env, dict) else {}).get("units") or []
    return [r.get("name") for r in (inv.values() if isinstance(inv, dict) else inv) if isinstance(r, dict) and r.get("name")]

CHECKS = {  # check id -> severity; warnings never fail the layer
    "process_language": "error", "code_vocabulary": "error", "internal_locator": "error", "run_shorthand": "error", "dangling_id": "error", "missing_sheet_ref": "error", "raw_key": "error", "empty_column": "error",
    "summary_number": "error", "summary_missing": "error", "literal_aggregate": "error", "formula_error": "error", "reconciliation": "error", "basis_empty": "error", "basis_code": "error",
    "basis_source": "error", "basis_assumption": "error", "basis_assumption_reason": "error", "basis_assumption_if_not": "error", "emphasis_budget": "error", "header_tier": "error", "duplicate_header": "error", "freeze": "error",
    "filter": "error", "print_setup": "error", "tab_colour": "error", "language": "error", "zero_match": "warning", "no_cached_values": "warning"}
CHECK_DOC = {  # check id -> (label, what it checks): the dashboard's hygiene table
    "process_language": ("Process language", "No cell speaks about how the study was made (reviewers, rounds, corrections, scores) or shows an internal column."),
    "code_vocabulary": ("Code vocabulary", "Texts say what is used or built, never how in code (class, method or file names)."),
    "internal_locator": ("Internal paths", "No cell shows a run-internal path, tool name or state file."),
    "run_shorthand": ("Run-internal ids", "No customer cell shows a scope-local assumption id, a knowledge-base id, a handover locator or a code-analysis source key."),
    "dangling_id": ("Unresolved ids", "Every claim, question or reference id a cell names exists in the workbook."),
    "missing_sheet_ref": ("Missing sheet", "Every sheet a formula refers to or a text mentions is in the workbook."),
    "raw_key": ("Raw keys", "No result cell shows a field name or snake_case key instead of a readable label."),
    "empty_column": ("Empty column", "No table column is empty in 95 % or more of its rows."),
    "summary_number": ("Typed number in summary", "Figures in management summary prose come from {kpi:id} placeholders, never typed by hand."),
    "summary_missing": ("Summary missing", "The management summary is written, not the placeholder text."),
    "literal_aggregate": ("Typed aggregate", "Summary and overview sheets compute their figures with formulas over the detail sheets instead of typed numbers."),
    "formula_error": ("Formula error", "No recalculated cell shows an Excel error (#REF!, #DIV/0!, #NAME? ...)."),
    "reconciliation": ("Reconciliation", "Every summary figure equals what its detail sheet gives."),
    "basis_empty": ("Empty basis", "Every result row names its basis."),
    "basis_code": ("Code basis without locator", "A row based on code carries a repository locator."),
    "basis_source": ("Source reference", "A vendor basis carries a [Qn] source, and every [Qn] has a titled row on the sources sheet in the deliverable language."),
    "basis_assumption": ("Assumption reference", "An assumption basis names its A-nn, and every A-nn has a row on the assumptions sheet in its own words."),
    "basis_assumption_reason": ("Assumption without reason", "Every assumption says why the study assumes it."),
    "basis_assumption_if_not": ("Assumption without consequence", "Every assumption says what changes if it does not hold."),
    "emphasis_budget": ("Decision columns", "A table highlights no more decision columns than the style allows."),
    "header_tier": ("Header colours", "Every header cell carries one of the header tier fills."),
    "duplicate_header": ("Duplicate header", "No header appears twice in a table (Excel repairs the table on open)."),
    "freeze": ("Frozen header", "The header row of every table is frozen."),
    "filter": ("Filter", "Every table has a filter."),
    "print_setup": ("Print setup", "The header row repeats on printed pages, the sheet fits the page width it needs, wide sheets print landscape."),
    "tab_colour": ("Tab colour", "Every sheet tab carries a role colour."),
    "language": ("Language", "Every sentence is in the deliverable language."),
    "zero_match": ("Count never matches", "A counting formula's criterion occurs in its range (otherwise a label drifted)."),
    "no_cached_values": ("Not recalculated", "The workbook was recalculated, so formula errors and reconciliation could be checked."),
}

def _rgb(color):
    v = getattr(color, "rgb", None) if color is not None else None
    return v[-6:].upper() if isinstance(v, str) and len(v) >= 6 else None

def _lang_of(text):
    words = re.findall(r"[a-zäöüß]+", text.lower()); de = sum(w in STOP["de"] for w in words); en = sum(w in STOP["en"] for w in words)
    return "en" if en >= 3 and en > 2 * de else ("de" if de >= 3 and de > 2 * en else None)

class Book:
    """One workbook opened twice: formulas (wb) and Excel's cached values (vb; None where never calculated)."""
    def __init__(self, path, cfg):
        import openpyxl
        self.path = path; self.name = os.path.basename(path)
        self.wb = openpyxl.load_workbook(path); self.vb = openpyxl.load_workbook(path, data_only=True); self.names = self.wb.sheetnames
        formulas = [(ws.title, c.coordinate) for ws in self.wb for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
        self.has_formulas = bool(formulas); self.cached = any(self.vb[s][coord].value is not None for s, coord in formulas[:400])
    def value(self, sheet, coord):
        v = self.wb[sheet][coord].value
        return self.vb[sheet][coord].value if isinstance(v, str) and v.startswith("=") else v
    def is_table(self, ws):
        if SKIP_SHEETS.match(ws.title) or ws.max_row < 1: return False
        hdr = [c.value for c in ws[header_row(ws)]]
        return bool(ws.tables) or (sum(isinstance(h, str) and bool(h.strip()) for h in hdr) >= 2 and ws.freeze_panes is not None)
    def headers(self, ws): return qualified(ws, header_row(ws))
    def rows(self, ws):
        """data rows of a table sheet: (row number, cells) with a non-empty first cell"""
        for r in ws.iter_rows(min_row=header_row(ws) + 1):
            if r and r[0].value not in (None, ""): yield r[0].row, r

def header_row(ws):
    """the table header row: the top row of the sheet's first Excel table, else of its autofilter (a sheet with option band
    headers has no table object: 2), else 1"""
    t = next(iter(ws.tables.values()), None) if ws.tables else None
    m = re.match(r"[A-Z]+(\d+)", t.ref if t is not None else str(ws.auto_filter.ref or ""))
    return int(m.group(1)) if m else 1

def bands(ws, hr):
    """[(first col, last col)] (0-based) of the option band cells above the header row"""
    if hr < 2: return []
    merged = {m.min_col: m.max_col for m in ws.merged_cells.ranges if m.min_row == m.max_row == hr - 1}
    return [(c.column - 1, merged.get(c.column, c.column) - 1) for c in ws[hr - 1] if c.value not in (None, "")]

def qualified(ws, hr, hdr=None):
    """the header texts of row hr (or the caller's list `hdr` of them); below option bands (autofilter, no table object) each
    block's headers read with the band's option label - "Migration: Vorgehen" - unless they carry it already, so they are unique"""
    hdr = list(hdr) if hdr is not None else [str(c.value).strip() if c.value is not None else "" for c in ws[hr]]
    if ws.tables or not ws.auto_filter.ref: return hdr
    for a, z in bands(ws, hr):
        lab = str(ws.cell(hr - 1, a + 1).value).strip()
        for i in range(a, min(z, len(hdr) - 1) + 1):
            if isinstance(hdr[i], str) and hdr[i] and not hdr[i].startswith(lab + ": "): hdr[i] = f"{lab}: {hdr[i]}"
    return hdr

def sheet_spec(sp, cfg, book, title):
    """the spec of sheet `title` in the deliverable whose file is `book` (any deliverable's sheet of that name as a fallback)"""
    ds = sp.get("deliverables") or {}; key = next((k for k, v in (cfg.get("deliverables") or {}).items() if isinstance(v, dict) and os.path.basename(str(v.get("file", ""))) == book), None)
    for d in ([ds[key]] if key in ds else []) + list(ds.values()):
        s = next((x for x in (d.get("sheets", []) if isinstance(d, dict) else []) if x.get("name") == title), None)
        if s: return s
    return None

def spec_columns(s, hdr, edition="customer"):
    """the visible spec columns of a table sheet aligned with its header cells, or None when they do not line up (a column with
    `edition: full` is not in the customer edition)"""
    try: from xl_spec import is_internal
    except Exception: return None
    cols = [c for c in (s or {}).get("columns", []) if not is_internal(c) and (edition != "customer" or c.get("edition") != "full")] if (s or {}).get("type") == "table" else None
    return cols if cols is not None and len(cols) == len(hdr) else None

def _spec():
    try:
        from common import deliverables_spec
        return deliverables_spec()
    except Exception: return {}

try: from xl_style import BANDS as _BANDS
except Exception: _BANDS = []

def _style(sp):
    st = sp.get("style") or {}; hd = st.get("header") or {}
    return {"tiers": {k: (hd.get(k) or {}).get("fill", d).upper() for k, d in (("normal", "3C4BC8"), ("decision", "100C2A"), ("support", "CDCDCD"))},
            "tabs": {v.upper() for v in (st.get("tabs") or {"result": "3C4BC8", "assumptions": "A78DB6", "reference": "CDCDCD", "internal": "100C2A"}).values()},
            "max_decision": st.get("max_decision_columns", 2), "option_headers": {str(x.get("header", "")).upper() for x in (st.get("option_bands") or _BANDS)}}

def _names(sp):
    """sheet names the build can produce (all deliverables + engine sheets), the basis header and the default assumption wording"""
    com = sp.get("common") or {}; names = {"Aussagen", "Claims", "Offene_Fragen", "Open_Questions"}
    for d in (sp.get("deliverables") or {}).values():
        names |= {s["name"] for s in (d.get("sheets", []) if isinstance(d, dict) else []) if s.get("name")}
    eng = {k: (com.get(k) or {}).get("name") for k in ("open_questions", "assumptions", "sources")}; names |= {v for v in eng.values() if v}
    dw = (com.get("assumptions") or {}).get("default_wording", "Die Analyse geht davon aus: {text}.")
    try:
        from common import labels, fmt
        ho = fmt(labels().get("basis_handover", "")); cl = fmt(labels().get("basis_client", ""))
    except Exception: ho = cl = ""
    return {"all": names, "assumptions": eng["assumptions"] or "Annahmen", "sources": eng["sources"] or "Quellen", "basis": (com.get("basis") or {}).get("header", "Grundlage"), "basis_handover": ho, "basis_client": cl,
            "assumption_headers": ((com.get("assumptions") or {}).get("headers") or ["Nr.", "Annahme", "Warum wir davon ausgehen", "Falls nicht zutreffend"])[2:4],
            "default_prefix": dw.split("{text}")[0].strip(), "sources_missing": (com.get("sources") or {}).get("missing", ""), "summary_missing": (com.get("mgmt") or {}).get("missing", "")}

def _label_keys():
    try:
        from common import labels
        return {k for k, v in labels().items() if isinstance(v, str) and v != k and not k.startswith("_")}
    except Exception: return set()

def standalone(files, cfg=None):
    """Hygiene report over the given workbooks: {passed, errors, warnings, counts, findings, cached_values, files}."""
    cfg = cfg or project(); lang = cfg["languages"]["deliverable"]; sp = _spec(); style = _style(sp); names = _names(sp); lkeys = _label_keys()
    try: from xl_spec import confidence_defaults; confidence_defaults(sp)   # the build's column visibility, so spec columns line up with the headers
    except Exception: pass
    L = cfg.get("lint", {}); ml = cfg["_method"].get("lint", {})
    forb = [re.compile(x, re.I) for x in L.get("forbidden_terms", []) + ml.get("forbidden_terms", []) + HYGIENE_TERMS + L.get("hygiene_terms", [])]
    allow = [re.compile(re.escape(x), re.I) for x in L.get("allow_terms", []) + ml.get("allow_terms", []) + L.get("hygiene_allow", [])]
    hforb = [re.compile(x, re.I) for x in HEADER_TERMS]; findings = []; cached = {}
    versions = {t for k in ("source", "target") for t in re.findall(r"\d+", str((cfg.get(k) or {}).get("version", "")))}   # '2211' names a release, not a figure
    def add(check, b, where, text): findings.append({"check": check, "severity": CHECKS[check], "file": b.name, "where": where, "text": str(text)[:240]})
    cv = bool(ml.get("code_vocabulary")); units = unit_names() if cv else []
    for f in files:
        b = Book(f, cfg); cached[b.name] = b.cached; b.edition = "full" if os.path.basename(os.path.dirname(os.path.abspath(f))) == "intern" else "customer"
        if b.has_formulas and not b.cached: add("no_cached_values", b, "-", "no cached values (never recalculated): formula errors and reconciliation are unchecked - run `dbcx render_workbook`")
        known = set()   # a full edition resolves ids against its own claims / questions sheets
        for ws in b.wb:
            col = 1 if ws.title in ("Aussagen", "Claims") else (0 if ws.title in ("Offene_Fragen", "Open_Questions") else None)
            if col is not None: known |= {str(r[col].value) for _, r in b.rows(ws) if len(r) > col and r[col].value}
        segments = set()   # names that occur inside paths (unit and file names) are not raw keys
        for ws in b.wb:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and "/" in c.value: segments |= set(re.split(r"[/\s.:;,()]+", c.value))
        sources, assumptions = {}, {}
        if names["sources"] in b.names:
            for _, r in b.rows(b.wb[names["sources"]]):
                m = re.search(r"\d+", str(r[0].value))
                if m: sources[int(m.group(0))] = str((r[1].value if len(r) > 1 else "") or "")
        if names["assumptions"] in b.names:
            aw = b.wb[names["assumptions"]]; hdr = b.headers(aw)
            cols = [(hdr.index(h) if h in hdr else i, check) for h, i, check in zip(names["assumption_headers"], (2, 3), ("basis_assumption_reason", "basis_assumption_if_not"))]
            for rn, r in b.rows(aw):
                m = ASSUMPTION_REF.search(str(r[0].value))
                if m: assumptions[int(m.group(1))] = str((r[1].value if len(r) > 1 else "") or "")
                for i, check in cols:   # an assumption the client cannot weigh: no reason, or no consequence if it is wrong
                    if len(r) <= i or not str(r[i].value or "").strip(): add(check, b, f"{aw.title}!{r[i].coordinate if len(r) > i else rn}", f"{r[0].value}: '{hdr[i] if i < len(hdr) else i}' is empty")
        ss = {ws.title: sheet_spec(sp, cfg, b.name, ws.title) for ws in b.wb}; cls = {t: (x or {}).get("class") for t, x in ss.items()}   # spec `class: mgmt|overview`
        mgmt = [ws for ws in b.wb if re.match(r"Management|Summary", ws.title, re.I) or cls[ws.title] == "mgmt"]
        overview = [ws for ws in b.wb if (re.match(r"Uebersicht|Übersicht|Overview", ws.title, re.I) or cls[ws.title] == "overview") and ws not in mgmt]
        for ws in b.wb:
            table = b.is_table(ws); hdr = b.headers(ws) if table else []; hr = header_row(ws)
            loc_cols = {i for i, h in enumerate(hdr) if LOCATOR_HEADERS.search(h)}
            for row in ws.iter_rows():
                for c in row:
                    v = c.value
                    if not isinstance(v, str) or not v.strip(): continue
                    where = f"{ws.title}!{c.coordinate}"
                    if v.startswith("="):
                        for q1, q2 in FORMULA_SHEET.findall(v):
                            if (q1 or q2) not in b.names: add("missing_sheet_ref", b, where, f"formula refers to sheet '{q1 or q2}', which is not in the workbook")
                        continue
                    for term, ctx in hits_in(v, forb, allow): add("process_language", b, where, f"[{term}] ...{ctx}...")
                    if table and c.row == hr and any(rx.search(v) for rx in hforb): add("process_language", b, where, f"internal column in a customer sheet: '{v}'")
                    for m in INTERNAL_LOC.finditer(v): add("internal_locator", b, where, m.group(0))
                    if b.edition == "customer":
                        for m in RUN_SHORTHAND.finditer(v): add("run_shorthand", b, where, f"{m.group(0)}: run-internal id in a customer cell ...{v[max(0, m.start() - 30): m.end() + 30]}...")
                    for m in ID_TOKENS.finditer(v):
                        if m.group(0) not in known: add("dangling_id", b, where, m.group(0))
                    mentioned = {m.group(1) for m in SHEET_MENTION.finditer(v) if m.group(1) in names["all"] or "_" in m.group(1)}
                    mentioned |= {n for n in names["all"] if "_" in n and re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", v)}
                    for n in sorted(mentioned - set(b.names)): add("missing_sheet_ref", b, where, f"mentions sheet '{n}', which is not in the workbook")
                    if c.row > hr and c.column - 1 not in loc_cols and (v in lkeys or (SNAKE.match(v) and v not in segments)): add("raw_key", b, where, v)
                    for n in SOURCE_REF.findall(v):
                        t = sources.get(int(n))
                        if t is None: add("basis_source", b, where, f"[Q{n}] has no row on sheet {names['sources']}")
                        elif ws.title == names["sources"] and (not t.strip() or (names["sources_missing"] and names["sources_missing"] in t) or _lang_of(t) not in (None, lang)): add("basis_source", b, where, f"[Q{n}]: title missing or not in the deliverable language: '{t[:80]}'")
                    if ws.title != names["assumptions"]:
                        cited = {n for m in (re.finditer(rf"{re.escape(names['basis_client'])} ?\(?((?:A-\d{{2,}}(?:, ?)?)+)", v) if names["basis_client"] else []) for n in ASSUMPTION_REF.findall(m.group(1))}   # "Angabe <client> (A-nn)": client-answered, no row by design
                        for n in ASSUMPTION_REF.findall(v):
                            t = assumptions.get(int(n))
                            if t is None and n not in cited: add("basis_assumption", b, where, f"A-{n} has no row on sheet {names['assumptions']}")
                    elif c.column == 2 and names["default_prefix"] and v.startswith(names["default_prefix"]): add("basis_assumption", b, where, f"default assumption wording: '{v[:80]}'")
                    if len(v.split()) >= 6 and c.column - 1 not in loc_cols and _lang_of(v) not in (None, lang): add("language", b, where, v[:100])
            if ws in mgmt or ws in overview:
                for row in ws.iter_rows():
                    for c in row:
                        if isinstance(c.value, (int, float)) and not isinstance(c.value, bool): add("literal_aggregate", b, f"{ws.title}!{c.coordinate}", f"typed number {c.value} where a formula over the detail sheets belongs")
            if ws in mgmt:
                for row in ws.iter_rows():
                    for c in row:
                        if not isinstance(c.value, str): continue
                        if names["summary_missing"] and names["summary_missing"] in c.value: add("summary_missing", b, f"{ws.title}!{c.coordinate}", f"placeholder instead of the management summary: '{names['summary_missing']}'")
                        for t in (re.findall(r'"([^"]*)"', c.value) if c.value.startswith("=") else [c.value]):
                            if len(t.split()) < 8: continue
                            for m in NUMBER.finditer(t):
                                if re.fullmatch(r"(19|20)\d\d", m.group(1)) or m.group(1) in versions or (m.group(1) in ("0", "1") and not m.group(2)): continue
                                add("summary_number", b, f"{ws.title}!{c.coordinate}", f"typed number '{m.group(0).strip()}' in summary prose (use a {{kpi:id}} placeholder): ...{t[max(0, m.start() - 40): m.end() + 30]}...")
            if table: _table_checks(b, ws, hdr, style, names, add, ss.get(ws.title))
            if table and cv: _code_checks(b, ws, hdr, units, add, ss.get(ws.title))
            _format_checks(ws, style, add, b, ss.get(ws.title))
        if b.cached: _value_checks(b, mgmt + overview, add)
    errors = sum(1 for x in findings if x["severity"] == "error"); warnings = len(findings) - errors
    return {"passed": not errors and bool(files), "errors": errors, "warnings": warnings, "counts": {k: sum(1 for x in findings if x["check"] == k) for k in CHECKS if k != "code_vocabulary" or cv},
            "findings": findings, "cached_values": cached, "files": [relp(f, ROOT) for f in files]}

def _code_checks(b, ws, hdr, units, add, ss=None):
    """code vocabulary in the text cells of a table sheet: locator columns and columns the spec marks `verbatim` (the client's own
    wording, e.g. the requirement list) are left out"""
    cols = spec_columns(ss, hdr, getattr(b, "edition", "customer"))
    skip = {i for i, h in enumerate(hdr) if LOCATOR_HEADERS.search(h)} | {i for i, c in enumerate(cols or []) if c.get("verbatim")}
    for _, r in b.rows(ws):
        for i, c in enumerate(r):
            if i in skip or not isinstance(c.value, str) or c.value.startswith("="): continue
            for kind, term in code_terms(c.value, units)[:1]: add("code_vocabulary", b, f"{ws.title}!{c.coordinate}", f"{kind} '{term}' - the text says WHAT is used or built, never HOW in code: ...{c.value[:120]}")

def _table_checks(b, ws, hdr, style, names, add, ss=None):
    from openpyxl.utils import get_column_letter
    rows = list(b.rows(ws)); n = len(rows); seen = {}; hr = header_row(ws); segs = bands(ws, hr); cols = spec_columns(ss, hdr, getattr(b, "edition", "customer"))
    seg_of = lambda i: next((k for k, (a, z) in enumerate(segs) if a <= i <= z), None)   # option block of a column (None = common)
    for i, h in enumerate(hdr):
        if h: seen.setdefault(h, []).append(i)
    for h, idx in seen.items():
        if len(idx) > 1: add("duplicate_header", b, f"{ws.title}!{hr}", f"header '{h}' appears {len(idx)} times (Excel repairs the table on open)")
    validated = {m.group(1) for dv in ws.data_validations.dataValidation for rng in str(dv.sqref).split() for m in [re.match(r"([A-Z]+)", rng)] if m}
    for i, h in enumerate(hdr):
        if not h or n == 0 or INPUT_HEADERS.search(h) or get_column_letter(i + 1) in validated or (cols and cols[i].get("sparse")): continue
        empty = sum(1 for _, r in rows if len(r) <= i or r[i].value in (None, "", "-"))
        if empty / n >= 0.95: add("empty_column", b, f"{ws.title}!{get_column_letter(i + 1)}{hr}", f"column '{h}' is empty in {empty} of {n} rows")
    basis_re = re.compile(rf"(?:^|[\s:·–—-]){re.escape(names['basis'])}$")   # "Grundlage", "Migration: Grundlage"
    loc = {i for i, h in enumerate(hdr) if LOCATOR_HEADERS.search(h)}
    for bi in (i for i, h in enumerate(hdr) if basis_re.search(h)):
        own = seg_of(bi); scope = (lambda i: True) if own is None else (lambda i: seg_of(i) in (None, own))   # an option's basis: proof in its own block or a common column
        for rn, r in rows:
            v = str(r[bi].value or "").strip() if len(r) > bi else ""
            text = " ".join(str(c.value) for i, c in enumerate(r) if isinstance(c.value, str) and scope(i)); where = f"{ws.title}!{get_column_letter(bi + 1)}{rn}"
            locs = [str(c.value) for i, c in enumerate(r) if i in loc and isinstance(c.value, str) and scope(i)] or [text]
            if not v: add("basis_empty", b, where, "empty basis on a result row"); continue
            if "Code" in (v.replace(names["basis_handover"], "") if names.get("basis_handover") else v) and not any(is_repo_locator(e.strip()) for x in locs for e in re.split(r"[;\n]", x) if e.strip()): add("basis_code", b, where, "basis 'Code' without a repository locator in the row")
            if re.search(r"Hersteller|Vendor", v) and not SOURCE_REF.search(text): add("basis_source", b, where, "vendor basis without a [Qn] source in the row")
            if re.search(r"Annahme|Assumption", v) and not ASSUMPTION_REF.search(v): add("basis_assumption", b, where, f"assumption basis without its A-nn: '{v}'")
    fills = [(_rgb(c.fill.fgColor) if c.fill is not None and c.fill.fill_type else None) for c in ws[hr]]; tiers = style["tiers"]
    decision = [hdr[i] for i, f in enumerate(fills) if i < len(hdr) and hdr[i] and f == tiers["decision"]]
    from xl_spec import decision_budget, budget_errors
    if ss and decision_budget(ss) is not None:   # per option block: blocks from the spec columns, else from the band cells
        blk = [(cols[i].get("_option") if cols else seg_of(i), hdr[i]) for i, f in enumerate(fills) if i < len(hdr) and hdr[i] and f == tiers["decision"]]
        for e in budget_errors(ss, [(None if o is None else str(o), h) for o, h in blk], style["max_decision"]): add("emphasis_budget", b, f"{ws.title}!{hr}", e)
    elif len(decision) > style["max_decision"]: add("emphasis_budget", b, f"{ws.title}!{hr}", f"{len(decision)} decision columns (max {style['max_decision']}): {', '.join(decision)}")
    ok = set(tiers.values()) | (style.get("option_headers", set()) if segs else set())   # option-block headers carry their band's tint
    off = [hdr[i] for i, f in enumerate(fills) if i < len(hdr) and hdr[i] and f not in ok]
    if off: add("header_tier", b, f"{ws.title}!{hr}", f"{len(off)} header cell(s) without a tier fill ({', '.join(f'{k} {v}' for k, v in tiers.items())}): {', '.join(off[:6])}")
    if not re.match(rf"[A-Z]+{hr + 1}$", str(ws.freeze_panes or "")): add("freeze", b, f"{ws.title}!{hr}", f"header row not frozen (freeze panes {ws.freeze_panes})")
    if not ws.tables and not ws.auto_filter.ref: add("filter", b, f"{ws.title}!{hr}", "no filter on the table")
    if not ws.print_title_rows: add("print_setup", b, f"{ws.title}!{hr}", "header row not repeated on printed pages")

try: from xl_style import pages_wide, PAGE_PT   # the build's rule: one page wide while the fit scale stays >= 60 %, else more pages across
except Exception: pages_wide, PAGE_PT = (lambda widths: 1), None

def visible_widths(ws):
    """widths of the printed columns (hidden / collapsed columns excluded); Excel's saved padding (+0.71) is cut off"""
    from openpyxl.utils import column_index_from_string
    dims = {}
    for key, cd in ws.column_dimensions.items():   # min/max come from the file; a dimension set in memory has only its letter
        lo = cd.min or column_index_from_string(key)
        for c in range(lo, (cd.max or lo) + 1): dims[c] = cd
    return [int((dims[c].width if c in dims and dims[c].width else 16)) for c in range(1, ws.max_column + 1) if not (c in dims and dims[c].hidden)]

def _format_checks(ws, style, add, b, ss=None):
    ps = ws.page_setup; fit = ws.sheet_properties.pageSetUpPr; widths = visible_widths(ws)
    want = int((ss or {}).get("pages_wide") or pages_wide(widths)); got = int(ps.fitToWidth) if ps.fitToWidth not in (None, "") else 1   # Excel omits fitToWidth="1" (its default) when it saves
    wide = PAGE_PT is not None and sum((7 * w + 5) * 0.75 for w in widths) > PAGE_PT * 0.707   # wider than a portrait page
    if not (fit is not None and fit.fitToPage): add("print_setup", b, ws.title, "print setup: fit to page is off")
    elif got != want: add("print_setup", b, ws.title, f"print setup: {got} page(s) wide, the column widths need {want}")
    if wide and ps.orientation != "landscape": add("print_setup", b, ws.title, f"print setup: orientation {ps.orientation} on a sheet wider than a portrait page")
    if _rgb(ws.sheet_properties.tabColor) not in style["tabs"]: add("tab_colour", b, ws.title, f"tab colour {_rgb(ws.sheet_properties.tabColor)} is not a role colour ({', '.join(sorted(style['tabs']))})")

def _range_values(b, ref):
    """cached / literal values of a one-column range Sheet!$A$2:$A$5000 (None when the sheet is missing or the range is wider)"""
    m = re.match(r"(?:'([^']+)'|([^!]+))!\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)$", ref.strip())
    if not m or m.group(3) != m.group(5) or (m.group(1) or m.group(2)) not in b.names: return None
    sheet = m.group(1) or m.group(2); ws = b.wb[sheet]
    return [b.value(sheet, f"{m.group(3)}{r}") for r in range(int(m.group(4)), min(int(m.group(6)), ws.max_row) + 1)]

def _value_checks(b, sheets, add):
    """cached values only: formula errors anywhere; single COUNTIF/COUNTA/SUM aggregates on summary/overview re-evaluated on the detail sheets."""
    for ws in b.vb:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.strip() in ERRORS: add("formula_error", b, f"{ws.title}!{c.coordinate}", f"{c.value} ({b.wb[ws.title][c.coordinate].value})")
    for ws in sheets:
        for row in ws.iter_rows():
            for c in row:
                m = re.fullmatch(r"=(COUNTIF|COUNTA|SUM)\(([^,()]+?)(?:,\s*\"([^\"]*)\")?\)", c.value.strip()) if isinstance(c.value, str) else None
                vals = _range_values(b, m.group(2)) if m else None
                if vals is None: continue
                fn, crit = m.group(1), m.group(3)
                if fn == "COUNTIF":
                    if crit is None or any(ch in crit for ch in "*?<>="): continue
                    exp = sum(1 for v in vals if v is not None and str(v).lower() == crit.lower())
                    if exp == 0 and any(v not in (None, "") for v in vals): add("zero_match", b, f"{ws.title}!{c.coordinate}", f"counts '{crit}', a value that never occurs in {m.group(2)} (label drift?)")
                elif fn == "COUNTA": exp = sum(1 for v in vals if v not in (None, ""))
                else: exp = sum(v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool))
                got = b.vb[ws.title][c.coordinate].value
                if isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - exp) > 1e-6: add("reconciliation", b, f"{ws.title}!{c.coordinate}", f"shows {got}, the detail sheet gives {exp} ({c.value})")

def hygiene_text(rep, top=3):
    out = [f"{k:18s} {n:5d} {CHECKS[k]:7s} e.g. " + " | ".join(f"{x['file']} {x['where']}: {x['text'][:90]}" for x in [y for y in rep["findings"] if y["check"] == k][:top]) for k, n in rep["counts"].items() if n]
    return "\n".join(out + [f"HYGIENE {'CLEAN' if rep['passed'] else 'FAILED'}: {rep['errors']} error(s), {rep['warnings']} warning(s) in {len(rep['files'])} workbook(s)"])

def edition_files(cfg, edition="customer", keys=None):
    """built workbooks of the customer edition (deliverables/<file>), the full edition (deliverables/intern/<file>) or both"""
    out = []
    for k, v in (cfg.get("deliverables") or {}).items():
        if not isinstance(v, dict) or not str(v.get("file", "")).endswith(".xlsx") or (keys and k not in keys): continue
        for sub in (["deliverables"] if edition in ("customer", "both") else []) + (["deliverables/intern"] if edition in ("full", "both") else []):
            if os.path.exists(os.path.join(ROOT, sub, v["file"])): out.append(os.path.join(ROOT, sub, v["file"]))
    return out

def write_round(rep, rnd, edition="customer"):
    d = os.path.join(ROOT, "analysis", "gate"); os.makedirs(d, exist_ok=True)
    json.dump(dict(rep, round=rnd, edition=edition), open(os.path.join(d, f"round{rnd}-hygiene.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(d, f"round{rnd}-hygiene.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# Hygiene round {rnd} ({edition} edition): {'CLEAN' if rep['passed'] else 'FAILED'}\n\n| check | severity | findings |\n|---|---|---|\n" + "".join(f"| {k} | {CHECKS[k]} | {n} |\n" for k, n in rep["counts"].items() if n)
                 + "\n## Findings\n\n" + "".join(f"- [{x['check']}] {x['file']} {x['where']}: {x['text']}\n" for x in rep["findings"]))
    return f"analysis/gate/round{rnd}-hygiene.json"

def main_standalone(a, p):
    ed = a[a.index("--edition") + 1] if "--edition" in a else "customer"
    keys = [x for x in a if x in p["deliverables"]]; files = [x if os.path.isabs(x) else os.path.join(ROOT, x) for x in a if x.endswith(".xlsx")]
    if "--all" in a or keys or not files: files += edition_files(p, ed, keys or None)
    if not files: sys.exit("no workbook found (build first: dbcx build_excel --all)")
    rep = standalone(files, p)
    if "--round" in a: print("wrote " + write_round(rep, int(a[a.index("--round") + 1]), ed) + " + .md")
    if "--json" in a: print(json.dumps(rep, indent=1, ensure_ascii=False))
    else:
        print(hygiene_text(rep))
        if "--fix-list" in a: print("\n".join(f"- [{x['check']}] {x['file']} {x['where']}: {x['text']}" for x in rep["findings"]))
    sys.exit(0 if rep["passed"] else 1)

def main():
    a = sys.argv[1:]; p = project()
    if "--standalone" in a: return main_standalone(a, p)
    ml = p["_method"].get("lint", {}); p = dict(p); p["lint"] = {"forbidden_terms": p["lint"].get("forbidden_terms", []) + ml.get("forbidden_terms", []), "allow_terms": p["lint"].get("allow_terms", []) + ml.get("allow_terms", [])}
    forb, allow = rules(p); hits = []
    mds = [a[i + 1] for i, x in enumerate(a) if x == "--md"]
    keys = [x for x in a if x in p["deliverables"]]; files = [x for x in a if x.endswith(".xlsx")]
    if not keys and not files and not mds: keys = [k for k, v in p["deliverables"].items() if isinstance(v, dict) and (v.get("enabled") or os.path.exists(os.path.join(ROOT, "deliverables", v.get("file", ""))))]
    for k in keys:
        f = os.path.join(ROOT, "deliverables", p["deliverables"][k]["file"])
        if os.path.exists(f): hits += lint_xlsx(f, forb, allow)
    for f in files: hits += lint_xlsx(f if os.path.isabs(f) else os.path.join(ROOT, f), forb, allow)
    for f in mds: hits += lint_md(f if os.path.isabs(f) else os.path.join(ROOT, f), forb, allow)
    if "--json" in a: print(json.dumps(hits, indent=1, ensure_ascii=False))
    else:
        by = {}
        for h in hits: by.setdefault((h["file"], h["where"].split("!")[0] if "!" in h["where"] else h["where"]), []).append(h)
        for (f, sheet), hs in sorted(by.items()): print(f"{f} {sheet}: {len(hs)} hit(s), e.g. [{hs[0]['term']}] {hs[0]['where']}: ...{hs[0]['context']}...")
        if "--fix-list" in a:
            for h in hits: print(f"- {h['file']} {h['where']} [{h['term']}]: {h['context']}")
    print(f"{len(hits)} process-language hit(s)" + ("" if hits else " - client-facing wording is clean"))
    sys.exit(1 if hits else 0)

if __name__ == "__main__":
    main()
