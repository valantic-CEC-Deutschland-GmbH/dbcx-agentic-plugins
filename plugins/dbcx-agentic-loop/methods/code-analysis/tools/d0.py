#!/usr/bin/env python3
"""D0 'findings requiring client attention' (optional deliverable, CP-12): collect the candidates, curate, build.

Usage: dbcx d0 collect            -> analysis/consolidated/D0.json: rows flagged client_attention=yes in the unit analyses (Patched standard
                                     behaviour, Migration concerns), critics' estate observations (analysis/consolidated/estate_observations.json),
                                     plus rows already curated in D0.json (kept, matched by id). New rows get severity "medium" and settled=false
                                     until the orchestrator curates them (edit D0.json: finding, severity high|medium|low, recommendation,
                                     settled true|false, settles_by, claims, evidence) - every finding must rest on PASSED claims.
       dbcx d0 list
The findings always reach docs/FINAL_REPORT.md (orchestrator); the workbook is built only when deliverables.D0.enabled (dbcx build_excel D0).
"""
import os, sys, json, glob, time, re
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, load_json, save_json

OUT = "analysis/consolidated/D0.json"

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cur = load_json(OUT, {"status": "draft", "findings": []})
    if a[0] == "list":
        for f in cur["findings"]: print(f"{f['id']:8s} {f.get('severity', '?'):7s} {'settled' if f.get('settled') else 'OPEN   '} {', '.join(f.get('units', [])):30s} {f['finding'][:100]}")
        print(f"{len(cur['findings'])} findings"); return
    if a[0] != "collect": sys.exit(__doc__)
    have = {f.get("source_key") for f in cur["findings"]}; n = len(cur["findings"]); added = 0
    def add(key, units, finding, rec, evidence, claims, src):
        nonlocal n, added
        if key in have: return
        n += 1; added += 1; have.add(key)
        cur["findings"].append({"id": f"IA-{n:03d}", "units": units, "finding": finding, "severity": "medium", "recommendation": rec or "", "settled": False, "settles_by": "", "claims": claims, "evidence": evidence, "source": src, "source_key": key, "added": time.strftime("%Y-%m-%d")})
    for fp in sorted(glob.glob(os.path.join(ROOT, "analysis", "units", "*.json"))):
        d = load_json(fp, {}); u = d.get("unit", os.path.basename(fp)[:-5]); st = load_json("state/STATUS.json", {"scopes": {}}).get("scopes", {}).get(u, {})
        if st.get("status") not in ("final", "passed", "passed-rework-ordered", "failed-gauntlet"): continue
        for r in d.get("migration_concerns", []):
            if r.get("client_attention"):
                cl = [c["id"] for c in d.get("claims", []) if r["finding"][:40].lower() in c["statement"].lower()]
                add(f"{u}:concern:{r['finding'][:60]}", [u], r["finding"], r.get("recommendation"), r.get("evidence", []), cl, "unit analysis / migration concern")
        for r in d.get("patched_standard", []):
            if r.get("client_attention"):
                cl = [c["id"] for c in d.get("claims", []) if r["what"][:40].lower() in c["statement"].lower()]
                add(f"{u}:patched:{r['what'][:60]}", [u], f"{r['what']}: {r.get('custom_behaviour', '')}".strip(": "), "", [r["file"] + (":" + r["lines"] if r.get("lines") else "")], cl, "unit analysis / patched standard behaviour")
    for e in load_json("analysis/consolidated/estate_observations.json", []):
        add(f"estate:{e['scope']}:{e['text'][:60]}", [e["scope"]] if e["scope"] not in ("D1", "D3", "D4") else [], e["text"], "", [], [], f"critic {e['critic']} on {e['scope']} round {e['round']} (estate observation - verify before publishing)")
    save_json(OUT, cur); print(f"D0: {added} candidate(s) added, {len(cur['findings'])} total -> {OUT}. Curate severity / recommendation / settles_by / claims; every row rests on PASSED claims; then `dbcx build_excel D0` (if enabled) and list them in FINAL_REPORT.")

if __name__ == "__main__":
    main()
