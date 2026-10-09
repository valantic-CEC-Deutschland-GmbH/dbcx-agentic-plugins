#!/usr/bin/env bash
# ea-landscape method self-test: two throw-away single-run projects in $TMP.
#   main:   full chain - corpus index, intake, inventory, discover/waves, one system analysis, both consolidations,
#           gauntlet for the system scope and for D1/FLOWS/TARGET, gate, all four workbooks, both diagrams, handover
#   de:     the same fixture with German deliverables (exercises deliverables.de.json + labels.de.json)
#   conflicts: the conflict register on the fixture plus a second system analysis: detect -> hold -> route -> resolve / undecidable
#   lean:   profile lean on the same fixture: rulings -> inventory (no critic) -> FLOWS/TARGET (one standard critic) -> batched release -> build -> gate hygiene
# Env from engine/smoke_test.sh: TOOLS, PLUGIN, TMP, LANG_
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; run() { python3 "$TOOLS/$1.py" "${@:2}"; }; mrun() { python3 "$HERE/tools/$1.py" "${@:2}"; }
export PATH="$PLUGIN/scripts:$PATH"

echo "=== ea-landscape / main ($LANG_)"
G="$TMP/ea-landscape"; mkdir -p "$G"; cd "$G"
run init run --method ea-landscape --dir "$G" --lang "$LANG_" --client "Fixture Industries AG" --consultancy "Fixture Consulting" --title "Enterprise architecture fixture" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$G" >/dev/null
run render instructions --force >/dev/null; run render plan --force >/dev/null; run render reference --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
test -f templates/landscape-inventory.md && test -f templates/system-analysis.md && test -f templates/consolidated-FLOWS.md && test -f templates/consolidated-TARGET.md
grep -q "protocol_style = api" templates/system-analysis.md

# ---------- corpus: the client's documents become greppable text with stable locators
run corpus index
run corpus list | grep -q SRC-003
run corpus grep "Akeneo" | grep -q "SRC-"
test -f corpus/unextractable.md
run intake --no-questions >/dev/null; test -f docs/INTAKE.md
run status init
run knowledge sources >/dev/null
run evidence bases | grep -q "^corpus"
run evidence resolve "SRC-001#L41" | grep -q "^OK "
run evidence resolve "SRC-003#Systems!R2" | grep -q "^OK "
run evidence resolve "visual, unverified" | grep -q "^OK "
run evidence resolve "SRC-001#p999" | grep -q "^MISSING"

# ---------- every kind converts
for k in "inventory analysis/inventory/landscape_inventory.md" "system analysis/scopes/hybris-shop.md" \
         "data_flows analysis/consolidated/FLOWS.md" "target_architecture analysis/consolidated/TARGET.md" \
         "critic analysis/gauntlet/hybris-shop/round1-client.md" "critic analysis/gauntlet/hybris-shop/round1-standard.md" \
         "gate analysis/gate/round1-cto.md"; do run md_to_json $k; done
python3 - <<'PY'
import json
inv = json.load(open("analysis/inventory/landscape_inventory.json"))
assert len(inv["systems"]) == 5, inv["systems"]
assert len(inv["data_objects"]) == 5 and len(inv["strategic_vision"]) == 5, inv
cust = next(o for o in inv["data_objects"] if o["name"] == "customer")
assert cust["claimed_master_systems"] == ["sap-erp", "salesforce-crm"], cust
s = json.load(open("analysis/scopes/hybris-shop.json"))
assert len(s["interfaces"]) == 5 and len(s["data_ownership"]) == 5, s
assert s["profile"]["vendor_product"] == "SAP Commerce Cloud" and s["profile"]["lifecycle"] == "active", s["profile"]
assert [i for i in s["interfaces"] if i["source_locators"] == ["visual, unverified"]], "the visual-only interface got lost"
f = json.load(open("analysis/consolidated/FLOWS.json"))
assert len(f["flows"]) == 5 and len(f["ssot_matrix"]) == 5, f
assert [x for x in f["ssot_matrix"] if x["verdict"] == "conflict"], "the mastership conflict got lost"
t = json.load(open("analysis/consolidated/TARGET.json"))
assert len(t["options"]) == 5 and len(t["roadmap"]) == 2 and len(t["principles"]) == 3, t
assert {o["recommendation"] for o in t["options"]} == {"preferred", "alternative", "rejected"}, t["options"]
print("kind conversion assertions ok")
PY

# ---------- scopes and waves come from the inventory's relevance / depends_on columns
mrun discover | grep -q "5 scopes"
python3 - <<'PY'
import json
sc = json.load(open("state/scopes.json"))["scopes"]
assert sc["hybris-shop"]["depends_on"] == ["sap-erp", "akeneo-pim"], sc["hybris-shop"]
assert sc["hybris-shop"]["group"] == "commerce" and sc["hybris-shop"]["size"] == 4, sc["hybris-shop"]
assert sc["salesforce-crm"]["light"] is True and not sc["salesforce-crm"]["skip"], sc["salesforce-crm"]
assert sc["legacy-portal"]["skip"] is True, sc["legacy-portal"]
assert sc["sap-erp"]["light"] is False, sc["sap-erp"]
print("discover assertions ok")
PY
run plan_waves | grep -q "wave 1"
python3 -c "
import json; w=json.load(open('state/WAVES.json'))
assert w['skipped']==['legacy-portal'], w['skipped']
lvl={m['name']:m['level'] for wv in w['waves'] for m in wv['members']}
assert lvl['hybris-shop']>lvl['sap-erp'] and lvl['salesforce-crm']>lvl['hybris-shop'], lvl
assert [m for wv in w['waves'] for m in wv['members'] if m['name']=='salesforce-crm'][0]['light_pass'], 'peripheral system not on light pass'
print('wave assertions ok')"

# ---------- the handover: the inventory's passed facts routed per system
run render handover >/dev/null; test -f analysis/inventory/HANDOVER.md; grep -q "hybris-shop" analysis/inventory/HANDOVER.md
grep -q "C-D1-004" analysis/inventory/HANDOVER.md

# ---------- briefs for every role
run render context analyst hybris-shop --round 1 >/dev/null
run render brief analyst hybris-shop --out >/dev/null
test -f analysis/briefs/analyst-hybris-shop.md
for pat in "EVIDENCE BASES YOU MAY READ" "ROLE INSTRUCTIONS" "SRC-001" "MASTERSHIP CONFLICT" "LOCATOR GRAMMAR" "HANDOVER" "corpus/text/" "C-D1-004"; do
  grep -q "$pat" analysis/briefs/analyst-hybris-shop.md || { echo "analyst brief lacks: $pat"; exit 1; }
done
grep -q "standard-docs" analysis/briefs/analyst-hybris-shop.md   # the analyst has NO web access - it must be listed under NO ACCESS
run render brief inventory --out >/dev/null; grep -q "relevance" analysis/briefs/inventory.md; grep -q "THE CORPUS" analysis/briefs/inventory.md
run render brief research | grep -q "RESEARCH TOPICS"
if run render brief critic client hybris-shop 1 --out >/dev/null 2>&1; then echo "claims-snapshot guard FAILED"; exit 1; else echo "claims-snapshot guard ok"; fi
run render brief critic client hybris-shop 1 --out --force >/dev/null; grep -q "^MODEL:" analysis/briefs/critic-client-hybris-shop-r1.md
grep -q "LOCATOR CHECK" analysis/briefs/critic-client-hybris-shop-r1.md
run render brief critic standard FLOWS 1 --out --force | grep -qE "MODEL (opus|sonnet|haiku|fable)\b"
grep -q "reference architect" analysis/briefs/critic-standard-FLOWS-r1.md
run render digest FLOWS >/dev/null; grep -q "citing claims" analysis/consolidated/digest-FLOWS.md
grep -q "described from both sides" analysis/consolidated/digest-FLOWS.md
run render digest TARGET >/dev/null; grep -q "Pain points and constraints" analysis/consolidated/digest-TARGET.md
run render brief consolidate FLOWS --out >/dev/null; grep -q "MASTERSHIP CLAIMS" analysis/briefs/consolidate-flows.md
run render brief consolidate TARGET --out >/dev/null
for pat in "FLOWS.json" "STRATEGIC STATEMENTS" "AS-IS PICTURE"; do
  grep -q "$pat" analysis/briefs/consolidate-target.md || { echo "TARGET consolidator brief lacks: $pat"; exit 1; }
done
run render brief progress | grep -q "progress-reporter"
if run render brief analyst hybris-shop --round 2 --out >/dev/null 2>&1; then echo "addendum guard FAILED"; exit 1; else echo "addendum guard ok"; fi

# ---------- gauntlet: the system scope with the fixture's reviewer files
run extract_claims hybris-shop
run evidence check hybris-shop | grep -q "0/"
run score_aggregate hybris-shop 1 --dry-run | grep -q '"passed": true'
run score_aggregate hybris-shop 1 >/dev/null
if run md_to_json critic analysis/gauntlet/hybris-shop/round1-client.md >/dev/null 2>&1; then echo "closed-file guard FAILED"; exit 1; else echo "closed-file guard ok"; fi
run render brief postpass hybris-shop | grep -q "POST-PASS TEXT CORRECTION"

# ---------- gauntlet: the consolidated scopes (reviewer files generated from their own claim registers)
for s in D1 FLOWS TARGET; do run extract_claims $s >/dev/null; run evidence check $s; done
python3 - <<'PY'
import json, os
TPL = """# Gauntlet score: {s} / {c} / round 1

- **scope:** {s}
- **critic:** {c}
- **round:** 1

## Scores

| claim_id | score | verdict | issue | counter_evidence | fix_hint |
|---|---|---|---|---|---|
{rows}

## Missing claims

- {missing}

## Estate observations

-

## Summary

{summary}
"""
for s in ("D1", "FLOWS", "TARGET"):
    reg = json.load(open(f"analysis/gauntlet/{s}/claims.json"))
    for c, base in (("client", 8), ("standard", 9)):
        rows = "\n".join(f"| {cl['id']} | {base + (i % 2)} | {'confirmed' if cl['type'] == 'fact' else 'insightful'} | | | |"
                         for i, cl in enumerate(reg["claims"]))
        open(f"analysis/gauntlet/{s}/round1-{c}.md", "w", encoding="utf-8").write(TPL.format(
            s=s, c=c, rows=rows,
            missing=("[standard-fact] " if c == "standard" else "") + "one statement a reader of this scope would expect and does not find",
            summary="Locators resolve and the statements match what the evidence shows."))
print("reviewer files for D1, FLOWS, TARGET written")
PY
for s in D1 FLOWS TARGET; do
  for c in client standard; do run md_to_json critic analysis/gauntlet/$s/round1-$c.md; done
  run score_aggregate $s 1 | grep -q '"passed": true' || { echo "$s did not pass"; exit 1; }
done
run gate_aggregate 1 >/dev/null; test -f analysis/gate/round1-fixplan.md

# ---------- client questions become the Open_Questions sheet of every workbook
run questions add inventory client "Which system wins when the customer address in the shop, the ERP and the CRM differ?" --effect "decides where the customer master belongs and whether the shop may keep writing its own registration data" >/dev/null
run questions add hybris-shop client "Is the line between the shop and the legacy portal an interface, or a drawing only?" --effect "decides whether switching off the portal touches the shop at all" >/dev/null
run questions add hybris-shop inventory "Should the undescribed line between CRM and ERP appear as an assumed interface?" >/dev/null
run questions list --client | grep -q client
if [ "$LANG_" = de ]; then
  run questions assumption Q-inventory-001 --text "Die Analyse geht davon aus, dass das ERP den führenden Kundendatensatz hält und das CRM ihn liest; der Shop schreibt Registrierungsdaten nur noch in das ERP." --if-not "Die Option O-001 ändert sich: die Führung des Kundendatensatzes liegt woanders, und der Fluss F-004 muss neu entworfen werden." >/dev/null
  run questions edit Q-inventory-001 --why "Das ERP führt die bestellende Organisation bereits für die Rechnungsstellung, und die Strategienotiz verlangt einen gemeinsamen Datensatz für Vertrieb und Service." --note fixture >/dev/null
  run questions assumption Q-hybris-shop-001 --text "Die Analyse geht davon aus, dass die Linie zwischen dem Shop und dem alten Portal nur gezeichnet ist und keine Schnittstelle besteht." --if-not "Das Abschalten des Portals (Option O-003) berührt auch den Shop; der Fluss F-005 braucht vor dem Vertragsende einen Ersatz." >/dev/null
  run questions edit Q-hybris-shop-001 --why "Kein Text der Landschaftsbeschreibung beschreibt diese Verbindung, und die Integrationsplattform kennt kein Szenario dafür." --note fixture >/dev/null
else
  run questions assumption Q-inventory-001 --text "The analysis assumes that the ERP holds the leading customer record and the CRM reads it; the shop writes registration data into the ERP only." --if-not "Option O-001 changes: the customer master sits elsewhere, and the flow F-004 has to be redesigned." >/dev/null
  run questions edit Q-inventory-001 --why "The ERP already holds the buying organisation for invoicing, and the strategy note asks for one record shared by sales and service." --note fixture >/dev/null
  run questions assumption Q-hybris-shop-001 --text "The analysis assumes that the line between the shop and the legacy portal is a drawing only and that no interface exists." --if-not "Switching off the portal (option O-003) also touches the shop; the flow F-005 needs a replacement before the contract ends." >/dev/null
  run questions edit Q-hybris-shop-001 --why "No text of the landscape description describes this connection, and the integration platform holds no scenario for it." --note fixture >/dev/null
fi
run questions affects Q-inventory-001 customer,O-001,F-004 >/dev/null
run questions affects Q-hybris-shop-001 I-hybris-shop-05,F-005,legacy-portal,O-003 >/dev/null
run questions list --open | grep -q "Q-hybris-shop"
run reference add --fact "fixture reference fact" --applies "SAP Commerce Cloud 2205" --url "https://example.invalid/doc" --provenance researcher | grep -q "added PS-7-001"
run learn add --section B --title "fixture learning" --what "x" --evidence "y" --generalises "z" --proposal "p" --touches "engine" | grep -q "L-001"
run status scope hybris-shop '{"status": "final", "wave": 1}' >/dev/null
run progress | grep -q "PROGRESS"

# ---------- workbooks and diagrams
run build_excel --all
run lint_deliverable
run lint_deliverable --standalone --all --round 1
run kb add --text "Every scope of this fixture reads the same nightly export." --topic fixture-export --topic-summary "the shared nightly export" --applies-to '*' --type decision | grep -q "KB-001"
run render brief gate cto 1 --out | grep -q "gate-cto"
if grep -q "## KNOWLEDGE BASE" analysis/briefs/gate-cto-r1.md; then echo "knowledge base block in a gate brief"; exit 1; fi   # 0.10: gate roles get no KNOWLEDGE BASE block
run render brief analyst hybris-shop --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/analyst-hybris-shop.md
run render brief critic client hybris-shop 1 --force --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/critic-client-hybris-shop-r1.md
mrun build_landscape_diagram --no-layout
python3 - <<'PY'
import openpyxl, glob, re, os, json, xml.etree.ElementTree as ET
files = sorted(glob.glob("deliverables/intern/*.xlsx"))   # full edition: + Claims + Open_Questions
assert len(files) == 4, files
for f in files:
    wb = openpyxl.load_workbook(f); names = set(wb.sheetnames); bad = []
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    for ref in re.findall(r"([A-Za-z_][\w]*)!\$", c.value):
                        if ref not in names: bad.append((ws.title, c.coordinate, ref))
    charts = sum(len(ws._charts) for ws in wb)
    oq = "Offene_Fragen" if json.load(open("run.json"))["languages"]["deliverable"] == "de" else "Open_Questions"
    assert oq in names, f"{f}: no {oq} sheet"
    assert wb[oq].max_row >= 3, f"{f}: the client questions did not reach the sheet"
    cust = openpyxl.load_workbook(f.replace("/intern/", "/")).sheetnames   # customer edition: result sheets only
    assert oq not in cust and "Claims" not in cust, cust
    heads = [c.value for c in wb["Claims"][1]]
    assert not any(h and ("Round" in h or "Note" in h) for h in heads), heads
    assert wb.sheetnames[0] == "Management_Summary", wb.sheetnames
    assert "Overview" in names and charts >= 1, f"{f}: no chart on Overview"
    print(f, "sheets:", len(wb.sheetnames), "| dangling refs:", len(bad), "| charts:", charts)
    assert not bad, bad[:5]
wb = openpyxl.load_workbook("deliverables/Landscape_System_Inventory.xlsx")
assert wb["Systems"].max_row == 6 and wb["Data_Objects"].max_row == 6, (wb["Systems"].max_row, wb["Data_Objects"].max_row)
assert wb["Sources"].max_row == 4 and wb["Strategic_Vision"].max_row == 6
assert str(wb["Data_Objects"]["E2"].value).startswith("=IF("), wb["Data_Objects"]["E2"].value   # mastership is a formula, never typed in
wb = openpyxl.load_workbook("deliverables/Landscape_System_Profiles.xlsx")
assert wb["Interfaces"].max_row == 6 and wb["Data_Ownership"].max_row == 6, wb["Interfaces"].max_row
assert wb["Profiles"].max_row == 2 and wb["Constraints"].max_row == 3
wb = openpyxl.load_workbook("deliverables/Landscape_Data_Flows_SSOT.xlsx")
assert wb["Flows"].max_row == 6 and wb["SSOT_Matrix"].max_row == 6, wb["Flows"].max_row
assert wb["Integration_Debt"].max_row == 4
wb = openpyxl.load_workbook("deliverables/Landscape_Target_Architecture.xlsx")
assert wb["Options"].max_row == 6 and wb["Roadmap"].max_row == 3 and wb["Principles"].max_row == 4, wb["Options"].max_row
for d in ("deliverables/Landscape_AsIs.drawio", "deliverables/Landscape_Target.drawio"):
    assert os.path.exists(d), d
    root = ET.parse(d).getroot()
    cells = root.findall(".//mxCell")
    verts = [c for c in cells if c.get("vertex") == "1"]; edges = [c for c in cells if c.get("edge") == "1"]
    assert len(verts) >= 5 and len(edges) >= 4, (d, len(verts), len(edges))
    print(d, "vertices:", len(verts), "edges:", len(edges))
tgt = open("deliverables/Landscape_Target.drawio", encoding="utf-8").read()
assert "mdm-hub" in tgt, "a system introduced by an option is missing from the target diagram"
assert "O-005" not in tgt, "a rejected option reached the target diagram"
print("workbook and diagram assertions ok")
PY
run build_excel --all --interim >/dev/null; ls work/interim/*/Landscape_System_Profiles.xlsx >/dev/null
python3 -c "import openpyxl,glob; wb=openpyxl.load_workbook(glob.glob('work/interim/*/Landscape_System_Profiles.xlsx')[0]); assert wb.sheetnames[0]=='INTERIM', wb.sheetnames"
run build_excel D3 --internal >/dev/null; test -f work/internal/Landscape_Data_Flows_SSOT_Review_Notes.xlsx
test ! -d deliverables/interim && test ! -d deliverables/internal
mrun build_landscape_diagram --as-is --no-layout | grep -q "as-is:"

# ---------- handover: the passed artefacts of this run
run handover export | grep -q released
for t in system-inventory data-flows target-architecture; do run handover list | grep -q "$t"; done
run status verify --brief || true
run status next || true

# ---------- quote gate: the optional quote column, dbcx evidence quotes, the critic pack block (after the workbooks: they never show a quote)
python3 - <<'PY'
p = "analysis/scopes/hybris-shop.md"; s = open(p, encoding="utf-8").read()
s = s.replace("| id | type | statement | evidence | target | supersedes | history |\n|---|---|---|---|---|---|---|", "| id | type | statement | evidence | quote | target | supersedes | history |\n|---|---|---|---|---|---|---|---|")
for row in [l for l in s.splitlines() if l.startswith("| C-hybris-shop-00")]:   # one quote (C-001), the other claims an empty cell
    c = row.split(" | "); c.insert(4, "The transfer runs at 01:30 and takes up to two hours." if row.startswith("| C-hybris-shop-001 |") else ""); s = s.replace(row, " | ".join(c))
open(p, "w", encoding="utf-8").write(s)
PY
run md_to_json system analysis/scopes/hybris-shop.md >/dev/null
run evidence quotes hybris-shop | grep -q "hybris-shop: 1 verified, 0 partial, 0 not_found, 0 unreadable, 3 no_quote"
run extract_claims hybris-shop --force | grep -q "quote check: 1 verified"
grep -q "C-hybris-shop-001: verified at SRC-001#L41" analysis/gauntlet/hybris-shop/critic-pack.md

echo "=== ea-landscape / conflicts (detect -> hold -> route -> resolve | undecidable -> consolidator brief)"
X="$TMP/ea-landscape-conflicts"; mkdir -p "$X"; cd "$X"
run init run --method ea-landscape --dir "$X" --lang "$LANG_" --client "Fixture Industries AG" --consultancy "Fixture Consulting" --title "Enterprise architecture fixture (conflicts)" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$X" --variant conflicts >/dev/null   # + a second system analysis (sap-erp) that disagrees with the shop and claims the customer master
run render instructions --force >/dev/null; run md_to_json --generate >/dev/null; run corpus index >/dev/null; run status init >/dev/null
for k in "inventory analysis/inventory/landscape_inventory.md" "system analysis/scopes/hybris-shop.md" "system analysis/scopes/sap-erp.md"; do run md_to_json $k >/dev/null; done
mrun discover >/dev/null; run plan_waves >/dev/null
run status set phases.preflight.status '"done"' >/dev/null; run status set phases.inventory '{"status": "final", "type": "gauntlet", "scope": "D1", "gauntlet_rounds": [1], "passed": true}' >/dev/null
run status scope sap-erp '{"status": "final", "wave": 1, "passed": true}' >/dev/null; run status scope hybris-shop '{"status": "final", "wave": 2, "passed": true}' >/dev/null
for s in akeneo-pim salesforce-crm legacy-portal; do run status scope $s '{"status": "skipped", "wave": 3}' >/dev/null; done
out="$(run status next)"; echo "$out" | grep -q "NEXT: conflicts before consolidation_flows - 2 open conflict(s)" || { echo "$out"; echo "conflict hold missing"; exit 1; }
if [ "$LANG_" = de ]; then CF1="Mechanismus, Frequenz"; CF2="als führend genannt"; else CF1="style, frequency"; CF2="claimed master"; fi   # detector framing in the run language
run conflicts list | grep -q "CF-001 \[interface\] hybris-shop <-> sap-erp (I-hybris-shop-01 / I-sap-erp-01; $CF1) - open"
run conflicts list | grep -q "CF-002 \[mastership\] customer ($CF2: sap-erp, salesforce-crm) - open"
run conflicts detect | grep -q "2 conflict(s) detected, 2 open"; python3 -c "import json; r=json.load(open('analysis/consolidated/CONFLICTS.json')); assert [c['id'] for c in r['conflicts']]==['CF-001','CF-002'], r"   # idempotent
out="$(run conflicts route)"; echo "$out" | grep -q "sap-erp: CF-001, CF-002 -> bash \"$PLUGIN/scripts/dbcx\" render brief analyst sap-erp --conflicts --out"; echo "$out" | grep -q "hybris-shop: CF-001"
run render brief analyst sap-erp --conflicts --out | grep -q "analysis/briefs/analyst-sap-erp-conflicts.md"
for pat in "## CONFLICTS TO RESOLVE" "CF-001" "CF-002" "YOU - sap-erp" "analysis/scopes/hybris-shop.md" "undecidable - <reason>"; do grep -q -- "$pat" analysis/briefs/analyst-sap-erp-conflicts.md || { echo "conflicts brief lacks: $pat"; exit 1; }; done
python3 - <<'PY2'
import json, subprocess, sys, os
H = os.path.join(os.environ["PLUGIN"], "hooks", "dbcx_hook.py"); cwd = os.getcwd()
def hook(tool, ti): return subprocess.run([sys.executable, H, "PreToolUse"], input=json.dumps({"tool_name": tool, "tool_input": ti, "agent_name": "analyst-sap-erp", "cwd": cwd}), capture_output=True, text=True).stdout
assert "deny" in hook("Bash", {"command": "dbcx conflicts resolve CF-001 --claim C-sap-erp-003 --by sap-erp"}), "H9: an analyst resolved a conflict"
assert "deny" in hook("Write", {"file_path": os.path.join(cwd, "analysis/consolidated/CONFLICTS.json"), "content": "{}"}), "H9: an analyst wrote the register"
assert "deny" not in hook("Bash", {"command": "dbcx conflicts list"}), "H9: conflicts list denied"
print("conflict hook guard ok")
PY2
if run conflicts resolve CF-001 --claim C-sap-erp-001 --by sap-erp >/dev/null 2>&1; then echo "quote guard FAILED (a resolution without quote)"; exit 1; fi
# the ERP analyst's answer: one claim with a verbatim quote settles the interface; the customer master stays undecidable
python3 - <<'PY2'
p = "analysis/scopes/sap-erp.md"; s = open(p, encoding="utf-8").read()
s = s.replace("| id | type | statement | evidence | target | supersedes | history |\n|---|---|---|---|---|---|---|", "| id | type | statement | evidence | quote | target | supersedes | history |\n|---|---|---|---|---|---|---|---|")
for row in [l for l in s.splitlines() if l.startswith("| C-sap-erp-00")]: c = row.split(" | "); c.insert(4, ""); s = s.replace(row, " | ".join(c))
s = s.rstrip("\n") + "\n| C-sap-erp-003 | fact | The ERP sends prices and stock to the shop as a nightly flat file that starts at 01:30. | SRC-001#L41 | The transfer runs at 01:30 and takes up to two hours. | D2/Interfaces:I-sap-erp-01 | | |\n"
open(p, "w", encoding="utf-8").write(s)
PY2
run md_to_json system analysis/scopes/sap-erp.md >/dev/null
run conflicts resolve CF-001 --claim C-sap-erp-003 --by sap-erp | grep -q "CF-001: resolved by sap-erp with C-sap-erp-003 (quote verified) -> KB-001 \[cross-scope-finding · proposal, applies to hybris-shop, sap-erp\]"
run conflicts undecidable CF-002 --reason "both the ERP and the CRM document their claim; no document ranks them" --by sap-erp | grep -q "CF-002: undecidable -> client question Q-sap-erp-CF-002"
python3 -c "import json; q=[x for x in json.load(open('state/QUESTIONS.json'))['questions'] if x['id']=='Q-sap-erp-CF-002'][0]; assert q['kind']=='client_question' and q['to']=='client' and len(q['options'])==2 and 'released' not in q, q"   # live release: no flag
run kb show --scope hybris-shop | grep -q "KB-001"
out="$(run status next)"; echo "$out" | grep -q "NEXT: consolidation_flows / scope FLOWS" || { echo "$out"; echo "the consolidation is still held"; exit 1; }
run render digest FLOWS >/dev/null; run render brief consolidate FLOWS --out >/dev/null
for pat in "## CONFLICTS (analysis/consolidated/CONFLICTS.json" "RESOLVED by sap-erp with C-sap-erp-003" "client question Q-sap-erp-CF-002"; do grep -q -- "$pat" analysis/briefs/consolidate-flows.md || { echo "consolidator brief lacks: $pat"; exit 1; }; done
echo "conflict register ok"

echo "=== ea-landscape / de"
D="$TMP/ea-landscape-de"; mkdir -p "$D"; cd "$D"
run init run --method ea-landscape --dir "$D" --lang de --client "Fixture Industries AG" --consultancy "Fixture Consulting" --title "Zielarchitektur Fixture" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$D" >/dev/null
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
run corpus index >/dev/null
run status init >/dev/null
for k in "inventory analysis/inventory/landscape_inventory.md" "system analysis/scopes/hybris-shop.md" \
         "data_flows analysis/consolidated/FLOWS.md" "target_architecture analysis/consolidated/TARGET.md"; do run md_to_json $k >/dev/null; done
mrun discover >/dev/null; run plan_waves >/dev/null
run questions add inventory client "Welches System gilt, wenn die Kundenadresse in Shop, ERP und CRM voneinander abweicht?" --effect "entscheidet, wo der Kundendatensatz geführt wird" >/dev/null
run questions add hybris-shop client "Ist die Linie zwischen Shop und altem Portal eine Schnittstelle oder nur gezeichnet?" --effect "entscheidet, ob das Abschalten des Portals den Shop berührt" >/dev/null
run questions assumption Q-inventory-001 --text "Die Analyse geht davon aus, dass das ERP den führenden Kundendatensatz hält und das CRM ihn liest; der Shop schreibt Registrierungsdaten nur noch in das ERP." --if-not "Die Option O-001 ändert sich: die Führung des Kundendatensatzes liegt woanders, und der Fluss F-004 muss neu entworfen werden." >/dev/null
run questions edit Q-inventory-001 --why "Das ERP führt die bestellende Organisation bereits für die Rechnungsstellung, und die Strategienotiz verlangt einen gemeinsamen Datensatz für Vertrieb und Service." --note fixture >/dev/null
run questions assumption Q-hybris-shop-001 --text "Die Analyse geht davon aus, dass die Linie zwischen dem Shop und dem alten Portal nur gezeichnet ist und keine Schnittstelle besteht." --if-not "Das Abschalten des Portals (Option O-003) berührt auch den Shop; der Fluss F-005 braucht vor dem Vertragsende einen Ersatz." >/dev/null
run questions edit Q-hybris-shop-001 --why "Kein Text der Landschaftsbeschreibung beschreibt diese Verbindung, und die Integrationsplattform kennt kein Szenario dafür." --note fixture >/dev/null
run questions affects Q-inventory-001 customer,O-001,F-004 >/dev/null
run questions affects Q-hybris-shop-001 I-hybris-shop-05,F-005,legacy-portal,O-003 >/dev/null
run build_excel --all
run lint_deliverable
run lint_deliverable --standalone --all
mrun build_landscape_diagram --no-layout | grep -q "target:"
python3 - <<'PY'
import openpyxl
wb = openpyxl.load_workbook("deliverables/Landscape_System_Inventory.xlsx")
vals = [wb["Systems"].cell(row=r, column=2).value for r in range(2, 7)]
assert "PIM" in vals and "Commerce / Shop" in vals, vals          # German labels reached the cells
wb = openpyxl.load_workbook("deliverables/Landscape_Target_Architecture.xlsx")
moves = [wb["Options"].cell(row=r, column=2).value for r in range(2, 7)]
assert "Führung verlagern" in moves and "abschalten" in moves, moves
assert wb["README"]["A1"].value.startswith("D4 Zielarchitektur"), wb["README"]["A1"].value
print("German deliverable assertions ok")
PY
run render brief analyst hybris-shop | grep -q "DELIVERABLE LANGUAGE: de"

echo "=== ea-landscape / lean (profile lean: rulings -> inventory -> consolidations -> build -> gate hygiene)"
L="$TMP/ea-landscape-lean"; mkdir -p "$L"; cd "$L"
if run init run --method tech-scoring --profile lean --dir "$TMP/lean-refused" >/dev/null 2>&1; then echo "profile guard FAILED (tech-scoring accepted lean)"; exit 1; fi
run init run --method ea-landscape --profile lean --dir "$L" --lang "$LANG_" --client "Fixture Industries AG" --consultancy "Fixture Consulting" --title "Enterprise architecture fixture (lean)" >/dev/null
grep -q '"profile": "lean"' run.json
python3 "$HERE/fixtures/make_fixture.py" "$L" >/dev/null
rm -f analysis/scopes/*.md; rm -rf analysis/gauntlet/hybris-shop   # a lean run has no system analyses
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
run corpus index >/dev/null
run status init >/dev/null
python3 - <<'PY2'
import json
st = json.load(open("state/STATUS.json"))
assert st["phases"]["waves"]["enabled"] is False, st["phases"]["waves"]
assert json.load(open("run.json"))["profile"] == "lean"
PY2
run status next | grep -q "evidence_bases"            # the lean preflight hint names the docs-domain allowlist
python3 - <<'PY2'
import json
r = json.load(open("run.json")); r["evidence_bases"] = [{"id": "standard-docs", "domains": ["help.sap.com"]}]; json.dump(r, open("run.json", "w"), indent=2)
PY2
run safe_web "SAP Commerce Cloud release notes" --check-only --url "https://help.sap.com/docs/SAP_COMMERCE_CLOUD" | grep -q '"allowed": true'
run status set phases.preflight.status '"done"' >/dev/null
run status next | grep -q "NEXT: rulings before inventory (human_input.rulings required)"
run rulings draft >/dev/null
run rulings add "Is the integration platform the only route for new interfaces?" --topic middleware --option "A|yes|every new flow runs over it" --option "B|no|point to point stays allowed" --recommend A >/dev/null
run rulings answer R-01 --option A >/dev/null; run rulings done >/dev/null
run status next | grep -q "NEXT: inventory / scope D1"
run status set phases.inventory.status '"analysing"' >/dev/null   # the inventory analyst was spawned and has reported
# every claim of the lean fixture gets a verbatim quote from a corpus locator it cites (quotes required); no claim cites a system analysis
python3 - <<'PY2'
import os, sys, re
sys.path.insert(0, os.environ["TOOLS"]); import common, evidence
cfg = common.project()
def text(loc): got, _ = evidence.locator_texts(loc, cfg, offline=True); return " ".join(t for _, t in got)
for p in ("analysis/inventory/landscape_inventory.md", "analysis/consolidated/FLOWS.md", "analysis/consolidated/TARGET.md"):
    s = re.sub(r"\bC-hybris-shop-\d{3}\b", "SRC-001#L41", open(p, encoding="utf-8").read()); head = "| id | type | statement | evidence | target | supersedes | history |"
    s = s.replace(head + "\n|---|---|---|---|---|---|---|", "| id | type | statement | evidence | quote | target | supersedes | history |\n|---|---|---|---|---|---|---|---|")
    for row in [l for l in s.splitlines() if re.match(r"\| C-", l)]:
        c = row.split(" | "); ev = [("SRC-001#L41" if e.strip().startswith("analysis/scopes/") else e.strip()) for e in c[3].split(";")]
        src = next((e for e in ev if e.startswith("SRC-")), None) or "SRC-001#L1"
        if src not in ev: ev.append(src)
        q = next(l.strip() for l in text(src).splitlines() if len(re.sub(r"[^0-9A-Za-z]", "", l)) >= 30 and not l.lstrip().startswith(("#", "|", "<")) and "|" not in l)
        c[3] = "; ".join(ev); c.insert(4, q); s = s.replace(row, " | ".join(c))
    open(p, "w", encoding="utf-8").write(s)
print("lean fixture: quotes added")
PY2
run md_to_json inventory analysis/inventory/landscape_inventory.md >/dev/null
run extract_claims D1 --round 1 | grep -q "quote check: .* 0 not_found"
test -f analysis/gauntlet/D1/quotes.json
python3 -c "import json; q=json.load(open('analysis/gauntlet/D1/quotes.json')); assert q['mode']=='required' and q['counts']['no_quote']==0 and q['counts']['not_found']==0, q['counts']"
if run render brief critic standard D1 1 --out >/dev/null 2>&1; then echo "no-critic guard FAILED (a critic brief for the lean inventory)"; exit 1; fi
if run render brief critic client D1 1 --out >/dev/null 2>&1; then echo "critic guard FAILED (client critic in a lean run)"; exit 1; fi
run status next | grep -q "no critic scores this scope"
run score_aggregate D1 1 | grep -q '"passed": true'
python3 -c "import json; r=json.load(open('analysis/gauntlet/D1/round1-result.json')); assert r['critics']=={} and r['pass_rule_id']=='defects+quotes', r"
run render handover >/dev/null
out="$(run status next)"; echo "$out" | grep -q "NEXT: consolidation_flows / scope FLOWS"
if echo "$out" | grep -q "plan_waves"; then echo "lean run points at plan_waves"; exit 1; fi
if run render brief analyst hybris-shop --out >/dev/null 2>&1; then echo "split guard FAILED (an analyst brief in a lean run)"; exit 1; fi
run render digest FLOWS >/dev/null; grep -q "split none, no scope analyses" analysis/consolidated/digest-FLOWS.md; grep -q "Interface candidates per system" analysis/consolidated/digest-FLOWS.md
run render brief consolidate FLOWS --out >/dev/null; B=analysis/briefs/consolidate-flows.md
grep -q "MASTERSHIP CLAIMS" $B; grep -q "THE SYSTEMS AND THE DOCUMENTS THAT MENTION THEM" $B; grep -q "profile lean" $B
grep "EVIDENCE BASES YOU MAY READ" $B | grep -q "corpus \[corpus\]"
if grep -q "no access to the client" $B; then echo "lean consolidator brief still denies the corpus"; exit 1; fi
python3 - <<'PY2'
import json, subprocess, sys, os
H = os.path.join(os.environ["PLUGIN"], "hooks", "dbcx_hook.py"); cwd = os.getcwd(); src = os.path.join(cwd, "corpus", "text", "SRC-001.md")
def hook(agent): return subprocess.run([sys.executable, H, "PreToolUse"], input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": src}, "agent_name": agent, "cwd": cwd}), capture_output=True, text=True).stdout
assert "deny" not in hook("consolidate-flows"), "lean consolidator corpus read denied (H5)"
assert "deny" in hook("critic-standard-FLOWS"), "standard critic corpus read not denied"
print("lean hook matrix ok")
PY2
for s in FLOWS TARGET; do
  if [ "$s" = TARGET ]; then run render digest TARGET >/dev/null; run render brief consolidate TARGET --out >/dev/null; grep -q "AS-IS PICTURE" analysis/briefs/consolidate-target.md; fi
  run md_to_json $( [ "$s" = FLOWS ] && echo data_flows || echo target_architecture ) analysis/consolidated/$s.md >/dev/null
  run extract_claims $s --round 1 >/dev/null
  if run render brief critic client $s 1 --out >/dev/null 2>&1; then echo "client critic guard FAILED ($s)"; exit 1; fi
  run render brief critic standard $s 1 --out >/dev/null; grep -q "ROUND: 1 of max 1 (+1 rework round for defects only)" analysis/briefs/critic-standard-$s-r1.md
  python3 - "$s" <<'PY2'
import json, sys
s = sys.argv[1]; reg = json.load(open(f"analysis/gauntlet/{s}/claims.json"))
rows = "\n".join(f"| {c['id']} | 9 | {'confirmed' if c['type'] == 'fact' else 'insightful'} | | | |" for c in reg["claims"])
open(f"analysis/gauntlet/{s}/round1-standard.md", "w", encoding="utf-8").write(f"# Gauntlet score: {s} / standard / round 1\n\n- **scope:** {s}\n- **critic:** standard\n- **round:** 1\n\n## Scores\n\n| claim_id | score | verdict | issue | counter_evidence | fix_hint |\n|---|---|---|---|---|---|\n{rows}\n\n## Missing claims\n\n-\n\n## Estate observations\n\n-\n\n## Summary\n\nThe statements match the external standard.\n")
PY2
  run md_to_json critic analysis/gauntlet/$s/round1-standard.md >/dev/null
  run score_aggregate $s 1 | grep -q '"passed": true' || { echo "lean $s did not pass"; exit 1; }
  python3 -c "import json,sys; r=json.load(open('analysis/gauntlet/$s/round1-result.json')); assert list(r['critics'])==['standard'] and r['pass_rule_id']=='defects+quotes', r['critics']"
done
run questions add inventory client "Which system wins when the customer address in the shop, the ERP and the CRM differ?" --effect "decides where the customer master belongs" | grep -q "batched: 1 unreleased"
if [ "$LANG_" = de ]; then
  run questions assumption Q-inventory-001 --text "Die Analyse geht davon aus, dass das ERP den führenden Kundendatensatz hält und das CRM ihn liest; der Shop schreibt Registrierungsdaten nur noch in das ERP." --if-not "Die Option O-001 ändert sich: die Führung des Kundendatensatzes liegt woanders, und der Fluss F-004 muss neu entworfen werden." >/dev/null
  run questions edit Q-inventory-001 --why "Das ERP führt die bestellende Organisation bereits für die Rechnungsstellung, und die Strategienotiz verlangt einen gemeinsamen Datensatz für Vertrieb und Service." --note fixture >/dev/null
else
  run questions assumption Q-inventory-001 --text "The analysis assumes that the ERP holds the leading customer record and the CRM reads it; the shop writes registration data into the ERP only." --if-not "Option O-001 changes: the customer master sits elsewhere, and the flow F-004 has to be redesigned." >/dev/null
  run questions edit Q-inventory-001 --why "The ERP already holds the buying organisation for invoicing, and the strategy note asks for one record shared by sales and service." --note fixture >/dev/null
fi
run status set phases.consolidation_flows.status '"final"' >/dev/null; run status set phases.consolidation_target.status '"final"' >/dev/null
run status next | grep -q "RELEASE QUESTION BATCH (build)"
if run build_excel --all >/dev/null 2>&1; then echo "batched-release guard FAILED (build with an unreleased question)"; exit 1; fi
run questions release --all | grep -q "0 still unreleased"
run build_excel --all >/dev/null
mrun build_landscape_diagram --no-layout >/dev/null
run lint_deliverable --standalone --all --round 1
python3 - <<'PY2'
import glob, os
books = sorted(os.path.basename(f) for f in glob.glob("deliverables/*.xlsx"))
assert books == ["Landscape_Data_Flows_SSOT.xlsx", "Landscape_System_Inventory.xlsx", "Landscape_System_Profiles.xlsx", "Landscape_Target_Architecture.xlsx"], books
assert not glob.glob("analysis/briefs/analyst-*") and not glob.glob("analysis/briefs/critic-client-*") and not glob.glob("analysis/briefs/critic-standard-D1*"), sorted(os.listdir("analysis/briefs"))
assert not os.path.exists("state/WAVES.json") and not os.path.exists("state/scopes.json") and not glob.glob("analysis/scopes/*.md")
assert all(os.path.exists(f"analysis/gauntlet/{s}/quotes.json") for s in ("D1", "FLOWS", "TARGET"))
print("lean assertions ok:", books)
PY2
python3 - "$LANG_" <<'PY2'
# D2 under lean: one profile per inventory system (out-of-scope excluded), interfaces = both ends of every FLOWS flow, ownership from the
# inventory's data objects; capabilities, pain points and constraints are not assessed - every figure over them says so, never a zero
import sys, openpyxl
NA = {"de": "nicht erhoben", "en": "not assessed"}[sys.argv[1]]
wb = openpyxl.load_workbook("deliverables/Landscape_System_Profiles.xlsx")
col = lambda ws, h: [c.value for c in ws[1]].index(h)
rows = lambda ws: [[c.value for c in r] for r in ws.iter_rows(min_row=2) if r[0].value]
p = rows(wb["Profiles"]); assert [r[0] for r in p] == ["akeneo-pim", "hybris-shop", "salesforce-crm", "sap-erp"], [r[0] for r in p]
for r in p: assert r[2] == NA and r[4].startswith("=COUNTIF(") and r[5].startswith("=COUNTIFS(") and r[6:9] == [NA] * 3, r
i = rows(wb["Interfaces"]); assert len(i) == 9 and {(r[0], r[1], r[2]) for r in i} >= {("hybris-shop", "F-001", "sap-erp"), ("sap-erp", "F-001", "hybris-shop"), ("hybris-shop", "F-005", "legacy-portal")}, i
assert not any(r[0] == "legacy-portal" for r in i)
o = rows(wb["Data_Ownership"]); assert sum(1 for r in o if r[1] == "customer") == 3 and len(o) == 12, o
for s in ("Capabilities", "Pain_Points", "Constraints"): assert not rows(wb[s]), s
m = [[c.value for c in r] for r in wb["Management_Summary"].iter_rows()]; na = sum(1 for r in m for v in r if v == NA); assert na == 5, na   # custom, blockers, act_now, constraints, eol
ov = [[c.value for c in r] for r in wb["Overview"].iter_rows()]; assert sum(1 for r in ov for v in r if v == NA) == 16, ov   # the pain-point matrix (4 x 2 + totals 2) and the six kv rows
assert len(wb["Overview"]._charts) == 2, len(wb["Overview"]._charts)   # no chart over a not-assessed sheet
rd = [[c.value for c in r] for r in wb["README"].iter_rows()]; assert sum(1 for r in rd if r[0] in ("Capabilities", "Pain_Points", "Constraints") and str(r[1]).lower().startswith(NA)) == 3, rd
inv = openpyxl.load_workbook("deliverables/Landscape_System_Inventory.xlsx")["Systems"]; h = [c.value for c in inv[1]]; k = next(n for n, x in enumerate(h) if x and "D2" in x)
assert [r[k] for r in rows(inv)].count({"de": "ja", "en": "yes"}[sys.argv[1]]) == 4, [r[k] for r in rows(inv)]   # D1 names the systems D2 profiles
print("lean D2 ok")
PY2

echo "EA-LANDSCAPE SMOKE OK"
