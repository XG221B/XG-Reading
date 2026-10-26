"""``check_environment.py`` (doctor) acceptance tests.

Contract under test:

* ``check_environment`` returns a JSON-serializable dict; ``ok`` is true only
  when there are no errors, and the CLI exits 0 only then.
* An unresolvable workspace root is an error that names ``Workspace root``.
* Missing dependencies, a missing/mismatched ``assets/reference.docx``, and a
  missing renderer (with ``--require-renderer``) are reported as errors.
* A missing renderer alone is only a warning by default.
* The CLI never prints a traceback, even on an unexpected crash.
"""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from types import SimpleNamespace

import check_environment as envcheck
import pytest
import render_reader_docx as render
from _portability_helpers import (
    OUTPUT_ROOT_ENV,
    SOFFICE_ENV,
    copy_skill,
    make_fake_repository,
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    monkeypatch.delenv(OUTPUT_ROOT_ENV, raising=False)
    monkeypatch.delenv(SOFFICE_ENV, raising=False)


@pytest.fixture
def skill_copy(tmp_path) -> Path:
    return copy_skill(tmp_path / "xg-reading")


@pytest.fixture
def output_root(tmp_path) -> Path:
    return tmp_path / "papers"


def test_standalone_skill_without_resolvable_root_reports_error(skill_copy):
    report = envcheck.check_environment(skill_copy)
    assert report["ok"] is False
    assert any("Workspace root" in error for error in report["errors"])
    assert report["repository_root"] is None
    assert report["outputs_root"] is None


def test_output_root_makes_the_environment_ok(skill_copy, output_root):
    report = envcheck.check_environment(skill_copy, output_root=output_root)
    assert report["ok"] is True, report["errors"]
    assert report["errors"] == []
    assert report["repository_root"] is None
    assert report["outputs_root"] == str(output_root.resolve())
    assert report["outputs_root_writable"]["ok"] is True
    assert report["template"]["ok"] is True
    # A missing renderer is only a warning, so `ok` must not depend on Office.
    # GitHub CI runners have neither Word nor necessarily LibreOffice; keep the
    # assertion capability-based and never assume a specific engine exists.
    engine = report["renderer"]["engine"]
    if engine is None:
        assert any("No DOCX renderer" in warning for warning in report["warnings"])
    else:
        assert engine in {"soffice", "word"}


def test_report_is_json_serializable_and_has_expected_fields(skill_copy, output_root):
    report = envcheck.check_environment(skill_copy, output_root=output_root)
    round_tripped = json.loads(json.dumps(report))
    assert round_tripped["ok"] == report["ok"]
    for field in (
        "ok",
        "python",
        "python_version",
        "python_ok",
        "files",
        "repository_root",
        "outputs_root",
        "outputs_root_writable",
        "config",
        "packages",
        "package_errors",
        "template",
        "renderer",
        "fonts",
        "errors",
        "warnings",
    ):
        assert field in report, field


def test_missing_dependency_is_explained(skill_copy, output_root, monkeypatch):
    real_import_module = envcheck.importlib.import_module

    def fake_import_module(name, package=None):
        if name == "pypdfium2":
            raise ImportError("simulated missing dependency")
        return real_import_module(name, package)

    monkeypatch.setattr(
        envcheck,
        "importlib",
        SimpleNamespace(import_module=fake_import_module, metadata=importlib.metadata),
    )
    report = envcheck.check_environment(skill_copy, output_root=output_root)
    assert report["ok"] is False
    assert "pypdfium2" in report["package_errors"]
    assert any("Dependency unavailable" in error for error in report["errors"])
    assert "pypdfium2" not in report["packages"]


def test_template_hash_mismatch_is_an_error(skill_copy, output_root):
    template = skill_copy / "assets" / "reference.docx"
    template.write_bytes(template.read_bytes() + b"\n# tampered\n")
    report = envcheck.check_environment(skill_copy, output_root=output_root)
    assert report["ok"] is False
    assert report["template"]["ok"] is False
    assert report["template"]["sha256"] != report["template"]["expected_sha256"]
    assert any(
        "does not match the retained template" in error for error in report["errors"]
    )


def test_missing_template_is_an_error(skill_copy, output_root):
    (skill_copy / "assets" / "reference.docx").unlink()
    report = envcheck.check_environment(skill_copy, output_root=output_root)
    assert report["ok"] is False
    assert report["template"]["ok"] is False
    assert any("Missing reference template" in error for error in report["errors"])


def test_missing_skill_file_is_an_error(skill_copy, output_root):
    (skill_copy / "SKILL.md").unlink()
    report = envcheck.check_environment(skill_copy, output_root=output_root)
    assert report["ok"] is False
    assert any("Missing skill file" in error for error in report["errors"])


def _hide_renderers(monkeypatch):
    monkeypatch.setattr(render, "find_soffice", lambda: None)
    monkeypatch.setattr(render, "find_word_powershell", lambda: None)


def test_missing_renderer_is_only_a_warning_by_default(
    skill_copy, output_root, monkeypatch
):
    _hide_renderers(monkeypatch)
    report = envcheck.check_environment(skill_copy, output_root=output_root)
    assert report["ok"] is True
    assert report["renderer"]["engine"] is None
    assert any("No DOCX renderer" in warning for warning in report["warnings"])
    assert not any("No DOCX renderer" in error for error in report["errors"])


def test_missing_renderer_is_an_error_when_required(skill_copy, output_root, monkeypatch):
    _hide_renderers(monkeypatch)
    report = envcheck.check_environment(
        skill_copy, output_root=output_root, require_renderer=True
    )
    assert report["ok"] is False
    assert any("No DOCX renderer" in error for error in report["errors"])


def test_repository_root_mode_resolves_repository_outputs(skill_copy, tmp_path):
    repo = make_fake_repository(tmp_path / "repo")
    report = envcheck.check_environment(skill_copy, repository_root=repo)
    assert report["ok"] is True, report["errors"]
    assert report["repository_root"] == str(repo.resolve())
    assert report["outputs_root"] == str((repo / "outputs").resolve())
    assert report["outputs_root_writable"]["ok"] is True


def test_conflicting_roots_are_reported_as_an_error(skill_copy, tmp_path, output_root):
    repo = make_fake_repository(tmp_path / "repo")
    report = envcheck.check_environment(
        skill_copy, output_root=output_root, repository_root=repo
    )
    assert report["ok"] is False
    assert any(
        "Workspace root" in error and "not both" in error
        for error in report["errors"]
    )


def test_cli_exits_zero_and_prints_json_on_success(tmp_path, capsys):
    output_root = tmp_path / "cli-output-root"
    assert envcheck.main(["--output-root", str(output_root)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["outputs_root"] == str(output_root.resolve())


def test_cli_unresolvable_root_exits_1_with_json(skill_copy, monkeypatch, capsys):
    monkeypatch.setattr(envcheck, "SKILL_DIR", skill_copy)
    assert envcheck.main([]) == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert any("Workspace root" in error for error in payload["errors"])
    assert "Traceback" not in captured.out + captured.err


def test_cli_never_tracebacks_on_unexpected_crash(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(envcheck, "check_environment", boom)
    assert envcheck.main([]) == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert any("Environment check crashed" in error for error in payload["errors"])
    assert "Traceback" not in captured.out + captured.err
