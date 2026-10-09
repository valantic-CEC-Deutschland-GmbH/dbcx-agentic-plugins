# iPaaS / Integration Platform Requirement Catalogue

This file is a reference **SEED**, not a client deliverable. It is a hand-written completeness checklist of
requirements that integration programmes tend to need, written from general integration-architecture practice
and not derived from any engagement. Nothing in it is a client requirement until an engagement has confirmed
it with that client, in their words, with their numbers. Per engagement the catalogue is **maintained**: entries
are selected, reworded to the client's language, given real interfaces, volumes and thresholds, and extended
with what the client needs that is missing here. Entries that were never discussed must not appear in a
deliverable. Two things should exist before this catalogue is used to compare tools: the **interface inventory**
(system pair, direction, protocol, volume, frequency, owner) and **data ownership per entity and attribute**.

## How to read the columns

- **id** — stable identifier `<AREA>-NNN`, numbered per area from `010` in steps of 10 so new entries can be
  inserted without renumbering. Ids are permanent: once allocated, an id keeps its meaning and is never reused
  for a different capability. They are used to trace a client requirement back to the catalogue entry it came from.
- **capability** — the capability in one line, phrased so it can be turned into a testable requirement. It is a
  prompt for elicitation, not final requirement text.
- **typical FR/TR/NFR** — the usual classification: **FR** = behaviour an operator, partner or business user can
  exercise; **TR** = a technical or interface constraint on how the solution is built or connected; **NFR** = a
  measurable quality attribute (throughput, latency, availability, residency, cost). Several entries are
  dual-classified because they split into a behaviour and a constraint; the engagement decides which half is
  being written.
- **B2B/B2C/both** — where the capability normally matters. `both` is the common case; `B2B` marks capabilities
  that are usually only in scope with trading partners or account-based selling. It is a hint about likelihood,
  not a rule.
- **notes** — the discriminating question to ask, the classic trap, or the thing that actually decides effort.
  This column is the reason the catalogue exists; read it before writing the requirement.

## IPAAS-CONN — Connectivity and adapters

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-CONN-010 | Protocol coverage for the required interfaces (HTTP/REST, SOAP, OData, JDBC, JMS/AMQP, SFTP, mail) | TR | both | Do not shortlist on an adapter matrix; list the actual interfaces first. One missing protocol on one legacy system decides the tool; ten adapters nobody will use decide nothing. |
| IPAAS-CONN-020 | On-premise connectivity to systems behind the firewall | TR | both | Ask exactly what the agent or gateway needs: an outbound-only tunnel, a VPN, or an inbound firewall rule. An inbound rule triggers a security review that is often longer than the integration build itself. |
| IPAAS-CONN-030 | Managed file transfer with pickup, archive and rename semantics | TR | both | The trap is the half-written file: a poller collecting while the partner is still uploading. Require a temp-name-then-rename or trigger-file convention per partner, in the interface specification. |
| IPAAS-CONN-040 | Database and legacy adapters (direct table or stored-procedure access) | TR | both | Direct database access is the fastest to build and the hardest to maintain: it couples the integration to a schema nobody documents. Ask whether the owning team accepts that coupling, in writing. |
| IPAAS-CONN-050 | SAP-specific connectivity (IDoc, RFC/BAPI, OData, packaged integration content) | TR | both | The discriminator is the SAP release and whether the client may extend standard IDoc or service structures. An extension means an SAP-side change request with its own approval and release timeline. |
| IPAAS-CONN-060 | Custom adapter or connector SDK for a system with no standard adapter | TR | both | One custom adapter is normal; three is a signal the tool is the wrong fit. Also ask who maintains it after go-live, and against which runtime version it must be re-certified. |
| IPAAS-CONN-070 | Outbound calls to third-party SaaS APIs with OAuth flows | TR | both | Token lifecycle is where this breaks: refresh inside a long-running flow, and what happens when the provider rotates a secret. Require automated refresh and secret retrieval, never a token pasted into a flow. |
| IPAAS-CONN-080 | Inbound webhook reception from SaaS providers | TR | both | Ask about signature verification and duplicate delivery. Most SaaS webhooks are at-least-once and unordered, which pushes idempotency and reordering into the receiving flow. |
| IPAAS-CONN-090 | Interface inventory as a precondition for the tooling decision | TR | both | The most useful artefact in the programme and usually the missing one: system pair, direction, protocol, payload, volume, frequency and data owner per interface. Without it, any iPaaS estimate is a guess with a number on it. |

## IPAAS-MAP — Mapping and transformation

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-MAP-010 | Graphical mapping versus code-based transformation | TR | both | Discriminator: who maintains the map after go-live? Graphical maps are reviewable by non-developers and effectively unmergeable in version control; code maps are the reverse. Choose per team capability, not per taste. |
| IPAAS-MAP-020 | Canonical or intermediate data model between systems | TR | both | Do the arithmetic: point-to-point mappings grow with the square of the system count, canonical mappings linearly plus one model to govern. With three systems canonical is overhead; beyond four it is the only thing that scales. |
| IPAAS-MAP-030 | Lookup and value-mapping tables (units, countries, payment and tax codes) | TR | both | Ask where these tables live and who edits them. Hard-coded in the map means a deployment for every new country code; require an externalised, business-editable value map with its own change history. |
| IPAAS-MAP-040 | Enrichment lookups against a third system mid-flow | TR | both | Every enrichment call adds a failure mode and latency to the flow. Ask whether the data can be cached or pre-joined instead - synchronous enrichment inside a high-volume flow is a hard throughput ceiling. |
| IPAAS-MAP-050 | Schema evolution and backward compatibility of mappings | TR | both | Agree the rule up front: additive changes only, unknown fields ignored, no field ever repurposed. Without it, one newly mandatory ERP field breaks every consumer on the same day. |
| IPAAS-MAP-060 | Large-payload handling and streaming transformation | NFR/TR | both | Get the largest realistic payload: a full price file, a complete catalogue export. In-memory tree transformation of a very large file is where the runtime dies; streaming has to be designed and load-tested, not hoped for. |
| IPAAS-MAP-070 | Format conversion (XML, JSON, CSV, fixed-width, EDIFACT, spreadsheet) | TR | both | Fixed-width and CSV are the deceptive ones: encoding, delimiter escaping, quoting, decimal separators and date formats vary per partner. Require a per-interface data-format specification, not the word "CSV". |
| IPAAS-MAP-080 | Field-level mapping documentation and traceability | NFR | both | The field-level mapping specification is the artefact the client keeps and audits. Ask whether it must be generated from the deployed artefact - hand-maintained mapping documents are out of date within a month. |

## IPAAS-ORCH — Orchestration and flow control

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-ORCH-010 | Explicit synchronous versus asynchronous classification per interface | TR | both | Classify every interface deliberately. Synchronous coupling means the shop is down when the ERP is down; most "it must be real time" requirements are satisfied by asynchronous processing plus a cached read. |
| IPAAS-ORCH-020 | Content-based routing and conditional flow | FR/TR | both | Ask how many routing conditions exist and who is allowed to change them. Routing on payload values means the integration layer holds business semantics, which is exactly where undocumented rules accumulate. |
| IPAAS-ORCH-030 | Splitter and aggregator patterns (batch to items, items to batch) | TR | both | The aggregator needs a completion condition *and* a timeout: what happens when 998 of 1000 items arrive? An undefined completion condition is the classic stuck-process incident nobody can explain. |
| IPAAS-ORCH-040 | Long-running and stateful process orchestration | TR | both | Ask for the longest expected duration and what happens to in-flight state across a runtime restart or deployment. Statefulness is the property that decides whether an iPaaS or a process engine fits. |
| IPAAS-ORCH-050 | Saga and compensation for multi-system business transactions | TR | both | There is no distributed rollback: the order is in the ERP, the payment failed. Require a named compensating action per step, otherwise the business inherits manual cleanup as an unwritten requirement. |
| IPAAS-ORCH-060 | Scheduling of periodic jobs (cron, calendar, business-day aware) | FR/TR | both | Ask about time zones, daylight saving and per-market business calendars. A nightly job defined in one time zone silently shifts by an hour twice a year and lands in the middle of the order peak. |
| IPAAS-ORCH-070 | Throttling and concurrency limits towards fragile downstream systems | TR | both | The downstream ERP is the bottleneck, not the iPaaS. Get the permitted concurrency and per-minute call limits from the owning team and enforce them in the flow, or the integration converts a slowdown into an outage. |
| IPAAS-ORCH-080 | Sequencing guarantees where message order matters | TR | both | Name the interfaces where order genuinely matters (price after product, address before order) and the key it is ordered by. Global ordering destroys parallelism; per-key ordering almost always suffices. |
| IPAAS-ORCH-090 | Bulk and initial-load flows kept separate from delta flows | TR | both | Initial load and delta are different non-functional problems and usually different flows. Reusing the delta flow for a full catalogue load is the standard go-live weekend failure. |

## IPAAS-ERR — Error handling, retry and replay

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-ERR-010 | Idempotency keys and duplicate suppression | TR | both | Ask for the business key per message and where duplicates are detected. Without idempotency every retry risks a duplicate order or a double stock movement - this is the most commonly missing requirement in integration scopes. |
| IPAAS-ERR-020 | Retry with exponential backoff and a retry ceiling | TR | both | Specify the policy per interface class, not once globally. Aggressive retries against a struggling ERP are precisely how an integration layer turns a degradation into a full outage. |
| IPAAS-ERR-030 | Separation of technical errors from business errors | TR | both | The discriminating question: is a rejected order a defect or a business outcome? Technical errors get retried; business errors need a person and a message back to the source system. Conflating them buries real rejections in a retry queue. |
| IPAAS-ERR-040 | Dead-letter store for messages that cannot be processed | TR | both | A dead-letter queue nobody watches is a silent data-loss channel. Require a named owner, a review cadence and an alert on arrival, otherwise the requirement is documented but not met. |
| IPAAS-ERR-050 | Operator-initiated replay and re-drive of failed messages | FR | both | Ask who may replay and whether replay is safe - see IPAAS-ERR-010. Replay without idempotency is how a single incident produces duplicate financial postings and a reconciliation project. |
| IPAAS-ERR-060 | Poison-message handling and head-of-line protection | TR | both | One malformed message must not block the queue behind it. Ask what happens to the other five thousand messages while the bad one retries - head-of-line blocking is the failure users describe as "the integration hangs". |
| IPAAS-ERR-070 | Error notification and alert routing to the responsible owner | FR/NFR | both | Route by interface owner, not to one shared mailbox. A shared mailbox receiving thousands of alerts a week is functionally identical to having no alerting at all. |
| IPAAS-ERR-080 | Business-facing exception view and error reporting | FR | both | Business users need to see their failed orders, not stack traces. Ask whether the exception view must live in the iPaaS tool or in the business system the user already has open all day. |
| IPAAS-ERR-090 | Catch-up behaviour after a downstream outage | NFR/TR | both | Ask what volume accumulates during a defined outage window and whether catch-up must be throttled. A four-hour ERP outage followed by an unthrottled burst takes the ERP down a second time. |

## IPAAS-MON — Monitoring and operations

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-MON-010 | End-to-end message tracing across all hops | NFR/TR | both | The test: given an order number from customer service, can someone see every hop that message took in under a minute? If tracing stops at the platform boundary, the answer is no and support will guess instead. |
| IPAAS-MON-020 | Correlation id generated once and propagated across systems | TR | both | This needs agreement from every connected system, so it is a governance requirement wearing technical clothing. Decide who generates the id and which header or field carries it through each protocol. |
| IPAAS-MON-030 | Operational dashboards for volume, latency and error rate per interface | NFR | both | Ask what the operations team actually looks at on Monday morning. A per-interface volume trend catches the failure nobody alerts on: a flow that quietly stopped sending anything. |
| IPAAS-MON-040 | SLA alerting including missing-message detection | NFR | both | Alerting on errors is easy; alerting on absence is what matters. "The nightly price file did not arrive by 06:00" must be a monitored condition in its own right, with an owner and an escalation. |
| IPAAS-MON-050 | Payload retention and support access to message content | NFR/TR | both | Two conflicting requirements meet here: support needs payloads to diagnose, data protection limits how long personal data may be kept. Set retention per interface and mask the fields support does not need. |
| IPAAS-MON-060 | Environment landscape and promotion path (dev, test, production) | TR | both | Ask how endpoints, credentials and partner parameters differ per environment. Configuration baked into the artefact means every promotion is a manual edit, which means production drift within a quarter. |
| IPAAS-MON-070 | Version control and CI/CD of integration artefacts | TR | both | The discriminating question: are flows in version control and buildable from source, or edited in a browser against production? The second answer changes the entire operating model and the risk profile of every change. |
| IPAAS-MON-080 | Automated interface testing with mocks and contract tests | NFR | both | Integration tests need mockable counterparties. Ask whether a test ERP exists and how often it is refreshed - "we test in production with real orders" is a real answer and a real risk that belongs in the report. |

## IPAAS-SEC — Security, secrets and data protection

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-SEC-010 | Transport security and mutual TLS with client certificates | TR | both | Certificate expiry is the single most common cause of integration outages. Require an inventory with expiry dates, a named owner per certificate and a renewal alert - as part of this requirement, not as a wish. |
| IPAAS-SEC-020 | Message-level security (signing, encryption, WS-Security) | TR | both | Ask whether it is genuinely mandated or transport security suffices. Message-level security is normally driven by a partner or regulator; where nobody mandates it, it is cost and complexity without benefit. |
| IPAAS-SEC-030 | Secret and credential lifecycle (vault, rotation, no secrets in artefacts) | TR | both | Test: can a secret be rotated without redeploying a flow? If not, rotation will quietly be skipped and the audit finding is only a matter of time. |
| IPAAS-SEC-040 | Tenant, environment and role isolation inside the platform | TR | both | Ask who can read production payloads. Developers with production payload access makes support fast and is a data-protection finding - decide it deliberately rather than inheriting the default. |
| IPAAS-SEC-050 | PII minimisation and masking in logs and traces | TR/NFR | both | Most integration tooling logs the whole payload by default. Require field-level masking rules per interface, agreed with the data-protection owner, before the first flow reaches production. |
| IPAAS-SEC-060 | Audit trail of configuration and deployment changes | NFR | both | Who changed the mapping that broke last week's invoices? If flows can be edited in production without an audit record, root-cause analysis is impossible and the same change will happen again. |
| IPAAS-SEC-070 | Data residency and cross-border processing of payloads | NFR | both | Ask where the runtime *and* the message and trace stores physically sit. A platform region that differs from the data-protection commitment is a blocker that surfaces late, in legal review, after tool selection. |

## IPAAS-API — API management

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-API-010 | API gateway in front of internal services | TR | both | Ask what the gateway is actually for: security enforcement, rate limiting, protocol translation, or just a stable URL. If it is only a URL, it is an extra hop with its own availability and latency cost. |
| IPAAS-API-020 | API products, plans and consumer onboarding | FR | both | Worth building only when there are real external consumers. For two internal consumers this is ceremony; for a partner ecosystem it is the whole point. Ask for the consumer list and its expected growth. |
| IPAAS-API-030 | API versioning and deprecation policy | TR | both | Require the policy in writing: how a version is expressed, how long an old version is supported, how consumers are notified. Without it no version is ever retired and all of them must be maintained forever. |
| IPAAS-API-040 | Rate limiting and quotas per consumer | TR/NFR | both | Derive the limit from the downstream system's capacity, not from a round number. Then decide the behaviour at the limit: a hard rejection, or accept and process asynchronously. |
| IPAAS-API-050 | Developer portal with documentation and try-it | FR | both | Ask whether documentation is generated from the specification or written by hand. Hand-written API documentation is wrong within two releases and converts directly into support load. |
| IPAAS-API-060 | Self-service credential issuance for consumers | FR | B2B | Mainly a partner-facing requirement. The discriminator is approval: fully self-service, or request-and-approve? An approval step needs an owner and an SLA for issuing credentials, or partner onboarding stalls. |
| IPAAS-API-070 | API specification as the contract (specification-first, validated in CI) | TR | both | Discriminating question: is the specification written before the implementation and enforced in the build, or exported from the code afterwards? Only the first order produces a contract consumers can safely build against. |
| IPAAS-API-080 | Per-API and per-consumer usage analytics | NFR | both | This is what makes deprecation possible: you cannot retire a version without knowing who still calls it. Require per-consumer usage data with retention long enough to cover a full deprecation window. |

## IPAAS-EVT — Event streaming

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-EVT-010 | Broker choice and its consequences (queue versus log semantics) | TR | both | The discriminator: must a new or recovering consumer re-read history (a log) or only consume once (a queue)? Retrofitting replay onto a queue-only design means rebuilding the integration, not configuring it. |
| IPAAS-EVT-020 | Event and topic design (granularity, naming, ownership) | TR | both | Ask what an event carries: a full state snapshot (larger, self-contained, simple consumers) or a thin notification (small, forces every consumer to call back to the source). This one choice sets the coupling for years. |
| IPAAS-EVT-030 | Schema registry and event contract governance | TR | both | Without a registry, the first breaking producer change is discovered by a consumer in production. Require compatibility rules enforced at publish time, not written in a guideline document nobody reads. |
| IPAAS-EVT-040 | Ordering and partitioning strategy | TR | both | Ordering only exists within a partition. Ask for the partition key per topic - usually the business entity id - and confirm that no consumer silently depends on ordering across different entities. |
| IPAAS-EVT-050 | Delivery-guarantee choice (at-least-once versus exactly-once) | TR | both | Exactly-once end to end across heterogeneous systems is effectively unavailable. The honest requirement is at-least-once delivery plus idempotent consumers - write it that way and cross-reference IPAAS-ERR-010. |
| IPAAS-EVT-060 | Replay from an offset or timestamp | FR/TR | both | Ask the retention needed to make replay useful and what a replay does downstream. Replaying a week of stock events into a live shop is not a recovery, it is a second incident with the first one's name on it. |
| IPAAS-EVT-070 | Consumer lag monitoring and back-pressure handling | NFR | both | Consumer lag is the leading indicator for nearly every event-driven incident. Require lag alerting per consumer group and a defined behaviour when a consumer cannot keep up: slow the producer, shed, or buffer. |
| IPAAS-EVT-080 | Transactional outbox in the producing application | TR | both | The dual-write problem: the order is committed but the event is lost, or the reverse. If the producing system cannot implement an outbox, say so plainly - the alternative is a reconciliation job, not a reassurance. |
| IPAAS-EVT-090 | Coexistence of event-driven and request/response interfaces | TR | both | Most landscapes need both. The trap is answering a synchronous business question from an event projection: "is this order paid?" read from a view that is seconds behind produces support tickets nobody can reproduce. |

## IPAAS-EDI — B2B and EDI

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-EDI-010 | EDIFACT message support (orders, order responses, dispatch advices, invoices, price catalogues) | TR | B2B | Never estimate "EDIFACT" as one line. Each message type per partner is its own mapping and its own test cycle, because every partner implements a different subset with different mandatory segments. |
| IPAAS-EDI-020 | ANSI X12 support for North American trading partners | TR | B2B | Only in scope where US or Canadian partners exist. If both X12 and EDIFACT are needed, the canonical model of IPAAS-MAP-020 earns its cost immediately rather than eventually. |
| IPAAS-EDI-030 | openTRANS, BMEcat and other industry-specific formats | TR | B2B | Common in German-speaking B2B and wholesale. Ask for a real sample file from the actual partner - the published standard and what the partner sends differ more often than they agree. |
| IPAAS-EDI-040 | EDI transport protocols (AS2, OFTP2, SFTP, X.400, value-added network) | TR | B2B | The protocol is chosen by the partner, not by the client. Ask whether a value-added network sits in between: a VAN absorbs the protocol diversity and adds a per-message fee that belongs in the cost model. |
| IPAAS-EDI-050 | Partner onboarding process with reusable partner profiles | FR | B2B | The effort question is: how long does partner number fifty take? If each partner is a bespoke flow, onboarding never gets cheaper. Require a profile-plus-parameters model and measure onboarding time as an NFR. |
| IPAAS-EDI-060 | Technical and functional acknowledgements | TR | B2B | Acknowledgements are how receipt is proven in a commercial dispute. Ask what happens when an expected acknowledgement does not arrive within the agreed window - that is a monitoring requirement, not a mapping one. |
| IPAAS-EDI-070 | Per-partner mapping variance and partner-specific rules | TR | B2B | Every partner has quirks: their own article numbers, units, rounding and mandatory segments. Model these as partner parameters and lookup tables rather than forked mappings, or maintenance grows linearly with partners. |
| IPAAS-EDI-080 | E-invoicing mandates (Peppol, ZUGFeRD, XRechnung and country equivalents) | TR/NFR | B2B | Regulatory, dated and non-negotiable per country, and the country set keeps changing. Ask which markets and which deadlines, and treat it as a compliance item with a date attached, not as a feature to prioritise. |

## IPAAS-MDM — Master-data synchronisation patterns

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-MDM-010 | System of record defined per entity and per attribute | TR | both | The most valuable half-day of the programme. Attribute-level ownership is the real answer - ERP owns price, PIM owns description, the shop owns none of it. Undefined ownership guarantees a data conflict after go-live. |
| IPAAS-MDM-020 | Initial load separated from delta synchronisation | TR | both | Two flows with different non-functional profiles. Ask for the initial-load record count and the acceptable load window; the delta interface almost never survives being reused for the full load. |
| IPAAS-MDM-030 | Change detection at the source (timestamp, CDC, event, full compare) | TR | both | The quality of the source's change detection caps the quality of the whole synchronisation. A source with no reliable change timestamp forces full compares, which changes the volume, latency and cost estimate entirely. |
| IPAAS-MDM-040 | Delete and tombstone handling | TR | both | The classic gap: a record deleted in the source stays live in the shop forever because the delta interface only carries creates and updates. Require an explicit delete signal or a periodic reconciliation sweep. |
| IPAAS-MDM-050 | Key mapping and cross-reference tables between systems | TR | both | Ask whether a shared business key exists at all. If not, the cross-reference table becomes critical state that needs its own backup, migration, audit and recovery story - and usually nobody has assigned it an owner. |
| IPAAS-MDM-060 | Conflict resolution when two systems change the same record | TR | both | Discriminating question: can the same attribute be edited in two systems? If yes, define the winner rule (source of truth, last write wins, or block the second editor) before build; if no, enforce read-only in the other system's UI. |
| IPAAS-MDM-070 | Reconciliation runs and drift reporting | NFR | both | Every delta interface drifts. Require a periodic count-and-compare per entity with a reported delta, because the alternative is learning about the drift from a customer complaint or a finance dispute. |
| IPAAS-MDM-080 | Hierarchy and relationship synchronisation (category trees, bills of material, account hierarchies) | TR | both | Hierarchies break differently from flat records: a parent arriving after its child, or a moved node orphaning a whole subtree. Require an ordering guarantee or a two-pass load, and test a node move explicitly. |

## IPAAS-NFR — Quality attributes and operations

| id | capability | typical FR/TR/NFR | B2B/B2C/both | notes |
|---|---|---|---|---|
| IPAAS-NFR-010 | Throughput per interface at normal and peak load | NFR | both | Get messages per hour at peak, not per day on average. Peaks are what break integrations: month-end invoicing, a promotion, or the nightly full price file arriving during the evening order rush. |
| IPAAS-NFR-020 | Latency target per interface class | NFR | both | Classify explicitly: real time (seconds, e.g. a stock check at checkout), near real time (minutes, e.g. order to ERP), batch (hours, e.g. accounting). One latency figure for all interfaces is untestable and over-engineers most of them. |
| IPAAS-NFR-030 | Availability target and planned-maintenance behaviour | NFR | both | Ask what the shop does while the integration layer is unavailable. Store-and-forward with asynchronous retry keeps it selling; a synchronous dependency does not. That is an architecture consequence, not a percentage. |
| IPAAS-NFR-040 | Disaster recovery with RPO and RTO for in-flight messages | NFR | both | The overlooked question: on failover, are in-flight messages lost, duplicated or preserved? All three answers exist in the market, and each one implies different requirements on the systems upstream. |
| IPAAS-NFR-050 | Data residency of messages and traces at rest | NFR | both | This covers the message store and the trace/log store, not just the runtime region. Traces holding customer addresses in the wrong region is the finding that appears late, in the security review, after selection. |
| IPAAS-NFR-060 | Cost model per message, connection or runtime hour | NFR | both | Commercial models differ sharply. Model the cost against real peak volume before selecting - a chatty per-item interface can cost more in message fees than the platform licence, and redesigning it later is a project. |
| IPAAS-NFR-070 | Observability and operational runbooks | NFR | both | Ask who operates this at 03:00 and what they read. A runbook per interface class - what failed, how to diagnose, when it is safe to replay, who to call - is a deliverable, not documentation debt. |
| IPAAS-NFR-080 | Capacity for full catalogue and full price loads | NFR | both | The concrete stress case worth sizing against: a complete product and price load with the real record count and payload size. If it does not fit the maintenance window, the design changes - the schedule will not. |
