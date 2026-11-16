# this_file: tests/test_image_view.py
"""Generic QLabel presentation: point sizes, device pixels and renderer scale."""

from types import SimpleNamespace as NS

import fontlabapp.qt.images.view as api
import pytest


class Pixmap:
    def __init__(self, scale, events):
        self.scale, self.events = scale, events

    def scaled(self, *args):
        self.events.append(("scaled", args))
        return Pixmap(self.scale, self.events)

    def setDevicePixelRatio(self, ratio):
        self.events.append(("dpr", ratio))


class Label:
    def __init__(self, ratio=1):
        self.ratio, self.events = ratio, []

    def devicePixelRatioF(self):
        self.events.append(("ratio",))
        return self.ratio

    def setPixmap(self, pixmap):
        self.events.append(("pixmap", pixmap))

    def clear(self):
        self.events.append(("clear",))


@pytest.mark.parametrize("ratio", [1, 1.5, 2])
@pytest.mark.parametrize(
    "mode,size,expected",
    [
        ("down", (8, 8), 0.5),
        ("down", (64, 40), 1),
        ("fit", (64, 40), 4),
        ("none", (64, 40), 1),
        ("fit", (0, 0), 0),
        ("down", (0, 0), 0),
    ],
)
def test_present_preserves_point_fit_and_requests_exact_device_pixel_scale(
    ratio, mode, size, expected
):
    label = Label(ratio)
    renders = []

    def render(scale):
        renders.append(scale)
        return Pixmap(scale, label.events)

    api.present(NS(), label, render, size=size, natural=(16, 8), mode=mode)
    assert renders == [expected * ratio]
    assert label.events[-2] == ("dpr", ratio) and label.events[-1][0] == "pixmap"


@pytest.mark.parametrize("natural", [(0, 8), (16, 0), (0, 0)])
def test_zero_natural_dimensions_preserve_unscaled_fallback(natural):
    label = Label()
    seen = []
    api.present(
        NS(),
        label,
        lambda scale: seen.append(scale) or Pixmap(scale, label.events),
        size=(40, 40),
        natural=natural,
        mode="fit",
    )
    assert seen == [1]


@pytest.mark.parametrize("ratio", [1, 1.5, 2])
def test_stretch_renders_at_display_ratio_then_scales_with_alpha_friendly_qt_flags(
    ratio,
):
    label = Label(ratio)
    seen = []
    qt = NS(QtCore=NS(Qt=NS(IgnoreAspectRatio=1, SmoothTransformation=2)))
    api.present(
        qt,
        label,
        lambda scale: seen.append(scale) or Pixmap(scale, label.events),
        size=(13, 7),
        natural=(16, 8),
        mode="stretch",
    )
    assert seen == [ratio]
    assert ("scaled", (round(13 * ratio), round(7 * ratio), 1, 2)) in label.events
    assert label.events[-2] == ("dpr", ratio)


def test_missing_image_clears_without_reading_ratio_or_other_arguments():
    label = Label()
    api.present(None, label, mode="invalid")
    assert label.events == [("clear",)]


def test_invalid_mode_refuses_before_renderer_or_widget_update():
    label = Label()
    with pytest.raises(ValueError, match="mode"):
        api.present(
            None, label, lambda scale: pytest.fail("must not render"), mode="invalid"
        )
    assert label.events == []


@pytest.mark.parametrize("failure", ["ratio", "render", "scaled", "dpr", "pixmap"])
def test_present_propagates_failure_without_replacing_the_displayed_pixmap(failure):
    class BrokenPixmap(Pixmap):
        def scaled(self, *args):
            if failure == "scaled":
                raise RuntimeError(failure)
            return self

        def setDevicePixelRatio(self, ratio):
            if failure == "dpr":
                raise RuntimeError(failure)

    class BrokenLabel(Label):
        def devicePixelRatioF(self):
            if failure == "ratio":
                raise RuntimeError(failure)
            return 2

        def setPixmap(self, pixmap):
            if failure == "pixmap":
                raise RuntimeError(failure)
            super().setPixmap(pixmap)

    label = BrokenLabel()

    def render(scale):
        if failure == "render":
            raise RuntimeError(failure)
        return BrokenPixmap(scale, label.events)

    qt = NS(QtCore=NS(Qt=NS(IgnoreAspectRatio=1, SmoothTransformation=2)))
    with pytest.raises(RuntimeError, match=failure):
        api.present(qt, label, render, size=(16, 8), natural=(8, 4), mode="stretch")
    assert not any(event[0] == "pixmap" for event in label.events)


def test_import_is_host_free_without_qt_or_bridge_dependencies():
    import subprocess
    import sys
    from pathlib import Path

    script = """
import importlib.abc,sys,typing,collections.abc
class StdlibOnly(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] not in sys.stdlib_module_names | {'fontlabapp'}:
   raise AssertionError(fullname)
sys.meta_path.insert(0,StdlibOnly());sys.path.insert(0,sys.argv[1])
import fontlabapp.qt.images.view
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str((Path(__file__).resolve().parents[1] / "src"))],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
