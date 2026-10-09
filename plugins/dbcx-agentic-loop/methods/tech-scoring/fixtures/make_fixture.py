#!/usr/bin/env python3
"""Write toy engagement content into an initialised tech-scoring RUN folder so the whole chain can be smoke-tested.

Usage: python3 methods/tech-scoring/fixtures/make_fixture.py <run_dir>
Fills the run.json placeholders (client context, decision, guardrails, three technologies, the method's default criteria,
shortlist size 2 so one technology is deliberately NOT shortlisted), writes a small client-context file and a requirements
workbook + mapping, and lays down one complete sample analysis per technology, the reviewer files of one technology and of
the consolidation, the consolidated shortlist, a gate file and the management summary.
Client-facing text is written in the run's deliverable language (a German customer edition must read German throughout);
vendor evidence cites reference ids PS-7-001..004, which smoke.sh registers (with titles) before the build.
"""
import os, sys, json, textwrap

T = os.path.abspath(sys.argv[1])
METHOD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRIT = json.load(open(os.path.join(METHOD_DIR, "method.json"), encoding="utf-8"))["defaults"]["criteria"]
CIDS = [c["id"] for c in CRIT]
DE = json.load(open(os.path.join(T, "run.json"), encoding="utf-8")).get("languages", {}).get("deliverable") == "de"


def t(de, en):
    """client-facing fixture text in the run's deliverable language"""
    return de if DE else en


def w(p, s):
    p = os.path.join(T, p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(textwrap.dedent(s))


def J(p): return json.load(open(os.path.join(T, p), encoding="utf-8"))
def W(p, d): json.dump(d, open(os.path.join(T, p), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def row(*cells): return "| " + " | ".join(str(c).replace("|", "/") for c in cells) + " |"
def head(*cells): return row(*cells) + "\n" + "|" + "---|" * len(cells)


# German criteria of the fixture run (the method defaults are English; a German run carries its own criteria wording)
CRIT_DE = {
 "C-01": ("Passung zum Geschäftsmodell (B2B / B2C)", "Tiefe des Geschäftsmodells, das der Kunde tatsächlich betreibt: B2B-Preise, Verträge, Einheiten und Organisationen, Freigaben, Angebote, Punch-out; B2C-Merchandising, Aktionen, Abonnements. Native Tiefe schlägt ein Zusatzmodul."),
 "C-02": ("Passung zu Ökosystem und ERP-Anbindung", "Passung zur bestehenden Landschaft des Kunden (ERP, PIM, CRM, Zahlung, Suche, Marketing): dokumentierte Konnektoren oder eine dokumentierte Integrationsschicht für genau diese Systeme."),
 "C-03": ("Standardabdeckung der Kernanforderungen", "Anteil der Kernanforderungen des Kunden, den dokumentierte Standardfunktionen der genannten Version bzw. des genannten Plans ohne Eigenentwicklung erfüllen."),
 "C-04": ("Selbstständigkeit der Fachanwender", "Was Fachanwender ohne Entwickler ändern: Inhalte, Preise, Aktionen, Katalog, Abläufe, Seitengestaltung. Ein Leitlinien-Kriterium: unter der Schwelle ist die Anforderung an die Selbstständigkeit nicht erfüllt."),
 "C-05": ("Betriebskosten und Lizenzmodell", "Lizenz- oder Abonnementmodell (Messgröße, Staffelung, Preistreiber), Betriebskosten, Aufwand für die Aktualität. Benanntes Modell und Messgröße, nie eine geschätzte Summe."),
 "C-06": ("Machbarkeit des Termins und Verfügbarkeit von Partnern", "Lässt sich der Starttermin des Kunden mit dieser Technologie halten, und gibt es Implementierungspartner in Region und Sprache des Kunden. Ein Leitlinien-Kriterium: unter der Schwelle ist der Termin nicht glaubwürdig."),
 "C-07": ("Passung zur Architektur (composable, API-first)", "Wie gut die Technologie zur Zielarchitektur des Kunden passt: API-Abdeckung, Headless- oder Composable-Optionen, Erweiterungsmodell, Upgrade-Pfad, Betriebsmodell in der Cloud."),
 "C-08": ("Präsenz und Support in der Region", "Präsenz des Herstellers, Supportzeiten und Sprache in den Märkten des Kunden, lokale Abdeckung von Steuern, Recht und Zahlung, Datenhaltung."),
 "C-09": ("Skalierbarkeit und Leistungsreserve", "Reserve für das Wachstumsziel des Kunden: Katalog- und Bestellvolumen, Lastspitzen, Skalierung über Sites und Märkte, dokumentierte Grenzen des Plans."),
 "C-10": ("Roadmap und Zukunftsfähigkeit des Herstellers", "Roadmap für die Fähigkeiten, auf die der Kunde angewiesen ist, Release-Takt, Eigentümer und wirtschaftliche Lage des Herstellers, Wartungszusage für die genannte Version."),
}
if DE:
    CRIT = [dict(c, name=CRIT_DE[c["id"]][0], description=CRIT_DE[c["id"]][1]) for c in CRIT]

# ------------------------------------------------------------------ the three fixture technologies
REQ_SHEET = t("Fachliche Anforderungen", "Functional Requirements")
REQ_SHEET_T = t("Technische Anforderungen", "Technical Requirements")
REQ_WB = "input/requirements/requirements_fixture.xlsx"
CLIENT_EV = f"input/context/strategy.md; {REQ_WB}!{REQ_SHEET}!A2"   # the client's own documents -> basis "stated by the client"
# (score, guardrail_hit, confidence, rationale) per criterion, in the order of CIDS
TECHS = [
 {"sid": "T-01", "name": "Fixture Commerce", "pack": "_generic", "version": "3.2 Business (SaaS)",
  "doc": "PS-7-001", "plans": "PS-7-002",
  "rows": [
   (9, "not-applicable", "high", t("Das Standard-B2B-Modul des Business-Plans bildet Kundenhierarchien, Preislisten je Hierarchieknoten und den Angebotsablauf ab", "Standard B2B module of the Business plan: customer hierarchies, price lists per hierarchy node, quote workflow")),
   (7, "not-applicable", "medium", t("Ein dokumentierter Konnektor für die ERP-Kategorie des Kunden ist vorhanden, das Mapping in der Middleware bleibt Projektaufgabe", "Documented outbound connector for the ERP category of the client, but the middleware mapping is a project task")),
   (8, "not-applicable", "high", t("Der Standard deckt die meisten Kernanforderungen der Liste ab, den Rest über Konfiguration", "Standard covers most of the key requirements of the list, the remainder as configuration")),
   (9, "no", "high", t("Inhalte, Preise, Aktionen und die Seitengestaltung werden in der Administration ohne Entwickler gepflegt", "Content, prices, promotions and page composition are edited in the admin without a developer")),
   (7, "not-applicable", "medium", t("Das Abonnement wird nach Bestellvolumen gestaffelt abgerechnet; das Volumen des Kunden liegt in der mittleren Stufe", "Subscription metered by order volume, tiered; the client's volume sits inside the middle tier")),
   (8, "no", "medium", t("Es gibt Partner in Region und Sprache des Kunden, mehrere davon mit Referenzen in diesem Segment", "Partners in the client's region and language, several of them with references in this segment")),
   (8, "not-applicable", "high", t("Katalog, Warenkorb und Bestellung sind vollständig über REST erreichbar, dazu gibt es eine Headless-Option für das Frontend", "Full REST coverage of catalogue, cart and order plus a headless frontend option")),
   (8, "not-applicable", "high", t("Der Hersteller hat ein Büro und Support in der Sprache des Kunden, die Daten liegen in der EU", "Vendor office and support in the client's language, data residency in the EU")),
   (7, "not-applicable", "medium", t("Die dokumentierten Grenzen des Plans liegen über dem Wachstumsziel des Kunden für Katalog und Bestellungen", "Documented limits of the plan sit above the client's growth target for catalogue and orders")),
   (8, "not-applicable", "medium", t("Zwei Releases pro Jahr; die Fähigkeiten, auf die der Kunde angewiesen ist, stehen in der öffentlichen Roadmap", "Two releases per year, the capabilities the client depends on are named in the public roadmap")),
  ],
  "caps": [
   (t("Kundenspezifische Preislisten je Kundenhierarchie", "Customer-specific price lists per customer hierarchy"), "yes", t("Standard im Business-Plan", "standard in the Business plan"), "PS-7-001", t("Preislisten hängen am Hierarchieknoten", "price lists hang on the hierarchy node")),
   (t("Konnektor für die ERP-Kategorie des Kunden", "Connector for the client's ERP category"), "partial", t("Konnektor im Business-Plan, Feld-Mapping als Projektaufgabe", "connector in the Business plan, field mapping is a project task"), "PS-7-001", t("der Konnektor überträgt Bestellungen und Bestände, nicht die Preiskonditionen", "the connector transfers orders and stock, not the price conditions")),
   (t("Seitengestaltung durch Fachanwender", "Page composition by business users"), "yes", t("Standard in jedem Plan", "standard in every plan"), "PS-7-001", t("Bausteine und Vorlagen pflegen die Fachanwender selbst", "business users maintain the building blocks and templates themselves")),
   (t("Punch-out-Beschaffung", "Punch-out procurement"), "no", t("nicht im Business-Plan", "not in the Business plan"), "PS-7-002", t("nur im Enterprise-Plan verfügbar", "available in the Enterprise plan only")),
  ],
  "risks": [
   (t("Das Abonnement wird nach Bestellvolumen abgerechnet: mit dem Wachstumsziel erreicht der Kunde innerhalb von zwei Jahren die nächste Stufe", "Subscription is metered by order volume: the growth target moves the client into the next tier within two years"), "major", "C-05", t("die nächste Stufe im Business Case einplanen", "model the next tier in the business case"), "PS-7-002"),
   (t("Punch-out ist nicht im genannten Plan enthalten, und zwei Großkunden des Kunden fragen danach", "Punch-out is not in the named plan, and two key accounts of the client ask for it"), "blocker", "C-01", t("den Plan mit dem Hersteller klären oder das Upgrade des Plans einplanen", "confirm the plan with the vendor or plan the plan upgrade"), "PS-7-002"),
  ],
  "questions": [
   ("Q-T-01-1", "client", t("Brauchen die zwei Großkunden zum Start eine Punch-out-Beschaffung?", "Do the two key accounts require punch-out procurement at go-live?"), t("entscheidet C-01 und den Lizenzplan", "decides C-01 and the licence plan"), "open", ""),
   ("Q-T-01-2", "vendor", t("Enthält der Business-Plan die Preiskonditionen im ERP-Konnektor?", "Does the Business plan include the price conditions in the ERP connector?"), t("entscheidet C-02", "decides C-02"), "open", ""),
  ]},
 {"sid": "T-02", "name": "Fixture Composable", "pack": "", "version": t("aktueller SaaS-Plan (Growth)", "current SaaS plan (Growth)"),
  "doc": "PS-7-003", "plans": "PS-7-003",
  "round": 0,
  "rows": [
   (8, "not-applicable", "medium", t("B2B-Fähigkeiten gibt es als API-Bausteine: Hierarchien und Preislisten sind vorhanden, der Einkaufsablauf wird gebaut", "B2B capabilities as API primitives: hierarchies and price lists exist, the buying workflow is built")),
   (8, "not-applicable", "medium", t("Die Anbindung läuft über die dokumentierte API-Schicht, einen fertigen Konnektor für die ERP-Kategorie des Kunden gibt es nicht", "Integration through the documented API layer, no ready connector for the client's ERP category")),
   (7, "not-applicable", "medium", t("Der Standard deckt den Commerce-Kern ab, Storefront und Pflegewerkzeuge sind Projektumfang", "Standard covers the commerce core, the storefront and the editing tools are project scope")),
   (4, "yes", "high", t("Fachanwender brauchen für die Seitengestaltung einen Entwickler: der Plan hat keine Standard-Oberfläche zur Pflege", "Business users depend on a developer for page composition: there is no standard authoring surface in the plan")),
   (5, "not-applicable", "medium", t("Das Abonnement wird nach API-Aufrufen und Bestellungen abgerechnet; das Lastmuster des Kunden ist schwer vorherzusagen", "Subscription metered by API calls and orders; the client's traffic pattern is hard to forecast")),
   (6, "no", "medium", t("Partner sind verfügbar, aber die Projekte im Segment des Kunden dauern länger als sein Zeitfenster", "Partners available, but the projects in the client's segment are longer than the client's window")),
   (10, "not-applicable", "high", t("Die Plattform ist API-first gebaut: jede Fähigkeit des Plans ist eine dokumentierte API", "API-first by design: every capability of the plan is a documented API")),
   (7, "not-applicable", "medium", t("Der Hersteller ist in der Region präsent, der Support ist nur auf Englisch verfügbar", "Vendor presence in the region, support in English only")),
   (9, "not-applicable", "high", t("Die dokumentierte Reserve liegt weit über dem Wachstumsziel des Kunden", "Documented headroom far above the client's growth target")),
   (9, "not-applicable", "high", t("Kontinuierliche Auslieferung und eine öffentliche Roadmap mit datierten Einträgen", "Continuous delivery, public roadmap with dated entries")),
  ],
  "caps": [
   (t("Kundenspezifische Preislisten je Kundenhierarchie", "Customer-specific price lists per customer hierarchy"), "yes", t("aktueller SaaS-Plan", "current SaaS plan"), "PS-7-003", t("Preislisten sind ein API-Baustein des Plans", "price lists are an API primitive of the plan")),
   (t("Seitengestaltung durch Fachanwender", "Page composition by business users"), "no", t("aktueller SaaS-Plan", "current SaaS plan"), "PS-7-003", t("das Frontend baut das Implementierungsteam", "the frontend is built by the implementation team")),
  ],
  "risks": [
   (t("Die Seitengestaltung braucht einen Entwickler, das widerspricht der Leitlinie zur Selbstständigkeit der Fachanwender", "Page composition needs a developer, which contradicts the client's autonomy guardrail"), "blocker", "C-04", t("eine Pflegeoberfläche einplanen oder die Abweichung von der Leitlinie bewusst annehmen", "budget an authoring layer or accept the guardrail miss"), "PS-7-003"),
  ],
  "questions": [
   ("Q-T-02-1", "client", t("Ist eine vom Implementierungsteam gebaute Pflegeoberfläche für die Leitlinie zur Selbstständigkeit akzeptabel?", "Is an authoring layer built by the implementation team acceptable for the autonomy guardrail?"), t("entscheidet C-04 und die Leitlinien-Tabelle", "decides C-04 and the guardrail table"), "open", ""),
  ]},
 {"sid": "T-03", "name": "Fixture Suite", "pack": "", "version": "2.4.7 Cloud",
  "doc": "PS-7-004", "plans": "PS-7-004",
  "round": 0,
  "rows": [
   (7, "not-applicable", "medium", t("B2B-Funktionen sind ein Modul der Suite: Hierarchien und Angebote sind vorhanden, Freigaben nur eingeschränkt", "B2B features are a module of the suite: hierarchies and quotes exist, approvals are limited")),
   (7, "not-applicable", "medium", t("Der Konnektor-Marktplatz deckt die ERP-Kategorie des Kunden über eine Partner-Erweiterung ab", "Connector marketplace covers the client's ERP category through a partner extension")),
   (8, "not-applicable", "medium", t("Der Standard deckt die Kernanforderungen ab, mehrere davon über mitgelieferte Erweiterungen", "Standard covers the key requirements, several of them through bundled extensions")),
   (6, "no", "medium", t("Fachanwender pflegen Inhalte und Aktionen; die Seitengestaltung braucht eine Änderung der Vorlage", "Business users edit content and promotions; page composition needs a template change")),
   (4, "not-applicable", "medium", t("Lizenz nach Bestellvolumen plus die Stufe der Cloud-Infrastruktur; die Summe liegt über der Budgetgrenze des Kunden", "Licence by order volume plus the cloud infrastructure tier; the total sits above the client's budget line")),
   (6, "no", "medium", t("Partner sind in der Region verfügbar, das Zeitfenster für die Umsetzung ist knapp, aber machbar", "Partners available in the region, the implementation window is tight but feasible")),
   (7, "not-applicable", "medium", t("REST und GraphQL decken den Commerce-Kern ab, eine Headless-Option ist dokumentiert", "REST and GraphQL coverage of the commerce core, headless option documented")),
   (8, "not-applicable", "high", t("Hersteller und Partner sind in der Sprache des Kunden präsent, die Daten liegen in der EU", "Vendor and partner presence in the client's language, EU data residency")),
   (8, "not-applicable", "high", t("Die Suite ist für Volumen über dem Wachstumsziel des Kunden dokumentiert", "Documented for volumes above the client's growth target")),
   (7, "not-applicable", "medium", t("Quartalsweise Releases; für eine Fähigkeit, auf die der Kunde angewiesen ist, gibt es keinen datierten Roadmap-Eintrag", "Quarterly releases; one capability the client depends on has no dated roadmap entry")),
  ],
  "caps": [
   (t("Kundenspezifische Preislisten je Kundenhierarchie", "Customer-specific price lists per customer hierarchy"), "yes", t("2.4.7 Cloud mit dem B2B-Modul", "2.4.7 Cloud with the B2B module"), "PS-7-004", t("setzt das B2B-Modul der Suite voraus", "requires the B2B module of the suite")),
   (t("Konnektor für die ERP-Kategorie des Kunden", "Connector for the client's ERP category"), "partial", t("Partner-Erweiterung, nicht Teil von 2.4.7", "partner extension, not part of 2.4.7"), "PS-7-004", t("gepflegt von einem Partner, nicht vom Hersteller", "maintained by a partner, not by the vendor")),
  ],
  "risks": [
   (t("Lizenz und Stufe der Cloud-Infrastruktur liegen zusammen über der Budgetgrenze, die der Kunde genannt hat", "Licence plus cloud infrastructure tier sits above the budget line the client named"), "major", "C-05", t("die kleinere Infrastrukturstufe mit dem Hersteller kalkulieren", "price the smaller infrastructure tier with the vendor"), "PS-7-004"),
  ],
  "questions": [
   ("Q-T-03-1", "vendor", t("Wird der ERP-Konnektor des Marktplatzes für 2.4.7 Cloud gepflegt?", "Is the ERP connector of the marketplace maintained for 2.4.7 Cloud?"), t("entscheidet C-02", "decides C-02"), "open", ""),
  ]},
]


def scoring_md(t_):
    lines = [f"# Technology scoring: {t_['name']}", "",
             f"- **technology:** {t_['name']}",
             f"- **pack:** {t_['pack']}",
             f"- **version_or_plan:** {t_['version']}",
             f"- **agent:** analyst-{t_['sid']}",
             "- **status:** final",
             f"- **round:** {t_.get('round', 1)}", "",
             "## Summary", "",
             f"{t_['name']} in the plan {t_['version']} is scored against the ten criteria of this decision. "
             f"{t_['rows'][0][3]}. {t_['rows'][3][3]}. The plan named here is the subject of every row: a capability of another plan is recorded as not available with the plan named.", "",
             "## Scores", "",
             head("criterion_id", "score", "rationale", "client_evidence", "vendor_evidence", "guardrail_hit", "confidence")]
    for cid, (score, gh, conf, rat) in zip(CIDS, t_["rows"]):
        lines.append(row(cid, score, rat, CLIENT_EV, t_["doc"], gh, conf))
    lines += ["", "## Capabilities", "", head("capability", "available", "version_or_plan", "locator", "notes")]
    for cap, av, ver, loc, notes in t_["caps"]:
        lines.append(row(cap, av, ver, loc, notes))
    lines += ["", "## Risks", "", head("risk", "impact", "affects_criterion", "mitigation", "evidence")]
    for r in t_["risks"]:
        lines.append(row(*r))
    lines += ["", "## Open questions", "", head("id", "to", "question", "why_needed", "status", "answer")]
    for q in t_["questions"]:
        lines.append(row(*q))
    lines += ["", "## Claims", "", head("id", "type", "statement", "evidence", "target", "supersedes")]
    return lines


def t01_claims():
    """One assessment claim per criterion, one fact claim per capability, one for the blocking risk - what the analyst brief demands."""
    t_ = TECHS[0]; out = []; n = 0
    for c, (score, gh, conf, rat) in zip(CRIT, t_["rows"]):
        n += 1
        out.append((f"C-T-01-{n:03d}", "assessment",
                    f"{t_['name']} meets '{c['name']}' at {score} of 10 in the plan {t_['version']}: {rat}."
                    + (f" The guardrail '{c['name']}' is held." if gh == "no" else ""),
                    f"{CLIENT_EV}; {t_['doc']}", f"D1/Scores:{c['id']}", ""))
    for cap, av, ver, loc, notes in t_["caps"]:
        n += 1
        out.append((f"C-T-01-{n:03d}", "fact",
                    f"'{cap}' is {av} in {ver}." + (f" {notes[0].upper()}{notes[1:]}." if notes else ""),
                    loc, f"D1/Capabilities:{cap}", ""))
    n += 1
    out.append((f"C-T-01-{n:03d}", "assessment", f"Punch-out procurement is not part of the plan {t_['version']}, and two key accounts of the client ask for it.",
                f"{t_['plans']}; input/context/strategy.md", "D1/Risks", ""))
    return out


def t01_md():
    return "\n".join(scoring_md(TECHS[0]) + [row(*c) for c in t01_claims()] + [""]) + "\n"


def short_md(t_, claims):
    lines = scoring_md(t_) + [row(*c) for c in claims] + [""]
    return "\n".join(lines) + "\n"


def critic_md(scope, critic, rows, missing, estate):
    lines = [f"# Gauntlet score: {scope} / {critic} / round 1", "",
             f"- **scope:** {scope}", f"- **critic:** {critic}", "- **round:** 1", "",
             "## Scores", "", head("claim_id", "score", "verdict", "issue", "counter_evidence", "fix_hint")]
    lines += [row(*r) for r in rows]
    lines += ["", "## Missing claims", ""] + [f"- {m}" for m in missing]
    lines += ["", "## Estate observations", ""] + ([f"- {e}" for e in estate] if estate else [])
    lines += ["", "## Summary", "", "Fixture review: every claim carries both locators and the plan it refers to; the scores are comparable across the criteria.", ""]
    return "\n".join(lines) + "\n"


def main():
    # ---------------- run.json
    p = J("run.json")
    p["engagement"].update({"consultancy": "Fixture Consulting", "client": "Fixture Retail GmbH",
                            "client_context": t("B2B-Händler für Ersatzteile, 30 Mio. EUR Umsatz, Wachstumsziel 100 Mio. EUR, DACH und Benelux, SAP als führendes System.",
                                                "B2B spare-parts distributor, 30 M EUR revenue, growth target 100 M EUR, DACH plus Benelux, SAP as the system of record."),
                            "title": t("Technologiebewertung Fixture", "Technology scoring fixture")})
    p["decision"] = {"question": t("Neuaufbau des B2B-Shops bis Q4 2026 - welche Technologien kommen für das Entscheidungsgremium auf die Shortlist.",
                                   "Replatform the B2B shop by Q4 2026 - which technologies go on the shortlist for the decision board."),
                     "timeline": t("Projektstart Q1 2026, Go-live Q4 2026", "project start Q1 2026, go-live Q4 2026"),
                     "guardrails": t("Standard vor Eigenentwicklung; Fachanwender ändern Inhalte und Preise ohne Entwickler; SAP bleibt das führende System",
                                     "standard before custom development; business users change content and prices without a developer; SAP stays the system of record")}
    p["technologies"] = [{"name": t_["name"], "pack": (t_["pack"] or None), "version_or_plan": t_["version"]} for t_ in TECHS]
    p["criteria"] = CRIT
    p["shortlist"] = {"size": 2}
    if DE: p["unit"] = {"noun": "Technologie", "noun_plural": "Technologien"}
    W("run.json", p)

    # ---------------- client context + requirements
    w("input/context/strategy.md", """\
    # Strategy and guardrails (fixture)

    Fixture Retail GmbH sells spare parts to workshops and industrial customers in DACH and Benelux.
    Revenue 30 M EUR, growth target 100 M EUR in three years. SAP stays the system of record for
    products, prices and orders. The board wants standard functionality before custom development,
    business users must change content and prices without a developer, and the shop must go live in Q4 2026.
    Two key accounts buy through their own procurement systems today.
    """)
    requirements_workbook()

    # ---------------- analyses
    w(f"analysis/scopes/{TECHS[0]['sid']}.md", t01_md())
    w(f"analysis/scopes/{TECHS[1]['sid']}.md", short_md(TECHS[1], [
        ("C-T-02-001", "assessment", f"{TECHS[1]['name']} has no standard authoring surface for page composition in the current plan, so business users depend on a developer.", f"{TECHS[1]['doc']}; input/context/strategy.md", "D1/Scores:C-04", ""),
        ("C-T-02-002", "fact", "Customer-specific price lists per customer hierarchy are part of the current SaaS plan.", TECHS[1]["doc"], f"D1/Capabilities:{TECHS[1]['caps'][0][0]}", ""),
    ]))
    w(f"analysis/scopes/{TECHS[2]['sid']}.md", short_md(TECHS[2], [
        ("C-T-03-001", "assessment", f"The ERP connector {TECHS[2]['name']} offers for the client's ERP category comes from a partner extension and is not part of the release.", TECHS[2]["doc"], "D1/Scores:C-02", ""),
        ("C-T-03-002", "assessment", "Licence and cloud infrastructure tier together sit above the budget line the client named.", f"{TECHS[2]['doc']}; input/context/strategy.md", "D1/Scores:C-05", ""),
    ]))

    # ---------------- reviewer files: one technology and the consolidation (every claim scored by both reviewers)
    ids = [c[0] for c in t01_claims()]
    w("analysis/gauntlet/T-01/round1-client.md", critic_md("T-01", "client",
        [(cid, 8 + (i % 2), "confirmed" if i % 2 == 0 else "insightful", "", "", "") for i, cid in enumerate(ids)],
        ["No statement on whether the quote workflow covers the approval step the requirement list asks for"],
        []))
    w("analysis/gauntlet/T-01/round1-standard.md", critic_md("T-01", "standard",
        [(cid, 9 - (i % 2), "insightful" if i % 2 == 0 else "confirmed", "", "", "") for i, cid in enumerate(ids)],
        ["No statement on the maintenance window of the named plan"],
        ["Punch-out is documented as an Enterprise-plan capability across this product family, which also affects the plan comparison of the other candidates"]))
    sl = [("C-SHORTLIST-001", 9, "confirmed", "", "", ""), ("C-SHORTLIST-002", 9, "insightful", "", "", ""),
          ("C-SHORTLIST-003", 8, "confirmed", "", "", ""), ("C-SHORTLIST-004", 9, "insightful", "", "", "")]
    w("analysis/gauntlet/SHORTLIST/round1-client.md", critic_md("SHORTLIST", "client", sl,
        ["No statement on which guardrail the board would have to relax for the second-ranked technology"], []))
    w("analysis/gauntlet/SHORTLIST/round1-standard.md", critic_md("SHORTLIST", "standard", sl,
        ["No statement on the release cadence differences between the three candidates"], []))

    # ---------------- consolidation
    w("analysis/consolidated/SHORTLIST.md", shortlist_md())

    # ---------------- gate + management summary
    w("analysis/gate/round1-cto.md", """\
    # Final gate: cto / round 1
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
    | I1 | D1 | Parameters!D1 | the weight column does not say that it is the only cell meant to be edited | presentation | minor | K2 | say it in the column header |

    ## Summary
    The ranking reacts to a changed weight, and every score names a mechanism and a source.
    """)
    w("analysis/summaries/D1.md", t("""\
    # Ergebnis

    {kpi:technologies} Technologien wurden gegen {kpi:criteria} Kriterien der Entscheidung von Fixture Retail GmbH bewertet. Fixture Commerce und Fixture Composable kommen auf die Shortlist, Fixture Suite nicht.

    Fixture Commerce führt, weil das Standard-B2B-Modul die Kundenhierarchien und Preislisten der Anforderungsliste abdeckt und Fachanwender Inhalte und Preise ohne Entwickler ändern. Offen ist die Punch-out-Anbindung der zwei Großkunden, die der genannte Plan nicht enthält.

    # Gewichtung

    Die Gewichte der Kriterien sind auf dem Blatt Parameters editierbar: ein geändertes Gewicht rechnet alle Gesamtwerte und das Ranking neu, so sieht das Gremium sofort, wie stark das Ergebnis von der gewählten Gewichtung abhängt.
    """, """\
    # Result

    {kpi:technologies} technologies were scored against {kpi:criteria} criteria of Fixture Retail GmbH's replatforming decision. Fixture Commerce and Fixture Composable go on the shortlist; Fixture Suite does not.

    Fixture Commerce leads because its standard B2B module covers the customer hierarchies and price lists of the requirement list and because business users change content and prices without a developer. Its open point is the procurement connection of the two key accounts, which the named plan does not contain.

    # Weighting

    The weights of the criteria are editable on the sheet Parameters: changing a weight recalculates every total and the ranking, so the board can see immediately how much the result depends on the weighting it chose.
    """))
    print("fixture written to", T)


def shortlist_md():
    lines = ["# Technology shortlist and weighted ranking", "",
             "- **status:** final", "- **round:** 1", "- **evaluated:** 3", "- **shortlist_size:** 2", "",
             "## Ranking", "",
             head("technology", "weighted_total_note", "rank", "shortlisted", "fit_statement", "partner_explanation"),
             row("Fixture Commerce", t("getragen von der Passung zum Geschäftsmodell und der Selbstständigkeit der Fachanwender, gebremst von der Lizenzstufe", "carried by the business model fit and the autonomy of business users, held back by the licence tier"), 1, "yes",
                 t("Fixture Commerce deckt Kundenhierarchien, Preislisten und den Angebotsablauf der Anforderungsliste mit dem Standard-B2B-Modul ab, und Fachanwender ändern Inhalte und Preise ohne Entwickler - die Leitlinie, die das Gremium zuerst genannt hat. Offen ist die Beschaffung: Punch-out ist nicht Teil des Business-Plans, und zwei Großkunden fragen danach.",
                   "Fixture Commerce covers the customer hierarchies, price lists and quote workflow of the requirement list with its standard B2B module, and business users change content and prices without a developer, which is the guardrail the board named first. The open point is procurement: punch-out is not part of the Business plan and two key accounts ask for it."),
                 t("Der hier genannte Plan enthält keine Punch-out-Beschaffung; der Eintrag auf der Shortlist setzt deshalb ein Upgrade des Plans oder eine spätere Phase für diese zwei Kunden voraus.",
                   "The plan named here does not contain punch-out procurement, so the shortlist entry assumes either a plan upgrade or a later phase for those two accounts.")),
             row("Fixture Composable", t("getragen von der Passung zur Architektur und der Leistungsreserve, gebremst vom Kriterium Selbstständigkeit", "carried by the architecture fit and the headroom, held back by the autonomy criterion"), 2, "yes",
                 t("Fixture Composable bietet jede Fähigkeit des Plans als dokumentierte API und hat eine Reserve weit über dem Wachstumsziel; das passt zur Zielarchitektur des Kunden. Die Technologie kommt mit einer offenen Leitlinie auf die Shortlist: die Seitengestaltung braucht einen Entwickler, solange keine Pflegeoberfläche gebaut wird.",
                   "Fixture Composable offers every capability of its plan as a documented API and has headroom far above the growth target, which fits the client's target architecture. It goes on the shortlist with one open guardrail: page composition needs a developer unless an authoring layer is built."),
                 t("Fixture Composable passt gut zu einer API-first-Landschaft. Für diesen Kunden ist die Leitlinie zur Selbstständigkeit die offene Frage, weil der Plan keine Standard-Oberfläche für Fachanwender hat.",
                   "Fixture Composable is a strong fit for an API-first landscape. For this client the autonomy guardrail is the open question, because the plan has no standard authoring surface for business users.")),
             row("Fixture Suite", t("getragen von der Standardabdeckung und der Präsenz in der Region, gebremst von den Betriebskosten", "carried by the standard coverage and the regional presence, held back by the cost of ownership"), 3, "no",
                 t("Fixture Suite deckt die Kernanforderungen breit im Standard ab, liegt mit Lizenz und Infrastruktur aber über der Budgetgrenze des Projekts.",
                   "Fixture Suite covers the key requirements broadly in the standard, but licence and infrastructure sit above the project's budget line."),
                 t("Fixture Suite ist eine ausgereifte Suite mit breiter Standardabdeckung und starker Partnerpräsenz in der Region des Kunden. Für diesen Kunden liegen Lizenz und Stufe der Cloud-Infrastruktur zusammen über der Budgetgrenze des Projekts, und der Konnektor für die ERP-Kategorie des Kunden kommt aus einer Partner-Erweiterung statt vom Hersteller. Deshalb kommt Fixture Suite in diesem Kontext nicht auf die Shortlist.",
                   "Fixture Suite is a mature suite with broad standard coverage and a strong partner presence in the client's region. For this client the licence together with the cloud infrastructure tier sits above the budget line named for the project, and the connector for the client's ERP category comes from a partner extension rather than from the vendor. Therefore Fixture Suite does not go on the shortlist in this context.")),
             "", "## Calibration", "",
             head("row_id", "technology", "criterion_id", "score_before", "score_after", "reason"),
             row("Fixture Composable/C-04", "Fixture Composable", "C-04", 5, 4, "Fixture Suite scores 6 for the same mechanism with a template change; a plan without any standard authoring surface cannot sit above it"),
             row("Fixture Suite/C-05", "Fixture Suite", "C-05", 5, 4, "the same budget comparison gives Fixture Composable a 5 with an uncertain forecast; a total above the named budget line scores lower"),
             "", "## Guardrails", "",
             head("technology", "guardrail", "hit", "note")]
    g_aut = t("Fachanwender ändern Inhalte und Preise ohne Entwickler", "business users change content and prices without a developer")
    g_std = t("Standard vor Eigenentwicklung", "standard before custom development")
    lines += [row("Fixture Commerce", g_aut, "no", t("die Seitengestaltung ist in jedem Plan Teil der Administration (C-T-01-013)", "page composition is part of the admin in every plan (C-T-01-013)")),
              row("Fixture Commerce", g_std, "no", t("der Standard deckt die meisten Kernanforderungen ab (C-T-01-003)", "most of the key requirements are covered by standard functionality (C-T-01-003)")),
              row("Fixture Composable", g_aut, "yes", t("der Plan hat keine Standard-Oberfläche zur Pflege; die Seitengestaltung braucht einen Entwickler (C-T-02-001)", "the plan has no standard authoring surface; page composition needs a developer (C-T-02-001)")),
              row("Fixture Composable", g_std, "unclear", t("der Commerce-Kern ist Standard, Storefront und Pflegewerkzeuge sind Projektumfang - die offene Annahme entscheidet es", "the commerce core is standard, the storefront and the editing tools are project scope - the open assumption decides it")),
              row("Fixture Suite", g_aut, "no", t("Fachanwender pflegen Inhalte und Aktionen; die Seitengestaltung braucht eine Änderung der Vorlage", "content and promotions are edited by business users; page composition needs a template change")),
              row("Fixture Suite", g_std, "no", t("die Kernanforderungen deckt der Standard mit mitgelieferten Erweiterungen ab", "the key requirements are covered by standard functionality and bundled extensions")),
              "", "## Open questions", "",
              head("id", "to", "question", "why_needed", "status", "answer"),
              row("Q-SL-1", "client", "Do the two key accounts require punch-out procurement at go-live? (effect of the answer: the leading technology needs a plan upgrade or a later phase)", "decides the first rank and the licence plan", "open", ""),
              row("Q-SL-2", "client", "Is an authoring layer built by the implementation team acceptable for the autonomy guardrail? (effect of the answer: the second shortlist entry loses its guardrail hit)", "decides the guardrail table for the second-ranked technology", "open", ""),
              "", "## Claims", "",
              head("id", "type", "statement", "evidence", "target", "supersedes"),
              row("C-SHORTLIST-001", "assessment", "Fixture Commerce reaches the highest weighted total of the three technologies with the weights the board set, carried by the business model fit and the autonomy of business users.", "analysis/scopes/T-01.md; state/requirements.json", "D1/Shortlist:Fixture Commerce", ""),
              row("C-SHORTLIST-002", "assessment", "Fixture Composable cannot hold the autonomy guardrail in its current plan: page composition needs a developer.", "analysis/scopes/T-02.md; input/context/strategy.md", "D1/Guardrails:Fixture Composable", ""),
              row("C-SHORTLIST-003", "assessment", "Fixture Suite does not reach the shortlist because licence and infrastructure tier together sit above the budget line named for the project.", "analysis/scopes/T-03.md; input/context/strategy.md", "D1/Shortlist:Fixture Suite", ""),
              row("C-SHORTLIST-004", "assessment", "Two of the three technologies reach the client's ERP category only through a partner extension or a project mapping, so the integration effort is comparable for both.", "analysis/scopes/T-01.md; analysis/scopes/T-03.md", "D1/Scores:C-02", ""),
              ""]
    return "\n".join(lines) + "\n"


def requirements_workbook():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = REQ_SHEET
    ws.append(["ID", "Epic", "Title", "Description", "Acceptance criteria", "Exclusions", "References", "Phase", "Priority", "Sources"])
    ws.append(["FR-009", "B2B pricing", "Customer-specific price lists", "Every customer hierarchy node has its own price list.", "1) price list per node", "No manual price maintenance in the shop", "TR-01", "MVP", "must", "WS1"])
    ws.append(["FR-023", "Content", "Business users edit content", "Content, prices and promotions are changed without a developer.", "1) page composition in the admin", "", "", "MVP", "must", "WS1"])
    ws.append(["FR-030", "Procurement", "Punch-out for key accounts", "Two key accounts order through their own procurement systems.", "", "", "", "Phase 2", "should", "WS2"])
    ws2 = wb.create_sheet(REQ_SHEET_T)
    ws2.append(["ID", "Epic", "Title", "Description", "Acceptance criteria", "Exclusions", "References", "Phase", "Priority", "Sources"])
    ws2.append(["TR-01", "Integration", "ERP stays the system of record", "Products, prices and orders are mastered in the ERP.", "", "", "FR-009", "MVP", "must", "TECH"])
    os.makedirs(os.path.join(T, "input/requirements"), exist_ok=True)
    wb.save(os.path.join(T, REQ_WB))
    m = J("requirements_mapping.json")
    cols = {"id": "ID", "epic": "Epic", "title": "Title", "description": "Description", "acceptance_criteria": "Acceptance criteria",
            "exclusions": "Exclusions", "references": "References", "phase": "Phase", "sources": "Sources", "priority": "Priority"}
    m["sheets"] = [{"sheet": REQ_SHEET, "group": "functional", "id_prefix": "FR-", "header_row": 1, "columns": cols, "extra_columns": []},
                   {"sheet": REQ_SHEET_T, "group": "technical", "id_prefix": "TR-", "header_row": 1, "columns": cols, "extra_columns": []}]
    m["phase_values_in_scope"] = ["MVP"]
    W("requirements_mapping.json", m)


if __name__ == "__main__":
    main()
