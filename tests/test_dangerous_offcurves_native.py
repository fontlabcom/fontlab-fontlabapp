# this_file: tests/test_dangerous_offcurves_native.py
"""Whole-font domain and identity fences with native-shaped owned objects."""

from types import SimpleNamespace as NS

import fontlabapp.contours.dangerous_offcurves.model as model
import fontlabapp.contours.dangerous_offcurves.native as api
import pytest


class Point:
    def __init__(self, x, y):
        self.coords = x, y

    def x(self):
        return self.coords[0]

    def y(self):
        return self.coords[1]


class Transform:
    def __getattr__(self, name):
        if name.startswith("m"):
            return lambda: 1 if name[1] == name[2] else 0
        raise AttributeError(name)

    def map(self, point):
        return Point(point.x() + 10, point.y() + 20)


class Node:
    isNull = False

    def __init__(self, identity, x, y, off=False):
        self.id, self.position, self.off = identity, Point(x, y), off

    def isOn(self):
        return not self.off

    def isOff(self):
        return False

    def isCurve(self):
        return self.off


def fixture(monkeypatch):
    package = NS(id=1)
    nodes = [Node(1, 0, 0), Node(2, 1, 1, True), Node(3, 2, 2, True), Node(4, 3, 3)]
    contour = NS(id=20, closed=False, isTT=False, nodes=lambda: nodes)
    shape = NS(id=30, isComponent=False, transform=Transform(), contours=[contour])
    glyphs = []
    for gid, name in ((100, "A"), (200, "B")):
        glyph = NS(
            id=gid,
            fgGlyphId=gid + 1,
            package=package,
            name=name,
            isNull=False,
            isValid=True,
        )
        glyph.layers = [
            NS(
                id=gid + i,
                name=layer,
                glyph=glyph,
                isNull=False,
                isValid=True,
                isMaskLayer=mask,
                isService=False,
                shapes=[shape] if i == 1 else [],
            )
            for i, layer, mask in (
                (1, "Regular", False),
                (2, "Aux", False),
                (3, "Mask", True),
            )
        ]
        glyph.findLayer = lambda name, g=glyph: next(
            (l for l in g.layers if l.name == name), None
        )
        glyphs.append(glyph)
    package.findFgId = lambda fid: next((g for g in glyphs if g.fgGlyphId == fid), None)
    package.findName = lambda name: next((g for g in glyphs if g.name == name), None)
    font = NS(glyphs=[NS(id=g.fgGlyphId, name=g.name) for g in glyphs])
    monkeypatch.setattr(
        api.source, "_current", lambda d: ((1, 2, "Regular"), package, font)
    )
    calls = []
    monkeypatch.setattr(
        api.tabs, "open_layer_tab", lambda *a, **kw: calls.append((a, kw))
    )
    return package, glyphs, nodes, shape, calls


def test_full_font_empty_auxiliary_and_transformed_own_paths(monkeypatch):
    _package, _glyphs, _nodes, _shape, calls = fixture(monkeypatch)
    captured = api.capture(float("inf"))
    assert [(r.glyph, r.name) for r in captured.layers] == [
        ("A", "Regular"),
        ("A", "Aux"),
        ("B", "Regular"),
        ("B", "Aux"),
    ]
    assert captured.layers[0].paths[0][0] == model.Node(10, 20, False)
    monkeypatch.setattr(model, "dangerous", lambda *a, **kw: True)
    result = api.run(deadline=float("inf"))
    assert result.layers == ((100, 101), (200, 201))
    assert calls == [
        (
            ((("A", "Regular"), ("B", "Regular")),),
            {"expected_id": 1, "master": "Regular", "deadline": float("inf")},
        )
    ]


def test_components_are_not_decomposed_and_no_findings_create_no_tab(monkeypatch):
    _, _glyphs, _, shape, calls = fixture(monkeypatch)
    shape.isComponent = True
    del shape.contours
    assert not api.run(deadline=float("inf")).layers
    assert calls == []


@pytest.mark.parametrize(
    "defect", ["owner", "role", "nonfinite", "projective", "null", "duplicate"]
)
def test_unreadable_full_font_domain_never_opens_partial_tab(monkeypatch, defect):
    _, glyphs, nodes, shape, calls = fixture(monkeypatch)
    if defect == "owner":
        glyphs[-1].layers[0].glyph = NS(id=999)
    elif defect == "role":
        glyphs[-1].layers[0].isService = 0
    elif defect == "nonfinite":
        nodes[0].position = Point(float("nan"), 0)
    elif defect == "projective":
        shape.transform.m13 = lambda: 1
    elif defect == "null":
        nodes[0].isNull = True
    else:
        glyphs[-1].layers.append(glyphs[-1].layers[0])
    with pytest.raises(ValueError):
        api.run(deadline=float("inf"))
    assert calls == []


def test_stale_geometry_is_rejected_by_second_complete_read(monkeypatch):
    _, _, _nodes, shape, calls = fixture(monkeypatch)
    n = [0]

    def changing(point):
        n[0] += 1
        return Point(point.x() + n[0], point.y())

    shape.transform.map = changing
    with pytest.raises(ValueError, match="changed"):
        api.capture(float("inf"))
    assert calls == []


def test_winning_unaddressable_name_is_not_silently_dropped(monkeypatch):
    _, glyphs, _, _, calls = fixture(monkeypatch)
    glyphs[0].layers[0].name = ""
    monkeypatch.setattr(model, "dangerous", lambda *a, **kw: True)
    with pytest.raises(ValueError, match="addressable"):
        api.run(deadline=float("inf"))
    assert calls == []


def test_closed_rotation_and_generated_contour_domain_are_preserved(monkeypatch):
    _, _, _, shape, _ = fixture(monkeypatch)
    shape.isComposite = True
    shape.contours[0].closed = True
    rows = api.capture(float("inf")).layers
    assert [n.off for n in rows[0].paths[0]] == [True, True, False, False]
    assert rows[0].paths[0][-1] == model.Node(10, 20, False)
