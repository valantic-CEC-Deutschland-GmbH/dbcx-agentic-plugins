## Research topics – Shopware 6 (source and target)
Seed for the version-pair refresh. Every line is a hypothesis *(verify)* until confirmed against a developer.shopware.com / docs.shopware.com / changelog URL for the project's exact 6.x minor, edition and deployment model (self-hosted, PaaS, SaaS). Prices, plan names and feature gating age fastest.

### 1. Overview
- Open-source commerce platform from Germany, now in its 6th major version; API-first core with an optional shipped Storefront *(verify)*
- Stack: PHP 8.x, Symfony 6, Vue.js administration, MySQL/MariaDB, optional Elasticsearch/OpenSearch *(verify exact minimum versions per 6.x minor)*
- Positioning: modern architecture plus business-user empowerment (Flow Builder, Rule Builder) aimed at the mid-market as an alternative to Adobe Commerce or SAP *(verify)*
- Two named differentiators: Flow Builder (no-code process automation) and Rule Builder (conditions for pricing, shipping, availability without code) *(verify)*
- Community Edition is described as genuinely fully featured; the commercial plans add the B2B suite and enterprise features *(verify what exactly is gated in the current plan matrix)*
- Extension marketplace quoted at 4,000+ extensions *(verify count)*

### 2. Editions/plans & licensing
- Community Edition: free, open source, MIT license *(verify - check the license of shopware/core and of shopware/commercial separately)*
- CRITICAL for any plan comparison: B2B Components and several commercial features live in the `shopware/commercial` package, which is not part of the open-source repository - a feature can be "Shopware standard" and still require a paid plan *(verify per feature)*

### 3. B2B capabilities
- B2B Suite / B2B Components (Commercial / Enterprise): company management, employee management per company, role-based granular permissions *(verify which plan)*
- Customer-specific pricing (individual price lists per customer), quick order by SKU, offer/quote management, order approval workflows, budget management per employee or department, cost centers *(verify per plan and per 6.x minor - the B2B feature set was rebuilt from the Shopware 5 B2B Suite into 6 B2B Components)*
- Customer-group registration (B2B sign-up with approval) exists in the standard: /store-api/customer-group-registration *(verify)*
- Known gaps: may not match Spryker or SAP Commerce for very complex B2B - punchout (OCI/cXML) and CPQ are named as poor-fit criteria *(verify whether any standard or Store extension covers punchout)*
- Open question for every B2B project: Store API coverage for the B2B flows when the frontend is headless - the B2B Components UI is built for the Storefront/administration first *(verify route by route)*

### 4. B2C capabilities
- Shopping Experiences: drag-and-drop CMS (sections, blocks, elements) with layouts assigned per category, product and landing page *(verify)*
- Promotions engine with rule-based conditions and discount stacking, dynamic product groups (automated collections), SEO tooling *(verify)*
- Sales channels: multiple storefronts/channels from one backend with their own catalog visibility, currencies, languages and CMS layouts *(verify limits)*
- Product types: variants (property/option based), sets and bundles *(verify what bundles need - core vs. Commercial vs. extension)*
- Elasticsearch/OpenSearch for high-volume catalog search *(verify when it becomes mandatory - catalog size thresholds)*
- Flow Builder for transactional automation (mails, state changes, tags) and Rule Builder for pricing/shipping/availability conditions *(verify the action catalogue of the target minor)*

### 5. Architecture & extensibility
- API-first: Store API (customer-facing) and Admin API incl. Sync API (back office, bulk); every DAL entity is automatically exposed on the Admin API *(verify)*
- Two extension models: PHP plugins (full DI access, self-hosted/PaaS only) and apps (manifest.xml + webhooks + app scripts + external app server, the only model allowed on SaaS) *(verify the current app-script capability set - it is the ceiling for SaaS extensibility)*
- Extension mechanics: Symfony DI service decoration, event subscribers on entity and business events, Twig block extension via `sw_extends` vs. full template override, EntityExtension vs. custom fields, tagged collections (cart processors, rules, payment handlers) *(verify the tag names of the target minor)*
- Data layer: DAL (EntityDefinition, EntityRepository, Criteria) rather than Doctrine ORM entities; schema changes through plugin migrations *(verify)*
- Content model: cms_page/section/block/slot as DATABASE data - CMS layouts do not live in the repository and do not travel with the code *(verify)*
- Frontend options: default Storefront (Twig), PWA / Vue Storefront, custom headless; Shopware Frontends is the current first-party headless toolkit *(verify current name and maturity)*
- Integration: REST Admin API, Store API, app system with webhooks, Sync API for bulk, ERP connectors for SAP Business One and Microsoft Dynamics via middleware, payment providers (Mollie, Stripe, PayPal, Klarna, Adyen) *(verify which connectors are first-party)*

### 6. Limitations & typical gaps
- Geographic focus: strong in DACH/Europe, limited partner presence outside Europe *(verify)*
- Enterprise B2B ceiling versus Spryker/SAP for very complex scenarios *(verify against the concrete requirement list)*
- Headless maturity: the Store API is still evolving - coverage gaps are most likely in B2B, account and CMS-adjacent flows *(verify per route)*
- Cloud/SaaS is comparatively young and APP-ONLY: no PHP plugins, no filesystem persistence, no custom cron, no raw SQL - the single most consequential constraint for a migration *(verify the current SaaS extension capability list)*
- Rule Builder conditions evaluate data Shopware knows; a live ERP price or stock check needs a custom rule provider - which is a PHP plugin and therefore not available on SaaS *(verify)*
- Flow Builder is a fixed action catalogue plus custom/app actions; no free scripting, limited retry/error semantics for long-running or external calls *(verify)*
- Marketplace / multi-vendor capabilities limited natively *(verify)*
- Brand recognition and hiring pool outside Europe *(verify)*

### 7. Hosting/operations
- Three deployment models with materially different constraints: Shopware Cloud (SaaS, apps only), Shopware PaaS, self-hosted (open source or commercial) *(verify what the project's contract actually covers)*
- SaaS: no server access, no filesystem persistence, no custom console commands or workers, no direct database access, extension only through the app system *(verify)*
- PaaS: plugins allowed, but ephemeral containers, object storage for media, build-time asset compilation, managed workers/cron and outbound network policy *(verify)*
- Self-hosted: any PHP hosting; operational load includes MySQL/MariaDB, Elasticsearch, message queue workers, cron and asset builds *(verify recommended topology per traffic class)*
- Deployment discipline: composer-managed plugins, `plugin:install/activate`, `database:migrate`, theme and administration asset builds - and the `plugin` DB table as the actual activation authority *(verify)*

### 8. Ecosystem & partners
- 4,000+ extensions on the Shopware Store *(verify)*
- PIM: Akeneo integration available; ERP: SAP Business One, Microsoft Dynamics and various middleware *(verify who maintains them)*
- Payment: Mollie, Stripe, PayPal, Klarna, Adyen *(verify first-party vs. partner)*
- Staffing: PHP/Symfony developers; a common migration path is from Magento 1/2 *(verify)*
- Partner network concentrated in DACH; global projects usually run through a DACH partner *(verify)*

### 9. Typical use cases
- Best fit: DACH mid-market retailers, B2B wholesalers and distributors needing solid B2B without SAP/Spryker complexity, Magento 1/2 migrants, multi-channel retailers, organisations that value open source but want a support option, teams with Symfony/PHP capability *(verify)*
- Moderate fit: international companies with a DACH headquarters, businesses scaling from SMB to mid-market, moderate B2B requirements *(verify)*
- Poor fit: global enterprises needing a worldwide partner network, very complex B2B, non-PHP organisations, teams that need a mature multi-tenant SaaS today, large-scale marketplaces, US/APAC-only businesses *(verify)*
- Scoring guidance keys on geography, B2B complexity, PHP/Symfony availability, open-source preference, automation appetite, business-user empowerment, Magento migration context and timeline *(verify - fit questionnaire, not a verdict)*
