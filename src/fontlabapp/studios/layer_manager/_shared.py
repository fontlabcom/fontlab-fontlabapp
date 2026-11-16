# this_file: src/fontlabapp/studios/layer_manager/_shared.py
# SPDX-License-Identifier: Apache-2.0
"""Pieces every Layer Manager tab shares: backends, the Undo label, one write route, the plan tab.

What: ``backends()`` returns ``core.scripting.layer_manager_backends()``
(tests replace it); ``Modules`` lets the verbatim originals keep reading
their module names. ``label`` builds ``"Layer Manager: <action> <subject>"``.
``commit`` is the one write route of the tabs: ``tool.shell.history`` over
explicit live layers (None when refused; the shell status says why).
``PlanTab`` is the host-mode form of the originals' panels: the tab's
controls, a sortable ``GlyphTable`` dry run (a row choice shows that glyph
and layer in the TGlyph preview), a status line, "Use selection" (rebinds
the tab to the current font and its Font-window selection, as the
originals' button and their open did) and one explicit verb button. Apply
plans again from the bound font and refuses a plan that differs from the
list on screen (``STALE``), then writes. Used by
``fontlabapp.studios.layer_manager``.
"""

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import layer_manager_backends

from .._kerning import ERRORS, NO_FONT, Tool
from .._kerning_ui import Panel, button, get, label as text_label

APP = "Layer Manager"
STALE = "The layers changed since the list was made; check the list again."


def backends() -> Any:
    """The reused App backends (tests replace this)."""
    return layer_manager_backends()


class Modules:
    """A module name the verbatim originals read; resolves to one reused backend."""

    def __init__(self, attribute: str) -> None:
        self.attribute = attribute

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(getattr(backends(), self.attribute), name)


class Qt:
    """``fly.qt`` as the originals read it: ``qt.QtGui`` and ``qt.QtCore``."""

    QtCore, QtGui = QtCore, QtGui


def ident(item: Any) -> int | None:
    """``int(item.id)`` of a native object, or None for a missing one.

    Stale keys use the native id, never Python ``id()``: PythonQt may hand
    back a new wrapper for the same layer or glyph on each read.
    """
    return None if item is None else int(item.id)


def subject(names: Iterable[str]) -> str:
    """Undo-label subject: the glyph name, or ``"N glyphs"`` for several."""
    unique = list(dict.fromkeys(str(n) for n in names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def label(action: str, names: Iterable[str]) -> str:
    """``"Layer Manager: <action> <glyph or N glyphs>"``."""
    return f"{APP}: {action} {subject(names)}"


def commit(
    tool: Tool,
    title: str,
    layers: Sequence[Any],
    glyphs: Sequence[Any],
    mutate: Callable[[], Any],
    *,
    read_back: Callable[[], Iterable[str]] | None = None,
    retain: Sequence[Any] = (),
    allow_bases: bool = False,
    window: int | None = None,
) -> Any:
    """ONE named Undo step through ``tool.shell.history``; None when refused.

    ``layers=[]`` is the originals' layer-creating write (new layers are
    returned by ``mutate``). ``window`` is passed only when given (the
    Copy Layers From Font selection-window and no-editors guards).
    """
    extra: dict[str, Any] = {} if window is None else {"window": window}
    if allow_bases:
        extra["allow_bases"] = True
    return tool.shell.history(title, list(glyphs), mutate, layers=list(layers), read_back=read_back,
                              retain=list(retain), **extra)  # fmt: skip


def refusal_text(tool: Tool) -> str:
    """The shell status text after a refused write; PythonQt exposes ``text`` as a property."""
    return str(get(tool.shell.status.text)) or "The write was refused."


def apply_editor(
    tool: Tool, title: str, work: list[Any], editor: Any, *, allow_bases: bool = False
) -> Any:
    """``masters.layers.writer.apply_work`` through ``tool.shell.history``; None when refused.

    ``prepare`` before history, ``write`` and ``settle`` per layer inside it,
    the removed native objects retained, ``check`` as read-back; a read-back
    gap raises the shared ``history.unstored_error`` as the original did.
    """
    layers = [layer for _, layer, _ in work]
    if not layers:
        return {"pending_updates": (), "pending_note": "", "edits": 0, "layers": 0}
    found = backends()
    glyphs = list({glyph.name: glyph for glyph, _, _ in work}.values())
    prepared = [(layer, editor.prepare(layer, edits)) for _, layer, edits in work]
    retain = [item for _, steps in prepared for item in editor.retain(steps)]

    def mutate() -> None:
        for layer, steps in prepared:
            editor.write(layer, steps)
            found.layers.settle(layer)

    done = commit(tool, title, layers, glyphs, mutate, read_back=lambda: editor.check(prepared), retain=retain,
                  allow_bases=allow_bases)  # fmt: skip
    if done is None:
        return None
    if done.mismatches:
        raise _history().unstored_error(done.mismatches)
    return result_dict(
        done, edits=sum(len(edits) for _, _, edits in work), layers=len(work)
    )


def _history() -> Any:
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

    return history


def result_dict(done: Any, **values: Any) -> dict[str, Any]:
    """The originals' result dict around a ``Committed``."""
    return {"pending_note": done.pending_note, "pending_updates": getattr(done, "pending_updates", ()),
            "mismatches": list(done.mismatches), **values}  # fmt: skip


def append_note(text: str, result: dict[str, Any]) -> str:
    """``edit_guards.append_note``: the result text and its pending note."""
    return backends().guards.append_note(text, result)


def hline(layout: Any) -> Any:
    line = QtGui.QHBoxLayout()
    layout.addLayout(line)
    return line


class PlanTab(Panel):
    """One original panel as a tab: controls, dry-run table, Use selection and the verb button.

    Subclasses set ``ACTION`` (the original button), ``HEADERS`` and the
    bound-font refusals ``NO_FONT_TEXT``/``CHANGED_TEXT``; they implement
    ``build_controls(form)``, ``plan()`` (from ``self.bound()`` and
    ``self.names``), ``rows(items)`` (``GlyphRow`` tuples), ``summary(items)``,
    ``key(items)`` (what Apply compares) and ``write(items)`` (a result
    text, or None when the shell refused).
    """

    ACTION = "Apply"
    HEADERS: tuple[str, ...] = ("Glyph",)
    RESELECT = "Use selection"
    NO_FONT_TEXT = "Open a font and select glyphs. Then run this script again."
    CHANGED_TEXT = "The font changed. Run this script again."
    #: Plan refusals the original showed in the status line (the rest go to the subtitle).
    STATUS_REFUSALS: tuple[str, ...] = ()

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.ready = False
        self.package_id: int | None = None
        self.names: list[str] = []
        self.items: list[Any] = []
        self.shown: Any = None
        self.form = QtGui.QVBoxLayout()
        self.layout.addLayout(self.form)
        self.build_controls(self.form)
        self.grid = self.table(list(self.HEADERS), self.row_chosen)
        self.status = text_label(self.widget, self.layout)
        self.buttons = hline(self.layout)
        self.build_buttons(self.buttons)
        self.ready = True

    # hooks -------------------------------------------------------------------
    def build_controls(self, form: Any) -> None:
        pass

    def build_buttons(self, line: Any) -> None:
        if self.RESELECT:
            self.reselect_button = button(
                self.widget, line, self.RESELECT, self.contain(self.reselect)
            )
        self.apply_button = button(self.widget, line, self.ACTION, self.press)

    def plan(self) -> Any:
        return []

    def rows(self, items: list[Any]) -> list[tuple]:
        return []

    def summary(self, items: list[Any]) -> str:
        return ""

    def key(self, items: list[Any]) -> Any:
        return tuple(self.rows(items))

    def ready_items(self, items: list[Any]) -> bool:
        return bool(items)

    def write(self, items: list[Any]) -> str | None:
        return None

    def selection(self) -> list[str]:
        """The Font-window selection the original reads (``names_selected_names``)."""
        return self.tool.selected_names()

    def subtitle_text(self) -> str:
        shown = ", ".join(self.names[:8]) + (" …" if len(self.names) > 8 else "")
        count = len(self.names)
        return f"{count} glyph{'' if count == 1 else 's'}: {shown}"

    # binding -----------------------------------------------------------------
    def bind(self) -> None:
        """Bind to the current font and its selection (the original's open / Use selection)."""
        package = self.tool.shell.package()
        self.package_id = None if package is None else package.id
        self.names = [] if package is None else list(self.selection())

    def bound(self) -> Any:
        """The bound font; refuse a closed or switched font (the original's texts)."""
        if self.package_id is None:
            raise ValueError(self.NO_FONT_TEXT)
        package = self.tool.shell.package()
        if package is None or package.id != self.package_id:
            raise ValueError(self.CHANGED_TEXT)
        return package

    def refresh(self) -> None:
        if (
            self.package_id is None
            or self.tool.package is None
            or self.tool.package.id != self.package_id
        ):
            self.reselect()
        else:
            self.redraw()

    def reselect(self) -> None:
        """Use selection: bind to the current font and selection again, then plan.

        A selection that cannot be read (changed while read, timed out)
        unbinds the tab and shows why.
        """
        try:
            self.bind()
        except ERRORS as error:
            self.package_id, self.names = None, []
            self.clear()
            self.subtitle.setText(str(error))
            self.status.setText("")
            return
        self.redraw()

    def clear(self) -> None:
        self.items, self.shown = [], None
        self.grid.set_rows([])
        self.apply_button.setEnabled(False)

    def redraw(self) -> None:
        """Plan from the bound font; a refusal clears the list and disables the verb button."""
        if not self.ready:
            return
        try:
            items = self.plan()
        except ERRORS as error:
            self.clear()
            if str(error) in self.STATUS_REFUSALS:
                self.status.setText(str(error))
            else:
                self.subtitle.setText(
                    NO_FONT
                    if self.tool.package is None and not str(error)
                    else str(error)
                )
                self.status.setText("")
            return
        self.items, self.shown = items, self.key(items)
        self.subtitle.setText(self.subtitle_text())
        self.grid.set_rows(self.rows(items))
        self.apply_button.setEnabled(self.ready_items(items))
        self.status.setText(self.summary(items))

    def press(self) -> None:
        self.run(self.apply)

    def checked(self) -> list[Any]:
        """Plan again; refuse a plan that is not the list on screen."""
        items = self.plan()
        if self.shown is None or self.key(items) != self.shown:
            self.redraw()
            raise ValueError(STALE)
        return items

    def apply(self) -> None:
        items = self.checked()
        text = self.write(items)
        self.redraw()
        if text is not None:
            self.note(text)

    def note(self, text: str) -> None:
        self.status.setText(text)
        self.tool.say(text)

    def run(self, action: Callable[[], Any]) -> Any:
        """A refusal goes to the tab status and the shell status line."""
        try:
            return action()
        except ERRORS as error:
            self.status.setText(str(error))
            self.tool.say(f"{self.tool.app}: {error}")
            return None

    def row_chosen(self, name: str, layer: Any) -> None:
        if self.tool.preview is not None and name:
            self.tool.preview.load(name, layer or None)


__all__ = [
    "APP", "STALE", "Modules", "PlanTab", "Qt", "append_note", "apply_editor", "backends", "commit", "hline",
    "ident", "label", "result_dict", "subject",
]  # fmt: skip
