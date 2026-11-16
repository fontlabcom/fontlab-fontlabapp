# this_file: src/fontlabapp/glyphs/unicode/duplicates/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Complete bounded Unicode/identity/dependency facts without fgGlyph conversion."""

from time import monotonic
from typing import Any

from fontlabapp.glyphs.unicode.duplicates.model import Glyph, groups
from fontlabapp.qt.safe import qt_list


def check(deadline: float) -> None:
    """A partial whole-font observation must never become an editable preview."""
    if monotonic() >= deadline:
        raise TimeoutError("Unicode operation expired; rescan before editing.")


def read(package: Any, font: Any, deadline: float, stamp: Any) -> tuple:
    """Use font-owned FontGate records; retain ordered codes and layer identities."""
    glyphs, dependencies, layer_ids = [], [], set()
    for record in font.glyphs:
        check(deadline)
        glyph = package.findFgId(int(record.id))
        if glyph is None or glyph.isNull or not glyph.isValid:
            raise ValueError("Native glyph mapping is missing; rescan.")
        if (
            int(glyph.fgGlyphId) != int(record.id)
            or glyph.name != record.name
            or int(glyph.package.id) != int(package.id)
        ):
            raise ValueError("Glyph identity, name or owner changed; rescan.")
        layers = []
        for layer in glyph.layers:
            check(deadline)
            identity = int(layer.id)
            if identity in layer_ids:
                raise ValueError("Shared layer identity has ambiguous ownership.")
            layer_ids.add(identity)
            layers.append((identity, str(layer.name), bool(layer.autoLayer)))
            bases = []
            for shape in layer.shapes:
                check(deadline)
                if shape.isComponent:
                    bases.append(str(shape.shapeData.componentGlyph))
            dependencies.append((str(record.name), bool(layer.autoLayer), tuple(bases)))
        glyphs.append(
            Glyph(
                int(record.id),
                int(glyph.id),
                record.name,
                tuple(record.unicodes),
                tuple(layers),
                stamp(glyph),
            )
        )
    result = tuple(glyphs)
    groups(result)
    check(deadline)
    return result, tuple(dependencies)


def require_no_editors(
    qt: Any, deadline: float, action: str = "removing Unicode assignments"
) -> None:
    """Refuse even inactive Glyph editors before the known Unicode save-cache gap.

    Reuse App's GC-protected conversion; inspect only the known QWidget class
    predicate, never widget property values or preferences. Native qualification
    remains required, including complete full-font preservation.
    """
    check(deadline)
    for widget in qt_list(qt.QtGui.QApplication.allWidgets):
        check(deadline)
        editor = widget.inherits("GlyphWindow")
        if type(editor) is not bool:
            raise ValueError("The open editor state is unreadable.")
        if editor:
            raise ValueError(
                f"Close all Glyph editors, then activate the Font window before {action}."
            )
    check(deadline)
