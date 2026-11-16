# this_file: tests/test_near_miss_native.py
"""Native-shaped full capture with unused-layer/master and mutation tripwires."""

from time import monotonic
from types import SimpleNamespace as S

import pytest

import fontlabapp.contours.near_miss.native as n


def fixture(monkeypatch):
    package = S(id=1, fgId=11, master="Bold", isNull=False)
    point = lambda x, y: S(x=lambda: x, y=lambda: y)
    nodes = [
        S(
            id=i,
            isNull=False,
            isOn=lambda: True,
            isOff=lambda: False,
            isCurve=lambda: False,
            position=point(x, y),
        )
        for i, (x, y) in enumerate([(0, 0), (101, 1)])
    ]
    contour = S(id=3, closed=False, isTT=False, nodes=lambda: nodes)
    transform = S(
        map=lambda p: p,
        **{
            f"m{i}{j}": lambda i=i, j=j: int(i == j)
            for i in (1, 2, 3)
            for j in (1, 2, 3)
        },
    )
    shape = S(
        id=4,
        isComponent=False,
        isComposite=False,
        transform=transform,
        contours=[contour],
    )
    glyph = S(id=2, fgGlyphId=22, name="a", package=package, isNull=False)
    layer = S(
        id=5, name="Regular", glyph=glyph, isNull=False, isValid=True, shapes=[shape]
    )
    glyph.layers = [layer, S()]
    package.findName = lambda name: glyph
    document = S(
        context=(1, "Bold", "font", 3), package=package, carriers=(), blocks=()
    )
    monkeypatch.setattr(n.selection, "_document", lambda deadline: document)
    monkeypatch.setattr(
        n.selection, "document_context", lambda deadline: document.context
    )
    monkeypatch.setattr(
        n.selection, "names_font_window_selection", lambda **kw: ["a", "a"]
    )
    data = {
        "masters": [
            {
                "fontMaster": {
                    "name": "Regular",
                    "ascender": 800,
                    "capsHeight": 700,
                    "xHeight": 500,
                    "descender": -200,
                    "fontStemsH": [{"value": 100}],
                    "fontStemsV": [{"value": 200}],
                }
            },
            {"fontMaster": {"name": "Bold", "fontStemsH": "UNUSED"}},
        ]
    }
    calls = []

    def native(name):
        assert name == "fontpr"

        def call(tool, **args):
            assert tool == "get_font_info" and args == {"font_id": 11}, "fontpr finds fonts by fgId"
            calls.append(tool)
            return data

        return S(call=call)

    monkeypatch.setattr(n, "_native", native)
    return S(
        package=package,
        glyph=glyph,
        layer=layer,
        shape=shape,
        contour=contour,
        nodes=nodes,
        data=data,
        document=document,
        calls=calls,
    )


def test_every_occurrence_uses_literal_first_layer_associated_master(monkeypatch):
    f = fixture(monkeypatch)
    rows = n.capture()
    assert len(rows) == 2 and all(
        r.master == "Regular" and r.horizontal == (100,) and r.vertical == (200,)
        for r in rows
    )
    assert (
        rows[0].metrics == (800, 700, 500, -200)
        and f.package.master == "Bold"
        and len(f.calls) == 2
    )
    assert rows[0].paths[0][1].point == (101, 1)


def test_editor_parent_order_does_not_read_selected_symbol_or_layer(monkeypatch):
    f = fixture(monkeypatch)

    class Info:
        isSelected = True
        isActive = False
        glyph = f.glyph

        @property
        def symbol(self):
            raise AssertionError("unneeded symbol read")

    f.document.context = (1, "Bold", "editor", 9)
    f.document.blocks = (
        S(id=8, glyphsCount=lambda: 3, getGlyphAt=lambda i: None if i == 0 else Info()),
    )
    assert len(n.capture()) == 2


@pytest.mark.parametrize(
    "mode",
    [
        "empty",
        "foreign",
        "no layers",
        "bad layer",
        "missing master",
        "duplicate master",
        "bad stems",
        "bad number",
        "shape role",
        "generated",
        "projective",
        "topology",
        "null node",
        "node role",
        "quadratic",
    ],
)
def test_bad_selected_source_refuses_whole_snapshot(monkeypatch, mode):
    f = fixture(monkeypatch)
    if mode == "empty":
        monkeypatch.setattr(n.selection, "names_font_window_selection", lambda **kw: [])
    elif mode == "foreign":
        f.glyph.package = S(id=999)
    elif mode == "no layers":
        f.glyph.layers = []
    elif mode == "bad layer":
        f.layer.isValid = False
    elif mode == "missing master":
        f.layer.name = "Unknown"
    elif mode == "duplicate master":
        f.data["masters"].append(f.data["masters"][0])
    elif mode == "bad stems":
        f.data["masters"][0]["fontMaster"]["fontStemsH"] = "bad"
    elif mode == "bad number":
        f.nodes[0].position = S(x=lambda: float("nan"), y=lambda: 0)
    elif mode == "shape role":
        f.shape.isComponent = 1
    elif mode == "generated":
        f.shape.isComposite = True
    elif mode == "projective":
        f.shape.transform.m13 = lambda: 1
    elif mode == "topology":
        f.contour.closed = 1
    elif mode == "null node":
        f.nodes[0].isNull = True
    elif mode == "node role":
        f.nodes[0].isOff = lambda: True
    elif mode == "quadratic":
        f.nodes[0].isOn = lambda: False
        f.nodes[0].isOff = lambda: True
    with pytest.raises((ValueError, TypeError)):
        n.capture()


def test_empty_components_closed_rotation_and_named_auxiliary_master(monkeypatch):
    f = fixture(monkeypatch)
    f.shape.contours.append(S(id=55, closed=False, isTT=False, nodes=list))
    f.layer.shapes.append(S(id=44, isComponent=True))
    f.layer.name = "Regular#mask"
    f.contour.closed = True
    rows = n.capture()
    assert (
        rows[0].master == "Regular"
        and rows[0].paths[0][0].point == (101, 1)
        and rows[0].paths[1] == ()
    )


def test_changed_geometry_selection_or_context_refuses(monkeypatch):
    f = fixture(monkeypatch)
    old = n._read
    calls = []

    def changing(*args):
        result = old(*args)
        calls.append(True)
        if len(calls) == 1:
            f.layer.name = "Regular#mask"
        return result

    monkeypatch.setattr(n, "_read", changing)
    with pytest.raises(ValueError, match="changed"):
        n.capture()
    with pytest.raises(TimeoutError):
        n._parents(monotonic() - 1)


def test_true_type_two_controls_never_masquerade_as_cubic(monkeypatch):
    f = fixture(monkeypatch)
    f.contour.isTT = True

    def node(i, x, off):
        return S(
            id=i,
            isNull=False,
            isOn=lambda: not off,
            isOff=lambda: off,
            isCurve=lambda: False,
            position=S(x=lambda: x, y=lambda: 1),
        )

    f.nodes[:] = [
        node(0, 0, False),
        node(1, 20, True),
        node(2, 80, True),
        node(3, 100, False),
    ]
    with pytest.raises(ValueError, match="Quadratic"):
        n.capture()
