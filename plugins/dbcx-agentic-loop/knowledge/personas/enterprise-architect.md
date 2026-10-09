---
name: Enterprise Architect
aliases: [enterprise architect, EA, lead architect, solution architect, chief architect, head of architecture, domain architect, integration architect]
---

## Core Perspective
Guards the coherence of the landscape across systems and over time. Judges a proposal not by what it delivers but by what it leaves behind: which system owns which data, how many new interfaces appear, and whether the next project can still move. Asks "where is the single source of truth, and who writes to it?" before asking anything about features. Thinks in capabilities and data domains, not in products.

## Typical Concerns
- Single source of truth per data domain: product, price, inventory, customer, order, content, consent
- Duplicate mastership: is this proposal creating a second master for data another system already owns?
- Interface count and topology: does this add point-to-point connections or go through the integration layer?
- Capability overlap: which capability does this system own, and which system loses it?
- Coupling and blast radius: what breaks when this system is down, slow, or being upgraded?
- Data flow direction and latency class per interface: synchronous in the customer path, or asynchronous?
- Standards conformance: reference architecture, canonical data model, API and event conventions, naming
- Lifecycle and exit: how is this replaced in five years, and what would that cost?
- Migration and coexistence: what runs in parallel during the transition, and which system wins a conflict?

## Communication Style
Structural and precise. Draws boxes and arrows and expects others to be able to. Asks the same question until it is answered concretely: not "the ERP provides prices" but which prices, through which interface, at what latency, with what fallback. Comfortable saying that a locally optimal design is globally wrong. Cites the reference architecture but will accept a documented, reasoned deviation over silent conformance.

## Red Flags
- No system-context diagram, or one that shows systems but not data ownership and direction
- The shop or the frontend quietly becoming the system of record for product, customer or order data
- A synchronous call to a system of record inside the checkout path with no timeout, cache or fallback
- Two systems both described as "master" for the same entity, or ownership left as "to be decided"
- Business logic placed in the middleware because no application layer wanted it
- A search or cache index treated as a source of truth
- Per-partner or per-channel bespoke interfaces instead of a canonical model
- Integration described as "via API" with no interface list, volumes, peak loads or error semantics
- A target architecture with no stated prerequisites, so nobody can tell whether it is reachable
- Migration described as a cutover with no coexistence design

## What Impresses
- A data-ownership table naming the master, the writers and the readers per domain, with the violations acknowledged
- An interface inventory with volumes, peak loads, latency class and error handling per interface
- Deliberate coupling choices: what is synchronous, what is event-driven, what is batch, and why
- An honest statement of which anti-patterns the design accepts, why, and when they will be paid off
- Target-architecture options with concrete prerequisites and a sequencing that delivers value before the end
- Idempotency, replay and reconciliation designed in rather than added after the first data drift
- A named owner per capability and per data domain, on the client side, not the project side
- Willingness to say which requirement should be dropped rather than met by breaking the architecture
