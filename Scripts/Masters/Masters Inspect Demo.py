# this_file: Scripts/Masters/Masters Inspect Demo.py
# SPDX-License-Identifier: Apache-2.0
"""List the masters of the open font and try App's master helpers on samples.

What: Builds a report from fontlabapp.masters.inspect.model: for the open font
each master in axis order with its location (location_text) and its ascender,
cap height, x-height and descender (from FontLab's FontMetrics); and, on
made-up data, the chart ticks of nice_ticks, the layer-name rules
associated_master and backup_layer_name, and ink_area of a box with a counter.
Use: Run it from the Scripts menu and click Show Details. A font is optional:
without one only the sample sections appear.
Safety: Read-only. The font sections read master names, axis locations and the
four vertical metrics of each master; this script never switches the current
master (App's overview helper does switch it briefly to read italic angles,
so it is not called) and writes no font, master, selection, history,
preference, Output or clipboard. The sample sections use numbers in this
script. The Masters panel shell (fontlabapp.masters.inspect.ui) is not opened.
"""

TITLE = "Masters Inspect Demo"
METRICS = (("Ascender", "ascender"), ("Cap height", "capsHeight"), ("x-height", "xHeight"), ("Descender", "descender"))
BOX = [(0, 0, True), (400, 0, True), (400, 700, True), (0, 700, True)]
COUNTER = [(100, 100, True), (100, 600, True), (300, 600, True), (300, 100, True)]


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def master_lines(package) -> list[str]:
    """One line per master in axis order: location and the four vertical metrics."""
    import fly
    from fly.ap.masters.inspect import model

    lines = []
    for master in model.master_order(package):
        metrics = fly.fl.FontMetrics(package, master)
        values = ", ".join(f"{label} {float(getattr(metrics, attr)):g}" for label, attr in METRICS)
        lines.append(f"{master} ({model.location_text(package, master)}): {values}")
    return lines


def sample_lines() -> list[str]:
    """The pure helpers on made-up values."""
    from fly.ap.masters.inspect import model

    masters = ["Light", "Regular", "Bold"]
    taken = ["Regular backup first"]
    return [
        f"nice_ticks(0, 83) -> {model.nice_ticks(0, 83)}",
        f"associated_master('Regular@ 2026-10-21') -> {model.associated_master('Regular@ 2026-10-21', masters)}",
        f"associated_master('mask.Regular') -> {model.associated_master('mask.Regular', masters)}",
        f"backup_master('Bold backup trial') -> {model.backup_master('Bold backup trial', masters)}",
        f"backup_layer_name('Regular', taken, 'first') -> {model.backup_layer_name('Regular', taken, 'first', masters)}",
        f"ink_area(box 400 x 700 with a 200 x 500 counter) -> {model.ink_area([BOX, COUNTER]):g}",
    ]


def main() -> None:
    """Show the report; the font sections appear only when a font is open."""
    from fly.ap.core.scripting import current_package

    package = current_package()
    lines = ["Masters of the open font:"]
    try:
        lines += master_lines(package) if package is not None else ["No font is open."]
    except (ValueError, RuntimeError) as error:
        lines.append(f"The masters could not be read: {error}")
    lines += ["", "Sample helpers (made-up data):", *sample_lines()]
    notify(TITLE, "Masters of the open font, with sample helpers. Nothing was written.", "\n".join(lines))


if __name__ == "__main__":
    main()
