#!/usr/bin/env python3
"""Active-extensions resolver for SAP Commerce repositories (deterministic, read-only, no network).

Usage: dbcx active_extensions <repo-root> [--ext a,b] [--custom] [--state <state>] [--json]
       (outside a run: python3 <plugin>/knowledge/platforms/sap-commerce/tools/active_extensions.py ...)

Sources, each XML-parsed with comments ignored and either quote style: the localextensions.xml the build uses (CCv2: manifest.json
useConfig.extensions.location minus useConfig.extensions.exclude; on-premise: hybris/config/localextensions.xml), its <path autoload>
entries, manifest.json extensions[] and storefrontAddons[], and the requires-extension closure over every extensioninfo.xml in the tree.
Every extension ends in exactly one state, with the evidence for it:
  active                    loaded by a source above AND provisioned (in the tree, or supplied through manifest.json)
  declared-not-provisioned  loaded by a source above (listed or required by an active extension) but neither in the tree nor in
                            manifest.json extensions[]: the repository does not provide it; whether the CCv2 build supplies it anyway is
                            not visible in the repository (requires-extension only auto-loads what is discoverable on a scanned path)
  not-decidable             the repository cannot settle it: no localextensions.xml in the repository, standard code not checked in,
                            or reachable only through an extension whose extensioninfo.xml is not in the repository
  inactive                  in the tree (or named in a query) but nothing in the repository loads it
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sap_repo as R

STATES = ("active", "declared-not-provisioned", "not-decidable", "inactive")
RULE = ("RULE: active = listed in the build's localextensions.xml (comments ignored, manifest exclude applied) / manifest.json extensions[] / "
        "storefrontAddons[] / a <path autoload='true'> folder / platform ext (extensions autoload default true), or required (requires-extension, "
        "transitively) by an active extension - AND present in the tree or supplied by manifest.json; declared-not-provisioned = loaded by those "
        "sources but not provided by the repository; not-decidable = the repository cannot settle it; inactive = nothing in the repository loads it. "
        "Deployment-time changes (Cloud Portal, build-time injection) are invisible to this resolver.")

def resolve(root):
    L = R.layout(root); rel = lambda p: os.path.relpath(p, L["root"]).replace(os.sep, "/") if p else None
    tree = R.extensions_in_tree(L["bin"]); man = L["manifest_json"]; mp = rel(L["manifest"])
    loads = {}   # name -> [evidence] of what loads it
    def load(n, ev): loads.setdefault(n, []).append(ev)
    notes = []; commented = []
    excl = set(((man.get("useConfig") or {}).get("extensions") or {}).get("exclude") or [])
    if L["localextensions"]:
        le = R.read_localextensions(L["localextensions"], L["hybris"]); lp = rel(L["localextensions"]); commented = le["commented"]
        for name, d, line in le["extensions"]:
            if not name and d:
                p = os.path.join(L["hybris"] or "", d.replace("${HYBRIS_BIN_DIR}/", "bin/").replace("${HYBRIS_BIN_DIR}", "bin"), "extensioninfo.xml")
                name = R.read_extensioninfo(p)["name"] if os.path.isfile(p) else os.path.basename(d.rstrip("/"))
            if not name: continue
            if name in excl: notes.append(f"{name}: listed at {lp}:{line} but excluded by {mp} useConfig.extensions.exclude"); continue
            load(name, f"{lp}:{line}")
        for d, auto, line in le["paths"]:
            if auto:
                for n, e in tree.items():
                    if os.path.abspath(e["dir"]).startswith(os.path.abspath(d) + os.sep): load(n, f"{lp}:{line} (<path autoload='true'>)")
        if le["platform_autoload"]:
            for n, e in tree.items():
                if "/platform/ext/" in e["dir"].replace(os.sep, "/") + "/": load(n, "platform extension (localextensions <extensions> autoload default true)")
    elif L["localextensions_declared"]:
        notes.append(f"{L['localextensions_source']} points at {rel(L['localextensions_declared'])}, which is not in the repository")
    for n in man.get("extensions") or []: load(n, f"{mp}:{R.json_line(L['manifest'], chr(34) + n + chr(34)) or '?'} (extensions[])")
    for a in man.get("storefrontAddons") or []:
        n = a.get("addon") if isinstance(a, dict) else a
        if n: load(n, f"{mp}:{R.json_line(L['manifest'], chr(34) + n + chr(34)) or '?'} (storefrontAddons[])")
    provided_by_manifest = set(man.get("extensions") or []) | {a.get("addon") if isinstance(a, dict) else a for a in man.get("storefrontAddons") or []}
    no_config = not L["localextensions"]
    out = {}; incomplete = []   # extensions whose own requires cannot be read
    queue = list(loads)
    while queue:
        n = queue.pop(0)
        if n in out: continue
        ev = loads.setdefault(n, [])
        if n in tree and n in excl:
            st = "not-decidable"; prov = (f"in the tree at {rel(tree[n]['dir'])}, excluded by {mp} useConfig.extensions.exclude but required by an active extension - "
                                          "whether the exclude also suppresses the requires-extension auto-load is not decidable from the repository")
        elif n in tree:
            e = tree[n]; st = "active"; prov = f"in the tree at {rel(e['dir'])}"
            for r, line in e["requires"]:
                load(r, f"required by {n} ({rel(e['manifest'])}:{line})")
                if r not in out: queue.append(r)
        elif n in provided_by_manifest:
            st = "active"; prov = "supplied by manifest.json (not in the tree; its requires-extension list is not in the repository)"; incomplete.append(n)
        elif not L["platform_in_repo"]:
            st = "not-decidable"; prov = "not in the tree and the standard code is not checked in (the CCv2 build supplies commerce-suite extensions from commerceSuiteVersion)"; incomplete.append(n)
        else:
            st = "declared-not-provisioned"; prov = ("neither in the tree nor in manifest.json extensions[] - the repository does not provide it; "
                                                    "whether the CCv2 build supplies it anyway is not decidable from the repository"); incomplete.append(n)
        out[n] = {"state": st, "evidence": ev, "_prov": prov, "dir": rel(tree[n]["dir"]) if n in tree else None, "custom": bool(n in tree and not tree[n]["standard"])}
    for n, e in tree.items():
        if n in out: continue
        if no_config and not e["standard"]:
            out[n] = {"state": "not-decidable", "evidence": ["no localextensions.xml in the repository - activation is configured outside it", f"in the tree at {rel(e['dir'])}"], "dir": rel(e["dir"]), "custom": True}
        else:
            ce = [f"commented out at {rel(L['localextensions'])}:{line}" for c, line in commented if c == n]
            out[n] = {"state": "inactive", "evidence": ce + [f"in the tree at {rel(e['dir'])}; not listed, not required by any active extension"], "dir": rel(e["dir"]), "custom": not e["standard"]}
    for n, v in out.items():
        if "_prov" in v: v["evidence"] = v["evidence"] + [v.pop("_prov")]
    for n, v in out.items(): v["loaded_in"] = [x for x in v["evidence"] if v["state"] == "active" and not x.startswith(("in the tree", "supplied by"))]
    counts = {s: sum(1 for v in out.values() if v["state"] == s) for s in STATES}
    return {"rule": RULE, "layout": {k: rel(L[k]) for k in ("core", "manifest", "localextensions")} | {"localextensions_source": L["localextensions_source"], "platform_in_repo": L["platform_in_repo"]},
            "extensions": out, "closure_incomplete": sorted(incomplete), "notes": notes, "counts": counts,
            "counts_custom": {s: sum(1 for v in out.values() if v["custom"] and v["state"] == s) for s in STATES}}

def query(res, name):
    """State of one extension, including names the repository never mentions."""
    if name in res["extensions"]: return res["extensions"][name]
    if res["closure_incomplete"]:
        return {"state": "not-decidable", "dir": None, "custom": False, "loaded_in": [], "evidence": [
            "no repository file lists, contains or requires it; it may be required by an extension whose extensioninfo.xml is not in the repository: "
            + ", ".join(res["closure_incomplete"][:12])]}
    return {"state": "inactive", "dir": None, "custom": False, "loaded_in": [], "evidence": ["not in the tree, not listed, not required by any extension in the repository"]}

def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"): sys.exit(__doc__)
    res = resolve(a[0]); names = a[a.index("--ext") + 1].split(",") if "--ext" in a else None
    sel = {n: query(res, n) for n in names} if names else res["extensions"]
    if "--custom" in a: sel = {n: v for n, v in sel.items() if v["custom"]}
    if "--state" in a: sel = {n: v for n, v in sel.items() if v["state"] == a[a.index("--state") + 1]}
    if "--json" in a: print(json.dumps(dict(res, extensions=sel), indent=1, ensure_ascii=False)); return
    print(f"layout: {res['layout']}")
    for n in sorted(sel, key=lambda n: (STATES.index(sel[n]["state"]), n)):
        v = sel[n]; print(f"{n:40s} {v['state']:25s} {'custom ' if v['custom'] else ''}| " + " | ".join(v["evidence"][:4]))
    for x in res["notes"]: print("NOTE", x)
    print(f"counts: {res['counts']} | custom: {res['counts_custom']} | closure incomplete below: {', '.join(res['closure_incomplete'][:10]) or '-'}")
    print(RULE)

if __name__ == "__main__":
    main()
