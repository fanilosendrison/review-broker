"""Bounded, coherent observation of regular-file path and byte identities."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
from typing import BinaryIO, Iterator


_READ_BLOCK_BYTES = 65_536


class FileObservationError(OSError):
    """A path could not be observed as one coherent regular file."""


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


def _file_identity(value: os.stat_result) -> tuple[int, int, int]:
    return value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode)


class _ObservedBinaryStream:
    """Track one caller's sequential first pass without retaining its bytes."""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._digest = hashlib.sha256()
        self._length = 0
        self._eof_reached = False

    def read(self, size: int = -1) -> bytes:
        try:
            value = self._stream.read(size)
        except OSError as exc:
            raise FileObservationError("OBSERVED_FILE_READ_FAILED") from exc
        self._record(value)
        if size < 0 or not value and size != 0:
            self._eof_reached = True
        return value

    def readline(self, size: int = -1) -> bytes:
        try:
            value = self._stream.readline(size)
        except OSError as exc:
            raise FileObservationError("OBSERVED_FILE_READ_FAILED") from exc
        self._record(value)
        if (
            not value and size != 0
            or size < 0 and value and not value.endswith(b"\n")
        ):
            self._eof_reached = True
        return value

    def first_pass_identity(self) -> tuple[int, str]:
        if not self._eof_reached:
            raise FileObservationError("OBSERVED_FILE_READ_INCOMPLETE")
        return self._length, self._digest.hexdigest()

    def _record(self, value: bytes) -> None:
        self._digest.update(value)
        self._length += len(value)


def _second_pass_identity(descriptor: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    length = 0
    offset = 0
    try:
        while True:
            block = os.pread(descriptor, _READ_BLOCK_BYTES, offset)
            if not block:
                break
            digest.update(block)
            block_length = len(block)
            length += block_length
            offset += block_length
    except OSError as exc:
        raise FileObservationError("OBSERVED_FILE_SECOND_READ_FAILED") from exc
    return length, digest.hexdigest()


def _lstat(path: Path) -> os.stat_result:
    try:
        return path.lstat()
    except OSError as exc:
        raise FileObservationError("OBSERVED_FILE_PATH_UNAVAILABLE") from exc


def _fstat(descriptor: int) -> os.stat_result:
    try:
        return os.fstat(descriptor)
    except OSError as exc:
        raise FileObservationError("OBSERVED_FILE_DESCRIPTOR_UNAVAILABLE") from exc


@contextmanager
def observed_regular_file(path: Path) -> Iterator[BinaryIO]:
    """Accept two coherent descriptor reads and a final matching path identity."""
    before = _lstat(path)
    if not stat.S_ISREG(before.st_mode):
        raise FileObservationError("OBSERVED_FILE_NOT_REGULAR")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise FileObservationError("OBSERVED_FILE_OPEN_FAILED") from exc
    try:
        opened = _fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
            raise FileObservationError("OBSERVED_FILE_IDENTITY_CHANGED")
        with os.fdopen(descriptor, "rb", closefd=False) as raw_stream:
            observed_stream = _ObservedBinaryStream(raw_stream)
            yield observed_stream
            first_pass = observed_stream.first_pass_identity()
            second_pass = _second_pass_identity(descriptor)
            after = _fstat(descriptor)
            current = _lstat(path)
            if not stat.S_ISREG(after.st_mode) or not stat.S_ISREG(current.st_mode):
                raise FileObservationError("OBSERVED_FILE_IDENTITY_CHANGED")
            if _identity(opened) != _identity(after):
                raise FileObservationError("OBSERVED_FILE_CHANGED_DURING_READ")
            if _file_identity(after) != _file_identity(current):
                raise FileObservationError("OBSERVED_FILE_PATH_IDENTITY_CHANGED")
            if _identity(after) != _identity(current):
                raise FileObservationError("OBSERVED_FILE_PATH_METADATA_CHANGED")
            if first_pass != second_pass:
                raise FileObservationError("OBSERVED_FILE_CONTENT_CHANGED_DURING_READ")
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
            chunk = stream.read(min(_READ_BLOCK_BYTES, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                raise FileObservationError("OBSERVED_FILE_LIMIT_EXCEEDED")
    return b"".join(chunks)
