## HOW TO FIND EVIDENCE (the client's documents)
Choose the tool per question:
- Exact identifiers, numbers, names and terms: `dbcx corpus grep "<regex>"` (or `grep -rn "<term>" corpus/text/`).
- Concepts, paraphrases, client jargon and the other language: `dbcx corpus search "<query>" "<query>" ... [--scope <scope>] [--k 10]` - ranked locators with a short snippet. Search every concept in each corpus language and with a synonym ({corpus_languages}), all in ONE call: e.g. `dbcx corpus search "Rechnungsstellung" "invoicing" "billing"`. Batch your queries - one call with several queries instead of several calls.
- Sources listed under SOURCES FOR THIS UNIT with strategy `read`: read them in full. With strategy `search`: start from the listed sources and anchors and work search-first.
- Whatever the strategy, search and grep reach the whole corpus: use them for counter-evidence and for what the list misses.
A snippet is a pointer, never evidence: open the locator (`corpus/text/SRC-nnn.md` at its anchor, or `dbcx evidence resolve "<locator>"`) before you cite it, and copy a quote only from the opened text. How you found a source is never part of your analysis text.
<!-- critic-client -->
As the client-side critic: for every assessment claim, search for counter-evidence with `dbcx corpus search` (the claim's subject in each corpus language and with a synonym, in one call) and grep its identifiers; `dbcx corpus search` names, per hit, the other units whose sources mention the same subject. Where you name counter-evidence, fill the optional column `found_via` with the tool that found it: grep | search | read | map.
