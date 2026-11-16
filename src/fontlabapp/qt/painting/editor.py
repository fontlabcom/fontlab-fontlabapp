# this_file: src/fontlabapp/qt/painting/editor.py
"""Paint over FontLab's glyph editor: one overlay per visible glyph window.

What it does:
    ``EditorPainters`` lets a script register painter callbacks. FontLab calls
    each callback once per laid-out glyph, after the native glyph layer is
    painted. Each call gets a ``PaintContext`` with the glyph-to-canvas map,
    the canvas-to-view map and a ready ``QPainter``.

How to use:
    ``painters = EditorPainters(qt, fontlab, error_sink=sink)`` where ``qt`` is
    the ``PythonQt`` module and ``fontlab`` is the FontLab module.
    ``token = painters.register("after_native_layer", callback)`` starts the
    work. ``painters.remove(token)`` stops one painter. ``painters.close()``
    stops all of them. After the last painter is gone, the poll timer stops and
    every overlay is detached.
    ``layer_filter`` is ``"active"`` (default), ``"inactive"`` or ``"all"``.
    ``document_id`` limits a painter to one font (``package.id``).
    Inside the callback, draw with ``context.painter`` and map glyph units to
    pixels with ``context.glyph_to_canvas`` then ``context.canvas_to_view``.

Native facts (FontLab 9.0.9780, measured by Glyport; evidence
``glyport-ui/probe-editor-paint.json``):
    - The native canvas paints the viewport from an event filter and fills it
      opaquely. A Python pre-paint leaves no visible pixel. Only painting
      after the native layer works, so ``before_native_layer`` raises
      ``ValueError`` here.
    - A transparent child widget of the viewport paints after the native
      canvas. This module uses one such child per viewport.
    - A glyph unit maps to a pixel as the native glyph paint does: glyph
      transform, then text-block transform, to canvas units, then
      ``flCanvas.mapToViewportF`` to pixels. Kerning is already in the glyph
      transform.

Why this design:
    - New glyph windows appear at any time. A 250 ms poll finds them. Hidden
      (closed) tabs stay alive, so only visible windows get an overlay.
    - Callback errors go to ``error_sink``. Nothing raises out of
      ``paintEvent``: an exception there, with a QPainter active, crashes
      FontLab (AGENTS.md landmines).
    - The painter is saved and restored around every callback. One plugin
      cannot leak pen, brush or transform state into the next.
    - Teardown disconnects each signal before ``deleteLater``. A widget deleted
      with live Python slot targets crashes FontLab (double delete in
      ``PythonQtSignalReceiver``).
    - Maths come from ``fontlabapp.contours.affine``. Native widget lists come through
      ``fontlabapp.qt.safe.qt_list`` (GC off during conversion).

Compare ``fontlabapp.qt.painting.drawing.Drawing``: that class paints one given widget.
This module is a registry over all glyph windows.
Glyport's ``fontlab_glyport.drawing.editor`` subclasses it. The subclass adds
the Glyphs ``UnsupportedCapability`` refusal for the before-native phase and
the ``layer_resolver`` wiring.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import count
from typing import Any, NamedTuple

# Absolute "import package.module" on purpose. "from fontlabapp import affine"
# (or "from . import affine") first reads the attribute on the package. That
# lookup reaches fontlabapp.__getattr__, whose native fallback raises
# RuntimeError outside FontLab and probes the native modules inside it.
import fontlabapp.contours.affine as affine  # noqa: PLR0402 - see the comment above
import fontlabapp.qt.safe as qtsafe  # noqa: PLR0402 - see the comment above

__all__ = [
    "AFTER_NATIVE_LAYER",
    "BEFORE_NATIVE_LAYER",
    "GLYPH_WINDOW_CLASS",
    "LAYER_FILTERS",
    "POLL_MS",
    "EditorPainters",
    "ErrorSink",
    "OverlayEntry",
    "PaintContext",
    "PainterEntry",
]

#: Phase name that ``register`` refuses: the native canvas paints over it.
BEFORE_NATIVE_LAYER = "before_native_layer"
#: The one supported phase: paint after the native glyph layer.
AFTER_NATIVE_LAYER = "after_native_layer"
#: Values for ``register(layer_filter=...)``.
LAYER_FILTERS = ("active", "inactive", "all")
#: How often, in milliseconds, to look for new glyph windows.
POLL_MS = 250
#: ``className()`` of a FontLab glyph window.
GLYPH_WINDOW_CLASS = "GlyphWindow"

#: ``error_sink(exception, source)``: receives every callback, poll and paint failure.
ErrorSink = Callable[[Exception, object], object]


class PainterEntry(NamedTuple):
    """One registered painter, as stored in ``EditorPainters.painters``."""

    callback: Callable[["PaintContext"], object]
    layer_filter: str
    document_id: Any


class OverlayEntry(NamedTuple):
    """One attached overlay, as stored in ``EditorPainters.overlays``.

    ``destroyed`` is the slot connected to ``viewport.destroyed``; teardown
    disconnects it before ``deleteLater``. Tuple indexing still works.
    """

    overlay: Any
    viewport: Any
    canvas: Any
    destroyed: Callable[..., None]


@dataclass(frozen=True)
class PaintContext:
    """One painter call for one laid-out glyph item.

    ``painter`` is valid only during the callback. Do not keep it.
    ``scale`` is view pixels per glyph unit. ``layer`` is whatever the
    optional ``layer_resolver`` returned for this glyph item, else ``None``.
    """

    document_id: Any
    layer_id: Any
    glyph_item_id: Any
    is_active_layer: bool
    phase: str
    glyph_to_canvas: Any  # QTransform: glyph units -> canvas units
    canvas_to_view: Any  # QTransform: canvas units -> widget pixels
    device_pixel_ratio: float
    clip: Any  # QRect in widget pixels
    painter: Any  # QPainter, valid only during the callback
    scale: float
    layer: Any = None


def _overlay_class(base: type, resize_type: Any) -> type:
    """Build the transparent overlay widget class on the Qt ``base`` class.

    The class is made at run time because ``base`` (``QtGui.QWidget``) exists
    only inside FontLab. The overlay paints through its owner, follows the
    viewport size, and ignores everything once the owner is cleared.
    """

    class Overlay(base):  # type: ignore[misc, valid-type]
        _owner: "EditorPainters | None" = None

        def paintEvent(self, event: Any) -> None:
            owner = self._owner
            if owner is not None:
                owner._paint(self, event)

        def eventFilter(self, watched: Any, event: Any) -> bool:
            if self._owner is not None and event.type() == resize_type:
                self.setGeometry(watched.rect)
            return False

    return Overlay


class EditorPainters:
    """Register glyph-editor painters with FontLab (one overlay per viewport).

    Attributes:
        painters: ``token -> PainterEntry`` for every registered painter.
        overlays: ``id(viewport) -> OverlayEntry`` for every attached overlay.
        layer_resolver: the optional ``layer_resolver`` callable.
    Read them; do not change them. Use ``register``/``remove``/``close``.
    """

    def __init__(
        self,
        qt: Any,
        fontlab: Any,
        *,
        error_sink: ErrorSink,
        layer_resolver: Callable[[Any], Any] | None = None,
    ) -> None:
        """Store the Qt and FontLab modules; start nothing.

        ``error_sink(exception, source)`` receives every callback, poll and
        paint failure. ``layer_resolver(glyph_info)`` may map a native glyph
        item to a script-side layer object for ``PaintContext.layer``.
        """
        self.qt, self.fl, self.sink = qt, fontlab, error_sink
        self.layer_resolver = layer_resolver
        self.painters: dict[int, PainterEntry] = {}
        self.overlays: dict[int, OverlayEntry] = {}
        self._ids = count(1)
        self._timer: Any = None
        # Timers whose teardown failed part-way. Each may still hold a live
        # slot, so it is stopped but never deleted, and this list keeps the
        # Python wrapper alive (no collector delete with a connected slot).
        self._kept_timers: list[Any] = []
        self._overlay_class: type | None = None

    # --- registration -------------------------------------------------------
    def register(
        self,
        phase: str,
        callback: Callable[[PaintContext], object],
        layer_filter: str = "active",
        *,
        document_id: Any = None,
    ) -> int:
        """Add a painter. Return its token for ``remove``.

        Only ``"after_native_layer"`` works. Any other phase, including
        ``"before_native_layer"``, and any unknown filter raise ``ValueError``.
        ``document_id`` limits the painter to one font.
        """
        if phase != AFTER_NATIVE_LAYER or layer_filter not in LAYER_FILTERS:
            raise ValueError(
                f"bad painter phase/filter: {phase!r}, {layer_filter!r}; "
                f"only {AFTER_NATIVE_LAYER!r} is supported "
                "(the native canvas paints opaquely after any earlier Python paint)"
            )
        token = next(self._ids)
        self.painters[token] = PainterEntry(callback, layer_filter, document_id)
        self._start()
        self._update_all()
        return token

    def remove(self, token: int) -> None:
        """Drop one painter. Unknown tokens are ignored.

        When the last painter goes, stop polling and detach every overlay.
        """
        if self.painters.pop(token, None) is None:
            return
        if self.painters:
            self._update_all()
        else:
            self._stop()

    def close(self) -> None:
        """Drop every painter, stop polling and detach every overlay."""
        self.painters.clear()
        self._stop()

    def _stop(self) -> None:
        """Stop the timer, then detach overlays (disconnect before delete).

        Try the timer and every overlay. A timer failure does not skip the
        overlays. Re-raise the first failure after all were tried.
        """
        failures: list[Exception] = []
        try:
            self._stop_timer()
        except Exception as error:  # noqa: BLE001 - re-raised below
            failures.append(error)
        for key in list(self.overlays):
            try:
                self._detach(key)
            except Exception as error:  # noqa: BLE001 - re-raised below
                failures.append(error)
        if failures:
            raise failures[0]

    def _stop_timer(self) -> None:
        """Stop, disconnect, then ``deleteLater`` the poll timer.

        On a failure, keep the timer in ``_kept_timers`` and do not delete it:
        its slot may still be connected (PythonQtSignalReceiver crash rule).
        A later ``register`` makes a fresh timer.
        """
        timer, self._timer = self._timer, None
        if timer is None:
            return
        try:
            timer.stop()
            timer.timeout.disconnect(self._attach_all)
            timer.deleteLater()
        except Exception:
            self._kept_timers.append(timer)
            raise

    # --- overlays -----------------------------------------------------------
    def _start(self) -> None:
        """Start the poll timer once, then look for windows at once."""
        if self._timer is None:
            timer = self.qt.QtCore.QTimer()
            timer.setInterval(POLL_MS)
            timer.timeout.connect(self._attach_all)
            timer.start()
            self._timer = timer
        self._attach_all()

    def _viewports(self) -> list[tuple[Any, Any]]:
        """Return ``(canvas, viewport)`` for each visible glyph window."""
        workspace = self.fl.flWorkspace.instance()
        gui = self.qt.QtGui
        found = []
        for widget in qtsafe.qt_list(gui.QApplication.allWidgets):
            if widget.className() != GLYPH_WINDOW_CLASS or not widget.isVisible():
                continue  # closed tabs stay alive hidden; attach when shown
            children = qtsafe.qt_list(widget.findChildren, gui.QWidget)
            for child in [widget, *children]:
                canvas = workspace.getCanvasForViewport(child)
                if canvas is not None:
                    found.append((canvas, child))
                    break
        return found

    def _attach_all(self) -> None:
        """Timer slot: attach an overlay to each new viewport. Never raises.

        With no painter left (after ``close``/last ``remove``) do nothing: a
        kept timer whose ``stop()`` failed can still fire this slot.
        """
        if not self.painters:
            return
        try:
            for canvas, viewport in self._viewports():
                if id(viewport) not in self.overlays:
                    self._attach(canvas, viewport)
        except Exception as exc:  # noqa: BLE001 - timer slot: never raise into Qt
            try:
                self.sink(exc, self)
            except Exception:  # noqa: BLE001, S110 - a failing sink must not escape either
                pass

    def _attach(self, canvas: Any, viewport: Any) -> None:
        """Add the transparent overlay child to one viewport."""
        qt = self.qt
        if self._overlay_class is None:
            self._overlay_class = _overlay_class(
                qt.QtGui.QWidget, qt.QtCore.QEvent.Resize
            )
        overlay = self._overlay_class(viewport)
        overlay._owner = self
        overlay.setAttribute(qt.QtCore.Qt.WA_TransparentForMouseEvents, True)
        overlay.setAttribute(qt.QtCore.Qt.WA_NoSystemBackground, True)
        overlay.setGeometry(viewport.rect)
        viewport.installEventFilter(overlay)
        key = id(viewport)

        def destroyed(*args: Any) -> None:  # window closed: Qt deletes the child too
            self.overlays.pop(key, None)

        viewport.destroyed.connect(destroyed)
        self.overlays[key] = OverlayEntry(overlay, viewport, canvas, destroyed)
        overlay.show()
        overlay.raise_()

    def _detach(self, key: int) -> None:
        """Remove one overlay. Disconnect first, then ``deleteLater``."""
        overlay, viewport, _, destroyed = self.overlays.pop(key)
        overlay._owner = None
        viewport.removeEventFilter(overlay)
        viewport.destroyed.disconnect(destroyed)
        overlay.hide()
        overlay.setParent(None)
        overlay.deleteLater()

    def _update_all(self) -> None:
        """Ask every overlay to repaint (``QWidget.update``, queued by Qt).

        Called after the painter set changes, so the change shows at once
        instead of at the next native repaint.
        """
        for entry in self.overlays.values():
            entry.overlay.update()

    # --- painting -----------------------------------------------------------
    def _paint(self, overlay: Any, event: Any) -> None:
        """Run all painters for one overlay. Never raises into ``paintEvent``.

        A failure in ``painter.end()`` also goes to the sink, after the error
        that came first, so neither hides the other.
        """
        entry = next((e for e in self.overlays.values() if e.overlay is overlay), None)
        if entry is None or not self.painters:
            return
        painter = None
        try:
            painter = self.qt.QtGui.QPainter(overlay)
            for context in self._contexts(entry.canvas, entry.viewport, painter, event):
                self._dispatch(context)
        except Exception as exc:  # noqa: BLE001 - never raise into paintEvent
            self.sink(exc, self)
        finally:
            if painter is not None:
                try:
                    painter.end()
                except Exception as exc:  # noqa: BLE001 - never raise into paintEvent
                    self.sink(exc, self)

    def _contexts(
        self, canvas: Any, viewport: Any, painter: Any, event: Any
    ) -> Iterator[PaintContext]:
        """Yield one ``PaintContext`` per laid-out glyph of ``canvas``.

        Read the canvas map fresh at each paint: pan and zoom change it.
        """
        gui = self.qt.QtGui
        to_view = affine.viewport_transform(canvas, self.qt.QtCore.QPointF)
        clip = event.rect() if event is not None else viewport.rect
        ratio = viewport.devicePixelRatioF()
        for block in canvas.textBlocks():
            block_tx = affine.from_qtransform(block.transform)
            package = getattr(block, "package", None)
            for info in block.getAllGlyphs() or ():
                glyph_tx = affine.concat(
                    affine.from_qtransform(info.transform), block_tx
                )
                full = affine.concat(glyph_tx, to_view)
                scale = (full[0] ** 2 + full[1] ** 2) ** 0.5
                layer = self.layer_resolver(info) if self.layer_resolver else None
                yield PaintContext(
                    document_id=getattr(package, "id", None),
                    layer_id=None,
                    glyph_item_id=getattr(info, "id", None),
                    is_active_layer=bool(info.isActive),
                    phase=AFTER_NATIVE_LAYER,
                    glyph_to_canvas=gui.QTransform(*glyph_tx),
                    canvas_to_view=gui.QTransform(*to_view),
                    device_pixel_ratio=ratio,
                    clip=clip,
                    painter=painter,
                    scale=scale,
                    layer=layer,
                )

    def _dispatch(self, context: PaintContext) -> None:
        """Call each matching painter inside a painter save/restore pair."""
        wanted = "active" if context.is_active_layer else "inactive"
        for entry in list(self.painters.values()):
            if entry.layer_filter not in (wanted, "all"):
                continue
            if entry.document_id is not None and entry.document_id != context.document_id:
                continue
            context.painter.save()
            try:
                entry.callback(context)
            except Exception as exc:  # noqa: BLE001 - plugin failure is data
                self.sink(exc, entry.callback)
            finally:
                context.painter.restore()
