#!/usr/bin/env python3
"""Build the Excel deliverables from the analysis JSON, driven by the method's deliverables.<lang>.json (+ engine common wording + <run>/overrides).
Usage: dbcx build_excel <D..> | --all   [--edition customer|full|both] [--interim] [--internal] [--check] [--force] [--allow-process-language] [--allow-modified-scores]
  --edition   customer -> deliverables/<file> (ready to send: no claims sheet, no Offene_Fragen); full -> deliverables/intern/<file>
              (customer + claims sheet(s) + Offene_Fragen); default both. Result sheets and formatting are identical.
  --interim   build from passed/final scopes only into work/interim/<date>/ (+ intern/) with an INTERIM banner sheet (team checkpoint, never a client file)
  --internal  also write work/internal/<D>_Review_Notes.xlsx: the critics' notes per claim + full copies of the table sheets incl. `internal` columns
  --check     validate the merged spec (ids, placeholders, emphasis budget, dataset fields, patches) and the method's run configuration rules
              (methods/<m>/validate.py check_config(cfg), optional) and print the effective sheet/column list; writes nothing
  --force     build a scope whose analysis is still `status: draft` (mid-gauntlet) - refused otherwise
  questions   Annahmen / Offene_Fragen show released questions only (human_input.release batched); a build that is not --interim refuses
              while a question is unreleased (`dbcx questions release --all`)
              a kept question (`dbcx questions keep`, resolution assumption_kept) leaves Offene_Fragen and stays on Annahmen; reopen brings it back
  after writing, `dbcx lint_deliverable` runs on both editions; process or versioning language fails the build unless --allow-process-language.
Principles:
  * Result sheets show results only: claim ids resolve to their own locators, PS-7-NNN -> [Qn] (sheet Quellen), client questions -> A-nn (sheet Annahmen);
    each verdict row carries `Grundlage` (Code / Herstellerdokumentation / Annahme (A-nn)) derived from its own evidence.
  * Every aggregate (count, sum, share, score, formula classification) is an Excel formula over the detail sheets.
  * Process (claims, reviewer scores, questions, answers) appears only on the claims sheet and Offene_Fragen of the full edition.
  * One style system (engine common spec `style`): valantic palette, header tiers, at most max_decision_columns status-coloured columns per sheet.
Datasets: engine (claims, client_questions, parameters) + methods/<m>/datasets.py DATASETS (row providers over the loaded JSON, see there).
Spec placeholders usable in formulas:  {r} current row  {MAXR} last row  {rng:Sheet.col_id} -> Sheet!$X$2:$X$MAXR
  {col:col_id} column letter in this sheet  {cell:col_id} -> X{r}  {L:token} display label  {p:param} -> Parameters!$B$n  {row} -> $A{r}  {x:key} extra context value
  {pt:table.col} -> a parameter table column's data range  {pt:table.col.key} -> its cell in the row whose first column is key
  Option repeats ({"repeat": "options", "columns": [...]}, xl_spec.expand_repeats) substitute {o.id|label|start|pack|...} before the build.
  Column `formula_field: "<field>"`: a row whose field holds a formula template gets that formula (same placeholders), other rows the column's `field` value.
  Management summary text: {kpi:<id>} -> the live KPI value (the paragraph becomes a formula).
  Column `input_field: "<field>"`: the cells of rows whose field is set get the input fill (a value someone else enters, e.g. a partner's estimate);
  `grundlage_default_field: "<field>"`: a row whose field is set names that basis first (an owner's input cell), before what else it rests on.
  Sheet `dataset: "<dataset>:<argument>"` calls the method dataset with an argument (one sheet per group, e.g. a `{"repeat": ..., "sheets": [...]}` entry).
  Parameter sheet: a scalar row with `validation` ("a,b" or a list) gets a dropdown; a table's rows may be a {key: {column: value}} mapping, a header with
  `label: true` shows display labels. Overview sheets print as many pages wide as their columns need.
"""
import json, os, sys, glob, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, WORK_DIR, REQ_PATH, REF_DIR, project, method, labels, deliverables_spec, load_json, fmt as cfg_fmt, resolve_ref, load_method_module, scope_info, scope_critics, is_consolidated, relp
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import Reference
import xl_style as X
from xl_transform import Transformer, basis, is_vendor_code, code_free, vendor_address, split_entries, qmap_of, assumption_numbers, answers_of, answer_type, answer_text, is_client, client_answered, affected, default_wording, if_not_text, why_text, norm_txt
from xl_spec import validate, col_key, is_evidence, is_internal, confidence_defaults, subst_option, option_blocks, decision_budget, budget_errors, KPI_RE

P = project(); METHOD = P["_method"]; LANG = P["languages"]["deliverable"]; L = labels(LANG)
SPEC = deliverables_spec(LANG); CM = SPEC["common"]
MAXR = 5000
INTERIM = "--interim" in sys.argv
_ED = sys.argv[sys.argv.index("--edition") + 1] if "--edition" in sys.argv else "both"
EDITIONS = ["customer", "full"] if _ED == "both" else [_ED]
DELIV = os.path.join(WORK_DIR, "interim", time.strftime("%Y-%m-%d")) if INTERIM else os.path.join(ROOT, "deliverables")
FINAL = ("final", "passed", "failed-gauntlet", "passed-rework-ordered")
X.configure(SPEC.get("style", {}), cfg_fmt(SPEC.get("style", {}).get("footer", ""), P))
NOTES = confidence_defaults(SPEC)   # build notes (printed after the build)

def g(v, ctx=None):
    """Label lookup for VALUES: an unknown key is echoed back so a client-facing enum never disappears silently. That makes it
    unusable as a fallback SOURCE - for text the builder composes, use L.get(key, <client-facing default>)."""
    if isinstance(v, bool): v = "true" if v else "false"
    if v is None: return ""
    if ctx and f"{v}_{ctx}" in L: return L[f"{v}_{ctx}"]
    return L.get(v, v) if isinstance(v, str) else v
def critic(cr):   # reviewer names never share the enum namespace ('standard' is a value); a per-pack critic: "<standard label> (<pack>)"
    if str(cr).startswith("standard-") and not L.get(f"critic_{cr}"): return f"{L.get('critic_standard') or 'standard'} ({cr[len('standard-'):]})"
    return L.get(f"critic_{cr}") or g(cr)
def j(lst, sep="; "): return sep.join(str(x) for x in (lst or []))
def get(d, path, default=""):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur: cur = cur[part]
        else: return default
    return cur if cur is not None else default
def fmt(s, **kw): return cfg_fmt(s, P, **kw)
BASIS_L = {k: fmt(L.get(k, "")) for k in ("basis_code", "basis_vendor", "basis_assumption", "basis_client", "basis_vendor_code", "basis_handover")}; BASIS_L["src"] = fmt(L.get("src_client_answer", ""))
# the client-workbook label as a pattern ("Anforderungsliste <client> (…), Zeile n"): such evidence is information stated by the client
CELL_RE = re.compile("^" + re.sub(r"\\\{(?:sheet|row|file)\\\}", ".+?", re.escape(fmt(L.get("src_client_workbook", "{sheet}, {row}")))) + "$") if L.get("src_client_workbook") else None
def edition_of(sh): return sh.get("edition") or ("full" if sh["type"] == "claims" else "both")
def visible(sh, review=False, edition="full"):   # `internal` columns only in the review copies; `edition: full` columns not in the customer edition
    return [c for c in sh.get("columns", []) if (review or not is_internal(c)) and (edition != "customer" or c.get("edition") != "full")]
def tier(c): return c.get("emphasis") if c.get("emphasis") in ("decision", "support") else "normal"
def clip(v): return v[:32000] if isinstance(v, str) and len(v) > 32000 else v

# ------------------------------------------------------------------ data loading (engine base + method datasets.py)
def client_questions():
    """Questions to the client from state/QUESTIONS.json (legacy Markdown tables until `dbcx questions migrate`)."""
    from common import load_questions

    def asker_label(v):
        """Who raised a question is a fact about the ANALYSIS, not about a role in the run: the client workbook
        names the subject area a question came out of, never an internal role such as orchestrator or critic."""
        v = (v or "").strip()
        if not v or v.lower() in ("orchestrator", "lead", "inventory", "consolidator") or v.lower().startswith(("critic", "gate", "postpass", "researcher")):
            # g() echoes an unknown key back, so never use it as a fallback source - look the label up explicitly.
            return L.get("raised_by_analysis") or ("Code-Analyse" if LANG == "de" else "Code analysis")
        return v

    rows = []
    for q in load_questions():
        if not is_client(q) or q.get("released") is False: continue   # human_input.release batched: released questions only
        if q.get("resolution") == "assumption_kept": continue   # kept: no longer asked - it stays on the Annahmen sheet only
        ans = (answers_of(q) or [None])[-1] or {}
        # An answer the RUN found (a later scope settled it; author is not the lead) is not a decision the client still owes:
        # the sheet says so instead of listing it as open. Status keys are labelled, never shown raw.
        found = bool(ans) and (ans.get("by") or "lead") not in ("lead", "client") and (q.get("status") or "open") == "open"
        at = answer_type(q)
        rows.append({"id": q.get("id"), "question": q.get("question", ""), "effect": q.get("effect", ""), "raised_by": asker_label(q.get("from", "")), "status": L.get("answered_by_analysis", "answered by the analysis") if found else g(q.get("status", "")),
                     "answer_type": fmt(L.get(at, "")) if at else "", "answer": answer_text(q)})
    return rows

def load_all():
    st = load_json("state/STATUS.json", {"scopes": {}, "phases": {}}); m = METHOD
    D = {"status": st, "req": load_json(REQ_PATH, {"requirements": [], "phase_values_in_scope": []}), "scopes": {}, "inventory": None, "cons": {}, "client_questions": client_questions()}
    for p in sorted(glob.glob(os.path.join(ROOT, m["scopes"].get("output_dir", "analysis/scopes"), "*.json"))):
        d = json.load(open(p, encoding="utf-8")); name = os.path.basename(p)[:-5]
        if INTERIM and st["scopes"].get(name, {}).get("status") not in FINAL: continue
        D["scopes"][name] = d
    inv = m.get("inventory")
    if inv:
        D["inventory"] = load_json(scope_info(inv["scope"], m)[0], {}) or None
        ph = next((x for x in m["phases"] if x.get("scope") == inv["scope"]), None)
        if INTERIM and D["inventory"] and ph and st["phases"].get(ph["id"], {}).get("status") not in FINAL: D["inventory"] = None
    for x, c in m.get("consolidations", {}).items():
        D["cons"][x] = load_json(scope_info(x, m)[0], {}) or None
        ph = next((p_ for p_ in m["phases"] if p_.get("scope") == x), None)
        if INTERIM and D["cons"][x] and ph and st["phases"].get(ph["id"], {}).get("status") not in FINAL: D["cons"][x] = None
    if MDS and hasattr(MDS, "load"): MDS.load(D, ROOT, INTERIM)
    return D

def latest_scores(scope):
    d = os.path.join(ROOT, "analysis", "gauntlet", scope); out = {}
    if not os.path.isdir(d): return out, 0
    crit = P["scoring"]["critics"]
    rounds = sorted({int(m.group(1)) for f in os.listdir(d) for m in [re.match(r"round(\d+)-(.+)\.json", f)] if m and m.group(2) in crit})
    if not rounds: return out, 0
    r = rounds[-1]
    resp = os.path.join(d, f"round{r}-result.json"); checks = json.load(open(resp, encoding="utf-8")).get("checksums", {}) if os.path.exists(resp) else {}
    for c in crit:
        fp = os.path.join(d, f"round{r}-{c}.json")
        if os.path.exists(fp) and checks.get(c) and "--allow-modified-scores" not in sys.argv:
            import hashlib
            if hashlib.sha256(open(fp, "rb").read()).hexdigest() != checks[c]: raise SystemExit(f"GUARD: {relp(fp, ROOT)} was modified after `dbcx score_aggregate {scope} {r}` (checksum mismatch). Scores are never edited by hand; re-run score_aggregate or pass --allow-modified-scores with a logged reason.")
        if os.path.exists(fp):
            for s in json.load(open(fp, encoding="utf-8"))["scores"]: out.setdefault(s["claim_id"], {})[c] = s["score"]; out[s["claim_id"]][c + "_issue"] = s.get("issue", "")
    return out, r

# ------------------------------------------------------------------ datasets: engine + method
MDS = load_method_module("datasets")
if MDS and hasattr(MDS, "_bind"): MDS._bind(g)
def ds_client_questions(D): return D["client_questions"]
DATASETS = {"client_questions": ds_client_questions}
if MDS: DATASETS.update(getattr(MDS, "DATASETS", {}))
def ds_rows(name, D):
    """the rows of a sheet's dataset; "<dataset>:<argument>" calls one dataset with an argument (one sheet per group of a run)"""
    n, _, arg = str(name).partition(":")
    return DATASETS[n](D, arg) if arg else DATASETS[n](D)

def claim_scopes(D, selector):
    """[(scope, claims)] for a Claims sheet: 'scopes' = every per-scope analysis, 'all' = everything, an inventory / consolidation id, or a method dataset name via datasets.claim_scopes."""
    m = METHOD; inv = m.get("inventory")
    if MDS and hasattr(MDS, "claim_scopes"):
        r = MDS.claim_scopes(D, selector)
        if r is not None: return r
    if selector == "scopes" or selector == "units": return [(n, D["scopes"][n].get("claims", [])) for n in sorted(D["scopes"])]
    if inv and selector == inv["scope"]: return [(selector, (D["inventory"] or {}).get("claims", []))]
    if selector in D["cons"]: return [(selector, (D["cons"][selector] or {}).get("claims", []))]
    if selector == "all":
        out = [(n, D["scopes"][n].get("claims", [])) for n in sorted(D["scopes"])]
        if inv and D["inventory"]: out.append((inv["scope"], D["inventory"].get("claims", [])))
        out += [(x, (d or {}).get("claims", [])) for x, d in D["cons"].items()]
        return out
    return []

def available(D, name):
    m = METHOD; inv = m.get("inventory")
    if name in ("scopes", "units"): return bool(D["scopes"])
    if inv and name in (inv["scope"], "inventory"): return bool(D["inventory"])
    if name in D["cons"]: return bool(D["cons"][name])
    if name == "req": return bool(D["req"]["requirements"])
    if MDS and hasattr(MDS, "available"):
        r = MDS.available(D, name)
        if r is not None: return r
    return bool(D.get(name))

def source_status(key):
    """The analysis whose `status: draft` refuses a final build of deliverable key (inventory or consolidation with deliverable == key)."""
    m = METHOD
    for ph in m["phases"]:
        if ph.get("deliverable") == key and ph.get("scope"): return load_json(scope_info(ph["scope"], m)[0], {}).get("status")
    return None

# ------------------------------------------------------------------ per-deliverable preparation: data, claims index, assumptions
class Prep:
    """Everything both editions share: dataset rows per table sheet, the claim index for the evidence transform, the question
    register mapped to A-nn, and each assumption's affected row keys (-> Grundlage links, Annahmen sheet)."""
    def __init__(self, key, dspec, D):
        from common import load_questions
        self.data = {sh["name"]: ds_rows(sh["dataset"], D) for sh in dspec["sheets"] if sh["type"] == "table"}
        self.claims = {c["id"]: c.get("evidence", []) for _, cl in claim_scopes(D, "all") for c in cl if c.get("id")}
        for _, cl in ((s, c) for sh in dspec["sheets"] if sh["type"] == "claims" for s, c in claim_scopes(D, sh["scopes"])):
            for c in cl: self.claims.setdefault(c["id"], c.get("evidence", []))
        self.questions = [q for q in load_questions() if q.get("released") is not False]; self.qmap = qmap_of(self.questions); nums = assumption_numbers(self.questions)   # released only
        self.keys = self.row_keys(dspec); self.known = known = set(self.keys) | global_row_keys(D)
        self.assumptions = []
        for q in self.questions:
            if not is_client(q) or client_answered(q): continue
            aff = affected(q, known); dk = [a for a in (q.get("affects") or []) if a in SPEC["deliverables"]]
            wording = (q.get("assumption") or "").strip()
            self.assumptions.append({"id": nums[q["id"]], "q": q, "affected": aff, "deliverables": dk, "defaulted": not wording,
                                     "wording": wording or default_wording(q, CM["assumptions"]["default_wording"])})
        self.links = {}; self.client_links = set()   # row keys resting on an answer BY the client (a fact: "Angabe <client>")
        for q in self.questions:
            if is_client(q) and client_answered(q): self.client_links.update(affected(q, known))
        for a in self.assumptions:
            for k in a["affected"]: self.links.setdefault(k, []).append(a["id"])
        self.valid_a = {a["id"] for a in self.assumptions}
        self.client_a = {nums[q["id"]] for q in self.questions if is_client(q) and client_answered(q)}   # cited bare: "Angabe <client> (A-nn)"
        self.as_ids = {(m.group(1), m.group(2)): f"A-{int(a.group(1)):02d}" for q in self.questions if (m := re.fullmatch(r"Q-(.+)-(AS-\d+)", q.get("id", ""))) and (a := re.fullmatch(r"A-(\d+)", str(q.get("assumption_id") or "").strip()))}   # (scope, AS-nn) -> the customer Annahmen id
        self.dspec = dspec; self.vendor_q = None   # opt-in `vendor_code_basis`: the [Qn] whose source address is vendor standard code
        if dspec.get("vendor_code_basis"):
            self.vendor_q = {n for n, c in reference_rows()[0].items() if len(c) > 3 and is_vendor_code(str(c[3]))}
            if not BASIS_L.get("basis_vendor_code"): NOTES.append(f"{key}: vendor_code_basis is set but the label basis_vendor_code is missing - vendor-code rows read '{BASIS_L['basis_vendor']}'")
    def row_keys(self, dspec):
        return {str(get(r, sh["row_key"], "")) for sh in dspec["sheets"] if sh["type"] == "table" and sh.get("row_key") for r in self.data[sh["name"]] if isinstance(r, dict) and get(r, sh["row_key"], "")} \
            | {k for sh in dspec["sheets"] if sh["type"] == "table" for r in self.data[sh["name"]] for k in grundlage_keys(sh, r)}

KEY_LABELS = {}   # composite row key -> how the client reads it (a dataset's `grundlage_key_labels` field), for the Annahmen sheet
def grundlage_keys(sh, row):
    """composite row keys of the sheet's `grundlage_key: "<field>@<suffix>"` columns (req_id@brownfield -> FR-041@brownfield): an
    assumption or client answer that `affects` such a key marks only that column; one on the plain row key marks every column.
    `grundlage_key: "<field>"` (no @): the row's field holds the composite key(s) itself - a string or a list (e.g. a work package's
    cell and package key); `grundlage_key_labels: "<field>"` = the row's {key: label} the Annahmen sheet shows instead of the key"""
    out = []
    for c in sh.get("columns", []):
        f, sep, suf = str(c.get("grundlage_key") or "").partition("@")
        if not (c.get("grundlage") and f and isinstance(row, dict) and get(row, f, "")): continue
        if sep: out.append(f"{get(row, f, '')}@{suf}"); continue
        v = get(row, f, ""); ks = [str(x) for x in (v if isinstance(v, list) else [v]) if str(x or "").strip()]; out += ks
        lab = get(row, c["grundlage_key_labels"], None) if c.get("grundlage_key_labels") else None
        if isinstance(lab, dict): KEY_LABELS.update({k: str(lab[k]) for k in ks if lab.get(k)})
    return out

_GK = {}
def global_row_keys(D):
    """Row keys of every deliverable's `row_key` sheets: an assumption names the same affected rows in every workbook."""
    if "k" not in _GK:
        ks = set()
        for d in SPEC["deliverables"].values():
            for sh in d.get("sheets", []):
                if sh.get("type") == "table" and sh.get("row_key") and sh.get("dataset") in DATASETS:
                    try: ks |= {str(get(r, sh["row_key"], "")) for r in DATASETS[sh["dataset"]](D) if isinstance(r, dict) and get(r, sh["row_key"], "")}
                    except Exception: pass
                if sh.get("type") == "table" and sh.get("dataset") in DATASETS and any(c.get("grundlage_key") for c in sh.get("columns", [])):
                    try: ks |= {k for r in DATASETS[sh["dataset"]](D) for k in grundlage_keys(sh, r)}
                    except Exception: pass
        _GK["k"] = ks
    return _GK["k"]

def transformer(prep):
    def cell_label(sheet, row, path): return fmt(L.get("src_client_workbook", "{sheet}, {row}"), sheet=sheet, row=row, file=os.path.basename(path))
    rh = prep.dspec.get("resolve_handover")
    return Transformer(prep.claims, prep.qmap, cell_label, fmt(L.get("src_client_answer", "")), handover_locators(rh) if rh else None, prep.dspec.get("code_locators") is not False, prep.client_a)

_HO = {}
def handover_locators(types):
    """Opt-in `resolve_handover: true | [types]`: HO-<type>#<id> -> the repository locators the imported artefact
    (input/handover/<type>.json) carries for that row - its evidence fields and the evidence of the artefact's claims on it - so
    the row's Grundlage reads "Code". None (the citation stays a client statement) when the row carries no repository locator."""
    from xl_transform import HO_RE, is_repo_locator, is_client_doc, INTERNAL_RE
    def load(t):
        if t not in _HO:
            env = load_json(os.path.join("input", "handover", f"{t}.json"), {}) or {}; data = env.get("data", env) if isinstance(env, dict) else {}
            _HO[t] = (data if isinstance(data, dict) else {}, {c.get("id"): c.get("evidence", []) for c in (data.get("claims") or []) if isinstance(c, dict)} if isinstance(data, dict) else {})
        return _HO[t]
    def resolve(entry):
        m = HO_RE.match(entry)
        if not m or (types is not True and m.group(1) not in (types or [])): return None
        data, claims = load(m.group(1)); rid = m.group(2)
        row = next((r for k, v in data.items() if k != "claims" and isinstance(v, list) for r in v if isinstance(r, dict) and (r.get("rid") == rid or str(next(iter(r.values()), "")) == rid)), None)
        if row is None: return None
        ents = [e for f, v in row.items() if f == "evidence" or f.endswith("_evidence") for e in split_entries(v)]
        ents += [e for cid in row.get("claimed_by") or [] for e in split_entries(claims.get(cid))]
        locs = [e for e in ents if is_repo_locator(e) and not is_client_doc(e) and not INTERNAL_RE.search(e)]
        return list(dict.fromkeys(locs)) or None
    return resolve

# ------------------------------------------------------------------ spec resolution
def conf_value(v, where):
    """`"$a.b"` -> the configuration value (parameter values and table rows may come from run.json / method defaults)"""
    try: return resolve_ref(v, P)
    except (KeyError, TypeError): sys.exit(f"SPEC ERROR: {where}: {v} names no configuration value - run `dbcx build_excel --check`")

def param_tables(sh):
    """[(table, header row, columns, value rows, first column)] of a parameters sheet's `tables`, written below the scalar rows
    (one blank row, a title row when the table has a `title`) - or, with `tables_beside: true`, stacked from row 2 in the columns
    right of the scalar table (one spacer column), so their column widths are their own. Header entries: "<id>" or
    {id, header, width, from, default, label}; rows: lists (positional), dicts by column id (a missing id falls back to the row's `from`
    key, then `default`), a {key: value} mapping for a two-column table, a {key: {column id: value}} mapping (the key fills the first
    column), or "$config.ref" to any of these. A header with `label: true` shows its values as display labels."""
    beside = bool(sh.get("tables_beside")); r = 2 if beside else max(1, len(sh.get("rows", []))) + 3; out = []
    c0 = len(sh.get("headers", [])) + 2 if beside else 1
    for t in sh.get("tables") or []:
        cols = [h if isinstance(h, dict) else {"id": h, "header": h} for h in t.get("headers", [])]
        raw = conf_value(t.get("rows", []), f"{sh['name']}/{t.get('id')}") if isinstance(t.get("rows"), str) else t.get("rows", [])
        if isinstance(raw, dict): raw = [dict(v, **{cols[0]["id"]: k}) if isinstance(v, dict) and cols else [k, v] for k, v in raw.items()]
        rows = [list(x) if isinstance(x, (list, tuple)) else [x.get(c["id"], x.get(c.get("from"), c.get("default"))) for c in cols] for x in raw or []]
        if t.get("title"): r += 1
        out.append((t, r, cols, rows, c0)); r += max(1, len(rows)) + 2
    return out

class Ctx:
    def __init__(self, dspec, review=False, edition="full"):
        self.cols = {}   # sheet name -> {col_id: letter}; `internal` columns only exist in the review copies
        self.params = {}; self.extra = {}; self.kpi = {}; self.ptab = {}; self.first = {}   # first data row per table sheet (3 below option bands)
        self.na = set(dspec.get("not_assessed") or [])   # table sheets this run does not assess: a formula over one shows `not_assessed`, never a zero
        for sh in dspec["sheets"]:
            if sh["type"] == "table":
                self.cols[sh["name"]] = {col_key(c): get_column_letter(i + 1) for i, c in enumerate(visible(sh, review, edition))}; self.first[sh["name"]] = header_row(sh, review) + 1
            if sh["type"] == "parameters":
                self.cols[sh["name"]] = {"name": "A", "value": "B", "meaning": "C"}
                for i, prm in enumerate(sh["rows"]): self.params[prm["name"]] = f"{sh['name']}!$B${i + 2}"
                for t, hr, tcols, trows, c0 in param_tables(sh):
                    self.ptab[t["id"]] = {"sheet": sh["name"], "first": hr + 1, "last": hr + max(1, len(trows)), "cols": {c["id"]: get_column_letter(c0 + i) for i, c in enumerate(tcols)},
                                          "keys": {str(x[0]): hr + 1 + k for k, x in enumerate(trows) if x}}
    def ptref(self, m):
        """{pt:<table>.<col>} -> the column's absolute data range; {pt:<table>.<col>.<key>} -> the cell in the row whose first column is <key>"""
        tid, _, rest = m.group(1).partition("."); cid, _, key = rest.partition("."); t = self.ptab.get(tid)
        if not t or cid not in t["cols"]: sys.exit(f"SPEC ERROR: {{pt:{m.group(1)}}} names no parameter table column - run `dbcx build_excel --check`")
        c = t["cols"][cid]
        if not key: return f"{t['sheet']}!${c}${t['first']}:${c}${t['last']}"
        if key not in t["keys"]: sys.exit(f"SPEC ERROR: {{pt:{m.group(1)}}}: parameter table '{tid}' has no row '{key}'")
        return f"{t['sheet']}!${c}${t['keys'][key]}"
    def is_na(self, s): return bool(self.na) and any(x.split(".")[0] in self.na for x in re.findall(r"\{rng:([^}]+)\}", str(s or "")))
    def formula(self, s, sheet=None, r=None):
        if self.is_na(s): return fmt(L["not_assessed"])
        def rng(m):
            sh, cid = m.group(1).split(".")
            if cid not in self.cols.get(sh, {}): sys.exit(f"SPEC ERROR: {{rng:{m.group(1)}}} names no visible column (internal or missing) - run `dbcx build_excel --check`")
            return f"{sh}!${self.cols[sh][cid]}${self.first.get(sh, 2)}:${self.cols[sh][cid]}${MAXR}"
        s = re.sub(r"\{pt:([^}]+)\}", self.ptref, s)
        s = re.sub(r"\{rng:([^}]+)\}", rng, s)
        s = re.sub(r"\{L:([^}]+)\}", lambda m: str(g(*m.group(1).split("|"))), s)
        s = re.sub(r"\{p:([^}]+)\}", lambda m: self.params[m.group(1)], s)
        s = re.sub(r"\{x:([^}]+)\}", lambda m: str(self.extra.get(m.group(1), "")), s)
        if sheet: s = re.sub(r"\{col:([^}]+)\}", lambda m: self.cols[sheet][m.group(1)], s); s = re.sub(r"\{cell:([^}]+)\}", lambda m: f"{self.cols[sheet][m.group(1)]}{r}", s)
        if r is not None: s = s.replace("{r}", str(r)).replace("{row}", f"$A{r}")
        return fmt(s.replace("{MAXR}", str(MAXR)))

# ------------------------------------------------------------------ sheet writers
def cell_value(col, row):
    if "const" in col: return col["const"]
    v = get(row, col["field"], None) if isinstance(row, dict) else None
    if isinstance(v, list): return j([g(x, col.get("label_ctx")) if col.get("label") else x for x in v], col.get("sep", "; "))
    if col.get("label"): return g(v, col.get("label_ctx"))
    return v if v not in (None, "") else col.get("default", "" if not col.get("numeric") else 0)

def status_map(c):
    """Status tokens of a decision column: `status` or the legacy `colors` mapped (GREEN/BLUE -> standard, YELLOW/ORANGE -> rework, RED -> rebuild, GREY -> neutral)."""
    return dict(c.get("status") or {}) or {t: X.status_key(v) for t, v in (c.get("colors") or {}).items()}

def header_row(sh, review=False): return 2 if option_blocks(visible(sh, review)) else 1   # option bands take row 1

def cust(T, v, scope, sheet, r):
    """customer edition: the locator rewrite of one cell value; what stays unresolved goes to the build notes"""
    n = len(T.open_refs); out = T.customer(v, scope)
    if len(T.open_refs) > n: NOTES.append(f"{sheet} row {r}: unresolved {', '.join(dict.fromkeys(T.open_refs[n:]))}" + (f" (scope {scope})" if scope else "") + " - needs a text post-pass")
    return out

def sheet_table(ws, sh, ctx, T, prep, where, review=False, edition="full"):
    allc = visible(sh, review); cols = visible(sh, review, edition); data = prep.data[sh["name"]]; name = sh["name"]; rk = sh.get("row_key"); rows = []; kinds = []
    shown = [i for i, c in enumerate(allc) if any(c is x for x in cols)]   # a full-edition column (evidence) still feeds the Grundlage of the customer edition
    evid = [col_key(c) for c in allc if is_evidence(c)]; nb = 0; hr = header_row(sh, review); d0 = hr + 1
    tk = rk or (allc[0].get("field") if allc else None)   # text_by_key matches this row key
    for c in allc:
        bad = sorted(set(c.get("text_by_key") or {}) - {str(get(r_, tk, "")) for r_ in data if isinstance(r_, dict)} if tk else c.get("text_by_key") or {})
        if bad: NOTES.append(f"{where}/{name}: text_by_key of '{col_key(c)}' names unknown row key(s): {', '.join(bad)}")
    for i, row in enumerate(data):
        r = i + d0; vals = []; ents = {}; texts = []; scope = get(row, "scope", None) if isinstance(row, dict) else None
        for k0, c in enumerate(allc):
            if c.get("grundlage"): vals.append(None); continue
            if k0 not in shown and not is_evidence(c): vals.append(None); continue
            if "formula" in c: vals.append(ctx.formula(c["formula"], name, r)); continue
            if c.get("formula_field") and isinstance(row, dict) and get(row, c["formula_field"], ""):   # a per-row formula template from the dataset (placeholders resolved here)
                vals.append(ctx.formula(str(get(row, c["formula_field"])), name, r)); continue
            if is_evidence(c) and c.get("field"):
                e = T.evidence(get(row, c["field"], None)); ents[col_key(c)] = e   # the Grundlage reads the raw entries
                vals.append(clip(j(list(dict.fromkeys(x for x in (cust(T, x, scope, name, r) for x in e) if x)) if edition == "customer" and k0 in shown else e, c.get("sep", "; ")))); continue
            v = cell_value(c, row)
            if c.get("text_by_key") and isinstance(row, dict) and tk: v = c["text_by_key"].get(str(get(row, tk, "")), v)
            if isinstance(v, str) and c.get("text_transform", not c.get("label")): v = T.text(v); texts.append(v); v = cust(T, v, scope, name, r) if edition == "customer" else v
            vals.append(clip(v))
        kind = {}; ids = [col_key(x) for x in allc]   # Grundlage kind per column (option blocks carry one Grundlage each)
        for k, c in enumerate(allc):
            if c.get("grundlage"):
                src = c.get("grundlage_from") or evid; e = []
                for s_ in src: e += ents.get(s_) or split_entries(vals[ids.index(s_)] if s_ in ids else "")
                tx = [vals[ids.index(s_)] for s_ in c["grundlage_text_from"] if s_ in ids and isinstance(vals[ids.index(s_)], str)] if c.get("grundlage_text_from") else texts
                keys = ([str(get(row, rk, ""))] if rk and isinstance(row, dict) else []) + [x for x in grundlage_keys({"columns": [c]}, row)]
                linked = list(dict.fromkeys(a for x in keys for a in prep.links.get(x, [])))
                vals[k], kind[k] = basis(e, tx, linked, BASIS_L, prep.valid_a, any(x in prep.client_links for x in keys), BASIS_L["src"], CELL_RE, prep.vendor_q, prep.dspec.get("handover_basis"), prep.dspec.get("grundlage_refs") is True, prep.client_a)
                dflt = get(row, c["grundlage_default_field"], "") if c.get("grundlage_default_field") and isinstance(row, dict) else ""   # a row that names its basis itself (an owner's input cell)
                if dflt and dflt not in str(vals[k] or ""): vals[k] = f"{dflt} + {vals[k]}" if vals[k] else dflt   # first, before what else it rests on (an assumption)
                nb += not vals[k]
        rows.append([vals[k] for k in shown]); kinds.append({shown.index(k): v for k, v in kind.items() if k in shown})
    specs = [{"header": fmt(c.get("header") or (CM["basis"]["header"] if c.get("grundlage") else "")), "width": c.get("width", 24 if c.get("grundlage") else 16), "tier": tier(c),
              "wrap": bool(c.get("wrap")), "group": c.get("group")} for c in cols]
    opts = [o["id"] for o in SPEC.get("_options") or []]; lab = {o["id"]: o["label"] for o in SPEC.get("_options") or []}
    band = [(a + 1, b + 1, lab.get(o, o), opts.index(o) if o in opts else 0) for a, b, o in option_blocks(cols)]
    if band:   # the band names the option: "Migration: Vorgehen" below the band "Migration" shows as "Vorgehen"
        for sp, c in zip(specs, cols):
            pre = f"{lab.get(c.get('_option'), '')}: "
            if c.get("_option") and sp["header"].startswith(pre): sp["header"] = sp["header"][len(pre):]
    end = X.table(ws, specs, rows, sh.get("table_name", name), header_row=hr, freeze=f"B{d0}", band=band or None, fit=sh.get("pages_wide"))
    tints = {o["label"]: X.band_of(k)["header"] for k, o in enumerate(SPEC.get("_options") or [])}
    for i, c in enumerate(cols, 1):   # `option_tint`: a cell naming an option carries that option's band tint
        if c.get("option_tint"):
            for rr in range(d0, end + 1):
                v = ws.cell(row=rr, column=i).value
                if v in tints: ws.cell(row=rr, column=i).fill = X.fill(tints[v])
    for i, c in enumerate(cols, 1):   # `input_field`: the cells of rows whose field is set are inputs (input fill) - e.g. a partner's estimate
        if c.get("input_field"):
            for rr, row in enumerate(data, d0):
                if isinstance(row, dict) and get(row, c["input_field"], ""): ws.cell(row=rr, column=i).fill = X.fill(X.tok("input_fill", "FFF7F5"))
    ignored = []; numeric = 0; dec = [c for c in cols if tier(c) == "decision"]
    if decision_budget(sh) is not None:
        bad = budget_errors(sh, [(c.get("_option"), fmt(c.get("header", ""))) for c in dec], int(X.tok("max_decision_columns", 2)))
        if bad: sys.exit(f"BUILD REJECTED: {where}/{name}: " + "; ".join(bad))
    elif len(dec) > int(X.tok("max_decision_columns", 2)): sys.exit(f"BUILD REJECTED: {where}/{name} declares {len(dec)} decision columns - at most {X.tok('max_decision_columns', 2)} per sheet")
    for i, c in enumerate(cols, 1):
        letter = get_column_letter(i); rng = f"{letter}{d0}:{letter}{end}"
        if c.get("number_format"):
            for rr in range(d0, end + 1): ws.cell(row=rr, column=i).number_format = c["number_format"]
        if c.get("validation"):
            toks = resolve_ref(c["validation"], P); dv = DataValidation(type="list", formula1='"' + ",".join(str(g(x, c.get("label_ctx"))) for x in toks) + '"'); ws.add_data_validation(dv); dv.add(rng)
        if tier(c) == "decision":
            for tok, key in status_map(c).items():
                pre = tok.endswith("*"); t0 = tok.rstrip("*"); val = ctx.formula(t0) if t0.startswith("{") else str(g(t0, c.get("label_ctx")))
                X.status_rule(ws, rng, f"{letter}{d0}", val, key, pre)
            if c.get("threshold_colors"):
                t = c["threshold_colors"]; ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=[str(t["below"])], fill=X.fill(X.status_colour("rebuild")))); ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThanOrEqual", formula=[str(t["below"])], fill=X.fill(X.status_colour("standard"))))
        elif c.get("colors") or c.get("status") or c.get("threshold_colors"): ignored.append(fmt(c.get("header", "")))
        if c.get("scale") or c.get("databar"):
            numeric += 1
            if numeric > 1: NOTES.append(f"{where}/{name}: numeric emphasis on '{fmt(c.get('header', ''))}' ignored (one per sheet)"); continue
            if c.get("scale"): X.scale_rule(ws, rng, c["scale"])
            else: X.databar(ws, rng)
        if c.get("grundlage"):
            for rr, kd in enumerate(kinds, d0):
                if kd.get(i - 1) == "assumption": ws.cell(row=rr, column=i).fill = X.fill(X.status_colour("assumption"))
    if ignored: NOTES.append(f"{where}/{name}: legacy colours ignored on {len(ignored)} non-decision column(s): {', '.join(ignored)}")
    if nb: NOTES.append(f"{where}/{name}: {nb} of {len(rows)} row(s) without Grundlage (no locator, [Qn] or A-nn in the row)")
    X.tab(ws, sh.get("tab", "internal" if review else "result"))
    return len(data)

def sheet_parameters(ws, sh, ctx):
    vals = [[p["name"], conf_value(p["value"], f"{sh['name']}/{p['name']}") if isinstance(p.get("value"), str) and p["value"].startswith("$") else p["value"], ctx.formula(p.get("meaning", ""))] for p in sh["rows"]]
    X.table(ws, [{"header": h, "width": w, "wrap": k == 2} for k, (h, w) in enumerate(zip(sh["headers"], [18, 10, 80]))], vals, sh["name"])
    for i, p in enumerate(sh["rows"], 2):   # a row with `validation` ("a,b,c" or a list) offers its values as a dropdown (e.g. a scenario selector)
        v = p.get("validation")
        if v:
            dv = DataValidation(type="list", formula1='"' + (v if isinstance(v, str) else ",".join(map(str, v))) + '"', allow_blank=False); ws.add_data_validation(dv); dv.add(f"B{i}")
    for t, hr, cols, rows, c0 in param_tables(sh):   # parameter tables ({pt:...}) below / beside the scalar rows
        if t.get("title"): ws.cell(row=hr - 1, column=c0, value=fmt(t["title"])).font = X.font(12, True, X.tok("accent", "FF4B4B"))
        if any(c.get("label") for c in cols): rows = [[g(v) if c.get("label") else v for c, v in zip(cols, r)] for r in rows]
        X.table(ws, [{"header": fmt(c.get("header", c["id"])), "width": c.get("width", 16)} for c in cols], rows, f"{sh['name']}_{t['id']}", header_row=hr, sub=True, first_col=c0)
        for i, c in enumerate(cols, c0):
            if c.get("number_format"):
                for rr in range(hr + 1, hr + 1 + len(rows)): ws.cell(row=rr, column=i).number_format = c["number_format"]
    if sh.get("tables_beside") and sh.get("tables"):   # the print width covers the tables beside, too
        n = ws.max_column; ws.column_dimensions[get_column_letter(len(sh["headers"]) + 1)].width = 3
        ws.page_setup.fitToWidth = X.pages_wide([ws.column_dimensions[get_column_letter(c)].width or 16 for c in range(1, n + 1)])
    X.tab(ws, sh.get("tab", "reference"))

def sheet_overview(ws, sh, D, ctx, blocks):
    ws["A1"] = fmt(sh.get("title", sh["name"])); ws["A1"].font = X.font(16, True); r = 3
    for blk in sh["blocks"]:
        if blk.get("title"): ws.cell(row=r, column=1, value=fmt(blk["title"])).font = X.font(12, True, X.tok("accent", "FF4B4B")); r += 1
        if blk["type"] == "matrix":
            heads = [blk["row_header"]] + [c["header"] for c in blk["columns"]]; nf = [None] + [c.get("number_format") for c in blk["columns"]]
            for c, h in enumerate(heads, 1): X.header(ws.cell(row=r, column=c, value=ctx.formula(h)))
            ws.row_dimensions[r].height = X.header_height([(ctx.formula(h), 44 if k == 0 else 18) for k, h in enumerate(heads)]); first = r + 1
            opts = (SPEC.get("_options") or []) if blk.get("rows_are") == "options" else None   # one row per option, {o.*} per row
            if opts is not None: toks = [o["id"] for o in opts]; rowvals = [o["label"] for o in opts]
            elif "row_tokens" in blk: toks = list(resolve_ref(blk["row_tokens"], P)); rowvals = [g(t, blk.get("label_ctx")) for t in toks]
            else:
                ds, fld = blk["row_values_from"].rsplit(".", 1); seen = []   # rsplit: a generic dataset is named <kind>.<table>
                for x in DATASETS[ds](D):
                    v = get(x, fld)
                    if v not in seen and v not in ("", None): seen.append(v)
                rowvals = seen; toks = seen
            for i, rv in enumerate(rowvals):
                rr = first + i; X.body(ws.cell(row=rr, column=1, value=rv))
                if opts: ws.cell(row=rr, column=1).fill = X.fill(X.band_of(i)["header"])   # the option's band tint, as on its table blocks
                for c, col in enumerate(blk["columns"], 2):
                    X.body(ws.cell(row=rr, column=c, value=ctx.formula(subst_option(col["formula"], opts[i]) if opts else col["formula"], None, rr)))
                    if nf[c - 1]: ws.cell(row=rr, column=c).number_format = nf[c - 1]
            r = first + len(rowvals)
            if blk.get("total", True):
                ws.cell(row=r, column=1, value=fmt(blk.get("total_label", "Total"))).font = X.font(10, True)
                for c in range(2, len(heads) + 1):
                    ws.cell(row=r, column=c, value=fmt(L["not_assessed"]) if ctx.is_na(blk["columns"][c - 2]["formula"]) else f"=SUM({get_column_letter(c)}{first}:{get_column_letter(c)}{r - 1})").font = X.font(10, True)
                    if nf[c - 1]: ws.cell(row=r, column=c).number_format = nf[c - 1]
                for c in range(1, len(heads) + 1): ws.cell(row=r, column=c).border = Border(top=Side(style="thin", color=X.tok("text", "100C2A")))
                r += 1
            ch = blk.get("chart", {"column": 1}); ch = {} if ch is True else ch
            info = {"ws": ws, "first": first, "last": first + len(rowvals) - 1, "heads": [ctx.formula(h) for h in heads], "tokens": toks, "labels": rowvals, "chart": ch or {},
                    "formats": nf, "colours": [X.band_of(i)["band"] for i in range(len(rowvals))] if opts else None}
            if blk.get("id"): blocks[blk["id"]] = info
            if ch is not False and rowvals and not all(ctx.is_na(c["formula"]) for c in blk["columns"]):   # CP-16: chart over formula cells -> stays formula-driven
                title = fmt(ctx.formula(str(ch.get("title") or blk.get("title") or blk.get("row_header") or heads[1])))
                ws.add_chart(block_chart(info, ch, title), f"{get_column_letter(len(heads) + 2)}{max(3, first - 1)}")
                r = max(r, max(3, first - 1) + 16)
            r += 1
        elif blk["type"] == "kv":
            for kv in blk["rows"]: X.body(ws.cell(row=r, column=1, value=ctx.formula(kv["label"]))); X.body(ws.cell(row=r, column=2, value=ctx.formula(kv["formula"]))); r += 1
            r += 1
    ws.column_dimensions["A"].width = 44
    for c in range(2, 12): ws.column_dimensions[get_column_letter(c)].width = 18
    X.finish(ws, sh.get("tab", "result"), grid=False, pages_wide=X.pages_wide([ws.column_dimensions[get_column_letter(c)].width or 16 for c in range(1, ws.max_column + 1)]))   # a wide matrix prints on more pages (the hygiene rule)

def point_colours(status, tokens, labels_):
    st = status or {}; return [X.status_colour(st.get(t) or st.get(l), "chart") if (st.get(t) or st.get(l)) else None for t, l in zip(tokens, labels_)]

def block_chart(info, ch, title):
    kind = ch.get("type", "pie"); ws = info["ws"]; cats = (1, info["first"], info["last"])
    if kind == "stacked":
        cols = ch.get("columns") or list(range(1, len(info["heads"])))
        series = [(k + 1, info["heads"][k]) for k in cols]; st = ch.get("status") or {}
        return X.chart(kind, ws, cats, series, title, series_colours=[X.status_colour(st[info["heads"][k]], "chart") if st.get(info["heads"][k]) else None for k in cols])
    k = int(ch.get("column", 1)); pc = point_colours(ch.get("status"), info["tokens"], info["labels"])
    if not any(pc) and info.get("colours"): pc = info["colours"]   # one bar per option in its band colour
    return X.chart(kind, ws, cats, [(k + 1, info["heads"][k])], title, pc, label_format=(info.get("formats") or [None] * (k + 1))[k])

def client_sources(dspec):
    """Sources in client language: `sources_client` or the method's `sources` with internal paths reduced to their description."""
    if dspec.get("sources_client"): return fmt(dspec["sources_client"])
    path = r"(?:@project/)?[\w.<>{}*-]+(?:/[\w.<>{}*-]+)+"
    s = re.sub(path + r"\s*\(([^)]*)\)", r"\1", fmt(dspec.get("sources", "")))
    s = re.sub(path, "", s); s = re.sub(r"\b[\w-]+\.(?:json|md|py|jsonl)\b", "", s)
    return re.sub(r"\s*,\s*(,\s*)+", ", ", s).strip(" ,;")

def sheet_readme(ws, key, dspec, wb, edition, engine, has_basis):
    C = CM["readme"]; ws["A1"] = fmt(dspec["title"]); ws["A1"].font = X.font(16, True)
    ws["A2"] = fmt(C["subtitle"]); ws["A2"].font = X.font(10, True, X.tok("accent", "FF4B4B"))
    names = {"sources_sheet": engine.get("sources", ""), "assumptions_sheet": engine.get("assumptions", ""), "claims_sheet": ", ".join(engine.get("claims", [])), "questions_sheet": engine.get("open_questions", "")}
    if has_basis:
        parts = [C.get("basis_handover") if dspec.get("handover_basis") and dspec.get("code_locators") is False and C.get("basis_handover") else C["basis_code"]] + ([C["basis_vendor"]] if engine.get("sources") else []) + ([C["basis_assumption"]] if engine.get("assumptions") else []) + ([C["basis_client"]] if engine.get("client_fact") and C.get("basis_client") else [])
        basis_t = C["basis_intro"] + " " + "; ".join(parts) + "."
    else: basis_t = C["evidence_text"]
    gl = " ".join([clean_glossary(fmt(C["glossary_text"]), wb.sheetnames)] + ([C["glossary_sources"]] if engine.get("sources") else []) + ([C["glossary_assumptions"]] if engine.get("assumptions") else []))
    items = [(C["purpose"], fmt(dspec["purpose"])), (C["created"], time.strftime("%Y-%m-%d")), (C["basis"], basis_t), (C["sources"], client_sources(dspec)), (C["aggregates"], C["aggregates_text"]), (C["glossary"], gl)]
    if dspec.get("extra"): items.append((C["notes"], fmt(dspec["extra"])))
    if edition != "customer" and engine.get("claims"): items.append((C["claims_row"], C["claims_text"]))
    if edition != "customer" and engine.get("open_questions"): items.append((C["questions_row"], C["questions_text"]))
    for i, (k, v) in enumerate(items, 4):
        a = ws.cell(row=i, column=1, value=k); a.font = X.font(10, True); a.alignment = Alignment(vertical="top"); c = ws.cell(row=i, column=2, value=fmt(v, threshold=P["scoring"]["pass_threshold"], **names)); X.body(c, wrap=True)
        ws.row_dimensions[i].height = X.LINE_PT * X.lines(c.value, 100)
    r = 4 + len(items) + 1; X.header(ws.cell(row=r, column=1, value=C["sheet"])); X.header(ws.cell(row=r, column=2, value=C["content"])); ws.row_dimensions[r].height = 20
    texts = {s["name"]: fmt(s.get("readme", "")) for s in dspec["sheets"]}
    for n in dspec.get("not_assessed") or []: texts[n] = fmt(L["not_assessed_sheet"]).replace("{text}", texts.get(n, "")).strip()
    texts.update({engine[k]: C["sheet_texts"].get(k, "") for k in ("assumptions", "sources", "open_questions") if engine.get(k)})
    for n in engine.get("claims", []): texts[n] = texts.get(n) or C["sheet_texts"].get("claims", "")
    for i, n in enumerate([x for x in wb.sheetnames if x != ws.title], r + 1):
        X.body(ws.cell(row=i, column=1, value=n)); X.body(ws.cell(row=i, column=2, value=texts.get(n, "")), wrap=True)
        ws.row_dimensions[i].height = X.LINE_PT * X.lines(texts.get(n, ""), 100)   # explicit: an auto-fitted wrapped row defeats fit-to-width
    ws.column_dimensions["A"].width = 26; ws.column_dimensions["B"].width = 100   # fits a landscape page unscaled (Excel stops scaling a sheet with very tall rows)
    X.finish(ws, dspec_tab(ws.title, dspec, "reference"), landscape=True, grid=False)

PROCESS_RE = re.compile(r"\bSA (?:Kunde|Plattform)\b|\b(?:Client|Platform) SA\b|\bPrüfer(?:in|innen|n|s)?\b|\breviewers?\b|\bPS-7|\bC-[\w-]*(?:nnn|\d{3})\b|\bQ-[\w-]+\b"
                        r"|\bKonfidenz(?:en)?\b|\bconfidence\b|\bKorrektur(?:en)?\b|\bkorrigiert(?:e|en|er|es)?\b|\boffener Fragen\b|\bopen questions\b|(?:analysis|state|work|tools)/|\bAussage-ID\b", re.I)   # whole words: 'Prüfergebnis', 'Korrekturvorschlag' are content

def clean_glossary(text, sheets):
    """Customer glossary = subject terms only: an entry ('Term = …' plus its follow-up sentences) that explains process vocabulary
    (reviewer roles, claim / reference / question ids, confidence, internal paths) or names a sheet the workbook lacks is dropped."""
    entries = []
    for s in re.split(r"(?<=[.!?])\s+(?=\S)", text or ""):
        if " = " in s or not entries: entries.append(s)
        else: entries[-1] += " " + s
    lacking = [x for t in re.findall(r"Blatt\s+[„\"“]?([A-Za-z_]+)|sheet\s+[“\"]?([A-Za-z_]+)", text or "") for x in t if x and x not in sheets]
    return " ".join(e for e in entries if not PROCESS_RE.search(e) and not any(re.search(rf"\b{re.escape(n)}\b", e) for n in lacking))

def dspec_tab(name, dspec, default): return next((s.get("tab") for s in dspec["sheets"] if s["name"] == name and s.get("tab")), default)

# ---- Management summary: title band, basis line, tiles, rendered Markdown with live {kpi:id}, top assumptions, KPI table, charts
def plain(t):
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), t); t = re.sub(r"(?<![\w*])\*(\S[^*]*?)\*(?![\w*])", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t); return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)

def md_items(txt):
    items, para = [], []
    def flush():
        if para: items.append(("p", " ".join(para))); para.clear()
    for line in txt.splitlines():
        s = line.strip()
        if not s: flush(); continue
        m = re.match(r"^(#{1,6})\s+(.*)", s)
        if m: flush(); items.append(("h", m.group(2).strip("# "))); continue
        m = re.match(r"^(\d+)[.)]\s+(.*)", s) or re.match(r"^([-*•])\s+(.*)", s)
        if m: flush(); items.append(("li", (f"{m.group(1)}. " if m.group(1).isdigit() else "• ") + m.group(2))); continue
        if s.startswith("|"):
            if not re.match(r"^\|[\s:|-]+\|?$", s): flush(); items.append(("li", " · ".join(c.strip() for c in s.strip("|").split("|"))))
            continue
        para.append(s)
    flush()
    return [(k, plain(t)) for k, t in items]

def kpi_formula(text, ctx, kfmt):
    """'… {kpi:x} …' -> ="…"&$D$n&"…" (string literals <= 250 chars: Excel's per-literal limit is 255). A KPI with
    `text_decimals: n` reads FIXED(ref, n) - separators in the reader's locale (TEXT's format code is locale-bound)."""
    parts = []
    for i, seg in enumerate(KPI_RE.split(text)):
        if i % 2:
            ref = ctx.kpi.get(seg, '"?"'); f = kfmt.get(seg)
            parts.append(f"FIXED({ref},{f[1]})" if isinstance(f, tuple) else f'TEXT({ref},"{f}")' if f else ref)
        else: parts += ['"' + seg[k:k + 250].replace('"', '""') + '"' for k in range(0, len(seg), 250)] if seg else []
    return "=" + "&".join(parts)

def sheet_mgmt(ws, key, dspec, sh, ctx, items, top, blocks, edition="customer"):
    C = CM["mgmt"]; charts = sh.get("charts") or []; tiles = (sh.get("tiles") or [])[:5]
    kpis = [k for k in sh.get("kpis", []) if edition != "customer" or k.get("edition") != "full"]   # `edition: full`: a check, not for the client
    for col, w in zip("ABCDEFG", (2, 18, 18, 18, 18, 18, 3)): ws.column_dimensions[col].width = w
    for c in range(8, 16): ws.column_dimensions[get_column_letter(c)].width = 11
    band = "O" if charts else "F"
    ws.merge_cells(f"B2:{band}2"); c = ws["B2"]; c.value = fmt(dspec["title"]); c.font = X.font(18, True, "FFFFFF"); c.fill = X.fill(X.tok("title_band", "100C2A")); c.alignment = Alignment(vertical="center", indent=1); ws.row_dimensions[2].height = 36
    ws.merge_cells(f"B3:{band}3"); c = ws["B3"]; c.value = fmt(C.get("basis_line", ""), key=key, date=time.strftime("%d.%m.%Y" if LANG == "de" else "%Y-%m-%d")); c.font = X.font(9, color=X.tok("muted", "6B6880"))
    r_text = 7 if tiles else 5   # order: title band, basis line, tiles (rows 4-5), summary text, key assumptions, KPI table + charts
    r_top = r_text + len(items) + (1 if items else 0)
    r_kpi = r_top + (len(top) + 2 if top else 0)
    kfmt = {}
    for i, k in enumerate(kpis):
        if k.get("id"): ctx.kpi[k["id"]] = f"$D${r_kpi + 2 + i}"; kfmt[k["id"]] = ("fixed", k["text_decimals"]) if "text_decimals" in k else k.get("number_format")
    for k, t in enumerate(tiles):   # tiles: large live numbers in the status tint
        col = "BCDEF"[k]; st = X.fill(X.status_colour(t.get("status") or "neutral")); kp = next((x for x in kpis if x.get("id") == t.get("kpi")), {})
        v = ws[f"{col}4"]; v.value = "=" + ctx.kpi.get(t.get("kpi"), '""'); v.font = X.font(24, True); v.alignment = Alignment(horizontal="center", vertical="center"); v.fill = st
        if kp.get("number_format"): v.number_format = kp["number_format"]
        lb = ws[f"{col}5"]; lb.value = ctx.formula(t.get("label") or kp.get("label", "")); lb.font = X.font(9); lb.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True); lb.fill = st
    if tiles: ws.row_dimensions[4].height = 40; ws.row_dimensions[5].height = 30
    for i, (kind, text) in enumerate(items):
        rr = r_text + i; ws.merge_cells(f"B{rr}:F{rr}"); c = ws[f"B{rr}"]
        c.value = kpi_formula(text, ctx, kfmt) if KPI_RE.search(text) else text
        if kind == "h": c.font = X.font(12, True, X.tok("accent", "FF4B4B")); ws.row_dimensions[rr].height = 22
        else:
            c.font = X.font(10); c.alignment = Alignment(wrap_text=True, vertical="top", indent=1 if kind == "li" else 0)
            ws.row_dimensions[rr].height = X.LINE_PT * X.lines(KPI_RE.sub("0000", text), 88) + 4
    if top:
        ws.merge_cells(f"B{r_top}:F{r_top}"); c = ws[f"B{r_top}"]; c.value = fmt(C.get("assumptions_heading", ""), assumptions_sheet=engine_name("assumptions", dspec)); c.font = X.font(12, True, X.tok("accent", "FF4B4B"))
        for i, a in enumerate(top, 1):
            rr = r_top + i; ws.merge_cells(f"B{rr}:F{rr}"); c = ws[f"B{rr}"]; c.value = f"{a['id']}  {a['text']}"; c.font = X.font(10); c.alignment = Alignment(wrap_text=True, vertical="top")
            c.fill = X.fill(X.status_colour("assumption")); ws.row_dimensions[rr].height = X.LINE_PT * X.lines(c.value, 88) + 2
    ws.merge_cells(f"B{r_kpi}:F{r_kpi}"); ws[f"B{r_kpi}"] = C.get("kpi_heading", ""); ws[f"B{r_kpi}"].font = X.font(12, True, X.tok("accent", "FF4B4B"))
    h = r_kpi + 1
    for col, v in (("B", C["kpi"]), ("C", None), ("D", C["value"]), ("E", C["note"]), ("F", None)): X.header(ws[f"{col}{h}"]); ws[f"{col}{h}"].value = v
    ws.merge_cells(f"B{h}:C{h}"); ws.merge_cells(f"E{h}:F{h}")
    for i, k in enumerate(kpis):
        rr = h + 1 + i
        a = ws[f"B{rr}"]; a.value = ctx.formula(k["label"]); X.body(a, wrap=True); a.font = X.font(10, True)
        v = ws[f"D{rr}"]; v.value = ctx.formula(k["formula"]); X.body(v); v.alignment = Alignment(horizontal="right", vertical="top")
        if k.get("number_format"): v.number_format = k["number_format"]
        n = ws[f"E{rr}"]; n.value = fmt(ctx.formula(k.get("note", ""))); X.body(n, wrap=True)
        for col in ("C", "F"): ws[f"{col}{rr}"].border = X.sep()
        ws.merge_cells(f"B{rr}:C{rr}"); ws.merge_cells(f"E{rr}:F{rr}")
        ws.row_dimensions[rr].height = X.row_height(max(X.lines(a.value, 36), X.lines(n.value, 36)))
    # charts: right of the tiles / summary text from the tiles row (page 1, as FORMAT-MUSTER), stacked by real row heights;
    # below the KPI table instead when the side-by-side page would print under 60 % (the summary text is never shrunk further)
    side = X.pages_wide([ws.column_dimensions[get_column_letter(c)].width or 10 for c in range(1, 16)]) == 1
    col = "H" if side else "B"; anchor = (4 if tiles else 5) if side else h + len(kpis) + 2; last = h + len(kpis); helper = 17
    kpi_rows = {k["id"]: h + 1 + i for i, k in enumerate(kpis) if k.get("id")}
    for ch in charts:
        kind = ch.get("type", "bar"); title = fmt(ctx.formula(ch.get("title", "")))
        if ch.get("block") in blocks: chart = block_chart(blocks[ch["block"]], dict(blocks[ch["block"]]["chart"], **{k: v for k, v in ch.items() if k not in ("block", "type")}, type=kind), title)
        else:
            ids = [x for x in ch.get("kpis", []) if x in ctx.kpi]
            if not ids: continue
            rows_ = [kpi_rows[x] for x in ids]
            if rows_ == list(range(rows_[0], rows_[0] + len(rows_))):   # consecutive KPI rows: the chart reads the KPI table itself
                chart = X.chart(kind, ws, (2, rows_[0], rows_[-1]), [(4, title)], title, point_colours(ch.get("status"), ids, ids), height=7.5, width=15)
            else:   # otherwise a small helper block right of the print area (visible, not hidden - Excel plots no hidden cells)
                for i, kid in enumerate(ids):
                    for cc, v in ((helper, f"=B{kpi_rows[kid]}"), (helper + 1, "=" + ctx.kpi[kid])): ws.cell(row=h + 1 + i, column=cc, value=v).font = X.font(8, color=X.tok("muted", "6B6880"))
                chart = X.chart(kind, ws, (helper, h + 1, h + len(ids)), [(helper + 1, title)], title, point_colours(ch.get("status"), ids, ids), height=7.5, width=15); helper += 3
        chart.width = 15; ws.add_chart(chart, f"{col}{anchor}")
        need, r = chart.height / 2.54 * 72 + 12, anchor   # next chart below this one: walk the real row heights (cm -> pt)
        while need > 0: need -= ws.row_dimensions[r].height or 15; r += 1
        anchor = r; last = max(last, r)
    X.finish(ws, sh.get("tab", "result"), grid=False)
    ws.print_area = f"A1:{'O' if charts and side else 'F'}{last}"

# ---- engine sheets: Annahmen (§5), Quellen (§6), Offene_Fragen, claims
def workbook_assumptions(prep, T, key):
    """The assumptions this workbook shows: those cited in its rows or affecting one of its row keys (matched, sorted by affected
    rows desc, then number), followed by every assumption whose `affects` match rows in NO workbook - a global premise such as
    the production platform never vanishes; it appears in every workbook (sorted by number)."""
    out = []
    for a in prep.assumptions:
        matched = a["id"] in T.cited_a or bool(set(a["affected"]) & prep.keys)
        if matched or not set(a["affected"]) & prep.known: out.append((0 if matched else 1, a))
    return [a for _, a in sorted(out, key=lambda x: (x[0], -len(x[1]["affected"]) if not x[0] else 0, int(x[1]["id"][2:])))]

def shown_key(k):
    """a composite row key FR-041[@<position>]@<option id> reads 'FR-041 (<option label>)' for the client; a key a dataset labels
    (`grundlage_key_labels`) reads its label; other keys stay as they are"""
    if k in KEY_LABELS: return KEY_LABELS[k]
    lab = {o["id"]: o["label"] for o in SPEC.get("_options") or []}; base, _, rest = str(k).partition("@"); oid = rest.split("@")[-1] if rest else ""
    return f"{base} ({lab[oid]})" if oid in lab and len(lab) > 1 else (base if oid in lab else str(k))

def sheet_assumptions(ws, rows, T):
    A = CM["assumptions"]; hd = [fmt(h) for h in A["headers"]]
    vals = []
    for a in rows:
        aff = ", ".join(shown_key(k) for k in a["affected"]); why, ifn = why_text(a["q"]), if_not_text(a["q"], aff)
        v = [a["id"]] + [cust(T, T.text(x), None, "Annahmen", a["id"]) for x in (a["wording"], why, ifn)] + [aff, None, None]
        for i in (2, 3):   # never the same text twice in one row (the hygiene lint flags the empty cell instead)
            if v[i] and any(norm_txt(v[i]) == norm_txt(v[k]) for k in (1, 2, 3, 4) if k != i and (k < i or k == 4)): v[i] = ""
        vals.append(v)
    cols = [{"header": hd[0], "width": 8}, {"header": hd[1], "width": 55, "wrap": True}, {"header": hd[2], "width": 45, "wrap": True}, {"header": hd[3], "width": 45, "wrap": True},
            {"header": hd[4], "width": 22, "wrap": True}, {"header": hd[5], "width": 16, "tier": "decision"}, {"header": hd[6], "width": 34, "tier": "decision", "wrap": True}]
    end = X.table(ws, cols, vals, "Assumptions")
    dv = DataValidation(type="list", formula1='"' + ",".join(A["options"]) + '"', allow_blank=True, showInputMessage=True, promptTitle=hd[5][:32], prompt=" / ".join(A["options"])); ws.add_data_validation(dv); dv.add(f"F2:F{end}")
    dv2 = DataValidation(type="textLength", operator="lessThanOrEqual", formula1="2000", allow_blank=True, showInputMessage=True, promptTitle=hd[6][:32], prompt=A.get("comment_prompt", "")); ws.add_data_validation(dv2); dv2.add(f"G2:G{end}")
    for rr in range(2, end + 1):
        for col in "FG": ws[f"{col}{rr}"].fill = X.fill(X.tok("input_fill", "FFF7F5"))
    X.tab(ws, "assumptions")

def reference_rows():
    """PS-7 rows by number + the German titles sidecar (reference/platform-standard.titles.<lang>.json)."""
    try:
        import reference as REFM
        rows = {int(c[0][5:]): c for _, c0 in REFM.load()[4] for c in [REFM.norm(c0)] if re.fullmatch(r"PS-7-\d+", c[0])}
    except (SystemExit, OSError, ValueError, IndexError): rows = {}
    side = load_json(os.path.join(REF_DIR, f"platform-standard.titles.{LANG}.json"), {}) or {}
    return rows, side

def sheet_sources(ws, cited, where, cfree=False):
    S_ = CM["sources"]; rows, side = reference_rows(); vals = []; missing = 0
    for n in sorted(cited):
        c = rows.get(n); pid = f"PS-7-{n:03d}"; t = side.get(pid) or {}
        if not c: vals.append([f"[Q{n}]", "", S_.get("missing", ""), "", "", ""]); missing += 1; continue
        fact = re.sub(r"\s+", " ", re.sub(r"\[superseded[^\]]*\]|\([^()]*\)", "", c[1])).strip(); head = re.split(r"(?<=[.!?:])\s", fact)[0][:160]
        if not t.get("title"): missing += 1   # fallback: the English fact head without remarks (hygiene error in the customer edition)
        vals.append([f"[Q{n}]", t.get("title") or head, t.get("summary", ""), t.get("applies") or c[2], vendor_address(c[3]) if cfree else c[3], c[4]])
    cols = [{"header": S_["headers"][0], "width": 8}, {"header": S_["headers"][1], "width": 45, "wrap": True}, {"header": S_["headers"][2], "width": 70, "wrap": True},
            {"header": S_["headers"][3], "width": 22, "wrap": True}, {"header": S_["headers"][4], "width": 40, "tier": "support"}, {"header": S_["headers"][5], "width": 12, "tier": "support"}]
    X.table(ws, cols, vals, "Sources")
    for rr, v in enumerate(vals, 2):
        if str(v[4]).startswith("http"): ws.cell(row=rr, column=5).hyperlink = v[4]
    X.tab(ws, "reference")
    if missing: NOTES.append(f"{where}/{ws.title}: {missing} of {len(vals)} source(s) without a {LANG} title (sidecar reference/platform-standard.titles.{LANG}.json; `dbcx reference title`) - English fact head shown")

def self_lint(strings, where):
    """Wording the BUILDER composes (labels, fixed column values, headers) is linted before the workbook exists. A hit here
    is a defect in labels.*.json or build_excel.py, never in the analysis files - the rejection says so, instead of sending
    the reader to a post-pass of the analyses."""
    import lint_deliverable as LD
    ml = METHOD.get("lint", {}); lint = P.get("lint", {})
    forb, allow = LD.rules({"lint": {"forbidden_terms": lint.get("forbidden_terms", []) + ml.get("forbidden_terms", []), "allow_terms": lint.get("allow_terms", []) + ml.get("allow_terms", [])}})
    hits = [(t, x) for x in sorted({x for x in strings if isinstance(x, str) and x}) for t, _ in LD.hits_in(x, forb, allow)]
    if hits and "--allow-process-language" not in sys.argv:
        sys.exit(f"BUILD REJECTED before writing: process language in text the BUILDER composed for {where}: " + "; ".join(f"[{t}] {x!r}" for t, x in hits[:6]) + ". Fix the label (engine/spec/labels.*.json, the method's labels or build_excel.py) - the analysis files are not the cause.")

def sheet_open_questions(ws, D):
    C = CM.get("open_questions", {}); hd = list(C["headers"]); hd.insert(5, C.get("answer_type_header", "Answer type"))
    self_lint(hd + [q["raised_by"] for q in D["client_questions"]] + [q["status"] for q in D["client_questions"]] + [q["answer_type"] for q in D["client_questions"]], f"{ws.title} headers, 'Raised by', 'Status' and answer type")
    rows = [[q["id"], q["question"], q["effect"], q["raised_by"], q["status"], q["answer_type"], q["answer"]] for q in D["client_questions"]]
    X.table(ws, [{"header": h, "width": w, "wrap": k in (1, 2, 6)} for k, (h, w) in enumerate(zip(hd, [16, 70, 50, 18, 14, 16, 50]))], rows, "OpenQuestions"); X.tab(ws, "internal")

def claim_critics_of(scope):
    """{claim id: critic ids that score it} from the gauntlet register (per-pack standard critics only; else empty = every critic)"""
    reg = load_json(os.path.join(ROOT, "analysis", "gauntlet", scope, "claims.json"), {}) or {}
    return {c["id"]: c["critics"] for c in reg.get("claims", []) if c.get("id") and c.get("critics")}

def sheet_claims(ws, sh, D, cfree=False):
    import conflicts
    C = CM["claims"]; crit = P["scoring"]["critics"]; rows = []; na = L.get("critic_not_applicable", "n/a"); used = set()
    det, cfr = L.get("critic_deterministic", "deterministic"), L.get("critic_conflict_resolution", "conflict resolution (quote checked)")
    for scope, claims in claim_scopes(D, sh["scopes"]):
        sc, rnd = latest_scores(scope); app = claim_critics_of(scope); own = scope_critics(scope, P)   # a scope without that critic shows n/a
        res = conflicts.resolved_claims(scope)
        for c in claims:
            s = sc.get(c["id"], {}); lab = det if not own else cfr if not s and c["id"] in res else None   # no critic by design (lean inventory: CHECK + quotes + locators) / a conflict resolution added after the scope's gauntlet
            if lab: used.add(lab)
            ev = code_free(c.get("evidence") or []) if cfree else c.get("evidence")
            rows.append([scope, c["id"], g(c["type"]), c.get("target", ""), c["statement"], j(ev)] + [lab or (s.get(cr) if cr in app.get(c["id"], own) else na) for cr in crit] + [None])
    heads = [C["scope"], C["id"], C["type"], C["target"], C["statement"], C["evidence"]] + [fmt(C["score"], critic=critic(cr)) for cr in crit] + [C["avg"]]
    n = len(crit); first = get_column_letter(7); last = get_column_letter(6 + n); avg_col = 7 + n
    end = X.table(ws, [{"header": h, "width": w, "wrap": k in (4, 5)} for k, (h, w) in enumerate(zip(heads, [18, 16, 10, 22, 80, 50] + [10] * n + [10]))], rows, "Claims")
    for r in range(2, end + 1): X.body(ws.cell(row=r, column=avg_col, value=f'=IF(COUNT({first}{r}:{last}{r})=0,"",AVERAGE({first}{r}:{last}{r}))'))
    T_ = P["scoring"]["pass_threshold"]; rng = f"{first}2:{get_column_letter(avg_col)}{end}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=[str(T_)], fill=X.fill(X.status_colour("rebuild")))); ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThanOrEqual", formula=[str(T_)], fill=X.fill(X.status_colour("standard"))))
    stats = [(C["n_claims"], f"=COUNTA(B2:B{MAXR})")] + [(fmt(C["avg_critic"], critic=critic(cr)), f'=IFERROR(AVERAGE({get_column_letter(7 + i)}2:{get_column_letter(7 + i)}{MAXR}),"")') for i, cr in enumerate(crit)] + [(fmt(C["below"], threshold=T_), "+".join(f'COUNTIF({get_column_letter(7 + i)}2:{get_column_letter(7 + i)}{MAXR},"<{T_}")' for i in range(n)).join(["=", ""])), (C["unscored"], f"=COUNTA(B2:B{MAXR})-COUNT({first}2:{first}{MAXR})" + "".join(f'-COUNTIF({first}2:{first}{MAXR},"{x}")' for x in sorted(used)))]
    sc_col = 9 + n
    for r, (lab, f) in enumerate(stats, 1): ws.cell(row=r, column=sc_col, value=lab).font = X.font(10, True); ws.cell(row=r, column=sc_col + 1, value=f).font = X.font(10)
    ws.column_dimensions[get_column_letter(sc_col)].width = 28; X.tab(ws, sh.get("tab", "internal"))

def internal_notes(D, key, dspec, prep):
    """work/internal/<D>_Review_Notes.xlsx: the critics' notes per claim + full copies of the table sheets INCLUDING `internal`
    columns (formula vs judgement, K7) - for the team, never for the client."""
    crit = P["scoring"]["critics"]; sh = next((x for x in dspec["sheets"] if x["type"] == "claims"), None)
    has_int = any(is_internal(c) for s in dspec["sheets"] if s["type"] == "table" for c in s["columns"])
    if not sh and not has_int: return
    wb = Workbook(); wb.remove(wb.active)
    if sh:
        ws = wb.create_sheet("Review_Notes"); rows = []
        for scope, claims in claim_scopes(D, sh["scopes"]):
            sc, rnd = latest_scores(scope)
            for c in claims:
                s = sc.get(c["id"], {}); rows.append([scope, c["id"], c["statement"], rnd if s else None] + [s.get(cr) for cr in crit] + [s.get(cr + "_issue", "") for cr in crit] + [c.get("history", "") or "", c.get("supersedes", "") or ""])
        heads = ["scope", "claim", "statement", "last round"] + [f"score {critic(cr)}" for cr in crit] + [f"note {critic(cr)}" for cr in crit] + ["history (internal)", "supersedes"]
        widths = [18, 16, 70, 8] + [8] * len(crit) + [50] * len(crit) + [50, 14]; wraps = {2} | set(range(4 + len(crit), 5 + 2 * len(crit)))
        X.table(ws, [{"header": h, "width": w, "wrap": k in wraps} for k, (h, w) in enumerate(zip(heads, widths))], rows, "ReviewNotes"); X.tab(ws, "internal")
    ctx = Ctx(dspec, review=True); ctx.extra.update(prep.extra); T = transformer(prep)
    for s in dspec["sheets"]:
        if s["type"] == "parameters": sheet_parameters(wb.create_sheet(s["name"]), s, ctx)
    for s in dspec["sheets"]:
        if s["type"] == "table": sheet_table(wb.create_sheet(s["name"]), s, ctx, T, prep, f"{key}/review", review=True)
    out_dir = os.path.join(WORK_DIR, "internal"); os.makedirs(out_dir, exist_ok=True); out = os.path.join(out_dir, P["deliverables"][key]["file"].replace(".xlsx", "_Review_Notes.xlsx")); wb.save(out); print(f"internal: {relp(out, ROOT)}")

def interim_banner(wb, key, D):
    st = D["status"]; sc = st.get("scopes", {}); fin = sorted(u for u, v in sc.items() if v.get("status") in ("final", "passed", "passed-rework-ordered")); allu = sorted(u for u, v in sc.items() if v.get("status") != "skipped")
    ws = wb.create_sheet("INTERIM", 0); ws["A1"] = f"INTERIM {key} - {time.strftime('%Y-%m-%d %H:%M')} - NOT A DELIVERABLE (team checkpoint)"; ws["A1"].font = X.font(16, True, X.tok("accent", "FF4B4B"))
    cons = ", ".join(f"{k} {st.get('phases', {}).get(ph['id'], {}).get('status')}" for ph in METHOD["phases"] if ph["type"] == "gauntlet" for k in [ph["scope"]])
    lines = [f"Built from scopes that passed their review at this moment: {len(fin)} of {len(allu)} scopes final ({', '.join(fin) or '-'}).", f"Still open: {', '.join(u for u in allu if u not in fin) or '-'}.",
             f"Gauntlet scopes: {cons}. Figures change until the final build; wording has not passed the gate."]
    for i, l in enumerate(lines, 3): c = ws.cell(row=i, column=1, value=l); c.font = X.font(10); c.alignment = Alignment(wrap_text=True)
    ws.column_dimensions["A"].width = 140; X.tab(ws, "internal")

# ------------------------------------------------------------------ one edition of one deliverable
def write_edition(key, dspec, D, prep, edition):
    wb = Workbook(); wb.remove(wb.active); ctx = Ctx(dspec, edition=edition); ctx.extra.update(prep.extra); T = transformer(prep); where = f"{key}"
    if edition == "customer": T.set_customer(prep.as_ids, BASIS_L, prep.dspec.get("handover_basis"))
    sheets = [s for s in dspec["sheets"] if edition != "customer" or edition_of(s) != "full"]
    front = [s for s in sheets if edition_of(s) != "full"]; back = [s for s in sheets if edition_of(s) == "full"]
    deferred, blocks, engine = [], {}, {"claims": [s["name"] for s in sheets if s["type"] == "claims"]}
    sp = os.path.join(ROOT, "analysis", "summaries", f"{key}.md")
    if not os.path.exists(sp): NOTES.append(f"{key}: management summary text missing ({relp(sp, ROOT)})")
    items = [(k, cust(T, T.text(t), None, "Summary", k)) for k, t in md_items(open(sp, encoding="utf-8").read())] if os.path.exists(sp) else [("p", CM["mgmt"]["missing"])]
    for sh in front + back:
        ws = wb.create_sheet(sh["name"]); t = sh["type"]
        if t in ("mgmt", "readme"): deferred.append((sh, ws))
        elif t == "table": sheet_table(ws, sh, ctx, T, prep, where, edition=edition)
        elif t == "overview": sheet_overview(ws, sh, D, ctx, blocks)
        elif t == "parameters": sheet_parameters(ws, sh, ctx)
        elif t == "claims": sheet_claims(ws, sh, D, dspec.get("code_locators") is False)
        if sh is (front or [None])[-1]:   # engine sheets follow the result sheets
            ass = workbook_assumptions(prep, T, key) if dspec.get("assumptions", True) else []
            if ass:
                engine["assumptions"] = engine_name("assumptions", dspec); sheet_assumptions(wb.create_sheet(engine["assumptions"]), ass, T)
                un = [a["id"] for a in ass if not set(a["affected"]) & prep.known and a["id"] not in T.cited_a]
                if un: NOTES.append(f"{key}: {len(un)} assumption(s) match no row in any workbook - shown in every workbook as global premises (fill `affects` with row keys if they are not): {', '.join(un)}")
                if any(a["defaulted"] for a in ass): NOTES.append(f"{key}: {sum(a['defaulted'] for a in ass)} of {len(ass)} assumption(s) in default wording (register field `assumption` empty)")
            engine["top"] = [{"id": a["id"], "text": cust(T, T.text(a["wording"]), None, "Summary", a["id"])} for a in ass[:5]]
            if T.cited_q and dspec.get("sources", True):
                engine["sources"] = engine_name("sources", dspec); sheet_sources(wb.create_sheet(engine["sources"]), set(T.cited_q), key, dspec.get("code_locators") is False)
    if edition != "customer" and D["client_questions"] and not any(s.get("dataset") == "client_questions" for s in dspec["sheets"]) and dspec.get("open_questions", True):
        engine["open_questions"] = CM["open_questions"].get("name", "Open_Questions"); sheet_open_questions(wb.create_sheet(engine["open_questions"]), D)
    has_basis = any(c.get("grundlage") for s in sheets if s["type"] == "table" for c in visible(s))
    engine["client_fact"] = has_basis and any(BASIS_L["basis_client"] in v for n in wb.sheetnames for r in wb[n].iter_rows(values_only=True) for v in r if isinstance(v, str))
    for sh, ws in deferred:
        if sh["type"] == "mgmt": sheet_mgmt(ws, key, dspec, sh, ctx, items, engine.get("top", []), blocks, edition)
    for sh, ws in deferred:
        if sh["type"] == "readme": sheet_readme(ws, key, dspec, wb, edition, engine, has_basis)
    if INTERIM: interim_banner(wb, key, D)
    out_dir = DELIV if edition == "customer" else os.path.join(DELIV, "intern"); os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, P["deliverables"][key]["file"]); wb.save(out)
    if T.unknown_claims: NOTES.append(f"{key}: {len(T.unknown_claims)} unknown claim id(s) dropped from evidence/text: {', '.join(sorted(T.unknown_claims)[:8])}")
    if T.unknown_q: NOTES.append(f"{key}: {len(T.unknown_q)} unknown question id(s) dropped: {', '.join(sorted(T.unknown_q)[:8])}")
    print(f"built: {key} -> {relp(out, ROOT)}" + (" (INTERIM)" if INTERIM else "") + f" [{edition}]")
    return out

def build(key):
    dspec = SPEC["deliverables"][key]; D = load_all()
    for n in dspec.get("requires", []):
        if not available(D, n): print(f"{key}: input '{n}' missing - skipped"); return []
    if source_status(key) == "draft" and not INTERIM and "--force" not in sys.argv:
        print(f"{key}: analysis is still `status: draft` (mid-gauntlet) - refused; use --interim for a checkpoint build or --force with a logged reason"); return []
    E, W, _ = validate(SPEC, key, DATASETS, engine_sheets=engine_names(dspec), cfg=P)
    if E: sys.exit(f"BUILD REJECTED: the spec of {key} is invalid (`dbcx build_excel --check {key}`):\n  " + "\n  ".join(E))
    prep = Prep(key, dspec, D); phases = D["req"].get("phase_values_in_scope") or ["MVP"]; prep.extra = {"phase_in_scope": phases[0]}
    if MDS and hasattr(MDS, "extra_context"): prep.extra.update(MDS.extra_context(D) or {})
    outs = [write_edition(key, dspec, D, prep, ed) for ed in EDITIONS]
    if "--internal" in sys.argv and not INTERIM: internal_notes(D, key, dspec, prep)
    return outs

def engine_name(kind, dspec):
    """Engine sheet name; `alt_name` when a method sheet already carries the name (e.g. a source inventory called 'Sources')."""
    n = CM[kind]["name"]; return CM[kind].get("alt_name", n + "_2") if any(s["name"] == n for s in dspec["sheets"]) else n
def engine_names(dspec): return [engine_name("assumptions", dspec), engine_name("sources", dspec)]

def check(which):
    """--check: validate the merged spec and print the effective sheet/column list (no workbook)."""
    errs = [f"override patches: {e}" for e in SPEC.get("_patch_errors", [])]
    mv = load_method_module("validate")   # optional method hook validate.check_config(cfg) -> [error | "WARNING ..."]: rules of the run configuration
    for e in (mv.check_config(P) or []) if mv and hasattr(mv, "check_config") else []:
        if e.startswith("WARNING "): print(f"run configuration warning: {e[8:]}")
        else: errs.append(f"run configuration: {e}")
    try: D = load_all(); data = {n: f(D) for n, f in DATASETS.items() if n != "client_questions"}
    except Exception as ex: D, data = None, None; print(f"(dataset field check skipped: {ex})")
    for k in which:
        sp = os.path.join(ROOT, "analysis", "summaries", f"{k}.md")
        E, W, out = validate(SPEC, k, DATASETS, data, open(sp, encoding="utf-8").read() if os.path.exists(sp) else None, engine_names(SPEC["deliverables"][k]), cfg=P)
        print(f"{k}: {SPEC['deliverables'][k].get('title', '')}"); print("\n".join(out))
        for w in W: print(f"  warning: {w}")
        errs += E
    for e in errs: print(f"ERROR: {e}")
    print(f"{len(errs)} error(s)"); sys.exit(1 if errs else 0)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "-h" in args or "--help" in args: print(__doc__); sys.exit(0)
    if _ED not in ("customer", "full", "both"): sys.exit("--edition customer|full|both")
    which = [a for a in args if a in SPEC["deliverables"]]
    if not which and "--all" not in args: sys.exit(f"name the deliverables to build ({' '.join(SPEC['deliverables'])}) or pass --all  (see --help)")
    if not which: which = [k for k in SPEC["deliverables"] if isinstance(P["deliverables"].get(k), dict) and P["deliverables"][k].get("enabled")]
    if "--check" in args: check(which)
    if SPEC.get("_patch_errors"): sys.exit("BUILD REJECTED: override patches failed:\n  " + "\n  ".join(SPEC["_patch_errors"]))
    if not INTERIM:   # the Annahmen and Offene_Fragen sheets show released questions only - a client workbook never ships without an unreleased assumption
        from common import load_questions
        un = [q["id"] for q in load_questions() if q.get("released") is False]
        if un: sys.exit(f"BUILD REJECTED: {len(un)} question(s) not released yet ({', '.join(un[:8])}) - review their `related` neighbours / link duplicates, then `dbcx questions release --all` (an --interim build shows the released ones only)")
    built = [b for w in which for b in build(w)]
    NOTES += [f"duplicate column header renamed to '{h}' on sheet {s} (fix the spec)" for s, h in X.DUPES]
    for n in dict.fromkeys(NOTES): print(f"note: {n}")
    if built and not INTERIM:
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lint_deliverable.py")] + built, capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0 and "--allow-process-language" not in args:
            for b in built: os.replace(b, b + ".REJECTED.xlsx")
            sys.exit("BUILD REJECTED: client-facing wording contains process language (see above). Fix the statements in the analysis files (`dbcx render brief postpass <scope>`) and rebuild, or pass --allow-process-language with a logged reason. Files kept as *.REJECTED.xlsx for inspection.")
