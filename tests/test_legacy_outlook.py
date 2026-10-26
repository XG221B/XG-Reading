"""Regression tests for A09: legacy limitations/trends are not silently
promoted to author-grounded future outlook.

Legacy JSON still builds, but preflight and audit warn that the section was not
verified against the authors' Discussion/Conclusion. New content should use
``future_outlook`` with source locations.
"""

from __future__ import annotations

import json

import audit_reader_docx as audit
import build_reader_docx as builder
import preflight_content as preflight
from docx import Document
from PIL import Image


def make_content(tmp_path, *, future_outlook=None, limitations=None, trends=None):
    Image.new("RGB", (80, 80), "white").save(tmp_path / "fig1.png")
    content = {
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
                "image": "fig1.png",
                "paper_claim": "作者对该证据块的主要表述。",
                "panel_explanations": [
                    {"title": "Fig.1A：该panel图注内容的中文译名", "text": "读图方法。"}
                ],
                "logic_role": "该证据块在全文论证中的作用。",
            }
        ],
    }
    if future_outlook is not None:
        content["future_outlook"] = future_outlook
    if limitations is not None:
        content["limitations"] = limitations
    if trends is not None:
        content["trends"] = trends
    return content


LEGACY_LIMITATIONS = [{"title": "第一，作者明确提出的未解决问题。", "text": "见讨论部分的原文依据。"}]
MODERN_OUTLOOK = [{"title": "第一，作者明确提出的未解决问题。", "text": "见讨论部分的原文依据。"}]


def write_content(tmp_path, content):
    path = tmp_path / "content.json"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return path


class TestPreflightLegacyOutlook:
    def test_legacy_limitations_warn_not_error(self, tmp_path):
        content = make_content(tmp_path, limitations=LEGACY_LIMITATIONS)
        result = preflight.check_content(content, tmp_path)
        assert result["errors"] == []
        assert any(
            "legacy limitations/trends" in warning for warning in result["warnings"]
        )

    def test_legacy_trends_warn_not_error(self, tmp_path):
        content = make_content(tmp_path, trends=LEGACY_LIMITATIONS)
        result = preflight.check_content(content, tmp_path)
        assert result["errors"] == []
        assert any(
            "legacy limitations/trends" in warning for warning in result["warnings"]
        )

    def test_modern_future_outlook_has_no_legacy_warning(self, tmp_path):
        content = make_content(
            tmp_path,
            future_outlook=MODERN_OUTLOOK,
            limitations=LEGACY_LIMITATIONS,
        )
        result = preflight.check_content(content, tmp_path)
        assert not any(
            "legacy limitations/trends" in warning for warning in result["warnings"]
        )

    def test_future_outlook_must_be_an_array(self, tmp_path):
        content = make_content(tmp_path, future_outlook={"title": "not a list"})
        result = preflight.check_content(content, tmp_path)
        assert any(
            "future_outlook must be an array" in error for error in result["errors"]
        )


class TestAuditLegacyOutlook:
    def test_legacy_content_builds_and_audits_with_warning(self, tmp_path):
        content = make_content(tmp_path, limitations=LEGACY_LIMITATIONS)
        content_path = write_content(tmp_path, content)
        docx_path = tmp_path / "reader.docx"
        builder.build_document(content, builder.DEFAULT_TEMPLATE, tmp_path, docx_path)

        report = audit.audit(docx_path, content_path)
        assert report["errors"] == []
        assert any(
            "legacy limitations/trends" in warning for warning in report["warnings"]
        )

        paragraphs = [paragraph.text for paragraph in Document(docx_path).paragraphs]
        assert "未来展望" in paragraphs
        assert LEGACY_LIMITATIONS[0]["title"] in paragraphs

    def test_modern_future_outlook_audits_without_legacy_warning(self, tmp_path):
        content = make_content(tmp_path, future_outlook=MODERN_OUTLOOK)
        content_path = write_content(tmp_path, content)
        docx_path = tmp_path / "reader.docx"
        builder.build_document(content, builder.DEFAULT_TEMPLATE, tmp_path, docx_path)
        report = audit.audit(docx_path, content_path)
        assert report["errors"] == []
        assert not any(
            "legacy limitations/trends" in warning for warning in report["warnings"]
        )
