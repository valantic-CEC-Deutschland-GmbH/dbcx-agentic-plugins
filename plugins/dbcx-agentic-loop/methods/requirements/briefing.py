"""Brief extras of the `requirements` method (called by dbcx render).

An epic analyst gets the SRC ids and titles of the sources its epic rests on plus the grep commands that turn the corpus into a
searchable evidence base; the inventory analyst gets the corpus statistics it must reconcile its Sources table with; every role that
may use the reference catalogue gets the path of the catalogue pack's `catalogue.md`; the consolidator's digest gets per-epic counts
and the integration candidates for the FR<->TR cross-check. Profile lean (split none): no epic analyses - the SET consolidator
gets the corpus rows, the grep block and every epic with its sources; its digest lists the epics with their expected counts instead.
"""
import os, re, sys, json

from common import RUN, CORPUS_DIR, load_json, read_json, CLI, relp, fwd

INTEGRATION_HINTS = ["erp", "pim", "dam", "crm", "wms", "psp", "payment", "shipping", "tax", "search", "sso", "single sign-on",
                     "interface", "api", "import", "export", "sync", "middleware", "webhook", "feed", "migration", "master data"]


def rel(p):
    p = os.path.abspath(p)
    return relp(p, RUN) if p.startswith(os.path.abspath(RUN) + os.sep) else fwd(p)


def corpus_index():
    return load_json(os.path.join(CORPUS_DIR, "index.json"), {"sources": {}, "built_at": None})


def catalogue_row(cfg):
    """CATALOGUE row: the catalogue pack's catalogue.md when a catalogue slot is set, else the configured fallback text."""
    pk = (cfg.get("_packs") or {}).get("catalogue")
    if pk:
        fp = os.path.join(pk["_dir"], pk.get("catalogue", "catalogue.md"))
        return ("CATALOGUE", f"{pk.get('display', pk['name'])} - {fp}" + ("" if os.path.exists(fp) else " (FILE MISSING - say so instead of inventing catalogue entries)"))
    return ("CATALOGUE", cfg.get("catalogue", {}).get("display", "(no reference catalogue configured)"))


def corpus_rows():
    """Full corpus pointer - for roles whose brief has no CORPUS input row of its own (the critics)."""
    idx = corpus_index()
    return [("CORPUS", f"{rel(os.path.join(CORPUS_DIR, 'index.json'))} ({len(idx.get('sources', {}))} sources, built {idx.get('built_at')}), text under {rel(os.path.join(CORPUS_DIR, 'text'))}/SRC-nnn.md"),
            ("UNEXTRACTABLE", rel(os.path.join(CORPUS_DIR, "unextractable.md")))]


def status_rows():
    """Counts only - the paths are already in the role's own input rows."""
    idx = corpus_index(); src = idx.get("sources", {})
    unex = [k for k, v in src.items() if v.get("quality") == "unextractable"]
    return [("CORPUS STATUS", f"{len(src)} sources indexed, built {idx.get('built_at')}, {sum(int(v.get('units') or 0) for v in src.values())} citable anchors, "
                              f"{len(unex)} without any text{' (' + ', '.join(unex) + ')' if unex else ''}")]


GREP_BLOCK = ("## CORPUS GREP - how to find a passage and cite it\n"
              "The corpus is text with anchors, so a document is searched the way code is searched:\n"
              "```\n"
              "grep -n \"<term>\" {text}/SRC-*.md          # every hit with its file\n"
              "{cli} corpus grep \"<regex>\"                # every hit WITH ITS LOCATOR (this is the one you cite)\n"
              "{cli} corpus show SRC-007                    # the anchor map of one source\n"
              "{cli} evidence resolve \"SRC-007#p12\"        # does this locator exist?\n"
              "```\n"
              "The anchor immediately ABOVE a hit is its locator: `<!-- SRC-007#p12 -->` -> cite `SRC-007#p12`. Never cite a line number of a corpus text file - the anchors are stable across re-indexing, line numbers are not.\n"
              "Locator shapes: `#p12` page, `#s7` slide, `#para12` paragraph block, `#table3` table, `#Sheet!R12` spreadsheet row, `#item:<id>` board item, `#frame:<name>` board frame, `#L120` line block of a text/markdown source.")


def epic_row(scope):
    ana = load_json("analysis/inventory/source_inventory.json", {})
    for e in ana.get("epics", []) or []:
        if e.get("name") == scope: return e
    return {}


def sources_block(scope):
    e = epic_row(scope); idx = corpus_index().get("sources", {})
    ids = e.get("sources") or []
    if not ids:
        return ("## YOUR SOURCES\nThe source inventory names no source for this scope (analysis/inventory/source_inventory.json). "
                "Do not fill the gap by inference: report it and work from the sources the CONTEXT names.")
    lines = [f"## YOUR SOURCES ({len(ids)} of {len(idx)} indexed sources carry this {'epic'})",
             "Read these completely before you write a single requirement; every other source is another epic's material.",
             "", "| source | title | type | anchors | text | file |", "|---|---|---|---|---|---|"]
    for sid in ids:
        s = idx.get(sid, {})
        lines.append(f"| {sid} | {s.get('title', '(not in the corpus index - report it)')} | {s.get('type', '?')} | {s.get('units', 0)} | {s.get('quality', '?')} | {s.get('path', '')} |")
    unex = [sid for sid in ids if str(idx.get(sid, {}).get("quality", "")).startswith(("unextractable", "none"))]
    if unex: lines += ["", f"NO TEXT could be extracted from {', '.join(unex)}: anything that rests on them is cited as `visual, unverified`, gets confidence low and a client question - never a requirement written as if the document had said it."]
    return "\n".join(lines)


def corpus_stats_block():
    idx = corpus_index(); src = idx.get("sources", {})
    if not src: return f"## CORPUS STATS\nThe corpus is empty - run `{CLI} corpus index` before this brief is worth anything, and report it."
    by_type, by_q = {}, {}
    for s in src.values():
        by_type[s.get("type", "?")] = by_type.get(s.get("type", "?"), 0) + 1
        by_q[str(s.get("quality", "?")).split(" (")[0]] = by_q.get(str(s.get("quality", "?")).split(" (")[0], 0) + 1
    unex = [k for k, v in src.items() if v.get("quality") == "unextractable"]
    rev = [k for k, v in src.items() if (v.get("revision") or 1) > 1]
    lines = [f"## CORPUS STATS (from {rel(os.path.join(CORPUS_DIR, 'index.json'))}, built {idx.get('built_at')}) - TOOL-DERIVED, treat as the denominator of your Sources table",
             f"- sources: {len(src)} ({', '.join(f'{k} {v}' for k, v in sorted(by_type.items()))})",
             f"- extraction quality: {', '.join(f'{k} {v}' for k, v in sorted(by_q.items()))}",
             f"- citable anchors in total: {sum(int(v.get('units') or 0) for v in src.values())}",
             f"- no text at all: {', '.join(unex) or 'none'}" + (" (listed in unextractable.md; citable only as `visual, unverified`)" if unex else ""),
             f"- revised since first indexing: {', '.join(rev) or 'none'}" + (" (the earlier text is kept as SRC-nnn@<rev>.md; cite the CURRENT revision)" if rev else ""),
             "", "Your Sources table has ONE ROW PER ID above - none left out, none added. A source you consider irrelevant to the requirements gets a row that says why.",
             "", "| source | title | type | anchors | text | file |", "|---|---|---|---|---|---|"]
    for sid, s in sorted(src.items()):
        lines.append(f"| {sid} | {s.get('title', '')} | {s.get('type', '')} | {s.get('units', 0)} | {s.get('quality', '')} | {s.get('path', '')} |")
    return "\n".join(lines)


def extra(role, scope, cfg, rnd):
    text = os.path.join(rel(CORPUS_DIR), "text")
    grep = GREP_BLOCK.format(text=text, cli=CLI)
    if role == "analyst":
        # the epic's own facts are already in the CONTEXT (state/scopes.json meta); add only what is not there
        return {"rows": status_rows() + [catalogue_row(cfg)], "blocks": [sources_block(scope), grep]}
    if role == "inventory":
        return {"rows": status_rows() + [("CORPUS TEXT", f"{rel(os.path.join(CORPUS_DIR, 'text'))}/SRC-nnn.md"), catalogue_row(cfg),
                                         ("CORPUS REBUILD", f"{CLI} corpus index (orchestrator only - never re-index yourself)")],
                "blocks": [corpus_stats_block(), grep]}
    if role == "consolidator" and cfg.get("split") == "none":   # profile lean: the consolidator writes the rows from the corpus
        ana = load_json("analysis/inventory/source_inventory.json", {})
        return {"rows": [catalogue_row(cfg)] + status_rows() + corpus_rows(), "blocks": [grep] + [sources_block(e.get("name")).replace("## YOUR SOURCES", f"## EPIC {e.get('name')} - ITS SOURCES", 1) for e in ana.get("epics", []) or [] if e.get("activation", "active") == "active"]}
    if role == "consolidator":
        return {"rows": [catalogue_row(cfg)] + status_rows(), "blocks": []}
    if role == "critic-client":
        return {"rows": corpus_rows(), "blocks": [grep,
                "## WHAT YOU ARE CHECKING\nOne question decides every score: does the cited passage say this? Open the locator of every requirement row a claim covers, read the passage, and compare it with the requirement text - wording, priority, exclusions, who wants it. A requirement whose locator does not carry it and which is not marked `inferred` is an INVENTED requirement: verdict `false`, not a low score."]}
    if role == "critic-standard":
        return {"rows": [catalogue_row(cfg)], "blocks": [
                "## WHAT YOU ARE CHECKING\nYou judge the SET against the reference catalogue and requirements best practice: which catalogue capability has no requirement and no explicit out-of-scope row, which requirement is untestable, which one is a solution rather than a capability, which classification (functional / technical / non-functional) is wrong, which non-functional requirement carries no measurable target. You do NOT judge whether a client document says something - you have no corpus access, and a conclusion of yours about the client's material carries no weight."]}
    if role == "researcher":
        return {"rows": [catalogue_row(cfg)], "blocks": []}
    return {}


def digest_extra(which, scopes, cfg):
    """Per-epic counts, the integration candidates for the FR<->TR cross-check and the catalogue pointer for the SET consolidator."""
    if which != "SET": return []
    ana = load_json("analysis/inventory/source_inventory.json", {})
    epics = {e.get("name"): e for e in ana.get("epics", []) or []}
    if cfg.get("split") == "none":   # profile lean: no epic analyses - the rows are written from the sources below
        lines = ["## Epics to write (inventory - the expected count is the inventory's estimate; reconcile what you write with it)", "",
                 "| epic | kind | activation | expected | sources |", "|---|---|---|---|---|"]
        lines += [f"| {n} | {e.get('kind', '?')} | {e.get('activation', '?')} | {e.get('estimated_requirements', '?')} | {', '.join(e.get('sources') or []) or '-'} |" for n, e in sorted(epics.items())]
        return lines + ["", "FR<->TR cross-check candidates: none yet - scan your own functional rows for system boundaries (" + ", ".join(INTEGRATION_HINTS[:10]) + ", ...).", "", "## Catalogue for the gap check", "", catalogue_row(cfg)[1]]
    lines = ["## Requirement counts per epic (from the epic analyses - reconcile with the inventory's estimate)", "",
             "| epic | kind | expected | delivered | functional | technical | nfr | inferred | must | contradictions | open questions |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in sorted(scopes):
        d = scopes[name]; rs = d.get("requirements", []) or []; e = epics.get(name, {})
        def n(pred): return sum(1 for r in rs if pred(r))
        lines.append(f"| {name} | {e.get('kind', '?')} | {e.get('estimated_requirements', '?')} | {len(rs)} | "
                     f"{n(lambda r: r.get('type') == 'functional')} | {n(lambda r: r.get('type') == 'technical')} | {n(lambda r: r.get('type') == 'nfr')} | "
                     f"{n(lambda r: [x.lower() for x in (r.get('source_locators') or [])] == ['inferred'])} | {n(lambda r: r.get('priority') == 'must')} | "
                     f"{len(d.get('contradictions', []) or [])} | {sum(1 for q in (d.get('open_questions', []) or []) if q.get('status') == 'open')} |")
    empty = [n for n in sorted(scopes) if not (scopes[n].get("requirements") or [])]
    missing = [n for n in sorted(epics) if n not in scopes and epics[n].get("activation") == "active"]
    lines += ["", f"Epics with NO requirement row: {', '.join(empty) or 'none'}. Active epics with no analysis at all: {', '.join(missing) or 'none'} (say so in the set rather than filling the gap)."]
    cand = []
    for name in sorted(scopes):
        for r in scopes[name].get("requirements", []) or []:
            if r.get("type") != "functional": continue
            blob = (r.get("title", "") + " " + r.get("description", "")).lower()
            hits = sorted({h for h in INTEGRATION_HINTS if h in blob})
            if hits: cand.append((r.get("req_id"), name, r.get("title", "")[:60], ", ".join(hits)))
    lines += ["", f"## FR<->TR cross-check candidates ({len(cand)} functional requirements mention a system boundary)", "",
              "A keyword scan, not a verdict: every row here needs a Crosscheck row (has-tr with the TR id, or missing-tr), and a functional requirement NOT listed here can still cross a boundary - read the set.", "",
              "| requirement | epic | title | boundary signals |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in cand]
    lines += ["", f"## Catalogue for the gap check", "", catalogue_row(cfg)[1]]
    return lines
