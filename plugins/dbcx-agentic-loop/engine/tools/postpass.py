#!/usr/bin/env python3
"""Post-pass CHECK: a text-only post-pass may not change what the critics scored.

Usage: dbcx postpass baseline <scope>                 snapshot the analysis rows before a post-pass (`dbcx render brief postpass` does it)
       dbcx postpass check <scope> [--accept C-x,C-y]  diff the corrected analysis against the scored register; exit 1 = REFUSED
Reads  the live analysis Markdown (converted in memory), analysis/gauntlet/<scope>/claims-round<n>.json of the last aggregated
       round (the scored register), every round's critic files (accept_if), round*-issues.md, postpass-baseline.json and
       postpass-justifications.md (kind `postpass`, template templates/postpass-justifications.md).
Refuses when a claim id was added or removed; when a scored claim's statement, evidence or target changed without a justification
row (and, where a critic recorded an accept_if, without `accept_if_kept`); when a changed claim lost an anchor (figure, locator,
id or quoted term) that both its accept_if and its scored text carry - such a change needs a re-score, or `--accept <ids>` by the
orchestrator (logged in the report). Lists as UNVERIFIED every locator in the corrected analysis that neither the register, the
baseline nor the issues/critic files contain: the post-pass role has no evidence access, so these go to the owning role.
Writes analysis/gauntlet/<scope>/postpass-check.md (also the per-scope log of changed claims and table rows).
"""
import json, os, re, sys, glob, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, spec, scope_info, load_json, method, relp

LOC = re.compile(r"(?:[\w.-]+/)+[\w.-]+\.[A-Za-z]\w{0,11}(?::\d+(?:-\d+)?)?|\bPS-7-\d+\b|\bC-[\w.-]+-\d+\b|\bSRC-\d+(?:#\S+)?|\S+\.xlsx![^!\s]+![A-Z]+\d+")
ANCHOR = re.compile(r"`[^`]+`|\"[^\"]{2,60}\"|(?<![\w.])\d+(?:[.,]\d+)?\s?%?(?![\w])|" + LOC.pattern)

def gd(scope): return os.path.join(ROOT, "analysis", "gauntlet", scope)
def norm(t): return re.sub(r"\s+", " ", str(t or "")).strip()
def ctext(c): return " ".join([c.get("statement", ""), " ".join(c.get("evidence") or []), c.get("target") or ""])
def locators(text): return {x.rstrip(".,;:)") for x in LOC.findall(text or "")}

def current(scope):
    import md_to_json
    js, md, kind, _, _ = scope_info(scope); SP, _ = spec()
    data, _ = md_to_json.convert(kind, open(md, encoding="utf-8").read(), SP)
    return data, kind, md

def baseline(scope):
    js, md, kind, _, _ = scope_info(scope)
    if not os.path.exists(js): sys.exit(f"missing {relp(js, ROOT)}")
    os.makedirs(gd(scope), exist_ok=True); out = os.path.join(gd(scope), "postpass-baseline.json")
    json.dump({"scope": scope, "taken_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "data": load_json(js, {})}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"post-pass baseline -> {relp(out, ROOT)}", file=sys.stderr); return out

def accept_ifs(scope, rnd):
    """claim id -> the last non-empty accept_if any critic recorded up to the scored round"""
    out = {}
    for r in range(1, rnd + 1):
        for fp in sorted(glob.glob(os.path.join(gd(scope), f"round{r}-*.json"))):
            if re.search(r"-(result|amend)\.json$|pre-amend", fp): continue
            for x in (load_json(fp, {}) or {}).get("scores", []) or []:
                if (x.get("accept_if") or "").strip(): out[x["claim_id"]] = x["accept_if"].strip()
    return out

def known_text(scope, rnd, reg):
    """everything the scored process has already seen: register, issues files, critic files, baseline"""
    parts = [ctext(c) for c in reg.get("claims", [])]
    for fp in glob.glob(os.path.join(gd(scope), "round*-issues.md")) + glob.glob(os.path.join(gd(scope), "round*-*.json")):
        if "result" in fp: continue
        parts.append(open(fp, encoding="utf-8").read())
    bp = os.path.join(gd(scope), "postpass-baseline.json")
    if os.path.exists(bp): parts.append(json.dumps(load_json(bp, {}).get("data", {}), ensure_ascii=False))
    return "\n".join(parts)

def row_strings(data, kind):
    import rows
    SP, _ = spec(); idx, _ = rows.build_index(kind, data, SP, method(), assign=False)
    return {f"{s}#{rid}": {k: v for k, v in row.items() if k not in ("rid", "claimed_by")} for s, ent in idx.items() for rid, row in ent["rows"].items()}

def check(scope, accept=()):
    d = gd(scope)
    rounds = sorted(int(m.group(1)) for f in (os.listdir(d) if os.path.isdir(d) else []) for m in [re.match(r"round(\d+)-result\.json$", f)] if m)
    if not rounds: sys.exit(f"REFUSED: {scope} has no aggregated round - a post-pass follows a pass")
    rnd = rounds[-1]; snap = os.path.join(d, f"claims-round{rnd}.json")
    reg = load_json(snap, None) or load_json(os.path.join(d, "claims.json"), {})
    data, kind, md = current(scope)
    old = {c["id"]: c for c in reg.get("claims", [])}; new = {c["id"]: c for c in data.get("claims", [])}
    refused, lines = [], []
    added = sorted(set(new) - set(old)); removed = sorted(set(old) - set(new))
    if added or removed: refused.append(f"claim ids changed (added {added or '-'}, removed {removed or '-'}) - ids and count stay byte-identical in a post-pass")
    jp = os.path.join(d, "postpass-justifications.md"); just = {}
    if os.path.exists(jp):
        import md_to_json
        SP, _ = spec(); jd, _ = md_to_json.convert("postpass", open(jp, encoding="utf-8").read(), SP)
        for r in jd.get("justifications", []): just[r.get("claim_id")] = r
    acc = accept_ifs(scope, rnd); changed = []
    for cid in sorted(set(old) & set(new)):
        o, n = old[cid], new[cid]
        diff = [f for f in ("statement", "evidence", "target") if norm(o.get(f) if f != "evidence" else ";".join(o.get(f) or [])) != norm(n.get(f) if f != "evidence" else ";".join(n.get(f) or []))]
        if not diff: continue
        changed.append(cid); j = just.get(cid) or {}; a = acc.get(cid, "")
        lines += [f"### {cid} ({', '.join(diff)} changed)", f"- scored: {norm(o.get('statement'))[:300]}", f"- now:    {norm(n.get('statement'))[:300]}"] + ([f"- accept_if: {a}"] if a else []) + [f"- justification: {j.get('justification') or '(none)'}" + (f" | accept_if kept: {j.get('accept_if_kept')}" if j.get("accept_if_kept") else "")]
        if cid in accept: lines.append("- ACCEPTED by the orchestrator (--accept)"); continue
        if not (j.get("justification") or "").strip(): refused.append(f"{cid}: scored {'/'.join(diff)} changed without a justification row in {relp(jp, ROOT)}")
        elif a and not (j.get("accept_if_kept") or "").strip(): refused.append(f"{cid}: changed, but the row does not say how the accept_if is kept ({a[:120]})")
        lost = sorted({t for t in ANCHOR.findall(a)} & {t for t in ANCHOR.findall(ctext(o))} - {t for t in ANCHOR.findall(ctext(n))}) if a else []
        if lost: refused.append(f"{cid}: the change drops {', '.join(lost[:6])} - carried by both the accept_if and the scored text; this needs a re-score (or --accept {cid})")
    known = known_text(scope, rnd, reg); now_locs = set()
    for c in new.values(): now_locs |= locators(ctext(c))
    rows_now = row_strings(data, kind)
    for r in rows_now.values(): now_locs |= locators(json.dumps(r, ensure_ascii=False))
    unverified = sorted(l for l in now_locs if l not in known and re.sub(r":\d+(?:-\d+)?$", "", l) not in known)
    bp = os.path.join(d, "postpass-baseline.json"); row_changes = []
    if os.path.exists(bp):
        before = row_strings(load_json(bp, {}).get("data", {}), kind)
        for k in sorted(set(before) | set(rows_now)):
            if k not in before: row_changes.append(f"- {k}: new row")
            elif k not in rows_now: row_changes.append(f"- {k}: removed")
            elif before[k] != rows_now[k]: row_changes.append(f"- {k}: " + ", ".join(f for f in rows_now[k] if before[k].get(f) != rows_now[k].get(f)))
    verdict = "REFUSED" if refused else "OK"
    rep = [f"# Post-pass check: {scope} - {verdict}", "", f"Scored register: `{relp(snap, ROOT)}` (round {rnd}); live file `{relp(md, ROOT)}`; checked {time.strftime('%Y-%m-%dT%H:%M:%S')}.", ""]
    rep += [f"## Refusals ({len(refused)})"] + [f"- {x}" for x in refused] + ["", f"## Changed scored claims ({len(changed)})"] + (lines or ["(none)"])
    rep += ["", f"## UNVERIFIED locators ({len(unverified)}) - not in the register, the baseline or the issues; the owning role verifies them before they stay"] + ([f"- {x}" for x in unverified] or ["(none)"])
    rep += ["", "## Changed table rows (corrections log)" + ("" if os.path.exists(bp) else " - no baseline: run `dbcx postpass baseline <scope>` before the next post-pass")] + (row_changes or ["(none)"])
    if accept: rep += ["", f"Accepted by the orchestrator: {', '.join(accept)}"]
    out = os.path.join(d, "postpass-check.md"); open(out, "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print(f"{verdict}: {len(changed)} changed scored claim(s), {len(refused)} refusal(s), {len(unverified)} unverified locator(s), {len(row_changes)} changed row(s) -> {relp(out, ROOT)}")
    for x in refused: print("  REFUSED", x)
    return not refused

def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("check", "baseline"): sys.exit(__doc__)
    if a[0] == "baseline": baseline(a[1]); return
    acc = tuple(x.strip() for x in (a[a.index("--accept") + 1] if "--accept" in a else "").split(",") if x.strip())
    sys.exit(0 if check(a[1], acc) else 1)

if __name__ == "__main__":
    main()
