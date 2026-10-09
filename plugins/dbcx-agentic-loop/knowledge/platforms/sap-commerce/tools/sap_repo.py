"""Shared, read-only helpers for the sap-commerce pack tools (active_extensions, effective_property, template_diff) and the adapter:
repository layout (on-premise or CCv2 wrapper), manifest.json, localextensions.xml, extensioninfo.xml, Java properties files.
Nothing here writes, builds or starts anything."""
import json, os, re

SKIP = {".git", "node_modules", "classes", "gensrc", "testclasses", "eclipsebin", "target", "build", "dist", ".idea"}
STD_PARTS = ("platform", "modules")   # below hybris/bin; plus every ext-* folder

def _subdirs(d):
    try: return sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)) and not x.startswith("."))
    except OSError: return []

def strip_xml_comments(txt):
    """Blank out <!-- ... --> but keep every newline, so line numbers stay true."""
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), txt, flags=re.S)

def line_of(txt, pos): return txt.count("\n", 0, pos) + 1

def read_text(path):
    with open(path, encoding="utf-8", errors="ignore") as f: return f.read()

def attr(tag, name):
    m = re.search(r"\b" + name + r"\s*=\s*(['\"])(.*?)\1", tag, re.S); return m.group(2) if m else None

def layout(root):
    """Locate hybris/, manifest.json and the active localextensions.xml below root (repository root, or up to two levels below it)."""
    root = os.path.abspath(root); cands = [root]; level = [root]
    for _ in range(2):
        level = [os.path.join(d, s) for d in level for s in _subdirs(d) if s not in SKIP]; cands += level
    core = next((c for c in cands if os.path.isdir(os.path.join(c, "hybris", "bin"))), None)
    man_path = man = None
    for c in ([core] if core else []) + cands:
        p = os.path.join(c, "manifest.json")
        if os.path.isfile(p):
            try: m = json.loads(read_text(p))
            except Exception: continue
            if isinstance(m, dict) and "commerceSuiteVersion" in m: man_path, man = p, m; break
    base = os.path.dirname(man_path) if man_path else core
    loc, src = None, None
    ue = ((man or {}).get("useConfig") or {}).get("extensions") or {}
    if man and ue.get("location"):
        loc = os.path.join(base, ue["location"].lstrip("/")); src = "manifest.json useConfig.extensions.location"
    elif core and os.path.isfile(os.path.join(core, "hybris", "config", "localextensions.xml")):
        loc = os.path.join(core, "hybris", "config", "localextensions.xml"); src = "hybris/config/localextensions.xml"
    hb = os.path.join(core, "hybris") if core else None
    return {"root": root, "core": core, "hybris": hb, "bin": os.path.join(hb, "bin") if hb else None, "manifest": man_path, "manifest_json": man or {},
            "manifest_base": base, "localextensions": loc if loc and os.path.isfile(loc) else None, "localextensions_declared": loc, "localextensions_source": src,
            "platform_in_repo": bool(hb and os.path.isfile(os.path.join(hb, "bin", "platform", "build.number")))}

def is_standard_dir(bin_dir, d):
    rp = os.path.relpath(d, bin_dir).replace(os.sep, "/").split("/")
    return bool(rp) and (rp[0] in STD_PARTS or rp[0].startswith("ext-"))

def read_extensioninfo(path):
    """{name, classprefix, requires: [(name, line)], meta} of one extensioninfo.xml (comments ignored, either quote style)."""
    txt = strip_xml_comments(read_text(path))
    m = re.search(r"<extension\b[^>]*>", txt, re.S); tag = m.group(0) if m else ""
    req = [(attr(r.group(0), "name"), line_of(txt, r.start())) for r in re.finditer(r"<requires-extension\b[^>]*>", txt, re.S) if attr(r.group(0), "name")]
    return {"name": attr(tag, "name") or os.path.basename(os.path.dirname(path)), "classprefix": attr(tag, "classprefix") or "", "requires": req,
            "webmodule": "<webmodule" in txt, "usemaven": (attr(tag, "usemaven") or "").lower() == "true"}

def extensions_in_tree(bin_dir):
    """Every extension below hybris/bin: {name: {dir, manifest, standard, classprefix, requires}} (an extension folder is not descended)."""
    out = {}
    if not bin_dir or not os.path.isdir(bin_dir): return out
    for dp, dns, fns in os.walk(bin_dir):
        if "extensioninfo.xml" in fns:
            info = read_extensioninfo(os.path.join(dp, "extensioninfo.xml"))
            out.setdefault(info["name"], dict(info, dir=dp, manifest=os.path.join(dp, "extensioninfo.xml"), standard=is_standard_dir(bin_dir, dp)))
            dns[:] = []; continue
        dns[:] = [d for d in dns if d not in SKIP and not d.startswith(".")]
    return out

def read_localextensions(path, hybris_dir):
    """{extensions: [(name|None, dir|None, line)], paths: [(dir, autoload, line)], platform_autoload, commented: [(name, line)]}."""
    raw = read_text(path); txt = strip_xml_comments(raw)
    exts = [(attr(m.group(0), "name"), attr(m.group(0), "dir"), line_of(txt, m.start())) for m in re.finditer(r"<extension\b[^>]*>", txt, re.S)]
    paths = []
    for m in re.finditer(r"<path\b[^>]*>", txt, re.S):
        d = (attr(m.group(0), "dir") or "").replace("${HYBRIS_BIN_DIR}", os.path.join(hybris_dir or "", "bin")).replace("${HYBRIS_CONFIG_DIR}", os.path.join(hybris_dir or "", "config"))
        paths.append((d, (attr(m.group(0), "autoload") or "false").lower() == "true", line_of(txt, m.start())))
    em = re.search(r"<extensions\b[^>]*>", txt, re.S)
    commented = [(c.group(2), line_of(raw, m.start() + c.start())) for m in re.finditer(r"<!--.*?-->", raw, re.S)
                 for c in re.finditer(r"extension\s+name\s*=\s*(['\"])([^'\"]+)\1", m.group(0))]
    return {"extensions": exts, "paths": paths, "platform_autoload": (attr(em.group(0), "autoload") or "true").lower() != "false" if em else True, "commented": commented}

def json_line(path, needle):
    """1-based line of the first occurrence of needle in a JSON file (for locators), else None."""
    try:
        for n, l in enumerate(read_text(path).splitlines(), 1):
            if needle in l: return n
    except OSError: pass
    return None

def read_properties(path):
    """Java properties -> [(key, value, line)] in file order (continuation lines, ':'/'=' /whitespace separators, '#'/'!' comments)."""
    out = []
    try: lines = read_text(path).splitlines()
    except OSError: return out
    i = 0
    while i < len(lines):
        start = i; ln = lines[i].lstrip(); i += 1
        if not ln or ln[0] in "#!": continue
        while ln.endswith("\\") and not ln.endswith("\\\\") and i < len(lines): ln = ln[:-1] + lines[i].lstrip(); i += 1
        m = re.match(r"((?:\\.|[^=:\s])+)\s*[=:\s]\s*(.*)$", ln) or re.match(r"((?:\\.|[^=:\s])+)()$", ln)
        if m: out.append((re.sub(r"\\(.)", r"\1", m.group(1)), m.group(2).strip(), start + 1))
    return out

SECRET_KEY = re.compile(r"(?i)(password|passwd|pwd|secret|api[._-]?key|apikey|token|credential|private[._-]?key|client[._-]?secret)")
PLACEHOLDER = re.compile(r"^\s*$|^<[^>]*>$|^(changeme|change_me|tbd|todo|xxx+|\*+|dummy|placeholder|secret|password|n/?a|none|null)$|maintained in|set (in|via|by) ", re.I)

def value_form(key, value):
    """Masked description of a value for secret-like keys (never print the value itself): placeholder / macro / literal of N chars."""
    if not SECRET_KEY.search(key or ""): return None
    v = value or ""
    if PLACEHOLDER.search(v): return f"placeholder ({len(v)} chars)"
    if "${" in v or v.startswith("$"): return f"macro/reference ({len(v)} chars) - resolve before judging"
    return f"literal ({len(v)} chars) - check whether it is a real credential"
