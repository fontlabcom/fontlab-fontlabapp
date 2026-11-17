# this_file: src/fontlabapp/fontui/tglyph.py
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: BLE001 -- Qt callbacks must contain backend exceptions.
"""TGlyph: a single-glyph view that follows FontLab.

What: one glyph of a font on an explicit layer (the layer selector lists the
font's layers/masters and starts on the default layer). The glyph name field
completes existing names; Prev/Next step through the glyph order. The canvas
draws the filled outline, on-curve points (squares; circles when smooth) and
off-curve points (small circles) with handle lines, a start point marker,
components (drawn, not editable), named anchors, the baseline, the advance box
and the vertical metric lines. Zoom with the wheel, ``+``/``-`` or Fit (``0``);
pan with space-drag or a middle-button drag; click a point to select it
(Shift adds or removes) or drag a rubber band. Editing: drag selected points
(the handles of a moved on-curve point follow), nudge with the arrows (Shift:
10 units), Delete removes points, and the pen tool (``P``; ``V`` returns to
select) adds line points to a new open contour, closes it on its first point
and ends with Escape. Each gesture writes once, on release or on the key,
through ``fontlabapp.fontui.tglyph_edit.Editor`` to the shown layer only; a
drag only previews until release, and a failed write reverts with its reason
in the status line. FontLab edits and Undo/Redo refresh within the follow delay,
keeping zoom, pan and selection while the point structure stays the same.
"Follow FontLab current glyph" switches to the glyph FontLab shows when it
changes (names absent from this font are ignored). Refreshes go through
``fontlabapp.fontui.livesync.Echo`` so the window's own writes can be skipped.
Use: ``show_tglyph()`` for FontLab's current font and glyph, or
``TGlyph(font, name, layer)`` over any FontParts-style font.
Why: geometry, hit-testing and change detection live in the Qt-free
``fontlabapp.fontui.tglyph_model`` and the edits in ``tglyph_edit``; this
module only draws and forwards input.
"""

from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.qt.events.key import key_press_handler

from fontlabapp.qt.compact import compact_layout
from ._canvas_palette import _canvas_colors
from .hinting import font_hint_check
from .lifecycle import Owned
from .livesync import Echo
from .tglyph_edit import Edit, Editor
from .tglyph_model import ZOOM_STEP, TGlyphModel, fingerprint, neighbour
from .twindow_host import FontLabHost, Host

__all__ = ["TGlyph", "create_canvas", "current_glyph_name", "paint", "show_tglyph"]

TITLE = "TGlyph"
NO_FONT_MESSAGE = "Open a font in FontLab first; TGlyph shows a glyph of the current font."
FOLLOW_LABEL = "Follow FontLab current glyph"
FOLLOW_POLL_MS = 250
HELP_TEXT = (
    "Wheel, +/-: zoom. 0 or Fit: fit the glyph. Space-drag or middle-drag: pan. "
    "Click a point to select it; Shift-click adds or removes; drag on empty space to select by rectangle. "
    "Drag selected points to move them; arrows nudge by 1, Shift+arrows by 10; Delete removes points. "
    "O toggles selected on/off-curve points (open endpoints stay on-curve). "
    "P: pen tool (the first click places a pending point, nothing is written until the second click; "
    "later clicks add points, clicking the first point closes, Escape ends); V: select tool."
)
TOOL_KEYS = {"Key_P": "pen", "Key_V": "select"}
NUDGE_KEYS = {"Key_Left": (-1.0, 0.0), "Key_Right": (1.0, 0.0), "Key_Up": (0.0, 1.0), "Key_Down": (0.0, -1.0)}
NUDGE_SHIFT = 10.0
DELETE_KEYS = ("Key_Delete", "Key_Backspace")
POINT_SIZE = 7.0  # on-curve marker, screen pixels
HANDLE_SIZE = 5.0  # off-curve marker, screen pixels
START_SIZE = 11.0  # start point ring, screen pixels
COLORS = {
    "background": "white",
    "box": "#f2f2f2",
    "guide": "#c8c8c8",
    "baseline": "#808080",
    "fill": "#e0e0e0",
    "outline": "#303030",
    "component": "#9cb6d0",
    "handle": "#a0a0a0",
    "on_curve": "#2a7ab0",
    "off_curve": "#b04a2a",
    "start": "#40a040",
    "selected": "#ff8000",
    "anchor": "#a040a0",
    "missing": "#b0b0b0",
    "band": "#2a7ab0",
    "overlay": "#7fb0e0",
    "highlight": "#e03060",
}
HIGHLIGHT_KINDS = ("points", "segments", "anchors")
ZOOM_KEYS = {"Key_Plus": ZOOM_STEP, "Key_Equal": ZOOM_STEP, "Key_Minus": 1 / ZOOM_STEP}
FIT_KEYS = ("Key_0",)


class TGlyph(Owned):
    """Owned TGlyph window over ``font``'s glyph ``name`` on ``layer``."""

    def __init__(
        self,
        font: Any,
        name: str | None = None,
        layer: str | None = None,
        parent: Any = None,
        *,
        controls: bool = True,
        label_prefix: str = "TGlyph",
        hint_check: Any = None,
        host: Host | None = None,
        read_only: bool = False,
    ):
        """``controls=False`` hides the toolbar and help for embedding in a studio shell.

        ``read_only=True`` keeps selection, navigation and zoom but refuses all writes.
        ``label_prefix`` starts every Undo name. ``hint_check(glyph, layer)``
        returns a ``fontui.hinting.HintState``; on a hinted layer point edits
        are refused and the status line says why.
        """
        super().__init__(parent)
        self.font = font
        self.host = FontLabHost(font) if host is None else host
        self.model = TGlyphModel(font, layer=layer)
        self.echo = Echo()
        self.label_prefix = label_prefix
        self.hint_check = hint_check
        self.overlay: Any = None
        self.highlights: dict[str, frozenset] = {kind: frozenset() for kind in HIGHLIGHT_KINDS}
        self.editor = Editor(self.model, label_prefix, read_only=read_only)
        self.panning: tuple[float, float] | None = None
        self.space = False
        self._controls()
        self.control_widgets = [
            self.layer_control, self.name_control, self.prev_control,
            self.next_control, self.fit_control, self.follow_control, self.help,
        ]
        if not controls:
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.setSpacing(0)
            for control in self.control_widgets:
                control.hide()
        else:
            compact_layout(self.layout)  # FontLab panel metrics, issue 253
        self.canvas = create_canvas(self, self.widget)
        self.layout.insertWidget(0, self.canvas, 1)  # glyph view in the top half
        self.follow_timer = QtCore.QTimer(self.widget)
        self.follow_timer.setInterval(FOLLOW_POLL_MS)
        self.connect(self.follow_timer.timeout, lambda *args: self.follow_current())
        self.load(name if name is not None else self._first_name())
        self.host.subscribe(self, self.follow, lambda: [self.font])

    # --- controls --------------------------------------------------------------------
    def _controls(self) -> None:
        row = QtGui.QHBoxLayout()
        self.layer_control = QtGui.QComboBox(self.widget)
        self.layer_control.setAccessibleName("Layer")
        row.addWidget(self.layer_control)
        self.name_control = QtGui.QLineEdit(self.widget)
        self.name_control.setAccessibleName("Glyph name")
        self.name_control.setPlaceholderText("Glyph name")
        row.addWidget(self.name_control)
        self.prev_control = QtGui.QPushButton("Prev", self.widget)
        self.next_control = QtGui.QPushButton("Next", self.widget)
        self.fit_control = QtGui.QPushButton("Fit", self.widget)
        for button in (self.prev_control, self.next_control, self.fit_control):
            row.addWidget(button)
        self.follow_control = QtGui.QCheckBox(FOLLOW_LABEL, self.widget)
        row.addWidget(self.follow_control)
        self.layout.addLayout(row)
        self.diagnostic = QtGui.QLabel("", self.widget)
        self.diagnostic.setWordWrap(True)
        self.readout = QtGui.QLabel("", self.widget)
        help_text = HELP_TEXT.split("Drag selected points")[0] if self.editor.read_only else HELP_TEXT
        self.help = QtGui.QLabel(help_text, self.widget)
        self.help.setWordWrap(True)
        for label in (self.diagnostic, self.readout, self.help):
            self.layout.addWidget(label)
        self._fill_layers()
        self._fill_completer()
        self.connect(self.layer_control.currentIndexChanged, lambda *args: self.choose_layer())
        self.connect(self.name_control.returnPressed, lambda *args: self.choose_name())
        self.connect(self.prev_control.clicked, lambda *args: self.step(-1))
        self.connect(self.next_control.clicked, lambda *args: self.step(1))
        self.connect(self.fit_control.clicked, lambda *args: self.fit())
        self.connect(self.follow_control.toggled, lambda *args: self.set_follow(bool(self.follow_control.checked)))

    def _fill_layers(self) -> None:
        names = self.model.layers()
        if self.model.layer not in names:
            names = [*names, self.model.layer]
        blocked = self.layer_control.blockSignals(True)
        try:
            self.layer_control.clear()
            self.layer_control.addItems(names)
            self.layer_control.setCurrentIndex(names.index(self.model.layer))
        finally:
            self.layer_control.blockSignals(blocked)

    def _fill_completer(self) -> None:
        self.completer = QtGui.QCompleter(self.model.glyph_order(), self.widget)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.name_control.setCompleter(self.completer)

    def _first_name(self) -> str | None:
        order = self.model.glyph_order()
        return order[0] if order else None

    # --- status ----------------------------------------------------------------------
    def fail(self, error: Exception) -> None:
        """Show ``error`` in the status line; the window stays usable."""
        if not self.closed:
            self.diagnostic.setText(f"Error: {error}")

    def hint_state(self) -> Any:
        """The hint state of the shown glyph on its layer (None without a checker or glyph)."""
        if self.model.name is None:
            return None
        check = self.hint_check if self.hint_check is not None else font_hint_check(self.font)
        return check(self.model.name, self.model.layer)

    def set_overlay(self, data: Any) -> None:
        """Draw ``data`` (a ``GlyphData``) as a ghost outline behind the glyph; None clears it."""
        if self.closed:
            return
        self.overlay = data
        self.canvas.update()

    def highlight(self, *, points: Any = (), segments: Any = (), anchors: Any = ()) -> None:
        """Mark ``points``/``segments`` (``(contour, index)`` keys) and ``anchors`` (names)."""
        if self.closed:
            return
        self.highlights = {
            "points": frozenset(points),
            "segments": frozenset(segments),
            "anchors": frozenset(anchors),
        }
        self.canvas.update()

    def _show(self) -> None:
        state = self.hint_state()
        self.diagnostic.setText(state.text() if state else self.model.status)
        data = self.model.data
        if data is None:
            self.readout.setText("")
        else:
            points = sum(len(c.points) for c in data.contours)
            selected = len(self.model.selection)
            self.readout.setText(
                f"{data.name} on {data.layer}: width {data.width:g}, {len(data.contours)} contours, "
                f"{points} points, {len(data.components)} components, {len(data.anchors)} anchors"
                + (f", {selected} selected" if selected else "")
                + (", pen tool" if self.editor.tool == "pen" else "")
            )
        blocked = self.name_control.blockSignals(True)
        try:
            self.name_control.setText(self.model.name or "")
        finally:
            self.name_control.blockSignals(blocked)
        self.canvas.update()

    def _size(self) -> tuple[float, float]:
        return float(self.canvas.width), float(self.canvas.height)

    # --- loading ---------------------------------------------------------------------
    def load(self, name: str | None, layer: str | None = None) -> None:
        """Show ``name`` (on ``layer`` when given), fitted, with no selection."""
        if self.closed:
            return
        try:
            self.editor.reset()
            self.model.load(name, layer)
            self.model.fit(*self._size())
            self._show()
        except Exception as error:
            self.fail(error)

    def refresh(self) -> None:
        """Re-read the shown glyph; keep zoom/pan, and the selection while the structure holds."""
        if self.closed:
            return
        try:
            self.editor.cancel()
            if self.model.refresh():
                self.editor.reset()  # structure changed: the pen contour index may be stale
            if not self.model.view.adjusted:
                self.model.fit(*self._size())
            self._show()
        except Exception as error:
            self.fail(error)

    def follow(self) -> None:
        """Follow callback: refresh unless the font still shows our own last write."""
        if self.closed:
            return
        try:
            fresh = self.model.fingerprint()
            shown = self.editor.before or self.model.data
            if self.editor.busy and fresh in (self.echo.token, fingerprint(shown, self.model.metrics)):
                return  # mid-gesture and nothing external changed: keep the drag and its preview
            if self.echo.stale(fresh):
                self.refresh()
        except Exception as error:
            self.fail(error)

    def choose_layer(self) -> None:
        """Layer selector changed: show the same glyph on the chosen layer."""
        if self.closed:
            return
        try:
            layer = self.layer_control.currentText
            if layer and layer != self.model.layer:
                self.load(self.model.name, layer)
        except Exception as error:
            self.fail(error)

    def choose_name(self) -> None:
        """Glyph name field confirmed: show that glyph."""
        if self.closed:
            return
        try:
            name = str(self.name_control.text).strip()
            if name and name != self.model.name:
                self.load(name)
        except Exception as error:
            self.fail(error)

    def step(self, offset: int) -> None:
        """Show the glyph ``offset`` places away in the glyph order (Prev/Next)."""
        if self.closed:
            return
        try:
            name = neighbour(self.model.glyph_order(), self.model.name or "", offset)
            if name is not None:
                self.load(name)
        except Exception as error:
            self.fail(error)

    def fit(self) -> None:
        """Fit the advance box and outline into the canvas."""
        if self.closed:
            return
        try:
            self.model.fit(*self._size())
            self.canvas.update()
        except Exception as error:
            self.fail(error)

    # --- follow FontLab's current glyph ----------------------------------------------
    def set_follow(self, on: bool) -> None:
        """Start or stop following FontLab's current glyph."""
        if self.closed:
            return
        try:
            if on:
                self.follow_timer.start()
                self.follow_current()
            else:
                self.follow_timer.stop()
        except Exception as error:
            self.fail(error)

    def follow_current(self) -> None:
        """Switch to FontLab's current glyph when it is in this font and differs."""
        if self.closed or not self.follow_control.checked:
            return
        try:
            name = current_glyph_name(self.font)
            if name is not None and name != self.model.name:
                self.load(name)
        except Exception as error:
            self.fail(error)

    # --- canvas input ----------------------------------------------------------------
    def zoom(self, factor: float, x: float | None = None, y: float | None = None) -> None:
        """Zoom by ``factor`` about canvas pixel ``(x, y)`` (default: the centre)."""
        if self.closed:
            return
        try:
            width, height = self._size()
            self.model.view.zoom(factor, width / 2 if x is None else x, height / 2 if y is None else y)
            self.canvas.update()
        except Exception as error:
            self.fail(error)

    def wheel(self, delta: float, x: float, y: float) -> None:
        """Wheel ``delta`` (eighths of a degree; 120 per notch) zooms about the cursor."""
        if delta:
            self.zoom(ZOOM_STEP ** (delta / 120.0), x, y)

    def press(self, x: float, y: float, button: Any, modifiers: Any = 0) -> None:
        """Mouse press: middle or space+left pans; left selects, drags or adds a pen point."""
        if self.closed:
            return
        try:
            if button == QtCore.Qt.MiddleButton or (self.space and button == QtCore.Qt.LeftButton):
                self.panning = (x, y)
                return
            if button != QtCore.Qt.LeftButton:
                return
            if self.editor.tool == "pen":
                edit = self.editor.pen_click(x, y)
                if edit is None:
                    self._show()  # repaint the pending point preview; nothing written
                else:
                    self.commit(edit)
                return
            self.editor.press(x, y, extend=_has(modifiers, "ShiftModifier"))
            self._show()
        except Exception as error:
            self.fail(error)

    def move(self, x: float, y: float) -> None:
        """Mouse move: pan, preview a point drag (no write) or grow the rubber band."""
        if self.closed:
            return
        try:
            if self.panning is not None:
                last_x, last_y = self.panning
                self.model.view.pan(x - last_x, y - last_y)
                self.panning = (x, y)
                self.canvas.update()
            elif self.editor.busy:
                self.editor.move(x, y)
                self._show()
        except Exception as error:
            self.fail(error)

    def release(self, x: float | None = None, y: float | None = None) -> None:
        """Mouse release: end a pan, a rubber band, or a drag (one write when it moved)."""
        if self.closed:
            return
        try:
            if self.panning is not None:
                self.panning = None
                return
            if self.editor.busy:
                edit = self.editor.release(x, y)
                if edit is None:
                    self._show()
                else:
                    self.commit(edit)
        except Exception as error:
            self.editor.cancel()
            self.fail(error)

    def commit(self, edit: Edit | None) -> None:
        """Write ``edit`` once; on success record the echo, on failure show why and revert."""
        if self.closed or edit is None:
            return
        state = self.hint_state()
        if state:
            self.editor.pen = self.editor.pending = None
            self._show()
            self.fail(ValueError(state.text()))
            return
        note = _pending_note()
        try:
            token = self.editor.commit(edit)
        except Exception as error:
            self._show()
            self.fail(error)
            return
        self.echo.record(token)
        self._show()
        message = f"{edit.action}: {self.model.name} on {self.model.layer}."
        self.diagnostic.setText(" ".join(part for part in (message, note) if part))

    def set_tool(self, tool: str) -> None:
        """Switch between the ``"select"`` and ``"pen"`` tools."""
        if self.closed:
            return
        try:
            self.editor.set_tool(tool)
            self._show()
        except Exception as error:
            self.fail(error)

    def key_press(self, key: Any, modifiers: Any = 0, auto_repeat: bool = False) -> bool:
        """Canvas keys: ``+``/``-`` zoom, ``0`` fits, space arms panning; never raise."""
        if self.closed:
            return False
        try:
            if self.editor.read_only and (
                key in [getattr(QtCore.Qt, name, None) for name in (*TOOL_KEYS, *NUDGE_KEYS, *DELETE_KEYS, "Key_O")]
                or (any(_has(modifiers, name) for name in ("ControlModifier", "MetaModifier"))
                    and key in [getattr(QtCore.Qt, name, None) for name in ("Key_X", "Key_V")])
            ):
                return True
            if key == getattr(QtCore.Qt, "Key_O", None):
                if auto_repeat or any(_has(modifiers, name) for name in ("ControlModifier", "MetaModifier", "AltModifier")):
                    return False
                self.commit(self.editor.toggle())
                return True
            if key == QtCore.Qt.Key_Space:
                self.space = True
                return True
            for name, factor in ZOOM_KEYS.items():
                if key == getattr(QtCore.Qt, name, None):
                    self.zoom(factor)
                    return True
            if any(key == getattr(QtCore.Qt, name, None) for name in FIT_KEYS):
                self.fit()
                return True
            return self._edit_key(key, modifiers)
        except Exception as error:
            self.fail(error)
            return False

    def _edit_key(self, key: Any, modifiers: Any) -> bool:
        if key == getattr(QtCore.Qt, "Key_Escape", None):
            ended = self.editor.escape()
            self._show()
            return ended
        for name, tool in TOOL_KEYS.items():
            if key == getattr(QtCore.Qt, name, None):
                self.set_tool(tool)
                return True
        for name, (dx, dy) in NUDGE_KEYS.items():
            if key == getattr(QtCore.Qt, name, None):
                step = NUDGE_SHIFT if _has(modifiers, "ShiftModifier") else 1.0
                self.commit(self.editor.nudge(dx * step, dy * step))
                return True
        if any(key == getattr(QtCore.Qt, name, None) for name in DELETE_KEYS):
            self.commit(self.editor.delete())
            return True
        return False

    def key_release(self, key: Any, auto_repeat: bool = False) -> bool:
        if self.closed or auto_repeat or key != QtCore.Qt.Key_Space:
            return False
        self.space = False
        self.panning = None
        return True

    def close(self) -> None:
        """Stop following, drop the font, then disconnect everything owned."""
        if self._close_complete:
            return
        self.follow_timer.stop()
        super().close()


class _Names:
    """``package.findName`` adapter for ``current_glyph``: the name when in ``font``."""

    def __init__(self, font: Any) -> None:
        self.font = font

    def findName(self, name: Any) -> str | None:
        name = str(name) if name else ""
        return name if name and name in self.font else None


def current_glyph_name(font: Any) -> str | None:
    """Name of FontLab's current glyph when ``font`` has it; None otherwise or offline.

    Uses ``fontlabapp.contours.nodes.coordinates.current_glyph`` (FontLab's
    ``CurrentGlyph()`` of the active window), reading only the glyph's name.
    """
    from fontlabapp.contours.nodes.coordinates import current_glyph

    try:
        return current_glyph(_Names(font))
    except RuntimeError:  # no FontLab: the native module is missing
        return None


def _has(modifiers: Any, name: str) -> bool:
    flag = getattr(QtCore.Qt, name, None)
    try:
        return bool(int(modifiers) & int(flag))
    except (TypeError, ValueError):
        return False


def _event_xy(event: Any) -> tuple[float, float]:
    position = event.pos()
    return float(position.x()), float(position.y())


def create_canvas(owner: TGlyph, parent: Any) -> Any:
    """Return the TGlyph canvas widget; it paints and forwards input to ``owner``."""

    class Canvas(QtGui.QWidget):
        def paintEvent(self, event: Any) -> None:
            paint(owner, self)

        def mousePressEvent(self, event: Any) -> None:
            try:
                self.setFocus()
                owner.press(*_event_xy(event), event.button(), event.modifiers())
            except Exception as error:
                owner.fail(error)
            event.accept()

        def mouseMoveEvent(self, event: Any) -> None:
            try:
                owner.move(*_event_xy(event))
            except Exception as error:
                owner.fail(error)
            event.accept()

        def mouseReleaseEvent(self, event: Any) -> None:
            try:
                owner.release(*_event_xy(event))
            except Exception as error:
                owner.fail(error)
            event.accept()

        def wheelEvent(self, event: Any) -> None:
            try:
                owner.wheel(float(event.angleDelta().y()), *_event_xy(event))
            except Exception as error:
                owner.fail(error)
            event.accept()

        def resizeEvent(self, event: Any) -> None:
            try:
                if not owner.closed and not owner.model.view.adjusted:
                    owner.fit()
            except Exception as error:
                owner.fail(error)

        keyPressEvent = key_press_handler(
            QtGui.QWidget,
            lambda widget, event: owner.key_press(event.key(), event.modifiers(), event.isAutoRepeat()),
        )

        def keyReleaseEvent(self, event: Any) -> None:
            try:
                if owner.key_release(event.key(), event.isAutoRepeat()):
                    event.accept()
                    return
                QtGui.QWidget.keyReleaseEvent(self, event)
            except Exception as error:
                owner.fail(error)

    canvas = Canvas(parent)
    canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
    canvas.setMinimumSize(320, 320)
    return canvas


def _pen(color: str, width: float = 1.0) -> Any:
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(width)
    return pen


def _brush(color: str | None) -> Any:
    return QtGui.QBrush(QtGui.QColor(color)) if color else QtGui.QBrush()


def paint(owner: TGlyph, canvas: Any) -> None:
    """Paint metrics, advance box, components, outline, handles, points and anchors; never raise."""
    painter = None
    try:
        painter = QtGui.QPainter(canvas)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        colors = _canvas_colors(canvas, COLORS)
        painter.fillRect(canvas.rect, QtGui.QColor(colors["background"]))
        model = owner.model
        _paint_metrics(painter, model, float(canvas.width), colors)
        data = model.data
        if data is None:
            painter.setPen(_pen(colors["missing"]))
            painter.drawText(canvas.rect, QtCore.Qt.AlignCenter, model.status or "No glyph")
            return
        if owner.overlay is not None:
            _paint_contours(painter, model.view, owner.overlay.contours, None, colors["overlay"])
        for component in data.components:
            _paint_contours(painter, model.view, component.contours, colors["component"], colors["component"])
        _paint_contours(painter, model.view, data.contours, colors["fill"], colors["outline"])
        _paint_points(painter, model, colors)
        _paint_anchors(painter, model, colors)
        _paint_highlights(painter, model, owner.highlights, colors)
        _paint_band(painter, owner.editor.band, colors)
        _paint_pending(painter, model.view, owner.editor.pending, colors)
    except Exception as error:
        owner.fail(error)
    finally:
        if painter is not None:
            painter.end()


def _paint_metrics(painter: Any, model: TGlyphModel, width: float, colors: dict[str, str]) -> None:
    view, metrics = model.view, model.metrics
    advance = model.data.width if model.data is not None else 0.0
    left, top = view.to_screen(0.0, metrics.top)
    right, bottom = view.to_screen(advance, metrics.bottom)
    box = QtCore.QRectF(left, top, right - left, bottom - top)
    painter.fillRect(box, QtGui.QColor(colors["box"]))
    painter.setPen(_pen(colors["guide"]))
    painter.drawRect(box)
    for label, y in metrics.lines():
        level = view.to_screen(0.0, y)[1]
        painter.setPen(_pen(colors["baseline" if label == "baseline" else "guide"]))
        painter.drawLine(QtCore.QLineF(0.0, level, width, level))
        painter.drawText(QtCore.QPointF(4.0, level - 3.0), label)


def _path(view: Any, contours: Any) -> Any:
    """A QPainterPath of ``contours`` in screen pixels (quadratic runs drawn as quads)."""
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.WindingFill)
    for contour in contours:
        _contour_path(path, view, contour)
    return path


def _contour_path(path: Any, view: Any, contour: Any) -> None:
    points = list(contour.points)
    if not points:
        return
    if contour.closed:
        # Start at an on-curve point; trailing off-curves lead into it.
        first = next((i for i, p in enumerate(points) if p.on_curve), None)
        if first is None:
            return
        points = points[first + 1 :] + points[: first + 1]
        start = points[-1]
    else:
        start, points = points[0], points[1:]
    path.moveTo(QtCore.QPointF(*view.to_screen(start.x, start.y)))
    pending: list[Any] = []
    for point in points:
        if not point.on_curve:
            pending.append(point)
            continue
        _segment(path, view, pending, point)
        pending = []
    if contour.closed:
        path.closeSubpath()


def _segment(path: Any, view: Any, offs: list[Any], end: Any) -> None:
    target = QtCore.QPointF(*view.to_screen(end.x, end.y))
    screen = [QtCore.QPointF(*view.to_screen(p.x, p.y)) for p in offs]
    if not offs:
        path.lineTo(target)
    elif end.type == "curve" and len(offs) == 2:
        path.cubicTo(screen[0], screen[1], target)
    elif end.type == "curve":
        path.lineTo(target)  # unusual cubic run: show its straight span
    else:
        # TrueType quadratic run: implied on-curve points between off-curves.
        for i in range(len(offs)):
            if i + 1 < len(offs):
                nxt = offs[i + 1]
                mid = QtCore.QPointF(*view.to_screen((offs[i].x + nxt.x) / 2, (offs[i].y + nxt.y) / 2))
                path.quadTo(screen[i], mid)
            else:
                path.quadTo(screen[i], target)


def _paint_contours(painter: Any, view: Any, contours: Any, fill: str, line: str) -> None:
    if not contours:
        return
    closed = [c for c in contours if c.closed]
    opened = [c for c in contours if not c.closed]
    painter.setPen(_pen(line))
    if closed:
        painter.setBrush(_brush(fill))
        painter.drawPath(_path(view, closed))
    if opened:
        painter.setBrush(_brush(None))
        painter.drawPath(_path(view, opened))


def _paint_points(painter: Any, model: TGlyphModel, colors: dict[str, str]) -> None:
    view, data = model.view, model.data
    for c, contour in enumerate(data.contours):
        points = contour.points
        count = len(points)
        painter.setPen(_pen(colors["handle"]))
        for i, point in enumerate(points):
            if point.on_curve:
                continue
            for j in (i - 1, (i + 1) % count):
                if j < 0 and not contour.closed:
                    continue
                other = points[j]
                if other.on_curve:
                    painter.drawLine(QtCore.QLineF(*view.to_screen(point.x, point.y), *view.to_screen(other.x, other.y)))
        for i, point in enumerate(points):
            x, y = view.to_screen(point.x, point.y)
            selected = (c, i) in model.selection
            color = colors["selected"] if selected else colors["on_curve" if point.on_curve else "off_curve"]
            painter.setPen(_pen(color))
            painter.setBrush(_brush(color))
            if not point.on_curve:
                size = HANDLE_SIZE
                painter.drawEllipse(QtCore.QRectF(x - size / 2, y - size / 2, size, size))
            elif point.smooth:
                size = POINT_SIZE
                painter.drawEllipse(QtCore.QRectF(x - size / 2, y - size / 2, size, size))
            else:
                size = POINT_SIZE
                painter.drawRect(QtCore.QRectF(x - size / 2, y - size / 2, size, size))
        start = next((p for p in points if p.on_curve), None)
        if start is not None:
            x, y = view.to_screen(start.x, start.y)
            painter.setPen(_pen(colors["start"], 2.0))
            painter.setBrush(_brush(None))
            painter.drawEllipse(QtCore.QRectF(x - START_SIZE / 2, y - START_SIZE / 2, START_SIZE, START_SIZE))


def _paint_anchors(painter: Any, model: TGlyphModel, colors: dict[str, str]) -> None:
    view = model.view
    for anchor in model.data.anchors:
        x, y = view.to_screen(anchor.x, anchor.y)
        painter.setPen(_pen(colors["anchor"]))
        painter.setBrush(_brush(None))
        size = POINT_SIZE
        painter.drawLine(QtCore.QLineF(x - size, y, x + size, y))
        painter.drawLine(QtCore.QLineF(x, y - size, x, y + size))
        painter.drawText(QtCore.QPointF(x + size, y - size), anchor.name)


def _paint_highlights(painter: Any, model: TGlyphModel, marks: dict[str, frozenset], colors: dict[str, str]) -> None:
    view, data = model.view, model.data
    painter.setPen(_pen(colors["highlight"], 2.0))
    painter.setBrush(_brush(None))
    size = START_SIZE
    for c, i in sorted(marks["points"] | marks["segments"]):
        if c < len(data.contours) and i < len(data.contours[c].points):
            point = data.contours[c].points[i]
            x, y = view.to_screen(point.x, point.y)
            painter.drawEllipse(QtCore.QRectF(x - size / 2, y - size / 2, size, size))
    for c, i in sorted(marks["segments"]):
        if c < len(data.contours) and i < len(data.contours[c].points):
            points = data.contours[c].points
            a, b = points[i], points[(i + 1) % len(points)]
            painter.drawLine(QtCore.QLineF(*view.to_screen(a.x, a.y), *view.to_screen(b.x, b.y)))
    for anchor in data.anchors:
        if anchor.name in marks["anchors"]:
            x, y = view.to_screen(anchor.x, anchor.y)
            painter.drawEllipse(QtCore.QRectF(x - size / 2, y - size / 2, size, size))


def _paint_band(painter: Any, band: tuple[float, float, float, float] | None, colors: dict[str, str]) -> None:
    if band is None:
        return
    x0, x1 = sorted((band[0], band[2]))
    y0, y1 = sorted((band[1], band[3]))
    painter.setPen(_pen(colors["band"]))
    painter.setBrush(_brush(None))
    painter.drawRect(QtCore.QRectF(x0, y0, x1 - x0, y1 - y0))


def _paint_pending(painter: Any, view: Any, point: Any, colors: dict[str, str]) -> None:
    """Draw the pen tool's unwritten first point as a hollow start marker."""
    if point is None:
        return
    x, y = view.to_screen(point.x, point.y)
    painter.setPen(_pen(colors["start"], 2.0))
    painter.setBrush(_brush(None))
    painter.drawEllipse(QtCore.QRectF(x - START_SIZE / 2, y - START_SIZE / 2, START_SIZE, START_SIZE))


def _pending_note() -> str:
    """FontLab's queued-update disclosure shared with TMetrics; empty offline."""
    from .tmetrics import _pending_note as pending_note

    return pending_note()


def _current_font() -> Any | None:
    """FontLab's current font as a live Fontport RFont (shared with TMetrics), or None."""
    from .tmetrics import _current_font as current_font

    return current_font()


def _notify(text: str) -> None:
    """Show ``text`` in a modal message box; print it when Qt or FontLab refuses."""
    try:
        import fontlab

        from fontlabapp.qt.dialogs import create_message_box, run_message_box

        box = create_message_box(QtGui, TITLE, text, "Information", (fontlab.MainWindow(),))
        run_message_box(box, QtGui.QMessageBox.Ok)
    except Exception:
        print(f"{TITLE}: {text}")


def show_tglyph(font: Any = None, name: str | None = None, layer: str | None = None, *, parent: Any = None) -> TGlyph | None:
    """Open TGlyph over ``font``'s ``name`` on ``layer`` and return it.

    Defaults: FontLab's current font, its current glyph (else the first glyph)
    and the default layer. Returns None, after a message, when no font is open
    or Fontport cannot resolve one.
    """
    if font is None:
        try:
            font = _current_font()
        except Exception as error:
            _notify(f"{NO_FONT_MESSAGE} ({error})")
            return None
        if font is None:
            _notify(NO_FONT_MESSAGE)
            return None
    if name is None:
        try:
            name = current_glyph_name(font)
        except Exception:
            name = None
    window = TGlyph(font, name, layer, parent)
    try:
        window.widget.setWindowTitle(TITLE)
        window.widget.resize(640, 720)
        window.widget.show()
    except Exception:
        window.close()
        raise
    return window
