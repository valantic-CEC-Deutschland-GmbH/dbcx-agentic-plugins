"""Settings hook of tech-fit-estimation: `common.project` calls effective(cfg) on the merged configuration layers; validate.check_config
(`dbcx build_excel --check`) adds scale_errors(cfg).

The size scale:
  estimation.sizes        the labels, smallest first (default 0 XS S M L XL XXL). A run's list replaces the method's. Numeric labels in
                          canonical form ("0.25", "8": decimal point, no leading or trailing zeros); a number given as JSON (0.25) becomes that text.
  estimation.tshirt_map   {label: person days}. A dict merges with the method default, so the default labels the run's scale does not list
                          are dropped here (a key the run adds itself stays - scale_errors refuses a key that is no label); kept in scale order
                          (the Parameter sheet's table).
  estimation.size_status  {label: rebuild | rework}: the colour of the size columns. Default labels outside the scale are dropped like above;
                          without an entry for a label of the scale: the largest label rebuild, the second largest rework.
  estimation.size_term    {lang: word}: the scale's name in the workbook texts and option headers ("T-shirt"; a person-day scale: "PD" / "PT").
  estimation.size_column  {lang: header}: the size column of the system and position sheets; follows size_term for a language whose
                          size_term the run changed and whose size_column it did not.
"""
from common import canon_number

STATUS = ("rebuild", "rework")
FORBIDDEN = (",", "|", '"')   # a comma splits the workbook's dropdown list, a pipe the analysis table cell, a quote the dropdown formula


def label(x):
    """a JSON number as a size label in canonical form, anything else unchanged"""
    return canon_number(str(x)) if isinstance(x, (int, float)) and not isinstance(x, bool) else x


def effective(cfg):
    est = cfg.get("estimation")
    if not isinstance(est, dict) or not isinstance(est.get("sizes"), list): return
    base = (((cfg.get("_method") or {}).get("defaults") or {}).get("estimation")) or {}
    sizes = est["sizes"] = [label(x) for x in est["sizes"]]
    def own(d, dflt): return {k: v for k, v in (d or {}).items() if k in sizes or k not in (dflt or {})}   # inherited default labels outside the scale go
    m = own(est.get("tshirt_map"), base.get("tshirt_map"))
    est["tshirt_map"] = {**{k: m[k] for k in sizes if k in m}, **{k: v for k, v in m.items() if k not in sizes}}
    st = own(est.get("size_status"), base.get("size_status"))
    if len(sizes) >= 2 and not any(k in sizes for k in st): st = {**st, sizes[-1]: "rebuild", sizes[-2]: "rework"}
    est["size_status"] = st
    term, col, bt, bc = (est.get("size_term") or {}), (est.get("size_column") or {}), (base.get("size_term") or {}), (base.get("size_column") or {})
    if isinstance(term, dict) and isinstance(col, dict):
        est["size_column"] = {**col, **{l: t for l, t in term.items() if t != bt.get(l) and col.get(l) == bc.get(l)}}


def scale_errors(cfg):
    """the --check rules of the size scale"""
    est = cfg.get("estimation") or {}; sizes = est.get("sizes"); m = est.get("tshirt_map") or {}; err = []
    if "sizes" not in est: return []   # a bare configuration (no method defaults)
    if not isinstance(sizes, list) or len(sizes) < 2: return ["estimation.sizes lists at least two size labels, smallest first"]
    for x in sizes:
        if not isinstance(x, str) or not x.strip() or x != x.strip(): err.append(f"estimation.sizes: {x!r} is no label (a text without surrounding blanks)")
        elif canon_number(x) != x: err.append(f"estimation.sizes: '{x}' is a number in another form - write '{canon_number(x)}' (decimal point, no leading or trailing zeros)")
        elif any(c in x for c in FORBIDDEN): err.append(f"estimation.sizes: '{x}' contains one of {' '.join(FORBIDDEN)} (a decimal label is written with a point)")
    dup = sorted({str(x) for x in sizes if sizes.count(x) > 1})
    if dup: err.append(f"estimation.sizes: label(s) {', '.join(dup)} listed twice")
    miss = [str(x) for x in sizes if x not in m]; extra = [k for k in m if k not in sizes]
    if miss: err.append(f"estimation.tshirt_map: no person days for label(s) {', '.join(miss)} of estimation.sizes")
    if extra: err.append(f"estimation.tshirt_map: key(s) {', '.join(extra)} are no label of estimation.sizes ({', '.join(map(str, sizes))})")
    pds = [(x, m[x]) for x in sizes if x in m]
    bad = [x for x, v in pds if not isinstance(v, (int, float)) or isinstance(v, bool)]
    if bad: err.append(f"estimation.tshirt_map: the person days of {', '.join(bad)} are no number")
    else:
        for (a, va), (b, vb) in zip(pds, pds[1:]):
            if vb <= va: err.append(f"estimation.tshirt_map: person days ascend with the scale - {b} ({vb:g}) is not above {a} ({va:g})")
        lim = est.get("sprint_limit_pd")
        if pds and isinstance(lim, (int, float)) and not isinstance(lim, bool) and lim > pds[-1][1]:
            err.append(f"estimation.sprint_limit_pd {lim:g} lies above the largest size {pds[-1][0]} ({pds[-1][1]:g} PD) - a requirement between them could neither be sized nor cut into positions")
    for k, v in (est.get("size_status") or {}).items():
        if k not in sizes: err.append(f"estimation.size_status: '{k}' is no label of estimation.sizes")
        if v not in STATUS: err.append(f"estimation.size_status.{k}: '{v}' is no status ({' | '.join(STATUS)})")
    return err
