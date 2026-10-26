"""Regression tests for A05: shared evidence labels and panel coverage.

``label_utils`` keeps object identity (kind, supplementary, number) separate
from panel letters. Preflight uses it to check block label/title agreement and
panel ownership/coverage without treating the first digits it sees as the
object number.
"""

from __future__ import annotations

import label_utils as labels
import preflight_content as preflight
import pytest
from PIL import Image


@pytest.mark.parametrize(
    ("text", "kind", "number", "supplementary", "panels"),
    [
        ("Fig.1", "figure", "1", False, ()),
        ("Fig. 1A", "figure", "1", False, ("A",)),
        ("Fig.1A-B", "figure", "1", False, ("A", "B")),
        ("Fig.1A–C", "figure", "1", False, ("A", "B", "C")),
        ("Figure 1A", "figure", "1", False, ("A",)),
        ("Fig.1A, B", "figure", "1", False, ("A", "B")),
        ("Fig.S1", "figure", "S1", True, ()),
        ("Fig S1", "figure", "S1", True, ()),
        ("Supplementary Fig. 1", "figure", "S1", True, ()),
        ("Table S2", "table", "S2", True, ()),
        ("Table1", "table", "1", False, ()),
        ("Supplementary Figure 3", "figure", "S3", True, ()),
        ("Fig. 10", "figure", "10", False, ()),
        ("Fig.1a", "figure", "1", False, ("A",)),
    ],
)
def test_parse_label_keeps_object_identity(
    text, kind, number, supplementary, panels
):
    parsed = labels.parse_label(text)
    assert parsed is not None
    assert parsed.kind == kind
    assert parsed.number == number
    assert parsed.supplementary is supplementary
    assert parsed.panels == panels


@pytest.mark.parametrize("text", ["", "abc", "see figure one", None])
def test_parse_label_returns_none_for_non_labels(text):
    assert labels.parse_label(text) is None


def test_object_id_separates_type_and_number():
    assert labels.parse_label("Fig.1").object_id == "figure:1"
    assert labels.parse_label("Table 1").object_id == "table:1"
    assert labels.parse_label("Fig.S1").object_id == "figure:S1"


def test_fig1_does_not_match_fig10():
    assert labels.parse_label("Fig.1").matches(labels.parse_label("Fig. 10")) is False


def test_fig1_matches_its_panel_title():
    assert labels.parse_label("Fig.1").matches(labels.parse_label("Fig.1A")) is True


def test_table1_is_not_a_figure():
    assert labels.parse_label("Table1").matches(labels.parse_label("Fig.1")) is False


def test_expand_panels_expands_ranges():
    assert labels.expand_panels("Fig.1A-C") == ("A", "B", "C")
    assert labels.expand_panels("Fig. 1A, B") == ("A", "B")


def test_panel_letters_only_come_from_labels():
    assert labels.panel_letters("Fig.1") == ()
    assert labels.panel_letters("no label here") == ()


def test_label_display_is_stable():
    assert labels.label_display(labels.parse_label("Fig.S1")) == "Fig.S1"
    assert labels.label_display(labels.parse_label("Table1")) == "Table 1"


@pytest.mark.parametrize(
    ("text", "start", "length", "expected"),
    [
        ("Fig. 1 caption", 0, 6, True),
        ("Fig. 10 caption", 0, 6, False),
        ("Fig. 1A caption", 0, 6, False),
        ("Fig. S10", 0, 7, False),
        ("Fig. S1", 0, 7, True),
        ("as in Fig. 1", 6, 6, True),
    ],
)
def test_is_number_boundary(text, start, length, expected):
    assert labels.is_number_boundary(text, start, length) is expected


def make_content(tmp_path):
    Image.new("RGB", (80, 80), "white").save(tmp_path / "f.png")
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
                "image": "f.png",
                "paper_claim": "作者对该证据块的主要表述。",
                "panel_explanations": [
                    {"title": "Fig.1A：该panel图注内容的中文译名", "text": "读图方法。"}
                ],
                "logic_role": "该证据块在全文论证中的作用。",
            }
        ],
    }


class TestPreflightLabelChecks:
    def run(self, tmp_path, mutate):
        content = make_content(tmp_path)
        mutate(content)
        return preflight.check_content(content, tmp_path)

    def test_valid_figure_block_has_no_errors(self, tmp_path):
        result = self.run(tmp_path, lambda content: None)
        assert result["errors"] == []

    def test_block_label_and_title_conflict_is_an_error(self, tmp_path):
        result = self.run(
            tmp_path,
            lambda content: content["evidence_blocks"][0].update(label="Fig.2"),
        )
        assert any("does not match title object" in error for error in result["errors"])

    def test_panel_from_another_object_is_an_error(self, tmp_path):
        result = self.run(
            tmp_path,
            lambda content: content["evidence_blocks"][0]["panel_explanations"][0].update(
                title="Fig.99A：错误归属"
            ),
        )
        assert any(
            "does not belong to block object figure:1" in error
            for error in result["errors"]
        )

    def test_combined_panel_range_expands_without_errors(self, tmp_path):
        result = self.run(
            tmp_path,
            lambda content: content["evidence_blocks"][0]["panel_explanations"][0].update(
                title="Fig.1A-C：组合展开"
            ),
        )
        assert result["errors"] == []

    def test_duplicate_panel_letter_is_an_error(self, tmp_path):
        def mutate(content):
            content["evidence_blocks"][0]["panel_explanations"] = [
                {"title": "Fig.1A：第一段", "text": "读图。"},
                {"title": "Fig.1A：重复段", "text": "读图。"},
            ]

        result = self.run(tmp_path, mutate)
        assert any("repeats panel A" in error for error in result["errors"])

    @pytest.mark.parametrize(
        ("letters", "missing"),
        [
            (["A", "C"], "B"),
            (["A", "B", "D"], "C"),
        ],
    )
    def test_missing_panel_letter_is_warning_only(self, tmp_path, letters, missing):
        def mutate(content):
            content["evidence_blocks"][0]["panel_explanations"] = [
                {"title": f"Fig.1{letter}：该段", "text": "读图。"}
                for letter in letters
            ]

        result = self.run(tmp_path, mutate)
        assert result["errors"] == []
        assert any("not contiguous" in warning for warning in result["warnings"])
        assert any(f"missing {missing}" in warning for warning in result["warnings"])

    def test_table_number_is_not_checked_as_a_figure_number(self, tmp_path):
        def mutate(content):
            block = content["evidence_blocks"][0]
            block.update(
                kind="table",
                label="Table 1",
                title="Table 1：表格标题",
                panel_explanations=[{"title": "统计结果汇总", "text": "表格解读。"}],
            )

        result = self.run(tmp_path, mutate)
        assert result["errors"] == []

    def test_table_panel_does_not_need_a_figure_label(self, tmp_path):
        def mutate(content):
            block = content["evidence_blocks"][0]
            block.update(kind="table", label="Table 1", title="Table 1：表格标题")
            block["panel_explanations"] = [{"title": "统计结果汇总", "text": "解读。"}]

        result = self.run(tmp_path, mutate)
        assert not any("must carry the 1 panel label" in error for error in result["errors"])

    def test_table_label_and_title_conflict_is_an_error(self, tmp_path):
        def mutate(content):
            block = content["evidence_blocks"][0]
            block.update(
                kind="table",
                label="Table 2",
                title="Table 1：表格标题",
                panel_explanations=[{"title": "统计结果汇总", "text": "解读。"}],
            )

        result = self.run(tmp_path, mutate)
        assert any("does not match title object table:1" in error for error in result["errors"])

    def test_figure_panel_with_a_table_caption_is_an_error(self, tmp_path):
        result = self.run(
            tmp_path,
            lambda content: content["evidence_blocks"][0]["panel_explanations"][0].update(
                title="Table 1：表格图注"
            ),
        )
        assert any("does not belong to block object figure:1" in error for error in result["errors"])

    def test_unparseable_block_label_is_a_warning(self, tmp_path):
        def mutate(content):
            block = content["evidence_blocks"][0]
            block["label"] = "主图"
            block["title"] = "没有编号的主图标题"

        result = self.run(tmp_path, mutate)
        assert any("no parseable figure/table label" in warning for warning in result["warnings"])
