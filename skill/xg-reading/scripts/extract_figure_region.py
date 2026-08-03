#!/usr/bin/env python3
"""Extract a complete paper figure and caption without leaking following body text."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


@dataclass
class TextLine:
    text: str
    start: int
    end: int
    left: float
    bottom: float
    right: float
    top: float
    glyph_height: float

    @property
    def center(self) -> float:
        return (self.bottom + self.top) / 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crop one complete figure and its caption from a PDF page using "
            "caption text coordinates rather than a fixed bottom boundary."
        )
    )
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True, type=int, help="1-based PDF page")
    parser.add_argument(
        "--label", required=True, help='Caption label, for example "Fig. 2"'
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=3.0)
    parser.add_argument(
        "--top-from-page",
        type=float,
        help="Manual crop top in PDF points measured from the page top",
    )
    parser.add_argument("--left", type=float, default=18.0)
    parser.add_argument("--right", type=float, default=18.0)
    parser.add_argument("--caption-padding", type=float, default=4.0)
    parser.add_argument("--allow-low-confidence", action="store_true")
    return parser.parse_args()


def caption_search_terms(label: str) -> list[str]:
    number = re.search(r"\d+[A-Za-z]?", label)
    if not number:
        return [label.strip()]
    token = number.group(0)
    return [f"Fig. {token}", f"Fig.{token}", f"Figure {token}"]


def find_caption_start(text_page, label: str) -> int:
    candidates = []
    for term in caption_search_terms(label):
        searcher = text_page.search(term, match_case=False, match_whole_word=False)
        while True:
            occurrence = searcher.get_next()
            if occurrence is None:
                break
            start, count = occurrence
            before_start = max(0, start - 3)
            before = text_page.get_text_range(before_start, start - before_start)
            after = text_page.get_text_range(start + count, 12)
            stripped = after.lstrip()
            score = 0
            if stripped.startswith("|"):
                score += 10
            elif stripped.startswith((":", ".", "-")):
                score += 5
            if "\n" in before or "\r" in before or start == 0:
                score += 3
            if stripped and stripped[0].isalnum():
                score -= 8
            candidates.append((score, start, term, after))
    if not candidates:
        raise ValueError(f"Caption label not found: {label}")
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    score, start, _, _ = candidates[0]
    if score < 3:
        raise ValueError(
            f"Only in-text references were found for {label}; caption marker is uncertain"
        )
    return start


def split_lines(text_page, start: int) -> list[TextLine]:
    lines: list[TextLine] = []
    characters: list[str] = []
    boxes = []
    heights = []
    line_start = start

    def flush(line_end: int) -> None:
        nonlocal characters, boxes, heights, line_start
        visible = "".join(characters).strip()
        if visible and boxes:
            lines.append(
                TextLine(
                    text=visible,
                    start=line_start,
                    end=line_end,
                    left=min(box[0] for box in boxes),
                    bottom=min(box[1] for box in boxes),
                    right=max(box[2] for box in boxes),
                    top=max(box[3] for box in boxes),
                    glyph_height=statistics.median(heights),
                )
            )
        characters = []
        boxes = []
        heights = []
        line_start = line_end + 1

    for index in range(start, text_page.count_chars()):
        character = text_page.get_text_range(index, 1)
        if character in {"\r", "\n"}:
            flush(index)
            continue
        characters.append(character)
        if character.isspace():
            continue
        try:
            box = text_page.get_charbox(index)
        except Exception:
            continue
        boxes.append(box)
        heights.append(max(0.0, box[3] - box[1]))
    if characters:
        flush(text_page.count_chars())
    return lines


def cluster_lines(lines: list[TextLine], tolerance: float = 2.0):
    clusters: list[dict] = []
    for line in sorted(lines, key=lambda item: item.center, reverse=True):
        target = None
        for cluster in clusters:
            if abs(cluster["center"] - line.center) <= tolerance:
                target = cluster
                break
        if target is None:
            clusters.append({"center": line.center, "lines": [line]})
        else:
            target["lines"].append(line)
            target["center"] = statistics.mean(
                item.center for item in target["lines"]
            )
    return sorted(clusters, key=lambda item: item["center"], reverse=True)


def detect_caption(text_page, label: str, page_height: float):
    caption_start = find_caption_start(text_page, label)
    lines = split_lines(text_page, caption_start)
    if not lines:
        raise ValueError(f"Caption line coordinates could not be recovered: {label}")
    start_line = lines[0]
    later_lines = [
        line
        for line in lines
        if line.center <= start_line.center + 3.0
        and 25.0 < line.center < page_height - 25.0
    ]
    clusters = cluster_lines(later_lines)
    start_cluster_index = min(
        range(len(clusters)),
        key=lambda index: abs(clusters[index]["center"] - start_line.center),
    )
    clusters = clusters[start_cluster_index:]
    if not clusters:
        raise ValueError("No caption line clusters were found")

    preliminary_gaps = [
        clusters[index]["center"] - clusters[index + 1]["center"]
        for index in range(min(len(clusters) - 1, 8))
        if 3.0
        < clusters[index]["center"] - clusters[index + 1]["center"]
        < 22.0
    ]
    line_spacing = statistics.median(preliminary_gaps) if preliminary_gaps else 10.0
    caption_height = statistics.median(
        line.glyph_height for line in clusters[0]["lines"]
    )
    boundary_index = len(clusters) - 1
    boundary_reason = "end_of_text_region"
    boundary_gap = None

    for index in range(len(clusters) - 1):
        current = clusters[index]
        following = clusters[index + 1]
        gap = current["center"] - following["center"]
        following_height = statistics.median(
            line.glyph_height for line in following["lines"]
        )
        large_gap = gap >= max(14.0, 1.55 * line_spacing)
        body_size_shift = (
            gap >= 1.08 * line_spacing and following_height >= 1.18 * caption_height
        )
        if large_gap or body_size_shift:
            boundary_index = index
            boundary_gap = gap
            boundary_reason = "large_vertical_gap" if large_gap else "body_font_shift"
            break

    caption_clusters = clusters[: boundary_index + 1]
    caption_min_center = caption_clusters[-1]["center"] - 2.1
    caption_max_center = caption_clusters[0]["center"] + 2.1
    caption_lines = [
        line
        for line in later_lines
        if caption_min_center <= line.center <= caption_max_center
    ]
    caption_bottom = min(line.bottom for line in caption_lines)
    caption_top = max(line.top for line in caption_lines)

    next_cluster = (
        clusters[boundary_index + 1]
        if boundary_index + 1 < len(clusters)
        else None
    )
    next_text_top = (
        max(line.top for line in next_cluster["lines"]) if next_cluster else None
    )
    next_text = (
        " ".join(line.text for line in next_cluster["lines"]) if next_cluster else ""
    )

    caption_text = " ".join(
        line.text for line in sorted(caption_lines, key=lambda item: item.start)
    )
    confidence = "high"
    warnings: list[str] = []
    if len(caption_lines) < 2:
        confidence = "medium"
        warnings.append("Caption contains only one detected line")
    if boundary_reason == "end_of_text_region":
        confidence = "medium"
        warnings.append("No following text block was available for boundary confirmation")
    if not re.match(r"(?i)\s*(?:fig|figure)", caption_text):
        confidence = "low"
        warnings.append("Recovered caption text does not begin with a Figure label")

    return {
        "caption_bottom": caption_bottom,
        "caption_top": caption_top,
        "caption_text": caption_text,
        "caption_line_count": len(caption_lines),
        "line_spacing": line_spacing,
        "boundary_reason": boundary_reason,
        "boundary_gap": boundary_gap,
        "next_text_top": next_text_top,
        "next_text_preview": next_text[:180],
        "confidence": confidence,
        "warnings": warnings,
    }


def detect_top(image: Image.Image, left: int, right: int, caption_top: int):
    height = image.height
    limit = min(int(height * 0.28), max(1, int(caption_top * 0.55)))
    # Convert the scanned region once instead of per row, keeping the exact
    # same < 242 luminance threshold and the same (left, right) column slice.
    region = image.crop((0, 0, image.width, limit)).convert("L")
    getter = getattr(region, "get_flattened_data", region.getdata)
    pixels = list(getter())
    row_width = region.width
    span = max(1, right - left)
    blank = []
    for y in range(limit):
        start = y * row_width + left
        row = pixels[start : start + span]
        ink = sum(value < 242 for value in row) / span
        blank.append(ink <= 0.0035)
    runs = []
    start = None
    for index, is_blank in enumerate(blank + [False]):
        if is_blank and start is None:
            start = index
        elif not is_blank and start is not None:
            if index - start >= max(6, int(height * 0.006)):
                runs.append((start, index))
            start = None

    interior = [run for run in runs if run[0] >= int(height * 0.025)]
    if interior:
        top = interior[0][1] + 2
        return top, "medium", "first_page_wide_whitespace_below_header"
    if runs and runs[0][0] == 0:
        return runs[0][1] + 2, "medium", "page_top_whitespace"
    return int(height * 0.04), "low", "fixed_top_fallback"


def caption_for_page(page, page_height: float, label: str) -> dict:
    """Detect the caption region from the page text layer (no rendering)."""
    text_page = page.get_textpage()
    return detect_caption(text_page, label, page_height)


def crop_from_rendered(
    rendered: Image.Image,
    page_width: float,
    page_height: float,
    caption: dict,
    label: str,
    output: Path,
    *,
    scale: float,
    left: float,
    right: float,
    caption_padding: float,
    top_from_page: float | None,
    allow_low_confidence: bool,
) -> dict:
    """Crop the figure from an already-rendered page and build the report."""
    crop_bottom_pdf = caption["caption_bottom"] - caption_padding
    if caption["next_text_top"] is not None:
        crop_bottom_pdf = max(
            crop_bottom_pdf, caption["next_text_top"] + 1.5
        )

    left_px = max(0, math.floor(left * scale))
    right_px = min(
        rendered.width, math.ceil((page_width - right) * scale)
    )
    caption_top_px = math.floor((page_height - caption["caption_top"]) * scale)
    bottom_px = min(
        rendered.height,
        math.ceil((page_height - crop_bottom_pdf) * scale),
    )

    if top_from_page is None:
        top_px, top_confidence, top_reason = detect_top(
            rendered, left_px, right_px, caption_top_px
        )
    else:
        top_px = max(0, math.floor(top_from_page * scale))
        top_confidence = "high"
        top_reason = "manual_pdf_coordinate"

    if top_px >= caption_top_px:
        caption["warnings"].append("Detected top overlaps the caption region")
        caption["confidence"] = "low"
    if bottom_px <= caption_top_px:
        caption["warnings"].append("Detected bottom does not contain the caption")
        caption["confidence"] = "low"
    if top_confidence == "low":
        caption["warnings"].append("Figure top used a fixed fallback")
        if caption["confidence"] == "high":
            caption["confidence"] = "medium"

    if caption["confidence"] == "low" and not allow_low_confidence:
        raise ValueError(
            "Low-confidence figure boundary detection; inspect the PDF and rerun "
            "with --top-from-page or --allow-low-confidence"
        )

    cropped = rendered.crop((left_px, top_px, right_px, bottom_px))
    output.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(output, optimize=True)

    return {
        "label": label,
        "output": str(output.resolve()),
        "confidence": caption["confidence"],
        "warnings": caption["warnings"],
        "caption_text": caption["caption_text"],
        "caption_line_count": caption["caption_line_count"],
        "caption_boundary_reason": caption["boundary_reason"],
        "caption_gap_points": caption["boundary_gap"],
        "next_text_preview": caption["next_text_preview"],
        "top_detection": {"confidence": top_confidence, "reason": top_reason},
        "crop_box_pixels": [left_px, top_px, right_px, bottom_px],
        "rendered_page_pixels": [rendered.width, rendered.height],
    }


def extract_figure(
    pdf: pdfium.PdfDocument,
    pdf_path: Path,
    page_index: int,
    label: str,
    output: Path,
    *,
    scale: float = 3.0,
    left: float = 18.0,
    right: float = 18.0,
    caption_padding: float = 4.0,
    top_from_page: float | None = None,
    allow_low_confidence: bool = False,
) -> dict:
    """Crop one figure and caption, returning the identical report dict that
    the single-figure CLI prints and stores as ``<output>.crop.json``."""
    if not 1 <= page_index <= len(pdf):
        raise ValueError(f"page must be between 1 and {len(pdf)}")
    page = pdf[page_index - 1]
    page_width, page_height = page.get_size()
    caption = caption_for_page(page, page_height, label)
    rendered = page.render(scale=scale).to_pil().convert("RGB")
    report = crop_from_rendered(
        rendered,
        page_width,
        page_height,
        caption,
        label,
        output,
        scale=scale,
        left=left,
        right=right,
        caption_padding=caption_padding,
        top_from_page=top_from_page,
        allow_low_confidence=allow_low_confidence,
    )
    return {
        "pdf": str(pdf_path.resolve()),
        "page": page_index,
        **report,
    }


def main() -> None:
    args = parse_args()
    pdf = pdfium.PdfDocument(args.pdf.resolve())
    report = extract_figure(
        pdf,
        args.pdf,
        args.page,
        args.label,
        args.output,
        scale=args.scale,
        left=args.left,
        right=args.right,
        caption_padding=args.caption_padding,
        top_from_page=args.top_from_page,
        allow_low_confidence=args.allow_low_confidence,
    )
    report_path = args.output.with_suffix(args.output.suffix + ".crop.json")
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
