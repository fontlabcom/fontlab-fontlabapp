# this_file: src/fontlabapp/studios/derived_glyphs/compat_placeholders.py
# SPDX-License-Identifier: Apache-2.0
'Create empty placeholder glyphs from typed glyph names or characters, on every\nmaster.\n\nWhat it does:\n    Type or paste glyph names and characters, separated by spaces, commas or\n    new lines. The script creates one empty glyph per entry, with a layer on\n    every master and the chosen advance width. A single non-ASCII character\n    becomes\n    uniXXXX (or uXXXXX) and gets that code point. A name of that form also\n    gets its code point, unless another glyph has it already. ASCII tokens\n    are glyph names: A stays A; & and 1 are invalid names.\n\nHow it works:\n    A small non-modal panel shows a live table: the name, the code point and\n    what will happen. Existing glyphs, repeated entries and invalid names\n    are listed and skipped. Create checks the font again. FontLab\'s own Add\n    Glyph command makes each new glyph with a layer on every master, the\n    advance width and the code point (shared module fly.ap.glyphs.creation).\n    After the write the script reads every new glyph back, and checks that\n    no automatic glyph of the font changed.\n\nWhy this design:\n    - Placeholders let you build features, classes, kerning groups and test\n      strings before the drawings exist. Unlike Font > Add Glyphs, the panel\n      takes characters directly, previews every name and code point, and\n      skips what exists instead of asking.\n    - An existing glyph is never overwritten, and a code point that another\n      glyph has is never assigned twice.\n    - FontLab\'s text conversion can change some characters, so the script\n      refuses text with NUL, no-break space or the Unicode line and paragraph\n      separators instead of creating changed names.\n    - A code point write needs an active Font window and no open Glyph\n      window, as every Unicode writer of this menu does. Create discloses\n      queued ids and their possible date changes. The script does not\n      call UpdateAll (fl#8537).\n    - FontLab can rebuild an automatic glyph when a new name appears. When\n      the font has automatic glyphs without a recipe whose names share a\n      dotted suffix with a new name (a new e.sc and eacute.sc), the row\n      shows "may rebuild auto ..." and is skipped unless you tick "Create\n      even if FontLab may rebuild these auto glyphs". A change of the text\n      clears the tick.\n    - Each new glyph is recorded as its own Undo step.\n\nHow to use:\n    Open a font and activate its Font window. Run the script. Type the names\n    or characters, set the advance width, check the table and press Create.\n\nBenefit:\n    A complete glyph set skeleton, named and encoded, in seconds.\n\nCredit:\n    Adapted from the author\'s own FontLab sample, Apache-2.0\n    (generate_placeholder_glyphs.py, "Placeholder Glyphs").'
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fontlabapp.studios.derived_glyphs.placeholders import Entry, Row
TITLE = "Placeholder Glyphs"
KEY = "generate_placeholder_glyphs"
NAME = re.compile(r"[A-Za-z_.][A-Za-z0-9_.-]*")
UNI = re.compile(r"uni([0-9A-F]{4})|u([0-9A-F]{5,6})")
UNSAFE = (
    ("\x00", "NUL"),
    ("\u00a0", "no-break space"),
    ("\u2028", "line separator"),
    ("\u2029", "paragraph separator"),
)
MAX_ROWS = 500
def check_text(text: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.check_text(text)


def char_name(char: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.char_name(char)


def code_of(name: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.code_of(name)


def parse(text: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.parse(text)


def font_codes():
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.font_codes()


def plan(entries: Sequence[Entry], exists: Callable[[str], bool], codes: dict[int, str]):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.plan(entries, exists, codes)


def gate(package: Any, rows: Sequence[Row], facts: Any, allow_rebuild: bool):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.gate(package, rows, facts, allow_rebuild)


def create(package: Any, rows: Sequence[Row], advance: int, facts: Any, allow_rebuild: bool=False):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import placeholders as implementation
    return implementation.create(package, rows, advance, facts, allow_rebuild)


def __getattr__(name: str):
    if name not in ("Entry", "Row"):
        raise AttributeError(name)
    from fontlabapp.studios.derived_glyphs import placeholders
    return getattr(placeholders, name)

def panel_type() -> type:
    """Build the panel class once Qt is available (inside FontLab)."""
    from fontlabapp.fontui import outline_generators_backends
    glyph_creation = outline_generators_backends().glyph_creation
    import fontlabapp.core.history.glyphs as history
    from fontlabapp.fontui import outline_generators_backends
    layer_writer = outline_generators_backends().layer_writer
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - avoid native parent fallback
    from fontlabapp.fontui import outline_generators_backends
    qt = outline_generators_backends().qt

    QtGui = qt.QtGui
    plural = layer_writer.plural

    class PlaceholderPanel(QtGui.QDialog):
        """Names, advance width, rebuild consent, live preview table, status and buttons."""

        def __init__(self, parent: Any = None) -> None:
            QtGui.QDialog.__init__(self, parent)
            self._connections: list[Any] = []
            self.rows: list[Row] = []
            self.package_id: int | None = None
            self.facts: Any = None
            self.last_result: dict[str, Any] = {}
            self.setWindowTitle(TITLE)
            self.setMinimumWidth(540)
            root = QtGui.QVBoxLayout(self)
            root.setContentsMargins(20, 18, 20, 16)
            root.setSpacing(12)
            heading = QtGui.QLabel(TITLE)
            face = heading.font
            face.setPointSizeF(face.pointSizeF() * 1.35)
            face.setBold(True)
            heading.setFont(face)
            root.addWidget(heading)
            self.subtitle = QtGui.QLabel("")
            self.subtitle.setWordWrap(True)
            root.addWidget(self.subtitle)
            self.names = QtGui.QPlainTextEdit()
            self.names.setPlaceholderText("e.g.  A.alt  ampersand.ss01  Ω  ₿")
            self.names.setMaximumHeight(90)
            root.addWidget(self.names)
            grid = QtGui.QGridLayout()
            grid.setHorizontalSpacing(10)
            self.advance = QtGui.QSpinBox()
            self.advance.setRange(0, 4000)
            self.advance.setSuffix(" units")
            self.advance.setValue(600)
            grid.addWidget(QtGui.QLabel("Advance width"), 0, 0)
            grid.addWidget(self.advance, 0, 1)
            self.consent = QtGui.QCheckBox(glyph_creation.REBUILD_LABEL)
            grid.addWidget(self.consent, 1, 0, 1, 3)
            grid.setColumnStretch(2, 1)
            root.addLayout(grid)
            self.table = QtGui.QTableWidget(0, 3)
            self.table.setHorizontalHeaderLabels(["Glyph", "Unicode", "Action"])
            self.table.verticalHeader().setVisible(False)
            self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
            self.table.horizontalHeader().setSectionResizeMode(
                QtGui.QHeaderView.Stretch
            )
            self.table.setMinimumHeight(200)
            root.addWidget(self.table, 1)
            footer = QtGui.QHBoxLayout()
            self.status = QtGui.QLabel("")
            self.status.setWordWrap(True)
            footer.addWidget(self.status, 1)
            self.close_button = QtGui.QPushButton("Close")
            self.apply_button = QtGui.QPushButton("Create")
            self.apply_button.setDefault(True)
            footer.addWidget(self.close_button)
            footer.addWidget(self.apply_button)
            root.addLayout(footer)
            for signal, slot in (
                (self.names.textChanged, lambda *a: self.text_changed()),
                (self.consent.toggled, lambda *a: self.refresh()),
                (self.apply_button.clicked, lambda *a: self.apply()),
                (self.close_button.clicked, lambda *a: self.close()),
            ):
                scripting.connect_guarded(self, signal, slot)
            try:
                package = scripting.current_package()
                if package is not None:
                    self.package_id = package.id
                    self.facts = history.scan_auto_facts(package)
            except (ValueError, RuntimeError, TimeoutError) as error:
                self.status.setText(str(error))
            self.refresh()

        def font_package(self) -> Any:
            """Return the bound font. Refuse a closed or switched font."""
            if self.package_id is None:
                raise ValueError("Open a font first. Then run this script again.")
            package = scripting.current_package()
            if package is None or package.id != self.package_id:
                raise ValueError("The font changed. Run this script again.")
            return package

        def consented(self) -> bool:
            """True when the user ticked the rebuild consent."""
            return bool(self.consent.isChecked())

        def plan(self, facts: Any = None) -> list[Row]:
            """Plan the typed text against the live font; gate rebuild candidates."""
            package = self.font_package()
            entries = parse(self.names.toPlainText())
            rows = plan(
                entries, lambda name: package.findName(name) is not None, font_codes()
            )
            if facts is None:
                if self.facts is None:
                    self.facts = history.scan_auto_facts(package)
                facts = self.facts
            return gate(package, rows, facts, self.consented())

        def text_changed(self) -> None:
            """New text: clear the rebuild consent, then plan again."""
            self.consent.setChecked(False)
            self.refresh()

        def refresh(self) -> None:
            """Recompute the preview. A refusal disables Create and shows its reason."""
            try:
                self.rows = self.plan()
                masters = len(self.font_package().masters)
            except (ValueError, RuntimeError, TimeoutError) as error:
                self.rows = []
                self.table.setRowCount(0)
                self.subtitle.setText(str(error))
                self.apply_button.setEnabled(False)
                return
            self.subtitle.setText(
                f"Creates empty glyphs on all {masters} masters. Existing glyphs are never overwritten."
            )
            visible = self.rows[:MAX_ROWS]
            self.table.setRowCount(len(visible))
            for number, row in enumerate(visible):
                action = (
                    f"{row.problem}: skipped"
                    if row.problem
                    else f"create on {masters} masters"
                )
                if row.rebuild and not row.problem:
                    action += " · " + glyph_creation.rebuild_note(row.rebuild)
                for column, text in enumerate((row.name, row.note, action)):
                    self.table.setItem(number, column, QtGui.QTableWidgetItem(text))
            ready = sum(1 for r in self.rows if not r.problem)
            self.apply_button.setEnabled(ready > 0)
            more = (
                f" (table shows the first {MAX_ROWS})"
                if len(self.rows) > MAX_ROWS
                else ""
            )
            self.status.setText(
                f"{plural(ready, 'glyph')} to create · {len(self.rows) - ready} skipped{more}"
            )

        def apply(self) -> None:
            """Scan the font again, plan, then create each glyph with FontLab's Add Glyph command."""
            try:
                package = self.font_package()
                facts = history.scan_auto_facts(package)
                rows = self.plan(facts)
                result = create(
                    package, rows, int(self.advance.value), facts, self.consented()
                )
            except (ValueError, RuntimeError, TimeoutError) as error:
                self.refresh()
                self.status.setText(str(error))
                return
            self.facts = facts
            self.last_result = result
            self.refresh()
            if not result["glyphs"]:
                self.status.setText("Nothing to create")
                return
            text = (
                f"Created {plural(result['glyphs'], 'glyph')} ({plural(result['layers'], 'master layer')}, "
                f"{plural(result['codes'], 'code point')})"
            )
            if result["mismatches"]:
                text += " · did not read back as planned: " + "; ".join(
                    result["mismatches"][:5]
                )
            note = result.get("pending_note", "")
            self.status.setText(f"{text} · {note}" if note else text)

        def closeEvent(self, event: Any) -> None:
            """Disconnect owned signals, then delete the panel."""
            scripting.close_script_dialog(self, event, KEY)

    return PlaceholderPanel

def main() -> Any:
    """Open the panel. A second run replaces the first panel."""
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - avoid native parent fallback

    return scripting.show_script_dialog(panel_type(), KEY)
