# this_file: src/fontlabapp/fontui/tmetrics_model.py
# SPDX-License-Identifier: Apache-2.0
"""Qt-free state of the TMetrics window: shaping, rows, readouts, fingerprint.

What: ``TMetricsModel`` holds the settings (text or ``/names``, features,
direction, script, language, kerning toggle, point size), shapes them with
``fontlabapp.fontui.shaping``, breaks the run into rows no wider than a wrap
width, maps cells to pixels (``Geometry``), keeps a visual selection and reads
out the selected glyph (advance, LSB, RSB) and the kerning pair before it.
``fingerprint`` digests the font state the window shows; the window records
it after its own writes for ``fontlabapp.fontui.livesync.Echo``.
``write_metric`` sets one glyph's LSB, RSB or advance width through a single
``font.edit_glyph`` on the default layer.
Use: ``fontlabapp.fontui.tmetrics.TMetrics`` drives it; tests drive it directly.
Why: the Qt layer stays a thin view; every rule here is unit-tested offscreen.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from hashlib import sha1
from math import isfinite
from typing import Any

from . import shaping
from ._font_reads import FontReads
from .model import outline

__all__ = [
    "Cell",
    "Geometry",
    "GlyphReadout",
    "Metrics",
    "PairReadout",
    "Settings",
    "TMetricsModel",
    "break_rows",
    "fingerprint",
    "kerning_pair",
    "read_metrics",
    "sidebearings",
    "write_metric",
]

DIRECTIONS = ("ltr", "rtl")
METRIC_FIELDS = {"lsb": "LSB", "rsb": "RSB", "width": "width"}
SHAPED_NOTE = "shaped (HarfBuzz)"
NO_TEXT_NOTE = "No text"
NO_FONT_NOTE = "No font"
DEFAULT_SIZE = 72
MARGIN = 20  # canvas pixels around the rows
ROW_GAP = 20  # canvas pixels between rows
KERN1, KERN2 = "public.kern1.", "public.kern2."


@dataclass(frozen=True)
class Settings:
    """What to shape and how large to draw it (``size`` is pixels per em)."""

    text: str = ""
    features: str = ""
    direction: str = "ltr"
    script: str = ""
    language: str = ""
    kerning: bool = True
    size: float = DEFAULT_SIZE


@dataclass(frozen=True)
class Metrics:
    """Vertical font metrics in font units; None when the font does not say."""

    upm: float = 1000.0
    ascender: float | None = None
    descender: float | None = None
    x_height: float | None = None
    cap_height: float | None = None

    @property
    def top(self) -> float:
        """Row top above the baseline: the ascender, or 80% of the em."""
        return self.ascender if self.ascender is not None else self.upm * 0.8

    @property
    def bottom(self) -> float:
        """Row bottom (negative): the descender, or -20% of the em."""
        return self.descender if self.descender is not None else -self.upm * 0.2

    def lines(self) -> list[tuple[str, float]]:
        """Return the known guide lines as ``(label, y)``, baseline first."""
        named = (
            ("ascender", self.ascender),
            ("cap height", self.cap_height),
            ("x-height", self.x_height),
            ("descender", self.descender),
        )
        return [("baseline", 0.0)] + [(k, v) for k, v in named if v is not None]


@dataclass(frozen=True)
class Cell:
    """One shaped glyph in visual order, placed in its row (font units).

    ``width`` is the glyph's own advance width (the placed advance when the
    glyph is missing); ``kern`` is the extra space after it that kerning or
    positioning added; ``lsb``/``rsb`` are None for empty or missing glyphs.
    ``mark`` is True for a mark (GDEF class mark when the shaping font has
    glyph classes, else a glyph whose own nominal width is 0);
    a mark's ``kern`` is always 0, so it never gets a kern bar.
    """

    index: int
    name: str
    cluster: int
    row: int
    x: float
    width: float
    kern: float
    x_offset: float = 0.0
    y_offset: float = 0.0
    lsb: float | None = None
    rsb: float | None = None
    present: bool = True
    mark: bool = False


@dataclass(frozen=True)
class GlyphReadout:
    """The selected glyph's advance and sidebearings."""

    name: str
    advance: float
    lsb: float | None
    rsb: float | None

    def text(self) -> str:
        """Return ``name  advance N  LSB N  RSB N`` (``–`` for an empty glyph)."""
        return (
            f"{self.name}  advance {_number(self.advance)}  "
            f"LSB {_number(self.lsb)}  RSB {_number(self.rsb)}"
        )


@dataclass(frozen=True)
class PairReadout:
    """The kerning pair ending at the selected glyph, in logical order.

    ``kind`` is ``"glyph"`` (both sides glyphs), ``"group"`` (a group on at
    least one side) or ``"none"``; ``key`` is the matching kerning key.
    """

    left: str
    right: str
    value: float
    kind: str
    key: tuple[str, str] | None = None

    def text(self) -> str:
        """Return ``Pair L R: value (group pair a b)`` or ``…: no kerning``."""
        head = f"Pair {self.left} {self.right}"
        if self.key is None:
            return f"{head}: no kerning"
        return f"{head}: {_number(self.value)} ({self.kind} pair {self.key[0]} {self.key[1]})"


@dataclass(frozen=True)
class Geometry:
    """Pixel layout of the rows: origin per cell, canvas size, hit testing."""

    scale: float
    width: float
    height: float
    row_height: float
    origins: tuple[tuple[float, float], ...]  # (x, baseline) per cell, pixels

    def row_top(self, row: int) -> float:
        """Return the top pixel of ``row``."""
        return MARGIN + row * self.row_height


def _number(value: float | None) -> str:
    if value is None:
        return "–"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def read_metrics(font: Any) -> Metrics:
    """Read upm and vertical metrics from ``font.info``; bad values become None."""
    info = getattr(font, "info", None)
    upm = _finite(getattr(info, "unitsPerEm", None))
    return Metrics(
        upm=upm if upm and upm > 0 else 1000.0,
        ascender=_finite(getattr(info, "ascender", None)),
        descender=_finite(getattr(info, "descender", None)),
        x_height=_finite(getattr(info, "xHeight", None)),
        cap_height=_finite(getattr(info, "capHeight", None)),
    )


def _glyph(font: Any, name: str) -> Any | None:
    try:
        return font[name] if name in font else None
    except Exception:
        return None


def sidebearings(
    font: Any, name: str, read: Any = None
) -> tuple[float | None, float | None, float | None]:
    """Return ``(width, lsb, rsb)`` of glyph ``name``; None where unknown.

    ``read`` replaces :func:`outline` (a per-refresh cache).
    """
    glyph = _glyph(font, name)
    if glyph is None:
        return None, None, None
    width = _finite(getattr(glyph, "width", None))
    try:
        bounds = (read or outline)(font, name).bounds
    except Exception:
        bounds = None
    if bounds is None or width is None:
        return width, None, None
    return width, bounds[0], width - bounds[2]


def _layer_sidebearings(
    font: Any, name: str, layer: str
) -> tuple[float | None, float | None, float | None]:
    """``(width, lsb, rsb)`` of ``name`` on the named ``layer``; ValueError when absent."""
    try:
        glyph = font.getLayer(layer)[name]
    except Exception:
        raise ValueError(f"Glyph not found: {name} on layer {layer}") from None
    width = _finite(getattr(glyph, "width", None))
    bounds = getattr(glyph, "bounds", None)
    if bounds is None or width is None:
        return width, None, None
    return width, bounds[0], width - bounds[2]


def write_metric(
    font: Any,
    name: str,
    metric: str,
    value: float,
    *,
    layer: str | None = None,
    undo_name: str | None = None,
) -> bool:
    """Set ``metric`` (``lsb``, ``rsb`` or ``width``) of glyph ``name`` to ``value``.

    One ``font.edit_glyph(name, layer=<layer>, undo_name=<undo_name>)`` per
    call. ``layer`` defaults to ``font.defaultLayerName``; a different layer
    reads its metrics from ``font.getLayer(layer)``. ``undo_name`` defaults to
    ``"TMetrics: <LSB|RSB|width> <name>"``. LSB shifts
    contours, components and anchors horizontally and grows the width by the
    same amount, keeping RSB; RSB and width change only the advance. Return
    False (no write) when the value already holds; raise ValueError for an
    unknown field, a non-finite value, a missing glyph or a sidebearing of an
    empty glyph, and TypeError for a font without ``edit_glyph``.
    """
    label = METRIC_FIELDS.get(metric)
    if label is None:
        raise ValueError(f"Unknown metric: {metric}")
    number = _finite(value)
    if number is None:
        raise ValueError(f"{label} must be a finite number")
    if not callable(getattr(font, "edit_glyph", None)):
        raise TypeError("Read-only: font has no edit_glyph")
    if _glyph(font, name) is None:
        raise ValueError(f"Glyph not found: {name}")
    default = getattr(font, "defaultLayerName", None)
    target = default if layer is None else layer
    if target == default:
        width, lsb, rsb = sidebearings(font, name)
    else:
        width, lsb, rsb = _layer_sidebearings(font, name, target)
    current = {"lsb": lsb, "rsb": rsb, "width": width}[metric]
    if metric != "width" and current is None:
        raise ValueError(f"{name} has no outline; set its advance width instead")
    if current is not None and current == number:
        return False
    undo = f"TMetrics: {label} {name}" if undo_name is None else undo_name
    with font.edit_glyph(name, layer=target, undo_name=undo) as glyph:
        if metric == "width":
            glyph.width = number
        elif metric == "rsb":
            glyph.width = glyph.width + number - current
        else:
            shift = number - current
            for item in (*glyph.contours, *glyph.components, *glyph.anchors):
                item.moveBy((shift, 0))
            glyph.width = glyph.width + shift
    return True


def kerning_pair(font: Any, left: str, right: str) -> PairReadout:
    """Look up the effective kerning of ``left``/``right`` and which key gives it.

    Precedence follows UFO: glyph-glyph, glyph-group, group-glyph, group-group.
    """
    try:
        pairs = dict(font.kerning.items())
        groups = dict(font.groups.items())
    except Exception:
        return PairReadout(left, right, 0.0, "none")
    first = [k for k, v in groups.items() if k.startswith(KERN1) and left in v]
    second = [k for k, v in groups.items() if k.startswith(KERN2) and right in v]
    lefts, rights = [left] + first[:1], [right] + second[:1]
    for key in ((a, b) for a in lefts for b in rights):
        if key in pairs:
            value = _finite(pairs[key]) or 0.0
            kind = "glyph" if key == (left, right) else "group"
            return PairReadout(left, right, value, kind, key)
    return PairReadout(left, right, 0.0, "none")


def fingerprint(font: Any, names: list[str] | tuple[str, ...], read: Any = None) -> str:
    """Digest what the window shows of ``font``: names, metrics, kerning, features
    and the width, Unicodes and outline of each glyph in ``names``.

    Never raises: unreadable parts digest as their error type.
    """
    parts: list[Any] = []
    for part in (
        lambda: sorted(font.keys()),
        lambda: read_metrics(font),
        lambda: font.kerning_digest() if hasattr(font, "kerning_digest") else sorted(font.kerning.items()),
        lambda: sorted((k, tuple(v)) for k, v in font.groups.items()),
        lambda: font.features.text or "",
    ):
        try:
            parts.append(part())
        except Exception as error:
            parts.append(type(error).__name__)
    for name in sorted(set(names)):
        glyph = _glyph(font, name)
        if glyph is None:
            parts.append((name, None))
            continue
        try:
            shape = (read or outline)(font, name).recording
        except Exception as error:
            shape = type(error).__name__
        parts.append((name, getattr(glyph, "width", None), tuple(getattr(glyph, "unicodes", ()) or ()), shape))
    return sha1(repr(parts).encode("utf-8")).hexdigest()


def _relayer(
    run: tuple[shaping.PlacedGlyph, ...],
    spans: list[float],
    own: list[tuple[float | None, float | None, float | None]],
    default_widths: list[float | None],
) -> tuple[tuple[shaping.PlacedGlyph, ...], list[float]]:
    """Re-space a run shaped on the default layer with the target layer's widths.

    Each glyph keeps its kerning (span minus its default width) and takes its
    layer width, so the preview and rows follow the layer being edited.
    """
    placed, new_spans, x = [], [], run[0].x if run else 0.0
    for i, glyph in enumerate(run):
        width, default = own[i][0], default_widths[i]
        span = spans[i] if width is None or default is None else max(spans[i] - default + width, 0.0)
        advance = glyph.advance if width is None or default is None else glyph.advance - default + width
        placed.append(replace(glyph, x=x, advance=advance))
        new_spans.append(span)
        x += span
    return tuple(placed), new_spans


def break_rows(
    run: tuple[shaping.PlacedGlyph, ...], widths: list[float], width: float | None, direction: str
) -> list[tuple[int, float]]:
    """Return ``(row, x)`` per glyph of ``run`` (visual order), rows at most ``width``.

    Rows break in reading order (right to left for RTL) and each row restarts
    at x 0 on its visual left. A glyph wider than ``width`` gets its own row.
    ``widths`` are the space each glyph takes (advance plus kerning).
    """
    count = len(run)
    order = list(range(count)) if direction == "ltr" else list(range(count - 1, -1, -1))
    rows = [0] * count
    if width is not None and isfinite(width) and width > 0:
        row, used = 0, 0.0
        for i in order:
            if used > 0 and used + widths[i] > width:
                row, used = row + 1, 0.0
            rows[i], used = row, used + widths[i]
    starts: dict[int, float] = {}
    for i in range(count):
        starts[rows[i]] = min(starts.get(rows[i], run[i].x), run[i].x)
    return [(rows[i], run[i].x - starts[rows[i]]) for i in range(count)]


@dataclass
class TMetricsModel:
    """Shaped text over ``font`` with rows, a visual selection and readouts."""

    font: Any
    settings: Settings = field(default_factory=Settings)
    result: shaping.GlyphRunResult | None = None
    cells: tuple[Cell, ...] = ()
    status: str = NO_TEXT_NOTE
    metrics: Metrics = field(default_factory=Metrics)
    selected: int | None = None
    wrap_width: float | None = None  # font units
    layer: str | None = None  # None or the default layer: read the font itself
    _outlines: dict[tuple[int, str], tuple[Any, Any]] | None = field(default=None, repr=False)

    @property
    def plain_font(self) -> Any:
        """The font itself, without the read memo TMetrics wraps it in."""
        return self.font.font if isinstance(self.font, FontReads) else self.font

    @property
    def source(self) -> Any:
        """The glyph set read for metrics and outlines: ``font.getLayer(layer)``, else the font.

        Shaping, kerning and font info always come from the font; a missing
        layer reads as the font so the view stays usable and the status names it.
        """
        if self.layer is None or self.font is None or self.layer == getattr(self.font, "defaultLayerName", None):
            return self.plain_font
        try:
            return self.font.getLayer(self.layer)
        except Exception:
            return self.plain_font

    @contextmanager
    def outline_scope(self, kept: dict[Any, Any] | None = None) -> Iterator[None]:
        """Share one outline per glyph across every read inside the block (one refresh).

        Outside a scope each read builds afresh, so a follow poll always sees the font as it is.
        ``kept`` carries the outlines over to later scopes (typing reuses them);
        the caller clears it whenever the font may have changed.
        """
        previous, self._outlines = self._outlines, ({} if kept is None else kept)
        try:
            yield
        finally:
            self._outlines = previous

    def outline_of(self, font: Any, name: str) -> Any:
        """``outline(font, name)``, built once per scope; failures are not remembered."""
        if isinstance(font, FontReads):
            font = font.font
        if self._outlines is None:
            return outline(font, name)
        key = (id(font), name)
        if key not in self._outlines or self._outlines[key][1] is not font:
            self._outlines[key] = (outline(font, name), font)
        return self._outlines[key][0]

    def update(self, **changes: Any) -> None:
        """Replace settings fields and re-shape, keeping the selection index."""
        self.settings = replace(self.settings, **changes)
        self.reshape()

    def reshape(self) -> None:
        """Shape the text again from the font (after edits or setting changes)."""
        self.metrics = read_metrics(self.font)
        self.result, self.status = self._shape()
        self._place()
        if self.selected is not None:
            self.selected = min(self.selected, len(self.cells) - 1) if self.cells else None

    def _shape(self) -> tuple[shaping.GlyphRunResult | None, str]:
        settings = self.settings
        if self.font is None:
            return None, NO_FONT_NOTE
        if not settings.text.strip():
            return None, NO_TEXT_NOTE
        try:
            result = shaping.shape(
                self.font,
                settings.text,
                features=settings.features,
                direction=settings.direction,
                script=settings.script.strip() or None,
                language=settings.language.strip() or None,
                kerning=settings.kerning,
            )
        except Exception as error:
            return None, f"Cannot shape: {error}"
        notes = list(result.diagnostics)
        if result.shaped:
            notes.insert(0, SHAPED_NOTE)
        return result, "; ".join(notes) or SHAPED_NOTE

    def set_wrap_width(self, width: float | None) -> bool:
        """Set the row width in font units; return True when the rows changed."""
        if width == self.wrap_width:
            return False
        self.wrap_width = width
        self._place()
        return True

    def _place(self) -> None:
        run = self.result.glyphs if self.result is not None else ()
        order = sorted(range(len(run)), key=lambda i: (run[i].x, i))
        run = tuple(run[i] for i in order)
        own: list[tuple[float | None, float | None, float | None]] = []
        cache: dict[str, Any] = {}
        source = self.source
        # The default layer reads through the font memo, so typing does not
        # re-check each glyph name against the whole font.
        glyphs = self.font if source is self.plain_font else source
        for placed in run:
            if placed.name not in cache:
                cache[placed.name] = sidebearings(glyphs, placed.name, self.outline_of)
            own.append(cache[placed.name])
        spans = []
        for i, placed in enumerate(run):
            end = run[i + 1].x if i + 1 < len(run) else placed.x + placed.advance
            spans.append(max(end - placed.x, 0.0))
        if source is not self.plain_font:
            run, spans = _relayer(run, spans, own, [sidebearings(self.font, p.name, self.outline_of)[0] for p in run])
        rows = break_rows(run, spans, self.wrap_width, self.settings.direction)
        cells = []
        for i, placed in enumerate(run):
            width, lsb, rsb = own[i]
            present = width is not None
            width = width if present else float(placed.advance)
            # GDEF decides when present; else the glyph's own nominal width, never the
            # shaped advance (it already includes kerning).
            mark = placed.mark if placed.mark is not None else present and width == 0
            cells.append(
                Cell(
                    index=i,
                    name=placed.name,
                    cluster=placed.cluster,
                    row=rows[i][0],
                    x=rows[i][1],
                    width=width,
                    kern=0.0 if mark else spans[i] - width,
                    x_offset=float(placed.x_offset),
                    y_offset=float(placed.y_offset),
                    lsb=lsb,
                    rsb=rsb,
                    present=present,
                    mark=mark,
                )
            )
        self.cells = tuple(cells)

    @property
    def rows(self) -> int:
        """Return the number of rows (0 without cells)."""
        return max((c.row for c in self.cells), default=-1) + 1

    def geometry(self, viewport_width: float = 0.0) -> Geometry:
        """Map cells to pixels for a canvas at least ``viewport_width`` wide.

        RTL rows are right-aligned; LTR rows start at the left margin.
        """
        metrics = self.metrics
        scale = max(float(self.settings.size), 1.0) / metrics.upm
        row_height = (metrics.top - metrics.bottom) * scale + ROW_GAP
        row_widths = [0.0] * max(self.rows, 1)
        for c in self.cells:
            row_widths[c.row] = max(row_widths[c.row], c.x + c.width + max(c.kern, 0.0))
        width = max(viewport_width, max(row_widths) * scale + 2 * MARGIN)
        origins = []
        for c in self.cells:
            left = MARGIN if self.settings.direction == "ltr" else width - MARGIN - row_widths[c.row] * scale
            baseline = MARGIN + c.row * row_height + metrics.top * scale
            origins.append((left + c.x * scale, baseline))
        height = 2 * MARGIN + max(self.rows, 1) * row_height - ROW_GAP
        return Geometry(scale, width, height, row_height, tuple(origins))

    def cell_at(self, geometry: Geometry, x: float, y: float) -> int | None:
        """Return the cell index under pixel ``(x, y)``, or None."""
        for c, (left, _baseline) in zip(self.cells, geometry.origins, strict=False):
            top = geometry.row_top(c.row)
            right = left + max(c.width + c.kern, 1.0) * geometry.scale
            if left <= x < right and top <= y < top + geometry.row_height:
                return c.index
        return None

    def select(self, index: int | None) -> bool:
        """Select cell ``index`` (None clears); return True when it changed."""
        if index is not None and not 0 <= index < len(self.cells):
            return False
        changed, self.selected = index != self.selected, index
        return changed

    def move(self, step: str) -> bool:
        """Move the selection: ``left``/``right`` visually, ``home``/``end`` logically."""
        if not self.cells:
            return False
        last = len(self.cells) - 1
        rtl = self.settings.direction == "rtl"
        current = self.selected
        if step in ("home", "end"):
            target = 0 if (step == "home") != rtl else last
        elif step in ("left", "right"):
            if current is None:
                target = 0 if step == "right" else last
            else:
                target = max(0, min(last, current + (1 if step == "right" else -1)))
        else:
            return False
        return self.select(target) or True

    def selected_cell(self) -> Cell | None:
        """Return the selected cell, or None."""
        return self.cells[self.selected] if self.selected is not None else None

    def glyph_readout(self) -> GlyphReadout | None:
        """Return the selected glyph's advance and sidebearings, or None."""
        cell = self.selected_cell()
        if cell is None:
            return None
        return GlyphReadout(cell.name, cell.width, cell.lsb, cell.rsb)

    def pair_readout(self) -> PairReadout | None:
        """Return the kerning pair ending at the selected glyph, or None at the start."""
        cell = self.selected_cell()
        if cell is None:
            return None
        before = cell.index + (1 if self.settings.direction == "rtl" else -1)
        if not 0 <= before < len(self.cells):
            return None
        return kerning_pair(self.font, self.cells[before].name, cell.name)

    def fingerprint(self) -> str:
        """Digest the font state behind the current cells, plus the target layer's glyphs."""
        names = [c.name for c in self.cells]
        digest = fingerprint(self.font, names, self.outline_of)
        source = self.source
        return digest if source is self.plain_font else digest + fingerprint(source, names, self.outline_of)
