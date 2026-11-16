# this_file: Scripts/Widgets/Toolkit Reference Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Report what the fontlabapp.ui facades and the pure fontlabapp.qt helpers do.

What: Opens a message box whose details list the names each fontlabapp.ui
subpackage (actions, canvas, dialogs, panels, widgets, windows) publishes. The
report also covers a small fontlabapp.qt.ui_graph tree round-tripped through
JSON, equations solved with fontlabapp.qt.layouts.linear, a stack laid out with
fontlabapp.qt.layouts.stack, numbers and colors converted with
fontlabapp.qt.numeric and fontlabapp.qt.colors, a value read with
fontlabapp.qt.properties, a file-chooser filter built with fontlabapp.qt.dialogs
and the constants of fontlabapp.qt.menus, fontlabapp.qt.painting.editor,
fontlabapp.qt.views and fontlabapp.qt.safe.
Use: Run it from the Scripts menu and click Show Details. The Widget Gallery
Demo uses the widget-bound helpers on real controls.
Safety: Read-only. The ui subpackages are only imported; none of the names they
publish is resolved or called, so no host object, menu, panel or glyph window is
touched. Every other call is pure arithmetic or data on values the demo creates.
No font, selection, history, preference, Output or clipboard is read or written.
"""

from types import SimpleNamespace

_BOXES: list = []  # modeless boxes stay referenced until the user closes them
UI_PACKAGES = (
    "fly.ap.ui.actions",
    "fly.ap.ui.canvas",
    "fly.ap.ui.dialogs",
    "fly.ap.ui.panels",
    "fly.ap.ui.widgets",
    "fly.ap.ui.windows",
)


def facade_lines(import_module) -> list[str]:
    """One line per fontlabapp.ui subpackage: the names it publishes."""
    return [f"{dotted}: {', '.join(import_module(dotted).__all__)}" for dotted in UI_PACKAGES]


def graph_lines(ui_graph) -> list[str]:
    """Build a two-node UI graph and report whether its JSON form reloads unchanged."""
    graph = ui_graph.UIGraph()
    root = graph.add_node("Window", properties={"title": "Reference"})
    button = graph.add_node("Button", parent_id=root.node_id, frame={"x": 0, "y": 0, "w": 80, "h": 24})
    graph.connect(button.node_id, root.node_id, "clicked", "close")
    data = graph.to_json()
    same = ui_graph.UIGraph.from_json(data).to_json() == data
    return [
        f"ui_graph version {data['version']}: {len(data['nodes'])} nodes, "
        f"{len(data['connections'])} connection, reload identical: {same}"
    ]


def layout_lines(linear, stack) -> list[str]:
    """Solve x + y = 10 with x - y = 2, and distribute three stack sizes."""
    solved = linear.solve([([1.0, 1.0], 10.0), ([1.0, -1.0], 2.0)], [], 2)
    sizes = [10.0, 20.0, 30.0]
    starts = stack.distribute(sizes, 100.0, 5.0, "equal")
    return [
        f"linear.solve: x={solved[0]:g}, y={solved[1]:g}",
        f"stack.distribute equal in 100 with spacing 5: sizes {sizes}, offsets {starts}",
    ]


def number_lines(numeric, colors, properties) -> list[str]:
    """Show the number, color and property helpers on plain values."""
    steps = numeric.STEPS
    position = numeric.position(5, 0, 20, steps)
    owner = SimpleNamespace(size=lambda: 12, name="field")
    return [
        f"numeric: 5 in 0..20 is position {position:g} of {steps}; back to "
        f"{numeric.value_at(0, position, 20, steps):g}",
        f"colors.rgba255((0.5, 0.25, 1, 1)) = {colors.rgba255((0.5, 0.25, 1, 1))}",
        f"colors.rgba_css((0.5, 0.25, 1, 1)) = {colors.rgba_css((0.5, 0.25, 1, 1))}",
        f"properties.value: a method gives {properties.value(owner, 'size')}, "
        f"an attribute gives {properties.value(owner, 'name')}",
    ]


def constant_lines(dialogs, menus, editor, views, safe) -> list[str]:
    """Name the constants and classes of the host-bound modules without using them."""
    return [
        f"dialogs.name_filters(['png', '.jpg']) = {dialogs.name_filters(['png', '.jpg'])}",
        f"menus.OWNED_MENU_TITLE = {menus.OWNED_MENU_TITLE!r}",
        f"painting.editor: phase {editor.AFTER_NATIVE_LAYER!r}, layer filters {editor.LAYER_FILTERS}",
        f"views classes: {views.Panel.__name__}, {views.Preview.__name__}, {views.GlyphWindow.__name__}",
        f"safe.MAIN_WINDOW_CLASS = {safe.MAIN_WINDOW_CLASS!r}",
    ]


def show_report(title: str, summary: str, lines: list[str]) -> None:
    """Show the report as a modeless, owned message box with selectable details."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, release_closed_message_boxes, show_message_box
    from fly.ap.qt.safe import main_window

    qt = fly.qt
    release_closed_message_boxes(_BOXES)
    box = create_message_box(qt.QtGui, title, summary, "Information", (main_window(fly.fl, qt),), detail="\n".join(lines))

    def configure(current) -> None:
        current.setWindowTitle(title)

    show_message_box(box, _BOXES, configure)


def main() -> None:
    """Build every section from the real fontlabapp modules and show them."""
    from importlib import import_module

    import fly.ap.qt.colors as colors
    import fly.ap.qt.dialogs as dialogs
    import fly.ap.qt.layouts.linear as linear
    import fly.ap.qt.layouts.stack as stack
    import fly.ap.qt.menus as menus
    import fly.ap.qt.numeric as numeric
    import fly.ap.qt.painting.editor as editor
    import fly.ap.qt.properties as properties
    import fly.ap.qt.safe as safe
    import fly.ap.qt.ui_graph as ui_graph
    import fly.ap.qt.views as views

    sections = (
        ("fontlabapp.ui subpackages", facade_lines(import_module)),
        ("fontlabapp.qt.ui_graph", graph_lines(ui_graph)),
        ("fontlabapp.qt.layouts", layout_lines(linear, stack)),
        ("fontlabapp.qt numbers, colors, properties", number_lines(numeric, colors, properties)),
        ("fontlabapp.qt constants", constant_lines(dialogs, menus, editor, views, safe)),
    )
    lines = []
    for heading, body in sections:
        lines += [heading + ":", *body, ""]
    show_report("Toolkit Reference Demo", f"{len(sections)} sections reported.", lines)


if __name__ == "__main__":
    main()
