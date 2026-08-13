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
from file_utils import release_lock, wait_for_lock

CACHE_NAME = "render-cache.json"
WORD_PDF_EXPORT = 17  # wdExportFormatPDF
WORD_EXPORT_RANGE = 0  # wdExportAllDocument
WORD_EXPORT_ITEM = 0  # wdExportDocumentContent
WORD_CREATE_BOOKMARKS = 0  # wdExportCreateNoBookmarks


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--pdf", default="reader.pdf", help="PDF name inside work-dir")
    parser.add_argument("--scale", type=float, default=2.0, help="PNG render scale")
    parser.add_argument("--force", action="store_true", help="Ignore the cache")
    return parser.parse_args(argv)


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


def cleanup_invisible_word() -> None:
    """Stop only invisible WINWORD instances left behind by a failed export.

    Visible Word windows belong to the user and are never touched.
    """
    script = (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        "Get-Process WINWORD -ErrorAction SilentlyContinue |\n"
        "  Where-Object { $_.MainWindowHandle -eq 0 } |\n"
        "  ForEach-Object { Stop-Process -Id $_.Id -Force }\n"
    )
    with tempfile.TemporaryDirectory(prefix="xg-render-") as tmp_raw:
        script_path = Path(tmp_raw) / "cleanup.ps1"
        script_path.write_bytes(script.encode("utf-8-sig"))
        try:
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
                check=False,
                timeout=120,
            )
        except (subprocess.SubprocessError, OSError):
            pass


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
        try:
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
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
            cleanup_invisible_word()
            raise RuntimeError(
                "Word conversion failed. Install LibreOffice for a more reliable "
                f"renderer, or inspect the DOCX in Word. Original error: {error}"
            ) from error


def convert_docx_to_pdf(docx: Path, pdf: Path) -> str:
    """Convert the DOCX to PDF and return the engine name used."""
    soffice = find_soffice()
    if soffice is not None:
        convert_with_soffice(soffice, docx, pdf)
        return "soffice"
    convert_with_word(docx, pdf)
    return "word"


def render_pages(pdf_path: Path, work_dir: Path, scale: float) -> list[str]:
    # Sequential rendering: PDFium is not thread-safe in this environment,
    # and per-page PNG rasterization is already fast at inspection scale.
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


def render_lock_path() -> Path:
    """One machine-wide lock for DOCX-to-PDF conversion, which uses shared
    single-instance resources (Word COM, the LibreOffice user profile)."""
    return Path(tempfile.gettempdir()) / "xg-render.lock"


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


def cache_matches(cache: dict, digest: str, scale: float, engine: str) -> bool:
    """A cached render is reusable only when hash, scale, and engine match."""
    return (
        cache.get("docx_sha256") == digest
        and cache.get("scale") == scale
        and cache.get("engine") == engine
    )


def page_hashes(work_dir: Path, pages: list[str]) -> dict[str, str]:
    hashes = {}
    for name in pages:
        path = work_dir / name
        if path.exists():
            hashes[name] = sha256(path)
    return hashes


def diff_pages(
    order: list[str],
    current: dict[str, str],
    previous: dict[str, str] | None,
):
    """Split page names into changed and unchanged against a previous render."""
    if previous is None:
        return list(order), []
    changed = [
        name for name in order if current.get(name) != previous.get(name)
    ]
    unchanged = [name for name in order if name not in changed]
    return changed, unchanged


def main() -> None:
    args = parse_args()
    if not args.docx.exists():
        raise FileNotFoundError(args.docx)
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / args.pdf

    digest = sha256(args.docx.resolve())
    engine = "soffice" if find_soffice() else "word"
    cache = load_cache(work_dir)
    if not args.force and cache_matches(cache, digest, args.scale, engine):
        cached_pdf = work_dir / cache["pdf"]
        cached_pages = [work_dir / name for name in cache.get("pages", [])]
        if cached_pdf.exists() and all(path.exists() for path in cached_pages):
            current = page_hashes(work_dir, cache.get("pages", []))
            changed, _unused = diff_pages(
                cache.get("pages", []), current, cache.get("page_hashes")
            )
            print("cached")
            print(cached_pdf)
            for name in cache.get("pages", []):
                path = work_dir / name
                if name in changed:
                    print(f"changed {path}")
                else:
                    print(f"unchanged {path}")
            return

    started = time.perf_counter()
    lock_path = render_lock_path()
    if not wait_for_lock(lock_path):
        raise RuntimeError(
            "Another XG-Reading render is still converting a document; "
            f"lock held at {lock_path}"
        )
    try:
        engine = convert_docx_to_pdf(args.docx.resolve(), pdf_path)
        converted = time.perf_counter()
        pages = render_pages(pdf_path, work_dir, args.scale)
    finally:
        release_lock(lock_path)
    rendered = time.perf_counter()

    save_cache(
        work_dir,
        {
            "docx_sha256": digest,
            "pdf": pdf_path.name,
            "pages": pages,
            "scale": args.scale,
            "engine": engine,
            "page_hashes": page_hashes(work_dir, pages),
        },
    )
    print(f"converted {pdf_path.name} in {converted - started:.1f}s")
    print(f"rendered {len(pages)} pages in {rendered - converted:.1f}s")
    print(pdf_path)
    for name in pages:
        print(f"changed {work_dir / name}")


if __name__ == "__main__":
    sys.exit(main())
