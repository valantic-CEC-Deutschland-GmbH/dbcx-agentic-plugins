"""Standard critics per system option technology - the
engine hook methods/<m>/critics.py, read by common.project (the critic ids), common.scope_critics, extract_claims (the claim routing),
render (the critic's pack and the analyst's notes). System mode only (run.json `systems`); every function returns None without it, so
a run without `systems` keeps the engine rule (run.json options: one `standard-<pack>` per pack when there are several).

Critic id of a system option: `standard-<pack>` for a technology pack (shared by every option on that pack, as in scenario mode); a `_generic`
option has no product knowledge in its pack and run.json has no vendor domains per system (the vendor-docs base is one union), so it gets
the critic of its SYSTEM, `standard-<system>` (one product expert per system; two `_generic` options of one system share it like two
options of one pack). In system mode the standard side is always these ids (also when there is only one).

  standard_critics(cfg)                 {critic id: {pack, label, options: [<system>:<option>]}} in declared order
  scope_critics(scope, critics, cfg)    an analyst chunk: the critics that are no standard critic + the chunk's system option critic;
                                        a triage chunk (TRIAGE / TRIAGE-n): + the critics of the agent-estimated systems its Impacts rows name
                                        (all of them before the file is converted); an architect batch (ARCHITECT-n):
                                        + the critics of the agent-estimated systems its decisions name as receiving end (`to`; all of them
                                        before the file is converted); any other scope: None (unchanged)
  claim_critics(claim, scope, critics, cfg)   an analyst chunk: every critic of the scope; a triage claim: the non-standard critics + the
                                        critics of the systems its target refs name (`triage/impacts#<row>@<system>`); a claim that names only
                                        `none` or systems estimated outside the agents is scored by the client side alone; an architect claim
                                        (`architect/decisions#<row>@<from>@<to>`): the non-standard critics + the critics of the RECEIVING
                                        system <to> (overrule / reduce-to-standard: the reporting system); a landscape system or a system
                                        estimated outside the agents has none - the client side alone; other scopes: None
  scope_pack(scope, cfg)                the pack of an analyst chunk's system option (its technology notes in the analyst brief)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tfe_model as TM

GENERIC = "_generic"


def _model(cfg):
    if not TM.system_mode(cfg or {}): return None
    m, err, _ = TM.parse_systems(cfg)
    return None if err else m


def critic_of(system, option):
    """the standard critic id of one system option"""
    pk = option.get("pack") or ""
    return f"standard-{pk}" if pk and pk != GENERIC else f"standard-{system['id']}"


def standard_critics(cfg):
    m = _model(cfg)
    if not m: return None
    out = {}
    for s in m["systems"]:
        if s.get("estimated_by") != "agents": continue
        for o in s.get("options") or []:
            cid = critic_of(s, o); pk = o.get("pack") or GENERIC
            x = out.setdefault(cid, {"pack": pk, "label": "", "options": [], "systems": []}); x["options"].append(TM.option_key(s["id"], o["id"]))
            if s["label"] not in x["systems"]: x["systems"].append(s["label"])
    for x in out.values(): x["label"] = f"{', '.join(x['systems'])} - {', '.join(x['options'])}"
    return out or None


def _std(c): return str(c) == "standard" or str(c).startswith("standard-")


def _systems_critics(m, sids):
    by = {s["id"]: s for s in m["systems"]}
    return list(dict.fromkeys(critic_of(by[s], o) for s in sids if s in by and by[s].get("estimated_by") == "agents" for o in by[s].get("options") or []))


def _triage(scope):
    return bool(re.fullmatch(re.escape(TM.TRIAGE_SCOPE) + r"(?:-\d+)?", str(scope or "")))


ARCH_SCOPE, ARCH_DIR = "ARCHITECT", os.path.join("analysis", "architect")   # = gaps.ARCH_SCOPE / ARCH_DIR


def _architect(scope):
    return bool(re.fullmatch(ARCH_SCOPE + r"-\d+", str(scope or "")))


def _receivers(claim):
    """the receiving systems of an architect claim: the last @-segment of every `architect/decisions#<row>@<from>@<to>` ref of its target"""
    out = []
    for part in [x for x in re.split(r"\s*;\s*", claim.get("target") or "") if x]:
        refs = part.split("#", 1)[1] if "#" in part else ""
        out += [r.strip().split("@")[-1] for r in refs.split(",") if r.count("@") >= 2]
    return out


def scope_critics(scope, critics, cfg):
    m = _model(cfg)
    if not m: return None
    e = TM.chunk_entry(cfg, scope)
    if e:
        s = next((x for x in m["systems"] if x["id"] == e["system"]), None); o = next((x for x in (s or {}).get("options") or [] if x["id"] == e["option"]), None)
        mine = critic_of(s, o) if s and o else None
        return [c for c in critics if not _std(c) or c == mine]
    if _triage(scope):
        d = TM.load(cfg.get("_run_dir"), os.path.join(TM.TRIAGE_DIR, f"{scope}.json"), None)
        if d is None: return None
        named = _systems_critics(m, [str(x.get("system") or "").strip() for x in d.get("impacts") or []])
        return [c for c in critics if not _std(c) or c in named]
    if _architect(scope):
        d = TM.load(cfg.get("_run_dir"), os.path.join(ARCH_DIR, f"{scope}.json"), None)
        if d is None: return None
        named = _systems_critics(m, [str(x.get("to") or "").strip() for x in d.get("decisions") or []])
        return [c for c in critics if not _std(c) or c in named]
    return None


def claim_critics(claim, scope, critics, cfg):
    m = _model(cfg)
    if not m: return None
    if TM.chunk_entry(cfg, scope): return list(critics)
    if _architect(scope):
        named = _systems_critics(m, _receivers(claim))
        return [c for c in critics if not _std(c) or c in named]
    if not _triage(scope): return None
    sids = []
    for part in [x for x in re.split(r"\s*;\s*", claim.get("target") or "") if x]:
        refs = part.split("#", 1)[1] if "#" in part else ""
        sids += [r.strip().split("@", 1)[1] for r in refs.split(",") if "@" in r]
    named = _systems_critics(m, sids)
    return [c for c in critics if not _std(c) or c in named]


def scope_pack(scope, cfg):
    e = TM.chunk_entry(cfg, scope) if _model(cfg) else None
    return (e or {}).get("pack") or None
