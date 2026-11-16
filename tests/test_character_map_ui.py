# this_file: tests/test_character_map_ui.py
"""Real Qt events, complete profile distinctions and an owned clipboard sink."""

import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.glyphs.character_map.model import Glyph, Snapshot
from fontlabapp.glyphs.character_map.fonts import change
from fontlabapp.glyphs.character_map.ui import panel_type
from test_spacing_worksheet import GUI, QtCore, QTest, drain, valid


def facts():
    return Snapshot(
        (7, 70, "Regular"),
        (Glyph(1, "A", (65, 0x1F600)), Glyph(2, "A.alt", (65,)), Glyph(3, "space", ())),
    )


@pytest.fixture(params=[2, 3])
def panel(request):
    state = NS(capture=Mock(return_value=facts()), sink=NS(setText=Mock()))
    p = panel_type(QtCore, GUI, request.param)(None, state.capture, state.sink)
    p.show()
    drain()
    yield p, state
    if valid(p):
        p.close()
    drain()


def click(p, code, button=None):
    QTest.mouseClick(
        p.grid,
        button or QtCore.Qt.LeftButton,
        pos=QtCore.QPoint(
            (code % 16) * p.grid.cell + 2, (code // 16) * p.grid.cell + 2
        ),
    )


def test_defaults_and_real_coverage(panel):
    p, s = panel
    assert p.merging.isChecked() and p.grid.last_key == -1
    assert p.grid.sizeHint() == QtCore.QSize(p.grid.cell * 16, p.grid.cell * 4096)
    assert p.text.maxLength() == 32767 and p.facts == facts()
    assert p.grid.cell == (36 if p.part == 2 else 24)
    if p.part == 2:
        assert (
            p.size_control.minimum(),
            p.size_control.maximum(),
            p.size_control.value(),
        ) == (6, 72, 14)
        assert [p.style_control.itemText(i) for i in range(3)] == [
            "Regular",
            "Bold",
            "Italic",
        ]
    else:
        assert isinstance(p, GUI.QMainWindow)
    assert (
        "3 glyphs" in p.output.toPlainText() and "1 unencoded" in p.output.toPlainText()
    )
    p.text.setText("A😀BA")
    assert (
        "2: U+1F600 → A" in p.output.toPlainText()
        and "3: U+0042 → MISSING" in p.output.toPlainText()
    )
    assert "A, A.alt" in p.grid.tooltip(65) and "missing" in p.grid.tooltip(66)
    assert not s.sink.setText.called


def test_mouse_selection_and_utf16_native_insertion(panel):
    p, s = panel
    p.text.setText("A😀B")
    p.text.setSelection(1, 2)
    click(p, 65)
    assert p.text.text() == ("A😀BA" if p.part == 2 else "AAB")
    before = p.text.text()
    click(p, 65, QtCore.Qt.RightButton)
    assert p.text.text() == (before + "A" if p.part == 2 else before)
    before = p.text.text()
    click(p, 0x378)
    assert p.text.text() == before
    assert p.grid.last_key == (65 if p.part == 2 else 0x378)
    click(p, 0xD800)
    assert p.text.text() == before
    if p.part == 3:
        assert "Surrogate" in p.last_error and p.grid.last_key == 0xD800
    p.text.setText("😀")
    p.copy()
    calls = list(s.sink.setText.call_args_list)
    assert len(calls) == (1 if p.part == 2 else 2)
    assert calls[0].args == ("😀", GUI.QClipboard.Clipboard)
    if p.part == 3:
        assert calls[1].args == ("😀", GUI.QClipboard.Selection)
    p.text.setMaxLength(1)
    p.text.setText("😀")
    # PyQt5 preserves the lone UTF16 unit; PySide6 converts it to an empty Python string.
    original = p.text
    p.text = NS(text="\ud83d")
    p.copy()
    p.text = original
    assert (
        len(s.sink.setText.call_args_list) == len(calls)
        and "incomplete Unicode" in p.last_error
    )


def emit_text(widget, name, text):
    signal = getattr(widget, name)
    try:
        signal[str].emit(text)
    except (IndexError, KeyError, TypeError):
        signal.emit(widget.currentIndex())


def test_every_typography_control_and_distinct_activation(panel):
    p, _ = panel
    if p.part == 2:
        for size in (6, 72, 14):
            p.size_control.setValue(size)
            assert p.grid.cell == max(20, size * 2 + 8)
        for style in range(3):
            p.style_control.setCurrentIndex(style)
            assert p.grid.display_font.bold() == (style == 1)
            assert p.grid.display_font.italic() == (style == 2)
        p.family.setCurrentFont(GUI.QFont("Times"))
        assert p.grid.display_font.family() == p.family.currentFont().family()
    else:
        oldfont = GUI.QFont(p.grid.display_font)
        oldcell = p.grid.cell
        sizes = [p.size_control.itemText(i) for i in range(p.size_control.count())]
        p.family.setCurrentFont(GUI.QFont("Times"))
        assert p.grid.display_font == oldfont and p.grid.cell == oldcell
        assert [
            p.size_control.itemText(i) for i in range(p.size_control.count())
        ] == sizes
        emit_text(p.family, "activated", p.family.currentText())
        assert p.grid.display_font.family() == p.family.currentText()
        emit_text(p.style_control, "activated", p.style_control.currentText())
        p.size_control.setCurrentIndex(
            (p.size_control.currentIndex() + 1) % p.size_control.count()
        )
        assert p.grid.display_font.pointSize() == int(p.size_control.currentText())
        before = p.grid.display_font.pointSize()
        p.size_control.setEditText("17")
        assert p.grid.display_font.pointSize() == before
        QTest.keyClick(p.size_control, QtCore.Qt.Key_Return)
        assert p.grid.display_font.pointSize() == 17
        change(p, GUI, "size", "bad")
        assert "integer" in p.last_error
    cell = p.grid.cell
    p.merging.setChecked(False)
    assert p.grid.display_font.styleStrategy() == GUI.QFont.NoFontMerging
    if p.part == 3:
        assert p.grid.cell == cell
        emit_text(p.style_control, "activated", p.style_control.currentText())
        assert p.grid.display_font.styleStrategy() == GUI.QFont.NoFontMerging
    p.merging.setChecked(True)
    assert p.grid.display_font.styleStrategy() == GUI.QFont.PreferDefault


def test_refresh_failure_does_not_replace_user_text_or_reference_face(panel):
    p, s = panel
    p.text.setText("B😀")
    font = GUI.QFont(p.grid.display_font)
    s.capture.side_effect = ValueError("font changed")
    p.refresh()
    assert (
        p.facts is None
        and not p.assignments
        and "unavailable" in p.output.toPlainText()
    )
    assert p.text.text() == "B😀" and p.grid.display_font == font
    assert "unavailable" in p.grid.tooltip(65)
    s.capture.side_effect = None
    p.refresh()
    assert p.facts == facts() and "MISSING" in p.output.toPlainText()


@pytest.mark.parametrize("terminal", ["close", "escape", "parent"])
def test_lifetime_and_late_callbacks(panel, terminal):
    p, s = panel
    slots = [slot for _, slot, _ in p.scope.records]
    sys.__dict__.setdefault("_fontlab_samples", {})[p.key] = p
    if terminal == "parent":
        parent = GUI.QWidget()
        p.setParent(parent)
        parent.deleteLater()
    elif terminal == "escape":
        QTest.keyClick(p, QtCore.Qt.Key_Escape)
    else:
        p.close()
    drain()
    assert (
        not valid(p)
        and p.closed
        and p.dead
        and not p.scope.records
        and not p.terminal.records
    )
    assert p.key not in sys._fontlab_samples
    count = s.capture.call_count
    for slot in slots:
        slot(1)
    p.copy()
    p.refresh()
    p.changed()
    assert s.capture.call_count == count and not s.sink.setText.called


def test_real_paint_clipping_and_surrogate_refusal(panel):
    p, _ = panel
    pix = p.grid.grab(QtCore.QRect(0, 4 * p.grid.cell, 16 * p.grid.cell, p.grid.cell))
    assert not pix.isNull() and not p.last_error
    p.grid.last_key = 0xD800
    pix = p.grid.grab(
        QtCore.QRect(0, (0xD800 // 16) * p.grid.cell, 16 * p.grid.cell, p.grid.cell)
    )
    assert not pix.isNull() and not p.last_error
    assert (
        "Surrogate" in p.grid.tooltip(0xD800)
        if p.part == 3
        else "Unassigned" in p.grid.tooltip(0xD800)
    )


def test_lazy_public_entrypoints_and_bad_profiles(monkeypatch):
    import fontlabapp
    import fontlabapp.glyphs.character_map.model as api
    import fontlabapp.glyphs.character_map.capture as source
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(
        fontlabapp, "_native", lambda name: NS(QtCore=QtCore, QtGui=GUI)
    )
    monkeypatch.setattr(source, "capture", facts)
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda factory, key: (key, factory(None))
    )
    for show, part in ((api.show, 2), (api.show_official, 3)):
        key, p = show()
        assert key == f"character_map_{part}" and p.facts == facts()
        p.close()
        drain()
    monkeypatch.setattr(api, "current_thread", lambda: None)
    with pytest.raises(RuntimeError):
        api.show()
    with pytest.raises(ValueError):
        panel_type(QtCore, GUI, 7)
    with pytest.raises(ValueError):
        api.codepoint_at(7, 0, 0, 24)
    with pytest.raises(ValueError):
        api.selectable(7, 65)
    assert api.codepoint_at(2, 0, 0, 0) is None
    assert not api.selectable(2, -1) and not api.selectable(3, 65536)


def test_tooltip_events_and_invalid_or_failed_clicks(panel, monkeypatch):
    p, _ = panel
    sink = Mock()
    monkeypatch.setattr(GUI.QToolTip, "showText", sink)
    point = QtCore.QPoint(p.grid.cell + 2, 4 * p.grid.cell + 2)
    event = NS(pos=lambda: point, globalPos=lambda: p.grid.mapToGlobal(point))
    p.grid.mouseMoveEvent(event)
    assert sink.called and "FontLab" in sink.call_args.args[1]
    bad = NS(
        pos=lambda: QtCore.QPoint(-1, -1),
        globalPos=lambda: p.grid.mapToGlobal(QtCore.QPoint(-1, -1)),
    )
    sink.reset_mock()
    p.grid.mouseMoveEvent(bad)
    assert not sink.called
    p.grid.mouseMoveEvent(
        NS(
            globalPos=Mock(side_effect=ValueError("mouse failed")),
            pos=Mock(side_effect=ValueError("mouse failed")),
        )
    )
    assert "mouse failed" in p.last_error
    p.grid.mousePressEvent(NS(button=lambda: QtCore.Qt.LeftButton, x=-1, y=-1))
    p.grid.mousePressEvent(
        NS(
            button=Mock(side_effect=ValueError("press failed")),
            x=Mock(side_effect=ValueError("press failed")),
            y=0,
        )
    )
    assert "press failed" in p.last_error
    p.closed = True
    p.grid.mouseMoveEvent(event)
    p.grid.mousePressEvent(event)
    p.grid.paintEvent(None)
    p.closed = False


def test_disconnect_retry_close_failure_and_diagnostic_containment(panel, monkeypatch):
    p, _ = panel
    finish = p.scope.finish
    monkeypatch.setattr(p.scope, "finish", Mock(return_value=False))
    assert not p.close() and p.closed and valid(p)
    monkeypatch.setattr(p.scope, "finish", finish)
    original = p.dispose
    monkeypatch.setattr(p, "dispose", Mock(side_effect=ValueError("disconnect failed")))
    assert not p.close() and "disconnect failed" in p.last_error
    monkeypatch.setattr(p, "dispose", original)
    status = p.status
    p.status = NS(setText=Mock(side_effect=ValueError("lost label")))
    p.failure(ValueError("failed"))
    assert "status unavailable" in p.last_error
    p.status = status
    QTest.keyClick(p, QtCore.Qt.Key_A)
    assert p.close()


def test_close_during_capture_and_constructor_failure(panel, monkeypatch):
    p, s = panel
    s.capture.side_effect = lambda: (p.close(), facts())[1]
    p.refresh()
    assert p.closed and p.facts is None
    import fontlabapp.glyphs.character_map.ui as module

    dead = []

    def broken(owner, *args):
        owner.destroyed.connect(lambda *args: dead.append(True))
        raise ValueError("build failed")

    monkeypatch.setattr(module, "build", broken)
    with pytest.raises(ValueError, match="build failed"):
        module.panel_type(QtCore, GUI, p.part)(None, facts, NS(setText=Mock()))
    drain()
    assert dead == [True]


def test_native_string_overload_exact_pairs_and_failed_disconnect():
    from fontlabapp.glyphs.character_map.fonts import TextSignal

    Native = type("QComboBox", (), {"__module__": "PythonQt.QtGui"})
    obj = Native()
    obj.activated = object()
    obj.connect = Mock()
    obj.disconnect = Mock()
    signal = TextSignal(obj, "activated")
    slot = Mock()
    signal.connect(slot)
    signal.disconnect(slot)
    obj.connect.assert_called_once_with("activated(QString)", slot)
    obj.disconnect.assert_called_once_with("activated(QString)", slot)
    combo = GUI.QComboBox()
    combo.addItems(["a", "b"])
    signal = TextSignal(combo, "currentIndexChanged")
    signal.connect(slot)
    combo.setCurrentIndex(1)
    assert slot.call_args.args == ("b",)
    signal.disconnect(slot)
    count = slot.call_count
    combo.setCurrentIndex(0)
    assert slot.call_count == count and not signal.slots
    combo.deleteLater()
    drain()


def test_paint_failure_always_ends_owned_painter(panel, monkeypatch):
    p, _ = panel
    import fontlabapp.glyphs.character_map.paint as paint

    painter = NS(
        setFont=Mock(side_effect=ValueError("paint failed")),
        isActive=lambda: True,
        end=Mock(),
    )
    gui = NS(QPainter=lambda grid: painter)
    paint.draw(p.grid, None, QtCore, gui)
    assert "paint failed" in p.last_error and painter.end.call_count == 1
    painter.end.side_effect = ValueError("end failed")
    paint.draw(p.grid, None, QtCore, gui)
    assert "end failed" in p.last_error
    with pytest.raises(ValueError):
        change(p, GUI, "unknown", 0)


def test_owned_attributes_do_not_shadow_inherited_native_widget_members():
    import ast
    from pathlib import Path

    import fontlabapp.glyphs.character_map.controls as controls
    import fontlabapp.glyphs.character_map.ui as module

    for source in (controls.__file__, module.__file__):
        tree = ast.parse(Path(source).read_text())
        assigned = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"panel", "self"}
        }
        assert not assigned.intersection(dir(GUI.QWidget)), assigned.intersection(
            dir(GUI.QWidget)
        )
        assert not assigned.intersection(dir(GUI.QMainWindow)), assigned.intersection(
            dir(GUI.QMainWindow)
        )


def test_coverage_corner_pixels_and_original_highlight(panel):
    p, _ = panel
    cell = p.grid.cell
    p.grid.last_key = 65
    image = p.grid.grab(QtCore.QRect(cell, 4 * cell, 2 * cell, cell)).toImage()
    assert image.pixelColor(cell - 4, cell - 4).name() == "#146caa"
    assert image.pixelColor(2 * cell - 5, cell - 5).name() == "#6b6b6b"
    if p.part == 3:
        assert image.pixelColor(2, 2).name() == "#ff0000"
    p.facts = None
    p.assignments = {}
    image = p.grid.grab(QtCore.QRect(cell, 4 * cell, cell, cell)).toImage()
    assert image.pixelColor(cell - 4, cell - 4).name() != "#146caa"


def test_unassigned_and_surrogate_never_query_part2_metrics(panel, monkeypatch):
    p, _ = panel
    if p.part != 2:
        return
    metrics = Mock(side_effect=AssertionError("invalid character queried native font"))
    monkeypatch.setattr(GUI, "QFontMetrics", metrics)
    click(p, 0x378)
    click(p, 0xD800)
    assert not metrics.called and p.last_error == "" and p.text.text() == ""
