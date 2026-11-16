# this_file: tests/plugmix/test_plugmix_snapshot.py
"""Fake native FontLab objects shaped like the layer and metric APIs."""

from dataclasses import FrozenInstanceError
from types import MappingProxyType
from types import SimpleNamespace as NS

import pytest

from fontlabapp.glyphs.identity import Identity
from fontlabapp.plugins import snapshot as snapshot_module
from fontlabapp.plugins.snapshot import (
    ActiveGlyph,
    Component,
    GlyphSnapshot,
    KerningGroups,
    MasterOutline,
    Metrics,
    NativeSource,
    Neighbours,
    ViewState,
    active_glyph,
    capture,
    palette_key,
    resolve_source,
)


class Point:
    """Qt-like point with x()/y() accessors."""

    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Transform:
    """Translate points as a fake shape transform."""

    def map(self, point):
        return Point(point.x() + 10, point.y() - 5)


def test_resolve_source_uses_glyph_master_and_ignores_null():
    package = NS(master="Regular")
    layer = NS(isNull=False)
    glyph = NS(isNull=False, package=package, findLayer=lambda master: layer)
    shown = NS(layerName="")
    assert resolve_source(NS(glyph=glyph, symbol=shown)) == NativeSource(
        package, layer, glyph
    ), "the source keeps the glyph for identity reads"
    assert resolve_source(NS(glyph=None, symbol=shown)) is None
    assert resolve_source(NS(glyph=NS(isNull=True), symbol=shown)) is None
    glyph.findLayer = lambda master: NS(isNull=True)
    assert resolve_source(NS(glyph=glyph, symbol=shown)) is None


def test_resolve_source_when_slot_shows_named_layer_then_paints_that_layer():
    package = NS(master="Regular")
    layers = {"Regular": NS(isNull=False), "Alt": NS(isNull=False)}
    asked = []
    glyph = NS(
        isNull=False,
        package=package,
        findLayer=lambda name: asked.append(name) or layers[name],
    )
    source = resolve_source(NS(glyph=glyph, symbol=NS(layerName="Alt")))
    assert source.layer is layers["Alt"], "text slot layer overrides the master"
    source = resolve_source(NS(glyph=glyph, symbol=NS(layerName="")))
    assert source.layer is layers["Regular"], "empty slot layer means the master"
    assert asked == ["Alt", "Regular"]


def test_capture_copies_transformed_nodes_anchors_metrics_immutably():
    package = NS(
        master="Regular",
        italicAngle_value=-12,
        upm=1000,
        ps_zonesT=[NS(name="cap", position=700, width=12)],
        ps_zonesB=[NS(name="baseline", position=0, width=15)],
    )
    node = NS(position=Point(1, 2), isOn=lambda: True, selected=True, smooth=True)
    off = NS(position=Point(3, 4), isOn=lambda: False, selected=False)
    contour = NS(nodes=lambda: [node, off], closed=False)
    outline = NS(isComponent=False, contours=[contour], transform=Transform())
    component = NS(isComponent=True, contours=[contour], transform=Transform())
    layer = NS(
        name="Regular",
        shapes=[outline, component],
        anchors=[NS(name="top", point=Point(5, 6))],
        advanceWidth=600,
        boundingBox=NS(
            x=lambda: 10, y=lambda: -20, width=lambda: 120, height=lambda: 500
        ),
    )
    metrics = NS(ascender=800, descender=-200, xHeight=500, capsHeight=700)
    fontlab = NS(FontMetrics=lambda pkg, master: metrics)
    snapshot = capture(
        NativeSource(package, layer),
        fontlab=fontlab,
        items=lambda get: list(get()),
        include_zones=True,
        include_bounds=True,
    )
    assert [(n.x, n.y, n.on_curve, n.selected) for n in snapshot.contours[0].nodes] == [
        (11, -3, True, True),
        (13, -1, False, False),
    ]
    assert len(snapshot.contours) == 1
    assert snapshot.contours[0].closed is False
    assert snapshot.contours[0].nodes[0].smooth is True
    assert (snapshot.anchors[0].name, snapshot.anchors[0].x) == ("top", 5)
    assert (
        snapshot.advance,
        snapshot.metrics.cap_height,
        snapshot.metrics.italic_slant,
        snapshot.metrics.upm,
    ) == (600, 700, 12, 1000)
    assert [(z.name, z.position, z.edge) for z in snapshot.metrics.zones] == [
        ("cap", 700, 712),
        ("baseline", 0, -15),
    ]
    assert snapshot.bounds == (10, -20, 130, 480)
    assert (
        capture(
            NativeSource(package, layer), fontlab=fontlab, items=lambda get: list(get())
        ).bounds
        is None
    )
    package.upm = 2048
    package.italicAngle_value = 12
    opposite = capture(
        NativeSource(package, layer), fontlab=fontlab, items=lambda get: list(get())
    )
    assert (opposite.metrics.upm, opposite.metrics.italic_slant) == (2048, -12)
    with pytest.raises(FrozenInstanceError):
        snapshot.advance = 10
    assert (snapshot.identity, snapshot.view) == (None, None), "no glyph, no identity"


def identity_source(glyph):
    """A one-contour-free layer whose package resolves glyph ``A``."""
    package = NS(
        fgId=3,
        master="Regular",
        masters=["Regular"],
        italicAngle_value=0,
        upm=1000,
        fgPackage={"A": NS(unicodes=[0x41])},
        packageLib={"public.skipExportGlyphs": []},
    )
    layer = NS(name="Regular", shapes=[], anchors=[], advanceWidth=500)
    return NativeSource(package, layer, glyph)


def identity_glyph(**attrs):
    """A glyph ``A`` with the cache-key fields (id, lastModified) set."""
    values = dict(id=11, lastModified=NS(toMSecsSinceEpoch=lambda: 100))
    values.update(name="A", mark=1, tags=[])
    values.update(attrs)
    return NS(**values)


FONTLAB = NS(
    FontMetrics=lambda package, master: NS(
        ascender=800, descender=-200, xHeight=500, capsHeight=700
    )
)


def test_capture_when_source_has_glyph_then_identity_is_read():
    glyph = identity_glyph(mark=241, tags=["keep"])
    reported = []
    snapshot = capture(
        identity_source(glyph),
        fontlab=FONTLAB,
        items=lambda get: list(get()),
        report=reported.append,
    )
    assert snapshot.identity == Identity("A", (0x41,), 241, (77, 77, 255), True)
    assert reported == []


def test_capture_when_identity_read_fails_then_reports_and_keeps_base():
    glyph = identity_glyph()
    del glyph.tags  # a missing native attribute
    reported = []
    snapshot = capture(
        identity_source(glyph),
        fontlab=FONTLAB,
        items=lambda get: list(get()),
        report=reported.append,
    )
    assert snapshot.identity is None
    assert (snapshot.advance, snapshot.metrics.upm) == (500, 1000), "base kept"
    assert len(reported) == 1 and isinstance(reported[0], AttributeError)
    with pytest.raises(AttributeError):
        capture(identity_source(glyph), fontlab=FONTLAB, items=lambda g: list(g()))


def counting_reads(monkeypatch):
    """Count identity reads behind the snapshot cache."""
    reads = []
    real = snapshot_module.read_identity

    def read(package, glyph):
        reads.append(glyph.name)
        return real(package, glyph)

    monkeypatch.setattr(snapshot_module, "read_identity", read)
    return reads


def capture_identity(source, reported):
    return capture(
        source, fontlab=FONTLAB, items=lambda get: list(get()), report=reported.append
    ).identity


def test_identity_cache_when_same_revision_then_read_once(monkeypatch):
    reads, reported = counting_reads(monkeypatch), []
    glyph = identity_glyph()
    first = capture_identity(identity_source(glyph), reported)
    second = capture_identity(identity_source(glyph), reported)
    assert first == second and first.name == "A"
    assert reads == ["A"], "one read per (font, glyph, revision, layer)"


def test_identity_cache_when_last_modified_changes_then_reads_again(monkeypatch):
    reads, reported = counting_reads(monkeypatch), []
    glyph = identity_glyph(mark=1)
    assert capture_identity(identity_source(glyph), reported).mark == 1
    glyph.mark = 121
    glyph.lastModified = NS(toMSecsSinceEpoch=lambda: 101)
    assert capture_identity(identity_source(glyph), reported).mark == 121
    source = identity_source(glyph)
    source.layer.name = "Alt"
    capture_identity(source, reported)
    assert len(reads) == 3, "a new revision or layer name is a new key"
    assert reported == []


def test_identity_cache_when_read_fails_then_reports_once_per_key(monkeypatch):
    reads, reported = counting_reads(monkeypatch), []
    glyph = identity_glyph()
    del glyph.tags
    for _ in range(3):
        assert capture_identity(identity_source(glyph), reported) is None
    assert len(reads) == 1, "a cached failure is not re-read"
    assert len(reported) == 1 and isinstance(reported[0], AttributeError)
    with pytest.raises(AttributeError):
        capture(identity_source(glyph), fontlab=FONTLAB, items=lambda g: list(g()))


def test_identity_cache_when_full_then_evicts_least_recent(monkeypatch):
    reads, reported = counting_reads(monkeypatch), []
    monkeypatch.setattr(snapshot_module, "_CACHE_LIMIT", 2)
    glyphs = [identity_glyph(id=n) for n in (1, 2, 3)]
    for glyph in glyphs:
        capture_identity(identity_source(glyph), reported)
    assert len(snapshot_module._cache) == 2, "the cache stays bounded"
    capture_identity(identity_source(glyphs[2]), reported)
    assert len(reads) == 3, "recent keys stay cached"
    capture_identity(identity_source(glyphs[0]), reported)
    assert len(reads) == 4, "the oldest key was evicted"


def test_resolve_source_when_symbol_null_or_missing_then_uses_master():
    package = NS(master="Regular")
    asked = []
    layer = NS(isNull=False)
    glyph = NS(
        isNull=False,
        package=package,
        findLayer=lambda name: asked.append(name) or layer,
    )
    assert resolve_source(NS(glyph=glyph, symbol=None)).layer is layer
    assert resolve_source(NS(glyph=glyph)).layer is layer
    assert resolve_source(NS(glyph=glyph, symbol=NS())).layer is layer
    assert asked == ["Regular"] * 3


def test_snapshot_view_fields_default_for_existing_positional_records():
    snapshot = GlyphSnapshot((), (), 0, Metrics(0, 0, 0, 0, 0, 1000))
    assert (snapshot.identity, snapshot.view) == (None, None)
    view = ViewState(2.5)
    assert (view.px_per_unit, view.mouse, view.neighbours) == (2.5, None, None)
    assert Neighbours() == Neighbours(None, None)


def test_palette_active_glyph_and_selection_key_follow_current_master():
    node = NS(selected=False)
    contour = NS(nodes=lambda: [node])
    shape = NS(isComponent=False, contours=[contour])
    layer = NS(isNull=False, shapes=[shape])
    glyph = NS(
        id=7,
        isNull=False,
        package=NS(id=42, fgId=2),
        lastModified=NS(toMSecsSinceEpoch=lambda: 42),
        findLayer=lambda master: layer,
    )
    package = NS(id=99, fgId=2, master="Regular", isNull=False)
    info = NS(isActive=True, glyph=glyph, symbol=NS(layerName=""))
    block = NS(glyphsCount=lambda: 1, getGlyphAt=lambda index: info)
    canvas = NS(isNull=False, textBlocks=lambda: [block])
    workspace = NS(
        currentPackage=package,
        activeFontPanel=None,
        getActiveCanvas=lambda: canvas,
    )
    fontlab = NS(
        flWorkspace=NS(instance=lambda: workspace),
        CurrentGlyph=lambda: (_ for _ in ()).throw(
            AssertionError("legacy glyph API used")
        ),
    )
    active = active_glyph(fontlab, items=lambda get: list(get()))
    assert active == ActiveGlyph(package, glyph, layer)
    first = palette_key(active, items=lambda get: list(get()))
    assert first[0] == 2
    assert first[3] == 42
    package.id = 12345
    assert palette_key(active, items=lambda get: list(get())) == first
    node.selected = True
    assert palette_key(active, items=lambda get: list(get())) != first
    package.master = "Bold"
    assert palette_key(active, items=lambda get: list(get()))[2] == "Bold"
    assert palette_key(None) is None
    info.symbol.layerName = "Alt"
    named = active_glyph(fontlab, items=lambda get: list(get()))
    assert named is not None
    package.isNull = True
    assert active_glyph(fontlab) is None
    package.isNull = False
    workspace.activeFontPanel = object()
    assert active_glyph(fontlab) is None
    workspace.activeFontPanel = None
    workspace.getActiveCanvas = lambda: None
    assert active_glyph(fontlab) is None
    workspace.getActiveCanvas = lambda: canvas
    info.isActive = False
    assert active_glyph(fontlab, items=lambda get: list(get())) is None
    info.isActive = True
    glyph.package.id = 3
    assert active_glyph(fontlab, items=lambda get: list(get())) is not None
    glyph.package.fgId = 3
    assert active_glyph(fontlab, items=lambda get: list(get())) is None
    glyph.package.fgId = 2
    glyph.findLayer = lambda master: NS(isNull=True)
    assert active_glyph(fontlab, items=lambda get: list(get())) is None


# G003 Task 2: components, background and masters ------------------------------


class Affine:
    """A QTransform-like translation with getters, map and isAffine."""

    def __init__(self, dx=0, dy=0):
        self._dx, self._dy = dx, dy

    def isAffine(self):
        return True

    def map(self, point):
        return Point(point.x() + self._dx, point.y() + self._dy)

    def m11(self):
        return 1

    def m12(self):
        return 0

    def m21(self):
        return 0

    def m22(self):
        return 1

    def dx(self):
        return self._dx

    def dy(self):
        return self._dy


def shape(*xs):
    """One plain contour of on-curve nodes at (x, 0)."""
    nodes = [NS(position=Point(x, 0), isOn=lambda: True, selected=False) for x in xs]
    return NS(isComponent=False, contours=[NS(nodes=lambda: nodes)], transform=Affine())


def optional_source(reads):
    """Glyph ``A``: a component of ``B`` at dx=100, a mask and two masters."""
    mask = NS(
        isNull=False, isValid=True, autoLayer=False, glyph=NS(id=11), shapes=[shape(4)]
    )
    shown = NS(
        isNull=False,
        name="Regular",
        isMaskLayer=False,
        getMaskLayer=lambda create: reads.append(("mask", create)) or mask,
        shapes=[
            shape(1, 2),
            NS(
                isComponent=True,
                shapeData=NS(componentGlyph="B", componentLayer=""),
                transform=Affine(dx=100),
            ),
        ],
        anchors=[],
        advanceWidth=500,
    )
    bold = NS(isNull=False, shapes=[shape(1, 3)], anchors=[], advanceWidth=600)
    base = NS(
        isNull=False,
        name="B",
        lastModified=NS(toMSecsSinceEpoch=lambda: 1),
        findLayer=lambda name: NS(isNull=False, shapes=[shape(7)]),
    )
    layers = {"Regular": shown, "Bold": bold}
    glyph = identity_glyph(findLayer=lambda name: layers.get(name))
    source = identity_source(glyph)
    source.package.masters = ["Regular", "Bold"]
    source.package.findName = lambda name: (
        reads.append(("base", name)) or (base if name == "B" else None)
    )
    return NativeSource(source.package, shown, glyph), base


def capture_optional(source, reported, **flags):
    return capture(
        source,
        fontlab=FONTLAB,
        items=lambda get: list(get()),
        report=reported.append,
        **flags,
    )


ALL = dict(include_components=True, include_background=True, include_masters=True)


def test_capture_when_flags_set_then_components_background_and_masters_are_read():
    reads, reported = [], []
    source, _ = optional_source(reads)
    shot = capture_optional(source, reported, **ALL)
    assert reported == []
    (part,) = shot.components
    assert isinstance(part, Component)
    assert (part.base, part.transform) == ("B", (1.0, 0.0, 0.0, 1.0, 100.0, 0.0))
    assert [n.x for n in part.contours[0].nodes] == [107]
    assert [n.x for n in shot.background[0].nodes] == [4]
    assert ("mask", False) in reads and ("mask", True) not in reads
    assert [(m.name, m.advance, m.compatible) for m in shot.masters] == [
        ("Regular", 500.0, True),
        ("Bold", 600.0, True),
    ]
    assert isinstance(shot.masters[0], MasterOutline)
    assert [n.x for n in shot.masters[1].contours[0].nodes] == [1, 3]


def test_capture_when_flags_unset_then_optional_data_is_not_read():
    reads, reported = [], []
    source, _ = optional_source(reads)
    shot = capture_optional(source, reported)
    assert (shot.components, shot.background, shot.masters) == ((), None, ())
    assert reads == [], "no findName or getMaskLayer without a flag"
    positional = GlyphSnapshot((), (), 0, Metrics(0, 0, 0, 0, 0, 1000))
    assert (positional.components, positional.background, positional.masters) == (
        (),
        None,
        (),
    )
    no_glyph = NativeSource(source.package, source.layer)
    assert capture_optional(no_glyph, reported, **ALL).components == ()
    assert reads == [] and reported == []


def test_optional_cache_when_same_revision_then_each_datum_read_once():
    reads, reported = [], []
    source, _ = optional_source(reads)
    first = capture_optional(source, reported, **ALL)
    second = capture_optional(source, reported, **ALL)
    assert first == second
    assert reads.count(("mask", False)) == 2, "background is read on every paint"
    # One read resolves B; each later hit re-checks only B's stamp.
    assert reads.count(("base", "B")) == 2
    assert reported == []


def test_cache_when_revision_changes_then_entry_is_replaced_not_added():
    reads, reported = [], []
    source, _ = optional_source(reads)
    capture_optional(source, reported, **ALL)
    kinds = sorted(key[0] for key in snapshot_module._cache)
    assert kinds == ["components", "identity", "masters"], "background is uncached"
    for stamp in (101, 102, 103):
        source.glyph.lastModified = NS(toMSecsSinceEpoch=lambda stamp=stamp: stamp)
        capture_optional(source, reported, **ALL)
    assert len(snapshot_module._cache) == 3, "one entry per datum and glyph"
    assert {value[0] for value in snapshot_module._cache.values()} == {103}
    assert reads.count(("base", "B")) == 4, "each revision re-reads once"


def test_background_when_foreign_mask_then_none_and_reported_once():
    reads, reported = [], []
    source, _ = optional_source(reads)
    mask = source.layer.getMaskLayer(False)
    mask.glyph = NS(id=99)
    for _ in range(3):
        assert (
            capture_optional(source, reported, include_background=True).background
            is None
        )
    assert len(reported) == 1 and isinstance(reported[0], ValueError)


def test_components_when_stamp_check_keeps_failing_then_reported_once_and_kept():
    reads, reported = [], []
    source, _ = optional_source(reads)
    source.layer.shapes.append(
        NS(
            isComponent=True,
            shapeData=NS(componentGlyph="gone", componentLayer=""),
            transform=Affine(),
        )
    )
    first = capture_optional(source, reported, include_components=True).components
    assert len(reported) == 1 and "'gone'" in str(reported[0])

    def broken(name):
        raise RuntimeError("stale package")

    source.package.findName = broken
    for _ in range(3):
        shot = capture_optional(source, reported, include_components=True)
        assert shot.components == first, "an unverifiable entry is kept"
    assert len(reported) == 2, "the skip is not re-reported; the failure once"
    assert isinstance(reported[1], RuntimeError)


def test_masters_and_background_when_nodes_selected_then_unselected():
    reads, reported = [], []
    source, _ = optional_source(reads)
    selected = NS(position=Point(1, 0), isOn=lambda: True, selected=True)
    pick = NS(
        isComponent=False, contours=[NS(nodes=lambda: [selected])], transform=Affine()
    )
    source.glyph.findLayer("Bold").shapes = [pick]
    source.layer.getMaskLayer(False).shapes = [pick]
    shot = capture_optional(source, reported, **ALL)
    assert shot.masters[1].contours[0].nodes[0].selected is False
    assert shot.background[0].nodes[0].selected is False


def test_optional_cache_when_base_glyph_changes_then_components_reread():
    reads, reported = [], []
    source, base = optional_source(reads)
    capture_optional(source, reported, include_components=True)
    base.lastModified = NS(toMSecsSinceEpoch=lambda: 2)
    base.findLayer = lambda name: NS(isNull=False, shapes=[shape(8)])
    shot = capture_optional(source, reported, include_components=True)
    assert [n.x for n in shot.components[0].contours[0].nodes] == [108]


def test_capture_when_slot_shows_other_master_then_its_metrics_and_no_zones():
    reads, asked = [], []
    source, _ = optional_source(reads)
    source.package.ps_zonesT = [NS(name="x", position=500, width=10)]
    source.package.ps_zonesB = []
    heights = {"Regular": 500, "Bold": 520}
    fontlab = NS(
        FontMetrics=lambda package, master: (
            asked.append(master)
            or NS(ascender=800, descender=-200, xHeight=heights[master], capsHeight=700)
        )
    )
    bold = source.glyph.findLayer("Bold")
    bold.name = "Bold"
    shot = capture(
        NativeSource(source.package, bold, source.glyph),
        fontlab=fontlab,
        items=lambda get: list(get()),
        include_zones=True,
    )
    assert asked == ["Bold"], "metrics come from the master that owns the layer"
    assert shot.metrics.x_height == 520
    assert shot.metrics.zones == (), "another master's zones are not read"
    shot = capture(
        source, fontlab=fontlab, items=lambda get: list(get()), include_zones=True
    )
    assert (shot.metrics.x_height, len(shot.metrics.zones)) == (500, 1)


def test_capture_when_owner_master_read_fails_then_current_master_and_one_report(
    monkeypatch,
):
    reads, asked, reported = [], [], []
    source, _ = optional_source(reads)
    fontlab = NS(
        FontMetrics=lambda package, master: (
            asked.append(master)
            or NS(ascender=800, descender=-200, xHeight=500, capsHeight=700)
        )
    )

    def broken(*_):
        raise RuntimeError("masters gone")

    monkeypatch.setattr("fontlabapp.components.decompose.owner_master", broken)
    for _ in range(2):
        shot = capture(
            source,
            fontlab=fontlab,
            items=lambda get: list(get()),
            report=reported.append,
        )
    assert shot.metrics.x_height == 500, "the base snapshot still paints"
    assert asked == [str(source.package.master)] * 2
    assert [str(e) for e in reported] == ["masters gone"], "reported once"


def test_components_when_mask_shown_and_current_master_changes_then_reread():
    reads, reported = [], []
    source, base = optional_source(reads)
    outlines = {"Regular": 7, "Bold": 8}
    base.findLayer = lambda name: NS(isNull=False, shapes=[shape(outlines[name])])
    source.layer.name = "mask.Regular"
    shot = capture_optional(source, reported, include_components=True)
    assert [n.x for n in shot.components[0].contours[0].nodes] == [107]
    source.package.master = "Bold"
    shot = capture_optional(source, reported, include_components=True)
    assert [n.x for n in shot.components[0].contours[0].nodes] == [108], (
        "the owner master is part of the components cache key"
    )
    assert reported == []


def test_optional_cache_when_read_fails_then_default_and_reported_once():
    reads, reported = [], []
    source, _ = optional_source(reads)
    del source.layer.isMaskLayer  # a missing native attribute
    del source.glyph.findLayer("Bold").advanceWidth  # an unreadable master
    for _ in range(3):
        shot = capture_optional(source, reported, **ALL)
        assert (shot.background, shot.masters) == (None, ())
        assert shot.components != (), "one failed datum never blocks another"
    assert len(reported) == 2, "each failed datum is reported once per key"
    with pytest.raises(AttributeError):
        capture(
            source,
            fontlab=FONTLAB,
            items=lambda get: list(get()),
            include_background=True,
        )


def test_optional_cache_when_missing_base_then_reported_once_per_key():
    reads, reported = [], []
    source, _ = optional_source(reads)
    source.layer.shapes[1].shapeData.componentGlyph = "gone"
    for _ in range(3):
        shot = capture_optional(source, reported, include_components=True)
        assert shot.components == ()
    assert len(reported) == 1 and "'gone'" in str(reported[0])


def with_kerning(source, classes):
    """Give the package ``kerning(master).groups.items()`` and log the master."""
    asked = []
    source.package.kerning = lambda master: (
        asked.append(master) or NS(groups=NS(items=lambda: list(classes.items())))
    )
    return asked


def test_kerning_groups_when_flag_set_then_read_for_owner_master():
    reads, reported = [], []
    source, _ = optional_source(reads)
    asked = with_kerning(
        source, {"L": (["A", "B"], "KernLeft"), "R": (["A"], "KernBothSide")}
    )
    shot = capture_optional(source, reported, include_kerning=True)
    assert shot.kerning_groups == KerningGroups(
        "L", "R", {"L": ("A", "B"), "R": ("A",)}
    )
    assert asked == ["Regular"] and reported == []
    assert capture_optional(source, reported).kerning_groups is None, "opt-in only"
    assert asked == ["Regular"]
    source.layer.name = "Bold"
    capture_optional(source, reported, include_kerning=True)
    assert asked[-1] == "Bold", "a slot showing another master reads that master"
    source.layer.name = "mask.Bold"
    capture_optional(source, reported, include_kerning=True)
    assert asked[-1] == "Regular", "a non-master layer reads the current master"


def test_kerning_groups_when_group_edit_keeps_last_modified_then_next_paint_sees_it():
    reads, reported = [], []
    source, _ = optional_source(reads)
    classes = {"L": (["A"], "KernLeft")}
    with_kerning(source, classes)
    first = capture_optional(source, reported, include_kerning=True)
    classes["L2"] = classes.pop("L")  # a class rename moves no glyph stamp
    second = capture_optional(source, reported, include_kerning=True)
    assert (first.kerning_groups.left, second.kerning_groups.left) == ("L", "L2")
    assert not [key for key in snapshot_module._cache if key[0] == "kerning"]


def test_kerning_groups_when_read_fails_then_none_reported_once_and_base_kept():
    reads, reported = [], []
    source, _ = optional_source(reads)

    def broken(master):
        raise RuntimeError("no kerning")

    source.package.kerning = broken
    for _ in range(3):
        shot = capture_optional(source, reported, include_kerning=True)
        assert shot.kerning_groups is None and shot.identity is not None
    assert [str(e) for e in reported] == ["no kerning"]


def other_glyph(name, gid, stamp, layers, reads):
    """A requested glyph whose findLayer logs the asked layer name."""
    return NS(
        isNull=False,
        id=gid,
        name=name,
        lastModified=NS(toMSecsSinceEpoch=lambda: stamp),
        findLayer=lambda layer: reads.append((name, layer)) or layers.get(layer),
    )


def with_others(source, reads):
    """Glyph ``B`` with Regular and Bold layers, glyph ``C`` with none."""
    picked = NS(position=Point(3, 0), isOn=lambda: True, selected=True)
    bold = NS(
        isNull=False,
        name="Bold",
        shapes=[
            NS(
                isComponent=False,
                contours=[NS(nodes=lambda: [picked])],
                transform=Affine(),
            ),
            NS(isComponent=True),
        ],
    )
    regular = NS(isNull=False, name="Regular", shapes=[shape(5)])
    glyphs = {
        "B": other_glyph("B", 21, 1, {"Regular": regular, "Bold": bold}, reads),
        "C": other_glyph("C", 22, 1, {}, reads),
    }
    source.package.findName = lambda name: glyphs.get(name)
    return glyphs


def test_others_when_requested_then_own_unselected_contours_from_owner_master():
    reads, reported = [], []
    source, _ = optional_source(reads)
    with_others(source, reads)
    seen = []
    shot = capture_optional(
        source,
        reported,
        requested=lambda identity, groups=None: seen.append(identity) or ("B",),
    )
    assert seen == [shot.identity]
    assert [n.x for n in shot.others["B"][0].nodes] == [5]
    source.layer.name = "Bold"
    shot = capture_optional(
        source, reported, requested=lambda identity, groups=None: ("B", "C", "Z")
    )
    assert list(shot.others) == ["B"], "missing glyphs or layers are simply absent"
    (contour,) = shot.others["B"]
    assert [(n.x, n.selected) for n in contour.nodes] == [(3, False)]
    assert reported == []
    with pytest.raises(TypeError):
        shot.others["X"] = ()


def test_others_cache_when_other_glyph_revision_changes_then_reread_only_it():
    reads, reported = [], []
    source, _ = optional_source(reads)
    glyphs = with_others(source, reads)

    def ask(identity, groups=None):
        return ("B",)

    for _ in range(2):
        capture_optional(source, reported, requested=ask)
    keys = [key for key in snapshot_module._cache if key[0] == "others"]
    assert keys == [("others", 3, 21, "Regular", None)], "keyed on the other glyph"
    glyphs["B"].findLayer("Regular").shapes = [shape(9)]
    shot = capture_optional(source, reported, requested=ask)
    assert [n.x for n in shot.others["B"][0].nodes] == [5], "same revision: cached"
    glyphs["B"].lastModified = NS(toMSecsSinceEpoch=lambda: 2)
    shot = capture_optional(source, reported, requested=ask)
    assert [n.x for n in shot.others["B"][0].nodes] == [9]


def test_others_when_lookup_fails_then_that_name_absent_and_reported_once():
    reads, reported = [], []
    source, _ = optional_source(reads)

    def broken(name):
        raise RuntimeError("stale")

    source.package.findName = broken
    for _ in range(2):
        shot = capture_optional(
            source, reported, requested=lambda identity, groups=None: ("B",)
        )
        assert dict(shot.others) == {}
    assert [str(e) for e in reported] == ["stale"]


def test_others_when_identity_missing_then_requested_is_not_asked():
    reads, reported = [], []
    source, _ = optional_source(reads)
    del source.glyph.mark  # the identity read fails
    asked = []
    shot = capture_optional(
        source, reported, requested=lambda identity, groups=None: asked.append(identity)
    )
    assert (shot.identity, dict(shot.others), asked) == (None, {}, [])


def test_snapshot_task3_fields_default_for_existing_positional_records():
    shot = GlyphSnapshot((), (), 0, Metrics(0, 0, 0, 0, 0, 1000))
    assert (shot.kerning_groups, dict(shot.others)) == (None, {})


def test_snapshot_when_task3_mappings_set_then_still_hashable_and_equal_hash():
    def shot():
        groups = KerningGroups("L", None, MappingProxyType({"L": ("A",)}))
        return GlyphSnapshot(
            (),
            (),
            0,
            Metrics(0, 0, 0, 0, 0, 1000),
            kerning_groups=groups,
            others=MappingProxyType({"B": ()}),
        )

    plain = GlyphSnapshot((), (), 0, Metrics(0, 0, 0, 0, 0, 1000))
    assert hash(plain) == hash(GlyphSnapshot((), (), 0, Metrics(0, 0, 0, 0, 0, 1000)))
    assert shot() == shot() and hash(shot()) == hash(shot()), (
        "pure compute may be memoised on snapshots"
    )


def test_requested_when_kerning_read_then_called_with_groups_else_identity_only():
    reads, reported, calls = [], [], []
    source, _ = optional_source(reads)
    with_kerning(source, {"L": (["A", "B"], "KernLeft")})

    def ask(identity, groups=None):
        calls.append(groups)
        return ()

    capture_optional(source, reported, include_kerning=True, requested=ask)
    capture_optional(source, reported, requested=ask)
    assert calls[0] == KerningGroups("L", None, {"L": ("A", "B")}), "groups reach it"
    assert calls[1] is None, "no needs_kerning, no groups"
    assert reported == []


def test_source_key_when_same_content_distinct_targets_then_excluded_from_equality_and_hash():
    from dataclasses import replace

    shot = GlyphSnapshot((), (), 500, Metrics(800, -200, 500, 700, 0, 1000))
    keyed = replace(shot, source_key=(1, 2, 3, "Regular"))
    other = replace(shot, source_key=(4, 5, 6, "Bold"))
    assert keyed == other == shot and hash(keyed) == hash(other) == hash(shot)
    assert keyed.source_key != other.source_key


def test_capture_when_source_has_ids_then_key_uses_actual_owner_not_selected_master():
    source, _ = optional_source([])
    source.layer.id = 33
    normal = capture_optional(source, [], include_components=True)
    assert normal.source_key == (
        int(source.package.fgId),
        int(source.glyph.id),
        33,
        "Regular",
    )
    bold = source.glyph.findLayer("Bold")
    bold.id = 44
    bold.name = "Bold"
    shot = capture_optional(NativeSource(source.package, bold, source.glyph), [])
    assert source.package.master == "Regular" and shot.source_key[-1] == "Bold"
    assert shot.source_key != normal.source_key
    source.package.fgId += 10
    assert capture_optional(source, []).source_key != normal.source_key
    source.glyph.id += 10
    assert capture_optional(source, []).source_key != normal.source_key


def test_capture_when_key_ids_missing_or_owner_unknown_then_key_is_none(monkeypatch):
    source, _ = optional_source([])
    assert capture_optional(source, []).source_key is None
    source.layer.id = 33

    def broken(*args):
        raise RuntimeError("owner unavailable")

    monkeypatch.setattr(snapshot_module.decompose, "owner_master", broken)
    reports = []
    assert capture_optional(source, reports).source_key is None
    assert len(reports) == 1 and "owner unavailable" in str(reports[0])


def test_capture_when_key_id_malformed_then_reports_or_raises_without_guess():
    source, _ = optional_source([])
    source.layer.id = "invalid"
    reports = []
    assert capture_optional(source, reports).source_key is None
    assert len(reports) == 1 and isinstance(reports[0], ValueError)
    with pytest.raises(ValueError):
        capture(source, fontlab=FONTLAB, items=lambda get: list(get()))


@pytest.mark.parametrize("needs_components", [False, True])
def test_tool_bridge_when_opted_in_then_event_and_real_painter_capture_same_key_and_components(
    monkeypatch, needs_components
):
    from fontlabapp.plugins.tool import Tool
    from fontlabapp.plugins.tools.bridge import ToolBridge

    source, base = optional_source([])
    source.layer.id = 33
    active = ActiveGlyph(source.package, source.glyph, source.layer)
    monkeypatch.setattr(snapshot_module, "active_glyph", lambda fontlab: active)
    original_import = snapshot_module.import_module
    monkeypatch.setattr(
        snapshot_module,
        "import_module",
        lambda name: FONTLAB
        if name == "fontlab"
        else NS(qt_list=lambda get: list(get()))
        if name == "fontlabapp.qt.safe"
        else original_import(name),
    )
    seen = []

    class Inspect(Tool):
        def marks(self, glyph):
            seen.append(glyph)
            return []

    tool = Inspect()
    tool.needs_components = needs_components
    bridge = ToolBridge(tool, NS(fontlab=FONTLAB))
    event = bridge.context.snapshot()
    reports = []
    bridge.painter.paint(
        NS(layer=source), NS(), lambda error, plugin: reports.append(error)
    )
    assert reports == [] and len(seen) == 1
    painted = seen[0]
    assert (
        event.source_key
        == painted.source_key
        == (int(source.package.fgId), int(source.glyph.id), 33, "Regular")
    )
    assert bool(event.components) == bool(painted.components) == needs_components
    if needs_components:
        assert event.components[0].transform[-2:] == (100.0, 0.0)
        base.lastModified = NS(toMSecsSinceEpoch=lambda: 2)
        base.findLayer = lambda name: NS(isNull=False, shapes=[shape(8)])
        bridge.painter.paint(
            NS(layer=source), NS(), lambda error, plugin: reports.append(error)
        )
        assert seen[-1].components[0].contours[0].nodes[0].x == 108
