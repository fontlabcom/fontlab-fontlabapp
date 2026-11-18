# this_file: Scripts/Font Editors/Transform Editor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview an affine transform of a made-up glyph in App's transform editor.

What: Opens one nonmodal window with the transform editor of
fontlabapp.fontui.transform (made by fontlabapp.fontui.transform_editor; the
controls and the compare canvas come from fontlabapp.fontui.transform_view)
over a detached sample font that the demo builds with ufoLib2. You type the
six numbers of an affine matrix and an intensity; Fontport builds the
transformed copy and the canvas draws it over the original. Fontport
validates the recipe, so this demo needs the fontport extra.
Use: Run it from the Scripts menu, pick a glyph, change the matrix (for
example yx 0.2 for a slant, or xx 1.2 for a wider glyph) or the intensity and
watch the canvas. Compare with original, Reset transform, Reset view, Zoom in
and Show script change only the view. Close the window when done.
Safety: The sample font exists only in memory and is not a FontLab font, and
the editor never changes it: the preview is a copy. Save settings writes the
recipe as a JSON file to the path you choose in Qt's file dialog, and Load
settings reads one; Qt, not this demo, decides whether the dialog remembers
the folders you visit. Nothing else is written. No FontLab font, master,
selection, history, preference, Output or clipboard is read or written.
Closing the window disconnects its signals and releases the demo; if Qt refuses
a step, the window and the demo are kept and a message says so. Without the
fontport extra the demo only says so.
"""

import importlib

TITLE = "Transform Editor Demo"
MODULES = ("fly.ap.fontui.transform", "fly.ap.fontui.transform_view")
CAPTION = "The preview is a copy of a sample glyph. Built from " + " and ".join(MODULES) + "."
IDLE = "No preview yet."
MISSING = "This demo needs the fontport extra: pip install 'fontlab-fontlabapp[fontport]'."
_HANDLES: list = []  # each open demo stays referenced until its window closes
SHAPES = (  # name, Unicode, width, closed contours (outer clockwise, holes counter-clockwise)
    ("A", 65, 600, [[(0, 0), (300, 700), (600, 0)]]),
    ("T", 84, 560, [[(0, 700), (560, 700), (560, 600), (330, 600), (330, 0), (230, 0), (230, 600), (0, 600)]]),
    ("O", 79, 640, [[(40, 0), (40, 700), (600, 700), (600, 0)], [(140, 100), (500, 100), (500, 600), (140, 600)]]),
)  # fmt: skip


def sample_ufo():
    """A detached ufoLib2 font with three glyphs."""
    from ufoLib2 import Font

    font = Font()
    font.info.familyName, font.info.styleName = "Demo Sans", "Regular"
    font.info.unitsPerEm, font.info.ascender, font.info.descender = 1000, 800, -200
    for name, code, width, contours in SHAPES:
        glyph = font.newGlyph(name)
        glyph.unicodes, glyph.width = [code], width
        pen = glyph.getPen()
        for points in contours:
            pen.moveTo(points[0])
            for point in points[1:]:
                pen.lineTo(point)
            pen.closePath()
    return font


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
        from fly.ap.fontui import transform_editor

        gui = self.qt.QtGui
        content.resize(560, 900)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = transform_editor(self.font, "A", content, self.previewed)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def previewed(self, recipe, result) -> None:
        """Show the matrix of the last good preview; the sample glyph is unchanged."""
        matrix = ", ".join(f"{value:g}" for value in recipe.matrix)
        self.status.setText(f"Preview of {result.name}: matrix ({matrix}) at {recipe.intensity:g}%. The sample is unchanged.")

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
    """Open the editor window on the sample font, or say what is missing."""
    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    try:
        for module in MODULES:  # the first one names the fontport extra when it is missing
            importlib.import_module(module)
        demo = Demo(qt, Scope, sample_ufo())
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
