## Research topics – SAP Commerce → SAP Commerce Cloud + composable storefront
Seed for the version-pair refresh (`dbcx render brief research`). Every line is a hypothesis *(verify)* until confirmed with a help.sap.com URL for the project's exact source and target versions.

### 1. Composable storefront feature libraries (check the target 2211.x release)
- B2B commerce org (units, users, cost centers, budgets, approvals, unit-level order history, account summary) – `@spartacus/organization`, OCC `commerceorgocc`, `b2bocc` *(verify)*
- Quotes – `@spartacus/quote` *(verify version)*; saved carts, quick order, import/export cart, reorder – `@spartacus/cart`
- Order approval, requested delivery date, scheduled replenishment – `@spartacus/order`, `@spartacus/organization/order-approval` *(verify)*
- Order history/details, consignment tracking, cancellations, returns; S/4 order management OCC (`saps4omocc`) *(verify)*
- Customer ticketing – `@spartacus/customer-ticketing` *(verify)*; product configurator (VC/CPQ, textfield) – `@spartacus/product-configurator`
- Variants, bundles/guided selling *(verify: limited)*; store finder / pickup in store; ASM – `@spartacus/asm`
- Punchout (cXML) – OCC `b2bpunchoutocc`, composable support *(verify version)*
- Login/CIAM: OAuth2 against `authorizationserver`; CDC login; external OIDC IdP needs custom OAuth2 integration *(verify: no standard connector for a specific external IdP)*
- Digital payments – `sapdigitalpaymentocc` / `@spartacus/digital-payments` *(verify)*; estimated/requested delivery date, future stock *(verify)*
- Segmentation/personalisation – `@spartacus/tracking`, CDS; EPD visualization; SmartEdit for composable; i18n/multi-site; accessibility program *(verify)*

### 2. OCC v2 endpoint families (see knowledge target_api_endpoint_families) and typical gaps
- customer-specific live pricing/availability (custom OCC or S/4 pricing integration `sapcentralpricing` / `saps4om` *(verify)*), installed base, customer material numbers, document downloads (`sapinvoiceocc` *(verify)*)

### 3. Deprecations / removals (verify against release notes of the target version)
- Accelerator JSP storefronts and the AddOn mechanism: deprecated since 2205, functional freeze (new commerce functionality via REST APIs only). **No fixed de-release date for the Accelerator UI template extensions since June 2026** and the Accelerator back-end functionality modules are NOT deprecated; the OCC AddOns keep hard removal dates (IEP/industry/template AddOns Q3 2026, core OCC AddOns September 2027) *(verified 2026-09-17, see reference-cache.md - re-verify the dates, not the framing)*
- Legacy cockpits removed 2205; hMC removed 1905; Data Hub is NOT deprecated or removed at 2211 (full documentation set ships for 2211, no deprecation row, listed API on the Business Accelerator Hub) - **refuted seed row, do not assert a Data Hub removal** *(refuted 2026-09-04 and 2026-09-17, see reference-cache.md)*; `ycommercewebservices` replaced by `commercewebservices` (2005)
- `sapcorejco` is NOT deprecated at IEP 2211 (documented, no deprecation row; JCo RFC is a supported Public Cloud mechanism, secured by VPN / Private Link). Only the **Synchronous Order Management module** (`sapordermgmt*`, `sapcommonbol`) is deprecated (2211, planned deletion Q3 2025) - **refuted seed row, never generalise it to JCo as a technology** *(refuted 2026-09-04 and 2026-09-17, see reference-cache.md)*; Jalo layer / `JaloSession` attribute usage
- JDK 11 → 17 (2211) *(verify)*; Spring Security `WebSecurityConfigurerAdapter` deprecation *(verify)*; Solr 8 → 9 *(verify)*

### 4. Standard data model anchors
`B2BUnit`, `B2BCustomer`, `B2BCostCenter`, `B2BBudget`, `B2BPermission`, `OrgUnit` hierarchy, `Quote`/`QuoteEntry`, `Cart/OrderEntry` (`entryGroups`, `configurationInfos`), `Product` + `ProductReference` types (ACCESSORIES, BASE_SPAREPART, CONSISTS_OF, FOLLOWUP, SPAREPART, SIMILAR, UPSELLING, CROSSELLING, ...), `Unit`, `PriceRow`/`DiscountRow`, `StockLevel`/`FutureStock`, `Warehouse`, `PointOfService`, `SAPConfiguration`, `SAPCpiOutbound*`, `Consignment`, `CsTicket`, `SavedCart`, `ProductInterest`; **no standard installed-base/equipment type** *(verify)*

### 5. On-premise → CCv2 (see pack snippet hosting_constraints) and composable prerequisites
- `cmsocc`, `commercewebservices` + all OCC extensions for used features, `smarteditwebservices`/`cmssmartedit`, OAuth2 clients, CORS config; `spartacussampledata` only for demos *(verify list for target version)*

### 6. Known traps (re-verify per version pair)
- `secureportaladdon`: extension deprecated and deleted (registration → `b2bcommerce`/`b2bcommercefacades`, storefront layer → `b2bacceleratoraddon`), while `CMSSecurePortalRestriction` the TYPE still ships (first defined at `b2bacceleratorservices`) *(verify for the target release)*
- `sapordermgmt*` (Synchronous Order Management): deprecated 2211, removed from the installer at 2211-jdk21.1; mitigation module-level only (`saps4om*`); `SAPConfiguration.sapordermgmt_*` attributes owned by `sapordermgmtbol` disappear with it → ImpEx headers writing them fail at import *(verify)*
- `sapinvoice*` (legacy SAP Invoice, JCo, deprecated Q4 2024, no OCC) vs `sapbillinginvoiceocc` (current Billing Invoice Integration) vs `@spartacus/pdf-invoices` (S/4HANA OM) *(verify)*
- OCC has no bulk add-to-cart endpoint: Quick Order and Cart Import/Export are client-side loops over the single-entry endpoint *(verify)*; no standard cart-suggestion CMS component in Spartacus *(verify)*
- Password encoders md5/sha/plaintext and `legacy.password.encoding.enabled` deleted at 2211-jdk21.5, Argon2 default *(verify; a scanner hit on `$passwordEncoding=md5` in a macro definition is only a definition)*

> Sections 7-11 carry commercial and fit content that the version-pair seed above does not. Everything below is UNVERIFIED and marked *(verify)*.

### 7. Editions and deployment options
- Two deployment editions are in scope for any assessment: SAP Commerce Cloud (vendor-managed, CCv2 on Azure) and on-premise SAP Commerce - the on-premise line still exists in the installed base and drives most migration projects *(verify current availability and maintenance end dates of the on-premise line)*
- Frontend options are license-neutral but support-relevant: composable storefront (Angular), accelerator templates, or a custom headless frontend on OCC *(verify the support status of the accelerator templates - the seed above already records them as deprecated with a functional freeze)*
- Integration Extension Pack and the SAP CX side products (Customer Data Cloud, Marketing Cloud, Service Cloud, Analytics Cloud, BTP) are separate licenses, not part of SAP Commerce *(verify per product)*

### 8. Ideal customer profile, fit and scoring guidance
- Strong fit: large SAP S/4HANA or ECC customers modernising commerce; global B2B manufacturers with complex pricing, contracts and approval workflows; automotive and industrial companies with configurator/CPQ needs; organisations requiring punchout (OCI, cXML); enterprises standardised on SAP; companies needing global deployment with SAP-level support *(verify against the client's actual landscape)*
- Moderate fit: large enterprises evaluating SAP ecosystem adoption, complex B2B where SAP ERP integration is planned rather than in place, organisations with an existing SAP Commerce investment seeking modernisation *(verify)*
- Poor fit: non-SAP ERP environments (the integration benefit disappears), mid-market and SMB (cost and complexity), fast time-to-market requirements (typically 9-18+ months), B2C-first businesses, organisations without Java expertise, agile/startup cultures *(verify)*
- Fit questionnaire: SAP ecosystem presence (S/4HANA or ECC customer vs. non-SAP with no plans), B2B complexity (punchout/CPQ/complex approvals vs. simple B2B or pure B2C), timeline tolerance (12-24 months / 6-12 / under 6), organisation size (large enterprise EUR 500M+ revenue / upper mid-market / mid-market), development resources (Java and SAP Commerce expertise available / hireable / none), industry (manufacturing, automotive, industrial / B2B distribution / consumer and DTC), global operations (multi-region and multi-subsidiary / regional / single market), compliance weight (heavy / moderate / standard) *(verify - these bands are not a measured benchmark; treat them as questions, never as a verdict)*
- Read the ERP question as the decisive one: the platform's central argument is the depth of the SAP integration, so a non-SAP ERP removes the main reason to choose it *(verify against the client's ERP roadmap, not its current state)*

### 9. Ecosystem, partners & adjacent SAP products
- SAP ecosystem integration is the stated USP: S/4HANA (real-time ERP integration), SAP ECC (classic connectivity), Customer Data Cloud (identity and consent), Marketing Cloud, Service Cloud, Analytics Cloud and BTP as the extension and integration platform *(verify which integrations are covered by the Integration Extension Pack and which need CPI content or custom work)*
- Integration patterns: OCC REST for commerce operations, the Integration Extension Pack for pre-built SAP integrations, IDoc/BAPI for traditional SAP patterns, Data Hub for master-data ETL, CPI (SAP Cloud Platform Integration / Integration Suite) connectors, plus third-party payment, shipping and tax provider connectors *(the list predates 2211 but still holds: Data Hub and JCo are current at 2211 - only Synchronous Order Management is deprecated; see section 3)*
- PIM: SAP Commerce PCM (Product Content Management) in the platform, or a third-party PIM *(verify PCM's current scope versus a dedicated PIM)*
- Delivery model: SAP Solution Partners; global systems integrators are typical *(verify partner availability and rate expectation for the project's region and size)*
- Staffing: Java developers with SAP Commerce experience - a small, expensive and specialised pool *(verify local availability before committing to a timeline)*
- Worldwide SAP partner network and global support are the ecosystem advantage over Shopware, Spryker, Sylius and VTEX for multi-region programmes *(verify support tiers by region)*

### 10. Documented weaknesses
- Complexity and a steep learning curve; specialised skills required - mitigation named: invest in training, hire certified developers *(verify)*
- Implementation time: long cycles of 9-18+ months - mitigation: accelerators and realistic timelines *(verify against the project plan)*
- Flexibility: customisation can be challenging - mitigation: follow SAP best practices *(verify; the pack's own best_practice snippet is the concrete version of this)*
- Technical debt: legacy architecture in some areas - mitigation: composable storefront for the frontend *(verify which areas; the seed above names the Jalo layer, accelerator/AddOn mechanism and JCo integration concretely)*
- Resource requirements: heavy infrastructure needs - mitigation: use the managed SAP Commerce Cloud *(verify against the CCv2 constraints already recorded in the pack's hosting_constraints snippet)*
- Upgrade effort: major upgrades require significant investment - mitigation: budget for upgrades and minimise customisations *(verify)*
- Java talent scarcity: requires specialised SAP Commerce developers - mitigation: partner with SAP Solution Partners *(verify)*
- Worth stating in any comparison: the platform's value is conditional on the SAP landscape, so its weaknesses weigh far heavier for a non-SAP client than for an S/4HANA customer *(verify per client)*
