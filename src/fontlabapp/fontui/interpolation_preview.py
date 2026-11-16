# this_file: src/fontlabapp/fontui/interpolation_preview.py
# SPDX-License-Identifier: Apache-2.0
"""Designspace controls linked to the existing two-master read-only preview."""

import math
from typing import Any

__all__ = ["show"]
_HANDLES = []


def _fraction(designspace: Any, first: Any, second: Any, location: Any) -> float:
    """Require a point on the chosen source segment, in mapped design coordinates."""
    values = dict(location.coordinates)
    a, b = dict(first.coordinates), dict(second.coordinates)
    factors = []
    for axis in designspace.axes:
        start, end, value = (axis.map_forward(v[axis.name]) for v in (a, b, values))
        if start == end:
            if not math.isclose(value, start, abs_tol=1e-8):
                raise ValueError("Location is outside the chosen two-master segment")
        else:
            factors.append((value - start) / (end - start))
    if not factors:
        raise ValueError("Choose two sources with distinct locations")
    factor = factors[0]
    if not 0 <= factor <= 1 or any(not math.isclose(factor, v, abs_tol=1e-8) for v in factors):
        raise ValueError("Location is outside the chosen two-master segment")
    return factor


def _panel_type() -> type:
    from PythonQt import QtCore, QtGui

    from fontlabapp.masters.interpolation.model import blend, outline, problem
    from fontlabapp.masters.interpolation.view import BlendView

    from . import designspace_panel
    from .lifecycle import Owned
    from .sequence import Designspace, NativeFontBackend, RFont

    class InterpolationPreview(Owned):
        def __init__(self, font: Any, parent: Any) -> None:
            self.controls = None
            self.font = font
            self.backend = self.package_id = None
            self._reading = False
            super().__init__(parent)
            self.widget.setWindowFlags(QtCore.Qt.Window)
            self.widget.setWindowTitle("Interpolation Preview")
            note = QtGui.QLabel(
                "Read-only two-master linear preview; choose a glyph and endpoints. "
                "Axis values must lie on their segment. This is not a full variable-font "
                "interpolator. Reads stored native outlines, never unfinished wrapper edits.", self.widget)
            note.setWordWrap(True)
            self.layout.addWidget(note)
            self.status = QtGui.QLabel("", self.widget)
            self.status.setWordWrap(True)
            self.layout.addWidget(self.status)
            row = QtGui.QHBoxLayout()
            self.layout.addLayout(row)
            self.glyph = QtGui.QLineEdit(self.widget)
            self.glyph.setAccessibleName("Glyph name")
            self.glyph.setPlaceholderText("Glyph name")
            self.first, self.second = QtGui.QComboBox(self.widget), QtGui.QComboBox(self.widget)
            self.first.setAccessibleName("First source master")
            self.second.setAccessibleName("Second source master")
            self.refresh_button = QtGui.QPushButton("Refresh preview", self.widget)
            for item in (self.glyph, self.first, self.second, self.refresh_button):
                row.addWidget(item)
            self.view = BlendView(self.widget)
            self.layout.addWidget(self.view)
            self.close_button = QtGui.QPushButton("Close", self.widget)
            self.layout.addWidget(self.close_button)
            self.connect(self.close_button.clicked, lambda *args: self.widget.close())
            try:
                if not isinstance(font, RFont) or not isinstance(font._backend, NativeFontBackend):
                    raise TypeError("An open registered FontLab font is required")
                self.backend = font._backend
                self.package_id = self._package().id
                self.designspace = Designspace.from_native(self.backend)
                self.sources = self.designspace.sources
                if len(self.sources) < 2:
                    raise ValueError("At least two source masters are required")
                names = [source.name for source in self.sources]
                if len(set(names)) != len(names):
                    raise ValueError("Source master names must be unique")
                for box in (self.first, self.second):
                    box.addItems(names)
                self.second.setCurrentIndex(len(names) - 1)
                try:
                    self.controls = designspace_panel(self.designspace, self.widget)
                except BaseException as error:
                    self.controls = getattr(error, "owner", None)
                    raise
                self.layout.addWidget(self.controls.widget)
                self.controls.on_location = lambda location: self.refresh()
                for signal in (self.first.currentIndexChanged, self.second.currentIndexChanged,
                               self.glyph.editingFinished, self.refresh_button.clicked):
                    self.connect(signal, lambda *args: self.refresh())
                self.refresh()
            except Exception as error:
                if self.controls is not None:
                    raise
                self.status.setText(str(error))

        def _package(self) -> Any:
            if self.closed or self.font._backend is not self.backend:
                raise ValueError("The borrowed font is closed or its backend changed")
            self.font._check()
            package = self.backend._package()
            if package.fgId != self.backend.font_id or (self.package_id is not None and package.id != self.package_id):
                raise ValueError("The registered font identity changed")
            return package

        def refresh(self) -> None:
            if self.closed or self._reading:
                return
            self._reading = True
            self.view.a, self.view.b, self.view.mix = [], [], []
            try:
                package = self._package()
                current = Designspace.from_native(self.backend)
                if current.document.tostring() != self.designspace.document.tostring():
                    raise ValueError("Designspace changed; reopen this preview")
                name = self.glyph.text.strip()
                if not name:
                    raise ValueError("Enter a glyph name")
                first, second = (self.sources[box.currentIndex] for box in (self.first, self.second))
                factor = _fraction(self.designspace, first, second, self.controls.current)
                glyph = package.findName(name)
                if glyph is None or glyph.isNull or glyph.name != name or glyph.package.id != package.id:
                    raise ValueError("Glyph is missing or belongs to another font")
                values = []
                for source in (first, second):
                    layer = glyph.findLayer(source.name)
                    if (layer is None or layer.isNull or not layer.isValid
                            or layer.isMasterLayer is not True or layer.isMaskLayer is not False
                            or layer.isService is not False or layer.name != source.name
                            or layer.glyph.id != glyph.id):
                        raise ValueError(f"Missing master layer: {source.name}")
                    values.append(outline(layer))
                a, b = values
                why = problem(a, b)
                if why:
                    raise ValueError(f"Not compatible: {why}")
                if any(not math.isfinite(v) for shape in (a, b) for contour in shape for x, y, _ in contour for v in (x, y)):
                    raise ValueError("Outline coordinates must be finite")
                self._package()
                if self.closed:
                    return
                self.view.a, self.view.b, self.view.mix = a, b, blend(a, b, factor)
                self.status.setText(f"{name}: {first.name} → {second.name}, {factor:.1%}; nothing written")
            except Exception as error:  # noqa: BLE001 - native reads and signal boundary
                if not self.closed:
                    self.status.setText(str(error))
            finally:
                self._reading = False
                if not self.closed:
                    self.view.update()

        def close(self) -> None:
            if self.controls is not None:
                self.controls.on_location = None
            self._close_with_child(self.controls)
            self.font = self.backend = None
            if self in _HANDLES:
                _HANDLES.remove(self)

    return InterpolationPreview


def show(font: Any, parent: Any = None) -> Any:
    """Show an owned preview of an explicit borrowed font without any font writes."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window

    from . import _construct

    host = parent if parent is not None else main_window(_native("fontlab"), _native("PythonQt"))
    owner = _construct(_panel_type(), font, host)
    _HANDLES.append(owner)
    try:
        owner.widget.resize(760, 700)
        owner.widget.show()
    except BaseException:
        owner.close()
        raise
    return owner
