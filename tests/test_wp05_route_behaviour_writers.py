# this_file: tests/test_wp05_route_behaviour_writers.py
# SPDX-License-Identifier: Apache-2.0
"""Coverage round A: panel-style writers, layer switching and the cursive sampler."""

from __future__ import annotations

import runpy
from types import SimpleNamespace as NS
from typing import Any

import pytest
from _cov_a_support import ROOT, Host, host as host_fixture  # noqa: F401
from _message_box_support import message_box_type
from _wp05_app_routes import route_path
from _wp05_scriptmix_shim import real_app  # noqa: F401


class PanelBase:
    """Stand-in for the App panel base: records what a script's panel asks of it."""

    TITLE = KEY = ""
    current_master = "Regular"

    def __init__(self) -> None:
        self.package = NS(name="package")
        self.form = NS(added=[], addWidget=lambda *a: self.form.added.append(a))
        self.rows: list[tuple] = []
        self.watched: list[Any] = []
        self.scope_made = 0

    def scope_box(self) -> NS:
        self.scope_made += 1
        return NS(currentIndexChanged="scope-signal")

    def add_row(self, label: str, *widgets: Any) -> None:
        self.rows.append((label, widgets))

    def watch(self, signal: Any, callback: Any = None) -> None:
        self.watched.append(signal)


# ---- Decompose Serif Components --------------------------------------------------


def serif_tool(host: Host, **scripting: Any) -> Any:
    return host.load(
        "Components/Decompose Serif Components.py",
        modules=("component_panel", "component_writer"),
        patches={"component_panel": {"panel_type": lambda: PanelBase}},
        scripting=scripting,
    )


def component(base: str, shape_id: int, *, affine: bool = True) -> NS:
    """Component shape double referring to ``base`` on the master layer."""
    return NS(
        isComponent=True,
        isComposite=True,
        id=shape_id,
        transform=NS(isAffine=lambda: affine),
        shapeData=NS(componentGlyph=base, componentLayer=""),
    )


















# ---- Retract Handles ---------------------------------------------------------------


class Node:
    def __init__(self, x: float, y: float, on: bool, selected: bool = False) -> None:
        self.x, self.y, self.selected = x, y, selected
        self._on = on

    def isOn(self) -> bool:  # noqa: N802 - FontLab name
        return self._on


class Contour:
    def __init__(self, nodes: list[Node], closed: bool = True, tt: bool = False) -> None:
        self._nodes, self.closed, self.isTT = nodes, closed, tt

    def nodes(self) -> list[Node]:
        return self._nodes


def cubic_loop(selected: tuple[int, ...] = ()) -> Contour:
    """Closed cubic contour: two on-curve nodes, each with two live handles."""
    points = [(0, 0, True), (10, 0, False), (20, 50, False), (30, 50, True), (40, 50, False), (0, 10, False)]
    return Contour([Node(x, y, on, i in selected) for i, (x, y, on) in enumerate(points)])


def shape_of(*contours: Contour, refs: int = 1, moved: bool = True, component: bool = False) -> NS:
    matrix = NS(m11=lambda: 1.0, m22=lambda: 1.0 if moved else 2.0, m12=lambda: 0.0, m21=lambda: 0.0, dx=lambda: 5, dy=lambda: 6)
    return NS(isComponent=component, contours=list(contours), shapeData=NS(referenceCount=refs), transform=matrix)


def retract_tool(host: Host, **scripting: Any) -> Any:
    return host.load(
        "Contours/Retract Handles.py",
        modules=("outline_panel", "outline_writer"),
        patches={"outline_panel": {"panel_type": lambda: PanelBase}},
        scripting=scripting,
    )


def test_moves_when_cubic_loop_then_all_four_handles_target_their_bases(host):
    tool = retract_tool(host)
    contour = cubic_loop()
    moves = tool.moves(contour, selected_only=False)
    nodes = contour.nodes()
    assert [(n, x, y) for n, x, y in moves] == [
        (nodes[1], 0.0, 0.0),
        (nodes[2], 30.0, 50.0),
        (nodes[4], 30.0, 50.0),
        (nodes[5], 0.0, 0.0),
    ], "Closing segment handles retract onto the first and last on-curve nodes"


def test_moves_when_selected_only_then_only_handles_of_selected_bases(host):
    tool = retract_tool(host)
    contour = cubic_loop(selected=(0,))
    moved = [n for n, _, _ in tool.moves(contour, selected_only=True)]
    assert moved == [contour.nodes()[1], contour.nodes()[5]], 'moves when selected only then only handles of selected bases: expected moved == [contour.nodes()[1], contour.nodes()[5]]'
    explicit = tool.moves(contour, True, selected_indices={3})
    assert [n for n, _, _ in explicit] == [contour.nodes()[2], contour.nodes()[4]], "Explicit indices win"


def test_moves_when_tt_open_or_degenerate_then_nothing_or_no_wrap(host):
    tool = retract_tool(host)
    assert tool.moves(Contour(cubic_loop().nodes(), tt=True), False) == [], "Quadratic contours are kept"
    open_contour = Contour(cubic_loop().nodes()[:4], closed=False)
    assert len(tool.moves(open_contour, False)) == 2, "An open contour does not wrap"
    flat = Contour([Node(0, 0, True), Node(0, 0, False), Node(4, 5, False), Node(5, 5, True)], closed=False)
    assert [(x, y) for _, x, y in tool.moves(flat, False)] == [(5.0, 5.0)], "Already-retracted handles are skipped"
    two_on = Contour([Node(0, 0, True), Node(9, 9, True)], closed=False)
    assert tool.moves(two_on, False) == [], "A line segment has no handles"


def test_changes_when_all_handles_then_one_row_with_count_and_targets(host):
    tool = retract_tool(host)
    layer = NS(shapes=[shape_of(cubic_loop())])
    rows = tool.changes(layer, selected_only=False)
    assert len(rows) == 1 and (rows[0].name, rows[0].old, rows[0].new) == ("handles", "4", "retracted"), "changes when all handles then one row with count and targets: unexpected result"
    assert len(rows[0].edit) == 4, "The row carries every planned move"


def test_changes_when_shared_or_scaled_shape_then_note_rows_and_no_edit(host):
    tool = retract_tool(host)
    layer = NS(shapes=[shape_of(cubic_loop(), refs=3), shape_of(cubic_loop(), moved=False), shape_of(cubic_loop(), component=True)])
    rows = tool.changes(layer, False)
    assert [r.new for r in rows] == ["shared outline, kept", "scaled or rotated shape, kept"], "changes when shared or scaled shape then note rows and no edit: unexpected result"
    assert all(r.edit is None for r in rows), "Notes are display-only rows"


def test_changes_when_selected_only_then_selection_read_from_reference_master(host):
    tool = retract_tool(host)
    target = NS(shapes=[shape_of(cubic_loop())])
    reference = NS(shapes=[shape_of(cubic_loop(selected=(3,)))])
    rows = tool.changes(target, True, reference)
    assert len(rows) == 1 and rows[0].old == "2", "Only handles at the reference master's selected node"
    none_selected = tool.changes(target, True, NS(shapes=[shape_of(cubic_loop())]))
    assert none_selected == [], "No selected nodes means no changes"


def test_changes_when_reference_structure_differs_then_blocking_row(host):
    tool = retract_tool(host)
    target = NS(shapes=[shape_of(cubic_loop())])
    fewer = NS(shapes=[])
    rows = tool.changes(target, True, fewer)
    assert rows[0].problem == "Master node structures differ.", "changes when reference structure differs then blocking row: expected rows[0].problem == 'Master node structures differ.'"
    shorter = Contour(cubic_loop().nodes()[:5])
    rows = tool.changes(target, True, NS(shapes=[shape_of(shorter)]))
    assert rows[0].problem == "Master node structures differ.", "Different node counts"
    retyped = cubic_loop()
    retyped.nodes()[1]._on = True
    rows = tool.changes(target, True, NS(shapes=[shape_of(retyped)]))
    assert rows[0].problem == "Master node structures differ.", "Different on/off pattern"


def test_retract_editor_when_write_and_check_then_coordinates_set_and_verified(host):
    tool = retract_tool(host)
    contour = cubic_loop()
    targets = tool.moves(contour, False)
    editor = tool.RetractEditor()
    layer = NS(name="Regular")
    editor.write(layer, [targets])
    assert (contour.nodes()[1].x, contour.nodes()[1].y) == (0.0, 0.0), 'retract editor when write and check then coordinates set and verified: expected (contour.nodes()[1].x, contour.nodes()[1].y) == (0.0, 0.0)'
    assert editor.check([(layer, [targets])]) == [], "Written handles read back exactly"
    contour.nodes()[2].x = 99
    assert editor.check([(layer, [targets])]) == ["Regular"], "A handle that did not hold is reported by layer name"


def test_retract_panel_when_built_then_filter_checkbox_added_and_watched(host):
    tool = retract_tool(host)
    panel = tool.RetractPanel()
    panel.build_controls()
    assert panel.selected_filter.label == "Only at selected on-curve nodes", "retract panel when built then filter checkbox added and watched: expected panel.selected_filter.label == 'Only at selected on-curve nodes'"
    assert panel.rows == [("", (panel.selected_filter,))], "retract panel when built then filter checkbox added and watched: expected panel.rows == [('', (panel.selected_filter,))]"
    assert panel.watched == [panel.selected_filter.toggled], 'retract panel when built then filter checkbox added and watched: expected panel.watched == [panel.selected_filter.toggled]'
    assert tool.RetractPanel.HEADERS == ("Glyph · master", "Item", "Handles", "After"), "retract panel when built then filter checkbox added and watched: unexpected result"
    assert tool.RetractPanel.UNIT == "contour", "retract panel when built then filter checkbox added and watched: expected tool.RetractPanel.UNIT == 'contour'"


def test_retract_panel_planner_when_filter_toggled_then_selection_read_from_current_master(host):
    tool = retract_tool(host)
    panel = tool.RetractPanel()
    panel.build_controls()
    calls: list[tuple] = []
    tool.changes = lambda layer, selected, reference: calls.append((layer, selected, reference)) or ["r"]
    glyph = NS(findLayer=lambda master: f"layer-of-{master}")
    plan = panel.planner()
    assert plan(glyph, "Bold", "L") == ["r"], "retract panel planner when filter toggled then selection read from current master: expected plan(glyph, 'Bold', 'L') == ['r']"
    panel.selected_filter.setChecked(True)
    plan = panel.planner()
    plan(glyph, "Bold", "L")
    assert calls == [("L", False, "layer-of-Regular"), ("L", True, "layer-of-Regular")], "retract panel planner when filter toggled then selection read from current master: unexpected result"


def test_retract_panel_editor_when_requested_then_retract_editor(host):
    tool = retract_tool(host)
    assert isinstance(tool.RetractPanel().editor(), tool.RetractEditor), 'retract panel editor when requested then retract editor: expected isinstance(tool.RetractPanel().editor(), tool.RetractEditor)'


@pytest.mark.parametrize("error", [ValueError("bad"), RuntimeError("rt"), TimeoutError("slow")])
def test_retract_main_when_dialog_refused_then_warning_box_and_none(host, error):
    def refuse(dialog_type: Any, key: str) -> None:
        raise error

    tool = retract_tool(host, show_script_dialog=refuse)
    warned: list[tuple] = []
    host.qt.QtGui.QMessageBox = message_box_type(warning=lambda *a: warned.append(a))
    assert tool.main() is None, 'retract main when dialog refused then warning box and none: expected tool.main() is None'
    assert warned == [(host.main_window, "Retract Handles", str(error))], "retract main when dialog refused then warning box and none: expected warned == [(host.main_window, 'Retract Handles', str(error))]"


def test_retract_main_when_dialog_opens_then_returned_and_script_guard_runs(host):
    tool = retract_tool(host, show_script_dialog=lambda dialog_type, key: host.windows().setdefault(key, dialog_type))
    assert tool.main() is tool.RetractPanel, 'retract main when dialog opens then returned and script guard runs: expected tool.main() is tool.RetractPanel'
    host.windows().clear()
    runpy.run_path(str(route_path("Retract Handles")), run_name="__main__")
    assert "contours_retract_handles" in host.windows(), "retract main when dialog opens then returned and script guard runs: expected 'contours_retract_handles' in host.windows()"


# ---- Display Previous Layer --------------------------------------------------------

LAYER_PATH = "Masters/Display Previous Layer.py"
MASTERS = ("Regular", "Bold")


def layer_tool(host: Host, **ap_modules: Any) -> Any:
    tool = host.load(LAYER_PATH, modules=("masters",))
    for name, attributes in ap_modules.items():
        host.fake_ap(name, **attributes)
    return tool


def glyph_with(*layers: tuple[str, bool]) -> NS:
    """Glyph whose layers are (name, is_body); masks and services are flagged."""
    return NS(
        layers=[NS(name=n, isMaskLayer=not body, isService=False) for n, body in layers],
        activated=[],
    )














def occurrence(glyph: Any, layer_name: str = "Regular#b", index: int = 0, block_id: int = 7) -> NS:
    return NS(glyph=glyph, layer_name=layer_name, index=index, block_id=block_id, glyph_name="a")


def capture_with(occurrences: list, editor: bool = True, carriers: list | None = None) -> Any:
    selection = NS(
        context=(None, None, "editor" if editor else "font"),
        occurrences=occurrences,
        carriers=carriers or [],
    )
    return lambda deadline: selection


def plan_tool(host: Host, capture: Any, package: Any = "ok") -> Any:
    tool = layer_tool(host, layer_selection=dict(capture=capture))
    host.package = NS(id=1, masters=list(MASTERS)) if package == "ok" else package
    return tool










class Symbol:
    def __init__(self, layer_name: str) -> None:
        self.layerName = layer_name


class Block:
    """Text block double holding one glyph slot."""

    def __init__(self, layer_name: str, block_id: int = 7) -> None:
        self.id = block_id
        self.symbol = Symbol(layer_name)
        self.changed_calls = 0

    def getGlyphAt(self, index: int) -> NS:  # noqa: N802
        return NS(symbol=self.symbol)

    def changed(self) -> None:
        self.changed_calls += 1


def show_tool(host: Host) -> Any:
    return layer_tool(host, qtsafe=dict(qt_list=lambda items: list(items)))
















# ---- Auto Cursive Attachment Get Sample --------------------------------------------

SAMPLE_PATH = "Anchors/Auto Cursive Attachment Get Sample.py"
SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]


def sample_tool(host: Host) -> Any:
    return host.load(SAMPLE_PATH)


def point(x: float, y: float) -> NS:
    return NS(x=lambda: x, y=lambda: y)


class Polygon:
    """PythonQt QPolygonF shape: size()/at(i) only, neither iterable nor subscriptable."""

    __iter__ = None

    def __init__(self, points):
        self._points = list(points)

    def size(self):
        return len(self._points)

    def at(self, index):
        return self._points[index]


def closed_shape(*polygons: list[tuple[float, float]], composite: bool = False, affine: bool = True, open_empty: bool = True) -> NS:
    return NS(
        isComposite=composite,
        transform=NS(isAffine=lambda: affine),
        openedPath=NS(isEmpty=lambda: open_empty),
        closedPath=NS(toSubpathPolygons=lambda transform: [Polygon(point(*p) for p in poly) for poly in polygons]),
    )






















def pin(name: str, x: float, y: float) -> NS:
    return NS(name=name, x=x, y=y)


def sample_layer(*pins: NS) -> NS:
    return NS(shapes=[closed_shape(SQUARE)], anchors=list(pins), name="Regular", isMaskLayer=False, isService=False)








class Dialogs:
    """qt_dialogs double: runs the script's chooser configuration and records message boxes."""

    def __init__(self, paths: list[str]) -> None:
        self.paths = paths
        self.configured: list[tuple] = []
        self.messages: list[tuple] = []
        self.parents: list[tuple] = []
        self.flags: list[int] = []

    def run_file_dialog(self, qt_gui: Any, configure: Any, title: str, start: str, parent_args: tuple = ()) -> list[str]:
        self.parents.append(parent_args)
        calls: list[tuple] = []
        recorder = NS(**{n: (lambda *a, n=n: calls.append((n, *a))) for n in (
            "setAcceptMode", "setOption", "setFileMode", "setNameFilter", "setDefaultSuffix")})
        recorder.windowFlags = lambda: 0x1000
        recorder.setWindowFlags = self.flags.append
        kind = NS(AcceptSave=1, DontConfirmOverwrite=2, AnyFile=3)
        configure(kind, recorder)
        self.configured.append((title, start, calls))
        return self.paths

    def create_message_box(self, qt_gui: Any, title: str, text: str, icon: str, parent_args: tuple = ()) -> NS:
        self.parents.append(parent_args)
        box = NS(title=title, text=text, icon=icon, windowFlags=lambda: 0x1000, setWindowFlags=self.flags.append, setStandardButtons=lambda buttons: None)
        self.messages.append((title, text, icon))
        return box

    def run_owned_dialog(self, box: Any, configure: Any, read_result: Any) -> Any:
        configure(box)
        self.messages.append(("ran", box.text))
        return read_result(box, 1)


def sample_main(host: Host, paths: list[str], occurrences: list | None = None, layer: NS | None = None, package: Any = "ok") -> tuple[Any, Dialogs]:
    tool = host.load(SAMPLE_PATH, modules=("masters",))
    layer = layer or sample_layer(pin("entry", 50, 25))
    occ = [NS(layer=layer)] if occurrences is None else occurrences
    host.fake_ap("layer_selection", capture=lambda deadline: NS(occurrences=occ))
    host.fake_ap("anchor_writer", raw_point=lambda p: (p.x, p.y))
    dialogs = Dialogs(paths)
    host.fake_ap("qt_dialogs", run_file_dialog=dialogs.run_file_dialog, create_message_box=dialogs.create_message_box, run_owned_dialog=dialogs.run_owned_dialog)
    host.qt.QtGui.QMessageBox = NS(Ok=1)
    host.package = NS(id=1, masters=["Regular", "Bold"]) if package == "ok" else package
    return tool, dialogs




















