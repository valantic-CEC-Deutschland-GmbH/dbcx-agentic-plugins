#!/usr/bin/env bash
# tech-fit-estimation self-test (one run, N options): throw-away single-run projects in $TMP, one per fixture variant.
#   none    the default single option (_generic pack) - full chain: fixture, intake, chunking, waves, every kind, gauntlet of both
#           chunks and of the SUMMARY, gate, every brief, workbook + interim + internal, lint, hygiene, handover, hooks
#   starts  brownfield "Migration" + greenfield "Neubau" on one pack: handover imports of a toy code analysis, client-assumptions,
#           a toy client repository with a narrow lookup, vendor standard code; bands, Grundlage per option, positions
#   packs   two technology packs (sap-commerce + spryker): standard-<pack> critics
#   scenarios the starts setup plus the row classification (dbcx classify draft -> agent proposal -> lead workbook -> approve ->
#           apply: TM-01, RF-01), Integration Suite sizes, a saving, run.json scenarios with fixed_phases_seed, client-critic grounds and a
#           standard dispute; asserts the validate refusals, the dispute routing, the scenario totals (recomputed before and after editing a
#           size of the mapping, a surcharge, a fixed phase and the day rate) and that no code locator reaches either edition
#   systems / systems-single a multi-system run (commerce with two options -> two scenarios, resp. one, a dependent
#           middleware, CDC, S/4 by the client, Magnolia by a partner) along the real flow: inputs, scope step, discover + waves
#           wave-1 analyses with gaps, the architect's batch (overrule, routing to the middleware, routing to SAP BTP outside the run,
#           reduction to the standard), the pickup into wave 2 (follow-up chunks, the routed packages in place), wave 2, consolidation,
#           build; fixtures/systems_check.py recomputes the views, the roll-up, the reconciliation, an external input, the range, the routed
#           and the superseded package, the SAP BTP input cell with its A-nn and (two scenarios) the selector and the comparison; both
#           editions, the customer edition passes the hygiene layer. Every every system chunk and the architect's batch run a critic round
#           (fake scores) with the critics the method routes to them - standard-<pack>, standard-<system> for a _generic option, the
#           receiving system's critic for an architect claim - and the architect's client assumptions sit on their cell / package only
# Every variant: the workbook's totals are recomputed with fixtures/xl_eval.py and compared with the totals the fixture defines, before
# and after a parameter edit (a size of the T-shirt mapping and a surcharge); the customer edition passes the hygiene layer.
# With LANG_ != de the `starts` and `scenarios` variants run a second time in German. Env from engine/smoke_test.sh: TOOLS, PLUGIN, TMP, LANG_
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; run() { python3 "$TOOLS/$1.py" "${@:2}"; }; mrun() { python3 "$HERE/tools/$1.py" "${@:2}"; }
export PLUGIN_ROOT="$PLUGIN"; export PATH="$PLUGIN/scripts:$PATH"

refs() {   # the fixture's reference rows (PS-7-001 ...) with titles in the deliverable language
  python3 - "$1" <<'PY'
import json, subprocess, sys, os
T = os.environ["TOOLS"]; lang = sys.argv[1]
for r in json.load(open("fixture_refs.json")):
    out = subprocess.run([sys.executable, f"{T}/reference.py", "add", "--fact", r["fact"], "--applies", r["applies"], "--url", r["url"], "--provenance", "researcher"], capture_output=True, text=True, check=True).stdout
    pid = out.split("added ")[1].split()[0]
    subprocess.run([sys.executable, f"{T}/reference.py", "title", pid, "--title", r["title"], "--summary", r["summary"], "--lang", lang], capture_output=True, text=True, check=True)
print("reference rows added")
PY
}

classification() {   # scenarios: draft -> the agent's proposal (fixture) -> lead workbook -> approve -> apply
  run status next | grep -q "HOLD before \`bash \"$PLUGIN/scripts/dbcx\" discover\`: row classification"
  mrun classify draft | grep -q "5 candidate(s)"; test -f work/classification.json   # 4 from the code analysis + the undecided derived row NR-003
  run md_to_json classification analysis/classification.md >/dev/null
  mrun classify draft | grep -q "status proposed"; test -f work/classification.xlsx
  python3 - <<'PY'
import openpyxl
wb = openpyxl.load_workbook("work/classification.xlsx"); ws = wb.worksheets[0]; h = [c.value for c in ws[1]]
k = next(i for i, x in enumerate(h) if str(x).startswith(("Klasse", "Class"))) + 1; c = next(i for i, x in enumerate(h) if str(x).startswith(("Kommentar", "Comment"))) + 1
assert [ws.cell(r, k).value for r in range(2, 7)] == ["refactoring", "tech-migration", "client-row", "drop", "client-row"], [ws.cell(r, k).value for r in range(2, 7)]
ws.cell(5, c).value = "agreed: carried by the project setup"; wb.save("work/classification.xlsx")   # the lead's edit
PY
  if mrun classify apply >/dev/null 2>&1; then echo "apply before approve"; exit 1; fi
  mrun classify approve --by "Fixture Lead" | grep -q "approved by Fixture Lead"
  mrun classify apply | grep -q "TM-01, RF-01"
  python3 - <<'PY'
import json
r = {x["id"]: x for x in json.load(open("state/requirements.json"))["requirements"]}
assert r["TM-01"]["row_class"] == "tech-migration" and r["TM-01"]["applies_to"] == ["brownfield", "greenfield"] and r["TM-01"]["links"] == ["FR-009", "FR-010"], r["TM-01"]
assert r["RF-01"]["row_class"] == "refactoring" and r["RF-01"]["applies_to"] == ["brownfield"] and r["RF-01"]["source"] == ["HO-customization-depth#shopnotify"], r["RF-01"]
st = json.load(open("work/classification.json")); assert st["status"] == "applied" and st["approved_by"] == "Fixture Lead" and st["rows"] == ["TM-01", "RF-01"], st
print("classification ok")
PY
  if run status next | grep -q "HOLD before"; then echo "status next still holds after apply"; exit 1; fi
}

variant() {   # variant <dir> <none|starts|packs|scenarios> <lang>
  local D="$1" V="$2" L="$3" PK="_generic"; [ "$V" = packs ] && PK="sap-commerce"
  echo "=== tech-fit-estimation / $V ($L)"
  mkdir -p "$D"; cd "$D"
  run init run --method tech-fit-estimation --dir "$D" --knowledge platform=$PK --lang "$L" --client "Fixture Retail GmbH" --consultancy "Fixture Consulting" --title "Fit estimation fixture" >/dev/null
  python3 "$HERE/fixtures/make_fixture.py" "$D" --variant "$V" >/dev/null
  run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
  run check_fill --quiet
  if [ "$V" = starts ] || [ "$V" = scenarios ]; then   # setup order (plan.md): handover imports and the client's answers BEFORE intake
    for typ in requirements-coverage target-readiness customization-depth code-inventory client-assumptions; do run handover import "ho/$typ.json" >/dev/null; done
    run questions import-handover input/handover/client-assumptions.json | grep -q "2 new assumption"
  fi
  run requirements_to_json | grep -q "14 requirements"
  [ "$V" = scenarios ] && python3 "$HERE/fixtures/make_fixture.py" "$D" --variant "$V" --derived-rows >/dev/null   # the requirements-set's code-proposed rows (decided in run.json)
  run intake --no-questions >/dev/null; test -f docs/INTAKE.md
  run status init >/dev/null
  refs "$L" >/dev/null
  if [ "$V" = starts ]; then   # a code-analysis handover holds discover for the row classification - this plain variant skips it
    run status next | grep -q "HOLD before \`bash \"$PLUGIN/scripts/dbcx\" discover\`: row classification"
    if mrun discover >/dev/null 2>&1; then echo "discover ran before the classification"; exit 1; fi
    mrun classify skip --reason "fixture: the plain variant has no classification" >/dev/null
  fi
  [ "$V" = scenarios ] && classification
  mrun discover >/dev/null; run plan_waves | grep -q "wave 1"
  for f in analysis/scopes/epic-01.md analysis/scopes/epic-02.md; do run md_to_json estimation "$f" >/dev/null; done
  run md_to_json summary analysis/consolidated/SUMMARY.md >/dev/null
  for s in epic-01 epic-02 SUMMARY; do for c in analysis/gauntlet/$s/round1-*.md; do run md_to_json critic "$c" >/dev/null; done; done
  run md_to_json gate analysis/gate/round1-cto.md >/dev/null
  run questions import epic-02 | grep -q "1 new assumption"   # the reading taken for FR-024 becomes a client-directed assumption
  for s in epic-01 epic-02 SUMMARY; do
    run extract_claims $s --round 1 >/dev/null
    run evidence check $s >/dev/null
    run score_aggregate $s 1 --dry-run | grep -q '"passed": true'
    run score_aggregate $s 1 >/dev/null
  done
  grep -q "0/" <(run evidence check epic-01) || { echo "evidence of epic-01 does not resolve completely"; cat analysis/gauntlet/epic-01/dangling-evidence.md; exit 1; }
  run status scope epic-01 '{"status": "final", "wave": 1}' >/dev/null; run status scope epic-02 '{"status": "final", "wave": 1}' >/dev/null
  run build_excel --all >/dev/null
  run lint_deliverable >/dev/null
  run lint_deliverable --standalone --all --round 1 >/dev/null || { run lint_deliverable --standalone --all --fix-list | tail -40; exit 1; }
  VARIANT="$V" LANGV="$L" python3 "$HERE/fixtures/smoke_check.py"
}

# ---- none: the full chain in the deliverable language
G="$TMP/tfe-none"; variant "$G" none "$LANG_"; cd "$G"
python3 - <<'PY'
import json
s = json.load(open("state/scopes.json"))["scopes"]
assert set(s) == {"epic-01", "epic-02"}, s
assert s["epic-01"]["size"] == 9 and s["epic-01"]["light"] is False, s["epic-01"]
assert s["epic-02"]["size"] == 5 and s["epic-02"]["light"] is True, s["epic-02"]
assert all(not any(c.isupper() for c in n) for n in s), "chunk names must stay neutral lower-case (hook H3 blocks vendor queries containing a scope name)"
d = json.load(open("analysis/scopes/epic-01.json"))
assert d["status"] == "final" and {r["rid"] for r in d["estimation"]} >= {"FR-009@target", "FR-009@1@target", "FR-009@3@target"}, sorted(r["rid"] for r in d["estimation"])[:8]
print("chunking and row ids ok")
PY
grep -q "Generic target platform 2.0" docs/PLAN.md
run knowledge sources >/dev/null
run evidence bases | grep -q requirements; run evidence bases | grep -q vendor-docs
if run md_to_json critic analysis/gauntlet/epic-01/round1-client.md >/dev/null 2>&1; then echo "closed-file guard FAILED"; exit 1; else echo "closed-file guard ok"; fi
run gate_aggregate 1 >/dev/null
run status show | grep -q "epic-01"
# ---- briefs for every role
run render context analyst epic-01 | grep -q "SCOPE KIND: estimation"
run render brief analyst epic-01 --out >/dev/null
B=analysis/briefs/analyst-epic-01.md; test -f $B
grep -q "EVIDENCE BASES YOU MAY READ" $B; grep -q "ROLE INSTRUCTIONS" $B; grep -q "YOUR REQUIREMENTS" $B
grep -q "RELATED REQUIREMENTS OWNED BY OTHER CHUNKS" $B; grep -q "FR-013" $B; grep -q "TECHNOLOGY NOTES" $B; grep -q "TR-01" $B
grep -q "### TARGET target" $B; grep -q "SIZE MAPPING" $B; grep -q "ASSUMPTION RULE" $B; grep -q "NO DOUBLE COUNTING" $B
if grep -q "^## NARROW CODE LOOKUP" $B; then echo "a greenfield-only run must not get the lookup rules"; exit 1; fi
if grep -qE '\{(target|estimation|unit|engagement|deliverables)\.' $B; then echo "UNRESOLVED placeholder in the analyst brief"; grep -nE '\{(target|estimation|unit|engagement|deliverables)\.' $B; exit 1; fi
run render brief analyst epic-02 --out >/dev/null; grep -q "LIGHT PASS: yes" analysis/briefs/analyst-epic-02.md
run render brief critic client epic-01 1 --out >/dev/null; grep -q "^MODEL:" analysis/briefs/critic-client-epic-01-r1.md
grep -q "THE REQUIREMENTS THIS SCOPE ESTIMATES" analysis/briefs/critic-client-epic-01-r1.md; grep -q "lead developer" analysis/briefs/critic-client-epic-01-r1.md
run render brief critic standard epic-01 1 --out >/dev/null; grep -q "### TARGET target" analysis/briefs/critic-standard-epic-01-r1.md
run render brief critic standard SUMMARY 1 --out | grep -qE "MODEL (opus|sonnet|haiku|fable)\b"
run render digest SUMMARY >/dev/null; grep -q "citing claims" analysis/consolidated/digest-SUMMARY.md; grep -q "Requirements without an estimation row" analysis/consolidated/digest-SUMMARY.md
run render brief consolidate SUMMARY --out >/dev/null; grep -q "DIGEST" analysis/briefs/consolidate-summary.md; grep -q "DEVELOPMENT PER CHUNK AND OPTION" analysis/briefs/consolidate-summary.md
run render brief postpass epic-01 | grep -q "POST-PASS TEXT CORRECTION"
run render brief research | grep -q "RESEARCH TOPICS"
run render brief progress | grep -q "progress-reporter"
# ---- questions, learnings, progress
run questions add epic-01 epic-02 "Does the nightly ERP delivery include the spare part numbers?" >/dev/null
run questions list --client | grep -q client
run learn add --section A --title "fixture learning" --what "x" --evidence "y" --generalises "z" --proposal "p" --touches "methods/tech-fit-estimation" | grep -q "L-001"
run progress | grep -q "PROGRESS"
# ---- interim, internal, gate
run build_excel D1 --interim >/dev/null; ls work/interim/*/Fit_Estimation_Generic.xlsx >/dev/null
python3 -c "import openpyxl,glob; wb=openpyxl.load_workbook(glob.glob('work/interim/*/Fit_Estimation_Generic.xlsx')[0]); assert wb.sheetnames[0]=='INTERIM', wb.sheetnames"
run build_excel D1 --internal >/dev/null; test -f work/internal/Fit_Estimation_Generic_Review_Notes.xlsx
test ! -d deliverables/interim && test ! -d deliverables/internal
run kb add --text "Every scope of this fixture reads the same nightly export." --topic fixture-export --topic-summary "the shared nightly export" --applies-to '*' --type decision | grep -q "KB-001"
run render brief gate cto 1 --out | grep -q "gate-cto"
if grep -q "## KNOWLEDGE BASE" analysis/briefs/gate-cto-r1.md; then echo "knowledge base block in a gate brief"; exit 1; fi   # 0.10: gate roles get no KNOWLEDGE BASE block
run render brief analyst epic-01 --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/analyst-epic-01.md
run render brief critic client epic-01 1 --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/critic-client-epic-01-r1.md
run gate questions cfo | grep -q "F1"
run status set phases.preflight.status '"done"' >/dev/null
run status next | grep -q "excel_build"
run status set phases.excel_build.status '"done"' >/dev/null
run status next | grep -q "final_gate"
run handover export fit-estimation | grep -q released; run handover list | grep -q fit-estimation
run status verify --brief || true
# ---- hooks: disjoint evidence bases, no client data to external services, no spawn without a brief
python3 - <<'PY'
import json, subprocess, sys, os
H = os.path.join(os.environ["PLUGIN"], "hooks", "dbcx_hook.py"); cwd = os.getcwd()
def hook(payload): return subprocess.run([sys.executable, H, "PreToolUse"], input=json.dumps(dict(payload, cwd=cwd)), capture_output=True, text=True).stdout
corpus = os.path.join(cwd, "corpus", "text", "SRC-001.md")
assert "deny" in hook({"tool_name": "Read", "tool_input": {"file_path": corpus}, "agent_name": "critic-standard-epic-01"}), "standard critic corpus read not denied"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": corpus}, "agent_name": "critic-client-epic-01"}), "client critic corpus read denied"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": corpus}, "agent_name": "analyst-epic-01"}), "analyst corpus read denied"
assert "deny" in hook({"tool_name": "Write", "tool_input": {"file_path": os.path.join(cwd, "input", "requirements", "x.xlsx")}}), "write into the requirements base not denied"
assert "deny" in hook({"tool_name": "WebSearch", "tool_input": {"query": "Fixture Retail GmbH product comparison"}}), "client name not denied"
assert "deny" in hook({"tool_name": "Agent", "tool_input": {"subagent_type": "dbcx-agentic-loop:analyst", "prompt": "estimate it", "model": "opus"}}), "spawn without brief not denied"
print("hook smoke ok")
PY

# ---- starts: brownfield + greenfield on one pack
S="$TMP/tfe-starts"; variant "$S" starts "$LANG_"; cd "$S"
run render brief analyst epic-01 --out >/dev/null; B=analysis/briefs/analyst-epic-01.md
grep -q "### TARGET brownfield" $B; grep -q "### TARGET greenfield" $B; grep -q "^## NARROW CODE LOOKUP" $B; grep -q "HO-requirements-coverage#FR-009" $B
run render brief critic client epic-01 1 --out >/dev/null; grep -q "LOOKUP SAMPLE" analysis/briefs/critic-client-epic-01-r1.md
run render brief consolidate SUMMARY --out >/dev/null; grep -q "HO-target-readiness#MT-035" analysis/briefs/consolidate-summary.md
python3 - <<'PY'
import json, subprocess, sys, os
H = os.path.join(os.environ["PLUGIN"], "hooks", "dbcx_hook.py"); cwd = os.getcwd()
def hook(payload): return subprocess.run([sys.executable, H, "PreToolUse"], input=json.dumps(dict(payload, cwd=cwd)), capture_output=True, text=True).stdout
repo = os.path.join(cwd, "client-repo", "src", "shopcore", "src", "com", "shop", "shopcore", "ShopcoreService.java")
vendor = next(os.path.join(d, f) for d, _, fs in os.walk(os.path.join(cwd, "reference", "vendor-code")) for f in fs)
assert "deny" in hook({"tool_name": "Read", "tool_input": {"file_path": repo}, "agent_name": "critic-standard-epic-01"}), "standard critic reads the client repository"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": repo}, "agent_name": "analyst-epic-01"}), "analyst cannot read the client repository"
assert "deny" in hook({"tool_name": "Read", "tool_input": {"file_path": vendor}, "agent_name": "critic-client-epic-01"}), "client critic reads vendor code"
assert "deny" not in hook({"tool_name": "Read", "tool_input": {"file_path": vendor}, "agent_name": "critic-standard-epic-01"}), "standard critic cannot read vendor code"
assert "deny" in hook({"tool_name": "Write", "tool_input": {"file_path": repo}}), "write into the client repository not denied"
print("hook smoke (client-repo, vendor-code) ok")
PY

# ---- packs: two technologies, one standard critic per pack
P="$TMP/tfe-packs"; variant "$P" packs "$LANG_"; cd "$P"
run render brief critic standard-spryker epic-01 1 --out >/dev/null; grep -q "AGENT NAME: critic-standard-spryker-epic-01" analysis/briefs/critic-standard-spryker-epic-01-r1.md
grep -q "Spryker" analysis/briefs/critic-standard-spryker-epic-01-r1.md

# ---- scenarios: row classes, integration platform, scenario totals, critic grounds
scenario_checks() {   # in the run folder of a scenarios variant
  run render brief analyst epic-02 --out >/dev/null; B=analysis/briefs/analyst-epic-02.md
  grep -q "## BASELINE (today's shop - the real scope of every requirement" $B; grep -q "TODAY'S SHOP" $B; grep -q "## ROW CLASSES" $B; grep -q "## INTEGRATION PLATFORM EFFORT (Integration Suite)" $B
  grep -q "row_class" $B; grep -q "HO-customization-depth#shopnotify" $B
  run render brief analyst epic-01 --out >/dev/null; grep -q "CL-03 (classification: part of this requirement" analysis/briefs/analyst-epic-01.md
  grep -q "NR-001 (derived requirement of the code analysis, merged into this requirement - part of its real scope, decision A-01)" analysis/briefs/analyst-epic-01.md
  grep -q "NR-003 (derived requirement of the code analysis, merged into this requirement - part of its real scope)" analysis/briefs/analyst-epic-01.md   # decided in the classification; grep -q "DESCRIPTION GAP" analysis/briefs/analyst-epic-01.md
  run render brief critic client epic-02 1 --out >/dev/null; grep -q "standard-dispute" analysis/briefs/critic-client-epic-02-r1.md; grep -q "expert of Generic target platform" analysis/briefs/critic-client-epic-02-r1.md
  run render brief consolidate SUMMARY --out >/dev/null; grep -q "## FIXED PHASE SEEDS" analysis/briefs/consolidate-summary.md; grep -q "(Migration + Refactoring): option brownfield" analysis/briefs/consolidate-summary.md
  run render brief classify --out | grep -q "consolidate-classification"; grep -q "## CANDIDATES" analysis/briefs/consolidate-classification.md
  run gate questions product_owner | grep -q "P4"
  python3 - <<'PY'
import json, os, re, shutil, subprocess, sys
T = os.environ["TOOLS"]; tmp = "work/mutated"; os.makedirs(tmp, exist_ok=True)
def conv(kind, src, edit, want):
    text = open(src, encoding="utf-8").read(); new = edit(text); assert new != text, (src, "edit changed nothing")
    fp = os.path.join(tmp, os.path.basename(src)); open(fp, "w", encoding="utf-8").write(new)
    r = subprocess.run([sys.executable, f"{T}/md_to_json.py", kind, fp, "--out", fp[:-3] + ".json"], capture_output=True, text=True)
    assert r.returncode != 0 and want in r.stdout, (want, r.stdout[-1500:])
sc = json.load(open("state/scopes.json"))["scopes"]; assert not {"NR-001", "NR-002", "NR-003"} & {i for s in sc.values() for i in s["meta"]["req_ids"]}, sc   # decided rows (run.json or the classification) are not chunked
E1 = "analysis/scopes/epic-01.md"; r10 = next(l for l in open(E1, encoding="utf-8") if l.startswith("| FR-010 | brownfield |"))
conv("estimation", E1, lambda t: t.replace(r10, r10 + r10.replace("| FR-010 | brownfield |", "| NR-001 | brownfield |")), "is merged into FR-010")
E2 = "analysis/scopes/epic-02.md"
row = next(l for l in open(E2, encoding="utf-8") if l.startswith("| RF-01 | brownfield |"))
conv("estimation", E2, lambda t: t.replace(row, row + row.replace("| RF-01 | brownfield |", "| RF-01 | greenfield |").replace("convert-to-standard", "custom")), "exists for brownfield options only")
der = next(l for l in open(E2, encoding="utf-8") if l.startswith("| TR-02 | greenfield |"))
cells = der.split(" | "); i = next(k for k, c in enumerate(cells) if c.startswith(("Bestellabbildung", "order mapping")))
conv("estimation", E2, lambda t: t.replace(der, " | ".join(cells[:i] + ["the OrderExportService is changed in line 56"] + cells[i + 1:])), "class name 'OrderExportService'")
conv("estimation", E2, lambda t: t.replace(der, " | ".join(cells[:i] + ["the mapping in src/shoperp/impl/OrderMapper.java:56 is extended"] + cells[i + 1:])), "path:line")
conv("estimation", E2, lambda t: t.replace(row, row.replace("| FR-014 |", "|  |")), "saved_size and saves go together")
C2 = "analysis/gauntlet/epic-02/round1-client.md"
c2 = next(l for l in open(C2, encoding="utf-8") if l.startswith("| C-epic-02-002 |"))
conv("critic", C2, lambda t: t.replace(c2, re.sub(r"^\| C-epic-02-002 \| \d+ \|", "| C-epic-02-002 | 5 |", c2).replace("| size-plausibility |", "|  |")), "without a ground")
res = json.load(open("analysis/gauntlet/epic-02/round1-result.json"))
assert res["passed"] and [x["claim_id"] for x in res["routed"]] == ["C-epic-02-001"] and res["routed"][0]["to"] == ["standard"], res.get("routed")
cl = json.load(open("analysis/gauntlet/epic-02/round1-client.json")); rows = [x for x in cl["scores"] if x["claim_id"] != "C-epic-02-001"]
assert [x["claim_id"] for x in cl["disputes"]] == ["C-epic-02-001"] and "C-epic-02-001" not in {x["claim_id"] for x in cl["scores"]}, cl
assert res["critics"]["client"]["avg"] == int(sum(x["score"] for x in rows) / len(rows) * 100) / 100 and res["critics"]["client"]["min"] >= 8 and res["critics"]["client"]["disputed"] == ["C-epic-02-001"], res["critics"]["client"]
assert "Disputes routed (1)" in open("analysis/gauntlet/epic-02/round1-issues.md", encoding="utf-8").read()
print("scenario refusals and dispute routing ok")
PY
}
S3="$TMP/tfe-scenarios"; variant "$S3" scenarios "$LANG_"; cd "$S3"; scenario_checks
if [ "$LANG_" != de ]; then S2="$TMP/tfe-starts-de"; variant "$S2" starts de; S4="$TMP/tfe-scenarios-de"; variant "$S4" scenarios de; cd "$S4"; scenario_checks; fi
# ---- systems: the real flow of a system-mode run, two scenarios and one
register() {   # every chunk of state/WAVES.json that state/STATUS.json does not hold yet, in the wave plan_waves gave it
  python3 - <<'PY'
import json, subprocess, sys, os
st = json.load(open("state/STATUS.json")).get("scopes") or {}
for w in json.load(open("state/WAVES.json"))["waves"]:
    for m in w["members"]:
        if m["name"] not in st: subprocess.run([sys.executable, os.path.join(os.environ["TOOLS"], "status.py"), "scope", m["name"], json.dumps({"wave": w["wave"], "status": "open"})], check=True, capture_output=True)
PY
}
critic_round() {   # critic_round <scope>: gauntlet round 1 of a system-mode scope with the critics the method routes to it (fake scores 8 / 9); logs the critic set
  local n="$1" cs c
  run extract_claims "$n" --round 1 >/dev/null
  cs="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import common; print(" ".join(common.scope_critics(sys.argv[2])))' "$TOOLS" "$n")"
  for c in $cs; do python3 "$HERE/fixtures/make_fixture.py" "$PWD" --variant systems --critic "$n" "$c" >/dev/null; run md_to_json critic "analysis/gauntlet/$n/round1-$c.md" >/dev/null; done
  run score_aggregate "$n" 1 --dry-run | grep -q '"passed": true' || { echo "critic round of $n did not pass"; run score_aggregate "$n" 1 --dry-run | tail -20; exit 1; }
  run score_aggregate "$n" 1 >/dev/null; echo "$n: $cs" >> work/critic-routing.txt
}
convert_open() {   # converts every Markdown analysis of a registered chunk that is not converted yet, runs its critic round and closes the chunk (final, passed)
  for f in analysis/scopes/*.md; do
    n="$(basename "$f" .md)"; [ -f "analysis/scopes/$n.json" ] && continue
    run md_to_json estimation "$f" >/dev/null; critic_round "$n"; run status scope "$n" '{"status": "final", "passed": true}' >/dev/null
  done
}
routing_check() {   # every system chunk was scored by the client critic and its system option's standard critic (standard-<pack>, a _generic option standard-<system>), the architect batch by the receiving systems' critics
  python3 - "$1" <<'PY'
import json, sys
got = dict(l.split(": ", 1) for l in open("work/critic-routing.txt").read().splitlines()); got = {k: v.split() for k, v in got.items()}
want = {"commerce-sapcc-01": ["client", "standard-sap-commerce"], "cdc-01": ["client", "standard-cdc"], "middleware-01": ["client", "standard-middleware"], "cdc-02": ["client", "standard-cdc"]}
if sys.argv[1] == "multi": want.update({"commerce-shopware-01": ["client", "standard-commerce"], "commerce-sapcc-02": ["client", "standard-sap-commerce"]})
else: want = {k.replace("commerce-sapcc-", "commerce-"): v for k, v in want.items()}; want["commerce-02"] = ["client", "standard-sap-commerce"]
for k, v in want.items(): assert got.get(k) == v, (k, got.get(k), v)
arch = json.load(open("analysis/gauntlet/ARCHITECT-1/claims.json"))["claims"]; by = {c["target"].split("#")[1]: c["critics"] for c in arch}
assert by["TA-01@cdc@cdc"] == ["client", "standard-cdc"] and by["TA-02@commerce@middleware"] == ["client", "standard-middleware"] and by["TA-03@commerce@SYS-BTP"] == ["client"], by   # a landscape receiver has no standard critic
res = json.load(open("analysis/gauntlet/commerce-sapcc-01/round1-result.json") if sys.argv[1] == "multi" else open("analysis/gauntlet/commerce-01/round1-result.json"))
assert res["passed"] and set(res["critics"]) == {"client", "standard-sap-commerce"}, res["critics"]
print(f"critic routing ok: {len(got)} gauntlet scopes, standard-<pack> and standard-<system> critics, architect claims by the receiving system")
PY
}
systems_variant() {   # systems_variant <dir> <multi|single> <lang>
  local D="$1" MODE="$2" L="$3" V=systems; [ "$2" = single ] && V=systems-single
  echo "=== tech-fit-estimation / $V ($L)"
  mkdir -p "$D"; cd "$D"
  run init run --method tech-fit-estimation --dir "$D" --knowledge platform=_generic --lang "$L" --client "Fixture Retail GmbH" --consultancy "Fixture Consulting" --title "Fit estimation fixture" >/dev/null
  python3 "$HERE/fixtures/make_fixture.py" "$D" --variant systems >/dev/null
  python3 "$HERE/fixtures/make_fixture.py" "$D" --variant systems --book-inputs "$MODE" >/dev/null
  run md_to_json --generate >/dev/null
  run requirements_to_json | grep -q "requirements ->"
  mrun landscape_import input/landscape/systemlandschaft.csv --map "id=System-ID,name=Systemname,kind=Typ,description=Beschreibung,owner=Verantwortlich,aliases=Aliasse" >/dev/null
  run status init >/dev/null
  refs "$L" >/dev/null
  mrun impact plan >/dev/null; run md_to_json triage analysis/triage/TRIAGE.md >/dev/null; mrun impact apply >/dev/null   # scope step: the triage agent's file (fixture)
  mrun discover >/dev/null; run plan_waves >/dev/null; register                                                                # wave 1 (+ the dependent middleware after it)
  python3 "$HERE/fixtures/make_fixture.py" "$D" --variant systems --gaps >/dev/null; convert_open                             # wave-1 analyses, two report gaps
  mrun architect plan | grep -q "ARCHITECT-1"; run md_to_json architect analysis/architect/ARCHITECT-1.md >/dev/null; mrun architect apply >/dev/null
  critic_round ARCHITECT-1                                                                                                     # the architect's claims by the receiving systems' critics
  run questions import ARCHITECT-1 >/dev/null                                                                                  # the two client assumptions (A-nn)
  mrun discover --pickup | grep -q "external input cell(s), no chunk: TA-03@SYS-BTP"; run plan_waves >/dev/null; register     # follow-ups in wave 2
  python3 "$HERE/fixtures/make_fixture.py" "$D" --variant systems --wave2 >/dev/null; convert_open                            # wave 2: follow-ups + the routed middleware packages
  python3 "$HERE/fixtures/make_fixture.py" "$D" --variant systems --consolidate "$MODE" >/dev/null; run md_to_json summary analysis/consolidated/SUMMARY.md >/dev/null
  routing_check "$MODE"
  run build_excel --check D1 >/dev/null
  run build_excel --all >/dev/null
  run lint_deliverable --standalone --all >/dev/null || { run lint_deliverable --standalone --all --fix-list | tail -40; exit 1; }
  VARIANT="$V" LANGV="$L" python3 "$HERE/fixtures/systems_check.py"
  if [ "$MODE" = single ]; then run gate questions cfo | grep -q "F4"; else run gate questions cfo | grep -q "F5"; fi   # key questions per mode (method.json gate.key_questions_when)
}
systems_variant "$TMP/tfe-systems" multi "$LANG_"; systems_variant "$TMP/tfe-systems-single" single "$LANG_"
if [ "$LANG_" != de ]; then systems_variant "$TMP/tfe-systems-de" multi de; systems_variant "$TMP/tfe-systems-single-de" single de; fi
echo "TECH-FIT-ESTIMATION SMOKE OK"
