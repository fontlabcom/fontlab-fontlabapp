# this_file: src/fontlabapp/fontui/designspace.py
# SPDX-License-Identifier: Apache-2.0
"""Original axis/source controls over a borrowed Fontport Designspace."""

from collections.abc import Callable
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.fontui.lifecycle import Owned
from fontlabapp.qt.properties import value as qt_value

STEPS = 100  # slider ticks per user-coordinate unit (two decimals)


class DesignspacePanel(Owned):
    """Sliders and numeric fields stay synchronised; selection never edits fonts.

    on_location(location) receives Fontport's Location for every change. A
    source master is reported as a source only while all axes match it exactly;
    any other point is labelled an instance location.
    """

    def __init__(
        self,
        designspace: Any,
        parent: Any = None,
        on_location: Callable[[Any], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.designspace, self.on_location = designspace, on_location
        self.axes, self.current = {}, None
        self.entries = [*designspace.sources, *designspace.instances]
        form = QtGui.QFormLayout()
        self.layout.addLayout(form)
        for axis in designspace.axes:
            self._axis_row(form, axis)
        self.reset_button = QtGui.QPushButton("&Reset axes to defaults", self.widget)
        self.layout.addWidget(self.reset_button)
        caption = QtGui.QLabel("&Sources and instances", self.widget)
        self.location_list = QtGui.QListWidget(self.widget)
        self.location_list.setAccessibleName("Sources and instances")
        caption.setBuddy(self.location_list)
        self.layout.addWidget(caption)
        self.layout.addWidget(self.location_list)
        for entry in self.entries:
            text = f"{entry.kind.capitalize()}: {entry.name}"
            if not entry.available:
                text += f" (unavailable: {entry.reason})"
            self.location_list.addItem(text)
        self.status = QtGui.QLabel(self.widget)
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        self.connect(self.reset_button.clicked, lambda *args: self.reset())
        self.connect(self.location_list.currentRowChanged, self.select)
        self.reset()

    def _axis_row(self, form: Any, axis: Any) -> None:
        slider = QtGui.QSlider(QtCore.Qt.Horizontal, self.widget)
        slider.setRange(round(axis.minimum * STEPS), round(axis.maximum * STEPS))
        number = QtGui.QDoubleSpinBox(self.widget)
        number.setDecimals(2)
        number.setRange(axis.minimum, axis.maximum)
        for control in (slider, number):
            control.setAccessibleName(f"{axis.name} axis value")
        row = QtGui.QHBoxLayout()
        row.addWidget(slider)
        row.addWidget(number)
        label = QtGui.QLabel(
            f"{axis.name} ({axis.tag}) {axis.minimum:g}–{axis.maximum:g}, "
            f"default {axis.default:g}",
            self.widget,
        )
        label.setBuddy(number)
        form.addRow(label, row)
        self.axes[axis.name] = (slider, number)
        self.connect(slider.valueChanged, lambda *a, n=axis.name: self._slid(n))
        self.connect(number.valueChanged, lambda *a, n=axis.name: self._typed(n))

    def values(self) -> dict[str, float]:
        return {name: float(number.value) for name, (_, number) in self.axes.items()}

    def _set(self, values: dict[str, float]) -> None:
        for name, (slider, number) in self.axes.items():
            for control, value in (
                (slider, round(values[name] * STEPS)),
                (number, values[name]),
            ):
                blocked = control.blockSignals(True)
                try:
                    control.setValue(value)
                finally:
                    control.blockSignals(blocked)

    def _slid(self, name: str) -> None:
        slider, number = self.axes[name]
        blocked = number.blockSignals(True)
        try:
            number.setValue(slider.value / STEPS)
        finally:
            number.blockSignals(blocked)
        self._changed()

    def _typed(self, name: str) -> None:
        slider, number = self.axes[name]
        blocked = slider.blockSignals(True)
        try:
            slider.setValue(round(number.value * STEPS))
        finally:
            slider.blockSignals(blocked)
        self._changed()

    def _changed(self, entry: Any = None) -> None:
        if self.closed:
            return
        try:
            values = self.designspace.location(self.values())
            if entry is None:
                entry = next(
                    (
                        e
                        for e in self.designspace.sources
                        if dict(e.coordinates) == values
                    ),
                    None,
                )
            self.current = entry or self.designspace.instance(values)
        except Exception as exc:  # noqa: BLE001 - show Fontport validation errors
            self.status.setText(str(exc))
            return
        if entry is None:
            point = ", ".join(f"{name}={value:g}" for name, value in values.items())
            self.status.setText(f"Instance location (not a source master): {point}")
        else:
            kind = "Source master" if entry.kind == "source" else "Instance"
            self.status.setText(f"{kind}: {entry.name}")
        if self.on_location is not None:
            try:
                self.on_location(self.current)
            except Exception as exc:  # noqa: BLE001 - consumer callback boundary
                self.status.setText(f"{qt_value(self.status, 'text')}; callback failed: {exc}")

    def reset(self) -> None:
        if self.closed:
            return
        self._set(self.designspace.defaults())
        self._changed()

    def select(self, row: int) -> None:
        if self.closed or not 0 <= row < len(self.entries):
            return
        entry = self.entries[row]
        if not entry.available:
            self.status.setText(f"{entry.name} is unavailable: {entry.reason}")
            return
        self._set(dict(entry.coordinates))
        self._changed(entry)

    def close(self) -> None:
        self.on_location = None
        super().close()
