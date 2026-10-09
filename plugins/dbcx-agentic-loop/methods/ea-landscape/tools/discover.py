#!/usr/bin/env python3
"""Scopes of the ea-landscape method: one scope per system of the landscape -> state/scopes.json
(consumed by `dbcx plan_waves`, `dbcx render`, `dbcx progress`).

Usage: dbcx discover [--from-run-json]

Source of truth is the VERIFIED inventory `analysis/inventory/landscape_inventory.json` (the Systems table of the D1 analysis).
Before the inventory exists, a provisional list may be given in run.json as `systems: [{name, category, depends_on, relevance, ...}]`
(or with --from-run-json to force it) so the wave plan can be sketched; re-run after the inventory has passed.

  group       = the system's category (erp | pim | crm | commerce | ...)
  depends_on  = the systems this system RECEIVES data from (inventory field `depends_on`, or `interfaces_from`), limited to known systems
  size        = the number of interfaces the documents mention for the system (`interfaces_mentioned`), else the number of upstream
                systems, else 1 - `plan_waves` uses it to order the waves and the engine to weight progress
  light       = relevance `peripheral`   (light pass: every section filled, essentials only)
  skip        = relevance `out-of-scope` (named in D1, not analysed)
"""
import os, sys, json

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, SCOPES_PATH, project, load_json, save_json, run_file, CLI

INV = "analysis/inventory/landscape_inventory.json"


def rows_from_inventory():
    ana = load_json(INV, None)
    if not ana:
        return None, None
    return ana.get("systems", []), INV


def rows_from_run():
    rf = run_file()
    rows = rf.get("systems") or []
    return (rows, "run.json systems (provisional - re-run after the inventory has passed)") if rows else (None, None)


def main():
    p = project()
    argv = sys.argv[1:]
    rows, src = (rows_from_run() if "--from-run-json" in argv else rows_from_inventory())
    if rows is None:
        rows, src = rows_from_run()
    if rows is None:
        sys.exit(f"missing {INV} (the Systems table of the D1 analysis) and no provisional `systems` list in run.json - "
                 f"run `{CLI} corpus index`, let the inventory analyst write {INV[:-5]}.md and convert it with `{CLI} md_to_json inventory {INV[:-5]}.md`")
    names = [r.get("name") for r in rows if r.get("name")]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        print(f"WARNING: the inventory lists these system names more than once: {', '.join(dupes)} - one row per system; the last row wins here")
    scopes = {}
    for r in rows:
        name = r.get("name")
        if not name:
            continue
        rel = r.get("relevance") or "core"
        deps = [d for d in (r.get("depends_on") or r.get("interfaces_from") or []) if d in names and d != name]
        try:
            n_if = int(r.get("interfaces_mentioned") or 0)
        except (TypeError, ValueError):
            n_if = 0
        size = n_if or len(deps) or 1
        light = rel == "peripheral"
        scopes[name] = {"group": r.get("category") or "other", "depends_on": deps, "size": size,
                        "light": True if light else False,
                        "light_reason": "inventory relevance = peripheral (named and described, examined in less depth)" if light else "",
                        "skip": rel == "out-of-scope",
                        "meta": {"CATEGORY": r.get("category") or "", "VENDOR / PRODUCT": r.get("vendor_product") or "",
                                 "LIFECYCLE": r.get("lifecycle") or "", "RELEVANCE": rel,
                                 "OWNER": r.get("owner") or "", "HOSTING": r.get("hosting") or ""}}
    out = {"noun": p.get("system", {}).get("noun", "System"), "method": "ea-landscape", "source": src, "scopes": scopes}
    save_json(SCOPES_PATH, out)
    n_light = sum(1 for s in scopes.values() if s["light"])
    n_skip = sum(1 for s in scopes.values() if s["skip"])
    print(f"{len(scopes)} scopes -> state/scopes.json from {src} "
          f"({len(scopes) - n_light - n_skip} core, {n_light} light, {n_skip} not analysed)")
    for n, s in sorted(scopes.items(), key=lambda kv: (kv[1]['group'], kv[0])):
        print(f"  {n:26s} {s['group']:12s} size={s['size']:<3d} receives from: {', '.join(s['depends_on']) or '-'}"
              + ("  [light]" if s["light"] else "") + ("  [not analysed]" if s["skip"] else ""))


if __name__ == "__main__":
    main()
