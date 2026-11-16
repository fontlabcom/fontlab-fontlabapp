# this_file: Scripts/Utilities/Shim Generator Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Replay a tiny made-up FontLab menu capture and show the shim App generates.

What: Feeds a three-action sample capture (a File and a Glyph menu and one
Tools > Actions entry) to fontlabapp.core.shimgen: replay builds the Host
tree, generate_pyi builds the typed stub and generate_py the lazy loader.
A modeless message box lists the replayed menus, action paths and glyph
actions, the stub's header lines and the typed names it declares.
Use: Run it from the Scripts menu and click Show Details. Compare the typed
names with the sample menu labels; the real capture has hundreds of actions.
Safety: Read-only. The capture is a literal in this script, so nothing is
read from FontLab or from disk. replay uses stand-in actions that cannot run
anything, and the two generators return strings. write(), which saves the
shim package to disk, is never called. No font, selection, history,
preference, Output or clipboard is read or written.
"""

import re

_BOXES: list = []  # modeless boxes stay referenced until the user closes them
TITLE = "Shim Generator Demo"
MEMBER = re.compile(r"^    (\w+): (\w+)$")


def action(name: str, text: str, shortcut: str = "") -> dict:
    """One captured QAction record, shaped like generated/fontlabapp_shim/capture.json."""
    record = {"objectName": f"action{name}", "statusTip": f"@mainwindow.action{name}", "text": text}
    record["toolTip"] = text.replace("&", "")
    return {**record, "shortcut": shortcut} if shortcut else record


SAMPLE = {
    "schema": 1,
    "host": {"app": "fontlab9", "app_version": "9.0.0", "locale": "en", "qt_version": None},
    "captured": "2026-01-01",
    "menus": [
        {"objectName": "menuFile", "title": "&File", "entries": [action("NewFont", "&New Font", "Ctrl+N"), action("SaveFont", "&Save Font...", "Ctrl+S")]},
        {"objectName": "menuGlyph", "title": "&Glyph", "entries": [action("Add_Component", "Add &Component")]},
    ],
    "actions": [],
    "catalogue": {"actions": [{"id": "remove_overlap", "label": "remove overlap"}], "count": 1},
    "widgets": [],
}  # fmt: skip


def host_lines(host) -> list[str]:
    """The replayed menus, every action path and the Tools > Actions ids."""
    return [
        f"menu bar: {', '.join(host.menu.items())}",
        *(f"action: {path}" for path in host.actions),
        f"glyph actions: {', '.join(host.glyph_actions.items())}",
    ]


def stub_lines(pyi: str, py: str) -> list[str]:
    """The stub's first three lines, the loader's first line and the typed names."""
    lines = pyi.splitlines()
    members = [f"{m[1]}: {m[2]}" for m in map(MEMBER.match, lines) if m]
    return [*lines[:3], py.splitlines()[0], "typed names: " + ", ".join(members)]


def notify(text: str, details: str) -> None:
    """Show one modeless, owned message box with selectable details."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, release_closed_message_boxes, show_message_box

    release_closed_message_boxes(_BOXES)
    qt = fly.qt
    box = create_message_box(qt.QtGui, TITLE, text, "Information", (fly.fl.MainWindow(),), detail=details)

    def configure(current) -> None:
        current.setWindowTitle(TITLE)

    show_message_box(box, _BOXES, configure)


def main() -> None:
    """Replay the sample, generate both shim files in memory and show them."""
    from fly.ap.core.shimgen import generate_py, generate_pyi, replay

    lines = [*host_lines(replay(SAMPLE)), "", *stub_lines(generate_pyi(SAMPLE), generate_py(SAMPLE))]
    notify("Click Show Details for the replayed menus and the generated stub.", "\n".join(lines))


if __name__ == "__main__":
    main()
