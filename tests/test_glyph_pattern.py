# this_file: tests/test_glyph_pattern.py
"""Public lazy Fly/App boundary, complete shared capture and main-thread refusal."""

from importlib import import_module
from threading import Thread
from time import monotonic
from types import SimpleNamespace as NS

glyph_pattern = import_module("fontlabapp.glyphs.pattern")
from fontlabapp.qt.tables.filter.model import Table


def test_complete_capture_reuses_existing_reader_and_vocabulary(monkeypatch):
    import fontlabapp.glyphs.catalog.native as source

    calls = []
    deadline = monotonic() + 2
    monkeypatch.setattr(
        source,
        "capture",
        lambda **kw: (
            calls.append(kw)
            or Table(("Name", "Unicode", "Modified"), (("A", "", ""), ("B", "", "")))
        ),
    )
    assert glyph_pattern._capture(deadline=deadline) == ("A", "B")
    assert calls == [{"deadline": deadline}]


def test_public_show_is_lazy_and_routes_owned_widget_to_existing_registry(monkeypatch):
    import fontlabapp
    import fontlabapp.qt.regexp.ui as panel

    scripting = import_module("fontlabapp.core.scripting")

    qt = NS(QtCore=object(), QtGui=object())
    calls = []
    monkeypatch.setattr(fontlabapp, "_native", lambda name: calls.append(name) or qt)
    monkeypatch.setattr(
        panel, "panel_type", lambda core, gui: lambda parent, capture: (parent, capture)
    )
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda factory, key: (key, factory("owned"))
    )
    result = glyph_pattern.show()
    assert result == ("glyph_pattern", ("owned", glyph_pattern._capture)) and calls == [
        "PythonQt"
    ]
    errors = []

    def other():
        try:
            glyph_pattern.show()
        except RuntimeError as error:
            errors.append(str(error))

    thread = Thread(target=other)
    thread.start()
    thread.join()
    assert len(errors) == 1 and "main UI thread" in errors[0] and calls == ["PythonQt"]
