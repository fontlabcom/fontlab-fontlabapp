# this_file: Scripts/Objects/Edit JSON Nodes With vfjo Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Edit JSON Nodes With vfjo Demo: raise outline nodes in copies of glyphs.

What: reads the selected glyphs as object JSON with ``fontlabapp.vfjo``
(``from_glyphs``), renames the copies with a ``.raised`` suffix
(``add_suffix``) and moves every outline node up by 20 units with
``edit_nodes`` and ``fontlabapp.vfjo.nodes.Node.moved``. Components and
anchors are not moved. Then ``vfjo.paste`` creates the copies as new glyphs,
with ``.1``, ``.2``, ... if a name is still taken.
Use: select a few glyphs and run; compare ``o`` with the new ``o.raised``.
Safety: the selected glyphs do not change. Each new glyph is its own Undo
step (FontLab's Add Glyph) and the outlines are one more Undo step. Needs
FontLab 9.1 or later; on 9.0 it says so and changes nothing.
"""

TITLE = "Edit JSON Nodes With vfjo Demo"
SUFFIX = ".raised"
RAISE = 20


def notify(title: str, text: str, details: str = "") -> None:
    """Show a modal report box."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(
        qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details
    )
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def raised(vfjo, Node, objs):
    """Return ``objs`` renamed with ``SUFFIX`` and every node moved up by ``RAISE``."""
    vfjo.add_suffix(objs, SUFFIX)
    return vfjo.edit_nodes(objs, lambda node: Node.moved(node, 0, RAISE))


def main() -> None:
    """Read the selection with vfjo, raise the nodes and paste the copies."""
    from fly.ap import vfjo
    from fly.ap.core.scripting import current_package, names_selected_names
    from fly.ap.vfjo.nodes import Node

    if not vfjo.available():
        notify(TITLE, vfjo.NEEDS_91)
        return
    package = current_package()
    if package is None:
        notify(TITLE, "Open a font first. Nothing was changed.")
        return
    names = [n for n in names_selected_names() if package.findName(n) is not None]
    if not names:
        notify(TITLE, "Select glyphs first. Nothing was changed.")
        return
    objs = raised(vfjo, Node, vfjo.from_glyphs(names, font=package))
    lines = ["Edited JSON:"] + ["  " + line for line in objs.describe()]
    try:
        pasted = vfjo.paste(objs, font=package, title=TITLE)
    except vfjo.PartialWriteError as error:
        notify(TITLE, vfjo.PARTIAL_TEXT, str(error))
        return
    except (ValueError, RuntimeError) as error:
        notify(TITLE, f"Nothing was pasted: {error}", "\n".join(lines))
        return
    lines += ["", "Created: " + (", ".join(pasted.created) or "nothing")]
    lines += [f"Note: {n}" for n in pasted.notes] + [
        f"Skipped: {s}" for s in pasted.skipped
    ]
    notify(
        TITLE,
        f"Created {len(pasted.created)} raised glyphs. {vfjo.GLYPHS_UNDO_TEXT}",
        "\n".join(lines),
    )


if __name__ == "__main__":
    main()
