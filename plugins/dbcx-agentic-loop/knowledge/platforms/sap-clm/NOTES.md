# sap-clm pack notes

Built from SAP's own sources; no client material. Last verified: **2026-10-05**.

## Scope and design

- **SAP Customer Loyalty Management (CLM) only.** SAP Emarsys Loyalty is a different product and deliberately not covered; a requirement that would be met by it is not "standard" for this pack.
- **Roles = `["target"]`, no `as_source`, no `adapter.py`.** CLM is public-cloud SaaS on SAP BTP; there is no customer code base to scan. Use: target pack of tech-fit-estimation (slot `platform` or an option pack) for a greenfield loyalty introduction, including B2B and indirect-channel scenarios, and the knowledge of the standard critic `standard-sap-clm`.
- **Snippet placement follows what the briefs render.** tech-fit-estimation shows the analyst `docs_domains`, `best_practice`, `expected_hotspots_d3`, `api_families_hint`, `content_model_notes` and the standard critic `critic2_persona`, `docs_domains`, `best_practice`, `critic2_focus`, `effort_rules`. The B2B fit therefore sits in `expected_hotspots_d3` (analyst) and `critic2_focus` (critic); the estimator effort profile in `effort_rules` (no other pack defines that key); the analyst gets its essentials (double configuration, custom integration per source, custom member UI) through `best_practice`, `expected_hotspots_d3` and `content_model_notes`. The extra keys `scope_editions`, `b2b_fit`, `pitfalls` are reference text for overrides and other methods; tech-scoring reads this folder's files directly.
- **knowledge.json keys start with `target_`** because `common.knowledge()` merges only `target_*` keys of a target-role pack: `target_api_endpoint_families`, `target_content_component_types`, `target_capability_map` (status standard / config / integration / custom, each row pointing to its reference-cache section), `target_documented_integrations`, `target_limits`.
- **labels.<lang>.json** re-word only the mechanism tokens `module`, `setting`, `app` in terms that are right for CLM (it has features and configuration, not modules or apps) and still neutral for a second technology in a comparison run - pack labels merge into the whole run.
- **reference-cache.md** keeps the platform cache columns and adds a fifth, `Quote (verbatim)`; the engine reads only the first columns (`pack.new_facts` dedups on fact + applies), so the extra column is compatible. Fragments of one page are joined by " […] ", the convention of `dbcx reference add --quote`, so a researcher can carry a row into section 7 unchanged.

## Sources (all read 2026-10-05)

| Source | Coverage |
|---|---|
| help.sap.com, product `Customer_Loyalty_Management`, version SHIP: About, Feature Scope Description, User Guide (112 topics), Admin Guide, Integration (19), APIs, Security Guide (18), What's New Viewer, Onboarding (27) - 200 topics | complete read of every deliverable |
| api.sap.com package `sap-clm-SAPCustomerLoyaltyManagement` | metadata only - the OpenAPI specifications require an SAP login and were not read |
| news.sap.com (NRF 2025, SAP Connect 2025, Q4 2025 recap, Q2 2026 recap) | official positioning and announced vs shipped integrations |
| licensed composable storefront registry (RBSC, `@spartacus` scope) | release 221121.18.0, 39 libraries, none for loyalty |
| help.sap.com search across SAP Commerce Cloud, Integration Extension Pack, composable storefront, Customer Data Cloud, Customer Data Platform, Emarsys, Integration Suite, S/4HANA, Business Data Cloud | no page documents a CLM integration (absence finding, recorded as such) |

sap.com product pages and partner and analyst sites are not cited - web search summaries drawn from partner sites claim native SAP Commerce Cloud integration and B2B support; no SAP source read for this pack confirms either.

## Main findings

- **B2B:** wallet = one person; only the "Consumers" wallet type is selectable (the UI already shows a B2C/B2B wallet type); group wallets pool persons; no company account, hierarchy, purchaser/beneficiary split, receipt/claim handling or wholesaler sell-through earning is documented.
- **Integrations:** documented are S/4HANA Cloud Private Edition (master data INTO CLM) and Service Cloud V2 (mashup). Commerce Cloud / composable storefront, Customer Data Cloud, Customer Data Platform, Emarsys and Integration Suite content are not documented - SAP's 2025 announcement named Commerce Cloud and Emarsys as intended integrations.
- **Finance:** append-only double-entry ledger with book types and exports; "passed to SAP S/4HANA for settlement and accounting", but no posting configuration is documented.
- **APIs:** Checkout Connect, Wallet Connect, Backend Services, Data Products - all 1.0.0-beta; no events/webhooks published.
- **Environments:** two workspaces, Staging -> Live one-way, business objects not promotable.

## Gaps (kept as *(verify)* in research-seed.md)

Operation-level API specifications (earn from order, reversal, idempotency); B2B wallet roadmap; financial posting to S/4HANA (and support for S/4HANA Cloud Public Edition / on-premise); events/webhooks; API rate and payload limits; price metric and editions; hyperscaler and exact region; automatic tier evaluation rules; physical reward fulfilment; duplicate-wallet detection; Business Data Cloud data products. Refresh: What's New Viewer and the api.sap.com package first, then the *(verify)* list; confirmed facts travel back through `dbcx learn export`.
