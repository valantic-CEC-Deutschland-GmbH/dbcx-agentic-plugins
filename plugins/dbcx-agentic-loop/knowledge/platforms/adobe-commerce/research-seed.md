## Research topics – Adobe Commerce (Magento 2)
Seed for the platform refresh. Every line below is a HYPOTHESIS *(verify)* until it is confirmed for the engagement's exact version, edition and deployment model with a developer.adobe.com / experienceleague.adobe.com URL and a date. Counts and version numbers age fastest.

### 1. Overview
- Adobe Commerce is the commercial edition of the open-source Magento 2 code base, sold as a managed PaaS (Adobe Commerce Cloud), as an on-premise licence, or self-hosted on AWS/Azure/GCP *(verify)*
- Monolithic PHP application with a modular structure; headless is an option on top, not the default *(verify)*
- Stack: PHP 8.x, MySQL/MariaDB, Elasticsearch/OpenSearch, Redis, Varnish (Fastly on Cloud), RabbitMQ *(verify the exact support matrix of the target 2.4.x release)*
- Frontends: Luma theme (server-rendered), PWA Studio, or a custom headless frontend; Adobe additionally pushes an Edge Delivery Services storefront line *(verify whether it is the recommended default for the target release)*
- Positioning: the most feature-complete native B2B platform with deep customization freedom and Adobe Experience Cloud integration *(verify against the current product page)*

### 2. Editions/plans & licensing
- Magento Open Source (free) vs Adobe Commerce (licensed) vs Adobe Commerce Cloud (licence + managed infrastructure) - B2B, Content Staging & Preview, customer segments, dynamic blocks, Live Search, Product Recommendations and Payment Services are NOT all in Open Source *(verify the exact feature-by-edition matrix; this decides most fit questions)*
- Cloud comes in Starter and Pro with different environment counts, service options and cron limits *(verify)*

### 3. B2B capabilities
- B2B module (Adobe Commerce only): company accounts, company users with roles and permissions, company hierarchy, company credit with credit limits and payment on account *(verify)*
- Shared catalogs: customer-group-scoped product visibility and pricing *(verify how shared-catalog pricing interacts with tier prices and the price index)*
- Negotiable quotes: full RFQ workflow with buyer/seller negotiation rounds and quote-to-order conversion *(verify the state machine and its API coverage)*
- Requisition lists, quick order (SKU entry and CSV upload), purchase orders with approval rules based on order value and role *(verify)*
- Typical REST surface: POST /V1/company, POST /V1/company-credit/{companyId}, POST /V1/shared-catalog, POST /V1/negotiable-quotes *(verify the full route list and the corresponding GraphQL coverage - they are not equivalent)*
- No standard punchout (OCI / cXML), no standard installed-base or equipment entity, no standard contract-price engine beyond shared catalogs and tier prices *(verify)*

### 4. B2C capabilities
- Product types: simple, configurable, bundle, grouped, virtual, downloadable, with custom options *(verify)*
- Catalog: categories, EAV attributes, attribute sets, layered navigation; Live Search and Adobe Sensei-driven recommendations as separate services *(verify which are included in the target edition)*
- Promotions: cart price rules, catalog price rules, coupon codes *(verify)*
- Content: Page Builder, CMS pages and blocks, widgets, dynamic blocks *(verify)*
- Customer segments and personalization, with Adobe Target / Adobe Analytics integration for the Experience Cloud path *(verify - segments are an Adobe Commerce feature)*
- Multi-website / multi-store / multi-store-view from one installation, with per-scope configuration *(verify the scope behaviour for every custom attribute)*
- Multi-source inventory (MSI) with sources, stocks, reservations and distance-based source selection *(verify behaviour with an external WMS)*
- Content Staging & Preview for scheduled content, price and rule changes *(verify which entities support staging)*

### 5. Architecture & extensibility
- Extension unit is a MODULE under app/code/<Vendor>/<Module> with registration.php and etc/module.xml; Marketplace extensions install under vendor/ *(verify)*
- Dependency injection through etc/di.xml: preferences, plugins (before/around/after), constructor arguments, virtual types; declarative schema through etc/db_schema.xml *(verify)*
- Storefront API = GraphQL (queries and mutations, customer token auth); integration API = REST /V1 with searchCriteria plus async and bulk variants; SOAP still exists *(verify whether SOAP is deprecated in the target release)*
- API Mesh and App Builder are the sanctioned way to add logic and aggregate APIs off-platform instead of extending the monolith *(verify the current product names, limits and pricing)*
- Message queues (RabbitMQ) for asynchronous work, cron groups for scheduled work, indexers with on-save vs on-schedule mode plus mview change logs *(verify)*
- Content model: Page Builder writes HTML with data-content-type attributes into the CMS content field, so GraphQL returns markup, not a component tree - a headless frontend needs one renderer per content type *(verify PWA Studio's covered set)*
- Integration: 4,000+ Marketplace extensions and connectors for SAP, Oracle, Microsoft Dynamics, NetSuite; PIM pairing with Akeneo, Salsify, inRiver *(verify counts and connector maturity)*

### 6. Limitations & typical gaps
- Customizations and core patches complicate upgrades; a patched vendor/ tree is the largest hidden migration cost *(verify by counting patches and shadowed classes in the engagement's repository)*
- GraphQL is not feature-complete against /V1, most visibly for B2B (negotiable quotes, requisition lists, company hierarchy and credit) *(verify per version - this is the decisive D4 question for a headless target)*
- Performance is resource-intensive: full-page cache variation under customer-specific pricing and shared catalogs, price-index size, and indexer mode are the recurring bottlenecks *(verify)*
- Live ERP price and stock lookups fight the indexed and page-cached design *(verify the sanctioned pattern for the target release)*
- Steep learning curve and scarce Magento-specialised PHP talent *(verify for the engagement's region)*
- Long time to market for a full implementation *(verify)*
- Page Builder content types have no headless renderer unless one is written; widgets and dynamic blocks are server-resolved and opaque to a headless client *(verify)*

### 7. Hosting/operations
- Adobe Commerce Cloud: read-only application file system at runtime except pub/media, var and declared mounts; cron only through the crontab in .magento.app.yaml; service versions pinned in .magento/services.yaml; Fastly as CDN with VCL changes only through the Fastly module's custom snippets *(verify the current limits per Starter/Pro)*
- Deployment through ece-tools build/deploy/post-deploy hooks with a maintenance window; patches applied from m2-hotfixes/ at build time *(verify)*
- Deploy-time configuration (Cloud UI variables, CONFIG__* environment variables) ranks after everything in the repository and is invisible to a code-only analysis *(verify per environment)*
- On-premise and self-hosted deployments have none of the Cloud restrictions but carry full infrastructure, patching and security responsibility *(verify which model the engagement targets)*
- Upgrade cadence: 2.4.x patch releases with a published security and quality-patch programme *(verify the support end date of the version in scope)*

### 8. Ecosystem & partners
- Adobe Solution Partner network, large and global; 4,000+ Marketplace extensions *(verify)*
- Strongest adjacency is Adobe Experience Cloud: Analytics, Target, Experience Platform, AEM *(verify which of these the engagement actually licenses)*
- Payment gateways: PayPal, Braintree, Adyen and many others, plus Adobe Payment Services *(verify availability per country)*
- Large open-source community around github.com/magento/magento2, which is often the only source for behaviour questions *(verify)*

### 9. Typical use cases
- Large B2B manufacturers and distributors with complex catalogs, pricing and approval workflows *(verify)*
- Hybrid B2B/B2C and multi-brand, multi-website enterprises served from one installation *(verify)*
- Organisations already invested in Adobe Experience Cloud *(verify)*
- Poor fit: fast time-to-market needs, simple B2C, teams without PHP/Magento capability, buyers who want SaaS simplicity *(verify)*
