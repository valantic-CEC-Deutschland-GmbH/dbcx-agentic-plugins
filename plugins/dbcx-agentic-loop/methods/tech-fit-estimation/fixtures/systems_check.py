#!/usr/bin/env python3
"""Workbook assertions of the system-mode smoke variants `systems` (two scenarios) and `systems-single` (the real flow; run in the run folder, env VARIANT, LANGV). The totals are recomputed from the workbook's formulas with fixtures/xl_eval.py and
compared with the fixture's own work packages (fixture_expected.json):

  * sheets: the client's pass-through sheet, the other rows, the long-form estimation, Summen, Vollstaendigkeit in both editions; Szenarien
    and Vergleich only with two scenarios; the workshop-source column hidden from the customer edition (present in the full one)
  * per system x release and per system (development, surcharges, fixed phases, total) of the selected scenario; davon bedingt and davon
    Zwischenloesung; the superseded first estimate is not counted
  * pass-through roll-up per client row and the reconciliation (client list + other rows = development, difference 0)
  * external cells: open count per owner; a number pasted into one cell enters every total (without surcharges) and closes the cell
  * the range: min / max = likely x factor by certainty; a factor edited on the Parameter sheet moves them
  * two scenarios: the selector on the Parameter sheet switches every single-scenario view; Vergleich shows every scenario's total
  * the architect: the overruled gap's first estimate (superseded by the follow-up chunk) is not counted; the packages routed to the
    middleware carry "routed from" and count in the receiving system in every scenario; the SAP BTP input cell (route-landscape) is
    listed in Vollstaendigkeit with its client assumption A-nn, which the Annahmen sheet holds; every gap is listed with its decision
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openpyxl
from xl_eval import Evaluator

V = os.environ.get("VARIANT", "systems"); DE = os.environ.get("LANGV", "en") == "de"; MULTI = V == "systems"
N = {k: (a if DE else b) for k, a, b in (("ES", "Schaetzung", "Estimation"), ("SU", "Summen", "Totals"), ("SZ", "Szenarien", "Scenarios"), ("VG", "Vergleich", "Comparison"),
                                           ("VS", "Vollstaendigkeit", "Completeness"), ("OT", "Weitere_Zeilen", "Other_Rows"), ("PA", "Parameter", "Parameters"), ("CL", "Aussagen", "Claims"),
                                           ("ZP", "Zuschlaege_und_Phasen", "Surcharges_and_Phases"))}
H = {k: (a if DE else b) for k, a, b in (("total", "Gesamt (PT)", "Total (PD)"), ("cond", "davon bedingt (PT)", "of which conditional (PD)"), ("interim", "davon Zwischenlösung (PT)", "of which interim solution (PD)"),
                                           ("dev", "Entwicklung (PT)", "Development (PD)"), ("sur", "Zuschläge (PT)", "Surcharges (PD)"), ("ph", "Feste Phasen (PT)", "Fixed phases (PD)"),
                                           ("open", "Offene Eingaben", "Open inputs"), ("min", "Entwicklung min (PT)", "Development min (PD)"), ("pd", "Aufwand (PT)", "Effort (PD)"),
                                           ("diff", "Abweichung (muss 0 sein)", "Difference (must be 0)"), ("sel", "Szenario", "Scenario"), ("total_label", "Gesamt", "Total"))}
X = json.load(open("fixture_expected.json")); F = "Fit_Estimation_Systems.xlsx"
cust = openpyxl.load_workbook(f"deliverables/{F}"); full = openpyxl.load_workbook(f"deliverables/intern/{F}")
for k in ("ES", "SU", "VS", "OT", "PA", "ZP"): assert N[k] in cust.sheetnames, (N[k], cust.sheetnames)
CS = X["client_sheet"]   # the client's pass-through sheet keeps its name
assert CS in cust.sheetnames and N["CL"] in full.sheetnames and N["CL"] not in cust.sheetnames, cust.sheetnames
assert (N["SZ"] in cust.sheetnames) == MULTI and (N["VG"] in cust.sheetnames) == MULTI, f"{V}: Szenarien / Vergleich only with two scenarios ({cust.sheetnames})"
hid = X["hidden_header"]
assert hid not in [c.value for c in cust[CS][1]] and hid in [c.value for c in full[CS][1]], "the hidden workshop-source column must be in the full edition only"

ev = Evaluator(cust); near = lambda a, b: abs(float(a or 0) - float(b)) < 1e-6
def head(ws, hr=1): return {ws.cell(hr, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(hr, c).value}
def rows(sheet):
    ws = cust[sheet]; h = head(ws); return ws, h, [r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value not in (None, "")]
def val(sheet, r, c): return ev.value(sheet, cust[sheet].cell(r, c).coordinate)
def block(sheet, first_header):
    """{row label: {header: value}} of the overview matrix whose header row starts with first_header"""
    ws = cust[sheet]
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, 1).value == first_header:
            h = {ws.cell(r, c).value: c for c in range(2, ws.max_column + 1) if ws.cell(r, c).value}; out = {}; rr = r + 1
            while rr <= ws.max_row and ws.cell(rr, 1).value not in (None, ""):
                out[ws.cell(rr, 1).value] = {k: ev.value(sheet, ws.cell(rr, c).coordinate) for k, c in h.items()}; rr += 1
            return out
    raise AssertionError(f"{sheet}: no block with header {first_header}")
def kv(sheet, label):
    ws = cust[sheet]
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, 1).value == label: return ev.value(sheet, f"B{r}")
    raise AssertionError(f"{sheet}: no row {label}")

pa = cust[N["PA"]]; sel_row = next(r for r in range(2, pa.max_row + 1) if pa.cell(r, 1).value == H["sel"])
def expected(sc, extra=None):
    """per system: dev, surcharges, phases, total; per (system, release) dev; cond / interim; per rollup id dev"""
    extra = extra or {}; out = {"sys": {}, "rel": {}, "cond": 0.0, "interim": 0.0, "roll": {}, "open": 0}
    for w in X["wps"]:
        if sc not in w["scenarios"]: continue
        pd = extra.get((w["row"], w["system"]), w["pd"]) if w["ext"] else w["pd"]
        if w["ext"] and (w["row"], w["system"]) not in extra: out["open"] += 1
        s = out["sys"].setdefault(w["system"], {"dev": 0.0, "sur": 0.0, "ph": 0.0}); s["dev"] += pd
        if not w["ext"]: s["sur"] += pd * X["surcharge_pct"] / 100
        out["rel"][(w["system"], w["release"])] = out["rel"].get((w["system"], w["release"]), 0) + pd
        out["cond"] += pd if w["cond"] else 0; out["interim"] += pd if w["interim"] else 0; out["roll"][w["rollup"]] = out["roll"].get(w["rollup"], 0) + pd
    for p in X["phases"]:
        if sc in p["scenarios"]: out["sys"].setdefault(p["system"], {"dev": 0.0, "sur": 0.0, "ph": 0.0})["ph"] += p["pd"]
    for s in out["sys"].values(): s["total"] = s["dev"] + s["sur"] + s["ph"]
    return out

def check(sc, label, extra=None):
    e = expected(sc, extra); agg = block(N["SU"], "System")
    for sname, s in e["sys"].items():
        got = agg[sname]
        for k in ("dev", "sur", "ph", "total"): assert near(got[H[k]], s[k]), (label, sname, k, got[H[k]], s[k])
    tot = agg[H["total_label"]]
    assert near(tot[H["total"]], sum(s["total"] for s in e["sys"].values())), (label, tot[H["total"]])
    assert near(tot[H["cond"]], e["cond"]) and near(tot[H["interim"]], e["interim"]), (label, tot[H["cond"]], e["cond"], tot[H["interim"]], e["interim"])
    assert near(tot[H["open"]], e["open"]), (label, "open inputs", tot[H["open"]], e["open"])
    rel = block(N["SU"], "Release")
    for (sname, r), pd in e["rel"].items(): assert near(rel[r][f"{sname} ({'PT' if DE else 'PD'})"], pd), (label, sname, r, rel[r], pd)
    ws, h, rs = rows(CS)   # pass-through roll-up per client row
    for r in rs:
        rid = ws.cell(r, 1).value; got = val(CS, r, h[H["total"]])
        assert near(got, e["roll"].get(rid, 0)), (label, "pass-through", rid, got, e["roll"].get(rid, 0))
    ws, h, rs = rows(N["OT"])
    other = sum(float(val(N["OT"], r, h[H["total"]]) or 0) for r in rs); client = sum(float(val(CS, r, head(cust[CS])[H["total"]]) or 0) for r in rows(CS)[2])
    assert near(client + other, sum(s["dev"] for s in e["sys"].values())), (label, "reconciliation", client, other)
    assert near(kv(N["SU"], H["diff"]), 0), (label, "difference", kv(N["SU"], H["diff"]))

sc0 = X["scenarios"][0]; check(sc0, "default")
# the overruled gap's first estimate (wave 1, superseded by the follow-up chunk) is not counted: one row, the re-estimate
ws, h, rs = rows(N["ES"]); sup = X["superseded"]; TS = "T-Shirt"
one = [r for r in rs if ws.cell(r, 1).value == sup["row"] and ws.cell(r, h["System"]).value == sup["system"] and ws.cell(r, h["Option"]).value == sup["option"]]
assert len(one) == 1 and ws.cell(one[0], h[TS]).value == sup["live"] and near(val(N["ES"], one[0], h[H["pd"]]), X["map"][sup["live"]]), ("superseded row counted", [ws.cell(r, h[TS]).value for r in one])
# the architect's routing: every package of the receiving cell carries "routed from" and counts in the receiving system
RF, BY, AS = ("Umgeleitet von", "Schätzung durch", "Schätzannahmen") if DE else ("Routed from", "Estimated by", "Estimation assumptions")
ro = X["routed"]; rr = [r for r in rs if ws.cell(r, 1).value == ro["row"] and ws.cell(r, h["System"]).value == ro["system"]]
assert rr and all(ws.cell(r, h[RF]).value == ro["from"] for r in rr), ("routed packages", [(ws.cell(r, h[RF]).value) for r in rr])
assert len(rr) == len(X["scenarios"]), ("one routed package per base option", len(rr))   # the routing applies to every scenario of the receiving system
for lab in X["scenario_labels"]:   # each scenario counts exactly one of them (the one on its base option)
    assert sum(int(val(N["ES"], r, h[f"In {lab}"]) or 0) for r in rr) == 1, (lab, "routed package not counted once in its scenario")
# the SAP BTP input cell: routed from the reporting system, the client assumption A-nn on the row and in Vollstaendigkeit, on the Annahmen sheet
la = X["landscape"]; lr = [r for r in rs if ws.cell(r, 1).value == la["row"] and ws.cell(r, h["System"]).value == la["system"]]
assert len(lr) == 1 and ws.cell(lr[0], h[RF]).value == la["from"] and val(N["ES"], lr[0], h[H["pd"]]) in (None, ""), "the SAP BTP input cell"
import re as _re
an = _re.match(r"A-\d+", str(ws.cell(lr[0], h[AS]).value or "")); assert an, ("the input cell names its client assumption", ws.cell(lr[0], h[AS]).value)
vs = cust[N["VS"]]; vrows = [[c.value for c in row] for row in vs.iter_rows(min_row=2)]
inp = [x for x in vrows if x[1] == la["row"] and x[3] == la["system"]]
assert inp and f"({an.group(0)})" in str(inp[0][5]), ("Vollstaendigkeit lists the input cell with its A-nn", inp)
ann = cust[next(n for n in cust.sheetnames if n in ("Annahmen", "Assumptions"))]
assert an.group(0) in [c.value for c in ann["A"]], (an.group(0), "not on the Annahmen sheet")
# an architect's client assumption sits on the receiving cell / the reduced package only (affects = <row>@<system>[:<option>]), never on
# the row's other systems or options (no A-nn on Magnolia's TA-03 input or on Shopware's IF-03), and the Annahmen sheet names the cell readably
BC = h["Grundlage" if DE else "Basis"]; on = {}
for r in rs:
    for a_ in _re.findall(r"A-\d+", str(ws.cell(r, BC).value or "")): on.setdefault(a_, set()).add((ws.cell(r, 1).value, ws.cell(r, h["System"]).value, ws.cell(r, h["Option"]).value))
assert on.get(an.group(0)) == {(la["row"], la["system"], None)}, ("the SAP BTP assumption only on its input cell", on)
red = [a_ for a_, ks in on.items() if any(k[0] == "IF-03" for k in ks)]
assert len(red) == 1 and on[red[0]] == {("IF-03", "E-Commerce", "SAP Commerce Cloud")}, ("the reduction's assumption only on the reduced package", on)
arow = next(row for row in ann.iter_rows(values_only=True) if row[0] == an.group(0)); rrow = next(row for row in ann.iter_rows(values_only=True) if row[0] == red[0])
assert f"{la['row']} ({la['system']})" in arow and "IF-03 (E-Commerce · SAP Commerce Cloud)" in rrow, ("Annahmen names the cell / package readably", arow, rrow)
gl = [x for x in vrows if x[0] == ("Lücke" if DE else "Gap")]
assert len(gl) == 4 and all(x[5] for x in gl), ("every gap with its decision", [(x[1], x[3], x[5]) for x in gl])
# the range: likely x factor by certainty; edit the factor of 'medium'
mid = next(r for r in rs if ws.cell(r, h["Option"]).value and ws.cell(r, h["T-Shirt"]).value == "S" and str(ws.cell(r, h[("Sicherheit der Schätzung" if DE else "Certainty of the estimate")]).value) == ("mittel" if DE else "medium"))
pd = float(val(N["ES"], mid, h[H["pd"]])); mn, mx = h[("PT min" if DE else "PD min")], h[("PT max" if DE else "PD max")]
assert near(val(N["ES"], mid, mn), pd * X["range"]["medium"]["min"]) and near(val(N["ES"], mid, mx), pd * X["range"]["medium"]["max"]), (pd, val(N["ES"], mid, mn), val(N["ES"], mid, mx))
fr = next((r, c) for r in range(1, pa.max_row + 1) for c in range(1, pa.max_column + 1) if pa.cell(r, c).value == ("mittel" if DE else "medium"))
before = block(N["SU"], "System")[H["total_label"]][H["min"]]
ev.set(N["PA"], pa.cell(fr[0], fr[1] + 1).coordinate, 0.5)
assert near(val(N["ES"], mid, mn), pd * 0.5), "the range does not follow the factor"
assert block(N["SU"], "System")[H["total_label"]][H["min"]] < before, "the development min does not follow the factor"
ev.set(N["PA"], pa.cell(fr[0], fr[1] + 1).coordinate, X["range"]["medium"]["min"])
# an external cell: paste a number, it enters every total and closes the cell
s4 = next(r for r in rs if ws.cell(r, 1).value == "TA-02" and ws.cell(r, h["System"]).value == "SAP S/4HANA")
assert val(N["ES"], s4, h[H["pd"]]) in (None, ""), "an external cell must start empty"
ev.set(N["ES"], ws.cell(s4, h[H["pd"]]).coordinate, 4)
check(sc0, "after an external input", {("TA-02", "SAP S/4HANA"): 4})
ev.set(N["ES"], ws.cell(s4, h[H["pd"]]).coordinate, None)
if MULTI:   # the selector switches every single-scenario view; Vergleich shows both scenarios
    sc1 = X["scenarios"][1]; labs = [cust[N["PA"]].cell(sel_row, 2).value]
    cmp_ = block(N["VG"], H["sel"])
    for sc in X["scenarios"]:
        lab = next(k for k in cmp_ if (k == "Shopware") == (sc == "shopware"))
        assert near(cmp_[lab][H["total"]], sum(s["total"] for s in expected(sc)["sys"].values())), (sc, cmp_[lab])
    ev.set(N["PA"], f"B{sel_row}", "Shopware"); check(sc1, "second scenario selected")
    print(f"{V} workbook ok: two scenarios, selector, comparison, roll-up, reconciliation, external input, range, superseded row, routed packages, SAP BTP input with its A-nn, gaps with decisions, hidden column")
else:
    print(f"{V} workbook ok: one scenario, no comparison, roll-up, reconciliation, external input, range, superseded row, routed packages, SAP BTP input with its A-nn, gaps with decisions, hidden column")
