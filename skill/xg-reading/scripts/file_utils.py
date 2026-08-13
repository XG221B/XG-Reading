#!/usr/bin/env python3
"""Shared file utilities: atomic writes and lock helpers."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

LOCK_TIMEOUT_SECONDS = 120.0
LOCK_POLL_SECONDS = 1.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text via a temporary file plus rename so a crash never leaves a
    half-written target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + f".tmp{os.getpid()}")
    temp_path.write_text(content, encoding=encoding)
    os.replace(temp_path, path)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write bytes via a temporary file plus rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + f".tmp{os.getpid()}")
    temp_path.write_bytes(content)
    os.replace(temp_path, path)


def atomic_replace(source: Path, target: Path) -> None:
    """Atomically move a finished temporary file onto its final path."""
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)


def wait_for_lock(
    lock_path: Path,
    timeout: float = LOCK_TIMEOUT_SECONDS,
    poll: float = LOCK_POLL_SECONDS,
) -> bool:
    """Acquire an exclusive advisory lock file, waiting up to ``timeout``.

    Returns True when the lock was acquired. The caller must release it by
    deleting the lock file.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        return True


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
