# this_file: tests/test_guides_geometry.py
# SPDX-License-Identifier: Apache-2.0
"""Original guide coordinates, native flags and grid records."""

from importlib import import_module

import pytest


@pytest.fixture
def api():
    return import_module("fontlabapp.guides.inspect.model")


@pytest.mark.parametrize(
    "direction,expected",
    [
        (
            0,
            [
                (0.0, -10.0, 0.0, "Grid H 1"),
                (-10.0, 0.0, 90.0, "Grid V 1"),
                (0.0, 15.0, 0.0, "Grid H 2"),
                (15.0, 0.0, 90.0, "Grid V 2"),
            ],
        ),
        (1, [(0.0, -10.0, 0.0, "Grid H 1"), (0.0, 15.0, 0.0, "Grid H 2")]),
        (2, [(-10.0, 0.0, 90.0, "Grid V 1"), (15.0, 0.0, 90.0, "Grid V 2")]),
    ],
)
def test_grid_keeps_original_direction_order_names_and_coordinates(
    api, direction, expected
):
    assert api.grid(direction, -10, 25, 2) == expected
    assert api.grid(direction, 0, 10, 0) == []


def test_guide_records_convert_radians_and_filter_hints(api):
    import math
    from types import SimpleNamespace as NS

    def guide(angle, x, y, name):
        return NS(
            angle=angle,
            centerPoint=NS(x=lambda: x, y=lambda: y),
            name=name,
            isHint=False,
        )

    h = guide(0, 24, 123, "H")
    v = guide(math.pi / 2, 345, 88, "V")
    a = guide(math.radians(33.5), -20, 30, "angle")
    assert api.guide_record(h) == (0.0, 123, 0.0, "H")
    assert api.guide_record(v) == (345, 0.0, 90.0, "V")
    assert api.guide_record(a) == (-20, 30, 33.5, "angle")
    assert api.glyph_guides(NS(guidelines=[h, NS(isHint=True), v, a])) == [h, v, a]


def test_new_guide_uses_native_line_flags_and_rejects_nonfinite_values(
    api, monkeypatch
):
    import math
    from types import SimpleNamespace as NS

    created = []

    def constructor(line, flags, style):
        result = NS(line=line, flags=flags, style=style, name="")
        created.append(result)
        return result

    core = NS(QLineF=lambda *args: args)
    native = NS(flGuideLine=constructor)
    monkeypatch.setattr(
        api, "_native", lambda name: NS(QtCore=core) if name == "PythonQt" else native
    )
    h = api.new_guide((0.0, 123.0, 0.0, "H"))
    v = api.new_guide((345.0, 0.0, 90.0, "V"))
    a = api.new_guide((-20.0, 30.0, 33.5, "angle"))
    assert (h.line, h.flags, h.style, h.name) == (
        (0.0, 123.0, 100.0, 123.0),
        0x2000,
        0x102,
        "H",
    )
    assert v.line == (345.0, 0.0, 345.0, 100.0) and v.flags == 0x4000
    assert a.flags == 0x1000 and a.line[2:] == pytest.approx(
        (
            -20 + 100 * math.cos(math.radians(33.5)),
            30 + 100 * math.sin(math.radians(33.5)),
        )
    )
    with pytest.raises(ValueError, match="finite"):
        api.new_guide((float("nan"), 0.0, 0.0, "bad"))
    assert len(created) == 3
