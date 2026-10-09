#!/usr/bin/env python3
"""Write toy engagement content into an initialised RUN folder (single-run project) so the whole chain can be smoke-tested.
Usage: python3 methods/code-analysis/fixtures/make_fixture.py <run_dir> [generic|sap]
  generic: fills run.json placeholders, fake repo for the _generic pack (composer-like 'unit.json' manifests), requirements workbook, sample analysis documents
  sap:     fake hybris-shaped repo (extensioninfo.xml, items.xml, spring, impex, localextensions, build.number) for the sap-commerce pack + requirements workbook
"""
import os, sys, json, textwrap
T = os.path.abspath(sys.argv[1]); MODE = sys.argv[2] if len(sys.argv) > 2 else "generic"
def w(p, s):
    p = os.path.join(T, p); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(textwrap.dedent(s))
def J(p): return json.load(open(os.path.join(T, p), encoding="utf-8"))
def W(p, d): json.dump(d, open(os.path.join(T, p), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
def t(de, en):
    """client-facing fixture text in the run's deliverable language (the customer edition must read German throughout in a German run)"""
    return de if J("run.json").get("languages", {}).get("deliverable") == "de" else en

def requirements_workbook():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Functional Requirements"
    ws.append(["ID", "Epic", "Title", "Description", "Acceptance criteria", "Exclusions", "References", "Phase", "Sources"])
    ws.append(["FR-009", "Installed base", "Equipment list", "Customers see their installed machines.", "1) list per unit", "No service booking", "TR-01", "MVP", "WS1"])
    ws.append(["FR-023", "Catalog", "Successor products", "Discontinued products show successors.", "1) successor shown on PDP", "", "", "MVP", "WS2"])
    ws.append(["FR-030", "Checkout", "Split delivery", "Orders may be split by plant.", "", "", "", "Phase 2", "WS2"])
    ws2 = wb.create_sheet("Technical Requirements"); ws2.append(["ID", "Epic", "Title", "Description", "Acceptance criteria", "Exclusions", "References", "Phase", "Sources"])
    ws2.append(["TR-01", "Integration", "ERP order transfer", "Orders go to the ERP via middleware.", "", "", "FR-009", "MVP", "TECH"])
    lg = wb.create_sheet("Legende"); lg.append(["Kürzel", "Dokument"])
    for k, de, en in (("WS1", "Workshop 1 Zielbild und Scope (12.05.2026)", "Workshop 1 target picture and scope (2026-05-12)"), ("WS2", "Workshop 2 Katalog und Checkout (19.05.2026)", "Workshop 2 catalogue and checkout (2026-05-19)"),
                      ("TECH", "Technische Bestandsaufnahme der Schnittstellen (26.05.2026)", "Technical assessment of the interfaces (2026-05-26)")): lg.append([k, t(de, en)])
    os.makedirs(os.path.join(T, "input/requirements"), exist_ok=True); wb.save(os.path.join(T, "input/requirements/requirements_fixture.xlsx"))
    m = J("requirements_mapping.json")
    cols = {"id": "ID", "epic": "Epic", "title": "Title", "description": "Description", "acceptance_criteria": "Acceptance criteria", "exclusions": "Exclusions", "references": "References", "phase": "Phase", "sources": "Sources", "priority": None}
    m["sheets"] = [{"sheet": "Functional Requirements", "group": "functional", "id_prefix": "FR-", "header_row": 1, "columns": cols, "extra_columns": []}, {"sheet": "Technical Requirements", "group": "technical", "id_prefix": "TR-", "header_row": 1, "columns": cols, "extra_columns": []}]
    m["phase_values_in_scope"] = ["MVP"]; m["legend_sheet"] = "Legende"; W("requirements_mapping.json", m)

def fill_project(extra):
    p = J("run.json")
    p["engagement"].update({"consultancy": "Fixture Consulting", "client": "Fixture Shop GmbH", "client_context": "B2B spare-parts shop, toy data.", "title": "Code analysis fixture"})
    p["repo"] = {"path": "repo"}
    for k, v in extra.items(): p[k] = {**p.get(k, {}), **v}
    W("run.json", p)

if MODE == "generic":
    fill_project({"source": {"version": "1.0 on-premise", "frontend": "server-side templates", "language_stack": "Java 17"}, "target": {"version": "2.0", "frontend": "composable storefront"}, "unit": {"repo_roots": ["src"], "standard_dirs": ["vendor"]}})
    # generic pack uses composer.json as manifest; fixture units use it too
    def unit(name, requires, desc):
        w(f"repo/src/{name}/composer.json", json.dumps({"name": f"fixture/{name}", "description": desc, "require": {f"fixture/{r}" if not r.startswith("platform-") else f"vendor/{r}": "*" for r in requires}}))
    unit("shopcore", ["platform-core"], "Core services and data model"); unit("shopfacade", ["shopcore", "platform-checkout"], "Facades / DTO conversion")
    unit("shopstorefront", ["shopfacade", "platform-storefront", "platform-cms"], "Server-side storefront"); unit("shopapi", ["shopfacade", "platform-core"], "Custom REST API"); unit("shopintegration", ["shopcore", "erp-connector-x"], "ERP integration")
    for v in ("platform-core", "platform-checkout", "platform-cms", "platform-storefront"): w(f"repo/vendor/{v}/composer.json", json.dumps({"name": f"vendor/{v}", "require": {}}))
    w("repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java", "package com.shop.core.order;\nimport com.vendor.core.order.DefaultCartService;\nimport com.vendor.core.session.LegacySession;\npublic class ShopCartService extends DefaultCartService {\n    public void recalc() { LegacySession.current().set(\"x\", 1); }\n}\n")
    w("repo/src/shopcore/src/main/java/com/vendor/core/b2b/DefaultUnitService.java", "package com.vendor.core.b2b;\npublic class DefaultUnitService { int patched; }\n")
    w("repo/src/shopcore/src/main/java/com/shop/core/equipment/EquipmentService.java", "package com.shop.core.equipment;\npublic interface EquipmentService { }\n")
    w("repo/src/shopcore/src/test/java/com/shop/core/FooTest.java", "package com.shop.core;\npublic class FooTest { }\n")
    w("repo/src/shopcore/src/main/resources/shopcore-di.xml", "<beans>\n  <alias name=\"shopCartService\" alias=\"cartService\"/>\n  <bean id=\"shopCartService\" class=\"com.shop.core.order.ShopCartService\"/>\n</beans>\n")
    w("repo/src/shopcore/src/main/resources/data/essential-usergroups.impex", "INSERT_UPDATE UserGroup;uid[unique=true]\n;reseller\n")
    w("repo/src/shopstorefront/src/main/java/com/shop/storefront/EquipmentPageController.java", "package com.shop.storefront;\nimport org.springframework.stereotype.Controller;\n@Controller\npublic class EquipmentPageController extends AbstractPageController { }\n")
    w("repo/src/shopstorefront/src/main/webapp/pages/equipment.jsp", "<div>equipment</div>\n<c:forEach items=\"${equipments}\" var=\"e\">${e.serialNumber}</c:forEach>\n")
    w("repo/src/shopstorefront/src/main/resources/data/cms-content.impex", "INSERT_UPDATE ShopEquipmentListComponent;uid[unique=true]\n;equipmentList\nINSERT_UPDATE ParagraphComponent;uid[unique=true]\n;p1\n")
    w("repo/src/shopapi/src/main/java/com/shop/api/EquipmentController.java", "package com.shop.api;\nimport org.springframework.web.bind.annotation.RestController;\n@RestController\npublic class EquipmentController { }\n")
    w("repo/src/shopintegration/src/main/java/com/shop/integration/ErpOrderOutbound.java", "package com.shop.integration;\nimport org.springframework.web.client.RestTemplate;\npublic class ErpOrderOutbound { RestTemplate t; /* SAP IDoc */ }\n")
    w("repo/composer.json", json.dumps({"name": "fixture/shop", "version": "1.0.3"}))
    W("overrides/knowledge.json", {"entry_point_patterns": {"frontend_controller": "@Controller\\b|extends AbstractPageController", "api_controller": "@RestController\\b"}, "override_patterns": {"di_override": "<alias name=\"\\w+\" alias=\"|decorates=\"", "class_shadowing_namespace_prefixes": ["com.vendor."]},
        "deprecation_patterns": [{"id": "DEP-LEGACY-SESSION", "title": "LegacySession usage", "pattern": "LegacySession", "file_glob": "*.java", "since": "1.0", "replacement": "SessionService", "verify": True}],
        "target_api_endpoint_families": ["/store-api/cart", "/store-api/product"], "target_content_component_types": ["ParagraphComponent", "BannerComponent"], "source_content_component_pattern": "INSERT_UPDATE (\\w+Component)"})
    requirements_workbook()
    # sample analysis documents - the free text a customer edition shows is written in the deliverable language (hygiene layer: German throughout)
    w("analysis/inventory/inventory_analysis.md", f"""\
# Inventory analysis (D1)
- **status:** final
- **round:** 1

## Repo notes
{t("Fixture-Repository mit fünf eigenen Modulen; Herstellercode liegt unter repo/vendor.", "Fixture repository with five custom modules; vendor code checked in under repo/vendor.")}

## Platform
- **version:** 1.0.3
- **version_confidence:** high
- **runtime:** Java 17
- **hosting:** {t("eigenes Rechenzentrum", "on-premise")}
- **frontend_technology:** {t("serverseitige Templates", "server-side templates")}
- **database:** MySQL 8
- **search:** Solr
- **evidence:** repo/composer.json
- **notes:** {t("Die Version steht im Manifest des Repositorys.", "The version is taken from the repository manifest.")}

## Units
| name | category | sub_categories | description | template_origin | activation | notes |
|---|---|---|---|---|---|---|
| shopcore | core | data | {t("Kernservices und eigenes Datenmodell für installierte Maschinen und den Warenkorb", "Core services and data model (equipment, cart)")} | vendor-core-template | active | {t("überlagert eine Standardklasse", "shadows a standard class")} |
| shopfacade | facade | | {t("Fassaden und Umwandlung in Datenobjekte für Storefront und API", "Facades and DTO conversion for storefront and API")} | vendor-facade-template | active | |
| shopstorefront | frontend | | {t("Serverseitige Storefront-Seiten", "Server-side storefront pages")} | vendor-storefront-template | active | |
| shopapi | api | | {t("Eigene REST-API für Maschinenlisten", "Custom REST API for equipment lists")} | | active | |
| shopintegration | integration | | {t("ERP-Anbindung für die Auftragsübertragung", "ERP connection for the order transfer")} | | dead | {t("in keiner Konfiguration geladen", "loaded by no configuration")} |

## Third-party packages
| name | kind | installed_on | source | notes |
|---|---|---|---|---|
| erp-connector-x | third-party | shopintegration | repo/src/shopintegration/composer.json | {t("Partnerpaket für die ERP-Anbindung", "partner package for the ERP connection")} |

## Deprecations
| id | what | units | status | since | replacement | verified_against | evidence |
|---|---|---|---|---|---|---|---|
| DEP-LEGACY-SESSION | {t("LegacySession im ShopCartService", "LegacySession usage in ShopCartService")} | shopcore | deprecated | 1.0 | SessionService | PS-7-001 | repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java:5 |

## Dependency notes
| from | to | kind | note | evidence |
|---|---|---|---|---|
| shopintegration | shopcore | runtime-di | {t("nutzt den Auftragsservice von shopcore", "uses the order service of shopcore")} | repo/src/shopcore/src/main/resources/shopcore-di.xml:2 |

## Claims
| id | type | statement | evidence | target | supersedes |
|---|---|---|---|---|---|
| C-D1-001 | fact | The platform version is 1.0.3. | repo/composer.json | D1/Platform | |
| C-D1-002 | assessment | shopcore is the dependency hub: every other module depends on it directly or via shopfacade. | repo/src/shopfacade/composer.json | D1/Dependencies | |
| C-D1-003 | fact | shopcore, shopfacade, shopstorefront and shopapi are loaded by the shop build. | repo/composer.json | D1/Units:shopcore,shopfacade,shopstorefront,shopapi | |
| C-D1-004 | fact | shopintegration is loaded by no configuration of the shop build. | repo/src/shopintegration/composer.json | D1/Units:shopintegration | |
""")
    w("analysis/units/shopcore.md", f"""\
# Unit analysis: shopcore
- **unit:** shopcore
- **agent:** unit-shopcore
- **wave:** 1
- **status:** final
- **round:** 1

## Summary
Core module with the own data model for installed equipment and changes to cart behaviour.

## Classification
- **depth:** heavy
- **rationale:** {t("Überschreibt den Standard-Warenkorbservice und überlagert DefaultUnitService.", "Overrides cartService and shadows DefaultUnitService.")}
- **confidence:** high
- **migration_relevance:** backend-only
- **disposition:** adapt-api
- **disposition_rationale:** {t("Die Warenkorblogik bleibt im Backend und wird über die Ziel-API angeboten; der überlagerte Einheitenservice wird durch Konfiguration ersetzt.", "cart logic stays in the backend and is exposed through the target API; the shadowed unit service is replaced by configuration.")}
- **key_statement:** {t("Die Warenkorblogik zieht mit um; nur der überlagerte Einheitenservice muss vor dem Upgrade ersetzt werden.", "The cart logic moves along; only the shadowed unit service must be replaced before the upgrade.")}

## Code units
| fqn | kind | standard_counterpart | purpose | file | lines | count |
|---|---|---|---|---|---|---|
| com.shop.core.order.ShopCartService | overridden | cartService (DefaultCartService) | {t("Neuberechnung des Warenkorbs mit Maschinenbezug", "cart recalculation with equipment context")} | repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java | 1-6 | |
| com.vendor.core.b2b.DefaultUnitService | shadowed | com.vendor.core.b2b.DefaultUnitService | {t("geänderte Ermittlung der Kundeneinheit", "patched unit resolution")} | repo/src/shopcore/src/main/java/com/vendor/core/b2b/DefaultUnitService.java | | |
| com.shop.core.equipment.EquipmentService | new | | {t("Abfrage installierter Maschinen", "equipment lookup")} | repo/src/shopcore/src/main/java/com/shop/core/equipment/EquipmentService.java | | |

## Data model
| type | kind | base | attributes_added | attributes | purpose | standard_alternative | file | data_class | source_of_truth |
|---|---|---|---|---|---|---|---|---|---|
| Product | extended-standard-type | Product | 2 | materialGroup; successorProduct | {t("ERP-Materialgruppe und Nachfolgeprodukt", "ERP material group and successor")} | ProductReference (SUCCESSOR) | repo/src/shopcore/schema.xml | master-reloadable | ERP |
| Equipment | new-type | Item | 1 | serialNumber | {t("installierte Maschinen", "installed base")} | | repo/src/shopcore/schema.xml | master-shop-owned | |

## Workflows
| name | kind | standard_counterpart | purpose | file |
|---|---|---|---|---|
| order-process | customized-standard | platform order-process | {t("sendet den Auftrag an das ERP", "sends order to ERP")} | repo/src/shopcore/process/order-process.xml |

## Scheduled jobs
shopcore defines no cron job, console command on a schedule or queue worker.

| name | job_class | purpose | file |
|---|---|---|---|

## Data scripts
| area | kind | files | notes |
|---|---|---|---|
| user groups | new | repo/src/shopcore/src/main/resources/data/essential-usergroups.impex | |

## Patched standard behaviour
| what | how | standard_behaviour | custom_behaviour | risk_for_upgrade | security_relevant | consequence | file | lines | client_attention |
|---|---|---|---|---|---|---|---|---|---|
| {t("Ermittlung der Kundeneinheit", "unit resolution")} | class-shadowing | {t("Einheit aus dem Kundenkonto", "unit from customer")} | {t("Einheit aus dem gewählten Werk", "unit from selected plant")} | high | yes | {t("Nach einem Upgrade kann ein Kunde Maschinen und Preise einer fremden Einheit sehen, bis der Eingriff ersetzt ist.", "After an upgrade a customer may see equipment and prices of another unit until the patch is replaced.")} | repo/src/shopcore/src/main/java/com/vendor/core/b2b/DefaultUnitService.java | 1-2 | yes |

## Requirements
| req_id | contribution | evidence | rationale | standard_alternative | standard_alternative_confidence | beyond_requirement |
|---|---|---|---|---|---|---|
| FR-009 | implements | repo/src/shopcore/schema.xml | type Equipment holds installed machines per unit | | | equipment can also be marked as decommissioned, which FR-009 does not mention |
| FR-023 | partially-implements | repo/src/shopcore/schema.xml | attribute successorProduct | ProductReference type SUCCESSOR (standard) | high | |

## Undocumented behaviour
| id | behaviour | users | nearest_requirement | relation | proposed_epic | business_value | evidence | confidence |
|---|---|---|---|---|---|---|---|---|
| UB-shopcore-01 | Equipment can be marked decommissioned and disappears from the list | customer admin | FR-009 | extends-requirement | Installed base | keeps the list clean | repo/src/shopcore/schema.xml | medium |
| UB-shopcore-02 | Reseller user group gets a separate price list per plant | reseller | | not-described | Roles | reseller pricing | repo/src/shopcore/src/main/resources/data/essential-usergroups.impex:2 | medium |

## Target API features
| feature_id | feature | primary_requirement | current_implementation | entry_points | target_api_coverage | target_api_endpoints | custom_api_exists | custom_api_needed | content_dependency | content_components | state_dependency | verdict | rationale | related_requirements | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F-shopcore-1 | Equipment list | FR-009 | storefront controller + template via EquipmentService | EquipmentPageController | none | | yes | | custom-components | ShopEquipmentListComponent | none | needs-api-work | own API exists in shopapi | FR-009 | repo/src/shopapi/src/main/java/com/shop/api/EquipmentController.java |
| F-shopcore-2 | Reseller plant price list | UB-shopcore-02 | price factory reads the reseller group | PriceController | partial | /store-api/product | no | plant parameter on the price endpoint | none | | none | needs-api-work | standard price endpoint lacks the plant dimension | | repo/src/shopcore/src/main/resources/data/essential-usergroups.impex:2 |

## Migration concerns
| topic | affected_requirements | finding | impact | recommendation | consequence | evidence | client_attention |
|---|---|---|---|---|---|---|---|
| session | FR-009; FR-030 | {t("Die Neuberechnung des Warenkorbs hängt an einem Attribut der Server-Session.", "LegacySession attribute for cart recalculation")} | major | {t("Das Kennzeichen als Warenkorbattribut führen.", "move to cart attribute")} | {t("Bei mehreren Servern kann ein Warenkorb falsch berechnet werden.", "With several servers a cart may be calculated wrongly.")} | repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java:5 | yes |
| deployment-config | TR-01 | {t("Das Webmodul des Auftragsprozesses ist dem Storefront-Aspekt zugeordnet.", "the order process web module is declared on the storefront aspect")} | major | {t("Das Modul im Manifest dem API-Aspekt zuordnen.", "move it to the api aspect in the manifest")} | | repo/composer.json | |

## Deprecations
The scanner recorded no deprecation hit for shopcore in this fixture and the review found none.

| what | status | since | replacement | evidence |
|---|---|---|---|---|

## Integrations
| system | direction | mechanism | data_objects | trigger | implementation | purpose | target_note | evidence |
|---|---|---|---|---|---|---|---|---|
| ERP | outbound | middleware | order | async | custom | order transfer via process | unchanged, backend only | repo/src/shopcore/process/order-process.xml |

## Claims
| id | type | statement | evidence | target | supersedes |
|---|---|---|---|---|---|
| C-shopcore-001 | fact | shopcore overrides the standard service cartService with ShopCartService. | repo/src/shopcore/src/main/resources/shopcore-di.xml:2-3 | D2/Code_units | |
| C-shopcore-002 | assessment | The shadowed DefaultUnitService is the biggest upgrade risk in shopcore. | repo/src/shopcore/src/main/java/com/vendor/core/b2b/DefaultUnitService.java | D2/Patched | |
| C-shopcore-003 | assessment | FR-023 successor products could use the standard ProductReference instead of the own attribute. | repo/src/shopcore/schema.xml | D3/Coverage:FR-023 | |
| C-shopcore-004 | assessment | shopcore is heavy: it overrides cartService and shadows DefaultUnitService. | repo/src/shopcore/src/main/resources/shopcore-di.xml:2-3; repo/src/shopcore/src/main/java/com/vendor/core/b2b/DefaultUnitService.java:1-2 | D2/Depth | |
| C-shopcore-005 | assessment | The shadowed unit resolution is a high upgrade risk and security relevant: it decides which unit's equipment and prices a customer sees. | repo/src/shopcore/src/main/java/com/vendor/core/b2b/DefaultUnitService.java:1-2 | D2/Patched:{t("Ermittlung der Kundeneinheit", "unit resolution")} | |
| C-shopcore-006 | fact | shopcore implements FR-009 with the own type Equipment. | repo/src/shopcore/schema.xml | D3/Coverage:FR-009 | |
| C-shopcore-007 | assessment | The equipment list needs API work: an own API exists in shopapi, the content component has no target counterpart. | repo/src/shopapi/src/main/java/com/shop/api/EquipmentController.java | D4/Features:F-shopcore-1 | |
| C-shopcore-008 | assessment | The reseller plant price list needs API work: the standard price endpoint lacks the plant parameter. | repo/src/shopcore/src/main/resources/data/essential-usergroups.impex:2 | D4/Features:F-shopcore-2 | |
| C-shopcore-009 | fact | Cart recalculation depends on a server session attribute, a major migration concern. | repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java:5 | D4/Tasks:{t("Die Neuberechnung des Warenkorbs hängt an einem Attribut der Server-Session.", "LegacySession attribute for cart recalculation")} | |
| C-shopcore-010 | fact | The order process web module sits on the storefront aspect, a major migration concern. | repo/composer.json | D4/Tasks:{t("Das Webmodul des Auftragsprozesses ist dem Storefront-Aspekt zugeordnet.", "the order process web module is declared on the storefront aspect")} | |

## Open questions
| id | to_unit | question | why_needed | status | answer |
|---|---|---|---|---|---|
| Q-shopcore-1 | shopapi | Does shopapi expose Equipment via the API? | verdict for F-shopcore-1 | answered | yes, /equipment |
""")
    for critic, s3 in (("client", "| C-shopcore-003 | 6 | trivial | obvious | | quantify usage |"), ("standard", "| C-shopcore-003 | 9 | insightful | | | |")):
        w(f"analysis/gauntlet/shopcore/round1-{critic}.md", f"""\
# Gauntlet score: shopcore / {critic} / round 1
- **scope:** shopcore
- **critic:** {critic}
- **round:** 1

## Scores
| claim_id | score | verdict | issue | counter_evidence | fix_hint |
|---|---|---|---|---|---|
| C-shopcore-001 | 8 | confirmed | | | |
| C-shopcore-002 | 9 | insightful | | | |
{s3}
| C-shopcore-004 | 8 | confirmed | | | |
| C-shopcore-005 | 8 | confirmed | | | |
| C-shopcore-006 | 9 | confirmed | | | |
| C-shopcore-007 | 8 | confirmed | | | |
| C-shopcore-008 | 8 | confirmed | | | |
| C-shopcore-009 | 8 | confirmed | | | |
| C-shopcore-010 | 8 | confirmed | | | |

## Missing claims
- No statement on API support for successor products in the target version

## Estate observations
-

## Summary
ok
""")
    w("analysis/consolidated/D3.md", f"""\
# Consolidation D3: requirements coverage
- **status:** final
- **round:** 1
- **target_version:** Generic target 2.0 + composable storefront

## Coverage
| req_id | verdict | today | target_standard | target_standard_ref | target_standard_confidence | recommendation | business_effect | key_statement | description_gap | current_state_note | units | standard_alternative_flag | standard_alternative | standard_alternative_confidence | rationale | confidence | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FR-009 | covered-custom | custom | none | | | keep-custom | {t("Die Maschinenliste behält ihre eigene Logik und wird als Frontend-Ansicht auf der vorhandenen API neu gebaut.", "The equipment list keeps its own logic and is rebuilt as a frontend view on the existing API.")} | {t("Die Maschinenliste bleibt eigene Logik; im neuen Frontend entsteht nur die Ansicht neu.", "The equipment list stays own logic; only its view is rebuilt in the new frontend.")} | {t("Maschinen lassen sich als stillgelegt markieren; FR-009 beschreibt das nicht.", "Equipment can be marked decommissioned; FR-009 does not describe this.")} | {t("Maschinen je Einheit vorhanden", "equipment per unit exists")} | shopcore; shopstorefront; shopapi | no | | | {t("eigener Typ Equipment", "own type Equipment")} | high | repo/src/shopcore/schema.xml |
| FR-023 | partial | custom | full | {t("Produktreferenz SUCCESSOR im Standard, Ziel 2.0 (PS-7-001)", "ProductReference SUCCESSOR, target 2.0 (PS-7-001)")} | high | refactor-to-standard | {t("Nachfolgeprodukte kommen künftig aus der Standard-Produktreferenz statt aus einem eigenen Attribut.", "Successor products come from the standard product reference instead of a custom attribute.")} | {t("Nachfolger laufen künftig über den Standard; das eigene Attribut entfällt.", "Successors run on the standard in future; the own attribute is dropped.")} | {t("Das eigene Attribut kennt nur einen Nachfolger je Produkt.", "The own attribute knows only one successor per product.")} | {t("nur Nachfolger gepflegt", "successors only")} | shopcore | yes | ProductReference SUCCESSOR | high | {t("Attribut statt Referenz", "attribute instead of reference")} | medium | C-shopcore-003; PS-7-001 |
| FR-030 | gap | none | none | {t("kein Standard für Teillieferungen je Werk", "no standard for split delivery per plant")} | | build-new | {t("Die Teillieferung je Werk muss neu gebaut werden.", "Split delivery has to be built.")} | {t("Teillieferungen je Werk gibt es weder heute noch im Standard; sie müssen neu gebaut werden.", "Split delivery per plant exists neither today nor in the standard; it has to be built.")} |  | {t("nicht umgesetzt", "not implemented")} | | no | | | {t("kein Code, kein Standard", "no code, no standard")} | high | |
| TR-01 | covered-custom | custom | partial | {t("Integrationsmodul im Standard, Ziel 2.0", "integration module, target 2.0")} | medium | keep-custom | {t("Die Auftragsübertragung bleibt, wie sie ist.", "The order transfer stays as it is.")} | {t("Die Auftragsübertragung an das ERP zieht unverändert mit um.", "The order transfer to the ERP moves along unchanged.")} | {t("Die Übertragung wiederholt fehlgeschlagene Aufträge automatisch.", "The transfer retries failed orders automatically.")} | {t("ausgehend über die Middleware", "outbound via middleware")} | shopintegration | no | | | {t("eigene Anbindung über die Middleware", "own connection via middleware")} | high | repo/src/shopintegration/src/main/java/com/shop/integration/ErpOrderOutbound.java |

## New requirements
| id | epic | title | description | acceptance_criteria | exclusions | references | phase | units | rationale | proposed_handling | confidence | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NR-001 | Roles | {t("Händlerpreisliste je Werk", "Reseller price list per plant")} | {t("Händler sehen je Werk eine eigene Preisliste.", "Resellers see a separate price list per plant.")} | {t("1) Händler sieht die Preisliste seines Werks", "1) reseller sees plant price list")} | {t("keine Preispflege im Shop", "no price maintenance in the shop")} | FR-009 | Offen | shopcore | {t("keine Anforderung nennt Händlerpreise", "no requirement mentions reseller pricing")} | keep-in-scope | medium | C-shopcore-001 |

## Claims
| id | type | statement | evidence | target | supersedes |
|---|---|---|---|---|---|
| C-D3-001 | assessment | FR-009 is covered by own code in three modules. | analysis/units/shopcore.md | D3/Coverage:FR-009 | |
| C-D3-002 | assessment | FR-023 is partial today and fully met by the standard product reference, so it is refactored to the standard. | repo/src/shopcore/schema.xml; PS-7-001 | D3/Coverage:FR-023 | |
| C-D3-003 | assessment | FR-030 is a gap: no code and no standard for split delivery per plant, so it is built new. | repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java | D3/Coverage:FR-030 | |
| C-D3-004 | assessment | TR-01 is covered by the own ERP connection and kept as custom code. | repo/src/shopintegration/src/main/java/com/shop/integration/ErpOrderOutbound.java | D3/Coverage:TR-01 | |
""")
    w("analysis/consolidated/D4.md", f"""\
# Consolidation D4: target readiness and migration tasks
- **status:** final
- **round:** 1

## Features
| feature_id | feature | primary_requirement | units | current_implementation | entry_points | target_api_coverage | target_api_endpoints | custom_api_exists | custom_api_needed | content_dependency | content_components | state_dependency | verdict | rationale | key_statement | related_requirements | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F-001 | {t("Maschinenliste", "Equipment list")} | FR-009 | shopstorefront; shopapi | {t("Template-Seite", "template page")} | EquipmentPageController | none | | yes | | custom-components | ShopEquipmentListComponent | none | needs-api-work | {t("Eigene API vorhanden, die Content-Komponente braucht ein Mapping.", "own API exists, content component needs mapping")} | {t("Die vorhandene API trägt die Liste; nur die Content-Komponente braucht ein eigenes Mapping.", "The existing API carries the list; only the content component needs its own mapping.")} | | repo/src/shopapi/src/main/java/com/shop/api/EquipmentController.java |
| F-002 | {t("Händlerpreisliste je Werk", "Reseller plant price list")} | NR-001 | shopcore | {t("Preisermittlung liest die Händlergruppe", "price factory reads the reseller group")} | PriceController | partial | /store-api/product | no | {t("Werk-Parameter am Preis-Endpunkt", "plant parameter on the price endpoint")} | none | | none | needs-api-work | {t("Dem Standard-Preisendpunkt fehlt die Dimension Werk.", "standard price endpoint lacks the plant dimension")} | {t("Der Standard-Preisendpunkt braucht einen zusätzlichen Werk-Parameter.", "The standard price endpoint needs an additional plant parameter.")} | FR-009 | repo/src/shopcore/src/main/resources/data/essential-usergroups.impex:2 |

## Content components
| component_type | kind | target_support | usages | units | notes | evidence |
|---|---|---|---|---|---|---|
| ShopEquipmentListComponent | custom | needs-custom-mapping | 1 | shopstorefront | {t("eigene Komponente ohne Gegenstück im Ziel", "own component without a target counterpart")} | repo/src/shopstorefront/src/main/resources/data/cms-content.impex:1 |
| ParagraphComponent | standard | supported | | shopstorefront | {t("vom Ziel-Frontend unterstützt", "supported by the target frontend")} | PS-7-001 |

## Integrations
| system | direction | mechanism | data_objects | trigger | implementation | units | purpose | target_impact | operator | target_note | related_requirements | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ERP | outbound | middleware | order | async | custom | shopcore; shopintegration | {t("Auftragsübertragung", "order transfer")} | unchanged | {t("Middleware-Team des Kunden, Überwachung durch die Kunden-IT", "the client's middleware team, monitored by the client's IT")} | {t("nur Backend", "backend only")} | TR-01 | repo/src/shopcore/process/order-process.xml |

## Migration tasks
| id | topic | task | finding | affected_requirements | units | impact | rank | sequence | depends_on | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| MT-001 | content | {t("Die eigene Maschinenlisten-Komponente einer Komponente des Ziel-Frontends zuordnen", "Map the custom equipment-list component to a target frontend component")} | {t("ShopEquipmentListComponent hat kein Gegenstück im Ziel", "ShopEquipmentListComponent has no target counterpart")} | FR-009; NR-001 | shopstorefront | blocker | 1 | during | | repo/src/shopstorefront/src/main/resources/data/cms-content.impex:1 |
| MT-002 | session | {t("Das Kennzeichen zur Warenkorb-Neuberechnung aus der Server-Session in ein Warenkorbattribut verlegen", "Move the cart recalculation flag from the server session to a cart attribute")} | {t("Die Neuberechnung hängt an einem Attribut der Server-Session", "LegacySession attribute for cart recalculation")} | FR-009; FR-030 | shopcore | major | | before | | repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java:5 |
| MT-003 | deployment-config | {t("Das Webmodul des Auftragsprozesses dem API-Aspekt zuordnen", "Declare the order process web module on the api aspect")} | {t("Das Webmodul ist dem Storefront-Aspekt zugeordnet, den der Umzug entfernt", "the web module is declared on the storefront aspect that the move retires")} | TR-01; FR-030 | shopcore | major | | before | MT-002 | repo/composer.json |

## Claims
| id | type | statement | evidence | target | supersedes |
|---|---|---|---|---|---|
| C-D4-001 | assessment | One custom content component type blocks a pure standard target storefront. | analysis/units/shopcore.md; C-shopcore-001 | D4/Tasks:MT-001 | |
| C-D4-002 | fact | Feature F-002 serves the proposed requirement NR-001 and no requirement of the client's list. | analysis/consolidated/D3.md | D4/Features:F-002 | |
| C-D4-003 | assessment | Feature F-001 needs API work: the own API exists, the content component needs a mapping. | repo/src/shopapi/src/main/java/com/shop/api/EquipmentController.java | D4/Features:F-001 | |
| C-D4-004 | assessment | Task MT-002 has major impact: the cart recalculation flag lives in the server session. | repo/src/shopcore/src/main/java/com/shop/core/order/ShopCartService.java:5 | D4/Tasks:MT-002 | |
| C-D4-005 | assessment | Task MT-003 has major impact: the order process web module sits on the retired storefront aspect. | repo/composer.json | D4/Tasks:MT-003 | |
""")
    w("analysis/gate/round1-cto.md", """\
# Final gate: cto / round 1
- **persona:** cto
- **round:** 1

## Key questions

| question_id | score | where | answer | rationale |
|---|---|---|---|---|
| C1 | 8 | Management_Summary!A5 | answered on the summary with its figure | the basis is visible in each row |
| C2 | 7 | Management_Summary!A6 | answered on the summary with its figure | only by combining two sheets |
| C3 | 8 | Management_Summary!A7 | answered on the summary with its figure | the basis is visible in each row |
| C4 | 9 | Management_Summary!A8 | answered on the summary with its figure | the basis is visible in each row |
| C5 | 8 | Management_Summary!A9 | answered on the summary with its figure | the basis is visible in each row |

## Board test

- **forward_unchanged:** no
- **blocking_items:** I1

## What is missing

- a view by release

## Issues

| id | deliverable | location | issue | kind | severity | question_id | proposed_change |
|---|---|---|---|---|---|---|---|
| I1 | D2 | Heatmap!Q1 | deviation score without explained scale | presentation | major | C2 | add the scale to the README |

## Summary
ok
""")
    summaries = {"D1": t("## Einordnung\n\nDas Repository enthält {kpi:units} eigene Module mit {kpi:loc_clean} bereinigten Codezeilen; der kundennahe Anteil liegt bei {kpi:loc_clean_cf}.\n\n- Genutzte Schnittstellen, die im Ziel entfallen, stehen auf dem Blatt Deprecations.",
                         "## Assessment\n\nThe repository holds {kpi:units} custom modules with {kpi:loc_clean} cleaned lines of code; the customer-facing share is {kpi:loc_clean_cf}.\n\n- Interfaces in use that the target removes are listed on the sheet Deprecations."),
                 "D2": t("## Einordnung\n\nDer Anteil der Module ohne Eingriff in Standardverhalten liegt bei {kpi:clean_core}; {kpi:patched_security} Eingriffe sind sicherheitsrelevant.\n\n- Die Befunde mit Handlungsbedarf stehen auf dem Blatt Sicherheit_und_Betrieb.",
                         "## Assessment\n\nThe share of modules without patches of standard behaviour is {kpi:clean_core}; {kpi:patched_security} patches are security relevant.\n\n- The findings requiring action are on the sheet Security_and_operations."),
                 "D3": t("## Einordnung\n\nVon {kpi:reqs} Anforderungen deckt der Standard {kpi:rec_std} direkt ab; {kpi:rec_refactor} lassen sich auf Standard umbauen und {kpi:rec_new} müssen neu gebaut werden.\n\n- Die Annahmen, von denen Ergebnisse abhängen, stehen auf dem Blatt Annahmen.",
                         "## Assessment\n\nOf {kpi:reqs} requirements the standard covers {kpi:rec_std} directly; {kpi:rec_refactor} can be refactored to the standard and {kpi:rec_new} have to be built.\n\n- The assumptions results rest on are on the sheet Assumptions."),
                 "D4": t("## Einordnung\n\n{kpi:tasks_blocker} Migrationsaufgaben sind Blocker; {kpi:ready} Features sind ohne Backend-Arbeit bereit.\n\n- Die Reihenfolge ergibt sich aus Auswirkung und Rang auf dem Blatt Migrationsaufgaben.",
                         "## Assessment\n\n{kpi:tasks_blocker} migration tasks are blockers; {kpi:ready} features are ready without backend work.\n\n- The order follows impact and rank on the sheet Migration_tasks.")}
    for d, txt in summaries.items(): w(f"analysis/summaries/{d}.md", txt + "\n")

elif MODE == "sap":
    fill_project({"source": {"version": "2205 on-premise", "frontend": "JSP B2B accelerator", "language_stack": "Java 11"}, "target": {"version": "2211 latest patch on CCv2", "frontend": "composable storefront (Spartacus) 2211.x"}, "unit": {"repo_roots": ["hybris/bin/custom"], "standard_dirs": ["hybris/bin/platform", "hybris/bin/modules"]}})
    def ext(name, requires, base="repo/hybris/bin/custom/shop", extra_meta="", web=False):
        req = "".join(f'    <requires-extension name="{r}"/>\n' for r in requires)
        xml = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n<extensioninfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
               f'  <extension abstractclassprefix="Generated" classprefix="{name.capitalize()}" name="{name}" description="Fixture {name}">\n{req}    {extra_meta}\n'
               f'    <coremodule generated="true" manager="de.hybris.platform.jalo.extension.Extension" packageroot="com.shop.{name}"/>\n'
               + (f'    <webmodule jspcompile="false" webroot="/{name}"/>\n' if web else "") + '  </extension>\n</extensioninfo>\n')
        w(f"{base}/{name}/extensioninfo.xml", xml)
    ext("shopcore", ["b2bcommerce", "commerceservices", "sapmodel"]); ext("shopfacades", ["shopcore", "commercefacades", "b2bcommercefacades"])
    ext("shopstorefront", ["shopfacades", "yacceleratorstorefront", "b2bacceleratoraddon"], web=True); ext("shopintegration", ["shopcore", "sapcpiadapter", "outboundservices"])
    ext("shopocc", ["shopfacades", "commercewebservices"], web=True); ext("shopbackoffice", ["shopcore", "backoffice"], extra_meta='<meta key="backoffice-module" value="true"/>')
    for std in ("b2bcommerce", "commerceservices", "sapmodel", "commercefacades", "b2bcommercefacades", "yacceleratorstorefront", "b2bacceleratoraddon", "sapcpiadapter", "outboundservices", "commercewebservices", "backoffice", "platformservices"):
        ext(std, [], base="repo/hybris/bin/modules/fixture")
    w("repo/hybris/bin/platform/build.number", "version=2205.14\nreleasedate=2023-05-01\n"); w("repo/hybris/bin/platform/extensioninfo.xml", '<extensioninfo><extension name="platform"/></extensioninfo>')
    w("repo/hybris/bin/custom/shop/shopcore/resources/shopcore-items.xml", """\
    <items xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <itemtypes>
        <itemtype code="Product" autocreate="false" generate="false"><attributes><attribute qualifier="materialGroup" type="java.lang.String"><persistence type="property"/></attribute><attribute qualifier="successorProduct" type="Product"><persistence type="property"/></attribute></attributes></itemtype>
        <itemtype code="ShopEquipment" extends="GenericItem" autocreate="true" generate="true"><deployment table="ShopEquipment" typecode="20001"/><attributes><attribute qualifier="serialNumber" type="java.lang.String"><persistence type="property"/></attribute></attributes></itemtype>
      </itemtypes>
      <relations><relation code="B2BUnit2ShopEquipment" localized="false"><sourceElement type="B2BUnit" qualifier="unit" cardinality="one"/><targetElement type="ShopEquipment" qualifier="equipments" cardinality="many"/></relation></relations>
      <enumtypes><enumtype code="ShopOrderChannel" autocreate="true" generate="true"><value code="SHOP"/></enumtype></enumtypes>
    </items>
    """)
    w("repo/hybris/bin/custom/shop/shopcore/resources/shopcore-spring.xml", '<beans xmlns="http://www.springframework.org/schema/beans">\n  <alias name="shopCommerceCartService" alias="commerceCartService"/>\n  <bean id="shopCommerceCartService" class="com.shop.shopcore.order.impl.ShopCommerceCartService" parent="defaultCommerceCartService"/>\n  <bean id="defaultB2BUnitService" class="com.shop.shopcore.b2b.ShopB2BUnitService"/>\n</beans>\n')
    w("repo/hybris/bin/custom/shop/shopcore/resources/shopcore/process/order-process.xml", '<process xmlns="http://www.hybris.de/xsd/processdefinition" start="checkOrder" name="order-process" processClass="de.hybris.platform.orderprocessing.model.OrderProcessModel"><end id="success" state="SUCCEEDED">ok</end></process>\n')
    w("repo/hybris/bin/custom/shop/shopcore/src/com/shop/shopcore/order/impl/ShopCommerceCartService.java", "package com.shop.shopcore.order.impl;\nimport de.hybris.platform.commerceservices.order.impl.DefaultCommerceCartService;\nimport de.hybris.platform.jalo.JaloSession;\npublic class ShopCommerceCartService extends DefaultCommerceCartService {\n    public void recalc() { JaloSession.getCurrentSession().setAttribute(\"x\", 1); }\n}\n")
    w("repo/hybris/bin/custom/shop/shopcore/src/de/hybris/platform/b2b/services/impl/DefaultB2BUnitService.java", "package de.hybris.platform.b2b.services.impl;\npublic class DefaultB2BUnitService { int patched; }\n")
    w("repo/hybris/bin/custom/shop/shopcore/testsrc/com/shop/shopcore/FooTest.java", "package com.shop.shopcore;\npublic class FooTest { }\n")
    # a source package named like a skip dir must be counted; a JSP include importing the Jalo layer is a hit
    w("repo/hybris/bin/custom/shop/shopcore/src/com/shop/shopcore/cache/impl/ShopCacheLoader.java", "package com.shop.shopcore.cache.impl;\npublic class ShopCacheLoader {\n    int loaded;\n}\n")
    w("repo/hybris/bin/custom/shop/shopstorefront/web/webroot/WEB-INF/views/head.inc", "<%@ page import=\"de.hybris.platform.jalo.*\" %>\n<div>head</div>\n")
    w("repo/hybris/bin/custom/shop/shopcore/resources/impex/essentialdata-usergroups.impex", "INSERT_UPDATE UserGroup;uid[unique=true]\n;reseller\n")
    w("repo/hybris/bin/custom/shop/shopstorefront/web/src/com/shop/storefront/controllers/pages/EquipmentPageController.java", "package com.shop.storefront.controllers.pages;\nimport de.hybris.platform.acceleratorstorefrontcommons.controllers.pages.AbstractPageController;\nimport org.springframework.stereotype.Controller;\n@Controller\npublic class EquipmentPageController extends AbstractPageController { }\n")
    w("repo/hybris/bin/custom/shop/shopstorefront/web/webroot/WEB-INF/views/responsive/pages/account/equipment.jsp", "<div>equipment</div>\n")
    w("repo/hybris/bin/custom/shop/shopstorefront/resources/impex/projectdata-cms.impex", "INSERT_UPDATE ShopEquipmentListComponent;uid[unique=true]\n;equipmentList\nINSERT_UPDATE CMSParagraphComponent;uid[unique=true]\n;p1\n")
    w("repo/hybris/bin/custom/shop/shopocc/web/src/com/shop/occ/controllers/EquipmentController.java", "package com.shop.occ.controllers;\nimport org.springframework.web.bind.annotation.RestController;\n@RestController\npublic class EquipmentController { }\n")
    w("repo/hybris/bin/custom/shop/shopintegration/src/com/shop/integration/SapOrderOutbound.java", "package com.shop.integration;\nimport org.springframework.web.client.RestTemplate;\npublic class SapOrderOutbound { RestTemplate t; }\n")
    w("repo/hybris/bin/custom/shop/shopbackoffice/resources/shopbackoffice-backoffice-config.xml", '<config xmlns="http://www.hybris.com/cockpit/config"/>\n')
    w("repo/hybris/config/localextensions.xml", '<hybrisconfig><extensions><extension name="shopcore"/><extension name="shopfacades"/><extension name="shopstorefront"/><extension name="shopintegration"/><extension name="shopocc"/><extension name="shopbackoffice"/><extension name="b2bacceleratoraddon"/></extensions></hybrisconfig>\n')
    requirements_workbook()
    # inventory analysis + D1 summary: the smoke builds the customer edition of D1 and runs the hygiene layer on it (German run)
    w("analysis/inventory/inventory_analysis.md", """\
# Inventory analysis (D1)
- **status:** final
- **round:** 1

## Repo notes
Hybris-Fixture mit sechs eigenen Extensions unter hybris/bin/custom/shop.

## Platform
- **version:** 2205.14
- **version_confidence:** high
- **runtime:** Java 11
- **hosting:** eigenes Rechenzentrum
- **frontend_technology:** JSP-Accelerator-Storefront
- **database:** MySQL 8
- **search:** Solr
- **evidence:** repo/hybris/bin/platform/build.number
- **notes:** Die Version steht in der Datei build.number der Plattform.

## Units
| name | category | sub_categories | description | template_origin | activation | notes |
|---|---|---|---|---|---|---|
| shopcore | core | data | Kernservices, eigenes Datenmodell für installierte Maschinen und die Warenkorbberechnung | yb2bacceleratorcore | active | überlagert eine Standardklasse |
| shopfacades | facade | | Fassaden zwischen Storefront, API und Kernservices | yb2bacceleratorfacades | active | |
| shopstorefront | frontend | | Serverseitige JSP-Storefront mit Maschinenliste | yb2bacceleratorstorefront | active | |
| shopintegration | integration | | Auftragsübertragung an SAP über die Integrationsplattform | | active | |
| shopocc | api | | Eigene OCC-Endpunkte für die Maschinenliste | ycommercewebservices | active | |
| shopbackoffice | admin | | Backoffice-Konfiguration für die eigenen Typen | ybackoffice | active | |

## Third-party packages
| name | kind | installed_on | source | notes |
|---|---|---|---|---|
| b2bacceleratoraddon | standard | shopstorefront | repo/hybris/config/localextensions.xml | Accelerator-AddOn des Herstellers |

## Deprecations
| id | what | units | status | since | replacement | verified_against | evidence |
|---|---|---|---|---|---|---|---|
| DEP-JALO | Nutzung der Jalo-Schicht | shopcore; shopstorefront | risky | 1811 | Service-Schicht | Herstellerdokumentation zur Jalo-Schicht | repo/hybris/bin/custom/shop/shopcore/src/com/shop/shopcore/order/impl/ShopCommerceCartService.java:3 |
| DEP-SESSION-CART-JSP | Warenkorb in der Server-Session | shopcore | risky | 2211 | Warenkorb über die OCC-API | Herstellerdokumentation zur Composable Storefront | repo/hybris/bin/custom/shop/shopcore/src/com/shop/shopcore/order/impl/ShopCommerceCartService.java:5 |
| DEP-ACCELERATOR-STOREFRONT | Accelerator-Storefront als Grundlage | shopstorefront | deprecated | 2211 | Composable Storefront | Herstellerdokumentation zur Accelerator-Ablösung | repo/hybris/bin/custom/shop/shopstorefront/extensioninfo.xml:3 |
| DEP-ADDONSUPPORT | AddOn-Mechanismus der Accelerator-Storefront | shopstorefront | deprecated | 2211 | Composable Storefront | Herstellerdokumentation zur Accelerator-Ablösung | repo/hybris/bin/custom/shop/shopstorefront/extensioninfo.xml:4 |

## Dependency notes
| from | to | kind | note | evidence |
|---|---|---|---|---|
| shopintegration | shopcore | runtime-di | nutzt den Auftragsservice von shopcore | repo/hybris/bin/custom/shop/shopcore/resources/shopcore-spring.xml:2 |
| shopbackoffice | shopcore | config | konfiguriert die eigenen Typen von shopcore | repo/hybris/bin/custom/shop/shopbackoffice/resources/shopbackoffice-backoffice-config.xml:1 |

## Claims
| id | type | statement | evidence | target | supersedes |
|---|---|---|---|---|---|
| C-D1-001 | fact | The platform version is 2205.14. | repo/hybris/bin/platform/build.number:1 | D1/Platform | |
| C-D1-002 | fact | All six custom extensions are listed in localextensions.xml. | repo/hybris/config/localextensions.xml | D1/Units:shopcore,shopfacades,shopstorefront,shopintegration,shopocc,shopbackoffice | |
""")
    w("analysis/summaries/D1.md", "## Einordnung\n\nDas Repository enthält {kpi:units} eigene Extensions mit {kpi:loc_clean} bereinigten Codezeilen; der kundennahe Anteil liegt bei {kpi:loc_clean_cf}.\n\n- Genutzte Schnittstellen, die im Ziel entfallen, stehen auf dem Blatt Deprecations.\n")
print("fixture", MODE, "written to", T)
