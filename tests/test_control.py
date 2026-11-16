# this_file: tests/test_control.py
"""Host-free direct controls and ownership contracts."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fontlabapp import FontLab
from fontlabapp.core.controls import GlyphWindow, Panel, Preview


def test_native_control_import_is_light_and_named_call_arguments_preserved(monkeypatch):
    pr = SimpleNamespace(call=Mock(return_value={"id": 42}))
    monkeypatch.setitem(sys.modules, "fontpr", pr)
    control = FontLab.__new__(FontLab)
    assert control.glyph_metrics(font_id=7, glyph_name="ą") == {"id": 42}
    pr.call.assert_called_once_with("get_glyph_metrics", font_id=7, glyph_name="ą")
    monkeypatch.setitem(
        sys.modules,
        "fontlab",
        SimpleNamespace(GetProperty=Mock(return_value="full output")),
    )
    assert control.output() == "full output"
    assert not hasattr(pr, "get_python_output"), (
        "Output must use the real native property"
    )


def test_panel_visibility_is_explicit_never_toggles_and_focus_is_scoped():
    widget = Mock()
    widget.isVisible.return_value = False
    panel = Panel(widget)
    panel.show()
    panel.hide()
    panel.focus()
    assert widget.setVisible.call_args_list[0].args == (True,)
    assert widget.setVisible.call_args_list[1].args == (False,)
    widget.raise_.assert_called_once()
    widget.setFocus.assert_called_once()


def test_preview_content_lookup_is_scoped_and_settings_use_verified_setters(
    monkeypatch,
):
    a = SimpleNamespace(
        className=lambda: "FontPreviewWidget",
        objectName="widgetPreview",
        setText=Mock(),
        setFontSize=Mock(),
    )
    other = SimpleNamespace(className=lambda: "QWidget", objectName="widgetPreview")
    parent = SimpleNamespace(findChildren=lambda cls: [other, a])
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtGui=SimpleNamespace(QWidget=object))
    )
    preview = Preview(parent)
    preview.set_text("Ą")
    preview.set_font_size(42)
    assert preview.widget is a
    a.setText.assert_called_once_with("Ą", True)
    with pytest.raises(ValueError):
        preview.set_font_size(-1)
    with pytest.raises(ValueError, match="pixels"):
        preview.draw(lambda painter: None, coordinates="canvas")


def test_glyph_canvas_resolves_inner_viewport_without_focusing_or_closing(monkeypatch):
    inner = SimpleNamespace(className=lambda: "QWidget")
    outer = SimpleNamespace(findChildren=lambda cls: [inner])
    widget = SimpleNamespace(widgetViewport=outer)
    canvas = object()
    ws = SimpleNamespace(
        getCanvasForViewport=lambda viewport: canvas if viewport is inner else None
    )
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtGui=SimpleNamespace(QWidget=object))
    )
    glyph = GlyphWindow(widget, ws)
    assert glyph.canvas is canvas and glyph.viewport is outer


def test_application_control_is_lazy_and_uses_same_application(monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtGui=SimpleNamespace())
    )
    from fontlabapp.core.application.context import Application

    app = Application.__new__(Application)
    assert app.control.application is app


def test_catalogue_panel_names_use_native_panel_ids_and_short_glyph_binding(
    monkeypatch,
):
    control = FontLab.__new__(FontLab)
    main = Mock()
    control.application = SimpleNamespace(
        main=main,
        ui=SimpleNamespace(
            panels={
                name: {"widget": Mock()} for name in ("node", "guide", "layers_masters")
            }
        ),
    )
    for name, identifier in [("node", 15), ("guide", 16), ("layers_masters", 9)]:
        control.panel(name).show()
        main.showPanel.assert_called_with(identifier, True)
    pr = SimpleNamespace(call=Mock(return_value={"glyph": "A"}))
    monkeypatch.setitem(sys.modules, "fontpr", pr)
    assert control.glyph("A", font_id=7) == {"glyph": "A"}
    pr.call.assert_called_once_with("get_glyph", glyph_name="A", font_id=7)
