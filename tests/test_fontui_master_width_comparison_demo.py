# this_file: tests/test_fontui_master_width_comparison_demo.py
"""Actual lazy App/FontWorld/native boundary dispatch into the shared window."""
import importlib
import importlib.util
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace

import pytest
from test_fontui_master_width_comparison import actual_qt as _qt_fixture, native_model as _native_fixture, choose
actual_qt, native_model = _qt_fixture, _native_fixture
del _qt_fixture, _native_fixture
ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "Scripts/Font Editors/Master Width Comparison Demo.py"
MODULE = ROOT / "src/fontlabapp/fontui/master_width_comparison.py"


def dispatch_entry(entry_path, actual_qt, native_model, monkeypatch, dispatch):
    from PySide6.QtWidgets import QMainWindow
    _, _, app = actual_qt
    _, package, _, _ = native_model
    parent = QMainWindow()
    native = sys.modules["fontlab"]
    monkeypatch.setattr(native, "MainWindow", lambda: parent, raising=False)
    calls = []
    active = [None if dispatch == "none" else 71]
    def call(tool, **kwargs):
        calls.append((tool, kwargs))
        if tool == "list_fonts":
            return {"fonts": [{"id": 71}] if active[0] is not None else []}
        if tool == "get_active_font":
            return {"id": active[0]}
        raise AssertionError("Unexpected native operation: " + tool)
    monkeypatch.setitem(sys.modules, "fontpr", SimpleNamespace(call=call, Error=RuntimeError))
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    before = list(module._HANDLES)
    owner = None
    try:
        if dispatch == "script":
            runpy.run_path(str(entry_path), run_name="__main__")
            owner, = [x for x in module._HANDLES if x not in before]
        else:
            spec = importlib.util.spec_from_file_location("master_width_entry", entry_path)
            entry = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(entry)
            assert module._HANDLES == before
            owner = entry.main()
        expected = 0 if dispatch == "none" else 1
        assert sum(tool == "get_active_font" for tool, _ in calls) == expected
        if dispatch == "none":
            assert owner.rows == () and owner.sequence is None
            assert "registered FontLab" in owner.diagnostic.text
        else:
            captured = owner.font
            active[0] = None
            choose(owner)
            assert owner.font is captured and owner.font._backend.font_id == package.fgId
            assert owner.rows == (("Light", 500.25), ("Middle", None), ("Bold", 750.75))
            assert sum(tool == "get_active_font" for tool, _ in calls) == 1
        assert all(tool in ("list_fonts", "get_active_font") for tool, _ in calls)
    finally:
        if owner is not None:
            owner.release()
            app.processEvents()
            assert owner._released
        parent.deleteLater()
        app.processEvents()


@pytest.mark.parametrize("dispatch", ["main", "script", "none"])
def test_entry_when_invoked_then_capture_once_and_keep_document(actual_qt, native_model, monkeypatch, dispatch):
    dispatch_entry(ENTRY, actual_qt, native_model, monkeypatch, dispatch)


def cold_import(module, entry):
    code = """
import importlib.abc, importlib.util, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('fontlab', 'PythonQt', 'PySide6', 'fontlab_fontport', 'ufoLib2'):
            raise AssertionError('Cold import touched ' + fullname)
sys.meta_path.insert(0, Block())
for filename in sys.argv[1:]:
    spec = importlib.util.spec_from_file_location('cold_master_width', filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, str(module), str(entry)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_import_when_host_unavailable_then_module_and_demo_remain_cold():
    cold_import(MODULE, ENTRY)
