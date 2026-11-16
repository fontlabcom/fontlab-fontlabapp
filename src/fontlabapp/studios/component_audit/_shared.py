# this_file: src/fontlabapp/studios/component_audit/_shared.py
# SPDX-License-Identifier: Apache-2.0
"""Pieces shared by the Component Audit tabs: backends, labels and the read-only snapshot panel.

What: ``backends()`` returns ``core.scripting.component_audit_backends()``
(tests replace it). ``label`` builds the ``"Component Audit: <action>
<subject>"`` Undo label. ``AuditPanel`` is the base of the three read-only
inspector tabs (Composites, Where used, Missing bases): Refresh reads the
font's ordered masters, whole-font glyph order and component source values
once and computes the tab's result from them; every action (select, copy,
open) first rechecks that the same font, masters, glyph order, source and
result are still current, with the original inspectors' refusal texts
(``fontlabapp.components.inspect.ui.ComponentsDialog``), and clears the tab
when they are not. Nothing here opens history or writes a glyph.
Used by ``fontlabapp.studios.component_audit``.
"""

from collections.abc import Callable, Iterable
from typing import Any

from PythonQt import QtGui

from fontlabapp.core.scripting import component_audit_backends

from .._kerning import NO_FONT, Tool
from .._kerning_ui import Panel, label as text_label

APP = "Component Audit"
#: The original inspectors' stale-source refusals, verbatim.
INCOMPLETE = "Results are incomplete; rescan or reopen this tool."
NOT_CURRENT = "The original font is no longer current; reopen this tool."
MASTERS_CHANGED = "Masters changed since preview; reopen this tool."
ORDER_CHANGED = "Font glyph order changed; reopen this tool."
SOURCE_CHANGED = "Component source changed; rescan or reopen this tool."


def backends() -> Any:
    """The App backends of this app (``core.scripting.component_audit_backends``)."""
    return component_audit_backends()


def subject(names: Iterable[str]) -> str:
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def label(action: str, names: Iterable[str]) -> str:
    """``"Component Audit: <action> <glyph or N glyphs>"``."""
    return f"{APP}: {action} {subject(names)}"


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'s' if count != 1 else ''}"


def hline(layout: Any) -> Any:
    """A horizontal line added to ``layout``."""
    line = QtGui.QHBoxLayout()
    layout.addLayout(line)
    return line


class AuditPanel(Panel):
    """A read-only inspector tab over one captured component snapshot.

    Subclasses set ``CHANGED`` (the original "results changed" refusal) and
    implement ``build_controls()``, ``scan(api)`` (the original calculation,
    from ``self.package``/``self.names``/``self.masters``), ``show_result()``
    and ``clear_view()``.
    """

    CHANGED = ""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.package: Any = None
        self.masters: list[str] = []
        self.current_master = ""
        self.names: list[str] = []
        self.domain: tuple = ((), "")
        self.source: Any = None
        self.result: Any = None
        self.build_controls()
        self.status = text_label(self.widget, self.layout)

    def build_controls(self) -> None:  # pragma: no cover - overridden
        pass

    def scan(self, api: Any) -> Any:  # pragma: no cover - overridden
        return None

    def show_result(self) -> None:  # pragma: no cover - overridden
        pass

    def clear_view(self) -> None:  # pragma: no cover - overridden
        pass

    def clear(self) -> None:
        """Drop the snapshot so nothing stale can be selected, copied or opened."""
        self.package, self.source, self.result = None, None, None
        self.clear_view()

    def refresh(self) -> None:
        """Read the font once (masters, glyph order, source values) and compute the result."""
        self.clear()
        tool = self.tool
        if tool.package is None:
            self.subtitle.setText(NO_FONT)
            self.show_result()
            return
        api = backends().inspect
        package = tool.package
        self.masters = [str(m) for m in package.masters]
        self.current_master = str(package.master)
        self.domain = (tuple(self.masters), self.current_master)
        self.names = list(api.font_glyph_names())
        self.package = package
        self.source = api.source_values(package, self.names, self.masters)
        self.result = self.scan(api)
        self.show_result()

    def ensure(self) -> None:
        """Refuse an action on a stale snapshot (original texts); clear the tab then."""
        try:
            if self.package is None:
                raise ValueError(INCOMPLETE)
            api = backends().inspect
            active = self.tool.shell.package()
            if (active.id if active is not None else None) != self.package.id:
                raise ValueError(NOT_CURRENT)
            domain = (tuple(str(m) for m in active.masters), str(active.master))
            if domain != self.domain:
                raise ValueError(MASTERS_CHANGED)
            if list(api.font_glyph_names()) != self.names:
                raise ValueError(ORDER_CHANGED)
            if api.source_values(self.package, self.names, self.masters) != self.source:
                raise ValueError(SOURCE_CHANGED)
            if self.scan(api) != self.result:
                raise ValueError(self.CHANGED)
        except Exception:
            self.clear()
            raise

    def action(self, work: Callable[[], Any]) -> Callable[[], Any]:
        """A button slot: recheck the snapshot, then run ``work``; refusals go to the status line."""

        def guarded(*args: Any) -> Any:
            def run() -> Any:
                self.ensure()
                return work()

            return self.run(run)

        return guarded

    def note(self, text: str) -> None:
        """The tab's own status line (the original panel footer)."""
        self.status.setText(text)

    def say(self, text: str) -> None:
        """An action result: the tab's status line and the shell status line."""
        self.note(text)
        self.tool.say(text)


__all__ = [
    "APP", "INCOMPLETE", "MASTERS_CHANGED", "NOT_CURRENT", "ORDER_CHANGED", "SOURCE_CHANGED",
    "AuditPanel", "backends", "hline", "label", "plural", "subject",
]  # fmt: skip
