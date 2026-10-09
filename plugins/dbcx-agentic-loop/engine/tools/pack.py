#!/usr/bin/env python3
"""Knowledge pack utilities (knowledge/<kind>/<name>/).
Usage: dbcx pack list [kind]
       dbcx pack cache-back                  RETIRED (the installed plugin is read-only): verified section-7 facts the pack lacks travel to
                                             the maintainer in `dbcx learn export` as knowledge-fact packages (new_facts; with several technology
                                             packs a row goes with the pack pack_of_row attributes it to: provenance naming the pack or its critic
                                             standard-<pack>, a vendor-code locator in the pack's vendor_code.scope, or a URL host in its docs_domains)
       dbcx pack new <kind> <name> --display "Name" [--roles source,target]   scaffold a new pack (platforms: from _generic; other kinds: minimal pack.json + seed files)"""
import os, re, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import KNOWLEDGE, TOOLS, project, list_packs, pack, P, REF_DIR, PLUGIN, option_packs, pack_snippets, relp
import reference

REFUTED_RE = re.compile(r"\b(refuted|disputed|superseded)\b", re.I)

HOST_RE = re.compile(r"(?<![\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}(?![\w.-])")

def pack_of_row(url, provenance, packs, cfg):
    """the pack (name) a section-7 row belongs to among several technology packs, or None when nothing attributes it"""
    for n in packs:
        if re.search(rf"(?:^|[^\w-]|standard-){re.escape(n)}(?![\w-])", provenance or ""): return n
    for n, pk in packs.items():
        sc = (pk.get("vendor_code") or {}).get("scope")
        if sc and str(url).lstrip().startswith(sc + "/"): return n
    host = (re.search(r"^[a-z]+://([^/:]+)", str(url).strip(), re.I) or [None, ""])[1].lower()
    hits = [n for n, pk in packs.items() if host and any(host == d or host.endswith("." + d) for d in HOST_RE.findall(pack_snippets(cfg, pk).get("docs_domains", "").lower()))]
    return hits[0] if len(hits) == 1 else None

def new_facts(name=None, exclude=()):
    """section-7 verified facts of <project>/reference/platform-standard.md that the pack's reference-cache.md lacks (dedup by fact+applies);
    refuted/disputed/superseded rows and --exclude'd ids are skipped; with several technology packs only the rows attributed to `name`.
    `dbcx learn export` carries these rows to the maintainer (kind c).
    -> (pack name, [{"id", "fact", "applies", "url", "date", "pack"}], note)"""
    cfg = project(); multi = option_packs(cfg) if cfg.get("options") else {}
    if len(multi) > 1 and not name: sys.exit(f"this run's options use {len(multi)} technology packs ({', '.join(multi)}) - pass the pack name; only that pack's rows are selected")
    pk = pack(name) if name else (cfg["_packs"].get("target") or cfg["_packs"].get("platform") or next(iter([x for x in cfg["_packs"].values() if x]), None))
    if not pk: return None, [], "no knowledge pack in this run"
    multi = multi if len(multi) > 1 else {}; foreign = []
    cache = os.path.join(pk["_dir"], pk.get("reference_cache", "reference-cache.md"))
    _, _, _, _, rows = reference.load()   # reuse the register's own section-7 parser (id-aware, header/separator already excluded)
    existing = open(cache, encoding="utf-8").read() if os.path.exists(cache) else ""
    seen = {(fact + applies).replace(" ", "") for fact, applies in re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", existing, re.M)}
    excluded = 0; refuted = 0; out = []
    for _, raw_cells in rows:
        rid, fact, applies, url, date, provenance, affects, status = reference.norm(raw_cells)
        if not fact or not url: continue
        if rid and rid in exclude: excluded += 1; continue
        if status == "disputed" or REFUTED_RE.search(provenance) or REFUTED_RE.search(fact): refuted += 1; continue
        if multi and pack_of_row(url, provenance, multi, cfg) != pk["name"]: foreign.append(f"{rid or fact[:40]} ({pack_of_row(url, provenance, multi, cfg) or 'unattributed'})"); continue
        key = (fact + applies).replace(" ", "")
        if key in seen: continue
        seen.add(key); out.append({"id": rid, "fact": fact, "applies": applies, "url": url, "date": date, "pack": pk["name"]})
    note = (f"{excluded} excluded, {refuted} refuted/disputed/superseded skipped" if excluded or refuted else "") + (f"; not {pk['name']}'s: {', '.join(foreign)}" if foreign else "")
    return pk["name"], out, note

def new(kind, name, display, roles):
    d = os.path.join(KNOWLEDGE, kind, name)
    if os.path.exists(d): sys.exit("exists")
    if kind == "platforms":
        shutil.copytree(os.path.join(KNOWLEDGE, "platforms", "_generic"), d)
        pj = json.load(open(os.path.join(d, "pack.json"), encoding="utf-8")); pj.update({"name": name, "display": display, "roles": roles, "kind": "platform"}); pj["_readme"] = "Scaffolded from _generic: replace adapter.py (methods/code-analysis/tools/adapter_template.py), knowledge.json, snippets, research-seed.md"
    else:
        os.makedirs(d); pj = {"name": name, "display": display, "kind": kind[:-1] if kind.endswith("s") else kind, "roles": roles, "config": {}, "snippets": {}, "research_seed": "research-seed.md", "reference_cache": "reference-cache.md", "_readme": "knowledge pack: fill knowledge.json, snippets, research-seed.md and reference-cache.md"}
        open(os.path.join(d, "research-seed.md"), "w", encoding="utf-8").write(f"# {display} - research seed\n\nHypotheses marked *(verify)* for the researcher.\n")
        open(os.path.join(d, "reference-cache.md"), "w", encoding="utf-8").write("# Verified facts cache\n\n| Fact | Applies to (version) | URL | Date |\n|---|---|---|---|\n")
    json.dump(pj, open(os.path.join(d, "pack.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False); print("scaffolded", d)

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("--help", "-h", "help"): print(__doc__); return
    if a[0] == "list":
        for k, n in list_packs(a[1] if len(a) > 1 else None): pk = pack(n, k); print(f"{k + '/' + n:36s} roles={','.join(pk.get('roles', []))}  {pk.get('display', '')}")
    elif a[0] == "cache-back": sys.exit("REFUSED: `dbcx pack cache-back` is retired - the installed plugin is read-only. Verified reference facts reach the maintainer through `dbcx learn export` (knowledge-fact packages); the maintainer adds them to the pack's reference-cache.md after `dbcx learn import`.")
    elif a[0] == "new": new(a[1], a[2], a[a.index("--display") + 1] if "--display" in a else a[2], (a[a.index("--roles") + 1] if "--roles" in a else "source,target").split(","))
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
