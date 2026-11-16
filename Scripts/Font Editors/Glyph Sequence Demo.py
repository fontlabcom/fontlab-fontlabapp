# this_file: Scripts/Font Editors/Glyph Sequence Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Set text in a made-up font with App's kerned glyph sequence, with wrapping.

What: Opens one nonmodal window with the glyph sequence of
fontlabapp.fontui.sequence (made by fontlabapp.fontui.glyph_sequence), drawn
by fontlabapp.fontui.sequence_canvas, over a detached sample font that the
demo builds with ufoLib2: five glyphs and two kerning pairs. Fontport places
the glyphs by Unicode and applies the kerning; the Wrap lines box splits the
run into lines with fontlabapp.fontui.wrap. This is a Unicode lookup, not
shaping; the separate fontlabapp.fontui.shaping backend shapes text with
HarfBuzz when the fontui-shaping extra is installed. The TMetrics window
(fontlabapp.fontui.tmetrics over fontlabapp.fontui.tmetrics_model) builds on
the same shaping for metrics and kerning, and writes edits back with
fontlabapp.fontui.livesync suppressing its own echo; double-clicking a glyph
there opens the TGlyph view (fontlabapp.fontui.tglyph over
fontlabapp.fontui.tglyph_model), which edits points through
fontlabapp.fontui.tglyph_edit. Both T windows accept the injectable host
protocol in fontlabapp.fontui.twindow_host; its FontLab adapter owns change
notifications and polls the captured Glyph window for literal Unicode text.
TMetrics can send that text back on Return; named or per-layer symbol streams
remain unavailable through that text bridge. This detached sequence demo does
not attach the native text bridge. The demo needs the fontport extra.
Use: Run it from the Scripts menu, change the text, switch to Glyph names (for
example /A /V /T), toggle Apply kerning, change the size or the direction and
tick Wrap lines, then narrow the window. Click a glyph, or press the arrow keys,
Home or End on the canvas, to select one; the status line names it. Close the
window when done.
Safety: Read-only. The sample font exists only in memory and is not a FontLab
font. The sequence listens to FontLab's change signals so that it can redraw
FontLab fonts, and the sample font is not among them. No FontLab font, master,
selection, history, preference, Output or clipboard is read or written and no
file is touched. Closing the window disconnects its signals and releases the
demo; if Qt refuses a step, the window and the demo are kept and a message
says so. Without the fontport extra the demo only says so.
"""

import importlib

TITLE = "Glyph Sequence Demo"
MODULES = (
    "fly.ap.fontui.sequence",
    "fly.ap.fontui.sequence_canvas",
    "fly.ap.fontui.wrap",
)
CAPTION = "Kerned text in a sample font. Built from " + ", ".join(MODULES) + "."
IDLE = "Click a glyph to select it."
START_TEXT = "AVA TOAV"
MISSING = "This demo needs the fontport extra: pip install 'fontlab-fontlabapp[fontport]'."
_HANDLES: list = []  # each open demo stays referenced until its window closes
SHAPES = (  # name, Unicode, width, closed contours (outer clockwise, holes counter-clockwise)
    ("A", 65, 600, [[(0, 0), (300, 700), (600, 0)]]),
    ("V", 86, 600, [[(600, 700), (300, 0), (0, 700)]]),
    ("T", 84, 560, [[(0, 700), (560, 700), (560, 600), (330, 600), (330, 0), (230, 0), (230, 600), (0, 600)]]),
    ("O", 79, 640, [[(40, 0), (40, 700), (600, 700), (600, 0)], [(140, 100), (500, 100), (500, 600), (140, 600)]]),
    ("space", 32, 250, []),
)  # fmt: skip


def sample_ufo():
    """A detached ufoLib2 font with five glyphs and sample kerning."""
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
    font.kerning[("A", "V")] = -80
    font.kerning[("T", "O")] = -30
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
        """Create the caption, the sequence and the status line inside ``content``."""
        from fly.ap.fontui import glyph_sequence

        gui = self.qt.QtGui
        content.resize(640, 420)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = glyph_sequence(self.font, content, self.selected)
        self.editor.text_control.setText(START_TEXT)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def selected(self, glyph, index) -> None:
        """Name the selected occurrence; a missing glyph arrives as ``None``."""
        name = "a missing glyph" if glyph is None else f"glyph {glyph.name}"
        self.status.setText(f"Selected {name} at position {index + 1}.")

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
    """Open the sequence window on the sample font, or say what is missing."""
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
