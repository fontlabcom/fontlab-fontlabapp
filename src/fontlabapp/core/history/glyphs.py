# this_file: src/fontlabapp/core/history/glyphs.py
# SPDX-License-Identifier: Apache-2.0
"""One native Undo step for a script edit, with auto-layer refusals.

What: ``commit`` runs a script's font change as ONE FontLab Undo step, in the
order that the reviewed App writers use:

1. Refuse before any write (``ValueError``, nothing touched):
   queued native glyph updates only with ``settled=True`` (FontLab issue
   8537; otherwise disclose them); optionally a missing Font
   window or an open Glyph editor (Unicode writers); a Glyph window as the
   active canvas when an owner glyph is not in that canvas (FontLab issue
   8573: the Undo step would cover only the shown glyphs; see
   ``edit_guards.require_history_scope``); an auto layer in the edit
   list or among the retained objects; a glyph that the operation policy
   refuses.
2. ``checkInitHistoryState(0)`` on every layer, then every glyph.
3. ``mutate()``. It may return the new native objects it made (for example new
   layers); they join the notification after the declared layers.
4. One shared UTC ``lastModified`` stamp on every glyph.
5. ONE ``notifyChangesApplied(title, layers + created + glyphs)``. With
   retained objects: ONE ``notifyChangesApplied(title, retain + layers +
   created + glyphs, True)``.
6. The same stamp again: window observers re-stamp after the history capture.
7. ``read_back()``: the caller compares the font with its plan.

Retained objects (``retain=``): a script that removes a component gives
the ORIGINAL shape, its shapeData and the builder, read BEFORE the removal
(``component_history(shape)``). They go first in the notification, before the
layers, and the third argument ``True`` asks for deep history. Glyport does
the same (``fontlab_backend._retain_component_history`` and ``_notify``): its
docstring says FontLab 9784 needs this to restore a removed component on Undo
(fl#7641). Without ``retain`` the call is the two-argument call, unchanged.

Steps 4 to 6 run also after a failed ``mutate``, so a partial edit stays on the
Undo stack. Every failure is collected and raised as ``PartialWriteError``
(a ``RuntimeError``) whose text says "Native changes may remain; use Edit >
Undo". No rollback is tried: Edit > Undo is the recovery.

Why the refusals: notifying a list that holds an auto layer makes FontLab
re-resolve every default-recipe auto layer in the font, and a change to a base
glyph rebuilds its auto composites. Anchors and locks can change and Undo does
not restore them (measured; see the workspace AGENTS.md). The policy depends on
the operation:

- ``"rename"``, ``"unicode"``, ``"geometry"``: refuse glyphs that own an auto
  layer and glyphs that are a base of an auto composite (also through a chain
  of manual composites). ``allow_bases=True`` lets a base through after the
  user agreed to the rebuild; an auto owner is never let through.
- ``"metadata"`` (notes, tags, mark colours): refuse only glyphs that own an
  auto layer.

How to use::

    import fly.ap.core.history.glyphs as history

    facts = history.scan_auto_facts(package)
    result = history.commit(
        "Round Advances", layers, glyphs, lambda: edit(layers),
        operation="geometry", facts=facts, read_back=check,
    )
    report(result.mismatches)

The module imports only the standard library at load time; FontLab modules and
``fontlabapp.guides.inspect.model`` load when a function runs. Offline tests prove the call
order only, not native Undo/Redo/reopen behaviour.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

from fontlabapp import _native

#: Write kinds that ``commit`` and ``refusal`` accept.
Operation = Literal["rename", "unicode", "geometry", "metadata"]
#: The values of ``Operation``, for checks at run time.
OPERATIONS = frozenset({"rename", "unicode", "geometry", "metadata"})
#: Operations that also refuse bases of auto composites.
STRUCTURAL = frozenset({"rename", "unicode", "geometry"})
#: The recovery text in every ``PartialWriteError``.
UNDO_HINT = "Native changes may remain; use Edit > Undo."
#: Start of the read-back error text; panels and scripts may match it (``unstored_error``).
NOT_STORED = "FontLab did not store"
#: The advice after a read-back gap. It makes no claim about what Undo restores.
CHECK_TEXT = "Check those layers before you save."
#: Mismatch texts that ``unstored_error`` names before it stops.
SHOWN_MISMATCHES = 6
#: One dependency record: (glyph name, layer is auto, component base names).
Record = tuple[str, bool, tuple[str, ...]]


@dataclass(frozen=True)
class AutoFacts:
    """Whole-font auto-layer facts that the refusal policy needs.

    ``autos``: names of glyphs that own at least one auto layer.
    ``users``: base name -> names of glyphs whose layers use it as a component.
    Build it with ``auto_facts`` or ``scan_auto_facts``; it is never patched,
    so scan again before each write.
    """

    autos: frozenset[str]
    users: Mapping[str, frozenset[str]]

    def dependants(self, name: str) -> tuple[str, ...]:
        """Return the sorted auto glyphs that FontLab rebuilds when ``name`` changes.

        Follow component users through any chain (``e`` -> manual ``ebar`` ->
        auto ``ebaracute``). The walk visits each glyph once, so circular
        components cannot hang the UI thread. ``name`` itself is never listed.
        """
        seen, todo = {name}, [name]
        while todo:
            for user in self.users.get(todo.pop(), ()):
                if user not in seen:
                    seen.add(user)
                    todo.append(user)
        return tuple(sorted(n for n in seen - {name} if n in self.autos))


class Committed(NamedTuple):
    """What ``commit`` returns after a complete write.

    ``created``: the native objects that ``mutate`` returned, in its order.
    ``mismatches``: the texts that ``read_back`` returned; empty when the font
    holds the plan or when no ``read_back`` was given.
    ``pending_updates``: ids read once before the write. ``pending_note``: the
    stored date caveat, empty without ids. Both also support string-key access.
    """

    created: tuple[Any, ...]
    mismatches: tuple[str, ...]
    pending_updates: tuple[int, ...] = ()
    pending_note: str = ""

    def __getitem__(self, key: int | slice | str) -> Any:
        """Support named result fields as well as the legacy tuple indexing."""
        return getattr(self, key) if isinstance(key, str) else tuple.__getitem__(self, key)


class PartialWriteError(RuntimeError):
    """A write, stamp, notification or read-back failed after history started.

    The font can hold part of the edit. The message names the title, every
    collected error and the recovery: "Native changes may remain; use Edit >
    Undo." ``errors`` keeps the original exceptions in the order they happened.
    """

    def __init__(self, title: str, errors: Sequence[Exception]) -> None:
        """Keep ``errors`` and build the message from ``title`` and their texts."""
        self.errors: tuple[Exception, ...] = tuple(errors)
        shown = "; ".join(str(error) or type(error).__name__ for error in self.errors)
        super().__init__(f"{title} did not finish: {shown}. {UNDO_HINT}")


def unstored_error(missed: Sequence[str], advice: str = "") -> RuntimeError:
    """Return the error for values that FontLab did not keep after a commit.

    Text: ``"FontLab did not store N change(s): a, b. <advice> Check those
    layers before you save."``. It starts with ``NOT_STORED``, so a panel
    can tell a read-back gap from a refusal. ``advice`` is an optional
    sentence before ``CHECK_TEXT``. The text makes no claim about Undo: the
    commit was one Undo step, but no measurement shows what Undo restores.
    """
    shown = ", ".join(missed[:SHOWN_MISMATCHES])
    extra = f"{advice} " if advice else ""
    return RuntimeError(
        f"{NOT_STORED} {len(missed)} change(s): {shown}. {extra}{CHECK_TEXT}"
    )


def auto_facts(records: Iterable[Record]) -> AutoFacts:
    """Build ``AutoFacts`` from dependency records, one record per layer.

    Use the records of ``fontlabapp.guides.inspect.model.dependency_values(package)``:
    ``(glyph name, layer is auto, component base names)``. A glyph with any
    auto record is an auto owner; every component base gets the glyph as user.
    """
    autos: set[str] = set()
    users: dict[str, set[str]] = {}
    for name, auto, bases in records:
        if auto:
            autos.add(name)
        for base in bases:
            users.setdefault(str(base), set()).add(name)
    return AutoFacts(frozenset(autos), {b: frozenset(n) for b, n in users.items()})


def scan_auto_facts(package: Any) -> AutoFacts:
    """Read every layer of ``package`` and return its ``AutoFacts``.

    Reuse ``fontlabapp.guides.inspect.model.dependency_values``: font order from FontGate
    records, ``package.findName`` per glyph, never ``flGlyph.fgGlyph``. A
    missing glyph raises ``ValueError("Glyph source changed; reopen this tool.")``.
    """
    from fontlabapp.guides.inspect.model import dependency_values

    return auto_facts(dependency_values(package))


def _require_operation(operation: str) -> None:
    """Raise ``ValueError`` for a write kind outside ``OPERATIONS``."""
    if operation not in OPERATIONS:
        raise ValueError(
            f"Unknown operation {operation!r}; use one of {sorted(OPERATIONS)}."
        )


def refusal(
    facts: AutoFacts, name: str, operation: str, *, allow_bases: bool = False
) -> str:
    """Return why ``operation`` must not edit glyph ``name``, or ``""``.

    Texts: ``"has auto layers"`` for an auto owner (every operation);
    ``"base of auto X, Y…"`` for a base of auto composites (``"rename"``,
    ``"unicode"``, ``"geometry"``, unless ``allow_bases``). An unknown
    operation raises ``ValueError``.
    """
    _require_operation(operation)
    if name in facts.autos:
        return "has auto layers"
    if operation not in STRUCTURAL or allow_bases:
        return ""
    found = facts.dependants(name)
    if not found:
        return ""
    return "base of auto " + ", ".join(found[:2]) + ("…" if len(found) > 2 else "")


def refusals(
    facts: AutoFacts,
    names: Iterable[str],
    operation: str,
    *,
    allow_bases: bool = False,
) -> dict[str, str]:
    """Return ``{refused name: reason}`` for ``names``, in their order.

    Names that ``operation`` may edit are left out. Use it to list refused
    rows in a preview before Apply.
    """
    found = {}
    for name in names:
        reason = refusal(facts, name, operation, allow_bases=allow_bases)
        if reason:
            found[name] = reason
    return found


def _refuse_auto(autos: Sequence[Any]) -> None:
    """Raise the auto-layer ``ValueError`` when ``autos`` is not empty."""
    if autos:
        shown = ", ".join(str(item.name) for item in autos[:3])
        raise ValueError(
            f"Refused: auto layer {shown} is in the edit list; "
            "FontLab would rebuild every auto layer in the font."
        )


def component_history(shape: Any) -> tuple[Any, ...]:
    """Return the native objects to retain when a script removes ``shape``.

    What: ``(shape, shape.shapeData, shapeData.builder)`` for a component;
    ``()`` for any other shape, so the result can always go to
    ``commit(..., retain=...)``. Same logic as glyport's
    ``_retain_component_history``.
    When: call it BEFORE ``removeShape``, outside ``mutate``. Glyport records
    that a builder read after detachment can already be too late (fl#7641).
    A component without shapeData raises ``ValueError``: nothing to retain is
    a fault, not an empty result. The builder is returned as FontLab gives it.
    """
    if not shape.isComponent:
        return ()
    data = shape.shapeData
    if data is None:
        raise ValueError("Component has no shape data; Undo cannot restore it.")
    return shape, data, data.builder


def _preflight(
    layers: Sequence[Any],
    glyphs: Sequence[Any],
    operation: str,
    facts: AutoFacts,
    allow_bases: bool,
    retain: Sequence[Any] = (),
) -> None:
    """Raise ``ValueError`` for an auto layer or a refused glyph. Write nothing.

    Layers must have ``autoLayer``. Retained objects (shapes, shapeData,
    builders) usually do not: ``getattr`` with a ``False`` default reads them,
    so only an object that says it is an auto layer is refused.
    """
    _require_operation(operation)
    _refuse_auto([layer for layer in layers if layer.autoLayer])
    _refuse_auto([item for item in retain if getattr(item, "autoLayer", False)])
    names = list(dict.fromkeys(str(glyph.name) for glyph in glyphs))
    refused = refusals(facts, names, operation, allow_bases=allow_bases)
    if refused:
        shown = "; ".join(f"{n}: {r}" for n, r in list(refused.items())[:3])
        more = f" (+{len(refused) - 3} more)" if len(refused) > 3 else ""
        raise ValueError(f"Refused. {shown}{more}.")


def _stamp_all(glyphs: Sequence[Any], stamp: Any, errors: list[Exception]) -> None:
    """Set ``lastModified`` on every glyph; collect each failure, go on."""
    for glyph in glyphs:
        try:
            glyph.lastModified = stamp
        except Exception as error:  # noqa: BLE001 - collected, raised by commit
            errors.append(error)


def commit(
    title: str,
    layers: Sequence[Any],
    glyphs: Sequence[Any],
    mutate: Callable[[], Iterable[Any] | None],
    *,
    operation: Operation,
    facts: AutoFacts,
    allow_bases: bool = False,
    read_back: Callable[[], Iterable[str]] | None = None,
    settled: bool = False,
    window: int | None = None,
    native: Any = None,
    stamp: Any = None,
    retain: Sequence[Any] = (),
    glyph_window_ok: bool = False,
) -> Committed:
    """Run ``mutate`` as ONE native Undo step. See the module text for the order.

    ``title``: the Undo name. ``layers``: every existing layer that ``mutate``
    changes (all layers of a glyph for renames and Unicode). ``glyphs``: their
    owner glyphs. ``mutate()``: the edit; return new native objects to notify,
    or ``None``. ``operation`` and ``facts``: the refusal policy (``facts``
    from a fresh ``scan_auto_facts``). ``allow_bases``: let bases of auto
    composites through after the user agreed. ``read_back()``: return one text
    per mismatch between font and plan. ``settled``: refuse queued native
    updates (explicit opt-in; default False discloses pre-write ids in
    ``Committed.pending_updates`` without clearing them). ``window``: the bound package id; when given, run
    ``require_selection_window`` and ``require_no_editors`` first (Unicode
    writers). ``native``/``stamp``: the ``fontlab`` module and the UTC stamp;
    the defaults are the native module and ``QDateTime.currentDateTimeUtc()``.
    ``retain``: native objects to keep in the Undo state, first in the list,
    with the deep-history flag ``True`` (use ``component_history`` for each
    removed component, read before the removal). They get no
    ``checkInitHistoryState`` and are not in ``Committed.created``. Empty:
    the two-argument notification, as before.
    ``glyph_window_ok``: skip the Glyph-window check
    (``edit_guards.require_history_scope``). Use it only for a caller that
    a native test proves safe; no caller uses it now.

    Raise ``ValueError`` before any history call for a refusal. Raise
    ``PartialWriteError`` when anything fails after history started, including
    a new auto layer from ``mutate`` (it stays out of the notification).
    """
    import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native

    module = _native("fontlab") if native is None else native
    ids = edit_guards.pending_updates(module)
    if settled and ids:
        raise ValueError("Native glyph updates are pending; finish the current edit first.")
    if window is not None:
        edit_guards.require_selection_window(window)
        edit_guards.require_no_editors(action="writing to the font")
    if not glyph_window_ok:
        edit_guards.require_history_scope(glyphs, native=module)
    retained = tuple(retain)
    _preflight(layers, glyphs, operation, facts, allow_bases, retained)
    when = (
        _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
        if stamp is None
        else stamp
    )
    for item in (*layers, *glyphs):
        try:
            item.checkInitHistoryState(0)
        except Exception as error:  # earlier items are initialised already
            raise PartialWriteError(title, [error]) from error
    errors: list[Exception] = []
    created: tuple[Any, ...] = ()
    try:
        created = tuple(mutate() or ())
    except Exception as error:  # noqa: BLE001 - finish history first, then raise
        errors.append(error)
    autos = [item for item in created if getattr(item, "autoLayer", False)]
    if autos:
        errors.append(ValueError(f"{len(autos)} new auto layer(s) left out of Undo"))
    notified = [
        *retained,
        *layers,
        *(item for item in created if item not in autos),
        *glyphs,
    ]
    _stamp_all(glyphs, when, errors)
    try:
        if retained:  # deep history, as glyport's _notify (fl#7641)
            module.flItems().notifyChangesApplied(title, notified, True)
        else:
            module.flItems().notifyChangesApplied(title, notified)
    except Exception as error:  # noqa: BLE001 - collected, raised below
        errors.append(error)
    _stamp_all(glyphs, when, errors)
    if errors:
        raise PartialWriteError(title, errors) from errors[0]
    try:
        mismatches = tuple(read_back()) if read_back is not None else ()
    except Exception as error:  # re-raised: the write already happened
        raise PartialWriteError(title, [error]) from error
    return Committed(created, mismatches, ids, edit_guards.pending_note(ids))


__all__ = [
    "CHECK_TEXT",
    "NOT_STORED",
    "OPERATIONS",
    "SHOWN_MISMATCHES",
    "STRUCTURAL",
    "UNDO_HINT",
    "AutoFacts",
    "Committed",
    "Operation",
    "PartialWriteError",
    "Record",
    "auto_facts",
    "commit",
    "component_history",
    "refusal",
    "refusals",
    "scan_auto_facts",
    "unstored_error",
]
