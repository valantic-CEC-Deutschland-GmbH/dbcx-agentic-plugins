# E-Commerce Requirement Catalogue (B2B/B2C)

**This whole file is a reference SEED.** It is a checklist used to elicit, challenge and complete the
requirements of one engagement. It is not a requirement list and must never be copied into a client
document as "the requirements". Every entry has to be confirmed as in or out of scope, scoped to the
client's actual processes, and rewritten into a testable requirement with the client's own vocabulary
and numbers before it means anything. The ids are stable, so an engagement can cite them
(for example "covers CAT-CUST-070, CAT-CUST-080") without repeating the text.

Use it in three ways: as a completeness check against extracted requirements, as an interview guide
for workshops, and as a challenge list when a requirement looks too small to be true.

## How to read the columns

- **id** - stable identifier `CAT-<AREA>-NNN`. Numbering runs per area from 010 in steps of 10, so new
  entries can be inserted without renumbering. Ids are never reused or renumbered.
- **capability** - the capability in solution-neutral, testable language, one capability per row. It is a
  starting formulation, not final requirement text: it still needs the client's scope, volumes and
  acceptance criteria. No platform or product names appear here by design.
- **typical FR/TR/NFR** - the classification this capability *usually* gets:
  - **FR** (functional) - observable behaviour a business user or customer can exercise and accept.
  - **TR** (technical) - a requirement on interfaces, data flows, ownership, data models or infrastructure
    that has no directly observable storefront behaviour but constrains the solution.
  - **NFR** (non-functional) - a quality requirement (performance, availability, security, data protection,
    accessibility, SEO, observability, maintainability) that applies across functions and needs a target value.
  - Combinations such as `FR + TR` mean the capability normally produces both a behavioural and an
    interface/data requirement, and should be split into two rows in the engagement's own list.
  The classification is *typical*, not binding - reclassify when the engagement's framing differs.
- **B2B/B2C/both** - **applicability, not priority**. It says in which model the capability usually appears
  at all. A "both" entry can still be irrelevant for a given client, and a "B2B" entry can matter in a B2C
  shop that sells to resellers. Priority, scope and phase are decided per engagement, never taken from here.
- **notes** - the discriminating question, the classic trap, or the fact that decides effort. This column is
  the reason the catalogue exists; read it before writing the requirement.

## CAT-CAT - Catalog & PIM

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-CAT-010 | Products are modelled with attribute sets per product type, and mandatory attributes are enforced before a product can be published | FR + TR | both | Count product types and attributes per type early - one type with 40 attributes and twelve types with 200 attributes are different projects; ask who authors attributes and whether the set changes seasonally. |
| CAT-CAT-020 | Variant products are grouped into a family and selectable by variant axes on one product page | FR | both | Ask how many axes and whether axes differ per category - two axes is standard; three or more, plus per-variant media and per-variant price, usually means custom UI. |
| CAT-CAT-030 | Fixed bundles and configurable sets can be sold as one orderable item | FR | both | Decide bundle pricing before design - bundle-level price, sum of components, or discount on components are three different mechanisms and they change order lines, returns and ERP posting. |
| CAT-CAT-040 | Rule-driven product configuration produces a unique orderable item with its configuration recorded on the order | FR + TR | both | Distinguish a simple option picker from a constraint-solving configurator; the latter is almost always an external engine and drives the cart line data model and the ERP interface. |
| CAT-CAT-050 | Products can be sold in defined units of measure and packaging units with conversion between them | FR | B2B | B2B killer detail - ask for the smallest sellable unit, the rounding rule, and whether the price refers to the base unit or the packaging unit; a wrong rounding rule appears as cent differences against the ERP invoice. |
| CAT-CAT-060 | Product media (images, video, 360 views, downloadable documents) can be maintained per variant and per locale | FR | both | Ask for asset count and origin - a DAM as source of truth changes the integration and the CDN design, and per-locale packaging shots are regularly forgotten until launch. |
| CAT-CAT-070 | Products are assigned to one or more category trees that drive navigation and listing | FR | both | Ask whether one tree is meant to serve navigation, ERP hierarchy and classification at once - separating the navigation tree from the classification tree usually prevents a later rebuild. |
| CAT-CAT-080 | Products carry standard classification data (for example ETIM, eCl@ss, UNSPSC, GS1) and it is exposed where required | TR | B2B | Mandatory in industrial B2B and almost never raised in workshops; ask whether the client must publish or consume a standard, and in which version. |
| CAT-CAT-090 | Product data passes an editorial state model (draft, in review, approved, published) with role-based transitions | FR | both | Clarify whether the workflow lives in the PIM or in the shop - two workflow engines acting on the same data is the trap, not the workflow itself. |
| CAT-CAT-100 | Product visibility can be controlled per channel, market and catalog independently of the product data | FR + TR | both | Ask for the channel matrix (country, brand, B2B/B2C, sales organisation); it decides whether one catalog with visibility rules or several catalogs are needed. |
| CAT-CAT-110 | Customer-specific assortments restrict which products a customer may see and buy | FR + TR | B2B | Ask whether the restriction is contractual (purchase denied) or presentational (hidden) - a deny must be enforced in the cart and the order API too, not only in listings and search. |
| CAT-CAT-120 | Stock and availability are displayed per product, including availability date and per-warehouse or per-branch levels where required | FR + TR | both | Ask for the acceptable staleness of the stock number in seconds - a live ERP call per product tile is the most common performance failure in these projects. |
| CAT-CAT-130 | Editorially maintained product relations (accessories, spare parts, alternatives, successors, cross-sells) are shown on the product page | FR | both | Spare-part relations often arrive as exploded views or bill-of-material structures rather than flat lists; inspect the source format before promising a simple relation table. |
| CAT-CAT-140 | Products carry the identifiers the business trades on (GTIN, manufacturer part number, customer part number) and they are searchable | FR + TR | both | Customer part number is the B2B search key clients forget - it must be searchable and appear on documents, which means per-customer data inside the search index. |
| CAT-CAT-150 | Product texts are localised per language and market-specific attribute values can differ per market | FR + TR | both | Separate the two - translated fields are a workflow problem, market-specific values are a data model problem, and treating them as one produces a model that cannot express either. |
| CAT-CAT-160 | Product lifecycle states (launch date, end of life, discontinued) control availability and the handling of retired product pages | FR | both | Ask what happens to an end-of-life product with organic traffic and with open orders; a missing rule here produces 404s and support tickets in the first week after go-live. |
| CAT-CAT-170 | Products can be created and maintained in bulk via file import or mass edit, with a validation report per run | FR | both | Ask for the actual file the client uses today - a sixty-column spreadsheet with merged headers dictates more effort than any feature discussion in the workshop. |
| CAT-CAT-180 | Data quality rules produce a completeness status per product and block publication when mandatory data is missing | FR | both | Define who may publish incomplete data - an explicit override right must exist, or editors will bypass the shop and maintain data somewhere else. |

## CAT-SRCH - Search & navigation

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-SRCH-010 | Full-text search across defined product attributes returns ranked results, and ranking is configurable without a deployment | FR + TR | both | Ask who owns relevance and how they will test it - "the search must be good" is untestable; agree a set of twenty real queries with expected top hits as acceptance criteria. |
| CAT-SRCH-020 | Search-as-you-type suggests products, categories and content | FR | both | Check the response-time budget and whether suggestions must already respect customer-specific assortment and prices - if yes, suggestions cannot be cached globally. |
| CAT-SRCH-030 | Result lists offer attribute facets with counts, ranges and multi-select | FR | both | Exact facet counts on restricted assortments and customer prices are the expensive part; ask whether counts must be exact or may be approximate. |
| CAT-SRCH-040 | Search covers customer-specific data such as customer part numbers and previously purchased items | FR + TR | B2B | Needs a per-customer index or a query-time join; decide early because it constrains the search platform choice more than any other requirement here. |
| CAT-SRCH-050 | Search tolerates typing errors and handles synonyms and word forms per language | FR + TR | both | Ask for the language list and whether German compound splitting is needed - compounding needs language-specific dictionaries and per-language tuning effort. |
| CAT-SRCH-060 | Entering a product identifier leads directly to the matching product | FR | both | B2B users paste article numbers with spaces, dashes and leading zeros - agree one normalisation rule and test it against real pasted values from the client. |
| CAT-SRCH-070 | A list of identifiers with quantities can be pasted or uploaded to build a cart in one step | FR | B2B | This is a purchasing workflow, not a search feature; ask for the paste format and, more importantly, the expected behaviour for unknown, blocked or discontinued items. |
| CAT-SRCH-080 | Business users can merchandise result and category pages with pinned products and boosting rules | FR | both | Ask whether merchandising is maintained per market and whether it must survive a full reindex - rules stored only in the index are lost on rebuild. |
| CAT-SRCH-090 | Search analytics report top queries, zero-result queries and click-through per query to business users | FR + NFR | both | Zero-result reporting is what actually improves search over time; name the person who owns the KPI, otherwise the report is built and never read. |
| CAT-SRCH-100 | Result lists can be sorted by relevance, price, name, novelty and availability | FR | both | Price sorting with customer-specific prices means the index must carry prices per price group - check the cardinality of price groups before promising it. |
| CAT-SRCH-110 | Technical products can be found by parametric search over technical values with units and ranges | FR + TR | B2B | Ask whether unit conversion and range logic (for example 5-10 mm) are needed - plain facets cannot express ranges over continuous values. |
| CAT-SRCH-120 | Content and documents (data sheets, manuals, pages) are findable alongside products | FR | both | Ask whether PDF content must be indexed full-text and whether access-restricted documents may appear in results - restricted hits leaking into a public result list is a real finding. |

## CAT-PRC - Pricing & promotions

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-PRC-010 | Every sellable item has a base price per currency and market with a validity period | FR + TR | both | Ask whether prices are net or gross per customer group and whether the ERP or the shop owns them - this decides whether a pricing service is needed at all. |
| CAT-PRC-020 | Prices can be maintained per customer group | FR | both | Ask how many groups and how customers are assigned - one group per customer is a smell that the real requirement is customer-specific pricing. |
| CAT-PRC-030 | Prices can be maintained per individual customer | FR + TR | B2B | Scale price, customer-specific price list and contract price are three different mechanisms, and most platforms cover only two of them out of the box. |
| CAT-PRC-040 | Quantity-dependent scale prices apply per unit of measure | FR | B2B | Clarify whether tiers apply per line, per order or per period (annual volume) - period-based tiers cannot be resolved in the cart and usually belong to the ERP. |
| CAT-PRC-050 | Contract prices apply within their validity and the contract reference travels with the order line | FR + TR | B2B | The contract number normally has to reach the ERP and appear on the invoice; confirm the field exists end to end before accepting the requirement. |
| CAT-PRC-060 | Prices can be determined by a live call to the leading system at cart and checkout | TR | B2B | Ask for the acceptable latency and the fallback when the leading system is unreachable - showing no price is a business decision, not a technical default. |
| CAT-PRC-070 | Price display follows configured rules (net or gross, VAT note, price on request, price hidden before login) | FR | both | "Price on request" is a lead-generation flow, not a price - confirm who receives the request and within which response time. |
| CAT-PRC-080 | Tax is determined per country and customer situation, including reverse charge, VAT ID validation and exemptions | FR + TR | both | Ask whether an external tax engine is required for the target countries; cross-border B2B and marketplace models usually force one, and retrofitting it is expensive. |
| CAT-PRC-090 | Promotions can be defined with percentage or absolute discounts, thresholds and product or category scope | FR | both | Write down stacking and priority rules with the business before design - conflicting promotions is the most common post-launch defect class. |
| CAT-PRC-100 | Coupons and vouchers are supported as single-use codes, code batches and personalised codes | FR | both | Gift cards are a payment instrument with a balance, not a promotion - split them into a separate requirement or they will land in the wrong component. |
| CAT-PRC-110 | Shipping costs can be reduced or waived by promotion rules | FR | both | Ask whether shipping promotions apply before or after tax and how they behave on partial shipments - both answers affect the invoice. |
| CAT-PRC-120 | Cross-product promotions (buy X get Y, mix and match) are evaluated on the whole cart | FR | B2C | These produce cart-level discount lines the ERP must accept; verify the ERP side before agreeing, not after. |
| CAT-PRC-130 | Retrospective conditions such as annual bonus or growth rebates are visible to the customer | FR + TR | B2B | Usually ERP territory - clarify whether the shop only displays the accrued value or is expected to calculate it. |
| CAT-PRC-140 | Business users can simulate and preview prices and promotions for a given date and customer | FR | both | Without a preview the business cannot test a campaign at all; ask whether the preview must be shareable with stakeholders who have no admin access. |
| CAT-PRC-150 | Cart, order and documents show line-level discounts with the reason or promotion name | FR | both | Agree what appears on the invoice versus only in the shop - purchasing departments reconcile line by line and reject documents they cannot match. |

## CAT-CART - Cart & checkout

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-CART-010 | Items can be added to the cart from listing, product page, search results and a previous order | FR | both | Ask whether adding from a listing must respect minimum quantity and packaging unit - it usually must, and that is exactly where quick-add implementations break. |
| CAT-CART-020 | Cart lines enforce minimum, maximum and increment quantities and packaging rounding with a visible message | FR | B2B | Agree whether the system silently rounds up or asks the user; silent rounding produces invoice disputes that are blamed on the shop. |
| CAT-CART-030 | Users can keep several named carts in parallel | FR | B2B | Often used per project or per construction site; ask who owns a cart when the employee leaves and whether colleagues may see it. |
| CAT-CART-040 | A cart can be handed over to a colleague or to a sales representative | FR | B2B | Clarify whether the receiver sees their own prices or the sender's - both answers are defensible and they need different data models. |
| CAT-CART-050 | Carts persist across sessions and devices for signed-in users, and anonymous carts are merged on login by a defined rule | FR | both | Define the merge rule explicitly (add, replace, keep both) or the first release will show duplicated lines after every login. |
| CAT-CART-060 | The cart is revalidated before checkout for price changes, availability, blocked items and expired contracts | FR | both | Ask what the user may do when validation fails - blocking versus warning is a business rule with measurable revenue impact, so it must be decided by the business. |
| CAT-CART-070 | A requested delivery date can be entered per order and, where required, per line | FR + TR | B2B | Per-line dates split the order into schedule lines; confirm the ERP accepts schedule lines before promising the feature. |
| CAT-CART-080 | The customer can choose between complete delivery and shipping as items become available | FR + TR | B2B | The flag must reach the ERP and the fulfilment system; ask what wins if the customer master already carries a contradicting delivery preference. |
| CAT-CART-090 | Delivery addresses can be selected from an address book, entered once, or restricted per unit | FR | both | Ask whether free-text addresses are allowed at all - many B2B setups only permit addresses maintained in the leading system, which removes a whole form and its validation. |
| CAT-CART-100 | Shipping methods and costs are determined by weight, value, destination and service level | FR + TR | both | Get the real freight rules - dimensional weight, dangerous goods and pallet freight are rarely covered by a simple weight table and are found late. |
| CAT-CART-110 | Checkout is possible as a guest, or restricted to registered and approved users | FR | both | In B2B guest checkout is often forbidden; confirm it, because the answer removes an entire flow together with its fraud handling. |
| CAT-CART-120 | A purchase-order number and cost centre can be entered at checkout and made mandatory per customer | FR | B2B | Ask whether the PO number format is validated and whether it must be unique per customer - both requirements are common and both need an explicit rule. |
| CAT-CART-130 | Order-level comments and file attachments (drawings, specifications, delivery instructions) can be submitted | FR + TR | B2B | Attachments must be stored, virus-scanned and forwarded; the forwarding path into the ERP or the service desk is normally the blocker, not the upload. |
| CAT-CART-140 | The order summary shows all cost components and the legally required pre-contract information, with explicit terms acceptance | FR | both | Name the jurisdictions - the German ordering-button and information duties differ from other markets and are audited by third parties. |
| CAT-CART-150 | A failed payment or checkout error preserves the cart and offers retry or an alternative method | FR | both | Ask what happens to reserved stock and to a partially captured payment on retry - the recovery path is where money actually gets lost. |
| CAT-CART-160 | Order placement produces a confirmation page and a confirmation message with the order reference | FR | both | Agree who is the sender of record and whether the confirmation constitutes acceptance of the contract or only a receipt - this is a legal wording decision. |

## CAT-PAY - Payment

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-PAY-010 | Available payment methods are configurable per market and customer group | FR | both | Build the method-by-country-by-segment matrix explicitly; every filled cell is integration, testing and support effort, and the matrix is what the estimate is based on. |
| CAT-PAY-020 | Purchase on account is offered with a credit check and a credit limit | FR + TR | B2B | The core B2B method - clarify who grants the limit, whether it is checked live at checkout, and what happens when the limit is exceeded mid-checkout. |
| CAT-PAY-030 | Card payment is supported with strong customer authentication | FR + TR | both | Ask whether the flow is redirect or embedded and who carries PCI responsibility - the answer sets the scope of the security review and the hosting constraints. |
| CAT-PAY-040 | Locally expected methods (direct debit, bank transfer, wallets, deferred payment) are offered per market | FR | both | Local methods carry local legal requirements such as direct debit mandate texts; confirm the wording, who approves it, and where the mandate is stored. |
| CAT-PAY-050 | Authorisation and capture happen at defined points in the order process | TR | both | This is an accounting decision - align with finance before design, or it gets rebuilt after the first month-end close. |
| CAT-PAY-060 | Partial capture, partial refund and refunds triggered by returns are supported | FR + TR | both | Partial flows are where payment provider and order management capabilities diverge; verify both sides support the same granularity before committing. |
| CAT-PAY-070 | Open items, payment status and dunning state are visible in the account area | FR + TR | B2B | Ask whether open items are read live from the leading system - a nightly extract shows an already paid invoice as open for a day and generates support calls. |
| CAT-PAY-080 | Prepayment and pro-forma invoice flows are supported | FR | B2B | Needs an order state that waits for incoming money and a rule for how long stock is held; get the timeout and the release behaviour in writing. |
| CAT-PAY-090 | Payment instruments can be stored per user or shared within a business unit | FR + TR | both | Clarify whether a unit shares a stored method and who may use it - a shared company card is a permissions requirement, not a payment feature. |
| CAT-PAY-100 | Payment transactions can be reconciled against provider settlement reports | TR | both | Ask who reconciles today and against which report; missing reconciliation surfaces only in finance, months after go-live, and is then urgent. |

## CAT-OMS - Order management

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-OMS-010 | Orders follow a defined state model with customer-facing state names | FR + TR | both | Agree one state model across shop, ERP and fulfilment - three different state vocabularies mapped onto each other is the classic integration mess and a permanent support cost. |
| CAT-OMS-020 | Order history is searchable and filterable by date, purchase-order number, cost centre and orderer, with re-order | FR | both | Ask how far back the history must reach and whether pre-migration orders must appear - legacy order import is a project of its own and is routinely underestimated. |
| CAT-OMS-030 | Order detail shows line-level status together with delivery and invoice documents | FR + TR | both | Confirm which system holds the authoritative document and where the PDFs live; regenerating documents in the shop is rarely acceptable to finance. |
| CAT-OMS-040 | Customers can change or cancel an order within defined rules | FR + TR | both | Get the cut-off rule (before picking, before shipment) and confirm the ERP can accept a change at all - often it cannot, and the requirement becomes a service-desk process. |
| CAT-OMS-050 | Shipments are tracked per shipment with carrier tracking references | FR + TR | both | Several shipments per order and per line need a real tracking data model; a single tracking field on the order will not survive the first split delivery. |
| CAT-OMS-060 | Returns can be requested with reason codes and a return document or label | FR | both | Ask whether returns run through the shop or the service desk today; formalising them in the shop changes the operating process and needs warehouse agreement. |
| CAT-OMS-070 | Credit notes and refunds are visible to the customer with their reference | FR + TR | both | Clarify the source of the credit note and whether the shop only displays it - creating credit notes in the shop is an accounting decision. |
| CAT-OMS-080 | Invoices and order documents can be downloaded per order and from a per-customer archive | FR + TR | B2B | Retention periods and access rights after an employee leaves the customer company are a compliance topic; ask explicitly rather than defaulting to open access. |
| CAT-OMS-090 | Recurring orders and scheduled deliveries can be set up and managed by the customer | FR | both | A recurring order needs a price-at-renewal rule and a defined failure path when a product is discontinued between two runs. |
| CAT-OMS-100 | Call-off orders against a framework contract show the remaining contracted quantity | FR + TR | B2B | The remaining-quantity ledger normally lives in the ERP - confirm that before designing shop-side accounting that will disagree with the ERP. |
| CAT-OMS-110 | Approval status of an order is visible to both requester and approver | FR | B2B | Make sure the approver's view contains what they need to decide, and confirm whether the approver may see prices at all. |
| CAT-OMS-120 | Orders created in other channels (EDI, sales representative, marketplace, phone) appear in the same order history | FR + TR | B2B | Ask whether the shop is meant to be the order display for all channels - if yes, it must show orders it never created, which is an integration requirement, not a UI one. |

## CAT-CUST - Customer & account

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-CUST-010 | Users can register themselves, and in B2B the account requires manual approval before it becomes usable | FR | both | Ask precisely what an unapproved account may see - prices visible before approval is a common accidental disclosure of negotiated conditions. |
| CAT-CUST-020 | Company master data (VAT ID, industry, sales organisation, leading-system customer number) is held per account | FR + TR | B2B | The leading-system customer number is the join key for prices, orders and documents; clarify when it is created and what the shop does before it exists. |
| CAT-CUST-030 | A business hierarchy of company, subsidiaries, sites and departments is supported with inheritance of settings | FR + TR | B2B | Ask for the deepest hierarchy that really exists and whether addresses, prices and approval rules inherit or are set per level - inheritance is where platforms differ most. |
| CAT-CUST-040 | Users are assigned to one or more units and can switch the active unit within a session | FR + TR | B2B | Multi-unit users break page caching and blur audit trails; confirm whether this is a real requirement or a rare edge case before designing for it. |
| CAT-CUST-050 | A role and permission model covers the standard buying-side roles (buyer, approver, administrator, viewer) | FR | B2B | List the permissions the client actually needs and map them onto few roles; an open, free-form permission matrix is a large custom effort with no visible feature. |
| CAT-CUST-060 | A customer administrator can manage their own users, roles and limits without contacting support | FR | B2B | This is what relieves the client's service desk, and it is regularly cut for budget - scope and price it as its own increment so the trade-off is visible. |
| CAT-CUST-070 | Orders above a defined threshold require approval, configurable per user, unit and cost centre | FR | B2B | Clarify whether an approval blocks the order or is post-hoc, and whether the approver sees prices. |
| CAT-CUST-080 | Multi-level or parallel approval is supported, with substitution and escalation on timeout | FR | B2B | Ask for the real escalation rule; holiday substitution is the requirement that only surfaces after go-live, when an order sits unapproved for two weeks. |
| CAT-CUST-090 | Spending limits and budgets can be set per user, unit and period, with consumption visible | FR + TR | B2B | Define what consumes budget - placing the order, the approval, or the invoice - and whether a cancellation releases it again. |
| CAT-CUST-100 | A cost centre or internal account can be assigned per order and, where required, per line | FR | B2B | Ask whether cost centres come from the leading system and whether an unknown value may be entered; per-line assignment usually splits the order document. |
| CAT-CUST-110 | A quote can be requested from a cart, producing a quote document and supporting negotiation rounds | FR | B2B | Define who may change what in a quote, and whether a changed quote is still convertible into an order at the quoted price. |
| CAT-CUST-120 | An accepted quote converts into an order with prices and conditions locked for its validity period | FR + TR | B2B | Get the expiry behaviour - a quote that silently reprices after expiry is a trust problem that costs more than the feature. |
| CAT-CUST-130 | Contracts with their validity, contracted products and prices are visible in the account area | FR + TR | B2B | Ask whether contracts should be visible to the buyer or applied silently; buyers usually want to verify what they negotiated, which turns a background rule into a UI. |
| CAT-CUST-140 | The credit limit and the behaviour when it is reached are defined and, where agreed, visible | FR + TR | B2B | Clarify whether the buyer may see the limit at all - many clients treat the number as confidential, which changes the entire checkout messaging. |
| CAT-CUST-150 | Procurement systems can punch out into the shop and receive a cart back | FR + TR | B2B | Name the protocol and the exact procurement system and version; punchout is standardised in theory and bespoke in practice, and every connection is its own test cycle. |
| CAT-CUST-160 | Orders can be received and confirmed electronically for large customers | TR | B2B | Electronic order intake usually bypasses the shop entirely - decide whether the shop is involved at all before scoping it here, otherwise effort is counted twice. |
| CAT-CUST-170 | A sales representative can act on behalf of a customer, with the impersonation state clearly visible | FR + NFR | B2B | Agree what the representative may do (change price, override a limit, place an order) and log every action - this is an audit requirement, not a convenience feature. |
| CAT-CUST-180 | Customers are assigned to representatives, and representatives only see their own customers | FR + TR | B2B | Ask where territories are maintained; if the CRM owns them, the shop needs a near-real-time feed, and a nightly one produces visible access errors. |
| CAT-CUST-190 | Shopping lists, order templates and customer-specific catalogues can be created and shared within a unit | FR | B2B | Clarify ownership and sharing scope (personal, unit, company) and what happens to a shared list when one of its products is discontinued. |
| CAT-CUST-200 | Preferred and blocked products can be defined per customer and per user | FR + TR | B2B | Check that a block is enforced in the order API and not only hidden in the interface - a blocked item ordered through re-order is a classic defect. |
| CAT-CUST-210 | Billing, shipping and default addresses can be maintained per unit in an address book | FR | both | Ask whether users may edit addresses or only select them; addresses owned by the leading system normally mean read-only in the shop. |
| CAT-CUST-220 | Changes to sensitive account data (bank details, VAT ID, company name) follow an approval path and are recorded | FR + NFR | B2B | These changes carry fraud exposure - require an internal approval and an audit record, and never let them flow straight into the leading system. |
| CAT-CUST-230 | Authentication, password and session policies are enforced, and corporate single sign-on is supported where required | NFR + TR | both | Name the identity provider and whether single sign-on is required per customer - per-customer federation multiplies onboarding effort for every new account. |
| CAT-CUST-240 | Users can request deactivation, deletion and export of their personal data | FR + NFR | both | The right to erasure collides with the duty to retain order data; the resolution is anonymisation - agree which fields are retained and in which state. |

## CAT-CMS - Content & CMS

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-CMS-010 | Business users can author pages from components and preview them before publication | FR | both | Ask whether the preview must show customer-group-specific content - previewing personalised or price-dependent content is far harder than previewing a static page. |
| CAT-CMS-020 | A defined inventory of reusable content components exists, with rules on where each may be placed | FR + TR | both | Agree and cap the component inventory during design - an open-ended component set is unbounded frontend effort and the main reason CMS scope slips. |
| CAT-CMS-030 | Content passes an editorial workflow with draft, review, approval and scheduled publication | FR | both | Ask whether scheduling must be timezone-aware per market, and who is allowed to publish without review. |
| CAT-CMS-040 | Campaign and landing pages can include rule-driven product listings | FR | both | Clarify whether marketing creates such pages per campaign; if yes, page creation must never require a deployment, which is an architecture constraint. |
| CAT-CMS-050 | Editorial content can reference products and be made shoppable | FR + TR | both | Ask whether referenced product data stays in sync automatically when the product changes or is retired - stale product blocks in content are a frequent complaint. |
| CAT-CMS-060 | Navigation and menus can be maintained independently of the category tree | FR | both | Separating navigation from the tree is usually necessary; confirm who maintains which, otherwise both are maintained by nobody. |
| CAT-CMS-070 | Content assets are managed with usage rights and expiry dates | FR + TR | both | Asset rights with an expiry require an active takedown mechanism; this is almost always forgotten and later found by the legal department. |
| CAT-CMS-080 | Editorial formats such as news, blog and knowledge content are supported with tagging and search integration | FR | both | Check whether such content already exists in another system on another domain - two content systems serving one domain forces a routing and SEO decision. |
| CAT-CMS-090 | Content changes are versioned and can be rolled back | FR + NFR | both | Ask for the required depth - a single undo is cheap, an auditable version history with author and timestamp is not. |
| CAT-CMS-100 | Content can be reused across sites with per-site overrides | FR + TR | both | Define the inheritance direction and who may break inheritance, or editors will copy pages and the reuse benefit disappears within a quarter. |

## CAT-MKT - Marketing & personalisation

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-MKT-010 | Content and product recommendations can be personalised by segment or behaviour | FR + TR | both | Agree the measurable goal and the data source; without a control group nobody can say whether personalisation worked, and the feature becomes unfalsifiable. |
| CAT-MKT-020 | Marketing can define and maintain customer segments without development effort | FR + TR | both | Ask which attributes segments may use and whether they include leading-system data - that single answer decides where segmentation has to run. |
| CAT-MKT-030 | Recommendations cover similar products, complements, frequently bought together and previously purchased items | FR | both | In B2B "previously purchased" usually outperforms behavioural models - confirm the priority before buying a recommendation engine. |
| CAT-MKT-040 | Transactional and marketing messages use maintainable templates with per-market branding | FR + TR | both | Separate transactional from marketing early - consent rules, sending systems and deliverability requirements differ and mixing them creates legal risk. |
| CAT-MKT-050 | Newsletter subscription uses double opt-in and stores an auditable consent record | FR + NFR | both | The consent record with timestamp and source is the auditable artefact; confirm which system stores it and how it is produced on request. |
| CAT-MKT-060 | Marketing automation is integrated for campaigns, abandoned cart and win-back flows | TR | both | Ask which system owns the customer profile, the shop or the automation tool, and how conflicting updates resolve - profile ownership decides the whole design. |
| CAT-MKT-070 | Storefront experiments and feature flags can be run and evaluated | FR + TR | both | Experiments must be designed around caching and personalisation; name who evaluates the result and against which KPI, or tests run forever without a decision. |
| CAT-MKT-080 | A loyalty or benefit programme is reflected in the storefront and the account area | FR + TR | both | Clarify whether points are a currency, which makes them a payment and accounting topic, or a status, which makes them a display topic. |
| CAT-MKT-090 | Consent for tracking and marketing technologies is collected and enforced per market | FR + NFR | both | The consent tool blocks tracking scripts - confirm that the agreed KPIs remain measurable once realistic consent rates are applied, before promising the reporting. |

## CAT-INTL - Internationalisation

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-INTL-010 | The storefront is available in several languages with localised content and product data | FR + TR | both | List locales and the fallback chain per field; a missing fallback rule shows up in production as empty pages, not as an error. |
| CAT-INTL-020 | Several currencies are supported with per-currency rounding and display rules | FR + TR | both | Ask who supplies exchange rates and whether prices are converted or maintained per currency - runtime conversion is rarely acceptable in B2B contract pricing. |
| CAT-INTL-030 | Country-specific assortment, prices, taxes, legal texts, payment and shipping options are supported | FR + TR | both | Build the country matrix once and treat each column as its own delivery increment - countries are the most common source of uncontrolled scope growth. |
| CAT-INTL-040 | Several sites or brands run on one platform with a defined split of shared and separate data | FR + TR | both | Agree what is shared (products, customers, orders, content) and what is separate - this is the single largest architecture decision in this area. |
| CAT-INTL-050 | Each market has a defined URL and domain strategy with locale detection and an override | FR + NFR | both | Automatic locale detection, SEO and caching pull in different directions; ask for the agreed rule and the manual override before implementation. |
| CAT-INTL-060 | Right-to-left and non-Latin scripts are supported where target markets require them | FR + NFR | both | Only relevant for some markets, but if it is relevant the frontend effort is real and cannot be added late without reworking layouts. |
| CAT-INTL-070 | Country-specific legal and compliance content is maintained per market | FR | both | Name who supplies and approves the texts per country - legal review of market texts is frequently on the critical path to launch. |
| CAT-INTL-080 | Address, name and telephone formats and mandatory fields follow country rules | FR | both | A German address form used in another market produces undeliverable orders; validation must be per country, and this is cheap only if designed in from the start. |

## CAT-INT - Integration & data

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-INT-010 | Customer master data is exchanged with the ERP with a defined owner per field | TR | both | Write down the field ownership matrix - shop-owned, ERP-owned, bidirectional - before any interface design; ambiguity here causes overwrite incidents in production. |
| CAT-INT-020 | Product master data and prices are supplied from the leading systems | TR | both | Ask for the delta mechanism and the real volume - a full nightly load of 500k products and near-real-time price changes require different designs and different budgets. |
| CAT-INT-030 | Stock and availability data is supplied from the leading system | TR | both | Agree the model: pushed levels, live call, or a reservation service - plus the caching allowance in seconds, which is a business decision. |
| CAT-INT-040 | Orders are transferred to the ERP with an acknowledgement and defined error handling | TR | both | Define what the customer sees when the ERP rejects an order; a silently lost order is the worst possible outcome and the first thing to test. |
| CAT-INT-050 | Order status, delivery and invoice information flows back from the ERP | TR | both | Check whether the ERP can push or must be polled, and the acceptable delay per document type - these differ, and one polling interval for all is usually wrong. |
| CAT-INT-060 | Product content is supplied from a PIM with a defined publication trigger | TR | both | Clarify whether the PIM publishes into the shop or the shop pulls, and who owns media derivatives - split ownership of derivatives causes duplicate assets. |
| CAT-INT-070 | Media assets are supplied from a DAM and delivered through a CDN with the required derivatives | TR + NFR | both | Ask who renders the image variants; generating them in the shop at request time is a known performance trap that only appears under campaign load. |
| CAT-INT-080 | Accounts, contacts, representative assignment and leads are exchanged with the CRM | TR | B2B | Define the deduplication rule between shop registrations and CRM contacts before go-live, otherwise every self-registration creates a duplicate. |
| CAT-INT-090 | Sourcing and fulfilment are integrated with the order management or warehouse system | TR | both | Clarify whether the order management system or the shop decides sourcing - two sourcing brains in one landscape generate defects nobody can reproduce. |
| CAT-INT-100 | Payment service providers are integrated including asynchronous status notifications | TR | both | Notifications need idempotency and replay handling - test the duplicate and out-of-order notification cases explicitly, they occur in production. |
| CAT-INT-110 | A tax engine is integrated for determination and reporting where required | TR | both | Ask whether the engine is called on every cart update; call volume and latency drive both licence cost and checkout performance. |
| CAT-INT-120 | Carrier integration covers rates, label creation, tracking and return labels | TR | both | Separate rating from label creation - they are often different systems and belong to different project phases, and bundling them hides effort. |
| CAT-INT-130 | Analytics and tag management are integrated through a documented data layer | TR + NFR | both | Specify the data layer events and the KPIs they feed; tracking retrofitted after launch permanently loses the baseline the business wanted to compare against. |
| CAT-INT-140 | The search platform is integrated with a defined index build and reindex strategy | TR + NFR | both | Ask how long a full reindex takes and whether the storefront stays fully functional during it - this constrains the release process, not just the search. |
| CAT-INT-150 | Every business entity has a documented system of record with direction and frequency of synchronisation | TR | both | Produce one table (entity, owner, direction, frequency, key) and get it signed off - it prevents most integration arguments later in the programme. |
| CAT-INT-160 | Each integration has a defined technology, authentication and interface contract | TR | both | Ask which counterpart systems cannot serve synchronous calls; that single fact reshapes the integration architecture more than any preference. |
| CAT-INT-170 | Interfaces have defined error handling, retry, dead-letter and alerting with a named responsible team | TR + NFR | both | Define who is alerted when an interface fails at 02:00 and what the business fallback is until it is fixed - without that, monitoring is decoration. |
| CAT-INT-180 | Non-production environments of the integrated systems are available with realistic test data | TR + NFR | both | Ask early whether an ERP test system with realistic data exists - missing counterpart test systems delay more projects than missing features do. |

## CAT-NFR - Non-functional

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-NFR-010 | Response-time targets are defined per key journey at a defined load | NFR | both | State numbers and the measurement point (server, browser, percentile) - "fast" is not testable; agree a p95 target at a named concurrency, per journey. |
| CAT-NFR-020 | Peak load and concurrency targets are defined together with the business event that causes them | NFR | both | Get the real peak (campaign, season, batch order intake) and its shape; average traffic tells you nothing about the design the peak requires. |
| CAT-NFR-030 | Availability targets, maintenance windows and degraded-mode behaviour are defined | NFR | both | Ask what the shop must still do when the ERP is unavailable - browsing without live prices is often an acceptable degraded mode, but only if it was agreed. |
| CAT-NFR-040 | Scalability expectations cover background jobs, imports and indexing alongside storefront traffic | NFR | both | Imports competing with storefront traffic is the usual cause of peak incidents; confirm whether workloads must be isolated and who enforces it. |
| CAT-NFR-050 | The caching strategy is compatible with customer-specific prices, assortments and personalisation | NFR + TR | B2B | Personalised prices defeat full-page caching - the split between a cached shell and dynamic fragments is an architecture-level decision and must be made before estimating. |
| CAT-NFR-060 | Security requirements cover authentication, authorisation, secret handling and vulnerability management | NFR | both | Ask for the client's own security standard, whether a penetration test is a go-live gate, and when it is scheduled - a late gate is a schedule risk, not a technical one. |
| CAT-NFR-070 | Data protection requirements define lawful basis, data minimisation, a deletion concept and processor agreements | NFR | both | The per-entity deletion concept with retention periods is the artefact auditors ask for; assign an owner in the project, not in the client's legal queue. |
| CAT-NFR-080 | Personal data is not exposed in logs, analytics or support tooling beyond what is necessary | NFR | both | Check log content early - full order payloads written to application logs is one of the most frequent findings in these reviews. |
| CAT-NFR-090 | The storefront and, where required, the administration meet a defined accessibility conformance level | NFR | both | Name the accessibility target level (EN 301 549 / WCAG 2.2 AA) and whether the European Accessibility Act deadline applies. |
| CAT-NFR-100 | SEO requirements cover indexable URLs, metadata, structured data, sitemaps and a redirect concept | NFR + FR | both | The redirect map from the old site is the highest-risk single migration item for organic traffic - demand the URL inventory before design, not before go-live. |
| CAT-NFR-110 | Frontend performance targets including core web vitals are defined for mobile and desktop | NFR | both | Agree the tooling and the device class used for acceptance; lab and field measurements disagree and both will be quoted in the go-live discussion. |
| CAT-NFR-120 | A browser and device support matrix is defined | NFR | both | Ask for the client's own analytics rather than a wish list - but legacy browser requirements in B2B intranets are sometimes real and must then be priced. |
| CAT-NFR-130 | Observability covers technical logging, metrics, tracing and business KPIs with named owners | NFR | both | Distinguish technical from business monitoring - nobody notices a broken price feed on a CPU graph, so name the business signals that must be alerted on. |
| CAT-NFR-140 | Backup, restore and recovery targets are defined including the integrated systems | NFR | both | A shop restored to yesterday against a current ERP state is not a recovery; the combined scenario has to be defined and tested at least once. |
| CAT-NFR-150 | Business-relevant actions (price override, impersonation, approval, sensitive data change) are auditable | NFR | B2B | Name the actions, the retention period and who may read the audit trail - an audit log nobody may read satisfies no auditor. |
| CAT-NFR-160 | Compliance requirements beyond data protection (product compliance, export control, sector rules) are met | NFR + FR | both | Export control and dangerous-goods checks block orders - where relevant they are functional requirements disguised as compliance and need their own flow. |
| CAT-NFR-170 | Documentation, handover and maintainability requirements are defined and accepted | NFR | both | Define the acceptance artefacts (architecture documentation, runbook, handover sessions) with a date, or they will not be produced. |

## CAT-OPS - Operations & admin

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| CAT-OPS-010 | Internal users have roles and permissions in the administration following least privilege | FR + NFR | both | Ask whether agency or partner staff need administrative access and how those accounts are governed and revoked - external admins are a recurring audit finding. |
| CAT-OPS-020 | Service-desk staff can look up orders and customers, impersonate a user and create an order manually | FR | both | Internal tooling is chronically under-specified; interview the service desk directly, not only the project sponsor, or the tooling gap appears in hypercare. |
| CAT-OPS-030 | Internal staff can enter and edit orders on behalf of customers within defined rules | FR + NFR | B2B | Clarify whether internal staff may override price and stock, and how each override is logged and reported to management. |
| CAT-OPS-040 | Content and campaign operations follow a calendar and a release process | FR | both | Ask whether content changes must wait for a deployment window - if yes, marketing will build a workaround outside the platform within months. |
| CAT-OPS-050 | Batch jobs, imports and interfaces have a business-readable status view | FR + NFR | both | Give operations a view they can read without a developer; "job failed" without business context turns every failure into an escalation. |
| CAT-OPS-060 | The environment, release and deployment strategy includes a stable staging with realistic data | NFR + TR | both | Ask how many environments exist and whether test data can be refreshed on demand - this constrains the entire test approach and the acceptance plan. |
| CAT-OPS-070 | It is defined which settings are editable at runtime and by whom | FR + NFR | both | Every runtime-editable setting is also a way to break production; agree the list and the authorised roles instead of making everything configurable. |
| CAT-OPS-080 | Data migration scope for customers, orders, content and URLs is defined with acceptance criteria | TR + FR | both | Agree what is migrated and what stays in the legacy system behind a read-only view; migrating everything is rarely worth its cost and always delays cutover. |
| CAT-OPS-090 | A cutover and hypercare plan exists with rollback criteria | NFR | both | Define the rollback trigger in business terms and name who is allowed to call it - a technical rollback criterion nobody owns is never invoked. |
