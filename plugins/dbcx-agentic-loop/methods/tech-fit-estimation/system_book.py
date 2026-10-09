"""The system-mode workbook of tech-fit-estimation.

A run with run.json `systems` builds D1 from the work packages: one estimation row per package (requirement row x system x option
[x parent option]) on the long-form estimation sheet, the client's own pass-through sheets with the rolled-up effort beside them, the
views (system x release, epic x system, scenario x system, components), the scenario comparison (only with more than one scenario), the
completeness sheet and the surcharges per system option. A run without `systems` never reaches this module (datasets.py keeps the scenario
path untouched).

Data:
  * analysis/scopes/<chunk>.json estimation rows: req_id, option = `<option>[@<parent option>]` (option_value), position, size,
    approach, mechanism, evidence, derivation, estimation_assumption, confidence, starting_point (reuse|extend|new|clarify), coverage
    (standard|extension|gap), gap_reason, route_suggestion; the system from the chunk (state/scopes.json entry `system`); a row
    counts only while its package is LIVE: `TM.planned` holds it in that chunk (superseded rows of an old analysis and packages moved to a
    follow-up chunk stay in their file and are left out). Expected packages = the impact matrix's (`TM.work_package_list`) plus every
    planned one (a package the architect routed into a cell the matrix lacks); one without a row reads NOT-ASSESSED.
  * state/impact.json cells: the external cells (estimated_by != agents) and the impact texts.
  * state/architect.json (`gaps.merge_decisions`): decisions [{row, from_system, decision overrule | route-estimated | route-landscape
    | reduce-to-standard, to, solution, reasoning, assumption_question, only_with}] - `gaps.followups` gives the input cells (external:
    a run system estimated outside the agents, landscape: a landscape system outside the run) with their client assumption, shown as the
    A-nn of the Annahmen sheet; a routing marks every package of the receiving cell "routed from" (it applies to every scenario of the
    receiving system - `only_with` names the reporting options, it never narrows the receiver).
  * analysis/consolidated/SUMMARY.json fixed_phases with `system` and / or option `<system>:<option>`.
  * state/requirements.json rows: `condition` and `interim` (any mapped column, e.g. "bedingt (OP-43)"); a row without them takes its
    roll-up target's. `passthrough` records and requirements_mapping.json sheet key `hide_columns` (headers or letters shown in the
    full edition only).
Configuration: estimation.range_factors {high|medium|low: {min, max}} (method default), estimation.ontop {mode per_system | total,
external}, estimation.show_cost, views.components {system id: [component labels]}.
"""
import copy, json, os, re
import tfe_model as TM

NAMES = {"de": {"est": "Schaetzung", "pos": "Schaetzpositionen", "zp": "Zuschlaege_und_Phasen", "sz": "Szenarien", "other": "Weitere_Zeilen", "sel": "Szenario",
                "taken": {"Management_Summary", "README", "Parameter", "Anforderungen", "Schaetzung", "Schaetzpositionen", "Zuschlaege_und_Phasen", "Szenarien", "Summen",
                          "Vergleich", "Vollstaendigkeit", "Weitere_Zeilen", "Abgrenzungen", "Risiken", "Aussagen", "Annahmen", "Quellen", "Offene_Fragen"}, "suffix": "_Kunde"},
         "en": {"est": "Estimation", "pos": "Estimation_Positions", "zp": "Surcharges_and_Phases", "sz": "Scenarios", "other": "Other_Rows", "sel": "Scenario",
                "taken": {"Management_Summary", "README", "Parameters", "Requirements", "Estimation", "Estimation_Positions", "Surcharges_and_Phases", "Scenarios", "Totals",
                          "Comparison", "Completeness", "Other_Rows", "Exclusions", "Risks", "Claims", "Assumptions", "Sources", "Open_Questions"}, "suffix": "_Client"}}
# a client pass-through sheet keeps the client's sheet name; when it collides with one of these method sheets, the METHOD sheet is renamed
# every formula follows (common.deliverables_spec `renames`)
RENAME = {"de": {"Anforderungen": "Zeilen_gesamt"}, "en": {"Requirements": "All_rows"}}
DECISION = {"overrule": "overrule", "route-estimated": "route", "route-landscape": "route-external", "reduce-to-standard": "reduce"}   # decision -> label token
FALSE = ("", "no", "nein", "false", "0", "-")


def active(cfg): return (cfg or {}).get("systems") is not None
def names(cfg): return NAMES["de" if ((cfg.get("languages") or {}).get("deliverable") == "de") else "en"]
def q(s): return str(s or "").replace('"', '""')


def labeller(L):
    """a label lookup like build_excel.g (token -> display label, `<token>_<ctx>` first; unknown tokens echo back)"""
    def g(v, ctx=None):
        if v is None: return ""
        if ctx and f"{v}_{ctx}" in L: return L[f"{v}_{ctx}"]
        return L.get(v, v) if isinstance(v, str) else v
    return g


def ontop(cfg):
    o = (cfg.get("estimation") or {}).get("ontop") or {}
    return ("total" if o.get("mode") == "total" else "per_system"), bool(o.get("external"))


def show_cost(cfg): return (cfg.get("estimation") or {}).get("show_cost", True) is not False


def entries(v):
    if isinstance(v, list): return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in re.split(r"[;\n]", str(v or "")) if x.strip()]


def flag_text(v):
    """a condition / interim cell: the text as written, empty for no / nein / false"""
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in FALSE else s


def sheet_name(raw, taken, suffix):
    """an Excel-safe sheet name for a client sheet that formulas can name unquoted ([A-Za-z0-9_], <= 31 characters, unique)"""
    n = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw or "")).strip("_") or "Liste"
    if not re.match(r"[A-Za-z_]", n): n = "L_" + n
    n = n[:31]
    while n in taken: n = (n[:31 - len(suffix)] + suffix) if not n.endswith(suffix) else n[:28] + f"_{len(taken) % 100}"
    return n


class Book:
    """everything the system-mode sheets need, computed once from the run files (cfg) and, at build time, the loaded analyses (D)"""

    def __init__(self, cfg, g, D=None):
        from common import fmt
        self.cfg, self.g, self.N = cfg, g, names(cfg); run = cfg.get("_run_dir"); self.lang = "de" if ((cfg.get("languages") or {}).get("deliverable") == "de") else "en"
        F = lambda s: fmt(s, cfg)
        model, err, _ = TM.parse_systems(cfg)
        if err: raise SystemExit("run.json systems / scenarios:\n  " + "\n  ".join(err))
        self.model = model; self.mode, self.ext_ontop = ontop(cfg); self.cost = show_cost(cfg)
        doc = (D or {}).get("req") if D else None
        self.reqdoc = doc if doc is not None else (TM.load(run, os.path.join("state", "requirements.json"), {}) or {})
        self.reqs = self.reqdoc.get("requirements") or []; self.by = {r["id"]: r for r in self.reqs}; self.order = {r["id"]: i for i, r in enumerate(self.reqs)}
        self.rows = TM.estimating_rows(cfg, self.reqs); self.row_ids = {r["id"] for r in self.rows}
        self.impact = TM.load(run, TM.IMPACT_PATH, None) or {}
        self.astate = TM.load(run, os.path.join("state", "architect.json"), None) or {}
        self.anum, self.awording = assumption_numbers(); self.arch = self._architect(self.astate); self.inputs = self._inputs()
        land = TM.load_landscape(run); self.land = {s["id"]: s for s in (TM.normalise_landscape(land)[0]["systems"] if land else [])}
        self.agents_owner = F(g("agents", "by"))
        # systems: the run's (declared order) + the landscape systems the architect routed packages to (external, not estimated in this run)
        self.systems = []
        for s in model["systems"]:
            ext = s["estimated_by"] != "agents"
            self.systems.append({"id": s["id"], "label": s["label"], "ext": ext, "by": s["estimated_by"], "depends_on": s.get("depends_on"), "options": s["options"],
                                 "owner": (s.get("owner_label") or F(g(s["estimated_by"], "by"))) if ext else self.agents_owner})
        known = {s["id"] for s in self.systems}
        for x in self.inputs:
            t = x["system"]
            if x["landscape"] and t not in known:
                ls = self.land.get(t) or {}; known.add(t)
                self.systems.append({"id": t, "label": ls.get("name") or t, "ext": True, "by": "client", "depends_on": None, "options": [], "owner": F(g("client", "by")), "landscape": True})
        self.sys = {s["id"]: s for s in self.systems}
        self.scenarios = []
        for sc in model["scenarios"]:
            lab = g("_solution_label") if sc.get("auto") and sc["id"] == "solution" and sc["label"] == "solution" else sc["label"]
            self.scenarios.append({"id": sc["id"], "label": lab, "pick": sc["pick"]})
        self.multi = len(self.scenarios) > 1
        self.picks = []
        for sc in self.scenarios:
            for s in self.systems:
                o = sc["pick"].get(s["id"])
                if not o: continue
                par = s["depends_on"]; po = sc["pick"].get(par) if par else None
                self.picks.append({"scenario": sc["label"], "system": s["label"], "option": self.olabel(s["id"], o), "parent": self.olabel(par, po) if po else ""})
        self.D = D
        self.wps, self.positions = self._packages(D) if D is not None else ([], [])

    # ------------------------------------------------------------------ helpers
    def olabel(self, sid, oid):
        s = self.sys.get(sid) or {}
        return next((o["label"] for o in s.get("options") or [] if o["id"] == oid), oid or "")

    def slabel(self, sid): return ((self.sys.get(sid) or {}).get("label") or (self.land.get(sid) or {}).get("name") or sid or "") if sid else ""

    def target(self, r):
        t = r.get("rollup_to")
        return self.by.get(t) if t and t != r["id"] else None

    def rollup(self, r): return r.get("rollup_to") or r["id"]

    def inherited(self, r, f):
        v = flag_text(r.get(f))
        if not v and self.target(r): v = flag_text(self.target(r).get(f))
        return v

    def row_info(self, rid):
        r = self.by.get(rid) or {"id": rid}; t = self.target(r) or {}; g = self.g
        return {"req_id": rid, "title": r.get("title", ""), "rollup": self.rollup(r), "epic": r.get("epic") or t.get("epic") or g("_no_epic"),
                "release": r.get("phase") or t.get("phase") or g("_no_release"), "group": r.get("group", ""), "condition": self.inherited(r, "condition"), "interim": self.inherited(r, "interim")}

    def _architect(self, doc):
        """the effective decisions of state/architect.json (gaps.merge_decisions) in this module's vocabulary: decision overrule | route
        (route-estimated) | route-external (route-landscape) | reduce (reduce-to-standard), target = the receiving system, text = the
        solution (the reasoning for an overrule), assumption = the A-nn of the client assumption it registered"""
        out = []
        for d in (doc.get("decisions") or []) if isinstance(doc, dict) else []:
            if not isinstance(d, dict) or not d.get("row"): continue
            out.append({"row": d["row"], "system": d.get("from_system") or "", "decision": DECISION.get(d.get("decision"), d.get("decision") or ""), "target": d.get("to") or "",
                        "text": (d.get("solution") or d.get("reasoning") or "").strip(), "assumption": self.anum.get(d.get("assumption_question") or "", ""),
                        "only_with": list(d.get("only_with") or [])})
        return out

    def _inputs(self):
        """the architect's input cells (gaps.followups, external): a routing to a run system estimated outside the agents (external) or to a
        landscape system outside the run (landscape) -> [{row, system, from, solution, assumption (A-nn), landscape}]"""
        if not self.astate.get("decisions"): return []
        import gaps as G
        by = {d["id"]: d for d in self.astate["decisions"] if isinstance(d, dict) and d.get("id")}; out = []
        for f in G.followups(self.astate, self.impact):
            if not f.get("external") or f.get("change") == "withdrawn": continue
            out.append({"row": f["row"], "system": f["system"], "from": (by.get(f["decision"]) or {}).get("from_system") or "", "solution": f.get("solution") or "",
                        "assumption": self.anum.get(f.get("assumption") or "", ""), "wording": self.awording.get(f.get("assumption") or "", ""), "landscape": bool(f.get("landscape"))})
        return out

    def routed(self, rid, sid):
        """the reporting system of an architect routing into the cell <rid>@<sid> ('' when none) - every package of the receiving cell,
        whatever option reported the gap (a routing applies to every scenario of the receiving system)"""
        return next((d["system"] for d in self.arch if d["decision"] in ("route", "route-external") and d["row"] == rid and d["target"] == sid), "")

    def _live(self, D):
        """(predicate scope, key) -> bool: the chunk holds the package as an active one (`TM.planned`; a superseded row of an old analysis
        or a package moved to a follow-up chunk is not live there); without package metadata every row is live"""
        chunks = (D or {}).get("chunks") or {}
        if not any(((e or {}).get("meta") or {}).get("work_packages") for e in (chunks.get("scopes") or {}).values()): return lambda scope, key: True
        held = {k: v[0] for k, v in TM.planned(chunks).items()}
        return lambda scope, key: held.get(key) == scope

    def _system_of(self, e, scope, D):
        if e.get("system"): return str(e["system"]).strip()
        ch = (((D or {}).get("chunks") or {}).get("scopes") or {}).get(scope) or {}
        if ch.get("system"): return ch["system"]
        opt = str(e.get("option") or "").partition("@")[0].strip()
        hit = [s["id"] for s in self.systems if any(o["id"] == opt for o in s["options"])]
        return hit[0] if len(hit) == 1 else ""

    # ------------------------------------------------------------------ work packages
    def _packages(self, D):
        g = self.g; live = self._live(D); seen = set(); main = {}; pos = []
        for scope in sorted((D or {}).get("scopes") or {}):
            for e in (D["scopes"][scope].get("estimation") or []):
                rid = str(e.get("req_id") or "").strip(); val = str(e.get("option") or "").strip(); sid = self._system_of(e, scope, D)
                if not rid or not sid: continue
                oid, _, par = val.partition("@"); key = f"{rid}@{sid}:{val}"; p = str(e.get("position") or "").strip()
                if not live(scope, key) or (key, p) in seen: continue
                seen.add((key, p))
                if p: pos.append((key, p, e, scope))
                else: main[key] = (e, sid, oid, par or None)
        out = []
        for key, (e, sid, oid, par) in main.items(): out.append(self._agent_row(key, e, sid, oid, par))
        have = set(main)
        for w in self._expected():
            k = f"{w['row']}@{w['system']}:{w['option']}" + (f"@{w['parent']}" if w.get("parent") else "")
            if k not in have: out.append(self._agent_row(k, {"req_id": w["row"], "approach": "NOT-ASSESSED"}, w["system"], w["option"], w.get("parent")))
        ext = {}
        for c in self.impact.get("cells") or []:
            s = self.sys.get(c.get("system")) or {}
            if c.get("affected") and s.get("ext") and c.get("row") in self.row_ids: ext[(c["row"], s["id"])] = self._ext_row(c["row"], s, c.get("impact", ""))
        for x in self.inputs:   # the architect's input cells: a cell the matrix already has keeps its impact text and gains the routing
            s = self.sys.get(x["system"]) or {}
            if not s.get("ext") or x["row"] not in self.row_ids: continue
            r = ext.get((x["row"], s["id"])) or self._ext_row(x["row"], s, x["solution"])
            r["routed_from"] = self.slabel(x["from"]) if x["from"] else ""; r["assumption"] = ": ".join(v for v in (x["assumption"], x["wording"]) if v); ext[(x["row"], s["id"])] = r
        out += list(ext.values())
        sord = {s["id"]: i for i, s in enumerate(self.systems)}
        def okey(w):
            s = self.sys.get(w["system_id"]) or {}; oo = [o["id"] for o in s.get("options") or []]
            return (self.order.get(w["req_id"], 10 ** 6), sord.get(w["system_id"], 99), oo.index(w["option_id"]) if w["option_id"] in oo else 0, w["parent"])
        out.sort(key=okey)
        ps = []
        for key, p, e, scope in pos:
            w = next((x for x in out if x["key"] == key), None)
            if not w: continue
            ps.append({"req_id": w["req_id"], "system": w["system"], "option": w["option"], "parent": w["parent"], "position": p, "title": e.get("position_title", ""),
                       "size": str(e.get("size") or ""), "assumption": e.get("estimation_assumption", ""), "evidence": entries(e.get("evidence")), "derivation": e.get("derivation", "")})
        order = {(w["req_id"], w["system"], w["option"], w["parent"]): i for i, w in enumerate(out)}
        ps.sort(key=lambda x: (order.get((x["req_id"], x["system"], x["option"], x["parent"]), 10 ** 6), _num(x["position"])))
        return out, ps

    def _expected(self):
        """the agent packages a row is expected for: the impact matrix's (`TM.work_package_list`) plus every planned one (a package
        the architect routed into a cell the matrix lacks, origin architect) -> [{row, system, option, parent}]"""
        out = TM.work_package_list(self.model, self.impact.get("cells") or [], self.rows); have = {w["key"] for w in out}
        for k, (_, w) in TM.planned(((self.D or {}).get("chunks")) or {}).items():
            if k not in have and w.get("row") in self.row_ids: out.append({"row": w["row"], "system": w["system"], "option": w["option"], "parent": w.get("parent")}); have.add(k)
        return out

    def _formulas(self, row):
        """per-row formula templates: the scenario membership (selected scenario + one per scenario)"""
        if row["ext"]:
            row["insel_f"] = "=1"; row["in_f"] = {s["id"]: "=1" for s in self.scenarios}; return row
        row["insel_f"] = "=" + member(f"{{p:{self.N['sel']}}}"); row["in_f"] = {s["id"]: "=" + member(f'"{q(s["label"])}"') for s in self.scenarios}
        return row

    def cell_impact(self, rid, sid):
        return next((c.get("impact", "") for c in self.impact.get("cells") or [] if c.get("row") == rid and c.get("system") == sid and c.get("affected")), "")

    def _agent_row(self, key, e, sid, oid, par):
        g = self.g; P = self.N["pos"]; s = self.sys.get(sid) or {}
        crit = (f'{{rng:{P}.req_id}},{{cell:req_id}},{{rng:{P}.system}},{{cell:system}},{{rng:{P}.option}},{{cell:option}}&"",'
                f'{{rng:{P}.parent}},{{cell:parent}}&""')
        pd = (f'=IF(COUNTIFS({crit})>0,SUMIFS({{rng:{P}.pd}},{crit}),IF({{cell:size}}="",0,IFERROR(INDEX({{pt:tshirt.pd}},MATCH(SUBSTITUTE(""&{{cell:size}},",","."),'
              f'{{pt:tshirt.size}},0)),0)))')
        row = dict(self.row_info(str(e.get("req_id")).strip()), key=key, system=s.get("label", sid), system_id=sid, option=self.olabel(sid, oid), option_id=oid,
                   parent=self.olabel(s.get("depends_on"), par) if par else "", ext=False, owner=self.agents_owner, starting_point=e.get("starting_point", ""),
                   coverage=e.get("coverage", ""), approach=e.get("approach", ""), mechanism=e.get("mechanism", ""), size=str(e.get("size") or ""), pd_formula=pd, pd_input=None,
                   confidence=e.get("confidence", ""), assumption=e.get("estimation_assumption", ""), evidence=entries(e.get("evidence")), derivation=e.get("derivation", ""),
                   routed_from=self.slabel(self.routed(str(e.get("req_id")).strip(), sid)), gap_reason=e.get("gap_reason", ""), route_suggestion=e.get("route_suggestion", ""),
                   basis_default=g("_basis_open") if e.get("approach") == "NOT-ASSESSED" else "", input="", impact=self.cell_impact(str(e.get("req_id")).strip(), sid))
        return self._formulas(self._akeys(row))

    def _akeys(self, row):
        """the keys a client assumption may name for this row: the cell <row>@<system> and the work package <row>@<system>:<option>[@<parent>]
        - an architect's assumption that affects one of them lands on that package / cell only, never on the row's other systems or options; the
        Annahmen sheet reads them as 'TA-03 (SAP BTP)' / 'IF-03 (E-Commerce · SAP Commerce Cloud)'"""
        rid, cell = row["req_id"], f"{row['req_id']}@{row['system_id']}"
        row["akeys"] = list(dict.fromkeys([cell, row["key"]])); row["akey_labels"] = {cell: f"{rid} ({row['system']})"}
        if row["key"] != cell: row["akey_labels"][row["key"]] = f"{rid} ({row['system']} · {row['option']}" + (f", {row['parent']}" if row.get("parent") else "") + ")"
        return row

    def _ext_row(self, rid, s, impact):
        g = self.g
        row = dict(self.row_info(rid), key=f"{rid}@{s['id']}", system=s["label"], system_id=s["id"], option="", option_id="", parent="", ext=True, owner=s["owner"],
                   starting_point="", coverage="", approach="", mechanism="", impact=impact, size="", pd_formula="", pd_input=None, confidence="", assumption="", evidence=[],
                   derivation="", routed_from="", gap_reason="", route_suggestion="",
                   basis_default=g("_basis_input").replace("{owner}", s["owner"]), input="yes")
        return self._formulas(self._akeys(row))

    # ------------------------------------------------------------------ surcharges, fixed phases, scenario lines
    def sysopts(self):
        """the columns of the surcharge table: one per system option (per_system), external systems with ontop.external; `total` mode: one"""
        if self.mode == "total": return [{"key": "total", "label": self.g("_all_systems")}]
        out = []
        for s in self.systems:
            if s["ext"]:
                if self.ext_ontop and not s.get("landscape"): out.append({"key": s["id"], "label": s["label"]})
                continue
            for o in s["options"]: out.append({"key": f"{s['id']}__{o['id']}", "label": s["label"] if o["label"] == s["label"] else f"{s['label']} · {o['label']}"})
        return out

    def ontop_rows(self):
        g = self.g; E = self.N["est"]; roles = [x.get("role") for x in (self.cfg.get("estimation") or {}).get("surcharges", []) if x.get("role")]
        phases = ((self.D or {}).get("sum") or {}).get("fixed_phases") or []; out = []
        def line(**kw):
            base = {"system": "", "option": "", "parent": "", "scenario": "", "block": "", "title": "", "rate": "", "rate_formula": "", "pd": None, "pd_formula": "", "derivation": "", "evidence": [], "ext": False}
            r = dict(base, **kw); return r
        def member_line(r):
            if r["ext"]: r["insel_f"] = "=1"; r["in_f"] = {s["id"]: "=1" for s in self.scenarios}
            elif not r["option"]: r["insel_f"] = "=" + member_sys(f"{{p:{self.N['sel']}}}"); r["in_f"] = {s["id"]: "=" + member_sys(f'"{q(s["label"])}"') for s in self.scenarios}
            else: r["insel_f"] = "=" + member(f"{{p:{self.N['sel']}}}"); r["in_f"] = {s["id"]: "=" + member(f'"{q(s["label"])}"') for s in self.scenarios}
            return r
        for s in self.systems:
            par = self.sys.get(s["depends_on"]) if s["depends_on"] else None
            if s["ext"]:
                dev = f'SUMIFS({{rng:{E}.pd}},{{rng:{E}.system}},"{q(s["label"])}")'
                out.append(member_line(line(system=s["label"], block="dev", title=g("_dev_title_ext").replace("{owner}", s["owner"]), pd_formula=f"={dev}", derivation=g("_dev_derivation_ext"), ext=True)))
                if self.mode == "per_system" and self.ext_ontop and not s.get("landscape"):
                    for ro in roles: out.append(member_line(line(system=s["label"], block="surcharge", title=g(f"{ro}_role"), rate_formula=f"={{pt:surcharge.{s['id']}.{ro}}}/100",
                                                                pd_formula=f"=({dev})*{{pt:surcharge.{s['id']}.{ro}}}/100", derivation=g("_surcharge_derivation_system"), ext=True)))
                continue
            for o in s["options"]:
                if not any(sc["pick"].get(s["id"]) == o["id"] for sc in self.scenarios): continue
                pars = [po["id"] for po in (par or {}).get("options") or [] if any(sc["pick"].get(s["id"]) == o["id"] and sc["pick"].get(par["id"]) == po["id"] for sc in self.scenarios)] if par else []
                ol = o["label"]; key = f"{s['id']}__{o['id']}"
                for po in pars or [None]:
                    base = f'SUMIFS({{rng:{E}.pd}},{{rng:{E}.system}},"{q(s["label"])}",{{rng:{E}.option}},"{q(ol)}"'
                    dev = f'{base},{{rng:{E}.parent}},"{q(self.olabel(par["id"], po))}")+{base},{{rng:{E}.parent}},"")' if po else f"{base})"
                    pl = self.olabel(par["id"], po) if po else ""
                    out.append(member_line(line(system=s["label"], option=ol, parent=pl, block="dev", title=g("_dev_title_system"), pd_formula=f"={dev}", derivation=g("_dev_derivation_system"))))
                    if self.mode == "per_system":
                        for ro in roles:
                            out.append(member_line(line(system=s["label"], option=ol, parent=pl, block="surcharge", title=g(f"{ro}_role"), rate_formula=f"={{pt:surcharge.{key}.{ro}}}/100",
                                                        pd_formula=f"=({dev})*{{pt:surcharge.{key}.{ro}}}/100", derivation=g("_surcharge_derivation_system"))))
        for p in phases:
            sid, oid = self.phase_target(p)
            s = self.sys.get(sid)
            if not s: continue
            out.append(member_line(line(system=s["label"], option=self.olabel(sid, oid) if oid else "", block=p.get("block", "phase"), title=p.get("title", ""), pd=_num(p.get("pd")),
                                        derivation=p.get("derivation", ""), evidence=entries(p.get("evidence")), ext=s["ext"], id=p.get("id", ""))))
        if self.mode == "total":
            for sc in self.scenarios:
                crit = "" if self.ext_ontop else f',{{rng:{E}.owner}},"{q(self.agents_owner)}"'
                dev = f'SUMIFS({{rng:{E}.pd}},{{rng:{E}.in_{sc["id"]}}},1{crit})'
                for ro in roles:
                    r = line(system=g("_all_systems"), scenario=sc["label"], block="surcharge", title=g(f"{ro}_role"), rate_formula=f"={{pt:surcharge.total.{ro}}}/100",
                             pd_formula=f"=({dev})*{{pt:surcharge.total.{ro}}}/100", derivation=g("_surcharge_derivation_total"))
                    r["insel_f"] = f'=IF({{p:{self.N["sel"]}}}="{q(sc["label"])}",1,0)'; r["in_f"] = {x["id"]: "=1" if x["id"] == sc["id"] else "=0" for x in self.scenarios}
                    out.append(r)
        return out

    def phase_target(self, p):
        """(system id, option id | None) of a fixed phase: `system`, an option `<system>:<option>`, or an option id one system owns"""
        sid = str(p.get("system") or "").strip(); opt = str(p.get("option") or "").strip()
        if ":" in opt: sid, opt = opt.split(":", 1)
        elif not sid and opt in self.sys and not any(o["id"] == opt for s in self.systems for o in s["options"]): sid, opt = opt, ""   # a system id: the whole system
        if sid and sid in self.sys:
            s = self.sys[sid]; return sid, (opt if any(o["id"] == opt for o in s["options"]) else None)
        hit = [s["id"] for s in self.systems if any(o["id"] == opt for o in s["options"])]
        return (hit[0], opt) if len(hit) == 1 else ("", None)

    def sum_systems(self):
        return [{"label": s["label"]} for s in self.systems] + ([{"label": self.g("_all_systems")}] if self.mode == "total" else [])

    def scenario_rows(self):
        """the scenario x system lines of the Szenarien sheet (more than one scenario): the build-up of each system in each scenario"""
        if not self.multi: return []
        Z, E, g = self.N["zp"], self.N["est"], self.g; out = []
        for sc in self.scenarios:
            sid = sc["id"]
            for s in self.sum_systems():
                z = lambda extra: f'SUMIFS({{rng:{Z}.pd}},{{rng:{Z}.system}},"{q(s["label"])}",{{rng:{Z}.in_{sid}}},1{extra})'
                e = lambda extra: f'SUMIFS({{rng:{E}.pd}},{{rng:{E}.system}},"{q(s["label"])}",{{rng:{E}.in_{sid}}},1{extra})'
                blk = lambda b: f',{{rng:{Z}.block}},"{{L:{b}|blk}}"'
                out.append({"scenario": sc["label"], "system": s["label"], "dev_f": "=" + z(blk("dev")), "sur_f": "=" + z(blk("surcharge")),
                            "ph_f": "=" + z(blk("phase")) + "+" + z(blk("migration-task")), "pd_f": "=" + z(""),
                            "cond_f": "=" + e(f',{{rng:{E}.condition}},"<>"'), "interim_f": "=" + e(f',{{rng:{E}.interim}},"<>"')})
        return out

    # ------------------------------------------------------------------ pass-through and other rows
    def pt_ids(self): return {r["id"] for p in self.reqdoc.get("passthrough") or [] for r in p.get("rows") or [] if r.get("id")}

    def impacts_of(self, key):
        """the impact texts of the work packages that roll up to `key` (one line per row and system)"""
        g = self.g; lines = []
        for c in self.impact.get("cells") or []:
            if not c.get("affected") or c.get("row") not in self.row_ids or self.rollup(self.by.get(c["row"]) or {"id": c["row"]}) != key: continue
            lines.append((self.order.get(c["row"], 0), f"{'' if c['row'] == key else c['row'] + ' · '}{self.slabel(c['system'])}: {c.get('impact', '')}".strip()))
        return "\n".join(t for _, t in sorted(lines, key=lambda x: x[0]))

    def hidden(self):
        """{client sheet: {header or letter (lower case)}} from requirements_mapping.json sheet key `hide_columns`"""
        mp = TM.load(self.cfg.get("_run_dir"), ((self.cfg.get("requirements") or {}).get("mapping") or "requirements_mapping.json"), {}) or {}
        return {str(s.get("sheet")): {str(x).strip().lower() for x in s.get("hide_columns") or []} for s in mp.get("sheets") or [] if isinstance(s, dict)}

    def passthrough(self):
        """[{group, sheet, name, idcol, table, columns, rows}] - one sheet per passthrough group, the client's columns in order"""
        hid = self.hidden(); out = []; names_ = self.sheet_names()
        for i, p in enumerate(self.reqdoc.get("passthrough") or [], 1):
            nm = names_[i - 1]; idl = p.get("id_column") or "A"; hide = hid.get(str(p.get("sheet")), set())
            rows = [{"c": {c["letter"]: (r.get("values") or [])[k] if k < len(r.get("values") or []) else None for k, c in enumerate(p.get("columns") or [])},
                     "id": r.get("id"), "impacts": self.impacts_of(r["id"]) if r.get("id") else ""} for r in p.get("rows") or []]
            cols = []
            for k, c in enumerate(p.get("columns") or []):
                vals = [str(r["c"].get(c["letter"]) or "") for r in rows]; longest = max([len(v) for v in vals] or [0])
                w = c.get("width") or min(60, max(10, longest + 2)); col = {"id": f"c_{c['letter']}", "header": str(c.get("header") or f"({c['letter']})"), "field": f"c.{c['letter']}",
                                                                               "width": min(60, max(6, int(w))), "verbatim": True, "text_transform": False, "sparse": True}
                if longest > 40: col["wrap"] = True
                if c["letter"] != idl and (str(c.get("header") or "").strip().lower() in hide or c["letter"].lower() in hide): col["edition"] = "full"
                cols.append(col)
            out.append({"group": p.get("group", ""), "sheet": str(p.get("sheet") or ""), "name": nm, "idcol": idl, "table": re.sub(r"\W", "", f"Client{nm}")[:40] or f"Client{i}",
                        "columns": cols, "rows": rows})
        return out

    def sheet_names(self):
        """the pass-through sheets' names: the client's sheet name (formula-safe); one that collides with a method sheet of RENAME keeps it
        and that method sheet is renamed (renames()); a collision with any other method sheet or another client sheet gets the suffix"""
        ren = RENAME[self.lang]; taken = (set(self.N["taken"]) - set(ren)) | set(ren.values()); used = set(); out = []
        for p in self.reqdoc.get("passthrough") or []:
            nm = sheet_name(p.get("sheet"), taken | used, self.N["suffix"]); used.add(nm); out.append(nm)
        return out

    def renames(self):
        """{method sheet: new name} for the method sheets a pass-through sheet's name took (common.deliverables_spec applies it)"""
        ren = RENAME[self.lang]; return {n: ren[n] for n in self.sheet_names() if n in ren}

    def other_rows(self):
        pt = self.pt_ids(); seen = []; g = self.g
        for r in self.rows:
            k = self.rollup(r)
            if k not in pt and k not in seen: seen.append(k)
        out = []
        for k in seen:
            r = self.by.get(k) or {"id": k}
            out.append({"id": k, "title": r.get("title", ""), "group": r.get("group", ""), "impacts": self.impacts_of(k)})
        return out

    # ------------------------------------------------------------------ completeness (Vollstaendigkeit)
    def completeness(self):
        g = self.g; E = self.N["est"]; out = []; none = self.impact.get("none") or {}
        cells = {(c.get("row"), c.get("system")): c for c in self.impact.get("cells") or []}
        cnt = lambda extra="": f'=COUNTIFS({{rng:{E}.req_id}},{{cell:row}}{extra})'
        st = lambda ok, bad: f'=IF({{cell:count}}>0,"{q(g(ok, "chk"))}","{q(g(bad, "chk"))}")'
        for r in self.rows:
            n = none.get(r["id"])
            if n: out.append({"check": "row", "row": r["id"], "title": r.get("title", ""), "system": "", "detail": n.get("reason", ""), "decision": "", "count_f": cnt(), "status": g("none", "chk"), "status_f": ""})
            else: out.append({"check": "row", "row": r["id"], "title": r.get("title", ""), "system": "", "detail": "", "decision": "", "count_f": cnt(), "status": "", "status_f": st("ok", "missing")})
        for r in self.rows:
            for e in r.get("ends") or []:
                s = self.sys.get(e.get("system") or "")
                if not s: continue
                c = cells.get((r["id"], s["id"])) or {}; det = f"{g(e.get('end'), 'end')}: {e.get('name', '')}"
                if c and not c.get("affected"):
                    out.append({"check": "interface", "row": r["id"], "title": r.get("title", ""), "system": s["label"], "detail": det, "decision": c.get("reason", ""),
                                "count_f": cnt(f',{{rng:{E}.system}},{{cell:system}}'), "status": "", "status_f": st("ok", "removed")})
                else:
                    out.append({"check": "interface", "row": r["id"], "title": r.get("title", ""), "system": s["label"], "detail": det, "decision": "",
                                "count_f": cnt(f',{{rng:{E}.system}},{{cell:system}}'), "status": "", "status_f": st("ok", "missing")})
        for w in self.wps:
            if w["ext"]:
                x = next((x for x in self.inputs if x["row"] == w["req_id"] and x["system"] == w["system_id"]), None)   # an input cell of the architect: its solution and A-nn
                dec = (x["solution"] + (f" ({x['assumption']})" if x["assumption"] else "")).strip() if x else ""
                out.append({"check": "input", "row": w["req_id"], "title": w["title"], "system": w["system"], "detail": w["owner"], "decision": dec,
                            "count_f": cnt(f',{{rng:{E}.system}},{{cell:system}},{{rng:{E}.pd}},""'), "status": "", "status_f": f'=IF({{cell:count}}>0,"{q(g("open", "chk"))}","{q(g("filled", "chk"))}")'})
        import gaps as G   # every gap any analysis reported (also one whose row a re-estimate superseded) with the architect's decision
        dec = {f"{d['row']}@{d['system']}": d for d in self.arch}; sord = {s["id"]: i for i, s in enumerate(self.systems)}
        for gp in sorted(G.gap_rows(self.cfg), key=lambda x: (self.order.get(x["row"], 10 ** 6), sord.get(x["system"], 99))):
            if gp["row"] not in self.row_ids: continue
            d = dec.get(gp["id"]); rs = list(dict.fromkeys((x["reason"], x["suggestion"]) for x in gp["sources"] if x["reason"]))
            det = "; ".join(r + (f" ({g('_suggestion')}: {self.slabel(sg)})" if sg else "") for r, sg in rs)
            txt = ""
            if d: txt = g(d["decision"], "arch") + (f": {self.slabel(d['target'])}" if d["target"] and d["decision"] in ("route", "route-external") else "") + (f" - {d['text']}" if d["text"] else "") + (f" ({d['assumption']})" if d["assumption"] else "")
            out.append({"check": "gap", "row": gp["row"], "title": (self.by.get(gp["row"]) or {}).get("title", ""), "system": self.slabel(gp["system"]), "detail": det, "decision": txt,
                        "count_f": cnt(f',{{rng:{E}.system}},{{cell:system}}'), "status": g(d["decision"], "chk") if d else g("open", "chk"), "status_f": ""})
        for x in out: x["check_label"] = g(x["check"], "chk")
        return out

    # ------------------------------------------------------------------ spec context (sets + flags)
    def spec_sets(self, g_owner_ids=True):
        sel = self.scenarios[0]["label"] if self.scenarios else ""
        pts = self.passthrough(); oth = self.other_rows()
        recon = "+".join([f'SUM({{rng:{p["name"]}.total}})' for p in pts] + ([f'SUM({{rng:{self.N["other"]}.total}})'] if oth else [])) or "0"
        owners = list(dict.fromkeys(s["owner"] for s in self.systems if s["ext"]))
        comps = []
        for sid, labs in (((self.cfg.get("views") or {}).get("components")) or {}).items():
            for c in labs if isinstance(labs, list) else [labs]:
                if sid in self.sys: comps.append({"label": str(c), "system": self.sys[sid]["label"]})
        return {"systems": {"as": "y", "items": [{"id": s["id"], "label": s["label"], "q": q(s["label"]), "owner": s["owner"]} for s in self.systems]},
                "sysopts": {"as": "k", "items": self.sysopts()},
                "scenarios": {"as": "s", "items": [{"id": s["id"], "label": s["label"], "q": q(s["label"])} for s in self.scenarios]},
                "picks": {"as": "k", "items": self.picks},
                "passthrough": {"as": "p", "items": [{k: v for k, v in p.items() if k != "rows"} for p in pts]},
                "owners": {"as": "w", "items": [{"id": f"w{i}", "label": o, "q": q(o)} for i, o in enumerate(owners, 1)]},
                "selsc": {"as": "f", "items": [{"label": sel, "labels": ",".join(s["label"].replace(",", " ") for s in self.scenarios), "recon": recon}]},
                "components": {"as": "c", "items": comps}}

    def flags(self):
        pts = self.reqdoc.get("passthrough") or []
        return {"system_mode": True, "system_single": not self.multi, "system_multi": self.multi, "hide_cost": not self.cost, "ontop_total": self.mode == "total",
                "ontop_per_system": self.mode == "per_system", "components": bool(((self.cfg.get("views") or {}).get("components"))), "other_rows": bool(self.other_rows()),
                "passthrough": bool(pts), "has_ext": any(s["ext"] for s in self.systems), "range": True,   # estimation.range_factors always holds the method default (a run overrides single values)
                "scenario_mode": False, "row_classes": False, "is": False, "refactoring": False}


def assumption_numbers():
    """({question id: A-nn}, {question id: the customer wording}) of the released client-directed questions - the numbers the Annahmen
    sheet shows (engine xl_transform)"""
    from common import load_questions
    from xl_transform import assumption_numbers as nums
    qs = [q for q in load_questions() if q.get("released") is not False]
    return nums(qs), {q["id"]: (q.get("assumption") or "").strip() for q in qs if q.get("id")}


EMPTY_SETS = {n: {"as": a, "items": []} for n, a in (("systems", "y"), ("sysopts", "k"), ("scenarios", "s"), ("picks", "k"), ("passthrough", "p"), ("owners", "w"), ("selsc", "f"), ("components", "c"))}


def member(S):
    """formula fragment: 1 when the row's (system, option, parent option) is picked by scenario S (a label literal or the selector cell)"""
    return (f'IF(COUNTIFS({{pt:pick.scenario}},{S},{{pt:pick.system}},{{cell:system}},{{pt:pick.option}},{{cell:option}}&"")=0,0,IF({{cell:parent}}="",1,'
            f'IF(COUNTIFS({{pt:pick.scenario}},{S},{{pt:pick.system}},{{cell:system}},{{pt:pick.option}},{{cell:option}}&"",{{pt:pick.parent}},{{cell:parent}}&"")>0,1,0)))')


def member_sys(S):
    """formula fragment: 1 when scenario S picks any option of the row's system (a fixed phase that names a system only)"""
    return f'IF(COUNTIFS({{pt:pick.scenario}},{S},{{pt:pick.system}},{{cell:system}})>0,1,0)'


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool): return float(v)
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v or ""))
    return float(m.group(0).replace(",", ".")) if m else 0.0
