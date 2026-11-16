# this_file: src/fontlabapp/fontui/kerning.py
# SPDX-License-Identifier: Apache-2.0
"""Explicit kerning actions and effective fallback over a borrowed font."""

from collections.abc import Callable
from typing import Any

from ._fontport import require_fontport

with require_fontport(__name__):
    from fontlab_fontport.kerning_edit import edit_kerning, inspect_kerning

from .kerning_view import build
from .lifecycle import Owned, follow_changes, follow_history

EMPTY_PAIR_TEXT = "Select a pair, or type the left and right names."


def number_text(value: float) -> str:
    """Show integral values without a fraction; native Undo can restore -0.0."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _require_apply(pairs: Any) -> None:
    if not callable(getattr(pairs, "apply", None)):
        raise TypeError("Read-only: model has no kerning.apply")


def apply_kerning(
    font: Any,
    action: str,
    pair: tuple[str, str],
    value: float | None,
    *,
    undo_name: str,
    pairs: Any = None,
    before: dict | None = None,
    master: str | None = None,
) -> dict | None:
    """Stage ``action`` on ``pair`` with Fontport, apply it once, verify readback.

    Return the applied values, or None when the staged kerning equals the
    current kerning (nothing is written). Raise TypeError for a model without
    ``kerning.apply`` and RuntimeError when the backend reads back different
    values. Shared by ``KerningEditor.edit`` and ``fontlabapp.fontui.tmetrics``.

    Fontport writes kerning to the default master only (its ``set_kerning``
    has no master argument). ``master`` names the master the caller resolved;
    when it is not the default master (``font.defaultLayerName``) the write is
    refused with ValueError before anything changes. None keeps the old
    behaviour: the default kerning target.
    """
    if master is not None:
        current = getattr(font, "defaultLayerName", None)
        if master != current:
            raise ValueError(
                f"Kerning is written to the default master ({current}) only; "
                f"{master} cannot be targeted."
            )
    pairs = font.kerning if pairs is None else pairs
    before = dict(pairs) if before is None else before
    _require_apply(pairs)
    values = edit_kerning(
        before, action, pair, value, groups=dict(font.groups), glyphs=font.keys()
    )
    if values == before:
        return None
    pairs.apply(values, undo_name=undo_name)
    if dict(pairs) != values:
        raise RuntimeError("Backend kerning readback differs from the requested edit")
    return values


def _value(value: float | None) -> str:
    """Kerning value text; ``none`` for an absent pair."""
    return "none" if value is None else number_text(value)


class KerningEditor(Owned):
    """Own controls and nested preview; Fontport stages and applies each batch."""

    def __init__(
        self,
        font: Any,
        parent: Any = None,
        on_apply: Callable[[Any, Any], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.font, self.on_apply = font, on_apply
        self.rows: list[tuple[str, str]] = []
        self.selected: tuple[str, str] | None = None
        self.editable: bool = False
        self._shown: tuple[str, str, str] = ("", "", "")
        build(self)
        self.connect(self.filter_control.textChanged, lambda *args: self.fill())
        self.connect(self.pair_list.currentRowChanged, self.select)
        for control in (self.left_control, self.right_control):
            self.connect(control.textChanged, lambda *args: self.inspect())
        self.connect(self.apply_button.clicked, lambda *args: self.edit("apply"))
        self.connect(self.delete_button.clicked, lambda *args: self.edit("delete"))
        self.connect(self.reload_button.clicked, lambda *args: self.reload())
        # Native Undo/Redo and other edits change pairs outside this editor.
        follow_history(self, self._changed)
        self.refresh()
        follow_changes(self, self._changed, lambda: [self.font])

    def reload(self) -> bool:
        """Discard the typed draft: show the typed pair's stored value, or clear."""
        if self.closed:
            return False
        typed = (self.left_control.text, self.right_control.text)
        try:
            stored = typed in self._pairs()
        except Exception:  # noqa: BLE001 - refresh reports a closed document
            stored = False
        if stored:
            return self.refresh(typed)
        self.selected, self._shown = None, ("", "", "")
        for control in (self.left_control, self.right_control, self.value_control):
            control.setText("")
        return self.refresh()

    def _staged(self) -> bool:
        """Typed key/value text that differs from the pair last shown."""
        typed = (
            self.left_control.text,
            self.right_control.text,
            self.value_control.text,
        )
        return typed != self._shown

    def _changed(self) -> None:
        """FontLab changed a document: reload the list; keep typed key/value text."""
        if self.closed:
            return
        if not self._staged():
            self.refresh()
            return
        typed = [
            c.text for c in (self.left_control, self.right_control, self.value_control)
        ]
        if self.refresh():
            for control, text in zip(
                (self.left_control, self.right_control, self.value_control),
                typed,
                strict=True,
            ):
                control.setText(text)
            self.inspect()
            self.diagnostic.setText(
                f"Changed in FontLab; typed pair kept, Reload shows the font. {self.diagnostic.text}"
            )

    def _pairs(self) -> Any:
        """The borrowed ``font.kerning``; raise ``ValueError`` without a font."""
        if self.font is None:
            raise ValueError("No font supplied")
        return self.font.kerning

    def _unavailable(self, error: Exception) -> None:
        """Show ``error`` in the preview and status; disable every control."""
        self.editable = False
        for control in (
            self.pair_list,
            self.filter_control,
            self.left_control,
            self.right_control,
            self.value_control,
            self.apply_button,
            self.delete_button,
            self.reload_button,
        ):
            control.setEnabled(False)
        self.preview.fail(error)
        self.preview.canvas.update()
        self.diagnostic.setText(str(error))

    def fill(self) -> None:
        if self.closed:
            return
        try:
            pairs = dict(self._pairs())
        except Exception as exc:  # noqa: BLE001 - borrowed document boundary
            self._unavailable(exc)
            return
        query = self.filter_control.text.casefold()
        self.rows = [
            pair for pair in sorted(pairs) if query in " ".join(pair).casefold()
        ]
        self.pair_list.blockSignals(True)
        try:
            self.pair_list.clear()
            self.pair_list.addItems(
                [f"{a} | {b} | {number_text(pairs[a, b])}" for a, b in self.rows]
            )
            self.pair_list.setCurrentRow(
                self.rows.index(self.selected) if self.selected in self.rows else -1
            )
        finally:
            self.pair_list.blockSignals(False)

    def refresh(self, selected: tuple[str, str] | None = None) -> bool:
        if self.closed:
            return False
        self.preview._invalidate_for_refresh()
        try:
            pairs = self._pairs()
            values = dict(pairs)
            self.editable = callable(getattr(pairs, "apply", None))
        except Exception as exc:  # noqa: BLE001 - borrowed model may be closed
            self._unavailable(exc)
            return False
        self.selected = selected if selected is not None else self.selected
        for control in (self.left_control, self.right_control, self.value_control):
            control.setEnabled(True)
            control.setReadOnly(not self.editable)
        self.apply_button.setEnabled(self.editable)
        self.fill()
        if self.selected in values:
            self._show(self.selected, values[self.selected])
        independent_proof = not (self.left_control.text or self.right_control.text)
        self.inspect()
        if independent_proof:
            self.preview.refresh()
        return True

    def _show(self, pair: tuple[str, str], value: float) -> None:
        """Put ``pair`` and ``value`` in the edit fields and remember them."""
        self._shown = (pair[0], pair[1], number_text(value))
        self.left_control.setText(pair[0])
        self.right_control.setText(pair[1])
        self.value_control.setText(self._shown[2])

    def select(self, row: int) -> None:
        if self.closed or not 0 <= row < len(self.rows):
            return
        self.selected = self.rows[row]
        try:
            self._show(self.selected, self._pairs()[self.selected])
        except Exception as exc:  # noqa: BLE001 - selection can outlive a pair
            self.diagnostic.setText(str(exc))
        self.inspect()

    def inspect(self) -> None:
        if self.closed:
            return
        if not (self.left_control.text or self.right_control.text):
            # A fresh editor has no pair yet: prompt instead of a validation error.
            self.delete_button.setEnabled(False)
            self.diagnostic.setText(EMPTY_PAIR_TEXT)
            return
        try:
            pair = (self.left_control.text, self.right_control.text)
            pairs, groups = dict(self._pairs()), dict(self.font.groups)
            detail = inspect_kerning(pairs, groups, pair)
            status = (
                f"Explicit value: {number_text(detail['value'])}"
                if detail["explicit"]
                else "No explicit pair"
            )
            names = [groups[name][0] if groups.get(name) else name for name in pair]
            text = " ".join("/" + name for name in names)
            parts = [status, "effective: " + _value(detail["effective"])]
            if names != list(pair):
                shown = inspect_kerning(pairs, groups, tuple(names))["effective"]
                parts.append(f"preview {text}: {_value(shown)}")
            self.diagnostic.setText(
                ("Read-only. " if not self.editable else "") + "; ".join(parts)
            )
            self.preview.text_control.setText(text)
            self.preview.refresh()
            self.delete_button.setEnabled(self.editable and detail["explicit"])
        except Exception as exc:  # noqa: BLE001 - invalid staged keys stay editable
            self.delete_button.setEnabled(False)
            self.diagnostic.setText(str(exc))
            self.preview.fail(exc)
            self.preview.canvas.update()

    def edit(self, action: str) -> bool:
        if self.closed:
            return False
        try:
            pairs = self._pairs()
            before = dict(pairs)
        except Exception as exc:  # noqa: BLE001 - disable a closed document
            self._unavailable(exc)
            return False
        try:
            _require_apply(pairs)
            pair = (self.left_control.text, self.right_control.text)
            value = float(self.value_control.text) if action == "apply" else None
            values = apply_kerning(
                self.font, action, pair, value, undo_name="Edit font kerning",
                pairs=pairs, before=before,
            )
            if values is None:
                self.diagnostic.setText("No changes to apply.")
                return False
        except Exception as exc:  # noqa: BLE001 - show staging/native failures
            self.diagnostic.setText(str(exc))
            return False
        self.refresh(pair)
        if self.on_apply is not None:
            try:
                self.on_apply(self.font, dict(values))
            except Exception as exc:  # noqa: BLE001 - consumer callback boundary
                if not self.closed:
                    self.diagnostic.setText(
                        f"Applied kerning; refresh callback failed: {exc}"
                    )
        return True

    def close(self) -> None:
        self.on_apply = None
        return self._close_with_child(getattr(self, "preview", None))
