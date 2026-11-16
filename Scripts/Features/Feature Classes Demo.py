# this_file: Scripts/Features/Feature Classes Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Preview what App's Clean Classes would remove from made-up OpenType classes.

What: Builds a sample font snapshot (glyph names and OpenType class contents,
the Snapshot of fontlabapp.features.classes.model) and prints the plan of
Clean Classes: every class that names a missing glyph, its members before and
after (changes, render). Member order and duplicates are kept; only missing
names go. The Clean Classes panel (fontlabapp.features.classes.ui) and the
native bridge (fontlabapp.features.classes.native) are only named.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The font and classes are plain
values in this script and no window opens. The panel has an Apply button that
rewrites classes in the font, and apply() in the model writes through a
bridge; neither is opened or called here, so no feature class, font, master,
selection, history, preference, Output or clipboard is touched.
"""

TITLE = "Feature Classes Demo"
NAMES = ("A", "Aacute", "B", "a", "aacute", "space")
CLASSES = (
    ("@UPPER_ACCENTED", "A Aacute Agrave Aogonek"),
    ("@lower", "a aacute a"),
    ("@Latin", "A B Cacute Cacute"),
)


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def lines() -> list[str]:
    """The sample plan, one line each."""
    from fly.ap.features.classes import model

    facts = model.Snapshot(("sample", 1), NAMES, CLASSES)
    return [f"Glyphs: {list(NAMES)}", "", *(f"{name} = [{code}]" for name, code in CLASSES), "", "Clean Classes would replace:", model.render(facts), "", f"{len(model.changes(facts))} of {len(CLASSES)} classes change."]


def main() -> None:
    """Show the sample plan; no font is needed."""
    notify(TITLE, "Sample Clean Classes plan. Nothing was read or written.", "\n".join(lines()))


if __name__ == "__main__":
    main()
