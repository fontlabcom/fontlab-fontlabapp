# this_file: src/fontlabapp/fontui/teaching_painter/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Painter Lab: retained SVG, reference, sketch and polygon teaching controls."""

from typing import Any


def polygon_actions(shell: Any, panel: Any, owned: Any) -> None:
    """Only an accepted preview with unchanged controls and target may draw."""
    from fontlabapp.fontui.teaching import host

    accepted: dict[str, Any] = {}
    panel.lab_accept_preview = lambda parameters: accepted.update(parameters=parameters, target=shell.preview_context)

    def ready() -> bool:
        host.require_current_preview(shell)
        if (accepted.get("parameters") != panel.parameters()
                or accepted.get("target") != shell.preview_context):
            raise ValueError("Preview Changes with these polygon settings before drawing.")
        return True

    panel.lab_check_target = ready
    panel.lab_applied = accepted.clear
    shell.set_actions(owned, preview=lambda: panel.publish(False), apply=panel.draw_polygon,
                      ready=ready, apply_label="Draw in Current Layer")


def show(parent: Any = None) -> Any:
    """Build four independent tasks without discarding their staged artwork."""
    from fontlabapp import _native
    from fontlabapp.fontui.teaching import host

    from . import outline_svg, polygon, sketch, svg_reference

    qt = _native("PythonQt")
    shell = host.create("Painter Lab", "tglyph", parent=parent)
    try:
        for title, module in (("SVG export", outline_svg), ("SVG reference", svg_reference),
                              ("Sketch", sketch), ("Polygon", polygon)):
            panel = module.panel_type(qt)(shell.widget)
            panel.lab_close = lambda: shell._run_action("close")
            panel.lab_refresh_preview = lambda: host.refresh_current_preview(shell)
            panel.lab_check_target = lambda: host.require_current_preview(shell)
            owned = host.embed(shell, title, panel)
            if title == "SVG export":
                shell.set_actions(owned, refresh=panel.capture_result, preview=panel.refresh_proof)
            elif title == "SVG reference":
                shell.set_actions(owned, preview=panel.compare)
            elif title == "Sketch":
                shell.set_actions(owned, refresh=panel.preview, preview=panel.svg_text,
                                  dirty=lambda panel=panel: bool(panel.canvas.strokes))
            else:
                polygon_actions(shell, panel, owned)
        shell.set_about("Painter Lab\nSVG export, local SVG reference, scratch strokes and star polygons.\n"
                        "Source: https://github.com/fontlabcom/fontlab-python-examples\n"
                        "FontLab contributors; Apache-2.0. Retained Qt/Nokia and Riverbank lesson credits: package NOTICE.\n"
                        "Sketch strokes stay local. Polygon drawing uses the guarded App history writer.")
        host.bind_current_preview(shell)
        return host.finish(shell)
    except BaseException:
        shell.close()
        raise
