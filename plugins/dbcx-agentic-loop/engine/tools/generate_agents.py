#!/usr/bin/env python3
"""Generate the Claude Code agents (agents/*.md) from the canonical role texts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime import PLUGIN, resolve_model


ROLES = PLUGIN / "roles"
INDEX = ROLES / "index.json"


def body_from_claude(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n.*?\n---\n(.*)$", text, re.S)
    return (match.group(1) if match else text).strip() + "\n"


def bootstrap(index: dict[str, dict]) -> None:
    ROLES.mkdir(parents=True, exist_ok=True)
    for name in index:
        target = ROLES / f"{name}.md"
        if target.exists():
            continue
        source = PLUGIN / "agents" / f"{name}.md"
        if not source.exists():
            raise SystemExit(f"cannot bootstrap missing role {name}: {source}")
        target.write_text(body_from_claude(source), encoding="utf-8")


def generate(index: dict[str, dict]) -> None:
    claude_dir = PLUGIN / "agents"
    claude_dir.mkdir(parents=True, exist_ok=True)
    for name, metadata in index.items():
        role_path = ROLES / f"{name}.md"
        if not role_path.exists():
            raise SystemExit(f"missing canonical role {role_path}")
        body = role_path.read_text(encoding="utf-8").strip() + "\n"
        digest = hashlib.sha256(body.encode()).hexdigest()
        # An agent's model_role is a semantic role key, not a model alias.
        # Let resolve_model map that role through model-profiles.json.
        cfg = {}
        claude = resolve_model(cfg, metadata["model_role"])
        frontmatter = [
            "---",
            f"name: {name}",
            f"description: {metadata['description']}",
            f"model: {claude.model}",
        ]
        if metadata.get("max_turns"):
            frontmatter.append(f"maxTurns: {metadata['max_turns']}")
        frontmatter.append(f"tools: {metadata['claude_tools']}")
        if metadata.get("cache_ttl"):
            # Long-running roles idle between tool calls and critic rounds for
            # more than the 5-minute default TTL of Claude Code subagents.
            # `experimental.cacheTtl` (Claude Code >= 2.1.248) keeps the prefix
            # warm for an hour; a global subagentPromptCacheTtl would also hit
            # one-shot helper requests.
            frontmatter += ["experimental:", f"  cacheTtl: {metadata['cache_ttl']}"]
        frontmatter.append("---")
        claude_text = "\n".join(frontmatter) + f"\n<!-- dbcx-role-sha256: {digest} -->\n" + body
        (claude_dir / f"{name}.md").write_text(claude_text, encoding="utf-8")
    print(f"generated {len(index)} Claude agents from roles/")


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"generate_agents is a maintainer tool: it regenerates agents/ from roles/, which only a git checkout of the plugin has (not {PLUGIN})")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if "--bootstrap" in sys.argv:
        bootstrap(index)
    generate(index)


if __name__ == "__main__":
    main()
