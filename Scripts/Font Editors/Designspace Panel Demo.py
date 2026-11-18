# this_file: Scripts/Font Editors/Designspace Panel Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Move through the axes of a made-up designspace in App's designspace panel.

What: Opens one nonmodal window with the designspace panel of
fontlabapp.fontui.designspace (made by fontlabapp.fontui.designspace_panel):
a slider and a number box for each axis, a list of sources and instances, and
a status line that says whether the axis values hit a source master or only an
instance location. The designspace is a small stand-in written in this script
with the members the panel reads (axes, sources, instances, defaults, location
and instance), because Fontport's own Designspace class lives in the Fontport
package and App only imports it inside fontlabapp.fontui. The panel never
interpolates and opens no font.
Use: Run it from the Scripts menu, drag the sliders or type axis values, pick a
source or an instance in the list, or click Reset axes to defaults. An
unavailable entry is listed with its reason and cannot be selected into the
sliders. Close the window when done.
Safety: Read-only. The axes, sources and instances are literals in this script,
no designspace file is read and no font is opened. No FontLab font, master,
selection, history, preference, Output or clipboard is read or written and no
file is touched. Closing the window disconnects its signals and releases the
demo; if Qt refuses a step, the window and the demo are kept and a message says
so. The demo needs no extra package.
"""

import importlib
from dataclasses import dataclass

TITLE = "Designspace Panel Demo"
MODULES = ("fly.ap.fontui.designspace",)
CAPTION = "A made-up designspace with two axes. Built from " + " and ".join(MODULES) + "."
IDLE = "Move an axis or pick a source."
_HANDLES: list = []  # each open demo stays referenced until its window closes


@dataclass(frozen=True)
class Axis:
    """One continuous axis, in user coordinates."""

    name: str
    tag: str
    minimum: float
    default: float
    maximum: float


@dataclass(frozen=True)
class Location:
    """A source or an instance at one point of the axes."""

    kind: str
    name: str
    coordinates: tuple
    available: bool = True
    reason: str | None = None


class SampleDesignspace:
    """Two axes, three sources and two instances, answering what the panel asks."""

    def __init__(self) -> None:
        self.axes = (Axis("Weight", "wght", 100, 400, 900), Axis("Width", "wdth", 75, 100, 125))
        self.sources = (
            Location("source", "Light", (("Weight", 100.0), ("Width", 100.0))),
            Location("source", "Regular", (("Weight", 400.0), ("Width", 100.0))),
            Location("source", "Black Condensed", (("Weight", 900.0), ("Width", 75.0))),
        )
        self.instances = (
            Location("instance", "Semibold", (("Weight", 600.0), ("Width", 100.0))),
            Location("instance", "Wide Light", (("Weight", 100.0), ("Width", 125.0)), False, "No font is made for it"),
        )

    def defaults(self) -> dict:
        """The default value of each axis."""
        return {axis.name: axis.default for axis in self.axes}

    def location(self, values: dict) -> dict:
        """A full location from ``values``; unknown or out-of-range axes are refused."""
        result = self.defaults()
        unknown = set(values) - set(result)
        if unknown:
            raise ValueError(f"Unknown design axes: {sorted(unknown)}")
        result.update(values)
        for axis in self.axes:
            if not axis.minimum <= result[axis.name] <= axis.maximum:
                raise ValueError(f"Location outside {axis.name} bounds")
        return result

    def instance(self, values: dict, name: str = "Instance") -> Location:
        """An instance location at ``values``."""
        return Location("instance", name, tuple(self.location(values).items()))


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


class Demo:
    """One open window: the panel, its signal scope and the dialog that hosts it."""

    def __init__(self, qt, scope_type, designspace) -> None:
        self.qt, self.designspace, self.editor, self.owned, self.status = qt, designspace, None, None, None
        self.problems: list = []
        self.scope = scope_type(self.problems.append)

    def build(self, content) -> None:
        """Create the caption, the panel and the status line inside ``content``."""
        from fly.ap.fontui import designspace_panel

        gui = self.qt.QtGui
        content.resize(520, 480)
        layout = gui.QVBoxLayout(content)
        caption, self.status = gui.QLabel(CAPTION, content), gui.QLabel(IDLE, content)
        self.editor = designspace_panel(self.designspace, content, self.moved)
        # The dialog layout already insets 6 px; the panel root adds none (no 12 px double inset).
        self.editor.layout.setContentsMargins(0, 0, 0, 0)
        for label in (caption, self.status):
            label.setWordWrap(True)
        for widget in (caption, self.editor.widget, self.status):
            layout.addWidget(widget)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def moved(self, entry) -> None:
        """Show the location the panel reported."""
        point = ", ".join(f"{name}={value:g}" for name, value in entry.coordinates)
        self.status.setText(f"Location {point}.")

    def on_finished(self, *args) -> None:
        """Release after Qt's dispatch returns, never from inside it."""
        self.qt.QtCore.QTimer.singleShot(0, lambda: self.release())

    def release(self) -> None:
        """Disconnect the demo's signals, close the panel and the dialog, drop this demo.

        If Qt refuses a step the window and this demo stay alive and a message says so.
        """
        from fly.ap.qt.widgets import release_owned

        if not release_owned(self.scope, self.owned, self.problems, (self.editor,)):
            notify(TITLE, "Qt refused part of the release; the window is kept open.", "\n".join(map(str, self.problems)))
        elif self in _HANDLES:
            _HANDLES.remove(self)


def main() -> None:
    """Open the panel window on the sample designspace."""
    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    for module in MODULES:
        importlib.import_module(module)
    demo = Demo(qt, Scope, SampleDesignspace())
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), TITLE, demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
