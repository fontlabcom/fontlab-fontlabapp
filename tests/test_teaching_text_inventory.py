# this_file: tests/test_teaching_text_inventory.py
"""Font Glyph Inventory Tabs: row adaptation, page text and the owned panel, on real offscreen Qt."""

from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import button, lab  # noqa: F401


@pytest.fixture
def inv(lab, monkeypatch):  # noqa: F811
    module, shown = lab("inventory")
    import fontlabapp.glyphs.catalog.model as model

    table = NS(rows=[("A", "U+0041", 1), ("dup", "U+0041 U+0042", 2), ("space", "", 3)])
    monkeypatch.setattr(model, "capture", lambda deadline: table)
    return module, shown, table


def test_glyph_rows_when_table_captured_then_codes_converted(inv):
    module, shown, table = inv
    assert module.glyph_rows() == (("A", (0x41,)), ("dup", (0x41, 0x42)), ("space", ()))


def test_glyph_rows_when_surrogate_then_refused(inv):
    module, shown, table = inv
    table.rows = [("bad", "U+D800", 1)]
    with pytest.raises(ValueError, match="Unreadable Unicode"):
        module.glyph_rows()


@pytest.mark.parametrize("ticks", ([0.0, 3.0], [0.0, 0.0, 3.0]))
def test_glyph_rows_when_deadline_passes_then_no_partial_result(inv, monkeypatch, ticks):
    module, shown, table = inv
    clock = iter(ticks + [9.0] * 20)
    monkeypatch.setattr(module, "monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError, match="no partial result"):
        module.glyph_rows()


def test_inventory_when_duplicates_then_counts_and_pages(inv):
    module, shown, table = inv
    summary, names, codes = module.inventory(module.glyph_rows())
    assert summary == "Glyphs: 3\nEncoded glyphs: 2\nDistinct codepoints: 2"
    assert names == "A\ndup\nspace"
    assert codes == "U+0041  A, dup\nU+0042  dup"


def test_dialog_when_previewed_then_three_tabs_filled_and_refresh_hook_called(inv):
    module, shown, table = inv
    dialog = module.build(None)
    calls = []
    dialog.lab_refresh_preview = lambda: calls.append("preview")
    assert dialog.preview() is True
    assert dialog.output.toPlainText().startswith("Glyphs: 3")
    assert dialog.extra_outputs[0].toPlainText() == "A\ndup\nspace"
    assert "U+0042  dup" in dialog.extra_outputs[1].toPlainText()
    assert dialog.status.text().startswith("Preview complete") and calls == ["preview"]
    assert dialog.tabs.count() == 3


def test_dialog_when_capture_fails_then_outputs_cleared_and_reason_shown(inv, monkeypatch):
    module, shown, table = inv
    dialog = module.build(None)
    dialog.preview()
    monkeypatch.setattr(module, "glyph_rows", lambda: (_ for _ in ()).throw(ValueError("No font")))
    assert dialog.preview() is False
    assert dialog.output.toPlainText() == "" and dialog.extra_outputs[1].toPlainText() == ""
    assert dialog.status.text() == "No font"


def test_close_button_and_main(inv):
    module, shown, table = inv
    dialog = module.build(None)
    calls = []
    dialog.lab_close = lambda: calls.append(1)
    button(dialog, "Close").click()
    assert calls == [1]
    module.main()
    assert shown[0][1] == "dialogs_tabdialog"
