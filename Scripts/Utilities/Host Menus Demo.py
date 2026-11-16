# this_file: Scripts/Utilities/Host Menus Demo.py
# SPDX-License-Identifier: Apache-2.0
"""List FontLab's menus, panels and Tools > Actions as fontlabapp sees them.

What: Opens a message box whose details count the entries of every top-level
menu with the Python name fontlabapp.core.menu_names gives it, show each
panel's visibility from fontlabapp.core.host and list the Tools > Actions ids.
Use: Run it from the Scripts menu. Click Show Details for the full report.
Safety: Read-only. It reads menu, panel and action state only. No menu action
is triggered, no panel is shown or hidden and no font, selection, history,
preference, Output or clipboard is touched.
"""

_BOXES: list = []  # modeless boxes stay referenced until the user closes them
ACTION_PREVIEW = 12  # Tools > Actions ids listed before the count summary


def count_entries(menu, menu_type) -> tuple[int, int, int]:
    """Return (actions, submenus, shortcuts) below ``menu``, recursively."""
    actions = submenus = shortcuts = 0
    for child in menu:
        if isinstance(child, menu_type):
            submenus += 1
            sub_actions, sub_menus, sub_shortcuts = count_entries(child, menu_type)
            actions, submenus, shortcuts = actions + sub_actions, submenus + sub_menus, shortcuts + sub_shortcuts
        else:
            actions += 1
            shortcuts += bool(child.shortcut)
    return actions, submenus, shortcuts


def menu_lines(host, menu_type, snake) -> list[str]:
    """One line per top-level menu: Python name, actions, submenus, shortcuts."""
    lines = []
    for top in host.menu:
        if isinstance(top, menu_type):
            actions, submenus, shortcuts = count_entries(top, menu_type)
            lines.append(f"{top.title} (menu.{snake(top.title)}): {actions} actions, {submenus} submenus, {shortcuts} shortcuts")
    return lines


def panel_lines(host) -> list[str]:
    """One line per panel; visibility is read only where FontLab exposes it."""
    lines = []
    for panel in host.panels:
        state = ("visible" if panel.visible else "hidden") if panel.supported else "visibility not readable"
        lines.append(f"{panel.label}: {state}")
    return lines


def action_lines(host) -> list[str]:
    """The Tools > Actions catalogue ids, previewed."""
    ids = list(host.glyph_actions.items())
    shown = ", ".join(ids[:ACTION_PREVIEW]) + (", ..." if len(ids) > ACTION_PREVIEW else "")
    return [f"{len(ids)} actions: {shown}"]


def show_report(host, title: str, summary: str, lines: list[str]) -> None:
    """Show the report as a modeless, owned message box with selectable details."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, release_closed_message_boxes, show_message_box

    release_closed_message_boxes(_BOXES)
    box = create_message_box(fly.qt.QtGui, title, summary, "Information", (host.main,), detail="\n".join(lines))

    def configure(current) -> None:
        current.setWindowTitle(title)

    show_message_box(box, _BOXES, configure)


def main() -> None:
    """Read the live menu, panel and action trees and show them."""
    from fly.ap.core.host import Menu, live
    from fly.ap.core.menu_names import snake

    host = live()
    menus, panels = menu_lines(host, Menu, snake), panel_lines(host)
    lines = ["Menus:"] + menus + ["", "Panels:"] + panels + ["", "Tools > Actions:"] + action_lines(host)
    show_report(host, "Host Menus Demo", f"{len(menus)} menus and {len(panels)} panels read.", lines)


if __name__ == "__main__":
    main()
