#!/usr/bin/env python3
"""dbcx <tool> [args] - dispatcher of the dbcx-agentic-loop plugin.
Resolves <tool> in engine/tools/, then in the active method's tools/ (methods/<m>/tools/), then in the knowledge packs' tools/.
Special: dbcx help | dbcx smoke [method|all] [tmpdir] | dbcx plugin-root | dbcx methods | dbcx which <tool>
Own methods: <engagement>/methods/<m>/ before the plugin's; $DBCX_METHOD_DIR = one method folder searched first (smoke of an own method).
Own methods: dbcx method list|new|card|check|confirm|generate|save|install (engine/tools/method.py; generate -> method_generate.py).
"""
import os, sys, subprocess
ENGINE = os.path.dirname(os.path.abspath(__file__)); PLUGIN = os.path.dirname(ENGINE); TOOLS = os.path.join(ENGINE, "tools")
sys.path.insert(0, TOOLS)

def candidates(name):
    out = [os.path.join(TOOLS, f"{name}.py")]
    try:
        import common
        m = common.method() if common.method_name() else None
        if m: out.append(os.path.join(m["_dir"], "tools", f"{name}.py"))
        if m and name == "discover" and str(m["scopes"].get("discover", "")).startswith("generic:"): out.append(os.path.join(TOOLS, "generic_discover.py"))
        if m:
            cfg = common.project()
            for pk in common.packs_of(cfg): out.append(os.path.join(pk["_dir"], "tools", f"{name}.py"))
    except SystemExit: pass
    except Exception: pass
    return out

def tool_env(env=None):
    """method code imports the engine by name - every tool gets the engine tools dir as DBCX_TOOLS and first on PYTHONPATH"""
    env = dict(os.environ if env is None else env); env["DBCX_TOOLS"] = TOOLS
    env["PYTHONPATH"] = os.pathsep.join([TOOLS] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p and p != TOOLS]); return env

def run(argv):
    """exec the tool; on Windows os.exec* returns to the caller at once (exit code 0, output after the prompt): wait for it instead"""
    if os.name == "nt": sys.exit(subprocess.call(argv, env=tool_env()))
    os.execvpe(argv[0], argv, tool_env())

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("help", "-h", "--help"):
        print(__doc__); print("engine tools:"); print("  " + "  ".join(sorted(f[:-3] for f in os.listdir(TOOLS) if f.endswith(".py") and f not in ("common.py", "validate.py"))))
        try:
            import common
            if common.method_name():
                m = common.method(); td = os.path.join(m["_dir"], "tools")
                if os.path.isdir(td): print(f"method tools ({m['name']}):"); print("  " + "  ".join(sorted(f[:-3] for f in os.listdir(td) if f.endswith(".py"))))
        except SystemExit: pass
        return
    cmd = a[0]
    if cmd == "plugin-root": print(PLUGIN); return
    if cmd == "methods":
        import common
        for n, e in common.method_index().items():   # own methods of this engagement first, with origin and version
            m = common.method(n); print(f"{n:24s} {e['source']:10s} {m.get('version', ''):8s} {m.get('display', '')}")
        for n, d in common.method_clashes().items(): print(f"{n:24s} REFUSED    own method in {d} reuses a plugin method's name")
        return
    if cmd == "smoke":   # the smoke scripts call python3: DBCX_PY makes them use this interpreter (Windows has no python3)
        os.environ["DBCX_PY"] = sys.executable.replace(os.sep, "/")
        if len(a) > 1 and not os.environ.get("DBCX_METHOD_DIR"):   # an own method of this engagement - its toy run lies outside the engagement
            import common
            e = common.method_index().get(a[1])
            if e and e["source"] == "engagement": os.environ["DBCX_METHOD_DIR"] = e["dir"]
        run(["bash", os.path.join(ENGINE, "smoke_test.sh").replace(os.sep, "/")] + a[1:])
    if cmd == "which":
        for c in candidates(a[1]):
            if os.path.exists(c): print(c); return
        sys.exit(f"unknown tool {a[1]}")
    for c in candidates(cmd):
        if os.path.exists(c): run([sys.executable, c] + a[1:])
    sys.exit(f"unknown tool {cmd} (dbcx help)")

if __name__ == "__main__": main()
