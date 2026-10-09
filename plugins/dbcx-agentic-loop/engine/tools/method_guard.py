#!/usr/bin/env python3
"""Method guardrails: a run's method stays as it was when the run started, and an own method's guard-relevant keys are
shown next to the plugin methods' so a looser setting is a conscious choice. They protect a running analysis; they never limit what
a method may contain.

  method_hash(m)    sha256 over the method folder's files (relative path + bytes; __pycache__, *.pyc, .DS_Store, *.bak* skipped).
                    `status init` stores stamp(m) in state/STATUS.json -> method_guard; `status verify` and the hook compare it (check).
                    An own method (source engagement) that changed stops the run; a plugin method only gets a note (a plugin update
                    between sessions is not an edit of the run's method).
  guard_report(m)   the guard-relevant keys (evidence_bases roles / roots / external / read_only, hook.scope_names_public,
                    briefs.extra_kinds.*.reads, defaults.rules.do_not_run, critics.standard[*].sources) and a warning wherever the
                    method is looser than every plugin method (a role reading a base kind no plugin method lets it read, a writable or
                    external client base, a root outside the run, public scope names, a standard critic pointed at client material).
                    The plugin's own methods are the baseline and produce no warnings. `dbcx method check` shows it;
                    `dbcx method confirm <m> --guard` stores the user's yes (GUARD_FILE, with the keys' hash; stamp() carries it).

Usage: dbcx method_guard hash [<method> | <method dir>] [--json]
       dbcx method_guard report [<method> | <method dir>] [--json]      (default: the run's method)
"""
import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import METHODS, DEFAULT_ROLES, CLIENT_KINDS, GATE_ROLES, read_json, fwd

CHANGED = "the method changed during the run - undo the change to finish this run, or start a new run (changes to a method belong between runs)"
SKIP_DIRS = {"__pycache__"}

def _skip(name): return name.endswith(".pyc") or name == ".DS_Store" or ".bak" in name

def method_hash(m):
    """sha256 over (relative path, bytes) of every file in the method folder, in a stable order"""
    d = m["_dir"] if isinstance(m, dict) else m; h = hashlib.sha256()
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not _skip(x))
        for f in sorted(files):
            if _skip(f): continue
            p = os.path.join(root, f); h.update(fwd(os.path.relpath(p, d)).encode() + b"\0")
            with open(p, "rb") as fh: h.update(hashlib.sha256(fh.read()).digest())
    return h.hexdigest()

def source(m):
    """`_source` from the method lookup; else plugin when the folder lies in the plugin's methods/"""
    if m.get("_source"): return m["_source"]
    d, r = os.path.realpath(m["_dir"]), os.path.realpath(METHODS)
    return "plugin" if d == r or d.startswith(r.rstrip(os.sep) + os.sep) else "engagement"

def stamp(m):
    st = {"hash": method_hash(m), "source": source(m), "dir": fwd(m["_dir"]), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    gc = guard_confirmation(m)
    if gc: st["guard_confirmed"] = {"keys_hash": gc["keys_hash"], "at": gc["at"]}   # the user's yes to the guard-key warnings, with the hash
    return st

def check(stored, m):
    """None while the method is unchanged (or the run is older: no stored hash); ("stop", text) for a changed own method;
    ("note", text) for a changed plugin method"""
    if not (stored or {}).get("hash") or method_hash(m) == stored["hash"]: return None
    if stored.get("source") == "plugin": return ("note", f"the plugin's method {m.get('name')} differs from the version this run started with (plugin update?) - finish with it or start a new run")
    return ("stop", CHANGED)

# ------------------------------------------------------------------ guard-key report
def _bases(m):
    """the method's evidence bases with the engine defaults of common.evidence_bases (roles by kind, external for web, read-only)"""
    out = []
    for eb in m.get("evidence_bases") or []:
        eb = dict(eb); eb["roles"] = eb.get("roles") or list(DEFAULT_ROLES.get(eb.get("kind"), ["*"]))
        eb.setdefault("external", eb.get("kind") == "web"); eb.setdefault("read_only", True); out.append(eb)
    return out

def _access(m):
    """[(base, role, via)]: who reads which base - its roles, and every brief kind that `reads` it (via that kind)"""
    by = {eb["id"]: eb for eb in _bases(m)}; out = [(eb, r, None) for eb in by.values() for r in eb["roles"]]
    for k, x in (((m.get("briefs") or {}).get("extra_kinds")) or {}).items():
        if isinstance(x, dict): out += [(by[b], x.get("role") or k, k) for b in x.get("reads") or [] if b in by]
    return out

def _plugin_methods():
    return [dict(read_json(os.path.join(METHODS, n, "method.json")), _dir=os.path.join(METHODS, n), _source="plugin", name=n)
            for n in sorted(os.listdir(METHODS)) if os.path.exists(os.path.join(METHODS, n, "method.json"))] if os.path.isdir(METHODS) else []

def envelope():
    """the loosest the plugin's methods go: roles per base kind (incl. brief-kind reads), kinds that are ever writable / external / not private"""
    env = {"roles": {}, "writable": set(), "external": set(), "public": set()}
    for pm in _plugin_methods():
        for eb, r, _ in _access(pm): env["roles"].setdefault(eb.get("kind"), set()).add(r)
        for eb in _bases(pm):
            if not eb["read_only"]: env["writable"].add(eb.get("kind"))
            if eb["external"]: env["external"].add(eb.get("kind"))
            if eb.get("privacy") is False: env["public"].add(eb.get("kind"))
    return env

def _covered(role, allowed):
    return role == "orchestrator" or role in allowed or (role != "*" and role not in GATE_ROLES and "*" in allowed)

def _loose_root(r):
    r = str(r).strip()
    if r.startswith("{"): return False   # a run.json placeholder ({repo.path}): the run names the folder
    bare = r[len("@project"):].strip("/") if r.startswith("@project") else r.strip("/")
    return os.path.isabs(r) or ".." in r.replace("\\", "/").split("/") or bare in ("", ".")

def guard_keys(m):
    xk = ((m.get("briefs") or {}).get("extra_kinds")) or {}
    return {"evidence_bases": [{k: eb.get(k) for k in ("id", "kind", "roles", "roots", "external", "read_only", "privacy") if eb.get(k) is not None} for eb in _bases(m)],
            "hook.scope_names_public": bool((m.get("hook") or {}).get("scope_names_public")),
            "briefs.extra_kinds.reads": {k: {"role": x.get("role"), "reads": x.get("reads")} for k, x in xk.items() if isinstance(x, dict) and x.get("reads")},
            "rules.do_not_run": list((((m.get("defaults") or {}).get("rules")) or {}).get("do_not_run") or []),
            "critics.standard.sources": {str(c.get("id")): c.get("sources") for c in ((m.get("critics") or {}).get("standard") or []) if isinstance(c, dict) and c.get("sources")}}

def guard_report(m, env=None):
    """{method, source, keys, warnings}: warnings where the method is looser than every plugin method"""
    env = env or envelope(); w = []
    roles = {}
    for eb, r, via in _access(m):
        if not _covered(r, env["roles"].get(eb.get("kind"), set())): roles.setdefault((eb["id"], eb.get("kind"), via), []).append(r)
    for (bid, kind, via), rs in roles.items():
        w.append(f"evidence base {bid} ({kind}) is read by {', '.join(rs)}" + (f" through brief kind {via}" if via else "") + f" - no plugin method lets {'that role' if len(rs) == 1 else 'these roles'} read a {kind} base")
    for eb in _bases(m):
        k = eb.get("kind")
        if not eb["read_only"] and k not in env["writable"]: w.append(f"evidence base {eb['id']} ({k}) is writable (read_only false) - every plugin method keeps a {k} base read-only")
        if eb["external"] and k not in env["external"]: w.append(f"evidence base {eb['id']} ({k}) is declared external - its roots are no longer kept out of web queries")
        if eb.get("privacy") is False and k not in env["public"]: w.append(f"evidence base {eb['id']} ({k}) has privacy false - its folder names may reach web queries")
        lr = [r for r in eb.get("roots") or [] if _loose_root(r)]
        if lr: w.append(f"evidence base {eb['id']} ({k}) has roots outside a folder of the run or engagement ({', '.join(map(str, lr))})")
    if (m.get("hook") or {}).get("scope_names_public") and source(m) != "plugin":
        w.append("hook.scope_names_public is true - scope names may reach web queries; among the plugin methods only tech-scoring sets it (its scopes are public technology names)")
    client = [eb for eb in _bases(m) if eb.get("kind") in CLIENT_KINDS]
    marks = {eb["id"] for eb in client} | {str(r).replace("@project/", "").strip("/") for eb in client for r in eb.get("roots") or [] if not str(r).startswith("{")}
    for cid, src in guard_keys(m)["critics.standard.sources"].items():
        vals = [v for x in (src.values() if isinstance(src, dict) else [src]) for v in (x if isinstance(x, list) else [x]) if isinstance(v, str)]
        hit = [v for v in vals if v.replace("@project/", "").strip("/") in marks or any(v.replace("@project/", "").startswith(mk + "/") for mk in marks)]
        if hit: w.append(f"standard critic {cid} would read client material ({', '.join(hit)}) - the standard side reads external sources only")
    return {"method": m.get("name"), "source": source(m), "keys": guard_keys(m), "warnings": w}

# ------------------------------------------------------------------ the user's confirmation of the guard keys (`dbcx method confirm <m> --guard`)
GUARD_FILE = "guard-confirmed.json"   # in the method folder: {keys_hash, warnings, at} - stale once a guard-relevant key changes
def keys_hash(m): return hashlib.sha256(json.dumps(guard_keys(m), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def guard_confirmation(m):
    """the stored confirmation when it still matches the method's guard keys, else None"""
    p = os.path.join(m["_dir"], GUARD_FILE); rec = read_json(p, {}) if os.path.exists(p) else {}
    return rec if rec.get("keys_hash") == keys_hash(m) else None
def confirm_guard(m):
    rec = {"keys_hash": keys_hash(m), "warnings": guard_report(m)["warnings"], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(os.path.join(m["_dir"], GUARD_FILE), "w", encoding="utf-8") as f: json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec

def _load(arg):
    if arg and os.path.isfile(os.path.join(arg, "method.json")):
        d = os.path.abspath(arg); m = read_json(os.path.join(d, "method.json")); m["_dir"] = d; m.setdefault("name", os.path.basename(d)); return m
    return common.method(arg)

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--json"]; js = "--json" in sys.argv
    if not a or a[0] not in ("hash", "report"): print(__doc__); sys.exit(0 if not a else 2)
    m = _load(a[1] if len(a) > 1 else None)
    if a[0] == "hash":
        st = stamp(m); print(json.dumps(st, indent=1) if js else st["hash"]); sys.exit(0)
    rep = guard_report(m)
    if js: print(json.dumps(rep, indent=1, ensure_ascii=False)); sys.exit(0)
    print(f"method {rep['method']} ({rep['source']})")
    for k, v in rep["keys"].items(): print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
    print(f"{len(rep['warnings'])} warning(s)" + ("" if rep["warnings"] else " - not looser than the plugin's methods"))
    for x in rep["warnings"]: print("  WARNING:", x)
