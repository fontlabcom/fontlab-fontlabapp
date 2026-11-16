# this_file: src/fontlabapp/fontui/tglyph_model.py
# SPDX-License-Identifier: Apache-2.0
"""Qt-free model behind the TGlyph window: one glyph on one explicit layer.

What: ``read_glyph(font, name, layer)`` reads a glyph's contours, components,
anchors and advance from ``font.getLayer(layer)`` through a point pen and
returns plain values (never live glyph objects, which a FontLab commit
invalidates). Components are decomposed through the same layer for drawing
only; a missing base or a component cycle marks that component unavailable.
When Fontport refuses the glyph itself (``UnsupportedCapability`` while
loading its component graph), ``own_glyph`` reads the own contours from an
aborted ``edit_glyph`` staging block, which writes nothing.
``View`` maps font units to screen pixels (y up in the font, y down on the
screen) with zoom about a point, pan and fit. ``hit_point`` finds the point
under the cursor within a tolerance in screen pixels. ``signature`` describes
the point structure (contour count, point types, components) without
coordinates, so a live follow can keep the selection while points only move;
``fingerprint`` digests every value a refresh shows, for
``fontlabapp.fontui.livesync.Echo``.
Use: ``TGlyphModel(font, name, layer)``; ``fontlabapp.fontui.tglyph`` draws it.
Why: geometry, hit-testing and change detection stay testable without Qt.
"""

import hashlib
import math
from dataclasses import dataclass, field, replace
from typing import Any

from .tmetrics_model import Metrics, read_metrics

__all__ = [
    "HIT_TOLERANCE",
    "Anchor",
    "Component",
    "Contour",
    "GlyphData",
    "Point",
    "TGlyphModel",
    "View",
    "bounds",
    "default_layer",
    "fingerprint",
    "hit_point",
    "layer_names",
    "neighbour",
    "own_glyph",
    "read_glyph",
    "signature",
]

HIT_TOLERANCE = 6.0  # screen pixels
ZOOM_STEP = 1.25
MIN_SCALE = 0.005
MAX_SCALE = 64.0
FIT_MARGIN = 24.0  # screen pixels around the fitted box
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass(frozen=True)
class Point:
    """One contour point in font units; ``type`` is None for an off-curve point."""

    x: float
    y: float
    type: str | None = None
    smooth: bool = False

    @property
    def on_curve(self) -> bool:
        return self.type is not None


@dataclass(frozen=True)
class Contour:
    """Points in drawing order; an open contour starts with a ``move`` point."""

    points: tuple[Point, ...]

    @property
    def closed(self) -> bool:
        return not self.points or self.points[0].type != "move"


@dataclass(frozen=True)
class Component:
    """A component: base name, 2x3 transformation and its decomposed contours."""

    base: str
    transformation: tuple[float, ...]
    contours: tuple[Contour, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class Anchor:
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class GlyphData:
    """Everything TGlyph shows of one glyph on one layer, as plain values."""

    name: str
    layer: str
    width: float = 0.0
    contours: tuple[Contour, ...] = ()
    components: tuple[Component, ...] = ()
    anchors: tuple[Anchor, ...] = ()


class _Collector:
    """Point pen that records contours and components as plain values."""

    def __init__(self) -> None:
        self.contours: list[Contour] = []
        self.components: list[tuple[str, tuple[float, ...]]] = []
        self._current: list[Point] | None = None

    def beginPath(self, identifier: Any = None, **kwargs: Any) -> None:
        self._current = []

    def addPoint(
        self,
        pt: Any,
        segmentType: str | None = None,
        smooth: bool = False,
        name: Any = None,
        identifier: Any = None,
        **kwargs: Any,
    ) -> None:
        if self._current is None:
            self._current = []
        self._current.append(Point(float(pt[0]), float(pt[1]), segmentType, bool(smooth)))

    def endPath(self) -> None:
        if self._current:
            self.contours.append(Contour(tuple(self._current)))
        self._current = None

    def addComponent(self, baseGlyphName: str, transformation: Any, identifier: Any = None, **kwargs: Any) -> None:
        self.components.append((str(baseGlyphName), tuple(float(v) for v in transformation)))


def _transform(point: Point, matrix: tuple[float, ...]) -> Point:
    xx, xy, yx, yy, dx, dy = matrix
    return Point(xx * point.x + yx * point.y + dx, xy * point.x + yy * point.y + dy, point.type, point.smooth)


def _compose(outer: tuple[float, ...], inner: tuple[float, ...]) -> tuple[float, ...]:
    """Matrix applying ``inner`` first, then ``outer``."""
    a, b, c, d, e, f = outer
    xx, xy, yx, yy, dx, dy = inner
    return (
        a * xx + c * xy,
        b * xx + d * xy,
        a * yx + c * yy,
        b * yx + d * yy,
        a * dx + c * dy + e,
        b * dx + d * dy + f,
    )


def _collect(layer: Any, name: str) -> _Collector:
    collector = _Collector()
    layer[name].drawPoints(collector)
    return collector


def _decompose(layer: Any, base: str, matrix: tuple[float, ...], seen: tuple[str, ...]) -> list[Contour]:
    if base in seen:
        raise ValueError(f"component cycle through {base}")
    if base not in layer:
        raise KeyError(f"base glyph {base} is not on this layer")
    collector = _collect(layer, base)
    contours = [Contour(tuple(_transform(p, matrix) for p in c.points)) for c in collector.contours]
    for inner_base, inner in collector.components:
        contours.extend(_decompose(layer, inner_base, _compose(matrix, inner), (*seen, base)))
    return contours


def _component(layer: Any, owner: str, base: str, matrix: tuple[float, ...]) -> Component:
    try:
        contours = _decompose(layer, base, matrix, (owner,))
        return Component(base, matrix, tuple(contours))
    except (KeyError, ValueError, RecursionError, NotImplementedError) as error:
        # NotImplementedError: Fontport's UnsupportedCapability (cyclic or unsupported base).
        return Component(base, matrix, (), str(error.args[0] if error.args else error))


def layer_names(font: Any) -> list[str]:
    """The font's layer (master) names in order; the default layer alone when unknown."""
    try:
        names = [str(name) for name in font.layerOrder]
    except Exception:
        names = []
    if names:
        return names
    return [default_layer(font)]


def default_layer(font: Any) -> str:
    """The font's default layer name (``public.default`` when it names none)."""
    name = getattr(font, "defaultLayerName", None)
    return str(name) if name else "public.default"


def _layer(font: Any, layer: str) -> Any:
    getter = getattr(font, "getLayer", None)
    if callable(getter):
        try:
            return getter(layer)
        except ValueError as error:  # fontParts: "No layer with the name ..."
            raise KeyError(f"layer {layer} is not available") from error
    if layer != default_layer(font):
        raise KeyError(f"layer {layer} is not available")
    return font


def read_glyph(font: Any, name: str, layer: str) -> GlyphData:
    """Read ``name`` on ``layer`` of ``font`` into plain values.

    Raises KeyError when the layer or the glyph does not exist; every other
    backend error propagates for the caller's status line.
    """
    source = _layer(font, layer)
    if name not in source:
        raise KeyError(f"{name} is not on layer {layer}")
    glyph = source[name]
    collector = _Collector()
    glyph.drawPoints(collector)
    components = tuple(_component(source, name, base, matrix) for base, matrix in collector.components)
    anchors = tuple(
        Anchor(str(anchor.name or ""), float(anchor.x), float(anchor.y)) for anchor in getattr(glyph, "anchors", ())
    )
    return GlyphData(name, layer, float(glyph.width or 0), tuple(collector.contours), components, anchors)


class _Peeked(Exception):
    """Aborts a peek through ``edit_glyph`` before it writes."""


def own_glyph(font: Any, name: str, layer: str, reason: str) -> GlyphData | None:
    """Read ``name``'s own contours when its components cannot load, or None.

    Fontport's ``layer[name]`` loads the whole component graph first and
    raises ``UnsupportedCapability`` for a cyclic or missing base. Its public
    ``edit_glyph`` stages a copy straight from the backend without resolving
    components; aborting the block inside skips the write. Components are kept
    with their own decomposition error (``reason`` when the layer cannot be
    read at all) and no decomposed contours when that fails.
    """
    edit = getattr(font, "edit_glyph", None)
    if not callable(edit):
        return None
    peeked: list[tuple[GlyphData, list[tuple[str, tuple[float, ...]]]]] = []
    try:
        with edit(name, layer=layer, undo_name="TGlyph: Read " + name) as staged:
            collector = _Collector()
            staged.drawPoints(collector)
            pending = list(collector.components)
            components = tuple(Component(base, matrix, (), reason) for base, matrix in pending)
            anchors = tuple(
                Anchor(str(anchor.name or ""), float(anchor.x), float(anchor.y))
                for anchor in getattr(staged, "anchors", ())
            )
            peeked.append(
                (
                    GlyphData(name, layer, float(staged.width or 0), tuple(collector.contours), components, anchors),
                    pending,
                )
            )
            raise _Peeked
    except _Peeked:
        data, pending = peeked[0]
        try:
            source = _layer(font, layer)
            return replace(
                data, components=tuple(_component(source, name, base, matrix) for base, matrix in pending)
            )
        except Exception:  # noqa: BLE001 - unreadable layer: every component keeps the owner reason
            return data
    except Exception:
        return None
    return None  # an edit_glyph that swallowed the abort; treat as unreadable


def _read_shown(font: Any, name: str, layer: str) -> tuple[GlyphData | None, str]:
    """``read_glyph`` with the own-contours fallback; returns data and an owner-level error."""
    try:
        return read_glyph(font, name, layer), ""
    except NotImplementedError as error:
        reason = str(error)
        return own_glyph(font, name, layer, reason), reason


def signature(data: GlyphData | None) -> tuple:
    """Point structure without coordinates: equal while points only move."""
    if data is None:
        return ()
    return (
        data.name,
        data.layer,
        tuple((c.closed, tuple(p.type for p in c.points)) for c in data.contours),
        tuple(c.base for c in data.components),
    )


def fingerprint(data: GlyphData | None, metrics: Metrics | None = None, error: str = "") -> str:
    """Digest every value TGlyph shows; equal digests mean nothing visible changed."""
    parts: list[Any] = [error]
    if metrics is not None:
        parts.append((metrics.upm, metrics.ascender, metrics.descender, metrics.x_height, metrics.cap_height))
    if data is not None:
        parts.append((data.name, data.layer, data.width))
        parts.append(tuple(tuple((p.x, p.y, p.type, p.smooth) for p in c.points) for c in data.contours))
        parts.append(
            tuple(
                (c.base, c.transformation, c.error, tuple(tuple((p.x, p.y) for p in k.points) for k in c.contours))
                for c in data.components
            )
        )
        parts.append(tuple((a.name, a.x, a.y) for a in data.anchors))
    return hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()


def bounds(data: GlyphData | None) -> tuple[float, float, float, float] | None:
    """(xMin, yMin, xMax, yMax) of every contour and component point, or None."""
    if data is None:
        return None
    points = [p for c in data.contours for p in c.points]
    points += [p for k in data.components for c in k.contours for p in c.points]
    if not points:
        return None
    xs, ys = [p.x for p in points], [p.y for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def neighbour(order: list[str], name: str, step: int) -> str | None:
    """The glyph ``step`` places from ``name`` in ``order``, wrapping; None when empty."""
    if not order:
        return None
    if name not in order:
        return order[0]
    return order[(order.index(name) + step) % len(order)]


@dataclass
class View:
    """Font units to screen pixels: ``sx = dx + x * scale``, ``sy = dy - y * scale``."""

    scale: float = 0.5
    dx: float = 0.0
    dy: float = 0.0
    adjusted: bool = False  # the user zoomed or panned since the last fit

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        return self.dx + x * self.scale, self.dy - y * self.scale

    def to_font(self, sx: float, sy: float) -> tuple[float, float]:
        return (sx - self.dx) / self.scale, (self.dy - sy) / self.scale

    def zoom(self, factor: float, sx: float, sy: float) -> None:
        """Scale by ``factor`` (clamped) keeping the font point under ``(sx, sy)`` still."""
        if not math.isfinite(factor) or factor <= 0:
            return
        x, y = self.to_font(sx, sy)
        self.scale = min(max(self.scale * factor, MIN_SCALE), MAX_SCALE)
        self.dx = sx - x * self.scale
        self.dy = sy + y * self.scale
        self.adjusted = True

    def pan(self, ddx: float, ddy: float) -> None:
        self.dx += ddx
        self.dy += ddy
        self.adjusted = True

    def fit(self, box: tuple[float, float, float, float], width: float, height: float, margin: float = FIT_MARGIN) -> None:
        """Centre ``box`` (font units) in a ``width`` x ``height`` pixel area."""
        x0, y0, x1, y1 = box
        span_x, span_y = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
        room_x, room_y = max(width - 2 * margin, 1.0), max(height - 2 * margin, 1.0)
        self.scale = min(max(min(room_x / span_x, room_y / span_y), MIN_SCALE), MAX_SCALE)
        self.dx = width / 2 - (x0 + x1) / 2 * self.scale
        self.dy = height / 2 + (y0 + y1) / 2 * self.scale
        self.adjusted = False


def hit_point(
    data: GlyphData | None, view: View, sx: float, sy: float, tolerance: float = HIT_TOLERANCE
) -> tuple[int, int] | None:
    """(contour, point) index of the nearest own point within ``tolerance`` pixels."""
    if data is None:
        return None
    best, best_distance = None, tolerance
    for c, contour in enumerate(data.contours):
        for p, point in enumerate(contour.points):
            px, py = view.to_screen(point.x, point.y)
            distance = math.hypot(px - sx, py - sy)
            if distance <= best_distance:
                best, best_distance = (c, p), distance
    return best


@dataclass
class TGlyphModel:
    """The shown glyph, its layer, metrics, view and point selection."""

    font: Any
    name: str | None = None
    layer: str | None = None
    data: GlyphData | None = None
    metrics: Metrics = field(default_factory=Metrics)
    view: View = field(default_factory=View)
    selection: set[tuple[int, int]] = field(default_factory=set)
    status: str = ""

    def __post_init__(self) -> None:
        if self.layer is None:
            self.layer = default_layer(self.font)

    def layers(self) -> list[str]:
        return layer_names(self.font)

    def glyph_order(self) -> list[str]:
        """Glyph names in the font's glyph order, falling back to its keys."""
        try:
            order = [str(n) for n in self.font.glyphOrder]
        except Exception:
            order = []
        try:
            present = [str(n) for n in self.font.keys()]
        except Exception:
            present = []
        known = set(present)
        ordered = [n for n in order if n in known] if known else order
        return ordered + sorted(known.difference(ordered))

    def box(self) -> tuple[float, float, float, float]:
        """The advance box (0..width, descender..ascender) united with the outline bounds."""
        width = self.data.width if self.data is not None else self.metrics.upm / 2
        x0, y0, x1, y1 = 0.0, self.metrics.bottom, max(width, 1.0), self.metrics.top
        outline = bounds(self.data)
        if outline is not None:
            x0, y0, x1, y1 = min(x0, outline[0]), min(y0, outline[1]), max(x1, outline[2]), max(y1, outline[3])
        return x0, y0, x1, y1

    def fit(self, width: float, height: float) -> None:
        self.view.fit(self.box(), width, height)

    def read(self) -> None:
        """Re-read metrics and the glyph; failures become ``status`` and no data."""
        self.metrics = read_metrics(self.font)
        self.data, self.status = None, ""
        if self.name is None:
            self.status = "Type a glyph name."
            return
        if self.layer not in self.layers():
            self.status = f"Layer {self.layer} is not in this font."
            return
        try:
            self.data, owner_error = _read_shown(self.font, self.name, self.layer)
        except KeyError as error:
            self.status = str(error.args[0] if error.args else error)
            return
        if owner_error:
            # Fontport's UnsupportedCapability for the glyph's own components:
            # own contours still show and stay editable (writes stage contours
            # only); with no edit_glyph peek nothing is shown or editable.
            suffix = "" if self.data is not None else "; own contours unreadable, editing disabled"
            self.status = f"Component unavailable: {owner_error}{suffix}"
            return
        unavailable = [f"{c.base} ({c.error})" for c in self.data.components if c.error]
        if unavailable:
            self.status = "Component unavailable: " + ", ".join(unavailable)

    def load(self, name: str | None, layer: str | None = None) -> None:
        """Show ``name`` (and ``layer`` when given): clear the selection and re-read."""
        self.name = name
        if layer is not None:
            self.layer = layer
        self.selection = set()
        self.read()

    def refresh(self) -> bool:
        """Re-read the same glyph; keep the selection while the point structure holds.

        Return True when the structure changed (and the selection was cleared).
        """
        before = signature(self.data)
        self.read()
        changed = signature(self.data) != before
        if changed:
            self.selection = set()
        return changed

    def fingerprint(self) -> str:
        """Digest of the font as this window shows it, read fresh (for ``Echo``)."""
        try:
            metrics = read_metrics(self.font)
            data = _read_shown(self.font, self.name, self.layer)[0] if self.name is not None else None
            return fingerprint(data, metrics)
        except Exception as error:
            return fingerprint(None, None, type(error).__name__)

    def select_at(self, sx: float, sy: float, extend: bool = False) -> tuple[int, int] | None:
        """Select the point under ``(sx, sy)``; ``extend`` toggles it. A miss clears unless extending."""
        hit = hit_point(self.data, self.view, sx, sy)
        if hit is None:
            if not extend:
                self.selection = set()
            return None
        if extend:
            self.selection ^= {hit}
        else:
            self.selection = {hit}
        return hit
