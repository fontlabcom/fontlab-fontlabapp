# this_file: src/fontlabapp/masters/text/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned nonmodal Master Text Comparison panel; original controls and presets.

Qt contracts: QListWidget.itemDoubleClicked, QWidget.save/restoreGeometry,
QSettings per-application namespace with fallbacks disabled. No custom theme,
native event loop, FontLab preferences or Output writes. PythonQt UTF16/IME
getter fidelity still requires native qualification; diagnostics use escaped JSON.
"""

from collections.abc import Callable
from dataclasses import asdict
import json
from pathlib import Path
from time import monotonic
from typing import Any
from fontlabapp.core.signals.scope import Scope
from fontlabapp.masters.text.model import (
    analyze,
    select_text,
    NoUsableGlyphs,
    checkpoint,
)
from fontlabapp.masters.text.settings import (
    PRESET_FILE,
    load,
    load_presets,
    presets_directory,
    read_presets,
    save,
)
from fontlabapp.qt.properties import value
from fontlabapp.masters.text.owners import require_clear, retain, release


def custom_text(editor: Any, check: Callable) -> str:
    """Read source's single-line custom field without Qt plaintext folding.

    QTextBlock.text preserves NBSP/LS; QTextDocument.characterCount counts
    UTF16 units plus its final paragraph mark. Refuse paragraphs and mismatched
    getter lengths (native NUL truncation), never accept a silently changed run.
    Physical multiline/PS custom input is held; UTF8 presets carry exact scalars.
    """
    check()
    document = editor.document()
    if value(document, "blockCount") != 1:
        raise ValueError(
            "Multiline/paragraph custom text is held; load exact UTF-8 presets instead."
        )
    text = str(value(document.firstBlock(), "text"))
    check()
    if value(document, "characterCount") != len(text.encode("utf-16-le")) // 2 + 1:
        raise ValueError(
            "Native UTF16/NUL custom getter cannot represent the full input; use named tokens or exact UTF-8 presets."
        )
    check()
    return text


def panel_type(core: Any, gui: Any) -> type:
    """Bind lazily; tests inject real isolated Qt and an owned settings store."""

    class ComparisonPanel(gui.QDialog):
        def __init__(
            self,
            parent: Any,
            opening: Any,
            run: Callable,
            *,
            settings: Any = None,
            directory: Path | None = None,
            deadline: float | None = None,
        ) -> None:
            opening_deadline = monotonic() + 3.0 if deadline is None else deadline
            limit = opening_deadline - 0.5
            checkpoint(limit, monotonic, lambda: False)
            require_clear()
            gui.QDialog.__init__(self, parent)
            try:
                self.closed = self.busy = False
                self.scopes, self.status, self.last_error = [], None, ""
                self.opening, self.run, self.settings = opening, run, settings
                self.selected, self.presets, self.comparison_result = -1, (), None
                self.geometry_saved = self.custom_held = False
                self.last_failure = self.custom_save_hold = None
                self._comparison_delete_scheduled = False
                self._comparison_native_destroyed = False
                check = lambda: checkpoint(limit, monotonic, lambda: self.closed)
                self.terminal = Scope(self.failure)
                self.terminal.connect(
                    self.destroyed, lambda *args: self.destroyed_cleanup(), closing=True
                )
                self.setWindowTitle("Master Text Comparison")
                self.resize(540, 500)
                root = gui.QVBoxLayout(self)
                root.addWidget(
                    gui.QLabel(
                        "Comma-separated text (unavailable characters are omitted):"
                    )
                )
                self.words_edit = gui.QPlainTextEdit()
                root.addWidget(self.words_edit)
                self.arrangement = gui.QComboBox()
                self.arrangement.addItems(["Stacked", "Side-by-side"])
                self.arrangement.setCurrentIndex(1)
                root.addWidget(self.arrangement)
                self.input_mode = gui.QComboBox()
                self.input_mode.addItems(
                    [
                        "Characters",
                        "Named tokens: /glyphname (one following space is syntax)",
                    ]
                )
                root.addWidget(self.input_mode)
                root.addWidget(
                    gui.QLabel(
                        "Or select a preset; double-click runs that preset immediately:"
                    )
                )
                self.preset_list = gui.QListWidget()
                root.addWidget(self.preset_list)
                self.path_edit = gui.QLineEdit(
                    str(presets_directory(directory) / PRESET_FILE)
                )
                root.addWidget(self.path_edit)
                self.status = gui.QLabel("")
                self.status.setWordWrap(True)
                root.addWidget(self.status)
                self.preview = gui.QPlainTextEdit()
                self.preview.setReadOnly(True)
                root.addWidget(self.preview)
                actions = gui.QHBoxLayout()
                root.addLayout(actions)
                for attr, text in (
                    ("load_button", "Load presets"),
                    ("run_button", "List as Masters"),
                    ("close_button", "Close"),
                ):
                    check()
                    control = gui.QPushButton(text)
                    setattr(self, attr, control)
                    actions.addWidget(control)
                if settings is None:
                    self.settings = core.QSettings(
                        "FontLabScriptmix", "MasterTextComparison"
                    )
                    self.settings.setFallbacksEnabled(False)
                custom, layout, geometry, settings_error = "", 1, None, ""
                try:
                    custom, layout, geometry = load(self.settings, check=check)
                except Exception as error:
                    settings_error = str(error)
                self.words_edit.setPlainText(custom)
                try:
                    if custom_text(self.words_edit, check) != custom:
                        raise ValueError(
                            "Saved custom text cannot roundtrip exactly through this native editor; edit it or use a UTF-8 preset."
                        )
                except Exception as error:
                    self.custom_held = True
                    settings_error = str(error)
                self.arrangement.setCurrentIndex(layout)
                if geometry is not None and not self.restoreGeometry(geometry):
                    settings_error = (
                        "Saved window geometry is invalid; default size retained."
                    )
                loaded = load_presets(presets_directory(directory), check=check)
                self.replace_presets(loaded.lines, check)
                for signal, callback in (
                    (self.words_edit.textChanged, lambda *a: self.custom_changed()),
                    (self.preset_list.currentRowChanged, self.selection),
                    (
                        self.preset_list.itemDoubleClicked,
                        lambda item: self.execute(self.preset_list.row(item)),
                    ),
                    (self.load_button.clicked, lambda *a: self.load_file()),
                    (self.run_button.clicked, lambda *a: self.execute()),
                ):
                    check()
                    self.connect_owned(signal, callback)
                # Retry-capable Close drains last, after every other owned signal.
                self.connect_owned(
                    self.close_button.clicked,
                    lambda *a: self.close(),
                    closing=True,
                    retry=True,
                )
                self.refresh()
                self.status.setText(
                    settings_error
                    or loaded.notice + " Select a preset or enter custom text."
                )
                check()
            except BaseException as error:
                try:
                    self.recover_owned(opening_deadline)
                except BaseException as cleanup_error:
                    failure = BaseExceptionGroup(
                        "Comparison construction and cleanup failed.",
                        [error, cleanup_error],
                    )
                    retain(self, failure)
                    raise failure
                raise

        def failure(self, error: Exception) -> None:
            self.last_failure = error
            self.last_error = str(error)
            label = getattr(self, "status", None)
            if label is not None and not getattr(
                self, "_comparison_native_destroyed", False
            ):
                label.setText(self.last_error)

        def connect_owned(
            self, signal: Any, callback: Callable, **options: Any
        ) -> None:
            """One signal per shared Scope permits per-disconnection checkpoints."""
            scope = Scope(self.failure)
            scope.connect(signal, callback, **options)
            self.scopes.append(scope)

        def replace_presets(self, lines: tuple[str, ...], check: Callable) -> None:
            """Replace only the preset UI after the full file has been staged."""
            check()
            self.preset_list.clear()
            self.presets, self.selected = lines, -1
            for line in lines:
                check()
                # String-created items can leave stale PySide wrappers after owner deletion.
                self.preset_list.addItem(gui.QListWidgetItem(line))
            self.preset_list.setCurrentRow(-1)
            check()

        def selection(self, row: int) -> None:
            if not self.closed and not self.busy:
                self.selected = row
                self.refresh()

        def refresh(self) -> None:
            """No selection plus blank custom is a useful disabled Run state."""
            if not self.closed:
                self.run_button.setEnabled(
                    not self.busy
                    and (
                        value(self.words_edit.document(), "characterCount") > 1
                        or self.selected >= 0
                    )
                )

        def custom_changed(self) -> None:
            self.custom_held = False
            self.refresh()

        def load_file(self) -> None:
            if self.closed or self.busy:
                return
            limit = monotonic() + 3.0
            check = lambda: checkpoint(limit, monotonic, lambda: self.closed)
            try:
                lines = read_presets(str(value(self.path_edit, "text")), check=check)
                self.replace_presets(lines, check)
                self.status.setText(
                    f"{len(lines)} presets loaded; UTF-8 BOM and newlines normalized."
                )
                self.refresh()
            except Exception as error:
                self.failure(error)

        def execute(self, immediate: int | None = None) -> None:
            """Preview complete sanitation, deliver the proof, then save controls."""
            if self.closed or self.busy:
                return
            self.busy = True
            self.comparison_result = None
            self.preview.clear()
            self.run_button.setEnabled(False)
            deadline = monotonic() + 3.0
            check = lambda: checkpoint(deadline - 0.5, monotonic, lambda: self.closed)
            try:
                custom = None
                if immediate is not None:
                    text = select_text(
                        "", self.presets, self.selected, immediate=immediate
                    )
                else:
                    if self.custom_held:
                        raise ValueError(
                            "Saved custom text could not roundtrip exactly; edit it or use exact UTF-8 presets."
                        )
                    custom = custom_text(self.words_edit, check)
                    text = select_text(custom, self.presets, self.selected)
                layout = int(value(self.arrangement, "currentIndex"))
                cmap, names, aliases = self.opening.maps(check)
                try:
                    result = analyze(
                        text,
                        cmap,
                        names,
                        self.opening.masters,
                        layout,
                        mode="names"
                        if value(self.input_mode, "currentIndex") == 1
                        else "characters",
                        check=check,
                    )
                except NoUsableGlyphs as error:
                    self.show_preview(error.comparison, aliases, check)
                    raise
                self.show_preview(result, aliases, check)
                self.run(
                    self.opening,
                    result,
                    deadline=deadline,
                    cancelled=lambda: self.closed,
                )
                check()
                self.custom_save_hold = None
                if immediate is not None:
                    try:
                        if self.custom_held:
                            raise ValueError("The unrelated custom value remains held.")
                        custom = custom_text(self.words_edit, check)
                    except (TimeoutError, InterruptedError):
                        raise
                    except Exception as error:
                        self.custom_save_hold = error
                save(
                    self.settings,
                    custom,
                    layout,
                    preserve_custom=custom is None,
                    check=check,
                )
                settings_note = (
                    " Custom field and last saved custom remain unchanged; custom settings held."
                    if self.custom_save_hold is not None
                    else ""
                )
                self.status.setText(
                    f"Opened comparison; omitted {len(result.dropped)} unavailable occurrences and {len(result.empty_words)} empty words. First font-order encoded aliases used."
                    + settings_note
                )
            except Exception as error:
                self.failure(error)
            finally:
                self.busy = False
                self.refresh()

        def show_preview(self, result: Any, aliases: tuple, check: Callable) -> None:
            """Render all sanitation findings safely, even when no glyph survives."""
            self.comparison_result = result
            report = {
                "preview": result.preview,
                "dropped": [],
                "empty_words": result.empty_words,
                "aliases": aliases,
                "alias_policy": "First font-order encoded alias; Unicode assignments are alternatives",
                "native_input": "PythonQt UTF16/NUL/IME getter and delimiter rendering qualification pending",
            }
            for omission in result.dropped:
                check()
                report["dropped"].append(asdict(omission))
            check()
            rendered = json.dumps(report, ensure_ascii=True, indent=2)
            check()
            self.preview.setPlainText(rendered)
            check()

        def dispose(
            self,
            deadline: float,
            *,
            destroyed: bool = False,
            cancelled: Callable = lambda: False,
        ) -> bool:
            """Fence work; disconnect per item, retaining failed Close retries."""
            self.closed = True
            try:
                for scope in getattr(self, "scopes", ()):
                    checkpoint(deadline, monotonic, cancelled)
                    if not scope.finish(destroyed=destroyed):
                        return False
                    checkpoint(deadline, monotonic, cancelled)
            except Exception as error:
                self.failure(error)
                return False
            self.run = self.comparison_result = None
            return True

        def recover_owned(
            self, deadline: float, *, cancelled: Callable = lambda: False
        ) -> None:
            """Retire this exact owner; failed stages remain retryable and fenced."""
            check = lambda: checkpoint(deadline, monotonic, cancelled)
            check()
            destroyed = getattr(self, "_comparison_native_destroyed", False)
            if not self.dispose(deadline, destroyed=destroyed, cancelled=cancelled):
                if isinstance(self.last_failure, (TimeoutError, InterruptedError)):
                    raise self.last_failure
                raise RuntimeError(
                    "Comparison signal cleanup is incomplete."
                ) from self.last_failure
            terminal = getattr(self, "terminal", None)
            check()
            if terminal is not None and not terminal.finish(destroyed=destroyed):
                raise RuntimeError(
                    "Comparison terminal cleanup is incomplete."
                ) from self.last_failure
            check()
            if not getattr(self, "_comparison_delete_scheduled", False):
                self.deleteLater()
                self._comparison_delete_scheduled = True
                check()

        def destroyed_cleanup(self) -> None:
            deadline = monotonic() + 0.5
            self._comparison_native_destroyed = self._comparison_delete_scheduled = True
            try:
                if not self.dispose(deadline, destroyed=True):
                    raise RuntimeError(
                        "Destroyed comparison cleanup is incomplete."
                    ) from self.last_failure
                self.terminal.finish(destroyed=True)
                self._comparison_delete_scheduled = True
                release(self)
            except Exception as error:
                retain(self, error)

        def closeEvent(self, event: Any) -> None:
            deadline = monotonic() + 0.5
            check = lambda: checkpoint(deadline, monotonic, lambda: False)
            try:
                if not self.geometry_saved:
                    check()
                    geometry = self.saveGeometry()
                    check()
                    save(self.settings, geometry=geometry, check=check)
                    self.geometry_saved = True
                self.recover_owned(deadline)
                check()
                gui.QDialog.closeEvent(self, event)
                check()
                release(self)
            except Exception as error:
                retain(self, error)
                self.failure(error)
                event.ignore()

    return ComparisonPanel
