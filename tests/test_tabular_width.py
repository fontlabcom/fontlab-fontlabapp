# this_file: tests/test_tabular_width.py
"""Test the adapted report with owned native-shaped sources only."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.metrics.tabular_width.model as api


def test_report_keeps_exact_reference_order_fractional_values_and_time():
    report = api.compare((("B", 500.125), ("A", 500.125), ("C", 500.126)), "12:34:56")
    assert report.same == 2 and report.different == 1
    assert [row.name for row in report.rows] == ["B", "A", "C"]
    assert report.rows[2].matches is False
    assert "500.125" in api.render(report) and "12:34:56" in api.render(report)
    assert "2 glyphs are on same width." in api.render(report)
    assert "1 glyphs are on different width." in api.render(report)


@pytest.mark.parametrize("rows", [(), (("a", float("nan")),), (("a", float("inf")),)])
def test_invalid_input_is_diagnosed(rows):
    with pytest.raises(ValueError):
        api.compare(rows, "00:00:00")


def test_zero_negative_and_single_reference_are_exact():
    assert api.compare((("a", 0.0), ("b", -1)), "x").same == 1
    assert api.compare((("a", -1.25),), "x").different == 0


@pytest.fixture
def source(monkeypatch):
    layers = {
        name: NS(id=i, name="Regular", isNull=False, advanceWidth=value)
        for i, (name, value) in enumerate((("a", 500.125), ("b", 500.125)), 1)
    }
    package = NS(id=7, fgId=700, master="Regular")
    glyphs = {
        name: NS(
            id=i,
            name=name,
            isNull=False,
            package=package,
            findLayer=lambda master, name=name: (
                layers.get(name) if master == "Regular" else None
            ),
        )
        for i, name in enumerate(layers, 1)
    }
    package.findName = glyphs.get
    state = NS(
        package=package, selection=["a", "b"], layers=layers, glyphs=glyphs, calls=[]
    )

    def selected(deadline):
        state.calls.append(deadline)
        package = state.package
        if package is None:
            raise ValueError("Open a font")
        rows = []
        for index, name in enumerate(state.selection):
            api._check_deadline(deadline)
            glyph = package.findName(name)
            api._check_deadline(deadline)
            layer = None if glyph is None else glyph.findLayer(package.master)
            if glyph is None or layer is None:
                raise ValueError("Selected glyph/layer is missing")
            rows.append(api.selection.LayerOccurrence(package, glyph, layer, 0, index))
        return api.selection.LayerSelection(context(deadline), tuple(rows))

    def context(deadline):
        return (state.package.id, state.package.master, "font", 1)

    monkeypatch.setattr(api.selection, "capture", selected)
    monkeypatch.setattr(api.selection, "document_context", context)
    return state


def test_capture_uses_actual_selection_and_never_fallback(source):
    assert api.capture().same == 2
    source.selection = ["b"]
    assert api.capture().rows[0].name == "b"
    source.selection = []
    with pytest.raises(ValueError, match="Select"):
        api.capture()
    source.package = None
    with pytest.raises(ValueError, match="Open"):
        api.capture()


@pytest.mark.parametrize(
    "change", ["width", "master", "font", "selection", "missing", "glyph", "layer"]
)
def test_capture_refuses_source_changes(source, monkeypatch, change):
    original = source.package.findName
    calls = 0

    def changed(name):
        nonlocal calls
        calls += 1
        if calls == 3:
            if change == "width":
                source.layers["a"].advanceWidth += 1
            if change == "master":
                source.package.master = "Bold"
            if change == "font":
                source.package = NS(id=8, fgId=800, master="Regular", findName=original)
            if change == "selection":
                source.selection.reverse()
            if change == "missing":
                source.layers.pop("a")
            if change == "glyph":
                source.glyphs["a"].id += 1
            if change == "layer":
                source.layers["a"].id += 1
        return original(name)

    source.package.findName = changed
    with pytest.raises(ValueError):
        api.capture()


@pytest.mark.parametrize("kind", ["glyph", "layer", "nullglyph", "nulllayer"])
def test_initial_missing_or_null_sources_refuse(source, kind):
    if kind == "glyph":
        source.glyphs.pop("a")
    if kind == "layer":
        source.layers.pop("a")
    if kind == "nullglyph":
        source.glyphs["a"].isNull = True
    if kind == "nulllayer":
        source.layers["a"].isNull = True
    with pytest.raises(ValueError):
        api.capture()


def test_capture_forwards_the_same_deadline_to_all_selection_fences(source):
    api.capture()
    assert len(source.calls) == 3 and len(set(source.calls)) == 1


def test_width_loop_deadline_stops_before_reading_remaining_rows(source, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(api, "monotonic", lambda: clock[0])
    original = source.package.findName
    visited = []

    def delayed(name):
        visited.append(name)
        clock[0] = 3.0
        return original(name)

    source.package.findName = delayed
    with pytest.raises(TimeoutError):
        api.capture()
    assert visited == ["a"], "Stop before touching the next native glyph"


def test_deadline_expired_before_first_width_read(source, monkeypatch):
    clock = iter([0.0, 3.0])
    monkeypatch.setattr(api, "monotonic", lambda: next(clock, 3.0))
    source.package.findName = lambda name: pytest.fail("No width read after deadline")
    with pytest.raises(TimeoutError):
        api.capture()
