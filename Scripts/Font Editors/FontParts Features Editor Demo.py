# this_file: Scripts/Font Editors/FontParts Features Editor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Edit the feature code of a made-up font in App's FontParts features editor.

What: Opens one nonmodal window with the feature code editor of
fontlabapp.fontui.features (made by fontlabapp.fontui.features_editor; the
controls come from fontlabapp.fontui.features_view and the staging, with its
line-ending rules, from fontlabapp.fontui.features_state) over a detached
sample font that holds a prefix block and two feature blocks in memory. You
edit the prefix and each block separately; Apply to font stores all blocks in
one batch. The code is stored, never compiled. This editor does not use
Fontport or ufoLib2, so the demo needs no extra package.
Use: Run it from the Scripts menu, pick a block, edit its text, add a feature
by typing a four-letter tag and clicking Add feature, or click Remove feature
for the picked block. Click Apply to font to store the blocks, or Revert to
font to drop the staged edits. Close the window when done.
Safety: The sample font exists only in memory and is not a FontLab font. Add
feature, Remove feature and your text edits only stage changes in the editor;
Apply to font then writes the staged blocks to the sample font in memory, and
nothing else. The editor listens to
FontLab's change signals and to its Undo and Redo actions so that it can
reload; it only reads the sample font when they fire and never triggers them.
No FontLab font, feature, master, selection, history, preference, Output or
clipboard is read or written and no file is touched. The writer
fontlabapp.fontui.feature_blocks, which does change FontLab fonts, is not
used. Closing the window disconnects its signals and releases the demo; if Qt
refuses a step, the window and the demo are kept and a message says so.
"""

import importlib

TITLE = "FontParts Features Editor Demo"
MODULES = ("fly.ap.fontui.features", "fly.ap.fontui.features_view", "fly.ap.fontui.features_state")
CAPTION = "Edits go to a sample font in memory and are never compiled. Built from " + ", ".join(MODULES) + "."
IDLE = "Nothing applied yet."
_HANDLES: list = []  # each open demo stays referenced until its window closes
PREFIX = "languagesystem DFLT dflt;\n"
FEATURES = [("kern", "feature kern {\n    pos A V -80;\n} kern;\n"), ("liga", "feature liga {\n} liga;\n")]


class SampleFeatures:
    """Feature blocks in memory, with the block hooks the editor looks for."""

    def __init__(self) -> None:
        self.blocks = {"prefix": PREFIX, "features": list(FEATURES)}

    @property
    def text(self) -> str:
        """All code in one piece: the prefix, then each block."""
        return self.blocks["prefix"] + "".join(code for _, code in self.blocks["features"])

    def get_blocks(self) -> dict:
        """A copy of the prefix and the ordered ``(tag, code)`` blocks."""
        return {"prefix": self.blocks["prefix"], "features": list(self.blocks["features"])}

    def set_blocks(self, blocks: dict, undo_name: str | None = None) -> None:
        """Replace all blocks; there is no history to name."""
        self.blocks = {"prefix": blocks["prefix"], "features": [tuple(pair) for pair in blocks["features"]]}


class SampleFont:
    """A borrowed font that holds only the feature blocks the editor reads and may change."""

    def __init__(self) -> None:
        self.features = SampleFeatures()


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


class Demo:
    """One open window: the editor, its signal scope and the dialog that hosts it."""

    def __init__(self, qt, scope_type, font) -> None:
        self.qt, self.font, self.editor, self.owned, self.status = qt, font, None, None, None
        self.problems: list = []
        self.scope = scope_type(self.problems.append)

    def build(self, content) -> None:
        """Create the caption, the editor and the status line inside ``content``."""
        from fly.ap.fontui import features_editor

        gui = self.qt.QtGui
        content.resize(560, 560)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = features_editor(self.font, content, self.applied)
        # The dialog layout already insets 6 px; the panel root adds none (no 12 px double inset).
        self.editor.layout.setContentsMargins(0, 0, 0, 0)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def applied(self, font, text) -> None:
        """Show the size of the code the last Apply stored in the sample font."""
        self.status.setText(f"Stored in the sample font in memory: {len(text.splitlines())} lines, not compiled.")

    def on_finished(self, *args) -> None:
        """Release after Qt's dispatch returns, never from inside it."""
        self.qt.QtCore.QTimer.singleShot(0, lambda: self.release())

    def release(self) -> None:
        """Disconnect the demo's signals, close the editor and the dialog, drop this demo.

        If Qt refuses a step the window and this demo stay alive and a message says so.
        """
        from fly.ap.qt.widgets import release_owned

        if not release_owned(self.scope, self.owned, self.problems, (self.editor,)):
            notify(TITLE, "Qt refused part of the release; the window is kept open.", "\n".join(map(str, self.problems)))
        elif self in _HANDLES:
            _HANDLES.remove(self)


def main() -> None:
    """Open the editor window on the sample font."""
    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    for module in MODULES:
        importlib.import_module(module)
    demo = Demo(qt, Scope, SampleFont())
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), TITLE, demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
