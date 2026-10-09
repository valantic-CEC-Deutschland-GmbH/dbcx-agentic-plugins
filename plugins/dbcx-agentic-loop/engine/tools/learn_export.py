#!/usr/bin/env python3
"""Learnings export / import: a colleague sends ONE anonymised, self-contained file to the plugin maintainer, who can reproduce
every upstream learning WITHOUT access to the colleague's project. Nothing here writes into the installed plugin (it is read-only).

Colleague side (inside a run folder of the engagement):
  dbcx learn repro <L-id> --kind tool|agent|fact|none [--note "..."]      stage a reproduction package for one learning of THIS run
         tool   (a) tool defect:   --file <path>[:a-b] ... --command "dbcx ..." --observed <file> --expected "..."
                    the files become a minimal fixture in the smoke-fixture layout (engagement.json + runs/<run>/run.json + the excerpts at
                    their engagement-relative paths; a single-run project: run.json + run-relative paths; files outside the engagement land
                    under _external/). The command runs in the run folder of the fixture; repro runs it once in a clean temp copy and prints
                    the output, so you see whether the fixture reproduces standalone before you export.
         agent  (b) agent behaviour: --brief <file>[:a-b] --output <file>[:a-b] --caught "critic score / gate finding that caught it"
                    exported as "observational" (a maintainer cannot re-run an agent deterministically)
         fact   (c) knowledge fact: --fact "..." --applies "<versions>" --url <public URL> --date YYYY-MM-DD
         none   (d) not reproducible standalone: --ask "what the maintainer would need to ask you"
       dbcx learn repro <L-id> --show | --drop
  dbcx learn anonymise add <term> [--as <placeholder>|<prefix>]   register a client-side identifier (system, extension/module, person name);
                                           --as ext numbers it <ext-1>, <ext-2> ...; --as "<crm>" is taken literally; default <term-n>
       dbcx learn anonymise list | remove <term>
  dbcx learn export --preview              print everything that would leave the project, plus a residual-risk scan
       dbcx learn export [--out <file>] [--all-runs]   write <engagement>/learnings/exports/<export-id>.zip (all runs of the engagement;
                                           --all-runs is accepted for symmetry with the old harvest, it is the default)
       --with-method [<name>,...] | --without-method the engagement has an own method: send it along (without names: the ones
                                           the exported runs used; its folder with
                                           method-card.json and METHOD-CARD.md, caches and binary files left out, anonymised in the path-safe
                                           form) or not; the user decides, and the export refuses until they did. Every export carries the
                                           run's method source, version and origin and the retrieval metrics (numbers only, state/RETRIEVAL.json)
Maintainer side (inside a git checkout of the plugin):
  dbcx learn import <export-file>          append one block with provenance to the plugin's learnings inbox (upstream and unresolved learnings
                                           first, then overrides that might become defaults, then verified reference facts, then the rest
                                           in one line each) and unpack every tool-defect fixture into a candidates folder per export
                                           and every own method into it as well (README: origin, versions, card)

Intended orchestrator steps (the skill guides them; the judgement is Claude's, the mechanics are this tool's):
  1. `dbcx learn list --unresolved` in every run; give each learning a verdict (`dbcx learn resolve <id> --as project|upstream|dismissed`).
  2. For every upstream or unresolved learning choose the kind and cut the SMALLEST excerpt that still shows the problem: a tool defect gets
     the few input files the command reads (line ranges where a file is long) and the exact failing command; agent behaviour gets the brief
     section, the offending output lines and the score/finding that caught it; a fact gets its public source; anything that depends on the
     client's material as a whole is kind none with the question the maintainer would ask. `dbcx learn repro ...` per learning; check that
     a tool package's standalone output shows the defect.
  3. `dbcx learn anonymise add` every client-side name the excerpts carry (systems, extension/module identifiers, people); the client name
     from engagement.json / run.json is mapped to <client> automatically.
  4. `dbcx learn export --preview`; show the user the residual-risk list, add terms until the user confirms, then `dbcx learn export`.
     With an own method in the engagement, ask the user first whether it goes along (--with-method | --without-method on both calls).
  5. Tell the user the file path; they send it to the maintainer (the mapping table <engagement>/learnings/anonymise.json never leaves).

Anonymisation: one mapping for the whole export, applied case-insensitively (longest term first, one pass) to every text, excerpt, command,
path and file name. Prose uses <placeholder>; the files, command and outputs of a tool-defect package use the shell- and path-safe form
anon-<name> so the fixture still runs. The engagement's absolute path becomes <engagement> (anon: @project), the home folder ~.
"""
import glob, json, os, re, secrets, shutil, subprocess, sys, tempfile, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import RUN, PROJECT_DIR, PLUGIN, CLI, CORPUS_DIR, P, PP, read_json, atomic_save_json, relp
from runtime import package_commit, package_version

MAP = PP("learnings", "anonymise.json"); EXPORTS = PP("learnings", "exports")
KINDS = {"tool": "tool defect", "agent": "agent behaviour", "fact": "knowledge fact", "none": "not reproducible standalone"}
LEGAL = re.compile(r"[\s,]+(gmbh\s*&\s*co\.?\s*kg(aa)?|gmbh|ag|kg(aa)?|se|ug|e\.?\s?v\.?|inc\.?|ltd\.?|llc|plc|s\.?a\.?|b\.?v\.?|co\.?)\s*$", re.I)
ENTRY = re.compile(r"^### (L-\d{3}) \[([A-F])\] (.+?)\n(.*?)(?=^### |\Z)", re.M | re.S)

def run_slug(run_dir): return "run" if os.path.abspath(run_dir) == os.path.abspath(PROJECT_DIR) else os.path.basename(run_dir.rstrip(os.sep))
def stage_dir(run_dir, lid): return os.path.join(run_dir, "work", "learn-repro", lid)

# ------------------------------------------------------------------ anonymisation
def label_terms():
    """the client name of engagement.json / run.json and its core without the legal form"""
    out = set()
    for f in (os.path.join(PROJECT_DIR, "engagement.json"), os.path.join(RUN, "run.json")):
        c = str((read_json(f, {}).get("engagement") or {}).get("client") or "").strip()
        if not c or common.PLACEHOLDER_RE.search(c): continue
        out.add(c); core = c
        while LEGAL.search(core): core = LEGAL.sub("", core).strip()
        if len(core) >= 3: out.add(core)
    return out

def load_map(): return read_json(MAP, {"format": 1, "terms": []})

def mapping():
    """[(term, placeholder name)] - label terms -> client, then the registered ones"""
    return [(t, "client") for t in sorted(label_terms())] + [(e["term"], e["as"]) for e in load_map()["terms"]]

class Anon:
    def __init__(self):
        pairs = [(os.path.realpath(PROJECT_DIR), "engagement", "@project"), (os.path.abspath(PROJECT_DIR), "engagement", "@project"),
                 (os.path.expanduser("~"), "~", "~")] + [(t, n, None) for t, n in mapping()]
        self.by = {}
        for t, n, safe in pairs:
            if t and t.lower() not in self.by: self.by[t.lower()] = (n, safe)
        self.re = re.compile("|".join(re.escape(t) for t in sorted(self.by, key=len, reverse=True)), re.I) if self.by else None
    def __call__(self, s, safe=False):
        if not self.re or not isinstance(s, str): return s
        def sub(m):
            n, sp = self.by[m.group(0).lower()]
            return (sp or f"anon-{n}") if safe else (n if n == "~" else f"<{n}>")
        return self.re.sub(sub, s)
    def deep(self, v, safe=False):
        if isinstance(v, dict): return {self(k, safe): self.deep(x, safe) for k, x in v.items()}
        if isinstance(v, list): return [self.deep(x, safe) for x in v]
        return self(v, safe)
    def terms(self): return {t for t, (n, _) in self.by.items() if n not in ("engagement", "~")}

def anonymise_cmd(a):
    m = load_map(); sub = a[0] if a else "list"
    if sub == "add":
        term = a[1].strip() if len(a) > 1 else ""; ph = a[a.index("--as") + 1] if "--as" in a and a.index("--as") + 1 < len(a) else "term"
        if len(term) < 3 or term.startswith("--"): sys.exit("dbcx learn anonymise add <term> [--as <placeholder>|<prefix>] - a term has at least 3 characters")
        if any(e["term"].lower() == term.lower() for e in m["terms"]) or term.lower() in {t.lower() for t in label_terms()}: sys.exit(f"{term!r} is already mapped")
        if ph.startswith("<") and ph.endswith(">"): name = ph[1:-1]
        else:
            pre = re.sub(r"[^a-z0-9-]+", "-", ph.lower()).strip("-") or "term"
            name = f"{pre}-{sum(1 for e in m['terms'] if re.match(re.escape(pre) + r'-\d+$', e['as'])) + 1}"
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]*$", name) or name == "engagement": sys.exit(f"placeholder <{name}> is not allowed (letters, digits, - and _; not <engagement>)")
        m["terms"].append({"term": term, "as": name, "date": time.strftime("%Y-%m-%d")}); os.makedirs(os.path.dirname(MAP), exist_ok=True); atomic_save_json(MAP, m)
        print(f"{term} -> <{name}>   (mapping {relp(MAP, PROJECT_DIR)} stays in the engagement, it is never exported)")
    elif sub == "remove":
        term = a[1] if len(a) > 1 else ""; keep = [e for e in m["terms"] if e["term"].lower() != term.lower()]
        if len(keep) == len(m["terms"]): sys.exit(f"{term!r} is not a registered term")
        m["terms"] = keep; atomic_save_json(MAP, m); print(f"{term} removed")
    elif sub == "list":
        for t in sorted(label_terms()): print(f"{t:40s} -> <client>   (engagement label)")
        for e in m["terms"]: print(f"{e['term']:40s} -> <{e['as']}>   (registered {e['date']})")
    else: sys.exit(__doc__)

# ------------------------------------------------------------------ learnings of every run
def runs():
    ds = [os.path.dirname(os.path.dirname(f)) for f in sorted(glob.glob(os.path.join(PROJECT_DIR, "runs", "*", "docs", "LEARNINGS.md")))]
    if os.path.exists(P("docs", "LEARNINGS.md")) and RUN not in ds: ds.append(RUN)
    return ds

def verdict(status):
    s = status.strip()
    if s.startswith(("recorded", "open")): return "unresolved"
    if s.startswith("upstream"): return "upstream"
    if s.startswith("applied"): return "applied"
    if s.startswith("dismissed"): return "dismissed"
    return "project"   # project-only, closed (an F item resolved in the run)

def learnings(run_dir):
    f = os.path.join(run_dir, "docs", "LEARNINGS.md")
    out = []
    for m in ENTRY.finditer(open(f, encoding="utf-8").read() if os.path.exists(f) else ""):
        fields = dict(re.findall(r"^- (\w+): (.*)$", m.group(4), re.M))
        out.append({"id": m.group(1), "section": m.group(2), "title": m.group(3).strip(), "fields": fields, "verdict": verdict(fields.get("status", "recorded"))})
    return out

def run_meta(run_dir):
    import handover
    rj = read_json(os.path.join(run_dir, "run.json"), {}); ej = read_json(os.path.join(PROJECT_DIR, "engagement.json"), {})
    out = {"run": run_slug(run_dir), "method": rj.get("method", ""), "profile": rj.get("profile") or ej.get("profile") or "full",
           "knowledge": common.deep_merge(ej.get("knowledge") or {}, rj.get("knowledge") or {}),
           "language": (rj.get("languages") or ej.get("languages") or {}).get("deliverable", ""), "engine_version": rj.get("engine_version", ""),
           **handover.method_provenance(rj)}   # method_source, method_version, method_origin, derived_from
    rm = retrieval_metrics(run_dir, rj, ej)
    if rm: out["retrieval"] = rm
    return out

def retrieval_metrics(run_dir, rj, ej):
    """numbers only from state/RETRIEVAL.json, refreshed with `dbcx corpus metrics` - per unit (U1, U2 ...: no
    unit name) kind, strategy, mapped share, calls per role and tool, found_via; read budget, semantic index and the user's decision. None
    without a corpus map."""
    f = os.path.join(run_dir, "state", "RETRIEVAL.json")
    if not os.path.exists(f): return None
    env = {k: v for k, v in os.environ.items() if k not in ("DBCX_RUN", "DBCX_PROJECT", "DBCX_METHOD")}
    subprocess.run([sys.executable, os.path.join(PLUGIN, "engine", "dbcx.py"), "corpus", "metrics"], cwd=run_dir, env=env, capture_output=True, text=True, timeout=300)
    d = read_json(f, {}); units, calls, fv = [], {}, {}
    def add(tgt, c):
        for k, v in c.items(): tgt[k] = tgt.get(k, 0) + v
    for i, (u, e) in enumerate((d.get("units") or {}).items(), 1):
        own = {"inventory": "inventory", "consolidation": "consolidator"}.get(e.get("kind"), "analyst"); by = {}
        for agent, c in (e.get("calls") or {}).items():
            add(by.setdefault(agent[:-len(u) - 1] if agent.startswith("critic-") and agent.endswith("-" + u) else own, {}), c); add(calls, c)
        add(fv, e.get("found_via") or {})
        units.append({"unit": f"U{i}", **{k: e.get(k) for k in ("kind", "strategy", "engine_strategy", "set_by", "share", "mapped_tokens", "sources")}, "calls": by, "found_via": e.get("found_via") or {},
                      "after_pass": after_pass(os.path.join(run_dir, "analysis", "gauntlet", u))})
    other = {}
    for c in (d.get("other_calls") or {}).values(): add(other, c); add(calls, c)
    dec = ej.get("retrieval") or rj.get("retrieval") or {}
    ap = {k: sum(u["after_pass"][k] for u in units) for k in ("postpass_claims", "postpass_rows", "amended_claims")}
    vd = [x for f in glob.glob(os.path.join(run_dir, "analysis", "gate", "round*-verifier.json")) for x in (read_json(f, {}).get("defects") or [])]
    ap.update(verifier_defects=len(vd), verifier_content_defects=sum(1 for x in vd if x.get("kind", "content") == "content"), reference_refutations=refutations())
    return {"read_budget_tokens": d.get("read_budget_tokens"), "corpus_tokens": d.get("corpus_tokens"), "semantic_index": d.get("semantic") or "none",
            "semantic_decision": dec.get("semantic") or "none", "strategies": {k: sum(1 for x in units if x["strategy"] == k) for k in ("read", "search")},
            "calls": calls, "other_calls": other, "found_via": fv, "after_pass": ap, "units": units}

def after_pass(gd):
    """contradictions found after a scope passed (counts): claims and table rows a post-pass corrected (postpass-check.md), claims a critic
    re-scored against a lead fact (round*-result.json amendments)"""
    pc = os.path.join(gd, "postpass-check.md"); txt = open(pc, encoding="utf-8").read() if os.path.exists(pc) else ""
    m = re.search(r"^## Changed scored claims \((\d+)\)", txt, re.M); rows = txt.split("## Changed table rows", 1)[1].split("\n## ", 1)[0] if "## Changed table rows" in txt else ""
    am = [x for f in glob.glob(os.path.join(gd, "round*-result.json")) for x in (read_json(f, {}).get("amendments") or [])]
    return {"postpass_claims": int(m.group(1)) if m else 0, "postpass_rows": len(re.findall(r"^- ", rows, re.M)), "amended_claims": sum(len(x.get("claims") or []) for x in am)}

def refutations():
    """reference rows a critic or researcher refuted (engagement-level, section 7 of reference/platform-standard.md)"""
    import reference
    if not os.path.exists(reference.REF): return 0
    try: return sum(1 for _, c in reference.load()[4] if reference.norm(c)[5].lower().startswith("refutation"))
    except SystemExit: return 0

def metrics_lines(r):
    """the retrieval metrics of one run in a few Markdown lines (export README, inbox)"""
    def cs(c): return ", ".join(f"{k} {v}" for k, v in sorted(c.items())) or "-"
    m = r.get("retrieval")
    if not m: return []
    L = [f"- `{r['run']}`: read budget {m['read_budget_tokens']} tokens, corpus ~{m['corpus_tokens']} tokens, semantic index {m['semantic_index']} (user decision {m['semantic_decision']}); "
         f"strategies read {m['strategies']['read']} / search {m['strategies']['search']}; calls {cs(m['calls'])} (outside the units {cs(m['other_calls'])}); found_via {cs(m['found_via'])}; "
         f"after a pass: {cs(m.get('after_pass') or {})}"]
    for u in m["units"]:
        L.append(f"  - {u['unit']} {u['kind']}: {u['strategy']}" + (f" (engine {u['engine_strategy']}, set by {u['set_by']})" if u["strategy"] != u["engine_strategy"] else "")
                 + f", share {u['share']}, ~{u['mapped_tokens']} tokens in {u['sources']} source(s); calls " + ("; ".join(f"{role} {cs(c)}" for role, c in sorted(u["calls"].items())) or "-") + f"; found_via {cs(u['found_via'])}; after a pass {cs({k: v for k, v in (u.get('after_pass') or {}).items() if v})}")
    return L

# ------------------------------------------------------------------ reproduction packages (staging in the run)
def spec_of(arg):
    m = re.match(r"^(.*?):(\d+)(?:-(\d+))?$", arg)
    path, a, b = (m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))) if m and not os.path.exists(arg) else (arg, None, None)
    path = os.path.abspath(path)
    if not os.path.isfile(path): sys.exit(f"no file {path}")
    return path, a, b

def excerpt(path, a, b):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines(True)
    return "".join(lines[a - 1:b]) if a else "".join(lines)

def fixture_rel(path):
    """where a file sits in the fixture: engagement-relative (the run's own under runs/<run>/), else _external/<name>"""
    real, eng = os.path.realpath(path), os.path.realpath(PROJECT_DIR)
    return relp(real, eng).replace(os.sep, "/") if real.startswith(eng + os.sep) else "_external/" + os.path.basename(path)

def run_fixture(fx, cwd_rel, command):
    """the command once in a clean temp copy of the fixture, with the installed launcher on PATH -> (exit code, output)"""
    launcher = next((x for x in (os.path.join(PLUGIN, "scripts", "dbcx"), os.path.join(PLUGIN, "bin", "dbcx")) if os.path.exists(x)), None)
    with tempfile.TemporaryDirectory(prefix="dbcx-repro-") as t:
        shutil.copytree(fx, os.path.join(t, "fx")); bind = os.path.join(t, "bin"); os.makedirs(bind)
        if launcher: os.symlink(launcher, os.path.join(bind, "dbcx"))
        env = {k: v for k, v in os.environ.items() if k not in ("DBCX_RUN", "DBCX_PROJECT", "DBCX_METHOD")}; env["PATH"] = bind + os.pathsep + env.get("PATH", "")
        r = subprocess.run(["bash", "-c", command], cwd=os.path.join(t, "fx", cwd_rel), env=env, capture_output=True, text=True, timeout=300)
        out = r.stdout + r.stderr
        for x in (os.path.realpath(os.path.join(t, "fx")), os.path.join(t, "fx")): out = out.replace(x, "<fixture>")
        return r.returncode, out

def repro(a):
    lid = a[0] if a and re.match(r"^L-\d{3}$", a[0]) else sys.exit("dbcx learn repro <L-id> --kind tool|agent|fact|none ...\n" + __doc__)
    def opt(k): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else ""
    d = stage_dir(RUN, lid)
    if "--show" in a:
        print(open(os.path.join(d, "repro.json"), encoding="utf-8").read() if os.path.exists(os.path.join(d, "repro.json")) else f"{lid}: no package staged"); return
    if "--drop" in a: shutil.rmtree(d, ignore_errors=True); print(f"{lid}: package dropped"); return
    if not any(e["id"] == lid for e in learnings(RUN)): sys.exit(f"no learning {lid} in {relp(P('docs', 'LEARNINGS.md'), PROJECT_DIR)}")
    kind = opt("--kind")
    if kind not in KINDS: sys.exit("--kind must be tool, agent, fact or none")
    need = {"tool": ["--file", "--command", "--observed", "--expected"], "agent": ["--brief", "--output", "--caught"], "fact": ["--fact", "--applies", "--url", "--date"], "none": ["--ask"]}[kind]
    miss = [k for k in need if not opt(k).strip()]
    if miss: sys.exit(f"dbcx learn repro --kind {kind}: {', '.join(miss)} required")
    if kind == "fact" and not re.match(r"^https?://", opt("--url")): sys.exit("--url must be a public http(s) URL")
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    pk = {"learning": lid, "kind": kind, "label": KINDS[kind], "note": opt("--note"), "staged": time.strftime("%Y-%m-%d %H:%M")}
    if kind == "tool":
        fx = os.path.join(d, "fixture"); files = []
        eng = os.path.abspath(PROJECT_DIR) != os.path.abspath(RUN)
        run_rel = relp(RUN, PROJECT_DIR).replace(os.sep, "/") if eng else "."
        for f in ([os.path.join(PROJECT_DIR, "engagement.json")] if eng else []) + [os.path.join(RUN, "run.json")]:
            j = read_json(f, {}); e = j.get("engagement")
            if isinstance(e, dict): j["engagement"] = dict(e, title="<title>", client_context="<context>")
            j.pop("runs", None)   # engagement.json's run list holds cwd-relative paths the fixture does not need
            rel = relp(f, PROJECT_DIR).replace(os.sep, "/")
            os.makedirs(os.path.dirname(os.path.join(fx, rel)) or fx, exist_ok=True); open(os.path.join(fx, rel), "w", encoding="utf-8").write(json.dumps(j, indent=1, ensure_ascii=False))
        for i, x in enumerate(a[:-1]):
            if x != "--file": continue
            path, lo, hi = spec_of(a[i + 1]); rel = fixture_rel(path)
            os.makedirs(os.path.dirname(os.path.join(fx, rel)), exist_ok=True); open(os.path.join(fx, rel), "w", encoding="utf-8").write(excerpt(path, lo, hi))
            files.append({"path": rel, "lines": f"{lo}-{hi}" if lo else "all"})
        pk.update({"files": files, "cwd": run_rel, "command": opt("--command"), "expected": opt("--expected"), "observed": open(opt("--observed"), encoding="utf-8", errors="replace").read()})
        code, out = run_fixture(fx, run_rel, pk["command"]); pk["fixture_run"] = {"exit": code, "output": out[-6000:]}
        print(f"standalone run of the fixture (exit {code}):\n{out[-3000:]}\n-> compare with --observed; if it does not show the defect, add the missing input files and stage again")
    elif kind == "agent":
        for k in ("--brief", "--output"):
            path, lo, hi = spec_of(opt(k)); pk[k[2:]] = {"file": os.path.basename(path), "lines": f"{lo}-{hi}" if lo else "all", "text": excerpt(path, lo, hi)}
        pk.update({"caught": opt("--caught"), "observational": True})
    elif kind == "fact": pk.update({k[2:]: opt(k) for k in need})
    else: pk["ask"] = opt("--ask")
    atomic_save_json(os.path.join(d, "repro.json"), pk); print(f"{lid}: {KINDS[kind]} package staged in {relp(d, RUN)}")

# ------------------------------------------------------------------ export
def plugin_defaults(ovs):
    """{O-id: {key: plugin default}} for JSON targets (override layers off, in THIS run's method); md/py targets: a sentence"""
    import override
    out = {}; in_run = bool(common.method_name())
    langs = sorted({o["target"] for o in ovs if override.JSON_T.match(o["target"]) and override.JSON_T.match(o["target"]).group(2)})
    base = override.plugin_base(langs) if in_run and ovs else {}
    for o in ovs:
        k = override.kind(o["target"])
        if k == "md": out[o["id"]] = "no PROJECT NOTES (the plugin's role text only)"
        elif k == "py": out[o["id"]] = "the knowledge pack's own scan adapter"
        elif not in_run or o["target"] not in base: out[o["id"]] = "(not computed: export from inside a run)"
        else:
            dv = {}
            for key in o["keys"]:
                cur = base[o["target"]]
                for part in key.split("."): cur = cur.get(part) if isinstance(cur, dict) else None
                dv[key] = cur
            out[o["id"]] = dv
    return out

def facts():
    """section-7 verified facts the packs' caches lack (kind c, from the old `pack cache-back` selection)"""
    import pack, reference
    if not common.method_name() or not os.path.exists(reference.REF): return []
    cfg = common.project(); multi = common.option_packs(cfg) if cfg.get("options") else {}
    names = list(multi) if len(multi) > 1 else [None]; out = []
    for n in names: out += [r for r in pack.new_facts(n)[1] if re.match(r"^https?://", r["url"].strip())]   # public sources only: a lead statement stays in the engagement
    return out

# ------------------------------------------------------------------ own methods
CACHE = {"__pycache__", ".pytest_cache", ".mypy_cache", ".cache", "node_modules"}
def own_methods():
    """{name: dir} of the engagement's own methods (folders inside the engagement)"""
    eng = os.path.realpath(PROJECT_DIR) + os.sep
    return {n: e["dir"] for n, e in common.method_index(PROJECT_DIR).items() if e["source"] == "engagement" and os.path.realpath(e["dir"]).startswith(eng)}

def method_choice(a):
    """--with-method [<name>,...] -> those own methods (without names: the ones the exported runs used); --without-method -> []; no flag ->
    None (undecided)"""
    own = own_methods()
    if "--without-method" in a: return []
    if "--with-method" not in a: return None if own else []
    i = a.index("--with-method")
    if i + 1 < len(a) and not a[i + 1].startswith("--"): names = [n for n in a[i + 1].split(",") if n]
    else:
        names = sorted({read_json(os.path.join(rd, "run.json"), {}).get("method") for rd in all_runs()} & set(own))
        if not names: sys.exit(f"--with-method: no run of this engagement used an own method; name the one(s) to send: --with-method <name>[,<name>] (own methods: {', '.join(sorted(own)) or 'none'})")
    bad = [n for n in names if n not in own]
    if bad: sys.exit(f"--with-method: {', '.join(bad)} is not an own method of this engagement (own methods: {', '.join(sorted(own)) or 'none'})")
    return names

def card_summary(c):
    """the method card in a few numbers and words (README, inbox): no example rows, no client material beyond the card's own texts"""
    def lst(x): return x if isinstance(x, list) else []
    if not c: return {}
    r, u, ev = c.get("result") or {}, c.get("unit") or {}, c.get("evidence") or {}
    wbs = [w for w in lst(r.get("workbooks")) if isinstance(w, dict)]
    return {"display": c.get("display"), "description": str(c.get("description") or "")[:400], "origin": (c.get("origin") or {}).get("type"), "closest": (c.get("origin") or {}).get("closest"),
            "personas": lst(r.get("personas")), "unit": " / ".join(str(u.get(k)) for k in ("noun", "source", "dependencies") if u.get(k)), "workbooks": len(wbs),
            "sheets": sum(len(lst(w.get("sheets"))) for w in wbs), "topics": len(lst(c.get("topics"))), "standard_critics": [x.get("id") for x in lst(ev.get("standard_critics")) if isinstance(x, dict)],
            "consolidations": len(lst(c.get("consolidations"))), "postponed": len(lst(c.get("postponed"))), "storage": c.get("storage"), "confirmed": bool(c.get("confirmed"))}

def method_package(name, d, an):
    """an own method's folder for the export: every text file anonymised in the path-safe form (the method still runs at the maintainer),
    caches left out; a binary file cannot be anonymised and stays in the engagement -> (meta, {arcname: bytes})"""
    import handover
    sn = an(name, True); base = f"method/{sn}"; files, left = {}, []
    for dp, dns, fs in os.walk(d):
        dns[:] = sorted(x for x in dns if x not in CACHE and not x.startswith("."))
        for f in sorted(fs):
            if f.startswith(".") or f.endswith((".pyc", ".pyo")) or (dp == d and f == "guard-confirmed.json"): continue   # the user's guard confirmation belongs to this engagement
            rel = relp(os.path.join(dp, f), d).replace(os.sep, "/"); b = open(os.path.join(dp, f), "rb").read()
            try: t = None if b"\0" in b else b.decode("utf-8")
            except UnicodeDecodeError: t = None
            if t is None: left.append(an(rel, True)); continue
            files[f"{base}/{an(rel, True)}"] = an(t, True).encode()
    mj = read_json(os.path.join(d, "method.json"), {}); card = read_json(os.path.join(d, "method-card.json"), {})
    pv = handover.method_provenance({}, dict(mj, _dir=d, _source="engagement"))
    used = [run_slug(rd) for rd in all_runs() if read_json(os.path.join(rd, "run.json"), {}).get("method") == name]
    return {"name": sn, "dir": base, "display": mj.get("display") or card.get("display"), "version": mj.get("version"), "engine": mj.get("engine"),
            "origin": pv.get("method_origin") or "custom", "derived_from": pv.get("derived_from"), "installed_from": pv.get("method_installed_from"),
            "library_version": pv.get("method_library_version"), "card": card_summary(card), "runs": used,
            "files": len(files), "left_out": left}, files

def method_lines(mt):
    c = mt.get("card") or {}; df = mt.get("derived_from")
    head = (f"- `{mt['name']}` ({mt.get('display') or '-'}): version {mt.get('version') or '-'}, engine {mt.get('engine') or '-'}, origin {mt['origin']}"
            + (f" (closest plugin method {c['closest']})" if c.get("closest") else "") + (f", derived from {json.dumps(df, ensure_ascii=False)}" if df else "")
            + (f", installed from the {mt['installed_from']} {mt.get('library_version') or ''}".rstrip() if mt.get("installed_from") else "")
            + f"; runs {', '.join(mt['runs']) or 'none yet'}; package `{mt['dir']}/` ({mt['files']} files" + (f"; left out, binary: {', '.join(mt['left_out'])}" if mt["left_out"] else "") + ")")
    if not c: return [head, "  - no method-card.json in the folder"]
    return [head, f"  - card: {c['workbooks']} workbook(s), {c['sheets']} sheet(s), {c['topics']} topic(s), standard critics {', '.join(map(str, c['standard_critics'])) or '-'}, "
                  f"{c['consolidations']} consolidation(s); unit {c['unit'] or '-'}; personas {', '.join(map(str, c['personas'])) or '-'}; {c['postponed']} postponed; "
                  f"storage {c.get('storage') or '-'}; {'confirmed' if c['confirmed'] else 'NOT confirmed'}", f"  - {c['description']}"]

def all_runs(): return sorted(set(runs()) | {os.path.dirname(f) for f in glob.glob(os.path.join(PROJECT_DIR, "runs", "*", "run.json"))} | ({RUN} if os.path.exists(P("run.json")) else set()))

def build(an, with_methods=()):
    """-> (EXPORT.json dict, {arcname: bytes}, [missing package ids])"""
    ls, files, missing = [], {}, []
    for rd in runs():
        slug = run_slug(rd)
        for e in learnings(rd):
            q = f"{slug}/{e['id']}"; x = {"id": q, "section": e["section"], "title": e["title"], "verdict": e["verdict"], "fields": e["fields"]}
            pf = os.path.join(stage_dir(rd, e["id"]), "repro.json")
            if e["verdict"] in ("upstream", "unresolved"):
                if not os.path.exists(pf): missing.append(q)
                else:
                    pk = read_json(pf); x["repro"] = {k: v for k, v in pk.items() if k not in ("observed", "fixture_run", "command", "expected", "files")}
                    if pk["kind"] == "tool":
                        base = f"repro/{an(slug, True)}/{e['id']}"
                        x["repro"].update({"dir": base, "files": an.deep(pk["files"], True), "cwd": an(pk["cwd"], True), "command": an(pk["command"], True),
                                           "expected": an(pk["expected"], True), "observed": an(pk["observed"], True), "fixture_run": an.deep(pk.get("fixture_run"), True)})
                        fx = os.path.join(os.path.dirname(pf), "fixture")
                        for dp, _, fs in os.walk(fx):
                            for f in fs:
                                rel = relp(os.path.join(dp, f), fx).replace(os.sep, "/")
                                files[f"{base}/fixture/{an(rel, True)}"] = an(open(os.path.join(dp, f), encoding="utf-8", errors="replace").read(), True).encode()
            ls.append(x)
    ovs = read_json(PP("overrides", "OVERRIDES.json"), {"overrides": []})["overrides"]; dv = plugin_defaults([o for o in ovs if not o.get("removed")])
    ox = [dict({k: o.get(k) for k in ("id", "target", "keys", "set", "text", "why", "plugin_version", "plugin_commit", "date", "removed", "method") if o.get(k) not in (None, "")},
               learning=(f"{os.path.basename(o['run']) or 'run'}/{o['learning']}" if o.get("learning") and o.get("run") else o.get("learning", "")),
               plugin_default=dv.get(o["id"], "(removed)")) for o in ovs]
    ex = {"format": 1, "export_id": f"LX-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}", "date": time.strftime("%Y-%m-%d"),
          "plugin": {"version": package_version(), "commit": package_commit()}, "runs": [run_meta(rd) for rd in all_runs()],
          "learnings": ls, "overrides": ox, "facts": facts(), "methods": [],
          "anonymisation": "client-side names are placeholders (<client>, <ext-1> ...; anon-<name> inside tool-defect fixtures); the mapping stayed with the sender"}
    own = own_methods()
    for n in with_methods:
        mt, mf = method_package(n, own[n], an); ex["methods"].append(mt); files.update(mf)
    for k in ("learnings", "overrides", "facts", "runs", "methods"): ex[k] = an.deep(ex[k])   # a tool package's fields are in the anon- form already: no-op there
    files["README.md"] = readme(ex).encode(); files["EXPORT.json"] = json.dumps(ex, indent=1, ensure_ascii=False).encode()
    return ex, files, missing

def readme(ex):
    L = [f"# dbcx learnings export {ex['export_id']}", "", f"Plugin {ex['plugin']['version']} {ex['plugin']['commit'] or '(dev checkout)'}, exported {ex['date']}. {ex['anonymisation']}.", ""]
    for r in ex["runs"]: L.append(f"- run `{r['run']}`: method {r['method']} ({r.get('method_source', '-')} {r.get('method_version', '-')}, origin {r.get('method_origin', '-')}{', from the library ' + str(r.get('method_library_version', '')) if r.get('method_installed_from') else ''}), profile {r['profile']}, language {r['language']}, knowledge {', '.join(f'{k}={v}' for k, v in r['knowledge'].items()) or '-'}")
    if ex.get("methods"): L += ["", "## Own methods (sent along by the user)", ""] + [l for mt in ex["methods"] for l in method_lines(mt)]
    rl = [l for r in ex["runs"] for l in metrics_lines(r)]
    if rl: L += ["", "## Retrieval metrics (numbers only)", ""] + rl
    L += ["", "## Learnings", ""]
    for x in ex["learnings"]:
        f = x["fields"]; L.append(f"### {x['id']} [{x['section']}] {x['title']} - {x['verdict']}")
        L += [f"- {k}: {v}" for k, v in f.items()]
        r = x.get("repro")
        if r:
            L.append(f"- reproduction ({r['label']}{', observational' if r.get('observational') else ''}):" + (f" {r['note']}" if r.get("note") else ""))
            if r["kind"] == "tool": L += [f"  - fixture `{r['dir']}/fixture/` ({', '.join(z['path'] for z in r['files']) or 'run.json only'}), run in `{r['cwd']}`: `{r['command']}`", f"  - expected: {r['expected']}", "  - observed:", "```", r["observed"].rstrip(), "```"]
            elif r["kind"] == "agent": L += [f"  - caught by: {r['caught']}", f"  - brief {r['brief']['file']} lines {r['brief']['lines']}:", "```", r["brief"]["text"].rstrip(), "```", f"  - output {r['output']['file']} lines {r['output']['lines']}:", "```", r["output"]["text"].rstrip(), "```"]
            elif r["kind"] == "fact": L.append(f"  - {r['fact']} (applies to {r['applies']}; {r['url']}, {r['date']})")
            else: L.append(f"  - ask the sender: {r['ask']}")
        L.append("")
    L += ["## Engagement overrides", ""] + [f"- {o['id']} {o['target']} {', '.join(o.get('keys') or [])}: {json.dumps(o.get('set'), ensure_ascii=False) if o.get('set') else (o.get('text') or '').strip()[:400]} - plugin default {json.dumps(o['plugin_default'], ensure_ascii=False)} - why: {o.get('why', '')}" + (f" - from {o['learning']}" if o.get("learning") else "") + (" - REMOVED" if o.get("removed") else "") for o in ex["overrides"]]
    L += ["", "## Verified reference facts the knowledge packs lack", ""] + [f"- [{x['pack']}] {x['fact']} (applies to {x['applies']}; {x['url']}, {x['date']}; {x['id']})" for x in ex["facts"]] + (["- none"] if not ex["facts"] else [])
    return "\n".join(L) + "\n"

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*[A-Za-z0-9]")
def toks(s): return {t for t in TOKEN.findall(s) if len(t) >= 3}
def residual(texts, an):
    """terms in the export that look client-side but are not mapped: a word of the client label, a file/folder name of the client's
    repository (any spelling), or a capitalised word / identifier of the client's corpus - minus the plugin's own vocabulary (an
    own method's words count as known only where the client's material lacks them; the preview labels the others)"""
    vocab = set()
    for dp, dns, fs in os.walk(PLUGIN):
        dns[:] = [x for x in dns if x not in (".git", "tests", "__pycache__")]   # tests and the inbox carry maintainer / client material
        for f in fs:
            if f.endswith((".md", ".py", ".json", ".sh", ".txt")) and f != "LEARNINGS-INBOX.md":
                try: vocab |= {t.lower() for t in toks(open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read())}
                except OSError: pass
    label = {w.lower() for t in label_terms() for w in re.findall(r"[A-Za-z0-9]{3,}", t)} - vocab
    corpus, repo = set(), set()
    for f in glob.glob(os.path.join(CORPUS_DIR, "text", "*.md")): corpus |= {t.lower() for t in toks(open(f, encoding="utf-8", errors="ignore").read())}
    if common.method_name():
        n = 0
        for eb in common.evidence_bases():
            if eb.get("kind") not in ("repository", "client-repo"): continue
            for root in eb["abs_roots"]:
                for dp, dns, fs in os.walk(root):
                    dns[:] = [x for x in dns if not x.startswith(".")]; n += len(fs)
                    repo |= {t.lower() for x in dns + fs for t in toks(os.path.splitext(x)[0])}
                    if n > 200000: break
    mapped = an.terms(); hits = {}
    for name, s in texts:
        for t in toks(s):
            if t.startswith("anon-"): continue
            shaped = t[0].isupper() or re.search(r"[_.\d]|[a-z][A-Z]", t)
            for p in {t.lower()} | {p.lower() for p in re.split(r"[_.-]", t) if len(p) >= 3}:
                if p in vocab or any(m in p for m in mapped): continue
                if p in label or p in repo or (shaped and p in corpus): hits.setdefault(t, set()).add(name); break
    return {t: sorted(v) for t, v in sorted(hits.items())}

def export(a):
    an = Anon(); choice = method_choice(a); ex, files, missing = build(an, choice or ())
    undecided = f"this engagement has own method(s) {', '.join(sorted(own_methods()))}: ask the user whether they go along, then add --with-method [<name>,...] or --without-method" if choice is None else ""
    if "--preview" in a:
        print(files["README.md"].decode())
        print("## Files in the export\n"); [print(f"- {n} ({len(b)} bytes)") for n, b in sorted(files.items())]
        for n, b in sorted(files.items()):
            if "/fixture/" in n or re.match(r"^method/[^/]+/(METHOD-CARD\.md|method-card\.json)$", n): print(f"\n--- {n}\n{b.decode(errors='replace')}")
        if missing: print(f"\nMISSING reproduction package for {len(missing)} upstream/unresolved learning(s): {', '.join(missing)} - `{CLI} learn repro <L-id> --kind ...` in that run (export refuses until each has one)")
        if undecided: print(f"\nOWN METHOD: {undecided} (export refuses until then)")
        rr = residual([(n, b.decode(errors="replace")) for n, b in files.items()], an)
        mv = {t for n, b in files.items() if n.startswith("method/") for t in toks(b.decode(errors="replace"))}
        print("\n## Residual risk (not mapped, but found in the client's corpus / repository)\n")
        for t, where in rr.items(): print(f"- {t}   ({', '.join(where[:3])})" + ("   - appears in your client material and in your method" if t in mv else ""))
        print(f"{len(rr)} term(s) - map each with `{CLI} learn anonymise add <term> [--as <kind>]` or confirm it is harmless" if rr else "none found")
        return
    if undecided: sys.exit(f"REFUSED: {undecided}")
    if missing: sys.exit(f"REFUSED: no reproduction package for {', '.join(missing)} - `{CLI} learn repro <L-id> --kind tool|agent|fact|none ...` in that run first (`{CLI} learn export --preview` shows the state)")
    out = os.path.abspath(a[a.index("--out") + 1]) if "--out" in a else os.path.join(EXPORTS, ex["export_id"] + ".zip")
    if os.path.realpath(out).startswith(os.path.realpath(PLUGIN) + os.sep): sys.exit("REFUSED: the export never goes into the plugin folder (it is read-only when installed)")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in sorted(files.items()): z.writestr(f"{ex['export_id']}/{n}", b)
    n_up = sum(1 for x in ex["learnings"] if x["verdict"] in ("upstream", "unresolved"))
    print(f"{out}\n{ex['export_id']}: {len(ex['learnings'])} learning(s) ({n_up} upstream/unresolved with a reproduction package), {len(ex['overrides'])} override(s), {len(ex['facts'])} reference fact(s), {len(ex['methods'])} own method(s); send this file to the plugin maintainer")

# ------------------------------------------------------------------ import (maintainer, plugin checkout)
CAND_README = """# Candidate {qid} ({export_id})

{title}

Tool-defect reproduction from a colleague's engagement (anonymised: anon-<name> stands for a client-side name).
- expected: {expected}
- run: `cd fixture/{cwd} && {command}` (the plugin's launcher on PATH)
- observed output at the sender: observed.txt; output of the sender's standalone check: fixture-run.txt

Turn it into a failing test: copy fixture/ into a tempfile.TemporaryDirectory in a test of the plugin (or fold the
files into the method's fixtures/make_fixture.py), run the command there, assert the EXPECTED behaviour and watch it fail with the observed
output; then fix the tool. Delete this folder once the test exists (or the learning was rejected in the inbox).
"""

METHOD_README = """# Own method {name} ({export_id})

A colleague's own method, sent along with the learnings export (anonymised in the path-safe form: anon-<name> stands for a client-side name).
- display: {display}; version {version}, written for engine {engine}; origin {origin}{closest}{derived}
- used in the sender's run(s): {runs}; files: method.json, kinds, deliverables, briefs ... with method-card.json / METHOD-CARD.md{left}
- card: {card}

Promote an own method: turn it into a plugin method, or leave it. Delete this folder once it became a plugin method or was rejected in the inbox.
"""

def import_(a):
    src = a[0] if a and not a[0].startswith("--") else sys.exit("dbcx learn import <export-file>")
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=os.getcwd(), capture_output=True, text=True)
    top = r.stdout.strip() if r.returncode == 0 else ""
    if not top or not os.path.exists(os.path.join(top, "engine", "tools", "learn.py")): sys.exit("REFUSED: dbcx learn import runs in a git checkout of the plugin (the maintainer's clone), not in an installed copy or a project")
    with zipfile.ZipFile(src) as z:
        names = z.namelist(); root = names[0].split("/", 1)[0]; ex = json.loads(z.read(f"{root}/EXPORT.json"))
        inbox = os.path.join(top, "docs", "LEARNINGS-INBOX.md"); marker = f"<!-- imported {ex['export_id']} -->"
        cur = open(inbox, encoding="utf-8").read() if os.path.exists(inbox) else "# Learnings inbox (plugin refinement backlog)\n\nOne block per imported export (`dbcx learn import`). Work through it; delete a block once its entries became plugin changes or were rejected with a note.\n"
        if marker in cur: sys.exit(f"{ex['export_id']} was imported already")
        cand = os.path.join(top, "tests", "candidates", ex["export_id"]); n_c = 0
        order = {"upstream": 0, "unresolved": 1}; up = sorted([x for x in ex["learnings"] if x["verdict"] in order], key=lambda x: order[x["verdict"]])
        B = [f"## Export `{ex['export_id']}` (plugin {ex['plugin']['version']} {ex['plugin']['commit'] or 'dev'}; methods {', '.join(sorted({r['method'] for r in ex['runs'] if r['method']}))}; exported {ex['date']}, imported {time.strftime('%Y-%m-%d')}) {marker}", ""]
        B += [f"Runs: " + "; ".join(f"`{r['run']}` {r['method']} ({r.get('method_source', '-')} {r.get('method_version', '-')}, origin {r.get('method_origin', '-')}) / {r['profile']} / {r['language']} / {', '.join(f'{k}={v}' for k, v in r['knowledge'].items())}" for r in ex["runs"]), "", "### Upstream and unresolved learnings", ""]
        for x in up:
            B.append(f"#### {x['id']} [{x['section']}] {x['title']} ({x['verdict']}, {x['fields'].get('confidence', 'hypothesis')})")
            B += [f"- {k}: {v}" for k, v in x["fields"].items() if k not in ("confidence",)]
            rp = x.get("repro") or {}
            if rp.get("kind") == "tool":
                d = os.path.join(cand, *x["id"].split("/")); os.makedirs(d, exist_ok=True); n_c += 1
                pre = f"{root}/{rp['dir']}/fixture/"
                for n in names:
                    if n.startswith(pre) and not n.endswith("/"):
                        t = os.path.join(d, "fixture", *n[len(pre):].split("/")); os.makedirs(os.path.dirname(t), exist_ok=True); open(t, "wb").write(z.read(n))
                open(os.path.join(d, "observed.txt"), "w", encoding="utf-8").write(rp["observed"]); open(os.path.join(d, "fixture-run.txt"), "w", encoding="utf-8").write(json.dumps(rp.get("fixture_run"), indent=1))
                open(os.path.join(d, "README.md"), "w", encoding="utf-8").write(CAND_README.format(qid=x["id"], export_id=ex["export_id"], title=x["title"], **{k: rp[k] for k in ("expected", "cwd", "command")}))
                B.append(f"- reproduction (tool defect): `{relp(d, top)}/` - `{rp['command']}`; expected: {rp['expected']}")
            elif rp.get("kind") == "agent": B += [f"- reproduction (agent behaviour, observational): caught by {rp['caught']}; brief {rp['brief']['file']} {rp['brief']['lines']}, output {rp['output']['file']} {rp['output']['lines']} (full excerpts in the export README)"]
            elif rp.get("kind") == "fact": B.append(f"- reproduction (knowledge fact): {rp['fact']} (applies to {rp['applies']}; {rp['url']}, {rp['date']})")
            elif rp: B.append(f"- NOT reproducible standalone - ask the sender: {rp['ask']}")
            B.append("")
        n_m = 0
        if ex.get("methods"): B += ["### Own methods (candidates for a plugin method)", ""]
        for mt in ex.get("methods") or []:
            d = os.path.join(cand, "method", mt["name"]); pre = f"{root}/{mt['dir']}/"; n_m += 1
            for n in names:
                if n.startswith(pre) and not n.endswith("/"):
                    t = os.path.join(d, *n[len(pre):].split("/")); os.makedirs(os.path.dirname(t), exist_ok=True); open(t, "wb").write(z.read(n))
            c = mt.get("card") or {}; df = mt.get("derived_from")
            rd = os.path.join(d, "README-candidate.md" if os.path.exists(os.path.join(d, "README.md")) else "README.md")
            open(rd, "w", encoding="utf-8").write(METHOD_README.format(name=mt["name"], export_id=ex["export_id"], display=mt.get("display") or "-", version=mt.get("version") or "-", engine=mt.get("engine") or "-",
                origin=mt["origin"], closest=f", closest plugin method {c['closest']}" if c.get("closest") else "", derived=f", derived from {json.dumps(df, ensure_ascii=False)}" if df else "",
                runs=", ".join(mt["runs"]) or "none yet", left=f"; left out at the sender (binary): {', '.join(mt['left_out'])}" if mt["left_out"] else "",
                card="\n  ".join(method_lines(mt)[1:])))
            B += method_lines(mt) + [f"  - unpacked: `{relp(d, top)}/`", ""]
        ml = [l for r in ex["runs"] for l in metrics_lines(r)]
        if ml: B += ["### Retrieval metrics", ""] + ml + [""]
        B += ["### Engagement overrides (candidates for a new default)", ""] + [f"- {o['id']} {o['target']} {', '.join(o.get('keys') or [])} = {json.dumps(o.get('set'), ensure_ascii=False) if o.get('set') else (o.get('text') or '').strip()[:300]} (plugin default {json.dumps(o['plugin_default'], ensure_ascii=False)}; plugin {o.get('plugin_version')}) - {o.get('why', '')}" + (f" - from {o['learning']}" if o.get("learning") else "") for o in ex["overrides"] if not o.get("removed")]
        B += ["", "### Verified reference facts (candidate reference-cache rows)", ""] + [f"- [{f['pack']}] {f['fact']} | {f['applies']} | {f['url']} | {f['date']} | {f['id']}" for f in ex["facts"]] + (["- none"] if not ex["facts"] else [])
        B += ["", "### Resolved at the sender (context only)", ""] + [f"- {x['id']} [{x['section']}] {x['title']} - {x['verdict']}: {x['fields'].get('status', '')}" for x in ex["learnings"] if x["verdict"] not in order]
    os.makedirs(os.path.dirname(inbox), exist_ok=True); open(inbox, "w", encoding="utf-8").write(cur.rstrip("\n") + "\n\n" + "\n".join(B).rstrip("\n") + "\n")
    print(f"{ex['export_id']}: {len(up)} upstream/unresolved learning(s), {sum(1 for o in ex['overrides'] if not o.get('removed'))} override(s), {len(ex['facts'])} fact(s) -> {relp(inbox, top)}; {n_c} tool-defect candidate(s), {n_m} own method(s) in {relp(cand, top)}/")

def main(a):
    cmd, rest = (a[0], a[1:]) if a else ("", [])
    if any(x in rest for x in ("--help", "-h")): print(__doc__); return
    if cmd == "export": export(rest)
    elif cmd == "repro": repro(rest)
    elif cmd == "anonymise": anonymise_cmd(rest)
    elif cmd == "import": import_(rest)
    else: print(__doc__)

if __name__ == "__main__":
    main(sys.argv[1:])
