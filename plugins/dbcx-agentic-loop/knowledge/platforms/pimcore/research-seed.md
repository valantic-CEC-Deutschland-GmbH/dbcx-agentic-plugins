## Research topics – Pimcore (as migration target and as source platform)
Seed for the version-pair refresh. Every line below is a HYPOTHESIS *(verify)* until confirmed for the project's exact Pimcore version and installed bundle set with a pimcore.com/docs or github.com/pimcore URL and a date.

### 0. Scope statement - read before scoring anything
- Pimcore is PRIMARILY a PIM/MDM, DAM and CMS platform on Symfony. Commerce comes from the OPTIONAL E-Commerce Framework bundle *(verify it is installed at all - `pimcore/ecommerce-framework-bundle` in composer.lock)*.
- The E-Commerce Framework is explicitly a framework for developers, not an out-of-the-box shop *(verify)*. It provides building blocks and contracts; the shop is built on top.
- Consequence for a fit estimation: split every requirement into a data/content part (Pimcore's strength, usually standard) and a shop part (usually project work). Scoring Pimcore as if it were a shop platform is the classic error - it produces both false gaps on the PIM side and false coverage on the commerce side.
- There is NO shipped storefront and NO shipped checkout UI *(verify)*. Frontend and checkout are project scope in every Pimcore commerce case.

### 1. Overview
- Open-source digital experience platform combining PIM, DAM, CMS and a commerce framework in one application *(verify)*.
- Monolithic PHP application built on the Symfony framework, MVC *(verify)*.
- Stack: PHP 8.x, Symfony 6 (verify the current line), MySQL/MariaDB, Elasticsearch *(verify whether Elasticsearch or OpenSearch is supported for the version in scope)*.
- Core object types: Data Objects (any entity, fully flexible schema), Assets (DAM), Documents (CMS pages) *(verify)*.
- Central claim to test: single source of truth for product content feeding multiple channels, marketplaces and print *(verify with the client's actual channel list)*.
- Community Edition described as genuinely powerful rather than crippled open core *(verify which features are Enterprise-only)*.

### 2. Editions/plans & licensing
- Community Edition: free, GPL-3.0 *(verify - check the licence of each bundle separately, some official bundles have their own terms)*.
- Enterprise Edition: commercial licensing *(verify what it adds - support, additional bundles, SLAs)*.
- Pimcore Cloud: managed hosting option *(verify what is managed and which regions)*.
- Bundle-level licensing matters more than edition here: establish for every needed bundle whether it is free, Enterprise-only or third-party *(verify per bundle)*.

### 3. B2B capabilities
- Multi-tenant commerce: separate B2B and B2C tenants in the E-Commerce Framework (index tenant, cart tenant, checkout tenant) *(verify)*.
- Customer-specific pricing through pricing rules and tenant configuration *(verify how far this scales - contract price lists per customer are usually custom)*.
- Complex B2B product information modelling through Data Objects - genuinely strong *(verify)*.
- Tenant-based configuration allows different checkout flows per tenant *(verify)*.
- API-driven custom B2B portals *(verify)*.
- MOST B2B features require custom development *(verify)*. Assume organisation hierarchies, budgets, approval workflows, quotes, order approval, punchout and contract pricing are all project work unless proven otherwise.
- Customer Management Framework bundle covers customer data, segments and activities - not B2B org structures *(verify)*.

### 4. B2C capabilities
- Product catalogue via Data Objects with full schema flexibility *(verify)*.
- Product search and filtering via the Index Service (default MySQL index, optimized MySQL index, or Elasticsearch/OpenSearch) plus the Filter Service *(verify which index types the version supports; relevance tuning is project work)*.
- Cart and checkout: CartManager and a configurable CheckoutManager with checkout steps *(verify - the steps are implemented per project, the UI entirely so)*.
- Pricing: Pricing Manager with rules, conditions and actions, plus price systems and price modifiers *(verify which conditions and actions ship)*.
- Promotions: voucher system with token series and voucher types *(verify)*.
- Order handling: Order Manager, order agent, order status *(verify how much order lifecycle is really covered vs. delegated to an ERP/OMS)*.
- Payment: a PSP connectivity framework plus separate payment provider bundles *(verify which provider bundles exist and are maintained for the version in scope - this is a frequent surprise)*.
- Commerce inside content pages via Documents *(verify)*.

### 5. Architecture & extensibility
- API families: Pimcore Data Hub exposes a GENERATED GraphQL schema per configuration - queries and mutations are named after the Data Object classes, so operation names are project-specific *(verify against the project's Data Hub configuration; no endpoint contract can be written without it)*. See knowledge target_api_endpoint_families.
- Data Hub endpoint shape: POST to a `/pimcore-graphql-webservices/<configuration>` style path with an API key *(verify the exact path and auth for the version)*.
- A Simple REST adapter for Data Hub provides read-only, Elasticsearch-backed REST endpoints (tree items, search, get element) *(verify the bundle name, availability and endpoint paths)*.
- The legacy Webservice REST API was removed in the Pimcore 10 line *(verify the exact release)* - do not assume an old integration still has an API.
- A newer Studio backend REST API accompanies the new admin UI *(verify whether it exists for the version in scope and whether it is public/stable)*.
- Extensibility: Symfony service decoration and aliasing, event subscribers on DataObject/Asset/Document events, Twig template overrides under `templates/bundles/<Bundle>/`, Data Object class definitions with parentClass/traits/interfaces, and the E-Commerce Framework's own configured extension points (price system, availability system, checkout step, order agent, index tenant, filter type) *(verify each for the version)*.
- Content model: Documents with editables, area bricks as reusable components, Data Objects with localized fields, field collections, object bricks and classification store *(verify)*.
- Integration patterns: Data Hub (GraphQL), Data Importer bundle for inbound file/HTTP/SQL feeds, Symfony Messenger for async work, direct ERP connectors as project code *(verify)*.
- Workflow Management: Symfony-Workflow-based, configured in YAML with places, transitions, guards and custom actions *(verify the effort - notifications and custom actions are code)*.
- Pimcore is frequently used as the PIM FEEDING another commerce platform rather than as the shop itself *(verify whether that is the better fit for the client)*.

### 6. Limitations & typical gaps
- Not turnkey: significant development required to build a shop *(verify against the client's timeline and budget)*.
- Commerce depth below dedicated commerce platforms *(verify feature by feature, never as a blanket statement)*.
- B2B features require custom development *(verify)*.
- Checkout needs custom implementation for anything beyond a trivial flow *(verify)*.
- Steep learning curve; needs experienced Symfony/Pimcore developers, and the developer pool is specialised *(verify local availability)*.
- Commerce ecosystem smaller than the alternatives *(verify - count maintained payment/shipping/tax bundles for the version in scope)*.
- Indexing and performance of large object trees is the recurring technical risk: the default MySQL product index does not scale like Elasticsearch, and full reindexes are expensive *(verify object counts and current index type)*.
- Documents and bricks render server-side Twig, so there is no headless render contract for editorial content - a headless frontend re-implements every brick *(verify)*.
- Class definitions may exist only in the database if never exported, making the data model invisible to a code-only analysis *(verify by looking for var/classes/definition_* files)*.
- Admin UI line change (classic ExtJS bundle vs the newer Studio UI) affects every admin extension a project has built *(verify the state for the version in scope)*.

### 7. Hosting/operations
- Self-hosted or Pimcore Cloud *(verify which)*.
- Typical self-hosted topology: php-fpm, MySQL/MariaDB, Redis, Elasticsearch/OpenSearch, Supervisor for Messenger workers, all containerised *(verify)*.
- Assets go through Flysystem adapters; local filesystem assumptions break on object storage, and the on-demand thumbnail pipeline needs a writable shared path or a CDN *(verify)*.
- A maintenance command must run on a short cron interval, and Messenger workers must be supervised - neither is provable from the repository *(verify with operations)*.
- PHP memory_limit, execution time and upload limits are functional constraints for large object trees and asset uploads, not just ops settings *(verify)*.
- Backups must cover the database AND the asset storage AND the exported class definitions *(verify the client's actual backup scope)*.

### 8. Ecosystem & partners
- Specialised Pimcore agencies, mostly Europe-centric *(verify current partner list and local availability)*.
- Bundle ecosystem: official pimcore/* bundles plus third-party bundles of varying maintenance quality - check the last release date and open issues of every bundle the design depends on *(verify per bundle)*.
- Developers: Symfony/PHP with Pimcore experience; Symfony skills transfer, Pimcore specifics do not *(verify)*.
- Frequently paired with a separate commerce platform (Shopware, Adobe Commerce, others) where Pimcore is the PIM/DAM and the shop is elsewhere *(verify whether this split fits the client better than a Pimcore-only build)*.
- Verticals: manufacturing, retail, media, any multi-channel publisher *(verify)*.

### 9. Typical use cases
- PIM-first organisations where product data management is the primary need and commerce is secondary *(verify the primary driver with the client)*.
- Complex product structures with deep attributes, relationships and hierarchies *(verify attribute and relation counts)*.
- Multi-channel publishers feeding product data to several touchpoints, including print *(verify the channel list)*.
- Manufacturers needing PIM plus light commerce: configurators, B2B portals, spare-parts catalogues *(verify)*.
- Organisations already running Pimcore PIM that want to add commerce *(verify the existing installation's version and customisation depth first)*.
- Poor fits to challenge explicitly: turnkey commerce seekers, simple B2C retail, teams without development capacity, complex B2B, fast time-to-market needs, and organisations with no PIM need at all - where Pimcore is simply overkill *(verify each against the client's real situation)*.
