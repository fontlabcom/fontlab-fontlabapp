# this_file: src/fontlabapp/glyphs/identity_tools/glyph_labels/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Stage palette and tag choices before the shared shell's explicit Apply."""
from typing import Any


def disconnect(panel: Any, signals: tuple[Any, ...]) -> None:
    for signal, slot in list(panel._connections):
        if signal in signals:
            signal.disconnect(slot)
            panel._connections.remove((signal, slot))


def tags(parent: Any) -> Any:
    from PythonQt import QtGui

    from .glyph_tags import _dialog_type

    panel = _dialog_type()(parent)
    disconnect(panel, (panel.tag.returnPressed, panel.add_button.clicked, panel.remove_button.clicked))
    panel.operation = QtGui.QComboBox(panel)
    panel.operation.addItems(["Add typed tag", "Remove checked tags"])
    panel.root.insertWidget(0, panel.operation)

    def apply():
        index = panel.operation.currentIndex
        index = index() if callable(index) else index
        return panel.add_tag() if index == 0 else panel.remove_ticked()

    panel.apply_staged = apply
    return panel


def marks(parent: Any) -> Any:
    from PythonQt import QtGui

    from .mark_color_palette import _dialog_type

    panel = _dialog_type()(parent)
    panel.mark_choice = QtGui.QComboBox(panel)
    panel.mark_choice.addItems(["Choose a mark"] + [str(mark) for mark in panel.swatches])
    panel.root.insertWidget(0, panel.mark_choice)
    disconnect(panel, tuple(button.clicked for button in panel.swatches.values()))

    def stage(value):
        panel.mark_choice.setCurrentIndex(list(panel.swatches).index(value) + 1)
        panel.status.setText(f"Mark {value} staged. Preview Changes, then Apply Changes.")

    for value, button in panel.swatches.items():
        panel._connect(button.clicked, lambda *args, value=value: stage(value))

    def apply():
        index = panel.mark_choice.currentIndex
        index = index() if callable(index) else index
        if index == 0:
            raise ValueError("Choose a mark colour first.")
        return panel.apply(list(panel.swatches)[index - 1])

    panel.apply_staged = apply
    return panel
