# this_file: Scripts/Masters/Master Switcher Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview the master buttons App's master switcher would show, without switching.

What: Reads the master buttons from fontlabapp.masters.switcher.model: the
masters of the open font ordered by their first axis, each with its axis
location as its button label, and reports which master is current. The switcher
panel shell (fontlabapp.masters.switcher.ui, SwitcherDialog) is only named: it
leaves the master buttons to the script that subclasses it, and this demo ships
none.
Use: Open a font and run it. Click Show Details for the buttons in order.
Safety: Read-only. It reads master names, axis names and axis locations and
the current master. switch(), the one function that would make another master
current (package.setMaster), is never called and no switcher panel opens, so
the current master, selection, history, preferences, Output and clipboard are
not touched and nothing is written to the font. With no font open it only says
so.
"""

TITLE = "Master Switcher Demo"


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def button_lines(package) -> list[str]:
    """One line per master button: its label as the switcher would draw it."""
    from fly.ap.masters.switcher import model

    return [
        f"[{master}{' · ' + label if label else ''}]{'  (current master)' if master == package.master else ''}"
        for master, label in model.button_values(package)
    ]


def main() -> None:
    """Show the master buttons of the open font, or say that a font is needed."""
    from fly.ap.core.scripting import current_package

    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. The demo previews its master buttons.")
        return
    try:
        lines = button_lines(package)
    except (ValueError, RuntimeError) as error:
        notify(TITLE, f"The master buttons could not be read: {error}")
        return
    notify(TITLE, f"{len(lines)} master buttons. Nothing was switched or written.", "\n".join(lines))


if __name__ == "__main__":
    main()
