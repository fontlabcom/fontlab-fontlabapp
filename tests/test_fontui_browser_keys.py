# this_file: tests/test_fontui_browser_keys.py
"""Browser construction and key policy over an owned Qt-shaped boundary.

These controls exercise the real Browser and real owned UFO outlines. They do
not create native Qt widgets, import FontLab or qualify PythonQt behavior.
"""
import importlib
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from _light_canvas import light_canvas
from ufoLib2 import Font


class Widget:
    def __init__(self, *args):
        self.signals = {}

    def __getattr__(self, name):
        return self.signals.setdefault(name, Mock())


class Item:
    def __init__(self, name):
        self.name, self.selected = name, False

    def text(self):
        return self.name

    def setIcon(self, icon):
        self.icon = icon

    def setSelected(self, selected):
        self.selected = selected

    def isSelected(self):
        return self.selected


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class Timer(Widget):
    def __init__(self, *args):
        super().__init__(*args)
        self.timeout, self.pending = Signal(), False

    def start(self, *args):
        self.pending = True

    def stop(self):
        self.pending = False


def drain(browser, limit=1000):
    """Run the deferred thumbnail timer like an idle Qt event loop would."""
    timer = browser.icon_timer
    while timer.pending and limit:
        timer.pending, limit = False, limit - 1
        timer.timeout.emit()


class Items(Widget):
    def __init__(self, *args):
        super().__init__(*args)
        self.rows, self.base_keys, self.blocked = [], [], False

    def blockSignals(self, state):
        previous, self.blocked = self.blocked, state
        return previous

    def clear(self):
        self.rows.clear()

    def addItem(self, item):
        self.rows.append(item)

    def item(self, index):
        return self.rows[index]

    def currentItem(self):
        return self.rows[0] if self.rows else None

    def keyPressEvent(self, event):
        self.base_keys.append(event)


@pytest.fixture
def browser_module(monkeypatch):
    for name in ['native','lifecycle','preview']:
        monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.'+name, raising=False)
    flags = NS(Key_Return=13, Key_Enter=10, NoPen=0, NoBrush=0, WindingFill=1)
    gui = NS(QWidget=Widget, QListWidget=Items, QListWidgetItem=Item)
    for name in ['QLineEdit','QLabel','QVBoxLayout','QHBoxLayout','QComboBox','QSpinBox','QPixmap','QColor','QPainter','QPen','QBrush','QPainterPath','QIcon']:
        setattr(gui, name, Mock())
    gui.QAbstractItemView = NS(ExtendedSelection=2, SingleSelection=1)
    gui.QListView = NS(IconMode=1, ListMode=0)
    monkeypatch.setitem(sys.modules, 'PythonQt', NS(QtGui=gui, QtCore=NS(Qt=flags,QSize=lambda w,h:(w,h),QPoint=lambda x,y:(x,y),QTimer=Timer)))
    class Preview:
        def __init__(self, font, name=None, parent=None, follow=True):
            self.font, self.widget = font, Widget()
            self._close_complete = False
            self.set_glyph, self.refresh, self.diagnostic = Mock(), Mock(), Mock()
            self.close = Mock(side_effect=self._complete_close)

        def _complete_close(self):
            self._close_complete = True
    monkeypatch.setitem(sys.modules, 'fontlabapp.fontui.preview', NS(Preview=Preview))
    module = importlib.import_module('fontlabapp.fontui.native')
    monkeypatch.setattr(module, 'follow_changes', Mock())
    light_canvas(monkeypatch, module)
    yield module, gui
    for name in ['native','lifecycle','preview']:
        sys.modules.pop('fontlabapp.fontui.'+name, None)


@pytest.fixture
def font():
    font = Font()
    for name in ['A','V']:
        glyph = font.newGlyph(name)
        glyph.width = 500
        pen = glyph.getPen()
        pen.moveTo((20,0))
        pen.lineTo((200,400))
        pen.lineTo((400,0))
        pen.closePath()
        pen.moveTo((40,50))
        pen.lineTo((150,80))
        pen.endPath()
    font.glyphOrder = ['V','A']
    return font


@pytest.mark.parametrize('multiple,follow', [(False,False),(True,True)])
def test_browser_when_constructed_then_draws_filters_selects_and_updates_mode(browser_module,font,multiple,follow):
    module, gui = browser_module
    browser = module.Browser(font,multiple=multiple,follow=follow)
    assert browser.state.names == ('V','A')
    assert not browser.glyph_list.blocked
    browser.glyph_list.setSelectionMode.assert_called_once_with(2 if multiple else 1)
    assert gui.QPainter.return_value.end.call_count == 0
    drain(browser)
    assert gui.QPainter.return_value.end.call_count == 2
    assert not browser.count_label.setToolTip.call_args.args[0]
    if follow:
        owner,callback,fonts = module.follow_changes.call_args.args
        assert owner is browser and callback == browser._changed and fonts() == [font]
    else:
        module.follow_changes.assert_not_called()
    browser.glyph_list.item(1).setSelected(True)
    browser.selection_changed()
    assert browser.state.selected == ('A',)
    browser.preview.set_glyph.assert_called_with('A')
    browser.filter('V')
    assert browser.state.names == ('V',) and browser.state.selected == ()
    browser.set_mode(1)
    browser.set_size(120)
    browser.glyph_list.setGridSize.assert_called_with((120,120))
    browser.set_mode(0)
    browser.set_size(40)
    browser.glyph_list.setGridSize.assert_called_with((40,30))
    browser.glyph_list.setIconSize.assert_called_with((16,16))
    browser.preview.set_glyph.reset_mock()
    browser._changed()
    browser.preview.set_glyph.assert_called_once_with(None)
    browser.preview.refresh.assert_not_called()
    browser.close()
    browser.preview.close.assert_called_once_with()
    assert browser.closed and browser.on_activate is None and not browser.connections


@pytest.mark.parametrize('key', [13,10,27])
def test_browser_when_key_pressed_then_keeps_activation_and_explicit_base_policy(browser_module,font,key):
    module,_ = browser_module
    delivered = Mock()
    browser = module.Browser(font,on_activate=delivered,follow=False)
    event = NS(key=lambda:key,accept=Mock())
    browser.glyph_list.keyPressEvent(event)
    if key in (13,10):
        delivered.assert_called_once_with(font['V'])
        event.accept.assert_called_once_with()
        assert not browser.glyph_list.base_keys
    else:
        delivered.assert_not_called()
        event.accept.assert_not_called()
        assert browser.glyph_list.base_keys == [event]
    browser.close()
    browser.glyph_list.keyPressEvent(NS(key=lambda:13,accept=Mock()))
    assert delivered.call_count == (1 if key in (13,10) else 0)


def test_browser_when_drawing_fails_then_diagnostic_and_painter_cleanup(browser_module,font,monkeypatch):
    module,gui = browser_module
    browser = module.Browser(font,follow=False)
    monkeypatch.setattr(module, 'outline', Mock(side_effect=OSError('owned outline failure')))
    gui.QPainter.return_value.end.reset_mock()
    browser.thumbnail('A')
    browser.count_label.setToolTip.assert_called_with('owned outline failure')
    gui.QPainter.return_value.end.assert_called_once_with()
    browser.close()


def test_browser_when_closed_then_all_updates_and_repeated_close_are_inert(browser_module,font):
    module,_ = browser_module
    browser = module.Browser(font,follow=False)
    browser.close()
    selected = browser.state.selected
    browser.preview.set_glyph.reset_mock()
    for call,args in [(browser.refresh,()),(browser.filter,('A',)),(browser.selection_changed,()),(browser.set_mode,(1,)),(browser.set_size,(80,)),(browser.close,())]:
        call(*args)
    assert browser.state.selected == selected
    browser.preview.set_glyph.assert_not_called()
    browser.preview.close.assert_called_once_with()


def test_selection_callback_when_initial_and_blocked_refresh_then_ordered_payload(
    browser_module, font
):
    module, _ = browser_module
    events = []
    browser = module.Browser(
        font, on_selection=lambda f, names: events.append((f, names))
    )
    assert events == [(font, ())]
    selected = browser.state.names[0]
    browser.glyph_list.rows[0].setSelected(True)
    browser.selection_changed()
    assert events[-1] == (font, (selected,))
    browser._changed()
    assert events[-1] == (font, (selected,))
    browser.filter("absent")
    assert events[-1] == (font, ())
    browser.close()
    assert browser.on_selection is None
    count = len(events)
    browser.selection_changed()
    assert len(events) == count


def test_host_change_when_selection_callback_raises_then_diagnostic_survives_and_recovers(
    browser_module, font
):
    module, _ = browser_module
    browser = module.Browser(font)
    browser.preview.refresh.side_effect = lambda: browser.preview.diagnostic.setText(
        "preview"
    )
    browser.preview.set_glyph.side_effect = lambda name: browser.preview.refresh()
    error = ValueError("consumer fault")

    def fail(*args):
        raise error

    browser.on_selection = fail
    browser._changed()
    assert browser.preview.diagnostic.setText.call_args.args == (
        "Selection callback failed: consumer fault",
    )
    assert browser.state.error is None
    browser.on_selection = lambda f, names: None
    browser._changed()
    assert browser.preview.diagnostic.setText.call_args.args == ("preview",)


def test_close_when_preview_raises_then_selection_callback_already_released(
    browser_module, font
):
    module, _ = browser_module
    browser = module.Browser(font)
    browser.on_selection = lambda *args: None
    browser.preview.close.side_effect = RuntimeError("close failed")
    with pytest.raises(RuntimeError, match="close failed"):
        browser.close()
    assert browser.on_selection is None


@pytest.fixture
def many():
    font = Font()
    for index in range(2000):
        font.newGlyph(f"g{index:04d}").width = 500
    return font


def _count_outlines(module, monkeypatch):
    calls, real = [], module.outline

    def counted(font, name):
        calls.append(name)
        return real(font, name)

    monkeypatch.setattr(module, "outline", counted)
    return calls


def test_browser_when_many_glyphs_then_thumbnails_render_lazily_and_cache(
    browser_module, many, monkeypatch
):
    module, _ = browser_module
    calls = _count_outlines(module, monkeypatch)
    browser = module.Browser(many, follow=False)
    assert len(browser.glyph_list.rows) == 2000 and calls == []
    drain(browser)
    # The fake has no geometry, so this is the logged blind window, not all 2000.
    assert 0 < len(calls) <= module.ICON_BLIND_ROWS
    rows = browser.glyph_list.rows
    assert all(getattr(rows[i], "icon", None) is not None for i in range(32))
    rendered, before = set(calls), len(calls)
    browser.filter("g000")
    drain(browser)
    assert set(browser.state.names) <= rendered and len(calls) == before
    assert all(getattr(row, "icon", None) is not None for row in browser.glyph_list.rows)
    browser.refresh()
    drain(browser)
    assert len(calls) > before
    browser.close()


def test_browser_when_scrolled_then_only_rows_near_viewport_render(
    browser_module, many, monkeypatch
):
    module, _ = browser_module
    calls = _count_outlines(module, monkeypatch)
    browser = module.Browser(many, follow=False)
    _geometry(browser.glyph_list, cell=(200, 30), item=(200, 30), rows_from_y=False,
              width=200, height=21 * 30, offset=500 * 30, total=2000)
    browser.glyph_list.verticalScrollBar.return_value.valueChanged.connect.call_args.args[0](5)
    drain(browser)
    rows = sorted(int(name[1:]) for name in calls)
    assert rows and rows[0] >= 500 - 32 and rows[-1] <= 520 + 32
    assert {500, 520} <= set(rows)
    browser.close()
    calls.clear()
    browser.icon_timer.timeout.emit()
    assert calls == []


@pytest.fixture
def huge():
    font = Font()
    for index in range(3055):
        font.newGlyph(f"g{index:04d}").width = 500
    return font


def _geometry(glyphs, *, cell, item, rows_from_y, width=400, height=300, offset=0, total=3055):
    """Qt-shaped item rectangles: ``item`` px at the top of ``cell`` px cells, scrolled by ``offset``.

    ``indexAt`` answers like Qt, so the old corner probes land in the gaps between items.
    """
    cell_w, cell_h = cell
    item_w, item_h = item
    columns = max(1, width // cell_w) if rows_from_y else 1
    glyphs.viewport = lambda: NS(rect=lambda: NS(width=lambda: width, height=lambda: height))
    glyphs.count = lambda: total
    index = {id(row): number for number, row in enumerate(glyphs.rows)}

    def rect(number):
        left = (number % columns) * cell_w + (cell_w - item_w) // 2
        top = (number // columns) * cell_h - offset
        return left, top, item_w, item_h

    def visual(item):
        left, top, w, h = rect(index[id(item)])
        return NS(top=lambda: top, bottom=lambda: top + h - 1, left=lambda: left)

    def index_at(point):
        x, y = point
        for number in range(total):
            left, top, w, h = rect(number)
            if left <= x < left + w and top <= y < top + h:
                return NS(row=lambda: number)
        return NS(row=lambda: -1)

    glyphs.visualItemRect = visual
    glyphs.indexAt = index_at
    return columns


def _scroll(browser):
    browser.glyph_list.verticalScrollBar.return_value.valueChanged.connect.call_args.args[0](1)
    drain(browser)


def test_browser_when_grid_corners_hit_gaps_then_scrolled_middle_rows_render(
    browser_module, huge, monkeypatch
):
    module, _ = browser_module
    calls = _count_outlines(module, monkeypatch)
    browser = module.Browser(huge, follow=False)
    browser.state.mode, browser.state.cell_size = "grid", 96
    drain(browser)
    calls.clear()
    columns = _geometry(browser.glyph_list, cell=(96, 96), item=(45, 15), rows_from_y=True, offset=380 * 96 + 10)
    assert browser.glyph_list.indexAt((0, 0)).row() == -1
    assert browser.glyph_list.indexAt((399, 299)).row() == -1
    _scroll(browser)
    rows = {int(name[1:]) for name in calls}
    visible = set(range(380 * columns, 384 * columns))
    assert visible <= rows, sorted(visible - rows)
    assert max(rows) < 384 * columns + 64 and min(rows) > 380 * columns - 64
    browser.close()


@pytest.mark.parametrize("line", [1500, 3045], ids=["middle", "end"])
def test_browser_when_list_scrolled_then_visible_rows_render(browser_module, huge, monkeypatch, line):
    module, _ = browser_module
    calls = _count_outlines(module, monkeypatch)
    browser = module.Browser(huge, follow=False)
    drain(browser)
    calls.clear()
    _geometry(browser.glyph_list, cell=(400, 30), item=(400, 30), rows_from_y=False, offset=line * 30)
    _scroll(browser)
    rows = {int(name[1:]) for name in calls}
    visible = set(range(line, min(3055, line + 10)))
    assert visible <= rows, sorted(visible - rows)
    assert min(rows) >= line - 64
    browser.close()


def test_browser_when_geometry_fails_then_rows_near_current_render_and_log_once(
    browser_module, huge, monkeypatch, caplog
):
    module, _ = browser_module
    calls = _count_outlines(module, monkeypatch)
    browser = module.Browser(huge, follow=False)
    drain(browser)
    calls.clear()
    glyphs = browser.glyph_list

    def broken():
        raise RuntimeError("underlying C++ object was deleted")

    glyphs.viewport = broken
    glyphs.currentRow = lambda: 2000
    with caplog.at_level("WARNING", logger=module.__name__):
        _scroll(browser)
        _scroll(browser)
    rows = {int(name[1:]) for name in calls}
    assert set(range(1900, 2100)) <= rows
    assert len([r for r in caplog.records if "geometry" in r.getMessage()]) == 1
    browser.close()


def test_browser_when_scroll_bar_missing_then_logs(browser_module, many, monkeypatch, caplog):
    module, gui = browser_module
    monkeypatch.setattr(gui.QListWidget, "verticalScrollBar", None, raising=False)
    with caplog.at_level("WARNING", logger=module.__name__):
        browser = module.Browser(many, follow=False)
    assert any("scroll" in r.getMessage() for r in caplog.records)
    browser.close()
