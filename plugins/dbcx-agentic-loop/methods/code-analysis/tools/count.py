#!/usr/bin/env python3
"""One counter for every figure in the engagement - so the predicate AND the line convention are stated once and quoted, not
re-implemented per agent.

Usage: dbcx count <unit | path> [--tracked | --raw] [--glob "*.java,*.jsp"] [--exclude "web/addonsrc,*/testsrc/*"] [--all-files] [--json]
  <unit>      a custom unit name from analysis/inventory/inventory.json (its folder below the repository), or any absolute/relative path
  --tracked   only files `git ls-files` reports below the path (default when the path is a git work tree; --raw forces the filesystem walk)
  --glob      comma-separated file globs (matched on the path relative to the counted folder); default: the scanner's bucket extensions.
              A glob match must also have a bucket extension (e.g. "import/sampledata/**" alone no longer counts images); files that match
              the glob but fall outside the buckets are excluded and reported (count + up to 5 example extensions) in the RULE line / --json.
  --exclude   comma-separated globs to leave out (applied after --glob)
  --all-files with --glob, count every glob match regardless of bucket extension (restores the old, glob-only behaviour)
Prints a RULE line to quote verbatim in a claim, then per convention: files, newline count (`wc -l`), logical lines (newline count + 1
for a final unterminated line), non-blank lines (the scanner's convention), and the per-bucket breakdown. Every convention is printed
so nobody has to guess which one a figure used; a claim states ONE of them and names it.
"""
import os, sys, json, fnmatch, subprocess
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, project, knowledge, load_json, relp

def tracked_set(path):
    try:
        r = subprocess.run(["git", "-C", path, "ls-files", "-z", "--", "."], capture_output=True, text=True, encoding="utf-8", errors="surrogateescape", timeout=120)
        return {os.path.normpath(os.path.join(path, f)) for f in r.stdout.split("\0") if f} if r.returncode == 0 else None
    except Exception: return None

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    target = a[0]; p = project(); K = knowledge(); buckets = K.get("loc_buckets", {}); skip = set(K.get("skip_dirs", []))
    inv = load_json("analysis/inventory/inventory.json", {"units": {}, "roots": []})
    if target in inv["units"]:
        roots = inv.get("roots") or [p.get("repo", {}).get("path", "")]
        base = os.path.commonpath(roots) if len(roots) > 1 else roots[0]
        path = os.path.join(base, inv["units"][target]["path"])
    else: path = os.path.abspath(target if os.path.isabs(target) else os.path.join(ROOT, target))
    if not os.path.isdir(path): sys.exit(f"not a folder: {path}")
    globs = [g.strip() for g in a[a.index("--glob") + 1].split(",")] if "--glob" in a else None
    excl = [g.strip() for g in a[a.index("--exclude") + 1].split(",")] if "--exclude" in a else []
    all_files = "--all-files" in a
    tracked = None if "--raw" in a else tracked_set(path)
    mode = "tracked (git ls-files)" if tracked is not None else "raw (filesystem walk, skip dirs " + str(sorted(skip)) + ")"
    files = []
    if tracked is not None: cands = sorted(tracked)
    else:
        cands = []
        src_markers = set(K.get("source_dir_markers", ["src", "testsrc"])); hard_skip = {".git", "node_modules"}
        for dp, dns, fns in os.walk(path):
            under_src = any(part in src_markers for part in relp(dp, path).split("/"))
            dns[:] = [d for d in dns if not d.startswith(".") and d not in hard_skip and (under_src or d not in skip)]
            cands += [os.path.join(dp, f) for f in fns]
    non_bucket_files = 0; non_bucket_exts = []
    for f in cands:
        rel = relp(f, path).replace(os.sep, "/"); ext = os.path.splitext(f)[1].lower()
        for k in buckets:
            if f.lower().endswith(k) and len(k) > len(ext): ext = k
        if globs:
            if not any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(os.path.basename(rel), g) for g in globs): continue
            if not all_files and ext not in buckets:
                non_bucket_files += 1
                if ext not in non_bucket_exts and len(non_bucket_exts) < 5: non_bucket_exts.append(ext)
                continue
        elif ext not in buckets: continue
        if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(os.path.basename(rel), g) for g in excl): continue
        files.append((f, rel, buckets.get(ext, ext or "(none)")))
    tot = {"files": 0, "newline": 0, "logical": 0, "non_blank": 0}; per = {}; unterminated = 0
    for f, rel, b in files:
        try: data = open(f, "rb").read()
        except Exception: continue
        nl = data.count(b"\n"); lg = nl + (1 if data and not data.endswith(b"\n") else 0); nb = sum(1 for l in data.split(b"\n") if l.strip())
        if data and not data.endswith(b"\n"): unterminated += 1
        tot["files"] += 1; tot["newline"] += nl; tot["logical"] += lg; tot["non_blank"] += nb
        q = per.setdefault(b, {"files": 0, "newline": 0, "logical": 0, "non_blank": 0}); q["files"] += 1; q["newline"] += nl; q["logical"] += lg; q["non_blank"] += nb
    rule = (f"RULE: files below `{relp(path, ROOT) if path.startswith(ROOT) else path}` - {mode}; " + (f"globs {globs}" if globs else f"bucket extensions {sorted(buckets)}") +
            (" (--all-files: bucket extension not required)" if globs and all_files else "") + (f"; excluding {excl}" if excl else "") +
            f" -> {tot['files']} files; lines: {tot['newline']} newline-count (`wc -l`), {tot['logical']} logical (newline count + 1 per final unterminated line; {unterminated} such files), {tot['non_blank']} non-blank incl. comments (scanner convention). State exactly ONE convention beside a published figure and name it." +
            (f" {non_bucket_files} file(s) matched --glob but have no bucket extension and were excluded (examples: {non_bucket_exts}); pass --all-files to count them too." if globs and not all_files and non_bucket_files else ""))
    excluded_non_bucket = {"files": non_bucket_files, "extensions": non_bucket_exts}
    if "--json" in a: print(json.dumps({"path": path, "mode": mode, "globs": globs, "exclude": excl, "totals": tot, "unterminated_files": unterminated, "per_bucket": per, "excluded_non_bucket": excluded_non_bucket, "rule": rule}, indent=1)); return
    print(rule); print()
    print(f"{'bucket':14s} {'files':>7s} {'newline':>9s} {'logical':>9s} {'non-blank':>10s}")
    for b, q in sorted(per.items()): print(f"{b:14s} {q['files']:7d} {q['newline']:9d} {q['logical']:9d} {q['non_blank']:10d}")
    print(f"{'TOTAL':14s} {tot['files']:7d} {tot['newline']:9d} {tot['logical']:9d} {tot['non_blank']:10d}")

if __name__ == "__main__":
    main()
