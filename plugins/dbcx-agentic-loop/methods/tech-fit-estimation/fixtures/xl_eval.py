#!/usr/bin/env python3
"""A small formula evaluator for the smoke test: recomputes the workbook's formulas with openpyxl only (no Excel, no LibreOffice),
so the smoke can edit a parameter cell and prove that every total follows.

Covers the formula language the workbook builder writes: numbers, strings, booleans, cell and range references (A1, $A$1, Sheet!A1,
'Sheet'!$A$2:$A$5000), + - * / & = <> < > <= >=, unary minus, and SUM, SUMIF, SUMIFS, COUNTIF, COUNTIFS, COUNTA, COUNT, INDEX, MATCH (exact),
IF, IFERROR, ROUND, AND, OR, NOT, LEN, LEFT, TEXT (value passthrough). Criteria as Excel: "=x", ">=5", "x" (case-insensitive).

Usage (library): ev = Evaluator(openpyxl.load_workbook(path)); ev.value("Summen", "B5"); ev.set("Parameter", "B12", 3); ev.value(...)
"""
import re
from openpyxl.utils import column_index_from_string, get_column_letter


class XlError(Exception): pass


TOK = re.compile(r"""\s*(?:(?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|(?P<str>"(?:[^"]|"")*")|(?P<ref>(?:(?:'[^']+'|[A-Za-z_][\w.]*)!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)|(?P<fn>[A-Z][A-Z0-9.]*)\s*\(|(?P<bool>TRUE|FALSE)\b|(?P<op><>|<=|>=|[-+*/&=<>(),:%^]))""")


def tokens(s):
    out, i = [], 0
    while i < len(s):
        m = TOK.match(s, i)
        if not m or m.end() == i:
            if s[i:].strip() == "": break
            raise XlError(f"cannot parse {s[i:i + 30]!r}")
        k = m.lastgroup; out.append((k, m.group(k))); i = m.end()
    return out


class Evaluator:
    def __init__(self, wb):
        self.wb = wb; self.cache = {}

    def set(self, sheet, coord, value):
        self.wb[sheet][coord].value = value; self.cache.clear()

    def value(self, sheet, coord):
        key = (sheet, coord)
        if key in self.cache: return self.cache[key]
        v = self.wb[sheet][coord].value
        if isinstance(v, str) and v.startswith("="):
            self.cache[key] = None   # cycle guard
            try: v = Parser(self, tokens(v[1:]), sheet).run()
            except XlError as e: v = e
        self.cache[key] = v
        return v

    def split(self, ref, sheet):
        if "!" in ref: sh, a = ref.rsplit("!", 1); sh = sh.strip("'")
        else: sh, a = sheet, ref
        return sh, a.replace("$", "")

    def rng(self, ref, sheet):
        sh, a = self.split(ref, sheet); ws = self.wb[sh]
        a1, _, a2 = a.partition(":"); a2 = a2 or a1
        m1 = re.match(r"([A-Z]+)(\d+)", a1); m2 = re.match(r"([A-Z]+)(\d+)", a2)
        c1, c2 = column_index_from_string(m1.group(1)), column_index_from_string(m2.group(1)); r1, r2 = int(m1.group(2)), min(int(m2.group(2)), max(ws.max_row, int(m1.group(2))))
        return [[self.value(sh, f"{get_column_letter(c)}{r}") for c in range(c1, c2 + 1)] for r in range(r1, r2 + 1)]


class Parser:
    """one formula (a token list) - precedence: comparison < & < + - < * / < unary < primary; IF / IFERROR evaluate only the taken branch"""
    def __init__(self, ev, toks, sheet): self.ev, self.t, self.i, self.sheet = ev, toks, 0, sheet

    def run(self):
        v = self.cmp()
        if self.i != len(self.t): raise XlError("trailing tokens")
        return v

    def peek(self): return self.t[self.i] if self.i < len(self.t) else (None, None)
    def take(self):
        if self.i >= len(self.t): raise XlError("unexpected end")
        tk = self.t[self.i]; self.i += 1; return tk

    def cmp(self):
        a = self.cat()
        while self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.take()[1]; b = self.cat(); a = compare(a, b, op)
        return a

    def cat(self):
        a = self.add()
        while self.peek()[1] == "&": self.take(); a = text(a) + text(self.add())
        return a

    def add(self):
        a = self.mul()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]; b = self.mul(); a = number(a) + number(b) if op == "+" else number(a) - number(b)
        return a

    def mul(self):
        a = self.unary()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]; b = self.unary()
            if op == "/" and number(b) == 0: raise XlError("#DIV/0!")
            a = number(a) * number(b) if op == "*" else number(a) / number(b)
        return a

    def unary(self):
        if self.peek()[1] == "-": self.take(); return -number(self.unary())
        if self.peek()[1] == "+": self.take(); return number(self.unary())
        return self.primary()

    def primary(self):
        k, v = self.take()
        if k == "num": return float(v)
        if k == "str": return v[1:-1].replace('""', '"')
        if k == "bool": return v == "TRUE"
        if k == "ref": return Range(self.ev.rng(v, self.sheet)) if ":" in v else self.ev.value(*self.ev.split(v, self.sheet))
        if v == "(":
            x = self.cmp(); self.take(); return x
        if k == "fn": return self.call(v)
        raise XlError(f"unexpected {v!r}")

    def spans(self):
        """the raw token lists of the arguments of the call whose '(' was just taken"""
        parts, depth, cur = [], 0, []
        while True:
            tk = self.take()
            if tk[0] == "fn" or tk[1] == "(": depth += 1
            elif tk[1] == ")":
                if depth == 0:
                    if cur or parts: parts.append(cur)
                    return parts
                depth -= 1
            elif tk[1] == "," and depth == 0: parts.append(cur); cur = []; continue
            cur.append(tk)

    def sub(self, toks):
        v = Parser(self.ev, toks, self.sheet).run()
        if isinstance(v, XlError): raise v
        return v

    def call(self, fn):
        parts = self.spans()
        if fn == "IFERROR":
            try: return self.sub(parts[0])
            except XlError: return self.sub(parts[1])
        if fn == "IF":
            return (self.sub(parts[1]) if len(parts) > 1 else True) if truthy(self.sub(parts[0])) else (self.sub(parts[2]) if len(parts) > 2 else False)
        f = FUNCS.get(fn)
        if not f: raise XlError(f"function {fn} not supported")
        return f(*[Parser(self.ev, p, self.sheet).run() for p in parts])


class Range:
    def __init__(self, rows): self.rows = rows
    def flat(self): return [v for r in self.rows for v in r]


def flat(x): return x.flat() if isinstance(x, Range) else [x]
def truthy(v): return bool(v) if not isinstance(v, str) else v.upper() == "TRUE"
def number(v):
    if isinstance(v, XlError): raise v
    if isinstance(v, Range): v = v.flat()[0]
    if v in (None, ""): return 0.0
    if isinstance(v, bool): return float(v)
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace(",", "."))
    except ValueError: raise XlError("#VALUE!")
def text(v):
    if isinstance(v, XlError): raise v
    if v is None: return ""
    if isinstance(v, bool): return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v)
def compare(a, b, op):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool): x, y = float(a), float(b)
    else: x, y = text(a).lower(), text(b).lower()
    return {"=": x == y, "<>": x != y, "<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]


def crit(c):
    """Excel criterion -> predicate"""
    if isinstance(c, (int, float)) and not isinstance(c, bool): return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == float(c)
    s = text(c); m = re.match(r"^(<>|<=|>=|=|<|>)(.*)$", s)
    op, val = (m.group(1), m.group(2)) if m else ("=", s)
    def num_ok(v):
        try: return float(v)
        except (TypeError, ValueError): return None
    def pred(v):
        nv, nc = num_ok(v) if not isinstance(v, str) or v.strip() else None, num_ok(val)
        if op in ("<", ">", "<=", ">=") or (nc is not None and nv is not None and op in ("=", "<>")):
            if nv is None or nc is None: return op == "<>"
            return compare(nv, nc, op)
        return compare(text(v), val, op)
    return pred


def f_sumifs(total, *pairs):
    vals = flat(total); keep = [True] * len(vals)
    for k in range(0, len(pairs), 2):
        r, p = flat(pairs[k]), crit(pairs[k + 1]); keep = [a and p(b) for a, b in zip(keep, r)]
    return sum(float(v) for v, k in zip(vals, keep) if k and isinstance(v, (int, float)) and not isinstance(v, bool))


def f_countifs(*pairs):
    n = len(flat(pairs[0])); keep = [True] * n
    for k in range(0, len(pairs), 2):
        r, p = flat(pairs[k]), crit(pairs[k + 1]); keep = [a and p(b) for a, b in zip(keep, r)]
    return float(sum(keep))


def f_match(v, r, mode=1.0):
    for i, x in enumerate(flat(r), 1):
        if compare(x, v, "="): return float(i)
    raise XlError("#N/A")


def f_index(r, i, j=1.0):
    rows = r.rows if isinstance(r, Range) else [[r]]
    i, j = int(number(i)), int(number(j))
    if len(rows) == 1 and len(rows[0]) > 1 and j == 1: return rows[0][i - 1]
    try: return rows[i - 1][j - 1]
    except IndexError: raise XlError("#REF!")


def nums(a): return [float(v) for x in a for v in flat(x) if isinstance(v, (int, float)) and not isinstance(v, bool)]


FUNCS = {
    "SUM": lambda *a: sum(nums(a)),
    "SUMIF": lambda r, c, s=None: f_sumifs(s if s is not None else r, r, c),
    "SUMIFS": f_sumifs,
    "COUNTIF": lambda r, c: f_countifs(r, c),
    "COUNTIFS": f_countifs,
    "COUNTA": lambda *a: float(sum(1 for x in a for v in flat(x) if v not in (None, ""))),
    "COUNT": lambda *a: float(len(nums(a))),
    "INDEX": f_index, "MATCH": f_match,
    "ROUND": lambda v, d=0.0: round(number(v), int(number(d))),
    "AND": lambda *a: all(truthy(v) for x in a for v in flat(x)), "OR": lambda *a: any(truthy(v) for x in a for v in flat(x)), "NOT": lambda v: not truthy(v),
    "LEN": lambda v: float(len(text(v))), "SUBSTITUTE": lambda v, old, new: text(v).replace(text(old), text(new)), "LEFT": lambda v, n=1.0: text(v)[:int(number(n))], "TEXT": lambda v, f="": v,
    "FIXED": lambda v, d=2.0, nc=False: f"{number(v):{'' if truthy(nc) else ','}.{max(0, int(number(d)))}f}",   # en separators (the evaluator has no locale)
}
