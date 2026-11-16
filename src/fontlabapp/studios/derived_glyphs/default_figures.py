# this_file: src/fontlabapp/studios/derived_glyphs/default_figures.py
# SPDX-License-Identifier: Apache-2.0
"""Default figures tab: ``Scripts/Components/Set Default Figures.py`` in host mode.

Choose one figure family (Lining .lf, Oldstyle .osf, Tabular lining .tf,
Tabular oldstyle .tosf; remembered in the original's QSettings
"FontLab"/"ScriptDefaultFigures" key ``optionFigures``). Apply makes the ten
default digit cells (zero-nine) show that family as plain components on
every master: missing cells are created with their U+0030-U+0039 code
points, advances and kerning memberships follow the source, anchors stay.
"Replace own contours" (off by default) also removes the cells' contours;
off, they stay (Scriptmix TODO:16). The rebuild consent works as in the
original. The writer is the shared component-set writer
(``_component_sets``); the functions below are the original's, verbatim.
Window placement is no longer saved (the shell owns the window).
"""

from typing import Any

from PythonQt import QtCore, QtGui

from .._kerning_ui import button, combo, get, row as form_row
from . import _shared
from ._component_sets import Pair, component_rows, write_components
from ._shared import PlanPanel, label

glyph_copies = _shared.Modules("copies")
glyph_creation = _shared.Modules("creation")
TITLE = "Set Default Figures"

CHOICES = (
    "Lining (.lf)",
    "Oldstyle (.osf)",
    "Tabular lining (.tf)",
    "Tabular oldstyle (.tosf)",
)


DIGITS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)


def load_family(settings: Any) -> int:
    """Restore the tool's family; absent or malformed values select lining."""
    settings.setFallbacksEnabled(False)
    settings.sync()
    if settings.status() != type(settings).NoError:
        raise RuntimeError("Figure settings could not be read.")
    value = str(settings.value("optionFigures", 0))
    return int(value) if value in ("0", "1", "2", "3") else 0


def save_family(settings: Any, option: int) -> None:
    """Save only the chosen family; report unconfirmed writes without editing fonts."""
    if type(option) is not int or option not in range(4):
        raise ValueError("Choose one of the four figure sets.")
    if not settings.isWritable():
        raise RuntimeError("Figure settings are read-only.")
    settings.setValue("optionFigures", option)
    settings.sync()
    if settings.status() != type(settings).NoError:
        raise RuntimeError("Figure settings could not be saved.")


def mappings(package: Any, option: int = 0) -> list[Pair]:
    """Require every source in the requested family; allow missing default cells."""
    if option not in range(4):
        raise ValueError("Choose one of the four figure sets.")
    suffix = ("lf", "osf", "tf", "tosf")[option]
    pairs = [(name, f"{name}.{suffix}") for name in DIGITS]
    for target, base in pairs:
        if package.findName(base) is None:
            raise ValueError(f"Missing {target} or {base}; no figures changed.")
    return pairs


def apply_pairs(
    package: Any,
    pairs: list[Pair],
    *,
    replace_contours: bool = False,
    allow_rebuild: bool = False,
    kept: list[str] | None = None,
    report: list[str] | None = None,
    disclosure: dict[str, Any] | None = None,
) -> int:
    """Use the single component-set writer with figure-specific preservation rules."""
    return write_components(
        package,
        pairs,
        title=TITLE,
        replace_contours=replace_contours,
        clear_anchors=False,
        allow_rebuild=allow_rebuild,
        kept=kept,
        report=report,
        disclosure=disclosure,
        unicodes={name: (ord("0") + i,) for i, name in enumerate(DIGITS)},
    )


def settings() -> Any:
    """The original's figure-family preferences (tests replace this)."""
    return QtCore.QSettings("FontLab", "ScriptDefaultFigures")


class DefaultFiguresPanel(PlanPanel):
    """Family, Replace own contours, rebuild consent, dry run, Apply to default figures."""

    ACTION = "Apply to default figures"
    UNDO = "set default figures"
    HEADERS = ("Figure source", "Default cell", "Action")
    SELECTION = False

    def __init__(self, tool: Any) -> None:
        self.CONSENT = _shared.backends().creation.REBUILD_LABEL
        self.settings_error = ""
        super().__init__(tool)

    def refresh(self) -> None:
        """Show a preference failure after the first plan, as the original's ``__init__`` did."""
        super().refresh()
        if self.settings_error and self.ready:
            self.status.setText(
                "Saved figure settings could not be loaded: " + self.settings_error
            )
            self.settings_error = ""

    def build_controls(self, form: Any) -> None:
        self.figure_family = combo(self.widget, list(CHOICES))
        self.figure_settings = settings()
        try:
            family = load_family(self.figure_settings)
        except (
            Exception
        ) as error:  # Keep a usable tab on preference failure, as the original does.
            self.settings_error = str(error)
            family = 0
        self.figure_family.setCurrentIndex(family)
        self.figure_family.currentIndexChanged.connect(
            lambda *_: self.contain(self.family_changed)()
        )
        self.replace_contours = QtGui.QCheckBox("Replace own contours")
        form_row(self.widget, form, "Family", self.figure_family)
        form.addWidget(self.replace_contours)
        self.replace_contours.toggled.connect(lambda *_: self.contain(self.refresh)())

    def add_buttons(self, footer: Any) -> None:
        self.check_button = button(
            self.widget, footer, "Check again", self.contain(self.rescan)
        )

    def rescan(self) -> None:
        self.facts = None
        self.refresh()

    def family_changed(self) -> None:
        """Refresh first so a settings error cannot leave the previous preview."""
        self.refresh()
        save_family(self.figure_settings, int(get(self.figure_family.currentIndex)))

    def plan(self, package: Any, facts: Any) -> list[Any]:
        rows = [
            glyph_copies.Row(source, target)
            for target, source in mappings(
                package, int(get(self.figure_family.currentIndex))
            )
        ]
        return component_rows(package, rows, allow_rebuild=self.consented())

    def cells(self, row: Any) -> tuple[str, str | None, tuple[Any, ...]]:
        action = (
            "replace contours and components"
            if self.replace_contours.isChecked()
            else "replace components; keep contours"
        )
        if row.rebuild and not row.note:
            action += " · " + glyph_creation.rebuild_note(row.rebuild)
        return (row.source, None, (row.target, row.note or action))

    def intro(self) -> str:
        package = self.package
        filled = any(
            not row.note and package.findName(row.target) is not None
            for row in self.rows
        )
        return (
            "Source advances and kerning memberships are copied; existing anchors stay. "
            + glyph_creation.undo_text(filled)
            + " Changed kerning memberships are recorded in the same Undo step, or as one more Undo step when no outlines are filled."
        )

    def pending(self, todo: list[Any]) -> str:
        return f"{_shared.plural(len(todo), 'row')} ready"

    def subjects(self, rows: list[Any]) -> list[str]:
        return ["digits"] if any(self.is_ready(r) for r in rows) else []

    def write(self, package: Any, rows: list[Any], facts: Any) -> dict[str, Any]:
        """``apply_pairs`` with the tab's Undo title (same arguments otherwise)."""
        disclosure = {"pending_updates": (), "pending_note": ""}
        report: list[str] = []
        pairs: list[Pair] = [(row.target, row.source) for row in rows]
        count = write_components(
            package,
            pairs,
            title=label(self.UNDO, self.subjects(rows)),
            replace_contours=bool(self.replace_contours.isChecked()),
            clear_anchors=False,
            allow_rebuild=self.consented(),
            unicodes={name: (ord("0") + i,) for i, name in enumerate(DIGITS)},
            report=report,
            disclosure=disclosure,
        )
        return {"layers": count, "report": report, "mismatches": [], **disclosure}

    def result_text(self, result: dict[str, Any]) -> str:
        return f"Changed {result['layers']} master layers." + (
            " " + "; ".join(result["report"]) if result.get("report") else ""
        )


__all__ = [
    "CHOICES",
    "DIGITS",
    "DefaultFiguresPanel",
    "apply_pairs",
    "load_family",
    "mappings",
    "save_family",
    "settings",
]
