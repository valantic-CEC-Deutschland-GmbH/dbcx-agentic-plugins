#!/usr/bin/env python3
"""Onboarding page of the dbcx-agentic-loop plugin (the /dbcx-agentic-loop:onboarding skill drives it).

Usage:
  dbcx onboarding open [--lang en|de]   opens engine/onboarding/index.html in the default browser and prints its path
  dbcx onboarding path                  prints the page's path only

The page is self-contained and works from file://. A language is passed as ?lang=; Windows and xdg-open drop the query of a file
URL, so --lang opens a one-line redirect page in the temp folder instead (the installed plugin folder is read-only).
DBCX_NO_OPEN=1 (tests, headless sessions) prints the path and opens nothing.
"""
import json, os, sys, tempfile, webbrowser
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "onboarding" / "index.html"

def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("open", "path"): print(__doc__); return
    print(PAGE)
    if a[0] == "path" or os.environ.get("DBCX_NO_OPEN") == "1": return
    url, lang = PAGE.as_uri(), a[a.index("--lang") + 1] if "--lang" in a else None
    if lang:
        stub = Path(tempfile.gettempdir()) / "dbcx-onboarding.html"
        stub.write_text(f'<!doctype html><meta charset="utf-8"><script>location.replace({json.dumps(url + "?lang=" + lang)})</script>', encoding="utf-8")
        url = stub.as_uri()
    if not webbrowser.open(url): sys.exit("could not open a browser - open the file above by double-click")

if __name__ == "__main__": main()
