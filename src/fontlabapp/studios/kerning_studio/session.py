# this_file: src/fontlabapp/studios/kerning_studio/session.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Studio state: per-master reads and per-master kerning writes.

What: ``Studio`` takes one snapshot of every master's pairs and classes from
the live package (``fontlabapp.fontui.kerning_snapshot``; reading changes
nothing) and keeps the master the preview shows. Every write is one
``fontlabapp.fontui.write_kerning`` call: ``{master: {pair: value or None}}``
on any masters, one ``"Kerning Studio: <action> <pair>"`` Undo step, checked
against the snapshot it was planned from and read back (Issue 235 §1.3/§1.4).
Why: The selected (preview) master is the write target; "Delete pair on all
masters" and the per-master grid write several masters in one step, as the
Scriptmix scripts did. Only changed masters are range-checked (Scriptmix TODO:80).
Used by the four tab modules in ``fontlabapp.studios.kerning_studio.tabs``.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import fontlabapp.fontui as fontui

from . import APP, model
from .model import MasterData, Pair, display

NO_FONT = "Open a font first."
WRITE_ERRORS = (ValueError, TypeError, RuntimeError, KeyError)
ROLES = {"KernLeft": "left", "KernRight": "right", "KernBothSide": "both"}
Edits = dict[str, dict[Pair, float | None]]


class Studio:
    """Shared state of one Kerning Studio window; tabs subscribe with ``views``."""

    def __init__(self, shell: Any, *, font: Callable[[], Any] | None = None) -> None:
        self.shell = shell
        self._font = font or fontui.current_font
        self.masters: dict[str, MasterData] = {}
        self.native: dict[str, dict[str, str]] = {}
        self.snapshot: Any = None
        self.current: str | None = None
        self.master: str | None = None
        self.views: list[Callable[[], None]] = []
        self.preview: Any = None
        self.status = ""
        self.last_edits: Edits = {}

    def say(self, text: str) -> None:
        """Show ``text`` in the shell status line and keep it for follow-up notes."""
        self.status = text
        self.shell.set_status(text)

    # Reads -----------------------------------------------------------------
    def font(self) -> Any:
        return self._font()

    def reload(self, *, preserve: bool = False) -> bool:
        """Re-read without writes; history refresh retains the chosen master and drafts."""
        try:
            package = self.shell.package()
            if package is None:
                raise ValueError(NO_FONT)
            snapshot = fontui.kerning_snapshot(package)
            if preserve and self.master is not None and self.master not in snapshot.masters:
                raise ValueError(f"The captured master {self.master} is missing; reopen this tool.")
            masters, native = {}, {}
            for name in snapshot.masters:
                classes = {g: (members, ROLES.get(mode, "")) for g, (members, mode) in snapshot.groups[name].items()}
                masters[name] = model.from_native(snapshot.pairs[name], classes)
                native[name] = {
                    model._prefixed(g, side): "@" + g
                    for g, (_members, role) in classes.items()
                    for side in model.NATIVE_SIDES.get(role, ())
                }
            self.masters, self.native, self.snapshot = masters, native, snapshot
            self.current = self.master if preserve and self.master is not None else str(package.master)
            if not preserve and self.master not in self.masters:
                self.master = self.current
        except (ValueError, RuntimeError, TypeError) as error:
            self.masters, self.native, self.current, self.snapshot = {}, {}, None, None
            self.say(NO_FONT if str(error) == NO_FONT else f"{APP}: {error}")
            if preserve:
                return False
        for view in list(self.views):
            if preserve:
                self._refresh_draft(view)
            else:
                view()
        return self.snapshot is not None

    def _refresh_draft(self, view: Callable[[], None]) -> None:
        """Table selection emits value changes; keep the user's unfinished numeric text."""
        from PythonQt import QtGui

        panel = view.__self__
        fields = {name: widget.text() if callable(widget.text) else widget.text
                  for name, widget in vars(panel).items() if isinstance(widget, QtGui.QLineEdit)}
        grid = {name: widget.text() if callable(widget.text) else widget.text
                for name, widget in getattr(panel, "grid", {}).items()}
        table = getattr(panel, "table", None)
        filter_box = getattr(table, "filter_box", None)
        filter_text = (filter_box.text() if callable(filter_box.text) else filter_box.text) if filter_box is not None else None
        try:
            view()
        finally:
            for name, text in fields.items():
                getattr(panel, name).setText(text)
            for name, text in grid.items():
                if name in panel.grid:
                    panel.grid[name].setText(text)
            if filter_text is not None:
                panel.table.filter_box.setText(filter_text)

    def choose_master(self, name: str | None) -> None:
        """Show ``name`` in the preview and make it the write target."""
        self.master = name
        if self.preview is not None:
            self.preview.set_layer(name)

    def glyph(self, master: str, name: str) -> Any:
        """The Fontport glyph ``name`` on ``master`` (advance and outline source)."""
        font = self.font()
        if font is None:
            raise ValueError(NO_FONT)
        if master == getattr(font, "defaultLayerName", None):
            layer = font
        else:
            try:
                layer = font.getLayer(master)
            except (AttributeError, KeyError, ValueError) as error:
                raise ValueError(f"Cannot read glyphs of {master}; make it the current master.") from error
        if name not in layer:
            raise ValueError(f"Glyph {name} is not in the font.")
        return layer[name]

    def cmap(self, font: Any) -> dict[int, str]:
        result: dict[int, str] = {}
        for name in font.keys():
            for code in getattr(font[name], "unicodes", ()) or ():
                result.setdefault(code, name)
        return result

    def order(self, font: Any) -> list[str]:
        return list(getattr(font, "glyphOrder", None) or font.keys())

    def value(self, master: str, left: str, right: str) -> tuple[float, Pair | None]:
        """Effective value of a pair on a natively read master."""
        return model.effective(self.masters[master], left, right)

    # Writes ----------------------------------------------------------------
    def native_key(self, master: str, key: Pair) -> Pair:
        """A model key (``public.kern1.X``) as the native ``@class`` pair of ``master``."""
        names = self.native.get(master, {})
        return tuple(names[side] if model.is_group(side) else side for side in key)  # type: ignore[return-value]

    def write(self, action: str, subject: str, plan: Callable[[], Edits]) -> bool:
        """Write ``plan()`` (``{master: {key: value or None}}``) as one Undo step."""
        package = self.shell.package()
        if package is None or self.snapshot is None:
            self.say(NO_FONT)
            return False
        label = f"{APP}: {action} {subject}"
        try:
            edits = {m: changes for m, changes in plan().items() if changes}
            native = {m: {self.native_key(m, k): v for k, v in changes.items()} for m, changes in edits.items()}
            done = bool(native) and fontui.write_kerning(package, native, label, expected=self.snapshot)
        except WRITE_ERRORS as error:
            self.say(f"{APP}: {error}")
            return False
        self.reload()
        where = ", ".join(edits) or self.master
        if not done:
            self.say(f"{APP}: no change to {subject} on {where}.")
            return False
        self.say(f"{label} on {where}.")
        self.last_edits = edits
        return True

    def _target(self) -> tuple[str, MasterData]:
        if self.master not in self.masters:
            raise ValueError(NO_FONT)
        return self.master, self.masters[self.master]

    def set_pairs(self, action: str, subject: str, values: Sequence[tuple[str, str, float]]) -> bool:
        """Set each ``(left, right, value)`` on the selected master: the most specific record, else the class one."""

        def plan() -> Edits:
            master, data = self._target()
            return {master: {model.target_key(data, left, right): value for left, right, value in values}}

        return self.write(action, subject, plan)

    def set_pair(self, left: str, right: str, value: float) -> bool:
        return self.set_pairs("kerning", pair_text(left, right), [(left, right, value)])

    def set_grid(self, left: str, right: str, values: Mapping[str, float | None]) -> bool:
        """Pair Editor grid: write each master's cell (None deletes that master's record), one Undo step."""

        def plan() -> Edits:
            edits: Edits = {}
            for master, value in values.items():
                data = self.masters[master]
                current, key = model.effective(data, left, right)
                if value is None:
                    if key is not None:
                        edits[master] = {key: None}
                elif current != value or key is None:
                    edits[master] = {model.target_key(data, left, right): value}
            return edits

        return self.write("kerning", pair_text(left, right), plan)

    def nudge(self, left: str, right: str, step: float) -> bool:
        def plan() -> Edits:
            master, data = self._target()
            value = model.effective(data, left, right)[0] + step
            return {master: {model.target_key(data, left, right): value}}

        return self.write(f"nudge {step:+g}", pair_text(left, right), plan)

    def kern_to_max(self, left: str, right: str) -> bool:
        def plan() -> Edits:
            if model.is_group(left) or model.is_group(right):
                raise ValueError("Kern To Max needs two glyphs, not groups.")
            master, data = self._target()
            value = model.kern_to_max(self.glyph(master, left).width, self.glyph(master, right).width)
            return {master: {model.target_key(data, left, right): value}}

        return self.write("Kern To Max", pair_text(left, right), plan)

    def delete(self, pairs: Sequence[tuple[str, str]]) -> bool:
        """Delete each pair's class record (glyph record if no class) on every master, one Undo step.

        Exceptions (more specific records) stay and are named in the status line.
        """
        kept: list[str] = []
        subject = ", ".join(pair_text(*pair) for pair in pairs)

        def plan() -> Edits:
            edits: Edits = {}
            for master, data in self.masters.items():
                for left, right in pairs:
                    key = model.class_key(data, left, right)
                    if key in data.pairs:
                        edits.setdefault(master, {})[key] = None
                    kept.extend(
                        f"{master}: {display(k[0])} {display(k[1])} = {v:g}"
                        for k, v in model.overrides(data, key, left, right)
                    )
            if not edits:
                raise ValueError(f"No kerning to delete for {subject}.")
            return edits

        done = self.write("delete", subject, plan)
        if done and kept:
            self.say(f"{self.status} Exceptions kept: " + "; ".join(dict.fromkeys(kept)) + ".")
        return done

    def steal(self, glyphs: Sequence[str], height: float) -> tuple[int, float, float]:
        """Measure the Steal value for pair 1 (glyphs 0-1) from pair 2 (glyphs 2-3) on the selected master."""
        if self.font() is None:
            raise ValueError(NO_FONT)
        if len(glyphs) != 4:
            raise ValueError("Enter four glyph names: the pair to change, then the reference pair.")
        master, data = self._target()
        widths, spans = [], []
        for name in glyphs:
            glyph = self.glyph(master, name)
            widths.append(glyph.width)
            spans.append(model.extents(record(glyph), height, name, master)[0])
        reference = model.effective(data, glyphs[2], glyphs[3])[0]
        return model.steal_value(widths, spans, reference)

    def apply_steal(self, glyphs: Sequence[str], height: float) -> bool:
        try:
            value, _gap1, _gap2 = self.steal(glyphs, height)
        except (ValueError, KeyError) as error:
            self.say(f"{APP}: {error}")
            return False
        left, right = glyphs[0], glyphs[1]

        def plan() -> Edits:
            master, data = self._target()
            if value == 0:
                key = model.effective(data, left, right)[1]
                return {master: {key: None}} if key is not None else {}
            return {master: {model.target_key(data, left, right): value}}

        return self.write("Steal Kerning", pair_text(left, right), plan)


def pair_text(left: str, right: str) -> str:
    return f"{display(left)} {display(right)}"


def record(glyph: Any) -> list[tuple[str, tuple]]:
    """The glyph's outline as pen operations, components decomposed."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen

    pen = DecomposingRecordingPen(getattr(glyph, "font", None) or {})
    glyph.draw(pen)
    return pen.value
