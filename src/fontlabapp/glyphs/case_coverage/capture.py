# this_file: src/fontlabapp/glyphs/case_coverage/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Capture registered FontGate facts without fgGlyph, activation or selection.

Metadata callbacks belong to the caller; App imports neither Glyport nor
Glyphs-specific databases. Native reads use crossfont_anchors_capture.fonts.
"""

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any

from fontlabapp.glyphs.case_coverage.model import (
    GlyphFact,
    Options,
    analyze,
    checkpoint,
    character_texts,
)
from fontlabapp.anchors.crossfont.capture import fonts
from fontlabapp.core.scripting import current_package
from fontlabapp.glyphs.smallcaps.capture import EXPORT_SCOPE


@dataclass(frozen=True)
class FontReport:
    """Detached report bound to one exact registered font and current master."""

    identity: int
    fg_id: int
    label: str
    master: str
    report: dict


@dataclass(frozen=True)
class Snapshot:
    """Complete all-font transaction; no native handles retained by report UI."""

    current_id: int
    fonts: tuple[FontReport, ...]

    @property
    def all_clear(self) -> bool:
        """Return true only when every complete per-font analysis is clear."""
        return self.clear()

    def clear(self, check: Callable = lambda: None) -> bool:
        """Reduce detached status with an optional caller budget per font."""
        for font in self.fonts:
            check()
            if not font.report["all_clear"]:
                return False
        check()
        return True


def validate(
    snapshot: Snapshot, deadline: float, *, check: Callable = lambda: None
) -> None:
    """Refuse closed/switched fonts or masters before report/proof publication."""
    check()
    current = current_package()
    if current is None or current.id != snapshot.current_id:
        raise ValueError("The current font changed or closed; run Case Coverage again.")
    registered = {}
    for font in fonts(deadline, checkpoint=check):
        check()
        registered[font.identity] = font
    for record in snapshot.fonts:
        check()
        source = registered.get(record.identity)
        if source is None or source.fg_id != record.fg_id:
            raise ValueError("A reported font closed; run Case Coverage again.")
        if str(source.package.master) != record.master:
            raise ValueError("A reported master changed; run Case Coverage again.")
    check()


def _font_report(
    source: Any,
    metadata: Callable,
    preferred: Callable,
    options: Options,
    deadline: float,
    clock: Callable,
    cancelled: Callable,
) -> FontReport:
    """Capture one complete font with caller metadata and the shared deadline."""
    check = lambda: checkpoint(deadline, clock, cancelled)
    master = str(source.package.master)
    skip = source.package.packageLib.get("public.skipExportGlyphs", ())
    if not isinstance(skip, (list, tuple)):
        raise ValueError("public.skipExportGlyphs must be a list of glyph names.")
    for name in skip:
        check()
        if not isinstance(name, str):
            raise ValueError("public.skipExportGlyphs must be a list of glyph names.")
    skip = set(skip)
    facts, names = [], {}
    for glyph in source.font.glyphs:
        check()
        name = str(glyph.name)
        codes_list = []
        for code in glyph.unicodes:
            check()
            codes_list.append(int(code))
        codes = tuple(codes_list)
        check()
        subcategory, text = metadata(name, codes, checkpoint=check)
        check()
        fact = GlyphFact(
            name, codes, name not in skip, subcategory, text, validation_check=check
        )
        facts.append(fact)
        for char in character_texts(fact, check):
            check()
            for mapped in (char.lower(), char.upper()):
                check()
                if mapped not in names:
                    canonical = preferred(mapped, checkpoint=check)
                    check()
                    if canonical:
                        names[mapped] = canonical
    report = analyze(
        facts, names, options, deadline=deadline, clock=clock, cancelled=cancelled
    )
    report.update(
        export_scope=EXPORT_SCOPE,
        metadata_policy="Caller-supplied GlyphData compatibility metadata; unknowns explicit",
    )
    label = source.label or str(source.font.info.familyName) + " (not saved)"
    check()
    return FontReport(source.identity, source.fg_id, label, master, report)


def read(
    options: Options,
    metadata: Callable,
    preferred: Callable,
    *,
    clock: Callable = monotonic,
    cancelled: Callable = lambda: False,
    deadline: float | None = None,
) -> Snapshot:
    """Capture every requested font under one budget, then revalidate identities.

    Synchronous native getters cannot be preempted; checks run before/after
    them and throughout every Python loop. No partial report is returned.
    """
    limit = clock() + 3.0 if deadline is None else deadline
    check = lambda: checkpoint(limit, clock, cancelled)
    check()
    current = current_package()
    if current is None:
        raise ValueError("Open a font before running Case Coverage.")
    check()
    selected = []
    for source in fonts(limit, checkpoint=check):
        check()
        if options.allFonts or source.identity == current.id:
            selected.append(
                _font_report(
                    source, metadata, preferred, options, limit, clock, cancelled
                )
            )
    if not selected:
        raise ValueError("The current font is no longer registered; run again.")
    snapshot = Snapshot(int(current.id), tuple(selected))
    validate(snapshot, limit, check=check)
    return snapshot
