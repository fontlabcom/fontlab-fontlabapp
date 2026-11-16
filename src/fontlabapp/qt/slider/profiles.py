# this_file: src/fontlabapp/qt/slider/profiles.py
# SPDX-License-Identifier: Apache-2.0
"""Preserve distinct original range and feedback algorithms on native widgets."""

from typing import Any

from fontlabapp.qt.properties import value


def connect(owner: Any, signal: Any, call: Any) -> None:
    owner.scope.connect(signal, call)


def group(owner: Any, core: Any, gui: Any, orientation: Any = None) -> tuple:
    """Create three controls, preserving part2 defaults and part3 focus/ticks."""
    controls = (
        gui.QSlider(owner) if orientation is None else gui.QSlider(orientation, owner),
        gui.QScrollBar(owner)
        if orientation is None
        else gui.QScrollBar(orientation, owner),
        gui.QDial(owner),
    )
    if orientation is None:
        # Repair the original initial Horizontal label/default-Vertical mismatch.
        for control in controls[:2]:
            control.setOrientation(core.Qt.Horizontal)
        for control in controls:
            control.setRange(0, 20)
            control.setValue(5)
    else:
        for control in controls:
            control.setFocusPolicy(core.Qt.StrongFocus)
        controls[0].setTickPosition(gui.QSlider.TicksBothSides)
        controls[0].setTickInterval(10)
        controls[0].setSingleStep(1)
        for source, target in zip(
            controls, (controls[1], controls[2], controls[0]), strict=True
        ):
            connect(
                owner, source.valueChanged, lambda n, target=target: target.setValue(n)
            )
    return controls


def part2(owner: Any, core: Any) -> None:
    """Manual high normalization plus guarded bounded feedback; original order."""
    low, high, number = (owner.controls[n] for n in ("minimum", "maximum", "value"))
    sliders = owner.groups[0]
    busy = [False]

    def sync(n: int) -> None:
        if busy[0]:
            return
        busy[0] = True
        try:
            bounded = max(int(value(low, "value")), min(int(value(high, "value")), n))
            for control in (*sliders, number):
                control.setValue(bounded)
        finally:
            busy[0] = False

    def bounds(*args: Any) -> None:
        minimum = int(value(low, "value"))
        maximum = max(minimum, int(value(high, "value")))
        high.setValue(maximum)
        for control in sliders:
            control.setRange(minimum, maximum)
        sync(int(value(number, "value")))

    for control in (*sliders, number):
        connect(owner, control.valueChanged, sync)
    for control in (low, high):
        connect(owner, control.valueChanged, bounds)
    connect(
        owner,
        owner.controls["orientation"].currentIndexChanged,
        lambda i: [
            c.setOrientation(core.Qt.Horizontal if i == 0 else core.Qt.Vertical)
            for c in sliders[:2]
        ],
    )
    sync(5)


def part3(owner: Any) -> None:
    """Native cyclic feedback and clamping; range editors stay independent."""
    horizontal, vertical = owner.groups
    number = owner.controls["value"]
    connect(owner, horizontal[2].valueChanged, lambda n: vertical[0].setValue(n))
    connect(owner, vertical[2].valueChanged, lambda n: number.setValue(n))
    connect(owner, number.valueChanged, lambda n: horizontal[0].setValue(n))
    for key, method in (("minimum", "setMinimum"), ("maximum", "setMaximum")):
        for controls in owner.groups:
            connect(
                owner,
                owner.controls[key].valueChanged,
                lambda n, controls=controls, method=method: [
                    getattr(c, method)(n) for c in controls
                ],
            )
    connect(
        owner,
        owner.controls["orientation"].activated,
        lambda i: owner.stack.setCurrentIndex(i),
    )
    owner.controls["minimum"].setValue(0)
    owner.controls["maximum"].setValue(20)
    number.setValue(5)


def wire(owner: Any, core: Any) -> None:
    """Wire exact original profiles, then observe settled actual slider values."""
    (part2(owner, core) if owner.part == 2 else part3(owner))
    for key, method in (
        ("appearance", "setInvertedAppearance"),
        ("keys", "setInvertedControls"),
    ):
        connect(
            owner,
            owner.controls[key].toggled,
            lambda flag, method=method: [
                getattr(c, method)(flag) for g in owner.groups for c in g
            ],
        )
    for control in (*owner.groups[0], owner.controls["value"]):
        connect(owner, control.valueChanged, lambda *args: owner.changed())
