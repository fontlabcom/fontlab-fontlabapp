# this_file: Scripts/Proof/Text Filter Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Filter proof text with a character class, then try the Text Simplifier panel.

What: Runs fontlabapp.proof.text_filter.model.filter_text on four sample
strings and shows the results, including the error a malformed character
class raises. Then opens the Text Simplifier panel (TextFilterDialog) with
sample input. The Characters field is a regular-expression character class:
a-z is a range and every character outside the class is removed.
Use: Read the message box (Show Details lists each result), then edit the
Input and Characters boxes in the panel and click Simplify. Reset restores
the default character set and clears the output but keeps the input. The
panel saves its three fields as you type.
Safety: The panel is given its own settings file in one fixed demo folder,
fontlabapp-demos/text-filter under the system temp directory, which the demo
reuses, resets with the sample input at every run and never deletes. FontLab's
saved Text Simplifier fields and window position are never read or changed.
If you tick Open in a New Tab and click Simplify, the panel opens one new text
tab with the filtered text on the current font; leave it unticked to open
none. While it creates the tab, fontlabapp reads every glyph shape's on/off
(active) state in the font and writes back any state the tab creation changed.
Nothing else is written: no font data, selection, history, Output or
clipboard. If a Text Simplifier panel is already open, the demo stops.
"""

import re
import sys
import tempfile
from pathlib import Path

TITLE = "Text Filter Demo"
INI = Path("fontlabapp-demos") / "text-filter" / "Text Simplifier.ini"
SAMPLE_INPUT = "Hamburgefonstiv 2026 -- naïve café, Ωmega!"
CASES = (
    (SAMPLE_INPUT, "a-zA-Z"),
    (SAMPLE_INPUT, "0-9"),
    (SAMPLE_INPUT, r"\w\s"),
    (SAMPLE_INPUT, "z-a"),  # a malformed range: filter_text raises re.error
)


def filter_lines(filter_text) -> list[str]:
    """One line per sample: the class, then what survives or the error raised."""
    lines = []
    for text, characters in CASES:
        try:
            outcome = repr(filter_text(text, characters))
        except re.error as error:
            outcome = f"re.error: {error}"
        lines.append(f"[{characters}] -> {outcome}")
    return lines


def notify(text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    box = create_message_box(qt.QtGui, TITLE, text, "Information", (parent,), detail=details)
    box.setWindowTitle(TITLE)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def is_open(key: str) -> bool:
    """True when the registry holds a live window; a destroyed one is dropped."""
    windows = getattr(sys, "_fontlab_samples", {})
    old = windows.get(key)
    if old is None:
        return False
    try:
        old.isVisible()
    except ValueError as error:
        # PythonQt: the wrapper outlived its QWidget, as in show_script_dialog;
        # any other ValueError leaves the window registered.
        if "destroyed" not in str(error):
            return True
        del windows[key]
        return False
    return True


def main() -> None:
    """Show the filter results, then open the panel on a demo-owned settings file."""
    import fly
    from fly.ap.core.scripting import show_script_dialog
    from fly.ap.proof.text_filter import settings
    from fly.ap.proof.text_filter.model import KEY, SavedText, filter_text
    from fly.ap.proof.text_filter.ui import TextFilterDialog

    if is_open(KEY):
        notify("A Text Simplifier panel is already open. Close it, then run this demo again.")
        return
    notify(f"filter_text ran on {len(CASES)} samples.", "\n".join(filter_lines(filter_text)))
    core = fly.qt.QtCore
    try:
        path = Path(tempfile.gettempdir()) / INI
        path.parent.mkdir(parents=True, exist_ok=True)
        store = core.QSettings(str(path), core.QSettings.IniFormat)
        settings.save(store, SavedText(input=SAMPLE_INPUT))
        show_script_dialog(lambda parent: TextFilterDialog(parent, settings=store), KEY)
    except (OSError, ValueError, RuntimeError) as error:
        notify(f"The Text Simplifier panel could not open: {error}")


if __name__ == "__main__":
    main()
