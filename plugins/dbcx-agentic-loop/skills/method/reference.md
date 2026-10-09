# Own methods – reference for the `method` skill

This is the authoring source for own methods. It is self-contained because the plugin's architecture notes do not ship. Read it before the
interview, and come back to a section when you need it. Nothing in this file is said to the user verbatim: translate it into plain words.

## 1. The method card

`<engagement>/methods/<name>/method-card.json` holds the answers, and `METHOD-CARD.md` is its rendering (`dbcx method card <name> --render`).
Both are written only by `dbcx method card`, never by hand. The generator (`dbcx method generate`) builds the method from the card,
`dbcx method check` validates it, and the learnings export carries it to the maintainer, so the card shows the intent and not only the
files.

- Every slot is required. A slot the user moves to "after the first run" holds `{"postponed": "<why>"}` (`--postpone <path> --why "..."`).
- Values are JSON: `--set unit.noun='"Supplier"'`, `--set result.personas='["cfo","head-of-it"]'`.
- Every text slot takes a string or one text per language, `{"en": "...", "de": "..."}`. Use the per-language form whenever `languages` has both (titles, sheet and column names, questions, anchors, unit nouns): each workbook language then reads natively.
- Set lists and objects whole, or one entry by index (`result.workbooks[0].title`; the index equal to the list's length appends).
- **Any change resets `confirmed`** (except a change of `storage` alone). The user sees the card again and says yes again before `dbcx method confirm`, which refuses while a slot is open.
- Paths below use `[]` for "every entry of the list".

### Questions → card slots

| Block / question (as asked) | Card path | Meaning – what it drives in the method |
|---|---|---|
| start: the task in one paragraph | `name`, `display`, `description` | id (lower-case words with hyphens, never a plugin method's name), display name, purpose; the method's description |
| B6 "English, German, or both?" | `languages` | `["en"]`, `["de"]` or both: one deliverable spec and label file per language |
| A2 the closest plugin method | `origin`, `origin.type`, `origin.closest` | `custom` (built from the card) or `derived` (`dbcx method new --from`); `closest` = the plugin method whose structure the generator borrows where an answer matches it, or null |
| A1 "what should the client decide or do with the result?" | `fit`, `fit.decision` | a decision or an action, never "an overview"; becomes the brief row DECISION and the management summary's purpose |
| A3 "what will the client's material be?" | `fit.client_material` | types (documents, workbooks, exports, boards, code repository): the client-side evidence base |
| A4 "what do we check it against on the outside?" | `fit.external_standards` | vendor documentation, a reference model, a catalogue, a norm, market data: the standard-side evidence, knowledge packs, research topics |
| A5 "tables someone can filter, total and trace back?" | `fit.table_shaped` | must be `true` (knock-out, §3) |
| B1 "who at the client reads it?" | `result`, `result.personas` | persona ids (§4.5; the check accepts only these, hyphen or underscore spelling): the final gate's readers |
| B2 "which three to five questions must the workbook answer?" | `result.key_questions` | the management summary and the gate personas' key questions |
| B5 "one workbook, or two for different readers?" | `result.workbooks`, `result.workbooks[].id`, `result.workbooks[].title`, `result.workbooks[].readers` | one entry per workbook (`D1`, `D2`, ...), its title and the persona ids that read it; no upper limit |
| B3 "what is one row of the main table, and which columns?" | `result.workbooks[].sheets`, `result.workbooks[].sheets[].name`, `result.workbooks[].sheets[].row` | the table sheets and what one row is ("one supplier", "one requirement x supplier") |
| B3 "which columns are facts, which are judgement?" | `result.workbooks[].sheets[].columns`, `result.workbooks[].sheets[].columns[].name`, `result.workbooks[].sheets[].columns[].kind`, `result.workbooks[].sheets[].columns[].from`, `result.workbooks[].sheets[].columns[].formula` | `kind`: `fact` (a claim of type fact), `assessment` (a judgement claim, scored like any claim), `formula` (an Excel formula, never a typed number); `from` = where the column is filled from: `<topic id>.<field>`, `<topic id>` alone for a text or list topic, `inventory.<field>` (the inventory step's unit table), `<view>.<field>` (a cross-unit view, `view` of `consolidations[]`), or null for a formula column; `formula` = the formula of a formula column, in the notation of "Formula hints" below |
| B4 "what should be counted, totalled, weighted or ranked?" | `result.workbooks[].aggregates`, `result.workbooks[].aggregates[].what`, `result.workbooks[].aggregates[].formula_hint` | the overview sheet: every aggregate is a formula over the detail sheets, written in the notation of "Formula hints" below |
| B4 "any weights or rates the client should be able to change?" | `result.workbooks[].parameters`, `result.workbooks[].parameters[].name`, `result.workbooks[].parameters[].default`, `result.workbooks[].parameters[].meaning` | the Parameters sheet: editable cells the formulas read |
| C1 "what is one unit a single analyst can look at completely?" | `unit`, `unit.noun`, `unit.noun_plural` | the unit of analysis (one analyst per unit), singular and plural |
| C2 "where does the list of units come from?" | `unit.source`, `unit.source_config` | `list` (named at the start), `workbook` (a column of a client workbook), `folders` (folders or documents of the input), `inventory` (an inventory step finds and verifies them first), `tool` (the method's own unit tool, when none of the four fits, and in a copy of a plugin method); the config shapes are in §4.1 |
| C3 "how many, how big, does one need another's result first?" | `unit.dependencies` | `independent` (all in parallel), `dependent` (in waves along the dependencies), `grouped` (waves by group) |
| C4 "are the unit names public, like product names?" | `unit.names_public` | `false` (default): the names never leave the machine in a web query; `true` only for public names (a guard key, §7) |
| D1 "does it build on another run's or department's result?" | `evidence`, `evidence.consumes`, `evidence.consumes[].type`, `evidence.consumes[].required` | artefact types imported at init (`requirements-set`, `system-inventory`, `shortlist`, ...): frozen snapshots, cited as evidence, never re-reviewed |
| D2 "who would the client's own reviewer be?" | `evidence.client_reviewer`, `evidence.client_reviewer.persona` | the persona of the one client-side critic (the client's architect, product owner, purchasing lead, ...); exactly one, never split |
| D3 "which outside standards, one expert per standard, with sources and topics?" | `evidence.standard_critics`, `evidence.standard_critics[].id`, `evidence.standard_critics[].persona`, `evidence.standard_critics[].scores` | the standard-side critics (§4.3): a short id, the expert's persona in one sentence, `scores`: `"all"` or `{"topics": ["<topic id>"]}` |
| D4 "which web sources may each expert use?" | `evidence.standard_critics[].sources`, `evidence.standard_critics[].sources.packs`, `evidence.standard_critics[].sources.domains`, `evidence.standard_critics[].sources.reference` | knowledge packs (`dbcx pack list`), official web domains, and whether the engagement's verified reference file counts; never client material |
| (optional, after D) "is some material clearly about certain units?" | `evidence.hints` | free-text hints ("the workshop folder 'Logistik' is about the warehouse units"); they boost the automatic mapping of material to units. Never ask which material belongs to which unit: the engine maps it. |
| E1 "what must be found out for each unit?" | `topics`, `topics[].id`, `topics[].title` | one section of the analyst's document per topic; the ids are what critics' `scores.topics` and columns' `from` name |
| E2 (table and rating topics) "exactly one row per unit, like one rating per unit, or several?" | `topics[].rows` | optional: `one` or `many` (default `many`); with `one`, a per-unit sheet's column shows the unit's value instead of an average, a count of yes or the first row (Formula hints) |
| E2 "a description, a list, or a rating? What do 0, 5 and 10 mean?" | `topics[].form`, `topics[].fields`, `topics[].fields[].name`, `topics[].fields[].type`, `topics[].fields[].enum`, `topics[].anchors` | `text`, `list`, `table` (rows with fields) or `rating` (0–10 with `anchors` `{"0": ..., "5": ..., "10": ...}`); field types `s` text, `i` integer, `n` number (decimals, a decimal comma is fine), `b` yes/no, `l` list; `enum` = allowed values (optional). `fields` are required for `table` and `rating` topics, `anchors` for `rating` only. Implicit fields, never listed: a rating has `score`, `rationale`, `evidence`, `confidence` (and `aspect` when it has no fields of its own); a table row has `evidence` |
| E3 "what must the analyst never do or assume?" | `analyst_rules` | sentences added to the analyst's method brief |
| E4 "which client-specific settings do we fill in at the start?" | `init_fields`, `init_fields[].key`, `init_fields[].hint`, `init_fields[].default` | placeholders `dbcx init run` writes and `dbcx check_fill` keeps open until filled (scale, deadline, shortlist size, the unit list or workbook file) |
| F1 "what do we only see with all units side by side?" | `consolidations`, `consolidations[].workbook`, `consolidations[].view` | one consolidation per workbook that needs a cross-unit view: `ranking`, `gap-list`, `totals`, `conflicts`, `target-picture`, `other`; no upper limit |
| F2 "which judgements are made there?" | `consolidations[].judgements` | the consolidator's tasks (calibrate ratings across units, name the top blockers, ...) |
| G1 "mostly a document collection where a short version is enough?" | `run_options`, `run_options.lean` | `true` offers the lighter run profile (one analysis over everything, fewer critic rounds) |
| G2 "does someone on our side decide something in the middle?" | `run_options.human_step` | null, or a sentence naming the decision and who takes it |
| G3 "does the result feed a later method? Under which name?" | `run_options.produces` | artefact types the run releases at handover |
| G4 "words that must never appear in the workbook?" | `run_options.forbidden_terms` | internal project terms the deliverable lint refuses |
| anything "after the first run" | `postponed` | free text per postponed wish; shown on the card and in the method's plan |
| last question of the interview, before the card is shown: "this engagement only, or also your library?" | `storage` | `engagement` (default) or `library` (then `dbcx method save` once the method is ready; save also sets it). Changing only this slot keeps the card confirmed. |
| set by the tools | `card_version`, `confirmed` | the card format (1); `confirmed` is set only by `dbcx method confirm` after the user's yes on the rendered card |

### Formula hints
`dbcx method generate` reads a formula column's `formula` and an aggregate's `formula_hint` only in this notation and refuses anything else.
Write the notation as soon as the answer is given (B3, B4), so the confirmed card builds; tell the user the formula in words.
- `=<Excel formula>`: `[Column]` is this row's cell, `[Sheet.Column]` that column's range, `{Parameter}` a parameter of the workbook,
  `{L:token}` the display label of an enum value. Names are the card's sheet and column names, topic ids or titles, and field names.
- `count <Sheet>`, `sum | average | min | max <Sheet>.<Column>`, `share <Sheet> where <condition>`, with
  `... where <Column> <op> <value> [and ...]` (op `=` `<>` `<` `>` `<=` `>=`). An aggregate may end in `per <unit noun>` (one row per
  unit) or `by <Column>` (one row per value).
- Examples: `=[Quality rating]*{Weight quality}+[Delivery rating]*{Weight delivery}`, `=RANK([Weighted score],[Suppliers.Weighted score])`,
  `count Suppliers by Recommendation`, `average Suppliers.On-time rate`.
- `first <Sheet>.<Column>` (per-unit sheets only): the value of the unit's first row on that sheet.
- A column of a per-unit sheet (one row per unit) whose `from` names a field of a `table` or `rating` topic shows:
  - with `rows: "one"` on the topic, the unit's value itself (the engine looks it up);
  - with many rows (the default), the average for numbers, the count of yes for yes/no fields, and the first row's value for text
    and dates.
  So when a topic has exactly one row per unit (a rating per unit, one contract per supplier), set `rows: "one"` instead of writing a
  lookup formula.

## 2. The frame (stated once, never asked)

Every method runs the same skeleton:

`preparation → [inventory + review] → the units in waves + review → cross-unit view(s) + review → Excel build → reading by the client's people`

Say it to the user in these six sentences, in the user's language:
- Every statement in the result is a claim with evidence someone can open.
- Reviewers from two sides check every statement: one from the client's own material, at least one from the outside standard.
- Every figure in the Excel is a formula.
- Questions for the client never stop the work. They are collected with a proposed answer.
- The workbook speaks about the client's subject only, never about how it was made.
- At the end, the client's people (the readers chosen in the interview) read and score the result.

The 13 principles behind them, in plain words. An answer that breaks one does not fit the framework:
1. One analyst per unit; it sees its unit, not the others (cross-unit facts travel through the lead).
2. Everything in a deliverable is a claim with an id, a type (fact or judgement), evidence and the cell it feeds.
3. Critics from two evidence sides score every claim 0–10: exactly one client-side critic, at least one standard-side critic, never the same evidence.
4. Formulas, not typed numbers; editable parameters where weights or rates exist.
5. Intermediate results are documents in fixed templates, converted by tools; only the tools write the Excel.
6. The run's state is written down and verified; a run resumes from it, never from memory.
7. Client questions are part of the result (their own sheet) and never block the run.
8. A final gate: the client's personas read the Excel and score it.
9. Evidence is read-only; nothing of the client goes to outside services; web lookups only for public standards with generic queries.
10. A passed review grades a claim's statement and nothing else; refutations are reviewed claims too.
11. Client-facing text speaks about the subject, in the present tense, never about rounds, corrections or versions.
12. Runs stand alone; a later method imports a released result as a frozen snapshot.
13. Learnings are collected and go to the plugin maintainer, anonymised.

## 3. Fit rules and what to offer instead

| Rule | When it fails | Offer instead (two sentences, then stop or adjust) |
|---|---|---|
| A2 a plugin method fits | code analysis, enterprise architecture landscape, requirements, technology scoring, technology-fit estimation (with adjustments) cover the task | recommend it, name the adjustments ("Optimize the project setup" changes wording, settings, knowledge, brief notes); the user may still insist on an own method |
| A3 knock-out | the knowledge exists only in people's heads | a workshop first; the notes then become the material (for requirements: the requirements method) |
| A4 knock-out | no outside standard to check against | the standard side needs at least one source (vendor documentation, a reference model, a catalogue, a norm, market data); propose one; without any, the framework does not fit |
| A5 knock-out | the result is not table-shaped (a text, a slide deck) | Excel is the only deliverable; a deck can be built from the workbook afterwards |
| C unit alone | every unit needs every other one | take the group as the unit, or let a cross-unit view (consolidation) do the cross-unit part |
| D one client reviewer | the user wants to split the client side | one client critic per unit, never split: its job includes finding contradictions between sources, and a split would hide them; splitting the unit is the way to make one job smaller |
| D outside experts | a topic without an expert | every topic is scored by at least one standard critic (`scores: "all"` covers all) |
| D separate evidence | an expert should read client material | a standard critic never reads client material (hook-enforced); its sources are packs, web domains, the reference file |
| B3/B4 formulas | a figure "typed in" | every count, total, share, weighting is a formula; a judgement stands next to the formula result |

## 4. Building blocks (no Python for a typical method)

### 4.1 Where the units come from (`unit.source` → generic discover, or the method's own tool)
| `unit.source` | `unit.source_config` | Init field the user fills |
|---|---|---|
| `list` | `[]`, or the names as soon as the user gives them | `units`: the names, e.g. `["Supplier A", "Supplier B"]` (entries may be objects with `name`, `group`, `depends_on`, `size`) |
| `workbook` | `{"sheet": "...", "column": "<header>", "group_column": "<header>", "header_row": 1}` (`sheet`, `group_column`, `header_row` optional) | `units.file`: the client workbook; one unit per distinct value of the column |
| `folders` | `{"root": "input/<folder>", "per": "folder" \| "document"}` | – (one unit per sub-folder, or per document) |
| `inventory` | `{"table": "...", "name": "...", "group": "...", "depends_on": "...", "size": "..."}` (each optional) | – (an inventory step finds and verifies the units first; its review must pass before the units start) |
| `tool` | `{"tool": "<tool name>"}` (default `discover`) | whatever the tool reads: the method's own `tools/<tool>.py` writes the unit list (§6); `method check` refuses the method while the tool is missing, and the generator never overwrites it. A copy of a plugin method (`method new --from`) starts with this source and that method's tool and smoke. A tool written for a custom method needs its own fictional fixture and `smoke.sh` too (§6). |

`unit.dependencies`: `independent` → all units in parallel, `dependent` → a unit waits for the units it depends on, `grouped` → waves by group.

### 4.2 Rows of the workbook
Every `table` topic becomes a dataset of rows (one per table row of every unit's analysis). Every unit becomes one row with its other
fields. Workbook columns are filled from `<topic id>.<field>` (`from`). A consolidation's tables become datasets the same way.

### 4.3 Outside experts (standard critics)
- Each entry of `evidence.standard_critics` becomes its own critic `standard-<id>`, with the persona, sources and topics given. The id is lower-case letters, digits and hyphens.
- `scores: "all"` gets every claim. `{"topics": [...]}` gets the claims of those topics.
- Every claim needs at least one expert, otherwise the check refuses the method.
- The client critic always scores every claim.
- Domains are named in the expert's brief. All experts and the researcher share one allowlist of web domains.
- The plugin methods' default is one expert with `scores: "all"`. Explain any deviation from it.

### 4.4 Example run (smoke)
- `dbcx smoke <name>` generates an invented example from the method itself: units, one analysis per unit and per cross-unit view, passing reviews and a gate file.
- It then runs the whole chain up to the workbook and the handover export.
- It runs in a temporary folder outside the engagement. The last line names the folder, and the workbooks are in `<folder>/<name>/deliverables/`.

### 4.5 Personas and packs
- Personas (B1, D2): `ceo`, `cfo`, `cio`, `cto`, `enterprise-architect`, `head-of-ecommerce`, `head-of-it`, `head-of-marketing`, `head-of-sales`, `product-owner`, `project-manager`, `team-lead`.
- Knowledge packs for the outside experts: `dbcx pack list <kind>` (platforms, catalogues, reference architectures).

## 5. Costs to name (never caps)

| Choice | Cost to mention |
|---|---|
| each further outside expert (standard critic) | another agent per unit and review round |
| each unit | an analyst, the client critic and the outside experts, per round (up to the round limit) |
| each cross-unit view | a consolidator and its review |
| each further workbook or reader | more to build and more gate reading (one gate agent per persona and gate round) |
| many topics or columns | longer analyses, more claims to review per unit |
| `run_options.lean` | cheaper for a document collection; fewer review rounds |
| an inventory step | one more reviewed phase before the units start |

Say the cost once, in one sentence, and accept the user's choice. "After the first run" is the user's choice to make, never your request.

## 6. Method files and own Python

`dbcx method generate` writes the method pack into the method folder from the card:
- `method.json`: phases from the fixed skeleton, units, evidence, critics, consolidations, artefacts, lint.
- `kinds.json`: the analysis templates.
- `deliverables.<lang>.json`: sheets, formulas, Parameters.
- `labels.<lang>.json`, `briefs/<role>.md`, `plan.md`.
- the smoke.

Do not edit these files by hand. Change the card and generate again.

**Derived methods are the exception.** A copy of a plugin method (`dbcx method new --from`, card `origin.type` `derived`) is never
regenerated: `generate` refuses it without `--force`, and the skill never forces it. Change its copied files directly and keep the method
pack contract. The copy itself is the template to follow:
- `method.json`: phases, units, evidence bases, critics, consolidations, artefacts, lint.
- `kinds.json`: sections and fields; a new column needs the field it is filled from.
- `deliverables.<lang>.json`: sheets and columns. Every aggregate is a formula. Change every language.
- `labels.<lang>.json`, `briefs/<role>.md`, `plan.md`.
Record the change on the card (`--set`), then run `dbcx method check <name>` and `dbcx smoke <name>`. The copy keeps its own smoke and fixture:
when a change adds a sheet, a topic or a field, extend the fixture so the example run fills it.

Write method Python only for a need the building blocks of §4 do not cover. It stays within the contract, and regeneration keeps it:

| File | When |
|---|---|
| `tools/discover.py` (or the name in `unit.source_config.tool`) | unit source `tool`: unit logic none of the four ready sources gives; it writes `state/scopes.json` (`{"noun", "method", "scopes": {<id>: {"group", "depends_on", "size", "light", "skip", "meta": {LABEL: value}}}}`) |
| `datasets.py` | computed rows; it may `import generic_datasets` and extend its `DATASETS` |
| `tools/<name>.py` | a method tool (a diagram, a special conversion), callable as `dbcx <name>` |
| `inputs.py` | enriching an imported requirement list |
| `validate.py` | method rules checked when an analysis is converted (`check(kind, data, cfg)`) |
| `briefing.py` | extra brief context per role |
| `critics.py` | an expert set computed from the run's configuration (rare; declared experts usually suffice) |

Import convention:
- Import the engine by name (`import common`, `from common import RUN as ROOT`).
- Never climb out of the method folder with `dirname(__file__)` chains. Paths to the method's own files stay relative to `__file__`.
- A tool that can also run as a plain script starts with `if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("run it through dbcx"))`.

**An own unit tool brings its own smoke.** The ready-made example run only works with the four ready sources. When you write a unit tool,
also write `fixtures/make_fixture.py` (invented units and material, never client names) and `smoke.sh` in the method folder. `method check` refuses
the method without them. `smoke.sh` gets `TOOLS`, `PLUGIN`, `TMP` and `LANG_` from the engine's smoke runner. It runs a toy run through the whole
chain: init, the unit tool, `plan_waves`, `md_to_json` of every kind, `extract_claims`, `score_aggregate`, `gate_aggregate`, a brief for every
role, `build_excel --all`, lint and the handover export. Start from the plugin's `engine/generic_smoke.sh` and `engine/generic_fixture.py`
(they show the chain step by step), and replace the generic unit step with the tool.

After writing Python, run `dbcx method check <name>` and `dbcx smoke <name>` again.

## 7. Guard rules (what they mean for the user)

- **Changes only between runs.** When a run starts, it stores a fingerprint of the method folder, card included. If the method changes during the run, the run stops with "the method changed during the run". To continue, undo the change, or start a new run.
  - A run counts as **open** when its run.json names this method, it has started (`state/STATUS.json` exists), it has no `docs/FINAL_REPORT.md`, and its final gate has not passed (a method without a gate: a phase is not done).
  - While a run is open, `method card --set/--postpone`, `method confirm` (with or without `--guard`) and `method install --update` refuse, and say why.
  - Note change wishes in that run's open items instead (`dbcx learn add --section F`), not in the method.
- **Agents never change a method.** The hook denies analysts, critics and every other sub-agent any write to the engagement's methods, its overrides and the personal library. It also denies them the method commands. The user and this session are not affected.
- **Looser than the plugin's methods.** `dbcx method check` shows the guard keys: who reads which evidence, public unit names, an expert pointed at client material, commands the run must never execute. It warns where the method is looser than every plugin method. Explain each warning in one sentence. Then either the user agrees (`dbcx method confirm <name> --guard` stores that yes with the method's fingerprint, so the check stays green) or the card changes.
- **Names.** An own method never reuses a plugin method's name.
- **Library copies.** A method installed from the library is a copy. A later library change reaches this engagement only through `dbcx method install <name> --update`, between runs.

## 8. Commands

| Command | Does |
|---|---|
| `dbcx method list` | plugin, engagement and library methods with origin and version |
| `dbcx method new <name> --from <plugin method>` | a derived copy in the engagement, card pre-filled |
| `dbcx method card <name> --init` / `--set <path>=<json>` / `--postpone <path> --why "..."` / `--render` / `--json` | create (name and origin pre-filled), answer, postpone, print the rendered card; `--json` lists the `open` and `invalid` slots (resume) |
| `dbcx method confirm <name>` | records the user's yes on the rendered card (refused while a slot is open) |
| `dbcx method confirm <name> --guard` | records the user's yes to the guard warnings of `method check` |
| `dbcx method generate <name> [--closest <plugin method>]` | card → method files (refuses an unconfirmed card) |
| `dbcx method check <name>` | files, keys, templates, workbook spec, experts, open card slots, guard report, name clash; exit 1 on error |
| `dbcx smoke <name>` | the example run (§4.4) |
| `dbcx method save <name>` / `dbcx method install <name> [--update]` | to the personal library (after a clean check) / from it |
| `dbcx init run --method <name>` | a run with the method (run skill, init) |
