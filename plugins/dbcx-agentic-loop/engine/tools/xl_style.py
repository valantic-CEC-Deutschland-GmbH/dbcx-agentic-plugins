"""Style and chart engine of build_excel: valantic palette only, three header tiers,
status fills only on decision columns, no row stripes, freeze + filter + zoom + print setup, row heights that collapsed or
supporting columns never drive, tab colours by role, charts in the cell colours. `configure(style, footer)` once per build."""
import math, re
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule, FormulaRule, ColorScaleRule, DataBarRule
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.chart import PieChart, DoughnutChart, BarChart, Reference
from openpyxl.chart.series import DataPoint, SeriesLabel
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.descriptors import Typed
from openpyxl.chart.data_source import NumFmt

S = {}; FOOTER = [""]; DUPES = []   # (sheet, header) renamed because a table header repeated
LEGACY = {"GREEN": "standard", "BLUE": "standard", "YELLOW": "rework", "ORANGE": "rework", "RED": "rebuild", "GREY": "neutral", "GRAY": "neutral", "ACCENT": "rebuild"}
ROLE_OF = {"mgmt": "result", "table": "result", "overview": "result", "assumptions": "assumptions", "readme": "reference", "sources": "reference", "parameters": "reference", "claims": "internal", "open_questions": "internal"}
LINE_PT = 15


def configure(style, footer=""):
    S.clear(); S.update(style or {}); FOOTER[0] = footer
    if "header_fill" in S and "header" not in S: S["header"] = {"normal": {"fill": S["header_fill"], "color": "FFFFFF"}}   # overrides of older runs


def tok(k, d): return S.get(k, d)
def font(size=10, bold=False, color=None, italic=False): return Font(name=tok("font", "Segoe UI"), size=size, bold=bold, italic=italic, color=color or tok("text", "100C2A"))
def fill(rgb): return PatternFill("solid", fgColor=rgb, bgColor=rgb)
def status_key(v): return LEGACY.get(str(v).upper(), v) if v else v
def status_colour(key, part="fill"):
    st = (tok("status", {}) or {}).get(status_key(key)) or {}
    return st.get(part) or {"fill": "E8E8E8", "chart": "CDCDCD"}[part]
def sep(): return Border(bottom=Side(style="thin", color=tok("separator", "E3E3E8")))


def header(cell, tier="normal"):
    h = (tok("header", {}) or {}).get(tier) or (tok("header", {}) or {}).get("normal") or {"fill": "3C4BC8", "color": "FFFFFF"}
    cell.fill = fill(h["fill"]); cell.font = font(10, True, h.get("color", "FFFFFF")); cell.alignment = Alignment(wrap_text=True, vertical="center"); cell.border = sep()


def body(cell, tier="normal", wrap=False):
    if tier == "support": cell.font = font(9, color=tok("muted", "6B6880"))
    else: cell.font = font(10, bold=(tier == "decision"))
    cell.alignment = Alignment(wrap_text=wrap, vertical="top"); cell.border = sep()


def lines(v, width):
    """Wrapped line count of a cell value in a column of `width` characters (Segoe UI 10 ~ 1.15 chars per width unit)."""
    if v in (None, "") or (isinstance(v, str) and v.startswith("=")): return 1
    per = max(4, int((width or 10) * 1.15))
    return sum(max(1, math.ceil(len(p) / per)) for p in str(v).split("\n"))


def header_height(heads):
    """Header row: the longest wrapped header decides (bold ~ 1.0 char per width unit), 2 to 4 lines of 14 pt, min 32 pt."""
    n = max([max(1, math.ceil(len(str(h or "")) / max(4, int((w or 10) * 1.0)))) for h, w in heads] or [1])
    return max(32, min(4, n) * 14 + 4)


def row_height(n): return max(1, min(int(tok("max_row_lines", 6)), n)) * LINE_PT


BANDS = [{"band": "3C4BC8", "color": "FFFFFF", "header": "D4D7F3"}, {"band": "C0AA81", "color": "100C2A", "header": "E9E1D3"},
         {"band": "A78DB6", "color": "100C2A", "header": "E5DDE9"}, {"band": "100C2A", "color": "FFFFFF", "header": "E8E8E8"}]


def band_of(k): bands = tok("option_bands", None) or BANDS; return bands[k % len(bands)]   # the k-th option's colours


def option_band(ws, row, segs, tiers):
    """Band header above the column headers (row + 1) of a sheet with option blocks: segs = [(first col, last col, label, k)] ->
    one merged cell per block in the k-th style.option_bands colour; the block's normal-tier headers take the band's light tint
    (decision and support headers keep their tier fill); columns outside every block stay empty."""
    bands = tok("option_bands", None) or BANDS
    for c0, c1, label, k in segs:
        b = bands[k % len(bands)]; cell = ws.cell(row=row, column=c0, value=label)
        cell.fill = fill(b["band"]); cell.font = font(10, True, b.get("color", "FFFFFF")); cell.alignment = Alignment(horizontal="center", vertical="center"); cell.border = sep()
        if c1 > c0: ws.merge_cells(start_row=row, start_column=c0, end_row=row, end_column=c1)
        for c in range(c0, c1 + 1):
            if tiers[c - 1] == "normal": h = ws.cell(row=row + 1, column=c); h.fill = fill(b["header"]); h.font = font(10, True, b.get("header_color", tok("text", "100C2A")))
    ws.row_dimensions[row].height = 20


def table(ws, cols, rows, name, header_row=1, freeze="B2", sub=False, band=None, first_col=1, fit=None):
    """cols: [{header, width, tier, wrap, group}] ; rows: list of value lists. Header tiers, body style, row heights from
    visible wrapped columns only, Excel table without row stripes (filter), groups collapsed, sheet finish. -> last row.
    sub=True: a further table below or beside (first_col) another one on the same sheet - column widths and row heights only
    grow, no groups, no sheet finish. band=[(first col, last col, label, k)]: option band headers in row header_row - 1
    (option_band), printed with the header row; the band names the option, so headers repeat per block - no Excel table
    object then (it needs unique header names), a plain autofilter instead. fit=n: n pages wide instead of pages_wide()."""
    seen = {}; x0 = first_col - 1
    for c, col in enumerate(cols, 1):   # an Excel table needs unique header names (duplicates make Excel repair the file)
        h = str(col["header"] if col["header"] not in (None, "") else f"Spalte {c}"); k = h.strip().lower(); seen[k] = seen.get(k, 0) + 1
        if seen[k] > 1 and not band: h = f"{h} ({seen[k]})"; DUPES.append((ws.title, h))
        header(ws.cell(row=header_row, column=x0 + c, value=h), col.get("tier", "normal")); cd = ws.column_dimensions[get_column_letter(x0 + c)]
        cd.width = max(cd.width or 0, col.get("width", 16)) if sub else col.get("width", 16)
    grow = lambda r, h: max(ws.row_dimensions[r].height or 0, h) if sub else h
    ws.row_dimensions[header_row].height = grow(header_row, header_height([(c["header"], c.get("width", 16)) for c in cols]))
    drive = [i for i, col in enumerate(cols) if col.get("wrap") and col.get("tier") != "support" and not col.get("group")]
    for r, row in enumerate(rows, header_row + 1):
        for c, v in enumerate(row, 1):
            col = cols[c - 1]; body(ws.cell(row=r, column=x0 + c, value=v), col.get("tier", "normal"), bool(col.get("wrap")))
        ws.row_dimensions[r].height = grow(r, row_height(max([lines(row[i], cols[i].get("width", 16)) for i in drive if i < len(row)] or [1])))
    end = max(header_row + 1, header_row + len(rows)); ref = f"{get_column_letter(first_col)}{header_row}:{get_column_letter(x0 + len(cols))}{end}"
    if band: ws.auto_filter.ref = ref
    else:
        tn = re.sub(r"\W", "", name) or "T"; taken = {t.lower() for s in ws.parent.worksheets for t in s.tables}; base = tn; k = 2
        while tn.lower() in taken: tn = f"{base}{k}"; k += 1   # table names are workbook-global (an engine sheet may meet a method table)
        t = Table(displayName=tn, ref=ref)
        t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False, showColumnStripes=False); ws.add_table(t)
    if sub: return end
    i = 0
    while i < len(cols):   # consecutive columns of one group -> one collapsed outline group
        g = cols[i].get("group"); j = i
        while g and j + 1 < len(cols) and cols[j + 1].get("group") == g: j += 1
        if g: ws.column_dimensions.group(get_column_letter(i + 1), get_column_letter(j + 1), hidden=True, outline_level=1)
        i = j + 1
    if band: option_band(ws, header_row - 1, band, [c.get("tier", "normal") for c in cols])
    finish(ws, freeze=freeze, title_rows=f"{header_row - 1 if band else header_row}:{header_row}", pages_wide=fit or pages_wide([c.get("width", 16) for c in cols if not c.get("group")]))
    return end


PAGE_PT = 770   # A4 landscape printable width at default margins (0.7 in each side)


def pages_wide(widths, min_scale=0.6):
    """Pages across for the VISIBLE columns (collapsed groups print hidden): 1 while the fit scale stays >= min_scale, else as
    many as keep min_scale. Column width w chars ~ (7w + 5) px ~ 0.75 * that in pt."""
    total = sum((7 * w + 5) * 0.75 for w in widths)
    return max(1, math.ceil(total * min_scale / PAGE_PT)) if total * min_scale > PAGE_PT else 1


def finish(ws, role=None, freeze=None, title_rows=None, landscape=True, grid=True, pages_wide=1):
    if role: ws.sheet_properties.tabColor = (tok("tabs", {}) or {}).get(role, "CDCDCD")
    if freeze: ws.freeze_panes = freeze
    ws.sheet_view.zoomScale = int(tok("zoom", 90)); ws.sheet_view.showGridLines = grid
    ws.page_setup.orientation = "landscape" if landscape else "portrait"; ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.fitToWidth = pages_wide; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    if title_rows: ws.print_title_rows = title_rows
    if FOOTER[0]: ws.oddFooter.center.text = FOOTER[0]; ws.oddFooter.center.size = 8


def tab(ws, role): ws.sheet_properties.tabColor = (tok("tabs", {}) or {}).get(role, "CDCDCD")


def status_rule(ws, rng, first, value, key, prefix=False):
    f = fill(status_colour(key))
    if prefix: ws.conditional_formatting.add(rng, FormulaRule(formula=[f'LEFT({first},{len(value)})="{value}"'], fill=f, stopIfTrue=True))
    else: ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{value}"'], fill=f, stopIfTrue=True))


def scale_rule(ws, rng, s):
    """Numeric heat scale in palette tints (standard -> rework -> rebuild); legacy colour names are mapped."""
    c = lambda k, d: status_colour(status_key(s.get(k)) or d)
    if "mid" in s: ws.conditional_formatting.add(rng, ColorScaleRule(start_type="num", start_value=s.get("min", 0), start_color=c("min_color", "standard"), mid_type="num", mid_value=s["mid"], mid_color=c("mid_color", "rework"), end_type="num", end_value=s.get("max", 1), end_color=c("max_color", "rebuild")))
    else: ws.conditional_formatting.add(rng, ColorScaleRule(start_type="num", start_value=s.get("min", 0), start_color=c("min_color", "standard"), end_type="num", end_value=s.get("max", 1), end_color=c("max_color", "rebuild")))


def databar(ws, rng): ws.conditional_formatting.add(rng, DataBarRule(start_type="min", end_type="max", color=status_colour("standard", "chart"), showValue=True))


# ---------------------------------------------------------------- charts (§2.4): values/percent only in labels, never "Series1"
class LabelList(DataLabelList):
    """DataLabelList whose numFmt carries sourceLinked (openpyxl writes the bare formatCode): a German Excel re-codes a format that is not
    explicitly unlinked (#,##0 -> #.##00). Redeclaring numFmt alone would shrink __elements__ to it: keep all of them, else dLbls is written empty."""
    __elements__ = DataLabelList.__elements__; __nested__ = tuple(n for n in DataLabelList.__nested__ if n != "numFmt")   # the metaclass derives both from this class's own attributes only
    numFmt = Typed(expected_type=NumFmt, allow_none=True)


def chart(kind, ws, cats, series, title, point_colours=None, series_colours=None, height=7.5, width=12, label_format=None):
    """cats = (min_col, min_row, max_row) on ws; series = [(col, title)] with values in the same rows; label_format: the data
    labels' number format (else Excel's default)."""
    kind = (kind or "pie").lower(); c0, r0, r1 = cats
    if kind in ("pie", "doughnut"):
        ch = DoughnutChart(holeSize=55) if kind == "doughnut" else PieChart(); series = series[:1]
    else:
        ch = BarChart(); ch.type = "bar" if kind == "bar" else "col"
        if kind == "stacked": ch.grouping = "stacked"; ch.overlap = 100
        ch.x_axis.delete = False; ch.y_axis.delete = False; ch.y_axis.majorGridlines = None; ch.x_axis.title = None; ch.y_axis.title = None
        ch.y_axis.numFmt = NumFmt(formatCode="#,##0", sourceLinked=False); ch.y_axis.scaling.min = 0; ch.gapWidth = 60   # never a truncated baseline, no repeated rounded ticks
        if kind == "bar": ch.x_axis.scaling.orientation = "maxMin"; ch.y_axis.crosses = "max"   # first category on top, as in the table; values axis stays at the bottom
    for col, stitle in series:
        ch.add_data(Reference(ws, min_col=col, min_row=r0, max_row=r1), titles_from_data=False)
        ch.series[-1].tx = SeriesLabel(v=str(stitle or title or " "))
    ch.set_categories(Reference(ws, min_col=c0, min_row=r0, max_row=r1)); ch.title = title or None
    seq = tok("chart_sequence", ["3C4BC8", "C0AA81", "A78DB6", "CDCDCD", "100C2A"])
    for si, s in enumerate(ch.series):
        dl = LabelList(); dl.showVal = kind not in ("pie", "doughnut"); dl.showPercent = kind in ("pie", "doughnut")
        dl.showCatName = False; dl.showSerName = False; dl.showLegendKey = False; s.dLbls = dl
        if label_format: dl.numFmt = NumFmt(formatCode=label_format, sourceLinked=False)
        if kind == "stacked" or len(ch.series) > 1:
            s.graphicalProperties.solidFill = (series_colours or [None] * 99)[si] or seq[si % len(seq)]; s.graphicalProperties.line.solidFill = "FFFFFF"
            continue
        n = r1 - r0 + 1; pc = point_colours or [None] * n
        if kind in ("bar", "col") and not any(pc):   # no status map: one colour, never an arbitrary (e.g. black) bar
            s.graphicalProperties.solidFill = status_colour("standard", "chart"); continue
        for i in range(n):
            pt = DataPoint(idx=i); pt.graphicalProperties.solidFill = pc[i] if i < len(pc) and pc[i] else seq[i % len(seq)]; pt.graphicalProperties.line.solidFill = "FFFFFF"; s.dPt.append(pt)
    if kind in ("bar", "col") and len(ch.series) == 1: ch.legend = None
    elif ch.legend is not None: ch.legend.position = "r"; ch.legend.overlay = False   # a bottom legend collides with the category labels
    if kind == "bar" and ch.title is not None and r1 - r0 + 1 >= 12:   # many categories: the title must not cover the first one
        ch.title.overlay = False; ch.layout = Layout(manualLayout=ManualLayout(layoutTarget="inner", xMode="edge", yMode="edge", x=0.25, y=0.14, w=0.70, h=0.78))
    ch.height = height; ch.width = width
    return ch
