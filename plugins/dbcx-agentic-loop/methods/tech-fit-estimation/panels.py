"""Dashboard panel of tech-fit-estimation (engine hook methods/<m>/panels.py, read by `dbcx dashboard`): the view "Impact per system"
(de "Auswirkung je System") of state/impact.json - the scope step's matrix row x system with the impact text, its source (pre-fill, triage,
override) and status (applied automatically, overridden, disputed). Every cell can be edited from the dashboard (add a system to a row,
remove it, edit the impact text): an optional override the lead sends through the inbox; `dbcx inbox apply` records it with
`dbcx impact override` and the next wave picks up the changed work package. Nothing waits for it.

the view "Gap decisions" (de "Lückenentscheidungen") of state/architect.json - one row per gap (<row>@<reporting system>), the
receiving system's cell carries the decision and the solution. An optional override: click another system's cell (route the gap there; the
reporting system's own cell = overrule) or edit the solution text; `dbcx inbox apply` records it with `dbcx architect override`. Nothing waits.

panels(cfg) -> [panel]; check(entry, cfg) -> error text or None (the dashboard refuses the edit); apply(entry, cfg) -> outcome line.
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tfe_model as TM

L = {"en": {"title": "Impact per system", "applied": "Applied automatically", "rows": "rows", "impacts": "impacts", "none": "touch no system", "none1": "touches no system",
            "disputed": "disputed", "overridden": "overridden", "changes": "work-package changes wait for the next wave", "none_note": "touches no system of this run",
            "source": {"prefill": "named in the client's list (pre-fill)", "triage": "added by the triage", "override": "set on the dashboard"},
            "status": {"applied": "applied automatically", "overridden": "overridden on the dashboard", "disputed": "a critic disputes the claim behind it"},
            "by": {"agents": "estimated by the agents", "partner": "estimated by the partner", "client": "estimated by the client", "team": "estimated by the team"}},
     "de": {"title": "Auswirkung je System", "applied": "Automatisch übernommen", "rows": "Zeilen", "impacts": "Auswirkungen", "none": "berühren kein System", "none1": "berührt kein System",
            "disputed": "bestritten", "overridden": "übersteuert", "changes": "Änderungen an Arbeitspaketen warten auf die nächste Welle", "none_note": "berührt kein System dieses Laufs",
            "source": {"prefill": "in der Kundenliste genannt (Vorbelegung)", "triage": "von der Triage ergänzt", "override": "im Dashboard gesetzt"},
            "status": {"applied": "automatisch übernommen", "overridden": "im Dashboard übersteuert", "disputed": "ein Kritiker bestreitet die Aussage dahinter"},
            "by": {"agents": "von den Agenten geschätzt", "partner": "vom Partner geschätzt", "client": "vom Kunden geschätzt", "team": "vom Team geschätzt"}}}


def _impact(cfg):
    return TM.load(cfg.get("_run_dir"), TM.IMPACT_PATH, None)


def panels(cfg):
    """the "Impact per system" panel while state/impact.json exists (the scope step applied it), else none"""
    doc = _impact(cfg)
    if not doc: return architect_panels(cfg)
    lang = (cfg.get("languages") or {}).get("deliverable", "en"); t = L.get(lang, L["en"])
    reqs = {r["id"]: r for r in TM.requirements(cfg.get("_run_dir"))}; by_row = {}
    for c in doc.get("cells") or []: by_row.setdefault(c["row"], []).append(c)
    rows = []
    for rid in doc.get("rows") or []:
        r = reqs.get(rid) or {}; n = (doc.get("none") or {}).get(rid)
        rows.append({"id": rid, "title": r.get("title") or "", "group": r.get("group") or "", "note": (t["none_note"] + (": " + n["reason"] if n.get("reason") else "")) if n else "",
                     "cells": [{"column": c["system"], "on": bool(c["affected"]), "text": c.get("impact") or "", "source": c["source"], "status": c["status"], "reason": c.get("reason") or "",
                                "claims": list(c.get("claims") or [])} for c in by_row.get(rid, [])]})
    cells = doc.get("cells") or []; aff = [c for c in cells if c["affected"]]
    dis = sum(1 for c in cells if c["status"] == "disputed"); ov = sum(1 for c in cells if c["status"] == "overridden"); net = TM.net_changes(doc.get("changes") or [])
    sub = [f"{len(doc.get('rows') or [])} {t['rows']}", f"{len(aff)} {t['impacts']}", f"{len(doc.get('none') or {})} {t['none1'] if len(doc.get('none') or {}) == 1 else t['none']}"] + ([f"{ov} {t['overridden']}"] if ov else []) + ([f"{dis} {t['disputed']}"] if dis else [])
    return [{"id": "impact", "title": t["title"], "subtitle": " · ".join(sub),
             "status": {"label": t["applied"], "tone": "warn" if dis else "ok", "at": doc.get("applied_at")},
             "columns": [{"id": s["id"], "label": s.get("label") or s["id"], "note": t["by"].get(s.get("estimated_by") or "agents", "") + (f" ({s['owner_label']})" if s.get("owner_label") else "")} for s in doc.get("systems") or []],
             "rows": rows, "edit": {"actions": ["add", "remove", "edit"]}, "legend": {"source": t["source"], "status": t["status"]},
             "changes": [{"key": k, "change": v} for k, v in net.items()], "changes_note": t["changes"] if net else ""}] + architect_panels(cfg)


def check(entry, cfg):
    """the dashboard's check of an edit before it reaches the inbox (the same rules `dbcx impact override` applies)"""
    if entry.get("panel") == "architect": return architect_check(entry, cfg)
    if entry.get("panel") != "impact": return f"unknown panel {entry.get('panel')}"
    sys.path.insert(0, os.path.join(HERE, "tools")); import impact
    return impact.override_error(cfg, entry.get("row"), entry.get("column"), entry.get("action"), entry.get("text"), entry.get("reason"))


def apply(entry, cfg):
    """`dbcx inbox apply` of a panel_edit entry: `dbcx impact override ...` records it (refused -> RuntimeError, the entry stays unprocessed)"""
    if entry.get("panel") == "architect":
        e = architect_check(entry, cfg)
        if e: raise RuntimeError(e)
        return _run(cfg, ["architect.py", "override"] + architect_args(entry, cfg), "dbcx architect override failed")
    a = [sys.executable, os.path.join(HERE, "tools", "impact.py"), "override", entry.get("action") or "", entry.get("row") or "", entry.get("column") or "",
         "--by", entry.get("by") or "lead", "--entry", entry.get("client_id") or ""]
    if entry.get("text"): a += ["--impact", entry["text"]]
    if entry.get("reason"): a += ["--reason", entry["reason"]]
    r = subprocess.run(a, cwd=cfg.get("_run_dir") or ".", capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode: raise RuntimeError(out or "dbcx impact override failed")
    return out.splitlines()[0] if out else "override recorded"


# ------------------------------------------------------------------ "Gap decisions" (state/architect.json)
A = {"en": {"title": "Gap decisions", "gaps": "gaps", "final": "final", "note": "reported by {s}: {r}", "changes": "follow-up work packages wait for the next wave",
            "source": {"prefill": "-", "triage": "decided by the architect", "override": "set on the dashboard"},
            "status": {"applied": "applied automatically", "overridden": "overridden on the dashboard", "disputed": "a critic disputes the claim behind it"},
            "decision": {"overrule": "back to the reporting system", "route-estimated": "routed", "route-landscape": "outside the run", "reduce-to-standard": "reduced to the standard"},
            "outside": "landscape system, not estimated in this run"},
     "de": {"title": "Lückenentscheidungen", "gaps": "Lücken", "final": "endgültig", "note": "gemeldet von {s}: {r}", "changes": "Folge-Arbeitspakete warten auf die nächste Welle",
            "source": {"prefill": "-", "triage": "vom Architekten entschieden", "override": "im Dashboard gesetzt"},
            "status": {"applied": "automatisch übernommen", "overridden": "im Dashboard übersteuert", "disputed": "ein Kritiker bestreitet die Aussage dahinter"},
            "decision": {"overrule": "zurück an das meldende System", "route-estimated": "weitergeleitet", "route-landscape": "außerhalb des Laufs", "reduce-to-standard": "auf den Standard reduziert"},
            "outside": "System der Landschaft, nicht Teil dieses Laufs"}}


def _arch(cfg):
    import gaps as G
    return TM.load(cfg.get("_run_dir"), G.ARCH_PATH, None)


def architect_panels(cfg):
    """the "Gap decisions" panel while state/architect.json has decisions, else none"""
    doc = _arch(cfg)
    if not doc or not doc.get("decisions"): return []
    lang = (cfg.get("languages") or {}).get("deliverable", "en"); t = A.get(lang, A["en"]); reqs = {r["id"]: r for r in TM.requirements(cfg.get("_run_dir"))}
    cols = [{"id": s["id"], "label": s.get("label") or s["id"], "note": L.get(lang, L["en"])["by"].get(s.get("estimated_by") or "agents", "")} for s in doc.get("systems") or []]
    known = {c["id"] for c in cols}
    cols += [{"id": d["to"], "label": d.get("to_label") or d["to"], "note": t["outside"]} for d in doc["decisions"] if d["to"] not in known and not known.add(d["to"])]
    reasons = {}
    for b in (TM.load(cfg.get("_run_dir"), "work/architect-plan.json", {}) or {}).get("batches") or []:
        for g in b.get("gaps") or []: reasons[g["id"]] = "; ".join(x["reason"] for x in g.get("sources") or [] if x.get("reason"))
    rows = [{"id": d["id"], "title": (reqs.get(d["row"]) or {}).get("title") or "", "group": (reqs.get(d["row"]) or {}).get("group") or "",
             "note": t["note"].format(s=d["from_system"], r=reasons.get(d["id"]) or "-") + (f" · {t['final']}" if d.get("final") else ""),
             "cells": [{"column": d["to"], "on": True, "text": f"{t['decision'].get(d['decision'], d['decision'])}: {d.get('solution') or d.get('reasoning') or ''}", "source": "override" if d["status"] == "overridden" else "triage",
                        "status": d["status"], "reason": d.get("reasoning") or "", "claims": list(d.get("claims") or [])}]} for d in doc["decisions"]]
    net = TM.net_changes(doc.get("changes") or []); dis = sum(1 for d in doc["decisions"] if d["status"] == "disputed")
    by = {}
    for d in doc["decisions"]: by[d["decision"]] = by.get(d["decision"], 0) + 1
    return [{"id": "architect", "title": t["title"], "subtitle": " · ".join([f"{len(doc['decisions'])} {t['gaps']}"] + [f"{v} {t['decision'].get(k, k)}" for k, v in by.items()]),
             "status": {"label": L.get(lang, L["en"])["applied"], "tone": "warn" if dis else "ok", "at": doc.get("applied_at")}, "columns": cols, "rows": rows,
             "edit": {"actions": ["add", "edit"]}, "legend": {"source": t["source"], "status": t["status"]},
             "changes": [{"key": k, "change": v} for k, v in net.items()], "changes_note": t["changes"] if net else ""}]


def architect_args(entry, cfg):
    """a cell edit -> `dbcx architect override` arguments: another system's cell = route there (the reporting system = overrule, a landscape
    column = route-landscape with the text as the client assumption); the current cell's text = a new solution for the same decision"""
    doc = _arch(cfg) or {}; d = next((x for x in doc.get("decisions") or [] if x["id"] == entry.get("row")), None) or {}
    col, text = entry.get("column") or "", (entry.get("text") or "").strip(); reason = (entry.get("reason") or "").strip() or "changed on the dashboard"
    syss = {s["id"] for s in doc.get("systems") or []}
    if entry.get("action") == "edit": dec, to = d.get("decision") or "", d.get("to") or ""
    elif col == d.get("from_system"): dec, to = "overrule", col
    else: dec, to = ("route-estimated" if col in syss else "route-landscape"), col
    if dec == "overrule" and not (entry.get("reason") or "").strip() and text: reason = text   # an overrule's text is its reasoning
    a = [entry.get("row") or "", dec, "--to", to, "--reason", reason, "--by", entry.get("by") or "lead", "--entry", entry.get("client_id") or ""]
    if text and dec != "overrule": a += ["--solution", text]
    if dec == "route-landscape" and entry.get("action") != "edit": a += ["--assumption", text]
    return a


def architect_check(entry, cfg):
    """the dashboard's check of a gap-decision edit (the rules of `dbcx architect override`)"""
    if entry.get("action") not in ("add", "edit"): return "a gap keeps a decision - click the system that should carry it, or edit the solution text"
    if not (entry.get("text") or "").strip() and entry.get("action") == "edit": return "the solution text is required"
    sys.path.insert(0, os.path.join(HERE, "tools")); import architect
    a = architect_args(entry, cfg); opt = lambda k: a[a.index(k) + 1] if k in a else ""
    return architect.override_error(cfg, a[0], a[1], opt("--to"), opt("--reason"), opt("--solution"), opt("--assumption"))


def _run(cfg, tool_args, fail):
    r = subprocess.run([sys.executable, os.path.join(HERE, "tools", tool_args[0])] + tool_args[1:], cwd=cfg.get("_run_dir") or ".", capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode: raise RuntimeError(out or fail)
    return out.splitlines()[0] if out else "override recorded"
