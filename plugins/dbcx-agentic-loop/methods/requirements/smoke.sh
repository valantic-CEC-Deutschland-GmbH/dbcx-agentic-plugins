#!/usr/bin/env bash
# requirements method self-test: one throw-away single-run project in $TMP.
#   corpus index over a toy input/ (two workshop notes + one longlist xlsx) -> SRC-001..003 with locator anchors,
#   the full chain: inventory -> discover -> waves -> one epic analysis -> gauntlet (checkout, D1, SET) -> gate ->
#   requirements export -> both workbooks -> lint -> handover release, plus the evidence-base hook matrix.
#   lean: profile lean on the same fixture: rulings -> inventory (no critic) -> SET (one standard critic) -> batched release -> build -> gate hygiene
# Env from engine/smoke_test.sh: TOOLS, PLUGIN, TMP, LANG_
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; run() { python3 "$TOOLS/$1.py" "${@:2}"; }; mrun() { python3 "$HERE/tools/$1.py" "${@:2}"; }
export PATH="$PLUGIN/scripts:$PATH"

echo "=== requirements / fixture engagement"
G="$TMP/requirements"; mkdir -p "$G"; cd "$G"
run init run --method requirements --dir "$G" --lang "$LANG_" --client "Fixture Parts GmbH" --consultancy "Fixture Consulting" --title "Requirements fixture" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$G"
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
grep -qE "eCommerce platform|E-Commerce-Plattform" docs/PLAN.md
test -f templates/source-inventory.md && test -f templates/epic-requirements.md && test -f templates/requirements-set.md
test -f schemas/epic-requirements.schema.json

echo "--- corpus"
run corpus index | grep -q "3 sources"
run corpus list | grep -q "SRC-003"
grep -q "SRC-001#L41" corpus/text/SRC-001.md
grep -q "SRC-003#Longlist!R3" corpus/text/SRC-003.md
run corpus grep "purchase order number" | grep -q "SRC-002#"
run corpus show SRC-002 | grep -q "SRC-002#L1"
run evidence resolve "SRC-002#L1" "SRC-003#Longlist!R3" | grep -c "^OK" | grep -q 2
run evidence resolve "SRC-002#p99" | grep -q MISSING
run intake --no-questions >/dev/null; test -f docs/INTAKE.md
run status init
run knowledge sources >/dev/null
run evidence bases | grep -q corpus

echo "--- markdown -> json (every kind)"
for k in "inventory analysis/inventory/source_inventory.md" "epic analysis/scopes/checkout.md" "requirements_set analysis/consolidated/SET.md" \
         "critic analysis/gauntlet/checkout/round1-client.md" "critic analysis/gauntlet/checkout/round1-standard.md" \
         "critic analysis/gauntlet/D1/round1-client.md" "critic analysis/gauntlet/D1/round1-standard.md" \
         "critic analysis/gauntlet/SET/round1-client.md" "critic analysis/gauntlet/SET/round1-standard.md" \
         "gate analysis/gate/round1-product_owner.md"; do run md_to_json $k; done
python3 - <<'PY'
import json
inv = json.load(open("analysis/inventory/source_inventory.json"))
assert len(inv["sources"]) == 3 and len(inv["epics"]) == 5, (len(inv["sources"]), len(inv["epics"]))
assert inv["coverage"]["estimated_requirements_total"] == 17 and inv["coverage"]["sources_total"] == 3
assert [e["name"] for e in inv["epics"] if e["activation"] == "out-of-scope"] == ["marketplace"]
ep = json.load(open("analysis/scopes/checkout.json"))
assert len(ep["requirements"]) == 7 and len(ep["contradictions"]) == 1 and len(ep["open_questions"]) == 3
assert [r["req_id"] for r in ep["requirements"] if r["source_locators"] == ["inferred"]] == ["TR-CO-001"]
assert all(r["source_locators"] for r in ep["requirements"]), "a requirement row without any locator"
s = json.load(open("analysis/consolidated/SET.json"))
assert len(s["requirements"]) == 14 and len(s["crosscheck"]) == 6 and len(s["catalogue_gaps"]) == 1 and len(s["open_questions"]) == 5
assert s["system_type"] in ("eCommerce platform", "E-Commerce-Plattform"), s["system_type"]
assert sum(1 for c in s["crosscheck"] if c["relation"] == "missing-tr") == 2
print("json shape ok")
PY

echo "--- scopes and waves"
mrun discover | grep -q "5 epics"
python3 - <<'PY'
import json
sj = json.load(open("state/scopes.json")); sc = sj["scopes"]
assert set(sc) == {"checkout", "account", "erp-integration", "performance", "marketplace"}, set(sc)
assert sc["marketplace"]["skip"] is True and sc["checkout"]["light"] is False
assert sc["account"]["light"] is True and sc["erp-integration"]["depends_on"] == ["checkout", "account"]
assert sc["checkout"]["size"] == 6 and sc["checkout"]["meta"]["EPIC"] in ("Cart and checkout", "Warenkorb und Checkout")
print("scopes ok:", {k: v["group"] for k, v in sc.items()})
PY
run plan_waves | grep -q "skipped (not analysed): marketplace"
python3 - <<'PY'
import json
w = json.load(open("state/WAVES.json")); waves = w["waves"]
pos = {m["name"]: i for i, wv in enumerate(waves) for m in wv["members"]}
assert "marketplace" not in pos and pos["erp-integration"] > pos["checkout"] and pos["erp-integration"] > pos["account"], pos
assert next(m for wv in waves for m in wv["members"] if m["name"] == "account")["light_pass"] is True
print("waves ok:", [[m["name"] for m in wv["members"]] for wv in waves])
PY

echo "--- gauntlet (checkout, D1, SET)"
for s in checkout D1 SET; do
  run extract_claims $s
  run evidence check $s | grep -q "^0/"
  run score_aggregate $s 1 --dry-run | grep -q '"passed": true'
  run score_aggregate $s 1 >/dev/null
done
test -f analysis/gauntlet/checkout/coverage-round1.md
grep -q "requirements" analysis/gauntlet/checkout/coverage-round1.md
if run md_to_json critic analysis/gauntlet/checkout/round1-client.md >/dev/null 2>&1; then echo "closed-file guard FAILED"; exit 1; else echo "closed-file guard ok"; fi
run gate_aggregate 1 >/dev/null; test -f analysis/gate/round1-fixplan.md
run status verify --brief || true

echo "--- briefs"
run render brief inventory --out >/dev/null; grep -q "CORPUS STATS" analysis/briefs/inventory.md; grep -q "SRC-003" analysis/briefs/inventory.md
run render brief analyst checkout --out >/dev/null
grep -q "EVIDENCE BASES YOU MAY READ" analysis/briefs/analyst-checkout.md
grep -q "ROLE INSTRUCTIONS" analysis/briefs/analyst-checkout.md
grep -q "YOUR SOURCES" analysis/briefs/analyst-checkout.md
grep -q "SRC-002" analysis/briefs/analyst-checkout.md
grep -q "corpus grep" analysis/briefs/analyst-checkout.md
grep -q "HANDOVER" analysis/briefs/analyst-checkout.md || true
run render brief critic client checkout 1 --out >/dev/null; grep -q "^MODEL:" analysis/briefs/critic-client-checkout-r1.md
grep -q "product owner" analysis/briefs/critic-client-checkout-r1.md
run render brief critic standard SET 1 --out | grep -qE "MODEL (opus|sonnet|haiku|fable)\b"
grep -q "no reference catalogue" analysis/briefs/critic-standard-SET-r1.md
run render brief consolidate SET --out >/dev/null; grep -q "DIGEST" analysis/briefs/consolidate-set.md
run render brief postpass checkout | grep -q "POST-PASS TEXT CORRECTION"
run render brief progress | grep -q "progress-reporter"
run render brief research | grep -q "RESEARCH TOPICS"
if run render brief analyst checkout --round 2 --out >/dev/null 2>&1; then echo "addendum guard FAILED"; exit 1; else echo "addendum guard ok"; fi
echo "second round: the client critic disputed nothing new" > analysis/briefs/add.md
run render brief analyst checkout --round 2 --addendum analysis/briefs/add.md --out | grep -q "wrote"

echo "--- handover, digest, questions"
run render handover >/dev/null; test -f analysis/inventory/HANDOVER.md
grep -q "## checkout" analysis/inventory/HANDOVER.md
grep -q "TOOL-DERIVED" analysis/inventory/HANDOVER.md
run render digest SET >/dev/null; test -f analysis/consolidated/digest-SET.md
grep -q "cross-check candidates" analysis/consolidated/digest-SET.md
grep -q "citing claims" analysis/consolidated/digest-SET.md
run questions add checkout client "Does the credit limit check reject an order or only flag it?" --id Q-checkout-1 --effect "decides whether the check blocks the checkout" >/dev/null
run questions add checkout account "Does the purchasing group visibility rule apply to quotes as well?" >/dev/null
if [ "$LANG_" = de ]; then run questions edit Q-checkout-1 --why "Die beiden Workshops widersprechen sich, ob die Bonitätsprüfung die Bestellung blockiert, und keine Quelle nennt, wo der daraus entstehende Freigabestatus gespeichert wird." --note "fixture" >/dev/null; run questions assumption Q-checkout-1 --text "Die Analyse geht davon aus, dass die Bonitätsprüfung die Bestellung bis zur Freigabe durch die Finanzabteilung blockiert und der Freigabestatus wie in TR-004 abgeleitet gespeichert werden kann." --if-not "Prüft die Bonitätsprüfung nur und blockiert nicht, braucht FR-007 ein zweites, nicht blockierendes Ergebnis; lässt sich der Freigabestatus nicht wie angenommen ableiten, muss TR-004 durch eine belegte Anforderung ersetzt werden." >/dev/null
else run questions edit Q-checkout-1 --why "The two workshops disagree on whether the credit limit check blocks the order, and no source states where the resulting approval state is kept." --note "fixture" >/dev/null; run questions assumption Q-checkout-1 --text "The analysis assumes the credit limit check blocks the order until finance clears it, and that the resulting approval state can be kept as inferred in TR-004." --if-not "If the check only flags the order, FR-007 needs a second, non-blocking outcome; if the approval state cannot be inferred as assumed, TR-004 must be replaced with a stated requirement." >/dev/null; fi
run questions affects Q-checkout-1 FR-007,TR-004
run questions list --client | grep -q client
run reference add --fact "fixture standard fact" --applies "eCommerce platform" --url "https://example.invalid/req" --provenance researcher | grep -q "added PS-7-001"
run learn add --section B --title "fixture learning" --what "x" --evidence "y" --generalises "z" --proposal "p" --touches "engine" | grep -q "L-001"
run progress | grep -q "PROGRESS"

echo "--- requirements export (state/requirements.json for downstream methods)"
mrun export_requirements | grep -q "exported 14 requirements"
python3 - <<'PY'
import json
r = json.load(open("state/requirements.json"))
assert len(r["requirements"]) == 14, len(r["requirements"])
assert {x["group"] for x in r["requirements"]} == {"functional", "technical"}, {x["group"] for x in r["requirements"]}
assert sum(1 for x in r["requirements"] if x["type"] == "nfr") == 1
assert r["phase_values_in_scope"] == ["MVP"], r["phase_values_in_scope"]
one = next(x for x in r["requirements"] if x["id"] == "FR-009")
assert one["sources"] and one["epic"] == "checkout" and one["acceptance_criteria"], one
assert next(x for x in r["requirements"] if x["id"] == "TR-004")["sources"] == ["inferred"]
assert "TR-003" in next(x for x in r["requirements"] if x["id"] == "FR-007")["references"]
for k in ("id", "group", "epic", "title", "description", "acceptance_criteria", "exclusions", "references", "phase", "sources", "priority"):
    assert k in one, k
print("state/requirements.json shape ok - importable by tech-scoring / tech-fit-estimation")
PY

echo "--- workbooks"
run build_excel --all
run build_excel D2 --internal >/dev/null; test -f work/internal/Requirements_Review_Notes.xlsx
run status scope checkout '{"status": "final"}' >/dev/null
run build_excel --all --interim >/dev/null; ls work/interim/*/Requirements.xlsx >/dev/null
test ! -d deliverables/interim && test ! -d deliverables/internal
run lint_deliverable
run lint_deliverable --standalone --all --round 1
run kb add --text "Every scope of this fixture reads the same nightly export." --topic fixture-export --topic-summary "the shared nightly export" --applies-to '*' --type decision | grep -q "KB-001"
run render brief gate product_owner 1 --out | grep -q "gate-product_owner"
if grep -q "## KNOWLEDGE BASE" analysis/briefs/gate-product_owner-r1.md; then echo "knowledge base block in a gate brief"; exit 1; fi   # 0.10: gate roles get no KNOWLEDGE BASE block
run render brief analyst checkout --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/analyst-checkout.md
run render brief critic client checkout 1 --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/critic-client-checkout-r1.md
# sheet names are translated per language (the German engine wording references the claims sheet as `Aussagen`),
# so the assertions read them from the resolved deliverables spec instead of hard-coding English names
eval "$(python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ["TOOLS"])
from common import deliverables_spec
S = deliverables_spec()["deliverables"]
n = lambda d, i: S[d]["sheets"][i]["name"]
for k, v in (("SH_SOURCES", n("D1", 2)), ("SH_EPICS", n("D1", 3)), ("SH_OV1", n("D1", 4)), ("SH_CLAIMS1", n("D1", 5)),
             ("SH_REQ", n("D2", 2)), ("SH_TRACE", n("D2", 3)), ("SH_CROSS", n("D2", 4)), ("SH_GAPS", n("D2", 5)),
             ("SH_CONTRA", n("D2", 6)), ("SH_OV2", n("D2", 7)), ("SH_CLAIMS2", n("D2", 8)), ("SH_OQ", deliverables_spec()["common"]["open_questions"]["name"])):
    print(f'export {k}="{v}"')
PY
)"
test -n "$SH_CLAIMS2" && echo "sheet names for $LANG_: $SH_SOURCES $SH_EPICS $SH_REQ $SH_TRACE $SH_CROSS $SH_GAPS $SH_CONTRA $SH_OV2 $SH_CLAIMS2"
python3 - <<'PY'
import openpyxl, glob, re, os
E = os.environ
for f in sorted(glob.glob("deliverables/intern/*.xlsx")):   # full edition: + claims sheet + Open_Questions
    wb = openpyxl.load_workbook(f); names = set(wb.sheetnames); bad = []
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    for ref in re.findall(r"([A-Za-z_][\w]*)!\$", c.value):
                        if ref not in names: bad.append((ws.title, c.coordinate, ref))
    charts = sum(len(ws._charts) for ws in wb); claims = E["SH_CLAIMS1"] if "Source_Inventory" in f else E["SH_CLAIMS2"]
    assert E["SH_OQ"] in names, f"{f}: no {E['SH_OQ']} sheet"
    assert claims in names and charts >= 1, (f, names, charts)
    heads = [c.value for c in wb[claims][1]]
    assert not any(h and ("Round" in h or "Note" in h) for h in heads), heads
    print(f, "sheets:", len(wb.sheetnames), "| dangling refs:", len(bad), "| charts:", charts); assert not bad, bad[:5]

wb = openpyxl.load_workbook("deliverables/intern/Source_Inventory_and_Epics.xlsx")
assert {E["SH_SOURCES"], E["SH_EPICS"], E["SH_OV1"], E["SH_CLAIMS1"], "README", "Management_Summary"} <= set(wb.sheetnames), wb.sheetnames
ws = wb[E["SH_SOURCES"]]; ids = [ws.cell(r, 1).value for r in range(2, 6)]
assert ids[:3] == ["SRC-001", "SRC-002", "SRC-003"], ids
assert sum(1 for r in range(2, 8) if ws.cell(r, 1).value) == 3, "one row per indexed source"
assert all(isinstance(ws.cell(r, 9).value, int) for r in range(2, 5)), "anchor counts missing"   # column 9 = Citable anchors (reordered: decision/support columns moved first)
we = wb[E["SH_EPICS"]]; assert sum(1 for r in range(2, 10) if we.cell(r, 1).value) == 5

wb2 = openpyxl.load_workbook("deliverables/intern/Requirements.xlsx")
assert {E["SH_REQ"], E["SH_TRACE"], E["SH_CROSS"], E["SH_GAPS"], E["SH_CONTRA"], E["SH_OV2"], E["SH_CLAIMS2"], E["SH_OQ"]} <= set(wb2.sheetnames), wb2.sheetnames
wr = wb2[E["SH_REQ"]]; n = sum(1 for r in range(2, 40) if wr.cell(r, 1).value)
assert n == 14, n
traced = [c.coordinate for c in wr[2] if isinstance(c.value, str) and c.value.startswith("=IF(EXACT(")]
assert len(traced) == 1, traced   # the per-row traceability formula (the column header is language-dependent, the formula is not)
wt = wb2[E["SH_TRACE"]]; loc = sum(1 for r in range(2, 60) if wt.cell(r, 1).value)
assert loc == 21, loc          # 14 requirements, 21 locator rows (7 rows carry two locators)
assert any("inferred" in str(wt.cell(r, 8).value).lower() or "abgeleitet" in str(wt.cell(r, 8).value).lower() for r in range(2, 2 + loc)), "no inferred locator row"
ov = wb2[E["SH_OV2"]]
share = [c.value for row in ov.iter_rows() for c in row if isinstance(c.value, str) and "COUNTIF" in c.value and "/COUNTA" in c.value]
assert share, "no traceability-share formula on the overview sheet"
ms = wb2["Management_Summary"]
assert any(isinstance(c.value, str) and c.value.startswith("=IFERROR(TEXT(COUNTIF(") for row in ms.iter_rows() for c in row), "no traceability KPI"
oq = wb2[E["SH_OQ"]]; assert sum(1 for r in range(2, 20) if oq.cell(r, 1).value) >= 1
print("workbook assertions ok")
PY

echo "--- optional estimation-sheet export (off by default, then enabled)"
mrun export_estimation_sheet | grep -q "estimation-sheet export is off"
python3 - <<'PY'
import json
r = json.load(open("run.json")); r.setdefault("deliverables", {})["estimation_sheet_export"] = {"enabled": True}
json.dump(r, open("run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
mrun export_estimation_sheet | grep -q "Requirements_EstimationSheet.xlsx"
python3 - <<'PY'
import openpyxl
wb = openpyxl.load_workbook("deliverables/Requirements_EstimationSheet.xlsx")
assert wb.sheetnames == ["Functional Requirements", "Technical Requirements"], wb.sheetnames
ws = wb["Functional Requirements"]
assert [ws.cell(2, c).value for c in range(1, 6)] == ["#", "ID", "Epic", "Title", "Description"]
assert ws.cell(2, 18).value == "Open Question" and ws.cell(3, 1).value == 1
assert sum(1 for r in range(3, 30) if ws.cell(r, 2).value) == 9
wt = wb["Technical Requirements"]
assert wt.cell(2, 15).value == "Open Question"
assert sum(1 for r in range(3, 30) if wt.cell(r, 2).value) == 5
assert any("[non-functional]" in str(wt.cell(r, 4).value) or "[nichtfunktional]" in str(wt.cell(r, 4).value) for r in range(3, 30))
for ws_ in wb:
    for row in ws_.iter_rows():
        for c in row: assert not (isinstance(c.value, str) and c.value.startswith("=")), (ws_.title, c.coordinate)
print("estimation-sheet export ok (formula-free)")
PY
run lint_deliverable deliverables/Requirements_EstimationSheet.xlsx
run lint_deliverable --standalone --all   # the export is a customer file too

echo "--- artefact release"
run handover types | grep -q "requirements-set"
run handover export requirements-set | grep -q released
run handover list | grep -q requirements-set
python3 - <<'PY'
import json, glob
f = sorted(glob.glob("handover/requirements-set-*.json"))[-1]
env = json.load(open(f))
assert env["artefact_type"] == "requirements-set" and env["gauntlet_passed"] is True
assert len(env["data"]["requirements"]) == 14 and env["passed_claim_ids"], env["passed_claim_ids"]
print("released artefact ok:", f, len(env["passed_claim_ids"]), "passed claims")
PY

echo "--- evidence-base hook matrix"
python3 - <<'PY'
import json, subprocess, sys, os
H = os.path.join(os.environ["PLUGIN"], "hooks", "dbcx_hook.py"); cwd = os.getcwd()
def hook(payload): return subprocess.run([sys.executable, H, "PreToolUse"], input=json.dumps(dict(payload, cwd=cwd)), capture_output=True, text=True).stdout
src = os.path.join(cwd, "corpus", "text", "SRC-001.md")
assert "deny" in hook({"tool_name": "Read", "tool_input": {"file_path": src}, "agent_name": "critic-standard-checkout"}), "standard critic corpus read not denied"
assert "deny" in hook({"tool_name": "Read", "tool_input": {"file_path": src}, "agent_name": "consolidate-set"}), "consolidator corpus read not denied"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": src}, "agent_name": "analyst-checkout"}), "epic analyst corpus read denied"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": src}, "agent_name": "critic-client-checkout"}), "client critic corpus read denied"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": src}}), "orchestrator corpus read denied"
assert "deny" in hook({"tool_name": "Write", "tool_input": {"file_path": os.path.join(cwd, "input", "x.md")}}), "write into input not denied"
assert "deny" in hook({"tool_name": "WebSearch", "tool_input": {"query": "Fixture Parts GmbH requirements"}}), "client name not denied"
assert "deny" in hook({"tool_name": "WebSearch", "tool_input": {"query": "what does SRC-001 say about checkout"}}), "corpus locator not denied"
assert "deny" in hook({"tool_name": "Agent", "tool_input": {"subagent_type": "dbcx-agentic-loop:analyst", "prompt": "do it", "model": "opus"}}), "spawn without brief not denied"
print("hook matrix ok")
PY

run status next || true
echo "=== requirements / lean (profile lean: rulings -> inventory -> SET -> build -> gate hygiene)"
L="$TMP/requirements-lean"; mkdir -p "$L"; cd "$L"
if run init run --method tech-fit-estimation --profile lean --dir "$TMP/requirements-lean-refused" >/dev/null 2>&1; then echo "profile guard FAILED (tech-fit-estimation accepted lean)"; exit 1; fi
run init run --method requirements --profile lean --dir "$L" --lang "$LANG_" --client "Fixture Parts GmbH" --consultancy "Fixture Consulting" --title "Requirements fixture (lean)" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$L" >/dev/null
rm -f analysis/scopes/*.md; rm -rf analysis/gauntlet/checkout   # a lean run has no epic analyses
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
run corpus index >/dev/null
run status init >/dev/null
python3 -c "import json; st=json.load(open('state/STATUS.json')); assert st['phases']['waves']['enabled'] is False, st['phases']['waves']"
run status next | grep -q "evidence_bases"
run status set phases.preflight.status '"done"' >/dev/null
run status next | grep -q "NEXT: rulings before inventory (human_input.rulings required)"
run rulings draft >/dev/null
run rulings add "Is marketplace selling out of scope for the first release?" --topic scope-boundaries --option "A|yes|no marketplace requirement" --option "B|no|marketplace epic analysed" --recommend A >/dev/null
run rulings answer R-01 --option A >/dev/null; run rulings done >/dev/null
run status next | grep -q "NEXT: inventory / scope D1"
run status set phases.inventory.status '"analysing"' >/dev/null
python3 - <<'PY2'
import os, sys, re
sys.path.insert(0, os.environ["TOOLS"]); import common, evidence
cfg = common.project()
def text(loc): got, _ = evidence.locator_texts(loc, cfg, offline=True); return " ".join(t for _, t in got)
for p in ("analysis/inventory/source_inventory.md", "analysis/consolidated/SET.md"):
    s = re.sub(r"analysis/scopes/[\w-]+\.md|\bC-(?!SET-|D1-)[\w-]+-\d{3}\b", "SRC-002#L1", open(p, encoding="utf-8").read()); head = "| id | type | statement | evidence | target | supersedes | history |"
    s = s.replace(head + "\n|---|---|---|---|---|---|---|", "| id | type | statement | evidence | quote | target | supersedes | history |\n|---|---|---|---|---|---|---|---|")
    for row in [l for l in s.splitlines() if re.match(r"\| C-", l)]:
        c = row.split(" | "); ev = list(dict.fromkeys(e.strip() for e in c[3].split(";")))
        src = next((e for e in ev if e.startswith("SRC-") and "!" not in e), None) or "SRC-001#L1"
        if src not in ev: ev.append(src)
        q = next(l.strip() for l in text(src).splitlines() if len(re.sub(r"[^0-9A-Za-z]", "", l)) >= 30 and not l.lstrip().startswith(("#", "|", "<")) and "|" not in l)
        c[3] = "; ".join(ev); c.insert(4, q); s = s.replace(row, " | ".join(c))
    open(p, "w", encoding="utf-8").write(s)
print("lean fixture: quotes added")
PY2
run md_to_json inventory analysis/inventory/source_inventory.md >/dev/null
run extract_claims D1 --round 1 | grep -q "quote check: .* 0 not_found"
python3 -c "import json; q=json.load(open('analysis/gauntlet/D1/quotes.json')); assert q['mode']=='required' and q['counts']['no_quote']==0 and q['counts']['not_found']==0, q['counts']"
if run render brief critic standard D1 1 --out >/dev/null 2>&1; then echo "no-critic guard FAILED"; exit 1; fi
run status next | grep -q "no critic scores this scope"
run score_aggregate D1 1 | grep -q '"passed": true'
run render handover >/dev/null
run status next | grep -q "NEXT: consolidation_set / scope SET"
if run render brief analyst checkout --out >/dev/null 2>&1; then echo "split guard FAILED (an epic analyst brief in a lean run)"; exit 1; fi
run render digest SET >/dev/null; grep -q "split none, no scope analyses" analysis/consolidated/digest-SET.md; grep -q "Epics to write" analysis/consolidated/digest-SET.md
run render brief consolidate SET --out >/dev/null; B=analysis/briefs/consolidate-set.md
grep -q "profile lean" $B; grep -q "EPIC checkout - ITS SOURCES" $B; grep -q "CORPUS GREP" $B
grep "EVIDENCE BASES YOU MAY READ" $B | grep -q "corpus \[corpus\]"
if grep -qE "you have no corpus access|no access to the client.s (documents|material)|no access to the client-side" $B; then echo "lean consolidator brief still denies the corpus"; exit 1; fi
python3 - <<'PY2'
import json, subprocess, sys, os
H = os.path.join(os.environ["PLUGIN"], "hooks", "dbcx_hook.py"); cwd = os.getcwd(); src = os.path.join(cwd, "corpus", "text", "SRC-001.md")
def hook(agent): return subprocess.run([sys.executable, H, "PreToolUse"], input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": src}, "agent_name": agent, "cwd": cwd}), capture_output=True, text=True).stdout
assert "deny" not in hook("consolidate-set"), "lean consolidator corpus read denied (H5)"
assert "deny" in hook("critic-standard-SET"), "standard critic corpus read not denied"
print("lean hook matrix ok")
PY2
run md_to_json requirements_set analysis/consolidated/SET.md >/dev/null
run extract_claims SET --round 1 >/dev/null
if run render brief critic client SET 1 --out >/dev/null 2>&1; then echo "client critic guard FAILED"; exit 1; fi
run render brief critic standard SET 1 --out >/dev/null; grep -q "ROUND: 1 of max 1 (+1 rework round for defects only)" analysis/briefs/critic-standard-SET-r1.md
python3 - <<'PY2'
import json
reg = json.load(open("analysis/gauntlet/SET/claims.json"))
rows = "\n".join(f"| {c['id']} | 9 | {'confirmed' if c['type'] == 'fact' else 'insightful'} | | | |" for c in reg["claims"])
open("analysis/gauntlet/SET/round1-standard.md", "w", encoding="utf-8").write(f"# Gauntlet score: SET / standard / round 1\n\n- **scope:** SET\n- **critic:** standard\n- **round:** 1\n\n## Scores\n\n| claim_id | score | verdict | issue | counter_evidence | fix_hint |\n|---|---|---|---|---|---|\n{rows}\n\n## Missing claims\n\n-\n\n## Estate observations\n\n-\n\n## Summary\n\nThe set matches requirements best practice.\n")
PY2
run md_to_json critic analysis/gauntlet/SET/round1-standard.md >/dev/null
run score_aggregate SET 1 | grep -q '"passed": true' || { echo "lean SET did not pass"; exit 1; }
python3 -c "import json; r=json.load(open('analysis/gauntlet/SET/round1-result.json')); assert list(r['critics'])==['standard'] and r['pass_rule_id']=='defects+quotes', r['critics']"
run questions add SET client "Does the credit limit check reject an order or only flag it?" --effect "decides whether the check blocks the checkout" | grep -q "batched: 1 unreleased"
if [ "$LANG_" = de ]; then run questions edit Q-SET-001 --why "Die beiden Workshops widersprechen sich, ob die Bonitätsprüfung die Bestellung blockiert, und keine Quelle nennt, wo der daraus entstehende Freigabestatus gespeichert wird." --note "fixture" >/dev/null; run questions assumption Q-SET-001 --text "Die Analyse geht davon aus, dass die Bonitätsprüfung die Bestellung bis zur Freigabe durch die Finanzabteilung blockiert und der Freigabestatus wie in TR-004 abgeleitet gespeichert werden kann." --if-not "Prüft die Bonitätsprüfung nur und blockiert nicht, braucht FR-007 ein zweites, nicht blockierendes Ergebnis; lässt sich der Freigabestatus nicht wie angenommen ableiten, muss TR-004 durch eine belegte Anforderung ersetzt werden." >/dev/null
else run questions edit Q-SET-001 --why "The two workshops disagree on whether the credit limit check blocks the order, and no source states where the resulting approval state is kept." --note "fixture" >/dev/null; run questions assumption Q-SET-001 --text "The analysis assumes the credit limit check blocks the order until finance clears it, and that the resulting approval state can be kept as inferred in TR-004." --if-not "If the check only flags the order, FR-007 needs a second, non-blocking outcome; if the approval state cannot be inferred as assumed, TR-004 must be replaced with a stated requirement." >/dev/null; fi
run status set phases.consolidation_set.status '"final"' >/dev/null
run status next | grep -q "RELEASE QUESTION BATCH (build)"
if run build_excel --all >/dev/null 2>&1; then echo "batched-release guard FAILED"; exit 1; fi
run questions release --all | grep -q "0 still unreleased"
run build_excel --all >/dev/null
run lint_deliverable --standalone --all --round 1
python3 - <<'PY2'
import glob, os, openpyxl
books = sorted(os.path.basename(f) for f in glob.glob("deliverables/*.xlsx"))
assert books == ["Requirements.xlsx", "Source_Inventory_and_Epics.xlsx"], books
assert not glob.glob("analysis/briefs/analyst-*") and not glob.glob("analysis/briefs/critic-client-*") and not glob.glob("analysis/briefs/critic-standard-D1*"), sorted(os.listdir("analysis/briefs"))
assert not os.path.exists("state/WAVES.json") and not os.path.exists("state/scopes.json") and not glob.glob("analysis/scopes/*.md")
assert all(os.path.exists(f"analysis/gauntlet/{s}/quotes.json") for s in ("D1", "SET"))
print("lean assertions ok:", books)
PY2

echo "REQUIREMENTS SMOKE OK"
