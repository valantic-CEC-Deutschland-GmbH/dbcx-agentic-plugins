"""Row providers of the tech-scoring method for `dbcx build_excel` (pure functions over the loaded analysis JSON).

load(D, ROOT, INTERIM) adds the method's own inputs to the engine's base dict (D["scopes"], D["cons"], D["req"], D["status"], D["client_questions"]):
  D["criteria"]  the criteria of this run (merged configuration: method defaults <- engagement.json <- run.json)
  D["scale"]     score scale and guardrail floor,  D["shortlist_cfg"]  shortlist size
  D["sl"]        the SHORTLIST consolidation (ranking, calibration, guardrails) or None
  D["tech"]      scope id -> {name, version_or_plan, pack} taken from each scope analysis' head

Row keys map 1:1 to the `field` entries in deliverables.<lang>.json. The consolidation's `calibration` table is intentionally
not exposed as a dataset: it records how scores were aligned internally and is not client-facing.
"""
import os, sys

from common import project

_G = None


def _bind(label_fn):
    global _G
    _G = label_fn


def g(v, ctx=None):
    return _G(v, ctx) if _G else v


def load(D, ROOT, INTERIM):
    cfg = project()
    crit = cfg.get("criteria") or []
    D["criteria"] = [c for c in crit if isinstance(c, dict) and c.get("id")]
    D["scale"] = cfg.get("scale") if isinstance(cfg.get("scale"), dict) else {}
    D["shortlist_cfg"] = cfg.get("shortlist") if isinstance(cfg.get("shortlist"), dict) else {}
    D["sl"] = D["cons"].get("SHORTLIST")
    D["tech"] = {name: {"name": (d.get("technology") or name), "version_or_plan": d.get("version_or_plan", ""), "pack": d.get("pack") or ""}
                 for name, d in D["scopes"].items()}


def available(D, name):
    if name == "sl": return bool(D["sl"])
    if name == "criteria": return bool(D["criteria"])
    return None


def extra_context(D):
    return {"n_technologies": len(D["scopes"]), "n_criteria": len(D["criteria"]),
            "guardrail_floor": D["scale"].get("guardrail_floor", 5), "shortlist_size": D["shortlist_cfg"].get("size", 3)}


def _crit_map(D):
    return {c["id"]: c for c in D["criteria"]}


def _scopes(D):
    """(scope id, technology display name, analysis) in a stable order."""
    return [(s, D["tech"].get(s, {}).get("name", s), D["scopes"][s]) for s in sorted(D["scopes"])]


# ------------------------------------------------------------------ datasets
def ds_parameters_rows(D):
    """The editable model: one row per criterion (weight) plus the settings the formulas read by INDEX/MATCH on `key`."""
    rows = []
    for c in D["criteria"]:
        rows.append({"key": c["id"], "name": c.get("name", c["id"]), "type": "criterion", "value": c.get("weight", 0),
                     "guardrail": bool(c.get("guardrail")), "meaning": c.get("description", "")})
    sc = D["scale"]; sl = D["shortlist_cfg"]
    for key, value in (("guardrail_floor", sc.get("guardrail_floor", 5)), ("shortlist_size", sl.get("size", 3)), ("score_max", sc.get("max", 10))):
        # the key is a label token: the Key column shows its label and the formulas MATCH on "{L:<key>}", so no raw key reaches the workbook
        rows.append({"key": key, "type": "control", "name": g(f"_name_{key}"), "value": value, "guardrail": False, "meaning": g(f"_meaning_{key}")})
    return rows


def ds_scores(D):
    cm = _crit_map(D); rows = []
    for sid, tech, d in _scopes(D):
        by_id = {r.get("criterion_id"): r for r in d.get("criteria_scores", [])}
        order = [c["id"] for c in D["criteria"]] + [k for k in by_id if k not in cm]
        for cid in order:
            r = by_id.get(cid)
            if not r: continue
            c = cm.get(cid, {})
            rows.append({"row_id": f"{tech} {cid}", "technology": tech, "scope": sid, "criterion_id": cid, "criterion": c.get("name", cid),
                         "score": r.get("score"), "guardrail_hit": r.get("guardrail_hit", ""), "confidence": r.get("confidence", ""),
                         "rationale": r.get("rationale", ""), "client_evidence": r.get("client_evidence", []), "vendor_evidence": r.get("vendor_evidence", []),
                         "version_or_plan": D["tech"].get(sid, {}).get("version_or_plan", "")})
    return rows


def ds_capabilities(D):
    return [{"technology": tech, "capability": c.get("capability", ""), "available": c.get("available", "unknown"),
             "version_or_plan": c.get("version_or_plan") or D["tech"].get(sid, {}).get("version_or_plan", ""),
             "locator": c.get("locator", []), "notes": c.get("notes", "")}
            for sid, tech, d in _scopes(D) for c in d.get("capabilities", [])]


def ds_risks(D):
    order = {"blocker": 0, "major": 1, "minor": 2}
    rows = [{"technology": tech, "risk": r.get("risk", ""), "impact": r.get("impact", "minor"), "affects_criterion": r.get("affects_criterion"),
             "mitigation": r.get("mitigation", ""), "evidence": r.get("evidence", [])}
            for sid, tech, d in _scopes(D) for r in d.get("risks", [])]
    rows.sort(key=lambda r: (order.get(r["impact"], 3), r["technology"]))
    return rows


def _evidence(D, tech, only=None):
    """Evidence of a technology's score rows (optionally only the given criterion ids): what a ranking or guardrail row rests on."""
    out = []
    for r in ds_scores(D):
        if r["technology"] == tech and (only is None or r["criterion_id"] in only):
            for e in list(r["client_evidence"] or []) + list(r["vendor_evidence"] or []):
                if e not in out: out.append(e)
    return out


def ds_ranking(D):
    """One row per technology from the consolidation; technologies without a ranking row are appended so no scored technology disappears.
    evidence = the technology's score evidence (the formula total is computed from exactly those rows)."""
    sl = D["sl"] or {}
    rows = [{"technology": r.get("technology", ""), "rank": r.get("rank"), "shortlisted": bool(r.get("shortlisted")),
             "weighted_total_note": r.get("weighted_total_note", ""), "fit_statement": r.get("fit_statement", ""),
             "partner_explanation": r.get("partner_explanation", "")} for r in sl.get("ranking", [])]
    named = {r["technology"] for r in rows}
    for sid, tech, d in _scopes(D):
        if tech not in named:
            rows.append({"technology": tech, "rank": None, "shortlisted": False, "weighted_total_note": "", "fit_statement": "", "partner_explanation": ""})
    for r in rows: r["evidence"] = _evidence(D, r["technology"])
    rows.sort(key=lambda r: (r["rank"] if isinstance(r["rank"], int) and r["rank"] > 0 else 999, r["technology"]))
    return rows


def ds_guardrails(D):
    """evidence = the claim ids the note cites plus the evidence of the technology's guardrail-criterion scores."""
    import re
    sl = D["sl"] or {}; gcrit = {c["id"] for c in D["criteria"] if c.get("guardrail")}
    return [{"technology": r.get("technology", ""), "guardrail": r.get("guardrail", ""), "hit": r.get("hit", "unclear"), "note": r.get("note", ""),
             "evidence": re.findall(r"\bC-[\w.-]+-\d{3}\b", r.get("note", "")) + _evidence(D, r.get("technology", ""), gcrit)}
            for r in sl.get("guardrails", [])]


DATASETS = {"parameters_rows": ds_parameters_rows, "scores": ds_scores, "capabilities": ds_capabilities,
            "risks": ds_risks, "ranking": ds_ranking, "guardrails": ds_guardrails}
