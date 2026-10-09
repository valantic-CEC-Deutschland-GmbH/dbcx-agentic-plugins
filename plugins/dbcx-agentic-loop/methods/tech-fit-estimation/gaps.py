"""Work-package fields, the derived 3-point range and the architect step of tech-fit-estimation - one definition for validate.py, briefing.py, tools/architect.py, panels.py, the wave planner and the workbook.

System mode only (run.json `systems`); a run without `systems` never reads this module's state.
  * analyst fields per work package (an estimation row without position): starting_point reuse | extend | new | clarify (greenfield = new),
    coverage standard | extension | gap; a gap carries gap_reason and optionally route_suggestion (a run system or a landscape id); its size is
    the reporting system's own share only. `standard` rests on a vendor reference (a PS-7-NNN reference row) - `downgrade` turns it into
    `extension` with confidence low (validate.py does it at the CHECK and reports it as a WARNING).
  * derived range (`pd_range`, `wp_range`): min / max = likely x the factor of the row's confidence from estimation.range_factors (method default
    RANGE_FACTORS, a run overrides it under the same key) - no estimation field of its own; the workbook renders it from the same key.
  * architect step (`open_gaps`, `merge_decisions`, `followups`, `followup_changes`): the gaps of the closed waves are batched (ARCHITECT-n, one
    batch per wave with gaps); the architect agent decides each gap - overrule | route-estimated | route-landscape | reduce-to-standard; a row
    that reaches the architect a second time gets a final decision (its follow-ups may not report a gap again - no third routing).
"""
import glob, hashlib, json, os, re
import tfe_model as TM

STARTING_POINTS = ("reuse", "extend", "new", "clarify")
COVERAGE = ("standard", "extension", "gap")
WP_FIELDS = ("starting_point", "coverage", "gap_reason", "route_suggestion")
DECISIONS = ("overrule", "route-estimated", "route-landscape", "reduce-to-standard")
CONFIDENCE = ("high", "medium", "low")
RANGE_FACTORS = {"high": {"min": 0.9, "max": 1.25}, "medium": {"min": 0.8, "max": 1.5}, "low": {"min": 0.7, "max": 2.0}}   # method default of estimation.range_factors
RANGE_FALLBACK = "low"   # a row without confidence (not in system mode, where validate wants one) gets the widest range
VENDOR_REF = re.compile(r"^PS-7-\d+$")
ARCH_PATH = os.path.join("state", "architect.json")
ARCH_PLAN = os.path.join("work", "architect-plan.json")
ARCH_SCOPE, ARCH_DIR, ARCH_KIND = "ARCHITECT", os.path.join("analysis", "architect"), "architect"
CLOSED = ("final", "failed-gauntlet", "skipped")


# ------------------------------------------------------------------ derived 3-point range
def range_factors(cfg):
    """{confidence: {"min": f, "max": f}} - estimation.range_factors (method default RANGE_FACTORS; a run overrides single values)"""
    raw = (cfg.get("estimation") or {}).get("range_factors") or {}; out = {}
    for k, d in RANGE_FACTORS.items():
        x = raw.get(k) if isinstance(raw.get(k), dict) else {}
        out[k] = {b: x.get(b, d[b]) for b in ("min", "max")}
    return out


def range_errors(cfg):
    """the --check rules of estimation.range_factors: high / medium / low only, numbers with 0 < min <= 1 <= max"""
    raw = (cfg.get("estimation") or {}).get("range_factors")
    if raw is None: return []
    if not isinstance(raw, dict): return ["estimation.range_factors maps high / medium / low to {min, max}"]
    err = [f"estimation.range_factors: '{k}' is no confidence (high | medium | low)" for k in raw if not str(k).startswith("_") and k not in CONFIDENCE]
    for k, x in range_factors(cfg).items():
        lo, hi = x["min"], x["max"]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lo, hi)): err.append(f"estimation.range_factors.{k}: min and max are numbers ({lo!r}, {hi!r})"); continue
        if not (0 < lo <= 1 <= hi): err.append(f"estimation.range_factors.{k}: 0 < min <= 1 <= max (min {lo:g}, max {hi:g})")
    return err


def pd_map(cfg):
    return {k: float(v) for k, v in ((cfg.get("estimation") or {}).get("tshirt_map") or {}).items()}


def pd_range(pd, confidence, cfg):
    """(min, likely, max) person days of one sized row: likely x the factors of its confidence (an unknown or empty confidence: RANGE_FALLBACK)"""
    f = range_factors(cfg).get(confidence if confidence in CONFIDENCE else RANGE_FALLBACK)
    return round(pd * f["min"], 2), round(pd, 2), round(pd * f["max"], 2)


def wp_range(rows, cfg):
    """the range of one work package: its requirement row (no position) and its estimation positions. A sized requirement row: its own range;
    with positions: the sums of the positions' ranges (a position without confidence takes the requirement row's) -> {min, likely, max}"""
    pd = pd_map(cfg); own = next((r for r in rows if not str(r.get("position") or "").strip()), {}) or {}
    pos = [r for r in rows if str(r.get("position") or "").strip()]
    parts = [(r.get("size"), r.get("confidence") or own.get("confidence")) for r in pos] if pos else [(own.get("size"), own.get("confidence"))]
    t = [pd_range(pd.get(s or "", 0.0), c, cfg) for s, c in parts]
    return {"min": round(sum(x[0] for x in t), 2), "likely": round(sum(x[1] for x in t), 2), "max": round(sum(x[2] for x in t), 2)}


# ------------------------------------------------------------------ work packages of an estimation row (system mode)
def scope_meta(run_dir, scope):
    """the chunk's entry in state/scopes.json (`dbcx discover`; system mode puts system / option at its top level)"""
    return ((TM.load(run_dir, os.path.join("state", "scopes.json"), {}) or {}).get("scopes") or {}).get(scope or "") or {}


def resolve(row, model, entry=None):
    """(system, option) dicts of an estimation row in system mode, or (None, None). the system-mode shape first: the chunk entry names system and option,
    the row's `option` is <option>[@<parent option>]; also accepted: a `system` field on the row, `option` written as <system>:<option>, or an
    option id that only one system has"""
    by = {s["id"]: s for s in model["systems"]}; entry = entry or {}; meta = entry.get("meta") or {}
    raw = str(row.get("option") or "").strip(); sid = str(row.get("system") or "").strip()
    if ":" in raw and not sid: sid, raw = raw.split(":", 1)
    oid = raw.split("@", 1)[0]
    sid = sid or str(entry.get("system") or meta.get("system") or ""); oid = oid or str(entry.get("option") or meta.get("option") or "")
    if sid:
        s = by.get(sid)
        return (s, next((o for o in s["options"] if o["id"] == oid), None)) if s else (None, None)
    hit = [(s, o) for s in model["systems"] for o in s["options"] if o["id"] == oid]
    return hit[0] if len(hit) == 1 else (None, None)


def cell_key(row_id, system): return f"{row_id}@{system}"
wp_key = cell_key   # the gap / decision key: the impact cell <row>@<system> (a decision covers every package of the cell that reported it)


def package_key(row_id, system, value):
    """the work-package key <row>@<system>:<option>[@<parent option>] (value = what the analyst writes into `option`)"""
    return f"{row_id}@{system}:{value}"


def option_value(row):
    """the row's option value <option>[@<parent option>] without a <system>: prefix"""
    v = str(row.get("option") or "").strip()
    return v.split(":", 1)[1] if ":" in v.split("@", 1)[0] else v


def vendor_refs(evidence): return [x for x in evidence or [] if VENDOR_REF.match(str(x).strip())]


def downgrade(row):
    """coverage standard without a vendor reference -> extension with confidence low (in place); True when it changed the row"""
    if row.get("coverage") != "standard" or vendor_refs(row.get("evidence")): return False
    row["coverage"] = "extension"; row["confidence"] = "low"; return True


# ------------------------------------------------------------------ gaps
def analyses(run_dir):
    """{scope: (converted estimation analysis, sha256 of its JSON)} of analysis/scopes/*.json"""
    out = {}
    for f in sorted(glob.glob(os.path.join(run_dir or ".", "analysis", "scopes", "*.json"))):
        try:
            raw = open(f, "rb").read(); d = json.loads(raw)
        except (OSError, ValueError): continue
        if isinstance(d, dict) and isinstance(d.get("estimation"), list): out[os.path.basename(f)[:-5]] = (d, hashlib.sha256(raw).hexdigest())
    return out


def scope_waves(run_dir):
    """{scope: (wave or None, status)} from state/STATUS.json (wave also from state/scopes.json)"""
    st = (TM.load(run_dir, os.path.join("state", "STATUS.json"), {}) or {}).get("scopes") or {}
    sj = (TM.load(run_dir, os.path.join("state", "scopes.json"), {}) or {}).get("scopes") or {}
    return {k: ((st.get(k) or {}).get("wave") or (sj.get(k) or {}).get("wave") or ((sj.get(k) or {}).get("meta") or {}).get("wave"), (st.get(k) or {}).get("status") or "open")
            for k in set(st) | set(sj)}


def ready(scope, waves):
    """a chunk's gaps go to the architect once its wave is closed (every chunk of the wave final, failed-gauntlet or skipped); a chunk without
    a wave once it is closed itself"""
    w, status = waves.get(scope, (None, "open"))
    if w is None: return status in CLOSED
    return all(s in CLOSED for k, (x, s) in waves.items() if x == w)


def gap_rows(cfg, run_dir=None, scopes=None):
    """every gap of the converted analyses, grouped per impact cell <row>@<system> -> [{id, row, system, options, packages (work-package keys
    <row>@<system>:<option>[@<parent>] that reported it), only_with, sources [{scope, option (value), sha256, reason, suggestion, size, claims}],
    wave}] in analysis order"""
    run_dir = run_dir or cfg.get("_run_dir"); model = TM.parse_systems(cfg)[0]; waves = scope_waves(run_dir); out = {}
    for scope, (d, sha) in analyses(run_dir).items():
        if scopes is not None and scope not in scopes: continue
        meta = scope_meta(run_dir, scope)
        for r in d.get("estimation") or []:
            if str(r.get("position") or "").strip() or r.get("coverage") != "gap": continue
            s, o = resolve(r, model, meta)
            if not s: continue
            g = out.setdefault(cell_key(r.get("req_id"), s["id"]), {"id": cell_key(r.get("req_id"), s["id"]), "row": r.get("req_id"), "system": s["id"], "options": [], "packages": [], "sources": [], "wave": waves.get(scope, (None, ""))[0]})
            oid = (o or {}).get("id") or option_value(r); val = option_value(r) or oid
            if oid not in g["options"]: g["options"].append(oid)
            if package_key(g["row"], s["id"], val) not in g.setdefault("packages", []): g["packages"].append(package_key(g["row"], s["id"], val))
            g["sources"].append({"scope": scope, "option": val, "sha256": sha, "reason": (r.get("gap_reason") or "").strip(), "suggestion": (r.get("route_suggestion") or "").strip(),
                                 "size": r.get("size") or "", "claims": list(r.get("claimed_by") or [])})
    by = {s["id"]: s for s in model["systems"]}
    for g in out.values():
        allo = [o["id"] for o in (by.get(g["system"]) or {}).get("options") or []]
        g["only_with"] = [TM.option_key(g["system"], o) for o in g["options"]] if allo and set(g["options"]) != set(allo) else []
    return list(out.values())


def visits(state):
    """{row id: how many batches decided a gap of the row} (the guard counts the row's visits; a later batch's decision on the same cell
    replaces the earlier one in `decisions`, its `visit` keeps the count)"""
    out = {}
    for d in (state or {}).get("decisions") or []: out[d["row"]] = max(out.get(d["row"], 0), int(d.get("visit") or 1))
    return out


def _seen(src, plan):
    """a gap occurrence (chunk, option, row, analysis checksum) already went into a batch"""
    return any(src["scope"] == s["scope"] and src["option"] == s["option"] and src["sha256"] == s["sha256"] and src.get("row") == s.get("row")
               for b in (plan or {}).get("batches") or [] for g in b.get("gaps") or [] for s in g.get("sources") or [])


def open_gaps(cfg, state=None, plan=None, run_dir=None, all_scopes=False):
    """-> (gaps for the next batch, guard-blocked gaps). A gap is open when its occurrence went into no batch yet and its work package has no
    standing decision: a routed gap (route-estimated / route-landscape - the reporting system keeps its own share), a reduced one and a final
    overrule are answered for good; an overruled gap comes back only when the reporting analysis was rewritten after the batch and still reports
    it (the second visit). A new gap on a row the architect decided twice already is guard-blocked (no third routing - validate.py refuses it)."""
    run_dir = run_dir or cfg.get("_run_dir"); waves = scope_waves(run_dir); vis = visits(state)
    dec = {d["id"]: d for d in (state or {}).get("decisions") or []}; out, blocked = [], []
    for g in gap_rows(cfg, run_dir):
        srcs = [dict(s, row=g["row"]) for s in g["sources"] if all_scopes or ready(s["scope"], waves)]
        srcs = [s for s in srcs if not _seen(s, plan)]
        if not srcs: continue
        d = dec.get(g["id"])
        if d and (d.get("decision") != "overrule" or d.get("final")): continue   # answered for good: routed (own share stays), reduced, overruled finally
        g = dict(g, sources=srcs, visit=vis.get(g["row"], 0) + 1)
        (blocked if g["visit"] > 2 else out).append(g)
    return out, blocked


# ------------------------------------------------------------------ decisions and follow-up work packages
def landscape_ids(run_dir):
    raw = TM.load_landscape(run_dir)
    return {s["id"]: s for s in (TM.normalise_landscape(raw)[0]["systems"] if raw is not None else [])}


def merge_decisions(batches, overrides, model, land, disputed=()):
    """the effective decisions: every batch's decision rows in batch order (visit = the row's n-th batch; final from the second visit on), then
    the dashboard / CLI overrides in their order (status overridden). -> [{id, row, from_system, options, only_with, decision, to, to_kind
    system | landscape, to_label, reasoning, solution, assumption, assumption_question, claims, batch, visit, final, status}]"""
    by = {s["id"]: s for s in model["systems"]}; out = {}; seen = {}
    for b in batches:
        for x in b.get("decisions") or []:
            row, frm = x["row_id"], x["from_system"]; key = wp_key(row, frm)
            if b["scope"] not in seen.setdefault(row, []): seen[row].append(b["scope"])
            gap = next((g for g in b.get("gaps") or [] if g["id"] == key), {}); to = (x.get("to") or "").strip()
            kind = "system" if to in by else "landscape"; visit = seen[row].index(b["scope"]) + 1
            out[key] = {"id": key, "row": row, "from_system": frm, "options": gap.get("options") or [], "packages": gap.get("packages") or [], "only_with": gap.get("only_with") or [], "decision": x["decision"], "to": to, "to_kind": kind,
                        "to_label": (by.get(to) or {}).get("label") or (land.get(to) or {}).get("name") or to, "reasoning": (x.get("reasoning") or "").strip(), "solution": (x.get("solution") or "").strip(),
                        "assumption": (x.get("assumption") or "").strip(), "assumption_question": f"Q-{b['scope']}-{x['assumption'].strip()}" if (x.get("assumption") or "").strip() else "",
                        "claims": list(x.get("claimed_by") or []), "batch": b["scope"], "visit": visit, "final": visit >= 2, "status": "applied"}
    for ov in overrides or []:
        d = out.get(ov["gap"])
        if not d: continue
        to = ov.get("to") or (d["from_system"] if ov["decision"] in ("overrule", "reduce-to-standard") else d["to"]); changed = ov["decision"] != d["decision"]
        d.update(decision=ov["decision"], to=to, to_kind="system" if to in by else "landscape", to_label=(by.get(to) or {}).get("label") or (land.get(to) or {}).get("name") or to,
                 reasoning=ov.get("reason") or d["reasoning"], solution=ov.get("solution") or d["solution"], status="overridden", override=ov["id"])
        if ov.get("assumption_question"): d.update(assumption="", assumption_question=ov["assumption_question"])
        elif changed: d.update(assumption="", assumption_question="")   # the earlier decision's client assumption no longer applies
    for d in out.values():
        if d["status"] == "applied" and set(d["claims"]) & set(disputed): d["status"] = "disputed"
    return list(out.values())


def decision_errors(d, model, land):
    """the rules of one effective decision (agent row or override): the receiving end per decision kind, texts, the assumption"""
    by = {s["id"]: s for s in model["systems"]}; w = f"{d['row']} x {d['from_system']}"; err = []; dec, to = d["decision"], d.get("to") or ""
    if dec not in DECISIONS: return [f"{w}: decision '{dec}' ({' | '.join(DECISIONS)})"]
    if dec in ("overrule", "reduce-to-standard") and to != d["from_system"]: err.append(f"{w}: {dec} keeps the work in the reporting system - to = {d['from_system']}")
    if dec == "route-estimated":
        if to not in by: err.append(f"{w}: route-estimated names a system of this run in `to` ({', '.join(by)}) - a landscape system outside the run is route-landscape")
        elif to == d["from_system"]: err.append(f"{w}: route-estimated to the reporting system itself - that is overrule")
    if dec == "route-landscape":
        if to in by: err.append(f"{w}: {to} is a system of this run - route-estimated")
        elif not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", to): err.append(f"{w}: route-landscape names the landscape system's id in `to`")
        elif land and to not in land: err.append(f"{w}: '{to}' is no system of the landscape ({', '.join(sorted(land)) or '-'}) or of this run")
        elif any(lid == to for s in model["systems"] for lid in s.get("landscape_ids") or []): err.append(f"{w}: landscape system {to} belongs to a system of this run - route-estimated to it")
    if not (d.get("reasoning") or "").strip(): err.append(f"{w}: the reasoning is missing (why this decision - an overrule's reasoning goes to the analyst)")
    if dec != "overrule" and not (d.get("solution") or "").strip(): err.append(f"{w}: {dec} needs the solution (the sketch the receiving system estimates, or the standard variant)")
    if dec in ("route-landscape", "reduce-to-standard") and not (d.get("assumption") or d.get("assumption_question")): err.append(f"{w}: {dec} records a client assumption - name its `Assumptions taken` id in `assumption`")
    return err


def packages_of(row, sid, state, impact):
    """the work packages of row x system for a follow-up (as tfe_model.work_package_list): one per option of the system that is in a
    scenario; a dependent system's package carries the parent option for every parent option in a scenario with it when the row touches the
    parent (an affected impact cell); an external system (not estimated by the agents) or a landscape system: the cell <row>@<system> only"""
    syss = {s["id"]: s for s in (state or {}).get("systems") or []}; s = syss.get(sid)
    if not s or s.get("estimated_by", "agents") != "agents" or not s.get("options"): return [cell_key(row, sid)]
    picks = (state or {}).get("picks") or []; par = syss.get(s.get("depends_on")) if s.get("depends_on") else None
    touches = {(c["row"], c["system"]) for c in (impact or {}).get("cells") or [] if c.get("affected")}; out = []
    for o in s["options"]:
        if picks and not any(p.get(sid) == o for p in picks): continue
        pos = [po for po in (par or {}).get("options") or [] if (row, par["id"]) in touches and any(p.get(sid) == o and p.get(par["id"]) == po for p in picks)] if par else []
        out += [package_key(row, sid, o + (f"@{po}" if po else "")) for po in pos or [None]]
    return out or [cell_key(row, sid)]


def followups(state, impact=None):
    """the follow-up work packages of the effective decisions (pure; the record shape of the impact matrix's work-package changes, `dbcx impact changes`,
    keyed by the work-package key): [{work_package <row>@<system>:<option>[@<parent option>] (an external / landscape cell: <row>@<system>),
    cell <row>@<system>, row, system, change new | re-brief, cause, decision, brief_note, final, external, landscape, assumption, only_with,
    solution}].
      overrule            re-brief every reporting package with the architect's reasoning (final on the second visit: no gap any more)
      route-estimated     new packages of the receiving system (re-brief when the impact matrix already has the cell) with the solution sketch;
                          they only estimate (final); an external receiver (estimated by partner / client / team) gets its input cell (external)
      route-landscape     an external cell <row>@<landscape id> (an empty input cell, landscape) + the client assumption naming the solution
      reduce-to-standard  re-brief every reporting package: estimate the standard variant (final) + the client assumption
    the wave planner schedules them (plan_system_chunks(followup=n) for new / re-brief: the analyst brief carries brief_note; final: the CHECK refuses a
    gap on the cell); external and landscape cells are inputs of the workbook, no chunk."""
    have = set(TM.work_packages(impact or {})); syss = {s["id"]: s for s in (state or {}).get("systems") or []}; out = []
    for d in (state or {}).get("decisions") or []:
        cause = f"architect {d['batch']} {d['decision']}" + (f" ({d['override']})" if d.get("override") else ""); frm, to, row = d["from_system"], d["to"], d["row"]
        base = {"cause": cause, "decision": d["id"], "row": row, "only_with": list(d.get("only_with") or []), "solution": d.get("solution") or ""}
        own = d.get("packages") or packages_of(row, frm, state, impact)
        if d["decision"] == "overrule":
            note = f"The architect overrules the gap you reported: {d['reasoning']}" + (" Final decision - estimate it in this system, no gap." if d.get("final") else "")
            out += [dict(base, work_package=k, cell=cell_key(row, frm), system=frm, change="re-brief", final=bool(d.get("final")), external=False, landscape=False, assumption="", brief_note=note) for k in own]
        elif d["decision"] == "route-estimated":
            ext = (syss.get(to) or {}).get("estimated_by", "agents") != "agents"; c = cell_key(row, to)
            note = f"Routed by the architect from {frm} ({d['reasoning']}): estimate this solution - its feasibility is decided: {d['solution']}"
            out += [dict(base, work_package=k, cell=c, system=to, change="re-brief" if c in have else "new", final=True, external=ext, landscape=False, assumption=d.get("assumption_question") or "", brief_note=note)
                    for k in packages_of(row, to, state, impact)]
        elif d["decision"] == "route-landscape":
            out.append(dict(base, work_package=cell_key(row, to), cell=cell_key(row, to), system=to, change="new", final=True, external=True, landscape=True, assumption=d.get("assumption_question") or "",
                            brief_note=f"Outside the estimated systems, on {d.get('to_label') or to}: {d['solution']}"))
        elif d["decision"] == "reduce-to-standard":
            note = f"The architect reduces the requirement to the standard ({d['reasoning']}): estimate the standard variant - {d['solution']}"
            out += [dict(base, work_package=k, cell=cell_key(row, frm), system=frm, change="re-brief", final=True, external=False, landscape=False, assumption=d.get("assumption_question") or "", brief_note=note) for k in own]
    return out


def followup_changes(old, new, impact=None):
    """the changes between two states' follow-ups (an override, a new batch): every follow-up that is new or whose note / kind changed as it
    is, and for a follow-up that disappeared: withdrawn (it was a new work package) or re-brief with the note that the decision changed"""
    a = {(f["work_package"], f["decision"]): f for f in followups(old, impact)}; b = {(f["work_package"], f["decision"]): f for f in followups(new, impact)}; out = []
    for k, f in b.items():
        p = a.get(k)
        if not p or any(p.get(x) != f.get(x) for x in ("change", "brief_note", "final", "external", "assumption")): out.append(f)
    for k, f in a.items():
        if k in b: continue
        out.append(dict(f, change="withdrawn" if f["change"] == "new" else "re-brief", final=False, brief_note="The architect's earlier decision on this work package is withdrawn - estimate it as briefed before."))
    return out


def no_gap(state):
    """{impact cell <row>@<system>: decision id} on which a gap is refused: the final follow-ups (routed, reduced, overruled the second time)"""
    return {f["cell"]: f["decision"] for f in followups(state) if f["final"] and not f["landscape"]}
