#!/usr/bin/env python3
"""Release the consolidated requirement set into the engine's requirements shape: analysis/consolidated/SET.json -> state/requirements.json.

Usage: dbcx export_requirements [--force] [--quiet]
Why: every downstream method (`tech-scoring`, `tech-fit-estimation`, a later `code-analysis` run) reads a client requirement list from
state/requirements.json - the same file `dbcx requirements_to_json` writes when the list comes from a client workbook. This tool writes it
from THIS run's own passed set, so a chained run imports the released `requirements-set` artefact and finds the familiar shape.

Mapping SET.json -> state/requirements.json:
  id = req_id | group = functional for type functional, technical for type technical and nfr (the engine's shape knows two groups;
  the untouched `type` travels along as an extra key, so nothing is lost) | epic | title | description
  acceptance_criteria = acceptance_hint | exclusions = "" (this method keeps exclusions in the requirement text and in the client questions)
  references = the counterpart ids of the FR<->TR cross-check | phase = release | sources = source_locators | priority
  phase_values_in_scope = the first configured release token (requirements.releases) that occurs in the set - the "first go-live" of the KPIs
Guard: refuses while SET.json is `status: draft` (mid-gauntlet) unless --force; reports whether the SET gauntlet passed.
"""
import os, sys, json, glob

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, REQ_PATH, project, load_json, save_json, CLI

SET = "analysis/consolidated/SET.json"


def gauntlet_passed(scope="SET"):
    res = sorted(glob.glob(os.path.join(ROOT, "analysis", "gauntlet", scope, "round*-result.json")))
    if not res: return None
    return bool(load_json(res[-1], {}).get("passed"))


def main():
    a = sys.argv[1:]; force = "--force" in a; quiet = "--quiet" in a
    p = project()
    s = load_json(SET, None)
    if not s: sys.exit(f"missing {SET} - convert the consolidation first (`{CLI} md_to_json requirements_set analysis/consolidated/SET.md`)")
    if s.get("status") != "final" and not force:
        sys.exit(f"{SET} is `status: {s.get('status')}` - the requirement set is exported when the consolidation is final "
                 f"(the orchestrator sets it after the gauntlet passed). --force with a logged assumption to export a draft.")
    passed = gauntlet_passed()
    refs = {}
    for c in s.get("crosscheck", []) or []:
        fr, tr = (c.get("functional_requirement") or "").strip(), (c.get("technical_requirement") or "").strip()
        if fr and fr.lower() != "none" and tr: refs.setdefault(fr, []).append(tr)
        if tr and fr and fr.lower() != "none": refs.setdefault(tr, []).append(fr)
    rows = []
    for r in s.get("requirements", []) or []:
        t = r.get("type") or "functional"
        rows.append({"id": r.get("req_id"), "group": "functional" if t == "functional" else "technical", "type": t,
                     "epic": r.get("epic", ""), "title": r.get("title", ""), "description": r.get("description", ""),
                     "acceptance_criteria": r.get("acceptance_hint", ""), "exclusions": "",
                     "references": sorted(set(refs.get(r.get("req_id"), []))), "phase": r.get("release", ""),
                     "sources": r.get("source_locators", []) or [], "priority": r.get("priority", ""),
                     "status": r.get("status", ""), "catalogue_ref": r.get("catalogue_ref")})
    releases = [x for x in (p.get("requirements", {}).get("releases") or []) if x.lower() != "unknown"]
    present = [x for x in releases if any((row["phase"] or "").strip().lower() == x.lower() for row in rows)]
    out = {"source_file": SET, "source_run": p.get("run_name") or os.path.basename(ROOT),
           "requirements": rows, "phase_values_in_scope": present[:1] or (releases[:1] or ["MVP"]),
           "legend": {"group": "functional | technical (non-functional requirements travel as technical; the original type is in `type`)",
                      "sources": "corpus locators (SRC-nnn#anchor) or the literal `inferred`",
                      "status": "confirmed | inferred | question (see the D2 workbook, sheet Requirements)"}}
    save_json(REQ_PATH, out)
    if not quiet:
        by = {}
        for r in rows: by[r["type"]] = by.get(r["type"], 0) + 1
        traced = sum(1 for r in rows if [x.lower() for x in r["sources"]] != ["inferred"] and r["sources"])
        print(f"exported {len(rows)} requirements -> state/requirements.json ({', '.join(f'{k} {v}' for k, v in sorted(by.items()))}; "
              f"{traced} with a source locator; first go-live {out['phase_values_in_scope']}; SET gauntlet "
              f"{'passed' if passed else ('not passed' if passed is False else 'not aggregated')})")
        print(f"a later run imports the released artefact with `{CLI} handover import requirements-set` (it materialises the same file)")


if __name__ == "__main__":
    main()
