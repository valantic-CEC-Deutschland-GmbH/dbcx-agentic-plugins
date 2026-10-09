#!/usr/bin/env python3
"""Convert the client's requirements workbook into state/requirements.json using <project>/requirements_mapping.json.

Usage: dbcx requirements_to_json [path/to/requirements.xlsx]      (default: newest file matching project.json requirements.input_glob)
Idempotent. Re-run whenever the client sends a new version. Requires openpyxl.
Optional group keys of a sheet entry (opt-in; a mapping without them writes exactly what it wrote before; the method interprets them -
tech-fit-estimation):
  kind: interfaces        rows are interfaces (`kind: "interface"` on the row; map columns.from / to / via like any other field)
  estimate: false         rows are reference rows (`estimate: false` on the row)
  systems_field: <col>    the cell names the affected systems -> `systems_named` [names as written, split at , ; and line breaks]
  rollup_to_field: <col>  the id the row's effort rolls up to -> `rollup_to` (empty cell: the row's own id)
  passthrough: true       the sheet is recorded unchanged -> `passthrough` [{group, sheet, header_row, id_column, columns [{letter, header,
                          width}], head_rows [[values above the header]], rows [{row, id, values}]}] (cached values, not formulas)
The keys used are recorded per group in `group_keys` (+ id_column, missing_columns). A method may enrich the result before it is written:
methods/<m>/inputs.py enrich_requirements(doc, cfg) -> [message lines].
"""
import datetime, json, sys, glob, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, REQ_PATH, project, load_json, save_json, is_placeholder, relp, load_method_module
import openpyxl
from openpyxl.utils import get_column_letter

GROUP_KEYS = ("kind", "estimate", "systems_field", "rollup_to_field", "passthrough")

OUT = REQ_PATH

def find_input(p):
    if len(sys.argv) > 1: return sys.argv[1]
    cands = [c for c in sorted(glob.glob(os.path.join(ROOT, p["requirements"]["input_glob"]))) if not os.path.basename(c).startswith("~$")]
    if not cands: sys.exit(f"no requirements workbook matching {p['requirements']['input_glob']}")
    return cands[-1]

def col_index(spec, headers):
    if spec is None or is_placeholder(spec): return None
    if isinstance(spec, int): return spec - 1
    for i, h in enumerate(headers):   # a header named exactly like the mapping value wins over a column-letter reading ("ID" is a header, not column I+D)
        if h is not None and str(h).strip().lower() == str(spec).strip().lower(): return i
    if re.fullmatch(r"[A-Z]{1,2}", str(spec)): return openpyxl.utils.column_index_from_string(spec) - 1
    print(f"WARNING header '{spec}' not found in {headers}"); return None

def cell_json(v):
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)): return v.isoformat()
    return v if v is None or isinstance(v, (bool, int, float, str)) else str(v)

def passthrough(ws, sh, hr, id_i):
    """the sheet as the client wrote it: columns in order (letter, header, width), the rows above the header and every row below it"""
    rows = [list(r) for r in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)]
    filled = [i for i, r in enumerate(rows) if any(v not in (None, "") for v in r)]
    rows = rows[:filled[-1] + 1] if filled else []
    ncol = max([j + 1 for r in rows for j, v in enumerate(r) if v not in (None, "")] or [0])
    head = rows[hr - 1] if len(rows) >= hr else []
    cols = [{"letter": get_column_letter(j + 1), "header": cell_json(head[j]) if j < len(head) else None,
             "width": ws.column_dimensions[get_column_letter(j + 1)].width if get_column_letter(j + 1) in ws.column_dimensions else None} for j in range(ncol)]
    def vals(r): return [cell_json(r[j]) if j < len(r) else None for j in range(ncol)]
    body = [{"row": n, "id": (str(r[id_i]).strip() or None) if id_i is not None and id_i < len(r) and r[id_i] not in (None, "") else None, "values": vals(r)}
            for n, r in enumerate(rows[hr:], hr + 1)]
    return {"group": sh["group"], "sheet": sh["sheet"], "header_row": hr, "id_column": get_column_letter(id_i + 1) if id_i is not None else None,
            "columns": cols, "head_rows": [vals(r) for r in rows[:hr - 1]], "rows": body}

def main():
    p = project(); m = load_json(p["requirements"]["mapping"]); path = find_input(p)
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {"source_file": relp(path, ROOT), "requirements": [], "legend": {}, "groups": [], "phase_values_in_scope": [x for x in m.get("phase_values_in_scope", []) if not is_placeholder(x)]}
    sep = re.compile(m.get("list_separator_regex", "[,;\n]")); lists = set(m.get("list_fields", []))
    for sh in m["sheets"]:
        if is_placeholder(sh["sheet"]): print(f"skip sheet placeholder: {sh['sheet']}"); continue
        if sh["sheet"] not in wb.sheetnames: print(f"WARNING sheet '{sh['sheet']}' not in workbook {wb.sheetnames}"); continue
        ws = wb[sh["sheet"]]; hr = sh.get("header_row", 1); headers = [c.value for c in ws[hr]]
        idx = {f: col_index(c, headers) for f, c in sh["columns"].items()}
        extra = {c: col_index(c, headers) for c in sh.get("extra_columns", [])}
        out["groups"].append(sh["group"]); n = 0
        keys = {k: sh[k] for k in GROUP_KEYS if k in sh}; sys_i = rol_i = None
        if keys:   # 0.4.0 group keys (opt-in)
            sys_i = col_index(sh["systems_field"], headers) if sh.get("systems_field") else None
            rol_i = col_index(sh["rollup_to_field"], headers) if sh.get("rollup_to_field") else None
            keys["sheet"] = sh["sheet"]; keys["id_column"] = get_column_letter(idx["id"] + 1) if idx.get("id") is not None else None
            miss = [sh[k] for k, i in (("systems_field", sys_i), ("rollup_to_field", rol_i)) if sh.get(k) and i is None]
            if miss: keys["missing_columns"] = miss
            out.setdefault("group_keys", {})[sh["group"]] = keys
            if sh.get("passthrough") is True:
                if idx.get("id") is None: print(f"ERROR passthrough sheet '{sh['sheet']}' has no id column (columns.id) - `dbcx build_excel --check` refuses")
                out.setdefault("passthrough", []).append(passthrough(ws, sh, hr, idx.get("id")))
        for rn, row in enumerate(ws.iter_rows(min_row=hr + 1, values_only=True), hr + 1):
            if not any(v not in (None, "") for v in row): continue
            rec = {"group": sh["group"]}
            for f, i in idx.items():
                v = row[i] if i is not None and i < len(row) else None
                if f in lists: rec[f] = [x.strip() for x in sep.split(str(v)) if x.strip()] if v else []
                else: rec[f] = str(v).strip() if v not in (None, "") else ""
            if not rec.get("id"): rec["id"] = f"{sh.get('id_prefix', '')}{rn:03d}"
            iface = sh.get("kind") == "interfaces"
            if not rec.get("title") and not rec.get("description") and not (iface and (rec.get("from") or rec.get("to"))): continue
            if iface: rec["kind"] = "interface"
            if sh.get("estimate") is False: rec["estimate"] = False
            if sh.get("systems_field"):
                v = row[sys_i] if sys_i is not None and sys_i < len(row) else None
                rec["systems_named"] = [x.strip() for x in re.split(r"[,;\n]", str(v)) if x.strip()] if v not in (None, "") else []
            if sh.get("rollup_to_field"):
                v = row[rol_i] if rol_i is not None and rol_i < len(row) else None
                rec["rollup_to"] = str(v).strip() if v not in (None, "") and str(v).strip() else rec["id"]
            rec["extra"] = {c: (row[i] if i is not None and i < len(row) else None) for c, i in extra.items()}
            out["requirements"].append(rec); n += 1
        print(f"{n} requirements from sheet '{sh['sheet']}' ({sh['group']})")
    if m.get("legend_sheet") and m["legend_sheet"] in wb.sheetnames:
        for row in wb[m["legend_sheet"]].iter_rows(values_only=True):
            if row and row[0] and len(row) > 1 and row[1]: out["legend"][str(row[0])] = str(row[1])
    ids = [r["id"] for r in out["requirements"]]
    if len(ids) != len(set(ids)): print("WARNING duplicate requirement ids:", sorted({i for i in ids if ids.count(i) > 1}))
    hook = load_method_module("inputs")   # optional method hook: enrich the rows before they are written (tech-fit-estimation: pre-fill)
    if hook and hasattr(hook, "enrich_requirements"):
        for line in hook.enrich_requirements(out, p) or []: print(line)
    save_json(OUT, out); print(f"{len(out['requirements'])} requirements -> {relp(OUT, ROOT)} from {out['source_file']}")

if __name__ == "__main__":
    main()
