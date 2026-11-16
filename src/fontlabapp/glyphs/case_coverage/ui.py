# this_file: src/fontlabapp/glyphs/case_coverage/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned native-theme nonmodal Case Coverage controls with exact signal lifetime."""

import sys
from collections.abc import Callable
from typing import Any
from time import monotonic

from fontlabapp.glyphs.case_coverage.model import Options, checkpoint
from fontlabapp.glyphs.case_coverage.settings import load, save
from fontlabapp.glyphs.case_coverage.targets import (
    Target,
    TargetChoiceRequired,
    ProofFailure,
)
from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.properties import value

LABELS = {
    "excludeMathSymbols": "Exclude math symbols (∆∏∑µ)",
    "allFonts": "Check all open fonts (otherwise frontmost only)",
    "reuseTab": "Reuse current tab",
    "showMacroWindow": "Open detailed report window",
}


def panel_type(core: Any, gui: Any) -> type:
    """Bind lazily to FontLab's PythonQt; standalone Qt is a test surface only."""

    class CaseCoverage(gui.QDialog):
        def __init__(
            self,
            parent: Any,
            run_report: Callable,
            available: Callable,
            show_details: Callable,
            *,
            settings: Any = None,
        ) -> None:
            """Construct the four original controls and own only our signal pairs."""
            gui.QDialog.__init__(self, parent)
            self.closed = self.busy = False
            self.run_report, self.available, self.show_details = (
                run_report,
                available,
                show_details,
            )
            self.scope, self.terminal = Scope(self.failure), Scope(self.failure)
            self.controls, self.status, self.report_result = {}, None, None
            self.last_error = ""
            self.target_controls = []
            self.target_widgets = []
            self.settings = settings
            try:
                self.terminal.connect(
                    self.destroyed, lambda *args: self.dispose(True), closing=True
                )
                self.setWindowTitle("Case Coverage")
                if settings is None:
                    self.settings = core.QSettings("FontLab", "ScriptCaseCoverage")
                    self.settings.setFallbacksEnabled(False)
                layout = gui.QVBoxLayout(self)
                self.owned_layout = layout
                layout.addWidget(gui.QLabel("Report all casefolding issues:"))
                defaults = Options()
                settings_error = ""
                try:
                    defaults = load(self.settings)
                except Exception as error:
                    settings_error = str(error)
                for key, label in LABELS.items():
                    control = gui.QCheckBox(label)
                    control.setChecked(getattr(defaults, key))
                    layout.addWidget(control)
                    self.controls[key] = control
                    self.scope.connect(control.toggled, lambda *args: self.changed())
                self.status = gui.QLabel("")
                self.status.setWordWrap(True)
                layout.addWidget(self.status)
                for attr, text, callback in (
                    ("report_button", "Report", self.execute),
                    ("refresh_button", "Refresh font availability", self.refresh),
                    ("details_button", "Show detailed report", self.details),
                    ("close_button", "Close", lambda: self.close()),
                ):
                    button = gui.QPushButton(text)
                    setattr(self, attr, button)
                    layout.addWidget(button)
                    self.scope.connect(
                        button.clicked,
                        lambda *args, call=callback: call(),
                        closing=attr == "close_button",
                        retry=attr == "close_button",
                    )
                self.details_button.setEnabled(False)
                self.refresh()
                if settings_error:
                    self.failure(ValueError(settings_error))
            except BaseException:
                if self.dispose():
                    self.deleteLater()
                else:
                    sys.__dict__.setdefault("_fontlab_samples", {})["case_coverage"] = (
                        self
                    )
                    self.show()
                raise

        def failure(self, error: Exception) -> None:
            """Keep callback failures on this owned panel, never the Output pane."""
            self.last_error = str(error)
            if not self.closed and self.status is not None:
                self.status.setText(self.last_error)

        def configuration(self) -> Options:
            """Read all four original controls as one immutable typed option value."""
            return Options(
                **{
                    key: bool(value(control, "isChecked"))
                    for key, control in self.controls.items()
                }
            )

        def changed(self) -> None:
            """Save exactly four controls after user input; fence late callbacks."""
            if self.closed or self.busy:
                return
            save(self.settings, self.configuration())

        def refresh(self) -> None:
            """Enable Report only when a source font is currently available."""
            if self.closed or self.busy:
                return
            try:
                enabled = bool(self.available())
                self.report_button.setEnabled(enabled)
                self.status.setText(
                    "Ready to report." if enabled else "Open a font, then refresh."
                )
            except Exception as error:
                self.report_button.setEnabled(False)
                self.failure(error)

        def execute(self) -> None:
            """Capture afresh and publish complete diagnostics or explicit view choices."""
            if self.closed or self.busy:
                return
            self.busy = True
            self.report_result = None
            self.details_button.setEnabled(False)
            self.report_button.setEnabled(False)
            options: Options | None = None
            try:
                options = self.configuration()
                save(self.settings, options)
                result = self.run_report(
                    options, lambda: self.closed, self.target_choices()
                )
                if self.closed:
                    return
                limit = monotonic() + 3.0
                clear = result.clear(
                    lambda: checkpoint(limit, monotonic, lambda: self.closed)
                )
                self.report_result = result
                self.details_button.setEnabled(True)
                self.status.setText(
                    "No issues found. Case coverage is clear."
                    if clear
                    else "Case Coverage findings are ready. Inspect the proof and detailed report."
                )
            except TargetChoiceRequired as error:
                self.report_result = error.snapshot
                self.details_button.setEnabled(self.report_result is not None)
                self.offer_targets(error.targets)
                self.failure(error)
            except ProofFailure as error:
                self.report_result = error.snapshot
                self.details_button.setEnabled(True)
                self.failure(error)
            except Exception as error:
                self.failure(error)
            finally:
                if (
                    not self.closed
                    and self.report_result is not None
                    and options is not None
                    and options.showMacroWindow
                ):
                    try:
                        self.show_details(self.report_result)
                    except Exception as error:
                        self.failure(error)
                self.busy = False
                if not self.closed:
                    self.report_button.setEnabled(True)

        def target_choices(self) -> dict[int, tuple[int, int]]:
            """Read explicit view identities without relying on QVariant conversions."""
            limit = monotonic() + 3.0
            check = lambda: checkpoint(limit, monotonic, lambda: self.closed)
            choices = {}
            for identity, targets, combo in self.target_controls:
                check()
                index = value(combo, "currentIndex")
                if index > 0:
                    target = targets[index - 1]
                    choices[identity] = (target.canvas_id, target.block_id)
            check()
            return choices

        def offer_targets(self, targets: dict[int, tuple[Target, ...]]) -> None:
            """Offer every ambiguous inactive view through nonmodal choices."""
            limit = monotonic() + 3.0
            check = lambda: checkpoint(limit, monotonic, lambda: self.closed)
            staged = []
            for identity, choices in targets.items():
                check()
                labels = ["Choose a proof view…"]
                for target in choices:
                    check()
                    labels.append(target.label)
                staged.append((identity, choices, labels))
            while self.target_widgets:
                check()
                widget = self.target_widgets[-1]
                self.owned_layout.removeWidget(widget)
                widget.deleteLater()
                self.target_widgets.pop()
                self.target_controls.pop()
            for identity, choices, labels in staged:
                check()
                combo = gui.QComboBox()
                self.target_widgets.append(combo)
                self.target_controls.append((identity, choices, combo))
                self.owned_layout.addWidget(combo)
                combo.addItems(labels)
                check()

        def details(self) -> None:
            """Show the retained full detached report whenever the user requests it."""
            if not self.closed and self.report_result is not None:
                self.show_details(self.report_result)

        def dispose(self, destroyed: bool = False) -> bool:
            """Fence work, release facts and disconnect only owned slots before deletion."""
            self.closed = True
            self.run_report = self.available = self.show_details = None
            self.report_result = self.settings = None
            if not self.scope.finish(destroyed=destroyed):
                return False
            if destroyed:
                self.terminal.finish(destroyed=True)
            return True

        def closeEvent(self, event: Any) -> None:
            """Refuse deletion on failed disconnect so Close can retry safely."""
            if not self.dispose():
                event.ignore()
                if self.status is not None:
                    self.status.setText(
                        self.last_error + "; Close again to retry signal cleanup."
                    )
                return
            gui.QDialog.closeEvent(self, event)
            self.deleteLater()

    return CaseCoverage
