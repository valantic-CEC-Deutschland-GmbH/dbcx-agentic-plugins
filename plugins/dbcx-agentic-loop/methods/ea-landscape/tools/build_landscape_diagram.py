#!/usr/bin/env python3
"""Generate the landscape diagrams (draw.io) from the same JSON the workbooks are built from, in the valantic landscape legend.

Usage: dbcx build_landscape_diagram [--as-is] [--target] [--png] [--no-layout]   (no --as-is/--target = both, as far as the inputs exist)
Reads  analysis/inventory/landscape_inventory.json   systems (category, lifecycle, relevance, vendor_product), data objects (claimed masters)
       analysis/consolidated/FLOWS.json              flows (F-nnn) with data objects, style, frequency, middleware, confidence
       analysis/consolidated/TARGET.json             options with strategic moves, systems affected, flows changed, masters that move (target)
Writes <run>/deliverables/<deliverables.D1.diagram>   the as-is landscape
       <run>/deliverables/<deliverables.D4.diagram>   the target landscape
(+ .png each when --png and the draw.io desktop CLI is installed; otherwise open the file in draw.io and use Arrange > Layout.)
--no-layout (or DBCX_NO_DRAWIO_CLI=1) writes the XML and never calls the draw.io desktop CLI.

Legend (knowledge/reference-architectures/valantic-cx-target, section 2 - approved 2026-09-09): lanes Experience and channels /
Integration and data / Systems of record; box fill+border = lifecycle status (keep grey, new green, replace orange, retire hatched grey
dashed, decision open blue dashed, context white dotted); arrow style = integration style (api solid black, event dashed black,
file/batch dash-dot grey with open head, manual solid with a person marker, unknown dotted grey); labels = flow id, data objects,
frequency, middleware; * = SSOT marker with the mastered data objects, ! = mastership conflict. Nothing is typed in by hand.
"""
import os, sys, html, re, shutil, subprocess

if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, project, labels, load_json, relp

# valantic landscape legend: status -> (fill, stroke, extra draw.io style)
STATUS_STYLE = {
    "keep":    ("#F2F2F2", "#616161", ""),
    "new":     ("#C8E6C9", "#2E7D32", ""),
    "replace": ("#FFE0B2", "#EF6C00", ""),
    "retire":  ("#EEEEEE", "#9E9E9E", "dashed=1;dashPattern=6 4;fillStyle=hatch;"),
    "open":    ("#E3F2FD", "#1E88E5", "dashed=1;dashPattern=7 4;"),
    "context": ("#FFFFFF", "#BDBDBD", "dashed=1;dashPattern=2 3;strokeWidth=1;"),
}
# integration style -> (stroke colour, extra style)
FLOW_STYLE = {
    "api":     ("#1A1A1A", "endArrow=block;endFill=1;"),
    "event":   ("#1A1A1A", "endArrow=block;endFill=1;dashed=1;dashPattern=6 4;"),
    "file":    ("#757575", "endArrow=open;endFill=0;dashed=1;dashPattern=8 3 2 3;"),
    "batch":   ("#757575", "endArrow=open;endFill=0;dashed=1;dashPattern=8 3 2 3;"),
    "manual":  ("#1A1A1A", "endArrow=block;endFill=1;"),
    "unknown": ("#9E9E9E", "endArrow=block;endFill=0;dashed=1;dashPattern=2 3;"),
}
LANES = [("Experience and channels", ["commerce", "cms", "search", "marketing"]),
         ("Integration and data", ["integration", "analytics"]),
         ("Systems of record", ["erp", "pim", "dam", "mdm", "crm", "service", "custom", "other"])]
OPEN_RX = re.compile(r"^\s*$|\b(tbd|open|to be decided|offen|\?)", re.I)
COL_W, ROW_H, BOX_W, BOX_H, LANE_X = 230, 120, 190, 64, 170
SSOT, CONFLICT, PERSON = "&#9733;", "&#9888;", "&#128100;"   # star, warning sign, bust-in-silhouette (draw.io renders HTML entities)


def find_cli():
    for c in ["drawio", "draw.io", "/Applications/draw.io.app/Contents/MacOS/draw.io", "/usr/bin/drawio", "/opt/drawio/drawio"]:
        p = shutil.which(c) or (c if os.path.exists(c) else None)
        if p:
            return p
    return None


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def node(nid, x, y, label, status, w=BOX_W, h=BOX_H):
    fill, stroke, extra = STATUS_STYLE.get(status, STATUS_STYLE["keep"])
    return (f'<mxCell id="{nid}" value="{esc(label)}" style="rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
            f'strokeWidth=2;fontFamily=Segoe UI;fontSize=11;fontColor=#1A1A1A;align=center;verticalAlign=middle;{extra}'
            f'" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def text(nid, x, y, w, h, label, size=10, bold=False, colour="#1A1A1A"):
    label = str(label).replace("\n", "<br>")
    return (f'<mxCell id="{nid}" value="{esc(label)}" style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;'
            f'fontFamily=Segoe UI;fontSize={size};fontColor={colour};{"fontStyle=1;" if bold else ""}strokeColor=none;fillColor=none;'
            f'" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def edge(eid, src, dst, label, style, width=1.5, opacity=100):
    colour, extra = FLOW_STYLE.get(style or "unknown", FLOW_STYLE["unknown"])
    return (f'<mxCell id="{eid}" value="{esc(label)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;{extra}'
            f'strokeColor={colour};strokeWidth={width};opacity={opacity};textOpacity={opacity};fontFamily=Segoe UI;fontSize=9;fontColor=#1A1A1A;labelBackgroundColor=#FFFFFF;'
            f'" edge="1" parent="1" source="{src}" target="{dst}"><mxGeometry relative="1" as="geometry"/></mxCell>')


def lane_box(nid, y, h, title, width):
    """Lane = rotated label at the left edge plus a dashed separator below the lane (no empty container boxes)."""
    return (f'<mxCell id="{nid}" value="{esc(title)}" style="text;html=1;whiteSpace=wrap;align=center;verticalAlign=middle;rotation=-90;'
            f'fontFamily=Segoe UI;fontSize=11;fontColor=#757575;fontStyle=1;strokeColor=none;fillColor=none;" vertex="1" parent="1">'
            f'<mxGeometry x="{-h / 2 + 20}" y="{y + h / 2 - 12}" width="{h}" height="24" as="geometry"/></mxCell>'
            f'<mxCell id="{nid}_sep" style="endArrow=none;strokeColor=#BDBDBD;dashed=1;dashPattern=6 5;strokeWidth=1;" edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry"><mxPoint x="{60}" y="{y + h + 12}" as="sourcePoint"/><mxPoint x="{width}" y="{y + h + 12}" as="targetPoint"/></mxGeometry></mxCell>')


def wrap(cells):
    return '<mxGraphModel adaptiveColors="auto" grid="1" gridSize="10" page="1"><root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel>"


def as_list(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in re.split(r"[,;/]", str(v or "")) if x.strip() and x.strip().lower() not in ("-", "none", "unknown")]


def status_as_is(s):
    lc = (s.get("lifecycle") or "").lower()
    if s.get("relevance") == "out-of-scope":
        return "context"
    if lc in ("retiring", "retired"):
        return "retire"
    if lc == "planned":
        return "open" if OPEN_RX.search(s.get("vendor_product") or "") else "new"
    return "keep"


def markers(inv):
    """SSOT star per system (data objects with exactly one claimed master) and conflict sign (two or more claimants)."""
    star, conflict = {}, {}
    for d in inv.get("data_objects", []) or []:
        ms = as_list(d.get("claimed_master_systems"))
        if len(ms) == 1:
            star.setdefault(ms[0], []).append(d.get("name", ""))
        elif len(ms) > 1:
            for m in ms:
                conflict.setdefault(m, []).append(d.get("name", ""))
    return star, conflict


def label_of(s, L, star, conflict, extra=""):
    sub = " / ".join(x for x in [s.get("vendor_product"), s.get("version"), extra] if x)
    line3 = []
    if s["name"] in star:
        line3.append(f"<font color='#F9A825'>{SSOT}</font> " + ", ".join(star[s["name"]]))
    if s["name"] in conflict:
        line3.append(f"<font color='#C62828'>{CONFLICT}</font> " + ", ".join(conflict[s["name"]]))
    return f"<b>{s['name']}</b>" + (f"<br><font style='font-size:9px'>{sub}</font>" if sub else "") + ("".join(f"<br><font style='font-size:8px'>{x}</font>" for x in line3))


def lay_out(systems, cats, L, star, conflict):
    """Three lanes (experience / integration / record), systems ordered by category inside a lane; returns (cells, ids, bottom_y)."""
    lane_of = {c: t for t, cs in LANES for c in cs}
    cells, ids, y = [], {}, 0
    width = LANE_X + max(1, min(5, max((sum(1 for s in systems if lane_of.get((s.get("category") or "other"), "Systems of record") == t) for t, _ in LANES), default=1))) * COL_W
    for title, lane_cats in LANES:
        order = [c for c in cats if c in lane_cats] + [c for c in lane_cats if c not in cats]
        mine = [s for s in systems if lane_of.get((s.get("category") or "other"), "Systems of record") == title]
        if not mine:
            continue
        mine.sort(key=lambda s: (order.index(s.get("category") or "other") if (s.get("category") or "other") in order else 99, s.get("name", "")))
        per_row = max(1, min(len(mine), 5))
        rows = (len(mine) + per_row - 1) // per_row
        cells.append(lane_box(f"lane{len(cells)}", y, rows * ROW_H, L.get("_lane_" + title.split()[0].lower(), title), width))
        for i, s in enumerate(mine):
            nid = f"n{len(ids)}"
            ids[s["name"]] = (nid, s)
            cells.append(node(nid, LANE_X + (i % per_row) * COL_W, y + 20 + (i // per_row) * ROW_H, label_of(s, L, star, conflict, s.get("_extra", "")), s.get("_status") or status_as_is(s)))
        y += rows * ROW_H + 30
    return cells, ids, y, width


def flow_label(f, L):
    objs = ", ".join(as_list(f.get("data_objects")))
    bits = [x for x in [f.get("frequency"), f.get("middleware")] if x]
    style = (f.get("style") or "unknown").lower()
    lab = " ".join(x for x in [f.get("id"), (PERSON + " ") if style == "manual" else "", objs] if x)
    if style == "unknown":
        bits.append(L.get("unknown", "style unknown"))
    if f.get("confidence") == "low":
        bits.append(L.get("_diagram_visual_unverified", "visual, unverified"))
    return lab + (f" ({'; '.join(bits)})" if bits else "")


def legend_cells(L, y, target=False, x0=1150):
    """The legend block every board carries (top right, right of the widest lane); status swatches, arrow styles, markers."""
    cells = [text("lg_title", x0, y, 240, 20, L.get("_diagram_legend_title", "Legend"), size=11, bold=True)]
    rows = [("keep", L.get("_status_keep", "existing, kept")), ("new", L.get("_status_new", "new")), ("replace", L.get("_status_replace", "to be replaced")),
            ("retire", L.get("_status_retire", "retiring")), ("open", L.get("_status_open", "decision open (capability term only)")), ("context", L.get("_status_context", "context, unchanged"))]
    yy = y + 24
    for st, lab in rows:
        cells.append(node(f"lg_{st}", x0, yy, "", st, w=34, h=16)); cells.append(text(f"lgt_{st}", x0 + 42, yy - 3, 220, 20, lab, size=9)); yy += 22
    for st, lab in [("api", L.get("_flow_api", "synchronous API")), ("event", L.get("_flow_event", "asynchronous event / message")), ("file", L.get("_flow_file", "file or batch")),
                    ("manual", PERSON + " " + L.get("_flow_manual", "manual step (person)")), ("unknown", L.get("_flow_unknown", "style not documented"))]:
        colour, extra = FLOW_STYLE[st]
        cells.append(f'<mxCell id="lgl_{st}" style="html=1;{extra}strokeColor={colour};strokeWidth=1.5;" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
                     f'<mxPoint x="{x0}" y="{yy + 8}" as="sourcePoint"/><mxPoint x="{x0 + 34}" y="{yy + 8}" as="targetPoint"/></mxGeometry></mxCell>')
        cells.append(text(f"lglt_{st}", x0 + 42, yy - 3, 220, 20, lab, size=9)); yy += 22
    cells.append(text("lg_marks", x0, yy, 260, 40, f"<font color='#F9A825'>{SSOT}</font> {L.get('_marker_ssot', 'single source of truth for the listed data objects')}<br><font color='#C62828'>{CONFLICT}</font> {L.get('_marker_conflict', 'mastership claimed by more than one system (client decision)')}", size=9))
    if target:
        cells.append(text("lg_target", x0, yy + 44, 260, 30, L.get("_diagram_legend_target_arrows", "Thick arrows: flows an option changes; faded arrows: unchanged."), size=9))
    return cells


def build_as_is(p, L, inv, flows, out):
    systems = [dict(s) for s in inv.get("systems", [])]
    if not systems:
        print("as-is: the inventory has no systems - nothing to draw"); return None
    star, conflict = markers(inv)
    cells, ids, bottom, width = lay_out(systems, p["system"]["categories"], L, star, conflict)
    n_edges = 0
    for i, f in enumerate(flows.get("flows", [])):
        a, b = ids.get(f.get("from_system")), ids.get(f.get("to_system"))
        if not a or not b:
            continue
        cells.append(edge(f"e{i}", a[0], b[0], flow_label(f, L), (f.get("style") or "unknown").lower()))
        n_edges += 1
    cells.insert(0, text("title", 0, -70, 1100, 30, L.get("_diagram_asis_title", "As-is landscape") + f" - {p['engagement'].get('client', '')}", size=16, bold=True))
    cells.insert(1, text("legend", 0, -40, 1100, 36, L.get("_diagram_legend_asis", "As-is landscape generated from the inventory and the flow list."), size=9, colour="#616161"))
    cells += legend_cells(L, -70, x0=width + 60)
    open(out, "w", encoding="utf-8").write(wrap(cells))
    print(f"as-is: {len(ids)} systems, {n_edges} flows, {sum(len(v) for v in star.values())} SSOT markers, {len(conflict)} systems with a mastership conflict -> {relp(out, ROOT)}")
    return out


def build_target(p, L, inv, flows, target, out):
    opts = [o for o in target.get("options", []) if o.get("recommendation") != "rejected"]
    if not opts:
        print("target: no option with a recommendation - nothing to draw"); return None
    move_of = {}
    order = ["keep", "re-home-ssot", "consolidate", "replace", "retire", "introduce"]
    for o in opts:
        for s in as_list(o.get("systems_affected")):
            cur = move_of.get(s)
            mv = o.get("strategic_move", "keep")
            if cur is None or order.index(mv if mv in order else "keep") > order.index(cur):
                move_of[s] = mv if mv in order else "keep"
    systems = [dict(s) for s in inv.get("systems", []) if s.get("relevance") != "out-of-scope" or s.get("name") in move_of]
    known = {s["name"] for s in systems}
    for s, mv in move_of.items():
        if s not in known:
            systems.append({"name": s, "category": "other", "vendor_product": "", "lifecycle": "planned"})
    star, conflict = markers(inv)
    for o in opts:   # masters that move: the target star sits on the receiving system(s)
        for obj in as_list(o.get("data_objects_re_mastered")):
            for s in as_list(o.get("systems_affected")):
                if o.get("strategic_move") in ("re-home-ssot", "introduce"):
                    star.setdefault(s, []).append(obj)
    for s in systems:
        mv = move_of.get(s["name"])
        inv_known = s["name"] in known
        if mv == "introduce" or not inv_known:
            s["_status"] = "open" if OPEN_RX.search(s.get("vendor_product") or "") else "new"
        elif mv in ("replace", "consolidate"):
            s["_status"] = "replace"
        elif mv == "retire":
            s["_status"] = "retire"
        else:
            s["_status"] = status_as_is(s)
        if mv:
            s["_extra"] = L.get(mv, mv)
    cells, ids, bottom, width = lay_out(systems, p["system"]["categories"], L, star, conflict)
    changed = {fid for o in opts for fid in as_list(o.get("flows_changed"))}
    by_id = {f.get("id"): f for f in flows.get("flows", [])}
    n_ch = n_keep = 0
    for i, f in enumerate(flows.get("flows", [])):
        a, b = ids.get(f.get("from_system")), ids.get(f.get("to_system"))
        if not a or not b:
            continue
        st = (f.get("style") or "unknown").lower()
        if f.get("id") in changed:
            cells.append(edge(f"e{i}", a[0], b[0], flow_label(f, L) + "  " + L.get("_diagram_changes", "[changes]"), st, width=2.5)); n_ch += 1
        else:
            cells.append(edge(f"e{i}", a[0], b[0], flow_label(f, L), st, width=1.0, opacity=40)); n_keep += 1
    missing = sorted(changed - set(by_id))
    rem = [o for o in opts if as_list(o.get("data_objects_re_mastered"))]
    lines = [L.get("_diagram_legend_target", "Target landscape generated from the option list.")]
    lines.append(L.get("_diagram_options", "Options in the picture") + ": " + "; ".join(f"{o.get('id')} {L.get(o.get('strategic_move'), o.get('strategic_move'))} {', '.join(as_list(o.get('systems_affected')))} [{L.get(o.get('recommendation'), o.get('recommendation'))}]" + (("  " + (str(o.get("phase")) if not str(o.get("phase")).strip().isdigit() else f"P{o.get('phase')}")) if o.get("phase") else "") for o in opts))
    if rem:
        lines.append(L.get("_diagram_masters_move", "Masters that move") + ": " + "; ".join(f"{o.get('id')}: {', '.join(as_list(o.get('data_objects_re_mastered')))}" for o in rem))
    if missing:
        lines.append("Flow ids named by an option that the flow list does not contain: " + ", ".join(missing))
    cells.insert(0, text("title", 0, -110, 1100, 30, L.get("_diagram_target_title", "Target landscape") + f" - {p['engagement'].get('client', '')}", size=16, bold=True))
    cells.insert(1, text("legend", 0, -80, 1100, 76, "\n".join(lines), size=9, colour="#616161"))
    cells += legend_cells(L, -110, target=True, x0=width + 60)
    open(out, "w", encoding="utf-8").write(wrap(cells))
    print(f"target: {len(ids)} systems, {n_ch} changed flows, {n_keep} unchanged flows, {len(move_of)} systems touched by an option -> {relp(out, ROOT)}")
    if missing:
        print("  WARNING: options reference flow ids that are not in FLOWS.json: " + ", ".join(missing))
    return out


def drawio(cli, args, what, path):
    """The draw.io desktop CLI starts a GUI application: it may be slow, need a display or hang - never let it fail the build."""
    try:
        r = subprocess.run([cli] + args, capture_output=True, text=True, timeout=90)
    except Exception as e:
        print(f"  {what}: skipped ({type(e).__name__}: {str(e)[:120]}) - the .drawio file is written; open it in draw.io for {what}")
        return False
    print(f"  {what}:", "ok" if r.returncode == 0 else (r.stderr or r.stdout)[:200].strip() or f"exit {r.returncode}")
    return r.returncode == 0


def main():
    argv = sys.argv[1:]
    p = project(); L = labels()
    want_asis = "--as-is" in argv or not ("--as-is" in argv or "--target" in argv)
    want_target = "--target" in argv or not ("--as-is" in argv or "--target" in argv)
    inv = load_json("analysis/inventory/landscape_inventory.json", None)
    if not inv:
        sys.exit("missing analysis/inventory/landscape_inventory.json - the inventory has to be converted first (dbcx md_to_json inventory ...)")
    flows = load_json("analysis/consolidated/FLOWS.json", {"flows": []}) or {"flows": []}
    out_dir = os.path.join(ROOT, "deliverables"); os.makedirs(out_dir, exist_ok=True)
    written = []
    if want_asis:
        w = build_as_is(p, L, inv, flows, os.path.join(out_dir, p["deliverables"]["D1"].get("diagram", "Landscape_AsIs.drawio")))
        if w:
            written.append(w)
    if want_target:
        t = load_json("analysis/consolidated/TARGET.json", None)
        if not t:
            print("target: analysis/consolidated/TARGET.json does not exist yet - the target diagram is drawn after the TARGET consolidation")
        else:
            w = build_target(p, L, inv, flows, t, os.path.join(out_dir, p["deliverables"]["D4"].get("diagram", "Landscape_Target.drawio")))
            if w:
                written.append(w)
    if "--no-layout" in argv or os.environ.get("DBCX_NO_DRAWIO_CLI"):
        print("draw.io CLI not called (--no-layout): the XML carries its own lane layout; open it in draw.io for a prettier one")
        return
    cli = find_cli()
    if cli:
        for w in written:
            if "--png" in argv:
                drawio(cli, ["-x", "-f", "png", "-e", "-b", "10", "-s", "2", "-o", w + ".png", w], "png", w)
    elif written:
        print("draw.io CLI not found: .drawio written with the lane layout (open in draw.io to adjust)")


if __name__ == "__main__":
    main()
