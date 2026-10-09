#!/usr/bin/env python3
"""Package versioning and model resolution (Claude Code only; models are the Agent tool's aliases)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any


TOOLS = Path(__file__).resolve().parent
ENGINE = TOOLS.parent
PLUGIN = ENGINE.parent
DEFAULT_PROFILES = ENGINE / "defaults" / "model-profiles.json"
HARNESS = PROVIDER = "claude"   # recorded per brief and agent (provenance)


@dataclass(frozen=True)
class ModelSelection:
    role: str
    profile: str
    harness: str
    provider: str
    model: str
    reasoning_effort: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def package_version() -> str:
    """VERSION as stamped by the release (MAJOR.MINOR.PATCH); a dev checkout holds only MAJOR.MINOR -> <MAJOR.MINOR>.dev"""
    version_file = PLUGIN / "VERSION"
    if version_file.exists():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return f"{value}.dev" if value.count(".") == 1 else value
    legacy = PLUGIN / ".claude-plugin" / "plugin.json"
    if legacy.exists() and json.loads(legacy.read_text(encoding="utf-8")).get("version"):
        return str(json.loads(legacy.read_text(encoding="utf-8"))["version"])
    return "0.0.0+unknown"


def package_commit() -> str:
    """the full sha the release stamped into COMMIT ("" in a dev checkout)"""
    commit_file = PLUGIN / "COMMIT"
    return commit_file.read_text(encoding="utf-8").strip() if commit_file.exists() else ""


def load_profiles(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    profile_path = Path(path) if path else DEFAULT_PROFILES
    return json.loads(profile_path.read_text(encoding="utf-8"))


def _override_map(cfg: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    value = cfg.get("model_overrides") or {}
    if isinstance(value, dict):
        result.update(value)
    raw = os.environ.get("DBCX_MODEL_OVERRIDES", "").strip()
    if raw:
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise SystemExit("DBCX_MODEL_OVERRIDES must be a JSON object")
        result.update(decoded)
    return result


def resolve_model(
    cfg: dict[str, Any],
    role: str,
    *,
    profiles: dict[str, Any] | None = None,
) -> ModelSelection:
    profiles = profiles or load_profiles()
    provider = PROVIDER
    configured = (cfg.get("models") or {}).get(role)
    default_profile = profiles["roles"].get(role, role)
    legacy = profiles.get("legacy_aliases", {})

    profile = default_profile
    explicit_model: str | None = None
    explicit_effort: str | None = None
    if isinstance(configured, dict):
        profile = configured.get("profile") or default_profile
        provider_value = configured.get(provider)
        if isinstance(provider_value, str):
            explicit_model = provider_value
        elif isinstance(provider_value, dict):
            explicit_model = provider_value.get("model")
            explicit_effort = provider_value.get("reasoning_effort") or provider_value.get("effort")
    elif isinstance(configured, str) and configured:
        if configured in profiles.get("providers", {}).get(provider, {}):
            profile = configured
        elif configured in legacy:
            profile = legacy[configured]
        else:
            explicit_model = configured

    base = dict(profiles["providers"][provider].get(profile) or {})
    if not base and not explicit_model:
        raise SystemExit(f"no {provider} model mapping for semantic profile {profile!r} (role {role!r})")

    overrides = _override_map(cfg)
    override = overrides.get(role, overrides.get(profile, {}))
    if isinstance(override, str):
        explicit_model = override
    elif isinstance(override, dict):
        scoped = override.get(provider, override)
        if isinstance(scoped, str):
            explicit_model = scoped
        elif isinstance(scoped, dict):
            explicit_model = scoped.get("model", explicit_model)
            explicit_effort = scoped.get("reasoning_effort", scoped.get("effort", explicit_effort))

    model = explicit_model or base.get("model")
    effort = explicit_effort or base.get("reasoning_effort") or "medium"
    if not model:
        raise SystemExit(f"model override for {role!r} did not provide a model")
    return ModelSelection(role, profile, HARNESS, provider, str(model), str(effort))


def package_root_from_env() -> str:
    for name in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        value = os.environ.get(name)
        if value:
            return os.path.abspath(os.path.expanduser(value))
    return str(PLUGIN)
