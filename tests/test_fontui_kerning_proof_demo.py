# this_file: tests/test_fontui_kerning_proof_demo.py
"""The actual lazy demo captures one real borrowed FontWorld font."""

import runpy
from pathlib import Path
import pytest


@pytest.mark.parametrize("active", [None, 1, 2])
@pytest.mark.parametrize("route", ["inspection", "__main__"])
def test_demo_when_dispatched_then_one_real_capture_and_exact_owner(monkeypatch, active, route):
    from fontlab_fontport import application
    from fontlab_fontport.memory import UFOBackend
    from fontlab_fontport.live import RFont
    from ufoLib2 import Font
    from fontlabapp.fontui import kerning_proof

    backends = {identifier: UFOBackend(Font()) for identifier in (1, 2)}
    calls = []

    class Host:
        def __init__(self):
            calls.append("world")

        def font_ids(self):
            return [1, 2]

        def current_font_id(self):
            calls.append("current")
            return active

        def backend(self, identifier, *, owned):
            assert owned is False
            return backends[identifier]

    result = object()

    def show(font):
        calls.append("show")
        assert font is None if active is None else isinstance(font, RFont) and font._backend is backends[active]
        return result

    monkeypatch.setattr(application, "NativeApplication", Host)
    monkeypatch.setattr(kerning_proof, "show", show)
    path = Path(__file__).resolve().parents[1] / "Scripts/Font Editors/Kerning Proof Workbench Demo.py"
    namespace = runpy.run_path(str(path), run_name=route)
    if route == "inspection":
        assert not calls
        assert namespace["main"]() is result
    assert calls == ["world", "current", "show"]
