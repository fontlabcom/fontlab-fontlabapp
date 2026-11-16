# this_file: src/fontlabapp/studios/proof_studio/session.py
# SPDX-License-Identifier: Apache-2.0
"""Proof Studio state: selection and font facts, generation, preview, copy, open and actions.

What: ``Studio`` turns the chosen generator, choice, seed and field values into
a ``Proof``, previews a part through TMetrics (``set_view`` for size and
kerning, ``set_layer`` for the master, then ``set_text``), hands the exact
part text to a clipboard callable, draws Waterfall and By master stacks in
the absorbed panels' own views (``paint``), opens the FontLab Glyph tab(s) through
the generator and runs generator actions. Every preview sets size, layer
and kerning, so one tab's settings never leak into another's.
Read-only for font data: it never edits the font, never calls history and
reads the selection or font facts only when the generator uses them. Its
only writes are a generator's own settings namespace. Qt-free.
Used by ``fontlabapp.studios.proof_studio`` (app and tabs).
"""

import re
from collections.abc import Callable
from time import monotonic
from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import current_package, layer_selection_api, proof_api

from .generators import Action, Context, Facts, Generator, Options, Outcome, Proof

APP = "Proof Studio"
#: Failures shown in the status line instead of raised (no font, changed selection,
#: timeout, settings I/O, malformed Text filter character class).
ERRORS = (ValueError, TimeoutError, RuntimeError, ImportError, OSError, re.error)
SELECTION_SECONDS = 2.0  # the absorbed scripts' capture deadline


def selected_names() -> tuple[str, ...]:
    """Ordered selected glyph names (Font window selection or Glyph window occurrences, repeats kept)."""
    selection = layer_selection_api().capture(monotonic() + SELECTION_SECONDS)
    return tuple(row.glyph_name for row in selection.occurrences)


def font_facts() -> Facts | None:
    """The current font's first-encoded character map, glyph names and masters; None with no font."""
    package = current_package()
    if package is None:
        return None
    cmap, names = proof_api().font_maps()
    return Facts(cmap, frozenset(names), tuple(str(m) for m in package.masters), str(package.master))


def paint_canvas(view: Any, package: Any, canvas: tuple[Any, ...]) -> str:
    """Feed a WaterfallView ``(names, sizes, master)`` or MasterRows ``(names, size)`` as the originals.

    Read-only: ``glyph_run`` reads each master's layer outline and advance;
    a missing glyph is a red box ``upm × 0.5`` wide. Return the original
    panel's status line.
    """
    api = proof_api()
    names = list(canvas[0])
    missing = sum(1 for name in names if name is None)
    if len(canvas) == 3:
        sizes, master = list(canvas[1]), canvas[2]
        glyphs = api.glyph_run(package, names, master)
        view.set_content(glyphs, sizes, package.upm, package.ascender_value)
        note = f" · {missing} missing (red boxes)" if missing else ""
        return f"Line width {view.width_units:g} units · {len(sizes)} sizes{note}"
    rows = []
    for master in package.masters:
        run = api.glyph_run(package, names, master)
        rows.append((master, run, sum(advance for _, advance in run)))
    view.set_content(rows, canvas[1], package.upm, (package.descender_value, package.ascender_value))
    widths = [width for _, _, width in rows]
    spread = f" · widths {min(widths):g}–{max(widths):g} units" if widths else ""
    return f"{len(rows)} rows{spread}" + (f" · {missing} missing" if missing else "")


class Studio:
    """Shared Proof Studio state for one shell."""

    def __init__(
        self,
        shell: Any,
        *,
        font: Callable[[], Any] | None = None,
        selection: Callable[[], tuple[str, ...]] | None = None,
        facts: Callable[[], Facts | None] | None = None,
        settings: Callable[[str, str], Any] | None = None,
        package: Callable[[], Any] | None = None,
    ) -> None:
        self.shell = shell
        self._font = font or fontui.current_font
        self.selection = selection or selected_names
        self.facts = facts or font_facts
        #: ``(organization, application) -> QSettings``; None: the tabs' real QSettings.
        self.settings = settings
        self.package = package or current_package
        self.preview: Any = None

    def font(self) -> Any:
        return self._font()

    def _status(self, text: str) -> None:
        self.shell.set_status(text)

    def generate(
        self,
        generator: Generator,
        choice: str,
        *,
        seed: int | None = None,
        values: dict[str, Any] | None = None,
    ) -> Proof | None:
        """The proof for ``choice``; None (with the reason in the status line) on failure."""
        try:
            names = tuple(self.selection()) if generator.uses_selection else ()
            facts = self.facts() if generator.uses_font else None
            proof = generator.make(choice, Options(names, seed, dict(values or {}), facts))
        except ERRORS as error:
            self._status(f"{generator.title}: {error}")
            return None
        if proof.note:
            self._status(f"{generator.scripts[choice]}: {proof.note}")
            return proof
        if generator.uses_selection:
            source = f"{len(names)} selected glyph(s)"
        elif generator.seeded:
            source = "an unseeded draw" if seed is None else f"seed {seed}"
        else:
            source = "bundled text"
        self._status(f"{generator.scripts[choice]}: {len(proof.parts)} tab(s) from {source}.")
        return proof

    def show(self, proof: Proof | None, part: int = 0) -> str:
        """Preview ``part`` of ``proof`` in TMetrics with its size, layer and kerning; return the text."""
        text = proof.preview(part) if proof is not None else ""
        size, layer, kerning = proof.view(part) if proof is not None else Proof(()).view(0)
        if self.preview is not None:
            set_view = getattr(self.preview, "set_view", None)
            if set_view is not None:
                set_view(size, kerning)
            set_layer = getattr(self.preview, "set_layer", None)
            if set_layer is not None:
                set_layer(layer)
            self.preview.set_text(text)
        return text

    def paint(self, generator: Generator, choice: str, view: Any, proof: Proof | None) -> str | None:
        """Draw ``proof.canvas`` in the absorbed panel's own stacked view; return the status.

        The status joins the proof note and the original panel's status line
        (width, sizes or rows, missing glyphs). None when there is nothing to
        draw or the draw failed (reason in the status line).
        """
        if view is None or proof is None or not proof.canvas:
            return None
        try:
            package = self.package()
            if package is None:
                raise ValueError("Open a font first.")
            status = paint_canvas(view, package, proof.canvas)
        except ERRORS as error:
            self._status(f"{generator.title}: {error}")
            return None
        text = f"{generator.scripts[choice]}: {proof.note} {status}"
        self._status(text)
        return text

    def copy(self, proof: Proof | None, part: int, clipboard: Callable[[str], Any]) -> str | None:
        """Put the exact text of ``part`` on ``clipboard``; return it (None when nothing to copy)."""
        if proof is None or not 0 <= part < len(proof.parts):
            self._status("Nothing to copy; preview a proof first.")
            return None
        clipboard(proof.parts[part])
        self._status(f"Copied part {part + 1} of {len(proof.parts)} ({len(proof.parts[part])} characters).")
        return proof.parts[part]

    def open(self, generator: Generator, choice: str, context: Context | None = None) -> bool:
        """Open the new FontLab Glyph tab(s); True on success.

        With ``open_current`` and a ``context`` the shown proof is opened;
        otherwise ``open(choice)`` repeats the absorbed script.
        """
        name = generator.scripts[choice]
        if not generator.opens:
            self._status(f"{name} has no FontLab Glyph tab; use Copy.")
            return False
        try:
            if generator.open_current is not None and context is not None:
                if context.proof is None or not 0 <= context.part < len(context.proof.parts):
                    self._status("Nothing to open; preview a proof first.")
                    return False
                message = generator.open_current(choice, context)
            elif generator.open is not None:
                message = generator.open(choice)
            else:
                self._status("Nothing to open; preview a proof first.")
                return False
        except ERRORS as error:
            self._status(f"{name} did not open: {error}")
            return False
        self._status(message or f"{name}: opened in new FontLab Glyph tab(s).")
        return True

    def run(self, generator: Generator, action: Action, context: Context) -> Outcome | None:
        """Run a generator action; its status goes to the status line (None on failure)."""
        try:
            outcome = action.run(context)
        except ERRORS as error:
            self._status(f"{generator.title}: {action.label} failed: {error}")
            return None
        if outcome.status:
            self._status(outcome.status)
        return outcome

    def load(self, generator: Generator, settings: Any) -> Outcome | None:
        """The generator's saved values (None, with the reason in the status line, on failure)."""
        if generator.load is None:
            return None
        try:
            return generator.load(settings)
        except ERRORS as error:
            self._status(f"{generator.title}: saved settings were not loaded: {error}")
            return None

    def save(self, generator: Generator, settings: Any, values: dict[str, Any], proof: Proof) -> bool:
        """Save the generator's values after a user edit; False (status) when the save fails."""
        if generator.save is None:
            return False
        try:
            generator.save(settings, values, proof)
        except ERRORS as error:
            self._status(f"{generator.title}: text is not saved: {error}")
            return False
        return True


__all__ = ["APP", "ERRORS", "SELECTION_SECONDS", "Studio", "font_facts", "paint_canvas", "selected_names"]
