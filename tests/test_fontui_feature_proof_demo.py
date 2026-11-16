# this_file: tests/test_fontui_feature_proof_demo.py
"""The actual lazy demo captures one real borrowed FontWorld font."""

import runpy
from pathlib import Path
import pytest
import test_fontui_feature_source as _source_fixtures

real_source = _source_fixtures.real_source


@pytest.mark.parametrize("active", [None, 1, 2])
@pytest.mark.parametrize("route", ["inspection", "__main__"])
def test_demo_when_dispatched_then_one_real_capture_and_exact_owner(
    monkeypatch, active, route
):
    from fontlab_fontport import application
    from fontlab_fontport.memory import UFOBackend
    from fontlab_fontport.live import RFont
    from ufoLib2 import Font
    from fontlabapp.fontui import feature_proof

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
        assert (
            font is None
            if active is None
            else isinstance(font, RFont) and font._backend is backends[active]
        )
        return result

    monkeypatch.setattr(application, "NativeApplication", Host)
    monkeypatch.setattr(feature_proof, "show", show)
    path = (
        Path(__file__).resolve().parents[1]
        / "Scripts/Font Editors/Feature Source and Proof Demo.py"
    )
    namespace = runpy.run_path(str(path), run_name=route)
    if route == "inspection":
        assert not calls
        assert namespace["main"]() is result
    assert calls == ["world", "current", "show"]


@pytest.mark.parametrize("active", [1, 2])
def test_demo_when_real_window_and_host_switch_then_exact_captured_editors(
    real_source, monkeypatch, active
):
    from fontlab_fontport import application
    from fontlabapp.fontui import feature_proof
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    actual_show = feature_proof.show

    calls, current = [], [active]

    class Host:
        def font_ids(self):
            return [1, 2]

        def current_font_id(self):
            calls.append(current[0])
            return current[0]

        def backend(self, identifier, *, owned):
            assert not owned
            return real_source.backends[identifier - 1]

    monkeypatch.setattr(application, "NativeApplication", Host)
    monkeypatch.setattr(feature_proof, "show", lambda font: actual_show(font, parent))
    path = (
        Path(__file__).resolve().parents[1]
        / "Scripts/Font Editors/Feature Source and Proof Demo.py"
    )
    namespace = runpy.run_path(str(path), run_name="inspection")
    c = namespace["main"]()
    real_source.owners.append(c)
    c._test_parent = parent
    current[0] = 3 - active
    assert calls == [active]
    assert c.editor.font is c.proof.font is c.font
    assert c.font._backend is real_source.backends[active - 1]
    assert c in feature_proof._HANDLES
