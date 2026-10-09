#!/usr/bin/env python3
"""Inspect the merged platform knowledge for this project.
Usage: dbcx knowledge show [key]        merged view (skeleton <- source pack <- target pack <- engagement overrides <- run overrides <- derived)
       dbcx knowledge sources           which layer contributes which keys"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import knowledge, project, override_files, DEFAULTS, DERIVED_PATH, RUN, read_json, load_json, relp

def main():
    a = sys.argv[1:]; k = knowledge()
    if not a or a[0] == "show":
        if len(a) > 1: print(json.dumps(k.get(a[1]), indent=1, ensure_ascii=False)); return
        for kk, v in k.items():
            if kk.startswith("_"): continue
            print(f"{kk:40s} {('list[%d]' % len(v)) if isinstance(v, list) else ('dict[%d]' % len(v) if isinstance(v, dict) else repr(v)[:80])}")
    elif a[0] == "sources":
        cfg = project(); layers = [("skeleton", read_json(os.path.join(DEFAULTS, "knowledge.skeleton.json")))]
        for slot, pk in cfg["_packs"].items():
            if not pk: continue
            fp = os.path.join(pk["_dir"], pk.get("knowledge", "knowledge.json"))
            if os.path.exists(fp): layers.append((f"{slot} pack {pk['name']}", read_json(fp)))
        layers += [(f"overrides {relp(f, RUN)}", read_json(f, {})) for f in override_files("knowledge.json")] + [("derived", load_json(DERIVED_PATH, {}))]
        for name, d in layers: print(f"{name:28s} {', '.join(kk for kk in d if not kk.startswith('_'))}")

if __name__ == "__main__":
    main()
