"""Row providers of the code-analysis method for dbcx build_excel (pure functions over the loaded JSON).
load(D, ROOT, INTERIM) adds the method's own inputs to the engine's base dict (D["scopes"], D["inventory"], D["cons"], D["req"], D["status"]):
  D["inv"] = scan (analysis/inventory/inventory.json), D["ana"] = inventory analysis (alias of D["inventory"]), D["units"] = alias of D["scopes"],
  D["d3"], D["d4"] = consolidations, D["d0"] = client-attention findings (analysis/consolidated/D0.json).
Since method 0.6: disposition / disposition_rationale (depth), data_class / source_of_truth (data_model), beyond_requirement (req_contributions),
today / target_standard / recommendation / business_effect / description_gap (coverage), new_requirements, joint_requirements, integrations (D4), snapshot rows (platform).
Since method 0.7: coverage rows carry the client's requirement text verbatim (one D3 sheet `Requirements`), frontend_features (compact D4 feature rows keyed by primary_requirement, for the D3 roll-up formulas),
features sorted by primary_requirement, migration_tasks (merged concerns + blockers of 0.6; interim fallback from the units' Migration concerns). req_contributions / joint_requirements stay available for internal use and the artefacts but are not client sheets any more.
Customer edition: every verdict row carries `evidence` for the Grundlage derivation - its own locators plus the ids of
the claims that target the row (`D3/Coverage:<req id>`, `D4/Features:<F id>`, `D4/Tasks:<MT id>`, `D4/Integrations:<system>`, `D4/Content:<type>`, a unit's `D2/Depth`),
which build_excel expands to their locators; `key_statement` (Kernaussage) on coverage, features and depth rows - the analysis value, or the editor's wording
from analysis/summaries/key_statements.json ({"<row key>": "<sentence>"}, wins when present); patched rows carry security_relevant / consequence /
`locator` (file:lines); security_operations = the D2 sheet Sicherheit_und_Betrieb (see ds_security_operations); migration tasks carry `rank` within their
impact class; req_sources = the source abbreviations of the client's requirement list (legend of state/requirements.json)."""
import os, json, glob

def load(D, ROOT, INTERIM):
    def lj(rel, default):
        p = os.path.join(ROOT, rel)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default
    D["inv"] = lj("analysis/inventory/inventory.json", {"units": {}, "dependency_edges": [], "deprecation_hits": [], "platform": {}})
    D["ana"] = D["inventory"] or {"units": [], "platform": {}, "packages": [], "deprecations": [], "dependency_notes": [], "claims": []}
    D["units"] = D["scopes"]; D["d3"] = D["cons"].get("D3"); D["d4"] = D["cons"].get("D4"); D["d0"] = lj("analysis/consolidated/D0.json", {}) or None
    D["ks"] = lj("analysis/summaries/key_statements.json", {}) or {}
    if D["ks"] and not D.get("_ks_checked"):   # build note: an editor sidecar key that names no row (typo, removed row) is never shown
        D["_ks_checked"] = True
        rows = {r["id"] for r in D["req"].get("requirements", [])} | {f.get("feature_id") for f in (D["d4"] or {}).get("features", [])} | set(D["scopes"])
        lost = sorted(k for k in D["ks"] if not k.startswith("_") and k not in rows)
        if lost: print(f"note: analysis/summaries/key_statements.json: {len(lost)} key(s) match no requirement, feature or unit row and are not shown: {', '.join(lost[:8])}")

def available(D, name):
    if name == "inv": return bool(D["inv"]["units"])
    if name == "d0": return bool(D["d0"])
    if name == "d3": return bool(D["d3"])
    if name == "d4": return bool(D["d4"])
    return None

def claim_scopes(D, selector):
    if selector == "D1": return [("D1", D["ana"].get("claims", []))]
    if selector in ("D3", "D4"): return [(selector, (D[selector.lower()] or {}).get("claims", []))]
    return None

def g(v, ctx=None):   # label lookup is injected by build_excel at import time (see _bind)
    return _G(v, ctx) if _G else v
def j(lst, sep="; "): return sep.join(str(x) for x in (lst or []))
_G = None
def _bind(label_fn):
    global _G; _G = label_fn

def _claims_for(claims, sheet, key=None):
    """ids of the claims whose target is `sheet` (whole sheet) or `sheet:<key>` - build_excel expands them to their own locators"""
    return [c["id"] for c in claims or [] if c.get("id") and (c.get("target") or "").split(":")[0].strip() == sheet and (key is None or (c.get("target") or "").partition(":")[2].strip() == str(key))]
def _ev(*parts):
    out = []
    for p in parts:
        for x in ([p] if isinstance(p, str) else (p or [])):
            if x and x not in out: out.append(x)
    return out
def _ks(D, key, row):
    """Kernaussage: the editor's sidecar wording wins, else the analysis field"""
    return (D.get("ks") or {}).get(str(key)) or (row or {}).get("key_statement") or ""
def _locator(file, lines):
    """file + simple line range -> one repository locator (file:12-30); anything else stays the file (lines keep their own column)"""
    import re
    return f"{file}:{lines}" if file and ";" not in str(file) and re.fullmatch(r"\d+(?:-\d+)?", str(lines or "").strip()) else (file or "")

def _customer_facing():
    """unit categories whose code customers experience (run config unit.customer_facing_categories, default frontend + api)"""
    try:
        from common import project
        return set((project().get("unit") or {}).get("customer_facing_categories") or ["frontend", "api"])
    except Exception: return {"frontend", "api"}
_SIZE = ("code", "templates", "js", "ts")
def _loc(m): return sum(int((m or {}).get(k) or 0) for k in _SIZE)
def ds_units(D):
    """Ladezustand = the scanner's resolved activation (activation_resolved.state: active | declared-not-provisioned | not-decidable | inactive),
    else the D1 analysis `activation`; loc_maintained = customer-maintained code + templates + JS + TS without tests, generated code and template
    copies (scanner field; fallback = the raw sum); overrides = resolved overrides of standard beans only (override_candidates_resolved), never
    the raw candidate count; loaded_in = the scanner's evidence of what loads the unit ('not-determined' when the adapter cannot tell)."""
    ana = {u["name"]: u for u in D["ana"].get("units", [])}; rows = []; cf = _customer_facing()   # activation feeds the cleaned-LOC formula of the sheet
    for n in sorted(D["inv"]["units"]):
        e = D["inv"]["units"][n]; a = ana.get(n, {}); m = e["metrics"]; ar = e.get("activation_resolved") or {}
        ovr = e.get("override_candidates_resolved"); tpl = (e.get("template") or {}).get("template")
        byc = e.get("deprecation_hits_by_class") or {}
        rows.append({"name": n, "path": e["path"], "category": a.get("category", e["primary_category"]), "sub_categories": [g(x) for x in a.get("sub_categories", e["categories"][1:])], "description": a.get("description", e.get("description", "")), "template_origin": a.get("template_origin") or (g("_skeleton") if tpl == "yempty" else tpl), "notes": a.get("notes", ""), "evidence": [e["evidence"]], "activation": ar.get("state") or a.get("activation") or "",
                     "loaded_in": [str(x).replace("required by ", g("_required_by") + " ", 1) for x in e.get("loaded_in") or []] or ([] if ar else ["not-determined"]),
                     "loc_maintained": e["loc_maintained"] if isinstance(e.get("loc_maintained"), int) else _loc(m), "loc_generated": _loc(e.get("metrics_generated")), "loc_template_copy": _loc(e.get("metrics_template_copy")),
                     "overrides_standard": ovr.get("overrides-standard", 0) if isinstance(ovr, dict) else "not-resolved",
                     "dep_hits_other": sum(v for k, v in byc.items() if k != "src"),
                     "reach": "_customer_facing" if a.get("category", e["primary_category"]) in cf else "_internal",
                     "requires_custom": e["requires_custom"], "requires_standard": e["requires_standard"], "requires_unknown": e["requires_unknown"], "requires_unknown_n": len(e["requires_unknown"]),
                     "code": m.get("code", 0), "code_test": m.get("code_test", 0), "templates": m.get("templates", 0), "js": m.get("js", 0), "ts": m.get("ts", 0), "config": m.get("config", 0), "data_scripts": m.get("data_scripts", 0), "css": m.get("css", 0),
                     "frontend_entry_points": e.get("frontend_entry_points", 0), "api_entry_points": e.get("api_entry_points", 0), "schema_new_types": e.get("schema_new_types", 0), "schema_extended_types": e.get("schema_extended_types", 0), "schema_attributes_on_extended_types": e.get("schema_attributes_on_extended_types", 0), "schema_relations": e.get("schema_relations", 0), "schema_enums": e.get("schema_enums", 0),
                     "di_definitions": e.get("di_definitions", 0), "workflows": e.get("workflows", []), "workflows_n": len(e.get("workflows", [])), "content_custom_component_types": e.get("content_custom_component_types", []), "integration_hits": [f"{k}:{v}" for k, v in (e.get("integration_hits") or {}).items()]})
    return rows
def ds_dependencies(D):
    rows = [{"from": d["from"], "to": d["to"], "to_kind": d["to_kind"], "type": d["type"], "note": "", "evidence": d["evidence"]} for d in D["inv"]["dependency_edges"]]
    for dn in D["ana"].get("dependency_notes", []): rows.append({"from": dn.get("from"), "to": dn.get("to"), "to_kind": "custom" if dn.get("to") in D["inv"]["units"] else "standard", "type": dn.get("kind") or "other", "note": dn.get("note", ""), "evidence": dn.get("evidence", "")})
    return rows
def ds_packages(D):
    seen, rows = set(), []
    for a in D["ana"].get("packages", []): seen.add(a["name"]); rows.append({"name": a["name"], "kind": a["kind"], "installed_on": a.get("installed_on", []), "source": a.get("source", ""), "notes": a.get("notes", "")})
    for n, e in D["inv"]["units"].items():
        for t in e.get("third_party_required", []):
            if t not in seen: seen.add(t); rows.append({"name": t, "kind": "third-party", "installed_on": [n], "source": e["evidence"], "notes": g("_found_by_scan")})
    return rows
def ds_platform(D):
    pl = D["ana"].get("platform", {}); rows = []
    for key in ("version", "runtime", "hosting", "frontend_technology", "database", "search", "notes"):   # no confidence row in any edition (K7)
        v = pl.get(key); rows.append({"key": key, "value": v if v not in (None, "") else "-", "evidence": pl.get("evidence") or []})
    scan_pl = D["inv"].get("platform", {}) or {}
    rows.append({"key": "standard_code_in_repo", "value": g(scan_pl.get("standard_code_in_repo")), "evidence": scan_pl.get("config_files") or []})
    snap = scan_pl.get("snapshot") or {}
    if snap: rows.append({"key": "snapshot", "value": f"{snap.get('commit', '')} ({snap.get('date', '')}, {snap.get('branch', '')})".strip(), "evidence": snap.get("evidence", "git rev-parse HEAD")})
    for f, h in (scan_pl.get("version_hints") or {}).items(): rows.append({"key": "version_hint", "value": j(h), "evidence": f})
    for name, ev in ((scan_pl.get("active_extensions") or {}).get("declared_not_provisioned") or {}).items():
        rows.append({"key": "declared_not_provisioned", "value": name, "evidence": ev})
    # scanner notes (scan_pl["notes"]) describe the scan, not the shop: they stay in analysis/inventory/scan_log.txt
    return rows
def ds_deprecations(D):
    ver = {d["id"]: d for d in D["ana"].get("deprecations", [])}; rows = []
    for h in D["inv"]["deprecation_hits"]:
        if h.get("path_class", "src") != "src": continue   # comment / config / lib / report / generated / test hits are no runtime finding (Einheiten counts them)
        v = ver.get(h["id"], {}); rows.append({"id": h["id"], "title": h["title"], "unit": h["unit"], "file": h["file"], "line": h["line"], "snippet": h["snippet"], "since": v.get("since") or h["since"], "replacement": v.get("replacement") or h["replacement"], "status": v.get("status", "unverified"), "verified_against": v.get("verified_against", ""), "locator": _locator(h["file"], h["line"])})
    for d in D["ana"].get("deprecations", []):
        if not any(r["id"] == d["id"] for r in rows): rows.append({"id": d["id"], "title": d["what"], "unit": j(d.get("units")), "file": j(d.get("evidence")), "line": "", "snippet": "", "since": d.get("since", ""), "replacement": d.get("replacement", ""), "status": d["status"], "verified_against": d.get("verified_against", ""), "locator": d.get("evidence") or []})
    return rows
def ds_code_units(D):
    return [{"unit": n, "fqn": c["fqn"], "kind": c["kind"], "standard_counterpart": c.get("standard_counterpart"), "purpose": c.get("purpose", ""), "count": c.get("count", 1) if c["kind"] == "aggregate" else 1, "file": c["file"], "lines": c.get("lines", "")} for n, d in sorted(D["units"].items()) for c in d.get("code_units", [])]
def ds_data_model(D):
    return [{"unit": n, "type": t["type"], "kind": t["kind"], "base": t.get("base"), "attributes_added": t.get("attributes_added", 0), "attributes": t.get("attributes", []), "purpose": t.get("purpose", ""), "standard_alternative": t.get("standard_alternative"), "data_class": t.get("data_class", ""), "source_of_truth": t.get("source_of_truth"), "file": t["file"]} for n, d in sorted(D["units"].items()) for t in d.get("data_model", [])]
def ds_workflows_jobs_scripts(D):
    rows = []
    for n, d in sorted(D["units"].items()):
        for w in d.get("workflows", []): rows.append({"unit": n, "group": "workflow", "name": w["name"], "kind": w["kind"], "counterpart": w.get("standard_counterpart"), "purpose": w.get("purpose", ""), "files": [w["file"]]})
        for s in d.get("scheduled_jobs", []): rows.append({"unit": n, "group": "job", "name": s.get("name"), "kind": "new", "counterpart": s.get("job_class"), "purpose": s.get("purpose", ""), "files": [s.get("file", "")]})
        for s in d.get("data_scripts", []): rows.append({"unit": n, "group": "data_script", "name": s["area"], "kind": s["kind"], "counterpart": "", "purpose": s.get("notes", ""), "files": s.get("files", [])})
    return rows
def _security(p):
    """security_relevant: yes/no as analysed; a row written before the field existed (key absent) is 'not-assessed', never a silent 'no'"""
    return "not-assessed" if "security_relevant" not in p else bool(p["security_relevant"])
def ds_patched(D):
    return [{"unit": n, "what": p["what"], "how": p["how"], "standard_behaviour": p.get("standard_behaviour", ""), "custom_behaviour": p.get("custom_behaviour", ""), "risk_for_upgrade": p.get("risk_for_upgrade", ""),
             "security_relevant": _security(p), "consequence": p.get("consequence") or "", "file": p["file"], "lines": p.get("lines", ""), "locator": _locator(p["file"], p.get("lines"))} for n, d in sorted(D["units"].items()) for p in d.get("patched_standard", [])]
_SEV = {"high": 0, "medium": 1, "low": 2}
SB_MAX = 25   # Sicherheit_und_Betrieb shows the top rows by severity; the rest stay on their detail sheets (KPI / overview count them)
def _curated(f):
    """a D0.json row the orchestrator curated: `curated: true`, or any curation mark (settled, settles_by, a severity other than the collect default)"""
    return bool(f) and bool(f.get("curated") or f.get("settled") or (f.get("settles_by") or "").strip() or f.get("severity") not in (None, "", "medium"))
def _security_rows(D):
    """all explicitly flagged findings, sorted severity (high first), then unit - see ds_security_operations"""
    d0 = {f.get("source_key"): f for f in ((D.get("d0") or {}).get("findings") or []) if f.get("source_key")}; used = set(); rows = []
    def add(key, units, kind, finding, severity, consequence, rec, origin, evidence):
        c = d0.get(key) if _curated(d0.get(key)) else {}; used.add(key)
        rows.append({"kind": kind, "units": c.get("units") or units, "finding": c.get("finding") or finding, "severity": c.get("severity") or severity,
                     "consequence": c.get("consequence") or consequence, "recommendation": c.get("recommendation") or rec, "origin": origin, "evidence": _ev(evidence, c.get("claims"), c.get("evidence"))})
    for n, d in sorted(D["units"].items()):
        for p in d.get("patched_standard", []):
            key = f"{n}:patched:{p['what'][:60]}"
            if p.get("security_relevant") or p.get("client_attention") or _curated(d0.get(key)):
                add(key, [n], "security" if p.get("security_relevant") else "operations", f"{p['what']}: {p.get('custom_behaviour', '')}".strip(": "),
                    p.get("risk_for_upgrade") or "medium", p.get("consequence") or "", "", "patched", [_locator(p["file"], p.get("lines"))])
        for c in d.get("migration_concerns", []):
            key = f"{n}:concern:{c['finding'][:60]}"; sec = c.get("topic") in ("security", "auth")
            if c.get("client_attention") or _curated(d0.get(key)):   # the security/auth topic sets kind and severity, it never adds a row by itself
                add(key, [n], "security" if sec else "operations", c["finding"],
                    "high" if sec and c.get("impact") in ("blocker", "major") else ("low" if c.get("impact") == "minor" else "medium"),
                    c.get("consequence") or "", c.get("recommendation", ""), "concern", c.get("evidence", []))
    for key, f in d0.items():
        if key in used or not _curated(f) or not f.get("claims") or not f.get("evidence"): continue
        rows.append({"kind": f.get("kind") or "operations", "units": f.get("units", []), "finding": f.get("finding", ""), "severity": f.get("severity") or "medium", "consequence": f.get("consequence") or "",
                     "recommendation": f.get("recommendation", ""), "origin": "finding", "evidence": _ev(f.get("evidence"), f.get("claims"))})
    rows.sort(key=lambda r: (_SEV.get(r["severity"], 9), ", ".join(r["units"]), 0 if r["kind"] == "security" else 1))
    for i, r in enumerate(rows, 1): r["id"] = f"SB-{i:03d}"
    return rows
def ds_security_operations(D):
    """D2 sheet Sicherheit_und_Betrieb (on by default, independent of D0): findings about today's shop that need the client's attention.
    A row only when it is explicitly flagged: patched standard behaviour with security_relevant or client_attention, a migration concern with
    client_attention, or a curated analysis/consolidated/D0.json row (`dbcx d0 collect` + curation). The curated D0 row with the same source_key
    overrides finding / severity / recommendation / consequence; a curated D0 row without a unit row needs claims and evidence. Uncurated severity:
    patched -> upgrade risk; concern -> high for a security/auth topic with blocker/major impact, low for minor impact, else medium.
    Sorted severity (high first), then unit; the first SB_MAX rows are shown, the count of the rest is the KPI / overview row `secops_more`."""
    return _security_rows(D)[:SB_MAX]
def extra_context(D):
    """{x:...} values for the spec: secops_flagged = all flagged security/operations findings (the sheet shows the top SB_MAX)"""
    return {"secops_flagged": len(_security_rows(D))}
def ds_depth(D):
    rows = []
    for n, d in sorted(D["units"].items()):
        c = d["classification"]; inv = D["inv"]["units"].get(n, {})
        rows.append({"unit": n, "category": inv.get("primary_category", ""), "depth": c["depth"], "rationale": c["rationale"], "confidence": c["confidence"], "migration_relevance": c.get("migration_relevance", ""),
                     "disposition": c.get("disposition", ""), "disposition_rationale": c.get("disposition_rationale", ""), "key_statement": _ks(D, n, c), "evidence": _claims_for(d.get("claims"), "D2/Depth"),
                     "concerns_major": sum(1 for h in d.get("migration_concerns", []) if h["impact"] in ("blocker", "major")), "open_questions": sum(1 for q in d.get("open_questions", []) if q["status"] == "open"), "document": f"analysis/units/{n}.md"})
    return rows
def ds_requirements(D):
    return [{"id": r["id"], "group": r["group"], "epic": r.get("epic", ""), "title": r.get("title", ""), "description": r.get("description", ""), "acceptance_criteria": r.get("acceptance_criteria", ""), "exclusions": r.get("exclusions", ""), "references": r.get("references", []), "phase": r.get("phase", ""), "sources": r.get("sources", []), "priority": r.get("priority", "")} for r in D["req"]["requirements"]]
def ds_req_contributions(D):
    return [{"req_id": c["req_id"], "unit": n, "contribution": c["contribution"], "rationale": c.get("rationale", ""), "beyond_requirement": c.get("beyond_requirement"), "standard_alternative": c.get("standard_alternative"), "standard_alternative_confidence": c.get("standard_alternative_confidence"), "evidence": c.get("evidence", [])} for n, d in sorted(D["units"].items()) for c in d.get("requirements", [])]
def ds_coverage(D):
    cov = {c["req_id"]: c for c in (D["d3"] or {}).get("coverage", [])}; rows = []
    for r in D["req"]["requirements"]:
        c = cov.get(r["id"], {})
        rows.append({"req_id": r["id"], "key_statement": _ks(D, r["id"], c), "group": r["group"], "epic": r.get("epic", ""), "title": r.get("title", ""), "phase": r.get("phase", ""), "verdict": c.get("verdict", "NOT-ASSESSED"),
                     "description": r.get("description", ""), "acceptance_criteria": r.get("acceptance_criteria", ""), "exclusions": r.get("exclusions", ""), "references": r.get("references", []), "sources": r.get("sources", []), "priority": r.get("priority", ""),
                     "today": c.get("today", "NOT-ASSESSED" if not c else ""), "target_standard": c.get("target_standard", "NOT-ASSESSED" if not c else ""), "target_standard_ref": c.get("target_standard_ref", ""), "target_standard_confidence": c.get("target_standard_confidence"),
                     "recommendation": c.get("recommendation", "NOT-ASSESSED" if not c else ""), "business_effect": c.get("business_effect", ""), "description_gap": c.get("description_gap") or "",
                     "units": c.get("units", []), "current_state_note": c.get("current_state_note", ""), "standard_alternative_flag": bool(c.get("standard_alternative_flag")), "standard_alternative": c.get("standard_alternative"), "standard_alternative_confidence": c.get("standard_alternative_confidence"), "rationale": c.get("rationale", ""), "confidence": c.get("confidence", ""), "evidence": _ev(c.get("evidence"), _claims_for((D["d3"] or {}).get("claims"), "D3/Coverage", r["id"]))})
    return rows
def ds_req_sources(D):
    """source abbreviations of the client's requirement list with their document (legend sheet of the workbook, requirements_mapping.json `legend_sheet`);
    an abbreviation the legend does not explain gets the generic wording."""
    used = []
    for r in D["req"]["requirements"]:
        for s in r.get("sources") or []:
            if s and s not in used: used.append(s)
    leg = D["req"].get("legend") or {}
    return [{"abbreviation": s, "document": leg.get(s) or g("_source_unexplained")} for s in used]
def ds_new_requirements(D):
    rows = []
    for n in (D["d3"] or {}).get("new_requirements", []):
        rows.append({"id": n["id"], "epic": n.get("epic", ""), "title": n.get("title", ""), "description": n.get("description", ""), "acceptance_criteria": n.get("acceptance_criteria", ""), "exclusions": n.get("exclusions", ""), "references": n.get("references", []), "phase": n.get("phase") or "Offen",
                     "units": n.get("units", []), "rationale": n.get("rationale", ""), "proposed_handling": n.get("proposed_handling", ""), "confidence": n.get("confidence", ""), "evidence": _ev(n.get("evidence"), _claims_for((D["d3"] or {}).get("claims"), "D3/New_requirements", n["id"]))})
    return rows
def ds_joint_requirements(D):
    rows = [dict(r, origin="client-list") for r in ds_requirements(D)]
    for n in ds_new_requirements(D):
        rows.append({"id": n["id"], "origin": "code-analysis", "group": "", "epic": n["epic"], "title": n["title"], "description": n["description"], "acceptance_criteria": n["acceptance_criteria"], "exclusions": n["exclusions"], "references": n["references"], "phase": n["phase"], "sources": [f"analysis:{u}" for u in n["units"]], "priority": ""})
    return rows
def _req_order(D):
    ids = [r["id"] for r in D["req"]["requirements"]] + [n["id"] for n in (D["d3"] or {}).get("new_requirements", [])]
    return {rid: i for i, rid in enumerate(ids)}
def _by_req(D, key):
    o = _req_order(D); return lambda x: (o.get(x.get(key) or "", len(o)), str(x.get(key) or ""), str(x.get("feature_id") or x.get("id") or ""))
def ds_features(D):
    cl = (D["d4"] or {}).get("claims")
    rows = [dict(f, primary_requirement=f.get("primary_requirement") or "", key_statement=_ks(D, f.get("feature_id"), f), evidence=_ev(f.get("evidence"), _claims_for(cl, "D4/Features", f.get("feature_id")))) for f in (D["d4"] or {}).get("features", [])]
    return sorted(rows, key=_by_req(D, "primary_requirement"))
def ds_frontend_features(D):
    """Compact feature rows for the requirement workbook (D3): the roll-up formulas of the Requirements sheet count over this sheet; the full detail stays in D4."""
    return [{"primary_requirement": f["primary_requirement"], "feature_id": f.get("feature_id", ""), "feature": f.get("feature", ""), "units": f.get("units", []), "target_api_coverage": f.get("target_api_coverage", ""), "custom_api_needed_flag": bool((f.get("custom_api_needed") or "").strip()),
             "content_dependency": f.get("content_dependency", ""), "state_dependency": f.get("state_dependency", ""), "verdict": f.get("verdict", ""), "related_requirements": f.get("related_requirements", []), "evidence": f.get("evidence", [])} for f in ds_features(D)]
_IMPACT = {"blocker": 0, "major": 1, "minor": 2}; _SEQ = {"before": 0, "during": 1, "after": 2, None: 3, "": 3}
def ds_migration_tasks(D):
    rows = [dict(t, sequence=t.get("sequence") or "") for t in (D["d4"] or {}).get("migration_tasks", [])]
    if not rows and not D["d4"]:
        # before the D4 consolidation exists (interim builds): the units' own concerns as provisional tasks, one per unit x concern
        for n, d in sorted(D["units"].items()):
            for i, c in enumerate(d.get("migration_concerns", []), 1):
                if c.get("impact") == "none": continue
                rows.append({"id": f"MT-{n}-{i:02d}", "topic": c.get("topic", "other"), "task": c.get("recommendation", ""), "finding": c.get("finding", ""), "affected_requirements": c.get("affected_requirements", []), "units": [n], "impact": c.get("impact", "minor"), "sequence": "", "depends_on": [], "evidence": c.get("evidence", [])})
    cl = (D["d4"] or {}).get("claims")
    for t in rows:
        t["evidence"] = _ev(t.get("evidence"), _claims_for(cl, "D4/Tasks", t.get("id"))); t["depends_on"] = list(t.get("depends_on") or []) or ["none"]
    # rank within the impact class: the consolidator's `rank` (1 = first); a class without ranks gets the documented order -
    # sequence (before / during / after), then tasks others depend on, then the number of affected requirements (desc), then id
    needed = {d for t in rows for d in t["depends_on"]}
    order = lambda t: (_SEQ.get(t.get("sequence"), 3), 0 if t.get("id") in needed else 1, -len(t.get("affected_requirements") or []), str(t.get("id")))
    for imp in {t.get("impact") for t in rows}:
        cls = [t for t in rows if t.get("impact") == imp]
        if any(isinstance(t.get("rank"), int) and t["rank"] > 0 for t in cls): continue
        todo, done, ids = sorted(cls, key=order), [], {t.get("id") for t in cls}
        while todo:   # a task never ranks before a prerequisite of the same impact class
            nxt = next((t for t in todo if all(d in done or d not in ids for d in t["depends_on"])), todo[0])
            todo.remove(nxt); done.append(nxt.get("id")); nxt["rank"] = len(done)
    return sorted(rows, key=lambda t: (_IMPACT.get(t.get("impact"), 9), t["rank"] if isinstance(t.get("rank"), int) and t["rank"] > 0 else 999, str(t.get("id"))))
def ds_content_components(D):
    """usages: a listed component type is in use, so an empty or 0 count means 'not counted', never 'unused'"""
    cl = (D["d4"] or {}).get("claims")
    return [dict(c, usages=c["usages"] if isinstance(c.get("usages"), int) and c["usages"] > 0 else (int(c["usages"]) if str(c.get("usages") or "").strip().isdigit() and int(c["usages"]) > 0 else "not-counted"),
                 evidence=_ev(c.get("evidence"), _claims_for(cl, "D4/Content", c.get("component_type")))) for c in (D["d4"] or {}).get("content_components", [])]
def ds_integrations(D):
    cl = (D["d4"] or {}).get("claims")
    rows = [dict(i, evidence=_ev(i.get("evidence"), _claims_for(cl, "D4/Integrations", i.get("system")))) for i in (D["d4"] or {}).get("integrations", [])]
    if rows or D["d4"]: return rows
    # before the D4 consolidation exists (interim builds): the units' own rows, one per unit x system x direction
    for n, d in sorted(D["units"].items()):
        for i in d.get("integrations", []): rows.append(dict(i, units=[n], target_impact="", related_requirements=[]))
    return rows
def ds_d0(D): return [dict(f, evidence=_ev(f.get("evidence"), f.get("claims"))) for f in (D["d0"] or {}).get("findings", [])]
DATASETS = {"d0": ds_d0, "units": ds_units, "dependencies": ds_dependencies, "packages": ds_packages, "platform": ds_platform, "deprecations": ds_deprecations, "code_units": ds_code_units, "data_model": ds_data_model, "workflows_jobs_scripts": ds_workflows_jobs_scripts, "patched": ds_patched, "security_operations": ds_security_operations, "depth": ds_depth,
            "requirements": ds_requirements, "req_contributions": ds_req_contributions, "coverage": ds_coverage, "req_sources": ds_req_sources, "new_requirements": ds_new_requirements, "joint_requirements": ds_joint_requirements,
            "features": ds_features, "frontend_features": ds_frontend_features, "content_components": ds_content_components, "integrations": ds_integrations, "migration_tasks": ds_migration_tasks}
