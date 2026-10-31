"""Sanitized classification of GitHub GraphQL application-error metadata."""
from __future__ import annotations

import re


def graphql_error_code(error: object) -> str:
    """Return only authenticated structured type metadata, never backend text."""
    if not isinstance(error, dict):
        return "GRAPHQL_APPLICATION_ERROR"
    candidate = error.get("type")
    extensions = error.get("extensions")
    extension_code = extensions.get("code") if isinstance(extensions, dict) else None
    if (isinstance(candidate, str) and isinstance(extension_code, str)
            and candidate != extension_code):
        return "GRAPHQL_APPLICATION_ERROR"
    if not isinstance(candidate, str):
        candidate = extension_code
    if isinstance(candidate, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", candidate):
        return f"GRAPHQL_TYPED_{candidate}"
    return "GRAPHQL_APPLICATION_ERROR"
