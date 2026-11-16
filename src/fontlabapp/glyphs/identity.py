# this_file: src/fontlabapp/glyphs/identity.py
"""Read a glyph's name, Unicodes, mark colour and export flag without writing.

Evidence classes follow Issue 209 ``native-data-map.md``: (a-stub) the name is
in the generated Echopy stub, (b) earlier App/Glyport code ran it natively,
(c) inference. Used by ``fontlabapp.plugins.snapshot.capture``.
"""

import colorsys
from dataclasses import dataclass
from typing import Any

__all__ = ["GREY", "LIGHTNESS", "Identity", "mark_rgb", "read"]

#: HSL lightness for mark swatches (c): FontLab's markLightness preference is
#: not exposed to Python, so swatches differ slightly from FontLab's flags.
LIGHTNESS = 0.65
#: Colour for grey marks (raw values above 1000).
GREY = (128, 128, 128)


@dataclass(frozen=True)
class Identity:
    """Cheap per-glyph facts every reporter receives."""

    name: str
    unicodes: tuple[int, ...]
    mark: int
    mark_rgb: tuple[int, int, int] | None
    exported: bool


def mark_rgb(mark: int) -> tuple[int, int, int] | None:
    """Map a raw ``glyph.mark`` to RGB: 0 none, >1000 grey, else hue = mark - 1.

    Encoding from a-src ``flcolors.cpp`` ``_mark2color``; channels round to
    the nearest integer.
    """
    if mark == 0:
        return None
    if mark > 1000:
        return GREY
    rgb = colorsys.hls_to_rgb((mark - 1) / 360, LIGHTNESS, 1.0)
    return tuple(round(channel * 255) for channel in rgb)  # type: ignore[return-value]


def _skip_list(package: Any) -> set[str]:
    """Read ``public.skipExportGlyphs`` (a-stub ``packageLib``; b smallcaps)."""
    skip = package.packageLib.get("public.skipExportGlyphs", ())
    if not isinstance(skip, (list, tuple)) or not all(
        isinstance(name, str) for name in skip
    ):
        raise ValueError("public.skipExportGlyphs must be a list of glyph names.")
    return set(skip)


def read(package: Any, glyph: Any) -> Identity:
    """Read one glyph's identity; raise on any missing native attribute.

    - Unicodes come from ``package.fgPackage[name].unicodes`` (a-stub, b
      Glyport ``glyph_info``); ``flGlyph`` has no Unicode binding and
      ``glyph.fgGlyph`` can clear ``lib.note`` (fl#8525). Lookup cost is
      unverified natively.
    - ``glyph.mark`` (a-stub, b) may run ``completeImport()`` on lazy glyphs
      (a-src ``flglyph.cpp``).
    - Export is off for a ``noexport`` tag (a-stub ``tags``) or a
      ``public.skipExportGlyphs`` entry.
    """
    name = str(glyph.name)
    unicodes = tuple(int(code) for code in package.fgPackage[name].unicodes)
    mark = int(glyph.mark)
    tags = {str(tag) for tag in glyph.tags}
    exported = "noexport" not in tags and name not in _skip_list(package)
    return Identity(name, unicodes, mark, mark_rgb(mark), exported)
