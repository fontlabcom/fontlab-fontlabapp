# this_file: Scripts/Masters/Layers Samples Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Show App's layer reports and planners on made-up glyphs, without a font.

What: Feeds sample layers to the pure parts of App's layer tools and prints
their results: bracket layers and the glyphs that use them
(fontlabapp.masters.layers.brackets.model), the adjacent-layer compatibility
check (fontlabapp.masters.layers.compatibility.model), the highest and lowest
layers (fontlabapp.masters.layers.extrema.model), the layer list of Show All
Layers (fontlabapp.masters.layers.show_all.model) and the next or previous
layer plan with its stale-source refusal
(fontlabapp.masters.layers.navigation.data).
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The glyphs are plain values in
this script, no window opens, no tab is created and no layer is shown or
changed. The native readers and writers of these tools (their native modules,
the panels, show_all.run and brackets.open_tab, which would open a proof tab)
are never called. No font, master, selection, history, preference, Output or
clipboard is touched.
"""

TITLE = "Layers Samples Demo"
SOURCE = ("sample", 1)  # the opaque source token the navigation planner compares


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def brackets() -> str:
    """Glyph a has a bracket layer; aacute reuses a as a component, so it is affected too."""
    from fly.ap.masters.layers.brackets import model

    glyphs = (
        model.Glyph("a", ("Regular", "Bold [wght>600]")),
        model.Glyph("aacute", ("Regular",), frozenset({"a", "acutecomb"})),
        model.Glyph("b", ("Regular",)),
    )
    return model.render(model.analyse(glyphs))


def compatibility() -> str:
    """Light and Regular differ in node count and anchors; Bold matches Regular."""
    from fly.ap.masters.layers.compatibility import model

    square = ("line",) * 4
    group = model.GlyphLayers(
        "A",
        (
            model.Layer("Light", (("line",) * 3,), frozenset({"top"})),
            model.Layer("Regular", (square,), frozenset({"top", "bottom"})),
            model.Layer("Bold", (square,), frozenset({"top", "bottom"})),
        ),
    )
    return model.render((group,)).rstrip()


def extrema() -> str:
    """Three layers; the first one with the highest top and the lowest bottom wins."""
    from fly.ap.masters.layers.extrema import model

    rows = (
        model.LayerExtent("a", "Regular", -10, 520),
        model.LayerExtent("Aacute", "Bold", 0, 960),
        model.LayerExtent("g", "Light", -240, 500),
    )
    return model.render(model.choose(rows))


def show_all() -> str:
    """Two selected glyphs and a line break (control); each glyph lists all its layers."""
    from fly.ap.masters.layers.show_all import model

    groups = (model.Group("a", ("Regular", "Bold")), model.Group(None, ("lost",)), model.Group("b", ("Regular",)), model.Group("\n", (), control=True))
    return "\n".join("(line break)" if row is None else f"{row[0]} [{row[1]}]" for row in model.expand(groups))


def navigation() -> str:
    """Next from the first layer, wrapping from the last, and a plan that went stale."""
    from fly.ap.masters.layers.navigation import data

    layers = (("id1", "Regular"), ("id2", "Regular @ trial"), ("id3", "Regular backup"))
    forward = data.plan("id1", layers, 1, SOURCE)
    wrapped = data.plan("id3", layers, 1, SOURCE)
    lines = [f"next from id1: {forward.before_layer} -> {forward.after_layer}", f"next from id3: {wrapped.before_layer} -> {wrapped.after_layer} (wraps)"]
    try:
        data.require_current(forward, ("sample", 2))
    except ValueError as error:
        lines.append(f"if the source changed before writing: {error}")
    return "\n".join(lines)


def main() -> None:
    """Show the sample reports; no font is needed."""
    lines = []
    for heading, build in (
        ("Bracket layers", brackets), ("Layer compatibility", compatibility), ("Highest and lowest layers", extrema),
        ("Show All Layers", show_all), ("Layer navigation", navigation),
    ):  # fmt: skip
        lines += [heading + ":", build(), ""]
    notify(TITLE, "Sample layer reports. Nothing was read or written.", "\n".join(lines))


if __name__ == "__main__":
    main()
