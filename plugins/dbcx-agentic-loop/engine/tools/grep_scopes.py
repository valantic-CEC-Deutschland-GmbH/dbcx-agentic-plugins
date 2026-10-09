#!/usr/bin/env python3
"""Cross-scope sweep: where else does a figure or phrase live?

Usage: dbcx grep_scopes "<string or regex>" [--fixed] [--all]
Searches every analysis Markdown and JSON (units, inventory, consolidated, summaries) and the reference file; --all adds docs/ and
deliverables/interim. Prints file:line: text. Use it BEFORE and AFTER a correction: the after-run must show only the deliberate
supersession sentences.
"""
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, REF_DIR, relp

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    pat = re.compile(re.escape(a[0]) if "--fixed" in a else a[0], re.I)
    roots = ["analysis/units", "analysis/scopes", "analysis/inventory", "analysis/consolidated", "analysis/summaries", relp(REF_DIR, ROOT)] + (["docs", "deliverables/interim"] if "--all" in a else [])
    n = 0
    for r in roots:
        for f in sorted(glob.glob(os.path.join(ROOT, r, "**", "*"), recursive=True)):
            if not f.endswith((".md", ".json")) or "digest-" in f: continue
            try: lines = open(f, encoding="utf-8", errors="ignore").read().splitlines()
            except Exception: continue
            for i, l in enumerate(lines, 1):
                if pat.search(l): n += 1; print(f"{relp(f, ROOT)}:{i}: {l.strip()[:160]}")
    print(f"{n} occurrence(s) of {a[0]!r}")

if __name__ == "__main__":
    main()
