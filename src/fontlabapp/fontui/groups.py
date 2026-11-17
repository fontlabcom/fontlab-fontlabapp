# this_file: src/fontlabapp/fontui/groups.py
# SPDX-License-Identifier: Apache-2.0
"""Original explicit group actions over a borrowed FontParts model."""

from collections.abc import Callable
from typing import Any

from ._fontport import require_fontport

with require_fontport(__name__):
    from fontlab_fontport.groups import edit_groups

from .groups_view import build
from .lifecycle import Owned, follow_changes
from fontlabapp.qt.compact import compact_layout


class GroupsEditor(Owned):
    """Keep selection by group name; Fontport validates and executes each batch."""

    def __init__(
        self,
        font: Any,
        parent: Any = None,
        on_apply: Callable[[Any, Any], None] | None = None,
    ) -> None:
        super().__init__(parent)
        compact_layout(self.layout)  # FontLab panel metrics, issue 253
        self.font, self.on_apply = font, on_apply
        self.selected: str | None = None
        self.names: list[str] = []
        self.editable: bool = False
        build(self)
        self.connect(self.group_list.currentRowChanged, self.select)
        self.connect(self.member_list.itemSelectionChanged, self.preview_member)
        self.connect(self.reload_button.clicked, lambda *args: self.reload())
        self.refresh()
        follow_changes(self, self._changed, lambda: [self.font])

    def reload(self) -> bool:
        """Discard typed name and members and show the font's groups."""
        if self.closed:
            return False
        self.members_control.setText("")
        return self.refresh()

    def _staged(self) -> bool:
        """Typed group name or members that no action has used yet."""
        return self.name_control.text != (self.selected or "") or bool(
            self.members_control.text.strip()
        )

    def _changed(self) -> None:
        """FontLab changed a document: reload the lists; keep typed name/members."""
        if self.closed:
            return
        if not self._staged():
            self.refresh()
            return
        typed = (self.name_control.text, self.members_control.text)
        if self.refresh():
            self.name_control.setText(typed[0])
            self.members_control.setText(typed[1])
            self.diagnostic.setText(
                "Changed in FontLab; typed name and members kept. Reload clears them."
            )

    def _groups(self) -> Any:
        """The borrowed ``font.groups``; raise ``ValueError`` without a font."""
        if self.font is None:
            raise ValueError("No font supplied")
        return self.font.groups

    def _unavailable(self, error: Exception) -> None:
        """Show ``error``, clear the preview and disable every control."""
        self.selected, self.editable = None, False
        for control in (
            self.group_list,
            self.member_list,
            self.name_control,
            self.members_control,
            *self.buttons.values(),
        ):
            control.setEnabled(False)
        self.preview.set_glyph(None)
        self.diagnostic.setText(str(error))

    def _buttons(self) -> None:
        """Enable Add when editable, the other actions only with a selection."""
        for action, button in self.buttons.items():
            button.setEnabled(
                self.editable and (action == "add" or self.selected is not None)
            )

    def refresh(self, selected: str | None = None) -> bool:
        """Read actual groups, retaining an existing selection without edits."""
        if self.closed:
            return False
        try:
            groups = self._groups()
            self.names = sorted(groups)
            self.editable = callable(getattr(groups, "apply", None))
        except Exception as exc:  # noqa: BLE001 - borrowed model boundary
            self._unavailable(exc)
            return False
        selected = self.selected if selected is None else selected
        self.group_list.blockSignals(True)
        try:
            self.group_list.clear()
            self.group_list.addItems(self.names)
            self.group_list.setCurrentRow(
                self.names.index(selected) if selected in self.names else -1
            )
        finally:
            self.group_list.blockSignals(False)
        for control in (
            self.group_list,
            self.member_list,
            self.name_control,
            self.members_control,
        ):
            control.setEnabled(True)
        self.name_control.setReadOnly(not self.editable)
        self.members_control.setReadOnly(not self.editable)
        self.select(self.group_list.currentRow)
        self.diagnostic.setText(
            "Select a group. Each edit requires an explicit action."
            if self.editable
            else "Read-only: model has no groups.apply."
        )
        return True

    def select(self, row: int) -> None:
        if self.closed:
            return
        try:
            values = dict(self._groups())
            name = self.names[row] if 0 <= row < len(self.names) else None
            self.selected = name if name in values else None
            members = values.get(self.selected, ())
        except Exception as exc:  # noqa: BLE001 - a document may have closed
            self._unavailable(exc)
            return
        self.name_control.setText(self.selected or "")
        self.member_list.blockSignals(True)
        try:
            self.member_list.clear()
            self.member_list.addItems(list(members))
            if members:
                self.member_list.setCurrentRow(0)
        finally:
            self.member_list.blockSignals(False)
        self._buttons()
        self.preview_member()

    def preview_member(self) -> None:
        if not self.closed:
            items = self.member_list.selectedItems()
            self.preview.set_glyph(items[0].text() if items else None)

    def edit(self, action: str) -> bool:
        """Apply one explicit operation; callback receives (font, complete_groups)."""
        if self.closed:
            return False
        try:
            groups = self._groups()
            before = dict(groups)
        except Exception as exc:  # noqa: BLE001 - closed models disable editing
            self._unavailable(exc)
            return False
        try:
            if not callable(getattr(groups, "apply", None)):
                raise TypeError("Read-only: model has no groups.apply.")
            name = self.name_control.text.strip() if action == "add" else self.selected
            members = (
                [item.text() for item in self.member_list.selectedItems()]
                if action == "remove_members"
                else self.members_control.text.split()
            )
            values = edit_groups(
                before,
                action,
                name,
                new_name=self.name_control.text.strip(),
                members=members,
                available_glyphs=self.font.keys(),
            )
            if values == before:
                self.diagnostic.setText("No changes to apply.")
                return False
            groups.apply(values, undo_name="Edit font groups")
            if dict(groups) != values:
                raise RuntimeError(
                    "Backend groups readback differs from the requested edit"
                )
        except Exception as exc:  # noqa: BLE001 - native errors stay beside action
            self.diagnostic.setText(str(exc))
            return False
        selected = (
            self.name_control.text.strip()
            if action in {"add", "rename"}
            else self.selected
        )
        self.refresh(selected)
        self.diagnostic.setText("Applied font groups.")
        if self.on_apply is not None:
            try:
                self.on_apply(self.font, dict(values))
            except Exception as exc:  # noqa: BLE001 - callback is a consumer boundary
                if not self.closed:
                    self.diagnostic.setText(
                        f"Applied groups; refresh callback failed: {exc}"
                    )
        return True

    def close(self) -> None:
        self.on_apply = None
        return self._close_with_child(getattr(self, "preview", None))
