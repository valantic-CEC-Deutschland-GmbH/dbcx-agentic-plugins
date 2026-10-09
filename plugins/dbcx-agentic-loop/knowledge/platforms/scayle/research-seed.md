## Research topics – SCAYLE (migration target)
Seed for the version-pair refresh. Every line below is a HYPOTHESIS *(verify)* until confirmed against the current SCAYLE developer documentation and, above all, the client's own contract, with a URL and a date. The vendor material is capability-level, so API resource names, module boundaries and content details in this seed are best-effort and unverified.

### 1. Overview
- Headless, API-first, cloud-native commerce platform developed by ABOUT YOU, one of Europe's largest fashion e-commerce companies *(verify)*.
- Built for ABOUT YOU's own operation first, then commercialised *(verify)* - so the feature set reflects fashion retail practice rather than a generic commerce checklist.
- Components: SCAYLE Commerce Engine (backend), Storefront API (customer-facing), Admin API (management), SCAYLE Panel (back-office UI), Add-on API for extended modules *(verify the current component names)*.
- Fully managed SaaS; no self-hosting option *(verify)*.
- Positioning claims to test: fashion domain expertise (size/colour matrices, returns, fast-fashion cycles), production-proven scale behind ABOUT YOU's roughly EUR 1.9B GMV *(verify the figure and its date)*, omnichannel built in, EU data residency and GDPR compliance, and managed hosting for the headless storefront *(verify each)*.

### 2. Editions/plans & licensing
- Commercial model is modular: a core platform plus add-on modules (omni-channel, wholesale and others) *(verify the current module list and which are separately priced)*.
- Implementation is delivered with professional services for setup *(verify what SCAYLE does versus what the SI does)*.
- CRITICAL CONSEQUENCE for a fit estimation: on a modular SaaS, "standard" means "contracted". A feature that appears in the documentation but is not in the client's package is a gap, not coverage *(verify every feature claim against the contract)*.

### 3. B2B capabilities
- B2B features are explicitly limited compared with dedicated B2B platforms *(verify)*.
- A wholesale module provides basic B2B/wholesale ordering *(verify what it actually covers)*.
- Customer groups give differentiated pricing and access *(verify granularity)*.
- Custom pricing through group-based price lists *(verify whether per-customer contract prices are possible at all)*.
- B2B workflows otherwise happen through API customisation in the frontend or an external service *(verify)*.
- Absent: approval workflows, punchout, quotes *(verify)*. Assume organisation hierarchies, budgets, order approval, RFQ and contract pricing are not available and would be built outside the engine.
- B2B commerce and complex B2B scenarios are a poor fit *(verify)* - a B2B-heavy requirement set is the clearest disqualifier for this platform.

### 4. B2C capabilities
- Rich product information management inside the engine *(verify how it compares with a dedicated PIM for attribute governance and workflows)*.
- Variant management optimised for fashion: size, colour and style matrices *(verify how non-fashion variant dimensions are modelled)*.
- Catalogue management: categories, attributes, filtering *(verify)*.
- High-performance product search and navigation *(verify the search technology, relevance tuning options and whether it is a separate module)*.
- Cart and checkout with optimised flows *(verify what the API provides versus what the frontend must implement)*.
- Promotions: discount and campaign management *(verify the promotion and voucher model - conditions available without custom code)*.
- Customer accounts: registration, profiles, order history *(verify self-service scope, especially returns)*.
- Wishlist with saving and sharing *(verify)*.
- Media management for images and assets *(verify transformation, CDN and video support)*.
- Internationalisation: multi-language and multi-currency *(verify the market, tax and legal-text coverage per country)*.

### 5. Architecture & extensibility
- API families: Storefront API (customer-facing, high-performance, REST and GraphQL options) and Admin API (full backend access), plus an Add-on API for extended modules *(verify which protocol each family really offers and whether GraphQL covers the same surface as REST)*. See knowledge target_api_endpoint_families.
- Webhooks for event-driven integrations *(verify the event catalogue, delivery guarantees, retries and ordering - obtain this in writing before designing an integration)*.
- Extensibility model: there is NO server-side extension point inside the commerce engine - no code is deployed into it. Customisation lives in the frontend (or a backend-for-frontend layer), in external services, and in the add-on catalogue *(verify)*. This is the single most important architectural constraint to state in a deliverable.
- Storefront Application: a reference implementation framework in JavaScript/TypeScript that accelerates the storefront build *(verify the framework, its licence and how much of a real storefront it delivers)*.
- Storefront Hosting: managed hosting for the headless frontend, reducing the DevOps burden *(verify what is managed - build, CDN, scaling, preview environments - and what remains the client's)*.
- Add-on marketplace of pre-built extensions *(verify the current catalogue size and maturity)*.
- ERP integration through connectors for common ERP systems *(verify which connectors exist and are maintained versus which are project work)*.
- Payment: multiple PSP integrations *(verify the list against the client's required providers and markets)*.
- Shipping: carrier and fulfilment integrations *(verify)*.
- Content model: see the pack snippet content_model_notes. No CMS module is listed, so editorial pages are expected from the storefront application or an external headless CMS *(verify whether a SCAYLE CMS or content module exists in the client's contract - this materially changes the scope)*.

### 6. Limitations & typical gaps
- B2B depth: very limited; the platform is not suited to B2B scenarios *(verify)*.
- Market presence: newer to market with less brand recognition; check references relevant to the client's size and vertical *(verify)*.
- Partner ecosystem smaller than established platforms - plan for SI and specialist availability explicitly *(verify current partner list in the client's region)*.
- Documentation still maturing, which slows estimation and integration design and increases reliance on SCAYLE support *(verify how much is publicly accessible)*.
- Fashion focus: other verticals may require adaptation of the product data model *(verify with the client's real attribute and variant requirements)*.
- Geographic reach strongest in DACH and Europe; validate support for other regions *(verify market, tax, payment and language coverage)*.
- Limited self-hosting - it is a managed SaaS, so infrastructure control and data-processing arrangements follow the vendor's terms *(verify the contract and the data-residency guarantee)*.
- Customisation boundaries: some scenarios need development effort, and that effort lands in the frontend or an external service rather than in the platform *(verify per requirement)*.
- No page CMS in the engine, so an external content system is usually added to the landscape *(verify)*.

### 7. Hosting/operations
- Fully managed SaaS, cloud-native, European infrastructure with EU data residency and GDPR compliance *(verify the exact regions and the sub-processor list)*.
- Storefront Hosting is available as managed hosting for headless frontends *(verify SLAs, build pipeline, preview environments, CDN and cache invalidation control)*.
- Operational surface for the client is the SCAYLE Panel plus the APIs; there is no server, shell or database access *(verify)*.
- API rate limits, bulk import throughput and webhook delivery behaviour are the real operational constraints on an integration and must be obtained in writing *(verify)*.
- Release and upgrade model is vendor-driven - establish how breaking API changes are versioned and announced *(verify)*.
- Monitoring and observability: establish what the client can see (API logs, webhook delivery status, error reporting) *(verify)*.

### 8. Ecosystem & partners
- Smaller partner ecosystem than established platforms; strongest in DACH and Europe *(verify)*.
- Add-on marketplace for pre-built extensions *(verify catalogue and maintenance)*.
- Skills required: modern JavaScript/TypeScript for the storefront, plus integration engineering for the API layer *(verify)*.
- Vertical alignment: fashion, lifestyle, consumer goods *(verify)*.
- Reference base: ABOUT YOU itself plus commercial customers *(verify current public references, ideally at the client's scale)*.
- ERP and PSP partner integrations *(verify per system the client runs)*.

### 9. Typical use cases
- Fashion and lifestyle brands building a modern headless storefront *(verify)*.
- Multi-brand fashion retailers needing one backend behind several storefronts *(verify the multi-shop and multi-tenant model)*.
- European D2C brands that require an EU-based, GDPR-compliant platform *(verify)*.
- Omnichannel fashion retailers wanting click and collect, ship from store and store inventory lookup from the omni-channel add-on *(verify the add-on's contents and price)*.
- High-volume fashion operations with complex size and colour management *(verify the volume profile against real references)*.
- Organisations that want ABOUT YOU's proven technology without building it themselves *(verify)*.
- Poor fits to challenge explicitly: B2B commerce, non-fashion verticals with a different product data model, complex B2B scenarios, companies outside Europe without an EU presence, budget-constrained SMBs, and organisations expecting a turnkey shop rather than a headless build *(verify each against the client's real situation)*.
