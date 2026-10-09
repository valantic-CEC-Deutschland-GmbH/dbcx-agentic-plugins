# NOTES – cms-requirements

Provenance: hand-written reference catalogue, created 2026-09-08. It is NOT derived from any client, project,
workshop or deliverable, and it is not converted from a vendor document. The content is general
content-platform / DXP architecture practice: the areas, the entries and above all the `notes` column are
written from experience of what content projects get wrong, not from a product feature list.

Nothing here is product-specific, so no statement carries `*(verify)*`: there are no version numbers, prices
or vendor feature claims to verify. Product-specific facts belong in the platform packs under
`knowledge/platforms/`, and confirmed per-engagement facts go into `reference-cache.md` via `dbcx learn export` to the maintainer.

Id allocation:
- Pattern `<AREA>-NNN`, where `<AREA>` is the area prefix (`CMS-MOD`, `CMS-EDIT`, `CMS-SITE`, `CMS-DAM`,
  `CMS-PERS`, `CMS-API`, `CMS-SEO`, `CMS-PREV`, `CMS-PERM`, `CMS-INT`, `CMS-NFR`) and `NNN` is a 3-digit
  number allocated per area starting at `010` in steps of 10.
- The step of 10 exists so a new entry can be inserted between two existing ones (e.g. `CMS-MOD-045`) without
  renumbering anything downstream.
- Ids are permanent. An id keeps its meaning for the life of the pack; a retired entry is struck through or
  removed but its id is never reused for a different capability, because engagement deliverables cite these ids.
- A new area gets a new prefix and starts again at `010`. Never renumber an existing area.
- The pack contract writes this scheme as `CAT-<AREA>-NNN`. Here the area prefix already carries the
  catalogue namespace (`CMS-...`), so the redundant `CAT-` is omitted: the ids stay globally unique and do
  not collide with the `CAT-CMS-NNN` area of the e-commerce requirement catalogue, which covers content
  from the commerce side.

WARNING - how this file must and must not be used: this catalogue is a SEED for elicitation and a completeness
check only. It must never be shipped to a client as their requirements, pasted into a requirements deliverable
wholesale, or presented as an analysis result. Doing so hands the client a generic checklist under their own
name, and any entry that was never discussed with them becomes a fabricated requirement. Per engagement:
select the entries that apply, reword them in the client's language, attach the client's real volumes,
thresholds and systems, and add what is missing. Unselected entries stay in the pack.

What a researcher should resolve first when using this pack:
- Whether the engagement is headless/decoupled or coupled - it changes CMS-API, CMS-PREV, CMS-PERS-040,
  CMS-SEO-070 and CMS-NFR-030 from optional to central.
- The real content volumes (entries, assets, locales, sites) before any NFR entry is given a number.
- Who owns personalisation segments and product data, since CMS-INT and CMS-PERS depend on that answer.
