# this_file: Scripts/Metrics/Alignment Zones Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show the alignment zones of the current master and a sample zone suggestion.

What: Reads the top and bottom PostScript alignment zones of the current
master (fontlabapp.metrics.zones.native.read_zones) and lists their position,
width and name in one message box. It also shows what
fontlabapp.metrics.zones.model.suggest proposes for sample x-height, cap height
and o and O extents, so you can see how a baseline, x-height and cap height
zone are derived.
Use: Open a font and run it, then click Show Details. Without a font only the
sample suggestion is shown.
Safety: Display only. It reads the zone lists of the current master and
never switches the master. The sample is plain numbers that are printed, not
applied. Alignment Zones editing and writing is not part of this demo: no
font, master, selection, history, preference, Output or clipboard is written.
"""

TITLE = "Alignment Zones Demo"
SAMPLE = {"x_height": 500, "caps_height": 700, "lower": (-10, 510), "upper": (-12, 712)}


def zone_lines(label: str, zones: tuple) -> list[str]:
    """One line per zone, or a note that the list is empty."""
    if not zones:
        return [f"{label}: none"]
    return [f"{label}: {zone.name!r} at {zone.position:g}, width {zone.width:g}" for zone in zones]


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def main() -> None:
    """Collect the current zones and the sample suggestion, then show them."""
    from fly.ap.core.scripting import current_package
    from fly.ap.metrics.zones.model import suggest
    from fly.ap.metrics.zones.native import read_zones

    lines = []
    package = current_package()
    summary = "Open a font to see its zones. Nothing was changed."
    if package is not None:
        try:
            zones = read_zones(package)
            lines += [f"Master {package.master}", *zone_lines("Top", zones.top), *zone_lines("Bottom", zones.bottom), ""]
            summary = f"Zones of master {package.master}. Nothing was changed."
        except (ValueError, RuntimeError) as error:
            summary = f"The zones could not be read: {error}"
    suggestion = suggest(SAMPLE["x_height"], SAMPLE["caps_height"], SAMPLE["lower"], SAMPLE["upper"])
    lines += [f"Sample suggestion for {SAMPLE} (not applied):", *zone_lines("Top", suggestion.top), *zone_lines("Bottom", suggestion.bottom)]
    notify(TITLE, summary, "\n".join(lines))


if __name__ == "__main__":
    main()
