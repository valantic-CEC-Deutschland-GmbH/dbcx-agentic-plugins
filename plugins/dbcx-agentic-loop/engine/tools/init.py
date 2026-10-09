#!/usr/bin/env python3
"""Create an engagement folder and/or a run folder for the dbcx-agentic-loop plugin.

Usage:
  dbcx init engagement --dir <client-folder> --client "Name" --consultancy "Name" [--lang de|en] [--personas p1,p2] [--knowledge slot=pack,...]
        writes <dir>/engagement.json + input/ corpus/ reference/ handover/ runs/          (shared, slowly growing assets of one client project)
  dbcx init run --method <method> [--dir <run-folder>] [--name <run-name>] [--title "..."] [--knowledge slot=pack,...] [--lang de|en]
        [--profile full|lean] [--import <artefact-type>=<released file>]... [--chain-next <method>] [--force]   (run in or below the engagement folder)
        --profile: how heavy the loop is - full (default: scope analysts in waves, a client critic and one or more standard
        critics) or lean (no scope split, one standard critic on the consolidations, quotes required, rulings first); refused when the method
        declares no such profile (method.json profiles)
        writes <run>/run.json (client fields inherited from engagement.json, method fields as placeholders unless given, method_source,
        method_version and method_origin of the method found - an own method in <engagement>/methods/<m>/ before the plugin's; origin =
        the card's custom | derived, plugin for a plugin method, + method_installed_from / method_library_version for a library copy), CLAUDE.md,
        docs/PLAN.md, templates/, schemas/, requirements_mapping.json (when the method consumes a requirements-set), empty working folders.
  dbcx init --list-methods | --list-packs [kind]
Idempotent: existing files are kept unless --force; run.json is merged (given flags win). A run without an engagement folder above it is a
single-run project (RUN == PROJECT); `dbcx init engagement` first is the recommended shape whenever a second method may follow.
"""
import json, os, sys, subprocess, shutil, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from runtime import package_version
from common import PLUGIN, TOOLS, DEFAULTS, list_packs, list_methods, method_index, method_clashes, method, pack, read_json, deep_merge, CLI, relp
import method as own_methods   # method_origin stamp (the module; `method` stays common.method)

PH = lambda t: f"<<PLACEHOLDER: {t}>>"
def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name); return sys.argv[i + 1]
    return default
def kv_list(name):
    out = {}
    for tok in [x for i, x in enumerate(sys.argv) if i > 0 and sys.argv[i - 1] == name]:
        for part in tok.split(","):
            if "=" in part: k, v = part.split("=", 1); out[k.strip()] = v.strip()
    return out
def version(): return package_version()
def target():
    """(engagement folder or None, the folder whose methods/ init resolves from) of the TARGET run: above --dir, else above the
    cwd - the same rule the tools apply inside the run (a single-run project resolves from the run folder itself)"""
    t = os.path.abspath(arg("--dir", os.getcwd())); proj = common._up(t, common.PROJECT_FILE); return proj, proj or t

def init_engagement():
    d = os.path.abspath(arg("--dir", os.getcwd())); os.makedirs(d, exist_ok=True); pf = os.path.join(d, common.PROJECT_FILE)
    existing = read_json(pf, {}) if os.path.exists(pf) else {}
    cfg = {"engine_version": version(), "created": time.strftime("%Y-%m-%d"),
           "engagement": {"consultancy": arg("--consultancy", existing.get("engagement", {}).get("consultancy") or PH("consultancy name")), "client": arg("--client", existing.get("engagement", {}).get("client") or PH("client name")),
                          "title": arg("--title", existing.get("engagement", {}).get("title") or PH("project title")), "client_context": arg("--context", existing.get("engagement", {}).get("client_context") or PH("1-2 sentences: industry, business model, markets, what the client wants to decide"))},
           "languages": {"deliverable": arg("--lang", existing.get("languages", {}).get("deliverable", "de")), "chat": "en"},
           "scoring": {"gate_personas": arg("--personas", ",".join(existing.get("scoring", {}).get("gate_personas", ["cto", "head_of_it", "head_of_ecommerce", "product_owner"]))).split(",")},
           "knowledge": deep_merge(existing.get("knowledge", {}), kv_list("--knowledge")),
           "runs": existing.get("runs", []),
           "_readme": "Shared by every run of this client project. input/ = everything the client hands over (by date); corpus/ = indexed text of those inputs with stable locators (dbcx corpus index); reference/ = verified vendor/reference facts; handover/ = released artefacts of finished runs; runs/<date-method>/ = one folder per method execution."}
    cfg = deep_merge(existing, cfg) if existing else cfg
    json.dump(cfg, open(pf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for sub in ("input", "corpus", "reference", "handover", "runs"): os.makedirs(os.path.join(d, sub), exist_ok=True)
    gi = os.path.join(d, ".gitignore")
    if not os.path.exists(gi): open(gi, "w", encoding="utf-8").write("runs/*/analysis/**/*.json\nruns/*/work/\nruns/*/state/derived_knowledge.json\ncorpus/text/\nreference/vendor-code/\n__pycache__/\n.DS_Store\n")
    print(f"engagement ready at {d}\nnext: drop client material into input/, then `{CLI} init run --method <m>` inside runs/ (methods: {', '.join(list_methods(d))})")

def init_run():
    mname = arg("--method"); proj_dir, base = target()
    if not mname: sys.exit(f"--method required (available: {', '.join(list_methods(base))})")
    m = method(mname, base); prof = arg("--profile")
    if prof and prof != "full" and prof not in (m.get("profiles") or {}): sys.exit(f"REFUSED: profile '{prof}' is not supported by method {mname} (supported: {', '.join(['full'] + [k for k in (m.get('profiles') or {}) if k not in ('full',) and not k.startswith('_')])})")
    default_dir = os.path.join(proj_dir, "runs", arg("--name", f"{time.strftime('%Y-%m')}-{mname}")) if proj_dir else os.getcwd()
    d = os.path.abspath(arg("--dir", default_dir)); os.makedirs(d, exist_ok=True); rf = os.path.join(d, common.RUN_FILE)
    force = "--force" in sys.argv; existing = read_json(rf, {}) if os.path.exists(rf) else {}
    eng = read_json(os.path.join(proj_dir, common.PROJECT_FILE), {}) if proj_dir else {}
    cfg = {"engine_version": existing.get("engine_version") or version(), "method": mname, "method_source": m["_source"], "method_version": m.get("version", ""), **own_methods.origin_stamp(m), "created": time.strftime("%Y-%m-%d"), "run_name": os.path.basename(d),
           "engagement": {"run_title": arg("--title", existing.get("engagement", {}).get("run_title") or m.get("display", mname))},
           "knowledge": deep_merge(existing.get("knowledge", {}), kv_list("--knowledge")),
           "languages": {"deliverable": arg("--lang", existing.get("languages", {}).get("deliverable") or eng.get("languages", {}).get("deliverable", "de")), "chat": "en"},
           "evidence_bases": existing.get("evidence_bases", []), "handover": {"imports": existing.get("handover", {}).get("imports", [])}, "chain_next": arg("--chain-next", existing.get("chain_next", ""))}
    if prof: cfg["profile"] = prof   # only when given: a run without the key is `full`
    if not proj_dir:   # single-run project: client fields live here
        cfg["engagement"].update({"consultancy": arg("--consultancy", PH("consultancy name")), "client": arg("--client", PH("client name")), "title": arg("--title", PH("engagement title")), "client_context": arg("--context", PH("1-2 sentences of client context"))})
        cfg["scoring"] = {"gate_personas": arg("--personas", "cto,head_of_it,head_of_ecommerce,product_owner").split(",")}
    # knowledge slots: defaults and placeholders
    for slot, sdef in m.get("knowledge_slots", {}).items():
        if slot not in cfg["knowledge"] and slot not in eng.get("knowledge", {}):
            if sdef.get("default"): cfg["knowledge"][slot] = sdef["default"]
            elif sdef.get("required"): cfg["knowledge"][slot] = PH(f"{sdef.get('kind', 'knowledge')} pack for slot {slot} ({CLI} pack list {sdef.get('kind', '')}s)")
    # method-declared client fields that are still open (placeholders listed by the method) - e.g. repo.path, source.version
    for path, hint in (m.get("init_fields") or {}).items():
        cur = cfg
        parts = path.split(".")
        for part in parts[:-1]: cur = cur.setdefault(part, {})
        flag = "--" + path.replace(".", "-").replace("_", "-")
        given = arg(flag)
        if given is not None: cur[parts[-1]] = given.split(",") if isinstance(hint, dict) and hint.get("list") else given
        elif parts[-1] not in cur and not _nested_get(existing, path): cur[parts[-1]] = PH(hint if isinstance(hint, str) else hint.get("hint", path))
    cfg = deep_merge(existing, cfg) if existing and not force else cfg
    json.dump(cfg, open(rf, "w", encoding="utf-8"), ensure_ascii=False, indent=2); print("wrote", relp(rf, os.getcwd()))
    for sub in ("input/handover", "overrides", "templates", "schemas", "state", "docs/questions", "analysis/gauntlet", "analysis/gate", "analysis/summaries", "analysis/briefs", "analysis/consolidated", "deliverables", "work"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    os.makedirs(os.path.join(d, m["scopes"].get("output_dir", "analysis/scopes")), exist_ok=True)
    if m.get("inventory"): os.makedirs(os.path.dirname(os.path.join(d, m["inventory"]["output"])), exist_ok=True)
    consumes = {c["type"]: c for c in m.get("artefacts", {}).get("consumes", [])}
    if "requirements-set" in consumes:
        rm = os.path.join(d, "requirements_mapping.json"); os.makedirs(os.path.join(d, "input", "requirements"), exist_ok=True)
        if force or not os.path.exists(rm): shutil.copy(os.path.join(DEFAULTS, "requirements_mapping.template.json"), rm); print("wrote requirements_mapping.json (fill the sheet/column mapping, or import a released requirements-set with dbcx handover import)")
    if not proj_dir:
        for sub in ("reference", "corpus", "handover", "input"): os.makedirs(os.path.join(d, sub), exist_ok=True)
    gi = os.path.join(d, ".gitignore")
    if not os.path.exists(gi): open(gi, "w", encoding="utf-8").write("analysis/gauntlet/*/round*.json\nanalysis/**/*.json\nwork/\nstate/derived_knowledge.json\nreference/vendor-code/\n__pycache__/\n.DS_Store\n")
    env = dict(os.environ, DBCX_RUN=d)
    for args in (["render.py", "instructions"] + (["--force"] if force else []), ["render.py", "plan"] + (["--force"] if force else []), ["render.py", "reference"] + (["--force"] if force else []), ["md_to_json.py", "--generate"]):
        r = subprocess.run([sys.executable, os.path.join(TOOLS, args[0])] + args[1:], env=env, capture_output=True, text=True)
        print((r.stdout.strip().splitlines() or [""])[-1], r.stderr.strip()[-300:] if r.returncode else "")
    for imp in [x for i, x in enumerate(sys.argv) if i > 0 and sys.argv[i - 1] == "--import"]:
        if "=" in imp:
            t, f = imp.split("=", 1); subprocess.run([sys.executable, os.path.join(TOOLS, "handover.py"), "import", f, "--as", t], env=env)
    if proj_dir:
        eg = read_json(os.path.join(proj_dir, common.PROJECT_FILE), {}); runs = eg.setdefault("runs", [])
        rel = relp(d, proj_dir)
        if not any(r.get("dir") == rel for r in runs): runs.append({"dir": rel, "method": mname, "created": time.strftime("%Y-%m-%d")}); json.dump(eg, open(os.path.join(proj_dir, common.PROJECT_FILE), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "check_fill.py"), "--quiet"], env=env, capture_output=True, text=True); print(r.stdout.strip())
    print(f"\nrun ready at {d} (method {mname})\nnext: fill the placeholders ({CLI} check_fill), provide the inputs the method consumes ({', '.join(consumes) or 'none'}), then \"Execute the plan\" (docs/PLAN.md)")

def _nested_get(d, path):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur: return None
        cur = cur[part]
    return cur

def main():
    if "--list-methods" in sys.argv:
        base = target()[1]
        for n, e in method_index(base).items(): print(f"{n:24s} {e['source']:10s} {method(n, base).get('display', '')}")
        for n, d in method_clashes(base).items(): print(f"{n:24s} REFUSED    own method in {d} reuses a plugin method's name")
        return
    if "--list-packs" in sys.argv:
        i = sys.argv.index("--list-packs"); kind = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else None
        for k, n in list_packs(kind): pk = pack(n, k); print(f"{k + '/' + n:36s} roles={','.join(pk.get('roles', []))}  {pk.get('display', '')}")
        return
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    what = a[0] if a else ("run" if "--method" in sys.argv else None)
    if what == "engagement": init_engagement()
    elif what == "run": init_run()
    else: print(__doc__)

if __name__ == "__main__":
    main()
