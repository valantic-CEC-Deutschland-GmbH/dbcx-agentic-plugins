#!/usr/bin/env python3
"""Section 7 of reference/platform-standard.md as governed rows (CP-9): stable ids, provenance, affected claims - cite by id, never by line.

Usage: dbcx reference list [--since YYYY-MM-DD]                   print rows (id, date, provenance, fact head)
       dbcx reference add --fact "..." --applies "..." --url "..." [--quote "..."] [--provenance researcher|critic|refutation] [--affects C-x,C-y] [--by <agent>] [--dry-run]
                                                                   append ONE row with the next id PS-7-NNN and today's date (the only sanctioned way to write section 7);
                                                                   an unknown flag is refused, not silently ignored; --dry-run prints the row without writing it;
                                                                   --quote = the verbatim sentence(s) of the page that carry the fact (>= 20 letters and digits, fragments
                                                                   joined by ' […] '): stored in an optional 9th column `Quote` (the header gains it with the first quote;
                                                                   8-column rows stay valid) and used by the quote gate (`dbcx evidence quotes`)
       dbcx reference correct <id> [--fact "..."] [--applies "..."] [--url "..."] [--date YYYY-MM-DD] [--by <agent>] [--dry-run]
                                                                   repair any of fact/applies/url/date in place (at least one required): a changed fact keeps the
                                                                   old text in a `superseded by` note, the row is re-dated (today, unless --date), provenance ->
                                                                   refutation, and every scope whose claims cite the id is printed (they must be re-scored or text-corrected)
       dbcx reference renumber                                      give ids to legacy 4-column rows (Fact | Applies | URL | Date) and migrate the table to the 7-column shape
       dbcx reference cite <id>                                     print the row (for a brief)
       dbcx reference title <id> --title "..." --summary "..." [--applies "..."] [--lang en]
                                                                   K6 sidecar: writes reference/platform-standard.titles.<lang>.json ({id: {title, summary[, applies]}}),
                                                                   the German title + short statement the Quellen sheet needs (a missing title falls back to
                                                                   the English fact head and is a customer-edition hygiene error); --applies is the Quellen
                                                                   sheet's "applies to" text in that language (else the row's own text), alone on a titled entry
       dbcx reference titles [--missing] [--lang en] [--cited-in <xlsx> ...]
                                                                   list every id's titling state, or (--missing) only the ids without one; --cited-in restricts
                                                                   to ids actually cited (as `[Qn]`) in the given workbook(s)
       dbcx reference status <id> <verified|verify|disputed>       set a row's status explicitly (e.g. after `dbcx render research`
                                                                   independently re-verifies a `verify` row, promote it to `verified`); `add`/`correct` derive
                                                                   it automatically otherwise - a critic must never treat a `verify`/`disputed` row as fact.
       dbcx reference delta --since <YYYY-MM-DD|last-final>        rows added or corrected since the date (or since the most recently
                                                                   finalised scope's analysis file), with the FINAL scopes whose claims cite the id or whose
                                                                   `Affects claims` names them - run at the deliverable-build boundary.
Rows appended by a critic mid-scope have had exactly one reader - `dbcx render research` re-verifies rows with provenance critic/refutation.
"""
import os, re, sys, time, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, REF_DIR, relp

STATUSES = ("verified", "verify", "disputed")
def derive_status(provenance, fact):
    """verified | verify | disputed, derived from provenance and a superseded note in the fact
    text when no status is stored explicitly. A refutation is itself unreviewed and disputes the row
    it replaces; a critic's mid-scope addition has had exactly one reader (`dbcx render research`
    re-verifies it); only the researcher's own verification (URL + date is the whole job) counts as
    verified."""
    p = (provenance or "").strip().lower()
    if p.startswith("refutation") or "[superseded" in (fact or "").lower(): return "disputed"
    if p.startswith("researcher"): return "verified"
    return "verify"

ADD_FLAGS = {"--fact", "--applies", "--url", "--quote", "--provenance", "--affects", "--by", "--dry-run"}
CORRECT_FLAGS = {"--fact", "--applies", "--url", "--date", "--by", "--dry-run"}
def check_flags(args, known):
    unknown = sorted({x for x in args if x.startswith("--") and x not in known})
    if unknown: sys.exit(f"unknown flag(s): {', '.join(unknown)} (known: {', '.join(sorted(known))})")

def titles_path(lang): return os.path.join(REF_DIR, f"platform-standard.titles.{lang}.json")
def load_titles(lang):
    p = titles_path(lang)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
def save_titles(lang, data):
    os.makedirs(os.path.dirname(titles_path(lang)), exist_ok=True)
    open(titles_path(lang), "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))

REF = os.path.join(REF_DIR, "platform-standard.md")   # project-level: shared by every run of the engagement
HDR = "| Id | Fact | Applies to (version) | URL | Date | Provenance | Affects claims | Status |"
SEP = "|---|---|---|---|---|---|---|---|"
HDR_Q = HDR + " Quote |"; SEP_Q = SEP + "---|"   # optional 9th column, added with the first quote

def quote_of(cells): return cells[8] if len(cells) > 8 else ""
def quote_cell(cells): return [cells[8]] if len(cells) > 8 and cells[8] else []   # a rewritten row keeps its quote

def split(line): return [c.strip() for c in line.strip().strip("|").split("|")]

def load():
    txt = open(REF, encoding="utf-8").read(); lines = txt.split("\n")
    s7 = next((i for i, l in enumerate(lines) if l.startswith("## 7")), None)
    if s7 is None: sys.exit("no section 7 in reference/platform-standard.md")
    end = next((i for i in range(s7 + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    rows = []; hdr_i = None
    for i in range(s7 + 1, end):
        l = lines[i]
        if l.startswith("|") and hdr_i is None: hdr_i = i; continue
        if l.startswith("|---") or not l.startswith("|"): continue
        rows.append((i, split(l)))
    return lines, s7, end, hdr_i, rows

def norm(cells):
    """8-column shape (... | Affects claims | Status); a legacy 7-column row (no Status yet) and a
    legacy 4-column row (Fact | Applies | URL | Date) both get a Status derived from provenance/fact."""
    if len(cells) >= 8: return cells[:8]
    if len(cells) == 7: return cells + [derive_status(cells[5], cells[1])]
    if len(cells) == 4: return ["", cells[0], cells[1], cells[2], cells[3], "researcher", "", derive_status("researcher", cells[0])]
    c = (cells + [""] * 8)[:8]
    if not c[7]: c[7] = derive_status(c[5], c[1])
    return c

def fmt(c): return "| " + " | ".join(x.replace("|", "/") for x in c) + " |"

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    lines, s7, end, hdr_i, rows = load()
    def opt(k, d=""): return a[a.index(k) + 1] if k in a else d
    if a[0] == "list":
        since = opt("--since")
        for i, c in rows:
            c = norm(c)
            if since and c[4] < since: continue
            print(f"{c[0] or '(no id)':10s} {c[4]:10s} {c[5]:12s} {c[7]:9s} {c[1][:110]}")
        print(f"{len(rows)} rows")
    elif a[0] == "cite":
        for i, c0 in rows:
            c = norm(c0)
            if c[0] == a[1]: print(fmt(c + quote_cell(c0))); return
        sys.exit("no such id")
    elif a[0] == "renumber":
        ids = [int(m.group(1)) for _, c in rows for m in [re.match(r"PS-7-(\d+)", norm(c)[0])] if m]; nxt = max(ids, default=0) + 1; out = []
        for i, c0 in rows:
            c = norm(c0)
            if not c[0]: c[0] = f"PS-7-{nxt:03d}"; nxt += 1
            lines[i] = fmt(c + quote_cell(c0))
        if hdr_i is not None: lines[hdr_i] = HDR_Q if any(quote_of(c0) for _, c0 in rows) else HDR; lines[hdr_i + 1] = SEP_Q if lines[hdr_i] == HDR_Q else SEP
        open(REF, "w", encoding="utf-8").write("\n".join(lines)); print(f"renumbered: {len(rows)} rows now carry ids PS-7-001..PS-7-{nxt - 1:03d}")
    elif a[0] == "add":
        check_flags(a[1:], ADD_FLAGS)
        ids = [int(m.group(1)) for _, c in rows for m in [re.match(r"PS-7-(\d+)", norm(c)[0])] if m]; nid = f"PS-7-{max(ids, default=0) + 1:03d}"
        provenance = opt("--provenance", "critic") + (f" ({opt('--by')})" if "--by" in a else "")
        c = [nid, opt("--fact"), opt("--applies"), opt("--url"), time.strftime("%Y-%m-%d"), provenance, opt("--affects"), derive_status(provenance, opt("--fact"))]
        if not c[1] or not c[3]: sys.exit("--fact and --url are required")
        if "--quote" in a:
            from evidence import qnorm
            if len(qnorm(opt("--quote"))) < 20: sys.exit("--quote needs the verbatim sentence(s) of the page: at least 20 letters and digits")
            c.append(opt("--quote").replace("\n", " "))
        if "--dry-run" in a: print(f"DRY-RUN: would add {fmt(c)}"); return
        insert_at = (rows[-1][0] + 1) if rows else ((hdr_i + 2) if hdr_i is not None else end)
        if hdr_i is None: lines[insert_at:insert_at] = [HDR_Q, SEP_Q] if len(c) > 8 else [HDR, SEP]; insert_at += 2
        elif len(c) > 8 and "| Quote |" not in lines[hdr_i]: lines[hdr_i] = HDR_Q; lines[hdr_i + 1] = SEP_Q
        lines.insert(insert_at, fmt(c)); open(REF, "w", encoding="utf-8").write("\n".join(lines))
        print(f"added {nid}" + (f" - affects claims {c[6]}: these re-enter the next delta (tell the orchestrator / the running critics)" if c[6] else ""))
    elif a[0] == "correct":
        check_flags(a[2:], CORRECT_FLAGS)
        tid = a[1]
        if not any(f in a for f in ("--fact", "--applies", "--url")): sys.exit("dbcx reference correct <id> needs at least one of --fact/--applies/--url to change")
        for i, c0 in rows:
            c = norm(c0)
            if c[0] == tid:
                old = c[1]
                if "--fact" in a: c[1] = opt("--fact") + f" [superseded {time.strftime('%Y-%m-%d')}; earlier text: {old[:140]}]"
                if "--applies" in a: c[2] = opt("--applies")
                if "--url" in a: c[3] = opt("--url")
                c[4] = opt("--date", time.strftime("%Y-%m-%d")); c[5] = "refutation" + (f" ({opt('--by')})" if "--by" in a else "")
                c[7] = derive_status(c[5], c[1])
                c += quote_cell(c0)
                if "--dry-run" in a: print(f"DRY-RUN: would correct {tid} -> {fmt(c)}"); return
                lines[i] = fmt(c); open(REF, "w", encoding="utf-8").write("\n".join(lines))
                cit = [relp(f, ROOT) for f in glob.glob(P("analysis", "**", "*.md"), recursive=True) if tid in open(f, encoding="utf-8", errors="ignore").read()]
                print(f"corrected {tid}; cited in: {', '.join(cit) if cit else 'nothing yet'} - a refutation is itself an unreviewed claim: state which half of the old row it kills and which it leaves; notify in-flight agents (dbcx status inflight list)"); return
        sys.exit("no such id")
    elif a[0] == "title":
        tid = a[1]; lang = opt("--lang", "en")
        ids = {norm(c)[0] for _, c in rows if norm(c)[0]}
        if tid not in ids: sys.exit(f"no such id {tid} in section 7")
        t = load_titles(lang); e = dict(t.get(tid, {}))
        if "--title" not in a and not ("--applies" in a and e.get("title")): sys.exit('dbcx reference title <id> --title "..." --summary "..." [--applies "..."] [--lang en]')
        if "--title" in a: e.update(title=opt("--title"), summary=opt("--summary", e.get("summary", "")))
        if "--applies" in a: e["applies"] = opt("--applies")
        t[tid] = e
        save_titles(lang, t); print(f"{tid}: {lang} title set")
    elif a[0] == "titles":
        lang = opt("--lang", "en"); t = load_titles(lang)
        all_ids = [norm(c)[0] for _, c in rows if norm(c)[0]]
        wanted = set(all_ids)
        if "--cited-in" in a:
            files = []; i = a.index("--cited-in") + 1
            while i < len(a) and not a[i].startswith("--"): files.append(a[i]); i += 1
            import openpyxl
            cited = set()
            for f in files:
                wb = openpyxl.load_workbook(f, data_only=True)
                for ws in wb.worksheets:
                    for row in ws.iter_rows():
                        for cell in row:
                            if isinstance(cell.value, str): cited |= {f"PS-7-{int(n):03d}" for n in re.findall(r"\[Q(\d+)\]", cell.value)}
            wanted &= cited
        if "--missing" in a:
            missing = sorted(x for x in wanted if x not in t)
            for x in missing: print(x)
            print(f"{len(missing)} id(s) without a {lang} title" + (" (cited in the given workbook(s))" if "--cited-in" in a else ""))
        else:
            for x in sorted(wanted): print(f"{x:12s} {'OK' if x in t else 'missing':8s} {t.get(x, {}).get('title', '')}")
    elif a[0] == "status":
        tid = a[1]; newstatus = a[2] if len(a) > 2 else ""
        if newstatus not in STATUSES: sys.exit(f"dbcx reference status <id> <{'|'.join(STATUSES)}>")
        for i, c0 in rows:
            c = norm(c0)
            if c[0] == tid:
                c[7] = newstatus; lines[i] = fmt(c + quote_cell(c0)); open(REF, "w", encoding="utf-8").write("\n".join(lines))
                print(f"{tid}: status -> {newstatus}"); return
        sys.exit("no such id")
    elif a[0] == "delta":
        since_arg = opt("--since")
        if not since_arg: sys.exit("dbcx reference delta --since <YYYY-MM-DD|last-final>")
        from common import load_json, STATUS_PATH, method, scope_info
        st = load_json(STATUS_PATH, {})
        final_scopes = {n for n, sc in (st.get("scopes") or {}).items() if sc.get("status") == "final"}
        for n, ph in (st.get("phases") or {}).items():
            if ph.get("status") == "final": final_scopes.add(ph.get("scope") or n)
        if since_arg == "last-final":
            mth = method(); dates = []
            for name in final_scopes:
                try:
                    js, md, kind, role, agent = scope_info(name, mth)
                    dates.append(time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(md))))
                except (OSError, SystemExit): pass
            if not dates: sys.exit("no final scope with a readable analysis file - nothing to delta against")
            since = max(dates)
        else: since = since_arg
        changed = [norm(c) for _, c in rows if norm(c)[4] >= since]
        if not changed: print(f"no reference row added or corrected since {since}"); return
        print(f"{len(changed)} reference row(s) changed since {since} (run at the deliverable-build boundary; a hit means a FINAL scope needs re-checking):")
        for c in changed:
            rid = c[0]; affected = set()
            for cid in [x.strip() for x in (c[6] or "").split(",") if x.strip()]:
                mm = re.match(r"C-(.+)-\d+$", cid)
                if mm: affected.add(mm.group(1))
            for f in glob.glob(P("analysis", "**", "*.md"), recursive=True):
                try: txt = open(f, encoding="utf-8", errors="ignore").read()
                except OSError: continue
                if rid and rid in txt:
                    # gauntlet files live in a directory NAMED after the scope; every other method output
                    # (analysis/<units|scopes|consolidated|...>/<name>.md) names it in the FILENAME instead.
                    mm = re.search(r"[/\\]gauntlet[/\\]([^/\\]+)[/\\]", f)
                    if mm: affected.add(mm.group(1))
                    mm = re.search(r"[/\\]analysis[/\\][^/\\]+[/\\]([^/\\.]+)\.md$", f)
                    if mm: affected.add(mm.group(1))
            hits = sorted(affected & final_scopes)
            print(f"  {rid} ({c[4]}, {c[7]}): {c[1][:90]}" + (f" -> re-check final scope(s): {', '.join(hits)}" if hits else " -> no final scope affected yet"))
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
