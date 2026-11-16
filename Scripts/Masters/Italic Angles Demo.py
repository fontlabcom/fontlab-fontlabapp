# this_file: Scripts/Masters/Italic Angles Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Lean three made-up masters with App's italic-angle gauge, no font needed.

What: Opens one nonmodal window with the Gauge painter of the Italic Angle
panel (fontlabapp.masters.angles.views): one slanted stem per master, labelled
with its angle. A slider sets the angle of the Bold master between the limits
of fontlabapp.masters.angles.model (MIN_ANGLE to MAX_ANGLE); Light and Regular
get a third and two thirds of it. A label also lists, from the same model,
whether FontLab's Undo keeps three blueScale values exactly
(history_preserves_blue_scale), the check the panel makes before it writes.
Use: Run it from the Scripts menu, drag the slider and close the window when
done. Negative angles lean right.
Safety: The three masters are plain numbers in this script, so no font is
opened or read. Only widgets the demo creates are touched. The Italic Angle
panel itself (fontlabapp.masters.angles.ui) is not opened: its Apply button
writes italic angles into the font, and even opening it switches masters while
it reads them. Closing the window disconnects its signals and releases the
demo. No font, master, selection, history, preference, Output or clipboard is
read or written.
"""

_HANDLES: list = []  # each open demo stays referenced until its window closes
MASTERS = (("Light", 1 / 3), ("Regular", 2 / 3), ("Bold", 1.0))  # name, share of the slider angle
BLUE_SCALES = (0.039625, 0.04, 0.03333333333)  # the FontLab default, a round value and a long one


def angles(value: float) -> list[tuple[str, float]]:
    """(master, angle) for each master when Bold leans by ``value`` degrees."""
    return [(name, round(value * share, 1)) for name, share in MASTERS]


def blue_scale_lines(check) -> list[str]:
    """One line per sample blueScale: does FontLab's Undo history keep it exactly?"""
    return [f"blueScale {value}: Undo keeps it exactly: {check(value)}" for value in BLUE_SCALES]


class Demo:
    """One open window: its gauge, slider and signal scope are owned here."""

    def __init__(self, kit) -> None:
        self.kit, self.owned, self.problems = kit, None, []
        self.scope = kit.Scope(self.problems.append)

    def build(self, content) -> None:
        """Create the gauge, the slider and the labels inside ``content``."""
        gui, model = self.kit.gui, self.kit.model
        gauge = self.kit.Gauge(content)
        label = gui.QLabel("", content)
        notes = gui.QLabel("\n".join(blue_scale_lines(model.history_preserves_blue_scale)), content)
        slider = gui.QSlider(self.kit.horizontal, content)
        slider.setRange(int(model.MIN_ANGLE), int(model.MAX_ANGLE))
        slider.setValue(-12)

        def moved(value: int) -> None:
            shown = angles(value)
            gauge.masters = [name for name, _ in shown]
            gauge.set_angles(shown)
            label.setText("Italic angle: " + ", ".join(f"{name} {angle:g}°" for name, angle in shown))

        layout = gui.QVBoxLayout(content)
        for widget in (label, gauge, slider, notes):
            layout.addWidget(widget)
        self.scope.connect(slider.valueChanged, moved)
        self.scope.connect(content.finished, self.on_finished, closing=True)
        moved(-12)

    def on_finished(self, *args) -> None:
        """Release after Qt's dispatch returns, never from inside it."""
        self.kit.single_shot(0, lambda: self.release())

    def release(self) -> None:
        """Disconnect every owned signal, close the window and drop this demo."""
        try:
            self.scope.finish()
            if self.owned is not None:
                self.owned.close()
        finally:  # the handle leaves even when the native window is already gone
            if self in _HANDLES:
                _HANDLES.remove(self)


def main() -> None:
    """Open the gauge window, retaining it until it closes."""
    from types import SimpleNamespace

    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.masters.angles import model
    from fly.ap.masters.angles.views import Gauge
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    kit = SimpleNamespace(
        gui=qt.QtGui, horizontal=qt.QtCore.Qt.Horizontal, single_shot=qt.QtCore.QTimer.singleShot,
        Scope=Scope, Gauge=Gauge, model=model,
    )  # fmt: skip
    demo = Demo(kit)
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), "Italic Angles Demo", demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
