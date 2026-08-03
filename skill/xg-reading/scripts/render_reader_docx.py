#!/usr/bin/env python3
"""Render a reader DOCX to a PDF plus per-page PNGs, cached by DOCX hash.

The DOCX is converted to PDF with Microsoft Word (COM, via PowerShell) or
LibreOffice when available, then each PDF page is rasterized with pypdfium2.
A ``render-cache.json`` records the DOCX SHA-256; when the DOCX has not
changed, a later call skips both conversions and reports the cached pages,
which keeps the inspect-and-fix loop in the skill workflow from re-rendering
unchanged documents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pypdfium2 as pdfium

CACHE_NAME = "render-cache.json"
WORD_PDF_EXPORT = 17  # wdExportFormatPDF
WORD_EXPORT_RANGE = 0  # wdExportAllDocument
WORD_EXPORT_ITEM = 0  # wdExportDocumentContent
WORD_CREATE_BOOKMARKS = 0  # wdExportCreateNoBookmarks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--pdf", default="reader.pdf", help="PDF name inside work-dir")
    parser.add_argument("--scale", type=float, default=2.0, help="PNG render scale")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--force", action="store_true", help="Ignore the cache")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_soffice() -> Path | None:
    on_path = shutil.which("soffice") or shutil.which("libreoffice")
    if on_path:
        return Path(on_path)
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
        / "LibreOffice/program/soffice.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
        / "LibreOffice/program/soffice.exe",
        Path.home() / "scoop/apps/libreoffice/current/program/soffice.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def convert_with_soffice(soffice: Path, docx: Path, pdf: Path) -> None:
    pdf.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(soffice),
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf.parent),
            str(docx),
        ],
        check=True,
        capture_output=True,
        timeout=600,
    )
    produced = pdf.parent / (docx.stem + ".pdf")
    if produced.exists() and produced != pdf:
        produced.replace(pdf)


def convert_with_word(docx: Path, pdf: Path) -> None:
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$word = New-Object -ComObject Word.Application\n"
        "$word.Visible = $false\n"
        "$word.DisplayAlerts = 0\n"
        "try {{\n"
        "  $doc = $word.Documents.Open('{docx}', $false, $true)\n"
        "  $doc.ExportAsFixedFormat('{pdf}', {fmt}, $false, 0, {rng}, 0, 0, {item}, $false, $true, {bm}, $true, $false, $false)\n"
        "  $doc.Close(0)\n"
        "}} finally {{\n"
        "  $word.Quit()\n"
        "}}\n"
    ).format(
        docx=str(docx.resolve()).replace("'", "''"),
        pdf=str(pdf.resolve()).replace("'", "''"),
        fmt=WORD_PDF_EXPORT,
        rng=WORD_EXPORT_RANGE,
        item=WORD_EXPORT_ITEM,
        bm=WORD_CREATE_BOOKMARKS,
    )
    pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xg-render-") as tmp_raw:
        script_path = Path(tmp_raw) / "render.ps1"
        # PowerShell 5.1 requires a BOM to read UTF-8 scripts correctly.
        script_path.write_bytes(script.encode("utf-8-sig"))
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            check=True,
            timeout=900,
        )


def convert_docx_to_pdf(docx: Path, pdf: Path) -> None:
    soffice = find_soffice()
    if soffice is not None:
        convert_with_soffice(soffice, docx, pdf)
        return
    convert_with_word(docx, pdf)


def render_pages(pdf_path: Path, work_dir: Path, scale: float, jobs: int) -> list[str]:
    # Sequential rendering: PDFium is not thread-safe in this environment,
    # and per-page PNG rasterization is already fast at inspection scale.
    del jobs
    pages = []
    with pdfium.PdfDocument(str(pdf_path.resolve())) as pdf:
        count = len(pdf)
        for index in range(count):
            page = pdf[index]
            rendered = page.render(scale=scale).to_pil().convert("RGB")
            name = f"page-{index + 1:02d}.png"
            rendered.save(work_dir / name, optimize=True)
            pages.append(name)
    return pages


def load_cache(work_dir: Path) -> dict:
    cache_path = work_dir / CACHE_NAME
    if not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(work_dir: Path, entry: dict) -> None:
    cache_path = work_dir / CACHE_NAME
    cache_path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    if not args.docx.exists():
        raise FileNotFoundError(args.docx)
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / args.pdf

    digest = sha256(args.docx.resolve())
    cache = load_cache(work_dir)
    if not args.force and cache.get("docx_sha256") == digest:
        cached_pdf = work_dir / cache["pdf"]
        cached_pages = [work_dir / name for name in cache.get("pages", [])]
        if cached_pdf.exists() and all(path.exists() for path in cached_pages):
            print("cached")
            print(cached_pdf)
            for page in cached_pages:
                print(page)
            return

    started = time.perf_counter()
    convert_docx_to_pdf(args.docx.resolve(), pdf_path)
    converted = time.perf_counter()
    pages = render_pages(pdf_path, work_dir, args.scale, args.jobs)
    rendered = time.perf_counter()

    save_cache(
        work_dir,
        {
            "docx_sha256": digest,
            "pdf": pdf_path.name,
            "pages": pages,
            "scale": args.scale,
        },
    )
    print(f"converted {pdf_path.name} in {converted - started:.1f}s")
    print(f"rendered {len(pages)} pages in {rendered - converted:.1f}s")
    print(pdf_path)
    for name in pages:
        print(work_dir / name)


if __name__ == "__main__":
    sys.exit(main())
