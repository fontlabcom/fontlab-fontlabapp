# this_file: src/fontlabapp/fontui/features.py
# SPDX-License-Identifier: Apache-2.0
"""Original staged feature-code editor over a borrowed duck-typed font model."""

from collections.abc import Callable
from typing import Any

from fontlabapp.fontui.features_state import PREFIX, FeatureState
from fontlabapp.fontui.features_view import build
from fontlabapp.fontui.lifecycle import Owned, follow_changes, follow_history
from fontlabapp.qt.compact import compact_layout

UNDO_NAME = "Edit font features"
READ_ONLY = "Feature code is read-only: model has no features.set_blocks or apply."


class FeaturesEditor(Owned):
    """Edit the prefix and each feature block; Apply writes them in one batch.

    Models with features.get_blocks/set_blocks (Fontport) are edited block by
    block; other models with features.apply edit one whole text. Code is stored,
    never compiled or executed; each block keeps its own line ending. FontLab's
    Undo/Redo actions reload the editor.
    """

    def __init__(
        self,
        font: Any,
        parent: Any = None,
        on_apply: Callable[[Any, str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        compact_layout(self.layout)  # FontLab panel metrics, issue 253
        self.font, self.on_apply = font, on_apply
        self.state, self.key, self.blocks, self.editable = None, PREFIX, False, False
        build(self)
        self.connect(self.text_control.textChanged, lambda *a: self._mark())
        self.connect(self.block_control.currentIndexChanged, lambda *a: self._switch())
        self.connect(self.add_button.clicked, lambda *a: self.add_feature())
        self.connect(self.remove_button.clicked, lambda *a: self.remove_feature())
        self.connect(self.apply_button.clicked, lambda *a: self.apply())
        self.connect(self.revert_button.clicked, lambda *a: self.refresh())
        follow_history(self, self._changed)
        self.refresh()
        follow_changes(self, self._changed, lambda: [self.font])

    def _changed(self) -> None:
        """FontLab changed a document: reload, unless that would drop staged text."""
        if self.closed:
            return
        if self.dirty:
            self.diagnostic.setText(
                "Changed in FontLab; Revert reloads it (staged edits kept)."
            )
        else:
            self.refresh()

    @property
    def dirty(self) -> bool:
        if self.closed or self.state is None:
            return False
        try:
            text = self.text_control.source_text()
        except ValueError:
            return True
        return self.state.dirty or text != self.state.text(self.key)

    def _features(self) -> Any:
        if self.font is None:
            raise ValueError("No font supplied")
        return self.font.features

    def _read(self, features: Any) -> dict:
        if self.blocks:
            return features.get_blocks()
        return {"prefix": features.text or "", "features": []}

    def _show(self, key: str | None = None) -> bool:
        keys = self.state.keys()
        selected = key if key in keys else PREFIX
        if not self.text_control.load_source(self.state.text(selected)):
            self.diagnostic.setText(
                self.text_control.diagnostic or "Feature source reload refused."
            )
            return False
        self.key = selected
        blocked = self.block_control.blockSignals(True)
        try:
            self.block_control.clear()
            self.block_control.addItems(keys if self.blocks else ["Feature text"])
            self.block_control.setCurrentIndex(keys.index(self.key))
        finally:
            self.block_control.blockSignals(blocked)
        self.remove_button.setEnabled(
            self.editable and self.blocks and self.key != PREFIX
        )
        self._mark()
        return True

    def _stash(self) -> None:
        """Read admitted intent before staging; preserve refused drafts unchanged."""
        text = self.text_control.source_text()
        self.state.set_text(self.key, text)

    def _switch(self) -> None:
        from fontlabapp.qt.properties import value

        if self.closed or self.state is None:
            return
        selected = self.state.keys()[value(self.block_control, "currentIndex")]
        try:
            self._stash()
        except ValueError as exc:
            self.diagnostic.setText(str(exc))
        else:
            if self._show(selected):
                return
        blocked = self.block_control.blockSignals(True)
        try:
            self.block_control.setCurrentIndex(self.state.keys().index(self.key))
        finally:
            self.block_control.blockSignals(blocked)

    def _mark(self) -> None:
        if self.closed:
            return
        self.status.setText("Modified, not applied" if self.dirty else "Unmodified")
        self.apply_button.setEnabled(self.editable and self.dirty)

    def _unavailable(self, error: Exception) -> None:
        self.editable = False
        for control in (
            self.text_control,
            self.apply_button,
            self.revert_button,
            self.add_button,
            self.remove_button,
            self.block_control,
        ):
            control.setEnabled(False)
        self.diagnostic.setText(str(error))

    def refresh(self) -> bool:
        """Explicitly discard staged edits and load the captured font's source."""
        self._read_only_reason = READ_ONLY
        if self.closed:
            return False
        try:
            features = self._features()
            self.blocks = all(
                callable(getattr(features, n, None))
                for n in ("get_blocks", "set_blocks")
            )
            self.editable = self.blocks or callable(getattr(features, "apply", None))
            loaded = self._read(features)
            tags = [tag for tag, _ in loaded["features"]]
            if len(tags) != len(set(tags)):
                loaded = {
                    "prefix": loaded["prefix"] + "".join(code for _, code in loaded["features"]),
                    "features": [],
                }
                self.editable = False
                self._read_only_reason = (
                    "Duplicate feature tags cannot be edited by occurrence; inspect only."
                )
            self.state = FeatureState(loaded)
        except Exception as exc:  # noqa: BLE001 - borrowed document boundary
            self._unavailable(exc)
            return False
        for control in (self.text_control, self.revert_button, self.block_control):
            control.setEnabled(True)
        self.text_control.setReadOnly(not self.editable)
        for control in (self.tag_control, self.add_button):
            control.setEnabled(self.editable and self.blocks)
        if not self._show(self.key):
            return False
        self.diagnostic.setText(
            self._read_only_reason if self._read_only_reason != READ_ONLY
            else "Original source contains unsupported paragraph markers; inspect only."
            if self.text_control.ambiguous
            else "Edits are staged until Apply." if self.editable else READ_ONLY
        )
        return True

    revert = refresh

    def add_feature(self) -> bool:
        try:
            self._stash()
            tag = self.tag_control.text.strip()
            self.state.add(tag)
        except (ValueError, AttributeError) as exc:
            self.diagnostic.setText(str(exc))
            return False
        self.tag_control.setText("")
        self._show(tag)
        return True

    def remove_feature(self) -> bool:
        try:
            self._stash()
            self.state.remove(self.key)
        except (ValueError, AttributeError) as exc:
            self.diagnostic.setText(str(exc))
            return False
        self._show(PREFIX)
        return True

    def apply(self) -> bool:
        """Write all staged blocks in one backend call and verify the readback."""
        if self.closed or self.state is None:
            return False
        try:
            features = self._features()
            features.text  # noqa: B018 - detect a document closed since refresh
        except Exception as exc:  # noqa: BLE001 - borrowed document may be closed
            self._unavailable(exc)
            return False
        try:
            if not self.editable:
                raise TypeError(getattr(self, "_read_only_reason", READ_ONLY))
            self._stash()
            if not self.state.dirty:
                self.diagnostic.setText("No changes to apply.")
                return False
            wanted, text = self.state.value(), self.state.whole_text()
            if self.blocks:
                features.set_blocks(wanted, undo_name=UNDO_NAME)
            else:
                features.apply(text, undo_name=UNDO_NAME)
            if FeatureState(self._read(features)).loaded != FeatureState(wanted).loaded:
                raise RuntimeError("Backend feature code differs from the applied code")
        except Exception as exc:  # noqa: BLE001 - keep backend failures out of Qt slots
            self.diagnostic.setText(str(exc))
            return False
        self.refresh()
        self.diagnostic.setText("Applied feature code (not compiled).")
        if self.on_apply is not None:
            try:
                self.on_apply(self.font, text)
            except Exception as exc:  # noqa: BLE001 - consumer callback boundary
                if not self.closed:
                    self.diagnostic.setText(f"Applied; refresh callback failed: {exc}")
        return True

    def close(self) -> None:
        self.on_apply = None
        super().close()
