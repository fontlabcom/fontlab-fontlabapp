# this_file: tests/test_revision_compare.py
# SPDX-License-Identifier: Apache-2.0
"""Owned native-shaped records; no archived body or FontLab code executes."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict
from types import SimpleNamespace as NS

import fontlabapp.fonts.revisions.model as api
import pytest


def matrix(values=(1, 0, 0, 1, 0, 0)):
    values = values + (0, 0, 1) if len(values) == 6 else values
    return NS(**{name: lambda value=value: value for name, value in zip(api.MATRIX_FIELDS, values)})


def glyph(name="space", identifier=1):
    nodes = [NS(x=0, y=-10, type="on", nodeState=257), NS(x=12, y=0, type="curve", nodeState=772)]
    contour = NS(closed=True, isTT=False, nodes=lambda: nodes)
    shape = NS(isComponent=False, transform=matrix(), contours=[contour])
    layer = NS(id=identifier + 100, isNull=False, advanceWidth=0, transform=matrix(), shapes=[shape], anchors=[NS(name="top", point=NS(x=lambda: 0, y=lambda: 700))])
    class Glyph:
        id = identifier
        isNull = False
        @property
        def fgGlyph(self):
            raise AssertionError("Forbidden FontGate glyph getter")
        def findLayer(self, master):
            return self.layers.get(master)
    result = Glyph()
    result.name = name
    result.layers = {"Regular": layer}
    return result


@pytest.fixture
def source(monkeypatch):
    class Package:
        isNull = False
        def __init__(self, identifier, label):
            self.id, self.fgId = identifier, identifier + 1000
            self.masters = ["Regular", "Bold"]
            self.path = label + ".vfj"
            self.items = [glyph()]
            self.label = label
        def title_name(self):
            return self.label
        @property
        def fgPackage(self):
            return NS(glyphs=[NS(name=g.name) for g in self.items])
        def findName(self, name):
            return next((g for g in self.items if g.name == name), None)
    packages = [Package(10, "A"), Package(20, "B")]
    workspace = NS(packages=lambda: list(packages))
    def promote(item):
        assert item in packages, "Promote registered packages only"
        return item
    monkeypatch.setattr(api, "_native", lambda name: NS(flPackage=promote))
    return workspace, packages


def test_choices_use_fg_ids_distinct_from_native_ids_and_keep_open_order(source):
    workspace, packages = source
    before = deepcopy([p.__dict__ for p in packages])
    choices = api.font_choices(workspace)
    assert [(c.font_id, c.package_id, c.label, c.masters, c.path) for c in choices] == [(1010, 10, "A", ("Regular", "Bold"), "A.vfj"), (1020, 20, "B", ("Regular", "Bold"), "B.vfj")]
    assert [p.id for p in packages] == [10, 20]
    assert [p.path for p in packages] == [row["path"] for row in before]
    with pytest.raises(ValueError, match="open"):
        api.capture(workspace, 10, "Regular")
    with pytest.raises(FrozenInstanceError):
        choices[0].label = "changed"


def test_capture_is_plain_frozen_exact_zero_offcurve_raw_state_and_closed(source):
    workspace, _ = source
    snapshot = api.capture(workspace, 1010, "Regular")
    record = snapshot.glyphs[0]
    assert record.advance == 0
    assert record.state == "present"
    contour = record.geometry[1][0][2][0]
    assert contour == (True, False, ((0.0, -10.0, "on", 257), (12.0, 0.0, "curve", 772)))
    assert record.anchors == (("top", 0.0, 700.0),)
    assert snapshot.master_present
    assert asdict(snapshot)["font"]["font_id"] == 1010
    with pytest.raises(FrozenInstanceError):
        record.advance = 4
    api.validate(workspace, snapshot)


@pytest.mark.parametrize("change,field", [
    (lambda l: setattr(l, "advanceWidth", -50), "advance"),
    (lambda l: setattr(l.shapes[0].contours[0], "closed", False), "geometry"),
    (lambda l: setattr(l.shapes[0].contours[0], "isTT", True), "geometry"),
    (lambda l: setattr(l.shapes[0].contours[0].nodes()[0], "nodeState", 258), "geometry"),
    (lambda l: setattr(l.shapes[0].contours[0].nodes()[1], "type", "off"), "geometry"),
    (lambda l: setattr(l.shapes[0].contours[0].nodes()[0], "x", .125), "geometry"),
    (lambda l: l.shapes[0].contours[0].nodes().reverse(), "geometry"),
    (lambda l: setattr(l.shapes[0], "transform", matrix((1, 0, 0, 1, .125, -7))), "geometry"),
    (lambda l: setattr(l, "transform", matrix((1, 0, 0, 1, 0, -7))), "geometry"),
    (lambda l: setattr(l.anchors[0], "name", "bottom"), "anchors"),
    (lambda l: setattr(l.anchors[0].point, "x", lambda: -2), "anchors"),
])
def test_named_field_differences_are_exact_and_invalidate_snapshot(source, change, field):
    workspace, packages = source
    before = api.capture(workspace, 1020, "Regular")
    change(packages[1].items[0].layers["Regular"])
    differences = api.compare(api.capture(workspace, 1010, "Regular"), api.capture(workspace, 1020, "Regular"))
    expected = (field, "raw_node_state") if before.glyphs[0].raw_node_states != api.capture(workspace, 1020, "Regular").glyphs[0].raw_node_states else (field,)
    assert [(d.glyph, d.fields) for d in differences] == [("space", expected)]
    with pytest.raises(ValueError, match="stale"):
        api.validate(workspace, before)


def test_missing_master_layer_glyph_and_membership_order_are_explicit(source):
    workspace, packages = source
    left = api.capture(workspace, 1010, "Regular")
    assert api.compare(left, api.capture(workspace, 1020, "Regular")) == ()
    missing = api.capture(workspace, 1020, "Missing")
    assert not missing.master_present
    assert missing.glyphs[0].state == "missing_master"
    assert api.compare(left, missing)[0].fields == ("master_presence",)
    assert api.capture(workspace, 1020, "Bold").glyphs[0].state == "missing_layer"
    packages[1].items = [glyph("other", 2)]
    rows = api.compare(left, api.capture(workspace, 1020, "Regular"))
    assert [(d.glyph, d.fields) for d in rows] == [("", ("glyph_order",)), ("space", ("glyph_presence",)), ("other", ("glyph_presence",))]
    packages[0].items += [glyph("other", 2)]
    packages[1].items = list(reversed(packages[0].items))
    rows = api.compare(api.capture(workspace, 1010, "Regular"), api.capture(workspace, 1020, "Regular"))
    assert [d.fields for d in rows] == [("glyph_order",)]


def test_components_preserve_shape_order_base_and_unrounded_matrix(source):
    workspace, packages = source
    layer = packages[1].items[0].layers["Regular"]
    layer.shapes.append(NS(isComponent=True, shapeData=NS(componentGlyph="base", componentLayer="Regular"), transform=matrix((1, .2, .3, 1, .125, -7))))
    before = api.capture(workspace, 1020, "Regular")
    assert before.glyphs[0].components == ((1, "base", "Regular", (1.0, .2, .3, 1.0, .125, -7.0, 0.0, 0.0, 1.0)),)
    layer.shapes[1].shapeData.componentGlyph = "replacement"
    after = api.capture(workspace, 1020, "Regular")
    assert api.compare(before, after)[0].fields == ("components",)
    assert api.capture(workspace, 1020, "Regular", components=False).glyphs[0].components is None
    with pytest.raises(ValueError, match="scope"):
        api.compare(before, api.capture(workspace, 1020, "Regular", components=False))
    layer.shapes.reverse()
    assert "geometry" in api.compare(after, api.capture(workspace, 1020, "Regular"))[0].fields


def test_component_layer_change_is_reported_and_invalidates_snapshot(source):
    workspace, packages = source
    layer = packages[1].items[0].layers["Regular"]
    data = NS(componentGlyph="base", componentLayer="Regular")
    layer.shapes.append(NS(isComponent=True, shapeData=data, transform=matrix()))
    before = api.capture(workspace, 1020, "Regular")
    data.componentLayer = "Bold"
    after = api.capture(workspace, 1020, "Regular")
    assert [(row.glyph, row.fields) for row in api.compare(before, after)] == [
        ("space", ("components",))
    ], "Switching the referenced layer changes the component even with the same base and matrix"
    with pytest.raises(ValueError, match="stale"):
        api.validate(workspace, before)


def test_unbacked_registered_font_refuses_before_allocating_fontgate_getter(source):
    workspace, packages = source
    class Unbacked(type(packages[0])):
        @property
        def fgPackage(self):
            raise AssertionError("Do not allocate FontGate backing during a read")
    package = Unbacked(90, "unbacked")
    package.fgId = 0
    packages.append(package)
    with pytest.raises(ValueError, match="FontGate backing"):
        api.capture(workspace, 1010, "Regular")


@pytest.mark.parametrize("change", [lambda ps: ps.reverse(), lambda ps: ps.pop(), lambda ps: ps[0].masters.reverse(), lambda ps: setattr(ps[0], "path", "replaced.vfj"), lambda ps: setattr(ps[0], "id", 99), lambda ps: ps[0].items.append(glyph("new", 3))])
def test_complete_source_domain_changes_refuse_stale_snapshots(source, change):
    workspace, packages = source
    snapshot = api.capture(workspace, 1010, "Regular")
    change(packages)
    with pytest.raises(ValueError, match="stale"):
        api.validate(workspace, snapshot)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_geometry_never_returns_partial_capture(source, value):
    workspace, packages = source
    packages[0].items[0].layers["Regular"].shapes[0].contours[0].nodes()[1].y = value
    with pytest.raises(ValueError, match="finite"):
        api.capture(workspace, 1010, "Regular")


def test_empty_closed_missing_and_unreadable_sources_fail_loudly(source):
    workspace, packages = source
    packages[0].items = []
    assert api.capture(workspace, 1010, "Regular").glyphs == ()
    packages[0].items = [glyph(), glyph()]
    with pytest.raises(ValueError, match="duplicate"):
        api.capture(workspace, 1010, "Regular")
    packages[0].items = [glyph()]
    packages[0].findName = lambda name: None
    with pytest.raises(ValueError, match="Glyph"):
        api.capture(workspace, 1010, "Regular")
    packages.clear()
    assert api.font_choices(workspace) == ()


def test_capture_rejects_changes_during_read(source):
    workspace, packages = source
    original = packages[0].findName
    def changing(name):
        result = original(name)
        result.layers["Regular"].advanceWidth += 1
        return result
    packages[0].findName = changing
    with pytest.raises(ValueError, match="changed"):
        api.capture(workspace, 1010, "Regular")


@pytest.mark.parametrize("flag", [0x20, 0x40, 0x80, 0x800])
def test_transient_flags_are_explicit_raw_differences_not_outline_geometry(source, flag):
    workspace, packages = source
    before = api.capture(workspace, 1020, "Regular")
    packages[1].items[0].layers["Regular"].shapes[0].contours[0].nodes()[0].nodeState ^= flag
    after = api.capture(workspace, 1020, "Regular")
    assert api.compare(before, after)[0].fields == ("raw_node_state",)
    assert before.glyphs[0].geometry == after.glyphs[0].geometry
    with pytest.raises(ValueError, match="stale"):
        api.validate(workspace, before)


@pytest.mark.parametrize("flag", [0x8, 0x10, 0x1000, 0x2000, 0x10000])
def test_smooth_first_advanced_and_unknown_flags_remain_geometry_changes(source, flag):
    workspace, packages = source
    before = api.capture(workspace, 1020, "Regular")
    packages[1].items[0].layers["Regular"].shapes[0].contours[0].nodes()[0].nodeState ^= flag
    assert api.compare(before, api.capture(workspace, 1020, "Regular"))[0].fields == ("geometry", "raw_node_state")


def test_full_projective_transform_coefficients_are_retained(source):
    workspace, packages = source
    before = api.capture(workspace, 1020, "Regular")
    packages[1].items[0].layers["Regular"].shapes[0].transform = matrix((1, 0, 0, 1, 0, 0, .125, -.2, 2))
    after = api.capture(workspace, 1020, "Regular")
    assert after.glyphs[0].geometry[1][0][1] == (1, 0, 0, 1, 0, 0, .125, -.2, 2)
    assert api.compare(before, after)[0].fields == ("geometry",)


def test_duplicate_master_ids_null_packages_and_invalid_explicit_master_refuse(source):
    workspace, packages = source
    for master in ("", None, 12):
        with pytest.raises(ValueError, match="master"):
            api.capture(workspace, 1010, master)
    packages[0].masters = ["Regular", "Regular"]
    with pytest.raises(ValueError, match="duplicate master"):
        api.font_choices(workspace)
    packages[0].masters = ["Regular"]
    packages[1].fgId = packages[0].fgId
    with pytest.raises(ValueError, match="duplicate FontGate"):
        api.font_choices(workspace)
    packages[0].isNull = True
    with pytest.raises(ValueError, match="registration"):
        api.font_choices(workspace)


def test_unreadable_layer_and_membership_identity_are_not_partial_success(source):
    workspace, packages = source
    snapshot = api.capture(workspace, 1010, "Regular")
    packages[0].items[0].layers["Regular"].advanceWidth = "invalid"
    with pytest.raises(ValueError):
        api.capture(workspace, 1010, "Regular")
    with pytest.raises(ValueError, match="stale"):
        api.validate(workspace, snapshot)
    packages[0].items[0].layers["Regular"].advanceWidth = 0
    packages[0].items[0].id = 777
    with pytest.raises(ValueError, match="stale"):
        api.validate(workspace, snapshot)
