#!/usr/bin/env python3
"""Batch-extract several complete paper figures and captions from one PDF.

Distinct pages are processed in parallel worker processes; every figure on
the same page shares one PDF open, one text layer, and one page render.
Worker processes are used instead of threads because PDFium rendering is not
thread-safe in this environment. Each crop and its ``.crop.json`` report are
byte-identical to what ``extract_figure_region.py`` produces for the same
label, page, and options.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium

from extract_figure_region import (
    caption_for_page,
    crop_from_rendered,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crop all listed figures from a PDF, processing each page in a "
            "worker process. Each --fig entry has the form <label>:<page>"
            "[:<output.png>], for example \"Fig. 2:5:Fig2.png\"."
        )
    )
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument(
        "--fig",
        required=True,
        action="append",
        help='<label>:<page>[:<output.png>], repeatable, for example "Fig. 2:5:Fig2.png"',
    )
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=3.0)
    parser.add_argument("--left", type=float, default=18.0)
    parser.add_argument("--right", type=float, default=18.0)
    parser.add_argument("--caption-padding", type=float, default=4.0)
    parser.add_argument(
        "--top-from-page",
        type=float,
        help="Manual crop top in PDF points applied to every figure on the page",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=min(4, os.cpu_count() or 4),
        help="Worker process count (default: 4 or the CPU count, whichever is smaller)",
    )
    parser.add_argument("--allow-low-confidence", action="store_true")
    return parser.parse_args()


def default_output_name(label: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "", label)
    return (name or "figure") + ".png"


def parse_fig_specs(specs: list[str]) -> list[dict]:
    figures: list[dict] = []
    for spec in specs:
        parts = spec.split(":")
        if len(parts) < 2 or len(parts) > 3:
            raise ValueError(
                f"Invalid --fig entry {spec!r}; expected <label>:<page>[:<output.png>]"
            )
        label = parts[0].strip()
        if not label:
            raise ValueError(f"Empty label in --fig entry {spec!r}")
        try:
            page = int(parts[1])
        except ValueError as error:
            raise ValueError(f"Invalid page in --fig entry {spec!r}") from error
        output = Path(parts[2].strip()) if len(parts) == 3 else None
        figures.append({"label": label, "page": page, "output": output})
    return figures


def process_page(payload: dict) -> list[dict]:
    """Worker entry point: extract all figures on one page and save them."""
    options = payload["options"]
    with pdfium.PdfDocument(payload["pdf"]) as pdf:
        page_index = payload["page_index"]
        page = pdf[page_index - 1]
        page_width, page_height = page.get_size()
        reports = []
        for fig in payload["figures"]:
            caption = caption_for_page(page, page_height, fig["label"])
            rendered = page.render(scale=options["scale"]).to_pil().convert("RGB")
            output = Path(options["outdir"]) / (
                fig["output"] if fig["output"] else default_output_name(fig["label"])
            )
            report = crop_from_rendered(
                rendered,
                page_width,
                page_height,
                caption,
                fig["label"],
                output,
                scale=options["scale"],
                left=options["left"],
                right=options["right"],
                caption_padding=options["caption_padding"],
                top_from_page=options["top_from_page"],
                allow_low_confidence=options["allow_low_confidence"],
            )
            reports.append(
                {
                    "pdf": payload["pdf"],
                    "page": page_index,
                    **report,
                }
            )
        return reports


def main() -> None:
    args = parse_args()
    if not args.pdf.exists():
        raise FileNotFoundError(args.pdf)
    args.outdir.mkdir(parents=True, exist_ok=True)

    with pdfium.PdfDocument(args.pdf.resolve()) as pdf:
        page_count = len(pdf)
        if page_count == 0:
            raise ValueError("PDF contains no pages")

    figures = parse_fig_specs(args.fig)
    for fig in figures:
        if not 1 <= fig["page"] <= page_count:
            raise ValueError(f"page must be between 1 and {page_count}: {fig['page']}")

    by_page: dict[int, list[dict]] = {}
    order: list[tuple[int, str]] = []
    for fig in figures:
        by_page.setdefault(fig["page"], []).append(fig)
        order.append((fig["page"], fig["label"]))

    options = {
        "scale": args.scale,
        "left": args.left,
        "right": args.right,
        "caption_padding": args.caption_padding,
        "top_from_page": args.top_from_page,
        "allow_low_confidence": args.allow_low_confidence,
        "outdir": str(args.outdir.resolve()),
    }
    payloads = [
        {
            "pdf": str(args.pdf.resolve()),
            "page_index": page_index,
            "figures": page_figs,
            "options": options,
        }
        for page_index, page_figs in by_page.items()
    ]

    completed: dict[tuple[int, str], dict] = {}
    context = multiprocessing.get_context("spawn")
    with context.Pool(processes=max(1, min(args.jobs, len(payloads)))) as pool:
        for reports in pool.map(process_page, payloads):
            for report in reports:
                completed[(report["page"], report["label"])] = report

    for page_index, label in order:
        report = completed[(page_index, label)]
        output = Path(report["output"])
        report_path = output.with_suffix(output.suffix + ".crop.json")
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    sys.exit(main())
