"""Race-resistant observation of regular files."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat
from typing import BinaryIO, Iterator


class FileObservationError(OSError):
    """A path could not be observed as one stable regular file."""


def _identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


@contextmanager
def observed_regular_file(path: Path) -> Iterator[BinaryIO]:
    """Open one stable regular-file identity without following a symlink."""
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise FileObservationError("OBSERVED_FILE_NOT_REGULAR")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
            raise FileObservationError("OBSERVED_FILE_IDENTITY_CHANGED")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            yield stream
            if _identity(opened) != _identity(os.fstat(descriptor)):
                raise FileObservationError("OBSERVED_FILE_CHANGED_DURING_READ")
    finally:
        os.close(descriptor)


def read_regular_file_bounded(path: Path, limit: int) -> bytes:
    """Read at most limit bytes and distinguish exact-limit from overflow."""
    if type(limit) is not int or limit < 0:
        raise ValueError("OBSERVED_FILE_LIMIT_INVALID")
    chunks: list[bytes] = []
    total = 0
    with observed_regular_file(path) as stream:
        while total <= limit:
            chunk = stream.read(min(65_536, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    if total > limit:
        raise FileObservationError("OBSERVED_FILE_LIMIT_EXCEEDED")
    return b"".join(chunks)
