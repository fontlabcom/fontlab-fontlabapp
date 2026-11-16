# this_file: tests/test_teaching_text.py
"""Keep the text and inspection labs composed from their original live panels."""

import importlib
from types import SimpleNamespace

import pytest

from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def teaching_text(request, monkeypatch):
    request.getfixturevalue("studio_qt")
    module = importlib.import_module("fontlabapp.fontui.teaching_text")
    package = importlib.import_module("fontlabapp.fontui.teaching")
    host = importlib.import_module("fontlabapp.fontui.teaching.host")
    fontui = importlib.import_module("fontlabapp.fontui")
    # Earlier Qt fixtures reload submodules; restore the matching parent attributes.
    monkeypatch.setattr(fontui, "teaching", package, raising=False)
    monkeypatch.setattr(package, "host", host, raising=False)
    monkeypatch.setattr(module, "host", host, raising=False)
    return module


@pytest.mark.parametrize("title", ("Text Editors Lab", "Scripting Workbench", "Snapshot Lab", "Font Inspection Lab"))
@pytest.mark.parametrize("provided", (False, True))
def test_show_embeds_every_named_panel_and_one_preview(monkeypatch, teaching_text, title, provided):
    events = []
    shell = SimpleNamespace(widget=object(), tabs=object(), preview=None, set_actions=lambda *a, **k: None, close=lambda: events.append("close"))
    monkeypatch.setattr(teaching_text.host, "create", lambda *a, **k: shell)
    monkeypatch.setattr(teaching_text.host, "embed", lambda s, label, panel: events.append((label, panel.name)))
    monkeypatch.setattr(teaching_text.host, "bind_preview", lambda *a, **k: events.append("preview"))
    monkeypatch.setattr(teaching_text.host, "bind_current_preview", lambda s: events.append("preview"))
    monkeypatch.setattr(teaching_text.host, "finish", lambda s: s)
    monkeypatch.setattr(teaching_text, "import_module", lambda name: SimpleNamespace(build=lambda parent: SimpleNamespace(name=name)))
    assert teaching_text.show(title, font=object() if provided else None) is shell
    preview, profiles = teaching_text.PROFILES[title]
    assert events == [(label, teaching_text.__name__ + "." + module) for label, module in profiles] + (["preview"] if preview else [])


def test_show_captures_font_once_and_closes_after_failed_build(monkeypatch, teaching_text):
    events = []
    shell = SimpleNamespace(widget=object(), tabs=object(), preview=None, set_actions=lambda *a, **k: None, close=lambda: events.append("close"))
    monkeypatch.setattr(teaching_text.host, "create", lambda *a, **k: shell)
    monkeypatch.setattr(teaching_text, "import_module", lambda name: SimpleNamespace(build=lambda parent: (_ for _ in ()).throw(ValueError("failed"))))
    with pytest.raises(ValueError, match="failed"):
        teaching_text.show("Snapshot Lab")
    assert events == ["close"]


def test_show_unknown_lab_refuses_before_creating_window(teaching_text):
    with pytest.raises(KeyError):
        teaching_text.show("Unknown")


def test_preview_action_uses_replacement_owner(teaching_text):
    calls = []
    shell = SimpleNamespace(preview=SimpleNamespace(refresh=lambda: calls.append("old")))
    def action():
        teaching_text.refresh_preview(shell)
    action()
    shell.preview = SimpleNamespace(refresh=lambda: calls.append("new"))
    action()
    assert calls == ["old", "new"]
    shell.preview = None
    with pytest.raises(ValueError, match="Capture a font"):
        action()


def test_xml_table_sorts_and_resizes_without_changing_export_snapshot(request):
    qt = request.getfixturevalue("studio_qt")
    import sys
    from fontlabapp.fontui.teaching_text import xml

    rows = (("B", "U+0042", ""), ("A", "U+0041", ""))
    panel = xml.show(sys.modules["PythonQt"], None,
                     capture=lambda: SimpleNamespace(rows=rows), embedded=True)
    assert not panel.isVisible()
    panel.table_view.sortByColumn(0, qt.QtCore.Qt.AscendingOrder)
    assert panel.owned_model.item(0, 0).text() == "A"
    assert panel.snapshot == rows
    header = panel.table_view.horizontalHeader()
    header.resizeSection(0, 241)
    assert header.sectionSize(0) == 241
    calls = []
    panel.lab_close = lambda: calls.append("shell")
    panel.action_strip.itemAt(panel.action_strip.count() - 1).widget().click()
    assert calls == ["shell"] and panel in xml._PANELS
    assert panel.close() and panel not in xml._PANELS
