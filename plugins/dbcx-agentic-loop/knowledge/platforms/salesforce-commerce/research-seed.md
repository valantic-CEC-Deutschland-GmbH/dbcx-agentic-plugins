## Research topics – Salesforce Commerce Cloud (as migration target and as source)
Seed for the version-pair refresh. Every line below is a HYPOTHESIS *(verify)* until confirmed for the project's exact compatibility mode, SFRA base version and licensed feature set with a developer.salesforce.com/docs/commerce or help.salesforce.com URL and a date.

### 0. Product split - establish this before anything else
- "Salesforce Commerce Cloud" is two different products: B2C Commerce (formerly Demandware, its own multi-tenant platform, JavaScript/ISML) and B2B Commerce (built on the Salesforce Platform, Lightning, Apex) *(verify)*.
- They are separate products with separate architectures, licences and skill sets; there is no unified solution *(verify)*.
- Almost everything else in this seed describes B2C Commerce. If the client's requirements are B2B-heavy, the honest candidate is B2B Commerce on the Salesforce Platform (or B2B Commerce on Core), and a B2C-Commerce-based estimate would be wrong *(verify which product the engagement is actually about)*.

### 1. Overview
- Enterprise e-commerce platform inside the Salesforce Customer 360 ecosystem *(verify)*.
- Multi-tenant SaaS; no server access, no direct database access *(verify)*.
- B2C Commerce storefront options: SFRA (Storefront Reference Architecture, server-rendered ISML with a JS/SCSS client build), SiteGenesis (legacy, pipeline-based), or headless over the Commerce API *(verify which the project uses)*.
- Development stack: server-side JavaScript with the dw.* Script API, ISML templates, standard client JS/CSS *(verify the script engine's supported language level for the compatibility mode)*.
- Back office is Business Manager *(verify)*.
- Key positioning claims to test: native integration with Sales/Service/Marketing Cloud and CDP, Einstein AI personalisation, Demandware heritage in fashion and retail, MuleSoft for integration, Black-Friday-proven scale *(verify each against the client's real requirements)*.

### 2. Editions/plans & licensing
- Feature availability is licence-dependent: Einstein, Page Designer, Omnichannel Inventory, Salesforce Order Management and headless access must each be confirmed as licensed, not assumed from documentation *(verify each)*.

### 3. B2B capabilities
- B2B Commerce is a SEPARATE product on the Salesforce Platform, in Lightning Experience *(verify)*.
- Account hierarchies for complex B2B organisations *(verify depth - how many levels, and what inherits)*.
- Contract pricing / customer-specific pricing *(verify how it is modelled and how it performs at scale)*.
- Quick order and fast reordering *(verify)*.
- Buyer portals for B2B self-service *(verify)*.
- Native Salesforce CRM connectivity *(verify)*.
- CPQ integration for configure-price-quote workflows *(verify whether Salesforce CPQ is a separate licence)*.
- Order on behalf of / sales-rep assisted selling *(verify)*.
- B2C Commerce itself has NONE of the above: organisation hierarchies, budgets, approval workflows, quotes, punchout and contract pricing are not part of it *(verify)*. Complex B2B is a poor fit, and B2B Commerce is reported as less mature than the Adobe and SAP equivalents *(verify)*.

### 4. B2C capabilities
- SFRA as a modern, customisable storefront reference architecture *(verify the base version and what the release actually ships)*.
- Einstein AI: product recommendations, personalisation, search *(verify licence and which Einstein features are included)*.
- Page Designer: visual content management for business users *(verify which standard components ship in the SFRA base of the release)*.
- Promotions and campaigns engine, described as sophisticated *(verify the promotion types and qualifier model)*.
- Built-in A/B testing and experimentation *(verify)*.
- Dynamic customer segments *(verify)*.
- Order management described as basic, with Salesforce Order Management as the fuller option *(verify - separate product and licence)*.
- Multi-site: several storefronts from one instance, with site-scoped catalogs, price books, slots and preferences *(verify the sharing model)*.
- Search: platform search with searchable attributes, refinements, sorting rules and search suggestions *(verify how relevance is tuned and whether Einstein Search is licensed)*.

### 5. Architecture & extensibility
- API families: SCAPI (the modern Commerce API - Shopper and Admin/Data families) and OCAPI (the legacy Open Commerce API, feature-frozen) *(verify which family each needed operation lives in for the release)*. See knowledge target_api_endpoint_families.
- Authentication for shopper APIs goes through SLAS (Shopper Login and API Access Service) with shopper JWTs; Admin APIs use an Account Manager client with OAuth *(verify the current auth flows)*.
- Headless / Commerce API maturity is a reported weakness and still evolving *(verify per resource - coverage differs sharply between families)*.
- Customisation model: CARTRIDGES on an ordered cartridge path; overrides are positional (same path, earlier cartridge wins), the SFRA middleware pattern uses server.append/prepend/replace with module.superModule, and hooks (cartridge/hooks.json) are additive extension points *(verify the hook list for the release)*.
- Platform objects are extended by CUSTOM ATTRIBUTES declared in metadata, and new entities by custom object types - dw.* classes cannot be subclassed *(verify the custom object quotas)*.
- LINK cartridges provide pre-built payment, tax, shipping and address integrations from partners *(verify maintenance status and LINK version for each one in scope - this is a frequent source of upgrade debt)*.
- Jobs Framework for scheduled imports, exports and bulk processing, with custom step types declared in steptypes.json *(verify runtime and quota bounds)*.
- Services: dw.svc.LocalServiceRegistry with service profiles carrying timeouts, rate limits and circuit breakers *(verify the defaults)*.
- MuleSoft as the preferred enterprise integration layer *(verify - separate licence)*.
- PWA Kit on Managed Runtime is the first-party headless frontend *(verify the current status, hosting model and cost)*.
- Content model: content assets, content slots and Page Designer components - see the pack snippet content_model_notes *(verify standard component names against the app_storefront_base cartridge of the target release, they change between releases)*.

### 6. Limitations & typical gaps
- B2C and B2B are different products; no unified solution *(verify)*.
- Proprietary stack with custom scripting and platform-specific patterns; specialised training required and the developer pool is narrow *(verify local availability)*.
- Headless maturity: the Commerce API is still evolving, so per-resource coverage must be checked rather than assumed *(verify)*.
- SaaS constraints limit customisation in some areas *(verify which, concretely, for the requirements in scope)*.
- Data ownership and portability follow typical SaaS terms *(verify the contract's export provisions)*.
- Value proposition diminishes sharply without the wider Salesforce ecosystem *(verify what the client actually runs)*.
- Quota framework: API call, object-count, collection-size and script quotas are enforced per request and per job, and quota warnings turn into enforced errors over time *(verify the current limits and the instance's quota status)*.
- No direct database access and no arbitrary background processing - only jobs *(verify)*.
- Code-version deployment: code is uploaded into numbered version slots and activated per instance; there is no per-file deploy and rollback means re-activating a previous version *(verify)*.
- Cartridge path collisions: two cartridges providing the same file resolve by position, silently *(verify the actual path per site)*.

### 7. Hosting/operations
- Fully vendor-hosted multi-tenant SaaS; instance topology is sandbox / development / staging / production with data replication *(verify how many sandboxes and how data refresh works)*.
- Deployment via sfcc-ci or the Business Manager code deployment UI, plus WebDAV upload of code versions *(verify the client's actual pipeline)*.
- Data interfaces via IMPEX WebDAV files consumed by jobs, plus SCAPI/OCAPI *(verify the file contracts)*.
- Page cache (<iscache>) and personalised caching are the main performance levers and belong in the architecture *(verify the current cache strategy)*.
- Reliability claim: proven under Black Friday peak traffic *(verify with a reference relevant to the client's volume profile)*.
- Monitoring and log access are limited to what Business Manager and the log WebDAV share expose *(verify what the client can see today)*.

### 8. Ecosystem & partners
- Large SI partner network, including the global integrators *(verify current certified partner availability in the client's region)*.
- LINK marketplace of partner cartridges for payment, tax, shipping, address validation, reviews and more *(verify each cartridge's LINK version, maintenance and SFRA compatibility)*.
- Salesforce ecosystem integrations: Sales Cloud, Service Cloud, Marketing Cloud, CDP, MuleSoft, Tableau, Slack *(verify which the client licenses)*.
- Strong vertical presence in fashion, beauty and consumer goods *(verify)*.
- Developers: SFCC-certified specialists; skills are platform-specific and do not transfer *(verify)*.

### 9. Typical use cases
- Salesforce-first organisations already running Sales, Service or Marketing Cloud that want commerce in the same ecosystem *(verify what is actually licensed and in use)*.
- Fashion and apparel retailers - the platform's heritage and strongest vertical *(verify)*.
- Consumer brands with marketing-heavy, personalisation-heavy requirements *(verify)*.
- B2C retailers wanting a unified commerce and CRM customer view *(verify)*.
- Enterprises that value out-of-the-box AI personalisation *(verify the Einstein licence)*.
- Poor fits to challenge explicitly: non-Salesforce CRM landscapes, complex B2B, organisations wanting an open or composable stack, budget-constrained programmes, teams wanting simple SaaS, and pure headless-first strategies *(verify each against the client's real situation)*.
