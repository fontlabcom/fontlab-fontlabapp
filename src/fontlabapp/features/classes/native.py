# this_file: src/fontlabapp/features/classes/native.py
# SPDX-License-Identifier: Apache-2.0
"""Use a caller-supplied actual OpenType-class API; never edit kerning groups.

Native classes are glyph-name lists. Their canonical code has spaces; no-op
classes never invoke set_class. Native metadata/history preservation is pending.
"""

from threading import current_thread, main_thread
from time import monotonic
from typing import Any
from fontlabapp import _native
from fontlabapp.features.classes.model import Snapshot


class Bridge:
    """One bound document and existing Glyport class-write/history implementation."""

    def __init__(self, backend: Any) -> None:
        """Accept the caller's class API; App imports no Glyport dependency."""
        self.backend, self.bound, self.poisoned = backend, None, False

    def read(self, deadline: float) -> Snapshot:
        """Read ordered actual feature classes and native glyph names, never fgGlyph."""
        if current_thread() is not main_thread():
            raise RuntimeError("Run Clean Classes on FontLab's UI thread.")
        if monotonic() >= deadline:
            raise TimeoutError("Class capture deadline exceeded.")
        token = self.backend.current_font_id()
        font = _native("fontlab").CurrentFont()
        if token is None or font is None:
            raise ValueError("Open a font before cleaning classes.")
        identity = (token, int(font.id))
        if self.bound is not None and identity != self.bound:
            raise ValueError(
                "The original font is no longer current; reopen this tool."
            )
        names = []
        for glyph in font.glyphs:
            if monotonic() >= deadline:
                raise TimeoutError("Class capture deadline exceeded.")
            names.append(str(glyph.name))
        classes = []
        for group in self.backend.classes(token):
            if monotonic() >= deadline:
                raise TimeoutError("Class capture deadline exceeded.")
            classes.append((group.name, " ".join(group.glyphs)))
        if self.backend.current_font_id() != token:
            raise ValueError("Font changed during class capture.")
        return Snapshot(identity, tuple(names), tuple(classes))

    def capture(self, *, deadline: float | None = None) -> Snapshot:
        """Require two complete equal passes within one absolute deadline."""
        if self.poisoned:
            raise RuntimeError(
                "Previous write failed; inspect the font and reopen this tool."
            )
        deadline = monotonic() + 2.0 if deadline is None else deadline
        first, second = self.read(deadline), self.read(deadline)
        if first != second or monotonic() >= deadline:
            raise ValueError("Font, glyph names or classes changed during capture.")
        self.bound = first.context
        return first

    def begin(self) -> None:
        """Existing Glyport transaction groups actual package class edits."""
        self.backend.begin_undo("Clean Classes")

    def write(self, name: str, members: tuple[str, ...]) -> None:
        """Write an actual existing FeaClassGroup through the reviewed native API."""
        font = _native("fontlab").CurrentFont()
        if font is None or (self.backend.current_font_id(), int(font.id)) != self.bound:
            raise ValueError("The font changed before a class write.")
        self.backend.set_class(self.bound[0], name, members)

    def end(self) -> None:
        """Publish the existing package-level history group once."""
        self.backend.end_undo()
