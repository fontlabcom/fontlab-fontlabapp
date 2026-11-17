# this_file: tests/test_issue205_fontui.py
"""Borrowed fonts/designspaces and preview failures over the existing Qt double."""

import sys
from types import SimpleNamespace as NS

import pytest
import _cov_qt as fq
from _light_canvas import light_canvas


@pytest.fixture
def ui(monkeypatch):
    handle = fq.install(monkeypatch)
    extras = (
        "fontlabapp.fontui.designspace",
        "fontlabapp.fontui.fonts",
        "fontlabapp.fontui.preview",
    )
    for name in extras:
        monkeypatch.delitem(sys.modules, name, raising=False)
        fq._forget_on_parent(name, monkeypatch)
    yield handle
    for name in extras:
        sys.modules.pop(name, None)
        fq._forget_on_parent(name)
    fq.release()


def test_designspace_when_slid_typed_selected_or_reset_then_exact_location_and_status(
    ui, monkeypatch, tmp_path
):
    from fontTools.designspaceLib import DesignSpaceDocument
    from fontlab_fontport.designspace import Designspace

    doc = DesignSpaceDocument()
    doc.addAxisDescriptor(
        name="Weight", tag="wght", minimum=100, default=400, maximum=900
    )
    (tmp_path / "regular.ufo").mkdir()
    doc.addSourceDescriptor(
        name="Regular",
        path=str(tmp_path / "regular.ufo"),
        designLocation={"Weight": 400},
    )
    doc.addSourceDescriptor(
        name="Missing",
        path=str(tmp_path / "missing.ufo"),
        designLocation={"Weight": 900},
    )
    doc.addInstanceDescriptor(name="Medium", userLocation={"Weight": 500})
    monkeypatch.setattr(
        ui.qt.QtGui.QDoubleSpinBox,
        "setDecimals",
        lambda self, value: None,
        raising=False,
    )
    module = ui.load("fontlabapp.fontui.designspace")
    seen = []
    panel = module.DesignspacePanel(Designspace(doc), on_location=seen.append)
    slider, number = panel.axes["Weight"]
    assert (
        panel.values() == {"Weight": 400}
        and panel.status.text == "Source master: Regular"
    )
    slider.setValue(51234)
    assert number.value == 512.34 and "not a source master" in panel.status.text
    number.setValue(600.25)
    assert slider.value == 60025 and dict(seen[-1].coordinates) == {"Weight": 600.25}
    panel.location_list.setCurrentRow(2)
    assert panel.values() == {"Weight": 500} and panel.status.text == "Instance: Medium"
    panel.select(1)
    assert "unavailable" in panel.status.text and panel.values() == {"Weight": 500}
    panel.select(-1)
    panel.select(99)
    number.setValue(1000)
    assert "Weight" in panel.status.text and dict(seen[-1].coordinates) == {
        "Weight": 500
    }
    panel.reset_button.clicked.emit()
    assert panel.values() == {"Weight": 400}
    panel.on_location = lambda value: (_ for _ in ()).throw(
        ValueError("owned callback")
    )
    panel._changed()
    assert "callback failed: owned callback" in panel.status.text
    before = len(seen)
    panel.close()
    panel.reset()
    panel.select(0)
    panel._changed()
    assert panel.closed and panel.on_location is None and len(seen) == before


def test_font_browser_when_identity_changes_then_list_selection_sort_and_child_state_are_exact(
    ui, monkeypatch
):
    module = ui.load("fontlabapp.fontui.fonts")
    children = []

    class Browser:
        def __init__(self, *args, **kwargs):
            self.state, self.preview = NS(font=None, selected=()), NS(font=None)
            self.widget, self.refreshes, self.closed = fq.FakeWidget(), 0, False
            self._close_complete = False
            children.append(self)

        def refresh(self):
            self.refreshes += 1

        def close(self):
            self.closed = True
            self._close_complete = True

    monkeypatch.setattr(module, "Browser", Browser)
    first = NS(info=NS(familyName="Zed", styleName="Regular"), path=None)
    second = NS(info=NS(familyName="Alpha", styleName="Bold"), path=None)
    panel = module.FontBrowser([first, second, first])
    assert panel.count_label.text == "2 fonts" and not panel.browser.widget.enabled
    panel.font_list.setCurrentRow(0)
    assert panel.state.selected is first and panel.browser.preview.font is first
    panel.browser.state.selected = ("A",)
    panel.refresh()
    assert panel.browser.state.selected == ("A",)
    panel.select(1)
    assert panel.browser.state.selected == () and panel.state.selected is second
    panel.sort()
    assert panel.state.fonts == (second, first) and panel.state.selected is second
    assert panel.font_list.currentRow == 0
    panel.select(-1)
    assert panel.state.selected is None and not panel.browser.widget.enabled
    panel.refresh([])
    assert panel.count_label.text == "0 fonts"
    panel.close()
    count = panel.browser.refreshes
    panel.refresh([first])
    panel.select(0)
    panel.sort()
    panel.close()
    assert panel.closed and children[0].closed and panel.browser.refreshes == count


def test_preview_when_overlays_and_source_fail_then_paths_metrics_diagnostics_and_end_are_exact(
    ui, monkeypatch
):
    from PySide6 import QtCore, QtGui
    from test_cov_ui_transform import Painter

    module = ui.load("fontlabapp.fontui.preview")
    light_canvas(monkeypatch, module)
    monkeypatch.setattr(module.QtGui, "QPainter", Painter)
    monkeypatch.setattr(module.QtGui, "QPainterPath", QtGui.QPainterPath)
    monkeypatch.setattr(module.QtCore, "Qt", QtCore.Qt)
    monkeypatch.setattr(
        Painter,
        "drawLine",
        lambda self, *args: self.calls.append(("drawLine", args)),
        raising=False,
    )
    monkeypatch.setattr(
        Painter,
        "drawEllipse",
        lambda self, *args: self.calls.append(("drawEllipse", args)),
        raising=False,
    )
    font = fq.FontModel(fq.ufo_font())
    preview = module.Preview(font, "A", follow=False)
    for name in ("oncurve", "offcurve", "anchors"):
        preview.set_option(name, True)
    Painter.made = []
    preview.canvas.paintEvent(None)
    calls = Painter.made[-1].calls
    assert [name for name, _ in calls].count("drawPath") == 2
    assert [name for name, _ in calls].count("drawLine") == 5
    assert any(name == "drawEllipse" for name, _ in calls)
    assert calls[-1][0] == "end" and preview.data is not None
    preview.set_option("fill", False)
    preview.set_option("stroke", False)
    preview.set_option("metrics", False)
    preview.zoom_buttons["+"].clicked.emit()
    assert preview.zoom == 1.25
    preview.zoom_buttons["Fit"].clicked.emit()
    assert preview.zoom == 1.0
    preview.paint(preview.canvas)
    assert preview.data is not None
    with pytest.raises(ValueError, match="Unknown overlay"):
        preview.set_option("missing", True)
    del font.ufo["A"]
    preview.paint(preview.canvas)
    assert preview.data is None and preview.diagnostic.text
    assert Painter.made[-1].calls[-1][0] == "end"
    preview.close()
    preview._zoom(2)
    preview.refresh()
    assert preview.zoom == 1.0
    with pytest.raises(RuntimeError, match="closed"):
        preview.set_glyph("V")
    with pytest.raises(RuntimeError, match="closed"):
        preview.set_option("fill", True)


@pytest.mark.parametrize("method", [True, False], ids=["method", "property"])
def test_designspace_when_status_text_is_method_or_property_then_callback_error_appends_to_text(
    ui, monkeypatch, tmp_path, method
):
    from fontTools.designspaceLib import DesignSpaceDocument
    from fontlab_fontport.designspace import Designspace

    doc = DesignSpaceDocument()
    doc.addAxisDescriptor(
        name="Weight", tag="wght", minimum=100, default=400, maximum=900
    )
    (tmp_path / "regular.ufo").mkdir()
    doc.addSourceDescriptor(
        name="Regular",
        path=str(tmp_path / "regular.ufo"),
        designLocation={"Weight": 400},
    )
    monkeypatch.setattr(
        ui.qt.QtGui.QDoubleSpinBox, "setDecimals", lambda self, value: None, raising=False
    )
    module = ui.load("fontlabapp.fontui.designspace")
    panel = module.DesignspacePanel(Designspace(doc), on_location=lambda value: None)

    class Label:
        shown = "Source master: Regular"

        def setText(self, value):
            self.shown = value

    Label.text = (
        (lambda self: self.shown) if method else property(lambda self: self.shown)
    )
    label = Label()
    panel.status = label
    panel.on_location = lambda value: (_ for _ in ()).throw(ValueError("owned callback"))
    panel._changed()
    assert label.shown == "Source master: Regular; callback failed: owned callback", label.shown
