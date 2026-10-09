#!/usr/bin/env python3
"""Machine setup for the dbcx-agentic-loop plugin (the /dbcx-agentic-loop:setup skill drives it).

Usage:
  dbcx setup check [--text]     JSON report: OS, shell, the Python the launcher picked (3.11+ needed), the engine's Python packages,
                                optional tools and what each enables; "ok" = everything required is there. --text: one line per item
  dbcx setup install [--user]   installs the missing Python packages into the plugin's own virtual environment <DBCX_HOME>/venv
                                (default ~/.dbcx/venv; scripts/dbcx prefers it once it exists). --user: `<python> -m pip install --user`
                                into the picked Python instead (fallback where venv is unavailable)

Why a venv and not `pip install --user` by default: Homebrew and many Linux Pythons refuse --user installs (PEP 668, "externally
managed"), a Windows user site is not always on the path of the Python the launcher finds, and a venv needs no admin rights and
leaves the user's other Python work alone. The installed plugin folder stays read-only: the venv lives outside it.
This file is kept free of newer syntax so that `setup check` still runs - and says what to install - on an old Python.
"""
import json, os, platform, shutil, subprocess, sys

PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIN_PY = (3, 11)
VENV = os.path.join(os.path.expanduser(os.environ.get("DBCX_HOME") or "~/.dbcx"), "venv")
VENV_PY = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")
PACKAGES = [   # (import name, pip name, what it enables) - all required
    ("openpyxl", "openpyxl", "reading client workbooks and building every Excel deliverable"),
    ("docx", "python-docx", "reading Word (.docx) inputs into the corpus"),
    ("pptx", "python-pptx", "reading PowerPoint (.pptx) inputs into the corpus"),
]
SOFT_PACKAGES = [   # (import name, pip requirement, what it enables) - installed in the same pip step when possible, never required
    ("model2vec", "model2vec>=0.9,<0.10", "meaning-based search in large client corpora (keyword search works without it)"),
]
MAC, WIN = sys.platform == "darwin", os.name == "nt"
TOOLS = [   # (name, executables / paths, what it enables, install hint)
    ("pdftotext", ["pdftotext"], "reading PDF inputs into the corpus", "brew install poppler" if MAC else "winget install oschwartz10612.Poppler (then reopen the terminal)" if WIN else "apt install poppler-utils"),
    ("pdfinfo / pdftoppm", ["pdftoppm"], "page images of the rendered workbooks for the final gate (poppler, same package as pdftotext)", "brew install poppler" if MAC else "winget install oschwartz10612.Poppler" if WIN else "apt install poppler-utils"),
    ("draw.io CLI", ["drawio", "draw.io", "/Applications/draw.io.app/Contents/MacOS/draw.io", r"C:\Program Files\draw.io\draw.io.exe"], "PNG/SVG export of landscape diagrams (ea-landscape; without it the .drawio file is still written)", "brew install --cask drawio" if MAC else "winget install JGraph.Draw" if WIN else "https://github.com/jgraph/drawio-desktop/releases"),
    ("git", ["git"], "fast file listing of client repositories (code-analysis)", "xcode-select --install" if MAC else "https://git-scm.com (Git for Windows, includes Git Bash)" if WIN else "apt install git"),
]
if MAC: TOOLS.append(("Microsoft Excel", ["/Applications/Microsoft Excel.app"], "recalculating and rendering the workbooks before the final gate (macOS only; without it formulas stay uncalculated in the review)", "install Microsoft Excel (Microsoft 365)"))

def find(cands):
    for c in cands:
        p = c if os.path.isabs(c) and os.path.exists(c) else shutil.which(c)
        if p: return p
    return None

def py_info(exe):
    """version and package state of another interpreter (the venv) - None when it does not run"""
    code = "import importlib.util, json, sys; print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3])), 'have': [m for m in %r if importlib.util.find_spec(m)]}))" % [m for m, _, _ in PACKAGES + SOFT_PACKAGES]
    try: return json.loads(subprocess.run([exe, "-c", code], capture_output=True, text=True, timeout=60).stdout)
    except Exception: return None

def check():
    import importlib.util
    in_venv = os.path.abspath(sys.prefix) == os.path.abspath(VENV)
    shell = "git-bash" if os.environ.get("MSYSTEM") else os.path.basename(os.environ.get("SHELL") or os.environ.get("ComSpec") or "?")
    pkgs = [{"name": pip, "import": m, "installed": bool(importlib.util.find_spec(m)), "enables": why} for m, pip, why in PACKAGES]
    tools = [{"name": n, "path": find(c), "enables": why, "install": hint} for n, c, why, hint in TOOLS]
    pyok = sys.version_info[:2] >= MIN_PY
    try: pip = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True, timeout=60).returncode == 0
    except Exception: pip = False
    r = {"os": platform.system(), "os_version": platform.release(), "machine": platform.machine(), "shell": shell,
         "python": {"executable": sys.executable, "version": platform.python_version(), "ok": pyok, "needed": ">= %d.%d" % MIN_PY, "pip": pip, "venv": in_venv},
         "venv": {"path": VENV, "exists": os.path.exists(VENV_PY), "used": in_venv},
         "packages": pkgs, "optional_packages": [{"name": pip, "import": m, "installed": bool(importlib.util.find_spec(m)), "enables": why} for m, pip, why in SOFT_PACKAGES], "optional_tools": tools, "launcher": os.path.join(PLUGIN, "scripts", "dbcx").replace(os.sep, "/"),
         "missing_required": ([] if pyok else ["python>=%d.%d" % MIN_PY]) + [p["name"] for p in pkgs if not p["installed"]]}
    r["ok"] = not r["missing_required"]
    return r

def say(msg): print(msg, flush=True)

def install(user=False):
    if sys.version_info[:2] < MIN_PY:
        sys.exit("REFUSED: this Python is %s; the plugin needs %d.%d or newer. Install a current Python (macOS: python.org installer or `brew install python`; Windows: python.org installer with 'Add python.exe to PATH', or `winget install Python.Python.3.12`), open a new terminal, run `dbcx setup check` again." % ((platform.python_version(),) + MIN_PY))
    if user: target = sys.executable
    else:
        if not os.path.exists(VENV_PY):
            say("step 1: creating the plugin's own Python environment in %s" % VENV)
            r = subprocess.run([sys.executable, "-m", "venv", VENV], capture_output=True, text=True)
            if r.returncode != 0: sys.exit("FAILED: creating the venv: %s\n(retry with `dbcx setup install --user`)" % (r.stderr or r.stdout).strip()[-800:])
        else: say("step 1: the plugin's Python environment exists (%s)" % VENV)
        target = VENV_PY
    info = py_info(target) or {"have": []}
    missing = [pip for m, pip, _ in PACKAGES if m not in info["have"]]; soft = [pip for m, pip, _ in SOFT_PACKAGES if m not in info["have"]]
    if not missing and not soft: say("step 2: all packages already installed")
    else:
        say("step 2: installing %s (this downloads from pypi.org and can take a minute)" % ", ".join(missing + soft))
        pip = [target, "-m", "pip", "install", "--disable-pip-version-check"] + (["--user"] if user else [])
        r = subprocess.run(pip + missing + soft, capture_output=True, text=True)
        if r.returncode != 0 and soft:   # a soft package never fails setup: retry without it
            say("step 2: %s could not be installed here - continuing without it" % ", ".join(soft))
            r = subprocess.run(pip + missing, capture_output=True, text=True) if missing else None
        if r is not None and r.returncode != 0: sys.exit("FAILED: pip install: %s" % (r.stderr or r.stdout).strip()[-1500:])
    info = py_info(target) or {"have": []}
    still = [pip for m, pip, _ in PACKAGES if m not in info["have"]]
    if still: sys.exit("FAILED: still missing after install: %s" % ", ".join(still))
    say("step 3: verified - %s runs Python %s with %s" % (target, info.get("version", "?"), ", ".join([pip for _, pip, _ in PACKAGES] + [pip.split(">")[0] for m, pip, _ in SOFT_PACKAGES if m in info["have"]])))
    if not user: say("the launcher uses this environment from now on (scripts/dbcx prefers %s)" % VENV_PY)
    return target, info

def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("check", "install"): print(__doc__); sys.exit(0 if not a else 2)
    if a[0] == "install": return install("--user" in a)
    r = check()
    if "--text" not in a: print(json.dumps(r, indent=1)); sys.exit(0 if r["ok"] else 1)
    print("python    %s %s (%s)" % (r["python"]["version"], "ok" if r["python"]["ok"] else "TOO OLD, needs " + r["python"]["needed"], r["python"]["executable"]))
    for p in r["packages"]: print("package   %-12s %s  - %s" % (p["name"], "ok" if p["installed"] else "MISSING", p["enables"]))
    for p in r["optional_packages"]: print("optional  %-18s %s  - %s" % (p["import"], "installed" if p["installed"] else "not installed (installed with the packages when possible)", p["enables"]))
    for t in r["optional_tools"]: print("optional  %-18s %s  - %s" % (t["name"], "found" if t["path"] else "not found (" + t["install"] + ")", t["enables"]))
    sys.exit(0 if r["ok"] else 1)

if __name__ == "__main__": main()
