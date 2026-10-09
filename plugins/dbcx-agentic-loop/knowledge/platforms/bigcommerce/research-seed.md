## Research topics – BigCommerce
Seed for the platform refresh. Every line below is a HYPOTHESIS *(verify)* until it is confirmed for the engagement's plan tier and API versions with a developer.bigcommerce.com / support.bigcommerce.com URL and a date. Prices, plan boundaries, rate limits and widget lists age fastest.

### 1. Overview
- Multi-tenant SaaS commerce platform positioned as "Open SaaS": no payment-gateway lock-in and no platform transaction fees on top of the processor's fees *(verify)*
- Serves mid-market to enterprise merchants with a multi-channel focus (own storefront plus marketplaces) *(verify)*
- Two frontend models: the Stencil theme engine (Cornerstone as the reference theme) and headless on the GraphQL Storefront API, with Catalyst (Next.js) as the official starter *(verify the current Catalyst status and version)*
- API surfaces: V3 Management REST, remaining V2 REST endpoints, GraphQL Storefront API, a GraphQL Admin API for selected domains, plus webhooks and the Scripts API *(verify which resources are still V2-only)*
- There is NO server-side code base: extension means an app plus an external service, so this pack has no source role *(verify only in the sense of confirming the SaaS boundary for the plan in scope)*

### 2. Editions/plans & licensing
- Plans carry an annual sales threshold that forces an upgrade once exceeded *(verify the current thresholds)*
- B2B Edition is a paid add-on, available on Enterprise plans *(verify the current packaging and whether it is still a separate product)*
- Some capabilities (multi-storefront, price lists, customer-group depth, faceted search, API rate limits) are tier-gated - the plan matrix decides feasibility, not the API reference *(verify each capability in scope against the tier)*
- No platform transaction fees; 65+ payment gateways *(verify the count and the gateway availability per country)*

### 3. B2B capabilities
- B2B Edition adds company accounts, a self-service buyer portal, corporate hierarchy, sales quotes, invoice management, shared shopping lists, quick order, purchase-order payment, company price lists and sales-rep masquerade ("super admin") *(verify the current feature list)*
- B2B Edition runs on its own API host and data model alongside the core store, so company/quote/invoice data must be joined in the frontend or in middleware *(verify)*
- Customer-specific pricing is modelled as price lists assigned to customer groups or companies *(verify the limits on price-list count and record volume)*
- Depth is explicitly mid-market: Spryker/SAP-level B2B is a poor fit *(verify against the engagement's requirement list)*
- No punchout (OCI / cXML) and no budget/cost-centre engine in the standard *(verify)*
- Approval workflows beyond the shipped ones have no server-side engine and must live in an external service *(verify)*

### 4. B2C capabilities
- Catalog: all product types with variants, options and modifiers; the vendor claims handling of 600+ variants per product and 10k-500k SKU catalogs *(verify the current documented limits)*
- Multi-storefront: multiple storefronts (Channels/Sites) from one backend with shared catalog and orders *(verify which resources are channel-aware)*
- Channel Manager for Amazon, eBay, Walmart, Facebook, Google and POS channels *(verify the current channel list)*
- One-page optimised checkout, plus Open Checkout / Checkout SDK and embedded checkout for customisation *(verify the customisation boundary)*
- Promotions engine, customer groups for segment pricing and content, abandoned-cart recovery *(verify which tier includes abandoned cart)*
- Faceted search on higher tiers, BOPIS, real-time carrier rates and label printing through Shipping Manager *(verify tier gating)*

### 5. Architecture & extensibility
- Fully managed multi-tenant SaaS; no access to servers, no custom server-side code, no database access *(verify)*
- Extension model: OAuth apps with scopes (public or single-click), webhooks for events, the Scripts API for storefront script injection, custom Page Builder widgets (widget template + JSON schema), and the Checkout SDK for checkout UI *(verify)*
- Content model: Page Builder widget instances in theme regions, addressable through /v3/content/widgets, /widget-templates, /placements, /regions - the instance data is API-readable but the RENDERING is a Handlebars template in the Stencil theme, so a headless frontend must reimplement each widget it needs *(verify what Makeswift covers for Catalyst)*
- Storefront data access requires a storefront API token, and logged-in data a customer-impersonation token; Management API tokens must never reach a browser *(verify the current token types and their scopes)*
- Rate limits are per plan and per store and are the main integration design constraint *(verify the current numbers per tier)*
- Webhook delivery is at-least-once and not ordered, so consumers must be idempotent *(verify the documented guarantees)*
- 1,000+ apps in the marketplace and pre-built ERP connectors for NetSuite, Acumatica, SAP Business One *(verify counts and connector scope)*

### 6. Limitations & typical gaps
- No server-side extension point: any rule, validation or enrichment beyond configuration runs outside the platform, with the resulting latency and consistency cost *(verify)*
- Checkout customisation is bounded by Open Checkout / Checkout SDK / embedded checkout - custom checkout steps with platform-side validation are the recurring hard stop *(verify the current boundary)*
- B2B depth below Spryker/SAP level, and B2B Edition being a separate system beside the core store *(verify)*
- Smaller app ecosystem than Shopify (1,000 vs 8,000+) and smaller partner network outside the US *(verify)*
- Stencil theme ecosystem considered less modern than alternatives, with headless/Catalyst as the mitigation *(verify)*
- Some enterprise features are Enterprise-tier only, so plan requirements must be fixed up front *(verify)*
- No structured content model, no content versioning and no scheduled publishing in the standard *(verify)*
- Historical data migration is limited to what the order and customer APIs accept *(verify whether original order ids can be preserved)*

### 7. Hosting/operations
- Fully managed and multi-tenant: BigCommerce owns uptime, scaling, PCI scope of the hosted checkout and platform patching *(verify the current SLA and PCI attestation level)*
- No environments to manage; a sandbox store is the usual development vehicle, and there is no platform-level staging/promotion of content or configuration *(verify)*
- A headless frontend is hosted by the customer (Vercel or equivalent for Catalyst), so operations, caching and CDN for the storefront become the customer's responsibility *(verify)*
- Observability is limited to platform reports, webhook logs and app-side logging *(verify what is available per tier)*
- Data residency and region choice *(verify the available regions - the partner network is US-centric and hosting regions are not addressed)*

### 8. Ecosystem & partners
- 1,000+ apps, 65+ payment gateways, built-in carrier integrations *(verify)*
- ERP adjacency: NetSuite, Acumatica, QuickBooks, SAP Business One *(verify)*
- Marketing: Klaviyo, Mailchimp, Google, Facebook *(verify)*
- Unique WordPress path: the BigCommerce for WordPress plugin as headless commerce for WordPress sites *(verify whether it is still actively maintained)*
- Partner network smaller globally, especially outside the US - a risk to validate per region *(verify)*

### 9. Typical use cases
- Multi-channel retailers selling across marketplaces and their own storefront *(verify)*
- Mid-market B2C brands wanting SaaS simplicity with a headless option *(verify)*
- B2B distributors needing a self-service buyer portal without enterprise complexity *(verify)*
- Merchants who want payment-gateway freedom without platform transaction fees *(verify)*
- Poor fit: complex B2B at SAP/Spryker level, very large enterprises needing custom infrastructure, heavily customised checkout, heavy reliance on a large app ecosystem *(verify)*
