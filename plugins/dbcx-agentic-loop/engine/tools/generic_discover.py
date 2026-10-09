#!/usr/bin/env python3
"""generic discover - the scopes of a method without its own discover tool -> state/scopes.json
(consumed by `dbcx plan_waves`, `dbcx render`, `dbcx progress`). `dbcx discover` runs it when the method declares
method.json `scopes.discover: "generic:<variant>"` and has no tools/discover.py.

Usage: dbcx discover [--json]          (or dbcx generic_discover [--json])
The run configuration key named by method.json `scopes.state_key` (default `units`; method defaults <- engagement.json <- run.json)
says where the units come from, in the shape of the variant:
  generic:list      `<state_key>`: ["name", {"name": ..., "group": ..., "depends_on": [names], "size": n, "light": bool, "skip": bool,
                    <other key>: value}, ...] - the units named at init; other keys travel in `meta` (label = the key in capitals)
  generic:workbook  `<state_key>`: {"file": "input/units.xlsx", "sheet": "Units", "column": "Name", "group_column": "Area", "header_row": 1}
                    - one unit per distinct value of the column (header name, case-insensitive; sheet default = the first sheet);
                    size = the number of rows naming the unit, group = the group column's value in its first row (wave_rule group)
  generic:folders   `<state_key>`: {"root": "input/units", "per": "folder" | "document"} - one unit per sub-folder of the root (size =
                    the files in it) or per document below it (group = its folder relative to the root, size = 1)
  generic:inventory `<state_key>` (optional): {"table": ..., "name": ..., "group": ..., "depends_on": ..., "size": ...} - one unit per row of
                    the unit table of the PASSED inventory analysis (method.json inventory; table default inventory.scopes_table, name
                    default inventory.scopes_key or `name`; group / depends_on / size = field names of that table, each optional);
                    runs after the inventory gauntlet (the inventory phase's `after`: dbcx render handover; dbcx discover; dbcx plan_waves)
Paths: absolute, `@project/...` or relative to the run.
Scope ids are kebab-case slugs of the names (file name analysis/<dir>/<id>.md, agent name <agent_prefix><id>); the name travels
in meta NAME and appears in every brief. No automatic light pass: a list entry with `light: true` or scoring.light_pass_scopes.
"""
import json, os, re, sys

from common import SCOPES_PATH, STATUS_PATH, project, method, save_json, load_json, is_placeholder, resolve_root, relp, scope_info, phase_for_scope, RUN as ROOT, CLI

VARIANTS = ("list", "workbook", "folders", "inventory")


def variant(m):
    d = str((m.get("scopes") or {}).get("discover") or "")
    if not d.startswith("generic:") or d[len("generic:"):] not in VARIANTS:
        sys.exit(f"method {m['name']}: scopes.discover is '{d}' - the generic discover needs generic:list | generic:workbook | generic:folders | generic:inventory")
    return d[len("generic:"):]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").strip().lower()).strip("-")[:40].strip("-") or "unit"


def source(cfg, key, kind):
    v = cfg.get(key)
    if not isinstance(v, kind) or not v or (isinstance(v, dict) and any(is_placeholder(x) for x in v.values())):
        sys.exit(f"run.json `{key}` is empty, still a placeholder or not a {'list' if kind is list else 'JSON object'} ({v!r}): it is the unit source "
                 f"of the generic discover (`{CLI} generic_discover --help`); `{CLI} check_fill` lists the open placeholders.")
    return v


def from_list(entries):
    out = []
    for e in entries:
        if isinstance(e, str): e = {"name": e}
        if not isinstance(e, dict) or not str(e.get("name") or "").strip(): sys.exit(f"a unit entry has no name: {e!r}")
        meta = {k.replace("_", " ").upper(): v for k, v in e.items() if k not in ("name", "group", "depends_on", "size", "light", "skip", "meta") and isinstance(v, (str, int, float))}
        meta.update(e.get("meta") or {})
        out.append({"name": str(e["name"]).strip(), "group": str(e.get("group") or ""), "depends_on": list(e.get("depends_on") or []),
                    "size": int(e.get("size") or 1), "light": bool(e.get("light")), "skip": bool(e.get("skip")), "meta": meta})
    return out, "run configuration list"


def from_workbook(src):
    import openpyxl
    f = resolve_root(str(src.get("file") or ""))
    if not f or not os.path.isfile(f): sys.exit(f"workbook not found: {src.get('file')!r} (`file` of the unit source)")
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    sh = src.get("sheet") or wb.sheetnames[0]
    if sh not in wb.sheetnames: sys.exit(f"{relp(f, ROOT)}: no sheet '{sh}' (sheets: {', '.join(wb.sheetnames)})")
    rows = list(wb[sh].iter_rows(values_only=True)); hr = int(src.get("header_row") or 1)
    if len(rows) < hr: sys.exit(f"{relp(f, ROOT)}!{sh}: no header row {hr}")
    heads = [str(h or "").strip().lower() for h in rows[hr - 1]]

    def col(name, required):
        if not name: return None
        if str(name).strip().lower() in heads: return heads.index(str(name).strip().lower())
        if required: sys.exit(f"{relp(f, ROOT)}!{sh}: no column '{name}' in header row {hr} ({', '.join(h for h in heads if h)})")
        return None
    ci = col(src.get("column"), True); gi = col(src.get("group_column"), bool(src.get("group_column")))
    from openpyxl.utils import get_column_letter
    units = {}
    for n, r in enumerate(rows[hr:], hr + 1):
        v = str(r[ci] if ci < len(r) and r[ci] is not None else "").strip()
        if not v: continue
        u = units.setdefault(v, {"name": v, "group": str(r[gi] or "").strip() if gi is not None and gi < len(r) else "", "depends_on": [], "size": 0, "light": False, "skip": False,
                                 "meta": {"SOURCE": f"{relp(f, ROOT)}!{sh}!{get_column_letter(ci + 1)}{n}"}})
        u["size"] += 1
    wb.close()
    for u in units.values(): u["meta"]["ROWS"] = u["size"]
    return list(units.values()), f"{relp(f, ROOT)}!{sh} column {src.get('column')}"


def from_folders(src):
    root = resolve_root(str(src.get("root") or "input")); per = src.get("per") or "folder"
    if per not in ("folder", "document"): sys.exit(f"`per` of the unit source is '{per}' - folder | document")
    if not os.path.isdir(root): sys.exit(f"folder not found: {src.get('root')!r} (`root` of the unit source)")
    files = lambda d: sorted(os.path.join(a, f) for a, ds, fs in os.walk(d) for f in fs if not f.startswith(".") and not any(p.startswith(".") for p in os.path.relpath(a, d).split(os.sep) if p != "."))
    out = []
    if per == "folder":
        for n in sorted(os.listdir(root)):
            d = os.path.join(root, n)
            if n.startswith(".") or not os.path.isdir(d): continue
            out.append({"name": n, "group": "", "depends_on": [], "size": len(files(d)) or 1, "light": False, "skip": False, "meta": {"FOLDER": relp(d, ROOT)}})
    else:
        for p in files(root):
            g = os.path.relpath(os.path.dirname(p), root)
            out.append({"name": os.path.splitext(os.path.basename(p))[0], "group": "" if g == "." else g.replace(os.sep, "/"), "depends_on": [], "size": 1, "light": False, "skip": False, "meta": {"DOCUMENT": relp(p, ROOT)}})
    return out, f"{relp(root, ROOT)} ({per} per unit)"


def from_inventory(m, src):
    inv = m.get("inventory") or sys.exit(f"method {m['name']}: generic:inventory needs an inventory phase (method.json inventory)")
    js = scope_info(inv["scope"], m)[0]; ph = phase_for_scope(inv["scope"], m)
    if not os.path.exists(js): sys.exit(f"no {relp(js, ROOT)} - the inventory analysis comes first (`{CLI} md_to_json {inv.get('kind', 'inventory')} {inv['output']}`, then its gauntlet)")
    if ph and not ((load_json(STATUS_PATH, {}) or {}).get("phases", {}).get(ph) or {}).get("passed"):
        sys.exit(f"the inventory {inv['scope']} has not passed its gauntlet (STATUS phases.{ph}.passed) - the units come from the passed inventory only")
    table = src.get("table") or inv.get("scopes_table"); key = src.get("name") or inv.get("scopes_key") or "name"
    rows = (load_json(js, {}) or {}).get(table)
    if not isinstance(rows, list): sys.exit(f"{relp(js, ROOT)} has no table '{table}' (`table` of the unit source or inventory.scopes_table)")
    f = lambda r, k: r.get(src[k]) if src.get(k) else None
    out = []
    for r in rows:
        if not str(r.get(key) or "").strip(): continue
        deps = f(r, "depends_on"); deps = [deps] if isinstance(deps, str) else list(deps or [])
        try: size = int(f(r, "size") or 1)
        except (TypeError, ValueError): size = 1
        out.append({"name": str(r[key]).strip(), "group": str(f(r, "group") or ""), "depends_on": [d for d in deps if d], "size": size, "light": False, "skip": False,
                    "meta": {"INVENTORY ROW": r.get("rid") or str(r[key]).strip()}})
    return out, f"{relp(js, ROOT)} table {table}"


def main():
    if "--help" in sys.argv or "-h" in sys.argv: print(__doc__); return
    cfg = project(); m = method(); v = variant(m); key = (m.get("scopes") or {}).get("state_key") or "units"
    units, src = from_list(source(cfg, key, list)) if v == "list" else from_workbook(source(cfg, key, dict)) if v == "workbook" \
        else from_folders(source(cfg, key, dict)) if v == "folders" else from_inventory(m, cfg.get(key) if isinstance(cfg.get(key), dict) else {})
    if not units: sys.exit(f"no units found in {src}")
    ids, scopes, warn = {}, {}, []
    for u in units:
        sid = base = slug(u["name"]); i = 2
        while sid in scopes: sid = f"{base}-{i}"; i += 1
        if u["name"] in ids: warn.append(f"duplicate unit name '{u['name']}' - kept as {sid}")
        ids.setdefault(u["name"], sid); ids.setdefault(slug(u["name"]), sid)
        scopes[sid] = {"group": u["group"], "depends_on": u["depends_on"], "size": u["size"], "light": u["light"], "light_reason": "listed as light" if u["light"] else "",
                       "skip": u["skip"], "meta": dict({"NAME": u["name"]}, **u["meta"])}
    for sid, s in scopes.items():
        deps = []
        for d in s["depends_on"]:
            t = ids.get(d) or ids.get(slug(d))
            if t and t != sid: deps.append(t)
            elif not t: warn.append(f"{sid}: depends on unknown unit '{d}' (ignored)")
        s["depends_on"] = deps
    nk = (m.get("scopes") or {}).get("noun_key") or "unit.noun"; noun = cfg
    for part in nk.split("."): noun = noun.get(part) if isinstance(noun, dict) else None
    out = {"noun": noun if isinstance(noun, str) and not is_placeholder(noun) else "Unit", "method": m["name"], "source": src, "scopes": scopes}
    save_json(SCOPES_PATH, out)
    if "--json" in sys.argv: print(json.dumps(out, indent=1, ensure_ascii=False)); return
    print(f"{len(scopes)} scopes -> state/scopes.json (generic:{v}, from {src})")
    for sid, s in scopes.items(): print(f"  {sid:30s} {s['meta']['NAME'][:40]:40s} group {s['group'] or '-'}  size {s['size']}" + ("  SKIP" if s["skip"] else ""))
    for w in warn: print("WARNING", w)
    print(f"next: {CLI} plan_waves, then `{CLI} status scope <id> '{{\"wave\": n, \"status\": \"open\"}}'` for every scope")


if __name__ == "__main__":
    main()
