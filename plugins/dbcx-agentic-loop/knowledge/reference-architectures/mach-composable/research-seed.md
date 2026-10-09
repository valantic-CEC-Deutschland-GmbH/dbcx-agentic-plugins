## Research topics – MACH / Composable Commerce Patterns

Open questions an analyst must resolve before any composable recommendation is defensible. Nothing here is a finding: every line is a question for the client, answered with a named source (document, interface list, contract, or the workshop statement and who made it) and a date. Every line is marked *(verify)* because none of it can be assumed from the reference file.

### 1. Constraint and driver
- Which capability is the binding constraint today, and what measured evidence supports that — lead time, lost requirement, cost figure, incident record *(verify)*
- What business outcome would justify the programme, who owns that number, and how will it be measured *(verify)*
- Has a target architecture already been decided elsewhere in the organisation, by whom, and on what basis *(verify)*
- Would a single-capability replacement or a frontend-only decomposition resolve the constraint *(verify)*

### 2. Team size and capability
- Platform team size, split explicitly into build and run capacity *(verify)*
- In-house frontend engineering capacity for permanent ownership, as distinct from a partner build *(verify)*
- In-house integration engineering capacity, and who currently operates the interfaces *(verify)*
- Which capabilities are partner-provided, under what contract, with what notice period and run responsibility *(verify)*
- On-call arrangements today: scope, hours, SLA, and who is reachable for an end-to-end failure *(verify)*

### 3. Operating model
- Named owner per system and per prospective service, for incidents, changes, upgrades and cost *(verify)*
- Release cadence per system and the organisation's change-freeze calendar *(verify)*
- Who is contractually and politically accountable for an end-to-end failure, and has that been accepted *(verify)*
- Environment provisioning, infrastructure-as-code maturity and observability the client can read without the vendor *(verify)*
- Internal back-office tooling that the current suite provides and that a composable landscape would have to replace *(verify)*

### 4. Integration budget and landscape
- Does an integration platform or event backbone exist today, is it operated, and by whom *(verify)*
- Does an interface inventory with volumes and peak loads exist, and when was it last reconciled *(verify)*
- Which business rules currently live inside integration flows rather than an owning system *(verify)*
- Funded integration budget for build and for run, stated separately *(verify)*
- Existing operational practice for events: idempotency, schema evolution, replay, dead-letter handling, consumer lag monitoring *(verify)*

### 5. Data ownership prerequisite
- Declared master per data domain — product, price, inventory, customer, account, consent, order, content, asset *(verify)*
- Which domains the commerce platform masters today that were not intended to be mastered there *(verify)*
- Does an attribute-level ownership decision exist and is it signed off *(verify)*
- Would fixing data ownership remove the stated reason for replatforming *(verify)*

### 6. Cost, contracts and constraints
- Total cost of ownership model over three to five years, covering engineering, operations and N upgrade cycles, not licences alone *(verify)*
- Cost shape: capital versus ongoing engineering, and which of the two the budget is built for *(verify)*
- Pricing metric per vendor (orders, revenue, API calls, messages, seats) and its growth relative to the business *(verify)*
- Contract terms per vendor: notice period, support hours, escalation, exit and data-export terms, renewal date *(verify)*
- Composed availability and latency across the chained services versus the business requirement *(verify)*
- Data residency, sovereignty, security-zoning and regulatory constraints, checked per vendor rather than once *(verify)*
- Deprecation policies and mandatory-update deadlines per vendor, and the annual maintenance load they sum to *(verify)*

### 7. Migration and reversibility
- Which coexistence period is acceptable, for how long, and who funds the parallel run *(verify)*
- Whether cut-over can be per channel, country, brand or journey — and what would force a big-bang *(verify)*
- Reversal option per step and the point after which it is no longer available *(verify)*
- Decommissioning criteria per legacy component, and who signs them off *(verify)*
