# this_file: src/fontlabapp/proof/text_holder/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Injected Qt floating plain-text editor with complete original control flow."""

from typing import Any

import fontlabapp.proof.text_holder.model as model
from fontlabapp.qt.properties import value
from fontlabapp.qt.literal_text import line_edit_type, read_text
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import close_script_dialog, connect_guarded
from fontlabapp.proof.text_holder.editor import (
    document_position,
    editor_type,
    literal_position,
    literal_text,
)


def dialog_type(qt: Any, store: Any) -> type:
    """Build PythonQt classes only on request; no font or preference API needed."""
    gui, core = qt.QtGui, qt.QtCore

    class Dialog(gui.QDialog):
        def __init__(self, parent: Any = None, *, snapshot: tuple | None = None):
            content, saved_frame = (
                snapshot if snapshot is not None else (store.load(), store.size())
            )
            gui.QDialog.__init__(self, parent)
            self._connections, self._closed = [], False
            self.store = store
            try:
                self._build(content, saved_frame)
            except BaseException:
                self._discard()
                raise

        def _build(self, content: str, saved_frame: tuple | None) -> None:
            self._saved_frame, self._positioned = saved_frame, False
            self.setWindowTitle("Text Holder")
            self.setWindowFlags(
                core.Qt.Window
                | core.Qt.WindowStaysOnTopHint
                | core.Qt.WindowTitleHint
                | core.Qt.WindowSystemMenuHint
                | core.Qt.WindowCloseButtonHint
                | core.Qt.WindowMinMaxButtonsHint
            )
            self.setMinimumSize(500, 400)
            self.setMaximumSize(1200, 800)
            self.resize(500, 400)
            root = gui.QVBoxLayout(self)
            self.editor = editor_type(qt)(self)
            self.editor.setPlainText(content)
            root.addWidget(self.editor, 1)
            grid = gui.QGridLayout()
            root.addLayout(grid)
            line_edit = line_edit_type(qt)
            self.find_input, self.replace_input = line_edit(self), line_edit(self)
            self.find_input.setPlaceholderText("Text to find")
            self.replace_input.setPlaceholderText("Replacement text")
            grid.addWidget(gui.QLabel("Find:", self), 0, 0)
            grid.addWidget(self.find_input, 0, 1, 1, 2)
            grid.addWidget(gui.QLabel("Replace:", self), 1, 0)
            grid.addWidget(self.replace_input, 1, 1, 1, 2)
            for name, label, callback, row, col in (
                ("replace_button", "Find && Replace", self.replace, 2, 0),
                ("find_button", "Find", self.find, 2, 1),
                ("save_button", "Save", self.save, 3, 0),
                ("save_close_button", "Save && Close", self.save_close, 3, 1),
                ("ignore_button", "Ignore && Close", self.ignore, 3, 2),
            ):
                button = gui.QPushButton(label, self)
                button.setAutoDefault(False)
                setattr(self, name, button)
                grid.addWidget(button, row, col)
                connect_guarded(self, button.clicked, callback)
            self.status = gui.QLabel("", self)
            self.status.setWordWrap(True)
            root.addWidget(self.status)
            self._completion_lifetime = install(self, model.KEY)
            self._completion_lifetime.on_destroyed.append(self._destroyed)

        def _discard(self) -> None:
            """Dispose an unshown candidate without writing recovery or geometry."""
            if not self._closed:
                self._closed = True
                self.store = None
                close_script_dialog(self, gui.QCloseEvent(), model.KEY)

        def showEvent(self, event: Any) -> None:
            # Protected native base handlers require explicit class dispatch.
            if self._closed:
                return
            try:
                gui.QDialog.showEvent(self, event)
                if self._positioned:
                    return
                self._positioned = True
                frame = value(self, "frameGeometry")
                extra = (
                    int(value(frame, "width")) - int(value(self, "width")),
                    int(value(frame, "height")) - int(value(self, "height")),
                )
                low, high, size = model.client_sizes(extra, self._saved_frame)
                self.setMinimumSize(*low)
                self.setMaximumSize(*high)
                self.resize(*size)
                frame = value(self, "frameGeometry")
                # FontLab primaryScreen is a null/value binding; the documented
                # host-safe screens()[0] route provides the primary screen.
                screens = value(gui.QApplication, "screens")
                if not screens:
                    raise ValueError("Primary screen geometry is unavailable.")
                screen = value(screens[0], "geometry")
                self.move(
                    *model.window_origin(
                        int(value(screen, "left")),
                        int(value(screen, "top")),
                        int(value(screen, "height")),
                        int(value(frame, "height")),
                    )
                )
            except Exception as error:  # noqa: BLE001 - never escape a native virtual handler
                self.slot_error = repr(error)
                self.status.setText(
                    "Original window geometry could not be restored: " + str(error)
                )

        def find(self, *args: Any) -> None:
            if self._closed:
                return
            needle = read_text(qt, value(self.find_input, "text"))
            if not needle:
                return
            result = model.find_first(literal_text(self.editor), needle)
            if result is None:
                self.status.setText("Text not found.")
                return
            cursor = self.editor.textCursor()
            cursor.setPosition(document_position(self.editor, result[0]))
            cursor.setPosition(
                document_position(self.editor, result[1], True),
                gui.QTextCursor.KeepAnchor,
            )
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
            self.editor.setFocus()
            self.status.setText("")

        def replace(self, *args: Any) -> None:
            if self._closed or value(self.editor, "isReadOnly"):
                return
            cursor = self.editor.textCursor()
            plan = model.plan_replacement(
                literal_text(self.editor),
                read_text(qt, value(self.find_input, "text")),
                read_text(qt, value(self.replace_input, "text")),
                literal_position(self.editor, int(value(cursor, "selectionStart"))),
                literal_position(self.editor, int(value(cursor, "selectionEnd"))),
            )
            if plan is None:
                return
            self.editor._replace_range(
                document_position(self.editor, plan.start),
                document_position(self.editor, plan.end, True),
                plan.text,
            )
            self.status.setText("")

        def save(self, *args: Any) -> None:
            if not self._closed:
                self.store.save(literal_text(self.editor))
                self.status.setText("Content saved.")

        def save_close(self, *args: Any) -> None:
            if not self._closed:
                self.save()
                self.close()

        def ignore(self, *args: Any) -> None:
            if not self._closed:
                self.close()

        def _destroyed(self) -> None:
            self._closed = True
            self._connections.clear()
            self.store = None

        def closeEvent(self, event: Any) -> None:
            if self._closed:
                event.accept()
                return
            try:
                self.store.save_size(
                    (
                        int(value(value(self, "frameGeometry"), "width")),
                        int(value(value(self, "frameGeometry"), "height")),
                    )
                )
            except Exception as error:  # noqa: BLE001 - size I/O cannot prevent Ignore & Close
                self.slot_error = repr(error)
            self._closed = True
            self.store = None
            close_script_dialog(self, event, model.KEY)

    return Dialog
