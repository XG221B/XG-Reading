
import file_utils


class TestSha256File:
    def test_hash_stable(self, tmp_path):
        target = tmp_path / "data.bin"
        target.write_bytes(b"hello")
        first = file_utils.sha256_file(target)
        second = file_utils.sha256_file(target)
        assert first == second
        assert len(first) == 64

    def test_hash_differs_on_change(self, tmp_path):
        target = tmp_path / "data.bin"
        target.write_bytes(b"hello")
        first = file_utils.sha256_file(target)
        target.write_bytes(b"world")
        assert file_utils.sha256_file(target) != first


class TestAtomicWriteText:
    def test_writes_content(self, tmp_path):
        target = tmp_path / "out.json"
        file_utils.atomic_write_text(target, '{"a": 1}')
        assert target.read_text(encoding="utf-8") == '{"a": 1}'

    def test_no_temp_leftover(self, tmp_path):
        target = tmp_path / "out.json"
        file_utils.atomic_write_text(target, "data")
        leftovers = [p.name for p in tmp_path.iterdir() if ".tmp" in p.name]
        assert leftovers == []

    def test_overwrites_existing(self, tmp_path):
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        file_utils.atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "out.json"
        file_utils.atomic_write_text(target, "data")
        assert target.exists()


class TestAtomicWriteBytes:
    def test_writes_bytes(self, tmp_path):
        target = tmp_path / "img.png"
        file_utils.atomic_write_bytes(target, b"\x89PNG")
        assert target.read_bytes() == b"\x89PNG"


class TestLock:
    def test_acquire_and_release(self, tmp_path):
        lock = tmp_path / "render.lock"
        assert file_utils.wait_for_lock(lock, timeout=0.1, poll=0.01) is True
        assert lock.exists()
        file_utils.release_lock(lock)
        assert not lock.exists()

    def test_times_out_when_locked(self, tmp_path, monkeypatch):
        lock = tmp_path / "render.lock"
        lock.write_text("123", encoding="utf-8")
        monkeypatch.setattr(file_utils.time, "sleep", lambda _: None)
        assert file_utils.wait_for_lock(lock, timeout=0.05, poll=0.01) is False
        assert lock.exists()

    def test_release_missing_lock_ok(self, tmp_path):
        file_utils.release_lock(tmp_path / "absent.lock")
