#!/usr/bin/env bash
# generic method self-test for a method without smoke.sh that declares scopes.discover "generic:<variant>".
#   The fixture is generated from the method's own files (engine/generic_fixture.py), then the chain of the method smokes runs:
#   init, inputs, the inventory phase (if any), discover, waves, Markdown conversion of every kind, gauntlet of one scope and of every
#   consolidation, gate aggregation,
#   every role brief, digests, workbook (--check, --all), table sheets with rows, lint, handover export.
# Usage: generic_smoke.sh <method dir>      Env from engine/smoke_test.sh: TOOLS, PLUGIN, TMP, LANG_
set -euo pipefail
: "${DBCX_PY:?run it through engine/smoke_test.sh (dbcx smoke), which picks the Python}"
[ "${DBCX_DRAWIO_IN_SMOKE:-}" = 1 ] || export DBCX_NO_DRAWIO_CLI=1 DBCX_NO_OPEN=1   # no draw.io desktop CLI (under a temp HOME it raises macOS keychain pop-ups) and no browser; DBCX_DRAWIO_IN_SMOKE=1 keeps both
MD="$1"; M="$(basename "$MD")"; run() { "$DBCX_PY" "$TOOLS/$1.py" "${@:2}"; }
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) PYSEP=";"; PYTOOLS="$(cygpath -w "$TOOLS")";; *) PYSEP=":"; PYTOOLS="$TOOLS";; esac   # Windows Python splits PYTHONPATH on ";" and reads Windows paths only
fx() { PYTHONPATH="$PYTOOLS${PYTHONPATH:+$PYSEP$PYTHONPATH}" "$DBCX_PY" "$PLUGIN/engine/generic_fixture.py" "$@"; }   # engine modules by name
export PATH="$PLUGIN/scripts:$PATH"

echo "=== $M (generic smoke)"
G="$TMP/$M"; mkdir -p "$G"; cd "$G"
run init run --method "$M" --dir "$G" --lang "$LANG_" --client "Fixture Client GmbH" --consultancy "Fixture Consulting" --title "Example run of $M" >/dev/null
fx inputs "$G"
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
if [ -f requirements_mapping.json ]; then run requirements_to_json; fi
run intake --no-questions >/dev/null
run status init
run reference add --fact "Example standard: the published norm the example cites" --applies "example" --url "https://docs.example.invalid/standard" --provenance researcher | grep "added PS-7-001" >/dev/null
run reference title PS-7-001 --title "Example standard" --summary "The published norm the example cites." --lang "$LANG_" >/dev/null
run evidence bases >/dev/null
INV=$("$DBCX_PY" -c "import json; m = json.load(open('$MD/method.json')); print((m.get('inventory') or {}).get('scope', ''))")
GSC=$("$DBCX_PY" -c "import json; print(' '.join(json.load(open('$MD/method.json')).get('consolidations') or {}))")

# ---- the inventory phase first (its passed unit table is the source of generic:inventory)
if [ -n "$INV" ]; then
  fx inventory "$G" > fixture_inventory.txt
  while read -r k f; do run md_to_json "$k" "$f" >/dev/null; done < fixture_inventory.txt
  run extract_claims "$INV" >/dev/null
  run score_aggregate "$INV" 1 | grep '"passed": true' >/dev/null || { echo "gauntlet of $INV did not pass"; exit 1; }
  run render handover >/dev/null
fi

# ---- scopes from the generic discover (dbcx discover resolves it from method.json scopes.discover)
"$DBCX_PY" "$PLUGIN/engine/dbcx.py" discover
run plan_waves | grep "wave 1" >/dev/null
SCOPES=$("$DBCX_PY" -c "import json; print(' '.join(k for k, v in json.load(open('state/scopes.json'))['scopes'].items() if not v.get('skip')))")
for u in $SCOPES; do run status scope "$u" '{"wave": 1, "status": "open"}' >/dev/null; done
S1="${SCOPES%% *}"

# ---- Markdown -> JSON for every document of the fixture
fx analyses "$G" > fixture_files.txt
while read -r k f; do run md_to_json "$k" "$f" >/dev/null; done < fixture_files.txt

# ---- gauntlet: the first scope and every consolidation
for x in $S1 $GSC; do
  run extract_claims "$x" >/dev/null
  run score_aggregate "$x" 1 | grep '"passed": true' >/dev/null || { echo "gauntlet of $x did not pass"; exit 1; }
done
run status verify --brief | grep "STATUS agrees with disk" >/dev/null
run gate_aggregate 1 >/dev/null

# ---- briefs for every role + the digests
P1=$("$DBCX_PY" -c "import json; print((json.load(open('run.json')).get('scoring') or {}).get('gate_personas', ['cto'])[0])")
run render brief analyst "$S1" --out >/dev/null
run render brief critic client "$S1" 1 --out >/dev/null
stdc() { PYTHONPATH="$PYTOOLS${PYTHONPATH:+$PYSEP$PYTHONPATH}" "$DBCX_PY" -c "import sys, common; print(' '.join(c for c in common.scope_critics(sys.argv[1]) if c != 'client'))" "$1"; }   # every standard critic of the scope (declared ones: standard-<id>)
for c in $(stdc "$S1"); do run render brief critic "$c" "$S1" 1 --out >/dev/null; done
for x in $GSC; do run render digest "$x" >/dev/null; run render brief consolidate "$x" --out >/dev/null; for c in $(stdc "$x"); do run render brief critic "$c" "$x" 1 --out >/dev/null; done; done
if [ -n "$INV" ]; then run render brief inventory --out >/dev/null; run render brief critic client "$INV" 1 --out >/dev/null; fi
run render brief postpass "$S1" >/dev/null
run render brief progress >/dev/null
run render brief research >/dev/null
run progress >/dev/null

# ---- workbook
run build_excel --check --all | tail -1
run build_excel --all
fx check "$G"
run render brief gate "$P1" 1 --out >/dev/null
run lint_deliverable
run lint_deliverable --standalone --all --round 1
for t in $("$DBCX_PY" -c "import json; print(' '.join(p['type'] for p in (json.load(open('$MD/method.json')).get('artefacts') or {}).get('produces', [])))"); do
  run handover export "$t" --force | grep released >/dev/null
done
echo "GENERIC SMOKE OK ($M)"
