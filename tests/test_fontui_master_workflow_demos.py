# this_file: tests/test_fontui_master_workflow_demos.py
"""Each App menu captures its explicit world/font once and dispatches lazily."""

from pathlib import Path
import runpy
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ("Open Fonts and Master Overview", "open_fonts_overview", True),
    ("Master Compatibility Browser", "master_compatibility", False),
    ("Node Counts Across Masters", "node_counts_masters", False),
    ("Font Info and Vertical Metrics", "font_info_metrics", False),
    ("Designspace Source Comparison", "source_comparison", False),
)


@pytest.mark.parametrize("title,module_name,all_fonts", WORKFLOWS)
@pytest.mark.parametrize("entry", ["main", "__main__"])
def test_demo_when_invoked_then_capture_once_and_return_owner(monkeypatch, title, module_name, all_fonts, entry):
    calls = []
    font, owner = object(), object()
    class World:
        def __init__(self):
            calls.append(self)
        def CurrentFont(self):
            calls.append("current")
            return font
    world_module = ModuleType("fontlab_fontport.world")
    world_module.FontWorld = World
    target = ModuleType("fontlabapp.fontui." + module_name)
    def show(value):
        assert value is calls[0] if all_fonts else value is font
        calls.append("show")
        return owner
    target.show = show
    monkeypatch.setitem(sys.modules, world_module.__name__, world_module)
    monkeypatch.setitem(sys.modules, target.__name__, target)
    path = ROOT / "Scripts/Font Editors" / (title + " Demo.py")
    loaded = runpy.run_path(str(path), run_name=entry)
    if entry == "main":
        assert not calls
        assert loaded["main"]() is owner
    assert calls[1:] == (["show"] if all_fonts else ["current", "show"])
