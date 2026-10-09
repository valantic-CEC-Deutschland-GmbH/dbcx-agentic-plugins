#!/usr/bin/env python3
"""Write toy engagement content into an initialised RUN folder (single-run project) so the whole tech-fit-estimation chain can be
smoke-tested: filled run.json, a requirements workbook + mapping, a tiny corpus, two chunk estimations, their critic score files, the
consolidation, a gate file, the management summary - for one of three variants:

  none    the default single option (no run.json `options`): today's generic fixture on the single-run model
  starts  two starting points on one pack: brownfield "Migration" + greenfield "Neubau"; toy handover artefacts of a code analysis
          (requirements-coverage, target-readiness, customization-depth, code-inventory), a toy client repository with one narrow
          lookup, client-assumptions with one answered and one open A-nn, a reference row whose source is vendor standard code
  packs   two technology packs (sap-commerce + spryker, both greenfield) - standard-<pack> critics
  scenarios  the starts setup plus row classes, the integration platform and scenario totals: a code analysis with a refactoring
          unit and three migration tasks (the classification proposal of the agent is analysis/classification.md: one refactoring row RF-01
          with a saving on FR-014, one technical migration row TM-01, one part of FR-011, one dropped), today's behaviour / description gaps
          on FR-011 and FR-030 (both options cite them), Integration Suite sizes on rows and a position, run.json `scenarios` (Migration,
          Migration + Refactoring, Neubau) with `fixed_phases_seed`, fixed phases per scenario with the seed decisions, client-critic grounds
          and one standard dispute; two derived rows of the code analysis (NR-001 merged into FR-010, NR-002 dropped - run.json
          requirements.decisions) and one without a decision (NR-003 - the classification merges it into FR-016), appended to
          state/requirements.json by `--derived-rows` after the requirement import
  systems (the inputs; wave 1, wave 2 and the consolidation by the steps below) run.json `systems` (commerce with two options -
          SAP Commerce Cloud on the sap-commerce pack and Shopware on _generic (two scenarios, per-technology standard critics) -, a dependent
          middleware, CDC, S/4 estimated by the client, Magnolia by a partner, each with landscape_ids) and a client workbook: a passthrough
          FR sheet with a title row above the header (estimate: false), a technical sheet with rollup_to_field and systems_field, an
          interface sheet (kind: interfaces), plus a landscape CSV with German headers (--map) that also lists SAP BTP, which the run does
          not estimate; no analyses. `--gaps` (+ integration, after `dbcx discover`): the analysts' Markdown files of the wave-1
          chunks analysis/scopes/commerce-sapcc-01.md (three gaps), commerce-shopware-01.md (none), cdc-01.md (one gap) for `dbcx md_to_json
          estimation`, and the architect agent's file analysis/architect/ARCHITECT-1.md (overrule, route to an estimated system, route to
          SAP BTP outside the run, reduce to the standard; two client assumptions)
          The smoke variants `systems` and `systems-single` (the real flow): --book-inputs multi|single [--client-sheet
          <name>] (before the requirement import: `single` keeps SAP Commerce Cloud only - one scenario -, the day rate, components, a
          condition column and a workshop-source column hidden from the customer edition on the FR sheet, an interim column on the
          technical sheet; --client-sheet renames the FR sheet), --gaps (wave 1, above), --wave2 (after the architect's batch, `dbcx
          discover --pickup`, `dbcx plan_waves` and the registration: the analyses of every planned chunk not analysed yet - the follow-ups
          of the overrule and the reduction, the middleware chunk with the packages routed to it, a position split) and --consolidate
          multi|single (SUMMARY.md with fixed phases per system option, the D1 summary text, fixture_expected.json)

Usage: python3 methods/tech-fit-estimation/fixtures/make_fixture.py <run_dir> [--variant none|starts|packs|scenarios|systems] [--no-analyses]
       python3 .../make_fixture.py <run_dir> --variant systems --gaps   (after `dbcx discover`: the wave-1 analyses + the architect's file)
       python3 .../make_fixture.py <run_dir> --variant scenarios --derived-rows   (after requirements_to_json: the requirements-set's NR rows)
       python3 .../make_fixture.py <run_dir> --variant systems --book-inputs multi|single [--client-sheet <name>] | --wave2 | --consolidate multi|single
       python3 .../make_fixture.py <run_dir> --variant systems --critic <scope> <critic>   (after `dbcx extract_claims <scope> --round 1`: the critic's round-1 file)
Every size is defined ONCE below; fixture_expected.json (in the run folder) carries per option the sizes and fixed phases the smoke
recomputes the totals from (for the default parameters and for edited ones), and fixture_refs.json the reference rows to add.
"""
import os, sys, json

T = os.path.abspath(sys.argv[1]); NO_ANA = "--no-analyses" in sys.argv
VARIANT = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "none"


def w(p, s):
    p = os.path.join(T, p); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(s)


def J(p): return json.load(open(os.path.join(T, p), encoding="utf-8"))
def W(p, d):
    p = os.path.join(T, p); os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


LANG = J("run.json").get("languages", {}).get("deliverable", "en")
def t(de, en):
    """client-facing fixture text in the run's deliverable language (the customer edition must read German throughout in a German run)"""
    return de if LANG == "de" else en


# --------------------------------------------------------------------------- the client's requirement list
# (id, epic, title, description, acceptance criteria, exclusions, references, release, priority, source)
FR = [
 ("FR-009", "Installed base", t("Maschinenliste", "Equipment list"), t("Kunden sehen die Maschinen, die an ihren Standorten installiert sind.", "Customers see the machines installed at their sites."), t("1) Liste je Einheit; 2) Filter nach Standort", "1) list per unit; 2) filter by site"), t("Keine Servicebuchung", "No service booking"), "TR-01", "MVP", "must", "WS1"),
 ("FR-010", "Installed base", t("Maschinen-Detailseite", "Equipment detail page"), t("Jede Maschine hat eine Detailseite mit Seriennummer, Standort und Garantie.", "Each machine has a detail page with serial number, site and warranty."), t("1) alle Stammdaten sichtbar", "1) all master data shown"), "", "TR-01", "MVP", "must", "WS1"),
 ("FR-011", "Installed base", t("Maschinendokumente", "Equipment documents"), t("Handbücher und Zertifikate sind je Maschine herunterladbar.", "Manuals and certificates are downloadable per machine."), t("1) Download je Dokument", "1) download per document"), t("Keine Dokumentenerstellung", "No document authoring"), "", "MVP", "should", "WS1"),
 ("FR-012", "Installed base", t("Maschinensuche", "Equipment search"), t("Kunden suchen ihre Maschinen über die Seriennummer.", "Customers search their machines by serial number."), t("1) exakte Übereinstimmung; 2) Teiltreffer", "1) exact match; 2) partial match"), "", "", "MVP", "must", "WS1"),
 ("FR-013", "Installed base", t("Maschinenexport", "Equipment export"), t("Die Maschinenliste ist als CSV exportierbar.", "The machine list is exportable as CSV."), t("1) Export der gefilterten Liste", "1) export of the filtered list"), t("Keine zeitgesteuerte Zustellung", "No scheduled delivery"), "", "Phase 2", "could", "WS2"),
 ("FR-014", "Installed base", t("Wartungsbenachrichtigungen", "Maintenance notifications"), t("Kunden werden benachrichtigt, bevor eine Wartung fällig ist.", "Customers are notified before a maintenance is due."), t("1) E-Mail 30 Tage vorher; 2) Abmeldung möglich", "1) e-mail 30 days before; 2) opt-out"), t("Keine SMS", "No SMS"), "TR-01", "MVP", "should", "WS2"),
 ("FR-015", "Installed base", t("Maschinenzuordnung", "Equipment assignment"), t("Ein Administrator ordnet Maschinen den Benutzern derselben Einheit zu.", "An administrator assigns machines to users of the same unit."), t("1) zuordnen; 2) entziehen", "1) assign; 2) revoke"), "", "", "MVP", "must", "WS1"),
 ("FR-016", "Installed base", t("Ersatzteile je Maschine", "Spare parts per machine"), t("Die Detailseite listet die Ersatzteile der Maschine.", "The detail page lists the spare parts of that machine."), t("1) Teileliste; 2) in den Warenkorb", "1) parts list; 2) add to cart"), t("Keine Kompatibilitätsprüfung", "No compatibility check"), "TR-01", "Phase 2", "should", "WS2"),
 ("FR-017", "Installed base", t("Servicehistorie", "Service history"), t("Kunden sehen vergangene Serviceeinsätze je Maschine.", "Customers see past service events per machine."), t("1) Liste mit Datum und Art", "1) list with date and type"), t("Keine Kostendaten", "No cost data"), "TR-01", "MVP", "could", "WS3"),
 ("FR-023", "Catalog", t("Nachfolgeprodukte", "Successor products"), t("Auslaufprodukte zeigen ihr Nachfolgeprodukt.", "Discontinued products show their successor."), t("1) Nachfolger auf der Produktseite sichtbar", "1) successor shown on the product page"), "", "", "MVP", "must", "WS2"),
 ("FR-024", "Catalog", t("Produktvergleich", "Product comparison"), t("Kunden vergleichen Produkte nebeneinander.", "Customers compare products side by side."), t("1) Attributtabelle", "1) attribute table"), "", "", "Phase 2", "could", "WS2"),
 ("FR-030", "Checkout", t("Teillieferung je Werk", "Split delivery by plant"), t("Eine Bestellung darf nach liefernden Werken aufgeteilt werden.", "An order may be split by delivering plant."), t("1) Aufteilung im Checkout sichtbar; 2) Aufteilung bleibt in der Bestellung erhalten", "1) split shown in checkout; 2) split kept in the order"), t("Keine Teilrechnung", "No partial invoicing"), "TR-02", "Phase 2", "should", "WS3"),
]
TR = [
 ("TR-01", "Integration", t("ERP-Synchronisation der Maschinen", "ERP equipment synchronisation"), t("Maschinen und Serviceeinsätze kommen jede Nacht aus dem ERP.", "Machines and service events come from the ERP every night."), t("1) nächtliches Delta; 2) Fehlerbericht", "1) nightly delta; 2) error report"), t("Keine Echtzeit-Synchronisation", "No real-time sync"), "FR-009", "MVP", "must", "TECH"),
 ("TR-02", "Integration", t("Bestellübergabe an das ERP", "ERP order transfer"), t("Bestellungen werden über die Middleware an das ERP übergeben.", "Orders are transferred to the ERP through the middleware."), t("1) Bestellung inkl. Aufteilung", "1) order incl. split"), t("Kein Retourenprozess", "No return process"), "FR-030", "Phase 2", "must", "TECH"),
]
HDR = ["Req ID", "Epic", "Title", "Description", "Acceptance criteria", "Exclusions", "References", "Release", "Priority", "Sources"]
EPIC = {r[0]: r[1] for r in FR + TR}; REL = {r[0]: r[7] for r in FR + TR}
CHUNK1 = [r[0] for r in FR if r[1] == "Installed base"]; CHUNK2 = [r[0] for r in FR + TR if r[1] != "Installed base"]
MAP = {"0": 0, "XS": 0.5, "S": 1, "M": 2, "L": 5, "XL": 10, "XXL": 20}

# --------------------------------------------------------------------------- options of the variant
PLATFORM = {"none": "_generic", "starts": "_generic", "packs": "sap-commerce", "scenarios": "_generic", "systems": "_generic"}[VARIANT]
SC = VARIANT == "scenarios"; BROWN = VARIANT in ("starts", "scenarios")
OPTIONS = {"none": [],
           "starts": [{"id": "brownfield", "label": "Migration", "start": "brownfield"}, {"id": "greenfield", "label": t("Neubau", "Rebuild"), "start": "greenfield"}],
           "scenarios": [{"id": "brownfield", "label": "Migration", "start": "brownfield"}, {"id": "greenfield", "label": t("Neubau", "Rebuild"), "start": "greenfield"}],
           "packs": [{"id": "sapcc", "label": "SAP Commerce", "pack": "sap-commerce", "start": "greenfield"}, {"id": "spryker", "label": "Spryker", "pack": "spryker", "start": "greenfield"}],
           "systems": []}[VARIANT]
OPTS = OPTIONS or [{"id": "target", "label": "Generic target platform", "start": "greenfield", "pack": "_generic"}]
PACK = {o["id"]: o.get("pack", PLATFORM) for o in OPTS}
PACKS = list(dict.fromkeys(PACK.values()))
CRITICS = ["client"] + ([f"standard-{p}" for p in PACKS] if len(PACKS) > 1 else ["standard"])
DAY_RATE = 1350 if BROWN else 1200

# --------------------------------------------------------------------------- reference rows (the smoke adds them in this order: PS-7-001 ...)
DOC = "https://docs.example.invalid/generic-target/2.0/"
VENDOR = "@spartacus/storefront@221121.18.0/fesm2022/spartacus-storefront.mjs:120"
REFS = [
 {"fact": "Assigning machines to users of a unit is a permission of the standard unit administration", "applies": "2.0", "url": DOC + "units",
  "title": t("Einheitenverwaltung: Maschinen den Benutzern einer Einheit zuordnen", "Unit administration: assigning machines to the users of a unit"), "summary": t("Die Zuordnung von Maschinen zu Benutzern einer Einheit ist eine Berechtigung der Standard-Einheitenverwaltung in Version 2.0.", "Assigning machines to the users of a unit is a permission of the standard unit administration in version 2.0.")},
 {"fact": "Custom entities with list and detail templates are the extension mechanism for own data", "applies": "2.0", "url": DOC + "custom-entities",
  "title": t("Eigene Entitäten mit Listen- und Detailvorlagen", "Custom entities with list and detail templates"), "summary": t("Eigene Daten werden in Version 2.0 als eigene Entität mit Listen- und Detailvorlage gebaut.", "Own data is built as a custom entity with list and detail templates in version 2.0.")},
 {"fact": "The media manager stores documents and offers downloads per object", "applies": "2.0", "url": DOC + "media-manager",
  "title": t("Medienverwaltung: Ablage und Download je Objekt", "Media manager: storage and download per object"), "summary": t("Die Medienverwaltung legt Dokumente ab und bietet den Download je Objekt an.", "The media manager stores documents and offers the download per object.")},
 {"fact": "The Import/Export module exports lists as CSV and runs nightly imports with an error report", "applies": "2.0", "url": DOC + "import-export",
  "title": t("Import/Export-Modul: CSV-Export und nächtlicher Import", "Import/Export module: CSV export and nightly import"), "summary": t("Das Modul exportiert Listen als CSV und führt nächtliche Importe mit Fehlerbericht aus.", "The module exports lists as CSV and runs nightly imports with an error report.")},
 {"fact": "The storefront renders product references of type SUCCESSOR on the product page out of the box", "applies": "221121.18.0", "url": VENDOR,
  "title": t("Storefront: Nachfolgeprodukte auf der Produktseite (Standardcode)", "Storefront: successor products on the product page (standard code)"), "summary": t("Die Storefront zeigt Produktreferenzen vom Typ SUCCESSOR ohne Anpassung auf der Produktseite.", "The storefront shows product references of type SUCCESSOR on the product page without a change.")},
 {"fact": "Checkout steps are extension points of the order process", "applies": "2.0", "url": DOC + "checkout-steps",
  "title": t("Checkout-Schritte als Erweiterungspunkte", "Checkout steps as extension points"), "summary": t("Der Bestellprozess lässt sich über Checkout-Schritte als Erweiterungspunkte ergänzen.", "The order process is extended through checkout steps as extension points.")},
]
R = {k: f"PS-7-{i:03d}" for i, k in enumerate(("units", "entities", "media", "impex", "vendor", "checkout"), 1)}

# --------------------------------------------------------------------------- sizes per requirement and option kind
# kind -> req -> (approach, size or [positions], evidence, mechanism, derivation(de, en), assumption(de, en) | None)
GF = {
 "FR-009": ("custom", ["XL", "XL", "S"], [R["entities"]], t("Eigene Entität und Storefront-Modul", "Custom entity and storefront module"), (t("eigene Entität mit acht Attributen, Listen- und Filteransicht; drei Positionen", "own entity with eight attributes, list and filter view; three positions"),), None),
 "FR-010": ("custom", "M", [R["entities"]], t("Detailvorlage der eigenen Entität", "Detail template of the custom entity"), (t("eine Detailvorlage über die Entität aus FR-009", "one detail template over the entity of FR-009"),), None),
 "FR-011": ("partial", "M", [R["media"]], t("Medienverwaltung", "Media manager"), (t("Ablage und Download aus der Medienverwaltung, die Zuordnung je Maschine wird gebaut", "storage and download from the media manager, the per-machine assignment is built"),), None),
 "FR-012": ("partial", "M", [R["entities"]], t("Suchindex", "Search index"), (t("Indizierung der eigenen Entität und ein eigener Analyzer für Teiltreffer", "indexing of the custom entity and an own analyser for partial matches"),), None),
 "FR-013": ("standard", "S", [R["impex"]], t("Import/Export-Modul", "Import/Export module"), (t("ein Exportprofil mit den gefilterten Spalten", "one export profile with the filtered columns"),), None),
 "FR-014": ("partial", "M", [R["impex"]], t("Benachrichtigungsvorlagen", "Notification templates"), (t("Vorlage und Abmeldung sind Einstellungen; die 30-Tage-Regel ist ein geplanter Job", "template and opt-out are settings; the 30-day rule is a scheduled job"),), None),
 "FR-015": ("standard", "S", [R["units"]], t("B2B-Einheitenverwaltung", "B2B unit administration"), (t("zwei Rollen mit der Standardberechtigung der Einheit", "two roles with the standard permission of the unit"),), None),
 "FR-016": ("custom", "L", [R["entities"]], t("Warenkorb-API und eigene Relation", "Cart API and custom relation"), (t("Relation Maschine zu Ersatzteil, Teileliste und In-den-Warenkorb", "relation machine to spare part, parts list and add to cart"),), None),
 "FR-017": ("custom", "M", [R["entities"]], t("Eigene Entität und Detail-Reiter", "Custom entity and detail tab"), (t("Entität Serviceeinsatz und ein Listenreiter auf der Detailseite", "service event entity and a list tab on the detail page"),), None),
 "FR-023": ("standard", "XS", [R["vendor"]], t("Produktreferenztyp SUCCESSOR", "Product reference type SUCCESSOR"), (t("ein Referenztyp konfiguriert; die Produktseite zeigt ihn ohne Anpassung", "one reference type configured; the product page renders it out of the box"),), None),
 "FR-024": ("standard", "S", [R["impex"]], t("Produktvergleich", "Product comparison"), (t("Modul aktivieren und ein Attributset für die Vergleichstabelle", "activate the module and one attribute set for the comparison table"),), (t("Vergleich von bis zu vier Produkten über das vorhandene Attributset", "comparison of up to four products over the existing attribute set"), "AS-01")),
 "FR-030": ("custom", "XL", [R["checkout"]], t("Erweiterungspunkt Checkout-Schritt", "Checkout step extension point"), (t("Aufteilungslogik je Werk, Checkout-Schritt und Bestellabbildung; die ERP-Übergabe liegt auf TR-02", "split logic per plant, checkout step and order mapping; the ERP transfer sits on TR-02"),), None),
 "TR-01": ("partial", "XL", [R["impex"]], t("Import/Export-Modul", "Import/Export module"), (t("nächtlicher Zeitplan und Fehlerbericht aus dem Modul, die Abbildung von Maschinen und Serviceeinsätzen wird gebaut", "nightly schedule and error report from the module, the mapping of machines and service events is built"),), None),
 "TR-02": ("custom", "L", [R["checkout"]], t("Ausgehender Bestell-Konnektor", "Outbound order connector"), (t("Bestellabbildung inkl. Werksaufteilung, Wiederholung und Überwachung", "order mapping incl. the plant split, retry and monitoring"),), None),
}
def HO(r): return f"HO-requirements-coverage#{r}"   # (GF is patched below for the scenarios variant)
BF = {
 "FR-009": ("keep", "0", [HO("FR-009")], t("Bestehende Entität Maschine", "Existing machine entity"), (t("die Liste läuft heute im eigenen Modul und bleibt unverändert", "the list runs in the own module today and stays unchanged"),), None),
 "FR-010": ("keep", "0", [HO("FR-010")], t("Bestehende Detailseite", "Existing detail page"), (t("die Detailseite besteht und bleibt unverändert", "the detail page exists and stays unchanged"),), None),
 "FR-011": ("adapt", "M", [HO("FR-011")], t("Bestehender Dokumentendienst", "Existing document service"), (t("der Dokumentendienst wird an die neue Medienablage angepasst; die Nachprüfung im Code ergab einen Dienst, keine drei", "the document service is adapted to the new media storage; the code lookup found one service, not three"),), None),
 "FR-012": ("adapt", "S", [HO("FR-012")], t("Bestehender Suchindex", "Existing search index"), (t("der eigene Analyzer wird in die Zielversion übernommen", "the own analyser is carried into the target version"),), None),
 "FR-013": ("keep", "0", [HO("FR-013")], t("Bestehender Export", "Existing export"), (t("der Export besteht und bleibt unverändert", "the export exists and stays unchanged"),), None),
 "FR-014": ("convert-to-standard", "M", [HO("FR-014"), R["impex"]], t("Benachrichtigungsvorlagen", "Notification templates"), (t("der eigene Benachrichtigungsjob wird durch Vorlagen und einen Standardjob ersetzt", "the own notification job is replaced by templates and a standard job"),), None),
 "FR-015": ("convert-to-standard", "S", [HO("FR-015"), R["units"]], t("B2B-Einheitenverwaltung", "B2B unit administration"), (t("die überschriebene Einheitenlogik wird durch die Standardberechtigung ersetzt", "the shadowed unit logic is replaced by the standard permission"),), None),
 "FR-016": ("adapt", "M", [HO("FR-016")], t("Bestehende Ersatzteilrelation", "Existing spare part relation"), (t("die Relation bleibt, die Teileliste wird an die neue Storefront angepasst", "the relation stays, the parts list is adapted to the new storefront"),), None),
 "FR-017": ("retire", "XS", [HO("FR-017")], t("Bestehender Reiter Servicehistorie", "Existing service history tab"), (t("der Reiter entfällt, weil das Serviceportal die Historie zeigt; nur der Rückbau zählt", "the tab is retired because the service portal shows the history; only the removal counts"),), None),
 "FR-023": ("new", "XS", [R["vendor"]], t("Produktreferenztyp SUCCESSOR", "Product reference type SUCCESSOR"), (t("heute nicht vorhanden; die Storefront zeigt den Referenztyp im Standard", "not present today; the storefront renders the reference type out of the box"),), None),
 "FR-024": ("new", "S", [R["impex"]], t("Produktvergleich", "Product comparison"), (t("heute nicht vorhanden; Modul und Attributset wie im Neubau", "not present today; module and attribute set as in the rebuild"),), (t("Vergleich von bis zu vier Produkten über das vorhandene Attributset", "comparison of up to four products over the existing attribute set"), "AS-01")),
 "FR-030": ("rebuild", ["XXL", "S"], [HO("FR-030"), R["checkout"]], t("Erweiterungspunkt Checkout-Schritt", "Checkout step extension point"), (t("der eigene Checkout wird auf den Standard-Checkout neu gebaut; zwei Positionen", "the own checkout is rebuilt on the standard checkout; two positions"),), None),
 "TR-01": ("adapt", "L", [HO("TR-01")], t("Bestehender ERP-Import", "Existing ERP import"), (t("der Import bleibt, die Abbildung wird an das neue Datenmodell angepasst", "the import stays, the mapping is adapted to the new data model"),), None),
 "TR-02": ("adapt", "S", [HO("TR-02")], t("Bestehender Bestell-Konnektor", "Existing order connector"), (t("der Konnektor wird angepasst; den Regressionstest trägt der QA-Zuschlag", "the connector is adapted; the regression test is carried by the QA surcharge"),), (t("Regressionstest im QA-Zuschlag enthalten", "regression test carried by the QA surcharge"), None)),
}
SPR = dict(GF)   # the second technology of the packs variant differs on four rows
SPR.update({
 "FR-011": ("standard", "S", [R["media"]], t("Dateiverwaltung", "File manager"), (t("die Dateiverwaltung trägt Dokumente je Objekt im Standard", "the file manager carries documents per object out of the box"),), None),
 "FR-015": ("partial", "M", [R["units"]], t("Unternehmenskonten", "Company accounts"), (t("Unternehmenskonten tragen die Zuordnung; die Entziehung wird gebaut", "company accounts carry the assignment; the revocation is built"),), None),
 "FR-030": ("custom", ["XXL", "M"], [R["checkout"]], t("Checkout-Erweiterung", "Checkout extension"), (t("Aufteilung je Werk über eine Checkout-Erweiterung; zwei Positionen", "split per plant through a checkout extension; two positions"),), None),
 "TR-01": ("partial", "L", [R["impex"]], t("Datenimport", "Data import"), (t("der Datenimport trägt Zeitplan und Fehlerbericht; die Abbildung wird gebaut", "the data import carries schedule and error report; the mapping is built"),), None)})
KIND = {"target": GF, "brownfield": BF, "greenfield": GF, "sapcc": GF, "spryker": SPR}
CLS = {}; IS = {}; SAVE = {}
if SC:   # the rows `dbcx classify apply` appends (TM-01 from MT-001, RF-01 from the unit shopnotify) and their sizes
    TMR = [("TM-01", "tech-migration", t("Technische Migration", "Technical migration"), t("Schnittstellen-Voraussetzungen der neuen Storefront", "Interface prerequisites of the new storefront"),
            t("Die neue Storefront braucht freigeschaltete Standardschnittstellen, einen eigenen Anmeldeclient und die Freigabe der Shop-Domains.", "The new storefront needs the standard interfaces switched on, its own login client and the shop domains allowed."), ["FR-009", "FR-010"], "HO-target-readiness#MT-001"),
           ("RF-01", "refactoring", "Refactoring", t("Wartungsbenachrichtigung auf Standardvorlagen umstellen", "Move the maintenance notification to standard templates"),
            t("Die heutige eigene Versandlogik der Wartungsbenachrichtigung wird durch Standardvorlagen und einen Standardzeitplan ersetzt.", "Today's own sending logic of the maintenance notification is replaced by standard templates and a standard schedule."), ["FR-014"], "HO-customization-depth#shopnotify")]
    for rid, cls, ep, *_ in TMR: EPIC[rid] = ep; REL[rid] = "MVP"; CLS[rid] = cls
    CHUNK2 += [x[0] for x in TMR]   # `dbcx discover` puts the appended rows into the mixed chunk
    BF["TM-01"] = ("new", "M", ["HO-target-readiness#MT-001"], t("Standardschnittstellen der Storefront", "Standard storefront interfaces"), (t("Schnittstellen freischalten, Anmeldeclient anlegen und Shop-Domains freigeben; heute nicht vorhanden", "switch the interfaces on, create the login client and allow the shop domains; not present today"),), None)
    GF["TM-01"] = ("partial", "S", ["HO-target-readiness#MT-001", R["units"]], t("Standardschnittstellen der Storefront", "Standard storefront interfaces"), (t("im Neubau Teil der Projektaufsetzung, es bleiben Anmeldeclient und Domain-Freigabe", "part of the project setup in the rebuild, the login client and the domain approval remain"),), None)
    BF["RF-01"] = ("convert-to-standard", "M", ["HO-customization-depth#shopnotify", R["impex"]], t("Standard-Benachrichtigungsvorlagen", "Standard notification templates"), (t("die eigene Versandlogik entfällt, Vorlagen und Zeitplan kommen aus dem Standard", "the own sending logic is removed, templates and schedule come from the standard"),), None)
    SAVE[("RF-01", "brownfield")] = ("S", ["FR-014"])
    IS.update({("TR-01", "brownfield"): ("M", t("die Abbildung der Maschinen im Import-Ablauf wird angepasst", "the machine mapping of the import flow is adapted")),
               ("TR-01", "greenfield"): ("L", t("der Import-Ablauf der Maschinen und Serviceeinsätze wird neu aufgebaut", "the import flow of machines and service events is rebuilt")),
               ("TR-02", "greenfield"): ("M", t("der Bestell-Ablauf wird für die neue Bestellabbildung neu aufgebaut", "the order flow is rebuilt for the new order mapping")),
               ("FR-030", "brownfield", "2"): ("XS", t("die Bestellschnittstelle trägt die Werksaufteilung als zusätzliches Feld", "the order interface carries the plant split as an additional field"))})
    for r in ("FR-011", "FR-030"):   # the code analysis shows more than the text: both options cite the coverage row (real scope)
        a, sz, ev, *rest = GF[r]; GF[r] = (a, sz, ev + [f"HO-requirements-coverage#{r}"], *rest)

PHASES = {
 "target": [("PH-01", "phase", t("Projektaufsetzung und Umgebungen", "Project setup and environments"), 5, t("Aufsetzen von Repository, Pipeline und drei Umgebungen", "setup of repository, pipeline and three environments"), [R["impex"]]),
            ("PH-02", "phase", t("Abnahmebegleitung", "Acceptance support"), 3, t("drei Wochen Begleitung der Abnahme mit einem halben Personentag je Tag", "three weeks of acceptance support at half a person day per day"), [R["impex"]])],
 "brownfield": [("PH-B1", "phase", t("Projektaufsetzung auf der bestehenden Umgebung", "Project setup on the existing environment"), 3, t("Pipeline und Umgebungen bestehen; nur die Zielversion wird aufgesetzt", "pipeline and environments exist; only the target version is set up"), [HO("TR-01")]),
                ("MT-035", "migration-task", t("Ablösung der JSP-Seiten und Add-ons", "Removal of the JSP pages and add-ons"), 6, t("Aufgabe der Code-Analyse ohne Anforderung: zwölf JSP-Seiten und zwei Add-ons entfallen", "task of the code analysis without a requirement: twelve JSP pages and two add-ons are removed"), ["HO-target-readiness#MT-035"])],
 "greenfield": [("PH-G1", "phase", t("Projektaufsetzung und Umgebungen", "Project setup and environments"), 5, t("Aufsetzen von Repository, Pipeline und drei Umgebungen", "setup of repository, pipeline and three environments"), [R["impex"]]),
                ("PH-G2", "phase", t("Datenbereinigung und Datenübernahme", "Data cleanup and data transfer"), 8, t("Bereinigung und Übernahme der Maschinen- und Kundendaten", "cleanup and transfer of machine and customer data"), [R["impex"]])],
 "sapcc": [("PH-S1", "phase", t("Projektaufsetzung und Umgebungen", "Project setup and environments"), 5, t("Aufsetzen von Repository, Pipeline und drei Umgebungen", "setup of repository, pipeline and three environments"), [R["impex"]])],
 "spryker": [("PH-P1", "phase", t("Projektaufsetzung und Umgebungen", "Project setup and environments"), 4, t("Aufsetzen von Repository, Pipeline und drei Umgebungen", "setup of repository, pipeline and three environments"), [R["impex"]])],
}

SEED = {"migration": [(t("Projektaufsetzung auf der bestehenden Umgebung", "Project setup on the existing environment"), 3), (t("Abnahmebegleitung", "Acceptance support"), 4)],
        "migration-refactoring": [(t("Projektaufsetzung auf der bestehenden Umgebung", "Project setup on the existing environment"), 3), (t("Bereinigung toten Codes", "Removal of dead code"), 2), (t("Abnahmebegleitung", "Acceptance support"), 4)],
        "rebuild": [(t("Projektaufsetzung und Umgebungen", "Project setup and environments"), 5), (t("Datenbereinigung und Datenübernahme", "Data cleanup and data transfer"), 8)]}
SCENARIOS = [{"id": "migration", "label": "Migration", "option": "brownfield", "classes": ["client", "tech-migration"]},
             {"id": "migration-refactoring", "label": "Migration + Refactoring", "option": "brownfield", "classes": ["client", "tech-migration", "refactoring"], "subtract_savings": True},
             {"id": "rebuild", "label": t("Neubau", "Rebuild"), "option": "greenfield", "classes": ["client", "tech-migration"]}]
# scenario -> (id, title, pd, derivation, evidence, seed decision, reason): the consolidator keeps / adjusts / drops each seed
SPHASES = {"migration": [("PH-M1", SEED["migration"][0][0], 3, t("Pipeline und Umgebungen bestehen; nur die Zielversion wird aufgesetzt", "pipeline and environments exist; only the target version is set up"), [HO("TR-01")], "keep", t("wie vorgeschlagen", "as proposed")),
                         ("PH-M2", SEED["migration"][1][0], 5, t("vier Wochen Begleitung der Abnahme durch den Kunden mit Fehlerbehebung", "four weeks of support of the client's acceptance incl. bug fixing"), [R["impex"]], "adjust", t("fünf statt vier Personentage: die Abnahme umfasst zwei Sites", "five instead of four person days: the acceptance covers two sites"))],
           "migration-refactoring": [("PH-R1", SEED["migration-refactoring"][0][0], 3, t("Pipeline und Umgebungen bestehen; nur die Zielversion wird aufgesetzt", "pipeline and environments exist; only the target version is set up"), [HO("TR-01")], "keep", t("wie vorgeschlagen", "as proposed")),
                                     ("PH-R3", SEED["migration-refactoring"][2][0], 5, t("vier Wochen Begleitung der Abnahme durch den Kunden mit Fehlerbehebung", "four weeks of support of the client's acceptance incl. bug fixing"), [R["impex"]], "adjust", t("fünf statt vier Personentage: die Abnahme umfasst zwei Sites", "five instead of four person days: the acceptance covers two sites"))],
           "rebuild": [("PH-N1", SEED["rebuild"][0][0], 5, t("Aufsetzen von Repository, Pipeline und drei Umgebungen", "setup of repository, pipeline and three environments"), [R["impex"]], "keep", t("wie vorgeschlagen", "as proposed")),
                       ("PH-N2", SEED["rebuild"][1][0], 8, t("Bereinigung und Übernahme der Maschinen- und Kundendaten", "cleanup and transfer of machine and customer data"), [R["impex"]], "keep", t("wie vorgeschlagen", "as proposed"))]}
SEED_DROP = [("migration-refactoring", SEED["migration-refactoring"][1][0], t("die Zeile RF-01 trägt die Bereinigung der Versandlogik; weiteren toten Code nennt die Code-Analyse nicht", "row RF-01 carries the removal of the sending logic; the code analysis names no further dead code"))]

SH = {k: t(k, v) for k, v in (("Schaetzung", "Estimation"), ("Abgrenzungen", "Exclusions"), ("Summen", "Totals"), ("Zuschlaege_und_Phasen", "Surcharges_and_Phases"), ("Risiken", "Risks"))}   # claim target sheets
EF = ["req_id", "option", "position", "position_title", "epic", "approach", "size", "mechanism", "mechanism_kind", "version_plan", "evidence", "derivation", "estimation_assumption", "carried_by",
      "depends_on", "integration_on_tr", "lookup_question", "lookup_locators", "lookup_answer", "lookup_extends", "lookup_status", "size_before_lookup", "client_attention", "confidence"] + (["is_size", "is_note", "saved_size", "saves"] if SC else [])
MK = {"standard": "module", "partial": "module", "custom": "custom-code", "keep": "existing-code", "adapt": "existing-code", "convert-to-standard": "module", "rebuild": "extension-point", "retire": "existing-code", "new": "module"}
LOOKUP = {("FR-011", "brownfield"): {"lookup_question": t("Liegt die Dokumentlogik von FR-011 in einem Dienst oder in drei Controllern?", "Does the document logic of FR-011 sit in one service or in three controllers?"),
                                     "lookup_locators": ["src/shopcore/src/com/shop/core/document/ShopDocumentService.java:1-40"], "lookup_answer": t("ein Dienst, von zwei Controllern aufgerufen", "one service, called by two controllers"),
                                     "lookup_extends": HO("FR-011"), "lookup_status": "done", "size_before_lookup": "L"}}


def rows_of(o, reqs):
    """estimation rows of option o for the requirement ids reqs: one row per requirement, plus its positions when it is above XXL"""
    out = []
    for r in reqs:
        if r not in KIND[o["id"]]: continue   # a refactoring row has no greenfield row
        appr, size, ev, mech, der, asm = KIND[o["id"]][r]
        base = {f: "" for f in EF}
        base.update({"req_id": r, "option": o["id"], "epic": EPIC[r], "approach": appr, "mechanism": mech, "mechanism_kind": MK[appr], "version_plan": "2.0", "evidence": "; ".join(ev),
                     "derivation": der[0], "estimation_assumption": asm[0] if asm else "", "carried_by": t("QA-Zuschlag", "QA surcharge") if r == "TR-02" and o["id"] == "brownfield" else "",
                     "depends_on": "TR-01" if r in ("FR-009", "FR-010", "FR-014", "FR-016", "FR-017") else ("TR-02" if r == "FR-030" else ""),
                     "integration_on_tr": "yes" if r in ("FR-009", "FR-010", "FR-014", "FR-016", "FR-017", "FR-030") else "no", "client_attention": "yes" if r == "FR-030" else "no", "confidence": "medium"})
        base.update({k: "; ".join(v) if isinstance(v, list) else v for k, v in LOOKUP.get((r, o["id"]), {}).items()})
        if (r, o["id"]) in SAVE: base.update(saved_size=SAVE[(r, o["id"])][0], saves="; ".join(SAVE[(r, o["id"])][1]))
        if isinstance(size, list):
            out.append(dict(base, size=""))
            for i, s in enumerate(size, 1):
                ip = IS.get((r, o["id"], str(i)), ("", ""))
                out.append(dict(base, position=str(i), position_title=t(f"Teil {i} von {r}", f"Part {i} of {r}"), size=s, estimation_assumption="", is_size=ip[0], is_note=ip[1], saved_size="", saves=""))
        else:
            ip = IS.get((r, o["id"]), ("", "")); out.append(dict(base, size=size, is_size=ip[0], is_note=ip[1]))
    return out


def dev_pd(oid, reqs=None):
    return round(sum(sum(MAP[x] for x in s) if isinstance(s, list) else MAP[s] for r, (_, s, *_rest) in KIND[oid].items() if reqs is None or r in reqs), 1)


def table(fields, rows, why=""):
    if not rows and why: return why   # an empty table section says why (md_to_json warns on a silent empty table)
    out = ["| " + " | ".join(fields) + " |", "|" + "---|" * len(fields)]
    for r in rows:
        vals = [r.get(f, "") for f in fields] if isinstance(r, dict) else list(r)
        out.append("| " + " | ".join(str(x).replace("|", "/") for x in vals) + " |")
    return "\n".join(out)


def tech(): return "; ".join(f"{o['label']}: 2.0" for o in OPTS)


# --------------------------------------------------------------------------- claims (targets name option rows -> applicability of per-pack critics)
def claims1():
    o0, o1 = OPTS[0], OPTS[-1]
    c = [("C-epic-01-001", "fact", "Assigning machines to users of the same unit is a permission of the standard unit administration; the requirement needs configuration of two roles only.", R["units"], f"D1/{SH['Schaetzung']}#FR-015@{o0['id'] if o0['start'] == 'greenfield' else o1['id']}"),
         ("C-epic-01-002", "assessment", "The installed base has no standard counterpart in a new build: machine, spare part relation and service events are a custom entity, cut into three sprint-sized positions for the equipment list.", R["entities"], f"D1/{SH['Schaetzung']}#FR-009@{o1['id']}"),
         ("C-epic-01-003", "fact", "The CSV export of the machine list is one export profile of the Import/Export module.", R["impex"], f"D1/{SH['Schaetzung']}#FR-013@{o1['id']}"),
         ("C-epic-01-004", "assessment", "The nightly ERP delivery of machines, spare parts and service events is the dependency the whole epic rests on.", "SRC-001#p2", f"D1/{SH['Abgrenzungen']}#AE-01")]
    if o0["id"] == "brownfield":
        c += [("C-epic-01-005", "fact", "The equipment list runs in the own module today and is kept unchanged in the migration.", HO("FR-009"), f"D1/{SH['Schaetzung']}#FR-009@brownfield"),
              ("C-epic-01-006", "assessment", "The document logic sits in one service called by two controllers, so the migration adapts one service.", HO("FR-011"), f"D1/{SH['Schaetzung']}#FR-011@brownfield")]
    elif len(OPTS) > 1:
        c += [("C-epic-01-005", "fact", "Documents per object are standard in the file manager of the second technology.", R["media"], f"D1/{SH['Schaetzung']}#FR-011@{o1['id']}")]
    return c


def claims2():
    o1 = OPTS[-1]
    extra = [("C-epic-02-004", "fact", "The interface prerequisites of the new storefront are a technical migration row sized for both options.", "HO-target-readiness#MT-001", f"D1/{SH['Schaetzung']}#TM-01@brownfield"),
             ("C-epic-02-005", "assessment", "Moving the maintenance notification to standard templates saves the migration of the own notification logic.", "HO-customization-depth#shopnotify", f"D1/{SH['Schaetzung']}#RF-01@brownfield")] if SC else []
    return extra + [("C-epic-02-001", "fact", "Successor products are a product reference type the storefront renders out of the box.", R["vendor"], f"D1/{SH['Schaetzung']}#FR-023@{o1['id']}"),
            ("C-epic-02-002", "assessment", "The delivery split by plant is larger than a sprint and is cut into positions.", R["checkout"], f"D1/{SH['Schaetzung']}#FR-030@{o1['id']}"),
            ("C-epic-02-003", "assessment", "The ERP synchronisation gets schedule and error report from the Import/Export module; the mapping is built.", R["impex"], f"D1/{SH['Schaetzung']}#TR-01@{o1['id']}")]


def claims_sum():
    return [("C-SUM-001", "fact", "Every requirement of the list is estimated once per option.", "analysis/scopes/epic-01.md; analysis/scopes/epic-02.md", f"D1/{SH['Summen']}"),
            ("C-SUM-002", "assessment", "The fixed phases per option carry project setup and the work no requirement describes; nothing in them repeats a requirement row.", R["impex"], f"D1/{SH['Zuschlaege_und_Phasen']}"),
            ("C-SUM-003", "assessment", "The delivery split by plant is the requirement that needs a decision before it is built.", R["checkout"], f"D1/{SH['Risiken']}#R-01")]


def applicable(target):
    ids = {o["id"] for o in OPTS}; ref = target.split("#", 1)[1] if "#" in target else ""
    opts = [s for s in ref.split("@")[1:] if s in ids]
    return [c for c in CRITICS if not c.startswith("standard-") or not opts or any(c == f"standard-{PACK[o]}" for o in opts)]


def analysis(scope, wave, reqs, ass, claims, taken, summary):
    rows = [r for o in OPTS for r in rows_of(o, reqs)]
    return "\n".join([
        f"# Fit estimation: {scope}", "",
        f"- **scope:** {scope}", "- **agent:** analyst-" + scope, f"- **technology:** {tech()}",
        f"- **wave:** {wave}", "- **status:** final", "- **round:** 1", "",
        "## Summary", "", summary, "",
        "## Estimation", "", table(EF, rows), "",
        "## Assumptions", "", table(["id", "requirement_ids", "assumption", "kind", "effect"], ass), "",
        "## Assumptions taken", "", table(["id", "affects", "question", "reading_taken", "assumption", "why", "if_not", "alternatives"], taken, "No requirement of this chunk is broad enough to need a reading."), "",
        "## Claims", "", table(["id", "type", "statement", "evidence", "target", "supersedes"], [(c[0], c[1], c[2], c[3], c[4], "") for c in claims]), "",
        "## Open questions", "", table(["id", "to", "question", "why_needed", "status", "answer"], [], "No question to another chunk or to the lead."), "",
    ])


DISPUTE = "C-epic-02-001"   # scenarios: the client critic doubts a standard statement - no score, routed to the standard critic


def critic(scope, which, claims, summary):
    scores = [(c[0], 9 if i % 2 else 8, "confirmed", "", "", "") + (("size-plausibility",) if SC and which == "client" else ()) for i, c in enumerate(claims) if which in applicable(c[4])]
    if SC and which == "client": scores = [(x[0], 3, "unsupported", "The code analysis lists successor products as a gap of today's shop; I doubt the storefront of the pinned release shows them without an own component.", "HO-requirements-coverage#FR-023", "the standard critic confirms or corrects the reference row", "standard-dispute") if x[0] == DISPUTE else x for x in scores]
    return "\n".join([
        f"# Gauntlet score: {scope} / {which} / round 1", "",
        f"- **scope:** {scope}", f"- **critic:** {which}", "- **round:** 1", "",
        "## Scores", "", table(["claim_id", "score", "verdict", "issue", "counter_evidence", "fix_hint"] + (["ground"] if SC and which == "client" else []), scores), "",
        "## Missing claims", "", "- ", "",
        "## Estate observations", "", "- ", "",
        "## Summary", "", summary, "",
    ])


def requirements_workbook():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Functional Requirements"; ws.append(HDR)
    for r in FR: ws.append(list(r))
    ws2 = wb.create_sheet("Technical Requirements"); ws2.append(HDR)
    for r in TR: ws2.append(list(r))
    os.makedirs(os.path.join(T, "input/requirements"), exist_ok=True); wb.save(os.path.join(T, "input/requirements/requirements_fixture.xlsx"))
    m = J("requirements_mapping.json")
    cols = {"id": "Req ID", "epic": "Epic", "title": "Title", "description": "Description", "acceptance_criteria": "Acceptance criteria",
            "exclusions": "Exclusions", "references": "References", "phase": "Release", "priority": "Priority", "sources": "Sources"}
    m["sheets"] = [{"sheet": "Functional Requirements", "group": "functional", "id_prefix": "FR-", "header_row": 1, "columns": cols, "extra_columns": []},
                   {"sheet": "Technical Requirements", "group": "technical", "id_prefix": "TR-", "header_row": 1, "columns": cols, "extra_columns": []}]
    m["phase_values_in_scope"] = ["MVP"]; W("requirements_mapping.json", m)


def fill_run():
    p = J("run.json")
    p["engagement"].update({"consultancy": "Fixture Consulting", "client": "Fixture Retail GmbH",
                            "client_context": t("B2B-Händler für Industriemaschinen, Spielzeugdaten.", "B2B distributor of industrial machines, toy data."), "title": t("Aufwandsschätzung Fixture", "Effort estimate fixture"),
                            "run_title": t("Aufwandsschätzung je Option", "Effort estimate per option")})
    p["estimation"] = {**p.get("estimation", {}), "unit": t("Personentag (PT)", "person day (PD)"), "day_rate": DAY_RATE}
    p["target"] = {**p.get("target", {}), "version": "2.0", "plan": "Standard", "frontend": "generic storefront"}
    p.setdefault("deliverables", {}).setdefault("D1", {})["file"] = "Fit_Estimation_Generic.xlsx"
    if OPTIONS: p["options"] = OPTIONS
    if BROWN: p["repo"] = {**p.get("repo", {}), "path": os.path.join(T, "client-repo")}
    if SC:
        p["requirements"] = {**p.get("requirements", {}), "decisions": {"NR-001": {"merge_into": "FR-010", "basis": "A-01"}, "NR-002": {"drop": True, "basis": "A-02"}}}
        p["scenarios"] = SCENARIOS
        p["estimation"].update({"integration_platform": "Integration Suite", "fixed_phases_seed": {k: [{"phase": ph, "pd": pd} for ph, pd in v] for k, v in SEED.items()}})
    W("run.json", p)


def corpus():
    w("corpus/text/SRC-001.md", "\n".join([
        "# SRC-001 Workshop notes installed base (2026-05-12)", "",
        "SRC-001#p1 The customer portal must show the machines installed at a customer site.",
        "SRC-001#p2 The ERP delivers the installed base per unit every night, including spare part numbers and service events.",
        "SRC-001#p3 Service booking is out of scope for this project.", ""]))
    W("corpus/index.json", {"sources": {"SRC-001": {"title": "Workshop notes installed base", "type": "notes", "date": "2026-05-12",
                                                    "origin": "workshop 2026-05-12", "quality": "good", "path": "text/SRC-001.md"}}})


def brownfield_inputs():
    """toy code-analysis handover artefacts (as `dbcx handover export` writes them), a toy client repository, vendor standard code,
    client-assumptions of an earlier run (A-01 answered by the client, A-02 open)"""
    units = {"shopcore": "src/shopcore", "shopstorefront": "src/shopstorefront", "shoperp": "src/shoperp"}
    impl = {r: (["shoperp"] if r.startswith("TR-") else ["shopcore", "shopstorefront"]) for r in EPIC if not r.startswith(("TM-", "RF-"))}
    for u, p in units.items():
        w(f"client-repo/{p}/src/com/shop/{u}/{u.capitalize()}Service.java", "\n".join([f"package com.shop.{u};", "", f"public class {u.capitalize()}Service {{"] + [f"    // line {i}" for i in range(4, 60)] + ["}", ""]))
    w("client-repo/src/shopcore/src/com/shop/core/document/ShopDocumentService.java", "\n".join(["package com.shop.core.document;", "", "public class ShopDocumentService {"] + [f"    // line {i}" for i in range(4, 60)] + ["}", ""]))
    if SC: units["shopnotify"] = "src/shopnotify"; impl["FR-014"] = ["shopnotify"]
    cov = [{"req_id": r, "verdict": "covered-custom" if r not in ("FR-023", "FR-024") else "gap", "units": impl[r] if r not in ("FR-023", "FR-024") else [],
            "evidence": [f"{units[u]}/src/com/shop/{u}/{u.capitalize()}Service.java:5-20" for u in impl[r]] if r not in ("FR-023", "FR-024") else [],
            "claimed_by": ["C-D3-001"] if r == "FR-009" else [], "rid": r} for r in impl]
    if SC:
        for c in cov:
            if c["req_id"] == "FR-011": c.update(today="custom", description_gap=t("Zertifikate erscheinen erst nach der Freigabe durch den Service; abgelaufene Handbücher bleiben als Archiv abrufbar.", "Certificates appear only after the service released them; expired manuals stay available as an archive."))
            if c["req_id"] == "FR-030": c.update(today="partial", current_state_note=t("Die Aufteilung je Werk zeigt der Checkout heute als eigene Zwischenseite mit Liefertermin je Werk.", "Today the checkout shows the split per plant on its own step with a delivery date per plant."))
    env = lambda typ, data: {"artefact_type": typ, "run": "2026-09-code-analysis-fixture", "method": "code-analysis", "released": "2026-09-20", "label": "fixture", "data": data}
    W("ho/requirements-coverage.json", env("requirements-coverage", {"coverage": cov, "claims": [{"id": "C-D3-001", "evidence": ["src/shopcore/src/com/shop/shopcore/ShopcoreService.java:21-40"]}]}))
    mts = [{"id": "MT-035", "topic": "frontend", "task": "Remove the JSP pages and add-ons", "affected_requirements": [], "units": ["shopstorefront"], "evidence": ["src/shopstorefront/src/com/shop/shopstorefront/ShopstorefrontService.java:5-9"], "rid": "MT-035"}]
    if SC: mts = [{"id": "MT-001", "topic": "api", "task": "Enable the OCC prerequisites of the composable storefront: cmsocc, a public OAuth client, CORS for the shop domains", "finding": "cmsocc is not in localextensions.xml", "affected_requirements": ["FR-009", "FR-010"], "units": ["shopcore"], "evidence": ["src/shopcore/src/com/shop/shopcore/ShopcoreService.java:5-9"], "rid": "MT-001"},
                  {"id": "MT-020", "topic": "media", "task": "Serve the equipment documents through the media storage of the target", "finding": "ShopDocumentService reads a local folder", "affected_requirements": ["FR-011"], "units": ["shopcore"], "evidence": ["src/shopcore/src/com/shop/core/document/ShopDocumentService.java:1-40"], "rid": "MT-020"}] + mts
    W("ho/target-readiness.json", env("target-readiness", {"migration_tasks": mts, "features": []}))
    disp = {"shopnotify": ("refactor-to-standard", "The own notification job NotifyJob duplicates the standard notification templates and the standard scheduling.")}
    W("ho/customization-depth.json", env("customization-depth", {"units": {u: {"unit": u, "classification": {"depth": "medium", "disposition": disp.get(u, ("adapt-api", ""))[0], "disposition_rationale": disp.get(u, ("", ""))[1]},
                                                                            "requirements": [{"req_id": "FR-014", "contribution": "implements"}] if u == "shopnotify" else [], "summary": ""} if SC else {"unit": u, "classification": {"depth": "medium", "disposition": "adapt-api"}} for u in units}}))
    W("ho/code-inventory.json", env("code-inventory", {"units": [{"name": u, "path": p, "category": "core", "rid": u} for u, p in units.items()]}))
    W("ho/client-assumptions.json", env("client-assumptions", {"assumptions": [
        {"assumption_id": "A-01", "id": "Q-D3-1", "from": "D3", "question": t("Läuft die Produktion auf der bestehenden Cloud-Umgebung weiter?", "Does production keep running on the existing cloud environment?"),
         "assumption": t("Die Produktion läuft auf der bestehenden Cloud-Umgebung weiter.", "Production keeps running on the existing cloud environment."), "why": t("Die Umgebung ist bezahlt und eingerichtet.", "The environment is paid for and set up."),
         "if_not": t("Eine neue Umgebung verlängert die Projektaufsetzung um fünf Personentage.", "A new environment extends the project setup by five person days."), "effect": "", "affects": ["FR-015@brownfield"], "options": [], "proceeding_under": "",
         "answers": [{"option": "", "text": t("ja", "yes"), "weight": "fact", "by": "client", "at": "2026-09-22T10:00:00", "channel": "import-assumptions", "status": "received", "type": "client-fact"}], "status": "answered_draft"},
        {"assumption_id": "A-02", "id": "Q-D3-2", "from": "D3", "question": t("Bleibt der CSV-Export der Maschinenliste unverändert?", "Does the CSV export of the machine list stay unchanged?"),
         "assumption": t("Der CSV-Export der Maschinenliste bleibt in der Migration unverändert.", "The CSV export of the machine list stays unchanged in the migration."), "why": t("Der Export wird heute täglich genutzt und ist nicht beanstandet.", "The export is used daily today and has no complaints."),
         "if_not": t("Ein geänderter Export kostet in der Migration einen Personentag mehr bei FR-013.", "A changed export costs one person day more for FR-013 in the migration."), "effect": "", "affects": ["FR-013@brownfield"], "options": [], "proceeding_under": "", "answers": [], "status": "open"}]}))
    w(f"reference/vendor-code/{VENDOR.split(':')[0]}", "\n".join(f"// standard code line {i}" for i in range(1, 200)) + "\n")


def scenario_expected():
    """per scenario the size tokens of its platform rows, its saving, its integration platform rows and its fixed phases"""
    out = []
    for s in SCENARIOS:
        o = s["option"]; rows = [(r, v) for r, v in KIND[o].items() if CLS.get(r, "client") in s["classes"]]
        plat = [x for r, (_, sz, *_r) in rows for x in (sz if isinstance(sz, list) else [sz])]
        isz = [v[0] for k, v in IS.items() if k[1] == o and CLS.get(k[0], "client") in s["classes"]]
        sav = [v[0] for k, v in SAVE.items() if k[1] == o and s.get("subtract_savings")]
        out.append({"id": s["id"], "label": s["label"], "option": o, "platform": plat, "saving": sav, "is": isz, "phases": [x[2] for x in SPHASES[s["id"]]]})
    return out


def expected():
    return {"variant": VARIANT, "day_rate": DAY_RATE, "map": MAP, "surcharges": {"PM": 15, "SA": 10, "BA": 10, "QA": 20}, "critics": CRITICS, "scenarios": scenario_expected() if SC else [],
            "options": [{"id": o["id"], "label": o["label"], "start": o["start"],
                         "sizes": [x for r, (_, s, *_r) in KIND[o["id"]].items() for x in (s if isinstance(s, list) else [s])],
                         "phases": [p[3] for p in PHASES[o["id"]]]} for o in OPTS]}


def classification_md():
    """the classification agent's proposal (the smoke converts it with `dbcx md_to_json classification`)"""
    rows = [("CL-01", "refactoring", "", TMR[1][3], TMR[1][4], "The unit replaces standard notification templates; not needed to run today's functions on the new storefront."),
            ("CL-02", "tech-migration", "", TMR[0][3], TMR[0][4], "No client row describes the interface prerequisites of the new storefront."),
            ("CL-03", "client-row", "FR-011", "", "", "Serving the documents through the target's media storage is part of FR-011 as the shop has it today."),
            ("CL-04", "drop", "", "", "", "The removal of the old pages is carried by the project setup phase."),
            ("CL-05", "client-row", "FR-016", "", "", "Filtering the spare parts by assembly is part of FR-016 as the shop has it today.")]
    w("analysis/classification.md", "\n".join(["# Row classification (proposal)", "", "- **agent:** consolidate-classification", "- **status:** final", "", "## Summary", "",
        "Five candidates: one refactoring, one technical migration, one part of FR-011, one dropped, one derived row merged into FR-016. The close call is CL-04.", "", "## Candidates", "",
        table(["candidate_id", "proposed_class", "client_rows", "title_de", "description_de", "rationale"], rows), ""]))


def derived_rows():
    """the rows a code analysis proposes (requirements-set extra.origin = code-analysis) - the client decided them in run.json"""
    p = os.path.join(T, "state", "requirements.json"); d = json.load(open(p, encoding="utf-8"))
    ex = lambda h, why: {"origin": "code-analysis", "proposed_handling": h, "client_decision": "", "rationale": why, "units": ["shopcore"]}
    d["requirements"] += [
        {"group": "proposed", "id": "NR-001", "epic": "Installed base", "title": t("Wartungsintervall je Maschine anzeigen", "Show the maintenance interval per machine"),
         "description": t("Die Detailseite zeigt das nächste Wartungsdatum und das Intervall der Maschine.", "The detail page shows the next maintenance date and the interval of the machine."),
         "acceptance_criteria": t("1) Datum und Intervall auf der Detailseite", "1) date and interval on the detail page"), "exclusions": "", "references": ["FR-010"], "phase": "MVP", "sources": ["code-analysis:shopcore"], "priority": "",
         "extra": ex("merge-into-existing", "FR-010 lists the master data of a machine; the shop shows the interval today.")},
        {"group": "proposed", "id": "NR-002", "epic": "Catalog", "title": t("Herstellerlogo bei der Systeminitialisierung", "Vendor logo at system initialisation"),
         "description": t("Bei jeder Initialisierung wird ein Medienobjekt mit dem Herstellerlogo angelegt.", "Every initialisation creates a media object with the vendor logo."),
         "acceptance_criteria": "", "exclusions": "", "references": [], "phase": "MVP", "sources": ["code-analysis:shopcore"], "priority": "", "extra": ex("drop", "No customer sees the media object.")},
        {"group": "proposed", "id": "NR-003", "epic": "Installed base", "title": t("Ersatzteile nach Baugruppe filtern", "Filter spare parts by assembly"),
         "description": t("Die Ersatzteilliste einer Maschine lässt sich nach Baugruppe filtern.", "The spare parts list of a machine can be filtered by assembly."),
         "acceptance_criteria": t("1) Filter nach Baugruppe", "1) filter by assembly"), "exclusions": "", "references": ["FR-016"], "phase": "Phase 2", "sources": ["code-analysis:shopcore"], "priority": "",
         "extra": ex("merge-into-existing", "FR-016 lists the spare parts; the shop filters them by assembly today.")}]   # no client decision: `dbcx classify` lists it
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- systems: the inputs of a multi-system run
SYSTEMS = [
    {"id": "commerce", "label": "E-Commerce", "options": [{"id": "sapcc", "label": "SAP Commerce Cloud", "pack": "sap-commerce", "start": "greenfield"},
                                                         {"id": "shopware", "label": "Shopware", "pack": "_generic", "start": "greenfield"}], "landscape_ids": ["SYS-COM"]},
    {"id": "middleware", "label": "Integration Suite", "options": [{"id": "is", "label": "Integration Suite", "pack": "_generic", "start": "brownfield"}], "depends_on": "commerce", "landscape_ids": ["SYS-CPI"]},
    {"id": "cdc", "label": "SAP Customer Data Cloud", "options": [{"id": "cdc", "label": "SAP Customer Data Cloud", "pack": "_generic", "start": "greenfield"}], "landscape_ids": ["SYS-CDC"]},
    {"id": "s4", "label": "SAP S/4HANA", "estimated_by": "client", "landscape_ids": ["SYS-ERP"]},
    {"id": "magnolia", "label": "Magnolia (CMS)", "estimated_by": "partner", "owner_label": t("CMS-Agentur", "CMS agency"), "landscape_ids": ["SYS-CMS"]}]
SYS_FR = [("FR-001", t("Konto", "Account"), t("Registrierung", "Registration"), t("Kunden registrieren sich mit E-Mail und Passwort.", "Customers register with e-mail and password."), "MVP", "must"),
          ("FR-002", t("Bestellung", "Ordering"), t("Bestellstatus", "Order status"), t("Kunden sehen den Status ihrer Bestellungen.", "Customers see the status of their orders."), "MVP", "must"),
          ("FR-003", t("Inhalte", "Content"), t("Ratgeberseiten", "Guide pages"), t("Redakteure pflegen Ratgeberseiten mit Produktbezug.", "Editors maintain guide pages with product links."), "Phase 2", "should"),
          ("FR-004", t("Kundenbindung", "Loyalty"), t("Bonuspunkte", "Bonus points"), t("Kunden sammeln Bonuspunkte je Bestellung.", "Customers collect bonus points per order."), "Phase 2", "could")]
SYS_TA = [("TA-01", "FR-001", t("Registrierung über CDC", "Registration through CDC"), t("Die Registrierung läuft über die Screen-Sets von CDC, der Shop legt das Kundenkonto an.", "Registration runs through the CDC screen-sets, the shop creates the customer account."), "Commerce, CDC", "MVP"),
          ("TA-02", "FR-002", t("Bestellstatus aus S/4", "Order status from S/4"), t("Statusänderungen kommen über die Integration Suite aus S/4 in den Shop.", "Status changes come from S/4 into the shop through the Integration Suite."), "SAP S/4HANA / Integration Suite", "MVP"),
          ("TA-03", "FR-003", t("Ratgeber-Komponenten", "Guide components"), t("Ratgeberseiten werden in Magnolia gepflegt; ein Bonus-Service auf BTP liefert Empfehlungen.", "Guide pages are maintained in Magnolia; a bonus service on BTP delivers recommendations."), "Magnolia; BTP", "Phase 2"),
          ("TA-04", None, t("Betriebsmonitoring", "Operations monitoring"), t("Alle Schnittstellen werden zentral überwacht.", "Every interface is monitored centrally."), "Integration Suite", "MVP")]
SYS_IF = [("IF-01", t("Kundendaten", "Customer data"), t("Profil und Einwilligungen nach jeder Änderung", "profile and consents after every change"), "SAP Customer Data Cloud", "SYS-COM", "CPI"),
          ("IF-02", t("Bestellungen", "Orders"), t("Bestellung an S/4, Status zurück", "order to S/4, status back"), "SYS-COM", "SAP S/4HANA", "Integration Suite"),
          ("IF-03", t("Bonuspunkte", "Bonus points"), t("Punkte je Bestellung aus dem Bonus-Service", "points per order from the bonus service"), "SAP BTP", "Commerce", "")]
LANDSCAPE_CSV = [["System-ID", "Systemname", "Typ", "Beschreibung", "Verantwortlich", "Aliasse"],
                 ["SYS-COM", "SAP Commerce Cloud", "commerce", "Online-Shop", "E-Commerce", "Commerce; Hybris"],
                 ["SYS-CPI", "SAP Integration Suite", "middleware", "Integrationsplattform", "IT", "CPI"],
                 ["SYS-CDC", "SAP Customer Data Cloud", "identity", "Kundenidentitäten und Einwilligungen", "Marketing", "Gigya"],
                 ["SYS-ERP", "SAP S/4HANA", "erp", "ERP", "Finanzen", "S4"],
                 ["SYS-CMS", "Magnolia", "cms", "Content-Management", "Marketing", ""],
                 ["SYS-BTP", "SAP BTP", "platform", "Erweiterungsplattform (nicht Teil dieser Schätzung)", "IT", "BTP"]]
LANDSCAPE_MAP = "id=System-ID,name=Systemname,kind=Typ,description=Beschreibung,owner=Verantwortlich,aliases=Aliasse"


def systems_inputs():
    """the inputs of the systems variant: run.json systems, the client workbook + mapping, the landscape CSV (convert it with
    `dbcx landscape_import input/landscape/systemlandschaft.csv --map <LANDSCAPE_MAP>`; fixture_inputs.json carries the map)"""
    import csv, openpyxl
    p = J("run.json"); p["engagement"].update({"consultancy": "Fixture Consulting", "client": "Fixture Retail GmbH", "title": t("Aufwandsschätzung Fixture", "Effort estimate fixture"),
                                                "client_context": t("Händler mit Online-Shop, Spielzeugdaten.", "Retailer with an online shop, toy data."), "run_title": t("Aufwandsschätzung je System", "Effort estimate per system")})
    p["target"] = {**p.get("target", {}), "version": "2.0", "plan": "Standard", "frontend": "generic storefront"}
    p.setdefault("deliverables", {}).setdefault("D1", {})["file"] = "Fit_Estimation_Systems.xlsx"; p["systems"] = SYSTEMS; W("run.json", p)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "FR"
    ws.append([t("Anforderungsliste des Kunden (Stand 09/2026)", "Client requirement list (as of 09/2026)")])
    ws.append(["Nr.", t("Bereich", "Area"), t("Anforderung", "Requirement"), t("Beschreibung", "Description"), "Phase", "Prio"])
    for r in SYS_FR[:2]: ws.append(list(r))
    ws.append([]); ws.append([None, t("Weitere Anforderungen", "Further requirements")])   # a blank line and a section line: carried, no requirement
    for r in SYS_FR[2:]: ws.append(list(r))
    ws.column_dimensions["C"].width = 30; ws.column_dimensions["D"].width = 60
    ws2 = wb.create_sheet("Technik"); ws2.append(["TA-ID", "FR-Bezug", t("Titel", "Title"), t("Beschreibung", "Description"), t("Betroffene Systeme", "Affected systems"), "Phase"])
    for r in SYS_TA: ws2.append(list(r))
    ws3 = wb.create_sheet(t("Schnittstellen", "Interfaces")); ws3.append(["IF-ID", "Name", t("Beschreibung", "Description"), t("Quelle", "Source"), t("Ziel", "Target"), t("Über", "Via")])
    for r in SYS_IF: ws3.append(list(r))
    os.makedirs(os.path.join(T, "input/requirements"), exist_ok=True); wb.save(os.path.join(T, "input/requirements/client_requirements.xlsx"))
    m = J("requirements_mapping.json")
    m["sheets"] = [{"sheet": "FR", "group": "functional", "header_row": 2, "passthrough": True, "estimate": False,
                    "columns": {"id": "Nr.", "epic": t("Bereich", "Area"), "title": t("Anforderung", "Requirement"), "description": t("Beschreibung", "Description"), "phase": "Phase", "priority": "Prio"}, "extra_columns": []},
                   {"sheet": "Technik", "group": "technical", "id_prefix": "TA-", "header_row": 1, "rollup_to_field": "FR-Bezug", "systems_field": t("Betroffene Systeme", "Affected systems"),
                    "columns": {"id": "TA-ID", "title": t("Titel", "Title"), "description": t("Beschreibung", "Description"), "phase": "Phase"}, "extra_columns": []},
                   {"sheet": t("Schnittstellen", "Interfaces"), "group": "interfaces", "kind": "interfaces", "id_prefix": "IF-", "header_row": 1,
                    "columns": {"id": "IF-ID", "title": "Name", "description": t("Beschreibung", "Description"), "from": t("Quelle", "Source"), "to": t("Ziel", "Target"), "via": t("Über", "Via")}, "extra_columns": []}]
    m["phase_values_in_scope"] = ["MVP"]; W("requirements_mapping.json", m)
    os.makedirs(os.path.join(T, "input/landscape"), exist_ok=True)
    with open(os.path.join(T, "input/landscape/systemlandschaft.csv"), "w", encoding="utf-8", newline="") as fh: csv.writer(fh, delimiter=";").writerows(LANDSCAPE_CSV)
    W("fixture_inputs.json", {"landscape_file": "input/landscape/systemlandschaft.csv", "landscape_map": LANDSCAPE_MAP})


# the triage agent's output (the scope step): keeps, adds and removes pre-fills, one row `none`; the smoke converts it with
# `dbcx md_to_json triage analysis/triage/TRIAGE.md` after `dbcx impact plan` (which keeps an existing file) and applies it with `dbcx impact apply`
SYS_TRIAGE = [
    ("TA-01", "commerce", "yes", t("Der Shop legt das Kundenkonto aus der Registrierung an und zeigt das Profil.", "The shop creates the customer account from the registration and shows the profile."), t("Die Systemspalte nennt Commerce.", "The systems column names Commerce.")),
    ("TA-01", "cdc", "yes", t("Registrierung und Einwilligung laufen über die Screen-Sets; neue Felder im Profil.", "Registration and consent run through the screen-sets; new fields in the profile."), t("Die Systemspalte nennt CDC.", "The systems column names CDC.")),
    ("TA-02", "commerce", "yes", t("Das Kundenkonto zeigt den Bestellstatus aus dem ERP.", "The customer account shows the order status from the ERP."), t("Der Status wird im Konto angezeigt (FR-002).", "The status is shown in the account (FR-002).")),
    ("TA-02", "middleware", "yes", t("Ein Ablauf bringt jede Statusänderung aus dem ERP in den Shop.", "A flow carries every status change from the ERP into the shop."), t("Die Systemspalte nennt die Integration Suite.", "The systems column names the Integration Suite.")),
    ("TA-02", "s4", "yes", t("Das ERP meldet jede Statusänderung einer Bestellung.", "The ERP reports every status change of an order."), t("Die Systemspalte nennt SAP S/4HANA.", "The systems column names SAP S/4HANA.")),
    ("TA-03", "commerce", "yes", t("Die Storefront zeigt die Ratgeberseiten mit aktuellen Produktdaten.", "The storefront shows the guide pages with current product data."), t("Die Seiten verlinken Produkte des Shops.", "The pages link products of the shop.")),
    ("TA-03", "magnolia", "yes", t("Redakteure pflegen Ratgeberseiten mit Produktbezug.", "Editors maintain guide pages with product links."), t("Die Systemspalte nennt Magnolia.", "The systems column names Magnolia.")),
    ("TA-04", "middleware", "no", "", t("Die Überwachung betreibt das Betriebsteam im vorhandenen Werkzeug außerhalb dieser Schätzung.", "Monitoring is run by the operations team in its existing tool outside this estimate.")),
    ("TA-04", "none", "yes", "", t("Zentrale Überwachung ist ein Betriebsdienst außerhalb der Systeme dieses Laufs.", "Central monitoring is an operations service outside the systems of this run.")),
    ("IF-01", "cdc", "yes", t("Profil und Einwilligungen werden nach jeder Änderung gesendet.", "Profile and consents are sent after every change."), t("Quelle der Schnittstelle.", "Source of the interface.")),
    ("IF-01", "commerce", "yes", t("Der Shop übernimmt Profil und Einwilligungen in das Kundenkonto.", "The shop takes profile and consents into the customer account."), t("Ziel der Schnittstelle.", "Target of the interface.")),
    ("IF-01", "middleware", "no", "", t("CDC ruft den Shop direkt auf; die Integration Suite liegt nicht auf diesem Weg.", "CDC calls the shop directly; the Integration Suite is not on this flow.")),
    ("IF-02", "commerce", "yes", t("Der Shop übergibt jede Bestellung und übernimmt den Status.", "The shop hands over every order and takes the status back."), t("Quelle der Schnittstelle.", "Source of the interface.")),
    ("IF-02", "middleware", "yes", t("Ein Ablauf übersetzt Bestellung und Status zwischen Shop und ERP.", "A flow translates order and status between shop and ERP."), t("Die Schnittstelle läuft über die Integration Suite.", "The interface runs through the Integration Suite.")),
    ("IF-02", "s4", "yes", t("Das ERP legt die Bestellung an und meldet den Status zurück.", "The ERP creates the order and reports the status back."), t("Ziel der Schnittstelle.", "Target of the interface.")),
    ("IF-03", "commerce", "yes", t("Der Shop übernimmt die Bonuspunkte je Bestellung und zeigt sie im Konto.", "The shop takes the bonus points per order and shows them in the account."), t("Ziel der Schnittstelle; die Quelle liegt auf SAP BTP außerhalb dieses Laufs.", "Target of the interface; the source runs on SAP BTP outside this run."))]
SYS_TRIAGE_CLAIMS = [
    ("C-TRIAGE-001", "fact", t("Kundenidentitäten und Einwilligungen liegen in CDC, das Kundenkonto im Shop.", "Customer identities and consents live in CDC, the customer account in the shop."), "HO-landscape#SYS-CDC; HO-requirements-set#TA-01", "triage/impacts#TA-01@commerce,TA-01@cdc,IF-01@cdc,IF-01@commerce"),
    ("C-TRIAGE-002", "assessment", t("Die Kundendaten fließen ohne die Integration Suite von CDC in den Shop.", "Customer data flows from CDC into the shop without the Integration Suite."), "HO-requirements-set#IF-01", "triage/impacts#IF-01@middleware"),
    ("C-TRIAGE-003", "fact", t("Bestellung und Status laufen zwischen Shop und ERP über die Integration Suite.", "Order and status run between shop and ERP through the Integration Suite."), "HO-landscape#SYS-CPI; HO-requirements-set#TA-02; HO-requirements-set#IF-02", "triage/impacts#TA-02@commerce,TA-02@middleware,TA-02@s4,IF-02@commerce,IF-02@middleware,IF-02@s4"),
    ("C-TRIAGE-004", "fact", t("Ratgeberseiten werden in Magnolia gepflegt und in der Storefront mit Produktdaten gezeigt.", "Guide pages are maintained in Magnolia and shown in the storefront with product data."), "HO-landscape#SYS-CMS; HO-requirements-set#TA-03", "triage/impacts#TA-03@commerce,TA-03@magnolia"),
    ("C-TRIAGE-005", "assessment", t("Die zentrale Überwachung berührt kein System dieses Laufs.", "Central monitoring touches no system of this run."), "HO-requirements-set#TA-04", "triage/impacts#TA-04@middleware,TA-04@none"),
    ("C-TRIAGE-006", "fact", t("Die Bonuspunkte kommen von einem Dienst auf SAP BTP in den Shop.", "The bonus points come from a service on SAP BTP into the shop."), "HO-landscape#SYS-BTP; HO-requirements-set#IF-03", "triage/impacts#IF-03@commerce")]


def systems_triage():
    """the triage agent's file of the systems variant (one chunk TRIAGE)"""
    w("analysis/triage/TRIAGE.md", "\n".join(["# Impact per system (triage TRIAGE)", "", "- **agent:** consolidate-triage", "- **scope:** TRIAGE", "- **status:** final", "- **round:** 0", "",
        "## Summary", "", "Seven rows: the shop is touched by six, the Integration Suite by two, the ERP by two, CDC by two and Magnolia by one. TA-04 touches no system of the run; two pre-fills of the Integration Suite are removed.", "",
        "## Impacts", "", table(["row_id", "system", "affected", "impact", "reason"], SYS_TRIAGE), "",
        "## Claims", "", table(["id", "type", "statement", "evidence", "target", "supersedes"], [c + ("",) for c in SYS_TRIAGE_CLAIMS]), ""]))


# the analyses of the wave-1 chunks of `dbcx discover` (Markdown for `dbcx md_to_json estimation`, the
# chunk names the wave planner gives them) - two of them report gaps - and the architect's decisions. A row's option is the option value as in the work packages
# (<option>[@<parent option>]); every row carries the work-package fields; one claim per row targets it.
SYS_EST_FIELDS = ["req_id", "option", "position", "epic", "approach", "size", "mechanism", "mechanism_kind", "evidence", "derivation", "estimation_assumption", "confidence",
                  "starting_point", "coverage", "gap_reason", "route_suggestion"]


def _est(req, option, size, cov, conf, gap="", sug="", sp="new", approach="partial"):
    r = {"req_id": req, "option": option, "epic": t("Technik", "Technical") if req.startswith("TA-") else t("Schnittstellen", "Interfaces"), "approach": approach, "size": size,
         "mechanism": t("Standardfunktion mit Erweiterung", "standard function with an extension"), "mechanism_kind": "module",
         "evidence": "HO-requirements-set#" + req, "derivation": t("Erweiterung des Standards im System.", "Extension of the standard in the system."), "confidence": conf, "starting_point": sp, "coverage": cov}
    if gap: r["gap_reason"] = gap
    if sug: r["route_suggestion"] = sug
    return r


SYS_GAP_CHUNKS = {   # by the chunk name of the two-option run; systems_gaps() writes each to the run's first chunk of that system option
    "commerce-sapcc-01": [_est("TA-01", "sapcc", "S", "extension", "medium"),
                          _est("TA-02", "sapcc", "XS", "gap", "medium", t("Der Shop kennt die Statuscodes des ERP nicht; er zeigt nur, was er erhält.", "The shop does not know the ERP status codes; it only shows what it receives."), "middleware"),
                          _est("TA-03", "sapcc", "S", "gap", "low", t("Produktempfehlungen für Ratgeberseiten brauchen einen Empfehlungsdienst, den der Shop nicht hat.", "Product recommendations for guide pages need a recommendation service the shop does not have."), "SYS-BTP"),
                          _est("IF-01", "sapcc", "S", "extension", "medium"), _est("IF-02", "sapcc", "M", "extension", "medium"),
                          _est("IF-03", "sapcc", "XS", "gap", "medium", t("Bonuspunkte in Echtzeit je Bestellung sind keine Funktion des Shops.", "Bonus points in real time per order are no function of the shop."))],
    "commerce-shopware-01": [_est(r, "shopware", sz, "extension", "medium", approach="custom") for r, sz in (("TA-01", "M"), ("TA-02", "S"), ("TA-03", "M"), ("IF-01", "M"), ("IF-02", "L"), ("IF-03", "S"))],
    "cdc-01": [_est("TA-01", "cdc", "XS", "gap", "medium", t("Double-Opt-in für die Newsletter-Einwilligung ist nicht Teil der Registrierungs-Screen-Sets.", "Double opt-in for the newsletter consent is not part of the registration screen-sets."), "commerce"),
               _est("IF-01", "cdc", "S", "extension", "high")]}
SYS_DECISIONS = [
    ("TA-01", "cdc", "overrule", "cdc", t("CDC versendet die Bestätigung einer Einwilligung mit den Standard-E-Mail-Vorlagen; im Screen-Set wird nur Double-Opt-in für die Einwilligung eingeschaltet.", "CDC sends the confirmation of a consent with its standard e-mail templates; the screen-set only switches double opt-in on for the consent."), "", ""),
    ("TA-02", "commerce", "route-estimated", "middleware", t("Die Übersetzung der Statuscodes gehört in den Integrationsablauf, der den Status ohnehin überträgt.", "Translating the status codes belongs to the integration flow that carries the status anyway."),
     t("Der Integrationsablauf übersetzt die Statuscodes des ERP in die Bestellstatus des Shops.", "The integration flow translates the ERP status codes into the order states of the shop."), ""),
    ("TA-03", "commerce", "route-landscape", "SYS-BTP", t("Die Landschaft führt SAP BTP als Erweiterungsplattform; dort laufen eigene Dienste.", "The landscape lists SAP BTP as the extension platform; own services run there."),
     t("Ein Empfehlungsdienst auf SAP BTP liefert die Produktempfehlungen der Ratgeberseiten.", "A recommendation service on SAP BTP delivers the product recommendations of the guide pages."), "AS-01"),
    ("IF-03", "commerce", "reduce-to-standard", "commerce", t("Der nächtliche Abgleich der Punkte ist Standard und deckt den Bedarf der Kunden.", "The nightly points import is standard and covers what the customers need."),
     t("Bonuspunkte erscheinen nach dem nächtlichen Abgleich im Konto statt sofort nach der Bestellung.", "Bonus points appear in the account after the nightly import instead of right after the order."), "AS-02")]
SYS_ARCH_TAKEN = [   # affects names the receiving cell (route-landscape) / the reporting work package (reduce-to-standard), never the bare row
    ("AS-01", "TA-03@SYS-BTP", t("Wird der Empfehlungsdienst auf SAP BTP gebaut?", "Is the recommendation service built on SAP BTP?"), t("Dienst auf SAP BTP", "service on SAP BTP"),
     t("Die Schätzung geht davon aus, dass der Empfehlungsdienst der Ratgeberseiten auf SAP BTP umgesetzt und dort separat geschätzt wird.", "The estimate assumes that the recommendation service of the guide pages is built on SAP BTP and estimated there separately."),
     t("Die Landschaft nennt SAP BTP als Erweiterungsplattform.", "The landscape names SAP BTP as the extension platform."), t("Der Dienst wäre im Shop zu schätzen.", "The service would be estimated in the shop."), ""),
    ("AS-02", "IF-03@commerce:sapcc", t("Genügen Bonuspunkte nach dem nächtlichen Abgleich?", "Are bonus points after the nightly import enough?"), t("nächtlicher Abgleich", "nightly import"),
     t("Die Schätzung geht davon aus, dass Bonuspunkte nach dem nächtlichen Abgleich im Konto erscheinen und nicht sofort nach der Bestellung.", "The estimate assumes that bonus points appear in the account after the nightly import, not right after the order."),
     t("Der Abgleich ist Standard und deckt den Bedarf.", "The import is standard and covers the need."), t("Echtzeitpunkte brauchen eine eigene Schnittstelle.", "Real-time points need an interface of their own."), "")]
SYS_ARCH_CLAIMS = [
    ("C-ARCHITECT-1-001", "assessment", t("Double-Opt-in für Einwilligungen ist in CDC mit den Standard-E-Mail-Vorlagen lösbar.", "Double opt-in for consents is solvable in CDC with its standard e-mail templates."), "HO-landscape#SYS-CDC; HO-requirements-set#TA-01", "architect/decisions#TA-01@cdc@cdc"),
    ("C-ARCHITECT-1-002", "assessment", t("Die Übersetzung der ERP-Statuscodes gehört in den Integrationsablauf.", "Translating the ERP status codes belongs to the integration flow."), "HO-landscape#SYS-CPI; HO-requirements-set#TA-02", "architect/decisions#TA-02@commerce@middleware"),
    ("C-ARCHITECT-1-003", "assessment", t("Der Empfehlungsdienst der Ratgeberseiten läuft auf SAP BTP.", "The recommendation service of the guide pages runs on SAP BTP."), "HO-landscape#SYS-BTP; HO-requirements-set#TA-03", "architect/decisions#TA-03@commerce@SYS-BTP"),
    ("C-ARCHITECT-1-004", "assessment", t("Bonuspunkte nach dem nächtlichen Abgleich decken den Bedarf.", "Bonus points after the nightly import cover the need."), "HO-requirements-set#IF-03", "architect/decisions#IF-03@commerce@commerce")]


SYS_GAP_OPT = {"commerce-sapcc-01": ("commerce", "sapcc"), "commerce-shopware-01": ("commerce", "shopware"), "cdc-01": ("cdc", "cdc")}


def wave1_chunk(system, option):
    """the first chunk `dbcx discover` planned for a system option (state/scopes.json), None when the run has no such option"""
    sc = J("state/scopes.json")["scopes"]
    return next((n for n in sorted(sc) if sc[n].get("system") == system and sc[n].get("option") == option and not sc[n].get("pickup")), None)


def systems_gaps():
    """the analysts' files of the wave-1 chunks (convert each with `dbcx md_to_json estimation analysis/scopes/<chunk>.md`) and the architect
    agent's file of batch ARCHITECT-1"""
    for name, rows in SYS_GAP_CHUNKS.items():
        scope = wave1_chunk(*SYS_GAP_OPT[name])
        if not scope: continue   # the option is not part of this run (systems-single: no Shopware)
        claims = [(f"C-{scope}-{i:03d}", "assessment" if r["coverage"] == "gap" else "fact", t("Die Arbeit des Pakets liegt in diesem System: ", "The work of the package lies in this system: ") + (r.get("gap_reason") or r["mechanism"]),
                   r["evidence"], f"D1/{SH['Schaetzung']}#{r['req_id']}@{r['option']}", "") for i, r in enumerate(rows, 1)]
        w(f"analysis/scopes/{scope}.md", "\n".join([f"# Fit estimation: {scope}", "", f"- **scope:** {scope}", f"- **agent:** analyst-{scope}", f"- **technology:** {scope}", "- **wave:** 1", "- **status:** final", "- **round:** 0", "",
            "## Summary", "", t("Die Pakete dieses Systems; was das System nicht tragen kann, ist als Lücke gemeldet.", "The packages of this system; what the system cannot carry is reported as a gap."), "",
            "## Estimation", "", table(SYS_EST_FIELDS, rows), "", "## Assumptions", "", t("Keine in diesem Chunk.", "None in this chunk."), "", "## Assumptions taken", "", t("Keine in diesem Chunk.", "None in this chunk."), "",
            "## Claims", "", table(["id", "type", "statement", "evidence", "target", "supersedes"], claims), "", "## Open questions", "", t("Keine in diesem Chunk.", "None in this chunk."), ""]))
    w("analysis/architect/ARCHITECT-1.md", "\n".join(["# Gap decisions (architect ARCHITECT-1)", "", "- **agent:** consolidate-architect-1", "- **scope:** ARCHITECT-1", "- **status:** final", "- **round:** 0", "",
        "## Summary", "", "Four gaps: one overruled (CDC carries double opt-in by its standard), one routed to the Integration Suite, one to SAP BTP outside the run, one reduced to the standard.", "",
        "## Decisions", "", table(["row_id", "from_system", "decision", "to", "reasoning", "solution", "assumption"], SYS_DECISIONS), "",
        "## Assumptions taken", "", table(["id", "affects", "question", "reading_taken", "assumption", "why", "if_not", "alternatives"], SYS_ARCH_TAKEN), "",
        "## Claims", "", table(["id", "type", "statement", "evidence", "target", "supersedes"], [c + ("",) for c in SYS_ARCH_CLAIMS]), ""]))
# --------------------------------------------------------------------------- systems: the workbook inputs, wave 2 and the consolidation
RANGE = {"high": {"min": 0.9, "max": 1.25}, "medium": {"min": 0.8, "max": 1.5}, "low": {"min": 0.7, "max": 2.0}}   # the method default of estimation.range_factors - not set in run.json
SYS_REFS = [
 {"fact": "Customer accounts are created from an identity provider login through the standard customer synchronisation", "applies": "2.0", "url": DOC + "customer-sync",
  "title": t("Kundenkonto aus dem Identitätsanbieter (Standard)", "Customer account from the identity provider (standard)"), "summary": t("Das Kundenkonto entsteht in Version 2.0 über die Standard-Synchronisation aus dem Identitätsanbieter.", "In version 2.0 the customer account is created through the standard synchronisation from the identity provider.")},
 {"fact": "Integration flows translate messages between the shop and the ERP with standard adapters", "applies": "2.0", "url": DOC + "integration-flows",
  "title": t("Integrationsabläufe zwischen Shop und ERP", "Integration flows between shop and ERP"), "summary": t("Integrationsabläufe übersetzen Nachrichten zwischen Shop und ERP mit Standardadaptern.", "Integration flows translate messages between shop and ERP with standard adapters.")}]
Q1, Q2 = "PS-7-001", "PS-7-002"
# wave 2 (after the architect's batch and `dbcx discover --pickup`): the estimate per work package key - (size | [position sizes], confidence,
# starting point, coverage, evidence); a package of the plan not listed here gets the default
WAVE2 = {"TA-01@cdc:cdc": ("S", "high", "new", "standard", Q1),                        # overruled gap: CDC estimates double opt-in with its standard
         "IF-03@commerce:sapcc": ("XS", "high", "new", "standard", Q1),                # reduced to the standard: the nightly import
         "TA-02@middleware:is@sapcc": ("M", "medium", "extend", "extension", Q2),      # routed from commerce: the flow translates the status codes
         "TA-02@middleware:is@shopware": ("L", "medium", "new", "extension", Q2),
         "IF-02@middleware:is@sapcc": (["XXL", "XL"], "medium", "extend", "extension", Q2),   # above the sprint limit: a position split
         "IF-02@middleware:is@shopware": ("XL", "low", "new", "extension", Q2)}
WAVE2_DEFAULT = ("M", "medium", "new", "extension", None)
SYS_PHASES = [("FP-01", "commerce:sapcc", t("Basis: Umgebungen und Konfiguration", "Base: environments and configuration"), 15),
              ("FP-02", "commerce:shopware", t("Basis: Umgebungen und Konfiguration", "Base: environments and configuration"), 20),
              ("FP-03", "cdc:cdc", t("Basis: Mandant und Screen-Sets", "Base: tenant and screen-sets"), 5)]
SYS_EXT = [("TA-02", "s4"), ("IF-02", "s4"), ("TA-03", "magnolia"), ("TA-03", "SYS-BTP")]   # input cells: the client's ERP, the CMS agency, SAP BTP (routed by the architect)


def book_inputs(mode):
    """before the requirement import: run.json (`single`: commerce with SAP Commerce Cloud only - one scenario; the day rate, surcharges per
    system, components), the client workbook's condition / workshop-source / interim columns and the mapping (condition, interim; hide_columns
    on the FR sheet). `--client-sheet <name>`: the FR sheet renamed (a client sheet that collides with a method sheet)"""
    import openpyxl
    p = J("run.json")
    if mode == "single": p["systems"][0]["options"] = [o for o in p["systems"][0]["options"] if o["id"] == "sapcc"]
    p["estimation"] = {**p.get("estimation", {}), "unit": t("Personentag (PT)", "person day (PD)"), "day_rate": 1200, "ontop": {"mode": "per_system"}}
    p["views"] = {"components": {"commerce": [t("Online-Shop", "Online shop")], "cdc": [t("Kundenkonto", "Customer account")]}}
    W("run.json", p)
    fp = os.path.join(T, "input/requirements/client_requirements.xlsx"); wb = openpyxl.load_workbook(fp)
    ws = wb["FR"]; ws.cell(2, 7, t("Bedingung", "Condition")); ws.cell(2, 8, t("Quelle Workshop", "Workshop source"))
    for r in range(3, ws.max_row + 1):
        rid = ws.cell(r, 1).value
        if rid: ws.cell(r, 8, f"W-{3458764600000 + r}")
        if rid == "FR-003": ws.cell(r, 7, t("bedingt (OP-43)", "conditional (OP-43)"))
    ws2 = wb["Technik"]; ws2.cell(1, 7, t("Zwischenlösung", "Interim solution"))
    for r in range(2, ws2.max_row + 1):
        if ws2.cell(r, 1).value == "TA-02": ws2.cell(r, 7, t("Statusabgleich per Datei bis zur Echtzeit-Schnittstelle", "status sync by file until the real-time interface"))
    m = J("requirements_mapping.json"); fr, te = m["sheets"][0], m["sheets"][1]
    if "--client-sheet" in sys.argv: ws.title = fr["sheet"] = sys.argv[sys.argv.index("--client-sheet") + 1]
    wb.save(fp)
    fr["columns"]["condition"] = t("Bedingung", "Condition"); fr["hide_columns"] = [t("Quelle Workshop", "Workshop source")]
    te["columns"]["interim"] = t("Zwischenlösung", "Interim solution"); W("requirements_mapping.json", m)
    W("fixture_refs.json", SYS_REFS)


def _wps(entry): return [w for w in (entry.get("meta") or {}).get("work_packages") or [] if w.get("status", "active") == "active"]


def systems_wave2():
    """the analysts' Markdown files of every chunk that is planned, not skipped and not analysed yet (after `dbcx discover --pickup`,
    `dbcx plan_waves` and the registration): the follow-up chunks (overrule -> CDC, reduce-to-standard -> SAP Commerce Cloud) and the
    middleware chunk whose TA-02 packages the architect routed there (in place); convert each with `dbcx md_to_json estimation`"""
    sc = J("state/scopes.json")["scopes"]; waves = {m["name"]: w["wave"] for w in J("state/WAVES.json")["waves"] for m in w["members"]}; done = []
    brown = {(s["id"], o["id"]) for s in J("run.json")["systems"] for o in s.get("options") or [] if o.get("start") == "brownfield"}
    for name in sorted(sc):
        e = sc[name]
        if e.get("skip") or os.path.exists(os.path.join(T, "analysis", "scopes", f"{name}.json")): continue
        rows = []
        for wp in _wps(e):
            size, conf, sp, cov, ev = WAVE2.get(wp["key"], WAVE2_DEFAULT)
            base = {"req_id": wp["row"], "option": wp["value"], "epic": t("Technik", "Technical") if wp["row"].startswith("TA-") else t("Schnittstellen", "Interfaces"),
                    "approach": ("keep" if cov == "standard" else "adapt") if (wp["system"], wp["option"]) in brown else ("standard" if cov == "standard" else "partial"), "size": "" if isinstance(size, list) else size,
                    "mechanism": t("Standardfunktion mit Konfiguration", "standard function with configuration") if cov == "standard" else t("Erweiterung im System", "extension in the system"),
                    "mechanism_kind": "module", "evidence": "; ".join(x for x in (ev, "HO-requirements-set#" + wp["row"]) if x),
                    "derivation": t("aus der Auswirkung je System abgeleitet: Umfang, Felder und Abläufe.", "derived from the impact per system: scope, fields and flows."),
                    "confidence": conf, "starting_point": sp, "coverage": cov}
            rows.append(base)
            if isinstance(size, list): rows += [dict({k: v for k, v in base.items() if k not in ("starting_point", "coverage")}, position=str(i), position_title=t(f"Teil {i}", f"Part {i}"), size=x) for i, x in enumerate(size, 1)]
        claims = [(f"C-{name}-{i:03d}", "fact", t("Die Arbeit des Pakets liegt in diesem System: ", "The work of the package lies in this system: ") + r["mechanism"], r["evidence"].split("; ")[0],
                   f"D1/{SH['Schaetzung']}#{r['req_id']}@{r['option']}", "") for i, r in enumerate([r for r in rows if not r.get("position")], 1)]
        w(f"analysis/scopes/{name}.md", "\n".join([f"# Fit estimation: {name}", "", f"- **scope:** {name}", f"- **agent:** analyst-{name}", f"- **technology:** {name}", f"- **wave:** {waves.get(name, 2)}", "- **status:** final", "- **round:** 0", "",
            "## Summary", "", t("Die Pakete dieses Chunks, mit den Entscheidungen des Architekten.", "The packages of this chunk, with the architect's decisions."), "",
            "## Estimation", "", table(SYS_EST_FIELDS[:3] + ["position_title"] + SYS_EST_FIELDS[3:], rows), "", "## Assumptions", "", t("Keine in diesem Chunk.", "None in this chunk."), "",
            "## Assumptions taken", "", t("Keine in diesem Chunk.", "None in this chunk."), "",
            "## Claims", "", table(["id", "type", "statement", "evidence", "target", "supersedes"], claims), "", "## Open questions", "", t("Keine in diesem Chunk.", "None in this chunk."), ""]))
        done.append(name)
    W("fixture_wave2.json", {name: [r for r in J("state/scopes.json")["scopes"][name]["meta"]["work_packages"] if r.get("status", "active") == "active"] for name in done})
    return done


def systems_consolidate(mode):
    """the consolidation (analysis/consolidated/SUMMARY.md for `dbcx md_to_json summary`: fixed phases per system option, one dependency),
    the summary text of D1 and fixture_expected.json - every work package's person days from the fixture's own estimates (a later wave's
    estimate of a package replaces the earlier one: the superseded first estimate is never counted), its scenarios and its row data"""
    sysm = J("run.json")["systems"]; multi = mode == "multi"
    olab = {(s["id"], o["id"]): o.get("label") or o["id"] for s in sysm for o in s.get("options") or []}
    slab = {s["id"]: s["label"] for s in sysm}; slab["SYS-BTP"] = "SAP BTP"
    phases = [ph for ph in SYS_PHASES if multi or ph[1] != "commerce:shopware"]
    w("analysis/consolidated/SUMMARY.md", "\n".join([
        "# Fit estimation summary (all systems)", "", "- **technology:** " + "; ".join(f"{olab[k]}" for k in olab), "- **status:** final", "- **round:** 1", "",
        "## Summary", "", t("Jedes Arbeitspaket ist je System und Option geschätzt; zwei Lücken gingen an andere Systeme, eine an SAP BTP außerhalb der Schätzung.",
                            "Every work package is estimated per system and option; two gaps went to other systems, one to SAP BTP outside the estimate."), "",
        "## Totals", "", table(["dimension", "option", "key", "requirements", "dev_pd", "note"], [], t("Die Summen rechnet die Arbeitsmappe.", "The workbook computes the totals.")), "",
        "## Calibration", "", table(["option", "mechanism", "rule", "before", "normalised_size", "rows_changed", "rationale"], [], t("Keine Kalibrierung nötig.", "No calibration needed.")), "",
        "## Fixed phases", "", table(["id", "option", "block", "title", "pd", "derivation", "evidence"],
                                     [{"id": i, "option": o, "block": "phase", "title": tt, "pd": str(pd), "derivation": t("Grundaufwand des Systems je Option", "base effort of the system per option"), "evidence": ""} for i, o, tt, pd in phases]), "",
        "## Assumptions", "", table(["id", "requirement_ids", "assumption", "kind", "effect", "scope"], [
            ("AE-01", "TA-02", t("Das ERP liefert jede Statusänderung einer Bestellung.", "The ERP delivers every status change of an order."), "dependency", t("Ohne die Meldung entfällt der Statusabgleich.", "Without the message the status sync is void."), t("alle Systeme", "all systems"))]), "",
        "## Risks", "", table(["id", "risk", "options", "affected", "likelihood", "impact", "mitigation", "evidence"], [], t("Keine Risiken über die Zeilen hinaus.", "No risk beyond the rows.")), "",
        "## Assumptions taken", "", table(["id", "affects", "question", "reading_taken", "assumption", "why", "if_not", "alternatives"], [], t("Keine auf Gesamtebene.", "None at total level.")), "",
        "## Claims", "", table(["id", "type", "statement", "evidence", "target", "supersedes"], [], t("Keine Aussage auf Gesamtebene.", "No statement at total level.")), "",
        "## Open questions", "", table(["id", "to", "question", "why_needed", "status", "answer"], [], t("Keine.", "None.")), ""]))
    w("analysis/summaries/D1.md", t("# Ergebnis\n\nIm gewählten Szenario kostet die Lösung {kpi:total_sel} Personentage über alle Systeme; offen sind noch {kpi:open_total} Eingaben anderer Eigentümer.\n",
                                    "# Result\n\nIn the selected scenario the solution takes {kpi:total_sel} person days across all systems; {kpi:open_total} inputs of other owners are still open.\n"))
    # the fixture's own estimates, wave by wave (a later estimate of the same package replaces the earlier one)
    est = {}
    for name, rows in SYS_GAP_CHUNKS.items():
        sid, oid = SYS_GAP_OPT[name]
        if (sid, oid) in olab:
            for r in rows: est[f"{r['req_id']}@{sid}:{r['option']}"] = {"size": r["size"], "conf": r["confidence"], "wave": 1}
    for name, wps in J("fixture_wave2.json").items():   # the packages wave 2 estimated (written by --wave2)
        for x in wps: size, conf, *_r = WAVE2.get(x["key"], WAVE2_DEFAULT); est[x["key"]] = {"size": size, "conf": conf, "wave": 2}
    scen = ["sapcc", "shopware"] if multi else ["solution"]
    pick = {"sapcc": {"commerce": "sapcc"}, "shopware": {"commerce": "shopware"}, "solution": {"commerce": "sapcc"}}
    rel = {"TA-01": "MVP", "TA-02": "MVP", "TA-03": "Phase 2"}; epic = {"TA-01": t("Konto", "Account"), "TA-02": t("Bestellung", "Ordering"), "TA-03": t("Inhalte", "Content")}
    roll = {"TA-01": "FR-001", "TA-02": "FR-002", "TA-03": "FR-003"}
    def info(r): return {"rollup": roll.get(r, r), "release": rel.get(r, t("ohne Release", "no release")), "epic": epic.get(r, t("ohne Epic", "no epic")), "cond": r == "TA-03", "interim": r == "TA-02"}
    exp = []
    for k, v in est.items():
        r, rest = k.split("@", 1); sid, val = rest.split(":", 1); oid, _, par = val.partition("@")
        pd = sum(MAP[x] for x in v["size"]) if isinstance(v["size"], list) else MAP[v["size"]]
        inn = [x for x in scen if (pick[x]["commerce"] == oid if sid == "commerce" else (not par or pick[x]["commerce"] == par))]
        exp.append(dict(info(r), row=r, system=slab[sid], option=olab[(sid, oid)], parent=olab.get(("commerce", par), "") if par else "", pd=pd, confidence=v["conf"], ext=False, scenarios=inn,
                        routed=(r == "TA-02" and sid == "middleware")))
    for r, sid in SYS_EXT:
        exp.append(dict(info(r), row=r, system=slab[sid], option="", parent="", pd=0, confidence="", ext=True, scenarios=scen, routed=sid == "SYS-BTP"))
    labs = [olab[("commerce", x)] for x in scen] if multi else [t("Gesamtlösung", "Solution")]
    W("fixture_expected.json", {"variant": "systems-" + mode, "map": MAP, "surcharge_pct": 55, "day_rate": 1200, "range": RANGE, "scenarios": scen, "scenario_labels": labs, "systems": [slab[s["id"]] for s in sysm] + ["SAP BTP"],
                                "wps": exp, "phases": [{"system": slab[o.split(":")[0]], "pd": pd, "scenarios": [x for x in scen if pick[x].get(o.split(":")[0], o.split(":")[1]) == o.split(":")[1]]} for _, o, _t, pd in phases],
                                "superseded": {"row": "TA-01", "system": slab["cdc"], "option": olab[("cdc", "cdc")], "size": "XS", "live": "S"},
                                "routed": {"row": "TA-02", "system": slab["middleware"], "from": slab["commerce"]}, "landscape": {"row": "TA-03", "system": "SAP BTP", "from": slab["commerce"]},
                                "hidden_header": t("Quelle Workshop", "Workshop source"), "client_sheet": J("requirements_mapping.json")["sheets"][0]["sheet"]})


if "--book-inputs" in sys.argv: book_inputs(sys.argv[sys.argv.index("--book-inputs") + 1]); print("book inputs written"); sys.exit(0)
if "--wave2" in sys.argv: print("wave-2 analyses written:", ", ".join(systems_wave2()) or "none"); sys.exit(0)
def system_critic(scope, which):
    """one critic's round-1 file of a system-mode gauntlet scope (a chunk of one system option or the architect's batch): it scores the
    claims `dbcx extract_claims` routed to it (claims.json `critics` - the method's critic routing), 8 or 9 each; convert it with
    `dbcx md_to_json critic`"""
    cl = [c for c in J(f"analysis/gauntlet/{scope}/claims.json")["claims"] if which in (c.get("critics") or [])]
    w(f"analysis/gauntlet/{scope}/round1-{which}.md", "\n".join([f"# Gauntlet score: {scope} / {which} / round 1", "", f"- **scope:** {scope}", f"- **critic:** {which}", "- **round:** 1", "",
        "## Scores", "", table(["claim_id", "score", "verdict", "issue", "counter_evidence", "fix_hint"], [(c["id"], 9 if i % 2 else 8, "confirmed", "", "", "") for i, c in enumerate(cl)],
                               t("Keine Aussage an diesen Kritiker geleitet.", "No claim routed to this critic.")), "",
        "## Missing claims", "", "- ", "", "## Estate observations", "", "- ", "", "## Summary", "", t("Die Pakete folgen den Anforderungen und nennen ihre Grundlage.", "The packages follow the requirements and name their basis."), ""]))
    return len(cl)


if "--critic" in sys.argv: i = sys.argv.index("--critic"); print(f"{sys.argv[i + 2]}: {system_critic(sys.argv[i + 1], sys.argv[i + 2])} claim(s) scored"); sys.exit(0)
if "--consolidate" in sys.argv: systems_consolidate(sys.argv[sys.argv.index("--consolidate") + 1]); print("consolidation, D1 summary and fixture_expected.json written"); sys.exit(0)


if "--derived-rows" in sys.argv: derived_rows(); print("derived rows NR-001, NR-002 appended"); sys.exit(0)
if "--gaps" in sys.argv: systems_gaps(); print(f"analyses {', '.join(SYS_GAP_CHUNKS)} (gaps in commerce-sapcc-01 and cdc-01) and the architect's file ARCHITECT-1 written"); sys.exit(0)
if VARIANT == "systems": systems_inputs(); systems_triage(); print("systems inputs written (run.json systems, client workbook + mapping, landscape CSV, the triage agent's file)"); sys.exit(0)
fill_run()
requirements_workbook()
corpus()
if BROWN: brownfield_inputs()
if SC: classification_md()
W("fixture_refs.json", REFS); W("fixture_expected.json", expected())

if not NO_ANA:
    A1 = [("AE-01", "FR-009; FR-010; FR-016; FR-017", t("Die installierte Basis kommt je Einheit aus dem ERP, einschließlich Ersatzteilnummern und Serviceeinsätzen.", "The installed base is delivered by the ERP per unit, including spare part numbers and service events."), "dependency", t("Ohne die Lieferung verlieren die vier Zeilen ihre Datenquelle.", "Without the delivery the four rows lose their data source."))]
    A2 = [("AE-02", "TR-01; TR-02", t("Middleware-Lizenzen und Arbeiten auf ERP-Seite sind nicht Teil der Zahlen.", "Middleware licences and ERP-side work are not part of the figures."), "exclusion", t("Den Aufwand auf ERP-Seite schätzt das ERP-Team.", "ERP-side effort is estimated by the ERP team."))]
    TAKEN = [("AS-01", "FR-024", t("Wie viele Produkte vergleichen Kunden nebeneinander?", "How many products do customers compare side by side?"), t("bis zu vier Produkte", "up to four products"),
              t("Die Schätzung geht davon aus, dass Kunden bis zu vier Produkte über das vorhandene Attributset vergleichen.", "The estimate assumes that customers compare up to four products over the existing attribute set."),
              t("Die Anforderung nennt keine Zahl; vier ist die Voreinstellung des Standardmoduls.", "The requirement names no number; four is the default of the standard module."),
              t("Mehr Produkte oder eigene Attribute kosten je Option eine Größe mehr bei FR-024.", "More products or own attributes cost one size more for FR-024 in every option."), t("unbegrenzter Vergleich", "unlimited comparison"))]
    C1, C2, CS = claims1(), claims2(), claims_sum()
    w("analysis/scopes/epic-01.md", analysis("epic-01", 1, CHUNK1, A1, C1, [],
        "The nine requirements of the installed base ask for a machine list, detail pages, documents, search, export, maintenance notifications, assignment and service history. "
        "Every option is estimated on the same rows; the equipment list is the largest item and is cut into positions where it exceeds a sprint. The figures rest on the nightly ERP delivery."))
    w("analysis/scopes/epic-02.md", analysis("epic-02", 1, CHUNK2, A2, C2, TAKEN,
        "The five requirements of catalogue, checkout and integration: successor products and the comparison are configuration, the delivery split by plant is larger than a sprint and cut into positions, "
        "the ERP synchronisation gets its schedule from the Import/Export module and builds the mapping."))
    for scope, cl in (("epic-01", C1), ("epic-02", C2), ("SUMMARY", CS)):
        for cr in CRITICS:
            w(f"analysis/gauntlet/{scope}/round1-{cr}.md", critic(scope, cr, cl, "The rows follow the requirements as written and every size names its basis."))
    tot = []
    for o in OPTS:
        tot.append({"dimension": "option", "option": o["id"], "key": o["id"], "requirements": len(EPIC), "dev_pd": dev_pd(o["id"]), "note": ""})
        for e in sorted(set(EPIC.values())): tot.append({"dimension": "epic", "option": o["id"], "key": e, "requirements": sum(1 for r in EPIC if EPIC[r] == e), "dev_pd": dev_pd(o["id"], [r for r in EPIC if EPIC[r] == e]), "note": ""})
    for s in (SCENARIOS if SC else []):
        tot.append({"dimension": "scenario", "option": s["option"], "key": s["id"], "requirements": sum(1 for r in KIND[s["option"]] if CLS.get(r, "client") in s["classes"]),
                    "dev_pd": round(dev_pd(s["option"], [r for r in KIND[s["option"]] if CLS.get(r, "client") in s["classes"]]) - (1 if s.get("subtract_savings") else 0), 1), "note": ""})
    w("analysis/consolidated/SUMMARY.md", "\n".join([
        "# Fit estimation summary (all epics, all options)", "",
        f"- **technology:** {tech()}", "- **status:** final", "- **round:** 1", "",
        "## Summary", "",
        "Every requirement is estimated once per option. The options differ most in the installed base and the checkout: what exists today is kept or adapted in a migration and built in a new solution. "
        "The delivery split by plant is the one requirement that needs a decision before it is built. Surcharges and fixed phases are parameters of the workbook; every total follows.", "",
        "## Totals", "", table(["dimension", "option", "key", "requirements", "dev_pd", "note"], tot), "",
        "## Calibration", "", table(["option", "mechanism", "rule", "before", "normalised_size", "rows_changed", "rationale"],
                                     [{"option": OPTS[-1]["id"], "mechanism": "Import/Export module", "rule": "same module, same size for the activation", "before": "S - M in two chunks", "normalised_size": "S",
                                       "rows_changed": f"FR-013@{OPTS[-1]['id']}", "rationale": "The module is activated once; the second row keeps its own mapping."}]), "",
        "## Fixed phases", "", table(["id", "option", "block", "title", "pd", "derivation", "evidence"] + (["scenario"] if SC else []),
                                     [{"id": p[0], "option": o["id"], "block": p[1], "title": p[2], "pd": p[3], "derivation": p[4], "evidence": "; ".join(p[5])} for o in OPTS for p in PHASES[o["id"]]] if not SC else
                                     [{"id": p[0], "option": s["option"], "scenario": s["id"], "block": "phase", "title": p[1], "pd": p[2], "derivation": p[3], "evidence": "; ".join(p[4])} for s in SCENARIOS for p in SPHASES[s["id"]]]), "",
        *(["## Fixed phase seeds", "", table(["scenario", "phase", "decision", "pd", "phase_id", "reason"],
               [{"scenario": sid, "phase": p[1], "decision": p[5], "pd": p[2], "phase_id": p[0], "reason": p[6]} for sid, ps in SPHASES.items() for p in ps] +
               [{"scenario": sid, "phase": ph, "decision": "drop", "pd": "", "phase_id": "", "reason": why} for sid, ph, why in SEED_DROP]), ""] if SC else []),
        "## Assumptions", "", table(["id", "requirement_ids", "assumption", "kind", "effect", "scope"], [
            ("AE-01", "FR-009; FR-010; FR-016; FR-017", t("Das ERP liefert die installierte Basis je Einheit jede Nacht, einschließlich Ersatzteilnummern und Serviceeinsätzen.", "The ERP delivers the installed base per unit every night, including spare part numbers and service events."), "dependency", t("Ohne die Lieferung verlieren vier Zeilen ihre Datenquelle.", "Without the delivery four rows lose their data source."), "Installed base"),
            ("AE-02", t("alle", "all"), t("Lizenzen, Arbeiten auf ERP- oder S/4-Seite und das Hosting sind nicht Teil der Zahlen.", "Licences, work on the ERP or S/4 side and hosting are not part of the figures."), "exclusion", t("Jeder dieser Posten wird vom zuständigen Team getrennt geschätzt.", "Each of these is estimated separately by the owning team."), t("alle", "all"))]), "",
        "## Risks", "", table(["id", "risk", "options", "affected", "likelihood", "impact", "mitigation", "evidence"], [
            ("R-01", t("Die Teillieferung je Werk widerspricht dem Bestellmodell; eine Aufteilung je Position müsste gegen die Standardbestellung gebaut werden.", "The delivery split by plant contradicts the order model; a split per item would have to be built against the standard order."), "", "FR-030; TR-02", "medium", "blocker",
             t("Die Ebene der Aufteilung vor dem Bau mit dem Kunden entscheiden.", "Decide the split level with the client before the build."), "C-epic-02-002; " + R["checkout"]),
            ("R-02", t("Die nächtliche ERP-Lieferung ist vom ERP-Team noch nicht bestätigt.", "The nightly ERP delivery is not yet confirmed by the ERP team."), OPTS[0]["id"], "FR-009; FR-016", "medium", "major",
             t("Die Lieferung im ERP-Workshop bestätigen.", "Confirm the delivery in the ERP workshop."), "SRC-001#p2")]), "",
        "## Assumptions taken", "", table(["id", "affects", "question", "reading_taken", "assumption", "why", "if_not", "alternatives"], [], "The readings of the chunks are registered by the chunks; none is added at total level."), "",
        "## Claims", "", table(["id", "type", "statement", "evidence", "target", "supersedes"], [(c[0], c[1], c[2], c[3], c[4], "") for c in CS]), "",
        "## Open questions", "", table(["id", "to", "question", "why_needed", "status", "answer"], [], "No question to another chunk or to the lead."), "",
    ]))
    w("analysis/gate/round1-cto.md", "\n".join([
        "# Final gate: cto / round 1", "", "- **persona:** cto", "- **round:** 1", "",
        "## Key questions", "", table(["question_id", "score", "where", "answer", "rationale"], [("T1", 8, "Schaetzung!A2", "approach per option", "on every row"), ("T2", 8, "Schaetzung!A2", "basis per option", "per block"), ("T3", 7, "Schaetzpositionen!A1", "positions listed", "no sprint plan")]), "",
        "## Board test", "", "- **forward_unchanged:** yes", "- **blocking_items:** ", "",
        "## What is missing", "", "- a sprint plan", "",
        "## Issues", "", table(["id", "deliverable", "location", "issue", "kind", "severity", "question_id", "proposed_change"], [("I1", "D1", "Schaetzpositionen!A1", "the positions have no sprint number", "structure", "minor", "T3", "add a sprint column")]), "",
        "## Summary", "", "Readable and provable per option.", "",
    ]))
    parts = []
    for o in ([] if SC else OPTS):
        parts.append(t(f"{{o}}: Gesamtaufwand {{kpi:total_{o['id']}}} Personentage, davon {{kpi:dev_{o['id']}}} Entwicklung, Kosten {{kpi:cost_{o['id']}}} Euro zum Tagessatz vom Blatt Parameter.",
                       f"{{o}}: total effort {{kpi:total_{o['id']}}} person days, of which {{kpi:dev_{o['id']}}} development, cost {{kpi:cost_{o['id']}}} euro at the day rate of the Parameters sheet.").replace("{o}", o["label"]))
    for s in (SCENARIOS if SC else []):
        parts.append(t(f"{s['label']}: Gesamtaufwand {{kpi:total_{s['id']}}} Personentage, Kosten {{kpi:cost_{s['id']}}} Euro zum Tagessatz vom Blatt Parameter.",
                       f"{s['label']}: total effort {{kpi:total_{s['id']}}} person days, cost {{kpi:cost_{s['id']}}} euro at the day rate of the Parameters sheet."))
    w("analysis/summaries/D1.md", "\n".join([
        t("Die Liste hat {kpi:req_total} Anforderungen; jede ist je Option geschätzt.", "The list has {kpi:req_total} requirements; each one is estimated per option."), ""] + [p + "\n" for p in parts] + [
        t("Die Optionen unterscheiden sich vor allem bei der installierten Basis und beim Checkout. Die Teillieferung je Werk braucht vor dem Bau eine Entscheidung; die Annahmen zu breit formulierten Anforderungen stehen mit ihrer Wirkung auf dem Blatt Annahmen.",
          "The options differ most in the installed base and the checkout. The delivery split by plant needs a decision before it is built; the assumptions on broadly written requirements are on the Assumptions sheet with their effect.")]))

print("fixture written to", T, f"(variant {VARIANT})" + ("" if not NO_ANA else " (without analyses)"))
