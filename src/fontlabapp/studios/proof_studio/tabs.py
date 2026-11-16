# this_file: src/fontlabapp/studios/proof_studio/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""Proof Studio tab panel: generator, choice, part and seed pickers, fields, preview, copy and open.

What: one ``GeneratorTab`` per registry tab (Pattern strings, Kerning proofs,
Real text, Random, Word finder, Waterfall, By master). Each generator gets a
page of its own fields and action buttons; changing the generator, choice,
part, seed or a field regenerates the proof and previews it in TMetrics
(contract §1.8). The read-only text box shows the exact text that Copy puts
on the clipboard; a report box shows action reports (coverage JSON).
"Open in FontLab Glyph tab" runs the absorbed script's backend. A generator
with a settings namespace loads from it at build and saves after user
edits (or on its explicit Save action). Nothing here writes to the font.
Used by ``fontlabapp.studios.proof_studio`` (tab builders).
"""

from collections.abc import Callable
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import proof_view_types

from .generators import Context, Field, Generator, Outcome, Proof, for_tab
from .session import Studio

OPEN = "Open in FontLab Glyph tab"
SEED_ERROR = "Seed must be a whole number (or empty for an unseeded draw)."


def _button(owner: Any, layout: Any, text: str, slot: Callable[[], Any]) -> Any:
    button = QtGui.QPushButton(text, owner)
    button.setAccessibleName(text)
    button.clicked.connect(lambda *args: slot())
    layout.addWidget(button)
    return button


def _combo(owner: Any, layout: Any, label: str) -> tuple[Any, Any]:
    caption = QtGui.QLabel(label, owner)
    layout.addWidget(caption)
    combo = QtGui.QComboBox(owner)
    combo.setAccessibleName(label)
    layout.addWidget(combo)
    return caption, combo


def _get(owner: Any, name: str) -> Any:
    """A Qt property that PythonQt exposes as a value and PySide6 as a method."""
    item = getattr(owner, name)
    return item() if callable(item) else item


def _index(combo: Any) -> int:
    """``currentIndex`` is a property in PythonQt and a method in PySide6."""
    return int(_get(combo, "currentIndex"))


def _clipboard(text: str) -> None:
    QtGui.QApplication.clipboard().setText(text)


def _settings(organization: str, application: str) -> Any:
    """The absorbed tool's own QSettings namespace, fallbacks off (as the originals)."""
    settings = QtCore.QSettings(organization, application)
    settings.setFallbacksEnabled(False)
    return settings


class GeneratorTab:
    """Controls for the generators of one registry tab over the shared studio."""

    def __init__(
        self,
        studio: Studio,
        title: str,
        *,
        clipboard: Callable[[str], Any] = _clipboard,
        settings: Callable[[str, str], Any] | None = None,
        generators: tuple[Generator, ...] | None = None,
        parent: Any = None,
    ) -> None:
        self.studio = studio
        self.title = title
        self.clipboard = clipboard
        self.settings_factory = settings or getattr(studio, "settings", None) or _settings
        self.generators = for_tab(title) if generators is None else generators
        self.proof: Proof | None = None
        self.settings: dict[str, Any] = {}
        self.inputs: dict[str, dict[str, Any]] = {}
        self.extras: dict[str, dict[str, Any]] = {}
        self.notes: dict[str, Any] = {}
        self.canvases: dict[str, Any] = {}
        self.closed = False
        self.widget = QtGui.QWidget(parent)
        layout = QtGui.QVBoxLayout(self.widget)
        row = QtGui.QHBoxLayout()
        layout.addLayout(row)
        _caption, self.picker = _combo(self.widget, row, "Generator")
        self.choice_caption, self.choice = _combo(self.widget, row, "Source")
        self.part_caption, self.part = _combo(self.widget, row, "Tab")
        self.seed_caption = QtGui.QLabel("Seed", self.widget)
        row.addWidget(self.seed_caption)
        self.seed = QtGui.QLineEdit(self.widget)
        self.seed.setAccessibleName("Seed")
        self.seed.setPlaceholderText("unseeded")
        row.addWidget(self.seed)
        for generator in self.generators:
            self.picker.addItem(generator.title)
        self.pages = QtGui.QStackedWidget(self.widget)
        layout.addWidget(self.pages)
        masters = self._masters()
        for generator in self.generators:
            self.pages.addWidget(self._page(generator, masters))
        self.text = QtGui.QPlainTextEdit(self.widget)
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Proof text")
        layout.addWidget(self.text)
        self.report = QtGui.QPlainTextEdit(self.widget)
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Report")
        self.report.hide()
        layout.addWidget(self.report)
        buttons = QtGui.QHBoxLayout()
        layout.addLayout(buttons)
        _button(self.widget, buttons, "Preview", self.regenerate)
        _button(self.widget, buttons, "Copy", self.copy)
        self.open_button = _button(self.widget, buttons, OPEN, self.open)
        self._fill_choices()
        self.picker.currentIndexChanged.connect(lambda *args: self._fill_choices())
        self.choice.currentIndexChanged.connect(lambda *args: self.regenerate())
        self.part.currentIndexChanged.connect(lambda *args: self.show_part())
        self.seed.textChanged.connect(lambda *args: self.regenerate())

    # Build ---------------------------------------------------------------------
    def _masters(self) -> tuple[tuple[str, ...], str]:
        """Master names and the active master, read once when a generator has a Master field."""
        if not any(f.kind == "master" for g in self.generators for f in g.fields):
            return (), ""
        try:
            facts = self.studio.facts()
        except Exception as error:  # noqa: BLE001 - an empty Master list, the reason in the status
            self.studio.shell.set_status(f"Masters were not read: {error}")
            facts = None
        return (facts.masters, facts.master) if facts is not None else ((), "")

    def _page(self, generator: Generator, masters: tuple[tuple[str, ...], str]) -> Any:
        page = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        note = QtGui.QLabel("", page)
        note.setWordWrap(True)
        note.hide()
        layout.addWidget(note)
        self.notes[generator.key] = note
        form = QtGui.QFormLayout()
        layout.addLayout(form)
        inputs = self.inputs[generator.key] = {}
        self.extras[generator.key] = {}
        for spec in generator.fields:
            control = self._control(spec, page, masters)
            caption = QtGui.QLabel(spec.label, page)
            caption.setBuddy(control)
            form.addRow(caption, control)
            inputs[spec.key] = control
        if generator.canvas:
            self.canvases[generator.key] = self._canvas(generator, page, layout)
        if generator.actions:
            row = QtGui.QHBoxLayout()
            layout.addLayout(row)
            for action in generator.actions:
                _button(page, row, action.label, lambda a=action, g=generator: self.run(g, a))
        if generator.settings is not None:
            self.settings[generator.key] = self.settings_factory(*generator.settings)
            outcome = self.studio.load(generator, self.settings[generator.key])
            if outcome is not None:
                self._apply(generator, outcome)
                if outcome.status:
                    note.setText(outcome.status)
                    note.show()
        for spec in generator.fields:
            self._connect(spec, inputs[spec.key])
        return page

    def _canvas(self, generator: Generator, page: Any, layout: Any) -> Any:
        """The absorbed panel's own stacked proof view, scrollable; None when it cannot be built."""
        try:
            view = getattr(proof_view_types(), generator.canvas)()
        except Exception as error:  # noqa: BLE001 - keep the tab; the reason goes to the status
            self.studio.shell.set_status(f"{generator.title}: stacked view unavailable: {error}")
            return None
        view.setAccessibleName(f"{generator.title} proof")
        scroll = QtGui.QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(220)
        scroll.setWidget(view)
        layout.addWidget(scroll, 1)
        return view

    def _control(self, spec: Field, page: Any, masters: tuple[tuple[str, ...], str]) -> Any:
        if spec.kind == "text":
            control = QtGui.QPlainTextEdit(page)
            control.setPlainText(str(spec.default))
            control.setMaximumHeight(110)
        elif spec.kind == "int":
            control = QtGui.QSpinBox(page)
            control.setRange(spec.minimum, spec.maximum)
            control.setValue(int(spec.default))
        elif spec.kind in ("combo", "master"):
            control = QtGui.QComboBox(page)
            names, active = masters
            items = names if spec.kind == "master" else spec.items
            for item in items:
                control.addItem(item)
            if spec.kind == "master":
                control.setCurrentIndex(names.index(active) if active in names else 0)
            else:
                control.setCurrentIndex(int(spec.default))
        else:
            control = QtGui.QLineEdit(page)
            control.setText(str(spec.default))
            if spec.placeholder:
                control.setPlaceholderText(spec.placeholder)
        control.setAccessibleName(spec.label)
        return control

    def _connect(self, spec: Field, control: Any) -> None:
        signal = {
            "text": "textChanged",
            "int": "valueChanged",
            "combo": "currentIndexChanged",
            "master": "currentIndexChanged",
        }.get(spec.kind, "textChanged")
        getattr(control, signal).connect(lambda *args: self.edited())

    # State ---------------------------------------------------------------------
    def generator(self) -> Generator | None:
        index = _index(self.picker)
        return self.generators[index] if 0 <= index < len(self.generators) else None

    def choice_key(self) -> str | None:
        generator, index = self.generator(), _index(self.choice)
        if generator is None or not 0 <= index < len(generator.choices):
            return None
        return generator.choices[index][1]

    def values(self, generator: Generator | None = None) -> dict[str, Any]:
        """The generator's field values (by key) plus values its load/actions keep."""
        generator = generator or self.generator()
        if generator is None:
            return {}
        values = dict(self.extras[generator.key])
        for spec in generator.fields:
            control = self.inputs[generator.key][spec.key]
            if spec.kind == "text":
                values[spec.key] = control.toPlainText()
            elif spec.kind == "int":
                values[spec.key] = int(_get(control, "value"))
            elif spec.kind == "combo":
                values[spec.key] = _index(control)
            elif spec.kind == "master":
                values[spec.key] = str(_get(control, "currentText"))
            else:
                values[spec.key] = str(_get(control, "text"))
        return values

    def seed_value(self) -> int | None:
        """The Seed field as an int; None when empty. ValueError when not a whole number."""
        text = str(_get(self.seed, "text")).strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            raise ValueError(SEED_ERROR) from None

    def context(self) -> Context | None:
        generator, key = self.generator(), self.choice_key()
        if generator is None or key is None:
            return None
        settings = self.settings.get(generator.key)
        return Context(key, self.values(generator), settings, self.proof, max(_index(self.part), 0),
                       cancelled=lambda: self.closed)

    def _apply(self, generator: Generator, outcome: Outcome) -> None:
        """Set the outcome's combo items and values without triggering edits."""
        inputs = self.inputs[generator.key]
        kinds = {spec.key: spec.kind for spec in generator.fields}
        for key, items in outcome.items.items():
            control = inputs[key]
            control.blockSignals(True)
            control.clear()
            for item in items:
                control.addItem(item)
            control.blockSignals(False)
        for key, value in outcome.values.items():
            if key not in inputs:
                self.extras[generator.key][key] = value
                continue
            control, kind = inputs[key], kinds[key]
            control.blockSignals(True)
            if kind == "text":
                control.setPlainText(str(value))
            elif kind == "int":
                control.setValue(int(value))
            elif kind == "combo":
                control.setCurrentIndex(int(value))
            elif kind == "master":
                index = control.findText(str(value))
                control.setCurrentIndex(max(index, 0))
            else:
                control.setText(str(value))
            control.blockSignals(False)
        if outcome.report is not None:
            self.report.setPlainText(outcome.report)
            self.report.setVisible(bool(outcome.report))

    # Actions -------------------------------------------------------------------
    def _fill_choices(self) -> None:
        generator = self.generator()
        self.choice.blockSignals(True)
        self.choice.clear()
        for label, _key in generator.choices if generator else ():
            self.choice.addItem(label)
        self.choice.blockSignals(False)
        many = generator is not None and len(generator.choices) > 1
        self.choice.setVisible(many)
        self.choice_caption.setVisible(many)
        self.choice_caption.setText(generator.choice_label if generator else "Source")
        self.part_caption.setText(generator.part_label if generator else "Tab")
        seeded = generator is not None and generator.seeded
        self.seed.setVisible(seeded)
        self.seed_caption.setVisible(seeded)
        self.open_button.setEnabled(generator is not None and generator.opens)
        if generator is not None:
            self.pages.setCurrentIndex(self.generators.index(generator))
        self.report.setPlainText("")
        self.report.hide()
        self.regenerate()

    def regenerate(self) -> Proof | None:
        """Make the proof for the current generator, choice, seed and fields, then preview part 1."""
        generator, key = self.generator(), self.choice_key()
        self.proof = None
        if generator and key:
            try:
                seed = self.seed_value() if generator.seeded else None
            except ValueError as error:
                self.studio.shell.set_status(str(error))
            else:
                self.proof = self.studio.generate(generator, key, seed=seed, values=self.values(generator))
        parts = len(self.proof.parts) if self.proof else 0
        labels = self.proof.labels if self.proof and self.proof.labels else ()
        self.part.blockSignals(True)
        self.part.clear()
        for number in range(parts):
            self.part.addItem(labels[number] if number < len(labels) else f"Tab {number + 1} of {parts}")
        self.part.setEnabled(parts > 1)
        self.part.blockSignals(False)
        self.show_part()
        if generator and key and generator.key in self.canvases:
            self.studio.paint(generator, key, self.canvases[generator.key], self.proof)
        return self.proof

    def close(self) -> None:
        """The window is closing: cancel a running Master text comparison Open."""
        self.closed = True

    def edited(self) -> Proof | None:
        """A field edit: regenerate, then save to the generator's settings when it saves on edit."""
        previous = self.proof
        proof = self.regenerate()
        generator = self.generator()
        if generator is not None and generator.save is not None:
            # The original saves every edit, even while its output cannot be made
            # (a malformed character class): the last output is kept.
            kept = proof if proof is not None else previous or Proof(())
            self.studio.save(generator, self.settings[generator.key], self.values(generator), kept)
        return proof

    def show_part(self) -> str:
        """Preview the chosen part and show its exact text."""
        part = max(_index(self.part), 0)
        self.text.setPlainText(self.proof.parts[part] if self.proof and part < len(self.proof.parts) else "")
        return self.studio.show(self.proof, part)

    def copy(self) -> str | None:
        return self.studio.copy(self.proof, max(_index(self.part), 0), self.clipboard)

    def open(self) -> bool:
        generator, context = self.generator(), self.context()
        if generator is None or context is None:
            return False
        if generator.open_current is not None:
            return self.studio.open(generator, context.choice, context)
        return self.studio.open(generator, context.choice)

    def run(self, generator: Generator, action: Any) -> Outcome | None:
        """Run a generator button, apply what it returns and regenerate."""
        context = self.context()
        if context is None:
            return None
        outcome = self.studio.run(generator, action, context)
        if outcome is not None:
            self._apply(generator, outcome)
            self.regenerate()
            if outcome.status:
                self.studio.shell.set_status(outcome.status)
        return outcome


__all__ = ["OPEN", "SEED_ERROR", "GeneratorTab"]
