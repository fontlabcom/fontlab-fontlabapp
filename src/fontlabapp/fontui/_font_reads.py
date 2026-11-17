# this_file: src/fontlabapp/fontui/_font_reads.py
# SPDX-License-Identifier: Apache-2.0
"""A font view that keeps whole-font reads until the font may have changed.

Why: a TMetrics keystroke reshapes the text, and shaping, the kerning readout
and the change fingerprint each read the whole font: glyph names, every
glyph's Unicodes, all kerning pairs, groups and features. On a live
3000-glyph FontLab font one kerning read alone costs over a second, so typing
lagged by seconds. Typing and view settings never change the font, so those
reads can be reused until a font change, an Undo, or a write of our own.

What: ``FontReads(font)`` answers ``keys()``, ``in``, ``kerning``, ``groups``,
``features.text``, ``info``, ``glyphOrder``, ``defaultLayerName`` and
``glyph_summaries()`` and ``font[name]`` from memory after the first read.
On an older Fontport every ``font[name]`` re-lists the whole layer to check
that the name exists, so a per-glyph loop costs a scan per glyph; remembering
each glyph object keeps later keystrokes free of those scans. Every other
attribute passes straight through to ``font``. ``reset()`` forgets
everything and refreshes a font that has ``refresh()``. Write through
``view.font``; the one exception is ``view.info``, whose attribute writes go
to the font's info and drop that cached value.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Any

__all__ = ["FontReads"]

LOG = logging.getLogger(__name__)


class _Features:
    __slots__ = ("text",)

    def __init__(self, text: Any) -> None:
        self.text = text


class _Info:
    """Attribute reads of ``font.info``, each read once."""

    __slots__ = ("_info", "_values")

    def __init__(self, info: Any) -> None:
        self._info = info
        self._values: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        values = self._values
        if name not in values:
            values[name] = getattr(self._info, name)
        return values[name]

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _Info.__slots__:
            object.__setattr__(self, name, value)
            return
        setattr(self._info, name, value)
        self._values.pop(name, None)


class FontReads:
    """Read-through view of ``font`` that remembers whole-font reads until ``reset()``."""

    def __init__(self, font: Any) -> None:
        self.font = font
        self._memo: dict[str, Any] = {}

    def reset(self) -> None:
        """Forget every remembered read; the next read asks the font again.

        A live Fontport font also keeps each glyph handle's width and outline
        as read when the handle was made, and FontLab edits do not reach it,
        so ``reset()`` calls the font's ``refresh()`` too when it has one.
        Without that, TMetrics kept showing the old width after a width
        change made in FontLab (issue 258). Fontport refuses ``refresh()``
        while a glyph has unfinished point edits; then the memo is still
        cleared and the cached handles are kept until the next reset.
        """
        self._memo.clear()
        refresh = getattr(self.font, "refresh", None)
        if not callable(refresh):
            return
        try:
            refresh()
        except NotImplementedError as error:
            # Fontport's UnsupportedCapability (a NotImplementedError); matched by
            # name because App code outside the Fontport editors must not import it.
            if type(error).__name__ != "UnsupportedCapability":
                raise
            LOG.debug("FontReads.reset: font refresh skipped: %s", error)

    def _read(self, key: str, read: Callable[[], Any]) -> Any:
        memo = self._memo
        if key not in memo:
            memo[key] = read()
        return memo[key]

    def keys(self) -> tuple[str, ...]:
        return self._read("keys", lambda: tuple(self.font.keys()))

    def __contains__(self, name: object) -> bool:
        return name in self._read("names", lambda: frozenset(self.keys()))

    def __getitem__(self, name: str) -> Any:
        """The font's glyph object, asked once per name; a missing name is asked again."""
        return self._read(f"glyph:{name}", lambda: self.font[name])

    def __iter__(self) -> Iterator[Any]:
        return (self[name] for name in self.keys())

    def __len__(self) -> int:
        return len(self.keys())

    @property
    def kerning(self) -> dict[Any, Any]:
        return self._read("kerning", lambda: dict(self.font.kerning.items()))

    @property
    def groups(self) -> dict[str, tuple[str, ...]]:
        return self._read("groups", lambda: {k: tuple(v) for k, v in self.font.groups.items()})

    @property
    def features(self) -> _Features:
        return self._read("features", lambda: _Features(self.font.features.text))

    @property
    def info(self) -> _Info:
        return self._read("info", lambda: _Info(self.font.info))

    def getLayer(self, name: str) -> Any:  # noqa: N802 - FontParts method name
        """The same layer object until ``reset()``, so per-layer caches can key on it."""
        return self._read(f"layer:{name}", lambda: self.font.getLayer(name))

    @property
    def glyphOrder(self) -> Any:  # noqa: N802 - FontParts attribute name
        return self._read("glyphOrder", lambda: self.font.glyphOrder)

    @property
    def defaultLayerName(self) -> Any:  # noqa: N802 - FontParts attribute name
        return self._read("defaultLayerName", self._live_default_layer)

    def _live_default_layer(self) -> Any:
        # FontParts' public property validates against every layer of the font;
        # the backend getter reads the current master name directly.
        read = getattr(self.font, "_get_defaultLayerName", None)
        return read() if callable(read) else self.font.defaultLayerName

    def master_changed(self) -> bool:
        """True when the current master differs from the remembered one."""
        if "defaultLayerName" not in self._memo:
            return False
        return self._live_default_layer() != self._memo["defaultLayerName"]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name == "font":
            raise AttributeError(name)
        value = getattr(self.font, name)
        if name == "glyph_summaries" and callable(value):
            return lambda: self._read("glyph_summaries", lambda: tuple(value()))
        return value
