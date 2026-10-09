#!/usr/bin/env python3
"""Conflict register: cross-scope disagreements - two analyses (or an analysis and the
inventory) stating different facts about the same thing - found by the method's detector and resolved where the evidence is, before a
consolidator would have to guess. analysis/consolidated/CONFLICTS.json is the register (written only by this tool, orchestrator only - hook H9).
The method hook methods/<m>/conflicts.py `detect(scopes, cfg) -> [{id, kind, subject, sides: [{scope, claim, value}]}]` (scopes = {name: the
converted scope analysis}; `id` a stable key per kind + subject). A method without the hook has no register: the feature is inactive.

Usage: dbcx conflicts detect                      run the detector, merge into the register (idempotent: a conflict keeps its id CF-nnn and its
                                                  resolution; one no longer detected while open becomes `cleared`, one detected again re-opens)
       dbcx conflicts list [--open]               the register, one line per conflict
       dbcx conflicts show CF-n                   one conflict as JSON
       dbcx conflicts route                       profile full: the open conflicts per owning analyst (a side's scope with an analysis) -> the
                                                  render commands of the short continuation briefs (`dbcx render brief analyst <scope> --conflicts --out`)
       dbcx conflicts resolve CF-n --claim <claim id> --by <scope> [--text "<one statement>"] [--topic T --topic-summary S]
                                                  the owning analyst settled it with a claim of its analysis (converted, with a verbatim `quote` the
                                                  quote gate finds offline) -> resolved + knowledge-base entry cross-scope-finding (by orchestrator,
                                                  weight proposal, applies_to = the sides' scopes; fewer than two -> + the consolidations)
       dbcx conflicts undecidable CF-n --reason "..." [--by <scope>] [--question "..."] [--effect "..."]
                                                  no document settles it -> a client question (kind client_question, one option per side, id
                                                  Q-<scope>-CF-n; human_input.release batched stores it unreleased like every new question)
       dbcx conflicts skip [CF-n] --reason "..."  the orchestrator lets the consolidation start with the conflict(s) open (recorded)
`dbcx status next` (profile full, split by_scope): before a consolidation phase starts it runs `detect` and holds the phase while a conflict is
open. Profile lean (split none): no routing and no hold - the register is a checklist block in the consolidator brief.
"""
import os, re, sys, json, time, glob, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, CLI, TOOLS, STATUS_PATH, load_json, save_json, method, project, scope_info, load_method_module, labels, relp

PATH = P("analysis", "consolidated", "CONFLICTS.json"); REL = "analysis/consolidated/CONFLICTS.json"
TOPIC = ("conflict-resolutions", "cross-scope disagreements the owning analysts settled from the evidence (dbcx conflicts)")
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def opt(a, k, d=""): return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
def hook(): mod = load_method_module("conflicts"); return mod if mod and hasattr(mod, "detect") else None
def load(): return load_json(PATH, {}) if os.path.exists(PATH) else {}
def find(reg, cid): return next((c for c in reg.get("conflicts", []) if c["id"] == cid), None) or sys.exit(f"no such conflict {cid} ({CLI} conflicts list)")
def live(reg): return [c for c in reg.get("conflicts", []) if c["status"] != "cleared"]
def open_ones(reg): return [c for c in reg.get("conflicts", []) if c["status"] == "open"]
def resolved_claims(scope):
    """{claim id: resolution} of the conflicts `scope` resolved - a claim added after the scope's gauntlet (Claims sheet, dashboard)"""
    return {c["resolution"]["claim"]: c["resolution"] for c in load().get("conflicts", []) if c["status"] == "resolved" and c["resolution"].get("by") == scope}
def side_line(s, claim=" (claim {claim})"): return f"{s['scope']}: {s['value']}" + (claim.format(claim=s["claim"]) if s.get("claim") else "")

def analyses(cfg):
    """{scope: converted analysis} - none under split none (profile lean has no scope analyses)"""
    if cfg.get("split") == "none": return {}
    m = cfg["_method"]; return {os.path.basename(f)[:-5]: load_json(f, {}) for f in sorted(glob.glob(P(m["scopes"].get("output_dir", "analysis/scopes"), "*.json")))}

def detect(cfg=None, quiet=False):
    """merge the hook's findings into the register; None when the method has no hook"""
    mod = hook()
    if not mod: return None
    cfg = cfg or project(); reg = load() or {"conflicts": []}; t = now()
    found = mod.detect(analyses(cfg), cfg) or []; keys = set(); by = {c["key"]: c for c in reg["conflicts"]}
    for d in found:
        key = d.get("id") or f"{d['kind']}|{d['subject']}"; keys.add(key); c = by.get(key)
        if c is None:
            n = max([int(x["id"][3:]) for x in reg["conflicts"]] + [0]) + 1
            c = {"id": f"CF-{n:03d}", "key": key, "status": "open", "detected_at": t}; reg["conflicts"].append(c); by[key] = c
        elif c["status"] == "cleared": c["status"] = "open"; c.pop("cleared_at", None)
        c.update({"kind": d["kind"], "subject": d["subject"], "sides": d["sides"], "updated_at": t})
    for c in reg["conflicts"]:
        if c["key"] not in keys and c["status"] == "open": c.update({"status": "cleared", "cleared_at": t, "updated_at": t})
    reg.update({"method": cfg["_method"]["name"], "profile": cfg.get("_profile") or "full", "detected_at": t}); save_json(PATH, reg)
    if not quiet: print(f"{REL}: {len(found)} conflict(s) detected, {len(open_ones(reg))} open" + "".join(f"\n  {c['id']} [{c['kind']}] {c['subject']} - {c['status']}" for c in live(reg)))
    return reg

def owners(c, cfg):
    """the sides' scopes an analyst owns (a scope analysis, not skipped) - the inventory and the consolidations are no routing target"""
    st = load_json(STATUS_PATH, {"scopes": {}}).get("scopes", {}); js = set() if cfg.get("split") == "none" else {os.path.basename(f)[:-5] for f in glob.glob(P(cfg["_method"]["scopes"].get("output_dir", "analysis/scopes"), "*.json"))}
    return list(dict.fromkeys(s["scope"] for s in c["sides"] if s["scope"] in js and (st.get(s["scope"]) or {}).get("status") != "skipped"))

def status_step(ph, cfg):
    """`dbcx status next` before a consolidation phase starts: True = hold (profile full while a conflict is open)"""
    reg = detect(cfg, quiet=True)
    if reg is None: return False
    op = open_ones(reg)
    if cfg.get("split") == "none":
        if live(reg): print(f"CONFLICTS (checklist, split none - no routing): {len(live(reg))} in {REL} - the consolidator brief lists them")
        return False
    if not op: return False
    print(f"NEXT: conflicts before {ph['id']} - {len(op)} open conflict(s) in {REL}: " + "; ".join(f"{c['id']} [{c['kind']}] {c['subject']}" for c in op))
    print(f"  DO: {CLI} conflicts route -> per owning analyst {CLI} render brief analyst <scope> --conflicts --out; continue the running analyst with that brief (SendMessage; {CLI} kb pending <agent> into the same message) or spawn it with the brief if it is gone")
    print(f"  ON REPORT: {CLI} md_to_json (CHECK line of the brief); per conflict {CLI} conflicts resolve <CF> --claim <claim id> --by <scope> | {CLI} conflicts undecidable <CF> --reason \"...\" --by <scope> (-> client question); no owning analyst or no time: {CLI} conflicts skip [<CF>] --reason \"...\"")
    return True

def route_block(scope, cfg, reg=None):
    """the CONFLICTS TO RESOLVE block of the short analyst continuation brief ("" when nothing is open for the scope)"""
    reg = reg if reg is not None else load(); mine = [c for c in open_ones(reg) if scope in owners(c, cfg)]
    if not mine: return ""
    out = [f"## CONFLICTS TO RESOLVE ({REL} - the consolidation waits for your answers)",
           "Your analysis and another source state different facts about the same thing. Resolve each where the evidence is: re-read the locators of EVERY side (EVIDENCE BASES) and the other side's analysis row - reading the files named below is allowed for this task.", ""]
    for c in mine:
        out.append(f"- **{c['id']}** [{c['kind']}] {c['subject']}")
        out += [f"  - {'YOU - ' if s['scope'] == scope else ''}{side_line(s)}" + ("" if s["scope"] == scope else f" [{relp(scope_info(s['scope'])[1], ROOT)}]") for s in c["sides"]]
    out += ["", "Per conflict, exactly one of:",
            "1. **Resolved** - a document settles it: ONE claim in your analysis's Claims table (type fact; a new id, or an existing claim you correct) that states the settled value, its `evidence` the locator(s) that settle it, its `quote` a verbatim excerpt (>= 20 characters, original language) from one of them - `dbcx conflicts resolve` checks it word for word and refuses a quote it does not find. Correct your own row where it was the wrong side (sweep its other homes); never edit another scope's file - say in the report what the other side has wrong.",
            "2. **Undecidable** - no document settles it (both sides are evidenced, or the only source is `visual, unverified`): no claim; one line with the reason. It becomes a client question.",
            "Keep `round:` and `status:` of your file unchanged. Run the CHECK, then SEND your report: one line per conflict, `CF-n: resolved by C-<scope>-nnn` or `CF-n: undecidable - <reason>`."]
    return "\n".join(out)

def consolidator_block(cfg, reg=None):
    """the CONFLICTS block of every consolidator brief ("" without a register or without a live conflict - byte-identical otherwise)"""
    reg = reg if reg is not None else load(); cs = live(reg)
    if not cs: return ""
    lean = cfg.get("split") == "none"
    out = [f"## CONFLICTS ({REL}; " + ("checklist from the method's detector - you read the corpus in this run: settle each from the documents with a claim, locator and quote, or keep it open with a client question; never pick a side without a document)" if lean else
           "cross-scope disagreements the owning analysts resolved from the evidence - adopt each outcome, do not re-decide it; cite the resolving claim or the client question)")]
    for c in cs:
        r = c.get("resolution") or {}; u = c.get("undecidable") or {}
        if c["status"] == "resolved": what = f"RESOLVED by {r['by']} with {r['claim']}: \"{r['statement']}\" (quote {r['quote_check']}" + (f" at {', '.join(r['at'])}" if r.get("at") else "") + (f"; {r['kb']}" if r.get("kb") else "") + ") - write the row with this value"
        elif c["status"] == "undecidable": what = f"UNDECIDABLE ({u['reason']}) - client question {u['question']}: keep both sides with their claims, cite the question, never pick a side"
        elif c["status"] == "skipped": what = f"NOT RESOLVED (skipped: {c.get('skip_reason', '')}) - both sides stand: report the disagreement, raise the question"
        else: what = "OPEN - settle it from the documents or raise a client question" if lean else "OPEN - both sides stand: report the disagreement, raise the question"
        out.append(f"- **{c['id']}** [{c['kind']}] {c['subject']}: {what}")
        out += [f"  - {side_line(s)}" for s in c["sides"]]
    return "\n".join(out)

def claim_of(scope, cid):
    js = scope_info(scope)[0]
    if not os.path.exists(js): sys.exit(f"REFUSED: {relp(js, ROOT)} missing - convert the analysis first ({CLI} md_to_json)")
    return next((x for x in (load_json(js, {}) or {}).get("claims", []) if x.get("id") == cid), None) or sys.exit(f"REFUSED: {cid} is no claim of {relp(js, ROOT)} - convert the analysis after the analyst's report ({CLI} md_to_json)")

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]; cfg = project()
    if not hook(): sys.exit(f"method {cfg['_method']['name']} has no conflict detector (methods/<m>/conflicts.py) - the register is inactive")
    if cmd == "detect": detect(cfg); return
    reg = load()
    if not reg: sys.exit(f"no {REL} yet - `{CLI} conflicts detect`")
    if cmd == "list":
        cs = open_ones(reg) if "--open" in a else reg["conflicts"]
        for c in cs: print(f"{c['id']} [{c['kind']}] {c['subject']} - {c['status']}" + (f" -> {c['resolution']['claim']}" if c.get("resolution") else "") + (f" -> {c['undecidable']['question']}" if c.get("undecidable") else ""))
        print(f"{len(cs)} conflict(s), {len(open_ones(reg))} open")
    elif cmd == "show": print(json.dumps(find(reg, a[1]) if len(a) > 1 else sys.exit("show CF-n"), indent=1, ensure_ascii=False))
    elif cmd == "route":
        if cfg.get("split") == "none": sys.exit(f"REFUSED: profile {cfg.get('_profile')} runs with split none - no owning analysts; the consolidator brief carries the register as a checklist")
        per = {}; t = now(); orphans = []
        for c in open_ones(reg):
            o = owners(c, cfg); c.update({"routed_to": o, "routed_at": t}) if o else orphans.append(c["id"])
            for s in o: per.setdefault(s, []).append(c["id"])
        save_json(PATH, reg)
        for s, ids in per.items(): print(f"{s}: {', '.join(ids)} -> {CLI} render brief analyst {s} --conflicts --out")
        if orphans: print(f"no owning analyst (every side is the inventory or a skipped scope): {', '.join(orphans)} -> {CLI} conflicts undecidable <CF> --reason \"...\" (client question) or {CLI} conflicts skip <CF> --reason \"...\"")
        if not per and not orphans: print("no open conflict")
    elif cmd == "resolve":
        c = find(reg, a[1] if len(a) > 1 else ""); cid = opt(a, "--claim"); by = opt(a, "--by")
        if c["status"] not in ("open", "skipped"): sys.exit(f"REFUSED: {c['id']} is {c['status']}")
        if not cid or not by: sys.exit("REFUSED: --claim <claim id> --by <scope>")
        if by not in [s["scope"] for s in c["sides"]]: sys.exit(f"REFUSED: {by} is no side of {c['id']} ({', '.join(s['scope'] for s in c['sides'])})")
        import evidence, kb
        cl = claim_of(by, cid); qc = evidence.quote_check(cl, cfg, offline=True)
        if qc["status"] not in ("verified", "partial"): sys.exit(f"REFUSED: the quote of {cid} is {qc['status']}" + (f" ({'; '.join(qc.get('unreadable') or qc.get('missing') or [])})" if qc.get("unreadable") or qc.get("missing") else "") + " - a resolution rests on a verbatim quote the tool finds in a cited locator (send it back to the analyst)")
        k = kb.load(); applies = list(dict.fromkeys(s["scope"] for s in c["sides"]))
        if len(applies) < 2: applies += [x for x in cfg["_method"].get("consolidations") or {} if x not in applies]
        tp, ts = opt(a, "--topic", TOPIC[0]), opt(a, "--topic-summary", TOPIC[1] if opt(a, "--topic", TOPIC[0]) == TOPIC[0] else "")
        t = now(); e = kb.add_entry(k, opt(a, "--text") or f"{c['subject']}: {cl['statement']}", tp, applies, "cross-scope-finding", "proposal", "orchestrator",
                                    {"kind": "finding", "ref": cid, "by": by, "at": t, "conflict": c["id"]}, "" if tp in (k.get("topics") or {}) else ts)
        kb.save(k)
        c.update({"status": "resolved", "updated_at": t, "resolution": {"claim": cid, "by": by, "statement": cl["statement"], "quote": cl.get("quote", ""), "quote_check": qc["status"], "at": qc.get("at", []), "kb": e["id"], "resolved_at": t}})
        save_json(PATH, reg); print(f"{c['id']}: resolved by {by} with {cid} (quote {qc['status']}) -> {e['id']} [cross-scope-finding · proposal, applies to {', '.join(applies)}]")
    elif cmd == "undecidable":
        c = find(reg, a[1] if len(a) > 1 else ""); why = opt(a, "--reason")
        if c["status"] not in ("open", "skipped"): sys.exit(f"REFUSED: {c['id']} is {c['status']}")
        if not why: sys.exit("REFUSED: --reason \"what no document settles\"")
        frm = opt(a, "--by") or next(iter(owners(c, cfg)), c["sides"][0]["scope"]); qid = f"Q-{frm}-{c['id']}"
        if frm not in [s["scope"] for s in c["sides"]]: sys.exit(f"REFUSED: {frm} is no side of {c['id']} ({', '.join(s['scope'] for s in c['sides'])})")
        L = labels(); sides = " / ".join(side_line(s, L["conflict_question_claim"]) for s in c["sides"])
        q = opt(a, "--question") or L["conflict_question"].format(subject=c["subject"], sides=sides)   # the run's deliverable language (labels.<lang>.json)
        cmd_ = [sys.executable, os.path.join(TOOLS, "questions.py"), "add", frm, "client", q, "--id", qid, "--why", why, "--effect", opt(a, "--effect") or L["conflict_question_effect"].format(subject=c["subject"]),
                "--affects", ",".join(dict.fromkeys([s["scope"] for s in c["sides"]] + list(cfg["_method"].get("consolidations") or {})))]
        for i, s in enumerate(c["sides"]): cmd_ += ["--option", f"{chr(65 + i)}|{side_line(s, L['conflict_question_claim']).replace('|', '/')}|"]
        r = subprocess.run(cmd_, cwd=ROOT, capture_output=True, text=True)
        if r.returncode: sys.exit(r.stderr.strip() or r.stdout.strip())
        print(r.stdout.strip()); t = now()
        c.update({"status": "undecidable", "updated_at": t, "undecidable": {"reason": why, "by": frm, "question": qid, "at": t}}); save_json(PATH, reg)
        print(f"{c['id']}: undecidable -> client question {qid}" + ("" if opt(a, "--question") else f" (generated wording, {cfg['languages']['deliverable']} - reword it for the client: {CLI} questions edit {qid} --question \"...\")"))
    elif cmd == "skip":
        why = opt(a, "--reason"); ids = [a[1]] if len(a) > 1 and not a[1].startswith("--") else [c["id"] for c in open_ones(reg)]
        if not why: sys.exit("REFUSED: --reason \"...\"")
        t = now(); n = 0
        for cid in ids:
            c = find(reg, cid)
            if c["status"] == "open": c.update({"status": "skipped", "skip_reason": why, "updated_at": t}); n += 1
        save_json(PATH, reg); print(f"{n} conflict(s) skipped ({why}) - the consolidation starts with them; the consolidator brief says both sides stand")
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
