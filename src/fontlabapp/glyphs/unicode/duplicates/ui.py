# this_file: src/fontlabapp/glyphs/unicode/duplicates/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Complete checkbox cleanup editor with owned, deferred native lifetime."""

import sys
from typing import Any

from fontlabapp import _native
from fontlabapp.glyphs.unicode.duplicates.tree import populate, publish_result, update
from fontlabapp.core.signals.scope import Scope
from fontlabapp.glyphs.unicode.duplicates.model import KEY, TITLE
from fontlabapp.glyphs.unicode.duplicates.native import Backend
from fontlabapp.qt.properties import value
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import close_script_dialog


def dialog_type(qt: Any = None) -> type:
    """Bind actual PythonQt lazily, or inject a real standalone Qt for tests."""
    qt = _native("PythonQt") if qt is None else qt
    core, gui = qt.QtCore, qt.QtGui

    class Dialog(gui.QDialog):
        """Whole-font editable preview; only Apply invokes the precise writer."""

        def __init__(self, parent: Any = None, *, backend: Any = None) -> None:
            """Retain all source controls and initialize after owned lifetime setup."""
            gui.QDialog.__init__(self, parent)
            self.backend = Backend() if backend is None else backend
            self._connections, self.items = [], {}
            self.facts = None
            self._closed = self._closing = self._dead = self._busy = False
            self.signals = Scope(self.failure)
            self._completion_lifetime = install(self, KEY)
            self._completion_lifetime.on_destroyed.append(self.destroyed_owned)
            try:
                self.setWindowTitle(TITLE)
                palette = value(self, "palette")
                palette.setColor(
                    gui.QPalette.Text, palette.color(gui.QPalette.WindowText)
                )
                self.setPalette(palette)
                self.setMinimumWidth(480)
                self.resize(520, 480)
                root = gui.QVBoxLayout(self)
                root.setContentsMargins(20, 18, 20, 16)
                root.setSpacing(12)
                heading = gui.QLabel(TITLE)
                font = value(heading, "font")
                font.setPointSizeF(font.pointSizeF() * 1.35)
                font.setBold(True)
                heading.setFont(font)
                root.addWidget(heading)
                self.subtitle = gui.QLabel()
                self.subtitle.setWordWrap(True)
                self.subtitle.setTextFormat(core.Qt.PlainText)
                root.addWidget(self.subtitle)
                self.tree = gui.QTreeWidget()
                self.tree.setColumnCount(2)
                self.tree.setHeaderLabels(["Code point · glyph", "Action"])
                self.tree.setAlternatingRowColors(True)
                self.tree.setRootIsDecorated(True)
                self.tree.setHorizontalScrollBarPolicy(core.Qt.ScrollBarAlwaysOff)
                self.tree.header().setSectionResizeMode(0, gui.QHeaderView.Stretch)
                self.tree.header().setSectionResizeMode(
                    1, gui.QHeaderView.ResizeToContents
                )
                root.addWidget(self.tree, 1)
                footer = gui.QHBoxLayout()
                self.status = gui.QLabel()
                self.status.setWordWrap(True)
                self.status.setTextFormat(core.Qt.PlainText)
                footer.addWidget(self.status, 1)
                for attr, text, callback in [
                    ("reload_button", "Rescan", self.reload),
                    ("close_button", "Close", self.close),
                    ("apply_button", "Remove ticked", self.apply),
                ]:
                    button = gui.QPushButton(text)
                    setattr(self, attr, button)
                    footer.addWidget(button)
                    self.connect_owned(
                        button.clicked, callback, closing=attr == "close_button"
                    )
                self.apply_button.setDefault(True)
                root.addLayout(footer)
                self.connect_owned(self.tree.itemChanged, self.update_actions)
                self.reload()
            except BaseException:
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[KEY] = self
                raise

        def connect_owned(
            self, signal: Any, callback: Any, *, closing: bool = False
        ) -> None:
            """Reuse exact-pair ownership, inert late calls and failed Close retry."""
            self.signals.connect(
                signal, lambda *args: callback(), closing=closing, retry=closing
            )

        def failure(self, error: Exception) -> None:
            """Contain callback errors and drop obsolete action targets."""
            self.slot_error = repr(error)
            if not self._dead:
                self.invalidate()
                self.status.setText("Error: " + self.slot_error)

        def destroyed_owned(self) -> None:
            """Release dying-emitter records without dereferencing dead Qt widgets."""
            self._dead = self._closed = True
            self.facts, self.items = None, {}
            self.signals.finish(destroyed=True)

        def invalidate(self) -> None:
            """Clear obsolete facts and rows; Rescan is the explicit recovery path."""
            self.facts, self.items, self.last_result = None, {}, None
            self.tree.clear()
            self.apply_button.setEnabled(False)

        def reload(self) -> None:
            """Publish only a complete current-font scan, resetting source defaults."""
            if self._closed or self._busy:
                return
            self.invalidate()
            facts = self.backend.capture()
            self.items = populate(qt, self.tree, facts)
            self.facts = facts
            count = value(self.tree, "topLevelItemCount")
            if facts is None:
                self.subtitle.setText("Open a font first.")
            elif not count:
                self.subtitle.setText(
                    f"No shared code points among {len(facts.glyphs)} glyphs."
                )
            else:
                self.subtitle.setText(
                    f"{count} code point{'s are' if count != 1 else ' is'} shared. Ticked glyphs lose that code point; unticked ones keep it."
                )
            self.update_actions()

        def removals(self) -> list[tuple[str, int]]:
            """Retain the source pair dictionary order, including its repeated-pair key."""
            return [
                key
                for key, item in self.items.items()
                if item.checkState(0) == core.Qt.Checked
            ]

        def update_actions(self) -> None:
            """Show live action labels and exact checked-pair count without recursion."""
            if self._closed or self._busy:
                return
            update(qt, self.tree, self.items, value(self, "palette"))
            count = len(self.removals())
            self.apply_button.setEnabled(self.facts is not None and count > 0)
            self.status.setText(f"{count} removal{'s' if count != 1 else ''} ticked")

        def apply(self) -> None:
            """Commit selected pairs, then rescan; failure never masquerades as success."""
            if self._busy:
                return
            removals = self.removals()
            if not removals:
                return
            self._busy = True
            try:
                result = self.backend.apply(self.facts, removals)
            finally:
                self._busy = False
            if self._closed:
                return
            publish_result(self, result)

        def reject(self) -> None:
            """Escape uses the same owned Close path, including reentrant rejection."""
            if self._closing:
                gui.QDialog.reject(self)
            elif not self._closed:
                self.close()

        def closeEvent(self, event: Any) -> None:
            """Stop polling and disconnect plain slots before deferred destruction."""
            if self._busy:
                event.ignore()
                return
            self._closed = True
            self.facts, self.items = None, {}
            if not self.signals.finish():
                event.ignore()
                return
            self._closing = True
            try:
                close_script_dialog(self, event, KEY)
            finally:
                self._closing = False

    return Dialog
