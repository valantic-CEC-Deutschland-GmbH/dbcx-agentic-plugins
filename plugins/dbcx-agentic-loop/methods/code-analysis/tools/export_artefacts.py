#!/usr/bin/env python3
"""Write the two handover artefacts of the code-analysis method that are not a single consolidation file (method.json artefacts.produces):
  analysis/consolidated/D2.json               customization-depth: every unit analysis (analysis/units/*.json) merged, with its STATUS state and last scores
  analysis/consolidated/requirements_set.json requirements-set: the joint requirement list in the engine's requirements shape - the client's rows unchanged
                                              (extra.coverage_* from D3) plus the NR-nnn rows of D3 `new_requirements` (extra.origin = code-analysis)
Usage: dbcx export_artefacts [--allow-draft]
Run after the waves and the D3 consolidation, before `dbcx build_excel --all` / `dbcx handover export`. Refuses when D3 is a draft (unless --allow-draft: interim only).
The client's requirement rows are copied verbatim - nothing of the client's text is changed; the code-analysis findings live in `extra`.
"""
import os, sys, json, glob, time
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, STATUS_PATH, load_json, save_json, run_file

def main():
    allow_draft = "--allow-draft" in sys.argv
    st = load_json(STATUS_PATH, {"scopes": {}}); scopes = st.get("scopes", {})
    # ---- customization-depth
    units = {}
    for fp in sorted(glob.glob(os.path.join(ROOT, "analysis", "units", "*.json"))):
        name = os.path.basename(fp)[:-5]; d = load_json(fp, {})
        if not d: continue
        s = scopes.get(name, {})
        units[name] = {"unit": name, "scope_status": s.get("status"), "rounds": s.get("rounds"), "last_scores": s.get("last_scores"), "light": s.get("light"),
                       "classification": d.get("classification", {}), "summary": d.get("summary", ""),
                       **{k: d.get(k, []) for k in ("code_units", "data_model", "workflows", "scheduled_jobs", "data_scripts", "patched_standard", "requirements", "undocumented_behaviour", "api_features", "migration_concerns", "integrations", "deprecations")},
                       "claims": d.get("claims", [])}
    inv = load_json("analysis/inventory/inventory.json", {})
    d2 = {"artefact": "customization-depth", "run": run_file().get("run_name"), "written": time.strftime("%Y-%m-%d %H:%M"), "snapshot": (inv.get("platform") or {}).get("snapshot"), "units": units,
          "_readme": "one entry per analysed unit: classification (depth, disposition), code units, data model (data_class), patched standard behaviour, requirement contributions (beyond_requirement), undocumented behaviour, target API features, migration concerns, integrations, deprecations, claims. Cite rows as HO-customization-depth#<unit>/<table>/<key>."}
    os.makedirs(os.path.join(ROOT, "analysis", "consolidated"), exist_ok=True)
    save_json("analysis/consolidated/D2.json", d2)
    print(f"analysis/consolidated/D2.json: {len(units)} units ({sum(1 for u in units.values() if u['scope_status'] in ('final', 'passed'))} final/passed)")
    # ---- requirements-set
    req = load_json("state/requirements.json", None)
    if not req: sys.exit("state/requirements.json missing - run dbcx requirements_to_json first")
    d3 = load_json("analysis/consolidated/D3.json", None)
    if d3 and d3.get("status") == "draft" and not allow_draft: sys.exit("analysis/consolidated/D3.md is a draft - export after the D3 gauntlet passed (--allow-draft for an interim view)")
    cov = {c["req_id"]: c for c in (d3 or {}).get("coverage", [])}
    rows = []
    for r in req["requirements"]:
        c = cov.get(r["id"], {}); rr = json.loads(json.dumps(r)); ex = dict(rr.get("extra") or {})
        ex.update({"origin": "client-list", "coverage_verdict": c.get("verdict"), "coverage_today": c.get("today"), "coverage_target_standard": c.get("target_standard"), "coverage_target_standard_ref": c.get("target_standard_ref"),
                   "coverage_recommendation": c.get("recommendation"), "coverage_business_effect": c.get("business_effect"), "coverage_description_gap": c.get("description_gap"), "coverage_units": c.get("units", []), "coverage_claims": [e for e in c.get("evidence", []) if str(e).startswith("C-")]})
        rr["extra"] = ex; rows.append(rr)
    for n in (d3 or {}).get("new_requirements", []):
        rows.append({"group": "proposed", "id": n["id"], "epic": n.get("epic", ""), "title": n.get("title", ""), "description": n.get("description", ""), "acceptance_criteria": n.get("acceptance_criteria", ""), "exclusions": n.get("exclusions", ""),
                     "references": n.get("references", []), "phase": n.get("phase") or "Offen", "sources": [f"code-analysis:{u}" for u in n.get("units", [])], "priority": "",
                     "extra": {"origin": "code-analysis", "proposed_handling": n.get("proposed_handling"), "client_decision": "", "rationale": n.get("rationale", ""), "units": n.get("units", []), "confidence": n.get("confidence"), "evidence": n.get("evidence", [])}})
    groups = req.get("groups", [])
    groups = (groups + [{"group": "proposed", "note": "new requirements proposed from the code (NR-nnn) - client decision pending"}]) if isinstance(groups, list) else dict(groups, proposed="new requirements proposed from the code (NR-nnn) - client decision pending")
    out = {"source_file": req.get("source_file"), "artefact": "requirements-set", "run": run_file().get("run_name"), "written": time.strftime("%Y-%m-%d %H:%M"), "d3_status": (d3 or {}).get("status"),
           "requirements": rows, "legend": req.get("legend", {}), "groups": groups, "phase_values_in_scope": req.get("phase_values_in_scope", []),
           "_readme": "the client's rows are verbatim copies of state/requirements.json (extra.coverage_* added from D3); NR rows are proposals (extra.origin = code-analysis, extra.client_decision empty until the client decided). Cite as HO-requirements-set#<id>."}
    save_json("analysis/consolidated/requirements_set.json", out)
    nr = sum(1 for r in rows if r["extra"].get("origin") == "code-analysis")
    print(f"analysis/consolidated/requirements_set.json: {len(rows) - nr} client rows + {nr} proposed NR rows" + (" (D3 draft - interim)" if (d3 or {}).get("status") == "draft" else "") + ("" if d3 else " (no D3 yet - coverage fields empty)"))

if __name__ == "__main__":
    main()
