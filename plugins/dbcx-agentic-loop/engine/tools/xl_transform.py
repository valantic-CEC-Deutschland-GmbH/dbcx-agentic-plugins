"""Evidence / text transform, Grundlage derivation and assumption numbering for build_excel.
Pure functions over plain data - no run context is imported, so they can be exercised directly.

Tokens (both editions; result sheets never show process ids):
  C-<scope>-NNN        -> that claim's own evidence (evidence columns) / removed (free text); unknown ids dropped with a warning
  PS-7-NNN             -> [Q<int>]  (collected for the Quellen sheet)
  Q-...                -> A-nn (client-directed question) | "Angabe <client>" (answered by the client) | dropped (any other role)
  input/..xlsx!S!A8    -> "<client workbook label>" with sheet and row
  state/ work/ analysis/ tools/ docs/ reference/ overrides/ *.py   -> dropped (internal locators)
  anything else (repository locators, URLs, SRC-nnn)             -> kept verbatim
"""
import re

CLAIM = r"C-[A-Za-z0-9_.]+(?:-[A-Za-z0-9_.]+)*-\d{2,4}"
CLAIM_RE = re.compile(rf"\b{CLAIM}(?:/\d{{2,4}})*\b")   # C-D4-027/059 = shorthand for two claims
CLAIM_LIST_RE = re.compile(rf"\s*\(\s*{CLAIM}(?:/\d{{2,4}})*(?:\s*(?:[,;/&]|\bund\b|\band\b|\bsowie\b)\s*{CLAIM}(?:/\d{{2,4}})*)*\s*\)")
PS_RE = re.compile(r"\bPS-7-(\d+)\b")
Q_RE = re.compile(r"\bQ-[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*\b")
CELL_RE = re.compile(r"(?:@project/)?input/[^;!\n]*?\.xls[xm]?!([^!;\n]+)!\$?([A-Z]{1,3})\$?(\d+)")
INTERNAL_RE = re.compile(r"^(?:\./)?(?:state|work|analysis|tools|docs|reference|overrides|templates)/|^[^/\s]+\.py(?::\d+(?:-\d+)?)?$")   # bare *.py = our tools; repo paths carry a folder
QN_RE = re.compile(r"\[Q(\d+)\]")
A_RE = re.compile(r"\bA-(\d{2,})\b")
URL_RE = re.compile(r"^[a-z]+://", re.I)
FILE_RE = re.compile(r"[\w-]\.[A-Za-z][A-Za-z0-9]{0,7}(?::\d+(?:-\d+)?)?$")


def split_entries(value):
    """Evidence cell value -> list of entries (lists stay lists; strings split on ';' and new lines)."""
    if value in (None, ""): return []
    if isinstance(value, (list, tuple)): out = []; [out.extend(split_entries(v)) for v in value]; return out
    return [x.strip() for x in re.split(r"[;\n]", str(value)) if x.strip()]


def tidy(s):
    """Punctuation left behind by removed tokens: '( ; x)', '(x, )', '()', doubled separators and spaces."""
    for _ in range(3):
        s = re.sub(r"\(\s*[,;/]+\s*", "(", s); s = re.sub(r"\s*[,;/]+\s*\)", ")", s); s = re.sub(r"\s*\(\s*\)", "", s)
        s = re.sub(r"([,;])\s*[,;]+", r"\1", s); s = re.sub(r"[ \t]{2,}", " ", s); s = re.sub(r"\s+([,;.:])", r"\1", s)
        s = re.sub(r"\s+\b(?:und|and|sowie|oder|or)\b(?=\s+(?:und|and|sowie|oder|or)\b|\s*(?:[,.;:)]|$))", "", s)   # conjunction left alone by a removed id
    return s.strip().strip(";,").strip()


class Transformer:
    """One per workbook: collects the cited [Qn] numbers, the A-nn ids and warnings while it transforms."""

    def __init__(self, claims=None, qmap=None, cell_label=None, client_fact="", handover=None, code_locators=True, client_a=()):
        self.claims = claims or {}          # claim id -> evidence entries
        self.code_locators = code_locators  # False (deliverable `code_locators: false`): repository and vendor-code locators never reach a cell
        self.handover = handover            # opt-in: HO-<type>#<id> -> [repository locators the artefact carries] | None (stays a client statement)
        self.qmap = qmap or {}              # question id -> ("A", "A-03") | ("client", None) | ("drop", None)
        self.cell_label = cell_label or (lambda sheet, row, path: f"{sheet}, {row}")
        self.client_fact = client_fact
        # bare A-nn of a client-answered question (no Annahmen row) -> "<client_fact> (A-nn)"; alone in parentheses "(<client_fact> A-nn, A-mm)";
        # a citation that already carries the label stays
        self.client_a = set(client_a); cf = re.escape(client_fact); ids = r"A-\d{2,}(?:\s*,\s*A-\d{2,})*"
        self.client_a_re = re.compile(rf"{cf} \(?{ids}\)?|\(\s*({ids})\s*\)|\bA-\d{{2,}}\b") if client_a and client_fact else None
        self.cited_q = set(); self.cited_a = set(); self.unknown_claims = set(); self.unknown_q = set()
        self.prefixes = {c.rsplit("-", 1)[0] for c in self.claims}   # a C-x-NN whose scope never made claims is a row id, not a claim
        self.customer_cfg = None; self.open_refs = []   # set_customer(): the customer edition's locator rewrite; open_refs = what it could not resolve

    def is_claim(self, t):   # loaded claim, a loaded claim scope, or the canonical C-<scope>-NNN shape
        t = t.split("/")[0]; return t in self.claims or t.rsplit("-", 1)[0] in self.prefixes or bool(re.fullmatch(r"C-.+-\d{3}", t))

    @staticmethod
    def expand(t):
        """'C-D4-027/059' -> ['C-D4-027', 'C-D4-059']."""
        head, *more = t.split("/"); base = head.rsplit("-", 1)[0]; return [head] + [f"{base}-{n}" for n in more]

    def _drop_claims(self, s):
        s = CLAIM_LIST_RE.sub(lambda m: "" if all(self.is_claim(x) for x in CLAIM_RE.findall(m.group(0))) else m.group(0), s)
        return CLAIM_RE.sub(lambda m: "" if self.is_claim(m.group(0)) else m.group(0), s)

    # ---- single tokens
    def _ps(self, m): n = int(m.group(1)); self.cited_q.add(n); return f"[Q{n}]"

    def _q(self, m):
        qid = m.group(0); kind, aid = self.qmap.get(qid, (None, None))
        if kind == "A": self.cited_a.add(aid); return aid
        if kind == "client": return self.client_fact
        if kind is None and not re.search(r"-\d+$", qid): return qid   # 'Q-' prose that is no register id
        if kind is None: self.unknown_q.add(qid)
        return ""

    def _cell(self, m):
        path = m.group(0).split("!")[0]; return self.cell_label(m.group(1).strip(), int(m.group(3)), path)

    def _inline(self, s):
        s = CELL_RE.sub(self._cell, s); s = PS_RE.sub(self._ps, s); s = Q_RE.sub(self._q, s)
        return self.client_a_re.sub(self._client_a, s) if self.client_a_re else s

    def _client_a(self, m):
        t = m.group(0)
        if t.startswith(self.client_fact): return t
        wrap = lambda a: f"{self.client_fact} ({a})" if a in self.client_a else a
        if m.group(1):   # "(A-39, A-55)": all client-answered -> "(<label> A-39, A-55)", else each on its own
            return f"({self.client_fact} {m.group(1)})" if all(a in self.client_a for a in re.findall(r"A-\d+", m.group(1))) else re.sub(r"A-\d+", lambda x: wrap(x.group(0)), t)
        return wrap(t)

    # ---- evidence column: list in, list out (claims expanded to their own locators, recursively)
    def evidence(self, value, _depth=0, _seen=None):
        seen = set() if _seen is None else _seen; out = []
        for e in split_entries(value):
            ids = [x for x in CLAIM_RE.findall(e) if self.is_claim(x)]
            if ids and not self._drop_claims(e).strip(" ,;()/"):   # the entry is only claim ids
                for cid in (x for t in ids for x in self.expand(t)):
                    if cid in seen: continue
                    seen.add(cid)
                    if cid not in self.claims: self.unknown_claims.add(cid); continue
                    if _depth < 5: out += self.evidence(self.claims[cid], _depth + 1, seen)
                continue
            if INTERNAL_RE.search(e): continue
            if self.handover and HO_RE.match(e.strip()):
                locs = self.handover(e.strip())
                if locs: out += locs; continue
            x = self._inline(e)
            if ids: x = self._drop_claims(x)
            x = tidy(x) if x != e else x
            if x and not INTERNAL_RE.search(x) and (self.code_locators or code_free([x])): out.append(x)
        return list(dict.fromkeys(out))

    # ---- free text: parenthetical claim lists removed, ids replaced inline
    def text(self, s):
        if not isinstance(s, str) or not s or s.startswith("="): return s
        if " " not in s.strip() and INTERNAL_RE.search(s.strip()): return ""   # a cell that is only an internal locator
        s0 = s; s = self._drop_claims(self._inline(s))
        return tidy(s) if s != s0 else s

    # ---- customer edition: run-local shorthand a client reader cannot resolve (AS-nn, KB-nnn, HO-<type>#<id>)
    def set_customer(self, as_ids=None, labels=None, ho_types=None):
        """as_ids: (scope, 'AS-02') -> 'A-68' (the register's assumption_id); labels/ho_types: as for basis() (the Grundlage rendering of HO rows)."""
        self.customer_cfg = {"as_ids": as_ids or {}, "labels": labels, "ho_types": ho_types}

    def customer(self, s, scope=None):
        """A cell of the customer edition: HO-<type>#<id> -> the Grundlage rendering ("Code-Analyse · MT-004"; an id that is no id, e.g. a unit
        name, is left out), KB-nnn dropped with its parentheses / list item, AS-nn of a row from `scope` -> "Annahme (A-nn)". What cannot be
        rewritten stays and is collected in open_refs (a text post-pass fixes it; lint_deliverable --standalone fails on it)."""
        if not self.customer_cfg or not isinstance(s, str) or not s or s.startswith("="): return s
        c = self.customer_cfg; s0 = s
        def ho(m):
            typ, rid = m.group(1), m.group(2).rstrip(".,;)")
            if not ID_RE.fullmatch(rid): return "" + m.group(2)[len(rid):]
            return basis([f"HO-{typ}#{rid}"], handover_types=c["ho_types"] or {typ}, labels=c["labels"], refs=True)[0] + m.group(2)[len(rid):]
        s = HO_ANY_RE.sub(ho, s)
        if CA_RE.search(s):   # "code-analysis:<unit>" sources -> the Grundlage label, once per cell
            lab = (c["labels"] or {}).get("basis_handover") or "Code-Analyse"; seen = []
            s = CA_RE.sub(lambda m: "" if seen else (seen.append(1) or lab), s); s = re.sub(r"\n\s*\n", "\n", s)
        s = KB_PAREN_RE.sub("", s); s = KB_TAIL_RE.sub("", s); s = KB_HEAD_RE.sub(r"\1", s)
        def as_id(n): return c["as_ids"].get((scope, n))
        def lst(m):   # "Registrierte Annahmen AS-02 und AS-12" -> "Annahmen (A-68, A-70)", only when every id resolves
            ids = re.findall(r"AS-\d+", m.group(2)); a = [as_id(i) for i in ids]
            return m.group(0) if not all(a) else f"{m.group(1)} ({', '.join(a)})"
        s = AS_LIST_RE.sub(lst, s)
        s = AS_PAREN_RE.sub(lambda m: f"({as_id(m.group(1))})" if as_id(m.group(1)) else m.group(0), s)
        s = AS_RE.sub(lambda m: f"Annahme ({as_id(m.group(0))})" if as_id(m.group(0)) else m.group(0), s)
        self.open_refs += [m.group(0) for m in re.finditer(r"\b(?:AS|KB)-\d+|HO-[\w-]+#\S+", s)]
        return tidy(s) if s != s0 else s


# ---------------------------------------------------------------- Grundlage (§4)
CA_RE = re.compile(r"\bcode-analysis:[\w.-]+")
HO_ANY_RE = re.compile(r"HO-([A-Za-z0-9_-]+)#([^\s;,()]+)")
KB_ID = r"KB-\d+"
KB_PAREN_RE = re.compile(rf"\s*\(\s*{KB_ID}(?:\s*(?:[,;/]|\bund\b|\band\b)\s*{KB_ID})*\s*\)")   # "(KB-016)", "(KB-015, KB-017)"
KB_TAIL_RE = re.compile(rf"(?<=[\w)\]])\s*[;,]\s*{KB_ID}(?=\s*(?:[;,)\].]|$))")   # "...; KB-026"
KB_HEAD_RE = re.compile(rf"((?:^|[(;,])\s*){KB_ID}\s*[;,]\s*")   # "KB-026; ..."
AS_ID = r"AS-\d+"
AS_LIST_RE = re.compile(rf"\b(?:Registrierte[n]? )?(Annahmen?|assumptions?) ({AS_ID}(?:(?:,| und| and| /|/) ?{AS_ID})*)", re.I)
AS_PAREN_RE = re.compile(rf"\((AS-\d+)\)")
AS_RE = re.compile(rf"\b{AS_ID}\b")
HO_RE = re.compile(r"^HO-([A-Za-z0-9_-]+)#(\S+)$")
VENDOR_CODE_RE = re.compile(r"(?<![\w/.-])(?:vendor:\S+|@[\w.-]+/[\w.-]+@\d[\w.+-]*/\S+)")   # vendor standard code: @scope/lib@version/path[:line]
DOC_RE = re.compile(r"^(?:SRC-\d+|HO-[A-Za-z0-9_-]+)(?:#\S*)?(?:\s|$|[,;)])")   # client document / handover locators
CLIENT_PATH_RE = re.compile(r"^(?:@project/)?(?:input|corpus)/")                  # the client's own material, never the repository


def is_client_doc(entry, cell_re=None):
    """A client document: SRC-nnn#anchor, HO-<type>#<id>, a path under input/ or corpus/, or the client-workbook label the
    transform wrote (cell_re) -> information stated by the client ("Angabe <client>")."""
    e = entry.strip()
    return bool(DOC_RE.match(e) or CLIENT_PATH_RE.match(e) or (cell_re and cell_re.search(e)))


def is_repo_locator(entry):
    e = QN_RE.sub("", A_RE.sub("", entry)).strip(" ,;()")
    if not e or URL_RE.match(e) or CLIENT_PATH_RE.match(e) or DOC_RE.match(e): return False
    tok = e.split()[0]
    return ("/" in tok and not URL_RE.match(tok)) or bool(FILE_RE.search(tok))


def is_vendor_code(entry): return bool(VENDOR_CODE_RE.match(entry.strip()))


def code_free(entries):
    """entries without repository and vendor-code locators (a deliverable with `code_locators: false`): reference ids, [Qn], A-nn,
    handover rows, client documents and URLs stay"""
    return [e for e in entries if not is_vendor_code(e) and not (is_repo_locator(e) and not is_client_doc(e))]


def vendor_address(addr):
    """a vendor-code address @scope/lib@version/path:line reads @scope/lib@version (no code location); anything else unchanged"""
    m = re.match(r"^(@[\w.-]+/[\w.-]+@\d[\w.+-]*)/\S+$", str(addr or "").strip())
    return m.group(1) if m else addr


def basis(entries, texts=(), linked=(), labels=None, valid=None, client=False, client_label="", cell_re=None, vendor_q=None, handover_types=None, refs=False, client_a=()):
    """-> (value, kind) with kind in {'handover', 'code', 'vendor', 'vendor_code', 'client', joined by '+', 'assumption', ''}. A registered assumption sets kind 'assumption' (§4); its label is appended to the other parts ("Code-Analyse · F-1 + Annahme (A-76)").
    vendor_q = the [Qn] numbers whose source is vendor standard code (opt-in `vendor_code_basis`): those, and a raw vendor-code
    locator, give `basis_vendor_code` (e.g. "Herstellerstandard") - never "Code"; other [Qn] stay `basis_vendor`.
    handover_types = artefact types whose HO-<type>#<id> rows are an earlier released analysis (opt-in `handover_basis`, e.g. the code
    analysis): they give `basis_handover` ("Code-Analyse") instead of a client statement. refs (opt-in `grundlage_refs`): every label
    carries its readable references - "Code-Analyse · FR-041", "Herstellerstandard [Q3]" (a handover row id that is no id, e.g. a unit
    name, is left out).
    valid = the A-nn ids that exist (an 'A-01' that is a native row id elsewhere is no assumption).
    client = the row rests on a question the client answered (linked via affects), or its evidence / text carries the
    client-statement label the transform wrote for such a question, or it cites a client document (is_client_doc) -> "Angabe <client>"
    (a fact, no assumption)."""
    L = labels or {"basis_code": "Code", "basis_vendor": "Herstellerdokumentation", "basis_assumption": "Annahme ({ids})", "basis_client": "Angabe Kunde"}
    aids = set(linked)
    for x in list(entries) + [t for t in texts if isinstance(t, str)]: aids.update(f"A-{m}" for m in A_RE.findall(x))
    cas = sorted(aids & set(client_a), key=lambda a: int(a[2:]))   # client-answered A-nn: no Annahmen row, a client basis
    if valid is not None: aids &= set(valid)
    alabel = L["basis_assumption"].replace("{ids}", ", ".join(sorted(aids, key=lambda a: int(a[2:])))) if aids else ""
    hts = set(handover_types or ()); hos = [m for m in (HO_RE.match(e.strip()) for e in entries) if m and m.group(1) in hts]
    ho_e = {m.group(0) for m in hos}; rest = [e for e in entries if e.strip() not in ho_e]
    client = client or bool(cas) or bool(client_label and any(client_label in x for x in list(entries) + [t for t in texts if isinstance(t, str)])) or any(is_client_doc(e, cell_re) for e in rest)
    vc = vendor_q is not None; vq = set(vendor_q or ())
    code = any(is_repo_locator(e) for e in rest if not (client_label and client_label in e) and not is_client_doc(e, cell_re) and not (vc and is_vendor_code(e)))
    qv = [int(n) for e in rest for n in QN_RE.findall(e) if int(n) not in vq]; qc = [int(n) for e in rest for n in QN_RE.findall(e) if int(n) in vq]
    vendor = bool(qv); vcode = vc and (bool(qc) or any(is_vendor_code(e) for e in rest))
    def ref(label, ids, sep=" "): return f"{label}{sep}{', '.join(ids)}" if refs and ids else label
    ho_ids = list(dict.fromkeys(m.group(2) for m in hos if ID_RE.fullmatch(m.group(2))))
    parts = ([ref(L.get("basis_handover") or L["basis_code"], ho_ids, " · ")] if hos else []) + ([L["basis_code"]] if code else []) \
        + ([ref(L["basis_vendor"], [f"[Q{n}]" for n in dict.fromkeys(qv)])] if vendor else []) \
        + ([ref(L.get("basis_vendor_code") or L["basis_vendor"], [f"[Q{n}]" for n in dict.fromkeys(qc)])] if vcode else []) + ([f"{L.get('basis_client', '')} ({', '.join(cas)})" if cas else L.get("basis_client", "")] if client else [])
    if alabel: return " + ".join([*dict.fromkeys(parts), alabel]), "assumption"   # the kind stays 'assumption'; the other evidence stays readable
    return " + ".join(dict.fromkeys(parts)), "+".join(k for k, f in (("handover", bool(hos)), ("code", code), ("vendor", vendor), ("vendor_code", vcode), ("client", client)) if f)


# ---------------------------------------------------------------- question register (§5; legacy `answer` and new `answers[]`)
def answers_of(q):
    lst = [a for a in (q.get("answers") or []) if isinstance(a, dict)]
    if not lst and isinstance(q.get("answer"), dict) and q["answer"]: lst = [q["answer"]]
    return lst


def is_client(q): return (q.get("to") or "").strip().lower() == "client"


def client_answered(q): return any((a.get("by") or "").strip().lower() == "client" for a in answers_of(q))


def assumption_numbers(questions):
    """Stable A-nn for every client-directed question: `assumption_id` where the register has one, else numbered by
    register order after the highest assigned one (as `dbcx questions assumptions --assign` does; asked_at has one-second resolution). Client-answered questions keep their number
    (no row) so the others never renumber when the client answers."""
    cq = [q for q in questions if is_client(q)]; ids = {}; used = set()
    for q in cq:
        m = re.fullmatch(r"A-(\d+)", str(q.get("assumption_id") or "").strip())
        if m: ids[q["id"]] = f"A-{int(m.group(1)):02d}"; used.add(int(m.group(1)))
    n = max(used, default=0)
    for q in (q for q in cq if q["id"] not in ids):
        n += 1; ids[q["id"]] = f"A-{n:02d}"
    return ids


def qmap_of(questions):
    """question id -> transform target (see Transformer)."""
    nums = assumption_numbers(questions); out = {}
    for q in questions:
        if not q.get("id"): continue
        out[q["id"]] = (("client", None) if client_answered(q) else ("A", nums[q["id"]])) if is_client(q) else ("drop", None)
    return out


def answer_type(q):
    """Offene_Fragen answer type key: answer_client | answer_decision | answer_assumption | '' (no answer yet)."""
    a = answers_of(q)
    if not a: return ""
    last = a[-1]
    if (last.get("by") or "").lower() == "client" or client_answered(q): return "answer_client"
    t = (last.get("type") or "").lower()
    if t == "client-fact": return "answer_client"
    if t in ("decision", "fact"): return "answer_decision"
    if t in ("working-assumption", "assumption", "proposal"): return "answer_assumption"
    return "answer_decision" if (last.get("weight") or "").lower() == "fact" else "answer_assumption"


def answer_text(q):
    a = answers_of(q)
    if not a: return ""
    last = a[-1]; o = next((x for x in q.get("options", []) if x.get("key") == last.get("option")), None)
    return ((f"{o['key']}) {o['text']}" if o else "") + (" " if o and last.get("text") else "") + (last.get("text") or "")).strip()


ID_RE = re.compile(r"\b[A-Z]{1,5}-\d{1,4}\b")


def affected(q, known_keys=()):
    """Normalised row keys an assumption affects: `affects` entries that are row keys (or id-shaped), else ids found in the
    effect / if_not text (§5 fallback). Deliverable keys (D1..) are kept separately by the caller."""
    known = set(known_keys); out = []
    for a in q.get("affects") or []:
        a = str(a).strip()
        if a and (a in known or ID_RE.fullmatch(a)) and not re.fullmatch(r"D\d+", a): out.append(a)
    if not out:
        txt = " ".join(str(q.get(k) or "") for k in ("effect", "if_not"))
        out = [m for m in ID_RE.findall(txt) if not re.fullmatch(r"(?:D\d+|PS-\d+|A-\d+|Q-\d+|C-\d+)", m)]
        out += [k for k in known if k and not ID_RE.fullmatch(k) and re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", txt)]
    return list(dict.fromkeys(out))


def norm_txt(s): return re.sub(r"[\W_]+", " ", str(s or "")).strip().lower()


def id_only(s):
    """True when a text is just a list of ids / row keys (nothing a reader could act on)."""
    return len(re.sub(r"[\W_\d]+", "", ID_RE.sub("", re.sub(r"\bD\d+\b", "", str(s or ""))))) < 4


def why_text(q):
    """'Warum wir davon ausgehen': the register's `why` - never an id list."""
    w = (q.get("why") or "").strip(); return "" if id_only(w) else w


def if_not_text(q, affected_text=""):
    """'Falls nicht zutreffend': `if_not`; else the effect when it says something `why` and 'Betroffen' do not; else the explicit
    consequences of the non-recommended options; else empty. An id list or a copy of another cell is never used."""
    if (q.get("if_not") or "").strip(): return q["if_not"].strip()
    taken = (norm_txt(q.get("why")), norm_txt(affected_text))
    eff = (q.get("effect") or "").strip()
    if eff and not id_only(eff) and norm_txt(eff) not in taken: return eff
    alt = "; ".join(f"{o.get('key')}) {o['consequence'].strip()}" for o in q.get("options", []) if not o.get("recommended") and (o.get("consequence") or "").strip() and not id_only(o["consequence"]))
    return alt if alt and norm_txt(alt) not in taken else ""


def default_wording(q, template):
    """'Die Analyse geht davon aus: <recommended option text or latest lead answer>.' (flagged by the hygiene lint)."""
    a = answers_of(q); text = ""
    if a:
        last = a[-1]; o = next((x for x in q.get("options", []) if x.get("key") == last.get("option")), None)
        text = (last.get("text") or "").strip() or (o or {}).get("text", "")
    if not text:
        o = next((x for x in q.get("options", []) if x.get("recommended")), None) or next((x for x in q.get("options", []) if x.get("key") == q.get("proceeding_under")), None)
        text = (o or {}).get("text", "") or (q.get("question") or "")
    return template.replace("{text}", text.strip().rstrip("."))
