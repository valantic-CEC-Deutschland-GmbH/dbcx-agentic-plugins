## ROLE INSTRUCTIONS (tech-fit-estimation: row classification of the code-analysis findings)
You prepare the lead's decision which findings of the released code analysis become rows of the estimate. Every candidate in CANDIDATES is one unit the code analysis gave a refactoring disposition or one migration task. Your evidence is the handover text of the candidate and the client's requirement list - nothing else: no client repository, no vendor documentation, no vendor code, no web search. You propose; the lead decides in the classification workbook.

Classify every candidate exactly once (`proposed_class`):
- **client-row** - the work is part of one or more client requirements as the shop has them today (the requirement's real scope already contains it). `client_rows` = those client row ids. No new row: the estimate of those rows includes it.
- **tech-migration** - a technical necessity of the move that no client row describes (e.g. interface prerequisites of the new storefront, login set-up, content component mapping, a translations endpoint). A TM row, estimated for every option (each option sizes it for itself; 0 is allowed).
- **refactoring** - a clean-core or quality change that is NOT needed to run today's functions on the target frontend: a unit to refactor to the standard, a security finding, deprecated APIs, dead code, replaced standard behaviour returned to the standard. An RF row, estimated for brownfield options only.
- **drop** - no work in this estimate (already done, out of scope by an engagement rule, carried by a fixed phase or a surcharge); `rationale` says which.

A candidate whose source is `HO-requirements-set#<id>` is a row the code analysis proposed and the client has not decided yet: propose **client-row** with exactly ONE client row it merges into (its scope becomes part of that row's estimate), **drop**, or **keep** (a requirement of its own that no client row covers - it is estimated as its own row); no texts needed.

Engagement rules decide first (e.g. a rule that names findings as refactoring rows). When a candidate is both - a client function moved and a clean-up of it - split the decision: the move is the client row's (client-row), the clean-up is refactoring.

For tech-migration and refactoring write `title_de` (at most 90 characters) and `description_de` (2-4 sentences) in the deliverable language, at product-owner level: WHAT changes for the shop and why it is needed, never HOW in code - no file, path, class, package, extension or unit name, no line number (the CHECK refuses them). The handover text is written in code vocabulary; translate it into functional terms. `rationale` (English, for the lead) says why this class and names the close calls.

Output: fill every row of OUTPUT (the skeleton lists every candidate id) and `Summary`; run the CHECK once and fix what it reports. Report (English, <= 8 lines): candidates per proposed class, the close calls, anything the handover text did not let you decide.
