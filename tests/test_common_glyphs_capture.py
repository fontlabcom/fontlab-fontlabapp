# this_file: tests/test_common_glyphs_capture.py
"""Capture all registered fonts without a current font or layer getters."""

from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
import fontlabapp.glyphs.common.capture as capture
from fontlabapp.glyphs.common.model import Production


def host():
    packages = [NS(id=17, fgId=117, isNull=False), NS(id=18, fgId=118, isNull=False)]
    fonts = [
        NS(
            id=p.fgId,
            info=NS(familyName=f"Family {p.id}"),
            glyphs=[NS(name="a", unicodes=[97, 65])],
        )
        for p in packages
    ]
    native = NS(
        flWorkspace=NS(instance=lambda: NS(packages=lambda: packages)),
        flPackage=lambda p: p,
        AllFonts=lambda: fonts,
    )
    return native, packages, fonts


def test_registered_double_read_preserves_family_order_and_ignores_current_font(
    monkeypatch,
):
    native, packages, fonts = host()
    monkeypatch.setattr(capture, "_native", lambda name: native)
    report = capture.capture(lambda name, **kw: Production(name, "database"))
    assert (
        report["families"] == ["Family 17", "Family 18"]
        and report["characters"] == "a "
    )
    assert fonts[0].glyphs[0].unicodes == [97, 65] and packages[0].id == 17
    for font in fonts:
        font.glyphs.append(NS(name="_nonexport", unicodes=[], export=False))
    report = capture.capture(lambda name, **kw: Production(name, "database"))
    assert "_nonexport" in report["glyph_names"] and report["characters"] == "a ", (
        "Nonexport/unencoded names stay in scope without invented strings"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "null",
        "zero",
        "duplicate",
        "unregistered",
        "missing",
        "repeat",
        "glyph",
        "code",
        "surrogate",
    ],
)
def test_invalid_registration_or_fact_refuses_instead_of_partial_report(
    monkeypatch, bad
):
    native, packages, fonts = host()
    if bad == "null":
        packages[0].isNull = True
    elif bad == "zero":
        packages[0].fgId = 0
    elif bad == "duplicate":
        packages.append(packages[0])
    elif bad == "unregistered":
        fonts[0].id = 999
    elif bad == "missing":
        fonts.pop()
    elif bad == "repeat":
        fonts.append(fonts[0])
    elif bad == "glyph":
        fonts[0].glyphs.append(fonts[0].glyphs[0])
    elif bad == "code":
        fonts[0].glyphs[0].unicodes = [0x110000]
    else:
        fonts[0].glyphs[0].unicodes = [0xDFFF]
    monkeypatch.setattr(capture, "_native", lambda name: native)
    with pytest.raises(ValueError):
        capture.capture(lambda name, **kw: Production(name, "database"))


def test_stale_after_metadata_no_fonts_deadline_and_cancel(monkeypatch):
    native, packages, fonts = host()
    monkeypatch.setattr(capture, "_native", lambda name: native)

    def metadata(name, **kw):
        fonts[0].info.familyName = "changed"
        return Production(name, "database")

    with pytest.raises(ValueError, match="changed"):
        capture.capture(metadata)
    native.AllFonts = lambda: []
    packages.clear()
    with pytest.raises(ValueError, match="Insufficient"):
        capture.capture(metadata)
    with pytest.raises(TimeoutError):
        capture.capture(metadata, deadline=0, clock=lambda: 0)
    with pytest.raises(InterruptedError):
        capture.capture(metadata, cancelled=lambda: True)


def test_native_read_overrun_and_non_gui_thread_are_refused(monkeypatch):
    native, packages, fonts = host()
    now = NS(value=0)

    def slow():
        now.value = 5
        return fonts

    native.AllFonts = slow
    monkeypatch.setattr(capture, "_native", lambda name: native)
    with pytest.raises(TimeoutError):
        capture.capture(Mock(), deadline=3, clock=lambda: now.value)
    monkeypatch.setattr(capture, "current_thread", lambda: object())
    with pytest.raises(ValueError, match="GUI"):
        capture.read(lambda: None)
