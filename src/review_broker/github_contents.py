"""Strict GitHub Contents Base64 transport decoding, separate from journal state."""
import base64

_BASE64_ALPHABET = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
_BASE64_WHITESPACE = frozenset(b" \t\r\n")


def decode_github_contents_base64(encoded: str) -> bytes:
    if not isinstance(encoded, str):
        raise ValueError("GITHUB_CONTENT_BASE64_INVALID")
    try:
        formatted = encoded.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("GITHUB_CONTENT_BASE64_INVALID") from exc
    compact = bytes(value for value in formatted if value not in _BASE64_WHITESPACE)
    if any(value not in _BASE64_ALPHABET for value in compact):
        raise ValueError("GITHUB_CONTENT_BASE64_INVALID")
    raw = base64.b64decode(compact, validate=True)
    if base64.b64encode(raw) != compact:
        raise ValueError("GITHUB_CONTENT_BASE64_NONCANONICAL")
    return raw
