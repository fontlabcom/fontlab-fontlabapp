# this_file: src/fontlabapp/components/panel/model.py
# SPDX-License-Identifier: Apache-2.0
"""Shared panel base and colour helpers of the component writer scripts.

What: ``panel_type()`` returns ``ComponentPanel``, the non-modal PythonQt
panel of the Components scripts (Align By Anchor, Build From Recipes, Copy
Offsets Between Masters, Decompose, Nested Finder, Replace Reference, Unlock
Lock): script controls, a live preview table, Reload selection, Close and
Apply. ``ink``, ``muted`` and ``readable_palette`` give readable text colours
in FontLab's light and dark themes. ``ERROR_COLOR`` colours blocked rows;
``MAX_ROWS`` limits the preview rows. The helpers are the same objects as in
``fontlabapp.anchors.panel.model`` and ``fontlabapp.metrics.panel.model``.

How: the panel plans with ``fontlabapp.components.writer`` (``collect``,
``blocked_rows``, ``require_safe``) on every control change. Apply plans
again from live data, scans the auto-layer facts again and writes with
``component_writer.apply_work`` and the script's ``editor()`` (one Undo
step). Signals connect through ``scripting.connect_guarded`` and disconnect
in ``closeEvent``.

Why: each script then holds only its planner, a small panel subclass and
``main``. This module imports only stdlib-only App modules at load time;
PythonQt loads inside the functions, and ``panel_type()`` loads the class
from ``fontlabapp.components.panel.ui``. So FontLab's 5-second cold import
stays fast, and tests without Qt can import it. Offline tests do not prove
native panel behaviour.

How to use (a script)::

    import fly.ap.components.panel.model as component_panel
    import fly.ap.components.writer as component_writer

    class Decompose(component_panel.panel_type()):
        TITLE, KEY, ACTION, DONE = "Decompose Components", "components_decompose", "Decompose", "Decomposed"
        HEADERS = ("Glyph · master", "Component", "Becomes")

        def build_controls(self): ...
        def planner(self): ...

        def editor(self):
            return component_writer.EjectEditor(unlock=True)
"""

from fontlabapp.anchors.panel.model import ERROR_COLOR, MAX_ROWS, ink, readable_palette
from fontlabapp.metrics.panel.model import muted


def panel_type() -> type:
    """Return the ``ComponentPanel`` base class (a PythonQt ``QDialog``).

    The class loads PythonQt, so call this inside FontLab only. Subclass it,
    set ``TITLE``, ``KEY``, ``ACTION``, ``DONE`` and ``HEADERS`` (3 or 4
    columns), and fill in the hooks ``build_controls``, ``planner`` and
    ``editor``; optionally ``first_scan``, ``glyph_names``, ``on_reload``,
    ``summary``, ``cells`` and ``after_apply``. See
    ``fontlabapp.components.panel.ui.ComponentPanel`` for the full contract.
    Show it with ``scripting.show_script_dialog(Subclass, Subclass.KEY)``.
    """
    from fontlabapp.components.panel.ui import ComponentPanel

    return ComponentPanel


__all__ = [
    "ERROR_COLOR",
    "MAX_ROWS",
    "ink",
    "muted",
    "panel_type",
    "readable_palette",
]
