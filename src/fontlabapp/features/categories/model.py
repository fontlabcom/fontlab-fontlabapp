# this_file: src/fontlabapp/features/categories/model.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Export Simon Cozens' complete ordered public.openTypeCategories fragment.

The caller supplies the category policy; the Scriptmix adapter uses Glyport's
GSGlyph.category implementation. Never infer a missing category from GDEF.
Read-only native capture preserves all glyphs and refuses an observed change.
"""

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from xml.sax.saxutils import escape

from fontlabapp import _native

Classifier = Callable[[str, list[str]], tuple[str | None, str | None]]


@dataclass(frozen=True)
class CategorySnapshot:
    """All ordered glyph names/categories detached from one document."""

    package_id: int
    rows: tuple[tuple[str, str | None], ...]


def render(report: CategorySnapshot) -> str:
    """Keep original Mark versus base mapping and indentation; escape XML text.

    This is a lib dictionary fragment for manual insertion, not a complete UFO
    or plist. The source deliberately classifies ligatures/components as base.
    """
    lines = ["", "    <key>public.openTypeCategories</key>", "    <dict>", ""]
    for name, category in report.rows:
        lines.extend(
            (
                f"      <key>{escape(name)}</key>",
                f"      <string>{'mark' if category == 'Mark' else 'base'}</string>",
            )
        )
    return "\n".join([*lines, "    </dict>", ""])


def _check(deadline: float) -> None:
    """Bound the complete Python scan; never return a partial dictionary."""
    if monotonic() >= deadline:
        raise TimeoutError("Category scan exceeded its deadline; refresh.")


def _read(deadline: float) -> tuple:
    """Read native names/Unicode directly without the cache-mutating fgGlyph getter."""
    _check(deadline)
    font = _native("fontlab").CurrentFont()
    if font is None:
        raise ValueError("Open a font before exporting categories.")
    rows = []
    for glyph in font.glyphs:
        _check(deadline)
        rows.append(
            (int(glyph.id), str(glyph.name), tuple(int(u) for u in glyph.unicodes))
        )
    _check(deadline)
    return int(font.id), tuple(rows)


def _classify(source: tuple, classify: Classifier, deadline: float) -> tuple:
    """Use the complete supplied policy, including unset and unencoded categories."""
    rows = []
    for _, name, unicodes in source[1]:
        _check(deadline)
        category, _ = classify(name, [f"{code:04X}" for code in unicodes])
        if category is not None and not isinstance(category, str):
            raise TypeError("The glyph category must be text or None.")
        rows.append((name, category))
    _check(deadline)
    return tuple(rows)


def capture(classify: Classifier) -> CategorySnapshot:
    """Fence the full font domain and category results across repeated observations.

    One2sdeadline includes classification. Native calls cannot be preempted;
    preservation and UI behavior remain pending actual FontLab qualification.
    Missing category dependencies propagate; they never become base silently.
    """
    deadline = monotonic() + 2.0
    first = _read(deadline)
    rows = _classify(first, classify, deadline)
    second = _read(deadline)
    repeated = _classify(second, classify, deadline)
    final = _read(deadline)
    if first != second or second != final or rows != repeated:
        raise ValueError(
            "Font, glyph order, names, encodings or categories changed; refresh."
        )
    _check(deadline)
    return CategorySnapshot(first[0], rows)


def show(classify: Classifier) -> object:
    """Open the complete report with the supplied category policy; load Qt lazily."""
    from fontlabapp.features.categories.ui import dialog_type
    from fontlabapp.core.scripting import show_script_dialog

    panel = dialog_type(classify)
    return show_script_dialog(panel, panel.KEY)
