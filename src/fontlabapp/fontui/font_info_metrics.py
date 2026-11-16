# this_file: src/fontlabapp/fontui/font_info_metrics.py
# SPDX-License-Identifier: Apache-2.0
"""Staged font information and a vertical report for the same borrowed font."""
from datetime import datetime
from typing import Any

_HANDLES = []
_FIELDS = (
    'openTypeOS2TypoAscender', 'openTypeOS2TypoDescender', 'openTypeOS2TypoLineGap',
    'openTypeHheaAscender', 'openTypeHheaDescender', 'openTypeHheaLineGap',
    'openTypeOS2WinDescent', 'openTypeOS2WinAscent',
)


def _panel_type():
    from PythonQt import QtGui

    from fontlabapp.metrics.vertical.model import (
        KEYS,
        MasterMetrics,
        MetricsReport,
        render,
    )

    from .fontinfo import FontInfoEditor

    class FontInfoMetrics(FontInfoEditor):
        """Use the editor's staged Apply and Owned lifetime without a second owner."""
        def __init__(self, font, parent):
            self.report = self.report_view = None
            super().__init__(font, parent, lambda *_: self.refresh_report())
            self.widget.setWindowTitle('Font Info and Vertical Metrics')
            self.report_view = QtGui.QPlainTextEdit(self.widget)
            self.report_view.setReadOnly(True)
            self.report_view.setAccessibleName('Vertical metrics report')
            self.layout.addWidget(self.report_view)
            self.refresh_report_button = QtGui.QPushButton('Refresh metrics report', self.widget)
            self.layout.addWidget(self.refresh_report_button)
            self.connect(self.refresh_report_button.clicked, lambda *_: self.refresh_report())
            self.refresh_report()

        def refresh(self):
            """Reload the editor fields, then the report, after any FontLab change."""
            ok = super().refresh()
            if self.report_view is not None:
                self.refresh_report()
            return ok

        def refresh_report(self):
            """Read stored info only; preserve the editor's unfinished draft."""
            if self.closed:
                return False
            self.report = None
            try:
                info = self._info()
                values = tuple(getattr(info, name) for name in _FIELDS)
                row = MasterMetrics(id(self.font), str(info.familyName or 'Untitled'),
                                    str(info.styleName or 'Current info source'), values)
                report = MetricsReport((row,), datetime.now().isoformat(timespec='seconds'))
                text = ('Captured font / current info source only; not an all-master comparison.\n'
                        + '\n'.join(f'{key}: {value}' for key, value in zip(KEYS, values))
                        + '\n' + render(report))
                self.report_view.setPlainText(text)
                self.report = report
                return True
            except Exception as error:  # noqa: BLE001 - borrowed model / Qt callback boundary
                self.report_view.setPlainText(str(error))
                return False

        def close(self):
            super().close()
            if self in _HANDLES:
                _HANDLES.remove(self)

    return FontInfoMetrics


def show(font: Any, parent: Any = None) -> Any:
    """Show one captured font; Apply uses the existing guarded Fontport editor."""
    from . import _construct
    owner = _construct(_panel_type(), font, parent)
    _HANDLES.append(owner)
    try:
        owner.widget.show()
    except BaseException:
        owner.close()
        raise
    return owner
