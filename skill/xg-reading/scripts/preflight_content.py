#!/usr/bin/env python3
"""Preflight a content.json against the reader contract before building.

Catches the audit-contract violations that would otherwise only surface
after a DOCX build and audit cycle: required fields, evidence-label formats,
panel title labels, forbidden prompts, Chinese-Latin boundary spaces, and
unresolvable image paths. Emits a JSON report and exits non-zero on errors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from build_reader_docx import clean_text
from label_utils import parse_label

HEADING_PATTERN = re.compile(
    r"^(?:Figure|Fig\.?|Table)\s*\d+[A-Za-z]?\s*[：:]", re.IGNORECASE
)
BLOCK_NUMBER_PATTERN = re.compile(
    r"(?:Figure|Fig\.?|Table)\s*(\d+[A-Za-z]?)", re.IGNORECASE
)
PANEL_LABEL_PATTERN = re.compile(r"Fig\.?\s*\d+[A-Za-z]?", re.IGNORECASE)
LOGIC_START_PATTERN = re.compile(
    r"^对应(?:Fig\.?|Figure|Table)\s*\d+[A-Za-z]?[：:。]"
)
CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
BOUNDARY_SPACE = re.compile(
    rf"(?:[{CJK}]\s+[A-Za-z0-9]|[A-Za-z0-9]\s+[{CJK}])"
)
MARKDOWN_MARKER = re.compile(r"\*\*|`|^#{1,6}\s", re.MULTILINE)
FORBIDDEN_PROMPTS = (
    "论文中的说法：",
    "图上如何体现：",
    "这张图在论文逻辑中的位置：",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate content.json against the reader contract without building."
    )
    parser.add_argument("--content", required=True, type=Path)
    return parser.parse_args(argv)


def collect_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from collect_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from collect_strings(item)


def resolve_image(raw: str, base_dir: Path) -> Path | None:
    path = Path(raw)
    if not path.is_absolute():
        path = base_dir / path
    try:
        resolved = path.resolve()
    except OSError:
        return None
    return resolved if resolved.exists() else None


def check_materials(
    data: dict[str, Any], base_dir: Path, errors: list[str], warnings: list[str]
) -> None:
    materials = data.get("materials")
    if materials is None:
        warnings.append(
            "materials section absent: required for papers centered on an "
            "engineered material, device, or micro/nanorobotic system"
        )
        return
    if not isinstance(materials, dict):
        errors.append("materials must be an object")
        return
    heading = materials.get("heading")
    if heading is not None and not clean_text(heading):
        errors.append("materials.heading must be non-empty when present")
    items = materials.get("items")
    if not isinstance(items, list) or not items:
        errors.append("materials.items must be a non-empty array")
    else:
        for index, item in enumerate(items, start=1):
            prefix = f"materials.items[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for key in ("name", "role"):
                if not clean_text(item.get(key)):
                    errors.append(f"{prefix}.{key} is required")
    if not clean_text(materials.get("summary")):
        errors.append("materials.summary is required")
    structure = materials.get("structure")
    if structure is not None:
        if not isinstance(structure, dict):
            errors.append("materials.structure must be an object")
        else:
            for key in ("title", "image", "explanation"):
                if not clean_text(structure.get(key)):
                    errors.append(f"materials.structure.{key} is required")
            image = clean_text(structure.get("image"))
            if image and resolve_image(image, base_dir) is None:
                errors.append(f"materials.structure.image cannot be resolved: {image}")


def check_block_label(
    block: dict[str, Any], prefix: str, errors: list[str], warnings: list[str]
):
    """Return the block's parsed object, checking label/title identity."""
    title = clean_text(block.get("title"))
    raw_label = clean_text(block.get("label"))
    title_parsed = parse_label(title)
    label_parsed = parse_label(raw_label) if raw_label else None
    if (
        label_parsed is not None
        and title_parsed is not None
        and not label_parsed.matches(title_parsed)
    ):
        errors.append(
            f"{prefix}.label {raw_label!r} does not match title object "
            f"{title_parsed.object_id}"
        )
    block_object = label_parsed or title_parsed
    if block_object is None:
        warnings.append(
            f"{prefix} has no parseable figure/table label; source coverage is unverified"
        )
    return block_object, title_parsed


def check_panel_coverage(
    panels: list[Any],
    block_object,
    title_parsed,
    prefix: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Check that panel titles belong to this object and cover letters once."""
    if block_object is None or title_parsed is None:
        return
    seen: dict[str, int] = {}
    ordered: list[str] = []
    for panel_index, panel in enumerate(panels, start=1):
        if not isinstance(panel, dict):
            continue
        panel_prefix = f"{prefix}.panel_explanations[{panel_index}]"
        parsed = parse_label(clean_text(panel.get("title")))
        if parsed is None:
            continue
        if not parsed.matches(block_object):
            errors.append(
                f"{panel_prefix}.title object {parsed.object_id} does not belong to "
                f"block object {block_object.object_id}"
            )
            continue
        for letter in parsed.panels:
            if letter in seen:
                errors.append(
                    f"{panel_prefix}.title repeats panel {letter} already covered by "
                    f"panel_explanations[{seen[letter]}]"
                )
                continue
            seen[letter] = panel_index
            ordered.append(letter)
    if not ordered:
        return
    highest = max(ord(letter) for letter in ordered)
    missing = [
        chr(code) for code in range(ord("A"), highest + 1) if chr(code) not in seen
    ]
    if missing:
        warnings.append(
            f"{prefix} panel letters are not contiguous (missing "
            f"{', '.join(missing)}); verify against the source caption"
        )


def check_content(data: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in ("document_title", "citation"):
        if not clean_text(data.get(key)):
            errors.append(f"{key} is required")

    positioning = data.get("field_positioning")
    if not isinstance(positioning, dict):
        errors.append("field_positioning must be an object")
    else:
        paragraphs = positioning.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs:
            errors.append("field_positioning.paragraphs must not be empty")
        elif any(not clean_text(item) for item in paragraphs):
            errors.append("field_positioning.paragraphs must not contain empty entries")

    check_materials(data, base_dir, errors, warnings)

    logic_chain = data.get("logic_chain")
    if not isinstance(logic_chain, list) or not logic_chain:
        errors.append("logic_chain must be a non-empty array")
    else:
        for index, step in enumerate(logic_chain, start=1):
            if not isinstance(step, dict):
                errors.append(f"logic_chain[{index}] must be an object")
                continue
            for key in ("title", "text"):
                if not clean_text(step.get(key)):
                    errors.append(f"logic_chain[{index}].{key} is required")
            text = clean_text(step.get("text"))
            if text and not LOGIC_START_PATTERN.match(text):
                errors.append(
                    f"logic_chain[{index}].text must start with 对应Fig.x："
                    " or the equivalent Table label"
                )

    blocks = data.get("evidence_blocks") or data.get("figures")
    if not isinstance(blocks, list) or not blocks:
        errors.append("evidence_blocks must be a non-empty array")
    else:
        for index, block in enumerate(blocks, start=1):
            prefix = f"evidence_blocks[{index}]"
            if not isinstance(block, dict):
                errors.append(f"{prefix} must be an object")
                continue
            title = clean_text(block.get("title"))
            if not title:
                errors.append(f"{prefix}.title is required")
            elif not HEADING_PATTERN.match(title):
                errors.append(
                    f"{prefix}.title must start with 'Figure X：' or the equivalent Table label"
                )
            for key in ("image", "paper_claim", "logic_role"):
                if not clean_text(block.get(key)):
                    errors.append(f"{prefix}.{key} is required")
            image = clean_text(block.get("image"))
            if image and resolve_image(image, base_dir) is None:
                errors.append(f"{prefix}.image cannot be resolved: {image}")

            panels = block.get("panel_explanations")
            if not isinstance(panels, list) or not panels:
                errors.append(f"{prefix}.panel_explanations must not be empty")
            else:
                block_number = None
                number_match = BLOCK_NUMBER_PATTERN.search(title)
                if number_match:
                    block_number = number_match.group(1)
                kind = clean_text(block.get("kind")) or "figure"
                label = clean_text(block.get("label"))
                is_table = kind == "table" or label.lower().startswith("table")
                block_object, title_parsed = check_block_label(
                    block, prefix, errors, warnings
                )
                if not is_table:
                    check_panel_coverage(
                        panels,
                        block_object,
                        title_parsed,
                        prefix,
                        errors,
                        warnings,
                    )
                for panel_index, panel in enumerate(panels, start=1):
                    panel_prefix = f"{prefix}.panel_explanations[{panel_index}]"
                    if isinstance(panel, str):
                        warnings.append(f"{panel_prefix} uses the legacy string form")
                        if not clean_text(panel):
                            errors.append(f"{panel_prefix} must not be empty")
                        continue
                    if not isinstance(panel, dict):
                        errors.append(f"{panel_prefix} must be an object")
                        continue
                    for key in ("title", "text"):
                        if not clean_text(panel.get(key)):
                            errors.append(f"{panel_prefix}.{key} is required")
                    if (
                        not is_table
                        and block_number is not None
                        and not PANEL_LABEL_PATTERN.search(
                            clean_text(panel.get("title"))
                        )
                    ):
                        errors.append(
                            f"{panel_prefix}.title must carry the {block_number} panel label"
                        )

            support_images = block.get("support_images") or []
            for support_index, item in enumerate(support_images, start=1):
                if not isinstance(item, dict) or not clean_text(item.get("path")):
                    errors.append(f"{prefix}.support_images[{support_index}] must contain path")
                elif resolve_image(clean_text(item["path"]), base_dir) is None:
                    errors.append(
                        f"{prefix}.support_images[{support_index}] path cannot be resolved"
                    )

    future = data.get("future_outlook")
    if future is not None and not isinstance(future, list):
        errors.append("future_outlook must be an array when present")
    if "future_outlook" not in data and (data.get("limitations") or data.get("trends")):
        warnings.append(
            "legacy limitations/trends will be rendered as 未来展望 but are not "
            "verified against the authors' Discussion/Conclusion; migrate them "
            "to future_outlook with source locations"
        )

    strings = list(collect_strings(data))
    for index, text in enumerate(strings, start=1):
        for prompt in FORBIDDEN_PROMPTS:
            if prompt in text:
                errors.append(f"Forbidden prompt {prompt!r} found in text value #{index}")
        if BOUNDARY_SPACE.search(text):
            errors.append(f"中英文边界空格 found in text value #{index}")
        if MARKDOWN_MARKER.search(text):
            warnings.append(f"Markdown marker found in text value #{index}")

    return {
        "content": str(Path(base_dir)),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def main_with_args(argv: list[str]) -> int:
    return run_main(parse_args(argv))


def run_main(args: argparse.Namespace) -> int:
    content_path = args.content.resolve()
    with content_path.open("r", encoding="utf-8-sig") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        print(
            json.dumps(
                {"errors": ["Content JSON must contain an object"]},
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1
    report = check_content(data, content_path.parent)
    report["ok"] = not report["errors"]
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 1


def main() -> None:
    sys.exit(run_main(parse_args()))


if __name__ == "__main__":
    main()
