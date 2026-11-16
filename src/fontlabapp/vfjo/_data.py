# this_file: src/fontlabapp/vfjo/_data.py
# SPDX-License-Identifier: Apache-2.0
"""The ``Objects`` root: FontLab 9.1 object JSON as a guarded python-box tree.

What: ``loads`` validates object JSON with ``json_data.Envelope.parse`` and
casts it onto a ``Box`` subclass, so ``objs.data.glyph.layers[0].advanceWidth``
reads like Python. ``Objects`` wraps that tree (``Objects.data``) and adds
helpers that are not JSON keys: ``kind``, ``glyphs``, ``glyph_names``,
``to_dict``, ``to_bytes``, ``envelope``, ``describe``, ``save``,
``copy_to_clipboard``, ``paste`` and ``copy``.

How: every level of the tree is a ``_Data`` box. Reading a missing key
raises ``UnknownKeyError`` (a ``KeyError`` and ``AttributeError``).
Existing keys can be written freely. A new key is refused on the known
levels (root, glyph, layer, element, ...) unless it is in ``KNOWN_KEYS``,
so a misspelt ``advanceWidht`` fails instead of being saved silently.
``add_key(box, key, value)`` adds any key on purpose. The level of a box
comes from the key that holds it; levels not listed (``hints``, ``lib``)
accept any key.

Lists are guarded too: an item added by ``append``, ``extend``, ``insert``
or ``lst[i] = ...`` becomes a ``_Data`` box locked at the level its list
implies (a dict appended to ``glyph.layers`` is a layer). A dict assigned to
an existing key is locked at that key's level the same way. ``update``,
``|=`` and ``setdefault`` go through the same check as ``box[key] = value``.

Limits: Box and dict method names (``items``, ``keys``, ``values``,
``copy``, ``update``, ``get``, ``to_dict``, ...) shadow JSON keys of the
same name in attribute access; use ``x["items"]`` for those. Keys are used
exactly as FontLab writes them: no dotted paths and no converted names
(``lib["a-b"]`` is not reachable as ``lib.a_b``).
"""

from __future__ import annotations

import copy as _copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

from box import Box, BoxList

from fontlabapp.objects import json_data

KNOWN_KEYS: dict[str, frozenset[str]] = {
    "root": frozenset(
        {
            "dataType",
            "upm",
            "packageId",
            "glyph",
            "objects",
            "layer",
            "element",
            "contour",
        }
    ),
    "entry": frozenset({"glyph", "layer", "element", "contour"}),
    "glyph": frozenset(
        {
            "name",
            "lastModified",
            "layers",
            "unicode",
            "unicodes",
            "openTypeGlyphClass",
            "colorFlag",
            "lib",
            "note",
        }
    ),
    "layer": frozenset(
        {
            "name",
            "flags",
            "advanceWidth",
            "advanceHeight",
            "elements",
            "hints",
            "color",
            "active",
            "colorFlag",
            "anchors",
            "guidelines",
            "autoRecipe",
            "metricsLeft",
            "metricsWidth",
            "metricsRight",
        }
    ),
    "element": frozenset(
        {
            "id",
            "elementData",
            "elementDataID",
            "active",
            "component",
            "transform",
            "nonSpacing",
            "locked",
        }
    ),
    "elementData": frozenset({"contours", "component", "elements"}),
    "contour": frozenset({"id", "nodes"}),
    "transform": frozenset({"xOffset", "yOffset", "xScale", "yScale"}),
    "anchor": frozenset({"name", "point", "appearance"}),
    "guideline": frozenset({"vertical", "horizontal", "position", "center", "vector"}),
    "component": frozenset({"glyphName"}),
}
"""Keys a known level accepts as new keys; other new keys need ``add_key``."""

_CHILD = {
    "objects": "entry",
    "glyph": "glyph",
    "layers": "layer",
    "layer": "layer",
    "elements": "element",
    "element": "element",
    "elementData": "elementData",
    "contours": "contour",
    "contour": "contour",
    "transform": "transform",
    "anchors": "anchor",
    "guidelines": "guideline",
    "component": "component",
}


class UnknownKeyError(KeyError, AttributeError):
    """A new key that its level does not know; use ``add_key`` to add it anyway."""


class _Data(Box):
    """A box that refuses unknown new keys once locked (see the module docstring)."""

    def __setitem__(self, key: Any, value: Any) -> None:
        own = self.__dict__
        if own.get("_locked") and key not in self:
            allowed = KNOWN_KEYS.get(own.get("_level") or "")
            if allowed is not None and key not in allowed:
                msg = (
                    f"{key!r} is not a known {own['_level']} key "
                    f"(known: {', '.join(sorted(allowed))}); use vfjo.add_key(box, {key!r}, value) to add it"
                )
                raise UnknownKeyError(msg)
        super().__setitem__(key, value)
        if own.get("_locked"):
            _lock_key(self, key, _child_level(own.get("_level"), key))

    def update(self, *args: Any, **kwargs: Any) -> None:
        """Set each key through ``__setitem__``, so unknown new keys are refused."""
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def __ior__(self, other: Mapping[str, Any]) -> Self:  # type: ignore[override]
        self.update(other)
        return self

    def setdefault(self, key: Any, default: Any = None) -> Any:
        """Like ``dict.setdefault``, with the new-key check of ``__setitem__``."""
        if key not in self:
            self[key] = default
        return self[key]


_BOX_OPTIONS = {
    "box_class": _Data,
    "default_box": False,
    "conversion_box": False,
    "box_dots": False,
}


class _List(BoxList):
    """A box list whose added items become ``_Data`` locked at the list's level."""

    def _adopt(self, start: int = 0, stop: int | None = None) -> None:
        own = self.__dict__
        if own.get("_locked"):
            for index in range(start, len(self) if stop is None else stop):
                _lock_item(self, index, own.get("_level"))

    def append(self, item: Any) -> None:
        super().append(item)
        self._adopt(len(self) - 1)

    def extend(self, items: Any) -> None:
        start = len(self)
        super().extend(items)
        self._adopt(start)

    def insert(self, index: Any, item: Any) -> None:
        before = len(self)
        super().insert(index, item)
        if len(self) > before:
            self._adopt()

    def __setitem__(self, index: Any, value: Any) -> None:
        if isinstance(index, slice):
            super().__setitem__(index, [_convert(v) for v in value])
            self._adopt()
            return
        super().__setitem__(index, _convert(value))
        self._adopt(index % len(self), index % len(self) + 1)

    def __iadd__(self, items: Any) -> Self:
        self.extend(items)
        return self


def _convert(value: Any) -> Any:
    if isinstance(value, Mapping) and not isinstance(value, _Data):
        return _Data(dict(value), **_BOX_OPTIONS)
    return value


def _child_level(level: str | None, key: Any) -> str | None:
    return _CHILD.get(key) if level else None


def _lock(value: Any, level: str | None) -> None:
    """Mark ``value`` and every box below it as locked at its level."""
    if isinstance(value, _Data):
        value.__dict__["_level"] = level
        value.__dict__["_locked"] = True
        for key in list(value.keys()):
            _lock_key(value, key, _child_level(level, key))
    elif isinstance(value, _List):
        value.__dict__["_level"] = level
        value.__dict__["_locked"] = True
        for index in range(len(value)):
            _lock_item(value, index, level)


def _lock_key(box: _Data, key: Any, level: str | None) -> None:
    """Lock ``box[key]``, first turning a plain box list into a guarded ``_List``."""
    value = box[key]
    if isinstance(value, list) and not isinstance(value, _List):
        value = _List(value, **_BOX_OPTIONS)
        dict.__setitem__(box, key, value)
    _lock(value, level)


def _lock_item(items: _List, index: int, level: str | None) -> None:
    value = list.__getitem__(items, index)
    if isinstance(value, Mapping) and not isinstance(value, _Data):
        value = _Data(dict(value), **_BOX_OPTIONS)
        list.__setitem__(items, index, value)
    elif isinstance(value, list) and not isinstance(value, _List):
        value = _List(value, **_BOX_OPTIONS)
        list.__setitem__(items, index, value)
    _lock(value, level)


def _box(data: Mapping[str, Any]) -> _Data:
    root = _Data(_copy.deepcopy(dict(data)), **_BOX_OPTIONS)
    _lock(root, "root")
    return root


def add_key(box: Box, key: str, value: Any) -> Box:
    """Add ``key`` to ``box`` even when its level does not know it; return ``box``."""
    if isinstance(box, _Data):
        own = box.__dict__
        locked = own.get("_locked")
        own["_locked"] = False
        try:
            box[key] = value
        finally:
            own["_locked"] = locked
        if locked:
            _lock_key(box, key, _child_level(own.get("_level"), key))
    else:
        box[key] = value
    return box


class Objects:
    """FontLab object JSON: ``data`` is the guarded box root; methods add helpers."""

    __slots__ = ("data",)

    def __init__(self, data: _Data) -> None:
        self.data = data

    def __repr__(self) -> str:
        names = ", ".join(self.glyph_names)
        return f"<vfjo.Objects {self.kind or 'empty'}{': ' + names if names else ''}>"

    def items(self) -> list[tuple[str, _Data]]:
        """Return ``(kind, box)`` for each payload object, in order."""
        root = self.data
        if "objects" in root:
            return [
                (kind, entry[kind])
                for entry in root["objects"]
                for kind in json_data.KINDS
                if kind in entry
            ]
        return [(kind, root[kind]) for kind in json_data.KINDS if kind in root]

    @property
    def kind(self) -> str:
        """``"glyph"``, ``"layer"``, ``"element"`` or ``"contour"``; ``"mixed"``; ``""`` when empty."""
        kinds = {kind for kind, _ in self.items()}
        if not kinds:
            return ""
        return kinds.pop() if len(kinds) == 1 else "mixed"

    @property
    def glyphs(self) -> list[_Data]:
        """Return the glyph boxes (singleton ``glyph`` or ``objects[*].glyph``)."""
        return [box for kind, box in self.items() if kind == "glyph"]

    @property
    def glyph_names(self) -> list[str]:
        """Return the glyph names, in order."""
        return [str(glyph.get("name", "")) for glyph in self.glyphs]

    def to_dict(self) -> dict[str, Any]:
        """Return plain ``dict``/``list`` data."""
        return self.data.to_dict()

    def envelope(self) -> json_data.Envelope:
        """Return a validated ``json_data.Envelope`` of the current data."""
        return json_data.Envelope.parse(self.to_dict())

    def to_bytes(self, indent: int | None = None) -> bytes:
        """Return validated UTF-8 object JSON."""
        return self.envelope().to_bytes(indent=indent)

    def describe(self) -> list[str]:
        """Return ``json_data.describe`` lines."""
        return json_data.describe(self.envelope())

    def save(self, path: str | Path) -> Path:
        """Write pretty-printed object JSON to ``path``; return the path."""
        return json_data.save_file(path, self.to_bytes())

    def copy_to_clipboard(self) -> None:
        """Put the JSON on the clipboard (``application/json`` and plain text)."""
        json_data.copy_to_clipboard(self.to_bytes())

    def paste(self, font: Any = None, **kw: Any) -> json_data.Pasted:
        """Paste into ``font`` (default: the current font); see ``vfjo.paste``."""
        from fontlabapp.vfjo._edit import paste

        return paste(self, font, **kw)

    def copy(self) -> Objects:
        """Return an independent, fully locked copy."""
        return Objects(_box(self.to_dict()))


def loads(data: Any) -> Objects:
    """Return ``Objects`` from object JSON bytes, text, a mapping or ``Objects``.

    Raises ``ValueError`` when the data is not FontLab object JSON.
    """
    if isinstance(data, Objects):
        return data.copy()
    return Objects(_box(json_data.Envelope.parse(data).to_dict()))


def load(path: str | Path) -> Objects:
    """Read object JSON from a file."""
    return loads(json_data.load_file(path))


def _current_package() -> Any:
    from fontlabapp.core.scripting import current_package

    return current_package()


def _selected_names() -> list[str]:
    from fontlabapp.core.scripting import names_selected_names

    return names_selected_names()


def from_glyphs(glyphs: Any = None, font: Any = None) -> Objects:
    """Export glyphs (names or ``flGlyph``) of ``font`` as ``Objects``.

    Defaults: the current font, and its selected glyphs or else the current
    glyph. Raises ``RuntimeError`` with no font and ``KeyError`` for a name
    the font does not have.
    """
    package = font if font is not None else _current_package()
    if package is None:
        raise RuntimeError("No font is open.")
    if glyphs is None:
        glyphs = _selected_names()
    elif isinstance(glyphs, str):
        glyphs = [glyphs]
    resolved = []
    for glyph in glyphs:
        if isinstance(glyph, str):
            found = package.findName(glyph)
            if found is None:
                raise KeyError(f"The font has no glyph {glyph!r}.")
            glyph = found
        resolved.append(glyph)
    if not resolved:
        raise ValueError("No glyphs to export.")
    return loads(json_data.export(package, resolved))


def from_clipboard() -> Objects | None:
    """Return the object JSON on the clipboard, or ``None`` when there is none."""
    raw = json_data.read_clipboard()
    return None if raw is None else loads(raw)
