# this_file: src/fontlabapp/fontui/hinting.py
# SPDX-License-Identifier: Apache-2.0
"""Hint guard for the studio widgets: read a layer's hint state, remove PostScript hints.

What: ``layer_is_hinted(layer)`` returns a ``HintState`` from exactly the three
native flags that Fontport's outline guard reads (``hasHints``, ``hasTTData``,
``hasTTH``; ``fontlab_fontport.host`` refuses outline edits when any is set).
TMetrics and TGlyph check it before outline or sidebearing writes. Advance
width and kerning stay editable on a hinted layer.

``remove_hints_with_recheck(layer, label, glyph=..., package=...)`` removes the
PostScript hints of that one layer as ONE named Undo step, with
``flLayer.removeHints(True, True)`` through ``core.history.glyphs.commit``, then
reads the state again. ``removeHints`` does not clear TrueType data and there
is no TrueType remover, so outline edits stay off while TrueType data remains.

The module imports nothing native at load time. Offline tests do not prove
native FontLab behaviour.
"""

from collections.abc import Callable
from typing import Any, NamedTuple

PS_TEXT = (
    "This layer has PostScript hints. Outline and sidebearing edits are off to protect them. "
    "Advance width and kerning still work."
)
TT_TEXT = (
    "This layer has TrueType hinting data. Outline and sidebearing edits are off to protect it. "
    "Advance width and kerning still work."
)
TT_REMAINS_TEXT = "TrueType data remains; outline edits stay off."
REMOVED_TEXT = "PostScript hints removed; outline edits are on."


class HintState(NamedTuple):
    """The hint flags of one layer; true when any flag is set."""

    ps_hints: bool = False
    tt_data: bool = False
    tt_hinting: bool = False

    def __bool__(self) -> bool:
        return self.ps_hints or self.tt_data or self.tt_hinting

    @property
    def tt(self) -> bool:
        """True when TrueType data or TrueType hinting is present."""
        return self.tt_data or self.tt_hinting

    def text(self) -> str:
        """The status text for this state ("" when the layer is not hinted)."""
        if self.ps_hints:
            return PS_TEXT
        return TT_TEXT if self.tt else ""


def layer_is_hinted(layer: Any) -> HintState:
    """Return the ``HintState`` of ``layer`` (``None`` is not hinted)."""
    if layer is None:
        return HintState()
    return HintState(
        bool(getattr(layer, "hasHints", False)),
        bool(getattr(layer, "hasTTData", False)),
        bool(getattr(layer, "hasTTH", False)),
    )


def native_layer(package: Any, name: str, layer: str | None = None) -> Any:
    """The live ``flLayer`` of glyph ``name`` on ``layer`` (default master) in ``package``, or None.

    Uses only ``findName``/``findLayer``/``isNull``/``defaultMaster``, the lookup
    Fontport's host uses; no other native attribute is read.
    """
    if package is None:
        return None
    glyph = package.findName(name)
    if glyph is None or glyph.isNull:
        return None
    target = glyph.findLayer(layer or package.defaultMaster)
    return None if target is None or target.isNull else target


def hint_state_of(package: Any, name: str, layer: str | None = None) -> HintState | None:
    """``layer_is_hinted`` of that live layer; None when the package, glyph or layer is absent."""
    target = native_layer(package, name, layer)
    return None if target is None else layer_is_hinted(target)


def package_of(font: Any) -> Any:
    """The live FontLab package behind a Fontport-backed ``font``, or None (detached or no host)."""
    font_id = getattr(getattr(font, "_backend", None), "font_id", None)
    if not isinstance(font_id, int):
        return None
    try:
        import fontlab
    except ImportError:
        return None
    package = fontlab.flWorkspace.instance().findPackageId(font_id)
    return None if package is None or package.isNull else package


def font_hint_check(font: Any) -> Callable[[str, str | None], HintState | None]:
    """The default ``hint_check(name, layer)`` of TMetrics and TGlyph over ``font``.

    It resolves the live package at every call, so a closed or swapped font
    reads as unhinted (None) instead of keeping a stale native pointer.
    """
    return lambda name, layer: hint_state_of(package_of(font), name, layer)


def recheck_text(state: HintState) -> str:
    """Status text after a removal: TrueType remains, still hinted, or removed."""
    if state.ps_hints:
        return PS_TEXT
    return TT_REMAINS_TEXT if state.tt else REMOVED_TEXT


def _default_commit(package: Any) -> Callable[..., Any]:
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - package __getattr__ is native

    def commit(label: str, layers: list[Any], glyphs: list[Any], mutate: Any, read_back: Any) -> Any:
        return history.commit(
            label, layers, glyphs, mutate,
            operation="geometry", facts=history.scan_auto_facts(package), read_back=read_back,
        )  # fmt: skip

    return commit


def remove_hints_with_recheck(
    layer: Any, label: str, *, glyph: Any, package: Any = None, commit: Callable[..., Any] | None = None
) -> HintState:
    """Remove the PostScript hints of ``layer`` as one Undo step named ``label``; re-check.

    ``glyph`` owns ``layer``. ``commit(label, layers, glyphs, mutate, read_back)``
    runs the history step (default: ``core.history.glyphs.commit`` with fresh
    auto facts of ``package``; ``AppShell.history`` supplies its own). A layer
    without PostScript hints makes no history call. Return the state after the
    write; refusals and partial writes raise from ``commit``.
    """
    from fontlabapp.hints.postscript import hint_counts

    if not layer_is_hinted(layer).ps_hints:
        return layer_is_hinted(layer)

    def mutate() -> None:
        layer.removeHints(True, True)

    def read_back() -> list[str]:
        horizontal, vertical = hint_counts(layer)
        if horizontal or vertical:
            return [f"{glyph.name}: {horizontal} horizontal and {vertical} vertical hints remain"]
        return []

    run = commit if commit is not None else _default_commit(package)
    run(label, [layer], [glyph], mutate, read_back)
    return layer_is_hinted(layer)
