# this_file: src/fontlabapp/core/scripting.py
"""Access the current native font lazily and select report results safely.

Import outside FontLab is supported; call these helpers inside FontLab scripts.
Selection changes only the Font window selection, never glyph geometry.
"""

from collections.abc import Callable, Iterable
from time import monotonic
from typing import Any

from fontlabapp import _native


def current_package(expected_id: int | None = None) -> Any | None:
    """Return the current non-null package, optionally matching a scanned id.

    A missing or changed font returns None so modeless reports can reject stale
    results without accessing fgPackage or creating application state.
    """
    package = _native("fontlab").flWorkspace.instance().currentPackage
    if package is None or package.isNull:
        return None
    if expected_id is not None and package.id != expected_id:
        return None
    return package


def font_id(package: Any) -> int:
    """Return the ``font_id`` that FontLab's fontpr tools need for ``package``.

    What: ``int(package.fgId)``, the FontGate id of the package.
    Why: fontpr finds a font by its FontGate id (``MCPTools::findPackage``
    -> ``flWorkspace::findPackageId`` compares ``fgId``, source
    ``mcptools.cpp:1025-1035``, ``flworkspace.cpp:1278-1287``), and
    ``get_fonts`` reports that id. ``package.id`` is a different id (the
    flObject id). With ``package.id`` a tool fails with "Font id not
    found", or, when the ids collide, reads or writes ANOTHER open font.
    Use: ``fontpr.call("get_font_info", font_id=scripting.font_id(package))``.
    Keep ``package.id`` for ``current_package(expected_id)`` and the other
    identity guards; those compare ``flPackage.id``.
    """
    return int(package.fgId)


def select_glyphs(
    names: Iterable[str], *, package_id: int, add: bool = False
) -> list[str]:
    """Select exactly the requested names in the matching current Font window.

    The optional add flag selects only missing names without clearing selection.
    Validate every requested name before any write; stale or missing fonts and
    unknown names raise ValueError. Return actual selected names in font order.
    Activate the regular Font window before selecting. A Glyph window may leave
    readable font/selection data while legacy selection writers would crash.
    Native errors propagate to the caller's guarded UI slot. Completed additions
    remain selected if a later addition fails; the prior selection is not cleared.
    Replacement mode still clears first. Call no refresh:
    ``FL.fl.Unselect``/``Select`` repaint their cells, and ``UpdateAll()``
    queued glyph ids (FontLab 9.0.9790, issue 122 M1; FontLab issue 8537).
    """
    if current_package(package_id) is None:
        raise ValueError("The scanned font is no longer current; refresh the report.")
    wanted = set(names)
    fl = _native("FL").fl
    font = fl.font
    available = [font[i].name for i in range(len(font))]
    unknown = wanted.difference(available)
    if unknown:
        raise ValueError(f"Unknown glyph names: {sorted(unknown)!r}")
    if add:
        wanted.difference_update(
            name for index, name in enumerate(available) if fl.Selected(index)
        )
    _require_selection_window(package_id)
    if not add:
        fl.Unselect()
    for index, name in enumerate(available):
        if name in wanted:
            fl.Select(index)
    return [name for index, name in enumerate(available) if fl.Selected(index)]


def _require_selection_window(package_id: int) -> None:
    """Fail closed before legacy writes when Font-window context is unreadable.

    FontLab9784 clears activeFontPanel on Glyph-window activation (fl#8528).
    A regular FontWindow has a YFrameWindow ancestor; docked or unknown panels
    are not accepted. Retain transient PythonQt wrappers throughout the bounded
    parent traversal so Python cannot reuse their ids during cycle detection.
    """
    try:
        panel = _native("fontlab").flWorkspace.instance().activeFontPanel
        if panel is not None and panel.inherits("FontWindow"):
            ancestors = [panel]
            seen = set()
            for _ in range(16):
                panel = panel.parentWidget()
                if panel is None:
                    break
                ancestors.append(panel)
                if id(panel) in seen:
                    break
                seen.add(id(panel))
                if panel.inherits("YFrameWindow"):
                    if current_package(package_id) is not None:
                        return
                    break
    except Exception as error:
        raise ValueError("Activate the Font window before selecting glyphs.") from error
    raise ValueError("Activate the Font window before selecting glyphs.")


def connect_guarded(dialog: Any, signal: Any, callback: Callable[..., Any]) -> None:
    """Retain a plain Python slot and contain errors at the PythonQt boundary."""

    def guarded(*args: Any) -> None:
        try:
            callback(*args)
        except Exception as error:  # noqa: BLE001 - native slots must contain errors
            dialog.slot_error = repr(error)
            label = getattr(dialog, "status", None)
            if label is not None:
                label.setText("Error: " + dialog.slot_error)

    signal.connect(guarded)
    dialog._connections.append((signal, guarded))


def close_script_dialog(
    dialog: Any,
    event: Any,
    key: str,
    *,
    timers: Iterable[Any] = (),
    children: Iterable[Any] = (),
) -> None:
    """Release only explicitly owned resources, then defer this dialog's deletion."""
    import sys
    from contextlib import suppress

    from fontlabapp.core.completion import stop

    stop(dialog)

    for timer in timers:
        timer.stop()
    for signal, slot in dialog._connections:
        with suppress(Exception):
            signal.disconnect(slot)
    dialog._connections.clear()
    for child in children:
        child.close()
        child.deleteLater()
    windows = getattr(sys, "_fontlab_samples", {})
    if windows.get(key) is dialog:
        windows.pop(key)
    _native("PythonQt").QtGui.QDialog.closeEvent(dialog, event)
    dialog.deleteLater()


def show_script_dialog(dialog_type: Callable[[Any], Any], key: str) -> Any:
    """Replace only a safely closed owner; retain and raise a diagnosed refusal.

    An old dialog whose native widget is already destroyed counts as gone."""
    import sys

    windows = sys.__dict__.setdefault("_fontlab_samples", {})
    old = windows.get(key)
    if old is not None:
        try:
            closed = old.close()
        except ValueError as error:
            if "destroyed" not in str(error):
                windows[key] = old
                raise
            # PythonQt: the wrapper outlived its QWidget (deleteLater, close-on-delete).
            closed = True
        except Exception:
            windows[key] = old
            raise
        if closed is False:
            windows[key] = old
            old.show()
            old.raise_()
            return old
        if windows.get(key) is old:
            windows.pop(key)
    dialog = dialog_type(_native("fontlab").MainWindow())
    windows[key] = dialog
    dialog.setWindowFlags(
        dialog.windowFlags() | _native("PythonQt").QtCore.Qt.WindowStaysOnTopHint
    )
    dialog.show()
    dialog.raise_()
    return dialog


_FONT_INFO_TEXT = frozenset(
    (
        "familyName",
        "styleName",
        "openTypeNameDesigner",
        "copyright",
        "openTypeNameVersion",
        "note",
    )
)
_FONT_INFO_NUMBERS = frozenset(
    (
        "ascender",
        "descender",
        "xHeight",
        "capHeight",
        "openTypeOS2TypoAscender",
        "openTypeOS2TypoDescender",
        "openTypeOS2TypoLineGap",
        "openTypeHheaAscender",
        "openTypeHheaDescender",
        "openTypeHheaLineGap",
        "openTypeOS2WinAscent",
        "openTypeOS2WinDescent",
        "versionMajor",
        "versionMinor",
    )
)


def _font_info_value(field: str, value: Any) -> None:
    """Reject unsupported fields and nonfinite/out-of-range Font Info values."""
    import math

    if field in _FONT_INFO_TEXT:
        if not isinstance(value, str):
            raise ValueError(f"{field} requires text.")
        if "\x00" in value:
            raise ValueError(f"{field} must not contain a null character.")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError(f"{field} must contain valid Unicode text.") from error
        return
    if field not in _FONT_INFO_NUMBERS:
        raise ValueError(f"Unsupported Font Info field: {field}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} requires a finite number.")  # noqa: TRY004 - form validation contract
    low, high = -32768, 32767
    if field in ("versionMajor", "versionMinor"):
        low, high = 0, 65535 if field == "versionMajor" else 999
        if not isinstance(value, int):
            raise ValueError(f"{field} requires an integer.")
    if field in ("openTypeOS2WinAscent", "openTypeOS2WinDescent"):
        low, high = 0, 65535
    if not low <= value <= high or not math.isfinite(value):
        raise ValueError(f"{field} must be between {low} and {high}.")


def write_font_info(
    package: Any,
    changes: Iterable[tuple[str | None, str, Any, Any]],
    *,
    undo_name: str,
) -> dict[str, int]:
    """Apply an explicit Font Info plan after checking every old value and master.

    This bounded helper supports the six script-menu Font Info tools. It uses
    Fontport's measured package plus masters-container history protocol; that
    protocol may expose an additional no-op Undo checkpoint. Native Undo and
    persistence acceptance remains the caller's responsibility. No glyph/layer
    is notified. A setter failure rolls back every attempted field, including a
    setter that wrote before raising. Rollback failure is reported explicitly.
    """
    active = current_package()
    if active is None or active.id != package.id:
        raise ValueError("The preview font is no longer current; reopen the tool.")
    if not isinstance(undo_name, str) or not undo_name.strip():
        raise ValueError("A nonempty Undo name is required.")
    plan = list(changes)
    original = package.master
    masters = set(package.masters)
    seen = set()
    staged = []
    try:
        for master, field, old, new in plan:
            target = original if master is None else master
            if target not in masters or (target, field) in seen:
                raise ValueError("Unknown master or duplicate field in Font Info plan.")
            seen.add((target, field))
            _font_info_value(field, new)
            package.setMaster(target)
            actual = getattr(package.info, field)
            if actual != old and not (actual is None and old == ""):
                raise ValueError(f"{field} changed since preview; refresh the tool.")
            if old != new:
                staged.append((master, field, actual, new))
    finally:
        package.setMaster(original)
    plan = staged
    if not plan:
        return {"changed": 0}
    native = _native("fontlab")
    history = [package, package.mastersContainer()]
    package.checkInitHistoryState(0)
    native.flItems.notifyChangesApplied(undo_name, history)
    attempted = []
    try:
        for master, field, old, new in plan:
            package.setMaster(original if master is None else master)
            attempted.append((master, field, old, new))
            setattr(package.info, field, new)
    except Exception as error:
        failures = []
        for master, field, old, _new in reversed(attempted):
            try:
                package.setMaster(original if master is None else master)
                setattr(package.info, field, old)
            except Exception as rollback_error:  # noqa: BLE001 - report every failed rollback
                failures.append(f"{master}/{field}: {rollback_error}")
        if failures:
            raise RuntimeError(
                "Partial Font Info edit; rollback failed: " + "; ".join(failures)
            ) from error
        raise
    finally:
        try:
            package.setMaster(original)
        finally:
            native.flItems.notifyChangesApplied(undo_name, history)
            native.UpdateAll()
    return {"changed": len(plan)}


def font_info_dialog_type() -> type[Any]:
    """Load the shared six-tool Font Info panel only when a script needs its UI.

    Importing scripting remains host-free; this call requires FontLab's PythonQt.
    Per-tool subclasses supply setup/refresh/apply, title, subtitle and registry
    key. MASTER_BOUND=True retains the two tools' current-master preview guard.
    """
    from fontlabapp.fonts.info.ui import FontInfoDialog

    return FontInfoDialog


def features_dialog_type() -> type[Any]:
    """Load the shared feature panel only when a native script needs it."""
    from fontlabapp.features.editor.ui import FeaturesDialog

    return FeaturesDialog


def read_feature_blocks(package: Any) -> dict:
    """Read exact VFJ feature source; see ``fontui.feature_blocks``."""
    from fontlabapp.fontui.feature_blocks import read_feature_blocks as read

    return read(package)


def write_feature_blocks(
    package: Any,
    expected: dict,
    updated: dict,
    *,
    references: Iterable[str],
    undo_name: str,
) -> dict[str, int]:
    """Write guarded VFJ feature source; see ``fontui.feature_blocks``."""
    from fontlabapp.fontui.feature_blocks import write_feature_blocks as write

    return write(package, expected, updated, references=references, undo_name=undo_name)


def names_dialog_type() -> type[Any]:
    """Load the shared inspection/selection Names panel inside FontLab only."""
    from fontlabapp.glyphs.names.ui import NamesDialog

    return NamesDialog


def names_snapshot_refresh(method: Any) -> Any:
    """Wrap a Names scan with complete-refresh publication."""
    from fontlabapp.glyphs.names.ui import snapshot_refresh

    return snapshot_refresh(method)


def names_muted(widget: Any) -> str:
    """Resolve theme-derived secondary colour for Names controls."""
    from fontlabapp.glyphs.names.ui import muted

    return muted(widget)


def names_font_glyphs() -> list[tuple[str, list[int]]]:
    """Read names and encodings in current font order without changing masters."""
    font = _native("fontlab").CurrentFont()
    return [(g.name, list(g.unicodes)) for g in font.glyphs] if font else []


def _carrier_id(font: Any, expected_fg_id: int) -> int:
    """The legacy FL.fl.font's package id.

    FontLab 9's legacy Font has no ``id`` (checked live on 9.0, 2026-11-03).
    Then the carrier counts as ``expected_fg_id`` only if the current package
    has that fgId and a saved path equal to ``font.file_name``; unsaved fonts
    and every other mismatch raise.
    """
    try:
        return int(font.id)
    except AttributeError:
        pass
    package = _native("fontlab").flWorkspace.instance().currentPackage
    path = str(font.file_name or "")
    if package is None or package.isNull or not path or str(package.path) != path:
        raise ValueError("Font-window carrier path differs from the current package.")
    return int(package.fgId)


def names_font_window_selection(
    *, expected_fg_id: int | None = None, deadline: float | None = None
) -> list[str]:
    """Read complete native font-order selection, with optional carrier fencing.

    Existing zero-argument callers keep their original behavior. Bound callers
    require FL.fl.font.id to equal flPackage.fgId; the official fgFont.id binding
    returns owner.getPackageID (pyfontgate/fgfont.cxx). No fgPackage is read.
    One absolute monotonic deadline covers the whole-font scan. Native calls
    cannot be interrupted here; the next checkpoint diagnoses an overrun.
    """
    fl = _native("FL").fl

    def check() -> None:
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError("Selection scan exceeded its deadline; no partial report.")
        if expected_fg_id is not None:
            try:
                actual = _carrier_id(fl.font, expected_fg_id)
            except Exception as error:
                raise ValueError("Font-window carrier is missing or unreadable.") from error
            if actual != expected_fg_id:
                raise ValueError("Font-window carrier differs from the active package.")

    check()
    font = fl.font
    if font is None:
        return []
    selected = []
    for index in range(len(font)):
        check()
        if fl.Selected(index):
            selected.append(font[index].name)
        check()
    check()
    return selected


def names_selected_names() -> list[str]:
    """Read Font window selection, otherwise the non-None current glyph.

    Native glyph truthiness counts contours, so empty and component-only glyphs
    remain valid fallbacks. Native read failures propagate to the guarded panel.
    """
    if _native("FL").fl.font is None:
        return []
    names = names_font_window_selection()
    if not names:
        glyph = _native("fontlab").CurrentGlyph()
        names = [glyph.name] if glyph is not None else []
    return names


def kerning_dialog_type() -> type[Any]:
    """Load the five read-only kerning panels' shared shell lazily (App 0.2.7)."""
    from fontlabapp.kerning.inspect.ui import KerningDialog

    return KerningDialog


def kerning_snapshot_refresh(method: Any) -> Any:
    """Publish complete kerning scans only; invalidate failed native reads."""
    from fontlabapp.kerning.inspect.ui import snapshot_refresh

    return snapshot_refresh(method)


def kerning_pairs(package: Any, master: str, *, typed: bool = False) -> dict:
    """Read explicit pairs; typed sides preserve literal @ glyph identifiers.

    The default retains legacy string keys for existing callers. Literal
    leading-@ glyph names cannot be encoded by that API and fail before a
    misleading view escapes; typed=True retains every identifier and mode.
    """
    from fontlabapp.kerning.identity import read_pairs

    return read_pairs(package, master, typed=typed)


def kerning_classes(package: Any, master: str) -> dict[str, tuple[list[str], str]]:
    """Return complete native class members and their pair-side roles."""
    sides = {"KernLeft": "left", "KernRight": "right", "KernBothSide": "both"}
    return {
        name: (list(members), sides.get(mode, mode))
        for name, (members, mode) in package.kerning(master).groups.items()
    }


def kerning_class_lists(package: Any, master: str) -> tuple[dict, dict, dict]:
    """Index class members by allowed left/right side, preserving native order."""
    left, right, members = {}, {}, {}
    for name, (glyphs, side) in kerning_classes(package, master).items():
        members[name] = glyphs
        for glyph in glyphs:
            if side in ("left", "both"):
                left.setdefault(glyph, []).append("@" + name)
            if side in ("right", "both"):
                right.setdefault(glyph, []).append("@" + name)
    return left, right, members


def kerning_pair_value(kerning: Any, left: str, right: str) -> float:
    """Use FontLab's effective glyph/class precedence; propagate read failures.

    Native pyfontgate/fgkerning.cxx get(names) calls getKerningValue, whereas
    items() reads explicit pairs. None means absent; an explicit zero is kept.
    """
    value = kerning.get((left, right))
    return 0 if value is None else value


def kerning_layout(
    package: Any, names: list[str], master: str, kerned: bool = True
) -> list[tuple[str, float, float, float]]:
    """Place actual glyph advances and effective kerning without changing master."""
    kerning = package.kerning(master)
    rows, x, previous = [], 0, None
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError(f"Missing glyph: {name}")
        layer = glyph.findLayer(master)
        if layer is None or layer.isNull:
            raise ValueError(f"Missing layer for {name} on {master}")
        kern = kerning_pair_value(kerning, previous, name) if kerned and previous else 0
        x += kern
        rows.append((name, x, layer.advanceWidth, kern))
        x += layer.advanceWidth
        previous = name
    return rows


def kerning_proof_geometry(
    rows: list,
    bounds: dict,
    width: float,
    height: float,
    scale: float,
    ascender: float,
    descender: float,
    labels: bool,
) -> tuple[float, list]:
    """Wrap and fit complete ink, overhangs and labels without omitting glyphs.

    Bounds are (left, bottom, right, top) in font coordinates. Requested size
    is an upper limit: shrink the whole proof when a tall/multi-line specimen
    otherwise exceeds its canvas. Return local padded pen/baseline positions.
    """
    if not rows:
        return scale, []
    if min(width, height, scale) <= 0:
        raise ValueError("Proof dimensions and scale must be positive")
    label = 20 if labels else 0
    usable = max(1, width - label * 2)
    lines, line, origin = [], [], rows[0][1]
    low, high = 0, 0
    for name, x, advance, kern in rows:
        left, bottom, right, top = bounds[name]
        a, b = (
            min(x - origin, x - origin + left),
            max(x - origin + advance, x - origin + right),
        )
        if line and (max(high, b) - min(low, a)) * scale > usable:
            lines.append((line, low, high))
            line, origin, low, high = [], x, 0, 0
            a, b = min(0, left), max(advance, right)
        line.append((name, x - origin, kern))
        low, high = min(low, a), max(high, b)
    lines.append((line, low, high))
    top = max(ascender, *(bounds[name][3] for name, *_ in rows))
    bottom = min(descender, *(bounds[name][1] for name, *_ in rows))
    span = max(1, top - bottom)
    gap = span * 0.15
    ink_width = max(1, *(high - low for _, low, high in lines))
    ink_height = len(lines) * span + max(0, len(lines) - 1) * gap
    label = min(label, height / (2 * len(lines)))
    label_height = len(lines) * label
    scale = min(scale, usable / ink_width, max(1, height - label_height) / ink_height)
    positions = []
    for index, (line, low, _) in enumerate(lines):
        baseline = top * scale + index * ((span + gap) * scale + label)
        positions.extend(
            (name, label + (x - low) * scale, baseline, kern) for name, x, kern in line
        )
    return scale, positions


def kerning_editor_api() -> Any:
    """Load shared pure plans and native batch access for menu editors (App0.2.8)."""
    from importlib import import_module

    return import_module("fontlabapp.kerning.edit.model")


def kerning_edit_dialog_type() -> type[Any]:
    """Load the snapshot-bound editor shell only when a native tool needs it."""
    from fontlabapp.kerning.edit.ui import KerningEditDialog

    return KerningEditDialog


def kerning_editor_refresh(method: Any) -> Any:
    """Bind complete kerning previews, with disabled actions on failed reads."""
    from fontlabapp.kerning.edit.ui import editor_refresh

    return editor_refresh(method)


def kerning_editor_apply(method: Any) -> Any:
    """Require the exact preview snapshot before any menu-editor mutation."""
    from fontlabapp.kerning.edit.ui import editor_apply

    return editor_apply(method)


def kerning_editor_make_table(headers: list[str]) -> Any:
    """Build shared editor preview tables with the original native sizing."""
    from fontlabapp.kerning.edit.ui import make_table

    return make_table(headers)


def kerning_selection_api() -> Any:
    """Load forthcoming App 0.2.9 selected-exception/text plans without native UI."""
    from importlib import import_module

    return import_module("fontlabapp.kerning.selection")


def proof_api() -> Any:
    """Load shared advance-only parsing, outlines and word filters (App0.2.10)."""
    from importlib import import_module

    return import_module("fontlabapp.proof.inspect.model")


def context_proof_api() -> Any:
    """Load the Glyphs Between/Surrounded context proofs and their named-tab opener."""
    from importlib import import_module

    return import_module("fontlabapp.proof.context")


def kerning_proof_api() -> Any:
    """Load the four bundled kerning proof texts and their new-tab opener."""
    from importlib import import_module

    return import_module("fontlabapp.kerning.proofs")


def layer_selection_api() -> Any:
    """Load the ordered selected-layer capture used by the context proofs."""
    from importlib import import_module

    return import_module("fontlabapp.masters.layers.selection")


def proof_studio_backends() -> Any:
    """Load the backends Proof Studio part 2 reuses, as one namespace of modules.

    ``random`` (seven random proofs), ``text_tab`` (one new text tab),
    ``text_filter``/``text_filter_settings`` (Text Filter), ``catalog`` (glyph
    catalogue for coverage) and ``master_text`` with ``capture``, ``model``,
    ``proof``, ``settings`` and ``owners`` (Master Text Comparison). Nothing
    native loads until a backend function runs.
    """
    from importlib import import_module
    from types import SimpleNamespace

    def load(name: str) -> Any:
        return import_module(f"fontlabapp.{name}")

    return SimpleNamespace(
        random=load("proof.random"),
        text_tab=load("proof.tabs.text"),
        text_filter=load("proof.text_filter.model"),
        text_filter_settings=load("proof.text_filter.settings"),
        catalog=load("glyphs.catalog.model"),
        master_text=SimpleNamespace(
            **{part: load(f"masters.text.{part}") for part in ("capture", "model", "proof", "settings", "owners")}
        ),
    )


def proof_dialog_type() -> type[Any]:
    """Load the owned native Proof panel shell only when a script needs it."""
    from fontlabapp.proof.inspect.ui import ProofDialog

    return ProofDialog


def proof_view_types() -> Any:
    """Load the three actual outline painters lazily inside FontLab."""
    from importlib import import_module

    return import_module("fontlabapp.proof.inspect.views")


def proof_snapshot_refresh(method: Any) -> Any:
    """Bind complete Proof results and clear failed or stale scans."""
    from fontlabapp.proof.inspect.ui import snapshot_refresh

    return snapshot_refresh(method)


def master_angles_api() -> Any:
    """Load staged master-angle reads and the single-container native writer lazily."""
    from importlib import import_module

    return import_module("fontlabapp.masters.angles.model")


def master_angles_dialog_type() -> type[Any]:
    """Load the complete italic-angle controls only when a menu is launched."""
    from fontlabapp.masters.angles.ui import ItalicAngleDialog

    return ItalicAngleDialog


def master_angles_view_types() -> Any:
    """Load the original slanted-stem gauge and native spin readability helpers."""
    from importlib import import_module

    return import_module("fontlabapp.masters.angles.ui")


def masters_api() -> Any:
    """Load shared read-only master calculations without importing native UI."""
    from importlib import import_module

    return import_module("fontlabapp.masters.inspect.model")


def masters_dialog_type() -> type[Any]:
    """Reuse the owned Proof/Names panel for complete original Masters menus."""
    from fontlabapp.masters.inspect.ui import MastersDialog

    return MastersDialog


def masters_snapshot_refresh(method: Any) -> Any:
    """Publish complete master report scans; refuse stale native actions."""
    from fontlabapp.masters.inspect.ui import snapshot_refresh

    return snapshot_refresh(method)


def masters_view_types() -> Any:
    """Load the actual original line and bar charts only inside FontLab."""
    from importlib import import_module

    return import_module("fontlabapp.masters.inspect.views")


def masters_make_table(headers: list[str], min_height: int = 280) -> Any:
    """Create the original read-only table beside the master report or chart."""
    from fontlabapp.masters.inspect.ui import make_table

    return make_table(headers, min_height)


def masters_fill_table(table: Any, rows: list, highlight: Any = None) -> None:
    """Render original master cells, notes and differing-value highlights."""
    from fontlabapp.masters.inspect.ui import fill_table

    fill_table(table, rows, highlight)


def inspectors_api() -> Any:
    """Load shared read-only metrics and raw contour calculations lazily."""
    from importlib import import_module

    return import_module("fontlabapp.proof.inspectors.model")


def inspectors_dialog_type() -> type[Any]:
    """Load the inspector extension of the existing owned Masters shell lazily."""
    from fontlabapp.proof.inspectors.ui import InspectorsDialog

    return InspectorsDialog


def inspectors_snapshot_refresh(method: Any) -> Any:
    """Reuse complete ordered master-domain scans and failed-read invalidation."""
    from fontlabapp.proof.inspectors.ui import snapshot_refresh

    return snapshot_refresh(method)


def inspectors_view_types() -> Any:
    """Load complete original spacing/contour painters only inside the host."""
    from importlib import import_module

    return import_module("fontlabapp.proof.inspectors.views")


def components_api() -> Any:
    """Load original component calculations without importing native Qt widgets."""
    from importlib import import_module

    return import_module("fontlabapp.components.inspect.model")


def components_dialog_type() -> type[Any]:
    """Reuse owned Proof/Names signals, bindings and Close for component inspectors."""
    from fontlabapp.components.inspect.ui import ComponentsDialog

    return ComponentsDialog


def components_snapshot_refresh(method: Any) -> Any:
    """Guard complete ordered component scans and source snapshots."""
    from fontlabapp.components.inspect.ui import snapshot_refresh

    return snapshot_refresh(method)


def components_action(method: Any) -> Any:
    """Refuse source drift before original filter, selection, copy and open actions."""
    from fontlabapp.components.inspect.ui import action

    return action(method)


def components_view_types() -> Any:
    """Load the complete original component badge painter only inside FontLab."""
    from importlib import import_module

    return import_module("fontlabapp.components.inspect.views")


def anchors_api() -> Any:
    """Load shared original anchor calculations without importing native Qt."""
    from importlib import import_module

    return import_module("fontlabapp.anchors.inspect.model")


def anchors_dialog_type() -> type[Any]:
    """Load the anchor extension of the owned Proof/Names panel shell lazily."""
    from fontlabapp.anchors.inspect.ui import AnchorsDialog

    return AnchorsDialog


def anchors_snapshot_refresh(method: Any) -> Any:
    """Publish complete anchor scans only after source/domain checks."""
    from fontlabapp.anchors.inspect.ui import snapshot_refresh

    return snapshot_refresh(method)


def anchors_action(method: Any) -> Any:
    """Guard original anchor selectors, filtering and Font-window selection."""
    from fontlabapp.anchors.inspect.ui import action

    return action(method)


def anchors_view_types() -> Any:
    """Load the complete original anchor cloud and attachment painters lazily."""
    from importlib import import_module

    return import_module("fontlabapp.anchors.inspect.views")


def vertical_metrics_backends() -> Any:
    """Load the backends the Vertical Metrics & Zones app reuses, as one namespace.

    ``master_metrics`` (route-A master metric writer), ``font_history``
    (``require_font_window``), ``zones``/``zone_rows``/``zone_data``/
    ``zone_editor``/``zone_native`` (the Alignment Zones model, rows, editor
    dialog and route-A writer), ``extent`` (outline vertical extent),
    ``angles`` (Italic Angle capture and apply), ``reporter`` (the Vertical
    Metrics Reporter capture and render) and ``panel`` (``muted``). Nothing
    native loads until a backend function runs. Used by
    ``fontlabapp.studios.vertical_metrics``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    return SimpleNamespace(
        master_metrics=import_module("fontlabapp.metrics.master_writer"),
        font_history=import_module("fontlabapp.core.history.masters"),
        zones=import_module("fontlabapp.metrics.zones.model"),
        zone_rows=import_module("fontlabapp.metrics.zones.rows"),
        zone_data=import_module("fontlabapp.metrics.zones.data"),
        zone_editor=import_module("fontlabapp.metrics.zones.editor"),
        zone_native=import_module("fontlabapp.metrics.zones.native"),
        extent=import_module("fontlabapp.contours.extent"),
        angles=import_module("fontlabapp.masters.angles.model"),
        reporter=SimpleNamespace(
            native=import_module("fontlabapp.metrics.vertical.native"),
            model=import_module("fontlabapp.metrics.vertical.model"),
        ),
        panel=import_module("fontlabapp.metrics.panel.model"),
    )


def vertical_metrics_views() -> Any:
    """Return the Qt module with the Italic Angle ``Gauge`` (``masters.angles.views``).

    Separate from ``vertical_metrics_backends`` because it loads PythonQt.
    Used by the Italic angle tab of ``fontlabapp.studios.vertical_metrics``.
    """
    from importlib import import_module

    return import_module("fontlabapp.masters.angles.views")


def mark_attachment_backends() -> Any:
    """Load the backends the Mark Attachment app reuses, as one namespace.

    ``inspect`` (the Mark Attachment Preview anchor model), ``components``
    (the component writer of Align By Anchor), ``anchors`` (the anchor
    writer of the cursive tools), ``selection`` (ordered selected-layer
    capture), ``masters`` (``associated_master``) and ``history``
    (auto-glyph facts). Nothing native loads until a backend function runs.
    Used by ``fontlabapp.studios.mark_attachment``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    return SimpleNamespace(
        inspect=import_module("fontlabapp.anchors.inspect.model"),
        components=import_module("fontlabapp.components.writer"),
        anchors=import_module("fontlabapp.anchors.writer"),
        selection=import_module("fontlabapp.masters.layers.selection"),
        masters=import_module("fontlabapp.masters.inspect.model"),
        history=import_module("fontlabapp.core.history.glyphs"),
    )


def component_studio_backends() -> Any:
    """Load the backends the Component Studio app reuses, as one namespace.

    ``components`` (the shared component writer: plans, editors, copy
    checks), ``recipes`` (the read-only Dump Component Recipes reader),
    ``panel`` (the component panel palette helpers, ``ink``), ``history``
    (auto-glyph facts and refusals) and ``pr`` (FontLab's in-process data
    tools: ``pr.call(tool, **arguments)``, as the originals' ``fly.pr``).
    Nothing native loads until a backend function runs.
    Used by ``fontlabapp.studios.component_studio``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    def call(tool: str, **arguments: Any) -> Any:
        return _native("fontpr").call(tool, **arguments)

    return SimpleNamespace(
        components=import_module("fontlabapp.components.writer"),
        recipes=import_module("fontlabapp.components.recipes.model"),
        panel=import_module("fontlabapp.components.panel.model"),
        history=import_module("fontlabapp.core.history.glyphs"),
        pr=SimpleNamespace(call=call),
    )


def component_audit_backends() -> Any:
    """Load the read-only backends the Component Audit app reuses, as one namespace.

    ``inspect`` (the original component report, usage index, missing-base
    and source-snapshot calculations), ``graph`` (the shared elastic
    component graph panel, ``graph.show()``), ``brackets`` (bracket-layer
    analysis and ``render``) with ``bracket_report()`` (its whole-font
    capture), and ``update_all()`` (FontLab's ``UpdateAll``, which the
    Components Report runs after making a glyph current). Nothing native
    loads until a backend function runs.
    Used by ``fontlabapp.studios.component_audit``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    def bracket_report() -> Any:
        return import_module("fontlabapp.masters.layers.brackets.native").report()

    def update_all() -> None:
        _native("fontlab").UpdateAll()

    return SimpleNamespace(
        inspect=import_module("fontlabapp.components.inspect.model"),
        graph=import_module("fontlabapp.components.graph.model"),
        brackets=import_module("fontlabapp.masters.layers.brackets.model"),
        bracket_report=bracket_report,
        update_all=update_all,
    )


def derived_glyphs_backends() -> Any:
    """Load the glyph-creation backends the Derived Glyphs app reuses, as one namespace.

    ``copies`` (``glyphs.copies``: survey, half_up, Row, create),
    ``creation`` (``glyphs.creation``: NewGlyph, Part, create_glyphs,
    auto_candidates, rebuild_note, REBUILD_LABEL, undo_text),
    ``component_creation`` (``components.creation``), ``components``
    (``components.writer``), ``contour_copy`` (``contours.copy``),
    ``catalog`` (``glyphs.catalog.model``), ``dialogs`` (``qt.dialogs``:
    the originals' standard message box) and ``fontlab`` (FontLab's
    native module, loaded on first attribute access). The originals'
    writers are reused unchanged.
    Used by ``fontlabapp.studios.derived_glyphs``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    class Native:
        def __getattr__(self, name: str) -> Any:
            return getattr(_native("fontlab"), name)

    return SimpleNamespace(
        copies=import_module("fontlabapp.glyphs.copies"),
        creation=import_module("fontlabapp.glyphs.creation"),
        component_creation=import_module("fontlabapp.components.creation"),
        components=import_module("fontlabapp.components.writer"),
        contour_copy=import_module("fontlabapp.contours.copy"),
        catalog=import_module("fontlabapp.glyphs.catalog.model"),
        dialogs=import_module("fontlabapp.qt.dialogs"),
        fontlab=Native(),
    )


def layer_manager_backends() -> Any:
    """Load the layer backends the Layer Manager app reuses, as one namespace.

    ``contour_copy`` (``contours.copy``: shape clones and repairs),
    ``outlines`` (``contours.writer``: the outline Editor and apply_work),
    ``layers`` (``masters.layers.writer``: settle, Editor), ``anchors``
    (``anchors.writer``), ``selection`` (``masters.layers.selection``:
    the captured layer selection), ``masters`` (``masters.inspect.model``:
    associated masters and the backup naming rules), ``catalog``
    (``glyphs.catalog.model``), ``creation`` (``glyphs.creation``),
    ``copies`` (``glyphs.copies``), ``guards`` (``core.edit_guards``),
    ``scripting`` (this module: the current package and the Font-window
    selection the cross-font originals read) and ``fontlab`` (FontLab's
    native module, loaded on first attribute access). The originals' App helpers are reused unchanged.
    Used by ``fontlabapp.studios.layer_manager``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    class Native:
        def __getattr__(self, name: str) -> Any:
            return getattr(_native("fontlab"), name)

    return SimpleNamespace(
        contour_copy=import_module("fontlabapp.contours.copy"),
        outlines=import_module("fontlabapp.contours.writer"),
        layers=import_module("fontlabapp.masters.layers.writer"),
        anchors=import_module("fontlabapp.anchors.writer"),
        selection=import_module("fontlabapp.masters.layers.selection"),
        masters=import_module("fontlabapp.masters.inspect.model"),
        catalog=import_module("fontlabapp.glyphs.catalog.model"),
        creation=import_module("fontlabapp.glyphs.creation"),
        copies=import_module("fontlabapp.glyphs.copies"),
        guards=import_module("fontlabapp.core.edit_guards"),
        scripting=import_module("fontlabapp.core.scripting"),
        fontlab=Native(),
    )


def unreferenced_api() -> Any:
    """Load original glyph-reference calculations without importing native Qt."""
    from importlib import import_module

    return import_module("fontlabapp.glyphs.unreferenced")


def names_legacy_font() -> list[str]:
    """Glyph names of the legacy ``FL.fl.font`` in its index order; [] with no font.

    The order the three Font Info ``glyph_records`` copies iterate; read only
    names, never ``flGlyph.fgGlyph``. Used by ``fontlabapp.studios._records``.
    """
    font = _native("FL").fl.font
    return [font[index].name for index in range(len(font))] if font is not None else []


def font_audit_backends() -> Any:
    """Load the report backends Font Audit reuses, as one namespace of modules.

    ``case_coverage`` (the Case Coverage controller), ``smallcaps`` (the
    Smallcap Consistency capture), ``reports`` (the owned JSON report window)
    and ``unreferenced`` (Select Unreferenced Glyphs). Nothing native loads
    until a backend function runs.
    """
    from importlib import import_module
    from types import SimpleNamespace

    return SimpleNamespace(
        case_coverage=import_module("fontlabapp.glyphs.case_coverage.controller"),
        smallcaps=import_module("fontlabapp.glyphs.smallcaps.capture"),
        reports=import_module("fontlabapp.proof.reports.model"),
        unreferenced=import_module("fontlabapp.glyphs.unreferenced"),
    )


def kerning_tool_backends() -> Any:
    """Load the kerning backends Kerning Browser and Kerning Batch reuse, as one namespace.

    ``edit`` (value plans: round, scale, small pairs, copy), ``selection``
    (exception finder), ``cutoff`` (the inclusive -250..100 clamp plan),
    ``batch`` (snapshots, ``ensure_snapshot``, ``validate_pair``) and
    ``reports`` (the owned JSON report window). Nothing native loads until a
    backend function runs. Used by ``fontlabapp.studios.kerning_browser`` and
    ``fontlabapp.studios.kerning_batch``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    return SimpleNamespace(
        edit=import_module("fontlabapp.kerning.edit.model"),
        selection=import_module("fontlabapp.kerning.selection"),
        cutoff=import_module("fontlabapp.kerning.cutoff"),
        group_proof=import_module("fontlabapp.kerning.group_proof.model"),
        persistence=import_module("fontlabapp.kerning.persistence.model"),
        symmetry=import_module("fontlabapp.kerning.symmetry.native"),
        symmetry_model=import_module("fontlabapp.kerning.symmetry.model"),
        batch=import_module("fontlabapp.kerning.batch"),
        reports=import_module("fontlabapp.proof.reports.model"),
    )


def advance_widths_backends() -> Any:
    """Load the metrics backends the Advance Widths app reuses, as one namespace.

    ``panel`` (layer survey, ``shift_and_set``, read-back and auto-glyph
    notes), ``inspectors`` (the Width Table progression report), ``masters``
    (master order and the Width Chart widths), ``tabular`` (the read-only
    Check Tabular Widths capture) and ``history`` (auto-glyph facts).
    Nothing native loads until a backend function runs. Used by
    ``fontlabapp.studios.advance_widths``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    return SimpleNamespace(
        panel=import_module("fontlabapp.metrics.panel.model"),
        inspectors=import_module("fontlabapp.proof.inspectors.model"),
        masters=import_module("fontlabapp.masters.inspect.model"),
        tabular=import_module("fontlabapp.metrics.tabular_width.model"),
        history=import_module("fontlabapp.core.history.glyphs"),
    )


def anchor_transfer_backends() -> Any:
    """Load the anchor backends the Anchor Transfer app reuses, as one namespace.

    ``writer`` (plans, refusals, layer steps and read-back), ``copy`` (the
    Copy Anchors from Glyph plan and its dependant refusal), ``crossfont``
    (``model``, ``capture`` and ``native`` of Copy Anchors Between Fonts),
    ``catalog`` (the glyph catalogue of Derive Anchors From Components) and
    ``history`` (auto-glyph facts). Nothing native loads until a backend
    function runs. Used by ``fontlabapp.studios.anchor_transfer``.
    """
    from importlib import import_module
    from types import SimpleNamespace

    return SimpleNamespace(
        writer=import_module("fontlabapp.anchors.writer"),
        copy=import_module("fontlabapp.anchors.copy.model"),
        crossfont=SimpleNamespace(
            model=import_module("fontlabapp.anchors.crossfont.model"),
            capture=import_module("fontlabapp.anchors.crossfont.capture"),
            native=import_module("fontlabapp.anchors.crossfont.native"),
            transaction=import_module("fontlabapp.anchors.crossfont.transaction"),
        ),
        catalog=import_module("fontlabapp.glyphs.catalog.model"),
        history=import_module("fontlabapp.core.history.glyphs"),
    )


def interpolation_api() -> Any:
    """Load original node blending and lazy native path calculations."""
    from importlib import import_module

    return import_module("fontlabapp.masters.interpolation.model")


def review_dialog_type() -> type[Any]:
    """Reuse the guarded owned lifecycle for two complete read-only reviews."""
    from fontlabapp.proof.review.ui import ReviewDialog

    return ReviewDialog


def review_snapshot_refresh(method: Any) -> Any:
    """Validate cached source before a complete review or intended option change."""
    from fontlabapp.anchors.inspect.ui import snapshot_refresh

    return snapshot_refresh(method)


def review_action(method: Any) -> Any:
    """Refuse stale review selections using the existing owned action boundary."""
    from fontlabapp.components.inspect.ui import action

    return action(method)


def interpolation_view_type() -> type[Any]:
    """Load the full original endpoint/mix painter only inside FontLab."""
    from fontlabapp.masters.interpolation.view import BlendView

    return BlendView


def node_coordinates_api() -> Any:
    """Load selected-node measurements without importing Qt or FontLab eagerly."""
    from importlib import import_module

    return import_module("fontlabapp.contours.nodes.coordinates")


def master_switcher_api() -> Any:
    """Load compact master-button calculations without eager host imports."""
    from importlib import import_module

    return import_module("fontlabapp.masters.switcher.model")


def master_switcher_dialog_type() -> type[Any]:
    """Reuse the owned Masters shell with exact master-button source guards."""
    from fontlabapp.masters.switcher.ui import SwitcherDialog

    return SwitcherDialog


def guides_api() -> Any:
    """Load guide calculations and guarded writer without eager native imports."""
    from importlib import import_module

    return import_module("fontlabapp.guides.inspect.model")


def guides_dialog_type() -> type[Any]:
    """Reuse the owned Masters shell for complete guide tools and source guards."""
    from fontlabapp.guides.inspect.ui import GuidesDialog

    return GuidesDialog


def guides_preview_type() -> type[Any]:
    """Load the complete grid painter with shared paint containment."""
    from fontlabapp.guides.inspect.views import GridPreview

    return GridPreview


def guide_rewrite_api() -> Any:
    """Load finite record parsing and complete native guide rewrite helpers lazily."""
    from importlib import import_module

    return import_module("fontlabapp.guides.rewrite.model")


def guide_rewrite_dialog_type() -> type[Any]:
    """Load the existing owned guide shell with late master target controls."""
    from fontlabapp.guides.rewrite.ui import RewriteDialog

    return RewriteDialog


def guide_editor_dialog_type() -> type[Any]:
    """Load the complete editable guide-row shell only inside FontLab."""
    from fontlabapp.guides.rewrite.editor_ui import GuideListDialog

    return GuideListDialog


def anchor_copy_api() -> Any:
    """Load complete anchor-copy arithmetic and guarded writes lazily."""
    from importlib import import_module

    return import_module("fontlabapp.anchors.copy.model")


def anchor_copy_dialog_type() -> type[Any]:
    """Load the owned anchor-copy shell only inside FontLab."""
    from fontlabapp.anchors.copy.ui import CopyDialog

    return CopyDialog


def anchor_copy_snapshot_refresh(method: Any) -> Any:
    """Bind old source before intentional control changes in the copy panel."""
    from fontlabapp.anchors.copy.ui import snapshot_refresh

    return snapshot_refresh(method)


def canvas_rsb_api() -> Any:
    """Load pure RSB foreground geometry without importing host APIs eagerly."""
    from importlib import import_module

    return import_module("fontlabapp.metrics.canvas_rsb.model")


def canvas_rsb_dialog_type() -> type[Any]:
    """Load the owned foreground RSB panel only inside FontLab."""
    from fontlabapp.metrics.canvas_rsb.ui import CanvasRSBDialog

    return CanvasRSBDialog


def canvas_anchor_rings_api() -> Any:
    """Load immutable duplicate-anchor ring capture and geometry lazily."""
    from importlib import import_module

    return import_module("fontlabapp.anchors.canvas_rings.model")


def canvas_anchor_rings_dialog_type() -> type[Any]:
    """Load the foreground ring controls on the shared RSB lifecycle."""
    from fontlabapp.anchors.canvas_rings.ui import CanvasAnchorRingsDialog

    return CanvasAnchorRingsDialog


def kerning_persistence_api() -> Any:
    """Load exact-pair audit snapshots without importing the native host."""
    from importlib import import_module

    return import_module("fontlabapp.kerning.persistence.model")

def kerning_persistence_dialog_type() -> type[Any]:
    """Load the nonmodal persistence audit only when its menu is invoked."""
    from fontlabapp.kerning.persistence.ui import KerningPersistenceDialog

    return KerningPersistenceDialog

def revision_compare_api() -> Any:
    """Load exact named-field comparison without eager native imports."""
    from importlib import import_module

    return import_module("fontlabapp.fonts.revisions.model")

def revision_compare_dialog_type() -> type[Any]:
    """Load explicit open-font comparison controls when their menu is invoked."""
    from fontlabapp.fonts.revisions.ui import RevisionCompareDialog

    return RevisionCompareDialog


def tabular_width_dialog_type() -> type[Any]:
    """Load the read-only tabular-width report inside FontLab, on demand."""
    from fontlabapp.metrics.tabular_width.ui import TabularWidthDialog

    return TabularWidthDialog


def component_recipes_dialog_type() -> type[Any]:
    """Load the read-only selected-layer component recipe report on demand."""
    from fontlabapp.components.recipes.ui import ComponentRecipesDialog

    return ComponentRecipesDialog


def angularizzle_dialog_type() -> type[Any]:
    """Load the bound Angularizzle preview session only when its menu runs."""
    from fontlabapp.contours.angularizzle.ui import AngularizzleDialog

    return AngularizzleDialog


def point_counts_dialog_type() -> type[Any]:
    """Load the owned Point Counter snapshot panel only when its menu runs."""
    from fontlabapp.contours.point_counts.ui import PointCountsDialog

    return PointCountsDialog


def vertical_metrics_dialog_type() -> type[Any]:
    """Load the all-master stored vertical-metrics report only on invocation."""
    from fontlabapp.metrics.vertical.ui import VerticalMetricsDialog

    return VerticalMetricsDialog


def anchors_coordinates_api() -> Any:
    """Load original coordinate arithmetic and the reviewed point core lazily."""
    from importlib import import_module

    return import_module("fontlabapp.anchors.coordinates.model")


def anchors_coordinate_dialog_type(kind: str) -> type[Any]:
    """Load the complete original coordinate panel only inside FontLab."""
    from fontlabapp.anchors.coordinates.ui import (
        CenterAnchors,
        RoundAnchors,
        SnapAnchors,
    )

    return {"center": CenterAnchors, "round": RoundAnchors, "metrics": SnapAnchors}[kind]


def spacing_offset_backends() -> Any:
    """Reuse the captured selected-layer offset preview without exposing studio internals."""
    from importlib import import_module
    from types import SimpleNamespace

    return SimpleNamespace(
        capture=import_module("fontlabapp.metrics.offset.capture").capture,
        preview=import_module("fontlabapp.metrics.offset.model").preview,
    )
