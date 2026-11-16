# this_file: src/fontlabapp/fontui/source_comparison.py
# SPDX-License-Identifier: Apache-2.0
"""Compare stored source layers without switching masters or editing a font."""
from math import isfinite
from time import monotonic
from typing import Any

_HANDLES = []
_READ_SECONDS = 3.5


def summary(font: Any, left: str, right: str, name: str) -> str:
    """Read detached backend glyphs and use the existing structural report."""
    from fontlabapp.masters.layers.compatibility.model import GlyphLayers, Layer, render

    font._check()
    backend = font._backend
    layers, widths = [], []
    for source in (left, right):
        if source not in backend.layer_names():
            raise ValueError("Selected source layer no longer exists")
        if name not in backend.glyph_names(source):
            raise ValueError(f"{name} is missing from {source}")
        glyph = backend.read_glyph(name, source)
        width = float(glyph.width)
        if not isfinite(width):
            raise ValueError("Advance width must be finite")
        widths.append(f"{source}: advance {width:g}")
        layers.append(Layer(source,
            tuple(tuple(point.type or 'offcurve' for point in contour) for contour in glyph.contours),
            frozenset(anchor.name for anchor in glyph.anchors if anchor.name),
            frozenset(component.baseGlyph for component in glyph.components)))
    font._check()
    return '\n'.join(widths) + '\n\n' + render((GlyphLayers(name, tuple(layers)),))


def show(font: Any, parent: Any = None) -> Any:
    """Show two explicit stored layer selectors, glyph choice and structural report.

    Compare captured-font layers or explicitly open an external designspace.
    Pending wrapper edits are not read; neither mode certifies interpolation.
    """
    from PythonQt import QtGui

    from fontlabapp.fontui import _construct
    from fontlabapp.fontui.lifecycle import Owned

    class Comparison(Owned):
        def __init__(self, parent: Any) -> None:
            super().__init__(parent)
            self.font = font
            self.widget.setWindowTitle('Designspace Source Comparison')
            self.left, self.right, self.glyph = (QtGui.QComboBox(self.widget) for _ in range(3))
            self.report = QtGui.QPlainTextEdit(self.widget)
            self.report.setReadOnly(True)
            self.refresh_button = QtGui.QPushButton('Refresh comparison', self.widget)
            self.open_button = QtGui.QPushButton('Open designspace…', self.widget)
            self.status = QtGui.QLabel('', self.widget)
            self.status.setWordWrap(True)
            note = QtGui.QLabel('Compare captured-font layers, or open an external designspace. Structural compatibility checks path/node types and anchor/component name sets; it does not certify interpolation. Pending wrapper edits are excluded.', self.widget)
            note.setWordWrap(True)
            self.layout.addWidget(note)
            for control, label in ((self.left, 'Reference source layer'), (self.right, 'Comparison source layer'), (self.glyph, 'Glyph')):
                control.setAccessibleName(label)
                self.layout.addWidget(QtGui.QLabel(label, self.widget))
                self.layout.addWidget(control)
            self.layout.addWidget(self.report)
            controls = QtGui.QHBoxLayout()
            controls.addWidget(self.refresh_button)
            controls.addWidget(self.open_button)
            self.layout.addLayout(controls)
            self.layout.addWidget(self.status)
            self.connect(self.open_button.clicked, lambda *args: self.open_designspace())
            try:
                font._check()
                names = tuple(font._backend.layer_names())
                self.left.addItems(list(names))
                self.right.addItems(list(names))
                glyphs = sorted({name for layer in names for name in font._backend.glyph_names(layer)})
                self.glyph.addItems(glyphs)
                self.right.setCurrentIndex(1 if len(names) > 1 else 0)
            except Exception as error:  # noqa: BLE001 - borrowed model/Qt callback boundary
                self.report.setPlainText(str(error))
                return
            for control in (self.left, self.right, self.glyph):
                self.connect(control.currentIndexChanged, lambda *args: self.refresh())
            self.connect(self.refresh_button.clicked, lambda *args: self.refresh())
            self.refresh()

        def open_designspace(self) -> None:
            if self.closed:
                return
            try:
                path = QtGui.QFileDialog.getOpenFileName(
                    self.widget, 'Open designspace', '', 'Designspace files (*.designspace)')
                path = path[0] if isinstance(path, tuple) else path
                if self.closed or not path:
                    return
                from fontlabapp.fontui.designspace_sources import refresh

                deadline = monotonic() + _READ_SECONDS

                def check() -> None:
                    if self.closed:
                        raise InterruptedError('Designspace comparison closed')
                    # Blocking file reads cannot be preempted; check between reads.
                    if monotonic() >= deadline:
                        raise TimeoutError('Designspace read exceeded its deadline')

                def publish(text: str) -> None:
                    check()
                    self.report.setPlainText(f'External designspace: {path}\n\n{text}')
                    self.status.setText(f'External designspace: {path}')

                refresh(path, publish, check=check)
            except Exception as error:  # noqa: BLE001 - file/Qt callback boundary
                if not self.closed:
                    self.status.setText(f'Open designspace failed: {error}')

        def refresh(self) -> None:
            if self.closed:
                return
            self.report.setPlainText('')
            try:
                text = summary(self.font, self.left.currentText, self.right.currentText, self.glyph.currentText)
            except Exception as error:  # noqa: BLE001 - borrowed model/Qt callback boundary
                text = str(error)
            if not self.closed:
                self.report.setPlainText(text)
                self.status.setText('Captured-font source layers')

        def close(self) -> None:
            super().close()
            if self._close_complete:
                self.font = None
                if self in _HANDLES:
                    _HANDLES.remove(self)

    owner = _construct(Comparison, parent)
    _HANDLES.append(owner)
    try:
        owner.widget.show()
    except BaseException:
        owner.close()
        raise
    return owner
