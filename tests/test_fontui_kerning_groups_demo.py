# this_file: tests/test_fontui_kerning_groups_demo.py
"""The actual lazy demo captures one real borrowed FontWorld font."""

import runpy
from pathlib import Path
import pytest
import test_fontui_kerning_groups as _group_fixtures

composition_env = _group_fixtures.composition_env
real_fonts = _group_fixtures.real_fonts


@pytest.mark.parametrize("active", [None, 1, 2])
@pytest.mark.parametrize("route", ["inspection", "__main__"])
def test_demo_when_dispatched_then_one_real_capture_and_exact_owner(
    monkeypatch, active, route
):
    from fontlab_fontport import application
    from fontlab_fontport.memory import UFOBackend
    from fontlab_fontport.live import RFont
    from ufoLib2 import Font
    from fontlabapp.fontui import kerning_groups

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
    monkeypatch.setattr(kerning_groups, "show", show)
    path = (
        Path(__file__).resolve().parents[1]
        / "Scripts/Font Editors/Kerning Group Explorer Demo.py"
    )
    namespace = runpy.run_path(str(path), run_name=route)
    if route == "inspection":
        assert not calls
        assert namespace["main"]() is result
    assert calls == ["world", "current", "show"]


@pytest.mark.parametrize("active", [1, 2])
def test_demo_when_real_window_and_host_switch_then_exact_captured_editors(
    real_fonts, monkeypatch, active
):
    from fontlab_fontport import application
    from fontlabapp.fontui import kerning_groups
    actual_show = kerning_groups.show

    calls, current = [], [active]

    class Host:
        def font_ids(self):
            return [1, 2]

        def current_font_id(self):
            calls.append(current[0])
            return current[0]

        def backend(self, identifier, *, owned):
            assert not owned
            return real_fonts.backends[identifier - 1]

    monkeypatch.setattr(application, "NativeApplication", Host)
    monkeypatch.setattr(kerning_groups, "show", lambda font: actual_show(font, real_fonts.env.parent))
    path = (
        Path(__file__).resolve().parents[1]
        / "Scripts/Font Editors/Kerning Group Explorer Demo.py"
    )
    namespace = runpy.run_path(str(path), run_name="inspection")
    c = namespace["main"]()
    real_fonts.owners.append(c)
    current[0] = 3 - active
    assert calls == [active]
    assert c.groups.font is c.kerning.font is c.font
    assert c.font._backend is real_fonts.backends[active - 1]
    assert c in kerning_groups._HANDLES
