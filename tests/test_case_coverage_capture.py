# this_file: tests/test_case_coverage_capture.py
from types import SimpleNamespace as NS
import pytest
import fontlabapp.glyphs.case_coverage.capture as capture
from fontlabapp.glyphs.case_coverage.model import Options


def carrier(identity, code):
    glyph = NS(name="same", unicodes=[code])
    return NS(
        identity=identity,
        fg_id=100 + identity,
        label=f"Font {identity}",
        package=NS(master="Regular", packageLib={}),
        font=NS(glyphs=[glyph], info=NS(familyName=f"Family {identity}")),
    )


def test_all_fonts_keep_exact_id_mapping_and_current_scope(monkeypatch):
    fonts = (carrier(1, 65), carrier(2, 66))
    monkeypatch.setattr(capture, "fonts", lambda deadline, *, checkpoint=None: fonts)
    monkeypatch.setattr(capture, "current_package", lambda: NS(id=2))
    meta = lambda name, codes, *, checkpoint=None: ("Letter", None)
    snap = capture.read(
        Options(), meta, lambda text, *, checkpoint=None: text.lower(), clock=lambda: 0
    )
    assert [(f.identity, f.report["proof"]) for f in snap.fonts] == [
        (1, ["same"]),
        (2, ["same"]),
    ]
    assert snap.current_id == 2 and not snap.all_clear
    snap = capture.read(
        Options(allFonts=False),
        meta,
        lambda text, *, checkpoint=None: text,
        clock=lambda: 0,
    )
    assert [f.identity for f in snap.fonts] == [2]


def test_no_font_stale_master_bad_policy_timeout_and_cancel(monkeypatch):
    monkeypatch.setattr(capture, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Open a font"):
        capture.read(Options(), None, None)
    font = carrier(1, 65)
    monkeypatch.setattr(capture, "current_package", lambda: NS(id=1))
    monkeypatch.setattr(capture, "fonts", lambda deadline, *, checkpoint=None: (font,))
    with pytest.raises(InterruptedError):
        capture.read(Options(), None, None, cancelled=lambda: True)
    font.package.packageLib = {"public.skipExportGlyphs": "same"}
    with pytest.raises(ValueError, match="list"):
        capture.read(Options(), None, None, clock=lambda: 0)
    font.package.packageLib = {}

    def changed(name, codes, *, checkpoint=None):
        font.package.master = "Bold"
        return "Letter", None

    with pytest.raises(ValueError, match="master"):
        capture.read(
            Options(), changed, lambda t, *, checkpoint=None: t, clock=lambda: 0
        )


def test_all_clear_empty_unknown_metadata_and_export_policy(monkeypatch):
    font = carrier(1, 65)
    font.font.glyphs = []
    monkeypatch.setattr(capture, "fonts", lambda deadline, *, checkpoint=None: (font,))
    monkeypatch.setattr(capture, "current_package", lambda: NS(id=1))
    snap = capture.read(
        Options(),
        lambda *a, **kw: None,
        lambda t, *, checkpoint=None: t,
        clock=lambda: 0,
    )
    assert snap.all_clear
    font.font.glyphs = [NS(name="same", unicodes=[65, 66])]
    font.package.packageLib = {"public.skipExportGlyphs": ["same"]}
    snap = capture.read(
        Options(),
        lambda *a, **kw: (None, None),
        lambda t, *, checkpoint=None: None,
        clock=lambda: 0,
    )
    assert not snap.all_clear and snap.fonts[0].report["unresolved"]
    assert len(snap.fonts[0].report["rows"]) == 2
