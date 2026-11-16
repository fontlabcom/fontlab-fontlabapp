# this_file: tests/test_point_counts_dialog.py
"""Exercise the new owned panel on real offscreen Qt widgets."""

import importlib

import test_tabular_width_dialog

from fontlabapp.contours.point_counts.model import Counts, GlyphCount, LayerCount

panel = test_tabular_width_dialog.panel


def test_point_panel_refresh_failure_close_and_lazy_factory(panel, monkeypatch):
    mod = importlib.import_module("fontlabapp.contours.point_counts.ui")
    report = (GlyphCount("A", (LayerCount("Regular", Counts(1, 1, 2, 1)),)),)
    monkeypatch.setattr(mod.api, "capture", lambda: report)
    widget = mod.PointCountsDialog()
    assert "4 points" in widget.output.toPlainText()
    assert (
        widget.report == report and widget.output.isReadOnly() and not widget.isModal()
    )
    from fontlabapp.core import scripting

    assert scripting.point_counts_dialog_type() is mod.PointCountsDialog
    monkeypatch.setattr(
        mod.api, "capture", lambda: (_ for _ in ()).throw(ValueError("No font"))
    )
    widget.refresh_button.click()
    assert widget.report is None and widget.output.toPlainText() == ""
    assert "No font" in widget.status.text()
    widget.close_button.click()
    assert widget._closed and not widget._connections
    widget.refresh()
