# this_file: src/fontlabapp/proof/crossfont/model.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Jens Kutilek's complete ordered composite and glyph-set comparisons.

Reference/target selection follows the originals, without a replacement chooser.
The owned report replaces printing to the user's Output; no font is changed.
"""
from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any
from time import monotonic

@dataclass(frozen=True)
class Glyph:
    """One original font-order name and ordered own component base sequence."""
    name: str
    components: tuple[str, ...] = ()

@dataclass(frozen=True)
class Font:
    """One open document, exact source filepath and selected named master."""
    identity: int
    path: str | None
    master: str
    glyphs: tuple[Glyph, ...]

@dataclass(frozen=True)
class Snapshot:
    """Current reference identity plus original open-document order."""
    current: int
    fonts: tuple[Font, ...]

def _reference(snapshot: Snapshot) -> tuple[Font, tuple[Font, ...]]:
    source = next((f for f in snapshot.fonts if f.identity == snapshot.current), None)
    others = tuple(f for f in snapshot.fonts if f.identity != snapshot.current)
    if source is None:
        raise ValueError("Open a current reference font.")
    return source, others

def _check(deadline: float | None) -> None:
    if deadline is not None and monotonic() >= deadline:
        raise TimeoutError("Cross-font report deadline expired; refresh.")

def _glyphs(font: Font, deadline: float | None) -> Iterator[Glyph]:
    for glyph in font.glyphs:
        _check(deadline)
        yield glyph

def composite_text(snapshot: Snapshot, *, deadline: float | None = None) -> str:
    """Compare first other font only; preserve source order and exact suffix exclusions."""
    _check(deadline)
    source, others = _reference(snapshot)
    if not others:
        raise ValueError("Open another font for the composite comparison.")
    target = {g.name: g for g in _glyphs(others[0], deadline)}
    lines, missing = [], []
    for glyph in _glyphs(source, deadline):
        _check(deadline)
        other = target.get(glyph.name)
        if other is not None:
            if other.components != glyph.components:
                lines.append(f"{glyph.name};{' '.join(glyph.components)};{' '.join(other.components)};")
        elif not glyph.name.endswith((".sc", ".pcap")):
            missing.append(glyph.name)
    _check(deadline)
    return "".join(line + "\n" for line in lines) + "\nMissing in target:\n\n" + "\n".join(missing) + "\n"

def glyph_sets_text(snapshot: Snapshot, *, deadline: float | None = None) -> str:
    """Compare every other font; retain raw filepath and both independent scan orders."""
    _check(deadline)
    source, others = _reference(snapshot)
    reference = tuple(g.name for g in _glyphs(source, deadline))
    reference_set = set(reference)
    lines = []
    for font in others:
        _check(deadline)
        lines.append(str(font.path))
        names = tuple(g.name for g in _glyphs(font, deadline))
        lines.extend(f"    Extra: {name}" for name in names if name not in reference_set)
        present = set(names)
        lines.extend(f"    Missing: {name}" for name in reference if name not in present)
    _check(deadline)
    return "\n".join(lines) + "\n" if lines else ""

def show(*, composites: bool = False) -> Any:
    """Open the complete original report through the package-owned lazy Fly API."""
    from fontlabapp.proof.crossfont.ui import open_report
    return open_report(composites=composites)
