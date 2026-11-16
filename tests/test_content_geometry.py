# this_file: tests/test_content_geometry.py
"""Raw contents fitting: no binding import, conversion, or hidden second read."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fontlabapp.qt.layouts.content import fit_contents


@pytest.mark.parametrize(
    "frame",
    [
        (1, 21, -2, 0),
        (Decimal("0.25"), -1.5, 0, Decimal("3.125")),
        tuple(object() for _ in range(4)),
    ],
)
def test_fit_preserves_exact_objects_and_accessor_order(frame):
    trace = []

    def step(name, value=None):
        trace.append(name)
        return value

    rect = SimpleNamespace(
        **{
            name: lambda name=name, value=value: step(name, value)
            for name, value in zip(("x", "y", "width", "height"), frame)
        }
    )
    content = SimpleNamespace(
        setGeometry=lambda *args: trace.append(("geometry", args))
    )
    result = fit_contents(
        SimpleNamespace(contentsRect=lambda: step("rect", rect)), content
    )
    assert trace == ["rect", "x", "y", "width", "height", ("geometry", frame)]
    assert all(actual is expected for actual, expected in zip(result, frame[2:]))


@pytest.mark.parametrize("failure", ["rect", "x", "y", "width", "height", "geometry"])
def test_fit_propagates_same_exception_and_stops_at_failure(failure):
    trace = []
    error = RuntimeError("owned injected error")

    def step(name, value=None):
        trace.append(name)
        if name == failure:
            raise error
        return value

    rect = SimpleNamespace(
        **{
            name: lambda name=name: step(name, 1)
            for name in ("x", "y", "width", "height")
        }
    )
    content = SimpleNamespace(setGeometry=lambda *args: step("geometry"))
    with pytest.raises(RuntimeError) as caught:
        fit_contents(SimpleNamespace(contentsRect=lambda: step("rect", rect)), content)
    assert caught.value is error
    stages = ["rect", "x", "y", "width", "height", "geometry"]
    assert trace == stages[: stages.index(failure) + 1]


@pytest.mark.parametrize(
    "missing", ["contentsRect", "x", "y", "width", "height", "setGeometry"]
)
def test_fit_missing_accessor_fails_before_later_work(missing):
    rect = SimpleNamespace(x=lambda: 1, y=lambda: 2, width=lambda: 3, height=lambda: 4)
    container = SimpleNamespace(contentsRect=lambda: rect)
    content = SimpleNamespace(
        setGeometry=lambda *args: pytest.fail("geometry called after missing accessor")
    )
    target = (
        container
        if missing == "contentsRect"
        else content
        if missing == "setGeometry"
        else rect
    )
    delattr(target, missing)
    with pytest.raises(AttributeError, match=missing):
        fit_contents(container, content)
