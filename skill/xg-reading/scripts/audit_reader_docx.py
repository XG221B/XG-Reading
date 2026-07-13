#!/usr/bin/env python3
"""Audit the deterministic formatting contract of a Figure Evidence DOCX."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--content", type=Path)
    parser.add_argument("--json-report", type=Path)
    return parser.parse_args()


def close_enough(actual, expected, tolerance: int = 1500) -> bool:
    return actual is not None and abs(int(actual) - int(expected)) <= tolerance


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
        if name not in document.styles:
            errors.append(f"Missing style: {name}")

    expected_styles = {
        "FER Title": (Pt(16), WD_ALIGN_PARAGRAPH.CENTER),
        "FER Metadata": (Pt(11), WD_ALIGN_PARAGRAPH.CENTER),
        "FER Section": (Pt(13), WD_ALIGN_PARAGRAPH.CENTER),
        "FER Step": (Pt(11), WD_ALIGN_PARAGRAPH.LEFT),
        "FER Body": (Pt(11), WD_ALIGN_PARAGRAPH.JUSTIFY),
        "FER Figure": (Pt(13), WD_ALIGN_PARAGRAPH.LEFT),
        "FER Figure Translation": (Pt(11), WD_ALIGN_PARAGRAPH.CENTER),
        "FER Supplement": (Pt(10.5), WD_ALIGN_PARAGRAPH.CENTER),
        "FER Picture": (Pt(11), WD_ALIGN_PARAGRAPH.CENTER),
        "FER Bullet": (Pt(11), WD_ALIGN_PARAGRAPH.JUSTIFY),
    }
    for name, (size, alignment) in expected_styles.items():
        if name not in document.styles:
            continue
        style = document.styles[name]
        if not close_enough(inherited_size(style), size, tolerance=10):
            errors.append(f"Incorrect size for {name}")
        if style.paragraph_format.alignment != alignment:
            errors.append(f"Incorrect alignment for {name}")
        if inherited_font(style, "ascii") != LATIN_FONT:
            errors.append(f"Incorrect Latin font for {name}")
        if inherited_font(style, "eastAsia") != CN_FONT:
            errors.append(f"Incorrect Chinese font for {name}")

    body_style = document.styles["FER Body"]
    if not close_enough(body_style.paragraph_format.first_line_indent, Cm(0.74)):
        errors.append("FER Body first-line indent is not 0.74 cm")
    if body_style.paragraph_format.line_spacing != 1.25:
        errors.append("FER Body line spacing is not 1.25")

    figure_style = document.styles["FER Figure"]
    if figure_style.paragraph_format.page_break_before is not True:
        errors.append("FER Figure must start on a new page")

    cjk = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    boundary_space = re.compile(
        rf"(?:[{cjk}]\s+[A-Za-z0-9]|[A-Za-z0-9]\s+[{cjk}])"
    )
    figure_headings = 0
    translated_figure_headings = 0
    forbidden_prompts = (
        "论文中的说法：",
        "图上如何体现：",
        "这张图在论文逻辑中的位置：",
    )
    for index, paragraph in enumerate(document.paragraphs):
        text = paragraph.text.strip()
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

    if content_path:
        with content_path.open("r", encoding="utf-8-sig") as stream:
            content = json.load(stream)
        evidence_blocks = content.get("evidence_blocks") or content.get("figures") or []
        expected_figures = len(evidence_blocks)
        if figure_headings != expected_figures:
            errors.append(
                f"Figure heading count {figure_headings} != expected {expected_figures}"
            )
        if translated_figure_headings != expected_figures:
            errors.append(
                f"Translated figure heading count {translated_figure_headings} != expected {expected_figures}"
            )
        expected_images = expected_figures + sum(
            1 for figure in evidence_blocks if figure.get("support_images")
        )
        if len(document.inline_shapes) != expected_images:
            errors.append(
                f"Inline image count {len(document.inline_shapes)} != expected {expected_images}"
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
    }


def main() -> None:
    args = parse_args()
    report = audit(args.docx.resolve(), args.content.resolve() if args.content else None)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(rendered, encoding="utf-8")
    if report["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
