# this_file: tests/test_fontui_tabular_audit_demo.py
"""The shipped App demo uses a genuine FontWorld and retains show results."""
import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize("run_name", ["audit_demo", "__main__"])
def test_demo_dispatches_one_real_world_and_retains_owner(monkeypatch, run_name):
    from fontlabapp.fontui import tabular_audit
    from fontlab_fontport.world import FontWorld

    calls = []
    retained = object()
    def show(world):
        assert isinstance(world, FontWorld)
        calls.append(world)
        return retained
    monkeypatch.setattr(tabular_audit, "show", show)
    path = Path(__file__).resolve().parents[1] / "Scripts/Font Editors/Tabular Width Audit Demo.py"
    namespace = runpy.run_path(str(path), run_name=run_name)
    if run_name == "audit_demo":
        assert calls == []
        assert namespace["main"]() is retained
    else:
        assert namespace["handle"] is retained
    assert len(calls) == 1
