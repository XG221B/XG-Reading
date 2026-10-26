#!/usr/bin/env python3
"""Batch-extract several complete paper figures and captions from one PDF.

Distinct pages are processed in parallel worker processes; every figure on
the same page shares one PDF open, one text layer, and one page render.
Worker processes are used instead of threads because PDFium rendering is not
thread-safe in this environment. Each crop and its ``.crop.json`` report are
byte-identical to what ``extract_figure_region.py`` produces for the same
label, page, and options. A failed figure or page is reported as an error
record without discarding the successful crops from the other figures.
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
    CROP_REPORT_SCHEMA_VERSION,
    caption_for_page,
    crop_from_rendered,
)
from file_utils import atomic_write_text, sha256_file


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
        help='<label>:<page>[:<output.png>][:<top_from_page>], repeatable, '
             'for example "Fig. 2:5:Fig2.png" or "Fig. 2:5:Fig2.png:120"',
    )
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=3.0)
    parser.add_argument("--left", type=float, default=18.0)
    parser.add_argument("--right", type=float, default=18.0)
    parser.add_argument("--caption-padding", type=float, default=4.0)
    parser.add_argument(
        "--top-from-page",
        type=float,
        help="Manual crop top in PDF points applied to every figure that has no per-figure top",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore matching previous crops and re-extract every figure",
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
        if len(parts) < 2 or len(parts) > 4:
            raise ValueError(
                f"Invalid --fig entry {spec!r}; expected "
                "<label>:<page>[:<output.png>][:<top_from_page>]"
            )
        label = parts[0].strip()
        if not label:
            raise ValueError(f"Empty label in --fig entry {spec!r}")
        try:
            page = int(parts[1])
        except ValueError as error:
            raise ValueError(f"Invalid page in --fig entry {spec!r}") from error
        output = Path(parts[2].strip()) if len(parts) >= 3 and parts[2].strip() else None
        top = None
        if len(parts) == 4:
            if not parts[3].strip():
                raise ValueError(f"Empty top-from-page in --fig entry {spec!r}")
            try:
                top = float(parts[3])
            except ValueError as error:
                raise ValueError(f"Invalid top-from-page in --fig entry {spec!r}") from error
        figures.append(
            {"label": label, "page": page, "output": output, **({"top": top} if top is not None else {})}
        )
    return figures


def validate_specs(figures: list[dict]) -> None:
    seen_keys: set[tuple[int, str]] = set()
    seen_outputs: dict[str, tuple[int, str]] = {}
    for fig in figures:
        key = (fig["page"], fig["label"])
        if key in seen_keys:
            raise ValueError(f"Duplicate --fig entry for {fig['label']} on page {fig['page']}")
        seen_keys.add(key)
        output = str(fig["output"]) if fig["output"] else default_output_name(fig["label"])
        if output in seen_outputs:
            other_page, other_label = seen_outputs[output]
            raise ValueError(
                f"Output collision: {fig['label']} on page {fig['page']} and "
                f"{other_label} on page {other_page} both write {output}"
            )
        seen_outputs[output] = key


def build_source(fig: dict, options: dict, page_index: int) -> dict:
    """Fingerprint of everything that influences one crop result."""
    return {
        "pdf_sha256": options["pdf_sha256"],
        "page": page_index,
        "label": fig["label"],
        "scale": options["scale"],
        "left": options["left"],
        "right": options["right"],
        "caption_padding": options["caption_padding"],
        "top_from_page": fig.get("top") if fig.get("top") is not None else options["top_from_page"],
        "allow_low_confidence": options["allow_low_confidence"],
    }


def cache_hit(report_path: Path, source: dict, output: Path) -> bool:
    """True when a previous crop report matches the source and its PNG intact."""
    if not report_path.exists() or not output.exists():
        return False
    try:
        existing = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(existing, dict):
        return False
    if existing.get("schema_version") != CROP_REPORT_SCHEMA_VERSION:
        return False
    if existing.get("source") != source:
        return False
    recorded = existing.get("output_sha256")
    if not isinstance(recorded, str) or not recorded:
        return False
    try:
        return sha256_file(output).lower() == recorded.lower()
    except OSError:
        return False


def extract_page(
    page,
    page_width: float,
    page_height: float,
    figures: list[dict],
    options: dict,
    *,
    page_index: int,
    pdf_path: str,
) -> list[dict]:
    """Extract every figure on one page with a single page render.

    Caption detection runs first and the page is only rendered when at least
    one figure has a usable caption. Each figure failure is captured as an
    error record so that a low-confidence crop on one figure never discards
    the successful crops on the same page.
    """
    detected: dict[str, dict | Exception] = {}
    for fig in figures:
        try:
            detected[fig["label"]] = caption_for_page(page, page_height, fig["label"])
        except Exception as error:
            detected[fig["label"]] = error

    if all(isinstance(value, Exception) for value in detected.values()):
        return [
            {
                "pdf": pdf_path,
                "page": page_index,
                "label": fig["label"],
                "output": str(
                    Path(options["outdir"])
                    / (fig["output"] if fig["output"] else default_output_name(fig["label"]))
                ),
                "error": f"{type(detected[fig['label']]).__name__}: {detected[fig['label']]}",
            }
            for fig in figures
        ]

    rendered = page.render(scale=options["scale"]).to_pil().convert("RGB")
    reports = []
    for fig in figures:
        output = Path(options["outdir"]) / (
            fig["output"] if fig["output"] else default_output_name(fig["label"])
        )
        caption = detected[fig["label"]]
        if isinstance(caption, Exception):
            reports.append(
                {
                    "pdf": pdf_path,
                    "page": page_index,
                    "label": fig["label"],
                    "output": str(output.resolve()),
                    "error": f"{type(caption).__name__}: {caption}",
                }
            )
            continue
        try:
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
                top_from_page=(
                    fig.get("top") if fig.get("top") is not None else options["top_from_page"]
                ),
                allow_low_confidence=options["allow_low_confidence"],
            )
            reports.append(
                {
                    "pdf": pdf_path,
                    "page": page_index,
                    **report,
                    "source": build_source(fig, options, page_index),
                }
            )
        except Exception as error:
            reports.append(
                {
                    "pdf": pdf_path,
                    "page": page_index,
                    "label": fig["label"],
                    "output": str(output.resolve()),
                    "error": f"{type(error).__name__}: {error}",
                }
            )
    return reports


def process_page(payload: dict) -> list[dict]:
    """Worker entry point: extract all figures on one page and save them."""
    options = payload["options"]
    with pdfium.PdfDocument(payload["pdf"]) as pdf:
        page_index = payload["page_index"]
        page = pdf[page_index - 1]
        page_width, page_height = page.get_size()
        return extract_page(
            page,
            page_width,
            page_height,
            payload["figures"],
            options,
            page_index=page_index,
            pdf_path=payload["pdf"],
        )


def process_page_safe(payload: dict) -> list[dict]:
    """Worker wrapper: a page-level failure becomes an error record."""
    try:
        return process_page(payload)
    except Exception as error:
        return [
            {
                "pdf": payload["pdf"],
                "page": payload["page_index"],
                "page_error": f"{type(error).__name__}: {error}",
                "labels": [fig["label"] for fig in payload["figures"]],
            }
        ]


def finalize_batch(specs: list[dict], results: dict[tuple[int, str], dict]):
    """Reconcile worker results with the requested order.

    Returns (reports_in_request_order, errors_in_request_order). Missing
    results (page-level failures) become error records.
    """
    reports = []
    errors = []
    for fig in specs:
        key = (fig["page"], fig["label"])
        record = results.get(key)
        if record is None or "error" in record:
            error_detail = None
            if record is not None:
                error_detail = record.get("error")
            if not error_detail:
                error_detail = f"Page {fig['page']} failed before extraction"
            errors.append(
                {
                    "page": fig["page"],
                    "label": fig["label"],
                    "error": error_detail,
                }
            )
            continue
        reports.append(record)
    return reports, errors


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
    validate_specs(figures)

    options = {
        "scale": args.scale,
        "left": args.left,
        "right": args.right,
        "caption_padding": args.caption_padding,
        "top_from_page": args.top_from_page,
        "allow_low_confidence": args.allow_low_confidence,
        "outdir": str(args.outdir.resolve()),
        "pdf_sha256": sha256_file(args.pdf.resolve()),
    }

    cached: dict[tuple[int, str], dict] = {}
    pending: list[dict] = []
    for fig in figures:
        output = args.outdir / (fig["output"] if fig["output"] else default_output_name(fig["label"]))
        report_path = output.with_suffix(output.suffix + ".crop.json")
        source = build_source(fig, options, fig["page"])
        if not args.no_cache and cache_hit(report_path, source, output):
            try:
                cached[(fig["page"], fig["label"])] = json.loads(
                    report_path.read_text(encoding="utf-8")
                )
                continue
            except (json.JSONDecodeError, OSError):
                pass
        pending.append(fig)

    by_page: dict[int, list[dict]] = {}
    for fig in pending:
        by_page.setdefault(fig["page"], []).append(fig)

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
        for page_reports in pool.imap_unordered(process_page_safe, payloads):
            for report in page_reports:
                if "page_error" in report:
                    for label in report["labels"]:
                        completed[(report["page"], label)] = {
                            "page": report["page"],
                            "label": label,
                            "error": report["page_error"],
                        }
                    continue
                completed[(report["page"], report["label"])] = report
                if "error" not in report:
                    write_report_file(report)

    for key, report in cached.items():
        completed[key] = report

    reports, errors = finalize_batch(figures, completed)
    for report in reports:
        print(json.dumps(report, ensure_ascii=True, indent=2))

    if errors:
        for error in errors:
            print(
                json.dumps(error, ensure_ascii=True, indent=2),
                file=sys.stderr,
            )
        sys.exit(1)


def write_report_file(report: dict) -> None:
    output = Path(report["output"])
    report_path = output.with_suffix(output.suffix + ".crop.json")
    atomic_write_text(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2),
    )


if __name__ == "__main__":
    sys.exit(main())
