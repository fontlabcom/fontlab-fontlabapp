# this_file: tests/test_issue205_features_ui.py
"""Feature tables and independent copy previews retain guarded font ownership."""

from types import SimpleNamespace as NS

import pytest
from issue205_panels import (
    QtCore,
    QtWidgets,
    panels as panels,
    legacy_qt as legacy_qt,
    owned as owned,
)


def test_features_when_prepared_and_filled_then_visible_cells_and_clipboard_match_the_preview(
    panels, monkeypatch
):
    module = panels.modules["features.editor.ui"]

    class Tool(module.FeaturesDialog):
        def setup(self):
            self.body = self.prepare()

        def refresh(self):
            self._preview_valid = True

        def apply(self):
            self.ensure_preview()

    panel = panels.own(
        Tool(title="Features", subtitle="Owned source", key="owned_features")
    )
    assert panel.names == ["A", "acute"] and panel.font_data.glyphs == [
        panels.glyph,
        panels.mark,
    ]
    assert (
        panel.table.isHidden() and panel.minimumWidth() == 640 and panel.width() == 780
    )
    panel.table = panel.make_table(["Tag", "Count"])
    panel.body.addWidget(panel.table)
    assert panel.table.editTriggers() == QtWidgets.QAbstractItemView.NoEditTriggers
    assert panel.table.alternatingRowColors() and not panel.table.showGrid()
    panel.fill([("kern", 2), ("liga", "abc")])
    assert panel.rows == [("kern", 2), ("liga", "abc")]
    assert (
        panel.table.item(0, 1).text() == "2"
        and panel.table.item(0, 1).textAlignment() & QtCore.Qt.AlignRight
    )
    assert not panel.table.item(1, 1).textAlignment() & QtCore.Qt.AlignRight
    copied = []
    monkeypatch.setattr(
        module.QtGui, "QApplication", NS(clipboard=lambda: NS(setText=copied.append))
    )
    before = list(panels.owned.events)
    panel.copy_text("feature kern {pos A A -20;} kern;")
    assert copied == ["feature kern {pos A A -20;} kern;"] and panel.last_result == {
        "copied": copied[0]
    }
    assert panel.status.text() == "Copied feature code to the clipboard."
    assert panel._safe(lambda: 17) == 17
    assert (
        panel.safe(lambda: (_ for _ in ()).throw(ValueError("owned feature failure")))
        is None
    )
    assert (
        not panel._preview_valid
        and not panel._copy_preview_valid
        and not panel.apply_button.isEnabled()
    )
    assert panel.status.text() == "owned feature failure"
    with pytest.raises(ValueError, match="No valid preview"):
        panel.copy_text("unsafe")
    assert len(copied) == 1
    panel._copy_preview_valid = True
    panel.copy_text("independent read-only preview")
    assert copied[-1] == "independent read-only preview" and not panel._preview_valid
    panels.state.package = None
    with pytest.raises(ValueError, match="original font"):
        panel.copy_text("wrong font")
    assert len(copied) == 2 and panels.owned.events == before
    panel.close()
    assert panel.package is None and not panel._connections


def test_features_when_no_font_is_open_then_prepare_keeps_an_empty_read_only_panel(
    panels,
):
    module = panels.modules["features.editor.ui"]
    panels.state.package = None

    class Tool(module.FeaturesDialog):
        def setup(self):
            self.body = self.prepare()

        def refresh(self):
            self.fill([])

    panel = panels.own(
        Tool(title="Features", subtitle="Owned source", key="owned_empty_features")
    )
    assert panel.font_data is None and panel.names == [] and panel.rows == []
    assert not panel.apply_button.isEnabled() and "Open a font" in panel.subtitle.text()
    assert panel.last_result is None
