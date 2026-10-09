## Research topics – VTEX (target)
Seed for the version-pair refresh. Every line is a hypothesis *(verify)* until confirmed against a developers.vtex.com / help.vtex.com URL for the account's current app versions and the project's region. Pricing, regional availability and app ownership (VTEX-maintained vs. partner) age fastest.

### 1. Overview
- Cloud-native, API-first commerce platform originating in Brazil, now serving global enterprise customers *(verify current regional coverage)*
- The unified-platform claim: commerce + OMS + marketplace in one product, so no separate OMS license *(verify what the OMS covers versus a dedicated OMS)*
- Marketplace is native: every VTEX store can act as a marketplace or as a seller *(verify)*
- Architecture: multi-tenant SaaS composed of independent services (Catalog, Pricing, Logistics, Checkout, OMS, Master Data, Payments, Intelligent Search, Sessions) *(verify the current service list)*
- VTEX IO is the development environment: apps, workspaces, Store Framework blocks, serverless node/react services *(verify)*
- Strongest differentiators: LATAM depth (local payments PIX and Boleto, local logistics and compliance), native OMS and omnichannel fulfilment *(verify per country)*

### 2. Editions/plans & licensing
- No per-seat licensing; unlimited users *(verify)*
- Some capabilities arrive as apps whose availability and support differ per region *(verify per app)*

### 3. B2B capabilities
- Native B2B through the B2B Suite, delivered as VTEX IO apps rather than as platform endpoints *(verify app names and versions: vtex.b2b-organizations, vtex.b2b-quotes, vtex.b2b-checkout-settings)*
- B2B organizations with multi-level hierarchies, cost centers and organisation-specific pricing *(verify how organisation pricing maps onto trade policies and price tables)*
- Payment terms, purchase orders, quote management, quick order by SKU, configurable order approval, a specialised B2B checkout flow *(verify approval depth - single vs. chained approval)*
- Not claimed and therefore to be treated as absent until proven: punchout (OCI/cXML), contract management depth, CPQ *(verify)*
- Advanced B2B may need customisation *(verify against the concrete requirement list)*
- Structural point to check early: B2B pricing and catalog visibility ride on trade policies (sales channels) - the number of trade policies a design needs is a real constraint *(verify limits)*

### 4. B2C capabilities
- Comprehensive product catalog modelling; Intelligent Search with AI ranking, autocomplete and merchandising rules *(verify)*
- Promotions engine (Rates and Benefits), native subscriptions, Live Shopping, personalisation and customer segmentation *(verify which are native and which are apps)*
- CMS for pages and layouts: Store Framework blocks plus Site Editor content, with the legacy CMS still present on older accounts *(verify which the account uses)*
- Omnichannel: ship-from-store, pickup in store, endless aisle, unified inventory across locations *(verify per country and per carrier integration)*
- Scale claim: Black-Friday-scale traffic handled by the platform *(verify - vendor-stated)*

### 5. Architecture & extensibility
- Headless, API-first microservices behind a multi-tenant SaaS; there is no single versioned API - each service has its own endpoints, its own pub (public) and pvt (private) scopes and its own authentication *(verify per service)*
- Authentication: appKey/appToken headers for server-to-server, user tokens for storefront/session context; License Manager governs roles *(verify current recommendation)*
- VTEX IO: apps are versioned and installed per account; development happens in workspaces and is promoted to master, so environments are workspaces rather than servers *(verify the current CLI and promotion flow)*
- Store Framework: pages declared as JSON block trees (store/blocks/*.json, store/routes.json); a new block type means a custom React component in a custom app *(verify)*
- FastStore: a separate headless (Next.js-based) frontend that does not render Store Framework blocks - a different project, not a configuration switch *(verify current status and support)*
- Checkout: orderForm is the cart and the single source of truth; customisation happens through sanctioned extension points (custom apps, attachments, custom data) rather than by modifying checkout *(verify what the current extension points allow)*
- Custom data: Master Data v2 entities with schemas are the only sanctioned custom persistence - validate query and scale characteristics before treating it as an application database *(verify limits)*
- Integration: REST APIs per service, the order hook and order feed for order events, webhooks, pre-built ERP connectors, Payment Hub with the Payment Provider Protocol for custom gateways, carrier and fulfilment integrations *(verify which connectors are VTEX-maintained)*

### 6. Limitations & typical gaps
- Geographic focus: strongest in LATAM, still building the enterprise footprint in Europe and North America - support coverage and reference customers must be checked per region *(verify)*
- Documentation quality historically challenging, which pushes projects towards partner knowledge - a dependency to plan for *(verify current state)*
- VTEX IO learning curve: proprietary patterns, small experienced talent pool outside LATAM; this is usually the first real project risk *(verify staffing plan)*
- Partner ecosystem smaller outside LATAM *(verify partner availability)*
- Enterprise maturity outside its home market is still being established *(verify reference customers in the project's region)*
- Complex B2B may need customisation beyond the B2B Suite *(verify)*
- Customisation constraints: scenarios that do not fit the IO patterns are the hard cases - checkout above all *(verify per requirement)*
- Marketplace-first data model: sellers, offers, split orders and the fulfilment/marketplace role split shape catalog, pricing and OMS even for a single-seller business, and every integration must respect it *(verify how it lands on the project's ERP interface)*
- No self-hosting, no data residency choice *(verify what the contract offers on data location)*

### 7. Hosting/operations
- Fully managed multi-tenant SaaS: no infrastructure, no maintenance windows, no server access *(verify)*
- Release management happens through IO workspaces and app versions; a rollback is an app version change, not a deployment pipeline *(verify)*
- Observability limited to what VTEX exposes (app logs, order feed, platform status) - no infrastructure metrics *(verify what an enterprise plan adds)*
- Regional infrastructure and CDN are the vendor's; performance work is frontend and app work *(verify)*
- PCI and platform compliance are VTEX's responsibility for the hosted checkout and Payment Hub *(verify the shared-responsibility split)*

### 8. Ecosystem & partners
- Pre-built integrations for ERP (SAP, Oracle, Microsoft), payment providers with strong local coverage (PIX, Boleto, local cards), carriers and the VTEX Shipping Network *(verify which are first-party and which regions they cover)*
- App Store / partner apps for extended functionality; github.com/vtex-apps holds the source of the standard apps *(verify maintenance state per app)*
- VTEX IO certification is the delivery skill; partner concentration is in LATAM with growing presence in the US and Europe *(verify)*
- Middleware and integration partners are commonly used for ERP connectivity rather than direct point-to-point *(verify)*

### 9. Typical use cases
- Best fit: Latin American enterprises or companies expanding into LATAM, marketplace operators, omnichannel retailers with complex fulfilment (ship-from-store, BOPIS, endless aisle), fast-growing D2C brands in emerging markets, grocery and CPG with local delivery, and buyers who want commerce plus OMS from one vendor *(verify)*
- Moderate fit: global companies with LATAM operations, businesses exploring marketplace models, retailers with moderate omnichannel needs *(verify)*
- Poor fit: pure European/North American focus without LATAM interest, simple single-store B2C, complex enterprise B2B needing Spryker/SAP depth, organisations requiring an established global support footprint, requirements needing customisation beyond the IO model, budget-constrained buyers *(verify)*
- Scoring guidance keys on geography, marketplace model, OMS need, omnichannel depth, B2B complexity, development capability, industry and local payment requirements *(verify - fit questionnaire, not a verdict)*
