"""Helpers for loading built-in and file-backed action safety policies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILTIN_POLICY_ROOT = REPO_ROOT / "policies"


def list_builtin_policy_names() -> list[str]:
    if not BUILTIN_POLICY_ROOT.exists():
        return []
    names: list[str] = []
    for path in sorted(BUILTIN_POLICY_ROOT.glob("*.yml")):
        names.append(path.stem)
    for path in sorted(BUILTIN_POLICY_ROOT.glob("*.yaml")):
        if path.stem not in names:
            names.append(path.stem)
    return names


def builtin_policy_path(name: str) -> Path:
    normalized = name.strip()
    if not normalized:
        raise ValueError("Policy preset name must not be empty.")
    for suffix in (".yml", ".yaml"):
        candidate = BUILTIN_POLICY_ROOT / f"{normalized}{suffix}"
        if candidate.exists():
            return candidate
    available = ", ".join(list_builtin_policy_names()) or "none"
    raise ValueError(f"Unknown policy preset '{normalized}'. Available presets: {available}")


def load_policy_file(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read safety policy file: {path}") from exc

    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            payload = json.loads(text)
        elif suffix in {".yml", ".yaml"}:
            payload = yaml.safe_load(text)
        else:
            raise ValueError("Safety policy files must end with .json, .yml, or .yaml")
    except (json.JSONDecodeError, yaml.YAMLError, ValueError) as exc:
        raise ValueError(f"Unable to parse safety policy file: {path}") from exc

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Safety policy file must contain an object: {path}")
    return {str(key): value for key, value in payload.items()}


def resolve_policy_path(path: str, *, cwd: Path | None = None) -> Path:
    candidate = Path(path.strip())
    if candidate.is_absolute():
        return candidate
    base = cwd or Path.cwd()
    return (base / candidate).resolve()


def resolve_action_safety_policy(
    *,
    inline_json: str | None = None,
    preset: str | None = None,
    file_path: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    policy: dict[str, Any] = {}
    if preset and preset.strip():
        policy.update(load_policy_file(builtin_policy_path(preset)))
    if file_path and file_path.strip():
        policy.update(load_policy_file(resolve_policy_path(file_path, cwd=cwd)))
    if inline_json and inline_json.strip():
        try:
            payload = json.loads(inline_json)
        except json.JSONDecodeError as exc:
            raise ValueError("Inline safety policy JSON must be a JSON object.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Inline safety policy JSON must be a JSON object.")
        policy.update(payload)
    return policy or None
