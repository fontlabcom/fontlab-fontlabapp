# this_file: src/fontlabapp/fontui/model.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only view state and decomposed drawing inputs for duck-typed glyph/font models."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class FontListState:
    """Borrow fonts without replacing identity by equality or display labels."""

    def __init__(self, fonts: Iterable[Any] = ()) -> None:
        self.fonts = ()
        self.selected = None
        self.sorted = False
        self.refresh(fonts)

    @staticmethod
    def label(font: Any) -> str:
        info = font.info
        family = getattr(info, "familyName", None) or "Untitled"
        style = getattr(info, "styleName", None) or ""
        path = getattr(font, "path", None)
        filename = Path(path).name if path else "Untitled"
        dirty = " *" if getattr(font, "dirty", False) else ""
        identity = f"{family} {style}".rstrip()
        return f"{identity} — {filename}{dirty}"

    @property
    def index(self) -> int | None:
        return next(
            (i for i, font in enumerate(self.fonts) if font is self.selected), None
        )

    def refresh(self, fonts: Iterable[Any]) -> None:
        unique = []
        for font in fonts:
            if not any(font is previous for previous in unique):
                unique.append(font)
        records = []
        for font in unique:
            try:
                records.append((font, self.label(font), None))
            except RuntimeError as error:
                records.append((font, f"Unavailable font: {error}", str(error)))
        if self.sorted:
            records.sort(key=lambda record: record[1].casefold())
        self.fonts = tuple(record[0] for record in records)
        self.labels = tuple(record[1] for record in records)
        self.errors = tuple(record[2] for record in records)
        if self.index is None or self.errors[self.index] is not None:
            self.selected = None

    def select(self, index: int | None) -> None:
        if index is not None and not 0 <= index < len(self.fonts):
            raise IndexError(index)
        self.selected = (
            None if index is None or self.errors[index] else self.fonts[index]
        )

    def sort(self) -> None:
        self.sorted = True
        self.refresh(self.fonts)


class BrowserState:
    """Keep name identity independent of rows; caller refreshes model changes."""

    def __init__(self, font):
        self.font = font
        self.query = ""
        self.selected = ()
        self.mode = "list"
        self.cell_size = 96
        self.refresh()

    def refresh(self):
        self.error = None
        try:
            keys = tuple(self.font.keys()) if self.font is not None else ()
            order = tuple(getattr(self.font, "glyphOrder", ()) or ())
        except RuntimeError as error:
            keys, order, self.error = (), (), str(error)
        self.original = tuple(n for n in order if n in keys)
        self.original += tuple(n for n in keys if n not in self.original)
        self.filter(self.query)

    def filter(self, query):
        self.query = str(query)
        self.names = tuple(
            n for n in self.original if self.query.casefold() in n.casefold()
        )
        self.select(self.selected)

    def select(self, names):
        wanted = set(names)
        self.selected = tuple(n for n in self.names if n in wanted)


@dataclass(frozen=True)
class Outline:
    recording: tuple
    bounds: tuple | None
    width: float
    anchors: tuple


def partition_paths(recording: Iterable[tuple]) -> tuple[tuple, tuple]:
    """Keep open contours out of fill paths; Qt otherwise closes them to fill."""
    closed, opened, contour = [], [], []
    for command in recording:
        contour.append(command)
        if command[0] in ("closePath", "endPath"):
            (closed if command[0] == "closePath" else opened).extend(contour)
            contour = []
    opened.extend(contour)
    return tuple(closed), tuple(opened)


def _check_components(font, name, active=()):
    if name in active:
        raise ValueError("Cyclic component: " + " -> ".join((*active, name)))
    if name not in font:
        raise ValueError(f"Missing component or glyph: {name}")
    for component in font[name].components:
        _check_components(font, component.baseGlyph, (*active, name))


def outline(font, name):
    """Decompose affine components before drawing; reject broken graphs explicitly."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.recordingPen import DecomposingRecordingPen

    _check_components(font, name)
    glyph = font[name]
    pen = DecomposingRecordingPen(font, skipMissingComponents=False)
    glyph.draw(pen)
    bounds = BoundsPen(None)
    pen.replay(bounds)
    anchors = tuple((a.x, a.y, a.name or "") for a in glyph.anchors)
    return Outline(tuple(pen.value), bounds.bounds, float(glyph.width or 0), anchors)


def viewport(bounds, advance, descender, ascender, width, height, zoom=1):
    """Uniform fit including advance and font metrics; screen y points down."""
    left, bottom, right, top = bounds or (0, 0, advance, 0)
    left, right = min(0, left), max(advance, right)
    bottom, top = min(descender, bottom), max(ascender, top)
    scale = (
        max(
            0.001,
            min(
                max(1, width - 40) / max(1, right - left),
                max(1, height - 40) / max(1, top - bottom),
            ),
        )
        * zoom
    )
    return (
        scale,
        (width - (right + left) * scale) / 2,
        (height + (top + bottom) * scale) / 2,
    )
