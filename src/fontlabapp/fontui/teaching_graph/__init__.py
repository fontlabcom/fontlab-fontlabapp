# this_file: src/fontlabapp/fontui/teaching_graph/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Graph Lab: both preserved elastic-force profiles and feature-name relationships."""

from typing import Any


def show(parent: Any = None) -> Any:
    """Embed all graph controls and own each simulation until its close ACK."""
    from fontlabapp import _native
    from fontlabapp.components.graph.elastic.ui import panel_type
    from fontlabapp.components.graph.native import capture
    from fontlabapp.fontui.teaching import host

    from . import feature_graph

    qt = _native("PythonQt")
    shell = host.create("Graph Lab", "tglyph", parent=parent)
    try:
        def capture_with_preview(**kwargs: Any) -> Any:
            host.refresh_current_preview(shell)
            return capture(**kwargs)

        graph = panel_type(qt.QtCore, qt.QtGui)
        for title, part in (("Dependency forces", 2), ("Degree forces", 3)):
            panel = graph(shell.widget, capture, part)
            panel.capture = capture_with_preview
            panel.close_button.hide()
            panel.close_button.setEnabled(False)
            owned = host.embed(shell, title, panel)
            shell.set_actions(owned, refresh=panel.refresh)
        panel = feature_graph.panel_type(qt)(shell.widget)
        panel.lab_close = lambda: shell._run_action("close")
        panel.lab_refresh_preview = lambda: host.refresh_current_preview(shell)
        owned = host.embed(shell, "Feature graph", panel)
        shell.set_actions(owned, refresh=panel.refresh)
        shell.set_about("Graph Lab\nBoth original elastic force profiles and an exact suffix feature draft.\n"
                        "Source: https://github.com/fontlabcom/fontlab-python-examples\n"
                        "FontLab contributors; Apache-2.0. Qt/Nokia and Riverbank lesson credits: package NOTICE.\n"
                        "Moving graph nodes changes only the scene. Feature text is a draft, never compiled here.")
        host.bind_current_preview(shell)
        return host.finish(shell)
    except BaseException:
        shell.close()
        raise
