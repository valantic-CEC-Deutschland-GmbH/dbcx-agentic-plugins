#!/usr/bin/env python3
"""the generic smoke fixture - fictional content for a method without fixtures, generated from its method.json and kinds.json.
Called by engine/generic_smoke.sh (`dbcx smoke <method>` for a method without smoke.sh that declares scopes.discover "generic:<variant>").

Usage (engine tools dir on PYTHONPATH, as generic_smoke.sh runs it):
       python3 generic_fixture.py inputs <run_dir>     fill every run.json placeholder, write the unit source of the discover variant
                                                         (list: three names; workbook: input/fixture/units.xlsx; folders: input/fixture/units/;
                                                         inventory: nothing - the inventory stage names the units),
                                                         input/fixture/context.md and, when the method consumes a requirements-set, a requirements
                                                         workbook with its mapping
       python3 generic_fixture.py inventory <run_dir>  a method with an inventory phase, before discover: the inventory analysis (its unit
                                                         table names the three fixture units with group, dependency and size) and passing
                                                         critic score files; prints "<kind> <file>" per written document
       python3 generic_fixture.py analyses <run_dir>   after discover: one analysis per scope (+ every consolidation) filled from
                                                         the kinds (enums, types, two rows per table, one claim per table section), passing critic
                                                         score files for the first scope and every consolidation, a gate file, the summaries;
                                                         prints "<kind> <file>" per written document for md_to_json
       python3 generic_fixture.py check <run_dir>      every table sheet of every built full-edition workbook has rows
Text is fictional and neutral; claims cite input/fixture/context.md and PS-7-001 (generic_smoke.sh registers it).
"""
import json, os, sys

STAGE, RUN_DIR = sys.argv[1], os.path.abspath(sys.argv[2])
os.environ["DBCX_RUN"] = RUN_DIR
from common import project, method, spec, scope_critics, load_json, save_json, is_placeholder, resolve_root, SCOPES_PATH, P

CONTEXT = "input/fixture/context.md"
EVIDENCE = f"{CONTEXT}; PS-7-001"
NAMES = ["Fixture Alpha", "Fixture Beta", "Fixture Gamma"]


def w(rel, text):
    p = P(rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(text)


def fill(v, path=""):
    """every placeholder string of run.json -> a fictional value"""
    if isinstance(v, dict): return {k: fill(x, f"{path}.{k}" if path else k) for k, x in v.items()}
    if isinstance(v, list): return [fill(x, path) for x in v]
    return f"Fixture {path.split('.')[-1].replace('_', ' ')}" if is_placeholder(v) else v


# ------------------------------------------------------------------ stage inputs
def inputs():
    m = method(); cfg = project(); rf = load_json("run.json"); rf = fill(rf)
    v = str(m["scopes"].get("discover", ""))[len("generic:"):]; key = m["scopes"].get("state_key") or "units"
    src = cfg.get(key) if isinstance(cfg.get(key), dict) else {}
    src = {k: x for k, x in src.items() if not is_placeholder(x)}
    if v == "list": rf[key] = [NAMES[0], {"name": NAMES[1], "group": "second"}, NAMES[2]]
    elif v == "workbook":
        import openpyxl
        src = dict({"file": "input/fixture/units.xlsx", "sheet": "Units", "column": "Name"}, **src)
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = src["sheet"]; heads = [src["column"]] + ([src["group_column"]] if src.get("group_column") else []) + ["Note"]
        ws.append(heads)
        for i, n in enumerate(NAMES):
            for r in range(2): ws.append([n] + ([f"Area {i % 2 + 1}"] if src.get("group_column") else []) + [f"row {r + 1} of {n}"])
        f = resolve_root(src["file"]); os.makedirs(os.path.dirname(f), exist_ok=True); wb.save(f); rf[key] = src
    elif v == "folders":
        src = dict({"root": "input/fixture/units", "per": "folder"}, **src); root = resolve_root(src["root"])
        for i, n in enumerate(NAMES):
            d = os.path.join(root, n) if src["per"] == "folder" else os.path.join(root, f"area-{i % 2 + 1}")
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "notes.md" if src["per"] == "folder" else f"{n}.md"), "w", encoding="utf-8").write(f"# {n}\n\nFictional notes about {n}.\n")
        rf[key] = src
    elif v != "inventory": sys.exit(f"method {m['name']}: scopes.discover '{m['scopes'].get('discover')}' is no generic variant")
    save_json("run.json", rf)
    w(CONTEXT, "# Context of the example\n\nThe client of this example is fictional. Its sourcing, delivery and audit figures are invented for the example run.\n")
    if os.path.exists(P("requirements_mapping.json")): requirements()
    print("fixture inputs written to", RUN_DIR, f"(generic:{v})")


def requirements():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Requirements"
    cols = ["ID", "Epic", "Title", "Description", "Acceptance criteria", "Exclusions", "References", "Phase", "Priority", "Sources"]
    ws.append(cols)
    ws.append(["FR-001", "Example", "First example requirement", "A fictional requirement of the example.", "", "", "", "MVP", "must", "WS1"])
    ws.append(["FR-002", "Example", "Second example requirement", "Another fictional requirement of the example.", "", "", "", "MVP", "should", "WS1"])
    os.makedirs(P("input/requirements"), exist_ok=True); wb.save(P("input/requirements/requirements_fixture.xlsx"))
    mp = load_json("requirements_mapping.json")
    mp["sheets"] = [{"sheet": "Requirements", "group": "functional", "id_prefix": "FR-", "header_row": 1, "columns": {c.lower().replace(" ", "_"): c for c in cols}, "extra_columns": []}]
    mp["phase_values_in_scope"] = ["MVP"]
    save_json("requirements_mapping.json", mp)


# ------------------------------------------------------------------ stage analyses
def row(*cells): return "| " + " | ".join(str(c).replace("|", "/") for c in cells) + " |"
def head(*cells): return row(*cells) + "\n|" + "---|" * len(cells)


def value(name, f, i, label, agent="", rnd=0):
    t = f.get("t", "s"); enum = f.get("enum")
    if name == "agent" and agent: return agent
    if name == "status" and isinstance(enum, list) and "final" in enum: return "final"
    if name == "round": return rnd
    if isinstance(enum, list) and enum: return enum[-(1 + i % len(enum))]
    if t == "i": return i + 1
    if t == "f": return (i + 1) * 1.5   # a number with decimals
    if t == "b": return "yes"
    if t == "l": return EVIDENCE
    return f"{label}: {name.replace('_', ' ')} {i + 1}"


def document(kind, k, scope, label, agent, targets, rnd, units=None):
    """(markdown, claim ids) of one analysis of `kind` (head round = rnd: 1 for a document the smoke takes through a gauntlet), every
    required part filled, one claim per table section; units = (table key, fn(i) -> {field: value}): that table gets one row per fixture unit"""
    lines = [f"# {k['title']}", ""] + [f"- **{n}:** {label if f.get('t', 's') == 's' and not f.get('enum') and n != 'agent' else value(n, f, 0, label, agent, rnd)}" for n, f in k["head"].items()] + [""]
    prefix = str(k.get("id_prefix") or "C-<scope>-").replace("<scope>", scope); claims = []
    for s in k["sections"]:
        if s.get("optional") or s["key"] == "claims": continue
        lines += [f"## {s['heading']}", ""]
        if s["type"] == "table":
            fs = list(s["fields"]); lines.append(head(*fs)); ov = units[1] if units and units[0] == s["key"] else None
            lines += [row(*((ov(i) if ov else {}).get(n, value(n, s["fields"][n], i, label)) for n in fs)) for i in range(len(NAMES) if ov else 2)]
            claims.append((f"{prefix}{len(claims) + 1:03d}", "assessment", f"{label} is described in the section {s['heading']} from the context document of the example.",
                           EVIDENCE, targets.get(f"{kind}.{s['key']}") or targets.get("_first") or f"{kind}/{s['key']}", ""))
        elif s["type"] == "kv": lines += [f"- **{n}:** {value(n, f, 0, label)}" for n, f in s["fields"].items()]
        elif s["type"] == "list": lines += [f"- {label}: item {i + 1} of {s['heading'].lower()}" for i in range(2)]
        else: lines.append(f"{label} is a fictional unit of this example. The statements below rest on the context document of the example.")
        lines.append("")
    if not claims: claims.append((f"{prefix}001", "fact", f"{label} is named in the context document of the example.", EVIDENCE, targets.get("_first") or f"{kind}/summary", ""))
    lines += ["## Claims", "", head("id", "type", "statement", "evidence", "target", "supersedes")] + [row(*c) for c in claims] + [""]
    return "\n".join(lines) + "\n", [c[0] for c in claims]


def critic_md(scope, critic, ids):
    return "\n".join([f"# Gauntlet score: {scope} / {critic} / round 1", "", f"- **scope:** {scope}", f"- **critic:** {critic}", "- **round:** 1", "",
                      "## Scores", "", head("claim_id", "score", "verdict", "issue", "counter_evidence", "fix_hint")]
                     + [row(c, 9, "confirmed", "", "", "") for c in ids]
                     + ["", "## Missing claims", "", "- No statement on the second example criterion", "", "## Estate observations", "",
                        "", "## Summary", "", "Fixture review: every claim names its locators.", ""]) + "\n"


def gate_md(persona):
    return f"""# Final gate: {persona} / round 1
- **persona:** {persona}
- **round:** 1

## Key questions

| question_id | score | where | answer | rationale |
|---|---|---|---|---|
| K1 | 8 | Management_Summary!A5 | answered on the summary with its figure | the basis is visible in each row |
| K2 | 8 | Management_Summary!A6 | answered on the summary with its figure | the basis is visible in each row |

## Board test

- **forward_unchanged:** yes
- **blocking_items:**

## What is missing

- a view by area

## Issues

| id | deliverable | location | issue | kind | severity | question_id | proposed_change |
|---|---|---|---|---|---|---|---|
| I1 | D1 | README!A1 | the reading order is not stated | presentation | minor | K2 | state it in the first line |

## Summary
The workbook answers the key questions with formulas over the detail sheets.
"""


def targets_of(dspec):
    """dataset -> claim target D<n>/<Sheet> of the first table sheet that reads it; `_first` = the first table sheet of any deliverable"""
    out = {}
    for d, x in (dspec.get("deliverables") or {}).items():
        for sh in x.get("sheets", []):
            if sh.get("type") != "table" or not sh.get("dataset"): continue
            out.setdefault(str(sh["dataset"]).partition(":")[0], f"{d}/{sh['name']}"); out.setdefault("_first", f"{d}/{sh['name']}")
    return out


def critics(cfg, gauntlet, done):
    for x, ids in gauntlet:
        for c in scope_critics(x, cfg):
            rel = f"analysis/gauntlet/{x}/round1-{c}.md"; w(rel, critic_md(x, c, ids)); done.append(("critic", rel))


def inventory():
    """the inventory analysis whose unit table names the fixture units (field names: the generic:inventory unit source, else the
    method's inventory.scopes_table / scopes_key) and its passing critic files"""
    from common import deliverables_spec
    cfg = project(); m = method(); inv = m.get("inventory") or sys.exit(f"method {m['name']} has no inventory phase")
    src = cfg.get(m["scopes"].get("state_key") or "units"); src = src if isinstance(src, dict) else {}
    table = src.get("table") or inv.get("scopes_table"); key = src.get("name") or inv.get("scopes_key") or "name"
    def unit(i):
        r = {key: NAMES[i]}
        if src.get("group"): r[src["group"]] = f"Area {i % 2 + 1}"
        if src.get("depends_on"): r[src["depends_on"]] = NAMES[0] if i == 1 else ""
        if src.get("size"): r[src["size"]] = i + 2
        return r
    kind = inv.get("kind", "inventory"); done = []
    md, ids = document(kind, spec(cfg)[0][kind], inv["scope"], inv["scope"], inv.get("agent", "inventory"), targets_of(deliverables_spec()), 1, (table, unit) if table else None)
    out = os.path.relpath(P(inv["output"]), RUN_DIR).replace(os.sep, "/"); w(out, md); done.append((kind, out))
    critics(cfg, [(inv["scope"], ids)], done)
    for kind, rel in done: print(kind, rel)


def analyses():
    from common import deliverables_spec
    cfg = project(); m = method(); SPEC = spec(cfg)[0]; dspec = deliverables_spec(); tg = targets_of(dspec)
    sj = load_json(SCOPES_PATH, None) or sys.exit("no state/scopes.json - run the discover first")
    sc = m["scopes"]; done = []; gauntlet = []
    for sid, s in sj["scopes"].items():
        if s.get("skip"): continue
        md, ids = document(sc["kind"], SPEC[sc["kind"]], sid, (s.get("meta") or {}).get("NAME") or sid, f"{sc.get('agent_prefix', 'analyst-')}{sid}", tg, 0 if done else 1)
        rel = f"{sc.get('output_dir', 'analysis/scopes')}/{sid}.md"; w(rel, md); done.append((sc["kind"], rel))
        if not gauntlet: gauntlet.append((sid, ids))
    for x, kind, out, agent in [(x, c.get("kind", x), c["output"], f"consolidate-{x.lower()}") for x, c in m["consolidations"].items()]:
        md, ids = document(kind, SPEC[kind], x, x, agent, tg, 1); out = os.path.relpath(P(out), RUN_DIR).replace(os.sep, "/")
        w(out, md); done.append((kind, out)); gauntlet.append((x, ids))
    critics(cfg, gauntlet, done)
    persona = (cfg.get("scoring") or {}).get("gate_personas", ["cto"])[0]
    w(f"analysis/gate/round1-{persona}.md", gate_md(persona)); done.append(("gate", f"analysis/gate/round1-{persona}.md"))
    for d in dspec.get("deliverables") or {}:
        w(f"analysis/summaries/{d}.md", "# Result\n\nThe assessment of the example covers every unit named for it. The detail sheets carry the rows, the formulas the totals.\n")
    for kind, rel in done: print(kind, rel)


# ------------------------------------------------------------------ stage check
def check():
    import openpyxl
    from common import deliverables_spec
    cfg = project(); bad = []; n = 0
    for d, x in (deliverables_spec().get("deliverables") or {}).items():
        if not ((cfg.get("deliverables") or {}).get(d) or {}).get("enabled", True): continue
        f = P("deliverables", "intern", cfg["deliverables"][d]["file"])
        if not os.path.exists(f): bad.append(f"{d}: {f} not built"); continue
        wb = openpyxl.load_workbook(f)
        for sh in x.get("sheets", []):
            if sh.get("type") != "table" or sh["name"] not in wb.sheetnames: continue
            ws = wb[sh["name"]]; rows = sum(1 for r in ws.iter_rows(min_row=2, values_only=True) if any(v not in (None, "") for v in r))
            n += 1
            if not rows: bad.append(f"{d}/{sh['name']}: no rows (dataset {sh.get('dataset')})")
    if bad: sys.exit("GENERIC FIXTURE CHECK FAILED:\n  " + "\n  ".join(bad))
    print(f"generic fixture check ok: {n} table sheet(s) with rows")


{"inputs": inputs, "inventory": inventory, "analyses": analyses, "check": check}[STAGE]()
