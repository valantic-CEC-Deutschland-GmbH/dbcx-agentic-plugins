#!/usr/bin/env python3
"""Render run documents, context blocks and complete agent briefs from the merged configuration, the method pack and the knowledge packs.

Usage:
  dbcx render instructions [--force]           <run>/CLAUDE.md
  dbcx render engagement-instructions [--force] <project>/CLAUDE.md
  dbcx render claude [--force]                  <run>/CLAUDE.md (compatibility command)
  dbcx render plan [--force]                   <run>/docs/PLAN.md from methods/<m>/plan.md
  dbcx render reference [--force]              <project>/reference/platform-standard.md from the knowledge packs' research seeds + caches
  dbcx render handover [--force]               the inventory handover (method.inventory.handover): passed inventory claims per scope + cross-cutting
  dbcx render digest <consolidation>           analysis/consolidated/digest-<X>.md: the rows of ALL final scope analyses a consolidator needs, with citing claim ids
                                               (split none, profile lean: the passed inventory's tables and claims + the corpus index instead)
  dbcx render context <role> ...               context block only (debug): analyst <scope> [--round n] | inventory | consolidate <X> | critic <client|standard> <scope> <round> | gate <persona> <round> | verifier <round> | editor <round>
  dbcx render brief <kind> ... --out [path] [--addendum <file>|--no-addendum]
        kinds: analyst <scope> [--round n | --conflicts] (alias unit) | inventory | consolidate <X> | critic <client|standard> <scope> <round> | gate <persona> <round> | verifier <round> | editor <round> | postpass <scope> | progress | research
        writes analysis/briefs/<agent>[-rN].md and prints path, MODEL and agent name; the spawn prompt references the PATH (the Agent hook checks it).
        analyst <scope> --conflicts: the short continuation brief with the CONFLICTS TO RESOLVE block (`dbcx conflicts route`) -> analysis/briefs/<agent>-conflicts.md;
        every consolidate brief carries the CONFLICTS block of analysis/consolidated/CONFLICTS.json when the register holds a conflict.
        Rounds > 1 of analyst / inventory / consolidate / critic need --addendum <file> (an addendum that lives only in a prompt does not survive the session) or --no-addendum.
        A critic brief refuses without a claims-round<n> snapshot newer than the analysis. Gate and verifier briefs refuse while the customer edition fails
        `lint_deliverable --standalone` (G2; --force + `dbcx status assume`), take the round's workbook snapshot, and from round 2 carry the persona's own previous
        issues and the tool diff (`dbcx gate diff`) - an --addendum is optional there. The verifier brief draws its row sample (`dbcx gate sample`).
  dbcx render snippets                         merged snippets (debug)
A brief = CONTEXT rows (generic + method rows + evidence bases for the role) + METHOD NOTES (snippets) + engine role text (engine/briefs/<role>.md)
+ method role text (methods/<m>/briefs/<role>.md, optional <role>-<scope>.md) + generic blocks (handover, routed questions, lead hints / facts, knowledge base, resume note, rework steps, addendum)
+ "Follow your agent definition." Header fields are never retyped by hand - render again instead.
PROJECT NOTES: overrides/briefs/<role>.md of the engagement and then of the run (<role> = the role text's name: analyst, inventory,
consolidate, critic-client, critic-standard, gate, verifier, editor, postpass, progress, research or a method's extra kind text) follow the
role text as one labelled block, both concatenated; they only add text. They are part of the brief's sha256; the .meta.json lists each note's path and sha256.
"""
import json, os, sys, glob, re, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import override_files, RUN, PROJECT_DIR, PLUGIN, ENGINE, TOOLS, STATUS_PATH, WAVES_PATH, SCOPES_PATH, REQ_PATH, REF_DIR, project, method, spec, snippets, fmt, cli_text, load_json, read_json, P, PP, evidence_bases, role_may_read, scope_info, scope_critics, all_critics, is_consolidated, load_method_module, packs_of, extra_option_packs, pack_snippets, option_packs, critic_role, critic_pack, scope_pack, CLI, AGENT_PREFIX, relp, declared_critic, pack as knowledge_pack
from runtime import resolve_model
import kb

def write(rel, text, force):
    p = rel if os.path.isabs(rel) else P(rel)
    if os.path.exists(p) and not force: print(f"kept {relp(p, RUN)} (use --force to overwrite)"); return
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(text.replace(CLI, "dbcx")); print(f"wrote {relp(p, RUN)}")   # run/engagement files travel with the folder: no machine path (the skill and the SessionStart hook name the launcher)

def block(title, rows):
    out = [f"## {title}"]
    for k, v in rows:
        if v in (None, "", [], {}): continue
        out.append(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
    return "\n".join(out)

def S(cfg, key): return resolve_model(cfg, key)
def M(cfg, key, default=None): return S(cfg, key).model
def model_rows(cfg, key):
    selected = S(cfg, key)
    return [("MODEL", selected.model), ("MODEL PROFILE", selected.profile), ("PROVIDER", selected.provider), ("HARNESS", selected.harness), ("REASONING EFFORT", selected.reasoning_effort)]
def helper_rows(cfg):
    selected = S(cfg, "helper")
    return [("HELPER MODEL", selected.model), ("HELPER MODEL PROFILE", selected.profile), ("HELPER REASONING EFFORT", selected.reasoning_effort)]
def MET(cfg): return cfg["_method"]
def rel_ref(): return relp(os.path.join(REF_DIR, "platform-standard.md"), RUN)

def method_notes(cfg, role_key, scope=None, pack=None):
    """the notes_keys snippets of a role. pack = one technology pack (a per-pack standard critic reads only its own pack's notes);
    otherwise every further option pack of the run adds its own block (a second technology is no knowledge slot, so the merged
    snippets never carry it)"""
    b = MET(cfg).get("briefs", {}); keys = b.get("notes_keys", {})
    ks = keys.get(f"{role_key}:{scope}") if scope else None
    ks = ks or keys.get(role_key) or []
    title = b.get("notes_title", "METHOD NOTES (from the method and knowledge packs)"); out = []
    for sn, t in ([(pack_snippets(cfg, pack), f"{title} - {pack.get('display', pack['name'])}")] if pack else
                  [(snippets(cfg), title)] + [(pack_snippets(cfg, pk), f"{title} - {pk.get('display', pk['name'])}") for pk in extra_option_packs(cfg)]):
        rows = [r for r in ((k.replace("_", " ").upper(), sn.get(k, "")) for k in ks) if r[1]]
        if rows: out.append(block(t, rows))
    return "\n\n".join(out)

def evidence_rows(cfg, role, agent=None):
    ebs = evidence_bases(cfg); may = [e for e in ebs if role_may_read(role, e, agent, MET(cfg))]; no = [e for e in ebs if not role_may_read(role, e, agent, MET(cfg))]
    def one(e): return f"{e['id']} [{e.get('kind')}] " + (", ".join(relp(r, RUN) if os.path.isabs(r) else r for r in e.get("abs_roots", [])) or ", ".join(e.get("domains", [])) or "-") + (f" - {e['note']}" if e.get("note") else "")
    return [("EVIDENCE BASES YOU MAY READ", "; ".join(one(e) for e in may)), ("NO ACCESS (hook-enforced; route questions to the orchestrator)", "; ".join(e["id"] for e in no))]

def brief_flags(cfg):
    """the method's brief flags (optional hook briefing.flags(cfg) -> names, e.g. tech-fit-estimation's system_mode): they select the
    conditional blocks of a method role text and the `when` of a briefs.rows entry; a method without the hook has none"""
    mod = load_method_module("briefing")
    return set((mod.flags(cfg) if mod and hasattr(mod, "flags") else None) or ())

def holds(when, flags):
    """`flag` or `!flag` (several joined by ' & ') against the method's brief flags"""
    return all((w[1:].strip() not in flags) if w.startswith("!") else (w in flags) for w in (x.strip() for x in str(when).split("&")) if w)

COND = re.compile(r"^<!-- (when (.+?)|else|end) -->$")
def conditional(text, flags):
    """a method role text's conditional blocks: lines `<!-- when <flag | !flag> -->` ... [`<!-- else -->` ...] `<!-- end -->` (one level). The
    marker lines go, the branch that does not hold goes with them; a text without markers is returned unchanged (byte for byte)"""
    if "<!-- when " not in text: return text
    out, keep = [], None
    for line in text.split("\n"):
        m = COND.match(line.strip())
        if not m: (out.append(line) if keep is not False else None); continue
        if m.group(1).startswith("when "): keep = holds(m.group(2), flags)
        elif m.group(1) == "else": keep = (not keep) if keep is not None else None
        else: keep = None
    return "\n".join(out)

def common_rows(cfg, role, agent=None):
    rows = []; flags = None
    for x in MET(cfg).get("briefs", {}).get("rows", []):
        label, tpl = x[0], x[1]
        if len(x) > 2:   # [label, template, when]: a row for some runs only (e.g. OPTIONS without run.json systems)
            flags = brief_flags(cfg) if flags is None else flags
            if not holds(x[2], flags): continue
        v = fmt(tpl, cfg)
        if "{" not in v and v.strip(" /()"): rows.append((label, v))
    rows += [("CLIENT", f"{cfg['engagement'].get('client', '')} - {cfg['engagement'].get('client_context', '')}".strip(" -"))]
    er = cfg["engagement"].get("rules") or []   # engagement.json / run.json -> engagement.rules: client-specific rules every role must apply (source weighting, scope exclusions, naming)
    if er: rows.append(("ENGAGEMENT RULES (binding for every source and claim)", " ".join(f"({i}) {r}" for i, r in enumerate(er if isinstance(er, list) else [er], 1))))
    rows += [("DELIVERABLE LANGUAGE", cfg["languages"]["deliverable"]), ("RUN", ".")]
    if PROJECT_DIR != RUN: rows.append(("PROJECT (shared input/, corpus/, reference/, handover/)", relp(PROJECT_DIR, RUN)))
    rows.append(("TOOLS", f"{CLI} <tool> (portable package launcher; a bare dbcx command in your agent definition means this one)"))
    rows += evidence_rows(cfg, role, agent)
    return rows

PRECISION_ROLES = ("analyst", "inventory", "consolidate", "critic-client")
def role_text(cfg, role, scope=None):
    """engine role text + method role text; the generic PRECISION CHECKLIST (engine/briefs/precision.md, A2) follows the engine
    text of every role that writes or scores client-evidence claims. A profile other than full reads `<name>.<profile>.md`
    before `<name>.md` where one exists (the lean consolidator reads the corpus)"""
    parts = []; pr = cfg.get("_profile") or "full"
    def names(n): return ([f"{n}.{pr}.md"] if pr != "full" else []) + [f"{n}.md"]
    for base in (os.path.join(ENGINE, "briefs"), os.path.join(MET(cfg)["_dir"], "briefs")):
        for name in (names(f"{role}-{scope}") if scope else []) + names(role):
            p = os.path.join(base, name)
            if os.path.exists(p):
                t = open(p, encoding="utf-8").read()
                parts.append(fmt((conditional(t, brief_flags(cfg)) if "<!-- when " in t else t).strip(), cfg)); break   # conditional blocks only where the text has them
        if base == os.path.join(ENGINE, "briefs") and role in PRECISION_ROLES and os.path.exists(os.path.join(base, "precision.md")):
            parts.append(fmt(open(os.path.join(base, "precision.md"), encoding="utf-8").read().strip(), cfg))
    parts.append(project_notes(role))
    return "\n\n".join(x for x in parts if x)

NOTES_USED = []   # the note files the rendered brief carries (-> .meta.json)
def project_notes(role):
    """the engagement's and the run's overrides/briefs/<role>.md as one labelled block after the fixed role text; never formatted
    (a note is the user's text), never a replacement of the instructions above"""
    fs = [f for f in override_files(os.path.join("briefs", f"{role}.md")) if os.path.exists(f)]
    if not fs: return ""
    body = []
    for f in fs:
        txt = open(f, encoding="utf-8").read().strip(); NOTES_USED.append({"path": relp(f, RUN), "sha256": hashlib.sha256(txt.encode()).hexdigest()})
        body.append(f"Source: `{relp(f, RUN)}`\n\n{txt}")
    return (f"## PROJECT NOTES (engagement-specific additions for the role {role}, written with `{CLI} override`; they add to the instructions above "
            "and never replace them or your agent definition - where a note contradicts a rule above, the rule wins and you name the conflict in your report)\n\n" + "\n\n".join(body))

def extra(cfg, role, scope, rnd):
    mod = load_method_module("briefing")
    if mod and hasattr(mod, "extra"):
        r = mod.extra(role, scope, cfg, rnd) or {}; return r.get("rows", []), r.get("blocks", [])
    return [], []

def quote_rows(cfg):
    """the `quote` column rule for the roles that write claims - no row while claims.quotes is off"""
    import evidence; m = evidence.quotes_mode(cfg)
    if m == "off": return []
    rule = "optional column `quote`: " if m == "warn" else "EVERY claim fills the column `quote`: "
    rule += "one verbatim excerpt (>= 20 characters, original language, fragments of one locator joined by ' […] ') from a cited locator that carries the statement - copied, never paraphrased or translated; the evidence cell stays locator-only. "
    rule += "`dbcx evidence quotes <scope> --offline` (after the CHECK) looks it up word for word; the critics see the result (verified / partial / not_found)" + (" - a fact claim whose quote is not found is a blocking defect, a claim without a quote counts as imprecise" if m == "required" else "")
    return [(f"QUOTES (claims.quotes = {m})", rule)]

def template_of(cfg, kind): SP, _ = spec(cfg); return f"templates/{SP[kind]['file']}" if kind in SP else "templates/<unknown kind>"

def wave_member(name):
    waves = load_json(WAVES_PATH, {"waves": [], "skipped": []})
    wave = next((w["wave"] for w in waves["waves"] if name in w.get("scopes", w.get("units", []))), None); mem = next((m for w in waves["waves"] for m in w["members"] if m["name"] == name), {})
    same = [x for x in next((w.get("scopes", w.get("units", [])) for w in waves["waves"] if name in w.get("scopes", w.get("units", []))), []) if x != name]
    return wave, mem, same, name in waves.get("skipped", [])
def is_light(name):
    _, mem, _, _ = wave_member(name); return bool(mem.get("light_pass"))

# ------------------------------------------------------------------ context blocks per role
def ctx_analyst(cfg, name, rnd):
    m = MET(cfg); sc = cfg["scoring"]; js, md, kind, role, agent = scope_info(name, m)
    wave, mem, same_wave, skipped = wave_member(name)
    if skipped: print(f"WARNING: {name} is in WAVES.json skipped (not analysed)", file=sys.stderr)
    sj = load_json(SCOPES_PATH, {"scopes": {}}); se = sj["scopes"].get(name, {})
    final = {os.path.basename(f)[:-3] for f in glob.glob(P(m["scopes"].get("output_dir", "analysis/scopes"), "*.md"))}
    deps = mem.get("depends_on") or se.get("depends_on") or []; fin = [d for d in deps if d in final]; running = [d for d in deps if d in same_wave]
    light = bool(mem.get("light_pass")) or name in cfg.get("models", {}).get("analyst_light_scopes", []); cap = sc.get("max_claims_light", 10) if light else sc.get("max_claims", 40)
    model_key = "analyst_light" if light else "analyst"
    rows = [("SCOPE", name), ("SCOPE KIND", kind), ("WAVE", wave), ("AGENT NAME", agent)] + model_rows(cfg, model_key) + helper_rows(cfg) + [("GROUP", se.get("group", "")), ("SIZE", se.get("size", ""))]
    rows += [(k, v) for k, v in (se.get("meta") or {}).items() if isinstance(v, (str, int)) and k.upper() == k]
    rows += common_rows(cfg, "analyst") + [("DEPENDS ON", deps), ("FINALIZED ANALYSES YOU MAY READ", [relp(scope_info(d, m)[1], RUN) for d in fin]), ("RUNNING IN THIS WAVE (ask via orchestrator)", running), ("DEPENDENTS", mem.get("required_by", []))]
    for k, v in (m.get("briefs", {}).get("analyst_inputs") or {}).items(): rows.append((k, fmt(v, cfg)))
    rows += [("REFERENCE", rel_ref()), ("TEMPLATE", template_of(cfg, kind)), ("OUTPUT", relp(md, RUN)), ("CHECK", f"{CLI} md_to_json {kind} {relp(md, RUN).replace(os.sep, '/')}"),
             ("ROUND", rnd if rnd else 0), ("FIX LIST", f"analysis/gauntlet/{name}/round{int(rnd) - 1}-issues.md" if rnd and int(rnd) > 0 else ""), ("LIGHT PASS", f"yes (<= {cap} claims, essentials only)" if light else "no"), ("CLAIM CAP", claim_cap_text(cfg, name, js, kind, cap))] + quote_rows(cfg)
    xr, xb = extra(cfg, "analyst", name, rnd)
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr), method_notes(cfg, "analyst", pack=scope_pack(name, cfg))] + xb if x)

def claim_cap_text(cfg, scope, js, kind, bound):
    """the cap follows the must-claim verdict rows (method.json claims.must_claim) + a reserve; the fixed cap is the upper bound"""
    sc = cfg["scoring"]; frz = f"register frozen after round {sc.get('freeze_register_after_round', 2)}: later rounds fix, never add"
    declared = any(k.split(".", 1)[0] == kind for k in ((MET(cfg).get("claims") or {}).get("must_claim") or {}) if not k.startswith("_"))
    if not declared: return f"{bound} ({frz})"
    reserve = sc.get("claim_cap_reserve", 5); data = load_json(js, None) if os.path.exists(js) else None
    if data:
        import rows; SP, _ = spec(cfg); res = rows.analyse(kind, data, SP, MET(cfg), scope, assign=False)
        return f"{rows.derived_cap(len(res['must_rows']), bound, sc)} = {len(res['must_rows'])} must-claim rows + reserve {reserve}, at most {bound}; {len(res['must_uncovered'])} must-claim cells still without a claim (the CHECK lists them) ({frz})"
    return f"must-claim rows + reserve {reserve}, at most {bound} - the CHECK prints the derived cap and every must-claim cell without a claim ({frz})"

def ctx_inventory(cfg, rnd=0):
    m = MET(cfg); inv = m.get("inventory")
    if not inv: sys.exit("this method has no inventory phase")
    sc = cfg["scoring"]; js, md, kind, role, agent = scope_info(inv["scope"], m)
    rows = [("SCOPE", inv["scope"]), ("AGENT NAME", agent)] + model_rows(cfg, "inventory") + helper_rows(cfg) + common_rows(cfg, "inventory")
    for k, v in (inv.get("inputs") or {}).items(): rows.append((k, fmt(v, cfg)))
    rows += [("REFERENCE", rel_ref()), ("TEMPLATE", template_of(cfg, kind)), ("OUTPUT", inv["output"]), ("CHECK", f"{CLI} md_to_json {kind} {inv['output']}"), ("ROUND", rnd or 0), ("FIX LIST", f"analysis/gauntlet/{inv['scope']}/round{int(rnd) - 1}-issues.md" if rnd and int(rnd) > 0 else ""), ("CLAIM CAP", claim_cap_text(cfg, inv["scope"], js, kind, sc.get("max_claims", 40)))] + quote_rows(cfg)
    xr, xb = extra(cfg, "inventory", inv["scope"], rnd)
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr), method_notes(cfg, "inventory")] + xb if x)

def ctx_consolidate(cfg, which, rnd=0):
    m = MET(cfg); c = m["consolidations"].get(which)
    if not c: sys.exit(f"unknown consolidation {which} (method has: {', '.join(m['consolidations']) or 'none'})")
    js, md, kind, role, agent = scope_info(which, m); lean = cfg.get("split") == "none"; b = m.get("briefs", {})   # split none - no scope analyses, the corpus is read here
    dg = "DIGEST (read FIRST - the inventory rows with their citing claim ids and the corpus index; this run has no scope analyses)" if lean else "DIGEST (read FIRST - all scope rows you need, with citing claim ids)"
    ho = (m.get("inventory") or {}).get("handover", ""); ho = ho if not lean or (ho and os.path.exists(P(ho))) else ""
    rows = [("SCOPE", which), ("AGENT NAME", agent)] + model_rows(cfg, "consolidator") + helper_rows(cfg) + common_rows(cfg, "consolidator") + [(dg, f"analysis/consolidated/digest-{which}.md ({CLI} render digest {which})"), ("INPUTS", fmt(b.get(f"consolidator_inputs_{cfg.get('_profile')}", b.get("consolidator_inputs", "")) if lean else b.get("consolidator_inputs", ""), cfg)), ("HANDOVER", ho), ("REFERENCE", rel_ref()), ("TEMPLATE", template_of(cfg, kind)), ("OUTPUT", c["output"]), ("CHECK", f"{CLI} md_to_json {kind} {c['output']}"), ("ROUND", rnd or 0), ("FIX LIST", f"analysis/gauntlet/{which}/round{int(rnd) - 1}-issues.md" if rnd and int(rnd) > 0 else "")]
    for k, v in (c.get("head_fields") or {}).items(): rows.append((k, fmt(v, cfg)))
    rows += quote_rows(cfg)
    xr, xb = extra(cfg, "consolidator", which, rnd)
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr), method_notes(cfg, "consolidate", which)] + xb if x)

def ctx_critic(cfg, critic, scope, rnd):
    m = MET(cfg); consolidated = is_consolidated(scope, m); js, md, kind, role, owner = scope_info(scope, m)
    light = (not consolidated) and is_light(scope); sc = cfg["scoring"]; rnd_i = int(rnd)
    if critic == "client": model_key = "critic_client_light" if light else "critic_client"
    else: model_key = "critic_standard_consolidation" if consolidated else "critic_standard"
    maxr = sc.get("max_gauntlet_rounds_light", 2) if light else sc["max_gauntlet_rounds"]; b = m.get("briefs", {})
    if sc.get("defect_rework_rounds"): maxr = f"{maxr} (+{sc['defect_rework_rounds']} rework round for defects only)"   # (profile lean)
    pk = critic_pack(critic, cfg)   # per-pack standard critic (or the method hook's per-technology critic)
    dc = declared_critic(critic, cfg); dpk = [knowledge_pack(n) for n in dc["sources"]["packs"]] if dc else []   # a declared discipline critic with its own persona and sources
    sfx = f"-{critic}" if pk or dc else ""; role = critic_role(critic)
    persona = fmt((cfg.get("briefs") or {}).get("critic_client_persona") or b.get("critic_client_persona", "the client's own senior expert who knows the client's material inside out and is sceptical of consultants"), cfg) if critic == "client" else (fmt(dc["persona"], cfg) if dc and dc["persona"] else None) or ((pack_snippets(cfg, pk) if pk else snippets(cfg)).get(b.get("critic_standard_persona_key", "critic_standard_persona"), "") or b.get("critic_standard_persona", "an independent expert of the external standard (vendor products, reference architectures, catalogues) for the subject of this run"))
    drows = [("YOUR CLAIMS", "every claim of this scope" if dc["scores"] == "all" else f"the claims on your topics ({', '.join(dc['scores']['topics'])}); the critic pack holds exactly these"),
             ("YOUR SOURCES: KNOWLEDGE PACKS (read their notes first)", "; ".join(f"{x.get('display', x['name'])}: {relp(os.path.join(x['_dir'], 'NOTES.md'), RUN) if os.path.exists(os.path.join(x['_dir'], 'NOTES.md')) else relp(x['_dir'], RUN)}" for x in dpk)),
             ("YOUR SOURCES: WEB DOMAINS (search and cite these; stated here, not enforced per critic)", dc["sources"]["domains"]),
             ("YOUR SOURCES: REFERENCE FILE", f"{rel_ref()} (PS-7-NNN)" if dc["sources"]["reference"] else "not one of your sources - judge against the packs and domains above")] if dc else []
    rows = [("SCOPE", scope), ("SCOPE KIND", "consolidated (cross-scope evidence expected)" if consolidated else ("single scope, LIGHT GAUNTLET" if light else "single scope")), ("CRITIC", critic), ("PERSONA", persona), ("AGENT NAME", f"critic-{critic}-{scope}"), ("ROUND", f"{rnd} of max {maxr}")] + model_rows(cfg, model_key) + helper_rows(cfg) + ([("TECHNOLOGY PACK (you score its options' claims and the option-neutral ones)", f"{pk.get('display', pk['name'])} ({pk['name']})")] if pk else []) + drows + [
            ("CRITIC PACK (read first)", f"analysis/gauntlet/{scope}/critic-pack{sfx}.md"), ("CLAIMS", f"analysis/gauntlet/{scope}/claims{sfx}.md"), ("DELTA (score only these)", f"analysis/gauntlet/{scope}/claims-delta{sfx}.md" if rnd_i > 1 else ""), ("COVERAGE REPORT (rows no claim cites - open a sample)", f"analysis/gauntlet/{scope}/coverage-round{rnd}.md"), ("DANGLING EVIDENCE", f"analysis/gauntlet/{scope}/dangling-evidence.md ({CLI} evidence check {scope})" if critic == "client" else ""), ("REFERENCE DELTA (re-score carried claims these rows narrow)", f"analysis/gauntlet/{scope}/reference-delta-round{rnd}.md" if rnd_i > 1 else ""), ("ANALYSIS (the LIVE text under judgement)", relp(md, RUN))]
    rows += common_rows(cfg, role) + [("REFERENCE", rel_ref() if not dc or dc["sources"]["reference"] else ""), ("PASS THRESHOLD", sc["pass_threshold"]), ("MISSING CLAIMS CAP", 0 if rnd_i > sc.get("freeze_register_after_round", 2) else sc.get("max_missing_claims_per_round", 3)), ("CARRIED EVIDENCE SAMPLE", f"open the evidence cells of {sc.get('carried_evidence_sample', 5)} carried claims (your choice, name them in the summary)" if rnd_i > 1 and critic == "client" else ""), ("TEMPLATE", "templates/critic-scores.md"), ("OUTPUT", f"analysis/gauntlet/{scope}/round{rnd}-{critic}.md"), ("CHECK", f"{CLI} md_to_json critic analysis/gauntlet/{scope}/round{rnd}-{critic}.md  (run it ONCE; after score_aggregate the file is closed)")]
    xr, xb = extra(cfg, role, scope, rnd)
    notes = "\n\n".join(method_notes(cfg, role, pack=x) for x in dpk) if dpk else method_notes(cfg, role, pack=pk)   # a declared critic: the notes of its own packs
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr), notes] + xb if x)

def persona_file(cfg, persona):
    name = f"{persona.replace('_', '-')}.md"
    configured = (cfg.get("personas") or {}).get("directories", [])
    cands = [os.path.abspath(os.path.expanduser(path)) + os.sep + name for path in configured]
    cands.append(os.path.join(PLUGIN, "knowledge", "personas", name))
    chosen = next((path for path in cands if os.path.exists(path)), cands[-1])
    return relp(chosen, RUN) if chosen.startswith(PLUGIN) or chosen.startswith(PROJECT_DIR) else chosen

def hygiene_gate(cfg, rnd):
    """G2: no persona or verifier brief while the customer edition fails the hygiene layer (the round's report, re-run when stale)."""
    import lint_deliverable as LD
    files = LD.edition_files(cfg, "customer"); rp = P("analysis", "gate", f"round{rnd}-hygiene.json")
    if not files:
        if "--force" not in sys.argv: sys.exit(f"REFUSED: no customer workbook in deliverables/ - build first ({CLI} build_excel --all), then {CLI} render_workbook --all")
        print("WARNING: no customer workbook in deliverables/ - rendered anyway (--force)", file=sys.stderr); return {"passed": False, "errors": 0, "cached_values": {}}
    rep = load_json(rp, None) if os.path.exists(rp) and os.path.getmtime(rp) >= max(os.path.getmtime(f) for f in files) else None
    if rep is None: rep = LD.standalone(files, cfg); LD.write_round(rep, rnd)
    if not rep["passed"]:
        msg = f"the customer edition fails the hygiene layer ({rep['errors']} error(s), analysis/gate/round{rnd}-hygiene.md)"
        if "--force" not in sys.argv: sys.exit(f"REFUSED: {msg}. Personas and the verifier read a clean customer edition only: clear it (deliverable-editor with the fix plan, `{CLI} build_excel --all`, `{CLI} render_workbook --all`, `{CLI} lint_deliverable --standalone --all --round {rnd}`). --force plus `{CLI} status assume <reason>` is the only way past.")
        print(f"WARNING: {msg} - rendered anyway (--force); record why with `{CLI} status assume`", file=sys.stderr)
    return rep

def gate_inputs(cfg, rnd, keys=None):
    """rows every gate role shares: the customer workbooks it reads, their renderings, the hygiene state; takes the round's snapshot"""
    import gate
    rep = hygiene_gate(cfg, rnd); gate.snapshot(rnd, cfg)
    files = gate.customer_files(cfg, keys); renders = gate.latest_render(cfg, keys); nocache = [f for f, ok in (rep.get("cached_values") or {}).items() if not ok and f in {os.path.basename(x) for x in files.values()}]
    rows = [("DELIVERABLES (customer edition - the only workbooks you read)", list(files.values())), ("RENDERINGS (what the client sees: index.json lists the first page of every sheet as an image, all Management Summary pages, and the full PDF)", [f"{k}: {v}/index.json" for k, v in renders.items()])]
    if nocache or len(renders) < len(files): rows.append(("RENDERING WARNING", f"no recalculated values / rendering for {', '.join(sorted(set(nocache) | {os.path.basename(f) for k, f in files.items() if k not in renders}))}: openpyxl shows formulas without values there - judge figures and charts from the formulas and say so in the rationale; never count a missing value as a wrong figure"))
    rows.append(("HYGIENE", f"analysis/gate/round{rnd}-hygiene.md ({'clean' if rep['passed'] else 'FAILED - rendered with --force'}) - the tool already checked wording, ids, locators, formulas, reconciliation and format; do not re-count what it checks"))
    return rows

def ctx_gate(cfg, persona, rnd):
    import gate
    rnd = int(rnd); qs = gate.key_questions(cfg, persona, rnd); keys = sorted({k for x in qs for k in x["deliverables"]})
    rows = [("PERSONA", persona), ("AGENT NAME", f"gate-{persona}")] + model_rows(cfg, "gate") + [("PERSONA FILE", persona_file(cfg, persona)), ("ROUND", rnd), ("CONSULTANCY", cfg["engagement"].get("consultancy", "")), ("STUDY", cfg["engagement"].get("run_title") or MET(cfg).get("display", ""))] + common_rows(cfg, "gate")
    rows += gate_inputs(cfg, rnd, keys) + [("PASS RULE", f"per persona mean over the key questions >= {cfg['scoring']['pass_threshold']}, no key question < {cfg['scoring'].get('gate_question_floor', 7)}, no blocker"), ("TEMPLATE", "templates/gate-scores.md"), ("OUTPUT", f"analysis/gate/round{rnd}-{persona}.md"), ("CHECK", f"{CLI} md_to_json gate {f'analysis/gate/round{rnd}-{persona}.md'}")]
    if rnd > 1: rows += [("YOUR PREVIOUS ISSUES", f"analysis/gate/round{rnd - 1}-{persona}.json (listed below)"), ("CHANGES SINCE ROUND " + str(rnd - 1), f"analysis/gate/round{rnd}-diff.md (tool diff of the customer workbooks)")]
    new = {c["question_id"] for c in gate.question_changes(cfg) if c["persona"] == persona and c["action"] == "reword" and c["from_round"] == rnd}   # reworded for this round: scored fresh, not against the last round's score
    kq = "## KEY QUESTIONS (score each on the anchored scale; judge only the deliverables a question names)\n" + "\n".join(f"- **{x['id']}** [{', '.join(x['deliverables'])}] {x['text']}" + (" (new wording this round - score it fresh)" if x["id"] in new else "") for x in qs)
    xr, xb = extra(cfg, "gate", persona, rnd)
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr), kq, method_notes(cfg, "gate")] + xb if x)

def previous_round_blocks(cfg, persona, rnd):
    """round >= 2: the persona's own previous issues + the tool diff - never orchestrator prose (G9)"""
    import gate, gate_diff
    prev = load_json(f"analysis/gate/round{rnd - 1}-{persona}.json", {}) or {}
    diffp = P("analysis", "gate", f"round{rnd}-diff.md")
    if os.path.isdir(gate_diff.snapshot_dir(rnd - 1)) and (not os.path.exists(diffp) or os.path.getmtime(diffp) < os.path.getmtime(gate_diff.snapshot_dir(rnd))): gate_diff.diff(rnd)
    issues = "\n".join(f"- {i.get('id')} [{i.get('severity')}, {i.get('kind')}] {i.get('deliverable')} {i.get('location')}: {i.get('issue')}" for i in prev.get("issues", [])) or "(none recorded)"
    return ("## YOUR PREVIOUS ISSUES (round " + str(rnd - 1) + ") - re-read the cells: fixed, partly fixed or not fixed? A fixed issue is not raised again; one not fixed is raised again with the same id prefix and the cell as it reads now\n" + issues,
            "## CHANGES SINCE ROUND " + str(rnd - 1) + "\n" + (f"`analysis/gate/round{rnd}-diff.md` lists every changed cell (tool output). Read the whole deliverables anyway: a fresh read finds what the last round missed." if os.path.exists(diffp) else "(no snapshot of the previous round - read everything fresh)"))

def ctx_verifier(cfg, rnd):
    import gate
    rnd = int(rnd); sp, n = gate.sample(rnd, cfg=cfg)
    rows = [("AGENT NAME", "gate-verifier"), ("ROLE", "the consultancy's own verifier - you check that each sampled row's locator supports its statement, against the client's repository")] + model_rows(cfg, "verifier") + [("ROUND", rnd), ("CONSULTANCY", cfg["engagement"].get("consultancy", ""))] + common_rows(cfg, "verifier")
    rows += gate_inputs(cfg, rnd) + [("SAMPLE (check these rows, in order)", f"{relp(sp, RUN)} ({n} rows, drawn by the tool)"), ("PASS RULE", f"your score >= {cfg['scoring']['pass_threshold']} on every deliverable"), ("TEMPLATE", "templates/verifier-scores.md"), ("OUTPUT", f"analysis/gate/round{rnd}-verifier.md"), ("CHECK", f"{CLI} md_to_json verifier {f'analysis/gate/round{rnd}-verifier.md'}")]
    xr, xb = extra(cfg, "verifier", None, rnd)
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr), method_notes(cfg, "verifier")] + xb if x)

def ctx_editor(cfg, rnd):
    rnd = int(rnd); lang = cfg["languages"]["deliverable"]; fp = f"analysis/gate/round{rnd}-fixplan.md"
    if rnd > 0 and not os.path.exists(P(fp)): sys.exit(f"REFUSED: no fix plan for round {rnd} ({CLI} gate_aggregate {rnd} first)")
    keys = [k for k, v in cfg.get("deliverables", {}).items() if isinstance(v, dict) and v.get("enabled")]
    plan = ("FIX PLAN (execute it)", f"{fp} + .json (clusters with mechanism, owner, acceptance test)") if rnd else ("PRE-GATE PASS (round 0)", f"no fix plan yet: write the management summaries after this build and clear every finding of analysis/gate/round1-hygiene.md ({CLI} lint_deliverable --standalone --all --round 1)")
    rows = [("AGENT NAME", "deliverable-editor"), ("ROUND", f"{rnd} (the next gate round is {rnd + 1})")] + model_rows(cfg, "editor") + common_rows(cfg, "editor") + [
        plan, ("HYGIENE REPORT", f"analysis/gate/round{max(rnd, 1)}-hygiene.md"),
        ("RUN OVERRIDES (spec, id-keyed patches)", f'overrides/deliverables.{lang}.json -> "patches": [{{"deliverable": "D1", "sheet": "<name>", "column": "<id or field>", "set": {{...}}}} | {{..., "remove_column": "<id>"}} | {{..., "insert_column": {{...}}, "after": "<id>"}}], applied after the merge; whole-list replacement only where a patch cannot express it'),
        ("LABELS", f"overrides/labels.{lang}.json"), ("KERNAUSSAGEN (sidecar, wins over the analysis wording)", "analysis/summaries/key_statements.json {\"<row key>\": \"<= 160 characters\"}"), ("MANAGEMENT SUMMARIES (written after the build, {kpi:<id>} for every figure)", ", ".join(f"analysis/summaries/{k}.md" for k in keys)),
        ("TOOLS", f"{CLI} build_excel --check · {CLI} build_excel --all · {CLI} render_workbook --all · {CLI} lint_deliverable --standalone --all --round {rnd + 1} · {CLI} gate diff {rnd + 1} (after the rebuild)"),
        ("NEVER EDIT", "scores, round results, claims registers (the `## Claims` table of any analysis), deliverables/ directly, state/"),
        ("OUTPUT", f"analysis/gate/round{rnd}-editor.md (per cluster: done / requested / escalated, what changed, the acceptance test result)"), ("CHECK", f"test -s analysis/gate/round{rnd}-editor.md")]
    xr, xb = extra(cfg, "editor", None, rnd)
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr), method_notes(cfg, "editor")] + xb if x)

def claims_snapshot_gate(scope, rnd, md):
    """a critic brief needs the round's claims snapshot, taken after the last edit of the analysis it scores"""
    snap = P("analysis", "gauntlet", scope, f"claims-round{rnd}.json")
    if "--force" in sys.argv: return
    if not os.path.exists(snap): sys.exit(f"REFUSED: no claims snapshot for round {rnd} of {scope} ({relp(snap, RUN)}): run `{CLI} extract_claims {scope} --round {rnd}` first - a critic brief without it scores a register that was never extracted.")
    if os.path.exists(md) and os.path.getmtime(md) > os.path.getmtime(snap) + 1: sys.exit(f"REFUSED: {relp(md, RUN)} is newer than {relp(snap, RUN)} - the snapshot is stale (a refused or earlier extraction). Re-run `{CLI} extract_claims {scope} --round {rnd}`; --force only with `{CLI} status assume <reason>`.")

def research(cfg):
    seeds = []
    for pk in packs_of(cfg) + extra_option_packs(cfg):   # every technology of the run's options, not only the slots
        sp = os.path.join(pk["_dir"], pk.get("research_seed", "research-seed.md"))
        if os.path.exists(sp): seeds.append(f"### {pk.get('kind')} pack {pk['name']} ({pk.get('_slot')})\n" + open(sp, encoding="utf-8").read())
    mt = MET(cfg).get("research_topics")
    if mt: seeds.append("### method topics\n" + fmt(mt, cfg))
    rows = [("AGENT NAME", "researcher")] + model_rows(cfg, "researcher") + common_rows(cfg, "researcher") + [("OUTPUT", f"{rel_ref()} (update in place: fill every (verify) item, add URL + date; section 7 only via {CLI} reference add|correct)"), ("DOCS DOMAINS", "; ".join(x for x in [snippets(cfg).get("docs_domains", "")] + [pack_snippets(cfg, pk).get("docs_domains", "") for pk in extra_option_packs(cfg)] if x)), ("WEB RESEARCH", f"Use only `{CLI} safe_web`; hosted web search is outside the local privacy-hook boundary.")]
    return "\n\n".join([block("CONTEXT", rows), method_notes(cfg, "researcher"), "## RESEARCH TOPICS (from the knowledge packs and the method)\n" + ("\n\n".join(seeds) or "(no seeds - research the versions/plans named above)")])

# ------------------------------------------------------------------ handover (inventory -> everyone downstream)
def fmt_claim(c, derived_markers):
    ev = c.get("evidence", []); derived = derived_markers and any(any(mk in e for mk in derived_markers) for e in ev) and not any(re.search(r":\d+", e) or "#" in e for e in ev)
    return f"- **{c['id']}** [→{c.get('target', '')}]{' [TOOL-DERIVED figure - never independently recounted; treat as upper bound]' if derived else ''} {c['statement']}  \n  evidence: {ev}"

def handover_text(cfg):
    m = MET(cfg); inv = m.get("inventory")
    if not inv: raise SystemExit("this method has no inventory phase")
    js, md, kind, role, agent = scope_info(inv["scope"], m); ana = load_json(js, None)
    if not ana: raise SystemExit(f"missing {relp(js, RUN)} (run {CLI} md_to_json {kind} ... first)")
    scopes = sorted(x.get(inv.get("scopes_key", "name")) for x in ana.get(inv.get("scopes_table", "scopes"), []) if x.get(inv.get("scopes_key", "name")))
    sj = load_json(SCOPES_PATH, {"scopes": {}}); scopes = sorted(set(scopes) | set(sj["scopes"]))
    per = {u: [] for u in scopes}; cross = []
    for c in ana.get("claims", []):
        text = c["statement"] + " " + " ".join(c.get("evidence", [])) + " " + (c.get("target") or "")   # target (e.g. D1/Units:shopcore) routes a claim whose statement names the scope only descriptively
        hits = [u for u in scopes if re.search(r"(?<![A-Za-z0-9_])" + re.escape(u) + r"(?![A-Za-z0-9_])", text)]
        for u in hits: per[u].append(c)
        if len(hits) == 0 or len(hits) >= 3: cross.append(c)
    dm = inv.get("derived_markers", [])
    lines = [f"# {inv['scope']} handover – verified facts per scope (generated by `{CLI} render handover` from the inventory analysis, status {ana.get('status', '?')})", "",
             f"Purpose: every analyst, consolidator and critic starts from these verified facts instead of from zero. Claim ids refer to `{inv['output']}` → Claims (scores on the {inv['scope']} Claims sheet). Treat as public facts; correct them only with new evidence and report the correction as \"handover correction: C-xxx\".", ""]
    for u in scopes: lines += [f"## {u}  ({len(per[u])} claims)"] + ([fmt_claim(c, dm) for c in per[u]] or [f"- (no {inv['scope']} claim names this scope)"]) + [""]
    lines += [f"## Cross-cutting facts ({len(cross)} claims – for consolidators, standard critics, researcher)"] + [fmt_claim(c, dm) for c in cross] + [""]
    return "\n".join(lines)

def handover_section(cfg, scope):
    inv = MET(cfg).get("inventory"); p = P(inv["handover"]) if inv and inv.get("handover") else None
    if not p or not os.path.exists(p): return ""
    for part in re.split(r"\n(?=## )", open(p, encoding="utf-8").read()):
        if re.match(r"## " + re.escape(scope) + r"\s", part): return part.strip()
    return ""

# ------------------------------------------------------------------ digest (all final scopes -> one consolidator)
def digest_lean(cfg, which, m):
    """split none (profile lean): no scope analyses - the digest carries the passed inventory (rows with their citing claim ids,
    the claims) and the corpus index; the consolidator reads the corpus itself"""
    from common import CORPUS_DIR
    inv = m.get("inventory") or {}; SP, _ = spec(cfg); d = load_json(scope_info(inv["scope"], m)[0], {}) if inv else {}
    cl = d.get("claims", []) or []; idx = read_json(os.path.join(CORPUS_DIR, "index.json"), {"sources": {}})
    def cites(key): return [x["id"] for x in cl if key and str(key).lower() in ((x.get("target") or "") + " " + x["statement"] + " " + " ".join(x.get("evidence", []))).lower()]
    def cell(v): return (";".join(map(str, v)) if isinstance(v, list) else str(v if v is not None else "")).replace("|", "/").replace("\n", " ")
    lines = [f"# Consolidation digest {which} - generated by `{CLI} render digest {which}` from the inventory and the corpus (profile {cfg.get('_profile')}: split none, no scope analyses)", "",
             f"Provenance: the inventory `{inv.get('output', '')}` (status {d.get('status', '?')}; its claims are citable by id once the inventory passed) and the corpus index. You are the analyst of everything in this run: a fact the inventory does not carry you read in the corpus yourself (EVIDENCE BASES) and cite with its locator and a verbatim `quote`. Rows with NO citing claim were never checked beyond the CHECK - verify them in the corpus before you rely on one.", ""]
    for sec in SP.get(inv.get("kind", "inventory"), {"sections": []})["sections"]:
        if sec.get("type") != "table" or sec["key"] in ("claims", "open_questions"): continue
        fields = list(sec["fields"])
        lines += [f"## {sec['heading']} (inventory)", "", "| " + " | ".join(fields) + " | citing claims |", "|" + "---|" * (len(fields) + 1)]
        lines += [f"| " + " | ".join(cell(r.get(f)) for f in fields) + f" | {cell(cites(r.get(fields[0]))) or 'NONE'} |" for r in d.get(sec["key"], []) or []] + [""]
    lines += [f"## Inventory claims ({len(cl)}) - cite by id", ""] + [f"- {x['id']} [{x.get('type')}] {cell(x['statement'])} (evidence: {cell(x.get('evidence'))})" for x in cl] + [""]
    lines += [f"## The corpus ({len(idx.get('sources', {}))} documents, `corpus/index.json`; text with anchors in corpus/text/SRC-nnn.md)", ""] + [f"- {k} `{v.get('title', '')}` [{v.get('type', '')}, {v.get('units', '?')} anchors, text {v.get('quality', '?')}]" for k, v in sorted((idx.get("sources") or {}).items())]
    mod = load_method_module("briefing")
    if mod and hasattr(mod, "digest_extra"): lines += [""] + (mod.digest_extra(which, {}, cfg) or [])
    out = P("analysis", "consolidated", f"digest-{which}.md"); os.makedirs(os.path.dirname(out), exist_ok=True); open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"wrote {relp(out, RUN)} ({len(lines)} lines, inventory + {len(idx.get('sources', {}))} corpus documents; split none)")

def digest(cfg, which):
    m = MET(cfg); c = m["consolidations"].get(which)
    if not c: sys.exit(f"unknown consolidation {which}")
    if cfg.get("split") == "none": return digest_lean(cfg, which, m)
    SP, _ = spec(cfg); skind = m["scopes"].get("kind"); k = SP.get(skind, {"sections": []})
    tables = c.get("digest_tables") or [s["key"] for s in k["sections"] if s.get("type") == "table" and s["key"] not in ("claims",)]
    scopes = {}
    for fp in sorted(glob.glob(P(m["scopes"].get("output_dir", "analysis/scopes"), "*.json"))):
        d = load_json(fp, {}); scopes[os.path.basename(fp)[:-5]] = d
    st = load_json(STATUS_PATH, {"scopes": {}})
    def cites(d, key): return [cl["id"] for cl in d.get("claims", []) if key and str(key).lower() in ((cl.get("target") or "") + " " + cl["statement"] + " " + " ".join(cl.get("evidence", []))).lower()]
    def cell(v): return (";".join(map(str, v)) if isinstance(v, list) else str(v if v is not None else "")).replace("|", "/").replace("\n", " ")
    lines = [f"# Consolidation digest {which} - generated by `{CLI} render digest {which}` from the {len(scopes)} scope analyses", "",
             "Provenance: every row names its scope and the claim ids that cite it. Rows with NO citing claim were never scored by a critic (the gauntlet grades claims, not rows) - treat them as unreviewed. Scope status from STATUS: final = passed the gauntlet; failed-gauntlet = usable, cite its open issues.", "",
             "| scope | status | rounds | scores |", "|---|---|---|---|"] + [f"| {u} | {st['scopes'].get(u, {}).get('status')} | {st['scopes'].get(u, {}).get('rounds')} | {st['scopes'].get(u, {}).get('last_scores')} |" for u in scopes] + [""]
    for t in tables:
        sec = next((s for s in k["sections"] if s.get("key") == t), None)
        if not sec or sec.get("type") != "table": continue
        fields = list(sec["fields"]); key_field = fields[0]
        lines += [f"## {sec['heading']} (all scopes)", "", "| scope | " + " | ".join(fields) + " | citing claims |", "|---|" + "---|" * len(fields) + "---|"]
        for u, d in scopes.items():
            for r in d.get(t, []): lines.append(f"| {u} | " + " | ".join(cell(r.get(f)) for f in fields) + f" | {cell(cites(d, r.get(key_field)) or cites(d, str(r.get(fields[1], ''))[:30]) if len(fields) > 1 else cites(d, r.get(key_field))) or 'NONE'} |")
        lines.append("")
    eo = load_json("analysis/consolidated/estate_observations.json", [])
    if eo: lines += [f"## Estate observations collected by the critics ({len(eo)})", ""] + [f"- [{e['scope']} r{e['round']} {e['critic']}] {e['text']}" for e in eo]
    mod = load_method_module("briefing")
    if mod and hasattr(mod, "digest_extra"): lines += [""] + (mod.digest_extra(which, scopes, cfg) or [])
    out = P("analysis", "consolidated", f"digest-{which}.md"); os.makedirs(os.path.dirname(out), exist_ok=True); open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"wrote {relp(out, RUN)} ({len(lines)} lines, {len(scopes)} scopes)")

# ------------------------------------------------------------------ complete briefs
def _cell(v): return str(v if v is not None else "").replace("\n", " ").strip()

def relayed_items(text):
    """every question, reference row and claim an addendum or lead block names, as its STORED text -
    a paraphrase has inverted facts on the way (a reference row turned into a deliverable, an inference put into a lead fact)."""
    from common import load_questions
    out = []
    qs = {q.get("id"): q for q in load_questions() if q.get("id")}
    for qid in sorted({t for t in re.findall(r"\b[A-Z][A-Za-z]*-[\w.-]*\d\b", text) if t in qs}):
        q = qs[qid]; line = f"- **{qid}** (from {q.get('from')}, to {q.get('to')}, status {q.get('status')}): {_cell(q.get('question'))}"
        if q.get("options"): line += " Options: " + "; ".join(f"{o.get('key')}) {_cell(o.get('text'))}" + (" (recommended)" if o.get("recommended") else "") for o in q["options"])
        answers = q.get("answers") or ([q["answer"]] if q.get("answer") else [])
        for an in answers:
            opt = next((o for o in q.get("options") or [] if o.get("key") == an.get("option")), None)
            line += f"\n  - answer by {an.get('by', '?')} [weight {an.get('weight', '?')}, type {an.get('type', '?')}, {an.get('at', '')}]" + (f" option {an['option']}" + (f" \"{_cell(opt.get('text'))}\"" if opt else "") if an.get("option") else "") + (f": \"{_cell(an.get('text'))}\"" if an.get("text") else "")
        if not answers: line += "\n  - (no answer yet - an open question is not evidence)"
        out.append(line)
    ps = sorted(set(re.findall(r"\bPS-7-\d+\b", text)))
    if ps:
        rows = {}
        ref = os.path.join(REF_DIR, "platform-standard.md")
        if os.path.exists(ref):
            in7 = False
            for l in open(ref, encoding="utf-8"):
                if l.startswith("## 7"): in7 = True; continue
                if in7 and l.startswith("## "): break
                if in7 and l.startswith("| PS-7-"):
                    import reference; raw = reference.split(l); c = reference.norm(raw); rows[c[0]] = c + reference.quote_cell(raw)   # 8 columns (+ an optional quote); legacy rows get a derived status
        for i in ps:
            c = rows.get(i)
            out.append(f"- **{i}** " + (f"fact: \"{c[1]}\" | applies to: {c[2]} | url: {c[3]} | date: {c[4]} | provenance: {c[5]} | status: {c[7]}" + (f" | quote: \"{c[8]}\"" if len(c) > 8 else "") if c else "(no such reference row - the id is dangling)"))
    for cid in sorted(set(re.findall(r"\bC-[\w.-]+-\d+\b", text))):
        mm = re.fullmatch(r"C-(.+)-(\d+)", cid); scope = mm.group(1); c = None; state = "unknown scope"
        try:
            js = scope_info(scope)[0]; c = next((x for x in (load_json(js, {}) or {}).get("claims", []) if x.get("id") == cid), None)
            import evidence; ok = evidence.cross_scope_claim(cid)[1]; state = "scored, scope final" if ok else "UNSCORED - unverified (scope not final)"
        except SystemExit: pass
        out.append(f"- **{cid}** [{state}] " + (f"\"{_cell(c.get('statement'))}\" (target {c.get('target', '')}; evidence: {'; '.join(c.get('evidence') or [])})" if c else "(no such claim in the analyses)"))
    return ("## RELAYED ITEMS (verbatim from the registers - where the text below restates one of these, this block is the fact)\n" + "\n".join(out)) if out else ""

def render_addendum(a):
    if "--addendum" in a:
        ap = a[a.index("--addendum") + 1]; ap = ap if os.path.isabs(ap) else P(ap)
        if not os.path.exists(ap): sys.exit(f"addendum file not found: {ap}")
        body = open(ap, encoding="utf-8").read().strip(); rel = relayed_items(body)
        return "\n\n".join(x for x in [rel, "## ORCHESTRATOR NOTE - verify (from " + relp(ap, RUN) + ")\nThis note is the orchestrator's own wording: every figure, locator, mechanism or restated answer in it that is not marked VERIFIED (by whom, how) is a hypothesis - reproduce it before you write it, dispute it with your own measurement if it does not reproduce. Questions, reference rows and claims it names are relayed verbatim above; its gloss belongs under `## HYPOTHESES (verify)`.\n\n" + body] if x)
    return ""

def question_line(q):
    """One brief line per question. An answer given WITHOUT an option rejected the question's premise or chose none of the
    options: the brief shows the corrected framing and hides the superseded options, so later scopes stop reading them."""
    ans = q.get("answer") or {}; line = f"- {q.get('id')} (from {q.get('from')}): {q.get('question')}"
    if ans.get("text") and not ans.get("option") and q.get("options"):
        return line + f" ANSWERED WITHOUT AN OPTION by {ans.get('by') or 'lead'} - the options are superseded, work from this framing: {ans['text']}"
    if q.get("options"): line += " Options: " + "; ".join(f"{o['key']}) {o['text']}" + (" (recommended)" if o.get("recommended") else "") for o in q.get("options", []))
    return line

def routed_questions(scope):
    from common import load_questions
    out = []
    for q in load_questions():
        ans = q.get("answer") or {}; corrected = bool(ans.get("text")) and not ans.get("option") and bool(q.get("options"))
        if re.match(re.escape(scope) + r"(\b|\s|\()", q.get("to", "")) and ((q.get("status") or "").lower().startswith("open") or corrected):
            out.append(question_line(q))
    return out

def lead_block(scope, kind):
    """LEAD HINTS (analysts: hypotheses) / LEAD FACTS (critics: binding) written by `dbcx inbox apply` from the dashboard."""
    fp = P("analysis", "briefs", f"lead-{kind}-{scope}.md")
    if not os.path.exists(fp): return ""
    body = open(fp, encoding="utf-8").read().strip(); rel = relayed_items(body)
    if rel: body += "\n\n" + rel.replace("## RELAYED ITEMS", "### RELAYED ITEMS", 1)
    if kind == "hints": return "## LEAD HINTS (from the engagement lead; hypotheses - reproduce before adopting, never cite or quote the lead in the analysis)\n" + body
    return "## LEAD FACTS (stated by the engagement lead; BINDING for this engagement)\nScore the named claims against these facts: a lead fact overrules a contradicting documentation or document source for this engagement. Record the conflict in `issue` (\"lead fact PS-7-NNN / lead-facts file overrules <source>\"), never mark a claim false on the strength of the overruled source.\n" + body

FOLLOW = "Follow your agent definition."
CONSOLIDATED_SCOPE_RULE = "## SCOPE RULE FOR A CONSOLIDATED SCOPE\nThis scope is cross-scope BY DEFINITION: evidence into any scope's material, the scope analyses (cite their claim ids), the inventory and the handover are all legitimate; the single-scope rule does NOT apply here. What remains a violation: an evidence locator that does not exist, a scope claim id that does not say what the consolidation says it says, a figure re-derived without stating its rule."

def rework_block(cfg, rnd):
    frozen = rnd > cfg["scoring"].get("freeze_register_after_round", 2)
    return (f"## REWORK ROUND {rnd} - numbered steps\n1. Fix every item of the FIX LIST. Every fix hint is a hypothesis: reproduce a count, locator or mechanism before adopting it; if it does not reproduce, dispute it with your own measurement (report 'hints verified / hints disputed'). An 'at least N' in a hint is a floor - re-run the whole measurement under one stated rule, never quote the floor.\n"
            f"2. Claims that passed and are unchanged keep their score automatically - do not rewrite them (an edit re-enters the claim into the delta and it is re-scored WHOLE). Add claims only for the missing-claim items in the FIX LIST" + (f" - none at all: the register is frozen after round {cfg['scoring'].get('freeze_register_after_round', 2)}" if frozen else "") + ". Never reuse an existing claim id for a different proposition - ids are stable once scored; a finding the register cannot take goes into the fitting non-claim section and into your report.\n"
            "3. After every correction sweep EVERY other home of the same fact - summary, rationale, every table row incl. verdict/score/effort columns - grep the OLD figure before the first edit and again after the last; the aggregate claim that summarises a table is re-synced from the table.\n"
            "4. A corrected statement is written as if it had always been right: absolute, present tense, no dates of edits, no 'round', 'corrected', 'critic', 'analyst', 'orchestrator', 'session'. The history goes into the claim's `history` column (internal, never exported).\n"
            "5. Re-read the evidence-cell rules in the TEMPLATE's Claims comment before you edit a cell: conventions may have been tightened since your first round, and a rework that only reads the FIX LIST misses them.\n"
            f"6. Set `round: {rnd}`, re-check with the CHECK command, then SEND your report (a message to the orchestrator - text in your transcript is not a report): addressed vs disputed issue numbers and the sweep result (old figure occurrences before/after). Sending freezes the file; if you still have edits, report 'still working' instead.")

CLOSED_SCOPE_STATES = ("final", "failed-gauntlet", "skipped")


def wave_gate(name):
    """A wave closes before the next one opens: no analyst brief for a scope of a later wave while the open wave still
    has work. Overlapping waves multiply the live agents (analyst + its critics per scope in gauntlet) and have run a
    session out of budget mid-round. `--force` (with `dbcx status assume`) is the only way past."""
    if "--force" in sys.argv or not os.path.exists(STATUS_PATH): return
    scopes = (read_json(STATUS_PATH) or {}).get("scopes", {}); w = (scopes.get(name) or {}).get("wave")
    if not isinstance(w, int): return
    blocking = sorted(f"{k} ({v.get('status')})" for k, v in scopes.items()
                      if isinstance(v.get("wave"), int) and v["wave"] < w and v.get("status") not in CLOSED_SCOPE_STATES)
    if blocking:
        sys.exit(f"REFUSED: {name} is wave {w}, and an earlier wave is not closed yet: {', '.join(blocking)}. A wave closes "
                 f"(every scope final | failed-gauntlet | skipped) before the next one is rendered or spawned - overlapping "
                 f"waves multiply the live agents and have run a session out of budget mid-round. Finish the wave, or pass "
                 f"--force and record why with `{CLI} status assume <reason>`.")


def brief(cfg, a):
    kind = a[0]
    if kind == "unit": kind = "analyst"
    rnd_any = int(a[a.index("--round") + 1]) if "--round" in a else (int(a[3]) if kind == "critic" and len(a) > 3 and a[3].isdigit() else (int(a[2]) if kind == "gate" and len(a) > 2 and a[2].isdigit() else 0))
    if rnd_any > 1 and "--addendum" not in a and "--no-addendum" not in a and (kind in ("analyst", "inventory", "critic", "consolidate") or ((MET(cfg).get("briefs") or {}).get("extra_kinds") or {}).get(kind, {}).get("gauntlet")):
        sys.exit(f"REFUSED: round {rnd_any} brief without --addendum <file>. What changed since the last round belongs in a file under analysis/briefs/. Pass --no-addendum to state explicitly that nothing beyond the rendered brief is needed.")
    add = render_addendum(a); m = MET(cfg)
    if kind == "analyst":
        name = a[1]; rnd = int(a[a.index("--round") + 1]) if "--round" in a else 0; js, md, skind, role, agent = scope_info(name, m)
        if cfg.get("split") == "none": sys.exit(f"REFUSED: profile {cfg.get('_profile')} runs with split none - no scope analysts; the inventory feeds the consolidations directly ({CLI} status next)")
        if "--conflicts" in a: return conflicts_brief(cfg, name, add), agent, 0
        wave_gate(name)
        parts = [ctx_analyst(cfg, name, rnd), role_text(cfg, "analyst")]
        hs = handover_section(cfg, name); inv = m.get("inventory")
        if inv and inv.get("handover"): parts.append("## HANDOVER – your scope\n" + (hs if hs else f"(no {inv['scope']} claim names {name})") + f"\n\nCross-cutting facts: `{inv['handover']}` → section \"Cross-cutting\" – read there, cite by id.")
        qs = routed_questions(name)
        if qs: parts.append("## QUESTIONS ADDRESSED TO YOUR SCOPE (answer in your analysis where they touch your claims; list the answers in your report as id: answer)\n" + "\n".join(qs))
        lh = lead_block(name, "hints")
        if lh: parts.append(lh)
        parts.append(kb.brief_block("analyst", name, m))
        if os.path.exists(md): parts.append(f"## RESUME NOTE\n`{relp(md, RUN)}` already exists on disk (partial or complete, possibly from an earlier session). Read it first and continue from it – do not restart from zero. Keep the file valid (CHECK) after every section you add.")
        if rnd > 0: parts.append(rework_block(cfg, rnd))
        if add: parts.append(add)
        parts.append(FOLLOW); return "\n\n".join(x for x in parts if x), agent, rnd
    if kind == "inventory":
        rnd = int(a[a.index("--round") + 1]) if "--round" in a else 0; inv = m["inventory"]; js, md, skind, role, agent = scope_info(inv["scope"], m)
        parts = [ctx_inventory(cfg, rnd), role_text(cfg, "inventory")]
        lh = lead_block(inv["scope"], "hints")
        if lh: parts.append(lh)
        parts.append(kb.brief_block("inventory", inv["scope"], m))
        if os.path.exists(md): parts.append(f"## RESUME NOTE\n`{inv['output']}` already exists on disk. Read it first and continue from it.")
        if rnd > 0: parts.append(rework_block(cfg, rnd))
        if add: parts.append(add)
        parts.append(FOLLOW); return "\n\n".join(x for x in parts if x), agent, rnd
    if kind == "critic":
        critic, scope, rnd = a[1], a[2], a[3]; critic = {"client_sa": "client", "platform_sa": "standard", "platform": "standard"}.get(critic, critic); consolidated = is_consolidated(scope, m)
        if critic not in all_critics(cfg): sys.exit(f"unknown critic '{critic}' - this run's critics: {', '.join(cfg['scoring']['critics'])}")
        if critic not in scope_critics(scope, cfg): sys.exit(f"REFUSED: critic '{critic}' does not score {scope} (scoring.phase_critics; critics of this scope: {', '.join(scope_critics(scope, cfg)) or 'none - the deterministic checks decide, see dbcx score_aggregate'})")
        claims_snapshot_gate(scope, rnd, scope_info(scope, m)[1])
        parts = [ctx_critic(cfg, critic, scope, rnd), role_text(cfg, critic_role(critic))]
        if consolidated: parts.append(CONSOLIDATED_SCOPE_RULE)
        lf = lead_block(scope, "facts")
        if lf: parts.append(lf)
        parts.append(kb.brief_block(critic_role(critic), scope, m))
        rp = P("analysis", "gauntlet", scope, f"round{int(rnd) - 1}-result.json")
        disp = [x for x in (load_json(rp, {}).get("routed") or [] if int(rnd) > 1 and os.path.exists(rp) else []) if critic in (x.get("to") or [])]
        if disp: parts.append(f"## DISPUTES ROUTED TO YOU (round {int(rnd) - 1}; the disputing critic's row counted as no score)\nAnswer each in your score row of the claim: confirm the statement with its evidence, or correct the reference row (`{CLI} reference correct ...`) / name the correction in `issue`. Your answer settles the dispute.\n" + "\n".join(f"- {x['claim_id']} (from {x['from']}, ground {x.get('ground')}): {x.get('issue', '')}" + (f" - counter-evidence: {'; '.join(x['counter_evidence'])}" if x.get("counter_evidence") else "") for x in disp))
        parts.append("## THIS ROUND\n" + ("Score every claim in the critic pack." if int(rnd) == 1 else "Score only the claims listed under 'Claims to score'. Re-verify first where the analysis adopted YOUR OWN earlier counter-evidence or fix hints. Carried claims keep their previous score (score_aggregate applies it). Read the REFERENCE DELTA: a carried claim it narrows is re-scored.") + " Missing claims: at most MISSING CLAIMS CAP, most important first. Anything you establish OUTSIDE this scope goes to `Estate observations`.")
        if add: parts.append(add)
        parts.append(FOLLOW); return "\n\n".join(x for x in parts if x), f"critic-{critic}-{scope}", int(rnd)
    if kind == "consolidate":
        which = a[1]; rnd = int(a[a.index("--round") + 1]) if "--round" in a else 0; js, md, skind, role, agent = scope_info(which, m)
        import conflicts
        parts = [ctx_consolidate(cfg, which, rnd), role_text(cfg, "consolidate", which), kb.brief_block("consolidate", which, m), conflicts.consolidator_block(cfg)]
        if os.path.exists(md): parts.append(f"## RESUME NOTE\n`{relp(md, RUN)}` already exists on disk. Read it first and continue from it.")
        if rnd > 0: parts.append(rework_block(cfg, rnd))
        if add: parts.append(add)
        parts.append(FOLLOW); return "\n\n".join(x for x in parts if x), agent, rnd
    if kind == "gate":
        persona, rnd = a[1], int(a[2]); parts = [ctx_gate(cfg, persona, rnd), role_text(cfg, "gate")]
        if rnd > 1: parts += list(previous_round_blocks(cfg, persona, rnd))
        if add: parts.append(add)
        parts.append(FOLLOW); return "\n\n".join(x for x in parts if x), f"gate-{persona}", rnd
    if kind == "verifier":
        rnd = int(a[1]); parts = [ctx_verifier(cfg, rnd), role_text(cfg, "verifier")]
        if add: parts.append(add)
        parts.append(FOLLOW); return "\n\n".join(x for x in parts if x), "gate-verifier", rnd
    if kind == "editor":
        rnd = int(a[1]); parts = [ctx_editor(cfg, rnd), role_text(cfg, "editor")]
        if add: parts.append(add)
        parts.append(FOLLOW); return "\n\n".join(x for x in parts if x), "deliverable-editor", rnd
    xk = (m.get("briefs") or {}).get("extra_kinds") or {}
    if kind in xk and xk[kind].get("gauntlet"): return extra_gauntlet_brief(cfg, kind, xk[kind], a, add)
    if kind in xk: return extra_kind_brief(cfg, kind, xk[kind], add), xk[kind]["agent"], 0
    if kind == "postpass": return postpass_brief(cfg, a[1], add), f"postpass-{a[1]}", 0
    if kind == "progress": return progress_brief(cfg, add), "progress-reporter", 0
    if kind == "research": return "\n\n".join(x for x in [research(cfg), role_text(cfg, "research"), add, FOLLOW] if x), "researcher", 0
    sys.exit("unknown brief kind (analyst | inventory | consolidate | critic | gate | verifier | editor | postpass | progress | research" + "".join(f" | {k}" for k in xk) + ")")

def extra_kind_brief(cfg, kind, spec_, add=""):
    """a method brief kind (method.json briefs.extra_kinds.<kind> = {role, agent, model, text}): the agent `agent` (its name maps to the
    engine role and so to that role's evidence bases), the model key `model`, the role text methods/<m>/briefs/<text>.md and the method's
    briefing.extra(<kind>, None, cfg, 0) rows and blocks"""
    rows = [("TASK", kind), ("AGENT NAME", spec_["agent"])] + model_rows(cfg, spec_.get("model") or spec_["role"]) + helper_rows(cfg) + common_rows(cfg, spec_["role"])
    xr, xb = extra(cfg, kind, None, 0)
    return "\n\n".join(x for x in [block("CONTEXT", rows + xr)] + xb + [role_text(cfg, spec_.get("text") or kind), add, FOLLOW] if x)

def extra_gauntlet_brief(cfg, kind, spec_, a, add=""):
    """a method brief kind with a gauntlet (briefs.extra_kinds.<kind>.gauntlet, common.extra_gauntlet): `dbcx render brief <kind> [<scope>]
    [--round n]` - the scope defaults to gauntlet.scope (a part: <scope>-<n>); the engine adds TEMPLATE, OUTPUT, CHECK, ROUND, FIX LIST and the
    quote rule, the method's briefing.extra(<kind>, <scope>, cfg, rnd) its rows and blocks; a rework round gets the engine's rework block"""
    from common import extra_gauntlet
    pos = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] not in ("--round", "--addendum", "--out")]
    scope = pos[0] if pos else spec_["gauntlet"]["scope"]; xg = extra_gauntlet(scope, MET(cfg))
    if not xg or xg[0] != kind: sys.exit(f"REFUSED: {scope} is no scope of the brief kind {kind} ({spec_['gauntlet']['scope']} or {spec_['gauntlet']['scope']}-<n>)")
    rnd = int(a[a.index("--round") + 1]) if "--round" in a else 0; js, md, skind, role, agent = scope_info(scope, MET(cfg)); out = relp(md, RUN).replace(os.sep, "/")
    rows = [("TASK", kind), ("SCOPE", scope), ("AGENT NAME", agent)] + model_rows(cfg, spec_.get("model") or spec_["role"]) + helper_rows(cfg) + common_rows(cfg, spec_["role"], agent) + [
            ("REFERENCE", rel_ref()), ("TEMPLATE", template_of(cfg, kind)), ("OUTPUT", out), ("CHECK", f"{CLI} md_to_json {kind} {out}"), ("ROUND", rnd or 0),
            ("FIX LIST", f"analysis/gauntlet/{scope}/round{rnd - 1}-issues.md" if rnd > 0 else "")] + quote_rows(cfg)
    xr, xb = extra(cfg, kind, scope, rnd)
    parts = [block("CONTEXT", rows + xr)] + xb + [role_text(cfg, spec_.get("text") or kind)]
    if os.path.exists(md): parts.append(f"## RESUME NOTE\n`{out}` already exists on disk. Read it first and continue from it.")
    if rnd > 0: parts.append(rework_block(cfg, rnd))
    return "\n\n".join(x for x in parts + [add, FOLLOW] if x), agent, rnd

def conflicts_brief(cfg, name, add=""):
    """the short continuation brief of an owning analyst - the CONFLICTS TO RESOLVE block of `dbcx conflicts route`"""
    import conflicts
    blk = conflicts.route_block(name, cfg)
    if not blk: sys.exit(f"REFUSED: no open conflict is routed to {name} ({CLI} conflicts route)")
    m = MET(cfg); js, md, kind, role, agent = scope_info(name, m); light = is_light(name) or name in cfg.get("models", {}).get("analyst_light_scopes", [])
    rows = [("SCOPE", name), ("AGENT NAME", agent), ("TASK", "conflict resolution (continuation of your analysis - nothing else changes)")] + model_rows(cfg, "analyst_light" if light else "analyst") + common_rows(cfg, "analyst") + [
            ("REFERENCE", rel_ref()), ("OUTPUT", relp(md, RUN)), ("CHECK", f"{CLI} md_to_json {kind} {relp(md, RUN).replace(os.sep, '/')}")] + quote_rows(cfg)
    return "\n\n".join(x for x in [block("CONTEXT", rows), blk, kb.brief_block("analyst", name, m), add, FOLLOW] if x)

def postpass_brief(cfg, scope, add=""):
    m = MET(cfg); js, md, kind, role, owner = scope_info(scope, m); ana = relp(md, RUN)
    gd = P("analysis", "gauntlet", scope); notes = []; rounds = sorted(int(mm.group(1)) for f in os.listdir(gd) for mm in [re.match(r"round(\d+)-result\.json", f)] if mm) if os.path.isdir(gd) else []
    if rounds:
        res = load_json(os.path.join(gd, f"round{rounds[-1]}-result.json"), {})
        notes = [f"- [{n['critic']}] {n['claim_id']} (scored {n['score']}){' OWED TEXT FIX' if n.get('owed') else ''}: {n['issue']}" + (f" - hint (hypothesis): {n['fix_hint']}" if n.get('fix_hint') else "") + (f" - keep: {n['accept_if']}" if n.get('accept_if') else "") for n in res.get("notes_on_passing_claims", [])]
    st = load_json(STATUS_PATH, {"open_issues": []}); issues = [f"- #{i['id']}: {i['text']}" for i in st.get("open_issues", []) if i.get("status") == "open" and i.get("scope") in (scope, owner)]
    if os.path.exists(js):   # the rows before this post-pass, for the corrections log and the unverified-locator list
        import postpass; postpass.baseline(scope)
    jf = f"analysis/gauntlet/{scope}/postpass-justifications.md"
    rows = [("FILE (the ONLY file you edit - the analysis, never the register under analysis/gauntlet/)", ana), ("SCOPE", scope), ("AGENT NAME", f"postpass-{scope}")] + model_rows(cfg, "postpass") + [
            ("JUSTIFICATIONS (one row per changed claim; template templates/postpass-justifications.md; append, never delete)", jf),
            ("CHECK (both must say OK)", f"{CLI} md_to_json {kind} {ana} && {CLI} postpass check {scope}"),
            ("REGISTER (frozen, write-protected - ids and count must stay byte-identical; read it, never edit it)", f"analysis/gauntlet/{scope}/claims.md"), ("CROSS-SCOPE SWEEP", f"{CLI} grep_scopes \"<old figure or phrase>\""),
            ("REPORT", "in your FINAL RESPONSE (you have no send operation; the orchestrator reads your final message)")] + common_rows(cfg, "postpass")
    parts = [block("CONTEXT", rows), role_text(cfg, "postpass"), "## ITEMS (notes on passing claims and owed text fixes from the last aggregated round)\n" + ("\n".join(notes) if notes else "(none recorded by score_aggregate - the orchestrator lists the items in the addendum)"), "## OPEN STATUS ISSUES FOR THIS SCOPE\n" + ("\n".join(issues) if issues else "(none)")]
    if add: parts.append(add)
    parts.append(FOLLOW); return "\n\n".join(x for x in parts if x)

def progress_brief(cfg, add=""):
    rows = [("AGENT NAME", "progress-reporter")] + model_rows(cfg, "progress") + [("PROGRESS JSON (computed, read first)", f"state/PROGRESS.json  ({CLI} progress)"), ("INTERIM DELIVERABLES (team-only)", f"work/interim/<latest date>/  ({CLI} build_excel --all --interim)"), ("INPUTS", "state/STATUS.json, state/PROGRESS.json, analysis/gauntlet/*/round*-result.json, the scope / consolidation JSONs (passed claims only), analysis/consolidated/estate_observations.json, state/QUESTIONS.json (client questions, assumptions, trade-offs; `" + CLI + " questions list --json`), docs/LEARNINGS.md"), ("OUTPUT", "docs/PROGRESS_REPORT.md (Markdown only - the live dashboard `" + CLI + " dashboard` renders it; no HTML)"), ("NEVER READ", "the client's evidence bases (code, corpus, workbooks) - you report state, you do not analyse")]
    return "\n\n".join(x for x in [block("CONTEXT", rows), role_text(cfg, "progress"), add, FOLLOW] if x)

# ------------------------------------------------------------------ run documents
def reference_text(cfg):
    packs = packs_of(cfg) + extra_option_packs(cfg)
    parts = [f"# Reference – verified standard facts for this engagement (knowledge packs: {', '.join(pk['name'] for pk in packs) or 'none'})", "", "Working notes for analysts and the standard critic. Items marked *(verify)* come from the knowledge packs' seeds and must be confirmed against current documentation for THIS engagement's versions/plans (research step: `" + CLI + " render brief research --out`). Verified facts go to section 7 with URL and date; `" + CLI + " learn export` carries them to the plugin maintainer for the next engagement. Shared by every run of this engagement folder.", ""]
    for pk in packs:
        for fn, title in ((pk.get("research_seed", "research-seed.md"), "Seed"), (pk.get("reference_cache", "reference-cache.md"), "Verified facts cache")):
            fp = os.path.join(pk["_dir"], fn)
            if os.path.exists(fp): parts += ["---", f"## {title} – {pk.get('kind')} pack `{pk['name']}` ({pk.get('_slot')})", "", open(fp, encoding="utf-8").read().strip(), ""]
    parts += ["---", f"## 7. Verified facts (appended ONLY via `{CLI} reference add ...` by the standard critic and the researcher; cite rows by Id, never by line number)", "| Id | Fact | Applies to (version) | URL | Date | Provenance | Affects claims |", "|---|---|---|---|---|---|---|", ""]
    return "\n".join(parts)

def package_inside_project():
    return os.path.abspath(PLUGIN).startswith(os.path.abspath(PROJECT_DIR) + os.sep)

def package_ref(base=None):
    """How the wrappers name the package: a relative path while it is vendored inside the engagement, otherwise the installed plugin (no home paths in client-facing wrappers)."""
    if package_inside_project(): return "`" + relp(PLUGIN, base or RUN) + "`"
    return "the installed `dbcx-agentic-loop` plugin (`dbcx plugin-root` prints its path)"

def invoke_text(base=None):
    if package_inside_project():
        package = relp(PLUGIN, base or RUN)
        return f"invoke `{package}/scripts/dbcx <tool>`"
    return "invoke `dbcx <tool>` - the plugin's launcher `<plugin-root>/scripts/dbcx`, run by its quoted absolute path (the dbcx skill and the SessionStart hook name it; it is not on PATH)"

def instruction_core(cfg):
    m = MET(cfg); selected = {key: S(cfg, key) for key in ("orchestrator", "analyst", "analyst_light", "critic_client", "critic_standard", "critic_standard_consolidation", "consolidator", "gate", "helper")}
    model_text = ", ".join(f"{key}={value.profile}" for key, value in selected.items())
    project = relp(PROJECT_DIR, RUN)
    return f"""# {cfg['engagement'].get('client', '')} – {cfg['engagement'].get('run_title') or m.get('display', '')} ({cfg['engagement'].get('consultancy', '')})

This folder is one **dbcx-agentic-loop** run, method **{m['name']}**. The portable package is {package_ref()} and the shared engagement folder is `{project}`. Disk state is authoritative.

- Invocation: "Execute the plan" runs `docs/PLAN.md`; "Prepare the run", "Show progress", and "Resume the run" map to the portable `dbcx-agentic-loop` skill. Resume with `{CLI} status verify`, then `{CLI} status next`.
- Tools: run `{CLI} <tool>` through the portable package launcher. `{CLI} help` lists engine and method tools; `{CLI} doctor` is read-only.
- Agents: every role starts from a rendered brief file created by `{CLI} render brief ... --out`. Pass the brief's MODEL and record delivery in shared state; conversation ids are disposable.
- Models: {model_text}. Rendered briefs resolve the model alias and reasoning effort; overrides belong in `model_overrides` and semantic role profiles stay unchanged.
- Evidence: `{CLI} evidence bases` defines read-only, role-scoped bases. Never build, start, initialize, or modify client evidence. Client names, non-public scope names, internal paths, corpus locators, handover locators, and client code never enter external queries.
- Web research: restricted roles use `{CLI} safe_web`, never hosted search, because only the local command is hook-visible. Standard critics and researchers stay outside client evidence bases.
- Formats: Markdown analyses convert through `{CLI} md_to_json`; client workbooks are built only through `{CLI} build_excel`; scores and recorded checksums are never edited by hand.
- State and control: `state/STATUS.json`, `state/QUESTIONS.json`, `state/KNOWLEDGE.json`, `state/INBOX.jsonl`, and `state/CONTROL.json` are canonical. The dashboard is best-effort UI; pause, checkpoint, and resume correctness does not depend on a UI wake mechanism.
- Rules: one scope per agent; every critic of a round uses one recorded model policy; only the orchestrator writes shared files and deliverables; questions receive proposed answers and execution continues under the recommendation; client-facing files contain no process/version language.
- Handoff: `{CLI} handoff check` is read-only; `{CLI} handoff prepare` refuses incomplete critic sets and writes `docs/RESUME.md`; the next session uses `{CLI} handoff accept` idempotently.
- Rollback: run state is never copied or reset. Repoint to the original package documented in `work/migration/ROLLBACK.md`.
""".replace(CLI, "dbcx")   # wrapper files travel with the folder: no machine path (the skill and the SessionStart hook name the launcher)

def instruction_agents():
    return f"""## Claude Code agents

Read this `CLAUDE.md`, use `{AGENT_PREFIX}<role>` agents, and spawn with Agent, continue with SendMessage, stop with TaskStop. Invoke the plugin skill or use the same natural-language commands. Claude web-query hooks remain enforced; restricted roles should still prefer `{CLI} safe_web` for parity.
""".replace(CLI, "dbcx")   # wrapper files travel with the folder: no machine path (the skill and the SessionStart hook name the launcher)

def instructions_md(cfg):
    return instruction_core(cfg) + "\n" + instruction_agents()

def engagement_instruction_core(cfg):
    run = relp(RUN, PROJECT_DIR)
    package = package_ref(PROJECT_DIR)
    client = cfg.get("engagement", {}).get("client", "")
    title = cfg.get("engagement", {}).get("run_title") or MET(cfg).get("display", "")
    return f"""# {client} – {title} engagement

This is a **dbcx-agentic-loop engagement**. The portable package is {package}; the active run is `{run}`. Disk state is authoritative. Read `docs/ENGAGEMENT.md` for the engagement scope, frozen evidence, decisions, and deliverable map.

- Work from `{run}` and {invoke_text(PROJECT_DIR)}.
- "Execute the plan", "Prepare the run", "Show progress", and "Resume the run" map to the portable `dbcx-agentic-loop` skill. Resume with `dbcx status verify`, then `dbcx status next`.
- Never initialize, build, start, pull, or modify the frozen client repository. Evidence bases are read-only and role-scoped.
- Never place the client name, non-public scope names, internal paths, corpus/handover locators, or client code in an external query. Restricted research roles use `dbcx safe_web`, not hosted search.
- All roles start from rendered brief files. Use their MODEL; correctness and handoff depend on files and checksums, not conversation ids.
- Use `dbcx handoff check|prepare|accept` when another session, machine or colleague takes over; never switch midway through a critic round.
- Claude Code loads the skill, the agents and the hooks from the installed `dbcx-agentic-loop` plugin; the engagement folder carries no plugin files.
- Rollback repoints package references only; it never copies or resets run state. See `work/migration/ROLLBACK.md`.
""".replace(CLI, "dbcx")   # wrapper files travel with the folder: no machine path (the skill and the SessionStart hook name the launcher)

def engagement_instructions_md(cfg):
    return engagement_instruction_core(cfg) + "\n" + instruction_agents()

def claude_md(cfg):
    return instructions_md(cfg)

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cfg = project(); force = "--force" in a; a = [x for x in a if x != "--force"]
    cmd = a[0]
    if cmd in ("instructions", "claude"): write("CLAUDE.md", instructions_md(cfg), force)
    elif cmd == "engagement-instructions": write(PP("CLAUDE.md"), engagement_instructions_md(cfg), force)
    elif cmd == "plan":
        pp = os.path.join(MET(cfg)["_dir"], "plan.md")
        if not os.path.exists(pp): sys.exit(f"method {MET(cfg)['name']} has no plan.md")
        write("docs/PLAN.md", fmt(open(pp, encoding="utf-8").read(), cfg, plugin=package_ref(), tools=os.path.join(package_ref(), "engine", "tools"), run=".", project=relp(PROJECT_DIR, RUN)), force)
    elif cmd == "reference": write(os.path.join(REF_DIR, "platform-standard.md"), reference_text(cfg), force)
    elif cmd == "handover": write(MET(cfg)["inventory"]["handover"], handover_text(cfg), force)
    elif cmd == "research": print(cli_text(research(cfg)))
    elif cmd == "snippets": print(json.dumps(snippets(cfg), indent=1, ensure_ascii=False))
    elif cmd == "digest": digest(cfg, a[1])
    elif cmd == "brief":
        args = a[1:]; txt, name, rnd = brief(cfg, args)
        import retrieval; txt = cli_text(retrieval.brief_blocks(cfg, txt, name))   # HOW TO FIND EVIDENCE + SOURCES FOR THIS UNIT (corpus readers only)
        if "--out" in args:
            i = args.index("--out"); custom = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("--") else None
            rel = custom or os.path.join("analysis", "briefs", f"{name}{('-r' + str(rnd)) if str(rnd) not in ('', '0') else ''}{'-conflicts' if '--conflicts' in args else ''}.md")
            p = rel if os.path.isabs(rel) else P(rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(txt + "\n")
            model = re.search(r"^MODEL: (\S+)", txt, re.M)
            def field(name):
                match = re.search(r"^" + re.escape(name) + r": (.+)$", txt, re.M)
                return match.group(1).strip() if match else ""
            meta = {"agent": name, "round": rnd, "brief": relp(p, RUN), "sha256": hashlib.sha256(txt.encode()).hexdigest(), "harness": field("HARNESS"), "provider": field("PROVIDER"), "model": field("MODEL"), "reasoning_effort": field("REASONING EFFORT"), "profile": field("MODEL PROFILE")}
            if NOTES_USED: meta["project_notes"] = NOTES_USED
            open(os.path.splitext(p)[0] + ".meta.json", "w", encoding="utf-8").write(json.dumps(meta, indent=2) + "\n")
            # a round-n continuation reaches its agent through SendMessage, which no hook sees;
            # every continuation starts with this render, so the render re-registers the agent as running for that round.
            if args[0] in ("analyst", "unit", "inventory", "consolidate") and str(rnd) not in ("", "0") and int(rnd) >= 2 and os.path.exists(STATUS_PATH):
                import subprocess, common as _common
                out_f = field("OUTPUT").split()[0] if field("OUTPUT") else ""
                entry = {"agent": name, "model": field("MODEL"), "provider": field("PROVIDER"), "harness": field("HARNESS"), "reasoning_effort": field("REASONING EFFORT"), "role": _common.role_of_agent(name, MET(cfg)), "subagent_type": "", "conversation_id": "",
                         "brief_path": relp(p, RUN), "brief_sha256": meta["sha256"], "addendum_path": (args[args.index("--addendum") + 1] if "--addendum" in args else ""), "output_files": [out_f] if out_f else [], "check_cmd": field("CHECK").split("  (")[0], "round": int(rnd),
                         "registered_by": "render brief (round continuation; SendMessage is not hook-visible)", "on_delivery": "convert with check_cmd (once) after the agent's REPORT arrived - a file is not a delivery signal - then continue per `dbcx status next`", "respawn": "re-spawn the role with the same brief path (a RESUME NOTE continues the file)"}
                subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "inflight", "add", json.dumps(entry)], cwd=RUN, capture_output=True, text=True)
                print(f"in_flight += {name} (round {rnd} continuation registered by this render; cleared by the delivery test or `{CLI} status inflight done {name}` once the REPORT has arrived)")
            print(f"wrote {relp(p, RUN)} ({len(txt)} bytes, sha256 {hashlib.sha256(txt.encode()).hexdigest()[:12]}); MODEL {model.group(1) if model else '?'}; agent name {name}")
            print(f"spawn prompt: 'Your brief is the file {relp(p, RUN).replace(os.sep, '/')} - read it completely first. Follow your agent definition.'  (model={model.group(1) if model else '?'}, name={name})")
        else: print(txt)
    elif cmd == "context":
        kind = a[1]
        if kind == "inventory": print(cli_text(ctx_inventory(cfg)))
        elif kind in ("analyst", "unit"): print(cli_text(ctx_analyst(cfg, a[2], a[a.index("--round") + 1] if "--round" in a else 0)))
        elif kind == "consolidate": print(cli_text(ctx_consolidate(cfg, a[2])))
        elif kind == "critic": print(cli_text(ctx_critic(cfg, {"client_sa": "client", "platform_sa": "standard"}.get(a[2], a[2]), a[3], a[4])))
        elif kind == "gate": print(cli_text(ctx_gate(cfg, a[2], a[3])))
        elif kind == "verifier": print(cli_text(ctx_verifier(cfg, a[2])))
        elif kind == "editor": print(cli_text(ctx_editor(cfg, a[2])))
        else: sys.exit("unknown context kind")
    else: sys.exit("unknown command")

if __name__ == "__main__":
    main()
