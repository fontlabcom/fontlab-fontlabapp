# this_file: tests/test_fontui_interpolation_preview_demo.py
"""Real App demo dispatch through FontWorld into the owned interpolation controls."""
import importlib.util
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_fontui_interpolation_preview import actual_qt, native_model, preview  # noqa: F401
from test_fontui_master_width_comparison_demo import cold_import

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "Scripts/Font Editors/Interpolation Preview Demo.py"
MODULE = ROOT / "src/fontlabapp/fontui/interpolation_preview.py"


@pytest.mark.parametrize("dispatch", ["main", "script", "none"])
def test_demo_when_invoked_then_capture_once_and_keep_borrowed_font(preview, monkeypatch, dispatch):  # noqa: F811 - imported pytest fixture
    from fontlabapp.qt import safe

    _, api, _, _, parent = preview
    monkeypatch.setattr(safe, "main_window", lambda *args: parent)
    active = [None if dispatch == "none" else 71]
    calls = []

    def call(tool, **kwargs):
        calls.append(tool)
        if tool == "list_fonts":
            return {"fonts": [{"id": 71}] if active[0] is not None else []}
        if tool == "get_active_font":
            return {"id": active[0]}
        raise AssertionError("Unexpected native operation: " + tool)

    monkeypatch.setitem(sys.modules, "fontpr", SimpleNamespace(call=call, Error=RuntimeError))
    before = list(api._HANDLES)
    if dispatch == "script":
        runpy.run_path(str(ENTRY), run_name="__main__")
        owner, = [item for item in api._HANDLES if item not in before]
    else:
        spec = importlib.util.spec_from_file_location("interpolation_entry", ENTRY)
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        assert api._HANDLES == before
        owner = entry.main()
    try:
        if dispatch == "none":
            assert owner.controls is None and "registered" in owner.status.text
            assert calls.count("get_active_font") == 0
        else:
            captured = owner.font
            active[0] = None
            owner.glyph.setText("A")
            owner.refresh()
            owner.controls.axes["Weight"][1].setValue(500)
            assert owner.view.mix[0][0] == (50, 0, True)
            assert owner.font is captured
            assert calls.count("get_active_font") == 1
        assert set(calls) <= {"list_fonts", "get_active_font"}
    finally:
        owner.close()
        assert owner._close_complete


def test_demo_when_cold_imported_then_host_dependencies_stay_unloaded():
    cold_import(MODULE, ENTRY)
