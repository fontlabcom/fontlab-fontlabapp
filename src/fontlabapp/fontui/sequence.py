# this_file: src/fontlabapp/fontui/sequence.py
# SPDX-License-Identifier: Apache-2.0
"""Original sequence controls; Fontport owns Unicode/kerning placement."""

from typing import Any
from weakref import ref as _ref

from ._fontport import require_fontport

with require_fontport(__name__):
    from fontlab_fontport.designspace import Designspace as Designspace  # noqa: PLC0414 - public re-export
    from fontlab_fontport.glyphrun import layout_names, layout_text
    from fontlab_fontport.host import NativeFontBackend as NativeFontBackend  # noqa: PLC0414 - public re-export
    from fontlab_fontport.live import RFont as RFont  # noqa: PLC0414 - public re-export
from PythonQt import QtCore, QtGui

from .lifecycle import Owned, follow_changes, native_ids
from fontlabapp.qt.compact import MARGIN, compact_layout
from .model import outline
from .sequence_canvas import create_canvas, prepare, reveal


def _identity(glyph: Any) -> Any:
    """FontParts recreates wrappers; retain the actual underlying glyph identity."""
    naked = getattr(glyph, "naked", None)
    return naked() if callable(naked) else glyph


class Sequence(Owned):
    """Show a glyph run for typed text or ``/glyph`` names; select one glyph.

    Fontport (``fontlab_fontport.glyphrun``) places the glyphs, with Unicode
    mapping and kerning. The canvas and the key and wrap helpers come from
    ``fontlabapp.fontui``. The font is borrowed. Selection follows the
    underlying glyph, not the FontParts wrapper, so it survives a refresh.
    """

    def __init__(
        self,
        font: Any,
        parent: Any = None,
        on_select: Any = None,
        on_update: Any = None,
    ) -> None:
        super().__init__(parent)
        # FontLab panel metrics, issue 253. Embedded in a host window the host's
        # own compact margin already frames the preview: no second inset.
        compact_layout(self.layout, margin=0 if parent is not None else MARGIN)
        self.font: Any = font
        self.on_select: Any = on_select
        self.on_update: Any = on_update
        self.run: Any = None
        self.outlines: dict[Any, Any] = {}
        self.selected_index: int | None = None
        self.positions: list[tuple[float, int]] = []
        self.line_height: float = 0.0
        self.wrap_width: float | None = None
        self._selected_font: Any = None
        self._selected_glyph: Any = None
        self._pending_selection: Any = None
        self._controls()
        self._canvas()
        self.refresh()
        follow_changes(self, self.refresh, lambda: [self.font])

    def _controls(self) -> None:
        """Build the text field, toolbar and status label; connect refreshes."""
        self.text_control = QtGui.QLineEdit(self.widget)
        label = QtGui.QLabel("Sequence text or /glyph names", self.widget)
        label.setBuddy(self.text_control)
        self.layout.addWidget(label)
        self.layout.addWidget(self.text_control)
        toolbar = QtGui.QHBoxLayout()
        self.layout.addLayout(toolbar)
        self._modes(toolbar)
        self._size_and_kerning(toolbar)
        self.diagnostic = QtGui.QLabel(self.widget)
        self.layout.addWidget(self.diagnostic)
        self.connect(self.text_control.textChanged, self.refresh)
        self.connect(self.mode_control.currentIndexChanged, self.refresh)
        self.connect(self.direction_control.currentIndexChanged, self.refresh)

    def _modes(self, toolbar: Any) -> None:
        """Add the input-mode and reading-direction combo boxes."""
        self.mode_control = QtGui.QComboBox(self.widget)
        self.mode_control.addItems(["Text", "Glyph names"])
        self.mode_control.setAccessibleName("Sequence input mode")
        toolbar.addWidget(self.mode_control)
        self.direction_control = QtGui.QComboBox(self.widget)
        self.direction_control.addItems(["Left to right", "Right to left"])
        self.direction_control.setAccessibleName("Reading direction")
        toolbar.addWidget(self.direction_control)

    def _size_and_kerning(self, toolbar: Any) -> None:
        """Add the size, kerning and wrap controls; connect refreshes."""
        self.size_control = QtGui.QSpinBox(self.widget)
        self.size_control.setRange(8, 512)
        self.size_control.setValue(72)
        self.size_control.setSuffix(" px/em")
        self.size_control.setAccessibleName("Glyph size in pixels per em")
        toolbar.addWidget(self.size_control)
        self.kerning_control = QtGui.QCheckBox("Apply kerning", self.widget)
        self.kerning_control.setChecked(True)
        toolbar.addWidget(self.kerning_control)
        self.wrap_control = QtGui.QCheckBox("&Wrap lines", self.widget)
        self.wrap_control.setToolTip(
            "Wrap at the view width when the text changes or this is toggled"
        )
        toolbar.addWidget(self.wrap_control)
        self.connect(self.size_control.valueChanged, self.refresh)
        self.connect(self.kerning_control.toggled, self.refresh)
        self.connect(self.wrap_control.toggled, self.refresh)

    def _canvas(self) -> None:
        """Build the scroll area and canvas; viewport resizes queue a reflow."""
        owner_ref = _ref(self)

        class Scroll(QtGui.QScrollArea):
            def viewportEvent(self, event: Any) -> bool:
                # Resizes include scroll bars appearing or disappearing.
                owner = owner_ref()
                if owner is not None and event.type() == QtCore.QEvent.Resize:
                    owner.reflow_timer.start()
                return QtGui.QScrollArea.viewportEvent(self, event)

        self.reflow_timer = QtCore.QTimer(self.widget)
        self.reflow_timer.setSingleShot(True)
        self.reflow_timer.setInterval(0)
        self.connect(self.reflow_timer.timeout, lambda *args: self._reflow())
        self.scroll = Scroll(self.widget)
        self.canvas = create_canvas(self, self.scroll)
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)
        self.layout.addWidget(self.scroll)

    def _reflow(self) -> None:
        """Wrap again after the view width changed; outside the resize event."""
        if self.closed or not self.wrap_control.checked or self.run is None:
            return
        if self.scroll.viewport().width != self.wrap_width:
            self.refresh()

    def _kerning_capability(self) -> None:
        """Disable and uncheck Apply kerning when the font has no kerning."""
        reason = ""
        try:
            if self.font is None:
                raise ValueError("No font supplied")
            _ = self.font.kerning, self.font.groups
        except Exception as error:  # noqa: BLE001 - optional backend capability boundary
            reason = f"Kerning unavailable: {error}"
        self.kerning_control.setEnabled(not reason)
        self.kerning_control.setToolTip(reason)
        if reason:
            blocked = self.kerning_control.blockSignals(True)
            try:
                self.kerning_control.setChecked(False)
            finally:
                self.kerning_control.blockSignals(blocked)

    def _invalidate_for_refresh(self) -> None:
        """Clear visible proof while retaining only its selected occurrence."""
        if self.closed:
            return
        if self.run is not None:
            self._pending_selection = (
                self.run.glyphs[self.selected_index]
                if self.selected_index is not None else None
            )
        self.run, self.outlines, self.selected_index = None, {}, None

    def refresh(self, *args: Any) -> None:
        if self.closed:
            return
        self._invalidate_for_refresh()
        selected, self._pending_selection = self._pending_selection, None
        self._kerning_capability()
        try:
            self._load_run()
            if selected is not None and self.font is self._selected_font:
                # FontLab-backed fonts rewrap glyphs after each invalidation and
                # expose no native glyph identity: keep the selection by font,
                # index, name and label. Detached models keep object identity,
                # so a different glyph under the same name drops it.
                by_name = bool(native_ids([self.font]))
                for occurrence in self.run.glyphs:
                    same = (occurrence.index, occurrence.name, occurrence.label) == (
                        selected.index,
                        selected.name,
                        selected.label,
                    )
                    if same and (
                        occurrence.name is None
                        or by_name
                        or _identity(self.font[occurrence.name]) is self._selected_glyph
                    ):
                        self.selected_index = occurrence.index
                        reveal(self, occurrence)
                        break
        except Exception as error:  # noqa: BLE001 - show model/layout failures in owned UI
            self.fail(error)
        else:
            self._notify_update()
        self.canvas.update()

    def _load_run(self) -> None:
        """Lay out the text or names, load outlines and show the diagnostics."""
        if self.font is None:
            raise ValueError("No font supplied")
        layout = layout_names if self.mode_control.currentIndex else layout_text
        self.run = layout(
            self.font,
            str(self.text_control.text),
            kerning=bool(self.kerning_control.checked),
            direction="rtl" if self.direction_control.currentIndex else "ltr",
        )
        self.outlines = {
            g.name: outline(self.font, g.name)
            for g in self.run.glyphs
            if g.name is not None
        }
        prepare(self)
        status = "Unicode lookup; no shaping" if self.run.glyphs else "No preview text"
        self.diagnostic.setText("; ".join(self.run.diagnostics) or status)

    def _notify_update(self) -> None:
        """Publish final layout state without changing selection callback semantics."""
        callback = getattr(self, "on_update", None)
        if self.closed or callback is None:
            return
        diagnostic = str(self.diagnostic.text)
        try:
            callback(self)
        except Exception as error:  # noqa: BLE001 - consumer failures must not recursively call fail
            self.diagnostic.setText(f"{diagnostic}; Update callback failed: {error}")

    def fail(self, error: Exception) -> None:
        if self.closed:
            return
        self._pending_selection = None
        self.run, self.outlines, self.selected_index = None, {}, None
        self.diagnostic.setText(str(error))
        self._notify_update()

    def select_at(self, pixel_x: float, pixel_y: float | None = None) -> None:
        if self.closed or self.run is None:
            return
        x = (pixel_x - self.origin_x) / self.scale
        line = 0
        if pixel_y is not None and self.line_height > 0:  # rows start at y 10
            line = max(0, int((pixel_y - 10) // self.line_height))
        for occurrence in reversed(self.run.glyphs):
            start, row = self.positions[occurrence.index]
            low, high = sorted(
                (start, start + occurrence.advance)
            )  # advance may be < 0
            if row != line or not low <= x <= high:
                continue
            self._select_occurrence(occurrence)
            return

    def _select_occurrence(self, occurrence: Any) -> None:
        """Select one placed glyph, reveal it, then call ``on_select``."""
        try:
            glyph = self.font[occurrence.name] if occurrence.name is not None else None
        except Exception as error:  # noqa: BLE001 - resolve model before consumer callback
            self.fail(error)
            self.canvas.update()
            return
        self.selected_index = occurrence.index
        self._selected_font = self.font
        self._selected_glyph = _identity(glyph)
        reveal(self, occurrence)
        self.canvas.update()
        if self.on_select is not None:
            self.on_select(glyph, occurrence.index)

    def select_key(self, key: int) -> bool:
        keys = (
            QtCore.Qt.Key_Left,
            QtCore.Qt.Key_Right,
            QtCore.Qt.Key_Home,
            QtCore.Qt.Key_End,
        )
        if self.closed or self.run is None or not self.run.glyphs or key not in keys:
            return False
        index = self.selected_index
        if key == QtCore.Qt.Key_End:
            index = len(self.run.glyphs) - 1
        elif key == QtCore.Qt.Key_Home or index is None:
            index = 0
        else:
            step = 1 if key == QtCore.Qt.Key_Right else -1
            index += step if self.run.direction == "ltr" else -step
        index = max(0, min(index, len(self.run.glyphs) - 1))
        self._select_occurrence(self.run.glyphs[index])
        return True

    def close(self) -> None:
        self._pending_selection = None
        self.on_update = None
        self.on_select = None
        self._selected_font, self._selected_glyph = None, None
        super().close()
