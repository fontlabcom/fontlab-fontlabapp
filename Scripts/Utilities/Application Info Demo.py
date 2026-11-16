# this_file: Scripts/Utilities/Application Info Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show FontLab's versions, system, folders and preference library in one report.

What: Opens a message box whose details list the application, operating system,
Python and Qt versions (fontlabapp.core.application.versions), the application
and user folders (paths) and the top-level keys of the preference library file.
Use: Run it from the Scripts menu. Click Show Details for the full report; the
text can be selected and copied.
Safety: Read-only. It builds the application object without its preference
library or UI parts and reads the preference file as plain JSON, so nothing is
created, saved or changed. No font, setting, Output or clipboard is touched.
"""

import json

_BOXES: list = []  # modeless boxes stay referenced until the user closes them


def preflib_lines(path) -> list[str]:
    """Describe the preference library file without creating or saving it."""
    if not path.is_file():
        return [f"Preference library: {path} (not created yet)"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"Preference library: {path} (unreadable: {error})"]
    if not isinstance(data, dict):
        return [f"Preference library: {path} (not a JSON object)"]
    return [f"Preference library: {path}", f"  top-level keys: {', '.join(sorted(data)) or 'none'}"]


def report_lines(app) -> list[str]:
    """Collect the read-only version, folder and preference report."""
    v, p = app.versions, app.paths
    lines = [
        f"Application: {v.app_name} {v.app_version} ({v.app_arch})",
        f"Operating system: {v.os_full_name}, version {v.os_version} ({v.os_arch})",
        f"Python: {v.py_version}",
        f"Qt: {v.qt_version}",
        "",
    ]
    folders = (
        ("Application folder", p.appFolder),
        ("Application data", p.appDataFolder),
        ("User data", p.userDataFolder),
        ("User preferences", p.sysUserPrefFolder),
        ("Temporary files", p.tempFolder),
    )
    lines += [f"{label}: {path}" for label, path in folders]
    return lines + [""] + preflib_lines(p.appPrefLibPath)


def show_report(app, title: str, summary: str, lines: list[str]) -> None:
    """Show the report as a modeless, owned message box with selectable details."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, release_closed_message_boxes, show_message_box

    release_closed_message_boxes(_BOXES)
    box = create_message_box(fly.qt.QtGui, title, summary, "Information", (app.main,), detail="\n".join(lines))

    def configure(current) -> None:
        current.setWindowTitle(title)

    show_message_box(box, _BOXES, configure)


def main() -> None:
    """Build the application object read-only and show its report."""
    from fly.ap.core.application.context import Application

    app = Application(with_ui=False, with_preflib=False)
    lines = report_lines(app)
    show_report(app, "Application Info Demo", "Click Show Details for the full report.", lines)


if __name__ == "__main__":
    main()
