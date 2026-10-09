#!/usr/bin/env python3
"""Write toy engagement content into an initialised RUN folder (single-run project) so the whole ea-landscape chain can be smoke-tested.

Usage: python3 methods/ea-landscape/fixtures/make_fixture.py <run_dir>

Creates: filled run.json (client fields + landscape.focus / strategy.*), a small client corpus in input/ (an IT landscape
description naming four systems with their interfaces, a strategy note, and a system list as .xlsx), a complete sample
landscape inventory, one system analysis with both reviewer files, sample FLOWS and TARGET consolidations, a gate file and
the four management summaries. `dbcx corpus index` turns the input/ files into SRC-001 (landscape), SRC-002 (strategy),
SRC-003 (system list) - the locators used below rely on that order.
"""
import os, sys, json

T = os.path.abspath(sys.argv[1])


def w(p, s):
    p = os.path.join(T, p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)


def J(p):
    return json.load(open(os.path.join(T, p), encoding="utf-8"))


def W(p, d):
    json.dump(d, open(os.path.join(T, p), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def t(de, en):
    """client-facing fixture text in the run's deliverable language (the hygiene lint flags a sentence in the wrong language)"""
    return de if J("run.json").get("languages", {}).get("deliverable") == "de" else en


# ------------------------------------------------------------------ run.json
def fill_run():
    p = J("run.json")
    p["engagement"].update({"consultancy": "Fixture Consulting", "client": "Fixture Industries AG",
                            "client_context": "B2B manufacturer of pumps, 40 markets, sells through a shop and a field-sales organisation.",
                            "title": "Enterprise architecture fixture"})
    p["landscape"] = {**p.get("landscape", {}), "focus": "the CX architecture: commerce, product data, customer data and order flow between ERP, PIM, shop and CRM"}
    p["strategy"] = {**p.get("strategy", {}), "vision": "One customer record for sales and service, self-service ordering for all 40 markets, and product data maintained once.",
                     "horizon": "18 months in two phases"}
    W("run.json", p)


# ------------------------------------------------------------------ input/ - the client's documents
LANDSCAPE = """# IT landscape description (internal, architecture board)

Version 1.4, dated 2024-04-18, written by the architecture board for the CX programme.

## Scope

This document describes the systems that carry order intake and product information for
the pump business. It does not cover finance consolidation or the plant systems.

## Systems in operation

The ERP is SAP S/4HANA 2022, hosted in a private cloud and operated by central IT.
It holds customers, prices and stock and is the system of record for material master data.

The product information system is Akeneo PIM 6.0, a SaaS subscription owned by the
product marketing department. All product attributes and media references are maintained
there and published to the shop.

The customer-facing shop is SAP Commerce Cloud 2205, operated by the digital unit on
CCv2. It is the entry point for self-service ordering. Order documents are created here
and transferred to the ERP.

The CRM is Salesforce Sales Cloud, owned by the sales organisation. Field sales maintain
the customer record there, including contacts and visit reports.

A legacy customer portal (in-house, Java, 2011) is still running for three markets and
will be switched off once those markets are migrated to the shop.

## Interfaces

Prices and stock are transferred from the ERP to the shop every night as a flat file over
SFTP. The transfer runs at 01:30 and takes up to two hours.

Product data is published from the PIM to the shop hourly as a delta export; the export
is picked up by the shop's import job.

Orders are sent from the shop to the ERP through the integration platform (SAP Cloud
Integration) as soon as the customer confirms the basket.

Customer and order data are pushed from the shop to the CRM via the CRM REST API when a
customer registers or places an order.

The architecture diagram on the following page also shows a line between the CRM and the
ERP, but no interface has ever been described for it and the integration platform holds
no scenario for it.

## Known problems

Customer data diverges between ERP and CRM. Both departments consider their own system
the leading one, and there is no agreed rule which record wins.

The nightly price transfer means the shop shows yesterday's prices during the day; sales
have complained about this repeatedly.

Three markets still run on the legacy portal, which nobody maintains any more. The
contract for its application server ends on 2025-06-30 and will not be renewed.

## Governance

The architecture board decides on new interfaces. The integration platform is the
mandated route for any new system-to-system connection; point-to-point interfaces are
tolerated only for interfaces that existed before 2022.
"""

STRATEGY = """# CX strategy note for the board

Dated 2024-05-06, written by the head of digital for the board meeting.

## Where we want to be in 18 months

We want one customer record that sales and service share. Today a field-sales colleague
and a service agent see different addresses for the same customer, and neither knows
which one is right. This has to end.

Self-service ordering has to be available in all 40 markets. Today only 37 markets are on
the shop; the remaining three are still on the old portal and cannot be extended.

Product data has to be maintained once. Every attribute that is entered twice is entered
wrongly at least once.

Prices have to be current in the shop. A price list that is a day old is not acceptable
for a business that quotes project prices.

## What we are not doing

We are not replacing the ERP in this horizon. The ERP move was finished in 2022 and the
board will not open it again.

We are not building a second shop for the remaining markets.
"""


def system_list_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Systems"
    ws.append(["System", "Product", "Version", "Owner", "Hosting", "Status"])
    ws.append(["ERP", "SAP S/4HANA", "2022", "central IT", "private cloud", "in operation"])
    ws.append(["PIM", "Akeneo PIM", "6.0", "product marketing", "SaaS", "in operation"])
    ws.append(["Shop", "SAP Commerce Cloud", "2205", "digital unit", "CCv2", "in operation"])
    ws.append(["CRM", "Salesforce Sales Cloud", "", "sales organisation", "SaaS", "in operation"])
    ws.append(["Customer portal", "in-house Java", "", "digital unit", "on-premise", "being retired"])
    os.makedirs(os.path.join(T, "input"), exist_ok=True)
    wb.save(os.path.join(T, "input", "2024-05-system-list.xlsx"))


# ------------------------------------------------------------------ analysis documents
def inventory():
    return f"""# Landscape inventory (D1)

- **status:** final
- **round:** 1

## Sources

| id | title | type | date | origin | quality | covers |
|---|---|---|---|---|---|---|
| SRC-001 | 2024-05-it-landscape | md | 2024-04-18 | {t("Architekturgremium, für das CX-Programm", "architecture board, for the CX programme")} | good | {t("Systeme, Schnittstellen, bekannte Probleme, Governance", "systems, interfaces, known problems, governance")} |
| SRC-002 | 2024-05-strategy-note | md | 2024-05-06 | {t("Leitung Digital, für die Vorstandssitzung", "head of digital, for the board meeting")} | good | {t("strategische Vision, Abgrenzungen", "strategic vision, out-of-scope statements")} |
| SRC-003 | 2024-05-system-list | xlsx | 2024-05-02 | {t("Asset-Liste der zentralen IT", "central IT asset list")} | good | {t("Produktnamen, Versionen, Verantwortung, Betrieb", "product names, versions, owners, hosting")} |

## Systems

| name | category | vendor_product | version | owner | hosting | lifecycle | relevance | description | depends_on | interfaces_mentioned | sources |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sap-erp | erp | SAP S/4HANA | 2022 | {t("zentrale IT", "central IT")} | private cloud | active | core | {t("Führt Kunden, Preise und Bestände und ist das führende System für die Materialstammdaten.", "Holds customers, prices and stock and is the system of record for material master data.")} | | 3 | SRC-001#L1; SRC-003#Systems!R2 |
| akeneo-pim | pim | Akeneo PIM | 6.0 | {t("Produktmarketing", "product marketing")} | SaaS | active | core | {t("Hier werden Produktattribute und Medienverweise gepflegt und an den Shop veröffentlicht.", "Product attributes and media references are maintained here and published to the shop.")} | | 1 | SRC-001#L1; SRC-003#Systems!R3 |
| hybris-shop | commerce | SAP Commerce Cloud | 2205 | {t("Digital-Einheit", "digital unit")} | CCv2 | active | core | {t("Shop für die Kunden und Einstieg in die Selbstbedienungsbestellung; hier entstehen die Auftragsbelege.", "Customer-facing shop and entry point for self-service ordering; order documents are created here.")} | sap-erp; akeneo-pim | 4 | SRC-001#L1; SRC-003#Systems!R4 |
| salesforce-crm | crm | Salesforce Sales Cloud | | {t("Vertriebsorganisation", "sales organisation")} | SaaS | active | peripheral | {t("Der Außendienst pflegt hier den Kundendatensatz, die Kontakte und die Besuchsberichte.", "Field sales maintain the customer record, contacts and visit reports here.")} | hybris-shop | 2 | SRC-001#L1; SRC-003#Systems!R5 |
| legacy-portal | custom | {t("Eigenentwicklung Java-Portal", "in-house Java portal")} | | {t("Digital-Einheit", "digital unit")} | on-premise | retiring | out-of-scope | {t("Kundenportal aus dem Jahr 2011, das noch drei Märkte bedient und abgeschaltet wird, sobald diese Märkte in den Shop wechseln.", "Customer portal from 2011, still serving three markets, to be switched off once those markets move to the shop.")} | | 1 | SRC-001#L1; SRC-003#Systems!R6 |

## Data objects

| name | description | claimed_master_systems | consumer_systems | sources |
|---|---|---|---|---|
| customer | {t("Firma, Adressen und Kontakte einer bestellenden Organisation.", "Company, addresses and contacts of a buying organisation.")} | sap-erp; salesforce-crm | hybris-shop | SRC-001#L1; SRC-001#L41 |
| product | {t("Produktattribute und Medienverweise.", "Product attributes and media references.")} | akeneo-pim | hybris-shop | SRC-001#L1 |
| price | {t("Kundenspezifische Preise und Listenpreise.", "Customer-specific and list prices.")} | sap-erp | hybris-shop | SRC-001#L1 |
| stock | {t("Verfügbare Menge je Werk.", "Available quantity per plant.")} | sap-erp | hybris-shop | SRC-001#L1 |
| order | {t("Auftragsbelege aus der Selbstbedienung.", "Order documents created by self-service.")} | hybris-shop | sap-erp; salesforce-crm | SRC-001#L1 |

## Strategic vision

| topic | statement | source_locators |
|---|---|---|
| {t("ein Kundendatensatz", "one customer record")} | {t("Vertrieb und Service teilen einen Kundendatensatz; heute zeigen die beiden Systeme für denselben Kunden unterschiedliche Adressen.", "Sales and service share one customer record; today the two systems show different addresses for the same customer.")} | SRC-002#L1 |
| {t("Abdeckung der Selbstbedienung", "self-service coverage")} | {t("Die Selbstbedienungsbestellung steht in allen 40 Märkten zur Verfügung; drei Märkte sind noch auf dem alten Portal.", "Self-service ordering is available in all 40 markets; three markets are still on the old portal.")} | SRC-002#L1 |
| {t("Produktdaten einmal gepflegt", "product data maintained once")} | {t("Jedes Produktattribut wird an genau einer Stelle gepflegt.", "Every product attribute is maintained in exactly one place.")} | SRC-002#L1 |
| {t("aktuelle Preise", "current prices")} | {t("Die Preise im Shop sind aktuell; eine Preisliste vom Vortag ist nicht akzeptabel.", "Prices in the shop are current; a price list that is a day old is not acceptable.")} | SRC-002#L1 |
| {t("nicht im Umfang", "out of scope")} | {t("Das ERP wird in diesem Horizont nicht abgelöst und es wird kein zweiter Shop gebaut.", "The ERP is not replaced in this horizon and no second shop is built.")} | SRC-002#L1 |

## Claims

| id | type | statement | evidence | target | supersedes | history |
|---|---|---|---|---|---|---|
| C-D1-001 | fact | The landscape in scope consists of five systems: sap-erp, akeneo-pim, hybris-shop, salesforce-crm and legacy-portal, the last of which is being retired. | SRC-001#L1; SRC-003#Systems!R2 | D1/Systems | | |
| C-D1-002 | fact | Two systems are claimed as the master of the customer record: sap-erp by central IT and salesforce-crm by the sales organisation. | SRC-001#L1; SRC-001#L41 | D1/Data_Objects:customer | | |
| C-D1-003 | fact | legacy-portal serves three markets and its application server contract ends on 2025-06-30 without renewal. | SRC-001#L41 | D1/Systems:legacy-portal | | |
| C-D1-004 | assessment | hybris-shop is the hub of the landscape: it receives product, price and stock data from akeneo-pim and sap-erp and produces the order documents every other system consumes. | SRC-001#L1 | D1/Systems:hybris-shop | | |
| C-D1-005 | assessment | The strategic vision names four outcomes that the landscape does not deliver today: one shared customer record, self-service in all 40 markets, product data maintained once and current prices in the shop. | SRC-002#L1 | D1/Strategic_Vision | | |
| C-D1-006 | fact | The integration platform is the mandated route for any new system-to-system connection; point-to-point interfaces are tolerated only where they existed before 2022. | SRC-001#L41 | D1/Systems | | |
"""


def shop():
    return f"""# System analysis: hybris-shop

- **system:** hybris-shop
- **agent:** analyst-hybris-shop
- **wave:** 2
- **status:** final
- **round:** 1

## Summary

{t("Der Shop ist der Einstieg der Kunden in die Selbstbedienungsbestellung und bedient 37 der 40 Märkte. Er erhält die Produktdaten aus dem PIM und Preise und Bestände aus dem ERP, erzeugt die Auftragsbelege und überträgt Kunden- und Auftragsdaten in das CRM. Er ist das einzige System der Landschaft, das Aufträge erzeugt; alle anderen Systeme sind Abnehmer seiner Ergebnisse.",
   "The shop is the customer-facing entry point for self-service ordering and serves 37 of the 40 markets. It receives product data from the PIM and prices and stock from the ERP, creates the order documents and pushes customer and order data into the CRM. It is the only system in the landscape that produces orders, which makes every other system a consumer of its output.")}

## Profile

- **purpose:** {t("Shop für die Kunden und Einstieg in die Selbstbedienungsbestellung", "Customer-facing shop and entry point for self-service ordering")}
- **vendor_product:** SAP Commerce Cloud
- **version:** 2205
- **owner:** {t("Digital-Einheit", "digital unit")}
- **hosting:** CCv2
- **lifecycle:** active
- **users:** {t("bestellende Organisationen in 37 Märkten, interner Vertriebsinnendienst", "buying organisations in 37 markets, internal sales support")}
- **sources:** SRC-001#L1; SRC-003#Systems!R4

## Interfaces

| id | counterpart | direction | protocol_style | frequency | data_objects | middleware | source_locators | confidence |
|---|---|---|---|---|---|---|---|---|
| I-hybris-shop-01 | sap-erp | in | file | {t("nachts ab 01:30, bis zu zwei Stunden", "nightly at 01:30, up to two hours")} | price; stock | | SRC-001#L41 | high |
| I-hybris-shop-02 | akeneo-pim | in | file | {t("stündlicher Delta-Export", "hourly delta export")} | product | | SRC-001#L41 | high |
| I-hybris-shop-03 | sap-erp | out | api | {t("bei Bestätigung des Warenkorbs", "on basket confirmation")} | order | SAP Cloud Integration | SRC-001#L41 | high |
| I-hybris-shop-04 | salesforce-crm | out | api | {t("bei Registrierung und Bestellung", "on registration and on order")} | customer; order | | SRC-001#L41 | medium |
| I-hybris-shop-05 | legacy-portal | bidirectional | unknown | {t("nicht dokumentiert", "not documented")} | customer | | visual, unverified | low |

## Data ownership

| data_object | role | note | source_locators |
|---|---|---|---|
| order | master | {t("Die Auftragsbelege entstehen hier und werden an das ERP übertragen; kein anderes System erzeugt einen Auftrag.", "Order documents are created here and transferred to the ERP; no other system creates an order.")} | SRC-001#L1 |
| product | consumer | {t("Kommt stündlich als Delta-Export aus dem PIM.", "Received hourly from the PIM as a delta export.")} | SRC-001#L41 |
| price | consumer | {t("Kommt nachts aus dem ERP; der Shop zeigt tagsüber die Preise des Vortags.", "Received nightly from the ERP; the shop shows the previous day's prices during the day.")} | SRC-001#L41 |
| stock | consumer | {t("Kommt nachts zusammen mit den Preisen aus dem ERP.", "Received nightly from the ERP together with the prices.")} | SRC-001#L41 |
| customer | copy | {t("Der Shop hält die Registrierungsdaten und überträgt sie in das CRM; das ERP und das CRM beanspruchen beide die Führung.", "The shop holds registration data and pushes it to the CRM; the ERP and the CRM both claim to be the master.")} | SRC-001#L1; SRC-001#L41 |

## Capabilities

| capability | provided_by | note |
|---|---|---|
| {t("Selbstbedienungsbestellung", "self-service ordering")} | standard | {t("Einstieg in die Selbstbedienungsbestellung in 37 Märkten.", "Entry point for self-service ordering in 37 markets.")} |
| {t("Anzeige von Projektpreisen", "project price display")} | custom | {t("Die Preise kommen aus der nächtlichen Datei und nicht aus einem Live-Aufruf.", "Prices are shown from the nightly file rather than from a live call.")} |
| {t("Einführung in weiteren Märkten", "market roll-out")} | standard | {t("Drei Märkte sind noch nicht im Shop und laufen stattdessen über das alte Portal.", "Three markets are not on the shop yet and run on the legacy portal instead.")} |

## Pain points

| topic | finding | impact | source_locators | client_attention |
|---|---|---|---|---|
| {t("veraltete Preise", "price staleness")} | {t("Durch die nächtliche Preisübertragung zeigt der Shop tagsüber die Preise des Vortags; der Vertrieb hat sich wiederholt beschwert.", "The nightly price transfer means the shop shows the previous day's prices during the day; sales have complained repeatedly.")} | blocker | SRC-001#L41 | yes |
| {t("abweichende Kundendaten", "customer divergence")} | {t("Die Kundendaten weichen zwischen Shop, ERP und CRM ab, weil keine Regel festlegt, welcher Datensatz gilt.", "Customer data diverges between the shop, the ERP and the CRM because no rule says which record wins.")} | major | SRC-001#L41 | yes |
| {t("Marktabdeckung", "market coverage")} | {t("Drei Märkte können den Shop nicht nutzen und werden stattdessen über das alte Portal bedient.", "Three markets cannot use the shop and are served by the legacy portal instead.")} | major | SRC-001#L1; SRC-002#L1 | no |

## Constraints

| constraint | kind | until | source_locators |
|---|---|---|---|
| {t("Jede neue Verbindung zwischen Systemen muss über die Integrationsplattform laufen; Punkt-zu-Punkt wird nur für Schnittstellen geduldet, die schon vor 2022 bestanden.", "Any new system-to-system connection has to run through the integration platform; point-to-point is tolerated only for interfaces that existed before 2022.")} | organisational | {t("unbefristet", "no end date")} | SRC-001#L41 |
| {t("Das ERP wird in diesem Horizont nicht abgelöst.", "The ERP is not replaced in this horizon.")} | organisational | {t("Ende des 18-Monats-Horizonts", "end of the 18-month horizon")} | SRC-002#L1 |

## Open questions

| id | to | question | why_needed | status | answer |
|---|---|---|---|---|---|
| Q-hybris-shop-1 | client | Which system wins when the customer address in the shop, the ERP and the CRM differ? | decides where the customer master belongs and whether the shop may keep writing its own registration data | open | |
| Q-hybris-shop-2 | client | Is there an interface between the shop and the legacy portal, or is the line in the architecture diagram a drawing only? | decides whether switching off the portal touches the shop at all | open | |
| Q-hybris-shop-3 | inventory | The landscape description mentions a line between the CRM and the ERP that the inventory does not list as an interface - should it appear as an assumed interface? | completeness of the flow list | open | |

## Claims

| id | type | statement | evidence | target | supersedes | history |
|---|---|---|---|---|---|---|
| C-hybris-shop-001 | fact | The shop receives prices and stock from the ERP as a nightly flat file that starts at 01:30 and takes up to two hours. | SRC-001#L41 | D2/Interfaces:I-hybris-shop-01 | | |
| C-hybris-shop-002 | fact | The shop is the only system that creates order documents; the ERP and the CRM receive them. | SRC-001#L1 | D2/Data_Ownership:order | | |
| C-hybris-shop-003 | assessment | The nightly price transfer is incompatible with the strategic requirement that prices in the shop are current, because the shop serves the previous day's prices for the whole trading day. | SRC-001#L41; SRC-002#L1 | D2/Pain_Points | | |
| C-hybris-shop-004 | assessment | The line drawn between the shop and the legacy portal is not evidenced by any text and is therefore recorded as an assumed interface with a question to the client. | visual, unverified | D2/Interfaces:I-hybris-shop-05 | | |
"""


def flows():
    return f"""# Consolidation FLOWS: data flows and single source of truth

- **status:** final
- **round:** 1

## Flows

| id | from_system | to_system | data_objects | style | frequency | middleware | evidence | confidence |
|---|---|---|---|---|---|---|---|---|
| F-001 | sap-erp | hybris-shop | price; stock | file | {t("nachts ab 01:30", "nightly at 01:30")} | | C-hybris-shop-001 | high |
| F-002 | akeneo-pim | hybris-shop | product | file | {t("stündlicher Delta-Export", "hourly delta export")} | | C-hybris-shop-002 | high |
| F-003 | hybris-shop | sap-erp | order | api | {t("bei Bestätigung des Warenkorbs", "on basket confirmation")} | SAP Cloud Integration | C-hybris-shop-002 | high |
| F-004 | hybris-shop | salesforce-crm | customer; order | api | {t("bei Registrierung und Bestellung", "on registration and on order")} | | C-hybris-shop-002 | medium |
| F-005 | hybris-shop | legacy-portal | customer | unknown | {t("nicht dokumentiert", "not documented")} | | C-hybris-shop-004 | low |

## SSOT matrix

| data_object | master_system | conflicting_claims | verdict | recommendation |
|---|---|---|---|---|
| customer |  | sap-erp (C-D1-002); salesforce-crm (C-D1-002) | conflict | {t("Beide Abteilungen beanspruchen den Kundendatensatz. Die Führung gehört dorthin, wo der Datensatz zuerst entsteht und laufend gepflegt wird; der Kunde muss entscheiden, bevor eine Option die Führung verlagert.", "Both departments claim the customer record. The master belongs where the record is created first and maintained continuously; the client has to decide before any option re-masters it.")} |
| product | akeneo-pim | | single-master | {t("Die Führung im PIM belassen und jede zweite Stelle entfernen, an der ein Produktattribut erfasst wird.", "Keep the master in the PIM and remove every second place a product attribute is entered.")} |
| price | sap-erp | | single-master | {t("Die Führung im ERP belassen und die nächtliche Datei durch eine aktuelle Schnittstelle ersetzen.", "Keep the master in the ERP and replace the nightly file by a current interface.")} |
| stock | sap-erp | | single-master | {t("Die Führung im ERP belassen; die nächtliche Übertragung reicht für die Bestände nur, wenn das Geschäft einen Stand vom Vortag akzeptiert.", "Keep the master in the ERP; the nightly transfer is acceptable for stock only if the business accepts a day-old figure.")} |
| order | hybris-shop | | single-master | {t("Die Auftragserzeugung im Shop belassen; das ERP und das CRM bleiben Abnehmer.", "Keep order creation in the shop; the ERP and the CRM stay consumers.")} |

## Integration debt

| finding | systems | impact | recommendation |
|---|---|---|---|
| {t("Zwei von fünf Flüssen bewegen Daten als Dateien nach Zeitplan; durch den Preisfluss zeigt der Shop einen ganzen Handelstag lang die Preise des Vortags.", "Two of five flows move data as files on a schedule; the price flow makes the shop serve the previous day's prices for a whole trading day.")} | sap-erp; hybris-shop; akeneo-pim | blocker | {t("Den Preisfluss vor der Einführung der Selbstbedienung durch eine aktuelle Schnittstelle über die Integrationsplattform ersetzen.", "Replace the price flow by a current interface over the integration platform before the self-service roll-out.")} |
| {t("Drei von fünf Flüssen laufen Punkt zu Punkt, obwohl die Integrationsplattform der vorgeschriebene Weg ist; nur der Auftragsfluss nutzt sie.", "Three of five flows are point to point although the integration platform is the mandated route; only the order flow uses it.")} | hybris-shop; sap-erp; salesforce-crm | major | {t("Die Kunden- und Produktflüsse über die Integrationsplattform führen, sobald sie das nächste Mal angefasst werden.", "Route the customer and product flows through the integration platform when they are next touched.")} |
| {t("Ein Fluss beruht auf einer Linie in einem Diagramm, hinter der weder ein Text noch ein Szenario auf der Integrationsplattform steht.", "One flow rests on a line in a diagram with no text behind it and no scenario in the integration platform.")} | hybris-shop; legacy-portal | minor | {t("Mit dem Kunden klären, bevor das Portal abgeschaltet wird.", "Settle it with the client before the portal is switched off.")} |

## Claims

| id | type | statement | evidence | target | supersedes | history |
|---|---|---|---|---|---|---|
| C-FLOWS-001 | fact | The customer record has two claimed masters and therefore no single source of truth; every other data object in the landscape has exactly one. | analysis/inventory/landscape_inventory.md; analysis/scopes/hybris-shop.md | D3/SSOT_Matrix:customer | | |
| C-FLOWS-002 | assessment | Two of the five flows are scheduled file transfers, which is the direct cause of the stale prices in the shop. | analysis/scopes/hybris-shop.md | D3/Integration_Debt | | |
| C-FLOWS-003 | assessment | Only the order flow uses the mandated integration platform; the remaining flows are point to point and contradict the governance rule the architecture board set. | analysis/inventory/landscape_inventory.md | D3/Integration_Debt | | |
"""


def target():
    p1, p2 = t("Phase 1", "phase 1"), t("Phase 2", "phase 2")
    return f"""# Consolidation TARGET: target architecture options and roadmap

- **status:** final
- **round:** 1

## Options

| id | strategic_move | systems_affected | flows_changed | data_objects_re_mastered | rationale | risks | prerequisites | phase | recommendation | confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| O-001 | re-home-ssot | sap-erp; salesforce-crm; hybris-shop | F-004 | customer | {t("Die Vision verlangt einen Kundendatensatz, den Vertrieb und Service teilen; heute beanspruchen ihn zwei Systeme. Das ERP führt die bestellende Organisation bereits für die Rechnungsstellung, also gehört der kaufmännische Datensatz dorthin und das CRM wird Abnehmer mit eigenen Kontaktdaten.", "The vision asks for one customer record shared by sales and service; today two systems claim it. The ERP already holds the buying organisation for invoicing, so the commercial record belongs there and the CRM becomes a consumer with its own contact data.")} | {t("Die Vertriebsorganisation verliert das Schreibrecht an dem Datensatz, den sie als ihren eigenen ansieht; das Hauptrisiko ist die Akzeptanz, nicht die Technik.", "The sales organisation loses write access to the record it considers its own; adoption is the main risk, not technology.")} | {t("Der Kunde beantwortet, welcher Datensatz gilt; die abweichenden Adressen werden vor der Umstellung abgeglichen.", "The client answers which record wins; a reconciliation of the diverging addresses before the switch.")} | {p1} | preferred | medium |
| O-002 | introduce | mdm-hub | F-001; F-004 | customer | {t("Ein eigener Stammdaten-Hub würde den Kundendatensatz unabhängig von ERP und CRM führen.", "A dedicated master data hub would hold the customer record independently of ERP and CRM.")} | {t("Ein fünftes System in einer Landschaft, deren Problem zu viele Besitzer sind; Lizenz- und Betriebskosten ohne belegten Bedarf.", "A fifth system in a landscape whose problem is too many owners; licence and operating cost without a documented need.")} | {t("Ein belegter Mengen- und Governance-Fall, den die Strategienotiz nicht macht.", "A documented volume and governance case that the strategy note does not make.")} | {p2} | alternative | low |
| O-003 | retire | legacy-portal | F-005 | | {t("Die Selbstbedienung muss in allen 40 Märkten verfügbar sein, und der Vertrag für den Anwendungsserver des Portals endet am 2025-06-30 ohne Verlängerung.", "Self-service has to be available in all 40 markets, and the portal's application server contract ends on 2025-06-30 without renewal.")} | {t("Die drei Märkte müssen vor dem Vertragsende in den Shop überführt sein.", "The three markets have to be onboarded to the shop before the contract ends.")} | {t("Die Märkte werden im Shop eingeführt; geklärt ist, ob zwischen Shop und Portal überhaupt eine Schnittstelle besteht.", "Market onboarding in the shop; the question whether an interface between shop and portal exists at all.")} | {p1} | preferred | high |
| O-004 | keep | sap-erp | | | {t("Die Strategienotiz sagt ausdrücklich, dass das ERP in diesem Horizont nicht abgelöst wird.", "The strategy note states explicitly that the ERP is not replaced in this horizon.")} | {t("Kein neues Risiko; das ERP bleibt, wie es ist.", "No new risk; the ERP stays as it is.")} | {t("Keine; der Schritt bestätigt den heutigen Stand.", "None; the move confirms the current state.")} | {p1} | preferred | high |
| O-005 | replace | hybris-shop | F-001; F-002; F-003; F-004 | order | {t("Ein anderes Commerce-Produkt könnte die drei verbleibenden Märkte schneller bedienen.", "A different commerce product could serve the three remaining markets faster.")} | {t("Die Strategienotiz schließt einen zweiten Shop aus und verlangt keine Ablösung; die Auftragsführung würde mitwandern.", "The strategy note rules out a second shop and does not ask for a replacement; the order master would move with it.")} | {t("Keine erfüllbare; der Schritt widerspricht einer dokumentierten Aussage.", "None that can be met; the move contradicts a documented statement.")} | {p2} | rejected | high |

## Roadmap

| phase | options | outcome | dependencies |
|---|---|---|---|
| {p1} | O-001; O-003; O-004 | {t("Vertrieb und Service lesen einen Kundendatensatz, die drei verbleibenden Märkte bestellen über den Shop, und das alte Portal ist vor seinem Vertragsende abgeschaltet.", "Sales and service read one customer record, the three remaining markets order through the shop, and the legacy portal is switched off before its contract ends.")} | {t("Der Kunde beantwortet, welcher Kundendatensatz gilt", "The client answers which customer record wins")} |
| {p2} | O-002 | {t("Nur wenn der Mengen- und Governance-Fall belegt ist: der Kundendatensatz wandert aus ERP und CRM in einen eigenen Hub.", "Only if the volume and governance case is made: the customer record moves out of both ERP and CRM into a dedicated hub.")} | {p1} |

## Principles

| principle | source_locators |
|---|---|
| {t("Jedes Datenobjekt hat genau ein führendes System, und jedes andere System liest es.", "Every data object has exactly one master, and every other system reads it.")} | SRC-002#L1 |
| {t("Neue Verbindungen zwischen Systemen laufen über die Integrationsplattform.", "New system-to-system connections run through the integration platform.")} | SRC-001#L41 |
| {t("Das ERP bleibt; die Landschaft verändert sich um das ERP herum.", "The ERP stays; the landscape changes around it.")} | SRC-002#L1 |

## Claims

| id | type | statement | evidence | target | supersedes | history |
|---|---|---|---|---|---|---|
| C-TARGET-001 | assessment | Moving the customer master to the ERP and making the CRM a consumer delivers the shared customer record the strategy asks for without adding a system. | analysis/consolidated/FLOWS.md; analysis/inventory/landscape_inventory.md | D4/Options:O-001 | | |
| C-TARGET-002 | fact | Switching off the legacy portal is bounded by the application server contract that ends on 2025-06-30, which places the market onboarding in the first phase. | analysis/inventory/landscape_inventory.md | D4/Roadmap:{p1} | | |
| C-TARGET-003 | assessment | Replacing the commerce platform is rejected because the strategy note rules out a second shop and asks for no replacement. | SRC-002#L1 | D4/Options:O-005 | | |
"""


CRITIC = """# Gauntlet score: hybris-shop / {critic} / round 1

- **scope:** hybris-shop
- **critic:** {critic}
- **round:** 1

## Scores

| claim_id | score | verdict | issue | counter_evidence | fix_hint |
|---|---|---|---|---|---|
| C-hybris-shop-001 | {s1} | confirmed | {i1} | | |
| C-hybris-shop-002 | {s2} | confirmed | | | |
| C-hybris-shop-003 | {s3} | insightful | | | |
| C-hybris-shop-004 | {s4} | confirmed | | | |

## Missing claims

- {missing}

## Estate observations

-

## Summary

{summary}
"""

GATE = """# Final gate: cto / round 1

- **persona:** cto
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
| I1 | D3 | SSOT_Matrix!B2 | the master cell shows a dash without saying who has to decide | content | major | K2 | name the decision owner in the recommendation column |

## Summary

The picture is clear and the numbers can be audited.
"""

def summaries():
    return {
        "D1": t("## Einordnung\n\nDie betrachtete Landschaft besteht aus {kpi:systems} Systemen rund um eine Commerce-Plattform; {kpi:core} davon tragen die betrachteten Geschäftsprozesse. Datenobjekte, die mehr als ein System als führend beansprucht: {kpi:conflicts}; jedes andere Datenobjekt hat genau einen Besitzer.\n\n- Das alte Kundenportal ist durch einen Vertrag begrenzt, der Mitte 2025 endet; daraus ergibt sich die früheste Frist dieser Untersuchung.",
                "## Assessment\n\nThe landscape in scope consists of {kpi:systems} systems around one commerce platform; {kpi:core} of them carry the business processes in scope. Data objects claimed as master by more than one system: {kpi:conflicts}; every other data object has exactly one owner.\n\n- The legacy customer portal is bounded by a contract that ends in mid-2025, which sets the earliest deadline in this study."),
        "D2": t("## Einordnung\n\nDie Commerce-Plattform erhält die Produktdaten stündlich und Preise und Bestände nachts, und sie ist das einzige System, das Auftragsbelege erzeugt. Belegte Schnittstellen: {kpi:interfaces}, davon beruhen {kpi:if_assumption} auf einer Annahme.\n\n- Die nächtliche Preisübertragung ist der Befund mit der größten Wirkung: durch sie zeigt der Shop einen ganzen Handelstag lang die Preise des Vortags.",
                "## Assessment\n\nThe commerce platform receives product data hourly and prices and stock nightly, and it is the only system that creates order documents. Interfaces documented: {kpi:interfaces}, of which {kpi:if_assumption} rest on an assumption.\n\n- The nightly price transfer is the finding with the widest effect: it makes the shop serve the previous day's prices for a whole trading day."),
        "D3": t("## Einordnung\n\nDatenflüsse in der Landschaft: {kpi:flows}; davon laufen {kpi:via_mw} über die Integrationsplattform, der Rest Punkt zu Punkt, obwohl sie der vorgeschriebene Weg ist.\n\n- Der Kundendatensatz ist das Datenobjekt ohne eindeutig führendes System, und genau auf ihm beruht die Strategie.",
                "## Assessment\n\nData flows in the landscape: {kpi:flows}; {kpi:via_mw} of them run through the integration platform, the rest point to point although it is the mandated route.\n\n- The customer record is the data object without a single source of truth, and it is the one the strategy depends on."),
        "D4": t("## Einordnung\n\nOptionen zur Entscheidung: {kpi:options}, davon empfohlen: {kpi:preferred}. Die erste Phase tragen zwei Schritte: die Führung des Kundendatensatzes wandert in das ERP und das alte Portal wird vor seinem Vertragsende abgeschaltet.\n\n- Ein eigener Stammdaten-Hub bleibt als Alternative erhalten, wird aber ohne belegten Mengen- und Governance-Fall nicht empfohlen.",
                "## Assessment\n\nOptions on the table: {kpi:options}, of which recommended: {kpi:preferred}. Two moves carry the first phase: the customer master moves to the ERP and the legacy portal is switched off before its contract ends.\n\n- A dedicated master data hub stays on the table as an alternative but is not recommended without a documented volume and governance case."),
    }


def erp():
    """--variant conflicts: a second system analysis whose price/stock interface end disagrees with the shop's (an API every 15
    minutes against a nightly file) and that claims the customer master the inventory also gives the CRM"""
    s = shop().replace("hybris-shop", "sap-erp")
    head, _, rest = s.partition("## Interfaces"); tail = rest[rest.index("## Capabilities"):]; tail = tail[:tail.index("## Claims")]
    return head + """## Interfaces

| id | counterpart | direction | protocol_style | frequency | data_objects | middleware | source_locators | confidence |
|---|---|---|---|---|---|---|---|---|
| I-sap-erp-01 | hybris-shop | out | api | every 15 minutes | price; stock | | SRC-001#L41 | medium |
| I-sap-erp-02 | hybris-shop | in | api | | order | SAP Cloud Integration | SRC-001#L41 | high |

## Data ownership

| data_object | role | note | source_locators |
|---|---|---|---|
| customer | master | The buying organisation is kept for invoicing. | SRC-001#L1 |
| price | master | Customer-specific and list prices. | SRC-001#L1 |
| order | consumer | Received from the shop. | SRC-001#L41 |

""" + tail + """## Claims

| id | type | statement | evidence | target | supersedes | history |
|---|---|---|---|---|---|---|
| C-sap-erp-001 | fact | The ERP pushes prices and stock to the shop over an API every 15 minutes. | SRC-001#L41 | D2/Interfaces:I-sap-erp-01 | | |
| C-sap-erp-002 | fact | The ERP is the master of the customer record. | SRC-001#L1 | D2/Data_Ownership:customer | | |
"""


def main():
    fill_run()
    w("input/2024-05-it-landscape.md", LANDSCAPE)
    w("input/2024-05-strategy-note.md", STRATEGY)
    system_list_xlsx()
    w("analysis/inventory/landscape_inventory.md", inventory())
    w("analysis/scopes/hybris-shop.md", shop())
    if "--variant" in sys.argv and sys.argv[sys.argv.index("--variant") + 1] == "conflicts": w("analysis/scopes/sap-erp.md", erp())
    w("analysis/consolidated/FLOWS.md", flows())
    w("analysis/consolidated/TARGET.md", target())
    w("analysis/gauntlet/hybris-shop/round1-client.md", CRITIC.format(
        critic="client", s1=8, s2=9, s3=8, s4=8,
        i1="the two-hour window is quoted as an upper bound; say so in the statement",
        missing="No statement on how many of the 40 markets are actually on the shop today",
        summary="The interfaces match what the landscape description says, and the locators resolve."))
    w("analysis/gauntlet/hybris-shop/round1-standard.md", CRITIC.format(
        critic="standard", s1=9, s2=8, s3=9, s4=8, i1="",
        missing="[standard-fact] A commerce platform of this generation offers a synchronous price lookup, which the analysis does not mention as an option",
        summary="The pattern assessment holds; the client half of every claim is left to the other reviewer."))
    w("analysis/gate/round1-cto.md", GATE)
    for k, v in summaries().items():
        w(f"analysis/summaries/{k}.md", v + "\n")
    print("fixture written to", T)


if __name__ == "__main__":
    main()
