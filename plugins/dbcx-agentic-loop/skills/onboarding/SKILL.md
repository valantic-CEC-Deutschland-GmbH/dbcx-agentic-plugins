---
name: onboarding
description: >-
  Walk a new user through the dbcx agentic loop plugin: opens a short
  onboarding page in the browser (what the plugin does, the main loop with
  example prompts, how the dashboard works with a live demo, how to customise
  it, what else there is) and sums it up in chat. Use when the user says
  "onboarding", "show me how the dbcx plugin works", "what can this plugin
  do", "how do I use dbcx", or "getting started with dbcx".
---
# dbcx-agentic-loop – onboarding

The user is usually not technical: plain words, no commands or paths in the chat unless something fails. The launcher is `bash "${CLAUDE_SKILL_DIR}/../../scripts/dbcx"` (written `dbcx` below; always run it like that). If `${CLAUDE_SKILL_DIR}` is not replaced by a path, the launcher is `scripts/dbcx` two folders above this `SKILL.md`.

0. **Where am I?** This needs Claude Code with a local shell. If you have no Bash tool here (claude.ai chat, Cowork), say in one plain sentence that the plugin works in Claude Code - the desktop app's Code tab or the terminal - and stop.
1. **Open the page.** Run `dbcx onboarding open` (add `--lang de` when the user writes German). It opens the page in the default browser and prints its path. If the launcher fails (for example "no Python found"), open `engine/onboarding/index.html` two folders above this `SKILL.md` directly (macOS `open "<file>"`, Windows `cmd /c start "" "<file>"`, Linux `xdg-open "<file>"`); if no browser opens, give the user the file path to open by double-click. If the environment variable `DBCX_NO_OPEN` is `1`, open nothing and only give the path (the tool already does so).
2. **Sum it up in five lines**, in the user's language:
   - The plugin turns a client's material into reviewed deliverables: agents analyse, critics from the client side and from the standard side check every statement against the evidence, a final gate reads the result as the client's stakeholders would.
   - Start: "Initiate the project with the dbcx agentic loop plugin" - Claude asks for the method: one of the five, or one of your own that it defines with you - then "Prepare for task 1", then "Execute the plan" in the run folder.
   - During the run the dashboard shows the progress and collects answers, hints, pause and checkpoint; "How far are we?" works in chat.
   - Afterwards: "Evaluate the outcome of task 1", then "Optimize the project setup" for this engagement or "Export the learnings" for the plugin maintainer.
   - The page's live demo buttons play a fictional run in the real dashboard: a code analysis, or an estimate of several systems (impact per system, gap decisions of the architect).
3. **Offer the next step.** Run `dbcx setup check` quietly: if it is not `ok` (or the launcher failed), offer the machine setup ("set up the dbcx plugin"). Otherwise, if the cwd is inside an engagement (`engagement.json` or `run.json` above it), offer to show where it stands; else offer to start a first project. When the user describes a task that none of the five methods fits, offer "Initiate the project with the dbcx agentic loop plugin – we need our own method for <task>".
