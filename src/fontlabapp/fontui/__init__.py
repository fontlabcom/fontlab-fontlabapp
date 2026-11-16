# this_file: src/fontlabapp/fontui/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Qt controls for FontLab objects and FontParts-style fonts. Qt loads only at construction.

What it holds: the general browsers, previews, features editor and Designspace
panel, the Qt lifetime base (``lifecycle``), the pure models, the sequence
canvas, and the editors for FontParts-style fonts: font info, groups, kerning,
transform, batch and glyph sequence. ``fontlabapp.fontui.feature_blocks``
reads and writes exact VFJ feature source through Fontport.

Lazy by design: this module imports no editor module and no PythonQt. A
factory imports its module only when you call it, which keeps the FontLab 5 s
cold-import limit.

Fontport: the FontParts editors validate and apply data with ``fontlab_fontport``.
That package depends on this one, so it is an optional extra:
``pip install "fontlab-fontlabapp[fontport]"``. Without it, calling one of
those factories raises ``ImportError`` that names the extra. Everything else
here works without Fontport.

Moved back (issue 201): ``fontlab_fontport.ui`` held these editors for one
release. Fontport now has no UI; its ``ui`` package only raises ``ImportError``.
    old: ``from fontlab_fontport.ui import kerning_editor``
    new: ``from fly.ap.fontui import kerning_editor``
"""

import importlib
from collections.abc import Callable
from typing import Any

from .model import BrowserState, FontListState, outline, viewport

#: ``on_apply(font, changes)``; private so the public surface stays ``__all__``.
_ApplyCallback = Callable[[Any, Any], None]


def _load(module: str) -> Any:
    """Import ``fontlabapp.fontui.<module>`` (the editor modules name the extra)."""
    return importlib.import_module(f"{__name__}.{module}")


def _construct(cls: type, *args: Any) -> Any:
    """Build ``cls(*args)``; on failure, close the half-built widget, then re-raise.

    ``__new__`` and ``__init__`` run apart, so a constructor that fails after
    it made ``owner.widget`` still gets ``close()`` and leaks no native widget.
    """
    owner = cls.__new__(cls)
    try:
        cls.__init__(owner, *args)
    except BaseException as error:
        if hasattr(owner, "widget"):
            from fontlabapp.qt.widgets import _cleanup_failure

            _cleanup_failure(owner, error)
        raise
    return owner


def glyph_browser(
    font: Any,
    parent: Any = None,
    on_activate: Callable[..., object] | None = None,
    multiple: bool = False,
) -> Any:
    """Return an owned glyph browser handle over ``font``.

    Keep the handle alive, show ``handle.widget``, call ``refresh()`` after
    external edits and ``close()`` when done. ``on_activate`` runs for an
    activated glyph; ``multiple`` allows a multi-selection.
    """
    from .native import Browser

    return _construct(Browser, font, parent, on_activate, multiple)


def font_browser(
    fonts: Any = (), parent: Any = None, on_activate: Callable[..., object] | None = None
) -> Any:
    """Return a browser over a borrowed font list.

    ``refresh(fonts)`` updates the list when fonts open or close elsewhere.
    """
    from .fonts import FontBrowser

    return _construct(FontBrowser, fonts, parent, on_activate)


def glyph_preview(font: Any, name: str | None = None, parent: Any = None) -> Any:
    """Return an owned glyph detail preview; use ``set_glyph(name)``, ``refresh()``, ``close()``."""
    from .native import Preview

    return _construct(Preview, font, name, parent)


def features_editor(
    font: Any, parent: Any = None, on_apply: Callable[[Any, str], object] | None = None
) -> Any:
    """Return an owned feature-code editor that stages text until Apply.

    ``on_apply(font, text)`` runs once after each accepted Apply. The text is
    never compiled here.
    """
    from .features import FeaturesEditor

    return _construct(FeaturesEditor, font, parent, on_apply)


def designspace_panel(
    designspace: Any, parent: Any = None, on_location: Callable[..., object] | None = None
) -> Any:
    """Return axis sliders, fields and a source list over a designspace object.

    ``on_location`` runs when the user changes the location.
    """
    from .designspace import DesignspacePanel

    return _construct(DesignspacePanel, designspace, parent, on_location)


def font_info_editor(
    font: Any, parent: Any = None, on_apply: _ApplyCallback | None = None
) -> Any:
    """Stage font information; ``on_apply(font, changes)`` follows a good batch.

    The borrowed model needs a callable ``font.info.apply`` for editing. Other
    models are read-only. Keep the handle and call ``close()`` when done.
    """
    return _construct(_load("fontinfo").FontInfoEditor, font, parent, on_apply)


def groups_editor(
    font: Any, parent: Any = None, on_apply: _ApplyCallback | None = None
) -> Any:
    """Edit explicit groups; ``on_apply(font, groups)`` follows one good batch."""
    return _construct(_load("groups").GroupsEditor, font, parent, on_apply)


def kerning_editor(
    font: Any, parent: Any = None, on_apply: _ApplyCallback | None = None
) -> Any:
    """Inspect explicit and effective kerning pairs; edit them in one batch.

    ``on_apply(font, pairs)`` follows a good batch. Keep the handle and call
    ``close()`` when done.
    """
    return _construct(_load("kerning").KerningEditor, font, parent, on_apply)


def transform_editor(
    font: Any,
    name: str | None = None,
    parent: Any = None,
    on_change: Callable[[Any, Any], None] | None = None,
    on_invalidate: Callable[[], None] | None = None,
) -> Any:
    """Preview an affine transform of one detached UFO glyph.

    ``on_change(recipe, result)`` follows each good preview. The source font is
    never changed. Keep the handle and call ``close()`` when done.
    ``on_invalidate()`` clears linked proof before subsequent attempts; it is
    registered after the initial preview and must not calculate or publish.
    """
    if on_invalidate is not None:
        return _construct(
            _load("transform").TransformEditor, font, name, parent, on_change,
            on_invalidate,
        )
    return _construct(_load("transform").TransformEditor, font, name, parent, on_change)


def batch_panel(
    recipe: Callable[[], Any],
    parent: Any = None,
    on_finish: Callable[[list], None] | None = None,
    python: str | None = None,
) -> Any:
    """Run ``recipe()`` over source UFOs in a child Python; ``on_finish(results)``.

    The child is ``python=`` or, if that is ``None``, ``$FONTLABAPP_BATCH_PYTHON``.
    It must be Python 3.11+ with ``fontlab-fontport`` installed. With neither
    set, Start refuses to run and says so in the panel status.
    """
    return _construct(_load("batch").BatchPanel, recipe, parent, on_finish, python)


def glyph_sequence(
    font: Any,
    parent: Any = None,
    on_select: Callable[[Any, Any], None] | None = None,
) -> Any:
    """Show a text or glyph-name sequence; ``on_select(glyph_or_None, index)``.

    Fontport places the glyphs (Unicode and kerning). The canvas comes from
    ``fontlabapp.fontui.sequence_canvas``.
    """
    return _construct(_load("sequence").Sequence, font, parent, on_select)


def anchor_component_studio(font: Any, parent: Any = None) -> Any:
    """Open the shared anchor and component inspection studio for a captured font."""
    return _load("anchor_components_studio").show(font, parent)


def owned_panel_type() -> type:
    """Return the lazy owned-widget base for studio panels and their cleanup."""
    return _load("lifecycle").Owned


def app_shell(
    title: str,
    preview: str | None = None,
    tabs: Any = (),
    parent: Any = None,
    *,
    package: Callable[[], Any] | None = None,
) -> Any:
    """Return an owned studio window shell: preview pane, tabs and status line.

    ``preview`` is ``"tglyph"``, ``"tmetrics"`` or None; ``tabs`` are
    ``fontlabapp.studios.TabSpec`` values. ``show()`` sizes it to about 80% by
    75% of the screen. Writes go through ``history(label, glyphs, mutate, layers=...)``.
    """
    shell = _load("appshell").AppShell
    owner = shell.__new__(shell)
    try:
        shell.__init__(owner, title, preview, tabs, parent=parent, package=package)
    except BaseException:
        if hasattr(owner, "widget"):
            owner.close()
        raise
    return owner


def kerning_snapshot(package: Any, *, typed: bool = False) -> Any:
    """Read every master's kerning pairs and classes of a live native package.

    Returns a ``KerningSnapshot`` (``masters``, ``pairs``, ``groups``) to pass
    back as ``expected=`` to ``write_kerning``; reading changes nothing. With
    ``typed=True`` pair sides are ``(name, "glyphMode" | "groupMode")``, so a
    group and a glyph of the same name stay distinct; the default keys use the
    legacy ``"@name"`` strings for groups.
    """
    from fontlabapp.kerning.batch import snapshot_kerning

    return snapshot_kerning(package, typed=typed)


def write_kerning(package: Any, edits: Any, undo_name: str, *, expected: Any = None) -> bool:
    """Write ``{master: {pair: value or None}}`` on any masters as one named Undo step.

    Only changed masters are range-checked; the result is read back. Raises
    ValueError for an unknown master, pair or out-of-range value and when
    ``expected`` is stale. Returns False when nothing changes.
    """
    from fontlabapp.kerning.batch import write_kerning as write

    return write(package, edits, undo_name, expected=expected)


def current_font() -> Any:
    """FontLab's current font as a live Fontport font, or None."""
    return _load("tmetrics")._current_font()


def glyph_table(columns: Any, parent: Any = None, layer_column: bool = False) -> Any:
    """Return an owned sortable, filterable glyph list; ``row_selected(name, layer)``.

    ``layer_column=True`` shows each row's layer as the second column.
    """
    return _construct(_load("table").GlyphTable, columns, parent, layer_column)


def glyph_view(
    font: Any,
    parent: Any = None,
    *,
    name: str | None = None,
    layer: str | None = None,
    controls: bool = False,
    read_only: bool = False,
    label_prefix: str = "TGlyph",
    hint_check: Callable[..., Any] | None = None,
) -> Any:
    """Return an owned TGlyph glyph view (``load``, ``refresh``, ``set_overlay``, ``highlight``)."""
    cls = _load("tglyph").TGlyph
    owner = cls.__new__(cls)
    try:
        cls.__init__(
            owner, font, name, layer, parent,
            controls=controls, label_prefix=label_prefix, hint_check=hint_check, read_only=read_only,
        )
    except BaseException:
        if hasattr(owner, "widget"):
            owner.close()
        raise
    return owner


def layer_is_hinted(layer: Any) -> Any:
    """Return the ``HintState`` of a native layer (PostScript hints, TrueType data, TT hinting)."""
    return _load("hinting").layer_is_hinted(layer)


def metrics_window(font: Any = None, text: str | None = None, *, parent: Any = None) -> Any:
    """Open the standalone TMetrics window (with its own controls) for ``font``; return it."""
    return _load("tmetrics").show_tmetrics(font, text, parent=parent)


def remove_hints(layer: Any, label: str, *, glyph: Any, commit: Callable[..., Any] | None = None) -> Any:
    """Remove the PostScript hints of a native ``layer`` as one Undo step named ``label``.

    ``glyph`` owns ``layer``; ``commit(label, layers, glyphs, mutate, read_back)``
    runs the history step (``AppShell.history`` in studios). Returns the
    ``HintState`` after the write; a layer without PostScript hints is untouched.
    """
    return _load("hinting").remove_hints_with_recheck(layer, label, glyph=glyph, commit=commit)


def metrics_preview(
    font: Any,
    parent: Any = None,
    *,
    text: str | None = None,
    controls: bool = False,
    layer: str | None = None,
    label_prefix: str = "TMetrics",
    hint_check: Callable[..., Any] | None = None,
    read_only: bool = False,
) -> Any:
    """Return an owned TMetrics text preview (``set_text``, ``set_layer``, ``set_view``, ``highlight_pair``).

    ``read_only=True`` refuses every metric and kerning write (a pure proof preview).
    """
    cls = _load("tmetrics").TMetrics
    owner = cls.__new__(cls)
    try:
        cls.__init__(
            owner, font, parent, None, text,
            controls=controls, layer=layer, label_prefix=label_prefix, hint_check=hint_check,
            read_only=read_only,
        )
    except BaseException:
        if hasattr(owner, "widget"):
            owner.close()
        raise
    return owner


def category_report(shell: Any, classify: Any) -> Any:
    """Return an owned complete category XML report pane for a captured studio."""
    return _load("category_xml").category_report(shell, classify)


def show_node_editor(parent: Any = None) -> Any:
    """Open the captured-font Node Editor with its live coordinate preview."""
    return _load("node_editor").show(parent=parent)


def duplicate_nodes(mode: str) -> Any:
    """Run one of the original node-duplication policies on the current selection."""
    return _load("node_editor.session").native.duplicate_selected_nodes(mode)


def hint_tools_window(*args: Any, **kwargs: Any) -> Any:
    """Open captured-font PostScript hint tasks in the shared studio shell."""
    from .hint_tools import show

    return show(*args, **kwargs)


def raise_ascender_tab(studio: Any, *, backend: Any = None) -> Any:
    """Build the owned ascender task, closing partial construction on failure."""
    return _construct(_load("raise_ascender").RaiseAscender, studio, backend)


def outline_generators_backends() -> Any:
    """Return the named outline-generator services used by studio tasks."""
    return _load("outline_generators").backends()


def follow_history(owner: Any, callback: Callable[[], Any]) -> int:
    """Attach an owned callback to available Undo/Redo actions; Qt loads on use."""
    return _load("lifecycle").follow_history(owner, callback)


def cleanup_failed_window(owner: Any, error: BaseException) -> None:
    """Close failed construction or preserve its owner with both exceptions."""
    from fontlabapp.qt.widgets import _cleanup_failure

    _cleanup_failure(owner, error)


def show_outline_compatibility(*args: Any, **kwargs: Any) -> Any:
    """Open contour order, node statistics and guarded compatibility tasks."""
    return _load("outline_compatibility").show(*args, **kwargs)


def outline_studio(title: str, parent: Any = None, **kwargs: Any) -> Any:
    """Open the exact outline task composition for the requested studio."""
    return _load("outline_studios").show(title, parent, **kwargs)


__all__ = [
    "core_pythonqt_lab",
    "BrowserState",
    "FontListState",
    "anchor_component_studio",
    "app_shell",
    "batch_panel",
    "current_font",
    "category_report",
    "cleanup_failed_window",
    "designspace_panel",
    "duplicate_nodes",
    "features_editor",
    "font_browser",
    "follow_history",
    "font_info_editor",
    "glyph_browser",
    "glyph_preview",
    "glyph_sequence",
    "glyph_table",
    "glyph_view",
    "hint_tools_window",
    "groups_editor",
    "identity_panel",
    "identity_route",
    "identity_studio",
    "kerning_editor",
    "kerning_snapshot",
    "layer_is_hinted",
    "metrics_preview",
    "metrics_window",
    "outline",
    "owned_panel_type",
    "outline_generators_backends",
    "outline_studio",
    "remove_hints",
    "raise_ascender_tab",
    "show_outline_compatibility",
    "show_node_editor",
    "transform_editor",
    "viewport",
    "write_kerning",
]


def core_pythonqt_lab(lab_id, *, profile=None, parent=None, font=None, package=None):
    """Open one core PythonQt lab with its original named lesson profiles."""
    return _load("core_pythonqt_labs").show(
        lab_id, profile=profile, parent=parent, font=font, package=package
    )


def identity_route(*args: Any, **kwargs: Any) -> Any:
    """Describe one retained identity/feature task for a studio."""
    return _load("identity_tools").Route(*args, **kwargs)


def identity_studio(*args: Any, **kwargs: Any) -> Any:
    """Open an identity/feature studio with guarded actions and captured previews."""
    return _load("identity_tools").show(*args, **kwargs)


def identity_panel(module: str, name: str, parent: Any, *, factory_type: bool = False) -> Any:
    """Build an App-owned task panel without exposing its implementation to studios."""
    factory = getattr(importlib.import_module("fontlabapp." + module), name)
    return (factory() if factory_type else factory)(parent)
