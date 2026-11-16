# this_file: src/fontlabapp/contours/selection/panel/model.py
# SPDX-License-Identifier: Apache-2.0
"""Shared panel base of the Contours scripts that work on the selected glyphs.

What: ``panel_type()`` returns ``SelectionPanel``, the non-modal PythonQt
panel of Shadow Copy, Outline Effect, Autohint Selected Layers and Remove
PostScript Hints: script controls, a master scope ("Current master" or "All
masters"), a consent tick for bases of automatic composites
(``BASES_TEXT``), a preview table, a status line and the buttons Use
selection, Close and the action. ``fontlabapp.glyphs.copies.panel_type()``
returns ``CopiesPanel``, the same base set up for the scripts that create
glyph copies.

How: the panel binds to the font that is current when it opens and takes
the Font window selection. The public ``facts`` attribute stores auto-layer
facts from construction, ``reselect()`` or ``scan()`` (explicit Refresh).
Use ``self.facts`` in ``plan_rows`` to avoid a whole-font scan for each
control signal. Every control change plans again with the
script's ``plan_rows`` and fills the table with its ``cells``. The action
plans again from the live font and calls the script's ``write`` once.
Use selection reads the selection again and clears the consent tick, because
the consent belongs to the glyphs that the user saw. A refusal
(``ValueError``, ``RuntimeError`` or ``TimeoutError``) in Use selection or
in the action shows its text in the status line. Signals connect through
``scripting.connect_guarded`` and disconnect when the panel closes.

Why: the four panels differed only in their controls, so each script now
holds only its own logic, a small panel subclass and ``main``. The panel
is not ``fontlabapp.contours.panel.model``'s ``OutlinePanel``: that one plans
``outline_writer`` rows; these scripts plan their own rows. ``MAX_ROWS`` is
the ``fontlabapp.anchors.panel.model`` limit. This module imports only
stdlib-only App modules at load time; ``panel_type()`` loads the class from
``fontlabapp.contours.selection.panel.ui``, which imports PythonQt. Offline tests do
not prove native panel behaviour.

How to use (a script)::

    import fly.ap.contours.selection.panel.model as selection_panel

    class ShadowPanel(selection_panel.panel_type()):
        TITLE, KEY, ACTION = "Shadow Copy", "generate_shadow", "Add Shadow"

        def build_controls(self): ...
        def plan_rows(self, package, masters): ...
        def cells(self, row): ...
        def pending(self, todo): ...
        def write(self, package, rows): ...
        def result_text(self, result): ...
"""

from fontlabapp.anchors.panel.model import MAX_ROWS

#: Label of the consent tick for bases of automatic composites.
BASES_TEXT = "Edit bases of auto glyphs anyway (FontLab rebuilds those auto glyphs)"
#: Glyph names shown in the subtitle before "…".
MAX_NAMES = 8
#: Subclass hooks of ``SelectionPanel``. A script overrides them; the panel calls them.
HOOKS = (
    "build_controls",
    "cells",
    "intro",
    "is_ready",
    "on_reselect",
    "on_result",
    "pending",
    "plan_rows",
    "result_text",
    "write",
)
#: Public members of a ``SelectionPanel`` that scripts may read, call or extend.
#: They stay stable; a change is an App API change. ``status``: the status
#: line label (a refusal shows its text there). ``consented()``: the consent
#: tick is ticked. Underscore names (``_connections``) keep working but are not API.
MEMBERS = (
    "add_row",
    "apply",
    "apply_button",
    "chosen_masters",
    "close_button",
    "consent",
    "consented",
    "font_masters",
    "font_package",
    "last_result",
    "names",
    "package_id",
    "plan",
    "refresh",
    "reselect",
    "rows",
    "scope",
    "selection_button",
    "status",
    "subtitle",
    "table",
    "watch",
)


def panel_type() -> type:
    """Return the ``SelectionPanel`` base class (a PythonQt ``QDialog``).

    The class loads PythonQt, so call this inside FontLab only. Subclass it,
    set ``TITLE``, ``KEY``, ``ACTION`` and ``HEADERS`` (optionally
    ``NOUN``, ``SCOPE``, ``CONSENT``, ``ALIGN``, ``WIDTH``), and fill in the
    hooks ``build_controls``, ``plan_rows``, ``cells``, ``pending``,
    ``write`` and ``result_text``; optionally ``intro``, ``on_reselect`` and
    ``on_result`` (all in ``HOOKS``). ``MEMBERS`` lists the other public
    members a script may use. See ``fontlabapp.contours.selection.panel.ui.SelectionPanel``. Show it
    with ``scripting.show_script_dialog(Subclass, Subclass.KEY)``.
    """
    from fontlabapp.contours.selection.panel.ui import SelectionPanel

    return SelectionPanel


__all__ = ["BASES_TEXT", "HOOKS", "MAX_NAMES", "MAX_ROWS", "MEMBERS", "panel_type"]
