#!/usr/bin/env python3
"""Render a reader DOCX to a PDF plus per-page PNGs, cached by DOCX hash.

Conversion uses LibreOffice (``XG_READING_SOFFICE``, PATH, or a platform
install location) or Microsoft Word COM on Windows. A conversion only counts
as successful after the produced PDF exists, is non-empty, opens in PDFium,
and contains at least one page. A ``render-cache.json`` records the DOCX hash,
conversion engine signature, PDF hash, and per-page hashes; a later call only
reuses the cache when every recorded output is still intact. Re-rendering
reports changed, unchanged, added, and removed pages against the previous
successful render.
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
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2 as pdfium
from file_utils import (
    atomic_replace,
    atomic_write_text,
    release_lock,
    wait_for_lock,
)

CACHE_NAME = "render-cache.json"
RENDER_CACHE_SCHEMA_VERSION = 3
WORKSPACE_LOCK_NAME = ".xg-render.lock"
SOFFICE_ENV = "XG_READING_SOFFICE"
WORD_PDF_EXPORT = 17  # wdExportFormatPDF
WORD_EXPORT_RANGE = 0  # wdExportAllDocument
WORD_EXPORT_ITEM = 0  # wdExportDocumentContent
WORD_CREATE_BOOKMARKS = 0  # wdExportCreateNoBookmarks
NO_RENDERER_MESSAGE = (
    "No DOCX renderer found. Install LibreOffice and expose soffice on PATH, "
    f"or set {SOFFICE_ENV} to its executable. Microsoft Word is used on Windows "
    "only when Word (COM) and PowerShell are both available."
)


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
    """Locate LibreOffice: explicit environment variable, PATH, install locations."""
    configured = os.environ.get(SOFFICE_ENV, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(
                f"{SOFFICE_ENV} does not point to a file: {candidate}"
            )
        return candidate.resolve()
    on_path = shutil.which("soffice") or shutil.which("libreoffice")
    if on_path:
        return Path(on_path)
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
        / "LibreOffice/program/soffice.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
        / "LibreOffice/program/soffice.exe",
        Path.home() / "scoop/apps/libreoffice/current/program/soffice.exe",
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        Path("/usr/lib/libreoffice/program/soffice"),
        Path("/opt/libreoffice/program/soffice"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_word_powershell() -> str | None:
    """Return the PowerShell path when Word COM is usable, else None."""
    if sys.platform != "win32":
        return None
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
            pass
    except (ImportError, OSError):
        return None
    return powershell


def available_engine() -> str:
    """Return the DOCX-to-PDF engine that would be used, or raise."""
    if find_soffice() is not None:
        return "soffice"
    if find_word_powershell() is not None:
        return "word"
    raise RuntimeError(NO_RENDERER_MESSAGE)


def engine_signature(engine: str) -> str:
    """Identity of the conversion engine that can affect rendered pages."""
    if engine == "soffice":
        soffice = find_soffice()
        if soffice is None:
            return "soffice:unknown"
        try:
            completed = subprocess.run(
                [str(soffice), "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            text = (completed.stdout or completed.stderr or "").strip().splitlines()
            if text:
                return f"soffice:{text[0].strip()}"
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            stat = soffice.stat()
            return f"soffice:path:{soffice}:{stat.st_size}:{int(stat.st_mtime)}"
        except OSError:
            return f"soffice:path:{soffice}"
    if engine == "word":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, r"Word.Application\CurVer"
            ) as key:
                value, _ = winreg.QueryValueEx(key, "")
                return f"word:{value}"
        except (ImportError, OSError):
            return "word:unknown"
    return f"{engine}:unknown"


def validate_pdf(path: Path) -> int:
    """Require a non-empty, readable PDF with at least one page."""
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Renderer reported success but produced no usable PDF: {path}")
    try:
        with pdfium.PdfDocument(str(path.resolve())) as pdf:
            pages = len(pdf)
    except Exception as error:  # PDFium raises several exception types
        raise RuntimeError(f"Renderer produced an unreadable PDF: {path}: {error}") from error
    if pages <= 0:
        raise RuntimeError(f"Renderer produced a PDF without pages: {path}")
    return pages


def convert_with_soffice(soffice: Path, docx: Path, pdf: Path) -> None:
    """Convert in a fresh staging directory and publish only a validated PDF."""
    pdf.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="xg-soffice-", dir=str(pdf.parent)))
    try:
        subprocess.run(
            [
                str(soffice),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(staging),
                str(docx),
            ],
            check=True,
            capture_output=True,
            timeout=600,
        )
        candidates = [path for path in staging.glob("*.pdf") if path.is_file()]
        if not candidates:
            raise RuntimeError(
                "LibreOffice reported success but produced no new PDF in the "
                "staging directory; the old PDF was not reused"
            )
        produced = candidates[0]
        validate_pdf(produced)
        atomic_replace(produced, pdf)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


WORD_LIST_SCRIPT = (
    "$ErrorActionPreference = 'SilentlyContinue'\n"
    "Get-Process WINWORD -ErrorAction SilentlyContinue |\n"
    "  ForEach-Object {\n"
    "    $started = try { $_.StartTime.ToUniversalTime().ToString('o') } catch { '' }\n"
    "    \"$($_.Id)`t$started\"\n"
    "  }\n"
)


def list_word_processes(powershell: str) -> dict[int, str]:
    """Snapshot WINWORD process ids and start times before an export attempt."""
    try:
        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                WORD_LIST_SCRIPT,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.SubprocessError, OSError):
        return {}
    processes: dict[int, str] = {}
    for line in (completed.stdout or "").splitlines():
        parts = line.strip().split("\t")
        if not parts or not parts[0].isdigit():
            continue
        processes[int(parts[0])] = parts[1].strip() if len(parts) > 1 else ""
    return processes


def list_word_pids(powershell: str) -> set[int]:
    """PID-only view of :func:`list_word_processes` (kept for compatibility)."""
    return set(list_word_processes(powershell))


def cleanup_script(
    keep_pids, started_after: str | None = None
) -> str:
    """Build a cleanup script for hidden Word instances created by this attempt.

    Only processes that are hidden, absent from the pre-attempt snapshot, and
    (when a start time is recorded) started after the attempt began are stopped.
    Word processes that existed before the attempt are never targeted, and when
    ownership cannot be confirmed no process is stopped.
    """
    keep = sorted({int(pid) for pid in keep_pids} | {os.getpid()})
    keep_literal = ",".join(str(pid) for pid in keep) if keep else "0"
    condition = "$_.MainWindowHandle -eq 0 -and $keep -notcontains $_.Id"
    lines = [
        "$ErrorActionPreference = 'SilentlyContinue'",
        f"$keep = @({keep_literal})",
    ]
    if started_after:
        lines.append(f"$since = [datetime]::Parse('{started_after}')")
        condition += " -and $_.StartTime.ToUniversalTime() -ge $since"
    lines.extend(
        [
            "Get-Process WINWORD -ErrorAction SilentlyContinue |",
            f"  Where-Object {{ {condition} }} |",
            "  ForEach-Object { Stop-Process -Id $_.Id -Force }",
        ]
    )
    return "\n".join(lines) + "\n"


def cleanup_word_processes(
    powershell: str, keep_pids=(), started_after: str | None = None
) -> None:
    """Stop candidate Word instances only after a confirmed ownership check."""
    try:
        subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                cleanup_script(keep_pids, started_after),
            ],
            check=False,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def convert_with_word(docx: Path, pdf: Path) -> None:
    powershell = find_word_powershell()
    if powershell is None:
        raise RuntimeError(NO_RENDERER_MESSAGE)
    keep_pids = list_word_pids(powershell)
    started_after = datetime.now(UTC).isoformat()
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
                    powershell,
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
            validate_pdf(pdf)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            OSError,
            RuntimeError,
        ) as error:
            cleanup_word_processes(powershell, keep_pids, started_after)
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
    if find_word_powershell() is None:
        raise RuntimeError(NO_RENDERER_MESSAGE)
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


def workspace_lock_path(work_dir: Path) -> Path:
    """Per-work-directory lock for cache read, render, and cache publish."""
    return work_dir / WORKSPACE_LOCK_NAME


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
    atomic_write_text(
        work_dir / CACHE_NAME,
        json.dumps(entry, ensure_ascii=False, indent=2),
    )


def cache_matches(cache: dict, digest: str, scale: float, engine: str) -> bool:
    """A cached render is reusable only when hash, scale, and engine match."""
    return (
        cache.get("docx_sha256") == digest
        and cache.get("scale") == scale
        and cache.get("engine") == engine
    )


def cache_valid(
    cache: dict,
    work_dir: Path,
    digest: str,
    scale: float,
    engine: str,
    signature: str,
) -> bool:
    """Check cache schema, engine signature, and every recorded output file."""
    if not isinstance(cache, dict):
        return False
    if cache.get("schema_version") != RENDER_CACHE_SCHEMA_VERSION:
        return False
    if not cache_matches(cache, digest, scale, engine):
        return False
    if cache.get("engine_signature") != signature:
        return False
    pdf_name = cache.get("pdf")
    pages = cache.get("pages")
    if not isinstance(pdf_name, str) or not isinstance(pages, list) or not pages:
        return False
    pdf_path = work_dir / pdf_name
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        return False
    pdf_hash = cache.get("pdf_sha256")
    if not isinstance(pdf_hash, str) or sha256(pdf_path) != pdf_hash:
        return False
    hashes = cache.get("page_hashes")
    if not isinstance(hashes, dict) or len(hashes) != len(pages):
        return False
    for name in pages:
        if not isinstance(name, str):
            return False
        page_path = work_dir / name
        if not page_path.is_file():
            return False
        if hashes.get(name) != sha256(page_path):
            return False
    return True


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
    changed = [name for name in order if current.get(name) != previous.get(name)]
    unchanged = [name for name in order if name not in changed]
    return changed, unchanged


def diff_generations(
    previous_pages: list[str],
    previous_hashes: dict[str, str],
    pages: list[str],
    hashes: dict[str, str],
) -> dict[str, list[str]]:
    """Compare a new render with the previous successful render."""
    changed = [name for name in pages if previous_hashes.get(name) != hashes.get(name)]
    unchanged = [name for name in pages if name not in changed]
    added = [name for name in pages if name not in previous_pages]
    removed = [name for name in previous_pages if name not in pages]
    return {
        "changed": changed,
        "unchanged": unchanged,
        "added": added,
        "removed": removed,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if not args.docx.exists():
            raise FileNotFoundError(f"DOCX not found: {args.docx}")
        work_dir = args.work_dir.resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = work_dir / args.pdf

        digest = sha256(args.docx.resolve())
        engine = available_engine()
        signature = engine_signature(engine)
        workspace_lock = workspace_lock_path(work_dir)
        if not wait_for_lock(workspace_lock):
            raise RuntimeError(
                "Another XG-Reading render holds this workspace lock; "
                f"lock held at {workspace_lock}"
            )
        try:
            cache = load_cache(work_dir)
            if not args.force and cache_valid(
                cache, work_dir, digest, args.scale, engine, signature
            ):
                pages = cache["pages"]
                current = page_hashes(work_dir, pages)
                changed, _unused = diff_pages(
                    pages, current, cache.get("page_hashes")
                )
                print("cached")
                print(work_dir / cache["pdf"])
                for name in pages:
                    path = work_dir / name
                    if name in changed:
                        print(f"changed {path}")
                    else:
                        print(f"unchanged {path}")
                return 0

            previous_pages = (
                list(cache.get("pages") or []) if isinstance(cache, dict) else []
            )
            previous_hashes = (
                dict(cache.get("page_hashes") or {}) if isinstance(cache, dict) else {}
            )

            started = time.perf_counter()
            converter_lock = render_lock_path()
            if not wait_for_lock(converter_lock):
                raise RuntimeError(
                    "Another XG-Reading render is still converting a document; "
                    f"lock held at {converter_lock}"
                )
            try:
                engine = convert_docx_to_pdf(args.docx.resolve(), pdf_path)
                converted = time.perf_counter()
                pages = render_pages(pdf_path, work_dir, args.scale)
            finally:
                release_lock(converter_lock)
            rendered = time.perf_counter()

            current_hashes = page_hashes(work_dir, pages)
            diff = diff_generations(
                previous_pages, previous_hashes, pages, current_hashes
            )
            save_cache(
                work_dir,
                {
                    "schema_version": RENDER_CACHE_SCHEMA_VERSION,
                    "docx_sha256": digest,
                    "pdf": pdf_path.name,
                    "pdf_sha256": sha256(pdf_path),
                    "pages": pages,
                    "scale": args.scale,
                    "engine": engine,
                    "engine_signature": signature,
                    "page_hashes": current_hashes,
                },
            )
            # Remove tail pages left by a previous, longer render only after the
            # new cache is published. Failure before this point keeps the old
            # cache valid, so a later run re-renders instead of mixing versions.
            for name in diff["removed"]:
                stale_page = work_dir / name
                if stale_page.is_file():
                    stale_page.unlink()
            print(f"converted {pdf_path.name} with {engine} in {converted - started:.1f}s")
            print(f"rendered {len(pages)} pages in {rendered - converted:.1f}s")
            print(pdf_path)
            for name in pages:
                status = "changed" if name in diff["changed"] else "unchanged"
                print(f"{status} {work_dir / name}")
            for name in diff["added"]:
                print(f"added {work_dir / name}")
            for name in diff["removed"]:
                print(f"removed {work_dir / name}")
            return 0
        finally:
            release_lock(workspace_lock)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
