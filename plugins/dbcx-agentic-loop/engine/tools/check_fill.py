#!/usr/bin/env python3
"""List every unresolved placeholder in the PROJECT (run.json, requirements_mapping.json, run + engagement overrides/, reference/). Exit 1 while any remain.
Usage: dbcx check_fill [--quiet]     Placeholders: '<<PLACEHOLDER: ...>>', '<<UPPER_CASE>>', 'TODO:'."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as PROJECT, PLACEHOLDER_RE, P, PP, relp

SCAN = ["run.json", "requirements_mapping.json", "overrides", "CLAUDE.md", "docs/PLAN.md", "../../engagement.json", "../../overrides", "../../reference"]

def main():
    quiet = "--quiet" in sys.argv; hits = []; seen = set()
    for top in SCAN:
        p = PP(top[6:]) if top.startswith("../../") else P(top)
        if p in seen: continue   # a run that is its own engagement: overrides/ once
        seen.add(p)
        files = [p] if os.path.isfile(p) else ([os.path.join(dp, f) for dp, dn, fn in os.walk(p) for f in fn] if os.path.isdir(p) else [])
        for f in files:
            if not f.endswith((".json", ".md", ".py")): continue
            for n, line in enumerate(open(f, encoding="utf-8", errors="ignore"), 1):
                if PLACEHOLDER_RE.search(line): hits.append((relp(f, PROJECT), n, line.strip()[:140]))
    if not quiet:
        for f, n, l in hits: print(f"{f}:{n}: {l}")
    print(f"{len(hits)} unresolved placeholder(s) in {PROJECT}" + ("" if hits else " - project is filled"))
    sys.exit(1 if hits else 0)

if __name__ == "__main__":
    main()
