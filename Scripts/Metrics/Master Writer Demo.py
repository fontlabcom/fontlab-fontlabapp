# this_file: Scripts/Metrics/Master Writer Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Explain how App writes master vertical metrics, with checked sample values.

What: Shows, in one message box, how fontlabapp.metrics.master_writer.parse
turns a sample request into the checked values that write_master_metrics would
send to FontLab as one Undo step: the five writable fields, the capHeight
alias and what a bad request looks like. The writer itself is described, not
called.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is written. The sample is a plain dictionary that is parsed
and printed; write_master_metrics is never called, so no font, master,
selection, history, preference, Output or clipboard is touched.
"""

TITLE = "Master Writer Demo"
SAMPLE = {"Regular": {"capHeight": 700, "ascender": 750}, "Bold": {"xHeight": 510.5}}
BAD_SAMPLES = (
    {"Regular": {"hhea_line_gap": 10}},
    {"Regular": {"capHeight": 700, "capsHeight": 710}},
    {"Regular": {"ascender": float("inf")}},
    {},
)


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def explanation_lines() -> list[str]:
    """Describe the checked sample request and the refusals, using the real parser."""
    from fly.ap.metrics import master_writer

    lines = [
        "Writable fields, in write order: " + ", ".join(master_writer.FIELDS),
        "Aliases: " + ", ".join(f"{alias} -> {field}" for alias, field in master_writer.ALIASES.items()),
        f"Undo step name: {master_writer.TITLE}",
        "",
        f"Sample request: {SAMPLE}",
        f"Checked values: {master_writer.parse(SAMPLE)}",
        "",
        "Requests that are refused before any call to FontLab:",
    ]
    for bad in BAD_SAMPLES:
        try:
            master_writer.parse(bad)
        except ValueError as error:
            lines.append(f"{bad} -> {error}")
    return lines


def main() -> None:
    """Show the explanation; no font is needed and nothing is written."""
    notify(TITLE, "Sample metrics request, checked but never written.", "\n".join(explanation_lines()))


if __name__ == "__main__":
    main()
