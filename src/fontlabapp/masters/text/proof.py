# this_file: src/fontlabapp/masters/text/proof.py
# SPDX-License-Identifier: Apache-2.0
"""Fresh exact-symbol master proof, with full staging and bounded restoration.

Official bindings: pyfgsymbol.cpp numeric/name constructor and name/layerName/
unicode; pyfgsymbollist.cpp list constructor/symbols; pyfltextblock.cpp symbolList.
Reuse established fresh/active-model contracts without weakening named_tab.
No native binding fallback: 9792 qualification remains a material acceptance hold.
"""

from collections.abc import Callable
from time import monotonic
from typing import Any
from fontlabapp import _native
from fontlabapp.glyphs.case_coverage.cleanup import PENDING, restore
from fontlabapp.glyphs.case_coverage.proof import _remember as remember
from fontlabapp.core.native_tabs import canvases
from fontlabapp.glyphs.case_coverage.views import active_model
from fontlabapp.masters.text.capture import Opening, validate, sources
from fontlabapp.masters.text.model import Comparison, checkpoint
from fontlabapp.masters.text.sender import sender, PENDING as PENDING_SENDERS


def signature(symbols: Any, check: Callable) -> tuple:
    """Read every occurrence's exact glyph/layer and delimiter Unicode scalar."""
    result = []
    for symbol in symbols.symbols():
        check()
        name = str(symbol.name)
        result.append((name, str(symbol.layerName), 0 if name else int(symbol.unicode)))
    check()
    return tuple(result)


def verify_content(symbols: Any, expected: tuple, check: Callable) -> None:
    """Detect missing/repeated/reordered glyphs AND missing trailing delimiters."""
    if signature(symbols, check) != expected:
        raise ValueError(
            "FontLab did not deliver the exact comparison content, including delimiters."
        )


def stage(
    native: Any, opening: Opening, source: Any, comparison: Comparison, check: Callable
) -> tuple:
    """Allocate every exact symbol and snapshot per-occurrence native layer IDs."""
    values, identities, expected = [], [], []
    for index, row in enumerate(comparison.rows):
        check()
        if index:
            values.append(native.fgSymbol(10))
            expected.append(("", "", 10))
        for name, master in row:
            check()
            if name is None:
                symbol = native.fgSymbol(32)
                expected.append(("", "", 32))
            else:
                glyph = source.package.findName(name)
                layer = (
                    None if glyph is None or glyph.isNull else glyph.findLayer(master)
                )
                check()
                if layer is None or layer.isNull:
                    raise ValueError(
                        f"{name} has no exact layer {master}; no proof opened."
                    )
                if master not in opening.masters:
                    raise ValueError("A comparison master is outside the opening font.")
                symbol = native.fgSymbol(name)
                symbol.layerName = master
                check()
                if str(symbol.name) != name or str(symbol.layerName) != master:
                    raise ValueError(
                        "FontLab cannot represent this exact glyph/layer name; proof held."
                    )
                identities.append((name, int(glyph.id), master, int(layer.id)))
                expected.append((name, master, 0))
            values.append(symbol)
    check()
    symbols = native.fgSymbolList(values)
    check()
    verify_content(symbols, tuple(expected), check)
    return symbols, tuple(identities), tuple(expected)


def _layers(source: Any, identities: tuple, check: Callable) -> None:
    """Fence every occurrence again immediately before native content population."""
    for name, glyph_id, master, layer_id in identities:
        check()
        glyph = source.package.findName(name)
        layer = None if glyph is None or glyph.isNull else glyph.findLayer(master)
        check()
        if (
            glyph is None
            or int(glyph.id) != glyph_id
            or layer is None
            or layer.isNull
            or int(layer.id) != layer_id
        ):
            raise ValueError(
                "A comparison glyph or exact layer changed; reopen this panel."
            )


def fresh(
    native: Any,
    workspace: Any,
    opening: Opening,
    source: Any,
    symbols: Any,
    identities: tuple,
    expected: tuple,
    previous_ids: set,
    check: Callable,
    cleanup: Callable,
    deadline: float,
) -> None:
    """Preserve the existing fresh-only guard, re-fencing layers after creation."""
    check()
    main = native.MainWindow()
    if main is None:
        raise ValueError("FontLab main window is unavailable; no comparison opened.")
    with sender(_native("PythonQt").QtGui, main, check, cleanup) as emitter:
        check()
        emitter.setText("")
        check()
        block = active_model(native, workspace)
        if (
            block is None
            or int(block.id) in previous_ids
            or int(block.package.id) != opening.identity
        ):
            raise ValueError(
                "No new exact comparison target became active; existing tabs were not populated."
            )
        block_id = int(block.id)
        if workspace.activeFontPanel is not None:
            raise ValueError(
                "The new comparison Glyph view is not active; no content was replaced."
            )
        validate(opening, deadline - 0.5, check=check)
        _layers(source, identities, check)
        check()
        native.flItems().requestContent(symbols, 0)
        check()
        actual = active_model(native, workspace)
        if (
            actual is None
            or int(actual.id) != block_id
            or int(actual.package.id) != opening.identity
            or workspace.activeFontPanel is not None
        ):
            raise ValueError(
                "The exact comparison target changed during delivery; proof held."
            )
        verify_content(actual.symbolList(), expected, check)


def open_proof(
    opening: Opening,
    comparison: Comparison,
    *,
    deadline: float,
    cancelled: Callable = lambda: False,
) -> None:
    """Open one NEW proof; no source/master selection, history or preference writes.

    All registered shapes are snapshotted, including another font's old rendered
    view. No set_active_font/setMaster operation is used. The new active proof
    is the intended UI change; cleanup context_pending=False restores shapes
    without reactivating the prior view. Source/master is rechecked after send.
    Half a second is reserved for cleanup; a failed cleanup retains native handles
    in the existing shared PENDING fence and refuses subsequent proof requests.
    Synchronous getters/setters are nonpreemptible; check on return.
    """
    check = lambda: checkpoint(deadline - 0.5, monotonic, cancelled)
    cleanup = lambda: checkpoint(deadline, monotonic, lambda: False)
    check()
    if PENDING or PENDING_SENDERS:
        raise ValueError(
            "A previous proof cleanup is incomplete; recover retained cleanup before retrying."
        )
    source = validate(opening, deadline - 0.5, check=check)
    native = _native("fontlab")
    workspace = native.flWorkspace.instance()
    symbols, identities, expected = stage(native, opening, source, comparison, check)
    previous_ids = set()
    for canvas in canvases(native, workspace):
        check()
        for block in canvas.textBlocks():
            check()
            previous_ids.add(int(block.id))
    records = {}
    for record in sources(deadline - 0.5, check):
        check()
        records[record.identity] = record
    states = remember(records, check)
    check()
    errors = []
    try:
        validate(opening, deadline - 0.5, check=check)
        _layers(source, identities, check)
        fresh(
            native,
            workspace,
            opening,
            source,
            symbols,
            identities,
            expected,
            previous_ids,
            check,
            cleanup,
            deadline,
        )
        check()
        block = active_model(native, workspace)
        if (
            block is None
            or int(block.package.id) != opening.identity
            or int(block.id) in previous_ids
        ):
            raise ValueError(
                "The exact fresh comparison target is unavailable; proof held."
            )
        verify_content(block.symbolList(), expected, check)
        validate(opening, deadline - 0.5, check=check)
        _layers(source, identities, check)
    except BaseException as error:
        errors.append(error)
    try:
        restore(states, workspace, None, source, None, cleanup, context_pending=False)
    except BaseException as error:
        errors.append(error)
    if len(errors) > 1:
        raise BaseExceptionGroup(
            "Comparison proof and shape restoration failed.", errors
        )
    if errors:
        raise errors[0]
