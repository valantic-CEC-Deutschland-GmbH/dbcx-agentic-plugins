"""Conflict detector of the ea-landscape method (called by `dbcx conflicts detect`).

interface   an interface described from both ends (briefing.interface_pairs - the digest's "described from both sides" pairing) whose two
            ends disagree on direction, style (protocol_style; `unknown` is no statement), frequency (one text containing the other
            agrees) or data objects; ends are matched by their data objects, a single row per side pairs with the other side's single row
mastership  a data object with more than one claimed master: the inventory's claimed_master_systems plus every `master` row of the
            system analyses' Data ownership tables. A side's scope is the claimed system when it has an analysis, else the inventory
The framing of subject and sides (field names, "claimed master" ...) comes from the method labels `_cf_*` of the run's deliverable language
(they reach the client question of `dbcx conflicts undecidable`), direction and style tokens through the method's value labels; ids,
systems, free-text values, frequencies and locators stay verbatim.
"""
import os, re, importlib.util

_spec = importlib.util.spec_from_file_location("dbcx_method_briefing", os.path.join(os.path.dirname(os.path.abspath(__file__)), "briefing.py"))
briefing = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(briefing)   # by path: the engine has a module named conflicts too
interface_pairs, _inventory = briefing.interface_pairs, briefing._inventory


def _cite(d, key):
    """the claim of an analysis that carries a row: target naming the key first, else a statement / evidence mentioning it"""
    cl = d.get("claims", []) or []; k = str(key).lower()
    return next((c["id"] for c in cl if k in (c.get("target") or "").lower()), None) or next((c["id"] for c in cl if k in (c["statement"] + " " + " ".join(c.get("evidence", []))).lower()), "")


def _norm(v): return re.sub(r"[^0-9a-zäöüß]+", " ", str(v or "").lower()).strip()
def _objs(i): return {_norm(x) for x in i.get("data_objects") or [] if _norm(x)}
def _flow(scope, i):
    c = i.get("counterpart", "?"); d = i.get("direction")
    return {(scope, c), (c, scope)} if d == "bidirectional" else {(c, scope)} if d == "in" else {(scope, c)}


def _disagree(sa, ia, sb, ib, L):
    """{field label: (value of a, value of b)} for the fields two ends of one interface state differently"""
    out = {}
    if _flow(sa, ia) != _flow(sb, ib): out[L["_cf_direction"]] = tuple(f"{L.get(x.get('direction'), x.get('direction'))} ({', '.join(f'{f} -> {t}' for f, t in sorted(_flow(s, x)))})" for s, x in ((sa, ia), (sb, ib)))
    st = [x.get("protocol_style") for x in (ia, ib)]
    if all(v and v != "unknown" for v in st) and st[0] != st[1]: out[L["_cf_style"]] = tuple(L.get(v, v) for v in st)   # tokens through the value labels (eingehend, API)
    fq = [_norm(x.get("frequency")) for x in (ia, ib)]
    if all(fq) and fq[0] not in fq[1] and fq[1] not in fq[0]: out[L["_cf_frequency"]] = (ia.get("frequency"), ib.get("frequency"))
    if _objs(ia) and _objs(ib) and _objs(ia) != _objs(ib): out[L["_cf_data_objects"]] = ("; ".join(ia.get("data_objects") or []), "; ".join(ib.get("data_objects") or []))
    return out


def _interfaces(scopes, L):
    out = []
    for (a, b), rows in sorted(interface_pairs(scopes).items()):
        ra = [i for n, i in rows if n == a]; rb = [i for n, i in rows if n == b]
        if not ra or not rb: continue   # one side only: no second statement to disagree with
        used = set()
        for ia in ra:
            best = max(((len(_objs(ia) & _objs(ib)), j) for j, ib in enumerate(rb) if j not in used), default=(0, None))
            j = best[1] if best[0] else (0 if len(ra) == len(rb) == 1 else None)
            if j is None: continue
            used.add(j); ib = rb[j]; dis = _disagree(a, ia, b, ib, L)
            if not dis: continue
            def val(k, i): return f"{i.get('id', '?')}: " + "; ".join(f"{f} {v[k]}" for f, v in dis.items()) + f" [{'; '.join(i.get('source_locators') or []) or '-'}]"
            out.append({"id": f"interface:{a}|{b}|{ia.get('id')}|{ib.get('id')}", "kind": "interface", "subject": f"{a} <-> {b} ({ia.get('id')} / {ib.get('id')}; {', '.join(dis)})",
                        "sides": [{"scope": a, "claim": _cite(scopes[a], ia.get("id")), "value": val(0, ia)}, {"scope": b, "claim": _cite(scopes[b], ib.get("id")), "value": val(1, ib)}]})
    return out


def _mastership(scopes, cfg, L):
    inv = _inventory(); inv_scope = ((cfg.get("_method") or {}).get("inventory") or {}).get("scope", "D1")
    from common import scope_info, load_json
    invd = load_json(scope_info(inv_scope)[0], {}) if inv_scope else {}
    claims = {}   # object -> {system: [(scope, claim, value)]}
    names = {}
    for o in inv.get("data_objects", []):
        names.setdefault(_norm(o["name"]), o["name"])
        for s in o.get("claimed_master_systems") or []:
            claims.setdefault(_norm(o["name"]), {}).setdefault(s, []).append((inv_scope, _cite(invd, o["name"]), L["_cf_master_inventory"].format(src="; ".join(o.get("sources") or []) or "-")))
    for name, d in sorted(scopes.items()):
        for r in d.get("data_ownership", []) or []:
            if r.get("role") != "master": continue
            names.setdefault(_norm(r["data_object"]), r["data_object"])
            claims.setdefault(_norm(r["data_object"]), {}).setdefault(name, []).append((name, _cite(d, r["data_object"]), L["_cf_master_analysis"].format(src="; ".join(r.get("source_locators") or []) or "-")))
    out = []
    for k, per in sorted(claims.items()):
        if len(per) < 2: continue
        sides = []
        for sy, ev in per.items():
            own = [e for e in ev if e[0] == sy]; scope = sy if sy in scopes else inv_scope
            sides.append({"scope": scope, "claim": (own or ev)[0][1], "value": L["_cf_is_master"].format(system=sy) + " - " + "; ".join(e[2] for e in own + [e for e in ev if e not in own])})
        out.append({"id": f"mastership:{k}", "kind": "mastership", "subject": f"{names[k]} ({L['_cf_claimed_master'].format(systems=', '.join(per))})", "sides": sides})
    return out


def detect(scopes, cfg):
    from common import labels
    L = labels(); return _interfaces(scopes, L) + _mastership(scopes, cfg, L)
