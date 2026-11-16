# this_file: tests/test_wp05_route_behaviour_rasc.py
"""Practical one-category Fly facade, exact original attribution, no eager action."""

import runpy
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / "src/fontlabapp/fontui/outline_routes/raise_ascender.py"


def test_menu_import_and_public_main_each_lazy_forward_once(monkeypatch):
    calls = []
    module = ModuleType("fontlabapp.contours.raise_ascender.model")
    module.show = lambda: calls.append(True) or "owned"
    monkeypatch.setitem(sys.modules, module.__name__, module)
    namespace = runpy.run_path(str(MENU))
    assert not calls
    assert namespace["main"]() == "owned"
    runpy.run_path(str(MENU), run_name="__main__")
    assert calls == [True, True]


