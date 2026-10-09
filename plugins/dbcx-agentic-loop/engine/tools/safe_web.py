#!/usr/bin/env python3
"""Hook-visible, privacy-checked web access for restricted dbcx roles.

Usage:
  dbcx safe_web "generic query" --check-only
  dbcx safe_web "generic query" --url https://allowed.example/docs/page [--max-bytes N]
In-process (the quote gate, `dbcx evidence quotes`): fetch(url) = the same check + the raw body; page_text(url) = readable page
text - help.sap.com through its content service (http.svc/deliverableMetadata + pagecontent: the site answers HTTP 200 for any
URL), api.sap.com refused as unreadable (a single-page app), any other page with its tags stripped.
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
import sys
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SCOPES_PATH, declared_standard_critics, evidence_bases, extra_option_packs, load_json, pack, pack_snippets, project, snippets


LOCATOR = re.compile(r"\bSRC-\d{3}|\bHO-[\w-]+#", re.I)


def _mentions_as_path(value: str, spelling: str) -> bool:
    """A base root counts as mentioned in a web query only when it appears path-like - adjacent to a
    `/` or `\\` on at least one side - never as an ordinary standalone word: an engine base literally
    named `deliverables`, `intern` or `render` must not turn "project deliverables", "international
    shipping" or "server side rendering" into a privacy violation, while a genuine path fragment
    ("analysis/x", "../../repo/core-customize") still counts."""
    esc = re.escape(spelling)
    return re.search(r"(?<![\w.-])" + esc + r"[/\\]|[/\\]" + esc + r"(?![\w.-])", value) is not None


def allowed_domains(cfg: dict) -> set[str]:
    domains: set[str] = set()
    for base in evidence_bases(cfg):
        if base.get("external"):
            domains.update(str(value).lower().strip(" .") for value in base.get("domains", []) if value)
    text = " ".join([snippets(cfg).get("docs_domains", "")] + [pack_snippets(cfg, pk).get("docs_domains", "") for pk in extra_option_packs(cfg)])   # union over the option packs
    found = re.findall(r"(?<![\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}(?![\w.-])", text.lower())
    domains.update(value for value in found if not value.endswith((".py", ".md", ".json", ".sh", ".toml")))
    for d in declared_standard_critics(cfg):   # a declared standard critic's domains and its packs' docs_domains join the union (per critic stated in its brief, not enforced)
        domains.update(str(x).lower().strip(" .") for x in d["sources"]["domains"] if x)
        found = re.findall(r"(?<![\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}(?![\w.-])", " ".join(pack_snippets(cfg, pack(n)).get("docs_domains", "") for n in d["sources"]["packs"]).lower())
        domains.update(value for value in found if not value.endswith((".py", ".md", ".json", ".sh", ".toml")))
    return domains


def privacy_reasons(query: str, cfg: dict) -> list[str]:
    lowered = query.lower()
    reasons: list[str] = []
    client = str((cfg.get("engagement") or {}).get("client") or "").strip()
    if client and len(client) > 2 and client.lower() in lowered and not (cfg.get("hook") or {}).get("client_name_public"):
        reasons.append("client name")
    scopes = (load_json(SCOPES_PATH, {}) or {}).get("scopes", {}) if os.path.exists(SCOPES_PATH) else {}
    if not (cfg.get("_method", {}).get("hook") or {}).get("scope_names_public"):
        for scope in scopes:
            if len(scope) > 5 and scope.lower() in lowered:
                reasons.append(f"non-public scope name {scope!r}")
    for base in evidence_bases(cfg):
        if base.get("external") or base.get("privacy") is False:   # a run-folder base (not client evidence) opts out
            continue
        for root in base.get("abs_roots", []):
            # No length floor: path-adjacency (not word length) is what makes a mention unambiguous,
            # and a short root ("repo") must still be caught as "../../repo/core-customize".
            candidates = {str(root).lower(), os.path.basename(str(root)).lower()}
            if any(_mentions_as_path(lowered, value) for value in candidates):
                reasons.append("internal evidence path")
                break
    if LOCATOR.search(query):
        reasons.append("internal corpus/handover locator")
    return sorted(set(reasons))


def domain_allowed(url: str, domains: set[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return bool(host and any(host == domain or host.endswith("." + domain) for domain in domains))


def validate(query: str, url: str | None = None) -> dict[str, object]:
    cfg = project()
    reasons = privacy_reasons(query + (" " + url if url else ""), cfg)
    domains = allowed_domains(cfg)
    if url and not domain_allowed(url, domains):
        reasons.append(f"domain is not allowlisted ({urlparse(url).hostname or 'missing host'})")
    return {"allowed": not reasons, "reasons": reasons, "allowed_domains": sorted(domains), "query": query, "url": url}


def _get(url: str, limit: int) -> bytes:
    request = Request(url, headers={"User-Agent": "dbcx-safe-web/0.7", "Accept": "text/html,text/plain,application/json"})
    with urlopen(request, timeout=30) as response:
        body = response.read(limit + 1)
        if len(body) > limit:
            raise SystemExit(f"response exceeds --max-bytes {limit}")
        return body


def fetch(url: str, query: str = "quote check", limit: int = 1_000_000) -> bytes:
    """validate() then the raw body - the in-process twin of `dbcx safe_web <query> --url <url>`; PermissionError when refused."""
    result = validate(query, url)
    if not result["allowed"]:
        raise PermissionError("safe_web refused: " + "; ".join(result["reasons"]))
    return _get(url, limit)


def html_text(raw: str) -> str:
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


SPA_HOSTS = ("api.sap.com",)   # single-page apps: HTTP 200 and the same shell for any URL - no page text to check


def page_text(url: str, query: str = "quote check", depth: int = 0) -> str:
    """Readable text of a documentation page (every request passes validate()). ValueError when the page cannot be read."""
    parts = urlparse(url); host = (parts.hostname or "").lower()
    if host in SPA_HOSTS:
        raise ValueError(f"{host} is a single-page app (HTTP 200 for any URL) - its text is not readable")
    if host != "help.sap.com":
        return html_text(fetch(url, query).decode("utf-8", "ignore"))
    if "/docs/" not in parts.path:
        raise ValueError("help.sap.com URL without /docs/<product>/<deliverable>/<topic> - the content service needs that form")
    p = parts.path.split("/docs/", 1)[1].split("/") + ["", ""]
    version = parse_qs(parts.query).get("version", ["LATEST"])[0]; svc = "https://help.sap.com/http.svc/"
    meta = json.loads(fetch(f"{svc}deliverableMetadata?product_url={quote(p[0])}&deliverable_url={quote(p[1])}&topic_url={quote(p[2])}&version={quote(version)}&loadlandingpageontopicnotfound=false", query))
    if meta.get("status") != "OK":
        raise ValueError(f"help.sap.com: no such page (content service status {meta.get('status')})")
    data = meta.get("data") or {}
    if data.get("redirect") and depth < 3:
        return page_text("https://help.sap.com" + data["redirect"], query, depth + 1)
    content = json.loads(fetch(f"{svc}pagecontent?deliverableInfo=1&deliverable_id={data['deliverable']['id']}&file_path={quote(data.get('filePath', ''))}", query))
    return html_text((content.get("data") or {}).get("body", ""))


def main() -> None:
    args = sys.argv[1:]
    positional = [value for index, value in enumerate(args) if not value.startswith("--") and (index == 0 or args[index - 1] not in {"--url", "--max-bytes"})]
    if not positional:
        raise SystemExit(__doc__)
    query = positional[0]
    url = args[args.index("--url") + 1] if "--url" in args else None
    limit = int(args[args.index("--max-bytes") + 1]) if "--max-bytes" in args else 1_000_000
    result = validate(query, url)
    if not result["allowed"]:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(2)
    if "--check-only" in args or not url:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    sys.stdout.buffer.write(_get(url, limit))


if __name__ == "__main__":
    main()
