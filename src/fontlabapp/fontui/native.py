# this_file: src/fontlabapp/fontui/native.py
# SPDX-License-Identifier: Apache-2.0
"""Original glyph collection and name-based selection."""

import logging

from PythonQt import QtCore, QtGui

from fontlabapp.qt.events.key import key_press_handler
from fontlabapp.fontui.lifecycle import Owned, follow_changes
from fontlabapp.fontui.model import BrowserState, outline, partition_paths, viewport
from fontlabapp.fontui.preview import Preview
from fontlabapp.qt.properties import value as qt_value

# Thumbnails paint lazily: a few dozen per idle turn, only near the viewport.
ICON_BATCH = 32
ICON_MARGIN = 32
ICON_FALLBACK_ROWS = 64
# Without geometry, paint this many rows centred on the current or scrolled row.
ICON_BLIND_ROWS = 256

LOG = logging.getLogger(__name__)
# PythonQt geometry reads fail as missing attributes, bad overloads or deleted objects.
GEOMETRY_ERRORS = (AttributeError, TypeError, ValueError, RuntimeError)


class Browser(Owned):
    def __init__(
        self,
        font,
        parent=None,
        on_activate=None,
        multiple=False,
        follow=True,
        on_selection=None,
    ):
        super().__init__(parent)
        self.layout.setContentsMargins(0, 0, 0, 0)
        body = QtGui.QHBoxLayout()
        self.layout.addLayout(body)
        controls = QtGui.QWidget(self.widget)
        self.controls_layout = QtGui.QVBoxLayout(controls)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        body.addWidget(controls, 1)
        self.state = BrowserState(font)
        self.on_activate = on_activate
        self.on_selection = on_selection
        self.filter_control = QtGui.QLineEdit(self.widget)
        self.filter_control.setPlaceholderText("Find glyphs")
        self.filter_control.setAccessibleName("Filter glyph names")
        search = QtGui.QHBoxLayout()
        search.addWidget(self.filter_control)
        self.controls_layout.addLayout(search)
        self.count_label = QtGui.QLabel(self.widget)
        display = search
        display.addWidget(self.count_label)
        self.mode_control = QtGui.QComboBox(self.widget)
        self.mode_control.addItems(["List", "Grid"])
        display.addWidget(self.mode_control)
        self.size_control = QtGui.QSpinBox(self.widget)
        self.size_control.setRange(40, 240)
        self.size_control.setValue(96)
        self.size_control.setAccessibleName("Glyph cell size")
        display.addWidget(self.size_control)
        owner = self

        def activate_key(widget, event):
            if event.key() not in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                return False
            owner.activate(widget.currentItem())
            return True

        class GlyphList(QtGui.QListWidget):
            keyPressEvent = key_press_handler(QtGui.QListWidget, activate_key)

            def resizeEvent(widget, event):
                QtGui.QListWidget.resizeEvent(widget, event)
                owner._schedule_icons()

        self.glyph_list = GlyphList(self.widget)
        self.glyph_list.setSelectionMode(
            QtGui.QAbstractItemView.ExtendedSelection
            if multiple
            else QtGui.QAbstractItemView.SingleSelection
        )
        self.selection_layout = QtGui.QVBoxLayout()
        self.selection_layout.addWidget(self.glyph_list, 1)
        self.controls_layout.addLayout(self.selection_layout, 1)
        from . import _construct

        self.preview = _construct(Preview, font, None, self.widget, False)
        body.addWidget(self.preview.widget, 1)
        self.connect(self.filter_control.textChanged, self.filter)
        self.connect(self.mode_control.currentIndexChanged, self.set_mode)
        self.connect(self.size_control.valueChanged, self.set_size)
        self.connect(self.glyph_list.itemSelectionChanged, self.selection_changed)
        self.connect(self.glyph_list.itemDoubleClicked, self.activate)
        self.icons, self._iconed = {}, set()
        self.icon_timer = QtCore.QTimer(self.widget)
        self.icon_timer.setSingleShot(True)
        self.icon_timer.setInterval(0)
        self.connect(self.icon_timer.timeout, self._render_icons)
        scroll = getattr(self.glyph_list, "verticalScrollBar", None)
        scroll = scroll() if callable(scroll) else None
        if scroll is not None:
            self.connect(scroll.valueChanged, self._schedule_icons)
        else:
            LOG.warning("Glyph list has no vertical scroll bar; thumbnails update on resize only")
        self.refresh()
        if follow:
            follow_changes(self, self._changed, lambda: [self.state.font])

    def _changed(self):
        """FontLab changed a document: rebuild the list and the preview."""
        self.refresh()

    def refresh(self):
        if self.closed:
            return
        self.preview.font = self.state.font
        self.icons = {}
        self.state.refresh()
        self.rebuild()

    def filter(self, text):
        if self.closed:
            return
        self.state.filter(text)
        self.rebuild()

    def rebuild(self):
        self.count_label.setToolTip(self.state.error or "")
        self.glyph_list.blockSignals(True)
        try:
            self.glyph_list.clear()
            self._iconed = set()
            for name in self.state.names:
                item = QtGui.QListWidgetItem(name)
                self.glyph_list.addItem(item)
                item.setSelected(name in self.state.selected)
        finally:
            self.glyph_list.blockSignals(False)
        self._schedule_icons()
        self.count_label.setText(f"{len(self.state.names)} glyphs")
        self.glyph_list.setEnabled(self.state.font is not None and not self.state.error)
        self.selection_changed()
        if self.state.error:
            self.preview.diagnostic.setText(self.state.error)

    def _schedule_icons(self, *args):
        timer = getattr(self, "icon_timer", None)
        if timer is not None and not self.closed:
            timer.start()

    def _visible_rows(self):
        """Binary-search item rectangles against the viewport; gaps and scroll position do not matter.

        Rows lay out in order in list and grid mode, so item tops never decrease with the row.
        """
        names = len(self.state.names)
        glyphs = self.glyph_list
        try:
            height = int(qt_value(qt_value(qt_value(glyphs, "viewport"), "rect"), "height"))
            count = min(names, int(qt_value(glyphs, "count")))

            def edges(row):
                rect = glyphs.visualItemRect(glyphs.item(row))
                return int(qt_value(rect, "top")), int(qt_value(rect, "bottom"))

            def search(test):
                low, high = 0, count
                while low < high:
                    middle = (low + high) // 2
                    low, high = (middle + 1, high) if test(middle) else (low, middle)
                return low

            first = search(lambda row: edges(row)[1] < 0)
            last = search(lambda row: edges(row)[0] < height) - 1
        except GEOMETRY_ERRORS as error:
            return self._blind_rows(names, error)
        if last < first:
            return range(min(count, ICON_FALLBACK_ROWS))
        return range(max(0, first - ICON_MARGIN), min(count, last + ICON_MARGIN + 1))

    def _blind_rows(self, names, error):
        """Geometry failed: log once, then paint a window around the current or scrolled row."""
        if not getattr(self, "_geometry_logged", False):
            self._geometry_logged = True
            LOG.warning("Glyph list geometry unavailable (%s: %s); painting rows near the current row",
                        type(error).__name__, error)
        centre = 0
        for read in (lambda: self.glyph_list.currentRow(), lambda: self.glyph_list.verticalScrollBar().value()):
            try:
                row = read()
            except GEOMETRY_ERRORS:
                continue
            if isinstance(row, int) and not isinstance(row, bool) and row >= 0:
                centre = row
                break
        first = max(0, min(centre - ICON_BLIND_ROWS // 2, names - ICON_BLIND_ROWS))
        return range(first, min(names, first + ICON_BLIND_ROWS))

    def _render_icons(self):
        if self.closed:
            return
        painted = 0
        for row in self._visible_rows():
            if row in self._iconed:
                continue
            name = self.state.names[row]
            icon = self.icons.get(name)
            if icon is None:
                if painted >= ICON_BATCH:
                    self.icon_timer.start()
                    return
                icon = self.icons[name] = self.thumbnail(name)
                painted += 1
            self.glyph_list.item(row).setIcon(icon)
            self._iconed.add(row)

    def thumbnail(self, name):
        from fontTools.pens.qtPen import QtPen
        from fontTools.pens.recordingPen import replayRecording

        pixmap = QtGui.QPixmap(80, 80)
        pixmap.fill(QtGui.QColor("white"))
        painter = QtGui.QPainter(pixmap)
        try:
            data = outline(self.state.font, name)
            scale, x, y = viewport(data.bounds, data.width, -200, 800, 80, 80)
            painter.translate(x, y)
            painter.scale(scale, -scale)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#303030")))
            path = QtGui.QPainterPath()
            path.setFillRule(QtCore.Qt.WindingFill)
            closed, opened = partition_paths(data.recording)
            replayRecording(closed, QtPen(None, path=path))
            painter.drawPath(path)
            path = QtGui.QPainterPath()
            replayRecording(opened, QtPen(None, path=path))
            painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
            pen = QtGui.QPen(QtGui.QColor("#303030"))
            pen.setWidthF(1 / scale)
            painter.setPen(pen)
            painter.drawPath(path)
        except Exception as error:  # noqa: BLE001 - backend/paint boundary retains diagnostic
            item_error = str(error)
            painter.resetTransform()
            painter.setPen(QtGui.QPen(QtGui.QColor("red")))
            painter.drawText(4, 40, "!")
            self.count_label.setToolTip(item_error)
        finally:
            painter.end()
        return QtGui.QIcon(pixmap)

    def selection_changed(self):
        if self.closed:
            return
        # Iteration by row avoids converting native widget lists.
        names = [
            self.glyph_list.item(i).text()
            for i in range(len(self.state.names))
            if self.glyph_list.item(i).isSelected()
        ]
        self.state.select(names)
        self.preview.set_glyph(self.state.selected[0] if self.state.selected else None)
        callback = getattr(self, "on_selection", None)
        if callback is not None:
            try:
                callback(self.state.font, tuple(self.state.selected))
            except Exception as error:  # consumer diagnostic, not a font failure
                self.preview.diagnostic.setText(f"Selection callback failed: {error}")

    def activate(self, item, *args):
        if self.closed or item is None or self.on_activate is None:
            return
        name = str(item.text())
        if name not in self.state.names:
            return
        try:
            if self.state.font is None or name not in self.state.font:
                raise ValueError(f"Missing component or glyph: {name}")
            glyph = self.state.font[name]
        except Exception as error:  # noqa: BLE001 - backend boundary retains diagnostic
            self.state.error = str(error)
            self.state.original = self.state.names = self.state.selected = ()
            self.rebuild()
            return
        # Consumer failures must not be misreported as unavailable font data.
        self.on_activate(glyph)

    def set_mode(self, index):
        if self.closed:
            return
        self.state.mode = "grid" if index else "list"
        self.glyph_list.setViewMode(
            QtGui.QListView.IconMode if index else QtGui.QListView.ListMode
        )
        self.set_size(self.state.cell_size)

    def set_size(self, value):
        if self.closed:
            return
        self.state.cell_size = int(value)
        self.glyph_list.setIconSize(
            QtCore.QSize(max(16, value - 24), max(16, value - 24))
        )
        self.glyph_list.setGridSize(
            QtCore.QSize(value, value if self.state.mode == "grid" else 30)
        )
        self._schedule_icons()

    def close(self):
        self.on_selection = None
        self.on_activate = None
        return self._close_with_child(getattr(self, "preview", None))
