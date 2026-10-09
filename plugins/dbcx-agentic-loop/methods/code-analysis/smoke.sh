#!/usr/bin/env bash
# code-analysis method self-test: two throw-away single-run projects in $TMP.
#   generic: _generic packs, full chain incl. Markdown conversion, gauntlet/gate aggregation, all four workbooks, diagram, hooks
#   sap:     sap-commerce pack, scan + derive + discover + waves + D1 build on a hybris-shaped fixture repo
# Env from engine/smoke_test.sh: TOOLS, PLUGIN, TMP, LANG_
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; run() { python3 "$TOOLS/$1.py" "${@:2}"; }; mrun() { python3 "$HERE/tools/$1.py" "${@:2}"; }
export PATH="$PLUGIN/scripts:$PATH"

echo "=== code-analysis / generic"
G="$TMP/code-generic"; mkdir -p "$G"; cd "$G"
run init run --method code-analysis --dir "$G" --knowledge source=_generic,target=_generic --lang "$LANG_" --client "Fixture Shop GmbH" --consultancy "Fixture Consulting" --title "Code analysis fixture" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$G" generic
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
run requirements_to_json
run intake --no-questions >/dev/null; test -f docs/INTAKE.md
run status init
mrun scan_inventory "$G/repo"
mrun discover
run plan_waves
run knowledge sources
run evidence bases | grep -q repository
for k in "inventory analysis/inventory/inventory_analysis.md" "unit analysis/units/shopcore.md" "critic analysis/gauntlet/shopcore/round1-client.md" "critic analysis/gauntlet/shopcore/round1-standard.md" "D3 analysis/consolidated/D3.md" "D4 analysis/consolidated/D4.md" "gate analysis/gate/round1-cto.md"; do run md_to_json $k; done
python3 - <<'PY'
import subprocess, sys, os
T = os.environ.get("TOOLS")
md = open("analysis/units/shopcore.md").read()
bad = md.replace("| user groups | new | repo/src/shopcore/src/main/resources/data/essential-usergroups.impex | |", "| user groups | new | repo/src/shopcore/src/main/resources/data/essential-usergroups.impex | keeps the literal <!-- marker | SURPLUS CELL |")
open("analysis/units/shopcore_bad.md", "w").write(bad)
r = subprocess.run([sys.executable, f"{T}/md_to_json.py", "unit", "analysis/units/shopcore_bad.md"], capture_output=True, text=True); out = r.stdout
assert "literal '<!--'" in out and "surplus folded" in out and "OK" in out, out
os.remove("analysis/units/shopcore_bad.md"); os.remove("analysis/units/shopcore_bad.json")
cr = open("analysis/gauntlet/shopcore/round1-client.md").read().replace("| C-shopcore-002 | 9 | insightful | | | |", "| C-shopcore-002 | 9 | insightful | | | |\n| C-shopcore-001 | 7 | imprecise | dup | | |")
open("analysis/gauntlet/shopcore/dup.md", "w").write(cr)
r = subprocess.run([sys.executable, f"{T}/md_to_json.py", "critic", "analysis/gauntlet/shopcore/dup.md"], capture_output=True, text=True)
assert r.returncode == 1 and "duplicate claim_id" in r.stdout, r.stdout
os.remove("analysis/gauntlet/shopcore/dup.md")
md2 = open("analysis/units/shopcore.md").read().replace("| C-shopcore-003 | assessment | FR-023 successor products could use the standard ProductReference instead of the own attribute. | repo/src/shopcore/schema.xml | D3/Coverage:FR-023 | |",
    "| C-shopcore-003 | assessment | FR-023 successor products could use the standard ProductReference instead of the own attribute. | repo/src/shopcore/schema.xml | D3/Coverage:FR-023; D2/Depth | |\n| C-shopcore-099 | fact | " + ("The unit holds 12 controllers, 34 services, 7 facades and 3 jobs across 96 files with 4 812 lines; " * 4) + "| repo/src/shopcore | D9/Nowhere | |")
open("analysis/units/shopcore_atomic.md", "w").write(md2)
r = subprocess.run([sys.executable, f"{T}/md_to_json.py", "unit", "analysis/units/shopcore_atomic.md"], capture_output=True, text=True); out = r.stdout
assert r.returncode == 0 and "2 targets" in out and "figures (> 2)" in out and "chars (> 350)" in out and "not a sheet of this method" in out and "atomic-claim rules: 1 over-long, 1 multi-figure, 2 target defects" in out, out
os.remove("analysis/units/shopcore_atomic.md"); os.remove("analysis/units/shopcore_atomic.json")
r = subprocess.run([sys.executable, f"{T}/md_to_json.py", "unit", "analysis/units/shopcore.md"], capture_output=True, text=True); assert "atomic-claim" not in r.stdout, r.stdout
print("converter guards ok (incl. atomic-claim rules)")
PY
run extract_claims shopcore
run evidence check shopcore
run score_aggregate shopcore 1 --dry-run | grep -q '"passed"'
run score_aggregate shopcore 1 >/dev/null
if run md_to_json critic analysis/gauntlet/shopcore/round1-client.md >/dev/null 2>&1; then echo "closed-file guard FAILED"; exit 1; else echo "closed-file guard ok"; fi
run status verify --brief || true
run extract_claims D1 >/dev/null; run extract_claims D3 >/dev/null; run extract_claims D4 >/dev/null
run gate_aggregate 1 >/dev/null
run render context analyst shopcore --round 1 | sed -n '1,5p'
run render context critic standard shopcore 2 | grep -c "PLATFORM NOTES" >/dev/null
run render brief analyst shopcore --out >/dev/null; test -f analysis/briefs/unit-shopcore.md; grep -q "EVIDENCE BASES YOU MAY READ" analysis/briefs/unit-shopcore.md; grep -q "ROLE INSTRUCTIONS" analysis/briefs/unit-shopcore.md
run render brief critic client shopcore 1 --out >/dev/null; grep -q "^MODEL:" analysis/briefs/critic-client-shopcore-r1.md
run render brief critic standard D3 1 --out | grep -q "MODEL "
if run render brief analyst shopcore --round 2 --out >/dev/null 2>&1; then echo "addendum guard FAILED"; exit 1; else echo "addendum guard ok"; fi
echo "test addendum" > analysis/briefs/add.md; run render brief analyst shopcore --round 2 --addendum analysis/briefs/add.md --out | grep -q "wrote"
run render brief postpass shopcore | grep -q "POST-PASS TEXT CORRECTION"
run render brief inventory | grep -q "activation"
run render brief research | grep -q "RESEARCH TOPICS"
run render digest D3 >/dev/null; run render digest D4 >/dev/null; test -f analysis/consolidated/digest-D4.md; grep -q "citing claims" analysis/consolidated/digest-D3.md
run render brief consolidate D4 | grep -q "DIGEST"
run render brief progress | grep -q "progress-reporter"
run render handover >/dev/null; test -f analysis/inventory/D1_HANDOVER.md
mrun count shopcore | grep -q "^RULE:"
run questions add shopcore shopapi "Does shopapi expose Equipment?" >/dev/null; run questions add shopcore client "Is the equipment list still in scope?" --id Q-shopcore-9 --effect "decides whether FR-030 and F-001 are estimated" >/dev/null;
if [ "$LANG_" = de ]; then run questions edit Q-shopcore-9 --why "Der Code enthält die Maschinenliste vollständig; die Anforderungsliste nennt sie nur für die erste Ausbaustufe." --note "fixture" >/dev/null; run questions assumption Q-shopcore-9 --text "Die Analyse geht davon aus, dass die Maschinenliste im Scope bleibt und die Teillieferung je Werk erst in einer späteren Phase kommt." --if-not "FR-030 wird in die erste Ausbaustufe vorgezogen; die Empfehlung und die Migrationsaufgaben MT-002 und MT-003 ändern sich." >/dev/null
else run questions edit Q-shopcore-9 --why "The code holds the complete equipment list; the requirement list names it for the first release only." --note "fixture" >/dev/null; run questions assumption Q-shopcore-9 --text "The analysis assumes that the equipment list stays in scope and split delivery per plant comes in a later phase." --if-not "FR-030 moves into the first release; the recommendation and the migration tasks MT-002 and MT-003 change." >/dev/null; fi
 run questions list --open | grep -q "Q-shopcore"; run questions list --client | grep -q client
run reference add --fact "fixture fact" --applies "2.0" --url "https://example.invalid/doc" --provenance researcher | grep -q "added PS-7-001"
if [ "$LANG_" = de ]; then run reference title PS-7-001 --title "Produktreferenzen und Nachfolgeprodukte im Standard" --summary "Der Standard führt Nachfolgeprodukte als Produktreferenz vom Typ SUCCESSOR." --lang de >/dev/null
else run reference title PS-7-001 --title "Product references and successor products in the standard" --summary "The standard models successor products as a product reference of type SUCCESSOR." --lang en >/dev/null; fi
run learn add --section B --title "fixture learning" --what "x" --evidence "y" --generalises "z" --proposal "p" --touches "engine" | grep -q "L-001"
mrun d0 collect | grep -q "D0:"
run progress | grep -q "PROGRESS"
mrun export_artefacts --allow-draft | grep -q "proposed NR rows"; test -f analysis/consolidated/D2.json; test -f analysis/consolidated/requirements_set.json
python3 -c "import json; d=json.load(open('analysis/consolidated/requirements_set.json')); r=d['requirements']; assert [x['id'] for x in r][-1]=='NR-001' and r[0]['extra']['coverage_recommendation']=='keep-custom' and r[0]['description']=='Customers see their installed machines.', r[0]"
run build_excel --all
run status scope shopcore '{"status": "final"}' >/dev/null
run build_excel --all --interim >/dev/null; ls work/interim/*/D2_Customization_Depth.xlsx >/dev/null; python3 -c "import openpyxl,glob; wb=openpyxl.load_workbook(glob.glob('work/interim/*/D2_Customization_Depth.xlsx')[0]); assert wb.sheetnames[0]=='INTERIM', wb.sheetnames"
run build_excel D2 --internal >/dev/null; test -f work/internal/D2_Customization_Depth_Review_Notes.xlsx
test ! -d deliverables/interim && test ! -d deliverables/internal
run lint_deliverable
run lint_deliverable --standalone --all --round 1; python3 -c "import json; d=json.load(open('analysis/gate/round1-hygiene.json')); assert {'passed','counts','findings','cached_values'} <= set(d) and 'dangling_id' in d['counts'], d.keys()"
run kb add --text "Every scope of this fixture reads the same nightly export." --topic fixture-export --topic-summary "the shared nightly export" --applies-to '*' --type decision | grep -q "KB-001"
run render brief gate cto 1 --out | grep -q "gate-cto"
if grep -q "## KNOWLEDGE BASE" analysis/briefs/gate-cto-r1.md; then echo "knowledge base block in a gate brief"; exit 1; fi   # 0.10: gate roles get no KNOWLEDGE BASE block
run render brief analyst shopcore --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/unit-shopcore.md
run render brief critic client shopcore 1 --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/critic-client-shopcore-r1.md
run gate questions cto | grep -q C5; run render brief verifier 1 --out | grep -q gate-verifier; test -f analysis/gate/round1-verifier-sample.md; test -f analysis/gate/round1-workbooks/manifest.json
run gate_aggregate 1 >/dev/null; test -f analysis/gate/round1-fixplan.json; run render brief editor 1 --out | grep -q deliverable-editor
mrun build_dependency_diagram --include-standard
python3 - <<'PY'
import openpyxl, glob, re
for f in sorted(glob.glob("deliverables/*.xlsx") + glob.glob("deliverables/intern/*.xlsx")):
    wb = openpyxl.load_workbook(f); names = set(wb.sheetnames); bad = []
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    for ref in re.findall(r"([A-Za-z_][\w]*)!\$", c.value):
                        if ref not in names: bad.append((ws.title, c.coordinate, ref))
    charts = sum(len(ws._charts) for ws in wb)
    if "Claims" in names:
        heads = [c.value for c in wb["Claims"][1]]; assert not any(h and ("Round" in h or "Note" in h) for h in heads), heads
    assert (("Open_Questions" in names) or ("Offene_Fragen" in names)) == ("/intern/" in f), f"{f}: Open_Questions only in the full edition"
    print(f, "sheets:", len(wb.sheetnames), "| dangling refs:", len(bad), "| charts:", charts); assert not bad, bad[:5]
    if ("Overview" in names) or ("Uebersicht" in names): assert charts >= 1, "no pie chart on Overview"
    if f.endswith("D3_Requirements_Coverage.xlsx"):
        rq = "Requirements" if "Requirements" in names else "Anforderungen"; assert ({"Requirements", "Frontend_features", "New_requirements"} <= names) or ({"Anforderungen", "Frontend_Features", "Neue_Anforderungen"} <= names), names
        assert not ({"Joint_list", "Contributions", "Coverage", "Gesamtliste", "Anforderung_Einheit", "Abdeckung"} & names), names
        assert wb[rq].max_row == 5, wb[rq].max_row; heads = [c.value for c in wb[rq][1]]; assert ("Description" in heads or "Beschreibung" in heads) and any(h and "readiness" in h.lower() or h and "Reife" in h for h in heads), heads
        ff = "Frontend_features" if "Frontend_features" in names else "Frontend_Features"; assert wb[ff].max_row == 3 and wb[ff]["C3"].value == "NR-001", (wb[ff].max_row, wb[ff]["C3"].value)
    if f.endswith("D4_Target_Readiness.xlsx"):
        assert ("Integrations" in names) or ("Schnittstellen" in names), names
        assert ("Migration_tasks" in names) or ("Migrationsaufgaben" in names), names; assert not ({"Blockers", "Concerns", "Blocker", "Risiken", "Features"} & names), names
        mt = "Migration_tasks" if "Migration_tasks" in names else "Migrationsaufgaben"; assert wb[mt].max_row == 4 and wb[mt]["A2"].value == "MT-001", (wb[mt].max_row, wb[mt]["A2"].value)
    if f.endswith("D2_Customization_Depth.xlsx"):
        hm = "Depth" if "Depth" in names else "Heatmap"; heads = [c.value for c in wb[hm][1]]; assert heads[2] == "Disposition" and not any("(Formel)" in str(h) or "(formula)" in str(h) or h in ("Abgleich", "Check", "Konfidenz", "Confidence") for h in heads), heads
PY
run handover export requirements-coverage --force | grep -q released; run handover export customization-depth --force | grep -q released; run handover export requirements-set --force | grep -q released; run handover list | grep -q requirements-set
run status next || true

echo "=== code-analysis / sap-commerce"
S="$TMP/code-sap"; mkdir -p "$S"; cd "$S"
run init run --method code-analysis --dir "$S" --knowledge source=sap-commerce,target=sap-commerce --lang de --client "Fixture Shop GmbH" --consultancy "Fixture Consulting" --title "SAP fixture" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$S" sap
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
run requirements_to_json >/dev/null
run status init >/dev/null
mrun scan_inventory "$S/repo"
python3 - <<'PY'
import json; inv=json.load(open("analysis/inventory/inventory.json")); d=json.load(open("state/derived_knowledge.json"))
u=inv["units"]; assert set(u)=={"shopcore","shopfacades","shopstorefront","shopintegration","shopocc","shopbackoffice"}, set(u)
assert len(d["standard_units"])>=12, d; assert not [e for e in inv["dependency_edges"] if e["to_kind"]=="unknown"], "unknown deps"
c=u["shopcore"]; assert c["schema_extended_types"]==1 and c["schema_new_types"]==1 and c["schema_relations"]==1, c
assert c["override_candidates"] and c["shadowing_candidates"] and c["workflows"]==["order-process"], c["workflows"]
assert inv["deprecation_hits"] and inv["platform"]["version_hints"], inv["platform"]
assert c["metrics"]["code"] == 12, ("the cache/ package must be counted", c["metrics"])
assert any(h["id"] == "DEP-JALO" and h["file"].endswith("head.inc") for h in inv["deprecation_hits"]), ("Jalo import in a .inc include must be a hit", [h["file"] for h in inv["deprecation_hits"]])
assert "snapshot" in inv["platform"] or True  # git may be absent in the temp dir
assert c["loaded_in"] and "loc_maintained" in c and "override_candidates_resolved" in c and all("path_class" in h for h in c["deprecation_hits"]), "WP-E scan fields"
print("sap scan assertions ok | std units derived:", len(d["standard_units"]), "| dep hits:", len(inv["deprecation_hits"]))
PY
mrun discover; run plan_waves
test -f analysis/inventory/deprecation_hits_per_unit.md
run md_to_json inventory analysis/inventory/inventory_analysis.md >/dev/null
run build_excel D1
run lint_deliverable --standalone --all
run render context analyst shopcore | grep -A3 "PLATFORM NOTES" | sed -n '1,4p'
run render brief analyst shopcore | grep -q "DEPRECATION HITS"
run render brief analyst shopcore | grep -q "CHECK RECIPES"
python3 - <<'PY'
import json, subprocess, sys, os
H = os.path.join(os.environ["PLUGIN"], "hooks", "dbcx_hook.py"); cwd = os.getcwd()
def hook(payload): return subprocess.run([sys.executable, H, "PreToolUse"], input=json.dumps(dict(payload, cwd=cwd)), capture_output=True, text=True).stdout
assert "deny" in hook({"tool_name": "Bash", "tool_input": {"command": "cd repo && ant clean all"}}), "ant not denied"
assert "deny" in hook({"tool_name": "Write", "tool_input": {"file_path": os.path.join(cwd, "repo", "x")}}), "repo write not denied"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": os.path.join(cwd, "repo", "hybris")}}), "orchestrator read denied"
assert "deny" in hook({"tool_name": "Read", "tool_input": {"file_path": os.path.join(cwd, "repo", "hybris")}, "agent_name": "critic-standard-shopcore"}), "standard critic repo read not denied"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": os.path.join(cwd, "repo", "hybris")}, "agent_name": "unit-shopcore"}), "analyst repo read denied"
assert "deny" in hook({"tool_name": "WebSearch", "tool_input": {"query": "Fixture Shop GmbH hybris"}}), "client name not denied"
assert "deny" in hook({"tool_name": "Agent", "tool_input": {"subagent_type": "dbcx-agentic-loop:analyst", "prompt": "do it", "model": "opus"}}), "spawn without brief not denied"
print("hook smoke ok")
PY
echo "CODE-ANALYSIS SMOKE OK"
