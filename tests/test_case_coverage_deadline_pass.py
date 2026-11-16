# this_file: tests/test_case_coverage_deadline_pass.py
from types import SimpleNamespace as NS
import pytest
import fontlabapp.anchors.crossfont.capture as carriers
from fontlabapp.glyphs.case_coverage.model import GlyphFact, analyze


def test_registered_carrier_checkpoint_runs_inside_glyph_names_not_just_per_font(
    monkeypatch,
):
    names = []

    def glyphs():
        for i in range(10000):
            names.append(i)
            yield NS(name=f"g{i}")

    package = NS(id=1, fgId=10, masters=("Regular", "#hidden"))
    font = NS(id=10, path="owned.vfj", glyphs=glyphs())
    native = NS(
        flWorkspace=NS(instance=lambda: NS(packages=lambda: [package])),
        flPackage=lambda p: p,
        AllFonts=lambda: [font],
    )
    monkeypatch.setattr(carriers, "_native", lambda name: native)
    monkeypatch.setattr(carriers, "require_main_thread", lambda: None)
    monkeypatch.setattr(carriers, "check", lambda deadline: None)
    ticks = []

    def cancel():
        ticks.append(1)
        if len(names) == 3:
            raise InterruptedError("cancel inside glyph names")

    with pytest.raises(InterruptedError, match="inside glyph"):
        carriers.fonts(10, checkpoint=cancel)
    assert names == [0, 1, 2] and len(ticks) > 3


def test_unicode_fact_validation_and_alias_walk_check_within_their_scopes():
    calls = []

    def cancel():
        calls.append(1)
        if len(calls) == 4:
            raise InterruptedError("validation cancelled")

    with pytest.raises(InterruptedError, match="validation"):
        GlyphFact("many", tuple(range(100)), True, "Letter", validation_check=cancel)
    rows = [GlyphFact("A", (65,), True, "Letter")] + [
        GlyphFact(f"alias{i}", (97,), True, "Letter") for i in range(100)
    ]
    ticks = []

    def clock():
        ticks.append(1)
        return len(ticks)

    with pytest.raises(TimeoutError):
        analyze(rows, {"a": "a"}, deadline=250, clock=clock)
    assert len(ticks) == 250
