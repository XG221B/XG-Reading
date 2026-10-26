"""CI workflow contract tests (E01).

These tests assert the documented CI guarantees rather than a past CI run:

* lint covers the whole repository (including ``skill/xg-reading/run.py``);
* Python 3.11 (declared minimum) and 3.12 are both tested;
* Windows runs the full suite;
* Ubuntu runs the pure-Python suite with real Office integration excluded;
* macOS is not claimed as verified;
* the declared dependency range and the CI-tested scope are recorded.

Passing these tests does not prove the workflow passed on GitHub, and the
platform/dependency matrix is intentionally not exhaustive.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

PYTHON_MATRIX = re.compile(r'python-version:\s*\[\s*"3\.11"\s*,\s*"3\.12"\s*\]')


def ci_text() -> str:
    return CI_YML.read_text(encoding="utf-8-sig")


def job_block(name: str) -> str:
    text = ci_text()
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"CI job {name!r} not found in {CI_YML}"
    return match.group(0)


class TestLintJob:
    def test_lint_runs_on_the_whole_repository(self):
        block = job_block("lint")
        assert "ruff check ." in block
        # The old lint command silently skipped run.py at the skill root.
        assert "ruff check skill/xg-reading/scripts tests" not in ci_text()

    def test_lint_installs_the_lint_dependencies(self):
        assert "requirements-dev.txt" in job_block("lint")


class TestPythonMatrix:
    def test_matrix_covers_minimum_and_current_python(self):
        assert PYTHON_MATRIX.search(ci_text()) is not None

    @pytest.mark.parametrize("job", ["test", "test-linux"])
    def test_each_test_job_uses_the_shared_matrix(self, job):
        block = job_block(job)
        assert "${{ matrix.python-version }}" in block
        assert PYTHON_MATRIX.search(block) is not None


class TestPlatformSplit:
    def test_windows_runs_on_windows_and_runs_the_full_suite(self):
        block = job_block("test")
        assert "runs-on: windows-latest" in block
        run_lines = [
            line.strip()
            for line in block.splitlines()
            if line.strip().startswith("run: pytest")
        ]
        assert run_lines == ["run: pytest tests -q"]

    def test_linux_runs_the_pure_python_suite_without_office_integration(self):
        block = job_block("test-linux")
        assert "runs-on: ubuntu-latest" in block
        assert "pytest tests -q -m" in block
        assert "not office_integration" in block
        assert "not windows_only" in block

    def test_ci_does_not_install_word_or_libreoffice(self):
        text = ci_text().lower()
        assert "choco install" not in text
        assert "apt-get install" not in text
        assert "winget install" not in text

    def test_macos_is_not_claimed_as_verified(self):
        text = ci_text()
        assert "runs-on: macos" not in text.lower()
        assert "No CI job runs on macOS" in text


class TestDependencyScope:
    def test_declared_dependency_bounds_are_recorded(self):
        text = ci_text()
        for bounds in (
            "python-docx>=1.1.2,<2.0",
            "Pillow>=10.0,<13.0",
            "pypdfium2>=4.30,<6.0",
            "pytest>=8.0",
            "ruff>=0.9",
        ):
            assert bounds in text, bounds

    def test_ci_states_only_resolved_versions_are_verified(self):
        text = ci_text()
        assert "not exhaustively verified" in text
        assert "only the versions resolved in those jobs are exercised" in text


class TestMarkers:
    @pytest.mark.parametrize("marker", ["office_integration", "windows_only"])
    def test_ci_exclusion_markers_are_registered(self, pytestconfig, marker):
        registered = "\n".join(pytestconfig.getini("markers"))
        assert marker in registered

    def test_current_suite_is_not_marked_platform_specific(self):
        # The Ubuntu job excludes only those markers; today it must still run
        # every test, so the full suite should not carry them.
        marker_usage = re.compile(r"@pytest\.mark\.(office_integration|windows_only)")
        test_files = sorted((REPO_ROOT / "tests").glob("test_*.py"))
        assert test_files
        for path in test_files:
            assert marker_usage.search(path.read_text(encoding="utf-8-sig")) is None, path
