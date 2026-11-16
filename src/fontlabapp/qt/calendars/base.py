# this_file: src/fontlabapp/qt/calendars/base.py
# SPDX-License-Identifier: Apache-2.0
"""Share injected-Qt calendar fields, owned callbacks and coherent date limits."""

from collections.abc import Callable
from typing import Any

import fontlabapp.qt.properties as _qt_properties
from fontlabapp.qt.calendars.classic.formats import surface


def value(owner: Any, name: str) -> Any:
    """Read a PythonQt property or external binding's no-argument getter."""
    return _qt_properties.value(owner, name)


class CalendarBase:
    """Keep UI mechanics shared; each lesson supplies its complete option policy."""

    def __init__(
        self,
        qt: Any,
        parent: Any,
        connect: Callable[..., None],
        *,
        maximum: tuple[int, int, int] = (2100, 12, 31),
    ) -> None:
        self.qt, self._connect = qt, connect
        self._closed, self._marked = False, ()
        self.combos, self.checks, self.dates = {}, {}, {}
        gui, core = qt.QtGui, qt.QtCore
        self.widget = gui.QWidget(parent)
        try:
            layout = gui.QHBoxLayout(self.widget)
            layout.setContentsMargins(0, 0, 0, 0)
            self.calendar = gui.QCalendarWidget(self.widget)
            surface(qt, self.calendar)
            self.calendar.setDateRange(core.QDate(1900, 1, 1), core.QDate(*maximum))
            layout.addWidget(self.calendar, 1)
            self.form = gui.QFormLayout()
            layout.addLayout(self.form)
        except BaseException:
            self._abort()
            raise

    def _abort(self) -> None:
        self.close()
        self.widget.deleteLater()

    def _make_dates(
        self, *, display_format: str = "yyyy-MM-dd", source_limits: bool = False
    ) -> None:
        gui, core = self.qt.QtGui, self.qt.QtCore
        limits = (
            (value(self.calendar, "minimumDate"), value(self.calendar, "maximumDate"))
            if source_limits
            else (core.QDate(1, 1, 1), core.QDate(9999, 12, 31))
        )
        for key in ("selected", "minimum", "maximum"):
            edit = gui.QDateEdit(self.widget)
            edit.setCalendarPopup(True)
            edit.setDisplayFormat(display_format)
            edit.setDateRange(*limits)
            self.dates[key] = edit
            self.form.addRow(key.title(), edit)
            self._link(edit.dateChanged, lambda day, k=key: self._date(k, day))

    def _link(self, signal: Any, action: Callable[..., None]) -> None:
        def slot(*args: Any) -> None:
            if not self._closed:
                action(*args)

        self._connect(signal, slot)

    def _combo(
        self,
        key: str,
        label: str,
        choices: tuple[str, ...],
        action: Callable[..., None],
    ) -> None:
        combo = self.qt.QtGui.QComboBox(self.widget)
        combo.addItems(list(choices))
        self.combos[key] = combo
        self.form.addRow(label, combo)
        self._link(combo.currentIndexChanged, action)

    def _check(
        self, key: str, label: str, checked: bool, action: Callable[..., None]
    ) -> None:
        check = self.qt.QtGui.QCheckBox(label, self.widget)
        check.setChecked(checked)
        self.checks[key] = check
        self.form.addRow(check)
        self._link(check.toggled, action)

    def _date(self, key: str, day: Any) -> None:
        setter = {
            "selected": self.calendar.setSelectedDate,
            "minimum": self.calendar.setMinimumDate,
            "maximum": self.calendar.setMaximumDate,
        }[key]
        setter(day)
        self._sync_dates()

    def _sync_dates(self, *args: Any) -> None:
        minimum, maximum = (
            value(self.calendar, "minimumDate"),
            value(self.calendar, "maximumDate"),
        )
        for key, name in (
            ("selected", "selectedDate"),
            ("minimum", "minimumDate"),
            ("maximum", "maximumDate"),
        ):
            edit = self.dates[key]
            previous = edit.blockSignals(True)
            try:
                if key == "selected":
                    edit.setDateRange(minimum, maximum)
                edit.setDate(value(self.calendar, name))
            finally:
                edit.blockSignals(previous)

    def close(self) -> None:
        """Fence queued callbacks; the caller still disconnects owned pairs."""
        self._closed, self._marked = True, ()
        self._connect = None
