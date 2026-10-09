#!/usr/bin/env python3
"""Are the dbcx guardrails actually running? 

Usage:
  dbcx hooks status [--json]             the declaration (hooks/hooks.json) and the heartbeat state/HOOKS.json that the hook
                                         stamps on every event - the only proof that the harness RUNS the hook

Why this exists: a plugin hook is only active when the harness knows the file - Claude Code discovers hooks/hooks.json in
the plugin root. Whether it fires is not visible from inside a session, so the hook writes a heartbeat and this tool reads it.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, PLUGIN
from runtime import HARNESS, package_version

HOOKS_JSON = os.path.join(PLUGIN, "hooks", "hooks.json")

def jload(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def declared():
    """Where the harness is TOLD about the hook file."""
    return {"claude": {"declaration": os.path.relpath(HOOKS_JSON, PLUGIN), "declared": os.path.exists(HOOKS_JSON), "how": "plugin root hooks/hooks.json (auto-discovered)"}}

def heartbeat():
    return (jload(os.path.join(ROOT, "state", "HOOKS.json"), {}) or {}).get("harnesses", {})

def status():
    dec = declared(); hb = heartbeat(); verdict = []
    beat = hb.get(HARNESS)
    if beat: verdict.append(f"{HARNESS}: hook ALIVE - last event {beat.get('last_event_at')} ({sum(beat.get('events', {}).values())} events, tools {', '.join(sorted(beat.get('tools', {}))) or '-'}) from {beat.get('plugin_root')} {beat.get('version', '')}")
    else: verdict.append(f"{HARNESS}: NO hook event recorded for this run <- guardrails, in_flight and delivery tests are NOT enforced until this changes")
    return {"harness": HARNESS, "package": {"root": PLUGIN, "version": package_version()}, "declared": dec, "heartbeat": hb, "verdict": verdict}

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("--help", "-h", "help"): print(__doc__); return
    if a[0] == "status":
        r = status()
        if "--json" in a: print(json.dumps(r, indent=1, ensure_ascii=False)); return
        print(f"dbcx {r['package']['version']} hooks | harness {r['harness']} | package {r['package']['root']}")
        for k, v in r["declared"].items():
            print(f"  {k:7s} declared={'yes' if v['declared'] else 'NO ':3s} {v['how']}")
        for line in r["verdict"]: print("  " + line)
        return
    sys.exit(__doc__)

if __name__ == "__main__":
    main()
