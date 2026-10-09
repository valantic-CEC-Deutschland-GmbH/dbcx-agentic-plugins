#!/usr/bin/env python3
"""Aggregate a final-gate round: pass rule + fix plan (G6, G10, G12). Usage: dbcx gate_aggregate <round>

Reads analysis/gate/round<n>-hygiene.json (dbcx lint_deliverable --standalone --round n), round<n>-verifier.json and
round<n>-<persona>.json for every persona in scoring.gate_personas. Writes round<n>-result.json and round<n>-fixplan.md + .json,
updates STATUS (phases.<gate>.rounds, idempotent by round) and prints a suggested `dbcx learn add` line per non-content cluster.
Pass = hygiene clean AND every verifier score >= pass_threshold AND per persona mean(key questions) >= pass_threshold AND no key
question < scoring.gate_question_floor (7) AND no blocker AND every major cluster carries a lead decision (`dbcx gate decide`).
The key questions are the round's (`dbcx gate questions --round n`): a question dismissed from round k on leaves the mean and the criteria from k.
Fix plan: issues of all personas, the verifier and the hygiene layer clustered (same deliverable | sheet | kind and similar text;
sheets identical in every workbook are one sheet), each with a mechanism, an owner, an acceptance test and "unchanged since round k".
"""
import hashlib, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import TOOLS, P, project, load_json, CLI, PLUGIN, PROJECT_DIR, relp
import gate

MECH_OWNER = {"spec/override": "deliverable-editor", "label": "deliverable-editor", "summary/Kernaussage text": "deliverable-editor",
              "content + mini gauntlet": "orchestrator -> owning consolidator/analyst, mini gauntlet on changed claims", "lead decision": "lead (`dbcx gate decide`)",
              "engine": "plugin change (lead approval; `dbcx learn add`)"}
HYGIENE_MECH = {"process_language": "label", "language": "content + mini gauntlet", "internal_locator": "engine", "run_shorthand": "content + mini gauntlet", "dangling_id": "engine", "missing_sheet_ref": "label",
                "raw_key": "label", "empty_column": "spec/override", "summary_number": "summary/Kernaussage text", "summary_missing": "summary/Kernaussage text", "literal_aggregate": "spec/override", "formula_error": "spec/override",
                "reconciliation": "spec/override", "basis_empty": "content + mini gauntlet", "basis_code": "content + mini gauntlet", "basis_source": "content + mini gauntlet",
                "basis_assumption": "content + mini gauntlet", "basis_assumption_reason": "content + mini gauntlet", "basis_assumption_if_not": "content + mini gauntlet", "emphasis_budget": "spec/override", "header_tier": "spec/override", "duplicate_header": "spec/override",
                "freeze": "engine", "filter": "engine", "print_setup": "engine", "tab_colour": "engine"}
HYGIENE_KIND = {"process_language": "language", "language": "language", "raw_key": "language", "missing_sheet_ref": "structure", "empty_column": "structure", "summary_number": "content", "summary_missing": "content",
                "literal_aggregate": "structure", "formula_error": "structure", "reconciliation": "content", "internal_locator": "content", "run_shorthand": "content", "dangling_id": "content",
                "basis_empty": "content", "basis_code": "content", "basis_source": "content", "basis_assumption": "content", "basis_assumption_reason": "content", "basis_assumption_if_not": "content"}
SEV = {"blocker": 0, "major": 1, "minor": 2}

def words(t): return {w for w in re.findall(r"[a-zäöüß0-9]{4,}", (t or "").lower())}
def jac(a, b): return len(a & b) / len(a | b) if a and b else 0.0
def q(t): return str(t).replace("'", "’").replace("\n", " ")[:220]   # single-quoted shell argument
def sheet_of(loc): return re.split(r"[!/ ]", (loc or "").strip(), maxsplit=1)[0].strip() or "-"

def shared_sheets(cfg):
    """sheet names whose content is identical in every customer workbook that has them (>= 2): one fix, not one per workbook"""
    import openpyxl
    seen, counts = {}, {}
    for f in gate.customer_files(cfg).values():
        for ws in openpyxl.load_workbook(P(f)):
            seen.setdefault(ws.title, set()).add(hashlib.sha256(repr([[c.value for c in r] for r in ws.iter_rows()]).encode()).hexdigest()); counts[ws.title] = counts.get(ws.title, 0) + 1
    return {n for n, h in seen.items() if len(h) == 1 and counts[n] >= 2}

def mechanism(kind, sheet, text):
    t = (text or "").lower(); mgmt = bool(re.match(r"management|summary", sheet, re.I))
    if kind == "outside-scope": return "lead decision"
    if kind == "content": return "summary/Kernaussage text" if mgmt or "kernaussage" in t else "content + mini gauntlet"
    if kind == "language": return "label" if re.search(r"feldname|schlüssel|\bkey|bezeichnung|spaltenname|label|enum", t) else ("summary/Kernaussage text" if mgmt else "content + mini gauntlet")
    if kind == "presentation":
        if mgmt: return "summary/Kernaussage text"
        return "label" if re.search(r"bezeichnung|beschriftung|label|feldname|überschrift|header|glossar", t) else "spec/override"
    return "spec/override"

def load_round(rnd, cfg, personas):
    by_file = {f: k for k, f in gate.enabled(cfg).items()}
    def dkey(d): d = str(d or "").strip(); return by_file.get(os.path.basename(d), d.split("_")[0] if re.match(r"D\d+_", d) else d)
    issues, scores, board, missing, qmiss = [], [], {}, {}, {}
    for p in personas:
        s = load_json(f"analysis/gate/round{rnd}-{p}.json", {})
        if not s: continue
        kq = {x["id"]: x for x in gate.key_questions(cfg, p, rnd)}; got = {x["question_id"]: x for x in s.get("questions", []) if x.get("question_id") in kq}
        qmiss[p] = [x for x in kq if x not in got]
        scores += [{"persona": p, "question_id": k, "deliverables": kq[k]["deliverables"], "score": v["score"], "where": v.get("where", "")} for k, v in got.items()]
        board[p] = s.get("board_test", {}); missing[p] = s.get("missing", [])
        issues += [dict(i, source=p, deliverable=dkey(i.get("deliverable"))) for i in s.get("issues", [])]
    v = load_json(f"analysis/gate/round{rnd}-verifier.json", {})
    if v: issues += [{"source": "verifier", "id": d.get("id"), "deliverable": dkey(d.get("deliverable")), "location": d.get("location"), "issue": d.get("defect"), "kind": d.get("kind", "content"), "severity": d.get("severity"), "proposed_change": d.get("proposed_change"), "evidence": d.get("evidence", "")} for d in v.get("defects", [])]
    h = load_json(f"analysis/gate/round{rnd}-hygiene.json", {})
    if h:
        groups = {}   # one generator fix clears an engine check everywhere; the other checks are fixed per sheet
        for x in h.get("findings", []):
            if x["severity"] == "error": groups.setdefault((x["check"], "*" if HYGIENE_MECH.get(x["check"]) == "engine" else x["where"].split("!")[0]), []).append(x)
        for (check, sh), xs in groups.items():
            files = sorted({by_file.get(x["file"], x["file"]) for x in xs}); where = sorted({f"{by_file.get(x['file'], x['file'])} {x['where']}" for x in xs})
            issues.append({"source": "hygiene", "id": check, "check": check, "deliverable": files[0] if len(files) == 1 else "*", "location": f"{sh}!" + "; ".join(where[:6]) + (f" (+{len(where) - 6})" if len(where) > 6 else ""),
                           "issue": f"{len(xs)} x {check} in {', '.join(files)}: {xs[0]['text']}", "kind": HYGIENE_KIND.get(check, "presentation"), "severity": "blocker",
                           "proposed_change": f"clear every `{check}` finding" + ("" if sh == "*" else f" on {sh}"), "mechanism": HYGIENE_MECH.get(check, "spec/override")})
    return issues, scores, board, missing, qmiss, v, h

def cluster(issues, rnd, shared):
    groups = []
    for i in issues:
        sh = sheet_of(i.get("location")); d = "*" if sh in shared else (i.get("deliverable") or "-")
        key = f"{d}|{sh}|{i.get('kind')}" + (f"|{i['check']}" if i.get("check") else ""); w = words(f"{i.get('issue')} {i.get('proposed_change')}")
        g = next((g for g in groups if g["key"] == key and (i.get("check") or jac(g["words"], w) >= 0.25)), None)
        if not g:   # the same theme on the same sheet name in another workbook
            g = next((g for g in groups if not i.get("check") and not g["check"] and g["sheet"] == sh and g["kind"] == i.get("kind") and jac(g["words"], w) >= 0.4), None)
            if g: g["deliverables"].add(d)
        if not g: g = {"key": key, "sheet": sh, "kind": i.get("kind"), "check": i.get("check"), "deliverables": {d}, "words": set(), "issues": []}; groups.append(g)
        g["issues"].append(i); g["words"] |= w
    groups.sort(key=lambda g: (min(SEV.get(i.get("severity"), 3) for i in g["issues"]), -len(g["issues"])))
    out = []
    for n, g in enumerate(groups, 1):
        iss = g["issues"]; first = min(iss, key=lambda i: SEV.get(i.get("severity"), 3))
        mech = first.get("mechanism") or mechanism(g["kind"], g["sheet"], " ".join(f"{i.get('issue')} {i.get('proposed_change')}" for i in iss))
        acc = []
        for i in iss:
            if i["source"] == "hygiene": acc.append(f"`{CLI} lint_deliverable --standalone` reports 0 `{i['check']}` findings on {i['deliverable']} {g['sheet']}")
            elif i["source"] == "verifier": acc.append(f"the verifier's re-check of {i.get('location')} is `confirmed`" + (f" ({i['evidence']})" if i.get("evidence") else ""))
            else: acc.append(f"{i['source']} scores {i.get('question_id') or 'its key questions'} >= 8 next round; {i.get('location')}: {i.get('proposed_change')}")
        out.append({"id": f"F{rnd}-{n:02d}", "key": g["key"], "title": str(first.get("issue"))[:140], "severity": first.get("severity"), "kind": g["kind"], "sheet": g["sheet"],
                    "deliverables": sorted(g["deliverables"]), "raised_by": sorted({i["source"] for i in iss}), "questions": sorted({i["question_id"] for i in iss if i.get("question_id")}),
                    "issues": [f"{i['source']}:{i.get('id')}" for i in iss], "locations": list(dict.fromkeys(str(i.get("location")) for i in iss))[:8],
                    "proposed_changes": list(dict.fromkeys(str(i.get("proposed_change")) for i in iss if i.get("proposed_change")))[:4],
                    "mechanism": mech, "owner": MECH_OWNER[mech], "acceptance": list(dict.fromkeys(acc))[:4], "words": sorted(g["words"])})
    return out

def history(clusters, rnd):
    """unchanged since round k: a cluster with the same key (and similar text) in every earlier round back to k"""
    prev = {k: load_json(f"analysis/gate/round{k}-fixplan.json", {}).get("clusters", []) for k in range(1, rnd)}
    for c in clusters:
        since, w = rnd, set(c["words"])
        for k in range(rnd - 1, 0, -1):
            if any(p["key"] == c["key"] and (c["key"].count("|") > 2 or jac(set(p.get("words", [])), w) >= 0.25) for p in prev[k]): since = k
            else: break
        c["unchanged_since"] = since if since < rnd else None

def learn_line(c, rnd, cfg):
    touches = "engine/tools/build_excel.py" if c["mechanism"] == "engine" else relp(os.path.join(cfg['_method']['_dir'], f"deliverables.{cfg['languages']['deliverable']}.json"), PLUGIN if cfg['_method'].get('_source') == "plugin" else PROJECT_DIR)   # an own method lives in the engagement
    return (f"{CLI} learn add --section B --title 'gate r{rnd} {c['id']}: {q(c['title'])[:90]}' --what '{c['kind']} defect on {q(c['sheet'])} ({', '.join(c['deliverables'])}), raised by {', '.join(c['raised_by'])}: {q(c['title'])}' "
            f"--evidence 'analysis/gate/round{rnd}-fixplan.md {c['id']}' --generalises 'the generator or the method spec lets this {c['kind']} defect reach a customer workbook' --proposal '{c['mechanism']}: {q((c['proposed_changes'] or [''])[0])}' --touches '{touches}'")

def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit(): sys.exit(__doc__)
    rnd = int(sys.argv[1]); cfg = project(); sc = cfg["scoring"]; TH = sc["pass_threshold"]; FLOOR = sc.get("gate_question_floor", 7); personas = sc["gate_personas"]
    issues, scores, board, missing, qmiss, ver, hyg = load_round(rnd, cfg, personas)
    clusters = cluster(issues, rnd, shared_sheets(cfg)); history(clusters, rnd); decs = gate.decisions(cfg)
    for c in clusters:
        d = next((d for d in reversed(decs) if (d["round"] == rnd and d["cluster"] == c["id"]) or (d["round"] < rnd and d["key"] == c["key"])), None)
        if d: c["decision"] = {k: d[k] for k in ("round", "cluster", "text", "by", "at")}
    seen = sorted({s["persona"] for s in scores}); miss_p = [p for p in personas if p not in seen]
    means = {p: round(sum(s["score"] for s in scores if s["persona"] == p) / sum(1 for s in scores if s["persona"] == p), 2) for p in seen}
    vscores = {x["deliverable"]: x["score"] for x in (ver or {}).get("scores", [])}
    blockers = [c["id"] for c in clusters if c["severity"] == "blocker"]; majors = [c["id"] for c in clusters if c["severity"] == "major" and not c.get("decision")]
    crit = {"hygiene clean": bool(hyg and hyg.get("passed")), f"verifier >= {TH} on every deliverable": bool(vscores) and min(vscores.values()) >= TH,
            "every persona present with all key questions": not miss_p and not any(qmiss.get(p) for p in personas), f"per persona mean >= {TH}": bool(means) and all(v >= TH for v in means.values()),
            f"no key question < {FLOOR}": bool(scores) and all(s["score"] >= FLOOR for s in scores), "no blocker": not blockers, "no major without a lead decision": not majors}
    passed = all(crit.values())
    res = {"round": rnd, "passed": passed, "criteria": crit, "personas": seen, "missing_personas": miss_p, "missing_questions": {p: v for p, v in qmiss.items() if v}, "persona_means": means,
           "min_question": min([s["score"] for s in scores], default=None), "verifier": vscores, "hygiene": {k: hyg.get(k) for k in ("passed", "errors", "warnings")} if hyg else None,
           "blockers": blockers, "majors_without_decision": majors, "clusters": len(clusters), "scores": scores + [{"persona": "verifier", "question_id": k, "score": v} for k, v in vscores.items()]}
    d = P("analysis", "gate"); os.makedirs(d, exist_ok=True)
    json.dump(res, open(os.path.join(d, f"round{rnd}-result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump({"round": rnd, "passed": passed, "clusters": clusters}, open(os.path.join(d, f"round{rnd}-fixplan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    learn = [learn_line(c, rnd, cfg) for c in clusters if c["kind"] != "content"]
    L = [f"# Final gate round {rnd}: {'PASS' if passed else 'FAIL'}", "", "| criterion | met |", "|---|---|"] + [f"| {k} | {'yes' if v else '**no**'} |" for k, v in crit.items()]
    L += ["", f"Hygiene: {res['hygiene'] or f'not run ({CLI} lint_deliverable --standalone --all --round {rnd})'} · verifier: {vscores or 'missing'} · persona means: {means or 'none'}" + (f" · missing personas: {', '.join(miss_p)}" if miss_p else ""), ""]
    L += ["## Key questions", "", "| persona | question | score | where |", "|---|---|---|---|"] + [f"| {s['persona']} | {s['question_id']} | {s['score']} | {s['where']} |" for s in scores]
    L += [f"| {p} | {', '.join(v)} | **not scored** | |" for p, v in res["missing_questions"].items()]
    L += ["", "## Board test and what is missing", ""] + [f"- **{p}**: forward unchanged = {'yes' if (board.get(p) or {}).get('forward_unchanged') else 'no'}; blocking: {', '.join((board.get(p) or {}).get('blocking_items') or []) or '-'}; missing: {'; '.join(missing.get(p) or []) or '-'}" for p in seen]
    L += ["", f"## Fix plan ({len(clusters)} clusters, blockers first)", "", "Every blocker and major cluster is fixed or escalated to the lead before the next round - there is no won't-fix list.", ""]
    for c in clusters:
        L += [f"### {c['id']} [{c['severity']}] {c['title']}", f"- kind {c['kind']} · sheet {c['sheet']} · deliverables {', '.join(c['deliverables'])} · raised by {', '.join(c['raised_by'])}" + (f" · key questions {', '.join(c['questions'])}" if c["questions"] else ""),
              f"- mechanism **{c['mechanism']}** · owner {c['owner']}", f"- locations: {'; '.join(c['locations'])}", f"- proposed: {' / '.join(c['proposed_changes']) or '-'}", f"- acceptance: {' · '.join(c['acceptance'])}", f"- issues: {', '.join(c['issues'])}"]
        if c["unchanged_since"]: L.append(f"- **unchanged since round {c['unchanged_since']}** - the last fix did not land: escalate (lead decision or engine change) instead of repeating it")
        if c.get("decision"): L.append(f"- lead decision (r{c['decision']['round']} {c['decision']['cluster']}, {c['decision']['by']}): {c['decision']['text']}")
        L.append("")
    if learn: L += ["## Suggested learnings (non-content clusters, G12)", "", "```"] + learn + ["```", ""]
    open(os.path.join(d, f"round{rnd}-fixplan.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    import status
    st = status.load(); fg = st["phases"].setdefault(gate.gate_phase(cfg), {"rounds": []})
    entry = {"round": rnd, "passed": passed, "personas": len(seen), "persona_means": means, "verifier": vscores, "hygiene_clean": crit["hygiene clean"], "blockers": len(blockers),
             "majors_without_decision": len(majors), "clusters": len(clusters), "scores": sorted([s for s in scores if s["score"] < TH], key=lambda s: s["score"])[:10]}
    fg["rounds"] = sorted([r for r in fg.get("rounds", []) if r.get("round") != rnd] + [entry], key=lambda r: r.get("round", 0)); fg["passed"] = passed; fg["status"] = "passed" if passed else "rework"
    status.save(st)
    subprocess.run([sys.executable, os.path.join(TOOLS, "status.py"), "log", f"final gate round {rnd}: {'PASS' if passed else 'FAIL'} means={means} verifier={vscores} hygiene={crit['hygiene clean']} blockers={len(blockers)} majors_open={len(majors)} clusters={len(clusters)}"], check=True, capture_output=True)
    print(json.dumps({k: v for k, v in res.items() if k != "scores"}, indent=1, ensure_ascii=False))
    print(f"wrote analysis/gate/round{rnd}-result.json, round{rnd}-fixplan.md + .json ({len(clusters)} clusters: " + ", ".join(f"{m} {n}" for m in MECH_OWNER for n in [sum(1 for c in clusters if c['mechanism'] == m)] if n) + ")")
    if learn: print("suggested learnings (review, then run):\n" + "\n".join(learn))

if __name__ == "__main__":
    main()
