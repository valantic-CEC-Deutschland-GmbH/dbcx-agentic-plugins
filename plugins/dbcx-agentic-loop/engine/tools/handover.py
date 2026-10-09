#!/usr/bin/env python3
"""Handover between runs: released, hash-stamped snapshots of artefacts (never live references).
Usage: dbcx handover export [<artefact-type>] [--label "..."]   copy the artefact the method produces (method.json artefacts.produces) into
                                                               <project>/handover/<type>-<run>-<date>.json (+ .sha256, manifest.json entry) with the passed claim ids
       dbcx handover list                                       released artefacts of this engagement (type, run, date, claims, sha)
       dbcx handover import <file|type> [--as <type>] [--mapping <json>]   snapshot an artefact into <run>/input/handover/<type>.json (+ .sha256) and record it
                                                               in STATUS and run.json; <type> alone picks the newest released artefact of that type from <project>/handover/;
                                                               an external file (another department's list) is imported the same way and marked provenance external
       dbcx handover types                                      artefact types this method consumes / produces
Engine artefact types (every method, no method.json declaration): client-assumptions = the client-directed questions of
state/QUESTIONS.json as assumptions (assumption_id A-nn, question, assumption, why, if_not, affects, options, answers[], status);
a consuming run materialises them with `dbcx questions import-handover input/handover/client-assumptions.json`. knowledge-base = the
active entries and topics of state/KNOWLEDGE.json (`dbcx kb export`); a consuming run imports them as KB-H-n with `dbcx kb import-handover
input/handover/knowledge-base.json [--as-global]`.
Rule: a run's inputs are frozen at start - `dbcx status verify` reports (as information) when a released artefact changed after the import; a later change is a delta run.
Rule: an imported artefact is EVIDENCE, cited as HO-<type>#<row id>; it is never restated as the run's own fact and never re-reviewed (that would be reviewing someone else's work).
"""
import os, sys, json, time, hashlib, shutil, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, HANDOVER_DIR, PROJECT_DIR, STATUS_PATH, project, method, load_json, save_json, run_file, load_questions

def client_assumptions():
    """engine artefact client-assumptions: every client-directed question with its stable A-nn and the full answer history"""
    from xl_transform import assumption_numbers, is_client, answers_of
    qs = load_questions(); nums = assumption_numbers(qs)
    rows = [{"assumption_id": nums[q["id"]], "id": q["id"], "from": q.get("from", ""), "question": q.get("question", ""), "assumption": q.get("assumption", ""), "why": q.get("why", ""),
             "if_not": q.get("if_not", ""), "effect": q.get("effect", ""), "affects": q.get("affects") or [], "options": q.get("options") or [], "proceeding_under": q.get("proceeding_under", ""),
             "answers": answers_of(q), "status": q.get("status") or "open"} for q in qs if is_client(q) and q.get("id")]
    return {"assumptions": sorted(rows, key=lambda r: int(r["assumption_id"][2:]))}
def knowledge_base():
    """engine artefact knowledge-base: the active entries of the run knowledge base and their topics (superseded entries are not carried)"""
    import kb; return kb.export_data()
ENGINE_TYPES = {"client-assumptions": client_assumptions, "knowledge-base": knowledge_base}
ENGINE_SOURCES = {"client-assumptions": "state/QUESTIONS.json", "knowledge-base": "state/KNOWLEDGE.json"}

def method_provenance(rj, m=None):
    """method_source, method_version, method_origin (custom | derived | plugin), derived_from and, for a copy from the personal library,
    method_installed_from / method_library_version of a run - the run.json stamps (init, method install) first, else the method folder (method.json
    `origin` as a string or {type, derived_from, installed_from, library_version}, method-card.json origin.type); keys without a value are left out"""
    if m is None:
        try: m = method(rj["method"]) if rj.get("method") else {}
        except (SystemExit, KeyError): m = {}
    o = m.get("origin"); card = (load_json(os.path.join(m["_dir"], "method-card.json"), {}) or {}).get("origin") if m.get("_dir") else None
    origin = rj.get("method_origin") or (o.get("type") if isinstance(o, dict) else o) or (card or {}).get("type") or ("plugin" if m.get("_source") == "plugin" else None)
    oo = o if isinstance(o, dict) else {}
    out = {"method_source": rj.get("method_source") or m.get("_source"), "method_version": rj.get("method_version") or m.get("version"), "method_origin": origin,
           "derived_from": rj.get("method_derived_from") or oo.get("derived_from") or m.get("derived_from"),
           "method_installed_from": rj.get("method_installed_from") or oo.get("installed_from"), "method_library_version": rj.get("method_library_version") or oo.get("library_version")}
    return {k: v for k, v in out.items() if v}

def sha(fp): return hashlib.sha256(open(fp, "rb").read()).hexdigest()
def manifest():
    p = os.path.join(HANDOVER_DIR, "manifest.json"); return (json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"released": []}), p
def run_name(): return run_file().get("run_name") or os.path.basename(ROOT)

def passed_claims(scope):
    gd = os.path.join(ROOT, "analysis", "gauntlet", scope); results = sorted(glob.glob(os.path.join(gd, "round*-result.json")))
    if not results: return None, []
    last = load_json(results[-1], {}); reg = load_json(os.path.join(gd, "claims.json"), {"claims": []})
    return bool(last.get("passed")), [c["id"] for c in reg["claims"]]

def export(t, label):
    m = method(); prods = {p["type"]: p for p in m["artefacts"].get("produces", [])}
    if t in ENGINE_TYPES and t not in prods:   # engine-built from run state, for every method
        pr = {"source": ENGINE_SOURCES[t]}; passed, ids = True, []; data = ENGINE_TYPES[t]()
    else:
        if t not in prods: sys.exit(f"this method produces: {', '.join(prods) or 'nothing declared'} (engine types: {', '.join(ENGINE_TYPES)})")
        pr = prods[t]; src = os.path.join(ROOT, pr["source"])
        if not os.path.exists(src): sys.exit(f"source {pr['source']} missing - the artefact is built from the passed analysis JSON")
        passed, ids = (passed_claims(pr["scope"]) if pr.get("scope") else (True, []))
        if passed is False and "--force" not in sys.argv: sys.exit(f"scope {pr['scope']} has not passed its gauntlet - export only released, passed artefacts (--force with a logged assumption)")
        data = load_json(src)
    os.makedirs(HANDOVER_DIR, exist_ok=True); date = time.strftime("%Y-%m-%d")
    name = f"{t}-{run_name()}-{date}.json"; out = os.path.join(HANDOVER_DIR, name)
    env = {"artefact_type": t, "run": run_name(), "method": m["name"], **method_provenance(run_file(), m), "released": date, "label": label, "source": pr["source"], "scope": pr.get("scope"), "passed_claim_ids": ids, "gauntlet_passed": passed, "engine_version": project().get("engine_version"), "data": data}
    json.dump(env, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1); h = sha(out); open(out + ".sha256", "w").write(h + "\n")
    man, mp = manifest(); man["released"] = [r for r in man["released"] if r["file"] != name] + [{"type": t, "run": run_name(), "method": m["name"], "released": date, "file": name, "sha256": h, "claims": len(ids), "label": label}]
    json.dump(man, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    st = load_json(STATUS_PATH, {})
    if st: st.setdefault("handover", {}).setdefault("exported", []).append({"type": t, "file": name, "sha256": h, "t": date}); save_json(STATUS_PATH, st)
    print(f"released {t} -> handover/{name} (sha {h[:12]}, {len(ids)} passed claims). A later run imports it with `dbcx handover import {t}`.")

def imp(what, as_type, mapping):
    m = method(); cons = {c["type"]: c for c in m["artefacts"].get("consumes", [])}
    man, _ = manifest()
    if os.path.exists(what): src = os.path.abspath(what); t = as_type or (json.load(open(src, encoding="utf-8")).get("artefact_type") if src.endswith(".json") else None) or os.path.splitext(os.path.basename(src))[0]
    else:
        cands = sorted([r for r in man["released"] if r["type"] == what], key=lambda r: r["released"])
        if not cands: sys.exit(f"no released artefact of type {what} in {HANDOVER_DIR} (dbcx handover list) - pass a file path for an external import")
        src = os.path.join(HANDOVER_DIR, cands[-1]["file"]); t = what
    if cons and t not in cons and t not in ENGINE_TYPES: print(f"WARNING: this method does not declare consuming '{t}' (declared: {', '.join(cons)}) - imported anyway as evidence")
    dst_dir = os.path.join(ROOT, "input", "handover"); os.makedirs(dst_dir, exist_ok=True); dst = os.path.join(dst_dir, f"{t}.json")
    released = os.path.normcase(src).startswith(os.path.normcase(os.path.abspath(HANDOVER_DIR)) + os.sep)
    if src.endswith(".json"): shutil.copy(src, dst)
    else:
        shutil.copy(src, os.path.join(dst_dir, os.path.basename(src)))
        json.dump({"artefact_type": t, "external_file": os.path.basename(src), "provenance": "external", "mapping": mapping}, open(dst, "w", encoding="utf-8"), indent=1)
    h = sha(src); open(dst + ".sha256", "w", encoding="utf-8").write(h + "\n")
    rec = {"type": t, "source_path": src, "sha256": h, "imported": time.strftime("%Y-%m-%d"), "provenance": "released-run" if released else "external", "mapping": mapping}
    rf = load_json("run.json", {}); rf.setdefault("handover", {}).setdefault("imports", []); rf["handover"]["imports"] = [x for x in rf["handover"]["imports"] if x["type"] != t] + [rec]; save_json("run.json", rf)
    st = load_json(STATUS_PATH, {})
    if st: st.setdefault("handover", {}).setdefault("imported", []).append(rec); save_json(STATUS_PATH, st)
    c = cons.get(t)
    if c and c.get("target") and released:
        env = json.load(open(dst, encoding="utf-8")); save_json(c["target"], env.get("data", env)); print(f"materialised {c['target']} from the released artefact")
    elif c and c.get("import_tool") and not released: print(f"external import: run `dbcx {c['import_tool']} {os.path.join('input/handover', os.path.basename(src))}` (with the mapping) to materialise {c.get('target')}")
    print(f"imported {t} ({rec['provenance']}, sha {h[:12]}) -> input/handover/{t}.json ; cite rows as HO-{t}#<id>; inputs of this run are now frozen for this artefact")
    if t == "client-assumptions": print(f"next: `dbcx questions import-handover input/handover/{t}.json` puts the assumptions (A-nn and answers kept) into this run's register")
    if t == "knowledge-base": print(f"next: `dbcx kb import-handover input/handover/{t}.json [--as-global]` puts the entries (as KB-H-n) into this run's knowledge base")

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    def opt(k, d=""): return a[a.index(k) + 1] if k in a else d
    if a[0] == "export":
        m = method(); prods = [p["type"] for p in m["artefacts"].get("produces", [])]
        ts = [a[1]] if len(a) > 1 and not a[1].startswith("--") else prods
        for t in ts: export(t, opt("--label"))
    elif a[0] == "list":
        man, _ = manifest()
        for r in sorted(man["released"], key=lambda r: r["released"]): print(f"{r['released']} {r['type']:24s} run {r['run']:28s} claims {r['claims']:4d} sha {r['sha256'][:12]} {r.get('label', '')}")
        print(f"{len(man['released'])} released artefact(s) in {HANDOVER_DIR}")
    elif a[0] == "import": imp(a[1], opt("--as"), opt("--mapping"))
    elif a[0] == "types":
        m = method(); print("consumes:", ", ".join(f"{c['type']}{' (required)' if c.get('required') else ''}" for c in m["artefacts"].get("consumes", [])) or "-"); print("produces:", ", ".join(p["type"] for p in m["artefacts"].get("produces", [])) or "-")
        print("engine (every method):", ", ".join(ENGINE_TYPES))
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
