## Research topics – Shopify Plus (target)
Seed for the version-pair refresh. Every line is a hypothesis *(verify)* until confirmed against a shopify.dev / help.shopify.com URL for the API version (YYYY-MM) and the plan the project actually uses. Prices, limits and plan names age fastest.

### 1. Overview
- Enterprise tier of Shopify: multi-tenant, fully managed SaaS; the merchant never operates infrastructure *(verify)*
- Positioning is speed to value: launches measured in weeks rather than months, at the price of a customization ceiling *(verify)*
- Reliability claim: 99.99% uptime SLA, flash-sale traffic absorbed without capacity planning *(verify SLA wording in the contract, not the marketing page)*
- Conversion argument rests on Shop Pay (accelerated checkout with stored credentials); the vendor claims up to 91% higher conversion than guest checkout *(verify - vendor-measured)*
- Extensibility model is apps + extensions + Shopify Functions (WebAssembly server-side logic), not source-code modification *(verify)*
- App ecosystem quoted at 8,000+ apps and the largest partner network of the platforms compared *(verify count)*

### 2. Editions/plans & licensing
- Plus is a plan, not a separate product: same platform, higher limits plus Plus-only features (checkout extensibility depth, expansion stores, Launchpad, higher API limits) *(verify which features are Plus-gated in the current plan matrix)*
- 10 expansion stores included; additional stores carry their own restrictions *(verify)*

### 3. B2B capabilities
- B2B on Shopify is native since 2022+ and lives inside the same store as B2C, not in a separate wholesale product *(verify)*
- Companies and company locations, multiple buyers per company, location-level payment terms and net terms, purchase orders *(verify)*
- Customer-specific pricing through B2B catalogs and price lists (fixed prices or percentage adjustments), volume/quantity breaks *(verify)*
- Draft orders for sales-rep assisted ordering; quick order and CSV ordering typically need an app *(verify)*
- Legacy password-protected wholesale channel is the predecessor model and is being replaced by B2B on Shopify *(verify sunset status)*
- Known gaps: multi-level approval workflows, punchout catalogs (OCI/cXML) and CPQ-level configuration are app or custom work, not standard *(verify)*
- Third-party B2B apps as mitigation: SparkLayer, Wholesale Club *(verify current fit)*

### 4. B2C capabilities
- Core strength area: catalog, promotions with stacking rules, customer segmentation (Audiences), Shop Pay, Shopify POS for unified commerce *(verify)*
- Internationalisation via Shopify Markets: multi-currency, multi-language, market-specific pricing, duties and localised checkout *(verify feature split between Markets and Markets Pro)*
- Subscriptions are app-based (Subscription APIs + selling plans), not a core module *(verify)*
- Shopify Flow for no-code automation; Launchpad for scheduling sales, product releases and theme changes (Plus) *(verify)*
- Hard catalog limits to design around: 100 variants per product and 3 options per product in the classic model; higher limits announced for newer product APIs *(verify against the current Admin API version)*

### 5. Architecture & extensibility
- Monolithic SaaS core with headless access: Storefront API (GraphQL) for customer-facing reads and cart, Admin API (GraphQL, REST legacy) for back office, Customer Account API for the new account area *(verify)*
- API versioning is quarterly (YYYY-MM) with a supported window; a field can be removed at the next version - pin and track the changelog *(verify current support window)*
- Rate limiting is cost-based (calculated query cost / leaky bucket) on GraphQL and request-based on legacy REST; Plus gets higher buckets *(verify current numbers)*
- Frontend options: Online Store 2.0 Liquid theme (sections, blocks, JSON templates, section groups) or headless with Hydrogen (React) on Oxygen hosting, or any framework on the Storefront API *(verify)*
- Content model: theme sections/blocks for layout, metaobjects and metafields for structured content; no page-tree CMS with workflow or content versioning *(verify)*
- Checkout extensibility: checkout.liquid and Checkout Scripts are replaced by Checkout UI extensions (published extension targets) and Shopify Functions; Functions run in WebAssembly with no network access and a strict execution budget *(verify limits and the final sunset dates)*
- Integration: webhooks, bulk operations for large exports/imports, Flow as an automation surface, pre-built ERP connectors for NetSuite, SAP Business One and Microsoft Dynamics *(verify who maintains each connector)*
- 100+ payment providers; Payments Apps API for a custom provider *(verify)*

### 6. Limitations & typical gaps
- Customization ceiling: scenarios outside the sanctioned extension points end as workarounds or accepted gaps *(verify per requirement)*
- Checkout control is weaker than any self-hosted platform - no arbitrary markup, no synchronous external call inside a Function *(verify)*
- B2B maturity behind dedicated B2B platforms for approvals, punchout and contract logic *(verify)*
- Multi-store: max 10 expansion stores, each with its own catalog and content; Markets vs. separate stores is an architecture decision with no cheap reversal *(verify)*
- Complex products: variant/option limits, no native CPQ or configurator *(verify)*
- No native marketplace / multi-vendor operation *(verify)*
- No self-hosting, no data residency choice, and migrating away is hard - data owned by third-party apps is the worst case *(verify)*
- Vendor lock-in is the explicit trade-off against the operational benefits *(verify)*

### 7. Hosting/operations
- Fully managed multi-tenant SaaS: no maintenance windows, no infrastructure cost line, no server access *(verify)*
- Deployment discipline lives in themes (Git-backed theme deploys), app/extension versions and Functions releases rather than in server pipelines *(verify current CLI/deploy model)*
- Hydrogen storefronts are hosted on Oxygen (Shopify-operated edge runtime) with environment-based deploys *(verify limits: runtime, cache, regions)*
- Observability is limited to what Shopify exposes (webhooks, Flow, app logs, Functions logs) - no infrastructure metrics *(verify)*
- Compliance and PCI are Shopify's responsibility for the hosted checkout *(verify scope of the shared-responsibility model)*

### 8. Ecosystem & partners
- 8,000+ apps in the App Store; the largest partner/agency network of the compared platforms *(verify count)*
- Marketing stack: native Shopify Email plus Klaviyo, Attentive and similar *(verify)*
- Fulfilment: Shopify Fulfillment Network and 3PL integrations *(verify current availability by region)*
- ERP connectors: NetSuite, SAP Business One, Microsoft Dynamics *(verify which are first-party)*
- Certification and delivery skills are broadly available, which lowers the staffing risk versus Spryker/SAP *(verify)*

### 9. Typical use cases
- Best fit: high-growth DTC brands (fashion, beauty, CPG, food and beverage), flash-sale operators, multi-brand retailers with up to 10 storefronts, fast international rollout, teams with limited IT *(verify)*
- Moderate fit: B2B-light wholesale, moderate ERP integration needs, some checkout customization achievable with Functions *(verify)*
- Poor fit: complex B2B enterprises (approvals, punchout, CPQ), heavily customized checkout, data-ownership or on-premise requirements, marketplace operators, more than ~10 distinct brands *(verify)*
- Fit questions: business model, time to market, IT resources, customization need, scale pattern, multi-brand count, B2B complexity and checkout requirements *(verify - use as a fit questionnaire, not as a verdict)*
