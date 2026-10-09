"""Method hook of `dbcx requirements_to_json`: the pre-fill of the rows that
carry the input fields - `systems_prefill` for a systems_field row, `ends` and `prefill` for an interface row - resolved against
run.json systems (tfe_model.parse_systems, landscape_ids) and the landscape (state/landscape.json, `dbcx landscape_import`). A list
without the group keys is written unchanged. The rules (`dbcx build_excel --check`) are tfe_model.input_check.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tfe_model as TM


def enrich_requirements(doc, cfg):
    """fill the pre-fill fields in place -> message lines (printed by requirements_to_json)"""
    rows = doc.get("requirements") or []
    if not any("systems_named" in r or r.get("kind") == "interface" for r in rows): return []
    land = None; raw = TM.load_landscape(cfg.get("_run_dir"))
    if raw is not None: land = TM.normalise_landscape(raw)[0]
    un = TM.enrich(doc, TM.parse_systems(cfg)[0], land)
    out = [f"pre-fill: {sum(1 for r in rows if r.get('systems_prefill'))} row(s) name systems, {sum(1 for r in rows if r.get('kind') == 'interface')} interface row(s)"
           f" ({sum(len(r.get('prefill') or []) for r in rows)} end(s) at a system of the run){'' if land else ' - no landscape (dbcx landscape_import)'}"]
    if un["systems"]: out.append(f"WARNING systems_field names no system of the run: {TM._listing(un['systems'])}")
    if un["outside"]: out.append(f"WARNING interface ends at landscape systems not in the run (recorded for the architect): {TM._listing(un['outside'])}")
    if un["unknown"]: out.append(f"WARNING interface ends neither a system of the run nor of the landscape: {TM._listing(un['unknown'])}")
    return out
