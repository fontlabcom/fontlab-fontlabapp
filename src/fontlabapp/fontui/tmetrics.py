# this_file: src/fontlabapp/fontui/tmetrics.py
# SPDX-License-Identifier: Apache-2.0
"""TMetrics: a shaping, metrics and kerning window that follows and edits FontLab.

What: type text (or ``/names``), features, direction, script and language; the
canvas shows the shaped rows with the baseline and vertical metric lines,
glyph boxes, sidebearing marks, kerning offsets and the selected glyph. The
readout names the selected glyph's advance, LSB and RSB and the kerning pair
before it (group or glyph pair). Click or press the arrow keys to select;
double-click calls ``on_open_glyph(name)``. The LSB, RSB, Width and Kerning
fields write the selected glyph and the pair before it back to the font (press
Return); Alt+Left/Right nudge the RSB and Ctrl+Alt+Left/Right the pair kerning
(on macOS either Control or Command with Option; see ``HELP_TEXT``). A write
to a group pair names the actual group keys in the status line. Each glyph write is one ``font.edit_glyph`` on the default
layer named ``TMetrics: <LSB|RSB|width> <glyph>``; each kerning write is one
``font.kerning.apply`` named ``TMetrics: kerning <left> <right>``, read back.
FontLab edits (outlines, metrics, kerning, features) and Undo/Redo re-shape
within the follow delay, keeping the text, the selection and the scroll
position; the window's own writes are recognised by
``fontlabapp.fontui.livesync.Echo`` and do not reset it a second time.
Use: ``show_tmetrics()`` over the current FontLab font (double-click opens
``fontlabapp.fontui.tglyph`` on that glyph, reusing one TGlyph window), or
``TMetrics(font, parent, on_open_glyph)`` over any FontParts-style font.
Why: all layout and readout rules live in the Qt-free
``fontlabapp.fontui.tmetrics_model``; this module only draws and forwards input.
"""

from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.qt.events.key import key_press_handler

from ._canvas_palette import _canvas_colors
from ._font_reads import FontReads
from ._fontport import require_fontport
from .hinting import font_hint_check
from .kerning import apply_kerning, number_text
from .lifecycle import Owned
from .livesync import Echo
from .model import partition_paths
from .tmetrics_model import MARGIN, METRIC_FIELDS, TMetricsModel, _layer_sidebearings, write_metric
from .twindow_host import FontLabHost, Host

__all__ = ["TMetrics", "create_canvas", "open_tglyph", "paint", "show_tmetrics"]

TITLE = "TMetrics"
NO_FONT_MESSAGE = "Open a font in FontLab first; TMetrics shows the current font."
DIRECTION_LABELS = ("Left to right", "Right to left")
KEY_STEPS = {"Key_Left": "left", "Key_Right": "right", "Key_Home": "home", "Key_End": "end"}
NUDGE_KEYS = {"Key_Left": -1, "Key_Right": 1}
SHIFT_FACTOR = 10
HELP_TEXT = (
    "Click or Left/Right/Home/End: select. Double-click: open the glyph. "
    "LSB, RSB, Width, Kerning: type a value and press Return to write it. "
    "Alt+Left/Right: RSB -1/+1. Ctrl+Alt+Left/Right: pair kerning -1/+1 "
    "(on macOS, Control+Option or Command+Option with Left/Right). "
    "Add Shift for steps of 10. Every write is one FontLab Undo step."
)
NO_PAIR_MESSAGE = "Select a glyph that follows another one to kern the pair."
READ_ONLY_MESSAGE = "This preview is read-only; edit metrics in another tool."
COLORS = {
    "background": "white",
    "guide": "#c8c8c8",
    "baseline": "#808080",
    "box": "#e4e4e4",
    "selected": "#d8eaff",
    "bearing": "#2a7ab0",
    "kern_negative": "#d04040",
    "kern_positive": "#40a040",
    "glyph": "#303030",
    "missing": "#b0b0b0",
}
BEARING_TICK = 6  # pixels below the baseline


class TMetrics(Owned):
    """Owned TMetrics window over ``font``; ``on_open_glyph(name)`` on double-click."""

    def __init__(
        self,
        font: Any,
        parent: Any = None,
        on_open_glyph: Any = None,
        text: str | None = None,
        *,
        controls: bool = True,
        layer: str | None = None,
        label_prefix: str = "TMetrics",
        hint_check: Any = None,
        read_only: bool = False,
        host: Host | None = None,
    ):
        """``controls=False`` hides the input rows (an app shell drives the text).

        ``layer`` is the explicit target layer of every metric write (None: the
        font's default layer); kerning writes name it as their master.
        ``label_prefix`` starts every Undo name. ``hint_check(glyph, layer)``
        returns a ``fontui.hinting.HintState``; on a hinted layer LSB/RSB edits
        are off while advance width and kerning still work.
        ``read_only=True`` refuses every metric and kerning write (edit fields
        and Alt+arrow nudges) with a status message: a pure text preview.
        """
        super().__init__(parent)
        self.font = font
        self.host = FontLabHost(font) if host is None else host
        self._host_text: str | None = None
        self._sync_text = controls and not read_only
        self.on_open_glyph = on_open_glyph
        self.layer = layer
        self.label_prefix = label_prefix
        self.hint_check = hint_check
        self.read_only = read_only
        self.control_widgets: list[Any] = []
        self._reads = FontReads(font)
        self._probed_names: set[str] = set()  # missing /names already asked of the font
        self._outline_memo: dict[Any, Any] = {}  # outlines kept while only the text changes
        self.model = TMetricsModel(self._reads, layer=layer)
        self.layout_geometry = self.model.geometry()
        self.outlines: dict[str, Any] = {}
        self.echo = Echo()
        self.drawn: str | None = None  # fingerprint of the state last shaped for drawing
        self._refresh_generation = 0
        self._controls()
        self._canvas()
        if not controls:
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.setSpacing(0)
            self.scroll.setFrameShape(QtGui.QFrame.NoFrame)
            for control in self.control_widgets:
                control.hide()
        if text:
            self.set_text(text)
        else:
            self.refresh()
        self.host.subscribe(self, self.follow, lambda: [self.font], text_callback=self.follow_text)
        self.connect(self.text_control.returnPressed, lambda *args: self.commit_text())

    def _field(self, row: Any, label: str, placeholder: str = "") -> Any:
        control = QtGui.QLineEdit(self.widget)
        control.setAccessibleName(label)
        if placeholder:
            control.setPlaceholderText(placeholder)
        caption = QtGui.QLabel(label, self.widget)
        caption.setBuddy(control)
        row.addWidget(caption)
        row.addWidget(control)
        self.control_widgets += [caption, control]
        self.connect(control.textChanged, lambda *args: self._reshape())
        return control

    def _edit_field(self, row: Any, label: str, target: str) -> Any:
        control = QtGui.QLineEdit(self.widget)
        control.setAccessibleName(f"{label} value")
        caption = QtGui.QLabel("Width" if label == "width" else label, self.widget)
        caption.setBuddy(control)
        row.addWidget(caption)
        row.addWidget(control)
        self.control_widgets += [caption, control]
        self.connect(control.returnPressed, lambda *args: self.commit(target, control.text))
        return control

    def _controls(self) -> None:
        first, second = QtGui.QHBoxLayout(), QtGui.QHBoxLayout()
        self.text_control = self._field(first, "Text", "Text or /names")
        self.features_control = self._field(first, "Features", "kern liga -calt")
        self.layer_control = QtGui.QComboBox(self.widget)
        self.layer_control.setAccessibleName("Master / layer")
        first.addWidget(self.layer_control)
        self.control_widgets.append(self.layer_control)
        self._fill_layers()
        self.connect(self.layer_control.currentIndexChanged, lambda *args: self.choose_layer())
        self.direction_control = QtGui.QComboBox(self.widget)
        self.direction_control.addItems(list(DIRECTION_LABELS))
        self.direction_control.setAccessibleName("Direction")
        second.addWidget(self.direction_control)
        self.script_control = self._field(second, "Script", "latn")
        self.language_control = self._field(second, "Language", "dflt")
        self.kerning_control = QtGui.QCheckBox("Apply kerning", self.widget)
        self.kerning_control.setChecked(True)
        second.addWidget(self.kerning_control)
        self.size_control = QtGui.QSpinBox(self.widget)
        self.size_control.setRange(8, 512)
        self.size_control.setValue(72)
        self.size_control.setSuffix(" px/em")
        self.size_control.setAccessibleName("Size")
        second.addWidget(self.size_control)
        self.layout.addLayout(first)
        self.layout.addLayout(second)
        self.diagnostic = QtGui.QLabel("", self.widget)
        self.diagnostic.setWordWrap(True)
        self.readout = QtGui.QLabel("", self.widget)
        self.pair_readout = QtGui.QLabel("", self.widget)
        for label in (self.diagnostic, self.readout, self.pair_readout):
            self.layout.addWidget(label)
        edits = QtGui.QHBoxLayout()
        self.metric_controls = {
            metric: self._edit_field(edits, label, metric) for metric, label in METRIC_FIELDS.items()
        }
        self.kern_control = self._edit_field(edits, "Kerning", "kerning")
        self.layout.addLayout(edits)
        self.help = QtGui.QLabel(HELP_TEXT, self.widget)
        self.help.setWordWrap(True)
        self.layout.addWidget(self.help)
        self.control_widgets += [self.direction_control, self.kerning_control, self.size_control, self.help]
        self.connect(self.direction_control.currentIndexChanged, lambda *args: self._reshape())
        self.connect(self.kerning_control.toggled, lambda *args: self._reshape())
        self.connect(self.size_control.valueChanged, lambda *args: self._reshape())

    def _canvas(self) -> None:
        owner = self

        class Scroll(QtGui.QScrollArea):
            def viewportEvent(self, event: Any) -> bool:
                if event.type() == QtCore.QEvent.Resize and not owner.closed:
                    owner.reflow_timer.start()
                return QtGui.QScrollArea.viewportEvent(self, event)

        self.reflow_timer = QtCore.QTimer(self.widget)
        self.reflow_timer.setSingleShot(True)
        self.reflow_timer.setInterval(0)
        self.connect(self.reflow_timer.timeout, lambda *args: self.reflow())
        self.scroll = Scroll(self.widget)
        self.canvas = create_canvas(self, self.scroll)
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)
        self.layout.addWidget(self.scroll)

    def fail(self, error: Exception) -> None:
        """Show ``error`` in the status line; the window stays usable."""
        if not self.closed:
            self.diagnostic.setText(f"Error: {error}")

    def _viewport_width(self) -> float:
        return float(self.scroll.viewport().width)

    def _wrap_units(self) -> float | None:
        scale = max(float(self.size_control.value), 1.0) / self.model.metrics.upm
        width = (self._viewport_width() - 2 * MARGIN) / scale
        return width if width > 0 else None

    def refresh(self) -> None:
        """Re-read the font and re-shape, keeping text, selection and scroll.

        Call this after changing the font. Typing and view settings use
        ``_reshape``, which reuses the whole-font reads of the last refresh.
        """
        if self.closed:
            return
        self._forget_font_reads()
        self._reshape()

    def _see_new_glyph_names(self) -> None:
        """Re-read the font when typed ``/name`` tokens name a glyph added since the last read.

        Each missing name asks the font once per read generation, so a
        ``/name`` that stays missing costs nothing on later keystrokes.
        """
        probed = self._probed_names
        for token in self.model.settings.text.split():
            name = token[1:]
            if not token.startswith("/") or not name or name in probed or name in self._reads:
                continue
            probed.add(name)
            if name in self._reads.font:
                self._forget_font_reads()
                return

    def _forget_font_reads(self) -> None:
        self._reads.reset()
        self._outline_memo.clear()
        self._probed_names.clear()

    def _reshape(self) -> None:
        """Re-shape from the controls with the remembered font reads."""
        if self.closed:
            return
        self.drawn = None
        try:
            self._use_font()
            self.model.settings = self.model.settings.__class__(
                text=self.text_control.text,
                features=self.features_control.text,
                direction="rtl" if self.direction_control.currentIndex == 1 else "ltr",
                script=self.script_control.text,
                language=self.language_control.text,
                kerning=bool(self.kerning_control.checked) and self._current_master(),
                size=float(self.size_control.value),
            )
            self._see_new_glyph_names()
            with self.model.outline_scope(self._outline_memo):
                self.model.reshape()
                self.drawn = self.model.fingerprint()
                self.model.set_wrap_width(self._wrap_units())
                self.outlines = {}
                for cell in self.model.cells:
                    if cell.present and cell.name not in self.outlines:
                        self.outlines[cell.name] = _outline(self.model, cell.name)
            status = self.model.status
            if not self._current_master():
                status += (
                    f"; kerning is unavailable for {self._target_layer()}; FontLab keeps font kerning "
                    f"on the default master ({getattr(self._reads, 'defaultLayerName', None)})."
                )
            self.diagnostic.setText(status)
            self._relayout()
            self._refresh_generation += 1
        except Exception as error:
            self.fail(error)

    def follow(self) -> None:
        """Follow callback: refresh unless the font still shows our own last write."""
        if self.closed:
            return
        try:
            generation = self._refresh_generation
            self._forget_font_reads()
            self._follow_text()
            self._fill_layers()
            self._use_font()
            current = self.model.fingerprint()
            if self.echo.stale(current) and (
                self._refresh_generation == generation or current != self.drawn
            ):
                # The reads were forgotten above and the fingerprint just re-read
                # the font, so re-shape from them instead of reading it again.
                self._reshape()
        except Exception as error:
            self.fail(error)

    def follow_text(self) -> None:
        """Glyph-window text poll: adopt new text; the font itself did not change."""
        if self.closed:
            return
        try:
            self._follow_text()
        except Exception as error:
            self.fail(error)

    def _use_font(self) -> None:
        if self._reads.font is not self.font:
            self._reads = FontReads(self.font)
            self._outline_memo.clear()
            self._probed_names.clear()
        elif self._reads.master_changed():
            # FontLab may switch the current master without a font notification.
            self._forget_font_reads()
        self.model.font = self._reads
        self.model.layer = self._target_layer()

    def _fill_layers(self) -> None:
        from .tglyph_model import layer_names

        self.layer_choices = [None, *layer_names(self.font)]
        if self.layer not in self.layer_choices:
            self.layer_choices.append(self.layer)
        blocked = self.layer_control.blockSignals(True)
        try:
            self.layer_control.clear()
            self.layer_control.addItems(["Current master", *self.layer_choices[1:]])
            self.layer_control.setCurrentIndex(self.layer_choices.index(self.layer))
        finally:
            self.layer_control.blockSignals(blocked)

    def _target_layer(self) -> str | None:
        """The layer read and written: the chosen one, else FontLab's current master.

        None means the default master (``defaultLayerName``). FontLab's current
        master can differ from it after ``setMaster()``; reads come from FontReads,
        so this costs nothing per keystroke.
        """
        if self.layer is not None:
            return self.layer
        current = getattr(self._reads, "current_master", None)
        return None if current in (None, getattr(self._reads, "defaultLayerName", None)) else current

    def _current_master(self) -> bool:
        """True when the target layer is the default master, which owns font kerning."""
        # FontParts checks the name against every layer of the font: read it once per refresh.
        return self._target_layer() in (None, getattr(self._reads, "defaultLayerName", None))

    def choose_layer(self) -> None:
        """Select the explicit layer for outlines and metrics; guard current-master kerning."""
        try:
            self.set_layer(self.layer_choices[self.layer_control.currentIndex])
        except Exception as error:
            self.fail(error)

    def _follow_text(self) -> None:
        if not self._sync_text:
            return
        text = self.host.read_text()
        if text is not None and text != self._host_text:
            if (self._host_text is None and not self.text_control.text) or self.text_control.text == self._host_text:
                self._host_text = text
                self.set_text(text)

    def commit_text(self) -> bool:
        """Return sends literal text to the bound FontLab glyph window when available."""
        if self.closed or self.read_only:
            return False
        try:
            text = self.text_control.text
            if not self.host.write_text(text):
                self.diagnostic.setText("FontLab glyph-window text is unavailable; preview text stays local.")
                return False
            self._host_text = text
            self.refresh()
            return True
        except Exception as error:
            self.fail(error)
            return False

    def commit(self, target: str, text: str) -> bool:
        """Write ``text`` to ``target`` (``lsb``/``rsb``/``width``/``kerning``) of the selection.

        Return True after a verified write. Failures (parse, guard, backend,
        readback) go to the status line and leave the model unchanged.
        """
        if self.closed:
            return False
        if self.read_only:
            self.fail(ValueError(READ_ONLY_MESSAGE))
            return False
        try:
            if target == "kerning":
                return self._write_kerning(None if not str(text).strip() else float(text))
            return self._write_metric(target, float(text))
        except Exception as error:
            self.fail(error)
            return False

    def nudge(self, target: str, step: float) -> bool:
        """Add ``step`` to the selected glyph's RSB (``rsb``) or the pair kerning (``kerning``)."""
        if self.closed:
            return False
        if self.read_only:
            self.fail(ValueError(READ_ONLY_MESSAGE))
            return False
        try:
            if target == "kerning":
                pair = self._pair()
                return self._write_kerning(pair.value + step)
            glyph = self._glyph()
            layer = self._target_layer()
            rsb = glyph.rsb if layer is None else _layer_sidebearings(self.font, glyph.name, layer)[2]
            if rsb is None:
                raise ValueError(f"{glyph.name} has no outline; set its advance width instead")
            return self._write_metric(target, rsb + step)
        except Exception as error:
            self.fail(error)
            return False

    def _glyph(self) -> Any:
        glyph = self.model.glyph_readout()
        if glyph is None:
            raise ValueError("Select a glyph first.")
        return glyph

    def _pair(self) -> Any:
        pair = self.model.pair_readout()
        if pair is None:
            raise ValueError(NO_PAIR_MESSAGE)
        return pair

    def hint_state(self, name: str | None = None) -> Any:
        """The hint state of ``name`` (default: the selected glyph) on the target layer."""
        if name is None:
            glyph = self.model.glyph_readout()
            name = glyph.name if glyph else None
        if name is None:
            return None
        check = self.hint_check if self.hint_check is not None else font_hint_check(self.font)
        return check(name, self._target_layer())

    def _write_metric(self, metric: str, value: float) -> bool:
        name = self._glyph().name
        if metric in ("lsb", "rsb"):
            state = self.hint_state(name)
            if state:
                raise ValueError(state.text())
        note = _pending_note()
        undo = f"{self.label_prefix}: {METRIC_FIELDS[metric]} {name}"
        if not write_metric(self.font, name, metric, value, layer=self._target_layer(), undo_name=undo):
            self.diagnostic.setText("No changes to apply.")
            return False
        self._written(f"Set {METRIC_FIELDS[metric]} of {name} to {number_text(value)}.", note)
        return True

    def _write_kerning(self, value: float | None) -> bool:
        pair = self._pair()
        key = pair.key or (pair.left, pair.right)
        note = _pending_note()
        if value is None and pair.key is None:
            self.diagnostic.setText("No changes to apply.")
            return False
        values = apply_kerning(
            self.font,
            "delete" if value is None else "apply",
            key,
            value,
            undo_name=f"{self.label_prefix}: kerning {pair.left} {pair.right}",
            master=self._target_layer(),
        )
        if values is None:
            self.diagnostic.setText("No changes to apply.")
            return False
        shown = "removed" if value is None else number_text(value)
        if pair.key is not None and pair.kind == "group":
            message = f"Kerning {key[0]}/{key[1]} (group pair for {pair.left} {pair.right}): {shown}."
        else:
            message = f"Kerning {key[0]} {key[1]}: {shown}."
        self._written(message, note)
        return True

    def _written(self, message: str, note: str) -> None:
        self.refresh()
        if self.drawn is not None:
            self.echo.record(self.drawn)
        self.diagnostic.setText(" ".join(part for part in (message, note) if part))

    def key_press(self, key: Any, modifiers: Any = 0) -> bool:
        """Canvas keys: Alt(+Ctrl)(+Shift)+Left/Right nudge, else selection; never raise."""
        if self.closed:
            return False
        try:
            if _has(modifiers, "AltModifier"):
                for name, sign in NUDGE_KEYS.items():
                    if key == getattr(QtCore.Qt, name, None):
                        step = sign * (SHIFT_FACTOR if _has(modifiers, "ShiftModifier") else 1)
                        # Qt on macOS reports the Control key as MetaModifier.
                        control = _has(modifiers, "ControlModifier") or _has(modifiers, "MetaModifier")
                        target = "kerning" if control else "rsb"
                        self.nudge(target, step)
                        return True
                return False
            return self.select_key(key)
        except Exception as error:
            self.fail(error)
            return False

    def reflow(self) -> None:
        """Re-break rows for the current viewport width (after a resize)."""
        if self.closed:
            return
        try:
            if self.model.set_wrap_width(self._wrap_units()):
                self._relayout()
        except Exception as error:
            self.fail(error)

    def _scroll_values(self) -> tuple[Any, Any]:
        return self.scroll.horizontalScrollBar().value, self.scroll.verticalScrollBar().value

    def _restore_scroll(self, values: tuple[Any, Any]) -> None:
        self.scroll.horizontalScrollBar().setValue(values[0])
        self.scroll.verticalScrollBar().setValue(values[1])

    def _relayout(self) -> None:
        values = self._scroll_values()
        try:
            self.layout_geometry = self.model.geometry(self._viewport_width())
            self.canvas.resize(int(self.layout_geometry.width), int(self.layout_geometry.height))
            self._show_selection()
        finally:
            self._restore_scroll(values)

    def _show_selection(self) -> None:
        glyph = self.model.glyph_readout()
        pair = self.model.pair_readout() if self._current_master() else None
        self.kern_control.setEnabled(self._current_master() and not self.read_only)
        self.readout.setText(glyph.text() if glyph else "")
        self.pair_readout.setText(pair.text() if pair else "")
        values = {"lsb": glyph.lsb, "rsb": glyph.rsb, "width": glyph.advance} if glyph else {}
        for metric, control in self.metric_controls.items():
            value = values.get(metric)
            control.setText("" if value is None else number_text(value))
        self.kern_control.setText(number_text(pair.value) if pair else "")
        state = self.hint_state() if glyph else None
        for metric in ("lsb", "rsb"):
            self.metric_controls[metric].setEnabled(not state)
        if state:
            self.diagnostic.setText(state.text())
        self.canvas.update()

    def set_text(self, text: str) -> None:
        """Show ``text`` (characters or /names) and reshape, as ``TMetrics(text=...)`` does."""
        if self.closed:
            return
        generation = self._refresh_generation
        self.text_control.setText(text)
        # Changed text refreshes synchronously through the owned textChanged slot.
        if self._refresh_generation == generation:
            self.refresh()

    def set_view(self, size: float | None = None, kerning: bool | None = None) -> float:
        """Set the drawing size (px/em, clamped to 8..512) and the kerning toggle; reshape once.

        ``None`` leaves that setting as it is. Return the size in effect.
        """
        if self.closed:
            return float(self.size_control.value)
        for control in (self.size_control, self.kerning_control):
            control.blockSignals(True)
        try:
            if size is not None:
                self.size_control.setValue(int(round(min(max(float(size), 8.0), 512.0))))
            if kerning is not None:
                self.kerning_control.setChecked(bool(kerning))
        finally:
            for control in (self.size_control, self.kerning_control):
                control.blockSignals(False)
        self._reshape()
        return float(self.size_control.value)

    def set_layer(self, layer: str | None) -> None:
        """Make ``layer`` the explicit target of later writes and recheck the hint guard."""
        if self.closed:
            return
        self.layer = layer
        self.model.layer = layer
        self._fill_layers()
        self.refresh()

    def highlight_cell(self, index: int) -> bool:
        """Select the glyph cell at ``index`` in the shaped line; True when it exists."""
        if self.closed or not 0 <= index < len(self.model.cells):
            return False
        self.model.select(index)
        self._show_selection()
        self._reveal()
        return True

    def highlight_pair(self, left: str, right: str) -> bool:
        """Select the first ``left`` glyph followed by ``right``; True when found."""
        cells = self.model.cells
        for index in range(len(cells) - 1):
            if cells[index].name == left and cells[index + 1].name == right:
                return self.highlight_cell(index + 1)
        return False

    def _reveal(self) -> None:
        cell = self.model.selected_cell()
        if cell is None:
            return
        origins = self.layout_geometry.origins
        if cell.index >= len(origins):
            return
        x, _baseline = origins[cell.index]
        top = self.layout_geometry.row_top(cell.row)
        self.scroll.ensureVisible(int(x), int(top + self.layout_geometry.row_height / 2))

    def select_at(self, x: float, y: float) -> None:
        """Select the glyph under canvas pixel ``(x, y)``; a miss keeps the selection."""
        if self.closed:
            return
        index = self.model.cell_at(self.layout_geometry, x, y)
        if index is not None and self.model.select(index):
            self._show_selection()

    def select_key(self, key: Any) -> bool:
        """Move the selection for Left/Right/Home/End; return True when handled."""
        if self.closed:
            return False
        for name, step in KEY_STEPS.items():
            if key == getattr(QtCore.Qt, name, None):
                try:
                    handled = self.model.move(step)
                    if handled:
                        self._show_selection()
                        self._reveal()
                except Exception as error:
                    self.fail(error)
                    return False
                return handled
        return False

    def open_at(self, x: float, y: float) -> None:
        """Call ``on_open_glyph(name)`` for the glyph under ``(x, y)``; errors go to the status."""
        if self.closed:
            return
        index = self.model.cell_at(self.layout_geometry, x, y)
        if index is None:
            return
        self.model.select(index)
        self._show_selection()
        cell = self.model.cells[index]
        if self.on_open_glyph is None or not cell.present:
            return
        try:
            self.on_open_glyph(cell.name)
        except Exception as error:
            self.fail(error)

    def close(self) -> None:
        """Drop the callback and the font, then disconnect everything owned."""
        if self._close_complete:
            return
        self.on_open_glyph = None
        self.outlines = {}
        super().close()


def _has(modifiers: Any, name: str) -> bool:
    """True when Qt keyboard ``modifiers`` include ``QtCore.Qt.<name>``."""
    flag = getattr(QtCore.Qt, name, None)
    try:
        return bool(int(modifiers) & int(flag))
    except (TypeError, ValueError):
        return False


def _pending_note() -> str:
    """Disclose FontLab's queued glyph updates before a write; empty offline."""
    try:
        import fontlabapp.core.edit_guards as edit_guards

        return edit_guards.pending_note(edit_guards.pending_updates())
    except Exception:
        return ""


def _outline(model: Any, name: str) -> Any | None:
    try:
        return model.outline_of(model.source, name)
    except Exception:
        return None


def create_canvas(owner: TMetrics, parent: Any) -> Any:
    """Return the TMetrics canvas widget; it paints and forwards input to ``owner``."""

    class Canvas(QtGui.QWidget):
        def paintEvent(self, event: Any) -> None:
            paint(owner, self)

        def mousePressEvent(self, event: Any) -> None:
            try:
                self.setFocus()
                owner.select_at(event.pos().x(), event.pos().y())
            except Exception as error:
                owner.fail(error)
            event.accept()

        def mouseDoubleClickEvent(self, event: Any) -> None:
            try:
                owner.open_at(event.pos().x(), event.pos().y())
            except Exception as error:
                owner.fail(error)
            event.accept()

        keyPressEvent = key_press_handler(
            QtGui.QWidget, lambda widget, event: owner.key_press(event.key(), event.modifiers())
        )

    canvas = Canvas(parent)
    canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
    return canvas


def _pen(color: str, width: float = 1.0) -> Any:
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(width)
    return pen


def paint(owner: TMetrics, canvas: Any) -> None:
    """Paint guides, boxes, bearings, kerning, selection and outlines; never raise."""
    painter = None
    try:
        painter = QtGui.QPainter(canvas)
        geometry, model = owner.layout_geometry, owner.model
        colors = _canvas_colors(canvas, COLORS)
        painter.fillRect(canvas.rect, QtGui.QColor(colors["background"]))
        for row in range(model.rows):
            _paint_guides(painter, geometry, model, row, colors)
        prepared: dict[int, list[tuple[Any, bool]]] = {}
        for cell, origin in zip(model.cells, geometry.origins, strict=False):
            _paint_cell(painter, owner, geometry, cell, origin, cell.index == model.selected, colors, prepared)
        # Draw after all cell backgrounds, which overlap negative kerning spans.
        for cell, (x, baseline) in zip(model.cells, geometry.origins, strict=False):
            if cell.kern:
                color = colors["kern_negative" if cell.kern < 0 else "kern_positive"]
                start, span = x + cell.width * geometry.scale, cell.kern * geometry.scale
                painter.fillRect(QtCore.QRectF(min(start, start + span), baseline, abs(span), BEARING_TICK), QtGui.QColor(color))
    except Exception as error:
        owner.fail(error)
    finally:
        if painter is not None:
            painter.end()


def _paint_guides(painter: Any, geometry: Any, model: TMetricsModel, row: int, colors: dict[str, str]) -> None:
    baseline = geometry.row_top(row) + model.metrics.top * geometry.scale
    for label, y in model.metrics.lines():
        painter.setPen(_pen(colors["baseline" if label == "baseline" else "guide"]))
        level = baseline - y * geometry.scale
        painter.drawLine(QtCore.QLineF(0, level, geometry.width, level))


def _paint_cell(painter: Any, owner: TMetrics, geometry: Any, cell: Any, origin: Any, selected: bool, colors: dict[str, str], prepared: dict[int, list[tuple[Any, bool]]]) -> None:
    x, baseline = origin
    scale, metrics = geometry.scale, owner.model.metrics
    top = baseline - metrics.top * scale
    height = (metrics.top - metrics.bottom) * scale
    box = QtCore.QRectF(x, top, cell.width * scale, height)
    painter.fillRect(box, QtGui.QColor(colors["selection_background" if selected else "box"]))
    painter.setPen(_pen(colors["guide"]))
    painter.drawRect(box)
    if cell.lsb is not None and cell.rsb is not None:
        painter.setPen(_pen(colors["bearing"], 2.0))
        right = x + cell.width * scale
        painter.drawLine(QtCore.QLineF(x, baseline + BEARING_TICK, x + cell.lsb * scale, baseline + BEARING_TICK))
        painter.drawLine(QtCore.QLineF(right - cell.rsb * scale, baseline + BEARING_TICK, right, baseline + BEARING_TICK))
    shape = owner.outlines.get(cell.name)
    if shape is None:
        painter.setPen(_pen(colors["selection_foreground" if selected else "missing"]))
        painter.drawText(box, QtCore.Qt.AlignCenter, cell.name)
        return
    _paint_outline(painter, shape, x + cell.x_offset * scale, baseline - cell.y_offset * scale, scale, colors["selection_foreground" if selected else "glyph"], prepared)


def _paint_outline(painter: Any, shape: Any, x: float, baseline: float, scale: float, color: str, prepared: dict[int, list[tuple[Any, bool]]]) -> None:
    from fontTools.pens.qtPen import QtPen
    from fontTools.pens.recordingPen import replayRecording

    painter.save()
    try:
        painter.translate(x, baseline)
        painter.scale(scale, -scale)
        painter.setPen(_pen(color, 1.0 / scale))
        key = id(shape.recording)
        if key not in prepared:
            closed, opened = partition_paths(shape.recording)
            paths = []
            for recording, filled in ((closed, True), (opened, False)):
                if not recording:
                    continue
                path = QtGui.QPainterPath()
                path.setFillRule(QtCore.Qt.WindingFill)
                replayRecording(recording, QtPen(None, path=path))
                paths.append((path, filled))
            prepared[key] = paths
        for path, filled in prepared[key]:
            painter.setBrush(QtGui.QBrush(QtGui.QColor(color)) if filled else QtGui.QBrush())
            painter.drawPath(path)
    finally:
        painter.restore()


_WORLD: list[Any] = []


def _current_font() -> Any | None:
    """Return FontLab's current font as a live Fontport RFont, or None."""
    with require_fontport(__name__):
        from fontlab_fontport.world import FontWorld
    if not _WORLD:
        _WORLD.append(FontWorld())
    return _WORLD[0].CurrentFont()


def _notify(text: str) -> None:
    """Show ``text`` in a modal message box; print it when Qt or FontLab refuses."""
    try:
        import fontlab

        from fontlabapp.qt.dialogs import create_message_box, run_message_box

        box = create_message_box(QtGui, TITLE, text, "Information", (fontlab.MainWindow(),))
        run_message_box(box, QtGui.QMessageBox.Ok)
    except Exception:
        print(f"{TITLE}: {text}")


def show_tmetrics(
    font: Any = None, text: str | None = None, *, parent: Any = None, on_open_glyph: Any = None
) -> TMetrics | None:
    """Open TMetrics over ``font`` (default: FontLab's current font) and return it.

    Returns None, after a message, when no font is open or Fontport cannot
    resolve one.
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
    window = TMetrics(font, parent, on_open_glyph, text)
    if on_open_glyph is None:
        window.on_open_glyph = lambda name: open_tglyph(window, name)
    try:
        window.widget.setWindowTitle(TITLE)
        window.widget.resize(900, 520)
        window.widget.show()
    except Exception:
        window.close()
        raise
    return window


def open_tglyph(window: TMetrics, name: str) -> Any:
    """Show ``name`` of ``window.font`` in TGlyph, reusing the window's open TGlyph.

    The TGlyph window is kept on ``window.tglyph`` so PythonQt does not collect
    it; a closed one is replaced. TGlyph is imported here, not at module load.
    """
    from .tglyph import show_tglyph

    viewer = getattr(window, "tglyph", None)
    if viewer is not None and not viewer.closed and viewer.font is window.font:
        viewer.load(name)
        viewer.widget.show()
        viewer.widget.raise_()
        return viewer
    window.tglyph = show_tglyph(window.font, name)
    return window.tglyph
