# this_file: Scripts/Font Editors/Font Browser Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Browse three made-up fonts in App's font list, with a glyph browser below.

What: Opens one nonmodal window with the font browser of
fontlabapp.fontui.fonts (FontBrowser, made by fontlabapp.fontui.font_browser)
over three detached sample fonts that the demo builds with ufoLib2. The list
labels come from fontlabapp.fontui.model.FontListState. Choosing a font fills
the glyph browser under the list. The demo needs ufoLib2 for its sample fonts,
which the fontport extra installs, but the browser itself needs no Fontport.
Use: Run it from the Scripts menu, choose a font, filter the glyph names and
switch between List and Grid. Sort fonts by name reorders the list. Double-click
a glyph, or select it and press Enter, to name it in the status line. Close the
window when done.
Safety: Read-only. The fonts exist only in memory and are not FontLab fonts.
Sort fonts by name reorders the browser's own copy of the list. The browser
listens to FontLab's change signals so that it can refresh FontLab fonts, and
the sample fonts are not among them. No FontLab font, master, selection,
history, preference, Output or clipboard is read or written and no file is
touched. Closing the window disconnects its signals and releases the demo; if
Qt refuses a step, the window and the demo are kept and a message says so.
Without ufoLib2 the demo only says so.
"""

import importlib

TITLE = "Font Browser Demo"
MODULES = ("fly.ap.fontui.fonts", "fly.ap.fontui.model")
CAPTION = "Three sample fonts held in memory. Built from " + " and ".join(MODULES) + "."
IDLE = "Choose a font, then double-click a glyph."
MISSING = "This demo needs ufoLib2, which the fontport extra installs: pip install 'fontlab-fontlabapp[fontport]'."
_HANDLES: list = []  # each open demo stays referenced until its window closes
SHAPES = (  # name, Unicode, width, closed contours (outer clockwise, holes counter-clockwise)
    ("A", 65, 600, [[(0, 0), (300, 700), (600, 0)]]),
    ("V", 86, 600, [[(600, 700), (300, 0), (0, 700)]]),
    ("T", 84, 560, [[(0, 700), (560, 700), (560, 600), (330, 600), (330, 0), (230, 0), (230, 600), (0, 600)]]),
    ("O", 79, 640, [[(40, 0), (40, 700), (600, 700), (600, 0)], [(140, 100), (500, 100), (500, 600), (140, 600)]]),
    ("space", 32, 250, []),
)  # fmt: skip
FONTS = (  # family, style, glyphs
    ("Demo Serif", "Regular", ("A", "V", "T", "O", "space")),
    ("Demo Sans", "Bold", ("A", "V")),
    ("Demo Sans", "Light", ("T", "O")),
)


def sample_ufo(family: str, style: str, names: tuple):
    """A detached ufoLib2 font with the glyphs of ``SHAPES`` named in ``names``."""
    from ufoLib2 import Font

    font = Font()
    font.info.familyName, font.info.styleName = family, style
    font.info.unitsPerEm, font.info.ascender, font.info.descender = 1000, 800, -200
    for name, code, width, contours in SHAPES:
        if name not in names:
            continue
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
    """One open window: the browser, its signal scope and the dialog that hosts it."""

    def __init__(self, qt, scope_type, fonts) -> None:
        self.qt, self.fonts, self.editor, self.owned, self.status = qt, fonts, None, None, None
        self.problems: list = []
        self.scope = scope_type(self.problems.append)

    def build(self, content) -> None:
        """Create the caption, the browser and the status line inside ``content``."""
        from fly.ap.fontui import font_browser

        gui = self.qt.QtGui
        content.resize(560, 900)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = font_browser(self.fonts, content, self.activated)
        # The dialog layout already insets 6 px; the panel root adds none (no 12 px double inset).
        self.editor.layout.setContentsMargins(0, 0, 0, 0)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def activated(self, glyph) -> None:
        """Name the activated glyph; it belongs to a sample font."""
        self.status.setText(f"Activated glyph {glyph.name} of a sample font. Nothing was changed.")

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
    """Open the browser window on the sample fonts, or say what is missing."""
    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    try:
        for module in MODULES:
            importlib.import_module(module)
        demo = Demo(qt, Scope, [sample_ufo(*font) for font in FONTS])
    except ImportError as error:
        # Only a missing ufoLib2 is the extra's fault; name any other failure as it is.
        absent = (error.name or "").partition(".")[0] == "ufoLib2"
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
