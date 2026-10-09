---
name: setup
description: >-
  Set up this computer for the dbcx agentic loop plugin: checks Python and the
  packages the plugin needs, installs what is missing, offers the optional
  tools, and finishes with a short self-test. Use when the user says "set up
  the dbcx plugin", "install the dbcx plugin", "dbcx does not work", "check my
  dbcx setup", or when a dbcx tool reports a missing Python or package.
---
# dbcx-agentic-loop – machine setup

The user is usually not technical. Speak plainly: say what you are about to do and why in one or two sentences, never paste raw JSON or stack traces, and ask before anything that installs software outside the plugin's own environment. The launcher is `bash "${CLAUDE_SKILL_DIR}/../../scripts/dbcx"` (written `dbcx` below; always run it like that). If `${CLAUDE_SKILL_DIR}` is not replaced by a path, the launcher is `scripts/dbcx` two folders above this `SKILL.md`.

0. **Where am I?** This needs Claude Code with a local shell. If you have no Bash tool here (claude.ai chat, Cowork), say in one plain sentence that the plugin works in Claude Code - the desktop app's Code tab or the terminal - and stop.
1. **Check.** Run `dbcx setup check`. Read the JSON: `python` (needs 3.11+), `packages`, `optional_tools`, `missing_required`, `ok` (`optional_packages` are installed with the packages when possible and never block - do not mention them). If the launcher itself fails with "no Python found", treat it as Python missing. Tell the user in a short list what is already fine and what is missing, and what each missing item is needed for (the `enables` text).
2. **Python too old or missing.** It cannot be installed by the plugin. Explain, and guide the user: macOS - the installer from python.org (or `brew install python` if they use Homebrew); Windows - `winget install Python.Python.3.12` or the python.org installer with "Add python.exe to PATH" ticked. Afterwards a new Claude Code session is needed (the PATH changes only for new sessions); then run the check again.
3. **Install the packages.** Say: "I will now install the Python packages the plugin needs into its own separate environment in your home folder (`~/.dbcx`); this touches nothing else on your computer and needs no admin rights." Run `dbcx setup install` and relay each `step` line in plain words as it happens. Then run `dbcx setup check` again and confirm `ok`.
4. **Optional tools.** For each optional tool that is not found, say in one line what it adds and that everything else works without it, and offer to install it with the `install` hint from the check (on macOS only offer `brew` if `brew` exists). Install only what the user accepts, one at a time, and re-check after each.
5. **Self-test.** Run `dbcx smoke engagement` (about 6 seconds, works in a temporary folder). On `SMOKE TEST OK` tell the user the plugin is ready and that a run starts with "Initiate the project with the dbcx agentic loop plugin".

**When something fails** (pip error, proxy or certificate error, venv creation fails, the smoke test fails, a Windows path or permission problem): diagnose it yourself first - read the error, check the obvious causes (network or company proxy: `pip` honours `HTTPS_PROXY`; no venv module: retry with `dbcx setup install --user`; Windows Store Python stub: install Python properly; a different Python picked: set `DBCX_PYTHON` to the full path of a working interpreter for the session), fix what you can, and explain what you did in one sentence. If it stays broken, tell the user plainly what is wrong and what they can send to the plugin maintainer. On Windows, record every problem you diagnosed and how it was fixed as a learning, so the maintainer can make the fix permanent: a run folder in the cwd → `dbcx learn add --section B --title "setup on Windows: <problem>" --what "<symptom and cause>" --evidence "<error line>" --generalises "<which machines>" --proposal "<what fixed it>" --touches "engine/tools/setup.py"`; outside a run, write the same fields to `~/.dbcx/setup-learnings.md` (append) and tell the user where it is.
