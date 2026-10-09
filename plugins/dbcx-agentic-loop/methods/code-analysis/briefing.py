"""Brief extras of the code-analysis method (called by dbcx render): scanner facts, counting rule and deprecation hits for a unit analyst,
scan inputs for the inventory analyst, and digest extras for the D4 consolidator."""
import os, json, sys
from common import RUN, load_json, knowledge, CLI

def scanner_rule(cfg):
    try:
        K = knowledge(); b = K.get("loc_buckets", {}); skip = K.get("skip_dirs", [])
        return (f"scanner LOC = NON-BLANK lines INCLUDING comments, counted over a FILESYSTEM WALK (not `git ls-files`) of the unit folder, skipping dirs {sorted(skip)}; "
                f"only files with these extensions count (bucket): {', '.join(f'{k}={v}' for k, v in sorted(b.items()))}; files/lines outside these buckets are NOT counted; "
                f"`metrics_tracked` (if present) repeats the count over git-tracked files only. Any figure you publish states its predicate (files in/out) and its line convention; use `{CLI} count <unit> [--tracked]` and quote its RULE line.")
    except Exception as e: return f"(scanner rule unavailable: {e})"

def deprecation_rows(name, cap=40):
    inv = load_json("analysis/inventory/inventory.json", {"units": {}, "deprecation_hits": []})
    hits = [h for h in inv.get("deprecation_hits", []) if h.get("unit") == name]
    if not hits: return f"(the scanner recorded NO deprecation hits for {name} - say so explicitly, do not write 'nothing to triage' without this line)"
    by = {}
    for h in hits: by.setdefault(h["id"], []).append(h)
    lines = [f"{len(hits)} scanner hits for {name} by id: " + ", ".join(f"{k} x{len(v)}" for k, v in sorted(by.items())) + ". Triage EVERY id (a scanner hit on a definition, an unused import or a commented line is a false-positive with a reason; a hit in untracked build output is noted as such). Raw counts are an upper bound, never an effort figure."]
    if any("path_class" in h for h in hits):
        src = sum(1 for h in hits if h.get("path_class") == "src")
        lines.append(f"{src} of {len(hits)} files are `src` (candidate runtime findings); hits marked NOT-SRC sit in config/comment/lib/report/generated/test paths and are no finding unless you show a runtime path. " + (inv.get("deprecation_rule") or ""))
    for h in sorted(hits, key=lambda h: h.get("path_class", "src") != "src")[:cap]:
        pc = h.get("path_class"); ll = h.get("line_list") or []
        lines.append(f"- {h['id']} {h['file']}:{h['line']}" + (f" [{h['kind']}]" if h.get("kind") else "") + (f" [{pc}]" if pc == "src" else f" [NOT-SRC: {pc}]" if pc else "")
                     + (f" lines {', '.join(map(str, ll))}{' ...' if h.get('lines', 0) > len(ll) else ''}" if len(ll) > 1 else "") + f" `{(h.get('snippet') or '')[:90]}`")
    if len(hits) > cap: lines.append(f"- ... {len(hits) - cap} more in analysis/inventory/deprecation_hits_per_unit.md")
    return "\n".join(lines)

def triggered_recipes(name):
    """A3d (WP E): the source pack's check recipes whose trigger the scanner saw in this unit (inventory units.<u>.triggers), with the
    triggering locators - None when nothing triggered, so untriggered recipes never reach a brief."""
    inv = load_json("analysis/inventory/inventory.json", {"units": {}}); trig = (inv["units"].get(name) or {}).get("triggers") or {}
    try: recipes = {r["id"]: r for r in knowledge().get("check_recipes", []) if isinstance(r, dict) and r.get("id")}
    except Exception: return None
    rows = [f"- **{recipes[i].get('title', i)}**: {recipes[i]['text']}\n  trigger: {'; '.join(ev[:3])}" for i, ev in trig.items() if i in recipes and ev]
    return ("## CHECK RECIPES (triggered by the scanner in your unit - apply each one; the trigger is a hypothesis, not a finding)\n" + "\n".join(rows)) if rows else None

def extra(role, scope, cfg, rnd):
    if role == "analyst":
        inv = load_json("analysis/inventory/inventory.json", {"units": {}}); u = inv["units"].get(scope, {})
        m, T = u.get("metrics", {}), lambda d: sum((d or {}).get(k, 0) for k in ("code", "templates", "js", "ts"))
        size = (f"{u['loc_maintained']} maintained LOC code+templates+js+ts (excluded: generated {T(u.get('metrics_generated'))}, vendor-template copy {T(u.get('metrics_template_copy'))}"
                + (f" of {u['template']['template']}" if (u.get("template") or {}).get("template") not in (None, "yempty") else "") + f"; raw code {m.get('code', 0)} / templates {m.get('templates', 0)})"
                if "loc_maintained" in u else f"code {m.get('code', 0)} / templates {m.get('templates', 0)} LOC")
        rows = [("PATH", u.get("path")), ("CATEGORY (scan)", u.get("primary_category")), ("SIZE (scan)", size)]
        return {"rows": rows, "blocks": ["## COUNTING RULE\nSCANNER: " + scanner_rule(cfg), "## DEPRECATION HITS (scanner, your unit)\n" + deprecation_rows(scope)] + [b for b in [triggered_recipes(scope)] if b]}
    if role == "inventory":
        return {"rows": [("SCAN", "analysis/inventory/inventory.json, analysis/inventory/deprecation_hits_per_unit.md, analysis/inventory/scan_log.txt, state/derived_knowledge.json"), ("KNOWLEDGE", f"merged view: {CLI} knowledge show")],
                "blocks": ["## COUNTING RULE\nSCANNER: " + scanner_rule(cfg), "Fill the `activation` column for EVERY unit (active | dead | stub) and back each dead/stub verdict with a claim - `" + CLI + " discover` + `" + CLI + " plan_waves` read it to decide light passes and skips."]}
    return {}

def digest_extra(which, scopes, cfg):
    if which != "D4": return []
    inv = load_json("analysis/inventory/inventory.json", {"units": {}}); lines = ["## Content component types (scanner, per unit)", ""]
    lines += [f"- {u}: {', '.join(inv['units'][u].get('content_custom_component_types', []))}" for u in scopes if inv["units"].get(u, {}).get("content_custom_component_types")]
    lines += ["", "## Deprecations reported by the units (compare with analysis/inventory/deprecation_hits_per_unit.md)", ""] + [f"- {u}: {len(d.get('deprecations', []))} rows triaged" + (" - EMPTY table, check the per-unit hit table" if not d.get("deprecations") else "") for u, d in scopes.items()]
    return lines
