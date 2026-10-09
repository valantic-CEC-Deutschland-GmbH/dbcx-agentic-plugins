"""Adapter template: platform-specific discovery and signals for tools/scan_inventory.py.

Copy to platforms/<pack>/adapter.py (or <project>/overrides/adapter.py for a one-off), implement every function.
The generic engine (scan_inventory.py) does the walking, LOC counting per bucket, deprecation/integration regexes,
entry-point regexes and dependency edges. The adapter supplies what only the platform knows.
Every returned record MUST carry an 'evidence' path (repo-relative) so the analyst can verify it.
"""

# file name that marks a unit root (None = use project.json unit.manifest_file)
UNIT_MANIFEST = None

def discover_units(roots, ctx):
    """Return [{'name', 'path', 'manifest', 'description', 'meta': {}}] for every custom unit below the roots.
    ctx = {'project', 'knowledge', 'rel': fn(path)->repo-relative, 'walk': fn(root)->(dirpath, dirs, files)}.
    TODO: parse the manifest (extensioninfo.xml / composer.json / module.xml / plugin.json ...)."""
    raise NotImplementedError("TODO: implement discover_units")

def parse_dependencies(unit, ctx):
    """Return the list of unit names this unit declares as dependencies (custom, standard or unknown alike).
    TODO: requires-extension / composer require / module.xml sequence / plugin dependencies."""
    raise NotImplementedError("TODO: implement parse_dependencies")

def is_standard_unit(name, ctx):
    """True if the name is a vendor/standard unit, False if custom, None if unknown (engine falls back to knowledge.json lists)."""
    return None

def unit_signals(unit, files, ctx):
    """Platform-specific counts for the unit. files = [(abs_path, rel_path, ext)] of all files in the unit.
    Return a dict with any of (missing keys default to 0/[]):
      schema_new_types, schema_extended_types, schema_attributes_on_extended_types, schema_relations, schema_enums,
      di_definitions, override_candidates (list of {'what','how','evidence'}), workflows (list of names),
      content_custom_component_types (list), third_party_required (list), loaded_in (list of config files that load the unit),
      has_plugin_dir (bool), categories_hint (list of category tokens), extra (dict),
      activation_resolved ({'state', 'evidence'}), triggers ({check-recipe id: [evidence]} for recipes whose trigger only the platform can see),
      template_diff ({'template', 'counts', 'loc', 'rule', 'copies': set of absolute paths of unchanged vendor-template copies} -> template_copy bucket)
    ctx also carries 'roots' (the scan roots) and may be used to cache platform resolutions across units.
    TODO: parse items.xml / transfer.xml / db_schema.xml / entity definitions, DI xml/yaml, process definitions."""
    return {}

def classify(unit, signals, metrics, ctx):
    """Return the ordered list of category tokens (first = primary) from config/project.json unit.categories.
    TODO: rules such as 'has web module + templates -> frontend', 'api controllers -> api', 'integration signals -> integration'."""
    return ["other"]

def platform_facts(roots, ctx):
    """Return {'version_hints': {file: [hints]}, 'config_files': {file: {...}}, 'standard_code_in_repo': bool|None, 'notes': [str]}.
    TODO: build.number / composer.lock vendor versions / manifest.json / config.php version markers."""
    return {"version_hints": {}, "config_files": {}, "standard_code_in_repo": None, "notes": []}

def resolve_overrides(unit, candidates, ctx):
    """Optional (0.8). Return the override candidates (scanner + adapter) with 'target' and 'resolution' added - e.g. overrides-standard /
    new-id / target-not-loaded / not-decidable - resolved against the standard definitions and the ACTIVE standard units; drop duplicates.
    The scanner counts them into override_candidates_resolved; the list stays a candidate list."""
    return candidates

def unit_activation(unit, ctx):
    """Optional (0.8). Return {'loaded_in': [...], 'activation_resolved': {'state', 'evidence'}} for one unit, or None."""
    return None

def derive_knowledge(roots, ctx):
    """Optional. Return knowledge lists derived from the vendor code shipped with THIS repository, e.g.
    {'standard_units': [...], 'target_content_component_types': [...], 'third_party_packages': [...]}.
    Written to state/derived_knowledge.json and unioned into the merged knowledge. Never hand-maintain what can be derived."""
    return {}
