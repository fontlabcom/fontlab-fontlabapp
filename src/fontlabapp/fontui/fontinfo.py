# this_file: src/fontlabapp/fontui/fontinfo.py
# SPDX-License-Identifier: Apache-2.0
"""Original staged information form; Fontport owns validation and history."""

from collections.abc import Callable
from math import isfinite
from typing import Any, ClassVar

from ._fontport import require_fontport

with require_fontport(__name__):
    from fontlab_fontport.info import INTEGER_FIELDS, METRIC_FIELDS, stage_info
from PythonQt import QtGui

from .lifecycle import Owned, follow_changes
from fontlabapp.qt.compact import compact_layout

UNDO_NAME = "Font information"


# Structured fields with a native route (Fontport 1.x writes the key master).
# openTypeNameRecords is left out: Fontport refuses it (no persisted route).
INTEGER_LISTS = frozenset(("openTypeOS2Panose",))
NUMBER_LISTS = frozenset(("postscriptStemSnapH", "postscriptStemSnapV"))
INTEGER_CLASSES = frozenset(("openTypeOS2WeightClass", "openTypeOS2WidthClass"))


def _number_text(value: Any) -> str:
    """Show an integral float without ``.0``; other values unchanged."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _display(name: str, value: Any) -> str:
    """Field text for ``value``: empty for None, numbers and lists normalized."""
    if value is None:
        return ""
    if name in INTEGER_LISTS | NUMBER_LISTS:
        return " ".join(_number_text(v) for v in value)
    if name in INTEGER_FIELDS | INTEGER_CLASSES:
        return _number_text(value)
    return str(value)


def _integer(text: str) -> int:
    """Exact integer: optional leading '-', then decimal digits (any script)."""
    token = text.strip()
    digits = token.removeprefix("-")
    if not digits.isdecimal():
        raise ValueError(f"{text!r} is not an integer")
    return int(token)


def _number(text: str) -> int | float:
    """Parse a finite number; integral values become ``int``."""
    value = float(text)
    if not isfinite(value):
        raise ValueError(f"{text!r} is not a finite number")
    return int(value) if value.is_integer() else value


def _parse(name: str, text: str) -> Any:
    """Typed value for a field's text; blank means absent (or no stems)."""
    if name in INTEGER_LISTS:
        return [_integer(part) for part in text.split()] if text.strip() else None
    if name in NUMBER_LISTS:
        return [_number(part) for part in text.split()]
    if name in INTEGER_FIELDS | INTEGER_CLASSES:
        return _integer(text) if text.strip() else None
    if name in METRIC_FIELDS:
        return float(text) if text.strip() else None
    return text


class FontInfoEditor(Owned):
    """Own the form, borrow its font, and never mutate during typing or Revert."""

    FIELD_LABELS: ClassVar[dict[str, str]] = {
        "familyName": "&Family name",
        "styleName": "&Style name",
        "unitsPerEm": "&Units per em (integer)",
        "ascender": "&Ascender",
        "descender": "&Descender",
        "capHeight": "&Cap height",
        "xHeight": "&X height",
        "italicAngle": "&Italic angle",
        "versionMajor": "&Major version (integer)",
        "versionMinor": "Mi&nor version (integer)",
        "note": "N&ote",
        "copyright": "Copy&right",
        "trademark": "&Trademark",
        "openTypeNameDesigner": "Desi&gner",
        "openTypeNameDesignerURL": "Designer URL",
        "openTypeNameManufacturer": "Manufactur&er",
        "openTypeNameManufacturerURL": "Manufacturer URL",
        "openTypeNameLicense": "&License",
        "openTypeNameLicenseURL": "License URL",
        "openTypeOS2WeightClass": "OS/2 &weight class (key master)",
        "openTypeOS2WidthClass": "OS/2 widt&h class (key master)",
        "openTypeOS2Panose": "&Panose, 10 integers (key master)",
        "postscriptStemSnapH": "Horizontal stems (key master)",
        "postscriptStemSnapV": "Vertical stems (key master)",
    }
    MULTILINE = frozenset(("note", "copyright", "trademark", "openTypeNameLicense"))

    def __init__(
        self,
        font: Any,
        parent: Any = None,
        on_apply: Callable[[Any, dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        compact_layout(self.layout)  # FontLab panel metrics, issue 253
        self.font, self.on_apply = font, on_apply
        self.fields: dict[str, Any] = {}
        self.source_text: dict[str, str] = {}
        scroll = QtGui.QScrollArea(self.widget)
        scroll.setWidgetResizable(True)
        content = QtGui.QWidget(scroll)
        form = QtGui.QFormLayout(content)
        scroll.setWidget(content)
        self.layout.addWidget(scroll)
        for name, label in self.FIELD_LABELS.items():
            cls = QtGui.QPlainTextEdit if name in self.MULTILINE else QtGui.QLineEdit
            editor = cls(content)
            if name in self.MULTILINE:
                editor.setMaximumHeight(90)
            else:
                editor.setMaxLength(2147483647)
            editor.setAccessibleName(label.replace("&", ""))
            editor.setPlaceholderText("Not set")
            caption = QtGui.QLabel(label, content)
            caption.setBuddy(editor)
            form.addRow(caption, editor)
            self.fields[name] = editor
        actions = QtGui.QHBoxLayout()
        self.layout.addLayout(actions)
        self.apply_button = QtGui.QPushButton("&Apply", self.widget)
        self.revert_button = QtGui.QPushButton("Re&vert", self.widget)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.revert_button)
        self.diagnostic = QtGui.QLabel(self.widget)
        self.diagnostic.setWordWrap(True)
        self.layout.addWidget(self.diagnostic)
        self.connect(self.apply_button.clicked, lambda *args: self.apply())
        self.connect(self.revert_button.clicked, lambda *args: self.refresh())
        self.refresh()
        follow_changes(self, self._changed, lambda: [self.font])

    def _staged(self) -> bool:
        """True when any field text differs from the loaded source text."""
        return any(
            (e.toPlainText() if n in self.MULTILINE else e.text)
            != self.source_text.get(n)
            for n, e in self.fields.items()
        )

    def _changed(self) -> None:
        """FontLab changed a document: reload, unless that would drop staged edits."""
        if self.closed:
            return
        if self._staged():
            self._say(
                "Changed in FontLab; Revert reloads it (staged edits kept)."
            )
        else:
            applied, before = self.diagnostic.text, dict(self.source_text)
            self.refresh()
            if applied.startswith("Applied font information") and self.source_text == before:
                self._say(applied)  # our own Apply echoed back; keep its status

    def _info(self) -> Any:
        """The borrowed ``font.info``; raise ``ValueError`` without a font."""
        if self.font is None:
            raise ValueError("No font supplied")
        return self.font.info

    def _unavailable(self, error: Exception) -> None:
        """Show ``error`` and disable Apply and every field."""
        self._say(str(error))
        self.apply_button.setEnabled(False)
        for editor in self.fields.values():
            editor.setEnabled(False)

    def _say(self, text: str) -> None:
        """Replace the diagnostic text and drop any stale tooltip."""
        self.diagnostic.setText(text)
        self.diagnostic.setToolTip("")

    def _metric_hint(self) -> tuple[str, str]:
        """Return (visible note, tooltip) for blank metrics.

        The backend's ``info.clearOptionalMetric`` capability supplies the technical
        reason as the tooltip; backends without ``capabilities()`` (or failing ones)
        get the note and no tooltip.
        """
        note = " FontLab can't clear a blank metric; enter a value instead."
        try:
            entry = self.font.capabilities().get("info.clearOptionalMetric")
        except Exception:  # noqa: BLE001 - optional backend capability boundary
            return note, ""
        if not isinstance(entry, dict):
            return note, ""
        if entry.get("supported"):
            return "", ""
        return note, str(entry.get("reason") or "")

    def refresh(self) -> bool:
        """Discard staged values and read actual information; return availability."""
        if self.closed:
            return False
        try:
            info = self._info()
            values = {name: getattr(info, name) for name in self.fields}
            editable = callable(getattr(info, "apply", None))
        except Exception as exc:  # noqa: BLE001 - borrowed model boundary
            self._unavailable(exc)
            return False
        self.source_text = {
            name: _display(name, value) for name, value in values.items()
        }
        for name, editor in self.fields.items():
            editor.setEnabled(True)
            editor.setReadOnly(not editable)
            setter = editor.setPlainText if name in self.MULTILINE else editor.setText
            setter(self.source_text[name])
        self.apply_button.setEnabled(editable)
        hint, reason = self._metric_hint() if editable else ("", "")
        self._say(
            f"Edits are staged until Apply.{hint}"
            if editable
            else "Font information is read-only: model has no batch info.apply."
        )
        self.diagnostic.setToolTip(reason)
        return True

    revert = refresh

    def _changes(self) -> dict[str, Any]:
        """Validate the edited fields one by one; return the staged batch."""
        changes = {}
        for name, editor in self.fields.items():
            text = editor.toPlainText() if name in self.MULTILINE else editor.text
            if text == self.source_text[name]:
                continue
            try:
                changes.update(stage_info({name: _parse(name, text)}, UNDO_NAME))
            except (TypeError, ValueError, NotImplementedError) as exc:
                editor.setFocus()
                raise ValueError(f"{name}: {exc}") from exc
        return stage_info(changes, UNDO_NAME)

    def apply(self) -> bool:
        """Validate the entire staged mapping, then invoke one backend batch."""
        if self.closed:
            return False
        try:
            info = self._info()
            # Reading also detects a document closed after the last refresh.
            actual = {name: getattr(info, name) for name in self.fields}
        except Exception as exc:  # noqa: BLE001 - borrowed document may be closed
            self._unavailable(exc)
            return False
        if not callable(getattr(info, "apply", None)):
            self._say(
                "Font information is read-only: model has no batch info.apply."
            )
            self.apply_button.setEnabled(False)
            return False
        try:
            changes = self._changes()
            changes = {
                name: value for name, value in changes.items() if actual[name] != value
            }
            if not changes:
                self._say("No changes to apply.")
                return False
            info.apply(changes, undo_name=UNDO_NAME)
        except Exception as exc:  # noqa: BLE001 - keep batch failures out of Qt slots
            self._say(str(exc))
            return False
        self.refresh()
        self._say("Applied font information.")
        if self.on_apply is not None:
            try:
                self.on_apply(self.font, dict(changes))
            except Exception as exc:  # noqa: BLE001 - consumer callback boundary
                if not self.closed:
                    self._say(
                        f"Applied font information; refresh callback failed: {exc}"
                    )
        return True

    def close(self) -> None:
        self.on_apply = None
        super().close()
