"""Row providers of the tech-fit-estimation method for `dbcx build_excel` (pure functions over the loaded JSON).

load(D, ROOT, INTERIM) adds the method's own inputs to the engine's base dict (D["scopes"], D["cons"], D["req"], D["status"], D["client_questions"]):
  D["sum"]     = the consolidation analysis/consolidated/SUMMARY.json (or None)
  D["chunks"]  = state/scopes.json (which epics sit in which chunk - the workbook names epics, never chunk ids)
  D["options"] = the run's options (common.options: run.json `options`, else the one option `target`)
  D["cfg"]     = the merged run configuration (surcharge roles)
  D["scenarios"], D["flags"] = tfe_model.scenarios / tfe_model.flags (the scenario totals and the `when` flags of the spec)

Row model: the chunk analyses hold one row per requirement x option (x position). The workbook shows ONE row per requirement
with one column block per option (fields opt.<option id>.*, sheet Schaetzung), the estimation positions of requirements above the largest size on
their own sheet, and per option the on-top lines (development total, PM/SA/BA/QA surcharges, fixed phases, technical migration tasks)
on Zuschlaege_und_Phasen. Sizes stay labels of the scale (estimation.sizes); person days are formulas against the Parameter sheet's mapping table.

Scenario mode (run.json `scenarios`, `estimation.integration_platform` or `fixed_phases_seed`, or TM / RF rows): the rows carry
their class (Klasse), the integration platform effort (is_size) and the saving of a refactoring row (saved_size, saves); Zuschlaege_und_
Phasen holds one block per SCENARIO (platform development of its classes, the saving, the surcharges on both areas, its fixed phases, the
integration platform development) - the one source every total (Szenarien, Summen, Vergleich, Management Summary) sums by scenario label.
spec_context(cfg) hands the engine the flags and the scenario set of the deliverables spec. No code locator reaches a cell (the
deliverable's `code_locators: false`): the lookup's classes stay in the analysis, the row cites the code-analysis row it extends.

System mode (run.json `systems`): system_book.py builds the long-form estimation (one row per work package), the
pass-through sheets, the views, the completeness sheet and the surcharges per system option; the sys_* datasets below hand them to the
engine, spec_context the flags (system_mode, system_single | system_multi, ...) and the repeat sets (systems, scenarios, passthrough, ...).
Every scenario-mode dataset stays as it was; in system mode it is not used by any sheet.
"""
import os, re, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tfe_model as TM
import system_book as SB


def spec_context(cfg):
    """engine hook (common.deliverables_spec): the `when` flags and, in scenario mode, the repeat set `scenarios` ({s.id|label|option|...};
    f_epic / f_release / f_class = the scenario's development over the row of a Summen block - its classes, minus its saving)"""
    from common import options, labels
    if SB.active(cfg):   # system mode: its own flags and sets (the scenario set never applies)
        try: b = SB.Book(cfg, SB.labeller(labels()))
        except SystemExit:   # a broken systems configuration: `dbcx build_excel --check` lists its errors (validate.check_config); empty sets meanwhile
            return {"flags": {"system_mode": True}, "sets": SB.EMPTY_SETS}
        return {"flags": b.flags(), "sets": b.spec_sets(), "renames": b.renames()}
    opts = options(cfg); f = TM.flags(cfg, opts, TM.requirements(cfg.get("_run_dir")))
    if not f["scenario_mode"]: return {"flags": f, "sets": {}}
    L = labels(); sh = "Schaetzung" if (cfg.get("languages") or {}).get("deliverable") == "de" else "Estimation"; items = []
    for x in TM.scenarios(cfg, opts):
        o = x["option"]; every = not f["row_classes"] or set(x["classes"]) >= set(TM.ROW_CLASSES); sav = x["subtract_savings"] and f.get(f"savings_{o}")
        def dev(col, crit):   # the scenario's classes over the rows matching crit
            if every: return f"SUMIFS({{rng:{sh}.pd_{o}}},{{rng:{sh}.{col}}},{crit})"
            return "+".join(f'SUMIFS({{rng:{sh}.pd_{o}}},{{rng:{sh}.{col}}},{crit},{{rng:{sh}.klasse}},"{L.get(c + "_cls", c)}")' for c in x["classes"])
        cls = "" if every else "(" + ",".join(f'{{row}}="{L.get(c + "_cls", c)}"' for c in x["classes"]).join(["OR(", ")"]) + ")*"
        items.append(dict(x, f_epic=dev("epic", "{row}") + (f"-SUMIFS({{rng:{sh}.save_pd_{o}}},{{rng:{sh}.epic}},{{row}})" if sav else ""),
                          f_release=dev("release", "{row}") + (f"-SUMIFS({{rng:{sh}.save_pd_{o}}},{{rng:{sh}.release}},{{row}})" if sav else ""),
                          f_class=f"{cls}SUMIFS({{rng:{sh}.pd_{o}}},{{rng:{sh}.klasse}},{{row}})" + (f'-IF({{row}}="{L.get("refactoring_cls")}",SUM({{rng:{sh}.save_pd_{o}}}),0)' if sav else "")))
    return {"flags": f, "sets": {"scenarios": {"as": "s", "items": items}}}


def load(D, ROOT, INTERIM):
    def lj(rel, default):
        p = os.path.join(ROOT, rel)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default
    from common import options, project, fmt
    D["sum"] = D["cons"].get("SUMMARY")
    D["chunks"] = lj("state/scopes.json", {"scopes": {}})
    D["cfg"] = project(); D["options"] = options(D["cfg"])
    if SB.active(D["cfg"]):   # system mode: the system book; the scenario datasets see no scenarios and no scenario flags
        try: D["book"] = SB.Book(D["cfg"], g, D)
        except SystemExit as ex: raise ValueError(f"{ex} (dbcx build_excel --check lists every configuration error)")   # an Exception: --check reports and goes on
        D["scenarios"] = []; D["flags"] = D["book"].flags()
    else:
        D["book"] = None; D["scenarios"] = TM.scenarios(D["cfg"], D["options"]); D["flags"] = TM.flags(D["cfg"], D["options"], D["req"]["requirements"])
    D["area"] = {"platform": fmt("{target.platform}", D["cfg"]), "is": fmt("{estimation.integration_platform}", D["cfg"])}   # the spec's area labels
    D["decisions"] = {k: v for k, v in TM.decisions(D["cfg"]).items() if v.get("drop") or v.get("merge_into")}


def available(D, name):
    if name in ("sum", "summary", "SUMMARY"): return bool(D["sum"])
    if name == "estimation": return bool(D["scopes"])
    return None


def g(v, ctx=None):   # the label lookup is injected by build_excel at import time (see _bind)
    return _G(v, ctx) if _G else v
_G = None
def _bind(label_fn):
    global _G; _G = label_fn


def num(v):
    """'1.5' | '1,5' | '3 PD' | 3 -> float; anything unusable -> 0.0 (visible as a missing figure, never guessed)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool): return float(v)
    s = str(v or "").strip().replace(",", "."); out = ""
    for ch in s:
        if ch.isdigit() or (ch == "." and "." not in out) or (ch == "-" and not out): out += ch
        elif out: break
    try: return float(out)
    except ValueError: return 0.0


def chunk_areas(D, scope):
    """The epic names of a chunk, for a client-facing 'Area' column (chunk ids like epic-03 never reach a deliverable)."""
    meta = (D["chunks"].get("scopes", {}).get(scope) or {}).get("meta") or {}
    return meta.get("EPICS") or scope


def _rows(D):
    """every estimation row of every chunk: (row, scope); the first occurrence of (req_id, option, position) wins"""
    seen, out = set(), []
    for scope in sorted(D["scopes"]):
        for e in D["scopes"][scope].get("estimation", []) or []:
            k = ((e.get("req_id") or "").strip(), (e.get("option") or "").strip(), str(e.get("position") or "").strip())
            if not k[0] or k in seen: continue
            seen.add(k); out.append((e, scope))
    return out


def _evidence(e, D=None):
    """the row's evidence plus the classes a narrow code lookup read (repository locators -> Grundlage Code); in scenario mode the
    lookup's classes stay in the analysis and the row cites the code-analysis row the lookup extends instead"""
    ev = list(e.get("evidence") or [])
    if D and D["flags"]["scenario_mode"]:
        return ev + ([e["lookup_extends"]] if e.get("lookup_locators") and e.get("lookup_extends") and e["lookup_extends"] not in ev else [])
    return ev + [x for x in (e.get("lookup_locators") or []) if x not in ev]


def _opt(e, D=None):
    out = {"approach": e.get("approach", ""), "size": str(e.get("size") or ""), "assumption": e.get("estimation_assumption", ""), "evidence": _evidence(e, D),
           "derivation": e.get("derivation", ""), "mechanism": e.get("mechanism", ""), "carried_by": e.get("carried_by", "")}
    if D and D["flags"]["scenario_mode"]:
        out.update({"is_size": str(e.get("is_size") or ""), "is_note": e.get("is_note", ""), "saved_size": str(e.get("saved_size") or ""), "saves": e.get("saves") or []})
    return out


def ds_requirements(D):
    """the client's list as received; with decisions a merged row follows its target, marked 'in <id> enthalten', a dropped row is left out
    (its Abgrenzungen line names the decision)"""
    def one(r, title=None):
        return {"id": r["id"], "group": r.get("group", ""), "epic": r.get("epic", ""), "title": r.get("title", "") if title is None else title, "description": r.get("description", ""),
                "acceptance_criteria": r.get("acceptance_criteria", ""), "exclusions": r.get("exclusions", ""), "references": r.get("references", []),
                "phase": r.get("phase", ""), "priority": r.get("priority", ""), "sources": r.get("sources", []), "extra": r.get("extra") or {}}
    dec = D.get("decisions") or {}
    if not dec: return [one(r) for r in D["req"]["requirements"]]
    by = {r["id"]: r for r in D["req"]["requirements"]}; out = []
    for r in D["req"]["requirements"]:
        if r["id"] in dec: continue
        out.append(one(r))
        out += [one(by[k], f"{by[k].get('title', '')} ({g('_merged_into').replace('{id}', r['id'])})") for k, d in dec.items() if d.get("merge_into") == r["id"] and k in by]
    return out


def ds_estimation(D):
    """One row per requirement of the client's list (client order) with one block per option (opt.<id>.*). A requirement an option
    never estimated reads NOT-ASSESSED in that block; an estimated requirement missing from the list is appended."""
    main, epic, scopes = {}, {}, {}
    for e, scope in _rows(D):
        if str(e.get("position") or "").strip(): continue
        main[(e["req_id"].strip(), e["option"].strip())] = e; epic.setdefault(e["req_id"].strip(), e.get("epic", "")); scopes.setdefault(e["req_id"].strip(), scope)
    req = {r["id"]: r for r in D["req"]["requirements"]}
    gone = set(D.get("decisions") or {})   # merged and dropped rows have no estimation row
    ids = [r["id"] for r in D["req"]["requirements"] if r["id"] not in gone] + [i for i in dict.fromkeys(k[0] for k in main) if i not in req and i not in gone]
    rows = []
    for rid in ids:
        r = req.get(rid, {})
        row = {"req_id": rid, "title": r.get("title", ""), "epic": epic.get(rid) or r.get("epic", ""), "release": r.get("phase", ""), "priority": r.get("priority", ""), "group": r.get("group", ""), "scope": scopes.get(rid, ""), "extra": r.get("extra") or {}, "opt": {}}
        if D["flags"]["scenario_mode"]: row["klasse"] = TM.row_class(r)
        for o in D["options"]:
            e = main.get((rid, o["id"]))
            if e: row["opt"][o["id"]] = _opt(e, D)
            elif D["flags"]["scenario_mode"] and not TM.applies(r, o):   # a refactoring row of a greenfield option: no estimate, the row's origin is its basis
                row["opt"][o["id"]] = {"approach": "NOT-APPLICABLE", "size": "", "assumption": "", "evidence": list(r.get("source") or []), "derivation": "", "mechanism": "", "carried_by": "", "is_size": "", "is_note": "", "saved_size": "", "saves": []}
            else: row["opt"][o["id"]] = {"approach": "NOT-ASSESSED", "size": "", "assumption": "", "evidence": [], "derivation": "", "mechanism": "", "carried_by": ""}
        rows.append(row)
    return rows


def ds_positions(D):
    """The estimation positions of requirements above the largest size (each at most that size), in list order; the requirement's own PT on Schaetzung
    is the SUMIFS over these rows."""
    lab = {o["id"]: o["label"] for o in D["options"]}; order = {r["id"]: i for i, r in enumerate(D["req"]["requirements"])}
    out = []
    for e, scope in _rows(D):
        pos = str(e.get("position") or "").strip()
        if not pos: continue
        rid, oid = e["req_id"].strip(), e["option"].strip()
        out.append(dict(_opt(e, D), scope=scope, req_id=rid, position=pos, option=lab.get(oid, oid), option_id=oid, title=e.get("position_title", "")))
    return sorted(out, key=lambda x: (order.get(x["req_id"], 10 ** 6), x["option_id"], num(x["position"])))


def ds_ontop(D):
    """Per option: the development total (formula over Schaetzung), one line per surcharge role (formula: development x the option's
    rate from the Parameter table), then the fixed phases and technical migration tasks of the consolidation (typed, editable PD)."""
    from common import fmt
    roles = [s.get("role") for s in (D["cfg"].get("estimation") or {}).get("surcharges", []) if s.get("role")]
    phases = (D["sum"] or {}).get("fixed_phases", []) or []; out = []
    if D["flags"]["scenario_mode"]: return ontop_scenarios(D, roles, phases)
    for o in D["options"]:
        oid, lab = o["id"], o["label"]; dev = f"SUM({{rng:{est_sheet(D)}.pd_{oid}}})"
        out.append({"id": f"{oid}-DEV", "option": lab, "block": "dev", "title": g("_dev_title"), "pd_formula": f"={dev}", "rate": "", "rate_formula": "", "derivation": fmt(g("_dev_derivation"), D["cfg"]), "evidence": []})
        for ro in roles:
            out.append({"id": f"{oid}-{ro}", "option": lab, "block": "surcharge", "title": g(f"{ro}_role"), "rate": "", "rate_formula": f"={{pt:surcharge.{oid}.{ro}}}/100",
                        "pd_formula": f"={dev}*{{pt:surcharge.{oid}.{ro}}}/100", "derivation": g("_surcharge_derivation"), "evidence": []})
        for p in phases:
            if (p.get("option") or "").strip() != oid: continue
            out.append({"id": p.get("id", ""), "option": lab, "block": p.get("block", "phase"), "title": p.get("title", ""), "pd": num(p.get("pd")), "pd_formula": "", "rate": "", "rate_formula": "",
                        "derivation": p.get("derivation", ""), "evidence": p.get("evidence", [])})
    return out


def class_sum(D, col, s):
    """formula fragment: the column over the rows of the scenario's classes (SUMIFS on the Klasse label; SUM when it takes every class)"""
    sh = est_sheet(D)
    if not D["flags"]["row_classes"] or set(s["classes"]) >= set(TM.ROW_CLASSES): return f"SUM({{rng:{sh}.{col}}})"
    return "+".join(f'SUMIFS({{rng:{sh}.{col}}},{{rng:{sh}.klasse}},"{g(c, "cls")}")' for c in s["classes"])


def ontop_scenarios(D, roles, phases):
    """scenario mode: per scenario the platform development of its classes, the saving (subtract_savings), the surcharges on it, its fixed
    phases (SUMMARY rows with `scenario`; without declared scenarios the option's rows), then the integration platform development and its
    surcharges (same rates, own lines). `line` names the row of the Szenarien sheet a line sums into."""
    from common import fmt
    out = []; declared = bool(D["cfg"].get("scenarios")); P_, I_ = D["area"]["platform"], D["area"]["is"]; lp = g("_line_phases"); G = lambda k: fmt(g(k), D["cfg"])
    cls_txt = lambda s: ", ".join(g(c, "cls") for c in s["classes"])
    for s in D["scenarios"]:
        o, lab = s["option"], s["label"]; base = {"scenario": lab, "option": s["option_label"], "rate": "", "rate_formula": "", "evidence": []}
        dev = class_sum(D, f"pd_{o}", s); sav = f"-SUM({{rng:{est_sheet(D)}.save_pd_{o}}})" if s["subtract_savings"] and D["flags"].get(f"savings_{o}") else ""
        out.append(dict(base, id=f"{s['id']}-DEV", area=P_, block="dev", title=g("_dev_title_classes").replace("{classes}", cls_txt(s)), line=g("_line_dev"), pd_formula=f"={dev}", derivation=G("_dev_derivation_scenario")))
        if sav: out.append(dict(base, id=f"{s['id']}-SAV", area=P_, block="saving", title=g("_saving_title"), line=g("_line_saving"), pd_formula=f"={sav}", derivation=g("_saving_derivation")))
        net = f"({dev}{sav})" if sav else f"({dev})"
        for ro in roles:
            out.append(dict(base, id=f"{s['id']}-{ro}", area=P_, block="surcharge", title=g(f"{ro}_role"), line=g(f"{ro}_role"), rate_formula=f"={{pt:surcharge.{o}.{ro}}}/100",
                            pd_formula=f"={net}*{{pt:surcharge.{o}.{ro}}}/100", derivation=g("_surcharge_derivation")))
        for ph in phases:
            if (ph.get("scenario") or ("" if declared else ph.get("option")) or "").strip() != s["id"]: continue
            out.append(dict(base, id=ph.get("id", ""), area=P_, block=ph.get("block", "phase"), title=ph.get("title", ""), line=lp, pd=num(ph.get("pd")), pd_formula="",
                            derivation=ph.get("derivation", ""), evidence=ph.get("evidence", [])))
        if D["flags"]["is"]:
            isd = class_sum(D, f"is_pd_{o}", s)
            out.append(dict(base, id=f"{s['id']}-IS", area=I_, block="dev", title=G("_is_dev_title").replace("{classes}", cls_txt(s)), line=g("_line_dev"), pd_formula=f"={isd}", derivation=G("_is_dev_derivation")))
            for ro in roles:
                out.append(dict(base, id=f"{s['id']}-IS-{ro}", area=I_, block="surcharge", title=g(f"{ro}_role"), line=g(f"{ro}_role"), rate_formula=f"={{pt:surcharge.{o}.{ro}}}/100",
                                pd_formula=f"=({isd})*{{pt:surcharge.{o}.{ro}}}/100", derivation=G("_is_surcharge_derivation")))
    return out


def ds_scenarios(D):
    """one row per scenario (the Szenarien / Summen / Vergleich rows sum ZP by this label)"""
    return [{"label": s["label"], "id": s["id"], "option": s["option_label"]} for s in D["scenarios"]] if D["flags"]["scenario_mode"] else []


def ds_scenario_lines(D):
    """the line labels of the Szenarien sheet: field `platform` (development, saving, surcharges, fixed phases) and `is` (development, surcharges)"""
    if not D["flags"]["scenario_mode"]: return []
    roles = [g(f"{s.get('role')}_role") for s in (D["cfg"].get("estimation") or {}).get("surcharges", []) if s.get("role")]
    plat = [g("_line_dev")] + ([g("_line_saving")] if any(s["subtract_savings"] and D["flags"].get(f"savings_{s['option']}") for s in D["scenarios"]) else []) + roles + [g("_line_phases")]
    return [{"platform": x} for x in plat] + ([{"is": x} for x in [g("_line_dev")] + roles] if D["flags"]["is"] else [])


def ds_classes(D):
    """the row classes present in the list, as the Klasse column shows them (Summen: development per class and option)"""
    if not D["flags"]["row_classes"]: return []
    have = {TM.row_class(r) for r in D["req"]["requirements"]}
    return [{"label": g(c, "cls")} for c in TM.ROW_CLASSES if c in have]


def est_sheet(D):
    """the estimation sheet's name in the deliverable language (deliverables.de.json Schaetzung, .en.json Estimation)"""
    return "Schaetzung" if (D["cfg"].get("languages") or {}).get("deliverable") == "de" else "Estimation"


def ae_id(v):
    """The method's own register ids are AE-nn; a legacy 'A-nn' would collide with the engine's client assumptions (sheet Annahmen)."""
    return re.sub(r"^A-(\d+)$", r"AE-\1", str(v or "").strip())


def ds_exclusions(D):
    """The consolidated exclusions / dependencies register when it exists (the consolidator owns completeness), else the chunk rows; then one
    line per derived row the client dropped, naming the decision"""
    return _exclusions(D) + dropped_rows(D)


def dropped_rows(D):
    by = {r["id"]: r for r in D["req"]["requirements"]}; out = []
    for k, d in (D.get("decisions") or {}).items():
        if not d.get("drop") or k not in by: continue
        b = basis_text(D, d.get("basis", ""))
        out.append({"id": k, "scope": g("_all_options"), "requirement_ids": [k], "kind": "exclusion", "assumption": g("_dropped_row").replace("{title}", by[k].get("title", "")),
                    "effect": g("_dropped_effect") + (" " + g("_decision_basis").replace("{basis}", b) if b else "")})
    return out


def basis_text(D, basis):
    """the basis of a decision as the client reads it: an assumption the client answered is a statement of the client (it has no row on
    the Annahmen sheet), an open one keeps its A-nn"""
    from common import load_questions, fmt
    from xl_transform import assumption_numbers, client_answered, is_client
    qs = load_questions(); nums = assumption_numbers(qs)
    if any(nums.get(q.get("id")) == basis and is_client(q) and client_answered(q) for q in qs): return fmt(g("src_client_answer"), D["cfg"])
    return basis


def _exclusions(D):
    if D["sum"]:
        return [{"id": ae_id(a.get("id")), "scope": a.get("scope", ""), "requirement_ids": a.get("requirement_ids", []), "kind": a.get("kind", ""),
                 "assumption": a.get("assumption", ""), "effect": a.get("effect", "")} for a in D["sum"].get("assumptions", []) or []]
    rows = []
    for scope in sorted(D["scopes"]):
        for a in D["scopes"][scope].get("assumptions", []) or []:
            rows.append({"id": ae_id(a.get("id")), "scope": chunk_areas(D, scope), "requirement_ids": a.get("requirement_ids", []), "kind": a.get("kind", ""),
                         "assumption": a.get("assumption", ""), "effect": a.get("effect", "")})
    return rows


def ds_risks(D):
    order = {"blocker": 0, "major": 1, "minor": 2}; lab = {o["id"]: o["label"] for o in D["options"]}
    rows = [{"id": r.get("id", ""), "risk": r.get("risk", ""), "options": [lab.get(x, x) for x in r.get("options") or []] or [g("_all_options")], "affected": r.get("affected", []),
             "likelihood": r.get("likelihood", ""), "impact": r.get("impact", ""), "mitigation": r.get("mitigation", ""), "evidence": r.get("evidence", [])}
            for r in (D["sum"] or {}).get("risks", []) or []]
    return sorted(rows, key=lambda x: order.get(x["impact"], 3))


# ------------------------------------------------------------------ system mode (system_book.py); empty without run.json `systems`
def _bk(D): return D.get("book")
def ds_wps(D): return _bk(D).wps if _bk(D) else []
def ds_sys_positions(D): return _bk(D).positions if _bk(D) else []
def ds_sys_ontop(D): return _bk(D).ontop_rows() if _bk(D) else []
def ds_sys_scenarios(D): return _bk(D).scenario_rows() if _bk(D) else []
def ds_sys_scenario_rows(D): return [{"label": s["label"]} for s in _bk(D).scenarios] if _bk(D) else []
def ds_sum_systems(D): return _bk(D).sum_systems() if _bk(D) else []
def ds_completeness(D): return _bk(D).completeness() if _bk(D) else []
def ds_other_rows(D): return _bk(D).other_rows() if _bk(D) else []
def ds_components(D): return _bk(D).spec_sets()["components"]["items"] if _bk(D) else []
def ds_passthrough(D, group=None):
    """one pass-through sheet: the rows of the group's client sheet (`passthrough:<group>`)"""
    if not _bk(D): return []
    return next((p["rows"] for p in _bk(D).passthrough() if p["group"] == group), [])


DATASETS = {"requirements": ds_requirements, "estimation": ds_estimation, "positions": ds_positions, "ontop": ds_ontop, "exclusions": ds_exclusions, "risks": ds_risks,
            "scenarios": ds_scenarios, "scenario_lines": ds_scenario_lines, "classes": ds_classes,
            "wps": ds_wps, "sys_positions": ds_sys_positions, "sys_ontop": ds_sys_ontop, "sys_scenarios": ds_sys_scenarios, "sys_scenario_rows": ds_sys_scenario_rows,
            "sum_systems": ds_sum_systems, "completeness": ds_completeness, "other_rows": ds_other_rows, "components": ds_components, "passthrough": ds_passthrough}
