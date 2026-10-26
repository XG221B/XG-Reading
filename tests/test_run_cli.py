"""``run.py`` CLI acceptance tests (dispatch, usage, exit codes)."""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest
from _portability_helpers import SKILL_DIR, load_script_module

run_cli = load_script_module(SKILL_DIR / "run.py", "xg_reading_run")

EXPECTED_COMMANDS = {
    "doctor",
    "workspace",
    "extract",
    "preflight",
    "build",
    "audit",
    "render",
}


class TestCommandTable:
    def test_all_commands_are_registered(self):
        assert set(run_cli.COMMANDS) == EXPECTED_COMMANDS

    def test_every_command_has_a_description(self):
        for name, entry in run_cli.COMMANDS.items():
            assert isinstance(entry, tuple) and len(entry) == 2
            assert entry[0].endswith(".py")
            assert entry[1].strip(), f"{name} needs a description"

    @pytest.mark.parametrize("command", sorted(EXPECTED_COMMANDS))
    def test_script_path_points_at_an_existing_script(self, command):
        path = run_cli.script_path(command)
        assert path.is_file(), path
        assert path.parent.name == "scripts"
        assert path.name == run_cli.COMMANDS[command][0]

    def test_unknown_command_has_no_script_path(self):
        with pytest.raises(KeyError):
            run_cli.script_path("deploy")

    def test_minimum_python_is_311(self):
        assert run_cli.MIN_PYTHON == (3, 11)


class TestUsage:
    def test_usage_lists_every_command(self):
        text = run_cli.usage()
        assert text.startswith("Usage: python run.py <command>")
        for command in EXPECTED_COMMANDS:
            assert command in text

    @pytest.mark.parametrize("argv", [[], ["-h"], ["--help"], ["help"]])
    def test_help_exits_zero_and_prints_usage(self, capfd, argv):
        assert run_cli.main(argv) == 0
        captured = capfd.readouterr()
        assert "Usage: python run.py <command>" in captured.out
        assert captured.err == ""

    def test_unknown_command_exits_2_and_prints_usage_on_stderr(self, capfd):
        assert run_cli.main(["nope"]) == 2
        captured = capfd.readouterr()
        assert "Unknown command: nope" in captured.err
        assert "Usage:" in captured.err

    def test_missing_script_file_exits_2(self, monkeypatch, tmp_path, capfd):
        monkeypatch.setattr(run_cli, "script_path", lambda command: tmp_path / "gone.py")
        assert run_cli.main(["doctor"]) == 2
        captured = capfd.readouterr()
        assert "Missing XG-Reading script" in captured.err

    def test_too_old_python_exits_2(self, monkeypatch, capfd):
        monkeypatch.setattr(
            run_cli,
            "sys",
            SimpleNamespace(
                version_info=(3, 10, 0),
                version="3.10.14 (fake)",
                executable=sys.executable,
                stderr=sys.stderr,
                stdout=sys.stdout,
            ),
        )
        assert run_cli.main(["--help"]) == 2
        captured = capfd.readouterr()
        assert "requires Python 3.11" in captured.err
        assert "3.10.14" in captured.err


class TestDispatch:
    def test_dispatches_with_the_current_interpreter_and_passthrough(self, monkeypatch):
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 7)

        monkeypatch.setattr(run_cli, "subprocess", SimpleNamespace(run=fake_run))
        assert run_cli.main(["preflight", "--content", "content.json"]) == 7
        assert len(calls) == 1
        command, kwargs = calls[0]
        assert command[0] == sys.executable
        assert command[1] == "-B"
        assert command[2] == str(run_cli.script_path("preflight"))
        assert command[3:] == ["--content", "content.json"]
        assert kwargs.get("check") is False

    def test_workspace_resolve_root_dispatches_successfully(self, tmp_path):
        output_root = tmp_path / "output root"
        assert (
            run_cli.main(
                ["workspace", "resolve-root", "--output-root", str(output_root)]
            )
            == 0
        )
        assert not output_root.exists()

    def test_child_exit_code_is_propagated(self, tmp_path):
        # Passing both roots makes reader_workspace exit 1; run.py must forward it.
        assert (
            run_cli.main(
                [
                    "workspace",
                    "resolve-root",
                    "--output-root",
                    str(tmp_path / "out"),
                    "--repository-root",
                    str(SKILL_DIR.parents[1]),
                ]
            )
            == 1
        )

    def test_subcommand_help_is_forwarded(self, capfd):
        assert run_cli.main(["workspace", "--help"]) == 0
        captured = capfd.readouterr()
        assert "resolve-root" in captured.out
        assert "init" in captured.out
