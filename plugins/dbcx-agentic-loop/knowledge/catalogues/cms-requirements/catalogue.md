# CMS / Content Platform Requirement Catalogue

This file is a reference **SEED**, not a client deliverable. It is a hand-written completeness checklist of
requirements that content-platform and DXP projects tend to need, written from general architecture practice
and not derived from any engagement. Nothing in it is a client requirement until an engagement has confirmed
it with that client, in their words, with their numbers. Per engagement the catalogue is **maintained**: entries
are selected, reworded to the client's language, given real volumes and thresholds, and extended with what the
client needs that is missing here. Entries that were never discussed must not appear in a deliverable.

## How to read the columns

- **id** — stable identifier `<AREA>-NNN`, numbered per area from `010` in steps of 10 so new entries can be
  inserted without renumbering. Ids are permanent: once allocated, an id keeps its meaning and is never reused
  for a different capability. They are used to trace a client requirement back to the catalogue entry it came from.
- **capability** — the capability in one line, phrased so it can be turned into a testable requirement. It is a
  prompt for elicitation, not final requirement text.
- **typical FR/TR/NFR** — the usual classification: **FR** = behaviour a user or editor can exercise;
  **TR** = a technical or interface constraint on how the solution is built or connected; **NFR** = a measurable
  quality attribute (latency, availability, volume, compliance). Several entries are dual-classified because they
  split into a behaviour and a constraint; the engagement decides which half is being written.
- **B2B/B2C/both** — where the capability normally matters. `both` is the common case; `B2B` or `B2C` marks
  capabilities that are usually only in scope for that model. It is a hint about likelihood, not a rule.
- **notes** — the discriminating question to ask, the classic trap, or the thing that actually decides effort.
  This column is the reason the catalogue exists; read it before writing the requirement.

## CMS-MOD — Content modelling

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-MOD-010 | Content type catalogue and its granularity | FR | both | Count the types before estimating: a 12-type model and a 90-type model are different projects. Discriminating question: does each type exist because it renders differently, or because someone wanted a different form label? The latter collapses into one type with a variant field. |
| CMS-MOD-020 | Field-level typing and validation rules | FR/TR | both | Ask where validation is enforced: in the model (rejects on save) or in the template (renders wrong, silently). Required, regex and min/max in the model are cheap; cross-field and cross-entry rules almost always need custom code. |
| CMS-MOD-030 | References between entries (single, multi, polymorphic) | TR | both | Polymorphic references - a slot accepting any of several block types - are the cost driver in headless delivery: every accepted type multiplies the query/fragment surface and the frontend union handling. |
| CMS-MOD-040 | Reusable content blocks and shared fragments | FR | both | Discriminator: reuse by reference (edit once, changes everywhere, needs impact preview) or reuse by copy (safe, drifts apart). Teams ask for reference and then object when one footer edit changes 400 pages. |
| CMS-MOD-050 | Composable page and layout composition model | FR | both | Decides whether editors can build a new page layout without a release. If layout is code-only, every campaign page is a developer ticket - state that consequence in the estimate rather than in a footnote. |
| CMS-MOD-060 | Taxonomy and controlled vocabularies | FR | both | Ask who owns the vocabulary. A free-text tag field costs nothing and produces hundreds of near-duplicate tags; a governed taxonomy needs a maintenance workflow and usually its own editor role. |
| CMS-MOD-070 | Modelled relationships to commerce entities (product, category, brand) | TR | both | The trap is storing product data in the CMS. The requirement should be a reference by SKU or category id resolved at delivery time; anything else creates a second product master that will drift. |
| CMS-MOD-080 | Schema versioning and migration of existing entries | TR | both | Ask what happens to the live entries when a required field is added. Platforms differ: some backfill empty, some block publishing, some need a migration script per change - this is a recurring cost, not a one-off. |
| CMS-MOD-090 | Structured content kept separate from presentation | TR | both | Test: can the same entry render on web, app and an in-store screen without abusing a presentation field? If the model carries CSS classes or column widths, the multi-channel reuse claim is not real. |
| CMS-MOD-100 | Per-field localisable / non-localisable marking | TR | both | Field-level localisation flags are the difference between one translation job and dozens. Decide the flag at modelling time; retrofitting it once content exists is a data migration, not a configuration change. |

## CMS-EDIT — Editing and editorial workflow

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-EDIT-010 | Rich-text editing with constrained formatting | FR | both | The requirement is the allow-list, not the editor widget. Unconstrained rich text guarantees inline styles that break the design system; ask which marks, embeds and block types are permitted. |
| CMS-EDIT-020 | Structured, block-based authoring of pages | FR | both | Discriminator against free rich text: do editors assemble typed blocks (predictable, testable, reusable) or author free HTML (fast, unmaintainable)? Most estates need both plus an explicit rule for which content uses which. |
| CMS-EDIT-030 | Drafts, version history and rollback | FR | both | Ask the granularity: per field, per entry, or per whole page composition. Rolling back a composed page whose referenced blocks also changed is a different feature from rolling back one entry. |
| CMS-EDIT-040 | Scheduled publish and unpublish (embargo) | FR | both | Unpublish is the half that gets forgotten. Then ask about the cache: a scheduled publish that leaves a CDN copy live for an hour fails the business requirement even though the CMS did its job. |
| CMS-EDIT-050 | Editorial workflow with review and approval steps | FR | both | Count the states and roles, not the feature. Two-step review is configuration on most platforms; conditional routing by market, brand or content type is usually custom development. |
| CMS-EDIT-060 | Editorial calendar and planning view | FR | both | Ask whether it must show campaign activity across channels (email, social, paid). If yes it is an integration requirement towards a planning tool, not a CMS view. |
| CMS-EDIT-070 | Bulk operations (edit, publish, tag, delete) | FR | both | The effort driver is the transactional guarantee: what happens when entry 300 of 500 fails validation mid-run? Partial-success semantics, a result report and a re-run path have to be specified. |
| CMS-EDIT-080 | Content search and filtering in the authoring UI | FR | both | Editors abandon a platform they cannot search. Ask for the real find case: "all pages referencing this asset" and "all entries in review for one market" are index requirements, not a search box. |
| CMS-EDIT-090 | Content cloning for campaigns and market rollout | FR | both | Clone must be specified as deep or shallow. Cloning a page that references shared blocks and then editing them is the classic way a market team unintentionally rewrites the global master. |

## CMS-SITE — Multi-site and multi-language

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-SITE-010 | Multiple sites managed from one instance | FR/TR | both | Discriminator: separate sites (own trees, own permissions, own publish cycle) or one site with market variants? This single choice fixes permission scoping, translation workflow and release process for the rest of the project. |
| CMS-SITE-020 | Site tree and navigation hierarchy management | FR | both | Ask whether navigation is derived from the content tree or curated separately. Derived is cheap and constrains editors; curated is flexible and silently drifts from the actual page set. |
| CMS-SITE-030 | Content inheritance with per-site or per-market override | FR | both | The hard part is the override indicator: an editor must see whether they are looking at inherited or locally overridden content, otherwise nobody trusts the global master and everything gets copied. |
| CMS-SITE-040 | Language variants per entry with a fallback chain | FR/TR | both | Specify the fallback per field or per entry, and what a missing translation does at delivery: silent fallback, show source language, or return 404. All three are defensible; only one is what the business wants. |
| CMS-SITE-050 | Translation workflow (export, vendor round trip, import) | FR | both | The trap is the round-trip window: the source changed while the translation was out for two weeks. Agree the conflict rule - source wins, translation wins, or manual merge - before choosing a connector. |
| CMS-SITE-060 | Machine translation with human post-editing | FR | both | Ask who signs off. Raw machine output on a regulated market page is a compliance issue rather than a quality issue, which turns this into an approval-workflow requirement. |
| CMS-SITE-070 | Per-market legal and regulatory content variance | FR | both | Common in B2B: availability statements, certifications, disclaimers and price display rules differ per market. Model them as market-scoped fields, not as forked page trees, or the estate doubles per market. |
| CMS-SITE-080 | Right-to-left and non-Latin locale support | TR | both | Cheap to promise, expensive to prove. It needs design-system work (mirrored layouts), font coverage and native editorial testing - budget it outside the platform licence discussion. |

## CMS-DAM — Assets and digital asset management

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-DAM-010 | Asset ingest (single, bulk, drag-and-drop, watched folder) | FR | both | Bulk ingest of the existing library is a migration project in its own right. Get the asset count and average size before treating this as a feature line. |
| CMS-DAM-020 | Automatic renditions and responsive derivatives | TR | both | Discriminator: pre-generated renditions (predictable storage, slow to change) or on-the-fly transformation via URL parameters (flexible, needs a cache strategy and a cost model per transformation). |
| CMS-DAM-030 | Focal point or smart crop per asset | FR | both | Without it every aspect-ratio change crops the subject out of the hero image. Ask whether the focal point is per asset or per usage - per usage means a field on the reference, not on the asset. |
| CMS-DAM-040 | Asset metadata model with mandatory fields | TR | both | Alt text is the field to force at upload time. Make it optional and accessibility remediation becomes a separate project across the whole library later. |
| CMS-DAM-050 | Rights management, licence expiry and takedown | FR | both | Ask what expiry actually does: block new usage, unpublish the pages already using the asset, or notify an owner. Automatic unpublish of live pages is technically possible and commercially alarming - decide it explicitly. |
| CMS-DAM-060 | Asset search (metadata, full text, auto-tagging, similarity) | FR | both | Automatic tagging is the usual answer to a library nobody labelled. Test it on the client's own assets: generic tags across tens of thousands of near-identical product photos do not make them findable. |
| CMS-DAM-070 | Video handling (upload, transcode, streaming, captions) | TR/FR | both | Captions and transcripts are the accessibility requirement hiding inside "we need video". Also settle whether the CMS stores video at all or only references an external video platform. |
| CMS-DAM-080 | Asset usage tracking and where-used reporting | FR | both | This is the deletion guard. Without where-used, no editor will ever dare delete an asset and the library grows forever, taking storage cost and search quality with it. |
| CMS-DAM-090 | Document assets (datasheets, certificates, CAD, price lists) | FR | B2B | B2B-specific: these documents are often gated by contract or account type, which makes it an entitlement requirement rather than a DAM feature. Ask who decides who may download what. |

## CMS-PERS — Personalisation and experimentation

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-PERS-010 | Audience segment definition and management | FR | both | Ask where the segment is defined: CMS-local rules, the commerce platform's customer groups, or a CDP. Three systems owning the same segment definition is the classic personalisation failure mode. |
| CMS-PERS-020 | Rule-based content variation per segment | FR | both | Count the variants an editor must maintain and QA: personalisation multiplies the authoring surface linearly. Two segments across ten pages is twenty pages to review before every release. |
| CMS-PERS-030 | A/B and multivariate testing of content | FR | both | Discriminator: does the test run server-side in the CMS (cache-safe variants, needs cache-key work) or in a client-side tool (flicker, Core Web Vitals cost)? Different requirements, different owners, different budgets. |
| CMS-PERS-040 | Personalisation reconciled with static generation and CDN caching | TR | both | The real constraint in headless: a fully cached page cannot be personalised server-side. Decide per zone - cached shell plus a personalised fragment - or the performance NFR and this FR directly contradict each other. |
| CMS-PERS-050 | Real-time behavioural triggers (cart, browsing, campaign source) | TR | both | Ask for the latency: "reacts in the same session" needs an edge-readable signal, "reacts next day" is a batch segment. The gap between those two answers is most of the cost. |
| CMS-PERS-060 | Measurement and attribution of personalisation and tests | NFR/FR | both | A personalisation programme without attribution reporting gets switched off within a year. Require the metric, the reporting owner and the review cadence as part of the functional requirement. |

## CMS-API — Headless delivery and APIs

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-API-010 | Content delivery API shape (REST, GraphQL, or both) | TR | both | Ask what the frontend fetches per page. Deeply composed pages over REST become request waterfalls; GraphQL removes the round trips and moves the cost into query-complexity limits and caching. |
| CMS-API-020 | Draft/preview API separated from published delivery | TR | both | If preview and delivery are the same endpoint with a flag, an unpublished draft will eventually leak into production. Require separate hosts and separate credentials, and test that published tokens cannot read drafts. |
| CMS-API-030 | Reference resolution depth and linked-entry expansion | TR | both | The concrete number matters: platforms cap include depth, usually at a few levels. A composed page deeper than the cap needs client-side stitching - find the cap before finalising the content model. |
| CMS-API-040 | CDN caching strategy and cache keys for content | NFR/TR | both | Specify the cache key against the variant axes: locale, market, segment, currency, device. Every axis multiplies cache population and invalidation surface, and turns a good hit ratio into a bad one. |
| CMS-API-050 | Targeted cache invalidation on publish (purge by tag or surrogate key) | TR | both | Full-site purge on every publish is what turns a fast site into a slow one every morning. Require tag-based purge and ask specifically how tags are attached to *referenced* content, not just the edited entry. |
| CMS-API-060 | Webhooks on content lifecycle events | TR | both | Ask about delivery guarantees and replay: at-least-once with retries means every consumer must be idempotent, and a webhook missed during a deployment must be recoverable without a manual database fix. |
| CMS-API-070 | Static generation / incremental regeneration on publish | TR | both | The effort driver is build time at real content volume. A full rebuild of tens of thousands of pages taking hours is not a publish workflow - incremental regeneration has to be designed and proven, not assumed. |
| CMS-API-080 | Official SDKs and generated types for the frontend | TR | both | Types generated from the content model are what keep a headless frontend honest. Without them, every model change is a silent runtime break discovered in production by a visitor. |
| CMS-API-090 | API rate limits, quotas and burst behaviour | NFR/TR | both | Take the published limit and compare it with peak page views divided by the expected cache hit ratio. Preview, build and migration traffic usually hit a different and much tighter limit than delivery. |

## CMS-SEO — URLs, metadata and search visibility

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-SEO-010 | URL and slug management with per-locale paths | FR | both | Ask whether editors may change a live slug. If yes, an automatic redirect on change is not a separate nice-to-have - make it part of this same requirement or expect broken inbound links. |
| CMS-SEO-020 | Redirect management (301/302, bulk import, chain detection) | FR | both | Migration reality check: the redirect map from the old site is usually thousands of rows. Require bulk import plus chain and loop detection, and name who is accountable for producing the map. |
| CMS-SEO-030 | Canonical URL control and duplicate-content handling | TR | both | Faceted, filtered and paginated pages are where duplicates come from. Decide the canonical rule per template, not per page, or editors will get it wrong at scale. |
| CMS-SEO-040 | Structured data / schema.org markup | TR | both | Ask whether markup is generated from the content model (correct, invisible to editors) or hand-authored per page (drifts, fails validation). Product, offer and FAQ markup usually need commerce data, not CMS data. |
| CMS-SEO-050 | Sitemap generation including images and hreflang alternates | TR | both | The hreflang alternates are the multi-market half that gets missed. Also settle the split: sitemaps have size caps and large estates need an index file plus a generation schedule. |
| CMS-SEO-060 | Per-page metadata, Open Graph and social preview | FR | both | Require sensible defaults derived from the content model *plus* an override field. Pure override fields mean a meaningful share of the estate ships with an empty title and no description. |
| CMS-SEO-070 | Core Web Vitals ownership in a decoupled setup | NFR | both | The discriminating question: who is accountable for LCP when the CMS ships JSON and a separate frontend team renders it? Without a named owner and a per-template budget, nobody fixes a regression. |
| CMS-SEO-080 | Robots, indexation control and staging protection | TR | both | The classic incident is a staging environment indexed because robots configuration was shared across environments. Require environment-specific indexation control and verify it on every environment, not just production. |

## CMS-PREV — Preview and staging

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-PREV-010 | In-context preview for a headless frontend | FR/TR | both | The single biggest headless disappointment. It needs a preview route in the frontend, draft-API credentials and a per-environment URL mapping - budget frontend work per template, not a CMS toggle. |
| CMS-PREV-020 | Visual editing with click-to-edit from the rendered page | FR | both | Ask whether editors truly need to click the rendered element or will accept side-by-side form and preview. Click-to-edit requires field-level annotation in the frontend markup for every component. |
| CMS-PREV-030 | Cross-device and responsive preview | FR | both | Viewport preview inside an iframe is not real device rendering. If the requirement is real-device confidence, it belongs in QA tooling rather than the CMS, and should be written that way. |
| CMS-PREV-040 | Time-travel preview of a future publish state | FR | both | Becomes necessary as soon as scheduled publishing exists: "show the site as it will look on campaign launch day", with all entries scheduled for that moment resolved together rather than one at a time. |
| CMS-PREV-050 | Shareable preview links for reviewers without a licence | FR | both | Ask for expiry and access control. An unauthenticated, permanent preview link to unpublished pricing or campaign content is a leak waiting to happen, and it will be forwarded outside the company. |
| CMS-PREV-060 | Preview of personalised and A/B variants | FR | both | Editors must be able to preview *as* a segment. Without it, personalised content is authored blind and effectively reviewed in production by real customers. |

## CMS-PERM — Permissions and governance

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-PERM-010 | Role and permission model for editorial functions | FR | both | Enumerate the real roles first (author, reviewer, publisher, translator, administrator, agency). Estimates fail because the client operates nine roles while the platform models four without customisation. |
| CMS-PERM-020 | Per-site, per-language and per-branch scoping of rights | TR | both | The discriminator for multi-market governance: can a market editor be prevented from touching the global master page? If scoping only exists per site, shared global content has no protection at all. |
| CMS-PERM-030 | Field-level and component-level edit restrictions | FR | both | Typical case: legal disclaimers editable only by legal, price statements only by pricing. Field-level locking is missing or awkward on many platforms - verify it in the product before promising it. |
| CMS-PERM-040 | Audit trail of who changed and published what | NFR/TR | both | Ask for the retention period and whether the trail must survive deletion of the entry. An audit trail wiped together with the content fails the compliance case it was bought for. |
| CMS-PERM-050 | Legal or compliance approval gate before publish | FR | both | In regulated sectors this is a hard gate, not a notification. Specify what happens to a scheduled publish whose approval expires before the scheduled date - block, or publish anyway. |
| CMS-PERM-060 | SSO, provisioning and de-provisioning of editors | TR | both | Agency and contractor churn is the driver: ask how a leaving external user loses access. Manual de-provisioning inside the CMS is an audit finding waiting to be written. |

## CMS-INT — Integration with the surrounding landscape

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-INT-010 | Commerce product, stock and price data inside content | TR | both | Choose the read pattern: server-side resolution at render (fresh, slower), build-time embedding (fast, stale prices) or client-side hydration (fresh, CWV cost). B2B contract prices rule out build-time embedding entirely. |
| CMS-INT-020 | External DAM as the asset system of record | TR | both | If an external DAM owns assets, the CMS must reference rather than copy them. Ask what happens on DAM-side deletion and whether renditions are served from the DAM's CDN or the site's. |
| CMS-INT-030 | Translation management system connector | TR | both | Check the connector's granularity: whole-entry jobs versus changed-field jobs. Whole-entry jobs mean paying to retranslate unchanged text on every minor edit, which shows up as an operating-cost surprise. |
| CMS-INT-040 | Search platform indexing content alongside products | TR | both | The requirement is unified results: one query returning products and editorial content ranked together. That is an index-design and relevance requirement, not a connector, and it needs an owner for relevance tuning. |
| CMS-INT-050 | Analytics and tag management integration | TR | both | Ask who can deploy tags. A tag manager that marketing can push straight to production bypasses the CMS release process and is the usual cause of unexplained performance and consent regressions. |
| CMS-INT-060 | Marketing automation and content reuse in email | FR/TR | both | Reusing CMS blocks in email means a second rendering target with far tighter constraints. Confirm whether email really needs to share the content model, or only the copy and the assets. |
| CMS-INT-070 | Customer profile / CDP integration for personalisation | TR | both | Fix the direction and latency of the profile read, and whether the CMS may store profile attributes at all - usually it may not, for data-protection reasons, which forces edge or client-side resolution. |
| CMS-INT-080 | Identity and entitlement for gated content | TR | B2B | B2B gating: whitepapers, price lists and documentation behind a login. The entitlement decision must live in exactly one system; a copy of the account model inside the CMS will drift and cause wrong access. |

## CMS-NFR — Quality attributes and operations

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CMS-NFR-010 | Publish-to-live latency | NFR | both | Make it measurable end to end including CDN purge: "editor clicks publish, change visible to an anonymous visitor within N seconds". A CMS-internal publish duration proves nothing to the business. |
| CMS-NFR-020 | Delivery response time and per-template performance budgets | NFR | both | Set the budget per template *with the cache state named* (cold versus warm). One site-wide number is untestable and becomes the main argument after go-live. |
| CMS-NFR-030 | Availability of the delivery tier | NFR | both | Ask whether delivery survives an authoring-tier outage. Decoupled or statically generated delivery usually does; a coupled CMS rendering pages live does not - that difference *is* the architecture decision. |
| CMS-NFR-040 | Accessibility of the authored output (target WCAG level) | NFR | both | No platform delivers this alone. Split the requirement in two: accessible components (built once) and accessible authoring (heading order, alt text, link text) enforced by validation and editor training. |
| CMS-NFR-050 | Authoring UI performance at real content volume | NFR | both | Test the entry list and search with the real number of entries, locales and versions. Authoring tools that feel fine with hundreds of entries can be unusable at tens of thousands. |
| CMS-NFR-060 | Content retention, archiving and legal hold | NFR | both | Ask whether a published version must be reproducible years later as evidence - common for regulated claims and published prices. That is an archive requirement, not a version history. |
| CMS-NFR-070 | Observability of the content publishing pipeline | NFR | both | Require alerting on the invisible failure: publish succeeded, build or cache purge failed, site silently stale. Nobody notices this until a campaign fails to appear at launch. |
| CMS-NFR-080 | Content migration volume and fidelity | NFR/TR | both | Get the counts early (pages, entries, assets, locales, versions) and the fidelity target. "Migrate everything as-is" combined with a new content model is a contradiction - force the choice between remodelling and lift-and-shift. |
