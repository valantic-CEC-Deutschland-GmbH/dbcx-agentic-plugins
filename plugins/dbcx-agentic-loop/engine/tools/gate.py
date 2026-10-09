#!/usr/bin/env python3
"""Final-gate helpers (G4-G10): key questions, round snapshots, the verifier's sample, lead decisions, the round diff.

Usage:
  dbcx gate questions [<persona>] [--round <n>]     the key questions each persona scores in round n (default: the next round) - run/engagement ->
                                                    method -> engine defaults, then the recorded question changes
  dbcx gate question <persona> <qid> --reword "<new text>" --why "<reason>" [--feedback <client_id>]
  dbcx gate question <persona> <qid> --dismiss --why "<reason>" [--feedback <client_id>]
  dbcx gate question <persona> <qid> --keep --why "<reason>" --feedback <client_id>
                                                    the orchestrator's answer to the lead's question feedback (inbox kind gate_question_feedback):
                                                    its own wording (never the lead's), the question dropped, or unchanged with a reason. Applies from
                                                    the first round whose persona briefs are not rendered yet; --feedback closes the inbox entry
  dbcx gate snapshot <round>                        copy the customer workbooks to analysis/gate/round<n>-workbooks/ (once per round)
  dbcx gate sample <round> [--per <n>]              analysis/gate/round<n>-verifier-sample.md: ~15 rows per deliverable, stratified
                                                    (figures, verdicts, security rows, 'Annahme' rows, 'Code' rows), drawn by the tool
  dbcx gate diff <round> [--against <k>]            changed cells between two rounds' customer workbooks (gate_diff)
  dbcx gate decide <round> <cluster> "<decision>" [--by lead]   record the lead's decision on a fix-plan cluster (a major with a
                                                    recorded decision no longer blocks the pass; a blocker always does); then
                                                    re-run `dbcx gate_aggregate <round>`
  dbcx gate decisions [<round>]                     list recorded decisions
Lead decisions live in state/STATUS.json -> phases.<gate phase>.decisions[] ({round, cluster, key, text, by, at}); a decision carries
to a later round's cluster with the same key (deliverable | sheet | kind).
Question changes live in phases.<gate phase>.question_changes[] ({persona, question_id, action reword|dismiss|keep, text, why, feedback,
feedback_text, intent, from_round, at, by}); `key_questions(cfg, persona, rnd)` applies every change with from_round <= rnd in order.
A method may vary its questions by run shape: method.json gate.key_questions_when [{when: <spec flag(s)>, key_questions}] - the first block
whose flags hold (datasets.spec_context) replaces gate.key_questions.
"""
import glob, hashlib, json, os, random, re, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, DEFAULTS, P, CLI, project, read_json, load_json, load_inbox, relp

def lang(cfg): return cfg["languages"]["deliverable"]
def text_of(t, cfg): return t.get(lang(cfg)) or t.get("en") or t.get("de") or next(iter(t.values()), "") if isinstance(t, dict) else str(t)

def enabled(cfg):
    """{deliverable key: file} of the enabled workbooks"""
    return {k: v["file"] for k, v in (cfg.get("deliverables") or {}).items() if isinstance(v, dict) and v.get("enabled") and str(v.get("file", "")).endswith(".xlsx")}

def key_questions(cfg, persona, rnd=None):
    """[{id, text, deliverables (keys), tags}] a persona scores in round `rnd` (None = the next round): run/engagement gate.key_questions ->
    method -> engine defaults ('*' last), then every question change with from_round <= rnd (reword replaces the text, dismiss drops it)"""
    m = cfg["_method"].get("gate") or {}; eng = read_json(os.path.join(DEFAULTS, "gate.defaults.json"), {})
    for src in ((cfg.get("gate") or {}).get("key_questions") or {}, method_questions(cfg, m), eng.get("key_questions") or {}):
        qs = src.get(persona) or src.get("*")
        if qs: break
    en = enabled(cfg); out = []
    for q in qs or []:
        dl = [k for k in en] if "*" in q.get("deliverables", ["*"]) else [k for k in q["deliverables"] if k in en]
        out.append({"id": q["id"], "text": text_of(q["text"], cfg), "deliverables": dl, "tags": q.get("tags", [])})
    rnd = next_round() if rnd is None else int(rnd)
    for c in question_changes(cfg):
        if c["persona"] != persona or c["from_round"] > rnd: continue
        if c["action"] == "dismiss": out = [q for q in out if q["id"] != c["question_id"]]
        elif c["action"] == "reword": out = [dict(q, text=c["text"]) if q["id"] == c["question_id"] else q for q in out]
    return out

def method_questions(cfg, m):
    """the method's key questions: the first `key_questions_when` block [{when, key_questions}] whose `when` holds on the method's spec
    flags (datasets.spec_context - e.g. one scenario vs several), else `key_questions`"""
    if m.get("key_questions_when"):
        from common import spec_context
        from xl_spec import when_holds
        flags = (spec_context(cfg) or {}).get("flags") or {}
        for v in m["key_questions_when"]:
            if isinstance(v, dict) and when_holds(v.get("when"), flags): return v.get("key_questions") or {}
    return m.get("key_questions") or {}

def started_rounds():
    """gate rounds whose persona briefs are rendered or whose persona scores exist (a round in progress is never changed)"""
    rs = {int(m.group(1)) for f in glob.glob(P("analysis", "briefs", "gate-*-r*.md")) if (m := re.search(r"-r(\d+)\.md$", f))}
    rs |= {int(m.group(1)) for f in glob.glob(P("analysis", "gate", "round*-*.json")) if (m := re.match(r"round(\d+)-(?!hygiene|result|fixplan)", os.path.basename(f)))}
    return rs

def next_round(): return max(started_rounds(), default=0) + 1

def customer_files(cfg, keys=None):
    return {k: f"deliverables/{f}" for k, f in enabled(cfg).items() if (keys is None or k in keys) and os.path.exists(P("deliverables", f))}

def latest_render(cfg, keys=None):
    """{key: work/render/<latest date>/<key>} for rendered customer workbooks newer than the workbook itself"""
    dates = sorted(os.path.basename(d) for d in glob.glob(P("work", "render", "*")) if os.path.isdir(d))
    out = {}
    for k, f in customer_files(cfg, keys).items():
        for d in reversed(dates):
            rd = P("work", "render", d, k)
            if glob.glob(os.path.join(rd, "*.pdf")) and os.path.getmtime(P(f)) <= max(os.path.getmtime(x) for x in glob.glob(os.path.join(rd, "*"))) + 5:
                out[k] = relp(rd, ROOT); break
    return out

def snapshot(rnd, cfg=None):
    """copy the customer workbooks the round reads to analysis/gate/round<n>-workbooks/ (kept once per round: the diff base of the next)"""
    cfg = cfg or project(); d = P("analysis", "gate", f"round{rnd}-workbooks")
    if os.path.isdir(d) and glob.glob(os.path.join(d, "*.xlsx")): return d, False
    os.makedirs(d, exist_ok=True); man = {}
    for k, f in customer_files(cfg).items():
        shutil.copy2(P(f), d); man[os.path.basename(f)] = hashlib.sha256(open(P(f), "rb").read()).hexdigest()
    json.dump({"round": rnd, "taken_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "sha256": man}, open(os.path.join(d, "manifest.json"), "w", encoding="utf-8"), indent=1)
    return d, True

# ------------------------------------------------------------------ verifier sample
STRATA = (("figure", 3), ("verdict", 5), ("security", 2), ("assumption", 3), ("code", 2))
SKIP = re.compile(r"^(README|Uebersicht|Übersicht|Overview|Quellen|Sources|Parameter|Annahmen|Assumptions|Aussagen|Claims|Offene_Fragen|Open_Questions|INTERIM)", re.I)
VERDICT_HDR = re.compile(r"Urteil|Empfehlung|Disposition|Auswirkung|Klassifizierung|Unterstützung|Status|Verdict|Recommendation|Impact|Support|Classification", re.I)
SECURITY = re.compile(r"Sicherheit|security|XSS|CSRF|Injection|Passwort|password|Secret|Credential|Token", re.I)

def sample(rnd, per=15, cfg=None):
    import openpyxl
    from lint_deliverable import REPO_LOC, ASSUMPTION_REF, LOCATOR_HEADERS, _rgb, _style, _spec, header_row, qualified
    from xl_transform import VENDOR_CODE_RE
    cfg = cfg or project(); sp = _spec(); decision_fill = _style(sp)["tiers"]["decision"]
    strata = tuple((str(k), int(n)) for k, n in ((cfg.get("gate") or {}).get("verifier_strata") or STRATA))   # a method / run may drop a stratum (a row of it counts as `other`)
    out = [f"# Verifier sample, round {rnd}", "", f"Drawn by `dbcx gate sample {rnd}` (stratified, seeded by round and workbook - not chosen by the verifier). Check every row in order; a row you cannot open counts as `no-locator`.", ""]
    total = 0
    for key, f in customer_files(cfg).items():
        wb = openpyxl.load_workbook(P(f)); rng = random.Random(f"{rnd}-{os.path.basename(f)}"); pool = {s: {} for s, _ in strata}; pool["other"] = {}
        vc = bool(((sp.get("deliverables") or {}).get(key) or {}).get("vendor_code_basis"))   # vendor standard code is no client code: never the code stratum
        for ws in wb:
            if re.match(r"Management|Summary", ws.title, re.I):
                for r in ws.iter_rows(min_row=2):
                    if len(r) > 1 and isinstance(r[1].value, str) and r[1].value.startswith("=") and r[0].value:
                        pool["figure" if "figure" in pool else "other"].setdefault(ws.title, []).append((f"{ws.title}!B{r[1].row}", str(r[0].value), r[1].value[:120]))
                continue
            hr = header_row(ws)   # 2 below option band headers
            if SKIP.match(ws.title) or ws.max_row < hr + 1: continue
            hdr = qualified(ws, hr, [str(c.value or "") for c in ws[hr]]); fills = [_rgb(c.fill.fgColor) if c.fill is not None and c.fill.fill_type else None for c in ws[hr]]
            vcols = [i for i, h in enumerate(hdr) if fills[i] == decision_fill] or [i for i, h in enumerate(hdr) if VERDICT_HDR.search(h)]
            bcols = [i for i, h in enumerate(hdr) if re.search(r"(?:^|[\s:·–—-])(?:Grundlage|Basis)$", h)]   # one per option block below bands
            for r in ws.iter_rows(min_row=hr + 1):
                if not r or r[0].value in (None, ""): continue
                shown = [(hdr[i], c.value) for i, c in enumerate(r) if i < len(hdr) and c.value not in (None, "") and not str(c.value).startswith("=")]
                text = " | ".join(f"{h}: {v}" for h, v in shown); prose = " ".join(str(v) for h, v in shown if not LOCATOR_HEADERS.search(h))
                row = (f"{ws.title}!{r[0].row}", str(r[0].value), text[:300]); basis = " + ".join(str(r[i].value or "") for i in bcols if i < len(r))
                s = ("assumption" if "Annahme" in basis or "Assumption" in basis or ASSUMPTION_REF.search(prose) else "security" if SECURITY.search(prose)
                     else "verdict" if any(i < len(r) and r[i].value not in (None, "") for i in vcols) else "code" if "Code" in basis or REPO_LOC.search(VENDOR_CODE_RE.sub("", text) if vc else text) else "other")
                pool[s if s in pool else "other"].setdefault(ws.title, []).append(row)
        def draw(by_sheet, n):   # round-robin over sheets, so one long sheet cannot take the whole stratum
            for rows in by_sheet.values(): rng.shuffle(rows)
            got, sheets = [], sorted(by_sheet)
            while len(got) < n and any(by_sheet[x] for x in sheets):
                for x in sheets:
                    if by_sheet[x] and len(got) < n: got.append(by_sheet[x].pop())
            return got
        picked = [(s,) + x for s, n in strata for x in draw(pool[s], n)]
        rest = {f"{s}:{sh}": [(s,) + x for x in rows] for s in pool for sh, rows in pool[s].items()}
        picked += draw(rest, max(0, per - len(picked)))
        out += [f"## {key} – {f}", "", "| # | stratum | location | row id | content (as shown) |", "|---|---|---|---|---|"]
        out += [f"| {i} | {s} | {loc} | {rid} | {txt.replace('|', '/')} |" for i, (s, loc, rid, txt) in enumerate(picked[:per], 1)] + [""]
        total += len(picked[:per])
    p = P("analysis", "gate", f"round{rnd}-verifier-sample.md"); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
    return p, total

# ------------------------------------------------------------------ lead decisions (state/STATUS.json -> phases.<gate>.decisions)
def gate_phase(cfg=None):
    cfg = cfg or project(); return next((ph["id"] for ph in cfg["_method"].get("phases", []) if ph.get("type") == "gate"), "final_gate")

def decisions(cfg=None):
    st = load_json("state/STATUS.json", {}) or {}
    return ((st.get("phases") or {}).get(gate_phase(cfg)) or {}).get("decisions", [])

def max_rounds(cfg=None):
    """scoring.max_gate_rounds of the run (run.json wins), else the STATUS copy taken at init, else 3 - the one source for status, progress and the dashboard"""
    cfg = cfg or project(); v = (cfg.get("scoring") or {}).get("max_gate_rounds")
    return int(v if v is not None else (load_json("state/STATUS.json", {}) or {}).get("max_gate_rounds", 3))

def question_changes(cfg=None):
    st = load_json("state/STATUS.json", {}) or {}
    return ((st.get("phases") or {}).get(gate_phase(cfg)) or {}).get("question_changes", [])

def norm(t): return " ".join(re.findall(r"\w+", (t or "").lower()))

def change_question(cfg, persona, qid, action, why, text=None, feedback=None, by="orchestrator"):
    """record a question change (reword | dismiss | keep) from the next round on; --feedback closes the lead's inbox entry with the outcome"""
    import status, inbox
    if persona not in cfg["scoring"]["gate_personas"]: sys.exit(f"{persona} is not a gate persona ({', '.join(cfg['scoring']['gate_personas'])})")
    if not (why or "").strip(): sys.exit("--why \"<reason>\" is required: the lead reads why the question changed (or did not)")
    if action == "reword" and not (text or "").strip(): sys.exit("--reword needs the new wording")
    if action == "keep" and not feedback: sys.exit("--keep closes a lead feedback: --feedback <client_id>")
    rnd = next_round(); qs = {q["id"]: q for q in key_questions(cfg, persona, rnd)}
    if qid not in qs and action != "keep": sys.exit(f"{persona} {qid} is not asked in round {rnd} (`{CLI} gate questions {persona} --round {rnd}`)")
    e = None
    if feedback:
        e = next((x for x in load_inbox() if x.get("client_id", "").startswith(feedback)), None)
        if not e or e.get("kind") != "gate_question_feedback": sys.exit(f"no gate question feedback {feedback} in the inbox")
        if e.get("processed"): sys.exit(f"{feedback} already processed ({e.get('outcome', '')})")
        if (e.get("persona"), e.get("question_id")) != (persona, qid): sys.exit(f"{feedback} is feedback on {e.get('persona')} {e.get('question_id')}, not {persona} {qid}")
        if action == "reword" and norm(text) == norm(e.get("text")): sys.exit("REFUSED: the new wording is the lead's text - react to the feedback and write the question yourself")
    s = status.load(); ph = s["phases"].setdefault(gate_phase(cfg), {}); cs = ph.setdefault("question_changes", [])
    cs.append({"persona": persona, "question_id": qid, "action": action, "text": text if action == "reword" else None, "why": why.strip(), "feedback": e["client_id"] if e else None,
               "feedback_text": e.get("text") if e else None, "intent": e.get("intent") if e else None, "from_round": rnd, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": by}); status.save(s)
    if e: inbox.mark(e["client_id"], f"{action}: {why.strip()}" + (f" (from round {rnd})" if action != "keep" else ""))
    print(f"recorded {action} of {persona} {qid}" + (f" from round {rnd}" if action != "keep" else " (unchanged)") + (f"; closed feedback {e['client_id'][:8]}" if e else ""))

def decide(rnd, cluster, text, by="lead"):
    import status
    fp = P("analysis", "gate", f"round{rnd}-fixplan.json")
    if not os.path.exists(fp): sys.exit(f"no fix plan for round {rnd} (dbcx gate_aggregate {rnd} first)")
    cl = next((c for c in read_json(fp)["clusters"] if c["id"] == cluster), None)
    if not cl: sys.exit(f"cluster {cluster} is not in {relp(fp, ROOT)}")
    s = status.load(); ph = s["phases"].setdefault(gate_phase(), {}); ds = ph.setdefault("decisions", [])
    ds[:] = [d for d in ds if not (d["round"] == rnd and d["cluster"] == cluster)]
    ds.append({"round": rnd, "cluster": cluster, "key": cl["key"], "severity": cl["severity"], "text": text, "by": by, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}); status.save(s)
    print(f"recorded {by} decision on {cluster} ({cl['severity']}: {cl['title'][:80]}) - re-run `dbcx gate_aggregate {rnd}`" + ("; a blocker still blocks the pass - it must be fixed" if cl["severity"] == "blocker" else ""))

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]; cfg = project()
    if cmd == "questions":
        rnd = int(a[a.index("--round") + 1]) if "--round" in a else next_round(); rest = [x for i, x in enumerate(a[1:], 1) if x != "--round" and a[i - 1] != "--round"]
        print(f"round {rnd}")
        for p in (rest[:1] or cfg["scoring"]["gate_personas"]):
            print(p); [print(f"  {q['id']} [{', '.join(q['deliverables'])}] ({'/'.join(q['tags'])}) {q['text']}") for q in key_questions(cfg, p, rnd)]
    elif cmd == "question":
        opt = lambda f: a[a.index(f) + 1] if f in a and a.index(f) + 1 < len(a) else None
        acts = [x for x in ("reword", "dismiss", "keep") if f"--{x}" in a]
        if len(a) < 3 or len(acts) != 1: sys.exit(__doc__)
        change_question(cfg, a[1], a[2], acts[0], opt("--why"), opt("--reword"), opt("--feedback"), opt("--by") or "orchestrator")
    elif cmd == "snapshot": d, new = snapshot(int(a[1]), cfg); print(("took " if new else "kept ") + relp(d, ROOT))
    elif cmd == "sample":
        p, n = sample(int(a[1]), int(a[a.index("--per") + 1]) if "--per" in a else 15, cfg); print(f"wrote {relp(p, ROOT)} ({n} rows)")
    elif cmd == "diff":
        import gate_diff; gate_diff.diff(int(a[1]), int(a[a.index("--against") + 1]) if "--against" in a else None)
    elif cmd == "decide":
        by = a[a.index("--by") + 1] if "--by" in a else "lead"; rest = [x for i, x in enumerate(a) if x != "--by" and (i == 0 or a[i - 1] != "--by")]
        decide(int(rest[1]), rest[2], " ".join(rest[3:]), by)
    elif cmd == "decisions":
        for d in decisions(cfg):
            if len(a) < 2 or str(d["round"]) == a[1]: print(f"  r{d['round']} {d['cluster']} [{d.get('severity')}] {d['by']} {d['at']}: {d['text']}")
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
