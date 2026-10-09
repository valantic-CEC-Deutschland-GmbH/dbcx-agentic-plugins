"""Row providers of the `requirements` method for dbcx build_excel (pure functions over the loaded JSON).

load(D, ROOT, INTERIM) adds the method's inputs to the engine's base dict (D["scopes"] = the epic analyses, D["inventory"], D["cons"], D["status"], D["client_questions"]):
  D["inv"]    = the source inventory / epic structure (alias of D["inventory"], with empty tables when it does not exist yet)
  D["set"]    = the consolidated requirement set (analysis/consolidated/SET.json) or None
  D["corpus"] = <project>/corpus/index.json (source paths, revisions, anchor counts, extraction quality) - the provable half of the Sources sheet

Datasets: sources, epics (D1); requirements, traceability, crosscheck, catalogue_gaps, contradictions (D2).
Every requirement row keeps its `source_locators`; `traceability` explodes them into one row per locator, which is what makes
"requirement -> the passage that says it" checkable in the workbook. A row whose only locator is the literal `inferred`
appears in Traceability too, with locator_kind `inferred`, so an inferred requirement can never hide.
"""
import os, sys, json, re

from common import CORPUS_DIR

EMPTY_INV = {"corpus_notes": "", "sources": [], "epics": [], "coverage": {}, "claims": []}
INFERRED = "inferred"


def load(D, ROOT, INTERIM):
    def lj(path, default):
        return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default
    D["inv"] = D["inventory"] or dict(EMPTY_INV)
    D["set"] = D["cons"].get("SET")
    D["corpus"] = lj(os.path.join(CORPUS_DIR, "index.json"), {"sources": {}})


def available(D, name):
    if name in ("sources", "epics", "inv"): return bool(D["inv"].get("sources") or D["inv"].get("epics"))
    if name in ("requirements", "traceability", "crosscheck", "catalogue_gaps", "set"): return bool(D["set"])
    if name == "contradictions": return bool(D["scopes"])
    return None


def claim_scopes(D, selector):
    """`scopes_and_set` = every epic analysis plus the consolidated set (the D2 Claims sheet); D1 and SET are handled by the engine."""
    if selector == "scopes_and_set":
        out = [(n, D["scopes"][n].get("claims", [])) for n in sorted(D["scopes"])]
        if D["set"]: out.append(("SET", D["set"].get("claims", [])))
        return out
    return None


# label lookup is injected by build_excel at import time
_G = None
def _bind(label_fn):
    global _G; _G = label_fn
def g(v, ctx=None): return _G(v, ctx) if _G else v
def j(lst, sep="; "): return sep.join(str(x) for x in (lst or []))


def locator_kind(loc):
    loc = (loc or "").strip().strip("`")
    if not loc: return "empty"
    if loc.lower() == INFERRED: return "inferred"
    if re.match(r"^SRC-\d+", loc): return "corpus"
    if re.match(r"^HO-[\w-]+#", loc): return "handover"
    if re.match(r"^PS-7-\d+", loc): return "reference"
    if re.match(r"^https?://", loc): return "url"
    if loc.lower().startswith("visual"): return "visual"
    return "other"


def split_locator(loc):
    m = re.match(r"^(SRC-\d+)(?:@(\d+))?(?:#(\S+))?", (loc or "").strip().strip("`"))
    return (m.group(1), m.group(3) or "") if m else ("", "")


# ------------------------------------------------------------------ D1: sources and epics
def ds_sources(D):
    idx = (D["corpus"] or {}).get("sources", {}); rows = []; listed = set()
    for s in D["inv"].get("sources", []):
        e = idx.get(s.get("id"), {}); listed.add(s.get("id"))
        rows.append({"id": s.get("id", ""), "title": s.get("title", ""), "type": s.get("type", ""), "date": s.get("date", ""), "origin": s.get("origin", ""),
                     "quality": s.get("quality", ""), "covers": s.get("covers", ""), "notes": s.get("notes", ""),
                     "path": e.get("path", ""), "revision": e.get("revision", ""), "anchors": e.get("units", 0), "index_quality": e.get("quality", ""),
                     "cite_as": f"{s.get('id', '')}#<anchor>"})
    for sid, e in sorted(idx.items()):
        if sid in listed: continue
        rows.append({"id": sid, "title": e.get("title", ""), "type": e.get("type", ""), "date": "", "origin": "", "quality": e.get("quality", ""), "covers": "",
                     "notes": "indexed in the corpus, not listed in the source inventory", "path": e.get("path", ""), "revision": e.get("revision", ""),
                     "anchors": e.get("units", 0), "index_quality": e.get("quality", ""), "cite_as": f"{sid}#<anchor>"})
    return rows


def ds_epics(D):
    rows = []
    for x in D["inv"].get("epics", []):
        rows.append({"name": x.get("name", ""), "title": x.get("title", ""), "kind": x.get("kind", ""), "description": x.get("description", ""),
                     "sources": x.get("sources", []), "n_sources": len(x.get("sources") or []), "estimated_requirements": x.get("estimated_requirements", 0),
                     "depends_on": x.get("depends_on", []), "activation": x.get("activation", ""), "notes": x.get("notes", "")})
    return rows


# ------------------------------------------------------------------ D2: the consolidated set
def _reqs(D): return (D["set"] or {}).get("requirements", [])


def ds_requirements(D):
    rows = []
    for r in _reqs(D):
        locs = r.get("source_locators") or []
        rows.append({"req_id": r.get("req_id", ""), "epic": r.get("epic", ""), "type": r.get("type", ""), "title": r.get("title", ""), "description": r.get("description", ""),
                     "source_locators": locs, "n_locators": len([x for x in locs if locator_kind(x) not in ("inferred", "empty")]),
                     "priority": r.get("priority", ""), "release": r.get("release", ""), "acceptance_hint": r.get("acceptance_hint", ""),
                     "catalogue_ref": r.get("catalogue_ref"), "duplicates_of": r.get("duplicates_of"), "status": r.get("status", "")})
    return rows


def ds_traceability(D):
    idx = (D["corpus"] or {}).get("sources", {}); rows = []
    for r in _reqs(D):
        locs = r.get("source_locators") or [""]
        for loc in locs:
            sid, anchor = split_locator(loc); e = idx.get(sid, {})
            rows.append({"req_id": r.get("req_id", ""), "epic": r.get("epic", ""), "type": r.get("type", ""), "title": r.get("title", ""),
                         "priority": r.get("priority", ""), "status": r.get("status", ""), "locator": loc, "locator_kind": locator_kind(loc),
                         "source_id": sid, "anchor": anchor, "source_title": e.get("title", ""), "source_path": e.get("path", "")})
    return rows


def ds_crosscheck(D):
    return [{"functional_requirement": c.get("functional_requirement", ""), "technical_requirement": c.get("technical_requirement"),
             "relation": c.get("relation", ""), "note": c.get("note", "")} for c in (D["set"] or {}).get("crosscheck", [])]


def ds_catalogue_gaps(D):
    rows = []
    for c in (D["set"] or {}).get("catalogue_gaps", []):
        cov = c.get("covered_by") or []
        rows.append({"catalogue_id": c.get("catalogue_id", ""), "capability": c.get("capability", ""), "covered_by": cov,
                     "n_covered": len(cov), "decision": c.get("decision", "")})
    return rows


def ds_contradictions(D):
    rows = []
    for name in sorted(D["scopes"]):
        d = D["scopes"][name]
        for c in d.get("contradictions", []) or []:
            rows.append({"epic": name, "topic": c.get("topic", ""), "source_a": c.get("source_a", ""), "source_b": c.get("source_b", ""),
                         "what_differs": c.get("what_differs", ""), "proposed_resolution": c.get("proposed_resolution", "")})
    return rows


DATASETS = {"sources": ds_sources, "epics": ds_epics, "requirements": ds_requirements, "traceability": ds_traceability,
            "crosscheck": ds_crosscheck, "catalogue_gaps": ds_catalogue_gaps, "contradictions": ds_contradictions}
