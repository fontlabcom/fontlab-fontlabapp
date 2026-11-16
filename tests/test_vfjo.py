# this_file: tests/test_vfjo.py
# SPDX-License-Identifier: Apache-2.0
"""Tests for ``fontlabapp.vfjo``: Box casting, safety, navigation, edits and paste routing (no FontLab)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fontlabapp import vfjo
from fontlabapp.objects import json_data
from fontlabapp.vfjo import _data, _edit

DATA = Path(__file__).parent / "data" / "vfjo"
FIXTURES = ["glyph_o", "glyph_Aogonek", "glyphs_o_dcaron", "element_o"]


def fixture(name: str) -> vfjo.Objects:
    return vfjo.load(DATA / f"{name}.json")


def raw(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text())


# --- loading and validation -------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_load_when_fixture_then_dict_round_trip_is_equal(name):
    objs = fixture(name)
    assert objs.to_dict() == raw(name), f"{name}: Box round trip changed the data"
    assert json.loads(objs.to_bytes()) == raw(name), (
        f"{name}: to_bytes changed the data"
    )


def test_loads_when_not_object_json_then_value_error():
    with pytest.raises(ValueError, match="dataType"):
        vfjo.loads({"dataType": "other", "upm": 1000})
    with pytest.raises(ValueError):
        vfjo.loads(b"not json")


def test_loads_when_bytes_str_mapping_or_objects_then_same_data():
    text = (DATA / "glyph_o.json").read_text()
    a, b, c = vfjo.loads(text.encode()), vfjo.loads(text), vfjo.loads(raw("glyph_o"))
    d = vfjo.loads(a)
    assert a.to_dict() == b.to_dict() == c.to_dict() == d.to_dict()
    assert d.data is not a.data, "loads(Objects) must copy"


def test_loads_when_mapping_then_source_is_not_shared():
    source = raw("glyph_o")
    objs = vfjo.loads(source)
    objs.data.glyph.layers[0].advanceWidth = 1
    assert source["glyph"]["layers"][0]["advanceWidth"] == 1162, (
        "edits must not reach the source dict"
    )


# --- safety --------------------------------------------------------------------


def test_read_when_missing_key_then_raises():
    layer = fixture("glyph_o").data.glyph.layers[0]
    with pytest.raises(KeyError):
        layer.advanceWidht  # noqa: B018 - the read itself must raise
    with pytest.raises(AttributeError):
        layer.advanceWidht  # noqa: B018


def test_write_when_typo_new_key_then_unknown_key_error():
    objs = fixture("glyph_o")
    layer = objs.data.glyph.layers[0]
    with pytest.raises(vfjo.UnknownKeyError, match="add_key"):
        layer.advanceWidht = 3
    with pytest.raises(vfjo.UnknownKeyError):
        layer["advanceWidht"] = 3
    with pytest.raises(vfjo.UnknownKeyError):
        objs.data.glyph.nmae = "x"
    assert "advanceWidht" not in layer, "a refused key must not be stored"


def test_write_when_existing_or_known_key_then_allowed():
    objs = fixture("glyph_Aogonek")
    layer = objs.data.glyph.layers[1]
    layer.advanceWidth = 999
    layer.metricsLeft = "=A"
    element = layer.elements[0]
    element.transform = {"xOffset": 5}
    assert layer.advanceWidth == 999 and layer.metricsLeft == "=A"
    with pytest.raises(vfjo.UnknownKeyError):
        element.transform.rotation = 3  # the new dict is locked as a transform


def test_write_when_free_level_then_any_key():
    hint = fixture("glyph_o").data.glyph.layers[0].hints[0]
    hint.custom = 1
    assert hint.custom == 1, "hints are not a known level"


def test_add_key_when_unknown_key_then_added_and_locked():
    layer = fixture("glyph_o").data.glyph.layers[0]
    assert vfjo.add_key(layer, "transform", {"xOffset": 1}) is layer
    with pytest.raises(vfjo.UnknownKeyError):
        layer.transform.rotation = 1
    assert vfjo.add_key({}, "a", 1) == {"a": 1}, "plain mappings also work"


def test_copy_when_edited_then_independent_and_locked():
    objs = fixture("glyphs_o_dcaron")
    twin = objs.copy()
    twin.glyphs[0].name = "x"
    assert objs.glyph_names == ["o", "dcaron"] and twin.glyph_names == ["x", "dcaron"]
    with pytest.raises(vfjo.UnknownKeyError):
        twin.glyphs[0].layers[0].advanceWidht = 1


# --- root helpers --------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "kind", "names"),
    [
        ("glyph_o", "glyph", ["o"]),
        ("glyphs_o_dcaron", "glyph", ["o", "dcaron"]),
        ("element_o", "element", []),
    ],
)
def test_glyphs_when_roots_differ_then_names(name, kind, names):
    objs = fixture(name)
    assert objs.kind == kind
    assert objs.glyph_names == names
    assert [g.name for g in objs.glyphs] == names
    assert kind in repr(objs)


def test_kind_when_empty_or_mixed():
    empty = vfjo.loads({"dataType": json_data.DATA_TYPE, "upm": 1000, "packageId": 1})
    assert empty.kind == "" and empty.glyphs == [] and "empty" in repr(empty)
    mixed = vfjo.loads(
        {
            "dataType": json_data.DATA_TYPE,
            "upm": 1000,
            "packageId": 1,
            "objects": [{"glyph": {"name": "a"}}, {"contour": {"nodes": ["0 0"]}}],
        }
    )
    assert mixed.kind == "mixed" and mixed.glyph_names == ["a"]


def test_describe_save_and_clipboard(tmp_path, monkeypatch):
    objs = fixture("glyph_o")
    assert objs.describe()[0].startswith('glyph "o" U+006F'), objs.describe()
    path = objs.save(tmp_path / "o.json")
    assert vfjo.load(path).to_dict() == raw("glyph_o")
    seen = []
    monkeypatch.setattr(json_data, "copy_to_clipboard", lambda data: seen.append(data))
    objs.copy_to_clipboard()
    assert json.loads(seen[0]) == raw("glyph_o")
    assert isinstance(objs.envelope(), json_data.Envelope)


# --- constructors that need FontLab (faked) -------------------------------------


class FakePackage:
    def __init__(self, names):
        self.glyphs = {name: f"<glyph {name}>" for name in names}

    def findName(self, name):
        return self.glyphs.get(name)


def test_from_glyphs_when_names_then_exports_resolved_glyphs(monkeypatch):
    calls = []

    def export(package, objects):
        calls.append(objects)
        return (DATA / "glyph_o.json").read_bytes()

    monkeypatch.setattr(json_data, "export", export)
    package = FakePackage(["o"])
    assert vfjo.from_glyphs("o", font=package).glyph_names == ["o"]
    assert calls == [["<glyph o>"]]
    with pytest.raises(KeyError, match="zz"):
        vfjo.from_glyphs(["zz"], font=package)


def test_from_glyphs_when_defaults_then_current_font_and_selection(monkeypatch):
    monkeypatch.setattr(
        json_data, "export", lambda p, o: (DATA / "glyph_o.json").read_bytes()
    )
    monkeypatch.setattr(_data, "_current_package", lambda: FakePackage(["o"]))
    monkeypatch.setattr(_data, "_selected_names", lambda: ["o"])
    assert vfjo.from_glyphs().glyph_names == ["o"]
    monkeypatch.setattr(_data, "_selected_names", list)
    with pytest.raises(ValueError, match="No glyphs"):
        vfjo.from_glyphs()
    monkeypatch.setattr(_data, "_current_package", lambda: None)
    with pytest.raises(RuntimeError, match="No font"):
        vfjo.from_glyphs()


def test_from_clipboard_when_empty_or_json(monkeypatch):
    monkeypatch.setattr(json_data, "read_clipboard", lambda: None)
    assert vfjo.from_clipboard() is None
    monkeypatch.setattr(
        json_data, "read_clipboard", lambda: (DATA / "element_o.json").read_bytes()
    )
    assert vfjo.from_clipboard().kind == "element"


# --- navigation ------------------------------------------------------------------


def test_navigation_when_glyph_then_layers_elements_contours_anchors():
    objs = fixture("glyph_o")
    assert [layer.name for layer in vfjo.layers(objs)] == ["Black", "Hairline"]
    assert len(list(vfjo.elements(objs))) == 2
    assert len(list(vfjo.contours(objs))) == 4
    assert [a.name for a in vfjo.anchors(objs)] == ["top", "bottom", "top", "bottom"]
    assert len(list(vfjo.contours(objs.glyphs[0]))) == 4, "a glyph box works too"
    with pytest.raises(TypeError):
        list(vfjo.layers({"a": 1}))


def test_navigation_when_element_root_or_nested_elements():
    objs = fixture("element_o")
    assert list(vfjo.layers(objs)) == []
    assert len(list(vfjo.elements(objs))) == 1
    assert len(list(vfjo.contours(objs))) == 2
    element = objs.data.element
    inner = {"elementData": {"contours": [{"nodes": ["1 2"]}]}}
    vfjo.add_key(element.elementData, "elements", [inner])
    assert len(list(vfjo.elements(objs))) == 2, "nested elements are walked"
    assert len(list(vfjo.contours(objs))) == 3


def test_navigation_when_contour_or_layer_root():
    head = {"dataType": json_data.DATA_TYPE, "upm": 1000, "packageId": 1}
    contour = vfjo.loads({**head, "contour": {"nodes": ["0 0", "10 0"]}})
    assert len(list(vfjo.contours(contour))) == 1
    layer = vfjo.loads(
        {**head, "layer": {"name": "L", "anchors": [{"name": "a", "point": "1 1"}]}}
    )
    assert [x.name for x in vfjo.layers(layer)] == ["L"]
    assert [a.point for a in vfjo.anchors(layer)] == ["1 1"]


# --- edits -------------------------------------------------------------------------


def test_edit_nodes_when_moved_then_nodes_change():
    objs = fixture("glyph_o")
    vfjo.edit_nodes(
        objs, lambda node: node.moved(1, 0) if node.name == "av01" else None
    )
    first = objs.data.glyph.layers[0].elements[0].elementData.contours[0].nodes[0]
    assert first == "584 1056 s {n:'av01'}", first


def test_edit_nodes_when_point_count_changes_then_value_error():
    objs = fixture("glyph_o")
    before = objs.to_dict()
    double = vfjo.Node(
        points=((0, 0), (1, 1), (2, 2)), smooth=False, g2=False, close=False
    )
    with pytest.raises(
        ValueError, match=r"point count of glyph 'o' layer 'Black' contour 'contour'"
    ):
        vfjo.edit_nodes(objs, lambda node: double)
    assert objs.to_dict() == before, "the failing contour is left unchanged"


def test_move_when_outline_glyph_then_nodes_anchors_guides_hints_follow():
    objs = vfjo.move(fixture("glyph_o"), 10, -5)
    layer = objs.data.glyph.layers[0]
    assert layer.elements[0].elementData.contours[0].nodes[0] == "593 1051 s {n:'av01'}"
    assert "transform" not in layer.elements[0], "outline elements move their nodes"
    assert layer.anchors[0].point == "593 1115"
    assert layer.guidelines[0].position == 602
    vertical = next(h for h in layer.hints if h.get("vertical"))
    assert vertical.node0.nodeNode.point == "61 517" and vertical.thickness == 320
    assert layer.advanceWidth == 1162, "move keeps widths"


def test_move_when_anchors_false_then_anchors_stay():
    objs = vfjo.move(fixture("glyph_o"), 10, 0, anchors=False)
    assert objs.data.glyph.layers[0].anchors[0].point == "583 1120"


def test_move_when_components_then_transforms_change():
    objs = vfjo.move(fixture("glyph_Aogonek"), 10, 0)
    black, hairline = objs.data.glyph.layers
    assert black.elements[0].transform == {"xOffset": 8}
    assert black.elements[1].transform == {"xOffset": 866}
    assert hairline.elements[0].transform == {"xOffset": 10}, (
        "a transform is added at non-default values only"
    )
    assert black.anchors[0].point == "719 1525"


def test_move_when_zero_then_no_transform_added():
    objs = vfjo.move(fixture("glyph_Aogonek"), 0, 0)
    assert objs.to_dict() == raw("glyph_Aogonek")


def test_scale_when_scaled_component_then_transform_composed():
    objs = vfjo.scale(fixture("glyphs_o_dcaron"), 2, origin=(100, 0), widths=True)
    black = objs.glyphs[1].layers[0]
    assert black.elements[1].transform == {"xScale": 1.4, "xOffset": 2296, "yScale": 2}
    assert black.elements[0].transform == {"xOffset": -100, "xScale": 2, "yScale": 2}
    assert black.advanceWidth == 2464
    assert black.anchors[0].point == "1760 3050"


def test_scale_when_outline_then_nodes_and_hint_thickness():
    objs = vfjo.scale(fixture("glyph_o"), 0.5, 2)
    layer = objs.data.glyph.layers[0]
    assert (
        layer.elements[0].elementData.contours[0].nodes[0] == "291.5 2112 s {n:'av01'}"
    )
    hints = list(layer.hints)
    assert next(h for h in hints if h.get("vertical")).thickness == 160
    assert next(h for h in hints if h.get("horizontal")).thickness == 480
    assert layer.advanceWidth == 1162, "widths=False keeps widths"


def test_scale_when_element_contour_or_center_guide_then_mapped():
    head = {"dataType": json_data.DATA_TYPE, "upm": 1000, "packageId": 1}
    contour = vfjo.scale(vfjo.loads({**head, "contour": {"nodes": ["10 10"]}}), 3)
    assert contour.data.contour.nodes == ["30 30"]
    element = vfjo.scale(fixture("element_o"), 2)
    assert (
        element.data.element.elementData.contours[0]
        .nodes[0]
        .startswith(
            str(
                vfjo.Node.parse(
                    raw("element_o")["element"]["elementData"]["contours"][0]["nodes"][
                        0
                    ]
                ).scaled(2)
            )
        )
    )
    layer = vfjo.loads(
        {
            **head,
            "layer": {
                "guidelines": [
                    {"center": "10 20", "vector": "1 1"},
                    {"horizontal": True, "position": 5},
                ]
            },
        }
    )
    vfjo.move(layer, 1, 1)
    assert [dict(g) for g in layer.data.layer.guidelines] == [
        {"center": "11 21", "vector": "1 1"},
        {"horizontal": True, "position": 6},
    ]


def test_move_when_unknown_transform_key_then_value_error():
    objs = fixture("glyph_Aogonek")
    vfjo.add_key(objs.data.glyph.layers[0].elements[0].transform, "rotate", 5)
    with pytest.raises(ValueError, match="rotate"):
        vfjo.move(objs, 1, 0)


def test_rename_set_width_and_add_suffix():
    objs = fixture("glyphs_o_dcaron")
    vfjo.rename(objs, {"o": "o.alt"})
    assert objs.glyph_names == ["o.alt", "dcaron"]
    vfjo.rename(objs, str.upper)
    assert objs.glyph_names == ["O.ALT", "DCARON"]
    vfjo.set_width(objs, lambda w: w + 10)
    assert objs.glyphs[0].layers[0].advanceWidth == 1172
    vfjo.set_width(objs, 500)
    assert {layer.advanceWidth for layer in vfjo.layers(objs)} == {500}
    vfjo.add_suffix(objs, ".s")
    assert objs.glyph_names == ["O.ALT.s", "DCARON.s"]
    assert "unicode" not in objs.glyphs[0], "add_suffix drops Unicode values by default"
    keep = vfjo.add_suffix(fixture("glyph_o"), ".k", drop_unicodes=False)
    assert keep.glyphs[0].unicode == "006f"


# --- paste routing -------------------------------------------------------------------


@pytest.fixture
def fakes(monkeypatch):
    calls = []
    monkeypatch.setattr(_edit, "_facts", lambda package: "facts")
    monkeypatch.setattr(_edit, "_current_package", lambda: "package")

    class Glyph:
        def activeLayer(self):
            return "layer"

    monkeypatch.setattr(_edit, "_current_glyph", Glyph)
    monkeypatch.setattr(
        json_data,
        "paste_glyphs",
        lambda *a, **kw: calls.append(("glyphs", a, kw)) or json_data.Pasted((), ()),
    )
    monkeypatch.setattr(
        json_data,
        "paste_shapes",
        lambda *a, **kw: calls.append(("shapes", a, kw)) or json_data.Pasted((), ()),
    )
    return calls


def test_paste_when_glyph_data_then_paste_glyphs(fakes):
    objs = fixture("glyphs_o_dcaron")
    objs.paste(on_conflict="skip")
    kind, args, kw = fakes[0]
    assert kind == "glyphs" and args[0] == "package"
    assert args[1].glyph_names() == ("o", "dcaron")
    assert kw == {"facts": "facts", "on_conflict": "skip"}


def test_paste_when_shape_data_then_paste_shapes_on_active_layer(fakes):
    vfjo.paste(fixture("element_o"), font="package")
    kind, args, kw = fakes[0]
    assert kind == "shapes" and args[0] == "layer" and args[2].kinds() == ("element",)
    assert kw == {"facts": "facts"}


def test_paste_when_empty_mixed_or_no_font_then_errors(fakes, monkeypatch):
    head = {"dataType": json_data.DATA_TYPE, "upm": 1000, "packageId": 1}
    with pytest.raises(ValueError, match="empty"):
        vfjo.paste(vfjo.loads(head))
    mixed = vfjo.loads(
        {**head, "objects": [{"glyph": {"name": "a"}}, {"contour": {"nodes": []}}]}
    )
    with pytest.raises(ValueError, match="glyphs and shapes"):
        vfjo.paste(mixed)
    monkeypatch.setattr(_edit, "_current_package", lambda: None)
    with pytest.raises(RuntimeError, match="No font"):
        vfjo.paste(fixture("glyph_o"))
    monkeypatch.setattr(_edit, "_current_package", lambda: "package")
    monkeypatch.setattr(_edit, "_current_glyph", lambda: None)
    with pytest.raises(RuntimeError, match="current glyph"):
        vfjo.paste(fixture("element_o"))
    assert fakes == []


# --- review fixes: update, lists, key conversion, shape kinds -------------------


def test_update_when_unknown_key_then_refused():
    glyph = fixture("glyph_o").data.glyph
    with pytest.raises(vfjo.UnknownKeyError):
        glyph.update({"bogus": 1})
    with pytest.raises(vfjo.UnknownKeyError):
        glyph.update(bogus=1)
    with pytest.raises(vfjo.UnknownKeyError):
        glyph |= {"bogus": 1}
    with pytest.raises(vfjo.UnknownKeyError):
        glyph.setdefault("bogus", 1)
    assert "bogus" not in glyph, "a refused key must not be stored"
    glyph.update({"name": "p"}, note="n")
    assert glyph.name == "p" and glyph.note == "n", "known keys still update"


def _layer_dict() -> dict:
    return raw("glyph_o")["glyph"]["layers"][0]


@pytest.mark.parametrize(
    ("how", "index"),
    [
        ("append", -1),
        ("extend", -1),
        ("insert", 0),
        ("setitem", 0),
        ("iadd", -1),
    ],
)
def test_list_when_item_added_then_locked_at_list_level(how, index):
    objs = fixture("glyph_o")
    layers = objs.data.glyph.layers
    item = _layer_dict()
    if how == "append":
        layers.append(item)
    elif how == "extend":
        layers.extend([item])
    elif how == "insert":
        layers.insert(0, item)
    elif how == "setitem":
        layers[0] = item
    else:
        objs.data.glyph.layers += [item]
    added = objs.data.glyph.layers[index]
    assert isinstance(added, _data._Data), f"{how}: item must become a guarded box"
    assert added.advanceWidth == 1162, f"{how}: attribute access works"
    with pytest.raises(vfjo.UnknownKeyError):
        added.advanceWidht = 1
    with pytest.raises(vfjo.UnknownKeyError):
        added.elements[0].elementData.contours[0].nodez = []
    with pytest.raises(vfjo.UnknownKeyError):
        added.anchors[0].pointt = "1 1"
    assert json.loads(objs.to_bytes())["glyph"]["layers"][index]["advanceWidth"] == 1162


def test_list_when_assigned_or_nested_append_then_locked():
    glyph = fixture("glyph_o").data.glyph
    glyph.layers = [_layer_dict()]
    with pytest.raises(vfjo.UnknownKeyError):
        glyph.layers[0].advanceWidht = 1
    glyph.layers.append(_layer_dict())
    with pytest.raises(vfjo.UnknownKeyError):
        glyph.layers[-1].advanceWidht = 1  # a list assigned to a key stays guarded
    anchors = glyph.layers[0].anchors
    anchors.append({"name": "x", "point": "1 1"})
    with pytest.raises(vfjo.UnknownKeyError):
        anchors[-1].pointt = "2 2"
    copy = vfjo.loads(fixture("glyph_o")).copy()
    copy.data.glyph.layers.append(_layer_dict())
    with pytest.raises(vfjo.UnknownKeyError):
        copy.data.glyph.layers[-1].advanceWidht = 1


def test_keys_when_dot_or_dash_then_not_converted():
    glyph = fixture("glyph_o").data.glyph
    glyph.lib = {"a-b": 1, "c.d": 2}
    assert glyph.lib["a-b"] == 1 and glyph.lib["c.d"] == 2
    with pytest.raises(AttributeError):
        glyph.lib.a_b  # noqa: B018 - the read itself must raise
    with pytest.raises(AttributeError):
        glyph.lib.c  # noqa: B018
    with pytest.raises(KeyError):
        glyph.lib["c"]


def test_paste_when_several_shape_kinds_then_value_error(fakes):
    head = {"dataType": json_data.DATA_TYPE, "upm": 1000, "packageId": 1}
    objs = vfjo.loads(
        {
            **head,
            "objects": [{"element": {"elementData": {}}}, {"contour": {"nodes": []}}],
        }
    )
    with pytest.raises(ValueError, match="more than one shape kind"):
        vfjo.paste(objs)
    assert fakes == []


# --- final review: keys of added mappings, paste(font=), re-exports -------------


@pytest.mark.parametrize(
    "how", ["append", "extend", "iadd", "insert", "setitem", "slice", "assign"]
)
def test_added_mapping_when_key_misspelt_then_refused_and_not_stored(how):
    layer = fixture("glyph_o").data.glyph.layers[0]
    before = len(layer.anchors)
    bad = {"nmae": "top", "point": "1 2"}
    with pytest.raises(vfjo.UnknownKeyError, match="nmae"):
        if how == "append":
            layer.anchors.append(bad)
        elif how == "extend":
            layer.anchors.extend([bad])
        elif how == "iadd":
            layer.anchors += [bad]
        elif how == "insert":
            layer.anchors.insert(0, bad)
        elif how == "setitem":
            layer.anchors[0] = bad
        elif how == "slice":
            layer.anchors[0:1] = [bad]
        else:
            layer.anchors = [bad]
    assert len(layer.anchors) == before, f"{how}: nothing may be stored"
    assert all("nmae" not in a for a in layer.anchors), f"{how}: typo not kept"


def test_added_mapping_when_nested_key_misspelt_then_refused():
    layer = fixture("glyph_o").data.glyph.layers[0]
    with pytest.raises(vfjo.UnknownKeyError, match="elementDatta"):
        layer.elements = [{"elementDatta": {"contours": []}}]
    with pytest.raises(vfjo.UnknownKeyError, match="nodez"):
        layer.elements.append({"elementData": {"contours": [{"nodez": []}]}})
    with pytest.raises(vfjo.UnknownKeyError, match="xOfset"):
        layer.elements[0].transform = {"xOfset": 1}
    assert "transform" not in layer.elements[0], "refused assignment is not stored"
    layer.elements.append({"elementData": {"contours": [{"nodes": ["0 0"]}]}})
    layer.hints.append({"anything": 1})  # free level stays permissive
    layer.elements.append(layer.elements[0])  # boxes from the tree are trusted
    assert len(layer.elements) == 3


def test_loaded_data_when_unknown_keys_then_still_permissive():
    data = raw("glyph_o")
    data["glyph"]["layers"][0]["futureKey"] = 1
    objs = vfjo.loads(data)
    assert objs.data.glyph.layers[0].futureKey == 1, "FontLab's own keys load as is"


def test_paste_when_shape_data_for_other_font_then_refused(fakes):
    objs = fixture("element_o")
    with pytest.raises(ValueError, match="current"):
        vfjo.paste(objs, font="other")
    assert fakes == []
    vfjo.paste(objs, font="package")
    assert fakes[0][0] == "shapes", "the current font is accepted"


def test_same_package_when_ids_match_then_true():
    class P:
        def __init__(self, ident):
            self.id = ident

    assert _edit._same_package(P(1), P(1)) and not _edit._same_package(P(1), P(2))
    assert not _edit._same_package(object(), object())


def test_reexports_when_imported_then_match_json_data():
    from fontlabapp.core.history.glyphs import PartialWriteError

    assert vfjo.available is json_data.available
    assert vfjo.NEEDS_91 == json_data.NEEDS_91
    assert vfjo.PARTIAL_TEXT == json_data.PARTIAL_TEXT
    assert vfjo.GLYPHS_UNDO_TEXT == json_data.GLYPHS_UNDO_TEXT
    assert vfjo.PartialWriteError is PartialWriteError
