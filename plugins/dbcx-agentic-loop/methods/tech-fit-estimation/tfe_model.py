"""Row classes and scenarios of tech-fit-estimation - one definition for datasets.py, briefing.py, validate.py and tools/classify.py.

Row classes (state/requirements.json `row_class`, absent = client): client (the client's list, every option), tech-migration (TM-nn,
every option; `dbcx classify apply`), refactoring (RF-nn, brownfield options only). `applies_to` on a row names its options explicitly.
Scenarios (run.json `scenarios`: [{id, label, option, classes, subtract_savings}]): the totals the workbook shows; without the key one
scenario per option with every class - the single-run totals.
Decisions on derived rows: a row the code analysis proposed (requirements-set extra.origin = code-analysis) is merged into a client row
or dropped by the client - run.json `requirements.decisions` {<id>: {"merge_into": "<client id>" | "drop": true, "basis": "A-nn"}} (the
requirement list itself is read-only evidence), or by the lead's classification (a client-row / drop candidate of `dbcx classify`). A
decided row gets no estimation row of its own; without decisions every row is estimated as before.
Systems: `system_model(cfg)` - the one normalised model of run.json
`systems` (options per system, depends_on, requires / excludes, estimated_by, kind, landscape_ids) and its scenarios (cartesian product
of one option per system minus requires / excludes, or run.json `scenarios` with `pick`). Without `systems`: one implicit system `target`
with today's options, plus the implicit dependent system `integration` for estimation.integration_platform. Nothing else reads it yet.
Inputs: the group keys of requirements_mapping.json (`mapping_errors`), reference rows (`is_reference`), the
landscape (`normalise_landscape`, state/landscape.json), name resolution against the systems and the landscape (`name_index`,
`system_tokens`), the pre-fill of systems_field and interface rows (`enrich`, used by inputs.py) and the input rules (`input_check`).
Scope step: `prefill`, `triage_parts`, `merge_impact`, `impact_errors`, the impact-cell changes (`wp_changes`, `net_changes`).
Work packages and chunks: `work_package_list` (impact cell x option [x parent option], key `wp_key` / `parse_wp`), the
chunks per system option under the context budget (`plan_system_chunks`, `pack_rows`), the roll-up context (`rollup_links`, `context_ids`),
the planned packages and what the next wave picks up (`planned`, `pending`), the parent's estimate for a dependent package (`parent_rows`).
the architect's follow-ups reach the pickup too; `dependent_packages` / `parent_key` give the cascade of a re-briefed or
withdrawn parent package to the packages of its dependent systems for the same row.
"""
import itertools, json, os, re

ROW_CLASSES = ("client", "tech-migration", "refactoring")
PREFIX = {"tech-migration": "TM", "refactoring": "RF"}
SCENARIO_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def row_class(req): return (req or {}).get("row_class") or "client"


def applies(req, option):
    """does a requirement row get an estimation row for this option? (applies_to, else: refactoring rows brownfield only)"""
    at = (req or {}).get("applies_to")
    if at: return option["id"] in at
    return row_class(req) != "refactoring" or (option.get("start") or "greenfield") == "brownfield"


def load(run_dir, rel, default):
    try:
        with open(os.path.join(run_dir or ".", rel), encoding="utf-8") as fh: return json.load(fh)
    except (OSError, ValueError): return default


def requirements(run_dir):
    return (load(run_dir, os.path.join("state", "requirements.json"), {}) or {}).get("requirements") or []


def handover(run_dir, typ):
    env = load(run_dir, os.path.join("input", "handover", f"{typ}.json"), {}) or {}
    return env.get("data", env) if isinstance(env, dict) else {}


def scenarios(cfg, options):
    """[{id, label, option, option_label, classes, subtract_savings}] from run.json `scenarios` (checked), else one per option with every class"""
    raw = cfg.get("scenarios") or []; ids = {o["id"]: o for o in options}
    if not raw: return [{"id": o["id"], "label": o["label"], "option": o["id"], "option_label": o["label"], "classes": list(ROW_CLASSES), "subtract_savings": False} for o in options]
    out, seen = [], set()
    for i, s in enumerate(raw, 1):
        sid = str((s or {}).get("id") or ""); where = f"run.json scenarios[{i}]"
        if not SCENARIO_ID_RE.match(sid) or sid in seen: raise SystemExit(f"{where}: id '{sid}' must match ^[a-z][a-z0-9-]*$ and be unique")
        if s.get("option") not in ids: raise SystemExit(f"{where}: option '{s.get('option')}' is no option of this run ({', '.join(ids)})")
        cls = list(s.get("classes") or ROW_CLASSES); bad = [c for c in cls if c not in ROW_CLASSES]
        if bad: raise SystemExit(f"{where}: classes {bad} unknown (client | tech-migration | refactoring)")
        if "refactoring" in cls and (ids[s["option"]].get("start") or "greenfield") != "brownfield": raise SystemExit(f"{where}: refactoring rows exist for brownfield options only - option '{s['option']}' is {ids[s['option']].get('start') or 'greenfield'}")
        seen.add(sid); out.append({"id": sid, "label": s.get("label") or sid, "option": s["option"], "option_label": ids[s["option"]]["label"], "classes": cls,
                                   "subtract_savings": bool(s.get("subtract_savings")) and "refactoring" in cls})
    if len({s["label"] for s in out}) < len(out): raise SystemExit("run.json scenarios: labels must be unique (the totals sum by label)")
    return out


def flags(cfg, options, reqs):
    """the `when` flags of the deliverables spec: scenario_mode (run.json scenarios, estimation.integration_platform or fixed_phases_seed,
    or TM / RF rows exist) switches on the scenario workbook; row_classes (Klasse column); is (integration platform columns);
    savings_<option> (a brownfield option while RF rows exist)"""
    est = cfg.get("estimation") or {}; cls = {row_class(r) for r in reqs}
    tmrf = bool(cls & {"tech-migration", "refactoring"}); rf = "refactoring" in cls
    f = {"scenario_mode": bool(cfg.get("scenarios") or est.get("integration_platform") or est.get("fixed_phases_seed") or tmrf),
         "row_classes": bool(cfg.get("scenarios") or tmrf), "is": bool(est.get("integration_platform")), "refactoring": rf}
    for o in options: f[f"savings_{o['id']}"] = rf and (o.get("start") or "greenfield") == "brownfield"
    return f


def derived(req): return ((req or {}).get("extra") or {}).get("origin") == "code-analysis"


def decisions(cfg):
    """{row id: {"merge_into": id} | {"drop": True}, + "basis"}: run.json requirements.decisions, completed by the applied classification's
    decisions on derived rows (a run.json decision wins; `keep` = it stays an estimation row of its own)"""
    out = {k: dict(v) for k, v in (((cfg.get("requirements") or {}).get("decisions")) or {}).items() if isinstance(v, dict) and not k.startswith("_")}
    st = load(cfg.get("_run_dir"), os.path.join("work", "classification.json"), {}) or {}
    for c in st.get("candidates") or [] if st.get("status") == "applied" else []:
        rid = c.get("row_id")
        if not rid or rid in out: continue
        if c.get("class") == "client-row" and c.get("client_rows"): out[rid] = {"merge_into": c["client_rows"][0], "basis": ""}
        elif c.get("class") == "drop": out[rid] = {"drop": True, "basis": ""}
    return out


def excluded(cfg):
    """ids with no estimation row of their own (merged or dropped)"""
    return {k for k, d in decisions(cfg).items() if d.get("drop") or d.get("merge_into")}


def decision_errors(cfg, reqs):
    """a decided id must be a row of the list, a merge target an existing client row (no derived, TM or RF row, not decided itself)"""
    by = {r["id"]: r for r in reqs}; dec = decisions(cfg); err = []
    for k, d in dec.items():
        if k not in by: err.append(f"requirements.decisions {k}: no row of state/requirements.json"); continue
        if not (d.get("drop") or d.get("merge_into")) or (d.get("drop") and d.get("merge_into")): err.append(f"requirements.decisions {k}: either merge_into or drop"); continue
        t = d.get("merge_into")
        if t and (t not in by or row_class(by[t]) != "client" or derived(by[t]) or t in dec): err.append(f"requirements.decisions {k}: merge target {t} is no client row of the list")
    return err


# ------------------------------------------------------------------ systems: one solution of several systems, options compete within a system
ESTIMATED_BY = ("agents", "partner", "client", "team")
SYSTEM_KINDS = ("system", "discipline")
MAX_AUTO = 6   # default of estimation.scenarios_max_auto: more cartesian scenarios need run.json `scenarios` with `pick`


def max_auto(cfg):
    """estimation.scenarios_max_auto (method default 6, overridable per run): the most cartesian scenarios a run builds without `pick`"""
    return (cfg.get("estimation") or {}).get("scenarios_max_auto", MAX_AUTO)


def option_key(system, option): return f"{system}:{option}"


def _option_base(cfg):
    """the defaults of an option (as common.options): pack = the target-role platform slot (else target.pack), start greenfield"""
    tgt = cfg.get("target") or {}
    slot = next((pk for pk in (cfg.get("_packs") or {}).values() if pk and pk.get("kind") == "platform" and pk.get("_role") == "target"), None)
    return {"pack": (slot or {}).get("name") or tgt.get("pack", ""), "start": tgt.get("start") or "greenfield"}


def violations(pick, by_id):
    """the requires / excludes rules a pick {system: option} breaks; requires: per named system the pick is one of the listed
    options (any of them), across systems all must hold; excludes: none of the listed options is picked"""
    out = []
    for sid, oid in pick.items():
        sy = by_id.get(sid) or {}
        need = {}
        for k in (sy.get("requires") or {}).get(oid) or []: need.setdefault(k.split(":", 1)[0], []).append(k.split(":", 1)[1])
        out += [f"{option_key(sid, oid)} requires {' | '.join(option_key(t, o) for o in opts)}" for t, opts in need.items() if t in pick and pick[t] not in opts]
        out += [f"{option_key(sid, oid)} excludes {k}" for k in (sy.get("excludes") or {}).get(oid) or [] if pick.get(k.split(":", 1)[0]) == k.split(":", 1)[1]]
    return out


def _classes(s, where, err):
    cls = list(s.get("classes") or ROW_CLASSES); bad = [c for c in cls if c not in ROW_CLASSES]
    if bad: err.append(f"{where}: classes {bad} unknown (client | tech-migration | refactoring)")
    return cls


def _compat(cfg, options, err, warn):
    """no run.json `systems`: the implicit system `target` with today's options (+ `integration` for estimation.integration_platform);
    scenarios = tfe_model.scenarios with the pick added - consumers of options and scenarios see exactly what they saw before"""
    tgt = cfg.get("target") or {}; ip = ((cfg.get("estimation") or {}).get("integration_platform") or "").strip()
    syss = [{"id": "target", "label": tgt.get("platform") or "target", "kind": "system", "estimated_by": "agents", "owner_label": "", "depends_on": None,
             "landscape_ids": [], "options": [dict(o) for o in options], "requires": {}, "excludes": {}, "implicit": True}]
    if ip:
        syss.append({"id": "integration", "label": ip, "kind": "system", "estimated_by": "agents", "owner_label": "", "depends_on": "target", "landscape_ids": [],
                     "options": [{"id": "integration", "label": ip, "pack": "_generic", "start": "greenfield"}], "requires": {}, "excludes": {},
                     "implicit": True, "alias": "estimation.integration_platform"})
        warn.append(f"estimation.integration_platform '{ip}' is read as the implicit system `integration` (depends_on target) - a run with `systems` declares it as a system with depends_on")
    try: sc = scenarios(cfg, options)
    except SystemExit as ex: err.append(str(ex)); sc = []
    for x in sc:
        x["pick"] = {"target": x["option"]}; x["auto"] = not cfg.get("scenarios")
        if ip: x["pick"]["integration"] = "integration"
    return syss, sc


def _declared(cfg, err, warn):
    raw = cfg.get("systems"); est = cfg.get("estimation") or {}
    if cfg.get("options"): err.append("run.json `options` and `systems` exclude each other - the options go into systems[].options")
    if (est.get("integration_platform") or "").strip(): err.append("estimation.integration_platform with `systems`: declare the integration platform as a system (depends_on its parent) instead")
    if not isinstance(raw, list) or not raw: err.append("run.json systems: a non-empty list of systems"); return []
    base = _option_base(cfg); out, seen = [], set()
    for i, s in enumerate(raw, 1):
        s = s if isinstance(s, dict) else {}; sid = str(s.get("id") or ""); where = f"run.json systems[{i}]"
        if not SCENARIO_ID_RE.match(sid) or sid in seen: err.append(f"{where}: id '{sid}' must match ^[a-z][a-z0-9-]*$ and be unique"); continue
        seen.add(sid); where = f"system {sid}"
        by, kind = s.get("estimated_by") or "agents", s.get("kind") or "system"
        if by not in ESTIMATED_BY: err.append(f"{where}: estimated_by '{by}' (agents | partner | client | team)")
        if kind not in SYSTEM_KINDS: err.append(f"{where}: kind '{kind}' (system | discipline)")
        lids = s.get("landscape_ids") or []
        if not isinstance(lids, list) or not all(isinstance(x, str) and x for x in lids): err.append(f"{where}: landscape_ids is a list of landscape system ids"); lids = []
        opts, oseen = [], set()
        for j, o in enumerate(s.get("options") or [], 1):
            o = o if isinstance(o, dict) else {}; oid = str(o.get("id") or "")
            if not SCENARIO_ID_RE.match(oid) or oid in oseen: err.append(f"{where} options[{j}]: id '{oid}' must match ^[a-z][a-z0-9-]*$ and be unique in the system"); continue
            oseen.add(oid); x = dict(base); x.update({k: v for k, v in o.items() if v not in (None, "")}); x["label"] = o.get("label") or oid; opts.append(x)
        if by != "agents" and opts: warn.append(f"{where}: estimated by {by} - its options are ignored (no analyst, the cells are inputs for {s.get('owner_label') or by})"); opts = []
        elif by == "agents" and not opts and not s.get("options"): err.append(f"{where}: an agent-estimated system needs at least one option")
        rules = {}
        for key in ("requires", "excludes"):
            r = s.get(key) or {}
            if not isinstance(r, dict): err.append(f"{where}: {key} maps an option id to a list of <system>:<option>"); r = {}
            rules[key] = {k: list(v) if isinstance(v, list) else [v] for k, v in r.items() if not str(k).startswith("_")}
        out.append({"id": sid, "label": s.get("label") or sid, "kind": kind, "estimated_by": by, "owner_label": s.get("owner_label") or "",
                    "depends_on": s.get("depends_on") or None, "landscape_ids": list(lids), "options": opts, "implicit": False, **rules})
    by_id = {x["id"]: x for x in out}
    for x in out:
        d = x["depends_on"]
        if d is None: pass
        elif d == x["id"] or (d in by_id and by_id[d]["depends_on"] == x["id"]): err.append(f"system {x['id']}: depends_on {d} - a cycle")
        elif d not in by_id: err.append(f"system {x['id']}: depends_on '{d}' is no system of this run ({', '.join(by_id)})")
        elif by_id[d]["depends_on"]: err.append(f"system {x['id']}: depends_on {d}, which depends on {by_id[d]['depends_on']} - one level only")
        for key in ("requires", "excludes"):
            for oid, refs in x[key].items():
                if oid not in {o["id"] for o in x["options"]}: err.append(f"system {x['id']} {key}: '{oid}' is no option of {x['id']}"); continue
                for ref in refs:
                    t, _, o = str(ref).partition(":")
                    if t == x["id"]: err.append(f"system {x['id']} {key} {oid}: '{ref}' names the system itself (one option per system and scenario)")
                    elif t not in by_id or not o: err.append(f"system {x['id']} {key} {oid}: '{ref}' - <system>:<option> of a system of this run ({', '.join(by_id)})")
                    elif o not in {y["id"] for y in by_id[t]["options"]}: err.append(f"system {x['id']} {key} {oid}: '{ref}' - {t} has no option '{o}' ({', '.join(y['id'] for y in by_id[t]['options']) or 'no options'})")
    owner = {}
    for x in out:
        for lid in x["landscape_ids"]:
            if lid in owner and owner[lid] != x["id"]: err.append(f"landscape id '{lid}' maps to {owner[lid]} and {x['id']} - one system per landscape id")
            owner.setdefault(lid, x["id"])
    return out


def _system_scenarios(cfg, syss, err, warn):
    by_id = {x["id"]: x for x in syss}; chosen = [x for x in syss if x["options"]]; multi = [x for x in chosen if len(x["options"]) > 1]
    raw = cfg.get("scenarios") or []
    if raw:
        out, seen = [], set()
        for i, s in enumerate(raw, 1):
            s = s if isinstance(s, dict) else {}; sid = str(s.get("id") or ""); where = f"run.json scenarios[{i}]"
            if not SCENARIO_ID_RE.match(sid) or sid in seen: err.append(f"{where}: id '{sid}' must match ^[a-z][a-z0-9-]*$ and be unique"); continue
            seen.add(sid); where = f"scenario {sid}"
            if s.get("option"): err.append(f"{where}: with `systems` a scenario names its options in pick {{system: option}}, not `option`")
            pick, ok = {}, True
            for t, o in (s.get("pick") or {}).items():
                if t not in by_id: err.append(f"{where}: pick names '{t}', no system of this run ({', '.join(by_id)})"); ok = False
                elif not by_id[t]["options"]: err.append(f"{where}: pick names {t}, which has no options (estimated by {by_id[t]['estimated_by']})"); ok = False
                elif o not in {y["id"] for y in by_id[t]["options"]}: err.append(f"{where}: pick {t}: '{o}' is no option of {t} ({', '.join(y['id'] for y in by_id[t]['options'])})"); ok = False
                else: pick[t] = o
            for x in chosen:
                if x["id"] in pick: continue
                if len(x["options"]) == 1: pick[x["id"]] = x["options"][0]["id"]
                else: err.append(f"{where}: pick names no option of {x['id']} ({', '.join(y['id'] for y in x['options'])})"); ok = False
            if ok: err += [f"{where}: {v}" for v in violations(pick, by_id)]
            cls = _classes(s, where, err)
            out.append({"id": sid, "label": s.get("label") or sid, "pick": {x["id"]: pick[x["id"]] for x in chosen if x["id"] in pick}, "classes": cls,
                        "subtract_savings": bool(s.get("subtract_savings")) and "refactoring" in cls, "auto": False})
        if len({s["label"] for s in out}) < len(out): err.append("run.json scenarios: labels must be unique (the totals sum by label)")
        return out
    combos = [dict(zip([x["id"] for x in chosen], c)) for c in itertools.product(*[[o["id"] for o in x["options"]] for x in chosen])]
    valid = [p for p in combos if not violations(p, by_id)]
    if not valid: err.append("no scenario: every combination of one option per system breaks a requires / excludes rule"); return []
    used = {(t, o) for p in valid for t, o in p.items()}
    warn += [f"{option_key(x['id'], o['id'])} is in no scenario (requires / excludes)" for x in chosen for o in x["options"] if (x["id"], o["id"]) not in used]
    cap = max_auto(cfg)
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1: err.append(f"estimation.scenarios_max_auto '{cap}' is a whole number of at least 1")
    elif len(valid) > cap: err.append(f"{len(valid)} scenarios from one option per system (above estimation.scenarios_max_auto {cap}) - list the scenarios to compare in run.json scenarios with pick, or raise the cap")
    lab = {(x["id"], o["id"]): o["label"] for x in chosen for o in x["options"]}; out, ids = [], set()
    for p in valid:
        sid = stem = "-".join(p[x["id"]] for x in multi) or "solution"; n = 2
        while sid in ids: sid = f"{stem}-{n}"; n += 1
        ids.add(sid)
        out.append({"id": sid, "label": " + ".join(lab[(x["id"], p[x["id"]])] for x in multi) or sid, "pick": p, "classes": list(ROW_CLASSES), "subtract_savings": False, "auto": True})
    return out


def parse_systems(cfg, options=None):
    """-> (model, errors, warnings); model = {"declared", "systems": [{id, label, kind, estimated_by, owner_label, depends_on, landscape_ids,
    options: [option dict as common.options], requires / excludes: {option id: [<system>:<option>]}, implicit[, alias]}], "scenarios":
    [{id, label, pick: {system: option}, classes, subtract_savings, auto} (+ option, option_label without `systems`)]}.
    options = common.options(cfg) when not given (only read without `systems`)"""
    err, warn = [], []
    if cfg.get("systems") is None:
        if options is None:
            from common import options as _opts
            options = _opts(cfg)
        syss, sc = _compat(cfg, options, err, warn)
    else:
        syss = _declared(cfg, err, warn); sc = _system_scenarios(cfg, syss, err, warn) if not err else []
    return {"declared": cfg.get("systems") is not None, "systems": syss, "scenarios": sc}, err, warn


def system_model(cfg, options=None):
    """the normalised systems model (parse_systems), refused on a configuration error (`dbcx build_excel --check` lists them all)"""
    m, err, _ = parse_systems(cfg, options)
    if err: raise SystemExit("run.json systems / scenarios:\n  " + "\n  ".join(err))
    return m


# ------------------------------------------------------------------ inputs: group keys, interface groups, the landscape
MAPPING_KEYS = ("sheet", "group", "id_prefix", "header_row", "columns", "extra_columns", "hide_columns")   # hide_columns: passthrough columns shown in the full edition only
GROUP_KEYS = ("kind", "estimate", "systems_field", "rollup_to_field", "passthrough")   # read by `dbcx requirements_to_json` (engine)
GROUP_KINDS = ("requirements", "interfaces")
ENDS = ("from", "to", "via")
LANDSCAPE_PATH = os.path.join("state", "landscape.json")
LANDSCAPE_FIELDS = ("id", "name", "kind", "description", "owner", "aliases")


def norm_name(s): return re.sub(r"\s+", " ", str(s or "")).strip().casefold()


def is_reference(req):
    """a row of a group with `estimate: false`: context for the analysts, never an estimation row"""
    return (req or {}).get("estimate") is False


def reference_ids(reqs): return {r["id"] for r in reqs or [] if is_reference(r)}


def _column_spec(v): return (isinstance(v, int) and not isinstance(v, bool) and v > 0) or (isinstance(v, str) and bool(v.strip()) and not v.startswith("<<"))


def mapping_errors(mapping):
    """-> (errors, warnings) of the group keys of requirements_mapping.json (sheet entries)"""
    err, warn = [], []
    for i, sh in enumerate((mapping or {}).get("sheets") or [], 1):
        if not isinstance(sh, dict) or str(sh.get("sheet") or "").startswith("<<"): continue
        where = f"requirements_mapping.json sheet '{sh.get('sheet')}'"; cols = sh.get("columns") or {}
        unknown = [k for k in sh if k not in MAPPING_KEYS + GROUP_KEYS and not str(k).startswith("_")]
        if unknown: warn.append(f"{where}: unknown key(s) {', '.join(unknown)} - ignored (group keys: {', '.join(GROUP_KEYS)})")
        kind = sh.get("kind", "requirements")
        if kind not in GROUP_KINDS: err.append(f"{where}: kind '{kind}' (requirements | interfaces)")
        for k in ("estimate", "passthrough"):
            if k in sh and not isinstance(sh[k], bool): err.append(f"{where}: {k} is true or false, not {sh[k]!r}")
        for k in ("systems_field", "rollup_to_field"):
            if k in sh and not _column_spec(sh[k]): err.append(f"{where}: {k} names one column (header text, column letter or 1-based index), not {sh[k]!r}")
        if kind == "interfaces":
            miss = [e for e in ("from", "to") if not _column_spec(cols.get(e))]
            if miss: err.append(f"{where}: an interface group maps the columns {' and '.join(miss)} (columns.from / columns.to, optionally columns.via)")
        elif any(_column_spec(cols.get(e)) for e in ENDS): warn.append(f"{where}: columns from / to / via are interface ends only on a group with kind: interfaces - here they are plain fields")
        if sh.get("passthrough") is True and not _column_spec(cols.get("id")): err.append(passthrough_id_error(sh.get("sheet")))
    return err, warn


def passthrough_id_error(sheet):
    return f"passthrough sheet '{sheet}' has no id column (columns.id): generated ids do not identify the client's rows - map the client's id column"


def load_landscape(run_dir):
    return load(run_dir, LANDSCAPE_PATH, None)


def normalise_landscape(data):
    """-> (landscape, errors, warnings); landscape = {"systems": [{id, name, kind, description, owner, aliases}], "interfaces": [{id, from, to, via}]}
    (systems: id required and unique, name defaults to the id; a name or alias of two systems is ambiguous and matches neither)"""
    err, warn = [], []; systems, seen = [], set()
    for i, s in enumerate((data or {}).get("systems") or [], 1):
        s = s if isinstance(s, dict) else {}; sid = str(s.get("id") if s.get("id") is not None else "").strip()
        if not sid: err.append(f"landscape system {i}: no id"); continue
        if sid in seen: err.append(f"landscape system id '{sid}' appears twice"); continue
        seen.add(sid); al = s.get("aliases") or []
        al = [x.strip() for x in (re.split(r"[;|\n]", al) if isinstance(al, str) else [str(a) for a in al]) if x and x.strip()]
        systems.append({"id": sid, "name": str(s.get("name") or "").strip() or sid, "kind": str(s.get("kind") or "").strip(),
                        "description": str(s.get("description") or "").strip(), "owner": str(s.get("owner") or "").strip(), "aliases": al})
    names = {}
    for s in systems:
        for n in {norm_name(x) for x in [s["id"], s["name"]] + s["aliases"]}: names.setdefault(n, []).append(s["id"])
    amb = sorted(f"'{n}' ({', '.join(v)})" for n, v in names.items() if len(v) > 1)
    if amb: warn.append(f"landscape names / aliases of more than one system match none of them: {'; '.join(amb)}")
    ifs = []
    for j, f in enumerate((data or {}).get("interfaces") or [], 1):
        f = f if isinstance(f, dict) else {}
        ifs.append({"id": str(f.get("id") or f"LIF-{j:03d}"), **{e: str(f.get(e) or "").strip() for e in ENDS}})
    return {"systems": systems, "interfaces": ifs}, err, warn


def name_index(model, land):
    """{normalised name: (run system id | None, landscape id | None)}: the landscape's ids, names and aliases (a landscape id resolves to the
    run system that lists it in landscape_ids), the landscape_ids of the run systems, and the run systems' ids and labels (they win; the
    landscape id stays only when it is one of that system's landscape_ids)"""
    owner = {lid: s["id"] for s in model.get("systems") or [] for lid in s.get("landscape_ids") or []}; idx, amb = {}, set()
    for ls in (land or {}).get("systems") or []:
        for n in {norm_name(x) for x in [ls["id"], ls.get("name")] + list(ls.get("aliases") or []) if x}:
            if n in idx and idx[n][1] != ls["id"]: amb.add(n)
            idx.setdefault(n, (owner.get(ls["id"]), ls["id"]))
    for n in amb: idx.pop(n, None)
    for lid, sid in owner.items(): idx.setdefault(norm_name(lid), (sid, lid))
    for s in model.get("systems") or []:
        for n in {norm_name(s["id"]), norm_name(s["label"])}:
            prev = idx.get(n); idx[n] = (s["id"], prev[1] if prev and prev[0] == s["id"] else None)
    return idx


def system_tokens(named, idx):
    """the names of a systems_field cell: split at , ; and line breaks (engine), then at / - the longest run of /-parts that is a known name
    stays one name ("SAP S/4HANA / Integration Suite" -> SAP S/4HANA, Integration Suite)"""
    out = []
    for t in named or []:
        parts, i = t.split("/"), 0
        while i < len(parts):
            j = next((j for j in range(len(parts), i + 1, -1) if norm_name("/".join(parts[i:j])) in idx), i + 1)
            if "/".join(parts[i:j]).strip(): out.append("/".join(parts[i:j]).strip())
            i = j
    return out


def enrich(doc, model, land):
    """the pre-fill of the rows that carry input fields (state/requirements.json, in place): systems_field rows get `systems_prefill`
    [run system ids]; interface rows (kind interface) get `ends` [{end, name, landscape_id, system}] and `prefill` [{system, end}] for the
    ends that map to a run system (estimated or external). Rows without these fields are left untouched. -> unresolved
    {"systems": {name: [row ids]}, "outside": {name: [row id end]}, "unknown": {name: [row id end]}}"""
    idx = name_index(model, land); un = {"systems": {}, "outside": {}, "unknown": {}}
    for r in (doc or {}).get("requirements") or []:
        if "systems_named" in r:
            got = []
            for t in system_tokens(r["systems_named"], idx):
                sid = idx.get(norm_name(t), (None, None))[0]
                if sid:
                    if sid not in got: got.append(sid)
                else: un["systems"].setdefault(t, []).append(r["id"])
            r["systems_prefill"] = got
        if r.get("kind") == "interface":
            ends, pre = [], []
            for e in ENDS:
                v = str(r.get(e) or "").strip()
                if not v: continue
                sid, lid = idx.get(norm_name(v), (None, None))
                ends.append({"end": e, "name": v, "landscape_id": lid, "system": sid})
                if sid: pre.append({"system": sid, "end": e})
                else: un["outside" if lid else "unknown"].setdefault(v, []).append(f"{r['id']} {e}")
            r["ends"] = ends; r["prefill"] = pre
    return un


def _listing(d): return "; ".join(f"{k} ({', '.join(v[:6])}{' ...' if len(v) > 6 else ''})" for k, v in sorted(d.items()))


def input_check(cfg, model=None):
    """-> (errors, warnings) of the inputs (`dbcx build_excel --check`, `dbcx discover`): the group keys of requirements_mapping.json, the
    landscape (state/landscape.json), and in state/requirements.json the roll-up targets, the systems_field names and interface ends that
    resolve to no system of the run, a passthrough sheet without an id column and a pre-fill older than run.json systems / the landscape"""
    import copy
    run = cfg.get("_run_dir"); err, warn = [], []
    if not run: return err, warn
    if model is None: model = parse_systems(cfg)[0]
    mp = load(run, ((cfg.get("requirements") or {}).get("mapping") or "requirements_mapping.json"), None)
    if mp: e, w = mapping_errors(mp); err += e; warn += w
    raw = load_landscape(run); land = None
    if raw is not None:
        land, e, w = normalise_landscape(raw); err += [f"{LANDSCAPE_PATH}: {x}" for x in e]; warn += [f"{LANDSCAPE_PATH}: {x}" for x in w]
        known = {s["id"] for s in land["systems"]}
        warn += [f"system {s['id']}: landscape id '{lid}' is not in the landscape" for s in model.get("systems") or [] for lid in s.get("landscape_ids") or [] if lid not in known]
    doc = load(run, os.path.join("state", "requirements.json"), None)
    if not doc: return list(dict.fromkeys(err)), list(dict.fromkeys(warn))
    reqs = doc.get("requirements") or []; by = {r["id"]: r for r in reqs}
    for g, k in (doc.get("group_keys") or {}).items():
        if k.get("passthrough") is True and not k.get("id_column"): err.append(passthrough_id_error(k.get("sheet")))
        if k.get("missing_columns"): warn.append(f"group {g}: column(s) {', '.join(map(str, k['missing_columns']))} not found in sheet '{k.get('sheet')}' - nothing read from them")
    pt = {r["id"] for r in reqs if (doc.get("group_keys") or {}).get(r.get("group"), {}).get("passthrough") is True}
    for r in reqs:
        t = r.get("rollup_to")
        if not t or t == r["id"]: continue
        if t not in by: err.append(f"{r['id']}: rolls up to '{t}', no row of the requirement list")
        elif (by[t].get("rollup_to") or t) != t: err.append(f"{r['id']}: rolls up to {t}, which rolls up to {by[t]['rollup_to']} - one level only")
        elif t not in pt: warn.append(f"{r['id']}: rolls up to {t}, a row of no passthrough sheet - the roll-up has no client sheet to show in")
    probe = copy.deepcopy(doc); un = enrich(probe, model, land)
    if un["systems"]: warn.append(f"systems_field names no system of the run: {_listing(un['systems'])}")
    if un["outside"]: warn.append(f"interface ends at landscape systems not in the run (recorded for the architect): {_listing(un['outside'])}")
    if un["unknown"]: warn.append(f"interface ends neither a system of the run nor of the landscape: {_listing(un['unknown'])}")
    keys = ("systems_prefill", "ends", "prefill")
    if any({k: a.get(k) for k in keys} != {k: b.get(k) for k in keys} for a, b in zip(reqs, probe["requirements"])):
        warn.append("the pre-fill in state/requirements.json is older than run.json systems or the landscape - re-run dbcx requirements_to_json (or dbcx landscape_import)")
    return list(dict.fromkeys(err)), list(dict.fromkeys(warn))


# ------------------------------------------------------------------ scope step: pre-fill + triage + overrides -> state/impact.json
IMPACT_PATH = os.path.join("state", "impact.json")
PLAN_PATH = os.path.join("work", "impact-plan.json")
TRIAGE_SCOPE, TRIAGE_DIR, TRIAGE_KIND = "TRIAGE", os.path.join("analysis", "triage"), "triage"
NONE = "none"   # the triage's system for a row that touches no system of the run
CONTEXT_BUDGET = 100000   # default of unit.context_budget (estimated tokens an agent's working set may take; the triage rows take at most half)


def scope_step(cfg):
    """the scope step runs in system mode only (run.json `systems`); a run without it skips the step entirely (the path without systems)"""
    return cfg.get("systems") is not None


def estimating_rows(cfg, reqs=None):
    """the rows the scope step covers: every row of state/requirements.json that is no reference row (estimate: false) and not decided away"""
    reqs = requirements(cfg.get("_run_dir")) if reqs is None else reqs; gone = excluded(cfg)
    return [r for r in reqs if not is_reference(r) and r["id"] not in gone]


def prefill(req, model):
    """{system id: [basis]} - the deterministic pre-fill of one row: systems_field (`systems_prefill`), interface ends (`prefill`
    [{system, end}]: interface from / to / via) and the row classes (a TM / RF row: the systems with an option its applies_to names,
    else the systems with a brownfield option - the code analysis describes today's system)"""
    out = {}
    for sid in req.get("systems_prefill") or []: out.setdefault(sid, []).append("systems_field")
    for p in req.get("prefill") or []: out.setdefault(p["system"], []).append(f"interface {p['end']}")
    cls = row_class(req)
    if cls != "client":
        at = set(req.get("applies_to") or []); syss = [s for s in model["systems"] if s["options"]]
        hit = [s["id"] for s in syss if at & {o["id"] for o in s["options"]}] or [s["id"] for s in syss if any((o.get("start") or "greenfield") == "brownfield" for o in s["options"])]
        for sid in hit: out.setdefault(sid, []).append(cls)
    known = {s["id"] for s in model["systems"]}
    return {k: v for k, v in out.items() if k in known}


def row_tokens(req):
    """estimated tokens of one row in the triage brief (characters / 4 of the fields the brief shows)"""
    keys = ("id", "group", "epic", "title", "description", "acceptance_criteria", "exclusions", "phase", "systems_named", "from", "to", "via", "rollup_to")
    return 20 + len(json.dumps({k: req.get(k) for k in keys if req.get(k)}, ensure_ascii=False)) // 4


def triage_parts(cfg, rows):
    """the triage chunks: as few as the context budget allows (unit.context_budget; the rows take at most half of it). Rows in list order,
    a (group, epic) block kept together where it fits; only a block larger than the budget is split. -> [{"scope", "rows", "tokens"}]"""
    budget = int(((cfg.get("unit") or {}).get("context_budget")) or CONTEXT_BUDGET) // 2
    blocks = []
    for r in rows:
        k = (r.get("group") or "", r.get("epic") or "")
        if blocks and blocks[-1][0] == k: blocks[-1][1].append(r)
        else: blocks.append((k, [r]))
    parts, cur, tok = [], [], 0
    for _, rs in blocks:
        t = sum(row_tokens(r) for r in rs)
        if cur and tok + t > budget: parts.append((cur, tok)); cur, tok = [], 0
        if t > budget:   # an oversize block is split
            for r in rs:
                if cur and tok + row_tokens(r) > budget: parts.append((cur, tok)); cur, tok = [], 0
                cur.append(r); tok += row_tokens(r)
            continue
        cur += rs; tok += t
    if cur: parts.append((cur, tok))
    one = len(parts) == 1
    return [{"scope": TRIAGE_SCOPE if one else f"{TRIAGE_SCOPE}-{i}", "rows": [r["id"] for r in rs], "tokens": tk} for i, (rs, tk) in enumerate(parts, 1)]


def _yes(v): return str(v).strip().lower() in ("yes", "true", "ja", "1", "y")


def triage_rows(run_dir, plan):
    """the converted triage files of every part -> [{row, system, affected, impact, reason, claims, scope}]"""
    out = []
    for p in (plan or {}).get("parts") or []:
        d = load(run_dir, os.path.join(TRIAGE_DIR, f"{p['scope']}.json"), None) or {}
        for x in d.get("impacts") or []:
            out.append({"row": str(x.get("row_id") or "").strip(), "system": str(x.get("system") or "").strip(), "affected": _yes(x.get("affected", "yes")),
                        "impact": (x.get("impact") or "").strip(), "reason": (x.get("reason") or "").strip(), "claims": list(x.get("claimed_by") or []), "scope": p["scope"]})
    return out


def disputed_claims(run_dir, scopes, threshold):
    """claim ids of the triage parts that failed the latest scored round (a score below the threshold or a `false` verdict of any critic) or
    that a critic routed as a dispute (scoring.dispute_routes) - their impacts are `disputed` until the rework is applied"""
    out = set()
    for sc in scopes:
        gd = os.path.join(run_dir or ".", "analysis", "gauntlet", sc)
        rs = sorted(int(f[5:-12]) for f in (os.listdir(gd) if os.path.isdir(gd) else []) if re.fullmatch(r"round\d+-result\.json", f))
        if not rs: continue
        for f in os.listdir(gd):
            if not re.fullmatch(rf"round{rs[-1]}-[\w-]+\.json", f) or f.endswith("-result.json"): continue
            d = load(run_dir, os.path.join(gd, f), {}) or {}
            for x in d.get("scores") or []:
                s = x.get("score")
                if x.get("verdict") == "false" or (isinstance(s, (int, float)) and s < threshold): out.add(x.get("claim_id"))
            out |= {x.get("claim_id") for x in d.get("disputes") or []}
    return {x for x in out if x}


def merge_impact(cfg, model, rows, triage, overrides, disputed=()):
    """the effective impact matrix -> (cells [{row, system, affected, source, origin, basis, impact, reason, claims, status, override}],
    none {row id: {reason, source, claims}}). Pre-fill first (source prefill), then the triage (impact text, reason, claims; a system it adds:
    source triage; `affected no` removes a pre-fill with its reason; `none`), then the dashboard overrides in their order (source override,
    status overridden). A row left without an affected system by an override becomes `none` with the override's reason. status: applied |
    overridden | disputed (a claim of the cell failed the triage gauntlet's latest round)"""
    by = {}; none = {}; order = []
    for r in rows:
        order.append(r["id"])
        for sid, basis in prefill(r, model).items():
            by[(r["id"], sid)] = {"row": r["id"], "system": sid, "affected": True, "source": "prefill", "origin": "prefill", "basis": basis, "impact": "", "reason": "", "claims": [], "status": "applied"}
    ids = set(order)
    for t in triage:
        if t["row"] not in ids: continue
        if t["system"] == NONE: none[t["row"]] = {"reason": t["reason"], "source": "triage", "claims": t["claims"]}; continue
        c = by.get((t["row"], t["system"]))
        if c is None: c = by[(t["row"], t["system"])] = {"row": t["row"], "system": t["system"], "affected": t["affected"], "source": "triage", "origin": "triage", "basis": [], "impact": "", "reason": "", "claims": [], "status": "applied"}
        c.update(affected=t["affected"], impact=t["impact"] if t["affected"] else "", reason=t["reason"], claims=t["claims"])
    for ov in overrides or []:
        k = (ov["row"], ov["system"])
        if ov["row"] not in ids: continue
        c = by.get(k) or {"row": ov["row"], "system": ov["system"], "affected": False, "origin": "override", "basis": [], "impact": "", "reason": "", "claims": []}
        if ov["action"] == "remove": c.update(affected=False, impact="", reason=ov.get("reason") or c.get("reason", ""))
        else: c.update(affected=True, impact=ov.get("impact") or c.get("impact", ""), reason=ov.get("reason") or c.get("reason", ""))
        c.update(source="override", status="overridden", override=ov["id"]); by[k] = c
        if c["affected"]: none.pop(ov["row"], None)
        elif not any(x["affected"] for (rr, _), x in by.items() if rr == ov["row"]): none[ov["row"]] = {"reason": ov.get("reason", ""), "source": "override", "claims": []}
    for c in by.values():
        if c["status"] == "applied" and set(c["claims"]) & set(disputed): c["status"] = "disputed"
    sys_order = [s["id"] for s in model["systems"]]
    cells = sorted(by.values(), key=lambda c: (order.index(c["row"]), sys_order.index(c["system"]) if c["system"] in sys_order else 99, c["system"]))
    return cells, {k: none[k] for k in order if k in none}


def impact_errors(doc, cfg, model=None, rows=None):
    """the rules of state/impact.json (`dbcx impact apply`, `dbcx build_excel --check`): every estimating row covered (an affected system or
    `none` with a reason), no unknown system, an impact text for every affected system, a reason for every removal and every `none`"""
    model = model or parse_systems(cfg)[0]; rows = estimating_rows(cfg) if rows is None else rows
    known = {s["id"] for s in model["systems"]}; err = []; cells = (doc or {}).get("cells") or []; none = (doc or {}).get("none") or {}
    aff = {}
    for c in cells:
        w = f"{c.get('row')} x {c.get('system')}"
        if c.get("system") not in known: err.append(f"impact {w}: '{c.get('system')}' is no system of this run ({', '.join(sorted(known))})"); continue
        if c.get("affected"):
            aff.setdefault(c["row"], []).append(c["system"])
            if not (c.get("impact") or "").strip(): err.append(f"impact {w}: no impact text (what changes in that system, in customer language)")
        elif not (c.get("reason") or "").strip(): err.append(f"impact {w}: a removed system needs its reason")
    for rid, n in none.items():
        if aff.get(rid): err.append(f"impact {rid}: `none` and affected systems ({', '.join(aff[rid])})")
        if not (n.get("reason") or "").strip(): err.append(f"impact {rid}: `none` needs its reason")
    miss = [r["id"] for r in rows if r["id"] not in aff and r["id"] not in none]
    if miss: err.append(f"impact: {len(miss)} estimating row(s) without an affected system or `none`: {', '.join(miss[:20])}{' ...' if len(miss) > 20 else ''}")
    return err


def work_packages(doc):
    """{"<row>@<system>": impact text} of the affected cells (the key is the impact cell; the wave planner expands it per option: <row>@<system>:<option>[@<parent option>],
    work_package_list / parse_wp map between the two)"""
    return {f"{c['row']}@{c['system']}": c.get("impact", "") for c in (doc or {}).get("cells") or [] if c.get("affected")}


def wp_changes(old, new):
    """[(work package, change)] between two impact matrices: new (a system added to a row) | withdrawn (removed) | re-brief (impact text changed)"""
    a, b = work_packages(old), work_packages(new)
    return [(k, "new") for k in b if k not in a] + [(k, "withdrawn") for k in a if k not in b] + [(k, "re-brief") for k in b if k in a and a[k] != b[k]]


def net_changes(changes):
    """the open changes per work package, folded in order: new + re-brief = new; new + withdrawn = nothing; withdrawn + new = re-brief"""
    out = {}
    for c in changes:
        if c.get("picked_up"): continue
        k, v = c["work_package"], c["change"]; p = out.get(k)
        if p == "new" and v == "re-brief": continue
        if p == "new" and v == "withdrawn": out.pop(k); continue
        if p == "withdrawn" and v == "new": out[k] = "re-brief"; continue
        out[k] = v
    return out


# ------------------------------------------------------------------ work packages, chunks and waves
SCOPES_FILE = os.path.join("state", "scopes.json")
WAVE_RULE = "after"   # engine plan_waves rule written into scopes.json in system mode: a scope's wave comes after every scope it depends on
ACTIVE, WITHDRAWN, SUPERSEDED = "active", "withdrawn", "superseded"
ORIGIN_ARCHITECT = "architect"   # a package an architect decision put into a cell the impact matrix does not have
PASSED_STATES = ("final", "passed", "passed-rework-ordered")


def wp_key(row, system, option, parent=None):
    """the work package key `<row>@<system>:<option>[@<parent option>]` (the impact cell `<row>@<system>` plus the option)"""
    return f"{row}@{system}:{option}" + (f"@{parent}" if parent else "")


def parse_wp(key):
    """`<row>@<system>:<option>[@<parent option>]` -> {row, system, option, parent, cell}"""
    row, _, rest = str(key).partition("@"); system, _, rest = rest.partition(":"); option, _, parent = rest.partition("@")
    return {"row": row, "system": system, "option": option, "parent": parent or None, "cell": f"{row}@{system}"}


def option_value(option, parent=None):
    """what the analyst writes into the `option` column of a work package's estimation row: the option id, for a dependent system
    `<option>@<parent option>` - so the row id `<row>@<option>[@<parent option>]` names the work package inside its chunk"""
    return option + (f"@{parent}" if parent else "")


def system_mode(cfg): return cfg.get("systems") is not None


def impact_basis(cfg, model, rows):
    """(cells, basis) the work packages come from: the applied state/impact.json, else the deterministic pre-fill alone (discover never
    waits for the scope step; the triage result reaches the plan through `dbcx discover --pickup`)"""
    doc = load(cfg.get("_run_dir"), IMPACT_PATH, None)
    if doc and doc.get("cells") is not None: return doc["cells"], {"source": IMPACT_PATH.replace(os.sep, "/"), "applied_at": doc.get("applied_at")}
    cells, _ = merge_impact(cfg, model, rows, [], [])
    return cells, {"source": "pre-fill", "applied_at": None}


def work_package_list(model, cells, rows):
    """the work packages of the affected impact cells: row x system x option of every agent-estimated system (the row applies
    to the option, the option is in a scenario); a dependent system's package carries the parent option for every parent option that is in
    a scenario with it, when the row touches the parent system too - otherwise it carries none (its effort does not differ per parent
    option). Order: systems, options, rows as declared / listed. -> [{key, row, system, option, parent, value, impact}]"""
    sysd = {s["id"]: s for s in model["systems"]}; aff = {(c["row"], c["system"]): c for c in cells or [] if c.get("affected")}
    picks = [s.get("pick") or {} for s in model.get("scenarios") or []]; out = []
    for s in model["systems"]:
        if s.get("estimated_by") != "agents" or not s.get("options"): continue
        par = sysd.get(s.get("depends_on")) if s.get("depends_on") else None
        for o in s["options"]:
            if not any(p.get(s["id"]) == o["id"] for p in picks): continue
            for r in rows:
                c = aff.get((r["id"], s["id"]))
                if not c or not applies(r, o): continue
                pos = [po["id"] for po in (par or {}).get("options") or [] if (r["id"], par["id"]) in aff and applies(r, po)
                       and any(p.get(s["id"]) == o["id"] and p.get(par["id"]) == po["id"] for p in picks)]
                for po in pos or [None]:
                    out.append({"key": wp_key(r["id"], s["id"], o["id"], po), "row": r["id"], "system": s["id"], "option": o["id"], "parent": po,
                                "value": option_value(o["id"], po), "impact": c.get("impact") or ""})
    return out


def rollup_links(reqs, cfg=None):
    """{target id: [ids of the estimating rows that roll up to it]} - the rows linked by roll-up (`rollup_to`; a row's own id is no link)"""
    gone = excluded(cfg) if cfg else set(); out = {}
    for r in reqs or []:
        t = r.get("rollup_to")
        if t and t != r["id"] and not is_reference(r) and r["id"] not in gone: out.setdefault(t, []).append(r["id"])
    return out


def context_ids(rid, by, links):
    """the rows an analyst of `rid` sees as context: the reference rows it names (references, its roll-up target), its
    roll-up target and the rows that roll up to the same target, and the rows that roll up to it"""
    r = by.get(rid) or {}; out = []
    t = r.get("rollup_to") if r.get("rollup_to") not in (None, rid) else None
    if t: out += [t] + [x for x in links.get(t, []) if x != rid]
    out += links.get(rid, [])
    out += [x for x in r.get("references") or [] if x in by and is_reference(by[x])]
    return [x for x in dict.fromkeys(out) if x in by and x != rid]


def wp_tokens(w):
    """estimated tokens of one work package in a brief beyond its row (impact text, key, the parent approach line)"""
    return 15 + len(w.get("impact") or "") // 4 + (40 if w.get("parent") else 0)


def chunk_costs(cfg, rows, wps):
    """{row id: estimated tokens} of the rows of one system option in an analyst brief: the row, its work packages, its context rows
    (reference / roll-up rows, characters / 4) and its BASELINE handover line"""
    by = {r["id"]: r for r in requirements(cfg.get("_run_dir"))} or {r["id"]: r for r in rows}; by.update({r["id"]: r for r in rows})
    links = rollup_links(by.values(), cfg); per = {}
    for w in wps: per.setdefault(w["row"], []).append(w)
    cov = {c.get("req_id"): c for c in handover(cfg.get("_run_dir"), "requirements-coverage").get("coverage") or [] if isinstance(c, dict)}
    return {rid: row_tokens(by[rid]) + sum(wp_tokens(w) for w in ws) + sum(row_tokens(by[x]) for x in context_ids(rid, by, links))
            + (len(json.dumps(cov[rid], ensure_ascii=False)) // 4 if rid in cov else 0) for rid, ws in per.items()}


def pack_rows(rows, cost, budget):
    """as few chunks as the budget allows: (group, epic) blocks in list order, each into the first chunk with room (first fit) - several small
    epics share a chunk, an epic stays whole where it fits; only a block larger than the budget is split (row by row, in order).
    -> [[row ids]] (each chunk's rows in list order)"""
    order = {r["id"]: i for i, r in enumerate(rows)}; blocks = []
    for r in rows:
        k = (r.get("group") or "", r.get("epic") or "")
        if blocks and blocks[-1][0] == k: blocks[-1][1].append(r["id"])
        else: blocks.append((k, [r["id"]]))
    bins = []
    for _, ids in blocks:
        t = sum(cost[i] for i in ids)
        if t > budget:
            cur = None
            for i in ids:
                if cur is None or cur[1] + cost[i] > budget: cur = [[], 0]; bins.append(cur)
                cur[0].append(i); cur[1] += cost[i]
            continue
        b = next((b for b in bins if b[1] + t <= budget), None)
        if b is None: b = [[], 0]; bins.append(b)
        b[0] += ids; b[1] += t
    return [sorted(b[0], key=order.get) for b in bins]


def budget_of(cfg):
    """the share of unit.context_budget the rows of a chunk may take (half; the other half is the brief's rules, notes and the agent's work)"""
    return int(((cfg.get("unit") or {}).get("context_budget")) or CONTEXT_BUDGET) // 2


def chunk_prefix(system, option):
    """neutral chunk names (never client text): <system>-NN for a system with one option, <system>-<option>-NN otherwise"""
    return f"{system['id']}-" if len(system["options"]) == 1 else f"{system['id']}-{option['id']}-"


def plan_system_chunks(cfg, model, rows, wps, taken=(), light_c=8, followup=None):
    """the chunks of the work packages: per system option (declared order), bin-packed under the context budget (pack_rows). taken = chunk names
    already in use (numbering continues). -> {name: scopes.json entry}; depends_on = every chunk of the parent system among `parents`
    (filled by the caller), meta.work_packages = the packages with status active"""
    budget = budget_of(cfg); by = {r["id"]: r for r in rows}; out = {}
    for s in model["systems"]:
        for o in s.get("options") or []:
            mine = [w for w in wps if w["system"] == s["id"] and w["option"] == o["id"]]
            if not mine: continue
            rs = [r for r in rows if any(w["row"] == r["id"] for w in mine)]; cost = chunk_costs(cfg, rs, mine)
            pre = chunk_prefix(s, o); n = max([int(x[len(pre):]) for x in taken if x.startswith(pre) and x[len(pre):].isdigit()] + [0])
            for ids in pack_rows(rs, cost, budget):
                n += 1; name = f"{pre}{n:02d}"; ws = [dict(w, status=ACTIVE) for w in mine if w["row"] in ids]
                epics = list(dict.fromkeys((by[i].get("epic") or "").strip() or "unassigned" for i in ids))
                groups = sorted({(by[i].get("group") or "").strip() for i in ids if by[i].get("group")}); rel = sorted({(by[i].get("phase") or "").strip() for i in ids if by[i].get("phase")})
                light = len(ws) <= light_c
                out[name] = {"group": s["id"], "depends_on": [], "size": len(ws), "light": light,
                             "light_reason": f"{len(ws)} work packages <= {light_c} (light chunk: essentials only, light gauntlet)" if light else "", "skip": False,
                             "system": s["id"], "option": o["id"], "option_key": option_key(s["id"], o["id"]), "pack": o.get("pack") or "", "parent_system": s.get("depends_on"),
                             "tokens": sum(cost[i] for i in ids), **({"followup": followup} if followup else {}),
                             "meta": {"SYSTEM": f"{s['label']} ({s['id']})" + (f", estimated per option of {s['depends_on']}" if s.get("depends_on") else ""),
                                      "OPTION": f"{o['label']} ({option_key(s['id'], o['id'])}, {o.get('start') or 'greenfield'}, pack {o.get('pack') or ''})",
                                      "EPICS": " + ".join(epics), "WORK PACKAGES": len(ws), "REQUIREMENT COUNT": len(ids), "GROUPS": ", ".join(groups) or "-",
                                      "RELEASES": ", ".join(rel) or "-", "FIRST/LAST ID": f"{ids[0]} ... {ids[-1]}", "req_ids": ids, "work_packages": ws}}
    return out


def chunk_wps(entry, status=ACTIVE):
    """the work packages of a chunk entry (state/scopes.json) with that status (None = all)"""
    return [w for w in ((entry or {}).get("meta") or {}).get("work_packages") or [] if status is None or w.get("status", ACTIVE) == status]


def planned(scopes):
    """{work package key: (chunk, entry)} of the active packages of state/scopes.json (system mode)"""
    return {w["key"]: (n, w) for n, e in ((scopes or {}).get("scopes") or {}).items() for w in chunk_wps(e)}


def planned_cells(scopes):
    """the impact cells the planned packages rest on (the baseline of the first work-package change after discover)"""
    seen = {}
    for _, w in planned(scopes).values(): seen.setdefault((w["row"], w["system"]), w.get("impact") or "")
    return {"cells": [{"row": r, "system": s, "affected": True, "impact": i} for (r, s), i in seen.items()]}


def levels(scopes):
    """{chunk: level} as plan_waves' rule `after` computes it (max of the scope's own `level` and 1 + the level of each dependency)"""
    sc = (scopes or {}).get("scopes") or {}; out = {}
    def lv(k, stack=()):
        if k in out: return out[k]
        if k in stack: return 0
        x = max([int(sc[k].get("level") or 0)] + [lv(d, stack + (k,)) + 1 for d in sc[k].get("depends_on") or [] if d in sc]); out[k] = x; return x
    for k in sc: lv(k)
    return out


def started(run_dir, name, status=None):
    """has a chunk's analyst begun (its analysis exists, or STATUS moved it past `open`)?"""
    st = ((status or load(run_dir, os.path.join("state", "STATUS.json"), {}) or {}).get("scopes") or {}).get(name) or {}
    return os.path.exists(os.path.join(run_dir or ".", "analysis", "scopes", f"{name}.json")) or st.get("status") not in (None, "open")


def wanted(cfg, model=None):
    """{work package key: wp} of the current impact matrix (state/impact.json, else the pre-fill)"""
    model = model or system_model(cfg); rows = estimating_rows(cfg); cells, _ = impact_basis(cfg, model, rows)
    return {w["key"]: w for w in work_package_list(model, cells, rows)}


def pending(cfg, model=None, scopes=None):
    """the work-package changes the next wave picks up: the packages of the current impact matrix against the planned ones ->
    {"new": [wp], "withdrawn": [(chunk, wp)], "re-brief": [(chunk, wp, new impact)]} (empty lists when nothing changed). A package the
    architect routed into a cell the matrix does not have (origin architect, ) is no matrix package: only an
    architect change withdraws it"""
    run = cfg.get("_run_dir"); scopes = scopes if scopes is not None else load(run, SCOPES_FILE, {}) or {}
    want = wanted(cfg, model); have = planned(scopes)
    return {"new": [w for k, w in want.items() if k not in have], "withdrawn": [(n, w) for k, (n, w) in have.items() if k not in want and w.get("origin") != ORIGIN_ARCHITECT],
            "re-brief": [(n, w, want[k]["impact"]) for k, (n, w) in have.items() if k in want and (want[k]["impact"] or "") != (w.get("impact") or "")]}


def dependent_packages(scopes, model, key):
    """the active packages that depend on a package: the same row in a system that depends on the package's system, with the package's
    option as parent option -> [(chunk, wp)] (direct dependents; the pickup's cascade walks the chain)"""
    p = parse_wp(key); deps = {s["id"] for s in model["systems"] if s.get("depends_on") == p["system"]}
    return [(n, w) for n, w in planned(scopes).values() if w["system"] in deps and w["row"] == p["row"] and w.get("parent") == p["option"]]


def parent_key(wp, model):
    """the package a dependent package rests on (`<row>@<parent system>:<parent option>`), None without a parent option"""
    s = next((x for x in model["systems"] if x["id"] == wp["system"]), {}) or {}
    return wp_key(wp["row"], s["depends_on"], wp["parent"]) if wp.get("parent") and s.get("depends_on") else None


def chunk_entry(cfg, scope):
    """the system-mode chunk of an analysis (state/scopes.json entry with `system`), else None"""
    e = ((load(cfg.get("_run_dir"), SCOPES_FILE, {}) or {}).get("scopes") or {}).get(scope)
    return e if e and e.get("system") else None


def location(scopes, key):
    """the chunk that holds a work package's live estimate (active), else None"""
    hit = planned(scopes).get(key); return hit[0] if hit else None


def parent_rows(cfg, scopes, wp, status=None):
    """the parent's estimate of the row for a dependent work package's parent option: (chunk, estimation row, passed) - the row of the parent
    system's package `<row>@<parent system>:<parent option>` in the chunk that holds it (its own row, no position); (chunk, None, passed) when
    the analysis has no such row yet, None when the parent has no package for it"""
    run = cfg.get("_run_dir"); e = (scopes.get("scopes") or {}).get(location(scopes, wp["key"]) or "") or {}
    par = e.get("parent_system")
    if not par or not wp.get("parent"): return None
    k = wp_key(wp["row"], par, wp["parent"]); ch = location(scopes, k)
    if not ch: return None
    st = ((status or load(run, os.path.join("state", "STATUS.json"), {}) or {}).get("scopes") or {}).get(ch) or {}
    ok = st.get("status") in PASSED_STATES or bool(st.get("passed"))
    d = load(run, os.path.join("analysis", "scopes", f"{ch}.json"), None) or {}
    row = next((r for r in d.get("estimation") or [] if r.get("req_id") == wp["row"] and r.get("option") == wp["parent"] and not str(r.get("position") or "").strip()), None)
    return ch, row, ok
