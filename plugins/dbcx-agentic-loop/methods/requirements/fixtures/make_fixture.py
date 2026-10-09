#!/usr/bin/env python3
"""Write toy engagement content into an initialised RUN folder (single-run project) so the whole `requirements` chain can be smoke-tested.

Usage: python3 methods/requirements/fixtures/make_fixture.py <run_dir>

Creates
  run.json                                    placeholders filled (client, consultancy, title, context, system.type)
  input/2026-04-15-workshop-notes.md          workshop notes (>= 41 lines, so the corpus gets #L1 AND #L41 anchors)
  input/2026-04-22-workshop-checkout.md       second workshop, contradicts the first about payment terms
  input/requirements-longlist.xlsx            a client longlist, sheet `Longlist` -> #Longlist!Rn anchors
  -> `dbcx corpus index` turns these into SRC-001 (notes), SRC-002 (checkout), SRC-003 (longlist)
  analysis/inventory/source_inventory.md      full inventory: Sources, Epics (5, one out of scope), Coverage, 5 claims
  analysis/scopes/checkout.md                 one epic analysis: 6 requirements (one `inferred`), a contradiction, questions, 4 claims
  analysis/gauntlet/<scope>/round1-{client,standard}.md   passing score files for checkout, D1 and SET
  analysis/consolidated/SET.md                the consolidated set: 9 requirements, cross-check, catalogue gaps, questions, 4 claims
  analysis/gate/round1-product_owner.md       one gate persona
  analysis/summaries/D1.md, D2.md             management summaries
Every locator in the fixture resolves against the indexed corpus - `dbcx evidence check <scope>` must report 0 dangling cells.
"""
import os, sys, json, textwrap

T = os.path.abspath(sys.argv[1])
DE = json.load(open(os.path.join(T, "run.json"), encoding="utf-8")).get("languages", {}).get("deliverable") == "de"
SYSTEM = "E-Commerce-Plattform" if DE else "eCommerce platform"


def t(de, en):
    """client-facing fixture text in the run's deliverable language (a German customer edition reads German throughout)"""
    return de if DE else en


def w(p, s):
    p = os.path.join(T, p); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(textwrap.dedent(s))


def J(p): return json.load(open(os.path.join(T, p), encoding="utf-8"))
def W(p, d): json.dump(d, open(os.path.join(T, p), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def fill_run():
    p = J("run.json")
    p["engagement"].update({"consultancy": "Fixture Consulting", "client": "Fixture Parts GmbH",
                            "client_context": "B2B spare-parts distributor, 4 countries, replacing a 12-year-old shop; toy data.",
                            "title": t("Anforderungen Fixture", "Requirements fixture")})
    p["system"] = {**p.get("system", {}), "type": SYSTEM}
    W("run.json", p)


# ------------------------------------------------------------------ the client's material (input/ -> corpus)
def inputs():
    w("input/2026-04-15-workshop-notes.md", """\
    # Workshop 1 - scope and processes (2026-04-15)

    Participants: head of eCommerce, head of IT, purchasing, two key account managers, Fixture Consulting.
    Goal of the day: agree what the new shop must do for the four sales countries.

    ## Customers and accounts

    Customers are companies. A company has several buyers, and the buyers must not see each
    other's orders unless they belong to the same purchasing group. Registration is never
    self-service: sales creates the company, the buyer receives an invitation mail.

    Every buyer must be able to see their own order history for the last 24 months.
    The head of eCommerce: "Without contract prices in the shop we do not go live."

    ## Catalogue and prices

    Products come from the ERP today. Prices are customer specific and are calculated in the
    ERP; the shop must never calculate a price itself. Stock is shown as a traffic light,
    not as a number, because purchasing does not want exact stock levels in the shop.

    Discontinued products must show their successor product. This was marked as nice to
    have for the first release.

    ## Checkout

    Buyers order against a purchase order number; the field is mandatory for all countries.
    Payment on account is the only payment method for the first release. Credit card was
    discussed and explicitly ruled out for the first release.

    Split delivery per plant is needed later, not in the first release.

    ## Integration

    The ERP is the leading system for customers, products, prices, stock and orders.
    Orders are transferred to the ERP through the existing middleware, at most 15 minutes
    after the buyer confirms them. Product data is imported nightly.

    A PIM is planned but not yet bought; the shop must not depend on it for go-live.

    ## Non-functional

    The shop must be usable on the shop floor with a poor connection: a product page has to
    render in under two seconds on 3G. Availability was discussed as "the same as the ERP"
    without a number.

    ## Out of scope

    Selling through marketplaces was raised by sales and ruled out for this project by the
    head of eCommerce - the marketplace topic belongs to a separate initiative.

    ## Open points from the day

    - Which countries get the shop first? Not decided.
    - Who owns the product texts once the PIM exists? Not decided.
    """)
    w("input/2026-04-22-workshop-checkout.md", """\
    # Workshop 2 - checkout deep dive (2026-04-22)

    Participants: head of eCommerce, finance, two key account managers, Fixture Consulting.
    This session went through the checkout step by step on the whiteboard.

    ## Cart

    The cart must survive a session: a buyer builds a cart over days and orders when the
    purchasing group has approved it. A buyer can have several named carts.

    Uploading a CSV of article numbers into the cart was asked for by both account managers
    and is a must for the first release - buyers work from their own maintenance lists.

    ## Checkout steps

    Step 1 delivery address from the ERP addresses of the company, no free text addresses.
    Step 2 requested delivery date, one per cart.
    Step 3 purchase order number, mandatory.
    Step 4 review and confirm.

    Finance: payment terms are per customer in the ERP and must be displayed in the review
    step, so the buyer sees the terms that apply before confirming.

    ## Payment

    Finance stated that payment on account requires a credit limit check against the ERP
    before the order is accepted, and that the limit is per company, not per buyer.

    Note: in workshop 1 payment on account was described as the only method with no mention
    of a limit check. Finance considers the check mandatory for go-live.

    ## Approvals

    Orders above a company specific threshold need approval by a second buyer of the same
    purchasing group. The threshold lives in the ERP.

    ## Confirmation

    The buyer receives an order confirmation mail immediately, and a second mail when the
    ERP has accepted the order. Both mails must carry the purchase order number.

    ## Open points from the day

    - Is the credit limit check hard (order rejected) or soft (order flagged)? Finance to clarify.
    - Does the approval threshold exist in the ERP today, or does it have to be created?
    """)
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Longlist"
    ws.append(["#", "Topic", "Wish", "Stated by", "Priority"])
    for r in [[1, "Account", "Buyer sees own order history 24 months", "key account", "must"],
              [2, "Account", "Purchasing group sees all orders of the group", "key account", "should"],
              [3, "Catalogue", "Successor product on discontinued articles", "purchasing", "could"],
              [4, "Integration", "Nightly product import from ERP", "IT", "must"],
              [5, "Integration", "Order transfer to ERP within 15 minutes", "IT", "must"],
              [6, "Performance", "Product page under 2 seconds on 3G", "head of eCommerce", "must"]]:
        ws.append(r)
    os.makedirs(os.path.join(T, "input"), exist_ok=True)
    wb.save(os.path.join(T, "input/requirements-longlist.xlsx"))


# ------------------------------------------------------------------ D1: source inventory and epic structure
def inventory():
    w("analysis/inventory/source_inventory.md", INVENTORY.replace("{SOURCES}", "\n    ".join(SOURCES)).replace("{EPICS}", "\n    ".join(EPICS)))


SOURCES = [
    t("| SRC-001 | 2026-04-15-workshop-notes | Workshop-Protokoll | 2026-04-15 | Workshop 1, Umfang und Prozesse | good | Konten, Katalog und Preise, Checkout, ERP-Anbindung, zwei nichtfunktionale Ziele, die Entscheidung gegen Marktplätze (#L1-#L41) | die einzige Quelle, die Ausschlüsse nennt |",
      "| SRC-001 | 2026-04-15-workshop-notes | workshop notes | 2026-04-15 | workshop 1, scope and processes | good | accounts, catalogue and prices, checkout, ERP integration, two non-functional targets, the out-of-scope decision on marketplaces (#L1-#L41) | the only source that states exclusions |"),
    t("| SRC-002 | 2026-04-22-workshop-checkout | Workshop-Protokoll | 2026-04-22 | Workshop 2, Checkout im Detail | good | Warenkorb, Checkout-Schritte, Zahlungsbedingungen und Kreditlimit, Freigaben, Bestätigungsmails (#L1-#L41) | widerspricht SRC-001 bei der Bonitätsprüfung |",
      "| SRC-002 | 2026-04-22-workshop-checkout | workshop notes | 2026-04-22 | workshop 2, checkout deep dive | good | cart, checkout steps, payment terms and credit limit, approvals, confirmation mails (#L1-#L41) | contradicts SRC-001 on the credit limit check |"),
    t("| SRC-003 | requirements-longlist | Tabelle | 2026-04-16 | Longlist des Kunden, Einkauf und Key Accounts | good | sechs Wünsche mit einer Spalte für die Priorität, wiederholt Workshop 1 (#Longlist!R2-#Longlist!R7) | die einzige Quelle mit genannten Prioritäten |",
      "| SRC-003 | requirements-longlist | spreadsheet | 2026-04-16 | client longlist, purchasing and key accounts | good | six wishes with a priority column, repeating workshop 1 (#Longlist!R2-#Longlist!R7) | the only source with stated priorities |"),
]
EPICS = [
    t("| checkout | Warenkorb und Checkout | functional | Dauerhafte und benannte Warenkörbe, CSV-Upload, die vier Checkout-Schritte, Bestellnummer des Kunden, Anzeige der Zahlungsbedingungen, Freigaben und Bestätigungsmails. Beruht auf vielen Stellen des Checkout-Workshops und einigen aus Workshop 1. | SRC-001; SRC-002 | 6 | | active | das Epic mit der stärksten Quellenbasis |",
      "| checkout | Cart and checkout | functional | Cart persistence, named carts, CSV upload, the four checkout steps, purchase order number, payment terms display, approvals and confirmation mails. Rests on 14 passages of the checkout workshop and 4 of workshop 1. | SRC-001; SRC-002 | 6 | | active | the epic with the strongest source base |"),
    t("| account | Konten und Bestellhistorie | functional | Firmenkonten mit mehreren Einkäufern, Einkaufsgruppen und ihre Sichtbarkeitsregeln, Registrierung nur auf Einladung, Bestellhistorie über 24 Monate. | SRC-001; SRC-003 | 4 | | active | |",
      "| account | Accounts and order history | functional | Company accounts with several buyers, purchasing groups and their visibility rules, invitation-based registration, order history for 24 months. | SRC-001; SRC-003 | 4 | | active | |"),
    t("| erp-integration | ERP-Anbindung | technical | Das ERP als führendes System für Kunden, Produkte, Preise, Bestände und Bestellungen; nächtlicher Produktimport, Bestellübergabe über die bestehende Middleware innerhalb von 15 Minuten, Abfrage von Kreditlimit und Freigabeschwelle. | SRC-001; SRC-002; SRC-003 | 5 | checkout; account | active | es wurde keine Schnittstellenliste übergeben |",
      "| erp-integration | ERP integration | technical | The ERP as leading system for customers, products, prices, stock and orders; nightly product import, order transfer through the existing middleware within 15 minutes, credit limit and approval threshold lookups. | SRC-001; SRC-002; SRC-003 | 5 | checkout; account | active | no interface list was handed over |"),
    t("| performance | Leistung und Verfügbarkeit | nfr | Messbare Ziele für die Lage in der Werkstatt: Ladezeit der Produktseite bei schlechter Verbindung, Erwartung an die Verfügbarkeit. | SRC-001 | 2 | | active | für die Verfügbarkeit nennt keine Quelle eine Zahl |",
      "| performance | Performance and availability | nfr | Measurable targets for the shop floor situation: product page render time on a poor connection, availability expectation. | SRC-001 | 2 | | active | availability has no number in any source |"),
    t("| marketplace | Verkauf über Marktplätze | functional | Verkauf über Marktplätze, vom Vertrieb in Workshop 1 eingebracht und von der Leitung eCommerce für dieses Projekt ausgeschlossen. | SRC-001 | 0 | | out-of-scope | ausgeschlossen bei SRC-001#L41 |",
      "| marketplace | Marketplace selling | functional | Selling through marketplaces, raised by sales in workshop 1 and ruled out for this project by the head of eCommerce. | SRC-001 | 0 | | out-of-scope | excluded at SRC-001#L41 |"),
]
INVENTORY = """\
    # Source inventory and epic structure (D1)
    - **status:** final
    - **round:** 1

    ## Corpus notes

    Three sources carry this requirement set: the notes of the scope workshop, the notes of the
    checkout workshop and the client's own wish longlist. All three yielded complete text, so every
    requirement can be traced to a passage. The two workshops overlap on checkout and payment and
    contradict each other on the credit limit check. The longlist repeats wishes of workshop 1 and adds
    a priority column, which is the only place priorities are stated at all. No architecture picture, no
    interface list and no data model were handed over: the technical epic rests on the prose of the two
    workshops, which is why its requirements are fewer and less precise than the functional ones.

    ## Sources

    | id | title | type | date | origin | quality | covers | notes |
    |---|---|---|---|---|---|---|---|
    {SOURCES}

    ## Epics

    | name | title | kind | description | sources | estimated_requirements | depends_on | activation | notes |
    |---|---|---|---|---|---|---|---|---|
    {EPICS}

    ## Coverage

    - **sources_total:** 3
    - **sources_unextractable:** 0
    - **sources_not_requirements_relevant:** 0
    - **epics_functional:** 3
    - **epics_technical:** 1
    - **epics_nfr:** 1
    - **estimated_requirements_total:** 17
    - **counting_rule:** every SRC id of corpus/index.json counts once at its current revision; the epic estimate counts source passages that carry a distinct capability, not sentences; the marketplace epic is counted as an epic but with 0 expected requirements because it is out of scope
    - **gaps:** no source states an availability target, a roll-out order of the four countries, ownership of product texts after the planned PIM, or any authorisation or data-protection requirement; all four are client questions, none of them is inferred into a requirement
    - **evidence:** corpus/index.json; SRC-001#L1; SRC-002#L1; SRC-003#Longlist!R2

    ## Claims

    | id | type | statement | evidence | target | supersedes | history |
    |---|---|---|---|---|---|---|
    | C-D1-001 | fact | The requirement set rests on three sources: two workshop protocols and one client longlist, all with fully extractable text. | corpus/index.json; SRC-001#L1; SRC-002#L1; SRC-003#Longlist!R2 | D1/Sources | | |
    | C-D1-002 | fact | Priorities are stated in exactly one source, the client longlist; the workshop protocols state a priority only for payment on account and the contract prices. | SRC-003#Longlist!R2; SRC-001#L1 | D1/Sources:SRC-003 | | |
    | C-D1-003 | assessment | The material carries five epics, of which the checkout epic has the strongest base and the technical ERP epic the weakest, because no architecture picture or interface list was handed over. | SRC-002#L1; SRC-001#L41 | D1/Epics | | |
    | C-D1-004 | fact | Marketplace selling is out of scope for this project by decision of the head of eCommerce. | SRC-001#L41 | D1/Epics:marketplace | | |
    | C-D1-005 | assessment | Four topics a requirement set for an eCommerce platform normally covers are absent from the material: availability targets, roll-out order of the countries, ownership of product texts, and authorisation and data protection. | SRC-001#L41; corpus/index.json | D1/Coverage | | |
    | C-D1-006 | fact | The indexed material offers 156 citable anchors across the three sources, so a requirement can point at a line block, a spreadsheet row or a page rather than at a document as a whole. | corpus/index.json | D1/Sources | | |
    """


# ------------------------------------------------------------------ D2: one epic analysis
def epic():
    w("analysis/scopes/checkout.md", EPIC.replace("{CONTRA}", CONTRA))


CONTRA = t("| Bonitätsprüfung vor Annahme der Bestellung | SRC-001#L1 | SRC-002#L1 | Der Umfangs-Workshop beschreibt Kauf auf Rechnung als einzige Zahlungsart ohne jede Limitprüfung; der Checkout-Workshop hält fest, dass die Finanzabteilung eine Bonitätsprüfung gegen das ERP für den Go-live verlangt. | Dem Checkout-Workshop folgen, weil die Finanzabteilung die Zahlungsbedingungen verantwortet, und mit dem Kunden klären, ob die Prüfung die Bestellung abweist oder nur markiert. |",
           "| credit limit check before order acceptance | SRC-001#L1 | SRC-002#L1 | The scope workshop describes payment on account as the only payment method without any limit check; the checkout workshop records finance calling a credit limit check against the ERP mandatory for go-live. | Follow the checkout workshop, because finance owns the payment terms, and confirm with the client whether the check rejects or only flags the order. |")
EPIC = """\
    # Epic requirements: checkout
    - **epic:** checkout
    - **status:** final
    - **round:** 1

    ## Summary

    The checkout epic covers the cart, the four checkout steps, the purchase order number, the display of
    payment terms, the approval of large orders and the confirmation mails. It rests on the checkout
    workshop of 2026-04-22 and on the checkout section of the scope workshop of 2026-04-15. The base is
    strong: every row below cites a passage, and only the cart approval flow needed an inference. The two
    workshops contradict each other on the credit limit check, which is recorded as a contradiction and as a
    question to the client rather than decided here.

    ## Requirements

    | req_id | type | title | description | source_locators | priority | release | acceptance_hint | catalogue_ref | confidence | open_question |
    |---|---|---|---|---|---|---|---|---|---|---|
    | FR-CO-001 | functional | Persistent named carts | The shop keeps a buyer's cart beyond the session and lets a buyer hold several carts under names they choose. | SRC-002#L1 | must | MVP | a cart created on one day can be opened and ordered two days later under its name | | high | |
    | FR-CO-002 | functional | CSV upload into the cart | A buyer can upload a CSV of article numbers and quantities into a cart. | SRC-002#L1 | must | MVP | a CSV of 20 article numbers produces a cart with 20 positions and a report of the lines that could not be matched | | high | |
    | FR-CO-003 | functional | Purchase order number is mandatory | The shop requires a purchase order number before an order can be confirmed, in every sales country. | SRC-001#L1; SRC-002#L1 | must | MVP | an order cannot be confirmed while the purchase order number is empty | | high | |
    | FR-CO-004 | functional | Payment terms shown before confirming | The review step shows the payment terms that apply to the buyer's company. | SRC-002#L1 | must | MVP | the review step shows the payment terms the ERP holds for that company | | high | |
    | FR-CO-005 | functional | Approval of orders above a threshold | An order above the company's threshold is released only after a second buyer of the same purchasing group has approved it. | SRC-002#L1 | must | MVP | an order above the threshold stays unreleased until a second buyer of the group approves it | | medium | Q-checkout-2 |
    | FR-CO-006 | functional | Order confirmation mails | The buyer receives a confirmation mail when the order is placed and a second mail when the ERP has accepted it; both carry the purchase order number. | SRC-002#L1 | must | MVP | both mails arrive and both show the purchase order number | | high | |
    | TR-CO-001 | technical | Approval state is kept outside the cart | The approval state of an order awaiting a second buyer survives a restart of the shop and is visible to both buyers. | inferred | unknown | | a pending approval is still pending after a deployment | | low | Q-checkout-3 |

    ## Contradictions

    | topic | source_a | source_b | what_differs | proposed_resolution |
    |---|---|---|---|---|
    {CONTRA}

    ## Open questions

    | id | to | question | why_needed | status | answer |
    |---|---|---|---|---|---|
    | Q-checkout-1 | client | Does the credit limit check reject an order or only flag it for finance? | decides whether the check becomes a blocking step of the checkout or a follow-up process, and whether FR-CO-004 needs a second outcome | open | |
    | Q-checkout-2 | client | Does the approval threshold exist in the ERP today, or does it have to be created there? | decides whether FR-CO-005 is a lookup or a new data field in the ERP | open | |
    | Q-checkout-3 | client | Where should a pending approval be stored so both buyers see it after a deployment? | TR-CO-001 is inferred; the answer replaces the inference with a stated requirement | open | |

    ## Claims

    | id | type | statement | evidence | target | supersedes | history |
    |---|---|---|---|---|---|---|
    | C-checkout-001 | fact | The checkout consists of four steps in this order: delivery address from the ERP addresses, requested delivery date, purchase order number, review and confirm. | SRC-002#L1 | D2/Requirements:FR-CO-003 | | |
    | C-checkout-002 | fact | The purchase order number is mandatory in every sales country and is stated in both workshops. | SRC-001#L1; SRC-002#L1 | D2/Requirements:FR-CO-003 | | |
    | C-checkout-003 | assessment | The two workshops contradict each other on the credit limit check: the scope workshop names no check, the checkout workshop records it as mandatory for go-live. | SRC-001#L1; SRC-002#L1 | D2/Contradictions | | |
    | C-checkout-004 | assessment | TR-CO-001 is inferred, not stated: no source says where a pending approval is kept, and the requirement follows from the approval flow of the checkout workshop plus the fact that two buyers must see the same pending order. | SRC-002#L1 | D2/Requirements:TR-CO-001 | | |
    """


# ------------------------------------------------------------------ score files (passing) for checkout, D1, SET
SCORES = {
    "checkout": [("C-checkout-001", 9, 8), ("C-checkout-002", 8, 8), ("C-checkout-003", 9, 9), ("C-checkout-004", 9, 10)],
    "D1": [("C-D1-001", 8, 8), ("C-D1-002", 9, 8), ("C-D1-003", 8, 9), ("C-D1-004", 9, 8), ("C-D1-005", 8, 10), ("C-D1-006", 8, 8)],
    "SET": [("C-SET-001", 9, 8), ("C-SET-002", 8, 9), ("C-SET-003", 9, 9), ("C-SET-004", 8, 8)],
}
MISSING = {
    "checkout": ("- No requirement covers what happens to a cart whose article numbers were discontinued between building and ordering",
                 "- [standard-fact] No requirement covers guest or punchout entry into the checkout, which a B2B shop of this type normally needs"),
    "D1": ("- No source inventory row says which of the two workshops is authoritative where they overlap",
           "- [standard-fact] The epic list has no epic for authorisation and roles, which every eCommerce requirement set needs"),
    "SET": ("- The set has no requirement for the stock traffic light, although workshop 1 states it",
            "- [inference-requires-client-evidence] The catalogue gap list rests on best practice only because no reference catalogue is configured"),
}
ESTATE = {
    "checkout": "- The client longlist SRC-003 repeats two checkout wishes of workshop 1 with a priority column, which the account epic also uses",
    "D1": "- SRC-003 is the only source with a priority column, so every priority outside it is `unknown` by construction",
    "SET": "- The performance epic will stay at one requirement because no source states an availability number",
}


def score_files():
    for scope, rows in SCORES.items():
        for ci, critic in enumerate(("client", "standard")):
            body = [f"| {cid} | {v} | {'insightful' if v >= 9 else 'confirmed'} | | | |" for cid, c, s in rows for v in [c if critic == "client" else s]]
            txt = ["# Gauntlet score: " + scope + " / " + critic + " / round 1", f"- **scope:** {scope}", f"- **critic:** {critic}", "- **round:** 1", "",
                   "## Scores", "", "| claim_id | score | verdict | issue | counter_evidence | fix_hint |", "|---|---|---|---|---|---|"] + body + [
                   "", "## Missing claims", "", MISSING[scope][ci],
                   "", "## Estate observations", "", ESTATE[scope],
                   "", "## Summary", "",
                   f"Every locator resolves and says what the statement says. Scope {scope}, round 1, nothing contradicted by evidence.", ""]
            w(f"analysis/gauntlet/{scope}/round1-{critic}.md", "\n".join(txt))


# ------------------------------------------------------------------ SET: the consolidated set
def consolidated():
    w("analysis/consolidated/SET.md", SET.replace("{REQS}", "\n    ".join(t(REQS_DE, REQS_EN))).replace("{CROSS}", "\n    ".join(t(CROSS_DE, CROSS_EN))).replace("{GAPS}", t(GAP_DE, GAP_EN)).replace("{SYSTEM}", SYSTEM))


REQS_EN = ["| FR-001 | account | functional | Company accounts with several buyers | A company account holds several buyers, and a buyer sees another buyer's orders only inside the same purchasing group. | SRC-001#L1; SRC-003#Longlist!R3 | should | MVP | a buyer of another purchasing group cannot open the order | | | confirmed |", '| FR-002 | account | functional | Invitation-based registration | Sales creates the company account and the buyer receives an invitation mail; there is no self-service registration. | SRC-001#L1 | must | MVP | no public registration form exists and an invited buyer can set a password | | | confirmed |',
    '| FR-003 | account | functional | Order history for 24 months | A buyer can see their own orders of the last 24 months. | SRC-001#L1; SRC-003#Longlist!R2 | must | MVP | an order placed 23 months ago is listed | | | confirmed |', "| FR-004 | checkout | functional | Persistent named carts | The shop keeps a buyer's cart beyond the session and lets a buyer hold several carts under names they choose. | SRC-002#L1 | must | MVP | a cart created on one day can be opened and ordered two days later under its name | | FR-CO-001 | confirmed |", '| FR-005 | checkout | functional | CSV upload into the cart | A buyer can upload a CSV of article numbers and quantities into a cart. | SRC-002#L1 | must | MVP | a CSV of 20 article numbers produces a cart with 20 positions and a report of the unmatched lines | | FR-CO-002 | confirmed |',
    '| FR-006 | checkout | functional | Purchase order number is mandatory | The shop requires a purchase order number before an order can be confirmed, in every sales country. | SRC-001#L1; SRC-002#L1 | must | MVP | an order cannot be confirmed while the purchase order number is empty | | FR-CO-003 | confirmed |', "| FR-007 | checkout | functional | Payment terms shown before confirming | The review step shows the payment terms that apply to the buyer's company. | SRC-002#L1 | must | MVP | the review step shows the payment terms the ERP holds for that company | | FR-CO-004 | confirmed |", "| FR-008 | checkout | functional | Approval of orders above a threshold | An order above the company's threshold is released only after a second buyer of the same purchasing group has approved it. | SRC-002#L1 | must | MVP | an order above the threshold stays unreleased until a second buyer of the group approves it | | FR-CO-005 | question |", '| FR-009 | checkout | functional | Order confirmation mails | The buyer receives a confirmation mail when the order is placed and a second mail when the ERP has accepted it; both carry the purchase order number. | SRC-002#L1 | must | MVP | both mails arrive and both show the purchase order number | | FR-CO-006 | confirmed |',
    '| TR-001 | erp-integration | technical | Order transfer to the ERP within 15 minutes | A confirmed order reaches the ERP through the existing middleware at most 15 minutes after the buyer confirmed it. | SRC-001#L1; SRC-003#Longlist!R6 | must | MVP | an order confirmed at 10:00 is in the ERP by 10:15 | | | confirmed |',
    '| TR-002 | erp-integration | technical | Nightly product import from the ERP | Product data is imported from the ERP once per night. | SRC-001#L1; SRC-003#Longlist!R5 | must | MVP | a product changed in the ERP during the day is current in the shop the next morning | | | confirmed |',
    '| TR-003 | erp-integration | technical | Price and payment term lookup in the ERP | The shop takes customer prices and payment terms from the ERP and never calculates a price itself. | SRC-001#L1; SRC-002#L1 | must | MVP | a price shown in the shop equals the price the ERP returns for that customer and article | | | confirmed |',
    '| TR-004 | erp-integration | technical | Approval state kept outside the cart | The approval state of an order awaiting a second buyer survives a restart of the shop and is visible to both buyers. | inferred | unknown | | a pending approval is still pending after a deployment | | TR-CO-001 | inferred |',
    '| NFR-001 | performance | nfr | Product page under two seconds on 3G | A product page renders in under two seconds on a 3G connection. | SRC-001#L41; SRC-003#Longlist!R7 | must | MVP | a product page measured on a throttled 3G connection renders in under two seconds | | | confirmed |']
REQS_DE = ['| FR-001 | account | functional | Firmenkonten mit mehreren Einkäufern | Ein Firmenkonto umfasst mehrere Einkäufer, und ein Einkäufer sieht Bestellungen anderer Einkäufer nur innerhalb derselben Einkaufsgruppe. | SRC-001#L1; SRC-003#Longlist!R3 | should | MVP | ein Einkäufer einer anderen Einkaufsgruppe kann die Bestellung nicht öffnen |  |  | confirmed |',
    '| FR-002 | account | functional | Registrierung nur auf Einladung | Der Vertrieb legt das Firmenkonto an, und der Einkäufer erhält eine Einladungsmail; eine Selbstregistrierung gibt es nicht. | SRC-001#L1 | must | MVP | es gibt kein öffentliches Registrierungsformular, und ein eingeladener Einkäufer kann ein Passwort setzen |  |  | confirmed |',
    '| FR-003 | account | functional | Bestellhistorie über 24 Monate | Ein Einkäufer sieht seine eigenen Bestellungen der letzten 24 Monate. | SRC-001#L1; SRC-003#Longlist!R2 | must | MVP | eine vor 23 Monaten aufgegebene Bestellung wird angezeigt |  |  | confirmed |',
    '| FR-004 | checkout | functional | Dauerhafte benannte Warenkörbe | Der Shop behält den Warenkorb eines Einkäufers über die Sitzung hinaus, und ein Einkäufer kann mehrere Warenkörbe unter selbst gewählten Namen führen. | SRC-002#L1 | must | MVP | ein an einem Tag angelegter Warenkorb lässt sich zwei Tage später unter seinem Namen öffnen und bestellen |  | FR-CO-001 | confirmed |',
    '| FR-005 | checkout | functional | CSV-Upload in den Warenkorb | Ein Einkäufer kann eine CSV-Datei mit Artikelnummern und Mengen in einen Warenkorb hochladen. | SRC-002#L1 | must | MVP | eine CSV-Datei mit 20 Artikelnummern ergibt einen Warenkorb mit 20 Positionen und eine Liste der nicht zugeordneten Zeilen |  | FR-CO-002 | confirmed |',
    '| FR-006 | checkout | functional | Bestellnummer des Kunden ist Pflicht | Der Shop verlangt eine Bestellnummer des Kunden, bevor eine Bestellung bestätigt werden kann, und zwar in jedem Vertriebsland. | SRC-001#L1; SRC-002#L1 | must | MVP | eine Bestellung lässt sich nicht bestätigen, solange die Bestellnummer fehlt |  | FR-CO-003 | confirmed |',
    '| FR-007 | checkout | functional | Zahlungsbedingungen vor der Bestätigung | Der Prüfschritt zeigt die Zahlungsbedingungen, die für die Firma des Einkäufers gelten. | SRC-002#L1 | must | MVP | der Prüfschritt zeigt die Zahlungsbedingungen, die das ERP für diese Firma führt |  | FR-CO-004 | confirmed |',
    '| FR-008 | checkout | functional | Freigabe von Bestellungen über einer Schwelle | Eine Bestellung über der Schwelle der Firma wird erst freigegeben, wenn ein zweiter Einkäufer derselben Einkaufsgruppe sie genehmigt hat. | SRC-002#L1 | must | MVP | eine Bestellung über der Schwelle bleibt gesperrt, bis ein zweiter Einkäufer der Gruppe sie genehmigt |  | FR-CO-005 | question |',
    '| FR-009 | checkout | functional | Bestätigungsmails zur Bestellung | Der Einkäufer erhält eine Bestätigungsmail, wenn die Bestellung aufgegeben ist, und eine zweite, wenn das ERP sie angenommen hat; beide tragen die Bestellnummer des Kunden. | SRC-002#L1 | must | MVP | beide Mails kommen an, und beide zeigen die Bestellnummer des Kunden |  | FR-CO-006 | confirmed |',
    '| TR-001 | erp-integration | technical | Bestellübergabe an das ERP in 15 Minuten | Eine bestätigte Bestellung erreicht das ERP über die bestehende Middleware spätestens 15 Minuten nach der Bestätigung durch den Einkäufer. | SRC-001#L1; SRC-003#Longlist!R6 | must | MVP | eine um 10:00 bestätigte Bestellung ist um 10:15 im ERP |  |  | confirmed |',
    '| TR-002 | erp-integration | technical | Nächtlicher Produktimport aus dem ERP | Produktdaten werden einmal pro Nacht aus dem ERP importiert. | SRC-001#L1; SRC-003#Longlist!R5 | must | MVP | ein tagsüber im ERP geändertes Produkt ist am nächsten Morgen im Shop aktuell |  |  | confirmed |',
    '| TR-003 | erp-integration | technical | Preise und Zahlungsbedingungen aus dem ERP | Der Shop übernimmt Kundenpreise und Zahlungsbedingungen aus dem ERP und berechnet nie selbst einen Preis. | SRC-001#L1; SRC-002#L1 | must | MVP | ein im Shop gezeigter Preis entspricht dem Preis, den das ERP für diesen Kunden und Artikel liefert |  |  | confirmed |',
    '| TR-004 | erp-integration | technical | Freigabestatus außerhalb des Warenkorbs | Der Freigabestatus einer Bestellung, die auf einen zweiten Einkäufer wartet, übersteht einen Neustart des Shops und ist für beide Einkäufer sichtbar. | inferred | unknown |  | eine offene Freigabe ist nach einem Deployment weiterhin offen |  | TR-CO-001 | inferred |',
    '| NFR-001 | performance | nfr | Produktseite unter zwei Sekunden bei 3G | Eine Produktseite lädt bei einer 3G-Verbindung in weniger als zwei Sekunden. | SRC-001#L41; SRC-003#Longlist!R7 | must | MVP | eine Produktseite, gemessen bei gedrosselter 3G-Verbindung, lädt in weniger als zwei Sekunden |  |  | confirmed |']
CROSS_EN = ['| FR-003 | TR-003 | has-tr | the order history reads orders the ERP owns, covered by the ERP lookup requirement |',
    '| FR-007 | TR-003 | has-tr | the payment terms shown in the review step come from the ERP |',
    '| FR-008 | TR-004 | has-tr | the approval flow needs the approval state requirement, which is inferred and carries a client question |',
    '| FR-009 | | missing-tr | both confirmation mails depend on an acceptance signal from the ERP and no requirement describes that inbound signal; raised as a client question rather than invented as a requirement |',
    '| FR-005 | | missing-tr | the CSV upload matches article numbers against the ERP article master and no requirement covers that lookup; raised as a client question |',
    '| none | TR-002 | orphan-tr | the nightly product import serves no functional requirement of this set: the catalogue epic was not part of the material, so the import is an undocumented driver stated by IT, not an invented requirement |']
CROSS_DE = ['| FR-003 | TR-003 | has-tr | die Bestellhistorie liest Bestellungen, die das ERP führt; das deckt die Anforderung zur ERP-Abfrage ab |',
    '| FR-007 | TR-003 | has-tr | die im Prüfschritt gezeigten Zahlungsbedingungen kommen aus dem ERP |',
    '| FR-008 | TR-004 | has-tr | der Freigabeablauf braucht die Anforderung zum Freigabestatus, die abgeleitet ist und an einer Annahme hängt |',
    '| FR-009 |  | missing-tr | beide Bestätigungsmails hängen an einem Annahmesignal des ERP, und keine Anforderung beschreibt dieses eingehende Signal; es steht als offene Frage an den Kunden statt als erfundene Anforderung |',
    '| FR-005 |  | missing-tr | der CSV-Upload gleicht Artikelnummern mit dem Artikelstamm des ERP ab, und keine Anforderung deckt diese Abfrage ab; es steht als offene Frage an den Kunden |',
    '| none | TR-002 | orphan-tr | der nächtliche Produktimport dient keiner fachlichen Anforderung dieses Satzes: das Katalog-Epic war nicht Teil des Materials, der Import ist also ein von der IT genannter Treiber und keine erfundene Anforderung |']
GAP_EN = '| none | No reference catalogue is configured for this run, so the completeness check rests on requirements best practice only and no catalogue ids can be named. | | question |'
GAP_DE = '| none | Für diesen Lauf ist kein Referenzkatalog hinterlegt; die Prüfung auf Vollständigkeit beruht deshalb nur auf bewährter Praxis für Anforderungen, und es lassen sich keine Katalogeinträge nennen. |  | question |'
SET = """\
    # Consolidated requirements set (SET)
    - **status:** final
    - **round:** 1
    - **system_type:** {SYSTEM}

    ## Requirements

    | req_id | epic | type | title | description | source_locators | priority | release | acceptance_hint | catalogue_ref | duplicates_of | status |
    |---|---|---|---|---|---|---|---|---|---|---|---|
    {REQS}

    ## Crosscheck

    | functional_requirement | technical_requirement | relation | note |
    |---|---|---|---|
    {CROSS}

    ## Catalogue gaps

    | catalogue_id | capability | covered_by | decision |
    |---|---|---|---|
    {GAPS}

    ## Open questions

    | id | to | question | why_needed | status | answer |
    |---|---|---|---|---|---|
    | Q-SET-1 | client | Does the credit limit check reject an order or only flag it for finance? | decides whether the check is a blocking checkout step and whether FR-007 needs a second outcome | open | |
    | Q-SET-2 | client | Does the approval threshold exist in the ERP today, or does it have to be created there? | decides whether FR-008 is a lookup or a new ERP data field | open | |
    | Q-SET-3 | client | Which inbound signal tells the shop that the ERP has accepted an order? | FR-009 promises a second mail and no requirement covers the signal that triggers it | open | |
    | Q-SET-4 | client | Which availability target applies to the shop? | workshop 1 says "the same as the ERP" without a number, so no non-functional requirement can be written | open | |
    | Q-SET-5 | client | Where should a pending approval be stored so both buyers see it after a deployment? | TR-004 is inferred; the answer replaces the inference with a stated requirement | open | |

    ## Claims

    | id | type | statement | evidence | target | supersedes | history |
    |---|---|---|---|---|---|---|
    | C-SET-001 | fact | The set holds 14 requirements: 9 functional, 4 technical and 1 non-functional, of which 13 cite at least one passage of the client's material and one is inferred. | analysis/scopes/checkout.md; SRC-001#L1; SRC-002#L1 | D2/Requirements | | |
    | C-SET-002 | assessment | Two functional requirements promise behaviour that depends on an ERP interface no requirement describes: the second confirmation mail and the CSV article matching. | SRC-002#L1; SRC-001#L1 | D2/Crosscheck:FR-009 | | |
    | C-SET-003 | assessment | The nightly product import is the only requirement in the set that no functional requirement needs, because the catalogue was never worked through in a workshop. | SRC-001#L1; SRC-003#Longlist!R5 | D2/Crosscheck | | |
    | C-SET-004 | assessment | Priorities outside the client longlist are unstated by construction: only two of the fourteen requirements carry a priority that a workshop protocol states in words. | SRC-003#Longlist!R2; SRC-001#L1 | D2/Requirements | | |
    """


def gate_and_summaries():
    w("analysis/gate/round1-product_owner.md", """\
    # Final gate: product_owner / round 1
    - **persona:** product_owner
    - **round:** 1

    ## Key questions

    | question_id | score | where | answer | rationale |
    |---|---|---|---|---|
    | K1 | 8 | Management_Summary!A5 | answered on the summary with its figure | the basis is visible in each row |
    | K2 | 7 | Management_Summary!A6 | answered on the summary with its figure | only by combining two sheets |
    | K3 | 8 | Management_Summary!A7 | answered on the summary with its figure | the basis is visible in each row |
    | K4 | 9 | Management_Summary!A8 | answered on the summary with its figure | the basis is visible in each row |

    ## Board test

    - **forward_unchanged:** no
    - **blocking_items:** I1

    ## What is missing

    - a view by release

    ## Issues

    | id | deliverable | location | issue | kind | severity | question_id | proposed_change |
    |---|---|---|---|---|---|---|---|
    | I1 | D2 | Crosscheck!D5 | a missing technical requirement is described but the note does not say who has to answer it | content | major | K2 | name the open question id in the note |

    ## Summary

    The set is usable as an input for a platform decision: every row can be followed to a passage.
    """)
    w("analysis/summaries/D1.md", t("""\
    Drei Quellen tragen diesen Anforderungssatz, alle vollständig lesbar: das Protokoll des Umfangs-Workshops, das Protokoll des Checkout-Workshops und die eigene Wunschliste des Kunden. Jede Anforderung lässt sich deshalb bis zu einer Seite, einem Zeilenblock oder einer Tabellenzeile verfolgen.

    Das Material trägt mehrere Epics. Das Checkout-Epic hat die stärkste Basis; das Epic zur ERP-Anbindung beruht nur auf Fließtext, weil kein Architekturbild und keine Schnittstellenliste übergeben wurden. Der Verkauf über Marktplätze ist nach Entscheidung der Leitung eCommerce nicht im Umfang. Themen, die ein Anforderungssatz für eine E-Commerce-Plattform üblicherweise abdeckt, fehlen im Material und stehen als Fragen an den Kunden statt als Annahmen.
    """, """\
    Three sources carry this requirement set, all of them fully readable: the notes of the scope workshop, the notes of the checkout workshop and the client's own wish longlist. Every requirement in D2 can therefore be followed to a page, a line block or a spreadsheet row.

    The material carries five epics. The checkout epic has the strongest base; the ERP integration epic rests on prose only, because no architecture picture or interface list was handed over. Marketplace selling is out of scope by decision of the head of eCommerce. Four topics an eCommerce requirement set normally covers are absent from the material and are listed as questions rather than filled in by assumption.
    """))
    w("analysis/summaries/D2.md", t("""\
    Der Anforderungssatz umfasst {kpi:requirements} Anforderungen an die E-Commerce-Plattform: {kpi:functional} fachliche, {kpi:technical} technische und eine nichtfunktionale. Bis auf eine nennen alle mindestens eine Stelle im eigenen Material des Kunden; die eine ist als abgeleitet gekennzeichnet und sagt, woraus sie abgeleitet ist.

    Zwei Zusagen des Satzes hängen an einer ERP-Schnittstelle, die noch keine Anforderung beschreibt, und eine technische Anforderung dient keiner fachlichen, weil der Katalog in keinem Workshop durchgearbeitet wurde. Prioritäten stehen nur dort, wo eine Quelle sie nennt: außerhalb der Longlist des Kunden haben die meisten Anforderungen keine Priorität. Mehrere Punkte brauchen eine Antwort des Kunden, bevor der Satz vollständig ist, jeweils mit der Wirkung der Antwort auf den Satz.
    """, """\
    The requirement set holds {kpi:requirements} requirements for the eCommerce platform: {kpi:functional} functional, {kpi:technical} technical and 1 non-functional. Thirteen of them cite at least one passage of the client's own material; one is marked as inferred and says what it was inferred from.

    Two promises of the set depend on an ERP interface that no requirement describes yet, and one technical requirement serves no functional requirement because the catalogue was never worked through in a workshop. Priorities are stated only where a source states them: outside the client longlist, most requirements carry no priority at all. Five points need an answer from the client before the set is complete, each with the effect its answer has on the set.
    """))


if __name__ == "__main__":
    fill_run()
    inputs()
    inventory()
    epic()
    score_files()
    consolidated()
    gate_and_summaries()
    print("fixture requirements written to", T)
