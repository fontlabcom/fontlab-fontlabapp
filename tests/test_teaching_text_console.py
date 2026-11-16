# this_file: tests/test_teaching_text_console.py
"""Glyph Snapshot Console: capture budget, bounded evaluation and panel lifecycle, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import console

    return console


@pytest.fixture
def untraced():
    """evaluate() chains a callable host trace (coverage's, when measuring) and restores it."""
    before = sys.gettrace()
    yield
    assert sys.gettrace() is before


NAMESPACE = {"glyphs": [{"name": "A"}, {"name": "B"}], "__builtins__": {"len": len, "print": print}}


def test_snapshot_namespace_when_rows_then_dicts_and_shared_builtins(mod):
    ns = mod.snapshot_namespace((("A", "U+0041", "2026-01-01 00:00:00"),))
    assert ns["glyphs"] == [{"name": "A", "unicode": "U+0041", "modified": "2026-01-01 00:00:00"}]
    assert ns["__builtins__"] is mod.BUILTINS and mod.BUILTINS["len"] is len


def test_evaluate_when_expression_statement_or_print_then_text(mod, untraced):
    assert mod.evaluate("len(glyphs)", dict(NAMESPACE)) == "2"
    assert mod.evaluate("x = 1", dict(NAMESPACE)) == "Statement complete."
    assert mod.evaluate("print('hi')", dict(NAMESPACE)) == "hi\n"
    assert mod.evaluate("None", dict(NAMESPACE)) == "None"


def test_evaluate_when_seconds_out_of_range_then_refused(mod):
    for bad in (0, -1, 61):
        with pytest.raises(ValueError, match="deadline greater than 0"):
            mod.evaluate("1", {}, bad)


def test_evaluate_when_loop_runs_past_deadline_then_timeout_and_trace_restored(mod, untraced):
    with pytest.raises(TimeoutError, match="exceeded 0.05 seconds"):
        mod.evaluate("[0 for _ in iter(int, 1)]", {"__builtins__": {"iter": iter, "int": int}}, 0.05)
    with pytest.raises(TimeoutError):
        mod.evaluate("while True:\n    pass", {"__builtins__": {}}, 0.05)


def test_evaluate_when_seconds_at_upper_bound_or_tiny_then_accepted(mod, untraced):
    assert mod.evaluate("1", {}, 60) == "1"  # kills `<= 60` -> `< 60`


def test_evaluate_when_clock_equals_deadline_then_times_out(mod, untraced, monkeypatch):
    ticks = iter([100.0])  # deadline = 100 + 5
    seen = {"deadline": None}

    def clock():
        value = next(ticks, None)
        if value is not None:
            seen["deadline"] = value + 5.0
            return value
        return seen["deadline"]  # exactly the deadline: `>=` must fire, `>` would not

    monkeypatch.setattr(mod, "monotonic", clock)
    with pytest.raises(TimeoutError, match="exceeded 5 seconds"):
        mod.evaluate("1", dict(NAMESPACE), 5.0)


def test_evaluate_when_slow_code_returns_then_final_check_raises(mod, untraced, monkeypatch):
    ticks = iter([0.0, 0.0, 0.0, 0.0, 99.0, 99.0, 99.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks, 99.0))
    with pytest.raises(TimeoutError):
        mod.evaluate("1", dict(NAMESPACE), 5.0)


def test_evaluate_when_host_trace_callable_then_chained_and_restored(mod):
    seen = []
    saved = sys.gettrace()

    def host(frame, event, arg):
        seen.append(event)
        return host

    sys.settrace(host)
    try:
        assert mod.evaluate("len(glyphs)", dict(NAMESPACE)) == "2"
        assert sys.gettrace() is host and "call" in seen
    finally:
        sys.settrace(saved)


def test_evaluate_when_host_trace_opaque_then_refused(mod, monkeypatch):
    monkeypatch.setattr(sys, "gettrace", lambda: object())
    with pytest.raises(RuntimeError, match="already traces"):
        mod.evaluate("1", {})


def test_capture_current_when_no_package_then_refused_else_budget_scaled(mod, monkeypatch):
    import fontlabapp.core.scripting as scripting
    import fontlabapp.glyphs.catalog.model as catalog

    status = NS(text=None, repainted=False)
    status.setText = lambda t: setattr(status, "text", t)
    status.repaint = lambda: setattr(status, "repainted", True)
    monkeypatch.setattr(scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Open a font"):
        mod.capture_current(status)
    monkeypatch.setattr(scripting, "current_package", lambda: NS(glyphsCount=lambda: 1000))
    clock = [100.0]
    monkeypatch.setattr(mod, "monotonic", lambda: clock[0])
    monkeypatch.setattr(catalog, "capture", lambda deadline: NS(deadline=deadline))
    assert mod.capture_current(status).deadline == 130.0  # 10 + 0.02 * 1000
    assert "Scanning 1,000 glyphs (budget 30 s)" in status.text and status.repainted
    monkeypatch.setattr(scripting, "current_package", lambda: NS(glyphsCount=10**6))
    assert mod.capture_current(status).deadline == 220.0  # capped at 120 s


@pytest.fixture
def console(lab, monkeypatch):  # noqa: F811
    module, shown = lab("console")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    yield module, qt, parent
    module._PANELS.clear()


def clicker(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_captured_run_and_cleared_then_each_state_shown(console, monkeypatch, untraced):
    module, qt, parent = console
    panel = module.show(qt, parent, embedded=True)
    clicker(panel, qt, "Run Trusted Python")
    assert panel.output_box.toPlainText() == "ValueError: Capture before Run."
    monkeypatch.setattr(module, "capture_current", lambda status: NS(rows=(("A", "U+0041", ""), ("B", "", ""))))
    hooks = []
    panel.lab_refresh_preview = lambda: hooks.append(1)
    clicker(panel, qt, "Capture / Reset Namespace")
    assert panel.status_line.text() == "Ready: 2 glyphs. Capture resets variables." and hooks == [1]
    clicker(panel, qt, "Run Trusted Python")
    assert panel.output_box.toPlainText() == "2" and panel.status_line.text().startswith("Result from")
    panel.query_entry.setText("1/0")
    panel.query_entry.returnPressed.emit()
    assert panel.output_box.toPlainText().startswith("ZeroDivisionError") and "Query failed" in panel.status_line.text()
    clicker(panel, qt, "Clear Snapshot")
    assert panel.query_namespace is None and panel.status_line.text().startswith("Snapshot cleared")


def test_panel_when_closed_then_scope_finished_or_retained(console):
    module, qt, parent = console
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.scope.finish
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS
    panel.release_owner()


def test_show_when_window_show_fails_then_released_or_kept(console, monkeypatch):
    module, qt, parent = console
    monkeypatch.setattr(qt.QtGui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("no screen")))
    with pytest.raises(RuntimeError, match="no screen"):
        module.show(qt, parent)
    assert module._PANELS == []
    import fontlabapp.core.signals.scope as signals

    monkeypatch.setattr(signals.Scope, "finish", lambda self, destroyed=False: False)
    with pytest.raises(RuntimeError, match="no screen"):
        module.show(qt, parent)
    assert len(module._PANELS) == 1


def test_main_and_build(console, monkeypatch, capsys):
    module, qt, parent = console
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    assert module.build(None) in module._PANELS
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p: seen.append(p))
    module.main()
    assert seen == [parent]
    monkeypatch.setattr(module, "show", lambda q, p: (_ for _ in ()).throw(ValueError("nope")))
    module.main()
    assert capsys.readouterr().out == f"{module.TITLE}: nope\n"


def test_evaluate_when_host_tracer_reinstalls_itself_then_deadline_still_fires_and_tracer_restored(mod):
    saved = sys.gettrace()

    def host(frame, event, arg):  # like coverage's C tracer: re-takes the global hook on every call
        sys.settrace(host)
        return host

    def hung(signum, frame):
        raise AssertionError("deadline never fired: the host tracer took the hook back")

    import signal

    old_handler = signal.signal(signal.SIGALRM, hung)  # fail instead of hanging if the guard is lost
    signal.setitimer(signal.ITIMER_REAL, 5)
    sys.settrace(host)
    try:
        with pytest.raises(TimeoutError, match="exceeded 0.05 seconds"):
            mod.evaluate("while True:\n    pass", {"__builtins__": {}}, 0.05)
        with pytest.raises(TimeoutError):
            mod.evaluate("[0 for _ in iter(int, 1)]", {"__builtins__": {"iter": iter, "int": int}}, 0.05)
        assert sys.gettrace() is host
    finally:
        sys.settrace(saved)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
