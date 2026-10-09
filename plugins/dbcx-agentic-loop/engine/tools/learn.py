#!/usr/bin/env python3
"""Structured learnings log (CP-14): agents report learnings in their final message, the orchestrator records them here -
only this tool writes docs/LEARNINGS.md (B14), entries are short and typed so a later session can turn them into plugin changes.

Usage: dbcx learn add --section A|B|C|D|E|F --title "..." --what "..." --evidence "..." --generalises "..." --proposal "..." --touches "plugin/file"
                       [--by <agent>] [--status hypothesis|proposal]
                                           --status (default hypothesis) is the entry's OWN confidence, shown in `list`: a single
                                           occurrence recorded in the heat of the moment is a hypothesis; promote it to proposal only
                                           after a second occurrence or a code trace confirms it (most entries here start as one).
       dbcx learn list [--section X] [--unresolved]      dbcx learn open  (section F items)      dbcx learn close <id> "<how it resolved>"
       dbcx learn resolve <id> --as applied|project|upstream|dismissed --ref "<plugin version / commit>" [--note "..."]
                                           the verdict for one entry: the status line records it; applied / project / dismissed compact the entry to
                                           header + when + what + status (the commit or the note carries the rest), the id stays; upstream (belongs in
                                           the plugin, goes to the maintainer with `learn export`) keeps the full entry. A later "challenge the
                                           learnings" session works from `dbcx learn list --unresolved` only.
       dbcx learn repro | anonymise | export | import    the standalone-reproducible export for the plugin maintainer and its import
                                           (engine/tools/learn_export.py, `dbcx learn export --help`)
       dbcx learn harvest                  RETIRED (the installed plugin is read-only) - refuses and points to `dbcx learn export`
Sections: A method findings that cost rounds - B orchestration mechanics - C agent behaviour to encode - D knowledge-pack / domain traps - E what worked, keep - F open items / handover.
Keep --what to one or two sentences and --evidence to file:line / scope / figures; the log is for a reader who was not here, not a narrative.
"""
import os, sys, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RUN as ROOT, P, PROJECT_DIR, relp

LOG = P("docs", "LEARNINGS.md")
HEAD = """# Learnings log

Written ONLY via `dbcx learn add` / `dbcx learn resolve` (agents put learnings in their final report; the orchestrator records them). One entry =
one fact for a fresh session that will turn it into a plugin change: what happened, evidence, why it generalises, proposed change + file touched.
Sections: A method - B orchestration - C agent behaviour - D pack/domain traps - E what worked (keep) - F open items (verify on disk before acting).
Status: `recorded` = not yet judged; `upstream` = for the plugin maintainer (`dbcx learn export`, entry kept in full); `applied in plugin <ref>` /
`project-only` / `dismissed` = judged (entry compacted, id kept). Challenge only
`dbcx learn list --unresolved`.

"""

def entries():
    if not os.path.exists(LOG): return []
    return re.findall(r"^### (L-\d{3}) \[([A-F])\] (.+)$", open(LOG, encoding="utf-8").read(), re.M)

def next_id():
    """Next free id: one above the highest header id on disk, whatever its shape (an untitled stub still occupies its number)."""
    if not os.path.exists(LOG): return 1
    ids = [int(x) for x in re.findall(r"^### L-(\d{3})\b", open(LOG, encoding="utf-8").read(), re.M)]
    return (max(ids) + 1) if ids else 1

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] in ("--help", "-h", "help") or (a[0] == "add" and any(x in a for x in ("--help", "-h"))): print(__doc__); return
    def opt(k, d=""): return a[a.index(k) + 1] if k in a else d
    if a[0] == "add":
        # A malformed call would append an untitled stub that entries() cannot see, so the id counter stays at 0
        # and every later entry reuses the first id. Require the two fields a reader needs; count ids from every header.
        sec = opt("--section", "B").upper()
        if sec not in "ABCDEF" or len(sec) != 1: sys.exit(f"--section must be one of A-F, got {sec!r}\n" + __doc__)
        missing = [k for k in ("--title", "--what") if not opt(k).strip() or opt(k).startswith("--")]
        if missing: sys.exit(f"dbcx learn add: {' and '.join(missing)} required (nothing recorded)\n" + __doc__)
        conf = opt("--status", "hypothesis")
        if conf not in ("hypothesis", "proposal"): sys.exit(f"--status must be hypothesis or proposal, got {conf!r}\n" + __doc__)
        n = next_id(); lid = f"L-{n:03d}"
        if not os.path.exists(LOG): os.makedirs(os.path.dirname(LOG), exist_ok=True); open(LOG, "w", encoding="utf-8").write(HEAD)
        body = [f"### {lid} [{sec}] {opt('--title')}", f"- when: {time.strftime('%Y-%m-%d %H:%M')}" + (f" - by {opt('--by')}" if "--by" in a else ""), f"- what: {opt('--what')}", f"- evidence: {opt('--evidence')}", f"- generalises: {opt('--generalises')}", f"- proposal: {opt('--proposal')}", f"- touches: {opt('--touches')}", f"- confidence: {conf}", f"- status: {'open' if sec == 'F' else 'recorded'}", ""]
        open(LOG, "a", encoding="utf-8").write("\n".join(body) + "\n"); print(f"{lid} recorded in section {sec} ({conf})")
    elif a[0] == "list":
        txt = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
        for lid, sec, title in entries():
            if "--section" in a and sec != opt("--section").upper(): continue
            m = re.search(r"^### " + re.escape(lid) + r" .*?^- status: (.+?)$", txt, re.M | re.S); status = m.group(1).strip() if m else "?"
            if "--unresolved" in a and not status.startswith(("recorded", "open")): continue
            cm = re.search(r"^### " + re.escape(lid) + r" .*?^- confidence: (.+?)$", txt, re.M | re.S); conf = cm.group(1).strip() if cm else "hypothesis"
            print(f"{lid} [{sec}] ({conf}) {title}" + ("" if "--unresolved" in a else f"  - {status}"))
    elif a[0] == "resolve":
        lid = a[1] if len(a) > 1 else ""; how = opt("--as"); ref = opt("--ref"); note = opt("--note")
        if how not in ("applied", "project", "upstream", "dismissed") or not lid: sys.exit("dbcx learn resolve <id> --as applied|project|upstream|dismissed [--ref ...] [--note ...]")
        if how == "applied" and not ref: sys.exit("--ref <plugin version / commit> is required for --as applied (where the change lives)")
        if how != "applied" and not note: sys.exit("--note is required for project / dismissed (the reason is what a later reader needs)")
        txt = open(LOG, encoding="utf-8").read()
        m = re.search(r"^(### " + re.escape(lid) + r" \[[A-F]\] .+?\n)(.*?)(?=^### |\Z)", txt, re.M | re.S)
        if not m: sys.exit(f"no entry {lid}")
        body = m.group(2); keep = [l for l in body.splitlines() if l.startswith(("- when:", "- what:"))] if how != "upstream" else [l for l in body.splitlines() if l.strip() and not l.startswith("- status:")]
        label = {"applied": f"applied in plugin {ref}", "project": "project-only", "upstream": "upstream", "dismissed": "dismissed"}[how]
        status = f"- status: {label}" + (f" ({ref})" if ref and how != "applied" else "") + (f" - {note}" if note else "") + f" [{time.strftime('%Y-%m-%d')}]"
        # the HEAD paragraph of an older log is refreshed so the reader learns the status semantics
        txt = txt[:m.start(2)] + "\n".join(keep + [status, ""]) + "\n" + txt[m.end(2):]
        txt = re.sub(r"^Append-only, written ONLY via `dbcx learn add`.*?acting\)\.\n", HEAD.split("\n", 2)[2], txt, count=1, flags=re.M | re.S)
        open(LOG, "w", encoding="utf-8").write(txt); print(f"{lid}: {label}")
    elif a[0] == "open":
        txt = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
        for m in re.finditer(r"^### (L-\d{3}) \[F\] (.+?)$(.*?)(?=^### |\Z)", txt, re.M | re.S):
            if "- status: open" in m.group(3): print(f"{m.group(1)} {m.group(2)}")
    elif a[0] == "harvest": sys.exit("REFUSED: `dbcx learn harvest` is retired - the installed plugin is read-only. `dbcx learn export` writes one anonymised, standalone-reproducible file into the engagement for the plugin maintainer (`dbcx learn export --preview` first).")
    elif a[0] in ("export", "repro", "anonymise", "import"):
        import learn_export; learn_export.main(a)
    elif a[0] == "close":
        txt = open(LOG, encoding="utf-8").read(); lid = a[1]
        m = re.search(r"(^### " + re.escape(lid) + r" .*?)(- status: open)", txt, re.M | re.S)
        if not m: sys.exit("no open entry with that id")
        txt = txt[:m.start(2)] + f"- status: closed {time.strftime('%Y-%m-%d')}: {a[2] if len(a) > 2 else ''}" + txt[m.end(2):]; open(LOG, "w", encoding="utf-8").write(txt); print(f"{lid} closed")
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
