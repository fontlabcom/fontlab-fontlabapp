# this_file: tests/test_teaching_writers_layer_metrics.py
"""Layer Metric Comparison: scalar reads, stability checks, comparison table and panel."""

import importlib
import sys
import threading
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401

MODULE = "fontlabapp.fontui.teaching_writers.layer_metric_comparison"
SELECTION = "fontlabapp.masters.layers.selection"


@pytest.fixture
def mod():
    return importlib.import_module(MODULE)


def layer(advance, box=None, shapes=1):
    bounds = NS(isNull=box is None, isEmpty=False, **(box or dict(x=0, width=0, height=0)))
    return NS(advanceWidth=advance, shapesCount=shapes, boundingBox=bounds)


def item(glyph, name, lay):
    return NS(glyph_name=glyph, layer_name=name, layer=lay)


def rows_of(*items):
    return NS(occurrences=items)


A = item("A", "Regular", layer(600, dict(x=50, width=500, height=700)))
B = item("B", "Regular", layer(300, dict(x=30, width=200, height=400)))
EMPTY = item("space", "Regular", layer(250, shapes=0))
FAR = float("inf")


def test_read_rows_when_shapes_present_then_bounds_and_right_bearing_derived(mod):
    assert mod.read_rows(rows_of(A, EMPTY), float("inf")) == (
        ("A", "Regular", 600.0, 500.0, 700.0, 50.0, 50.0),
        ("space", "Regular", 250.0, None, None, None, None),
    )


def test_read_rows_when_bounds_null_then_unavailable(mod):
    null = item("N", "R", layer(100, box=None))
    assert mod.read_rows(rows_of(null), FAR)[0][3:] == (None,) * 4


def test_read_rows_when_empty_bounds_then_unavailable(mod):
    lay = layer(100, dict(x=1, width=1, height=1))
    lay.boundingBox.isEmpty = True
    assert mod.read_rows(rows_of(item("E", "R", lay)), FAR)[0][3] is None


def test_read_rows_when_deadline_passed_then_timeout(mod):
    with pytest.raises(TimeoutError, match="no partial"):
        mod.read_rows(rows_of(A), 0.0)


def test_read_rows_when_name_has_tab_then_refused(mod):
    with pytest.raises(ValueError, match="TSV"):
        mod.read_rows(rows_of(item("A\tB", "R", layer(1))), FAR)


def test_read_rows_when_value_not_finite_then_refused(mod):
    with pytest.raises(ValueError, match="finite: A / R"):
        mod.read_rows(rows_of(item("A", "R", layer(float("nan")))), FAR)


def patch_capture(monkeypatch, selections):
    sel = importlib.import_module(SELECTION)
    queue = list(selections)
    monkeypatch.setattr(sel, "capture", lambda deadline: queue.pop(0))


def test_capture_metrics_when_stable_then_rows_returned(mod, monkeypatch):
    same = rows_of(A, B)
    patch_capture(monkeypatch, [same, same, same])
    assert [row[0] for row in mod.capture_metrics()] == ["A", "B"]


def test_capture_metrics_when_selection_changes_then_refresh_requested(mod, monkeypatch):
    patch_capture(monkeypatch, [rows_of(A), rows_of(A), rows_of(B)])
    with pytest.raises(ValueError, match="changed; refresh again"):
        mod.capture_metrics()


def test_capture_metrics_when_measurements_change_then_refresh_requested(mod, monkeypatch):
    other = item("A", "Regular", layer(601, dict(x=50, width=500, height=700)))
    same = rows_of(A)
    patch_capture(monkeypatch, [same, rows_of(other), same])
    with pytest.raises(ValueError, match="changed; refresh again"):
        mod.capture_metrics()


def test_capture_metrics_when_nothing_selected_then_refused(mod, monkeypatch):
    patch_capture(monkeypatch, [rows_of()] * 3)
    with pytest.raises(ValueError, match="at least one glyph layer"):
        mod.capture_metrics()


def test_capture_metrics_when_deadline_expires_then_timeout(mod, monkeypatch):
    patch_capture(monkeypatch, [rows_of(A)] * 3)
    ticks = iter([0.0] + [100.0] * 20)
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError):
        mod.capture_metrics()


def test_capture_metrics_when_off_main_thread_then_refused(mod):
    errors = []

    def run():
        try:
            mod.capture_metrics()
        except RuntimeError as error:
            errors.append(str(error))

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    assert errors and "main UI thread" in errors[0]


def fake_rows(monkeypatch, mod, rows):
    monkeypatch.setattr(mod, "capture_metrics", lambda: rows)


ROWS = (
    ("A", "Regular", 600.0, 500.0, 700.0, 50.0, 50.0),
    ("B", "Regular", 300.0, 0.0, None, None, None),
)


def test_build_output_when_difference_blank_reference_then_first_row_used(mod, monkeypatch):
    fake_rows(monkeypatch, mod, ROWS)
    out = mod.build_output(("Advance", "", "", "Difference"))
    assert out.splitlines() == ["Glyph\tLayer\tValue\tCompared", "A\tRegular\t600\t0", "B\tRegular\t300\t-300"]


def test_build_output_when_percent_and_unavailable_then_marked(mod, monkeypatch):
    fake_rows(monkeypatch, mod, ROWS)
    out = mod.build_output(("Height", "A", "Regular", "Percent"))
    assert out.splitlines()[1:] == ["A\tRegular\t700\t100", "B\tRegular\tUnavailable\tUnavailable"]


def test_build_output_when_percent_of_zero_reference_then_undefined(mod, monkeypatch):
    fake_rows(monkeypatch, mod, ROWS)
    out = mod.build_output(("Width", "B", "Regular", "Percent"))
    assert out.splitlines()[1] == "A\tRegular\t500\tUndefined (zero reference)"


def test_build_output_when_inputs_invalid_then_refused(mod, monkeypatch):
    fake_rows(monkeypatch, mod, ROWS)
    with pytest.raises(ValueError, match="listed measurement"):
        mod.build_output(("Depth", "", "", "Difference"))
    with pytest.raises(ValueError, match="both reference names"):
        mod.build_output(("Advance", "A", "", "Difference"))
    with pytest.raises(ValueError, match="must be selected"):
        mod.build_output(("Advance", "Z", "Regular", "Difference"))


def test_build_output_when_result_overflows_then_refused(mod, monkeypatch):
    fake_rows(monkeypatch, mod, (("A", "R", 1e308, None, None, None, None), ("B", "R", -1e308, None, None, None, None)))
    with pytest.raises(ValueError, match="Compared measurement must be finite"):
        mod.build_output(("Advance", "", "", "Difference"))


@pytest.mark.parametrize("text", ["a\0b", "a b", "a b", "a\rb", "\ud800"])
def test_checked_when_unsafe_text_then_refused(mod, text):
    with pytest.raises(ValueError):
        mod.checked(text)


def test_checked_when_plain_then_returned(mod):
    assert mod.checked("Åb") == "Åb"


def test_panel_when_refreshed_and_copied_then_status_and_clipboard_follow(studio_qt, mod, monkeypatch):  # noqa: F811
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(mod, "build_output", lambda fields: "Glyph\tLayer\tValue\tCompared\n" + "|".join(fields))
    panel = mod.show(qt, None, embedded=True)
    assert panel in mod._PANELS and "Advance" in panel.output_box.toPlainText()
    assert panel.status_line.text().startswith("Result refreshed")
    panel.copy_output()
    assert panel.status_line.text() == "Fresh result copied."
    monkeypatch.setattr(mod, "build_output", lambda fields: (_ for _ in ()).throw(ValueError("stale")))
    panel.refresh_output()
    assert panel.status_line.text() == "stale" and panel.output_box.toPlainText() == ""
    panel.copy_output()
    assert panel.status_line.text() == "stale"
    monkeypatch.setattr(mod, "build_output", lambda fields: "")
    panel.copy_output()
    assert panel.status_line.text() == "No matching output to copy."


def test_panel_when_close_cleanup_fails_then_retained_until_release(studio_qt, mod, monkeypatch):  # noqa: F811
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(mod, "build_output", lambda fields: "x")
    panel = mod.show(qt, None, embedded=True)
    panel.signal_scope.finish = lambda destroyed=False: False
    event = NS(ignored=False)
    event.ignore = lambda: setattr(event, "ignored", True)
    panel.closeEvent(event)
    assert event.ignored and panel in mod._PANELS
    del panel.signal_scope.finish
    event.accept = lambda: setattr(event, "accepted", True)
    panel.closeEvent(event)
    assert event.accepted and panel not in mod._PANELS


def test_show_when_refresh_raises_then_scope_finished_and_reraised(studio_qt, mod, monkeypatch):  # noqa: F811
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(qt.QtGui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("no screen")), raising=False)
    monkeypatch.setattr(mod, "build_output", lambda fields: "x")
    before = list(mod._PANELS)
    with pytest.raises(RuntimeError, match="no screen"):
        mod.show(qt, None)
    assert mod._PANELS == before


def test_main_when_show_refuses_then_prints_title_and_reason(mod, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: "w"))
    monkeypatch.setitem(sys.modules, "PythonQt", NS())
    monkeypatch.setattr(mod, "show", lambda qt, parent: (_ for _ in ()).throw(ValueError("nope")))
    mod.main()
    assert capsys.readouterr().out == "Layer Metric Comparison: nope\n"
