# Sourced by scripts/dbcx and hooks/run.sh (both then export PYTHONUTF8=1: Windows Python reads and writes pipes and files as cp1252).
# dbcx_python sets PY to the Python the engine runs with - $DBCX_PYTHON (one interpreter path), else the plugin's venv
# (`dbcx setup install`: ${DBCX_HOME:-~/.dbcx}/venv), else the first of python3.14..python3.11, python3, python (a WindowsApps
# candidate only if it actually runs - the Store alias stub does not), py -3. Only WindowsApps candidates are probed and the version is
# not (every call would pay a process start): `dbcx setup check` reports it.
dbcx_python() {
  if [ -n "${DBCX_PYTHON:-}" ]; then PY=("$DBCX_PYTHON"); return 0; fi   # one interpreter path (may contain spaces)
  local c p v="${DBCX_HOME:-$HOME/.dbcx}/venv"
  for p in "$v/bin/python" "$v/Scripts/python.exe"; do [ -x "$p" ] && { PY=("$p"); return 0; }; done
  for c in python3.14 python3.13 python3.12 python3.11 python3 python; do
    p="$(command -v "$c" 2>/dev/null)" || continue
    case "$p" in *WindowsApps*) "$p" -c "import sys" >/dev/null 2>&1 || continue;; esac   # the Store alias stub does not run; a real Store Python does
    PY=("$c"); return 0
  done
  if command -v py >/dev/null 2>&1; then PY=(py -3); return 0; fi
  echo "dbcx: no Python found (python3, python or py -3 on PATH, or DBCX_PYTHON) - run /dbcx-agentic-loop:setup" >&2; return 1
}
