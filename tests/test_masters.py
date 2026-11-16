# this_file: tests/test_masters.py
"""Read-only master geometry and structural contracts, without native imports."""

from itertools import pairwise
from types import SimpleNamespace as NS

import pytest


def api():
    from importlib import import_module

    return import_module("fontlabapp.masters.inspect.model")


def test_width_zero_missing_and_master_order():
    m = api()
    glyph = NS(findLayer=lambda n: {"A": NS(isNull=False, advanceWidth=0)}.get(n))
    assert m.widths(glyph, ["A", "B"]) == [("A", 0.0), ("B", None)]
    p = NS(
        masters=["B", "A"],
        axes=[NS(shortName="wt")],
        location=lambda n: {"wt": {"A": 0, "B": 1}[n]},
    )
    assert m.master_order(p) == ["A", "B"]


def test_ink_area_nested_and_empty():
    m = api()
    square = lambda a, b: [(a, a, True), (b, a, True), (b, b, True), (a, b, True)]
    assert m.ink_area([square(0, 10), square(2, 8), square(4, 6)]) == 68
    assert m.ink_area([[], [(0, 0, True)]]) == 0


def test_signature_ignores_component_contours_and_auto_missing_semantics():
    m = api()
    c = NS(nodes=lambda: [NS(x=0, y=0, isOn=lambda: True)])
    own = NS(isComponent=False, contours=[c])
    component = NS(isComponent=True, contours=[c, c], shapeData=NS(componentGlyph="A"))
    l = NS(
        isNull=False, autoLayer=False, shapes=[own, component], anchors=[NS(name="top")]
    )
    assert m.signature(l) == (("o",), ("top",), ("A",))
    auto = NS(isNull=False, autoLayer=True)
    g = NS(findLayer=lambda n: {"A": l, "B": auto}.get(n))
    assert m.check_glyph(g, ["A", "B"])[1]
    assert m.check_glyph(g, ["A", "B", "C"])[2] == ["missing layer"]


@pytest.mark.parametrize(
    "low,high", [(0, 0), (500, 500), (-500, -500), (1e300, 1e300), (-1000, 1000)]
)
def test_ticks_are_bounded_for_constant_negative_and_huge_native_widths(low, high):
    ticks = api().nice_ticks(low, high)
    assert 1 <= len(ticks) <= 8
    assert all(a < b for a, b in pairwise(ticks))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_chart_ranges_are_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        api().nice_ticks(value, value)


def test_cubic_flattening_keeps_original_twelve_steps_and_rotated_start():
    points = [(0, 0, True), (0, 10, False), (10, 10, False), (10, 0, True)]
    poly = api().polygon(points)
    assert len(poly) == 14 and poly[-1] == (0, 0)
    assert poly[6] == (5.0, 7.5)
    assert api().polygon(points[1:] + points[:1]) == api().polygon(
        points[3:] + points[:3]
    )


def test_transformed_component_area_keeps_linear_determinant(monkeypatch):
    import fontlabapp.masters.inspect.model as m

    class Point:
        def __init__(self, x, y):
            self.a, self.b = x, y

        def x(self):
            return self.a

        def y(self):
            return self.b

    monkeypatch.setattr(m, "_native", lambda name: NS(QtCore=NS(QPointF=Point)))
    contour = NS(
        nodes=lambda: [
            NS(x=x, y=y, isOn=lambda: True)
            for x, y in [(0, 0), (10, 0), (10, 10), (0, 10)]
        ]
    )
    transform = NS(
        isIdentity=lambda: False,
        map=lambda p: Point(2 * p.x() + p.y() + 100, 3 * p.y() - 20),
    )
    layer = NS(shapes=[NS(contours=[contour], isComponent=True, transform=transform)])
    assert m.ink_area(m.layer_contours(layer)) == 600


def test_italic_angle_failure_restores_original_master():
    class Package:
        master = "B"

        def setMaster(self, m):
            self.master = m

        @property
        def italicAngle_value(self):
            if self.master == "A":
                raise RuntimeError("angle unavailable")
            return -10

    p = Package()
    with pytest.raises(RuntimeError, match="angle"):
        api().italic_angles(p, ["B", "A"])
    assert p.master == "B"


def test_signature_compares_pattern_not_just_counts_and_component_order():
    m = api()

    def layer(pattern, bases):
        contour = NS(
            nodes=lambda: [NS(x=0, y=0, isOn=lambda on=on: on) for on in pattern]
        )
        shapes = [NS(isComponent=False, contours=[contour])] + [
            NS(isComponent=True, shapeData=NS(componentGlyph=n)) for n in bases
        ]
        return NS(isNull=False, autoLayer=False, shapes=shapes, anchors=[])

    layers = {
        "A": layer([True, False], ["A", "B"]),
        "B": layer([False, True], ["B", "A"]),
    }
    assert m.check_glyph(NS(findLayer=layers.get), ["A", "B"])[2] == [
        "contours",
        "components",
    ]
    assert m.summary(m.signature(layers["A"])) == (1, 2, 0, 2)


def test_no_axes_and_unavailable_axis_position_keep_original_order_fallback():
    m = api()
    p = NS(masters=["B", "A"], axes=[])
    assert (
        m.master_order(p) == ["B", "A"]
        and m.location_text(NS(axes=[], location=lambda m: {}), "A") == "–"
    )
    p.axes = [NS(shortName="wght")]
    p.location = lambda name: {}
    assert m.master_order(p) == ["B", "A"]
    assert m.spread([0, 0, 2], 5) == [0, 5, 10]
    assert m.label_tops([0, 0, 20], 16) == [-20, 6, 26]


def test_shared_masters_api_import_stays_host_free_in_fresh_interpreter():
    import subprocess
    import sys

    code = "import sys; from fontlabapp.core.scripting import masters_api; m=masters_api(); assert m.STEPS==12; assert not {'fontlab','PythonQt','FL'} & set(sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def shared_masters_dialog(monkeypatch):
    """Load actual shared refresh/invalidation methods without a Qt binary."""
    import importlib.util
    import sys
    from pathlib import Path

    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.proof.inspect.ui",
        NS(ProofDialog=object, QtCore=NS(), QtGui=NS()),
    )
    path = Path(__file__).parents[1] / "src/fontlabapp/masters/inspect/ui.py"
    spec = importlib.util.spec_from_file_location("fontlabapp.masters.inspect.ui", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "fontlabapp.masters.inspect.ui", module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("during", [None, "masters", "master"])
def test_review_shared_refresh_binds_one_actual_master_domain(
    shared_masters_dialog, during
):
    shared = shared_masters_dialog
    package = NS(masters=["Bold", "Light", "New"], master="Bold")
    panel = NS(
        package=package,
        masters=["Bold", "Light"],
        current_master="Bold",
        prepare_initial=lambda: None,
        check_binding=lambda: None,
        source_values=lambda **kwargs: None,
        invalid=False,
        _bound_id=7,
    )
    panel.invalidate = lambda: setattr(panel, "invalid", True)

    def scan(self):
        assert self.masters == package.masters, "Scan used an old master domain"
        if during == "masters":
            package.masters.append("Late")
        elif during == "master":
            package.master = "Light"

    refresh = shared.snapshot_refresh(scan)
    if during is None:
        refresh(panel)
        assert panel._display_masters == ("Bold", "Light", "New")
    else:
        with pytest.raises(ValueError, match="changed"):
            refresh(panel)
        assert panel.invalid, "Changing domains must invalidate partial results"


@pytest.mark.parametrize("change", ["insert", "delete", "reorder"])
def test_review_shared_source_rechecks_whole_font_order(
    shared_masters_dialog, monkeypatch, change
):
    shared = shared_masters_dialog
    names = ["H", "O", "n"]
    panel = shared.MastersDialog.__new__(shared.MastersDialog)
    panel.package = NS(findName=lambda name: name)
    panel._key = "masters_compatibility_check"
    panel.source = NS(currentIndex=1)
    panel.masters = ["Bold", "Light"]
    panel._structures = {name: {} for name in names}
    panel._scope_names, panel._scope_whole = tuple(names), True
    monkeypatch.setattr(shared, "all_names", lambda: names)
    monkeypatch.setattr(
        shared,
        "check_glyph",
        lambda *args: pytest.fail(
            "Read tracked signatures before rejecting changed membership"
        ),
    )
    if change == "insert":
        names.append("New")
    elif change == "delete":
        names.pop()
    else:
        names.reverse()
    with pytest.raises(ValueError, match="changed"):
        panel.source_values()


@pytest.mark.parametrize("populated", [False, True])
def test_review_shared_invalidation_requests_only_one_clear_repaint(
    shared_masters_dialog, populated
):
    shared = shared_masters_dialog
    panel = shared.MastersDialog.__new__(shared.MastersDialog)
    calls = []
    panel.chart = NS(
        masters=["Bold"] if populated else [],
        series=[("H", [100])] if populated else [],
        update=lambda: calls.append("paint"),
    )
    panel.invalidate()
    panel.invalidate()
    assert calls == (["paint"] if populated else []), (
        "Repeated invalidation scheduled another paint"
    )


@pytest.mark.parametrize(
    "low,high",
    [
        (494, 713),
        (499, 713),
        (0, 713),
        (-713, -494),
        (-713, 494),
        (0, 0),
        (500, 500),
        (-500, -500),
        (1e300, 1e300),
        (-1e300, -1e300),
        (1e300, 1.4e300),
        (-1.4e300, -1e300),
        (1e-300, 2e-300),
    ],
)
def test_fix2_ticks_cover_both_finite_endpoints_with_nonzero_axis(low, high):
    import math

    ticks = api().nice_ticks(low, high)
    assert 2 <= len(ticks) <= 8, (
        "A constant range needs two distinct finite axis endpoints"
    )
    assert all(math.isfinite(tick) for tick in ticks)
    assert all(a < b for a, b in pairwise(ticks))
    assert ticks[0] <= low <= high <= ticks[-1], f"Axis {ticks} clips {low}..{high}"


def test_fix2_native_range_keeps_original_nice_step_selection():
    assert api().nice_ticks(494, 713) == [450, 500, 550, 600, 650, 700, 750]
    assert api().nice_ticks(499, 713) == [450, 500, 550, 600, 650, 700, 750]
    assert api().nice_ticks(0, 713) == [0, 200, 400, 600, 800]


# --- issue 122 T14b: associated_master (flLayer::isMasterLayerName rule) -----


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Regular", "Regular"),
        ("Regular@ 2026-10-21", "Regular"),
        ("Regular#bracket", "Regular"),
        ("Regular@a#b", "Regular"),
        ("|temp|Bold@x", "Bold"),
        ("Light Copy", None),
        ("mask.Regular", None),
        ("@Regular", None),
        ("", None),
    ],
)
def test_associated_master_when_layer_named_then_master_before_at_or_hash(name, expected):
    assert api().associated_master(name, ["Regular", "Bold"]) == expected



@pytest.mark.parametrize("name,masters,expected", [
    ("Bold", ["Bold", "Bold Italic"], None),
    ("Bold Italic", ["Bold", "Bold Italic"], None),
    ("BOLD ITALIC", ["Bold", "Bold Italic"], None),
    ("Bold Italic backup x", ["Bold", "Bold Italic"], "Bold Italic"),
    ("Bold backup x", ["Bold", "Bold Italic"], "Bold"),
    ("bold italic backup x", ["Bold", "Bold Italic"], None),
    ("regular sketch", ["Regular"], None),
    ("BOLD backup x", ["Bold", "BOLD"], "BOLD"),
    ("Bold backup x", ["Bold", "BOLD"], "Bold"),
    ("Bold backup x", ["Bold", "Bold backup x"], None),
    ("Bold backup x extra", ["Bold", "Bold backup x"], "Bold backup x"),
    ("Bold backup |temp| x", ["Bold"], None),
    ("Bold backup |TEMP| x", ["Bold"], "Bold"),
    ("Bold#bracket", ["Bold"], None),
    ("Bold@ old", ["Bold", "Bold Italic"], "Bold"),
    ("bold italic@ old", ["Bold", "Bold Italic"], None),
    ("Unknown@ old", ["Bold"], None),
    ("Boldness copy", ["Bold"], None),
    ("", ["Bold"], None),
])
def test_backup_master_when_copy_cases_then_resolves_longest_master(name, masters, expected):
    assert api().backup_master(name, masters) == expected
    for master in masters:
        assert api().is_backup_layer(name, master, masters) == (expected == master)


@pytest.mark.parametrize("taken,expected", [
    ([], "Bold backup x"),
    (["BOLD BACKUP X"], "Bold backup x (2)"),
    (["Bold backup x", "bold backup x (2)"], "Bold backup x (3)"),
])
def test_backup_name_when_copy_collisions_then_suffix_and_number_preserved(taken, expected):
    assert api().backup_layer_name("Bold", iter(taken), " x ", ["Bold", "Bold Italic"]) == expected


@pytest.mark.parametrize("base,suffix,masters,message", [
    ("Bold", "", ["Bold"], "suffix"),
    ("Bold", "  ", ["Bold"], "suffix"),
    ("Bold", "x@y", ["Bold"], "must not contain"),
    ("Bold", "x#y", ["Bold"], "must not contain"),
    ("Bold", "x|temp|y", ["Bold"], "must not contain"),
    ("Bold", "x|TEMP|y", ["Bold"], "must not contain"),
    ("Bold", "x", ["Bold", "Bold backup x"], "master name"),
    ("Bold", "x", ["Bold", "Bold backup"], "would read as master"),
    ("Missing", "x", ["Bold"], "would read as master"),
])
def test_backup_name_when_copy_refusals_then_readable_error(base, suffix, masters, message):
    with pytest.raises(ValueError, match=message):
        api().backup_layer_name(base, [], suffix, masters)


def test_default_suffix_when_given_datetime_then_matches_script_timestamp():
    from datetime import datetime
    assert api().STAMP_FORMAT == "%H:%M:%S, %d/%m/%y"
    assert api().default_suffix(datetime(2026, 10, 22, 8, 9, 10)) == "08:09:10, 22/10/26"
