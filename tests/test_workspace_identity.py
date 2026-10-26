"""Regression tests for B01: workspace identity and source revisions.

Repeated ``init`` keeps the registered source set unless a role is explicitly
replaced, describes added/removed/relocated/changed sources, marks the
workspace ``stale`` for content/registry changes, and never deletes old
artifacts. Unmanaged output directories and title conflicts are refused.
"""

from __future__ import annotations

import hashlib
import json

import pytest
import reader_workspace as workspace


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_files(tmp_path):
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\nfirst paper\n")
    supplement = tmp_path / "supplement.pdf"
    supplement.write_bytes(b"%PDF-1.4\nsupplement\n")
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"movie bytes")
    return paper, supplement, movie


def init_workspace(
    tmp_path, paper, *, title="2024-Identity", supplements=(), movies=()
):
    args = [
        "init",
        "--paper",
        str(paper),
        "--title",
        title,
        "--output-root",
        str(tmp_path / "out"),
    ]
    for item in supplements:
        args.extend(["--supplement", str(item)])
    for item in movies:
        args.extend(["--movie", str(item)])
    return workspace.initialize_workspace(workspace.parse_args(args))


def manifest_path(tmp_path, title="2024-Identity"):
    return tmp_path / "out" / title / "process" / "source-manifest.json"


class TestManifestIdentity:
    def test_manifest_records_v2_identity_fields(self, tmp_path):
        paper, _supplement, _movie = make_files(tmp_path)
        manifest = init_workspace(tmp_path, paper)
        assert manifest["schema_version"] == 2
        assert manifest["paper_identity"] == sha256(paper)
        assert manifest["source_revision"] == sha256(paper)
        assert manifest["source_changes"] == {
            "added": [],
            "removed": [],
            "relocated": [],
            "changed": [],
        }
        assert manifest["stale"] is False
        assert manifest["stale_reasons"] == []
        assert manifest["created_at"]

    def test_paper_identity_is_stable_while_revision_tracks_content(
        self, tmp_path, capsys
    ):
        paper, _supplement, _movie = make_files(tmp_path)
        first = init_workspace(tmp_path, paper)
        second = init_workspace(tmp_path, paper)
        assert second["paper_identity"] == first["paper_identity"]
        assert second["source_revision"] == first["source_revision"]
        assert second["stale"] is False

        paper.write_bytes(b"%PDF-1.4\nrevised paper content\n")
        third = init_workspace(tmp_path, paper)
        capsys.readouterr()
        assert third["paper_identity"] == first["paper_identity"]
        assert third["source_revision"] == sha256(paper)
        assert third["source_revision"] != first["source_revision"]
        assert third["stale"] is True


class TestSourceRevisions:
    def test_reinit_without_flags_preserves_registered_sources(self, tmp_path, capsys):
        paper, supplement, movie = make_files(tmp_path)
        first = init_workspace(
            tmp_path, paper, supplements=[supplement], movies=[movie]
        )
        capsys.readouterr()
        assert [record["role"] for record in first["sources"]] == [
            "main_paper",
            "supplement",
            "movie",
        ]

        second = init_workspace(tmp_path, paper)
        captured = capsys.readouterr()
        assert [record["role"] for record in second["sources"]] == [
            "main_paper",
            "supplement",
            "movie",
        ]
        assert second["stale"] is False
        assert second["source_changes"] == {
            "added": [],
            "removed": [],
            "relocated": [],
            "changed": [],
        }
        assert captured.err == ""

    def test_source_content_change_marks_stale_and_keeps_old_docx(
        self, tmp_path, capsys
    ):
        paper, _supplement, _movie = make_files(tmp_path)
        first = init_workspace(tmp_path, paper)
        capsys.readouterr()
        paper_dir = tmp_path / "out" / "2024-Identity"
        old_docx = paper_dir / "2024-Identity论文逐图解读.docx"
        old_docx.write_bytes(b"old build output")
        content = paper_dir / "process" / "content.json"
        content.write_text('{"kept": true}', encoding="utf-8")

        paper.write_bytes(b"%PDF-1.4\nsecond version with new data\n")
        second = init_workspace(tmp_path, paper)
        captured = capsys.readouterr()

        assert second["stale"] is True
        assert second["source_changes"]["changed"] == [
            {"role": "main_paper", "path": str(paper.resolve())}
        ]
        assert any(
            "source content changed" in reason for reason in second["stale_reasons"]
        )
        assert "sources changed since the last init" in captured.err
        assert "may be stale and are not deleted" in captured.err
        assert second["created_at"] == first["created_at"]
        assert old_docx.read_bytes() == b"old build output"
        assert content.read_text(encoding="utf-8") == '{"kept": true}'

    def test_relocated_source_is_not_stale(self, tmp_path, capsys):
        paper, supplement, _movie = make_files(tmp_path)
        first = init_workspace(tmp_path, paper, supplements=[supplement])
        capsys.readouterr()
        renamed = tmp_path / "supplement-renamed.pdf"
        supplement.rename(renamed)

        second = init_workspace(tmp_path, paper, supplements=[renamed])
        capsys.readouterr()
        assert second["source_changes"]["relocated"] == [
            {
                "role": "supplement",
                "from": str(supplement.resolve()),
                "to": str(renamed.resolve()),
            }
        ]
        assert second["source_changes"]["removed"] == []
        assert second["stale"] is False
        assert first["created_at"] == second["created_at"]

    def test_added_source_marks_stale(self, tmp_path, capsys):
        paper, supplement, _movie = make_files(tmp_path)
        init_workspace(tmp_path, paper)
        capsys.readouterr()
        second = init_workspace(tmp_path, paper, supplements=[supplement])
        captured = capsys.readouterr()
        assert second["source_changes"]["added"] == [
            {"role": "supplement", "path": str(supplement.resolve())}
        ]
        assert second["stale"] is True
        assert "new source registered" in captured.err

    def test_removed_source_marks_stale(self, tmp_path, capsys):
        paper, supplement, _movie = make_files(tmp_path)
        init_workspace(tmp_path, paper, supplements=[supplement])
        capsys.readouterr()
        supplement.unlink()
        second = init_workspace(tmp_path, paper)
        captured = capsys.readouterr()
        assert second["source_changes"]["removed"] == [
            {"role": "supplement", "path": str(supplement.resolve())}
        ]
        assert second["stale"] is True
        assert "registered source no longer present" in captured.err


class TestWorkspaceGuards:
    def test_title_conflict_is_refused(self, tmp_path):
        paper, _supplement, _movie = make_files(tmp_path)
        init_workspace(tmp_path, paper)
        path = manifest_path(tmp_path)
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["paper_title"] = "Different Title"
        path.write_text(json.dumps(stored), encoding="utf-8")
        with pytest.raises(ValueError, match="title conflict"):
            init_workspace(tmp_path, paper)

    def test_unmanaged_directory_without_manifest_is_refused(self, tmp_path):
        paper, _supplement, _movie = make_files(tmp_path)
        unmanaged = tmp_path / "out" / "2024-Identity"
        unmanaged.mkdir(parents=True)
        (unmanaged / "random.txt").write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="without a source manifest"):
            init_workspace(tmp_path, paper)
        assert (unmanaged / "random.txt").read_text(encoding="utf-8") == "x"

    def test_manifest_that_is_not_an_object_is_refused(self, tmp_path):
        paper, _supplement, _movie = make_files(tmp_path)
        path = manifest_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="not a JSON object"):
            init_workspace(tmp_path, paper)
