# this_file: tests/test_teaching_text_notebook.py
"""Script Snippet Notebook: record store, JSON round trip and the draft panel, on real offscreen Qt."""

import json
import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import notebook

    return notebook


def test_put_when_valid_rename_or_collision_then_mapping_updated_or_refused(mod):
    book = mod.Notebook()
    book.put("one", "a = 1")
    book.put("two", "b = 2")
    book.put("uno", "a = 1", old="one")
    assert sorted(book.items) == ["two", "uno"]
    book.put("two", "b = 3", old="two")
    assert book.items["two"] == "b = 3"
    with pytest.raises(ValueError, match="already exists"):
        book.put("uno", "x", old="two")
    with pytest.raises(ValueError, match="missing"):
        book.put("new", "x", old="ghost")
    for title, body in (("", "x"), ("t", " "), ("a\nb", "x")):
        with pytest.raises(ValueError, match="single-line"):
            book.put(title, body)
    with pytest.raises(ValueError, match="CR"):
        book.put("t", "x\r")


def test_remove_navigate_find_when_records_then_sorted_wrapping(mod):
    book = mod.Notebook()
    with pytest.raises(ValueError, match="Add a snippet"):
        book.navigate(None, 1)
    for title in ("b", "a", "c"):
        book.put(title, "Body " + title.upper())
    assert book.navigate("a", 1) == "b" and book.navigate("a", -1) == "c" and book.navigate("c", 1) == "a"
    assert book.navigate("zzz", 1) == "a"
    assert book.find("BODY b") == ["b"] and book.find("") == ["a", "b", "c"] and book.find("nothing") == []
    book.remove("b")
    assert "b" not in book.items
    with pytest.raises(ValueError, match="existing record"):
        book.remove("b")


def test_encode_decode_when_round_trip_then_equal_and_bad_input_keeps_data(mod):
    book = mod.Notebook()
    book.put("é", "x = 'ü'\n")
    text = book.encode()
    assert text.endswith("\n") and "é" in text
    other = mod.Notebook()
    other.put("keep", "k")
    other.decode(text)
    assert other.items == book.items
    keep = mod.Notebook()
    keep.put("keep", "k")
    for bad, message in (('{"a": 1, "a": 2}', "Duplicate"), ("[1]", "JSON object"), ('{"a": 1}', "must be text"),
                         ('{"": "x"}', "single-line")):
        with pytest.raises(ValueError, match=message):
            keep.decode(bad)
        assert keep.items == {"keep": "k"}
    with pytest.raises(json.JSONDecodeError):
        keep.decode("{")


def test_export_when_snippet_then_commented_python_and_newline_added(mod):
    book = mod.Notebook()
    book.put("t", "x = 1")
    book.put("u", "y = 2\n")
    assert book.export("t") == "# t\nx = 1\n" and book.export("u") == "# u\ny = 2\n"
    with pytest.raises(ValueError, match="existing record"):
        book.export("zz")


@pytest.fixture
def notebook(lab, monkeypatch):  # noqa: F811
    module, shown = lab("notebook")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    monkeypatch.setattr(module, "capture_names", lambda: ("A", "B"))
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def type_record(panel, title, body):
    panel.title_field.setText(title)
    panel.editor.setPlainText(body)


def test_panel_when_records_added_replaced_and_navigated_then_state_follows(notebook):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    click(panel, qt, "Replace")
    assert "Select a record to replace" in panel.status.text()
    type_record(panel, "b", "B = 2")
    assert panel.record_dirty
    click(panel, qt, "Next")
    assert "Add, Replace or Cancel Draft" in panel.status.text()
    click(panel, qt, "Add")
    assert panel.current == "b" and not panel.record_dirty and panel.collection_dirty
    type_record(panel, "a", "A = 1")
    click(panel, qt, "Add")
    click(panel, qt, "Next")
    assert panel.current == "b" and panel.title_field.text == "b"
    click(panel, qt, "Previous")
    assert panel.current == "a"
    type_record(panel, "a2", "A = 1")
    click(panel, qt, "Replace")
    assert sorted(panel.book.items) == ["a2", "b"] and panel.current == "a2"
    click(panel, qt, "Remove")
    assert panel.current == "b" and sorted(panel.book.items) == ["b"]
    click(panel, qt, "Remove")
    assert panel.current is None and panel.book.items == {}
    click(panel, qt, "Remove")
    assert panel.status.text() == "Select an existing record first."


def test_panel_when_cancel_draft_then_committed_text_restored(notebook):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    type_record(panel, "a", "A = 1")
    click(panel, qt, "Add")
    panel.editor.setPlainText("changed")
    click(panel, qt, "Cancel Draft")
    assert panel.editor.toPlainText() == "A = 1" and not panel.record_dirty
    assert panel.dirty is True and panel.status.text().startswith("Draft cancelled")


def test_panel_when_find_then_cycles_matches_and_refuses_none(notebook):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    for title, body in (("a", "alpha"), ("b", "beta alpha")):
        type_record(panel, title, body)
        click(panel, qt, "Add")
    panel.query.setText("alpha")
    click(panel, qt, "Find")
    first = panel.current
    click(panel, qt, "Find")
    assert {first, panel.current} == {"a", "b"}
    panel.query.setText("zzz")
    click(panel, qt, "Find")
    assert panel.status.text() == "No matching snippet."


def test_panel_when_exported_and_loaded_then_json_round_trips(notebook, tmp_path):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    type_record(panel, "a", "A = 1")
    click(panel, qt, "Add")
    panel.destination.setText(str(tmp_path / "book.json"))
    click(panel, qt, "Export New")
    assert json.loads((tmp_path / "book.json").read_text()) == {"a": "A = 1"}
    assert not panel.collection_dirty and not panel.dirty
    panel.destination.setText(str(tmp_path / "a.py"))
    click(panel, qt, "Export Snippet")
    assert (tmp_path / "a.py").read_text() == "# a\nA = 1\n" and "Snippet exported" in panel.status.text()
    other = module.show(qt, parent, embedded=True)
    other.source.setText(str(tmp_path / "book.json"))
    click(other, qt, "Load JSON")
    assert other.current == "a" and other.status.text() == "Notebook loaded. No code was executed."
    other.source.setText("rel.json")
    click(other, qt, "Load JSON")
    assert "absolute source" in other.status.text()
    (tmp_path / "bad.json").write_text("[1]")
    other.source.setText(str(tmp_path / "bad.json"))
    click(other, qt, "Load JSON")
    assert "JSON object" in other.status.text() and other.current == "a"
    type_record(other, "z", "Z")
    other.record_dirty = False
    other.source.setText(str(tmp_path / "book.json"))
    click(other, qt, "Load JSON")
    assert "Export the notebook" in other.status.text()


def test_panel_when_font_names_then_comment_inserted(notebook):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    click(panel, qt, "Font Names")
    assert "# Current font glyphs: A B" in panel.editor.toPlainText()


def test_panel_when_copy_then_editor_text_on_clipboard(notebook, monkeypatch):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    copied = []
    monkeypatch.setattr(qt.QtGui.QApplication, "clipboard", staticmethod(lambda: NS(setText=copied.append)))
    type_record(panel, "a", "A = 1")
    click(panel, qt, "Copy")
    assert copied == ["A = 1"]


def test_panel_close_failures_and_main_build(notebook, monkeypatch):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: None)
    panel.editor.setPlainText("draft")
    panel.closeEvent(event)
    assert event.ignored
    panel.dirty = False
    click(panel, qt, "Discard and Close")
    assert panel not in module._PANELS
    window = module.show(qt, parent)
    assert window.isVisible()
    window.close()
    module._PANELS.clear()
    monkeypatch.setattr(qt.QtGui, "QLineEdit", lambda *a: (_ for _ in ()).throw(RuntimeError("no entry")))
    with pytest.raises(RuntimeError, match="no entry"):
        module.show(qt, parent)
    assert module._PANELS == []
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p, **k: seen.append(p))
    module.main()
    assert seen == [parent]


@pytest.mark.parametrize(
    "character,refused",
    [("퟿", False), ("\ud800", True), ("\udfff", True), ("", False)],
)
def test_check_text_when_character_at_surrogate_range_edge_then_only_lone_surrogates_refused(mod, character, refused):
    if refused:
        with pytest.raises(ValueError, match="lone surrogate"):
            mod.check_text("a" + character)
    else:
        assert mod.check_text("a" + character) == "a" + character


def test_navigate_when_current_missing_then_forward_starts_first_and_backward_starts_last(mod):
    book = mod.Notebook()
    for title in ("b", "a", "c"):
        book.put(title, "x")
    assert book.navigate(None, 1) == "a" and book.navigate("zzz", 1) == "a"
    assert book.navigate(None, -1) == "c" and book.navigate("zzz", -1) == "c"


def test_panel_when_find_repeats_then_walks_matches_in_order_and_wraps(notebook):
    module, qt, parent = notebook
    panel = module.show(qt, parent, embedded=True)
    for title, body in (("a", "alpha"), ("b", "beta alpha"), ("c", "gamma alpha")):
        type_record(panel, title, body)
        click(panel, qt, "Add")
    panel.query.setText("alpha")
    seen = []
    for _ in range(4):
        click(panel, qt, "Find")
        seen.append(panel.current)
    assert seen == ["a", "b", "c", "a"]
