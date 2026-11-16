# this_file: src/fontlabapp/fontui/teaching_writers/app.py
# SPDX-License-Identifier: Apache-2.0
"""Compose the retained editing lessons without duplicating their guarded writers."""

from importlib import import_module
from typing import Any

# Each entry preserves a separately selectable original profile.
LABS = {
    "Node Editing Lab": ("tglyph", (
        ("Node table", "node_table"),
        ("Slopes and handles", "node_slope_and_handles"),
    )),
    "Stem Interpolation Lab": ("tglyph", (
        ("Stem blend", "stem_blend"),
        ("Stem-compensated scale", "scale_with_stem_compensation"),
    )),
    "Kerning Recipe Lab": ("tmetrics", (
        ("Copy rules", "kerning_copy_rules"),
        ("Pair imports", "import_kerning_pair_list"),
    )),
    "Font Metadata Lab": (None, (
        ("Snapshot", "font_info_snapshot"),
        ("Encoding audit", "font_name_encoding_audit"),
        ("Localized names", "localized_font_names"),
    )),
    "Layer Transfer Lab": ("tglyph", (
        ("Layer copies", "copy_layers_from_font"),
        ("Metric comparison", "layer_metric_comparison"),
    )),
}

ACTIONS = {
    "node_table": ("refresh_nodes", "read_selection", "write_cells"),
    "node_slope_and_handles": ("reload", "refresh", "apply"),
    "stem_blend": ("refresh_sources", "build_result", "apply_result"),
    "scale_with_stem_compensation": ("reload_selection", "preview_scale", "create_layers"),
    "kerning_copy_rules": (None, "build_result", None),
    "import_kerning_pair_list": (None, "preview_pairs", "apply_list"),
    "font_info_snapshot": ("refresh_info", "compare_saved", None),
    "font_name_encoding_audit": ("refresh_info", "refresh_info", None),
    "localized_font_names": ("refresh_info", None, None),
    "copy_layers_from_font": ("reload_selection", "preview_copy", "copy_rows"),
    "layer_metric_comparison": ("refresh_output", "refresh_output", None),
}


def numeric_columns(table: Any, columns: tuple[int, ...]) -> None:
    """Give editable numeric cells a numeric Qt value before sorting is enabled."""
    from PythonQt import QtCore, QtGui
    from fontlabapp.qt.properties import value

    for row in range(int(value(table, "rowCount"))):
        for column in columns:
            old = table.item(row, column)
            item = QtGui.QTableWidgetItem()
            item.setData(QtCore.Qt.DisplayRole, float(value(old, "text")))
            item.setFlags(value(old, "flags"))
            table.setItem(row, column, item)


def dirty(panel: Any) -> bool:
    """Refuse Refresh while a tab holds authored cells, translations or a plan."""
    return (bool(getattr(panel, "unsaved", False))
            or getattr(panel, "plan_data", None) is not None
            or (hasattr(panel, "staged_edits") and panel.staged_edits()))


def ready(panel: Any) -> bool:
    """Respect the original panel's accepted-plan or enabled-action boundary."""
    from fontlabapp.qt.properties import value

    if hasattr(panel, "apply_button"):
        return bool(value(panel.apply_button, "isEnabled"))
    if hasattr(panel, "snapshot_data"):
        return panel.snapshot_data is not None
    return getattr(panel, "plan_data", None) is not None


def show(title: str, parent: Any = None) -> Any:
    """Open one lab with complete original controls and a captured read-only preview."""
    import PythonQt as qt
    from fontlabapp.qt.properties import value
    from fontlabapp.fontui.teaching import host

    preview, profiles = LABS[title]
    shell = host.create(title, preview, parent)
    try:
        for label, name in profiles:
            module = import_module(f"fontlabapp.fontui.teaching_writers.{name}")
            if hasattr(module, "panel_type"):
                panel = module.panel_type()(shell.tabs)
            else:
                panel = module.show(qt, shell.tabs, embedded=True)
            if hasattr(panel, "close_button"):
                panel.close_button.hide()
                panel.close_button.setEnabled(False)
            for table_name in ("master_table", "mapping_table", "preview_table", "table"):
                if hasattr(panel, table_name):
                    table = getattr(panel, table_name)
                    table.horizontalHeader().setSectionResizeMode(qt.QtGui.QHeaderView.Interactive)
                    if table_name == "master_table":
                        numeric_columns(table, tuple(range(4, int(value(table, "columnCount")))))
                    table.setSortingEnabled(True)
            owner = host.embed(shell, label, panel)
            refresh, preview_action, apply = ACTIONS[name]
            panel.lab_check_target = lambda: host.require_current_preview(shell)
            panel.lab_refresh_preview = lambda: host.refresh_current_preview(shell)
            def refresh_task(panel=panel, method=refresh, name=name):
                getattr(panel, method)()
                if shell.preview_kind is not None and name == "layer_metric_comparison":
                    host.refresh_current_preview(shell)
            shell.set_actions(
                owner,
                refresh=refresh_task if refresh else None,
                preview=getattr(panel, preview_action) if preview_action else None,
                apply=getattr(panel, apply) if apply else None,
                dirty=lambda panel=panel: dirty(panel),
                ready=lambda panel=panel: ready(panel),
            )
        if preview is not None:
            host.bind_current_preview(shell)
        return host.finish(shell)
    except BaseException:
        shell.close()
        raise
