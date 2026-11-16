# this_file: tests/test_profile_drag_panels.py
"""Behavioural coverage for the four E06 drag/drop profile panels (real Qt widgets)."""

from importlib import import_module
from types import SimpleNamespace

import pytest

from test_studio_labs_e04_e06 import real_qt  # noqa: F401  (fixture)

BASE = "fontlabapp.fontui.core_pythonqt_labs.profiles."
ROWS = (
    SimpleNamespace(name="A", unicodes=(65,)),
    SimpleNamespace(name="V", unicodes=(86,)),
    SimpleNamespace(name="a.alt", unicodes=()),
)
FACTS = SimpleNamespace(rows=ROWS)


class Event:
    def __init__(self, mime, source=None):
        self._mime, self._source = mime, source
        self.accepted = self.ignored = False
        self.action = None

    def mimeData(self):
        return self._mime

    def source(self):
        return self._source

    def setDropAction(self, action):
        self.action = action

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


def build(real_qt, name, capture=lambda: FACTS, *args):
    qt, _app = real_qt
    module = import_module(BASE + name)
    panel = module.panel_type(qt, *( (capture,) if name != "font_file_drop_shelf" else args ))()
    panel.execute_drag = lambda mime: panel.__dict__.setdefault("dragged", []).append(mime)
    return qt, module, panel


def text_mime(qt, text):
    mime = qt.QtCore.QMimeData()
    mime.setText(text)
    return mime


def url_mime(qt, *paths):
    mime = qt.QtCore.QMimeData()
    mime.setUrls([qt.QtCore.QUrl.fromLocalFile(p) for p in paths])
    return mime


def test_encode_and_lazy_report(real_qt):
    qt, module, panel = build(real_qt, "deferred_glyph_report")
    assert '"a.alt"' in module.encode_report(ROWS)
    with pytest.raises(ValueError):
        module.LazyReport(None)
    lazy = module.LazyReport(FACTS)
    assert lazy.get() == lazy.get()
    mime = panel.output_mime()
    assert mime.hasText() or mime.formats()
    panel.copy_output()
    panel.drag_output()
    assert panel.dragged
    panel.invalidate()
    panel.changed()
    panel.seed()
    panel.close()


def test_deferred_report_refresh_failure_and_close(real_qt):
    def boom():
        raise RuntimeError("no font")

    qt, module, panel = build(real_qt, "deferred_glyph_report", boom)
    assert panel.facts is None and "no font" in panel.status.text()
    panel.busy = True
    event = Event(None)
    panel.closeEvent(event)
    assert event.ignored and not event.accepted
    panel.busy = False
    event = Event(None)
    panel.closeEvent(event)
    assert event.accepted


def test_font_drop_inspector(real_qt):
    qt, module, panel = build(real_qt, "font_drop_inspector")
    assert "MISSING" in module.coverage_report(FACTS, "AZ")
    for bad, facts in (("x" * 5001, FACTS), ("A", None), ("\ud800", FACTS)):
        with pytest.raises(ValueError):
            module.coverage_report(facts, bad)
    assert module.coverage_report(FACTS, "  ") == "No text received."
    panel.receive(text_mime(qt, "AV"))
    assert "U+0041" in panel.output.toPlainText()
    panel.receive(text_mime(qt, "x" * 5001))
    assert "at most" in panel.output.toPlainText()
    panel.receive(url_mime(qt, "/tmp/a.ufo"))
    assert "/tmp/a.ufo" in panel.output.toPlainText()
    panel.receive(qt.QtCore.QMimeData())
    assert "No text or URLs" in panel.output.toPlainText()
    mime = panel.output_mime()
    assert mime.hasText()
    panel.output.clear()
    with pytest.raises(ValueError):
        panel.output_mime()
    panel.entry.setText("A")
    panel.use_input() if hasattr(panel, "use_input") else None
    panel.close()


def test_font_drop_inspector_events(real_qt):
    qt, module, panel = build(real_qt, "font_drop_inspector")
    items = panel.items
    good, empty = Event(text_mime(qt, "A")), Event(qt.QtCore.QMimeData())
    items.dragEnterEvent(good)
    assert good.accepted
    items.dragEnterEvent(empty)
    assert empty.ignored
    moved = Event(text_mime(qt, "A"))
    items.dragMoveEvent(moved)
    assert moved.accepted
    dropped = Event(text_mime(qt, "A"))
    items.dropEvent(dropped)
    assert dropped.accepted
    panel.facts = None
    bad = Event(text_mime(qt, "A"))
    items.dropEvent(bad)
    items.startDrag(None)
    panel.close()


def test_pair_board(real_qt):
    qt, module, panel = build(real_qt, "glyph_pair_board")
    assert module.resolve_tokens(FACTS, "  ") == ()
    for text, facts in (("/A", None), ("A", FACTS), ("/Q", FACTS)):
        with pytest.raises(ValueError):
            module.resolve_tokens(facts, text)
    assert module.pair_lines(("A", "V", "A")) == "/A/V\n/V/A"
    panel.entry.setText("/A/V/A")
    panel.use_input()
    assert panel.output.toPlainText() == "/A/V\n/V/A"
    panel.items.setCurrentRow(0)
    panel.items.item(0).setSelected(True)
    panel.remove_selected()
    assert panel.text_items() == ("V", "A")
    with pytest.raises(ValueError):
        panel.remove_selected()
    panel.receive(text_mime(qt, "/A"))
    with pytest.raises(ValueError):
        panel.receive(url_mime(qt, "/tmp/x"))
    panel.copy_output()
    assert panel.output_mime().hasText()
    panel.drag_selected()
    assert panel.dragged
    panel.clear()
    with pytest.raises(ValueError):
        panel.copy_output()
    with pytest.raises(ValueError):
        panel.output_mime()
    panel.facts = None
    with pytest.raises(ValueError):
        panel.output_mime()
    panel.invalidate()
    panel.close()


def test_pair_board_events_reorder_and_plain(real_qt, monkeypatch):
    qt, module, panel = build(real_qt, "glyph_pair_board")
    items = panel.items
    base = qt.QtGui.QListWidget
    for native in ("dragEnterEvent", "dragMoveEvent", "dropEvent", "startDrag"):
        monkeypatch.setattr(base, native, lambda self, *a: None)
    own = Event(text_mime(qt, "A"), source=items)
    items.dragEnterEvent(own)
    items.dragMoveEvent(Event(text_mime(qt, "A"), source=items))
    other = Event(qt.QtCore.QMimeData())
    items.dragEnterEvent(other)
    assert other.ignored
    items.dragMoveEvent(Event(text_mime(qt, "A")))
    ok = Event(text_mime(qt, "/A/V"))
    items.dropEvent(ok)
    assert ok.accepted and panel.text_items() == ("A", "V")
    bad = Event(text_mime(qt, "nope"))
    items.dropEvent(bad)
    assert bad.ignored
    items.dropEvent(Event(text_mime(qt, "x"), source=items))
    items.startDrag(qt.QtCore.Qt.CopyAction)
    monkeypatch.setattr(module, "REORDER", False)
    items.startDrag(None)
    assert panel.dragged
    event = Event(None)
    panel.busy = True
    panel.closeEvent(event)
    assert event.ignored
    panel.busy = False
    panel.close()


def test_pair_board_refresh_failure(real_qt):
    def boom():
        raise RuntimeError("closed")

    qt, module, panel = build(real_qt, "glyph_pair_board", boom)
    assert panel.facts is None and "closed" in panel.status.text()
    panel.close()


def test_file_shelf(real_qt, tmp_path):
    opened = []
    font = tmp_path / "a.ttf"
    font.write_bytes(b"x")
    ufo = tmp_path / "b.ufo"
    ufo.mkdir()
    qt, _app = real_qt
    module = import_module(BASE + "font_file_drop_shelf")
    panel = module.panel_type(qt, opened.append)()
    panel.execute_drag = lambda mime: panel.__dict__.setdefault("dragged", []).append(mime)
    assert module.font_paths([str(font), str(font), str(ufo)]) == (str(font), str(ufo))
    for bad in ([], ["rel.ttf"], [str(tmp_path / "missing.ttf")], [str(tmp_path / "c.txt")], [str(tmp_path / "x.ufo")]):
        with pytest.raises(ValueError):
            module.font_paths(bad)
    panel.receive(url_mime(qt, str(font), str(ufo)))
    assert panel.items.count() == 2
    with pytest.raises(ValueError):
        panel.output_mime()
    panel.items.selectAll()
    mime = panel.output_mime()
    assert mime.hasUrls() and mime.hasText()
    panel.drag_selected()
    assert panel.dragged
    methods = [name for name in ("open_selected", "open_rows", "open_fonts") if hasattr(panel, name)]
    for name in methods:
        getattr(panel, name)()
    assert opened or not methods
    panel.close()


def test_deferred_mime_formats_and_retrieve(real_qt, monkeypatch):
    qt, _app = real_qt
    monkeypatch.setattr(qt.QtCore, "QVariant", SimpleNamespace(String="S"), raising=False)  # PythonQt-only name
    module = import_module(BASE + "deferred_glyph_report")
    mime = module.deferred_mime(qt.QtCore, module.LazyReport(FACTS))
    assert mime.formats() == ["application/json", "text/plain"]
    assert mime.hasFormat("text/plain") and not mime.hasFormat("x/y")
    assert bytes(mime.retrieveData("application/json", None)).startswith(b"{")
    assert bytes(mime.retrieveData("text/plain", None)) == b"A\nV\na.alt"
    assert not bytes(mime.retrieveData("x/y", None))
    assert mime.retrieveData("text/plain", "S") == "A\nV\na.alt"


def test_deferred_items_refuse_everything(real_qt):
    qt, module, panel = build(real_qt, "deferred_glyph_report")
    for method in (panel.items.dragEnterEvent, panel.items.dragMoveEvent, panel.items.dropEvent):
        event = Event(None)
        method(event)
        assert event.ignored
    panel.items.startDrag(None)
    assert panel.dragged
    panel.dispose()
    panel.close()


def test_file_shelf_events_and_open(real_qt, tmp_path):
    font = tmp_path / "a.ttf"
    font.write_bytes(b"x")
    other = tmp_path / "b.otf"
    other.write_bytes(b"x")
    opened = []

    def opener(path):
        opened.append(path)
        if path == str(other) and fail:
            raise OSError("denied")

    fail = False
    qt, _app = real_qt
    module = import_module(BASE + "font_file_drop_shelf")
    panel = module.panel_type(qt, opener)()
    items = panel.items
    ok, no = Event(url_mime(qt, str(font))), Event(qt.QtCore.QMimeData())
    items.dragEnterEvent(ok)
    items.dragEnterEvent(no)
    assert ok.accepted and no.ignored
    items.dragMoveEvent(Event(url_mime(qt, str(font))))
    drop = Event(url_mime(qt, str(font), str(other)))
    items.dropEvent(drop)
    assert drop.accepted and panel.items.count() == 2
    bad = Event(text_mime(qt, "x"))
    items.dropEvent(bad)
    assert bad.ignored
    panel.entry.setText(str(tmp_path / "missing.ttf"))
    with pytest.raises(ValueError):
        panel.use_input()
    panel.entry.setText(str(font))
    panel.use_input()
    panel.sort_rows(qt.QtCore.Qt.DescendingOrder)
    with pytest.raises(ValueError):
        panel.open_selected()
    panel.items.selectAll()
    panel.open_selected()
    assert sorted(opened) == sorted([str(font), str(other)])
    fail = True
    with pytest.raises(RuntimeError, match="failed"):
        panel.open_selected()
    panel.copy_output()
    panel.clear()
    with pytest.raises(ValueError):
        panel.copy_output()
    panel.drag_output()
    panel.busy = True
    event = Event(None)
    panel.closeEvent(event)
    assert event.ignored
    panel.busy = False
    panel.close()


def test_open_in_fontlab_confirms_one_new_package(monkeypatch):
    import sys

    module = import_module(BASE + "font_file_drop_shelf")
    packages = [SimpleNamespace(id=1)]

    class Workspace:
        @staticmethod
        def instance():
            return Workspace()

        def packages(self):
            return list(packages)

    class Host:
        result = None

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def open_font(self, path):
            if Host.result is None:
                packages.append(SimpleNamespace(id=len(packages) + 1))
            return Host.result

    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(flWorkspace=Workspace))
    monkeypatch.setattr("fontlabapp.core.controls.FontLab", Host)
    module.open_in_fontlab("/x.ttf")
    Host.result = {"status": "error"}
    with pytest.raises(RuntimeError, match="could not open"):
        module.open_in_fontlab("/x.ttf")
    Host.result = {"status": "ok"}
    with pytest.raises(RuntimeError, match="expected one"):
        module.open_in_fontlab("/x.ttf")
