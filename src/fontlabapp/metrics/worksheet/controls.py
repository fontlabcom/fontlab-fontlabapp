# this_file: src/fontlabapp/metrics/worksheet/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Build the original four-by-two numeric table and the local spacing report."""

from typing import Any

from fontlabapp.metrics.worksheet.data import defaults
from fontlabapp.qt.spinbox.delegate import delegate_type


def model(core: Any, gui: Any, parent: Any, official: bool) -> Any:
    """Stage every item before exposing the complete native model to its view."""
    result = gui.QStandardItemModel(4, 2, parent)
    try:
        for row, pair in enumerate(defaults(official)):
            for column, number in enumerate(pair):
                if official:
                    if (
                        result.setData(
                            result.index(row, column), number, core.Qt.EditRole
                        )
                        is False
                    ):
                        raise RuntimeError("Qt refused a default worksheet integer.")
                else:
                    result.setItem(row, column, gui.QStandardItem(number))
        if not official:
            result.setHorizontalHeaderLabels(["Factor A", "Factor B"])
        return result
    except Exception:
        result.deleteLater()
        raise


def build(owner: Any, core: Any, gui: Any) -> None:
    """Make Close and diagnostics before optional capture; retain native defaults."""
    owner.setAttribute(core.Qt.WA_QuitOnClose, False)
    owner.setWindowTitle(
        "Glyph Spacing Worksheet — "
        + ("Spin Box Delegate" if owner.official else "Numeric cell delegate")
    )
    owner.layout_root = gui.QVBoxLayout(owner)
    label = gui.QLabel(
        "A is a font-unit increment. B is its repeat count. Each row gives A × B. Candidates do not change font metrics.",
        owner,
    )
    label.setWordWrap(True)
    owner.layout_root.addWidget(label)
    owner.table = gui.QTableView(owner)
    owner.layout_root.addWidget(owner.table)
    owner.report = gui.QPlainTextEdit(owner)
    owner.report.setReadOnly(True)
    owner.layout_root.addWidget(owner.report, 1)
    owner.status = gui.QLabel("Local worksheet ready.", owner)
    owner.status.setWordWrap(True)
    owner.layout_root.addWidget(owner.status)
    row = gui.QHBoxLayout()
    owner.layout_root.addLayout(row)
    for name, caption, call in (
        ("refresh_button", "Refresh Selection", owner.refresh),
        ("reset_button", "Reset Factors", owner.reset),
        ("close_button", "Close", owner.close),
    ):
        button = gui.QPushButton(caption, owner)
        setattr(owner, name, button)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setFocusPolicy(core.Qt.NoFocus)
        row.addWidget(button)
        owner.scope.connect(
            button.clicked,
            lambda *args, action=call: action(),
            closing=name == "close_button",
            retry=name == "close_button",
        )
    owner.model = model(core, gui, owner, owner.official)
    owner.delegate = delegate_type(core, gui)(
        owner.model, owner.table, owner.official, owner.failure, owner.changed
    )
    owner.table.setModel(owner.model)
    owner.table.setItemDelegate(owner.delegate)
    owner.scope.connect(owner.model.dataChanged, lambda *args: owner.changed())
    if not owner.official:
        owner.resize(640, 460)
