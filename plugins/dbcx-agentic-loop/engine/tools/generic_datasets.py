"""generic row providers for `dbcx build_excel` - the datasets of a method that declares method.json `"datasets": "generic"`
and has no datasets.py (common.load_method_module loads this module in its place). Pure functions over the loaded analysis JSON.

Dataset names (the `dataset` of a table sheet, `row_values_from: "<dataset>.<field>"` of an overview matrix):
  <kind>.<table>   one row per row of the table section <table> of every analysis of the method kind <kind>: the per-scope kind
                   (every scope analysis), the inventory kind, a consolidation kind (every consolidation of that kind)
  <kind>           one row per analysis of the kind: its head fields, text and list sections, kv sections as nested fields (`<section>.<field>`)
Every row also carries `scope` (the scope id: the unit's slug, the inventory scope or the consolidation id) and `scope_name` (the unit's
name from state/scopes.json meta NAME, else the id); a field of the table with the same name wins. Row fields are the kinds.json field names.
A method's own datasets.py may import this module by name and extend its DATASETS.
"""
import json, os

from common import method, load_json, SCOPES_PATH


def _docs(D, kind, m):
    """[(scope id, analysis)] of one method kind, in a stable order"""
    out = [(s, D["scopes"][s]) for s in sorted(D["scopes"])] if (m.get("scopes") or {}).get("kind") == kind else []
    inv = m.get("inventory")
    if inv and inv.get("kind", "inventory") == kind and D.get("inventory"): out.append((inv["scope"], D["inventory"]))
    out += [(x, D["cons"][x]) for x, c in sorted((m.get("consolidations") or {}).items()) if c.get("kind", x) == kind and (D.get("cons") or {}).get(x)]
    return out


def _names():
    return {s: str((v.get("meta") or {}).get("NAME") or s) for s, v in (load_json(SCOPES_PATH, {}) or {}).get("scopes", {}).items()}


def _table(kind, table):
    def rows(D):
        m = method(); names = _names()
        return [dict({"scope": s, "scope_name": names.get(s, s)}, **r) for s, d in _docs(D, kind, m) for r in (d.get(table) or []) if isinstance(r, dict)]
    return rows


def _head(kind, tables):
    def rows(D):
        m = method(); names = _names()
        return [dict({"scope": s, "scope_name": names.get(s, s)}, **{k: v for k, v in d.items() if k not in tables and k not in ("claims", "claimed_rows", "assumptions_taken")})
                for s, d in _docs(D, kind, m)]
    return rows


def datasets(m):
    """{dataset name: fn(D) -> rows} from the method's kinds.json"""
    kinds = json.load(open(os.path.join(m["_dir"], "kinds.json"), encoding="utf-8")).get("kinds", {})
    out = {}
    for kind, k in kinds.items():
        tables = [s["key"] for s in k.get("sections", []) if isinstance(s, dict) and s.get("type") == "table"]
        out[kind] = _head(kind, tables)
        for t in tables: out[f"{kind}.{t}"] = _table(kind, t)
    return out


try: DATASETS = datasets(method())
except (SystemExit, OSError, ValueError): DATASETS = {}


def available(D, name):
    return bool(DATASETS[name](D)) if name in DATASETS else None
