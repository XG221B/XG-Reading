"""Regression tests for B03/B04/B07/B08: render safety and cache integrity.

* ``validate_pdf`` rejects empty/corrupt renderer output, and a LibreOffice
  staging directory is published only after validation.
* Word cleanup only targets hidden instances started after the attempt began.
* The render cache is keyed by schema, engine signature, PDF hash, and page
  hashes; ``diff_generations`` reports changed/unchanged/added/removed pages.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import render_reader_docx as render
from PIL import Image


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_valid_pdf(path, size=(60, 80)):
    Image.new("RGB", size, "white").save(path, format="PDF")


def make_work_dir(tmp_path, pages=("page-01.png", "page-02.png")):
    work_dir = tmp_path / "rendered"
    work_dir.mkdir()
    pdf_path = work_dir / "reader.pdf"
    write_valid_pdf(pdf_path)
    for index, name in enumerate(pages, start=1):
        Image.new("RGB", (20, 20), (index, 0, 0)).save(work_dir / name)
    return work_dir, pdf_path


def make_cache(work_dir, pdf_path, pages, *, digest="docx-digest"):
    return {
        "schema_version": render.RENDER_CACHE_SCHEMA_VERSION,
        "docx_sha256": digest,
        "pdf": pdf_path.name,
        "pdf_sha256": sha256(pdf_path),
        "pages": list(pages),
        "scale": 2.0,
        "engine": "word",
        "engine_signature": "word:fake",
        "page_hashes": {
            name: sha256(work_dir / name) for name in pages
        },
    }


class TestValidatePdf:
    def test_missing_pdf_is_rejected(self, tmp_path):
        with pytest.raises(RuntimeError, match="no usable PDF"):
            render.validate_pdf(tmp_path / "missing.pdf")

    def test_empty_pdf_is_rejected(self, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        with pytest.raises(RuntimeError, match="no usable PDF"):
            render.validate_pdf(empty)

    def test_corrupt_pdf_is_rejected(self, tmp_path):
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"not a pdf at all")
        with pytest.raises(RuntimeError, match="unreadable PDF"):
            render.validate_pdf(corrupt)

    def test_valid_pdf_reports_page_count(self, tmp_path):
        valid = tmp_path / "valid.pdf"
        write_valid_pdf(valid)
        assert render.validate_pdf(valid) == 1


class TestSofficeStaging:
    def test_success_without_pdf_does_not_reuse_old_file(self, tmp_path):
        pdf_path = tmp_path / "reader.pdf"
        pdf_path.write_bytes(b"OLD PDF BYTES")
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(render.subprocess, "run", fake_run)
            with pytest.raises(RuntimeError, match="produced no new PDF"):
                render.convert_with_soffice(
                    Path("soffice"), tmp_path / "doc.docx", pdf_path
                )
        finally:
            monkeypatch.undo()
        assert calls
        assert pdf_path.read_bytes() == b"OLD PDF BYTES"
        assert not list(tmp_path.glob("xg-soffice-*"))

    def test_invalid_staged_pdf_is_not_published(self, tmp_path):
        pdf_path = tmp_path / "reader.pdf"
        pdf_path.write_bytes(b"OLD PDF BYTES")

        def fake_run(command, **kwargs):
            staging = Path(command[command.index("--outdir") + 1])
            (staging / "doc.pdf").write_bytes(b"")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(render.subprocess, "run", fake_run)
            with pytest.raises(RuntimeError, match="no usable PDF"):
                render.convert_with_soffice(
                    Path("soffice"), tmp_path / "doc.docx", pdf_path
                )
        finally:
            monkeypatch.undo()
        assert pdf_path.read_bytes() == b"OLD PDF BYTES"
        assert not list(tmp_path.glob("xg-soffice-*"))

    def test_valid_staged_pdf_is_published(self, tmp_path):
        pdf_path = tmp_path / "reader.pdf"
        pdf_path.write_bytes(b"OLD PDF BYTES")

        def fake_run(command, **kwargs):
            staging = Path(command[command.index("--outdir") + 1])
            write_valid_pdf(staging / "doc.pdf")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(render.subprocess, "run", fake_run)
            render.convert_with_soffice(Path("soffice"), tmp_path / "doc.docx", pdf_path)
        finally:
            monkeypatch.undo()
        assert render.validate_pdf(pdf_path) == 1
        assert not list(tmp_path.glob("xg-soffice-*"))


class TestWordCleanup:
    def test_cleanup_without_start_time_has_no_start_filter(self):
        script = render.cleanup_script([111])
        assert "$keep = @(" in script
        assert "$keep -notcontains $_.Id" in script
        assert "StartTime" not in script

    def test_cleanup_with_start_time_filters_by_process_start(self):
        started_after = "2026-10-26T00:00:00+00:00"
        script = render.cleanup_script([111], started_after)
        assert f"$since = [datetime]::Parse('{started_after}')" in script
        assert "StartTime.ToUniversalTime() -ge $since" in script
        assert "$keep -notcontains $_.Id" in script

    def test_cleanup_word_processes_forwards_start_time(self, monkeypatch):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(render, "subprocess", SimpleNamespace(run=fake_run))
        render.cleanup_word_processes("powershell.exe", [99], "2026-10-26T00:00:00Z")
        script = calls[0][calls[0].index("-Command") + 1]
        assert "2026-10-26T00:00:00Z" in script
        assert "StartTime" in script
        assert "99" in script

    def test_failed_word_export_keeps_snapshot_pids_and_filters_start_time(
        self, monkeypatch
    ):
        calls = []

        def fake_run(command, check=True, timeout=None, **kwargs):
            calls.append(command)
            if "-File" in command:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(
                command, 0, stdout="4321\t2026-10-26T00:00:00Z\n", stderr=""
            )

        monkeypatch.setattr(render, "find_word_powershell", lambda: "powershell.exe")
        monkeypatch.setattr(
            render,
            "subprocess",
            SimpleNamespace(
                run=fake_run,
                CalledProcessError=subprocess.CalledProcessError,
                TimeoutExpired=subprocess.TimeoutExpired,
                SubprocessError=subprocess.SubprocessError,
            ),
        )
        with pytest.raises(RuntimeError, match="Word conversion failed"):
            render.convert_with_word(Path("x.docx"), Path("x.pdf"))
        cleanup = [
            call
            for call in calls
            if "-Command" in call and "$keep" in call[call.index("-Command") + 1]
        ]
        assert cleanup, "a failed export must attempt cleanup"
        script = cleanup[0][cleanup[0].index("-Command") + 1]
        assert "4321" in script
        assert re.search(r"\$since = \[datetime\]::Parse\('.+'\)", script)
        assert "StartTime.ToUniversalTime() -ge $since" in script


class TestCacheValid:
    @pytest.fixture
    def cached(self, tmp_path):
        work_dir, pdf_path = make_work_dir(tmp_path)
        cache = make_cache(work_dir, pdf_path, ["page-01.png", "page-02.png"])
        return work_dir, cache

    def assert_valid(self, work_dir, cache):
        return render.cache_valid(
            cache, work_dir, "docx-digest", 2.0, "word", "word:fake"
        )

    def test_valid_cache_is_accepted(self, cached):
        work_dir, cache = cached
        assert self.assert_valid(work_dir, cache) is True

    def test_non_object_cache_is_invalid(self, tmp_path):
        work_dir, _pdf = make_work_dir(tmp_path)
        assert render.cache_valid(
            [], work_dir, "d", 2.0, "word", "word:fake"
        ) is False

    def test_wrong_schema_is_invalid(self, cached):
        work_dir, cache = cached
        cache["schema_version"] = 2
        assert self.assert_valid(work_dir, cache) is False

    def test_wrong_docx_digest_is_invalid(self, cached):
        work_dir, cache = cached
        cache["docx_sha256"] = "other"
        assert self.assert_valid(work_dir, cache) is False

    def test_wrong_scale_is_invalid(self, cached):
        work_dir, cache = cached
        cache["scale"] = 3.0
        assert self.assert_valid(work_dir, cache) is False

    def test_wrong_engine_is_invalid(self, cached):
        work_dir, cache = cached
        cache["engine"] = "soffice"
        assert self.assert_valid(work_dir, cache) is False

    def test_wrong_engine_signature_is_invalid(self, cached):
        work_dir, cache = cached
        cache["engine_signature"] = "word:other"
        assert self.assert_valid(work_dir, cache) is False

    def test_missing_pdf_is_invalid(self, cached):
        work_dir, cache = cached
        (work_dir / cache["pdf"]).unlink()
        assert self.assert_valid(work_dir, cache) is False

    def test_changed_pdf_bytes_are_invalid(self, cached):
        work_dir, cache = cached
        (work_dir / cache["pdf"]).write_bytes(b"different pdf")
        assert self.assert_valid(work_dir, cache) is False

    def test_missing_page_file_is_invalid(self, cached):
        work_dir, cache = cached
        (work_dir / "page-02.png").unlink()
        assert self.assert_valid(work_dir, cache) is False

    def test_changed_page_bytes_are_invalid(self, cached):
        work_dir, cache = cached
        Image.new("RGB", (20, 20), "black").save(work_dir / "page-01.png")
        assert self.assert_valid(work_dir, cache) is False

    def test_empty_page_list_is_invalid(self, cached):
        work_dir, cache = cached
        cache["pages"] = []
        cache["page_hashes"] = {}
        assert self.assert_valid(work_dir, cache) is False

    def test_missing_page_hashes_are_invalid(self, cached):
        work_dir, cache = cached
        del cache["page_hashes"]
        assert self.assert_valid(work_dir, cache) is False


class TestDiffGenerations:
    def test_changed_unchanged_added_and_removed(self):
        previous_pages = ["page-01.png", "page-02.png", "page-03.png"]
        previous_hashes = {
            "page-01.png": "a",
            "page-02.png": "b",
            "page-03.png": "c",
        }
        pages = ["page-01.png", "page-02.png", "page-04.png"]
        hashes = {"page-01.png": "a", "page-02.png": "X", "page-04.png": "d"}
        diff = render.diff_generations(
            previous_pages, previous_hashes, pages, hashes
        )
        assert diff["changed"] == ["page-02.png", "page-04.png"]
        assert diff["unchanged"] == ["page-01.png"]
        assert diff["added"] == ["page-04.png"]
        assert diff["removed"] == ["page-03.png"]

    def test_first_render_marks_every_page_changed(self):
        diff = render.diff_generations([], {}, ["page-01.png"], {"page-01.png": "a"})
        assert diff["changed"] == ["page-01.png"]
        assert diff["unchanged"] == []
        assert diff["added"] == ["page-01.png"]
        assert diff["removed"] == []

    def test_page_count_shrink_reports_removed(self):
        diff = render.diff_generations(
            ["page-01.png", "page-02.png"],
            {"page-01.png": "a", "page-02.png": "b"},
            ["page-01.png"],
            {"page-01.png": "a"},
        )
        assert diff["changed"] == []
        assert diff["unchanged"] == ["page-01.png"]
        assert diff["removed"] == ["page-02.png"]


class TestRenderMainCache:
    def make_docx(self, tmp_path):
        docx_path = tmp_path / "reader.docx"
        docx_path.write_bytes(b"fake docx bytes")
        return docx_path

    def test_valid_cache_is_used_without_conversion(self, tmp_path, monkeypatch, capsys):
        work_dir, pdf_path = make_work_dir(tmp_path)
        docx_path = self.make_docx(tmp_path)
        cache = make_cache(work_dir, pdf_path, ["page-01.png", "page-02.png"])
        cache["docx_sha256"] = sha256(docx_path)
        render.save_cache(work_dir, cache)
        monkeypatch.setattr(render, "available_engine", lambda: "word")
        monkeypatch.setattr(render, "engine_signature", lambda engine: "word:fake")

        def fail_conversion(*args, **kwargs):
            raise AssertionError("a valid cache must not trigger a conversion")

        monkeypatch.setattr(render, "convert_docx_to_pdf", fail_conversion)
        assert render.main(["--docx", str(docx_path), "--work-dir", str(work_dir)]) == 0
        captured = capsys.readouterr()
        assert "cached" in captured.out
        assert "unchanged" in captured.out
        assert not (work_dir / render.WORKSPACE_LOCK_NAME).exists()

    def test_invalid_cache_rebuilds_and_records_generation(
        self, tmp_path, monkeypatch, capsys
    ):
        work_dir, pdf_path = make_work_dir(tmp_path)
        docx_path = self.make_docx(tmp_path)
        cache = make_cache(work_dir, pdf_path, ["page-01.png", "page-02.png"])
        cache["docx_sha256"] = sha256(docx_path)
        render.save_cache(work_dir, cache)
        # Corrupt one cached page so the cache is invalid and a re-render runs.
        Image.new("RGB", (20, 20), "black").save(work_dir / "page-01.png")

        monkeypatch.setattr(render, "available_engine", lambda: "word")
        monkeypatch.setattr(render, "engine_signature", lambda engine: "word:fake")

        def fake_convert(document_path, target_pdf):
            write_valid_pdf(target_pdf)
            return "word"

        def fake_render_pages(pdf, work, scale):
            names = ["page-01.png", "page-02.png"]
            for index, name in enumerate(names, start=1):
                Image.new("RGB", (20, 20), (index, 1, 1)).save(work / name)
            return names

        monkeypatch.setattr(render, "convert_docx_to_pdf", fake_convert)
        monkeypatch.setattr(render, "render_pages", fake_render_pages)
        assert render.main(["--docx", str(docx_path), "--work-dir", str(work_dir)]) == 0
        captured = capsys.readouterr()
        assert "converted reader.pdf with word" in captured.out
        assert "changed" in captured.out

        saved = json.loads((work_dir / render.CACHE_NAME).read_text(encoding="utf-8"))
        assert saved["schema_version"] == render.RENDER_CACHE_SCHEMA_VERSION == 3
        assert saved["pdf_sha256"] == sha256(pdf_path)
        assert saved["engine_signature"] == "word:fake"
        assert set(saved["page_hashes"]) == {"page-01.png", "page-02.png"}
        assert not (work_dir / render.WORKSPACE_LOCK_NAME).exists()
        assert not render.render_lock_path().exists()

    def test_workspace_lock_failure_returns_error(self, tmp_path, monkeypatch, capsys):
        work_dir = tmp_path / "rendered"
        work_dir.mkdir()
        docx_path = self.make_docx(tmp_path)
        monkeypatch.setattr(render, "wait_for_lock", lambda *args, **kwargs: False)
        assert render.main(["--docx", str(docx_path), "--work-dir", str(work_dir)]) == 2
        captured = capsys.readouterr()
        assert "workspace lock" in captured.err

    def test_converter_lock_failure_returns_error(self, tmp_path, monkeypatch, capsys):
        work_dir = tmp_path / "rendered"
        work_dir.mkdir()
        docx_path = self.make_docx(tmp_path)
        monkeypatch.setattr(render, "available_engine", lambda: "word")
        monkeypatch.setattr(render, "engine_signature", lambda engine: "word:fake")

        def fake_wait(path, *args, **kwargs):
            return path.parent == work_dir.resolve()

        monkeypatch.setattr(render, "wait_for_lock", fake_wait)
        assert render.main(["--docx", str(docx_path), "--work-dir", str(work_dir)]) == 2
        captured = capsys.readouterr()
        assert "still converting" in captured.err
        # the workspace lock must be released even when the converter lock fails
        assert not (work_dir / render.WORKSPACE_LOCK_NAME).exists()
