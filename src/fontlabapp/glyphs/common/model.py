# this_file: src/fontlabapp/glyphs/common/model.py
# SPDX-License-Identifier: Apache-2.0
"""Detached exact-name intersection and original CommonGlyphs report sections.

Production metadata belongs to the caller. App does not import Glyphs adapters
or databases. One font retains glyph order; multiple fonts use sorted names in
place of the original unordered set. Unicode assignments are alternatives:
Glyphs.string/charString uses the first scalar, including encoded ligatures.
"""

from collections.abc import Callable
from dataclasses import dataclass
import json
from time import monotonic
from typing import Literal

MARK_HOLD = (
    "Charcoal marking in every open font is unavailable: FontLab's public "
    "mark property can recolour layers and has no supported glyph-only history "
    "path (FontLab issue 8564). No font is changed. The full optional action "
    "remains unimplemented. Planned semantic dark grey is mark 1001; appearance "
    "depends on theme/preferences, not exact Glyphs charcoal RGB. Raw layer "
    "labels/inheritance must be preserved; inherited appearance may follow "
    "an intentional glyph-label change."
)


@dataclass(frozen=True)
class Glyph:
    """Stored name and every assigned Unicode scalar in source order."""

    name: str
    unicodes: tuple[int, ...]


@dataclass(frozen=True)
class Font:
    """Registered package/FontGate identities, family and font-order glyphs."""

    identity: int
    fg_id: int
    family: str
    glyphs: tuple[Glyph, ...]


@dataclass(frozen=True)
class Production:
    """A caller-verified production name or an explicit unresolved mapping."""

    name: str | None
    status: Literal["database", "derived", "unknown"]

    def __post_init__(self) -> None:
        """Reject unsupported statuses or a fallback disguised as known data."""
        if self.status not in ("database", "derived", "unknown"):
            raise ValueError("Invalid production metadata status.")
        if (self.status == "unknown") != (self.name is None):
            raise ValueError("Unknown production mappings must be explicit.")
        if self.name is not None and (not isinstance(self.name, str) or not self.name):
            raise ValueError("A known production name must be nonempty text.")


def checkpoint(
    deadline: float, clock: Callable = monotonic, cancelled: Callable = lambda: False
) -> None:
    """Refuse expired/cancelled work before publishing any partial report."""
    if cancelled():
        raise InterruptedError("Common Glyphs was cancelled.")
    if clock() >= deadline:
        raise TimeoutError("Common Glyphs exceeded its deadline; run again.")


def validate(fonts: tuple[Font, ...], check: Callable) -> None:
    """Validate detached identities/names/scalars with per-item checkpoints."""
    identities, fg_ids = set(), set()
    for font in fonts:
        check()
        if (
            type(font.identity) is not int
            or type(font.fg_id) is not int
            or font.identity <= 0
            or font.fg_id <= 0
            or font.identity in identities
            or font.fg_id in fg_ids
        ):
            raise ValueError("Open fonts have invalid or duplicate registrations.")
        identities.add(font.identity)
        fg_ids.add(font.fg_id)
        names = set()
        for glyph in font.glyphs:
            check()
            if not isinstance(glyph.name, str) or not glyph.name or glyph.name in names:
                raise ValueError("A font has empty or duplicate glyph names.")
            names.add(glyph.name)
            for code in glyph.unicodes:
                check()
                if (
                    type(code) is not int
                    or not 0 <= code <= 0x10FFFF
                    or 0xD800 <= code <= 0xDFFF
                ):
                    raise ValueError(f"Invalid Unicode scalar in {glyph.name!r}.")
    check()


def analyze(
    fonts: tuple[Font, ...], metadata: Callable, *, check: Callable = lambda: None
) -> dict:
    """Build the full original report without selection/current-font prerequisites.

    ``metadata(name, checkpoint=check)`` returns Production. Unknown mappings
    remain explicit placeholders. Nonexport/unencoded glyphs are never filtered.
    Every nonempty source string and every name retains its final source space.
    """
    check()
    if not fonts:
        raise ValueError(
            "Insufficient number of fonts open to compare; open at least one font."
        )
    validate(fonts, check)
    maps = []
    for font in fonts:
        row = {}
        for glyph in font.glyphs:
            check()
            row[glyph.name] = glyph.unicodes
        maps.append(row)
    shared = set(maps[0])
    for row in maps[1:]:
        check()
        shared.intersection_update(row)
        check()
    ordered = list(maps[0]) if len(fonts) == 1 else sorted(shared)
    check()
    characters, nice, production, mappings, slash = [], [], [], [], []
    for name in ordered:
        check()
        codes = maps[0][name]
        if codes:
            characters.append(chr(codes[0]) + " ")
        nice.append(name + " ")
        slash.append("/" + name)
        info = metadata(name, checkpoint=check)
        check()
        if not isinstance(info, Production):
            raise ValueError(
                "Production metadata must return explicit Production facts."
            )
        production.append(
            (info.name if info.name is not None else f"[unknown:{name}]") + " "
        )
        mappings.append(
            {"stored_name": name, "production_name": info.name, "status": info.status}
        )
    alternatives, families = [], []
    for font, row in zip(fonts, maps, strict=True):
        check()
        families.append(font.family)
        values = {}
        for name in ordered:
            codes = []
            for code in row[name]:
                check()
                codes.append(f"U+{code:04X}")
            check()
            values[name] = codes
        alternatives.append(
            {"font": font.family, "package_id": font.identity, "glyphs": values}
        )
    text, nice_text, prod_text = "".join(characters), "".join(nice), "".join(production)
    source = (
        f"Analysed fonts: {', '.join(families)}\nNumber of common glyphs: {len(ordered)}\n\n"
        f"{text}\n\n\nNice names: \n{nice_text}\n\n\nProduction names: \n{prod_text}\n\n\n"
    )
    result = {
        "families": families,
        "count": len(ordered),
        "glyph_names": ordered,
        "slash_text": "".join(slash),
        "characters": text,
        "nice_names": nice_text,
        "production_names": prod_text,
        "source_text": source,
        "production_metadata": mappings,
        "unicode_by_font": alternatives,
        "order_policy": "One font: original glyph order. Multiple fonts: sorted exact-name intersection; original set order was unspecified.",
        "character_policy": "First open-font carrier only; first assigned Unicode scalar, never alternate encodings or inferred ligature components.",
        "charcoal": {"default": False, "available": False, "reason": MARK_HOLD},
        "acceptance": "Partial implementation: report source repairs; full optional all-font action and native acceptance remain pending.",
    }
    check()
    return result


def render(report: dict, *, check: Callable = lambda: None) -> str:
    """Keep human-readable source sections plus exact escaped Unicode facts.

    Qt plain-text copying can fold NBSP and line separators. ASCII JSON escapes
    preserve every source scalar there, including NUL/supplementary values. The
    complete bounded serialization precedes any report widget update.
    Human-readable NUL is disclosed as an escape so native QString conversion
    cannot truncate the later exact JSON; the source_text fact remains unchanged.
    """
    check()
    chunks = []
    encoder = json.JSONEncoder(ensure_ascii=True, indent=2, allow_nan=False)
    for chunk in encoder.iterencode(report):
        check()
        chunks.append(chunk)
    source = report["source_text"]
    if "\0" in source:
        source = (
            "NUL is displayed as \\u0000; exact source text is retained in the escaped JSON below.\n\n"
            + source.replace("\0", "\\u0000")
        )
    text = source + "\nEncodings and production metadata:\n" + "".join(chunks)
    check()
    return text
