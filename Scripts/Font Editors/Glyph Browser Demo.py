# this_file: Scripts/Font Editors/Glyph Browser Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Browse the glyphs of a made-up font in App's glyph browser and detail preview.

What: Opens one nonmodal window with the glyph browser of
fontlabapp.fontui.native (made by fontlabapp.fontui.glyph_browser) over a
detached sample font that the demo builds with ufoLib2. The browser lists the
glyph names with thumbnails, filters them and switches between a list and a
grid. Selecting a glyph shows it in the detail preview of
fontlabapp.fontui.preview, which has zoom and six overlays: fill, stroke,
metrics, anchors, on-curve and off-curve points. The glyph state comes from
fontlabapp.fontui.model. The demo needs ufoLib2 for the sample font, which the
fontport extra installs, but the controls need no Fontport.
Use: Run it from the Scripts menu, type in the filter, pick List or Grid, change
the cell size, select glyphs (several may be selected) and try the preview's Fit,
minus and plus buttons and its overlay boxes. Double-click a glyph, or select it
and press Enter, to name it in the status line. Close the window when done.
Safety: Read-only. The sample font exists only in memory and is not a FontLab
font. The browser listens to FontLab's change signals so that it can refresh
FontLab fonts, and the sample font is not among them. No FontLab font, master,
selection, history, preference, Output or clipboard is read or written and no
file is touched. Closing the window disconnects its signals and releases the
demo; if Qt refuses a step, the window and the demo are kept and a message says
so. Without ufoLib2 the demo only says so.
"""

import importlib

TITLE = "Glyph Browser Demo"
MODULES = ("fly.ap.fontui.native", "fly.ap.fontui.preview", "fly.ap.fontui.model")
CAPTION = "A sample font held in memory. Built from " + ", ".join(MODULES) + "."
IDLE = "Select a glyph; double-click it to name it here."
MISSING = "This demo needs ufoLib2, which the fontport extra installs: pip install 'fontlab-fontlabapp[fontport]'."
_HANDLES: list = []  # each open demo stays referenced until its window closes
SHAPES = (  # name, Unicode, width, closed contours (outer clockwise, holes counter-clockwise)
    ("A", 65, 600, [[(0, 0), (300, 700), (600, 0)]]),
    ("V", 86, 600, [[(600, 700), (300, 0), (0, 700)]]),
    ("T", 84, 560, [[(0, 700), (560, 700), (560, 600), (330, 600), (330, 0), (230, 0), (230, 600), (0, 600)]]),
    ("O", 79, 640, [[(40, 0), (40, 700), (600, 700), (600, 0)], [(140, 100), (500, 100), (500, 600), (140, 600)]]),
    ("space", 32, 250, []),
)  # fmt: skip


def sample_ufo():
    """A detached ufoLib2 font with five glyphs and one anchor."""
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
    font["A"].appendAnchor({"name": "top", "x": 300, "y": 700})
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
    """One open window: the browser, its signal scope and the dialog that hosts it."""

    def __init__(self, qt, scope_type, font) -> None:
        self.qt, self.font, self.editor, self.owned, self.status = qt, font, None, None, None
        self.problems: list = []
        self.scope = scope_type(self.problems.append)

    def build(self, content) -> None:
        """Create the caption, the browser and the status line inside ``content``."""
        from fly.ap.fontui import glyph_browser

        gui = self.qt.QtGui
        content.resize(480, 900)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = glyph_browser(self.font, content, self.activated, True)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def activated(self, glyph) -> None:
        """Name the activated glyph; it belongs to the sample font."""
        self.status.setText(f"Activated glyph {glyph.name} of the sample font. Nothing was changed.")

    def on_finished(self, *args) -> None:
        """Release after Qt's dispatch returns, never from inside it."""
        self.qt.QtCore.QTimer.singleShot(0, lambda: self.release())

    def release(self) -> None:
        """Disconnect the demo's signals, close the browser and the dialog, drop this demo.

        If Qt refuses a step the window and this demo stay alive and a message says so.
        """
        from fly.ap.qt.widgets import release_owned

        if not release_owned(self.scope, self.owned, self.problems, (self.editor,)):
            notify(TITLE, "Qt refused part of the release; the window is kept open.", "\n".join(map(str, self.problems)))
        elif self in _HANDLES:
            _HANDLES.remove(self)


def main() -> None:
    """Open the browser window on the sample font, or say what is missing."""
    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    try:
        for module in MODULES:
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
