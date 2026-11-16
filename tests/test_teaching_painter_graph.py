# this_file: tests/test_teaching_painter_graph.py
"""The drawing and graph lessons retain callable models and build-only panels."""

import importlib
import pytest
from types import SimpleNamespace
from _studio_qt import studio_qt  # noqa: F401





@pytest.mark.parametrize("module, function", [
    ("teaching_painter.outline_svg", "svg_text"),
    ("teaching_painter.svg_reference", "alignment_matrix"),
    ("teaching_painter.sketch", "sketch_svg"),
    ("teaching_painter.polygon", "polygon_points"),
    ("teaching_graph.feature_graph", "feature_draft"),
])
def test_extracted_lesson_when_imported_then_preserves_model_and_panel_factory(module, function):
    lesson = importlib.import_module("fontlabapp.fontui." + module)
    assert callable(getattr(lesson, function))
    assert callable(lesson.panel_type)


def test_polygon_and_graph_models_preserve_exact_outputs():
    from fontlabapp.fontui.teaching_graph.feature_graph import (
        feature_draft,
        variant_edges,
    )
    from fontlabapp.fontui.teaching_painter.polygon import polygon_points

    assert polygon_points(1000, 4, .5, .25, 0)[0] == (500, 0)
    edges = variant_edges(("a", "a.ss01", "orphan.ss01"), "ss01")
    assert edges == (("a", "a.ss01"),)
    assert feature_draft(edges).endswith("sub \\a by \\a.ss01;")





@pytest.mark.parametrize("kind", ["teaching_painter", "teaching_graph"])
@pytest.mark.parametrize("fail", [False, True])
def test_lab_when_composed_then_named_panels_owned_and_errors_close(studio_qt, monkeypatch, kind, fail):  # noqa: F811
    import fontlabapp
    from fontlabapp.components.graph.elastic import ui
    from fontlabapp.components.graph import native
    from fontlabapp.fontui.teaching import host

    module = importlib.import_module("fontlabapp.fontui." + kind)
    seen, actions, calls = [], [], []
    panel = SimpleNamespace(
        capture_result=lambda: calls.append("capture"),
        refresh_proof=lambda: calls.append("proof"),
        compare=lambda: calls.append("compare"),
        preview=lambda: calls.append("preview"),
        svg_text=lambda: calls.append("svg"),
        publish=lambda save: calls.append(save),
        canvas=SimpleNamespace(strokes=[1]),
        parameters=lambda: (5, .45, .2, 90),
        draw_polygon=lambda: calls.append("draw"),
        refresh=lambda: calls.append("refresh"),
        close_button=SimpleNamespace(hide=lambda: None, setEnabled=lambda value: None),
    )
    shell = SimpleNamespace(widget=object(), preview_context=(1, "A", 2), set_actions=lambda *a, **kw: actions.append(kw),
                            set_about=lambda text: calls.append(text), close=lambda: calls.append("close"),
                            _run_action=lambda action: calls.append(action))
    monkeypatch.setattr(fontlabapp, "_native", lambda name: SimpleNamespace(QtCore=studio_qt.QtCore, QtGui=object()))
    monkeypatch.setattr(host, "create", lambda *a, **kw: shell)
    monkeypatch.setattr(host, "embed", lambda shell, title, panel: seen.append(title) or panel)
    monkeypatch.setattr(host, "finish", lambda shell: shell)
    monkeypatch.setattr(host, "refresh_current_preview", lambda shell: calls.append("refresh preview"), raising=False)
    monkeypatch.setattr(host, "require_current_preview", lambda shell: calls.append("check target"), raising=False)
    def bind(shell):
        if fail:
            raise ValueError("preview failed")
    monkeypatch.setattr(host, "bind_current_preview", bind)
    names = ("outline_svg", "svg_reference", "sketch", "polygon") if kind == "teaching_painter" else ("feature_graph",)
    for name in names:
        child = importlib.import_module("fontlabapp.fontui." + kind + "." + name)
        monkeypatch.setattr(child, "panel_type", lambda qt: lambda parent: panel)
    monkeypatch.setattr(ui, "panel_type", lambda *a: lambda *a: panel)
    monkeypatch.setattr(native, "capture", lambda **kwargs: calls.append(("capture graph", kwargs)))
    if fail:
        with pytest.raises(ValueError, match="preview failed"):
            module.show()
        assert calls[-1] == "close"
    else:
        assert module.show() is shell
        assert seen == (["SVG export", "SVG reference", "Sketch", "Polygon"] if kind == "teaching_painter"
                        else ["Dependency forces", "Degree forces", "Feature graph"])
        panel.lab_close()
        if kind == "teaching_graph":
            panel.capture(deadline=7)
            assert calls[-2:] == ["refresh preview", ("capture graph", {"deadline": 7})]
            panel.lab_refresh_preview()
            assert calls[-1] == "refresh preview"
        if kind == "teaching_painter":
            panel.lab_refresh_preview()
            with pytest.raises(ValueError, match="Preview Changes"):
                panel.lab_check_target()
            panel.lab_accept_preview(panel.parameters())
            panel.lab_check_target()
            shell.preview_context = (1, "B", 3)
            with pytest.raises(ValueError, match="Preview Changes"):
                panel.lab_check_target()
            shell.preview_context = (1, "A", 2)
            panel.lab_applied()
            with pytest.raises(ValueError, match="Preview Changes"):
                panel.lab_check_target()
            panel.lab_accept_preview(panel.parameters())
        for action in actions:
            for callback in action.values():
                if callable(callback):
                    callback()


@pytest.mark.parametrize("module", ["outline_svg", "svg_reference", "sketch"])
@pytest.mark.parametrize("case", ["no_font", "no_layer", "wrong_font", "empty", "label", "invalid_upm", "bounds", "deadline"])
def test_outline_capture_when_invalid_then_refuses_before_preview(monkeypatch, module, case):
    from fontlabapp.contours.nodes import coordinates
    from fontlabapp.core import scripting
    from fontlabapp.proof.inspectors import model as inspectors

    lesson = importlib.import_module("fontlabapp.fontui.teaching_painter." + module)
    package = SimpleNamespace(id=1, fgId=2, master="Regular", upm=1000,
                              descender_value=-200, ascender_value=800)
    layer = SimpleNamespace(id=3, isNull=False, advanceWidth=600)
    glyph = SimpleNamespace(id=4, name="A", package=package, findLayer=lambda name: layer)
    bounds = SimpleNamespace(x=lambda: 0, y=lambda: 0, right=lambda: 600, bottom=lambda: 700)
    path = SimpleNamespace(isEmpty=lambda: case == "empty", boundingRect=lambda: bounds)
    monkeypatch.setattr(scripting, "current_package", lambda *a: None if case == "no_font" else package)
    monkeypatch.setattr(coordinates, "current_glyph", lambda package: glyph)
    monkeypatch.setattr(inspectors, "outline_source", lambda layer: ())
    monkeypatch.setattr(inspectors, "outline", lambda layer: path)
    if case == "no_layer":
        glyph.findLayer = lambda name: None
    elif case == "wrong_font":
        glyph.package = SimpleNamespace(id=99)
    elif case == "label":
        glyph.name = "A\u2028"
    elif case == "invalid_upm":
        package.upm = -1
    elif case == "bounds":
        bounds.right = lambda: float("inf")
    elif case == "deadline":
        ticks = iter([0, 3, 3, 3])
        monkeypatch.setattr(lesson, "monotonic", lambda: next(ticks))
    refused = case in {"no_font", "no_layer", "deadline"}
    refused |= module != "sketch" and case in {"wrong_font", "empty", "label"}
    refused |= module == "sketch" and case in {"invalid_upm", "bounds"}
    if refused:
        with pytest.raises((ValueError, TimeoutError)):
            lesson.capture_outline()
    else:
        assert lesson.capture_outline()[1] is path


def test_painter_numeric_overflow_and_invalid_xml_are_refused():
    from fontlabapp.fontui.teaching_painter import outline_svg, sketch, svg_reference

    with pytest.raises(ValueError, match="XML"):
        sketch.sketch_svg("A\x00", [[(1, 2)]], (0, 0, 100, 100))
    path = SimpleNamespace(boundingRect=lambda: SimpleNamespace(x=0, y=0, width=1e12, height=100))
    with pytest.raises(ValueError, match="document size"):
        outline_svg.font_frame(path, (500, -200, 800))
    with pytest.raises(ValueError, match="finite range"):
        svg_reference.alignment_matrix((1e300, 0, 1e-300, 1e-300), (0, 0, 1e300, 1e300))
    with pytest.raises(ValueError, match="finite range"):
        svg_reference.reference_matrix((1e300, 0, 1e-300, 1e-300), (0, 0, 1e300, 1e300), (0, 0, 100, 100), True)
