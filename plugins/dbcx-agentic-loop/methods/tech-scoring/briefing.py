"""Brief extras of the tech-scoring method (called by `dbcx render`).

Every role gets the CRITERIA block (the rows an analyst must fill and a reviewer must check), the client's guardrails and the
requirement counts; the technology analyst and the standard reviewer additionally get the paths of that technology's knowledge
pack, because the engine can bind a knowledge pack per RUN but not per SCOPE - the analyst reads the seed and the verified-fact
cache of its own technology directly from the paths in the TECHNOLOGY KNOWLEDGE block.

digest_extra() adds the cross-technology score matrix to the consolidation digest: calibration is a comparison, so the
consolidator needs every technology's score for one criterion side by side, not one analysis after the other.
"""
import os, sys

from common import KNOWLEDGE, REQ_PATH, SCOPES_PATH, pack_dir, load_json, CLI


# ------------------------------------------------------------------ helpers
def criteria(cfg):
    return [c for c in (cfg.get("criteria") or []) if isinstance(c, dict) and c.get("id")]


def criteria_block(cfg):
    cs = criteria(cfg)
    if not cs:
        return "## CRITERIA\n(no criteria configured - run.json `criteria` is empty or still a placeholder; nothing can be scored)"
    total = sum(float(c.get("weight") or 0) for c in cs)
    lines = [f"## CRITERIA ({len(cs)} rows, total weight {total:g}; the weights are editable in the workbook and do not change what you score)", "",
             "| criterion_id | criterion | weight | guardrail | what it measures |", "|---|---|---|---|---|"]
    for c in cs:
        lines.append(f"| {c['id']} | {c.get('name', '')} | {c.get('weight', 0)} | {'YES' if c.get('guardrail') else 'no'} | "
                     + str(c.get("description", "")).replace("|", "/") + " |")
    lines += ["", "Score EVERY row, no additions and no omissions. A guardrail row (guardrail = YES) carries a hard client constraint: "
                  f"`guardrail_hit` is an explicit yes or no on every row, and a guardrail row scored below {cfg.get('scale', {}).get('guardrail_floor', 5)} is a guardrail hit."]
    return "\n".join(lines)


def guardrails_block(cfg):
    raw = str(cfg.get("decision", {}).get("guardrails") or "").strip()
    items = [x.strip() for x in raw.split(";") if x.strip()]
    if not items:
        return ""
    lines = [f"## CLIENT GUARDRAILS ({len(items)}) - a technology either holds these or it does not; say which and why", ""]
    lines += [f"{i}. {x}" for i, x in enumerate(items, 1)]
    lines.append("\nEvery guardrail is judged for every technology. Where the evidence does not settle it, the verdict is `unclear` and an open question exists - never a hopeful yes.")
    return "\n".join(lines)


def requirements_rows(cfg):
    req = load_json(REQ_PATH, {"requirements": [], "groups": [], "phase_values_in_scope": []})
    rows = req.get("requirements", [])
    if not rows:
        return [("REQUIREMENTS", f"state/requirements.json is EMPTY - score the criteria against the strategic context and the guardrails only, and give every affected row confidence low (`{CLI} requirements_to_json` or `{CLI} handover import requirements-set` fills it)")]
    by = {}
    for r in rows:
        by[r.get("group", "?")] = by.get(r.get("group", "?"), 0) + 1
    prio = sorted({str(r.get("priority") or "").strip() for r in rows} - {""})
    return [("REQUIREMENTS", f"{len(rows)} rows in state/requirements.json (" + ", ".join(f"{k}: {v}" for k, v in sorted(by.items())) + f") from {req.get('source_file', '?')}"),
            ("REQUIREMENT PRIORITIES", ", ".join(prio) or "(none in the workbook)"),
            ("PHASES IN SCOPE", ", ".join(req.get("phase_values_in_scope") or []) or "(all)")]


def tech_meta(scope):
    sj = load_json(SCOPES_PATH, {"scopes": {}})
    return (sj.get("scopes", {}).get(scope) or {}).get("meta", {}) or {}


def pack_paths(pack):
    """Folder + seed + verified-fact cache of a technology's knowledge pack, or None when there is no pack for it."""
    if not pack:
        return None
    d = pack_dir(pack)
    if not d:
        cand = os.path.join(KNOWLEDGE, "platforms", pack)
        d = cand if os.path.isdir(cand) else None
    if not d:
        return None
    files = []
    for fn, what in (("research-seed.md", "seed - hypotheses marked *(verify)*, confirm each against current documentation before you cite it"),
                     ("reference-cache.md", "verified facts from earlier engagements - usable, but re-check the version or plan"),
                     ("knowledge.json", "structured facts of the pack"), ("NOTES.md", "notes on the pack")):
        p = os.path.join(d, fn)
        if os.path.exists(p):
            files.append((p, what))
    return d, files


def knowledge_block(pack, tech):
    pp = pack_paths(pack)
    if not pp:
        return ("## TECHNOLOGY KNOWLEDGE\n"
                f"There is no knowledge pack for {tech or 'this technology'} (`pack` is empty in run.json `technologies`). Work from the vendor documentation and the reference file, "
                "and put every fact you verify into the reference file with `" + CLI + " reference add` so the next engagement starts from it.")
    d, files = pp
    lines = [f"## TECHNOLOGY KNOWLEDGE - pack `{os.path.basename(d)}` for {tech}", "",
             f"Pack folder (read directly, it is not bound to your scope by the engine): `{d}`", ""]
    lines += [f"- `{p}` - {what}" for p, what in files] or ["- (the pack folder holds no seed and no cache yet)"]
    lines.append("\nA pack fact is a starting point, never the evidence: the locator you publish is the vendor document or a PS-7-NNN row of the reference file.")
    return "\n".join(lines)


def technologies_block(cfg):
    sj = load_json(SCOPES_PATH, {"scopes": {}})
    sc = sj.get("scopes", {})
    if not sc:
        return ""
    lines = ["## TECHNOLOGIES IN THIS RUN (scope id -> technology; use the technology NAME in every table, the scope id only for file paths)", "",
             "| scope | technology | version / plan | knowledge pack | analysis |", "|---|---|---|---|---|"]
    for s in sorted(sc):
        m = sc[s].get("meta", {}) or {}
        lines.append(f"| {s} | {m.get('TECHNOLOGY', s)} | {m.get('VERSION OR PLAN', '')} | {m.get('PACK', '') or '-'} | analysis/scopes/{s}.md |")
    return "\n".join(lines)


# ------------------------------------------------------------------ engine entry points
def extra(role, scope, cfg, rnd):
    if role == "analyst":
        m = tech_meta(scope)
        rows = [("HEAD FIELDS OF YOUR OUTPUT", f"technology: {m.get('TECHNOLOGY', scope)} / version_or_plan: {m.get('VERSION OR PLAN', '')} / pack: {m.get('PACK', '') or '(none)'}")] + requirements_rows(cfg)
        return {"rows": rows, "blocks": [criteria_block(cfg), guardrails_block(cfg), knowledge_block(m.get("PACK"), m.get("TECHNOLOGY", scope))]}
    if role == "consolidator":
        return {"rows": requirements_rows(cfg) + [("SHORTLIST SIZE", cfg.get("shortlist", {}).get("size", 3))],
                "blocks": [technologies_block(cfg), criteria_block(cfg), guardrails_block(cfg)]}
    if role == "critic-client":
        return {"rows": requirements_rows(cfg), "blocks": [criteria_block(cfg), guardrails_block(cfg)]}
    if role == "critic-standard":
        m = tech_meta(scope)
        blocks = [criteria_block(cfg)]
        blocks.append(knowledge_block(m.get("PACK"), m.get("TECHNOLOGY", scope)) if m else technologies_block(cfg))
        return {"rows": [("TECHNOLOGY", m.get("TECHNOLOGY", scope)) if m else ("SCOPE", scope), ("VERSION OR PLAN", m.get("VERSION OR PLAN", ""))], "blocks": [b for b in blocks if b]}
    if role == "gate":
        return {"rows": [("WEIGHTS", "the criterion weights on the sheet Parameters are meant to be changed in the meeting - check that the ranking reacts and that no number is typed in")], "blocks": []}
    return {}


def digest_extra(which, scopes, cfg):
    if which != "SHORTLIST":
        return []
    cs = criteria(cfg)
    names = {}
    for s, d in scopes.items():
        names[s] = d.get("technology") or s
    order = sorted(scopes)
    lines = ["## Score matrix (calibration input: read one criterion across ALL technologies before you change anything)", "",
             "| criterion | " + " | ".join(names[s] for s in order) + " | spread |", "|---" * (len(order) + 2) + "|"]
    for c in cs:
        vals = []
        for s in order:
            row = next((r for r in scopes[s].get("criteria_scores", []) if r.get("criterion_id") == c["id"]), None)
            vals.append(row.get("score") if row else None)
        nums = [v for v in vals if isinstance(v, int)]
        spread = (max(nums) - min(nums)) if nums else 0
        lines.append(f"| {c['id']} {c.get('name', '')}{' [guardrail]' if c.get('guardrail') else ''} | "
                     + " | ".join("-" if v is None else str(v) for v in vals) + f" | {spread}{' <- check' if spread >= 4 else ''} |")
    lines += ["", "A spread of 4 or more on one criterion is where calibration usually belongs: compare the rationales, then move the outlier, not the majority.", ""]
    miss = [(s, [c["id"] for c in cs if not any(r.get("criterion_id") == c["id"] for r in scopes[s].get("criteria_scores", []))]) for s in order]
    miss = [(s, m) for s, m in miss if m]
    lines += ["## Completeness", ""]
    lines += [f"- {names[s]} ({s}): MISSING criterion rows {', '.join(m)}" for s, m in miss] or ["- every technology has a row for every criterion"]
    nolo = [(names[s], c.get("capability", "")) for s in order for c in scopes[s].get("capabilities", []) if not c.get("locator")]
    lines += ["", "## Capability rows without a source (a capability without a locator cannot be published as a fact)", ""]
    lines += [f"- {t}: {cap}" for t, cap in nolo[:30]] or ["- every capability row names a source"]
    gh = [(names[s], r.get("criterion_id"), r.get("rationale", "")[:90]) for s in order for r in scopes[s].get("criteria_scores", []) if r.get("guardrail_hit") == "yes"]
    lines += ["", f"## Guardrail hits reported by the technology analyses ({len(gh)}) - every one of them belongs in the Guardrails table", ""]
    lines += [f"- {t} / {cid}: {why}" for t, cid, why in gh] or ["- no technology analysis reports a guardrail hit; say so explicitly in a claim"]
    return lines
