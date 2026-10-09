## Research topics – SAP Customer Loyalty Management

Seed for the platform refresh. Lines marked **[cache §n]** were verified on 2026-10-05 (reference-cache.md, section n) and only need a currency check; every line marked *(verify)* is a HYPOTHESIS or an open gap until it is confirmed for the engagement with a help.sap.com page read through the content service, an api.sap.com specification, or a written SAP statement - URL and date. The product went GA in Q4 2025 and ships continuously (help.sap.com version SHIP): documentation is thin in places, and an absent page means "not documented", not "not possible". Start every refresh with the What's New Viewer (deliverable 4c5c6ecfbd5149ebb7cbda7a30fca030) and the api.sap.com package sap-clm-SAPCustomerLoyaltyManagement.

**Three facts to establish before any B2B estimate:** (1) whether a B2B wallet type is selectable in the engagement's subscription - documented today is "Consumers" only **[cache §3]**; (2) the operation-level API specification for earning from an order and for reversing it (Checkout Connect / Data Products, 1.0.0-beta) *(verify)*; (3) whether SAP provides any standard financial posting from the CLM ledger into SAP S/4HANA *(verify)*.

### 1. Product, deployment, editions
- Name SAP Customer Loyalty Management; public-cloud SaaS on SAP BTP, customer BTP sub-account subscription, SAP Cloud Identity Services, provisioning in SAP for Me **[cache §1]**
- Announced NRF January 2025, availability Q4 2025, What's New items GA through 2026 **[cache §1]**
- No on-premise or private-cloud edition and no edition tiers are documented *(verify with SAP sales: editions, add-ons, price metric - consumption is metered and loyalty transactions carry a Billable flag, the metric itself is not public)*
- Two workspaces per subscription; further workspaces are an extra order *(verify the commercial terms)* **[cache §2]**
- Data centres North America, Europe, Asia-Pacific per workspace **[cache §2]**; underlying hyperscaler and exact region (e.g. EU country) *(verify - export download URLs point to blob storage, which hints at but does not prove the provider)*
- Line of business Commerce, parent product SAP Customer Experience on api.sap.com; support component CEC-CLM **[cache §1]**

### 2. Members and B2B fit
- One wallet per person per workspace; base identity schema is personal (email, first name, birth date) and not modifiable; extended attributes and custom wallet keys **[cache §3]**
- Workspace wallet type: only "Consumers" selectable; the tile shows "B2C or B2B" **[cache §3]** - is a B2B wallet type planned, in early adoption, or available on request? *(verify on SAP Road Map Explorer / with SAP product management; record who said what and when)*
- Company-level membership, organisation hierarchy, several buyers of one company earning into one account, purchaser vs beneficiary (company vs individual buyer) *(verify - not documented; today only group wallets pooling persons exist, one group per member)* **[cache §3]**
- Wallet extended attributes or custom keys as a carrier for a company/account number (e.g. ERP sold-to) and aggregation outside CLM *(verify feasibility and limits - extended attributes exist, aggregation logic does not)*
- Indirect channel: earning on purchases made through wholesalers/distributors - sell-through feeds, purchase claims, receipt or invoice upload and validation *(verify - no receipt/claim handling is documented; Partner Brands are documented as coalition partners such as airlines, not as a sales channel)* **[cache §4]**

### 3. Earn and burn rules
- Base earn per currency unit of the member brand, rounding incl. fractions, promotions, journeys, goodwill, transfers **[cache §4, §5]**
- How exactly an order becomes points: Checkout Connect basket submission ("post-sales loyalty processing") vs Data Products "processing transactions" - payload, line-level product eligibility, net/gross amounts, currency, B2B net prices *(verify in the api.sap.com spec)*
- Product- or category-specific earn multipliers outside promotions *(verify - promotions have merchandise sets; a permanent category multiplier is not documented)*
- Earning on invoices or deliveries from the ERP instead of the webshop basket *(verify - no ERP transactional integration is documented)*
- Idempotency: the requestor action reference and order id on loyalty transactions **[cache §6]** - does the API reject duplicates with the same reference? *(verify)*

### 4. Pending points, returns, expiry, fraud
- "Postponed" spending = pending balance for N days, main program only **[cache §4]**; can pending points be released or cancelled by an event (delivery, end of return window) instead of a fixed day count? *(verify)*
- Returns, cancellations, partial returns, credit notes: no reversal transaction type documented (types Earned, Created, Goodwill, Credited, Debited, Expired, Exchanged, Redeemed) **[cache §6]** - which API reverses earned points with reference to the original order, and what happens when the points were already spent (negative balance option exists for one transaction) *(verify)*
- Expiry monthly after N months or never **[cache §4]**; expiry at a fixed date (e.g. end of year) or per tier *(verify)*
- Fraud and duplicates: earning/spending/gifting/goodwill limits, postponed spending, key statuses (suspended, stolen, lost), suspended wallets block transfers **[cache §3, §4]**; automatic duplicate-wallet detection or merge *(verify - not documented)*; anomaly detection is described only as a Business Data Cloud / AI use of exported data *(verify)*

### 5. Tiers, rewards, promotions, partners
- Tiers: thresholds plus periodic evaluation by staff, status points from journeys **[cache §4]**; automatic qualification, requalification periods, downgrade rules, tier validity *(verify - the multi-tier page is thin)*
- Rewards bank per region, rewards as discount codes, tier-specific point prices **[cache §4]**; physical premiums, partner vouchers, fulfilment and stock *(verify - not documented)*
- Promotions with approval, budget, funding, targeting by individual, segment or tier; personal discount code formats **[cache §5]**; promotion types available in the wizard and stacking rules *(verify)*
- Partner programs: partner brand units with business partner id, booking and redemption rates, partner interactions in journeys **[cache §4, §5]**; partner self-service access *(verify)*

### 6. APIs, events, limits
- Four REST APIs on api.sap.com, all 1.0.0-beta, OAuth client credentials via SAP Cloud Identity Services app-to-app **[cache §7]**; operation list, paths and payloads *(verify - specifications need an SAP login)*; GA date of the APIs and the deprecation policy for beta changes *(verify)*
- Events/webhooks for balance changes, tier changes, expiry warnings *(verify - none documented; the Business Accelerator Hub lists REST APIs only)*
- API rate limits, payload limits, bulk endpoints for initial load and migration of existing balances *(verify - not published)*
- Transaction exports via /admin/dataproducts/v1/... daily or manual **[cache §6]**

### 7. Standard integrations
- SAP S/4HANA Cloud Private Edition: master data into CLM only (products, prices, plants, product groups) via DRF; financial posting/accruals from the ledger into S/4HANA *(verify - the ledger is "passed to SAP S/4HANA" per the Admin Guide, but no configuration is documented; whether S/4HANA Cloud Public Edition or on-premise S/4HANA are supported is also undocumented)* **[cache §6, §7]**
- SAP Service Cloud Version 2: wallet mashup **[cache §7]**
- SAP Commerce Cloud incl. composable storefront: no CLM integration documented in Commerce, Integration Extension Pack or composable storefront docs, and no loyalty library in the licensed composable storefront 221121.18.0 **[cache §7]** - SAP's January 2025 announcement named Commerce Cloud as an intended integration **[cache §1]**; status today *(verify)*
- SAP Customer Data Cloud for identity: not documented; CLM keeps wallet personal data in its own internal SAP CIAM technology **[cache §7]** - mapping of a CDC UID to a wallet key *(verify)*
- SAP Customer Data Platform (segments into CLM; CLM transactions into CDP) *(verify - CLM ingests segments "from a data platform", no CDP connector is documented)*
- SAP Emarsys for loyalty communication: not documented for CLM (CLM sends no communication itself) *(verify)* - note that SAP Emarsys Loyalty is a different product and out of this pack's scope
- SAP Integration Suite: no prebuilt iFlow package for CLM on the Business Accelerator Hub **[cache §7]**; use as custom integration layer *(verify whether SAP plans content)*
- SAP Business Data Cloud: transaction data share for analytics **[cache §6]** - setup and data product names *(verify)*

### 8. Environments and operations
- Two workspaces, Staging -> Live one-way, no configuration promotion, wallets not copied **[cache §2]**; any export/import or API-based recreation of promotions, journeys and rewards *(verify)*
- Personal data: CLM deletes nothing by itself, wallet DELETE endpoint, anonymisation via update, audit log in BTP Audit Log Service **[cache §7]**
- SLA, maintenance windows, release cadence *(verify in the service description / Cloud Availability Center)*
