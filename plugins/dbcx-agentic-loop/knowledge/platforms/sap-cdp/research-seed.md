## Research topics – SAP Customer Data Platform (target pack)
Seed for the research step (`dbcx render brief research --out`). Lines without a marker are already verified in `reference-cache.md` (row Id in
brackets) and only need a date check; every line marked *(verify)* is a hypothesis or an open question that must be confirmed with a URL, a date and
a verbatim quote before an estimate relies on it. help.sap.com is read through the content service (`saphelp.py` / `sapsearch.py` in the
sap-commerce pack's `tools/`), never by HTTP status. The product has no release numbers: name the access date of every fact.

### 0. Frame the brownfield question first
- A new country can be a new **business unit** (own customer schema, matching rules, purposes, applications, segments, flows) or a new **business
  area** inside an existing unit (data-visibility split by an area-defining attribute, shared configuration) [ARCH-1, ARCH-2, BA-1, BA-2]. Ask which
  one the client runs or intends, and why (separate identity space, legal entity, consent regime, brand).
- How is a new business unit created in an existing tenant - self-service in the console, via SAP support, or via SAP for Me provisioning? The
  crawled documentation has no procedure for it *(verify)*.
- Is the existing unit **Legacy** or **SAP Integrated** [SCH-1]? Can a unit change variant after creation *(verify: the documentation only says the
  variant is assigned at creation)*. Variants can coexist in one tenant [WN-3].
- Which profile views does the existing unit run (Unified only, or also Contextual) [IDR-2, IDR-3, IDR-4, WN-2]?
- Small market: predictive indicators need about 20,000 profiles/groups and 100,000 orders after filters [LIM-20] - check whether the new
  unit or area reaches that before promising predictive scores.

### 1. Licensing, packaging, commercial metric
- Product naming and family: sap.com lists SAP Customer Data Platform under SAP Business Data Cloud [SAP-1]; the contract / price-list naming of
  the client's order *(verify on the order form / SAP for Me entitlements)*.
- Pricing metric: blocks of records (customer profiles and groups) with included storage and activations, add-ons for storage, activations and
  Advanced Insights - seen only in a search-engine excerpt of the sap.com pricing page, which renders client-side and could not be read *(verify
  against the Service Description Guide or the order form; never quote the excerpt)*.
- Does adding a business unit or a country change the licence (records counted per tenant or per unit) *(verify)*.
- Advanced Insights add-on (material 8018086) is required for Direct Data Access and can be enabled per workspace or business unit [DDA-1, ARCH-4].
- Environments: production entitlement role in SAP for Me [ONB-2]; production and non-production workspace per data center [ARCH-1]; number of
  non-production workspaces included *(verify in the Service Description)*.

### 2. Data residency and operations
- Two data centers: Europe (Netherlands, BTP cf-eu20) and US East (Virginia, BTP cf-us21) [DR-1, DR-2]. Other regions, China, or country-specific
  residency requirements of the new market *(verify; treat as a blocker until confirmed)*.
- Latency: SAP documents "near real time" processing and CX-flow activation that is not always instantaneous [ARCH-9, ACT-4]; no latency SLA was
  found *(verify)*.
- Rate limits: are the ingestion and query limits [API-1, API-4] per business unit, per application or per tenant *(verify)*.

### 3. SAP Commerce Cloud integration (most brownfield extensions start here)
- Current connector: one-directional, webhook-based, customers / carts / orders, needs the 2211 September 2024 update [COM-1, COM-2, COM-4].
  Minimum update on the JDK 21 line (2211-jdk21.x) *(verify in the Commerce update release notes)*.
- Commerce side is the SAP One Domain Model Integration; its replication pages document **B2C** customers, orders and carts [COM-6]. Whether B2B
  customers (B2BCustomer / B2BUnit), B2B orders or quotes replicate in standard *(verify; until confirmed estimate B2B Commerce data as custom
  Connector Studio / ingestion-API work or a Commerce extension)*.
- Multi-site Commerce: the ODM consumed destinations are named per object (odmCustomerDestination, odmOrderDestination, odmCartDestination)
  [COM-11]; whether a second BaseSite / country can be routed to a different CDP business unit or event listener in standard *(verify; likely
  custom routing)*. Personalization Connectivity destinations can be mapped per Base Store [COM-15].
- Initial load per new site: outbound-sync cron jobs, external-ID / OID back-fill scripts (the sample filters one BaseSite) [COM-8, COM-9].
- Storefront personalisation with CDP segments: logged-in users only, segments created manually in Commerce, cached lookup [COM-12..COM-15].
- Legacy connector (CPI package, polling, tested on 2005) [COM-5] - check which one the existing unit uses before reusing its configuration.

### 4. SAP Customer Data Cloud and consent
- One CDC application per business unit, several CDC sites possible; do not share one CDC site across business units [CDC-2]. A new country with
  its own CDC site: new site in the same unit, or new unit *(decide in section 0)*.
- CDC organisation data reaches CDP as groups and relationships via batch polling [CDC-4]; whether CDC B2B organization management maps
  one-to-one to CDP group types *(verify)*.
- Purposes: CDP enforces, never collects consent [PUR-1]; the CDC application auto-creates purposes [CDC-3]; max 30 purposes per unit [PUR-3].
  New country-specific consent in CDC = new or reused purposes in CDP *(verify the client's purpose design)*.

### 5. SAP Emarsys / SAP Engagement Cloud
- One application per Emarsys tenant; a tenant connects either to CDP or to CDC; WSSE ends with 2026 [EMA-1, EMA-2, EMA-3]. Opt-ins for several
  purposes / tenants via purpose transformations [EMA-6]; several enterprise-edition tenants from one unit need a support ticket [EMA-8]; the
  equivalent rule for several SAP Emarsys tenants per unit *(verify)*.
- Emarsys field limits for contact sync [LIM-17]; CDP audience builder usable inside SAP Engagement Cloud since 2026 [WN-6].

### 6. ERP / SAP Integration Suite
- S/4HANA connector via SAP Cloud Integration; Business Partner and relationship iFlows are built by the project [S4-1, S4-4, S4-5]. Current
  version of the integration package on the SAP Business Accelerator Hub *(verify on api.sap.com)*.
- S/4HANA Cloud connector polls customers and returns [S4-6]; Master Data Integration connector for Business Partner batch sync [S4-7].
- The Integration Guide has a SAP Business Data Cloud integration page *(verify its scope before using it in an estimate)*.

### 7. Configuration promotion and test
- Packages carry schemas, indicators, most segments, merge/matching rules, outbound purposes, custom connectors; they do NOT carry applications,
  audiences, CX flows, CX journeys, exploration segments, RFM and other indicators [ENV-3, ENV-4, WN-5]. Imported matching rules are appended
  [ENV-3]; same-named entities conflict on API import [API-7].
- Business-unit reset only in development workspaces [ENV-1]. Whether a package can be imported into a unit of the other variant (Legacy ->
  SAP Integrated) *(verify)*.

### 8. Roadmap and deprecations
- Only dated facts from the What's New viewer count [WN-1..WN-9]. Planned features from the SAP Road Map Explorer *(verify; never estimate on
  a planned feature)*.
