# this_file: src/fontlabapp/plugins/reporter.py
"""Pure mark protocol and guarded rendering through backend contexts."""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any, Literal

from fontlabapp.glyphs.identity import Identity

from .geometry import fill_points
from .plugin import Plugin
from .snapshot import Contour, GlyphSnapshot, KerningGroups, ViewState, first_report

Point = tuple[float, float]
Color = tuple[int, int, int]
Kind = Literal["ring", "line", "text", "polyline", "polygon"]

#: Most other glyphs one reporter may request per paint; the rest are dropped.
MAX_REQUESTED = 32


@dataclass(frozen=True)
class Mark:
    """Glyph-unit points with pixel-sized stroke, text and ring diameter."""

    kind: Kind
    points: tuple[Point, ...]
    color: Color = (220, 50, 45)
    stroke_px: float = 1.5
    text: str = ""
    text_px: int = 12
    diameter_px: float = 16.0
    fill: tuple[int, int, int, int] | None = None


def fill_mark(
    contours: tuple[Contour, ...], fill: tuple[int, int, int, int]
) -> Mark | None:
    """One odd-even RGBA polygon over ``contours``, or None if nothing fills."""
    points = fill_points(contours)
    return Mark("polygon", points, fill=fill) if len(points) >= 3 else None


def _view_point(context: Any, qt: Any, point: Point) -> Any:
    """Map glyph units through both native transforms into view pixels."""
    native = qt.QtCore.QPointF(*point)
    return context.canvas_to_view.map(context.glyph_to_canvas.map(native))


def _draw(mark: Mark, context: Any, qt: Any) -> None:
    """Draw one mark without changing the context's world transform."""
    painter = context.painter
    if mark.kind == "polygon" and len(mark.points) < 3:
        return
    points = tuple(_view_point(context, qt, p) for p in mark.points)
    if mark.kind == "polygon":
        if mark.fill is None:
            raise ValueError("Polygon mark needs an RGBA fill")
        painter.save()
        try:
            painter.setPen(qt.QtCore.Qt.NoPen)
            painter.setBrush(qt.QtGui.QColor(*mark.fill))
            painter.drawPolygon(qt.QtGui.QPolygonF(list(points)))
        finally:
            painter.restore()
        return
    pen = qt.QtGui.QPen(qt.QtGui.QColor(*mark.color))
    pen.setWidthF(mark.stroke_px)
    painter.setPen(pen)
    if mark.kind == "ring":
        painter.setBrush(qt.QtGui.QBrush())
        p, radius = points[0], mark.diameter_px / 2
        painter.drawEllipse(
            qt.QtCore.QRectF(p.x() - radius, p.y() - radius, radius * 2, radius * 2)
        )
    elif mark.kind == "text":
        font = qt.QtGui.QFont()
        font.setPixelSize(mark.text_px)
        painter.setFont(font)
        painter.drawText(points[0], mark.text)
    elif mark.kind in {"line", "polyline"}:
        for start, end in pairwise(points):
            painter.drawLine(start, end)
    else:
        raise ValueError(f"Unknown mark kind: {mark.kind}")


def render_marks(marks: list[Mark], context: Any, qt: Any) -> None:
    """Paint marks in view coordinates, preserving view-pixel widths."""
    for mark in marks:
        _draw(mark, context, qt)


class Reporter(Plugin):
    """Subclass with a name, title and pure ``compute(snapshot)`` method."""

    name = ""
    title = ""
    kind = "reporter"
    layer: Literal["foreground", "background"] = "foreground"
    needs_zones = False
    needs_bounds = False
    #: Opt-in data. Components and masters are read once per glyph revision
    #: for all reporters; background is read on every paint.
    needs_components = False
    needs_background = False
    needs_masters = False
    #: Kerning groups, read on every paint (class edits may not move the glyph
    #: stamp), and same-line neighbours with displayed kerning (view state).
    needs_kerning = False
    needs_neighbours = False
    #: Cursor in glyph units (view state). While any enabled reporter asks,
    #: the native backend watches the active canvas and repaints on moves.
    needs_mouse = False
    _capped = False  # set once the MAX_REQUESTED cap has been reported

    def compute(self, snapshot: GlyphSnapshot) -> list[Mark]:
        """Return marks for one glyph occurrence."""
        raise NotImplementedError

    def requested_glyphs(
        self, identity: Identity, kerning_groups: KerningGroups | None = None
    ) -> tuple[str, ...]:
        """Name other glyphs whose outlines ``snapshot.others`` should carry.

        Read from the same (owner) master, paint-safe, at most
        ``MAX_REQUESTED`` unique names. Asked only when identity was read.
        ``kerning_groups`` is the groups read this paint, None unless
        ``needs_kerning``. Every override takes it.
        """
        return ()

    def _requested(
        self,
        identity: Identity,
        report: Callable[[Exception], object],
        kerning_groups: KerningGroups | None = None,
    ) -> tuple[str, ...]:
        """Unique, capped glyph names; a bad request reports and asks for none."""
        try:
            raw = self.requested_glyphs(identity, kerning_groups)
            names = () if isinstance(raw, str) else tuple(dict.fromkeys(raw))
            if isinstance(raw, str) or not all(isinstance(n, str) for n in names):
                raise TypeError("requested_glyphs must return a tuple of glyph names")
        except Exception as error:  # noqa: BLE001 - reporter code must not block
            self._once(report, error)
            return ()
        if len(names) > MAX_REQUESTED:
            if not self._capped:
                self._capped = True
                report(
                    ValueError(
                        f"{self.name or type(self).__name__} requested "
                        f"{len(names)} glyphs; only the first {MAX_REQUESTED} are read"
                    )
                )
            names = names[:MAX_REQUESTED]
        return names

    def paint(
        self,
        context: Any,
        qt: Any,
        sink: Callable[[Exception, object], object],
        capture: Callable[[Any], GlyphSnapshot] | None = None,
    ) -> None:
        """Never allow capture, computation or Qt errors into paintEvent.

        Both backends' contexts carry scale (view pixels per glyph unit);
        it becomes snapshot.view after capture, keeping captured content
        independent of the view.
        """
        report = lambda error: self._report(sink, error)
        try:
            if context.layer is None:
                return
            if capture is None:
                from . import snapshot

                data = snapshot.capture(
                    context.layer,
                    include_zones=self.needs_zones,
                    include_bounds=self.needs_bounds,
                    include_components=self.needs_components,
                    include_background=self.needs_background,
                    include_masters=self.needs_masters,
                    include_kerning=self.needs_kerning,
                    requested=lambda identity, groups=None: self._requested(
                        identity, report, groups
                    ),
                    report=report,
                )
            else:
                data = capture(context.layer)
            scale = getattr(context, "scale", None)
            # Non-finite scale degrades to no view, as on the native backend.
            if scale is not None and math.isfinite(float(scale)):
                near = getattr(context, "neighbours", None)
                mouse = getattr(context, "mouse", None)
                view = ViewState(float(scale), mouse=mouse, neighbours=near)
                data = replace(data, view=view)
            render_marks(self.compute(data), context, qt)
        except Exception as error:  # noqa: BLE001 - Qt paint boundary must not raise
            self._once(report, error)

    def _once(self, report: Callable[[Exception], object], error: Exception) -> None:
        """Report reporter-code errors, which repeat each paint, only once.

        Keyed (reporter name, exception class) in the bounded backend lifetime.
        """
        name = self.name or type(self).__name__
        if first_report(("reporter", name, type(error))):
            report(error)

    def _report(
        self, sink: Callable[[Exception, object], object], error: Exception
    ) -> None:
        """Pass one error to the sink; even a failing sink must not unwind."""
        try:
            sink(error, self)
        except Exception:  # noqa: BLE001, S110 - even an error sink must not unwind
            pass

    def bind(
        self, painters: Any, qt: Any, sink: Callable[[Exception, object], object]
    ) -> int:
        """Register with the selected native or fallback painter backend."""
        return painters.register(self, qt, sink)
