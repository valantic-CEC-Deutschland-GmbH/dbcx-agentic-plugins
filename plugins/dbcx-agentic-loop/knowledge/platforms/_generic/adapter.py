"""Generic adapter: every directory below the repo roots that contains the manifest file (analysis.json / pack unit.manifest_file)
is a unit. Dependencies are read from JSON manifests ('require', 'dependencies', 'requires', 'depends') or from
XML manifests (any element with a 'name' attribute inside a *require* element). Good enough to start; replace with a
platform adapter for real engagements (see methods/code-analysis/tools/adapter_template.py)."""
import json, os, re
from xml.etree import ElementTree as ET

UNIT_MANIFEST = None

def discover_units(roots, ctx):
    manifest = ctx["project"]["unit"]["manifest_file"]; out = []
    for r in roots:
        for dp, dns, fns in ctx["walk"](r):
            if manifest in fns:
                mp = os.path.join(dp, manifest); name = os.path.basename(dp); desc = ""
                try:
                    if mp.endswith(".json"):
                        d = json.load(open(mp, encoding="utf-8")); name = d.get("name", name).split("/")[-1] if isinstance(d.get("name"), str) else name; desc = d.get("description", "") or ""
                    elif mp.endswith(".xml"):
                        rt = ET.parse(mp).getroot()
                        el = rt.find(".//*[@name]") if rt.get("name") is None else rt
                        if el is not None and el.get("name"): name = el.get("name")
                        desc = (el.get("description") if el is not None else "") or ""
                except Exception as e:
                    desc = f"manifest parse error: {e}"
                out.append({"name": name, "path": dp, "manifest": mp, "description": desc, "meta": {}})
                dns[:] = []  # do not descend into nested units
    return out

def parse_dependencies(unit, ctx):
    mp = unit["manifest"]; deps = []
    try:
        if mp.endswith(".json"):
            d = json.load(open(mp, encoding="utf-8"))
            for k in ("require", "dependencies", "requires", "depends", "peerDependencies"):
                v = d.get(k)
                if isinstance(v, dict): deps += list(v)
                elif isinstance(v, list): deps += [x if isinstance(x, str) else x.get("name") for x in v]
        elif mp.endswith(".xml"):
            rt = ET.parse(mp).getroot()
            for el in rt.iter():
                if "require" in el.tag.lower() or "depend" in el.tag.lower():
                    if el.get("name"): deps.append(el.get("name"))
                    for ch in el:
                        if ch.get("name"): deps.append(ch.get("name"))
    except Exception:
        pass
    return [d.split("/")[-1] if isinstance(d, str) else d for d in deps if d]

def is_standard_unit(name, ctx):
    return None

def unit_signals(unit, files, ctx):
    return {}

def classify(unit, signals, metrics, ctx):
    cats = []; p = unit["path"].lower(); m = metrics
    if signals.get("api_entry_points"): cats.append("api")
    if m.get("templates", 0) > 50 or signals.get("frontend_entry_points"): cats.append("frontend")
    if signals.get("integration_hits"): cats.append("integration")
    if any(k in p for k in ("admin", "backoffice", "backend-ui")): cats.append("admin")
    if any(k in p for k in ("facade", "client", "api-client")): cats.append("facade")
    if m.get("data_scripts", 0) > m.get("code", 0): cats.append("data")
    if m.get("code", 0) == 0 and m.get("code_test", 0) > 0: cats.append("test")
    if not cats: cats.append("core" if m.get("code", 0) > 0 else "other")
    allowed = ctx["project"]["unit"]["categories"]
    return [c for c in cats if c in allowed] or ["other"]

def platform_facts(roots, ctx):
    facts = {"version_hints": {}, "config_files": {}, "standard_code_in_repo": None, "notes": ["generic_dirs adapter: platform facts must be established from the configuration (module 1)"]}
    for r in roots:
        for cand in ("composer.lock", "composer.json", "package.json", "build.number", "manifest.json", "pom.xml", "build.gradle"):
            for dp, dns, fns in ctx["walk"](r):
                if cand in fns:
                    p = os.path.join(dp, cand); txt = open(p, encoding="utf-8", errors="ignore").read()[:20000]
                    hints = re.findall(r'"?(?:version|commerceSuiteVersion|shopware/core|spryker/kernel|magento/product-community-edition)"?\s*[:=]\s*"?([\w.\-]+)', txt)[:5]
                    if hints: facts["version_hints"][ctx["rel"](p)] = hints
                break
    return facts

def derive_knowledge(roots, ctx):
    """Standard units = every unit found below the pack's standard dirs (vendor code shipped with the repo)."""
    std = []
    for r in roots:
        for sd in ctx["std_dirs"]:
            base = os.path.join(r, sd)
            if os.path.isdir(base):
                for u in discover_units([base], ctx): std.append(u["name"])
    return {"standard_units": sorted(set(std))} if std else {}
