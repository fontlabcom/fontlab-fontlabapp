# this_file: src/fontlabapp/contours/panel/model.py
# SPDX-License-Identifier: Apache-2.0
"""Shared panel base and colour helpers of the outline writer scripts.

What: ``panel_type()`` returns ``OutlinePanel``, the non-modal PythonQt
panel of the Contours writer scripts: script controls, the master scope, a
"Keep masters compatible" tick for scripts that change the node structure,
a consent tick for bases of automatic composites, a live preview table,
Reload selection, Close and Apply. ``ink``, ``muted`` and
``readable_palette`` give readable text colours in FontLab's light and dark
themes. ``ERROR_COLOR`` colours blocked rows; ``MAX_ROWS`` limits the
preview rows. The helpers are the same objects as in
``fontlabapp.anchors.panel.model``.

How: the panel plans with ``fontlabapp.contours.writer.collect`` on every
control change. Apply plans again from live data, scans the auto-layer
facts again and writes with ``outline_writer.apply_work`` and the script's
``editor()`` (one Undo step). A new scan clears the consent tick, because
the consent belongs to the glyphs that the user saw. Signals connect
through ``scripting.connect_guarded`` and disconnect in ``closeEvent``.

Why: each script then holds only its own logic, a small panel subclass and
``main``. ``OutlinePanel`` is its own class, not a subclass of
``fontlabapp.components.panel.model``'s ``ComponentPanel``: the scope, the ticks,
the per-glyph refusal, the error display of Apply and the status texts
differ, so a subclass would replace almost every method. This module
imports only stdlib-only App modules at load time; PythonQt loads inside
the functions, and ``panel_type()`` loads the class from
``fontlabapp.contours.panel.ui``. So FontLab's 5-second cold import stays
fast, and tests without Qt can import it. Offline tests do not prove
native panel behaviour.

How to use (a script)::

    import fly.ap.contours.panel.model as outline_panel
    import fly.ap.contours.writer as outline_writer

    class RoundCoordinates(outline_panel.panel_type()):
        TITLE, KEY, ACTION, DONE, UNIT = "Round Coordinates", "outlines_round", "Round", "Rounded", "item"

        def build_controls(self): ...
        def planner(self): ...
        def editor(self): ...
"""

import fontlabapp.core.history.glyphs as _history
from fontlabapp.anchors.panel.model import (
    ERROR_COLOR,
    MAX_ROWS,
    ink,
    muted,
    readable_palette,
)

#: Subclass hooks of ``OutlinePanel``. A script overrides them; the panel calls them.
HOOKS = (
    "after_refresh",
    "build_controls",
    "build_extra",
    "cells",
    "editor",
    "intro",
    "on_reload",
    "planner",
    "summary",
)
#: Public members of an ``OutlinePanel`` that scripts may read, call or extend.
#: They stay stable; a change is an App API change. Underscore names
#: (``_connections``) keep working but are not API.
MEMBERS = (
    "add_row",  # add_row(label, *widgets): put widgets on the next form row
    "apply",  # plan again from live data and write once; override and call it
    "apply_button",  # the action button; enabled only when the plan is safe
    "bases",  # the consent tick for bases of automatic composites
    "chosen_masters",  # chosen_masters() -> master names in scope
    "close_button",  # the Close button
    "compatible",  # the "Keep masters compatible" tick (STRUCTURAL panels)
    "current_master",  # the master that was current at the last scan
    "facts",  # history.AutoFacts of the last scan
    "glyphs",  # the scanned selected glyphs
    "last_result",  # the result dict of the last Apply
    "live_glyphs",  # live_glyphs() -> (package, glyphs); ValueError when stale
    "masters",  # every master name of the bound font
    "options",  # options() -> keyword options of outline_writer.collect
    "package",  # the bound font (flPackage) or None
    "package_id",  # flPackage.id of the bound font, for current_package()
    "refresh",  # plan again and fill the table and status line
    "reload",  # scan again; a failure shows in the status line
    "reload_button",  # the Reload selection button
    "scan",  # read font, selection and auto facts again (clears the consent)
    "scope",  # the master scope combo box: 0 current master, 1 all masters
    "slot_error",  # "" or the text of the last refusal of Reload or Apply
    "spin",  # spin(low, high, value, suffix="", decimals=0) -> watched spin box
    "status",  # the status line label
    "subtitle",  # the subtitle label (intro text)
    "table",  # the preview QTableWidget
    "timers",  # QTimers that the panel stops when it closes
    "watch",  # watch(signal, callback=None): guarded connect, default refresh
)
#: Start of the read-back error text (``history.NOT_STORED``): "FontLab did not store".
#: A status line that starts with "Error: " + this text reports a read-back gap.
NOT_STORED = _history.NOT_STORED
#: The recovery text of a failure after history started (``history.UNDO_HINT``).
UNDO_HINT = _history.UNDO_HINT


def panel_type() -> type:
    """Return the ``OutlinePanel`` base class (a PythonQt ``QDialog``).

    The class loads PythonQt, so call this inside FontLab only. Subclass it,
    set ``TITLE``, ``KEY``, ``ACTION``, ``DONE``, ``UNIT``, ``HEADERS`` (3
    or 4 columns) and ``STRUCTURAL`` (True when the edits change node counts
    or order), and fill in the hooks ``build_controls``, ``planner`` and
    ``editor``; optionally ``build_extra``, ``on_reload`` and
    ``after_refresh`` (all in ``HOOKS``). ``spin(...)`` makes a watched
    spin box. ``MEMBERS`` lists the other public members a script may
    use, for example ``slot_error``, ``status`` and ``apply_button``. See
    ``fontlabapp.contours.panel.ui.OutlinePanel`` for the full contract. Show
    it with ``scripting.show_script_dialog(Subclass, Subclass.KEY)``.
    """
    from fontlabapp.contours.panel.ui import OutlinePanel

    return OutlinePanel


__all__ = [
    "ERROR_COLOR",
    "HOOKS",
    "MAX_ROWS",
    "MEMBERS",
    "NOT_STORED",
    "UNDO_HINT",
    "ink",
    "muted",
    "panel_type",
    "readable_palette",
]
