#!/usr/bin/env python3
"""The customer's system landscape -> state/landscape.json: ALL systems of the
customer, also those this run does not estimate (BTP, ERP, CMS ...). Optional; without it names resolve against run.json systems only.

Usage: dbcx landscape_import <file> [<file> ...] [--sheet S] [--header-row N] [--map id=<col>,name=<col>,kind=<col>,description=<col>,owner=<col>,aliases=<col>] [--dry-run]
  <file>.csv | .xlsx   GENERIC converter: one row per system; columns id, name, kind and the optional description, owner,
                       aliases (several separated by ; | or line breaks). --map names the client's headers (header text, case-insensitive,
                       or a column letter); without it the headers are the field names. CSV: UTF-8, delimiter , or ; (detected).
  <file>.json          a released artefact (`dbcx handover import ...` puts it into input/handover/):
                       system-inventory (ea-landscape): systems[] name -> id, vendor_product -> name (else name), category -> kind,
                         description, owner; aliases: the short name when vendor_product is the display name
                       data-flows (ea-landscape): flows[] id, from_system -> from, to_system -> to, middleware -> via = the landscape's
                         interfaces (combine it with a system source)
                       landscape: the shape itself ({systems: [...], interfaces: [...]})
                       target-architecture is refused: it has no system list (its options name system ids only)
Writes state/landscape.json {"sources": [{file, type, sha256}], "systems": [{id, name, kind, description, owner, aliases}], "interfaces":
[{id, from, to, via}]}; errors (no id, an id twice) write nothing. Afterwards it refreshes the pre-fill of state/requirements.json.
Freeze the client's file first like every artefact: `dbcx handover import <file> --as landscape`, then convert input/handover/<file>.
"""
import csv, hashlib, io, json, os, re, sys

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, REQ_PATH, project, load_json, save_json, relp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import tfe_model as TM

FIELDS = TM.LANDSCAPE_FIELDS


def opt(a, k, d=None): return a[a.index(k) + 1] if k in a else d


def table_rows(path, sheet, header_row):
    if path.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        if sheet and sheet not in wb.sheetnames: sys.exit(f"sheet '{sheet}' not in {path} ({', '.join(wb.sheetnames)})")
        rows = [list(r) for r in (wb[sheet] if sheet else wb.worksheets[0]).iter_rows(values_only=True)]
    else:
        text = open(path, encoding="utf-8-sig").read(); first = (text.splitlines() or [""])[0]
        delim = ";" if first.count(";") > first.count(",") else ","
        rows = [list(r) for r in csv.reader(io.StringIO(text), delimiter=delim)]
    rows = rows[header_row - 1:]
    if not rows: sys.exit(f"{path}: no header row")
    return [("" if h is None else str(h).strip()) for h in rows[0]], [r for r in rows[1:] if any(v not in (None, "") for v in r)]


def column(spec, headers):
    for i, h in enumerate(headers):
        if h.lower() == str(spec).strip().lower(): return i
    if re.fullmatch(r"[A-Z]{1,2}", str(spec)):
        from openpyxl.utils import column_index_from_string
        return column_index_from_string(spec) - 1
    return None


def from_table(path, a):
    m = dict(x.split("=", 1) for x in (opt(a, "--map", "") or "").split(",") if "=" in x)
    bad = [k for k in m if k not in FIELDS]
    if bad: sys.exit(f"--map: unknown field(s) {', '.join(bad)} (fields: {', '.join(FIELDS)})")
    headers, rows = table_rows(path, opt(a, "--sheet"), int(opt(a, "--header-row", "1")))
    idx = {f: column(m.get(f, f), headers) for f in FIELDS}
    miss = [f"{f} ('{m.get(f, f)}')" for f in ("id", "name", "kind") if idx[f] is None]
    if idx["id"] is None: sys.exit(f"{path}: no id column {miss[0]} in {headers} - name it with --map id=<header>")
    warn = [f"{path}: column(s) {', '.join(miss)} not found in {headers} - " + "name defaults to the id, kind stays empty" if miss else ""]
    def val(r, f): v = r[idx[f]] if idx[f] is not None and idx[f] < len(r) else None; return "" if v is None else str(v).strip()
    return {"systems": [{f: val(r, f) for f in FIELDS} for r in rows]}, [w for w in warn if w]


def from_json(path):
    env = json.load(open(path, encoding="utf-8")); t = env.get("artefact_type") if isinstance(env, dict) else None
    d = env.get("data", env) if isinstance(env, dict) else {}
    if t == "system-inventory":
        out = []
        for s in d.get("systems") or []:
            disp = (s.get("vendor_product") or "").strip() or s.get("name")
            out.append({"id": s.get("name"), "name": disp, "kind": s.get("category") or "", "description": s.get("description") or "", "owner": s.get("owner") or "",
                        "aliases": [s.get("name")] if disp != s.get("name") else []})
        return t, {"systems": out}
    if t == "data-flows":
        return t, {"interfaces": [{"id": f.get("id"), "from": f.get("from_system"), "to": f.get("to_system"), "via": f.get("middleware")} for f in d.get("flows") or []]}
    if t == "target-architecture": sys.exit(f"{path}: a target-architecture artefact has no system list (its options name system ids only) - import the system-inventory of the same run")
    if isinstance(d, dict) and ("systems" in d or "interfaces" in d): return t or "landscape", {"systems": d.get("systems") or [], "interfaces": d.get("interfaces") or []}
    sys.exit(f"{path}: artefact type '{t}' - system-inventory, data-flows or the landscape shape ({{systems, interfaces}})")


def main():
    a = sys.argv[1:]
    files = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--sheet", "--header-row", "--map"))]
    if not files: sys.exit(__doc__)
    raw, sources, warn = {"systems": [], "interfaces": []}, [], []
    for f in files:
        if not os.path.exists(f): sys.exit(f"{f}: no such file")
        if f.lower().endswith(".json"): t, part = from_json(f)
        elif f.lower().endswith((".csv", ".xlsx", ".xlsm")): t = "table"; part, w = from_table(f, a); warn += w
        else: sys.exit(f"{f}: a .csv, .xlsx or .json file")
        raw["systems"] += part.get("systems") or []; raw["interfaces"] += part.get("interfaces") or []
        sources.append({"file": relp(os.path.abspath(f), ROOT), "type": t, "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest()})
    land, err, w = TM.normalise_landscape(raw); warn += w
    for x in warn: print(f"WARNING {x}")
    if err: sys.exit("REFUSED (nothing written):\n  " + "\n  ".join(err))
    if not land["systems"]: sys.exit("REFUSED: no system in " + ", ".join(files))
    out = {"sources": sources, **land}
    print(f"{len(land['systems'])} system(s), {len(land['interfaces'])} interface(s) from {', '.join(s['file'] for s in sources)}")
    if "--dry-run" in a: print("DRY RUN - nothing written"); return
    save_json(TM.LANDSCAPE_PATH, out); print(f"-> {TM.LANDSCAPE_PATH}")
    doc = load_json(REQ_PATH, {}) if os.path.exists(REQ_PATH) else None
    if doc and any("systems_named" in r or r.get("kind") == "interface" for r in doc.get("requirements") or []):
        import inputs
        for line in inputs.enrich_requirements(doc, project()): print(line)
        save_json(REQ_PATH, doc); print(f"pre-fill of {relp(REQ_PATH, ROOT)} refreshed")


if __name__ == "__main__":
    main()
