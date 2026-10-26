#!/usr/bin/env python3
"""Read-only environment diagnostics for XG-Reading.

Reports interpreter, dependencies, resolved workspace roots, template hash,
renderer, fonts, and output-root writability as JSON. A passing diagnosis only
means the toolkit is usable; it does not mean a paper passed audit or rendered
page inspection.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path

from file_utils import sha256_file
from reader_workspace import (
    LOCAL_CONFIG_NAME,
    OUTPUT_ROOT_ENV,
    SKILL_DIR,
    load_local_config,
    resolve_workspace_roots,
)

PACKAGES = {"docx": "python-docx", "PIL": "Pillow", "pypdfium2": "pypdfium2"}
REQUIRED_FILES = ("SKILL.md", "assets/reference.docx", "run.py")
REQUIRED_SCRIPTS = (
    "reader_workspace.py",
    "check_environment.py",
    "extract_figures_batch.py",
    "preflight_content.py",
    "build_reader_docx.py",
    "audit_reader_docx.py",
    "render_reader_docx.py",
)
MIN_PYTHON = (3, 11)


def check_write_access(directory: Path) -> dict:
    """Probe the nearest existing directory for writability without leaving files."""
    target = directory
    while not target.exists():
        if target.parent == target:
            return {
                "ok": False,
                "checked": str(directory),
                "error": "No existing parent directory",
            }
        target = target.parent
    if not target.is_dir():
        return {"ok": False, "checked": str(target), "error": "Not a directory"}
    try:
        with tempfile.TemporaryDirectory(prefix=".xg-doctor-", dir=target):
            pass
    except OSError as error:
        return {"ok": False, "checked": str(target), "error": str(error)}
    return {"ok": True, "checked": str(target)}


def check_fonts() -> dict:
    if sys.platform == "win32":
        fonts_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        required = {"华文中宋": "STZHONGS.TTF", "Times New Roman": "times.ttf"}
        missing = [
            family for family, filename in required.items() if not (fonts_dir / filename).exists()
        ]
        return {"checked_dir": str(fonts_dir), "missing": missing}
    return {
        "checked_dir": None,
        "missing": [],
        "note": "Verify 华文中宋 and Times New Roman are installed before inspecting pages",
    }


def check_template(skill_dir: Path, errors: list[str], warnings: list[str]) -> dict:
    path = skill_dir / "assets" / "reference.docx"
    info: dict = {"path": str(path), "sha256": None, "expected_sha256": None, "ok": False}
    if not path.is_file():
        errors.append(f"Missing reference template: {path}")
        return info
    try:
        info["sha256"] = sha256_file(path)
    except OSError as error:
        errors.append(f"Reference DOCX cannot be hashed: {error}")
        return info
    try:
        from build_reader_docx import EXPECTED_TEMPLATE_SHA256
        from docx import Document
    except Exception as error:
        warnings.append(f"Cannot verify the retained template without python-docx: {error}")
        return info
    info["expected_sha256"] = EXPECTED_TEMPLATE_SHA256
    if info["sha256"].lower() != EXPECTED_TEMPLATE_SHA256.lower():
        errors.append(
            "Reference DOCX does not match the retained template SHA-256; "
            "visual output is not protected"
        )
    else:
        info["ok"] = True
    try:
        Document(path)
    except Exception as error:
        errors.append(f"Reference DOCX cannot be opened: {error}")
    return info


def check_renderer(
    require_renderer: bool, packages_ok: bool, errors: list[str], warnings: list[str]
) -> dict:
    info: dict = {"engine": None, "soffice": None}
    if not packages_ok:
        message = "Renderer check needs python-docx, Pillow, and pypdfium2"
        (errors if require_renderer else warnings).append(message)
        return info
    try:
        import render_reader_docx as render

        soffice = render.find_soffice()
        info["soffice"] = str(soffice) if soffice is not None else None
        info["engine"] = render.available_engine()
    except (OSError, RuntimeError, ImportError) as error:
        (errors if require_renderer else warnings).append(str(error))
    return info


def check_environment(
    skill_dir: Path = SKILL_DIR,
    output_root: Path | None = None,
    repository_root: Path | None = None,
    require_renderer: bool = False,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    skill_dir = Path(skill_dir).expanduser().resolve()

    python_ok = sys.version_info >= MIN_PYTHON
    if not python_ok:
        errors.append(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; "
            f"this interpreter is {sys.version.split()[0]}"
        )

    files: dict[str, bool] = {}
    for relative in (*REQUIRED_FILES, *(f"scripts/{name}" for name in REQUIRED_SCRIPTS)):
        present = (skill_dir / relative).is_file()
        files[relative] = present
        if not present:
            errors.append(f"Missing skill file: {skill_dir / relative}")

    packages: dict[str, str] = {}
    package_errors: dict[str, str] = {}
    for module, distribution in PACKAGES.items():
        try:
            importlib.import_module(module)
            packages[distribution] = importlib.metadata.version(distribution)
        except Exception as error:
            package_errors[distribution] = f"{type(error).__name__}: {error}"
    errors.extend(
        f"Dependency unavailable: {distribution} ({message})"
        for distribution, message in package_errors.items()
    )

    roots: dict = {"repository_root": None, "outputs_root": None}
    try:
        repository, outputs = resolve_workspace_roots(repository_root, output_root, skill_dir)
        roots = {
            "repository_root": str(repository) if repository is not None else None,
            "outputs_root": str(outputs),
        }
    except (OSError, ValueError, RuntimeError) as error:
        errors.append(f"Workspace root: {error}")

    writable = None
    if roots["outputs_root"]:
        writable = check_write_access(Path(roots["outputs_root"]))
        if not writable["ok"]:
            errors.append(f"Output root is not writable: {writable['error']}")

    config: dict = {"path": str(skill_dir / LOCAL_CONFIG_NAME), "present": False}
    try:
        config["present"] = (skill_dir / LOCAL_CONFIG_NAME).exists()
        if config["present"]:
            config["keys"] = sorted(load_local_config(skill_dir))
    except (OSError, ValueError) as error:
        warnings.append(f"Local config could not be parsed: {error}")

    template = check_template(skill_dir, errors, warnings)
    renderer = check_renderer(require_renderer, not package_errors, errors, warnings)
    fonts = check_fonts()
    if fonts["missing"]:
        warnings.append(
            "Required fonts are not installed: " + ", ".join(fonts["missing"])
        )

    return {
        "ok": not errors,
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "python_ok": python_ok,
        "minimum_python": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
        "skill_dir": str(skill_dir),
        "files": files,
        "repository_root": roots["repository_root"],
        "outputs_root": roots["outputs_root"],
        "outputs_root_writable": writable,
        "config": config,
        "packages": packages,
        "package_errors": package_errors,
        "template": template,
        "renderer": renderer,
        "fonts": fonts,
        "output_root_env": OUTPUT_ROOT_ENV,
        "errors": errors,
        "warnings": warnings,
        "note": "Availability checks do not replace DOCX audit or rendered-page inspection.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--require-renderer", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = check_environment(
            SKILL_DIR, args.output_root, args.repository_root, args.require_renderer
        )
    except Exception as error:
        report = {
            "ok": False,
            "errors": [f"Environment check crashed: {type(error).__name__}: {error}"],
            "warnings": [],
            "note": "Availability checks do not replace DOCX audit or rendered-page inspection.",
        }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
