#!/usr/bin/env python3
"""Search backends of the corpus retrieval. No command line; used by retrieval.py.

keyword   BM25 over the anchor blocks of corpus/text/SRC-nnn.md, pure Python, always available. Per-source term counts are cached in
          corpus/search/blocks/<SRC>.json (keyed by the source's sha256, so `corpus index` re-tokenises only new and revised sources);
          the merged inverted index is corpus/search/keyword.json.
semantic  meaning-based search with model2vec + minishlab/potion-multilingual-128M computed LOCALLY. The seam:

            class SemanticBackend:
                name: str                                     # recorded in corpus/PROFILE.json
                def index(self, sid, sha, blocks, store): ... # blocks = [(locator "SRC-nnn#anchor", raw anchor text)] of ONE source;
                                                              # (re)embed it into store (= corpus/search/semantic/); new or revised sources only
                def drop(self, sid, store): ...               # a source left the corpus
                def search(self, query, k, store): ...        # -> [(locator, cosine)] best first, at most k

          semantic_backend() returns Model2Vec when the package is importable AND the model folder MODEL_DIR is complete, else None
          (keyword search alone, silently). The model is fetched once by `dbcx retrieval enable` (fetch_model: the four needed files of
          the pinned revision over HTTPS, sha256-checked, converted to an fp16 copy in MODEL_DIR, the download deleted) and ALWAYS loaded
          from that local folder - model2vec's from_pretrained(<repo id>) would download the whole repository on every load. Index and
          search never open a network connection.
"""
import glob, importlib.util, json, math, os, re, shutil, sys, tempfile, unicodedata

MODELS_DIR = os.path.join(os.path.expanduser(os.environ.get("DBCX_HOME") or "~/.dbcx"), "models")   # same rule as setup.py / common.DBCX_HOME
MODEL_REPO, MODEL_REV = "minishlab/potion-multilingual-128M", "73908c3438cf03b6a01bcb9611d62b23d0726f08"
MODEL_DIR = os.path.join(MODELS_DIR, "potion-multilingual-128M-f16")
MODEL_URL = "https://huggingface.co/" + MODEL_REPO + "/resolve/" + MODEL_REV + "/{}"   # the hub redirects to its CDN (us.aws.cdn.hf.co); HTTPS_PROXY is honoured
MODEL_FILES = {   # the only files the model needs: sha256 and size at MODEL_REV
    "model.safetensors": ("14b5eb39cb4ce5666da8ad1f3dc6be4346e9b2d601c073302fa0a31bf7943397", 512361560),
    "tokenizer.json": ("19f1909063da3cfe3bd83a782381f040dccea475f4816de11116444a73e1b6a1", 18616131),
    "config.json": ("595e4cab2093732efd5dbe084fd5c1826b5eea693b73b4c1fd971672867d2e54", 271),
    "modules.json": ("a68dcbed0429dcdd5bfdca92b0b03cc30d09122c0a3fcf4758787d4b244e45b2", 278)}
DOWNLOAD_MB = round(sum(n for _, n in MODEL_FILES.values()) / 1e6)

def package_ready(): return importlib.util.find_spec("model2vec") is not None
def model_ready(): return all(os.path.isfile(os.path.join(MODEL_DIR, f)) for f in MODEL_FILES)

def semantic_backend():
    """Model2Vec when the package and the local model are there, else None (module docstring)"""
    return Model2Vec() if package_ready() and model_ready() else None

class Model2Vec:
    """unit-normalised fp16 vectors of the raw anchor text per source in <store>/<SRC>.npy + <SRC>.json (locators); cosine search"""
    name = "model2vec:potion-multilingual-128M-f16@" + MODEL_REV[:7]
    def __init__(self): self._m = None; self._mat = None
    def _vec(self, texts):
        import numpy as np
        if self._m is None:
            from model2vec import StaticModel
            self._m = StaticModel.from_pretrained(MODEL_DIR)   # the local folder only, never the repo id (module docstring)
        e = np.asarray(self._m.encode(list(texts)), dtype=np.float32).reshape(len(texts), -1)
        return (e / np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-9)).astype(np.float16)
    def index(self, sid, sha, blocks, store):
        import numpy as np
        os.makedirs(store, exist_ok=True); np.save(os.path.join(store, f"{sid}.npy"), self._vec([t for _, t in blocks]) if blocks else np.zeros((0, 1), np.float16))
        with open(os.path.join(store, f"{sid}.json"), "w", encoding="utf-8") as f: json.dump([loc for loc, _ in blocks], f)
        self._mat = None
    def drop(self, sid, store):
        for x in (".npy", ".json"):
            if os.path.exists(os.path.join(store, sid + x)): os.remove(os.path.join(store, sid + x))
        self._mat = None
    def search(self, query, k, store):
        import numpy as np
        if self._mat is None:   # loaded once per process: several queries of one `corpus search` call share it
            locs, mats = [], []
            for f in sorted(glob.glob(os.path.join(store, "SRC-*.json"))):
                with open(f, encoding="utf-8") as h: ls = json.load(h)
                if ls: locs += ls; mats.append(np.load(f[:-5] + ".npy").astype(np.float32))
            self._mat = (locs, np.concatenate(mats) if mats else None)
        locs, mat = self._mat
        if mat is None: return []
        s = mat @ self._vec([query])[0].astype(np.float32)
        return [(locs[i], float(s[i])) for i in np.argsort(-s)[:k]]

def fetch_model(say=print, urlopen=None, convert=None):
    """download the model's files of the pinned revision over HTTPS, check each sha256, convert to an fp16 copy in MODEL_DIR and delete
    the download (the only network access of the retrieval)"""
    import hashlib, urllib.request
    urlopen = urlopen or urllib.request.urlopen; convert = convert or convert_fp16
    os.makedirs(MODELS_DIR, exist_ok=True); dl = tempfile.mkdtemp(prefix=".download-", dir=MODELS_DIR)
    try:
        for f, (sha, size) in MODEL_FILES.items():
            say(f"step: downloading the search model, {f} ({max(1, round(size / 1e6))} MB)")
            h = hashlib.sha256()
            with urlopen(urllib.request.Request(MODEL_URL.format(f), headers={"User-Agent": "dbcx-agentic-loop"}), timeout=120) as r, open(os.path.join(dl, f), "wb") as out:
                for chunk in iter(lambda: r.read(1 << 20), b""): h.update(chunk); out.write(chunk)
            if h.hexdigest() != sha: raise RuntimeError(f"{f} does not match its checksum (download damaged or changed)")
        say("step: converting the search model to a compact local copy")
        convert(dl, MODEL_DIR)
        if not model_ready(): raise RuntimeError("the converted model folder is incomplete")
    finally: shutil.rmtree(dl, ignore_errors=True)

def convert_fp16(src, dst):
    from model2vec import StaticModel
    tmp = dst + ".part"; shutil.rmtree(tmp, ignore_errors=True)
    StaticModel.from_pretrained(src, quantize_to="float16").save_pretrained(tmp)   # src is a local folder: no hub access
    shutil.rmtree(dst, ignore_errors=True); os.replace(tmp, dst)

# ------------------------------------------------------------------ keyword (BM25)
STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to was were will with not no but if then than
which who what when where how all any can may must should would into out over per via be been being our your their there these those such
der die das den dem des ein eine einer eines einem einen und oder ist sind war wird werden wurde im in am an auf aus bei mit nach von vor zu zum
zur fuer für ueber über unter nicht kein keine auch als wie wenn dann dass daß es er sie wir ihr sich so nur noch schon bis durch gegen ohne um
je pro beim vom ins man hat haben kann können koennen muss müssen soll sollen""".split())
TOKEN = re.compile(r"[^\W_]+", re.U)
FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

def stem(t):
    """light suffix stripping for German and English inflection (plural, case endings) - enough for BM25 to meet 'Rechnungen' and 'Rechnung'"""
    for _ in range(2):   # twice: 'orders' -> 'order' -> 'ord' meets 'order' -> 'ord'
        for suf, rep in (("ungen", "ung"), ("ies", "y"), ("en", ""), ("er", ""), ("es", ""), ("e", ""), ("s", ""), ("n", "")):
            if len(t) - len(suf) >= 4 and t.endswith(suf): t = t[:-len(suf)] + rep; break
        else: break
    return t

def tokens(text):
    out = []
    for w in TOKEN.findall(unicodedata.normalize("NFC", (text or "").lower()).translate(FOLD)):
        if len(w) < 2 or w in STOP: continue
        out.append(stem(w) if not w.isdigit() else w)
    return out

def term_counts(text):
    tf = {}
    for t in tokens(text): tf[t] = tf.get(t, 0) + 1
    return tf

def merge(caches):
    """per-source caches {sid: {"blocks": [[locator, length, {term: tf}], ...]}} -> the inverted index"""
    blocks, postings = [], {}
    for sid in sorted(caches):
        for loc, n, tf in caches[sid]["blocks"]:
            bi = len(blocks); blocks.append([loc, n])
            for t, c in tf.items(): postings.setdefault(t, []).append([bi, c])
    return {"version": 1, "N": len(blocks), "avgdl": (sum(b[1] for b in blocks) / len(blocks)) if blocks else 0.0, "blocks": blocks, "postings": postings}

def bm25(idx, query_weights, k1=1.2, b=0.75, allowed=None):
    """{block index: score} for a weighted query {term: weight}; allowed = set of source ids the result is limited to"""
    N, avg, blocks, out = idx["N"], idx["avgdl"] or 1.0, idx["blocks"], {}
    for t, w in query_weights.items():
        ps = idx["postings"].get(t)
        if not ps: continue
        idf = math.log(1 + (N - len(ps) + 0.5) / (len(ps) + 0.5))
        for bi, c in ps:
            if allowed is not None and blocks[bi][0].split("#", 1)[0] not in allowed: continue
            n = blocks[bi][1]; out[bi] = out.get(bi, 0.0) + w * idf * c * (k1 + 1) / (c + k1 * (1 - b + b * n / avg))
    return out

def interleave(rankings):
    """several queries' rankings -> one: each location at its best rank across the queries, round robin at equal rank (query order), so
    every query keeps its own top hits (summing scores lets the sources that match several queries in several lists push the rest out)"""
    best = {}
    for qi, r in enumerate(rankings):
        for i, (loc, s) in enumerate(r):
            if loc not in best or (i, qi) < best[loc][:2]: best[loc] = (i, qi, s)
    return [(loc, v[2]) for loc, v in sorted(best.items(), key=lambda kv: kv[1][:2])]

def fuse(rankings, k=60):
    """reciprocal rank fusion of several [(locator, score)] lists -> [(locator, fused score)] best first"""
    out = {}
    for r in rankings:
        for i, (loc, _) in enumerate(r): out[loc] = out.get(loc, 0.0) + 1.0 / (k + i + 1)
    return sorted(out.items(), key=lambda x: -x[1])

if __name__ == "__main__":   # `python retrieval_backends.py fetch-model`: run by `dbcx retrieval enable` with the Python that has model2vec
    if sys.argv[1:] != ["fetch-model"]: sys.exit("usage: retrieval_backends.py fetch-model")
    try: fetch_model(lambda m: print(m, flush=True))
    except Exception as e: sys.exit(f"FAILED: {type(e).__name__}: {e}")
