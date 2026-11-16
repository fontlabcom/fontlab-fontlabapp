# this_file: Scripts/Utilities/Signals And Hotkeys Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Try Qt signal ownership, quiet callbacks and key routing in a small window.

What: Opens one nonmodal window with a text field, two buttons and a check box.
The field routes key presses through fontlabapp.qt.events.key, the buttons use
a fontlabapp.core.signals Scope, the programmatic button runs under
quiet_callbacks, and the check box uses track_connection. A label also shows
whether FontLab's global hotkey backend is available.
Use: Run it from the Scripts menu, type in the field and click the buttons. The
counters in the window change. Close the window when done.
Safety: Only widgets the demo creates are touched. Closing the window
disconnects every signal it connected and releases the demo. No hotkey manager
is constructed or registered; only availability is reported. No font,
selection, history, preference, Output
or clipboard is read or written.
"""

import sys
from importlib.util import find_spec

_HANDLES: list = []  # each open demo stays referenced until its window closes


def hotkey_lines() -> list[str]:
    """Report the global hotkey backend without constructing a manager."""
    if sys.platform == "win32":
        backend = "not implemented on Windows"
    elif sys.platform != "darwin":
        backend = f"no backend for {sys.platform}"
    elif find_spec("Quartz") is None:
        backend = "macOS backend needs pyobjc-framework-Quartz (the hotkeys extra)"
    else:
        backend = "macOS backend available (fontlabapp.core.hotkey.mac, Quartz found)"
    return [f"Global hotkeys: {backend}", "This demo registers no hotkeys"]


class State:
    """Counters the widgets update; ``_quiet`` is the flag quiet_callbacks sets."""

    def __init__(self) -> None:
        self._quiet = False
        self.keys = self.clicks = self.ignored = self.toggles = 0
        self.last_key = None

    def text(self) -> str:
        """The status label text."""
        return (
            f"Key presses: {self.keys} (last key code {self.last_key})\n"
            f"Clicks counted: {self.clicks}, quiet clicks ignored: {self.ignored}\n"
            f"Toggles: {self.toggles}"
        )


class Demo:
    """One open window: its widgets, signal scope and connections are owned here."""

    def __init__(self, kit) -> None:
        self.kit, self.state = kit, State()
        self.problems: list = []
        self.scope = kit.Scope(self.problems.append)
        self.pairs: list = []
        self.owned = None
        self.status = None
        self.click_button = None

    def build(self, content) -> None:
        """Create the widgets inside ``content`` (the demo's own dialog)."""
        gui, kit = self.kit.gui, self.kit

        class KeyField(gui.QLineEdit):
            keyPressEvent = kit.key_press_handler(gui.QLineEdit, self.on_key)

        layout = gui.QVBoxLayout(content)
        hotkeys = gui.QLabel("\n".join(hotkey_lines()), content)
        self.status = gui.QLabel("", content)
        field = KeyField(content)
        field.setPlaceholderText("Type here to see key-press routing")
        self.click_button = gui.QPushButton("Count a click", content)
        quiet_button = gui.QPushButton("Click it programmatically (quiet)", content)
        check = gui.QCheckBox("Track this toggle", content)
        for widget in (hotkeys, self.status, field, self.click_button, quiet_button, check):
            layout.addWidget(widget)
        self.scope.connect(self.click_button.clicked, self.on_click)
        self.scope.connect(quiet_button.clicked, self.on_programmatic)
        self.scope.connect(content.finished, self.on_finished, closing=True)
        kit.track_connection(self.pairs, check.toggled, self.on_toggle)
        self.refresh()

    def refresh(self) -> None:
        self.status.setText(self.state.text())

    def on_key(self, widget, event) -> bool:
        """Record the key; False lets the field handle it normally."""
        self.state.keys += 1
        self.state.last_key = event.key()
        self.refresh()
        return False

    def on_click(self) -> None:
        if self.state._quiet:
            self.state.ignored += 1
        else:
            self.state.clicks += 1
        self.refresh()

    def on_programmatic(self) -> None:
        with self.kit.quiet_callbacks(self.state):
            self.click_button.click()

    def on_toggle(self, checked) -> None:
        self.state.toggles += 1
        self.refresh()

    def on_finished(self, *args) -> None:
        """Release after Qt's dispatch returns, never from inside it."""
        self.kit.single_shot(0, lambda: self.release())

    def release(self) -> None:
        """Disconnect every owned signal, close the window and drop this demo."""
        self.kit.disconnect_connections(self.pairs, self.problems.append)
        self.scope.finish()
        if self.owned is not None:
            self.owned.close()
        if self in _HANDLES:
            _HANDLES.remove(self)


def main() -> None:
    """Open the demo window, retaining it until it closes."""
    from types import SimpleNamespace

    import fly
    from fly.ap.core.signals.callbacks import quiet_callbacks
    from fly.ap.core.signals.connections import disconnect_connections, track_connection
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.events.key import key_press_handler
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    kit = SimpleNamespace(
        gui=qt.QtGui,
        single_shot=qt.QtCore.QTimer.singleShot,
        quiet_callbacks=quiet_callbacks,
        disconnect_connections=disconnect_connections,
        track_connection=track_connection,
        Scope=Scope,
        key_press_handler=key_press_handler,
    )
    demo = Demo(kit)
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), "Signals And Hotkeys Demo", demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
