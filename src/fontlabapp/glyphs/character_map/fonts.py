# this_file: src/fontlabapp/glyphs/character_map/fonts.py
# SPDX-License-Identifier: Apache-2.0
"""The two originals' deliberately different typography and signal contracts."""

from typing import Any

from fontlabapp.qt.properties import value


class TextSignal:
    """Own the Qt5 QString overload, with an index-event adapter on Qt6."""

    def __init__(self, widget: Any, name: str) -> None:
        self.widget, self.name = widget, name
        self.slots: dict = {}

    def connect(self, slot: Any) -> Any:
        signal = getattr(self.widget, self.name)
        if type(self.widget).__module__.startswith("PythonQt"):
            return self.widget.connect(self.name + "(QString)", slot)
        try:
            selected = signal[str]
        except (KeyError, TypeError, IndexError):

            def changed(*args: Any) -> None:
                slot(value(self.widget, "currentText"))

            self.slots[slot] = changed
            return signal.connect(changed)
        self.slots[slot] = (selected, slot)
        return selected.connect(slot)

    def disconnect(self, slot: Any) -> Any:
        if type(self.widget).__module__.startswith("PythonQt"):
            return self.widget.disconnect(self.name + "(QString)", slot)
        record = self.slots.get(slot)
        signal, target = (
            record
            if isinstance(record, tuple)
            else (getattr(self.widget, self.name), record)
        )
        result = signal.disconnect(target)
        if result is not False:
            self.slots.pop(slot, None)
        return result


def resize_grid(panel: Any, gui: Any, *, recalculate: bool = True) -> None:
    grid = panel.grid
    if recalculate:
        grid.cell = max(
            24, int(value(gui.QFontMetrics(grid.display_font), "xHeight")) * 3
        )
    # PythonQt's native adjustSize does not dispatch our Python sizeHint.
    grid.resize(grid.sizeHint())
    grid.update()


def typography(panel: Any, gui: Any) -> None:
    """Part2 applies every visible choice immediately, with fixed cell sizing."""
    font = gui.QFont(value(panel.family, "currentFont"))
    point_size, style = (
        int(value(panel.size_control, "value")),
        value(panel.style_control, "currentIndex"),
    )
    font.setPointSize(point_size)
    font.setBold(style == 1)
    font.setItalic(style == 2)
    font.setStyleStrategy(
        gui.QFont.PreferDefault
        if value(panel.merging, "isChecked")
        else gui.QFont.NoFontMerging
    )
    panel.grid.display_font, panel.grid.cell = font, max(20, point_size * 2 + 8)
    panel.grid.setFixedSize(panel.grid.cell * 16, panel.grid.cell * 4096)
    panel.grid.update()


def find_styles(panel: Any, gui: Any, font: Any) -> None:
    previous = value(panel.style_control, "currentText")
    panel.style_control.clear()
    panel.style_control.addItems(gui.QFontDatabase().styles(value(font, "family")))
    panel.style_control.setCurrentIndex(max(0, panel.style_control.findText(previous)))


def find_sizes(panel: Any, gui: Any, font: Any) -> None:
    """Constructor-only original sizing; no invented family-change refresh."""
    previous = value(panel.size_control, "currentText")
    database = gui.QFontDatabase()
    panel.size_control.blockSignals(True)
    try:
        panel.size_control.clear()
        family, style = value(font, "family"), database.styleString(font)
        scalable = database.isSmoothlyScalable(family, style)
        sizes = (
            database.standardSizes()
            if scalable
            else database.smoothSizes(family, style)
        )
        for size in sizes:
            panel.size_control.addItem(str(size))
            panel.size_control.setEditable(scalable)
    finally:
        panel.size_control.blockSignals(False)
    index = panel.size_control.findText(previous)
    panel.size_control.setCurrentIndex(
        index if index >= 0 else max(0, value(panel.size_control, "count") // 3)
    )


def change(panel: Any, gui: Any, kind: str, argument: Any) -> None:
    """Apply part3 events without conflating displayed and activated choices."""
    grid, font = panel.grid, panel.grid.display_font
    if kind == "family":
        font.setFamily(argument)
    elif kind == "size":
        try:
            size = int(argument)
        except (TypeError, ValueError):
            panel.failure(ValueError("Font size must be an integer"))
            return
        font.setPointSize(size)
    elif kind == "style":
        strategy = value(font, "styleStrategy")
        grid.display_font = gui.QFontDatabase().font(
            value(font, "family"), argument, value(font, "pointSize")
        )
        grid.display_font.setStyleStrategy(strategy)
    elif kind == "merging":
        font.setStyleStrategy(
            gui.QFont.PreferDefault if argument else gui.QFont.NoFontMerging
        )
    else:
        raise ValueError("Unknown reference-font change.")
    resize_grid(panel, gui, recalculate=kind != "merging")


def connect(panel: Any, gui: Any) -> None:
    scope = panel.scope
    if panel.part == 2:
        for signal in (
            panel.family.currentFontChanged,
            panel.style_control.currentIndexChanged,
            panel.size_control.valueChanged,
            panel.merging.toggled,
        ):
            scope.connect(signal, lambda *args: typography(panel, gui))
        typography(panel, gui)
        return
    find_styles(panel, gui, value(panel.family, "currentFont"))
    find_sizes(panel, gui, value(panel.family, "currentFont"))
    scope.connect(
        panel.family.currentFontChanged, lambda font: find_styles(panel, gui, font)
    )
    for widget, signal, kind in (
        (panel.family, "activated", "family"),
        (panel.style_control, "activated", "style"),
        (panel.size_control, "currentIndexChanged", "size"),
    ):
        scope.connect(
            TextSignal(widget, signal),
            lambda text, kind=kind: change(panel, gui, kind, text),
        )
    scope.connect(
        panel.merging.toggled, lambda enabled: change(panel, gui, "merging", enabled)
    )
