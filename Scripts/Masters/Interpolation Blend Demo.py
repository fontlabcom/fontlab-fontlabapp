# this_file: Scripts/Masters/Interpolation Blend Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Slide between two outlines and watch App's interpolation painter blend them.

What: Opens one nonmodal window with BlendView (fontlabapp.masters.interpolation.view),
the painter behind App's interpolation preview: both endpoint outlines dashed
and faint, the mixed outline filled, and every on-curve node of the mix as a
dot. A slider moves the mix from 0 to 100 percent with blend() from
fontlabapp.masters.interpolation.model. With a font open it uses the selected
glyph (or the current glyph) in the font's first and last master by axis
position, when the outlines are compatible; otherwise it uses two round
outlines made in this script and says why.
Use: Run it from the Scripts menu, drag the slider and close the window when
done. Select a glyph in a Font window first to blend your own outlines.
Safety: Read-only. With a font open it reads the Font window selection or the
current glyph, the font's master names and axis locations, and that glyph's
layers, contours and node coordinates; it switches no master and does not move
a node. The window, painter and slider belong to this demo and the slider only
changes what that window paints. Nothing is written to a font, master,
selection, history, preference, Output or clipboard. Closing the window
disconnects its signals and releases the demo.
"""

_HANDLES: list = []  # each open demo stays referenced until its window closes
ROUND = [
    (350, 0, True), (488, 0, False), (600, 112, False), (600, 350, True),
    (600, 588, False), (488, 700, False), (350, 700, True), (212, 700, False),
    (100, 588, False), (100, 350, True), (100, 112, False), (212, 0, False),
]  # fmt: skip


def sample(width: float, lean: float) -> list:
    """A round contour ``width`` wide, each point shifted right by ``lean`` per unit of height."""
    return [[(100 + (x - 100) * width / 500 + y * lean, y, on) for x, y, on in ROUND]]


def font_pair(model) -> tuple:
    """(label, outline a, outline b) of the selected glyph in the first and last master, or (reason, None, None)."""
    from fly.ap.core.scripting import current_package
    from fly.ap.masters.inspect.model import master_order

    package = current_package()
    if package is None:
        return "No font is open", None, None
    names = model.selected_names()
    masters = master_order(package)
    if not names or len(masters) < 2:
        return "Select a glyph in a font with two or more masters", None, None
    glyph = package.findName(names[0])
    if glyph is None or glyph.isNull:
        return f"{names[0]} is not in the font", None, None
    first, last = masters[0], masters[-1]
    layers = model.master_layers(glyph, [first, last])
    if len(layers) < 2:
        return f"{names[0]} lacks a layer in {first} or {last}", None, None
    a, b = model.outline(layers[first]), model.outline(layers[last])
    why = model.problem(a, b)
    if why:
        return f"{names[0]} cannot interpolate: {why}", None, None
    return f"{names[0]}: {first} to {last}", a, b


def sources(model) -> tuple:
    """(heading, outline a, outline b): the font's glyph when usable, else the samples."""
    try:
        label, a, b = font_pair(model)
    except (ValueError, RuntimeError) as error:
        label, a, b = f"The font could not be read ({error})", None, None
    if a is None:
        return f"Sample outlines ({label})", sample(500, 0), sample(800, 0.25)
    return label, a, b


class Demo:
    """One open window: its painter, slider and signal scope are owned here."""

    def __init__(self, kit) -> None:
        self.kit, self.owned, self.problems = kit, None, []
        self.scope = kit.Scope(self.problems.append)

    def build(self, content) -> None:
        """Create the painter, the slider and the label inside ``content``."""
        gui, model = self.kit.gui, self.kit.model
        heading, a, b = sources(model)
        view = self.kit.BlendView(content)
        view.a, view.b = a, b
        view.setMinimumSize(520, 380)
        label = gui.QLabel("", content)
        slider = gui.QSlider(self.kit.horizontal, content)
        slider.setRange(0, 100)
        slider.setValue(50)

        def moved(value: int) -> None:
            view.mix = model.blend(a, b, value / 100)
            label.setText(f"{heading}\nMix: {value}% of the way from the first outline to the second")
            view.update()

        layout = gui.QVBoxLayout(content)
        for widget in (label, view, slider):
            layout.addWidget(widget)
        self.scope.connect(slider.valueChanged, moved)
        self.scope.connect(content.finished, self.on_finished, closing=True)
        moved(50)

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
    """Open the blend window, retaining it until it closes."""
    from types import SimpleNamespace

    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.masters.interpolation import model
    from fly.ap.masters.interpolation.view import BlendView
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    kit = SimpleNamespace(
        gui=qt.QtGui, horizontal=qt.QtCore.Qt.Horizontal, single_shot=qt.QtCore.QTimer.singleShot,
        Scope=Scope, BlendView=BlendView, model=model,
    )  # fmt: skip
    demo = Demo(kit)
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), "Interpolation Blend Demo", demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
