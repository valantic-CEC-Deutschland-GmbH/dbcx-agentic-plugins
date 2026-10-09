#!/usr/bin/env bash
# Plugin self-test: runs every method's smoke.sh (methods/<m>/smoke.sh) in throw-away folders under a temp dir.
# Usage: dbcx smoke [method|all] [tmpdir] [de|en]        Never touches the plugin's own folders or any real project.
# An own method: DBCX_METHOD_DIR=<engagement>/methods/<m> (set by `dbcx smoke <m>` inside the engagement); its toy runs stay in the tmpdir.
set -euo pipefail
ENGINE="$(cd "$(dirname "$0")" && pwd)"; export PLUGIN="$(dirname "$ENGINE")"; export TOOLS="$ENGINE/tools"
if [ -z "${DBCX_PY:-}" ]; then . "$PLUGIN/scripts/python.sh"; dbcx_python || exit 127; DBCX_PY="$("${PY[@]}" -c "import sys; print(sys.executable.replace(chr(92), '/'))")"; fi   # run directly: the launcher's choice (py -3 resolved to its path)
[ "${DBCX_DRAWIO_IN_SMOKE:-}" = 1 ] || export DBCX_NO_DRAWIO_CLI=1 DBCX_NO_OPEN=1   # no draw.io desktop CLI (under a temp HOME it raises macOS keychain pop-ups) and no browser; DBCX_DRAWIO_IN_SMOKE=1 keeps both
export DBCX_PY; python3() { "$DBCX_PY" "$@"; }; export -f python3   # the smoke scripts' python3() is the launcher's Python (Windows has no python3)
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) PYSEP=";"; PYTOOLS="$(cygpath -w "$TOOLS")";; *) PYSEP=":"; PYTOOLS="$TOOLS";; esac   # Windows Python splits PYTHONPATH on ";" and reads Windows paths only
export DBCX_TOOLS="$PYTOOLS"; export PYTHONPATH="$PYTOOLS${PYTHONPATH:+$PYSEP$PYTHONPATH}"   # method tools (plugin, own, generic) import the engine by name, also without the launcher
WHICH="${1:-all}"; TMP="${2:-${TMPDIR:-/tmp}/dbcx-smoke-$$}"; export LANG_="${3:-en}"
case "$TMP" in /*) ;; *) TMP="$PWD/$TMP";; esac; export TMP
# A tmpdir inside a real run or engagement (e.g. `dbcx smoke all en` run from a run folder, where `en`
# became the tmpdir) makes the tools resolve the REAL run.json above it and re-render that run's files.
d="$(dirname "$TMP")"; while [ "$d" != "/" ]; do
  if [ -f "$d/run.json" ] || [ -f "$d/engagement.json" ]; then echo "refusing tmpdir $TMP: inside the project $d (run from a neutral folder or pass an absolute tmpdir outside any project; the language is the THIRD argument)"; exit 2; fi
  d="$(dirname "$d")"; done
rm -rf "$TMP"; mkdir -p "$TMP"
ran=0
if [ "$WHICH" = "engagement" ]; then echo "##### engagement (engine)"; bash "$ENGINE/smoke_engagement.sh"; echo "SMOKE TEST OK (engagement) -> $TMP"; exit 0; fi
for d in ${DBCX_METHOD_DIR:+"$DBCX_METHOD_DIR/"} "$PLUGIN"/methods/*/; do   # an own method (one folder, `dbcx smoke <name>` sets it) first
  m="$(basename "$d")"
  [ "$WHICH" = "all" ] || [ "$WHICH" = "$m" ] || continue
  if [ -f "$d/smoke.sh" ]; then echo "##### method $m"; bash "$d/smoke.sh"; ran=$((ran+1))
  elif grep -q '"discover": *"generic:' "$d/method.json" 2>/dev/null; then echo "##### method $m (generic smoke)"; bash "$ENGINE/generic_smoke.sh" "${d%/}"; ran=$((ran+1))
  else echo "##### method $m: no smoke.sh (skipped)"; fi
done
[ "$ran" -gt 0 ] || { echo "no method smoke test ran (asked for '$WHICH')"; exit 1; }
if [ "$WHICH" = "all" ] || [ "$WHICH" = "engagement" ]; then echo "##### engagement (engine)"; bash "$ENGINE/smoke_engagement.sh"; fi
echo "SMOKE TEST OK ($ran method(s)) -> $TMP"
