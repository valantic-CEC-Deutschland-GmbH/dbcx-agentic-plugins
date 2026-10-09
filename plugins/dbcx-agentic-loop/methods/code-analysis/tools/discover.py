#!/usr/bin/env python3
"""Scopes of the code-analysis method: one scope per custom unit, from analysis/inventory/inventory.json (dbcx scan_inventory) and the
D1 analysis's `activation` column when present -> state/scopes.json (consumed by dbcx plan_waves, render, progress).
Usage: dbcx discover
Light pass: D1 activation = dead, or scanner says not loaded anywhere (unless D1 says active), or code < scoring.light_pass_size LOC without new schema types and without business-process definitions
(a process definition can invert a unit's reading however small its code).
Size and code are MAINTAINED lines when the scan provides them (metrics_maintained / loc_maintained: generator output and unchanged vendor-template
copies excluded), so the wave plan, the light pass and the claim cap key on the code a person maintains; raw metrics otherwise.
Skipped: D1 activation = stub (D1 covers them).
"""
import os, sys, json
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, SCOPES_PATH, project, load_json, save_json

def main():
    p = project(); sc = p["scoring"]; light_size = sc.get("light_pass_size", sc.get("light_pass_loc", 1000))
    inv = load_json("analysis/inventory/inventory.json", None)
    if not inv: sys.exit("missing analysis/inventory/inventory.json - run dbcx scan_inventory <repo> first")
    activation = {}
    ana = load_json("analysis/inventory/inventory_analysis.json", {})
    if ana:
        for u in ana.get("units", []):
            if u.get("activation"): activation[u["name"]] = u["activation"]
    any_loaded = any(u.get("loaded_in") for u in inv["units"].values()); scopes = {}
    for k, u in inv["units"].items():
        m = u.get("metrics_maintained") or u.get("metrics", {}); code = m.get("code", 0); size = u.get("loc_maintained", sum(v for kk, v in m.items() if kk in ("code", "templates", "ts", "js")))
        light = None; reason = ""
        if activation.get(k) == "dead": light, reason = True, "D1 activation = dead"
        elif any_loaded and not u.get("loaded_in") and activation.get(k) != "active": light, reason = True, "scanner: not loaded anywhere"
        elif code < light_size and not u.get("schema_new_types") and not u.get("workflows"): light, reason = True, f"{'maintained ' if u.get('metrics_maintained') else ''}code {code} < {light_size} LOC, no new schema types, no process definitions"
        else: light = False
        scopes[k] = {"group": u.get("primary_category", "other"), "depends_on": u.get("requires_custom", []), "size": size, "light": light, "light_reason": reason, "skip": activation.get(k) == "stub",
                     "meta": {"activation": activation.get(k), "size_basis": "maintained" if "loc_maintained" in u else "raw", "size_raw": sum(v for kk, v in u.get("metrics", {}).items() if kk in ("code", "templates", "ts", "js"))}}
    out = {"noun": p.get("unit", {}).get("noun", "unit"), "method": "code-analysis", "source": "analysis/inventory/inventory.json" + (" + inventory_analysis.json activation" if activation else ""), "scopes": scopes}
    save_json(SCOPES_PATH, out)
    print(f"{len(scopes)} scopes -> state/scopes.json ({sum(1 for s in scopes.values() if s['light'])} light, {sum(1 for s in scopes.values() if s['skip'])} skipped as stub)" + ("" if activation else " - D1 activation not yet available; re-run after the inventory passed"))

if __name__ == "__main__":
    main()
