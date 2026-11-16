# this_file: src/fontlabapp/proof/numeric/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Build both distinct original spinbox profiles through injected Qt5 classes.

Use actual native editors for correction, keyboard input, stepping and format
sections. Preserve original ranges, defaults, precision and special-value text.
"""

from typing import Any

FORMATS = {
    2: ("yyyy-MM-dd hh:mm", "dd MMM yyyy", "hh:mm AP"),
    3: (
        "yyyy-MM-dd hh:mm:ss (zzz 'ms')",
        "hh:mm:ss MM/dd/yyyy",
        "hh:mm:ss dd/MM/yyyy",
        "hh:mm:ss",
        "hh:mm ap",
    ),
}


def build(owner: Any, core: Any, gui: Any) -> None:
    """Create every original editor, plus captured results/Refresh/Close."""
    owner.setWindowTitle(
        "Glyph Metrics and Revisions" + (" — Detailed" if owner.part == 3 else "")
    )
    owner.setAttribute(core.Qt.WA_QuitOnClose, False)
    owner.resize(980, 690)
    layout = gui.QVBoxLayout(owner)
    caption = gui.QLabel(
        "Compare captured selected-layer advances and whole-font revisions. Local worksheet only.",
        owner,
    )
    caption.setWordWrap(True)
    layout.addWidget(caption)
    columns = gui.QHBoxLayout()
    layout.addLayout(columns)
    groups = []
    for title in ("Integer proof recipe", "Revision cutoffs", "Decimal proof recipe"):
        box = gui.QGroupBox(title, owner)
        form = gui.QFormLayout(box)
        columns.addWidget(box)
        groups.append(form)
    owner.controls = {}
    official = owner.part == 3
    specs = (
        ("integer", "Advance offset (units)", False, -20, 20, 1, 0, "", "", "", 0),
        (
            "zoom",
            "12pt proof zoom",
            False,
            0,
            1000,
            10 if official else 1,
            100,
            "",
            "%",
            "Automatic" if official else "",
            0,
        ),
        (
            "currency",
            "Proof cost per glyph",
            False,
            0,
            999,
            1,
            99 if official else 25,
            "$",
            "",
            "",
            0,
        ),
        (
            "decimal",
            "Advance offset (units)",
            True,
            -20 if official else -1000,
            20 if official else 1000,
            1,
            0 if official else 12.34,
            "",
            "",
            "",
            2,
        ),
        (
            "percent",
            "Candidate advance scale",
            True,
            0 if official else -1000,
            1000,
            10 if official else 1,
            100 if official else 12.34,
            "",
            "%",
            "No scaling" if official else "",
            2,
        ),
        (
            "money",
            "Proof quote per glyph",
            True,
            0 if official else -1000,
            1000,
            1,
            99.99 if official else 12.34,
            "$",
            "",
            "",
            2,
        ),
    )
    for (
        key,
        label,
        decimal,
        lo,
        hi,
        step,
        initial,
        prefix,
        suffix,
        special,
        column,
    ) in specs:
        widget = (gui.QDoubleSpinBox if decimal else gui.QSpinBox)(owner)
        widget.setRange(lo, hi)
        widget.setSingleStep(step)
        widget.setPrefix(prefix)
        widget.setSuffix(suffix)
        widget.setSpecialValueText(special)
        widget.setValue(initial)
        owner.controls[key] = widget
        groups[column].addRow(label, widget)
        signal = widget.valueChanged
        owner.scope.connect(signal, lambda *args: owner.changed())
    precision = gui.QSpinBox(owner)
    precision.setRange(0, 100)
    precision.setValue(2)
    owner.controls["precision"] = precision
    groups[2].insertRow(0, "Decimal places", precision)
    owner.scope.connect(precision.valueChanged, owner.precision)
    for key, kind, label in (
        ("date", gui.QDateEdit, "Modified on/before date"),
        ("time", gui.QTimeEdit, "Modified at/before time"),
        ("meeting", gui.QDateTimeEdit, "Modified before instant"),
    ):
        widget = kind(owner)
        if official and key == "time":
            # QTimeEdit(QTime) keeps the original hidden date2000-01-01.
            widget.setTime(core.QTime.currentTime())
        else:
            widget.setDateTime(core.QDateTime.currentDateTime())
        owner.controls[key] = widget
        groups[1].addRow(label, widget)
        owner.scope.connect(widget.dateTimeChanged, lambda *args: owner.changed())
    if official:
        owner.controls["date"].setDateRange(
            core.QDate(2005, 1, 1), core.QDate(2010, 12, 31)
        )
        owner.controls["time"].setTimeRange(core.QTime(9, 0), core.QTime(16, 30))
    else:
        owner.controls["meeting"].setDateTimeRange(
            core.QDateTime(core.QDate(2020, 1, 1), core.QTime(0, 0)),
            core.QDateTime(core.QDate(2040, 12, 31), core.QTime(0, 0)),
        )
    formats = gui.QComboBox(owner)
    formats.addItems(list(FORMATS[owner.part]))
    owner.controls["format"] = formats
    groups[1].addRow("Instant format", formats)
    owner.meeting_label = gui.QLabel(owner)
    owner.meeting_label.setWordWrap(True)
    groups[1].addRow(owner.meeting_label)
    owner.scope.connect(
        formats.activated if official else formats.currentIndexChanged,
        owner.format_changed,
    )
    owner.output = gui.QPlainTextEdit(owner)
    owner.output.setReadOnly(True)
    layout.addWidget(owner.output, 1)
    owner.status = gui.QLabel(owner)
    owner.status.setWordWrap(True)
    layout.addWidget(owner.status)
    buttons = gui.QHBoxLayout()
    owner.refresh_button, owner.close_button = (
        gui.QPushButton("Refresh Font and Selection", owner),
        gui.QPushButton("Close", owner),
    )
    buttons.addWidget(owner.refresh_button)
    buttons.addStretch(1)
    buttons.addWidget(owner.close_button)
    layout.addLayout(buttons)
    owner.scope.connect(owner.refresh_button.clicked, lambda *args: owner.refresh())
    owner.scope.connect(
        owner.close_button.clicked,
        lambda *args: owner.close(),
        closing=True,
        retry=True,
    )
    if official:
        owner.format_changed(0)
    else:
        owner.meeting_label.setText("Instant date range: 2020-01-01 to 2040-12-31.")
