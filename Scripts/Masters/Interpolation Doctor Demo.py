# this_file: Scripts/Masters/Interpolation Doctor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Interpolation Doctor: check, count, preview and make masters compatible.

What: Opens the Interpolation Doctor window
(fontlabapp.studios.interpolation_doctor) for the current font. A TGlyph
preview sits beside four tabs. Check compares contours, nodes, anchors and
components across masters and prints the Why You Not Compatible and Master
Node Compatibility reports; Node counts lists contours / nodes per master
and prints both Point Counter reports; Preview ghosts a blend of two masters
with a slider; Fix runs Make Compatible.
Use: Open a font, type glyph names or use the font selection, then press
Check, Count or Show blend. On Fix, press Preview to see the rows, then
"Make compatible on chosen glyphs" to write.
Safety: Check, Node counts and Preview never write. Make Compatible writes the
explicit layers it planned as one named Undo step ("Interpolation Doctor:
..."), then reads the node counts back. Auto layers are skipped; bases of
auto glyphs need the consent tick; hinted layers are refused unless you tick
"Edit hinted layers anyway" or remove PostScript hints. With no font open the
window says so.
"""

TITLE = "Interpolation Doctor Demo"


def main() -> None:
    """Open Interpolation Doctor, or say why it did not open."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box
    from fly.ap.studios.interpolation_doctor import show

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(
            qt,
            parent,
            TITLE,
            f"Interpolation Doctor did not open: {error}",
            "Warning",
            kind.Ok,
        )


if __name__ == "__main__":
    main()
