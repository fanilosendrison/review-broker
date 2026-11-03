"""Requester mission and mandatory profile composition; no source or execution authority."""
from __future__ import annotations

from importlib import resources
import json
from typing import Any

# Any retains the schema-validated request/profile JSON representation across this extraction.

from .source_authorization import SourceAuthorizationError as OrchestrationError


def review_instruction(request: dict[str, Any], profile: dict[str, Any]) -> str:
    mission = request["mission"]
    profile_rules = "\n".join(f"- {rule}" for rule in profile["mandatory_behavior"])
    criteria = "\n".join(f"- {criterion}" for criterion in mission["criteria"])
    return (
        f"OBJECTIVE: {mission['objective']}\n"
        f"REQUESTER INSTRUCTIONS: {mission['instructions']}\n"
        f"MANDATORY PROFILE BEHAVIOR:\n{profile_rules}\n"
        f"EXAMINATION CRITERIA:\n{criteria}\n"
        "The custom mission may strengthen but never disable mandatory profile behavior."
    )


def load_profile(profile_id: str, version: int) -> dict[str, Any]:
    target = resources.files("review_broker.profiles").joinpath(f"{profile_id}-v{version}.json")
    try:
        profile = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise OrchestrationError("PROFILE_UNAVAILABLE") from exc
    if profile.get("id") != profile_id or profile.get("version") != version:
        raise OrchestrationError("PROFILE_IDENTITY_MISMATCH")
    if profile.get("custom_mission_may_disable") is not False:
        raise OrchestrationError("PROFILE_WEAKENING_FORBIDDEN")
    return profile
