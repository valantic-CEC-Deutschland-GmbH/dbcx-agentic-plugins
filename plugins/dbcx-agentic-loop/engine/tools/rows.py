#!/usr/bin/env python3
"""Stable row ids, claim -> row targeting and must-claim coverage.

Row id (`rid`, written into every table row by md_to_json): the section's row key - kinds.json `row_key` (a field or a list of
fields), else the key field of method.json `gauntlet.row_tables`, else the section's first field. A single id-like key value
(no spaces, <= 80 characters, e.g. FR-012, F-001, de.shop.CartService) IS the row id; anything else (free text, several key
cells) becomes "r" + the first 8 hex digits of sha1(the normalised key cells: lowercase, whitespace collapsed, lists joined by ';').
A hashed id changes when its key text changes - that is the one case in which a claim has to be re-targeted. A section with
several key fields and `row_key_sep` (e.g. "@", row_key ["req_id", "option"]) joins its filled id-like key values instead:
FR-041@brownfield (a claim targets D1/Schaetzung#FR-041@brownfield exactly). A repeated id in one
section gets a suffix (~2, ~3). A kv section is one row; its id is the scope name (the row the deliverable shows for the scope).

Targets: `<D>/<Sheet>` or `<kind>/<section>`, optionally followed by `#` (or the legacy `:`) and one or more row ids or row key
values separated by ','. A claim covers a row when a target ref equals the row's rid or its key value (exact, after normalising).
method.json `claims.sheet_tables` maps a sheet to the section(s) it shows; without it a ref must be unique across the sections.
Coverage is an exact id match - no substring matching of statements.
Must-claim: method.json `claims.must_claim: {"<kind>.<section>": [fields]}` - a row whose listed field is filled (a boolean only
when true) needs a claim. Claim cap = must-claim rows + scoring.claim_cap_reserve (5), never above the old fixed cap.
"""
import hashlib, json, re

SKIP = ("claims", "open_questions")
ID_LIKE = re.compile(r"^[A-Za-z0-9_.$/@+-]{1,80}$")
TARGET = re.compile(r"^(?P<sheet>[^#:]+?)\s*(?:[#:]\s*(?P<refs>.+))?$")

def norm(v):
    if isinstance(v, list): v = ";".join(map(str, v))
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip().lower()

def rhash(row):
    """content hash of a row without the fields this module adds"""
    return hashlib.sha1(json.dumps({k: v for k, v in row.items() if k not in ("rid", "claimed_by")}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]

def sections(kind, SP, m):
    """[(section key, type 'table'|'kv', [key fields])] of a kind - every table/kv section except claims and open questions"""
    rt = {t: k for t, k in ((m or {}).get("gauntlet", {}).get("row_tables", {}).get(kind) or [])}
    out = []
    for s in (SP.get(kind) or {}).get("sections", []):
        if not isinstance(s, dict) or s.get("type") not in ("table", "kv") or s.get("key") in SKIP or not s.get("fields"): continue
        rk = s.get("row_key") or rt.get(s["key"]) or next(iter(s["fields"]))
        out.append((s["key"], s["type"], rk if isinstance(rk, list) else [rk]))
    return out

def key_seps(kind, SP):
    """{section key: row_key_sep} of a kind's sections that declare one"""
    return {s["key"]: s["row_key_sep"] for s in (SP.get(kind) or {}).get("sections", []) if isinstance(s, dict) and s.get("row_key_sep")}

def row_id(row, keys, sep=None):
    vals = [row.get(k) for k in keys]
    if len(vals) == 1 and isinstance(vals[0], (str, int)) and ID_LIKE.match(str(vals[0]).strip()): return str(vals[0]).strip()
    filled = [str(v).strip() for v in vals if v not in (None, "", [])]
    if sep and filled and all(isinstance(v, (str, int)) for v in vals if v not in (None, "", [])) and ID_LIKE.match(sep.join(filled)): return sep.join(filled)
    if all(v in (None, "", []) for v in vals): return "r" + rhash(row)[:8]
    return "r" + hashlib.sha1("|".join(norm(v) for v in vals).encode("utf-8")).hexdigest()[:8]

def build_index(kind, data, SP, m, scope=None, assign=True):
    """{section: {"type", "keys", "rows": {rid: row}, "by_key": {normalised key value: rid}}}; assign=True writes row["rid"]"""
    idx = {}; dups = []; seps = key_seps(kind, SP)
    for key, typ, keys in sections(kind, SP, m):
        val = data.get(key)
        ent = {"type": typ, "keys": keys, "rows": {}, "by_key": {}}
        if typ == "kv":
            if isinstance(val, dict) and any(v not in (None, "", [], False, 0) for v in val.values()):
                rid = scope or key; ent["rows"][rid] = val; ent["by_key"][norm(rid)] = rid
        else:
            for row in val or []:
                rid = row_id(row, keys, seps.get(key)); base = rid; n = 1
                while rid in ent["rows"]: n += 1; rid = f"{base}~{n}"
                if n > 1: dups.append(f"{key}#{base}")
                if assign: row["rid"] = rid
                ent["rows"][rid] = row
                kv = norm(";".join(str(row.get(k) or "") for k in keys))
                if kv: ent["by_key"].setdefault(kv, rid)
        idx[key] = ent
    return idx, dups

def parse_target(t):
    mm = TARGET.match((t or "").strip())
    if not mm: return "", []
    refs = mm.group("refs") or ""
    return mm.group("sheet").strip(), ([r.strip() for r in refs.split(",") if r.strip()] if refs else [])

def candidates(sheet, kind, idx, sheet_tables):
    """sections of this analysis a target sheet addresses (None = unknown sheet: search every section)"""
    if "/" in sheet and sheet.split("/", 1)[0] == kind and sheet.split("/", 1)[1] in idx: return [sheet.split("/", 1)[1]]
    mapped = (sheet_tables or {}).get(sheet)
    if mapped is None: return None
    mapped = mapped if isinstance(mapped, list) else [mapped]
    return [x.split(".", 1)[1] for x in mapped if x.split(".", 1)[0] == kind and x.split(".", 1)[1] in idx]

def resolve_target(target, kind, idx, sheet_tables):
    """([(section, rid)], [unresolved or ambiguous refs])"""
    sheet, refs = parse_target(target)
    cand = candidates(sheet, kind, idx, sheet_tables); pool = cand if cand is not None else list(idx)
    if not refs:
        kvs = [s for s in (cand or []) if idx[s]["type"] == "kv" and idx[s]["rows"]]
        return ([(kvs[0], next(iter(idx[kvs[0]]["rows"])))] if len(kvs) == 1 and len(cand) == 1 else []), []
    def find(r): return [(s, r) for s in pool if r in idx[s]["rows"]] or [(s, idx[s]["by_key"][norm(r)]) for s in pool if norm(r) in idx[s]["by_key"]]
    if len(refs) > 1 and not all(find(r) for r in refs) and find(", ".join(refs)): refs = [", ".join(refs)]   # a key value that contains commas
    hits, bad = [], []
    for r in refs:
        found = find(r)
        if len(found) == 1 or (found and cand is not None): hits += found   # several mapped sections: the sheet shows all of them
        else: bad.append(r + (" (ambiguous: " + ", ".join(s for s, _ in found) + ")" if found else ""))
    return hits, bad

def claim_rows(kind, claims, idx, sheet_tables):
    """({(section, rid): [claim ids]}, [(claim id, unresolved ref)])"""
    cov, bad = {}, []
    for c in claims or []:
        for part in [x for x in re.split(r"\s*;\s*", c.get("target") or "") if x]:
            hits, miss = resolve_target(part, kind, idx, sheet_tables)
            for h in hits:
                ids = cov.setdefault(h, [])
                if c.get("id") not in ids: ids.append(c.get("id"))
            bad += [(c.get("id"), r) for r in miss]
    return cov, bad

def must_claim_cells(kind, idx, m):
    """[(section, rid, field, value)] for every filled must-claim cell; None when the method declares none for this kind"""
    mc = {k: v for k, v in ((m or {}).get("claims") or {}).get("must_claim", {}).items() if not k.startswith("_") and k.split(".", 1)[0] == kind}
    if not mc: return None
    cells = []
    for key, fields in mc.items():
        sec = key.split(".", 1)[1]
        for rid, row in (idx.get(sec) or {}).get("rows", {}).items():
            for f in fields:
                v = row.get(f)
                if v in (None, "", [], False): continue
                cells.append((sec, rid, f, v))
    return cells

def derived_cap(n_must_rows, bound, sc):
    return min(int(bound), n_must_rows + int((sc or {}).get("claim_cap_reserve", 5)))

def label(row, keys, rid):
    v = " / ".join(str(row.get(k) or "") for k in keys).strip(" /")
    return f"{rid}" if v == rid or not v else f"{rid} ({v[:60]})"

def analyse(kind, data, SP, m, scope=None, assign=True):
    """everything md_to_json / extract_claims / postpass need: index, coverage, uncovered rows, must-claim cells"""
    idx, dups = build_index(kind, data, SP, m, scope, assign)
    st = ((m or {}).get("claims") or {}).get("sheet_tables") or {}
    st = {k: v for k, v in st.items() if not k.startswith("_")}
    cov, bad = claim_rows(kind, data.get("claims") or [], idx, st)
    cells = must_claim_cells(kind, idx, m)
    must_rows = sorted({(s, r) for s, r, _, _ in cells}) if cells is not None else None
    return {"index": idx, "dups": dups, "covered": cov, "unresolved": bad, "must_cells": cells, "must_rows": must_rows,
            "must_uncovered": [x for x in (cells or []) if (x[0], x[1]) not in cov]}

def annotate(result):
    """write claimed_by into every table row (kv sections are listed in the top-level claimed_rows map only)"""
    out = {}
    for sec, ent in result["index"].items():
        for rid, row in ent["rows"].items():
            ids = result["covered"].get((sec, rid), [])
            if ent["type"] == "table": row["claimed_by"] = ids
            out[f"{sec}#{rid}"] = ids
    return out
