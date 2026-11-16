# this_file: tests/test_demo_scripts_widgets.py
"""Offline runs of the Scripts/Widgets demos that open one existing panel (Issue 208).

Covers Toolkit Reference, Table Filter, Image Viewer and Find Files. The
Widget Gallery has its own file. Each demo runs through runpy as ``__main__``
(entry point and arguments asserted) and as an imported name (nothing may run).
The real ``fontlabapp.qt`` modules stay in use; only the ``PythonQt`` and
``fontlab`` natives and the panel ``show`` functions are replaced.
Offline results are not native FontLab acceptance.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _demo_support import Recorder, qt_namespace, run_script, script_path, stub_module

import fontlabapp.qt.find_files.model as find_files_model
import fontlabapp.qt.images.viewer.model as viewer_model
import fontlabapp.qt.tables.filter.model as filter_model
from fontlabapp.qt.find_files.search import Search

REFERENCE = script_path("Widgets", "Toolkit Reference Demo")
TABLE = script_path("Widgets", "Table Filter Demo")
VIEWER = script_path("Widgets", "Image Viewer Demo")
FINDER = script_path("Widgets", "Find Files Demo")


def install_qt(monkeypatch, **names):
    """Stub PythonQt and fontlab; return the QtGui namespace."""
    qt = qt_namespace(**names)
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: "main-window")
    return qt


def use_temp(monkeypatch, tmp_path):
    """Make tempfile.gettempdir point at ``tmp_path`` before a script computes its folder."""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))


# --- Toolkit Reference Demo ------------------------------------------------------


def test_reference_when_main_then_reports_every_section_in_one_owned_box(monkeypatch) -> None:
    qt = install_qt(monkeypatch)
    names = run_script(REFERENCE)
    box = qt.QtGui.QMessageBox.return_value
    assert qt.QtGui.QMessageBox.call_args[0] == ("main-window",)
    box.show.assert_called_once_with()
    box.setModal.assert_called_once_with(False)
    box.setWindowTitle.assert_called_once_with("Toolkit Reference Demo")
    assert names["_BOXES"] == [box], "the modeless box stays referenced"
    text = box.setDetailedText.call_args[0][0]
    for dotted in names["UI_PACKAGES"]:
        assert f"{dotted}: " in text, f"{dotted} is missing from the report"
    assert "fly.ap.ui.actions: Action, Actions, GlyphAction, GlyphActions, ActionDisabledError, live" in text
    assert "fly.ap.ui.windows: GlyphWindow, Preview" in text
    assert "ui_graph version 1: 2 nodes, 1 connection, reload identical: True" in text
    assert "linear.solve: x=6, y=4" in text
    assert "sizes [30.0, 30.0, 30.0], offsets [0.0, 35.0, 70.0]" in text
    assert "5 in 0..20 is position 250000 of 1000000; back to 5" in text
    assert "colors.rgba255((0.5, 0.25, 1, 1)) = (128, 64, 255, 255)" in text
    assert "colors.rgba_css((0.5, 0.25, 1, 1)) = rgba(128, 64, 255, 255)" in text
    assert "a method gives 12, an attribute gives field" in text
    assert "dialogs.name_filters(['png', '.jpg']) = ['Files (*.png *.jpg)']" in text
    assert "menus.OWNED_MENU_TITLE = 'Plugins'" in text
    assert "layer filters ('active', 'inactive', 'all')" in text
    assert "views classes: Panel, Preview, GlyphWindow" in text
    assert "safe.MAIN_WINDOW_CLASS = 'MainWindow'" in text
    assert qt.QtGui.QMessageBox.return_value.setInformativeText.call_args[0][0] == "5 sections reported."


def test_reference_when_a_second_report_shows_then_the_closed_first_box_is_released(monkeypatch) -> None:
    boxes = []

    class MessageBox:
        Information = 1

        def __new__(cls, *args):
            boxes.append(MagicMock(name=f"box{len(boxes)}"))
            return boxes[-1]

    install_qt(monkeypatch, QMessageBox=MessageBox)
    names = run_script(REFERENCE, "imported")
    names["show_report"]("First", "one", ["a"])
    boxes[0].isVisible.return_value = False  # the user closed it
    names["show_report"]("Second", "two", ["b"])
    boxes[0].deleteLater.assert_called_once_with()
    assert names["_BOXES"] == [boxes[1]] and boxes[1].deleteLater.call_count == 0


def test_reference_when_imported_then_nothing_runs(monkeypatch) -> None:
    qt = install_qt(monkeypatch)
    names = run_script(REFERENCE, "imported")
    assert qt.QtGui.QMessageBox.call_count == 0 and names["_BOXES"] == [] and callable(names["main"])


# --- Table Filter Demo -----------------------------------------------------------


def test_table_filter_when_main_then_shows_custom_panel_on_sample_rows(monkeypatch) -> None:
    show = Recorder()
    monkeypatch.setattr(filter_model, "show", show)
    names = run_script(TABLE)
    ((args, kwargs),) = show.calls
    assert kwargs["title"] == "Table Filter Demo" and kwargs["key"] == "widgets-demo-table-filter"
    assert kwargs["custom"] is True and "official" not in kwargs
    table = args[0]()
    assert table is args[0](), "every refresh captures the same complete table"
    assert table.headers == ("Glyph", "Description", "Modified") and len(table.rows) == 8 and table.epochs is None
    assert kwargs["description"] == "Sample rows only. Filter the top table into the bottom one."
    assert table.rows == (
        ("A", "Latin capital A <U+0041>", "2026-01-05 09:30"),
        ("B", "Latin capital B <U+0042>", "2026-01-12 14:05"),
        ("a", "Latin small a <U+0061>", "2026-02-02 11:00"),
        ("Aacute", "Latin capital A acute <U+00C1>", "2026-02-20 16:45"),
        ("alpha", "Greek small alpha <U+03B1>", "2026-03-08 08:10"),
        ("Alpha", "Greek capital alpha <U+0391>", "2026-03-09 10:20"),
        ("zero", "Digit zero <U+0030>", "2026-04-01 13:15"),
        ("space", "Space <U+0020>", "2026-04-15 17:55"),
    )


def test_table_filter_when_sample_rows_queried_then_text_and_date_limits_apply(monkeypatch) -> None:
    show = Recorder()
    monkeypatch.setattr(filter_model, "show", show)
    filter_model.show_demo()
    rows = show.calls[0][0][0]().rows
    march = filter_model.Query("alpha", "fixed", False, False, "2026-03-01", "2026-03-31")
    assert [row[0] for row in rows if march.accepts(row)] == ["alpha", "Alpha"]
    exact = filter_model.Query("Alpha", "fixed", True, False)
    assert [row[0] for row in rows if exact.accepts(row)] == ["Alpha"], "case-sensitive text differs"
    assert len({row[0] for row in rows}) == len(rows), "glyph names are distinct"


def test_table_filter_when_imported_then_nothing_runs(monkeypatch) -> None:
    show = Recorder()
    monkeypatch.setattr(filter_model, "show", show)
    run_script(TABLE, "imported")
    assert show.calls == []


# --- Image Viewer Demo -----------------------------------------------------------


class Image:
    """A QImage stand-in: ``save`` writes a marker file and reports success."""

    Format_RGB32 = 4
    saves = True

    def __init__(self, width, height, kind) -> None:
        self.size, self.filled = (width, height), None

    def fill(self, color) -> None:
        self.filled = color

    def save(self, path: str) -> bool:
        if self.saves:
            Path(path).write_bytes(b"png")
        return self.saves


class Unsaving(Image):
    saves = False


def test_image_viewer_when_main_then_saves_sample_in_demo_folder_and_loads_it(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    install_qt(monkeypatch, QImage=Image)
    viewer = SimpleNamespace(load=Recorder(True))
    show = Recorder(viewer)
    monkeypatch.setattr(viewer_model, "show", show)
    run_script(VIEWER)
    sample = tmp_path / "fontlabapp-demos" / "image-viewer" / "sample.png"
    assert sample.read_bytes() == b"png"
    assert show.calls == [((), {})], "the free-zoom viewer opens"
    assert viewer.load.calls == [((str(sample),), {})]
    assert [path.name for path in sample.parent.iterdir()] == ["sample.png"]


def test_image_viewer_when_run_again_then_sample_is_replaced_in_the_same_folder(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    install_qt(monkeypatch, QImage=Image)
    monkeypatch.setattr(viewer_model, "show", Recorder(SimpleNamespace(load=Recorder(True))))
    run_script(VIEWER)
    (tmp_path / "fontlabapp-demos" / "image-viewer" / "sample.png").write_bytes(b"stale")
    run_script(VIEWER)
    folder = tmp_path / "fontlabapp-demos" / "image-viewer"
    assert (folder / "sample.png").read_bytes() == b"png" and len(list(folder.iterdir())) == 1


def test_image_viewer_when_qt_cannot_save_then_raises_before_opening_the_viewer(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    install_qt(monkeypatch, QImage=Unsaving)
    show = Recorder()
    monkeypatch.setattr(viewer_model, "show", show)
    with pytest.raises(OSError, match="could not write"):
        run_script(VIEWER)
    assert show.calls == []


def test_image_viewer_when_imported_then_nothing_runs(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    show = Recorder()
    monkeypatch.setattr(viewer_model, "show", show)
    run_script(VIEWER, "imported")
    assert show.calls == [] and not (tmp_path / "fontlabapp-demos").exists()


# --- Find Files Demo -------------------------------------------------------------


def fake_panel() -> SimpleNamespace:
    return SimpleNamespace(directory=MagicMock(), pattern=MagicMock(), containing=MagicMock())


def test_find_files_when_main_then_writes_samples_and_points_the_panel_at_them(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    panel = fake_panel()
    show = Recorder(panel)
    monkeypatch.setattr(find_files_model, "show", show)
    run_script(FINDER)
    folder = tmp_path / "fontlabapp-demos" / "find-files"
    assert sorted(path.name for path in folder.iterdir()) == ["alpha.txt", "beta.txt", "notes.txt"]
    assert show.calls == [((), {})]
    assert [call[0] for call in panel.directory.method_calls] == ["clear", "addItem", "setEditText"]
    panel.directory.addItem.assert_called_once_with(str(folder))
    panel.directory.setEditText.assert_called_once_with(str(folder))
    panel.pattern.setEditText.assert_called_once_with("*")
    panel.containing.setEditText.assert_called_once_with("glyph")


def test_find_files_when_the_real_search_runs_on_the_samples_then_two_files_match(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    monkeypatch.setattr(find_files_model, "show", Recorder(fake_panel()))
    names = run_script(FINDER)
    folder = names["SAMPLE_FOLDER"]
    before = {path.name: path.read_text(encoding="utf-8") for path in folder.iterdir()}
    search = Search(folder, "*", "glyph", "text")
    for _ in range(100):
        if not search.active:
            break
        search.step()
    assert not search.active and search.error == ""
    assert sorted(item.path.name for item in search.results) == ["alpha.txt", "beta.txt"]
    after = {path.name: path.read_text(encoding="utf-8") for path in folder.iterdir()}
    assert after == before, "searching must not change the files"


def test_find_files_when_run_again_then_samples_are_reset_and_other_files_stay(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    monkeypatch.setattr(find_files_model, "show", Recorder(fake_panel()))
    run_script(FINDER)
    folder = tmp_path / "fontlabapp-demos" / "find-files"
    (folder / "alpha.txt").write_text("changed", encoding="utf-8")
    (folder / "mine.txt").write_text("keep", encoding="utf-8")
    run_script(FINDER)
    assert (folder / "alpha.txt").read_text(encoding="utf-8").startswith("glyph alpha")
    assert (folder / "mine.txt").read_text(encoding="utf-8") == "keep"


def test_find_files_when_imported_then_nothing_runs(monkeypatch, tmp_path) -> None:
    use_temp(monkeypatch, tmp_path)
    show = Recorder()
    monkeypatch.setattr(find_files_model, "show", show)
    run_script(FINDER, "imported")
    assert show.calls == [] and not (tmp_path / "fontlabapp-demos").exists()


def test_table_filter_when_read_then_launcher_only_imports_and_calls_domain_main() -> None:
    import ast

    tree = ast.parse(TABLE.read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    body = [node for node in main.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))]
    assert len(body) == 2 and isinstance(body[0], ast.ImportFrom)
    assert body[0].module == "fly.ap.qt.tables.filter.model"
    assert [(alias.name, alias.asname) for alias in body[0].names] == [("show_demo", None)]
    assert ast.unparse(body[1]) == "show_demo()"
    assert not any(isinstance(node, ast.Assign) for node in tree.body)
