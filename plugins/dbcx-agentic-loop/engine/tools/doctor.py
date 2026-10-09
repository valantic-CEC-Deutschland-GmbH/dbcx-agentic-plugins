#!/usr/bin/env python3
"""Read-only diagnostics for a portable dbcx package and run.

Usage: dbcx doctor [--json]
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DASHBOARD_PATH, PLUGIN, PROJECT_DIR, RUN, project, relp
from runtime import HARNESS, PROVIDER, package_commit, package_version, resolve_model


def exists(path: Path) -> dict[str, object]:
    return {"path": str(path), "exists": path.exists()}


def report() -> dict[str, object]:
    cfg = project()
    roles = (
        "orchestrator",
        "analyst",
        "analyst_light",
        "inventory",
        "consolidator",
        "critic_client",
        "critic_standard",
        "critic_standard_consolidation",
        "gate",
        "researcher",
        "progress",
        "postpass",
        "helper",
    )
    models = {role: resolve_model(cfg, role).to_dict() for role in roles}
    dashboard = {}
    if os.path.exists(DASHBOARD_PATH):
        try:
            dashboard = json.load(open(DASHBOARD_PATH, encoding="utf-8"))
        except Exception as exc:
            dashboard = {"error": str(exc)}
    plugin = Path(PLUGIN)
    agents_dir = plugin / "agents"
    overrides_failures = {}
    for module_path in sorted(set((Path(PROJECT_DIR) / "overrides").glob("*.py")) | set((Path(RUN) / "overrides").glob("*.py"))):
        # A run adapter that no longer imports (moved package, stale literal path) fails only when a scan runs.
        try:
            spec = importlib.util.spec_from_file_location(f"dbcx_doctor_{module_path.stem}", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - any import failure is the finding
            overrides_failures[relp(module_path, RUN)] = f"{type(exc).__name__}: {exc}"
    try:   # stale engagement overrides warn, they do not fail the doctor
        import override
        stale = override.check()
    except Exception as exc:  # noqa: BLE001
        stale = [{"id": "-", "target": "OVERRIDES.json", "reasons": [f"{type(exc).__name__}: {exc}"]}]
    try:   # own methods - information only (a changed plugin base, a newer library copy)
        import method as own_methods
        method_info = own_methods.doctor_lines()
    except Exception as exc:  # noqa: BLE001
        method_info = [f"own methods not checked ({type(exc).__name__}: {exc})"]
    # Hook files existing proves nothing about the harness RUNNING them: a whole session once went by without one
    # hook event. `hooks status` reads the declaration and the heartbeat the hook stamps into state/HOOKS.json.
    try:
        import hooks as hooks_tool
        hook_state = hooks_tool.status()
    except Exception as exc:  # noqa: BLE001
        hook_state = {"error": str(exc), "declared": {}, "heartbeat": {}, "verdict": []}
    declared_here = ((hook_state.get("declared") or {}).get(HARNESS) or {})
    heartbeat = (hook_state.get("heartbeat") or {}).get(HARNESS)
    checks = {
        "version": bool(package_version()),
        "overrides_importable": not overrides_failures,
        "run_json": (Path(RUN) / "run.json").exists(),
        "status": (Path(RUN) / "state/STATUS.json").exists(),
        "skill": (plugin / "skills/run/SKILL.md").exists(),
        "hooks": (plugin / "hooks/hooks.json").exists() and (plugin / "hooks/dbcx_hook.py").exists() and (plugin / "hooks/run.sh").exists(),
        "hooks_declared": bool(declared_here.get("declared")),
        "agents": agents_dir.exists() and len(list(agents_dir.glob("*.md"))) >= 9,
        "launcher_executable": os.access(plugin / "scripts/dbcx", os.X_OK),
        "dashboard_html": (plugin / "engine/dashboard/dashboard.html").exists(),
    }
    return {
        "ok": all(checks.values()),
        "package": {"root": str(plugin), "version": package_version(), "commit": package_commit()},
        "harness": HARNESS,
        "provider": PROVIDER,
        "run_root": RUN,
        "project_root": PROJECT_DIR,
        "models": models,
        "hooks": {
            "declaration": str(plugin / "hooks/hooks.json"),
            "declared_for_harness": hook_state.get("declared"),
            "heartbeat": heartbeat,
            "alive": bool(heartbeat),
            "verdict": hook_state.get("verdict"),
        },
        "agents": {"directory": str(agents_dir), "count": len(list(agents_dir.glob("*.md"))) if agents_dir.exists() else 0},
        "dependencies": {
            name: bool(importlib.util.find_spec(name))
            for name in ("openpyxl", "jsonschema", "yaml")
        },
        "dashboard": {
            "ready": checks["dashboard_html"],
            "url": dashboard.get("url"),
            "pid": dashboard.get("pid"),
        },
        "overrides": {"failures": overrides_failures, "stale": stale},
        "methods": method_info,
        "checks": checks,
    }


def main() -> None:
    args = sys.argv[1:]
    result = report()
    if "--json" in args:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"dbcx {result['package']['version']} | {result['harness']} / {result['provider']}")
        print(f"package: {result['package']['root']}" + (f" (commit {result['package']['commit'][:12]})" if result["package"].get("commit") else ""))
        print(f"run: {result['run_root']}")
        print(f"project: {result['project_root']}")
        print(f"hooks: {result['hooks']['declaration']}")
        for line in result["hooks"].get("verdict") or []:
            print(f"hooks: {line}")
        if not result["hooks"]["alive"]:
            print(f"hooks: WARNING no hook event from {result['harness']} recorded in state/HOOKS.json - the guardrails are files, not behaviour, until a heartbeat appears (`dbcx hooks status`)")
        print(f"agents: {result['agents']['count']} in {result['agents']['directory']}")
        for role, model in result["models"].items():
            print(f"model {role:32s} {model['profile']:18s} {model['model']:22s} effort={model['reasoning_effort']}")
        for key, value in result["checks"].items():
            print(f"{'OK' if value else 'FAIL':4s} {key}")
        for name, error in result["overrides"]["failures"].items():
            print(f"     {name}: {error}")
        for entry in result["overrides"]["stale"]:
            for reason in entry["reasons"]:
                print(f"overrides: WARNING stale {entry['id']} {entry['target']}: {reason} (`dbcx override check`)")
        for line in result["methods"]:
            print(f"methods: INFO {line}")
        print("dashboard:", result["dashboard"]["url"] or "ready, not started")
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
