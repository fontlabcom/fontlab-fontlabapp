# this_file: tests/test_vertical_metrics_dialog.py
"""Exercise the real owned report panel and its lazy scripting factory."""

import importlib

import test_tabular_width_dialog

from fontlabapp.metrics.vertical.model import MasterMetrics, MetricsReport

panel = test_tabular_width_dialog.panel


def test_snapshot_refresh_failure_close_and_lazy_factory(panel, monkeypatch):
    mod = importlib.import_module("fontlabapp.metrics.vertical.ui")
    report = MetricsReport(
        (
            MasterMetrics(
                7, "Owned.vfc", "Regular", (800, -200, 0, None, None, None, 200, 800)
            ),
        ),
        "12:34:56",
    )
    monkeypatch.setattr(mod.api, "capture", lambda: report)
    widget = mod.VerticalMetricsDialog()
    assert "✅ typoAscender" in widget.output.toPlainText()
    assert "1 fonts, 1 masters" in widget.status.text()
    assert (
        widget.report == report and widget.output.isReadOnly() and not widget.isModal()
    )
    from fontlabapp.core import scripting

    assert scripting.vertical_metrics_dialog_type() is mod.VerticalMetricsDialog
    monkeypatch.setattr(
        mod.api, "capture", lambda: (_ for _ in ()).throw(ValueError("Owned failure"))
    )
    widget.refresh_button.click()
    assert widget.report is None and widget.output.toPlainText() == ""
    assert "Owned failure" in widget.status.text()
    widget.close_button.click()
    assert widget._closed and not widget._connections
    widget.refresh()
