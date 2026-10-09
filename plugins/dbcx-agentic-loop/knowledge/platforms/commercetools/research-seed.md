## Research topics – commercetools Composable Commerce
Seed for the platform refresh. Every line below is a HYPOTHESIS *(verify)* until it is confirmed for the engagement's region, API version and licensed products with a docs.commercetools.com URL and a date. Product names, limits and GA status age fastest.

**The single most important architectural fact: commercetools ships NO CMS.** There is no page, template, slot, block or content-version resource in the platform *(verify)*. Every content, landing-page, banner and navigation requirement is met by an external CMS plus a binding layer plus a renderer in your own frontend - three distinct pieces of work, never covered-standard. The same holds for order-management and search-merchandising back-office UIs *(verify the current Merchant Center scope)*.

### 1. Overview
- Cloud-native, API-first, headless commerce platform built on MACH principles (microservices, API-first, cloud-native, headless); founding member of the MACH Alliance *(verify)*
- Fully managed multi-tenant SaaS on Google Cloud Platform, available in several regions (EU, US, AU) *(verify the current region list and data-residency options)*
- No built-in frontend at all; the platform enforces no frontend or architecture decision *(verify)*
- Both REST/HTTP and GraphQL over the same project model; the vendor claims 300+ API endpoints *(verify)*
- Reference customers named by the vendor: Audi, BMW, Danone, Sephora *(verify - reference lists change and belong to the vendor)*

### 2. Editions/plans & licensing
- Separate products around the platform: commercetools Frontend (formerly Frontastic), commercetools Checkout, commercetools Connect *(verify which are licensed in the engagement and what each includes)*

### 3. B2B capabilities
- Business Units with parent/child hierarchies (company and division types) for company account structures *(verify the current hierarchy semantics)*
- Associate Roles with fine-grained permissions for buyers inside a business unit *(verify the permission catalogue)*
- Approval Rules and Approval Flows for order approval based on value, role or custom criteria *(verify the GA status and the expression language)*
- Quote flow as three resources: quote-requests, staged-quotes, quotes *(verify the state machine and who can act at each step)*
- Customer-specific and tiered pricing through embedded prices, Standalone Prices, price tiers and channel/customer-group/store scoping; high-precision (sub-cent) prices *(verify the price-selection rules, which decide most B2B pricing questions)*
- No punchout (OCI / cXML), no budget/cost-centre engine, no contract-document management in the standard *(verify)*
- B2B admin work still happens in the Merchant Center or in a custom application - check per capability whether a business user has a screen *(verify)*

### 4. B2C capabilities
- Flexible product modelling through Product Types and attributes, variants, and bundle/configurable modelling by convention rather than by a dedicated resource *(verify whether a bundle resource exists now)*
- Product Selections for per-store assortments; Stores and Channels for multi-brand, multi-market and multi-currency setups *(verify)*
- Discounts: cart discounts, product discounts, discount codes, with a documented predicate language *(verify the predicate capabilities against the promotion requirements in scope)*
- Search: /product-projections/search with faceting and filtering, plus the newer Product Search API *(verify which one is current and GA, and what search merchandising exists)*
- Customer groups and personalisation hooks; personalisation itself is an external concern *(verify)*
- Composable checkout with session management; commercetools Checkout is a separate product *(verify what it covers versus a hand-built checkout)*
- State machines for order, payment, review, product and quote lifecycles *(verify)*

### 5. Architecture & extensibility
- One project endpoint per project (https://api.<region>.commercetools.com/<projectKey>/<resource>), OAuth2 client-credential tokens with scopes from a separate auth host *(verify the current scope model)*
- Writes go through per-resource UPDATE ACTIONS with optimistic concurrency: send the resource version, handle 409 by re-reading - this is the real API contract and the usual retrofit cost for legacy integration code *(verify)*
- Reads for listing and search use /product-projections/search or the Product Search API, which are EVENTUALLY CONSISTENT projections of the write model - read-after-write in a storefront flow will break *(verify the documented consistency window)*
- Reference expansion loads related resources in one request, with a documented depth limit *(verify)*
- Extensibility: API Extensions (synchronous hooks inside a request, hard timeout, must be highly available or writes fail), Subscriptions (at-least-once, unordered message delivery to a queue), Custom Applications inside the Merchant Center, and Connect for deployable connectors *(verify the timeouts, retry policy and Connect runtime limits)*
- Import API on a separate host for asynchronous bulk loads; the Export/GraphQL route for extraction *(verify the current bulk options)*
- Custom fields via Types on any resource, and CustomObjects as an untyped JSON store *(verify the size and query limits of CustomObjects before designing anything on them)*
- Official SDKs for Java, TypeScript/JavaScript, PHP, .NET and Python *(verify which are actively maintained)*
- Per-project limits and quotas (request rate, resource counts, query restrictions, expansion depth) shape every integration design *(verify the current numbers)*

### 6. Limitations & typical gaps
- No CMS, no order-management UI, no search-merchandising UI, no CSR/impersonation tooling and no document generation in the standard - each is a product selection or custom work *(verify the current Merchant Center scope, which is the one thing that genuinely changes)*
- No built-in frontend: significant frontend investment, own SSR/caching, own SEO and URL model beyond slugs *(verify what commercetools Frontend covers)*
- Limited out-of-the-box features compared with all-in-one platforms, mitigated by the Connect marketplace *(verify what a connector really covers before counting it as coverage)*
- Steep learning curve and mature CI/CD required for the frontend, *(verify against the client's own capability)*
- Longer time to market than turnkey solutions *(verify)*
- Eventual consistency of the search projection and optimistic concurrency on writes are the two most common sources of migration surprises *(verify)*

### 7. Hosting/operations
- Fully managed multi-tenant SaaS: the vendor owns scaling, patching and availability of the API; the customer owns the frontend, the integration services, the CMS and every other composable piece *(verify the current SLA)*
- GCP-based with multi-region availability and data-residency options *(verify the exact regions and whether the project can be moved)*
- Observability is API-level: the customer must build logging, tracing and alerting across their own services; platform-side there are Messages and Subscriptions as the audit trail *(verify what retention Messages have)*
- No environments in the platform sense - projects are the isolation unit, so dev/test/prod means multiple projects with their own data and keys *(verify the licensing implication of extra projects)*
- Release model is continuous with a public changelog; there is no version to pin, so behaviour changes arrive without a project upgrade *(verify the deprecation policy and notice period)*

### 8. Ecosystem & partners
- Large partner network and the Connect marketplace for certified integrations (payment, ERP, PIM, tax, search) *(verify which connectors are vendor-maintained versus partner-maintained)*
- Frontend accelerators: commercetools Frontend (Frontastic), Vue Storefront, Vercel Commerce *(verify their current support status)*
- Frequently paired with an external PIM (Akeneo, Salsify), an external CMS, an external search/merchandising product and an external OMS *(verify which of these the engagement already owns - it changes the gap list substantially)*
- ERP adjacency via connectors for SAP, Microsoft Dynamics, Oracle *(verify connector depth, especially for pricing and availability)*
- MACH Alliance leadership as a talent and partner argument *(verify)*

### 9. Typical use cases
- Digital-first enterprises with strong development teams that want complete frontend freedom *(verify)*
- Multi-brand portfolios on one commerce backend with brand-specific experiences *(verify)*
- Global retailers needing multi-region, multi-currency and multi-language at scale *(verify)*
- B2B manufacturers with complex pricing (customer-specific, volume tiers, contracts) *(verify)*
- Omnichannel retailers integrating web, mobile, IoT and in-store *(verify)*
- Poor fit: SMBs needing quick time-to-market, organisations without a development team, buyers who want an all-in-one solution with a built-in frontend *(verify)*
