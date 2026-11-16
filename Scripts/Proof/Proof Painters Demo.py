# this_file: Scripts/Proof/Proof Painters Demo.py
# SPDX-License-Identifier: Apache-2.0
"""See FontLab's proof painters draw sample outlines in a window of their own.

What: Opens one nonmodal window that feeds made-up outlines (a box and a round
shape in three masters) to the real painters of fontlabapp.proof.inspect.views
(Grid, MasterRows and WaterfallView) and fontlabapp.proof.inspectors.views
(OrderView, with contour numbers, start dots and direction arrows). A label
adds a width progression from fontlabapp.proof.inspectors.model and names the
panel shells ProofDialog (fontlabapp.proof.inspect.ui), InspectorsDialog
(fontlabapp.proof.inspectors.ui) and ReviewDialog (fontlabapp.proof.review.ui).
Use: Run it from the Scripts menu and scroll through the four proofs. Missing
glyphs show as red boxes or a dash. Close the window when done.
Safety: The outlines are built in memory from numbers in this file, so no font
is opened or read. Only widgets the demo creates are touched. Closing the
window disconnects its signal and releases the demo. The panel shells are
only named, never opened. No font, selection, history, preference, Output or
clipboard is read or written.
"""

_HANDLES: list = []  # each open demo stays referenced until its window closes
MASTERS = (("Light", -30), ("Regular", 0), ("Bold", 40))  # name, stem growth
UPM, FRAME, SIZES = 1000, (-200, 800), (16, 32, 64)
BOX = [(100, 0, True), (600, 0, True), (600, 700, True), (100, 700, True)]
COUNTER = [(250, 150, True), (250, 550, True), (450, 550, True), (450, 150, True)]
ROUND = [
    (350, 0, True), (488, 0, False), (600, 112, False), (600, 350, True),
    (600, 588, False), (488, 700, False), (350, 700, True), (212, 700, False),
    (100, 588, False), (100, 350, True), (100, 112, False), (212, 0, False),
]  # fmt: skip


def grow(points: list, amount: int) -> list:
    """Move points right of the glyph's middle outwards by ``amount``, the rest inwards."""
    return [(x + amount if x >= 350 else x - amount, y, on) for x, y, on in points]


def contour_info(points: list, signed_area, index: int = 0) -> tuple:
    """(index, points, start, next, 'ccw'|'cw') the way OrderView expects it."""
    direction = "ccw" if signed_area([p[:2] for p in points]) > 0 else "cw"
    return (index, points, points[0][:2], points[1][:2], direction)


def shell_lines(shells: tuple) -> list[str]:
    """Name each panel shell class and its module; none is instantiated."""
    return [f"{kind.__name__} ({kind.__module__})" for kind in shells]


class Demo:
    """One open window: its views and signal connection are owned here."""

    def __init__(self, kit) -> None:
        self.kit, self.owned, self.slot = kit, None, None

    def build(self, content) -> None:
        """Create the labelled painters inside ``content`` (the demo's own dialog)."""
        gui, kit = self.kit.gui, self.kit
        paths = {name: kit.outline_path([points]) for name, points in (("box", BOX), ("round", ROUND))}
        layers = {
            master: {
                "box": (kit.outline_path([grow(BOX, grow_by), grow(COUNTER, -grow_by)]), 700 + 2 * grow_by),
                "round": (kit.outline_path([grow(ROUND, grow_by)]), 700 + 2 * grow_by),
            }
            for master, grow_by in MASTERS
        }
        widths = [layers[master]["box"][1] for master, _ in MASTERS]
        run = [layers["Regular"][name] for name in ("box", "round")] + [(None, 500), layers["Regular"]["box"]]
        waterfall, rows, grid = kit.WaterfallView(), kit.MasterRows(), kit.Grid()
        waterfall.set_content(run, SIZES, UPM, FRAME[1])
        rows.set_content([(m, [layers[m]["box"], layers[m]["round"], (None, 500)], sum(w for _, w in layers[m].values())) for m, _ in MASTERS], 40, UPM, FRAME)
        grid.set_content([(name, [(m, *layers[m][name]) for m, _ in MASTERS]) for name in ("box", "round")] + [("missing", [(m, None, 0) for m, _ in MASTERS])], [m for m, _ in MASTERS], FRAME, 120)
        order = kit.OrderView()
        order.columns = [
            (m, [contour_info(grow(BOX, g), kit.signed_area), contour_info(grow(COUNTER, -g), kit.signed_area, 1)])
            for m, g in MASTERS
        ]
        info = gui.QLabel(
            f"Box width by master: {widths} ({kit.progression(widths)}).\n"
            + "\n".join(shell_lines(kit.shells)),
            content,
        )
        holder = gui.QWidget(content)
        stack = gui.QVBoxLayout(holder)
        for title, view in (("Waterfall", waterfall), ("Master rows", rows), ("Glyph by master grid", grid), ("Contour order", order)):
            stack.addWidget(gui.QLabel(title, holder))
            stack.addWidget(view)
        area = gui.QScrollArea(content)
        area.setWidgetResizable(True)
        area.setWidget(holder)
        layout = gui.QVBoxLayout(content)
        layout.addWidget(info)
        layout.addWidget(area)
        content.resize(720, 640)
        self.slot = lambda *args: self.kit.single_shot(0, self.release)
        content.finished.connect(self.slot)
        self.finished = content.finished

    def release(self) -> None:
        """Disconnect the window's signal, close it and drop this demo."""
        try:
            if self.slot is not None:
                slot, self.slot = self.slot, None
                self.finished.disconnect(slot)
            if self.owned is not None:
                self.owned.close()
        finally:  # the handle leaves even when the native window is already gone
            if self in _HANDLES:
                _HANDLES.remove(self)


def main() -> None:
    """Open the painters window, retaining it until it closes."""
    from types import SimpleNamespace

    import fly
    from fly.ap.proof.inspect.ui import ProofDialog
    from fly.ap.proof.inspect.views import Grid, MasterRows, WaterfallView
    from fly.ap.proof.inspectors.model import progression, signed_area
    from fly.ap.proof.inspectors.ui import InspectorsDialog
    from fly.ap.proof.inspectors.views import OrderView, outline_path
    from fly.ap.proof.review.ui import ReviewDialog
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    kit = SimpleNamespace(
        gui=qt.QtGui, single_shot=qt.QtCore.QTimer.singleShot, shells=(ProofDialog, InspectorsDialog, ReviewDialog),
        Grid=Grid, MasterRows=MasterRows, WaterfallView=WaterfallView, OrderView=OrderView,
        outline_path=outline_path, progression=progression, signed_area=signed_area,
    )  # fmt: skip
    demo = Demo(kit)
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), "Proof Painters Demo", demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
