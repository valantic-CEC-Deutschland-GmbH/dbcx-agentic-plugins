# Scoring protocol (gauntlet and final gate)

All numbers are real. Averages are floored to two decimals by `dbcx score_aggregate`, never rounded up. Failed rounds stay in `state/STATUS.json` and `analysis/gauntlet/<scope>/round<n>-*.md/.json`. Claim statements and critic issue texts are written in the deliverable language (they appear on the Excel sheet 'Claims'); critic summaries and reports are English. The final report lists every failed round and everything still open.

Thresholds and round limits come from `run.json` → `scoring` (engine defaults: pass ≥ 8.0, 4 gauntlet rounds, 2 light rounds, 3 gate rounds; a method pack may set other defaults).

## 1. Claims

Everything that ends up in a deliverable is a **claim** in the `## Claims` table of the Markdown analysis, with a stable id (`C-<scope>-NNN`, `C-<inventory scope>-NNN`, `C-<consolidation>-NNN`), a type, the statement, the evidence (repository paths, optionally `:line-range`) and the deliverable cell/row it feeds.

| type | meaning | examples |
|---|---|---|
| `fact` | verifiable against the client's evidence or external documentation | "unit X replaces the standard cart service via DI alias", "platform version is 6.5.8", "FR-023 is not covered by the current code" |
| `assessment` | judgement built on facts | "unit X is `heavy`", "feature Y `needs-redesign`", "FR-023 could use the standard product-reference type" |

Rules for analysts: no statement in a deliverable without a claim; no fact claim without a locator; every estimate states its decomposition, every percentage its denominator, every count its predicate; **one proposition per claim** - one fact or one judgement, at most two figures (a count and its basis), one target sheet, at most 350 characters (`md_to_json` warns; `scoring.claim_max_statement_chars` / `claim_max_figures`); specific and quantified beats generic, but a correct evidenced fact is an 8 and is never padded - the first engagement's round-1 failure share rose from 3 % for statements under 300 characters to 48 % above 1 000, and from 14 % with one figure to 50 % with seven or more, because one wrong figure sinks a whole paragraph and the incremental gauntlet then re-scores the paragraph; never restate the scanner's raw numbers as claims unless you corrected them.

**Quote (optional column `quote`).** One verbatim excerpt (≥ 20 characters, original language, fragments of one locator joined by `[…]`) from a cited locator that carries the statement; the evidence cell stays locator-only and the quote is not part of the claim hash (a changed quote alone does not re-open a scored claim). `dbcx evidence quotes <scope|all>` (run by `extract_claims` - under `warn` only when a claim carries a quote, under `required` always) looks it up word for word: lowercase letters and digits only, fragments split at `[…]` / `…` / ` – ` / ` | ` / ` / ` / line breaks, each ≥ 20 characters; text per locator: corpus `SRC-nnn#anchor` → the anchored block ± one block (anchors are coarse), `PS-7-NNN` → the row's stored quote (`dbcx reference add --quote`) + its URL's page through safe_web (help.sap.com through its content service), `KB-n` → the entry, `Q-`/`A-` → the answer, a repository or run path → the file with its `:from-to` range. Result per claim `verified | partial | not_found | unreadable | no_quote` in `analysis/gauntlet/<scope>/quotes.json` and as a `Quote check` block in the critic pack: a verified quote settles existence, the critics judge interpretation.

## 2. Gauntlet (per scope, per inventory, per consolidation)

Critics from two evidence sides score **every** claim independently, 0–10: exactly one client-side critic (`client`, every claim) and at least one standard-side critic per claim. With options on more than one technology pack (`run.json → options`, method
tech-fit-estimation) the standard side is one critic per pack, id `standard-<pack>`: it scores the claims whose target row belongs to one of
its pack's options (`D1/Schaetzung#FR-041@<option>`, or the row's `option` field) and every option-neutral claim; the client-side critic
still scores every claim. `extract_claims` records the applicable critics per claim, each pack critic gets its own critic pack and delta,
and `score_aggregate` counts unscored / stale / averages per critic over its own claims only. A single pack keeps the id `standard`.
A method may define the standard side from its own model through the hook `methods/<m>/critics.py` (tech-fit-estimation with
run.json `systems`: one critic per system option technology - `standard-<pack>`, a `_generic` option `standard-<system>`): the hook replaces
`standard` in the critic list, narrows the critics of one scope (an analyst chunk of one system option: client + that option's critic; a triage
chunk: client + the critics of the systems its rows name; an architect batch: client + the critics of the receiving systems of its
decisions) and routes each claim (a triage claim to the critics of the systems in its target's `@<system>` segments; an architect claim
`architect/decisions#<row>@<from>@<to>` to the critics of the receiving system <to>; a claim naming only `none`, a landscape system or
systems estimated outside the agents to the client critic alone).

**Declared standard critics** (`method.json → critics.standard`, no Python). A method names its standard-side critics by
discipline - vendor documentation, a norm, a regulation - each with its own persona, sources and topics:
`[{"id": "wcag", "persona": "...", "sources": {"packs": [...], "domains": [...], "reference": true}, "scores": "all" | {"topics": [...]}}]`.
- **Ids.** Each entry is critic `standard-<id>` (id `^[a-z][a-z0-9-]*$`, role `critic-standard`, agent `critic-standard-<id>-<scope>`). The
  placeholder `standard` in `scoring.critics` / `phase_critics` expands to the declared set, so run-level settings keep working. The entry
  `{"id": "standard"}` (no other key) stays the critic `standard` with today's expansion (one critic, per pack with run.json options, or the
  method hook `critics.py`); discipline critics sit next to it. A method without `critics` runs as before. A declared id that collides with
  a per-pack or hook critic id is refused. There is no upper limit; each critic is one more agent per scope and round.
- **Routing** (`extract_claims`, recorded per claim in `critics`). The client critic and a `scores: "all"` critic get every claim. A topic
  critic gets the claims whose topic keys (`common.claim_topics`, case-insensitive) name one of its topics. A claim's topic keys are:
  - the scope kind (`scoring`);
  - per target part, the deliverable (`D1`) and the sheet (`D1/Scores`, the text before `#` / `:`);
  - the sections of the scope's analysis its target rows resolve to (`capabilities`, `scoring.capabilities`; the exact row match of
    `engine/tools/rows.py`, so a target without a row id, `D1/Risks`, matches by sheet only).

  Claims carry no section and no column of their own, so a column is no topic. Section keys do not depend on the deliverable language and
  are the safer choice. Every claim must reach at least one standard critic. A claim that matches no topic still goes to every `scores: all`
  critic (and to `standard` when declared); with neither, `extract_claims` stops with an error naming the claims - a defect of the method
  (exit 1, before the register is written). Per-pack option routing applies to per-pack critics only; a method hook's `claim_critics` /
  `scope_critics` narrows only the critics it owns (`standard`, `standard-<pack|system>`) - a declared critic is never removed by
  the hook and stays subject to its own topics.
- **Scopes.** A topic critic scores a scope only when the scope's latest register routes a claim to it (`common.scope_critics`; before the
  first extraction it is listed). Each declared critic gets its own `claims-<critic>.md`, `claims-delta-<critic>.md` and
  `critic-pack-<critic>.md`, and `score_aggregate` decides the pass over every critic of the scope, each over its own claims.
- **Briefs.** `render brief critic standard-<id> <scope> <round>` shows the declared persona (`{a.b}` filled; the method's standard persona
  when empty), YOUR CLAIMS (all, or the topics), the knowledge packs with their `NOTES.md`, the web domains and the reference file - or the
  note that the reference file is not one of its sources (`reference: false`, the REFERENCE row is dropped). The METHOD NOTES block holds the
  role's `notes_keys` from each of its packs' snippets (one block per pack; without packs the run's notes as for `standard`).
- **Evidence.** The hook keeps one role for every standard critic: client evidence stays denied, standard critics may overlap with each
  other. Per-critic domains are stated in the brief, not enforced: the declared domains and the packs' `docs_domains`
  join the `safe_web` allowlist, which every standard critic and the researcher share.

**Scoring grounds and disputes** (opt-in, `scoring.dispute_routes`; tech-fit-estimation 0.3.0). A method may add a `ground` column to the
critic table (kinds.json `extend.critic`): the client critic names what it judged (requirement-reading | current-shop | effort-driver |
size-plausibility) and the method's CHECK refuses a low score without one. A ground listed in `dispute_routes` (`{"standard-dispute":
"standard"}`) is a doubt about the other side's half - no score: `score_aggregate` moves the row to the critic file's `disputes`, keeps
the critic's carried score or leaves the claim out of that critic's count this round (it is never unscored), lists it in result.json
`routed` and in the issues file; `extract_claims` puts the claim into the next round's delta with the dispute, and the named critic's brief
shows DISPUTES ROUTED TO YOU. Its answer is a reference-row correction or a note; a scope that passed gets it as a continuation message.

| score | client-side critic (the client's own evidence only) | standard-side critic (external standard, best practice) |
|---|---|---|
| 10 | positively surprised that you found this | uses standard knowledge most consultants miss (version-specific, edge case) |
| 8 | understandable and reasonable, evidence checks out | correct against the standard for the target version, reasonable recommendation |
| 6 | true, but you do not need to be an expert to see that | true, but generic; any developer on this platform would say this |
| 4 | I do not understand why this is true (unclear, unsupported, evidence does not show it) | not aligned with standard behaviour / best practice, or version not stated where it matters |
| 2 | provably false in the codebase | provably wrong against vendor documentation (feature exists / does not exist, wrong version, wrong endpoint) |

Odd scores are allowed as in-betweens. Fact claims: the "6 = trivial" anchor does **not** apply; a correct, precisely evidenced fact is an 8, an imprecise or unevidenced one a 4, a wrong one a 2. Facts essential for the deliverable (e.g. classification counts) are expected, not penalised.

Critics also list **missing claims**: things the analysis should say and does not (each becomes a ranked issue).

**How a finding was found** (optional column `found_via` of the critic score table): `grep | search | read | map` - the tool that
turned up the counter-evidence or the doubt (exact grep over `corpus/text/`, `dbcx corpus search`, a full read of a mapped source, the corpus map),
empty when the row needs none. It never changes a score or the pass: it is a retrieval metric, counted per unit in `state/RETRIEVAL.json`
(`dbcx corpus metrics`). Every critic's score file may carry it, a declared standard critic's too; a standard critic has no corpus access,
so its rows normally stay empty.

**Pass** is decided by the run's `scoring.pass_rule`:

- **`defects`** (default for new runs): every claim scored or carried, **no claim with verdict `false`** and none scored ≤ 2, **no `unsupported` with counter-evidence**, and at most max(1, `scoring.max_imprecise_share` (10 %) of the claims) **imprecise** claims – verdict `imprecise`, or `unsupported` without counter-evidence below the threshold (the standard critic's "unsupported, carried at 8" for a client half it cannot see is not a defect) – each carrying an owed text fix (an `issue` or `fix_hint`). On a pass the tolerated imprecise claims become owed text fixes in `notes_on_passing_claims` (the post-pass brief's items). The averages, minimum and below-threshold share stay in `round<n>-result.json` as information; they no longer decide. Rationale: 82 % of all scorings are exactly 8, so a mean ≥ 8.0 was decided at the arithmetic boundary (one scope in three passed at exactly 8.00, a light scope with 10 claims absorbed no defect, carried 8s lifted averages); the client needs "nothing false, nothing unsupported", which the defect rule states directly.
- **Quote gate (`claims.quotes: required`):** on top of either rule a `fact` claim whose quote is `not_found` at its locators is a blocking defect (issue by `quotes`, like `unsupported` with counter-evidence); under `defects` a claim without a quote counts toward the imprecise limit (its owed fix is the quote; on a pass it becomes an owed text fix). `partial` and `unreadable` are shown to the critics, never decided by the tool. score_aggregate refuses without a `quotes.json` of the snapshot's analysis version. Under `warn` (engine default) and `off` the quote status changes no score and no pass.
- **`defects+quotes`** (the `lean` profile): the `defects` rule with the quote gate always on (as under `claims.quotes: required`) and **every evidence locator resolving** (`dbcx evidence check`; a dangling locator is a blocking defect, issue by `locators`). These deterministic checks are what lets a gauntlet run with **one critic or none** (`scoring.phase_critics`): under `lean` the inventory has no critic and passes on its CHECK, its verbatim quotes (no fact claim `not_found`, missing quotes within the imprecise limit) and its locators; each consolidation has the standard critic only - the client-side facts are carried by the quotes, the critic judges interpretation against the external standard. `max_gauntlet_rounds: 1` plus `defect_rework_rounds: 1`: a failed round whose reasons are all defects (not a missing critic file or unscored claims) gets one rework round, with the register frozen after round 1. The final gate is unchanged.
- **`mean`** (runs whose run.json has no `pass_rule` and an `engine_version` of an older engine – an engagement's rule never changes silently; or set explicitly): average ≥ threshold for **every** critic, every claim scored or carried, no claim ≤ 2, no verdict `false` (or `unsupported` with counter-evidence, `scoring.block_unsupported_with_counter_evidence`), and no more than `scoring.max_below_threshold_share` (default 20 %) of the claims below threshold for any critic.

`dbcx score_aggregate <scope> <n> --dry-run --rule defects|defects+quotes|mean` shows what the other rule would have decided without writing anything. Under both rules `false` is a verdict, not a score: a critic that checked and found the statement contradicted marks it `false` even when it scores 4 – a 0-2 score means fabricated, not merely refuted, and passes let refuted statements through otherwise. A claim is listed **either** as an issue **or** as a note: a note of one critic on a claim another critic raised as an issue is merged into that issue ("also noted by"). A fix hint that names a locator or identifier the claim does not carry is tagged **NEW in this hint** – the analyst reproduces it before adopting it. A spread of ≥ `scoring.critic_divergence_flag` (3) points between any two critics on one claim becomes an issue even on a PASS: that is where factual disputes live (the client critic prevails on facts about the client's estate, the standard critic on facts about the external standard). After the last round the scope is marked `failed-gauntlet` in STATUS with the remaining issues and continues into the deliverable with those issues listed on the Claims sheet. Never silently drop a failing claim to lift the average; a claim may be removed only if the critic showed it to be false or irrelevant, and the removal is logged (`supersedes`).

Anti-gaming rules for critics: score the statement as written, not the intent; the client critic may only use the client-side evidence bases and the analysis; the standard critic may only use external documentation / knowledge packs and the analysis, never the client's evidence (hook-enforced) – and for every passing claim it names which half is standard and which is client, underwriting only the standard half; a critic that scores everything ≥ 8 in round 1 must say why in `summary`, and the orchestrator spot-checks 3 random claims. A confirmation is scoped to what was recomputed ("figures X, Y, Z reproduce"), never universal; a fact claim whose own enumeration does not reconcile with its headline is imprecise regardless of how sound the surrounding reading is. `issue` text on a passing claim is a wording note collected as `notes_on_passing_claims` (text correction after the pass), never a rework by itself. `Estate observations` carry facts established outside the scope to the consolidators and D0.

## 2a. Row ids and coverage

`md_to_json` gives every table row a stable `rid` (the row key itself when it is an id such as `FR-012`, `F-001` or a class name; otherwise `r` + 8 hex digits of the hash of the normalised key text – kinds.json `row_key`, else method `gauntlet.row_tables`, else the first field; a kv section is one row with the scope name as id) and `claimed_by` (the claims whose target names the row); the top-level `claimed_rows` map covers kv sections too. A claim backs exactly the rows its target names: `D2/Patched#r1a2b3c4d`, `D3/Coverage#FR-012,FR-013` or `<kind>/<section>#<rid>`; the legacy `:` separator and the exact row key value are accepted; method.json `claims.sheet_tables` maps a sheet to the section(s) it shows. Coverage is an **exact row-id match** – the earlier 60-character substring matcher, and with it the practice of opening statements with verbatim row keys, is gone. `extract_claims` fills the register's `rows_without_claim` and `must_claim_uncovered` (never the analyst) and writes `coverage-round<n>.md|json`. Cross-scope claim ids (`C-<scope>-NNN`) resolve as evidence when that scope is final or the claim is in the inventory handover.

## 2b. Incremental gauntlet (round 2 and later)

`dbcx extract_claims <scope> --round <n>` hashes every claim (statement + evidence + target), snapshots the register per round and writes `claims-delta.md` and `critic-pack.md`. In round n ≥ 2 the critics score **only** the delta: new claims, changed claims, and unchanged claims that were below the threshold in round n-1. Every other claim keeps its round n-1 score: `dbcx score_aggregate` carries it forward into the critic's JSON (`carried_from_round`) before computing the average, so the pass rule is unchanged (every claim scored or carried; under `mean` every average ≥ threshold, under `defects` no false/unsupported-with-counter-evidence and the imprecise tolerance). A critic may still re-score a carried claim when it holds new counter-evidence and says so in `issue`.

Caps (run.json → `scoring`): when the method declares must-claim verdict cells (method.json `claims.must_claim: {"<kind>.<section>": [fields]}` – e.g. disposition, coverage verdict, migration-task impact, security flag), the cap is **derived**: must-claim rows + `scoring.claim_cap_reserve` (5), never above the fixed cap `max_claims` per scope (engine default 40; the code-analysis method sets 60 because its claims are atomic), `max_claims_light` (10) for light-pass scopes or `max_claims_consolidated` (120); without a declaration the fixed cap applies. Atomic claims are never merged into paragraphs to stay under the cap: at cap, the remaining finding goes into the fitting non-claim section and the trade-off to the orchestrator; `max_missing_claims_per_round` (3) per critic and round – most important first, the rest is dropped by the aggregator; `freeze_register_after_round` N (2) – **rounds > N** fix, they never add (round N itself may still add); missing claims raised after the freeze are recorded as deferred for the FINAL_REPORT. The freeze changes what a round can do, not whether to run one: a post-freeze round can still fix and re-score, which is better than an unverified text correction.

What carrying forward means: `carried_from_round` records the provenance of a score, not the depth of verification behind it – a carried claim is unexamined since that round, not corroborated. Therefore: a **changed** claim is re-scored as a whole statement (the diff says where to look first); the delta names the round in which each claim was last fully scored; the client critic opens the evidence cells of `scoring.carried_evidence_sample` (5) carried claims per round; the pack ships a **coverage report** of table rows no claim targets (they were never graded) and of must-claim cells without a claim and, from round 2, a **reference delta** (section-7 rows added since the previous round – the standard a claim was judged against may have moved; a carried claim such a row narrows is re-scored). The pack and snapshot carry the source file's hash: `score_aggregate` refuses when the live analysis differs from what the critics were given, when a DIRTY marker says the file was edited during the round, or when the previous round's checksums no longer match; `--dry-run` computes without writing.

Light gauntlet: light-pass scopes are scored by the client critic on `models.critic_client_light` for at most `scoring.max_gauntlet_rounds_light` (2) rounds. Critics persist per scope: rounds ≥ 2 are messages with the new delta to the same agent.

Critics read the critic pack (key sections of the analysis + the register or delta) and open the full analysis or the repository only for what a claim points to. Score files are checksummed by `score_aggregate`; `build_excel` refuses a score file changed afterwards.

**Post-pass CHECK (A8).** A passed scope gets text-only corrections from the post-pass corrector (no evidence access). `dbcx render brief postpass <scope>` snapshots the rows (`postpass-baseline.json`); `dbcx postpass check <scope>` diffs the corrected analysis against the scored register of the last aggregated round and refuses an added/removed claim id, a changed statement/evidence/target without a row in `postpass-justifications.md` (kind `postpass`: justification + how the critic's `accept_if` is kept), and a change that drops a figure, locator or id both the `accept_if` and the scored text carry (that needs a re-score, or `--accept <ids>` by the orchestrator). Locators neither the register, the issues nor the baseline contain are listed as UNVERIFIED for the owning role; changed table rows are logged in `postpass-check.md`. The corrector reports in its final response.

## 3. Final gate (three layers, on the customer edition)

The gate reads what the client receives and nothing else: the customer-edition workbooks at the top of `deliverables/` (never
`deliverables/intern/`, the analyses or internal work - the gate roles see only the engine evidence bases `customer-edition` and
`gate-io`), recalculated and rendered by `dbcx render_workbook` (Excel via AppleScript: cached values, a PDF and one PNG per page under
`work/render/<date>/<D>/`). Each layer is judged by whoever can actually judge it.

1. **Hygiene - tool, binary.** `dbcx lint_deliverable --standalone --all --round <n>` (report `analysis/gate/round<n>-hygiene.json`):
   process vocabulary (DE + EN) and internal locators, dangling `C-`/`Q-`/`PS-7-` ids, references to sheets not in the workbook, raw keys,
   bound columns >= 95 % empty, typed numbers in summary prose, literal aggregates, formula errors and reconciliation of summary/overview
   aggregates with the detail sheets (cached values; a WARNING without them), `Grundlage` proofs (Code -> repository locator, `[Qn]` ->
   Quellen row with a title in the deliverable language, `A-nn` -> Annahmen row without the default wording), emphasis budget, header tiers,
   freeze, filter, print setup, tab colours. `dbcx render brief gate|verifier` refuses while it fails. Personas do not score it.
2. **Truth - `gate-verifier`** (balanced_review; the client's repository read-only + the customer workbooks). Works through a tool-drawn
   sample of about 15 rows per deliverable (`dbcx gate sample`: figures, verdicts, security rows, `Annahme` rows, `Code` rows, round-robin
   over the sheets) and checks locator => statement; results confirmed | imprecise | unsupported | false | no-locator | assumption-in-code;
   a score 0-10 per deliverable (10 all confirmed, 8 at most one imprecise, 6 several imprecise or one unsupported, 4 more unsupported,
   2 a false verdict or figure, 0 several false) plus located defects.
3. **Value - personas on their key questions.** Each persona scores 3-5 key questions `{id, text, deliverables, tags}` (method
   `gate.key_questions`, tailored per engagement in run.json / engagement.json `gate.key_questions`; engine default
   `engine/defaults/gate.defaults.json`) and reads only the deliverables its questions name. Anchored scale, identical for every persona:

| score | the key question is ... |
|---|---|
| 10 | answered on the Management Summary with a figure, its consequence and its basis |
| 8 | answered in the relevant sheet with at most one filter; the basis is visible in each row |
| 6 | answerable, but only by combining sheets or reading many rows |
| 4 | partial or ambiguous |
| 2 | not answerable |
| 0 | answered wrongly or misleadingly (two cells contradict each other, or the verifier confirms a false row) |

   Plus, unscored: a **board test** (forward unchanged? which issues block) and **what is missing**. Issues have no minimum count; each
   carries a location, a `kind` (content | presentation | structure | language | outside-scope), a severity (blocker | major | minor), the
   key question it hurts and a proposed change. `tags` (understand | prove | act) keep a cross-run rollup possible without steering the gate.

**Pass** (`dbcx gate_aggregate <n>`) = hygiene clean ∧ every verifier score >= `pass_threshold` ∧ per persona mean over its key questions
>= `pass_threshold` ∧ no key question < `scoring.gate_question_floor` (7) ∧ no blocker ∧ no major cluster without a recorded lead decision
(`dbcx gate decide <n> <cluster> "..."`, stored in STATUS `phases.<gate>.decisions`, carried to a later round's cluster with the same key).

**Fix plan.** `gate_aggregate` clusters the issues of all personas, the verifier and the hygiene layer (same deliverable | sheet | kind and
similar text; sheets identical in every workbook count once; an engine-level hygiene check is one cluster) into
`analysis/gate/round<n>-fixplan.md|json`: severity, mechanism (spec/override, label, summary/Kernaussage text, content + mini gauntlet,
lead decision, engine), owner, acceptance test, and "unchanged since round k" (a fix that did not land is escalated, never repeated). The
`deliverable-editor` (deep_reasoning) executes it through run overrides (id-keyed patches), labels, the management summaries (written after
the build with `{kpi:id}`) and the Kernaussage sidecar `analysis/summaries/key_statements.json`; content items go back to the orchestrator for the owning role and a mini gauntlet. There
is no won't-fix list: every blocker and major cluster is fixed or escalated before the next round. Non-content clusters come with a
suggested `dbcx learn add` line. From round 2 a persona gets its own previous issues and the tool diff of the customer workbooks
(`dbcx gate diff <n>`, from the per-round snapshots `analysis/gate/round<n>-workbooks/`) - never orchestrator prose. STATUS
`phases.<gate>.rounds[]` keeps every round.

**Question feedback (the lead on a key question).** On the dashboard's gate section the lead can send feedback on a key question of the
current round (inbox kind `gate_question_feedback`: answered outside this study - dismiss it | asks the wrong thing - rephrase it |
something else, plus a text). The orchestrator decides and records it with `dbcx gate question <persona> <qid> --reword "<its own
question>" | --dismiss | --keep --why "<reason>" --feedback <client_id>` (STATUS `phases.<gate>.question_changes[]`, which closes the
inbox entry). It reacts to the feedback and writes the question itself - the lead's wording is never pasted (the tool refuses an identical
text). A change applies from `from_round`, the first round whose persona briefs are not rendered yet; a round in progress or finished is
never changed. `dbcx gate questions --round <n>` prints the questions as asked in round n: the gate brief, `gate_aggregate` (a dismissed
question leaves the mean and the "all key questions" criterion) and the dashboard read the same per-round list. `dbcx status next` lists
open feedback before it prints the next round's persona briefs.

## 4. Persisted state

`state/STATUS.json` – phases, per-scope rounds/scores/pass, `in_flight` agents (written by the Agent hook, cleared by the delivery test), open issues, assumptions, feedback, history. Scope states: open · analysing · gauntlet · rework · passed · passed-rework-ordered (a round ordered on a passing scope) · final · failed-gauntlet · skipped. `dbcx status verify` compares the file with disk; `dbcx status next` is status-driven and refuses "nothing to do" while work is owed. Round results are recorded **idempotently by round number** (re-aggregating replaces, never duplicates). Critic score files are closed once aggregated: `md_to_json critic` refuses to overwrite them, the hook denies edits, `build_excel` verifies the checksums.


## 5. Estimates, percentages and scores (methods without code)

An effort in person days is an `assessment` claim whose statement names the mechanism it rests on; the row's `effort_basis` carries the decomposition and the assumptions - the client critic checks that the decomposition covers the requirement as written (incl. exclusions, no double counting with technical requirements), the standard critic checks that the mechanism exists in the named version/plan and that the effort is plausible for it. A coverage percentage names its denominator (e.g. 3 of 5 acceptance criteria). A strategic score names its anchors and both locators (client context and vendor documentation). Consolidators calibrate across parallel scopes and list every changed row by id; changed rows re-enter the next critic brief.

## Lead input: `accept_if`, lead facts, amendments

- **`accept_if`** (mandatory below the threshold) is the test the critic will apply next round: what the corrected statement must state or cite to pass. Written before the critic sees the fix, it keeps the judgement independent and turns the fix hint (a hypothesis) into a checkable contract. The issues file shows it as "passes next round if"; the dashboard shows it per claim.
- **Lead facts.** The engagement lead can dispute a critic's evidence from the dashboard. As a `critic_fact` the statement is binding for the engagement: `dbcx inbox apply` writes it into `analysis/briefs/lead-facts-<scope>.md` (rendered into every critic brief of the scope as LEAD FACTS) and, for the standard critic, into section 7 of the reference with provenance `lead`. The critic scores against it and records the conflict in `issue`; a `false` verdict may not stand on the strength of the overruled source. The researcher re-verifies `lead` rows on `refresh`; the final report lists them. A `critic_hint` is only a re-check request: the critic keeps its own score.
- **Amendments.** A closed round is re-opened only this way: the critic writes ONLY the re-scored rows into `round<n>-<critic>-amend.md`, the orchestrator converts it and runs `dbcx score_aggregate <scope> <n> --amend <critic>`. The original score file is kept as `round<n>-<critic>.pre-amend<k>.json`, the amended rows carry `amended_from` and `amendment`, the result records `amendments`, checksums are recomputed. Guard 1 (live text moved) is not applied to an amendment - the snapshot is what was judged. If the recomputed round passes, the analyst's rework in progress is stopped and discarded; if not, the analyst is told which claim is settled.
- **Knowledge base.** `state/KNOWLEDGE.json` holds knowledge that matters to more than one scope (`applies_to` = `*` or ≥ 2 scopes), one statement per entry in the orchestrator's words. Weight and type mean what they mean for answers (`questions.type_of`): `client-fact` / weight `fact` is binding like a lead fact for the critics and a given for the analysts, `working-assumption` / weight `proposal` is weighed against the evidence, `decision` / `cross-scope-finding` carry their recorded weight. A claim may cite `KB-n` (`KB-H-n` after a handover import) as a locator of kind `kb` with the entry's weight - a client-fact carries client-evidence weight; a superseded entry does not resolve. The standard critic sees only entries marked `standard` (they passed the external-leak check); gate roles, the verifier, the editor, the post-pass corrector, the researcher and the progress reporter see none. The knowledge base never changes the evidence access matrix, and lead hints stay hypotheses for the analysts only.
- **Lead hints** (`analyst_hint`) reach the analyst only (LEAD HINTS block of the next brief, or a message while it runs) and are hypotheses like every other hint. The lead never rewrites a claim and never influences a critic through this channel.
