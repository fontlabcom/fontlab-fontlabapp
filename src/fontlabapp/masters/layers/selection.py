# this_file: src/fontlabapp/masters/layers/selection.py
"""Read ordered native selected-layer occurrences without changing selection.

Use bound text-block slots rather than MCP's active-glyph-only editor reply.
Native9787 order, side effects and retained widget-wrapper identity still need
owned-host qualification; source and fake checks alone do not establish them.
"""

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.qt.safe import qt_list
from fontlabapp.core.scripting import (
    _require_selection_window,
    names_font_window_selection,
)


@dataclass(frozen=True)
class LayerOccurrence:
    """One selected slot; native handles retained, equality uses captured facts."""

    package: Any = field(compare=False)
    glyph: Any = field(compare=False)
    layer: Any = field(compare=False)
    block_id: int
    index: int
    package_id: int = field(init=False)
    glyph_id: int = field(init=False)
    layer_id: int = field(init=False)
    glyph_name: str = field(init=False)
    layer_name: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("package_id", int(self.package.id)),
            ("glyph_id", int(self.glyph.id)),
            ("layer_id", int(self.layer.id)),
            ("glyph_name", str(self.glyph.name)),
            ("layer_name", str(self.layer.name)),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class LayerSelection:
    """Document context separate from occurrence selection; retain native owners."""

    context: tuple
    occurrences: tuple[LayerOccurrence, ...]
    carriers: tuple[Any, ...] = field(default=(), compare=False, repr=False)


@dataclass(frozen=True)
class _Document:
    context: tuple
    package: Any
    blocks: tuple = ()
    carriers: tuple = ()


def _check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError(
            "Selected-layer capture exceeded its deadline; no partial result."
        )


def _glyph_window(widget: Any) -> tuple:
    """Retain each known parent wrapper; never enumerate application widgets."""
    parents = []
    for _ in range(16):
        if widget is None:
            break
        parents.append(widget)
        if widget.inherits("GlyphWindow"):
            return tuple(parents)
        widget = widget.parentWidget()
    raise ValueError("Activate a Glyph window before reading editor layers.")


def _document(deadline: float) -> _Document:
    _check(deadline)
    workspace = _native("fontlab").flWorkspace.instance()
    package = workspace.currentPackage
    if package is None or package.isNull:
        raise ValueError("Open a font before reading selected layers.")
    base = (int(package.id), str(package.master))
    panel = workspace.activeFontPanel
    if panel is not None:
        _require_selection_window(base[0])
        # Retain the wrapper so the PythonQt wrapper cache cannot release/reuse
        # it mid-session. Actual wrapper reuse is an explicit native gate.
        return _Document((*base, "font", id(panel)), package, carriers=(panel,))
    canvas = workspace.getActiveCanvas()
    if canvas is None or canvas.isNull:
        raise ValueError("Activate a Glyph window before reading editor layers.")
    parents = _glyph_window(canvas.viewPort)
    blocks = tuple(qt_list(canvas.textBlocks))
    context = (*base, "editor", int(canvas.id), tuple(int(b.id) for b in blocks))
    _check(deadline)
    return _Document(context, package, blocks, (canvas, *parents, *blocks))


def _occurrence(
    package: Any, glyph: Any, layer: Any, block: int, index: int
) -> LayerOccurrence:
    if glyph is None or glyph.isNull or int(glyph.package.id) != int(package.id):
        raise ValueError("A selected glyph is missing or belongs to another font.")
    if layer is None or layer.isNull:
        raise ValueError(
            "A selected layer is missing; refresh after restoring the source."
        )
    return LayerOccurrence(package, glyph, layer, block, index)


def _font_rows(document: _Document, deadline: float) -> tuple[LayerOccurrence, ...]:
    package, rows = document.package, []
    names = names_font_window_selection(
        expected_fg_id=int(package.fgId), deadline=deadline
    )
    for index, name in enumerate(names):
        _check(deadline)
        glyph = package.findName(name)
        layer = None if glyph is None else glyph.findLayer(document.context[1])
        rows.append(_occurrence(package, glyph, layer, 0, index))
    return tuple(rows)


def _editor_rows(document: _Document, deadline: float) -> tuple[LayerOccurrence, ...]:
    rows = []
    for block in document.blocks:
        _check(deadline)
        for index in range(int(block.glyphsCount())):
            _check(deadline)
            info = block.getGlyphAt(index)
            if info is None or not (info.isSelected or info.isActive):
                continue
            glyph = info.glyph
            if glyph is None or glyph.isNull:
                raise ValueError("A selected editor slot has no glyph.")
            name = str(info.symbol.layerName)
            layer = glyph.findLayer(name) if name else glyph.activeLayer
            rows.append(
                _occurrence(document.package, glyph, layer, int(block.id), index)
            )
            _check(deadline)
    return tuple(rows)


def _read(deadline: float) -> LayerSelection:
    document = _document(deadline)
    rows = (_font_rows if document.context[2] == "font" else _editor_rows)(
        document, deadline
    )
    _check(deadline)
    return LayerSelection(document.context, rows, document.carriers)


def capture(deadline: float) -> LayerSelection:
    """Return complete twice-read slot facts, or a diagnosed whole-call refusal.

    Explicit per-slot symbol.layerName preserves mixed layers and repeated glyphs;
    an empty symbol layer uses that glyph's active layer. Font-window rows use
    actual native selection on the current master. Qt modeless focus is ignored.
    No CurrentGlyph, selection/master writer, fgGlyph or fgPackage getter is used.
    Native calls cannot be preempted; checkpoints diagnose expiry on return.
    """
    first, second = _read(deadline), _read(deadline)
    if first != second or second.context != _document(deadline).context:
        raise ValueError(
            "Selected layers or their font/master/document changed; refresh."
        )
    _check(deadline)
    return second


def document_context(deadline: float) -> tuple:
    """Read parent/view context without resolving a changed selected glyph."""
    return _document(deadline).context
