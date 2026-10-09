"""Run-specific scanner adapter TEMPLATE - copy to <run>/overrides/adapter.py only when the run needs a unit the platform
pack cannot discover (an application without the pack's manifest, a second technology in the same repository ...).
Everything else stays delegated to the pack adapter (a NEW platform adapter starts from methods/code-analysis/tools/adapter_template.py
instead). Never hard-code the package path: the engine that imports this file
already knows its own root (an expanduser literal breaks every scan after the package moves).

Replace <pack> and the extra unit below; keep the delegation lines as they are.
"""
from common import load_pack_adapter   # engine/tools is on sys.path whenever the engine loads this adapter

_pack = load_pack_adapter("<pack>")          # e.g. "sap-commerce"
UNIT_MANIFEST = _pack.UNIT_MANIFEST

def discover_units(roots, ctx):
    units = _pack.discover_units(roots, ctx)
    # units.append({...})                    # the additional unit, with the same fields the pack produces
    return units

def __getattr__(name):                       # every other hook of the pack adapter (derive_knowledge, classify, ...) passes through
    return getattr(_pack, name)
