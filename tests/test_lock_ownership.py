"""Regression tests for B05: owner-tracked advisory locks.

A lock is reclaimable only when its recorded owner is provably gone on this
host. Locks owned by a live process, another host, or an unreadable record are
never broken, and ``release_lock`` never deletes a lock it does not own.
"""

from __future__ import annotations

import json
import os
import socket

import file_utils as fus

DEAD_PID = 2**31 - 1


def write_lock(path, **overrides):
    record = {
        "schema_version": fus.LOCK_SCHEMA_VERSION,
        "pid": DEAD_PID,
        "token": "foreign-token",
        "host": socket.gethostname(),
        "created_at": 0.0,
    }
    record.update(overrides)
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def test_wait_for_lock_writes_an_owner_record(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    assert fus.wait_for_lock(lock_path, timeout=1.0, poll=0.01) is True
    record = fus.read_lock(lock_path)
    assert record is not None
    assert set(record) == {"schema_version", "pid", "token", "host", "created_at"}
    assert record["schema_version"] == fus.LOCK_SCHEMA_VERSION == 2
    assert record["pid"] == os.getpid()
    assert isinstance(record["token"], str) and len(record["token"]) == 32
    assert record["host"] == socket.gethostname()
    assert isinstance(record["created_at"], float)


def test_release_lock_removes_own_lock(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    assert fus.wait_for_lock(lock_path, timeout=1.0, poll=0.01) is True
    fus.release_lock(lock_path)
    assert not lock_path.exists()


def test_release_lock_keeps_another_process_lock(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    write_lock(lock_path, pid=DEAD_PID)
    fus.release_lock(lock_path)
    assert lock_path.exists()


def test_dead_owner_lock_is_reclaimed(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    write_lock(lock_path, pid=DEAD_PID)
    assert fus.lock_is_stale(lock_path) is True
    assert fus.wait_for_lock(lock_path, timeout=1.0, poll=0.01) is True
    record = fus.read_lock(lock_path)
    assert record is not None and record["pid"] == os.getpid()
    assert record["token"] != "foreign-token"


def test_live_owner_lock_is_not_broken(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    write_lock(lock_path, pid=os.getpid(), token="held-by-me")
    assert fus.lock_is_stale(lock_path) is False
    assert fus.wait_for_lock(lock_path, timeout=0.2, poll=0.01) is False
    record = fus.read_lock(lock_path)
    assert record is not None and record["token"] == "held-by-me"


def test_other_host_lock_is_not_broken(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    write_lock(lock_path, pid=DEAD_PID, host="another-host.example")
    assert fus.lock_is_stale(lock_path) is False
    assert fus.wait_for_lock(lock_path, timeout=0.2, poll=0.01) is False
    assert lock_path.exists()


def test_unreadable_lock_is_not_treated_as_stale(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    lock_path.write_text("{broken", encoding="utf-8")
    assert fus.read_lock(lock_path) is None
    assert fus.lock_is_stale(lock_path) is False
    assert fus.wait_for_lock(lock_path, timeout=0.2, poll=0.01) is False
    assert lock_path.exists()


def test_lock_without_integer_pid_is_not_stale(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    write_lock(lock_path, pid="not-a-pid")
    assert fus.lock_is_stale(lock_path) is False


def test_release_lock_is_noop_for_missing_file(tmp_path):
    lock_path = tmp_path / "workspace.lock"
    fus.release_lock(lock_path)
    assert not lock_path.exists()
