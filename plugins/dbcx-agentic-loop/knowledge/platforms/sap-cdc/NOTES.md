# sap-cdc pack notes

SAP Customer Data Cloud (CDC): products Customer Identity (formerly Registration-as-a-Service), Customer Consent (with Enterprise Consent and Preference Management) and CIAM for B2B (Organization Management, Delegated Admin, policy-based authorization). Last verified: **2026-10-05**.

## Purpose and shape
- **Roles = `["target"]` only, no `as_source`, no `adapter.py`.** CDC is SaaS: there is no client code base to scan. The pack serves the tech-fit-estimation method as platform pack (brownfield extensions: a client already runs CDC, usually with SAP Commerce Cloud, in one country and adds a country / site / brand) and the standard critic `standard-sap-cdc`.
- `pack.json` `as_target`: `content_model_name` = screen-set; snippets `critic2_persona`, `docs_domains`, `best_practice`, `critic2_focus`, `effort_rules` (typical size per mechanism, read by the standard critic), `expected_hotspots_d3`, `expected_blockers_d4`, `content_model_notes`, `api_families_hint`.
- `knowledge.json`: `target_api_endpoint_families` (API namespaces from the documentation's table of contents, plus the Commerce-side endpoints) and `target_content_component_types` (out-of-the-box screen-sets, Hosted Pages, Delegated Admin console, preference center, templates).
- `labels.<lang>.json`: CDC wording for the method's mechanism tokens (product/package, pre-built integration, console configuration / policy, extension / webhook / dataflow, custom code).
- Generic product knowledge only; no client data.

## Sources and verification
- **reference-cache.md: 421 verified rows**, all read 2026-10-05 from help.sap.com. Each row has URL, date, source type and a verbatim quote; every quote fragment (split as the engine's quote gate splits, ≥ 20 letters/digits) was found word for word in the page text (normalised as `evidence.qnorm`). Table-cell quotes join the cell texts without the separators.
- Deliverables read: CDC product help (SAP_CUSTOMER_DATA_CLOUD / 8b8d6fffe113457094a17701f63e3d6a, version SHIP, all 1154 topics of the table of contents downloaded); What's New Viewer for Customer Data Cloud (cf79af525d4941e4a13095df8aa95f50 - only three pages are reachable through the content service); SAP Commerce Integration Extension Pack "SAP Customer Data Cloud Integration" (SAP_COMMERCE_INTEGRATIONS / b6a1e8b75222421a8faf0269e8fbd0dc, 2211) incl. the IEP deprecation table and the 2211-jdk21.1 upgrade page; composable storefront "SAP Customer Data Cloud Integration" (SAP_COMMERCE_COMPOSABLE_STOREFRONT, 2211); SAP Customer Data Platform and SAP Emarsys integration guides (CDC connector pages only).
- Rows by area: product 15, identity 35, multisite / operations 79, CIAM for B2B 70, consent 86, data model and extensibility 93, SAP Commerce integration 37, adjacent products 6. Source type: help.sap.com (content service) for all 421 rows; no context7 mirror, SAP Note, PDF or blog row was needed.
- Not used, by rule: the open-source Spartacus repository and public npm packages (composable storefront is a licensed SAP product; its current CDC library state is a *(verify)* item to be read from the licensed packages).

## Main findings for estimators (details and quotes in the cache)
- The **site-group decision** drives everything: a child site shares user base, schema (children override only *required*), consent statements (parent only), B2B approval workflows and Authorization Workspace, extensions (one per extension point per group) and webhook fan-out; adding an already active site to a group later loses users / audit log / consent vault. A separate site means rebuilding or copying configuration; the Copy Configuration Tool covers schema, screen-sets and policies only, without rollback.
- **Global Access does not support CIAM for B2B Organization Management** (nor Data Store, Flow Builder); a normal site group lives in one data center; EU2 and CN1 have separate consoles.
- CIAM for B2B: no nested organizations, fixed OrganizationRegistration screen-set, approval limits 3 paths x 3 steps x 10 approvers, irreversible organization / member attributes, organization cap 10 % of B2B users.
- Limits worth quoting: Acceptable Use Policy rates per licence tier, accounts.search caps, extension timeout 10-5000 ms (default 1000), webhook retries for 3 hours then discard and deactivation after 7 days, dataflow quotas per partner (25 / 25 / 5), import 5 calls per UID per minute, Email OTP throttling.
- SAP Commerce integration: IEP module sap-customer-data-cloud (gigya* extensions); Accelerator addons deprecated (gigyab2bloginaddon Q4 2024, gigyaloginaddon Q3 2028); composable storefront via @spartacus/cdc; documented gaps: no cart merge on CDC login, no refresh tokens, no profile update via screen-sets on global sites, B2B user management redirects to the Delegated Admin console, B2B user replication per base site (webhook) or by dataflow (new users only, 10-minute minimum); gigyauserdeleteservices removed with 2211-jdk21.1.

## Gaps (kept as *(verify)* in research-seed.md)
- Commercial packaging and metrics (which products / premium components are licensed, contract impact of a new country) - not in the product help.
- Current What's New entries (the viewer's release list is not reachable through the content service); only the 2021 social-engagement deprecation, the TLS hardening and the 2026 H1 IP address release are cached.
- Documentation conflicts: webhook events per message (100 vs 500 for v3.0); Email-channel double opt-in on communication topics.
- Objects the Copy Configuration Tool does not copy (the documentation lists only what it copies).
- JDK 21 line: CDC custom OAuth grant with the new authorization server and with the composable storefront's authorization code + PKCE flow.
- Current licensed composable storefront release of `@spartacus/cdc` (read from the SAP repository-based shipment channel, never from the open-source repository).
- Tenant facts (site structure, data center, consent solution version, account model, toggles, quotas in use).

## Refresh
Re-run the content-service fetch for the CDC deliverable (version SHIP changes continuously) and re-check every row older than two CDC releases; facts confirmed in engagements reach the maintainer through `dbcx learn export`.
