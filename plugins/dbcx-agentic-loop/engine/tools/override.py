#!/usr/bin/env python3
"""Engagement overrides with provenance: tune one engagement without touching the plugin (the installed copy is read-only).

Usage: dbcx override add <target> --why "..." [--learning L-nnn] (--set <dotted.key>=<value> [--set ...] | --text "..." | --from <file>)
                                     <value> is parsed as JSON, else taken as text (--set scoring.pass_threshold=7.5, --set languages.deliverable=en)
       dbcx override list [--all] [--json]    the active overrides (--all: removed ones too)
       dbcx override check [--json]           stale overrides; exit 1 when one is stale (`dbcx doctor` warns with the same list)
       dbcx override remove <O-nnn> --why "..."
Targets (files under <engagement>/overrides/):
  settings.json                any run setting (no protected keys); merged after engagement.json, before run.json
  knowledge.json | labels.<lang>.json | deliverables.<lang>.json | snippets.json    as a run's overrides/ file, before the run's own
                               (deliverables: `--set patches=[...]` appends id-keyed patches, see xl_spec.py)
  briefs/<role>.md             PROJECT NOTES appended to that role's brief (`dbcx render brief`); --text / --from; several notes concatenate
  adapter.py                   the engagement's scan adapter (--from; one override owns it)
Full order: engine defaults <- method <- profile <- packs <- engagement.json <- engagement overrides <- run.json <- run overrides.

Provenance format (the export of a later package builds on it). <engagement>/overrides/OVERRIDES.json is the source of truth; every target
file is regenerated from it after each add / remove (JSON targets: the active entries' `set` deep-merged in id order; .md: their `text`
joined by a blank line; .py: the one entry's `text`). A target file that differs from what the register generates was edited by hand:
`add` / `remove` refuse to overwrite it and `check` flags it.
  {"format": 1, "overrides": [
    {"id": "O-001",                     O-nnn, never reused (a removed entry keeps its id)
     "target": "settings.json",         path relative to <engagement>/overrides/
     "keys": ["scoring.pass_threshold"],  dotted keys the entry sets; for briefs/<role>.md: [<role>]; for adapter.py: []
     "set": {"scoring": {"pass_threshold": 7.5}},  JSON targets only - the nested value the keys spell
     "text": "...",                     .md / .py targets only
     "learning": "<id>",                the learning (id in the run's learnings file) or ""
     "run": "runs/2026-09-code-analysis", "method": "code-analysis",   where it was written ("" at engagement level)
     "why": "...", "plugin_version": "0.10.dev", "plugin_commit": "<sha from COMMIT or ''>", "date": "YYYY-MM-DD",
     "removed": {"date": "YYYY-MM-DD", "why": "..."}}]}   only on removed entries
Stale (`check`) = real breakage only (plugin_version is provenance, `list` shows it; an update alone never makes an override stale): a target file that is not a known kind (labels / deliverables
for a language the plugin lacks); a key the plugin's own configuration (override layers off) no longer has - a key under an empty map
(model_overrides, a new snippet a method names in notes_keys) counts as existing; a brief role no role text exists for; a deliverables
patch that no longer applies; a hand-edited target file.
"""
import copy, glob, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import PP, RUN, PROJECT_DIR, CLI, ENGINE, SPEC, read_json, atomic_save_json, deep_merge, relp
from runtime import package_commit, package_version

REG = PP("overrides", "OVERRIDES.json")
JSON_T = re.compile(r"^(settings|knowledge|snippets)\.json$|^(labels|deliverables)\.([a-z]{2})\.json$")
BRIEF_T = re.compile(r"^briefs/([a-z0-9][a-z0-9-]*)\.md$")

def load(): return read_json(REG, {"format": 1, "overrides": []})
def active(reg=None): return [o for o in (reg or load())["overrides"] if not o.get("removed")]

def kind(target):
    if JSON_T.match(target): return "json"
    if BRIEF_T.match(target): return "md"
    if target == "adapter.py": return "py"
    return None

def render(reg, target):
    """the content the register generates for one target file (None = no active entry: the file must not exist)"""
    es = [o for o in active(reg) if o["target"] == target]
    if not es: return None
    if kind(target) == "json":
        out = {}
        for o in es:
            pt = (out.get("patches") or []) + (o["set"].get("patches") or []); out = deep_merge(out, o["set"])
            if pt: out["patches"] = pt
        return out
    return "\n\n".join(o["text"].strip() for o in es) + "\n"

def on_disk(target):
    p = PP("overrides", target)
    if not os.path.exists(p): return None
    return read_json(p) if kind(target) == "json" else open(p, encoding="utf-8").read()

def hand_edited(reg, target): return on_disk(target) != render(reg, target)

def write_target(reg, target):
    p = PP("overrides", target); c = render(reg, target)
    if c is None:
        if os.path.exists(p): os.remove(p)
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(json.dumps(c, ensure_ascii=False, indent=2) + "\n" if kind(target) == "json" else c)

def nest(key, value):
    for part in reversed(key.split(".")): value = {part: value}
    return value

def parse_value(v):
    try: return json.loads(v)
    except ValueError: return v

def add(a):
    def opt(k): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else ""
    target = a[0] if a and not a[0].startswith("--") else ""; k = kind(target); why = opt("--why").strip(); lid = opt("--learning")
    if not k: sys.exit(f"dbcx override add: unknown target '{target}'\n" + __doc__)
    if not why: sys.exit("dbcx override add: --why is required (the reason is what a later reader and the plugin maintainer need)")
    if lid and not re.match(r"^L-\d{3}$", lid): sys.exit(f"--learning must be a learning id L-nnn, got {lid!r}")
    reg = load()
    if hand_edited(reg, target): sys.exit(f"REFUSED: overrides/{target} differs from {relp(REG, PROJECT_DIR)} (edited by hand) - move its content into `{CLI} override add` entries, then delete the file")
    e = {"id": "", "target": target}
    if k == "json":
        sets = [a[i + 1] for i, x in enumerate(a[:-1]) if x == "--set"]
        if not sets or any("=" not in x for x in sets): sys.exit("dbcx override add <json target>: one or more --set <dotted.key>=<value>")
        e["keys"] = [x.split("=", 1)[0] for x in sets]; e["set"] = {}
        for x in sets: e["set"] = deep_merge(e["set"], nest(*[x.split("=", 1)[0], parse_value(x.split("=", 1)[1])]))
    else:
        text = opt("--text") or (open(opt("--from"), encoding="utf-8").read() if opt("--from") else "")
        if not text.strip(): sys.exit("dbcx override add <.md|.py target>: --text \"...\" or --from <file>")
        if k == "py" and active(reg) and any(o["target"] == target for o in active(reg)): sys.exit(f"REFUSED: {target} is already owned by an override - remove it first")
        e["keys"] = [BRIEF_T.match(target).group(1)] if k == "md" else []; e["text"] = text
    n = max([int(o["id"][2:]) for o in reg["overrides"]] + [0]) + 1; e["id"] = f"O-{n:03d}"
    run_rel = relp(RUN, PROJECT_DIR) if RUN != PROJECT_DIR else ""
    e.update({"learning": lid, "run": run_rel, "method": (common.method_name() or "") if run_rel else "", "why": why,
              "plugin_version": package_version(), "plugin_commit": package_commit(), "date": time.strftime("%Y-%m-%d")})
    reg["overrides"].append(e); write_target(reg, target); atomic_save_json(REG, reg)
    print(f"{e['id']} -> overrides/{target}" + (f" ({', '.join(e['keys'])})" if e["keys"] else "") + f" - plugin {e['plugin_version']}" + (f", from {lid}" if lid else ""))

def remove(a):
    oid = a[0] if a else ""; why = a[a.index("--why") + 1] if "--why" in a and a.index("--why") + 1 < len(a) else ""
    if not why: sys.exit("dbcx override remove <O-nnn> --why \"...\"")
    reg = load(); e = next((o for o in active(reg) if o["id"] == oid), None)
    if not e: sys.exit(f"no active override {oid}")
    if hand_edited(reg, e["target"]): sys.exit(f"REFUSED: overrides/{e['target']} was edited by hand - resolve that first (`{CLI} override check`)")
    e["removed"] = {"date": time.strftime("%Y-%m-%d"), "why": why}; write_target(reg, e["target"]); atomic_save_json(REG, reg)
    print(f"{oid} removed (overrides/{e['target']} regenerated)")

def summary():
    """one line for `dbcx status`"""
    act = active() if os.path.exists(REG) else []
    if not act: return ""
    return f"  engagement overrides: {len(act)} active ({', '.join(sorted(set(o['target'] for o in act)))}) - {CLI} override list / check"

# ------------------------------------------------------------------ stale check
def has_path(base, key):
    """the dotted key exists in the plugin's own configuration; a key below an empty (open) map counts as existing"""
    cur = base
    for part in key.split("."):
        if not isinstance(cur, dict): return False
        if part not in cur: return cur == {}
        cur = cur[part]
    return True

def plugin_base(lang_targets):
    """the configuration, knowledge, labels and specs WITHOUT any override layer (engagement or run)"""
    common.OVERRIDES_ON[0] = False; common._PROJECT_CACHE.clear()
    try:
        cfg = common.project(); out = {"settings.json": cfg, "knowledge.json": common.knowledge(), "snippets.json": common.snippets(cfg)}
        for t in lang_targets:
            kd, lang = JSON_T.match(t).group(2, 3)
            out[t] = common.labels(lang) if kd == "labels" else common.deliverables_spec(lang)
        return out
    finally: common.OVERRIDES_ON[0] = True; common._PROJECT_CACHE.clear()

def brief_roles():   # every method this project can run (its own methods and the plugin's): an override on an own method is not stale
    names = [os.path.basename(f) for f in glob.glob(os.path.join(ENGINE, "briefs", "*.md")) + [g for e in common.method_index().values() for g in glob.glob(os.path.join(e["dir"], "briefs", "*.md"))]]
    return {n[:-3].split(".")[0] for n in names}

def notes_keys():
    out = set()
    for f in (os.path.join(e["dir"], "method.json") for e in common.method_index().values()):
        for ks in ((read_json(f).get("briefs") or {}).get("notes_keys") or {}).values(): out.update(ks)
    return out

def check():
    """-> [{id, target, reasons}] for every stale active override, plus hand-edited target files"""
    reg = load(); act = active(reg); out = []
    def spec_file(m): return os.path.join(SPEC, f"labels.{m.group(3)}.json" if m.group(2) == "labels" else f"deliverables.common.{m.group(3)}.json")
    langs = sorted({o["target"] for o in act if JSON_T.match(o["target"]) and JSON_T.match(o["target"]).group(2)})
    missing_lang = {t for t in langs if not os.path.exists(spec_file(JSON_T.match(t)))}
    in_run = bool(common.method_name()); base = plugin_base([t for t in langs if t not in missing_lang]) if act and in_run else {}
    roles = brief_roles(); nk = notes_keys()
    for o in act:
        r = []; t = o["target"]
        if not kind(t) or t in missing_lang: r.append(f"target overrides/{t} is no file kind the plugin reads")
        elif kind(t) == "md" and o["keys"][0] not in roles: r.append(f"role '{o['keys'][0]}' has no role text in the plugin (engine/briefs, methods/*/briefs)")
        elif kind(t) == "json" and in_run:   # keys are method-specific: checked inside a run only
            for key in o["keys"]:
                if key == "patches" and t.startswith("deliverables."):
                    spec = copy.deepcopy(base[t]); spec["patches"] = o["set"].get("patches") or []
                    from xl_spec import apply_patches
                    r += [f"patch no longer applies: {x}" for x in apply_patches(spec)["_patch_errors"]]
                elif not (has_path(base[t], key) or (t == "snippets.json" and key in nk)): r.append(f"key '{key}' no longer exists in the plugin's {t[:-5]}")
        if r: out.append({"id": o["id"], "target": t, "reasons": r})
    od = PP("overrides"); files = {relp(os.path.join(dp, f), od).replace(os.sep, "/") for dp, _, fs in os.walk(od) for f in fs} if os.path.isdir(od) else set()
    for t in sorted({o["target"] for o in reg["overrides"]} | {f for f in files if kind(f)}):
        if hand_edited(reg, t): out.append({"id": "-", "target": t, "reasons": [f"overrides/{t} differs from {os.path.basename(REG)} (edited by hand)"]})
    return out

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"): print(__doc__); return
    cmd, rest = a[0], a[1:]
    if cmd == "add": add(rest)
    elif cmd == "remove": remove(rest)
    elif cmd == "list":
        es = load()["overrides"] if "--all" in rest else active()
        if "--json" in rest: print(json.dumps(es, indent=2, ensure_ascii=False)); return
        for o in es:
            print(f"{o['id']} {o['target']:28s} {', '.join(o['keys']) or '-':40s} written for {o.get('plugin_version')} {o.get('date')}" + (f" from {o['learning']}" if o.get("learning") else "") + (f" REMOVED {o['removed']['date']}" if o.get("removed") else "") + f"\n      why: {o['why']}")
        print(f"{len(es)} override(s) in {relp(REG, RUN)}")
    elif cmd == "check":
        st = check()
        if "--json" in rest: print(json.dumps(st, indent=2, ensure_ascii=False))
        else:
            for s in st:
                for x in s["reasons"]: print(f"STALE {s['id']} {s['target']}: {x}")
            print(f"{len(st)} stale override(s)" if st else f"{len(active()) if os.path.exists(REG) else 0} override(s), none stale")
            if not common.method_name(): print("(not inside a run: setting / knowledge / label / deliverable keys were not checked - run it in a run folder)")
        sys.exit(1 if st else 0)
    else: sys.exit(f"unknown command {cmd}\n{__doc__}")

if __name__ == "__main__":
    main()
