# this_file: src/fontlabapp/plugins/snapshot.py
"""Copy native FontLab glyph data into immutable, Python-only records."""

from collections import OrderedDict
from collections.abc import Callable, Mapping
import dataclasses
from dataclasses import dataclass
from importlib import import_module
from time import monotonic
from types import MappingProxyType
from typing import Any

import fontlabapp.components.decompose as decompose
from fontlabapp.glyphs import background as background_reader
from fontlabapp.glyphs import others as others_reader
from fontlabapp.glyphs.identity import Identity
from fontlabapp.glyphs.identity import read as read_identity
from fontlabapp.kerning import groups as groups_reader
from fontlabapp.masters.interpolation import outlines as master_reader

#: Most cached results kept; one per (datum, font, glyph, revision, layer) key.
_CACHE_LIMIT = 256
#: Identity and optional data or their read failures, shared by every reporter
#: and paint; least recent first.
_cache: "OrderedDict[tuple[Any, ...], Any]" = OrderedDict()
#: Keys of uncached failures already reported; least recent first.
_reported: "OrderedDict[tuple[Any, ...], None]" = OrderedDict()


@dataclass(frozen=True)
class Node:
    """A shape-transformed node in layer font units."""

    x: float
    y: float
    on_curve: bool
    selected: bool
    smooth: bool = False


@dataclass(frozen=True)
class Contour:
    """Nodes in native contour order."""

    nodes: tuple[Node, ...]
    closed: bool = True


@dataclass(frozen=True)
class Anchor:
    """A named anchor in layer font units."""

    name: str
    x: float
    y: float


@dataclass(frozen=True)
class Zone:
    """One selected-master alignment zone with its outer edge."""

    name: str
    position: float
    edge: float


@dataclass(frozen=True)
class Metrics:
    """Owner-master metrics; italic_slant is positive when the top leans right.

    ``zones`` stay empty when the shown layer belongs to another master;
    ``italic_slant`` stays the current master's. Both need a paint-unsafe
    master switch to read per master (``FontMetrics`` has neither).
    """

    ascender: float
    descender: float
    x_height: float
    cap_height: float
    italic_slant: float
    upm: float
    zones: tuple[Zone, ...] = ()


@dataclass(frozen=True)
class Neighbours:
    """Same-line neighbours as ``(name, displayed kerning)``, or None per side."""

    prev: tuple[str, float] | None = None
    next: tuple[str, float] | None = None


@dataclass(frozen=True)
class ViewState:
    """Per-paint view data; never part of the cacheable captured content."""

    px_per_unit: float
    mouse: tuple[float, float] | None = None
    neighbours: Neighbours | None = None


@dataclass(frozen=True)
class Component:
    """One component: base name, (m11, m12, m21, m22, dx, dy) and contours.

    contours are the decomposed base outlines, nested components
    included, already placed in the displayed layer's units.
    """

    base: str
    transform: tuple[float, float, float, float, float, float]
    contours: tuple[Contour, ...]


@dataclass(frozen=True)
class MasterOutline:
    """One master layer of the glyph, with unselected nodes.

    ``compatible`` compares contour count, node count per contour and the
    on/off-curve pattern with the shown layer's own contours. It ignores
    components and the open/closed state. Caching: see ``capture``.
    """

    name: str
    contours: tuple[Contour, ...]
    anchors: tuple[Anchor, ...]
    advance: float
    compatible: bool


@dataclass(frozen=True)
class KerningGroups:
    """The glyph's kerning classes in the owner master (caching: see ``capture``).

    ``left`` is the class used when the glyph is a pair's first member
    (KernLeft or KernBothSide), ``right`` when it is the second (KernRight or
    KernBothSide); a side-specific class wins, then native order. ``members``
    maps each chosen class to its members.
    """

    left: str | None
    right: str | None
    members: Mapping[str, tuple[str, ...]] = dataclasses.field(hash=False)


#: The shared empty, read-only mapping for snapshots without requested glyphs.
_NO_OTHERS: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class GlyphSnapshot:
    """Read-only data needed by reporter computations.

    ``others`` maps each requested glyph name that exists in the owner master
    to that layer's own unselected contours (components skipped), cached per
    requested glyph's own revision. Mapping fields are left out of the hash,
    so snapshots stay hashable (equal snapshots still hash equal).
    """

    contours: tuple[Contour, ...]
    anchors: tuple[Anchor, ...]
    advance: float
    metrics: Metrics
    bounds: tuple[float, float, float, float] | None = None
    identity: Identity | None = None
    view: ViewState | None = None
    components: tuple[Component, ...] = ()
    background: tuple[Contour, ...] | None = None
    masters: tuple[MasterOutline, ...] = ()
    kerning_groups: KerningGroups | None = None
    others: Mapping[str, tuple[Contour, ...]] = dataclasses.field(
        default_factory=lambda: _NO_OTHERS, hash=False
    )
    #: Source identity fences Tool interactions without changing content equality.
    source_key: tuple[int, int, int, str] | None = dataclasses.field(
        default=None, compare=False, hash=False
    )


@dataclass(frozen=True)
class NativeSource:
    """Short-lived handles resolved from one editor glyph item."""

    package: Any
    layer: Any
    glyph: Any = None


@dataclass(frozen=True)
class ActiveGlyph:
    """Checked current glyph and its selected-master layer for palette actions."""

    package: Any
    glyph: Any
    layer: Any


def active_glyph(
    fontlab: Any,
    *,
    items: Callable[[Callable[[], Any]], list[Any]] | None = None,
) -> ActiveGlyph | None:
    """Resolve the active canvas slot against the workspace's current package."""
    workspace = fontlab.flWorkspace.instance()
    package = workspace.currentPackage
    if package is None or package.isNull or workspace.activeFontPanel is not None:
        return None
    canvas = workspace.getActiveCanvas()
    if canvas is None or canvas.isNull:
        return None
    if items is None:
        items = import_module("fontlabapp.qt.safe").qt_list
    for block in items(canvas.textBlocks):
        for index in range(int(block.glyphsCount())):
            info = block.getGlyphAt(index)
            if info is None or not info.isActive:
                continue
            glyph = info.glyph
            if (
                glyph is None
                or glyph.isNull
                or int(glyph.package.fgId) != int(package.fgId)
            ):
                return None
            name = str(info.symbol.layerName)
            layer = glyph.findLayer(name or package.master)
            return (
                None
                if layer is None or layer.isNull
                else ActiveGlyph(package, glyph, layer)
            )
    return None


def _revision(glyph: Any) -> Any:
    """Read ``glyph.lastModified`` as epoch milliseconds when it is a QDateTime."""
    stamp = glyph.lastModified
    return stamp.toMSecsSinceEpoch() if hasattr(stamp, "toMSecsSinceEpoch") else stamp


def palette_key(
    active: ActiveGlyph | None,
    *,
    items: Callable[[Callable[[], Any]], list[Any]] | None = None,
) -> tuple[Any, ...] | None:
    """Read a cheap revision and node-selection key without a full snapshot."""
    if active is None:
        return None
    if items is None:
        items = import_module("fontlabapp.qt.safe").qt_list
    revision = _revision(active.glyph)
    # This checks every native node each tick; keep capture itself behind the key.
    selected = []
    for shape in items(lambda: active.layer.shapes):
        if shape.isComponent:
            continue
        for contour in items(lambda shape=shape: shape.contours):
            selected.append(tuple(bool(node.selected) for node in items(contour.nodes)))
    return (
        int(active.package.fgId),
        int(active.glyph.id),
        str(active.package.master),
        revision,
        tuple(selected),
    )


def selected_layers() -> Any:
    """Read the active Font/Glyph window selection through App's checked adapter."""
    return import_module("fontlabapp.masters.layers.selection").capture(monotonic() + 2)


def select_contours(
    layer: Any,
    indices: tuple[int, ...],
    *,
    toggle: bool = False,
    items: Callable[[Callable[[], Any]], list[Any]] | None = None,
) -> None:
    """Select whole editable contours by index; never change outline geometry."""
    items = items or import_module("fontlabapp.qt.safe").qt_list
    contours = [
        contour
        for shape in items(lambda: layer.shapes)
        if not shape.isComponent
        for contour in items(lambda shape=shape: shape.contours)
    ]
    targets = set(indices)
    for index, contour in enumerate(contours):
        nodes = items(contour.nodes)
        if toggle:
            if index in targets:
                selected = not all(bool(node.selected) for node in nodes)
                for node in nodes:
                    node.selected = selected
        else:
            for node in nodes:
                node.selected = index in targets


def resolve_source(info: Any) -> NativeSource | None:
    """Resolve the layer the text slot shows, as ``active_glyph`` does.

    ``info.symbol.layerName`` (a-stub ``fgSymbol.layerName``) names a slot's
    layer override; empty means the package's current master (b: active_glyph).
    A null or missing symbol also means the master, so one odd slot never
    aborts the overlay.
    """
    glyph = info.glyph
    if glyph is None or glyph.isNull:
        return None
    package = glyph.package
    name = getattr(getattr(info, "symbol", None), "layerName", None)
    layer = glyph.findLayer(str(name or "") or package.master)
    if layer is None or layer.isNull:
        return None
    return NativeSource(package, layer, glyph)


def _contours(
    layer: Any,
    items: Callable[[Callable[[], Any]], list[Any]],
    *,
    selection: bool = True,
) -> tuple[Contour, ...]:
    """Read editable outlines and apply each shape's native transform.

    ``selection=False`` clears every node's ``selected`` flag, for layers that
    are not edited in place (cached masters, the mask).
    """
    rows = []
    for shape in items(lambda: layer.shapes):
        if shape.isComponent:
            continue
        for contour in items(lambda shape=shape: shape.contours):
            nodes = []
            for node in items(contour.nodes):
                point = shape.transform.map(node.position)
                nodes.append(
                    Node(
                        float(point.x()),
                        float(point.y()),
                        bool(node.isOn()),
                        bool(node.selected) if selection else False,
                        bool(getattr(node, "smooth", False)),
                    )
                )
            rows.append(Contour(tuple(nodes), bool(getattr(contour, "closed", True))))
    return tuple(rows)


def _zones(
    package: Any, items: Callable[[Callable[[], Any]], list[Any]]
) -> tuple[Zone, ...]:
    """Read the selected master's native PostScript top and bottom zones."""
    zones = []
    for field, direction in (("ps_zonesT", 1), ("ps_zonesB", -1)):
        for item in items(lambda field=field: getattr(package, field, ())):
            position = float(item.position)
            zones.append(
                Zone(str(item.name), position, position + direction * float(item.width))
            )
    return tuple(zones)


def _bounds(layer: Any) -> tuple[float, float, float, float] | None:
    """Copy the native ink box, including curve extrema and components."""
    box = getattr(layer, "boundingBox", None)
    if box is None or (box.width() <= 0 and box.height() <= 0):
        return None
    x, y = float(box.x()), float(box.y())
    return x, y, x + float(box.width()), y + float(box.height())


def _anchors(
    layer: Any, items: Callable[[Callable[[], Any]], list[Any]]
) -> tuple[Anchor, ...]:
    """Copy a layer's named anchors."""
    return tuple(
        Anchor(str(pin.name), float(pin.point.x()), float(pin.point.y()))
        for pin in items(lambda: layer.anchors)
    )


def _raise(error: Exception) -> None:
    """Report partial-read problems by raising when the caller gave no sink."""
    raise error


_MISSING = object()


def _cached(
    kind: str,
    source: NativeSource,
    read: Callable[[Callable[[Exception], object]], Any],
    report: Callable[[Exception], object] | None,
    default: Any,
    still: Callable[[Any], bool] | None = None,
    owner: str | None = None,
) -> Any:
    """Read one datum once per glyph revision, keyed (datum, font, glyph, layer).

    A datum that depends on the owner master passes ``owner``; it joins the key.

    The entry holds ``(revision, value)``; a new ``lastModified`` replaces it,
    so each glyph keeps one entry per datum. Every reporter and paint shares
    the result, however many reporters ask. ``read(report)`` may report
    partial problems; it runs only on a miss, so they are reported once.
    ``still(value)`` can turn a hit into a miss. A failure is cached too:
    reported on the miss, then ``default`` without a re-read. Without
    ``report`` a failure raises and is not cached. A failed key read is not
    cached; it is reported or raised each time. ``lastModified`` also moves
    on unrelated queued writes (fl#8537), which only re-reads early.
    """
    try:
        glyph = source.glyph
        key = (
            kind,
            int(source.package.fgId),
            int(glyph.id),
            str(source.layer.name),
            owner,
        )
        revision = _revision(glyph)
    except Exception as error:  # noqa: BLE001 - optional data degrades
        if report is None:
            raise
        report(error)
        return default
    stored, value = _cache.get(key, (_MISSING, _MISSING))
    fresh = stored != revision or (
        still is not None and not isinstance(value, Exception) and not still(value)
    )
    if fresh:
        try:
            value = read(report or _raise)
        except Exception as error:  # noqa: BLE001 - cached, reported below
            # Drop the traceback: its frames would keep native wrappers alive.
            value = error.with_traceback(None)
        _cache[key] = (revision, value)
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_LIMIT:
        _cache.popitem(last=False)
    if not isinstance(value, Exception):
        return value
    if report is None:
        _cache.pop(key)  # raising re-attaches frames; keep none cached
        raise value
    if fresh:
        report(value)
    return default


def _stamp(glyph: Any) -> Any:
    """A base glyph's revision, or None when it is missing."""
    return None if glyph is None or glyph.isNull else _revision(glyph)


def _once(
    kind: str,
    source: NativeSource,
    error: Exception,
    report: Callable[[Exception], object] | None,
) -> None:
    """Report an uncached failure once per (datum, glyph, layer, message).

    Without ``report`` the failure raises, as every failure without a sink.
    """
    if report is None:
        raise error
    try:
        where = (
            int(source.package.fgId),
            int(source.glyph.id),
            str(source.layer.name),
        )
    except Exception:  # noqa: BLE001 - dedupe by message alone
        where = None
    if first_report((kind, where, type(error).__name__, str(error))):
        report(error)


def first_report(key: tuple[Any, ...]) -> bool:
    """True the first time ``key`` is seen since ``reset()``; bounded LRU."""
    if key in _reported:
        _reported.move_to_end(key)
        return False
    _reported[key] = None
    while len(_reported) > _CACHE_LIMIT:
        _reported.popitem(last=False)
    return True


def reset() -> None:
    """Forget cached reads and reported errors; backends call this on close()."""
    _cache.clear()
    _reported.clear()


def _bases_unchanged(
    package: Any,
    stamps: tuple[tuple[str, Any], ...],
    failed: Callable[[Exception], object],
) -> bool:
    """True while every looked-up base glyph keeps its decomposition stamp.

    Base edits do not move the composite's ``lastModified`` (map §5, c), so
    a component hit re-checks one ``findName`` and stamp per base. A check
    that raises keeps the entry and goes to ``failed``, so it never turns
    every paint into a re-read that re-reports the same skips.
    """
    try:
        return all(_stamp(package.findName(name)) == stamp for name, stamp in stamps)
    except Exception as error:  # noqa: BLE001 - reported once, entry kept
        failed(error)
        return True


def _components(
    source: NativeSource,
    items: Callable[[Callable[[], Any]], list[Any]],
    report: Callable[[Exception], object],
) -> tuple[tuple[Component, ...], tuple[tuple[str, Any], ...]]:
    """Decomposed components of the shown layer, with their base stamps."""
    rows, stamps = decompose.read(
        source.package,
        str(source.glyph.name),
        source.layer,
        lambda layer: _contours(layer, items),
        items=items,
        revision=_revision,
        report=report,
    )
    return tuple(Component(*row) for row in rows), stamps


def _masters(
    source: NativeSource,
    shown: tuple[Contour, ...],
    items: Callable[[Callable[[], Any]], list[Any]],
) -> tuple[MasterOutline, ...]:
    """Every master layer of the glyph, compared with the shown contours."""
    rows = master_reader.read(
        source.package,
        source.glyph,
        shown,
        lambda layer: _contours(layer, items, selection=False),
        lambda layer: _anchors(layer, items),
        items=items,
    )
    return tuple(MasterOutline(*row) for row in rows)


def _kerning_groups(source: NativeSource, owner: str) -> KerningGroups:
    """The shown glyph's kerning classes in the owner master; never cached."""
    left, right, members = groups_reader.read(
        source.package, owner, str(source.glyph.name)
    )
    return KerningGroups(left, right, MappingProxyType(members))


def _others(
    source: NativeSource,
    owner: str,
    names: tuple[str, ...],
    items: Callable[[Callable[[], Any]], list[Any]],
    report: Callable[[Exception], object] | None,
) -> Mapping[str, tuple[Contour, ...]]:
    """Own contours of each requested glyph's owner-master layer, by name.

    Each glyph is looked up every paint; its contours are cached on its own
    (fgId, glyph id, lastModified, layer). A missing glyph or layer is absent;
    a failed lookup or read is reported once and that name is absent.
    """
    found = {}
    for name in names:
        try:
            hit = others_reader.find(source.package, name, owner)
        except Exception as error:  # noqa: BLE001 - optional data degrades
            _once("others", source, error, report)
            continue
        if hit is None:
            continue
        glyph, layer = hit
        contours = _cached(
            "others",
            NativeSource(source.package, layer, glyph),
            lambda _, layer=layer: _contours(layer, items, selection=False),
            report,
            None,
        )
        if contours is not None:
            found[name] = contours
    return MappingProxyType(found)


def capture(
    source: NativeSource,
    *,
    fontlab: Any = None,
    items: Callable[[Callable[[], Any]], list[Any]] | None = None,
    include_zones: bool = False,
    include_bounds: bool = False,
    include_components: bool = False,
    include_background: bool = False,
    include_masters: bool = False,
    include_kerning: bool = False,
    requested: Callable[..., tuple[str, ...]] | None = None,
    report: Callable[[Exception], object] | None = None,
) -> GlyphSnapshot:
    """Read one current native layer; inject native adapters in offline tests.

    Metrics, components, kerning groups and requested glyphs come from the
    master that owns the shown layer (``decompose.owner_master``). Zones are
    read only when that is the current master; another master's zones need a
    paint-unsafe master switch. A source with a glyph also yields its
    identity and the opted-in data. Identity, components and masters are
    cached per glyph revision (``_cached``; masters may lag until the glyph's
    ``lastModified`` moves); background and kerning groups, whose edits may
    not move it, are read on every paint. ``requested(identity, groups)`` names glyphs for ``others``; it is asked
    only when identity was read and must not raise. ``report`` receives a
    failed read once and the field keeps its default; without ``report`` the
    failure raises.
    """
    if fontlab is None:
        fontlab = import_module("fontlab")
    if items is None:
        items = import_module("fontlabapp.qt.safe").qt_list
    layer, package, glyph = source.layer, source.package, source.glyph
    owner_known = True
    try:
        owner = decompose.owner_master(package, layer, items)
    except Exception as error:  # noqa: BLE001 - a masters read must not block paint
        _once("owner_master", source, error, report)
        owner = str(package.master)
        owner_known = False
    metrics = fontlab.FontMetrics(package, owner)
    current = owner == str(package.master)
    anchors = _anchors(layer, items)
    values = Metrics(
        float(metrics.ascender),
        float(metrics.descender),
        float(metrics.xHeight),
        float(metrics.capsHeight),
        # OpenType post uses counter-clockwise degrees from vertical.
        -float(package.italicAngle_value),
        float(package.upm),
        _zones(package, items) if include_zones and current else (),
    )
    contours = _contours(layer, items)
    identity, components, background, masters = None, (), None, ()
    groups, others = None, _NO_OTHERS
    source_key = None
    if glyph is not None and owner_known:
        try:
            ids = (
                getattr(package, "fgId", None),
                getattr(glyph, "id", None),
                getattr(layer, "id", None),
            )
            if all(value is not None for value in ids):
                source_key = (int(ids[0]), int(ids[1]), int(ids[2]), owner)
        except Exception as error:  # noqa: BLE001 - optional source identity degrades
            _once("source_key", source, error, report)
    if glyph is not None:
        identity = _cached(
            "identity", source, lambda _: read_identity(package, glyph), report, None
        )
        if include_components:
            components = _cached(
                "components",
                source,
                lambda sink: _components(source, items, sink),
                report,
                ((), ()),
                still=lambda value: _bases_unchanged(
                    package,
                    value[1],
                    lambda error: _once("components", source, error, report),
                ),
                owner=owner,
            )[0]
        if include_background:
            # Cheap and uncached: a mask edit may not move lastModified (c).
            sink = lambda error: _once("background", source, error, report)
            try:
                background = background_reader.read(
                    glyph,
                    layer,
                    lambda mask: _contours(mask, items, selection=False),
                    sink,
                )
            except Exception as error:  # noqa: BLE001 - optional data degrades
                sink(error)
        if include_masters:
            masters = _cached(
                "masters",
                source,
                lambda _: _masters(source, contours, items),
                report,
                (),
            )
        if include_kerning:
            try:
                groups = _kerning_groups(source, owner)
            except Exception as error:  # noqa: BLE001 - optional data degrades
                _once("kerning", source, error, report)
        names = (
            () if requested is None or identity is None else requested(identity, groups)
        )
        if names:
            try:
                others = _others(source, owner, names, items, report)
            except Exception as error:  # noqa: BLE001 - optional data degrades
                _once("others", source, error, report)
    return GlyphSnapshot(
        contours,
        anchors,
        float(layer.advanceWidth),
        values,
        _bounds(layer) if include_bounds else None,
        identity,
        None,
        components,
        background,
        masters,
        groups,
        others,
        source_key,
    )
