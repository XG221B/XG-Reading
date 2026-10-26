#!/usr/bin/env python3
"""Parse evidence labels for figures, tables, supplementary objects, and panels.

The parser keeps object identity (kind, supplementary status, object number)
separate from panel letters so callers never treat the first digits they see as
the object number, and never match ``Fig. 1`` against ``Fig. 10``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LABEL_RE = re.compile(
    r"^(?P<supplementary>supplementary\s+)?"
    r"(?P<kind>fig(?:ure)?|table)\s*\.?\s*"
    r"(?P<number>[sS]?\d+[A-Za-z]?)"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)

PANEL_PREFIX_RE = re.compile(
    r"^(?P<panels>[A-Za-z](?:\s*[-–—]\s*[A-Za-z])?"
    r"(?:\s*[,，、/;；]\s*[A-Za-z](?:\s*[-–—]\s*[A-Za-z])?)*)"
)
PANEL_RANGE_RE = re.compile(r"([A-Za-z])\s*[-–—]\s*([A-Za-z])")
PANEL_LETTER_RE = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class EvidenceLabel:
    kind: str  # "figure" or "table"
    prefix: str  # display prefix, for example "Fig." or "Table"
    number: str  # object number without panel letters, for example "1" or "S1"
    supplementary: bool
    panels: tuple[str, ...]
    raw: str

    @property
    def object_id(self) -> str:
        """Stable identity for comparisons: ``figure:1``, ``figure:S1``, ``table:1``."""
        return f"{self.kind}:{self.number}"

    @property
    def canonical(self) -> str:
        return f"{self.prefix} {self.number}".strip()

    def matches(self, other: EvidenceLabel | None) -> bool:
        return other is not None and self.object_id == other.object_id


def _panels_from_rest(rest: str) -> tuple[str, ...]:
    match = PANEL_PREFIX_RE.match(rest.strip())
    if not match:
        return ()
    letters: list[str] = []
    for range_match in PANEL_RANGE_RE.finditer(match.group("panels")):
        start, end = range_match.group(1).upper(), range_match.group(2).upper()
        if ord(start) <= ord(end) and ord(end) - ord(start) <= 10:
            letters.extend(chr(code) for code in range(ord(start), ord(end) + 1))
    if not letters:
        letters = [letter.upper() for letter in PANEL_LETTER_RE.findall(match.group("panels"))]
    # Preserve order while removing duplicates such as "A,A".
    seen: set[str] = set()
    ordered = []
    for letter in letters:
        if letter not in seen:
            seen.add(letter)
            ordered.append(letter)
    return tuple(ordered)


def parse_label(text: object) -> EvidenceLabel | None:
    """Return a parsed label or None when the text is not an evidence label."""
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    match = LABEL_RE.match(raw)
    if match is None:
        return None
    kind = "table" if match.group("kind").lower().startswith("table") else "figure"
    number_token = match.group("number")
    supplementary = bool(match.group("supplementary")) or number_token.lower().startswith("s")
    digits = re.match(r"[sS]?(\d+)", number_token)
    if digits is None:
        return None
    number = f"S{digits.group(1)}" if supplementary else digits.group(1)
    rest = number_token[digits.end() :] + match.group("rest")
    prefix = "Table" if kind == "table" else "Figure"
    return EvidenceLabel(
        kind=kind,
        prefix=prefix,
        number=number,
        supplementary=supplementary,
        panels=_panels_from_rest(rest),
        raw=raw,
    )


def expand_panels(text: object) -> tuple[str, ...]:
    """Return panel letters from a label or title, expanding ranges such as A-C."""
    parsed = parse_label(text)
    if parsed is not None:
        return parsed.panels
    return _panels_from_rest(str(text or ""))


def panel_letters(text: object) -> tuple[str, ...]:
    parsed = parse_label(text)
    return parsed.panels if parsed is not None else ()


def label_display(parsed: EvidenceLabel) -> str:
    """Return a stable display form without panel letters."""
    if parsed.kind == "table":
        return f"Table {parsed.number}"
    return f"Fig.{parsed.number}"


def caption_search_terms(label: object) -> list[str]:
    """Search terms for a figure or table caption, preserving object type.

    Terms are ordered from the most specific caption form to the most generic.
    A ``Fig. 1`` term never matches ``Fig. 10`` because callers must apply
    :func:`is_number_boundary` after each hit.
    """
    parsed = parse_label(label)
    if parsed is None:
        return [re.sub(r"\s+", " ", str(label or "")).strip()]
    number = parsed.number.lstrip("Ss")
    display_number = parsed.number
    if parsed.kind == "table":
        terms = [f"Table {display_number}", f"Table{display_number}"]
        if parsed.supplementary:
            terms = [
                f"Supplementary Table {number}",
                f"Supplementary Table S{number}",
                f"Table S{number}",
                *terms,
            ]
        return terms
    if parsed.supplementary:
        return [
            f"Supplementary Figure {number}",
            f"Supplementary Fig. {number}",
            f"Supplementary Fig.{number}",
            f"Figure S{number}",
            f"Fig. S{number}",
            f"Fig.S{number}",
        ]
    return [
        f"Figure {display_number}",
        f"Fig. {display_number}",
        f"Fig.{display_number}",
    ]


def is_number_boundary(text: str, start: int, length: int) -> bool:
    """Reject a match followed or preceded by an alphanumeric character.

    This keeps ``Fig. 1`` from matching ``Fig. 10`` or ``Fig. 1A`` and keeps a
    supplementary ``Fig. S1`` from matching ``Fig. S10``.
    """
    before = text[start - 1] if start > 0 else ""
    after_index = start + length
    after = text[after_index] if after_index < len(text) else ""
    if before and (before.isalnum() or before in "._-"):
        return False
    return not (after and (after.isalnum() or after == "A"))


def caption_prefix_matches(caption_text: str, label: object) -> bool:
    """Whether a recovered caption begins with the expected object number and type."""
    parsed = parse_label(label)
    if parsed is None:
        return True
    caption = parse_label(caption_text)
    if caption is None:
        return False
    if caption.kind != parsed.kind:
        return False
    return caption.number.upper() == parsed.number.upper()
