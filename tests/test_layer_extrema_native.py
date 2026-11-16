# this_file: tests/test_layer_extrema_native.py
"""Owned raw-bound/master/domain controls, without native FontLab or corpus code."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.masters.layers.extrema.native as api
from fontlabapp.masters.layers.extrema.model import choose


class Package(NS):
    """Native shape: no flPackage glyph list; fgPackage.glyphs orders, findName resolves.

    glyphs is write-only test setup: reading it raises AttributeError, as in FontLab.
    """

    glyphs = property(None, lambda self, value: setattr(self, "_glyphs", value))

    @property
    def fgPackage(self):
        return NS(glyphs=[NS(name=g.name) for g in self._glyphs])

    def findName(self, name):
        return next((g for g in self._glyphs if g.name == name), None)


class Box:
    def __init__(self, bottom, top):
        self.values = [0, bottom, 100, top - bottom]

    def x(self):
        return self.values[0]

    def y(self):
        return self.values[1]

    def width(self):
        return self.values[2]

    def height(self):
        return self.values[3]


class Layer:
    def __init__(self, identifier, name, bottom, top, master=True):
        self.id, self.name = identifier, name
        self.isNull, self.isValid = False, True
        self.isMasterLayer, self.isMaskLayer, self.isService = master, False, False
        self.box = Box(bottom, top)
        self.state = None

    @property
    def boundingBox(self):
        if self.isMaskLayer or self.isService:
            pytest.fail("Do not inspect background/cache bounds")
        self.state.reads += 1
        if self.state.during:
            self.state.during(self)
        return self.box


class Glyph:
    def __init__(self, identifier, name, package, layers):
        self.id, self.name, self.package = identifier, name, package
        self.layers, self.isNull, self.find_calls = layers, False, []
        for layer in layers:
            layer.glyph = self

    def findLayer(self, name):
        self.find_calls.append(name)
        return next((layer for layer in self.layers if layer.name == name), None)


@pytest.fixture
def host(monkeypatch):
    state = NS(current=True, seconds=0, reads=0, during=None)
    package = Package(id=31, master="Regular", masters=("Thin", "Regular"), glyphs=[])
    layers = [
        Layer(1, "Thin", -20, 700),
        Layer(2, "Regular", 0, 500),
        Layer(3, "Sketch", -100, 100, False),
        Layer(4, "mask", -9999, 9999, False),
        Layer(5, "cache", -9999, 9999, False),
    ]
    layers[3].isMaskLayer = True
    layers[4].isService = True
    for layer in layers:
        layer.state = state
    other = [
        Layer(6, "Thin", 0, 650),
        Layer(7, "Regular", -30, 600),
        Layer(8, "Sketch", 100, 1000, False),
    ]
    for layer in other:
        layer.state = state
    package.glyphs = [
        Glyph(10, "a", package, [layers[i] for i in (2, 1, 3, 0, 4)]),
        Glyph(11, "b", package, other),
    ]
    monkeypatch.setattr(
        api,
        "current_package",
        lambda expected_id=None: package if state.current else None,
    )
    monkeypatch.setattr(api, "monotonic", lambda: state.seconds)
    return package, state, layers


def test_current_and_all_foreground_scopes_preserve_order_and_exact_layers(host):
    package, _state, layers = host
    current = api.capture("current")
    assert choose(current.rows).layers == (("b", "Regular"), ("b", "Regular"))
    assert [g.find_calls for g in package._glyphs] == [
        ["Regular", "Regular"],
        ["Regular", "Regular"],
    ]
    all_layers = api.capture("all")
    assert tuple((row.glyph, row.layer) for row in all_layers.rows) == (
        ("a", "Thin"),
        ("a", "Regular"),
        ("a", "Sketch"),
        ("b", "Thin"),
        ("b", "Regular"),
        ("b", "Sketch"),
    )
    assert choose(all_layers.rows).layers == (("b", "Sketch"), ("a", "Sketch"))
    assert len(all_layers.domain[0][2]) == 5 and all_layers.domain[0][2][2][-1] is None
    assert package.master == "Regular" and layers[0].box.values == [0, -20, 100, 720]


@pytest.mark.parametrize("fault", ["id", "masters", "master", "no_font", "mode"])
def test_bad_font_domain_rejects_before_any_bound_read(host, fault):
    p, state, _ = host
    if fault == "id":
        p.id = True
    elif fault == "masters":
        p.masters = ("Regular", "Regular")
    elif fault == "master":
        p.master = "missing"
    elif fault == "no_font":
        state.current = False
    with pytest.raises(ValueError):
        api.capture("unknown" if fault == "mode" else "all")
    assert state.reads == 0


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "invalid",
        "null",
        "role",
        "duplicate_id",
        "duplicate_name",
        "unmapped",
        "nonmaster",
        "negative_height",
        "nonfinite",
        "bad_name",
    ],
)
def test_bad_complete_layer_domain_has_no_snapshot(host, fault):
    p, _, layers = host
    if fault == "missing":
        p._glyphs[0].layers.remove(layers[0])
    elif fault == "invalid":
        layers[0].isValid = False
    elif fault == "null":
        layers[0].isNull = True
    elif fault == "role":
        layers[0].isMasterLayer = lambda: True
    elif fault == "duplicate_id":
        layers[0].id = layers[1].id
    elif fault == "duplicate_name":
        layers[2].name = "Regular"
    elif fault == "unmapped":
        layers[0].name = "alien"
    elif fault == "nonmaster":
        layers[0].isMasterLayer = False
    elif fault == "negative_height":
        layers[0].box.values[3] = -1
    elif fault == "nonfinite":
        layers[0].box.values[1] = float("nan")
    elif fault == "bad_name":
        layers[0].name = None
    with pytest.raises(ValueError):
        api.capture("all")
