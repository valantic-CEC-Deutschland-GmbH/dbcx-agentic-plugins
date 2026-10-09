#!/usr/bin/env python3
"""Shared helpers of the dbcx-agentic-loop engine: roots, layered configuration, method packs, knowledge packs, spec, roles.

Roots
  PLUGIN    the plugin folder (this file lives in <plugin>/engine/tools/)
  ENGINE    <plugin>/engine     SPEC <engine>/spec     DEFAULTS <engine>/defaults
  METHODS   <plugin>/methods/<method>/       (method packs: what a scope is, kinds, deliverables, phases, briefs, datasets, tools)
            own methods: <project>/methods/<method>/ searched first, and $DBCX_METHOD_DIR (one method folder) before that
  KNOWLEDGE <plugin>/knowledge/<kind>/<name>/ (knowledge packs: platforms, catalogues, reference-architectures)
  RUN       the run folder: $DBCX_RUN, or --run <dir>, or the nearest parent of the cwd containing run.json, else the cwd
  PROJECT   the engagement folder: $DBCX_PROJECT, or the nearest parent of RUN containing engagement.json, else RUN
            (shared, slowly growing assets live here: input/, corpus/, reference/, handover/; every run keeps its own state/analysis/deliverables)

Configuration layers (later wins): engine/defaults/run.defaults.json <- methods/<m>/method.json "defaults" <- method.json
"profiles"[<profile>] (run.json / engagement.json `profile`, default full) <- knowledge packs
(platform packs: as_source / as_target config; other packs: "config") <- <project>/engagement.json <- <project>/overrides/settings.json
<- <run>/run.json <- <run>/overrides/settings.json
Knowledge layers: engine/defaults/knowledge.skeleton.json <- source platform pack knowledge.json <- target platform pack (target_* keys)
<- other packs' knowledge.json <- <project>/overrides/knowledge.json <- <run>/overrides/knowledge.json <- <run>/state/derived_knowledge.json (lists unioned)
Override files (knowledge.json, labels.<lang>.json, deliverables.<lang>.json, snippets.json, adapter.py, briefs/<role>.md, settings.json) exist at
engagement level (<project>/overrides/, written by `dbcx override`, with provenance) and run level (<run>/overrides/); the run's win.
"""
import json, os, re, sys, importlib.util, tempfile
try: import fcntl
except ImportError: fcntl = None   # no advisory locking on this platform; the temp-file + os.replace half of M1 still holds

_DISCOVERED_TOOLS = os.path.dirname(os.path.abspath(__file__))
_DISCOVERED_ENGINE = os.path.dirname(_DISCOVERED_TOOLS); _DISCOVERED_PLUGIN = os.path.dirname(_DISCOVERED_ENGINE)
_ENV_PLUGIN = next((os.environ.get(name) for name in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT") if os.environ.get(name)), None)
PLUGIN = os.path.abspath(os.path.expanduser(_ENV_PLUGIN)) if _ENV_PLUGIN and os.path.exists(os.path.join(os.path.expanduser(_ENV_PLUGIN), "engine", "tools", "common.py")) else _DISCOVERED_PLUGIN
ENGINE = os.path.join(PLUGIN, "engine"); TOOLS = os.path.join(ENGINE, "tools")
SPEC = os.path.join(ENGINE, "spec"); DEFAULTS = os.path.join(ENGINE, "defaults")
METHODS = os.path.join(PLUGIN, "methods"); KNOWLEDGE = os.path.join(PLUGIN, "knowledge")
DBCX_HOME = os.path.expanduser(os.environ.get("DBCX_HOME") or "~/.dbcx")   # same rule as engine/tools/setup.py
LIBRARY_METHODS_DIR = os.path.join(DBCX_HOME, "methods")   # the personal library - a source (`dbcx method install`), never a lookup root
PLACEHOLDER_RE = re.compile(r"<<PLACEHOLDER[^>]*>>|<<[A-Z_ ]{3,}>>|\bTODO:")
RUN_FILE = "run.json"; PROJECT_FILE = "engagement.json"
LAUNCHER = os.path.join(PLUGIN, "scripts", "dbcx"); AGENT_PREFIX = "dbcx-agentic-loop:"
CLI = 'bash "' + LAUNCHER.replace(os.sep, "/") + '"'   # every command the engine prints runs without PATH and without the executable bit (a zip upload may drop it); forward slashes: Git Bash runs C:/... too
_CLI_WORDS = None
def cli_text(text):
    """`dbcx <tool>` in text written for agents (templates, method hints, hook messages) -> `<CLI> <tool>`; prose (`the dbcx loop`) stays."""
    global _CLI_WORDS
    if _CLI_WORDS is None:
        dirs = [TOOLS] + [os.path.join(e["dir"], "tools") for e in method_index().values()] + [os.path.join(KNOWLEDGE, k, n, "tools") for k in (os.listdir(KNOWLEDGE) if os.path.isdir(KNOWLEDGE) else []) if os.path.isdir(os.path.join(KNOWLEDGE, k)) for n in os.listdir(os.path.join(KNOWLEDGE, k))]
        words = {f[:-3] for d in dirs if os.path.isdir(d) for f in os.listdir(d) if f.endswith(".py")} | {"help", "smoke", "plugin-root", "methods", "which", "<tool>", "..."}
        _CLI_WORDS = re.compile(r"(?<![\w/.\-\"])dbcx(?= (?:" + "|".join(sorted(map(re.escape, words), key=len, reverse=True)) + r")(?![\w-]))")
    return _CLI_WORDS.sub(lambda m: CLI, text) if text else text
def run_cli(cmd, **kw):
    """subprocess.run of a rendered command line (a brief's CHECK): a `[bash] <launcher> <tool> ...` line runs as this Python + engine/dbcx.py without
    a shell (Windows: shell=True is cmd.exe, which cannot run the bash launcher; a bare `dbcx` of an older run needs no PATH either)."""
    import shlex, shutil, subprocess
    if os.name == "nt": cmd = cmd.replace("\\", "/")   # Windows paths in a CHECK: shlex would eat the backslashes
    try: argv = shlex.split(cmd)
    except ValueError: argv = []
    if argv[:1] == ["bash"] and len(argv) > 1 and os.path.basename(argv[1]) == "dbcx": argv = argv[1:]
    if argv and os.path.basename(argv[0]) == "dbcx" and not any(t in ("|", "&&", "||", ";", ">", ">>") for t in argv):
        return subprocess.run([sys.executable, os.path.join(ENGINE, "dbcx.py")] + argv[1:], **kw)
    if os.name == "nt" and shutil.which("bash"): return subprocess.run(["bash", "-c", cmd], **kw)   # `test -s`, `&&`: POSIX shell syntax, not cmd.exe
    return subprocess.run(cmd, shell=True, **kw)

def replace_file(src, dst):
    """os.replace that waits out Windows' PermissionError while a reader (hook, dashboard, virus scanner) has dst open (~1 s)"""
    for i in range(20):
        try: return os.replace(src, dst)
        except PermissionError:
            if i == 19 or os.name != "nt": raise
            import time; time.sleep(0.05)

def fwd(path):
    """a path as the engine renders and stores it: forward slashes on every OS (Git Bash and shlex eat backslashes; stored state stays portable)"""
    return path.replace(os.sep, "/") if os.sep != "/" and isinstance(path, str) else path
def relp(path, start=None): return fwd(os.path.relpath(path, start) if start is not None else os.path.relpath(path))

def _up(start, marker):
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, marker)): return cur
        parent = os.path.dirname(cur)
        if parent == cur: return None
        cur = parent

def _find_run():
    if os.environ.get("DBCX_RUN"): return os.path.abspath(os.environ["DBCX_RUN"])
    for flag in ("--run", "--project"):
        if flag in sys.argv:
            i = sys.argv.index(flag); p = os.path.abspath(sys.argv[i + 1]); del sys.argv[i:i + 2]; return p
    return _up(os.getcwd(), RUN_FILE) or os.getcwd()
RUN = _find_run()

def _find_project():
    if os.environ.get("DBCX_PROJECT"): return os.path.abspath(os.environ["DBCX_PROJECT"])
    return _up(RUN, PROJECT_FILE) or RUN
PROJECT_DIR = _find_project()
PROJECT = RUN   # legacy alias: tools written for the single-folder layout treat the RUN as their root

def P(*rel): return os.path.join(RUN, *rel)
def PP(*rel): return os.path.join(PROJECT_DIR, *rel)
def resolve_root(spec_path):
    """'@project/x' -> <project>/x ; absolute stays ; else <run>/x."""
    if not spec_path: return spec_path
    if spec_path.startswith("@project/"): return PP(spec_path[len("@project/"):])
    return spec_path if os.path.isabs(spec_path) else P(spec_path)

STATUS_PATH = P("state", "STATUS.json"); WAVES_PATH = P("state", "WAVES.json"); SCOPES_PATH = P("state", "scopes.json")
REQ_PATH = P("state", "requirements.json"); DERIVED_PATH = P("state", "derived_knowledge.json")
TEMPLATES_DIR = P("templates"); SCHEMAS_DIR = P("schemas")
QUESTIONS_PATH = P("state", "QUESTIONS.json"); KNOWLEDGE_PATH = P("state", "KNOWLEDGE.json"); INBOX_PATH = P("state", "INBOX.jsonl"); CONTROL_PATH = P("state", "CONTROL.json"); DASHBOARD_PATH = P("state", "DASHBOARD.json")
QUESTION_KINDS = ("client_question", "scope_question", "assumption", "trade_off")
REF_DIR = PP("reference"); CORPUS_DIR = PP("corpus"); HANDOVER_DIR = PP("handover"); INPUT_DIR = PP("input")
WORK_DIR = P("work")   # team-only artefacts (interim builds, review notes) - never client deliverables

def read_json(path, default=None):
    if not os.path.exists(path):
        if default is not None: return default
        raise SystemExit(f"missing {path}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
def load_json(rel, default=None): return read_json(rel if os.path.isabs(rel) else P(rel), default)

def atomic_save_json(path, data):
    """Write JSON so a reader never sees a half-written file and two concurrent writers (a spawn
    hook and an orchestrator `status set`, two SubagentStop delivery tests) never interleave: an
    fcntl lock on a sidecar `.lock` serializes writers, the payload goes to a temp file in the same
    directory first, and `os.replace` swaps it in atomically; the previous content is kept as one
    `.bak` (concurrent hook writes would otherwise corrupt STATUS.json)."""
    d = os.path.dirname(path) or "."; os.makedirs(d, exist_ok=True)
    lock_fh = open(path + ".lock", "a+") if fcntl else None
    try:
        if lock_fh: fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        if os.path.exists(path):
            try:
                with open(path, "rb") as src, open(path + ".bak", "wb") as bak: bak.write(src.read())
            except OSError: pass
        fd, tmp = tempfile.mkstemp(prefix=".tmp-" + os.path.basename(path) + "-", suffix=".part", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle: json.dump(data, handle, ensure_ascii=False, indent=2)
            replace_file(tmp, path)
        except Exception:
            try: os.unlink(tmp)
            except OSError: pass
            raise
    finally:
        if lock_fh: fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN); lock_fh.close()

def save_json(rel, data):
    p = rel if os.path.isabs(rel) else P(rel); atomic_save_json(p, data)

def deep_merge(a, b):
    """b over a; dicts merged recursively, lists and scalars replaced."""
    if not isinstance(a, dict) or not isinstance(b, dict): return json.loads(json.dumps(b))
    out = json.loads(json.dumps(a))
    for k, v in b.items(): out[k] = deep_merge(out.get(k), v) if isinstance(v, dict) and isinstance(out.get(k), dict) else json.loads(json.dumps(v))
    return out
OVERRIDES_ON = [True]   # `dbcx override check` switches the override layers off to compute the plugin's own base
def override_files(rel):
    """[<project>/overrides/<rel>, <run>/overrides/<rel>] - engagement first, the run's wins; one path when the run is its own engagement"""
    return list(dict.fromkeys([PP("overrides", rel), P("overrides", rel)])) if OVERRIDES_ON[0] else []
def override_json(rel):
    """the merged JSON override files of <rel>; `patches` lists concatenate (an engagement patch survives a run's own), other lists are replaced"""
    out = {}
    for p in override_files(rel):
        o = read_json(p, {}); pt = (out.get("patches") or []) + (o.get("patches") or [])
        out = deep_merge(out, o)
        if pt: out["patches"] = pt
    return out
def union_merge(a, b):
    if isinstance(a, list) and isinstance(b, list): return a + [x for x in b if x not in a]
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items(): out[k] = union_merge(out[k], v) if k in out else v
        return out
    return b

# ------------------------------------------------------------------ method packs
def method_roots(project_dir=None):
    """the existing method roots in lookup order - the engagement's methods/ (a run that is its own engagement: <run>/methods/), then
    the plugin's. Without project_dir the current PROJECT, and only when it is one (engagement.json or run.json): a stray methods/ in the cwd is no root."""
    eng = project_dir or (PROJECT_DIR if any(os.path.exists(os.path.join(PROJECT_DIR, f)) for f in (PROJECT_FILE, RUN_FILE)) else None)
    own = [os.path.join(eng, "methods")] if eng and os.path.realpath(os.path.join(eng, "methods")) != os.path.realpath(METHODS) else []
    return [r for r in own + [METHODS] if os.path.isdir(r)]
def _scan_methods(project_dir=None):
    """({name: {dir, source}} in lookup order: $DBCX_METHOD_DIR, engagement, plugin; {name: dir} of own methods refused for a plugin method's name)"""
    plugin = {n for n in (os.listdir(METHODS) if os.path.isdir(METHODS) else []) if os.path.exists(os.path.join(METHODS, n, "method.json"))}
    env = os.path.abspath(os.path.expanduser(os.environ["DBCX_METHOD_DIR"])) if os.environ.get("DBCX_METHOD_DIR") else None
    cand = [(os.path.basename(env), env)] if env else []
    cand += [(n, os.path.join(r, n)) for r in method_roots(project_dir) for n in sorted(os.listdir(r))]
    found, clash = {}, {}
    for n, d in cand:
        if n in found or not os.path.exists(os.path.join(d, "method.json")): continue
        if os.path.realpath(os.path.dirname(d)) == os.path.realpath(METHODS): found[n] = {"dir": d, "source": "plugin"}; continue
        if n in plugin or read_json(os.path.join(d, "method.json")).get("name", n) in plugin: clash[n] = d; continue
        found[n] = {"dir": d, "source": "engagement"}
    return {n: e for n, e in found.items() if n not in clash}, clash   # a refused name is ambiguous in this project: neither copy runs
def method_index(project_dir=None):
    """{name: {"dir", "source"}} of every method this project can run; source = engagement (own method) | plugin"""
    return _scan_methods(project_dir)[0]
def method_clashes(project_dir=None):
    """{name: dir} of own methods refused because they reuse a plugin method's name (no shadowing)"""
    return _scan_methods(project_dir)[1]
def list_methods(project_dir=None): return sorted(method_index(project_dir))
def run_file(): return load_json(RUN_FILE, {})
def project_file(): return read_json(PP(PROJECT_FILE), {}) if os.path.exists(PP(PROJECT_FILE)) else {}
def method_name():
    return os.environ.get("DBCX_METHOD") or run_file().get("method") or None
_METHOD_CACHE = {}   # by method folder, not name (an engagement's own method and another engagement's may share a name)
def method(name=None, project_dir=None):
    name = name or method_name()
    if not name: raise SystemExit(f"no method: run.json lacks `method` (available: {', '.join(list_methods(project_dir))}); `{CLI} init` creates a run")
    found, clash = _scan_methods(project_dir)
    if name in clash: raise SystemExit(f"REFUSED: your own method '{name}' ({clash[name]}) has the same name as a method of the plugin, so neither can run in this engagement. Give your method a new name: rename its folder and set the same name as `name` in its method.json (for example '{name}-own').")
    if name not in found: raise SystemExit(f"unknown method '{name}' (available: {', '.join(sorted(found))})")
    d = found[name]["dir"]
    if d in _METHOD_CACHE: return _METHOD_CACHE[d]
    m = read_json(os.path.join(d, "method.json")); m["_dir"] = d; m["_source"] = found[name]["source"]; m.setdefault("name", name)
    for k, v in (("defaults", {}), ("knowledge_slots", {}), ("evidence_bases", []), ("phases", []), ("scopes", {}), ("consolidations", {}), ("inventory", None), ("gauntlet", {}), ("briefs", {}), ("deliverable_sources", {}), ("artefacts", {"consumes": [], "produces": []}), ("snippets", {}), ("lint", {})):
        m.setdefault(k, v)
    _METHOD_CACHE[d] = m; return m
def method_tool(name, m=None):
    """Path of a method-specific tool (methods/<m>/tools/<name>.py) or None."""
    try: m = m or method()
    except SystemExit: return None
    p = os.path.join(m["_dir"], "tools", f"{name}.py"); return p if os.path.exists(p) else None

# ------------------------------------------------------------------ knowledge packs
def list_packs(kind=None):
    out = []
    if not os.path.isdir(KNOWLEDGE): return out
    for k in sorted(os.listdir(KNOWLEDGE)):
        kd = os.path.join(KNOWLEDGE, k)
        if not os.path.isdir(kd) or (kind and k not in (kind, kind + "s", kind.rstrip("s"))): continue
        for n in sorted(os.listdir(kd)):
            if os.path.exists(os.path.join(kd, n, "pack.json")): out.append((k, n))
    return out
def pack_dir(name, kind=None):
    for k, n in list_packs(kind):
        if n == name: return os.path.join(KNOWLEDGE, k, n)
    return None
def pack(name, kind=None):
    d = pack_dir(name, kind)
    if not d: raise SystemExit(f"unknown knowledge pack '{name}'" + (f" of kind {kind}" if kind else "") + f" (available: {', '.join(f'{k}/{n}' for k, n in list_packs(kind))})")
    pk = read_json(os.path.join(d, "pack.json")); pk["_dir"] = d; pk.setdefault("kind", os.path.basename(os.path.dirname(d))); pk.setdefault("name", name); return pk

def _slot_packs(pf, rf, m):
    """Resolve knowledge slots: run.json/engagement.json `knowledge: {slot: pack}` (+ legacy source.pack / target.pack)."""
    kn = deep_merge(pf.get("knowledge", {}) or {}, rf.get("knowledge", {}) or {})
    for role in ("source", "target"):
        legacy = (rf.get(role) or pf.get(role) or {}).get("pack")
        if legacy and role not in kn: kn[role] = legacy
    out = {}
    for slot, sdef in m.get("knowledge_slots", {}).items():
        name = kn.get(slot) or sdef.get("default")
        if name and PLACEHOLDER_RE.search(str(name)): continue   # unfilled slot: tools still run, `dbcx check_fill` reports it
        if name: out[slot] = pack(name, sdef.get("kind")); out[slot]["_slot"] = slot; out[slot]["_role"] = sdef.get("role", slot)
    for slot, name in kn.items():
        if slot not in out and name and not PLACEHOLDER_RE.search(str(name)): out[slot] = pack(name); out[slot]["_slot"] = slot; out[slot]["_role"] = slot
    return out

_PROJECT_CACHE = {}
def _lang(v, lang): return v.get(lang, v.get("en", "")) if isinstance(v, dict) else v
def project():
    """Merged configuration of the current run (engine defaults <- method defaults <- knowledge packs <- engagement.json <- engagement
    overrides/settings.json <- run.json <- run overrides/settings.json)."""
    if "cfg" in _PROJECT_CACHE: return _PROJECT_CACHE["cfg"]
    cfg = read_json(os.path.join(DEFAULTS, "run.defaults.json")); pf = project_file(); rf = run_file()
    ov = [read_json(p, {}) for p in override_files("settings.json")]   # every setting may be overridden (no protected keys)
    if len(ov) == 2: pf = deep_merge(pf, ov[0])
    if ov: rf = deep_merge(rf, ov[-1])
    mname = rf.get("method") or os.environ.get("DBCX_METHOD")
    m = method(mname) if mname else {"defaults": {}, "knowledge_slots": {}, "name": None, "_dir": None, "evidence_bases": [], "phases": [], "scopes": {}, "consolidations": {}, "inventory": None, "gauntlet": {}, "briefs": {}, "deliverable_sources": {}, "artefacts": {"consumes": [], "produces": []}, "snippets": {}, "lint": {}}
    cfg = deep_merge(cfg, m.get("defaults", {}))
    prof = rf.get("profile") or pf.get("profile") or "full"   # the profile layer sits on the method defaults; packs, engagement and run.json still win
    cfg = deep_merge(cfg, (m.get("profiles") or {}).get(prof) or {})
    packs = _slot_packs(pf, rf, m) if mname else {}
    lang = (rf.get("languages") or pf.get("languages") or {}).get("deliverable", cfg["languages"]["deliverable"])
    layer = {}
    for slot, pk in packs.items():
        if not pk: continue
        if pk.get("kind") == "platform":
            if pk["_role"] == "source":
                a = pk.get("as_source", {}); layer = deep_merge(layer, {"source": {"platform": a.get("platform", pk["display"]), "pack": pk["name"]}, "unit": a.get("unit", {}), "rules": {"do_not_run": a.get("do_not_run", [])}})
            else:
                a = pk.get("as_target", pk.get("as_source", {})); layer = deep_merge(layer, {"target": {"platform": a.get("platform", pk["display"]), "pack": pk["name"], "api_name": a.get("api_name", ""), "content_model_name": _lang(a.get("content_model_name", ""), lang)}})
        layer = deep_merge(layer, pk.get("config", {}))
    cfg = deep_merge(deep_merge(deep_merge(cfg, layer), pf), rf)
    cfg["_packs"] = packs; cfg["_method"] = m; cfg["_profile"] = prof; cfg["_run_dir"] = RUN; cfg["_project_dir"] = PROJECT_DIR; cfg["_plugin_dir"] = PLUGIN
    hk = method_hook("settings", m)   # optional method hook settings.py `effective(cfg)`: settings the method derives from the merged layers (tech-fit-estimation: the size scale)
    if hk and hasattr(hk, "effective"): hk.effective(cfg)
    for d in (cfg.get("deliverables") or {}).values():   # file names may carry {a.b} placeholders (e.g. the technology under evaluation)
        if isinstance(d, dict) and isinstance(d.get("file"), str) and "{" in d["file"]: d["file"] = fmt(d["file"], cfg).replace("/", "-").replace(" ", "_")
    sc = cfg.get("scoring") or {}   # lead decision 7: one standard critic per technology pack when the options use more than one
    dids = [d["critic"] for d in declared_standard_critics(cfg)]   # `standard` stands for the declared set; its {"id": "standard"} entry expands below as before
    if dids:
        def per_decl(cs): return [x for c in cs for x in (dids if c == "standard" else [c])]
        if sc.get("critics"): sc["critics"] = per_decl(sc["critics"])
        for k, v in (sc.get("phase_critics") or {}).items(): sc["phase_critics"][k] = per_decl(v or [])
    if cfg.get("options"):
        ps = list(dict.fromkeys(o["pack"] for o in options(cfg) if o.get("pack") and not PLACEHOLDER_RE.search(str(o["pack"]))))
        def per_pack(cs): return [x for c in cs for x in ([f"standard-{p}" for p in ps] if c == "standard" else [c])] if len(ps) > 1 and "standard" in cs else cs
        if sc.get("critics"): sc["critics"] = per_pack(sc["critics"])
        for k, v in (sc.get("phase_critics") or {}).items(): sc["phase_critics"][k] = per_pack(v or [])
    elif standard_critic_info(cfg):   # method hook critics.py: the standard side per technology of the method's own model (tech-fit-estimation: per system option)
        ids = list(standard_critic_info(cfg))
        def per_hook(cs): return [x for c in cs for x in (ids if c == "standard" else [c])]
        if sc.get("critics"): sc["critics"] = per_hook(sc["critics"])
        for k, v in (sc.get("phase_critics") or {}).items(): sc["phase_critics"][k] = per_hook(v or [])
    for cs in [sc.get("critics") or []] + [v or [] for v in (sc.get("phase_critics") or {}).values()] if dids else []:
        dup = sorted({c for c in cs if cs.count(c) > 1})
        if dup: raise SystemExit(f"method {m.get('name')}: critic id {', '.join(dup)} occurs twice - a declared standard critic (method.json critics.standard) collides with a per-pack or method-hook critic; rename the declared id")
    _PROJECT_CACHE["cfg"] = cfg; return cfg

def profile_error(cfg=None, name=None):
    """why the run's profile cannot run (None when it can). `full` is today's pipeline and always supported; any other
    profile needs a block under the method's method.json `profiles`."""
    cfg = cfg or project(); name = name or cfg.get("_profile") or "full"; m = cfg["_method"]; have = ["full"] + [k for k in (m.get("profiles") or {}) if k != "full" and not k.startswith("_")]
    if name in have: return None
    return f"profile '{name}' is not supported by method {m.get('name')} (supported: {', '.join(have)}) - set `profile` in run.json to one of them" + (" (split stays mandatory for a repository or a requirement estimate)" if name == "lean" else "")

def scope_critics(scope, cfg=None, routed=True):
    """the critics of one gauntlet scope - scoring.phase_critics[inventory | consolidation | scopes] when the run sets that key
    (a list of one or none), else scoring.critics. the method hook critics.py narrows only the critics it owns (never a declared
    standard-<id>); a declared standard critic with topics scores a scope only when the scope's
    latest register (claims.json, extract_claims) routes a claim to it; before the first extraction, and with routed=False (extract_claims
    itself), it is listed"""
    cfg = cfg or project(); m = cfg["_method"]; sc = cfg.get("scoring") or {}; pc = sc.get("phase_critics") or {}; inv = m.get("inventory")
    key = "inventory" if inv and scope == inv.get("scope") else ("consolidation" if scope in (m.get("consolidations") or {}) else "scopes")
    out = list(pc[key]) if key in pc else list(sc.get("critics") or [])
    hk = method_hook("critics", m)   # a method narrows the standard critics of one scope (tech-fit-estimation: the critic of the chunk's system option)
    x = hk.scope_critics(scope, out, cfg) if hk and hasattr(hk, "scope_critics") else None
    dk = {d["critic"] for d in declared_standard_critics(cfg) if d["critic"] != "standard"}   # a hook narrows only the critics it owns; declared ones follow their topics
    out = out if x is None else [c for c in out if c in set(x) or c in dk]
    tc = {d["critic"] for d in declared_standard_critics(cfg) if d["scores"] != "all"} & set(out)
    rp = os.path.join(cfg.get("_run_dir") or RUN, "analysis", "gauntlet", scope, "claims.json"); reg = read_json(rp, {}) if tc and routed and os.path.exists(rp) else {}
    if any("critics" in c for c in reg.get("claims") or []):
        got = {cr for c in reg["claims"] for cr in c.get("critics") or []}; out = [c for c in out if c not in tc or c in got]
    return out

def all_critics(cfg=None):
    """every critic id a gauntlet of this run may use (scoring.critics + every scoring.phase_critics list)"""
    sc = (cfg or project()).get("scoring") or {}
    return list(dict.fromkeys(list(sc.get("critics") or []) + [c for v in (sc.get("phase_critics") or {}).values() for c in (v or [])]))

def packs_of(cfg, kind=None):
    return [pk for pk in cfg["_packs"].values() if pk and (kind is None or pk.get("kind") == kind)]

# ------------------------------------------------------------------ solution options (one run, N options: technology x starting point)
OPTION_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
def options(cfg=None):
    """[{id, label, pack, start, ...}] - run.json `options` (ids ^[a-z][a-z0-9-]*$, unique; `pack` defaults to the target pack,
    `start` to greenfield, `label` to the id). Without `options`: ONE option `target` built from target.* and the target-role
    platform slot, so a run that never declares options sees exactly one option block (header prefixes suppressed)."""
    cfg = cfg or project(); tgt = cfg.get("target") or {}
    slot = next((pk for pk in (cfg.get("_packs") or {}).values() if pk and pk.get("kind") == "platform" and pk.get("_role") == "target"), None)
    base = {"pack": (slot or {}).get("name") or tgt.get("pack", ""), "start": tgt.get("start") or "greenfield"}
    raw = cfg.get("options") or []
    if not raw:
        o = dict(base, id="target", label=tgt.get("platform") or (slot or {}).get("display", "") or "target")
        for k in ("version", "plan", "frontend"): o[k] = tgt.get(k, "")
        return [o]
    out, seen = [], set()
    for i, o in enumerate(raw, 1):
        oid = str((o or {}).get("id") or "")
        if not OPTION_ID_RE.match(oid): raise SystemExit(f"run.json options[{i}]: id '{oid}' must match ^[a-z][a-z0-9-]*$")
        if oid in seen: raise SystemExit(f"run.json options: id '{oid}' used twice")
        seen.add(oid); x = dict(base); x.update({k: v for k, v in o.items() if v not in (None, "")}); x["label"] = o.get("label") or oid; out.append(x)
    return out

def critic_role(critic):
    """critic id -> hook / brief role: client -> critic-client; standard, standard-<pack> and a declared standard-<id> -> critic-standard"""
    return "critic-standard" if critic == "standard" or str(critic).startswith("standard-") else f"critic-{critic}"

def claim_options(claim, option_ids, rows_of=None):
    """option ids a claim is about: an explicit claim `option`, '@<option>' in a target row ref (FR-041@brownfield[@2]), or the
    `option` field of the rows its target names (rows_of(target part) -> [row dict]); empty = option-neutral"""
    import rows as R
    ids = set(option_ids); out = [claim["option"]] if claim.get("option") in ids else []
    for part in [x for x in re.split(r"\s*;\s*", claim.get("target") or "") if x]:
        for ref in R.parse_target(part)[1]: out += [seg for seg in ref.split("@")[1:] if seg in ids]
        out += [r["option"] for r in (rows_of(part) if rows_of else []) if isinstance(r, dict) and r.get("option") in ids]
    return list(dict.fromkeys(out))

def claim_critics(critics, opts, cfg):
    """the critics that score a claim: the client critic and a single `standard` critic score every claim; a per-pack critic
    standard-<pack> scores the claims of its pack's options and every option-neutral claim; a declared standard critic passes (its topics route it, common.topic_critics)"""
    pk = {o["id"]: o.get("pack") for o in options(cfg)}; dc = {d["critic"] for d in declared_standard_critics(cfg)}
    return [c for c in critics if c in dc or not str(c).startswith("standard-") or not opts or any(c == f"standard-{pk.get(o)}" for o in opts)]

# ------------------------------------------------------------------ declared standard critics (docs/SCORING.md §2)
CRITIC_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
def declared_standard_critics(cfg=None):
    """method.json `critics.standard: [{id, persona, sources: {packs, domains, reference}, scores: "all" | {"topics": [...]}}]` -> the
    entries in declared order, normalised, each with `critic` = `standard-<id>` (role critic-standard). The entry {"id": "standard"} stays
    critic `standard` and takes no other key (one critic, per pack with run.json options, or the method hook critics.py - as without a
    declaration). [] when the method declares none: the run behaves as before. A malformed declaration is a method defect (SystemExit)."""
    m = (cfg if cfg is not None else project()).get("_method") or {}; raw = (m.get("critics") or {}).get("standard") or []
    out, seen = [], set(); where = f"method {m.get('name')}: method.json critics.standard"
    for i, e in enumerate(raw if isinstance(raw, list) else [raw], 1):
        cid = str((e or {}).get("id") or "") if isinstance(e, dict) else ""
        if not CRITIC_ID_RE.match(cid): raise SystemExit(f"{where}[{i}]: id '{cid}' must match ^[a-z][a-z0-9-]*$")
        if cid in seen: raise SystemExit(f"{where}: id '{cid}' declared twice")
        seen.add(cid)
        if cid == "standard":
            if set(e) - {"id"}: raise SystemExit(f"{where}[{i}]: the entry {{\"id\": \"standard\"}} takes no other key (its persona and sources are the method's briefs and knowledge slots) - got {', '.join(sorted(set(e) - {'id'}))}")
            out.append({"id": cid, "critic": "standard", "persona": "", "sources": {"packs": [], "domains": [], "reference": True}, "scores": "all"}); continue
        s = e.get("scores", "all"); tp = s.get("topics") if isinstance(s, dict) else None
        if s != "all" and not (isinstance(tp, list) and tp and all(isinstance(t, str) and t.strip() for t in tp)): raise SystemExit(f"{where}[{i}] ({cid}): scores must be \"all\" or {{\"topics\": [<section> | <kind>.<section> | <kind> | D<n> | D<n>/<sheet>, ...]}}")
        if not isinstance(e.get("persona", ""), str): raise SystemExit(f"{where}[{i}] ({cid}): persona must be a text")
        src = e.get("sources") or {}
        if not isinstance(src, dict) or not all(isinstance(src.get(k, []), list) for k in ("packs", "domains")): raise SystemExit(f"{where}[{i}] ({cid}): sources must be {{\"packs\": [...], \"domains\": [...], \"reference\": true|false}}")
        out.append({"id": cid, "critic": f"standard-{cid}", "persona": e.get("persona") or "", "sources": {"packs": list(src.get("packs") or []), "domains": list(src.get("domains") or []), "reference": src.get("reference", True) is not False},
                    "scores": "all" if s == "all" else {"topics": [t.strip() for t in tp]}})
    return out

def declared_critic(critic, cfg=None):
    """the declaration of a declared discipline critic standard-<id> (declared_standard_critics), None for every other critic incl. `standard`"""
    return next((d for d in declared_standard_critics(cfg) if d["critic"] == critic and critic != "standard"), None)

def claim_topics(claim, kind, idx=None, sheet_tables=None):
    """the topic keys of a claim (lower case) a declared critic's `topics` are matched against: the scope kind; per target part (`;`-separated)
    the deliverable (`d1`) and the sheet (`d1/scores`, the text before `#` / `:`); the sections of the scope's analysis its target rows
    resolve to (`capabilities` and `scoring.capabilities`; engine/tools/rows.py, idx = rows.analyse(...)["index"])"""
    import rows as R
    keys = {kind}
    for part in [x for x in re.split(r"\s*;\s*", claim.get("target") or "") if x]:
        sheet = R.parse_target(part)[0]
        if sheet: keys |= {sheet, sheet.split("/", 1)[0]}
        if idx: keys |= {k for sec, _ in R.resolve_target(part, kind, idx, sheet_tables or {})[0] for k in (sec, f"{kind}.{sec}")}
    return {str(k).strip().lower() for k in keys if k}

def topic_critics(keys, critics, cfg):
    """the declared discipline critics among `critics` that score a claim with these topic keys (claim_topics): every `scores: all` critic,
    and every critic with a topic among the keys (case-insensitive)"""
    return [d["critic"] for d in declared_standard_critics(cfg) if d["critic"] in critics and d["critic"] != "standard"
            and (d["scores"] == "all" or any(t.lower() in keys for t in d["scores"]["topics"]))]

def option_packs(cfg=None):
    """{pack name: pack} of the options' technology packs. They are NOT knowledge slots: a second platform pack in a slot would
    overwrite {target.*} and merge its snippets last-wins; option packs are only read where a tool asks for them. Plus the packs
    of the method hook's standard critics (critics.py; tech-fit-estimation: every system option's pack)."""
    cfg = cfg or project(); slots = {pk["name"]: pk for pk in (cfg.get("_packs") or {}).values() if pk}; out = {}
    for n in [o.get("pack") for o in options(cfg)] + [v.get("pack") for v in (standard_critic_info(cfg) or {}).values()]:
        if n and n not in out and not PLACEHOLDER_RE.search(str(n)): out[n] = slots.get(n) or pack(n, "platform")
    return out

_HOOKS = {}
def method_hook(name, m):
    """methods/<m>/<name>.py of a method (dict with `_dir`), imported once - None when the method has no such file"""
    p = os.path.join((m or {}).get("_dir") or "", f"{name}.py") if (m or {}).get("_dir") else None
    if not p or not os.path.exists(p): return None
    if p not in _HOOKS:
        spec_ = importlib.util.spec_from_file_location(f"dbcx_hook_{name}", p); mod = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(mod); _HOOKS[p] = mod
    return _HOOKS[p]

def standard_critic_info(cfg):
    """the method hook critics.py `standard_critics(cfg) -> {critic id: {"pack": name, "label": text}}` - the run's standard critics when the
    method's own model defines them (tech-fit-estimation: one per system option technology); None = the engine rule (run.json options)"""
    hk = method_hook("critics", (cfg or {}).get("_method"))
    return (hk.standard_critics(cfg) or None) if hk and hasattr(hk, "standard_critics") else None

def critic_pack(critic, cfg=None):
    """the technology pack a standard critic judges: standard-<pack> of run.json options, or the method hook's critic (its label as display);
    None for `standard` (the slot packs) and every other critic"""
    cfg = cfg or project()
    if not str(critic).startswith("standard-") or declared_critic(critic, cfg): return None   # a declared critic names its packs itself
    info = (standard_critic_info(cfg) or {}).get(critic)
    if info:
        pk = dict(option_packs(cfg).get(info["pack"]) or pack(info["pack"], "platform"))
        if info.get("label"): pk["display"] = info["label"]
        return pk
    return option_packs(cfg).get(critic[len("standard-"):])

def scope_pack(scope, cfg=None):
    """the technology pack of one analyst scope when the method hook names it (critics.py scope_pack; tech-fit-estimation: the
    chunk's system option) - its notes replace the slot notes in the analyst brief; None = the engine rule"""
    cfg = cfg or project(); hk = method_hook("critics", cfg.get("_method"))
    n = hk.scope_pack(scope, cfg) if hk and hasattr(hk, "scope_pack") else None
    return option_packs(cfg).get(n) if n else None

def knowledge():
    k = read_json(os.path.join(DEFAULTS, "knowledge.skeleton.json")); cfg = project()
    for pk in packs_of(cfg):
        kp = os.path.join(pk["_dir"], pk.get("knowledge", "knowledge.json"))
        if os.path.exists(kp):
            pkk = read_json(kp)
            if pk.get("kind") == "platform" and pk["_role"] == "target": pkk = {kk: v for kk, v in pkk.items() if kk.startswith("target_")}
            k = deep_merge(k, pkk)
    k = deep_merge(k, override_json("knowledge.json"))
    k = union_merge(k, load_json(DERIVED_PATH, {}))
    return k

def labels(lang=None):
    cfg = project(); lang = lang or cfg["languages"]["deliverable"]; m = cfg["_method"]
    L = read_json(os.path.join(SPEC, f"labels.{lang}.json"), read_json(os.path.join(SPEC, "labels.en.json"), {}))
    if m.get("_dir"): L = deep_merge(L, read_json(os.path.join(m["_dir"], f"labels.{lang}.json"), {}))
    for pk in packs_of(cfg): L = deep_merge(L, read_json(os.path.join(pk["_dir"], f"labels.{lang}.json"), {}))
    return deep_merge(L, override_json(f"labels.{lang}.json"))

def deliverables_spec(lang=None):
    cfg = project(); lang = lang or cfg["languages"]["deliverable"]; m = cfg["_method"]
    base = read_json(os.path.join(SPEC, f"deliverables.common.{lang}.json"), read_json(os.path.join(SPEC, "deliverables.common.en.json")))
    ms = read_json(os.path.join(m["_dir"], f"deliverables.{lang}.json"), None) if m.get("_dir") else None
    if ms is None and m.get("_dir"): ms = read_json(os.path.join(m["_dir"], "deliverables.en.json"), {"deliverables": {}})
    from xl_spec import apply_patches, expand_repeats, apply_when, rename_sheets   # id-keyed override patches after the deep merge (errors land in `_patch_errors`)
    merged = deep_merge(deep_merge(base, ms or {}), override_json(f"deliverables.{lang}.json"))
    pp = (merged.pop("profile_patches", None) or {}).get(cfg.get("_profile") or "full") or []   # a method's patches for the run's profile, before the run's own
    if pp: merged["patches"] = pp + (merged.get("patches") or [])
    ctx = spec_context(cfg); flags, sets = ctx.get("flags") or {}, ctx.get("sets") or {}   # optional method hook: `when` flags and further repeat sets
    if ctx.get("renames"): merged = rename_sheets(merged, ctx["renames"])   # before the expansion: a generated sheet ({p.name}) of the same name keeps it
    opts = options(cfg)   # option repeats first, so patches can name the expanded ids; again after them, for a repeat a patch inserts
    out = apply_when(expand_repeats(apply_patches(expand_repeats(apply_when(merged, flags), opts, sets)), opts, sets), flags)
    def status_refs(o):   # a column's `status: "$a.b"` takes its token -> status map from the configuration (tech-fit-estimation: estimation.size_status)
        if isinstance(o, dict):
            if isinstance(o.get("status"), str) and o["status"].startswith("$"): o["status"] = dict(resolve_ref(o["status"], cfg) or {})
            for v in o.values(): status_refs(v)
        elif isinstance(o, list):
            for v in o: status_refs(v)
    status_refs(out); return out

def spec_context(cfg):
    """optional method hook `datasets.spec_context(cfg) -> {"flags": {name: bool}, "sets": {name: {"as": "<prefix>", "items": [dict]}},
    "renames": {sheet name: new name}}`: the flags a spec item's `when` names, the lists a `{"repeat": "<set>"}` entry copies (placeholders
    {<prefix>.<key>}) and method sheets that give way to a generated sheet of the same name (every {rng:<sheet>.} follows); none without it"""
    if not (cfg.get("_method") or {}).get("_dir"): return {}
    mod = load_method_module("datasets")
    return (mod.spec_context(cfg) or {}) if mod and hasattr(mod, "spec_context") else {}

def snippets(cfg=None):
    """Merged snippets: platform packs (as_source / as_target), other packs (`snippets`), method (`snippets`), engagement + run overrides/snippets.json."""
    cfg = cfg or project(); s = {}
    for pk in packs_of(cfg):
        if pk.get("kind") == "platform": s.update(pk.get("as_source" if pk["_role"] == "source" else "as_target", {}).get("snippets", {}))
        else: s.update(pk.get("snippets", {}))
    s.update(cfg["_method"].get("snippets", {})); s.update(override_json("snippets.json"))
    return {k: fmt(v, cfg) for k, v in s.items()}

def pack_snippets(cfg, target):
    """Snippets as one technology pack sees them (per-pack standard critic, per-pack notes): like snippets(), but the target-role
    platform pack is replaced by `target` (an option pack) - never the last-wins merge of several technologies."""
    s = {}
    for pk in packs_of(cfg):
        if pk.get("kind") == "platform" and pk["_role"] != "source": continue
        s.update(pk.get("as_source", {}).get("snippets", {}) if pk.get("kind") == "platform" else pk.get("snippets", {}))
    s.update(target.get("as_target", target.get("as_source", target)).get("snippets", {}))   # a declared critic's pack may be a catalogue or reference architecture (no as_target / as_source)
    s.update(cfg["_method"].get("snippets", {})); s.update(override_json("snippets.json"))
    return {k: fmt(v, cfg) for k, v in s.items()}

def extra_option_packs(cfg):
    """option packs that are not already a knowledge slot (a second technology); each marked `_slot: option`. Only a run that
    declares `options` has any (the default option is the target slot itself)."""
    if not cfg.get("options") and not standard_critic_info(cfg): return []
    slots = {pk["name"] for pk in packs_of(cfg)}
    return [dict(pk, _slot="option") for n, pk in option_packs(cfg).items() if n not in slots]

def load_pack_adapter(pack_name, filename="adapter.py"):
    """Import knowledge/platforms/<pack>/adapter.py from THIS package. A run's overrides/adapter.py delegates to it
    through this helper instead of a hard-coded package path, so a package move or a second installation cannot break
    the run. Template: engine/defaults/adapter.template.py."""
    p = os.path.join(KNOWLEDGE, "platforms", pack_name, filename)
    if not os.path.exists(p): raise FileNotFoundError(f"pack adapter not found: {p}")
    spec_ = importlib.util.spec_from_file_location(f"dbcx_pack_adapter_{pack_name}", p); mod = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(mod); mod.__file__ = p; return mod

def load_adapter():
    cfg = project(); src = cfg["_packs"].get("source"); cand = override_files("adapter.py")[::-1]   # the run's adapter first, then the engagement's
    if src: cand.append(os.path.join(src["_dir"], src.get("adapter", "adapter.py")))
    for c in cand:
        if os.path.exists(c):
            spec_ = importlib.util.spec_from_file_location("dbcx_adapter", c); mod = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(mod); mod.__file__ = c; return mod
    raise SystemExit("no adapter found: " + ", ".join(cand))

def load_method_module(name, required=False):
    """Import methods/<m>/<name>.py (datasets.py, briefing.py) or return None."""
    m = method(); p = os.path.join(m["_dir"], f"{name}.py")
    if not os.path.exists(p) and name == "datasets" and m.get("datasets") == "generic":   # the generic rows from the kinds tables
        import generic_datasets; return generic_datasets
    if not os.path.exists(p):
        if required: raise SystemExit(f"method {m['name']} lacks {name}.py")
        return None
    spec_ = importlib.util.spec_from_file_location(f"dbcx_method_{name}", p); mod = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(mod); return mod

# ------------------------------------------------------------------ analysis spec (engine kinds + method kinds)
def resolve_ref(value, proj):
    if isinstance(value, str) and value.startswith("$"):
        cur = proj
        for part in value[1:].split("."): cur = cur[part]
        return cur
    return value
def norm_field(f, proj):
    if isinstance(f, str): f = {"t": f}
    f = dict(f)
    if "enum" in f: f["enum"] = resolve_ref(f["enum"], proj)
    if isinstance(f.get("enum"), list):   # a "$a.b" item inside the list splices that list in (["", "$estimation.sizes"]: empty or a configured size)
        f["enum"] = [y for x in f["enum"] for y in (lambda r: r if isinstance(r, list) else [r])(resolve_ref(x, proj))]
    return f
def spec(proj=None):
    proj = proj or project(); sp = read_json(os.path.join(SPEC, "engine_spec.json")); claims = sp["claims"]
    kinds = dict(sp["kinds"]); m = proj["_method"]; mk = read_json(os.path.join(m["_dir"], "kinds.json"), {}) if m.get("_dir") else {}
    kinds.update(mk.get("kinds", {}))
    for kind, secs in (mk.get("extend") or {}).items():   # a method adds fields to a section of an engine kind (critic -> scores.ground) without copying the kind
        if kind not in kinds: continue
        kinds[kind] = json.loads(json.dumps(kinds[kind]))
        for s in kinds[kind]["sections"]:
            ext = secs.get(s.get("key")) if isinstance(s, dict) else None
            if ext: s.setdefault("fields", {}).update(ext.get("fields") or {}); s["help"] = " ".join(x for x in (s.get("help"), ext.get("help")) if x)
    out = {}
    for kind, k in kinds.items():
        k = json.loads(json.dumps(k)); k["head"] = {n: norm_field(f, proj) for n, f in k.get("head", {}).items()}; secs = []
        for s in k["sections"]:
            if s == "CLAIMS": s = json.loads(json.dumps(claims))
            if s == "ASSUMPTIONS": s = {k2: v for k2, v in json.loads(json.dumps(sp["assumptions"])).items() if k2 != "_readme"}   # opt-in: readings taken instead of open questions
            if s.get("fields"): s["fields"] = {n: norm_field(f, proj) for n, f in s["fields"].items()}
            secs.append(s)
        k["sections"] = secs; out[kind] = k
    return out, sp.get("conventions", "")

# ------------------------------------------------------------------ scopes, roles, agent names
ROLE_PREFIXES = [("critic-client-", "critic-client"), ("critic-standard-", "critic-standard"), ("critic-platform-", "critic-standard"), ("consolidate-", "consolidator"), ("gate-verifier", "verifier"), ("deliverable-editor", "editor"), ("gate-", "gate"), ("postpass-", "postpass"), ("progress-reporter", "progress"), ("researcher", "researcher"), ("inventory", "inventory")]
def role_of_agent(name, m=None):
    name = name or ""
    if name.startswith(AGENT_PREFIX):   # Claude agent type "dbcx-agentic-loop:gate-persona"
        name = name[len(AGENT_PREFIX):]
    if name.startswith("dbcx-"):
        name = name[len("dbcx-"):]
    exact = {
        "analyst": "analyst",
        "consolidator": "consolidator",
        "critic-client": "critic-client",
        "critic-standard": "critic-standard",
        "gate-persona": "gate",
        "gate-verifier": "verifier",
        "deliverable-editor": "editor",
        "inventory-analyst": "inventory",
        "postpass-corrector": "postpass",
        "progress-reporter": "progress",
        "researcher": "researcher",
    }
    if name in exact:
        return exact[name]
    for pre, role in ROLE_PREFIXES:
        if name.startswith(pre): return role
    try: m = m or method()
    except SystemExit: m = None
    ap = (m or {}).get("scopes", {}).get("agent_prefix", "analyst-")
    if name.startswith(ap) or name.startswith("analyst-") or name.startswith("unit-"): return "analyst"
    return "orchestrator" if name in ("", "orchestrator") else "unknown"

def extra_gauntlet(scope, m=None):
    """a gauntlet scope of a method brief kind - method.json briefs.extra_kinds.<kind>.gauntlet = {"scope": "TRIAGE", "output_dir": "analysis/triage"}
    (tech-fit-estimation): the scope itself or a part <scope>-<n> -> (kind, spec, part number or None); None for any other scope.
    Its analysis is <output_dir>/<scope>.md, its agent the kind's `agent` (a part: <agent>-<n>), its role the kind's `role`; it is consolidated
    (cross-scope evidence) and score_aggregate records its rounds under STATUS `steps.<scope>` - it is neither a phase nor a wave member."""
    if not scope: return None
    try: m = m or method()
    except SystemExit: return None
    for k, x in (((m or {}).get("briefs") or {}).get("extra_kinds") or {}).items():
        g = x.get("gauntlet") if isinstance(x, dict) else None
        mm = re.fullmatch(re.escape(str(g.get("scope") or "")) + r"(?:-(\d+))?", str(scope)) if isinstance(g, dict) and g.get("scope") else None
        if mm: return k, x, (int(mm.group(1)) if mm.group(1) else None)
    return None
def extra_agent(spec_, part=None):
    """the agent name of a method brief kind (a part of a gauntlet kind: <agent>-<n>)"""
    return spec_["agent"] + (f"-{part}" if part else "")
def scope_info(scope, m=None):
    """(json_path, md_path, kind, role, agent_name) for a gauntlet scope: the inventory scope, a consolidation, a method brief kind's
    gauntlet scope (extra_gauntlet) or a per-scope analysis."""
    m = m or method(); inv = m.get("inventory")
    if inv and scope == inv.get("scope"):
        md = P(inv["output"]); return md[:-3] + ".json", md, inv.get("kind", "inventory"), "inventory", inv.get("agent", "inventory")
    if scope in m.get("consolidations", {}):
        c = m["consolidations"][scope]; md = P(c["output"]); return md[:-3] + ".json", md, c.get("kind", scope), "consolidator", f"consolidate-{scope.lower()}"
    xg = extra_gauntlet(scope, m)
    if xg:
        k, x, part = xg; md = P(x["gauntlet"].get("output_dir") or "analysis", f"{scope}.md"); return md[:-3] + ".json", md, k, x.get("role", "consolidator"), extra_agent(x, part)
    sc = m.get("scopes", {}); md = P(sc.get("output_dir", "analysis/scopes"), f"{scope}.md")
    return md[:-3] + ".json", md, sc.get("kind", "scope"), "analyst", f"{sc.get('agent_prefix', 'analyst-')}{scope}"
def scope_of_path(rel_path, m=None):
    """Reverse of scope_info for an analysis Markdown path relative to the run (None when the path is no analysis file)."""
    m = m or method(); rp = rel_path.replace(os.sep, "/")
    inv = m.get("inventory")
    if inv and rp == inv["output"]: return inv["scope"]
    for s, c in m.get("consolidations", {}).items():
        if rp == c["output"]: return s
    for x in ((m.get("briefs") or {}).get("extra_kinds") or {}).values():
        g = x.get("gauntlet") if isinstance(x, dict) else None
        xd = (g.get("output_dir") or "analysis").rstrip("/") + "/" if isinstance(g, dict) and g.get("scope") else None
        if xd and rp.startswith(xd) and rp.endswith(".md") and extra_gauntlet(rp[len(xd):-3], m): return rp[len(xd):-3]
    d = m.get("scopes", {}).get("output_dir", "analysis/scopes").rstrip("/") + "/"
    if rp.startswith(d) and rp.endswith(".md") and "/" not in rp[len(d):]: return rp[len(d):-3]
    return None
def is_consolidated(scope, m=None):
    m = m or method(); inv = m.get("inventory")
    return bool(inv and scope == inv.get("scope")) or scope in m.get("consolidations", {}) or bool(extra_gauntlet(scope, m))
def phase_for_scope(scope, m=None):
    m = m or method()
    for ph in m.get("phases", []):
        if ph.get("scope") == scope: return ph["id"]
    return None

# ------------------------------------------------------------------ evidence bases
# The final gate reads what the client receives and nothing else (G1): the customer edition at the top of deliverables/, the
# renderings of it, its own brief and score files. The full edition, the analyses and the internal work are not the client's.
GATE_ROLES = ("gate", "verifier")
# `privacy: false`: run folders, not client evidence - their names may appear in a web query (honoured by the privacy checks once they read it).
ENGINE_BASES = [
    {"id": "customer-edition", "kind": "deliverable", "roots": ["deliverables"], "roles": ["*", "gate", "verifier"], "privacy": False, "note": "the customer edition (top-level workbooks) - what the client receives"},
    {"id": "full-edition", "kind": "derived", "roots": ["deliverables/intern"], "roles": ["*"], "privacy": False, "note": "the full edition with the claims and open-question sheets - internal"},
    {"id": "run-internal", "kind": "derived", "roots": ["work", "state", "docs"], "roles": ["*"], "privacy": False, "note": "team-only work, run state and reports"},
    {"id": "gate-io", "kind": "derived", "roots": ["analysis/briefs", "analysis/gate", "work/render"], "roles": ["*", "gate", "verifier"], "privacy": False, "note": "gate briefs, score files and the rendered customer workbooks"},
]
# Base kinds with engine default roles (used when the base declares no `roles`):
#   vendor-code  the vendor's standard code (e.g. the composable storefront libraries, reference/vendor-code/...): read-only,
#                never client evidence - standard side + analyst, consolidator, researcher, verifier; the client critic never reads it
#   client-repo  the client's frozen repository for one option (brownfield lookups): read-only, analyst + client critic (+ verifier);
#                inert while its root placeholder (e.g. {repo.path}) is unset
DEFAULT_ROLES = {"vendor-code": ["orchestrator", "analyst", "critic-standard", "consolidator", "researcher", "verifier"],
                 "client-repo": ["orchestrator", "analyst", "critic-client"]}
CLIENT_KINDS = ("repository", "client-repo", "workbook", "corpus", "documents")   # the client's own evidence (the verifier reads what the client critic reads)
READ_ONLY_KINDS = ("repository", "client-repo", "vendor-code", "corpus", "workbook", "handover", "documents")
def evidence_bases(cfg=None):
    """Resolved evidence bases: engine gate bases <- method defaults <- run.json evidence_bases (matched by id; a run may add or replace)."""
    cfg = cfg or project(); by = {eb["id"]: dict(eb) for eb in ENGINE_BASES}
    for eb in cfg["_method"].get("evidence_bases", []): by[eb["id"]] = dict(eb)
    for eb in cfg.get("evidence_bases", []) or []: by[eb["id"]] = deep_merge(by.get(eb["id"], {}), eb)
    out = []
    for eb in by.values():
        eb = dict(eb); eb.setdefault("roles", list(DEFAULT_ROLES.get(eb.get("kind"), ["*"]))); eb.setdefault("external", eb.get("kind") == "web"); eb.setdefault("read_only", True)
        if cfg.get("consolidator_reads_corpus") and eb.get("kind") == "corpus" and "consolidator" not in eb["roles"]: eb["roles"] = eb["roles"] + ["consolidator"]   # the consolidator is the analyst of everything
        roots = []
        for r in eb.get("roots", []) or []:
            r = fmt(r, cfg)
            if PLACEHOLDER_RE.search(r) or not r.strip() or "{" in r: continue
            roots.append(os.path.realpath(resolve_root(r)))   # realpath, not abspath: a root given as an absolute path (e.g. run.json repo.path) may itself carry an unresolved symlink component (macOS $TMPDIR, a symlinked checkout) that a hook's realpath'd file_path would then fail to match
        eb["abs_roots"] = roots; out.append(eb)
    return out
def agent_reads(agent, m=None):
    """evidence-base ids a method brief kind grants its agent beyond its role (method.json briefs.extra_kinds.<kind>.reads; a part
    <agent>-<n> of a gauntlet kind too) - e.g. the tech-fit-estimation triage agent (role consolidator) reads the corpus"""
    agent = str(agent or "")
    if agent.startswith(AGENT_PREFIX): agent = agent[len(AGENT_PREFIX):]
    if not agent: return set()
    try: m = m or method()
    except SystemExit: return set()
    out = set()
    for x in (((m or {}).get("briefs") or {}).get("extra_kinds") or {}).values():
        if isinstance(x, dict) and x.get("reads") and x.get("agent") and re.fullmatch(re.escape(x["agent"]) + r"(?:-\d+)?", str(agent)): out |= set(x["reads"])
    return out
def role_may_read(role, base, agent=None, m=None):
    """`*` grants every working role, not the gate roles: a gate persona reads only bases that name it; the verifier also reads
    the client's own evidence the client-side critic reads (repository, the client's workbooks such as the requirement list, corpus / documents)
    and the vendor's standard code; the client critic never reads vendor code (disjoint evidence: it judges the client's side).
    `agent` (optional): a method brief kind's agent may read the bases its kind lists under `reads` (agent_reads)."""
    roles = base.get("roles", []); kind = base.get("kind")
    if agent and role not in GATE_ROLES and base.get("id") in agent_reads(agent, m): return True
    if kind == "vendor-code": return role in ("orchestrator", "verifier") or (role != "critic-client" and (role in roles or (role not in GATE_ROLES and "*" in roles)))
    if role == "orchestrator" or role in roles: return True
    if role == "verifier": return kind in CLIENT_KINDS and role_may_read("critic-client", base)
    return role not in GATE_ROLES and "*" in roles

# ------------------------------------------------------------------ questions (state/QUESTIONS.json is the register; docs/questions/*.md is a rendered view)
def _legacy_questions():
    """Read the older Markdown tables (docs/questions/<from>.md) into the JSON shape - used until `dbcx questions migrate` ran."""
    import glob
    out = []
    for f in sorted(glob.glob(P("docs", "questions", "*.md"))):
        hdr = None
        for line in open(f, encoding="utf-8"):
            if not line.startswith("|"): continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if hdr is None: hdr = ["to" if c.lower() == "to_unit" else c.lower() for c in cells]; continue
            if all(re.match(r"^-*$", c) for c in cells): continue
            row = dict(zip(hdr, cells)); q = row.get("question", "")
            if not row.get("id") or row.get("id", "").lower() == "id": continue
            why = re.search(r"\(why: (.*?)\)(?=\s*(\(effect of the answer:|$))", q); eff = re.search(r"\(effect of the answer: (.*?)\)\s*$", q)
            q = re.sub(r"\s*\(effect of the answer: .*?\)\s*$", "", q); q = re.sub(r"\s*\(why: .*?\)\s*$", "", q)
            to = row.get("to", ""); status = row.get("status", "open") or "open"
            ans = row.get("answer", "")
            out.append({"id": row["id"], "kind": "client_question" if to.lower() == "client" else "scope_question", "from": row.get("from") or os.path.basename(f)[:-3], "to": to, "question": q, "why": why.group(1) if why else "", "effect": eff.group(1) if eff else "",
                        "options": [], "proceeding_under": "", "status": status, "asked_at": "", "updated_at": "", "answered_by": row.get("answered_by", ""), "scored_in_round": row.get("scored_in_round", ""), "qualification": row.get("qualification", ""),
                        "answer": {"option": "", "text": ans, "weight": "proposal", "by": row.get("answered_by", ""), "at": "", "channel": "legacy", "status": "received"} if ans else None, "_legacy_file": os.path.relpath(f, RUN)})
    return out
def load_questions():
    """All questions of the run as a list of dicts (JSON register first, legacy Markdown tables as fallback)."""
    if os.path.exists(QUESTIONS_PATH): return read_json(QUESTIONS_PATH).get("questions", [])
    return _legacy_questions()
def load_control(): return read_json(CONTROL_PATH, {}) if os.path.exists(CONTROL_PATH) else {}
def load_inbox():
    if not os.path.exists(INBOX_PATH): return []
    out = []
    for l in open(INBOX_PATH, encoding="utf-8"):
        l = l.strip()
        if not l: continue
        try: out.append(json.loads(l))
        except Exception: continue
    return out

# ------------------------------------------------------------------ misc
def placeholders_in(text): return PLACEHOLDER_RE.findall(text)
def is_placeholder(v): return isinstance(v, str) and bool(PLACEHOLDER_RE.search(v))

NUM_TOKEN_RE = re.compile(r"\s*(\d+)(?:([.,])(\d+))?\s*")
def canon_number(v):
    """the canonical form of a numeric enum token (a size label "0.25", "8"): decimal point, no leading or trailing zeros ("0,25" ->
    "0.25", "8.0" -> "8", "08" -> "8"); anything else - and a comma before exactly three digits (a thousands separator?) - comes back unchanged"""
    m = NUM_TOKEN_RE.fullmatch(v) if isinstance(v, str) else None
    if not m or (m.group(2) == "," and len(m.group(3)) == 3): return v
    i, f = m.group(1).lstrip("0") or "0", (m.group(3) or "").rstrip("0")
    return i + ("." + f if f else "")

def fmt(s, cfg=None, **kw):
    """Replace {a.b} / {a.b.c} with configuration values, {list:a.b} with a joined list, {last:a.b} with its last item, and {k} with kw."""
    if not isinstance(s, str) or "{" not in s: return s
    cfg = cfg or project()
    acc = {}
    def walk(prefix, o):
        for k, v in o.items():
            if k.startswith("_"): continue
            if isinstance(v, dict): walk(prefix + k + ".", v)
            elif isinstance(v, (str, int, float)) and not isinstance(v, bool): acc["{" + prefix + k + "}"] = str(v)
            elif isinstance(v, list): acc["{list:" + prefix + k + "}"] = ", ".join(map(str, v)); acc["{last:" + prefix + k + "}"] = str(v[-1]) if v else ""
    walk("", cfg)
    for k, v in kw.items(): acc["{" + k + "}"] = str(v)
    for k, v in acc.items():
        if k in s: s = s.replace(k, v)
    return s
