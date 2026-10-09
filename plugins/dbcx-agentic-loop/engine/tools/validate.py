#!/usr/bin/env python3
"""Minimal JSON schema validator (required keys, enums, types) - no external dependency.
Usage: python3 tools/validate.py <schema.json> <file.json> [more files]     exit code 1 if any file is invalid.
Also used as a library by md_to_json.py (check_data)."""
import json, sys

TYPES = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "number": (int, float), "null": type(None)}

def check(schema, data, path, errs):
    t = schema.get("type")
    if t:
        ts = t if isinstance(t, list) else [t]
        if not any(isinstance(data, TYPES[x]) and not (x == "integer" and isinstance(data, bool)) for x in ts):
            errs.append(f"{path}: expected {ts}, got {type(data).__name__}"); return
    if "enum" in schema and data not in schema["enum"]:
        errs.append(f"{path}: value {data!r} not in {schema['enum']}")
    if isinstance(data, dict):
        for r in schema.get("required", []):
            if r not in data: errs.append(f"{path}: missing required key '{r}'")
        for k, sub in schema.get("properties", {}).items():
            if k in data: check(sub, data[k], f"{path}.{k}", errs)
    if isinstance(data, list) and "items" in schema:
        for i, it in enumerate(data): check(schema["items"], it, f"{path}[{i}]", errs)

def semantic(data, errs):
    if isinstance(data.get("claims"), list):
        ids = [c.get("id") for c in data["claims"]]
        if len(ids) != len(set(ids)): errs.append("duplicate claim ids")
        for c in data["claims"]:
            if c.get("type") == "fact" and not c.get("evidence"): errs.append(f"claim {c.get('id')}: fact without evidence")
    if isinstance(data.get("scores"), list) and all(isinstance(x, dict) and "claim_id" in x and "verdict" in x for x in data["scores"]):   # critic score files only
        for s in data["scores"]:
            if isinstance(s.get("score"), int) and s["score"] < 8 and not (s.get("issue") or "").strip(): errs.append(f"score {s.get('claim_id')} < 8 without issue text")
            if isinstance(s.get("score"), int) and s["score"] <= 4 and not s.get("counter_evidence"): errs.append(f"score {s.get('claim_id')} <= 4 without counter_evidence")

def check_data(schema, data):
    errs = []; check(schema, data, "$", errs); semantic(data, errs); return errs

def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    schema = json.load(open(sys.argv[1], encoding="utf-8")); bad = 0
    for f in sys.argv[2:]:
        try: data = json.load(open(f, encoding="utf-8"))
        except Exception as e: print(f"INVALID {f}: {e}"); bad += 1; continue
        errs = check_data(schema, data)
        if errs: bad += 1; print(f"INVALID {f}:"); [print("   ", e) for e in errs[:60]]
        else: print(f"OK {f}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
