# this_file: src/fontlabapp/contours/angularizzle/native.py
# SPDX-License-Identifier: Apache-2.0
"""Native Angularizzle boundary with private rich backups and source fences.

The occurrence provider supplies actual selected layers, including repeats. This
adapter resolves first-master targets, preserves separate source inputs, stages
all geometry before history and retains components. Native acceptance is pending.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fontlabapp import _native
from fontlabapp.contours.angularizzle._native_records import (
    clone_shape,
    read_layer,
    shape_record,
)
from fontlabapp.contours.angularizzle._native_write import (
    NativeAdapterError,
    prepare,
    publish,
)
from fontlabapp.contours.angularizzle.model import _check_deadline
from fontlabapp.contours.angularizzle.session import Capture, LayerSnapshot

if TYPE_CHECKING:
    from fontlabapp.masters.layers.selection import LayerSelection


@dataclass
class _Bound:
    package: Any
    glyph: Any
    layer: Any
    snapshot: LayerSnapshot
    fingerprint: tuple
    owners: tuple
    originals: tuple = ()
    backed_up: bool = False
    glyph_name: str = ""
    glyph_id: int = 0
    layer_id: int = 0
    history: int = 0

    def __post_init__(self) -> None:
        self.history = int(self.glyph.currentHistoryState())
        self.glyph_name, self.glyph_id, self.layer_id = (
            str(self.glyph.name),
            int(self.glyph.id),
            int(self.layer.id),
        )


def _key(package: Any, glyph: Any, layer: Any) -> str:
    return f"{int(package.id)}:{int(glyph.id)}:{int(layer.id)}"


def _occurrences(selection: Any, deadline: float) -> tuple:
    facts = []
    for occurrence in selection.occurrences:
        _check_deadline(deadline)
        facts.append(
            (
                int(occurrence.package_id),
                int(occurrence.glyph_id),
                int(occurrence.layer_id),
                int(occurrence.block_id),
                int(occurrence.index),
            )
        )
    return tuple(facts)


def _unsafe_dependants(records: tuple, targets: set, deadline: float) -> list[str]:
    """Follow manual/automatic component chains with the same action deadline."""
    uses, automatic = {}, set()
    for name, auto, bases in records:
        _check_deadline(deadline)
        if auto:
            automatic.add(name)
        for base in bases:
            _check_deadline(deadline)
            uses.setdefault(base, set()).add(name)
    seen, pending = set(), set(targets)
    while pending:
        _check_deadline(deadline)
        name = pending.pop()
        if name not in seen:
            seen.add(name)
            pending.update(uses.get(name, set()) - seen)
    return sorted(automatic & seen)


class NativeBackend:
    """Consume layer_selection.capture or an injected identical provider.

    No native import occurs until capture. Provider context excludes modeless Qt
    focus; selection=False still fences font/master/document and native sources.
    A failed native publication permanently poisons this writer instance.
    """

    def __init__(
        self,
        provider: Callable[[float], "LayerSelection"] | None = None,
        native: Callable[[str], Any] = _native,
        context_provider: Callable[[float], tuple] | None = None,
    ) -> None:
        self.provider, self.native, self.context_provider = (
            provider,
            native,
            context_provider,
        )
        self.poisoned = False
        self.error: str | None = None
        self.recovery: tuple = ()
        self._source: Capture | None = None
        self._bound: dict[str, _Bound] = {}

    def _selection(self, deadline: float) -> Any:
        _check_deadline(deadline)
        if self.provider is None:
            from fontlabapp.masters.layers.selection import capture

            selection = capture(deadline)
        else:
            selection = self.provider(deadline)
        _check_deadline(deadline)
        return selection

    def _context_now(self, deadline: float) -> tuple:
        if self.context_provider is not None:
            result = self.context_provider(deadline)
        elif self.provider is not None:
            result = self._selection(deadline).context
        else:
            from fontlabapp.masters.layers.selection import document_context

            result = document_context(deadline)
        _check_deadline(deadline)
        return result

    def _registered(self, package: Any, deadline: float) -> Any:
        native = self.native("fontlab")
        workspace = native.flWorkspace.instance()
        _check_deadline(deadline)
        registered = set()
        for item in workspace.packages():
            _check_deadline(deadline)
            registered.add(int(native.flPackage(item).id))
        current = workspace.currentPackage
        expected = self._package_id if self._source is not None else int(package.id)
        if current is None or expected not in registered or int(current.id) != expected:
            raise ValueError(
                "Angularizzle source package changed or is no longer registered."
            )
        font = native.CurrentFont()
        if font is None or int(font.id) != int(current.fgId):
            raise ValueError("Angularizzle current font carrier changed.")
        _check_deadline(deadline)
        return font

    def _dependencies(self, package: Any, deadline: float) -> tuple:
        font = self._registered(package, deadline)
        records = []
        for record in font.glyphs:
            _check_deadline(deadline)
            glyph = package.findName(record.name)
            if glyph is None:
                raise ValueError("Angularizzle glyph source changed.")
            for layer in glyph.layers:
                _check_deadline(deadline)
                bases = []
                for shape in layer.shapes:
                    _check_deadline(deadline)
                    if shape.isComponent:
                        bases.append(str(shape.shapeData.componentGlyph))
                records.append((str(glyph.name), bool(layer.autoLayer), tuple(bases)))
        _check_deadline(deadline)
        return tuple(records)

    def _read(self, package: Any, glyph: Any, layer: Any, deadline: float) -> _Bound:
        if package.findName(glyph.name) is None or int(
            package.findName(glyph.name).id
        ) != int(glyph.id):
            raise ValueError("Angularizzle glyph identity changed.")
        available = set()
        for row in glyph.layers:
            _check_deadline(deadline)
            available.add(int(row.id))
        if int(layer.id) not in available:
            raise ValueError("Angularizzle layer identity changed.")
        paths, fingerprint, owners = read_layer(layer, deadline)
        # Numeric color belongs to the session; preserve actual native hue privately.
        snapshot = LayerSnapshot(
            _key(package, glyph, layer), paths, 8 if int(layer.mark) == 280 else None
        )
        return _Bound(package, glyph, layer, snapshot, fingerprint, owners)

    def _resolve(self, bound: _Bound, deadline: float) -> _Bound:
        """Check registration using cached ids before dereferencing stored children."""
        self._registered(bound.package, deadline)
        package = self.native("fontlab").flWorkspace.instance().currentPackage
        glyph = package.findName(bound.glyph_name)
        if glyph is None or int(glyph.id) != bound.glyph_id:
            raise ValueError("Angularizzle bound glyph identity changed.")
        layer = None
        for row in glyph.layers:
            _check_deadline(deadline)
            if int(row.id) == bound.layer_id:
                layer = row
                break
        if layer is None:
            raise ValueError("Angularizzle bound layer identity changed.")
        return self._read(package, glyph, layer, deadline)

    def capture(self, deadline: float) -> Capture:
        """Bind ordered source occurrences and first-master targets, read twice."""
        _check_deadline(deadline)
        if self._source is not None:
            raise ValueError(
                "Angularizzle backend already has a session; reopen with a new backend."
            )
        first = self._selection(deadline)
        if not first.occurrences:
            raise ValueError("Select glyph layers before opening Angularizzle.")
        bound, targets, inputs = {}, [], []
        package = first.occurrences[0].package
        self._registered(package, deadline)
        for occurrence in first.occurrences:
            _check_deadline(deadline)
            if int(occurrence.package.id) != int(package.id):
                raise ValueError(
                    "Angularizzle selected occurrences cross source packages."
                )
            masters = tuple(str(m) for m in package.masters)
            if not masters:
                raise ValueError("Angularizzle source has no first master.")
            target = occurrence.glyph.findLayer(masters[0])
            if target is None:
                raise ValueError("Angularizzle first-master layer is missing.")
            for layer, rows in ((target, targets), (occurrence.layer, inputs)):
                row = self._read(package, occurrence.glyph, layer, deadline)
                previous = bound.setdefault(row.snapshot.key, row)
                if previous.fingerprint != row.fingerprint:
                    raise ValueError(
                        "Angularizzle layer source changed during capture."
                    )
                rows.append(row.snapshot)
        dependencies = self._dependencies(package, deadline)
        blocked = _unsafe_dependants(
            dependencies, {o.glyph.name for o in first.occurrences}, deadline
        )
        if blocked:
            raise ValueError(
                "Angularizzle cannot safely edit automatic dependants: "
                + ", ".join(blocked)
            )
        second = self._selection(deadline)
        if first.context != second.context or _occurrences(
            first, deadline
        ) != _occurrences(second, deadline):
            raise ValueError("Angularizzle selection/context changed during capture.")
        self._selection_keep = first  # retain provider widget/document carriers
        self._context, self._selected, self._dependencies_before = (
            first.context,
            _occurrences(first, deadline),
            dependencies,
        )
        self._package_id = int(package.id)
        self._masters, self._master = tuple(package.masters), str(package.master)
        self._bound = bound
        source = Capture(repr(first.context), tuple(targets), tuple(inputs))
        self._source = source
        try:
            self.check(source, selection=True, deadline=deadline)
        except BaseException:
            self._source, self._bound = None, {}
            raise
        return source

    def check(self, source: Capture, *, selection: bool, deadline: float) -> None:
        """Reject changed registration, document, master, selection or observed data."""
        if self.poisoned:
            raise NativeAdapterError(
                "Angularizzle writer failed; review native history before reopening."
            )
        if source is not self._source:
            raise ValueError("Angularizzle capture does not belong to this backend.")
        fresh = self._selection(deadline) if selection else None
        context = fresh.context if fresh is not None else self._context_now(deadline)
        if context != self._context or (
            selection and _occurrences(fresh, deadline) != self._selected
        ):
            raise ValueError("Angularizzle selection/context changed; reopen the tool.")
        package = next(iter(self._bound.values())).package
        self._registered(package, deadline)
        package = self.native("fontlab").flWorkspace.instance().currentPackage
        if (
            tuple(package.masters) != self._masters
            or str(package.master) != self._master
        ):
            raise ValueError("Angularizzle master source changed.")
        if self._dependencies(package, deadline) != self._dependencies_before:
            raise ValueError("Angularizzle component dependency source changed.")
        for bound in self._bound.values():
            _check_deadline(deadline)
            fresh_bound = self._resolve(bound, deadline)
            if (
                fresh_bound.fingerprint != bound.fingerprint
                or fresh_bound.history != bound.history
            ):
                raise ValueError(
                    "Angularizzle observed layer source changed; reopen the tool."
                )
            bound.package, bound.glyph, bound.layer = (
                fresh_bound.package,
                fresh_bound.glyph,
                fresh_bound.layer,
            )
        final = self._selection(deadline) if selection else None
        if (
            final.context if final is not None else self._context_now(deadline)
        ) != self._context or (
            selection and _occurrences(final, deadline) != self._selected
        ):
            raise ValueError(
                "Angularizzle selection/context changed during verification."
            )
        _check_deadline(deadline)

    def apply(
        self,
        source: Capture,
        before: tuple[LayerSnapshot, ...],
        after: tuple[LayerSnapshot, ...],
        *,
        restore: bool,
        deadline: float,
    ) -> None:
        """Stage every replacement before history; poison on any native write error."""
        self.check(source, selection=not restore, deadline=deadline)
        required = {row.key for row in source.layers}
        if (
            len(before) != len(after)
            or len({r.key for r in before}) != len(before)
            or {row.key for row in before} != required
        ):
            raise ValueError(
                "Angularizzle requires one before/after record per target."
            )
        inputs = {
            target.key: value
            for target, value in zip(
                source.layers, source.inputs or source.layers, strict=True
            )
        }
        jobs, backups, expected = [], {}, {}
        native, qt = self.native("fontlab"), self.native("PythonQt")
        try:
            for old, new in zip(before, after, strict=True):
                _check_deadline(deadline)
                bound = self._bound.get(old.key)
                if (
                    bound is None
                    or old.key != new.key
                    or old != bound.snapshot
                    or new.color != 8
                ):
                    raise ValueError(
                        "Angularizzle plan does not match its bound native target."
                    )
                if not bound.backed_up and old.paths != new.paths:
                    backups[old.key] = tuple(
                        (i, clone_shape(s, deadline))
                        for i, s in enumerate(bound.layer.shapes)
                        if not s.isComponent and s.contours
                    )
                replacements = prepare(
                    bound, old, new, inputs[old.key], restore, native, qt, deadline
                )
                jobs.append((bound, replacements, 280, int(bound.layer.mark)))
                fields = list(bound.fingerprint)
                fields[1] = 280
                shapes = list(fields[-1])
                for index, _, shape in replacements:
                    if shape is None:
                        shapes.pop(index)
                    elif index == len(shapes):
                        shapes.append(shape_record(shape, deadline))
                    else:
                        shapes[index] = shape_record(shape, deadline)
                fields[-1] = tuple(shapes)
                expected[old.key] = tuple(fields)
        except (ValueError, TimeoutError):
            raise
        except BaseException as error:
            raise NativeAdapterError(f"Angularizzle staging failed: {error}") from error
        self.check(source, selection=not restore, deadline=deadline)
        for key, values in backups.items():
            self._bound[key].originals = values
            self._bound[key].backed_up = True
        self.recovery = tuple(jobs)
        try:
            publish(tuple(jobs), native, qt, deadline)
            for bound in self._bound.values():
                fresh = self._resolve(bound, deadline)
                planned = next(
                    (row for row in after if row.key == bound.snapshot.key),
                    bound.snapshot,
                )
                if (
                    fresh.snapshot.paths != planned.paths
                    or fresh.fingerprint
                    != expected.get(bound.snapshot.key, bound.fingerprint)
                ):
                    raise NativeAdapterError(
                        "Angularizzle post-write verification failed; native data changed. Review history before reopening."
                    )
                bound.fingerprint, bound.history = fresh.fingerprint, fresh.history
            if (
                self._context_now(deadline) != self._context
                or self._dependencies(
                    next(iter(self._bound.values())).package, deadline
                )
                != self._dependencies_before
            ):
                raise NativeAdapterError(
                    "Angularizzle post-write context/dependencies changed; review native history."
                )
            for new in after:
                self._bound[new.key].snapshot = new
        except BaseException as error:
            self.poisoned = True
            self.error = str(error)
            raise
        self.recovery = ()


__all__ = ["NativeAdapterError", "NativeBackend"]
