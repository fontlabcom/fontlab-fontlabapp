# this_file: src/fontlabapp/fontui/core_pythonqt_labs/profiles/e07_e09_actions.py
# SPDX-License-Identifier: Apache-2.0
"""Explicit shared-shell actions for proof, Unicode and review lesson controls."""
import json
from typing import Any

from fontlabapp.qt.properties import value

REFRESH = {
    "Glyph Batch Recipe Settings": "preview", "Glyph Proof Batch Wizard": "preview",
    "Glyph Proof Groups": "preview", "Glyph Proof Worksheet": "refresh",
    "Pair Proof Generator": "refresh_output", "Saved Proof Sample": "check_coverage",
    "Glyph Proof Layout": "refresh", "Glyph Proof Pad": "refresh",
    "Glyph Coverage Grid": "refresh", "Glyph Encoding Chart": "refresh",
    "Glyph Character Map": "refresh", "Glyph Character Map - Styles": "refresh",
    "Proof Text Coverage Dialog": "preview", "Unicode Issues Dock": "refresh_issues",
    "Apply Unicode Map": "refresh", "Glyph Mark Colours": "refresh",
    "Glyph Review Form": "refresh", "Glyph Review Priorities": "refresh",
    "Glyph Mark Colour Board": "refresh", "Glyph Review Cards": "refresh",
}


def proof_text(child: Any, title: str) -> str | tuple[str, ...]:
    """Read the actual result or captured identities without changing local drafts."""
    if title == "Glyph Batch Recipe Settings":
        return tuple(json.loads(child.output.toPlainText())["glyphs"])
    if title in ("Glyph Proof Batch Wizard", "Glyph Proof Groups"):
        return str(child.output.toPlainText())
    if title == "Pair Proof Generator":
        return str(child.output_box.toPlainText())
    if title == "Saved Proof Sample":
        return child.sample_text()
    if title == "Glyph Proof Worksheet":
        from .glyph_proof_worksheet import report
        if child.pending:
            raise ValueError("Apply Draft before previewing the proof.")
        return report(child.snapshot, child.drafts)
    if title in ("Glyph Character Map", "Glyph Character Map - Styles"):
        return str(value(child.text, "text"))
    if title == "Proof Text Coverage Dialog":
        return child.draft
    if title == "Unicode Issues Dock":
        return tuple(dict.fromkeys(row[0] for row in child.issue_snapshot))
    if title in ("Glyph Proof Layout", "Glyph Proof Pad", "Apply Unicode Map"):
        return tuple(child.names)
    if title == "Glyph Review Form":
        return (child.snapshot[child.current_row - 1][0],) if child.snapshot else ()
    if title in ("Glyph Mark Colours", "Glyph Review Priorities"):
        from .table_sorting import source_row
        index = value(child.table_view, "currentIndex")
        if value(index, "isValid"):
            return (child.snapshot[source_row(child, index)][0],)
        return tuple(row[0] for row in child.snapshot[:1])
    if title == "Glyph Review Cards":
        return tuple(name for name, _state, _note in child.cards)
    if title == "Glyph Mark Colour Board":
        return tuple(child.names)
    return tuple(row[0] for row in child.snapshot)


def bindings(child: Any, title: str, publish: Any) -> dict[str, Any]:
    """Connect real profile actions; writers keep their own validation and history."""
    panel = child.controller if title == "Unicode Issues Dock" else child
    refresh = getattr(panel, REFRESH[title])

    def dirty() -> bool:
        if title == "Glyph Review Cards":
            return panel.has_draft()
        # SelectionPanel (Apply Unicode Map) defines ``pending`` as a hook method;
        # a bound method is always truthy, so only plain flags count as staged edits.
        flags = (getattr(panel, "dirty", False), getattr(panel, "pending", False))
        return any(flag for flag in flags if not callable(flag))

    def preview() -> None:
        if title in ("Glyph Batch Recipe Settings", "Glyph Proof Batch Wizard", "Glyph Proof Groups", "Pair Proof Generator"):
            refresh()
        publish(proof_text(panel, title))

    result = {"refresh": refresh, "preview": preview, "dirty": dirty}
    if getattr(panel, "status", None) is not None:
        result["status"] = lambda: str(value(panel.status, "text") or "")
    if title in ("Glyph Mark Colours", "Glyph Review Form"):
        result.update(apply=panel.apply, ready=lambda: bool(panel.snapshot) and dirty())
    elif title == "Apply Unicode Map":
        result.update(apply=panel.apply, ready=lambda: any(panel.is_ready(row) for row in panel.rows), apply_label="Apply Map")
    return result
