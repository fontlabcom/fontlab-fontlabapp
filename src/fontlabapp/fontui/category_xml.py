# this_file: src/fontlabapp/fontui/category_xml.py
# SPDX-License-Identifier: Apache-2.0
"""Owned category XML pane using the original complete font snapshot policy."""

from typing import Any


def category_report(shell: Any, classify: Any) -> Any:
    """Own the complete ordered category fragment and its refresh callback."""
    from PythonQt import QtGui
    from fontlabapp.features.categories import model
    from fontlabapp.fontui.lifecycle import Owned

    tab = Owned(shell.widget)
    tab.output = QtGui.QPlainTextEdit(tab.widget)
    tab.output.setReadOnly(True)
    tab.output.setAccessibleName("Categories to XML Lib Key")
    help_text = QtGui.QLabel(
        "All glyphs in font order. Mark becomes mark; all other categories become base. "
        "Select the XML fragment for manual insertion into a UFO lib dictionary. "
        "No font or file changes. Adapted from Simon Cozens (MIT).", tab.widget
    )
    help_text.setWordWrap(True)
    tab.layout.addWidget(help_text)
    tab.layout.addWidget(tab.output, 1)

    def refresh() -> None:
        tab.output.clear()
        try:
            if classify is None:
                raise ValueError("Category XML needs GlyphData; use the Scriptmix launcher.")
            shell.font_audit.package()
            report = model.capture(classify)
            shell.font_audit.package()
            tab.output.setPlainText(model.render(report))
            shell.set_status(f"{len(report.rows)} glyphs. No font or file changes.")
        except Exception as error:  # noqa: BLE001 - contain native capture and Qt callbacks
            tab.output.clear()
            shell.set_status(str(error))

    tab.refresh = refresh
    shell.set_actions(tab, refresh=refresh)
    refresh()
    return tab

