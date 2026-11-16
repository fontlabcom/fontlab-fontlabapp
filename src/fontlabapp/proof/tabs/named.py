# this_file: src/fontlabapp/proof/tabs/named.py
# SPDX-License-Identifier: MIT
"""Open explicit named glyphs without slash-string or Unicode substitution.

Native fgSymbol/fgSymbolList construction follows the reviewed Glyport backend;
see NOTICE. Build everything before opening. Only a verified fresh target tab
may receive requestContent. Native acceptance remains pending.

Public: ``open_named_tab`` (rows of glyph names on the current master),
``open_layer_tab`` (one row of exact glyph/layer pairs) and
``open_layer_rows`` (rows of exact glyph/layer pairs with ``SPACE``
spacers and line breaks).
"""

from time import monotonic
from typing import Any

import fontlabapp.proof.tabs.text as _tab
from fontlabapp import _native


def _symbols(
    native: Any, lines: tuple[tuple[str, ...], ...], deadline: float, master: str
) -> Any:
    """Keep all named symbols and every line break, including final blank rows."""
    symbols = None
    for index, names in enumerate(lines):
        _tab._check(deadline)
        if isinstance(names, str):
            raise TypeError("A proof row must contain glyph names, not a text string.")
        parts = [native.fgSymbolList("\n")] if index else []
        row = []
        for name in names:
            _tab._check(deadline)
            if not isinstance(name, str) or not name:
                raise ValueError("Every proof glyph needs a nonempty name.")
            symbol = native.fgSymbol(name)
            symbol.layerName = master
            row.append(symbol)
        if row:
            parts.append(native.fgSymbolList(row))
        for part in parts:
            if symbols is None:
                symbols = part
            else:
                symbols.append(part)
    _tab._check(deadline)
    return native.fgSymbolList("") if symbols is None else symbols


def open_named_tab(
    lines: tuple[tuple[str, ...], ...],
    *,
    expected_id: int,
    master: str,
    deadline: float | None = None,
) -> None:
    """Open a fresh empty native tab, verify its identity/font, then set names.

    Keep the captured current master explicitly in every symbol layerName.
    No Unicode lookup, slash parsing, missing-name filtering or master switch. Any build failure opens no tab. Creation/populate
    failure can leave a new tab; no atomic UI rollback is claimed. Shared App
    preflight preserves captured activation flags and checks source-font identity.
    """
    limit = monotonic() + 2.0 if deadline is None else deadline
    if not isinstance(master, str):
        raise TypeError("The source master name must be a string.")
    native = _native("fontlab")
    symbols = _symbols(native, lines, limit, master)

    _open_symbols(native, symbols, expected_id, master, limit)


def open_layer_tab(
    layers: tuple[tuple[str, str], ...],
    *,
    expected_id: int,
    master: str,
    deadline: float | None = None,
) -> None:
    """Open exact glyph/layer occurrences in a verified fresh native tab.

    Every pair is (glyph name, exact foreground layer name). Preserve auxiliary
    layers, mixed masters and repeated winners without Unicode/slash substitution.
    Validate the complete immutable request before native symbol allocation.
    The separate master argument fences the current source context; it does not
    overwrite each symbol's requested layer. Native qualification remains open.
    """
    limit = monotonic() + 2.0 if deadline is None else deadline
    if not isinstance(master, str):
        raise TypeError("The source master name must be a string.")
    if type(layers) is not tuple:
        raise ValueError("Named layer occurrences must be an immutable tuple.")
    for row in layers:
        _tab._check(limit)
        if (
            type(row) is not tuple
            or len(row) != 2
            or any(not isinstance(v, str) or not v for v in row)
        ):
            raise ValueError("Every occurrence needs exact nonempty glyph/layer names.")
    native = _native("fontlab")
    values = []
    for name, layer in layers:
        _tab._check(limit)
        symbol = native.fgSymbol(name)
        symbol.layerName = layer
        values.append(symbol)
    _tab._check(limit)
    _open_symbols(native, native.fgSymbolList(values), expected_id, master, limit)


#: One item of ``open_layer_rows``: (glyph name, exact layer name), or ``SPACE``.
RowItem = tuple[str | None, str]
#: The spacer item of ``open_layer_rows``: one space between two layers.
SPACE: RowItem = (None, "")


def _check_rows(rows: Any, limit: float) -> None:
    """Raise ValueError unless ``rows`` is a tuple of tuples of valid items."""
    if type(rows) is not tuple:
        raise ValueError("Layer rows must be an immutable tuple.")
    for row in rows:
        _tab._check(limit)
        if type(row) is not tuple:
            raise ValueError("Every layer row must be an immutable tuple.")
        for item in row:
            if item == SPACE and type(item) is tuple:
                continue
            if (
                type(item) is not tuple
                or len(item) != 2
                or any(not isinstance(v, str) or not v for v in item)
            ):
                raise ValueError(
                    "Every row item needs exact nonempty glyph/layer names, or (None, '') for a space."
                )


def _check_layers(
    rows: tuple[tuple[RowItem, ...], ...], expected_id: int, limit: float
) -> None:
    """Raise ValueError when a requested glyph or layer does not exist in the source font."""
    package = _tab.current_package(expected_id)
    if package is None:
        raise ValueError("The source font changed or closed; run the proof again.")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        for name, layer_name in row:
            _tab._check(limit)
            if name is None or (name, layer_name) in seen:
                continue
            seen.add((name, layer_name))
            glyph = package.findName(name)
            layer = (
                None if glyph is None or glyph.isNull else glyph.findLayer(layer_name)
            )
            if layer is None or layer.isNull:
                raise ValueError(f"{name} has no layer {layer_name}; no tab opened.")


def open_layer_rows(
    rows: tuple[tuple[RowItem, ...], ...],
    *,
    expected_id: int,
    master: str,
    deadline: float | None = None,
) -> None:
    """Open exact glyph/layer occurrences in rows, in ONE verified fresh native tab.

    What: each row is a tuple of items. An item is ``(glyph name, exact
    layer name)``, or ``SPACE`` (``(None, "")``) for one space. Rows are
    separated by one line break; an empty row keeps its line, as in
    ``open_named_tab``. Use it for stacked or side-by-side layer
    comparisons (Master Text Comparison).

    How: the complete immutable request is validated first. Then every
    requested layer must exist in the font ``expected_id`` (``flPackage.id``,
    the current font). Only then are native symbols built: a layer item is an
    ``fgSymbol`` with its own ``layerName``; a space is the text symbol list
    ``fgSymbolList(" ")`` and a line break ``fgSymbolList("\\n")``, the same
    text form that ``open_named_tab`` uses for line breaks. The tab opens
    through the shared fresh-tab fence (``_open_symbols``). ``master`` fences
    the current source master; it does not overwrite the layer of an item.

    Why: scripts must not build ``fgSymbol`` lists or call ``requestContent``
    themselves. Any failure before the tab opens opens no tab. Native
    qualification (space text symbol, layer per symbol) remains open.
    """
    limit = monotonic() + 2.0 if deadline is None else deadline
    if not isinstance(master, str):
        raise TypeError("The source master name must be a string.")
    _check_rows(rows, limit)
    _check_layers(rows, expected_id, limit)
    native = _native("fontlab")
    parts: list[Any] = []
    for index, row in enumerate(rows):
        if index:
            parts.append(native.fgSymbolList("\n"))
        parts.extend(_row_parts(native, row, limit))
    _tab._check(limit)
    _open_symbols(native, _join(native, parts), expected_id, master, limit)


def _row_parts(native: Any, row: tuple[RowItem, ...], limit: float) -> list[Any]:
    """Return the symbol lists of one row: runs of layer symbols, a text list per space."""
    parts: list[Any] = []
    batch: list[Any] = []
    for name, layer_name in row:
        _tab._check(limit)
        if name is None:
            if batch:
                parts.append(native.fgSymbolList(batch))
                batch = []
            parts.append(native.fgSymbolList(" "))
            continue
        symbol = native.fgSymbol(name)
        symbol.layerName = layer_name
        batch.append(symbol)
    if batch:
        parts.append(native.fgSymbolList(batch))
    return parts


def _join(native: Any, parts: list[Any]) -> Any:
    """Append every part to the first; no part gives an empty symbol list."""
    if not parts:
        return native.fgSymbolList("")
    symbols = parts[0]
    for part in parts[1:]:
        symbols.append(part)
    return symbols


def _open_symbols(
    native: Any, symbols: Any, expected_id: int, master: str, limit: float
) -> None:
    """Share deadline, fresh-target population and source/activation restoration."""

    def populate() -> None:
        if monotonic() >= limit:
            raise TimeoutError(
                "Named-tab creation exceeded its deadline; a new tab may remain."
            )
        native.flItems().requestContent(symbols, 0)
        if monotonic() >= limit:
            raise TimeoutError(
                "Named-tab population exceeded its deadline; a new tab may remain."
            )

    _tab._open_tab(
        "",
        expected_id=expected_id,
        deadline=limit,
        populate=populate,
        expected_master=master,
    )


__all__ = ["SPACE", "RowItem", "open_layer_rows", "open_layer_tab", "open_named_tab"]
