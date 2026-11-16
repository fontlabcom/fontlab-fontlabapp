# this_file: src/fontlabapp/studios/vertical_metrics/calculate.py
# SPDX-License-Identifier: Apache-2.0
"""Calculate tab: Calculate Vertical Metrics (Font Info) and Vertical Metrics Reporter (Reports).

Calculate: Refresh measures the bounds of every nonempty glyph in every
master (``scan_bounds``, the original 2.5 s interactive deadline) and the
dry run lists, per master in scope, the font-info fields that would enclose
every glyph, rounded outward (``enclosing_metrics``): padding 0–2000 and line
gap 0–32767 (both default 0); the hhea and Win groups are ticked, the OS/2
Typo group (= FontLab's own ascender, descender and line gap) is optional
and off, as in the original. "Set metrics" writes exactly the listed plan
through the original writer ``core.scripting.write_font_info`` (it refuses a
value that changed since the preview) as one
``Vertical Metrics: calculate metrics of <masters>`` Undo step. Bounds are
captured on Refresh; press Refresh after outline edits.

The glyph list keeps the original ``glyph_records`` read (legacy
``FL.fl.font`` order and ``fgGlyph.unicodes``); moving it to the shared
``studios._records`` catalogue waits for the native check (Scriptmix
TODO:48, T10 ruling, T29) and is disclosed in the task report.

Reporter: "Compare open fonts" reads eight stored metrics of every master in
every open font (``metrics.vertical.native.capture``) and shows the original
text report (``metrics.vertical.model.render``). It only reads.
"""

import math
import time
from typing import Any

from PythonQt import QtGui

from fontlabapp.core.scripting import current_package, write_font_info

from .._kerning import ERRORS, Tool
from .._kerning_ui import Panel, button, check, combo, get, label, row, spin
from . import _shared
from ._shared import MasterTable, ap

REPORTER_NOTE = ("Compare eight stored metric values across every master in every open font. Unset hhea values "
                 "remain None. Exported or automatically derived values are outside this report.")  # fmt: skip
STATUS = ("Typo/hhea descenders are negative; Win descent is positive. Empty masters skipped. "
          "Bounds captured on Refresh; press Refresh after outline edits.")  # fmt: skip


def glyph_records(package: Any) -> Any:
    """Read all Unicode assignments, including secondary encodings, in font order."""
    FL = ap.FL

    active = current_package()
    if active is None or active.id != package.id:
        msg = "Activate the original font and reopen this tool."
        raise ValueError(msg)
    legacy = FL.fl.font
    return [
        (legacy[i].name, list(package.findName(legacy[i].name).fgGlyph.unicodes))
        for i in range(len(legacy))
    ]


METRIC_FIELDS = [
    "openTypeOS2TypoAscender",
    "openTypeOS2TypoDescender",
    "openTypeOS2TypoLineGap",
    "openTypeHheaAscender",
    "openTypeHheaDescender",
    "openTypeHheaLineGap",
    "openTypeOS2WinAscent",
    "openTypeOS2WinDescent",
]
GROUPS = [  # (label, fields): FontLab's ascender/descender/line gap are the typo fields
    ("Typo (= FontLab ascender, descender, line gap)", METRIC_FIELDS[0:3]),
    ("hhea", METRIC_FIELDS[3:6]),
    ("Win", METRIC_FIELDS[6:8]),
]
LABELS = {
    "openTypeOS2TypoAscender": "Typo ascender",
    "openTypeOS2TypoDescender": "Typo descender",
    "openTypeOS2TypoLineGap": "Typo line gap",
    "openTypeHheaAscender": "hhea ascender",
    "openTypeHheaDescender": "hhea descender",
    "openTypeHheaLineGap": "hhea line gap",
    "openTypeOS2WinAscent": "Win ascent",
    "openTypeOS2WinDescent": "Win descent",
}


def number(value: Any) -> Any:
    """965.0 -> 965 for display."""
    return int(value) if isinstance(value, float) and value.is_integer() else value


def enclosing_metrics(low: float, high: float, padding: int, gap: int) -> list[float]:
    """Round bounds outward and validate OpenType metric limits."""
    if (
        not all(math.isfinite(v) for v in (low, high, padding, gap))
        or low > high
        or not 0 <= padding <= 2000
        or not 0 <= gap <= 32767
    ):
        raise ValueError("Use finite bounds, padding 0–2000 and line gap 0–32767.")
    ascent = max(0, math.ceil(high) + padding)
    descent = min(0, math.floor(low) - padding)
    if ascent > 32767 or descent < -32768:
        msg = "Bounds exceed signed 16-bit typo/hhea limits."
        raise ValueError(msg)
    return [ascent, descent, gap, ascent, descent, gap, ascent, -descent]


def scan_bounds(package: Any) -> dict[str, tuple[float, float, int]]:
    """Measure all nonempty glyph bounds with an interactive deadline."""
    records = glyph_records(package)
    result = {}
    deadline = time.monotonic() + 2.5
    for master in package.masters:
        lows, highs = [], []
        for name, _ in records:
            if time.monotonic() > deadline:
                msg = "Font too large for an interactive scan; no changes made."
                raise ValueError(
                    msg,
                )
            layer = package.findName(name).findLayer(master)
            if layer is None or layer.isNull:
                continue
            box = layer.boundingBox
            if box.width() == 0 and box.height() == 0:
                continue
            lows.append(box.y())
            highs.append(box.y() + box.height())
        if lows:
            result[master] = (min(lows), max(highs), len(lows))
    return result


def metric_plan(
    package: Any,
    bounds: Any,
    masters: Any,
    padding: Any,
    gap: Any,
    fields: Any = METRIC_FIELDS,
) -> Any:
    """Build selected master and metric edits while restoring the active master."""
    original = package.master
    changes = []
    try:
        for master in masters:
            if master not in bounds:
                continue
            package.setMaster(master)
            values = enclosing_metrics(*bounds[master][:2], padding, gap)
            changes.extend(
                (master, k, getattr(package.info, k), v)
                for k, v in zip(METRIC_FIELDS, values, strict=False)
                if k in fields
            )
    finally:
        package.setMaster(original)
    return changes


class CalculatePanel(Panel):
    """Calculate Vertical Metrics, with the Vertical Metrics Reporter below."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.subtitle.setText("Sets hhea and Win (and, if ticked, OS/2 typo) metrics to enclose every glyph, "
                              "rounded outward. Typo = FontLab's own ascender/descender lines.")  # fmt: skip
        self.scope = combo(
            self.widget,
            ["Current master", "All masters"],
            _shared.keep(self, self.show_plan),
        )
        row(self.widget, self.layout, "Scope", self.scope)
        self.padding = spin(
            self.widget, 0, 2000, 0, slot=_shared.keep(self, self.show_plan)
        )
        row(self.widget, self.layout, "Padding", self.padding)
        self.gap = spin(
            self.widget, 0, 32767, 0, slot=_shared.keep(self, self.show_plan)
        )
        row(self.widget, self.layout, "Line gap", self.gap)
        groups = QtGui.QHBoxLayout()
        self.layout.addLayout(groups)
        self.group_checks = [check(self.widget, groups, text, index > 0, _shared.keep(self, self.show_plan))
                             for index, (text, _) in enumerate(GROUPS)]  # fmt: skip
        self.grid = MasterTable(
            self.widget, self.layout, ["Master · field", "Current", "Proposed"]
        )
        self.status = label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(
            self.widget, buttons, "Set metrics", lambda: self.run(self.apply)
        )
        label(self.widget, self.layout, "Vertical Metrics Reporter")
        label(self.widget, self.layout, REPORTER_NOTE)
        self.report = QtGui.QPlainTextEdit(self.widget)
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Vertical metrics report")
        self.layout.addWidget(self.report, 1)
        self.report_status = label(self.widget, self.layout)
        button(
            self.widget,
            self.layout,
            "Compare open fonts",
            _shared.keep(self, self.compare),
        )
        self.bounds: dict[str, tuple[float, float, int]] = {}
        self.plan: list[tuple] = []

    def clear(self) -> None:
        self.bounds, self.plan = {}, []
        self.show_rows()

    def refresh(self) -> None:
        self.bounds, self.plan = {}, []
        tool = self.tool
        if tool.package is not None:
            self.scope.setItemText(0, f"Current master ({tool.current})")
            self.scope.setItemText(1, f"All masters ({len(tool.masters)})")
            self.bounds = scan_bounds(tool.package)
        self.show_plan()

    def fields(self) -> list[str]:
        return [
            f
            for box, (_, group) in zip(self.group_checks, GROUPS, strict=True)
            if box.isChecked()
            for f in group
        ]

    def masters(self) -> list[str]:
        return (
            list(self.tool.masters)
            if get(self.scope.currentIndex)
            else [self.tool.current]
        )

    def show_plan(self) -> None:
        """Build the explicit per-master plan from the controls (the original ``changes``)."""
        self.plan = []
        if self.tool.package is not None and self.bounds:
            self.plan = metric_plan(self.tool.package, self.bounds, self.masters(),
                                    get(self.padding.value), get(self.gap.value), self.fields())  # fmt: skip
        self.show_rows()

    def show_rows(self) -> None:
        self.grid.set_rows(
            [
                (m + " · " + LABELS[k], number(old), number(new))
                for m, k, old, new in self.plan
            ]
        )
        changed = [c for c in self.plan if c[2] != c[3]]
        self.apply_button.setEnabled(bool(changed))
        if self.tool.package is None:
            self.status.setText("Open a font first.")
        else:
            self.status.setText(
                f"{_shared.plural(len(changed), 'metric field')} to change · {STATUS}"
            )

    def apply(self) -> None:
        plan = list(self.plan)
        if self.tool.package is None or not any(old != new for _, _, old, new in plan):
            raise ValueError("Nothing to change.")
        if self.tool.package.master != self.tool.current:
            self.plan = []
            self.show_rows()
            raise ValueError("Master changed; refresh before applying metrics.")
        title = _shared.label("calculate metrics", [c[0] for c in plan if c[2] != c[3]])
        result = write_font_info(self.tool.package, plan, undo_name=title)
        refresh_error = ""
        try:
            self.tool.reload()
        except ERRORS as error:
            refresh_error = f" · Refresh failed: {error}"
        note = f" · {result['pending_note']}" if result.get("pending_note") else ""
        self.tool.say(f"{title}. Applied {result['changed']} metric fields{note}{refresh_error}")

    def compare(self) -> None:
        """The Vertical Metrics Reporter: one read of every open font and master."""
        reporter = _shared.backends().reporter
        self.report.setPlainText("")
        report = reporter.native.capture()
        self.report.setPlainText(reporter.model.render(report))
        self.report_status.setText(
            f"Snapshot: {report.fonts} fonts, {len(report.rows)} masters. Refresh after changes."
        )


__all__ = ["GROUPS", "LABELS", "METRIC_FIELDS", "CalculatePanel", "enclosing_metrics", "glyph_records",
           "metric_plan", "number", "scan_bounds"]  # fmt: skip
