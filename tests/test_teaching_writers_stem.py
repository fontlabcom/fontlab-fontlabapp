# this_file: tests/test_teaching_writers_stem.py
"""Behaviour of the stem-blend and stem-compensation writers' pure algorithms."""

import importlib

import pytest

NAMES = ("stem_blend", "scale_with_stem_compensation")


def load(name):
    return importlib.import_module(f"fontlabapp.fontui.teaching_writers.{name}")


def square(shift=0.0, closed=True):
    pts = [(0.0 + shift, 0.0, True), (100.0 + shift, 0.0, True), (100.0 + shift, 100.0, True), (0.0 + shift, 100.0, True)]
    return (closed, pts, False)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    ("wanted", "got", "ok"),
    [(5.5, 5.8, False), (5.4, 6.0, False), (10.0, 11.0, False), (5.5, 5.0, True), (5.5, 6.0, True), (5.5, 5.5, True), (5.4, 5.0, True)],
)
def test_stored_when_native_snaps_to_integer_then_only_half_unit_accepted(name, wanted, got, ok):
    assert load(name)._stored(got, wanted) is ok


@pytest.mark.parametrize("name", NAMES)
def test_stored_outline_matches_when_shapes_differ_then_false(name):
    mod = load(name)
    base = [square()]
    assert mod.stored_outline_matches(base, [square()])
    assert not mod.stored_outline_matches(base, [square(2.0)])
    assert not mod.stored_outline_matches(base, [square(), square()])
    assert not mod.stored_outline_matches(base, [square(closed=False)])


STEMS = (10.0, 20.0, 30.0, 40.0)


@pytest.mark.parametrize("name", NAMES)
def test_blend_contours_when_target_at_ends_then_returns_sources_and_midpoint(name):
    mod = load(name)
    a, b = [square()], [square(40.0)]
    first = mod.blend_contours(a, b, STEMS, (10.0, 30.0), (1.0, 1.0), 0.0)
    last = mod.blend_contours(a, b, STEMS, (20.0, 40.0), (1.0, 1.0), 0.0)
    mid = mod.blend_contours(a, b, STEMS, (15.0, 35.0), (1.0, 1.0), 0.0)
    assert first[0][1][1][0] == pytest.approx(100.0)
    assert last[0][1][1][0] == pytest.approx(140.0)
    assert mid[0][1][1][0] == pytest.approx(120.0)
    scaled = mod.blend_contours(a, b, STEMS, (30.0, 35.0), (2.0, 1.0), 0.0)
    assert scaled[0][1][1][0] == pytest.approx(240.0)
    slanted = mod.blend_contours(a, b, STEMS, (15.0, 35.0), (1.0, 1.0), 10.0)
    assert slanted[0][1][2][0] == pytest.approx(120.0), 'x-only shift survives the slant round trip'


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    ("kwargs", "text"),
    [
        ({"stems": (10.0, 20.0, 30.0, float("nan"))}, "finite positive"),
        ({"scales": (0.0, 1.0)}, "finite positive"),
        ({"angle": 85.0}, "between -85 and 85"),
        ({"stems": (10.0, 10.0, 30.0, 40.0)}, "differ"),
        ({"target": (25.0, 35.0)}, "between"),
        ({"target": (15.0, 45.0)}, "between"),
        ({"second": []}, "nonempty|equal contour|compatible"),
        ({"first": [], "second": []}, "nonempty|compatible"),
        ({"second": [(True, square()[1][:3], False)]}, "match|Closure"),
        ({"second": [square(closed=False)]}, "match|Closure"),
    ],
)
def test_blend_contours_when_input_invalid_then_value_error(name, kwargs, text):
    mod = load(name)
    args = {"first": [square()], "second": [square(4.0)], "stems": STEMS, "target": (15.0, 35.0), "scales": (1.0, 1.0), "angle": 0.0}
    args.update(kwargs)
    with pytest.raises(ValueError, match=text):
        mod.blend_contours(args["first"], args["second"], args["stems"], args["target"], args["scales"], args["angle"])


@pytest.mark.parametrize("name", NAMES)
def test_blend_contours_when_result_overflows_then_value_error(name):
    mod = load(name)
    big = (True, [(1e308, 0.0, True), (0.0, 0.0, True), (0.0, 1.0, True)], False)
    with pytest.raises(ValueError, match="range"):
        mod.blend_contours([big], [big], STEMS, (150.0, 35.0), (10.0, 1.0), 0.0)


# ---------------------------------------------------------------- pure helpers and layer readers
from types import SimpleNamespace as NS  # noqa: E402


def make_node(x, y, on=True, name="", state=0):
    return NS(x=x, y=y, isOn=lambda: on, name=name, nodeState=state, getProperties=lambda: None, getProperty=lambda key: None)


def make_contour(points, closed=True, tt=False, name=""):
    nodes = [make_node(*p) for p in points]
    return NS(
        nodes=lambda: nodes, closed=closed, isTT=tt, name=name,
        getProperties=lambda: None,
    )


def make_layer(contours, **extra):
    shape = NS(isComponent=False, transform=NS(isIdentity=lambda: True), contours=contours)
    return NS(shapes=[shape], **extra)


def test_path_text_when_curves_then_commands_match_control_counts():
    mod = load("stem_blend")
    pts = [(0.0, 0.0, True), (1.0, 2.0, False), (3.0, 4.0, True), (5.0, 6.0, False), (7.0, 8.0, False), (9.0, 0.0, True)]
    text = mod.path_text(True, pts)
    assert text.startswith("M 0 0") and " Q " in text and " C " in text and text.endswith("Z")
    assert mod.path_text(False, [(0.0, 0.0, True), (5.0, 5.0, True)]) == "M 0 0 L 5 5"


@pytest.mark.parametrize(
    ("closed", "pts", "text"),
    [
        (True, [(0.0, 0.0, False), (1.0, 1.0, False)], "on-curve"),
        (True, [(0.0, float("nan"), True)], "finite"),
        (False, [(0.0, 0.0, False), (1.0, 1.0, True)], "begin and end"),
        (True, [(0.0, 0.0, True), (1.0, 1.0, False), (2.0, 2.0, False), (3.0, 3.0, False), (4.0, 0.0, True)], "more than two|More than two"),
    ],
)
def test_path_text_when_contour_unsafe_then_value_error(closed, pts, text):
    mod = load("stem_blend")
    with pytest.raises(ValueError, match=text):
        mod.path_text(closed, pts)


def test_path_text_when_truetype_all_off_curve_then_midpoint_start():
    mod = load("stem_blend")
    text = mod.path_text(True, [(0.0, 0.0, False), (10.0, 0.0, False), (10.0, 10.0, False)], tt=True)
    assert text.startswith("M ") and "Q" in text and text.endswith("Z")


def test_svg_text_when_label_and_contours_then_escaped_flipped_svg():
    mod = load("stem_blend")
    svg = mod.svg_text("A&B", [square()])
    assert "<title>A&amp;B</title>" in svg and 'scale(1 -1)' in svg and "viewBox" in svg
    with pytest.raises(ValueError, match="no outline"):
        mod.svg_text("A", [])
    for bad in ("a\x01", "a ", "a￾"):
        with pytest.raises(ValueError, match="SVG"):
            mod.svg_text(bad, [square()])


def test_numbers_when_wrong_count_or_text_then_value_error():
    mod = load("stem_blend")
    assert mod.numbers("1 2.5", 2) == (1.0, 2.5) or list(mod.numbers("1 2.5", 2)) == [1.0, 2.5]
    with pytest.raises(ValueError, match="space-separated"):
        mod.numbers("1 x", 2)
    with pytest.raises(ValueError, match="exactly 2"):
        mod.numbers("1 2 3", 2)
    with pytest.raises(ValueError, match="exactly 2"):
        mod.numbers("1 inf", 2)


def test_export_new_when_path_valid_then_written_once_and_never_overwritten(tmp_path):
    mod = load("stem_blend")
    target = tmp_path / "out.svg"
    mod.export_new(str(target), "<svg/>")
    assert target.read_text() == "<svg/>"
    with pytest.raises(FileExistsError):
        mod.export_new(str(target), "other")
    assert target.read_text() == "<svg/>"
    for bad in ("relative.svg", str(tmp_path / "x.txt"), ""):
        with pytest.raises(ValueError, match="absolute .svg"):
            mod.export_new(bad, "x")


def test_checked_layer_name_when_reserved_or_master_name_then_refused():
    mod = load("stem_blend")
    assert mod.checked_layer_name(" Blend ", ["Light"]) in ("Blend", " Blend ")
    for bad in ("a@b", "a#b", "|temp|x"):
        with pytest.raises(ValueError, match="must not contain"):
            mod.checked_layer_name(bad, ["Light"])
    with pytest.raises(ValueError, match="master name"):
        mod.checked_layer_name("light", ["Light"])


@pytest.mark.parametrize("name", ["", "@x", "#x", "|temp|x", "Mask.a", "img.b", "BW.c", "a\x01", "a "])
def test_checked_name_when_reserved_then_refused(name):
    mod = load("scale_with_stem_compensation")
    with pytest.raises(ValueError, match="nonempty layer name"):
        mod.checked_name(name)
    assert mod.checked_name("Scaled") == "Scaled"


def test_read_contours_when_plain_layer_then_points_and_deadline(monkeypatch):
    mod = load("stem_blend")
    layer = make_layer([make_contour([(0, 0, True), (10, 0, True), (10, 10, True)])])
    assert mod.read_contours(layer, 1e18) == [(True, [(0.0, 0.0, True), (10.0, 0.0, True), (10.0, 10.0, True)], False)]
    with pytest.raises(TimeoutError, match="expired"):
        mod.read_contours(layer, 0.0)
    layer.shapes[0].isComponent = True
    with pytest.raises(ValueError, match="without components"):
        mod.read_contours(layer, 1e18)


def test_read_contours_scale_module_when_locked_component_or_custom_then_refused():
    mod = load("scale_with_stem_compensation")
    good = make_layer([make_contour([(0, 0, True), (10, 0, True), (10, 10, True)], name="c")], autoLayer=False, isLocked=False, isNull=False)
    data, meta = mod.read_contours(good, 1e18)
    assert data[0][0] is True and meta[0][0] == "c"
    for broken, text in ((None, "missing"),):
        with pytest.raises(ValueError, match=text):
            mod.read_contours(broken, 1e18)
    good.isLocked = True
    with pytest.raises(ValueError, match="locked"):
        mod.read_contours(good, 1e18)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(("drift", "ok"), [(1.6e-5, True), (5e-4, True), (2e-3, False)])
def test_stored_when_live_redo_or_reopen_drift_then_tolerance_1e_3(name, drift, ok):
    """Live drift: 1.2e-5..1.6e-5 after Redo, up to 5e-4 after reopen (Issue 250)."""
    assert load(name)._stored(10.25 + drift, 10.25) is ok


@pytest.mark.parametrize("name", NAMES)
def test_stored_outline_matches_when_drift_5e_4_then_true_and_2e_3_then_false(name):
    mod = load(name)
    want = [square()]
    near = [(c, [(x + 5e-4, y - 5e-4, k) for x, y, k in p], t) for c, p, t in want]
    far = [(c, [(x + 2e-3, y, k) for x, y, k in p], t) for c, p, t in want]
    assert mod.stored_outline_matches(near, want) is True
    assert mod.stored_outline_matches(far, want) is False
