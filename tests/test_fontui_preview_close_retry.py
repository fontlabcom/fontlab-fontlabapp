# this_file: tests/test_fontui_preview_close_retry.py
"""Production preview owners must let AppShell retry incomplete disconnects."""

import importlib
import sys
from types import SimpleNamespace

import pytest
from _tglyph_fakes import editable_font
from _tmetrics_fakes import EditableFont
from test_cov_ui_tglyph import tg_mod  # noqa: F401 - fixture
from test_cov_ui_tmetrics import tm_mod  # noqa: F401 - fixture

import _cov_qt as fq


@pytest.mark.parametrize("kind", ["tglyph", "tmetrics"])
@pytest.mark.parametrize("refusal", ["raise", "false"])
def test_shell_when_preview_disconnect_fails_then_retry_completes(request, monkeypatch, kind, refusal):
    module = request.getfixturevalue("tg_mod" if kind == "tglyph" else "tm_mod")
    if kind == "tglyph":
        child = module.TGlyph(editable_font(), "a", read_only=True)
    else:
        child = module.TMetrics(EditableFont(), on_open_glyph=lambda name: None, text="AV", read_only=True)
    monkeypatch.setattr(fq, "RECORDED_METHODS", fq.RECORDED_METHODS | {
        "setSizeConstraint", "setChildrenCollapsible", "setContentsMargins",
        "insertWidget", "addTab", "setVisible",
    })
    monkeypatch.setattr(fq, "SIGNALS", fq.SIGNALS | {"currentChanged"})
    monkeypatch.setattr(fq.FakeWidget, "currentWidget", lambda self: None, raising=False)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.appshell", raising=False)
    fq._forget_on_parent("fontlabapp.fontui.appshell", monkeypatch)
    shell = importlib.import_module("fontlabapp.fontui.appshell").AppShell("Retry", preview=kind)
    shell.set_preview(child)
    attempts = []

    def disconnect(slot):
        attempts.append(slot)
        if len(attempts) == 1:
            if refusal == "raise":
                raise RuntimeError("transient disconnect failure")
            return False
        return None

    child.connect(SimpleNamespace(connect=lambda slot: None, disconnect=disconnect), lambda: None)
    try:
        shell.close_button.clicked.emit()
        assert child.closed and not child._close_complete
        assert not shell._close_complete and shell.children == [child]
        assert "Close incomplete" in shell.status.text
        assert child.connections
        if kind == "tglyph":
            assert ("stop", ()) in child.follow_timer.calls
        else:
            assert child.on_open_glyph is None and child.outlines == {}
        shell.close_button.clicked.emit()
        assert len(attempts) == 2
        assert child._close_complete and shell._close_complete
        assert child.connections == shell.connections == shell.children == []
        child.close()
        shell.close()
        assert len(attempts) == 2
    finally:
        sys.modules.pop("fontlabapp.fontui.appshell", None)
        fq._forget_on_parent("fontlabapp.fontui.appshell")
