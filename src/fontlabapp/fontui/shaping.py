# this_file: src/fontlabapp/fontui/shaping.py
# SPDX-License-Identifier: Apache-2.0
"""Qt-free text shaping for the TMetrics and TGlyph windows.

``shape`` turns a duck-typed font (glyph widths, unicodes, feature text,
kerning and groups) plus a text string into positioned glyphs.  With the
optional ``uharfbuzz`` extra the font is compiled to a minimal in-memory
binary (empty outlines, real metrics, cmap, GSUB/GPOS from the feature
text and from the kerning data) and shaped by HarfBuzz.  Without it the
Fontport glyph-run layout is used instead and the result says it was
``shaped=False``.
"""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from ._fontport import require_fontport

__all__ = ["GlyphRunResult", "PlacedGlyph", "clear_cache", "shape", "shape_names"]

FALLBACK_NOTE = "unshaped: uharfbuzz not available"
CACHE_SIZE = 16
# Every glyph also gets a cmap entry here so "/name" runs can be fed to
# HarfBuzz as codepoints without depending on the glyph's real unicodes.
PUA_BASE = 0xF0000
KERN_GROUP_PREFIXES = ("public.kern1.", "public.kern2.")
_COMMENT = re.compile(r"#[^\n]*")
_HAS_KERN_FEATURE = re.compile(r"\bfeature\s+kern\b")
_NOT_IDENT = re.compile(r"[^A-Za-z0-9_.]")


@dataclass(frozen=True)
class PlacedGlyph:
    """One glyph in a run; ``x``/``y`` are the pen position before offsets.

    ``mark`` is the GDEF verdict: True/False when the shaping font classifies
    its glyphs, None when it has no GDEF glyph classes (or no HarfBuzz).
    """

    name: str | None
    cluster: int
    x: float
    y: float
    advance: float
    x_offset: float = 0.0
    y_offset: float = 0.0
    mark: bool | None = None


@dataclass(frozen=True)
class GlyphRunResult:
    """Positioned glyphs in visual (left-to-right on screen) order."""

    glyphs: tuple[PlacedGlyph, ...]
    advance: float
    shaped: bool
    diagnostics: tuple[str, ...] = ()


_CACHE: OrderedDict[str, tuple[bytes, tuple[str, ...]]] = OrderedDict()


def clear_cache() -> None:
    """Forget every compiled font blob."""
    _CACHE.clear()


def _load_harfbuzz() -> Any | None:
    try:
        import fontTools.fontBuilder  # noqa: F401  (the compile step needs it too)
        import uharfbuzz
    except ImportError:
        return None
    return uharfbuzz


def _glyph_order(font: Any) -> list[str]:
    keys = list(font.keys())
    live = set(keys)
    wanted = list(getattr(font, "glyphOrder", None) or keys)
    order = [n for n in dict.fromkeys([*wanted, *keys]) if n in live and n != ".notdef"]
    return [".notdef", *order]


def _units_per_em(font: Any) -> int:
    return int(getattr(getattr(font, "info", None), "unitsPerEm", None) or 1000)


def _snapshot(font: Any) -> dict[str, Any]:
    """Everything that decides the compiled font, as plain comparable data."""
    order = _glyph_order(font)
    rows = _glyph_rows(font)
    if rows is None:
        live = set(font.keys())
        glyphs = [
            (n, tuple(font[n].unicodes), _width(font, n)) if n in live else (n, (), 0)
            for n in order
        ]
    else:
        glyphs = [(n, *rows.get(n, ((), 0))) for n in order]
    groups = {k: tuple(v) for k, v in font.groups.items()}
    return {
        "upm": _units_per_em(font),
        "glyphs": glyphs,
        "features": getattr(getattr(font, "features", None), "text", None) or "",
        "kerning": sorted((tuple(k), v) for k, v in font.kerning.items()),
        "groups": sorted(groups.items()),
    }


def _width(font: Any, name: str) -> int:
    return int(round(font[name].width))


def _glyph_rows(font: Any) -> dict[str, tuple[tuple[int, ...], int]] | None:
    """Unicodes and rounded width per glyph from one bulk read, when the font offers it.

    Fontport's ``glyph_summaries()`` reads the whole default layer in one native
    pass; asking ``font[name]`` per glyph instead loads every outline.
    """
    method = getattr(font, "glyph_summaries", None)
    if not callable(method):
        return None
    return {name: (tuple(unicodes), int(round(width))) for name, unicodes, width in method()}


def _fingerprint(snapshot: dict[str, Any]) -> str:
    return hashlib.sha1(repr(snapshot).encode("utf-8")).hexdigest()


_FEA_NAME = re.compile(r"[A-Za-z_.][A-Za-z0-9_.\-]{0,62}")


def _fea_names(snapshot: dict[str, Any]) -> set[str]:
    """Glyph names the feature language can spell (``1x`` cannot be)."""
    return {n for n, _, _ in snapshot["glyphs"] if _FEA_NAME.fullmatch(n)}


def _kern_fea(snapshot: dict[str, Any]) -> str:
    """Build a ``kern`` feature from UFO-style kerning.

    Order follows ufo2ft: glyph-glyph pairs, then ``enum pos`` exceptions
    (glyph against class), then class-class pairs.
    """
    names = _fea_names(snapshot)
    classes: dict[str, str] = {}
    lines: list[str] = []
    for group, members in snapshot["groups"]:
        live = [m for m in members if m in names]
        if group.startswith(KERN_GROUP_PREFIXES) and live:
            ident = f"@kern_{len(classes)}_" + _NOT_IDENT.sub("_", group)
            classes[group] = ident
            escaped = " ".join("\\" + m for m in live)
            lines.append(f"{ident} = [{escaped}];")

    def side(key: str) -> tuple[str, bool] | None:
        if key in classes:
            return classes[key], True
        return ("\\" + key, False) if key in names else None

    pairs = []
    for (left, right), value in snapshot["kerning"]:
        a, b = side(left), side(right)
        if a and b:
            rank = a[1] + b[1]
            prefix = "enum " if rank == 1 else ""
            pairs.append((rank, f"{prefix}pos {a[0]} {b[0]} {int(round(value))};"))
    if not pairs:
        return ""
    body = [text for _, text in sorted(pairs, key=lambda p: p[0])]
    return "\n".join([*lines, "feature kern {", *body, "} kern;"])


def _build_binary(snapshot: dict[str, Any], fea: str) -> bytes:
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    order = [name for name, _, _ in snapshot["glyphs"]]
    upm = snapshot["upm"]
    cmap: dict[int, str] = {}
    for name, unicodes, _ in snapshot["glyphs"]:
        cmap.update({u: name for u in unicodes if u not in cmap})
    for gid, name in enumerate(order):
        cmap.setdefault(PUA_BASE + gid, name)
    builder = FontBuilder(upm, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf({name: TTGlyphPen(None).glyph() for name in order})
    builder.setupHorizontalMetrics({name: (width, 0) for name, _, width in snapshot["glyphs"]})
    builder.setupHorizontalHeader(ascent=int(upm * 0.8), descent=-int(upm * 0.2))
    builder.setupNameTable({"familyName": "Shaping", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    if fea.strip():
        addOpenTypeFeaturesFromString(builder.font, fea)
    out = BytesIO()
    builder.font.save(out)
    return out.getvalue()


def _try_build(snapshot: dict[str, Any], fea: str) -> tuple[bytes | None, str]:
    try:
        return _build_binary(snapshot, fea), ""
    except Exception as error:  # feaLib raises many types for bad feature code
        return None, str(error) or type(error).__name__


def _compile(snapshot: dict[str, Any]) -> tuple[bytes, tuple[str, ...]]:
    user = snapshot["features"]
    notes: list[str] = []
    kern = ""
    if _HAS_KERN_FEATURE.search(_COMMENT.sub("", user)):
        if snapshot["kerning"]:
            notes.append("generated kerning skipped: the feature code defines kern")
    else:
        kern = _kern_fea(snapshot)
        bad = sorted({n for n, _, _ in snapshot["glyphs"]} - _fea_names(snapshot))
        if bad and snapshot["kerning"]:
            notes.append(f"kerning skipped for unspellable glyph names: {', '.join(bad)}")
    blob, error = _try_build(snapshot, f"{user}\n{kern}")
    if blob is not None:
        return blob, tuple(notes)
    if kern:
        blob, user_error = _try_build(snapshot, user)
        if blob is not None:
            return blob, (*notes, f"kerning not compiled: {error}")
        error = user_error
    notes.append(f"features not compiled: {error}")
    if kern:
        blob, kern_error = _try_build(snapshot, kern)
        if blob is not None:
            return blob, tuple(notes)
        notes.append(f"kerning not compiled: {kern_error}")
    return _build_binary(snapshot, ""), tuple(notes)


def _compiled(font: Any) -> tuple[bytes, tuple[str, ...], list[str]]:
    snapshot = _snapshot(font)
    key = _fingerprint(snapshot)
    if key in _CACHE:
        _CACHE.move_to_end(key)
    else:
        _CACHE[key] = _compile(snapshot)
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.popitem(last=False)
    blob, notes = _CACHE[key]
    return blob, notes, [name for name, _, _ in snapshot["glyphs"]]


def parse_features(spec: str) -> tuple[dict[str, bool | int], list[str]]:
    """Parse ``"liga,-kern,ss01,cv01=2"`` into a HarfBuzz feature mapping.

    Returns the mapping and a diagnostic for every token that was skipped.
    """
    result: dict[str, bool | int] = {}
    skipped: list[str] = []
    for token in re.split(r"[,\s]+", spec.strip()):
        if not token:
            continue
        tag, _, value = token.lstrip("+-").partition("=")
        if not tag:
            skipped.append(f"ignored feature {token!r}")
        elif not value:
            result[tag] = not token.startswith("-")
        elif value.isdigit():
            result[tag] = int(value)
        else:
            skipped.append(f"ignored feature {token!r}")
    return result, skipped


def _is_names_run(text: str) -> bool:
    tokens = text.split()
    return bool(tokens) and all(t.startswith("/") and len(t) > 1 for t in tokens)


def _shape_harfbuzz(
    hb: Any,
    font: Any,
    text: str,
    *,
    features: str,
    direction: str,
    script: str | None,
    language: str | None,
    kerning: bool,
    names_run: bool,
) -> GlyphRunResult:
    blob, notes, order = _compiled(font)
    diagnostics = list(notes)
    chars = [t[1:] for t in text.split()] if names_run else list(text)
    codepoints: list[int] = []
    for char in chars:
        if names_run and char not in order:
            diagnostics.append(f"unknown glyph name /{char}")
        elif names_run:
            codepoints.append(PUA_BASE + order.index(char))
        else:
            codepoints.append(ord(char))
    if not codepoints:
        # Only unknown /names: HarfBuzz returns no glyph lists for an empty buffer.
        return GlyphRunResult((), 0.0, True, tuple(diagnostics))
    buf = hb.Buffer()
    buf.add_codepoints(codepoints)
    buf.direction = direction
    if script:
        buf.script = script
    if language:
        buf.language = language
    buf.guess_segment_properties()
    wanted, skipped = parse_features(features)
    diagnostics += skipped
    if not kerning:
        wanted["kern"] = False
    face = hb.Face(hb.Blob(blob))
    hb.shape(hb.Font(face), buf, wanted)
    placed, advance = _place(buf, order, _mark_classes(hb, face))
    diagnostics += _missing(buf, chars, names_run)
    return GlyphRunResult(tuple(placed), advance, True, tuple(diagnostics))


def _mark_classes(hb: Any, face: Any) -> Callable[[int], bool] | None:
    """GDEF mark test for glyph ids of ``face``; None when it has no glyph classes."""
    try:
        if not face.has_layout_glyph_classes:
            return None
        mark = hb.OTLayoutGlyphClass.MARK
        glyph_class = face.get_layout_glyph_class
    except AttributeError:  # an older uharfbuzz without the GDEF API
        return None
    return lambda gid: glyph_class(gid) == mark


def _place(
    buf: Any, order: list[str], is_mark: Callable[[int], bool] | None = None
) -> tuple[list[PlacedGlyph], float]:
    placed: list[PlacedGlyph] = []
    pen_x = pen_y = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True):
        mark = None if is_mark is None else bool(is_mark(info.codepoint))
        placed.append(
            PlacedGlyph(order[info.codepoint], info.cluster, pen_x, pen_y,
                        pos.x_advance, pos.x_offset, pos.y_offset, mark)
        )
        pen_x += pos.x_advance
        pen_y += pos.y_advance
    return placed, pen_x


def _missing(buf: Any, chars: list[str], names_run: bool) -> list[str]:
    if names_run:
        return []
    return [
        f"Missing glyph for {chars[info.cluster]!r}"
        for info in buf.glyph_infos
        if info.codepoint == 0 and info.cluster < len(chars)
    ]


def _shape_fallback(font: Any, text: str, *, direction: str, kerning: bool, names_run: bool) -> GlyphRunResult:
    with require_fontport(__name__):
        from fontlab_fontport.glyphrun import layout_names, layout_text
    layout = layout_names if names_run else layout_text
    run = layout(font, text, kerning=kerning, direction=direction)
    glyphs = tuple(PlacedGlyph(g.name, g.index, g.x, 0.0, g.advance) for g in run.glyphs)
    return GlyphRunResult(glyphs, run.advance, False, (FALLBACK_NOTE, *run.diagnostics))


def shape(
    font: Any,
    text: str,
    *,
    features: str = "",
    direction: str = "ltr",
    script: str | None = None,
    language: str | None = None,
    kerning: bool = True,
) -> GlyphRunResult:
    """Shape ``text`` with ``font``.

    ``features`` is a HarfBuzz feature list such as ``"liga,-kern,ss01"``.
    Text made only of whitespace-separated ``/glyphname`` tokens is treated
    as glyph names rather than characters.  Raises ``ValueError`` for an
    unknown direction and ``TypeError`` for non-string text.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if direction not in ("ltr", "rtl"):
        raise ValueError("direction must be 'ltr' or 'rtl'")
    names_run = _is_names_run(text)
    hb = _load_harfbuzz()
    if hb is None:
        return _shape_fallback(font, text, direction=direction, kerning=kerning, names_run=names_run)
    return _shape_harfbuzz(
        hb, font, text, features=features, direction=direction, script=script,
        language=language, kerning=kerning, names_run=names_run,
    )


def shape_names(font: Any, names: list[str], **options: Any) -> GlyphRunResult:
    """Shape a run given as glyph names (no leading slash)."""
    return shape(font, " ".join(f"/{name}" for name in names), **options)
