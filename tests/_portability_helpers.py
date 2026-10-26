"""Shared helpers for the portability / acceptance tests.

This module is imported by the ``test_*.py`` files in this directory; pytest
does not collect it. Everything here writes only under caller-supplied
``tmp_path`` trees, never into the real repository ``outputs/``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SKILL_DIR = REPO_ROOT / "skill" / "xg-reading"
SCRIPTS_DIR = SKILL_DIR / "scripts"
OUTPUT_ROOT_ENV = "XG_READING_OUTPUT_ROOT"
SOFFICE_ENV = "XG_READING_SOFFICE"

_SKILL_COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.py[cod]",
    "*.local.json",
    # Transient atomic-write/editor scratch files can appear in the skill tree
    # while the repository is being edited; never copy or chase them.
    ".*.tmpdir",
    "*.tmp*",
)


def copy_skill(destination: Path) -> Path:
    """Copy the installed skill tree into *destination* like a standalone user."""
    shutil.copytree(SKILL_DIR, destination, ignore=_SKILL_COPY_IGNORE)
    return destination


def make_minimal_skill(skill_dir: Path) -> Path:
    """Create the smallest tree ``run.py`` can dispatch from.

    Copies ``run.py`` plus every script module so that a new intra-scripts
    import (for example ``file_utils``) does not silently break the standalone
    copy; no resources, templates, or references are needed for workspace
    commands.
    """
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SKILL_DIR / "run.py", skill_dir / "run.py")
    for script in sorted(SCRIPTS_DIR.glob("*.py")):
        shutil.copy2(script, skill_dir / "scripts" / script.name)
    return skill_dir


def make_fake_repository(root: Path) -> Path:
    """Build a directory that ``looks_like_repository_root`` accepts."""
    skill = root / "skill" / "xg-reading"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("# fake standalone skill\n", encoding="utf-8")
    (root / "README.md").write_text("# fake repository\n", encoding="utf-8")
    return root


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Copy the environment without XG-Reading overrides, then add *extra*."""
    env = dict(os.environ)
    env.pop(OUTPUT_ROOT_ENV, None)
    env.pop(SOFFICE_ENV, None)
    if extra:
        env.update(extra)
    return env


def run_cli(
    args: list[str],
    *,
    skill_dir: Path = SKILL_DIR,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run ``run.py`` with the interpreter running the tests."""
    return subprocess.run(
        [sys.executable, "-B", str(Path(skill_dir) / "run.py"), *[str(arg) for arg in args]],
        cwd=str(cwd) if cwd is not None else None,
        env=clean_env(env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def parse_json_stdout(result: subprocess.CompletedProcess) -> dict:
    """Parse a CLI stdout payload and assert it is a JSON object."""
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise AssertionError(f"CLI stdout is not a JSON object: {result.stdout!r}")
    return payload


def load_script_module(path: Path, name: str):
    """Import a helper script by file path (the scripts are not a package)."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
