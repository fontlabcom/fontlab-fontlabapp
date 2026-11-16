# this_file: tests/test_public_examples.py
"""Run public examples/ through real Fly with detached models and owned host stand-ins."""

from contextlib import contextmanager
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

import pytest

from _demo_support import stub_module

ROOT = Path(__file__).resolve().parents[1]


def test_font_browser_when_run_then_opens_detached_triangle_through_canonical_factory(monkeypatch):
    import fontlabapp.fontui as fontui

    owner = NS(widget=MagicMock())
    fonts = []
    monkeypatch.setattr(fontui, "font_browser", lambda values: fonts.extend(values) or owner)
    namespace = runpy.run_path(str(ROOT / "examples/font_browser.py"))
    assert namespace["browser"] is owner
    font, = fonts
    assert font.info.familyName == "Browser demonstration"
    assert font.info.styleName == "Regular" and list(font.keys()) == ["A"]
    assert font["A"].width == 600
    assert [(point.x, point.y) for point in font["A"].contours[0].points] == [(50, 0), (300, 700), (550, 0)]
    owner.widget.resize.assert_called_once_with(850, 1000)
    owner.widget.show.assert_called_once_with()


def test_font_features_when_called_then_retains_editor_for_explicit_borrowed_font(monkeypatch):
    import fontlabapp.fontui as fontui

    font, calls = object(), []
    owner = NS(widget=MagicMock())
    monkeypatch.setattr(fontui, "features_editor", lambda value: calls.append(value) or owner)
    namespace = runpy.run_path(str(ROOT / "examples/font_features.py"))
    assert calls == []
    assert namespace["edit_features"](font) is owner
    assert calls == [font]
    owner.widget.resize.assert_called_once_with(800, 600)
    owner.widget.show.assert_called_once_with()


def test_native_smoke_when_run_then_preserves_explicit_no_preference_initialization(monkeypatch, capsys):
    import fontlabapp

    calls = []
    app = NS(main=object(), ui=object(), versions=NS(app_version="9-test", qt_version="qt-test"))
    monkeypatch.setitem(fontlabapp.__dict__, "Application", lambda **kwargs: calls.append(kwargs) or app)
    namespace = runpy.run_path(str(ROOT / "examples/native_smoke.py"))
    assert namespace["app"] is app
    assert calls == [{"with_ui": True, "with_preflib": False}]
    assert capsys.readouterr().out == "9-test qt-test\n"


@pytest.mark.parametrize("has_glyph", [False, True])
def test_drawing_when_run_then_captures_only_owned_preview_and_optional_glyph_and_closes_compositions(monkeypatch, tmp_path, has_glyph):
    import fontlabapp

    (tmp_path / "Desktop").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    qt, painter = MagicMock(), MagicMock()
    stub_module(monkeypatch, "PythonQt", QtGui=qt)
    events, handles = [], []

    @contextmanager
    def draw(paint):
        paint(painter)
        yield NS(raise_if_failed=lambda: events.append("checked"))

    def compose(*args, build=None):
        (build or args[-1])(object())
        handle = MagicMock()
        handles.append(handle)
        return handle

    class Control:
        preview = NS(draw=draw, widget="preview")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            events.append("released")

        def glyph_windows(self):
            return [NS(draw=draw, canvas=NS(viewPort=NS(grab=lambda: "pixmap")))] if has_glyph else []

        create_panel = staticmethod(compose)
        create_dialog = staticmethod(compose)
        create_widget = staticmethod(compose)

    app = NS(control=Control())
    monkeypatch.setitem(fontlabapp.__dict__, "Application", lambda: app)
    capture = MagicMock()
    stub_module(monkeypatch, "grablab", Grab=lambda **kwargs: capture)
    namespace = runpy.run_path(str(ROOT / "examples/drawing.py"))
    assert namespace["app"] is app
    assert events == ["checked"] * (1 + has_glyph) + ["released"]
    assert capture.getWidgetSVG.call_count == 1 + has_glyph
    assert capture.getPixmapPNG.call_count == has_glyph
    assert len(handles) == 3
    for handle in handles:
        handle.close.assert_called_once_with()
    assert qt.QVBoxLayout.return_value.addWidget.call_count == 6
    assert painter.drawText.call_args.args == (30, 80, "Overlay Łódź")
    assert namespace["folder"] == tmp_path / "Desktop/fontlab-overlay"
