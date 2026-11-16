# this_file: tests/test_fontui_designspace_sources.py
"""Real on-disk designspace source reports; no Qt or native runtime."""
from pathlib import Path

import pytest
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.ufoLib.errors import UFOLibError
from ufoLib2 import Font

from fontlabapp.fontui.designspace_sources import compare, refresh, render


def fixture(tmp_path: Path, *, layer=False):
    doc = DesignSpaceDocument()
    doc.addAxisDescriptor(name="Weight", tag="wght", minimum=100, default=100,
                          maximum=900, map=[(100, 0), (900, 1)])
    for index in range(2):
        font = Font()
        for field, value in dict(unitsPerEm=1000, ascender=800 + index,
                                descender=-200, xHeight=500, capHeight=700,
                                italicAngle=-index).items():
            setattr(font.info, field, value)
        target = font.layers.newLayer("alternate") if layer else font.layers.defaultLayer
        glyph = target.newGlyph("A")
        glyph.width = 600 + index * 0.5
        pen = glyph.getPen()
        pen.moveTo((0, 0))
        pen.lineTo((100, 0))
        pen.lineTo((50, 100))
        pen.closePath()
        target.newGlyph("left" if index == 0 else "right")
        font.save(tmp_path / f"{index}.ufo")
        doc.addSourceDescriptor(name=f"source {index}", filename=f"{index}.ufo",
                                layerName="alternate" if layer else None,
                                designLocation={"Weight": index})
    path = tmp_path / "test.designspace"
    doc.write(path)
    return path


def test_compare_when_real_sources_then_metrics_locations_and_missing(tmp_path):
    path = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = compare(path)
    assert result.axes[0].mapping == ((100, 0), (900, 1))
    assert result.sources[1].design_location == (("Weight", 1),)
    assert result.sources[1].user_location == (("Weight", 900),)
    assert result.sources[0].metrics == (1000, 800, -200, 500, 700, 0)
    assert result.sources[1].missing == ("left",)
    assert result.sources[1].extra == ("right",)
    a, left, right = result.glyphs
    assert a.name == "A" and a.advances == (600, 600.5) and a.compatible is True
    assert left.advances == (0, None) and left.compatible is None
    assert right.advances == (None, 0) and right.compatible is None
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    output = []
    assert refresh(path, output.append) == result
    assert output == [render(result)]
    assert "UPM" in output[0] and "not comparable" in output[0]


def test_compare_when_named_layer_and_topology_diff_then_reports(tmp_path):
    path = fixture(tmp_path, layer=True)
    with Font.open(tmp_path / "1.ufo") as font:
        glyph = font.layers["alternate"]["A"]
        glyph.clearContours()
        glyph.appendAnchor(dict(name="top", x=0, y=800))
        font.save()
    result = compare(path)
    assert result.sources[1].layer == "alternate"
    assert result.glyphs[0].compatible is False
    assert {d.kind for d in result.glyphs[0].differences} == {"path counts", "anchors"}
    assert "not compatible" in render(result)


@pytest.mark.parametrize("problem", ["source", "layer", "empty", "discrete"])
def test_compare_when_unavailable_or_unsupported_then_fails_without_view_update(tmp_path, problem):
    path = fixture(tmp_path)
    doc = DesignSpaceDocument.fromfile(path)
    if problem == "source":
        doc.sources[0].path = str(tmp_path / "absent.ufo")
    elif problem == "layer":
        doc.sources[0].layerName = "absent"
    elif problem == "empty":
        doc.sources = []
    else:
        from fontTools.designspaceLib import DiscreteAxisDescriptor
        doc.axes = [DiscreteAxisDescriptor(name="Weight", tag="wght", values=[0, 1], default=0)]
    doc.write(path)
    output = []
    with pytest.raises((ValueError, UFOLibError, NotImplementedError)):
        refresh(path, output.append)
    assert output == []


def test_compare_when_single_source_and_unset_metrics_then_not_comparable(tmp_path):
    path = fixture(tmp_path)
    doc = DesignSpaceDocument.fromfile(path)
    doc.sources = doc.sources[:1]
    doc.sources[0].name = None
    doc.write(path)
    with Font.open(tmp_path / "0.ufo") as font:
        font.info.xHeight = None
        font.save()
    result = compare(path)
    assert result.sources[0].metrics[3] is None
    assert all(g.compatible is None for g in result.glyphs)
    assert "unset" in render(result)


def test_compare_when_nonfinite_width_then_refuses(tmp_path):
    path = fixture(tmp_path)
    glif = next((tmp_path / "1.ufo" / "glyphs").glob("A_*.glif"))
    glif.write_text(glif.read_text().replace('width="600.5"', 'width="nan"'))
    with pytest.raises(ValueError, match="finite"):
        compare(path)


def test_compare_when_source_has_no_path_then_refuses(tmp_path):
    path = fixture(tmp_path)
    doc = DesignSpaceDocument.fromfile(path)
    doc.sources[0].path = None
    doc.sources[0].filename = None
    doc.write(path)
    with pytest.raises(ValueError, match="no file path"):
        compare(path)


def test_compare_when_three_sources_then_checks_every_source(tmp_path):
    path = fixture(tmp_path)
    doc = DesignSpaceDocument.fromfile(path)
    doc.addSourceDescriptor(name="third", filename="0.ufo", designLocation={"Weight": 0.5})
    doc.write(path)
    result = compare(path)
    assert result.glyphs[0].advances == (600, 600.5, 600)
    assert result.glyphs[0].compatible is True
    assert result.sources[2].missing == result.sources[2].extra == ()
    assert "Weight (wght)" in render(result)
    assert "design location" in render(result)


def test_compare_when_missing_document_then_raises(tmp_path):
    with pytest.raises(OSError):
        compare(tmp_path / "missing.designspace")


def test_compare_when_bad_metric_then_raises(tmp_path):
    path = fixture(tmp_path)
    info = tmp_path / "1.ufo" / "fontinfo.plist"
    info.write_text(info.read_text().replace("<integer>801</integer>", "<real>nan</real>"))
    with pytest.raises((ValueError, UFOLibError)):
        compare(path)


def test_compare_when_anisotropic_location_then_refuses(tmp_path):
    path = fixture(tmp_path)
    doc = DesignSpaceDocument.fromfile(path)
    doc.sources[0].designLocation = {"Weight": (0, 1)}
    doc.write(path)
    with pytest.raises(ValueError, match="location"):
        compare(path)


def test_demo_when_called_or_run_as_script_then_prints_real_report(tmp_path, capsys, monkeypatch):
    import runpy
    import sys

    path = fixture(tmp_path)
    demo = Path(__file__).resolve().parents[1] / "Scripts/Font Editors/Designspace Source Report Demo.py"
    namespace = runpy.run_path(str(demo))
    assert capsys.readouterr().out == ""
    namespace["main"](path)
    expected = render(compare(path)) + "\n"
    assert capsys.readouterr().out == expected
    monkeypatch.setattr(sys, "argv", [str(demo), str(path)])
    runpy.run_path(str(demo), run_name="__main__")
    assert capsys.readouterr().out == expected


@pytest.mark.parametrize('phase', ['document', 'source', 'glyph', 'render', 'publish'])
def test_refresh_when_checkpoint_cancels_then_no_partial_report(tmp_path, phase):
    import inspect
    from fontlabapp.fontui import designspace_sources as module

    path = fixture(tmp_path)
    output = []
    def check():
        frame = inspect.currentframe().f_back
        function = frame.f_code.co_name
        if ((phase == 'document' and function == 'compare')
                or (phase == 'source' and function == '_source')
                or (phase == 'glyph' and function == '_glyph')
                or (phase == 'render' and function == 'render')
                or (phase == 'publish' and function == 'refresh')):
            raise InterruptedError(phase)
    with pytest.raises(InterruptedError, match=phase):
        module.refresh(path, output.append, check=check)
    assert output == []
    assert compare(path).glyphs[0].advances == (600, 600.5)
