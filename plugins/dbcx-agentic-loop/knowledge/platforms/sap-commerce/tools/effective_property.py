#!/usr/bin/env python3
"""Effective-property resolver for SAP Commerce repositories (deterministic, read-only, no network).

Usage: dbcx effective_property <repo-root> <key> [<key> ...] [--persona development|staging|production] [--aspect <aspect>] [--json]
       (outside a run: python3 <plugin>/knowledge/platforms/sap-commerce/tools/effective_property.py ...)

Chain, lowest first; the LAST writer wins:
  CCv2 (manifest.json present): hybris/bin/platform/project.properties -> project.properties of every ACTIVE extension (active_extensions;
    the order among extensions is the platform's load order and is not computed - several extension defaults are all listed) ->
    manifest.json `properties` without persona -> manifest.json useConfig.properties files in ARRAY order (persona entries only for the
    selected persona, aspect entries only for the selected aspect) -> manifest.json `properties` with the selected persona -> the selected
    aspect's `properties` in manifest.json aspects[] -> DEPLOYMENT-TIME layers (Cloud Portal) that are invisible in the repository.
  on-premise (no manifest.json): platform project.properties -> active extensions' project.properties -> hybris/config/local.properties ->
    deployment-time layers (HYBRIS_OPT_CONFIG_DIR files, y_* environment variables), invisible in the repository.
Without --persona every persona is resolved. Values of secret-like keys are never printed (form + length only). A value with ${...} is
reported raw; property placeholders are resolved by the platform at runtime. Config files that set the key but are not in the chain are
listed separately (a local, non-CCv2 build may assemble files differently).
"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sap_repo as R
import active_extensions as AE

PERSONAS = ("development", "staging", "production")

def _defs(path, keys, rel, layer):
    out = []
    for k, v, line in R.read_properties(path):
        if k in keys: out.append({"key": k, "value": v, "at": f"{rel(path)}:{line}", "layer": layer})
    return out

def chain(root, keys, persona=None, aspect=None, res=None):
    """[(layer, [definitions])] in ascending precedence for one persona/aspect selection, plus the files outside the chain."""
    L = R.layout(root); rel = lambda p: os.path.relpath(p, L["root"]).replace(os.sep, "/"); man = L["manifest_json"]; keys = set(keys)
    res = res or AE.resolve(root); tree = R.extensions_in_tree(L["bin"]); layers = []; used = set()
    def add(layer, path):
        if path and os.path.isfile(path): used.add(os.path.abspath(path)); layers.append((layer, _defs(path, keys, rel, layer)))
    if L["bin"]: add("platform default", os.path.join(L["bin"], "platform", "project.properties"))
    ext_defs = []
    for n, v in sorted(res["extensions"].items()):
        if v["state"] == "active" and n in tree:
            p = os.path.join(tree[n]["dir"], "project.properties")
            if os.path.isfile(p): used.add(os.path.abspath(p)); ext_defs += _defs(p, keys, rel, f"extension default ({n})")
    layers.append(("extension project.properties (load order not computed)", ext_defs))
    if L["manifest"]:
        mp = rel(L["manifest"])
        def inline(items, layer, want_persona):
            d = []
            for it in items or []:
                if it.get("key") in keys and (it.get("persona") == want_persona):
                    d.append({"key": it["key"], "value": str(it.get("value", "")), "at": f"{mp}:{R.json_line(L['manifest'], chr(34) + it['key'] + chr(34)) or '?'}", "layer": layer})
            return d
        layers.append(("manifest.json properties", inline(man.get("properties"), "manifest.json properties", None)))
        for e in (man.get("useConfig") or {}).get("properties") or []:
            used.add(os.path.abspath(os.path.join(L["manifest_base"], e["location"].lstrip("/"))))   # in the chain for some persona/aspect
            if e.get("persona") and e["persona"] != persona: continue
            if e.get("aspect") and e["aspect"] != aspect: continue
            p = os.path.join(L["manifest_base"], e["location"].lstrip("/"))
            lay = "useConfig " + e["location"] + (f" (persona {e['persona']})" if e.get("persona") else "") + (f" (aspect {e['aspect']})" if e.get("aspect") else "")
            if os.path.isfile(p): add(lay, p)
            else: layers.append((lay + " - FILE NOT IN REPOSITORY", []))
        if persona: layers.append((f"manifest.json properties (persona {persona})", inline(man.get("properties"), f"manifest.json properties (persona {persona})", persona)))
        if aspect:
            asp = next((a for a in man.get("aspects") or [] if a.get("name") == aspect), {})
            d = [x for x in inline(asp.get("properties"), f"manifest.json aspect {aspect}", None) + (inline(asp.get("properties"), f"manifest.json aspect {aspect} (persona {persona})", persona) if persona else [])]
            layers.append((f"manifest.json aspect {aspect} properties", d))
    elif L["hybris"]:
        add("hybris/config/local.properties", os.path.join(L["hybris"], "config", "local.properties"))
    outside = []
    for base in filter(None, [L["core"] and os.path.join(L["core"], "environments"), L["hybris"] and os.path.join(L["hybris"], "config")]):
        for p in sorted(glob.glob(os.path.join(base, "**", "*.properties"), recursive=True)):
            if os.path.abspath(p) not in used: outside += _defs(p, keys, rel, "not in the chain")
    return layers, outside

def resolve(root, keys, persona=None, aspect=None):
    res = AE.resolve(root); ccv2 = bool(R.layout(root)["manifest"]); out = {}
    for ps in ([persona] if persona else (PERSONAS if ccv2 else [None])):
        layers, outside = chain(root, keys, ps, aspect, res)
        for k in keys:
            defs = [d for _, ds in layers for d in ds if d["key"] == k]
            eff = defs[-1] if defs else None
            ext = [d for d in defs if d["layer"].startswith("extension default")]
            r = out.setdefault(k, {"key": k, "by_persona": {}, "outside_chain": [d["at"] for d in outside if d["key"] == k]})
            show = lambda d: dict(d, value=R.value_form(k, d["value"]) or d["value"])
            r["by_persona"][ps or "on-premise"] = {"effective": show(eff) if eff else None, "overridden": [show(d) for d in defs[:-1]],
                                                   "note": ("several extension defaults, order = platform load order (not computed)" if len(ext) > 1 and eff in ext else "")
                                                   + ("; deployment-time layers (Cloud Portal) can still override - invisible in the repository")}
    return {"rule": __doc__.split("Chain, lowest first; the LAST writer wins:")[1].split("Without --persona")[0].strip(), "aspect": aspect, "properties": out}

def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0].startswith("-"): sys.exit(__doc__)
    flags = {"--persona", "--aspect"}; keys = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] not in flags]
    r = resolve(a[0], keys, a[a.index("--persona") + 1] if "--persona" in a else None, a[a.index("--aspect") + 1] if "--aspect" in a else None)
    if "--json" in a: print(json.dumps(r, indent=1, ensure_ascii=False)); return
    for k, v in r["properties"].items():
        print(f"== {k}" + (f" (aspect {r['aspect']})" if r["aspect"] else " (no aspect file selected)"))
        for ps, x in v["by_persona"].items():
            e = x["effective"]; print(f"  {ps:12s} " + (f"EFFECTIVE {e['value']!r} at {e['at']} [{e['layer']}]" if e else "not set in any repository layer (platform code default applies)"))
            for o in reversed(x["overridden"]): print(f"  {'':12s}   overridden: {o['value']!r} at {o['at']} [{o['layer']}]")
            if x["note"]: print(f"  {'':12s}   note: {x['note'].strip('; ')}")
        if v["outside_chain"]: print(f"  set in files outside the chain: {', '.join(v['outside_chain'])}")
    print("RULE: " + " ".join(r["rule"].split()))

if __name__ == "__main__":
    main()
