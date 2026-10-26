#!/usr/bin/env python3
"""Create and describe a durable XG-Reading paper workspace.

The workspace can live in an XG-Reading repository (``<repo>/outputs``) or in a
plain project directory supplied by an agent. Root resolution never creates
directories; only ``init`` does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from file_utils import atomic_write_text, release_lock, wait_for_lock

SKILL_DIR = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_NAME = "xg-reading.local.json"
OUTPUT_ROOT_ENV = "XG_READING_OUTPUT_ROOT"
WORKSPACE_SCHEMA_VERSION = 2
INVALID_FOLDER_CHARS = r'[<>:"/\\|?*\x00-\x1f]'
WINDOWS_RESERVED_NAME = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)
YEAR_PREFIX = re.compile(r"^(?:19|20)\d{2}-")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a durable per-paper workspace in a repository or explicit output root."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser(
        "resolve-root", help="Resolve the output root without creating directories"
    )
    resolve.add_argument("--repository-root", type=Path)
    resolve.add_argument("--output-root", type=Path, help="Output directory; no repository required")
    resolve.add_argument("--skill-dir", type=Path, default=SKILL_DIR)

    init = subparsers.add_parser("init", help="Create or reuse one paper workspace")
    init.add_argument("--paper", required=True, type=Path, help="Main-paper PDF")
    init.add_argument("--title", help="Stable paper folder name; defaults to the PDF stem")
    init.add_argument("--supplement", action="append", type=Path, default=[])
    init.add_argument("--movie", action="append", type=Path, default=[])
    init.add_argument("--repository-root", type=Path)
    init.add_argument("--output-root", type=Path, help="Output directory; no repository required")
    init.add_argument("--skill-dir", type=Path, default=SKILL_DIR)
    return parser.parse_args(argv)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def clean_folder_text(value: object) -> str:
    """Normalise a recorded title for case-insensitive workspace comparison."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def local_config_path(skill_dir: Path) -> Path:
    return skill_dir / LOCAL_CONFIG_NAME


def load_local_config(skill_dir: Path) -> dict:
    """Read the optional skill-local config; UTF-8 with or without a BOM."""
    config_path = local_config_path(skill_dir)
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid local XG-Reading config: {config_path}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Local XG-Reading config must be a JSON object: {config_path}")
    return data


def config_path_value(value: str, skill_dir: Path) -> Path:
    """Resolve a config path; relative values stay anchored to the config file."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = local_config_path(skill_dir).parent / path
    return path.resolve()


def read_local_config(skill_dir: Path) -> Path | None:
    data = load_local_config(skill_dir)
    if not data:
        return None
    config_file = local_config_path(skill_dir)
    configured = data.get("repository_root")
    if not isinstance(configured, str) or not configured.strip():
        raise ValueError(
            f"repository_root is required in {config_file} when output_root is not set"
        )
    root = config_path_value(configured, skill_dir)
    if not root.exists():
        raise FileNotFoundError(
            f"Configured repository root does not exist: {root}. "
            "Pass --output-root to use a project directory, or update the local config."
        )
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
        "XG-Reading output root could not be resolved. Pass --output-root for a "
        f"project directory, set {OUTPUT_ROOT_ENV}, configure {LOCAL_CONFIG_NAME} "
        "beside SKILL.md, or pass --repository-root. Artifacts must never be "
        "written to the skill directory."
    )


def validate_output_root(path: Path, skill_dir: Path) -> Path:
    root = path.expanduser().resolve()
    if root.is_relative_to(skill_dir.resolve()):
        raise ValueError(
            f"Output root must be outside the skill directory: {root}. "
            "Artifacts must never be written to the skill directory."
        )
    if root.exists() and not root.is_dir():
        raise ValueError(f"Output root is not a directory: {root}")
    return root


def resolve_workspace_roots(
    repository_root: Path | None, output_root: Path | None, skill_dir: Path
) -> tuple[Path | None, Path]:
    """Resolve ``(repository_root | None, outputs_root)`` without creating dirs.

    Priority: explicit options, then environment variable, then skill-local
    config, then repository discovery. Explicit options always win, so a stale
    config can be overridden instead of silently redirecting artifacts.
    """
    if output_root is not None and repository_root is not None:
        raise ValueError("Choose --output-root or --repository-root, not both")
    skill_dir = skill_dir.expanduser().resolve()
    if output_root is not None:
        return None, validate_output_root(output_root, skill_dir)
    if repository_root is not None:
        root = resolve_repository_root(repository_root, skill_dir)
        return root, validate_output_root(root / "outputs", skill_dir)
    environment_root = os.environ.get(OUTPUT_ROOT_ENV, "").strip()
    if environment_root:
        candidate = Path(environment_root).expanduser()
        if not candidate.is_absolute():
            raise ValueError(
                f"{OUTPUT_ROOT_ENV} must be an absolute path to stay independent of the "
                f"current directory: {environment_root}"
            )
        return None, validate_output_root(candidate, skill_dir)
    config = load_local_config(skill_dir)
    if "output_root" in config:
        configured = config["output_root"]
        if not isinstance(configured, str) or not configured.strip():
            raise ValueError(
                f"output_root must be a non-empty path in {local_config_path(skill_dir)}"
            )
        return None, validate_output_root(
            config_path_value(configured, skill_dir), skill_dir
        )
    root = resolve_repository_root(None, skill_dir)
    return root, validate_output_root(root / "outputs", skill_dir)


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
    repository_root: Path | None,
    paper_dir: Path,
    title: str,
    sources: list[dict],
    paper_identity: str | None,
    source_revision: str | None,
    source_changes: dict,
    stale: bool,
    stale_reasons: list[str],
) -> dict:
    process_dir = paper_dir / "process"
    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "updated_at": utc_now(),
        "paper_title": title,
        "repository_root": str(repository_root) if repository_root is not None else None,
        "outputs_root": str(paper_dir.parent),
        "paper_identity": paper_identity,
        "source_revision": source_revision,
        "source_changes": source_changes,
        "stale": stale,
        "stale_reasons": stale_reasons,
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


def build_sources(
    paper: Path,
    supplements: Iterable[Path],
    movies: Iterable[Path],
    previous: dict | None,
) -> list[dict]:
    """Build source records, preserving previously registered supplements.

    Re-running ``init`` without ``--supplement``/``--movie`` must not silently
    drop sources that were registered earlier. A role is replaced only when the
    caller explicitly passes at least one file for that role.
    """
    sources = [file_record(paper, "main_paper")]

    def collect(role: str, provided: Iterable[Path]) -> list[dict]:
        provided_list = list(provided)
        if provided_list:
            return [file_record(item, role) for item in provided_list]
        preserved = []
        for record in (previous or {}).get("sources") or []:
            if not isinstance(record, dict) or record.get("role") != role:
                continue
            raw_path = record.get("path")
            if not raw_path:
                continue
            refreshed = file_record(Path(str(raw_path)), role)
            if not refreshed.get("sha256") and record.get("sha256"):
                refreshed["sha256"] = record["sha256"]
            preserved.append(refreshed)
        return preserved

    sources.extend(collect("supplement", supplements))
    sources.extend(collect("movie", movies))
    return sources


def compare_source_revisions(previous: dict | None, current: list[dict]) -> dict:
    """Describe added, removed, relocated, and content-changed sources."""
    changes: dict[str, list] = {
        "added": [],
        "removed": [],
        "relocated": [],
        "changed": [],
    }
    previous_sources = [
        record for record in (previous or {}).get("sources") or [] if isinstance(record, dict)
    ]
    previous_by_key = {
        (record.get("role"), record.get("path")): record for record in previous_sources
    }
    current_by_key = {
        (record.get("role"), record.get("path")): record for record in current
    }
    relocation_targets: set[tuple] = set()
    for key, record in previous_by_key.items():
        if key in current_by_key:
            continue
        role, path = key
        relocation = next(
            (
                (other_key, other)
                for other_key, other in current_by_key.items()
                if other_key not in previous_by_key
                and other_key[0] == role
                and other.get("sha256")
                and other.get("sha256") == record.get("sha256")
            ),
            None,
        )
        if relocation is not None:
            other_key, other = relocation
            relocation_targets.add(other_key)
            changes["relocated"].append(
                {"role": role, "from": path, "to": other.get("path")}
            )
        else:
            changes["removed"].append({"role": role, "path": path})
    for key, record in current_by_key.items():
        old = previous_by_key.get(key)
        if (
            old is not None
            and old.get("exists", True)
            and not record.get("exists", True)
        ):
            # Registered source that is still recorded but no longer accessible.
            changes["removed"].append({"role": key[0], "path": key[1]})
            continue
        if key not in previous_by_key and key not in relocation_targets:
            changes["added"].append({"role": key[0], "path": key[1]})
    for key, record in current_by_key.items():
        old = previous_by_key.get(key)
        if not record.get("exists", True):
            continue
        if (
            old is not None
            and old.get("sha256")
            and record.get("sha256")
            and old["sha256"] != record["sha256"]
        ):
            changes["changed"].append({"role": key[0], "path": key[1]})
    return changes


def initialize_workspace(args: argparse.Namespace) -> dict:
    repository_root, outputs_root = resolve_workspace_roots(
        args.repository_root, args.output_root, args.skill_dir
    )
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
    paper_dir = outputs_root / title
    process_dir = paper_dir / "process"
    manifest_path = process_dir / "source-manifest.json"
    if paper_dir.exists() and not manifest_path.exists() and any(paper_dir.iterdir()):
        raise ValueError(
            f"Workspace exists without a source manifest: {paper_dir}. "
            "Choose a different --title or output root instead of overwriting "
            "unmanaged files."
        )
    for directory in (
        paper_dir,
        process_dir,
        process_dir / "figures",
        process_dir / "supplementary",
        process_dir / "movie-frames",
        process_dir / "rendered",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    lock_path = paper_dir / ".workspace.lock"
    if not wait_for_lock(lock_path):
        raise RuntimeError(f"Another init holds this workspace lock: {lock_path}")
    try:
        previous = None
        if manifest_path.exists():
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(previous, dict):
                raise ValueError(f"Existing source manifest is not a JSON object: {manifest_path}")
            previous_title = clean_folder_text(previous.get("paper_title"))
            if previous_title and previous_title.casefold() != title.casefold():
                raise ValueError(
                    f"Workspace title conflict: existing {previous_title!r} vs requested "
                    f"{title!r}. Use a different --title or an explicit workspace."
                )
        sources = build_sources(paper, args.supplement, args.movie, previous)
        main_record = next(
            (record for record in sources if record.get("role") == "main_paper"), {}
        )
        changes = (
            compare_source_revisions(previous, sources)
            if previous is not None
            else {"added": [], "removed": [], "relocated": [], "changed": []}
        )
        previous_identity = (
            previous.get("paper_identity") if isinstance(previous, dict) else None
        )
        paper_identity = (
            previous_identity
            if isinstance(previous_identity, str) and previous_identity
            else main_record.get("sha256")
        )
        stale = bool(changes["changed"] or changes["removed"] or changes["added"])
        stale_reasons = []
        if changes["changed"]:
            stale_reasons.append(
                "source content changed: "
                + ", ".join(item["path"] for item in changes["changed"])
            )
        if changes["removed"]:
            stale_reasons.append(
                "registered source no longer present: "
                + ", ".join(item["path"] for item in changes["removed"])
            )
        if changes["added"]:
            stale_reasons.append(
                "new source registered: "
                + ", ".join(item["path"] for item in changes["added"])
            )
        manifest = make_workspace_manifest(
            repository_root,
            paper_dir,
            title,
            sources,
            paper_identity if isinstance(paper_identity, str) else None,
            main_record.get("sha256"),
            changes,
            stale,
            stale_reasons,
        )
        if previous is not None:
            manifest["created_at"] = previous.get("created_at", manifest["updated_at"])
        else:
            manifest["created_at"] = manifest["updated_at"]
        atomic_write_text(
            manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
    finally:
        release_lock(lock_path)
    if stale:
        print(
            "warning: sources changed since the last init; existing crops, content, "
            "build, and render outputs may be stale and are not deleted: "
            + "; ".join(stale_reasons),
            file=sys.stderr,
        )
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "resolve-root":
            root, outputs_root = resolve_workspace_roots(
                args.repository_root, args.output_root, args.skill_dir
            )
            result = {
                "repository_root": str(root) if root is not None else None,
                "outputs_root": str(outputs_root),
            }
        else:
            result = initialize_workspace(args)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
