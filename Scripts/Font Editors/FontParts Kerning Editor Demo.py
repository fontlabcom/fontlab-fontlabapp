# this_file: Scripts/Font Editors/FontParts Kerning Editor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Edit the kerning of a made-up font in App's FontParts kerning editor.

What: Opens one nonmodal window with the kerning editor of
fontlabapp.fontui.kerning (made by fontlabapp.fontui.kerning_editor; the
controls come from fontlabapp.fontui.kerning_view) over a detached sample font
that the demo builds with ufoLib2: two kerning groups, one group pair and one
glyph pair. The editor lists explicit pairs, shows the effective value for the
pair you type and previews it in a glyph sequence. Fontport validates every
edit, so this demo needs the fontport extra.
Use: Run it from the Scripts menu, pick a pair or type a left and right name
(for example public.kern1.A and public.kern2.V, or T and O), change the value
and click Apply pair, or Delete explicit pair. Reload drops what you typed.
Close the window when done.
Safety: The sample font exists only in memory and is not a FontLab font. Apply
pair and Delete explicit pair write into the sample font's kerning in memory,
and nothing else. The editor listens to FontLab's change signals and to its
Undo and Redo actions so that it can reload; it only reads the sample font when
they fire and never triggers them. No FontLab font, master, selection,
history, preference, Output or clipboard is read or written and no file is
touched. Closing the window disconnects its signals and releases the demo; if
Qt refuses a step, the window and the demo are kept and a message says so.
Without the fontport extra the demo only says so.
"""

import importlib

TITLE = "FontParts Kerning Editor Demo"
MODULES = ("fly.ap.fontui.kerning", "fly.ap.fontui.kerning_view")
CAPTION = "Edits go to a sample font in memory. Built from " + " and ".join(MODULES) + "."
IDLE = "Nothing applied yet."
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
    font.groups["public.kern1.A"], font.groups["public.kern2.V"] = ["A"], ["V"]
    font.kerning[("public.kern1.A", "public.kern2.V")] = -80
    font.kerning[("T", "O")] = -30
    return font


class SampleKerning(dict):
    """Pairs as a plain dict, plus the batch ``apply`` hook the editor looks for."""

    def apply(self, values: dict, undo_name: str | None = None) -> None:
        """Replace all pairs with ``values``; there is no history to name."""
        self.clear()
        self.update(values)


class SampleFont:
    """A borrowed font: the ufoLib2 font with kerning the editor may change."""

    def __init__(self, ufo) -> None:
        self.ufo = ufo
        self.groups = dict(ufo.groups)
        self.kerning = SampleKerning(ufo.kerning)

    def __getattr__(self, name):
        return getattr(self.ufo, name)

    def __getitem__(self, name):
        return self.ufo[name]

    def __contains__(self, name) -> bool:
        return name in self.ufo


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
        from fly.ap.fontui import kerning_editor

        gui = self.qt.QtGui
        content.resize(560, 820)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = kerning_editor(self.font, content, self.applied)
        # The dialog layout already insets 6 px; the panel root adds none (no 12 px double inset).
        self.editor.layout.setContentsMargins(0, 0, 0, 0)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def applied(self, font, pairs) -> None:
        """Show the result of an Apply or Delete on the sample font."""
        self.status.setText(f"Applied to the sample font in memory: {len(pairs)} explicit pairs.")

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
        demo = Demo(qt, Scope, SampleFont(sample_ufo()))
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
