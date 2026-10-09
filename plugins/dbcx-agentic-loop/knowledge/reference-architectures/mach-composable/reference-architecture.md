# MACH / Composable Commerce Patterns

Everything in this file is REFERENCE GUIDANCE, to be confirmed per client. It is not a finding and not a recommendation: it describes what the MACH principles demand of a client organisation, which composable patterns recur, and when composable is the wrong answer. A deliverable must argue from the client's own team size, operating model, interface inventory and budget shape — never from this file. Where the client's situation contradicts a statement here, the client's situation decides.

## 1. The four MACH principles and what each demands of the client

The vendor side of each principle is well documented. The part that decides whether a programme succeeds is what the principle demands of the client organisation, which is rarely on the slide.

**Microservices** — the vendor ships independently deployable services. The client must be able to run a landscape whose parts version independently: a service inventory with an owner per service, contract and version management between them, distributed tracing and correlation ids so a failed order can be followed across services, and a release process that does not require every service to move together. The organisational demand is a team structure that matches the service boundaries; where one team owns all services, the independence is theoretical and the coordination cost returns as internal queueing.

**API-first** — the vendor exposes every capability through an API rather than a UI or a template. The client inherits the work the suite used to hide: the composition of those APIs into a journey, the caching and rate-limit strategy, an integration platform or backend layer that mediates them, and API lifecycle management as an ongoing discipline. API-first also means no back-office screen exists for a capability until someone builds it — the client must budget for internal tooling that a suite would have shipped.

**Cloud-native** — the vendor operates the runtime elastically. The client must be able to consume that: infrastructure-as-code and environment provisioning as a practised routine, observability the client can read rather than the vendor's dashboard, cost management for consumption-based pricing (someone must own the bill and be able to explain a spike), and acceptance that maintenance windows and release dates are the vendor's to choose. Data residency and network zoning requirements must be checked against each vendor separately, not once for the landscape.

**Headless** — presentation is separated from the backend. The client owns a frontend application for its whole life: framework choice and upgrades, rendering and caching strategy, performance and Core Web Vitals, accessibility, SEO and URL continuity, and the editorial preview experience that a coupled storefront provided for free. This is the principle most often underestimated, because the build is visible and the ownership is not: a headless frontend is a permanent engineering commitment, not a project deliverable.

## 2. Composable patterns

**Best-of-breed per capability** — a specialist product per capability (commerce engine, PIM, CMS, search, OMS, payment). *Fits* when several capabilities are genuinely the constraint, the client already operates an integration platform, and there is capacity to manage a vendor per capability. *Does not fit* when only one capability is weak — replacing that one is cheaper and reversible.

**Frontend-first decomposition, commerce backend kept whole** — the storefront is separated and the suite stays as the backend. *Fits* when the pain is release speed, front-end experience, multi-brand or multi-country presentation, and the backend's business capabilities are adequate. This is the lowest-risk entry point and often sufficient; it is also the pattern most often skipped in favour of a full decomposition that was never needed.

**Incremental strangler migration** — capabilities are peeled off the incumbent one at a time behind a stable façade, with the old system serving everything not yet moved. *Fits* when the incumbent must stay in production throughout and a big-bang cut-over is unacceptable. *Demands* a façade or routing layer, a data-synchronisation strategy for the coexistence period, and an organisation that can fund a multi-year parallel run without declaring victory early.

**Orchestration / BFF layer** — a backend-for-frontend composes several services into the calls a channel actually needs. *Fits* when multiple channels consume the same services with different shapes, or when service APIs are too chatty for a mobile client. *Risk* — it becomes the new monolith and the place business logic accumulates, so the rule that it may compose and shape but not own domain logic has to be enforced in review, not stated once.

**Event backbone** — state changes are published and consumed asynchronously. *Fits* when several consumers need the same state changes and eventual consistency is acceptable. *Demands* real operational practice: idempotent consumers, schema evolution, ordering and partitioning decisions, replay and dead-letter handling, and per-consumer lag monitoring. Without those, it produces stale data that surfaces days later with no error to point at.

## 3. When not to go composable

The strongest reasons to decline are organisational, and they do not become weaker because the architecture is sound.

**A small platform team.** Composable multiplies the number of things that must be understood, upgraded, monitored and paid for. A team that is already fully occupied keeping one suite current will not absorb N vendors, N contracts and N upgrade cycles; the work does not disappear, it becomes a backlog with a security clock on it. Count run capacity, not headcount.

**No in-house frontend capability.** Headless makes the frontend a permanent product. A client who has always received a storefront from a vendor or a partner, and who has no intention of hiring frontend engineers, is buying an application it cannot maintain. A partner can build it; someone must still own it on the Monday after go-live.

**No integration platform or integration budget.** In a composable landscape, integration is the architecture. Without an existing platform or event backbone and a funded team to run it, the interfaces end up as point-to-point connections between more systems than before — the sprawl the programme was meant to remove, at a higher vendor count.

**Few and simple requirements.** Where the requirement list is modest and largely standard, a suite covers it out of the box and the composable premium buys flexibility nobody will use. Decomposition is justified by a constraint that is actually binding, not by the possibility of a future one.

**A business that needs one throat to choke.** Some organisations require a single accountable vendor for contractual, procurement, audit or political reasons. In a composable landscape, accountability for an end-to-end failure lands on the client's own integration team by construction. If the organisation is not willing to be that accountable party, the model is a mismatch regardless of its technical merits.

**A landscape whose real problem is data ownership.** If product data is mastered in the shop, prices are duplicated, the customer exists three times or the order lifecycle runs in two systems, a new platform will inherit every one of those problems and add integration work on top. Data ownership must be fixed first; doing so often removes the reason for the replatforming.

**A total cost of ownership dominated by ongoing engineering rather than licences.** When the model shows that most of the cost is people — integration, frontend, operations, upgrades — moving to composable increases exactly the dominant cost line. A licence saving that is smaller than the added engineering cost is a worse deal presented as a better one.

## 4. Cost and operating-model consequences

**Who runs what** — every service needs a named owner for incidents, changes, upgrades and cost. Unowned services are found during the first serious incident.

**On-call** — the client's on-call scope grows to cover the composition layer and the frontend, and the interfaces between vendors, which is where end-to-end failures land. Vendor on-call covers their service, not the journey.

**The upgrade treadmill of N vendors** — each vendor's release cadence, deprecation policy and mandatory-update deadline applies independently. The client's annual maintenance load is the sum, and it is not schedulable at the client's convenience. Budget it as recurring capacity, not as project work.

**Contract and SLA fragmentation** — N contracts with different terms, notice periods, support hours, escalation paths, exit clauses and pricing metrics (orders, revenue, API calls, messages, seats). Availability does not compose: chained services multiply their availabilities, so several 99.9 % services in one path deliver less than 99.9 %. Check that the composed figure meets the business requirement, and that no vendor's pricing metric grows faster than the business it serves.

**Cost shape** — consumption-based pricing moves cost from predictable licence to variable spend that tracks traffic, including traffic that does not convert. Someone must own the bill, be able to explain a spike, and have the authority to change a design that causes one.

## 5. Decision checklist

Answer each with evidence from the client, not an assumption. A "no" is not a veto, but it is a prerequisite that must be funded and named before the programme starts.

- Which single capability is the binding constraint today, and what evidence shows it — a measured lead time, a lost requirement, a cost figure?
- Would replacing that one capability, or decomposing only the frontend, resolve the constraint at lower risk?
- Is the real problem data ownership rather than the platform? If mastership is unclear per domain, has that been decided and signed off first?
- What is the platform team's run capacity as opposed to its build capacity, and who will own each service after go-live?
- Does in-house frontend engineering capacity exist for permanent ownership, including upgrades, performance and accessibility?
- Does an integration platform or event backbone already exist and run, with a funded team, or is it part of the programme's scope?
- Does an interface inventory with volumes and peak loads exist?
- Does a total cost of ownership model over at least three to five years exist, covering engineering, operations and N upgrade cycles rather than licences alone?
- Do the composed availability, latency and residency figures meet the business requirement, per vendor and end to end?
- Who is the accountable party for an end-to-end failure, and has that organisation accepted the role in writing?
- What is the reversal option per step, and until when does it remain available?
- What business outcome will be measured to decide whether to continue after the first decomposed capability, and by when?
