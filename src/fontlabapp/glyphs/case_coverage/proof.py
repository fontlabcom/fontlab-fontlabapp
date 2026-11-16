# this_file: src/fontlabapp/glyphs/case_coverage/proof.py
# SPDX-License-Identifier: Apache-2.0
"""Exact FontLab proof targets, explicit ambiguity and context restoration.

Source: pyflworkspace.cpp canvases/getActiveCanvas/setActiveCanvas; typed
flCanvas.textBlocks; flItems.requestContent(fgSymbolList,int). Active block
normalization is capability-checked: flTextBlockItem and flTextBlock identities
are distinct. Never cast an item to a model or infer active block from order.
Installed native qualification remains required, including multi-block refusal.
"""

from collections.abc import Callable
from time import monotonic
from typing import Any
from fontlabapp import _native
from fontlabapp.glyphs.case_coverage.model import Options, checkpoint
from fontlabapp.glyphs.case_coverage.cleanup import restore as _restore, PENDING
from fontlabapp.glyphs.case_coverage.capture import Snapshot
from fontlabapp.glyphs.case_coverage.targets import Target, choose
from fontlabapp.anchors.crossfont.capture import fonts
from fontlabapp.glyphs.case_coverage.views import (
    active_model as _active_model,
    targets as _targets,
    fresh as _fresh,
    verify as _verify,
)
from fontlabapp.core.scripting import current_package


def _stage(native: Any, snapshot: Snapshot, sources: dict, check: Callable) -> dict:
    """Validate every exact layer and allocate all named symbols before activation."""
    staged = {}
    for record in snapshot.fonts:
        check()
        source = sources.get(record.identity)
        if (
            source is None
            or source.fg_id != record.fg_id
            or str(source.package.master) != record.master
        ):
            raise ValueError("A proof font or master changed or closed; run again.")
        symbols, layers, expected = [], [], []
        for name in record.report["proof"]:
            check()
            glyph = source.package.findName(name)
            layer = (
                None
                if glyph is None or glyph.isNull
                else glyph.findLayer(record.master)
            )
            if layer is None or layer.isNull:
                raise ValueError(
                    f"{name} has no exact layer {record.master}; no proof opened."
                )
            symbol = native.fgSymbol(name)
            symbol.layerName = record.master
            symbols.append(symbol)
            layers.append((name, record.master, int(layer.id)))
            expected.append((name, record.master))
        staged[record.identity] = (
            native.fgSymbolList(symbols),
            tuple(layers),
            tuple(expected),
        )
    check()
    return staged


def _remember(sources: dict, check: Callable) -> dict:
    """Snapshot complete registered shape activation without native glyph mirrors."""
    states = {}
    for source in sources.values():
        check()
        for name in source.names:
            check()
            glyph = source.package.findName(name)
            if glyph is None or glyph.isNull:
                raise ValueError("A proof glyph disappeared during preflight.")
            for layer in glyph.layers:
                check()
                for shape in layer.shapes:
                    check()
                    states.setdefault(int(shape.id), (shape, bool(shape.active)))
    check()
    return states


def open_proofs(
    snapshot: Snapshot,
    options: Options,
    *,
    deadline: float,
    cancelled: Callable = lambda: False,
    choices: dict | None = None,
) -> None:
    """Preflight the entire request before any UI activation or content change.

    Known active or sole targets reuse automatically. Ambiguous inactive views
    require explicit nonmodal caller choice. A selected multi-block canvas must
    expose the exact active model; otherwise activate that block and retry.
    All symbols carry exact master names; missing layers refuse the whole batch.
    Half a second is reserved for bounded cleanup. Cancellation starts recovery;
    expiration stops setters and retains an explicit incomplete-cleanup fence. View creation/population is not an atomic UI transaction.
    """
    action_deadline = deadline - 0.5
    check = lambda: checkpoint(action_deadline, monotonic, cancelled)
    cleanup_check = lambda: checkpoint(deadline, monotonic, lambda: False)
    check()
    if PENDING:
        raise ValueError(
            "A previous Case Coverage cleanup is incomplete; recover it before proofing again."
        )
    has_proof = False
    for record in snapshot.fonts:
        check()
        has_proof = has_proof or bool(record.report["proof"])
    if not has_proof:
        return
    if current_package(snapshot.current_id) is None:
        raise ValueError("The current source font changed or closed; run again.")
    native, tool = _native("fontlab"), _native("fontpr")
    workspace = native.flWorkspace.instance()
    sources = {}
    for source in fonts(action_deadline, checkpoint=check):
        check()
        sources[source.identity] = source
    original = sources.get(snapshot.current_id)
    if original is None:
        raise ValueError("The original font closed; run again.")
    previous = workspace.getActiveCanvas()
    previous_panel = workspace.activeFontPanel
    active = _active_model(native, workspace)
    targets, handles = _targets(native, workspace, snapshot.fonts, check)
    selected = choose(
        snapshot.fonts,
        targets,
        None if active is None else int(active.id),
        options.reuseTab,
        choices or {},
        check=check,
    )
    previous_ids = set()
    for target in targets:
        check()
        previous_ids.add(target.block_id)
    staged = _stage(native, snapshot, sources, check)
    states = _remember(sources, check)
    check()
    try:
        for identity, target in selected.items():
            check()
            source = sources[identity]
            live = {}
            for font in fonts(action_deadline, checkpoint=check):
                check()
                live[font.identity] = font
            if identity not in live or live[identity].fg_id != source.fg_id:
                raise ValueError("A proof font closed before activation; run again.")
            if target is not None:
                current_targets, _ = _targets(native, workspace, snapshot.fonts, check)
                if target not in current_targets:
                    raise ValueError(
                        "The selected proof target changed or closed; Refresh and retry."
                    )
            tool.call("set_active_font", font_id=source.fg_id)
            check()
            symbols, layers, expected = staged[identity]
            for name, master, layer_id in layers:
                check()
                glyph = source.package.findName(name)
                layer = None if glyph is None else glyph.findLayer(master)
                if (
                    layer is None
                    or layer.isNull
                    or int(layer.id) != layer_id
                    or str(source.package.master) != master
                ):
                    raise ValueError("A proof layer or master changed; run again.")
            if target is None:
                _fresh(
                    native,
                    workspace,
                    identity,
                    symbols,
                    expected,
                    previous_ids,
                    check,
                    _native("PythonQt").QtGui,
                )
            else:
                canvas, block = handles[(target.canvas_id, target.block_id)]
                workspace.setActiveCanvas(canvas)
                check()
                actual = _active_model(native, workspace)
                if (
                    actual is None
                    or int(actual.id) != target.block_id
                    or int(actual.package.id) != identity
                    or workspace.getActiveCanvas().id != target.canvas_id
                    or current_package(identity) is None
                ):
                    raise ValueError(
                        "The selected proof target is not active. Activate its text block, Refresh and retry; no content was replaced there."
                    )
                check()
                if workspace.activeFontPanel is not None:
                    raise ValueError(
                        "Activate the selected Glyph view before proofing; the Font window is active."
                    )
                check()
                native.flItems().requestContent(symbols, 0)
                _verify(
                    native,
                    workspace,
                    identity,
                    expected,
                    check,
                    block_id=target.block_id,
                )
            check()
    finally:
        _restore(
            states,
            workspace,
            previous,
            original,
            tool,
            cleanup_check,
            panel=previous_panel,
        )
