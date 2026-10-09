## Research topics – OXID eShop (as migration target and as source shop)
Seed for the version-pair refresh. Every line below is a HYPOTHESIS *(verify)* until confirmed for the project's exact compilation, edition and module versions with a docs.oxid-esales.com / github.com/OXID-eSales URL and a date.

### 1. Overview
- Open-source PHP e-commerce platform from Germany, more than 20 years on the market *(verify)*, positioned for DACH SMB and mid-market with a B2B option *(verify)*.
- Monolithic PHP application with a module extension system; Composer-based project layout, PSR-4 autoloading in modules *(verify)*.
- Technology stack: PHP 8.x, MySQL/MariaDB, Symfony components, Doctrine DBAL and Doctrine migrations *(verify exact minimum versions per compilation)*.
- Template engine Twig from v7, Smarty before that *(verify the release that made the switch)* - the shipped theme is Apex in v7, Flow in v6 *(verify)*.
- Positioning claims to test against the client's case: lower cost than enterprise SaaS, no GMV-based licensing, full data ownership through self-hosting, stability over innovation pace *(verify all four)*.
- Genuine open source rather than open core: the Community Edition is described as fully functional under GPL-3.0 *(verify which features are actually CE-only vs edition-gated)*.

### 2. Editions/plans & licensing
- Community Edition: free, GPL-3.0 *(verify)*.
- B2B Edition: additional licence on top of Enterprise *(verify - is the B2B Suite really EE-only)*.
- Edition is encoded in the Composer metapackage name (oxideshop-metapackage-ce / -pe / -ee) *(verify)*.
- Multi-shop (several shops from one installation, shared backend) is an Enterprise capability *(verify - the single most common edition misassumption)*.
- Visual CMS is a licensed module rather than core CMS *(verify which editions include it)*.
- Hosting is self-managed or partner-managed; there is no vendor-operated cloud offering *(verify)*.

### 3. B2B capabilities
- B2B Suite in the Enterprise B2B Edition bundles the B2B feature set *(verify the exact module list)*.
- Company accounts with multiple users per business account *(verify user/role model depth)*.
- Budget management: spending limits and controls *(verify granularity - per user, per unit, per period)*.
- Approval workflows for orders *(verify how many approval levels and whether it is configurable)*.
- Quick order by SKU *(verify)*; order templates / saved order lists for repeat purchasing *(verify)*.
- RFQ / request for quote *(verify whether it produces a real quote object or an email)*.
- Customer-specific pricing through individual price agreements *(verify how it relates to price groups and graduated prices)*.
- Punchout via OCI catalog integration *(verify - OCI only, or also cXML)*.
- Complex enterprise B2B is a poor fit *(verify)*; assume anything beyond the list above is custom work.

### 4. B2C capabilities
- Product management: variants, attributes, cross-selling *(verify variant model depth, e.g. size/colour matrices)*.
- Catalog: categories, manufacturer and vendor pages, attribute filtering *(verify)*.
- Built-in search with filters; relevance and faceting at scale need a search module (Elasticsearch/Solr) *(verify which module is certified for the compilation)*.
- Promotions: vouchers, discounts, promotion rules *(verify the rule model - conditions available without custom code)*.
- CMS described as basic *(verify)* - see section 5 for the content model.
- Customer accounts: registration, order history, addresses *(verify self-service scope, e.g. returns)*.
- Multi-shop storefronts from one installation *(verify - Enterprise, see section 2)*.
- German compliance built in: tax, legal texts, price display rules *(verify against current DACH legislation, this ages fast)*.

### 5. Architecture & extensibility
- API families: there is no first-party REST storefront API in the metapackage; the API story is the optional graphql-base + graphql-storefront modules *(verify)*. REST is module- or partner-provided *(verify)*.
- GraphQL coverage must be checked query by query for the module release in scope: catalogue, customer, basket and order are the usual core; checkout, payment method selection, CMS content and B2B entities are the usual gaps *(verify each)*. See knowledge target_api_endpoint_families.
- Module extension mechanism: metadata.php with extend (class chain via <Class>_parent), controllers, templates, blocks, settings, events *(verify metadata version 2.0 vs 2.1 key support)*.
- Modern alternative: module services.yaml decorating shop services through Symfony DI *(verify from which release this is the recommended way)*.
- Unified/virtual namespace OxidEsales\Eshop\... is what modules extend, not the concrete vendor class *(verify)*.
- Module configuration lives in var/configuration/shops/<shopId>.yaml from 6.2 onwards; before that in database rows *(verify the release)*.
- Theme system: Twig themes with named block regions that modules override *(verify)*.
- Integration patterns: ERP connectors for SAP Business One, Microsoft Dynamics and German ERP systems, usually via middleware or a partner module *(verify which connectors are certified today)*.
- Payment: PayPal, Klarna, German PSPs such as Unzer, Mollie *(verify current module availability and maintenance status)*.
- Shipping: DHL, UPS and other carrier modules *(verify)*.
- OXID Exchange marketplace supplies modules and themes *(verify compatibility per compilation before assuming a module exists)*.

### 6. Limitations & typical gaps
- Ecosystem and market presence are limited to DACH; brand recognition and developer pool outside DACH are small *(verify)*.
- Less API-first than newer platforms; native headless capability is limited to the GraphQL modules *(verify)*.
- Ecosystem size smaller than Magento/Adobe Commerce or Shopify globally *(verify)*.
- Innovation pace slower than SaaS platforms - stability is the trade-off *(verify against the recent release cadence in the GitHub CHANGELOG)*.
- May struggle at very large scale / very high volume deployments *(verify with a scale reference before ruling it in or out)*.
- Module chain conflicts: several modules extending the same class and method, one of them not calling parent, produce silent behaviour loss *(verify per module set)*.
- Upgrade friction on heavily extended shops: a compilation upgrade re-tests every chain override, and 6.x -> 7.x additionally rewrites Smarty template overrides to Twig *(verify effort with the real override count)*.
- Requires an in-house or partner PHP team; not suitable for organisations without development resources *(verify)*.

### 7. Hosting/operations
- Self-hosted (CE/PE/EE) or managed hosting from OXID partners *(verify which model the client is on)*.
- No vendor cloud: PHP version, cron entries, cache backend, object storage, CDN and TLS are hoster facts, not repository facts *(verify each with the hoster)*.
- Writable paths required: source/out (media and generated images), var/ (configuration, cache), tmp/ *(verify)*; a multi-node or container setup needs shared or object storage plus a shared cache backend *(verify)*.
- File-based template and module-configuration caches must be cleared explicitly after configuration changes *(verify the command for the release, e.g. oe-console oe:cache:clear)*.
- Generated database views (oxv_*) must be regenerated after schema or language changes *(verify)*.
- Scheduled work runs from the system crontab, which is outside the repository *(verify the actual cron entries)*.
- Data sovereignty argument: German/EU hosting, full control over data and infrastructure *(verify against the client's compliance requirements)*.

### 8. Ecosystem & partners
- Strong partner network in Germany, Austria and Switzerland; few specialists elsewhere *(verify current partner list)*.
- OXID Exchange marketplace for modules and themes *(verify module maintenance status and compilation compatibility individually - an unmaintained module is a project risk, not a feature)*.
- Developers: PHP developers with OXID certification; certification programme exists for modules as well *(verify)*.
- ERP fit: SAP Business One, Microsoft Dynamics, German mid-market ERP systems *(verify)*.
- Payment fit: German PSPs (Unzer), Mollie, international options *(verify)*.
- Hosting fit: German hosting providers and on-premise *(verify)*.

### 9. Typical use cases
- DACH SMB and mid-market retail where cost and data ownership outweigh feature breadth *(verify)*.
- On-premise deployments driven by data sovereignty requirements *(verify)*.
- DACH B2B distributors with a straightforward B2B requirement set covered by the B2B Edition *(verify against the actual requirement list, not the brochure)*.
- Budget-conscious organisations that cannot fund enterprise SaaS licensing *(verify the budget envelope)*.
- Organisations with an existing OXID investment deciding between upgrade and replatform *(verify the override count first - it drives the whole decision)*.
- Poor fits to challenge explicitly: global enterprises, headless-first strategies, teams without PHP capacity, complex enterprise B2B, very large scale *(verify each against the client's real numbers)*.
