#!/usr/bin/env python3
"""Intake check of imported / external inputs - tool-driven, before any analyst is spawned. Defects become CLIENT questions
(`dbcx questions add intake client ...`), not review findings: we do not review another department's work, we ask.
Usage: dbcx intake [--requirements] [--corpus] [--handover] [--no-questions]        (default: everything present)
Checks: requirements (state/requirements.json): empty descriptions, duplicate ids, missing titles, missing priority/phase where the mapping has the column,
        rows without a source; corpus: unextractable sources, sources with quality none/partial; handover: imported artefacts whose sha no longer matches the source.
Writes docs/INTAKE.md and appends open client questions (one per defect class, with the row ids) unless --no-questions.
"""
import os, sys, json, glob, hashlib, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, TOOLS, REQ_PATH, CORPUS_DIR, load_json, run_file

def main():
    a = sys.argv[1:]; sel = {k for k in ("--requirements", "--corpus", "--handover") if k in a} or {"--requirements", "--corpus", "--handover"}
    lines = [f"# Intake check - {time.strftime('%Y-%m-%d %H:%M')}", ""]; questions = []
    if "--requirements" in sel and os.path.exists(REQ_PATH):
        req = load_json(REQ_PATH); rows = req.get("requirements", []); ids = [r["id"] for r in rows]
        dup = sorted({i for i in ids if ids.count(i) > 1}); nodesc = [r["id"] for r in rows if not (r.get("description") or "").strip()]
        notitle = [r["id"] for r in rows if not (r.get("title") or "").strip()]; nosrc = [r["id"] for r in rows if not r.get("sources")]
        noprio = [r["id"] for r in rows if "priority" in r and not r.get("priority")]
        lines += [f"## Requirements ({len(rows)} rows from {req.get('source_file', '?')})", f"- duplicate ids: {len(dup)} {dup[:10]}", f"- empty description: {len(nodesc)} {nodesc[:10]}", f"- missing title: {len(notitle)} {notitle[:10]}", f"- no source reference: {len(nosrc)} (of {len(rows)})", f"- no priority: {len(noprio)}", ""]
        if dup: questions.append(f"Requirement ids appear more than once ({', '.join(dup[:8])}{'...' if len(dup) > 8 else ''}) - which row is authoritative? (effect: the estimate would count a requirement twice)")
        if nodesc: questions.append(f"{len(nodesc)} requirements have a title but no description ({', '.join(nodesc[:8])}{'...' if len(nodesc) > 8 else ''}) - what is expected? (effect: coverage and effort can only be estimated from the title, confidence low)")
        if len(nosrc) == len(rows) and rows: questions.append("No requirement names its source (workshop, document, stakeholder) - can the origin be added? (effect: traceability of the requirement list is not provable)")
    if "--corpus" in sel and os.path.exists(os.path.join(CORPUS_DIR, "index.json")):
        idx = load_json(os.path.join(CORPUS_DIR, "index.json")); src = idx["sources"]
        unex = [k for k, v in src.items() if v.get("quality") == "unextractable"]; partial = [k for k, v in src.items() if str(v.get("quality", "")).startswith(("partial", "none"))]
        def client_side(k): return (src[k].get("origin") or "client") in ("client", "workshop", "unclear")   # provenance.json origin; sources without one count as the client's
        c_unex, c_partial = [k for k in unex if client_side(k)], [k for k in partial if client_side(k)]; own = [k for k in unex + partial if not client_side(k)]
        origins = {}
        for v in src.values(): origins[v.get("origin") or "-"] = origins.get(v.get("origin") or "-", 0) + 1
        lines += [f"## Corpus ({len(src)} sources)", f"- origin (provenance.json): " + ", ".join(f"{k}={n}" for k, n in sorted(origins.items())), f"- unextractable: {len(unex)} {unex[:10]}", f"- partial / no text layer: {len(partial)} {partial[:10]}", ""]
        if own: lines += [f"- NOT a client question: {len(own)} of these are the consultancy's own or public material ({', '.join(own[:8])}) - ask the team for the editable originals, or accept `visual, unverified`", ""]
        unclear = [k for k, v in src.items() if v.get("origin") == "unclear"]
        if unclear: questions.append(f"{len(unclear)} document(s) of unclear authorship ({', '.join(unclear[:6])}) - were they written by the client (then they count as client evidence) or by the consultancy? (effect: until confirmed they weigh as unapproved consultancy material)")
        if c_unex or c_partial: questions.append(f"{len(c_unex) + len(c_partial)} client documents yield no or partial text ({', '.join((c_unex + c_partial)[:6])}) - can the client provide the source files (pptx/docx/xlsx instead of images or scanned PDFs)? (effect: statements about them stay `visual, unverified`)")
    if "--handover" in sel:
        for h in run_file().get("handover", {}).get("imports", []):
            src = h.get("source_path"); ok = src and os.path.exists(src) and hashlib.sha256(open(src, "rb").read()).hexdigest() == h.get("sha256")
            lines.append(f"- handover {h['type']} ({h.get('provenance')}): {'unchanged since import' if ok else 'SOURCE CHANGED or missing - inputs are frozen; consider a delta run'}")
        lines.append("")
    if questions:
        lines += ["## Client questions raised", ""] + [f"- {q}" for q in questions]
        if "--no-questions" not in a:
            for q in questions: subprocess.run([sys.executable, os.path.join(TOOLS, "questions.py"), "add", "intake", "client", q], cwd=ROOT, capture_output=True, text=True)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True); open(os.path.join(ROOT, "docs", "INTAKE.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines)); print(f"-> docs/INTAKE.md ({len(questions)} client question(s) {'recorded' if questions and '--no-questions' not in a else 'listed'})")

if __name__ == "__main__":
    main()
