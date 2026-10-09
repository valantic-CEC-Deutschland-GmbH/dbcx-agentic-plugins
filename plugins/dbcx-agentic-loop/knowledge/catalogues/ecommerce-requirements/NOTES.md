# NOTES – ecommerce-requirements

## Provenance
- Hand-written reference catalogue, created 2026-09-08. It is **not** derived from any client engagement,
  any client requirement list, or any single platform's feature documentation, and it contains no client
  names or client-specific process detail.
- The content is generalised delivery experience from B2B and B2C commerce programmes: the capability set,
  the usual FR/TR/NFR classification, and the questions that in practice decide scope and effort. The notes
  column carries the judgement; the capability column carries only a neutral starting formulation.
- Nothing here is a verified fact about a product. Where an engagement confirms a platform-specific fact
  while using this catalogue, that fact belongs in the relevant platform pack's `reference-cache.md`, not here.
- `reference-cache.md` in this pack is intentionally empty. It exists for facts about the catalogue's own
  external anchors (for example a legal or standard reference such as an accessibility conformance level or a
  classification standard version) once an engagement has verified them with a URL and a date.

## Id allocation
- Ids are `CAT-<AREA>-NNN` with a three-digit number, allocated per area from 010 in steps of 10.
- The 13 areas and their prefixes are fixed: `CAT-CAT`, `CAT-SRCH`, `CAT-PRC`, `CAT-CART`, `CAT-PAY`,
  `CAT-OMS`, `CAT-CUST`, `CAT-CMS`, `CAT-MKT`, `CAT-INTL`, `CAT-INT`, `CAT-NFR`, `CAT-OPS`.
- Ids are stable and are cited by engagements. Never renumber, never reuse a retired id, and never change
  the meaning of an existing id. A capability whose meaning shifts gets a new id.

## Current size (2026-09-08)
178 entries: CAT-CAT 18, CAT-SRCH 12, CAT-PRC 15, CAT-CART 16, CAT-PAY 10, CAT-OMS 12, CAT-CUST 24,
CAT-CMS 10, CAT-MKT 9, CAT-INTL 8, CAT-INT 18, CAT-NFR 17, CAT-OPS 9.

## How to extend it
- Insert between existing entries using the free numbers (011-019 style is allowed if a step of 10 is
  exhausted); otherwise append at the end of the area with the next multiple of 10.
- A new entry is only worth adding if its notes cell contains a discriminating question, a classic trap, or
  the fact that decides effort. Entries whose note would read "important" or "must be clarified" are noise
  and must be rejected in review.
- One capability per row, testable and solution-neutral. No platform or product names in the capability
  column. Combined classifications (`FR + TR`) signal that an engagement should split the row into two
  requirements.
- Adding a new area means a new prefix and a new H2 section; keep the same five columns so the tables stay
  machine-readable.
- Keep the header sections ("How to read the columns") in sync when the classification vocabulary changes.

## Warning
**This catalogue must never be shipped to a client as their requirements.** It is an elicitation and
challenge checklist. Delivering it unfiltered would present unconfirmed, unscoped and untestable statements
as agreed scope, and would hand the client capabilities nobody has decided to buy. Every entry taken into an
engagement must be confirmed as in or out of scope, rewritten with the client's own vocabulary, volumes and
acceptance criteria, and re-classified if the engagement's framing differs.
