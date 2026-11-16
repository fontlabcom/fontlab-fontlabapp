# this_file: src/fontlabapp/studios/_kerning.py
# SPDX-License-Identifier: Apache-2.0
"""Shared state of Kerning Browser and Kerning Batch: package, masters, preview and the one writer.

What: ``Tool`` holds one shell's current package, its masters and the
current master (``package.master``, as the Scriptmix scripts read it), the
TMetrics preview and the kerning backends (``core.scripting.kerning_tool_backends``).
``reload`` re-reads the package and re-runs every tab's view; ``show_pair``
previews one pair on its master; ``write`` is the only write path: one
``fontlabapp.fontui.write_kerning`` call with ``expected=`` the snapshot the
plan was built from, one ``"<App>: <action> <subject>"`` Undo step
(Issue 235 §1.3/§1.4). Only changed masters are range-checked by the writer.
Tabs never call notify or ``fgGlyph``. Qt-free.
Used by ``fontlabapp.studios.kerning_browser`` and ``fontlabapp.studios.kerning_batch``.
"""

from collections.abc import Callable, Iterable
from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import kerning_tool_backends, names_selected_names, select_glyphs

NO_FONT = "Open a font first."
#: Failures shown in the status line instead of raised.
ERRORS = (ValueError, TimeoutError, RuntimeError, ImportError, OSError, KeyError, TypeError, AttributeError)


def pair_text(left: str, right: str) -> str:
    """``"A  V"``: the two sides with two spaces, as the Scriptmix tables showed them."""
    return f"{left}  {right}"


def side_name(side: Any) -> str:
    """A legacy ``"@class"``/glyph string, or a typed ``(name, mode)`` side, as text."""
    if isinstance(side, tuple):
        name, mode = side
        return ("@" if mode == "groupMode" else "") + name
    return str(side)


def counts(per_master: dict[str, int]) -> str:
    """``"Regular 3 · Bold 0"``: every master of the plan with its count, as the originals printed it."""
    return " · ".join(f"{master} {n}" for master, n in per_master.items())


class Tool:
    """One Kerning Browser or Kerning Batch window's shared state; tabs subscribe with ``views``."""

    def __init__(self, shell: Any, app: str, *, font: Callable[[], Any] | None = None,
                 backends: Callable[[], Any] = kerning_tool_backends) -> None:
        self.shell = shell
        self.app = app
        self._font = font or fontui.current_font
        self._backends = backends
        self.package: Any = None
        self.masters: list[str] = []
        #: ``str(package.master)``; ``""`` while no font is open.
        self.current = ""
        self.views: list[Callable[[], None]] = []
        self.preview: Any = None
        self.preview_factory: Callable[[], Any] | None = None
        self.status = ""

    def say(self, text: str) -> None:
        """Show ``text`` in the shell status line."""
        self.status = text
        self.shell.set_status(text)

    def backends(self) -> Any:
        return self._backends()

    def font(self) -> Any:
        return self._font()

    def reload(self) -> None:
        """Re-read the current package and its masters (no writes), then refresh every view.

        A failure (for example a font closed under the tool) is shown in the
        status line; it never escapes the Refresh slot or skips the other views.
        """
        try:
            self.package = self.shell.package()
            masters = [] if self.package is None else [str(m) for m in self.package.masters]
            current = "" if self.package is None else str(self.package.master)
            problem = NO_FONT if self.package is None else ""
        except ERRORS as error:
            self.package, masters, current, problem = None, [], "", f"{self.app}: {error}"
        self.masters, self.current = masters, current
        if problem in ("", NO_FONT) and self.preview is None and self.preview_factory is not None:
            self.preview = self.preview_factory()
            if self.preview is not None:
                self.shell.set_preview(self.preview)
        if problem:
            self.say(problem)
        for view in list(self.views):
            try:
                view()
            except ERRORS as error:
                self.say(f"{self.app}: {error}")
        if problem:
            self.say(problem)

    def scope(self, all_masters: bool) -> list[str]:
        """The current master alone, or every master."""
        if not self.masters:
            return []
        return list(self.masters) if all_masters else [self.current]

    def selected_names(self) -> list[str]:
        """Font-window selection, unique, in selection order."""
        return list(dict.fromkeys(names_selected_names()))

    def select(self, names: Iterable[str]) -> int:
        """Select ``names`` in the Font window of this tool's package; return how many."""
        names = list(names)
        if self.package is None:
            raise ValueError(NO_FONT)
        select_glyphs(names, package_id=self.package.id)
        return len(names)

    def show_pair(self, left: str, right: str, master: str | None = None) -> None:
        """Preview a pair on ``master``; a ``@class`` side shows its first member."""
        if self.preview is None or not left or not right:
            return
        first, second = self._member(left, master), self._member(right, master)
        if first is None or second is None:
            return
        self.preview.set_text(f"/{first}/{second}")
        if master:
            self.preview.set_layer(master)
        if not left.startswith("@") and not right.startswith("@"):
            self.preview.highlight_pair(left, right)

    def _member(self, side: str, master: str | None) -> str | None:
        if not side.startswith("@"):
            return side
        snapshot = fontui.kerning_snapshot(self.package) if self.package is not None else None
        groups = snapshot.groups.get(master or self.current, {}) if snapshot is not None else {}
        members = groups.get(side[1:], ((), ""))[0]
        return next(iter(members), None)

    def write(self, action: str, subject: str, edits: dict, expected: Any) -> bool:
        """Write ``edits`` (``{master: {pair: value or None}}``) as one Undo step; refusals go to the status line."""
        label = f"{self.app}: {action} {subject}"
        edits = {master: changes for master, changes in edits.items() if changes}
        if self.package is None or expected is None:
            raise ValueError(NO_FONT)
        if not edits:
            raise ValueError("Nothing to apply; use Refresh.")
        self.shell.package()
        try:
            return bool(fontui.write_kerning(self.package, edits, label, expected=expected))
        except RuntimeError as error:
            raise RuntimeError(f"{error} Native changes may remain; use Edit > Undo.") from error


__all__ = ["ERRORS", "NO_FONT", "Tool", "counts", "pair_text", "side_name"]
