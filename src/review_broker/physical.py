"""Decode UTF-8 snapshots without losing physical byte/line boundaries."""
from __future__ import annotations

from typing import Any


class PhysicalLineError(ValueError):
    """The source bytes cannot be mapped to UTF-8 physical lines."""


def decode_physical_lines(data: bytes) -> tuple[str, tuple[str, ...], tuple[dict[str, Any], ...]]:
    has_bom = data.startswith(b"\xef\xbb\xbf")
    encoding = "utf-8-sig" if has_bom else "utf-8"
    lines: list[str] = []
    mapping: list[dict[str, Any]] = []
    start = 0
    number = 1
    while start < len(data):
        cursor = start
        while cursor < len(data) and data[cursor] not in (10, 13):
            cursor += 1
        content_end = cursor
        if cursor == len(data):
            line_end, ending = cursor, "NONE"
        elif data[cursor:cursor + 2] == b"\r\n":
            line_end, ending = cursor + 2, "CRLF"
        elif data[cursor] == 10:
            line_end, ending = cursor + 1, "LF"
        else:
            line_end, ending = cursor + 1, "CR"
        content_start = start + (3 if number == 1 and has_bom else 0)
        try:
            text = data[content_start:content_end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PhysicalLineError("SOURCE_ENCODING_INVALID") from exc
        lines.append(text)
        mapping.append({
            "line": number,
            "byte_start": start,
            "content_start": content_start,
            "content_end": content_end,
            "line_end": line_end,
            "ending": ending,
        })
        start = line_end
        number += 1
    return encoding, tuple(lines), tuple(mapping)
