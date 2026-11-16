# this_file: Scripts/Widgets/Owned Lifetime Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Create one owned widget, panel and dialog and watch their close state live.

What: Opens a window built with create_dialog from the fontlabapp.ui facade.
Inside it create_widget makes a child label, create_panel adds a small panel
to FontLab's main window and a second create_dialog makes a "subject" dialog.
fontlabapp.core.completion.install wires the subject's finished and destroyed
signals to a Completion record. The window prints each OwnedWidget's closed
flag and last_error and the record's closed, finishing, hooks and error
fields. Refresh re-reads them; Close widget and Close panel call
OwnedWidget.close; the subject's Close button stops the record, as a script
panel's close handler does, then closes the dialog, so closed turns True.
Use: Run it from the Scripts menu, click the buttons and watch the status.
Closing the main window of the demo releases everything it created; the
"Owned Panel Demo" panel should disappear with it.
Safety: Only widgets the demo creates are touched. The panel is a dock widget
the demo adds to FontLab's main window (it may float, on top, when that
window is hidden) and removes again on close. It is a child of that window, so
quitting FontLab with it open discards it with the window. The
subject is never registered as a script dialog. The demo disconnects its own
signals and releases its objects on close. No font, selection, history,
preference, Output or clipboard is read or written. Closing the subject with
the window's own close button instead runs Completion.complete, whose result
shows in the error field.
"""

_HANDLES: list = []  # each open demo stays referenced until its window closes
TITLE = "Owned Lifetime Demo"
KEY = "owned-lifetime-demo"  # the Completion record's registry key, never registered


def status_lines(owned: dict, record) -> list[str]:
    """closed and last_error per OwnedWidget, then the Completion record's fields."""
    lines = [f"{label}: closed={item.closed}, last_error={item.last_error!r}" for label, item in owned.items()]
    return [
        *lines,
        f"Completion {record.key!r}: closed={record.closed}, finishing={record.finishing}, "
        f"hooks={len(record.hooks)}, error={record.error!r}, errors={len(record.errors)}",
    ]


def close_all(items: list) -> None:
    """Close each still-open OwnedWidget; a failure does not skip the rest."""
    if not items:
        return
    head, *rest = items
    try:
        if head is not None and not head.closed:
            head.close()
    finally:
        close_all(rest)


class Demo:
    """One open demo: its owned widgets, completion record and signals live here."""

    def __init__(self, kit, main) -> None:
        self.kit, self.main = kit, main
        self.owned = self.widget = self.panel = self.subject = self.record = self.status = None
        self.hooks: list = []  # (signal, slot) pairs to disconnect on release

    def connect(self, signal, slot) -> None:
        """Connect and remember the pair so release can disconnect it."""
        signal.connect(slot)
        self.hooks.append((signal, slot))

    def labelled(self, text: str):
        """A build callback that puts one label into the owned widget."""

        def build(content) -> None:
            layout = self.kit.gui.QVBoxLayout(content)
            layout.addWidget(self.kit.gui.QLabel(text, content))

        return build

    def build_subject(self, content) -> None:
        """The subject dialog: a label and the Close button of its own."""
        gui = self.kit.gui
        layout = gui.QVBoxLayout(content)
        layout.addWidget(gui.QLabel("Completion is installed on this dialog.", content))
        close = gui.QPushButton("Close", content)
        layout.addWidget(close)
        self.connect(close.clicked, self.close_subject)

    def build(self, content) -> None:
        """Create the owned widget, panel and subject inside the demo's own dialog."""
        kit, gui = self.kit, self.kit.gui
        self.widget = kit.create_widget(content, self.labelled("An owned child widget (create_widget)."))
        self.panel = kit.create_panel(self.main, "Owned Panel Demo", self.labelled("An owned dock panel (create_panel)."), "right")
        self.subject = kit.create_dialog(self.main, "Completion subject", self.build_subject)
        self.record = kit.install(self.subject.widget, KEY)
        self.status = gui.QLabel("", content)
        layout = gui.QVBoxLayout(content)
        layout.addWidget(self.widget.widget)
        layout.addWidget(self.status)
        for label, action in (
            ("Refresh", self.refresh),
            ("Close widget", lambda *args: self.close_one(self.widget)),
            ("Close panel", lambda *args: self.close_one(self.panel)),
        ):
            button = gui.QPushButton(label, content)
            layout.addWidget(button)
            self.connect(button.clicked, action)
        self.refresh()
        content.resize(560, 300)
        self.connect(content.finished, lambda *args: kit.single_shot(0, self.release))

    def refresh(self, *args) -> None:
        """Re-read every state field into the status label (nothing after release)."""
        if self.status is not None:
            owned = {"widget": self.widget, "panel": self.panel, "subject dialog": self.subject}
            self.status.setText("\n".join(status_lines(owned, self.record)))

    def close_one(self, item) -> None:
        """Close one OwnedWidget and show its new state."""
        close_all([item])
        self.refresh()

    def close_subject(self, *args) -> None:
        """Stop the record first (what a panel's close handler does), then close."""
        self.record.stop()
        self.close_one(self.subject)

    def release(self) -> None:
        """Disconnect every signal, close everything the demo made, drop the demo."""
        try:
            self.status = None
            if self.record is not None:
                self.record.stop()
            try:
                while self.hooks:
                    signal, slot = self.hooks.pop()
                    signal.disconnect(slot)
            finally:  # a dead signal must not leave the windows open
                close_all([self.subject, self.panel, self.widget, self.owned])
        finally:  # the handle leaves even when a native object is already gone
            if self in _HANDLES:
                _HANDLES.remove(self)


def main() -> None:
    """Open the demo window, retaining it until it closes."""
    from types import SimpleNamespace

    import fly.ap.ui as ui  # a lazy facade: the factories resolve on first access
    import fly
    from fly.ap.core.completion import install
    from fly.ap.qt.safe import main_window

    qt = fly.qt
    kit = SimpleNamespace(
        gui=qt.QtGui, single_shot=qt.QtCore.QTimer.singleShot, install=install,
        create_dialog=ui.create_dialog, create_panel=ui.create_panel, create_widget=ui.create_widget,
    )  # fmt: skip
    demo = Demo(kit, main_window(fly.fl, qt))
    _HANDLES.append(demo)
    try:
        demo.owned = kit.create_dialog(demo.main, TITLE, demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
