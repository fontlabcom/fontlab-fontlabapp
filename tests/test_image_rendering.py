# this_file: tests/test_image_rendering.py
"""Injected Qt exercises image selection and painter ownership without a host."""

from types import SimpleNamespace

import pytest
from fontlabapp.qt.images.resources import raster_image, svg_image


def qt_images(sizes, *, null=False):
    seen = []

    class Image:
        Format_ARGB32_Premultiplied = 4

        def __init__(self, *args):
            self.size = args[0] if args else sizes[0]
            seen.append(("image", args))

        def isNull(self):
            return null

        def width(self):
            return self.size[0]

        def height(self):
            return self.size[1]

        def scaled(self, size, aspect, transform):
            seen.append(("scaled", size, aspect, transform))
            self.size = size
            return self

        def fill(self, value):
            seen.append(("fill", value))

    class Reader:
        def __init__(self, path):
            self.index = 0
            seen.append(("reader", path))

        def imageCount(self):
            return len(sizes)

        def jumpToImage(self, index):
            self.index = index
            seen.append(("frame", index))

        def size(self):
            w, h = sizes[self.index]
            return SimpleNamespace(width=lambda: w, height=lambda: h)

        def read(self):
            return Image(sizes[self.index])

        def errorString(self):
            return "unreadable"

    class Painter:
        def __init__(self, image):
            seen.append(("painter", image))

        def end(self):
            seen.append(("end",))

    qt = SimpleNamespace(
        QtGui=SimpleNamespace(QImageReader=Reader, QImage=Image, QPainter=Painter),
        QtCore=SimpleNamespace(
            QSize=lambda w, h: (w, h),
            Qt=SimpleNamespace(IgnoreAspectRatio=0, SmoothTransformation=1),
        ),
    )
    return qt, seen


@pytest.mark.parametrize(
    "sizes,target,chosen",
    [
        ([(8, 8), (32, 32), (16, 16)], (12, 12), 2),
        ([(8, 8), (32, 32), (16, 16)], (64, 64), 1),
        ([(12, 12)], (12, 12), 0),
    ],
)
def test_raster_when_frames_available_then_smallest_cover_or_largest(
    sizes, target, chosen
):
    qt, seen = qt_images(sizes)
    image = raster_image(qt, "icon.tiff", *target)
    assert ("frame", chosen) == [item for item in seen if item[0] == "frame"][-1]
    assert (image.width(), image.height()) == target
    assert any(item[0] == "scaled" for item in seen) is (sizes[chosen] != target)


def test_raster_when_reader_returns_null_then_original_error():
    qt, _ = qt_images([(1, 1)], null=True)
    with pytest.raises(OSError, match="cannot read image icon.png: unreadable"):
        raster_image(qt, "icon.png", 1, 1)


@pytest.mark.parametrize("fail", [False, True])
def test_svg_when_painting_then_transparent_target_and_painter_always_ended(fail):
    qt, seen = qt_images([(1, 1)])

    def renderer():
        def render(painter):
            seen.append(("render", painter))
            if fail:
                raise ValueError("paint failure")

        return SimpleNamespace(render=render)

    if fail:
        with pytest.raises(ValueError, match="paint failure"):
            svg_image(qt, renderer, 30, 40)
    else:
        assert svg_image(qt, renderer, 30, 40).size == (30, 40)
    assert ("fill", 0) in seen
    assert seen[-1] == ("end",), "the owned painter must end even when rendering fails"
