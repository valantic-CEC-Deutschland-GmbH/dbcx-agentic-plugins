#!/usr/bin/env bash
# hooks.json entry: run.sh <event> < hook-input JSON. The hooks fire on every tool call of every session with the plugin enabled, so the
# common case - no run.json at or above the input's cwd - exits here before any Python starts. When the cwd cannot be read cheaply
# (missing, escaped, relative) dbcx_hook.py decides, exactly as before.
IFS= read -r -d '' IN
case "$IN" in
  *'"cwd":"'*) d="${IN#*\"cwd\":\"}";; *'"cwd": "'*) d="${IN#*\"cwd\": \"}";; *) d="";;
esac
d="${d%%\"*}"; d="${d//\\\\//}"
case "$d" in
  *\\*) ;;
  /*|[A-Za-z]:/*)
    while [ ! -e "$d/run.json" ]; do p="${d%/*}"; [ "$p" = "$d" ] && exit 0; d="$p"; done;;
esac
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../scripts/python.sh"; dbcx_python || exit 0
export PYTHONUTF8=1
exec "${PY[@]}" "$HERE/dbcx_hook.py" "$@" <<<"$IN"
