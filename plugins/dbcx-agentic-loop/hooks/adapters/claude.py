"""Claude Code hook event adapter."""

from __future__ import annotations

from typing import Any

from policy import Event


def normalize(event_name: str, payload: dict[str, Any]) -> Event:
    return Event(
        event=event_name or str(payload.get("hook_event_name") or ""),
        harness="claude",
        cwd=str(payload.get("cwd") or ""),
        tool=str(payload.get("tool_name") or ""),
        tool_input=payload.get("tool_input") or {},
        agent_name=str(payload.get("agent_name") or payload.get("agentName") or ""),
        agent_type=str(payload.get("agent_type") or payload.get("agentType") or ""),
        raw=payload,
    )


def successful_stop(messages: list[str]) -> str:
    return "\n".join(messages)
