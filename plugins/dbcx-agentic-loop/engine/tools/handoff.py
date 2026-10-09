#!/usr/bin/env python3
"""Check, prepare, and accept a verified dbcx session handoff (another session, machine or colleague).

Usage:
  dbcx handoff check [--json]
  dbcx handoff prepare [--orphan-and-rehydrate]
  dbcx handoff accept
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CONTROL_PATH, INBOX_PATH, PLUGIN, RUN, STATUS_PATH, load_json, project, scope_critics
from runtime import package_commit, package_version


ROOT = Path(RUN)
HANDOFF = ROOT / "state" / "HANDOFF.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inbox_pending() -> int:
    if not Path(INBOX_PATH).exists():
        return 0
    entries = []
    for line in Path(INBOX_PATH).read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return sum(1 for entry in entries if not entry.get("processed"))


def round_audit(status: dict) -> tuple[list[dict], list[str]]:
    try: critics = project()["scoring"]["critics"]   # the live configuration (per-pack standard critics follow run.json options)
    except SystemExit: critics = status.get("critics", ["client", "standard"])
    rounds: list[dict] = []
    errors: list[str] = []
    root = ROOT / "analysis" / "gauntlet"
    if not root.exists():
        return rounds, errors
    for snapshot in sorted(root.glob("*/claims-round*.json")):
        match = re.search(r"claims-round(\d+)\.json$", snapshot.name)
        if not match:
            continue
        number = int(match.group(1)); directory = snapshot.parent
        own = critics
        try:   # a scope with one critic or none (scoring.phase_critics)
            cfg = project()
            own = scope_critics(directory.name, cfg)
        except SystemExit: pass
        result_path = directory / f"round{number}-result.json"
        if result_path.exists(): own = list(json.loads(result_path.read_text(encoding="utf-8")).get("critics") or own)   # an aggregated round's own critics (a topic critic follows the register)
        files = {critic: directory / f"round{number}-{critic}.json" for critic in own}
        present = [critic for critic, path in files.items() if path.exists()]
        entry = {"scope": directory.name, "round": number, "critics": present, "result": result_path.exists()}
        rounds.append(entry)
        if present and len(present) != len(own):
            errors.append(f"{directory.name} round {number}: incomplete critic set ({', '.join(present)})")
        if len(present) == len(own) and not result_path.exists():
            errors.append(f"{directory.name} round {number}: every critic delivered but round is not aggregated")
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            for critic, expected in (result.get("checksums") or {}).items():
                path = files.get(critic)
                if not path or not path.exists() or sha256(path) != expected:
                    errors.append(f"{directory.name} round {number}: checksum mismatch for {critic}")
    return rounds, errors


def audit() -> dict[str, object]:
    status = load_json(STATUS_PATH, {})
    rounds, errors = round_audit(status)
    active = [entry for entry in status.get("in_flight", []) if not entry.get("delivered")]
    conversion_pending = []
    for entry in active:
        if "md_to_json" in str(entry.get("check_cmd", "")):
            outputs = [ROOT / path for path in entry.get("output_files", [])]
            if outputs and all(path.exists() for path in outputs):
                conversion_pending.append(entry.get("agent"))
    if active:
        errors.append(f"{len(active)} agent(s) still in flight")
    if conversion_pending:
        errors.append("agent output awaits delivery conversion: " + ", ".join(str(value) for value in conversion_pending))
    control = load_json(CONTROL_PATH, {}) if Path(CONTROL_PATH).exists() else {}
    result = {
        "clean": not errors,
        "package_root": PLUGIN,
        "package_version": package_version(),
        "package_commit": package_commit(),
        "run_root": RUN,
        "rounds": rounds,
        "errors": errors,
        "in_flight": active,
        "conversion_pending": conversion_pending,
        "inbox_unprocessed": inbox_pending(),
        "dashboard_control": control,
        "status_sha256": sha256(Path(STATUS_PATH)) if Path(STATUS_PATH).exists() else None,
    }
    return result


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def prepare(orphan: bool) -> None:
    result = audit()
    hard_errors = list(result["errors"])
    if orphan and hard_errors:
        unsafe = [entry for entry in result["in_flight"] if not entry.get("output_files") or not all((ROOT / path).exists() for path in entry.get("output_files", []))]
        if unsafe:
            raise SystemExit("REFUSED: orphan-and-rehydrate requires every in-flight agent output to exist safely on disk")
        hard_errors = [error for error in hard_errors if "in flight" not in error and "awaits delivery conversion" not in error]
    if hard_errors:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit("REFUSED: handoff is not clean")
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    state = {
        **result,
        "prepared_at": stamp,
        "orphan_and_rehydrate": orphan,
        "rehydrate": [entry for entry in result["in_flight"]] if orphan else [],
        "accepted_at": None,
    }
    write_json(HANDOFF, state)
    package = os.path.relpath(PLUGIN, RUN)
    resume = f"""# dbcx session resume

Prepared at: {stamp}
Portable package: `{package}`
Run: `.`
Status checksum: `{result['status_sha256']}`

Run exactly:

```sh
{package}/bin/dbcx status verify
{package}/bin/dbcx handoff accept
{package}/bin/dbcx status next
```

Unprocessed inbox entries: {result['inbox_unprocessed']}
Agents to rehydrate: {', '.join(str(entry.get('agent')) for entry in state['rehydrate']) or 'none'}
"""
    (ROOT / "docs").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "RESUME.md").write_text(resume, encoding="utf-8")
    print("prepared the handoff; wrote state/HANDOFF.json and docs/RESUME.md")


def accept() -> None:
    if not HANDOFF.exists():
        raise SystemExit("REFUSED: no prepared state/HANDOFF.json")
    state = json.loads(HANDOFF.read_text(encoding="utf-8"))
    if state.get("accepted_at"):
        print(f"already accepted at {state['accepted_at']} (idempotent)")
        return
    current = sha256(Path(STATUS_PATH)) if Path(STATUS_PATH).exists() else None
    if current != state.get("status_sha256"):
        raise SystemExit("REFUSED: STATUS changed after handoff preparation; prepare again from the source session")
    state["accepted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_json(HANDOFF, state)
    subprocess.run([sys.executable, str(Path(__file__).with_name("status.py")), "verify"], cwd=RUN, check=False)
    subprocess.run([sys.executable, str(Path(__file__).with_name("status.py")), "next"], cwd=RUN, check=False)
    print(f"accepted the handoff at {state['accepted_at']}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    command = args[0]
    if command == "check":
        result = audit()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(0 if result["clean"] else 1)
    if command == "prepare":
        prepare("--orphan-and-rehydrate" in args)
        return
    if command == "accept":
        accept()
        return
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
