"""Resolve the attributable GitHub publication actor for trusted callers."""
from __future__ import annotations

import os
from typing import Any, Callable, Mapping


ACTIONS_BOT_LOGIN = "github-actions[bot]"
ACTIONS_BOT_ID = 41898282
ACTIONS_BOT_TYPE = "Bot"


class PublisherIdentityError(RuntimeError):
    """The actual GitHub publication actor cannot be established."""


def resolve_publisher_identity(
    get_json: Callable[[str], Any],
    *,
    environment: Mapping[str, str] = os.environ,
) -> dict[str, Any]:
    """Resolve a user token or the official GitHub.com Actions installation actor."""
    if environment.get("GITHUB_ACTIONS") == "true":
        if (
            environment.get("GITHUB_SERVER_URL") != "https://github.com"
            or environment.get("GITHUB_API_URL") != "https://api.github.com"
        ):
            raise PublisherIdentityError("PUBLICATION_ACTIONS_CONTEXT_UNSUPPORTED")
        value = get_json("users/github-actions%5Bbot%5D")
        if not isinstance(value, dict) or (
            value.get("login") != ACTIONS_BOT_LOGIN
            or value.get("id") != ACTIONS_BOT_ID
            or value.get("type") != ACTIONS_BOT_TYPE
        ):
            raise PublisherIdentityError("PUBLICATION_ACTIONS_ACTOR_INVALID")
        return {"login": ACTIONS_BOT_LOGIN, "id": ACTIONS_BOT_ID}

    value = get_json("user")
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("login"), str)
        or not value["login"]
        or not isinstance(value.get("id"), int)
    ):
        raise PublisherIdentityError("PUBLICATION_ACTOR_INVALID")
    return {"login": value["login"], "id": value["id"]}
