import subprocess

import pytest
import render_reader_docx as render


class TestCacheMatches:
    def test_matching_cache_hits(self):
        cache = {
            "docx_sha256": "abc",
            "scale": 2.0,
            "engine": "word",
        }
        assert render.cache_matches(cache, "abc", 2.0, "word") is True

    def test_changed_digest_misses(self):
        cache = {
            "docx_sha256": "abc",
            "scale": 2.0,
            "engine": "word",
        }
        assert render.cache_matches(cache, "def", 2.0, "word") is False

    def test_changed_scale_misses(self):
        cache = {
            "docx_sha256": "abc",
            "scale": 2.0,
            "engine": "word",
        }
        assert render.cache_matches(cache, "abc", 3.0, "word") is False

    def test_changed_engine_misses(self):
        cache = {
            "docx_sha256": "abc",
            "scale": 2.0,
            "engine": "word",
        }
        assert render.cache_matches(cache, "abc", 2.0, "soffice") is False

    def test_legacy_cache_without_scale_engine_misses(self):
        cache = {"docx_sha256": "abc"}
        assert render.cache_matches(cache, "abc", 2.0, "word") is False

    def test_empty_cache_misses(self):
        assert render.cache_matches({}, "abc", 2.0, "word") is False


class TestDiffPages:
    def test_all_changed_when_no_previous(self):
        order = ["page-01.png", "page-02.png"]
        current = {"page-01.png": "a", "page-02.png": "b"}
        changed, unchanged = render.diff_pages(order, current, None)
        assert changed == order
        assert unchanged == []

    def test_only_differing_pages_changed(self):
        order = ["page-01.png", "page-02.png", "page-03.png"]
        previous = {"page-01.png": "a", "page-02.png": "b", "page-03.png": "c"}
        current = {"page-01.png": "a", "page-02.png": "X", "page-03.png": "c"}
        changed, unchanged = render.diff_pages(order, current, previous)
        assert changed == ["page-02.png"]
        assert unchanged == ["page-01.png", "page-03.png"]

    def test_page_count_growth_flags_new_pages(self):
        order = ["page-01.png", "page-02.png"]
        previous = {"page-01.png": "a"}
        current = {"page-01.png": "a", "page-02.png": "b"}
        changed, unchanged = render.diff_pages(order, current, previous)
        assert changed == ["page-02.png"]
        assert unchanged == ["page-01.png"]


class TestArgparse:
    def test_jobs_flag_removed(self):
        with pytest.raises(SystemExit):
            render.parse_args(
                ["--docx", "x.docx", "--work-dir", "out", "--jobs", "4"]
            )

    def test_basic_args(self):
        args = render.parse_args(["--docx", "x.docx", "--work-dir", "out"])
        assert args.docx.name == "x.docx"


class TestConvertWithWordFailure:
    def test_failure_raises_friendly_error_and_cleans_up(self, monkeypatch):
        calls = []

        def fake_run(command, check=True, timeout=None, **kwargs):
            calls.append(command)
            if len(calls) == 1:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr(render.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="Word"):
            render.convert_with_word(render.Path("x.docx"), render.Path("x.pdf"))
        assert len(calls) >= 2

    def test_timeout_raises_friendly_error(self, monkeypatch):
        def fake_run(command, check=True, timeout=None, **kwargs):
            raise subprocess.TimeoutExpired(command, timeout)

        monkeypatch.setattr(render.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="Word"):
            render.convert_with_word(render.Path("x.docx"), render.Path("x.pdf"))


class TestRenderLock:
    def test_lock_path_lives_in_tempdir(self):
        path = render.render_lock_path()
        assert path.name == "xg-render.lock"
