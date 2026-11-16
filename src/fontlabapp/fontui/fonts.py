# this_file: src/fontlabapp/fontui/fonts.py
# SPDX-License-Identifier: Apache-2.0
"""Original explicit-list font browser composed with the glyph controls."""

from PythonQt import QtGui

from fontlabapp.fontui.lifecycle import Owned, follow_changes
from fontlabapp.fontui.model import FontListState
from fontlabapp.fontui.native import Browser


class FontBrowser(Owned):
    def __init__(self, fonts=(), parent=None, on_activate=None, follow=True):
        super().__init__(parent)
        self.state = FontListState(fonts)
        self.count_label = QtGui.QLabel(self.widget)
        self.layout.addWidget(self.count_label)
        sort_button = QtGui.QPushButton("Sort fonts by name", self.widget)
        self.layout.addWidget(sort_button)
        self.font_list = QtGui.QListWidget(self.widget)
        self.font_list.setAccessibleName("Fonts")
        self.layout.addWidget(self.font_list)
        from . import _construct

        self.browser = _construct(Browser, None, self.widget, on_activate, False, False)
        self.layout.addWidget(self.browser.widget)
        self.connect(sort_button.clicked, lambda *args: self.sort())
        self.connect(self.font_list.currentRowChanged, self.select)
        self.refresh()
        if follow:
            follow_changes(self, self.refresh, lambda: self.state.fonts)

    def refresh(self, fonts=None):
        if self.closed:
            return
        self.state.refresh(self.state.fonts if fonts is None else fonts)
        self.font_list.blockSignals(True)
        try:
            self.font_list.clear()
            self.font_list.addItems(list(self.state.labels))
            self.font_list.setCurrentRow(
                -1 if self.state.index is None else self.state.index
            )
        finally:
            self.font_list.blockSignals(False)
        self.count_label.setText(f"{len(self.state.fonts)} fonts")
        self._update_browser()

    def _update_browser(self):
        font = self.state.selected
        if self.browser.state.font is not font:
            self.browser.state.selected = ()
        self.browser.state.font = self.browser.preview.font = font
        self.browser.widget.setEnabled(font is not None)
        self.browser.refresh()

    def select(self, index):
        if self.closed:
            return
        self.state.select(None if index < 0 else index)
        self._update_browser()

    def sort(self):
        if self.closed:
            return
        self.state.sort()
        self.refresh()

    def close(self):
        return self._close_with_child(getattr(self, "browser", None))
