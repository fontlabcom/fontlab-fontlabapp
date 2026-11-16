# this_file: src/fontlabapp/vfjo/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""vfjo: VFJ Objects, a Box-based workflow over FontLab 9.1 object JSON.

What: ``fontlabapp.vfjo`` casts the object JSON of
``fontlabapp.objects.json_data`` onto python-box, so glyphs, layers,
elements, contours, anchors and hints read and edit as attributes. It adds
safe whole-object edits (``move``, ``scale``, ``rename``, ``set_width``,
``add_suffix``, ``edit_nodes``) and ``paste`` into the font with Undo.
``nodes`` holds the node-string model (``Node``).

How: ``loads``/``load``/``from_glyphs``/``from_clipboard`` return
``Objects``; ``Objects.data`` is the box tree. Data is validated by
``json_data.Envelope.parse`` on the way in and out. Reading a missing key
raises; a misspelt new key on a known level raises; ``add_key`` adds a key
on purpose. ``move`` and ``scale`` change element transforms (components
and transformed elements) or nodes, and anchors, guidelines and hints
follow, so the data stays consistent. ``edit_nodes`` refuses to change a
contour's point count (hints address points by index).

Undo: only ``paste`` (and ``Objects.paste``) changes a font. Glyph data
becomes new glyphs through ``json_data.paste_glyphs``: Edit > Undo removes
them one step per new glyph plus one for the outlines
(``GLYPHS_UNDO_TEXT``). Layer, element and contour data is added to the
current glyph's active layer through ``json_data.paste_shapes`` as one
step; with ``font=`` it must be the current font. ``available``,
``NEEDS_91``, ``PARTIAL_TEXT``, ``GLYPHS_UNDO_TEXT`` and
``PartialWriteError`` are re-exported so scripts need only ``vfjo``.

Limits: never reads FontLab's ``vic/*`` clipboard (that binding crashes
9.1.9812, Fontlab/fl#8655). Checked live in FontLab 9.1.9812 with Lato and
python-box 7.4.1: ``from_glyphs(["o", "Aogonek"])``, ``add_suffix``,
``move(40, 0)``, ``set_width(w + 80)`` and ``paste`` gave correct nodes,
anchors, component offsets and widths in both masters; a misspelt read
raised ``BoxKeyError`` and a misspelt write ``UnknownKeyError``. ``scale``,
Undo and shape paste are not yet checked live.

How to use::

    from fontlabapp import vfjo
    objs = vfjo.from_glyphs(["o"])                 # selected glyphs by default
    vfjo.add_suffix(objs, ".shift")
    vfjo.move(objs, 100, 0); vfjo.set_width(objs, lambda w: w + 200)
    objs.paste()                                   # new glyph o.shift, with Undo
"""

from importlib import import_module
from typing import Any

__all__ = [
    "GLYPHS_UNDO_TEXT",
    "KNOWN_KEYS",
    "NEEDS_91",
    "PARTIAL_TEXT",
    "Node",
    "Objects",
    "PartialWriteError",
    "UnknownKeyError",
    "add_key",
    "add_suffix",
    "anchors",
    "available",
    "contours",
    "edit_nodes",
    "elements",
    "format_nodes",
    "from_clipboard",
    "from_glyphs",
    "layers",
    "load",
    "loads",
    "move",
    "parse_nodes",
    "paste",
    "rename",
    "scale",
    "set_width",
]

_EXPORTS = {
    "GLYPHS_UNDO_TEXT": "fontlabapp.objects.json_data",
    "KNOWN_KEYS": "fontlabapp.vfjo._data",
    "NEEDS_91": "fontlabapp.objects.json_data",
    "Node": "fontlabapp.vfjo.nodes",
    "Objects": "fontlabapp.vfjo._data",
    "PARTIAL_TEXT": "fontlabapp.objects.json_data",
    "PartialWriteError": "fontlabapp.core.history.glyphs",
    "UnknownKeyError": "fontlabapp.vfjo._data",
    "add_key": "fontlabapp.vfjo._data",
    "add_suffix": "fontlabapp.vfjo._edit",
    "anchors": "fontlabapp.vfjo._edit",
    "available": "fontlabapp.objects.json_data",
    "contours": "fontlabapp.vfjo._edit",
    "edit_nodes": "fontlabapp.vfjo._edit",
    "elements": "fontlabapp.vfjo._edit",
    "format_nodes": "fontlabapp.vfjo.nodes",
    "from_clipboard": "fontlabapp.vfjo._data",
    "from_glyphs": "fontlabapp.vfjo._data",
    "layers": "fontlabapp.vfjo._edit",
    "load": "fontlabapp.vfjo._data",
    "loads": "fontlabapp.vfjo._data",
    "move": "fontlabapp.vfjo._edit",
    "parse_nodes": "fontlabapp.vfjo.nodes",
    "paste": "fontlabapp.vfjo._edit",
    "rename": "fontlabapp.vfjo._edit",
    "scale": "fontlabapp.vfjo._edit",
    "set_width": "fontlabapp.vfjo._edit",
}


def __getattr__(name: str) -> Any:
    """Resolve one public name only when it is requested."""
    try:
        source = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(source), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List only the names published by this package."""
    return sorted(__all__)
