"""Output-root resolution and workspace init acceptance tests.

Contract under test (``skill/xg-reading/scripts/reader_workspace.py``):

* ``resolve_workspace_roots`` never creates directories; only ``init`` does.
* Priority: explicit options, then ``XG_READING_OUTPUT_ROOT``, then the
  skill-local config, then repository discovery.
* Artifacts may never be written into the skill directory.
* ``init`` prints the manifest as ASCII JSON (``ensure_ascii=True``) and
  reports failures as ``{"ok": false, "error": ...}`` with exit code 1.
"""

from __future__ import annotations

import json

import pytest
import reader_workspace as workspace
from _portability_helpers import (
    OUTPUT_ROOT_ENV,
    make_fake_repository,
    make_minimal_skill,
    parse_json_stdout,
    run_cli,
)

CONFIG_NAME = "xg-reading.local.json"


@pytest.fixture(autouse=True)
def _clear_output_env(monkeypatch):
    monkeypatch.delenv(OUTPUT_ROOT_ENV, raising=False)


@pytest.fixture
def standalone_skill(tmp_path):
    return make_minimal_skill(tmp_path / "standalone" / "xg-reading")


def write_config(skill_dir, payload, *, bom=False):
    path = skill_dir / CONFIG_NAME
    text = json.dumps(payload, ensure_ascii=False)
    data = ("\ufeff" + text).encode("utf-8") if bom else text.encode("utf-8")
    path.write_bytes(data)
    return path


def make_skill_in_repository(root):
    """Build a fake repository whose own skill tree holds the dispatch scripts."""
    repo = make_fake_repository(root)
    make_minimal_skill(repo / "skill" / "xg-reading")
    return repo


class TestResolveWorkspaceRoots:
    def test_explicit_output_root_wins_and_creates_nothing(self, tmp_path, standalone_skill):
        output_root = tmp_path / "项目 输出 root"
        repository, outputs = workspace.resolve_workspace_roots(
            None, output_root, standalone_skill
        )
        assert repository is None
        assert outputs == output_root.resolve()
        assert not output_root.exists()

    def test_explicit_repository_root_uses_outputs_subdirectory(
        self, tmp_path, standalone_skill
    ):
        repo = make_fake_repository(tmp_path / "repo")
        repository, outputs = workspace.resolve_workspace_roots(
            repo, None, standalone_skill
        )
        assert repository == repo.resolve()
        assert outputs == (repo / "outputs").resolve()
        assert not (repo / "outputs").exists()

    def test_both_explicit_roots_are_rejected(self, tmp_path, standalone_skill):
        repo = make_fake_repository(tmp_path / "repo")
        with pytest.raises(ValueError, match="not both"):
            workspace.resolve_workspace_roots(repo, tmp_path / "out", standalone_skill)

    def test_environment_root_beats_config(self, tmp_path, standalone_skill, monkeypatch):
        write_config(standalone_skill, {"output_root": "../from-config"})
        env_root = tmp_path / "from-env"
        monkeypatch.setenv(OUTPUT_ROOT_ENV, str(env_root))
        repository, outputs = workspace.resolve_workspace_roots(
            None, None, standalone_skill
        )
        assert repository is None
        assert outputs == env_root.resolve()

    def test_explicit_output_root_beats_environment_and_config(
        self, tmp_path, standalone_skill, monkeypatch
    ):
        write_config(standalone_skill, {"output_root": "../from-config"})
        monkeypatch.setenv(OUTPUT_ROOT_ENV, str(tmp_path / "from-env"))
        explicit = tmp_path / "explicit"
        repository, outputs = workspace.resolve_workspace_roots(
            None, explicit, standalone_skill
        )
        assert repository is None
        assert outputs == explicit.resolve()

    def test_relative_environment_root_is_rejected(self, standalone_skill, monkeypatch):
        monkeypatch.setenv(OUTPUT_ROOT_ENV, "relative/output-root")
        with pytest.raises(ValueError, match="absolute"):
            workspace.resolve_workspace_roots(None, None, standalone_skill)

    def test_config_output_root_is_relative_to_skill_dir(
        self, tmp_path, standalone_skill
    ):
        write_config(standalone_skill, {"output_root": "../papers-out"})
        repository, outputs = workspace.resolve_workspace_roots(
            None, None, standalone_skill
        )
        assert repository is None
        assert outputs == (standalone_skill.parent / "papers-out").resolve()
        assert not outputs.exists()

    def test_config_with_utf8_bom_is_parsed(self, tmp_path, standalone_skill):
        write_config(standalone_skill, {"output_root": "../bom-out"}, bom=True)
        _, outputs = workspace.resolve_workspace_roots(None, None, standalone_skill)
        assert outputs == (standalone_skill.parent / "bom-out").resolve()

    def test_config_repository_root_resolves_outputs(self, tmp_path, standalone_skill):
        repo = make_fake_repository(tmp_path / "repo")
        write_config(standalone_skill, {"repository_root": str(repo)})
        repository, outputs = workspace.resolve_workspace_roots(
            None, None, standalone_skill
        )
        assert repository == repo.resolve()
        assert outputs == (repo / "outputs").resolve()

    def test_config_repository_root_may_be_relative(self, tmp_path, standalone_skill):
        repo = make_fake_repository(tmp_path / "repo")
        write_config(standalone_skill, {"repository_root": "../../repo"})
        repository, outputs = workspace.resolve_workspace_roots(
            None, None, standalone_skill
        )
        assert repository == repo.resolve()
        assert outputs == (repo / "outputs").resolve()

    def test_stale_config_repository_root_raises_file_not_found(
        self, tmp_path, standalone_skill
    ):
        write_config(standalone_skill, {"repository_root": str(tmp_path / "gone")})
        with pytest.raises(FileNotFoundError, match="does not exist"):
            workspace.resolve_workspace_roots(None, None, standalone_skill)

    def test_explicit_output_root_overrides_stale_config(
        self, tmp_path, standalone_skill
    ):
        write_config(standalone_skill, {"repository_root": str(tmp_path / "gone")})
        override = tmp_path / "override-root"
        repository, outputs = workspace.resolve_workspace_roots(
            None, override, standalone_skill
        )
        assert repository is None
        assert outputs == override.resolve()

    @pytest.mark.parametrize("configured", ["inside", "."])
    def test_config_output_root_inside_skill_dir_is_rejected(
        self, tmp_path, standalone_skill, configured
    ):
        write_config(standalone_skill, {"output_root": configured})
        with pytest.raises(ValueError, match="outside the skill directory"):
            workspace.resolve_workspace_roots(None, None, standalone_skill)

    def test_explicit_output_root_inside_skill_dir_is_rejected(self, standalone_skill):
        with pytest.raises(ValueError, match="outside the skill directory"):
            workspace.resolve_workspace_roots(
                None, standalone_skill / "inside", standalone_skill
            )

    def test_output_root_that_is_a_file_is_rejected(self, tmp_path, standalone_skill):
        a_file = tmp_path / "not-a-dir"
        a_file.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="not a directory"):
            workspace.resolve_workspace_roots(None, a_file, standalone_skill)

    def test_repository_is_discovered_upwards_from_skill_dir(self, tmp_path):
        repo = make_skill_in_repository(tmp_path / "repo")
        repository, outputs = workspace.resolve_workspace_roots(
            None, None, repo / "skill" / "xg-reading"
        )
        assert repository == repo.resolve()
        assert outputs == (repo / "outputs").resolve()

    def test_explicit_repository_root_must_look_like_a_repository(
        self, tmp_path, standalone_skill
    ):
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(ValueError, match="Not an XG-Reading repository root"):
            workspace.resolve_workspace_roots(plain, None, standalone_skill)

    def test_config_repository_root_must_look_like_a_repository(
        self, tmp_path, standalone_skill
    ):
        plain = tmp_path / "plain"
        plain.mkdir()
        write_config(standalone_skill, {"repository_root": str(plain)})
        with pytest.raises(ValueError, match="not an XG-Reading repository root"):
            workspace.resolve_workspace_roots(None, None, standalone_skill)

    def test_no_config_no_repository_is_an_error(self, standalone_skill):
        with pytest.raises(RuntimeError, match="could not be resolved"):
            workspace.resolve_workspace_roots(None, None, standalone_skill)

    def test_config_without_any_root_is_an_error(self, standalone_skill):
        write_config(standalone_skill, {"unrelated": True})
        with pytest.raises(ValueError, match="repository_root is required"):
            workspace.resolve_workspace_roots(None, None, standalone_skill)

    def test_invalid_config_json_is_an_error(self, standalone_skill):
        (standalone_skill / CONFIG_NAME).write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid local XG-Reading config"):
            workspace.resolve_workspace_roots(None, None, standalone_skill)


class TestMainArgvList:
    def test_resolve_root_main_accepts_an_argv_list(self, tmp_path, capsys):
        output_root = tmp_path / "direct-root"
        assert workspace.main(
            ["resolve-root", "--output-root", str(output_root)]
        ) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["repository_root"] is None
        assert payload["outputs_root"] == str(output_root.resolve())

    def test_init_main_accepts_an_argv_list(self, tmp_path, capsys):
        paper = tmp_path / "paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        output_root = tmp_path / "direct-root"
        assert workspace.main(
            [
                "init",
                "--paper",
                str(paper),
                "--title",
                "2024-Direct",
                "--output-root",
                str(output_root),
            ]
        ) == 0
        manifest = json.loads(capsys.readouterr().out)
        assert manifest["schema_version"] == 2
        assert (output_root / "2024-Direct" / "process").is_dir()

    def test_init_main_reports_errors_as_json_and_exit_1(self, tmp_path, capsys):
        assert workspace.main(
            [
                "init",
                "--paper",
                str(tmp_path / "missing.pdf"),
                "--output-root",
                str(tmp_path / "root"),
            ]
        ) == 1
        assert json.loads(capsys.readouterr().out)["ok"] is False


class TestWorkspaceCliResolveRoot:
    def test_resolve_root_prints_json_and_creates_nothing(
        self, tmp_path, standalone_skill
    ):
        output_root = tmp_path / "project 输出根"
        result = run_cli(
            ["workspace", "resolve-root", "--output-root", str(output_root)],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 0, result.stderr
        payload = parse_json_stdout(result)
        assert payload["repository_root"] is None
        assert payload["outputs_root"] == str(output_root.resolve())
        assert not output_root.exists()

    def test_resolve_root_with_repository_root(self, tmp_path, standalone_skill):
        repo = make_fake_repository(tmp_path / "repo")
        result = run_cli(
            ["workspace", "resolve-root", "--repository-root", str(repo)],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 0, result.stderr
        payload = parse_json_stdout(result)
        assert payload["repository_root"] == str(repo.resolve())
        assert payload["outputs_root"] == str((repo / "outputs").resolve())

    def test_resolve_root_uses_repository_discovery(self, tmp_path):
        repo = make_skill_in_repository(tmp_path / "repo")
        result = run_cli(
            ["workspace", "resolve-root"], skill_dir=repo / "skill" / "xg-reading"
        )
        assert result.returncode == 0, result.stderr
        payload = parse_json_stdout(result)
        assert payload["repository_root"] == str(repo.resolve())
        assert payload["outputs_root"] == str((repo / "outputs").resolve())

    def test_resolve_root_without_any_root_fails_as_json(self, standalone_skill):
        result = run_cli(["workspace", "resolve-root"], skill_dir=standalone_skill)
        assert result.returncode == 1
        payload = parse_json_stdout(result)
        assert payload["ok"] is False
        assert "could not be resolved" in payload["error"]
        assert result.stdout.isascii()

    def test_conflicting_roots_fail_with_exit_1(self, tmp_path, standalone_skill):
        repo = make_fake_repository(tmp_path / "repo")
        result = run_cli(
            [
                "workspace",
                "resolve-root",
                "--output-root",
                str(tmp_path / "out"),
                "--repository-root",
                str(repo),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 1
        payload = parse_json_stdout(result)
        assert payload["ok"] is False
        assert "not both" in payload["error"]

    def test_environment_root_is_used_by_cli(self, tmp_path, standalone_skill):
        env_root = tmp_path / "env-root"
        result = run_cli(
            ["workspace", "resolve-root"],
            skill_dir=standalone_skill,
            env={OUTPUT_ROOT_ENV: str(env_root)},
        )
        assert result.returncode == 0, result.stderr
        payload = parse_json_stdout(result)
        assert payload["outputs_root"] == str(env_root.resolve())

    def test_relative_environment_root_is_rejected_by_cli(self, standalone_skill):
        result = run_cli(
            ["workspace", "resolve-root"],
            skill_dir=standalone_skill,
            env={OUTPUT_ROOT_ENV: "relative/path"},
        )
        assert result.returncode == 1
        payload = parse_json_stdout(result)
        assert payload["ok"] is False
        assert "absolute" in payload["error"]

    def test_config_output_root_relative_to_skill_and_cwd_independent(
        self, tmp_path, standalone_skill
    ):
        write_config(standalone_skill, {"output_root": "../papers-out"}, bom=True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        result = run_cli(
            ["workspace", "resolve-root"], skill_dir=standalone_skill, cwd=elsewhere
        )
        assert result.returncode == 0, result.stderr
        payload = parse_json_stdout(result)
        assert payload["outputs_root"] == str(
            (standalone_skill.parent / "papers-out").resolve()
        )
        assert not (standalone_skill.parent / "papers-out").exists()

    def test_stale_config_errors_but_explicit_output_root_overrides(
        self, tmp_path, standalone_skill
    ):
        write_config(standalone_skill, {"repository_root": str(tmp_path / "gone")})
        stale = run_cli(["workspace", "resolve-root"], skill_dir=standalone_skill)
        assert stale.returncode == 1
        assert parse_json_stdout(stale)["ok"] is False

        paper = tmp_path / "2024-Paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        override = tmp_path / "override"
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(paper),
                "--title",
                "2024-Override",
                "--output-root",
                str(override),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert parse_json_stdout(result)["repository_root"] is None

    def test_config_output_root_inside_skill_is_rejected_by_cli(
        self, standalone_skill
    ):
        write_config(standalone_skill, {"output_root": "inside"})
        result = run_cli(["workspace", "resolve-root"], skill_dir=standalone_skill)
        assert result.returncode == 1
        assert parse_json_stdout(result)["ok"] is False

    def test_output_root_inside_skill_is_rejected_by_cli(self, standalone_skill):
        result = run_cli(
            [
                "workspace",
                "resolve-root",
                "--output-root",
                str(standalone_skill / "inside"),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 1
        payload = parse_json_stdout(result)
        assert payload["ok"] is False
        assert "outside the skill directory" in payload["error"]


class TestWorkspaceCliInit:
    def test_init_with_output_root_writes_manifest(self, tmp_path, standalone_skill):
        paper = tmp_path / "paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        output_root = tmp_path / "项目 输出 root"
        title = "2024-中文 标题 Test"
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(paper),
                "--title",
                title,
                "--output-root",
                str(output_root),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.isascii(), "init stdout must be ASCII-safe JSON"
        manifest = parse_json_stdout(result)
        assert manifest["schema_version"] == 2
        assert manifest["repository_root"] is None
        assert manifest["paper_title"] == title
        assert manifest["outputs_root"] == str(output_root.resolve())
        assert isinstance(manifest["paper_identity"], str)
        assert len(manifest["paper_identity"]) == 64
        assert manifest["source_revision"] == manifest["sources"][0]["sha256"]
        assert manifest["source_changes"] == {
            "added": [],
            "removed": [],
            "relocated": [],
            "changed": [],
        }
        assert manifest["stale"] is False
        assert manifest["stale_reasons"] == []
        assert set(manifest["workspace"]) >= {
            "paper_dir",
            "final_docx",
            "process_dir",
            "content_json",
            "figures_dir",
            "supplementary_dir",
            "movie_frames_dir",
            "rendered_dir",
            "audit_report",
        }
        paper_dir = output_root / title
        assert manifest["workspace"]["paper_dir"] == str(paper_dir)
        for relative in (
            "process/figures",
            "process/supplementary",
            "process/movie-frames",
            "process/rendered",
        ):
            assert (paper_dir / relative).is_dir()
        assert (paper_dir / "process" / "source-manifest.json").is_file()
        assert manifest["created_at"] == manifest["updated_at"]
        source = manifest["sources"][0]
        assert source["role"] == "main_paper"
        assert source["exists"] is True
        assert len(source["sha256"]) == 64

    def test_init_with_repository_root_lands_in_outputs(
        self, tmp_path, standalone_skill
    ):
        repo = make_fake_repository(tmp_path / "repo")
        paper = tmp_path / "2024-Repo Paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(paper),
                "--title",
                "2024-Repo Paper",
                "--repository-root",
                str(repo),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = parse_json_stdout(result)
        assert manifest["repository_root"] == str(repo.resolve())
        assert manifest["outputs_root"] == str((repo / "outputs").resolve())
        assert manifest["workspace"]["paper_dir"] == str(
            (repo / "outputs" / "2024-Repo Paper").resolve()
        )

    def test_init_records_all_source_roles(self, tmp_path, standalone_skill):
        paper = tmp_path / "2024-Sources.pdf"
        paper.write_bytes(b"%PDF-1.4\nmain\n")
        supplement = tmp_path / "si.pdf"
        supplement.write_bytes(b"%PDF-1.4\nsupp\n")
        movie = tmp_path / "movie.mp4"
        movie.write_bytes(b"fake movie bytes")
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(paper),
                "--title",
                "2024-Sources",
                "--supplement",
                str(supplement),
                "--movie",
                str(movie),
                "--output-root",
                str(tmp_path / "root"),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = parse_json_stdout(result)
        assert [record["role"] for record in manifest["sources"]] == [
            "main_paper",
            "supplement",
            "movie",
        ]
        for record in manifest["sources"]:
            assert record["exists"] is True
            assert len(record["sha256"]) == 64
            assert record["size_bytes"] > 0

    def test_init_without_year_prefix_warns_but_succeeds(
        self, tmp_path, standalone_skill
    ):
        paper = tmp_path / "paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(paper),
                "--title",
                "NoYear-Chinese Title",
                "--output-root",
                str(tmp_path / "root"),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "warning" in result.stderr
        assert (tmp_path / "root" / "NoYear-Chinese Title").is_dir()

    @pytest.mark.parametrize("title", ["CON", "nul", "LPT9"])
    def test_init_rejects_windows_reserved_names(self, tmp_path, standalone_skill, title):
        paper = tmp_path / "paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(paper),
                "--title",
                title,
                "--output-root",
                str(tmp_path / "root"),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 1
        payload = parse_json_stdout(result)
        assert payload["ok"] is False
        assert "reserved" in payload["error"]

    def test_init_rejects_unusable_title(self, tmp_path, standalone_skill):
        paper = tmp_path / "paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(paper),
                "--title",
                "   ",
                "--output-root",
                str(tmp_path / "root"),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 1
        assert parse_json_stdout(result)["ok"] is False

    def test_init_missing_paper_fails(self, tmp_path, standalone_skill):
        result = run_cli(
            [
                "workspace",
                "init",
                "--paper",
                str(tmp_path / "missing.pdf"),
                "--title",
                "2024-Missing",
                "--output-root",
                str(tmp_path / "root"),
            ],
            skill_dir=standalone_skill,
        )
        assert result.returncode == 1
        payload = parse_json_stdout(result)
        assert payload["ok"] is False
        assert "does not exist" in payload["error"]

    def test_reinit_preserves_created_at_and_existing_files(
        self, tmp_path, standalone_skill
    ):
        paper = tmp_path / "paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfake\n")
        args = [
            "workspace",
            "init",
            "--paper",
            str(paper),
            "--title",
            "2024-Reinit",
            "--output-root",
            str(tmp_path / "root"),
        ]
        first = run_cli(args, skill_dir=standalone_skill)
        assert first.returncode == 0, first.stdout + first.stderr
        paper_dir = tmp_path / "root" / "2024-Reinit"
        manifest_path = paper_dir / "process" / "source-manifest.json"
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored["created_at"] = "2020-01-01T00:00:00+00:00"
        manifest_path.write_text(json.dumps(stored), encoding="utf-8")

        marker = paper_dir / "process" / "figures" / "keep-me.txt"
        marker.write_text("keep", encoding="utf-8")
        content = paper_dir / "process" / "content.json"
        content.write_text('{"custom": true}', encoding="utf-8")

        second = run_cli(args, skill_dir=standalone_skill)
        assert second.returncode == 0, second.stdout + second.stderr
        manifest = parse_json_stdout(second)
        assert manifest["created_at"] == "2020-01-01T00:00:00+00:00"
        assert manifest_path.is_file()
        assert marker.read_text(encoding="utf-8") == "keep"
        assert content.read_text(encoding="utf-8") == '{"custom": true}'

    def test_reinit_warns_when_source_changed(self, tmp_path, standalone_skill):
        paper = tmp_path / "paper.pdf"
        paper.write_bytes(b"%PDF-1.4\nfirst\n")
        args = [
            "workspace",
            "init",
            "--paper",
            str(paper),
            "--title",
            "2024-Changed",
            "--output-root",
            str(tmp_path / "root"),
        ]
        first = run_cli(args, skill_dir=standalone_skill)
        assert first.returncode == 0, first.stdout + first.stderr
        assert "changed since the last init" not in first.stderr
        paper.write_bytes(b"%PDF-1.4\nsecond version with new content\n")
        second = run_cli(args, skill_dir=standalone_skill)
        assert second.returncode == 0, second.stdout + second.stderr
        assert "sources changed since the last init" in second.stderr
        assert "may be stale and are not deleted" in second.stderr
        assert "source content changed" in second.stderr
        manifest = parse_json_stdout(second)
        assert manifest["stale"] is True
        assert manifest["stale_reasons"]
        assert any(
            "source content changed" in reason for reason in manifest["stale_reasons"]
        )
        assert manifest["source_changes"]["changed"][0]["role"] == "main_paper"
