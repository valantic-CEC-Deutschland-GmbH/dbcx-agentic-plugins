#!/usr/bin/env python3
"""Automated repository scan (D1 input). Platform-neutral engine + the source pack's adapter (or <project>/overrides/adapter.py).

Usage: dbcx scan_inventory <REPO_ROOT> [more roots]

Writes analysis/inventory/inventory.json (contract below) and analysis/inventory/scan_log.txt.
Everything is heuristic and must be verified by the inventory analyst; every record carries an evidence path.

inventory.json contract (consumed by plan_waves.py, build_excel.py, build_dependency_diagram.py, agents):
{
  "scanned_at", "adapter", "roots": [...],
  "platform": {"version_hints": {file: [..]}, "config_files": {...}, "standard_code_in_repo": bool|null, "notes": [..]},
  "units": {name: {"name","path","evidence","description","meta",
                   "categories": [tokens], "primary_category",
                   "requires": [..], "requires_custom": [..], "requires_standard": [..], "requires_unknown": [..],
                   "metrics": {"code","code_test","templates","js","ts","config","data_scripts","css","total","files"},   # raw: non-blank lines incl. comments, filesystem walk, bucket extensions only
                   "metrics_tracked": {same keys, over `git ls-files` of the unit folder} | null (no git),  "metrics_rule": "<the rule as text>",
                   "metrics_generated", "metrics_template_copy", "metrics_maintained": {same keys} (generator output by header marker or committed
                   reports/ | unchanged or cosmetic copies of the vendor template the adapter's template diff found | the rest), "loc_maintained": int
                   (maintained code+templates+js+ts, the size the wave plan / light pass / claim cap key on), "loc_rule", "template": {template, counts, loc, ...} | null,
                   "data_scripts_effective": non-blank minus comment lines of data scripts, "data_scripts_comment_only_files": [file],
                   "deprecation_hits": [{id,file,line,kind,path_class,lines,snippet}] (this unit's hits; kind = use | definition | import-unused | comment;
                   path_class = src | config | comment | lib | report | generated | test; lines = matching lines in that file, line_list = their numbers (first 20)),  "deprecation_hits_by_id": {id: n},
                   "deprecation_hits_by_class": {path_class: n}, "override_candidates_resolved": {resolution: n}, "activation_resolved": {state, evidence} | null,
                   "triggers": {recipe id: [evidence]} (check recipes of the knowledge, rendered into the unit's analyst brief),
                   "frontend_entry_points","api_entry_points","integration_hits": {signal: n},
                   "schema_new_types","schema_extended_types","schema_attributes_on_extended_types","schema_relations","schema_enums",
                   "di_definitions","override_candidates": [{what,how,evidence}],"shadowing_candidates": [file],
                   "workflows": [..],"content_custom_component_types": [..],"third_party_required": [..],"loaded_in": [..],"has_plugin_dir","extra": {}}},
  "dependency_edges": [{"from","to","to_kind": custom|standard|unknown,"type","evidence"}],
  "deprecation_hits": [{"id","title","unit","file","line","snippet","since","replacement","verify","kind","path_class","lines"}], "deprecation_rule": "<count convention>",
  "standard_units_present_count", "notes": [..]
}
The adapter may implement derive_knowledge(roots, ctx) -> lists written to state/derived_knowledge.json and merged into the knowledge.
"""
import os, re, sys, json, time, fnmatch, subprocess
from collections import defaultdict
if "common" not in sys.modules: sys.path.insert(0, os.environ.get("DBCX_TOOLS") or sys.exit("DBCX_TOOLS is not set: run method tools as `dbcx <tool>`"))   # the engine by name, never by path
from common import RUN as ROOT, DERIVED_PATH, project, knowledge, load_adapter, save_json, is_placeholder, relp
import importlib.util
OPTIONAL_HOOKS = ("resolve_overrides", "unit_activation")   # 0.8 adapter hooks a wrapping run adapter may not re-export

def pack_hooks(adapter, p):
    """Optional hooks the run adapter lacks, taken from the source pack's own adapter (a run overrides/adapter.py that wraps the
    pack adapter would otherwise silently lose them). Returns ({hook: function}, pack adapter path or None)."""
    src = (p.get("_packs") or {}).get("source"); pa = os.path.join(src["_dir"], src.get("adapter", "adapter.py")) if src else None
    missing = [h for h in OPTIONAL_HOOKS if not hasattr(adapter, h)]
    if not missing or not pa or not os.path.exists(pa) or os.path.abspath(pa) == os.path.abspath(adapter.__file__): return {}, None
    spec = importlib.util.spec_from_file_location("dbcx_pack_adapter_hooks", pa); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return {h: getattr(mod, h) for h in missing if hasattr(mod, h)}, pa

OUT_DIR = os.path.join(ROOT, "analysis", "inventory")
LOG = []
def log(m): LOG.append(m); print(m)

GEN_MARKERS = [r"This (?:class|file|code) (?:was|is) (?:automatically )?generated", r"\bGenerated by\b", r"@(?:javax\.annotation\.|jakarta\.annotation\.(?:processing\.)?)?Generated\b",
               r"DO NOT EDIT", r"[Aa]uto-?generated(?! (?:method|constructor) stub| catch block)", r"<p>Java class for .+ complex type", r"@XmlRegistry", r"@(?:jakarta|javax)\.xml\.bind\.annotation\.XmlSchema", r"@WebServiceClient\b"]
REPORT_DIRS = ("reports/", "web/reports/")
LIB_PARTS = {"lib", "libs", "webjars", "bower_components", "vendor", "thirdparty", "third-party", "third_party"}
DEP_RULE = ("deprecation count convention: ONE hit per (pattern, file) - `line` is the first matching non-comment line (else the first match), `lines` counts every "
            "matching line of that file; so `deprecation_hits_by_id` counts FILES, the sum of `lines` counts LINES. path_class: comment (hit line is a comment), "
            "test, report (committed reports/ or web/reports/), generated (generator header marker), lib (embedded library folder or *.min.js), "
            "config (xml/properties/json/impex/csv/sql), src (everything else). Only src hits are candidate runtime findings; raw counts are an upper bound.")

def path_class(unit_rel, bucket, kind, generated, in_test):
    """where a scanner hit sits - only `src` hits are candidate runtime findings."""
    parts = unit_rel.split("/")
    if kind == "comment": return "comment"
    if in_test: return "test"
    if unit_rel.startswith(REPORT_DIRS): return "report"
    if generated: return "generated"
    if LIB_PARTS & set(parts[:-1]) or unit_rel.endswith(".min.js"): return "lib"
    if bucket in ("config", "data_scripts"): return "config"
    return "src"

def main():
    roots = [os.path.abspath(r) for r in sys.argv[1:]]
    if not roots: sys.exit(__doc__)
    p = project(); K = knowledge()
    skip = set(K.get("skip_dirs", [])); buckets = K["loc_buckets"]; tests = set(K.get("test_dir_markers", []))
    std_dirs = [d for d in (K.get("standard_dirs", []) + p["unit"].get("standard_dirs", [])) if not is_placeholder(d)]
    std_units = {u for u in K.get("standard_units", []) if not is_placeholder(u)}
    std_prefixes = [u for u in K.get("standard_unit_prefixes", []) if not is_placeholder(u)]
    repo_base = os.path.commonpath(roots) if len(roots) > 1 else roots[0]
    def rel(path): return relp(path, repo_base)
    src_markers = set(K.get("source_dir_markers", ["src", "testsrc"])); hard_skip = {".git", "node_modules"}
    def walk(root):
        for dp, dns, fns in os.walk(root):
            # skip_dirs name build output; below a source root a directory with the same name is a package.
            under_src = any(part in src_markers for part in relp(dp, root).split("/"))
            dns[:] = [d for d in dns if not d.startswith(".") and d not in hard_skip and (under_src or d not in skip)]
            yield dp, dns, fns
    def is_std_path(path):
        rp = rel(path).replace(os.sep, "/")
        return any(sd.strip("/") in rp for sd in std_dirs)
    adapter = load_adapter()
    ctx = {"project": p, "knowledge": K, "rel": rel, "walk": walk, "std_dirs": std_dirs}
    log(f"adapter {relp(adapter.__file__, os.path.dirname(os.path.dirname(ROOT)))}, roots {roots}")
    fallback, pack_adapter = pack_hooks(adapter, p)
    if fallback: log(f"run adapter lacks {', '.join(sorted(fallback))} - using the source pack adapter's ({pack_adapter})")
    hook = lambda h: getattr(adapter, h, None) or fallback.get(h)
    # ---- derive knowledge from the vendor code shipped with this repository (never hand-maintained)
    if hasattr(adapter, "derive_knowledge"):
        derived = adapter.derive_knowledge(roots, ctx) or {}
        if derived:
            save_json(DERIVED_PATH, derived); K = knowledge(); ctx["knowledge"] = K
            std_units |= {u for u in K.get("standard_units", []) if not is_placeholder(u)}
            log("derived knowledge: " + ", ".join(f"{k}={len(v) if isinstance(v, list) else v}" for k, v in derived.items() if not k.startswith("_")))

    # ---- unit discovery below unit.repo_roots (repo-relative; fall back to the whole root) ----
    search = [os.path.join(r, rr) for r in roots for rr in p["unit"].get("repo_roots", []) if os.path.isdir(os.path.join(r, rr))] or roots
    ctx["roots"] = roots; ctx["search_roots"] = search; log(f"unit search roots: {[rel(x) for x in search]}")
    found = adapter.discover_units(search, ctx)
    std_present = {u["name"] for u in found if is_std_path(u["path"])}
    custom = [u for u in found if not is_std_path(u["path"])]
    log(f"{len(found)} units found, {len(std_present)} in standard dirs, {len(custom)} custom")
    names = {u["name"] for u in custom}
    def kind_of(dep):
        if dep in names: return "custom"
        r = adapter.is_standard_unit(dep, ctx)
        if r is True or dep in std_units or dep in std_present or any(dep.startswith(pf) for pf in std_prefixes): return "standard"
        if r is False: return "unknown"
        return "unknown"

    # ---- regexes
    dep_pats = [(d, re.compile(d["pattern"])) for d in K.get("deprecation_patterns", []) if not is_placeholder(d.get("pattern", ""))]
    int_pats = [(s["id"], re.compile(s["pattern"])) for s in K.get("integration_signals", [])]
    ep = K.get("entry_point_patterns", {})
    fe_re = re.compile(ep["frontend_controller"]) if ep.get("frontend_controller") and not is_placeholder(ep["frontend_controller"]) else None
    api_re = re.compile(ep["api_controller"]) if ep.get("api_controller") and not is_placeholder(ep["api_controller"]) else None
    ov = K.get("override_patterns", {})
    di_re = re.compile(ov["di_override"]) if ov.get("di_override") and not is_placeholder(ov["di_override"]) else None
    shadow_prefixes = [x for x in ov.get("class_shadowing_namespace_prefixes", []) if not is_placeholder(x)]
    ccp = K.get("source_content_component_pattern"); cc_re = re.compile(ccp) if ccp and not is_placeholder(ccp) else None
    gen_re = re.compile("|".join(GEN_MARKERS + [x for x in K.get("generated_markers", []) if not is_placeholder(x)]))
    recipes = [r for r in K.get("check_recipes", []) if isinstance(r, dict) and r.get("id") and (r.get("trigger") or {}).get("glob")]
    rec_re = {r["id"]: re.compile(r["trigger"]["content"]) for r in recipes if r["trigger"].get("content")}
    ov_recipes = [r for r in K.get("check_recipes", []) if isinstance(r, dict) and (r.get("trigger") or {}).get("override_resolution")]
    def glob_hit(unit_rel, g, ex=""):
        m = lambda gg: any(fnmatch.fnmatch(unit_rel, x.strip()) or fnmatch.fnmatch(os.path.basename(unit_rel), x.strip()) for x in gg.split(",") if x.strip())
        return m(g) and not (ex and m(ex))

    def tracked_files(path):
        """git-tracked files below path (absolute), or None when path is not in a git work tree."""
        try:
            r = subprocess.run(["git", "-C", path, "ls-files", "-z", "--", "."], capture_output=True, text=True, encoding="utf-8", errors="surrogateescape", timeout=60)
            if r.returncode != 0: return None
            return {os.path.normpath(os.path.join(path, f)) for f in r.stdout.split("\0") if f}
        except Exception: return None
    def hit_kind(ext, line, in_xml_comment, txt, rx):
        st = line.strip()
        if in_xml_comment or st.startswith(("<!--", "//", "/*", "*", "#", "--")): return "comment"
        if ext in (".impex", ".csv") and re.match(r"\$\w+\s*=", st): return "definition"
        if ext in (".java", ".groovy", ".kt", ".scala") and st.startswith("import "):
            m = re.search(r"import\s+(?:static\s+)?([\w.]+)", st); sym = m.group(1).rsplit(".", 1)[-1] if m else ""
            body = "\n".join(l for l in txt.splitlines() if not l.strip().startswith("import "))
            return "use" if sym and sym != "*" and re.search(r"\b" + re.escape(sym) + r"\b", body) else "import-unused"
        return "use"
    rule_text = (f"raw metrics = NON-BLANK lines INCLUDING comments over a FILESYSTEM WALK of the unit folder (skip dirs {sorted(skip)}), files counted only when their extension is a bucket ({', '.join(f'{k}={v}' for k, v in sorted(buckets.items()))}); "
                 f"metrics_tracked = the same over `git ls-files` of the unit folder (null when no git); test lines = files below {sorted(tests)}. Neither is an effort figure.")
    units, edges, dep_hits = {}, [], []; MKEYS = ("code", "code_test", "templates", "js", "ts", "config", "data_scripts", "css", "total", "files")
    for u in sorted(custom, key=lambda x: x["name"]):
        tracked = tracked_files(u["path"]); metrics_t = defaultdict(int) if tracked is not None else None
        files = []
        for dp, dns, fns in walk(u["path"]):
            for fn in fns:
                ap = os.path.join(dp, fn); ext = os.path.splitext(fn)[1].lower()
                for k in buckets:  # multi-dot extensions first
                    if fn.lower().endswith(k) and len(k) > len(ext): ext = k
                files.append((ap, rel(ap), ext))
        metrics = defaultdict(int); fe = api = 0; ints = defaultdict(int); overrides = []; shadow = []; cc_types = set()
        sig = adapter.unit_signals(u, files, ctx) or {}   # before the LOC loop: the template diff decides the template_copy bucket
        if "activation_resolved" not in sig and hook("unit_activation"):
            sig.update({k: v for k, v in (hook("unit_activation")(u, ctx) or {}).items() if k == "activation_resolved" or not sig.get(k)})
        copies = (sig.get("template_diff") or {}).get("copies") or set()
        m_gen, m_tpl, m_main = defaultdict(int), defaultdict(int), defaultdict(int); gen_why = defaultdict(int); data_eff = 0; data_co = []; trig = defaultdict(list)
        for ap, rp, ext in files:
            urel = relp(ap, u["path"]).replace(os.sep, "/"); in_test = any(part in tests for part in rp.split("/"))
            for r in recipes:
                if not in_test and r["id"] not in rec_re and len(trig[r["id"]]) < 3 and glob_hit(urel, r["trigger"]["glob"], r["trigger"].get("exclude", "")): trig[r["id"]].append(rp)
            b = buckets.get(ext)
            if not b: continue
            try: txt = open(ap, encoding="utf-8", errors="ignore").read()
            except Exception: continue
            loc = sum(1 for l in txt.splitlines() if l.strip())
            key = "code_test" if (b == "code" and in_test) else b
            metrics[key] += loc; metrics["total"] += loc; metrics["files"] += 1
            if metrics_t is not None and os.path.normpath(ap) in tracked:
                metrics_t[key] += loc; metrics_t["total"] += loc; metrics_t["files"] += 1
            is_report = urel.startswith(REPORT_DIRS); is_gen = is_report or bool(b in ("code", "templates", "js", "ts") and gen_re.search(txt[:6000]))
            tgt = m_gen if is_gen else (m_tpl if os.path.normpath(ap) in copies else m_main)
            tgt[key] += loc; tgt["total"] += loc; tgt["files"] += 1
            if is_gen: gen_why["reports" if is_report else "header marker"] += loc
            if b == "data_scripts":
                cp = "--" if ext == ".sql" else "#"; nc = sum(1 for l in txt.splitlines() if l.strip() and not (l.strip().startswith(cp) and not l.strip().startswith("#%")))
                data_eff += nc
                if nc == 0 and loc: data_co.append(rp)
            if in_test: continue
            for r in recipes:
                if r["id"] in rec_re and len(trig[r["id"]]) < 3 and glob_hit(urel, r["trigger"]["glob"], r["trigger"].get("exclude", "")):
                    mm = rec_re[r["id"]].search(txt)
                    if mm: trig[r["id"]].append(f"{rp}:{txt.count(chr(10), 0, mm.start()) + 1}")
            if b in ("code", "templates", "config", "data_scripts", "js", "ts"):
                for d, rx in dep_pats:
                    fg = d.get("file_glob") or d.get("glob") or "*"   # packs write `glob`, fixtures `file_glob`; comma-separated
                    if fg != "*" and not any(fnmatch.fnmatch(os.path.basename(rp), g.strip()) for g in fg.split(",")): continue
                    in_c = False; found = []
                    for n, line in enumerate(txt.splitlines(), 1):
                        if rx.search(line): found.append((n, line, hit_kind(ext, line, in_c, txt, rx)))
                        if "<!--" in line and "-->" not in line: in_c = True
                        elif "-->" in line: in_c = False
                    if found:   # one hit per (pattern, file): the first non-comment match represents the file
                        n, line, kd = next((f for f in found if f[2] != "comment"), found[0])
                        dep_hits.append({"id": d["id"], "title": d["title"], "unit": u["name"], "file": rp, "line": n, "kind": kd, "path_class": path_class(urel, b, kd, is_gen, in_test), "lines": len(found), "line_list": [f[0] for f in found][:20], "tracked": (os.path.normpath(ap) in tracked) if tracked is not None else None, "snippet": line.strip()[:160], "since": d.get("since", ""), "replacement": d.get("replacement", ""), "verify": d.get("verify", True)})
                for sid, rx in int_pats:
                    if rx.search(txt): ints[sid] += 1
            if b == "code":
                if fe_re and fe_re.search(txt): fe += 1
                if api_re and api_re.search(txt): api += 1
                m = re.search(r"^\s*(?:package|namespace)\s+([\w.\\]+)", txt, re.M)
                if m and any(m.group(1).startswith(pf) for pf in shadow_prefixes): shadow.append(rp)
            if b == "config" and di_re:   # commented-out XML is not a candidate (A4)
                live = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), txt, flags=re.S) if ext.endswith(".xml") else txt
                for n, line in enumerate(live.splitlines(), 1):
                    if di_re.search(line): overrides.append({"what": line.strip()[:120], "how": "di-override-candidate", "evidence": f"{rp}:{n}"})
            if cc_re and b in ("data_scripts", "config"):
                for m in cc_re.finditer(txt):
                    t = next((g for g in m.groups() if g), None)
                    if t and t not in K.get("target_content_component_types", []): cc_types.add(t)
        sig.setdefault("frontend_entry_points", fe); sig.setdefault("api_entry_points", api); sig.setdefault("integration_hits", dict(ints))
        reqs = adapter.parse_dependencies(u, ctx)
        cats = adapter.classify(u, sig, metrics, ctx) or ["other"]
        for hint in sig.get("categories_hint", []):
            if hint not in cats: cats.append(hint)
        ocands = overrides + list(sig.get("override_candidates", []))
        if hook("resolve_overrides"): ocands = hook("resolve_overrides")(u, ocands, ctx)
        for r in ov_recipes: trig[r["id"]] += [f"{c['evidence']} ({c.get('target')})" for c in ocands if c.get("resolution") == r["trigger"]["override_resolution"] and re.search(r["trigger"].get("target") or "", c.get("target") or "")][:3]
        rec = {"name": u["name"], "path": rel(u["path"]), "evidence": rel(u["manifest"]), "description": u.get("description", ""), "meta": u.get("meta", {}),
               "categories": cats, "primary_category": cats[0],
               "requires": reqs, "requires_custom": [d for d in reqs if kind_of(d) == "custom"], "requires_standard": [d for d in reqs if kind_of(d) == "standard"], "requires_unknown": [d for d in reqs if kind_of(d) == "unknown"],
               "metrics": {k: metrics.get(k, 0) for k in ("code", "code_test", "templates", "js", "ts", "config", "data_scripts", "css", "total", "files")},
               "metrics_tracked": ({k: metrics_t.get(k, 0) for k in ("code", "code_test", "templates", "js", "ts", "config", "data_scripts", "css", "total", "files")} if metrics_t is not None else None), "metrics_rule": rule_text,
               "deprecation_hits": [{k: h[k] for k in ("id", "file", "line", "kind", "path_class", "lines", "line_list", "tracked", "snippet")} for h in dep_hits if h["unit"] == u["name"]], "deprecation_hits_by_id": {i: sum(1 for h in dep_hits if h["unit"] == u["name"] and h["id"] == i) for i in sorted({h["id"] for h in dep_hits if h["unit"] == u["name"]})},
               "deprecation_hits_by_class": {c: sum(1 for h in dep_hits if h["unit"] == u["name"] and h["path_class"] == c) for c in sorted({h["path_class"] for h in dep_hits if h["unit"] == u["name"]})},
               "frontend_entry_points": sig["frontend_entry_points"], "api_entry_points": sig["api_entry_points"], "integration_hits": sig["integration_hits"],
               "schema_new_types": sig.get("schema_new_types", 0), "schema_extended_types": sig.get("schema_extended_types", 0), "schema_attributes_on_extended_types": sig.get("schema_attributes_on_extended_types", 0), "schema_relations": sig.get("schema_relations", 0), "schema_enums": sig.get("schema_enums", 0),
               "di_definitions": sig.get("di_definitions", 0), "override_candidates": ocands, "override_candidates_resolved": {k: sum(1 for c in ocands if c.get("resolution") == k) for k in sorted({c["resolution"] for c in ocands if c.get("resolution")})}, "shadowing_candidates": shadow,
               "workflows": list(sig.get("workflows", [])), "content_custom_component_types": sorted(cc_types | set(sig.get("content_custom_component_types", []))), "third_party_required": list(sig.get("third_party_required", [])),
               "loaded_in": list(sig.get("loaded_in", [])), "has_plugin_dir": bool(sig.get("has_plugin_dir", False)), "extra": sig.get("extra", {}),
               "metrics_generated": {k: m_gen.get(k, 0) for k in MKEYS}, "metrics_template_copy": {k: m_tpl.get(k, 0) for k in MKEYS}, "metrics_maintained": {k: m_main.get(k, 0) for k in MKEYS},
               "loc_maintained": sum(m_main.get(k, 0) for k in ("code", "templates", "js", "ts")), "loc_generated_by": dict(gen_why),
               "loc_rule": "metrics = metrics_generated + metrics_template_copy + metrics_maintained (same non-blank convention); generated = committed reports/ or web/reports/ or a generator header marker in code/templates/js/ts; template_copy = files identical to the vendor template after the rename, or differing only in comments/whitespace (template diff); loc_maintained = maintained code+templates+js+ts (tests excluded).",
               "template": ({k: v for k, v in sig["template_diff"].items() if k != "copies"} if sig.get("template_diff") else None),
               "data_scripts_effective": data_eff, "data_scripts_comment_only_files": data_co[:30],
               "activation_resolved": sig.get("activation_resolved"),
               "triggers": {k: v for k, v in list(trig.items()) + list((sig.get("triggers") or {}).items()) if v}}
        units[u["name"]] = rec
        for d in reqs: edges.append({"from": u["name"], "to": d, "to_kind": kind_of(d), "type": "declared", "evidence": rec["evidence"]})
        log(f"  {u['name']:36s} {cats[0]:12s} code={rec['metrics']['code']:7d} tpl={rec['metrics']['templates']:6d} maintained={rec['loc_maintained']:7d}" + (f" (template {rec['template']['template']})" if rec["template"] else "") + f" deps={len(reqs)} dep-hits={sum(1 for h in dep_hits if h['unit']==u['name'])}")
    facts = adapter.platform_facts(roots, ctx) or {}
    facts.setdefault("standard_code_in_repo", bool(std_present) or None)
    try:  # the analysed snapshot: every deliverable and a later estimation run refer to it
        def gitq(*a): r = subprocess.run(["git", "-C", repo_base, *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30); return r.stdout.strip() if r.returncode == 0 else ""
        top = gitq("rev-parse", "--show-toplevel"); top, run = (os.path.realpath(top) if top else ""), os.path.realpath(ROOT)
        if top and (run == top or run.startswith(top.rstrip(os.sep) + os.sep)): LOG.append(f"snapshot: not taken - the git work tree {top} holds the run folder itself, so it is the environment's repository, not the client's")   # e.g. a run or smoke folder inside a plugin checkout: its branch is no client fact
        elif gitq("rev-parse", "HEAD"): facts["snapshot"] = {"commit": gitq("rev-parse", "HEAD"), "short": gitq("rev-parse", "--short", "HEAD"), "date": gitq("log", "-1", "--format=%cI"), "branch": gitq("rev-parse", "--abbrev-ref", "HEAD"), "dirty": bool(gitq("status", "--porcelain")), "evidence": "git rev-parse HEAD / git log -1 in " + rel(repo_base)}
    except Exception as e: LOG.append(f"snapshot: git not available ({e})")
    out = {"scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "adapter": adapter.__file__, "roots": roots, "platform": facts, "metrics_rule": rule_text, "deprecation_rule": DEP_RULE, "units": units, "dependency_edges": edges, "deprecation_hits": dep_hits, "standard_units_present_count": len(std_present), "notes": LOG[:3]}
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(out, open(os.path.join(OUT_DIR, "inventory.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # per-unit deprecation table: what every analyst and critic brief pastes for its unit
    with open(os.path.join(OUT_DIR, "deprecation_hits_per_unit.md"), "w", encoding="utf-8") as f:
        f.write(f"# Deprecation hits per unit (generated by `dbcx scan_inventory` {out['scanned_at']}; {len(dep_hits)} raw hits)\n\nRAW counts = upper bound, never an effort figure. kind: use | definition (ImpEx macro line) | import-unused (Java import with no body reference) | comment. tracked=false: file is not git-tracked (build output).\n{DEP_RULE}\n\n")
        for name, rec in units.items():
            hs = rec["deprecation_hits"]; f.write(f"## {name} ({len(hs)} hits" + (f"; {sum(1 for h in hs if h.get('tracked') is False)} in untracked files" if any(h.get('tracked') is False for h in hs) else "") + ")\n\n")
            if not hs: f.write("(no scanner hits - the unit's Deprecations section must say so explicitly)\n\n"); continue
            def cls_of(i): return ", ".join(f"{c} {sum(1 for h in hs if h['id'] == i and h['path_class'] == c)}" for c in sorted({h["path_class"] for h in hs if h["id"] == i}))
            f.write("| id | files | lines | kinds | path classes |\n|---|---|---|---|---|\n" + "".join(f"| {i} | {n} | {sum(h['lines'] for h in hs if h['id'] == i)} | {', '.join(sorted({h['kind'] for h in hs if h['id'] == i}))} | {cls_of(i)} |\n" for i, n in rec["deprecation_hits_by_id"].items()) + "\n")
            for h in hs[:60]: f.write(f"- {h['id']} `{h['file']}:{h['line']}` [{h['kind']}, {h['path_class']}, {h['lines']} line(s){', untracked' if h.get('tracked') is False else ''}] {h['snippet'][:100]}\n")
            if len(hs) > 60: f.write(f"- ... {len(hs) - 60} more (inventory.json units.{name}.deprecation_hits)\n")
            f.write("\n")
    unknown = sorted({e["to"] for e in edges if e["to_kind"] == "unknown"})
    if unknown: log(f"WARNING {len(unknown)} dependencies of unknown kind (add to overrides/knowledge.json standard_units or improve adapter.derive_knowledge/is_standard_unit): {unknown[:15]}")
    log(f"{len(units)} custom units, {len(edges)} edges, {len(dep_hits)} deprecation hits -> analysis/inventory/inventory.json (+ deprecation_hits_per_unit.md; metrics_tracked {'available' if any(u.get('metrics_tracked') for u in units.values()) else 'not available - no git work tree'})")
    open(os.path.join(OUT_DIR, "scan_log.txt"), "w", encoding="utf-8").write("\n".join(LOG))

if __name__ == "__main__":
    main()
