#!/usr/bin/env python3
"""Reachability check for SAP Commerce business-process definitions: parses every *.xml whose root element is
<process> (namespace http://www.hybris.de/xsd/processdefinition, or none) and computes, from the root's `start` attribute, which
nodes a BFS over transition/then/choice/timeout/targetNode edges can actually reach - the rest are dead: this definition never
executes them. Also reports, for every wait node, whether a timeout fires into a node that eventually reaches a SUCCEEDED end.

Usage: python3 process_reach.py <file-or-folder> ... [--json]
Prints per file: process name, start node, node/reachable counts, unreachable node ids, and per wait node its event and each
timeout's delay/target, flagged TIMEOUT->SUCCESS when that target reaches an end with state SUCCEEDED; then the RULE line to quote.
"""
import os, sys, json
import xml.etree.ElementTree as ET

def local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag

def analyse(path):
    """None if path is not a process definition; else {name, start, nodes, reachable, unreachable, waits, file}."""
    try: root = ET.parse(path).getroot()
    except ET.ParseError: return None
    if local(root.tag) != "process": return None
    start = root.get("start"); name = root.get("name")
    nodes = {child.get("id"): child for child in root if child.get("id")}
    edges = {nid: set() for nid in nodes}
    waits = []
    for nid, el in nodes.items():
        then = el.get("then")
        if then: edges[nid].add(then)
        for sub in el.iter():
            sk = local(sub.tag)
            if sk == "transition" and sub.get("to"): edges[nid].add(sub.get("to"))
            elif sk == "targetNode" and sub.get("name"): edges[nid].add(sub.get("name"))
            elif sk == "timeout" and sub.get("then"): edges[nid].add(sub.get("then"))
            elif sk == "choice" and sub.get("then"): edges[nid].add(sub.get("then"))
        if local(el.tag) == "wait":
            ev = next((sub.text.strip() for sub in el if local(sub.tag) == "event" and sub.text), None)
            timeouts = [{"delay": sub.get("delay"), "then": sub.get("then")} for sub in el.iter() if local(sub.tag) == "timeout"]
            waits.append({"id": nid, "event": ev, "timeouts": timeouts})
    reachable = set()
    if start in nodes:
        stack = [start]; reachable.add(start)
        while stack:
            cur = stack.pop()
            for nxt in edges.get(cur, ()):
                if nxt in nodes and nxt not in reachable: reachable.add(nxt); stack.append(nxt)
    unreachable = sorted(set(nodes) - reachable)

    def reaches_success(nid, seen):
        if nid not in nodes or nid in seen: return False
        seen.add(nid); el = nodes[nid]
        if local(el.tag) == "end": return el.get("state") == "SUCCEEDED"
        return any(reaches_success(nxt, seen) for nxt in edges.get(nid, ()))

    for w in waits:
        for t in w["timeouts"]: t["reaches_success"] = bool(t["then"]) and reaches_success(t["then"], set())
    return {"name": name, "start": start, "nodes": sorted(nodes), "reachable": sorted(reachable), "unreachable": unreachable, "waits": waits, "file": path}

def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p): files += [os.path.join(dp, f) for dp, _, fs in os.walk(p) for f in fs if f.lower().endswith(".xml")]
        else: files.append(p)
    return files

def main():
    a = sys.argv[1:]
    paths = [x for x in a if not x.startswith("--")]
    if not paths: sys.exit(__doc__)
    results = [r for r in (analyse(f) for f in sorted(collect(paths))) if r]
    if "--json" in a: print(json.dumps(results, indent=1)); return
    nf = nw = 0
    for r in results:
        nf += 1
        print(f"{os.path.relpath(r['file'])}: process {r['name']!r} start {r['start']!r} - {len(r['nodes'])} nodes, {len(r['reachable'])} reachable")
        if r["unreachable"]: print(f"  UNREACHABLE: {', '.join(r['unreachable'])}")
        for w in r["waits"]:
            nw += 1
            print(f"  wait {w['id']} event {w['event']}")
            for t in w["timeouts"]:
                flag = " TIMEOUT->SUCCESS" if t["reaches_success"] else ""
                print(f"    timeout delay {t['delay']} -> {t['then']}{flag}")
    print(f"RULE: a node is reachable when a breadth-first search from the process's `start` attribute, over <transition to=..>, a node's own `then=`, <case><choice then=..> and <timeout then=..> inside wait nodes, and a split's <targetNode name=..>, reaches it; a node this search never reaches is never executed by this process definition -> {nf} process file(s), {nw} wait node(s) examined")

if __name__ == "__main__":
    main()
