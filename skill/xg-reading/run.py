#!/usr/bin/env python3
"""Agent-neutral XG-Reading command entrypoint.

Every subcommand is dispatched to an existing helper script from the same
directory using the interpreter that runs this file, so one installed Python
environment is used consistently and no shell path quoting is involved.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

COMMANDS = {
    "doctor": ("check_environment.py", "check Python, dependencies, roots, template, renderer"),
    "workspace": ("reader_workspace.py", "resolve the output root or init a paper workspace"),
    "extract": ("extract_figures_batch.py", "extract main figures from the paper PDF"),
    "preflight": ("preflight_content.py", "validate content.json before building"),
    "build": ("build_reader_docx.py", "build the reader DOCX"),
    "audit": ("audit_reader_docx.py", "audit the built DOCX"),
    "render": ("render_reader_docx.py", "render the DOCX to cached inspection pages"),
}

MIN_PYTHON = (3, 11)


def script_path(command: str) -> Path:
    return Path(__file__).resolve().parent / "scripts" / COMMANDS[command][0]


def usage() -> str:
    width = max(len(name) for name in COMMANDS)
    lines = [
        "Usage: python run.py <command> [arguments]",
        "",
        "Commands:",
        *(f"  {name:<{width}}  {description}" for name, (_, description) in COMMANDS.items()),
        "",
        "Pass --help after a command for its options. Read SKILL.md before interpreting a paper.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print(
            f"XG-Reading requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer; "
            f"this interpreter is {sys.version.split()[0]}.",
            file=sys.stderr,
        )
        return 2
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(usage())
        return 0
    command = args[0]
    if command not in COMMANDS:
        print(f"Unknown command: {command}\n", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2
    path = script_path(command)
    if not path.is_file():
        print(f"Missing XG-Reading script for {command}: {path}", file=sys.stderr)
        return 2
    return subprocess.run(
        [sys.executable, "-B", str(path), *args[1:]], check=False
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
