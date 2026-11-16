# this_file: src/fontlabapp/fontui/feature_blocks.py
# SPDX-License-Identifier: Apache-2.0
"""Read and write exact VFJ feature source for the active FontLab font.

Owned by FontLab App. Use these two
functions from FontLab scripts and tools that edit feature source.

Import is cheap and host-free: no Qt binding and no ``fontlab`` module are loaded
until a function runs. ``NativeFontBackend`` is also imported at call time.
App owns the generic "which package is current" helper; this module calls it
through the module object ``fontlabapp.core.scripting``, so one patch point serves
every caller.
"""

from collections.abc import Iterable
from importlib import import_module
from typing import Any

import fontlabapp.core.scripting

__all__ = ["read_feature_blocks", "write_feature_blocks"]


def read_feature_blocks(package: Any) -> dict:
    """Read exact ordered VFJ feature source through Fontport and fontpr.

    Requires an active registered font inside FontLab (fontpr is host-provided).
    Native object ids guard the UI binding; fgId identifies the fontpr font.
    Raise ValueError when the bound font is no longer the active font.
    """
    from fontlab_fontport.host import NativeFontBackend

    active = fontlabapp.core.scripting.current_package(package.id)
    if active is None:
        raise ValueError("Activate the original font before reading feature source.")
    return NativeFontBackend(active.fgId).get_feature_blocks()


def _terminated(blocks: dict) -> dict:
    """Return ``blocks`` with every non-empty feature code ending the way FontLab stores it.

    Fontport's history split-back returns each feature as ``code + "\\n"`` and keeps a
    block only if its last line ends in a newline. Code without a final newline
    (``features.code.feature_text``) or with spaces/tabs after the last newline
    would be refused, so those get trailing spaces and tabs stripped and one
    newline added. Codes already ending in a newline (including ``"\\n\\n"`` and
    ``"  \\n"``) and empty codes are returned unchanged; blank-only code becomes empty. Only spaces and tabs are stripped: a
    trailing ``\r`` or ``\f`` is kept and gets the newline after it (Fontport accepts both).
    """

    def end(code: str) -> str:
        code = code.rstrip(" \t")
        return code + "\n" if code and not code.endswith("\n") else code

    return {**blocks, "features": [(tag, end(code)) for tag, code in blocks["features"]]}


def write_feature_blocks(
    package: Any,
    expected: dict,
    updated: dict,
    *,
    references: Iterable[str],
    undo_name: str,
) -> dict[str, int]:
    """Apply an exact source-bound feature plan with Fontport's history checks.

    All referenced glyphs and the complete source snapshot must still match.
    Fontport validates split-back, language synthesis and empty history slots
    before mutation, and notifies only package/features. Groups are untouched.
    Unexpected native errors may leave partial changes; they are not hidden.

    Refuse with ValueError when the font is inactive, the source differs from
    ``expected``, or a referenced glyph is gone. Return ``{"changed": 0}`` when
    ``expected == updated`` and ``{"changed": 1}`` after a write. Feature codes
    missing a final newline, or with trailing spaces/tabs after it, are
    normalised by ``_terminated`` before comparing and staging. The master
    that was active before the write is restored in ``finally``.
    """
    from fontlab_fontport.host import NativeFontBackend

    active = fontlabapp.core.scripting.current_package(package.id)
    if active is None:
        raise ValueError("Activate the original font before applying.")
    backend = NativeFontBackend(active.fgId)
    updated = _terminated(updated)
    if backend.get_feature_blocks() != expected:
        raise ValueError("Feature source changed; refresh the preview before applying.")
    # Reached only after the Fontport backend imported fontlab; kept for the CurrentFont glyph-name check.
    font = import_module("fontlab").CurrentFont()
    known = {glyph.name for glyph in font.glyphs}
    if set(references).difference(known):
        raise ValueError("Referenced glyphs changed; reopen this tool.")
    if expected == updated:
        return {"changed": 0}
    master = active.master
    try:
        backend.set_feature_blocks(updated, undo_name=undo_name)
    except Exception as error:
        raise RuntimeError(
            f"Feature write failed; changes may be partial: {error}"
        ) from error
    finally:
        if active.master != master:
            active.setMaster(master)
    return {"changed": 1}
