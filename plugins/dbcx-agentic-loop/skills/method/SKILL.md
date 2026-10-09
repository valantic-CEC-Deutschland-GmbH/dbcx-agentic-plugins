---
name: method
description: >-
  Define, change, check or reuse an analysis method of your own for the dbcx
  agentic loop plugin, inside the plugin's framework: Claude interviews you
  block by block, writes the method card, builds the method, tests it on a
  small invented example and shows you the example workbook. Use when the
  user says "Create our own method", "define a method for this engagement",
  "Continue defining our method", "Change our method", "Check our method",
  "Use a method from my library", or "Save our method to my library", and
  when the run skill's init hands over a request like "... we need our own
  method for [task]".
---
# dbcx-agentic-loop – own methods

The user is usually not technical: plain words, one topic per message, no commands, keys or file names in the chat unless something fails; this includes the client's files ("the audit notes", not the file's name). Answer in the language the user writes in, never the client's or the deliverables' language; in German address the user as "du". The launcher is `bash "${CLAUDE_SKILL_DIR}/../../scripts/dbcx"` (written `dbcx` below; always run it like that). If `${CLAUDE_SKILL_DIR}` is not replaced by a path, the launcher is `scripts/dbcx` two folders above this `SKILL.md`. **Read `reference.md` next to this file before the first question**: the card slots and where each answer goes, the framework in plain words, the building blocks, the costs, the guard rules. Do every step yourself in this session: the hook denies the method commands to sub-agents.

An own method lives in the engagement (`<engagement>/methods/<name>/`). Its source of truth is the **method card**. Write the card only through `dbcx method card <name> --set <path>=<json>` (or `--postpone <path> --why "..."`), and never edit the card or the generated files by hand. Hand-written method Python (only where the building blocks do not cover a need, `reference.md` §6) is one exception, and regeneration keeps it. A **derived** method (a copy of a plugin method, card `origin.type` `derived`) is the other: it is never regenerated, and you change its copied files directly (`reference.md` §6). A method changes **only between runs**.

## Create – "Create our own method", "define a method for this engagement", or the hand-over from init
0. An `engagement.json` must exist above the cwd. If it does not, run the run skill's init step 1 first, then come back.
1. **Start from the task.** Ask for one paragraph on what the client needs, and for an example result from an earlier project if there is one (an Excel, a slide table, a report). Read it and pre-fill every answer you can. Never copy a client's or a person's name from it into the card. Read the client's material only to pre-fill answers, and never comment on its content (figures, gaps, contradictions), neither in the interview nor at the hand-back to init: that is the run's job.
2. **State the frame once**, in the six plain sentences of `reference.md` §2. It is fixed: it is never asked and never changed.
3. **Block A, the fit check.**
   - A1: ask what the client should decide or do with the result.
   - A2: compare with the plugin's methods (`dbcx method list`). If one of them with adjustments does the job, recommend it, say what the adjustments would change, and stop if the user agrees. Then hand back to the run skill's init with that method; the adjustments are made later with "Optimize the project setup". If its structure fits but the user needs more than adjustments, offer a copy to build on (`dbcx method new <name> --from <method>`), ask only about the differences, and make them as for a derived method under Change.
   - A3–A5 are knock-outs: knowledge only in people's heads, no outside standard to check against, a result that is not table-shaped. Explain the alternative from `reference.md` §3 in two sentences and stop. The user can overrule A2, never a knock-out.
   - Then propose a short name (lower-case words with hyphens, not a plugin method's name), create the card with `dbcx method card <name> --init`, and write block A.
4. **Blocks B to G, one block per message.** Ask at most three questions per message, each with a proposed answer the user can accept with "yes" ("I'd propose one unit = one supplier. OK, or something else?"). Write every answer at once with `--set` (`reference.md` §1 maps question → card path; formulas in its "Formula hints" notation). When the user says "after the first run", use `--postpone`.
   - Apply the fit rules of `reference.md` §3 as you go. A unit must be analysable alone. There is one client reviewer. Every topic needs at least one outside expert.
   - Name the cost of large choices (`reference.md` §5, e.g. "each further outside expert is another agent per unit and round") and let the user decide. Never cap the size and never ask the user to cut scope.
   - Readers (B1, B5) are the plugin's personas (`reference.md` §4.5): offer the closest one when the user names another role. The client reviewer (D2) is described in the user's words.
   - Units (C2): propose one of the four ready sources. When the user names the units (source `list`), write the names to `unit.source_config` at once, so a resumed session does not ask again; step 10 fills the run's unit list from them. If none fits, the method gets its own unit tool (`unit.source` `"tool"`, `reference.md` §4.1): say so in one sentence. After the build, write the tool together with a fictional fixture and its own smoke (`reference.md` §6); `method check` refuses the method without them. A copy of a plugin method keeps that method's tool and smoke.
   - Both languages (B6): write every text slot as one text per language (`reference.md` §1).
   - **Where to keep it**, the last question of the interview: "Should this method stay in this engagement only, or also go into your personal library so you can use it in other projects?" Propose this engagement only, and write the answer to `storage`.
5. **Pause and resume.** Every answer is saved when it is given, so the user may stop at any point. "Continue defining our method": find the method (`dbcx method list`; ask if there are several unfinished ones), run `dbcx method card <name> --json` and read its `open` and `invalid` lists, give a two-line recap and continue with the first open block.
6. **Block H, confirm.** Run `dbcx method card <name> --render` and present the card as one page in plain words: purpose, readers and their questions, the unit and where the list comes from, the client reviewer and the outside experts with their sources and topics, the topics per unit, the cross-unit view, the workbook sketch, what was postponed, and where it is kept. Write corrections with `--set` and render again. Only on a clear yes: `dbcx method confirm <name>`; it refuses while a slot is open, so finish or postpone that slot first. **Every later change of an answer makes the card unconfirmed again**: show the changed card and get a new yes before `confirm` and `generate`.
7. **Build and test.** Run these in order:
   - `dbcx method generate <name>` (add `--closest <method>` when the card names one; never for a derived method, see Change).
   - `dbcx method check <name>`. Explain each guard warning in one plain sentence. On the user's yes run `dbcx method confirm <name> --guard`; otherwise change the card.
   - `dbcx smoke <name>`.
   On a failure, read the message and fix the cause: method Python within the contract (such as the unit tool), or the card. A card fix unconfirms the card: stop, show the user what changed in plain words and wait for a new yes before `confirm` and `generate`. Never confirm a changed card on your own. Run the checks again, and tell the user in one plain sentence what was wrong. If it stays broken, tell the user plainly what is wrong and what they can send to the plugin maintainer (the check's output and the card).
8. **Show the example workbook.** The smoke prints `SMOKE TEST OK ... -> <folder>`, and the workbooks are in `<folder>/<name>/deliverables/`. Copy each workbook into a new temporary folder under a name that cannot collide with a real deliverable, `<file name> – example.xlsx` (German: `– Beispiel`), because Excel refuses two open workbooks of the same name. Open the copy (macOS `open "<copy>"`, Windows `cmd /c start "" "<copy>"`, Linux `xdg-open "<copy>"`), or give its path if no window opens. If the environment variable `DBCX_NO_OPEN` is `1`, open nothing and only give the path. Say that the data is invented and only shows the shape. A correction changes the card, so it goes back to step 6 (new yes, then generate again), until the user says the method is ready.
9. **Library copy.** If the user chose "also my library" (`storage` = `library`), run `dbcx method save <name>` now (it needs a clean check).
10. **Hand back** to the run skill's init (step 2 onwards) with `dbcx init run --method <name>`. Fill the run's fields the user already answered in the interview (such as the unit names) before you name what is still open.

## Change – "Change our method" (between runs only)
- If a run of the engagement that uses this method is open (`reference.md` §7), do not change anything. Say in one sentence that changes wait for the end of the run, and offer to note the change in that run's open items: `dbcx learn add --section F --title "method change after this run: ..." ...`.
- Otherwise:
  - Read the card (`dbcx method card <name> --render`) and the open items of the last run (`dbcx learn open`).
  - Ask only about what changes, one block per message as in Create step 4.
  - Write the answers with `--set`, then run Create steps 6 to 8: confirm, generate, check, smoke, example workbook.
  - **A derived method** (card `origin.type` `derived`): never run `generate` on it. It would replace the copy, it needs `--force`, and you never force it. Instead:
    - Make the change directly in the copied files (method.json, kinds.json, deliverables, labels, briefs, plan), within the method pack contract (`reference.md` §6).
    - Record the change on the card with `--set`, show the card, and confirm it on the user's yes.
    - Then run `dbcx method check <name>` and `dbcx smoke <name>`, and show the example workbook.
  - If the method is also in the library, ask whether to update the library copy too (`dbcx method save <name>`).

## Check – "Check our method"
Run `dbcx method check <name>` and `dbcx smoke <name>`. Report in plain words: ready, or what is wrong and what you propose. Fix only after the user's yes.

## Library – "Use a method from my library" / "Save our method to my library"
- **Use:** `dbcx method list` shows the library. Install the chosen method with `dbcx method install <name>` into this engagement as its own copy, so later library edits never change this engagement. Then run `dbcx method check <name>` and `dbcx smoke <name>`, and continue with the run skill's init. If a newer library version exists, `dbcx method install <name> --update` replaces the copy, between runs only.
- **Save:** `dbcx method save <name>` (it needs a clean check). If the library already has a method of that name, ask before replacing it.
