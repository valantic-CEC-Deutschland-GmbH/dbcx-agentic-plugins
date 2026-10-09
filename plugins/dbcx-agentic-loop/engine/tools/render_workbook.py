#!/usr/bin/env python3
"""Recalculate and render the built workbooks through Microsoft Excel (macOS, AppleScript) - the gate reads values, not formulas (G3).

Usage: dbcx render_workbook [--all | D1 ... | <file.xlsx> ...] [--edition customer|full|both] [--no-writeback] [--timeout <s>]
Per workbook: copy into Excel's sandbox container (~/Library/Containers/com.microsoft.Excel/Data/dbcx-render/<call id>/ - other paths
fail with -50), alerts off, open without updating links, calculate, save (cached values written), save the whole workbook as a PDF, then
one PDF per sheet (every other sheet hidden in the open, never re-saved workbook), close it, alerts back on.
Output in work/render/<date>/<D>/ (customer edition) or work/internal/render/<date>/<D>/ (full edition - the gate roles never see it):
<file>.pdf (the whole workbook, for the record), <nn>-<sheet>.png = the first page of each sheet (the Management Summary: every page,
<nn>-<sheet>-p<k>.png), and index.json listing sheet, page count and images - the gate briefs point to it. The recalculated xlsx goes back
to its place unless --no-writeback. Images need pdftoppm (poppler); without it only the PDFs are written.
Only workbooks this call opened are closed - a user's own open workbooks, and another call's, stay untouched; Excel is quit again when it
was not running. Default: every customer workbook. A workbook Excel had to repair is reported (its repair log names the part).
Exit 0 = all rendered; 1 = a workbook failed or was repaired; 3 = Microsoft Excel / osascript not available (sandbox, CI, Linux):
the gate then warns that personas see formulas without values.
"""
import glob, json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, project, relp
from lint_deliverable import edition_files

CONTAINER = os.path.expanduser("~/Library/Containers/com.microsoft.Excel/Data")
STAGE = os.path.join(CONTAINER, "dbcx-render", f"{os.getpid()}-{int(time.time())}")   # per call: closing "ours" never touches another call's workbooks
REPAIR_LOGS = os.path.join(CONTAINER, "tmp")
MGMT = re.compile(r"Management|Summary", re.I)

def excel_available():
    return sys.platform == "darwin" and shutil.which("osascript") and os.path.isdir("/Applications/Microsoft Excel.app") and os.path.isdir(CONTAINER)

def osa(script, timeout):
    return subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True, timeout=timeout)

def excel_running():
    return osa('tell application "System Events" to (name of processes) contains "Microsoft Excel"', 30).stdout.strip() == "true"

def close_ours():
    """close every workbook opened from this call's staging folder (never the user's own), alerts back on"""
    osa(f'''tell application "Microsoft Excel"
  set display alerts to false
  repeat with wb in (get every workbook)
    try
      if (full name of wb) contains "{os.path.basename(STAGE)}" then close wb saving no
    end try
  end repeat
  set display alerts to true
end tell''', 60)

def hfs(path): return f'(POSIX file "{path}") as text'
def sheet_pdf(pdf, i): return f"{pdf[:-4]}-s{i:02d}.pdf"
def slug(name): return re.sub(r"[^\w.-]+", "_", name).strip("_") or "sheet"

def render_one(src, pdf, sheets, timeout):
    """recalculate + save in place (in the container) + whole-workbook PDF + one PDF per visible sheet; returns (ok, message).
    Paths are resolved before the Excel tell block (a path built inside it fails with -50)."""
    n = len(sheets); shown = [i for i, (_, v) in enumerate(sheets, 1) if v]
    lines = [f"set pAll to {hfs(pdf)}"] + [f"set p{i} to {hfs(sheet_pdf(pdf, i))}" for i in shown]
    per = []
    for i in shown:
        per += ["  try", f"    set visible of worksheet {i} of wb to true"] + [f"    set visible of worksheet {j} of wb to false" for j in shown if j != i] + \
               [f"    save workbook as wb filename p{i} file format PDF file format", "  end try"]
    script = "\n".join(lines) + f'''
with timeout of {timeout} seconds
tell application "Microsoft Excel"
  set display alerts to false
  set wb to open workbook workbook file name {hfs(src)} update links do not update links
  calculate
  save wb
  save workbook as wb filename pAll file format PDF file format
''' + "\n".join(per) + '''
  close wb saving no
  set display alerts to true
end tell
end timeout'''
    try: r = osa(script, timeout + 30)
    except subprocess.TimeoutExpired: return False, f"timeout after {timeout + 30}s"
    return r.returncode == 0, (r.stderr or r.stdout).strip()

def pages(pdf):
    r = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True) if shutil.which("pdfinfo") and os.path.exists(pdf) else None
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M) if r and r.returncode == 0 else None
    return int(m.group(1)) if m else 0

def images(pdf, i, name, out):
    """the first page of a sheet; every page of the management summary -> <nn>-<sheet>[-p<k>].png"""
    if not shutil.which("pdftoppm") or not os.path.exists(pdf): return []
    last = (pages(pdf) or 1) if MGMT.match(name) else 1; base = os.path.join(out, f"{i:02d}-{slug(name)}")
    subprocess.run(["pdftoppm", "-png", "-r", "80", "-f", "1", "-l", str(last), pdf, base + "-tmp"], capture_output=True)
    got = []
    for k, f in enumerate(sorted(glob.glob(base + "-tmp-*.png")), 1):
        dst = base + (".png" if k == 1 else f"-p{k}.png"); os.replace(f, dst); got.append(os.path.basename(dst))
    return got

def main():
    a = sys.argv[1:]; cfg = project()
    ed = a[a.index("--edition") + 1] if "--edition" in a else "customer"
    timeout = int(a[a.index("--timeout") + 1]) if "--timeout" in a else 600
    keys = [x for x in a if x in cfg.get("deliverables", {})]; files = [x if os.path.isabs(x) else os.path.join(ROOT, x) for x in a if x.endswith(".xlsx")]
    if "--all" in a or keys or not files: files += edition_files(cfg, ed, keys or None)
    if not files: sys.exit("no workbook found (build first: dbcx build_excel --all)")
    if not excel_available():
        print("render_workbook: Microsoft Excel via osascript is not available here (needs macOS with Excel). The workbooks keep formulas without cached values; the gate briefs warn the personas, and the hygiene layer skips formula errors and reconciliation.")
        sys.exit(3)
    import openpyxl
    os.makedirs(STAGE, exist_ok=True); date = time.strftime("%Y-%m-%d"); was_running = excel_running(); failed = 0
    by_file = {os.path.basename(v["file"]): k for k, v in cfg.get("deliverables", {}).items() if isinstance(v, dict) and v.get("file")}
    try:
        for f in files:
            name = os.path.basename(f); key = by_file.get(name, os.path.splitext(name)[0]); internal = os.sep + "intern" + os.sep in f
            out = os.path.join(ROOT, "work", "internal", "render", date, key) if internal else os.path.join(ROOT, "work", "render", date, key)
            wb = openpyxl.load_workbook(f, read_only=True); sheets = [(ws.title, ws.sheet_state == "visible") for ws in wb.worksheets]; wb.close()
            src = os.path.join(STAGE, name); pdf = os.path.join(STAGE, os.path.splitext(name)[0] + ".pdf")
            shutil.copy2(f, src); before = set(glob.glob(os.path.join(REPAIR_LOGS, "Repair Result to *.xml")))
            t0 = time.time(); ok, msg = render_one(src, pdf, sheets, timeout)
            repaired = sorted(set(glob.glob(os.path.join(REPAIR_LOGS, "Repair Result to *.xml"))) - before)
            if not ok or not os.path.exists(pdf):
                failed += 1; print(f"FAILED {relp(f, ROOT)}: {msg or 'no PDF written'}"); close_ours(); continue
            os.makedirs(out, exist_ok=True)
            for old in glob.glob(os.path.join(out, "*")): os.remove(old)
            shutil.copy2(pdf, os.path.join(out, os.path.basename(pdf)))
            index = {"workbook": relp(f, ROOT), "pdf": os.path.basename(pdf), "pages": pages(pdf), "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "sheets": [{"nn": i, "sheet": sn, "pages": pages(sheet_pdf(pdf, i)), "images": images(sheet_pdf(pdf, i), i, sn, out)} for i, (sn, v) in enumerate(sheets, 1) if v]}
            json.dump(index, open(os.path.join(out, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            if "--no-writeback" not in a: shutil.copy2(src, f)
            print(f"rendered {relp(f, ROOT)} in {time.time() - t0:.0f}s -> {relp(out, ROOT)}/ ({index['pages']} PDF page(s), {len(index['sheets'])} sheet(s), "
                  f"{sum(len(s['images']) for s in index['sheets'])} image(s), index.json)" + ("" if "--no-writeback" in a else "; cached values written back"))
            empty = [s["sheet"] for s in index["sheets"] if not s["pages"]]
            if empty: print(f"  WARNING no sheet PDF for: {', '.join(empty)} (nothing to print, or the export failed)")
            for rp in repaired:
                failed += 1; print(f"  REPAIRED BY EXCEL: {os.path.basename(rp)} - " + open(rp, encoding="utf-8", errors="replace").read()[-400:])
    finally:
        close_ours(); shutil.rmtree(STAGE, ignore_errors=True)
        if not was_running: osa('tell application "Microsoft Excel" to quit saving no', 60)
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
