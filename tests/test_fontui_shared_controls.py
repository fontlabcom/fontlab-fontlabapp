# this_file: tests/test_fontui_shared_controls.py
"""Observable controls and failure behavior for the shared fontui editors."""

import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _cov_qt as fq


@pytest.fixture
def controls(monkeypatch):
    handle = fq.install(monkeypatch)
    names = ("designspace", "fonts", "features_view", "preview")
    for name in names:
        qualified = f"fontlabapp.fontui.{name}"
        monkeypatch.delitem(sys.modules, qualified, raising=False)
        fq._forget_on_parent(qualified, monkeypatch)
    monkeypatch.setattr(
        handle.qt.QtGui.QDoubleSpinBox,
        "setDecimals",
        lambda self, value: None,
        raising=False,
    )
    yield handle
    for name in names:
        qualified = f"fontlabapp.fontui.{name}"
        sys.modules.pop(qualified, None)
        fq._forget_on_parent(qualified)
    fq.release()


def test_designspace_when_controls_change_then_sync_location_and_contain_failures(
    controls,
):
    module = controls.load("fontlabapp.fontui.designspace")
    source = NS(
        kind="source", name="Regular", available=True, coordinates={"Weight": 400}
    )
    instance = NS(
        kind="instance", name="Bold", available=True, coordinates={"Weight": 700}
    )
    missing = NS(
        kind="source",
        name="Missing",
        available=False,
        coordinates={"Weight": 900},
        reason="file missing",
    )
    designspace = NS(
        axes=[NS(name="Weight", tag="wght", minimum=100, maximum=900, default=400)],
        sources=[source, missing],
        instances=[instance],
        defaults=lambda: {"Weight": 400},
        location=dict,
        instance=lambda values: NS(kind="instance", coordinates=values),
    )
    callback = Mock()
    panel = module.DesignspacePanel(designspace, on_location=callback)
    slider, number = panel.axes["Weight"]
    assert panel.current is source and panel.status.text == "Source master: Regular", (
        "Defaults select the exact source"
    )
    slider.setValue(55025)
    assert number.value == 550.25 and panel.values() == {"Weight": 550.25}, (
        "Slider units convert to user coordinates"
    )
    assert "not a source master" in panel.status.text, (
        "Intermediate coordinates are labelled instances"
    )
    number.setValue(600.5)
    assert slider.value == 60050 and not slider.blocked and not number.blocked, (
        "Typed values synchronise without leaving signals blocked"
    )
    panel.location_list.setCurrentRow(2)
    assert panel.current is instance and panel.status.text == "Instance: Bold", (
        "Selecting a named instance retains identity"
    )
    panel.select(1)
    assert "Missing is unavailable: file missing" == panel.status.text, (
        "Unavailable entries are refused visibly"
    )
    assert panel.current is instance, "A refusal keeps the prior location"
    panel.select(-1)
    panel.select(99)
    callback.side_effect = RuntimeError("consumer failed")
    panel.reset_button.clicked.emit()
    assert "callback failed: consumer failed" in panel.status.text, (
        "Callback failure remains visible without losing the source"
    )
    designspace.location = Mock(side_effect=ValueError("invalid location"))
    panel._changed()
    assert panel.status.text == "invalid location", "Validation failures are shown"
    calls = callback.call_count
    panel.close()
    panel.reset()
    panel.select(0)
    panel._changed()
    assert (
        panel.closed and panel.on_location is None and callback.call_count == calls
    ), "Closed controls stop callbacks"


def test_font_browser_when_refreshed_then_preserves_selection_and_disables_missing_font(
    controls, monkeypatch
):
    module = controls.load("fontlabapp.fontui.fonts")
    factory = Mock()

    class Browser:
        def __init__(self, font, parent, on_activate, multiple=False, follow=True):
            factory(font, parent, on_activate, multiple, follow)
            self.widget = fq.FakeWidget()
            self.state = NS(font=None, selected=())
            self.preview = NS(font=None)
            self.refresh = Mock()
            self._close_complete = False
            self.close = Mock(side_effect=self._complete_close)

        def _complete_close(self):
            self._close_complete = True

    monkeypatch.setattr(module, "Browser", Browser)
    first, second = fq.ufo_font(), fq.ufo_font()
    first.info.familyName, second.info.familyName = "Zulu", "Alpha"
    callback = Mock()
    panel = module.FontBrowser([first, second, first], on_activate=callback)
    inner = panel.browser
    assert panel.count_label.text == "2 fonts" and not inner.widget.enabled, (
        "Duplicate identities are removed and no font starts selected"
    )
    factory.assert_called_once_with(None, panel.widget, callback, False, False)
    assert not inner._close_complete, "An initialized child has not acknowledged cleanup"
    panel.font_list.setCurrentRow(0)
    assert inner.state.font is first and inner.preview.font is first, (
        "Selection supplies the exact font to both views"
    )
    inner.state.selected = ("A",)
    panel.sort()
    assert panel.state.fonts == (second, first) and panel.state.selected is first, (
        "Sorting keeps selected identity"
    )
    assert inner.state.selected == ("A",), (
        "Refreshing the same font retains glyph selection"
    )
    panel.select(0)
    assert inner.state.font is second and inner.state.selected == (), (
        "Changing fonts clears old glyph selection"
    )
    panel.refresh([])
    assert panel.count_label.text == "0 fonts" and not inner.widget.enabled, (
        "Removing every font disables the glyph browser"
    )
    panel.select(-1)
    panel.close()
    before = inner.refresh.call_count
    panel.refresh([first])
    panel.sort()
    panel.select(0)
    panel.close()
    assert panel.closed and inner.refresh.call_count == before, (
        "Closed browsers never refresh borrowed fonts"
    )
    inner.close.assert_called_once_with()


def test_feature_view_when_built_then_labels_staging_and_explicit_apply(monkeypatch):
    import importlib
    import shiboken6
    from _feature_source_qt import owned_application, qt_namespace

    name = "fontlabapp.fontui.features_view"
    previous = sys.modules.get(name)
    monkeypatch.setitem(sys.modules, "PythonQt", qt_namespace())
    monkeypatch.delitem(sys.modules, name, raising=False)
    with owned_application():
        module = importlib.import_module(name)
        widget = module.QtGui.QWidget()
        owner = NS(widget=widget, layout=module.QtGui.QVBoxLayout(widget),
                   closed=False, _mark=lambda: None)
        try:
            module.build(owner)
            assert owner.block_control.accessibleName() == "Feature block", (
                "The block selector is labelled"
            )
            assert owner.text_control.accessibleName() == "Feature code (stored, not compiled)", (
                "The code editor discloses staging"
            )
            assert (
                owner.apply_button.text() == "&Apply to font"
                and owner.revert_button.text() == "Re&vert to font"
            ), "Apply and Revert remain explicit separate actions"
            assert (
                owner.add_button.text() == "A&dd feature"
                and owner.remove_button.text() == "Re&move feature"
            ), "Block editing controls remain available"
            assert owner.diagnostic.wordWrap(), "Diagnostics wrap instead of clipping"
        finally:
            owner.closed = True
            shiboken6.delete(widget)
            assert not shiboken6.isValid(widget)
            sys.modules.pop(name, None)
            if previous is not None:
                sys.modules[name] = previous


def test_preview_when_painted_then_draws_overlays_and_releases_painter_on_error(
    controls, monkeypatch
):
    module = controls.load("fontlabapp.fontui.preview")
    font = fq.ufo_font()
    preview = module.Preview(font, "A")
    painter = Mock()
    monkeypatch.setattr(controls.qt.QtGui, "QPainter", Mock(return_value=painter))
    monkeypatch.setattr(
        controls.qt.QtGui, "QPainterPath", Mock(side_effect=lambda: Mock())
    )
    assert preview.data.width == 600 and preview.diagnostic.text == "A", (
        "Preview captures the selected glyph"
    )
    preview.zoom_buttons["+"].clicked.emit()
    assert preview.zoom == 1.25, "Zoom buttons drive the displayed multiplier"
    preview.zoom_buttons["Fit"].clicked.emit()
    preview.set_option("oncurve", True)
    preview.set_option("anchors", True)
    preview.paint(preview.canvas)
    assert painter.drawPath.call_count == 2 and painter.drawLine.call_count == 5, (
        "Paint draws both contour paths and all advance/vertical metrics"
    )
    assert painter.drawEllipse.call_count > 0 and preview.data is not None, (
        "Enabled point overlays paint without discarding data"
    )
    painter.end.assert_called_once_with()
    preview.set_option("fill", False)
    preview.set_option("stroke", False)
    preview.set_option("metrics", False)
    font.info.ascender = font.info.descender = None
    preview.paint(preview.canvas)
    assert preview.data is not None, "Missing font metrics use the documented defaults"
    del font["A"]
    preview.paint(preview.canvas)
    assert (
        preview.data is None
        and "Missing component or glyph: A" == preview.diagnostic.text
    ), "Paint-time deletion discards stale geometry visibly"
    assert painter.end.call_count == 3, (
        "Every paint attempt ends its painter, including failed reads"
    )
    preview.set_glyph(None)
    assert preview.diagnostic.text == "No glyph selected", (
        "Clearing selection removes old glyph data"
    )
    preview.close()
    preview.refresh()
    preview._zoom(10)
    with pytest.raises(RuntimeError, match="Preview is closed"):
        preview.set_glyph("V")
    preview.paint(preview.canvas)
    assert painter.end.call_count == 4 and preview.zoom == 1.0, (
        "Closed previews stop updates and still release a painter"
    )



def _install_browser_constructor_boundary(controls, monkeypatch):
    """Supply only list/item/pixmap capabilities used by the real constructors."""
    class BrowserItem(fq.Item):
        def __init__(self, name):
            super().__init__(name)
            self.selected = False

        def setIcon(self, icon):
            self.icon = icon

        def setSelected(self, selected):
            self.selected = bool(selected)

        def isSelected(self):
            return self.selected

    class BrowserList(fq.FakeWidget):
        def __init__(self, *args):
            super().__init__(*args)
            self.itemDoubleClicked = fq.Signal()

        def addItem(self, item):
            self.items.append(item)

        def item(self, index):
            return self.items[index]

    def fill(pixmap, color):
        pixmap.calls.append(("fill", (color,)))

    monkeypatch.setattr(controls.qt.QtGui, "QListWidget", BrowserList)
    monkeypatch.setattr(controls.qt.QtGui, "QListWidgetItem", BrowserItem)
    monkeypatch.setattr(controls.qt.QtGui.QPixmap, "fill", fill, raising=False)


@pytest.mark.parametrize("case", ['hide', 'deleteLater'])
def test_browser_when_actual_preview_fails_then_callbacks_and_work_are_fenced_before_child(controls, monkeypatch, case):
    _install_browser_constructor_boundary(controls, monkeypatch)
    from copy import deepcopy
    module = controls.load("fontlabapp.fontui.native")
    font = fq.ufo_font()
    before = deepcopy(font)
    owner = module.Browser(font, on_activate=lambda *a: None, on_selection=lambda *a: None)
    child = owner.preview
    assert type(child).__name__ == "Preview"
    normal = getattr(child.widget, case)
    error = RuntimeError("real Preview partial stage")
    def fail():
        assert owner.closed and owner.on_selection is None and owner.on_activate is None
        raise error
    monkeypatch.setattr(child.widget, case, fail)
    captured = None
    try:
        owner.close()
    except BaseException as caught:
        captured = caught
    assert captured is error and owner.closed and not owner._close_complete
    assert owner.on_selection is owner.on_activate is None and not child._close_complete
    monkeypatch.setattr(child.widget, case, normal)
    owner.close()
    owner.close()
    assert owner._close_complete and child._close_complete and font == before



@pytest.mark.parametrize("case", ['browser-hide', 'browser-deleteLater', 'preview-hide', 'preview-deleteLater'])
def test_font_browser_when_nested_partial_close_fails_then_retry_skips_completed_descendants(controls, monkeypatch, case):
    _install_browser_constructor_boundary(controls, monkeypatch)
    from copy import deepcopy
    role, stage = case.split("-", 1)
    module = controls.load("fontlabapp.fontui.fonts")
    font = fq.ufo_font()
    before = deepcopy(font)
    owner = module.FontBrowser([font], on_activate=lambda *a: None)
    browser, preview = owner.browser, owner.browser.preview
    preview_close = preview.close
    calls = []
    def close_preview():
        calls.append("preview")
        return preview_close()
    monkeypatch.setattr(preview, "close", close_preview)
    target = browser if role == "browser" else preview
    normal = getattr(target.widget, stage)
    error = RuntimeError("real nested stage")
    def fail():
        assert owner.closed and browser.closed
        assert browser.on_activate is browser.on_selection is None
        raise error
    monkeypatch.setattr(target.widget, stage, fail)
    captured = None
    try:
        owner.close()
    except BaseException as caught:
        captured = caught
    assert captured is error and not owner._close_complete
    monkeypatch.setattr(target.widget, stage, normal)
    owner.close()
    owner.close()
    assert owner._close_complete and browser._close_complete and preview._close_complete
    assert calls == (["preview"] if role == "browser" else ["preview", "preview"])
    assert font == before



@pytest.mark.parametrize("case", ['none', 'false', 'zero'])
def test_browser_when_child_closes_normally_then_falsy_return_remains_ignored(controls, monkeypatch, case):
    _install_browser_constructor_boundary(controls, monkeypatch)
    module = controls.load("fontlabapp.fontui.native")
    owner = module.Browser(fq.ufo_font())
    child = owner.preview
    normal = child.close
    calls = []
    def close_child():
        calls.append(case)
        normal()
        return {"none": None, "false": False, "zero": 0}[case]
    monkeypatch.setattr(child, "close", close_child)
    owner.close()
    owner.close()
    assert calls == [case] and child._close_complete and owner._close_complete
