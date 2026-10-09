## Research topics – Sylius (source and target)
Seed for the version-pair refresh. Every line is a hypothesis *(verify)* until confirmed against a docs.sylius.com / github.com/Sylius URL for the project's exact Sylius minor AND Symfony major. Prices, plugin compatibility and the Plus feature boundary age fastest.

### 1. Overview
- Open-source e-commerce FRAMEWORK on Symfony - framing: it is a foundation for building a tailored shop, not a ready product *(verify)*
- Stack: PHP 8.x, Symfony 6/7, Doctrine ORM, MySQL or PostgreSQL *(verify supported versions per Sylius minor)*
- API-first through API Platform: a REST/JSON-LD API is generated from the resources rather than bolted on *(verify which operations exist per version)*
- Design claim: one of the best-architected Symfony applications, SOLID, with 100% BDD test coverage *(verify - the coverage claim is vendor-stated)*
- MIT license for Sylius Standard; the commercial parts are separate packages *(verify the license of sylius/plus and each plugin separately)*
- Frontend options: Twig storefront, headless via the API, or SyliusFrontwing (React-based) *(verify current status and maintenance of any React starter)*

### 2. Editions/plans & licensing
- Sylius Standard: free, open source, MIT *(verify)*
- Sylius Plus: commercial licence *(verify - and verify what Plus actually contains in the current version, since the boundary has moved)*
- B2B Suite / B2B Kit: an additional commercial plugin on top *(verify whether it is part of Plus or priced separately)*
- Enterprise support packages optional *(verify SLA)*

### 3. B2B capabilities
- Not in core. B2B comes from Sylius Plus and/or the B2B Suite (B2B Kit plugin) *(verify)*
- Organisations / business account management, multi-organisation structures for complex hierarchies *(verify depth: how many levels, per-user roles)*
- Customer-specific pricing lists *(verify how it interacts with channel pricing and catalog promotions)*
- Quick shopping / fast reorder, admin-side order creation (back-office ordering), specialised B2B checkout flows *(verify)*
- Not named and therefore to be treated as absent until proven: punchout (OCI/cXML), multi-level approval chains, budgets per cost center, quote negotiation rounds, contract management *(verify)*
- Practical rule for scoring: on Sylius, "achievable with development" is not the same as covered - name the plugin, the Plus feature or the effort *(verify per requirement)*

### 4. B2C capabilities
- Products: simple, configurable (options/variants) and bundles; Taxons as the category tree; product attributes and translations *(verify bundle support - core vs. plugin)*
- Cart and checkout: a state-machine-driven, fully customisable checkout *(verify the default graph: cart -> addressed -> shipping selected -> payment selected -> completed)*
- Promotions: catalog promotions (price-level) and cart promotions (order-level) with rules and actions *(verify)*
- Customer accounts with registration and order history; multi-channel (multiple stores/channels natively) *(verify what a channel isolates: catalog, currency, locale, theme, payment/shipping)*
- Payments through the Payum abstraction (PayPal, Stripe, Mollie, custom gateways); flexible shipping calculators *(verify current gateway plugins and their maintenance state)*
- Search: Elasticsearch or Algolia via plugins, not in core *(verify)*
- Content: nothing - see section 6 *(verify)*

### 5. Architecture & extensibility
- Symfony bundle architecture: project code in src/, Sylius in vendor/sylius, activation through config/bundles.php *(verify)*
- The customization model is documented and sanctioned: override a resource's model, controller, factory, repository or form through `sylius_<bundle>: resources:` configuration; add behaviour with event subscribers; wrap services with DI decoration *(verify the exact configuration keys for the target minor)*
- Twig Hooks (2.x) replace template-override-everything as the storefront extension mechanism *(verify availability in the project's version and which hooks exist)*
- API: API Platform resources under /api/v2/shop (customer context) and /api/v2/admin (back office), JWT authentication; GraphQL is possible through API Platform but not a supported default *(verify)*
- Order lifecycle in state machines (winzou state machine, or the Symfony Workflow component on newer versions) with callbacks as the extension point *(verify which implementation the target version uses)*
- Admin UI built from sylius_grid definitions plus menu subscribers *(verify - the 2.x admin was reworked)*
- Integration: any Symfony bundle, HTTP clients for ERP/PIM/CRM, Symfony Messenger for async work; there are no pre-built ERP connectors from the vendor - integration is custom *(verify)*

### 6. Limitations & typical gaps
- SYLIUS CORE SHIPS NO CMS. There is no page, block or content entity and no page builder; content is a plugin (BitBag CMS is the common choice), a headless CMS, or custom entities. This must be decided before the frontend architecture *(verify what the project's version and plugin set actually provide)*
- Not turnkey: development is required to launch - the first weakness *(verify)*
- Learning curve: Symfony expertise is a hard prerequisite *(verify team availability)*
- Fewer out-of-the-box features than all-in-one platforms; expectations set by Shopware/Magento will not be met without development *(verify per requirement)*
- B2B depth requires Plus or plugins; several enterprise features sit behind Plus *(verify the current boundary)*
- Ecosystem is small: plugin maintenance state and Sylius-version compatibility are real project risks *(verify per plugin, per version, with the last-commit date)*
- Admin depth for merchandising, marketing and reporting is thin compared with all-in-one platforms *(verify)*
- Hosting is self-managed; there is no vendor SaaS to fall back to *(verify)*
- Market presence smaller than Magento/Shopify - reference checks matter *(verify)*

### 7. Hosting/operations
- Any PHP hosting; Symfony-optimised PaaS (Platform.sh and similar) is the usual recommendation *(verify current support)*
- Operational scope owned by the project: database, cron (sylius:cancel-unpaid-orders plus project jobs), Messenger workers as long-running processes, asset builds at deploy time, search cluster if added *(verify)*
- Container-readiness caveats: media on the local filesystem by default (needs a Flysystem adapter for object storage), file-based cache/session/locks do not survive multiple instances *(verify what the project uses)*
- Upgrades: a Sylius upgrade is usually also a Symfony upgrade - read UPGRADE-*.md for both *(verify)*
- No vendor-operated environment means no vendor-provided SLA on availability *(verify what an enterprise support package covers)*

### 8. Ecosystem & partners
- Plugin sources: official Sylius plugins, community plugins, Sylius Plus as a commercial bundle, BitBag as the best-known third-party plugin vendor *(verify current catalogue and maintenance state)*
- Partner model: digital agencies building bespoke shops; strongest in Europe *(verify partner availability in the project's region)*
- Staffing: Symfony developers are broadly available, which is a genuine advantage over Spryker or SAP Commerce - Sylius-specific experience is rarer *(verify)*
- The Symfony ecosystem itself is the largest part of the value: any Symfony bundle is usable *(verify)*

### 9. Typical use cases
- Best fit: custom e-commerce projects needing full control, Symfony teams, digital agencies delivering bespoke client shops, startups needing an extensible foundation, B2B buyer portals with development budget, organisations that value code quality *(verify)*
- Moderate fit: PHP teams willing to learn Symfony, moderate customisation needs, organisations evaluating headless commerce *(verify)*
- Poor fit: buyers who want turnkey commerce, organisations without development resources, complex enterprise B2B out of the box, budget- or time-constrained launches, non-technical teams wanting business-user control, massive enterprise scale without architecture investment *(verify)*
- Scoring guidance keys on development philosophy, Symfony expertise, customisation need, development budget, B2B requirements, timeline, code-quality priority, API strategy and scale *(verify - fit questionnaire, not a verdict)*
