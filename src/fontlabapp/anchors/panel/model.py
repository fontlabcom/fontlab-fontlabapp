# this_file: src/fontlabapp/anchors/panel/model.py
# SPDX-License-Identifier: Apache-2.0
"""Shared panel base and colour helpers of the anchor writer scripts.

What: ``panel_type()`` returns ``AnchorPanel``, the non-modal PythonQt panel
of the Anchors scripts: script controls, a live preview table, Reload
selection, Close and Apply. ``ink``, ``muted`` and ``readable_palette`` give
readable text colours in FontLab's light and dark themes. ``ERROR_COLOR``
colours blocked rows; ``MAX_ROWS`` limits the preview rows.

How: the panel plans with ``fontlabapp.anchors.writer`` (``collect``,
``blocked_rows``, ``require_safe``) on every control change, and Apply plans
again from live data and writes with ``anchor_writer.apply_work`` (one Undo
step). Signals connect through ``scripting.connect_guarded`` and disconnect
in ``closeEvent``.

Why: the seven Anchors scripts then hold only their planner, a small panel
subclass and ``main``. This module imports only the standard library and
stdlib-only App modules at load time; PythonQt loads inside the functions,
and ``panel_type()`` loads the class from ``fontlabapp.anchors.panel.ui``. So
FontLab's 5-second cold import stays fast, and tests without Qt can import
it. Offline tests do not prove native panel behaviour.

How to use (a script)::

    import fly.ap.anchors.panel.model as anchor_panel

    class RoundToGrid(anchor_panel.panel_type()):
        TITLE, KEY, ACTION = "Round Anchors to Grid", "anchors_round_to_grid", "Round"

        def build_controls(self): ...
        def planner(self): ...
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.metrics.panel.model import muted

#: Colour of a blocked row's last cell.
ERROR_COLOR = "#d33"
#: Preview rows shown. The edit itself is never truncated.
MAX_ROWS = 500


def ink() -> Any:
    """Return a ``QBrush`` for item text, from the main window ``WindowText``.

    FontLab's palette ``Text`` can be pale in item views, so the brush uses
    ``WindowText`` of ``fontlab.MainWindow()``.
    """
    gui = _native("PythonQt").QtGui
    palette = _native("fontlab").MainWindow().palette
    return gui.QBrush(gui.QColor(palette.color(gui.QPalette.WindowText)))


def readable_palette(widget: Any) -> None:
    """Give ``widget`` a readable ``Text`` colour in each colour group.

    For the Active and Inactive groups, keep whichever of ``Text`` and
    ``WindowText`` differs more in lightness from ``Base``, then set the
    palette on the widget.
    """
    gui = _native("PythonQt").QtGui
    palette = widget.palette
    for group in (gui.QPalette.Active, gui.QPalette.Inactive):
        base = gui.QColor(palette.color(group, gui.QPalette.Base)).lightness()
        candidates = (
            gui.QColor(palette.color(group, gui.QPalette.Text)),
            gui.QColor(palette.color(group, gui.QPalette.WindowText)),
        )
        best = max(candidates, key=lambda c: abs(c.lightness() - base))
        palette.setColor(group, gui.QPalette.Text, best)
    widget.setPalette(palette)


def panel_type() -> type:
    """Return the ``AnchorPanel`` base class (a PythonQt ``QDialog``).

    The class loads PythonQt, so call this inside FontLab only. Subclass it,
    set ``TITLE``, ``KEY``, ``ACTION`` and ``HEADERS``, and fill in the hooks
    ``build_controls`` and ``planner``; optionally ``chosen_masters``,
    ``glyph_names`` and ``on_reload``. See
    ``fontlabapp.anchors.panel.ui.AnchorPanel`` for the full contract. Show it
    with ``scripting.show_script_dialog(Subclass, Subclass.KEY)``.
    """
    from fontlabapp.anchors.panel.ui import AnchorPanel

    return AnchorPanel


__all__ = [
    "ERROR_COLOR",
    "MAX_ROWS",
    "ink",
    "muted",
    "panel_type",
    "readable_palette",
]
