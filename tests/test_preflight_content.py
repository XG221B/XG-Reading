import json

import preflight_content as preflight
from PIL import Image


def make_content(tmp_path, **overrides):
    image = tmp_path / "fig1.png"
    Image.new("RGB", (80, 80), "white").save(image)
    content = {
        "document_title": "题目与逐图解读",
        "citation": "论文：Author et al., Title, Journal,Year",
        "field_positioning": {
            "heading": "领域定位与本文解决的问题",
            "paragraphs": ["领域问题", "具体缺口", "本文贡献与边界"],
        },
        "logic_chain": [
            {
                "title": "Step1：为什么需要这一步",
                "text": "对应Fig.1：实验、结果及其支持的结论。",
            }
        ],
        "evidence_blocks": [
            {
                "kind": "figure",
                "label": "Fig.1",
                "title": "Figure 1：主图英文标题的准确中文翻译",
                "image": "fig1.png",
                "paper_claim": "作者对该证据块的主要表述。",
                "panel_explanations": [
                    {"title": "Fig.1A：该panel图注内容的中文译名", "text": "Fig.1A的读图方法与意义。"}
                ],
                "logic_role": "该证据块在全文论证中的作用。",
            }
        ],
    }
    content.update(overrides)
    return content


def run(data, tmp_path):
    return preflight.check_content(data, tmp_path)


class TestValidContent:
    def test_valid_content_passes(self, tmp_path):
        result = run(make_content(tmp_path), tmp_path)
        assert result["errors"] == []
        assert result["warnings"] == []

    def test_legacy_string_panel_is_warning_only(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["panel_explanations"] = ["一段纯文本解读。"]
        result = run(content, tmp_path)
        assert result["errors"] == []
        assert any("legacy" in warning for warning in result["warnings"])

    def test_markdown_marker_is_warning_only(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["paper_claim"] = "作者用**强调**的表述。"
        result = run(content, tmp_path)
        assert result["errors"] == []
        assert any("markdown" in warning.lower() for warning in result["warnings"])


class TestRequiredFields:
    def test_missing_document_title(self, tmp_path):
        content = make_content(tmp_path)
        del content["document_title"]
        result = run(content, tmp_path)
        assert any("document_title" in error for error in result["errors"])

    def test_empty_paragraphs(self, tmp_path):
        content = make_content(tmp_path)
        content["field_positioning"]["paragraphs"] = []
        result = run(content, tmp_path)
        assert any("field_positioning" in error for error in result["errors"])


class TestLogicChain:
    def test_text_must_start_with_evidence_label(self, tmp_path):
        content = make_content(tmp_path)
        content["logic_chain"][0]["text"] = "首先做了实验。"
        result = run(content, tmp_path)
        assert any("对应Fig" in error for error in result["errors"])

    def test_colon_and_full_stop_separators_accepted(self, tmp_path):
        for separator in ("：", "。", ":"):
            content = make_content(tmp_path)
            content["logic_chain"][0]["text"] = f"对应Table 2{separator}内容。"
            result = run(content, tmp_path)
            assert result["errors"] == []


class TestEvidenceBlocks:
    def test_title_must_start_with_figure_label(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["title"] = "没有标签的标题"
        result = run(content, tmp_path)
        assert any("title" in error for error in result["errors"])

    def test_panel_title_must_carry_block_number(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["panel_explanations"][0]["title"] = "第一个panel"
        result = run(content, tmp_path)
        assert any("panel" in error for error in result["errors"])

    def test_table_block_skips_panel_label_check(self, tmp_path):
        content = make_content(tmp_path)
        block = content["evidence_blocks"][0]
        block["kind"] = "table"
        block["label"] = "Table 1"
        block["title"] = "Table 1：表格标题"
        block["panel_explanations"] = [
            {"title": "统计结果汇总", "text": "表格解读。"}
        ]
        result = run(content, tmp_path)
        assert result["errors"] == []

    def test_missing_image_file(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["image"] = "nope.png"
        result = run(content, tmp_path)
        assert any("image" in error for error in result["errors"])

    def test_empty_panel_list(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["panel_explanations"] = []
        result = run(content, tmp_path)
        assert any("panel" in error for error in result["errors"])


class TestForbiddenContent:
    def test_forbidden_prompt_detected(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["paper_claim"] = "论文中的说法：作者认为。"
        result = run(content, tmp_path)
        assert any("论文中的说法" in error for error in result["errors"])

    def test_boundary_space_detected(self, tmp_path):
        content = make_content(tmp_path)
        content["evidence_blocks"][0]["panel_explanations"][0]["text"] = "细胞 A 的荧光"
        result = run(content, tmp_path)
        assert any("边界" in error for error in result["errors"])

    def test_boundary_space_in_nested_field_detected(self, tmp_path):
        content = make_content(tmp_path)
        content["logic_chain"][0]["title"] = "Step1：Figure 1 的验证"
        result = run(content, tmp_path)
        assert any("边界" in error for error in result["errors"])


class TestCli:
    def test_cli_writes_report_and_exit_code(self, tmp_path, capsys):
        content_path = tmp_path / "content.json"
        content_path.write_text(
            json.dumps(make_content(tmp_path), ensure_ascii=False), encoding="utf-8"
        )
        assert preflight.main_with_args(["--content", str(content_path)]) == 0
        output = capsys.readouterr().out
        assert '"errors"' in output

    def test_cli_nonzero_on_errors(self, tmp_path, capsys):
        content = make_content(tmp_path)
        content["document_title"] = " "
        content_path = tmp_path / "content.json"
        content_path.write_text(
            json.dumps(content, ensure_ascii=False), encoding="utf-8"
        )
        assert preflight.main_with_args(["--content", str(content_path)]) == 1
