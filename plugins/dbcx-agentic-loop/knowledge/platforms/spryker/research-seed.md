## Research topics – Spryker Commerce OS (source and target)
Seed for the version-pair refresh. Every line is a hypothesis *(verify)* until confirmed against a docs.spryker.com / GitHub CHANGELOG URL for the MODULE versions and the release group the project pins. Spryker versions modules independently, so a feature claim without a module name and version is unverifiable.

### 1. Overview
- Composable, headless commerce platform for complex B2B, B2C and marketplace scenarios; described as a "commerce operating system" rather than a shop *(verify)*
- Modularity is the core promise: 900+ independent modules, install only what is needed, replace anything *(verify count)*
- Architecture layers: Yves (customer-facing), Zed (back office and business logic), Glue API (headless API layer), Backoffice (merchant UI) *(verify current application names - the Backoffice and Glue Backend applications were reworked)*
- Stack: PHP 8.x, Symfony components, PostgreSQL or MySQL, Redis, Elasticsearch, RabbitMQ *(verify supported versions per release group)*
- Deployment: Spryker Cloud Commerce OS (PaaS) or self-hosted, both container-based via the Docker SDK *(verify)*
- Positioned as the modern alternative for enterprises replacing SAP Commerce with comparable B2B depth *(verify)*

### 2. Editions/plans & licensing
- Commercial license, priced on GMV/revenue tiers; no free community edition of the full suite *(verify)*
- Spryker Cloud Commerce OS as managed PaaS with infrastructure included *(verify what the SLA covers)*
- Marketplace Suite and other suites are separately licensed capability packages *(verify which suites a project needs)*
- Delivery through certified partners is the normal model *(verify partner availability in the project's region)*
- Release model: release groups / product releases bundling module versions - upgrade cost is per module, which is the platform's stated upgrade advantage *(verify how far behind the project's modules are)*

### 3. B2B capabilities
- Company accounts with multi-level organisational hierarchies, business units, departments and cost centers *(verify module names: CompanyUser, CompanyBusinessUnit, ...)*
- Granular roles and permissions per company user; configurable approval processes *(verify approval depth - single-level vs. chained)*
- Quote management (RFQ) with negotiated pricing and quote versions *(verify)*
- Shopping lists (multiple, shareable, quick reorder) and quick order by SKU/CSV *(verify)*
- Agent Assist: sales-rep impersonation and support *(verify)*
- Punchout: OCI and cXML support *(verify module and version - punchout is a frequent differentiator claim)*
- Contract/customer-specific pricing agreements *(verify how it interacts with the price read model)*
- Packaging units (cases, pallets) and measurement units (sell by weight, length, volume) - named as unique differentiators against Shopware/Shopify *(verify)*
- Merchant relations for B2B relationship management *(verify)*

### 4. B2C capabilities
- Product management incl. configurable products and bundles, Elasticsearch-powered faceted search and navigation *(verify)*
- Promotions/discount engine, wishlists, customer accounts with registration and profiles *(verify)*
- CMS with pages, blocks and slots plus typed content items *(verify - see content_model_notes: this is not a page builder)*
- Multi-store and multi-currency/multi-language from a single code base *(verify how stores are configured: config/Shared/stores.php plus per-store OMS and search indexes)*
- Spryker is overengineered for simple B2C - out-of-the-box storefront breadth is thin because the demo shops are reference implementations *(verify)*

### 5. Architecture & extensibility
- Glue API is the headless surface, split into a Storefront API and a Backend API application; resources are registered through resource route plugins *(verify which resources exist in which application for the project's version)*
- Extension model: project code under src/Pyz wired through *DependencyProvider plugin stacks; subclassing core classes is normal practice, patching vendor code is not *(verify)*
- Transfer objects (*.transfer.xml) are the cross-layer data contract; Propel is the ORM and schema merge mechanism *(verify)*
- Publish & Synchronize: Zed writes, an event/queue pipeline publishes read models into Redis (storage) and Elasticsearch (search), and Yves/Glue read only those - a new customer-facing data need often means a new P&S pipeline, not just a query *(verify)*
- OMS state machines in config/Zed/oms/*.xml with command/condition plugins are the order process *(verify how many state machines and stores)*
- Separate applications (Yves, Zed, Glue, Backoffice, backend gateway) run as separate deployments - no shared session assumptions *(verify)*
- Integration: Glue API, App Composition Platform (ACP) for pre-built integrations, ERP connectors for SAP, Microsoft Dynamics, Oracle, PIM connectors for Akeneo, Stibo, Informatica, payment via Stripe/Adyen/PayPal, middleware compatibility with MuleSoft/Boomi/Celigo *(verify which are first-party modules and which are partner-built)*
- Marketplace: native marketplace suite with merchant portal, merchant products/offers, split orders, merchant orders and commission management *(verify module set)*

### 6. Limitations & typical gaps
- Complexity and learning curve: needs experienced, ideally certified developers; the first weakness *(verify staffing plan)*
- Ecosystem size: fewer partners and extensions than Magento/Shopify - more is built rather than installed *(verify)*
- Frontend investment: headless means the frontend is a project, and even Yves is a reference implementation to be finished *(verify)*
- Documentation historically challenging, improving; many features arrive as an integration guide plus glue code the project writes *(verify per feature)*
- Market presence and brand recognition outside DACH *(verify)*
- Implementation time: 6-12+ months for complex projects *(verify against the project timeline)*
- Practical trap for assessments: "Spryker has feature X" often means a module exists whose integration guide has 20 steps - always ask whether the storefront part exists *(verify)*

### 7. Hosting/operations
- Spryker Cloud Commerce OS (PaaS) or self-hosted; Docker SDK builds the images and defines the applications in deploy*.yml *(verify)*
- No persistent local filesystem: media and import files through object storage *(verify)*
- Scheduled work through the platform scheduler (Jenkins/cron declared in deploy*.yml), queue workers as their own application *(verify)*
- Operating a self-hosted Spryker means owning PostgreSQL/MySQL, Redis, Elasticsearch, RabbitMQ and the worker fleet *(verify)*
- Zero-downtime deployment and the P&S re-publish/reindex cost are real operational topics *(verify how long a full publish takes at the project's catalog size)*

### 8. Ecosystem & partners
- Strong SAP and Microsoft Dynamics integration story; often paired with Akeneo or an enterprise PIM *(verify)*
- App Composition Platform apps as the vendor's answer to a smaller extension marketplace *(verify current app catalogue)*
- Certified PHP developers with Spryker certification; Spryker Academy as the training path *(verify)*
- Strongest presence in DACH, expanding globally; partner access outside DACH is called out as a risk *(verify for the project's region)*

### 9. Typical use cases
- Best fit: complex B2B manufacturers and distributors (sophisticated pricing, packaging units, punchout), marketplace operators, B2B/B2C hybrids on one platform, automotive and industrial companies with complex configurations, enterprises replacing SAP Commerce, organisations with strong development teams *(verify)*
- Moderate fit: mid-market B2B with growing complexity, businesses exploring marketplace models, headless requirements with moderate B2B needs *(verify)*
- Poor fit: simple B2C retailers, budget-constrained organisations, projects needing a quick launch, teams without strong development resources, regions without certified partner access, buyers who want all-in-one SaaS *(verify)*
- Scoring guidance keys on B2B complexity, marketplace ambition, development resources, timeline, architecture preference, industry, SAP-replacement context and region *(verify - fit questionnaire, not a verdict)*
