#!/usr/bin/env python3
import json, sys, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def search(q, product="SAP_COMMERCE_CLOUD_PUBLIC_CLOUD", n=8):
    p = {
        "area": "content", "language": "en-US", "state": "PRODUCTION",
        "q": q, "transtype": "standard", "product": product,
        "to": n, "advancedSearch": 0, "excludeNotSearchable": 1,
    }
    req = urllib.request.Request(
        "https://help.sap.com/http.svc/elasticsearch?" + urllib.parse.urlencode(p), headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    for x in d["data"]["results"]:
        print(x["title"], "|", x["deliverableTitle"], "|", x["version"])
        print("   https://help.sap.com" + x["url"])


if __name__ == "__main__":
    prod = sys.argv[2] if len(sys.argv) > 2 else "SAP_COMMERCE_CLOUD_PUBLIC_CLOUD"
    search(sys.argv[1], prod)
