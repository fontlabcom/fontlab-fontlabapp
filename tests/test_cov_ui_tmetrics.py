# this_file: tests/test_cov_ui_tmetrics.py
# SPDX-License-Identifier: Apache-2.0
"""TMetrics window built offscreen: controls, status, selection, painting, follow and close."""

import sys
from types import SimpleNamespace
from typing import Any

import pytest

import _cov_qt as fq

pytest.importorskip("uharfbuzz")

OWN_MODULES = (
    "fontlabapp.fontui.tmetrics",
    "fontlabapp.fontui.tmetrics_model",
    "fontlabapp.fontui.livesync",
    "fontlabapp.fontui.tglyph",
    "fontlabapp.fontui.tglyph_model",
    "fontlabapp.fontui.tglyph_edit",
)
MODIFIERS = {"ShiftModifier": 0x02000000, "ControlModifier": 0x04000000, "AltModifier": 0x08000000, "MetaModifier": 0x10000000}


class Painter(fq.FakeWidget):
    """Fake QPainter that records the drawing calls TMetrics makes."""

    log: list = []

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        Painter.log.append(self)

    def _record(name):
        def method(self, *args: Any) -> None:
            self.__dict__.setdefault("calls", []).append((name, args))

        return method

    drawLine = _record("drawLine")
    drawRect = _record("drawRect")
    drawText = _record("drawText")
    save = _record("save")
    restore = _record("restore")


class Bar:
    """Scrollbar fake whose value clamps to 0 when the canvas shrinks."""

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def setValue(self, value: int) -> None:
        self.value = value


def _bar(name):
    def method(self):
        return self.__dict__.setdefault(name, Bar())

    return method


@pytest.fixture
def tm_mod(monkeypatch):
    handle = fq.install(monkeypatch)
    for name in OWN_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
        fq._forget_on_parent(name, monkeypatch)
    handle.qt.QtGui.QPainter = Painter
    monkeypatch.setattr(fq, "SIGNALS", fq.SIGNALS | {"returnPressed"})
    for name, flag in MODIFIERS.items():
        monkeypatch.setattr(fq.FakeWidget, name, flag, raising=False)
    monkeypatch.setattr(fq.FakeWidget, "setWindowTitle", lambda self, title: self.__dict__.setdefault("calls", []).append(("setWindowTitle", (title,))), raising=False)
    monkeypatch.setattr(fq.FakeWidget, "horizontalScrollBar", _bar("_hbar"), raising=False)
    monkeypatch.setattr(fq.FakeWidget, "verticalScrollBar", _bar("_vbar"), raising=False)
    Painter.log = []
    module = handle.load("fontlabapp.fontui.tmetrics")
    # Painter doubles use the light scheme; the real Qt suite checks resolution.
    monkeypatch.setattr(module, "_canvas_colors", lambda canvas, colors: {
        **colors, "selection_background": colors["selected"], "selection_foreground": "#303030",
    })
    monkeypatch.setattr(fq, "RECORDED_METHODS", fq.RECORDED_METHODS | {
        "setContentsMargins", "setSpacing", "setFrameShape",
    })
    module.model_module = handle.load("fontlabapp.fontui.tmetrics_model")
    yield module
    for name in OWN_MODULES:
        sys.modules.pop(name, None)
        fq._forget_on_parent(name)
    fq.release()


def font() -> fq.FontModel:
    model = fq.FontModel(fq.ufo_font())
    model.features = SimpleNamespace(text="")
    return model


def make(module: Any, text: str = "AV", on_open: Any = None):
    window = module.TMetrics(font(), None, on_open, text)
    window.scroll.viewport().width = 800
    window.refresh()
    return window


def click(window: Any, index: int, method: str = "select_at") -> None:
    x, _ = window.layout_geometry.origins[index]
    getattr(window, method)(x + 1, window.layout_geometry.row_top(0) + 5)


def test_init_when_text_given_then_shaped_status_and_outlines(tm_mod):
    window = make(tm_mod)
    assert window.diagnostic.text == "shaped (HarfBuzz)", "the status names HarfBuzz shaping"
    assert [c.name for c in window.model.cells] == ["A", "V"], "the model holds the shaped run"
    assert set(window.outlines) == {"A", "V"}, "outlines are cached per glyph"
    assert window.readout.text == "" and window.pair_readout.text == "", "no selection, no readout"


def test_refresh_when_run_shown_then_each_outline_built_once(tm_mod, monkeypatch):
    import fontlabapp.fontui.tmetrics_model as model_mod
    calls: list[str] = []
    real = model_mod.outline

    def counting(font, name):
        calls.append(name)
        return real(font, name)

    monkeypatch.setattr(model_mod, "outline", counting)
    window = make(tm_mod)
    calls.clear()
    window.refresh()
    assert sorted(calls) == ["A", "V"], "one outline per glyph per refresh, shared by shaping, drawn token and painting"
    calls.clear()
    window.follow()
    assert set(calls) == {"A", "V"}, "a follow re-reads the font afresh and never reuses a cache"


def test_controls_when_changed_then_model_settings_follow(tm_mod):
    window = make(tm_mod)
    window.features_control.setText("-kern")
    assert window.model.cells[0].kern == 0, "the features field disables kern"
    window.features_control.setText("")
    window.kerning_control.setChecked(False)
    assert window.model.settings.kerning is False, "the kerning toggle reaches the shaper"
    window.direction_control.setCurrentIndex(1)
    assert window.model.settings.direction == "rtl", "the direction combo selects RTL"
    window.script_control.setText("latn")
    window.language_control.setText("dflt")
    assert window.model.settings.script == "latn", "script follows the field"
    window.size_control.setValue(144)
    assert window.layout_geometry.scale == pytest.approx(0.144), "size sets the scale"


def test_refresh_when_uharfbuzz_missing_then_fallback_in_status(tm_mod, monkeypatch):
    shaping = tm_mod.model_module.shaping
    monkeypatch.setattr(shaping, "_load_harfbuzz", lambda: None)
    shaping.clear_cache()
    window = make(tm_mod)
    assert window.diagnostic.text.startswith("unshaped: uharfbuzz not available"), "fallback diagnostic shown"


def test_select_when_clicked_then_readouts_show_glyph_and_pair(tm_mod):
    window = make(tm_mod)
    click(window, 1)
    assert window.model.selected == 1, "a click selects the glyph under it"
    assert window.readout.text == "V  advance 600  LSB 0  RSB 0", "the glyph readout"
    assert window.pair_readout.text.startswith("Pair A V: -80 (group pair"), "the pair readout"
    window.select_at(1, 1)
    assert window.model.selected == 1, "a miss keeps the selection"


def test_select_key_when_arrows_then_selection_moves_and_scrolls(tm_mod):
    window = make(tm_mod)
    qt = sys.modules["PythonQt"].QtCore.Qt
    assert window.select_key(qt.Key_Right) is True and window.model.selected == 0, "right selects the first"
    assert window.select_key(qt.Key_End) and window.model.selected == 1, "end selects the last"
    assert ("ensureVisible", window.scroll.calls[-1][1]) == window.scroll.calls[-1], "the selection is revealed"
    assert window.select_key("Key_Up") is False, "other keys are not handled"


def test_refresh_when_font_edited_then_text_and_selection_preserved(tm_mod):
    window = make(tm_mod)
    click(window, 1)
    window.font["V"].width = 640
    window.refresh()
    assert window.text_control.text == "AV" and window.model.selected == 1, "text and selection survive"
    assert window.readout.text.startswith("V  advance 640"), "the readout follows the edit"


def test_reflow_when_viewport_narrows_then_rows_break(tm_mod):
    window = make(tm_mod, "AVAVAV")
    assert window.model.rows == 1, "a wide viewport holds one row"
    window.scroll.viewport().width = 150
    window.reflow()
    assert window.model.rows > 1, "a narrow viewport breaks rows"
    calls = len(window.canvas.calls)
    window.reflow()
    assert len(window.canvas.calls) == calls, "an unchanged width does not relayout"


def test_scroll_when_resized_then_reflow_timer_started(tm_mod):
    window = make(tm_mod)
    started = window.reflow_timer.started
    window.scroll.viewportEvent(fq.FakeEvent(sys.modules["PythonQt"].QtCore.QEvent.Resize))
    assert window.reflow_timer.started == started + 1, "a viewport resize schedules a reflow"


def test_open_at_when_double_clicked_then_callback_gets_name(tm_mod):
    opened = []
    window = make(tm_mod, on_open=opened.append)
    click(window, 0, "open_at")
    assert opened == ["A"] and window.model.selected == 0, "double-click selects and opens"
    window.open_at(1, 1)
    assert opened == ["A"], "a miss opens nothing"


def test_open_at_when_callback_raises_or_glyph_missing_then_status_or_nothing(tm_mod):
    def boom(name):
        raise RuntimeError("no editor")

    window = make(tm_mod, "A?", on_open=boom)
    click(window, 0, "open_at")
    assert window.diagnostic.text == "Error: no editor", "callback errors go to the status"
    seen = []
    window.on_open_glyph = seen.append
    click(window, 1, "open_at")
    assert seen == [], "missing glyphs are not opened"


def test_paint_when_run_selected_then_guides_boxes_bearings_kerning_and_outlines(tm_mod):
    window = make(tm_mod, "AV?")
    window.model.font.info.xHeight = 500
    window.refresh()
    click(window, 0)
    tm_mod.paint(window, window.canvas)
    calls = [name for name, _ in Painter.log[-1].calls]
    assert calls[-1] == "end", "the painter is always ended"
    assert calls.count("drawLine") >= 4 + 4, "guides plus two bearing marks per glyph"
    assert "drawPath" in calls and calls.count("save") == calls.count("restore") == 2, "two outlines drawn"
    assert "drawText" in calls, "the missing glyph is labelled"
    assert calls.count("fillRect") >= 1 + 3 + 1, "background, three boxes and a kerning offset"


@pytest.fixture
def prepared_paint(tm_mod, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainterPath

    partitions, paths = [], []
    partition = tm_mod.partition_paths

    def counting(recording):
        partitions.append(recording)
        return partition(recording)

    def path():
        value = QPainterPath()
        paths.append(value)
        return value

    monkeypatch.setattr(tm_mod, "partition_paths", counting)
    monkeypatch.setattr(tm_mod.QtGui, "QPainterPath", path)
    monkeypatch.setattr(tm_mod.QtCore.Qt, "WindingFill", Qt.WindingFill, raising=False)
    return partitions, paths


@pytest.mark.parametrize(("text", "unique"), [("AAA", 1), ("AVA", 2)])
def test_paint_when_glyphs_repeat_then_prepare_once_and_draw_every_occurrence(tm_mod, prepared_paint, text, unique):
    partitions, paths = prepared_paint
    window = make(tm_mod, text)
    tm_mod.paint(window, window.canvas)
    calls = Painter.log[-1].calls
    draws = [args[0] for name, args in calls if name == "drawPath"]
    assert len(draws) == 3, "every occurrence still draws"
    assert len(partitions) == len(paths) == unique, "prepare once per unique recording per paint"
    assert draws[0] is draws[-1], "repeated occurrences reuse the prepared path"
    assert calls[-1][0] == "end" and sum(name == "restore" for name, _ in calls) == 3
    tm_mod.paint(window, window.canvas)
    assert len(partitions) == len(paths) == 2 * unique, "a second paint rebuilds all paths"
    assert Painter.log[-1].calls != []
    window.outlines["A"] = SimpleNamespace(recording=(("moveTo", ((11, 12),)), ("lineTo", ((31, 42),)), ("endPath", ())))
    tm_mod.paint(window, window.canvas)
    assert len(partitions) == len(paths) == 3 * unique, "replacement recordings prepare afresh"
    replacement = [args[0] for name, args in Painter.log[-1].calls if name == "drawPath"][0]
    assert (replacement.boundingRect().x(), replacement.boundingRect().y(), replacement.boundingRect().width(), replacement.boundingRect().height()) == (11, 12, 20, 30)


@pytest.mark.parametrize("empty", [False, True])
def test_paint_when_reused_paths_then_geometry_colors_offsets_and_empty_are_preserved(tm_mod, prepared_paint, monkeypatch, empty):
    from dataclasses import replace

    partitions, paths = prepared_paint
    window = make(tm_mod, "AAA")
    recording = () if empty else (("moveTo", ((0, 0),)), ("lineTo", ((100, 200),)), ("lineTo", ((200, 0),)), ("closePath", ()), ("moveTo", ((300, 400),)), ("lineTo", ((500, 600),)), ("endPath", ()))
    window.outlines["A"] = SimpleNamespace(recording=recording)
    window.model.cells = [replace(cell, x_offset=17 + cell.index, y_offset=23 + cell.index) for cell in window.model.cells]
    window.model.selected = 1
    monkeypatch.setattr(tm_mod, "_canvas_colors", lambda *_: {**tm_mod.COLORS, "selection_background": "#123456", "selection_foreground": "#abcdef"})
    tm_mod.paint(window, window.canvas)
    calls = Painter.log[-1].calls
    assert len(partitions) == 1, "even empty recordings prepare only once"
    assert len(paths) == (0 if empty else 2)
    assert [args for name, args in calls if name == "translate"] == [(x + cell.x_offset * window.layout_geometry.scale, baseline - cell.y_offset * window.layout_geometry.scale) for cell, (x, baseline) in zip(window.model.cells, window.layout_geometry.origins)]
    assert [args for name, args in calls if name == "scale"] == [(window.layout_geometry.scale, -window.layout_geometry.scale)] * 3
    assert sum(name == "save" for name, _ in calls) == sum(name == "restore" for name, _ in calls) == 3
    if not empty:
        assert [(p.boundingRect().x(), p.boundingRect().y(), p.boundingRect().width(), p.boundingRect().height()) for p in paths] == [(0, 0, 200, 200), (300, 400, 200, 200)]
        assert [[(p.elementAt(i).x, p.elementAt(i).y) for i in range(p.elementCount())] for p in paths] == [[(0, 0), (100, 200), (200, 0), (0, 0)], [(300, 400), (500, 600)]]
        assert all(p.fillRule() == tm_mod.QtCore.Qt.WindingFill for p in paths)
        brushes = [args[0].args for name, args in calls if name == "setBrush"]
        assert [args[0].text if args else None for args in brushes] == [tm_mod.COLORS["glyph"], None, "#abcdef", None, tm_mod.COLORS["glyph"], None]
        pens = [args[0] for name, args in calls if name == "setPen"]
        outline_pens = [pen for pen in pens if ("setWidthF", (1.0 / window.layout_geometry.scale,)) in pen.calls]
        assert [pen.args[0].text for pen in outline_pens] == [tm_mod.COLORS["glyph"], "#abcdef", tm_mod.COLORS["glyph"]]
        assert [args[0] for name, args in calls if name == "drawPath"] == paths * 3
    assert calls[-1][0] == "end"


@pytest.mark.parametrize("failure", ["partition", "replay", "draw"])
def test_paint_when_path_preparation_or_reused_draw_fails_then_restores_and_ends(tm_mod, prepared_paint, monkeypatch, failure):
    window = make(tm_mod, "AAA")

    def boom(*args):
        raise RuntimeError("outline failed")

    if failure == "partition":
        monkeypatch.setattr(tm_mod, "partition_paths", boom)
    elif failure == "replay":
        import fontTools.pens.recordingPen as recording
        monkeypatch.setattr(recording, "replayRecording", boom)
    else:
        draw = Painter._record("drawPath")
        def fail_second(self, *args):
            if any(name == "drawPath" for name, _ in self.calls):
                boom()
            draw(self, *args)
        monkeypatch.setattr(Painter, "drawPath", fail_second, raising=False)
    tm_mod.paint(window, window.canvas)
    calls = Painter.log[-1].calls
    assert window.diagnostic.text == "Error: outline failed"
    assert sum(name == "save" for name, _ in calls) == sum(name == "restore" for name, _ in calls)
    assert calls[-1][0] == "end"


def test_paint_when_drawing_fails_then_status_and_painter_ended(tm_mod, monkeypatch):
    window = make(tm_mod)
    monkeypatch.setattr(tm_mod, "_paint_guides", lambda *args: (_ for _ in ()).throw(ValueError("bad")))
    tm_mod.paint(window, window.canvas)
    assert window.diagnostic.text == "Error: bad", "paint errors go to the status"
    assert Painter.log[-1].calls[-1][0] == "end", "the painter is ended after a failure"


def test_canvas_events_when_pressed_then_forwarded_and_accepted(tm_mod):
    window = make(tm_mod)
    x, _ = window.layout_geometry.origins[1]
    pos = SimpleNamespace(x=lambda: x + 1, y=lambda: window.layout_geometry.row_top(0) + 5)
    accepted = []
    event = SimpleNamespace(pos=lambda: pos, accept=lambda: accepted.append(True))
    window.canvas.mousePressEvent(event)
    assert window.model.selected == 1, "a press selects"
    window.canvas.mouseDoubleClickEvent(event)
    window.canvas.paintEvent(None)
    assert accepted == [True, True], "mouse events are accepted"
    broken = SimpleNamespace(pos=lambda: None, accept=lambda: accepted.append(True))
    window.canvas.mousePressEvent(broken)
    window.canvas.mouseDoubleClickEvent(broken)
    assert window.diagnostic.text.startswith("Error:"), "event errors go to the status"


def test_refresh_when_controls_fail_then_status_reports(tm_mod, monkeypatch):
    window = make(tm_mod)
    monkeypatch.setattr(window.model, "reshape", lambda: (_ for _ in ()).throw(RuntimeError("font gone")))
    window.refresh()
    assert window.diagnostic.text == "Error: font gone", "refresh errors go to the status"
    monkeypatch.setattr(window.model, "set_wrap_width", lambda width: (_ for _ in ()).throw(RuntimeError("w")))
    window.reflow()
    assert window.diagnostic.text == "Error: w", "reflow errors go to the status"


def test_close_when_called_twice_then_callbacks_dropped_and_inert(tm_mod):
    window = make(tm_mod, on_open=print)
    window.close()
    window.close()
    assert window.closed and window.on_open_glyph is None, "close drops the callback"
    assert window.connections == [], "every owned connection is released"
    window.refresh()
    window.reflow()
    window.select_at(0, 0)
    window.open_at(0, 0)
    assert window.select_key("Key_Left") is False, "a closed window ignores input"
    window.fail(RuntimeError("late"))
    assert window.diagnostic.text != "Error: late", "a closed window keeps its last status"


def test_live_follow_when_fontlab_present_then_change_and_history_hooks_armed(tm_mod, monkeypatch):
    lifecycle = sys.modules["fontlabapp.fontui.lifecycle"]
    seen = []
    monkeypatch.setattr(lifecycle, "follow_changes", lambda owner, callback, fonts: seen.append(("changes", fonts())))
    monkeypatch.setattr(lifecycle, "follow_history", lambda owner, callback: seen.append(("history", callback)))
    window = make(tm_mod)
    assert seen[0] == ("changes", [window.font]), "font changes are followed for this font"
    assert seen[1][0] == "history" and seen[1][1] == window.follow, "Undo/Redo go through the echo-aware follow"
    assert lifecycle.follow_changes is not None, "the lifecycle helpers are the follow route"


def test_show_tmetrics_when_font_given_then_window_shown(tm_mod):
    window = tm_mod.show_tmetrics(font(), "AV")
    assert window.widget.calls and window.text_control.text == "AV", "the window is shown with the text"
    assert ("setWindowTitle", ("TMetrics",)) in window.widget.calls, "the title is set"


def test_show_tmetrics_when_no_font_then_message_and_none(tm_mod, monkeypatch, capsys):
    monkeypatch.setattr(tm_mod, "_current_font", lambda: None)
    assert tm_mod.show_tmetrics() is None, "no current font returns None"
    assert tm_mod.NO_FONT_MESSAGE in capsys.readouterr().out, "the message falls back to print"
    monkeypatch.setattr(tm_mod, "_current_font", lambda: (_ for _ in ()).throw(ImportError("no fontport")))
    assert tm_mod.show_tmetrics() is None, "an unresolvable font returns None"


def test_show_tmetrics_when_current_font_resolves_then_it_is_used(tm_mod, monkeypatch):
    current = font()
    monkeypatch.setattr(tm_mod, "_current_font", lambda: current)
    window = tm_mod.show_tmetrics(text="A")
    assert window.font is current, "the current font is shown"


def test_show_tmetrics_when_show_fails_then_window_closed_and_error_raised(tm_mod, monkeypatch):
    monkeypatch.setattr(fq.FakeWidget, "setWindowTitle", lambda self, title: (_ for _ in ()).throw(RuntimeError("x")), raising=False)
    with pytest.raises(RuntimeError):
        tm_mod.show_tmetrics(font(), "A")


def test_current_font_when_fontworld_used_then_it_is_created_once(tm_mod, monkeypatch):
    created = []

    class World:
        def __init__(self):
            created.append(self)

        def CurrentFont(self):
            return "font"

    world_module = SimpleNamespace(FontWorld=World)
    monkeypatch.setitem(sys.modules, "fontlab_fontport.world", world_module)
    monkeypatch.setattr(tm_mod, "_WORLD", [])
    assert tm_mod._current_font() == "font" and tm_mod._current_font() == "font", "the current font is returned"
    assert len(created) == 1, "the world is created once"


def test_notify_when_fontlab_present_then_message_box_used(tm_mod, monkeypatch):
    shown = []
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(MainWindow=lambda: "main"))
    dialogs = sys.modules.get("fontlabapp.qt.dialogs") or __import__("fontlabapp.qt.dialogs", fromlist=["x"])
    monkeypatch.setattr(dialogs, "create_message_box", lambda *args, **kwargs: ("box", args))
    monkeypatch.setattr(dialogs, "run_message_box", lambda box, buttons: shown.append(box))
    tm_mod._notify("hello")
    assert shown and shown[0][1][2] == "hello", "the message box carries the text"


def test_select_key_when_geometry_stale_after_failed_refresh_then_no_raise(tm_mod):
    window = make(tm_mod)
    qt = sys.modules["PythonQt"].QtCore.Qt
    window.select_key(qt.Key_Right)
    window.layout_geometry = window.layout_geometry.__class__(**{**window.layout_geometry.__dict__, "origins": []})
    assert window.select_key(qt.Key_Right) is True, "stale origins are tolerated"
    window.model.move = lambda step: (_ for _ in ()).throw(RuntimeError("boom"))
    assert window.select_key(qt.Key_Left) is False, "a failing move does not raise"
    assert window.diagnostic.text == "Error: boom", "the failure reaches the status"


def test_refresh_when_failing_then_good_then_scroll_preserved(tm_mod):
    window = make(tm_mod)
    bars = window.scroll.horizontalScrollBar(), window.scroll.verticalScrollBar()
    bars[0].value, bars[1].value = 7, 42
    original = window.canvas.resize

    def clamping(w, h):
        original(w, h)
        for bar in bars:
            bar.value = 0

    window.canvas.resize = clamping
    window.refresh()
    assert (bars[0].value, bars[1].value) == (7, 42), "scroll survives a relayout"
    good = window.model.reshape
    window.model.reshape = lambda: (_ for _ in ()).throw(RuntimeError("bad"))
    window.refresh()
    assert window.diagnostic.text == "Error: bad", "the refresh failed"
    assert (bars[0].value, bars[1].value) == (7, 42), "scroll survives a failing refresh"
    window.model.reshape = good
    window.refresh()
    assert (bars[0].value, bars[1].value) == (7, 42), "scroll survives the next good refresh"


def test_paint_when_painter_construction_raises_then_status_not_exception(tm_mod, monkeypatch):
    window = make(tm_mod)

    def boom(*args):
        raise RuntimeError("no painter")

    monkeypatch.setattr(sys.modules["PythonQt"].QtGui, "QPainter", boom)
    tm_mod.paint(window, window.canvas)
    assert window.diagnostic.text == "Error: no painter", "painter failure is reported, not raised"


# --- Task 3: write-back, nudges and echo suppression -----------------------

from _tmetrics_fakes import EditableFont  # noqa: E402

ALT, CTRL, SHIFT, META = (MODIFIERS[n] for n in ("AltModifier", "ControlModifier", "ShiftModifier", "MetaModifier"))


def editable(module: Any, text: str = "AV", select: int | None = 1):
    window = module.TMetrics(EditableFont(), None, None, text)
    window.scroll.viewport().width = 800
    window.refresh()
    if select is not None:
        window.model.select(select)
        window._show_selection()
    return window


def test_edit_fields_when_glyph_selected_then_show_metrics_and_pair(tm_mod):
    window = editable(tm_mod)
    assert window.metric_controls["width"].text == "600", "width field follows the selection"
    assert window.metric_controls["rsb"].text == "0", "RSB field follows the selection"
    assert window.kern_control.text == "-80", "kerning field shows the pair before the glyph"
    assert "Alt+Left/Right" in window.help.text and "Ctrl+Alt+Left/Right" in window.help.text, "bindings documented"
    assert "Control+Option" in window.help.text and "Command+Option" in window.help.text, "macOS keys named"


def test_commit_when_rsb_entered_then_one_named_write_and_readout_updates(tm_mod):
    window = editable(tm_mod)
    control = window.metric_controls["rsb"]
    control.setText("40")
    control.returnPressed.emit()
    assert window.font.edits == [("V", "public.default", "TMetrics: RSB V")], "one edit_glyph on the explicit layer"
    assert window.readout.text == "V  advance 640  LSB 0  RSB 40", "readout follows the write"
    assert window.diagnostic.text == "Set RSB of V to 40.", "the status reports the write"
    assert window.echo.token == window.model.fingerprint(), "the own write is recorded for echo suppression"


def test_commit_when_lsb_and_width_entered_then_written_with_undo_names(tm_mod):
    window = editable(tm_mod)
    assert window.commit("lsb", "25") is True, "LSB written"
    assert window.readout.text == "V  advance 625  LSB 25  RSB 0", "LSB keeps RSB"
    assert window.commit("width", "700") is True, "width written"
    assert [e[2] for e in window.font.edits] == ["TMetrics: LSB V", "TMetrics: width V"], "undo names per action"


def test_commit_when_value_unchanged_then_no_write(tm_mod):
    window = editable(tm_mod)
    assert window.commit("width", "600") is False, "unchanged width"
    assert window.diagnostic.text == "No changes to apply." and window.font.edits == [], "nothing written"


@pytest.mark.parametrize("text", ["abc", "inf"])
def test_commit_when_bad_text_then_error_and_model_unchanged(tm_mod, text):
    window = editable(tm_mod)
    before = window.model.fingerprint()
    assert window.commit("rsb", text) is False, "bad input refused"
    assert window.diagnostic.text.startswith("Error:"), "the failure is in the diagnostic line"
    assert window.model.fingerprint() == before and window.font.edits == [], "model unchanged"


def test_commit_when_backend_refuses_then_error_and_no_echo_token(tm_mod):
    window = editable(tm_mod)
    window.font.fail = ValueError("history scope refused")
    assert window.commit("rsb", "30") is False, "guard refusal reported"
    assert window.diagnostic.text == "Error: history scope refused", "guard message shown"
    assert window.echo.token is None, "a failed write records no token"
    assert window.readout.text == "V  advance 600  LSB 0  RSB 0", "readout unchanged"


def test_commit_when_nothing_selected_or_no_pair_then_error(tm_mod):
    window = editable(tm_mod, select=None)
    assert window.commit("rsb", "5") is False and window.diagnostic.text == "Error: Select a glyph first.", "needs a glyph"
    window.model.select(0)
    assert window.commit("kerning", "5") is False and window.diagnostic.text.startswith("Error: "), "first glyph has no pair"


def test_commit_when_font_read_only_then_error(tm_mod):
    window = tm_mod.TMetrics(font(), None, None, "AV")
    window.scroll.viewport().width = 800
    window.refresh()
    window.model.select(1)
    assert window.commit("rsb", "5") is False, "read-only font refused"
    assert "Read-only" in window.diagnostic.text, "read-only reason shown"


def test_commit_when_kerning_entered_then_group_key_applied_and_read_back(tm_mod):
    window = editable(tm_mod)
    window.kern_control.setText("-50")
    window.kern_control.returnPressed.emit()
    assert dict(window.font.kerning) == {("public.kern1.A", "public.kern2.V"): -50}, "the effective group key is edited"
    assert window.font.kerning.undo_names == ["TMetrics: kerning A V"], "kerning undo name"
    assert window.diagnostic.text == "Kerning public.kern1.A/public.kern2.V (group pair for A V): -50.", (
        "status names the actual group keys"
    )
    assert window.pair_readout.text.startswith("Pair A V: -50"), "readout follows"


def test_commit_when_kerning_cleared_then_pair_removed(tm_mod):
    window = editable(tm_mod)
    assert window.commit("kerning", "") is True, "empty text deletes the pair"
    assert dict(window.font.kerning) == {}, "pair removed"
    assert window.diagnostic.text.endswith(": removed."), "status says removed"
    assert window.commit("kerning", " ") is False and window.diagnostic.text == "No changes to apply.", "nothing to remove"


def test_commit_when_kerning_readback_differs_then_error(tm_mod, monkeypatch):
    window = editable(tm_mod)
    monkeypatch.setattr(window.font.kerning, "apply", lambda values, *, undo_name: None)
    before = window.model.fingerprint()
    assert window.commit("kerning", "-10") is False, "readback mismatch refused"
    assert "readback" in window.diagnostic.text and window.echo.token is None, "error shown, no token"
    assert window.model.fingerprint() == before, "model unchanged"


def test_commit_when_new_glyph_pair_then_glyph_key_created(tm_mod):
    window = editable(tm_mod, text="VA")
    assert window.commit("kerning", "12") is True, "a pair without kerning is created"
    assert window.font.kerning[("V", "A")] == 12, "glyph-glyph key added"
    assert window.diagnostic.text == "Kerning V A: 12.", "a glyph pair keeps the plain status"


@pytest.mark.parametrize(
    ("modifiers", "target", "expected"),
    [
        (ALT, "rsb", 1),
        (ALT | SHIFT, "rsb", 10),
        (ALT | CTRL, "kerning", -79),
        (ALT | META, "kerning", -79),
        (ALT | CTRL | SHIFT, "kerning", -70),
    ],
)
def test_key_press_when_alt_right_then_nudges(tm_mod, modifiers, target, expected):
    window = editable(tm_mod)
    assert window.key_press("Key_Right", modifiers) is True, "nudge keys are handled"
    if target == "rsb":
        assert window.readout.text.endswith(f"RSB {expected}"), "RSB nudged"
    else:
        assert window.font.kerning[("public.kern1.A", "public.kern2.V")] == expected, "kerning nudged"


def test_key_press_when_alt_left_or_other_key_then_decrease_or_ignore(tm_mod):
    window = editable(tm_mod)
    assert window.key_press("Key_Left", ALT | SHIFT) is True and window.readout.text.endswith("RSB -10"), "left decreases"
    assert window.key_press("Key_Up", ALT) is False, "other Alt keys are not handled"
    assert window.key_press("Key_Left") is True and window.model.selected == 0, "plain arrows still select"
    assert window.key_press("Key_Right", "bogus") is True, "unreadable modifiers fall back to selection"


def test_canvas_key_event_when_alt_right_then_rsb_nudged(tm_mod):
    window = editable(tm_mod)
    event = SimpleNamespace(key=lambda: "Key_Right", modifiers=lambda: ALT, accept=lambda: None, ignore=lambda: None)
    window.canvas.keyPressEvent(event)
    assert window.readout.text.endswith("RSB 1"), "the canvas forwards modifiers"


def test_nudge_when_empty_glyph_then_error(tm_mod):
    window = editable(tm_mod, select=None)
    window.font.ufo.newGlyph("space").width = 200
    window.text_control.setText("/space")
    window.model.select(0)
    assert window.nudge("rsb", 1) is False, "empty glyph refused"
    assert "no outline" in window.diagnostic.text, "reason shown"


def test_written_when_font_moves_after_draw_then_token_is_drawn_state(tm_mod, monkeypatch):
    window = editable(tm_mod)
    window.refresh()
    assert window.drawn == window.model.fingerprint(), "refresh keeps the fingerprint of what it drew"
    drawn = window.drawn
    monkeypatch.setattr(window, "refresh", lambda: None)
    window.font.ufo["V"].width = 900
    window._written("done", "")
    assert window.echo.token == drawn != window.model.fingerprint(), "token comes from the drawn state, not a fresh read"


def test_follow_when_own_write_echoes_then_reset_skipped(tm_mod, monkeypatch):
    window = editable(tm_mod)
    window.commit("rsb", "40")
    calls = []
    monkeypatch.setattr(window, "refresh", lambda: calls.append("refresh"))
    window.follow()
    window.follow()
    assert calls == [], "matching fingerprint skips the full reset"


def test_follow_when_external_change_then_refresh(tm_mod, monkeypatch):
    window = editable(tm_mod)
    window.commit("rsb", "40")
    window.font.ufo["V"].width = 900
    calls = []
    # follow() re-shapes from the reads its fingerprint just made (no second whole-font read).
    monkeypatch.setattr(window, "refresh", lambda: calls.append("refresh"))
    monkeypatch.setattr(window, "_reshape", lambda: calls.append("reshape"))
    window.follow()
    assert calls == ["reshape"], "an external change re-shapes once"
    window.font.ufo["V"].width = 640
    window.follow()
    assert calls == ["reshape", "reshape"], "a stale token after a second external change re-shapes"


def test_follow_when_refresh_raises_or_closed_then_safe(tm_mod, monkeypatch):
    window = editable(tm_mod)
    monkeypatch.setattr(window.model, "fingerprint", lambda: (_ for _ in ()).throw(RuntimeError("gone")))
    window.follow()
    assert window.diagnostic.text == "Error: gone", "follow failures reach the status line"
    window.close()
    window.follow()
    assert window.commit("rsb", "1") is False and window.nudge("rsb", 1) is False, "closed window ignores writes"
    assert window.key_press("Key_Right", ALT) is False, "closed window ignores keys"


def test_pending_note_when_updates_queued_then_disclosed(tm_mod, monkeypatch):
    import fontlabapp.core.edit_guards as edit_guards

    monkeypatch.setattr(edit_guards, "pending_updates", lambda: ["g1"])
    monkeypatch.setattr(edit_guards, "pending_note", lambda ids: "Note: 1 queued update.")
    window = editable(tm_mod)
    window.commit("rsb", "3")
    assert window.diagnostic.text == "Set RSB of V to 3. Note: 1 queued update.", "pending updates disclosed"


def test_commit_when_backend_refuses_fractional_kerning_then_capability_message_shown(tm_mod, monkeypatch):
    """Live FontLab 9 (Fontport write_kerning): fractional values raise UnsupportedCapability
    ``kerning.fractionalHistory`` before any readback, so TMetrics only has to surface it."""
    unsupported = pytest.importorskip("fontlab_fontport.errors").UnsupportedCapability
    assert issubclass(unsupported, NotImplementedError), "real backend type is a NotImplementedError"
    window = editable(tm_mod)

    def refuse(values, *, undo_name):
        raise unsupported("kerning.fractionalHistory", "Native kerning history rounds fractional values")

    monkeypatch.setattr(window.font.kerning, "apply", refuse)
    assert window.commit("kerning", "-12.5") is False, "fractional kerning refused"
    assert "fractionalHistory" in window.diagnostic.text, "backend reason shown verbatim"
    assert "readback" not in window.diagnostic.text, "the refusal precedes any readback"
    assert window.echo.token is None, "no echo token recorded"


def test_embed_when_controls_hidden_then_no_outer_margins_spacing_or_scroll_frame(tm_mod):
    window = tm_mod.TMetrics(font(), text="AV", controls=False)
    assert ("setContentsMargins", (0, 0, 0, 0)) in window.layout.calls
    assert ("setSpacing", (0,)) in window.layout.calls
    assert ("setFrameShape", (tm_mod.QtGui.QFrame.NoFrame,)) in window.scroll.calls
    assert window.diagnostic.shown and window.readout.shown and window.pair_readout.shown
    window.close()
