#!/usr/bin/env bash
# tech-scoring method self-test: one throw-away single-run project in $TMP.
#   full chain: init, fixture, requirements, discover (technologies -> scopes), waves, Markdown conversion of every kind,
#   gauntlet of one technology and of the consolidation, gate aggregation, every role brief, digest, workbook, lint, handover.
# Env from engine/smoke_test.sh: TOOLS, PLUGIN, TMP, LANG_
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; run() { python3 "$TOOLS/$1.py" "${@:2}"; }; mrun() { python3 "$HERE/tools/$1.py" "${@:2}"; }
export PATH="$PLUGIN/scripts:$PATH"
# the vendor sources the fixture cites (PS-7-001..004), each with a title in the deliverable language (sheet Sources/Quellen)
refs() {
  run reference add --fact "Fixture Commerce 3.2 Business: B2B price lists per hierarchy node, ERP connector, page composition" --applies "3.2 Business" --url "https://docs.example.invalid/fixture-commerce/3.2" --provenance researcher | grep -q "added PS-7-001"
  run reference add --fact "Fixture Commerce plans and pricing: punch-out only in Enterprise, subscription tiered by order volume" --applies "3.2" --url "https://docs.example.invalid/fixture-commerce/3.2/plans" --provenance researcher >/dev/null
  run reference add --fact "Fixture Composable current SaaS plan: API primitives, no standard authoring surface" --applies "SaaS Growth" --url "https://docs.example.invalid/fixture-composable" --provenance researcher >/dev/null
  run reference add --fact "Fixture Suite 2.4.7 Cloud: B2B module, connector marketplace, licence plus infrastructure tier" --applies "2.4.7 Cloud" --url "https://docs.example.invalid/fixture-suite/2.4.7" --provenance researcher >/dev/null
  if [ "$1" = de ]; then
    run reference title PS-7-001 --title "Fixture Commerce 3.2 Business: B2B-Preislisten, ERP-Konnektor, Seitengestaltung" --summary "Preislisten je Hierarchieknoten, Konnektor ohne Preiskonditionen, Seitengestaltung durch Fachanwender." --lang de >/dev/null
    run reference title PS-7-002 --title "Fixture Commerce: Pläne und Preise" --summary "Punch-out nur im Enterprise-Plan; Abonnement nach Bestellvolumen gestaffelt." --lang de >/dev/null
    run reference title PS-7-003 --title "Fixture Composable: aktueller SaaS-Plan" --summary "Fähigkeiten als API-Bausteine; keine Standard-Oberfläche zur Seitengestaltung." --lang de >/dev/null
    run reference title PS-7-004 --title "Fixture Suite 2.4.7 Cloud: Module, Marktplatz, Lizenz" --summary "B2B-Modul, ERP-Konnektor als Partner-Erweiterung, Lizenz plus Infrastrukturstufe." --lang de >/dev/null
  else
    run reference title PS-7-001 --title "Fixture Commerce 3.2 Business: B2B price lists, ERP connector, page composition" --summary "Price lists per hierarchy node, connector without price conditions, page composition by business users." --lang en >/dev/null
    run reference title PS-7-002 --title "Fixture Commerce: plans and pricing" --summary "Punch-out in the Enterprise plan only; subscription tiered by order volume." --lang en >/dev/null
    run reference title PS-7-003 --title "Fixture Composable: current SaaS plan" --summary "Capabilities as API primitives; no standard authoring surface for page composition." --lang en >/dev/null
    run reference title PS-7-004 --title "Fixture Suite 2.4.7 Cloud: modules, marketplace, licence" --summary "B2B module, ERP connector as a partner extension, licence plus infrastructure tier." --lang en >/dev/null
  fi
}

echo "=== tech-scoring"
G="$TMP/tech-scoring"; mkdir -p "$G"; cd "$G"
run init run --method tech-scoring --dir "$G" --lang "$LANG_" --client "Fixture Retail GmbH" --consultancy "Fixture Consulting" --title "Technology scoring fixture" >/dev/null
test -f requirements_mapping.json    # the method consumes a requirements-set
python3 "$HERE/fixtures/make_fixture.py" "$G"
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
for k in technology-scoring consolidated-SHORTLIST critic-scores gate-scores; do test -f "templates/$k.md" || { echo "template $k missing"; exit 1; }; done
run check_fill --quiet
run requirements_to_json
run intake --no-questions >/dev/null; test -f docs/INTAKE.md
run status init
refs "$LANG_"
run knowledge sources
run evidence bases | grep -q client-context
run evidence bases | grep -q vendor-docs

# ---- scopes come from run.json technologies (no inventory phase in this method)
mrun discover | grep -q "3 scopes"
python3 - <<'PY'
import json
sj = json.load(open("state/scopes.json")); sc = sj["scopes"]
assert set(sc) == {"T-01", "T-02", "T-03"}, set(sc)
assert all(len(s) <= 5 for s in sc), "scope ids must stay <= 5 chars (the hook blocks longer scope names in web queries)"
assert all(v["light"] is False and not v["skip"] for v in sc.values()), sc
assert sc["T-01"]["size"] == 10 and sc["T-01"]["meta"]["TECHNOLOGY"] == "Fixture Commerce", sc["T-01"]
assert sc["T-01"]["meta"]["PACK"] == "_generic" and sc["T-01"]["meta"]["KNOWLEDGE PACK FOLDER"], sc["T-01"]["meta"]
print("discover assertions ok |", len(sj["criteria"]), "criteria")
PY
run plan_waves | grep -q "wave 1"
for u in T-01 T-02 T-03; do run status scope $u '{"wave": 1, "status": "open"}' >/dev/null; done

# ---- Markdown -> JSON for every kind of this method
for k in "scoring analysis/scopes/T-01.md" "scoring analysis/scopes/T-02.md" "scoring analysis/scopes/T-03.md" \
         "critic analysis/gauntlet/T-01/round1-client.md" "critic analysis/gauntlet/T-01/round1-standard.md" \
         "critic analysis/gauntlet/SHORTLIST/round1-client.md" "critic analysis/gauntlet/SHORTLIST/round1-standard.md" \
         "shortlist analysis/consolidated/SHORTLIST.md" "gate analysis/gate/round1-cto.md"; do run md_to_json $k; done
python3 - <<'PY'
import json
d = json.load(open("analysis/scopes/T-01.json"))
crit = [c["id"] for c in json.load(open("run.json"))["criteria"]]
assert [r["criterion_id"] for r in d["criteria_scores"]] == crit, "one score row per criterion, in order"
assert all(r["client_evidence"] and r["vendor_evidence"] for r in d["criteria_scores"]), "both locators on every score row"
assert all(r["guardrail_hit"] for r in d["criteria_scores"]), "guardrail_hit filled on every row"
assert all(c["locator"] for c in d["capabilities"]), "every capability names a source"
s = json.load(open("analysis/consolidated/SHORTLIST.json"))
assert [r["rank"] for r in s["ranking"]] == [1, 2, 3] and [r["shortlisted"] for r in s["ranking"]] == [True, True, False], s["ranking"]
assert len(s["guardrails"]) == 6 and len(s["calibration"]) == 2, (len(s["guardrails"]), len(s["calibration"]))
print("kind assertions ok")
PY

# ---- gauntlet: one technology and the consolidation
run extract_claims T-01
run evidence check T-01 | grep -q "evidence cells dangling"
run score_aggregate T-01 1 --dry-run | grep -q '"passed": true'
run score_aggregate T-01 1 >/dev/null
if run md_to_json critic analysis/gauntlet/T-01/round1-client.md >/dev/null 2>&1; then echo "closed-file guard FAILED"; exit 1; else echo "closed-file guard ok"; fi
run extract_claims SHORTLIST
run score_aggregate SHORTLIST 1 | grep -q '"passed": true'
run status verify --brief | grep -q "STATUS agrees with disk"
run gate_aggregate 1 >/dev/null

# ---- briefs for every role + the consolidation digest
run render digest SHORTLIST >/dev/null; test -f analysis/consolidated/digest-SHORTLIST.md
grep -q "Score matrix" analysis/consolidated/digest-SHORTLIST.md
grep -q "Completeness" analysis/consolidated/digest-SHORTLIST.md
grep -q "^## Scores (all scopes)" analysis/consolidated/digest-SHORTLIST.md
grep -q "criteria_scores: 10 rows, 0 without a citing claim" analysis/gauntlet/T-01/coverage-round1.md
run render context analyst T-01 | grep -q "TECHNOLOGY: Fixture Commerce"
run render brief analyst T-01 --out >/dev/null; B=analysis/briefs/analyst-T-01.md
for s in "EVIDENCE BASES YOU MAY READ" "ROLE INSTRUCTIONS" "## CRITERIA" "CLIENT GUARDRAILS" "TECHNOLOGY KNOWLEDGE" "SCORE ANCHORS" "HEAD FIELDS OF YOUR OUTPUT"; do grep -q "$s" $B || { echo "missing '$s' in $B"; exit 1; }; done
grep -q "_generic/research-seed.md" $B
grep -qE "^MODEL: (opus|sonnet|haiku|fable)$" $B
run render brief consolidate SHORTLIST --out | grep -q "consolidate-shortlist"
grep -q "Score matrix\|DIGEST" analysis/briefs/consolidate-shortlist.md
grep -q "TECHNOLOGIES IN THIS RUN" analysis/briefs/consolidate-shortlist.md
run render brief critic client T-01 1 --out >/dev/null; grep -q "^MODEL:" analysis/briefs/critic-client-T-01-r1.md
grep -q "CTO / enterprise architect" analysis/briefs/critic-client-T-01-r1.md
run render brief critic standard T-01 1 --out >/dev/null; grep -q "TECHNOLOGY KNOWLEDGE" analysis/briefs/critic-standard-T-01-r1.md
run render brief critic standard SHORTLIST 1 --out | grep -qE "MODEL (opus|sonnet|haiku|fable)\b"
run render brief postpass T-01 | grep -q "POST-PASS TEXT CORRECTION"
run render brief progress | grep -q "progress-reporter"
run render brief research | grep -q "RESEARCH TOPICS"
if run render brief analyst T-01 --round 2 --out >/dev/null 2>&1; then echo "addendum guard FAILED"; exit 1; else echo "addendum guard ok"; fi

# ---- client questions, reference row, learnings, progress
run questions add T-01 client "Do the two key accounts require punch-out procurement at go-live?" --id Q-T-01-9 --effect "decides the first rank and the licence plan" >/dev/null
run questions add SHORTLIST client "Is an authoring layer built by the implementation team acceptable for the autonomy guardrail?" --id Q-SHORTLIST-9 --effect "decides the guardrail table of the second-ranked technology" >/dev/null
run questions affects Q-T-01-9 "Fixture Commerce C-01,Fixture Commerce" >/dev/null; run questions affects Q-SHORTLIST-9 "Fixture Composable C-04,Fixture Composable" >/dev/null
if [ "$LANG_" = de ]; then
  run questions edit Q-T-01-9 --why "Die Strategie nennt die Punch-out-Beschaffung der zwei Großkunden nur für eine spätere Phase; die Anforderungsliste führt sie als Soll-Anforderung für Phase 2." --note "fixture" >/dev/null
  run questions assumption Q-T-01-9 --text "Die Bewertung geht davon aus, dass die zwei Großkunden die Punch-out-Beschaffung erst nach dem Go-live brauchen." --if-not "Fixture Commerce braucht zum Start den Enterprise-Plan: C-01 sinkt, die Lizenzkosten steigen, und der erste Rang ist neu zu prüfen." >/dev/null
  run questions edit Q-SHORTLIST-9 --why "Die Leitlinie verlangt Pflege ohne Entwickler; eine vom Implementierungsteam gebaute Oberfläche erfüllt das im Betrieb, aber nicht im Standard." --note "fixture" >/dev/null
  run questions assumption Q-SHORTLIST-9 --text "Die Bewertung geht davon aus, dass eine vom Implementierungsteam gebaute Pflegeoberfläche die Leitlinie zur Selbstständigkeit nicht erfüllt." --if-not "Fixture Composable verliert den Leitlinien-Treffer bei C-04, die Bewertung steigt, und der Abstand zum ersten Rang schrumpft." >/dev/null
else
  run questions edit Q-T-01-9 --why "The strategy names punch-out for the two key accounts for a later phase only; the requirement list carries it as a should requirement for phase 2." --note "fixture" >/dev/null
  run questions assumption Q-T-01-9 --text "The scoring assumes that the two key accounts need punch-out procurement only after go-live." --if-not "Fixture Commerce needs the Enterprise plan at go-live: C-01 drops, the licence cost rises and the first rank must be re-checked." >/dev/null
  run questions edit Q-SHORTLIST-9 --why "The guardrail asks for maintenance without a developer; an authoring layer built by the implementation team meets it in operation, not in the standard." --note "fixture" >/dev/null
  run questions assumption Q-SHORTLIST-9 --text "The scoring assumes that an authoring layer built by the implementation team does not meet the autonomy guardrail." --if-not "Fixture Composable loses its guardrail hit on C-04, its score rises and the gap to the first rank narrows." >/dev/null
fi
run questions list --client | grep -q client
run learn add --section B --title "fixture learning" --what "x" --evidence "y" --generalises "z" --proposal "p" --touches "engine" | grep -q "L-001"
run progress | grep -q "PROGRESS"

# ---- workbook
run build_excel --all
run lint_deliverable
run lint_deliverable --standalone --all --round 1
run kb add --text "Every scope of this fixture reads the same nightly export." --topic fixture-export --topic-summary "the shared nightly export" --applies-to '*' --type decision | grep -q "KB-001"
run render brief gate cto 1 --out | grep -q "gate-cto"
if grep -q "## KNOWLEDGE BASE" analysis/briefs/gate-cto-r1.md; then echo "knowledge base block in a gate brief"; exit 1; fi   # 0.10: gate roles get no KNOWLEDGE BASE block
run render brief analyst T-01 --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/analyst-T-01.md
run render brief critic client T-01 1 --out >/dev/null; grep -q "## KNOWLEDGE BASE" analysis/briefs/critic-client-T-01-r1.md
python3 - <<'PY'
import openpyxl, glob, re, json
f = "deliverables/intern/Technology_Scoring.xlsx"   # full edition: + Claims + Open_Questions
wb = openpyxl.load_workbook(f); names = set(wb.sheetnames)
OQ = "Offene_Fragen" if "Offene_Fragen" in names else "Open_Questions"   # engine sheet names follow the deliverable language
for s in ("Management_Summary", "README", "Parameters", "Scores", "Ranking", "Shortlist", "Capabilities", "Guardrails", "Risks", "Claims", OQ):
    assert s in names, f"sheet {s} missing: {sorted(names)}"
bad = []
for ws in wb:
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("="):
                for ref in re.findall(r"([A-Za-z_][\w]*)!\$", c.value):
                    if ref not in names: bad.append((ws.title, c.coordinate, ref))
assert not bad, bad[:5]
charts = sum(len(ws._charts) for ws in wb)
assert len(wb["Ranking"]._charts) >= 1, "no chart on Ranking"
heads = [c.value for c in wb["Claims"][1]]
assert not any(h and ("Round" in h or "Note" in h) for h in heads), heads
# the ranking is formula-driven: SUMPRODUCT on Ranking and on Shortlist, weights looked up from Parameters, RANK over the totals
rank_f = [c.value for r in wb["Ranking"].iter_rows() for c in r if isinstance(c.value, str) and c.value.startswith("=")]
assert any("SUMPRODUCT" in v for v in rank_f), "no SUMPRODUCT in Ranking"
assert any("Shortlist!$" in v for v in rank_f), "Ranking does not read the shortlist"
sl_f = [c.value for r in wb["Shortlist"].iter_rows() for c in r if isinstance(c.value, str) and c.value.startswith("=")]
assert any("SUMPRODUCT" in v for v in sl_f) and any("RANK(" in v for v in sl_f), "Shortlist not formula-driven"
sc_f = [c.value for r in wb["Scores"].iter_rows() for c in r if isinstance(c.value, str) and c.value.startswith("=")]
assert any("Parameters!$" in v and "MATCH" in v for v in sc_f), "Scores does not read the weights from Parameters"
# rows: 10 criteria + 3 settings on Parameters, 3 technologies x 10 criteria on Scores, no typed-in total anywhere
keys = [wb["Parameters"].cell(row=r, column=1).value for r in range(2, 20)]
keys = [k for k in keys if k]
assert len([k for k in keys if k.startswith("C-")]) == 10 and ({"Floor", "Size", "Max"} <= set(keys) or {"Schwelle", "Anzahl", "Maximum"} <= set(keys)), keys   # setting keys are labelled tokens
assert sum(1 for r in range(2, 100) if wb["Scores"].cell(row=r, column=1).value) == 30, "expected 3 technologies x 10 criteria"
assert sum(1 for r in range(2, 20) if wb[OQ].cell(row=r, column=1).value) == 2, "client questions missing"
heads = [c.value for c in wb["Shortlist"][1]] + [c.value for c in wb["Scores"][1]]
assert not any("(formula)" in str(h) or "(Formel)" in str(h) or h in ("Check", "Confidence", "Prüfung", "Sicherheit") for h in heads), heads   # checks and confidence live in the internal review workbook only
c = openpyxl.load_workbook("deliverables/Technology_Scoring.xlsx"); assert ({"Assumptions", "Sources"} <= set(c.sheetnames) or {"Annahmen", "Quellen"} <= set(c.sheetnames)) and "Claims" not in c.sheetnames, c.sheetnames
print(f, "sheets:", len(wb.sheetnames), "| charts:", charts, "| dangling refs:", len(bad))
PY
run build_excel D1 --internal >/dev/null; test -f work/internal/Technology_Scoring_Review_Notes.xlsx
test ! -d deliverables/internal
run handover export shortlist --force | grep -q released
run handover list | grep -q shortlist
run status next || true

echo "=== tech-scoring / German deliverable"
S="$TMP/tech-scoring-de"; mkdir -p "$S"; cd "$S"
run init run --method tech-scoring --dir "$S" --lang de --client "Fixture Retail GmbH" --consultancy "Fixture Consulting" --title "Technologiebewertung Fixture" >/dev/null
python3 "$HERE/fixtures/make_fixture.py" "$S" >/dev/null
run render instructions --force >/dev/null; run render plan --force >/dev/null; run md_to_json --generate >/dev/null
run check_fill --quiet
run requirements_to_json >/dev/null
run status init >/dev/null
refs de
mrun discover >/dev/null; run plan_waves >/dev/null
for k in "scoring analysis/scopes/T-01.md" "scoring analysis/scopes/T-02.md" "scoring analysis/scopes/T-03.md" "shortlist analysis/consolidated/SHORTLIST.md"; do run md_to_json $k >/dev/null; done
run build_excel D1
run lint_deliverable
run lint_deliverable --standalone --all
python3 - <<'DE'
import openpyxl
wb = openpyxl.load_workbook("deliverables/intern/Technology_Scoring.xlsx"); names = set(wb.sheetnames)
for s in ("Management_Summary", "README", "Parameters", "Scores", "Ranking", "Shortlist", "Capabilities", "Guardrails", "Risks", "Claims"):
    assert s in names, sorted(names)
heads = [c.value for c in wb["Scores"][1]]
assert "Bewertung 0-10" in heads and "Grundlage" in heads, heads
assert "Nachweis Herstellerdokumentation" in heads, heads
gr = [c.value for n in ("Ranking", "Shortlist") for r in wb[n].iter_rows() for c in r if isinstance(c.value, str) and c.value.startswith("=")]
assert any('"ja"' in v for v in gr) and any('"Schwelle"' in v for v in gr), "the German label tokens do not reach the formulas"
assert len(wb["Ranking"]._charts) >= 1, "no chart on Ranking"
print("German workbook ok |", len(wb.sheetnames), "sheets")
DE

echo "TECH-SCORING SMOKE OK"
