# this_file: tests/test_crossfont_anchors_repair.py
"""Original int-advance and native-derived flag/insertion regressions, not host proof."""

import fontlabapp.anchors.crossfont.native as api
import pytest
from fontlabapp.anchors.crossfont.model import Options, Pin, copy_layer
from test_crossfont_anchors_native import host


@pytest.mark.parametrize(
    "source,destination,x",
    [
        (100.75, 200.75, 50),
        (-100.75, -200.75, 50),
        (0.75, 200.75, 25),
        (-0.75, -200.75, 25),
    ],
)
def test_original_integer_advance_controls_ratio_and_zero_fallback(
    source, destination, x
):
    pin = Pin(1, "top", 25, 100, (5, True, True, True, 2, "", ""))
    result = copy_layer((pin,), (), source, destination, Options(relative=True))
    assert result.pins[0].x == x
    assert result.zero_advance == (("top",) if int(source) == 0 else ())


@pytest.mark.parametrize("width", [0.75, -0.75])
def test_subunit_advance_does_not_write_clone_point_and_raw_metric_stays_captured(
    monkeypatch, width
):
    h = host(monkeypatch)
    h.source.advanceWidth = width
    h.target.advanceWidth = 200.75
    # A source-faithful fallback does not setPoint at all; a strong-rounding
    # setter can otherwise alter even a nominally identical source coordinate.
    original = type(h.source.anchors[0]).clone

    class ImmutablePointPin(type(h.source.anchors[0])):
        def __setattr__(self, name, value):
            if name == "point" and hasattr(self, "point"):
                raise AssertionError("absolute fallback must not write point")
            super().__setattr__(name, value)

    def clone(pin):
        result = original(pin)
        result.__class__ = ImmutablePointPin
        return result

    monkeypatch.setattr(type(h.source.anchors[0]), "clone", clone)
    result = api.Backend().copy(
        41, 42, "Regular", "Other", False, Options(relative=True)
    )
    assert result["zero_advance"] == (("a", "top"),)
    assert h.target.anchors[-1].point.x() == 25
    assert h.source.advanceWidth == width and h.target.advanceWidth == 200.75


@pytest.mark.parametrize("rename_destination", [False, True])
@pytest.mark.parametrize(
    "raw_cloud,raw_mark", [(True, True), (True, False), (False, False)]
)
def test_caret_rename_retains_raw_bits_and_verifies_exact_derived_metadata(
    monkeypatch, rename_destination, raw_cloud, raw_mark
):
    from test_crossfont_anchors_native import Pin as NativePin

    class CaretPin(NativePin):
        @property
        def cloudEnabled(self):
            return self.raw_cloud and self.name != "caret_1"

        @cloudEnabled.setter
        def cloudEnabled(self, v):
            self.raw_cloud = v

        @property
        def markEnabled(self):
            return self.raw_cloud and self.raw_mark and self.name != "caret_1"

        @markEnabled.setter
        def markEnabled(self, v):
            self.raw_mark = v

    h = host(monkeypatch)
    h.source.anchors = [CaretPin("caret_1")]
    h.target.anchors = [CaretPin("caret_1")]
    for pin in [*h.source.anchors, *h.target.anchors]:
        pin.raw_cloud, pin.raw_mark = raw_cloud, raw_mark
    result = api.Backend().copy(
        41,
        42,
        "Regular",
        "Other",
        False,
        Options(rename_destination=rename_destination),
    )
    assert result["anchors"] == 1 and len(h.events) == 1
    assert [pin.name for pin in h.target.anchors] == (
        ["caret_1.bak", "caret_1"] if rename_destination else ["caret_1", "caret_1.bak"]
    )
    for pin in [*h.source.anchors, *h.target.anchors]:
        assert (pin.raw_cloud, pin.raw_mark) == (raw_cloud, raw_mark)
        assert pin.cloudEnabled == (raw_cloud and pin.name != "caret_1")
        assert pin.markEnabled == (raw_cloud and raw_mark and pin.name != "caret_1")


def test_empty_suffix_collision_uses_native_normalization_before_later_collisions(
    monkeypatch,
):
    from test_crossfont_anchors_native import Pin as NativePin

    h = host(monkeypatch)
    h.source.anchors = [NativePin("top"), NativePin("top.1")]
    h.target.anchors = [NativePin("top")]
    old = h.target.addAnchor

    def native_add(pin):
        names = {p.name for p in h.target.anchors}
        name = pin.name.strip()
        base = (
            name.rsplit(".", 1)[0]
            if name.rsplit(".", 1)[-1].isdigit() and "." in name
            else name
        )
        number = int(name.rsplit(".", 1)[1]) + 1 if base != name else 1
        while name in names:
            name = f"{base}.{number}"
            number += 1
        pin.name = name
        old(pin)

    h.target.addAnchor = native_add
    result = api.Backend().copy(
        41, 42, "Regular", "Other", False, Options(rename_destination=False, suffix="")
    )
    assert result["anchors"] == 2 and [p.name for p in h.target.anchors] == [
        "top",
        "top.1",
        "top.2",
    ]
    assert [p.name for p in h.source.anchors] == ["top", "top.1"] and len(h.events) == 1


def test_unchanged_name_transform_still_refuses_cloud_corruption_before_history(
    monkeypatch,
):
    from test_crossfont_anchors_native import Pin as NativePin

    h = host(monkeypatch)
    original = NativePin.clone

    class CorruptPoint(NativePin):
        def __setattr__(self, name, value):
            if name == "point":
                self.cloudEnabled = False
                self.markEnabled = False
            super().__setattr__(name, value)

    def clone(pin):
        result = original(pin)
        result.__class__ = CorruptPoint
        return result

    monkeypatch.setattr(NativePin, "clone", clone)
    with pytest.raises(ValueError, match="metadata"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options(relative=True))
    assert h.events == [] and [p.name for p in h.target.anchors] == ["keep"]


@pytest.mark.parametrize("failure", ["add", "clear", "release"])
def test_native_name_staging_releases_all_owned_placeholders_even_on_failure(failure):
    from time import monotonic
    from types import SimpleNamespace as NS

    from fontlabapp.anchors.crossfont.names import insertion_name

    events = []
    pins = []

    class Placeholder:
        def __init__(self):
            self.name = ""
            self.index = len(pins)
            pins.append(self)

        def release(self):
            events.append(("pin", self.index))
            if failure == "release" and self.index == 0:
                raise RuntimeError("owned release")

    class Layer:
        def addAnchor(self, p):
            events.append(("add", p.name))
            if failure == "add" and len(pins) == 2:
                raise RuntimeError("owned add")

        def clearAnchors(self):
            events.append(("clear",))
            if failure == "clear":
                raise RuntimeError("owned clear")

        def release(self):
            events.append(("layer",))

    native = NS(flLayer=Layer, flPinPoint=lambda point: Placeholder())
    qt = NS(QtCore=NS(QPointF=lambda *a: a))
    with pytest.raises(RuntimeError, match="owned"):
        insertion_name("incoming", ("first", "second"), native, qt, monotonic() + 3)
    assert sorted(n for kind, *v in events if kind == "pin" for n in v) == list(
        range(len(pins))
    )
    assert ("clear",) in events and events[-1] == ("layer",)


def test_measured_native_style_string_is_retained_without_integer_coercion(monkeypatch):
    h = host(monkeypatch)
    h.source.anchors[0].style = "FreePosition"
    h.target.anchors[0].style = "FreePosition"
    result = api.Backend().copy(
        41, 42, "Regular", "Other", False, Options(relative=True)
    )
    assert result["anchors"] == 1 and len(h.events) == 1
    assert [pin.style for pin in h.target.anchors] == ["FreePosition", "FreePosition"]
    assert h.source.anchors[0].style == "FreePosition"


@pytest.mark.parametrize("style", ["FreePosition", "ShapeBound"])
def test_crossfont_source_style_change_between_capture_passes_refuses_before_history(
    monkeypatch, style
):
    h = host(monkeypatch)
    h.source.anchors[0].style = style
    original = api.read
    calls = []

    def changed(*args):
        facts = original(*args)
        calls.append(1)
        if len(calls) == 1:
            h.source.anchors[0].style = (
                "ShapeBound" if style == "FreePosition" else "FreePosition"
            )
        return facts

    monkeypatch.setattr(api, "read", changed)
    with pytest.raises(ValueError, match="changed during capture"):
        api.Backend().copy(41, 42, "Regular", "Other", False, Options())
    assert h.events == [] and [pin.name for pin in h.target.anchors] == ["keep"]
