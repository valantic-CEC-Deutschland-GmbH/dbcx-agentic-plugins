# sap-cdp pack notes

Last verified: **2026-10-05**. Role: `target` only (no `as_source`, no `adapter.py` - CDP has no code base to scan). Used as the technology pack
of a tech-fit-estimation option and as the per-pack standard critic `standard-sap-cdp`. Generic product knowledge only, no client content.

## Sources and method
- **help.sap.com**: all six SAP_CUSTOMER_DATA_PLATFORM deliverables
  were read through their tables of contents on 2026-10-05 - User Guide (205 topics), Integration Guide (274), APIs (32), What's New Viewer (6),
  Onboarding Guide (59), Security Guide (9) - plus the Commerce-side connector modules under SAP_COMMERCE_INTEGRATIONS (SAP One Domain Model
  Integration, SAP Personalization Connectivity). Every quote in `reference-cache.md` was matched word for word against the page text.
- **sap.com product pages** (overview, features): positioning only (product family, related products). The pricing page renders its content
  client-side; its metric is therefore NOT in the cache and stays *(verify)*.

## Coverage (reference-cache.md: 166 verified rows - 164 help.sap.com, 2 sap.com)
Architecture and terminology; business units, business areas, roles; environments, provisioning, configuration packages (UI and API) and their
non-transportable entities; customer schema (Legacy vs SAP Integrated variants, profile / group / relationship / activity schemas, PII, limits);
identity resolution (application identifiers, system and user-defined and weak matching rules, lifetime limits, Unified vs Contextual profile);
merge rules; ingestion pipeline order; connectors with direction, mode, events/actions and limits for SAP Commerce Cloud (current and Legacy, plus
the Commerce-side ODM integration and Personalization Connectivity), SAP Customer Data Cloud, SAP Emarsys, SAP Engagement Cloud enterprise edition,
SAP S/4HANA (+ Cloud Integration iFlows), S/4HANA Cloud, Master Data Integration; extension mechanisms (Connector Studio, webhooks, pre-mapping
extension on BTP Kyma, enrichment points, server and web client applications); APIs with size and rate limits and OAuth; processing purposes and
consent interplay; B2B (groups, relationships, child indicators, Enrich with Parent Data); per-business-unit limits; activation (audiences,
scheduling, CX flows), exports, data retention; data residency (EU Netherlands / US East), certifications, security defaults; Direct Data Access
(Advanced Insights add-on); dated What's New facts and the one documented deprecation (Emarsys WSSE by end of 2026).

## Design decisions
- `pack.json as_target.snippets` carries the keys tech-fit-estimation pulls: `critic2_persona`, `docs_domains`, `best_practice`, `critic2_focus`,
  `effort_rules` (first pack to define it), `expected_hotspots_d3`, `expected_blockers_d4`, `content_model_notes`, `api_families_hint`.
  `effort_rules` gives RELATIVE T-shirt bands per mechanism; they are an estimator's starting point, not measured SAP figures.
- `knowledge.json`: only `target_*` keys reach a run's merged knowledge (common.knowledge filters target packs); `standard_connectors` and
  `limits` are reference lists with cache Ids for analysts and the critic.
- `labels.<lang>.json` only rewords the mechanism tokens `app` and `setting`; pack labels merge last-wins across all packs of a run, so the
  values stay correct for any platform.
- The brownfield frame (new country = new business unit vs new business area) is the load-bearing decision of every estimate; it opens the seed.

## Gaps (open *(verify)* items, see research-seed.md)
Licence metric and what a new business unit costs; how a business unit is created in an existing tenant; number of non-production workspaces;
B2B Commerce data and multi-site routing in the Commerce-side ODM integration; minimum Commerce update on the JDK 21 line; latency SLA; scope of
rate limits; CDC B2B organisation mapping to CDP groups; several Emarsys tenants per unit; package import across business-unit variants; Cloud
Integration package version on api.sap.com; regions beyond EU/US; roadmap items.
