#!/usr/bin/env python3
"""state/STATUS.json helper of a run. The orchestrator resumes from this file, never from memory - and the file is verified
against disk before it is trusted (`dbcx status verify`, run automatically by `status next` and the SessionStart hook).
Phases come from the method pack (methods/<m>/method.json -> phases); scopes are the method's unit of analysis.

Usage:
  dbcx status init                      create state/STATUS.json from the merged configuration if missing (init / show / next / verify refuse
                                        a `profile` the method does not declare); stores the method folder's hash and source (method_guard)
  dbcx status show                      compact overview (+ verify flags)
  dbcx status next                      the next open item to work on, STATUS-DRIVEN; refuses "nothing to do" while verify reports owed work.
                                        before the first wave the rulings step (`dbcx rulings`; held under human_input.rulings required,
                                        a recommendation line under optional); RELEASE QUESTION BATCH when batched questions of a closed wave /
                                        finished phase wait (human_input.release batched). `split: none` (profile lean) skips the scopes phase -
                                        no discover / plan_waves / waves, the inventory feeds the consolidations; the rulings hold the first gauntlet;
                                        `phase_hints.<phase>` of the profile replaces a phase's hint / before / after; a scope without critic
                                        (scoring.phase_critics) goes from the CHECK straight to score_aggregate. before a consolidation
                                        starts, a method with a conflict detector gets `dbcx conflicts detect`; profile full holds the phase
                                        while a conflict is open (route -> resolve | undecidable | skip), split none prints the checklist line only.
                                        method.json `holds` (tech-fit-estimation: the row classification before discover) print the step
                                        a method tool's hold_line() names before that tool may run; method.json `steps` (tech-fit-estimation:
                                        the scope step before discover) print an automatic step that holds nothing (step_line) and its lines
                                        beside the later phases (also_lines: ALSO ...). Final gate: unprocessed gate question
                                        feedback (inbox) comes before the next round's persona briefs
  dbcx status verify [--brief]          compare STATUS with disk: phase vs `round:` header of each analysis file, source newer than its
                                        derived .json / workbook, checksum audit of every aggregated round, in_flight delivery tests, DIRTY markers,
                                        the method hash of `status init` (a changed own method is owed and stops `next`; a changed
                                        plugin method is a note)
  dbcx status set <dotted.path> <json>  e.g. set phases.preflight.status '"done"'
  dbcx status scope <name> <json>       merge fields into scopes.<name> (states: open | analysing | gauntlet | rework | passed |
                                        passed-rework-ordered | final | failed-gauntlet | skipped)      (`unit` is an alias)
  dbcx status issue add <scope> <text>  add open issue;  issue close <id>
  dbcx status assume <text>             record a decision taken without the user
  dbcx status log <text>                append to history (timestamped)
  dbcx status inflight add <json> | done <agent> | list      running agents (written by the Agent hook too); list adds the last activity
                                        (state/ACTIVITY.jsonl) and STALLED after activity.stall_minutes silent - verify prints a STALLED line too
  dbcx status done <agent> [--round n]  agent-written proof of delivery: a role's LAST step. Records
                                        {agent, round, output files + sha256, at} on the in_flight entry;
                                        the SubagentStop delivery test for that agent trusts this over a
                                        file's mere existence or a message that may never arrive.
  dbcx status feedback add <text> | done <id> <outcome> | list
"""
import json, os, sys, time, re, glob, hashlib, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import method_guard
from common import RUN as ROOT, STATUS_PATH, SCOPES_PATH, project, method, scope_info, scope_critics, profile_error, load_json, load_inbox, atomic_save_json, CLI, cli_text, run_cli, relp, fwd

PATH = STATUS_PATH
OPEN_STATES = ("open", "analysing", "gauntlet", "rework", "passed-rework-ordered", "passed")
CLOSED_STATES = ("final", "failed-gauntlet", "skipped")
INFLIGHT_REQUIRED = ("agent", "model", "brief_path", "output_files", "check_cmd")

def load():
    if not os.path.exists(PATH):
        sys.exit(f"no {relp(PATH, ROOT)} yet - this run has not started. Phase 0 of docs/PLAN.md creates it with `dbcx status init` (after check_fill, smoke, corpus index and intake). Nothing to verify or resume.")
    return json.load(open(PATH, encoding="utf-8"))
def save(s):
    s["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S"); atomic_save_json(PATH, s)   # temp file + os.replace + fcntl lock
def rel(p): return relp(p, ROOT)
def enabled(ph, p):
    cond = ph.get("enabled_if")
    if not cond: return True
    cur = p
    for part in cond.split("."):
        cur = cur.get(part, {}) if isinstance(cur, dict) else None
    return bool(cur)

def split_none(p): return p.get("split") == "none"   # no scope analysts - the inventory feeds the consolidations directly

def init():
    if os.path.exists(PATH): print("exists"); return
    p = project(); sc = p["scoring"]; m = p["_method"]
    phases = {}
    for ph in m["phases"]:
        e = {"status": "open", "type": ph["type"]}
        if ph["type"] == "gauntlet": e.update({"scope": ph["scope"], "gauntlet_rounds": [], "passed": False})
        if ph["type"] == "scopes": e.update({"current_wave": 0, "total_waves": 0})
        if ph["type"] == "gate": e.update({"rounds": [], "passed": False})
        if ph.get("enabled_if") is not None: e["enabled"] = enabled(ph, p)
        if ph["type"] == "scopes" and split_none(p): e["enabled"] = False
        phases[ph["id"]] = e
    s = {"run": f"{p['engagement']['client']} - {p['engagement'].get('run_title') or p['engagement']['title']}", "method": m["name"],
         "pass_threshold": sc["pass_threshold"], "max_gauntlet_rounds": sc["max_gauntlet_rounds"], "max_gate_rounds": sc["max_gate_rounds"], "critics": sc["critics"], "gate_personas": sc["gate_personas"],
         "phases": phases, "scopes": {}, "in_flight": [],
         "deliverables": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in p.get("deliverables", {}).items() if isinstance(v, dict)},
         "handover": {"imported": list((load_json("run.json", {}).get("handover") or {}).get("imports", [])), "exported": []}, "open_issues": [], "issue_seq": 0, "history": [], "assumptions": [], "feedback": [],
         "method_guard": method_guard.stamp(m)}   # the method as the run started with it (verify and the hook compare)
    os.makedirs(os.path.dirname(PATH), exist_ok=True); save(s); print("initialised", rel(PATH))

# ------------------------------------------------------------------ verify
def file_round(path):
    try:
        for line in open(path, encoding="utf-8").read().split("\n")[:15]:
            mm = re.match(r"- \*\*round:\*\*\s*(\d+)", line.strip())
            if mm: return int(mm.group(1))
    except FileNotFoundError: return None
    return None

def scope_files(s):
    """[(status key, scope, base path without extension, is_phase)] for the inventory, the consolidations and every per-scope analysis."""
    m = method(); out = []
    for ph in m["phases"]:
        if ph["type"] == "gauntlet":
            js, md, kind, role, agent = scope_info(ph["scope"], m); out.append((ph["id"], ph["scope"], md[:-3], True))
    for u in sorted(s.get("scopes", {})):
        js, md, kind, role, agent = scope_info(u, m); out.append((u, u, md[:-3], False))
    return out

def dry_check(cmd):
    if "md_to_json" in cmd and "--out" not in cmd:
        import tempfile; return cmd.split("  (")[0] + " --out " + fwd(tempfile.mktemp(suffix=".json"))
    return cmd.split("  (")[0]

def verify(brief=False):
    s = load(); owed = []; info = []; m = method(); p = project()
    mg = method_guard.check(s.get("method_guard"), m)   # a method is refined between runs, never during one
    if mg: (owed if mg[0] == "stop" else info).append(mg[1])
    for key, scope, base, is_phase in scope_files(s):
        ph = s["phases"].get(key, {}) if is_phase else s["scopes"].get(key, {})
        rec = len(ph.get("gauntlet_rounds", [])) if "gauntlet_rounds" in ph else ph.get("rounds", 0)
        fr = file_round(base + ".md")
        if fr is not None and rec is not None and fr > rec and ph.get("status") not in ("skipped",): owed.append(f"{scope}: analysis file says round {fr}, STATUS recorded {rec} rounds (status {ph.get('status')}) -> a delivered rework whose gauntlet was never run, or a round being scored right now")
        md, js = base + ".md", base + ".json"
        if os.path.exists(md) and os.path.exists(js) and os.path.getmtime(md) > os.path.getmtime(js) + 1: owed.append(f"{scope}: {rel(md)} newer than its .json -> {CLI} md_to_json owed")
        gd = os.path.join(ROOT, "analysis", "gauntlet", scope)
        if os.path.isdir(gd):
            for resf in sorted(glob.glob(os.path.join(gd, "round*-result.json"))):
                try: chk = json.load(open(resf, encoding="utf-8")).get("checksums") or {}
                except Exception: continue
                for c, h in chk.items():
                    fp = os.path.join(gd, os.path.basename(resf).replace("-result.json", f"-{c}.json"))
                    if os.path.exists(fp) and h and not h.startswith("(") and hashlib.sha256(open(fp, "rb").read()).hexdigest() != h: owed.append(f"{scope}: {rel(fp)} no longer matches the checksum in {os.path.basename(resf)} -> carried entries lost; re-run score_aggregate for that round (dry-run first), never md_to_json")
            if os.path.exists(os.path.join(gd, "DIRTY")): owed.append(f"{scope}: DIRTY marker - the analysis was edited while a round was open; re-extract (round open) or investigate")
            snaps = sorted(int(mm.group(1)) for f in os.listdir(gd) for mm in [re.match(r"claims-round(\d+)\.json", f)] if mm)
            if snaps and not os.path.exists(os.path.join(gd, f"round{snaps[-1]}-result.json")) and ph.get("status") not in ("gauntlet", "analysing", "rework"): info.append(f"{scope}: round {snaps[-1]} extracted but not aggregated (status {ph.get('status')})")
    # derived deliverables older than their sources (method.deliverable_sources)
    for key, srcs in m.get("deliverable_sources", {}).items():
        dl = s.get("deliverables", {}).get(key, {}); xls = os.path.join(ROOT, "deliverables", dl.get("file", "")) if dl.get("file") else None
        if xls and os.path.exists(xls):
            for pat in srcs:
                for src in glob.glob(os.path.join(ROOT, pat)):
                    if os.path.getmtime(src) > os.path.getmtime(xls) + 1: owed.append(f"{key}: {rel(src)} newer than {rel(xls)} -> {CLI} build_excel {key} owed"); break
    for e in s.get("in_flight", []) or []:
        if e.get("delivered"): continue
        miss = [k for k in INFLIGHT_REQUIRED if not e.get(k)]
        if miss: info.append(f"in_flight {e.get('agent')}: entry lacks {', '.join(miss)} - a resuming session cannot test delivery")
        outs = e.get("output_files") or []
        have = [f for f in outs if os.path.exists(os.path.join(ROOT, f))]
        if outs and len(have) == len(outs):
            ok = None
            if e.get("check_cmd"):
                r = run_cli(dry_check(e["check_cmd"]), cwd=ROOT, capture_output=True, text=True); ok = r.returncode == 0 and "INVALID" not in r.stdout and "REFUSED" not in r.stdout
            # a file that exists and converts proves the file parses, not that its author finished.
            owed.append(f"in_flight {e.get('agent')}: output on disk" + (f", check {'OK' if ok else 'INVALID'}" if ok is not None else "") + f" -> author state UNKNOWN (a file is not a delivery signal): confirm with the harness agent list that {e.get('agent')} has finished or reported" + (f" (round {e.get('round')} continuation)" if e.get('round') else "") + f"; then run its on_delivery steps and `{CLI} status inflight done {e.get('agent')}`; do NOT re-spawn (it could overwrite a scored round)")
        else: info.append(f"in_flight {e.get('agent')}: {len(have)}/{len(outs)} output files -> LOST if the agent is gone: re-spawn per its `respawn` field ({e.get('respawn', '?')[:80]})")
    un = unreleased()
    if un and open_phase(s, m)[1]: owed.append(f"{len(un)} question(s) not released at build (human_input.release batched): {', '.join(q['id'] for q in un[:12])} - the workbooks show released questions only and a final build refuses: review `related` / link duplicates, then `{CLI} questions release --all`")
    fb = [x for x in s.get("feedback", []) if not x.get("processed")]
    if fb: owed.append(f"{len(fb)} user feedback item(s) not yet processed ({CLI} status feedback list)")
    try:   # open knowledge-base candidates are owed like feedback; growth warnings are information only
        import kb; k = kb.load(); oc = [c["id"] for c in k.get("candidates", []) if c.get("status") == "open"]
        if oc: owed.append(f"{len(oc)} knowledge-base candidate(s) open: {', '.join(oc)} ({CLI} kb promote <KC> --text ... --topic ... --applies-to ... | {CLI} kb reject <KC> --reason ...)")
        info += [f"knowledge base: {w}" for w in kb.warnings(k, kb.thresholds(m))]
    except Exception: pass
    try:
        from common import load_inbox, load_control
        ib = [e for e in load_inbox() if not e.get("processed")]
        if ib: owed.append(f"{len(ib)} inbox entr{'y' if len(ib) == 1 else 'ies'} from the dashboard not yet applied ({CLI} inbox next)")
        ctl = load_control()
        if ctl.get("pause_requested"): owed.append(f"PAUSE requested {ctl.get('pause_requested_at')}" + (" and acknowledged - do not spawn; a fresh session resumes with `" + CLI + " inbox control resume`" if ctl.get("pause_ack_at") else f" - spawn nothing new (hook-enforced), finish in-flight work, verify, write docs/RESUME.md, `{CLI} inbox control ack-pause`, end the turn"))
        if ctl.get("checkpoint_requested_at"): owed.append(f"CHECKPOINT requested {ctl.get('checkpoint_requested_at')} - {CLI} progress; {CLI} build_excel --all --interim; {CLI} render brief progress --out -> progress-reporter; {CLI} inbox control checkpoint-done")
    except Exception: pass
    # handover drift: an imported artefact whose source changed since import (information, not owed work)
    for h in s.get("handover", {}).get("imported", []):
        src = h.get("source_path")
        if src and os.path.exists(src) and h.get("sha256") and hashlib.sha256(open(src, "rb").read()).hexdigest() != h["sha256"]: info.append(f"handover {h.get('type')}: the released artefact {src} changed since this run imported it - inputs are frozen per run; consider a delta run")
    lp = os.path.join(ROOT, "docs", "LEARNINGS.md")
    if os.path.exists(lp) and not brief: info.append("read docs/LEARNINGS.md section F (open items) before acting - verify each on disk")
    # a hook that has never fired enforces nothing; say so every time, brief or not (`verify` would keep saying
    # "agrees with disk" while a whole session ran unguarded).
    warn = ""
    try:
        from runtime import HARNESS as h
        hb = (load_json("state/HOOKS.json", {}) or {}).get("harnesses", {})
        if not hb.get(h): warn = f"WARNING: no hook event from harness '{h}' recorded for this run (state/HOOKS.json) - brief enforcement, read-only guard, web hygiene, in_flight and delivery tests are NOT active. Spawn nothing until `{CLI} hooks status` shows a heartbeat."
    except Exception: pass
    if owed:
        print(f"VERIFY: {len(owed)} owed item(s) - handle these before `status next` is trusted:"); [print("  OWED:", x) for x in owed]
    else: print("VERIFY: STATUS agrees with disk")
    if warn: print("  " + warn)
    for x in stalled(s): print("  " + x)
    if not brief:
        for x in info: print("  note:", x)
    return owed

def activity_of(fl):
    """last activity + stalled flag per undelivered in_flight entry (engine/tools/activity.py)"""
    import activity
    lw = lambda e: max([time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(os.path.join(ROOT, f)))) for f in e.get("output_files") or [] if f and os.path.exists(os.path.join(ROOT, f))] or [None])
    try: return activity.per_agent(ROOT, fl, activity.stall_minutes(project()), last_write=lw, max_call_minutes=activity.max_call_minutes(project()))
    except Exception: return {}
def stalled(s):
    act = activity_of(s.get("in_flight", []) or [])
    return [f"STALLED: in_flight {k} silent for {v['silent_min']} min (no tool call, no output write; last: {v.get('activity') or 'nothing recorded'}{' at ' + v['activity_at'] if v.get('activity_at') else ''}) - check it in the harness's agent list; message it, or stop and re-spawn it per its `respawn` field" for k, v in act.items() if v.get("stalled")]

def show():
    s = load(); print(f"run {s.get('run')} method {s.get('method')} updated {s.get('updated_at')}")
    for k, v in s["phases"].items():
        print(f"  {k:24s} {str(v.get('status')):22s} passed={v.get('passed', '-')} rounds={len(v.get('gauntlet_rounds', v.get('rounds', [])))}" + ("" if v.get("enabled", True) else " (disabled)"))
    for k, v in sorted(s["scopes"].items()):
        print(f"  scope {k:34s} wave={v.get('wave')} status={str(v.get('status')):22s} rounds={v.get('rounds', 0)} scores={v.get('last_scores', {})} passed={v.get('passed')}")
    oi = [i for i in s["open_issues"] if i.get("status") == "open"]
    print(f"  open issues: {len(oi)}; in_flight (undelivered): {sum(1 for e in s.get('in_flight', []) if not e.get('delivered'))}")
    for i in oi[:15]: print(f"    #{i['id']} [{i['scope']}] {i['text'][:110]}")
    import override; ov = override.summary()   # engagement overrides written with `dbcx override`
    if ov: print(ov)
    verify(brief=True)

def gauntlet_hint(scope, role, agent, st, r, crit, gd, is_scope):
    setter = f"{CLI} status scope {scope}" if is_scope else f"{CLI} status set phases.<phase>"
    brief_kind = {"analyst": f"analyst {scope}", "inventory": "inventory", "consolidator": f"consolidate {scope}"}[role]
    if st == "open": print(f"  DO: {CLI} render brief {brief_kind} --out  ->  spawn {agent} with the brief's MODEL; then {setter} status analysing" + (" (all scopes of this wave in one message)" if is_scope else ""))
    elif not crit and st in ("analysing", "rework", "passed-rework-ordered", "gauntlet"):   # no critic on this scope - the deterministic checks decide
        print(f"  DO: agent {agent} still running? if not: {CLI} render brief {brief_kind}" + (f" --round {r + 1} --addendum <file>" if r else "") + " --out -> re-spawn")
        print(f"  ON REPORT: {CLI} md_to_json (CHECK line of the brief); {CLI} status inflight done {agent}; {CLI} extract_claims {scope} --round {r + 1} (quote gate); {CLI} evidence check {scope}; no critic scores this scope (scoring.phase_critics) - {CLI} score_aggregate {scope} {r + 1} --dry-run, then without --dry-run (pass rule {project()['scoring'].get('pass_rule', 'defects')}: CHECK + quotes + locators)")
    elif len(crit) == 1 and st in ("analysing", "rework", "passed-rework-ordered", "gauntlet"):   # one critic: the same steps, one agent
        if st == "gauntlet": print(f"  DO: " + ("" if os.path.exists(os.path.join(gd, f"round{r + 1}-{crit[0]}.md")) else f"critic file missing -> re-spawn from {CLI} render brief critic {crit[0]} {scope} {r + 1} --out; ") + f"then {CLI} md_to_json critic analysis/gauntlet/{scope}/round{r + 1}-{crit[0]}.md (ONCE); {CLI} score_aggregate {scope} {r + 1} --dry-run, then without --dry-run")
        else:
            print(f"  DO: agent {agent} still running? if not: {CLI} render brief {brief_kind}" + (f" --round {r + 1} --addendum <file>" if r else "") + " --out -> re-spawn")
            print(f"  ON REPORT: {CLI} md_to_json (CHECK line of the brief); {CLI} status inflight done {agent}; {CLI} extract_claims {scope} --round {r + 1}; {CLI} render brief critic {crit[0]} {scope} {r + 1} --out -> spawn critic-{crit[0]}-{scope} (round >= 2: continue the running critic with the delta); status gauntlet")
    elif st == "analysing":
        print(f"  DO: agent {agent} still running? (ListAgents) if not: {CLI} render brief {brief_kind} --out -> re-spawn (RESUME NOTE continues the file)")
        print(f"  ON REPORT: {CLI} md_to_json (CHECK line of the brief); {CLI} status inflight done {agent}; {CLI} extract_claims {scope} --round {r + 1}; {CLI} render brief critic <critic> {scope} {r + 1} --out for {', '.join(crit)} -> spawn each (or SendMessage the delta to still-running critics); status gauntlet")
    elif st in ("rework", "passed-rework-ordered"):
        print(f"  DO: agent {agent} still running with round{r}-issues.md? if not: {CLI} render brief {brief_kind} --round {r + 1} --addendum <file> --out -> re-spawn")
        print(f"  ON REPORT: convert once; {CLI} extract_claims {scope} --round {r + 1}; critics: SendMessage the delta to the running critic-*-{scope} agents or re-spawn from {CLI} render brief critic <critic> {scope} {r + 1} --out; status gauntlet")
    elif st == "gauntlet":
        have = [c for c in crit if os.path.exists(os.path.join(gd, f"round{r + 1}-{c}.md"))]; miss = [c for c in crit if c not in have]
        print("  DO: " + (f"critic files missing for {', '.join(miss)} -> re-spawn from {CLI} render brief critic <critic> {scope} {r + 1} --out; " if miss else "") + f"then {CLI} md_to_json critic analysis/gauntlet/{scope}/round{r + 1}-<critic>.md each (ONCE); {CLI} score_aggregate {scope} {r + 1} --dry-run, then without --dry-run")
    elif st == "passed": print(f"  DO: {CLI} render brief postpass {scope} --out if round{r}-issues.md lists notes on passing claims (text only, no re-score) else set `status: final` in the analysis file and record status final")

def gate_hint(ph, e, s):
    """final gate, file-driven: hygiene -> personas + verifier -> gate_aggregate -> deliverable-editor -> next round (G2-G10)"""
    rounds = e.get("rounds", []); last = rounds[-1] if rounds else None; gd = os.path.join(ROOT, "analysis", "gate")
    have = lambda f: os.path.exists(os.path.join(gd, f))
    if last and not last.get("passed"):
        k = last.get("round", len(rounds))
        import gate
        if len(rounds) >= gate.max_rounds(): print(f"NEXT: final gate exhausted after {len(rounds)} rounds -> write docs/FINAL_REPORT.md with the open clusters of analysis/gate/round{k}-fixplan.md"); return
        if not have(f"round{k}-editor.md"):
            print(f"NEXT: {ph['id']} round {k} FAILED ({last.get('clusters', '?')} clusters, {last.get('blockers', '?')} blocker, {last.get('majors_without_decision', '?')} major without a lead decision) - execute analysis/gate/round{k}-fixplan.md")
            print(f"  DO: {CLI} render brief editor {k} --out -> spawn deliverable-editor; its REQUESTS (content) -> owning consolidator/analyst + mini gauntlet; ESCALATIONS -> the lead, then `{CLI} gate decide {k} <cluster> \"<decision>\"` and `{CLI} gate_aggregate {k}` again. Every blocker/major cluster is fixed or escalated before round {k + 1}.")
            return
    n = last.get("round", len(rounds)) + 1 if last else 1
    hyg = load_json(f"analysis/gate/round{n}-hygiene.json", {}); books = glob.glob(os.path.join(ROOT, "deliverables", "*.xlsx"))
    stale = bool(hyg) and bool(books) and max(os.path.getmtime(b) for b in books) > os.path.getmtime(os.path.join(gd, f"round{n}-hygiene.json"))
    if not hyg or stale or not hyg.get("passed"):
        print(f"NEXT: {ph['id']} round {n} - hygiene layer: {CLI} build_excel --all; {CLI} render_workbook --all; {CLI} lint_deliverable --standalone --all --round {n}" + (" (report older than the workbooks)" if stale else (f" - FAILED with {hyg['errors']} error(s): clear them first (analysis/gate/round{n}-hygiene.md; deliverable-editor)" if hyg else "")))
        if n == 1 and not have("round0-editor.md"): print(f"  THEN: {CLI} render brief editor 0 --out -> deliverable-editor writes the management summaries after the build and clears the hygiene findings (pre-gate pass)")
        return
    miss = [p for p in s.get("gate_personas", []) if not have(f"round{n}-{p}.json")] + ([] if have(f"round{n}-verifier.json") else ["verifier"])
    fb = [e for e in load_inbox() if e.get("kind") == "gate_question_feedback" and not e.get("processed")]
    if fb and miss and not glob.glob(os.path.join(ROOT, "analysis", "briefs", f"gate-*-r{n}.md")):   # a question change applies from the first round whose briefs are not rendered yet: this one
        print(f"NEXT: {ph['id']} round {n} - the lead's gate question feedback first ({len(fb)} open), then the persona briefs")
        for e in fb: print(f"  - {e['client_id'][:8]} {e.get('persona')} {e.get('question_id')} (round {e.get('round')}, {e.get('intent')}): {(e.get('text') or '')[:100]}")
        print(f"  DO: {CLI} inbox next per entry -> decide reword | dismiss | keep -> {CLI} gate question <persona> <qid> ... --feedback <client_id> (your own wording, never the lead's)")
        return
    note = f"  NOTE: {len(fb)} open gate question feedback - round {n} is under way, a change recorded now applies from round {n + 1} ({CLI} inbox next)" if fb else ""
    if miss:
        print(f"NEXT: {ph['id']} round {n} - personas + verifier (missing: {', '.join(miss)})")
        print(f"  DO: {CLI} render brief gate <persona> {n} --out per missing persona and {CLI} render brief verifier {n} --out; spawn them in one message; convert each once with its CHECK")
        if note: print(note)
        return
    print(f"NEXT: {ph['id']} round {n} - {CLI} gate_aggregate {n} (pass rule + fix plan)")
    if note: print(note)

def pending_scopes(s): return [(k, v) for k, v in s["scopes"].items() if v.get("status") in OPEN_STATES or (not v.get("passed") and v.get("status") not in ("failed-gauntlet", "skipped", "final"))]
def gauntlet_open(e): return e.get("status") not in ("final", "failed-gauntlet") and (not e.get("passed") or e.get("status") in ("rework", "gauntlet", "analysing", "passed-rework-ordered"))

def open_phase(s, m):
    """(the first phase with work left as `status next` walks them, at build: True when that is the build / gate phase or none is left)"""
    sn = split_none(project())
    for ph in m["phases"]:
        e = s["phases"].get(ph["id"], {}); t = ph["type"]
        if not e.get("enabled", True) or (t == "scopes" and sn): continue
        if (t in ("simple", "build") and e.get("status") != "done") or (t == "gauntlet" and gauntlet_open(e)) or (t == "scopes" and (not s["scopes"] or pending_scopes(s))) or (t == "gate" and not e.get("passed")):
            return ph, t in ("build", "gate")
    return None, True

def unreleased():
    try:
        from common import load_questions; return [q for q in load_questions() if q.get("released") is False]
    except Exception: return []

def batch_line(s, m):
    """the unreleased questions of closed waves and finished gauntlet phases - at build every one;
    questions of askers that are no scope (orchestrator, lead, intake) join the next batch"""
    un = unreleased()
    if not un: return ""
    ph, at_build = open_phase(s, m); pend = pending_scopes(s); ow = min([v["wave"] for _, v in pend if isinstance(v.get("wave"), int)], default=None)
    phase_scope = {x["scope"]: s["phases"].get(x["id"], {}) for x in m["phases"] if x["type"] == "gauntlet"}
    def closed(f):
        if f in s["scopes"]: v = s["scopes"][f]; return v.get("status") in CLOSED_STATES and (ow is None or not isinstance(v.get("wave"), int) or v["wave"] < ow)
        return not gauntlet_open(phase_scope[f]) if f in phase_scope else None
    ready = un if at_build else [q for q in un if closed(q.get("from"))]
    if not ready: return ""
    if not at_build: ready += [q for q in un if closed(q.get("from")) is None]
    by = {}
    for q in ready: by[q.get("from")] = by.get(q.get("from"), 0) + 1
    return (f"RELEASE QUESTION BATCH ({'build' if at_build else 'wave gate / phase end'}): {len(ready)} unreleased question(s) from " + ", ".join(f"{k} ({v})" for k, v in by.items())
            + f" - review their `related` neighbours ({CLI} questions list --unreleased; a duplicate -> {CLI} questions link <dup> <primary>, answered by an entry -> {CLI} questions answer <id> --from-kb KB-n), then {CLI} questions release " + ("--all" if at_build else "--scope " + ",".join(by)))

def rulings_step(ph, cfg):
    """the rulings sheet before the first wave (a method without a scopes phase: before the first gauntlet). required -> the NEXT
    line (True: hold); optional -> a recommendation line, the wave goes on"""
    import rulings as RU
    r = RU.load()
    if r.get("status") in ("done", "skipped"): return False
    if (cfg.get("human_input") or {}).get("rulings", "optional") == "required": print(f"NEXT: rulings before {ph['id']} (human_input.rulings required) - {RU.next_line(r)}"); return True
    print(f"RECOMMENDED before {ph['id']}: rulings - {RU.next_line(r)}"); return False

def method_hold(m, cfg):
    """method.json `holds: [{"before": "<tool>", "tool": "<method tool>"}]`: the method tool's hold_line(cfg) -> the step that has to
    happen before <tool> (a line) or None (nothing to wait for, e.g. the classification before discover) -> (hold, line)"""
    import importlib.util
    from common import method_tool
    for h in m.get("holds") or []:
        tp = method_tool(h.get("tool", ""), m)
        if not tp: continue
        sp_ = importlib.util.spec_from_file_location(f"dbcx_hold_{h['tool']}", tp); mod = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(mod)
        line = mod.hold_line(cfg) if hasattr(mod, "hold_line") else None
        if line: return h, line
    return None, None

def method_steps(m, cfg):
    """method.json `steps: [{"before": "<tool>", "tool": "<method tool>"}]`: an automatic step of the pipeline that comes before <tool>
    but holds nothing (tech-fit-estimation: the scope step before discover). The tool's step_line(cfg) -> the step's next action or
    None (done / not part of this run); also_lines(cfg) -> [lines] that run beside the later phases (e.g. the step's gauntlet, changes
    waiting for the next wave) -> [(step, line, also)]"""
    import importlib.util
    from common import method_tool
    out = []
    for h in m.get("steps") or []:
        tp = method_tool(h.get("tool", ""), m)
        if not tp: continue
        sp_ = importlib.util.spec_from_file_location(f"dbcx_step_{h['tool']}", tp); mod = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(mod)
        out.append((h, mod.step_line(cfg) if hasattr(mod, "step_line") else None, (mod.also_lines(cfg) if hasattr(mod, "also_lines") else None) or []))
    return out

def own_preflight(hint, m):
    """an own method is checked (`dbcx method check`) before its smoke test in preflight"""
    if m.get("_source") != "engagement": return hint
    n = m["name"]; sm = f"dbcx smoke {n}"
    return hint.replace(sm, f"dbcx method check {n}; {sm}") if sm in hint else f"dbcx method check {n}; {sm}" + (f"; {hint}" if hint else "")

def nxt():
    owed = verify(brief=True); s = load(); p = s["phases"]; m = method(); cfg = project()   # live critics per scope: common.scope_critics (per-pack standard critics follow run.json options, a method hook narrows them)
    if method_guard.CHANGED in owed: print(f"STOP: {method_guard.CHANGED}"); return   # no next step on a changed method
    bl = batch_line(s, m)
    if bl: print(bl)
    steps = method_steps(m, cfg); scoped = os.path.exists(SCOPES_PATH)
    for h, line, also in steps:
        if line and scoped: print(f"ALSO: step before `{CLI} {h['before']}` not done (it holds nothing): {line}")
        for x in also: print(f"ALSO: {x}")
    step = next(((h, line) for h, line, _ in steps if line), (None, None))
    sn = split_none(cfg); hints = cfg.get("phase_hints") or {}   # split none skips the scopes phase; a profile may replace a phase's hint / before / after
    hold = (None if sn else next((x for x in m["phases"] if x["type"] == "scopes"), None)) or next((x for x in m["phases"] if x["type"] == "gauntlet"), None)
    for ph in m["phases"]:
        e = p.get(ph["id"], {})
        if not e.get("enabled", True) or (ph["type"] == "scopes" and sn): continue
        is_hold = ph is hold; ph = dict(ph, **(hints.get(ph["id"]) or {})) if hints.get(ph["id"]) else ph
        t = ph["type"]
        if t == "simple":
            if e.get("status") != "done":
                hint = own_preflight(ph.get("hint") or "", m) if ph["id"] == "preflight" else ph.get("hint")
                print(f"NEXT: {ph['id']}" + (f" - {hint}" if hint else ""))
                h, line = method_hold(m, cfg) if not os.path.exists(SCOPES_PATH) else (None, None)
                if line: print(f"  HOLD before `{CLI} {h['before']}`: {line}")
                elif step[1] and not scoped: print(f"  STEP before `{CLI} {step[0]['before']}` (automatic, nothing waits for a person): {step[1]}")
                return
        elif t == "gauntlet":
            scope = ph["scope"]
            if gauntlet_open(e):
                if is_hold and e.get("status", "open") == "open" and rulings_step(ph, cfg): return
                if scope in (m.get("consolidations") or {}) and e.get("status", "open") == "open":   # the conflict register before a consolidation starts
                    import conflicts
                    if conflicts.status_step(ph, cfg): return
                js, md, kind, role, agent = scope_info(scope, m); r = len(e.get("gauntlet_rounds", []))
                print(f"NEXT: {ph['id']} / scope {scope} (status={e.get('status')}, rounds={r}, passed={e.get('passed')})" + (f"; before: {ph['before']}" if ph.get("before") and e.get("status") == "open" else ""))
                gauntlet_hint(scope, role, agent, e.get("status"), r, scope_critics(scope, cfg), os.path.join(ROOT, "analysis", "gauntlet", scope), False)
                if ph.get("after"): print(f"  AFTER PASS: {ph['after']}")
                return
        elif t == "scopes":
            pend = pending_scopes(s)
            if not s["scopes"] and os.path.exists(SCOPES_PATH):
                print(f"NEXT: {ph['id']} - scopes discovered but none registered: {CLI} plan_waves, then `{CLI} status scope <name> '{{\"wave\": n, \"status\": \"open\"}}'` for every scope"); return
            if not s["scopes"]:
                h, line = method_hold(m, cfg)
                if line: print(f"NEXT: {ph['id']} - held before `{CLI} {h['before']}`: {line}"); return
                if step[1]: print(f"NEXT: {ph['id']} - step before `{CLI} {step[0]['before']}` (automatic, nothing waits for a person): {step[1]}"); return
                print(f"NEXT: {ph['id']} - no scopes yet: run the method's discover tool ({'discover' if str(m['scopes'].get('discover', '')).startswith('generic:') else m['scopes'].get('discover', 'discover')}), then {CLI} plan_waves"); return
            if pend:
                if is_hold and all(v.get("status", "open") in ("open", "skipped") for v in s["scopes"].values()) and rulings_step(ph, cfg): return
                pend.sort(key=lambda kv: (kv[1].get("wave", 999), -(kv[1].get("rounds", 0)), min([x for x in (kv[1].get("last_scores") or {}).values() if isinstance(x, (int, float))] or [0])))
                k, v = pend[0]; st = v.get("status"); r = v.get("rounds", 0); js, md, kind, role, agent = scope_info(k, m)
                print(f"NEXT: scope {k} (wave {v.get('wave')}, status={st}, rounds={r}, scores={v.get('last_scores')})")
                waves = [x[1].get("wave") for x in pend if isinstance(x[1].get("wave"), int)]
                if waves:
                    ow = min(waves); still = sorted(f"{a} ({b.get('status')})" for a, b in pend if b.get("wave") == ow)
                    print(f"  WAVE GATE: wave {ow} is open - {len(still)} scope(s) not closed: {', '.join(still)}. No scope of a later wave is rendered or spawned until every one of them is final | failed-gauntlet | skipped.")
                gauntlet_hint(k, role, agent, st, r, scope_critics(k, cfg), os.path.join(ROOT, "analysis", "gauntlet", k), True); return
        elif t == "build":
            if e.get("status") != "done": print(f"NEXT: {ph['id']} ({CLI} build_excel --all; {CLI} lint_deliverable; write analysis/summaries/<D>.md first)"); return
        elif t == "gate":
            if not e.get("passed"): gate_hint(ph, e, s); return
    if owed: print("NEXT: nothing scheduled, but VERIFY reports owed work above - clear it first"); return
    print(f"NEXT: write docs/FINAL_REPORT.md, {CLI} handover export for every produced artefact, {CLI} learn export on the user's word (all gates passed)")

def setp(path, val):
    s = load(); cur = s; parts = path.split(".")
    for part in parts[:-1]: cur = cur.setdefault(part, {})
    v = json.loads(val)
    if v is None and parts[-1] in cur:   # explicit null removes the key - a wrongly registered entry is retracted, not left as a null the readers trip over
        cur.pop(parts[-1]); save(s); print(f"ok (removed {path})"); refresh_progress(); return
    cur[parts[-1]] = v; save(s); print("ok")

def refresh_progress():
    try: subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.py"), "--quiet"], cwd=ROOT, capture_output=True, text=True, timeout=20)
    except Exception: pass

def scope(name, val):
    s = load()
    # scopes[] holds the method's units of analysis (the wave members). A scope a PHASE already owns - the
    # inventory and the consolidations - is tracked by that phase; registering it here too gives it a second
    # analyst row in a phantom wave and makes it count in the share of analysed units.
    owned = {v.get("scope"): k for k, v in (s.get("phases") or {}).items() if v.get("scope")}
    if name in owned and name not in s.get("scopes", {}):
        sys.exit(f"{name} is the scope of phase '{owned[name]}' and is tracked there - use `dbcx status set phases.{owned[name]}.<field>`. scopes[] is for the units of analysis.")
    e = s["scopes"].setdefault(name, {"status": "open", "rounds": 0, "passed": False}); e.update(json.loads(val)); save(s); print("ok"); refresh_progress()

def issue(cmd, *rest):
    s = load()
    if cmd == "add":
        s["issue_seq"] += 1; s["open_issues"].append({"id": s["issue_seq"], "scope": rest[0], "text": " ".join(rest[1:]), "status": "open", "created": time.strftime("%Y-%m-%d %H:%M")}); save(s); print("added #%d" % s["issue_seq"])
    elif cmd == "close":
        for i in s["open_issues"]:
            if str(i["id"]) == rest[0]: i["status"] = "closed"; i["closed"] = time.strftime("%Y-%m-%d %H:%M")
        save(s); print("closed")

def inflight(cmd, *rest):
    s = load(); fl = s.setdefault("in_flight", [])
    if cmd == "add":
        e = json.loads(" ".join(rest)); e.setdefault("spawned_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        miss = [k for k in INFLIGHT_REQUIRED if not e.get(k)]
        fl[:] = [x for x in fl if x.get("agent") != e.get("agent")]; fl.append(e); save(s)
        print(f"in_flight += {e.get('agent')}" + (f"  WARNING missing fields: {', '.join(miss)}" if miss else "")); refresh_progress()
    elif cmd == "done":
        n = 0
        for x in fl:   # re-stamps an already delivered entry too: extract_claims compares the file's mtime with delivered_at
            if x.get("agent") == rest[0]: x["delivered"] = True; x["delivered_at"] = time.strftime("%Y-%m-%dT%H:%M:%S"); n += 1
        save(s); print(f"marked delivered: {n}"); refresh_progress()
    elif cmd == "list":
        act = activity_of(fl)
        for x in fl:
            if x.get("delivered"): continue
            a = act.get(x.get("agent")) or {}
            print(f"  {x.get('agent'):40s} {x.get('harness', '?')}/{x.get('provider', '?')} {str(x.get('model', '?')):20s} effort={x.get('reasoning_effort', '?')} role={x.get('role', '?')} brief={x.get('brief_path')} out={x.get('output_files')} check={x.get('check_cmd')}")
            now_ = f"running {a['busy_tool']} for {a['busy_min']} min" if a.get("busy_min") is not None else f"silent {a.get('silent_min', '?')} min"
            print(f"    {'STALLED ' if a.get('stalled') else ''}last activity {a.get('activity_at') or '-'} {a.get('activity') or '(none recorded)'}; {now_}")
        print(f"{sum(1 for x in fl if not x.get('delivered'))} running/undelivered")

def feedback(cmd, *rest):
    s = load(); fb = s.setdefault("feedback", [])
    if cmd == "add": fb.append({"id": len(fb) + 1, "t": time.strftime("%Y-%m-%d %H:%M"), "text": " ".join(rest), "processed": False}); save(s); print(f"feedback #{len(fb)} recorded")
    elif cmd == "done":
        for x in fb:
            if str(x["id"]) == rest[0]: x["processed"] = True; x["outcome"] = " ".join(rest[1:])
        save(s); print("ok")
    else:
        for x in fb: print(f"  #{x['id']} {x['t']} {'done' if x.get('processed') else 'OPEN'}: {x['text'][:160]}" + (f" -> {x.get('outcome')}" if x.get('outcome') else ""))

def donecmd(agent, round_):
    """Agent-written proof of delivery: the role's LAST step. Recorded on the in_flight entry
    (created if the spawn hook never registered one) so the SubagentStop delivery test for exactly
    THIS agent can trust it instead of inferring delivery from a file's mere existence or a message
    that may never arrive. Does not itself flip
    `delivered` - the hook still runs the entry's check_cmd once before accepting it."""
    s = load(); fl = s.setdefault("in_flight", [])
    e = next((x for x in fl if x.get("agent") == agent), None)
    if e is None: e = {"agent": agent, "spawned_at": time.strftime("%Y-%m-%dT%H:%M:%S")}; fl.append(e)
    outs = e.get("output_files") or []
    hashes = {f: hashlib.sha256(open(os.path.join(ROOT, f), "rb").read()).hexdigest() for f in outs if os.path.exists(os.path.join(ROOT, f))}
    e["done"] = {"round": round_, "output_files": outs, "sha256": hashes, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save(s); print(f"done: {agent}" + (f" round {round_}" if round_ else "") + f" ({len(hashes)}/{len(outs)} output file(s) hashed)" + ("" if hashes or not outs else " - WARNING no output file found on disk yet"))

def assume(text):
    s = load(); s["assumptions"].append({"t": time.strftime("%Y-%m-%d %H:%M"), "text": text}); save(s); print("ok")
def logmsg(text):
    s = load(); s["history"].append({"t": time.strftime("%Y-%m-%d %H:%M"), "msg": text}); save(s); print("ok")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(0)
    cmds = {"init": lambda: init(), "show": lambda: show(), "next": lambda: nxt(), "verify": lambda: sys.exit(1 if verify("--brief" in a) else 0), "set": lambda: setp(a[1], a[2]), "scope": lambda: scope(a[1], a[2]), "unit": lambda: scope(a[1], a[2]), "issue": lambda: issue(*a[1:]), "inflight": lambda: inflight(*a[1:]), "done": lambda: donecmd(a[1], (a[a.index("--round") + 1] if "--round" in a else None)), "feedback": lambda: feedback(*a[1:]), "assume": lambda: assume(" ".join(a[1:])), "log": lambda: logmsg(" ".join(a[1:]))}
    if a[0] not in cmds: sys.exit(f"unknown command {a[0]}\n{__doc__}")
    if a[0] in ("init", "show", "next", "verify") and profile_error(): sys.exit("REFUSED: " + profile_error())
    if a[0] not in ("next", "verify"): cmds[a[0]]()
    else:   # method hints and tool lines name `dbcx <tool>`: print them as runnable launcher commands
        import contextlib, io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf): cmds[a[0]]()
        finally: sys.stdout.write(cli_text(buf.getvalue()))
