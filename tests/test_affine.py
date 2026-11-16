# this_file: tests/test_affine.py
"""Pure affine math: identity, Qt row-vector order, inversion, finite checks."""

import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import fontlabapp.contours.affine as affine


class Point:
    """Minimal QPointF stand-in: constructor (x, y), accessors x() and y()."""

    def __init__(self, x: float, y: float) -> None:
        self._x, self._y = x, y

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y


def test_identity_when_applied_then_point_unchanged():
    assert affine.apply(affine.IDENTITY, 3.5, -2.0) == (3.5, -2.0)


def test_concat_when_identity_on_either_side_then_operand_unchanged():
    t = (2.0, 0.5, -1.0, 3.0, 7.0, -4.0)
    assert affine.concat(affine.IDENTITY, t) == t, "identity first"
    assert affine.concat(t, affine.IDENTITY) == t, "identity last"


def test_concat_when_composed_then_first_applies_before_then():
    scale = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)
    shift = (1.0, 0.0, 0.0, 1.0, 10.0, 0.0)
    # Qt row-vector rule: scale first, then shift => (1,1) -> (2,2) -> (12,2).
    assert affine.apply(affine.concat(scale, shift), 1, 1) == (12.0, 2.0)
    # Reversed order differs: shift first => (1,1) -> (11,1) -> (22,2).
    assert affine.apply(affine.concat(shift, scale), 1, 1) == (22.0, 2.0)


def test_concat_when_general_matrices_then_equals_stepwise_apply():
    first = (1.5, 0.25, -0.75, 2.0, 3.0, -5.0)
    then = (0.5, -1.0, 2.0, 0.25, -7.0, 9.0)
    combined = affine.concat(first, then)
    step = affine.apply(then, *affine.apply(first, 4.0, -3.0))
    assert affine.apply(combined, 4.0, -3.0) == pytest.approx(step)


def test_invert_when_regular_then_round_trip_is_identity():
    t = (2.0, 1.0, -1.0, 3.0, 5.0, -6.0)
    round_trip = affine.concat(t, affine.invert(t))
    assert round_trip == pytest.approx(affine.IDENTITY), "t then t^-1"


def test_invert_when_singular_then_value_error():
    with pytest.raises(ValueError, match="invertible"):
        affine.invert((1.0, 2.0, 2.0, 4.0, 0.0, 0.0))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_invert_when_non_finite_then_value_error(bad):
    with pytest.raises(ValueError):
        affine.invert((bad, 0.0, 0.0, 1.0, 0.0, 0.0))


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_concat_when_non_finite_operand_then_value_error(bad):
    with pytest.raises(ValueError, match="finite"):
        affine.concat((1.0, 0.0, 0.0, 1.0, bad, 0.0), affine.IDENTITY)
    with pytest.raises(ValueError, match="finite"):
        affine.concat(affine.IDENTITY, (1.0, 0.0, 0.0, bad, 0.0, 0.0))


def test_concat_when_finite_check_off_then_non_finite_passes_through():
    result = affine.concat(
        (1.0, 0.0, 0.0, 1.0, math.inf, 0.0), affine.IDENTITY, finite=False
    )
    assert result[4] == math.inf


def test_concat_when_result_overflows_then_value_error():
    huge = (1e200, 0.0, 0.0, 1e200, 0.0, 0.0)
    with pytest.raises(ValueError, match="finite"):
        affine.concat(huge, huge)


def test_apply_when_non_finite_point_then_value_error():
    with pytest.raises(ValueError, match="finite"):
        affine.apply(affine.IDENTITY, math.nan, 0.0)


def test_rotation_when_quarter_turn_then_x_axis_maps_to_y_axis():
    x, y = affine.apply(affine.rotation(90), 1.0, 0.0)
    assert (x, y) == pytest.approx((0.0, 1.0), abs=1e-12)


def test_from_qtransform_when_valid_then_six_floats_in_qt_order():
    qt = SimpleNamespace(
        m11=lambda: 1, m12=lambda: 2, m21=lambda: 3, m22=lambda: 4,
        dx=lambda: 5, dy=lambda: 6,
    )
    assert affine.from_qtransform(qt) == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)


def test_from_qtransform_when_non_finite_then_value_error():
    qt = SimpleNamespace(
        m11=lambda: math.nan, m12=lambda: 0, m21=lambda: 0, m22=lambda: 1,
        dx=lambda: 0, dy=lambda: 0,
    )
    with pytest.raises(ValueError, match="finite"):
        affine.from_qtransform(qt)


def test_viewport_transform_when_sampled_then_maps_unit_axes():
    canvas = SimpleNamespace(
        mapToViewportF=lambda p: Point(3 * p.x() + 7, -3 * p.y() + 11)
    )
    t = affine.viewport_transform(canvas, Point)
    assert t == (3.0, 0.0, 0.0, -3.0, 7.0, 11.0)
    assert affine.apply(t, 2, 1) == (13.0, 8.0), "must agree with the native map"


def test_viewport_transform_when_sampling_then_reads_origin_x_y_in_order():
    seen = []

    def sample(p):
        seen.append((p.x(), p.y()))
        return p

    affine.viewport_transform(SimpleNamespace(mapToViewportF=sample), Point)
    assert seen == [(0, 0), (1, 0), (0, 1)]


def test_viewport_transform_when_native_map_non_finite_then_value_error():
    canvas = SimpleNamespace(mapToViewportF=lambda p: Point(math.nan, 0))
    with pytest.raises(ValueError, match="viewport"):
        affine.viewport_transform(canvas, Point)


def test_affine_when_cold_imported_then_no_native_or_heavy_modules_load():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root != 'fontlabapp' and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.contours.affine as a
assert a.apply(a.IDENTITY, 1, 2) == (1, 2)
banned = {'PythonQt', 'fontlab', 'fontgate', 'FL', 'fontpr', 'PySide2',
          'PySide6', 'fontport', 'fontlab_fontport', 'glyport',
          'fontlab_glyport', 'fontTools', 'fontParts'}
loaded = {n.split('.')[0] for n in sys.modules} & banned
assert not loaded, loaded
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
