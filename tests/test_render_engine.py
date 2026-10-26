"""``render_reader_docx.py`` engine-selection and cleanup acceptance tests.

Contract under test:

* ``XG_READING_SOFFICE`` pointing at a real file wins; a broken value raises
  ``FileNotFoundError`` instead of silently falling back.
* ``find_word_powershell`` is ``None`` on non-Windows, without PowerShell, and
  when Word COM is not registered.
* ``available_engine`` prefers LibreOffice and reports a clear error when no
  renderer exists.
* The Word cleanup script only stops *hidden* WINWORD processes that did not
  exist before this export attempt; it must never kill every hidden Word.
"""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import render_reader_docx as render
from _portability_helpers import SOFFICE_ENV


@pytest.fixture(autouse=True)
def _clear_soffice_env(monkeypatch):
    monkeypatch.delenv(SOFFICE_ENV, raising=False)


class TestFindSoffice:
    def test_environment_variable_pointing_at_a_file_is_used(
        self, tmp_path, monkeypatch
    ):
        soffice = tmp_path / "soffice.exe"
        soffice.write_bytes(b"fake")
        monkeypatch.setenv(SOFFICE_ENV, str(soffice))
        assert render.find_soffice() == soffice.resolve()

    def test_environment_variable_pointing_at_a_missing_file_raises(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(SOFFICE_ENV, str(tmp_path / "missing-soffice.exe"))
        with pytest.raises(FileNotFoundError, match="does not point to a file"):
            render.find_soffice()

    def test_environment_variable_pointing_at_a_directory_raises(
        self, tmp_path, monkeypatch
    ):
        directory = tmp_path / "soffice-dir"
        directory.mkdir()
        monkeypatch.setenv(SOFFICE_ENV, str(directory))
        with pytest.raises(FileNotFoundError, match="does not point to a file"):
            render.find_soffice()


class TestFindWordPowershell:
    def test_non_windows_returns_none(self, monkeypatch):
        monkeypatch.setattr(render, "sys", SimpleNamespace(platform="linux"))
        assert render.find_word_powershell() is None

    def test_windows_without_powershell_returns_none(self, monkeypatch):
        monkeypatch.setattr(render, "sys", SimpleNamespace(platform="win32"))
        monkeypatch.setattr(render, "shutil", SimpleNamespace(which=lambda name: None))
        assert render.find_word_powershell() is None

    def test_windows_without_registered_word_com_returns_none(self, monkeypatch):
        def open_key(*args, **kwargs):
            raise OSError("Word.Application is not registered")

        monkeypatch.setattr(render, "sys", SimpleNamespace(platform="win32"))
        monkeypatch.setattr(
            render,
            "shutil",
            SimpleNamespace(which=lambda name: "C:/Windows/powershell.exe"),
        )
        monkeypatch.setitem(
            sys.modules,
            "winreg",
            SimpleNamespace(HKEY_CLASSES_ROOT=object(), OpenKey=open_key),
        )
        assert render.find_word_powershell() is None

    def test_windows_with_registered_word_com_returns_powershell(self, monkeypatch):
        monkeypatch.setattr(render, "sys", SimpleNamespace(platform="win32"))
        monkeypatch.setattr(
            render,
            "shutil",
            SimpleNamespace(which=lambda name: "C:/Windows/powershell.exe"),
        )
        monkeypatch.setitem(
            sys.modules,
            "winreg",
            SimpleNamespace(
                HKEY_CLASSES_ROOT=object(),
                OpenKey=lambda *args, **kwargs: contextlib.nullcontext(),
            ),
        )
        assert render.find_word_powershell() == "C:/Windows/powershell.exe"


class TestAvailableEngine:
    def test_soffice_is_preferred(self, monkeypatch):
        monkeypatch.setattr(render, "find_soffice", lambda: Path("C:/soffice.exe"))
        monkeypatch.setattr(render, "find_word_powershell", lambda: "powershell.exe")
        assert render.available_engine() == "soffice"

    def test_word_is_used_when_soffice_is_absent(self, monkeypatch):
        monkeypatch.setattr(render, "find_soffice", lambda: None)
        monkeypatch.setattr(render, "find_word_powershell", lambda: "powershell.exe")
        assert render.available_engine() == "word"

    def test_no_renderer_raises_a_clear_error(self, monkeypatch):
        monkeypatch.setattr(render, "find_soffice", lambda: None)
        monkeypatch.setattr(render, "find_word_powershell", lambda: None)
        with pytest.raises(RuntimeError, match="No DOCX renderer"):
            render.available_engine()

    def test_configured_soffice_environment_selects_soffice(
        self, tmp_path, monkeypatch
    ):
        soffice = tmp_path / "soffice.exe"
        soffice.write_bytes(b"fake")
        monkeypatch.setenv(SOFFICE_ENV, str(soffice))
        monkeypatch.setattr(render, "find_word_powershell", lambda: "powershell.exe")
        assert render.available_engine() == "soffice"


class TestCleanupScript:
    def test_filters_on_hidden_window_and_the_keep_set(self):
        script = render.cleanup_script([1234, 5678])
        assert "$keep" in script
        assert "$_.MainWindowHandle -eq 0 -and $keep -notcontains $_.Id" in script
        assert "Get-Process WINWORD" in script
        assert "Stop-Process -Id $_.Id -Force" in script
        assert "1234" in script and "5678" in script
        assert str(os.getpid()) in script

    def test_never_unconditionally_stops_every_word_process(self):
        script = render.cleanup_script([])
        assert not re.search(
            r"Get-Process\s+WINWORD[^|]*\|\s*Stop-Process", script
        ), script

    def test_empty_keep_set_still_keeps_this_process(self):
        script = render.cleanup_script([])
        assert str(os.getpid()) in script
        assert "$keep = @(" in script

    def test_accepts_any_iterable_of_pids(self):
        script = render.cleanup_script(pid for pid in (11, 22))
        assert "11" in script and "22" in script

    def test_cleanup_word_processes_writes_the_keep_script(self, monkeypatch):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(render, "subprocess", SimpleNamespace(run=fake_run))
        render.cleanup_word_processes("powershell.exe", keep_pids=[99])
        assert len(calls) == 1
        command = calls[0]
        assert command[0] == "powershell.exe"
        assert "-Command" in command
        script = command[command.index("-Command") + 1]
        assert "99" in script
        assert "$keep -notcontains $_.Id" in script


class TestConvertWithWord:
    def test_failure_cleanup_keeps_preexisting_word_pids(self, monkeypatch):
        calls = []

        def fake_run(command, check=True, timeout=None, **kwargs):
            calls.append(command)
            if "-File" in command:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0, stdout="4321\n", stderr="")

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
        cleanup_script = cleanup[0][cleanup[0].index("-Command") + 1]
        assert "4321" in cleanup_script

    def test_without_powershell_raises_renderer_error(self, monkeypatch):
        monkeypatch.setattr(render, "find_word_powershell", lambda: None)
        with pytest.raises(RuntimeError, match="No DOCX renderer"):
            render.convert_with_word(Path("x.docx"), Path("x.pdf"))


class TestConvertDocxToPdf:
    def test_uses_soffice_when_available(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(render, "find_soffice", lambda: Path("C:/soffice.exe"))
        monkeypatch.setattr(
            render,
            "convert_with_soffice",
            lambda soffice, docx, pdf: calls.append((soffice, docx, pdf)),
        )
        engine = render.convert_docx_to_pdf(tmp_path / "a.docx", tmp_path / "a.pdf")
        assert engine == "soffice"
        assert len(calls) == 1

    def test_uses_word_when_soffice_is_absent(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(render, "find_soffice", lambda: None)
        monkeypatch.setattr(render, "find_word_powershell", lambda: "powershell.exe")
        monkeypatch.setattr(
            render,
            "convert_with_word",
            lambda docx, pdf: calls.append((docx, pdf)),
        )
        engine = render.convert_docx_to_pdf(tmp_path / "a.docx", tmp_path / "a.pdf")
        assert engine == "word"
        assert len(calls) == 1

    def test_without_renderer_raises_runtime_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(render, "find_soffice", lambda: None)
        monkeypatch.setattr(render, "find_word_powershell", lambda: None)
        with pytest.raises(RuntimeError, match="No DOCX renderer"):
            render.convert_docx_to_pdf(tmp_path / "a.docx", tmp_path / "a.pdf")


def test_render_main_without_renderer_exits_2_without_traceback(
    monkeypatch, tmp_path, capsys
):
    docx = tmp_path / "reader.docx"
    docx.write_bytes(b"fake docx")
    monkeypatch.setattr(render, "find_soffice", lambda: None)
    monkeypatch.setattr(render, "find_word_powershell", lambda: None)
    assert (
        render.main(
            ["--docx", str(docx), "--work-dir", str(tmp_path / "rendered")]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "No DOCX renderer" in captured.err
    assert "Traceback" not in captured.out + captured.err
