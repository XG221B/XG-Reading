"""Isolation guards for the test suite (E01).

The suite must not depend on the real repository's location or its ``outputs/``
directory:

* workspace-root resolution returns the same result for a standalone skill copy
  placed inside the repository tree and one placed outside it;
* upward repository discovery is only exercised through explicit fake
  repository roots, so the real checkout above a temporary directory can never
  silently satisfy (or break) a test;
* ``preflight_content`` resolves relative image paths identically inside and
  outside the repository tree.

The temporary directories created inside the repository are deleted by the
context managers below; nothing is written to the real ``outputs/`` directory.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

import preflight_content as preflight
import pytest
import reader_workspace as workspace
from _portability_helpers import (
    REPO_ROOT,
    make_fake_repository,
    make_minimal_skill,
    parse_json_stdout,
    run_cli,
)
from PIL import Image


@contextlib.contextmanager
def temp_dir_inside_repository():
    """A temporary directory under the repository root, removed on exit."""
    with tempfile.TemporaryDirectory(prefix=".e01-tmp-", dir=REPO_ROOT) as path:
        yield Path(path)


@contextlib.contextmanager
def temp_dir_outside_repository():
    """A temporary directory in the system temp area, removed on exit."""
    with tempfile.TemporaryDirectory(prefix="e01-tmp-") as path:
        yield Path(path)


@contextlib.contextmanager
def both_temp_roots():
    with temp_dir_inside_repository() as inside, temp_dir_outside_repository() as outside:
        yield inside, outside


def make_preflight_content(directory: Path, image: str):
    Image.new("RGB", (80, 80), "white").save(directory / "fig1.png")
    return {
        "document_title": "题目与逐图解读",
        "citation": "论文：Author et al., Title, Journal,Year",
        "field_positioning": {
            "heading": "领域定位与本文解决的问题",
            "paragraphs": ["领域问题"],
        },
        "logic_chain": [
            {"title": "Step1：为什么需要这一步", "text": "对应Fig.1：结论。"}
        ],
        "evidence_blocks": [
            {
                "kind": "figure",
                "label": "Fig.1",
                "title": "Figure 1：主图英文标题的准确中文翻译",
                "image": image,
                "paper_claim": "作者对该证据块的主要表述。",
                "panel_explanations": [
                    {"title": "Fig.1A：该panel图注内容的中文译名", "text": "读图方法。"}
                ],
                "logic_role": "该证据块在全文论证中的作用。",
            }
        ],
    }


class TestWorkspaceResolutionIsolation:
    def test_explicit_output_root_behaves_the_same_inside_and_outside_the_repo(self):
        with both_temp_roots() as (inside, outside):
            shared_output = outside / "papers"
            inside_skill = make_minimal_skill(inside / "skill" / "xg-reading")
            outside_skill = make_minimal_skill(outside / "skill" / "xg-reading")
            inside_result = workspace.resolve_workspace_roots(
                None, shared_output, inside_skill
            )
            outside_result = workspace.resolve_workspace_roots(
                None, shared_output, outside_skill
            )
            assert inside_result == outside_result == (None, shared_output.resolve())
            assert not shared_output.exists()

    def test_in_repository_copy_does_not_leak_the_real_repository_root(self):
        with temp_dir_inside_repository() as inside:
            skill = make_minimal_skill(inside / "skill" / "xg-reading")
            repository, outputs = workspace.resolve_workspace_roots(
                None, inside / "papers", skill
            )
            assert repository is None
            assert outputs == (inside / "papers").resolve()
            assert repository != REPO_ROOT.resolve()

    def test_discovery_uses_the_nearest_explicit_fake_repository(self):
        with both_temp_roots() as (inside, outside):
            inside_repo = make_fake_repository(inside / "fake-repo")
            make_minimal_skill(inside_repo / "skill" / "xg-reading")
            outside_repo = make_fake_repository(outside / "fake-repo")
            make_minimal_skill(outside_repo / "skill" / "xg-reading")

            inside_resolved, inside_outputs = workspace.resolve_workspace_roots(
                None, None, inside_repo / "skill" / "xg-reading"
            )
            outside_resolved, outside_outputs = workspace.resolve_workspace_roots(
                None, None, outside_repo / "skill" / "xg-reading"
            )

            assert inside_resolved == inside_repo.resolve()
            assert outside_resolved == outside_repo.resolve()
            # the real checkout above the in-repo temp directory must not win
            assert inside_resolved != REPO_ROOT.resolve()
            # identical resolution semantics in both locations
            assert inside_outputs == inside_resolved / "outputs"
            assert outside_outputs == outside_resolved / "outputs"
            assert inside_resolved.name == outside_resolved.name == "fake-repo"

    def test_workspace_cli_resolution_matches_inside_and_outside_the_repo(self):
        with both_temp_roots() as (inside, outside):
            shared_output = outside / "cli-papers"
            inside_skill = make_minimal_skill(inside / "skill" / "xg-reading")
            outside_skill = make_minimal_skill(outside / "skill" / "xg-reading")
            payloads = []
            for skill in (inside_skill, outside_skill):
                result = run_cli(
                    ["workspace", "resolve-root", "--output-root", str(shared_output)],
                    skill_dir=skill,
                )
                assert result.returncode == 0, result.stderr
                payloads.append(parse_json_stdout(result))
            assert payloads[0] == payloads[1]
            assert payloads[0] == {
                "repository_root": None,
                "outputs_root": str(shared_output.resolve()),
            }
            assert not shared_output.exists()


class TestContentParsingIsolation:
    @pytest.mark.parametrize("image", ["fig1.png", "missing.png"])
    def test_preflight_results_match_inside_and_outside_the_repository(self, image):
        with both_temp_roots() as (inside, outside):
            results = []
            for directory in (inside, outside):
                content = make_preflight_content(directory, image)
                results.append(preflight.check_content(content, directory))
            assert results[0]["errors"] == results[1]["errors"]
            assert results[0]["warnings"] == results[1]["warnings"]

    def test_preflight_reports_the_same_resolution_error_in_both_locations(self):
        with both_temp_roots() as (inside, outside):
            outside_content = make_preflight_content(outside, "missing.png")
            inside_content = make_preflight_content(inside, "missing.png")
            outside_result = preflight.check_content(outside_content, outside)
            inside_result = preflight.check_content(inside_content, inside)
            outside_errors = [
                error for error in outside_result["errors"] if "cannot be resolved" in error
            ]
            assert outside_errors
            assert outside_errors == [
                error for error in inside_result["errors"] if "cannot be resolved" in error
            ]
