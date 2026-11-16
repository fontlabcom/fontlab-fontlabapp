# this_file: src/fontlabapp/plugins/backend.py
"""Native per-canvas painters with an EditorPainters fallback for old builds.

FontLab's text-block item applies its own transform before drawing a glyph
item (`fltextblockitem.cpp`). `EditorPainters` applies the glyph-item and block
transforms in that order. This backend does the same, then uses the native
`canvas.mapToViewportF` map for final viewport coordinates. The HT Letterspacer
consumer uses the glyph transform alone; that suffices only when the block's
transform is identity.

While an enabled reporter has ``needs_mouse``, one event filter watches the
active canvas viewport. A mouse or hover move starts a single-shot
``REPAINT_MS`` timer unless one is pending; its timeout calls
``canvas.updateScreenRect`` over the whole viewport (viewport pixels), then
``canvas.updateViewport()``: the first only adds the rect to FontLab's pending
update region, and only the second repaints it. Flushes are thus at most one
per window and always trail the last move, and the paint reads
``canvas.mousePosition()`` after FontLab has stored it. That moves reach a
viewport filter under every tool is unverified natively.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from itertools import count
from typing import Any

from fontlabapp.qt.painting.view import glyph_point, neighbours, px_per_unit

from . import snapshot
from .reporter import Reporter
from .snapshot import NativeSource, Neighbours, resolve_source

POLL_MS = 250
#: Shortest gap between mouse-driven repaints (about one 60 Hz frame).
REPAINT_MS = 16


@dataclass
class _CanvasEntry:
    """Keep a live canvas and its native tokens together."""

    identifier: int
    canvas: Any
    tokens: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class _GlyphMap:
    """Apply the glyph-item position, then its text-block transform."""

    glyph: Any
    block: Any

    def map(self, point: Any) -> Any:
        """Map one layer point into canvas coordinates."""
        return self.block.map(self.glyph.map(point))


@dataclass(frozen=True)
class _CanvasMap:
    """Expose FontLab's canvas-to-viewport map as ``map``."""

    canvas: Any

    def map(self, point: Any) -> Any:
        """Map a canvas point into viewport pixels."""
        return self.canvas.mapToViewportF(point)


@dataclass(frozen=True)
class _PaintContext:
    """The renderer's small context for one native glyph occurrence."""

    painter: Any
    layer: NativeSource
    glyph_to_canvas: _GlyphMap
    canvas_to_view: _CanvasMap
    scale: float | None = None  # view pixels per glyph unit, as in EditorPainters
    neighbours: Neighbours | None = None  # only for needs_neighbours reporters
    mouse: tuple[float, float] | None = None  # glyph units; needs_mouse only


@dataclass(frozen=True)
class _MouseWatch:
    """One installed viewport filter; the canvas id is read at install."""

    canvas: Any
    canvas_id: int
    viewport: Any
    filter: Any


def _mouse_filter_class(base: type, moves: tuple[Any, ...]) -> type:
    """Build the viewport mouse filter on the Qt ``base`` (``QtGui.QWidget``).

    Made at run time because the base exists only inside FontLab; ``QObject``
    is only in ``PythonQt.private`` (b: ``EditorPainters`` overlay filter).
    The filter never consumes an event and never raises.
    """

    class MouseFilter(base):  # type: ignore[misc, valid-type]
        _owner: "NativeCanvasBackend | None" = None

        def eventFilter(self, watched: Any, event: Any) -> bool:
            try:
                owner = self._owner
                if owner is not None and event.type() in moves:
                    owner._moved()
            except Exception as error:  # noqa: BLE001 - Qt event boundary
                try:
                    self._owner._mouse_failed("mouse_filter", error)  # type: ignore[union-attr]
                except Exception:  # noqa: BLE001, S110 - never raise into Qt
                    pass
            return False

    return MouseFilter


def active_glyph_map(canvas: Any, items: Any = None) -> _GlyphMap | None:
    """Find the active glyph occurrence, including later text-line positions."""
    if canvas is None or canvas.isNull:
        return None
    items = items or import_module("fontlabapp.qt.safe").qt_list
    for block in items(canvas.textBlocks):
        for info in items(lambda block=block: block.getAllGlyphs() or ()):
            if info.isActive:
                return _GlyphMap(info.transform, block.transform)
    return None


class NativeCanvasBackend:
    """Attach every enabled reporter to every active canvas encountered."""

    def __init__(
        self,
        qt: Any,
        fontlab: Any,
        sink: Callable[[Exception, object], object],
        *,
        items: Callable[[Callable[[], Any]], list[Any]] | None = None,
    ) -> None:
        self.qt, self.fl, self.sink = qt, fontlab, sink
        self.items = items or import_module("fontlabapp.qt.safe").qt_list
        self.canvases: dict[int, _CanvasEntry] = {}
        self._failed_canvas_ids: dict[int, str] = {}
        self._view_failed: set[tuple[str, int]] = set()
        self._reporters: dict[int, Reporter] = {}
        self._ids = count(1)
        self._timer: Any = None
        self._timer_slot: Callable[[], None] | None = None
        self._kept_timers: list[Any] = []
        self._watch: _MouseWatch | None = None
        self._repaint: Any = None  # single-shot mouse repaint timer
        self._repaint_slot: Callable[[], None] | None = None
        self._filter_class: type | None = None
        self._kept_filters: list[Any] = []  # filters whose teardown failed

    def register(self, reporter: Reporter, qt: Any, sink: Any) -> int:
        """Retain a reporter and attach it to all known live canvases."""
        token = next(self._ids)
        self._reporters[token] = reporter
        try:
            if self._timer is None:
                self._start_timer()
        except Exception:
            self._reporters.pop(token)
            raise
        self._poll()
        if token not in self._reporters:
            return token
        for entry in tuple(self.canvases.values()):
            self._attach(entry, token)
        return token

    def remove(self, token: int) -> None:
        """Remove a reporter's native token from each surviving canvas."""
        if self._reporters.pop(token, None) is None:
            return
        for entry in tuple(self.canvases.values()):
            native = entry.tokens.pop(token, None)
            if native is None:
                continue
            try:
                if bool(entry.canvas.isNull):
                    continue  # FontLab already dropped the painter with its canvas
                entry.canvas.removePythonPainter(native)
            except Exception as error:  # noqa: BLE001 - stale native wrapper
                self._report(error, self)
        if self._watch is not None and not self._mouse_wanted():
            self._unwatch()
        if not self._reporters:
            self._stop_timer()
            self.canvases.clear()

    def close(self) -> None:
        """Drop every painter and stop polling; safe to call twice."""
        try:
            for token in tuple(self._reporters):
                self.remove(token)
        finally:
            self._reporters.clear()
            self._unwatch()
            if self._timer is not None:
                self._stop_timer()
            self.canvases.clear()
            self._failed_canvas_ids.clear()
            self._view_failed.clear()
            snapshot.reset()

    def _start_timer(self) -> None:
        """Poll new active canvases while any reporter is enabled."""
        timer = self.qt.QtCore.QTimer()
        timer.setInterval(POLL_MS)
        slot = lambda: self._poll() if self._timer is timer else None
        timer.timeout.connect(slot)
        timer.start()
        self._timer = timer
        self._timer_slot = slot

    def _stop_timer(self) -> None:
        """Stop the poll timer."""
        timer, self._timer = self._timer, None
        slot, self._timer_slot = self._timer_slot, None
        self._drop_timer(timer, slot)

    def _drop_timer(self, timer: Any, slot: Callable[[], None] | None) -> None:
        """Disconnect before deletion, retaining failed teardown wrappers."""
        if timer is None:
            return
        assert slot is not None, "An owned timer must have its exact connected slot."
        try:
            timer.stop()
            timer.timeout.disconnect(slot)
            timer.deleteLater()
        except Exception as error:  # noqa: BLE001 - Qt teardown boundary
            self._kept_timers.append(timer)
            self._report(error, self)

    def _mouse_wanted(self) -> bool:
        """True while any enabled reporter asks for the mouse."""
        return any(reporter.needs_mouse for reporter in self._reporters.values())

    def _sync_mouse(self, canvas: Any) -> None:
        """Watch the active ``canvas`` (None: no canvas) while the mouse is wanted."""
        if canvas is None or not self._mouse_wanted():
            self._unwatch()
            return
        timer = self._timer
        identifier = int(canvas.id)
        if self._timer is not timer or not self._mouse_wanted():
            return
        if self._watch is not None and self._watch.canvas_id == identifier:
            return
        self._unwatch()
        if (
            self._timer is not timer
            or self._watch is not None
            or not self._mouse_wanted()
        ):
            return
        self._install_watch(canvas, identifier)

    def _install_watch(self, canvas: Any, identifier: int) -> None:
        """Filter one viewport; a refused canvas is reported once, not retried."""
        if ("mouse_watch", identifier) in self._view_failed:
            return
        timer, watch = self._timer, self._watch
        item = None
        try:
            viewport = canvas.viewPort
            if (
                self._timer is not timer
                or self._watch is not watch
                or not self._mouse_wanted()
            ):
                return
            if self._filter_class is None:
                event = self.qt.QtCore.QEvent
                self._filter_class = _mouse_filter_class(
                    self.qt.QtGui.QWidget, (event.MouseMove, event.HoverMove)
                )
            item = self._filter_class()
            item._owner = self
            viewport.installEventFilter(item)
        except Exception as error:  # noqa: BLE001 - optional mouse support
            if item is not None:
                item._owner = None
                self._kept_filters.append(item)
            if (
                self._timer is timer
                and self._watch is watch
                and self._mouse_wanted()
            ):
                self._once(("mouse_watch", identifier), error, self)
            return
        if (
            self._timer is timer
            and self._watch is watch
            and self._mouse_wanted()
        ):
            self._watch = _MouseWatch(canvas, identifier, viewport, item)
            return
        item._owner = None
        try:
            if not bool(canvas.isNull):
                viewport.removeEventFilter(item)
            item.deleteLater()
        except Exception as error:  # noqa: BLE001 - stale native wrapper
            self._kept_filters.append(item)
            self._report(error, self)

    def _unwatch(self) -> None:
        """Remove the viewport filter and repaint timer; keep failed wrappers."""
        watch, self._watch = self._watch, None
        timer, self._repaint = self._repaint, None
        slot, self._repaint_slot = self._repaint_slot, None
        if watch is not None:
            watch.filter._owner = None
        self._drop_timer(timer, slot)
        if watch is None:
            return
        try:
            if not bool(watch.canvas.isNull):  # a closed canvas took its viewport
                watch.viewport.removeEventFilter(watch.filter)
            watch.filter.deleteLater()
        except Exception as error:  # noqa: BLE001 - stale native wrapper
            self._kept_filters.append(watch.filter)
            self._report(error, self)

    def _moved(self) -> None:
        """Filter slot: schedule one trailing repaint unless one is pending."""
        timer = self._repaint
        if timer is None:
            timer = self.qt.QtCore.QTimer()
            timer.setSingleShot(True)
            timer.setInterval(REPAINT_MS)
            slot = lambda: self._flush() if self._repaint is timer else None
            timer.timeout.connect(slot)
            self._repaint = timer
            self._repaint_slot = slot
        if not timer.isActive():
            timer.start()

    def _flush(self) -> None:
        """Timer slot: repaint the watched viewport once. Never raises."""
        watch = self._watch
        if watch is None:
            return
        try:
            gone = bool(watch.canvas.isNull)
            if self._watch is not watch or gone:
                return
            rect = self.qt.QtCore.QRectF(watch.viewport.rect)
            if self._watch is not watch:
                return
            watch.canvas.updateScreenRect(rect)
            if self._watch is not watch:
                return
            watch.canvas.updateViewport()  # updateScreenRect only marks it dirty
        except Exception as error:  # noqa: BLE001 - Qt timer boundary
            if self._watch is watch:
                self._mouse_failed("mouse_flush", error)

    def _mouse_failed(self, kind: str, error: Exception) -> None:
        """Report a filter or flush failure once per kind and watched canvas."""
        watch = self._watch
        self._once((kind, watch.canvas_id if watch else 0), error, self)

    def _report(self, error: Exception, source: object) -> None:
        """An error sink must never unwind through native paint or Qt timers."""
        try:
            self.sink(error, source)
        except Exception:  # noqa: BLE001, S110 - native callback boundary
            pass

    def _poll(self) -> None:
        """Observe active canvases and forget wrappers destroyed by FontLab."""
        if not self._reporters:
            return
        timer = self._timer
        try:
            for identifier, entry in tuple(self.canvases.items()):
                try:
                    gone = bool(entry.canvas.isNull)
                except Exception as error:  # noqa: BLE001 - stale native wrapper
                    self._report(error, self)
                    gone = True
                if self._timer is not timer:
                    return
                if gone:
                    del self.canvases[identifier]
            canvas = self.fl.flWorkspace.instance().getActiveCanvas()
            if self._timer is not timer:
                return
            gone = canvas is None or bool(canvas.isNull)
            if self._timer is not timer:
                return
            if gone:
                self._sync_mouse(None)
                return
            self._sync_mouse(canvas)
            if self._timer is not timer:
                return
            identifier = int(canvas.id)
            if self._timer is not timer:
                return
            entry = self.canvases.setdefault(
                identifier, _CanvasEntry(identifier, canvas)
            )
            for token in tuple(self._reporters):
                self._attach(entry, token)
        except Exception as error:  # noqa: BLE001 - Qt timer boundary
            self._report(error, self)

    def _attach(self, entry: _CanvasEntry, token: int) -> None:
        """Register one callback at the reporter's requested native order."""
        if (
            token not in self._reporters
            or self.canvases.get(entry.identifier) is not entry
            or token in entry.tokens
            or entry.identifier in self._failed_canvas_ids
        ):
            return
        timer = self._timer
        reporter = self._reporters[token]
        callback = lambda painter, canvas: self._paint(token, reporter, painter, canvas)
        try:
            order = (
                entry.canvas.UnderOwner
                if reporter.layer == "background"
                else entry.canvas.OverOwner
            )
            if (
                self._timer is not timer
                or token not in self._reporters
                or self.canvases.get(entry.identifier) is not entry
            ):
                return
            native = entry.canvas.appendPythonPainter(callback, order)
        except Exception as error:  # noqa: BLE001 - native registration boundary
            if (
                self._timer is timer
                and token in self._reporters
                and self.canvases.get(entry.identifier) is entry
            ):
                self._failed_canvas_ids[entry.identifier] = str(error)
                self._report(error, reporter)
            return
        if (
            self._timer is timer
            and token in self._reporters
            and self.canvases.get(entry.identifier) is entry
        ):
            entry.tokens[token] = native
            return
        try:
            if native is not None and not bool(entry.canvas.isNull):
                entry.canvas.removePythonPainter(native)
        except Exception as error:  # noqa: BLE001 - stale native wrapper
            self._report(error, self)

    def _view_error(
        self, kind: str, canvas: Any, error: Exception, reporter: Reporter
    ) -> None:
        """Report a view-data failure once per (datum, canvas) until close()."""
        self._once((kind, int(canvas.id)), error, reporter)

    def _once(self, key: tuple[str, int], error: Exception, source: object) -> None:
        """Report ``error`` for ``key`` once until close()."""
        if key not in self._view_failed:
            self._view_failed.add(key)
            self._report(error, source)

    def _near(
        self,
        block: Any,
        position: int,
        info: Any,
        found: dict[int, list[int]],
        report: Callable[[Exception], object],
    ) -> Neighbours:
        """Same-line neighbours of the block's ``position``-th active glyph.

        ``getAllGlyphs`` list positions are not paragraph indices: it skips
        unplaced glyphs (``lineIndex < 0``, a-src ``fltextblock.cpp``). So the
        block's paragraph is scanned once with ``getGlyphAt`` (b:
        ``snapshot.active_glyph``) under the same filter, and the k-th active
        entries of both scans are paired (c). A failing side is None and goes
        to ``report``.
        """
        if id(block) not in found:
            found[id(block)] = [
                index
                for index in range(int(block.glyphsCount()))
                if (slot := block.getGlyphAt(index)) is not None
                and slot.isActive
                and int(block.getLineIndex(index)) >= 0
            ]
        indexes = found[id(block)]
        if position >= len(indexes):
            raise ValueError("Active glyph has no paragraph index for neighbours.")
        return Neighbours(*neighbours(block, indexes[position], info, report))

    def _paint(self, token: int, reporter: Reporter, painter: Any, canvas: Any) -> None:
        """Draw every active glyph occurrence in viewport coordinates; never raise."""
        if token not in self._reporters:
            return
        found: dict[int, list[int]] = {}
        try:
            point = None  # canvas-unit cursor, only on the watched canvas
            watch = self._watch
            if reporter.needs_mouse and watch and watch.canvas_id == int(canvas.id):
                try:
                    point = canvas.mousePosition()
                except Exception as error:  # noqa: BLE001 - view is optional
                    self._view_error("mouse", canvas, error, reporter)
            for block in self.items(canvas.textBlocks):
                glyphs = self.items(lambda block=block: block.getAllGlyphs() or ())
                actives = [info for info in glyphs if info.isActive]
                for position, info in enumerate(actives):
                    source = resolve_source(info)
                    if source is None:
                        continue
                    to_canvas = _GlyphMap(info.transform, block.transform)
                    to_view = _CanvasMap(canvas)
                    try:
                        scale = px_per_unit(
                            lambda p: to_view.map(to_canvas.map(p)),
                            self.qt.QtCore.QPointF,
                        )
                    except Exception as error:  # noqa: BLE001 - view is optional
                        self._view_error("scale", canvas, error, reporter)
                        scale = None
                    near = None
                    if reporter.needs_neighbours:

                        def failed(error: Exception) -> None:
                            self._view_error("neighbours", canvas, error, reporter)

                        try:
                            near = self._near(block, position, info, found, failed)
                        except Exception as error:  # noqa: BLE001 - view is optional
                            failed(error)
                    mouse = None
                    if point is not None and scale is not None:
                        try:
                            mouse = glyph_point(info.transform, block.transform, point)
                        except Exception as error:  # noqa: BLE001 - view is optional
                            self._view_error("mouse", canvas, error, reporter)
                    context = _PaintContext(
                        painter, source, to_canvas, to_view, scale, near, mouse
                    )
                    reporter.paint(context, self.qt, self.sink)
        except Exception as error:  # noqa: BLE001 - native paint boundary
            self._report(error, reporter)


class EditorBackend:
    """Use App's transparent viewport overlay on builds without native hooks."""

    def __init__(
        self, painters: Any, sink: Callable[[Exception, object], object]
    ) -> None:
        self.painters, self.sink = painters, sink
        self._warned = False

    def register(self, reporter: Reporter, qt: Any, sink: Any) -> int:
        """Draw after native glyphs; announce background substitution once."""
        if reporter.layer == "background" and not self._warned:
            self._warned = True
            self.sink(
                RuntimeError(
                    "Background reporters draw over the canvas on this FontLab build"
                ),
                self,
            )
        return self.painters.register(
            "after_native_layer",
            lambda context: reporter.paint(context, qt, sink),
            layer_filter="active",
        )

    def remove(self, token: int) -> None:
        """Remove one App painter token."""
        self.painters.remove(token)

    def close(self) -> None:
        """Close App's viewport overlay owner."""
        try:
            self.painters.close()
        finally:
            snapshot.reset()


def select_backend(
    qt: Any,
    fontlab: Any,
    sink: Callable[[Exception, object], object],
    *,
    editor_factory: Any = None,
    items: Callable[[Callable[[], Any]], list[Any]] | None = None,
) -> NativeCanvasBackend | EditorBackend:
    """Choose native hooks once; import EditorPainters only for older builds."""
    if hasattr(getattr(fontlab, "flCanvas", None), "appendPythonPainter"):
        return NativeCanvasBackend(qt, fontlab, sink, items=items)
    factory = (
        editor_factory or import_module("fontlabapp.qt.painting.editor").EditorPainters
    )
    painters = factory(qt, fontlab, error_sink=sink, layer_resolver=resolve_source)
    return EditorBackend(painters, sink)
