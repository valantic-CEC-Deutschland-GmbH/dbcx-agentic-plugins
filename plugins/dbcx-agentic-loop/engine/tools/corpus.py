#!/usr/bin/env python3
"""Evidence corpus: turn the client's documents into greppable text with STABLE LOCATORS, so a claim about a document can be checked
the way a claim about code is checked (path:line). Project-level (<project>/corpus/), append-only, shared by every run.

Usage: dbcx corpus index [--input <dir>]...     walk <project>/input/ (or the given dirs) and (re)build corpus/index.json + corpus/text/SRC-nnn.md
       dbcx corpus list [--changed]             sources with id, revision, type, pages, extraction quality
       dbcx corpus show <SRC-id>                header + locator anchors of one source
       dbcx corpus grep "<regex>"               grep across corpus/text with locators (analysts and critics use `grep -n` on corpus/text/ directly)
       dbcx corpus profile | search | map | metrics   corpus retrieval (engine/tools/retrieval.py): profile, ranked search, corpus map and strategy per unit
Locators: SRC-007#p12 (PDF page), #s7 (slide), #para12 (docx paragraph block), #Sheet!R12 (xlsx row), #item:<id> (Miro item), #L120 (text/markdown line block), #frame:<name>.
Revisions: a source whose content hash changed keeps its id and gets a new revision (SRC-007@2); the previous text stays under text/SRC-007@1.md.
Extractors: .md/.txt/.csv/.json (as text), .pdf (pdftotext -layout, page separators), .docx (python-docx incl. tables), .pptx (python-pptx incl. notes),
.xlsx (openpyxl, one anchor per row), Miro board exports (corpus/miro/*.json or input/**/*.miro.json: list of items {id,type,text,frame,parent,url}),
.svg Miro board exports (one item per widget #item:<id>, frames by containment #frame:<name>, arrows -> derived links #link:<n>, marked heuristic),
.vsdx Visio drawings (shapes #p<n>s<id>, connectors #p<n>c<k> from the connection records).
Provenance: optional <project>/input/provenance.json {"default": {"origin","approved","note"}, "rules": [{"prefix": "input/<folder>", "origin": "client|workshop|consultancy-sales|public", "approved": bool, "note"}]}
- longest prefix wins; origin and approval land in index.json, in every SRC header line and in `corpus list`. Identical files under two paths become ONE source with aliases.
Images, diagrams without text and files no extractor handles are listed in corpus/unextractable.md - an analyst may cite them only as `visual, unverified`.
"""
import os, sys, json, re, hashlib, time, glob, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CORPUS_DIR, INPUT_DIR, PROJECT_DIR, relp

INDEX = os.path.join(CORPUS_DIR, "index.json"); TEXT = os.path.join(CORPUS_DIR, "text"); UNEX = os.path.join(CORPUS_DIR, "unextractable.md")
SKIP_EXT = {".ds_store", ".gitignore", ".sha256", ".url", ".webloc", ".lnk"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".heic"}
PROVENANCE = os.path.join(INPUT_DIR, "provenance.json")

def sha(fp): return hashlib.sha256(open(fp, "rb").read()).hexdigest()
def load_index(): return json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {"sources": {}, "next_id": 1, "built_at": None}

def anchors_text(lines, sid, block=40):
    out = []
    for i, l in enumerate(lines):
        if i % block == 0: out.append(f"<!-- {sid}#L{i + 1} -->")
        out.append(l)
    return out

def ext_pdf(fp, sid):
    try: r = subprocess.run(["pdftotext", "-layout", fp, "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except FileNotFoundError: return None, "pdftotext not installed (brew install poppler)"
    if r.returncode != 0: return None, r.stderr.strip()[:200]
    pages = r.stdout.split("\f"); out = []; empty = 0
    for i, pg in enumerate(pages, 1):
        if not pg.strip():
            empty += 1
            if i == len(pages): continue
        out.append(f"<!-- {sid}#p{i} -->"); out.append(pg.rstrip())
    q = "good" if empty <= len(pages) * 0.2 else ("partial" if empty < len(pages) else "none (scanned? no text layer)")
    return out, q, len(pages)

def ext_docx(fp, sid):
    try: import docx
    except ImportError: return None, "python-docx not installed"
    d = docx.Document(fp); out = []; n = 0
    for p in d.paragraphs:
        if not p.text.strip(): continue
        n += 1
        if n % 12 == 1: out.append(f"<!-- {sid}#para{n} -->")
        out.append(("#" * min(6, int(p.style.name.split()[-1])) + " " if p.style and p.style.name.startswith("Heading") and p.style.name.split()[-1].isdigit() else "") + p.text)
    for ti, t in enumerate(d.tables, 1):
        out.append(f"<!-- {sid}#table{ti} -->")
        for r in t.rows: out.append("| " + " | ".join(c.text.replace("|", "/").replace("\n", " ") for c in r.cells) + " |")
    return out, "good" if n else "none", n

def ext_pptx(fp, sid):
    try: from pptx import Presentation
    except ImportError: return None, "python-pptx not installed"
    prs = Presentation(fp); out = []; pics = 0
    for i, s in enumerate(prs.slides, 1):
        out.append(f"<!-- {sid}#s{i} -->")
        for sh in s.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip(): out.append(sh.text_frame.text.strip())
            if getattr(sh, "has_table", False) and sh.has_table:
                for r in sh.table.rows: out.append("| " + " | ".join(c.text.replace("|", "/") for c in r.cells) + " |")
            if sh.shape_type == 13: pics += 1
        if s.has_notes_slide and s.notes_slide.notes_text_frame and s.notes_slide.notes_text_frame.text.strip(): out.append("[notes] " + s.notes_slide.notes_text_frame.text.strip())
    return out, ("good" if pics < len(prs.slides) else "partial (image-heavy)"), len(prs.slides)

def ext_xlsx(fp, sid):
    import openpyxl
    wb = openpyxl.load_workbook(fp, data_only=True, read_only=True); out = []; n = 0
    for ws in wb.worksheets:
        out.append(f"## sheet {ws.title}")
        for r, row in enumerate(ws.iter_rows(values_only=True), 1):
            if not any(v not in (None, "") for v in row): continue
            n += 1; out.append(f"<!-- {sid}#{ws.title}!R{r} --> | " + " | ".join("" if v is None else str(v).replace("|", "/").replace("\n", " ") for v in row) + " |")
    return out, "good" if n else "none", n

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?"
def _translate(attrs):
    m = re.search(r"translate\(\s*(" + _NUM + r")\s*[, ]\s*(" + _NUM + r")", attrs or "")
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)
def _clean(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t).replace("​", "").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")).strip()
def _texts(chunk): return [_clean(m) for m in re.findall(r"<text\b[^>]*>(.*?)</text>", chunk, re.S) if _clean(m)]
def _pt_seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; l2 = dx * dx + dy * dy
    t = 0 if l2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / l2))
    return ((px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2) ** 0.5

def ext_svg(fp, sid):
    """Miro board exported as SVG: one item per widget group (text joined), frames by containment, connectors derived from arrow paths.
    Anchors: #item:<data-widget-id or positional n>, #frame:<name>, #link:<n>. Generic SVGs fall back to their text lines."""
    s = open(fp, encoding="utf-8", errors="ignore").read()
    toks = list(re.finditer(r"<g\b[^>]*>|</g>", s)); stack = []; groups = []   # (start, end, attrs, depth, wrapper_attrs)
    for m in toks:
        if m.group(0) == "</g>":
            if stack:
                st = stack.pop()
                if st[2] is not None: groups.append((st[0], m.end(), st[1], st[3], st[4]))
            continue
        attrs = m.group(0); sized = re.search(r'\bwidth="(' + _NUM + r')px"\s+height="(' + _NUM + r')px"', attrs)
        conn = None
        outer_open = any(x[2] is not None for x in stack)
        wrapper = stack[-1][1] if stack else ""
        stack.append((m.start(), attrs, (sized or conn) if not outer_open else None, len(stack), wrapper) if sized else (m.start(), attrs, None, len(stack), wrapper))
    widgets = []; conns = []
    for start, end, attrs, depth, wrapper in groups:
        chunk = s[start:end]; w, h = map(float, re.search(r'\bwidth="(' + _NUM + r')px"\s+height="(' + _NUM + r')px"', attrs).groups()); x, y = _translate(attrs)
        wid = re.search(r'data-widget-id="(\d+)"', wrapper or "") or re.search(r'data-widget-id="(\d+)"', s[max(0, start - 300):start])
        kind = "sticky" if "StickerType" in s[max(0, start - 500):start] else ("frame" if 'class="shape-background"' in chunk or "shape-border" in chunk else ("shape" if "<path" in chunk or "<rect" in chunk else "text"))
        if "LineHeadArrow" in chunk or ('class="shape-element' not in chunk and re.search(r'<path[^>]*\bd="M', chunk) and "<rect" not in chunk and not _texts(chunk)):
            conns.append((x, y, chunk, wid.group(1) if wid else None)); continue
        widgets.append({"x": x, "y": y, "w": w, "h": h, "text": " ".join(_texts(chunk)), "id": wid.group(1) if wid else None, "kind": kind, "cx": x + w / 2, "cy": y + h / 2})
    # connectors that are not sized groups (data-widget-id wrappers with a path + arrowheads)
    for m in re.finditer(r'<g data-widget-id="(\d+)">(.*?)</g>\s*</g>', s, re.S):
        chunk = m.group(2)
        if "LineHeadArrow" in chunk and not any(c[3] == m.group(1) for c in conns):
            inner = re.search(r"<g\b([^>]*)>", chunk); x, y = _translate(inner.group(1) if inner else ""); conns.append((x, y, chunk, m.group(1)))
    if not widgets:
        lines = _texts(s)
        if not lines: return None, "svg without text (pure drawing or image) - describe it or ask for the source"
        return anchors_text(lines, sid), "partial (generic svg: text lines only)", len(lines)
    # Miro exports a shape or frame as TWO sibling groups at the same origin: the background (no text) and the text - merge them
    merged = []
    for wd in widgets:
        twin = next((m for m in merged if abs(m["x"] - wd["x"]) < 1.5 and abs(m["y"] - wd["y"]) < 1.5 and (not m["text"] or not wd["text"])), None)
        if twin:
            if wd["text"]: twin["text"] = (twin["text"] + " " + wd["text"]).strip()
            if wd["id"] and not twin["id"]: twin["id"] = wd["id"]
            if wd["w"] * wd["h"] > twin["w"] * twin["h"]: twin.update({k: wd[k] for k in ("w", "h", "cx", "cy")})
            if twin["kind"] in ("text",) and wd["kind"] != "text": twin["kind"] = wd["kind"]
        else: merged.append(wd)
    widgets = merged
    for i, wd in enumerate(sorted(widgets, key=lambda d: (round(d["y"] / 50), d["x"])), 1):
        if not wd["id"]: wd["id"] = f"n{i}"
    # frames: widgets whose box contains the centres of >= 2 other widgets
    def contains(a, b, tol=2): return a["x"] - tol <= b["cx"] <= a["x"] + a["w"] + tol and a["y"] - tol <= b["cy"] <= a["y"] + a["h"] + tol
    frames = [wd for wd in widgets if wd["kind"] != "sticky" and sum(1 for o in widgets if o is not wd and contains(wd, o)) >= 2]   # a sticky is never a container, even when stickies overlap
    for wd in widgets: wd["kind"] = "frame" if wd in frames else ("shape" if wd["kind"] == "frame" else wd["kind"])
    def home(wd):   # smallest STRICTLY larger frame that contains the centre (the area rule breaks mutual-containment cycles)
        cands = [fr for fr in frames if fr is not wd and contains(fr, wd) and fr["w"] * fr["h"] > wd["w"] * wd["h"]]
        return min(cands, key=lambda f: f["w"] * f["h"]) if cands else None
    id_kind = "Miro widget ids" if any(re.fullmatch(r"\d+", w["id"]) for w in widgets) else "positional (export carries no widget ids)"
    out = [f"# Miro board export (svg) - {os.path.splitext(os.path.basename(fp))[0]}", f"widgets: {len(widgets)} | frames: {len(frames)} | connectors: {len(conns)} | ids: {id_kind}", ""]
    by_frame = {}
    for wd in widgets:
        if wd in frames or wd.get("_title_of"): continue
        by_frame.setdefault(id(home(wd)) if home(wd) else None, []).append(wd)
    def emit(fr, its, level=2):
        if fr is not None:
            out.append(f"<!-- {sid}#frame:{re.sub(r'[^A-Za-z0-9_.-]+', '_', fr['text'])[:60] or fr['id']} -->"); out.append("#" * level + f" frame {fr['text'] or fr['id']}  @({fr['x']:.0f},{fr['y']:.0f} {fr['w']:.0f}x{fr['h']:.0f})")
        for wd in sorted(its, key=lambda d: (round(d["y"] / 40), d["x"])):
            if wd["text"]: out.append(f"<!-- {sid}#item:{wd['id']} --> [{wd['kind']}] {wd['text']}  @({wd['cx']:.0f},{wd['cy']:.0f})")
    top = [fr for fr in frames if home(fr) is None]
    emit(None, by_frame.get(None, []))
    def walk(fr, level):
        emit(fr, by_frame.get(id(fr), []), level)
        for sub in sorted([f for f in frames if home(f) is fr], key=lambda d: (d["y"], d["x"])): walk(sub, min(6, level + 1))
    for fr in sorted(top, key=lambda d: (d["y"], d["x"])): walk(fr, 2)
    left = [fr for fr in frames if not any(f"#frame:{re.sub(r'[^A-Za-z0-9_.-]+', '_', fr['text'])[:60] or fr['id']} -->" in l for l in out)]
    for fr in left: emit(fr, by_frame.get(id(fr), []), 2)
    rest = [wd for wd in widgets if wd not in frames and wd["text"] and not any(f"#item:{wd['id']} -->" in l for l in out)]
    if rest: out.append(f"<!-- {sid}#frame:_unplaced -->"); out.append("## items outside any frame"); emit(None, rest)
    # connectors -> links between the widgets they touch (heuristic)
    links = []
    for x, y, chunk, cid in conns:
        pm = re.search(r'<path[^>]*\bd="([^"]+)"', chunk)
        if not pm: continue
        nums = [float(v) for v in re.findall(_NUM, re.sub(r"[A-Za-z]", " ", pm.group(1)))]
        pts = [(x + nums[i], y + nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
        if len(pts) < 2: continue
        heads = [(_translate(a)) for a in re.findall(r'<use[^>]*LineHeadArrow[^>]*transform="([^"]+)"', chunk)]
        def at(p, q, tol=6): return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol
        head_start = any(at((x + hx, y + hy), pts[0]) for hx, hy in heads); head_end = any(at((x + hx, y + hy), pts[-1]) for hx, hy in heads) or (heads and not head_start)
        def hit(p):
            inside = [wd for wd in widgets if wd not in frames and wd["x"] - 12 <= p[0] <= wd["x"] + wd["w"] + 12 and wd["y"] - 12 <= p[1] <= wd["y"] + wd["h"] + 12]
            if inside: return min(inside, key=lambda d: d["w"] * d["h"])
            near = min((wd for wd in widgets if wd not in frames), key=lambda d: ((d["cx"] - p[0]) ** 2 + (d["cy"] - p[1]) ** 2) ** 0.5, default=None)
            return near if near and ((near["cx"] - p[0]) ** 2 + (near["cy"] - p[1]) ** 2) ** 0.5 <= max(60, min(near["w"], near["h"])) else None
        a, b = hit(pts[0]), hit(pts[-1])
        if a is not None and a is b: continue   # both ends on the same widget: a decoration or a mis-mapped short arrow, not a link
        via = [wd for wd in widgets if wd not in frames and wd is not a and wd is not b and wd["text"] and wd["w"] * wd["h"] < 60000 and any(_pt_seg_dist(wd["cx"], wd["cy"], *pts[i], *pts[i + 1]) < 30 for i in range(len(pts) - 1))]
        arrow = "<->" if head_start and head_end else ("<-" if head_start and not head_end else "->")
        cap = " ".join(_texts(chunk))
        links.append((cid, a, b, arrow, via, cap))
    if links:
        out += ["", f"<!-- {sid}#links -->", "## connectors (derived from arrow geometry - heuristic; cite as `visual, derived` and verify against the rendered board)"]
        for n, (cid, a, b, arrow, via, cap) in enumerate(links, 1):
            f = lambda wd: (f"{wd['text'][:50]} (#item:{wd['id']})" if wd else "? (no widget at this end)")
            out.append(f"<!-- {sid}#link:{cid or n} --> {f(a)} {arrow} {f(b)}" + (f"  via: " + "; ".join(f"{v['text'][:60]} (#item:{v['id']})" for v in via) if via else "") + (f"  caption: {cap}" if cap else ""))
    q = "good" if sum(1 for w in widgets if w["text"]) >= 3 else "partial (few text items)"
    return out, q, len(widgets)

def ext_vsdx(fp, sid):
    """Visio drawing: one item per shape with text, connectors from the page's Connect records. Anchors #page<n>, #p<n>s<shapeId>, #p<n>c<k>."""
    import zipfile, xml.etree.ElementTree as ET
    ns = "{http://schemas.microsoft.com/office/visio/2012/main}"
    try: z = zipfile.ZipFile(fp)
    except zipfile.BadZipFile: return None, "not a valid vsdx (zip) file"
    pages = sorted((n for n in z.namelist() if re.match(r"visio/pages/page\d+\.xml$", n)), key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    names = {}
    try:
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("visio/pages/_rels/pages.xml.rels"))}
        for pg in ET.fromstring(z.read("visio/pages/pages.xml")).iter(ns + "Page"):
            rel = pg.find(ns + "Rel")
            if rel is not None:
                rid = next((v for k, v in rel.attrib.items() if k.endswith("}id")), None); names[rels.get(rid, "")] = pg.get("Name", "")
    except (KeyError, ET.ParseError): pass
    out = []; n_items = 0
    for pi, pn in enumerate(pages, 1):
        root = ET.fromstring(z.read(pn)); out.append(f"<!-- {sid}#page{pi} -->"); out.append(f"## page {pi} {names.get(pn.rsplit('/', 1)[1], '')}".rstrip())
        txt = {}
        for sh in root.iter(ns + "Shape"):
            t = sh.find(ns + "Text"); text = re.sub(r"\s+", " ", "".join(t.itertext())).strip() if t is not None else ""
            if text:
                txt[sh.get("ID")] = text; n_items += 1
                out.append(f"<!-- {sid}#p{pi}s{sh.get('ID')} --> [{sh.get('Type', 'Shape')}{(' ' + sh.get('NameU')) if sh.get('NameU') else ''}] {text}")
        ends = {}
        for c in root.iter(ns + "Connect"):
            ends.setdefault(c.get("FromSheet"), {})["begin" if c.get("FromCell", "").startswith("Begin") else "end"] = c.get("ToSheet")
        if ends:
            out.append(f"<!-- {sid}#p{pi}connectors -->"); out.append("### connectors (from the drawing's connection records)")
            for k, (cid, e) in enumerate(ends.items(), 1):
                f = lambda i: f"{txt.get(i, 'shape ' + str(i))[:60]} (#p{pi}s{i})" if i else "? (open end)"
                out.append(f"<!-- {sid}#p{pi}c{k} --> {f(e.get('begin'))} -> {f(e.get('end'))}" + (f"  label: {txt[cid]}" if cid in txt else ""))
    return out, ("good" if n_items else "none (no shape text)"), n_items

def ext_miro(fp, sid):
    d = json.load(open(fp, encoding="utf-8")); items = d.get("items", d if isinstance(d, list) else [])
    out = [f"# Miro board {d.get('board_name', os.path.basename(fp))} ({d.get('board_id', '')})"]; frames = {}
    for it in items:
        fr = it.get("frame") or it.get("parent") or ""
        frames.setdefault(fr, []).append(it)
    for fr, its in frames.items():
        if fr: out.append(f"<!-- {sid}#frame:{fr} -->"); out.append(f"## frame {fr}")
        for it in its:
            txt = re.sub(r"<[^>]+>", " ", str(it.get("text") or it.get("title") or "")).strip()
            if txt: out.append(f"<!-- {sid}#item:{it.get('id')} --> [{it.get('type', 'item')}] {txt}")
    return out, "good" if len(out) > 1 else "none", len(items)

def extract(fp, sid):
    ext = os.path.splitext(fp)[1].lower()
    if ext == ".pdf": return ext_pdf(fp, sid)
    if ext == ".docx": return ext_docx(fp, sid)
    if ext == ".pptx": return ext_pptx(fp, sid)
    if ext in (".xlsx", ".xlsm"): return ext_xlsx(fp, sid)
    if ext == ".svg": return ext_svg(fp, sid)
    if ext in (".vsdx", ".vsdm"): return ext_vsdx(fp, sid)
    if fp.endswith(".miro.json") or "/miro/" in fp.replace(os.sep, "/"): return ext_miro(fp, sid)
    if ext in (".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".html", ".xml"):
        lines = open(fp, encoding="utf-8", errors="ignore").read().splitlines(); return anchors_text(lines, sid), "good", len(lines)
    if ext in IMG_EXT: return None, "image - no text layer (describe it in a note or ask the client for the source)"
    return None, f"no extractor for {ext}"

def provenance_of(rel, prov):
    """Longest matching prefix rule of <project>/input/provenance.json wins; else the file's default."""
    best = None
    for r in prov.get("rules", []):
        pre = r.get("prefix", "").rstrip("/")
        if pre and (rel == pre or rel.startswith(pre + "/")) and (best is None or len(pre) > len(best.get("prefix", ""))): best = r
    d = dict(prov.get("default", {})); d.update({k: v for k, v in (best or {}).items() if k != "prefix"}); return d

def index(inputs):
    idx = load_index(); os.makedirs(TEXT, exist_ok=True); by_path = {v["path"]: k for k, v in idx["sources"].items()}; unex = []; n_new = n_rev = 0
    prov = json.load(open(PROVENANCE, encoding="utf-8")) if os.path.exists(PROVENANCE) else {}
    by_hash = {v["sha256"]: k for k, v in idx["sources"].items()}; n_dup = 0; n_prov = 0
    files = []
    for root in inputs:
        for dp, dn, fn in os.walk(root):
            dn[:] = [x for x in dn if not x.startswith(".")]
            for f in sorted(fn):
                if f.startswith((".", "~$")) or os.path.splitext(f)[1].lower() in SKIP_EXT: continue
                if os.path.abspath(os.path.join(dp, f)) == os.path.abspath(PROVENANCE): continue   # the provenance map is metadata, not a source
                files.append(os.path.join(dp, f))
    for fp in sorted(files):
        rel = relp(fp, PROJECT_DIR); h = sha(fp)
        if rel in by_path:
            sid = by_path[rel]; e = idx["sources"][sid]
            if e["sha256"] == h:
                pv = provenance_of(rel, prov) if prov else {}   # unchanged file, but the provenance map may have changed: refresh entry and header
                if pv and (e.get("origin"), e.get("client_approved"), e.get("provenance_note")) != (pv.get("origin", "unknown"), pv.get("approved"), pv.get("note", "")):
                    e["origin"] = pv.get("origin", "unknown"); e["client_approved"] = pv.get("approved"); e["provenance_note"] = pv.get("note", ""); n_prov += 1
                    tf = os.path.join(TEXT, f"{sid}.md")
                    if os.path.exists(tf):
                        L = open(tf, encoding="utf-8").read().splitlines(); L = [l for l in L[:6] if not l.startswith("origin: ")] + L[6:]
                        L.insert(2, f"origin: {e['origin']} | client-approved: {'yes' if e.get('client_approved') else 'NO'}" + (f" | {e['provenance_note']}" if e.get("provenance_note") else "")); open(tf, "w", encoding="utf-8").write("\n".join(L) + "\n")
                continue
            e["revision"] += 1; e["sha256"] = h; e["indexed_at"] = time.strftime("%Y-%m-%d"); n_rev += 1
            if os.path.exists(os.path.join(TEXT, f"{sid}.md")): os.replace(os.path.join(TEXT, f"{sid}.md"), os.path.join(TEXT, f"{sid}@{e['revision'] - 1}.md"))
        elif h in by_hash and idx["sources"][by_hash[h]]["path"] != rel:   # identical content under a second path: alias, not a second source
            e = idx["sources"][by_hash[h]]; e.setdefault("aliases", [])
            if rel not in e["aliases"]: e["aliases"].append(rel); n_dup += 1
            continue
        else:
            sid = f"SRC-{idx['next_id']:03d}"; idx["next_id"] += 1; n_new += 1
            e = idx["sources"][sid] = {"id": sid, "path": rel, "title": os.path.splitext(os.path.basename(fp))[0], "type": os.path.splitext(fp)[1].lower().lstrip("."), "sha256": h, "revision": 1, "indexed_at": time.strftime("%Y-%m-%d")}
            by_path[rel] = sid; by_hash[h] = sid
        pv = provenance_of(rel, prov) if prov else {}
        if pv: e["origin"] = pv.get("origin", "unknown"); e["client_approved"] = pv.get("approved"); e["provenance_note"] = pv.get("note", "")
        res = extract(fp, sid)
        if res is None or res[0] is None:
            reason = res[1] if res else "unknown"; e.update({"quality": "unextractable", "units": 0, "reason": reason}); unex.append((sid, rel, reason)); continue
        lines, quality, units = res
        e.update({"quality": quality, "units": units}); e.pop("reason", None)
        head = [f"# {sid} (rev {e['revision']}) - {e['title']}", f"source: {rel} | type: {e['type']} | sha256: {h[:12]} | extracted: {e['indexed_at']} | quality: {quality}"]
        if e.get("origin"): head.append(f"origin: {e['origin']} | client-approved: {'yes' if e.get('client_approved') else 'NO'}" + (f" | {e['provenance_note']}" if e.get("provenance_note") else ""))
        if e.get("aliases"): head.append("identical copies: " + "; ".join(e["aliases"]))
        head += ["cite as `" + sid + "#<anchor>` - anchors are the HTML comments below; never cite a line number of this file.", ""]
        open(os.path.join(TEXT, f"{sid}.md"), "w", encoding="utf-8").write("\n".join(head + lines) + "\n")
    idx["built_at"] = time.strftime("%Y-%m-%dT%H:%M:%S"); idx["inputs"] = [relp(x, PROJECT_DIR) for x in inputs]
    os.makedirs(CORPUS_DIR, exist_ok=True); json.dump(idx, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    allunex = [(k, v["path"], v.get("reason", "")) for k, v in idx["sources"].items() if v.get("quality") == "unextractable"]
    open(UNEX, "w", encoding="utf-8").write("# Unextractable sources\n\nNo text could be extracted. An analyst may cite these only as `visual, unverified` (confidence low) and must raise a client question for anything the deliverable depends on.\n\n" + "\n".join(f"- {k} `{p}`: {r}" for k, p, r in allunex) + "\n")
    if prov:
        from collections import Counter
        c = Counter(v.get("origin", "unknown") for v in idx["sources"].values()); print("origin: " + ", ".join(f"{k}={n}" for k, n in sorted(c.items())) + (" (provenance.json)" ))
    print(f"corpus: {len(idx['sources'])} sources ({n_new} new, {n_rev} revised, {n_prov} provenance updated, {n_dup} duplicate copies aliased, {len(allunex)} unextractable) -> {relp(INDEX, PROJECT_DIR)}, text/ ; index sha {hashlib.sha256(open(INDEX, 'rb').read()).hexdigest()[:12]}")
    import retrieval; retrieval.build()   # corpus/PROFILE.json + corpus/search/ (incremental per source)

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] == "index":
        inputs = [os.path.abspath(a[i + 1]) for i, x in enumerate(a) if x == "--input"] or [INPUT_DIR]
        inputs = [x for x in inputs if os.path.isdir(x)]
        if not inputs: sys.exit(f"no input folder ({INPUT_DIR}) - put the client's documents there (by date) or pass --input <dir>")
        index(inputs)
    elif a[0] == "list":
        idx = load_index()
        for k, v in idx["sources"].items(): print(f"{k:8s} rev{v['revision']} {v['type']:5s} {str(v.get('units', '')):>5s} {v.get('quality', ''):12s} {(v.get('origin') or '-'):18s} {v['path']}" + (f"  (+{len(v['aliases'])} identical copies)" if v.get("aliases") else ""))
        print(f"{len(idx['sources'])} sources, built {idx.get('built_at')}")
    elif a[0] == "show":
        fp = os.path.join(TEXT, f"{a[1]}.md")
        if not os.path.exists(fp): sys.exit("no such source")
        for l in open(fp, encoding="utf-8"):
            if l.startswith("<!--") or l.startswith("#") or l.startswith("source:"): print(l.rstrip())
    elif a[0] == "grep":
        rx = re.compile(a[1], re.I); n = 0
        for f in sorted(glob.glob(os.path.join(TEXT, "*.md"))):
            anchor = ""
            for l in open(f, encoding="utf-8"):
                m = re.match(r"<!-- (SRC-\d+#\S+) -->", l)
                if m: anchor = m.group(1)
                if rx.search(l) and not l.startswith("<!--"): print(f"{anchor or os.path.basename(f)}: {l.strip()[:160]}"); n += 1
        print(f"{n} hit(s)")
    elif a[0] in ("profile", "search", "map", "metrics"):
        import retrieval; retrieval.main(a)
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
