# this_file: tests/test_node_duplicator_dialog.py
"""The result window reports the empty selection or every skipped target, read-only."""

from types import SimpleNamespace as NS

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

import fontlabapp.contours.nodes.duplicator.ui as ui  # noqa: E402


@pytest.fixture
def show(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    closed = []
    monkeypatch.setattr(ui, "_native", lambda name: NS(QtGui=QtWidgets))
    monkeypatch.setattr(ui, "show_script_dialog", lambda cls, key: cls())
    monkeypatch.setattr(ui, "close_script_dialog", lambda dialog, event, key: closed.append(key))
    monkeypatch.setattr(ui, "connect_guarded", lambda owner, signal, slot: signal.connect(slot))
    yield lambda result: (ui.show_result(result), closed)
    assert app is not None


def test_show_result_when_no_selection_then_only_the_original_message(show):
    dialog, _ = show({"no_selection_message": True, "inserted": 0, "skipped": []})
    assert "No nodes selected" in dialog.findChild(QtWidgets.QLabel).text()
    assert dialog.findChild(QtWidgets.QPlainTextEdit) is None, "nothing was skipped"
    assert not dialog.isModal()


def test_show_result_when_targets_skipped_then_all_are_listed_read_only(show):
    skipped = [("A", "Regular", 0, 3), ("B", "Bold", 1, 7)]
    dialog, _ = show({"no_selection_message": False, "inserted": 2, "skipped": skipped})
    assert "Inserted 2 nodes" in dialog.findChild(QtWidgets.QLabel).text()
    output = dialog.findChild(QtWidgets.QPlainTextEdit)
    assert output.isReadOnly()
    assert output.toPlainText().splitlines() == ["Glyph A, layer Regular: path 0, node 3", "Glyph B, layer Bold: path 1, node 7"]


def test_close_when_button_or_reject_then_owned_close_runs_and_flag_resets(show):
    dialog, closed = show({"no_selection_message": False, "inserted": 1, "skipped": []})
    dialog.findChild(QtWidgets.QPushButton).click()
    assert closed == ["node-duplicator-result"]
    dialog.reject()
    assert closed == ["node-duplicator-result"] * 2, "reject routes through the owned close"
    assert dialog._closing is False
    dialog._closing = True
    dialog.reject()
    assert closed == ["node-duplicator-result"] * 2, "a closing dialog uses the native reject"
