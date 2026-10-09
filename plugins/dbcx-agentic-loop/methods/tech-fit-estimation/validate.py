"""Method rules of tech-fit-estimation that a schema cannot state (called by `dbcx md_to_json` after the row ids: check(kind, data, cfg)).

estimation rows (one per requirement x option x position):
  * option = an option id of the run; approach from the vocabulary of the option's start (estimation.approaches.<start>)
  * size: a label of the run's scale estimation.sizes (nothing above the largest anywhere); a requirement row without size has estimation positions (position 1, 2, ...),
    each sized, and their sum lies above the sprint limit (otherwise the requirement is sized itself); a sized requirement has none
  * greenfield rows cite no client-repository locator and carry no lookup fields
  * lookup fields: all or none; status done | budget-exhausted (then the estimation assumption says how it was sized);
    at most estimation.lookup.max_classes code classes per requirement and option; every locator inside the extensions of the handover
    row it extends (units of that row, paths from the code-inventory handover) plus at most max_extra_extensions further ones
  * carried_by names an on-top block -> the estimation assumption names it too
  * open questions never go to the client (an unclear requirement is an `Assumptions taken` row)
  scenario mode:
  * row classes (state/requirements.json row_class): a refactoring row (RF) only for brownfield options, a row only for the options
    it applies to (applies_to)
  * is_size only when run.json estimation.integration_platform names the platform; a requirement with positions has no own is_size
  * saved_size / saves only on refactoring rows, both or neither, saves = client rows; WARNING when the saving exceeds the summed
    brownfield size of the rows it names
  * product-owner language: mechanism, derivation, estimation_assumption, position_title, is_note and the assumption / exclusion / risk texts
    carry no code vocabulary (file names, path:line, paths, 'line NN', package names, class-like identifiers, the run's unit names -
    lint_deliverable.code_terms, the same patterns the hygiene layer applies); a claim statement carries no code locator
  * decisions on derived rows (run.json requirements.decisions): a merged or dropped row has no estimation row; every decision is
    valid (the id is a row, a merge target an existing client row)
  * real scope: a row of a requirement whose requirements-coverage row has a description gap or today = custom / partial cites
    HO-requirements-coverage#<id>; a greenfield derivation of such a row is no stub (>= 10 words); a brownfield keep of one of the two smallest
    sizes (0 / XS by default) cites an HO row
summary: fixed phases / calibration name known options; fixed-phase PD are numbers; with declared scenarios every fixed phase
  names its scenario (and that scenario's option), a scenario total names a scenario, every seed phase (estimation.fixed_phases_seed) has
  its keep / adjust / drop decision.
triage (the scope step): the chunk is one of work/impact-plan.json; every row of the chunk has an Impacts row, no foreign or
  reference row; system = a system of the run or `none`; affected yes needs the impact text (customer language, no code vocabulary),
  every row its reason; every pre-filled system is kept or removed with `affected no`; `none` stands alone; every Impacts row is covered by
  a claim. check_config adds the rules of an applied state/impact.json (every estimating row covered, no unknown system, impact texts).
critic: the client critic's score below the pass threshold names its ground (WARNING for a passing row without); ground is the client
  critic's field. classification: every candidate of work/classification.json classified once, texts of TM / RF rows present and at
  product-owner level, client-row candidates name existing client rows.
check_config(cfg) (`dbcx build_excel --check`): run.json systems / scenarios through tfe_model.parse_systems - unknown system or
  option refs, depends_on on a missing system, cycles and more than one level, requires / excludes typos, options and systems together,
  more cartesian scenarios than estimation.scenarios_max_auto without explicit pick; WARNING for the integration_platform alias and for the
  options of a system that is not estimated by the agents (ignored).
  (tfe_model.input_check): the group keys of requirements_mapping.json (kind, estimate, systems_field, rollup_to_field,
  passthrough; an interface group maps from and to; a passthrough sheet has an id column), the landscape (an id twice), roll-up targets
  (no row of the list, or a chain); WARNING for systems_field names and interface ends that resolve to no system of the run, roll-up
  targets on no passthrough sheet, a landscape_id the landscape lacks and a stale pre-fill. estimation rows: a reference row
  (estimate: false) has none.
  in a chunk of one system option (state/scopes.json `system`) every estimation row is an active work package of the chunk
  (req_id + option = `<option>[@<parent option>]`), the approach vocabulary is that option's start; a package without a row is a WARNING, a
  withdrawn / superseded package's row is refused. Remainder rule (every run with roll-up links): the own row of a row that other estimating
  rows roll up to names at least one of them in its estimation assumption (in system mode: the linked rows with a package in the chunk's system).
  (gaps.py): the work-package fields of estimation rows (check_work_packages) - only with run.json systems (refused without);
  on the requirement row, never a position; starting_point reuse | extend | new | clarify (greenfield: new, filled in when empty), coverage
  standard | extension | gap and confidence required; a gap names its gap_reason, a route_suggestion is a run system or landscape id;
  gap_reason / route_suggestion only on a gap; no gap on a work package the architect decided finally (routed, reduced, overruled twice).
  coverage standard without a vendor reference (PS-7-NNN in evidence) is DOWNGRADED in the converted JSON to extension with confidence low
  and reported as a WARNING (auto-fix, not a refusal: the contract wants the downgrade, md_to_json prints what it folded). architect: the
  batch is one of work/architect-plan.json, one decision per gap, the receiving end per decision kind, reasoning / solution / the client
  assumption, customer language, every decision claimed. check_config: estimation.range_factors (0 < min <= 1 <= max per confidence).
  check_config: the size scale (settings.scale_errors) - at least two labels, none twice, numeric labels in canonical form, no , | or ";
  tshirt_map with exactly the labels and strictly ascending person days; sprint_limit_pd not above the largest label; size_status labels
  of the scale with rebuild | rework.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tfe_model as TM
import gaps as G
import settings as S

PO_FIELDS = ("mechanism", "derivation", "estimation_assumption", "position_title", "is_note")
LOCATOR_RE = re.compile(r"(?:[\w@.-]+/)+[\w@.-]+:\d+(?:-\d+)?|\b[\w-]+\.(?:java|kt|groovy|ts|tsx|js|jsx|mjs|xml|jsp|impex|properties|html|scss|py):\d+")
STUB_WORDS = 10


def po(where, text, units):
    """code vocabulary in a product-owner text (lint_deliverable.code_terms)"""
    if not (text or "").strip(): return []
    from lint_deliverable import code_terms
    return [f"{where}: {k} '{t}' - say WHAT is used or built, never HOW in code (no file, path, class, package, extension name or line number)" for k, t in code_terms(text, units)[:2]]

CODE_EXT = re.compile(r"\.(?:java|kt|groovy|scala|ts|tsx|js|jsx|mjs|php|py|cs|go)(?::\d+(?:-\d+)?)?$", re.I)
NON_REPO = re.compile(r"^(?:HO-|PS-7-|SRC-|C-|Q-|A-\d|https?://|@[\w.-]+/|vendor:|input/|corpus/|reference/)", re.I)


def savings(data, cfg, pd):
    """WARNING when a refactoring row saves more than the summed brownfield sizes of the client rows it names (every chunk's rows)"""
    import glob
    rows = [r for f in glob.glob(os.path.join(cfg.get("_run_dir") or ".", "analysis", "scopes", "*.json")) for r in (TM.load(None, f, {}) or {}).get("estimation") or []]
    here = {(r.get("req_id"), r.get("option"), str(r.get("position") or "")) for r in data.get("estimation") or []}
    rows = [r for r in rows if (r.get("req_id"), r.get("option"), str(r.get("position") or "")) not in here] + list(data.get("estimation") or [])
    out = []
    for r in data.get("estimation") or []:
        if not r.get("saved_size") or not r.get("saves"): continue
        named = sum(pd.get(x.get("size") or "", 0) for x in rows if x.get("req_id") in r["saves"] and x.get("option") == r.get("option"))
        if pd.get(r["saved_size"], 0) > named: out.append(f"WARNING {r.get('rid')}: saving {r['saved_size']} ({pd.get(r['saved_size'], 0):g} PD) exceeds the summed {r.get('option')} size of {', '.join(r['saves'])} ({named:g} PD)")
    return out


def _handover(cfg, typ):
    p = os.path.join(cfg.get("_run_dir") or ".", "input", "handover", f"{typ}.json")
    try:
        with open(p, encoding="utf-8") as fh: env = json.load(fh)
    except Exception: return {}
    return env.get("data", env) if isinstance(env, dict) else {}


def _ho_row(cfg, ref):
    """HO-<type>#<id> -> the artefact row (dict) or None"""
    m = re.match(r"HO-([\w-]+)#(\S+)$", (ref or "").strip())
    if not m: return None
    data = _handover(cfg, m.group(1))
    for k, v in (data.items() if isinstance(data, dict) else []):
        if isinstance(v, list):
            for r in v:
                if isinstance(r, dict) and (r.get("rid") == m.group(2) or str(next(iter(r.values()), "")) == m.group(2)): return r
        if isinstance(v, dict) and m.group(2) in v and isinstance(v[m.group(2)], dict): return v[m.group(2)]
    return None


def _unit_paths(cfg):
    inv = _handover(cfg, "code-inventory").get("units") or []
    rows = inv.values() if isinstance(inv, dict) else inv
    return {r.get("name"): (r.get("path") or r.get("name")).rstrip("/") for r in rows if isinstance(r, dict) and r.get("name")}


def _extension(loc, paths, units=()):
    """the unit (extension) a repository locator lies in: the longest code-inventory path it starts with, else a named unit that is a
    path segment of it, else its first two segments"""
    p = re.sub(r":\d+(?:-\d+)?$", "", loc.strip()).lstrip("./")
    best = max((u for u, pre in paths.items() if p == pre or p.startswith(pre + "/")), key=lambda u: len(paths[u]), default=None)
    return best or next((u for u in units if f"/{u}/" in f"/{p}/"), None) or "/".join(p.split("/")[:2])


def repo_locators(values):
    return [x for x in values if x and not NON_REPO.match(x.strip()) and ("/" in x or CODE_EXT.search(x))]


def check_critic(data, cfg):
    thr = (cfg.get("scoring") or {}).get("pass_threshold", 8); client = (data.get("critic") or "") == "client"; out = []
    for r in data.get("scores") or []:
        if not client and r.get("ground"): out.append(f"{r.get('claim_id')}: ground is the client critic's field - leave it empty"); continue
        if client and not r.get("ground"):
            if isinstance(r.get("score"), int) and r["score"] < thr: out.append(f"{r.get('claim_id')}: score {r['score']} below {thr} without a ground (requirement-reading | current-shop | effort-driver | size-plausibility | standard-dispute)")
            else: out.append(f"WARNING {r.get('claim_id')}: no ground - every client-critic row names what it judged")
    return out


def check_classification(data, cfg):
    st = TM.load(cfg.get("_run_dir"), os.path.join("work", "classification.json"), {}) or {}; ids = [c["candidate_id"] for c in st.get("candidates") or []]
    rows = data.get("candidates") or []; got = [r.get("candidate_id") for r in rows]; err = []; units = list(_unit_paths(cfg))
    if not ids: return ["work/classification.json has no candidates - run `dbcx classify draft` first"]
    err += [f"candidate {i} is not classified (no row)" for i in ids if i not in got] + [f"candidate {i} is no candidate of work/classification.json" for i in got if i not in ids]
    err += [f"candidate {i} has more than one row" for i in dict.fromkeys(got) if got.count(i) > 1]
    client = {r["id"] for r in TM.requirements(cfg.get("_run_dir")) if TM.row_class(r) == "client" and not TM.derived(r)}
    derived_ids = {c["candidate_id"] for c in st.get("candidates") or [] if c.get("row_id")}
    from common import options
    bf = any((o.get("start") or "greenfield") == "brownfield" for o in options(cfg))
    for r in rows:
        cid, cls = r.get("candidate_id"), r.get("proposed_class")
        if cls in ("tech-migration", "refactoring"):
            if not (r.get("title_de") or "").strip() or not (r.get("description_de") or "").strip(): err.append(f"{cid}: a {cls} row needs title_de and description_de")
            err += po(f"{cid} title_de", r.get("title_de"), units) + po(f"{cid} description_de", r.get("description_de"), units)
        if cls == "refactoring" and not bf: err.append(f"{cid}: refactoring rows exist for brownfield options only - this run has none")
        if cid in derived_ids and (cls not in ("client-row", "drop", "keep") or (cls == "client-row" and len(r.get("client_rows") or []) != 1)): err.append(f"{cid}: a derived row is merged into ONE client row (client-row), dropped or kept as its own row")
        if cls == "keep" and cid not in derived_ids: err.append(f"{cid}: keep is the decision on a derived row only")
        if cls == "client-row":
            if not r.get("client_rows"): err.append(f"{cid}: client-row names the client rows it belongs to (client_rows)")
            err += [f"{cid}: client_rows {x} is no client row of state/requirements.json" for x in r.get("client_rows") or [] if x not in client]
    return err


def check_triage(data, cfg):
    """scope step: one triage chunk (work/impact-plan.json) - every row of the chunk covered, systems of the run or `none`, impact text
    and reason, every pre-filled system kept or removed with a reason, `none` alone, every Impacts row covered by a claim, customer language"""
    run = cfg.get("_run_dir"); pl = TM.load(run, TM.PLAN_PATH, {}) or {}; scope = (data.get("scope") or "").strip()
    part = next((p for p in pl.get("parts") or [] if p["scope"] == scope), None)
    if not part: return [f"scope '{scope}' is no triage chunk of {TM.PLAN_PATH} ({', '.join(p['scope'] for p in pl.get('parts') or []) or 'no plan - dbcx impact plan'})"]
    model = TM.system_model(cfg); known = {s["id"] for s in model["systems"]}; ids = part["rows"]; by = {r["id"]: r for r in TM.requirements(run)}
    rows = data.get("impacts") or []; err = []; units = list(_unit_paths(cfg)); per = {}
    for x in rows:
        rid, sid = (x.get("row_id") or "").strip(), (x.get("system") or "").strip(); w = f"{rid} x {sid or '?'}"
        if rid not in ids:
            err.append(f"{w}: {rid} is no row of chunk {scope}" + (" (a reference row, estimate: false - context only)" if rid in by and TM.is_reference(by[rid]) else "")); continue
        if sid != TM.NONE and sid not in known: err.append(f"{w}: '{sid}' is no system of this run ({', '.join(sorted(known))}) or `none`"); continue
        per.setdefault(rid, []).append(x)
        if not (x.get("reason") or "").strip(): err.append(f"{w}: the reason is missing")
        if sid != TM.NONE and TM._yes(x.get("affected")):
            if not (x.get("impact") or "").strip(): err.append(f"{w}: affected yes needs the impact text (what changes in that system)")
            err += po(f"{w} impact", x.get("impact"), units)
        if not x.get("claimed_by"): err.append(f"{w}: no claim covers this row (target triage/impacts#{rid}@{sid or 'none'})")
    for rid in ids:
        xs = per.get(rid) or []
        if not xs: err.append(f"{rid}: no Impacts row - every row of the chunk names its systems or `none`"); continue
        got = [x["system"].strip() for x in xs]; dup = sorted({g for g in got if got.count(g) > 1})
        if dup: err.append(f"{rid}: more than one row for {', '.join(dup)}")
        aff = [x["system"].strip() for x in xs if x["system"].strip() != TM.NONE and TM._yes(x.get("affected"))]
        if TM.NONE in got and aff: err.append(f"{rid}: `none` together with affected systems ({', '.join(aff)})")
        if TM.NONE not in got and not aff: err.append(f"{rid}: no affected system - name the systems it touches or one row `none` with the reason")
        pre = TM.prefill(by.get(rid) or {}, model)
        err += [f"{rid}: pre-filled system {k} ({', '.join(v)}) is missing - keep it (affected yes + impact) or remove it (affected no + reason)" for k, v in pre.items() if k not in got]
        err += [f"WARNING {rid} x {x['system'].strip()}: affected no on a system that is not pre-filled - leave the row out" for x in xs if x["system"].strip() not in pre and x["system"].strip() != TM.NONE and not TM._yes(x.get("affected"))]
    return err + texts({"claims": data.get("claims")}, units)


def summary_scenarios(data, cfg, opts):
    """scenario summary rules: fixed phases per declared scenario, scenario totals, one decision per seed phase"""
    err = []; olist = list(opts.values()); declared = bool(cfg.get("scenarios")); sc = {s["id"]: s for s in TM.scenarios(cfg, olist)}; units = list(_unit_paths(cfg))
    for r in data.get("fixed_phases") or []:
        sid = (r.get("scenario") or "").strip()
        if declared and not sid: err.append(f"fixed phase {r.get('id')}: scenario missing - the phases are per scenario ({', '.join(sc)})")
        elif sid and sid not in sc: err.append(f"fixed phase {r.get('id')}: scenario '{sid}' is no scenario of this run ({', '.join(sc)})")
        elif sid and r.get("option") != sc[sid]["option"]: err.append(f"fixed phase {r.get('id')}: option '{r.get('option')}' - scenario {sid} is option {sc[sid]['option']}")
        err += po(f"fixed phase {r.get('id')} title", r.get("title"), units) + po(f"fixed phase {r.get('id')} derivation", r.get("derivation"), units)
    for r in data.get("totals") or []:
        if r.get("dimension") == "scenario" and r.get("key") not in sc: err.append(f"total {r.get('key')}: no scenario of this run ({', '.join(sc)})")
    seed = (cfg.get("estimation") or {}).get("fixed_phases_seed") or {}; dec = {((r.get("scenario") or "").strip(), (r.get("phase") or "").strip()): r for r in data.get("seed_decisions") or []}
    ph = {(r.get("scenario") or "", r.get("id")) for r in data.get("fixed_phases") or []}
    for sid, rows in seed.items():
        if sid.startswith("_") or not isinstance(rows, list): continue
        for x in rows:
            d = dec.get((sid, (x.get("phase") or "").strip()))
            if not d: err.append(f"seed phase '{x.get('phase')}' of scenario {sid}: no row in `Fixed phase seeds` (keep, adjust or drop with the reason)"); continue
            if d.get("decision") in ("keep", "adjust"):
                try: float(str(d.get("pd", "")).replace(",", "."))
                except ValueError: err.append(f"seed phase '{x.get('phase')}' ({sid}): pd '{d.get('pd')}' is no number")
                if (sid, d.get("phase_id")) not in ph: err.append(f"seed phase '{x.get('phase')}' ({sid}): phase_id '{d.get('phase_id')}' names no Fixed phases row of scenario {sid}")
    return err


def texts(data, units):
    """the assumption and exclusion texts (Assumptions, Assumptions taken) at product-owner level"""
    out = []
    for r in data.get("assumptions") or []: out += po(f"assumption {r.get('id')}", r.get("assumption"), units) + po(f"assumption {r.get('id')} effect", r.get("effect"), units)
    for r in data.get("assumptions_taken") or []:
        for f in ("question", "reading_taken", "assumption", "why", "if_not"): out += po(f"assumption taken {r.get('id')} {f}", r.get(f), units)
    for r in data.get("risks") or []: out += po(f"risk {r.get('id')}", r.get("risk"), units) + po(f"risk {r.get('id')} mitigation", r.get("mitigation"), units)   # the Risiken sheet: the hygiene layer lints it too
    for c in data.get("claims") or []:
        m = LOCATOR_RE.search(c.get("statement") or "")
        if m: out.append(f"claim {c.get('id')}: code locator '{m.group(0)}' in the statement - the workbooks show no code location (the locator belongs in the evidence of the analysis)")
    return out


def check_config(cfg):
    """the run configuration rules of the systems model (errors; "WARNING ..." entries are printed, not refused)"""
    m, err, warn = TM.parse_systems(cfg)
    ie, iw = TM.input_check(cfg, m)
    doc = TM.load(cfg.get("_run_dir"), TM.IMPACT_PATH, None) if TM.scope_step(cfg) and not err else None   # the applied impact matrix
    if doc: ie += TM.impact_errors(doc, cfg, m)
    ie += G.range_errors(cfg)   # the derived range's factors
    ie += S.scale_errors(cfg)   # the size scale: labels = map keys, canonical numeric labels, ascending person days, size_status
    return err + ie + [f"WARNING {w}" for w in warn + iw]


def system_phase_targets(cfg):
    """what a fixed phase's `option` may name in system mode (read by system_book.phase_target): `<system>:<option>`, an
    option id exactly one system owns, or a system id (a phase of the whole system, every scenario that has the system)"""
    model = TM.parse_systems(cfg)[0]; out = {}
    ids = [o["id"] for s in model["systems"] for o in s.get("options") or []]
    for s in model["systems"]:
        out[s["id"]] = s
        for o in s.get("options") or []:
            out[TM.option_key(s["id"], o["id"])] = s
            if ids.count(o["id"]) == 1: out[o["id"]] = s
    return out


def check(kind, data, cfg):
    from common import options
    if kind == "critic": return check_critic(data, cfg)
    if kind == "classification": return check_classification(data, cfg)
    if kind == "triage": return check_triage(data, cfg)
    if kind == "architect": return check_architect(data, cfg)
    est = cfg.get("estimation") or {}; opts = {o["id"]: o for o in options(cfg)}; err = []
    sizes = list(est.get("sizes") or est.get("tshirt_map") or ["0", "XS", "S", "M", "L", "XL", "XXL"]); pd = {k: float(v) for k, v in (est.get("tshirt_map") or {}).items()}   # the run's scale (settings.py; the method default for a bare cfg)
    limit = float(est.get("sprint_limit_pd") or 20); lk = est.get("lookup") or {}
    no_client_q = [f"open question {q.get('id')}: to = client - take the most probable reading and record it under `Assumptions taken`" for q in data.get("open_questions") or [] if (q.get("to") or "").strip().lower() == "client"]
    if kind == "summary":
        fopts = system_phase_targets(cfg) if TM.system_mode(cfg) else opts   # system mode: <system>:<option>, an option id one system owns, or a system id
        for r in data.get("fixed_phases") or []:
            if r.get("option") not in fopts: err.append(f"fixed phase {r.get('id')}: option '{r.get('option')}' is no option of this run ({', '.join(fopts)})")
            try: float(str(r.get("pd", "")).replace(",", "."))
            except ValueError: err.append(f"fixed phase {r.get('id')}: pd '{r.get('pd')}' is no number")
        for r in data.get("calibration") or []:
            if r.get("option") not in fopts: err.append(f"calibration {r.get('mechanism')}: option '{r.get('option')}' is no option of this run")
        return err + summary_scenarios(data, cfg, opts) + texts(data, list(_unit_paths(cfg))) + no_client_q
    if kind != "estimation": return []
    ch = TM.chunk_entry(cfg, (data.get("scope") or "").strip()) if TM.system_mode(cfg) else None   # a chunk of one system option
    if ch: opts = chunk_options(cfg, ch); err += chunk_rows(data, ch)
    groups = {}; rq = {r["id"]: r for r in TM.requirements(cfg.get("_run_dir"))}; units = list(_unit_paths(cfg)); isp = bool(est.get("integration_platform"))
    dec = TM.decisions(cfg); err += TM.decision_errors(cfg, list(rq.values())) if dec else []
    cov = {c.get("req_id"): c for c in _handover(cfg, "requirements-coverage").get("coverage") or [] if isinstance(c, dict)}
    for r in data.get("estimation") or []:
        rid = r.get("rid") or r.get("req_id"); oid = (r.get("option") or "").strip(); o = opts.get(oid)
        if not o:
            if not ch: err.append(f"{rid}: option '{oid}' is no option of this run ({', '.join(opts)})")
            continue
        q = rq.get(r.get("req_id")) or {}; cls = TM.row_class(q); own = not str(r.get("position") or "").strip()
        d = dec.get(r.get("req_id"))
        if TM.is_reference(q): err.append(f"{rid}: {r.get('req_id')} is a reference row (its group has estimate: false) - context only, no estimation row")
        if d: err.append(f"{rid}: {r.get('req_id')} is " + (f"merged into {d['merge_into']} - its scope is estimated there" if d.get("merge_into") else "dropped") + " (requirements.decisions) - no row of its own")
        if cls == "refactoring" and (o.get("start") or "greenfield") != "brownfield": err.append(f"{rid}: a refactoring row (RF) exists for brownfield options only - no {o.get('start') or 'greenfield'} row")
        elif q and not TM.applies(q, o): err.append(f"{rid}: {r.get('req_id')} does not apply to option {oid} (applies_to: {', '.join(q.get('applies_to') or [])})")
        if r.get("is_size") and not isp: err.append(f"{rid}: is_size without an integration platform (run.json estimation.integration_platform) - leave it empty")
        if (r.get("saved_size") or r.get("saves")) and cls != "refactoring": err.append(f"{rid}: a saving (saved_size / saves) belongs to a refactoring row only")
        elif bool(r.get("saved_size")) != bool(r.get("saves")): err.append(f"{rid}: saved_size and saves go together (the size of the saving and the client rows it relieves)")
        for x in r.get("saves") or []:
            if x not in rq or TM.row_class(rq[x]) != "client": err.append(f"{rid}: saves {x} - no client row of the requirement list")
        for f in PO_FIELDS: err += po(f"{rid} {f}", r.get(f), units)
        c = cov.get(r.get("req_id")) or {}
        if own and ((c.get("description_gap") or "").strip() or c.get("today") in ("custom", "partial")):
            if f"HO-requirements-coverage#{r.get('req_id')}" not in (r.get("evidence") or []): err.append(f"{rid}: the code analysis shows more than the text (description gap / today {c.get('today') or '-'}) - cite HO-requirements-coverage#{r.get('req_id')} and size the real scope")
            if (o.get("start") or "greenfield") == "greenfield" and len((r.get("derivation") or "").split()) < STUB_WORDS: err.append(f"{rid}: a greenfield derivation of this requirement names the scope elements it rebuilds (today's behaviour, the description gap) - '{r.get('derivation')}' is a stub")
        if own and (o.get("start") or "") == "brownfield" and r.get("approach") == "keep" and r.get("size") in sizes[:2] and not any(str(x).startswith("HO-") for x in r.get("evidence") or []):
            err.append(f"{rid}: a brownfield keep of size {r.get('size')} cites the handover row that shows the function exists (HO-...)")
        start = o.get("start") or "greenfield"; voc = (est.get("approaches") or {}).get(start) or []
        if voc and r.get("approach") not in voc: err.append(f"{rid}: approach '{r.get('approach')}' is not in the {start} vocabulary ({' | '.join(voc)})")
        if r.get("size") not in ("", None) and r.get("size") not in sizes: err.append(f"{rid}: size '{r.get('size')}' - nothing above {sizes[-1]}; cut it into positions")
        groups.setdefault((r.get("req_id"), oid), []).append(r)
        look = [f for f in ("lookup_question", "lookup_locators", "lookup_answer", "lookup_extends", "lookup_status") if r.get(f)]
        if start != "brownfield":
            if look: err.append(f"{rid}: a greenfield row has no code lookup ({', '.join(look)})")
            bad = repo_locators(r.get("evidence") or [])
            if bad: err.append(f"{rid}: a greenfield row cites no client repository ({', '.join(bad[:3])})")
        if look and len(look) < 5: err.append(f"{rid}: lookup fields incomplete - question, locators, answer, extends and status belong together (missing: {', '.join(f for f in ('lookup_question', 'lookup_locators', 'lookup_answer', 'lookup_extends', 'lookup_status') if f not in look)})")
        if r.get("lookup_status") == "budget-exhausted" and not (r.get("estimation_assumption") or "").strip(): err.append(f"{rid}: lookup budget exhausted - the estimation assumption states the reading the size rests on")
        if r.get("lookup_extends") and not re.match(r"HO-[\w-]+#\S+$", r["lookup_extends"]): err.append(f"{rid}: lookup_extends '{r['lookup_extends']}' is no handover row HO-<type>#<id>")
        if r.get("carried_by") and not (r.get("estimation_assumption") or "").strip(): err.append(f"{rid}: carried_by '{r['carried_by']}' - the estimation assumption names the block that carries the part sized 0")
    paths = _unit_paths(cfg)
    for (req, oid), rs in groups.items():
        own = [r for r in rs if not str(r.get("position") or "").strip()]; pos = [r for r in rs if str(r.get("position") or "").strip()]
        if len(own) != 1: err.append(f"{req}@{oid}: {len(own)} requirement rows (exactly one; positions carry position = 1, 2, ...)"); continue
        if pos:
            if own[0].get("size"): err.append(f"{req}@{oid}: a requirement with positions has no own size (its effort is the sum of the positions)")
            if own[0].get("is_size"): err.append(f"{req}@{oid}: a requirement with positions has no own is_size (the positions carry theirs)")
            miss = [p.get("position") for p in pos if not p.get("size")]
            if miss: err.append(f"{req}@{oid}: positions without size: {', '.join(miss)}")
            total = sum(pd.get(p.get("size"), 0) for p in pos)
            if not miss and total <= limit: err.append(f"{req}@{oid}: positions sum to {total:g} PD, not above the sprint limit {limit:g} - size the requirement itself")
        elif not own[0].get("size"): err.append(f"{req}@{oid}: no size and no positions")
        locs = [x for r in rs for x in (r.get("lookup_locators") or [])]
        if not locs: continue
        classes = {re.sub(r":\d+(?:-\d+)?$", "", x) for x in locs if CODE_EXT.search(x)}
        if len(classes) > int(lk.get("max_classes", 5)): err.append(f"{req}@{oid}: {len(classes)} classes read - the lookup budget is {lk.get('max_classes', 5)} per requirement and option")
        units = set()
        for r in rs:
            ho = _ho_row(cfg, r.get("lookup_extends"))
            if r.get("lookup_extends") and ho is None: err.append(f"{req}@{oid}: lookup_extends {r['lookup_extends']} names no row of the imported artefact")
            units |= set((ho or {}).get("units") or [])
        extra = {_extension(x, paths, units) for x in locs} - units
        if units and len(extra) > int(lk.get("max_extra_extensions", 2)):
            err.append(f"{req}@{oid}: the lookup leaves the handover row's extensions ({', '.join(sorted(units))}) for {len(extra)} further ones ({', '.join(sorted(extra))}) - at most {lk.get('max_extra_extensions', 2)}")
    return err + savings(data, cfg, pd) + texts(data, units) + no_client_q + remainder(data, cfg, rq, ch) + check_work_packages(data, cfg)


def chunk_options(cfg, ch):
    """{option value: the system option} of a system-mode chunk - the values its work packages name (`<option>` or `<option>@<parent option>`)"""
    s = next(x for x in TM.system_model(cfg)["systems"] if x["id"] == ch["system"]); o = next(x for x in s["options"] if x["id"] == ch["option"])
    return {w["value"]: o for w in TM.chunk_wps(ch)} or {ch["option"]: o}


def chunk_rows(data, ch):
    """every estimation row of a system-mode chunk is one of its active work packages (req_id + option value); a package without a
    row is a WARNING (the consolidation lists it as not assessed); a withdrawn or superseded package has no row here any more"""
    wps = {(w["row"], w["value"]): w for w in TM.chunk_wps(ch)}; gone = {(w["row"], w["value"]): w for w in TM.chunk_wps(ch, None) if w.get("status") not in (None, TM.ACTIVE)}
    out, seen = [], set()
    for r in data.get("estimation") or []:
        k = ((r.get("req_id") or "").strip(), (r.get("option") or "").strip()); seen.add(k)
        if k in wps: continue
        w = f"{k[0]}@{ch['system']}:{k[1]}"
        if k in gone: out.append(f"{r.get('rid')}: work package {w} is {gone[k]['status']} (dbcx discover --pickup) - drop the row")
        else: out.append(f"{r.get('rid')}: {w} is no work package of chunk {data.get('scope')} - write req_id and option exactly as WORK PACKAGES lists them ({', '.join(sorted(x['key'] for x in wps.values())[:12])})")
    out += [f"WARNING {w['key']}: no estimation row - every work package of the chunk gets one" for k, w in wps.items() if k not in seen]
    return out


def remainder(data, cfg, rq, ch):
    """remainder rule (generic): the own estimation row of a row that other estimating rows roll up to (rollup_to) names in its
    estimation assumption the linked rows and what it covers beyond them - in system mode the linked rows that have a work package in the
    chunk's system; without systems every linked estimating row. A run without roll-up links is untouched."""
    links = TM.rollup_links(rq.values(), cfg)
    if not links: return []
    aff = {(w["row"], w["system"]) for _, w in TM.planned(TM.load(cfg.get("_run_dir"), TM.SCOPES_FILE, {}) or {}).values()} if ch else None
    out = []
    for r in data.get("estimation") or []:
        t = r.get("req_id")
        if t not in links or str(r.get("position") or "").strip(): continue
        ids = [x for x in links[t] if aff is None or (x, ch["system"]) in aff]
        if not ids: continue
        a = r.get("estimation_assumption") or ""
        if not any(re.search(rf"(?<![\w-]){re.escape(x)}(?![\w-])", a) for x in ids):
            out.append(f"{r.get('rid')}: {', '.join(ids)} roll up to {t} - the estimation assumption names them and states what {t} covers beyond them (remainder rule: e.g. 'beyond {ids[0]}: ...'; size 0 when they carry everything)")
    return out


# ------------------------------------------------------------------ work-package fields and the architect's decisions
def check_work_packages(data, cfg):
    """the analyst fields per work package (system mode only); a `standard` without a vendor reference is downgraded in place (WARNING)"""
    rows = data.get("estimation") or []; run = cfg.get("_run_dir")
    if not TM.scope_step(cfg):
        return [f"{r.get('rid') or r.get('req_id')}: {f} is a field of a multi-system run (run.json systems) - leave it empty" for r in rows for f in G.WP_FIELDS if r.get(f)]
    model = TM.system_model(cfg); meta = G.scope_meta(run, data.get("scope")); land = G.landscape_ids(run); ast = TM.load(run, G.ARCH_PATH, None) or {}; ng = G.no_gap(ast); vis = G.visits(ast)
    known = {s["id"] for s in model["systems"]}; idx = TM.name_index(model, TM.normalise_landscape(TM.load_landscape(run))[0] if land else None); err = []
    for r in rows:
        rid = r.get("rid") or r.get("req_id")
        if str(r.get("position") or "").strip():
            err += [f"{rid}: {f} belongs on the requirement row of the work package, not on a position" for f in G.WP_FIELDS if r.get(f)]; continue
        s, o = G.resolve(r, model, meta); start = (o or {}).get("start") or "greenfield"; sp, cov = r.get("starting_point"), r.get("coverage")
        if not sp and o and start == "greenfield": r["starting_point"] = "new"   # the greenfield default
        elif not sp: err.append(f"{rid}: starting_point missing - what exists today: reuse | extend | new | clarify")
        elif o and start == "greenfield" and sp != "new": err.append(f"{rid}: starting_point '{sp}' on a greenfield option - nothing exists there today (new)")
        if not cov: err.append(f"{rid}: coverage missing - standard | extension | gap")
        if cov == "standard" and G.downgrade(r): err.append(f"WARNING {rid}: coverage standard without a vendor reference (no PS-7-NNN in evidence) - downgraded to extension with confidence low in the converted file; cite the reference row to keep standard")
        if not r.get("confidence"): err.append(f"{rid}: confidence missing - high | medium | low (the work package's range follows from it)")
        if cov == "gap":
            if not (r.get("gap_reason") or "").strip(): err.append(f"{rid}: a gap names its gap_reason (why the system cannot carry it)")
            sug = (r.get("route_suggestion") or "").strip()
            if sug and sug not in known and sug not in land and TM.norm_name(sug) not in idx: err.append(f"{rid}: route_suggestion '{sug}' is no system of this run ({', '.join(sorted(known))}) or of the landscape")
            elif sug and s and sug == s["id"]: err.append(f"{rid}: route_suggestion names the reporting system itself")
            k = G.wp_key(r.get("req_id"), (s or {}).get("id"))
            if s and k in ng: err.append(f"{rid}: the architect decided this work package finally ({ng[k]}) - estimate it (extension or standard); no gap again")
            elif vis.get(r.get("req_id"), 0) >= 2: err.append(f"{rid}: {r.get('req_id')} reached the architect twice - no third routing; estimate your share (extension)")
        elif r.get("gap_reason") or r.get("route_suggestion"): err.append(f"{rid}: gap_reason / route_suggestion belong to coverage gap only")
    return err


def check_architect(data, cfg):
    """one architect batch (work/architect-plan.json): a decision per gap, the receiving end per decision kind, texts, assumptions, claims"""
    run = cfg.get("_run_dir"); scope = (data.get("scope") or "").strip(); pl = TM.load(run, G.ARCH_PLAN, {}) or {}
    b = next((x for x in pl.get("batches") or [] if x["scope"] == scope), None)
    if not b: return [f"scope '{scope}' is no architect batch of {G.ARCH_PLAN} ({', '.join(x['scope'] for x in pl.get('batches') or []) or 'no batch - dbcx architect plan'})"]
    model = TM.system_model(cfg); land = G.landscape_ids(run); units = list(_unit_paths(cfg)); gaps = {g["id"]: g for g in b.get("gaps") or []}
    taken = {(a.get("id") or "").strip(): a for a in data.get("assumptions_taken") or []}; seen = set(); err = []
    for x in data.get("decisions") or []:
        row, frm = (x.get("row_id") or "").strip(), (x.get("from_system") or "").strip(); key = G.wp_key(row, frm); w = f"{row} x {frm}"
        if key not in gaps: err.append(f"{w}: no gap of batch {scope} ({', '.join(gaps)})"); continue
        if key in seen: err.append(f"{w}: more than one decision - one per gap"); continue
        seen.add(key); a = (x.get("assumption") or "").strip()
        err += G.decision_errors({"row": row, "from_system": frm, "decision": x.get("decision"), "to": (x.get("to") or "").strip(), "reasoning": x.get("reasoning"), "solution": x.get("solution"), "assumption": a}, model, land)
        if a and a not in taken: err.append(f"{w}: assumption '{a}' is no row of `Assumptions taken` ({', '.join(taken) or 'none'})")
        elif a:   # the A-nn lands on the receiving cell / the reporting packages only - a bare row id would mark every system's package of the row
            to = (x.get("to") or "").strip(); own = (x.get("decision") or "").strip() in ("overrule", "reduce-to-standard")
            ok = {G.wp_key(row, to or frm)} | (set(gaps[key].get("packages") or []) if own else set()); aff = [str(v).strip() for v in taken[a].get("affects") or [] if str(v).strip()]
            if not aff or any(v not in ok for v in aff):
                err.append(f"{w}: `Assumptions taken` {a} - affects names " + (f"the reporting work packages ({', '.join(gaps[key].get('packages') or [])}) or the cell {row}@{frm}" if own else f"the receiving cell {row}@{to}")
                           + f", never the bare row or another system (now: {', '.join(aff) or 'empty'})")
        err += po(f"{w} solution", x.get("solution"), units)
        if not x.get("claimed_by"): err.append(f"{w}: no claim covers this decision (target architect/decisions#{row}@{frm}@{(x.get('to') or '').strip() or '?'})")
    err += [f"{k}: no decision - every gap of the batch is decided (overrule | route-estimated | route-landscape | reduce-to-standard)" for k in gaps if k not in seen]
    return err + texts({"claims": data.get("claims"), "assumptions_taken": data.get("assumptions_taken")}, units)
