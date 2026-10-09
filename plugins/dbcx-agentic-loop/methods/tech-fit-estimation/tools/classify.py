#!/usr/bin/env python3
"""Row classification of tech-fit-estimation - the lead gate before `dbcx discover` (run with a code-analysis handover).

Usage: dbcx classify draft [--force]      candidates -> work/classification.json: one per customization-depth unit whose disposition is in
                                          classification.refactoring_dispositions and one per target-readiness migration task (source locator,
                                          topic, affected client requirements, units, the handover text) and one per derived row of the
                                          requirements-set without a decision in run.json requirements.decisions (client-row = merged into
                                          ONE client row | drop | keep as its own row - the decision, not a new row); first call: also the skeleton
                                          analysis/classification.md for the classification agent (`dbcx render brief classify --out`). Once
                                          analysis/classification.json exists (the agent's file after `dbcx md_to_json classification ...`)
                                          the proposals and product-owner texts are merged and work/classification.xlsx is written for the lead
                                          (class per candidate as a dropdown: client-row | tech-migration | refactoring | drop). Refuses to
                                          overwrite a workbook the lead has edited and an approved classification (--force re-drafts)
       dbcx classify approve [--by <name>] reads work/classification.xlsx back, checks every candidate (class, texts at product-owner level,
                                          named client rows exist) and records the approver
       dbcx classify apply                appends TM-nn / RF-nn rows to state/requirements.json (row_class, group, epic = the class label,
                                          applies_to, links / references = the affected client rows, source = the handover locator, title and
                                          description = the approved texts); client-row candidates stay in work/classification.json as BASELINE
                                          hints of the named client rows. Idempotent: a re-apply replaces the rows of the previous apply
       dbcx classify skip --reason "..."  no classification in this run (recorded)
       dbcx classify show                 the candidates and their state
`dbcx status next` and `dbcx discover` wait for the classification (applied or skipped) while a customization-depth or target-readiness
handover is imported and yields candidates; without them the step does not exist.
"""
import os, sys, json, time
HERE = os.path.dirname(os.path.abspath(__file__)); MDIR = os.path.dirname(HERE)
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
sys.path.insert(0, MDIR)
from common import RUN as ROOT, P, CLI, REQ_PATH, load_json, save_json, project, options, labels, relp
import tfe_model as TM

STATE = P("work", "classification.json"); XLSX = P("work", "classification.xlsx"); MD = P("analysis", "classification.md"); MDJ = P("analysis", "classification.json")
CLASSES = ("client-row", "tech-migration", "refactoring", "drop", "keep")   # keep: a derived row stays an estimation row of its own
COLS = [("candidate_id", "Kandidat", "Candidate", 11), ("source", "Quelle", "Source", 30), ("topic", "Thema", "Topic", 16), ("requirements", "Anforderungen", "Requirements", 18),
        ("units", "Einheiten", "Units", 18), ("handover_text", "Befund der Code-Analyse", "Code-analysis finding", 60), ("proposed_class", "Vorschlag", "Proposal", 14),
        ("class", "Klasse (Entscheidung)", "Class (decision)", 16), ("client_rows", "Teil von Anforderung (client-row)", "Part of requirement (client-row)", 18),
        ("title_de", "Titel", "Title", 34), ("description_de", "Beschreibung", "Description", 60), ("rationale", "Begründung des Vorschlags", "Rationale of the proposal", 40),
        ("comment", "Kommentar", "Comment", 30)]
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def opt(a, k, d=""): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
def rel(p): return relp(p, ROOT)
def load(): return load_json(STATE, {}) if os.path.exists(STATE) else {}
def reqs(): return load_json(REQ_PATH, {"requirements": []})


def imported():
    return [t for t in ("customization-depth", "target-readiness") if os.path.exists(P("input", "handover", f"{t}.json"))]


def candidates(cfg):
    """the deterministic columns: customization-depth units with a refactoring disposition (sorted by unit), then every migration task"""
    disp = set(((cfg.get("classification") or {}).get("refactoring_dispositions")) or [])
    units = TM.handover(ROOT, "customization-depth").get("units") or {}
    units = units if isinstance(units, dict) else {(u.get("unit") or u.get("name")): u for u in units if isinstance(u, dict)}
    out = []
    for name in sorted(u for u in units if u):
        u = units[name]; cl = u.get("classification") or {}
        if cl.get("disposition") not in disp: continue
        rq = list(dict.fromkeys(r.get("req_id") for r in u.get("requirements") or [] if isinstance(r, dict) and r.get("req_id")))
        out.append({"source": f"HO-customization-depth#{name}", "topic": cl.get("disposition", ""), "requirements": rq, "units": [name],
                    "handover_text": " ".join(x for x in (cl.get("disposition_rationale"), u.get("summary")) if x)})
    for t in TM.handover(ROOT, "target-readiness").get("migration_tasks") or []:
        if not isinstance(t, dict) or not t.get("id"): continue
        out.append({"source": f"HO-target-readiness#{t['id']}", "topic": t.get("topic", ""), "requirements": list(t.get("affected_requirements") or []), "units": list(t.get("units") or []),
                    "handover_text": " ".join(x for x in (t.get("task"), t.get("finding")) if x)})
    decided = {k for k, v in (((cfg.get("requirements") or {}).get("decisions")) or {}).items() if isinstance(v, dict)}
    for r in reqs()["requirements"]:   # a row the code analysis proposed and the client has not decided yet
        if not TM.derived(r) or r["id"] in decided: continue
        x = r.get("extra") or {}
        out.append({"source": f"HO-requirements-set#{r['id']}", "row_id": r["id"], "topic": x.get("proposed_handling", ""), "requirements": list(r.get("references") or []), "units": list(x.get("units") or []),
                    "handover_text": " ".join(v for v in (r.get("title"), r.get("description"), x.get("rationale")) if v)})
    for i, c in enumerate(out, 1): c["candidate_id"] = f"CL-{i:02d}"
    return out


def hold_line(cfg):
    """the classification step as `dbcx status next` prints it before discover (None: nothing to wait for)"""
    if not imported(): return None
    st = load(); s = st.get("status")
    if s == "skipped": return None
    if s == "applied":
        have = {r["id"] for r in reqs()["requirements"] if TM.row_class(r) != "client"}
        miss = [x for x in st.get("rows") or [] if x not in have]
        return None if not miss else f"the classification was applied, but {len(miss)} of its rows are no longer in state/requirements.json (re-imported?) - `{CLI} classify apply` again"
    if not st:
        if not candidates(cfg): return None
        return f"row classification of the code-analysis handover: `{CLI} classify draft`, the classification agent (`{CLI} render brief classify --out`), `{CLI} md_to_json classification {rel(MD)}`, `{CLI} classify draft`, the lead decides in {rel(XLSX)}, `{CLI} classify approve --by <lead>`, `{CLI} classify apply` - or `{CLI} classify skip --reason \"...\"`"
    if s == "drafted": return f"classification drafted ({len(st['candidates'])} candidates): spawn the classification agent from `{CLI} render brief classify --out`, convert its file with `{CLI} md_to_json classification {rel(MD)}`, then `{CLI} classify draft`"
    if s == "proposed": return f"the lead decides the class of every candidate in {rel(XLSX)} (and may edit the texts), then `{CLI} classify approve --by <lead>`"
    return f"classification approved by {st.get('approved_by')}: `{CLI} classify apply`"


def po_errors(cfg, where, text):
    from lint_deliverable import code_terms, unit_names
    return [f"{where}: {k} '{t}' - product-owner language: WHAT changes for the shop, never HOW in code" for k, t in code_terms(text, unit_names(ROOT))[:2]]


def check_candidate(cfg, c, cls, client_ids):
    """errors of one decided candidate (class, texts, client rows)"""
    e = []; cid = c["candidate_id"]
    if cls not in CLASSES: return [f"{cid}: class '{cls}' - one of {' | '.join(CLASSES)}"]
    if c.get("row_id") and (cls not in ("client-row", "drop", "keep") or (cls == "client-row" and len(c.get("client_rows") or []) != 1)): return [f"{cid}: a derived row ({c['row_id']}) is merged into ONE client row (client-row), dropped or kept as its own row"]
    if cls == "keep" and not c.get("row_id"): return [f"{cid}: keep is the decision on a derived row only"]
    if cls in ("tech-migration", "refactoring"):
        if not (c.get("title_de") or "").strip() or not (c.get("description_de") or "").strip(): e.append(f"{cid}: a {cls} row needs a title and a description")
        e += po_errors(cfg, f"{cid} title", c.get("title_de")) + po_errors(cfg, f"{cid} description", c.get("description_de"))
    if cls == "refactoring" and not any((o.get("start") or "greenfield") == "brownfield" for o in options(cfg)): e.append(f"{cid}: refactoring rows need a brownfield option")
    if cls == "client-row":
        rows = c.get("client_rows") or []
        if not rows: e.append(f"{cid}: client-row needs the client rows it belongs to")
        bad = [x for x in rows if x not in client_ids]
        if bad: e.append(f"{cid}: {', '.join(bad)} is no client row of state/requirements.json")
    return e


def write_md_skeleton(st, lang):
    if os.path.exists(MD): return False
    os.makedirs(os.path.dirname(MD), exist_ok=True)
    rows = "\n".join(f"| {c['candidate_id']} |  |  |  |  |  |" for c in st["candidates"])
    open(MD, "w", encoding="utf-8").write(f"# Row classification (proposal)\n\n- **agent:** consolidate-classification\n- **status:** draft\n\n## Summary\n\n(3-5 sentences for the lead)\n\n## Candidates\n\n"
                                          f"| candidate_id | proposed_class | client_rows | title_de | description_de | rationale |\n|---|---|---|---|---|---|\n{rows}\n")
    return True


def write_xlsx(st, lang):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Klassifikation" if lang == "de" else "Classification"
    ws.append([h_de if lang == "de" else h_en for _, h_de, h_en, _ in COLS])
    for c in st["candidates"]:
        ws.append([", ".join(c.get(k) or []) if isinstance(c.get(k), list) else (c.get(k) or "") for k, _, _, _ in COLS])
    for i, (k, _, _, w) in enumerate(COLS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w; ws.cell(1, i).font = Font(bold=True, color="FFFFFF"); ws.cell(1, i).fill = PatternFill("solid", fgColor="100C2A" if k in ("class", "client_rows", "title_de", "description_de", "comment") else "3C4BC8")
        for r in range(2, ws.max_row + 1): ws.cell(r, i).alignment = Alignment(wrap_text=True, vertical="top")
    col = get_column_letter([k for k, *_ in COLS].index("class") + 1)
    dv = DataValidation(type="list", formula1='"' + ",".join(CLASSES) + '"', allow_blank=False); ws.add_data_validation(dv); dv.add(f"{col}2:{col}{max(2, ws.max_row)}")
    ws.freeze_panes = "B2"; ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{max(1, ws.max_row)}"
    os.makedirs(os.path.dirname(XLSX), exist_ok=True); wb.save(XLSX); st["xlsx_written_at"] = os.path.getmtime(XLSX)


def read_xlsx(lang):
    import openpyxl
    ws = openpyxl.load_workbook(XLSX).worksheets[0]; hdr = [str(c.value or "").strip() for c in ws[1]]
    key = {h: k for k, de, en, _ in COLS for h in (de, en)}; idx = {key[h]: i for i, h in enumerate(hdr) if h in key}
    if "candidate_id" not in idx or "class" not in idx: sys.exit(f"REFUSED: {rel(XLSX)} has no columns '{COLS[0][1 if lang == 'de' else 2]}' and '{COLS[7][1 if lang == 'de' else 2]}' in row 1")
    out = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        cid = str(r[idx["candidate_id"]] or "").strip()
        if cid: out[cid] = {k: ("" if r[i] is None else str(r[i]).strip()) for k, i in idx.items()}
    return out


def split_ids(v): return [x.strip() for x in str(v or "").replace(";", ",").split(",") if x.strip()]


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]; cfg = project(); lang = cfg["languages"]["deliverable"]; st = load(); force = "--force" in a
    if cmd == "draft":
        if st.get("status") in ("approved", "applied", "skipped") and not force: sys.exit(f"REFUSED: the classification is {st['status']} - `--force` drafts it again (the approval is dropped)")
        if not imported(): sys.exit("REFUSED: no customization-depth or target-readiness handover imported (input/handover/) - nothing to classify; the step does not apply to this run")
        prev = {c["source"]: c for c in st.get("candidates") or []}; cands = candidates(cfg)
        for c in cands:   # the lead's and the agent's fields survive a re-draft (matched by source locator)
            for k in ("proposed_class", "class", "client_rows", "title_de", "description_de", "rationale", "comment"):
                if k in prev.get(c["source"], {}): c[k] = prev[c["source"]][k]
        st = {"status": "drafted", "drafted_at": now(), "candidates": cands, **{k: st[k] for k in ("xlsx_written_at",) if k in st}}
        if os.path.exists(MDJ):
            prop = {r["candidate_id"]: r for r in (load_json(MDJ, {}).get("candidates") or [])}; ids = [c["candidate_id"] for c in cands]
            miss = [i for i in ids if i not in prop]; extra = [i for i in prop if i not in ids]
            if miss or extra: print(f"WARNING: {rel(MDJ)} does not match the candidates (missing {', '.join(miss) or '-'}; unknown {', '.join(extra) or '-'}) - fix the agent's file and convert it again")
            else:
                for c in cands:
                    p = prop[c["candidate_id"]]; c.update({k: p.get(k) or ([] if k == "client_rows" else "") for k in ("proposed_class", "client_rows", "title_de", "description_de", "rationale")})
                    c.setdefault("class", p.get("proposed_class"))
                    if not c.get("class"): c["class"] = p.get("proposed_class")
                if os.path.exists(XLSX) and st.get("xlsx_written_at") and os.path.getmtime(XLSX) > st["xlsx_written_at"] + 1 and not force:
                    sys.exit(f"REFUSED: {rel(XLSX)} was edited after it was written (the lead's decisions) - `{CLI} classify approve` reads it; --force overwrites it")
                st["status"] = "proposed"; write_xlsx(st, lang)
        wrote = write_md_skeleton(st, lang); save_json(STATE, st)
        by = {}
        for c in cands: by[c.get("proposed_class") or "-"] = by.get(c.get("proposed_class") or "-", 0) + 1
        print(f"{rel(STATE)}: {len(cands)} candidate(s) ({', '.join(f'{k} {v}' for k, v in by.items())}); status {st['status']}" + (f"; skeleton {rel(MD)}" if wrote else "") + (f"; lead workbook {rel(XLSX)}" if st["status"] == "proposed" else ""))
        print("NEXT: " + (hold_line(cfg) or "-"))
    elif cmd == "approve":
        if st.get("status") not in ("proposed", "approved") or not os.path.exists(XLSX): sys.exit(f"REFUSED: nothing to approve (status {st.get('status') or 'none'}; {rel(XLSX)} {'exists' if os.path.exists(XLSX) else 'missing'}) - {hold_line(cfg)}")
        got = read_xlsx(lang); client_ids = {r["id"] for r in reqs()["requirements"] if TM.row_class(r) == "client"}; errs = []
        for c in st["candidates"]:
            x = got.get(c["candidate_id"])
            if not x: errs.append(f"{c['candidate_id']}: no row in {rel(XLSX)}"); continue
            c.update({"class": x.get("class", c.get("class")), "title_de": x.get("title_de", c.get("title_de", "")), "description_de": x.get("description_de", c.get("description_de", "")),
                      "client_rows": split_ids(x.get("client_rows")) if "client_rows" in x else c.get("client_rows") or [], "comment": x.get("comment", "")})
            errs += check_candidate(cfg, c, c["class"], client_ids)
        if errs: print(f"REFUSED ({len(errs)} problem(s) in {rel(XLSX)}; nothing recorded):"); [print("  -", e) for e in errs]; sys.exit(1)
        st.update({"status": "approved", "approved_by": opt(a, "--by", "lead"), "approved_at": now()}); save_json(STATE, st)
        by = {}
        for c in st["candidates"]: by[c["class"]] = by.get(c["class"], 0) + 1
        print(f"classification approved by {st['approved_by']}: " + ", ".join(f"{k} {v}" for k, v in by.items()) + f" - NEXT: `{CLI} classify apply`")
    elif cmd == "apply":
        if st.get("status") not in ("approved", "applied"): sys.exit(f"REFUSED: the classification is {st.get('status') or 'not drafted'} - {hold_line(cfg)}")
        R = reqs(); rows = [r for r in R["requirements"] if not ((r.get("extra") or {}).get("origin") == "classification")]
        client = {r["id"]: r for r in rows if TM.row_class(r) == "client"}; opts = options(cfg); L = labels(lang); n = {"tech-migration": 0, "refactoring": 0}; new = []
        order = [r["id"] for r in rows]
        for c in [c for k in ("tech-migration", "refactoring") for c in st["candidates"] if c["class"] == k]:   # TM rows first, then RF rows
            cls = c["class"]
            n[cls] += 1; rid = f"{TM.PREFIX[cls]}-{n[cls]:02d}"; links = [x for x in c.get("requirements") or [] if x in client]
            phase = next((client[x].get("phase", "") for x in sorted(links, key=order.index)), "") or (R.get("phase_values_in_scope") or [""])[0]   # no linked row: the first release in scope
            new.append({"group": cls, "id": rid, "epic": L.get(f"{cls}_cls", cls), "title": c.get("title_de", ""), "description": c.get("description_de", ""), "acceptance_criteria": "", "exclusions": "",
                        "references": links, "phase": phase, "sources": [c["source"]], "priority": "", "row_class": cls,
                        "applies_to": [o["id"] for o in opts if cls != "refactoring" or (o.get("start") or "greenfield") == "brownfield"], "links": links, "source": [c["source"]],
                        "extra": {"origin": "classification", "classification": c["candidate_id"]}})
            c["row"] = rid
        R["requirements"] = rows + new; save_json(REQ_PATH, R)
        st.update({"status": "applied", "applied_at": now(), "rows": [r["id"] for r in new]}); save_json(STATE, st)
        merges = [c for c in st["candidates"] if c["class"] == "client-row"]
        print(f"applied: {n['tech-migration']} technical migration row(s), {n['refactoring']} refactoring row(s) appended to {rel(REQ_PATH)} ({', '.join(r['id'] for r in new) or '-'}); "
              f"{len(merges)} candidate(s) merged into client rows as BASELINE hints; {sum(1 for c in st['candidates'] if c['class'] == 'drop')} dropped. NEXT: `{CLI} discover`")
    elif cmd == "skip":
        if st.get("status") == "applied" and not force: sys.exit(f"REFUSED: the classification is applied ({', '.join(st.get('rows') or [])}) - --force records the skip (the rows stay until the requirements are imported again)")
        if not opt(a, "--reason"): sys.exit('REFUSED: --reason "..."')
        st = dict(st, status="skipped", skip_reason=opt(a, "--reason"), skipped_at=now()); save_json(STATE, st); print(f"classification skipped ({st['skip_reason']})")
    elif cmd == "show":
        if not st: print(f"(no classification - {hold_line(cfg) or 'not needed in this run'})"); return
        print(f"status {st.get('status')}" + (f", approved by {st['approved_by']} {st.get('approved_at')}" if st.get("approved_by") else "") + (f" ({st['skip_reason']})" if st.get("skip_reason") else ""))
        for c in st.get("candidates") or []: print(f"  {c['candidate_id']} {c['source']:45s} {c.get('proposed_class') or '-':15s} -> {c.get('class') or '-':15s} {c.get('row', '')} {(c.get('title_de') or '')[:60]}")
    else: sys.exit(__doc__)


if __name__ == "__main__":
    main()
