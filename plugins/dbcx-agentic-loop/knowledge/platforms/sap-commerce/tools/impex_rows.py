#!/usr/bin/env python3
"""Count ImpEx rows and distinct key values per item type the way ImpEx actually parses (D5 of the first engagement):
a header (INSERT/INSERT_UPDATE/UPDATE/REMOVE <Type>[modifier];...) stays active until the NEXT header - blank lines and '#' comments do NOT
close a block, and a type's block may appear anywhere in a file, not only first. A quoted value ("...", "" = escaped quote) may span several
physical lines and counts as ONE row; a physical line ending in a single '\\' continues on the next line (ImpEx line continuation).

Usage: python3 impex_rows.py --type <ItemType> [--key <column index, default 0>] <file-or-folder> ...   [--headers INSERT_UPDATE,INSERT,UPDATE,REMOVE]
       python3 impex_rows.py --files <file-or-folder> ...
--type mode prints per file: header count, data rows, distinct key values (column index within the header, 0 = first column); totals; the RULE
line to quote. Macro lines ($x = ...) and '#' comments are skipped; ';' inside quotes is honoured for the key column split.
--files mode (no --type needed) prints per file: non-blank lines, comment lines, scripting directives ('#%'), macro lines, header lines, data
rows (all types), flagging COMMENT-ONLY files (no data rows, no headers, but comment lines) - e.g. to find dead ImpEx files.
"""
import os, re, sys, csv, io

DEFAULT_HEADERS = ["INSERT_UPDATE", "INSERT", "UPDATE", "REMOVE"]

def header_re(kinds):
    return re.compile(r"^(" + "|".join(kinds) + r")\s+(\w+)\s*(?:\[[^\]]*\])?\s*(;|$)", re.I)

def logical_lines(path):
    """Physical lines of an ImpEx file, joined into logical lines: a trailing single '\\' joins the next physical line, and an
    odd running count of unescaped '"' (double '""' is one escaped literal quote, not a toggle) keeps a quoted value - and
    anything inside it, including '#' or blank lines - open until the quote balances again."""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        phys = fh.read().splitlines()
    joined = []; cont = None
    for ln in phys:
        ln = cont + ln if cont is not None else ln
        if ln.endswith("\\") and not ln.endswith("\\\\"): cont = ln[:-1]
        else: joined.append(ln); cont = None
    if cont is not None: joined.append(cont)
    out = []; buf = None; in_quote = False
    for ln in joined:
        buf = ln if buf is None else buf + "\n" + ln
        i = 0
        while i < len(ln):
            if ln[i] == '"':
                if i + 1 < len(ln) and ln[i + 1] == '"': i += 2; continue
                in_quote = not in_quote
            i += 1
        if not in_quote: out.append(buf); buf = None
    if buf is not None: out.append(buf)
    return out

def parse(path, wanted, key_idx, header_kinds):
    rows = 0; keys = set(); headers = 0; active = False; hre = header_re(header_kinds)
    for raw in logical_lines(path):
        st = raw.strip()
        if not st or st.startswith("#"): continue          # do NOT close the block (a '#' inside an open quote never reaches here)
        if st.startswith("$"): continue                     # macro definition
        m = hre.match(st)
        if m:
            active = m.group(2).lower() == wanted.lower()
            if active: headers += 1
            continue
        if active:
            rows += 1
            cells = next(csv.reader(io.StringIO(st), delimiter=";", quotechar='"'), [])
            cells = cells[1:] if cells and cells[0] == "" else cells   # data rows start with ';'
            if len(cells) > key_idx: keys.add(cells[key_idx].strip())
    return headers, rows, keys

def file_stats(path):
    """Pure per-file counts for the inventory scanner: non_blank, comment, directive ('#%'), macro, headers, data_rows (all
    types), comment_only (data_rows == 0 and headers == 0 and comment > 0 - a dead ImpEx file)."""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        phys = fh.read().splitlines()
    non_blank = comment = directive = macro = 0; in_quote = False
    for ln in phys:
        st = ln.strip()
        if st: non_blank += 1
        if not in_quote and st:
            if st.startswith("#%"): directive += 1
            elif st.startswith("#"): comment += 1
            elif st.startswith("$"): macro += 1
        i = 0
        while i < len(ln):
            if ln[i] == '"':
                if i + 1 < len(ln) and ln[i + 1] == '"': i += 2; continue
                in_quote = not in_quote
            i += 1
    headers = data_rows = 0; active = False; hre = header_re(DEFAULT_HEADERS)
    for raw in logical_lines(path):
        st = raw.strip()
        if not st or st.startswith("#") or st.startswith("$"): continue
        m = hre.match(st)
        if m: headers += 1; active = True; continue
        if active: data_rows += 1
    return {"non_blank": non_blank, "comment": comment, "directive": directive, "macro": macro, "headers": headers,
            "data_rows": data_rows, "comment_only": data_rows == 0 and headers == 0 and comment > 0}

def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p): files += [os.path.join(dp, f) for dp, _, fs in os.walk(p) for f in fs if f.lower().endswith((".impex", ".csv"))]
        else: files.append(p)
    return files

def main():
    a = sys.argv[1:]
    if "--files" in a:
        paths = [x for x in a if not x.startswith("--")]   # --files takes no value, unlike --type/--key/--headers below
        files = collect(paths); tot = {"non_blank": 0, "comment": 0, "directive": 0, "macro": 0, "headers": 0, "data_rows": 0}; nco = 0
        for f in sorted(files):
            s = file_stats(f); flag = " COMMENT-ONLY" if s["comment_only"] else ""
            print(f"{os.path.relpath(f):70s} non-blank {s['non_blank']:5d} comment {s['comment']:4d} directive {s['directive']:3d} macro {s['macro']:3d} headers {s['headers']:3d} data rows {s['data_rows']:5d}{flag}")
            for k in tot: tot[k] += s[k]
            if s["comment_only"]: nco += 1
        print(f"TOTAL non-blank {tot['non_blank']} comment {tot['comment']} directive {tot['directive']} macro {tot['macro']} headers {tot['headers']} data rows {tot['data_rows']} across {len(files)} files, {nco} of them COMMENT-ONLY")
        print("RULE: a file is COMMENT-ONLY when data rows == 0 and headers == 0 and comment lines > 0; '#' is a comment, '#%' is a scripting directive (counted separately); '$' is a macro; quoted multi-line values and trailing '\\' continuations count as one row.")
        return
    if "--type" not in a: sys.exit(__doc__)
    t = a[a.index("--type") + 1]; key_idx = int(a[a.index("--key") + 1]) if "--key" in a else 0
    kinds = a[a.index("--headers") + 1].split(",") if "--headers" in a else DEFAULT_HEADERS
    paths = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--type", "--key", "--headers"))]
    files = collect(paths)
    th = tr = 0; tk = set(); nf = 0
    for f in sorted(files):
        h, r, k = parse(f, t, key_idx, kinds)
        if h: nf += 1; th += h; tr += r; tk |= k; print(f"{os.path.relpath(f):70s} headers {h:3d} rows {r:5d} distinct keys {len(k):5d}")
    print(f"RULE: type {t}, header kinds {kinds}, key = column {key_idx} of the header; a header stays active until the next header (blank lines and '#' comments do not close a block); a Type[modifier] header is recognised; a quoted value spanning several physical lines, or a line joined by a trailing '\\', counts as one row; macro lines skipped -> {nf} files with the type, {th} header blocks, {tr} data rows, {len(tk)} distinct key values across all files")

if __name__ == "__main__":
    main()
