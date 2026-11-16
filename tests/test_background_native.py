# this_file: tests/test_background_native.py
"""Complete three-action native-shaped transport without a native host."""

from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
import test_angularizzle_native as f
from fontlabapp.masters.background.native import Backend
from fontlabapp.masters.background.model import Transform


class CopyShape(f.Shape):
    def assignStyle(self, other):
        for key in (
            "active",
            "selected",
            "opacity",
            "excluded",
            "contentLocked",
            "pen",
            "brush",
        ):
            setattr(self, key, deepcopy(getattr(other, key)))

    def addContour(self, contour, check_duplicate=False, validate=True):
        self.contours.append(contour)


CONSTRUCTORS = NS(flShape=CopyShape, flNode=f.Node, flContour=f.Contour)


def owned():
    glyphs = []
    events = []

    class Layer(f.Layer):
        def __init__(self, name, shapes=()):
            super().__init__(name, shapes)
            self.isLocked = False
            self.isVisible = True
            self.isService = name.startswith("mask")
            self.isWireframe = self.isService
            self.isMaskLayer = self.isService
            self.isNull = False
            self.isValid = True

        def getMaskLayer(self, create):
            existing = self.glyph.findLayer("mask." + self.name)
            if existing is None and create:
                existing = Layer("mask." + self.name)
                existing.glyph = self.glyph
                self.glyph.layers.insert(0, existing)
                self.isVisible = False
            return existing

        def clearAnchors(self):
            self.anchors = []

        def addAnchor(self, a):
            self.anchors.append(a)

        def removeGuides(self, h, v):
            self.guidelines = []

        def appendGuidelines(self, items):
            self.guidelines.extend(items)

    class Glyph(f.Glyph):
        def __init__(self, name, layers):
            super().__init__(name, layers)
            self.activeLayer = layers[-1]
            for layer in layers:
                layer.glyph = self

        def removeLayer(self, layer):
            self.layers.remove(layer)

    for name in ["a", "b"]:
        front = Layer("Regular", [f.Shape([f.square()])])
        background = Layer(
            "mask.Regular", [f.Shape([f.square(10)]), f.Shape(component=True)]
        )
        glyphs.append(Glyph(name, [background, front]))
    package = NS(
        id=10,
        fgId=20,
        master="Regular",
        masters=["Regular"],
        findName=lambda name: next((g for g in glyphs if g.name == name), None),
    )
    for glyph in glyphs:
        for layer in glyph.layers:
            layer.glyph.package = package
    selection = NS(
        context=(10, "Regular", "editor", 1),
        occurrences=(
            NS(
                package=package,
                glyph=glyphs[0],
                layer=glyphs[0].findLayer("Regular"),
                block_id=1,
                index=0,
            ),
        ),
    )
    font = NS(id=20, glyphs=[NS(name=g.name) for g in glyphs])
    window = NS(updatesEnabled=True)
    window.setUpdatesEnabled = lambda value: (
        events.append(("updates", value)),
        setattr(window, "updatesEnabled", value),
    )
    workspace = NS(currentPackage=package, packages=lambda: [package])
    native = NS(
        flShape=CopyShape,
        flNode=f.Node,
        flContour=f.Contour,
        CurrentFont=lambda: font,
        MainWindow=lambda: window,
        flPackage=lambda p: p,
        flWorkspace=NS(instance=lambda: workspace),
        flItems=lambda: NS(
            notifyChangesApplied=lambda *args: events.append(("notify", args))
        ),
    )
    qt = NS(
        QtCore=NS(QPointF=f.Point, QDateTime=NS(currentDateTimeUtc=lambda: "new date")),
        QtGui=NS(QTransform=lambda *m: f.Transform(m[6], m[7], m[0])),
    )
    backend = Backend(
        provider=lambda deadline: selection,
        first_provider=lambda deadline: selection,
        native=lambda name: native if name == "fontlab" else qt,
    )
    return NS(
        glyphs=glyphs,
        package=package,
        selection=selection,
        font=font,
        events=events,
        window=window,
        native=native,
        qt=qt,
        backend=backend,
        Layer=Layer,
    )


def test_scale_path_nodes_only_and_preserve_mask_metadata_component_identity():
    h = owned()
    mask = h.glyphs[0].findLayer("mask.Regular")
    component = mask.shapes[1]
    mask.lib = {"private": [1, 2]}
    mask.shapes[0].contours[0].nodes()[0].nodeState |= 0x3008
    before = deepcopy(mask.shapes[0].contours[0].nodes()[0].position)
    result = h.backend.apply(h.backend.capture("scale"), Transform("scale", 50))
    assert result["changed"] == 1 and mask.shapes[1] is component
    assert mask.shapes[0].contours[0].nodes()[0].position.x() == before.x() / 2
    assert mask.lib == {"private": [1, 2]} and mask.shapes[0].shapeData.note == "note"
    assert (
        h.window.updatesEnabled and len([e for e in h.events if e[0] == "notify"]) == 1
    )


def test_shift_moves_components_and_nodes_but_never_foreground():
    h = owned()
    front = h.glyphs[0].findLayer("Regular")
    mask = h.glyphs[0].findLayer("mask.Regular")
    original = front.shapes[0]
    h.backend.apply(h.backend.capture("shift"), Transform("shift", -40))
    assert mask.shapes[0].contours[0].nodes()[0].position.x() == -30
    assert mask.shapes[1].transform.m31() == -40 and front.shapes[0] is original


def test_replacement_uses_first_paths_and_every_glyph_preserving_mask_metadata():
    h = owned()
    source = h.selection.occurrences[0].layer
    for node in source.shapes[0].contours[0].nodes():
        node.selected = True
        node.nodeState |= 0x20
    masks = [g.findLayer("mask.Regular") for g in h.glyphs]
    for m in masks:
        m.lib = {"custom": m.id}
        m.anchors = [NS(id=13)]
        m.guidelines = [NS(id=14, isHint=False)]
    result = h.backend.apply(h.backend.capture("replace"), None)
    assert result["changed"] == 2
    for mask in masks:
        assert len(mask.shapes) == 1 and not mask.shapes[0].isComponent
        assert mask.shapes[0].contours[0].nodes()[0].position.x() == 0
        assert (
            not mask.anchors and not mask.guidelines and mask.lib == {"custom": mask.id}
        )
    assert masks[0].shapes[0].id != masks[1].shapes[0].id


@pytest.mark.parametrize("mode", ["scale", "shift"])
def test_empty_selection_and_absent_masks_are_successful_noops(mode):
    h = owned()
    h.selection.occurrences = ()
    assert (
        h.backend.apply(
            h.backend.capture(mode), Transform(mode, 100 if mode == "scale" else 0)
        )["changed"]
        == 0
    )
    h = owned()
    h.glyphs[0].layers.remove(h.glyphs[0].findLayer("mask.Regular"))
    assert (
        h.backend.apply(h.backend.capture(mode), Transform(mode, 12))["changed"] == 0
        and not h.events
    )


@pytest.mark.parametrize("mode,value", [("scale", 100), ("shift", 0)])
def test_real_noop_has_no_history_or_notification(mode, value):
    h = owned()
    assert (
        h.backend.apply(h.backend.capture(mode), Transform(mode, value))["changed"] == 0
    )
    assert not h.events and not h.glyphs[0].events


def test_repeated_occurrences_are_not_deduplicated_in_geometry():
    h = owned()
    h.selection.occurrences *= 2
    assert (
        h.backend.apply(h.backend.capture("shift"), Transform("shift", 3))["changed"]
        == 1
    )
    assert (
        h.glyphs[0]
        .findLayer("mask.Regular")
        .shapes[0]
        .contours[0]
        .nodes()[0]
        .position.x()
        == 16
    )


def test_replacement_keeps_first_auxiliary_background_plus_every_selected_master():
    h = owned()
    glyph = h.glyphs[0]
    aux = h.Layer("Regular.aux", [f.Shape([f.square(77)])])
    aux.glyph = glyph
    for n in aux.shapes[0].contours[0].nodes():
        n.selected = True
        n.nodeState |= 0x20
    background = h.Layer("mask.Regular.aux", [f.Shape([f.square(999)])])
    background.glyph = glyph
    glyph.layers.extend([background, aux])
    first = h.selection.occurrences[0]
    h.selection.occurrences = (NS(**(vars(first) | {"layer": aux})), NS())
    assert h.backend.apply(h.backend.capture("replace"), None)["changed"] == 3
    for mask in [background, *[g.findLayer("mask.Regular") for g in h.glyphs]]:
        assert mask.shapes[0].contours[0].nodes()[0].position.x() == 77


def test_replacement_empty_selection_of_paths_clears_every_background():
    h = owned()
    for n in h.selection.occurrences[0].layer.shapes[0].contours[0].nodes():
        n.selected = False
    assert h.backend.apply(h.backend.capture("replace"), None)["changed"] == 2
    assert all(not g.findLayer("mask.Regular").shapes for g in h.glyphs)
    assert h.backend.apply(h.backend.capture("replace"), None)["changed"] == 0


def test_replacement_creates_missing_mask_and_restores_foreground_visibility_activation():
    h = owned()
    g = h.glyphs[0]
    front = g.findLayer("Regular")
    g.layers.remove(g.findLayer("mask.Regular"))
    for n in front.shapes[0].contours[0].nodes():
        n.selected = True
    assert h.backend.apply(h.backend.capture("replace"), None)["changed"] == 2
    assert (
        g.findLayer("mask.Regular").shapes
        and front.isVisible
        and g.activeLayer is front
    )


@pytest.mark.parametrize(
    "problem",
    [
        "missing-font",
        "foreign-font",
        "master",
        "fg-carrier",
        "absent-carrier",
        "missing-glyph",
        "missing-master",
        "mask-selected",
        "foreign-mask",
        "automatic-mask",
        "ps-hints",
        "tt-hints",
        "tt-program",
    ],
)
def test_full_domain_guard_failures_never_publish_a_partial_subset(problem):
    h = owned()
    mask = h.glyphs[0].findLayer("mask.Regular")
    if problem == "missing-font":
        h.native.flWorkspace.instance().currentPackage = None
    elif problem == "foreign-font":
        h.native.flWorkspace.instance().currentPackage = NS(id=99, master="Regular")
    elif problem == "master":
        h.package.master = "Other"
    elif problem == "fg-carrier":
        h.font.id = 999
    elif problem == "absent-carrier":
        h.native.CurrentFont = lambda: None
    elif problem == "missing-glyph":
        h.font.glyphs.append(NS(name="absent"))
    elif problem == "missing-master":
        h.glyphs[1].layers.remove(h.glyphs[1].findLayer("Regular"))
    elif problem == "mask-selected":
        h.selection.occurrences[0].layer.isMaskLayer = True
    elif problem == "foreign-mask":
        mask.glyph = NS(id=999)
    elif problem == "automatic-mask":
        mask.autoLayer = True
    elif problem == "ps-hints":
        mask.guidelines = [NS(id=13, isHint=True)]
    elif problem == "tt-hints":
        mask.ttData = NS(hasHints=lambda: True)
    elif problem == "tt-program":
        mask.tthProgram = ["hint"]
    with pytest.raises(ValueError):
        h.backend.capture("replace")
    assert not h.events


def test_invalid_background_wrapper_is_not_edited_and_mode_poison_guards_work():
    h = owned()
    h.glyphs[0].findLayer("mask.Regular").isValid = False
    assert (
        h.backend.apply(h.backend.capture("scale"), Transform("scale", 50))["changed"]
        == 0
    )
    with pytest.raises(ValueError):
        h.backend.capture("unknown")
    h.selection.occurrences = ()
    with pytest.raises(ValueError):
        h.backend.capture("replace")
    h.backend.poisoned = True
    with pytest.raises(RuntimeError):
        h.backend.capture("scale")
    with pytest.raises(RuntimeError):
        h.backend.apply(None, None)


def test_apply_rechecks_every_destination_and_operation_identity():
    h = owned()
    source = h.backend.capture("shift")
    with pytest.raises(ValueError):
        h.backend.apply(source, None)
    with pytest.raises(ValueError):
        h.backend.apply(source, Transform("scale", 50))
    h.glyphs[0].findLayer("mask.Regular").note = "external edit"
    with pytest.raises(ValueError, match="changed"):
        h.backend.apply(source, Transform("shift", 1))
    assert not h.events


def test_scale_does_not_read_clone_or_notify_any_component_details():
    h = owned()
    mask = h.glyphs[0].findLayer("mask.Regular")

    class Component:
        isComponent = True
        id = 999

        @property
        def shapeData(self):
            raise AssertionError("Scale must not inspect a component")

    component = Component()
    mask.shapes[1] = component
    assert (
        h.backend.apply(h.backend.capture("scale"), Transform("scale", 50))["changed"]
        == 1
    )
    assert mask.shapes[1] is component


@pytest.mark.parametrize("replace", [False, True])
def test_partial_attachment_failure_restores_geometry_and_rich_mask_contents(replace):
    from fontlabapp.masters.background.transaction import BackgroundWriteError

    h = owned()
    mask = h.glyphs[0].findLayer("mask.Regular")
    before = tuple(mask.shapes)
    mask.anchors = [NS(id=23)]
    mask.guidelines = [NS(id=24, isHint=False)]
    if replace:
        for n in h.selection.occurrences[0].layer.shapes[0].contours[0].nodes():
            n.selected = True
    mask.fail_insert = 1
    h.window.updatesEnabled = False
    with pytest.raises(BackgroundWriteError) as error:
        h.backend.apply(
            h.backend.capture("replace" if replace else "shift"),
            None if replace else Transform("shift", 12),
        )
    assert error.value.geometry_recovery_attempted and tuple(mask.shapes) == before
    assert (
        mask.anchors[0].id == 23
        and mask.guidelines[0].id == 24
        and h.window.updatesEnabled is False
    )
    assert h.backend.poisoned


def test_new_mask_creation_then_failure_is_removed_during_recovery():
    from fontlabapp.masters.background.transaction import BackgroundWriteError

    h = owned()
    g = h.glyphs[0]
    front = g.findLayer("Regular")
    g.layers.remove(g.findLayer("mask.Regular"))
    original = front.getMaskLayer

    def get(create):
        result = original(create)
        if create:
            raise RuntimeError("created then failed")
        return result

    front.getMaskLayer = get
    for n in front.shapes[0].contours[0].nodes():
        n.selected = False
    with pytest.raises(BackgroundWriteError):
        h.backend.apply(h.backend.capture("replace"), None)
    assert (
        original(False) is None
        and front.isVisible
        and g.activeLayer is front
        and h.window.updatesEnabled
    )


def test_refused_mask_creation_preserves_foreground_and_exposes_error():
    from fontlabapp.masters.background.transaction import BackgroundWriteError

    h = owned()
    g = h.glyphs[0]
    front = g.findLayer("Regular")
    g.layers.remove(g.findLayer("mask.Regular"))
    front.getMaskLayer = lambda create: None
    for n in front.shapes[0].contours[0].nodes():
        n.selected = False
    with pytest.raises(BackgroundWriteError):
        h.backend.apply(h.backend.capture("replace"), None)
    assert front.isVisible and g.activeLayer is front and h.window.updatesEnabled


def test_cache_and_recovery_failure_are_both_retained():
    from fontlabapp.masters.background.transaction import BackgroundWriteError

    h = owned()
    mask = h.glyphs[0].findLayer("mask.Regular")
    before = tuple(mask.shapes)
    mask.update = lambda: False
    with pytest.raises(BackgroundWriteError) as error:
        h.backend.apply(h.backend.capture("shift"), Transform("shift", 12))
    assert (
        len(error.value.errors) == 2
        and tuple(mask.shapes) == before
        and h.window.updatesEnabled
    )


@pytest.mark.parametrize("fault", ["notify", "stamp", "paint-restore", "paint-block"])
def test_late_failures_never_claim_atomic_success_or_suppress_retained_errors(fault):
    from fontlabapp.masters.background.transaction import BackgroundWriteError

    h = owned()

    def fail(*args):
        raise RuntimeError("owned " + fault + " failure")

    if fault == "notify":
        h.native.flItems = lambda: NS(notifyChangesApplied=fail)
    elif fault == "stamp":
        g = h.glyphs[0]

        class FailedDate(type(g)):
            @property
            def lastModified(self):
                return "old date"

            @lastModified.setter
            def lastModified(self, value):
                fail()

        g.__class__ = FailedDate
    else:
        original = h.window.setUpdatesEnabled

        def paint(value):
            if value == (fault == "paint-restore"):
                fail()
            original(value)

        h.window.setUpdatesEnabled = paint
    with pytest.raises(BackgroundWriteError) as error:
        h.backend.apply(h.backend.capture("shift"), Transform("shift", 3))
    assert error.value.errors and h.backend.poisoned
    if fault != "paint-restore":
        assert h.window.updatesEnabled


def test_component_original_builder_is_retained_before_detachment():
    h = owned()
    mask = h.glyphs[0].findLayer("mask.Regular")
    old = mask.shapes[1]
    builder = object()
    old.shapeData.builder = builder
    h.backend.apply(h.backend.capture("shift"), Transform("shift", 3))
    items = next(e[1][1] for e in h.events if e[0] == "notify")
    assert items[:3] == [old, old.shapeData, builder] and items[-1] is h.glyphs[0]
