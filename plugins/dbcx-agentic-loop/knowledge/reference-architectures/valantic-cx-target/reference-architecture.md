# valantic CX Target-Architecture Standard

Everything in this file is REFERENCE GUIDANCE, not a finding. It describes how valantic draws and assesses a customer-experience landscape (commerce, PIM, DAM, CMS, CRM, ERP, integration, search, identity, analytics) so that the picture, the tables behind it and the assessment agree. Nothing here is a statement about a particular client: a deliverable cites the client's own systems and interfaces with the evidence actually seen, never this file. Where a client's landscape contradicts a rule here, the landscape is right and the rule is the question that uncovered it.

The patterns are **best practice, not hard guardrails**: apply a pattern where the client's landscape has the element and never draw an empty placeholder (an integration hub, an enablement lane) to satisfy the pattern.

## 1. Canvas

| lane | holds | rule |
|---|---|---|
| Experience and channels | storefronts, websites, portals, apps, marketplaces, feeds, personas and external parties as actors | personas on top by segment (customer groups, internal roles, partners, suppliers, authorities); external channels as boxes with a market or partner list |
| Integration and data | integration platform / middleware, API gateway, event broker, file transfer, data lake or warehouse | drawn only where the client has or decides on such a component; the analytics platform sits here or in systems of record as a consumer box with ONE aggregated inbound arrow, per-source analytics flows go to the interface table and the data-flow zoom |
| Systems of record | ERP, PIM, DAM, CRM, CMS, OMS, WMS, PLM, pricing engine, identity | one box per deployable, licensed or operated system |
| Enablement (optional) | identity and CIAM, CDN, consent, monitoring, tracking | used when cross-cutting services would otherwise spray arrows across the board; omitted for small landscapes |

## 2. Legend and palette (mandatory block on every board)

Colour and border style double-encode every status, so the board survives greyscale printing and colour-vision deficiency.

| element | meaning | fill | border | label |
|---|---|---|---|---|
| system, existing, kept | stays as it is | light grey `#F2F2F2` | solid dark grey `#616161`, 2 px | logical name, product below |
| system, new | introduced by the programme | light green `#C8E6C9` | solid green `#2E7D32`, 2 px | logical name, product or overarching term |
| system, to be replaced | exists today, replaced by a new box | light orange `#FFE0B2` | solid orange `#EF6C00`, 2 px | logical name, product, "→ replaced by <box>" badge |
| system, retiring | switched off in a phase | light grey `#EEEEEE` with diagonal hatch | dashed grey `#9E9E9E` | name struck through, phase badge |
| system, decision open | capability decided, product not | light blue `#E3F2FD` | dashed blue `#1E88E5`, 2 px | overarching term only (CRM, PIM, "Search"); candidates live in the decision table, never on the box |
| context system | not changed by the programme, drawn for completeness | white | dotted grey `#BDBDBD`, 1 px | logical name |
| manual step | a person moves or maintains data | human icon on the arrow or box | – | who, how often |
| arrow, synchronous API | request/response | solid black line, filled head | – | data objects, frequency "on request" |
| arrow, asynchronous event or message | fire and forget via broker or queue | dashed black line, filled head | – | data objects, trigger |
| arrow, file or batch | scheduled transfer | dash-dot grey `#757575` line, open head | – | data objects, schedule ("nightly 02:00") |
| arrow, manual | export/import or re-keying by a person | solid line with a human icon | – | data objects, frequency, role |
| arrow direction | data direction, double head for bidirectional | – | – | one arrow per direction when the payloads differ |
| ★ SSOT marker | this system masters the listed data domains | gold star with domain list | – | e.g. "★ product enrichment, assets" |
| ⟳ copy marker | this system writes the object back into the master or holds an editable copy | grey circular arrow | – | data object |
| ⚠ conflict marker | two systems claim the same domain | red triangle | – | domain; resolved by the client, not by the architect |
| numbered badge | annotation, rule, risk | black circle with number | – | text in the annotation table |
| phase badge | delta view only | "P1", "P2" in a rounded box | – | phase from the roadmap |

Legend block: top-right of every board, identical wording on every board of the engagement.

## 3. Element rules

1. **One box = one deployable, separately licensed or operated system.** Modules, microservices and capability lists go to a zoom view, never onto the landscape sheet. A product name and a project name for the same installation are one box with both names.
2. **Logical name first, product second.** The logical name (commerce platform, PIM, CRM) is the stable identity; the product and, where known, the version or edition are the second line. Vendor logos are decoration and allowed.
3. **Undecided means the overarching term.** A box whose capability is decided but whose product is not carries the capability term and the "decision open" style. Candidates, decision owner and target date are rows in the decision table. The product decision is normally taken after the architecture project.
4. **Personas and external parties** on top and at the sides: customer segments, internal roles (sales, service, product management), suppliers, marketplaces, authorities, punch-out customers.
5. **Manual steps stay visible** with a human icon: manual product upload, re-keyed orders, spreadsheet exports, e-mailed price lists. They are findings, not embarrassments, and every one is a candidate for the roadmap.
6. **Annotation boxes are numbered** and repeated in an annotation table (rule, constraint, risk, open decision) so a text document can cite them.
7. **Multi-country and multi-brand** are drawn as one storefront or one system with a market or brand list, not as repeated boxes. A country-specific exception (a non-SAP ERP, a local shop) is its own box with a market badge.
8. **Language:** one language per board, the client's vocabulary for data objects, abbreviations expanded in the legend.

## 4. Arrows and the interface table

The diagram is a **view of a table**. Every arrow carries an interface id `I-nn` that exists in the interface table; an arrow without a row, or a row without an arrow, is a defect of the deliverable.

| column | content |
|---|---|
| id | I-nn, stable across versions |
| source system, target system | by logical name (inventory id) |
| direction | source → target; two rows when payloads differ per direction |
| data objects | client vocabulary: products, prices, stock, customers, orders, invoices, assets, content, consent, tickets, leads |
| style | api / event / file / batch / manual / unknown |
| frequency | as the source states it: real time, on request, every 15 min, nightly, monthly, on demand |
| middleware | the hub or gateway the interface runs through, or "direct" with the reason in `note` |
| owner | team or role that operates the interface (table only, never on the board) |
| volume, peak | for the checkout, availability, pricing, login and order paths at least an order of magnitude |
| status | as-is / target / retire, phase |
| evidence | document locator, or `visual, unverified` with a client question |

Where the table lives is a project decision: typically Excel, sometimes only Miro. In the dbcx loop the D1 system inventory and the D3 data-flow workbook are exactly these tables.

Analytics and data-lake flows: the landscape sheet shows the analytics platform once, as a consumer box with one aggregated inbound arrow ("analytics extracts", style and frequency as documented). Per-source analytics interfaces are rows in the table and appear in the data-flow zoom where they matter. Rationale: analytics masters nothing operational, and one arrow per source doubles the arrow count without changing any decision.

## 5. Integration hub policy

Whether an integration platform belongs in the target picture is a **per-client decision**, evaluated and recommended in every project against: number of systems and interfaces, protocol and format diversity, need for central monitoring and error handling, existing platform investment and skills (an SAP landscape with BTP skills is a different case from a mid-size retailer with two interfaces), and whether the same team can operate flows after go-live.

When a hub exists or is recommended: state the policy once on the board ("all system-to-system flows via <hub> except …"), route the flows through it, and annotate every direct link with the reason (latency budget, vendor-provided connector, file drop with no consumer besides one system). When no hub exists and none is recommended: draw the point-to-point interfaces honestly, never an empty "Data Integration Layer" box. Business rules and derived data never live in the hub; it owns contracts, routing, mapping and monitoring.

## 6. Single source of truth per data domain

| data domain | canonical master | typical writers | classic violation |
|---|---|---|---|
| product structure, commercial and logistic attributes (material number, unit, tax class, weight, status) | ERP material master | ERP material management | shop or PIM invents materials the ERP does not know |
| product enrichment (descriptions, marketing attributes, classification such as ETIM or eCl@ss, relations, locale variants, publication state) | PIM | PIM editors, supplier feeds via PIM import | attributes edited in the shop backoffice so the PIM export is switched off for them |
| assets (binaries, renditions, rights) | DAM | creative production, supplier feeds | the shop's media folder as the de-facto library |
| price and conditions | ERP condition records or a pricing engine | pricing maintenance, contract processes | customer discounts rebuilt as shop promotions |
| inventory and availability | ERP or WMS; an availability service aggregates but never originates | goods movements, allocation | the shop decrements stock itself or has no staleness budget |
| customer identity and credentials | CIAM / identity provider | registration, SSO | registrations isolated in the shop |
| customer account, hierarchy, terms, credit | ERP business partner (B2B), CRM for the person and relationship | ERP, CRM | shop-created accounts that the ERP cannot bill |
| customer profile, segments, leads | CRM or CDP | sales, marketing | parallel customer numbers per channel |
| consent and preferences | consent management platform or the CDP holding the auditable record | capture points | consent stored per channel, withdrawal not propagated |
| order after capture | OMS where one exists, otherwise the ERP sales order | OMS / ERP lifecycle | the shop advances its own order status model in parallel |
| editorial content | CMS | editors, translators | content copied per channel and edited in each copy |
| search index | derived, never a master | indexing pipeline | corrections applied to the index because the source is slow |
| analytics and behavioural data | data warehouse, lakehouse or CDP | pipelines | operational decisions read from the analytics store |

Rules: a mastership statement names the document that claims it; two claims for one domain are a ⚠ conflict and a client decision, never an architect's choice; a system that writes back into another system's object is a ⟳ copy, not a second master; "unknown" is a legitimate verdict and better than a guess.

## 7. Views

| view | content | rule |
|---|---|---|
| As-is | systems and interfaces as documented today, with manual steps and shadow IT visible | no target elements; "decision open" style not used |
| Target | the end state for the horizon | lifecycle styles keep / new / replace / retire / open; hub policy stated |
| Delta by phase | target elements and arrows with phase badges; retiring systems with retire badge and phase | derived from the roadmap; every phase must be executable (a master cannot move before the receiver can hold the object; a system cannot retire while a flow still feeds from it) |
| Data-flow zoom | one flow across systems, for example product data: created in the ERP, enriched in the PIM, assets from the DAM, replicated to commerce and search, published to marketplaces; every step with system, action, automated or manual, frequency, owner | one zoom per critical flow (product, price, stock, customer and account, order, content); not per lane, not per system |

Zoom template (one row per step): `step | system | action (create, enrich, approve, transform, replicate, publish) | automated / manual (human icon) | trigger or frequency | owner | interface id | evidence`.

## 8. Anti-patterns seen in our own diagrams (symptom first)

| symptom | why it happens | cost | way out |
|---|---|---|---|
| No legend; the same colour means "system of record" on one board and "to be decided" on another | each author invents a palette | readers misread status; boards cannot be compared across projects | section 2 legend block on every board |
| Silent hub bypasses | drawn from memory, exception not discussed | integration policy is unverifiable; estimates miss interfaces | annotate every direct link with its reason, or route it |
| Arrows without ids | picture drawn before the table | nothing traceable to requirements or estimates | interface table first, diagram as its view |
| "TBD" without decision owner | decision belongs to a later phase | the open decision disappears from follow-up | decision table with owner and date; overarching term on the box |
| As-is periphery mixed into a target picture | one board for everything | nobody can say what changes | separate as-is, target and delta views |
| Microservices next to whole ERPs | one author zooms, another does not | granularity noise, unreadable for stakeholders | one box per system; zoom views for decomposition |
| Two labels for the same link | drawn twice from two directions | double counting in the interface list | one id per interface, two rows only when payloads differ per direction |
| Analytics arrows from every source | data lake drawn as an operational hub | arrow count doubles without a decision changing | one aggregated arrow; detail in the table |
| Organisational implications promised in the title, absent on the board | operating model has no visual element | the reader looks for it and finds nothing | ownership and operating model in the tables; roadmap names the team changes |
| No version or edition on products | not known at drawing time | capability claims cannot be checked | product line carries version or edition where known, "version unknown" otherwise |

## 9. Target-option patterns and their prerequisites

| move | fits when | prerequisites before it can be sequenced | typical sequence |
|---|---|---|---|
| Introduce a PIM | product enrichment happens in the shop, spreadsheets or several systems; more than one channel needs the same product data | declared product-data ownership per attribute group; classification standard chosen; product-data governance role named | ERP material master interface first, then enrichment migration, then channel feeds; shop backoffice editing switched off per attribute group |
| Replace the commerce platform | end of life, cost or capability gap documented; requirements with evidence | requirements set with priorities; SSOT for product, price, stock and customer decided; integration approach decided | MVP markets first with the existing masters unchanged; further markets and ERPs in later phases |
| Introduce a headless frontend or CMS | content and commerce must be composed per market with business-user autonomy; several touchpoints share content | content model and editorial roles defined; identity across touchpoints; performance and SEO requirements measured | CMS with the website first where the shop carried the content, then storefront composition |
| Introduce an integration platform | see section 5 | team to operate flows; monitoring the business can read; canonical data model for the top five objects | highest-volume or most fragile interfaces first; never all at once |
| Re-home the customer master (to CRM or ERP business partner) | registrations or accounts exist only in the shop; sales cannot see customers | identity split (CIAM) decided; account hierarchy owner decided; reconciliation and dual-run period planned | CIAM first, then account master, then profile sync; shop registration becomes a consumer |
| Retire a system | its data domains have a new master and every flow from it has a replacement | delta view shows no arrow left from it in the retire phase | after the last consuming flow is switched, with an archive decision |

## 10. Tables behind every board

System inventory: `id | logical name | product, version or edition | category | lifecycle status | decision status | owner | operating model (SaaS, PaaS, on-prem, hosted) | markets | ★ mastered domains | evidence`. Interface table: section 4. Decision log: `id | capability | status (decided, preferred, candidates, open) | candidates | owner | target date | rationale | evidence`. Annotation table: `badge | type (rule, constraint, risk, open decision) | text | affects (system or interface ids)`.

## 11. Using this file in an assessment

Use sections 2, 3 and 4 to check the client's own diagrams and to draw the deliverable pictures. Use section 6 to generate the SSOT questions and the conflict list. Use section 5 to decide and justify the hub recommendation for this client. Use section 9 to check that every target option states its prerequisites and a sequence. Cite the client's systems and documents, never this file; where a row here is contradicted by the client's evidence, record the contradiction as a finding and a question.
