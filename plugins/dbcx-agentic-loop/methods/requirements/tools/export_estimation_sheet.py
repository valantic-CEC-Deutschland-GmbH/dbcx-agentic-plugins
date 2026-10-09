#!/usr/bin/env python3
"""Optional export of the consolidated set into the client's EstimationSheet shape: deliverables/Requirements_EstimationSheet.xlsx.

Usage: dbcx export_estimation_sheet [--force]
Off by default. Enable with run.json -> `deliverables.estimation_sheet_export.enabled: true` (a bare boolean directly under
`deliverables` breaks `dbcx status init`). --force exports without the flag (log the reason).

Shape (the client's own template, so their columns line up when they paste it in): two sheets `Functional Requirements` and
`Technical Requirements`, row 1 = group header, row 2 = column headers, data from row 3; A = #, B = ID of this run, C = Epic,
D = Title, E = Description, and the open question in R (functional) / O (technical). Formula-free by design: this file exists to be
pasted into the client's estimation workbook, where columns F.. carry THEIR priorities, releases and estimation formulas.
Non-functional requirements travel on the technical sheet (the template has no third sheet) with `[non-functional]` in front of the title.
The deliverable of record stays deliverables/Requirements.xlsx - this is a convenience export, not a second source of truth.
"""
import os, sys

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, project, load_json, CLI, relp
from xl_style import pages_wide
from lint_deliverable import visible_widths
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

SET = "analysis/consolidated/SET.json"
HEAD = ["#", "ID", "Epic", "Title", "Description"]


def enabled(cfg):
    v = (cfg.get("deliverables") or {}).get("estimation_sheet_export")
    if isinstance(v, dict): return bool(v.get("enabled")), v.get("file", "Requirements_EstimationSheet.xlsx")
    return bool(v), "Requirements_EstimationSheet.xlsx"


def sheet(wb, title, rows, question_col, subtitle):
    ws = wb.create_sheet(title)
    ws.cell(row=1, column=1, value=subtitle).font = Font(name="Segoe UI", size=10, bold=True, color="3C4BC8")
    for i, h in enumerate(HEAD, 1):
        c = ws.cell(row=2, column=i, value=h); c.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="3C4BC8")
    qc = ws.cell(row=2, column=question_col, value="Open Question"); qc.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF"); qc.fill = PatternFill("solid", fgColor="3C4BC8")
    for i, r in enumerate(rows, 1):
        rr = i + 2
        for col, v in ((1, i), (2, r["id"]), (3, r["epic"]), (4, r["title"]), (5, r["description"])):
            c = ws.cell(row=rr, column=col, value=v); c.font = Font(name="Segoe UI", size=10); c.alignment = Alignment(wrap_text=col == 5, vertical="top")
        if r.get("question"): ws.cell(row=rr, column=question_col, value=r["question"]).alignment = Alignment(wrap_text=True, vertical="top")
    for col, w in ((1, 6), (2, 12), (3, 24), (4, 40), (5, 90), (question_col, 50)): ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w
    ws.freeze_panes = "C3"
    ws.sheet_properties.tabColor = "3C4BC8"   # valantic palette "result" tab role
    ws.page_setup.orientation = "landscape"; ws.page_setup.fitToWidth = pages_wide(visible_widths(ws)); ws.page_setup.fitToHeight = 0   # the engine's page rule over the printed columns (F.. included), so the hygiene lint agrees
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return len(rows)


def main():
    cfg = project(); on, fname = enabled(cfg); de = cfg["languages"]["deliverable"] == "de"
    t = lambda d, e: d if de else e   # the column heads are the template's contract (English); the texts follow the deliverable language
    if not on and "--force" not in sys.argv:
        print(f"estimation-sheet export is off (run.json deliverables.estimation_sheet_export.enabled = false) - nothing written"); return
    s = load_json(SET, None)
    if not s: sys.exit(f"missing {SET} - convert the consolidation first (`{CLI} md_to_json requirements_set analysis/consolidated/SET.md`)")
    q = {x.get("id"): x.get("question", "") for x in s.get("open_questions", []) or []}
    fr, tr = [], []
    for r in s.get("requirements", []) or []:
        row = {"id": r.get("req_id"), "epic": r.get("epic", ""), "title": r.get("title", ""), "description": r.get("description", ""),
               "question": q.get(r.get("req_id"), "") or (t("offener Punkt: ", "open point: ") + (r.get("acceptance_hint") or "") if r.get("status") == "question" else "")}
        if r.get("type") == "functional": fr.append(row)
        else:
            if r.get("type") == "nfr": row["title"] = t("[nichtfunktional] ", "[non-functional] ") + row["title"]
            tr.append(row)
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    n1 = sheet(wb, "Functional Requirements", fr, 18, t(f"Anforderungen an {cfg.get('system', {}).get('type', 'das System')} - fachlich (aus dem Anforderungssatz dieser Studie; die Spalten ab F bleiben Ihre)", f"Requirements for {cfg.get('system', {}).get('type', 'the system')} - functional (from the requirement set of this study; columns F.. stay yours)"))
    n2 = sheet(wb, "Technical Requirements", tr, 15, t(f"Anforderungen an {cfg.get('system', {}).get('type', 'das System')} - technisch und nichtfunktional (aus dem Anforderungssatz dieser Studie; die Spalten ab F bleiben Ihre)", f"Requirements for {cfg.get('system', {}).get('type', 'the system')} - technical and non-functional (from the requirement set of this study; columns F.. stay yours)"))
    out_dir = os.path.join(ROOT, "deliverables"); os.makedirs(out_dir, exist_ok=True); out = os.path.join(out_dir, fname)
    wb.save(out)
    print(f"wrote {relp(out, ROOT)} ({n1} functional, {n2} technical/non-functional rows, formula-free) - the deliverable of record stays deliverables/{cfg['deliverables']['D2']['file']}")


if __name__ == "__main__":
    main()
