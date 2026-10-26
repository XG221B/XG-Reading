#!/usr/bin/env python3
"""Shared file utilities: atomic writes and owner-tracked lock files."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import uuid
from pathlib import Path

LOCK_TIMEOUT_SECONDS = 120.0
LOCK_POLL_SECONDS = 1.0
LOCK_SCHEMA_VERSION = 2


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


def pid_alive(pid: int) -> bool:
    """Best-effort liveness probe that never signals another process.

    POSIX uses signal 0. Windows uses OpenProcess, because ``os.kill`` on
    Windows would terminate the target for most signal numbers.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, pid
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except (AttributeError, OSError):
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_record() -> dict:
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "pid": os.getpid(),
        "token": uuid.uuid4().hex,
        "host": socket.gethostname(),
        "created_at": time.time(),
    }


def read_lock(lock_path: Path) -> dict | None:
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def lock_is_stale(lock_path: Path) -> bool:
    """True only when the recorded owner is provably gone on this host.

    An unreadable lock is not treated as stale, and a lock from another host is
    never reclaimed, because ownership cannot be proven.
    """
    record = read_lock(lock_path)
    if record is None:
        return False
    pid = record.get("pid")
    host = record.get("host")
    if not isinstance(pid, int):
        return False
    if isinstance(host, str) and host and host != socket.gethostname():
        return False
    return not pid_alive(pid)


def wait_for_lock(
    lock_path: Path,
    timeout: float = LOCK_TIMEOUT_SECONDS,
    poll: float = LOCK_POLL_SECONDS,
) -> bool:
    """Acquire an exclusive advisory lock file, waiting up to ``timeout``.

    Returns True when the lock was acquired. The caller must release it with
    :func:`release_lock`. A lock whose recorded owner has exited is reclaimed;
    a lock held by a live or unverifiable owner is waited on instead of broken.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if lock_is_stale(lock_path):
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(_lock_record(), stream)
        return True


def release_lock(lock_path: Path) -> None:
    """Release a lock only when this process created it."""
    record = read_lock(lock_path)
    if record is not None and record.get("pid") != os.getpid():
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
