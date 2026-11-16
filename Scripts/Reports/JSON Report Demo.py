# this_file: Scripts/Reports/JSON Report Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show a detached snapshot report: sample data formatted as indented JSON.

What: Builds a small made-up report in memory, formats it with
fontlabapp.proof.reports.model.format_report and opens it with show_report in
a read-only, nonmodal Report window. The window states that it is a detached
snapshot. A message box then reports how format_report refuses a report that
holds NaN (it would not be valid JSON) and one that exceeds a deadline.
Use: Run it from the Scripts menu. Read or select text in the window; its Close
button ends it. Run the demo again to open a fresh snapshot in the same window.
Safety: Read-only. The report is sample data created by this file, so no font
is opened or read. The window shows detached text and does not refresh itself.
Nothing is written: no font, selection, history, preference, Output or
clipboard, except what you copy yourself with the usual editing keys.
"""

KEY = "json_report_demo"  # not the shared default key, so no other report is replaced
TITLE = "JSON Report Demo"
REPORT = {
    "tool": "JSON Report Demo",
    "note": "Sample data made by the demo, not read from a font.",
    "glyphs": [
        {"name": "A", "unicode": "0041", "width": 640, "contours": 2},
        {"name": "Aacute", "unicode": "00C1", "width": 640, "components": ["A", "acutecomb"]},
        {"name": "ß", "unicode": "00DF", "width": 610, "contours": 3},
    ],
}


def refusal_lines(format_report) -> list[str]:
    """How format_report answers a report it cannot publish, one line each."""
    attempts = (
        ("NaN value", {"width": float("nan")}, {}),
        ("deadline already passed", REPORT, {"deadline": 0.0}),
    )
    lines = []
    for label, report, options in attempts:
        try:
            format_report(report, **options)
            lines.append(f"{label}: formatted")
        except (ValueError, TimeoutError) as error:
            lines.append(f"{label}: {type(error).__name__}: {error}")
    return lines


def main() -> None:
    """Open the snapshot window, then explain the refusals."""
    import fly
    from fly.ap.proof.reports.model import format_report, show_report
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    show_report(REPORT, title=TITLE, key=KEY)
    box = create_message_box(
        qt.QtGui,
        TITLE,
        "The snapshot window is open.",
        "Information",
        (fly.fl.MainWindow(),),
        detail="\n".join(refusal_lines(format_report)),
    )
    box.setWindowTitle(TITLE)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


if __name__ == "__main__":
    main()
