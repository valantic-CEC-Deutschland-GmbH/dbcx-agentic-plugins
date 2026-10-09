"""Brief extras of the ea-landscape method (called by `dbcx render`).

analyst      the inventory row of the system under analysis, the data objects that name it, and the client documents
             that mention it (SRC ids with title, type and extraction quality) plus the grep hint into corpus/text/
inventory    the whole corpus with extraction quality and the unextractable list
critic-client the corpus index and the locator check command
consolidator FLOWS: interface and mastership counts per system; TARGET: a pointer to the passed as-is picture (FLOWS.json)
             profile lean (split none): no system analyses - the consolidator gets the corpus rows and, per system, the documents
             that mention it; the interfaces are derived from the corpus, the mastership CONFLICT seeding stays from the inventory
interface_pairs(scopes) pairs the interface rows of the system analyses by the systems they connect - the digest's "described from both
sides" list and the conflict detector (conflicts.py) share it.
Every extra also carries the REFERENCE ARCHITECTURE row when a reference-architecture knowledge pack is set for the run.
"""
import os, json, sys

from common import RUN, CORPUS_DIR, load_json, read_json, CLI

GREP = f'grep -rn "<term>" corpus/text/ | head -40      or      {CLI} corpus grep "<regex>"'


def _index():
    return read_json(os.path.join(CORPUS_DIR, "index.json"), {"sources": {}})


def _inventory():
    return load_json("analysis/inventory/landscape_inventory.json", {"systems": [], "data_objects": [], "sources": [], "strategic_vision": []})


def _src_ids(values):
    """SRC ids out of a list of locators ('SRC-003#Sheet1!R4' -> 'SRC-003')."""
    out = []
    for v in values or []:
        for tok in str(v).replace(",", " ").split():
            tok = tok.strip("`;,()")
            if tok.upper().startswith("SRC-"):
                sid = tok.split("#")[0].split("@")[0].upper()
                if sid not in out:
                    out.append(sid)
    return out


def _source_line(sid, idx):
    e = idx["sources"].get(sid)
    if not e:
        return f"- {sid}: NOT in corpus/index.json - re-run `{CLI} corpus index` or correct the locator"
    q = e.get("quality", "?")
    warn = "  <-- no usable text: cite only as `visual, unverified` and raise a client question" if q in ("unextractable", "none") or str(q).startswith("none") else ""
    return f"- {sid} `{e.get('title', '')}` [{e.get('type', '')}, {e.get('units', '?')} units, text {q}] -> corpus/text/{sid}.md{warn}"


def _ref_arch_rows(cfg):
    pk = (cfg.get("_packs") or {}).get("reference_architecture")
    if not pk:
        return []
    fp = os.path.join(pk["_dir"], "reference-architecture.md")
    return [("REFERENCE ARCHITECTURE", f"{pk.get('display', pk.get('name'))} - capability map, system types, data objects, SSOT placements and integration styles: {fp}")]


def _unextractable_block():
    fp = os.path.join(CORPUS_DIR, "unextractable.md")
    if not os.path.exists(fp):
        return ""
    lines = [l.strip() for l in open(fp, encoding="utf-8") if l.strip().startswith("- ")]
    if not lines:
        return ""
    return ("## SOURCES WITHOUT A TEXT LAYER (corpus/unextractable.md)\n"
            "A statement resting on one of these carries the exact phrase `visual, unverified`, confidence low, and a client question with the effect of its answer.\n\n"
            + "\n".join(lines[:30]) + (f"\n- ... {len(lines) - 30} more in corpus/unextractable.md" if len(lines) > 30 else ""))


def _systems_block(inv, idx, title):
    """profile lean: every system of the inventory with the documents that mention it - the consolidator's evidence base"""
    lines = [title, f"Search with:\n`{GREP}`", ""]
    for sy in inv.get("systems", []):
        lines += [f"- **{sy.get('name')}** ({sy.get('category', '')}, {sy.get('lifecycle', '')}, {sy.get('relevance', '')}) - interfaces mentioned: {sy.get('interfaces_mentioned', '?')} (upper bound), receives data from: {', '.join(sy.get('depends_on') or []) or '-'}"]
        lines += ["  " + _source_line(x, idx) for x in _src_ids(sy.get("sources", []))]
    return "\n".join(lines if inv.get("systems") else lines + ["- (the inventory records no system)"])


def extra(role, scope, cfg, rnd):
    r = _extra(role, scope, cfg, rnd)
    if role != "consolidator" or cfg.get("split") != "none": return r
    idx = _index(); un = _unextractable_block()   # profile lean: the consolidator reads the corpus itself
    blocks = r["blocks"] + [_systems_block(_inventory(), idx, "## THE SYSTEMS AND THE DOCUMENTS THAT MENTION THEM (no system analyses in this run - " + ("derive every interface from these texts" if scope == "FLOWS" else "read the constraints, contract terms, end-of-life dates and pain points here") + ")")]
    return {"rows": r["rows"] + [("CORPUS", f"{len(idx['sources'])} documents in corpus/index.json - your evidence base in this run"), ("CORPUS GREP", GREP), ("LOCATOR CHECK", f'{CLI} evidence resolve "<locator>"')], "blocks": blocks + ([un] if un else [])}


def _extra(role, scope, cfg, rnd):
    idx = _index()
    rows = list(_ref_arch_rows(cfg))
    if role == "analyst":
        inv = _inventory()
        me = next((s for s in inv.get("systems", []) if s.get("name") == scope), {})
        rows += [("CATEGORY (inventory)", me.get("category", "")), ("VENDOR / PRODUCT (inventory)", me.get("vendor_product", "")),
                 ("LIFECYCLE (inventory)", me.get("lifecycle", "")), ("DEPTH OF EXAMINATION", me.get("relevance", "")),
                 ("RECEIVES DATA FROM (inventory)", me.get("depends_on", [])), ("INTERFACES MENTIONED (inventory, upper bound)", me.get("interfaces_mentioned", ""))]
        prof = ["## YOUR {} IN THE INVENTORY (verified facts - cite them, extend them, never re-measure them; a correction is reported as `handover correction: C-D1-nnn`)".format(cfg.get("system", {}).get("noun", "SYSTEM").upper())]
        if me:
            for k in ("name", "category", "vendor_product", "version", "owner", "hosting", "lifecycle", "relevance", "description"):
                prof.append(f"- {k}: {me.get(k) or '(not stated by any document - a client question, never a guess)'}")
            prof.append(f"- sources: {'; '.join(me.get('sources', [])) or '(none)'}")
        else:
            prof.append(f"- (the inventory has no row named `{scope}` - tell the orchestrator before you write anything; `to = inventory`)")
        objs = [o for o in _inventory().get("data_objects", []) if scope in (o.get("claimed_master_systems") or []) or scope in (o.get("consumer_systems") or [])]
        if objs:
            prof += ["", "### Data objects the inventory connects to your system (fill one Data ownership row for each)"]
            prof += [f"- {o['name']}: claimed as master by {', '.join(o.get('claimed_master_systems') or ['-'])}; read by {', '.join(o.get('consumer_systems') or ['-'])}"
                     + ("   <-- MASTERSHIP CONFLICT: name the document behind each claim, do not decide it" if len(o.get("claimed_master_systems") or []) > 1 else "")
                     for o in objs]
        ids = _src_ids(me.get("sources", [])) or list(idx["sources"])
        docs = ["## THE CLIENT DOCUMENTS THAT MENTION YOUR SYSTEM (your evidence base)",
                f"Cite as SRC-nnn#anchor; the anchors are the HTML comments in corpus/text/SRC-nnn.md. Search with:\n`{GREP}`", ""]
        docs += [_source_line(s, idx) for s in ids]
        docs += ["", f"The inventory names these as your system's sources. The corpus holds {len(idx['sources'])} documents in total (`{CLI} corpus list`); a document that mentions your system but is not listed above is a finding - name it in your Summary and cite it."]
        blocks = ["\n".join(prof), "\n".join(docs)]
        un = _unextractable_block()
        if un:
            blocks.append(un)
        return {"rows": rows, "blocks": blocks}
    if role == "inventory":
        rows += [("CORPUS", f"{len(idx['sources'])} documents in corpus/index.json"), ("CORPUS GREP", GREP)]
        lst = ["## THE CORPUS - every client document with its extraction quality",
               "One row of your Sources table per document below. `date` is the date the document itself carries, `origin` is who wrote it for which purpose - both decide how much weight it carries.", ""]
        lst += [_source_line(s, idx) for s in sorted(idx["sources"])] or ["- (corpus/index.json is empty - run `dbcx corpus index` first)"]
        blocks = ["\n".join(lst)]
        un = _unextractable_block()
        if un:
            blocks.append(un)
        return {"rows": rows, "blocks": blocks}
    if role == "critic-client":
        rows += [("CORPUS INDEX", f"corpus/index.json ({len(idx['sources'])} documents) - the same documents the analysis had"),
                 ("LOCATOR CHECK", f'{CLI} evidence resolve "<locator>"   (a locator that does not resolve makes the claim unverifiable)'),
                 ("CORPUS GREP", GREP)]
        return {"rows": rows, "blocks": []}
    if role == "consolidator":
        if scope == "TARGET":
            fl = load_json("analysis/consolidated/FLOWS.json", None)
            rows += [("AS-IS PICTURE (passed)", "analysis/consolidated/FLOWS.json + analysis/consolidated/FLOWS.md" + ("" if fl else "  <-- MISSING: the FLOWS consolidation has to pass before an option may be written"))]
            if fl:
                ss = fl.get("ssot_matrix", [])
                conflict = [s["data_object"] for s in ss if s.get("verdict") == "conflict"]
                unknown = [s["data_object"] for s in ss if s.get("verdict") == "unknown"]
                blk = ["## THE AS-IS PICTURE YOU BUILD ON (analysis/consolidated/FLOWS.json - passed, cite its claim ids)",
                       f"- flows: {len(fl.get('flows', []))} (ids F-nnn - `flows_changed` of an option references these ids)",
                       f"- data objects with one master: {sum(1 for s in ss if s.get('verdict') == 'single-master')}",
                       f"- data objects with a mastership conflict: {len(conflict)}{(' - ' + ', '.join(conflict)) if conflict else ''}",
                       f"- data objects without a documented master: {len(unknown)}{(' - ' + ', '.join(unknown)) if unknown else ''}",
                       f"- integration findings: {len(fl.get('integration_debt', []))}",
                       "", "Every option that moves a master names the object from this matrix; an object in `conflict` or `unknown` may be re-mastered only together with the client question that settles it."]
                rows_txt = "\n".join(blk)
            else:
                rows_txt = "## THE AS-IS PICTURE YOU BUILD ON\nanalysis/consolidated/FLOWS.json does not exist yet - stop and tell the orchestrator; a target architecture without a passed as-is picture is a guess."
            inv = _inventory()
            vis = ["## THE STRATEGIC STATEMENTS THE OPTIONS MUST SERVE (from the inventory, with their locators)", ""]
            vis += [f"- {v.get('topic')}: {v.get('statement')}  [{'; '.join(v.get('source_locators') or [])}]" for v in inv.get("strategic_vision", [])] or ["- (the inventory records no strategic statement - an option cannot be justified; raise it with the orchestrator)"]
            return {"rows": rows, "blocks": [rows_txt, "\n".join(vis)]}
        if scope == "FLOWS":
            inv = _inventory()
            claims = [o for o in inv.get("data_objects", []) if len(o.get("claimed_master_systems") or []) > 1]
            blk = ["## MASTERSHIP CLAIMS THE INVENTORY ALREADY RECORDS (one SSOT matrix row per data object below)", ""]
            blk += [f"- {o['name']}: claimed by {', '.join(o.get('claimed_master_systems') or [])}" + ("   <-- CONFLICT" if len(o.get("claimed_master_systems") or []) > 1 else "") for o in inv.get("data_objects", [])] or ["- (the inventory records no data object)"]
            blk += ["", f"{len(claims)} of {len(inv.get('data_objects', []))} data objects carry more than one claim. Every one of them gets verdict `conflict`, a recommendation and a client question - never a verdict you invented in between."]
            return {"rows": rows, "blocks": ["\n".join(blk)]}
    return {"rows": rows, "blocks": []}


def interface_pairs(scopes):
    """{(system, system) sorted: [(scope, interface row), ...]} - every interface row of every system analysis keyed by the system pair it
    connects (the digest's "described from both sides" list and the conflict detector, conflicts.py)"""
    pairs = {}
    for name, d in sorted(scopes.items()):
        for i in d.get("interfaces", []) or []:
            pairs.setdefault(tuple(sorted([name, i.get("counterpart", "?")])), []).append((name, i))
    return pairs


def digest_extra(which, scopes, cfg):
    """Appended to `dbcx render digest <which>`: what the consolidator would otherwise have to count itself."""
    lines = []
    if cfg.get("split") == "none":   # profile lean: no system analyses - the inventory seeds, the corpus answers
        inv = _inventory(); objs = inv.get("data_objects", [])
        if which == "FLOWS":
            lines += ["## Interface candidates per system (inventory - an upper bound; the flows come from the documents)", ""]
            lines += [f"- {sy.get('name')}: {sy.get('interfaces_mentioned', '?')} interfaces mentioned, receives data from {', '.join(sy.get('depends_on') or []) or '-'}, sources {', '.join(_src_ids(sy.get('sources', []))) or '-'}" for sy in inv.get("systems", [])]
            conflict = [o["name"] for o in objs if len(o.get("claimed_master_systems") or []) > 1]
            lines += ["", f"## Mastership claims with more than one master ({len(conflict)} of {len(objs)} data objects) - verdict `conflict` each", ""] + [f"- {n}" for n in conflict]
        if which == "TARGET":
            lines += ["## Systems by lifecycle (inventory)", ""] + [f"- {sy.get('name')}: {sy.get('lifecycle', '?')}" for sy in inv.get("systems", [])]
            lines += ["", "## Pain points, constraints and custom capabilities", "", "- no system analyses in this run: read them in the documents that mention each system (brief block THE SYSTEMS AND THE DOCUMENTS THAT MENTION THEM) and cite them with their locators and quotes"]
        return lines
    if which == "FLOWS":
        lines += ["## Interface and ownership rows per system (from the system analyses)", ""]
        for name, d in sorted(scopes.items()):
            ifs = d.get("interfaces", []) or []
            own = d.get("data_ownership", []) or []
            low = sum(1 for i in ifs if i.get("confidence") == "low")
            master = [o["data_object"] for o in own if o.get("role") == "master"]
            lines.append(f"- {name}: {len(ifs)} interfaces ({low} resting on a picture only), masters {', '.join(master) or '-'}, "
                         f"{sum(1 for o in own if o.get('role') == 'copy')} copies")
        both = {k: [f"{n} says {i.get('direction')}/{i.get('protocol_style')}" for n, i in v] for k, v in interface_pairs(scopes).items() if len({n for n, _ in v}) > 1}   # two different scopes, as the detector pairs them - two rows of ONE side are no pair
        lines += ["", f"## Interface ends described from both sides ({len(both)}) - merge each pair into ONE flow and report the disagreement", ""]
        lines += [f"- {k[0]} <-> {k[1]}: " + " | ".join(v) for k, v in sorted(both.items())] or ["- (none - every interface is described from one side only; say so in your Integration debt findings)"]
    if which == "TARGET":
        lines += ["## Pain points and constraints that frame the options", ""]
        for name, d in sorted(scopes.items()):
            pp = d.get("pain_points", []) or []
            cs = d.get("constraints", []) or []
            block = sum(1 for p in pp if p.get("impact") == "blocker")
            eol = [c for c in cs if c.get("kind") == "end-of-life"]
            lines.append(f"- {name}: {len(pp)} pain points ({block} blocking), {len(cs)} constraints"
                         + (f", end of life: {'; '.join(c.get('constraint', '') + ' (' + (c.get('until') or 'no date') + ')' for c in eol)}" if eol else ""))
        lines += ["", "## Capabilities built for this client (a replacement has to rebuild these)", ""]
        for name, d in sorted(scopes.items()):
            cust = [c["capability"] for c in (d.get("capabilities", []) or []) if c.get("provided_by") == "custom"]
            if cust:
                lines.append(f"- {name}: {', '.join(cust)}")
    return lines
