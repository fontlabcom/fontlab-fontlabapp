# this_file: tests/test_stack_layout.py
"""Independent axis geometry expectations for the shared stack arithmetic."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest
from fontlabapp.qt.layouts.stack import distribute


@pytest.mark.parametrize(
    "mode,expected_sizes,expected_starts",
    [
        ("fixed", [10.0, 20.0, 30.0], [0.0, 15.0, 40.0]),
        ("equal", [30.0, 30.0, 30.0], [0.0, 35.0, 70.0]),
        ("proportional", [15.0, 30.0, 45.0], [0.0, 20.0, 55.0]),
        ("spacing", [10.0, 20.0, 30.0], [0.0, 30.0, 70.0]),
        ("centering", [10.0, 20.0, 30.0], [0.0, 35.0, 70.0]),
    ],
)
def test_distribute_when_three_items_then_independent_axis_geometry(
    mode, expected_sizes, expected_starts
):
    sizes = [10.0, 20.0, 30.0]
    identity = id(sizes)
    assert distribute(sizes, 100.0, 5.0, mode) == pytest.approx(expected_starts)
    assert sizes == pytest.approx(expected_sizes) and id(sizes) == identity


@pytest.mark.parametrize(
    "mode", ["fixed", "equal", "proportional", "spacing", "centering"]
)
def test_distribute_when_empty_or_single_then_total(mode):
    sizes = []
    assert distribute(sizes, 10.0, 2.0, mode) == [] and sizes == []
    single = [7.0]
    assert distribute(single, 10.0, 2.0, mode) == [0.0]
    assert single == ([10.0] if mode in ("equal", "proportional") else [7.0])


@pytest.mark.parametrize(
    "mode,sizes,length,spacing,want_sizes,want_starts",
    [
        ("equal", [10.0, 20.0], 5.0, 10.0, [0.0, 0.0], [0.0, 10.0]),
        ("proportional", [10.0, 20.0], 5.0, 10.0, [0.0, 0.0], [0.0, 10.0]),
        ("proportional", [0.0, 0.0], 100.0, 2.0, [0.0, 0.0], [0.0, 2.0]),
        ("spacing", [60.0, 60.0], 50.0, 5.0, [60.0, 60.0], [0.0, 65.0]),
        ("centering", [60.0, 60.0], 50.0, 5.0, [60.0, 60.0], [0.0, -10.0]),
        ("fixed", [1.25, 2.5], 10.0, -0.5, [1.25, 2.5], [0.0, 0.75]),
        ("proportional", [0.0, 10.0], 100.0, 0.0, [0.0, 100.0], [0.0, 0.0]),
    ],
)
def test_distribute_when_constrained_or_fractional_then_existing_policy(
    mode, sizes, length, spacing, want_sizes, want_starts
):
    assert distribute(sizes, length, spacing, mode) == pytest.approx(want_starts)
    assert sizes == pytest.approx(want_sizes)


def test_distribute_when_unknown_mode_then_fail_before_mutation():
    sizes = [1.0, 2.0]
    with pytest.raises(ValueError, match="distribution"):
        distribute(sizes, 10.0, 2.0, "unknown")
    assert sizes == [1.0, 2.0]


def test_module_when_loaded_then_no_binding_or_bridge_dependencies():
    module = importlib.import_module("fontlabapp.qt.layouts.stack")
    assert module.distribute is distribute
    root = str((Path(__file__).resolve().parents[1] / "src"))
    code = f"import sys; sys.path.insert(0, {root!r}); import fontlabapp.qt.layouts.stack; assert not {{'PythonQt','fontlab','fontgate','FL','fontlab_glyport','fontlab_fontport'}} & set(sys.modules)"
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
