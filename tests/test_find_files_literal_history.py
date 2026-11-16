# this_file: tests/test_find_files_literal_history.py
"""History append preserves the live editor and releases failed staging."""

from types import SimpleNamespace as NS

import pytest
from test_find_files_literal import history
from test_find_files_literal import (
    panel as panel,  # noqa: PLC0414 - pytest fixture export
)


def test_history_append_leaves_live_editor_state_and_activation_untouched(panel):
    from fontlabapp.qt.find_files.text import remember

    create, _, qt = panel
    w = create("bytes")
    combo = w.containing
    line = combo.lineEdit()
    combo.setEditText("draft")
    line.insert(" edit")
    line.setSelection(1, 3)
    state = lambda: (
        combo.currentIndex(),
        combo.currentText(),
        line.cursorPosition(),
        line.selectionStart(),
        line.selectedText(),
        line.isUndoAvailable(),
    )
    before = state()
    activated = []
    callback = lambda *args: activated.append(args)
    combo.activated.connect(callback)
    try:
        prior = history(combo)
        remember(qt, combo, "A\0B")
        remember(qt, combo, "A\0B")
        remember(qt, combo, "A\0C")
        assert history(combo) == prior + ["A\0B", "A\0C"]
        assert state() == before and not activated
        line.undo()
        assert combo.currentText() == "draft"
    finally:
        combo.activated.disconnect(callback)


def test_history_setup_failure_preserves_model_and_editor(panel, monkeypatch):
    from fontlabapp.qt.find_files import text

    create, _, qt = panel
    w = create("bytes")
    w.containing.setEditText("draft")
    prior = history(w.containing)
    real = text.combo_type
    dead = []

    def broken(binding):
        base = real(binding)

        class Broken(base):
            def __init__(self):
                super().__init__()
                self.destroyed.connect(lambda *a: dead.append(True))

            def setEditText(self, value):
                raise RuntimeError("owned staging fault")

        return Broken

    monkeypatch.setattr(text, "combo_type", broken)
    with pytest.raises(RuntimeError, match="owned staging fault"):
        text.remember(qt, w.containing, "A\0B")
    assert history(w.containing) == prior and w.containing.currentText() == "draft"
    assert dead == [True]


def test_native_model_refusal_preserves_history_and_releases_stage(panel, monkeypatch):
    from fontlabapp.qt.find_files import text

    create, _, qt = panel
    w = create("bytes")
    prior = history(w.containing)
    real = text.combo_type
    dead = []

    def watched(binding):
        base = real(binding)

        class Stage(base):
            def __init__(self):
                super().__init__()
                self.destroyed.connect(lambda *a: dead.append(True))

        return Stage

    monkeypatch.setattr(text, "combo_type", watched)
    monkeypatch.setattr(
        type(w.containing), "model", lambda self: NS(dropMimeData=lambda *args: False)
    )
    with pytest.raises(RuntimeError, match="could not be added"):
        text.remember(qt, w.containing, "A\0B")
    assert history(w.containing) == prior and dead == [True]
