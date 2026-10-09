#!/usr/bin/env python3
"""Fetch a help.sap.com topic as plain text via the portal's own JSON API."""
import json, re, sys, urllib.parse, urllib.request, html

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def strip(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?i)</(tr|div|p|li|h[1-6]|table)>", "\n", h)
    h = re.sub(r"(?i)</t[dh]>", " | ", h)
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)
    h = re.sub(r"<[^>]+>", "", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t]+", " ", h)
    h = re.sub(r"\n\s*\n+", "\n", h)
    return h.strip()


def fetch(product, deliverable, topic=None, version="LATEST"):
    p = {
        "product_url": product,
        "deliverable_url": deliverable,
        "version": version,
        "language": "en-US",
        "state": "PRODUCTION",
        "loadlandingpageontopicnotfound": "true",
    }
    if topic:
        p["topic_url"] = topic
    md = get("https://help.sap.com/http.svc/deliverableMetadata?" + urllib.parse.urlencode(p))
    d = md["data"]
    dl = d["deliverable"]
    out = {
        "deliverable_title": dl.get("title"),
        "deliverable_version": dl.get("versionName") or dl.get("version"),
        "file_path": d.get("filePath"),
        "topic_loio": d.get("topicLoio"),
        "id": dl.get("id"),
        "build": dl.get("buildNo"),
    }
    q = {
        "deliverableInfo": 0,
        "deliverable_id": dl["id"],
        "buildNo": dl["buildNo"],
    }
    if out["file_path"]:
        q["file_path"] = out["file_path"]
    pc = get("https://help.sap.com/http.svc/pagecontent?" + urllib.parse.urlencode(q))
    data = pc["data"]
    out["title"] = (data.get("currentPage") or {}).get("t")
    out["text"] = strip(data.get("body") or data.get("content") or "")
    return out, d


if __name__ == "__main__":
    url = sys.argv[1]
    m = re.search(r"/docs/([^/]+)/([0-9a-f]{32})(?:/([0-9a-f]{32}))?", url)
    ver = "LATEST"
    mv = re.search(r"version=(v?[\w.\-]+)", url)
    if mv:
        ver = mv.group(1)
    prod, deliv, topic = m.group(1), m.group(2), m.group(3)
    out, raw = fetch(prod, deliv, topic, ver)
    print("### DELIVERABLE:", out["deliverable_title"], "| version:", out["deliverable_version"])
    print("### TOPIC:", out["title"])
    print(out["text"])
