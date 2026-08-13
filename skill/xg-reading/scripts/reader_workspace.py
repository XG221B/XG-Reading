#!/usr/bin/env python3
"""Create and describe a durable XG-Reading paper workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_NAME = "xg-reading.local.json"
WORKSPACE_SCHEMA_VERSION = 1
INVALID_FOLDER_CHARS = r'[<>:"/\\|?*\x00-\x1f]'
WINDOWS_RESERVED_NAME = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)
YEAR_PREFIX = re.compile(r"^(?:19|20)\d{2}-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a durable per-paper workspace under an XG-Reading repository."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve-root", help="Print the configured repository root")
    resolve.add_argument("--repository-root", type=Path)
    resolve.add_argument("--skill-dir", type=Path, default=SKILL_DIR)

    init = subparsers.add_parser("init", help="Create or reuse one paper workspace")
    init.add_argument("--paper", required=True, type=Path, help="Main-paper PDF")
    init.add_argument("--title", help="Stable paper folder name; defaults to the PDF stem")
    init.add_argument("--supplement", action="append", type=Path, default=[])
    init.add_argument("--movie", action="append", type=Path, default=[])
    init.add_argument("--repository-root", type=Path)
    init.add_argument("--skill-dir", type=Path, default=SKILL_DIR)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_local_config(skill_dir: Path) -> Path | None:
    config_path = skill_dir / LOCAL_CONFIG_NAME
    if not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid local XG-Reading config: {config_path}") from error
    configured = data.get("repository_root")
    if not isinstance(configured, str) or not configured.strip():
        raise ValueError(f"repository_root is required in {config_path}")
    root = Path(configured).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Configured repository root does not exist: {root}")
    return root


def looks_like_repository_root(path: Path) -> bool:
    return (path / "skill" / "xg-reading" / "SKILL.md").exists() and (
        (path / ".git").exists() or (path / "README.md").exists()
    )


def find_repository_root(start: Path) -> Path | None:
    for candidate in (start.resolve(), *start.resolve().parents):
        if looks_like_repository_root(candidate):
            return candidate
    return None


def resolve_repository_root(explicit: Path | None, skill_dir: Path) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        if not looks_like_repository_root(root):
            raise ValueError(f"Not an XG-Reading repository root: {root}")
        return root

    configured = read_local_config(skill_dir.resolve())
    if configured is not None:
        if not looks_like_repository_root(configured):
            raise ValueError(
                f"Configured path is not an XG-Reading repository root: {configured}"
            )
        return configured

    discovered = find_repository_root(skill_dir)
    if discovered is not None:
        return discovered

    raise RuntimeError(
        "XG-Reading repository root could not be resolved. Configure "
        f"{LOCAL_CONFIG_NAME} beside SKILL.md or pass --repository-root. "
        "Artifacts must not be written to the installed Codex skill directory."
    )


def safe_folder_name(value: str) -> str:
    normalized = re.sub(INVALID_FOLDER_CHARS, "-", value).strip().rstrip(". ")
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        raise ValueError("Paper title does not contain a usable folder name")
    if WINDOWS_RESERVED_NAME.match(normalized):
        raise ValueError(f"Paper title is a reserved Windows name: {normalized}")
    return normalized[:140]


def file_record(path: Path, role: str) -> dict:
    resolved = path.expanduser().resolve()
    record = {"role": role, "path": str(resolved), "exists": resolved.exists()}
    if resolved.exists() and resolved.is_file():
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        record["sha256"] = digest.hexdigest()
        record["size_bytes"] = resolved.stat().st_size
    return record


def make_workspace_manifest(
    repository_root: Path,
    paper_dir: Path,
    title: str,
    paper: Path,
    supplements: Iterable[Path],
    movies: Iterable[Path],
) -> dict:
    sources = [file_record(paper, "main_paper")]
    sources.extend(file_record(item, "supplement") for item in supplements)
    sources.extend(file_record(item, "movie") for item in movies)
    process_dir = paper_dir / "process"
    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "updated_at": utc_now(),
        "paper_title": title,
        "repository_root": str(repository_root),
        "workspace": {
            "paper_dir": str(paper_dir),
            "final_docx": str(paper_dir / f"{title}论文逐图解读.docx"),
            "process_dir": str(process_dir),
            "content_json": str(process_dir / "content.json"),
            "figures_dir": str(process_dir / "figures"),
            "supplementary_dir": str(process_dir / "supplementary"),
            "movie_frames_dir": str(process_dir / "movie-frames"),
            "rendered_dir": str(process_dir / "rendered"),
            "audit_report": str(process_dir / "audit-report.json"),
        },
        "sources": sources,
    }


def compare_sources(previous_manifest: dict, current_sources: list[dict]) -> list[str]:
    """Warn when a source file's sha256 changed since the last init."""
    warnings: list[str] = []
    current_by_key = {
        (record.get("role"), record.get("path")): record
        for record in current_sources
    }
    for previous in previous_manifest.get("sources") or []:
        key = (previous.get("role"), previous.get("path"))
        current = current_by_key.get(key)
        if current is None:
            continue
        previous_hash = previous.get("sha256")
        current_hash = current.get("sha256")
        if previous_hash and current_hash and previous_hash != current_hash:
            warnings.append(
                f"{previous.get('role')} changed since the last init: "
                f"{previous.get('path')}"
            )
    return warnings


def initialize_workspace(args: argparse.Namespace) -> dict:
    repository_root = resolve_repository_root(args.repository_root, args.skill_dir)
    paper = args.paper.expanduser().resolve()
    if not paper.exists() or not paper.is_file():
        raise FileNotFoundError(f"Main paper does not exist: {paper}")
    title = safe_folder_name(args.title or paper.stem)
    if not YEAR_PREFIX.match(title):
        print(
            f"warning: paper folder name {title!r} does not follow the "
            "'年份-文章标题' convention (for example 2023-Autonomous ...); "
            "pass --title 'YYYY-<title>' to name the output folder accordingly.",
            file=sys.stderr,
        )
    paper_dir = repository_root / "outputs" / title
    process_dir = paper_dir / "process"
    for directory in (
        paper_dir,
        process_dir,
        process_dir / "figures",
        process_dir / "supplementary",
        process_dir / "movie-frames",
        process_dir / "rendered",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_path = process_dir / "source-manifest.json"
    manifest = make_workspace_manifest(
        repository_root,
        paper_dir,
        title,
        paper,
        args.supplement,
        args.movie,
    )
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = previous.get("created_at", manifest["updated_at"])
        for warning in compare_sources(previous, manifest["sources"]):
            print(warning, file=sys.stderr)
    else:
        manifest["created_at"] = manifest["updated_at"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    args = parse_args()
    if args.command == "resolve-root":
        root = resolve_repository_root(args.repository_root, args.skill_dir)
        print(json.dumps({"repository_root": str(root), "outputs_root": str(root / "outputs")}, ensure_ascii=True))
        return
    print(json.dumps(initialize_workspace(args), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
