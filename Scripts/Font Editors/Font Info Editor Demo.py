# this_file: Scripts/Font Editors/Font Info Editor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Edit the font information of a made-up font in App's FontParts info form.

What: Opens one nonmodal window with the font information form of
fontlabapp.fontui.fontinfo (made by fontlabapp.fontui.font_info_editor) over a
detached sample font that holds a ufoLib2 information object (names, metrics,
version and a few text fields) and no glyphs. The form stages your edits until
you click Apply; Fontport validates the whole batch first, so this demo needs
the fontport extra.
Use: Run it from the Scripts menu, change a field (for example the family
name, the ascender, or the OS/2 weight class), then click Apply, or Revert to
drop the staged text. A bad value, such as text in an integer field, is
refused with a message in the form. Close the window when done.
Safety: The sample font exists only in memory and is not a FontLab font. Apply
writes the changed fields into the sample font's information in memory, and
nothing else. The form listens to FontLab's change signals so that it can
reload; it only reads the sample font when they fire. No FontLab font, master,
selection, history, preference, Output or clipboard is read or written and no
file is touched. Closing the window disconnects its signals and releases the
demo; if Qt refuses a step, the window and the demo are kept and a message
says so. Without the fontport extra the demo only says so.
"""

import importlib

TITLE = "Font Info Editor Demo"
MODULES = ("fly.ap.fontui.fontinfo",)
CAPTION = "Edits go to a sample font in memory. Built from " + " and ".join(MODULES) + "."
IDLE = "Nothing applied yet."
MISSING = "This demo needs the fontport extra: pip install 'fontlab-fontlabapp[fontport]'."
_HANDLES: list = []  # each open demo stays referenced until its window closes


def sample_info():
    """A detached ufoLib2 information object holding made-up names, metrics and version."""
    from ufoLib2 import Font

    info = Font().info
    info.familyName, info.styleName = "Demo Sans", "Regular"
    info.unitsPerEm, info.ascender, info.descender = 1000, 800, -200
    info.capHeight, info.xHeight, info.italicAngle = 700, 500, 0
    info.versionMajor, info.versionMinor = 1, 0
    info.copyright, info.openTypeNameDesigner = "Demo font, no rights reserved.", "Demo Designer"
    info.openTypeOS2WeightClass = 400
    return info


class SampleInfo:
    """The ufoLib2 information, plus the batch ``apply`` hook the form looks for."""

    def __init__(self, info) -> None:
        self.info = info

    def __getattr__(self, name):
        return getattr(self.info, name)

    def apply(self, changes: dict, undo_name: str | None = None) -> None:
        """Set every changed field, or none of them if ufoLib2 refuses one."""
        before = {name: getattr(self.info, name) for name in changes}  # ufoLib2 checks each value as it is set
        try:
            for name, value in changes.items():
                setattr(self.info, name, value)
        except ValueError:
            for name, value in before.items():
                setattr(self.info, name, value)
            raise


class SampleFont:
    """A borrowed font that holds only the information the form reads and may change."""

    def __init__(self, info) -> None:
        self.info = SampleInfo(info)


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
        from fly.ap.fontui import font_info_editor

        gui = self.qt.QtGui
        content.resize(560, 580)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = font_info_editor(self.font, content, self.applied)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def applied(self, font, changes) -> None:
        """Show which fields the last Apply changed in the sample font."""
        self.status.setText("Applied to the sample font in memory: " + ", ".join(sorted(changes)) + ".")

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
    """Open the form window on the sample font, or say what is missing."""
    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    try:
        for module in MODULES:  # the first one names the fontport extra when it is missing
            importlib.import_module(module)
        demo = Demo(qt, Scope, SampleFont(sample_info()))
    except ImportError as error:
        # Only a missing extra package is the extra's fault; name any other failure as it is.
        culprit = error.name or getattr(error.__cause__, "name", None) or ""
        absent = culprit.partition(".")[0] in ("fontlab_fontport", "ufoLib2")
        notify(TITLE, MISSING if absent else "An App module could not be imported.", str(error))
        return
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), TITLE, demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
