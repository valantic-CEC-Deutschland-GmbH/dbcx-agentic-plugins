#!/usr/bin/env python3
"""Aggregate critic scores for a scope/round, decide pass/fail, write the ranked issue list, update STATUS.json.

Usage: dbcx score_aggregate <scope> <round> [--dry-run [--rule defects|defects+quotes|mean]] [--force]
  --rule (dry runs only) computes the round under the other pass rule - what that rule would have decided; nothing is written
Reads  analysis/gauntlet/<scope>/round<n>-<critic>.json for every critic of the scope (scoring.phase_critics[inventory|consolidation|scopes], else scoring.critics)
       analysis/gauntlet/<scope>/claims-round<n>.json (snapshot with source hashes) + earlier snapshots and score files for carry-forward
Writes analysis/gauntlet/<scope>/round<n>-result.json, round<n>-issues.md, appends estate observations to
       analysis/consolidated/estate_observations.json, records the round in STATUS (idempotently, by round number).

Pass rule (docs/SCORING.md), run config scoring.pass_rule:
  "defects" (default for new runs): every claim scored or carried, no verdict `false` / score <= 2, no
      `unsupported` with counter-evidence, imprecise claims (verdict imprecise, or unsupported without counter-evidence below the threshold - the standard critic's
      'unsupported, carried at 8' for a client half it cannot see is not a defect) at most
      max(1, scoring.max_imprecise_share (10 %) of the claims), each carrying an owed text fix (issue or fix hint). On a pass the
      imprecise claims move to notes_on_passing_claims as owed text fixes. Averages stay in the result file as information.
  "defects+quotes" (profile lean): "defects" with the quote gate always on (as under claims.quotes required) and every evidence
      locator resolving (`dbcx evidence check`: a dangling locator is a blocking defect) - the deterministic checks that let a gauntlet run
      with ONE critic or none (scoring.phase_critics: [] - the inventory then passes on CHECK + quotes + locators alone). A failed round
      whose reasons are all defects gets scoring.defect_rework_rounds more rounds beyond max_gauntlet_rounds (lean: 1 + 1).
  "mean" (runs whose run.json has no pass_rule and an engine_version of an older engine - an engagement's rule never changes silently): every
      critic avg >= pass_threshold, every claim scored or carried, no claim <= 2, no verdict `false` (or `unsupported` with
      counter-evidence when scoring.block_unsupported_with_counter_evidence), below-threshold share <= max_below_threshold_share.
Quote gate (claims.quotes required; analysis/gauntlet/<scope>/quotes.json from extract_claims / `dbcx evidence quotes`): a fact
claim whose quote is `not_found` at its locators is a blocking defect (issue by `quotes`, like `unsupported` with counter-evidence);
a claim without a quote is imprecise under `defects` (counts toward the limit; its owed fix is the quote). A missing quotes.json or
one computed on another version of the analysis refuses like a stale pack. warn / off: the quote status changes nothing here.
Averages are floored, never rounded up. A claim is listed EITHER as an issue OR as a note: a note of one critic on a claim
another critic raised as an issue is merged into that issue. A fix hint that names a locator or identifier absent from the claim
is tagged "new in hint": the analyst reproduces it before adopting it.
Carry-forward (round >= 2): a claim the critic did not score is carried from the LAST round in which that critic scored it
>= threshold with the same hash (walks back through every earlier round, not only n-1). Carried entries are appended to the
critic's JSON (carried_from_round) and the file is then checksummed (build_excel refuses a file changed afterwards).
Guards: refuses when the live analysis file differs from the snapshot the critics were given (stale pack - re-run
extract_claims while the round is open), when a DIRTY marker says the analysis was edited during the round, or when the
previous round's checksums no longer match (its carried entries were lost - re-run score_aggregate for that round first).
--force overrides the guards (say why in `dbcx status assume`), --dry-run computes and prints everything, writes nothing.
Also written: cross-critic divergence issues (spread >= scoring.critic_divergence_flag), notes_on_passing_claims (issue
text on claims at/above threshold - wording repairs owed, never a rework on their own), estate observations.
Disputes (scoring.dispute_routes {ground: critic}, e.g. {"standard-dispute": "standard"}): a score row whose `ground` names a route is no
score - the claim keeps the critic's carried score or, without one, does not count for that critic this round (never unscored); the row
moves to the critic file's `disputes`, result.json `routed` lists it for the named critic (`standard` = every standard / standard-<pack>
critic that scores the claim), extract_claims puts the claim into that critic's next delta and the issues file lists it.
"""
import json, os, re, sys, subprocess, math, hashlib, time
import glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, TOOLS, STATUS_PATH, project, method, scope_info, scope_critics, is_consolidated, phase_for_scope, extra_gauntlet, relp

PLACEHOLDER = __import__('re').compile(r"^(?:[-–—]+|none|keine|n/?a|not applicable|nicht zutreffend|nichts|\(none\)|\(keine\)|no missing claims?)\.?$", __import__('re').I)
def sha(fp): return hashlib.sha256(open(fp, "rb").read()).hexdigest()
def jload(fp): return json.load(open(fp, encoding="utf-8"))

def pass_rule_of(p):
    """scoring.pass_rule when the run or engagement sets it; else "defects" for new runs, "mean" for runs of an older engine"""
    rule = (p.get("scoring") or {}).get("pass_rule")
    if rule in ("defects", "defects+quotes", "mean"): return rule
    if rule: sys.exit(f"scoring.pass_rule must be 'defects', 'defects+quotes' or 'mean', not {rule!r}")
    try: from common import run_file; ver = str(run_file().get("engine_version") or "0")
    except Exception: ver = "0"
    try: major_minor = tuple(int(x) for x in (ver.split(".") + ["0"])[:2])
    except ValueError: major_minor = (0, 0)
    return "defects" if major_minor >= (0, 8) else "mean"

_LOC = re.compile(r"(?:[\w.-]+/)+[\w.-]+(?::\d+(?:-\d+)?)?|\b[\w-]+\.(?:java|xml|properties|impex|groovy|jsp|tag|js|ts|html|json|yml|yaml|vm|py|kt|scss|css)(?::\d+(?:-\d+)?)?\b|\bPS-7-\d+\b|\bC-[\w.-]+-\d+\b|\b(?:[a-z]\w*\.){2,}[A-Za-z]\w*\b|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*){2,}\b")
def new_in_hint(hint, claim):
    """locators / identifiers a fix hint introduces that the claim (statement + evidence + target) does not carry"""
    if not hint: return []
    have = " ".join([claim.get("statement", ""), " ".join(claim.get("evidence", []) or []), claim.get("target") or ""])
    out = []
    for t in _LOC.findall(hint):
        t = t.rstrip(".,;:)")
        base = re.sub(r":\d+(?:-\d+)?$", "", t)
        if len(base) > 3 and base not in have and t not in out: out.append(t)
    return out[:8]

def source_paths(scope):
    js, md, kind, role, agent = scope_info(scope); return js, md

def round_model_policy(scope, rnd, critics):
    per = {}
    for critic in critics:
        pattern = os.path.join(ROOT, "analysis", "briefs", f"critic-{critic}-{scope}-r{rnd}.meta.json")
        matches = glob.glob(pattern)
        if matches:
            meta = jload(matches[0]); per[critic] = {k: meta.get(k) for k in ("harness", "provider", "model", "reasoning_effort", "profile", "brief", "sha256")}
    harnesses = {value.get("harness") for value in per.values() if value.get("harness")}
    providers = {value.get("provider") for value in per.values() if value.get("provider")}
    if len(harnesses) > 1 or len(providers) > 1:
        raise SystemExit(f"REFUSED: the critics of {scope} round {rnd} was rendered under different harness/provider policies: {per}")
    return {"harness": next(iter(harnesses), None), "provider": next(iter(providers), None), "critics": per}

def main():
    a = sys.argv[1:]; dry = "--dry-run" in a; force = "--force" in a
    amend = a[a.index("--amend") + 1] if "--amend" in a else None
    if amend: i = a.index("--amend"); del a[i:i + 2]
    rule_arg = a[a.index("--rule") + 1] if "--rule" in a else None
    if rule_arg:
        if not dry or rule_arg not in ("defects", "defects+quotes", "mean"): sys.exit("--rule defects|defects+quotes|mean is a dry-run option (the run's own rule is scoring.pass_rule)")
        i = a.index("--rule"); del a[i:i + 2]
    a = [x for x in a if not x.startswith("--")]
    scope, rnd = a[0], int(a[1]); p = project(); sc = p["scoring"]; PASS = sc["pass_threshold"]; critics = scope_critics(scope, p)
    maxr = sc.get("max_gauntlet_rounds_light", sc["max_gauntlet_rounds"]) if is_light(scope) else sc["max_gauntlet_rounds"]
    cap_missing = sc.get("max_missing_claims_per_round", 3); freeze = sc.get("freeze_register_after_round", 2)
    max_share = sc.get("max_below_threshold_share", 0.2); spread_flag = sc.get("critic_divergence_flag", 3)
    block_unsup = sc.get("block_unsupported_with_counter_evidence", True); rule = rule_arg or pass_rule_of(p); routes = sc.get("dispute_routes") or {}
    if rule != "mean": block_unsup = True
    d = os.path.join(ROOT, "analysis", "gauntlet", scope)
    snap_p = os.path.join(d, f"claims-round{rnd}.json")
    reg = jload(snap_p) if os.path.exists(snap_p) else jload(os.path.join(d, "claims.json"))
    claims_by_id = {c["id"]: c for c in reg["claims"]}
    problems = []
    amendments = (jload(os.path.join(d, f"round{rnd}-result.json")).get("amendments") or []) if os.path.exists(os.path.join(d, f"round{rnd}-result.json")) else []
    if amend:
        # ---- amendment: a critic re-scored named claims of an already aggregated round against a LEAD FACT; the round is recomputed, the audit trail kept
        if amend not in critics: sys.exit(f"--amend expects one of {critics}")
        ap = os.path.join(d, f"round{rnd}-{amend}-amend.json"); base_p = os.path.join(d, f"round{rnd}-{amend}.json")
        if not os.path.exists(ap): sys.exit(f"REFUSED: {relp(ap, ROOT)} missing - the critic writes round{rnd}-{amend}-amend.md (ONLY the re-scored rows), you convert it with `dbcx md_to_json critic`")
        if not os.path.exists(base_p): sys.exit(f"REFUSED: {relp(base_p, ROOT)} missing - nothing to amend")
        if not os.path.exists(os.path.join(d, f"round{rnd}-result.json")): sys.exit(f"REFUSED: round {rnd} was never aggregated - run score_aggregate normally")
        am = jload(ap); base = jload(base_p); k = len(amendments) + 1
        if not dry:
            import shutil; shutil.copy(base_p, os.path.join(d, f"round{rnd}-{amend}.pre-amend{k}.json"))
        ids = []
        for row in am.get("scores", []):
            old = next((x for x in base["scores"] if x["claim_id"] == row["claim_id"]), None)
            row = dict(row); row["amended_from"] = {"score": old["score"], "verdict": old.get("verdict")} if old else None; row["amendment"] = k; row["amended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            if old: base["scores"][base["scores"].index(old)] = row
            else: base["scores"].append(row)
            ids.append(row["claim_id"])
        if not ids: sys.exit("REFUSED: the amendment file has no score rows")
        if not dry: json.dump(base, open(base_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        amendments.append({"critic": amend, "claims": ids, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "file": relp(ap, ROOT), "backup": f"round{rnd}-{amend}.pre-amend{k}.json"})
        print(f"AMENDMENT {k}: critic {amend} re-scored {', '.join(ids)} in round {rnd}" + (" (dry run: files untouched)" if dry else f"; original rows kept in round{rnd}-{amend}.pre-amend{k}.json"))
    # ---- guard 1: the text under judgement moved since extraction - not applied to an amendment (the snapshot is what was judged)
    sj, sm = source_paths(scope)
    if amend: pass
    elif reg.get("source_sha256") and os.path.exists(sj) and sha(sj) != reg["source_sha256"]: problems.append(f"{relp(sj, ROOT)} changed since the round-{rnd} snapshot was extracted (the critics scored other text)")
    if reg.get("source_md_sha256") and os.path.exists(sm) and sha(sm) != reg["source_md_sha256"]: problems.append(f"{relp(sm, ROOT)} changed since the round-{rnd} snapshot was extracted")
    import evidence; qreq = evidence.quotes_mode(p) == "required" or rule == "defects+quotes"; qp = os.path.join(d, "quotes.json"); qd = jload(qp) if qreq and os.path.exists(qp) else None
    if qreq and not qd: problems.append(f"claims.quotes is required but analysis/gauntlet/{scope}/quotes.json is missing - run `dbcx evidence quotes {scope}`")
    elif qd and qd.get("source_sha256") != reg.get("source_sha256"): problems.append(f"analysis/gauntlet/{scope}/quotes.json was computed on another version of the analysis than the round-{rnd} snapshot - re-run `dbcx evidence quotes {scope}`")
    dirty = os.path.join(d, "DIRTY")
    if os.path.exists(dirty) and not amend: problems.append("DIRTY marker present: " + open(dirty, encoding="utf-8").read().strip()[:200])
    # ---- guard 2: previous round's checksums
    if rnd > 1:
        pres = os.path.join(d, f"round{rnd - 1}-result.json")
        if os.path.exists(pres):
            for c, h in (jload(pres).get("checksums") or {}).items():
                fp = os.path.join(d, f"round{rnd - 1}-{c}.json")
                if os.path.exists(fp) and sha(fp) != h: problems.append(f"round{rnd - 1}-{c}.json no longer matches the checksum recorded in round{rnd - 1}-result.json - its carried entries may be lost; re-run `dbcx score_aggregate {scope} {rnd - 1}` first")
    if problems and not force:
        print("REFUSED (nothing written):"); [print("  -", x) for x in problems]
        print(f"  fix the cause (round still open: `dbcx md_to_json ...` then `dbcx extract_claims {scope} --round {rnd}` and tell the critics what changed) or re-run with --force and log why via `dbcx status assume`."); sys.exit(1)
    for x in problems: print("WARNING (forced):", x)
    # ---- earlier snapshots + score files for carry-forward
    snaps = {}; prev_scores = {}
    for r in range(1, rnd):
        sp = os.path.join(d, f"claims-round{r}.json")
        if os.path.exists(sp): snaps[r] = {c["id"]: c for c in jload(sp)["claims"]}
        for c in critics:
            fp = os.path.join(d, f"round{r}-{c}.json")
            if os.path.exists(fp): prev_scores.setdefault(c, {})[r] = {x["claim_id"]: x for x in jload(fp)["scores"]}
    model_policy = round_model_policy(scope, rnd, critics)
    res = {"scope": scope, "round": rnd, "critics": {}, "passed": False, "checksums": {}, "source_sha256": reg.get("source_sha256"), "aggregated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "amendments": amendments, "model_policy": model_policy}
    issues = []; deferred = []; notes = []; estate = []; per_claim = {}; written_files = []; routed = []
    for critic in critics:
        fp = os.path.join(d, f"round{rnd}-{critic}.json")
        if not os.path.exists(fp): res["critics"][critic] = {"missing": True}; continue
        mine = {cid: c for cid, c in claims_by_id.items() if critic in (c.get("critics") or critics)}   # per-pack standard critics score only their claims (extract_claims `critics`)
        s = jload(fp); moved = [x for x in s["scores"] if routes and x.get("ground") in routes]   # a dispute is no score: it leaves the scores (kept under `disputes`)
        if moved: s["scores"] = [x for x in s["scores"] if not any(x is y for y in moved)]; s["disputes"] = (s.get("disputes") or []) + moved
        disputed = {x["claim_id"] for x in s.get("disputes") or [] if x.get("claim_id") in mine}
        scored = {x["claim_id"] for x in s["scores"]}; carried = 0; carried_from = {}
        for cid, c in mine.items():
            if cid in scored: continue
            for r in range(rnd - 1, 0, -1):   # walk back: last round this critic scored it with the same hash
                px = prev_scores.get(critic, {}).get(r, {}).get(cid); pc = snaps.get(r, {}).get(cid)
                if px and pc and pc.get("hash") and pc.get("hash") == c.get("hash"):
                    if px["score"] >= PASS and px.get("verdict") != "false":
                        s["scores"].append({"claim_id": cid, "score": px["score"], "verdict": px.get("verdict", "confirmed"), "issue": "", "counter_evidence": [], "fix_hint": "", "carried_from_round": px.get("carried_from_round", r)}); carried += 1; carried_from[cid] = px.get("carried_from_round", r)
                    break
        if (carried or moved) and not dry: json.dump(s, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=2); written_files.append(fp)
        for x in s.get("disputes") or []:
            cid = x.get("claim_id"); tgt = routes.get(x.get("ground"), "")
            if cid not in mine: continue
            to = [c for c in (claims_by_id[cid].get("critics") or critics) if c != critic and (c == tgt or c.startswith(tgt + "-"))]
            routed.append({"claim_id": cid, "from": critic, "to": to, "ground": x.get("ground"), "score": x.get("score"), "issue": x.get("issue", ""), "counter_evidence": x.get("counter_evidence", []), "fix_hint": x.get("fix_hint", ""), "statement": claims_by_id[cid].get("statement", "")})
        mine = {cid: c for cid, c in mine.items() if cid not in disputed or cid in {x["claim_id"] for x in s["scores"]}}   # disputed and not carried: not counted, not unscored
        rows = [x for x in s["scores"] if x["claim_id"] in mine]; scores = [x["score"] for x in rows]
        stale = sorted({x["claim_id"] for x in s["scores"]} - set(mine))
        avg = math.floor((sum(scores) / len(scores) if scores else 0.0) * 100) / 100
        unscored = sorted(set(mine) - {x["claim_id"] for x in s["scores"]})
        false_v = [x["claim_id"] for x in rows if x.get("verdict") == "false" or (block_unsup and x.get("verdict") == "unsupported" and x.get("counter_evidence"))]
        # a critic's 'none' placeholder is not a missing claim
        missing = [m for m in (s.get("missing_claims", []) or []) if not PLACEHOLDER.match((m or "").strip())]; kept_missing = missing[:cap_missing]
        below = [x for x in rows if x["score"] < PASS]
        res["critics"][critic] = {"avg": avg, "n": len(scores), "carried": carried, "min": min(scores) if scores else None, "below_threshold": len(below), "below_threshold_share": round(len(below) / len(scores), 3) if scores else 0,
                                  "false_claims": sum(1 for x in rows if x["score"] <= 2), "false_verdicts": false_v, "unscored_claims": unscored, "stale_scored_ids": stale,
                                  "missing_claims": len(missing), "missing_claims_kept": len(kept_missing) if rnd <= freeze else 0, "notes_on_passing": sum(1 for x in rows if x["score"] >= PASS and (x.get("issue") or "").strip() and not x.get("carried_from_round"))}
        if disputed: res["critics"][critic]["disputed"] = sorted(disputed)
        for x in rows:
            per_claim.setdefault(x["claim_id"], {})[critic] = x
            if x["score"] < PASS or x["claim_id"] in false_v:
                issues.append({"critic": critic, "claim_id": x["claim_id"], "score": x["score"], "verdict": x.get("verdict"), "issue": x.get("issue", ""), "fix_hint": x.get("fix_hint", ""), "accept_if": x.get("accept_if", "") or "", "counter_evidence": x.get("counter_evidence", []), "statement": claims_by_id[x["claim_id"]].get("statement", ""), "blocking": x["claim_id"] in false_v, "new_in_hint": new_in_hint(x.get("fix_hint", ""), claims_by_id[x["claim_id"]])})
            elif (x.get("issue") or "").strip() and not x.get("carried_from_round"):
                notes.append({"critic": critic, "claim_id": x["claim_id"], "score": x["score"], "issue": x["issue"], "fix_hint": x.get("fix_hint", ""), "new_in_hint": new_in_hint(x.get("fix_hint", ""), claims_by_id[x["claim_id"]])})
        for m in kept_missing:
            (deferred if rnd > freeze else issues).append({"critic": critic, "claim_id": None, "score": None, "verdict": "missing", "issue": m, "fix_hint": "add a claim with evidence or explain why not applicable", "statement": "", "blocking": False})
        for e in s.get("estate_observations", []) or []:
            if e.strip(): estate.append({"scope": scope, "round": rnd, "critic": critic, "text": e.strip(), "t": res["aggregated_at"]})
        res["checksums"][critic] = sha(fp) if not dry else "(dry-run: not recorded)"
    # ---- cross-critic divergence: both scored the same claim this round, spread >= flag
    diverg = []
    for cid, by in per_claim.items():
        fresh = {c: x for c, x in by.items() if not x.get("carried_from_round")}
        if len(fresh) >= 2:
            vals = [x["score"] for x in fresh.values()]
            if max(vals) - min(vals) >= spread_flag:
                diverg.append({"claim_id": cid, "scores": {c: x["score"] for c, x in fresh.items()}, "verdicts": {c: x.get("verdict") for c, x in fresh.items()}})
                score_details = ", ".join(
                    "{} {}/{}".format(c, x["score"], x.get("verdict"))
                    for c, x in fresh.items()
                )
                issues.append({"critic": "both", "claim_id": cid, "score": min(vals), "verdict": "divergence", "issue": f"critics diverge by {max(vals) - min(vals)} points ({score_details}) - a factual dispute; the client-evidence critic prevails on facts about the client's estate, the standard critic on facts about the external standard; settle it explicitly", "fix_hint": "", "counter_evidence": [], "statement": claims_by_id[cid].get("statement", ""), "blocking": False})
    got = [v for v in res["critics"].values() if "avg" in v]
    # ---- a claim is an issue OR a note, never both - a note on a claim another critic raised is merged into the issue
    issue_ids = {i["claim_id"] for i in issues if i["claim_id"] and i["verdict"] != "divergence"}
    for n in [n for n in notes if n["claim_id"] in issue_ids]:
        tgt = next(i for i in issues if i["claim_id"] == n["claim_id"] and i["verdict"] != "divergence")
        tgt.setdefault("also_noted", []).append({k: n[k] for k in ("critic", "score", "issue", "fix_hint")}); notes.remove(n)
    qres = {cid: r for cid, r in ((qd or {}).get("claims") or {}).items() if cid in claims_by_id}
    q_nf = sorted(cid for cid, r in qres.items() if r["status"] == "not_found" and claims_by_id[cid].get("type") == "fact"); q_nq = sorted(cid for cid, r in qres.items() if r["status"] == "no_quote")
    for cid in q_nf: issues.append({"critic": "quotes", "claim_id": cid, "score": None, "verdict": "not_found", "issue": "the quoted words are not at the cited locators (claims.quotes required): " + " / ".join(qres[cid].get("missing") or []), "fix_hint": "copy the words exactly as they stand at a cited locator, or cite the locator that carries them", "counter_evidence": [], "statement": claims_by_id[cid].get("statement", ""), "blocking": True})
    dangling = {}   # defects+quotes: an evidence locator that does not resolve is a blocking defect (the deterministic half of the client critic)
    for c in (reg["claims"] if rule == "defects+quotes" else []):
        bad = [ev for ev in c.get("evidence") or [] if not evidence.resolve(ev, p, set(claims_by_id))[1]]
        if bad: dangling[c["id"]] = bad; issues.append({"critic": "locators", "claim_id": c["id"], "score": None, "verdict": "dangling", "issue": "evidence locator(s) that do not resolve: " + "; ".join(bad), "fix_hint": f"cite a locator that exists (`dbcx evidence check {scope}`)", "counter_evidence": [], "statement": c.get("statement", ""), "blocking": True})
    for cid in (q_nq if rule != "mean" else []): issues.append({"critic": "quotes", "claim_id": cid, "score": None, "verdict": "no_quote", "issue": "no verbatim quote (claims.quotes required)", "fix_hint": "add a quote column entry: the words of a cited locator that carry the statement", "counter_evidence": [], "statement": claims_by_id[cid].get("statement", ""), "blocking": False})
    reasons = []
    if q_nf: reasons.append("quote not found at the cited locators (claims.quotes required): " + ", ".join(q_nf))
    if dangling: reasons.append("evidence locator does not resolve: " + ", ".join(sorted(dangling)))
    if len(got) != len(critics): reasons.append("critic file missing")
    if any(v["unscored_claims"] for v in got): reasons.append("unscored claims")
    if any(v["false_claims"] for v in got): reasons.append("claim scored <= 2")
    if any(v["false_verdicts"] for v in got): reasons.append("verdict false / unsupported with counter-evidence: " + ", ".join(sorted({x for v in got for x in v["false_verdicts"]})))
    blocking_ids = {x for v in got for x in v["false_verdicts"]} | {cid for cid, by in per_claim.items() if any(x["score"] <= 2 for x in by.values())} | set(q_nf) | set(dangling)
    imprecise = sorted({cid for cid, by in per_claim.items() if cid not in blocking_ids and any(x.get("verdict") == "imprecise" or (x.get("verdict") == "unsupported" and not x.get("counter_evidence") and x["score"] < PASS) for x in by.values())})
    limit = max(1, math.floor(sc.get("max_imprecise_share", 0.10) * len(claims_by_id)))
    unfixed = [cid for cid in imprecise if not any((x.get("issue") or "").strip() or (x.get("fix_hint") or "").strip() for x in per_claim[cid].values())]
    if q_nq: imprecise = sorted(set(imprecise) | (set(q_nq) - blocking_ids))   # the owed fix of a missing quote is the quote itself
    res["defects"] = {"blocking": sorted(blocking_ids), "imprecise": imprecise, "imprecise_limit": limit, "imprecise_without_fix": unfixed}
    if qd: res["defects"].update(quote_not_found=q_nf, no_quote=q_nq); res["quotes"] = qd.get("counts")
    if dangling: res["defects"]["dangling_locators"] = dangling
    if rule != "mean":
        if len(imprecise) > limit: reasons.append(f"{len(imprecise)} imprecise claims (limit max(1, {int(sc.get('max_imprecise_share', 0.10) * 100)} % of {len(claims_by_id)}) = {limit}): " + ", ".join(imprecise))
        if unfixed: reasons.append("imprecise claims without an owed text fix (issue or fix hint): " + ", ".join(unfixed))
        res["pass_rule"] = f"{rule}: every claim scored or carried, no verdict false / score <= 2, no unsupported with counter-evidence, imprecise (or below-threshold unsupported without counter-evidence) claims <= {limit} each with an owed text fix; averages are information" + ("; claims.quotes required: a fact claim whose quote is not found blocks, a claim without a quote is imprecise" if qreq else "") + ("; every evidence locator resolves; critics of this scope: " + (", ".join(critics) or "none - the deterministic checks decide") if rule == "defects+quotes" else "")
    else:
        if any(v["avg"] < PASS for v in got): reasons.append("average below threshold")
        if any(v["below_threshold_share"] > max_share for v in got): reasons.append(f"more than {int(max_share * 100)} % of the claims below threshold")
        res["pass_rule"] = f"mean: every critic avg >= {PASS}, every claim scored or carried, no claim <= 2, no verdict false{' (or unsupported with counter-evidence)' if block_unsup else ''}, below-threshold share <= {max_share}"
    res["pass_rule_id"] = rule
    res["passed"] = not reasons; res["fail_reasons"] = reasons; res["divergence"] = diverg
    if routed: res["routed"] = routed
    if res["passed"] and rule != "mean":   # the tolerated defects become owed text fixes for the post-pass, not a rework
        owed = [i for i in issues if i["claim_id"] and i["verdict"] not in ("divergence", "missing") and not i.get("blocking")]
        for i in owed:
            issues.remove(i); notes.append({"critic": i["critic"], "claim_id": i["claim_id"], "score": i["score"], "issue": i["issue"], "fix_hint": i["fix_hint"], "accept_if": i.get("accept_if", ""), "owed": True, "new_in_hint": i.get("new_in_hint", [])})
            for a in i.get("also_noted", []): notes.append(dict(a, claim_id=i["claim_id"], owed=True, new_in_hint=[]))
    issues.sort(key=lambda i: (0 if i.get("blocking") else 1, i["score"] if i["score"] is not None else 3, i["critic"])); res["issue_count"] = len(issues); res["deferred_missing"] = len(deferred); res["notes_on_passing_claims"] = notes; res["estate_observations"] = len(estate)
    extra = sc.get("defect_rework_rounds", 0) if reasons and not any(r in ("critic file missing", "unscored claims") for r in reasons) else 0   # one more round only when defects failed it
    status = "passed" if res["passed"] else ("failed-gauntlet" if rnd >= maxr + extra else "rework")
    summary = {"rounds": rnd, "passed": res["passed"], "last_scores": {c: v.get("avg") for c, v in res["critics"].items()}, "status": status}
    if dry:
        print(json.dumps(res, indent=1)); print(f"DRY RUN: nothing written. Would set {scope} -> {status}."); return
    json.dump(res, open(os.path.join(d, f"round{rnd}-result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if os.path.exists(dirty): os.remove(dirty)
    with open(os.path.join(d, f"round{rnd}-issues.md"), "w", encoding="utf-8") as f:
        f.write(f"# Gauntlet result {scope} round {rnd}: {'PASS' if res['passed'] else 'FAIL'}" + (f" ({'; '.join(reasons)})" if reasons else "") + "\n\n")
        for c, v in res["critics"].items():
            f.write(f"- {c}: " + (f"avg {v['avg']} over {v['n']} claims ({v['carried']} carried), min {v['min']}, {v['below_threshold']} below {PASS} ({int(v['below_threshold_share'] * 100)} %), {v['false_claims']} scored <= 2, verdict false {len(v['false_verdicts'])}, unscored {len(v['unscored_claims'])}{(' ' + str(v['unscored_claims'])) if v['unscored_claims'] else ''}, missing-claims raised {v['missing_claims']} (kept {v['missing_claims_kept']}, cap {cap_missing})" if "avg" in v else "MISSING") + "\n")
        f.write(f"\n## Ranked issues ({len(issues)}), blocking first, then worst score\n\nFix every issue below. Add claims only for the missing-claim items listed here" + (f" - none at all, the register is frozen after round {freeze}" if rnd > freeze else "") + ". Unchanged passing claims keep their score - do not rewrite them. Every fix hint is a HYPOTHESIS: reproduce a count, path or mechanism before you adopt it, dispute it with your own measurement if it does not reproduce. After a correction, sweep every other home of the same fact (Summary, Classification rationale, table rows incl. verdict columns) and grep the old figure before and after.\n\n")
        for i, it in enumerate(issues, 1):
            f.write(f"{i}. **[{it['critic']}] {it['claim_id'] or 'MISSING'} score={it['score']} ({it['verdict']}{', BLOCKING' if it.get('blocking') else ''})** {it['statement'][:200]}\n   - issue: {it['issue']}\n" + "".join(f"   - also noted by [{a['critic']}] ({a['score']}): {a['issue']}\n" for a in it.get('also_noted', [])) + (f"   - NEW in this hint, not in the claim (reproduce before adopting): {', '.join(it['new_in_hint'])}\n" if it.get('new_in_hint') else "") + (f"   - counter-evidence: {', '.join(it['counter_evidence'])}\n" if it.get('counter_evidence') else "") + (f"   - fix hint (hypothesis - verify before adopting): {it['fix_hint']}\n" if it.get('fix_hint') else "") + (f"   - passes next round if: {it['accept_if']}\n" if it.get('accept_if') else ""))
        if notes:
            f.write(f"\n## Notes on passing claims ({len(notes)}) - wording/precision repairs owed, not a rework on their own\n\nApply as text corrections (`dbcx render brief postpass {scope}` after the pass); if you edit a claim now it re-enters the delta and is re-scored whole.\n\n")
            for n in notes: f.write(f"- [{n['critic']}] {n['claim_id']} ({n['score']}){' OWED TEXT FIX' if n.get('owed') else ''}: {n['issue']}" + (f" - hint: {n['fix_hint']}" if n['fix_hint'] else "") + (f" - NEW in hint (reproduce first): {', '.join(n['new_in_hint'])}" if n.get('new_in_hint') else "") + (f" - keep: {n['accept_if']}" if n.get('accept_if') else "") + "\n")
        if deferred:
            f.write(f"\n## Deferred missing claims ({len(deferred)}) - register frozen after round {freeze}; listed for the FINAL_REPORT, not to be added now\n\n")
            for it in deferred: f.write(f"- [{it['critic']}] {it['issue']}\n")
        if routed:
            f.write(f"\n## Disputes routed ({len(routed)}) - no score of the disputing critic; the named critic answers them" + (" in the next round (they are in its delta)" if not res["passed"] else " (the scope passed: send them to that critic as a continuation message)") + " - its answer is a reference-row correction (`dbcx reference correct`) or a note; the analyst changes nothing for a dispute alone\n\n")
            for x in routed: f.write(f"- {x['claim_id']} [{x['from']} -> {', '.join(x['to']) or 'no critic of this scope'}, ground {x['ground']}]: {x['issue']}" + (f" (counter-evidence: {', '.join(x['counter_evidence'])})" if x.get("counter_evidence") else "") + "\n")
        if estate:
            f.write(f"\n## Estate observations ({len(estate)}) - outside this scope; routed to consolidators / D0 via analysis/consolidated/estate_observations.json\n\n")
            for e in estate: f.write(f"- [{e['critic']}] {e['text']}\n")
    if estate:
        ep = os.path.join(ROOT, "analysis", "consolidated", "estate_observations.json"); os.makedirs(os.path.dirname(ep), exist_ok=True)
        cur = jload(ep) if os.path.exists(ep) else []
        keys = {(x["scope"], x["round"], x["critic"], x["text"]) for x in cur}
        cur += [e for e in estate if (e["scope"], e["round"], e["critic"], e["text"]) not in keys]
        json.dump(cur, open(ep, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ---- STATUS: idempotent by round number, and say exactly what was written (B21c/B24)
    st = os.path.join(TOOLS, "status.py")
    key = phase_for_scope(scope)
    if key:
        s = jload(STATUS_PATH); ph = s["phases"][key]
        entry = {"round": rnd, "scores": summary["last_scores"], "passed": res["passed"], "issues": len(issues), "model_policy": model_policy}
        ph["gauntlet_rounds"] = [e for e in ph.get("gauntlet_rounds", []) if e.get("round") != rnd] + [entry]; ph["gauntlet_rounds"].sort(key=lambda e: e["round"])
        ph["passed"] = res["passed"] or (ph.get("passed") and rnd > 1 and any(e.get("passed") for e in ph["gauntlet_rounds"][:-1]))
        ph["status"] = status if not (ph.get("status") == "final" and res["passed"]) else "final"
        json.dump(s, open(STATUS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"recorded STATUS phases.{key}.gauntlet_rounds[round={rnd}] (replaced if it existed), status={ph['status']} - nothing else to record by hand")
    elif extra_gauntlet(scope):   # a method brief kind's gauntlet scope (e.g. the triage) is neither a phase nor a wave member
        s = jload(STATUS_PATH); e = s.setdefault("steps", {}).setdefault(scope, {})
        e["gauntlet_rounds"] = [x for x in e.get("gauntlet_rounds", []) if x.get("round") != rnd] + [{"round": rnd, "scores": summary["last_scores"], "passed": res["passed"], "issues": len(issues), "model_policy": model_policy}]
        e["gauntlet_rounds"].sort(key=lambda x: x["round"]); e.update(summary)
        json.dump(s, open(STATUS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"recorded STATUS steps.{scope}.gauntlet_rounds[round={rnd}] (replaced if it existed), status={status} - nothing else to record by hand")
    else:
        subprocess.run([sys.executable, st, "scope", scope, json.dumps(summary)], check=True)
        print(f"recorded STATUS scopes.{scope} rounds={rnd} status={status} - nothing else to record by hand")
    subprocess.run([sys.executable, st, "log", f"gauntlet {scope} round {rnd}: {'PASS' if res['passed'] else 'FAIL'} {summary['last_scores']} issues={len(issues)} carried={ {c: v.get('carried') for c, v in res['critics'].items()} }" + (f" reasons={reasons}" if reasons else "")], check=True)
    print(json.dumps({k: v for k, v in res.items() if k not in ("notes_on_passing_claims",)}, indent=1))
    if written_files: print("critic files now carry the carried entries and are CLOSED (checksummed): " + ", ".join(relp(x, ROOT) for x in written_files) + " - never re-run md_to_json on them")
    if amend: print(f"AMENDED round {rnd} of {scope}: {'PASS' if res['passed'] else 'FAIL'} - " + ("stop the reworking analyst (TaskStop) if it is still running: the scope passed on the amended scores; mark it passed/final" if res['passed'] else "the round still fails; tell the analyst which claim is settled and to leave it unchanged"))
    subprocess.run([sys.executable, os.path.join(TOOLS, "progress.py"), "--quiet"], cwd=ROOT, capture_output=True, text=True)   # round finished -> dashboard data refreshed

def is_light(scope):
    try:
        w = jload(os.path.join(ROOT, "state", "WAVES.json"))
        return any(m.get("light_pass") for wv in w.get("waves", []) for m in wv.get("members", []) if m["name"] == scope)
    except Exception: return False

if __name__ == "__main__":
    main()
