#!/usr/bin/env python3
"""Vendor-code installer for the SAP Commerce composable storefront (`@spartacus` scope) libraries: a version-pinned,
read-only copy of the standard npm packages as citable evidence.

Usage: dbcx vendor_code resolve [--line <line>] [--package <lib>] [--json]
       dbcx vendor_code install --version <v> --root <dir> [--force] [--json]
       dbcx vendor_code verify --root <dir> [--version <v>] [--json]
       (outside a run: python3 <plugin>/knowledge/platforms/sap-commerce/tools/vendor_code.py ...)

Packages and release lines come from this pack's pack.json `vendor_code` block (npm scope, the library list, and
`release_lines`: platform variant -> line, "default" for every other variant). The SAP registry sets NO `latest`
dist-tag: plain `npm view <pkg> version` prints nothing, so `resolve` finds the highest published version of a
release line with a semver RANGE query (">=<line>.0.0 <<line+1>.0.0") and sorts the matches numerically, not as
strings (string order would rank "221121.9.0" above "221121.41.1").

`install` downloads every library with `npm pack` (no `npm install`, no dependency tree, no lifecycle scripts) and
unpacks each tarball to <root>/<version>/@<scope>/<lib>@<version>/... so a locator of the form
`@<scope>/<lib>@<version>/<path>:<line>` resolves by joining onto <root>/<version>/. It writes
<root>/<version>/MANIFEST.json (package, version, tarball sha256 + registry integrity, file count, installed_at)
and makes the whole version tree read-only. A library missing from a release is recorded in the manifest and
printed, never fatal - other libraries still install.

Credentials: npm reads the caller's own ~/.npmrc; this tool never opens, prints or logs that file or any token in
it. Any npm output this tool echoes is redacted first (auth tokens, passwords, Authorization headers); an E401 from
the registry prints one hint line ("renew the registry credentials in ~/.npmrc") instead of npm's raw error.
"""
import glob, hashlib, json, os, re, stat, subprocess, sys, tarfile, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_JSON = os.path.join(HERE, "..", "pack.json")
MANIFEST_NAME = "MANIFEST.json"

# ------------------------------------------------------------------ pack config
def pack_config():
    with open(PACK_JSON, encoding="utf-8") as fh:
        pk = json.load(fh)
    vc = pk.get("vendor_code") or {}
    if not vc.get("libraries") or not vc.get("scope"):
        sys.exit(f"{PACK_JSON} has no usable vendor_code block (scope + libraries required)")
    return vc

def default_line(vc):
    return (vc.get("release_lines") or {}).get("default", "2211")

def default_package(vc):
    libs = vc["libraries"]
    return "storefront" if "storefront" in libs else libs[0]

# ------------------------------------------------------------------ secret redaction (never echo an npmrc credential)
_SECRET_LINE_RE = re.compile(r"(?i)_auth\b|_authToken|_password|:_authToken=|:_password=|://[^/\s]*:[^@/\s]+@|Authorization:\s*\S+")

def redact(text):
    """Drop any line of npm output that looks like it carries a registry credential (token, password, basic-auth
    URL, bearer header) - defence in depth: npm should never need to print one for `view`/`pack`, but a
    misconfigured ~/.npmrc or verbose npm build can echo one, and this tool must never repeat it."""
    if not text:
        return text
    return "\n".join("[redacted: credential-looking line]" if _SECRET_LINE_RE.search(ln) else ln for ln in text.splitlines())

def auth_hint(err):
    if re.search(r"\bE401\b|401 Unauthorized", err or ""):
        print("npm registry returned 401 - renew the registry credentials in ~/.npmrc", file=sys.stderr)

def run_npm(args):
    try:
        import shutil; r = subprocess.run([shutil.which("npm") or "npm"] + args, capture_output=True, text=True)   # Windows: npm is npm.cmd
    except FileNotFoundError:
        sys.exit("npm not found on PATH")
    return r.returncode, redact(r.stdout), redact(r.stderr)

# ------------------------------------------------------------------ resolve
def line_range(line):
    return f">={line}.0.0 <{int(line) + 1}.0.0"

def version_key(v):
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"[.\-]", v))

def resolve_line(line, package):
    """Highest published version of `package` in release `line`, via a semver range query (the registry has no
    `latest` dist-tag for these packages)."""
    rc, out, err = run_npm(["view", f"{package}@{line_range(line)}", "version", "--json"])
    if rc != 0:
        auth_hint(err)
        sys.exit(f"npm view failed for {package} (line {line}): {(err or '').strip().splitlines()[-1:] or ['?']}")
    versions = json.loads(out) if out.strip() else []
    if isinstance(versions, str):
        versions = [versions]
    versions = sorted(set(versions), key=version_key)
    if not versions:
        sys.exit(f"no published version of {package} matches line {line} (range {line_range(line)}; the registry sets no 'latest' tag)")
    return versions[-1]

# ------------------------------------------------------------------ install
def extract_tarball(tgz_path, target_dir):
    """Unpack an `npm pack` tarball, stripping the leading package/ directory the registry always wraps it in."""
    os.makedirs(target_dir, exist_ok=True)
    n = 0
    with tarfile.open(tgz_path, "r:gz") as tf:
        base = os.path.abspath(target_dir)
        for member in tf.getmembers():
            name = member.name[len("package/"):] if member.name.startswith("package/") else member.name
            if not name:
                continue
            dest = os.path.abspath(os.path.join(target_dir, name))
            if dest != base and not dest.startswith(base + os.sep):
                continue   # refuse a tarball entry that tries to escape the target directory
            if member.isdir():
                os.makedirs(dest, exist_ok=True)
            elif member.isfile():
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                src = tf.extractfile(member)
                if src is None:
                    continue
                with open(dest, "wb") as out:
                    out.write(src.read())
                n += 1
            # symlinks/devices: npm tarballs do not carry them; skip anything else defensively
    return n

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def make_read_only(root_dir):
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            os.chmod(p, stat.S_IMODE(os.stat(p).st_mode) & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        os.chmod(dirpath, stat.S_IMODE(os.stat(dirpath).st_mode) & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))

def make_writable(root_dir):
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        os.chmod(dirpath, stat.S_IMODE(os.stat(dirpath).st_mode) | stat.S_IWUSR)
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            os.chmod(p, stat.S_IMODE(os.stat(p).st_mode) | stat.S_IWUSR)

def install_one(scope, lib, version, version_dir):
    package = f"{scope}/{lib}"
    with tempfile.TemporaryDirectory(prefix="vendor-code-pack-") as tmp:
        rc, _out, err = run_npm(["pack", f"{package}@{version}", "--pack-destination", tmp, "--json"])
        if rc != 0:
            auth_hint(err)
            reason = (err or "").strip().splitlines()
            return {"package": package, "ok": False, "reason": (reason[-1] if reason else "npm pack failed")}
        tgz = sorted(glob.glob(os.path.join(tmp, "*.tgz")))
        if not tgz:
            return {"package": package, "ok": False, "reason": "npm pack reported success but produced no tarball"}
        tgz = tgz[0]
        integrity = None
        try:
            j = json.loads(_out) if _out.strip() else []
            if j and isinstance(j, list):
                integrity = j[0].get("integrity")
        except (json.JSONDecodeError, AttributeError, IndexError):
            pass   # integrity is a secondary, best-effort field; sha256 below is authoritative
        target = os.path.join(version_dir, scope, f"{lib}@{version}")
        files = extract_tarball(tgz, target)
        return {
            "package": package, "ok": True, "version": version, "tarball": os.path.basename(tgz),
            "sha256": sha256_of(tgz), "integrity": integrity, "files": files,
            "path": os.path.relpath(target, version_dir), "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

def cmd_install(args):
    vc = pack_config()
    version = need(args, "--version")
    root = os.path.abspath(need(args, "--root"))
    force = "--force" in args
    version_dir = os.path.join(root, version)
    manifest_path = os.path.join(version_dir, MANIFEST_NAME)
    if os.path.exists(manifest_path) and not force:
        sys.exit(f"{version_dir} is already installed (has {MANIFEST_NAME}); pass --force to reinstall")
    if os.path.isdir(version_dir) and force:
        make_writable(version_dir)
        import shutil
        shutil.rmtree(version_dir)
    os.makedirs(version_dir, exist_ok=True)
    installed, missing = [], []
    for lib in vc["libraries"]:
        r = install_one(vc["scope"], lib, version, version_dir)
        (installed if r["ok"] else missing).append(r)
        print(f"{'OK  ' if r['ok'] else 'MISS'} {r['package']}" + (f" ({r.get('files')} files)" if r["ok"] else f" - {r['reason']}"))
    manifest = {
        "scope": vc["scope"], "version": version, "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "packages": [{k: v for k, v in r.items() if k != "ok"} for r in installed],
        "missing": [{"package": r["package"], "reason": r["reason"]} for r in missing],
    }
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    make_read_only(version_dir)
    summary = {"root": root, "version": version, "installed": len(installed), "missing": [m["package"] for m in missing], "manifest": manifest_path}
    if "--json" in args:
        print(json.dumps(summary, indent=2))
    else:
        print(f"installed {len(installed)}/{len(vc['libraries'])} packages of {vc['scope']}@{version} into {version_dir} (read-only)")
        if missing:
            print("missing: " + ", ".join(m["package"] for m in missing))
    return summary

# ------------------------------------------------------------------ verify
def verify_version(version_dir):
    """Structural, offline re-check: every manifest entry still has its directory, file count and read-only bit -
    no network, so this never depends on registry or npm availability (consistent with the pack's other resolver
    tools)."""
    manifest_path = os.path.join(version_dir, MANIFEST_NAME)
    if not os.path.exists(manifest_path):
        return {"version_dir": version_dir, "ok": False, "error": f"no {MANIFEST_NAME}"}
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    problems = []
    for pkg in manifest.get("packages", []):
        p = os.path.join(version_dir, pkg["path"])
        if not os.path.isdir(p):
            problems.append(f"{pkg['package']}: {pkg['path']} missing"); continue
        n = sum(len(fs) for _r, _d, fs in os.walk(p))
        if n != pkg.get("files"):
            problems.append(f"{pkg['package']}: {n} files on disk, manifest says {pkg.get('files')}")
        writable_bits = stat.S_IMODE(os.stat(p).st_mode) & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        if writable_bits:
            problems.append(f"{pkg['package']}: {pkg['path']} is not read-only")
    return {"version_dir": version_dir, "ok": not problems, "packages": len(manifest.get("packages", [])),
            "missing_recorded": [m["package"] for m in manifest.get("missing", [])], "problems": problems}

def cmd_verify(args):
    root = os.path.abspath(need(args, "--root"))
    version = flag(args, "--version")
    version_dirs = [os.path.join(root, version)] if version else sorted(
        os.path.join(root, d) for d in (os.listdir(root) if os.path.isdir(root) else []) if os.path.exists(os.path.join(root, d, MANIFEST_NAME)))
    if not version_dirs:
        sys.exit(f"no installed version found under {root}")
    results = [verify_version(v) for v in version_dirs]
    if "--json" in args:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{'OK ' if r['ok'] else 'FAIL'} {r['version_dir']} ({r.get('packages', 0)} packages)")
            for p in r.get("problems", []):
                print("  -", p)
            if r.get("missing_recorded"):
                print("  recorded missing:", ", ".join(r["missing_recorded"]))
    return results

# ------------------------------------------------------------------ cli
def flag(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default

def need(args, name):
    v = flag(args, name)
    if v is None:
        sys.exit(f"{name} is required")
    return v

def cmd_resolve(args):
    vc = pack_config()
    line = flag(args, "--line", default_line(vc))
    lib = flag(args, "--package", default_package(vc))
    version = resolve_line(line, f"{vc['scope']}/{lib}")
    if "--json" in args:
        print(json.dumps({"line": line, "package": f"{vc['scope']}/{lib}", "version": version}))
    else:
        print(version)

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    cmd, rest = a[0], a[1:]
    if cmd == "resolve":
        cmd_resolve(rest)
    elif cmd == "install":
        cmd_install(rest)
    elif cmd == "verify":
        r = cmd_verify(rest)
        if not all(x["ok"] for x in r):
            sys.exit(1)
    else:
        sys.exit(f"unknown subcommand {cmd} (resolve | install | verify)\n\n{__doc__}")

if __name__ == "__main__":
    main()
