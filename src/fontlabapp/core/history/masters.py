# this_file: src/fontlabapp/core/history/masters.py
# SPDX-License-Identifier: Apache-2.0
"""One native Undo step for font-level edits on one or more masters.

What: ``commit_masters`` writes master values (zones, vertical metrics) as ONE
FontLab Undo step. It uses route A of the issue 122 M2 measurement (FontLab
9.0.9790): the history objects of Font Info and "Sync font metrics"
(``dlgfontinfo.cpp:2100-2175``, ``mainwindow_edit.cpp:1208-1226``):

1. Refuse before any native write (``ValueError``): a thread other than the
   GUI thread; no active Font window of this font, or a Glyph window as the
   active canvas (measured in the Font window only); an unknown, duplicate or
   empty master list; an empty title.
2. Read the queued glyph ids once (``edit_guards.pending_updates``). Never
   clear them.
3. ``checkInitHistoryState(0)`` on the package and on ONE
   ``package.mastersContainer()`` handle.
4. For each requested master, in font order: ``setMaster(name, False)``,
   ``read()`` and ``save()`` (the values to restore), ``write()``, ``read()``
   again and ``verify()`` that value.
5. ``setMaster(original, False)``.
6. ONE ``flItems().notifyChangesApplied(title, [package, container], False)``.
   No glyph and no layer is in the list, so no auto layer is notified.

Rollback policy (a decision that differs from ``history.commit``):
``history.commit`` always notifies, also after a failure, and Edit > Undo is
the recovery. Here a failure in steps 3 to 5 (a write callback error, or a
read-back mismatch) comes BEFORE the notification. So the helper restores
every master that it touched, in reverse order, reads each one back, and
notifies nothing. Edit > Undo would revert the user's previous step, so no
error text recommends it. An interrupt (``KeyboardInterrupt``,
``SystemExit``) also runs the rollback and the master restore, then is
raised unchanged.

- All values restored: raise ``RolledBackError`` (a ``ValueError``: the font
  is as before, like a refusal). A caller whose restore re-creates native
  objects passes ``restored_text`` to say so (``zone_native``).
- A restore failed, or the notification failed: raise ``UnrestoredError`` (a
  ``history.PartialWriteError``). Values can remain with no Undo step.

Known host defect (fl#8574, measured on 9.0.9790, issue 122 M2): after Edit > Undo or
Redo of such a step, both masters show only 3 of the 9 font-metric
guidelines (the zone guidelines) until ``package.updateFontMetrics()`` runs or
the font is reopened. The saved file is correct. This module does not patch
Undo; it cannot hook the user's Undo.

How to use::

    import fly.ap.core.history.masters as font_history

    edit = font_history.MasterEdit(save, write, read, verify, restore)
    result = font_history.commit_masters(package, "Edit Zones", {"Bold": edit})
    edit_guards.disclose(result)

The module imports only the standard library at load time. Offline tests
prove the call order only, not native Undo/Redo/reopen behaviour.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from threading import current_thread, main_thread
from typing import Any, NamedTuple

from fontlabapp import _native
from fontlabapp.core.history.glyphs import (
    NOT_STORED,
    SHOWN_MISMATCHES,
    PartialWriteError,
)

#: The recovery text of ``UnrestoredError``. It does not recommend Undo.
UNRESTORED_HINT = (
    "Values can remain with no Undo step; check every master before you save, "
    "or close the font without saving."
)
#: The end of the ``RolledBackError`` text.
RESTORED_TEXT = "Every written value was restored; nothing was added to Undo."
#: The refusal text off the GUI thread.
THREAD_TEXT = "Run this on the FontLab GUI thread."
#: The refusal text while a Glyph window is the active canvas.
WINDOW_TEXT = "Activate the Font window before editing font masters."


@dataclass(frozen=True)
class MasterEdit:
    """The callbacks for one master. Each runs while that master is selected.

    ``save()``: return the native state that ``restore`` needs (for example
    copies of native zones). ``write()``: write the new values. ``read()``:
    return plain, comparable values. ``verify(value)``: return one text per
    difference between ``value`` and the plan. ``restore(saved)``: write the
    ``save()`` state back; ``read()`` must then equal its first value.
    """

    save: Callable[[], Any]
    write: Callable[[], None]
    read: Callable[[], Any]
    verify: Callable[[Any], Iterable[str]]
    restore: Callable[[Any], None]


class MastersCommitted(NamedTuple):
    """What ``commit_masters`` returns after the notification.

    ``values``: master name -> its verified ``read()`` value, in font order.
    ``pending_updates``: ids read once before the write. ``pending_note``: the
    date caveat, empty without ids. String keys work, as in
    ``history.Committed``, so ``edit_guards.disclose`` accepts the result.
    """

    values: Mapping[str, Any]
    pending_updates: tuple[int, ...] = ()
    pending_note: str = ""

    def __getitem__(self, key: int | slice | str) -> Any:
        """Support named result fields as well as tuple indexing."""
        return getattr(self, key) if isinstance(key, str) else tuple.__getitem__(self, key)


class RolledBackError(ValueError):
    """A master write failed before the notification; every value is restored.

    ``errors``: the first failure. The font holds no change and no Undo step.
    """

    def __init__(self, title: str, error: Exception, restored: str = RESTORED_TEXT) -> None:
        """Keep ``error``; build the text from ``title`` and ``restored``."""
        self.errors: tuple[Exception, ...] = (error,)
        super().__init__(f"{title} refused: {_text(error)}. {restored}")


class UnrestoredError(PartialWriteError):
    """A restore or the notification failed; values can remain without Undo.

    ``errors``: every collected exception, in the order they happened.
    """

    def __init__(self, title: str, errors: Sequence[Exception]) -> None:
        """Keep ``errors``; the text gives ``UNRESTORED_HINT``, not Undo."""
        self.errors = tuple(errors)
        shown = "; ".join(_text(error) for error in self.errors)
        RuntimeError.__init__(self, f"{title} did not finish: {shown}. {UNRESTORED_HINT}")


def _text(error: Exception) -> str:
    """Return the error text, or its type name for an empty text."""
    return str(error) or type(error).__name__


def require_font_window(package: Any, native: Any = None) -> None:
    """Refuse unless this runs on the GUI thread with the Font window active.

    Raise ``ValueError(THREAD_TEXT)`` on another thread. Then raise
    ``ValueError(WINDOW_TEXT)`` when ``edit_guards.require_selection_window``
    refuses (no Font window of this font is active; its own selection text
    stays for selection writers), when a Glyph window is the active canvas,
    or when the canvas cannot be read. Call it before any master switch.
    """
    import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native

    if current_thread() is not main_thread():
        raise ValueError(THREAD_TEXT)
    try:  # keep the selection guard's own text for selection writers
        edit_guards.require_selection_window(int(package.id))
    except ValueError as error:
        raise ValueError(WINDOW_TEXT) from error
    try:
        shown = edit_guards.canvas_glyphs(native)
    except Exception as error:  # an unreadable canvas is not proved safe
        raise ValueError(WINDOW_TEXT) from error
    if shown is not None:
        raise ValueError(WINDOW_TEXT)


def _order(package: Any, title: str, edits: Mapping[str, MasterEdit]) -> tuple[str, ...]:
    """Return the requested masters in font order, or raise ``ValueError``."""
    if not isinstance(title, str) or not title.strip():
        raise ValueError("A history title is required.")
    if not edits:
        raise ValueError("No master to edit.")
    masters = tuple(str(name) for name in package.masters)
    unknown = sorted(str(name) for name in edits if name not in masters)
    if unknown or len(set(masters)) != len(masters):
        raise ValueError(f"Unknown or duplicate master: {unknown or masters!r}")
    if any(not isinstance(edit, MasterEdit) for edit in edits.values()):
        raise ValueError("Each master needs a MasterEdit.")
    return tuple(name for name in masters if name in edits)


def _select(package: Any, name: str) -> None:
    """Select ``name`` without notification and check that FontLab did it."""
    package.setMaster(name, False)
    if str(package.master) != name:
        raise RuntimeError(f"FontLab did not select master {name!r}.")


def _write(
    package: Any, order: Sequence[str], edits: Mapping[str, MasterEdit], touched: dict, values: dict
) -> None:
    """Write and verify every master; keep restore data in ``touched``."""
    for name in order:
        edit = edits[name]
        _select(package, name)
        before = edit.read()
        touched[name] = (before, edit.save())
        edit.write()
        value = edit.read()
        missed = tuple(edit.verify(value))
        if missed:
            shown = "; ".join(missed[:SHOWN_MISMATCHES])
            raise ValueError(f"{NOT_STORED} master {name}: {shown}")
        values[name] = value


def _rollback(
    package: Any, edits: Mapping[str, MasterEdit], touched: dict, original: str
) -> list[Exception]:
    """Restore the touched masters in reverse order; return what failed.

    A second interrupt during this rollback is not caught: it can leave a
    master switched and values unrestored.
    """
    problems: list[Exception] = []
    for name in reversed(list(touched)):
        before, saved = touched[name]
        try:
            _select(package, name)
            edits[name].restore(saved)
            if edits[name].read() != before:
                problems.append(RuntimeError(f"master {name} was not restored"))
        except Exception as error:  # noqa: BLE001 - collected, raised by the caller
            problems.append(error)
    try:
        _select(package, original)
    except Exception as error:  # noqa: BLE001 - collected, raised by the caller
        problems.append(error)
    return problems


def commit_masters(
    package: Any,
    title: str,
    edits: Mapping[str, MasterEdit],
    *,
    native: Any = None,
    restored_text: str = RESTORED_TEXT,
) -> MastersCommitted:
    """Write ``edits`` as ONE native Undo step. See the module text for the order.

    ``package``: the ``flPackage``. ``title``: the Undo name. ``edits``:
    master name -> ``MasterEdit``. ``native``: the ``fontlab`` module
    (default: the native one). ``restored_text``: the end of the
    ``RolledBackError`` text, for a caller whose restore re-creates native
    objects (zones). Raise ``ValueError`` before any history call
    for a refusal, ``RolledBackError`` after a restored failure and
    ``UnrestoredError`` when a restore or the notification failed.

    After Undo/Redo of the step, FontLab 9.0.9790 shows 3 of 9 font-metric (fl#8574)
    guidelines until ``updateFontMetrics()`` or a reopen (host defect; the
    saved file is correct).
    """
    import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native

    module = _native("fontlab") if native is None else native
    require_font_window(package, module)
    order = _order(package, title, edits)
    ids = edit_guards.pending_updates(module)
    original = str(package.master)
    container = package.mastersContainer()
    touched: dict[str, tuple[Any, Any]] = {}
    values: dict[str, Any] = {}
    try:
        package.checkInitHistoryState(0)
        container.checkInitHistoryState(0)
        _write(package, order, edits, touched, values)
        _select(package, original)
    except BaseException as error:  # restore first, also on KeyboardInterrupt
        problems = _rollback(package, edits, touched, original)
        if not isinstance(error, Exception):
            raise
        if problems:
            raise UnrestoredError(title, [error, *problems]) from error
        raise RolledBackError(title, error, restored_text) from error
    try:
        module.flItems().notifyChangesApplied(title, [package, container], False)
    except Exception as error:  # the values stay; FontLab may have no Undo step
        raise UnrestoredError(title, [error]) from error
    return MastersCommitted(values, ids, edit_guards.pending_note(ids))


__all__ = [
    "RESTORED_TEXT",
    "THREAD_TEXT",
    "UNRESTORED_HINT",
    "WINDOW_TEXT",
    "MasterEdit",
    "MastersCommitted",
    "RolledBackError",
    "UnrestoredError",
    "commit_masters",
    "require_font_window",
]
