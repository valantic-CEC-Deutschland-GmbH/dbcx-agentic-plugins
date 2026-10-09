## Research topics – SAP Engagement Cloud | SAP Emarsys (target, brownfield extension)
Seed for the per-engagement refresh (`dbcx render brief research`). Lines marked *(verified 2026-10-05)* have a row in reference-cache.md (official page + verbatim quote) - re-check the date-sensitive ones. Every *(verify)* line is a hypothesis until confirmed for the client's account, package and date with a help.sap.com (content service) or dev.emarsys.com URL.

### 0. Establish first (decides most estimates)
- Product name today: help.sap.com and the Feature Scope Description say "SAP Engagement Cloud | SAP Emarsys" (short SAP Emarsys); dev.emarsys.com still says "SAP Emarsys Customer Engagement Platform" *(verified 2026-10-05)*. Use the current page title in deliverables.
- The Feature Scope Description is the legally binding scope; features elsewhere on the help portal may need separate licences *(verified 2026-10-05)*.
- Which product packages the client licenses: Core, + Omnichannel Marketing Option, + E-Commerce Accelerator (full Predict, Smart Insight), + offline stores option, + Advanced Integration Capabilities, + Loyalty Module, + Mobile app marketing option, + Account Engagement option, + Additional account, + Test tenant *(package list verified 2026-10-05; the client's contract and the package-to-feature mapping: verify)*.
- Account generation: External Events and Google Pub/Sub events only for clients who started before January 2026; newer clients use Engagement Events; the External event trigger source is deprecated incrementally from Q2 2026 *(verified 2026-10-05)*. Whether a NEW country account of an EXISTING pre-2026 client gets External Events ("additional accounts" via the customer success manager) *(verify)*.
- Account topology in use: one account per country / brand, shared account, staging / repository account *(verify with the client)*.
- API authentication in use (WSSE or OAuth 2.0 v3): WSSE sunset "end of 2026" on most pages, EOL "February 1, 2027" on the developer hub Good-to-know page *(both verified 2026-10-05 - the dates conflict; plan with the earlier one)*.

### 1. Multi-country / multi-brand
- Distribution of Automation programs, block-based email campaigns and templates, Web Channel content blocks and custom fields between connected accounts; bulk up to 15 programs; above 50 segments distribution can fail; custom fields up to 100 at once; not distributable: contact lists, relational segments, API nodes, Custom HTML / VCMS campaigns, triggered-email sender domain *(verified 2026-10-05)*.
- Programs with an Engagement Event trigger are NOT on the "supported assets" list for distribution *(verify - absence from the list is not proof)*.
- Whether forms, voucher pools, external events, Relational Data connections and Predict settings can be distributed *(verify)*.
- One Predict account per Emarsys account; Web Channel domains in one account share one merchant ID *(verified 2026-10-05)*; a separate country account therefore needs its own Web Extend / Predict set-up *(verify the onboarding effort)*.
- Single-account multi-brand: per-brand consents via CDC / CDP mapping (CD_C_* fields), multiple SMS short codes, VCE language versions *(verified 2026-10-05)*; per-brand sender names, reply handling and reporting separation inside one account *(verify)*.
- Unified dashboard across accounts is in the Feature Scope Description *(verified 2026-10-05)*; which metrics it covers *(verify)*.

### 2. Triggered journeys and events
- Event-based Automation: one trigger per program, default trigger event timeout 6 hours, 50 trigger events per second per account, triggers only below 20 kB of event data although the API answers 200 OK *(verified 2026-10-05)*.
- Engagement Events: integration + event type, generated endpoint per type, draft endpoint for tests, existing contacts only (no creation), 200 kB payload, 5000 calls per minute, max 200 event types, max 100 integrations, retention 1-1100 days *(verified 2026-10-05)*. How the SAP Commerce Cloud "Engagement Event integration" (November 2025) relates to the connector's real-time events, and which one SAP recommends for new journeys *(verify)*.
- Triggered Email mail streams ignore opt-in; a Decision node is needed before marketing content *(verified 2026-10-05)*.
- Webhook node: 20 s timeout, max 20 contact fields, fail-safe after the 11th failed attempt *(verified 2026-10-05)*.
- Event payload loops: max 100 items in foreach *(verified 2026-10-05)*.

### 3. Integrations
- SAP Commerce Cloud connector: one Backoffice per Emarsys account, customerID as fixed identifier, unchangeable field mapping, real-time events for logged-in users only, product sync in one language / one currency / no deletion, required Integration API extensions and ImpEx, IP allow-list, maintenance after upgrades from 2211.28 *(verified 2026-10-05)*. How a multi-country Commerce installation feeds a second Emarsys account (second connection, Product Catalog API, custom feed) *(verify)*.
- SAP Customer Data Cloud / Customer Data Platform: one instance can feed several accounts with filter rules; 'Try to Match by Email' needed when combined with the Commerce connector; custom-field limits 40 strings / 100 numeric-date-boolean; CDC sync max 1000 requests per minute *(verified 2026-10-05)*.
- SAP Integration Suite: the SAP_EMARSYS help pages name no prepackaged Integration Suite content; Emarsys-side integration points are the Core API, Engagement Events endpoints, webhook node and SFTP / WebDAV *(verify on the SAP Business Accelerator Hub before assuming any prepackaged iFlow)*.
- Sales data: Sales Data API (GA November 2025; 1000 requests per minute, 10 MB, hourly processing) or SFTP files; deduplication rules differ per load path *(verified 2026-10-05)*.
- Product Catalog API (GA Q3 2026): 100 items / 9 MB per request; not usable with Loyalty, the Predict email recommender and the Price drop product set *(verified 2026-10-05 on the Getting Started page; whether this still holds after GA: verify)*.

### 4. Environments and promotion
- Sandbox tenants: requested via the customer success manager, same contracted functionality, full set-up needed, NO email sending, no sender domains *(verified 2026-10-05)*.
- SAP for Me entitlement roles "Testing Tenant" and "Productive"; email channel activation only for productive tenants *(verified 2026-10-05)*. Whether "Sandbox tenant", "Testing Tenant" and the "Core + Test tenant" package are the same thing and how each is licensed *(verify)*.
- Configuration promotion = distribution from a staging / repository account; no transport or export / import of account configuration was found *(distribution verified 2026-10-05; absence of another mechanism: verify)*.

### 5. Data residency and security
- ISO 27001, ISO 27018, SOC 2 Type II *(verified 2026-10-05)*.
- Open Data is EU-only on Google Cloud; Smart Insight stores data in BigQuery; Predict runs on AWS with servers in Ireland *(verified 2026-10-05)*.
- Hosting location of the core platform (contacts, campaigns) and any data-centre choice *(verify - no general statement on the help portal; check the SAP Trust Center, the service description and the DPA)*.

### 6. Pilot / Early Adopter at 2026-10-05 - not standard
- Brand Center, Design Themes, Branded Blocks (Web Channel and in-app only), Universal Schema Builder, Localized Product Personalization (Early Adopter Care until end of 2027), SAP Engagement Cloud SDK, Embedded Messaging, Multi-Contact ID handling *(verified 2026-10-05 - GA status moves every quarter: verify)*.

### 7. B2B (context)
- Account Engagement (SKU 8013363) needed for the B2B unit fields of the Commerce connector and for CDP corporate accounts (whether every corporate-account feature needs it: verify); the CRM connector is SAP Sales Cloud Version 1, other CRMs go through the Corporate Account API *(verified 2026-10-05)*.

### 8. Loyalty (context only - separate loyalty pack)
- Loyalty is an add-on that requires Smart Insight; Multiplan (several plans per account, Support enables) vs Multi Market; Loyalty API v4 on its own host with an x-api-key *(verified 2026-10-05)*.
