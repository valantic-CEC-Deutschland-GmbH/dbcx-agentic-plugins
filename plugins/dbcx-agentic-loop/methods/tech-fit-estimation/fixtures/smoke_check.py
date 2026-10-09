#!/usr/bin/env python3
"""Workbook assertions of the tech-fit-estimation smoke for one fixture variant (run in the run folder; env VARIANT, LANGV).

  * the sheets of the plain workbook (customer + full edition), no unresolved placeholder, no reference to a missing sheet
  * the totals per option, recomputed from the formulas (fixtures/xl_eval.py), equal the totals of the fixture's own sizes and phases
    (fixture_expected.json) - on Summen, Vergleich and the Management Summary KPIs - before AND after editing the Parameter sheet:
    one size of the T-shirt mapping and the QA surcharge of the first option
  * starts: option band headers, Grundlage per option (Code from resolved handover rows and the lookup, the open client assumption,
    the client's answer, Herstellerstandard from vendor standard code), positions of a requirement above XXL
  * packs: one standard critic per technology pack in the claims register and on the Aussagen sheet
  * scenarios: the scenario totals (Szenarien, Summen, Vergleich, Management Summary KPIs) recomputed and compared with the
    fixture's sizes, savings, integration platform sizes and fixed phases per scenario - after each of four edits: a size of the mapping,
    a surcharge of the first option, a fixed phase, the day rate; Klasse / Integration Suite / saving columns, the greenfield block of a
    refactoring row, Grundlage with readable references, no Fundstellen in the customer edition, no code locator in any cell of either edition
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openpyxl
from xl_eval import Evaluator

V = os.environ.get("VARIANT", "none"); DE = os.environ.get("LANGV", "en") == "de"
N = {"MS": "Management_Summary", "PA": "Parameter" if DE else "Parameters", "RQ": "Anforderungen" if DE else "Requirements", "ES": "Schaetzung" if DE else "Estimation",
     "POS": "Schaetzpositionen" if DE else "Estimation_Positions", "ZP": "Zuschlaege_und_Phasen" if DE else "Surcharges_and_Phases", "SU": "Summen" if DE else "Totals",
     "VG": "Vergleich" if DE else "Comparison", "AB": "Abgrenzungen" if DE else "Exclusions", "RI": "Risiken" if DE else "Risks", "AN": "Annahmen" if DE else "Assumptions",
     "QU": "Quellen" if DE else "Sources", "CL": "Aussagen" if DE else "Claims", "SC": "Szenarien" if DE else "Scenarios"}
X = json.load(open("fixture_expected.json")); F = "Fit_Estimation_Generic.xlsx"
cust = openpyxl.load_workbook(f"deliverables/{F}"); full = openpyxl.load_workbook(f"deliverables/intern/{F}")
for k in ("MS", "PA", "RQ", "ES", "POS", "ZP", "SU", "VG", "AB", "RI", "AN", "QU"): assert N[k] in cust.sheetnames, (N[k], cust.sheetnames)
assert N["CL"] in full.sheetnames and N["CL"] not in cust.sheetnames, (full.sheetnames, cust.sheetnames)
names = set(full.sheetnames); bad, unresolved = [], []
for ws in full:
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str):
                if c.value.startswith("="): bad += [(ws.title, c.coordinate, r) for q, r0 in re.findall(r"(?:'([^']+)'|([A-Za-z_][\w]*))!\$", c.value) for r in [q or r0] if r not in names]
                elif re.search(r"\{[A-Za-z_][^}]*\}", c.value): unresolved.append((ws.title, c.coordinate, c.value[:80]))
assert not bad, bad[:5]; assert not unresolved, unresolved[:5]
for w in ("Risikozuschlag", "contingency", "Aktivierung", "Implementierung (", "Activate", "Implement ("):
    assert not any(w in str(c.value) for ws in cust for r in ws.iter_rows() for c in r if c.value), f"legacy effort model text '{w}' still in the workbook"
if V != "scenarios": assert N["SC"] not in full.sheetnames, f"a plain run has no {N['SC']} sheet"

# ---- totals recomputed from the formulas
def matrix(ws, title_col_values):
    """{row label: {header: cell coordinate}} of the first matrix block whose rows are the option labels"""
    rows = {}
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v in title_col_values and v not in rows:
            hr = r - 1
            while hr > 0 and ws.cell(hr, 1).value in title_col_values: hr -= 1
            rows[v] = {ws.cell(hr, c).value: ws.cell(r, c).coordinate for c in range(2, ws.max_column + 1) if ws.cell(hr, c).value}
    return rows


if V == "scenarios":   # totals per scenario, the four parameter edits, the scenario columns and the code-free rendering
    SCN = X["scenarios"]; labs = [x["label"] for x in SCN]; opts = [o["id"] for o in X["options"]]
    def sc_expected(map_, pct, rate, extra_phase=None):
        out = {}
        for x in SCN:
            f = sum(pct[x["option"]].values()) / 100; dev = sum(map_[k] for k in x["platform"]); sav = sum(map_[k] for k in x["saving"]); isd = sum(map_[k] for k in x["is"])
            ph = sum(x["phases"]) + (extra_phase[1] if extra_phase and extra_phase[0] == x["id"] else 0)
            plat = (dev - sav) * (1 + f) + ph; ist = isd * (1 + f); out[x["label"]] = {"tot": plat + ist, "cost": (plat + ist) * rate, "plat": plat, "is": ist}
        return out
    def num(h, rx): return next((v for k, v in h.items() if re.match(rx, str(k))), None)
    def sc_check(ev, exp, when):
        for sheet in (N["SC"], N["SU"], N["VG"]):
            m = matrix(full[sheet], labs); assert set(m) == set(labs), (when, sheet, list(m), labs)
            for lab in labs:
                got = {h: ev.value(sheet, c) for h, c in m[lab].items()}
                tot = num(got, r"(Gesamt|Total) \("); cost = num(got, r"(Kosten|Cost) \(")
                assert abs(tot - exp[lab]["tot"]) < 1e-6 and abs(cost - exp[lab]["cost"]) < 1e-3, (when, sheet, lab, got, exp[lab])
                if sheet == N["SC"]:
                    assert abs(num(got, r"Generic target platform \(") - exp[lab]["plat"]) < 1e-6 and abs(num(got, r"Integration Suite \(") - exp[lab]["is"]) < 1e-6, (when, lab, got, exp[lab])
        ms = full[N["MS"]]; kp = {str(ms.cell(r, 2).value): ms.cell(r, 4).coordinate for r in range(1, ms.max_row + 1) if ms.cell(r, 4).value and str(ms.cell(r, 4).value).startswith("=")}
        for lab in labs:
            key = next(k for k in kp if k.startswith(lab + ":") and re.search(r"(Gesamtaufwand|total effort)", k, re.I))
            assert abs(ev.value(N["MS"], kp[key]) - exp[lab]["tot"]) < 1e-6, (when, key, ev.value(N["MS"], kp[key]), exp[lab])
    pct = {o: dict(X["surcharges"]) for o in opts}; mp = dict(X["map"]); rate = X["day_rate"]
    ev = Evaluator(full); base = sc_expected(mp, pct, rate); sc_check(ev, base, "default parameters")
    pa = full[N["PA"]]; right = {c.value: pa.cell(c.row, c.column + 1).coordinate for r in pa.iter_rows() for c in r if isinstance(c.value, str)}
    ev.set(N["PA"], right["M"], 3); mp["M"] = 3; sc_check(ev, sc_expected(mp, pct, rate), "size M = 3")
    ev.set(N["PA"], right["QA"], 25); pct[opts[0]]["QA"] = 25; sc_check(ev, sc_expected(mp, pct, rate), "QA of the first option 25 %")
    zp = full[N["ZP"]]; zh = [c.value for c in zp[1]]; ph1 = next(r for r in range(2, zp.max_row + 1) if zp.cell(r, zh.index("Szenario" if DE else "Scenario") + 1).value == SCN[0]["label"] and zp.cell(r, zh.index("Block") + 1).value == ("Feste Phase" if DE else "Fixed phase"))
    cc = zp.cell(ph1, zh.index(next(h for h in zh if re.match(r"(Aufwand|Effort) \(", str(h)))) + 1); ev.set(N["ZP"], cc.coordinate, cc.value + 2)
    sc_check(ev, sc_expected(mp, pct, rate, (SCN[0]["id"], 2)), "a fixed phase + 2")
    ev.set(N["PA"], right["Tagessatz" if DE else "Day rate"], 1500); sc_check(ev, sc_expected(mp, pct, 1500, (SCN[0]["id"], 2)), "day rate 1500")
    print(f"scenarios: totals recompute per scenario ({', '.join(f'{l} {base[l]['tot']:g}' for l in labs)}) - after a size, a surcharge, a fixed phase and the day rate")
    LOC = re.compile(r"(?:[\w@.-]+/)+[\w@.-]+:\d+(?:-\d+)?|\b[\w-]+\.(?:java|ts|js|mjs|xml|jsp|impex|properties|groovy|html|scss)(?::\d+(?:-\d+)?)?\b")
    for name, wb in (("customer", cust), ("full", full)):
        hits = [(ws.title, c.coordinate, c.value[:80]) for ws in wb for r in ws.iter_rows() for c in r if isinstance(c.value, str) and not c.value.startswith("=") and LOC.search(c.value)]
        assert not hits, (name, hits[:5])
    es_c, es_f = cust[N["ES"]], full[N["ES"]]
    def heads(ws):
        raw = [c.value for c in ws[2]]; h = list(raw)
        for m in ws.merged_cells.ranges:
            if m.min_row == 1: h[m.min_col - 1:m.max_col] = [f"{ws.cell(1, m.min_col).value}: {x}" if x else x for x in raw[m.min_col - 1:m.max_col]]
        return h
    hc, hf = heads(es_c), heads(es_f); mig, neu = [o["label"] for o in X["options"]]; g = "Grundlage" if DE else "Basis"
    fund = "Fundstellen" if DE else "Evidence"
    assert ("Klasse" if DE else "Class") in hc and f"{mig}: Integration Suite " + ("T-Shirt" if DE else "T-shirt") in hc, hc
    assert f"{mig}: " + ("Einsparung T-Shirt" if DE else "Saving T-shirt") in hc and f"{neu}: " + ("Einsparung T-Shirt" if DE else "Saving T-shirt") not in hc, hc
    assert not [h for h in hc if str(h).endswith(fund)] and f"{mig}: {fund}" in hf and f"{neu}: {fund}" in hf, (hc, hf)
    ev0 = Evaluator(openpyxl.load_workbook(f"deliverables/{F}"))
    def cell(rid, header):
        r = next(r for r in range(3, es_c.max_row + 1) if es_c.cell(r, 1).value == rid); return ev0.value(N["ES"], es_c.cell(r, hc.index(header) + 1).coordinate)
    ca = "Code-Analyse" if DE else "Code analysis"
    assert cell("FR-009", f"{mig}: {g}") == f"{ca} · FR-009", cell("FR-009", f"{mig}: {g}")
    assert cell("FR-011", f"{mig}: {g}") == f"{ca} · FR-011", cell("FR-011", f"{mig}: {g}")   # the narrow lookup: the code-analysis row it extends
    assert cell("FR-023", f"{neu}: {g}") == ("Herstellerstandard [Q5]" if DE else "Vendor standard [Q5]"), cell("FR-023", f"{neu}: {g}")
    assert cell("FR-013", f"{mig}: {g}") == ("Code-Analyse · FR-013 + Annahme (A-02)" if DE else "Code analysis · FR-013 + Assumption (A-02)") and "Fixture Retail GmbH" in cell("FR-015", f"{mig}: {g}"), (cell("FR-013", f"{mig}: {g}"), cell("FR-015", f"{mig}: {g}"))
    assert cell("RF-01", ("Klasse" if DE else "Class")) == "Refactoring" and cell("TM-01", ("Klasse" if DE else "Class")) == ("Technische Migration" if DE else "Technical migration")
    assert cell("RF-01", f"{neu}: " + ("Vorgehen" if DE else "Approach")) == ("nicht Teil dieser Option" if DE else "not part of this option") and cell("RF-01", f"{neu}: " + ("Aufwand (PT)" if DE else "Effort (PD)")) == 0
    assert cell("RF-01", f"{mig}: " + ("Einsparung T-Shirt" if DE else "Saving T-shirt")) == "S" and cell("RF-01", f"{mig}: " + ("entlastet" if DE else "relieves")) == "FR-014" and cell("RF-01", f"{mig}: " + ("Einsparung (PT)" if DE else "Saving (PD)")) == 1
    assert cell("TR-01", f"{neu}: Integration Suite " + ("T-Shirt" if DE else "T-shirt")) == "L" and cell("FR-030", f"{mig}: Integration Suite (" + ("PT)" if DE else "PD)")) == 0.5, cell("FR-030", f"{mig}: Integration Suite (" + ("PT)" if DE else "PD)"))
    qu = cust[N["QU"]]; q5 = next(r for r in qu.iter_rows(min_row=2, values_only=True) if r[0] == "[Q5]"); assert q5[4] == "@spartacus/storefront@221121.18.0", q5
    assert N["SC"] in cust.sheetnames and cust.sheetnames.index(N["SC"]) == cust.sheetnames.index(N["ZP"]) + 1, cust.sheetnames
    rq = [r for r in cust[N["RQ"]].iter_rows(min_row=2, values_only=True) if r[0]]; ids = [r[0] for r in rq]   # merged under its target, dropped gone
    assert ids[ids.index("FR-010") + 1] == "NR-001" and rq[ids.index("NR-001")][2].endswith("(" + ("in FR-010 enthalten" if DE else "included in FR-010") + ")") and "NR-002" not in ids, rq
    assert ids[ids.index("FR-016") + 1] == "NR-003" and rq[ids.index("NR-003")][2].endswith("(" + ("in FR-016 enthalten" if DE else "included in FR-016") + ")"), rq   # decided in the classification
    assert not {"NR-001", "NR-002", "NR-003"} & {es_c.cell(r, 1).value for r in range(3, es_c.max_row + 1)}
    ab = [r for r in cust[N["AB"]].iter_rows(min_row=2, values_only=True) if r[0] == "NR-002"]; assert len(ab) == 1 and "A-02" in ab[0][3], ab
    print(f"scenarios workbook ok: {len(cust.sheetnames)} customer sheets, {len(full.sheetnames)} full; no code locator in either edition")
    sys.exit(0)


def expected(map_, qa_first=None):
    out = {}
    for i, o in enumerate(X["options"]):
        dev = sum(map_[s] for s in o["sizes"]); pct = dict(X["surcharges"])
        if qa_first is not None and i == 0: pct["QA"] = qa_first
        sur = dev * sum(pct.values()) / 100; ph = sum(o["phases"]); tot = dev + sur + ph
        out[o["label"]] = {"dev": dev, "sur": sur, "ph": ph, "tot": tot, "cost": tot * X["day_rate"]}
    return out

labels = [o["label"] for o in X["options"]]
def check(ev, exp, when):
    for sheet in (N["SU"], N["VG"]):
        m = matrix(full[sheet], labels); assert set(m) == set(labels), (sheet, m.keys(), labels)
        for lab in labels:
            got = {h: ev.value(sheet, c) for h, c in m[lab].items()}
            tot = next(v for h, v in got.items() if re.match(r"(Gesamt|Total) \(", str(h)))
            cost = next(v for h, v in got.items() if re.match(r"(Kosten|Cost) \(", str(h)))
            dev = next(v for h, v in got.items() if re.match(r"(Entwicklung|Development) \(", str(h)))
            assert abs(tot - exp[lab]["tot"]) < 1e-6 and abs(cost - exp[lab]["cost"]) < 1e-3 and abs(dev - exp[lab]["dev"]) < 1e-6, (when, sheet, lab, got, exp[lab])
    ms = full[N["MS"]]; kp = {str(ms.cell(r, 2).value): ms.cell(r, 4).coordinate for r in range(1, ms.max_row + 1) if ms.cell(r, 4).value and str(ms.cell(r, 4).value).startswith("=")}
    for lab in labels:
        key = next(k for k in kp if re.search(r"(Gesamtaufwand|total effort)", k, re.I) and (len(labels) == 1 or k.startswith(lab + ":")))
        assert abs(ev.value(N["MS"], kp[key]) - exp[lab]["tot"]) < 1e-6, (when, key, ev.value(N["MS"], kp[key]), exp[lab])
ev = Evaluator(full); base = expected(X["map"]); check(ev, base, "default parameters")
ms = full[N["MS"]]   # the summary prose with live KPI values: no placeholder syntax survives the evaluation
prose = [ev.value(N["MS"], c.coordinate) for r in ms.iter_rows() for c in r if isinstance(c.value, str) and c.value.startswith('="')]
assert prose and not [p for p in prose if re.search(r"[{}]", str(p))], [p for p in prose if re.search(r"[{}]", str(p))][:2]
assert all(isinstance(p, str) for p in prose), [p for p in prose if not isinstance(p, str)][:2]   # every function of the prose evaluates
if V == "starts": assert any(f"{base[labels[0]]['cost']:,.0f}" in p for p in prose), prose   # FIXED(cost, 0) in the running text
pa = full[N["PA"]]; right = {c.value: pa.cell(c.row, c.column + 1).coordinate for r in pa.iter_rows() for c in r if isinstance(c.value, str)}   # the cell right of a key (tables beside the scalar rows)
assert pa["B1"].value and pa[right["Tagessatz" if DE else "Day rate"]].value == X["day_rate"], right
ev.set(N["PA"], right["M"], 3); ev.set(N["PA"], right["QA"], 25)   # a size of the mapping and the first option's QA surcharge
check(ev, expected(dict(X["map"], M=3), qa_first=25), "edited parameters")
print(f"{V}: totals recompute per option ({', '.join(f'{l} {base[l]['tot']:g}' for l in labels)}) - before and after the parameter edit")

es = full[N["ES"]]; hr = 2 if len(labels) > 1 else 1; raw = [c.value for c in es[hr]]; hdr = list(raw)
for m in es.merged_cells.ranges if hr == 2 else []:   # below the option bands a header reads "<band>: <header>"
    if m.min_row == 1: hdr[m.min_col - 1:m.max_col] = [f"{es.cell(1, m.min_col).value}: {h}" if h else h for h in raw[m.min_col - 1:m.max_col]]
ev0 = Evaluator(openpyxl.load_workbook(f"deliverables/intern/{F}"))
def cell(rid, header):   # the shown value (a formula cell is evaluated)
    r = next(r for r in range(hr + 1, es.max_row + 1) if es.cell(r, 1).value == rid); return ev0.value(N["ES"], es.cell(r, hdr.index(header) + 1).coordinate)
ann = [r for r in cust[N["AN"]].iter_rows(min_row=2, values_only=True) if r[0]]
assert any("FR-024" in str(r[4]) for r in ann), ann   # the reading taken for FR-024 (Assumptions taken) is a client assumption
if V == "none":
    assert hr == 1 and es.cell(1, 1).value, "a single option has no band row"
    assert ("T-Shirt" if DE else "T-shirt") in hdr and (("Grundlage" in hdr) if DE else ("Basis" in hdr)), hdr
    assert cell("FR-009", "Hinweis" if DE else "Note") == ("in Positionen aufgeteilt" if DE else "split into positions"), cell("FR-009", "Hinweis" if DE else "Note")
if V == "starts":
    mig, neu = labels; g = "Grundlage" if DE else "Basis"
    assert es.cell(1, hdr.index(f"{mig}: " + ("Vorgehen" if DE else "Approach")) + 1).value == mig and es.cell(1, hdr.index(f"{neu}: " + ("Vorgehen" if DE else "Approach")) + 1).value == neu, "band headers missing"
    assert not es.tables and es.auto_filter.ref.startswith("A2:") and raw.count("Vorgehen" if DE else "Approach") == 2 and not [h for h in raw if str(h).startswith(mig)], raw   # no option label below its band
    hidden = {c for d in es.column_dimensions.values() if d.hidden for c in range(d.min, d.max + 1)}   # collapsed outline groups
    assert es.page_setup.fitToWidth == 1 and {hdr.index(f"{o}: {h}") + 1 for o in labels for h in (("Fundstellen", "Herleitung", "Mechanismus") if DE else ("Evidence", "Derivation", "Mechanism"))} <= hidden, hidden
    ms_c = cust[N["MS"]]; assert not any(("nicht bewertet" if DE else "not assessed") in str(c.value) for r in ms_c.iter_rows() for c in r), "a check KPI in the customer edition"
    assert any(("nicht bewertet" if DE else "not assessed") in str(c.value) for r in full[N["MS"]].iter_rows() for c in r)
    assert any("FIXED(" in str(c.value) for r in ms_c.iter_rows() for c in r) and not any("TEXT(" in str(c.value) for r in ms_c.iter_rows() for c in r)
    vg = full[N["VG"]]; bars = next(ch for ch in vg._charts); assert [str(p.graphicalProperties.solidFill.srgbClr) for p in bars.series[0].dPt] == ["3C4BC8", "C0AA81"], "bars not in the band colours"
    assert bars.series[0].dLbls.numFmt == "#,##0.0"
    assert cell("FR-009", f"{mig}: {g}") == "Code", cell("FR-009", f"{mig}: {g}")   # HO-requirements-coverage#FR-009 -> the artefact's repository locators
    assert "ShopDocumentService.java" in cell("FR-011", f"{mig}: " + ("Fundstellen" if DE else "Evidence")) and "Code" in cell("FR-011", f"{mig}: {g}")   # the narrow lookup
    assert cell("FR-013", f"{mig}: {g}") == "Code + Annahme (A-02)" if DE else cell("FR-013", f"{mig}: {g}") == "Code + Assumption (A-02)", cell("FR-013", f"{mig}: {g}")
    assert "Fixture Retail GmbH" in cell("FR-015", f"{mig}: {g}"), cell("FR-015", f"{mig}: {g}")   # A-01 answered by the client: a fact
    assert "Annahme" not in str(cell("FR-013", f"{neu}: {g}")), cell("FR-013", f"{neu}: {g}")      # the assumption concerns the migration only
    assert cell("FR-023", f"{neu}: {g}") == ("Herstellerstandard" if DE else "Vendor standard"), cell("FR-023", f"{neu}: {g}")
    pos = [r for r in full[N["POS"]].iter_rows(min_row=2, values_only=True) if r[0]]
    assert [(r[0], r[1], r[2]) for r in pos if r[0] == "FR-030"] == [("FR-030", "1", mig), ("FR-030", "2", mig)], pos
    zp = [r for r in full[N["ZP"]].iter_rows(min_row=2, values_only=True) if r[0]]
    assert any(r[0] == mig and ("Technische Migrationsaufgabe" if DE else "Technical migration task") == r[1] for r in zp), zp
if V == "packs":
    reg = json.load(open("analysis/gauntlet/epic-01/claims.json"))
    crit = sorted({c for x in reg["claims"] for c in x.get("critics", [])}); assert crit == ["client", "standard-sap-commerce", "standard-spryker"], crit
    assert os.path.exists("analysis/gauntlet/epic-01/critic-pack-standard-spryker.md")
    h = [c.value for c in full[N["CL"]][1]]; assert any("(spryker)" in str(x) for x in h), h
print(f"{V} workbook ok: {len(cust.sheetnames)} customer sheets, {len(full.sheetnames)} full, charts {sum(len(ws._charts) for ws in full)}")
