# this_file: tests/test_fontui_interpolation_preview.py
"""Real designspace controls and blend over an owned fake native font."""
import importlib
import sys
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from test_fontui_master_width_comparison import actual_qt, native_model  # noqa: F401


@pytest.fixture
def preview(actual_qt, native_model, monkeypatch):  # noqa: F811 - imported pytest fixtures
    from PySide6 import QtWidgets

    qt, parent, app = actual_qt
    class Double(QtWidgets.QDoubleSpinBox):
        value = property(QtWidgets.QDoubleSpinBox.value)
    class Slider(QtWidgets.QSlider):
        value = property(QtWidgets.QSlider.value)
    qt.QtGui.QDoubleSpinBox, qt.QtGui.QSlider = Double, Slider
    modules = ["fontlabapp.fontui.designspace", "fontlabapp.masters.interpolation.view",
               "fontlabapp.anchors.inspect.views", "fontlabapp.components.inspect.views",
               "fontlabapp.proof.inspect.views"]
    previous = {name: sys.modules.pop(name, None) for name in modules}
    font, package, registry, _ = native_model
    package.axes = [NS(name="Weight", tag="wght", shortName="wt", minimal=100,
                       default=100, maximum=900, map={})]
    package.masters = ["Light", "Bold"]
    package.instances = []
    for name in ("A", "B"):
        for layer in package.findName(name).layers:
            x = 0 if layer.name == "Light" else 100
            layer.shapes = [NS(transform=NS(isIdentity=lambda: True), contours=[NS(
                nodes=lambda x=x: [NS(x=x, y=0, isOn=lambda: True),
                                   NS(x=x+50, y=100, isOn=lambda: True)])])]
    api = importlib.import_module("fontlabapp.fontui.interpolation_preview")
    owner = api.show(font, parent)
    try:
        yield owner, api, package, registry, parent
    finally:
        owner.close()
        app.processEvents()
        for name, old in previous.items():
            sys.modules.pop(name, None)
            if old is not None:
                sys.modules[name] = old


def test_controls_when_changed_then_existing_blend_and_no_font_mutation(preview):
    owner, _, package, _, _ = preview
    assert "Enter a glyph" in owner.status.text
    before = [(layer.name, layer.advanceWidth, deepcopy(layer.lib))
              for layer in package.findName("A").layers]
    owner.glyph.setText("A")
    owner.glyph.editingFinished.emit()
    assert owner.view.mix == [[(0.0, 0.0, True), (50.0, 100.0, True)]]
    owner.controls.axes["Weight"][1].setValue(500)
    assert owner.view.mix == [[(50.0, 0.0, True), (100.0, 100.0, True)]]
    owner.controls.location_list.setCurrentRow(1)
    assert owner.view.mix == [[(100.0, 0.0, True), (150.0, 100.0, True)]]
    owner.controls.reset_button.clicked.emit()
    assert owner.view.mix[0][0][0] == 0
    owner.first.setCurrentIndex(1)
    assert not owner.view.mix and "segment" in owner.status.text
    owner.first.setCurrentIndex(0)
    owner.refresh_button.clicked.emit()
    assert owner.view.mix
    assert before == [(layer.name, layer.advanceWidth, layer.lib)
                      for layer in package.findName("A").layers]
    owner.close_button.clicked.emit()
    assert owner._close_complete and owner.controls._close_complete
    owner.refresh()
    owner.close()


@pytest.mark.parametrize("case", ["missing", "layer", "incompatible", "nan", "stale", "axes", "backend"])
def test_refresh_when_refused_then_clears_prior_geometry(preview, case):
    owner, _, package, registry, _ = preview
    owner.glyph.setText("A")
    owner.refresh()
    assert owner.view.mix
    glyph = package.findName("A")
    if case == "missing":
        owner.glyph.setText("Absent")
    elif case == "layer":
        glyph.findLayer("Bold").isNull = True
    elif case == "incompatible":
        glyph.findLayer("Bold").shapes = []
    elif case == "nan":
        glyph.findLayer("Bold").shapes[0].contours[0].nodes = lambda: [NS(x=float("nan"), y=0, isOn=lambda: True), NS(x=1,y=1,isOn=lambda:True)]
    elif case == "stale":
        registry.clear()
    elif case == "axes":
        package.axes[0].maximum = 1000
    else:
        owner.backend = object()
    owner.refresh()
    assert not owner.view.a and not owner.view.b and not owner.view.mix
    assert owner.status.text


def test_show_when_no_font_then_visible_refusal_and_cleanup(preview):
    owner, api, _, _, parent = preview
    refusal = api.show(None, parent)
    assert "registered" in refusal.status.text
    refusal.close()
    owner._reading = True
    owner.refresh()
    owner._reading = False


def test_fraction_when_mapped_axes_then_design_coordinates_and_segment_refusals():
    from fontlab_fontport.designspace import Designspace
    from fontlabapp.fontui.interpolation_preview import _fraction
    from fontTools.designspaceLib import DesignSpaceDocument
    doc = DesignSpaceDocument()
    doc.addAxisDescriptor(name="Weight", tag="wght", minimum=0, default=0, maximum=100,
                          map=[(0,0),(50,20),(100,100)])
    doc.addAxisDescriptor(name="Width", tag="wdth", minimum=0, default=0, maximum=100)
    ds = Designspace(doc)
    def loc(w, d):
        return ds.instance({"Weight": w, "Width": d})
    assert _fraction(ds, loc(0,0), loc(100,0), loc(50,0)) == .2
    assert _fraction(ds, loc(0,0), loc(100,100), loc(50,20)) == .2
    for first, second, point in [(loc(0,0),loc(100,0),loc(50,1)),
                                 (loc(0,0),loc(100,100),loc(50,50)),
                                 (loc(50,0),loc(100,0),loc(0,0)),
                                 (loc(0,0),loc(0,0),loc(0,0))]:
        with pytest.raises(ValueError):
            _fraction(ds, first, second, point)


@pytest.mark.parametrize("case", ["one", "duplicates", "identity"])
def test_show_when_native_metadata_invalid_then_refuses(preview, case):
    owner, api, package, _, parent = preview
    font = owner.font
    if case == "one":
        package.masters = ["Light"]
    elif case == "duplicates":
        package.masters = ["Light", "Light"]
    else:
        owner.package_id = -1
        owner.refresh()
        assert "identity changed" in owner.status.text
        return
    refusal = api.show(font, parent)
    assert refusal.controls is None
    assert "required" in refusal.status.text or "unique" in refusal.status.text
    refusal.close()


def test_close_when_child_cleanup_fails_then_retains_owner_for_retry(preview, monkeypatch):
    owner, api, _, _, _ = preview
    original = owner.controls.close
    def fail():
        raise RuntimeError("child cleanup refused")
    monkeypatch.setattr(owner.controls, "close", fail)
    with pytest.raises(RuntimeError, match="child cleanup"):
        owner.close()
    assert owner in api._HANDLES and not owner._close_complete
    assert owner.controls.on_location is None
    monkeypatch.setattr(owner.controls, "close", original)
    owner.close()
    assert owner not in api._HANDLES and owner._close_complete


def test_show_when_widget_show_fails_then_cleans_owned_children(preview, monkeypatch):
    owner, api, _, _, parent = preview
    cls = api._panel_type()
    original = cls.__init__
    seen = []
    def build(self, *args):
        original(self, *args)
        seen.append(self)
        def fail():
            raise RuntimeError("show failed")
        self.widget.show = fail
    monkeypatch.setattr(cls, "__init__", build)
    monkeypatch.setattr(api, "_panel_type", lambda: cls)
    with pytest.raises(RuntimeError, match="show failed"):
        api.show(owner.font, parent)
    assert seen[0]._close_complete and seen[0].controls._close_complete
    assert seen[0] not in api._HANDLES


def test_show_when_child_factory_fails_then_retains_exact_cleanup_owner(preview, monkeypatch):
    owner, api, _, _, parent = preview
    import fontlabapp.fontui as ui
    from fontlabapp.fontui.lifecycle import Owned
    child = Owned(parent)
    def fail(*args):
        error = RuntimeError("child factory failed")
        error.owner = child
        raise error
    monkeypatch.setattr(ui, "designspace_panel", fail)
    with pytest.raises(RuntimeError, match="child factory failed"):
        api.show(owner.font, parent)
    assert child._close_complete
