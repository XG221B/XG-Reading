#!/usr/bin/env python3
"""Audit the deterministic formatting contract of a Figure Evidence DOCX."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from build_reader_docx import (
    clean_text,
    evidence_label,
    figure_heading,
    image_dimensions,
    normalized_logic_text,
)
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

CN_FONT = "华文中宋"
LATIN_FONT = "Times New Roman"
CUSTOM_STYLES = {
    "FER Title",
    "FER Metadata",
    "FER Section",
    "FER Step",
    "FER Body",
    "FER Figure",
    "FER Figure Translation",
    "FER Supplement",
    "FER Picture",
    "FER Bullet",
}

CENTER = WD_ALIGN_PARAGRAPH.CENTER
LEFT = WD_ALIGN_PARAGRAPH.LEFT
JUSTIFY = WD_ALIGN_PARAGRAPH.JUSTIFY

STYLE_CONTRACT = {
    "FER Title": {
        "size": Pt(16), "bold": True, "alignment": CENTER,
        "line_spacing": 1.25, "space_after": Pt(8), "keep_with_next": False,
    },
    "FER Metadata": {
        "size": Pt(11), "bold": False, "alignment": CENTER,
        "line_spacing": 1.25, "space_after": Pt(12), "keep_with_next": False,
    },
    "FER Section": {
        "size": Pt(13), "bold": True, "alignment": CENTER,
        "line_spacing": 1.25, "space_before": Pt(10), "space_after": Pt(8),
        "keep_with_next": True, "widow_control": True,
    },
    "FER Step": {
        "size": Pt(11), "bold": True, "alignment": LEFT,
        "line_spacing": 1.25, "space_after": Pt(3),
        "keep_with_next": True, "widow_control": True,
    },
    "FER Body": {
        "size": Pt(11), "bold": False, "alignment": JUSTIFY,
        "line_spacing": 1.25, "space_after": Pt(6),
        "first_line_indent": Cm(0.74), "widow_control": True,
    },
    "FER Figure": {
        "size": Pt(13), "bold": True, "alignment": CENTER,
        "line_spacing": 1.25, "space_after": Pt(8),
        "keep_with_next": True, "widow_control": True,
    },
    "FER Figure Translation": {
        "size": Pt(11), "bold": True, "alignment": CENTER,
        "line_spacing": 1.25, "space_before": Pt(6), "space_after": Pt(4),
        "keep_with_next": True, "widow_control": True,
    },
    "FER Supplement": {
        "size": Pt(11), "bold": True, "alignment": CENTER,
        "line_spacing": 1.25, "space_after": Pt(2), "keep_with_next": True,
    },
    "FER Picture": {
        "size": Pt(11), "bold": False, "alignment": CENTER,
        "space_after": Pt(4),
    },
    "FER Bullet": {
        "size": Pt(11), "bold": False, "alignment": JUSTIFY,
        "line_spacing": 1.25, "space_after": Pt(5),
        "left_indent": Cm(0.74), "first_line_indent": Cm(-0.37),
        "widow_control": True,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--content", type=Path)
    parser.add_argument("--json-report", type=Path)
    return parser.parse_args()


def close_enough(actual, expected, tolerance: int = 1500) -> bool:
    return actual is not None and abs(int(actual) - int(expected)) <= tolerance


def line_spacing_close_enough(actual, expected) -> bool:
    return actual is not None and abs(float(actual) - float(expected)) <= 0.01


def inherited_font(style, attr: str):
    current = style
    while current is not None:
        rpr = current._element.rPr
        if rpr is not None and rpr.rFonts is not None:
            value = rpr.rFonts.get(qn(f"w:{attr}"))
            if value:
                return value
        current = current.base_style
    return None


def inherited_size(style):
    current = style
    while current is not None:
        if current.font.size is not None:
            return current.font.size
        current = current.base_style
    return None


def emu(value) -> int:
    return int(value) if value is not None else 0


def flag_set(actual, expected) -> bool:
    if expected:
        return actual is True
    return actual in (None, False)


def check_style_contract(
    document: Document, name: str, expected: dict, errors: list[str]
) -> None:
    if name not in document.styles:
        errors.append(f"Missing style: {name}")
        return
    style = document.styles[name]
    if not close_enough(inherited_size(style), expected["size"], tolerance=10):
        errors.append(f"Incorrect size for {name}")
    if style.paragraph_format.alignment != expected["alignment"]:
        errors.append(f"Incorrect alignment for {name}")
    if inherited_font(style, "ascii") != LATIN_FONT:
        errors.append(f"Incorrect Latin font for {name}")
    if inherited_font(style, "eastAsia") != CN_FONT:
        errors.append(f"Incorrect Chinese font for {name}")
    if not flag_set(style.font.bold, expected["bold"]):
        errors.append(f"Incorrect bold for {name}")
    paragraph_format = style.paragraph_format
    if "line_spacing" in expected and not line_spacing_close_enough(
        paragraph_format.line_spacing, expected["line_spacing"]
    ):
        errors.append(f"Incorrect line spacing for {name}")
    for attribute in ("space_before", "space_after", "first_line_indent", "left_indent"):
        if attribute not in expected:
            continue
        wanted = expected[attribute]
        actual = getattr(paragraph_format, attribute)
        if not close_enough(emu(actual), emu(wanted)):
            errors.append(f"Incorrect {attribute} for {name}")
    if "keep_with_next" in expected and not flag_set(
        paragraph_format.keep_with_next, expected["keep_with_next"]
    ):
        errors.append(f"Incorrect keep_with_next for {name}")
    if "widow_control" in expected and not flag_set(
        paragraph_format.widow_control, expected["widow_control"]
    ):
        errors.append(f"Incorrect widow_control for {name}")


def is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    haystack_index = 0
    for item in needle:
        while haystack_index < len(haystack) and haystack[haystack_index] != item:
            haystack_index += 1
        if haystack_index == len(haystack):
            return False
        haystack_index += 1
    return True


def build_expected_texts(data: dict) -> list[str]:
    expected = [clean_text(data["document_title"]), clean_text(data["citation"])]
    positioning = data["field_positioning"]
    expected.append(clean_text(positioning.get("heading") or "领域定位与本文解决的问题"))
    expected.extend(clean_text(item) for item in positioning["paragraphs"])
    expected.extend(clean_text(note) for note in data.get("bullet_notes") or [])
    expected.append(clean_text("整篇论文的图像逻辑链"))
    for step in data["logic_chain"]:
        expected.append(clean_text(step.get("title")))
        expected.append(normalized_logic_text(step.get("text")))
    future = data.get("future_outlook")
    if future is None:
        future = [
            *(data.get("limitations") or []),
            *(data.get("trends") or []),
        ]
    if future:
        expected.append(clean_text("未来展望"))
        for item in future:
            expected.append(clean_text(item.get("title")))
            expected.append(clean_text(item.get("text")))
    blocks = data.get("evidence_blocks") or data.get("figures") or []
    for index, block in enumerate(blocks, start=1):
        expected.append(clean_text(figure_heading(block, index)))
        expected.append(clean_text(block.get("paper_claim")))
        for panel in block["panel_explanations"]:
            if isinstance(panel, dict):
                expected.append(clean_text(panel["title"]))
                expected.append(clean_text(panel["text"]))
            else:
                expected.append(clean_text(panel))
        label = evidence_label(block, index)
        expected.append(clean_text(f"{label}总结：{block.get('logic_role')}"))
        support_text = clean_text(block.get("support_text"))
        if support_text:
            expected.append(clean_text(f"补充材料如何支撑：{support_text}"))
        if block.get("support_images"):
            expected.append(clean_text("相关补充材料组图"))
    return expected


def expected_image_widths(data: dict, content_dir: Path) -> list[tuple[str, int | None]]:
    """Expected widths per inline shape: exact for main images (recomputed with
    the same aspect limits the builder uses), a max bound for generated
    support sheets whose source images are not available to the audit."""
    widths: list[tuple[str, int | None]] = []
    blocks = data.get("evidence_blocks") or data.get("figures") or []
    for block in blocks:
        raw = clean_text(block.get("image"))
        exact = None
        if raw:
            path = Path(raw)
            if not path.is_absolute():
                path = content_dir / path
            try:
                width_cm, _ = image_dimensions(path, 15.5, 18.3)
                exact = int(Cm(width_cm))
            except (OSError, ValueError):
                exact = None
        widths.append(("exact", exact))
        if block.get("support_images"):
            widths.append(("max", int(Cm(14.6))))
    return widths


def check_spacer_positions(document: Document, errors: list[str]) -> None:
    paragraphs = document.paragraphs
    meaningful = [
        index
        for index, paragraph in enumerate(paragraphs)
        if paragraph.text.strip() or paragraph._p.xpath(".//w:drawing")
    ]

    def prev_meaningful(index):
        candidates = [position for position in meaningful if position < index]
        return candidates[-1] if candidates else None

    def next_meaningful(index):
        candidates = [position for position in meaningful if position > index]
        return candidates[0] if candidates else None

    for index, paragraph in enumerate(paragraphs):
        if paragraph.text.strip() or paragraph.style.name != "FER Body":
            continue
        if paragraph.paragraph_format.line_spacing != 0.2:
            continue
        previous = prev_meaningful(index)
        following = next_meaningful(index)
        if previous is None or following is None:
            errors.append(f"Panel spacer without neighboring text at paragraph {index}")
            continue
        previous_style = paragraphs[previous].style.name
        following_style = paragraphs[following].style.name
        if previous_style != "FER Body" or following_style != "FER Step":
            errors.append(f"Panel spacer not between panel text and panel title at paragraph {index}")
            continue
        before_previous = prev_meaningful(previous)
        if before_previous is None or paragraphs[before_previous].style.name != "FER Step":
            errors.append(f"Panel spacer after a non-panel paragraph at paragraph {index}")


def audit(docx_path: Path, content_path: Path | None):
    document = Document(docx_path)
    errors: list[str] = []
    warnings: list[str] = []

    if len(document.sections) != 1:
        errors.append(f"Expected 1 section, found {len(document.sections)}")
    section = document.sections[0]
    checks = {
        "page width": (section.page_width, Cm(21.59)),
        "page height": (section.page_height, Cm(27.94)),
        "top margin": (section.top_margin, Cm(2.0)),
        "bottom margin": (section.bottom_margin, Cm(2.0)),
        "left margin": (section.left_margin, Cm(2.3)),
        "right margin": (section.right_margin, Cm(2.3)),
    }
    for label, (actual, expected) in checks.items():
        if not close_enough(actual, expected):
            errors.append(f"Incorrect {label}: {actual}, expected {expected}")

    for name in CUSTOM_STYLES:
        check_style_contract(document, name, STYLE_CONTRACT[name], errors)

    for name in CUSTOM_STYLES:
        if name == "FER Figure" or name not in document.styles:
            continue
        if document.styles[name].paragraph_format.page_break_before is True:
            errors.append(f"Unexpected page break before style {name}")

    if "FER Figure" in document.styles:
        figure_style = document.styles["FER Figure"]
        if figure_style.paragraph_format.page_break_before is not True:
            errors.append("FER Figure must start on a new page")

    cjk = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    boundary_space = re.compile(
        rf"(?:[{cjk}]\s+[A-Za-z0-9]|[A-Za-z0-9]\s+[{cjk}])"
    )
    figure_headings = 0
    translated_figure_headings = 0
    panel_spacers = 0
    forbidden_prompts = (
        "论文中的说法：",
        "图上如何体现：",
        "这张图在论文逻辑中的位置：",
    )
    for index, paragraph in enumerate(document.paragraphs):
        text = paragraph.text.strip()
        if not text and paragraph.style.name == "FER Body":
            if paragraph.paragraph_format.line_spacing == 0.2:
                panel_spacers += 1
                if paragraph.paragraph_format.first_line_indent != Cm(0):
                    errors.append(
                        f"Panel spacer first-line indent is not zero at paragraph {index}"
                    )
            elif not paragraph._p.xpath(".//w:drawing"):
                errors.append(f"Unexpected blank FER Body paragraph at paragraph {index}")
        if not text and not paragraph._p.xpath(".//w:drawing"):
            continue
        style_name = paragraph.style.name
        if style_name.startswith("Heading") or style_name == "Title":
            errors.append(f"Collapsible built-in heading style at paragraph {index}")
        if text and style_name not in CUSTOM_STYLES:
            errors.append(
                f"Unexpected paragraph style {style_name!r} at paragraph {index}"
            )
        if style_name == "FER Figure":
            figure_headings += 1
        if style_name == "FER Figure Translation":
            translated_figure_headings += 1
        if any(text.startswith(prompt) for prompt in forbidden_prompts):
            errors.append(f"Deprecated prompt at paragraph {index}: {text}")
        if boundary_space.search(text):
            errors.append(f"Chinese-Latin boundary space at paragraph {index}")

        for run in paragraph.runs:
            if not run.text.strip():
                continue
            rpr = run._element.rPr
            if rpr is None or rpr.rFonts is None:
                errors.append(f"Missing explicit run fonts at paragraph {index}")
                continue
            if rpr.rFonts.get(qn("w:ascii")) != LATIN_FONT:
                errors.append(f"Wrong run Latin font at paragraph {index}")
            if rpr.rFonts.get(qn("w:eastAsia")) != CN_FONT:
                errors.append(f"Wrong run Chinese font at paragraph {index}")
            color = run.font.color.rgb
            if color is not None and str(color) != "000000":
                errors.append(f"Non-black text at paragraph {index}")

    check_spacer_positions(document, errors)

    for section in document.sections:
        for part_name, part in (("header", section.header), ("footer", section.footer)):
            if any(paragraph.text.strip() for paragraph in part.paragraphs):
                errors.append(f"Non-empty {part_name} text is not allowed")

    for index, paragraph in enumerate(document.paragraphs):
        text_runs = [run for run in paragraph.runs if run.text.strip()]
        if len(text_runs) >= 2:
            if text_runs[0].bold is not True:
                errors.append(f"Multi-run paragraph label not bold at paragraph {index}")
            if any(run.bold is True for run in text_runs[1:]):
                errors.append(f"Multi-run paragraph body run bold at paragraph {index}")

    if content_path:
        with content_path.open("r", encoding="utf-8-sig") as stream:
            content = json.load(stream)
        evidence_blocks = content.get("evidence_blocks") or content.get("figures") or []
        expected_figures = len(evidence_blocks)
        if figure_headings != expected_figures:
            errors.append(
                f"Figure heading count {figure_headings} != expected {expected_figures}"
            )
        if translated_figure_headings:
            errors.append(
                "Separate translated figure-title paragraphs are no longer allowed"
            )
        expected_panel_spacers = sum(
            max(len(figure.get("panel_explanations") or []) - 1, 0)
            for figure in evidence_blocks
        )
        if panel_spacers != expected_panel_spacers:
            errors.append(
                f"Panel spacer count {panel_spacers} != expected {expected_panel_spacers}"
            )
        expected_images = expected_figures + sum(
            1 for figure in evidence_blocks if figure.get("support_images")
        )
        if len(document.inline_shapes) != expected_images:
            errors.append(
                f"Inline image count {len(document.inline_shapes)} != expected {expected_images}"
            )
        widths = expected_image_widths(content, content_path.parent)
        if len(document.inline_shapes) == len(widths):
            for shape_index, shape in enumerate(document.inline_shapes):
                kind, expected_width = widths[shape_index]
                if expected_width is None:
                    continue
                if kind == "exact":
                    if not close_enough(shape.width, expected_width, tolerance=20000):
                        errors.append(
                            f"Inline image {shape_index + 1} width "
                            f"{shape.width} != expected {expected_width}"
                        )
                elif shape.width > expected_width + 20000:
                    errors.append(
                        f"Inline image {shape_index + 1} width "
                        f"{shape.width} exceeds support-sheet bound {expected_width}"
                    )
        doc_texts = [
            clean_text(paragraph.text)
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]
        expected_texts = build_expected_texts(content)
        if not is_subsequence(expected_texts, doc_texts):
            errors.append(
                "DOCX text is missing or altered relative to content.json"
            )
        if not is_subsequence(doc_texts, expected_texts):
            errors.append(
                "DOCX contains text not present in content.json"
            )

    if not Path("C:/Windows/Fonts/STZHONGS.TTF").exists():
        warnings.append("华文中宋字体文件未在Windows标准字体目录中找到")

    return {
        "docx": str(docx_path.resolve()),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "paragraphs": len(document.paragraphs),
        "images": len(document.inline_shapes),
        "figure_headings": figure_headings,
        "translated_figure_headings": translated_figure_headings,
        "panel_spacers": panel_spacers,
    }


def main() -> None:
    args = parse_args()
    report = audit(args.docx.resolve(), args.content.resolve() if args.content else None)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(rendered, encoding="utf-8")
    if report["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
