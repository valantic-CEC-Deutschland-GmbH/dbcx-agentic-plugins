## Research topics – CX / Commerce Reference Architecture

Open questions an analyst must resolve before this reference architecture can be applied to an engagement. Nothing here is a finding: every line is a question whose answer must come from the client, with the source named (document, interface list, configuration file, or the workshop statement and who made it) and the date. Every line is marked *(verify)* because none of it can be assumed from the reference file.

### 1. Data ownership
- Which system is the declared master per data domain: product, price, inventory, customer, account, consent, order, content, asset, segment *(verify)*
- Does an attribute-level ownership list exist, or only a system-level one — and is it signed off by someone with the authority to decide *(verify)*
- Which attributes can be edited in more than one system today, and which system wins in practice when they disagree *(verify)*
- For product data: which attributes come from the ERP material master, which are enriched, and where is enrichment actually done *(verify)*
- For B2B: where is the account hierarchy mastered, and does the hierarchy the shop shows match the one the ERP prices against *(verify)*
- Where is identity mastered versus profile versus account, and is a stable customer key propagated to every channel *(verify)*
- Where is the auditable consent record held, and how is a withdrawal propagated to every consumer *(verify)*
- Which domains does the commerce platform master today that were not intended to be mastered there *(verify)*
- Is the search index rebuildable from sources without data loss, and when was that last actually done *(verify)*
- Who owns product-data governance by name, and what decision rights does that role have *(verify)*

### 2. Interface inventory
- Does a current interface inventory exist, who maintains it, and when was it last reconciled against reality *(verify)*
- Per interface: source, target, direction, style (synchronous API, event, batch/file, iPaaS-mediated, direct database), protocol and format *(verify)*
- Per interface: the consumers — including the ones not in the inventory, found by asking the receiving teams *(verify)*
- Which interfaces write into another system's database directly, and which of those are read-only *(verify)*
- Which interfaces sit in a user-facing path (checkout, login, search) and what their failure behaviour is *(verify)*
- Which business rules currently live inside mapping or integration flows rather than in an owning system *(verify)*
- How many partner-specific interfaces exist, and what the onboarding effort per new partner is *(verify)*
- Which interfaces are undocumented but load-bearing — typically discovered by asking what breaks during a maintenance window *(verify)*
- What monitoring exists per interface, and who receives the alert *(verify)*

### 3. Volumes and peaks
- Orders per day and per peak hour, and the ratio between average and peak *(verify)*
- Catalogue size: products, variants, locales, channel-specific projections, media assets *(verify)*
- Update rates: product changes per day, price changes per day, stock updates per minute at peak *(verify)*
- Traffic profile: sessions, requests per second at peak, campaign spikes, seasonal pattern and the date of the annual peak *(verify)*
- Registered customers and B2B accounts, plus the number of contacts per account for the largest accounts *(verify)*
- Message volumes per interface and per event topic, with the peak burst rather than the daily average *(verify)*
- Batch windows: current duration, the window available, and how close the two already are *(verify)*
- Latency budgets that exist as commitments (checkout response, search response, availability lookup) and whether they are measured *(verify)*
- Growth assumptions the business is planning against, and who owns those numbers *(verify)*

### 4. Organisation and governance
- Size and composition of the platform team, split between build and run capacity *(verify)*
- In-house frontend engineering capacity, and in-house integration capacity, as distinct questions *(verify)*
- Which capabilities are provided by partners, under what kind of contract, and with what notice period *(verify)*
- On-call arrangements per system: who is reachable, at which hours, under which SLA *(verify)*
- Release cadence per system and the change-freeze calendar, including the business's own freeze periods *(verify)*
- Decision rights: who can decide data ownership, who can decide an interface contract, who can decide to decommission a system *(verify)*
- Editorial and product-data operations capacity, and whether an enrichment backlog already exists *(verify)*
- Which organisational units own which system politically, and where that conflicts with the technical target *(verify)*
- Whether a target architecture has already been decided elsewhere in the organisation, and by whom *(verify)*

### 5. Licensing and hosting constraints
- Licence model per system: per-order, per-revenue, per-message, per-user, per-core, and the contract's renewal date *(verify)*
- Which contractual limits would be crossed by the target architecture (message volumes, environments, seats, API calls) *(verify)*
- Hosting model per system, and any data-residency or sovereignty requirement that binds it *(verify)*
- Regulatory obligations in scope: data protection, retention, accessibility, industry-specific rules, audit requirements *(verify)*
- Constraints imposed by the current hosting on the target (no persistent local storage, restricted outbound network, no custom infrastructure components) *(verify)*
- Security requirements that shape integration: authentication standards, network zoning, secret management, penetration-test cadence *(verify)*
- Whether the budget is shaped for capital investment or for ongoing engineering cost, and which of the two the target requires *(verify)*
- Exit and portability terms per vendor, including data export format and the notice period *(verify)*

### 6. Migration and coexistence
- Which systems must run in parallel during the transition, for how long, and who pays for the parallel run *(verify)*
- Which data must be migrated, which may be left behind, and who is entitled to decide that per domain *(verify)*
- Whether the cut-over can be per country, per channel, per brand, per product range or per journey — and what forces a big-bang if anything does *(verify)*
- How master data stays consistent while two masters exist, and which direction the temporary synchronisation runs *(verify)*
- Which interfaces must be duplicated during coexistence, and what that costs to operate *(verify)*
- URL, SEO and redirect continuity requirements, and who owns the measurement of any regression *(verify)*
- Rollback options per step, and the point after which rollback is no longer available *(verify)*
- The business events that constrain the timeline: peak season, fiscal year end, contract renewals, other programmes competing for the same people *(verify)*
- Decommissioning criteria per legacy system: what must be true before it can actually be switched off, and who signs that off *(verify)*
