# this_file: tests/test_issue205_controls.py
"""Native control transport and owned resource lifetime stay exact."""

import importlib
from types import SimpleNamespace as NS

import pytest

controls = importlib.import_module("fontlabapp.core.controls")


def test_native_tools_when_dispatched_then_names_arguments_and_results_are_preserved(
    monkeypatch,
):
    calls = []
    marker = {"fonts": [{"id": 42}]}
    native = NS(
        call=lambda name, **kw: calls.append((name, kw)) or marker,
        GetProperty=lambda name: "owned output",
        CurrentFont=lambda: "font",
        CurrentGlyph=lambda: "glyph",
    )
    monkeypatch.setattr(controls, "_native", lambda name: native)
    api = controls.FontLab(NS())
    names = {
        "open_font": "open_font",
        "new_font": "new_font",
        "save_font": "save_font",
        "close_font": "close_font",
        "list_glyphs": "list_glyphs",
        "font_info": "get_font_info",
        "glyph_info": "get_glyph",
        "font_metrics": "get_font_metrics",
        "glyph_metrics": "get_glyph_metrics",
        "set_font_metrics": "set_font_metrics",
        "set_glyph_metrics": "set_glyph_metrics",
        "activate_font": "set_active_font",
        "activate_glyph": "set_active_glyph",
        "run_actions": "run_actions",
    }
    for method, native_name in names.items():
        assert getattr(api, method)(font_id=42) is marker
        assert calls[-1] == (native_name, {"font_id": 42})
    for method, native_name in (
        ("current_font", "get_active_font"),
        ("current_glyphs", "get_current_glyphs"),
        ("list_actions", "list_actions"),
    ):
        assert getattr(api, method)() is marker and calls[-1] == (native_name, {})
    assert api.fonts() == [{"id": 42}]
    assert api.glyph("A", font_id=42) is marker and calls[-1] == (
        "get_glyph",
        {"glyph_name": "A", "font_id": 42},
    )
    assert (api.output(), api.native_font, api.native_glyph) == (
        "owned output",
        "font",
        "glyph",
    )


def test_controls_when_owning_resources_then_context_closes_only_owned_in_reverse_order(
    monkeypatch,
):
    import fontlabapp

    widgets = importlib.import_module("fontlabapp.qt.widgets")
    closed = []

    def create(*args, **kwargs):
        return NS(args=args, kwargs=kwargs, close=lambda: closed.append(args))

    for name in ("create_panel", "create_dialog", "create_widget"):
        monkeypatch.setattr(widgets, name, create)
    application = NS(main="main")
    monkeypatch.setitem(vars(fontlabapp), "Application", lambda **kw: application)
    with controls.FontLab() as api:
        panel = api.create_panel("Owned", area="left")
        dialog = api.create_dialog("Question")
        widget = api.create_widget(show=False)
        child = api.create_widget(parent="parent")
        assert panel.args == ("main", "Owned", None, "left")
        assert dialog.args == ("main", "Question", None)
        assert widget.kwargs == {"floating": True, "show": False}
        assert child.kwargs == {"floating": False, "show": True}
    assert closed == [child.args, widget.args, dialog.args, panel.args]
    api.close()
    assert len(closed) == 4 and api._owned == []


def test_ui_when_panels_and_active_canvas_change_then_exact_selection_or_refusal(
    monkeypatch,
):
    ui_module = importlib.import_module("fontlabapp.core.application.ui")
    ui = NS(
        panels={"preview": {"widget": object()}, "missing": {"widget": None}},
        glyphWindows=lambda: {"A": "one", "B": "two"},
    )
    monkeypatch.setattr(ui_module, "ApplicationUI", lambda app: ui)
    monkeypatch.setattr(
        controls,
        "GlyphWindow",
        lambda window, ws, owner: NS(canvas=window, owner=owner),
    )
    monkeypatch.setattr(
        controls, "Preview", lambda panel, owner: NS(panel=panel, _owner=owner)
    )
    app = NS(main="main", ws=NS(getActiveCanvas=lambda: "two"))
    api = controls.FontLab(app)
    assert api._ui() is api._ui() is ui
    assert api.panel("preview").widget is ui.panels["preview"]["widget"]
    assert api.preview._owner is api
    assert api.glyph_window().canvas == "two"
    for name in ("missing", "unknown"):
        with pytest.raises(LookupError, match="panel is unavailable"):
            api.panel(name)
    app.ws.getActiveCanvas = lambda: "gone"
    with pytest.raises(LookupError, match="No active Glyph window"):
        api.glyph_window()
