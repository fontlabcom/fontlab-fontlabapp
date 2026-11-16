# this_file: src/fontlabapp/objects/json_data.py
"""FontLab 9.1 object JSON: read, edit, copy, save and paste glyphs, layers, elements and contours.

What: FontLab 9.1 (build 9812 and later) can write glyphs, layers, elements
and contours as JSON and read that JSON back into new, detached objects:
``fontlab.flModelProducer.getClipboardDataJson(package_id, upm, objects)``
returns a ``QByteArray`` and ``getObjectsFromJsonData(data)`` returns a
list, or ``None`` when it cannot read the data. This module gives that pair
a safe Python surface.

The pure layer needs no FontLab. ``Envelope.parse`` reads the JSON
envelope (``"dataType": "com.fontlab.objects"``, ``"upm"``, ``"packageId"``
and one payload: a singleton ``"glyph"``, ``"layer"``, ``"element"`` or
``"contour"`` key for one object, ``"objects": [{"glyph": {...}}, ...]`` for
two or more, and no payload key for an empty list). ``Envelope.to_bytes``
writes the same shapes back. ``describe`` lists what the data holds, and
``rename_glyphs``, ``unique_glyph_names``, ``filter_layers``,
``set_advance_width`` and ``drop_unicodes`` return edited copies.

The native layer runs inside FontLab: ``available``, ``export``,
``decode``, ``copy_to_clipboard``, ``read_clipboard``, ``save_file``,
``load_file``, ``paste_glyphs`` and ``paste_shapes``.

How: ``decode`` always hands FontLab a ``PythonQt.QtCore.QByteArray``.
Passing Python ``bytes``, ``bytearray`` or ``str`` to
``getObjectsFromJsonData`` crashes FontLab 9.1.9812 (SIGBUS), so no other
type reaches it. ``None`` from FontLab becomes ``ValueError``. Decoded
objects are detached: a decoded glyph has a new id and no font, and
``flGlyph`` has no ``unicode`` attribute, so Unicode values come from the
JSON. ``upm`` is ignored on decode; nothing is scaled.

``paste_glyphs`` never calls ``flPackage.addGlyph`` (a raw insert without
Undo that also produced duplicate names live). It creates glyphs through
``fontlabapp.glyphs.creation.create_glyphs`` and copies the decoded
outlines in its ``fill`` step. ``paste_shapes`` adds decoded shapes to one
live layer inside one ``fontlabapp.core.history.glyphs.commit``.

Undo: the JSON calls record nothing. ``paste_glyphs``: each new glyph is
its own Undo step (FontLab's Add Glyph) and the outlines are one more
named step. ``paste_shapes``: one named Undo step. Everything else changes
no font.

Clipboard: FontLab 9.1 puts this JSON on the clipboard as
``application/json`` (seen live on 9.1.9812: Edit > Copy of a glyph in the
Font window, byte for byte what ``export`` returns), next to its own
``vic/*`` formats. ``copy_to_clipboard`` writes ``application/json`` plus
the JSON as plain text; ``read_clipboard`` reads ``application/json``, then
the older ``application/x-fontlab-objects+json``, then plain text.

Limits: whether FontLab's Edit > Paste accepts our clipboard without its
``vic/*`` formats is not verified live. Components in pasted glyphs keep their base
names; a base missing from the target font is not created. Unicode values
are dropped from renamed glyphs; other Unicode clashes are not checked.

How to use::

    from fontlabapp.objects import json_data
    raw = json_data.export(package, [glyph])        # bytes, UTF-8 JSON
    env = json_data.Envelope.parse(raw)
    print("\\n".join(json_data.describe(env)))
    env = json_data.rename_glyphs(env, {"o": "o.alt"})
    json_data.paste_glyphs(package, env, facts=scan_auto_facts(package))
"""

from __future__ import annotations

import copy as _copy
import json
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from fontlabapp import _native

#: The ``dataType`` value of every FontLab object JSON envelope.
DATA_TYPE = "com.fontlab.objects"
#: The object kinds FontLab writes, as their JSON keys.
KINDS = ("glyph", "layer", "element", "contour")
#: The clipboard MIME type FontLab 9.1 uses for object JSON (seen live).
MIME_TYPE = "application/json"
#: The MIME type earlier fontlabapp versions wrote; still read.
_OLD_MIME_TYPE = "application/x-fontlab-objects+json"
#: The message every caller shows on FontLab 9.0.
NEEDS_91 = "This needs FontLab 9.1 or later: this FontLab has no object JSON API."
#: Undo text for pasted glyphs and for pasted shapes.
#: Same text as ``fontlabapp.glyphs.creation.UNDO_TEXT`` (kept here so import
#: stays stdlib-only; a test pins the two together).
GLYPHS_UNDO_TEXT = (
    "Each new glyph is recorded as its own Undo step, "
    "and the outlines as one more Undo step."
)
SHAPES_UNDO_TEXT = "The pasted shapes are one Undo step."
#: The message for ``history.PartialWriteError``: part of the edit may exist.
PARTIAL_TEXT = (
    "The paste stopped part way. FontLab may now hold part of it "
    "(the details name any new glyphs). Use Edit > Undo to remove it."
)

Item = tuple[str, dict[str, Any]]


# ---------------------------------------------------------------- pure layer
@dataclass(frozen=True)
class Envelope:
    """One FontLab object JSON document: header values and the ordered items.

    ``upm`` and ``package_id`` are ``None`` when the JSON omits them (FontLab
    still reads such data). ``items`` holds ``(kind, payload)`` pairs.
    ``extra`` keeps unknown top-level keys so a round trip loses nothing.
    """

    upm: int | None
    package_id: int | None
    items: tuple[Item, ...] = ()
    extra: tuple[tuple[str, Any], ...] = field(default=())

    @classmethod
    def parse(cls, data: bytes | bytearray | str | Mapping[str, Any]) -> Envelope:
        """Read and check object JSON; raise ``ValueError`` with a plain reason."""
        if isinstance(data, Envelope):
            return data
        if isinstance(data, bytes | bytearray):
            try:
                data = bytes(data).decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"Object JSON is not UTF-8 text: {error}") from None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as error:
                raise ValueError(f"Object JSON is not valid JSON: {error}") from None
        if not isinstance(data, Mapping):
            raise ValueError(  # noqa: TRY004 - malformed data is a ValueError for callers
                f"Object JSON must be a JSON object, not {type(data).__name__}."
            )
        kind = data.get("dataType")
        if kind != DATA_TYPE:
            raise ValueError(
                f'Object JSON dataType is {kind!r}, expected "{DATA_TYPE}".'
            )
        payload = [key for key in (*KINDS, "objects") if key in data]
        if len(payload) > 1:
            raise ValueError(
                f"Object JSON has more than one payload key: {', '.join(payload)}."
            )
        items: tuple[Item, ...] = ()
        if payload == ["objects"]:
            items = tuple(_entry(entry) for entry in _list(data["objects"]))
        elif payload:
            items = (_item(payload[0], data[payload[0]]),)
        known = {"dataType", "upm", "packageId", *KINDS, "objects"}
        extra = tuple((k, v) for k, v in data.items() if k not in known)
        return cls(
            _int_or_none(data, "upm"), _int_or_none(data, "packageId"), items, extra
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON object: singleton key for one item, ``objects`` for more."""
        out: dict[str, Any] = {"dataType": DATA_TYPE}
        if self.upm is not None:
            out["upm"] = self.upm
        if self.package_id is not None:
            out["packageId"] = self.package_id
        out.update(self.extra)
        if len(self.items) == 1:
            kind, payload = self.items[0]
            out[kind] = payload
        elif self.items:
            out["objects"] = [{kind: payload} for kind, payload in self.items]
        return out

    def to_bytes(self, indent: int | None = None) -> bytes:
        """Return UTF-8 JSON; ``indent`` pretty-prints it."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False).encode(
            "utf-8"
        )

    def kinds(self) -> tuple[str, ...]:
        """Return the kind of each item, in order."""
        return tuple(kind for kind, _ in self.items)

    def glyph_names(self) -> tuple[str, ...]:
        """Return the names of the glyph items, in order."""
        return tuple(str(p.get("name", "")) for k, p in self.items if k == "glyph")

    def replace_items(self, items: Iterable[Item]) -> Envelope:
        """Return a copy with other items and the same header."""
        return Envelope(self.upm, self.package_id, tuple(items), self.extra)


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError('Object JSON "objects" must be a list.')  # noqa: TRY004 - malformed data is a ValueError for callers
    return value


def _entry(entry: Any) -> Item:
    if not isinstance(entry, Mapping) or len(entry) != 1:
        raise ValueError('Each entry in "objects" must be an object with one key.')
    ((kind, payload),) = entry.items()
    return _item(kind, payload)


def _item(kind: str, payload: Any) -> Item:
    if kind not in KINDS:
        raise ValueError(
            f"Object JSON item kind {kind!r} is not one of {', '.join(KINDS)}."
        )
    if not isinstance(payload, Mapping):
        raise ValueError(f"Object JSON {kind} must be a JSON object.")  # noqa: TRY004 - malformed data is a ValueError for callers
    return kind, dict(payload)


def _int_or_none(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Object JSON {key} must be a number, not {value!r}.")  # noqa: TRY004 - malformed data is a ValueError for callers
    return int(value)


def _count(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    return len(value) if isinstance(value, list) else 0


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _width(value: Any) -> str:
    return f"{value:g}" if isinstance(value, int | float) else "?"


def _layer_text(layer: Mapping[str, Any]) -> str:
    return (
        f'"{layer.get("name", "")}" width {_width(layer.get("advanceWidth"))}, '
        f"{_plural(_count(layer, 'elements'), 'element')}"
    )


def describe(envelope: Envelope) -> list[str]:
    """Return one line per item: kind, name, layers, widths and counts."""
    if not envelope.items:
        return ["No objects."]
    lines = []
    for kind, payload in envelope.items:
        if kind == "glyph":
            layers = [x for x in payload.get("layers") or () if isinstance(x, Mapping)]
            code = payload.get("unicode")
            code_text = f" U+{str(code).upper()}" if code else ""
            parts = "; ".join(_layer_text(x) for x in layers) or "no layers"
            lines.append(f'glyph "{payload.get("name", "")}"{code_text}: {parts}')
        elif kind == "layer":
            lines.append(f"layer {_layer_text(payload)}")
        elif kind == "element":
            lines.append(
                f"element id {payload.get('id', '?')}, "
                f"active {bool(payload.get('active', False))}"
            )
        else:
            lines.append(f"contour with {_plural(_count(payload, 'nodes'), 'node')}")
    return lines


def unique_name(name: str, existing: Container[str]) -> str:
    """Return ``name``, or ``name.1``, ``name.2``, ... the first not in ``existing``."""
    if name not in existing:
        return name
    number = 1
    while f"{name}.{number}" in existing:
        number += 1
    return f"{name}.{number}"


def _glyphs_edit(
    envelope: Envelope, edit: Callable[[dict[str, Any]], dict[str, Any] | None]
) -> Envelope:
    items = []
    for kind, payload in envelope.items:
        if kind == "glyph":
            payload = _copy.deepcopy(payload)
            result = edit(payload)
            if result is None:
                continue
            payload = result
        items.append((kind, payload))
    return envelope.replace_items(items)


def rename_glyphs(
    envelope: Envelope, rename: Mapping[str, str] | Callable[[str], str]
) -> Envelope:
    """Return a copy whose glyph items carry new names from a mapping or a function.

    Names missing from a mapping stay. Unicode values stay; use
    ``drop_unicodes`` when the renamed glyph must not claim them.
    """
    change = rename.get if isinstance(rename, Mapping) else None

    def edit(payload: dict[str, Any]) -> dict[str, Any]:
        old = str(payload.get("name", ""))
        payload["name"] = change(old, old) if change else rename(old)
        return payload

    return _glyphs_edit(envelope, edit)


def unique_glyph_names(
    envelope: Envelope, existing: Container[str]
) -> tuple[Envelope, dict[str, str]]:
    """Rename glyph items so no name is in ``existing`` or repeated in the data.

    Return the edited copy and ``{old: new}`` for the renamed glyphs, in
    item order. A renamed glyph keeps its Unicode values.
    """
    planned: set[str] = set()
    renamed: dict[str, str] = {}

    class Taken:
        def __contains__(self, name: object) -> bool:
            return name in planned or name in existing

    def edit(payload: dict[str, Any]) -> dict[str, Any]:
        old = str(payload.get("name", ""))
        new = unique_name(old, Taken())
        planned.add(new)
        if new != old:
            renamed.setdefault(old, new)
            payload["name"] = new
        return payload

    return _glyphs_edit(envelope, edit), renamed


def filter_layers(envelope: Envelope, names: Iterable[str]) -> Envelope:
    """Keep only the layers named in ``names``: inside glyphs and as layer items."""
    keep = set(names)

    def edit(payload: dict[str, Any]) -> dict[str, Any]:
        layers = payload.get("layers") or []
        payload["layers"] = [x for x in layers if x.get("name") in keep]
        return payload

    edited = _glyphs_edit(envelope, edit)
    return edited.replace_items(
        (kind, payload)
        for kind, payload in edited.items
        if kind != "layer" or payload.get("name") in keep
    )


def set_advance_width(
    envelope: Envelope, width: float, layers: Iterable[str] | None = None
) -> Envelope:
    """Set ``advanceWidth`` on glyph layers and layer items (all, or the named ones)."""
    only = None if layers is None else set(layers)

    def apply(layer: dict[str, Any]) -> dict[str, Any]:
        if only is None or layer.get("name") in only:
            layer["advanceWidth"] = width
        return layer

    def edit(payload: dict[str, Any]) -> dict[str, Any]:
        payload["layers"] = [apply(x) for x in payload.get("layers") or []]
        return payload

    edited = _glyphs_edit(envelope, edit)
    return edited.replace_items(
        (kind, apply(_copy.deepcopy(p)) if kind == "layer" else p)
        for kind, p in edited.items
    )


def drop_unicodes(envelope: Envelope, names: Iterable[str] | None = None) -> Envelope:
    """Remove the ``unicode`` value from all glyph items, or from the named ones."""
    only = None if names is None else set(names)

    def edit(payload: dict[str, Any]) -> dict[str, Any]:
        if only is None or payload.get("name") in only:
            payload.pop("unicode", None)
        return payload

    return _glyphs_edit(envelope, edit)


def unicodes(payload: Mapping[str, Any]) -> tuple[int, ...]:
    """Return the code points of a glyph payload's ``unicode`` hex text (``"006f"``)."""
    text = str(payload.get("unicode") or "")
    values = []
    for token in text.replace(",", " ").split():
        try:
            values.append(int(token.upper().removeprefix("U+"), 16))
        except ValueError:
            raise ValueError(
                f"Glyph {payload.get('name', '')!r} has an unreadable unicode {text!r}."
            ) from None
    return tuple(values)


def only_glyphs(envelope: Envelope) -> Envelope:
    """Return a copy holding only the glyph items."""
    return envelope.replace_items(x for x in envelope.items if x[0] == "glyph")


# ---------------------------------------------------------------- native layer
def available(fl: Any = None) -> bool:
    """True when this FontLab has the object JSON API (9.1 or later)."""
    if fl is None:
        try:
            fl = _native("fontlab")
        except RuntimeError:
            return False
    producer = getattr(fl, "flModelProducer", None)
    return hasattr(producer, "getObjectsFromJsonData") and hasattr(
        producer, "getClipboardDataJson"
    )


def require_available(fl: Any = None) -> None:
    """Raise ``RuntimeError(NEEDS_91)`` on FontLab 9.0 or outside FontLab."""
    if not available(fl):
        raise RuntimeError(NEEDS_91)


def _raw(data: Envelope | bytes | bytearray | str | Mapping[str, Any]) -> bytes:
    """Check ``data`` as an envelope and return its UTF-8 JSON."""
    if isinstance(data, bytes | bytearray):
        Envelope.parse(data)
        return bytes(data)
    return Envelope.parse(data).to_bytes()


def _qt(qt: Any) -> Any:
    return _native("PythonQt") if qt is None else qt


def as_qbytearray(data: Any, qt: Any = None) -> Any:
    """Return a ``QByteArray`` for ``data``; a ``QByteArray`` passes unchanged."""
    qbytes = _qt(qt).QtCore.QByteArray
    if isinstance(data, qbytes):
        return data
    return qbytes(_raw(data))


def export(package: Any, objects: Sequence[Any], *, fl: Any = None) -> bytes:
    """Return FontLab's JSON for ``objects`` (glyphs, layers, shapes or contours).

    Reads only: the font does not change and nothing is recorded for Undo.
    """
    fl = _native("fontlab") if fl is None else fl
    require_available(fl)
    data = fl.flModelProducer.getClipboardDataJson(
        int(package.id), int(package.upm), list(objects)
    )
    return bytes(data.data())


def decode(data: Any, *, fl: Any = None, qt: Any = None) -> list[Any]:
    """Return new detached objects read from object JSON.

    ``data``: an ``Envelope``, a dict, JSON ``bytes``/``str`` or a
    ``QByteArray``. Anything but a ``QByteArray`` is checked by
    ``Envelope.parse`` first and then wrapped, because Python bytes crash
    FontLab here. Raises ``ValueError`` when FontLab returns ``None``.
    """
    fl = _native("fontlab") if fl is None else fl
    require_available(fl)
    result = fl.flModelProducer.getObjectsFromJsonData(as_qbytearray(data, qt))
    if result is None:
        raise ValueError(
            "FontLab could not read this object JSON (getObjectsFromJsonData returned None)."
        )
    return list(result)


def copy_to_clipboard(data: Any, *, qt: Any = None) -> None:
    """Put object JSON on the clipboard as ``application/json`` and as plain text."""
    qt = _qt(qt)
    raw = _raw(data)
    mime = qt.QtCore.QMimeData()
    mime.setData(MIME_TYPE, qt.QtCore.QByteArray(raw))
    mime.setText(raw.decode("utf-8"))
    qt.QtGui.QApplication.clipboard().setMimeData(mime)


def copy_objects(
    package: Any, objects: Sequence[Any], *, fl: Any = None, qt: Any = None
) -> bytes:
    """Copy ``objects`` to the clipboard so FontLab's Edit > Paste accepts them.

    Uses ``flModelProducer.copyToClipboard`` when FontLab has it. It writes
    FontLab's own ``vic/objects`` formats plus ``application/json``, the same
    as FontLab's Copy. Live on 9.1.9812, Edit > Paste then added a copied glyph
    in both masters, in the Font window and in a Glyph window. Without it, the
    JSON goes on the clipboard through ``copy_to_clipboard``, which FontLab's
    Paste may not accept. Returns the copied JSON. Reads only: the font does
    not change and nothing is recorded for Undo.
    """
    fl = _native("fontlab") if fl is None else fl
    raw = export(package, objects, fl=fl)
    native_copy = getattr(fl.flModelProducer, "copyToClipboard", None)
    if native_copy is None:
        copy_to_clipboard(raw, qt=qt)
        return raw
    native_copy(int(package.id), list(objects))
    return read_clipboard(qt=qt) or raw


def read_clipboard(*, qt: Any = None) -> bytes | None:
    """Return object JSON from the clipboard, or ``None`` when it holds none.

    ``application/json`` (FontLab's Copy and ours) is read first, then the
    older ``application/x-fontlab-objects+json``, then plain text; each
    counts only when it parses as an object JSON envelope.
    """
    mime = _qt(qt).QtGui.QApplication.clipboard().mimeData()
    if mime is None:
        return None
    candidates = []
    for kind in (MIME_TYPE, _OLD_MIME_TYPE):
        if mime.hasFormat(kind):
            candidates.append(bytes(mime.data(kind).data()))
    if mime.hasText():
        candidates.append(str(mime.text()).encode("utf-8"))
    for raw in candidates:
        try:
            Envelope.parse(raw)
        except ValueError:
            continue
        return raw
    return None


def save_file(path: str | Path, data: Any) -> Path:
    """Write object JSON to ``path`` as pretty-printed UTF-8; return the path."""
    path = Path(path)
    path.write_bytes(Envelope.parse(_raw(data)).to_bytes(indent=2) + b"\n")
    return path


def load_file(path: str | Path) -> bytes:
    """Read object JSON from ``path``; raise ``ValueError`` when it is not object JSON."""
    raw = Path(path).read_bytes()
    Envelope.parse(raw)
    return raw


class Pasted(NamedTuple):
    """What a paste did: the names made, the items skipped and the native result."""

    created: tuple[str, ...]
    skipped: tuple[str, ...]
    notes: tuple[str, ...] = ()
    result: Any = None


class _Taken:
    """Names taken in the font (``package.findName``) or planned for this paste."""

    def __init__(self, package: Any, planned: set[str]) -> None:
        self.package, self.planned = package, planned

    def __contains__(self, name: object) -> bool:
        return name in self.planned or self.package.findName(name) is not None


def _layer_map(
    payload: Mapping[str, Any], masters: Sequence[str]
) -> tuple[dict[str, str], list[str], list[str]]:
    """Return ``{master: JSON layer name}``, unmatched JSON layers and notes."""
    names = [str(x.get("name", "")) for x in payload.get("layers") or ()]
    matched = {m: m for m in masters if m in names}
    notes = []
    if not matched and len(names) == 1 and masters:
        matched = dict.fromkeys(masters, names[0])
        notes.append(
            f'{payload.get("name", "")}: layer "{names[0]}" used for every master'
        )
    unmatched = [n for n in names if n not in matched.values()]
    return matched, unmatched, notes


def _layer_width(payload: Mapping[str, Any], layer_name: str) -> int | None:
    """Return the rounded ``advanceWidth`` of one JSON layer, or ``None`` if it has none."""
    for layer in payload.get("layers") or ():
        if layer.get("name") == layer_name and layer.get("advanceWidth") is not None:
            return round(float(layer["advanceWidth"]))
    return None


class _Parts(NamedTuple):
    """What one decoded JSON layer gives a new master layer."""

    shapes: list[Any]
    anchors: list[Any]
    guidelines: list[Any]


def _parts(layer: Any) -> _Parts:
    """Return the shapes, anchors and guidelines of one decoded layer.

    ``flLayer.guidelines`` holds the layer's guidelines and its hints
    (``flGuideLine.isHint()``); hints refer to nodes of the same decoded
    shapes, so both are taken from one decoded layer together.
    """
    return _Parts(
        list(layer.shapes),
        list(getattr(layer, "anchors", ())),
        list(getattr(layer, "guidelines", ())),
    )


def _decoded_layers(
    data: Envelope, matched: Mapping[str, str], fl: Any, qt: Any
) -> dict[str, _Parts]:
    """Return ``{master: parts}`` for one glyph, decoded before any write.

    One decode serves every distinct JSON layer. A JSON layer used for more
    than one master (the one-layer fallback) needs its own shapes per master,
    because one detached shape cannot be added to two layers; those extra
    masters get one more decode each, still before any glyph is created.
    """
    out: dict[str, _Parts] = {}
    used: set[str] = set()
    glyph = None
    for master, layer_name in matched.items():
        if glyph is None or layer_name in used:
            (glyph,) = decode(data, fl=fl, qt=qt)
            used = set()
        used.add(layer_name)
        out[master] = next(
            (_parts(x) for x in glyph.layers if str(x.name) == layer_name),
            _Parts([], [], []),
        )
    return out


def _shape_from_contours(fl: Any, contours: list[Any]) -> Any:
    """Join decoded contours into one new shape.

    The only shape constructor used here: no-argument ``fl.flShape()`` plus
    ``addContours(list, True)``, the same calls as
    ``fontlabapp.glyphs.copies`` (copy generator fill). Isolated so the
    native check can target it.
    """
    shape = fl.flShape()
    shape.addContours(contours, True)
    return shape


def _free_codes(
    package: Any, name: str, codes: Sequence[int], planned: dict[int, str]
) -> tuple[tuple[int, ...], list[str]]:
    """Keep the codes not already in the font (``package.findUnicode``) or this paste.

    ``flGlyph`` has no ``unicodes`` attribute, so the font is asked per code.
    Each clashing code is dropped with a note; kept codes are added to ``planned``.
    """
    kept, notes = [], []
    for code in codes:
        owner = planned.get(code)
        if owner is None:
            found = package.findUnicode(code)
            owner = None if found is None else str(found.name)
        if owner is None:
            planned[code] = name
            kept.append(code)
        else:
            notes.append(f"{name}: U+{code:04X} already on {owner}, dropped")
    return tuple(kept), notes


def paste_glyphs(
    package: Any,
    data: Any,
    *,
    facts: Any,
    on_conflict: str = "rename",
    masters: Sequence[str] | None = None,
    allow_rebuild: bool = False,
    title: str = "Paste JSON Glyphs",
    fl: Any = None,
    qt: Any = None,
) -> Pasted:
    """Create new glyphs from the glyph items of object JSON, with Undo.

    Names are made unique against the font (``on_conflict="rename"``) or
    taken glyphs are skipped (``"skip"``). Each master gets the width,
    outlines, anchors, guidelines and hints of the JSON layer of the same name; with no name match and one
    JSON layer, that layer is used for every master. Unmatched JSON layers
    and non-glyph items are listed in ``skipped``. Renamed glyphs lose their
    Unicode values; a kept value that is already in the font or earlier in
    this paste is dropped with a note. A layer without ``advanceWidth`` gets
    width 0 with a note.

    Automatic glyphs: a new name that ``creation.auto_candidates`` says may
    make FontLab rebuild automatic glyphs is skipped with a note unless
    ``allow_rebuild=True``, which is passed on to ``create_glyphs``. Skipping
    keeps the rest of the paste instead of refusing all of it.

    Every glyph is decoded once before any glyph is created (see
    ``_decoded_layers``), so a decode failure or bad data changes nothing.
    ``create_glyphs`` may raise ``history.PartialWriteError`` after
    the first glyph exists; callers must report it with the Undo hint.
    """
    if on_conflict not in ("rename", "skip"):
        raise ValueError(
            f'on_conflict must be "rename" or "skip", not {on_conflict!r}.'
        )
    import fontlabapp.glyphs.creation as creation  # noqa: PLR0402 - lazy native import

    fl = _native("fontlab") if fl is None else fl
    require_available(fl)
    envelope = Envelope.parse(data)
    skipped = [f"{kind}: not a glyph" for kind in envelope.kinds() if kind != "glyph"]
    glyphs = only_glyphs(envelope)
    masters = [str(m) for m in (package.masters if masters is None else masters)]
    planned: set[str] = set()
    planned_codes: dict[int, str] = {}
    specs, sources, notes = [], {}, []
    for _, payload in glyphs.items:
        old = str(payload.get("name", ""))
        if on_conflict == "skip" and old in _Taken(package, planned):
            skipped.append(f"{old}: exists")
            continue
        new = unique_name(old, _Taken(package, planned))
        matched, unmatched, layer_notes = _layer_map(payload, masters)
        if not matched:
            skipped.append(f"{old}: no layer matches a master")
            continue
        notes += layer_notes
        skipped += [f'{old}: layer "{n}" matches no master' for n in unmatched]
        planned.add(new)
        if new != old:
            notes.append(
                f"{old} -> {new}"
                + (" (Unicode dropped)" if payload.get("unicode") else "")
            )
        codes, code_notes = _free_codes(
            package, new, unicodes(payload) if new == old else (), planned_codes
        )
        notes += code_notes
        layers = []
        for master in (m for m in masters if m in matched):
            width = _layer_width(payload, matched[master])
            if width is None:
                notes.append(f'{new}: layer "{matched[master]}" has no width, 0 used')
            layers.append((master, width or 0))
        specs.append(creation.NewGlyph(new, tuple(layers), codes))
        sources[new] = (glyphs.replace_items([("glyph", payload)]), matched)

    if not allow_rebuild:
        found = creation.auto_candidates(package, facts, [s.name for s in specs])
        for name, owners in found.items():
            skipped.append(
                f"{name}: {creation.rebuild_note(owners)}; not created"
                " (allow_rebuild=True creates it)"
            )
        specs = [s for s in specs if s.name not in found]
    shapes = {spec.name: _decoded_layers(*sources[spec.name], fl, qt) for spec in specs}

    def fill(named: dict[str, Any]) -> None:
        for name, per_master in shapes.items():
            for master, decoded in per_master.items():
                target = named[name].findLayer(master)
                for shape in decoded.shapes:
                    target.addShape(shape)
                for anchor in decoded.anchors:
                    target.addAnchor(anchor)
                if decoded.guidelines:
                    target.appendGuidelines(decoded.guidelines)

    result = creation.create_glyphs(
        package, specs, title, facts, fill=fill, allow_rebuild=allow_rebuild
    )
    return Pasted(tuple(s.name for s in specs), tuple(skipped), tuple(notes), result)


def paste_shapes(
    layer: Any,
    glyph: Any,
    data: Any,
    *,
    facts: Any,
    title: str = "Paste JSON Shapes",
    fl: Any = None,
    qt: Any = None,
) -> Pasted:
    """Add the shapes of object JSON to one live ``layer`` of ``glyph`` as one Undo step.

    Element items paste as shapes; layer items paste all their shapes;
    contour items are joined into one new shape. Glyph items are skipped.
    """
    import fontlabapp.core.history.glyphs as history

    fl = _native("fontlab") if fl is None else fl
    require_available(fl)
    envelope = Envelope.parse(data)
    skipped = tuple(
        f"{k}: paste glyphs as new glyphs" for k in envelope.kinds() if k == "glyph"
    )
    usable = envelope.replace_items(x for x in envelope.items if x[0] != "glyph")
    if not usable.items:
        return Pasted((), skipped)
    objects = decode(usable, fl=fl, qt=qt)
    shapes, contours = [], []
    for kind, obj in zip(usable.kinds(), objects, strict=True):
        if kind == "element":
            shapes.append(obj)
        elif kind == "layer":
            shapes += list(obj.shapes)
        else:
            contours.append(obj)
    if contours:
        shapes.append(_shape_from_contours(fl, contours))

    def mutate() -> None:
        for shape in shapes:
            layer.addShape(shape)

    result = history.commit(
        title, [layer], [glyph], mutate, operation="geometry", facts=facts
    )
    made = (f"{_plural(len(shapes), 'shape')} on {glyph.name}/{layer.name}",)
    return Pasted(made, skipped, (), result)
