# NOTES – ipaas-requirements

Provenance: hand-written reference catalogue, created 2026-09-08. It is NOT derived from any client, project,
workshop or deliverable, and it is not converted from a vendor document. The content is general
integration-architecture practice: the areas, the entries and above all the `notes` column are written from
experience of where ERP-to-commerce integration programmes actually fail - the non-happy path - rather than
from any product's feature list.

Nothing here is product-specific, so no statement carries `*(verify)*`: there are no version numbers, prices
or vendor feature claims to verify. Product-specific facts belong in platform packs under
`knowledge/platforms/`, and confirmed per-engagement facts go into `reference-cache.md` via
`dbcx learn export` to the maintainer. Standards named in IPAAS-EDI (EDIFACT, ANSI X12, openTRANS/BMEcat, AS2, OFTP2,
Peppol, ZUGFeRD, XRechnung) are named as elicitation prompts only; the applicable message versions, country
scope and mandate dates must be confirmed per engagement, since they change on a regulatory schedule.

Id allocation:
- Pattern `<AREA>-NNN`, where `<AREA>` is the area prefix (`IPAAS-CONN`, `IPAAS-MAP`, `IPAAS-ORCH`,
  `IPAAS-ERR`, `IPAAS-MON`, `IPAAS-SEC`, `IPAAS-API`, `IPAAS-EVT`, `IPAAS-EDI`, `IPAAS-MDM`, `IPAAS-NFR`)
  and `NNN` is a 3-digit number allocated per area starting at `010` in steps of 10.
- The step of 10 exists so a new entry can be inserted between two existing ones (e.g. `IPAAS-ERR-045`)
  without renumbering anything downstream.
- Ids are permanent. An id keeps its meaning for the life of the pack; a retired entry is struck through or
  removed but its id is never reused for a different capability, because engagement deliverables cite these ids.
- A new area gets a new prefix and starts again at `010`. Never renumber an existing area.
- The pack contract writes this scheme as `CAT-<AREA>-NNN`. Here the area prefix already carries the
  catalogue namespace (`IPAAS-...`), so the redundant `CAT-` is omitted; the ids stay globally unique and
  do not collide with the `CAT-INT-NNN` area of the e-commerce requirement catalogue.
- Some entries deliberately cross-reference another id (e.g. IPAAS-EVT-050 to IPAAS-ERR-010). Keep those
  references correct when editing; they carry the argument that at-least-once delivery is only acceptable
  together with idempotent consumers.

WARNING - how this file must and must not be used: this catalogue is a SEED for elicitation and a completeness
check only. It must never be shipped to a client as their requirements, pasted into a requirements deliverable
wholesale, or presented as an analysis result. Doing so hands the client a generic checklist under their own
name, and any entry that was never discussed with them becomes a fabricated requirement. Per engagement:
select the entries that apply, reword them in the client's language, attach the client's real interfaces,
volumes, thresholds and system names, and add what is missing. Unselected entries stay in the pack.

What a researcher should resolve first when using this pack:
- The interface inventory (IPAAS-CONN-090) and attribute-level data ownership (IPAAS-MDM-010). Comparing
  iPaaS products before both exist produces a shortlist that cannot be defended.
- Whether trading partners / EDI are in scope at all - IPAAS-EDI is the largest cost swing in this catalogue
  and is entirely out of scope for many B2C engagements.
- Real peak volumes and the largest payload, before any IPAAS-NFR entry is given a number.
