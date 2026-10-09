"""Scanner adapter for SAP Commerce (hybris) code bases (platform pack sap-commerce).
Units = extensions (extensioninfo.xml). Dependencies = requires-extension. Signals from *-items.xml, *-spring.xml,
process definitions, ImpEx, backoffice config, acceleratoraddon folders; platform facts from build.number,
localextensions.xml and CCv2 manifest.json.
"""
import json, os, re, sys
from xml.etree import ElementTree as ET
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
import sap_repo, active_extensions, template_diff, process_reach, impex_rows   # pack tools (read-only resolvers)

UNIT_MANIFEST = "extensioninfo.xml"
STD_PKG = ("de.hybris.", "com.sap.", "com.hybris.")

def _ns(root): return root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""

def discover_units(roots, ctx):
    out = []
    for r in roots:
        for dp, dns, fns in ctx["walk"](r):
            if UNIT_MANIFEST in fns:
                mp = os.path.join(dp, UNIT_MANIFEST); meta = {}; name = os.path.basename(dp); desc = ""
                try:
                    rt = ET.parse(mp).getroot(); ns = _ns(rt); ext = rt.find(f"{ns}extension")
                    if ext is not None:
                        name = ext.get("name", name); desc = ext.get("description", "") or ""
                        meta = {m.get("key"): m.get("value") for m in ext.findall(f"{ns}meta")}
                        meta["webmodule"] = ext.find(f"{ns}webmodule") is not None; meta["coremodule"] = ext.find(f"{ns}coremodule") is not None
                except ET.ParseError as e:
                    desc = f"parse error: {e}"
                out.append({"name": name, "path": dp, "manifest": mp, "description": desc, "meta": meta})
    return out

def parse_dependencies(unit, ctx):
    try:
        rt = ET.parse(unit["manifest"]).getroot(); ns = _ns(rt)
        return [r.get("name") for r in rt.iter(f"{ns}requires-extension") if r.get("name")]
    except ET.ParseError:
        return []

def is_standard_unit(name, ctx):
    return None  # knowledge.json standard_units (generated from hybris/bin/{platform,modules}) decides

def _layout_root(ctx):
    roots = ctx.get("roots") or []
    return next((r for r in roots if sap_repo.layout(r)["core"]), roots[0] if roots else None)

def activation(ctx):
    """active_extensions.resolve() of the scanned repository, computed once per scan."""
    if "_sap_activation" not in ctx:
        r = _layout_root(ctx); ctx["_sap_activation"] = active_extensions.resolve(r) if r else None
        L = sap_repo.layout(r) if r else {}; ctx["_sap_tree"] = sap_repo.extensions_in_tree(L.get("bin")) if r else {}; ctx["_sap_layout"] = L
    return ctx["_sap_activation"]

_BEAN = re.compile(r"<bean\b[^>]*>", re.S); _ALIAS = re.compile(r"<alias\b[^>]*>", re.S)

def _spring_defs(path):
    """[(kind bean|alias, id, target class|alias name, line)] of one Spring XML (comments ignored, either quote style)."""
    try: txt = sap_repo.strip_xml_comments(sap_repo.read_text(path))
    except OSError: return []
    out = [("bean", sap_repo.attr(m.group(0), "id") or sap_repo.attr(m.group(0), "name"), sap_repo.attr(m.group(0), "class") or "", sap_repo.line_of(txt, m.start()), m.group(0)) for m in _BEAN.finditer(txt)]
    out += [("alias", sap_repo.attr(m.group(0), "alias"), sap_repo.attr(m.group(0), "name") or "", sap_repo.line_of(txt, m.start()), m.group(0)) for m in _ALIAS.finditer(txt)]
    return [d for d in out if d[1]]

def _is_spring(rp, base):
    rp = rp.replace(os.sep, "/"); return base.endswith(".xml") and ("spring" in base) and "/testsrc/" not in rp and "/test/" not in rp

def standard_beans(ctx):
    """{bean id or alias: [(extension, active, kind, target, locator)]} over the Spring files of every standard extension in the tree."""
    if "_sap_std_beans" in ctx: return ctx["_sap_std_beans"]
    act = activation(ctx) or {"extensions": {}}; idx = {}; L = ctx.get("_sap_layout") or {}
    for n, e in (ctx.get("_sap_tree") or {}).items():
        if not e["standard"]: continue
        on = (act["extensions"].get(n) or {}).get("state") == "active"
        for dp, dns, fns in os.walk(e["dir"]):
            dns[:] = [d for d in dns if d not in sap_repo.SKIP and d not in ("testsrc", "src", "gensrc", "node_modules", "_ui", "_ui-src") and not d.startswith(".")]
            for f in fns:
                if _is_spring(os.path.join(dp, f), f):
                    for k, i, t, line, _ in _spring_defs(os.path.join(dp, f)): idx.setdefault(i, []).append((n, on, k, t, f"{os.path.relpath(os.path.join(dp, f), L.get('root', dp)).replace(os.sep, '/')}:{line}"))
    ctx["_sap_std_beans"] = idx; return idx

def resolve_overrides(unit, cands, ctx):
    """Every override candidate gets `target` and `resolution` - overrides-standard (a bean id or alias an ACTIVE
    standard extension defines), no-op-standard-alias (repeats the standard's own alias), target-not-loaded (defined only in inactive standard
    extensions), custom-id / new-id (no standard definition), not-decidable (standard code not in the repository), aop. Duplicates of one
    file:line are dropped. The list stays a CANDIDATE list; only `overrides-standard` rows are overrides, and only after the analyst's check."""
    act = activation(ctx); std = standard_beans(ctx); in_repo = bool(act and act["layout"].get("platform_in_repo")); out = []; seen = set()
    for c in cands:
        if c.get("evidence") in seen: continue
        seen.add(c.get("evidence")); w = c.get("what", ""); c = dict(c)
        m = re.search(r"<alias\b[^>]*", w); tgt = sap_repo.attr(w, "alias") if m else None; name = sap_repo.attr(w, "name") if m else None
        if not m:
            mm = re.search(r"bean id (\S+) redefined", w) or re.search(r"<bean\b[^>]*\bid\s*=\s*['\"]([^'\"]+)", w); tgt = mm.group(1) if mm else None
        c["target"] = tgt
        if "<aop:" in w: c["resolution"] = "aop"
        elif not tgt: c["resolution"] = "not-decidable (no bean id in the line)"
        elif not in_repo: c["resolution"] = "not-decidable (standard code not in the repository)"
        else:
            d = std.get(tgt, []); live = [x for x in d if x[1]]
            if live and name and any(x[2] == "alias" and x[3] == name for x in live): c["resolution"] = "no-op-standard-alias"; c["standard_at"] = [x[4] for x in live][:3]
            elif live: c["resolution"] = "overrides-standard"; c["standard_at"] = [f"{x[0]}: {x[4]}" for x in live][:3]
            elif d: c["resolution"] = "target-not-loaded"; c["standard_at"] = [f"{x[0]} (inactive): {x[4]}" for x in d][:3]
            else: c["resolution"] = "new-id"
        out.append(c)
    return out

def _addon_footprints(unit, ctx):
    """Install evidence of an AddOn (storefront requires-extension, storefront-prefixed lines addoninstall writes into
    the AddOn's project.properties, manifest storefrontAddons) plus project.properties lines absent from project.properties.template."""
    L = ctx.get("_sap_layout") or {}; tree = ctx.get("_sap_tree") or {}; rel = lambda p: os.path.relpath(p, L.get("root", unit["path"])).replace(os.sep, "/"); name = unit["name"]; ev = []
    sfs = {n: e for n, e in tree.items() if not e["standard"] and e.get("webmodule") and n != name}
    for n, e in sfs.items():
        for r, line in e["requires"]:
            if r == name: ev.append(f"{rel(e['manifest'])}:{line} (storefront {n} requires-extension)")
    pp, tp = os.path.join(unit["path"], "project.properties"), os.path.join(unit["path"], "project.properties.template")
    hand = []
    if os.path.isfile(pp):
        tl = {re.sub(r"\\:", ":", f"{k}={v}") for k, v, _ in sap_repo.read_properties(tp)} if os.path.isfile(tp) else None
        for k, v, line in sap_repo.read_properties(pp):
            if k.split(".")[0] in sfs: ev.append(f"{rel(pp)}:{line} ({k.split('.')[0]}.{k.split('.', 1)[1].split('.')[0]} - line addoninstall writes)")
            elif tl is not None and not any(re.sub(r"\\:", ":", f"{k}={v}") == t.replace("yacceleratorstorefront", k.split(".")[0]) or f"{k}={v}" == t for t in tl): hand.append(f"{rel(pp)}:{line}")
    man = L.get("manifest_json") or {}
    if any((a.get("addon") if isinstance(a, dict) else a) == name for a in man.get("storefrontAddons") or []): ev.append(f"{rel(L['manifest'])} storefrontAddons[] names {name}")
    return ev[:6], hand[:6]

def unit_activation(unit, ctx):
    """{loaded_in, activation_resolved} of one unit from active_extensions (also the scanner's fallback when a run adapter wraps this one)."""
    act = activation(ctx)
    if not act: return None
    a = act["extensions"].get(unit["name"]) or active_extensions.query(act, unit["name"])
    return {"loaded_in": list(a.get("loaded_in", [])), "activation_resolved": {"state": a["state"], "evidence": a["evidence"][:4]}}

def unit_signals(unit, files, ctx):
    sig = {"schema_new_types": 0, "schema_extended_types": 0, "schema_attributes_on_extended_types": 0, "schema_relations": 0, "schema_enums": 0, "di_definitions": 0, "override_candidates": [], "workflows": [], "content_custom_component_types": [], "third_party_required": [], "loaded_in": [], "has_plugin_dir": False, "categories_hint": [], "extra": {}, "triggers": {}}
    std_addons = set(ctx["knowledge"].get("third_party_packages", [])); act = activation(ctx); std = standard_beans(ctx); trig = sig["triggers"]
    impex = {"files": 0, "data_rows": 0, "comment_only": []}; tests = set(ctx["knowledge"].get("test_dir_markers", [])); procs = []
    for ap, rp, ext in files:
        base = os.path.basename(ap)
        if base.endswith("-items.xml"):
            try:
                rt = ET.parse(ap).getroot()
                for it in rt.iter("itemtype"):
                    if (it.get("autocreate", "true").lower() == "false"): sig["schema_extended_types"] += 1; sig["schema_attributes_on_extended_types"] += len(list(it.iter("attribute")))
                    else: sig["schema_new_types"] += 1
                sig["schema_relations"] += len(list(rt.iter("relation"))); sig["schema_enums"] += len(list(rt.iter("enumtype")))
            except ET.ParseError: pass
        elif base.endswith("-spring.xml") or (ext == ".xml" and "/web/webroot/WEB-INF/" in rp.replace(os.sep, "/") and "spring" in base):
            txt = open(ap, encoding="utf-8", errors="ignore").read()
            sig["di_definitions"] += len(re.findall(r"<bean\s", txt))
            for k, i, t, n, tag in _spring_defs(ap):   # XML-aware: either quote style, any attribute order, comments ignored
                if k == "alias": sig["override_candidates"].append({"what": tag.strip()[:120], "how": "bean-alias", "evidence": f"{rp}:{n}"})
                elif t and not t.startswith(STD_PKG) and (i.startswith("default") or i in std): sig["override_candidates"].append({"what": f"bean id {i} redefined with {t}", "how": "bean-id-redefinition", "evidence": f"{rp}:{n}"})
        elif ("/process/" in rp.replace(os.sep, "/") or base.endswith("-process.xml")) and ext == ".xml" and not tests & set(rp.replace(os.sep, "/").split("/")):
            r = process_reach.analyse(ap)
            if r:
                sig["workflows"].append(r["name"])
                tt = [f"{t['then']} after {t['delay']}" + (" (rejoins a SUCCEEDED end)" if t["reaches_success"] else "") for w in r["waits"] for t in w["timeouts"]]
                procs.append((bool(r["unreachable"]) or any(t["reaches_success"] for w in r["waits"] for t in w["timeouts"]), f"{rp}: start {r['start']}, {len(r['unreachable'])} of {len(r['nodes'])} nodes unreachable" + (f" ({', '.join(r['unreachable'][:6])})" if r["unreachable"] else "") + (f"; timeout -> {'; '.join(tt[:3])}" if tt else "")))
        elif base.endswith("backoffice-config.xml"): sig["categories_hint"].append("admin")
        if ext == ".impex":
            st = impex_rows.file_stats(ap); impex["files"] += 1; impex["data_rows"] += st["data_rows"]
            if st["comment_only"]: impex["comment_only"].append(rp)
        if "/acceleratoraddon/" in rp.replace(os.sep, "/"): sig["has_plugin_dir"] = True
    if procs: trig["process-reachability"] = [t for _, t in sorted(procs, key=lambda x: not x[0])]   # unreachable nodes / timeout->success first
    deps = parse_dependencies(unit, ctx)
    sig["third_party_required"] = [d for d in deps if d in std_addons]
    if impex["files"]: sig["extra"]["impex"] = {"files": impex["files"], "data_rows": impex["data_rows"], "comment_only_files": impex["comment_only"][:20], "rule": "impex_rows.file_stats: quoted multi-line values and '\\' continuations = one row, Type[modifier] headers recognised, a comment-only file has 0 rows"}
    sig.update(unit_activation(unit, ctx) or {})
    if sig["has_plugin_dir"] or unit["name"].endswith("addon"):
        ev, hand = _addon_footprints(unit, ctx)
        trig["addon-installed"] = ev or ["no install footprint found (no storefront requires-extension, no storefront-prefixed project.properties line, not in storefrontAddons)"]
        if hand: trig["addon-installed"] = trig["addon-installed"][:4] + [f"hand-edit candidates (not in project.properties.template, lost on re-install): {', '.join(hand[:3])}"]
    tree = ctx.get("_sap_tree") or {}
    if unit["name"] in tree:   # rename-normalised template diff (feeds the scanner's template_copy LOC bucket)
        cache = ctx.setdefault("_sap_tpl_files", {}); u = tree[unit["name"]]; uf = template_diff.files_of(u["dir"])
        best = template_diff.detect(u, tree, uf, cache)
        if best:
            d = template_diff.diff(u, tree[best[0]], uf, cache[best[0]], with_files=True)
            copies = {os.path.normpath(os.path.join(u["dir"], f)) for k in ("unchanged-copy", "cosmetic-copy") for f in d["files"][k]}
            if best[0] != "yempty":
                trig["template-copy"] = [f"{best[0]}: {d['counts']['unchanged-copy'] + d['counts']['cosmetic-copy']} unchanged/cosmetic copies, {d['counts']['modified']} modified files (+{d['modified_changed_lines']} lines), {d['counts']['new']} new files"]
            sig["template_diff"] = {"template": d["template"], "counts": d["counts"], "loc": d["loc"], "modified_changed_lines": d["modified_changed_lines"], "detection": {"share": best[1], "matched_paths": best[2]}, "rule": d["rule"], "copies": copies}
    return sig

def classify(unit, signals, metrics, ctx):
    cats = []; deps = set(parse_dependencies(unit, ctx)); name = unit["name"].lower(); meta = unit.get("meta", {})
    if signals.get("has_plugin_dir") or name.endswith("addon"): cats.append("plugin")
    if meta.get("webmodule") and (metrics.get("templates", 0) > 0 or "yacceleratorstorefront" in deps or "storefront" in name): cats.append("frontend")
    if signals.get("api_entry_points") or "commercewebservices" in deps or name.endswith("occ"): cats.append("api")
    if "admin" in signals.get("categories_hint", []) or "backoffice" in deps or "backoffice" in name: cats.append("admin")
    if signals.get("integration_hits") or any(d.startswith(("sapcpi", "sapcore", "odata", "outbound", "integration")) for d in deps): cats.append("integration")
    if "facades" in name or any(d.endswith("facades") for d in deps) and "facade" in name: cats.append("facade")
    if signals.get("schema_new_types") or signals.get("di_definitions", 0) > 5 or "core" in name: cats.append("core")
    if metrics.get("code", 0) == 0 and metrics.get("data_scripts", 0) > 0: cats.append("data")
    if metrics.get("code", 0) == 0 and metrics.get("code_test", 0) > 0: cats.append("test")
    if not cats: cats.append("other")
    allowed = ctx["project"]["unit"]["categories"]
    return [c for c in dict.fromkeys(cats) if c in allowed] or ["other"]

def platform_facts(roots, ctx):
    facts = {"version_hints": {}, "config_files": {}, "standard_code_in_repo": None, "notes": []}
    for r in roots:
        for dp, dns, fns in ctx["walk"](r):
            if "build.number" in fns and dp.replace(os.sep, "/").endswith("hybris/bin/platform"):
                txt = open(os.path.join(dp, "build.number"), encoding="utf-8", errors="ignore").read()
                facts["version_hints"][ctx["rel"](os.path.join(dp, "build.number"))] = re.findall(r"version=([\w.]+)", txt)[:3]; facts["standard_code_in_repo"] = True
            if "localextensions.xml" in fns:
                p = os.path.join(dp, "localextensions.xml")
                try: facts["config_files"][ctx["rel"](p)] = {"extensions": [e.get("name") for e in ET.parse(p).getroot().iter("extension") if e.get("name")]}
                except ET.ParseError: pass
            if "manifest.json" in fns and "node_modules" not in dp:
                p = os.path.join(dp, "manifest.json")
                try:
                    m = json.load(open(p, encoding="utf-8"))
                    if "commerceSuiteVersion" in m:
                        facts["config_files"][ctx["rel"](p)] = {k: m.get(k) for k in ("commerceSuiteVersion", "extensionPacks", "extensions", "storefrontAddons", "aspects")}
                        facts["version_hints"][ctx["rel"](p)] = [m["commerceSuiteVersion"]]
                except Exception: pass
    act = activation(ctx) if ctx.get("roots") else None
    if act:   # the resolved activation (states per extension live in the unit records' activation_resolved)
        facts["active_extensions"] = {"rule": act["rule"], "layout": act["layout"], "counts": act["counts"], "counts_custom": act["counts_custom"], "notes": act["notes"],
                                      "declared_not_provisioned": {n: v["evidence"] for n, v in act["extensions"].items() if v["state"] == "declared-not-provisioned"},
                                      "not_decidable": {n: v["evidence"] for n, v in act["extensions"].items() if v["state"] == "not-decidable"},
                                      "closure_incomplete_below": act["closure_incomplete"]}
    return facts

_STD_SUBDIRS = ("hybris/bin/platform", "hybris/bin/modules", "hybris/bin/ext-accelerator", "hybris/bin/ext-commerce", "hybris/bin/ext-content", "hybris/bin/ext-channel", "hybris/bin/ext-integration", "hybris/bin/ext-backoffice")

def _std_bases(root):
    """The standard dirs sit at the repository root in an on-premise checkout and under core-customize/ (or another wrapper) in a CCv2 repository; look for them at the root and up to two levels below it."""
    def subdirs(d):
        try: return sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)) and not x.startswith("."))
        except OSError: return []
    bases = [root]
    level = [root]
    for _ in range(2):
        level = [os.path.join(d, s) for d in level for s in subdirs(d)]
        bases += level
    return list(dict.fromkeys(bases))

def derive_knowledge(roots, ctx):
    """Standard extensions and standard addons from the platform code shipped with the repository (hybris/bin/platform, hybris/bin/modules, ext-*), wherever the wrapper layout puts them."""
    std, addons = set(), set()
    for r in roots:
        for rb in _std_bases(r):
            for sd in _STD_SUBDIRS:
                base = os.path.join(rb, sd)
                if not os.path.isdir(base): continue
                for u in discover_units([base], ctx):
                    std.add(u["name"])
                    if u["name"].endswith("addon") or os.path.isdir(os.path.join(u["path"], "acceleratoraddon")): addons.add(u["name"])
    out = {}
    if std: out["standard_units"] = sorted(std)
    if addons: out["third_party_packages"] = sorted(addons)
    return out
