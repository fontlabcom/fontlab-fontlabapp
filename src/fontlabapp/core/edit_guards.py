# this_file: src/fontlabapp/core/edit_guards.py
# SPDX-License-Identifier: Apache-2.0
"""Public queue disclosure and refusal guards for scripts that write to the current font.

What: queue disclosure for ordinary writers, and four checks that raise ``ValueError`` before any native write.

- ``require_selection_window(package_id)``: the active panel is a Font window
  of the bound font (FontLab issue 8528: selection writers crash while a Glyph
  window is active).
- ``require_no_editors()``: no Glyph editor is open, also an inactive one
  (the Unicode save-cache gap of the duplicate-Unicode writer).
- ``require_settled()``: FontLab has no queued native glyph updates (FontLab
  issue 8537: queued cache updates become semantic edits later).
- ``require_history_scope(glyphs, creates=...)``: no Glyph window is the
  active canvas, or every owner glyph is in that canvas and no glyph is new
  (FontLab issue 8573: from a Glyph window, the Undo step covers only the
  glyphs that the canvas shows). ``fontlabapp.core.history.glyphs.commit``,
  ``fontlabapp.glyphs.creation.create_glyphs`` and the eight App writers that
  call ``notifyChangesApplied`` directly call it.

How: the selection and editor guards delegate to the reviewed private
implementation (``scripting._require_selection_window``,
``duplicate_unicodes_capture.require_no_editors``); ``require_settled`` reads
the native queue once; ``require_history_scope`` reads the text blocks of the
active canvas once. The implementations load only when a guard runs, so this
module imports only the standard library and FontLab's 5-second cold import
stays fast.

Why: scripts must not import private App names. Use these guards through
``fly.ap.core.edit_guards``. ``fontlabapp.core.history.glyphs.commit`` discloses the queue by default;
``settled=True`` explicitly opts into refusing it. Never normalise unrelated dates.
Offline tests do not prove native behaviour.
"""

from collections.abc import Mapping, Sequence
from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp import _native

#: Seconds that ``require_no_editors`` may take when no deadline is given.
EDITOR_SCAN_SECONDS = 2.0
#: Seconds that ``canvas_glyphs`` may take when no deadline is given.
CANVAS_SCAN_SECONDS = 1.0
#: The refusal text of ``require_history_scope`` (FontLab issue 8573).
CANVAS_TEXT = (
    "Switch to the Font window first: from a Glyph window FontLab cannot undo "
    "this edit in glyphs the window does not show."
)
#: Marker for a canvas that exists but cannot be read.
_UNREAD: frozenset[tuple[int, str]] = frozenset({(-1, "")})


def require_selection_window(package_id: int) -> None:
    """Refuse a write unless a Font window of the bound font is active.

    ``package_id`` is the ``flPackage.id`` that the caller scanned. Raise
    ``ValueError("Activate the Font window before selecting glyphs.")`` when
    the active panel is no regular Font window or the font changed. Use it
    before Unicode writes and before ``FL.fl.Select``/``Unselect``.
    """
    from fontlabapp.core.scripting import _require_selection_window

    _require_selection_window(package_id)


def require_no_editors(
    *,
    qt: Any = None,
    deadline: float | None = None,
    action: str = "removing Unicode assignments",
) -> None:
    """Refuse a write while any Glyph editor is open, also an inactive one.

    ``qt`` is the PythonQt module (default: the native one). ``deadline`` is a
    ``time.monotonic()`` instant (default: now plus ``EDITOR_SCAN_SECONDS``).
    ``action`` completes the refusal text "before <action>."
    Raise ``ValueError`` for an open or unreadable editor and ``TimeoutError``
    when the widget scan passes the deadline. The scan reads only the
    ``inherits("GlyphWindow")`` predicate, with cyclic GC off.
    """
    from fontlabapp.glyphs.unicode.duplicates.capture import (
        require_no_editors as implementation,
    )

    module = _native("PythonQt") if qt is None else qt
    limit = monotonic() + EDITOR_SCAN_SECONDS if deadline is None else deadline
    implementation(module, limit, action)


def pending_updates(native: Any = None) -> tuple[int, ...]:
    """Read the native queue once before a write; never clear or deliver it.

    Use this with ``pending_note`` for ordinary writers. FontLab 9.0.9790
    can keep ids queued for the rest of the process after a refresh or opening
    an editor. Use ``require_settled`` only for explicit opt-in protocols.
    """
    module = _native("fontlab") if native is None else native
    return tuple(module.flGlyph.updatedFgGlyphs())


def pending_note(ids: Sequence[int]) -> str:
    """Explain queued ids and their date caveat, or return empty text."""
    if not ids:
        return ""
    noun = "glyph" if len(ids) == 1 else "glyphs"
    return (
        f"FontLab had queued updates for {len(ids)} {noun}; FontLab may also "
        "change their modification dates (FontLab issue 8537)."
    )


def append_note(text: str, result: Mapping[str, Any]) -> str:
    """Append the stored pre-write note once, using the standard separator."""
    note = result["pending_note"]
    return f"{text} · {note}" if note and note not in text else text


def disclose(result: Any, target: dict[str, Any] | None = None) -> None:
    """Copy a commit's disclosure to a caller's result, or print it for CLI use.

    Writers with a legacy scalar/list return pass a target for their panel or
    tests; standalone callers without a target see the same note in Output.
    """
    if target is not None:
        target.update(pending_updates=result["pending_updates"], pending_note=result["pending_note"])
    elif result["pending_note"]:
        print(f"Queued glyph ids: {result['pending_updates']} · {result['pending_note']}")


def canvas_glyphs(
    native: Any = None, *, deadline: float | None = None
) -> frozenset[tuple[int, str]] | None:
    """Return the glyphs that the active Glyph window shows, or ``None``.

    ``None``: no Glyph window is the active canvas, so FontLab records
    package history. Otherwise return one ``(package id, glyph name)`` pair
    for each glyph in the text blocks of the active canvas. Use the name, not
    the id: ``CurrentGlyph().id`` and the canvas slot id of the same glyph
    differ on 9790 (412 against 531175085312). These are the glyphs
    that FontLab's canvas history attaches an Undo step to
    (``flhistorycontroller.cpp``, the ``in_glyphs`` branch; FontLab issue
    8573). Empty slots are skipped. ``deadline`` is a ``time.monotonic()``
    instant (default: now plus ``CANVAS_SCAN_SECONDS``); a later checkpoint
    raises ``TimeoutError``. Native read errors propagate.

    A ``fontlab`` module without ``flWorkspace``, or a workspace without
    ``getActiveCanvas`` (offline doubles), has no canvas: return ``None``.
    FontLab's own module always defines both.
    """
    from fontlabapp.qt.safe import qt_list

    module = _native("fontlab") if native is None else native
    limit = monotonic() + CANVAS_SCAN_SECONDS if deadline is None else deadline
    workspace = getattr(module, "flWorkspace", None)
    active = None if workspace is None else getattr(workspace.instance(), "getActiveCanvas", None)
    if active is None:
        return None
    canvas = active()
    if canvas is None or canvas.isNull:
        return None
    shown: set[tuple[int, str]] = set()
    for block in qt_list(canvas.textBlocks):
        for index in range(int(block.glyphsCount())):
            if monotonic() >= limit:
                raise TimeoutError("Glyph window scan exceeded its deadline.")
            info = block.getGlyphAt(index)
            glyph = None if info is None else info.glyph
            if glyph is not None and not glyph.isNull:
                shown.add(_identity(glyph))
    return frozenset(shown)


def _identity(glyph: Any) -> tuple[int, str]:
    """Return ``(package id, glyph name)``; names are unique in one font."""
    return int(glyph.package.id), str(glyph.name)


def _is_current(identity: tuple[int, str], module: Any) -> bool:
    """Return True when ``identity`` is the current glyph of the current font."""
    current = module.CurrentGlyph()
    package = module.flWorkspace.instance().currentPackage
    return (
        current is not None
        and package is not None
        and (int(package.id), str(current.name)) == identity
    )


def require_history_scope(
    glyphs: Sequence[Any], *, creates: bool = False, native: Any = None
) -> None:
    """Refuse a write that FontLab would undo only in part (FontLab issue 8573).

    While a Glyph window is the active canvas, FontLab attaches the Undo step
    of ``notifyChangesApplied`` only to the glyphs that this canvas shows.
    Other notified glyphs keep the change after Undo (measured on 9790). With
    the Font window active, the Undo step covers every notified glyph.

    ``glyphs``: the owner glyphs of the write, matched by font and glyph name.
    ``creates``: the write makes new glyphs (a new glyph is never in the
    canvas). Raise ``ValueError(CANVAS_TEXT)`` before any write when a Glyph
    window is the active canvas and the write creates glyphs, or when an owner
    is not in the canvas. When the canvas cannot be read, use the safe rule:
    allow no owner, or one owner that is the current glyph, and no new glyph.
    With no active canvas, return. Call it on the GUI thread only; other
    threads are refused. ``native`` is the ``fontlab`` module (default: the
    native one).
    """
    if current_thread() is not main_thread():
        raise ValueError(CANVAS_TEXT)
    try:
        shown = canvas_glyphs(native)
    except Exception:  # noqa: BLE001 - an unreadable canvas gets the safe rule
        shown = _UNREAD
    if shown is None:
        return
    try:
        owners = {_identity(g) for g in glyphs}
        if creates:
            allowed = False
        elif shown is _UNREAD:
            module = _native("fontlab") if native is None else native
            allowed = all(_is_current(o, module) for o in owners) and len(owners) <= 1
        else:
            allowed = owners <= shown
    except Exception as error:  # an owner that cannot be read is not proved safe
        raise ValueError(CANVAS_TEXT) from error
    if not allowed:
        raise ValueError(CANVAS_TEXT)


def require_settled(native: Any = None) -> None:
    """Refuse a write while FontLab has queued native glyph updates.

    ``native`` is the ``fontlab`` module (default: the native one). Read
    ``flGlyph.updatedFgGlyphs()`` once and never clear it: clearing the queue
    hides the defect instead of avoiding it (FontLab issue 8537).
    """
    module = _native("fontlab") if native is None else native
    if tuple(module.flGlyph.updatedFgGlyphs()):
        raise ValueError(
            "Native glyph updates are pending; finish the current edit first."
        )


__all__ = [
    "CANVAS_SCAN_SECONDS",
    "CANVAS_TEXT",
    "EDITOR_SCAN_SECONDS",
    "append_note",
    "canvas_glyphs",
    "disclose",
    "pending_updates",
    "pending_note",
    "require_history_scope",
    "require_no_editors",
    "require_selection_window",
    "require_settled",
]
