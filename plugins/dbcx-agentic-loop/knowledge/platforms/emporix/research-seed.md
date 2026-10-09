## Research topics – Emporix
Seed for the platform refresh. Every line below is a HYPOTHESIS *(verify)* until it is confirmed for the engagement's tenant and subscribed services with a developer.emporix.io URL and a date. This is the thinnest-sourced of the four seeds: the vendor material names services and capabilities but no paths and no version numbers, and the vendor's documentation is reported as less extensive than that of the large platforms *(verify)*. Treat every capability claim as unconfirmed until a URL, a vendor statement with a date, or a proof of concept backs it.

**Two facts to establish before anything else:** Emporix ships no frontend and no CMS *(verify)* - storefront, content and their binding are the project's own build - and the ecosystem is young, so scale, partner availability and reference customers are part of the risk assessment, not footnotes *(verify)*.

### 1. Overview
- Cloud-native, API-first, microservices-based commerce platform designed for B2B and complex commerce, originally focused on B2B manufacturing and distribution *(verify)*
- Fully managed multi-tenant SaaS with true multi-tenancy as an explicit differentiator for multi-brand and multi-region setups *(verify what tenancy means operationally - one tenant per brand, per region, or per legal entity)*
- Composable premise: consume only the services needed, replace components without lock-in *(verify which services can genuinely be omitted)*
- German/European heritage with EU data residency and a GDPR focus *(verify the current hosting regions and the cloud provider)*
- Positioning: a modern alternative to SAP Commerce for B2B, more B2B-focused than commercetools and simpler than Spryker for some B2B cases *(verify - this is vendor positioning)*

### 2. Editions/plans & licensing
- Services are sold individually, so the subscribed service set defines what "standard" means for this client - establish it before any coverage verdict *(verify)*
- Professional services are available from the vendor *(verify the split between vendor and partner delivery)*

### 3. B2B capabilities
- Company accounts with hierarchical business customer structures and multi-level buyer organisations *(verify the depth of the hierarchy and how permissions inherit)*
- Configurable approval workflows for order approval *(verify the rule model - value thresholds, roles, custom predicates)*
- Customer- and contract-specific pricing plus volume/tiered pricing through price lists and price models *(verify the price-selection precedence, which decides most B2B pricing questions)*
- Quote management with RFQ and negotiation workflows *(verify the state machine and the back-office UI for sales staff)*
- Purchase-order payment support *(verify)*
- Punchout with OCI and cXML support - notable, because most composable platforms have none *(verify the supported cXML/OCI versions and whether it covers both catalog and order punchout)*
- Cost centres with budget management by department *(verify)*
- Quick order by SKU *(verify whether CSV upload is included)*
- Units of measure and packaging conversion handling, which B2B distribution needs and B2C-derived platforms lack *(verify the unit-handling service scope)*
- B2B-first design is the platform's central claim - built for B2B rather than adapted from B2C *(verify against the requirement list rather than accepting the claim)*

### 4. B2C capabilities
- Product catalog with flexible modelling, product search and filtering, standard cart and checkout flows, discount and campaign engine, customer registration and profiles, multi-site storefronts *(verify each)*
- Vendor positioning: B2C features are functional but that the platform's strength is B2B *(verify which specific B2C requirements in scope fall into the lighter area - promotions depth, loyalty, reviews, wishlists, gift registries, marketing automation)*
- No shipped storefront, so all B2C presentation work is a custom frontend *(verify whether a starter or accelerator exists and what it covers)*

### 5. Architecture & extensibility
- Independent services per domain (product information, pricing and tax, cart and checkout, order management, customer management, inventory, promotions) exposed as REST APIs on api.emporix.io with the tenant in the path *(verify the exact service catalogue and path shape - the knowledge list is reconstructed, not quoted)*
- OAuth2 client-credential authentication with tenant-scoped tokens and role/scope management in an IAM service *(verify the scope model and how storefront-safe access is achieved)*
- Mixins: schema-registered JSON extensions that add structured, validated fields to platform entities - the sanctioned way to extend the data model *(verify how mixins behave in search, in the back office and in exports)*
- Event-driven integration through webhooks and event subscriptions *(verify delivery guarantees, ordering and retry behaviour before an integration depends on them)*
- Built-in PIM capabilities, or integration with an external PIM *(verify how deep the built-in PIM is for large assortments)*
- No server-side extension point inside the platform: custom logic runs in the project's own services beside it *(verify)*
- Content model: no CMS resources; the content-shaped primitives are the media/asset service, localized product and category texts, mixins, and the label/configuration services *(verify)*
- API rate limits and quotas per tenant *(verify the current numbers - not stated in the vendor material)*

### 6. Limitations & typical gaps
- Small market presence and brand recognition; the mitigation is to request references *(verify with two references at comparable scale and business model)*
- Fewer public reference customers and fewer proof points *(verify)*
- Smaller implementation partner network - partner availability in the client's region is a project risk, not a detail *(verify)*
- Documentation less extensive than that of larger platforms, with vendor support as the fallback *(verify and record who confirmed what and when)*
- Smaller extension marketplace, so capabilities that are off-the-shelf apps elsewhere become custom development *(verify per requirement)*
- Lighter B2C depth *(verify)*
- Frontend investment required *(verify)*
- Less proven at very large scale: catalog size, order throughput and peak behaviour need a load reference or a proof of concept rather than a datasheet figure *(verify)*
- No CMS, no shipped back-office breadth comparable to an incumbent suite - establish per capability whether a business user has a screen *(verify)*

### 7. Hosting/operations
- Fully managed SaaS, cloud-native on major cloud providers, multi-tenant *(verify which provider and which regions, and whether EU residency is contractual)*
- The vendor owns platform availability and patching; the customer owns the frontend, the integration services and every composable component *(verify the SLA and the support tiers)*
- Continuous release model without a customer-side version to pin *(verify the deprecation and notice policy - with a young platform this matters more, not less)*
- Environments: establish how many tenants or environments the subscription includes for dev, test and production *(verify)*
- Observability is the customer's responsibility across their own services; platform-side, event streams are the audit trail *(verify what logs and retention the tenant can access)*

### 8. Ecosystem & partners
- ERP integrations for SAP, Microsoft Dynamics and Oracle *(verify whether these are productised connectors or reference implementations)*
- Multiple PSP options and an open integration architecture *(verify the PSP list per market)*
- PIM: built-in or external (Akeneo and similar) *(verify)*
- Any modern frontend framework; API-focused development skills required *(verify whether a maintained starter exists)*
- Vertical focus on manufacturing, distribution and industrial; European roots with global availability *(verify)*
- Competitive framing: SAP Commerce alternative for B2B, more B2B-focused than commercetools, simpler than Spryker *(verify)*

### 9. Typical use cases
- B2B manufacturers with complex pricing models and customer contracts *(verify)*
- Industrial distributors replacing legacy B2B systems *(verify)*
- Organisations evaluating SAP Commerce alternatives that want a modern architecture *(verify)*
- Multi-brand enterprises needing efficient multi-tenant management *(verify)*
- European manufacturers needing an EU-based, GDPR-compliant platform *(verify)*
- Poor fit: B2C-dominant businesses, simple B2C retail, buyers who need an established brand or a large partner network, fast time-to-market needs *(verify)*
