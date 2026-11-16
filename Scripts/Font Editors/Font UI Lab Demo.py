# this_file: Scripts/Font Editors/Font UI Lab Demo.py
# SPDX-License-Identifier: Apache-2.0
"""What: Open three read-only inspection windows over one detached in-memory font.

Use: Inspect fractional metrics, anchors, affine components and Unicode order.
To inspect this same sample in the shared split-pane shell, call
fontlabapp.studios.anchor_component_inspector.show(sample_font()). Its
fontlabapp.fontui.anchor_components_studio assembly retains the anchor inspector
controller, adds numeric table sorting and a read-only TGlyph canvas, and refuses
refresh after the captured default layer changes. Close and reopen that inspector
to inspect a different default layer; the three windows below remain independent.
Safety: Creates only an owned UFO sample. FontLab's main window is used as a
parent; no font document, font registry, file, history or preference is changed.
Close each window independently. Refused cleanup retains its actual controller.
"""


def sample_font():
    """Return an explicitly detached checked Fontport font, never a native font."""
    from fly.fp.live import RFont
    from fly.fp.memory import UFOBackend
    from ufoLib2 import Font
    from ufoLib2.objects import Anchor, Component

    model = Font()
    model.info.familyName, model.info.styleName = "Owned Font UI Lab", "Regular"
    model.info.unitsPerEm = 1000
    model.info.ascender, model.info.descender = 800, -200
    for name, width, codes in (
        ("A", 600.5, [65]),
        ("V", 600.5, [86]),
        ("affine.A", 700.25, []),
        ("space", 250, [32]),
        ("grin", 650, [0x1F600, 0x1F601]),
    ):
        glyph = model.newGlyph(name)
        glyph.width, glyph.unicodes = width, codes
        if name in ("A", "V"):
            pen = glyph.getPen()
            pen.moveTo((0, 0))
            pen.lineTo((300, 700))
            pen.lineTo((600, 0))
            pen.closePath()
    model["A"].anchors = [
        Anchor(100, 700, "top"),
        Anchor(200, 700, "top"),
        Anchor(0, -20, None),
    ]
    model["affine.A"].components = [Component("A", (1.1, 0.125, -0.1, 1, 30.5, -10.25))]
    model.glyphOrder = ["A", "V", "affine.A", "space", "grin"]
    return RFont(UFOBackend(model))


def main():
    """Open the three actual compositions; keep earlier cleanup failures visible."""
    from fly.ap.fontui.glyph_metrics import show as show_metrics
    from fly.ap.fontui.anchor_components import show as show_details
    from fly.ap.fontui.unicode_order import show as show_unicode

    font, opened = sample_font(), []
    try:
        for show in (show_metrics, show_details, show_unicode):
            opened.append(show(font))
    except BaseException as error:
        for owner in reversed(opened):
            try:
                if not owner.release():
                    error.add_note(
                        "An earlier inspection controller retains incomplete cleanup"
                    )
            except BaseException as cleanup:
                error.add_note(f"An earlier inspection cleanup failed: {cleanup!r}")
        raise
    return tuple(opened)


if __name__ == "__main__":
    main()
