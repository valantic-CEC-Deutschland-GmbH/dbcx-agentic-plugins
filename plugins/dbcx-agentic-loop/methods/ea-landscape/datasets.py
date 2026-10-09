"""Row providers of the ea-landscape method for `dbcx build_excel` - pure functions over the loaded analysis JSON.

load(D, ROOT, INTERIM) adds the method's own aliases to the engine base dict (D["scopes"], D["inventory"], D["cons"], D["status"], D["client_questions"]):
  D["inv"]     the landscape inventory  (analysis/inventory/landscape_inventory.json, alias of D["inventory"])
  D["systems"] one entry per analysed system (alias of D["scopes"])
  D["flows"]   the FLOWS consolidation   (analysis/consolidated/FLOWS.json)
  D["target"]  the TARGET consolidation  (analysis/consolidated/TARGET.json)
  D["lean"]    profile lean (split none): no system analyses by design - D2 is built from the inventory's system rows (relevance other
               than out-of-scope, as discover would analyse them), its data objects and the FLOWS flows (one interface row per end); what
               only a system analysis provides is `not_assessed` (engine label) or a sheet in the spec's `not_assessed`
Nothing is aggregated here: counts, shares and matrices are Excel formulas in deliverables.<lang>.json over these detail rows.
"""
import os, re

def load(D, ROOT, INTERIM):
    D["inv"] = D["inventory"] or {"sources": [], "systems": [], "data_objects": [], "strategic_vision": [], "claims": []}
    D["systems"] = D["scopes"]
    D["flows"] = D["cons"].get("FLOWS")
    D["target"] = D["cons"].get("TARGET")
    D["_root"] = ROOT
    from common import project
    D["lean"] = project().get("split") == "none"

def available(D, name):
    if name == "inv": return bool(D["inv"].get("systems"))
    if name == "flows": return bool(D["flows"])
    if name == "target": return bool(D["target"])
    return None

def claim_scopes(D, selector):
    """`inventory_flows` = the inventory and FLOWS claims (the Claims sheet of the lean D2); every other selector is the engine's"""
    if selector == "inventory_flows": return [("D1", D["inv"].get("claims", []))] + ([("FLOWS", D["flows"].get("claims", []))] if D["flows"] else [])
    return None

# the label lookup of build_excel is injected at import time
_G = None
def _bind(label_fn):
    global _G
    _G = label_fn
def g(v, ctx=None): return _G(v, ctx) if _G else v
def j(lst, sep="; "): return sep.join(str(x) for x in (lst or []))

# ------------------------------------------------------------------ D1: the inventory
def ds_sources(D):
    return [{"id": s.get("id", ""), "title": s.get("title", ""), "type": s.get("type", ""), "date": s.get("date", ""),
             "origin": s.get("origin", ""), "quality": s.get("quality", ""), "covers": s.get("covers", "")} for s in D["inv"].get("sources", [])]

def ds_systems(D):
    rows = []; prof = _profiled(D)
    for s in D["inv"].get("systems", []):
        name = s.get("name", "")
        rows.append({"name": name, "category": s.get("category", ""), "vendor_product": s.get("vendor_product", ""), "version": s.get("version", ""),
                     "owner": s.get("owner", ""), "hosting": s.get("hosting", ""), "lifecycle": s.get("lifecycle", ""), "relevance": s.get("relevance", ""),
                     "description": s.get("description", ""), "depends_on": s.get("depends_on", []), "interfaces_mentioned": s.get("interfaces_mentioned", 0) or 0,
                     "analysed": name in D["systems"] or name in prof, "document": f"analysis/scopes/{name}.md" if name in D["systems"] else "", "sources": s.get("sources", [])})
    return rows

def ds_data_objects(D):
    return [{"name": o.get("name", ""), "description": o.get("description", ""), "claimed_master_systems": o.get("claimed_master_systems", []),
             "consumer_systems": o.get("consumer_systems", []), "sources": o.get("sources", [])} for o in D["inv"].get("data_objects", [])]

def ds_strategic_vision(D):
    return [{"topic": v.get("topic", ""), "statement": v.get("statement", ""), "source_locators": v.get("source_locators", [])} for v in D["inv"].get("strategic_vision", [])]

# ------------------------------------------------------------------ D2: the system profiles
def _profiled(D):
    """lean: {inventory system name: row} of the systems D2 profiles (relevance other than out-of-scope); full: {}"""
    return {s.get("name", ""): s for s in D["inv"].get("systems", []) if s.get("name") and s.get("relevance") != "out-of-scope"} if D.get("lean") else {}

def _per_system(D, key):
    for name in sorted(D["systems"]):
        for row in D["systems"][name].get(key, []) or []:
            yield name, row

def ds_profiles(D):
    if D.get("lean"):
        na = g("not_assessed")
        return [{"system": n, "purpose": s.get("description", ""), "vendor_product": s.get("vendor_product", ""), "version": s.get("version", ""), "owner": s.get("owner", ""),
                 "hosting": s.get("hosting", ""), "lifecycle": s.get("lifecycle", ""), "users": na, "summary": na, "sources": s.get("sources", []), "document": ""} for n, s in sorted(_profiled(D).items())]
    rows = []
    for name in sorted(D["systems"]):
        p = D["systems"][name].get("profile", {}) or {}
        rows.append({"system": name, "purpose": p.get("purpose", ""), "vendor_product": p.get("vendor_product", ""), "version": p.get("version", ""),
                     "owner": p.get("owner", ""), "hosting": p.get("hosting", ""), "lifecycle": p.get("lifecycle", ""), "users": p.get("users", ""),
                     "summary": (D["systems"][name].get("summary") or "").replace("\n", " "), "sources": p.get("sources", []), "document": f"analysis/scopes/{name}.md"})
    return rows

def ds_interfaces(D):
    if D.get("lean"):   # one row per end of a FLOWS flow, the flow id as the row id (an assumption on F-nnn marks both ends)
        prof = _profiled(D); rows = []
        for f in (D["flows"] or {}).get("flows", []):
            for n, c, d in ((f.get("from_system"), f.get("to_system"), "out"), (f.get("to_system"), f.get("from_system"), "in")):
                if n in prof: rows.append({"system": n, "id": f.get("id", ""), "counterpart": c or "", "direction": d, "protocol_style": f.get("style", ""), "frequency": f.get("frequency", ""),
                                           "data_objects": f.get("data_objects", []), "middleware": f.get("middleware", ""), "source_locators": f.get("evidence", []), "confidence": f.get("confidence", "")})
        return sorted(rows, key=lambda r: r["system"])
    return [{"system": n, "id": r.get("id", ""), "counterpart": r.get("counterpart", ""), "direction": r.get("direction", ""), "protocol_style": r.get("protocol_style", ""),
             "frequency": r.get("frequency", ""), "data_objects": r.get("data_objects", []), "middleware": r.get("middleware", ""),
             "source_locators": r.get("source_locators", []), "confidence": r.get("confidence", "")} for n, r in _per_system(D, "interfaces")]

def ds_data_ownership(D):
    if D.get("lean"):   # the inventory's claimed masters and consumers of each data object; the note is the object's description
        prof = _profiled(D)
        return sorted(({"system": n, "data_object": o.get("name", ""), "role": role, "note": o.get("description", ""), "source_locators": o.get("sources", [])}
                       for o in D["inv"].get("data_objects", []) for role, key in (("master", "claimed_master_systems"), ("consumer", "consumer_systems")) for n in o.get(key) or [] if n in prof),
                      key=lambda r: r["system"])
    return [{"system": n, "data_object": r.get("data_object", ""), "role": r.get("role", ""), "note": r.get("note", ""),
             "source_locators": r.get("source_locators", [])} for n, r in _per_system(D, "data_ownership")]

def ds_capabilities(D):
    return [{"system": n, "capability": r.get("capability", ""), "provided_by": r.get("provided_by", ""), "note": r.get("note", "")} for n, r in _per_system(D, "capabilities")]

def ds_pain_points(D):
    return [{"system": n, "topic": r.get("topic", ""), "finding": r.get("finding", ""), "impact": r.get("impact", ""),
             "source_locators": r.get("source_locators", []), "client_attention": bool(r.get("client_attention"))} for n, r in _per_system(D, "pain_points")]

def ds_constraints(D):
    return [{"system": n, "constraint": r.get("constraint", ""), "kind": r.get("kind", ""), "until": r.get("until", ""),
             "source_locators": r.get("source_locators", [])} for n, r in _per_system(D, "constraints")]

# ------------------------------------------------------------------ D3: flows and SSOT
def ds_flows(D):
    return [{"id": f.get("id", ""), "from_system": f.get("from_system", ""), "to_system": f.get("to_system", ""), "data_objects": f.get("data_objects", []),
             "style": f.get("style", ""), "frequency": f.get("frequency", ""), "middleware": f.get("middleware", ""), "evidence": f.get("evidence", []),
             "confidence": f.get("confidence", "")} for f in (D["flows"] or {}).get("flows", [])]

def ds_ssot_matrix(D):
    # evidence = the claim ids the conflicting claims cite plus the inventory's document locators for the data object (the verdict's basis)
    docs = {o.get("name"): o.get("sources", []) for o in D["inv"].get("data_objects", [])}
    return [{"data_object": s.get("data_object", ""), "master_system": s.get("master_system", ""), "conflicting_claims": s.get("conflicting_claims", []),
             "verdict": s.get("verdict", ""), "recommendation": s.get("recommendation", ""),
             "evidence": list(dict.fromkeys(re.findall(r"\bC-[\w.-]+?-\d{3}\b", " ".join(s.get("conflicting_claims", []))) + list(docs.get(s.get("data_object"), []))))}
            for s in (D["flows"] or {}).get("ssot_matrix", [])]

def ds_integration_debt(D):
    return [{"finding": d.get("finding", ""), "systems": d.get("systems", []), "impact": d.get("impact", ""),
             "recommendation": d.get("recommendation", "")} for d in (D["flows"] or {}).get("integration_debt", [])]

# ------------------------------------------------------------------ D4: target architecture
def ds_options(D):
    return [{"id": o.get("id", ""), "strategic_move": o.get("strategic_move", ""), "systems_affected": o.get("systems_affected", []),
             "flows_changed": o.get("flows_changed", []), "data_objects_re_mastered": o.get("data_objects_re_mastered", []), "rationale": o.get("rationale", ""),
             "risks": o.get("risks", ""), "prerequisites": o.get("prerequisites", ""), "phase": o.get("phase", ""),
             "recommendation": o.get("recommendation", ""), "confidence": o.get("confidence", "")} for o in (D["target"] or {}).get("options", [])]

def ds_roadmap(D):
    return [{"phase": r.get("phase", ""), "options": r.get("options", []), "outcome": r.get("outcome", ""),
             "dependencies": r.get("dependencies", [])} for r in (D["target"] or {}).get("roadmap", [])]

def ds_principles(D):
    return [{"principle": p.get("principle", ""), "source_locators": p.get("source_locators", [])} for p in (D["target"] or {}).get("principles", [])]

DATASETS = {"sources": ds_sources, "systems": ds_systems, "data_objects": ds_data_objects, "strategic_vision": ds_strategic_vision,
            "profiles": ds_profiles, "interfaces": ds_interfaces, "data_ownership": ds_data_ownership, "capabilities": ds_capabilities,
            "pain_points": ds_pain_points, "constraints": ds_constraints,
            "flows": ds_flows, "ssot_matrix": ds_ssot_matrix, "integration_debt": ds_integration_debt,
            "options": ds_options, "roadmap": ds_roadmap, "principles": ds_principles}
