"""Brief extras of the tech-fit-estimation method (called by `dbcx render`; one run, N options).

The rows an agent must judge are put INTO the brief, so no analyst and no reviewer parses the client's workbook or the handover
artefacts to find what belongs to its chunk (chunk membership comes from state/scopes.json -> meta.req_ids):
  analyst          the OPTIONS (one TARGET block per option), the size mapping and rules, its requirements, related requirements owned
                   by other chunks, and for brownfield options the BASELINE (handover rows naming each requirement) + the lookup rules
  critic-client    the same requirements and baseline, the lookup sample rule
  critic-standard  the options of its technology pack (a per-pack critic sees only its own options)
  consolidator     development per chunk and option, the migration tasks that name no requirement (fixed-PD candidates), the rules
  classify         (method brief kind) the classification candidates with their handover text and the client rows they name
  triage           (scope step, method brief kind with a gauntlet: TRIAGE / TRIAGE-n) the run's systems, the landscape, the chunk's rows
                   verbatim with the pre-fill and the reference rows they roll up to; the critics of a triage chunk get what they judge
  architect        (method brief kind with a gauntlet: ARCHITECT-n) the run's systems, the landscape, per gap of the batch the row
                   verbatim, the reporting analysts' reasons / suggestions / own share, the row's impact cells and earlier decisions (FINAL on the
                   second visit); the critics of a batch get what they judge
digest_extra adds the calibration candidates per option and the requirements an option has no row for (system mode, per system
option over the live estimates, and the planned work packages without a row; the consolidator gets the development per chunk and system option).
flags(cfg) -> {"system_mode"} in a run with `systems`: `dbcx render` keeps the `<!-- when system_mode -->` blocks of briefs/*.md and the
briefs.rows entries with that `when` - the role texts of a run without systems are unchanged byte for byte.
(system mode, a chunk of state/scopes.json with `system`): the analyst estimates ONE system option - its TARGET block, the WORK
PACKAGES (row, the `option` value to write, parent option, the impact text in this system and in the other systems), for a dependent
system the PARENT'S APPROACH per row and parent option (from the parent's passed analyses), the CONTEXT ROWS (the reference rows it names,
the rows linked by roll-up with their impact texts per system) with the remainder rule; the critics see the same packages and context.
the WORK PACKAGES block also names the architect's decision on a package (its note, FINAL) and a parent package that
was re-briefed or withdrawn after the package was planned (cascade of `dbcx discover --pickup`).
Scenario mode: the BASELINE (today's shop - the real scope of every requirement) goes to EVERY option; row classes (TM / RF rows), the integration
platform effort (run.json estimation.integration_platform), the scenarios and the fixed-phase seeds (run.json scenarios,
estimation.fixed_phases_seed) reach the analyst and the consolidator where the run declares them.
"""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN, SCOPES_PATH, REQ_PATH, load_json, options, option_packs, CLI
import tfe_model as TM
import gaps as G

FIELDS = ("id", "group", "epic", "title", "description", "acceptance_criteria", "exclusions", "references", "phase", "priority")

SIZE_RULES = ("SIZE RULES (L2/L3): every row gets a T-shirt size 0 | XS | S | M | L | XL | XXL - never person days; the Parameter sheet maps the size to person days "
              "(mapping below, editable by the client) and every total follows by formula. 0 = nothing to do (e.g. kept as it is). Nothing is above XXL. A requirement that needs "
              "more than XXL keeps its own row WITHOUT size and gets estimation positions below it (same req_id and option, position 1, 2, ..., position_title), each at most XXL; "
              "the workbook sums them and flags the requirement as cut. A requirement sized XXL itself is flagged as not sprint-sized. The client's rows are never re-cut, merged or renamed.")


def size_rules(cfg):
    """the size rules: SIZE_RULES for the method's T-shirt labels, the run's own scale otherwise (estimation.sizes, settings.py)"""
    if "own_size_scale" not in flags(cfg): return SIZE_RULES
    est = cfg.get("estimation") or {}; sz = [str(x) for x in est.get("sizes") or []]; top = sz[-1] if sz else "?"
    return (f"SIZE RULES (L2/L3): every row gets one label of the run's size scale {' | '.join(sz)} - never a person-day figure of its own; the Parameter sheet maps the "
            "label to person days (mapping below, editable by the client) and every total follows by formula. " + ("0 = nothing to do (e.g. kept as it is). " if "0" in sz else "")
            + f"Nothing is above {top}. A requirement that needs more than {top} keeps its own row WITHOUT size and gets estimation positions below it (same req_id and option, "
            f"position 1, 2, ..., position_title), each at most {top}; the workbook sums them and flags the requirement as cut. A requirement at or above the sprint limit "
            f"({est.get('sprint_limit_pd', 20)} {est.get('unit_short', {}).get('en', 'PD')}) is flagged as not sprint-sized. The client's rows are never re-cut, merged or renamed. "
            "Effort bands written in T-shirt sizes (knowledge packs, reference rows) translate by the method's default person days: "
            + ", ".join(f"{k} = {v}" for k, v in (((cfg.get("_method") or {}).get("defaults") or {}).get("estimation") or {}).get("tshirt_map", {}).items()) + " - take the label of your scale closest to that effort.")


ASSUMPTION_RULE = ("ASSUMPTION RULE: single values only. A broadly written requirement is sized under its most probable reading; on a tie the reading with the lowest "
           "effort that is closest to the standard. Write the reading short into the row's estimation_assumption AND register it once in `Assumptions taken` (affects = the row keys, "
           "FR-041 or FR-041@<option> when it concerns one option only; assumption = the sentence the client confirms or denies; if_not = what changes). Never an open question to the client - "
           "the reading lands on the Annahmen sheet with a confirm / deny dropdown, and a later denial explains the change.")
COUNT_RULE = ("NO DOUBLE COUNTING: PM, SA, BA and QA are percentages on top of the development total per option, and phases no requirement describes (project setup, content "
              "setup, acceptance support, cutover, hypercare, data cleanup) are fixed person days of the consolidation. A row whose content such a block carries (CI/CD, operations, test strategy, "
              "data migration and cutover) sizes only the development work the block does not contain; the part the block carries is size 0 here - set carried_by to the block and name it in "
              "estimation_assumption ('abgedeckt durch QA-Zuschlag', 'abgedeckt durch Phase Umstieg'). Every client row stays visible. FR/TR split: the interface, synchronisation and middleware "
              "effort sits on the technical requirement (depends_on, integration_on_tr = yes); the functional row carries UI and platform-internal logic only.")
APPROACH = {"greenfield": "standard = shipped functionality of the named version carries it (configuration and test only) | partial = shipped functionality carries part of it, the gap is built | custom = built from scratch",
            "brownfield": "keep = today's code stays as it is (size 0 unless a test or a small change is needed) | adapt = today's code stays and is changed for the target | convert-to-standard = today's own code is replaced by the target's standard | rebuild = rebuilt on the target | retire = the function is removed (size = the removal) | new = not present today, built new"}
LOOKUP_RULES = ("NARROW CODE LOOKUP (brownfield options only): the BASELINE is the default evidence. Open the frozen client repository only to fill a named gap - write lookup_question "
                "BEFORE you open code; start only from the locators the BASELINE names for that row (implementing units, feature and task locators); follow the call chain in whole classes and "
                "methods: at most {max_classes} classes per requirement and option over at most {max_layers} layers (controller -> facade -> service/strategy) plus the bean wiring, items.xml and "
                "ImpEx of the types involved; grep only inside the row's units plus at most {max_extra_extensions} further ones. Record lookup_locators (file:line ranges), lookup_answer, "
                "lookup_extends (the HO row it extends), lookup_status done | budget-exhausted and size_before_lookup. Budget exhausted: stop, size under the most probable reading, say so in "
                "estimation_assumption. A lookup that contradicts a handover row changes nothing silently: report it as a finding for the lead. Greenfield rows: no repository lookup at all.")


def cell(v, cap=400):
    s = "; ".join(str(x) for x in v) if isinstance(v, list) else str(v if v is not None else "")
    s = s.replace("|", "/").replace("\n", " <br> ").strip()
    return (s[:cap] + " ...") if len(s) > cap else s


def requirements():
    return {r["id"]: r for r in load_json(REQ_PATH, {"requirements": []})["requirements"]}


def scope_entry(scope):
    return (load_json(SCOPES_PATH, {"scopes": {}})["scopes"].get(scope) or {})


def chunk_ids(scope):
    """The requirement ids of a chunk: state/scopes.json meta.req_ids (written by `dbcx discover`)."""
    return list((scope_entry(scope).get("meta") or {}).get("req_ids") or [])


def owner_of(rid):
    for name, e in load_json(SCOPES_PATH, {"scopes": {}})["scopes"].items():
        if rid in ((e.get("meta") or {}).get("req_ids") or []): return name
    return None


def req_table(ids, req, title, note):
    if not ids: return ""
    fields = FIELDS + (("row_class", "applies_to") if any((req.get(i) or {}).get("row_class") for i in ids) else ())   # TM / RF rows in the chunk
    head = "| " + " | ".join(fields) + " |\n|" + "---|" * len(fields)
    rows = [f"| " + " | ".join(cell(req[i].get(f)) if i in req else ("" if f != "id" else i) for f in fields) + " |" for i in ids]
    return f"## {title}\n{note}\n\n{head}\n" + "\n".join(rows)


def related_block(ids, req):
    """Requirements referenced by this chunk's rows but owned elsewhere - needed for depends_on / the FR-TR split."""
    mine = set(ids); out = []
    for i in ids:
        for ref in (req.get(i, {}).get("references") or []):
            ref = ref.strip()
            if not ref or ref in mine or ref not in req: continue
            o = req[ref]; out.append(f"- **{ref}** ({o.get('group', '')}, epic {o.get('epic', '')}, owned by chunk {owner_of(ref) or '?'}): {cell(o.get('title'), 120)} - {cell(o.get('description'), 240)}")
    uniq = list(dict.fromkeys(out))
    if not uniq: return "## RELATED REQUIREMENTS OWNED BY OTHER CHUNKS\n(none of your rows references a requirement outside your chunk - the integration effort of your rows then sits on your own rows and derivation says so)"
    return ("## RELATED REQUIREMENTS OWNED BY OTHER CHUNKS (never estimate them)\n"
            "These carry the integration, synchronisation and middleware effort of your rows. Name them in `depends_on`, set `integration_on_tr = yes` "
            f"and size only UI, UX, frontend and platform-internal logic for the referencing row. A question about one goes to `Open questions` (`{CLI} questions` routes it to the owning chunk).\n\n" + "\n".join(uniq))


def options_block(cfg, packs=None):
    """one TARGET block per option (packs = only the options of these technology packs)"""
    pk = option_packs(cfg); out = ["## OPTIONS (estimate EVERY requirement for EVERY option below; option = the id in the `option` column)"]
    for o in options(cfg):
        if packs and o.get("pack") not in packs: continue
        p = pk.get(o.get("pack")) or {}; start = o.get("start") or "greenfield"
        out.append(f"### TARGET {o['id']} - {o['label']}\n- start: {start}\n- technology: {p.get('display', o.get('pack', ''))} (pack {o.get('pack', '')})"
                   + "".join(f"\n- {k}: {o[k]}" for k in ("version", "plan", "frontend") if o.get(k))
                   + f"\n- approach vocabulary: {APPROACH.get(start, '')}"
                   + ("\n- evidence beyond vendor sources: the BASELINE rows (HO-...) and, for a named gap, a narrow lookup in the client repository" if start == "brownfield" else "\n- no client repository: vendor sources and vendor standard code only"))
    return "\n\n".join(out)


def size_block(cfg):
    est = cfg.get("estimation") or {}; m = est.get("tshirt_map") or {}
    sur = ", ".join(f"{s.get('role')} {s.get('pct')} %" for s in est.get("surcharges") or [])
    return (f"## SIZE MAPPING (defaults of the Parameter sheet - editable in the workbook)\n" + ", ".join(f"{k} = {v}" for k, v in m.items()) + f" {est.get('unit', 'PD')}; sprint limit {est.get('sprint_limit_pd', 20)}; "
            f"surcharges on top of the development per option: {sur}; day rate {est.get('day_rate', '')} {est.get('currency', '')}.\n\n{size_rules(cfg)}\n\n{ASSUMPTION_RULE}\n\n{COUNT_RULE}")


def _ho(typ):
    env = load_json(os.path.join("input", "handover", f"{typ}.json"), {}) or {}
    return env.get("data", env) if isinstance(env, dict) else {}


def nr_merges(req, cfg=None):
    """derived requirements of the code analysis (requirements-set rows of origin code-analysis) merged into client rows:
    {client id: [NR row]} - with decisions (run.json requirements.decisions or the applied classification) the decided target only;
    without them target = extra.merged_into, else the rows it references"""
    dec = TM.decisions(cfg) if cfg else {}
    if dec:
        out = {}
        for k, d in dec.items():
            if d.get("merge_into") and k in req: out.setdefault(d["merge_into"], []).append(dict(req[k], _basis=d.get("basis", "")))
        return out
    out = {}
    rows = list(req.values()) + [r for r in _ho("requirements-set").get("requirements") or [] if isinstance(r, dict) and r.get("id") not in req]
    for r in rows:
        x = r.get("extra") or {}
        if x.get("origin") != "code-analysis" or (x.get("client_decision") or x.get("proposed_handling")) != "merge-into-existing": continue
        tgt = x.get("merged_into") or r.get("references") or []
        for t in ([tgt] if isinstance(tgt, str) else tgt): out.setdefault(t, []).append(r)
    return out


def class_merges():
    """client-row candidates of the applied classification: {client id: [candidate]}"""
    st = load_json(os.path.join("work", "classification.json"), {}) or {}; out = {}
    if st.get("status") not in ("approved", "applied"): return out
    for c in st.get("candidates") or []:
        if c.get("class") == "client-row":
            for t in c.get("client_rows") or []: out.setdefault(t, []).append(c)
    return out


BASELINE_RULES = ("READING AND SIZING (every option): the written requirement is the heading, the code analysis tells the detailed story - "
                  "the real scope of a requirement = its text + the description gap + what today's shop does + the derived requirements merged into it. "
                  "The most probable reading of a broad requirement is what today's shop does (every current function stays); the tie-break 'lowest effort, closest to the standard' "
                  "applies only when neither the requirement text nor the code analysis decides. Brownfield sizes what the move changes on top of what exists: a function that stays as it is "
                  "may be {smallest} - cite the HO row that shows it. Greenfield sizes the rebuild of the REAL scope and its derivation names the scope elements in functional terms "
                  "(e.g. 'incl. own steps for payer address and unloading point, order reference mandatory with 36 characters'); greenfield rows may cite HO rows (functional scope), never the repository. "
                  "A row of a requirement whose coverage row shows a description gap or today custom / partial cites that HO-requirements-coverage#<id> (the CHECK refuses it otherwise).")


def baseline_block(ids, cfg):
    """per requirement the handover rows that name it - the real scope of every requirement, for EVERY option"""
    cov = {r.get("req_id"): r for r in _ho("requirements-coverage").get("coverage") or [] if isinstance(r, dict)}
    tr = _ho("target-readiness"); depth = (_ho("customization-depth").get("units") or {}); req = requirements()
    feats = [f for f in tr.get("features") or [] if isinstance(f, dict)]; tasks = [x for x in tr.get("migration_tasks") or [] if isinstance(x, dict)]
    nr = nr_merges(req, cfg); cm = class_merges(); tk = {x.get("id"): x for x in tasks}
    head = "## BASELINE (today's shop - the real scope of every requirement; every option - cite as HO-<type>#<id>, never restate it as your own fact)"
    if not (cov or feats or tasks or depth or nr or cm):
        if not any((o.get("start") or "") == "brownfield" for o in options(cfg)): return ""
        return head + "\n(no code-analysis handover imported yet - `dbcx handover import requirements-coverage` etc.; until then a brownfield row rests on assumptions)"
    lines = [head, BASELINE_RULES.replace("{smallest}", " or ".join(map(str, ((cfg.get("estimation") or {}).get("sizes") or ["0", "XS"])[:2]))), ""]   # the two smallest labels of the scale
    for i in ids:
        c = cov.get(i); parts = []; r = req.get(i) or {}
        if c:
            parts.append(f"HO-requirements-coverage#{i}: verdict {c.get('verdict', '')}" + (f", today {c['today']}" if c.get("today") else "") + f", units {', '.join(c.get('units') or []) or '-'}"
                         + (f", target standard {c['target_standard']}" if c.get("target_standard") else "") + (f", recommendation {c['recommendation']}" if c.get("recommendation") else "")
                         + (f", {cell(c.get('key_statement'), 160)}" if c.get("key_statement") else "") + (f"; DESCRIPTION GAP: {cell(c['description_gap'], 400)}" if c.get("description_gap") else "")
                         + (f"; TODAY'S SHOP: {cell(c['current_state_note'], 400)}" if c.get("current_state_note") else ""))
        for u in (c or {}).get("units") or []:
            d = (depth.get(u) or {}).get("classification") or {}
            if d: parts.append(f"HO-customization-depth#{u}: depth {d.get('depth', '')}, disposition {d.get('disposition', '')}")
        parts += [f"HO-target-readiness#{f.get('feature_id')}: {cell(f.get('feature'), 80)} - {f.get('verdict', '')}" for f in feats if f.get("primary_requirement") == i]
        parts += [f"HO-target-readiness#{x.get('id')}: {cell(x.get('task'), 100)}" for x in tasks if i in (x.get("affected_requirements") or [])]
        parts += [f"{n['id']} (derived requirement of the code analysis, merged into this requirement - part of its real scope" + (f", decision {n['_basis']}" if n.get("_basis") else "") + f"): {cell(n.get('title'), 100)} - {cell(n.get('description'), 300)}"
                  + (f" - acceptance: {cell(n.get('acceptance_criteria'), 240)}" if n.get("acceptance_criteria") else "") for n in nr.get(i, [])]
        parts += [f"{m['candidate_id']} (classification: part of this requirement - {m['source']}): {cell(m.get('title_de') or m.get('handover_text'), 240)}" for m in cm.get(i, [])]
        for src in r.get("source") or [] if TM.row_class(r) != "client" else []:   # a TM / RF row: the handover row it comes from
            typ, _, key = src[3:].partition("#") if src.startswith("HO-") else ("", "", "")
            if typ == "target-readiness" and key in tk: parts.append(f"{src}: {cell(tk[key].get('task'), 200)}" + (f" - finding: {cell(tk[key].get('finding'), 200)}" if tk[key].get("finding") else ""))
            elif typ == "customization-depth" and key in depth: d = (depth[key].get("classification") or {}); parts.append(f"{src}: disposition {d.get('disposition', '')} - {cell(d.get('disposition_rationale'), 300)}")
        lines.append(f"- **{i}**: " + ("; ".join(parts) if parts else "no handover row - a brownfield row for it rests on the requirement text (approach new, or an assumption)"))
    return "\n".join(lines)


def classes_block(ids, req, cfg=None):
    """scenario mode: the row-class rules when the chunk holds technical migration or refactoring rows"""
    if not any(TM.row_class(req.get(i)) != "client" for i in ids): return ""
    term = (((cfg or {}).get("estimation") or {}).get("size_term") or {}).get("en") or "T-shirt"
    return ("## ROW CLASSES (technical migration TM-nn, refactoring RF-nn)\nTM rows are technical necessities of the move no client row describes: estimate them for every option in their "
            "`applies_to` (each option sizes them for itself; 0 is allowed). RF rows are clean-core / quality changes not needed to run today's functions on the target: estimate them for the "
            "brownfield options only - a greenfield option has NO row for them (the CHECK refuses one). A refactoring row may carry the migration effort it makes unnecessary on the client rows "
            f"it names: saved_size ({term}) + saves (the client row ids) - the client rows keep their own sizes, the scenario total subtracts the saving. Client rows stay the 'pure' variant of "
            "the option: brownfield = today's functions moved to the target frontend, backend changed only where the headless frontend forces it; greenfield = rebuilt on the standard.")


def is_block(cfg):
    """scenario mode: the integration platform effort when run.json estimation.integration_platform names one"""
    ip = (cfg.get("estimation") or {}).get("integration_platform")
    if not ip: return ""
    term = ((cfg.get("estimation") or {}).get("size_term") or {}).get("en") or "T-shirt"
    return (f"## INTEGRATION PLATFORM EFFORT ({ip})\nEvery row also carries is_size = the {term} size of its effort on {ip} (the same mapping; empty when the row touches no interface) and "
            f"is_note = what changes on the interface, in one functional sentence (e.g. 'the order interface carries the plant split as an additional field'). Estimation positions carry their own "
            f"is_size; a requirement with positions has none. One interface change is carried by ONE row - the row that owns the interface; others name it in carried_by. The PM / SA / BA / QA "
            f"surcharges apply to {ip} effort as well (shown separately); size is the effort on the commerce platform only.")


def lookup_block(cfg):
    if not any((o.get("start") or "") == "brownfield" for o in options(cfg)): return ""
    return "## " + LOOKUP_RULES.format(**{"max_classes": 5, "max_layers": 3, "max_extra_extensions": 2, **((cfg.get("estimation") or {}).get("lookup") or {})})


def option_overview(cfg):
    """development per chunk and option from the chunk analyses, for the consolidator's reconciliation"""
    sj = load_json(SCOPES_PATH, {"scopes": {}})["scopes"]; est = cfg.get("estimation") or {}; m = {k: float(v) for k, v in (est.get("tshirt_map") or {}).items()}
    opts = options(cfg); ip = (est.get("integration_platform") or "")
    cols = [f"{o['id']} PD" for o in opts] + ([f"{o['id']} {ip} PD" for o in opts] if ip else [])
    lines = ["| chunk | epics | requirements | " + " | ".join(cols) + " |", "|---|---|---|" + "---|" * len(cols)]
    for name in sorted(sj):
        d = load_json(os.path.join("analysis", "scopes", f"{name}.json"), None); meta = sj[name].get("meta") or {}
        if not d: lines.append(f"| {name} | {cell(meta.get('EPICS'), 60)} | {len(meta.get('req_ids') or [])} | " + " | ".join("(no analysis yet)" for _ in cols) + " |"); continue
        rows = d.get("estimation", []) or []
        lines.append(f"| {name} | {cell(meta.get('EPICS'), 60)} | {len(meta.get('req_ids') or [])} | " + " | ".join(str(round(sum(m.get(r.get(f) or '', 0) for r in rows if r.get('option') == o['id']), 1)) for f in ("size",) + (("is_size",) if ip else ()) for o in opts) + " |")
    tasks = [x for x in _ho("target-readiness").get("migration_tasks") or [] if isinstance(x, dict) and not x.get("affected_requirements")]
    tb = ("\n\n## TECHNICAL MIGRATION TASKS WITHOUT A REQUIREMENT (brownfield: each becomes a fixed-PD line, block migration-task, of its option)\n" + "\n".join(f"- HO-target-readiness#{x.get('id')}: {cell(x.get('task'), 160)}" for x in tasks)) if tasks else ""
    return "## DEVELOPMENT PER CHUNK AND OPTION (from the chunk analyses, sizes mapped with the default table)\nYour `Totals` must reconcile with these numbers per option; where they cannot, the divergence is a finding, not a rounding.\n\n" + "\n".join(lines) + tb


def scenarios_block(cfg):
    """scenario mode: the scenarios the workbook totals and the lead's starting values of the fixed phases per scenario"""
    opts = options(cfg); f = TM.flags(cfg, opts, list(requirements().values()))
    if not f["scenario_mode"]: return ""
    sc = TM.scenarios(cfg, opts); seed = (cfg.get("estimation") or {}).get("fixed_phases_seed") or {}
    out = ["## SCENARIOS (the workbook's totals - run.json `scenarios`; without it one per option)"] + [f"- **{s['id']}** ({s['label']}): option {s['option']}, row classes {', '.join(s['classes'])}" + (", minus the savings of the refactoring rows" if s["subtract_savings"] else "") for s in sc]
    out += ["", "Per scenario: `Totals` one row dimension scenario (key = the scenario id); `Fixed phases` with column scenario (and its option) - the phases of the migration-only and of the refactoring scenario may differ."]
    rows = [(sid, x) for sid, xs in seed.items() if not sid.startswith("_") and isinstance(xs, list) for x in xs]
    if rows:
        out += ["", "## FIXED PHASE SEEDS (the lead's starting values - keep, adjust or drop each with the reason in `Fixed phase seeds`; drop a phase a row or a surcharge already carries; you may add)"]
        out += [f"- {sid}: {x.get('phase')} - {x.get('pd')} PD" + (f" ({x['note']})" if x.get("note") else "") for sid, x in rows]
        if seed.get("_readme"): out.append(f"(note of the lead: {seed['_readme']})")
    return "\n".join(out)


def classify_block(cfg):
    """the classification agent's candidates (work/classification.json) and the client rows they name"""
    st = load_json(os.path.join("work", "classification.json"), {}) or {}; req = requirements()
    if not st.get("candidates"): return "## CANDIDATES\n(no work/classification.json - run `dbcx classify draft` first)"
    out = ["## CANDIDATES (work/classification.json - classify every one; the handover text is code-analysis vocabulary, your texts are not)", "", "| candidate_id | source | topic | requirements | units | handover text |", "|---|---|---|---|---|---|"]
    out += [f"| {c['candidate_id']} | {c['source']} | {cell(c.get('topic'))} | {cell(c.get('requirements'))} | {cell(c.get('units'))} | {cell(c.get('handover_text'), 700)} |" for c in st["candidates"]]
    named = list(dict.fromkeys(x for c in st["candidates"] for x in c.get("requirements") or []))
    out += ["", "## CLIENT REQUIREMENTS THE CANDIDATES NAME (verbatim; the whole list: state/requirements.json)", ""] + [f"- **{i}** ({cell(req[i].get('epic'), 40)}): {cell(req[i].get('title'), 120)} - {cell(req[i].get('description'), 300)}" for i in named if i in req]
    out += ["", "## OPTIONS OF THIS RUN", "; ".join(f"{o['id']} ({o['label']}, {o.get('start', 'greenfield')})" for o in options(cfg))]
    return "\n".join(out)


def triage_part(scope):
    """the rows of a triage chunk (work/impact-plan.json, `dbcx impact plan`)"""
    pl = load_json(TM.PLAN_PATH, {}) if os.path.exists(TM.PLAN_PATH) else {}
    return next((p["rows"] for p in pl.get("parts") or [] if p["scope"] == scope), None)


def systems_block(cfg):
    """the run's systems: who estimates them, what they depend on, their landscape ids and options"""
    m = TM.system_model(cfg)
    out = ["## SYSTEMS OF THIS RUN (an Impacts row names one of these ids, or `none`)", "", "| system | label | kind | estimated by | owner | depends on | landscape ids | options |", "|---|---|---|---|---|---|---|---|"]
    out += [f"| {s['id']} | {cell(s['label'])} | {s['kind']} | {s['estimated_by']} | {cell(s.get('owner_label'))} | {s.get('depends_on') or ''} | {cell(s.get('landscape_ids'))} | "
            + cell("; ".join(f"{o['id']} ({o['label']}, {o.get('start', 'greenfield')})" for o in s["options"])) + " |" for s in m["systems"]]
    return "\n".join(out)


def landscape_block(cfg):
    """the customer's landscape (state/landscape.json): every system with its run system, the interfaces - cited as HO-landscape#<id>"""
    raw = TM.load_landscape(RUN)
    if raw is None: return "## LANDSCAPE\n(no landscape imported - name systems outside the run from the corpus; the run's systems are above)"
    land = TM.normalise_landscape(raw)[0]; owner = {lid: s["id"] for s in TM.system_model(cfg)["systems"] for lid in s.get("landscape_ids") or []}
    out = ["## LANDSCAPE (state/landscape.json - every system of the customer; cite an entry as HO-landscape#<id>)", "", "| id | name | kind | description | owner | aliases | run system |", "|---|---|---|---|---|---|---|"]
    out += [f"| {x['id']} | {cell(x['name'])} | {cell(x['kind'])} | {cell(x['description'], 200)} | {cell(x['owner'])} | {cell(x['aliases'])} | {owner.get(x['id'], '(not in this run)')} |" for x in land["systems"]]
    if land["interfaces"]: out += ["", "Interfaces of the landscape:", ""] + [f"- {f['id']}: {f['from']} -> {f['to']}" + (f" via {f['via']}" if f.get("via") else "") for f in land["interfaces"]]
    return "\n".join(out)


def triage_rows_block(ids, req, cfg):
    """the chunk's rows verbatim with what the client's list names and the deterministic pre-fill"""
    m = TM.system_model(cfg)
    out = ["## YOUR ROWS (verbatim from the client's list; pre-fill = the systems the list names - keep each one with its impact text or remove it with a reason)", "",
           "| id | group | epic | title | description | acceptance_criteria | exclusions | phase | named in the list | pre-fill | rolls up to |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i in ids:
        r = req.get(i) or {"id": i}; pre = TM.prefill(r, m)
        named = "; ".join(r.get("systems_named") or []) or "; ".join(f"{e['end']}: {e['name']}" for e in r.get("ends") or [])
        out.append(f"| {i} | {cell(r.get('group'))} | {cell(r.get('epic'))} | {cell(r.get('title'))} | {cell(r.get('description'))} | {cell(r.get('acceptance_criteria'))} | {cell(r.get('exclusions'))} | "
                   f"{cell(r.get('phase'))} | {cell(named)} | {cell('; '.join(k + ' (' + ', '.join(v) + ')' for k, v in pre.items()))} | {r.get('rollup_to') if r.get('rollup_to') not in (None, i) else ''} |")
    refs = [x for x in dict.fromkeys(req[i].get("rollup_to") for i in ids if i in req) if x and x in req and TM.is_reference(req[x])]
    if refs:
        out += ["", "## REFERENCE ROWS YOUR ROWS ROLL UP TO (estimate: false - context only, never an Impacts row)", ""]
        out += [f"- **{x}** ({cell(req[x].get('epic'), 40)}): {cell(req[x].get('title'), 120)} - {cell(req[x].get('description'), 400)}" for x in refs]
    n = sum(1 for r in req.values() if TM.is_reference(r))
    if n > len(refs): out += ["", f"The list has {n} reference row(s) (estimate: false) in all - context only (state/requirements.json), never an Impacts row."]
    return "\n".join(out)


def mechanism_block(scopes):
    """per option: mechanisms that appear in more than one chunk with diverging sizes - the calibration candidates"""
    by = {}
    for name, d in scopes.items():
        for r in d.get("estimation", []) or []:
            mech = (r.get("mechanism") or "").strip().lower()
            if mech and not str(r.get("position") or "").strip(): by.setdefault((r.get("option"), mech), []).append((name, r.get("rid") or r.get("req_id"), r.get("size")))
    out = [f"- **{m}** ({o}) in {len({x[0] for x in rows})} chunks, sizes {'/'.join(sorted({str(x[2]) for x in rows}))}: " + ", ".join(f"{x[1]} ({x[0]}, {x[2]})" for x in rows)
           for (o, m), rows in sorted(by.items()) if len({x[0] for x in rows}) > 1 and len({x[2] for x in rows}) > 1]
    if not out: return ["## Mechanisms sized in more than one chunk", "", "(none diverge - say so in the summary and leave `Calibration` empty)"]
    return ["## Mechanisms sized in more than one chunk with diverging sizes, per option (calibration candidates)", ""] + out


def missing_block(scopes, cfg):
    req = requirements(); out = []; gone = TM.excluded(cfg) | TM.reference_ids(req.values())
    for o in options(cfg):
        done = {r.get("req_id") for d in scopes.values() for r in d.get("estimation", []) or [] if r.get("option") == o["id"]}
        miss = [i for i in req if i not in done and TM.applies(req[i], o) and i not in gone]
        if miss: out.append(f"- {o['id']}: " + "; ".join(miss[:60]) + (f" ... (+{len(miss) - 60})" if len(miss) > 60 else ""))
    if not out: return ["## Requirements without an estimation row", "", "(none - every requirement is estimated for every option)"]
    return ["## Requirements without an estimation row per option - they reach the workbook as NOT ASSESSED", ""] + out + ["",
            "Do not estimate them yourself: name them in your report and raise one open question to the owning chunk per cause."]


# ------------------------------------------------------------------ system mode: one chunk = one system option
REMAINDER_RULE = ("REMAINDER RULE (rows linked by roll-up): a row that other estimating rows roll up to estimates ONLY what it needs beyond them - the linked rows carry "
                  "their own work. Its estimation_assumption names the linked rows and states what it covers beyond them (e.g. 'beyond TA-01, TA-02: the account page and its texts'); "
                  "size 0 when the linked rows carry everything (the assumption says so). A row that rolls up to another row never re-estimates the target's remainder.")


def _impacts():
    d = load_json(TM.IMPACT_PATH, {}) if os.path.exists(os.path.join(RUN, TM.IMPACT_PATH)) else {}; out = {}
    for c in d.get("cells") or []:
        if c.get("affected"): out.setdefault(c["row"], []).append((c["system"], c.get("impact") or ""))
    return out


def _impact_text(rid, imp, skip=None):
    return "; ".join(f"{s}: {cell(t, 200) or '(no impact text yet)'}" for s, t in imp.get(rid, []) if s != skip) or "-"


def _system_option(cfg, e):
    m = TM.system_model(cfg); s = next(x for x in m["systems"] if x["id"] == e["system"])
    return m, s, next(x for x in s["options"] if x["id"] == e["option"])


def system_block(cfg, e):
    """the chunk's system option as its TARGET block (one option: the other systems and options are other analysts' chunks)"""
    m, s, o = _system_option(cfg, e); pk = option_packs(cfg).get(o.get("pack")) or {}; start = o.get("start") or "greenfield"
    par = next((x for x in m["systems"] if x["id"] == s.get("depends_on")), None)
    return (f"## THIS CHUNK ESTIMATES ONE SYSTEM OPTION: {s['label']} - {o['label']} ({TM.option_key(s['id'], o['id'])})\n"
            "The run's other systems and options are estimated by other analysts; a requirement that touches several systems has one work package per system - size only the work in THIS system.\n\n"
            f"### TARGET {o['id']} - {o['label']}\n- system: {s['label']} ({s['id']}, {s.get('kind') or 'system'})\n- start: {start}\n- technology: {pk.get('display', o.get('pack', ''))} (pack {o.get('pack', '')})"
            + "".join(f"\n- {k}: {o[k]}" for k in ("version", "plan", "frontend") if o.get(k))
            + f"\n- approach vocabulary: {APPROACH.get(start, '')}"
            + ("\n- evidence beyond vendor sources: the BASELINE rows (HO-...) and, for a named gap, a narrow lookup in the client repository" if start == "brownfield" else "\n- no client repository: vendor sources and vendor standard code only")
            + (f"\n- depends on {par['label']} ({par['id']}): estimated per option of {par['id']} - a package with a parent option sizes this system's work for that option of {par['id']}, a package without one is the same for every option" if par else ""))


def wp_block(e, imp, previous=True):
    """the chunk's work packages: the estimation rows to write"""
    ws = TM.chunk_wps(e); sid = e["system"]
    out = ["## WORK PACKAGES (one estimation row per package - req_id and option EXACTLY as listed; positions keep the same req_id and option; no other row)", "",
           "| req_id | option (write this) | parent option | work package | impact in this system | the row's impact in the other systems |", "|---|---|---|---|---|---|"]
    out += [f"| {w['row']} | {w['value']} | {w.get('parent') or ''} | {w['key']} | {cell(w.get('impact'), 300) or '(no impact text yet - the scope step is not applied; read the row)'} | {_impact_text(w['row'], imp, sid)} |" for w in ws]
    again = [w for w in ws if w.get("previous")]
    if previous and again:
        out += ["", "RE-ESTIMATION (the impact text changed after the first estimate - size the package anew against the new text; the earlier row in the named chunk is superseded):"]
        out += [f"- {w['key']}: estimated in {w['previous']['chunk']} against '{cell(w['previous'].get('impact'), 200)}'" for w in again]
    arch = [w for w in ws if (w.get("architect") or {}).get("note")]   # the architect's decision on a package (dbcx discover --pickup)
    if arch:
        out += ["", "ARCHITECT'S DECISIONS ON YOUR WORK PACKAGES (a gap was decided - estimate as the note says; FINAL: no gap on the package again, the CHECK refuses it):"]
        out += [f"- {w['key']}{' (FINAL)' if w['architect'].get('final') else ''}: {cell(w['architect']['note'], 400)}" for w in arch]
    casc = [w for w in ws if w.get("cascade")]
    if casc:
        out += ["", "PARENT PACKAGE CHANGED (the parent system's package of the row was re-briefed or withdrawn after your package was planned - size against the parent's current approach):"]
        out += [f"- {w['key']}: {w['cascade']['parent']} {w['cascade']['change']}" for w in casc]
    return "\n".join(out)


def parent_block(cfg, e, sj):
    """a dependent system's chunk: the parent's approach per row and parent option, from the parent's passed analyses"""
    par = e.get("parent_system")
    if not par: return ""
    status = load_json(os.path.join("state", "STATUS.json"), {}) if os.path.exists(os.path.join(RUN, "state", "STATUS.json")) else {}
    lines = []
    for w in TM.chunk_wps(e):
        if not w.get("parent"): continue
        hit = TM.parent_rows(cfg, sj, w, status)
        if hit is None: lines.append(f"- {w['row']} / {w['parent']}: no work package of {par} for this row"); continue
        ch, row, ok = hit
        if not ok or row is None: lines.append(f"- {w['row']} / {w['parent']}: not available yet ({ch} has not passed its gauntlet) - size on the row and the impact text, name the reading in estimation_assumption"); continue
        lines.append(f"- {w['row']} / {w['parent']} ({ch}): approach {row.get('approach', '')}, size {row.get('size') or 'positions'} - {cell(row.get('mechanism'), 160)}"
                     + (f"; {cell(row.get('derivation'), 300)}" if row.get("derivation") else "") + (f" (assumption: {cell(row.get('estimation_assumption'), 200)})" if row.get("estimation_assumption") else ""))
    if not lines: return ""
    return (f"## THE PARENT'S APPROACH PER ROW AND PARENT OPTION ({par} - from its passed analyses; the basis of a difference between parent options, never re-estimate the parent)\n"
            "A package's size follows from what the parent option does there: a standard interface of one parent option needs a standard flow, a custom one of another its own mapping.\n\n" + "\n".join(lines))


def context_block(ids, req, cfg, imp):
    """the reference rows the chunk's rows name and the rows linked by roll-up, with their impact texts per system"""
    links = TM.rollup_links(req.values(), cfg); out = []
    for i in ids:
        cx = TM.context_ids(i, req, links)
        if not cx: continue
        out.append(f"- **{i}**:")
        for x in cx:
            r = req[x]; own = req.get(i) or {}
            rel = ("its roll-up target" if x == own.get("rollup_to") else "rolls up to it" if r.get("rollup_to") == i else "rolls up to the same target" if r.get("rollup_to") and r.get("rollup_to") == own.get("rollup_to") else "named in its references")
            out.append(f"  - {x} ({rel}{', reference row - context only' if TM.is_reference(r) else ''}): {cell(r.get('title'), 120)} - {cell(r.get('description'), 300)} | impacts: {_impact_text(x, imp)}")
    if not out: return ""
    rule = REMAINDER_RULE if any(links.get(i) for i in ids) else ""
    return ("## CONTEXT ROWS (never estimate them here: reference rows, and rows linked by roll-up - their own work packages carry their work)\n"
            + (rule + "\n\n" if rule else "") + "\n".join(out))


def system_analyst(scope, e, cfg, req):
    sj = load_json(SCOPES_PATH, {"scopes": {}}); ids = list((e.get("meta") or {}).get("req_ids") or []); imp = _impacts(); ws = TM.chunk_wps(e)
    rows = [("EPICS", (e.get("meta") or {}).get("EPICS", "")), ("WORK PACKAGES IN YOUR CHUNK", f"{len(ws)}: " + ", ".join(w["key"] for w in ws[:30]) + (" ..." if len(ws) > 30 else "")),
            ("CHUNK RULE", "one estimation row per WORK PACKAGE below (req_id + option as listed) and no other; the effort of THIS system only - the other systems' packages are other chunks; "
                           "one understanding of each requirement, the differences between parent options explained on their rows"),
            ("CLAIM TARGETS", "D1/Schaetzung#<req_id>@<option as listed> (the row id, e.g. " + (f"{ws[0]['row']}@{ws[0]['value']}" if ws else "FR-041@<option>") + "); the standard critic of this system option scores every claim of the chunk")]
    _, _, o = _system_option(cfg, e); look = lookup_block(cfg) if (o.get("start") or "") == "brownfield" else ""
    return {"rows": rows, "blocks": [x for x in (system_block(cfg, e), size_block(cfg), classes_block(ids, req, cfg), look, wp_block(e, imp), parent_block(cfg, e, sj),
            req_table(ids, req, "YOUR REQUIREMENTS (verbatim from the client's list)",
                      "Estimate against the requirement AS WRITTEN, including its `exclusions` column: work an exclusion names is in no figure and appears in your `Assumptions` table as an exclusion. Never rewrite, merge or split a requirement."),
            context_block(ids, req, cfg, imp), related_block(ids, req), baseline_block(ids, cfg)) if x]}


def system_critic(role, scope, e, cfg, req):
    imp = _impacts(); ids = list((e.get("meta") or {}).get("req_ids") or []); ws = TM.chunk_wps(e)
    if role == "critic-standard": return {"blocks": [system_block(cfg, e), wp_block(e, imp, previous=False)]}
    sj = load_json(SCOPES_PATH, {"scopes": {}})
    return {"rows": [("WORK PACKAGES UNDER JUDGEMENT", f"{len(ws)} of {e.get('option_key')}: " + ", ".join(w["key"] for w in ws[:30]) + (" ..." if len(ws) > 30 else ""))],
            "blocks": [x for x in (wp_block(e, imp), parent_block(cfg, e, sj), req_table(ids, req, "THE REQUIREMENTS THIS SCOPE ESTIMATES (verbatim)",
                       "Every package is judged against the requirement as written and the impact text of its system: does the size cover only this system's work, does a row others roll up to estimate only its remainder (its assumption names the linked rows), is a difference between parent options explained."),
                       context_block(ids, req, cfg, imp), baseline_block(ids, cfg)) if x]}


def extra(role, scope, cfg, rnd):
    req = requirements()
    if role in ("architect", "critic-client", "critic-standard") and architect_batch(scope) is not None: return architect_extra(role, scope, cfg, req)   # 
    se = scope_entry(scope) if role in ("analyst", "critic-client", "critic-standard") else {}
    if se.get("system"):   # a chunk of one system option
        return system_analyst(scope, se, cfg, req) if role == "analyst" else system_critic(role, scope, se, cfg, req)
    if role in ("critic-client", "critic-standard") and triage_part(scope) is not None:   # the critics of a triage chunk
        ids = triage_part(scope)
        rule = ("## THIS SCOPE IS THE TRIAGE (impact per system - no sizes)\nThe claims say which systems a row touches and what changes there; the method instructions about sizes, options and lookups do not apply. "
                + ("Judge against the client's material: does the impact follow from the row as written (incl. its exclusions), the documents and the landscape - a missing system, a system the row does not touch, a removed pre-fill without a good reason, a `none` that hides work. "
                   "Ground `requirement-reading` for the reading of a row; `standard-dispute` when you doubt that a system carries such a function by its standard (no score - routed to the standard critic)." if role == "critic-client" else
                   "Judge the standard side: does the named system carry such a function by its product standard (or is it another system's job), is an interface end plausible for that system. A DISPUTE ROUTED TO YOU from the client critic is answered in your score row."))
        return {"rows": [("ROWS UNDER JUDGEMENT", f"{len(ids)} rows of the triage chunk {scope}: " + ", ".join(ids[:40]) + (" ..." if len(ids) > 40 else ""))],
                "blocks": [rule, systems_block(cfg)] + ([landscape_block(cfg), triage_rows_block(ids, req, cfg)] if role == "critic-client" else [])}
    if role == "analyst":
        e = scope_entry(scope); meta = e.get("meta") or {}; ids = chunk_ids(scope)
        rows = [("EPICS", meta.get("EPICS", "")), ("REQUIREMENT GROUPS", meta.get("GROUPS", "")),
                ("REQUIREMENTS IN YOUR CHUNK", f"{len(ids)} rows: " + ", ".join(ids[:40]) + (" ..." if len(ids) > 40 else "")),
                ("OPTIONS OF THIS RUN", "; ".join(f"{o['id']} ({o['label']}, {o.get('start', 'greenfield')}, pack {o.get('pack', '')})" for o in options(cfg))),
                ("CHUNK RULE", "estimate EVERY id listed below for EVERY option it applies to (a refactoring row RF-nn: brownfield options only) and no other id; one understanding of each requirement, the differences between the options explained on their rows")]
        return {"rows": rows, "blocks": [x for x in (options_block(cfg), size_block(cfg), is_block(cfg), classes_block(ids, req, cfg), lookup_block(cfg),
            req_table(ids, req, "YOUR REQUIREMENTS (verbatim from the client's list)",
                      "Estimate against the requirement AS WRITTEN, including its `exclusions` column: work an exclusion names is in no figure and appears in your `Assumptions` table as an exclusion. Never rewrite, merge or split a requirement."),
            related_block(ids, req), baseline_block(ids, cfg)) if x]}
    if role == "critic-client":
        ids = chunk_ids(scope)
        if not ids: return {}
        sample = int(((cfg.get("estimation") or {}).get("lookup") or {}).get("critic_sample", 3))
        lb = (f"## LOOKUP SAMPLE (brownfield)\nRe-open the classes of {sample} lookups of this chunk (your choice, name them) plus every lookup whose size_before_lookup differs from the size by two steps or more; "
              "check the lookup answer against the code. No own exploration beyond those classes.") if lookup_block(cfg) else ""
        return {"rows": [("REQUIREMENTS UNDER JUDGEMENT", f"{len(ids)} rows x {len(options(cfg))} option(s): " + ", ".join(ids[:40]) + (" ..." if len(ids) > 40 else ""))],
                "blocks": [x for x in (req_table(ids, req, "THE REQUIREMENTS THIS SCOPE ESTIMATES (verbatim)",
                                                   "Every row is judged against the requirement as written: does the approach fit what is asked (incl. the exclusions), does a 'keep' or 'adapt' match what today's code does, is the integration effort on the technical requirement instead of counted twice, is the reading of a broad requirement registered as an assumption."),
                                       baseline_block(ids, cfg), lb) if x]}
    if role == "critic-standard":
        return {"blocks": [x for x in (options_block(cfg), is_block(cfg)) if x]}
    if role == "triage":   # scope step: a triage chunk (TRIAGE or TRIAGE-n)
        ids = triage_part(scope)
        if ids is None: raise SystemExit(f"REFUSED: {scope} is no scope of the triage plan {TM.PLAN_PATH} - `{CLI} impact plan` names the chunks")
        return {"rows": [("INPUT", f"state/requirements.json (the rows), state/landscape.json (the landscape), {TM.PLAN_PATH} (the chunks)"),
                         ("ROWS IN YOUR CHUNK", f"{len(ids)} rows: " + ", ".join(ids[:40]) + (" ..." if len(ids) > 40 else "")),
                         ("LOCATORS", "a requirement row HO-requirements-set#<row id>; a landscape system HO-landscape#<id>; the client documents SRC-nnn#anchor; claim targets triage/impacts#<row_id>@<system>")],
                "blocks": [systems_block(cfg), landscape_block(cfg), triage_rows_block(ids, req, cfg)]}
    if role == "classify":
        return {"rows": [("INPUT", "work/classification.json (the candidates, deterministic columns written by `dbcx classify draft`)"), ("TEMPLATE", "templates/classification.md"),
                         ("OUTPUT", "analysis/classification.md (the skeleton `dbcx classify draft` wrote - fill every row)"), ("CHECK", f"{CLI} md_to_json classification analysis/classification.md")],
                "blocks": [classify_block(cfg)]}
    if role == "consolidator" and TM.system_mode(cfg):   # every system option, the systems estimated outside the agents named
        return {"rows": [("CHUNK MAP", "state/scopes.json - one chunk = one system option; chunk ids are internal, the deliverable names systems, options and epics, never chunk ids")],
                "blocks": [x for x in (system_option_overview(cfg), systems_block(cfg), size_block(cfg)) if x] + [
                           "## FIXED PHASES AND CALIBRATION\nPer system option (`option` = <system>:<option>, a phase of the whole system names the system id): propose the fixed phases no work package describes "
                           "(with basis; a 'Basis' phase per system for setup, environments and configuration management) as `Fixed phases` rows; calibrate per system option (same mechanism, same size) and list every "
                           "changed row id <req_id>@<option as the chunk wrote it> in rows_changed. The workbook computes the totals per system, scenario, release and epic by formula."]}
    if role == "consolidator":
        return {"rows": [("CHUNK MAP", "state/scopes.json - chunk ids are internal; the deliverable names epics, never chunk ids")],
                "blocks": [x for x in (option_overview(cfg), size_block(cfg), is_block(cfg), scenarios_block(cfg)) if x] + [
                           "## FIXED PHASES AND CALIBRATION\nPer option: propose the fixed phases no requirement describes (with basis) and the technical migration tasks without a requirement as `Fixed phases` rows; "
                           "calibrate per option (same mechanism, same size) and list every changed row id FR-041@<option> in rows_changed; assert the development totals per option in `Totals`."]}
    return {}


# ------------------------------------------------------------------ the architect step
def architect_batch(scope):
    """the batch ARCHITECT-n of work/architect-plan.json (`dbcx architect plan`), None for any other scope"""
    if not str(scope or "").startswith(G.ARCH_SCOPE): return None
    pl = load_json(G.ARCH_PLAN, {}) if os.path.exists(os.path.join(RUN, G.ARCH_PLAN)) else {}
    return next((b for b in pl.get("batches") or [] if b["scope"] == scope), None)


def gaps_block(b, req):
    """per gap: the row verbatim, what the reporting analysts wrote, the row's impact cells, the earlier decisions on the row"""
    imp = load_json(TM.IMPACT_PATH, {}) if os.path.exists(os.path.join(RUN, TM.IMPACT_PATH)) else {}; st = load_json(G.ARCH_PATH, {}) if os.path.exists(os.path.join(RUN, G.ARCH_PATH)) else {}
    out = [f"## GAPS OF THIS BATCH ({len(b['gaps'])} - one decision each; a gap marked FINAL is the row's second visit: your decision is final, no third routing)"]
    for g in b["gaps"]:
        r = req.get(g["row"]) or {}; cells = [c for c in imp.get("cells") or [] if c["row"] == g["row"]]; prev = [d for d in st.get("decisions") or [] if d["row"] == g["row"]]
        out += ["", f"### {g['id']}" + (" - FINAL (second visit)" if g.get("visit", 1) >= 2 else "") + f" - reported by {g['system']} ({', '.join(g['options'])})" + (f", only in {', '.join(g['only_with'])}" if g.get("only_with") else ""),
                f"- row {g['row']} ({cell(r.get('group'))}, epic {cell(r.get('epic'))}): {cell(r.get('title'), 160)} - {cell(r.get('description'), 500)}"
                + (f" - acceptance: {cell(r.get('acceptance_criteria'), 300)}" if r.get("acceptance_criteria") else "") + (f" - exclusions: {cell(r.get('exclusions'), 200)}" if r.get("exclusions") else "")]
        out += [f"- work packages that reported it: {', '.join(g.get('packages') or []) or '-'} (a reduction's client assumption affects these keys; a routing's the receiving cell {g['row']}@<to>)"]
        out += [f"- analyst of {g['system']}:{x['option']} ({x['scope']}): gap_reason {cell(x['reason'], 400) or '-'}; route_suggestion {x['suggestion'] or '-'}; own share {x['size'] or '-'}" + (f"; claims {', '.join(x['claims'])}" if x.get("claims") else "") for x in g["sources"]]
        out += [f"- impact {c['system']}: " + (cell(c.get("impact"), 240) if c["affected"] else f"removed ({cell(c.get('reason'), 160)})") for c in cells] or ["- impact: (no impact matrix row)"]
        out += [f"- earlier decision ({d['batch']}): {d['decision']} -> {d['to']}: {cell(d.get('reasoning'), 200)}" for d in prev]
    return "\n".join(out)


def architect_extra(role, scope, cfg, req):
    """the architect of a batch ARCHITECT-n and the critics of that batch"""
    b = architect_batch(scope)
    if role == "architect":
        return {"rows": [("INPUT", f"{G.ARCH_PLAN} (the batch), state/requirements.json (the rows), state/landscape.json (the landscape), {TM.IMPACT_PATH} (the impact matrix), analysis/scopes/*.json (the reporting analyses)"),
                         ("GAPS IN YOUR BATCH", f"{len(b['gaps'])}: " + ", ".join(g["id"] for g in b["gaps"][:40]) + (" ..." if len(b["gaps"]) > 40 else "")),
                         ("LOCATORS", "a requirement row HO-requirements-set#<row id>; a landscape system HO-landscape#<id>; the client documents SRC-nnn#anchor; a reference row PS-7-NNN; the reporting analyst's claim C-<chunk>-NNN; claim targets architect/decisions#<row_id>@<from_system>@<to>")],
                "blocks": [systems_block(cfg), landscape_block(cfg), gaps_block(b, req)]}
    rule = ("## THIS SCOPE IS AN ARCHITECT BATCH (gap decisions - no sizes)\nThe claims say where the work of a gap goes: back to the reporting system (overrule), to another system of the run, to a landscape system outside the run, or reduced to the standard. "
            + ("Judge against the client's material: does the decision keep what the row asks for (a reduction to the standard is recorded as a client assumption), is the receiving system plausible for the customer's landscape. Ground `requirement-reading` for the reading; `standard-dispute` when you doubt a system's standard (routed to the standard critic)." if role == "critic-client" else
               "Judge the standard side of the RECEIVING system (the last part of a claim target architect/decisions#<row>@<from>@<to>): does it carry the solution sketch by its product standard or as an extension, and was the gap real in the reporting system (an overrule says it was not)."))
    return {"rows": [("DECISIONS UNDER JUDGEMENT", f"{len(b['gaps'])} gap(s) of {scope}: " + ", ".join(g["id"] for g in b["gaps"][:40]))],
            "blocks": [rule, systems_block(cfg)] + ([landscape_block(cfg), gaps_block(b, req)] if role == "critic-client" else [gaps_block(b, req)])}


def flags(cfg):
    """the brief flags of `dbcx render` (engine hook): system_mode selects the system-mode wording of the role texts (briefs/*.md
    `<!-- when system_mode -->` blocks) and the briefs.rows entries with `when`; a run without `systems` has none - its briefs are scenario mode's.
    own_size_scale: the run's estimation.sizes differ from the method default - the role texts name that scale instead of the T-shirt sizes"""
    est = cfg.get("estimation") or {}; dflt = (((cfg.get("_method") or {}).get("defaults") or {}).get("estimation") or {}).get("sizes")
    own = {"own_size_scale"} if dflt and est.get("sizes") and list(est["sizes"]) != list(dflt) else set()   # a run's own size labels: the role texts name its scale
    return ({"system_mode"} if TM.system_mode(cfg) else set()) | own


def digest_extra(which, scopes, cfg):
    if which != "SUMMARY": return []
    if TM.system_mode(cfg): return system_mechanism_block(scopes) + [""] + system_missing_block(scopes, cfg)
    return mechanism_block(scopes) + [""] + missing_block(scopes, cfg)


# ------------------------------------------------------------------ the consolidator's digest and overview in system mode
def _live(scopes_json, analyses):
    """{chunk: [the chunk's live estimation rows]} - a row counts where its work package is active (TM.planned: a superseded first estimate
    stays in its analysis and is left out), with its positions; [(chunk, entry)] of the system-option chunks"""
    sj = (scopes_json or {}).get("scopes") or {}; live = {}
    for name, e in sj.items():
        if not e.get("system"): continue
        act = {(w["row"], w["value"]) for w in TM.chunk_wps(e)}; d = analyses.get(name) or {}
        live[name] = [r for r in d.get("estimation", []) or [] if (r.get("req_id"), (r.get("option") or "").strip()) in act]
    return live


def system_option_overview(cfg):
    """development per chunk and system option from the live estimates (system mode), for the consolidator's reconciliation"""
    sj = load_json(SCOPES_PATH, {"scopes": {}}); est = cfg.get("estimation") or {}; m = {k: float(v) for k, v in (est.get("tshirt_map") or {}).items()}
    an = {n: load_json(os.path.join("analysis", "scopes", f"{n}.json"), None) for n in sj["scopes"]}; live = _live(sj, {k: v for k, v in an.items() if v})
    lines = ["| chunk | system option | work packages | PD (live estimates) |", "|---|---|---|---|"]; tot = {}
    for name in sorted(n for n, e in sj["scopes"].items() if e.get("system")):
        e = sj["scopes"][name]; k = e.get("option_key") or TM.option_key(e["system"], e["option"]); n = len(TM.chunk_wps(e))
        if not an.get(name): lines.append(f"| {name} | {k} | {n} | (no analysis yet) |"); continue
        pd = round(sum(m.get(r.get("size") or "", 0) for r in live[name]), 1); tot[k] = round(tot.get(k, 0) + pd, 1)
        lines.append(f"| {name} | {k} | {n} | {pd} |")
    lines += ["", "Per system option: " + ("; ".join(f"{k} {v}" for k, v in tot.items()) or "(no analysis yet)")]
    return ("## DEVELOPMENT PER CHUNK AND SYSTEM OPTION (live estimates - a package estimated again in a follow-up counts once, from the chunk that holds it; sizes mapped with the default table)\n"
            "The workbook computes every total by formula; these numbers are your check. Systems estimated by a partner, the client or the team have no row here - their cells are inputs of their owners.\n\n" + "\n".join(lines))


def system_mechanism_block(scopes):
    """per system option: mechanisms of the live estimates that appear in more than one chunk with diverging sizes"""
    sj = load_json(SCOPES_PATH, {"scopes": {}}); live = _live(sj, scopes); by = {}
    for name, rows in live.items():
        k = sj["scopes"][name].get("option_key") or name
        for r in rows:
            mech = (r.get("mechanism") or "").strip().lower()
            if mech and not str(r.get("position") or "").strip(): by.setdefault((k, mech), []).append((name, r.get("rid") or r.get("req_id"), r.get("size")))
    out = [f"- **{mc}** ({k}) in {len({x[0] for x in rows})} chunks, sizes {'/'.join(sorted({str(x[2]) for x in rows}))}: " + ", ".join(f"{x[1]} ({x[0]}, {x[2]})" for x in rows)
           for (k, mc), rows in sorted(by.items()) if len({x[0] for x in rows}) > 1 and len({x[2] for x in rows}) > 1]
    if not out: return ["## Mechanisms sized in more than one chunk of a system option", "", "(none diverge - say so in the summary and leave `Calibration` empty)"]
    return ["## Mechanisms sized in more than one chunk with diverging sizes, per system option (calibration candidates)", ""] + out


def system_missing_block(scopes, cfg):
    """the planned work packages without a live estimation row, per system option - they reach the workbook as NOT ASSESSED"""
    sj = load_json(SCOPES_PATH, {"scopes": {}}); live = _live(sj, scopes); out = {}
    for name, e in sj["scopes"].items():
        if not e.get("system"): continue
        done = {(r.get("req_id"), (r.get("option") or "").strip()) for r in live.get(name) or []}
        miss = [w["key"] for w in TM.chunk_wps(e) if (w["row"], w["value"]) not in done]
        if miss: out.setdefault(e.get("option_key") or name, []).extend(miss)
    if not out: return ["## Work packages without an estimation row", "", "(none - every planned work package is estimated)"]
    return ["## Work packages without an estimation row per system option - they reach the workbook as NOT ASSESSED", ""] + [f"- {k}: " + "; ".join(v[:60]) + (f" ... (+{len(v) - 60})" if len(v) > 60 else "") for k, v in out.items()] + ["",
            "Do not estimate them yourself: name them in your report and raise one open question to the owning chunk per cause."]
