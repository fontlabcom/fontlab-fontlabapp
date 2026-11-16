# this_file: tests/test_component_creation.py
"""Plain components for EXISTING glyphs, cloned from one prototype, added in one commit (T14i fix 1).

The doubles log ``clone``, ``checkInitHistoryState``, ``addShape``, the
stamps and the one notification in one list. The ``fontpr`` double answers
only ``get_glyph`` (a VFJ built from the package doubles, with each shape's
extra ``vfj`` keys) and refuses ``set_glyph``; the package has no
``deleteGlyph``: a scratch-glyph path fails the test. Offline proof of the
call order and the refusals, not native Undo.
"""

import itertools
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import test_glyph_creation as tgc
from test_glyph_creation import LOG, Glyph, Layer, Native

import fontlabapp.components.creation as cc
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__

IDS = itertools.count(5000)


class Transform:
    """A QTransform double: (m11, m12, m21, m22, dx, dy)."""

    def __init__(self, m11=1.0, m12=0.0, m21=0.0, m22=1.0, dx=0.0, dy=0.0):
        self.values = (m11, m12, m21, m22, dx, dy)

    def isAffine(self):
        return True

    def m11(self):
        return self.values[0]

    def m12(self):
        return self.values[1]

    def m21(self):
        return self.values[2]

    def m22(self):
        return self.values[3]

    def dx(self):
        return self.values[4]

    def dy(self):
        return self.values[5]


class Component:
    """A component shape double; ``clone`` makes a detached copy unless told otherwise."""

    isComponent = True

    def __init__(self, base, transform=None, share=False, refs=1, fail=None):
        self.vfj = {}
        self.id = next(IDS)
        self.shapeData = NS(id=next(IDS), componentGlyph=base, componentLayer="", note="n", referenceCount=1)
        self.transform = transform or Transform(dx=5.0)
        self.name, self.selected, self.share, self.refs, self.fail = "proto", True, share, refs, fail
        self.contours = []
        self.excluded, self.contentLocked, self.opacity = False, False, 1.0
        self.component_vfj, self.ignore = {}, set()
        self.vfj.clear()

    def __setattr__(self, name, value):
        if name in getattr(self, "ignore", ()):
            return
        object.__setattr__(self, name, value)
        if name == "contentLocked" and not value:
            self.vfj["locked"] = False  # the setter is what clears the saved flag

    def clone(self):
        LOG.append(("clone", self.shapeData.componentGlyph))
        if self.fail is not None:
            raise self.fail
        copy = Component(self.shapeData.componentGlyph, Transform(*self.transform.values))
        if self.share:
            copy.shapeData = self.shapeData
        copy.shapeData.referenceCount = self.refs
        copy.vfj["locked"] = True  # A2 report 26: a clone serializes locked whatever the prototype says
        return copy


class Package(tgc.Package):
    def deleteGlyph(self, glyph):
        raise AssertionError("raw deleteGlyph is outside history")


class FontPR:
    """fontpr double: ``get_glyph`` returns a VFJ-shaped dict of the package glyph."""

    def __init__(self, package):
        self.package, self.calls, self.fail, self.extra_element = package, [], None, False

    def call(self, name, **arguments):
        self.calls.append((name, arguments))
        assert name == "get_glyph", "no native command: only the VFJ read"
        assert arguments["font_id"] == 40, "fontpr finds fonts by fgId"
        if self.fail is not None:
            raise self.fail
        glyph = self.package.findName(arguments["glyph_name"])
        layers = []
        for layer in glyph.layers:
            elements = []
            for shape in layer.shapes:
                if shape.isComponent:
                    component = {"glyphName": shape.shapeData.componentGlyph, **shape.component_vfj}
                    elements.append({"component": component, **shape.vfj})
                else:
                    elements.append({"elementData": {"contours": []}})
            if self.extra_element:
                elements.append({"elementData": {}})
            layers.append({"name": layer.name, "elements": elements})
        return {"name": glyph.name, "layers": layers}


def facts_of(package):
    return tgc.facts_of(package)


@pytest.fixture
def world(monkeypatch):
    LOG.clear()
    native = Native()
    proto = Component("A")
    package = Package(
        Glyph("A", [Layer("L", 600), Layer("B", 640)]),
        Glyph("Adieresis", [Layer("L", 600, [proto]), Layer("B", 640)]),
        Glyph("a", [Layer("L", 500), Layer("B", 520)]),
        Glyph("zero", [Layer("L", 500)]),
    )
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: tgc.STAMP)), QtGui=NS(QTransform=Transform))
    tools = FontPR(package)
    monkeypatch.setitem(sys.modules, "fontlab", native)
    monkeypatch.setitem(sys.modules, "fontpr", tools)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    return NS(native=native, package=package, proto=proto, tools=tools)


def build(world, wanted, target="a"):
    return cc.build_components(world.package, target, wanted, facts_of(world.package))


# ---------------------------------------------------------------- build
def test_build_when_prototype_then_detached_retargeted_clones_in_order_and_font_unchanged(world):
    wanted = [cc.NewComponent("A", "L"), cc.NewComponent("A", "B", 10, -5), cc.NewComponent("zero", "L", 300)]
    shapes = build(world, wanted)
    assert [(s.shapeData.componentGlyph, s.shapeData.componentLayer, s.transform.values) for s in shapes] == [
        ("A", "L", (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)),
        ("A", "B", (1.0, 0.0, 0.0, 1.0, 10.0, -5.0)),
        ("zero", "L", (1.0, 0.0, 0.0, 1.0, 300.0, 0.0)),
    ]
    assert all(s.name == "" and s.shapeData.note == "" and s.selected is False for s in shapes)
    assert LOG == [("clone", "A")] * 3, "no history and no native command before the caller's commit"
    assert world.proto.shapeData.componentGlyph == "A" and world.proto.transform.values[4] == 5.0
    assert world.package.findName("a").findLayer("L").shapes == [], "nothing is in the font yet"


def test_build_when_cloned_then_saved_vfj_locked_key_is_false(world):
    """D26-1: assert the glyph VFJ key; the contentLocked getter reads True on 9.0.9809 regardless."""
    shapes = build(world, [cc.NewComponent("A", "L"), cc.NewComponent("A", "B", 10, -5)])
    glyph = world.package.findName("a")
    for layer, shape in zip(glyph.layers, shapes, strict=True):
        cc.add_component(layer, shape)
    saved = world.tools.call("get_glyph", font_id=40, glyph_name="a")
    elements = [e for layer in saved["layers"] for e in layer["elements"]]
    assert len(elements) == 2 and all(e["locked"] is False for e in elements)


def test_build_then_add_inside_one_commit_then_one_geometry_step(world):
    target = world.package.findName("a")
    shapes = build(world, [cc.NewComponent("A", m) for m in ("L", "B")])
    layers = [target.findLayer("L"), target.findLayer("B")]
    LOG.clear()

    def mutate():
        for layer, shape in zip(layers, shapes, strict=True):
            assert cc.add_component(layer, shape) is shape

    history.commit("Unicase", layers, [target], mutate, operation="geometry", facts=facts_of(world.package))
    assert LOG == [
        ("init", "L"), ("init", "B"), ("init", "a"),
        ("addShape", "L"), ("addShape", "B"),
        ("stamp", "a"), ("notify", "Unicase", ["L", "B", "a"]), ("stamp", "a"),
    ]  # fmt: skip
    assert [s.shapeData.componentGlyph for x in layers for s in x.shapes] == ["A", "A"]


def test_build_when_font_has_no_component_then_kept_row_text_and_no_native_call(world):
    world.package.glyphs.pop("Adieresis")
    with pytest.raises(ValueError) as error:
        build(world, [cc.NewComponent("A", "L")])
    assert str(error.value) == f"a: kept; {cc.NO_PROTOTYPE}."
    assert "Undo" not in str(error.value) and LOG == []


@pytest.mark.parametrize(
    "transform",
    [Transform(m11=2.0), Transform(m12=0.5)],
    ids=["scaled", "slanted"],
)
def test_prototype_when_only_scaled_or_slanted_component_then_none(world, transform):
    world.proto.transform = transform
    assert cc.prototype(world.package, facts_of(world.package)) is None


def test_prototype_when_only_in_auto_layer_then_none(world):
    world.package.findName("Adieresis").layers[0].autoLayer = True
    assert cc.prototype(world.package, facts_of(world.package)) is None


def test_build_when_nothing_then_no_native_call(world):
    assert build(world, []) == ()
    assert LOG == []


@pytest.mark.parametrize(
    ("item", "text"),
    [
        (cc.NewComponent("missing", "L"), "a · L: kept; no base glyph missing with that layer"),
        (cc.NewComponent("zero", "B"), "a · B: kept; no base glyph zero with that layer"),
        (cc.NewComponent("", "L"), "a: kept; a component needs a base glyph and a layer"),
        (cc.NewComponent("A", ""), "a: kept; a component needs a base glyph and a layer"),
        (cc.NewComponent("A", "L", float("nan")), "a · L: kept; the offset must be finite numbers"),
    ],
    ids=["no-base", "no-layer", "empty-base", "empty-layer", "nan"],
)
def test_build_when_refused_then_value_error_naming_target_before_any_clone(world, item, text):
    with pytest.raises(ValueError, match=text):
        build(world, [cc.NewComponent("A", "L"), item])
    assert LOG == []


@pytest.mark.parametrize(
    ("change", "text"),
    [
        ({"share": True}, "did not detach the component copy for A"),
        ({"refs": 2}, "did not detach the component copy for A"),
        ({"fail": TimeoutError("clone timed out")}, "clone timed out"),
        ({"fail": RuntimeError("wrapper gone")}, "wrapper gone"),
    ],
    ids=["shared-data", "references", "timeout", "native-error"],
)
def test_build_when_clone_fails_then_runtime_error_says_nothing_was_added(world, change, text):
    for key, value in change.items():
        setattr(world.proto, key, value)
    with pytest.raises(RuntimeError) as error:
        build(world, [cc.NewComponent("A", "L")])
    message = str(error.value)
    assert type(error.value) is RuntimeError and text in message
    assert message.startswith("a: kept; ") and message.endswith("Nothing was added to the font.")
    assert history.UNDO_HINT not in message and "Undo" not in message, "no Undo advice: the font is unchanged"
    assert world.package.findName("a").findLayer("L").shapes == []


# ---------------------------------------------------------------- add
def test_add_component_when_layer_drops_shape_then_runtime_error(world):
    shapes = build(world, [cc.NewComponent("A", "L")])
    layer = Layer("L")
    layer.addShape = lambda shape: None
    with pytest.raises(RuntimeError, match="did not add the component A"):
        cc.add_component(layer, shapes[0])


def test_add_component_when_layer_already_has_that_base_but_drops_new_then_runtime_error(world):
    shapes = build(world, [cc.NewComponent("A", "L"), cc.NewComponent("A", "L")])
    layer = Layer("L", 0, [shapes[0]])
    layer.addShape = lambda shape: None
    with pytest.raises(RuntimeError, match="did not add the component A"):
        cc.add_component(layer, shapes[1])


def test_module_when_cold_imported_then_only_stdlib_and_no_native():
    import fontlabapp

    root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc, sys
class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in ('fontlabapp', 'org') and fullname.split('.')[0] not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)
sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.components.creation
lazy = {'fontlabapp.core.scripting', 'PythonQt', 'fontlab', 'fontpr', 'fontgate'}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-c", script, root], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------- strict prototype filter (re-review N1)
@pytest.mark.parametrize(
    ("member", "value"),
    [("excluded", True), ("opacity", 0.5), ("excluded", 0)],
    ids=["excluded", "opacity", "excluded-not-bool"],
)
def test_prototype_when_shape_style_not_default_then_none(world, member, value):
    setattr(world.proto, member, value)
    assert cc.prototype(world.package, facts_of(world.package)) is None


def test_prototype_when_style_member_unreadable_then_none(world, monkeypatch):
    class Unreadable(Component):
        @property
        def excluded(self):
            raise AttributeError("no such member")

        @excluded.setter
        def excluded(self, value):
            pass

    shape = Unreadable("A")
    world.package.findName("Adieresis").layers[0].shapes = [shape]
    assert cc.prototype(world.package, facts_of(world.package)) is None


@pytest.mark.parametrize(
    ("where", "vfj"),
    [
        ("component", {"attached": True}),
        ("component", {"attachAnchor": "top"}),
        ("component", {"off2026Variation": [1]}),
        ("component", {"unknownKey": 1}),
        ("element", {"nonSpacing": True}),
        ("element", {"booleanOperation": 2}),
        ("element", {"locked": True}),
        ("element", {"excluded": True}),
        ("element", {"opacity": 0.4}),
    ],
    ids=["attached", "anchor", "variation", "unknown", "nonspacing", "boolean", "locked", "excluded", "opacity"],
)
def test_prototype_when_vfj_state_not_default_then_none_and_kept_row(world, where, vfj):
    (world.proto.component_vfj if where == "component" else world.proto.vfj).update(vfj)
    assert cc.prototype(world.package, facts_of(world.package)) is None
    with pytest.raises(ValueError, match="a: kept; the font has no plain, unattached component"):
        build(world, [cc.NewComponent("A", "L")])
    assert LOG == [], "no clone of a disqualified prototype"


def test_prototype_when_explicit_defaults_then_qualifies(world):
    world.proto.component_vfj.update({"attached": False, "layerName": "L"})
    world.proto.vfj.update({"locked": False, "nonSpacing": False, "opacity": 1.0})
    assert cc.prototype(world.package, facts_of(world.package)) is world.proto


def test_prototype_when_native_content_lock_true_and_no_vfj_lock_then_qualifies(world):
    """FontLab 9.0.9808 reads contentLocked True for every component (A2 report 18); the VFJ decides."""
    world.proto.contentLocked = True
    assert cc.prototype(world.package, facts_of(world.package)) is world.proto


def test_prototype_when_native_content_lock_true_and_vfj_locked_then_none(world):
    world.proto.contentLocked = True
    world.proto.vfj.update({"locked": True})
    assert cc.prototype(world.package, facts_of(world.package)) is None


@pytest.mark.parametrize("fault", ["count", "read", "base"])
def test_prototype_when_vfj_unreadable_or_unmatched_then_none(world, fault):
    if fault == "count":
        world.tools.extra_element = True
    elif fault == "read":
        world.tools.fail = RuntimeError("Font id not found.")
    else:
        world.proto.component_vfj["glyphName"] = "B"
    assert cc.prototype(world.package, facts_of(world.package)) is None


def test_prototype_when_first_candidate_attached_then_next_qualifying_one(world):
    world.proto.component_vfj["attached"] = True
    plain = Component("A")
    world.package.glyphs["Aring"] = Glyph("Aring", [Layer("L", 600, [plain])])
    assert cc.prototype(world.package, facts_of(world.package)) is plain
    assert [a["glyph_name"] for _, a in world.tools.calls] == ["Adieresis", "Aring"]


def test_no_prototype_text_when_read_then_no_absolute_constructor_claim():
    assert "no component constructor is measured on this FontLab build" in cc.NO_PROTOTYPE
    assert "gives Python no component constructor" not in cc.NO_PROTOTYPE


# ---------------------------------------------------------------- full re-target read-back (re-review N4)
@pytest.mark.parametrize(
    ("field", "offset"),
    [("componentLayer", (10, -5)), ("transform", (10, -5)), ("transform", (10, 0)), ("transform", (5, -5))],
    ids=["layer", "both", "x-only", "y-only"],
)
def test_build_when_retarget_not_kept_then_runtime_error(world, monkeypatch, field, offset):
    real = Component.clone

    def clone(self):
        copy = real(self)
        if field == "transform":
            copy.ignore = {"transform"}
        else:
            copy.shapeData = NS(**vars(copy.shapeData))
            data = copy.shapeData

            class Data(NS):
                def __setattr__(self, name, value):
                    if name != "componentLayer":
                        object.__setattr__(self, name, value)

            copy.shapeData = Data(**vars(data))
        return copy

    monkeypatch.setattr(Component, "clone", clone)
    with pytest.raises(RuntimeError, match="did not re-target the component copy to A · B"):
        build(world, [cc.NewComponent("A", "B", *offset)])


def test_prototype_when_two_component_layers_then_one_vfj_read(world):
    user = world.package.findName("Adieresis")
    world.proto.component_vfj = {"attached": True}
    second = Component("A")
    user.findLayer("B").shapes = [second]
    assert cc.prototype(world.package, facts_of(world.package)) is second
    assert len(world.tools.calls) == 1, "VFJ must be fetched once per glyph, not layer"


def test_build_when_cache_shared_then_prototype_scan_reused(world):
    facts, cache = facts_of(world.package), {}
    for target in ("a", "zero"):
        cc.build_components(world.package, target, [cc.NewComponent("A", "L")], facts, cache=cache)
    assert len(world.tools.calls) == 1, "one Apply can reuse its prototype"


def test_build_when_missing_prototype_cached_then_scan_not_repeated(world):
    world.proto.component_vfj = {"attached": True}
    facts, cache = facts_of(world.package), {}
    for target in ("a", "zero"):
        with pytest.raises(ValueError, match="no plain"):
            cc.build_components(world.package, target, [cc.NewComponent("A", "L")], facts, cache=cache)
    assert len(world.tools.calls) == 1
