#!/usr/bin/env python3
"""Collect the claims of one scope into a register for the critics - with per-claim hashes, a per-round snapshot that
records the SOURCE FILE HASHES, the delta against the previous scored round, a compact critic pack, a coverage report of
table rows no claim points at, and (round >= 2) the reference-file delta since the previous round.

Usage: dbcx extract_claims <scope> [--round <n>]
  scope = unit name -> analysis/units/<scope>.json;  D1 -> analysis/inventory/inventory_run.json;  D3 | D4 -> analysis/consolidated/<scope>.json
  --round n = the gauntlet round the critics are about to score (default: existing round*-result.json count + 1)
Writes analysis/gauntlet/<scope>/
  claims.json, claims.md                  full register; every claim carries hash = sha1(statement | evidence | target)
  claims-round<n>.json                    snapshot for score_aggregate: claims + source_sha256/source_md_sha256 + row hashes of every table
  claims-delta.md, claims-delta-round<n>.md   round >= 2: claims to score (new / changed / previously below threshold) and carried claims
                                          with prior scores and the round in which each was LAST FULLY SCORED (carried = unexamined, not corroborated)
  critic-pack.md, critic-pack-round<n>.md what the critics read first: header with source hash + timestamp, key sections, register or delta
  per-pack standard critics (scoring.critics standard-<pack>, lead decision 7): every claim records `critics` (the ids that score
  it: common.claim_critics), and each standard-<pack> critic gets claims-<critic>.md, claims-delta-<critic>.md and
  critic-pack-<critic>.md (+ -round<n>) with only its claims; the plain files keep every claim (the client critic scores all)
  declared standard critics (method.json critics.standard, docs/SCORING.md §2): a critic standard-<id> with scores "all" gets
  every claim, one with topics the claims whose topic keys (common.claim_topics: scope kind, deliverable, sheet, resolved sections) name
  one of them - its own files as above; a method hook's claim routing narrows only the critics it owns. A claim no standard critic scores is an error
  (exit 1 before the register is written): the declaration is a method defect
  coverage-round<n>.md / .json            rows no claim targets (exact row-id match, engine/tools/rows.py), must-claim cells without a claim
                                          (method.json claims.must_claim), rows changed since the previous round; the register's
                                          `rows_without_claim` is filled here, never by the analyst
  reference-delta-round<n>.md             section-7 rows of reference/platform-standard.md dated after the previous round (round >= 2)
  quotes.json                             quote gate (claims.quotes): `dbcx evidence quotes <scope>` run here - under warn only when a claim
                                          carries a quote, under required always; its status per claim becomes the critic pack's `Quote check`
Guards: warns when the .md is newer than the .json (run md_to_json first); refuses (unless --force) when the scope's owner is
listed as running in STATUS in_flight (do not extract while the analyst still writes); clears a DIRTY marker left by an edit during a round.
Warnings (never blocking): claim cap - derived from the must-claim rows + scoring.claim_cap_reserve (5), bounded by
scoring.max_claims / max_claims_light / max_claims_consolidated (the fixed cap when the method declares no must-claim cells) -,
new claims after scoring.freeze_register_after_round.
"""
import json, os, sys, re, glob, hashlib, time, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, STATUS_PATH, WAVES_PATH, REF_DIR, project, method, spec, scope_info, scope_critics, is_consolidated, load_json, options, claim_options, claim_critics, method_hook, relp, declared_standard_critics, claim_topics, topic_critics, critic_role

def pack_sections(kind):
    ps = method().get("gauntlet", {}).get("pack_sections", {})
    if kind in ps: return ps[kind]
    SP, _ = spec(); k = SP.get(kind, {"sections": []})
    return [sec["heading"] for sec in k["sections"] if sec.get("type") in ("text", "kv")][:2] or ["Summary"]
# tables whose rows should be covered by a claim, with the field that identifies a row: method.json gauntlet.row_tables, else every table section of the kind with its first field
def row_tables(kind):
    rt = method().get("gauntlet", {}).get("row_tables", {})
    if kind in rt: return [tuple(x) for x in rt[kind]]
    SP, _ = spec(); k = SP.get(kind, {"sections": []})
    return [(sec["key"], next(iter(sec["fields"]))) for sec in k["sections"] if sec.get("type") == "table" and sec.get("key") not in ("claims", "open_questions") and sec.get("fields")]

def source(scope): return scope_info(scope)[0]

def sha(fp): return hashlib.sha256(open(fp, "rb").read()).hexdigest()
def chash(c): return hashlib.sha1("|".join([c["statement"].strip(), ";".join(x.strip() for x in c.get("evidence", [])), (c.get("target") or "").strip()]).encode("utf-8")).hexdigest()[:12]

def md_sections(md_path, wanted, max_rows=40):
    if not os.path.exists(md_path): return ""
    lines = open(md_path, encoding="utf-8").read().splitlines(); out = []; cur = None; buf = []
    def flush():
        if cur in wanted:
            body = [l for l in buf if not l.startswith("<!--")]
            if len(body) > max_rows: body = body[:max_rows] + [f"... ({len(body) - max_rows} more rows in the full analysis)"]
            out.append(f"## {cur} (from the analysis)\n" + "\n".join(body).strip())
    for l in lines:
        if l.startswith("## "):
            flush(); cur = l[3:].strip(); buf = []
        elif cur: buf.append(l)
    flush(); return "\n\n".join(out)

def table(claims, extra=None):
    rows = ["| id | type | target | statement | evidence |" + (" status |" if extra else ""), "|---|---|---|---|---|" + ("---|" if extra else "")]
    for c in claims: rows.append(f"| {c['id']} | {c['type']} | {c.get('target','')} | {c['statement'].replace('|','/')} | {'<br>'.join(c.get('evidence', []))} |" + (f" {extra[c['id']]} |" if extra else ""))
    return "\n".join(rows)

def coverage(kind, scope, data, prev_rows):
    """which rows does no claim target? Exact row-id match (engine/tools/rows.py) - a claim covers the rows its target names
    (`D2/Patched#<rid>`), never a row whose key merely occurs in its statement. Reported tables: method gauntlet.row_tables (else
    every table) plus every must-claim section."""
    import rows as R
    SP, _ = spec(); m = method()
    res = R.analyse(kind, data, SP, m, scope, assign=False)
    listed = [t for t, _ in row_tables(kind)] + [s for s, _, _, _ in (res["must_cells"] or []) if s not in [t for t, _ in row_tables(kind)]]
    rows_now = {}; report = []; uncovered_ids = []
    for t in dict.fromkeys(listed):
        ent = res["index"].get(t)
        if not ent or not ent["rows"]: continue
        uncov, changed = [], []
        for rid, row in ent["rows"].items():
            key = f"{t}#{rid}"; rows_now[key] = R.rhash(row)
            if (t, rid) not in res["covered"]: uncov.append(R.label(row, ent["keys"], rid)); uncovered_ids.append(key)
            if prev_rows and key in prev_rows and prev_rows[key] != rows_now[key]: changed.append(R.label(row, ent["keys"], rid))
            if prev_rows and key not in prev_rows: changed.append(R.label(row, ent["keys"], rid) + " (new)")
        report.append((t, len(ent["rows"]), uncov, changed))
    return rows_now, report, res, uncovered_ids

def reference_delta(since_ts):
    """Section-7 rows of reference/platform-standard.md whose Date is after since_ts (YYYY-MM-DD compare) - the standard moved."""
    p = os.path.join(REF_DIR, "platform-standard.md")
    if not os.path.exists(p) or not since_ts: return []
    since = since_ts[:10]; out = []; in7 = False
    for line in open(p, encoding="utf-8"):
        if line.startswith("## 7"): in7 = True; continue
        if in7 and line.startswith("## "): break
        if in7 and line.startswith("|") and not line.startswith("|---") and not re.match(r"\|\s*(Id\s*\|\s*)?Fact", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            dates = [c for c in cells if re.match(r"\d{4}-\d{2}-\d{2}", c)]
            if dates and dates[-1][:10] >= since: out.append(line.rstrip())
    return out

def owner_running(scope):
    e = owner_entry(scope)
    return e.get("agent") if e and not e.get("delivered") else None
def owner_entry(scope):
    """the scope's latest in_flight entry (delivered or not) - None when no agent of this run ever wrote the scope."""
    try: st = json.load(open(STATUS_PATH, encoding="utf-8"))
    except Exception: return None
    names = {scope_info(scope)[4]}
    return next((e for e in reversed(st.get("in_flight", []) or []) if e.get("agent") in names), None)

def main():
    scope = sys.argv[1]; a = sys.argv[2:]; p = project(); sc = p["scoring"]; critics = scope_critics(scope, p, routed=False); PASS = sc["pass_threshold"]   # the scope's own critics (one or none under profile lean); every declared critic, the routing below decides
    force = "--force" in a
    sj = source(scope); md_path = sj[:-5] + ".md"
    if not os.path.exists(sj): sys.exit(f"missing {relp(sj, ROOT)} - run `dbcx md_to_json` first")
    if os.path.exists(md_path) and os.path.getmtime(md_path) > os.path.getmtime(sj) + 1:
        msg = f"{relp(md_path, ROOT)} is NEWER than its .json - run `dbcx md_to_json` first or the critics judge text the deliverable will not contain"
        if force: print("WARNING: " + msg)
        else: sys.exit("REFUSED: " + msg + " (--force overrides)")
    who = owner_running(scope)
    if who and not force: sys.exit(f"REFUSED: STATUS in_flight lists {who} as still running on this scope - an extraction mid-edit produces a stale delta. Wait for the delivery test, mark it delivered, or pass --force.")
    # a DIRTY marker says the analysis was edited while a round was open. It would be deleted silently by the
    # very extraction it warns about, and the in_flight entry that also guarded the file is cleared by the delivery
    # sweep - so the marker has to refuse by itself; read it first, then --force once its claim is settled.
    dirty_path = os.path.join(ROOT, "analysis", "gauntlet", scope, "DIRTY")
    if os.path.exists(dirty_path) and not force:
        sys.exit(f"REFUSED: {relp(dirty_path, ROOT)} exists - the analysis was edited while a round was open, so this file may be a half-written round. Read the marker: it says what happened and whether the round is to be re-run. Extracting anyway (--force) deletes the marker and supersedes it.")
    # a file is not a delivery signal. When an agent of this run owns the scope (an in_flight entry
    # exists), refuse a file written seconds ago or after its delivery was marked - the author may still be writing.
    ent = owner_entry(scope)
    if ent and os.path.exists(md_path) and not force:
        age = time.time() - os.path.getmtime(md_path)
        if age < 60: sys.exit(f"REFUSED: {relp(md_path, ROOT)} was written {int(age)} s ago - its author may still be writing (a round was once extracted from a half-written file). The delivery signal is the agent's REPORT, not the file: extract after the report arrived, or pass --force.")
        try: dl = time.mktime(time.strptime(ent.get("delivered_at") or "", "%Y-%m-%dT%H:%M:%S"))
        except Exception: dl = None
        if dl and ent.get("delivered") and os.path.getmtime(md_path) > dl + 1: sys.exit(f"REFUSED: {relp(md_path, ROOT)} changed after {ent.get('agent')} was marked delivered at {ent.get('delivered_at')} (an analyst kept editing after its report). Ask the agent whether it is still working; when it has finished, `dbcx status inflight done {ent.get('agent')}` re-stamps the delivery, then extract - or pass --force.")
    data = json.load(open(sj, encoding="utf-8")); claims = data.get("claims", [])
    for c in claims: c["hash"] = chash(c)
    out_dir = os.path.join(ROOT, "analysis", "gauntlet", scope); os.makedirs(out_dir, exist_ok=True)
    done_rounds = sorted(int(m.group(1)) for f in os.listdir(out_dir) for m in [re.match(r"round(\d+)-result\.json", f)] if m)
    rnd = int(a[a.index("--round") + 1]) if "--round" in a else (done_rounds[-1] + 1 if done_rounds else 1)
    prev_snap = os.path.join(out_dir, f"claims-round{rnd - 1}.json"); reg = os.path.join(out_dir, "claims.json")
    if rnd > 1 and not os.path.exists(prev_snap) and os.path.exists(reg) and os.path.exists(os.path.join(out_dir, f"round{rnd - 1}-result.json")):
        old = json.load(open(reg, encoding="utf-8"))
        for c in old.get("claims", []): c.setdefault("hash", chash(c))
        json.dump(old, open(prev_snap, "w", encoding="utf-8"), ensure_ascii=False, indent=2); print(f"bootstrapped snapshot claims-round{rnd - 1}.json from the previous register")
    prev = json.load(open(prev_snap, encoding="utf-8")) if os.path.exists(prev_snap) else {}
    kind = scope_info(scope)[2]
    prev_rows = prev.get("rows") or {}
    if prev_rows and not any("#" in k for k in prev_rows): prev_rows = {}   # older snapshot keyed by row text: no row-level change report this once
    rows_now, cov, rres, rows_without_claim = coverage(kind, scope, data, prev_rows)
    per_pack = [cr for cr in critics if cr.startswith("standard-")]
    if per_pack:   # which critics score which claim: its option's pack critic (+ client); option-neutral claims every critic
        import rows as R
        st = {k: v for k, v in ((method().get("claims") or {}).get("sheet_tables") or {}).items() if not k.startswith("_")}
        def rows_of(part): return [rres["index"][sec]["rows"][rid] for sec, rid in R.resolve_target(part, kind, rres["index"], st)[0]]
        ids = [o["id"] for o in options(p)]; hk = method_hook("critics", p["_method"])   # a method's own routing (tech-fit-estimation: the system named by the target)
        dc = {d["critic"] for d in declared_standard_critics(p) if d["critic"] != "standard"} & set(critics); unrouted = []   # declared discipline critics follow their topics
        for c in claims:
            x = hk.claim_critics(c, scope, critics, p) if hk and hasattr(hk, "claim_critics") else None
            c["critics"] = [cr for cr in critics if cr in set(x) or cr in dc] if x is not None else claim_critics(critics, claim_options(c, ids, rows_of), p)
            if dc:   # a hook narrows only the critics it owns; the declared ones follow their topics
                mine = topic_critics(claim_topics(c, kind, rres["index"], st), critics, p); c["critics"] = [cr for cr in c["critics"] if cr not in dc or cr in mine]
                if x is None and not any(critic_role(cr) == "critic-standard" for cr in c["critics"]): unrouted.append(f"{c['id']} (target {c.get('target') or '-'})")
        if unrouted: sys.exit(f"ERROR: {len(unrouted)} claim(s) of {scope} reach no standard critic - no declared topic matches and no standard critic scores all (method.json critics.standard: add the topic, or a critic with scores \"all\"; docs/SCORING.md §2): " + "; ".join(unrouted))
    def applicable(c): return c.get("critics") or critics
    def share(cr): return "its topics" if cr in {d["critic"] for d in declared_standard_critics(p)} else "its options + option-neutral"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S"); src_sha = sha(sj); md_sha = sha(md_path) if os.path.exists(md_path) else None
    register = {"scope": scope, "source": relp(sj, ROOT), "source_sha256": src_sha, "source_md_sha256": md_sha, "extracted_at": stamp, "round": rnd, "analysis_round_field": data.get("round", 0), "claims": claims, "rows": rows_now,
                "rows_without_claim": rows_without_claim, "must_claim_uncovered": [f"{t}#{r}.{f}" for t, r, f, _ in rres["must_uncovered"]]}
    json.dump(register, open(reg, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(register, open(os.path.join(out_dir, f"claims-round{rnd}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "claims.md"), "w", encoding="utf-8") as f: f.write(f"# Claims register: {scope} (critic round {rnd}, {len(claims)} claims)\n\nSource `{relp(md_path, ROOT)}` sha256 {md_sha[:12] if md_sha else '-'} extracted {stamp}\n\n" + table(claims) + "\n")
    dirty = os.path.join(out_dir, "DIRTY")
    if os.path.exists(dirty): os.remove(dirty); print("cleared DIRTY marker (the analysis had been edited during the round; this extraction supersedes it)")
    # caps
    light = any(m.get("light_pass") for w in load_json(WAVES_PATH, {"waves": []})["waves"] for m in w["members"] if m["name"] == scope)
    bound = sc.get("max_claims_light", 10) if light else sc.get("max_claims", 40)
    bound = sc.get("max_claims_consolidated", 120) if is_consolidated(scope) else bound
    # the cap follows the client-visible verdict rows - must-claim rows + a small reserve, the fixed cap stays the upper bound
    import rows as R
    cap = R.derived_cap(len(rres["must_rows"]), bound, sc) if rres["must_rows"] is not None else bound
    cap_rule = f"{len(rres['must_rows'])} must-claim rows + reserve {sc.get('claim_cap_reserve', 5)}, at most {bound}" if rres["must_rows"] is not None else f"fixed cap ({'light pass' if light else 'full pass'})"
    prev_ids = {c["id"] for c in prev.get("claims", [])} if prev else set()
    added = [c["id"] for c in claims if c["id"] not in prev_ids] if prev_ids else [c["id"] for c in claims]
    if len(claims) > cap and (rnd == 1 or (prev_ids and len(added) > 0 and len(claims) > len(prev_ids))):
        print(f"WARNING: {len(claims)} claims exceed the cap of {cap} for this scope ({cap_rule}); {len(added)} added this round - claims go to the must-claim rows first; the analyst drops or merges, not adds (no action if the excess predates the cap)")
    elif len(claims) > cap: print(f"note: {len(claims)} claims above the cap of {cap} were all present before this round - no action")
    # per-pack standard critics read only their claims (the plain files are the full register)
    variants = [("", lambda c: True)] + [(f"-{cr}", lambda c, cr=cr: cr in applicable(c)) for cr in per_pack]
    for sfx, keep in variants[1:]:
        sub = [c for c in claims if keep(c)]
        with open(os.path.join(out_dir, f"claims{sfx}.md"), "w", encoding="utf-8") as f: f.write(f"# Claims register: {scope} - critic {sfx[1:]} (critic round {rnd}, {len(sub)} of {len(claims)} claims: {share(sfx[1:])})\n\nSource `{relp(md_path, ROOT)}` sha256 {md_sha[:12] if md_sha else '-'} extracted {stamp}\n\n" + table(sub) + "\n")
    # delta + last-fully-scored round per claim
    to_score, carried, status, last_full = [], [], {}, {}
    prev_scores = {}
    for r in range(1, rnd):
        for cr in critics:
            fp = os.path.join(out_dir, f"round{r}-{cr}.json")
            if os.path.exists(fp):
                for s in json.load(open(fp, encoding="utf-8"))["scores"]:
                    prev_scores.setdefault(r, {}).setdefault(s["claim_id"], {})[cr] = s["score"]
                    if not s.get("carried_from_round"): last_full[s["claim_id"]] = max(last_full.get(s["claim_id"], 0), r)
    if rnd > 1 and prev:
        pv = {c["id"]: c for c in prev["claims"]}; ps_prev = prev_scores.get(rnd - 1, {})
        rp = os.path.join(out_dir, f"round{rnd - 1}-result.json")   # disputes the previous round routed (score_aggregate `routed`) go to their critic's delta
        routed = {x["claim_id"]: x for x in (json.load(open(rp, encoding="utf-8")).get("routed") or [] if os.path.exists(rp) else [])}
        for c in claims:
            pc = pv.get(c["id"]); ps = ps_prev.get(c["id"], {})
            if not pc: status[c["id"]] = "new"; to_score.append(c)
            elif c["id"] in routed: x = routed[c["id"]]; status[c["id"]] = f"dispute of the {x['from']} critic routed to {', '.join(x['to']) or '-'} ({x.get('ground')}): {x.get('issue', '')[:160]} - answer it: confirm the statement with its evidence, or correct the reference row"; to_score.append(c)
            elif pc.get("hash") != c["hash"]: status[c["id"]] = f"changed - re-score the WHOLE statement, not only the diff (last fully scored: round {last_full.get(c['id'], '-')})"; to_score.append(c)
            elif len(ps) < len(applicable(c)) or any(v < PASS for v in ps.values()): status[c["id"]] = "unchanged, was below threshold - score again (analyst disputes or overlooked it)"; to_score.append(c)
            else: carried.append((c, ps))
        removed = sorted(set(pv) - {c["id"] for c in claims})
        freeze = sc.get("freeze_register_after_round", 2)
        if rnd > freeze and any(v == "new" for v in status.values()): print(f"WARNING: register frozen after round {freeze}, but {sum(1 for v in status.values() if v == 'new')} new claims appeared in round {rnd}: " + ", ".join(k for k, v in status.items() if v == "new"))
        for sfx, keep in variants:
            ts = [c for c in to_score if keep(c)]; ca = [(c, ps) for c, ps in carried if keep(c)]
            delta = [f"# Claims delta: {scope} round {rnd} (vs. round {rnd - 1})" + (f" - critic {sfx[1:]}" if sfx else ""), "", f"Source `{relp(md_path, ROOT)}` sha256 {md_sha[:12] if md_sha else '-'} extracted {stamp}. If the file you open carries other text than this delta, STOP and tell the orchestrator (stale pack).", "",
                     f"## Claims to score ({len(ts)})", "", table(ts, status) if ts else "(none)", "",
                     f"## Carried claims ({len(ca)}) - unchanged since round {rnd - 1} and passed by every critic; score_aggregate carries the previous score forward.", "",
                     "A carried score records WHEN a claim was last examined, not how deeply: nothing was re-read since the round named. Re-score one only with new counter-evidence (say so in `issue`); open the evidence cells of the sample your brief names.", ""]
            delta += [f"- {c['id']}: " + ", ".join(f"{cr} {ps.get(cr)}" for cr in applicable(c)) + f" (last fully scored: round {last_full.get(c['id'], '-')}) - {c['statement'][:110].replace(chr(10),' ')}..." for c, ps in ca]
            if removed: delta += ["", f"## Removed since round {rnd - 1} ({len(removed)}): " + ", ".join(removed) + " (must be logged via `supersedes`)"]
            txt = "\n".join(delta) + "\n"
            open(os.path.join(out_dir, f"claims-delta{sfx}.md"), "w", encoding="utf-8").write(txt); open(os.path.join(out_dir, f"claims-delta{sfx}-round{rnd}.md"), "w", encoding="utf-8").write(txt)
        print(f"delta: {len(to_score)} to score ({sum(1 for v in status.values() if v=='new')} new, {sum(1 for v in status.values() if v.startswith('changed'))} changed), {len(carried)} carried, {len(removed)} removed")
    # coverage report
    covp = os.path.join(out_dir, f"coverage-round{rnd}.md"); cov_lines = [f"# Coverage report: {scope} round {rnd} - table rows no claim targets", "", "The gauntlet grades claim STATEMENTS. A claim covers exactly the rows its target names (`<D>/<Sheet>#<rid>`; exact row-id match, engine/tools/rows.py). Rows below have no claim targeting them, so no critic is obliged to read them. Critics: open a sample; orchestrator: put changed rows into the next brief by hand.", ""]
    n_uncov = 0
    if rres["must_cells"] is not None:
        mu = rres["must_uncovered"]
        cov_lines += [f"## Must-claim cells without a claim: {len(mu)} of {len(rres['must_cells'])} (claim cap {cap}: {cap_rule})"] + ([f"- {t}#{r}.{f} = {str(v)[:60]}" for t, r, f, v in mu[:60]] + ([f"- ... (+{len(mu) - 60})"] if len(mu) > 60 else []) if mu else ["- (none - every client-visible verdict row is claim-backed)"]) + [""]
    for t, n, uncov, changed in cov:
        n_uncov += len(uncov); cov_lines.append(f"## {t}: {n} rows, {len(uncov)} without a citing claim" + (f", {len(changed)} changed/new since round {rnd - 1}" if prev else ""))
        if uncov: cov_lines.append("- uncovered: " + "; ".join(uncov[:40]) + (f" ... (+{len(uncov) - 40})" if len(uncov) > 40 else ""))
        if changed: cov_lines.append("- CHANGED since previous round (read these first): " + "; ".join(changed[:40]))
        cov_lines.append("")
    if rres["unresolved"]: cov_lines += [f"## Target rows that name no row ({len(rres['unresolved'])})"] + [f"- {cid}: {ref}" for cid, ref in rres["unresolved"][:40]] + [""]
    if data.get("rows_without_claim"): cov_lines += ["Note: the analysis' own `Rows without claim` list is ignored - this report is computed.", ""]
    open(covp, "w", encoding="utf-8").write("\n".join(cov_lines) + "\n")
    json.dump({"scope": scope, "round": rnd, "claim_cap": cap, "cap_rule": cap_rule, "rows_without_claim": rows_without_claim, "must_claim_cells": len(rres["must_cells"] or []), "must_claim_uncovered": [f"{t}#{r}.{f}" for t, r, f, _ in rres["must_uncovered"]], "unresolved_targets": [f"{c}: {r}" for c, r in rres["unresolved"]], "tables": {t: {"rows": n, "uncovered": len(u)} for t, n, u, _ in cov}}, open(covp[:-3] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # reference delta (round >= 2): rows dated after the previous round's aggregation
    ref_rows = []
    if rnd > 1:
        pres = os.path.join(out_dir, f"round{rnd - 1}-result.json"); since = None
        if os.path.exists(pres):
            try: since = json.load(open(pres, encoding="utf-8")).get("aggregated_at")
            except Exception: since = None
            since = since or time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(pres)))
        ref_rows = reference_delta(since)
        open(os.path.join(out_dir, f"reference-delta-round{rnd}.md"), "w", encoding="utf-8").write(f"# Reference delta: section-7 rows of reference/platform-standard.md dated on/after {since[:10] if since else '-'}\n\nThe standard a claim was judged against may have moved. Any carried claim these rows narrow or contradict must be re-scored (name it in `issue`).\n\n" + ("\n".join(ref_rows) if ref_rows else "(none)") + "\n")
    # quote gate: the mechanical existence check the critics build on
    import evidence; qmode = evidence.quotes_mode(p); qp = os.path.join(out_dir, "quotes.json")
    qall = qmode == "required" or sc.get("pass_rule") == "defects+quotes"   # the lean pass rule always needs the quote result
    quotes = evidence.quotes_scope(scope, p) if qall or (qmode == "warn" and any(c.get("quote") for c in claims)) else None
    if quotes: print("quote check: " + ", ".join(f"{v} {k}" for k, v in quotes["counts"].items()) + f" -> analysis/gauntlet/{scope}/quotes.json")
    elif os.path.exists(qp): os.remove(qp)   # no quote left to check: a stale result must not reach the pass rule
    # critic pack
    for sfx, keep in variants:
        cl = [c for c in claims if keep(c)]; ts = [c for c in to_score if keep(c)]; ca = [(c, ps) for c, ps in carried if keep(c)]
        pack = [f"# Critic pack: {scope} / round {rnd}" + (f" - critic {sfx[1:]} ({len(cl)} of {len(claims)} claims: {share(sfx[1:])})" if sfx else ""), f"SOURCE: `{relp(md_path, ROOT)}` sha256 `{md_sha[:12] if md_sha else '-'}` (json `{src_sha[:12]}`), extracted {stamp}. The LIVE file is the text under judgement; this pack is a snapshot. If they differ, tell the orchestrator before scoring.",
                f"Full analysis: open it only for the rows a claim points to; everything you must score is below. Register: `analysis/gauntlet/{scope}/claims{sfx}.md` ({len(cl)} claims)" + (f"; delta: `analysis/gauntlet/{scope}/claims-delta{sfx}.md`" if rnd > 1 else "") + f"; coverage report: `analysis/gauntlet/{scope}/coverage-round{rnd}.md` ({n_uncov} table rows without a citing claim" + (f", {len(rres['must_uncovered'])} must-claim cells uncovered" if rres['must_cells'] is not None else "") + " - open a sample)" + (f"; reference delta: `analysis/gauntlet/{scope}/reference-delta-round{rnd}.md` ({len(ref_rows)} rows)" if rnd > 1 else ""),
                "", md_sections(md_path, pack_sections(kind))]
        if rnd > 1 and prev:
            pack += ["", f"## Claims to score in round {rnd} ({len(ts)})", "", table(ts, status) if ts else "(none - every claim is carried; write a summary that says so)", "", f"## Carried (not re-scored, {len(ca)})", ""] + [f"- {c['id']}: " + ", ".join(f"{cr} {ps.get(cr)}" for cr in applicable(c)) + f" (last fully scored r{last_full.get(c['id'], '-')})" for c, ps in ca]
            if ref_rows: pack += ["", f"## Reference rows added/changed since round {rnd - 1} ({len(ref_rows)}) - re-score any carried claim they narrow", ""] + ref_rows
        else: pack += ["", f"## Claims to score ({len(cl)})", "", table(cl)]
        if quotes: pack += ["", evidence.quote_section(quotes, {c["id"] for c in cl})]
        txt = "\n".join(pack) + "\n"
        open(os.path.join(out_dir, f"critic-pack{sfx}.md"), "w", encoding="utf-8").write(txt); open(os.path.join(out_dir, f"critic-pack{sfx}-round{rnd}.md"), "w", encoding="utf-8").write(txt)
    print(f"{len(claims)} claims -> analysis/gauntlet/{scope}/claims.md, critic-pack.md (round {rnd}, source sha {src_sha[:12]}); coverage: {n_uncov} uncovered rows" + (f", {len(rres['must_uncovered'])} of {len(rres['must_cells'])} must-claim cells uncovered, claim cap {cap}" if rres['must_cells'] is not None else "") + (f"; reference delta rows: {len(ref_rows)}" if rnd > 1 else ""))

if __name__ == "__main__":
    main()
