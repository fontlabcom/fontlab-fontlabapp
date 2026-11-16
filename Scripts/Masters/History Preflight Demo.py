# this_file: Scripts/Masters/History Preflight Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Ask App's undo-step helpers what they would refuse in the open font.

What: Calls two read-only checks of fontlabapp.core.history. glyphs.
scan_auto_facts(package) reads every layer and lists the glyphs that own
auto layers, the base glyphs each is built from and the auto glyphs FontLab
would rebuild when a base changes. masters.require_font_window(package,
native) says whether a master write could start now (GUI thread, Font window
active, no Glyph window as the active canvas) and prints the refusal text if
not. A message box shows both answers.
Use: Open a font, run it from the Scripts menu and click Show Details. Run it
again after clicking into a Glyph window to see the refusal. A large font
makes the scan slow, and FontLab waits until the box appears.
Safety: Read-only. scan_auto_facts reads glyph names and layers through
FontGate and package.findName; require_font_window reads the active panel
and canvas. It starts no history step, switches no master and does not call
commit or commit_masters. No font, selection, preference, Output or
clipboard is written. Without an open font it only says so.
"""

TITLE = "History Preflight Demo"
SHOWN = 12  # lines listed per section


def auto_lines(facts) -> list[str]:
    """Each auto owner with its bases, then the auto glyphs a base change rebuilds."""
    owners = sorted(facts.autos)
    lines = [
        f"{owner}: built from {', '.join(sorted(base for base, users in facts.users.items() if owner in users)) or 'no components'}"
        for owner in owners[:SHOWN]
    ]
    rebuilt = [(base, facts.dependants(base)) for base in sorted(facts.users)]
    lines += [f"Changing {base} rebuilds: {', '.join(found)}" for base, found in rebuilt if found][:SHOWN]
    return lines or ["No glyph owns an auto layer."]


def window_text(require_font_window, package, native) -> str:
    """Would a master write be allowed now, or the refusal text."""
    try:
        require_font_window(package, native)
    except ValueError as error:
        return f"A master write would be refused now: {error}"
    return "A master write would be allowed now."


def notify(text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, TITLE, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(TITLE)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def main() -> None:
    """Report the auto-layer facts and the master-write precondition."""
    import fly
    from fly.ap.core import scripting
    from fly.ap.core.history.glyphs import scan_auto_facts
    from fly.ap.core.history.masters import require_font_window

    package = scripting.current_package()
    if package is None:
        notify("Open a font first: there is nothing to check.")
        return
    try:
        autos = auto_lines(scan_auto_facts(package))
    except ValueError as error:  # a glyph vanished while scanning
        autos = [f"Auto layers could not be scanned: {error}"]
    gate = window_text(require_font_window, package, fly.fl)
    notify(gate, "\n".join(["Auto layers:", *autos]))


if __name__ == "__main__":
    main()
