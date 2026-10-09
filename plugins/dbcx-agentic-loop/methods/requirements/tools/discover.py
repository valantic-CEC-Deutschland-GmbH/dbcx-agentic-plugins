#!/usr/bin/env python3
"""Scopes of the `requirements` method: one scope per EPIC, from the passed source inventory -> state/scopes.json
(consumed by dbcx plan_waves, render, progress, status).

Usage: dbcx discover [--epics analysis/inventory/source_inventory.json]
Source: the `Epics` table of analysis/inventory/source_inventory.json (name, title, kind, description, sources,
estimated_requirements, depends_on, activation). Fallback for an early run before the inventory exists: a list `epics`
in run.json (strings, or objects with the same fields) - the same shape, so the run can start before D1 passed and the
tool is re-run afterwards.

Waves: `wave_rule: dependency`, so an epic runs only when the epics it depends on are in an earlier or the same wave -
a technical epic names the functional epics it serves in `depends_on`, which is why the functional epics run first.
Light pass: estimated_requirements < scoring.light_pass_size (6 by default, so 5 rows or fewer).
Skipped: activation = out-of-scope (D1 carries them with the locator that excludes them).
Scope names are kebab-case ids: they become the file name (analysis/scopes/<name>.md) and the agent name (analyst-<name>),
so a name with spaces or capitals is normalised here and the original is kept as the epic title.
"""
import os, re, sys, json

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, SCOPES_PATH, project, load_json, save_json

INV = "analysis/inventory/source_inventory.json"


def slug(s):
    out = re.sub(r"[^a-z0-9]+", "-", str(s or "").strip().lower()).strip("-")
    return out or "epic"


def from_run_config(cfg):
    """run.json `epics`: ["checkout", ...] or [{"name": ..., "kind": ..., ...}, ...]."""
    out = []
    for e in cfg.get("epics") or []:
        out.append({"name": e, "title": e, "kind": "functional", "description": "", "sources": [], "estimated_requirements": 0, "depends_on": [], "activation": "active"} if isinstance(e, str) else dict(e))
    return out


def main():
    a = sys.argv[1:]; p = project(); sc = p["scoring"]; light_size = sc.get("light_pass_size", 6)
    path = a[a.index("--epics") + 1] if "--epics" in a else INV
    ana = load_json(path, {}) or {}
    epics = ana.get("epics") or []; src = path
    if not epics:
        epics = from_run_config(p); src = "run.json epics (the source inventory has no Epics table yet)"
    if not epics:
        sys.exit(f"no epics: neither {path} (Epics table) nor run.json `epics` names one - run the inventory analyst first "
                 f"(dbcx render brief inventory --out), convert with dbcx md_to_json inventory analysis/inventory/source_inventory.md, then dbcx discover")
    known = {slug(e.get("name")) for e in epics}
    scopes = {}; renamed = []; unknown_deps = []
    for e in epics:
        name = slug(e.get("name")); title = e.get("title") or e.get("name") or name
        if name != str(e.get("name") or ""): renamed.append(f"{e.get('name')} -> {name}")
        size = int(e.get("estimated_requirements") or 0)
        deps = [slug(d) for d in (e.get("depends_on") or []) if slug(d) != name]
        unknown_deps += [f"{name} -> {d}" for d in deps if d not in known]
        out_of_scope = str(e.get("activation") or "active") == "out-of-scope"
        light = (not out_of_scope) and size > 0 and size < light_size
        scopes[name] = {"group": e.get("kind") or "functional", "depends_on": deps, "size": size,
                        "light": light, "light_reason": (f"{size} expected requirements < {light_size}" if light else ""),
                        "skip": out_of_scope,
                        # meta keys in CAPITALS become CONTEXT rows of the epic's brief; group and size are printed by the engine already
                        "meta": {"EPIC": title, "EPIC COVERS": (e.get("description") or "")[:400],
                                 "SOURCES": ", ".join(e.get("sources") or []), "IN SCOPE": e.get("activation") or "active"}}
    out = {"noun": p.get("unit", {}).get("noun", "Epic"), "method": "requirements", "source": src, "scopes": scopes}
    save_json(SCOPES_PATH, out)
    n_light = sum(1 for s in scopes.values() if s["light"]); n_skip = sum(1 for s in scopes.values() if s["skip"])
    print(f"{len(scopes)} epics -> state/scopes.json ({n_light} light pass, {n_skip} out of scope) from {src}")
    for g in sorted({s["group"] for s in scopes.values()}):
        print(f"  {g}: " + ", ".join(f"{k}[{v['size']}]" for k, v in sorted(scopes.items()) if v["group"] == g))
    if renamed: print("  normalised epic names (kebab-case scope ids):", "; ".join(renamed))
    if unknown_deps: print("  WARNING depends_on names no epic of this inventory (ignored by plan_waves):", "; ".join(unknown_deps))
    if src.startswith("run.json"): print("  NOTE: the epic structure came from run.json - re-run `dbcx discover` after the inventory passed its gauntlet")


if __name__ == "__main__":
    main()
