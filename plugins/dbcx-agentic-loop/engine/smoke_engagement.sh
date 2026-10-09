#!/usr/bin/env bash
# Engine-level smoke: engagement folder > two runs, corpus index, handover export/import, learn export, project/run resolution.
# Uses the code-analysis generic fixture as the producing run. Env: TOOLS, PLUGIN, TMP
set -euo pipefail
run() { python3 "$TOOLS/$1.py" "${@:2}"; }; export PATH="$PLUGIN/scripts:$PATH"
E="$TMP/engagement"; mkdir -p "$E"; cd "$E"
echo "=== engagement"
run init engagement --dir "$E" --client "Fixture Shop GmbH" --consultancy "Fixture Consulting" --title "Fixture programme" --context "B2B spare parts, toy data" --lang en >/dev/null
test -f engagement.json && test -d runs && test -d corpus
mkdir -p input/2026-09-workshop; printf "# Workshop notes\n\nThe shop must show installed equipment per customer unit.\n\nOrders are transferred to the ERP nightly.\n" > input/2026-09-workshop/notes.md
python3 - <<'PY'
import openpyxl; wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Systems"; ws.append(["System", "Owner"]); ws.append(["ERP", "IT"]); ws.append(["Shop", "eCom"]); wb.save("input/2026-09-workshop/systems.xlsx")
PY
run corpus index | grep -q "2 sources"
run corpus list | grep -q "SRC-001"
run corpus grep "equipment" | grep -q "SRC-00"
run evidence resolve "SRC-001#L1" "SRC-002#Systems!R2" "SRC-009#p1" | grep -c "^OK" | grep -q "^2$"
echo "=== run A (producer)"
cd "$E/runs"; A="$E/runs/2026-09-code-analysis"
run init run --method code-analysis --dir "$A" --knowledge source=_generic,target=_generic >/dev/null
python3 "$PLUGIN/methods/code-analysis/fixtures/make_fixture.py" "$A" generic >/dev/null
cd "$A"; run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
grep -q "runs/2026-09-code-analysis" "$E/engagement.json"
run check_fill --quiet
grep -q "Fixture Shop GmbH" CLAUDE.md          # client inherited from engagement.json
run requirements_to_json >/dev/null; run status init >/dev/null
run md_to_json D3 analysis/consolidated/D3.md >/dev/null
run extract_claims D3 >/dev/null
run evidence bases | grep -q "reference.*engagement/reference"   # project-level reference dir
echo "=== question register, inbox, dashboard state"
run questions add D3 client "Is the nightly ERP transfer acceptable for order status? Options: A) yes, nightly is enough (recommended) B) no, near-real-time is required; proceeding under A" --effect "decides the integration pattern of the order flow" | grep -q "2 options"
run questions import D3 | grep -q imported
run questions list --json | python3 -c "import json,sys; q=json.load(sys.stdin); assert q[0]['options'][0]['recommended'] and q[0]['proceeding_under']=='A' and q[0]['kind']=='client_question', q[0]"
test -f state/QUESTIONS.json && grep -q "Q-D3-001" docs/questions/D3.md
run questions add orchestrator lead "Assumption taken: the legacy portal is out of scope" --kind assumption --option "A|confirm|no change" --option "B|overrule|one scope more" --recommend A | grep -q "A-orchestrator-001"
run inbox add answer '{"id":"Q-D3-001","option":"B","text":"","weight":"fact"}' | grep -q queued
run inbox next | grep -q "questions answer Q-D3-001"
run inbox apply next | grep -q APPLIED
run questions show Q-D3-001 | grep -q '"weight": "fact"'
run inbox add analyst_hint '{"scope":"D3","claim_id":"C-D3-001","text":"the nightly job table lists the transfer window"}' >/dev/null; run inbox apply next | grep -q "lead-hints-D3"
grep -q "nightly job table" analysis/briefs/lead-hints-D3.md
run inbox add critic_fact '{"scope":"D3","claim_id":"C-D3-001","critic":"standard","text":"vendor confirmed the nightly batch stays supported"}' >/dev/null; run inbox apply next | grep -q "score_aggregate D3"
grep -q "BINDING" analysis/briefs/lead-facts-D3.md && grep -q "lead" "$E/reference/platform-standard.md"
run inbox control pause | grep -q '"pause_requested": true'
(run status verify --brief || true) | grep -q PAUSE   # verify exits 1 while work is owed
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"dbcx-agentic-loop:analyst","prompt":"analysis/briefs/x.md","model":"opus"},"cwd":"'"$A"'"}' | python3 "$PLUGIN/hooks/dbcx_hook.py" PreToolUse | grep -q '"deny"'
run inbox control resume | grep -q '"pause_requested": false'
run inbox list | grep -c done | grep -q "^3$"
run progress --quiet; test -f state/PROGRESS.json; python3 -c "import json; p=json.load(open('state/PROGRESS.json')); assert 'analysts' in p and 'counts' in p"
run dashboard state | python3 -c "import json,sys; s=json.load(sys.stdin); assert s['questions'] and 'control' in s and 'analysts' in s and s['inbox']['total']==4, list(s)"
run dashboard state --scope D3 | grep -q claims_total
echo "=== run knowledge base"
run questions add D3 D4 "Does one order export feed both the coverage and the target API view?" --id Q-D3-90 >/dev/null
run questions answer Q-D3-90 "yes, one export feeds both" --by lead --weight fact | grep -q "KC-001: knowledge-base candidate (affects D3, D4)"
(run status verify --brief || true) | grep -q "knowledge-base candidate(s) open: KC-001"
if run kb add --text "x" --topic order-export --topic-summary "s" --applies-to D3 --type decision >/dev/null 2>&1; then echo "single-scope guard FAILED"; exit 1; fi
run kb promote KC-001 --text "One order export feeds the coverage and the target API view." --topic order-export --topic-summary "the order export" --applies-to D3,D4 | grep -q "KC-001 -> KB-001"
run kb show --scope D4 | grep -q "KB-001 · decision · fact"
run render brief consolidate D4 --out >/dev/null; grep -q "KB-001" analysis/briefs/consolidate-d4.md
sleep 1
run kb add --text "The order export runs nightly." --topic order-export --applies-to D3,D4 --type decision --by lead | grep -q "KB-002"
run kb pending consolidate-d4 | grep -q "KB-002"
run handover export requirements-coverage --force | grep -q released
test -f "$E/handover/manifest.json"
run learn add --section D --title "fixture learning" --what "x" --evidence "y" --generalises "z" --proposal "p" --touches "knowledge" >/dev/null
run learn repro L-001 --kind fact --fact "The nightly batch stays supported" --applies "2.0" --url https://example.org/batch --date 2026-09-30 | grep -q "knowledge fact package staged"
echo "=== engagement overrides"
run override add settings.json --set scoring.max_claims=30 --why "smoke" --learning L-001 | grep -q "O-001 -> overrides/settings.json"
python3 -c "import sys; sys.path.insert(0, '$TOOLS'); import common; assert common.project()['scoring']['max_claims'] == 30"
run override add briefs/consolidate.md --text "Smoke project note." --why "smoke" >/dev/null
run render brief consolidate D4 --out >/dev/null; grep -q "^## PROJECT NOTES" analysis/briefs/consolidate-d4.md && grep -q "Smoke project note." analysis/briefs/consolidate-d4.md
run override check | grep -q "2 override(s), none stale"
run status show | grep -q "engagement overrides: 2 active"
run override remove O-001 --why "smoke" >/dev/null; run override remove O-002 --why "smoke" >/dev/null; test ! -e "$E/overrides/settings.json"
echo "=== rulings intake and batched questions"
run status set phases.preflight.status '"done"' >/dev/null; run status set phases.inventory.status '"final"' >/dev/null; run status set phases.inventory.passed true >/dev/null
run status scope unit-a '{"wave": 1, "status": "open"}' >/dev/null
(run status next || true) | grep -q "RECOMMENDED before waves: rulings"   # engine default human_input.rulings optional: a line, no hold
run rulings draft | grep -q "3 topic(s) (target-version, customisation-policy, scope-boundaries)"
run rulings add "Which target version is binding?" --topic target-version --option "A|the latest release|standard upgrades" --option "B|the release before|fewer changes" --recommend A | grep -q "R-01"
run rulings add "Are custom checkout steps kept?" --topic customisation-policy --option "A|kept|x" --option "B|refactored to the standard|y" --recommend B | grep -q "R-02"
python3 -c "import json; r=json.load(open('run.json')); r['human_input']={'rulings': 'required', 'release': 'batched'}; json.dump(r, open('run.json', 'w'), indent=1)"
(run status next || true) | grep -q "NEXT: rulings before waves (human_input.rulings required) - 0 of 2"
cid=$(run inbox add answer '{"id":"R-01","option":"A","text":"","weight":"proposal"}' | awk '{print $2}'); run inbox apply "$cid" | grep -q "R-01: answered"
run rulings done | grep -q "1 answered, 1 working assumption(s)"
run kb show --core | grep -q "working-assumption · proposal"
(run status next || true) | grep -q "NEXT: scope unit-a"
run questions add unit-a client "Is the nightly export acceptable?" --option "A|yes|x" --option "B|no|y" --recommend A | grep -q "batched: 1 unreleased"
run dashboard state | python3 -c "import json,sys; s=json.load(sys.stdin); ids=[q['id'] for q in s['questions']]; assert 'Q-unit-a-001' not in ids and 'R-01' in ids, ids"
run status scope unit-a '{"status": "final"}' >/dev/null
(run status next || true) | grep -q "RELEASE QUESTION BATCH (wave gate / phase end): 1 unreleased question(s) from unit-a (1)"
run questions release --scope unit-a | grep -q "released 1 question(s)"
echo "=== run B (consumer)"
cd "$E/runs"; B="$E/runs/2026-10-code-analysis"
run init run --method code-analysis --dir "$B" --knowledge source=_generic,target=_generic --import requirements-coverage=requirements-coverage > "$TMP/initB.log" 2>&1; grep -q "imported requirements-coverage" "$TMP/initB.log"
cd "$B"; test -f input/handover/requirements-coverage.json && test -f input/handover/requirements-coverage.json.sha256
python3 -c "import json; r=json.load(open('run.json')); assert r['handover']['imports'][0]['provenance']=='released-run', r['handover']"
run status init >/dev/null; run status verify --brief >/dev/null || true
run evidence resolve "HO-requirements-coverage#FR-009" | grep -q "^OK"
run intake --no-questions | grep -q "handover requirements-coverage"
echo "=== learnings export"
run learn anonymise add shopcore --as ext | grep -q "<ext-1>"
run learn export --preview | grep -q "^## Residual risk"
run learn export --out "$TMP/learn-export.zip" | grep -q "1 learning(s) (1 upstream/unresolved with a reproduction package)"
python3 -c "import sys, zipfile; z = zipfile.ZipFile(sys.argv[1]); t = ' '.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist()).lower(); assert 'fixture shop' not in t and 'shopcore' not in t and '2026-09-code-analysis/l-001' in t and not any('anonymise' in n for n in z.namelist()), 'client label or mapped term in the export'" "$TMP/learn-export.zip"
(run learn harvest 2>&1 || true) | grep -q "retired"
(run pack cache-back 2>&1 || true) | grep -q "retired"
echo "ENGAGEMENT SMOKE OK"
