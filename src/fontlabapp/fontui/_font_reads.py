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
``features.text``, ``info``, ``glyphOrder``, ``defaultLayerName``, ``current_master`` and
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

from .hinting import package_of

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
        self.kerning_master: str | None = None  # None: the font's default master

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
        """Kerning of ``kerning_master`` (None or the default master: Fontport's), one snapshot per master.

        Fontport reads only the default master's kerning; another master's comes from the native
        package's ``kerning(master)`` (FontLab keeps separate kerning per master). Any failure of
        that read gives no kerning (never the default master's) and ``kerning_unread`` names the master.
        """
        name = self.kerning_master
        if name is not None and name != self._live_default_layer():
            return self._read(f"kerning:{name}", lambda: self._master_kerning(name))
        return self._read("kerning", lambda: dict(self.font.kerning.items()))

    def _master_kerning(self, name: str) -> dict[Any, Any]:
        try:
            return dict(package_of(self.font).kerning(name).items())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            LOG.warning("FontReads: kerning of master %s could not be read: %s", name, error)
            self._memo["kerning_unread"] = name
            return {}

    @property
    def kerning_unread(self) -> str | None:
        """Master whose kerning read failed in this snapshot, else None."""
        return self._memo.get("kerning_unread")

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

    @property
    def current_master(self) -> Any:
        """The layer of FontLab's current master (``flPackage.master``), else ``defaultLayerName``.

        ``setMaster()`` moves ``flPackage.master`` and leaves ``defaultMaster``
        (Fontport's ``defaultLayerName``) where it was, so "Current master"
        must read the package; a detached or host-free font has no package.
        ``renameMaster()`` renames the master but not the glyph layers, so a
        master that names no layer reads as ``defaultLayerName`` and
        ``unresolved_master`` names it.
        """
        return self._read("current_master", self._resolve_current_master)[0]

    @property
    def unresolved_master(self) -> str | None:
        """FontLab's current master when no glyph layer carries its name, else None."""
        return self._read("current_master", self._resolve_current_master)[1]

    def _live_master_name(self) -> str | None:
        """``flPackage.master`` as text; None when there is no live package or no master."""
        master = getattr(package_of(self.font), "master", None)
        return str(master) if master else None

    def _resolve_current_master(self) -> tuple[Any, str | None]:
        self._memo["master_name"] = master = self._live_master_name()
        default = self._live_default_layer()
        if master is None or master == default or self._has_master_layer(master, default):
            return (master or default), None
        return default, master

    def _has_master_layer(self, master: str, default: Any) -> bool:
        # Look at the first glyph that has the default master's layer: one native
        # lookup instead of Fontport's layer list, which walks every glyph.
        package = package_of(self.font)
        for name in self.keys():
            glyph = package.findName(name)
            if glyph is None or _null(glyph.findLayer(default)):
                continue
            return not _null(glyph.findLayer(master))
        return False

    def master_changed(self) -> bool:
        """True when FontLab's current or default master differs from the remembered one.

        Called on every refresh: one ``package_of()`` lookup and one master read
        (about 0.006 ms together in FontLab 9.1.9813, measured while typing).
        """
        memo = self._memo
        if "master_name" in memo and self._live_master_name() != memo["master_name"]:
            return True
        return "defaultLayerName" in memo and self._live_default_layer() != memo["defaultLayerName"]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name == "font":
            raise AttributeError(name)
        value = getattr(self.font, name)
        if name == "glyph_summaries" and callable(value):
            return lambda: self._read("glyph_summaries", lambda: tuple(value()))
        return value


def _null(layer: Any) -> bool:
    return layer is None or bool(getattr(layer, "isNull", False))
