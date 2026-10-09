#!/usr/bin/env python3
"""Scopes of the tech-scoring method: one scope per technology in the run configuration -> state/scopes.json
(consumed by `dbcx plan_waves`, `dbcx render`, `dbcx progress`).

Usage: dbcx discover [--json]
Input: run.json (or engagement.json) `technologies`: [{"name": "Shopware", "pack": "shopware", "version_or_plan": "6.6 Evolve"}, ...]
       a plain string entry is accepted as a name without pack and version.
Output: one scope per technology, group `technology`, size = number of criteria, no light pass (a technology is never
       scored "essentials only": the criteria set is the same for every candidate, otherwise the ranking is not comparable).

Scope ids are short codes T-01, T-02, ... and NOT the technology names: the engine's hook denies any web query that contains
a scope name longer than five characters (it protects client scope names), and in this method the standard reviewer and the
researcher must be able to search the vendor documentation by product name. The display name, the version or plan and the
knowledge pack travel in `meta` (TECHNOLOGY, VERSION OR PLAN, PACK) and appear in every rendered brief.
"""
import json, os, sys

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, KNOWLEDGE, SCOPES_PATH, project, pack_dir, save_json, is_placeholder, CLI


def entries(cfg):
    t = cfg.get("technologies")
    if isinstance(t, str) or t is None or (isinstance(t, list) and not t):
        sys.exit(f"run.json `technologies` is empty or still a placeholder ({t!r}).\n"
                 f"Fill it with one entry per technology to evaluate:\n"
                 f'  "technologies": [{{"name": "Shopware", "pack": "shopware", "version_or_plan": "6.6 Evolve"}}, ...]\n'
                 f"`pack` is the name of a knowledge pack (`{CLI} pack list`) or null; `{CLI} check_fill` lists the open placeholders.")
    out = []
    for e in t:
        if isinstance(e, str): e = {"name": e}
        if not isinstance(e, dict) or not str(e.get("name") or "").strip():
            sys.exit(f"run.json `technologies` holds an entry without a name: {e!r}")
        out.append({"name": str(e["name"]).strip(), "pack": (e.get("pack") or "").strip() if isinstance(e.get("pack"), str) else "",
                    "version_or_plan": str(e.get("version_or_plan") or "").strip()})
    return out


def main():
    cfg = project()
    techs = entries(cfg)
    crit = [c for c in (cfg.get("criteria") or []) if isinstance(c, dict) and c.get("id")]
    names = [t["name"] for t in techs]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup: sys.exit(f"duplicate technology names in run.json `technologies`: {', '.join(dup)} - one scope per technology")
    warn = []
    if not crit: warn.append("no criteria configured (method defaults `criteria` empty and run.json does not set them) - nothing can be scored")
    else:
        total = sum(float(c.get("weight") or 0) for c in crit)
        if total <= 0: warn.append("the criteria weights sum to 0 - every weighted total would be empty")
    scopes = {}
    for i, t in enumerate(techs, 1):
        sid = f"T-{i:02d}"
        pack = t["pack"]
        pd = pack_dir(pack) if pack else None
        if pack and not pd:
            cand = os.path.join(KNOWLEDGE, "platforms", pack)
            pd = cand if os.path.isdir(cand) else None
            if not pd: warn.append(f"{sid} {t['name']}: knowledge pack '{pack}' not found - the analyst works from vendor documentation only")
        if not t["version_or_plan"] or is_placeholder(t["version_or_plan"]):
            warn.append(f"{sid} {t['name']}: no version_or_plan - every score and capability would be about the product family instead of a subject that can be verified")
        scopes[sid] = {"group": "technology", "depends_on": [], "size": len(crit) or 1, "light": False,
                       "light_reason": "", "skip": False,
                       "meta": {"TECHNOLOGY": t["name"], "VERSION OR PLAN": t["version_or_plan"], "PACK": pack,
                                "KNOWLEDGE PACK FOLDER": pd or ""}}
    out = {"noun": (cfg.get("unit") or {}).get("noun", "Technology"), "method": "tech-scoring",
           "source": "run.json technologies", "criteria": [c["id"] for c in crit], "scopes": scopes}
    save_json(SCOPES_PATH, out)
    if "--json" in sys.argv:
        print(json.dumps(out, indent=1, ensure_ascii=False)); return
    print(f"{len(scopes)} scopes -> state/scopes.json ({len(crit)} criteria per technology, all full passes)")
    for sid, s in scopes.items():
        m = s["meta"]; print(f"  {sid}  {m['TECHNOLOGY']:28s} {m['VERSION OR PLAN'] or '(no version/plan)':28s} pack {m['PACK'] or '-'}")
    for w in warn: print("WARNING", w)
    print(f"next: {CLI} plan_waves, then `{CLI} status scope <id> '{{\"wave\": n, \"status\": \"open\"}}'` for every scope")


if __name__ == "__main__":
    main()
