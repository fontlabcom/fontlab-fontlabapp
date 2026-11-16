# this_file: src/fontlabapp/fontui/teaching_text/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Text, scripting and inspection labs with retained, independently owned panels."""

from importlib import import_module
from typing import Any


PROFILES = {
    "Text Editors Lab": ("tmetrics", (("Rich letter", "handoff"), ("Review notes", "review"), ("Feature draft", "feature"))),
    "Scripting Workbench": (None, (("Snippet notebook", "notebook"), ("Scaffold", "scaffold"), ("Qt slots", "slots"), ("Icons", "icons"), ("Palette roles", "palette"))),
    "Snapshot Lab": ("tglyph", (("Inventory tabs", "inventory"), ("XML model", "xml"), ("Console", "console"), ("Diff", "diff"))),
    "Font Inspection Lab": ("tglyph", (("Paths", "paths"), ("Symbol tags", "tags"))),
}
REFRESH = {
    "scaffold": "preview", "slots": "read_slots", "icons": "preview",
    "palette": "preview", "inventory": "preview", "xml": "refresh",
    "console": "capture_rows", "diff": "capture_latest",
    "paths": "refresh_report", "tags": "refresh_output",
}


def show(title: str, parent: Any = None, *, font: Any = None,
         name: str | None = None, layer: str | None = None) -> Any:
    """Embed complete teaching controls; keep drafts and close refusals per tab."""
    from fontlabapp.fontui.teaching import host

    preview, profiles = PROFILES[title]
    shell = host.create(title, preview, parent=parent)
    try:
        owners = []
        for label, module_name in profiles:
            panel = import_module(__name__ + "." + module_name).build(shell.tabs)
            panel.lab_close = lambda: shell._run_action("close")
            if preview:
                panel.lab_refresh_preview = lambda: host.refresh_current_preview(shell)
            owners.append((module_name, host.embed(shell, label, panel), panel))
        if preview:
            if font is None:
                host.bind_current_preview(shell)
            else:
                host.bind_preview(shell, font, name=name, layer=layer)
        for module_name, owner, panel in owners:
            shell.set_actions(
                owner, refresh=getattr(panel, REFRESH.get(module_name, ""), None),
                preview=(lambda: refresh_preview(shell)) if preview else None,
                dirty=lambda panel=panel: bool(getattr(panel, "dirty", False)),
            )
        return host.finish(shell)
    except BaseException:
        shell.close()
        raise


def refresh_preview(shell: Any) -> None:
    """Refresh the current proof owner, including after a tab replaced it."""
    if shell.preview is None:
        raise ValueError("Capture a font in this tab before refreshing its preview.")
    shell.preview.refresh()
