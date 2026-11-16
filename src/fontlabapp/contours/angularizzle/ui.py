# this_file: src/fontlabapp/contours/angularizzle/ui.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Original Angularizzle controls with bound targets and owned modeless lifetime."""

import sys
from typing import Any

import fontlabapp.contours.angularizzle.settings as prefs
from fontlabapp import _native
from fontlabapp.contours.angularizzle.session import Session

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class AngularizzleDialog(QtGui.QDialog):
    """Process previews one target; Cancel restores its original paths."""

    KEY = "angularizzle"

    def __init__(
        self, parent: Any = None, *, backend: Any = None, preferences: Any = None
    ) -> None:
        super().__init__(parent)
        self._closed, self._connections, self._lifetime_connections = False, [], []
        self._backend, self.session, self._settings = backend, None, None
        self.persistence_error = ""
        self.cleanup_errors = []
        self.setWindowTitle("Angularizzle Yo")
        self.setModal(False)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.resize(222, 130)
        root = QtGui.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        form = QtGui.QFormLayout()
        self.plane_input = QtGui.QLineEdit("80")
        form.addRow("Min plane:", self.plane_input)
        root.addLayout(form)
        self.detail_input = QtGui.QCheckBox("Keep detail")
        self.detail_input.setChecked(True)
        root.addWidget(self.detail_input)
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        row = QtGui.QHBoxLayout()
        self.cancel_button = QtGui.QPushButton("Cancel")
        self.process_button = QtGui.QPushButton("Process")
        self.process_button.setDefault(True)
        row.addWidget(self.cancel_button)
        row.addWidget(self.process_button)
        root.addLayout(row)
        self._connect(self.process_button.clicked, lambda *args: self.process())
        self._connect(self.cancel_button.clicked, lambda *args: self.cancel())
        for signal, callback in (
            (self.destroyed, lambda *args: self._finish(destroying=True)),
            (self.finished, lambda *args: self._finish()),
        ):
            signal.connect(callback)
            self._lifetime_connections.append((signal, callback))
        if parent is not None:
            self._connect(parent.destroyed, lambda *args: self._finish())
        self._load(preferences)
        self._open_source()

    def _connect(self, signal: Any, callback: Any) -> None:
        signal.connect(callback)
        self._connections.append((signal, callback))

    def _load(self, preferences: Any) -> None:
        self.preferences = {} if preferences is None else preferences
        try:
            if preferences is None:
                self._settings, self.preferences = prefs.native_preferences(QtCore)
            settings = prefs.load(self.preferences)
            self.plane_input.setText(settings.plane)
            self.detail_input.setChecked(settings.detail)
            if settings.geometry is not None:
                self.setGeometry(*settings.geometry)
            self.persistence_error = settings.warning
        except Exception as error:  # noqa: BLE001 - contain errors at the native UI boundary
            self.persistence_error = str(error)

    def _open_source(self) -> None:
        try:
            if self._backend is None:
                from fontlabapp.contours.angularizzle.native import NativeBackend

                self._backend = NativeBackend()
            self.session = Session(self._backend)
            message = f"{len(self.session.source.layers)} selected layer occurrence(s). Process writes first-master paths."
            self.status.setText(
                " ".join(filter(None, (message, self.persistence_error)))
            )
        except Exception as error:  # noqa: BLE001 - contain errors at the native UI boundary
            self.status.setText(str(error))
            self.process_button.setEnabled(False)

    def _geometry(self) -> tuple[int, int, int, int]:
        rect = self.geometry
        return rect.x(), rect.y(), rect.width(), rect.height()

    def _persist(self, keys: tuple[str, ...]) -> None:
        if self._settings is not None:
            prefs.persist(QtCore, self._settings, self.preferences, keys)

    def process(self) -> None:
        """Finish all source planning before write; keep errors visible and owned."""
        if self._closed or self.session is None:
            return
        try:
            if not self.session.process(
                str(self.plane_input.text), self.detail_input.isChecked()
            ):
                return
            self.status.setText(
                "Processed. Process again uses opening paths; Cancel restores them."
            )
            try:
                prefs.save(
                    self.preferences,
                    str(self.plane_input.text),
                    self.detail_input.isChecked(),
                    self._geometry(),
                )
                self._persist((prefs.PLANE, prefs.CHECK, prefs.WINDOW))
            except Exception as error:  # noqa: BLE001 - contain errors at the native UI boundary
                self.persistence_error = str(error)
                self.status.setText(f"Processed; settings were not saved: {error}")
            if self.session.closed:
                self.close()
        except Exception as error:  # noqa: BLE001 - contain errors at the native UI boundary
            self._failure(error)

    def cancel(self) -> None:
        """Restore only through the bound session, never during destruction."""
        if self._closed:
            return
        try:
            if self.session is None or self.session.cancel():
                self.close()
        except Exception as error:  # noqa: BLE001 - contain errors at the native UI boundary
            self._failure(error)

    def _failure(self, error: Exception) -> None:
        self.status.setText(str(error))
        if getattr(self._backend, "poisoned", False):
            self.process_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            self._retain_recovery()

    def _retain_recovery(self) -> None:
        owners = sys.__dict__.setdefault("_fontlab_angularizzle_recovery", [])
        if not any(owner is self._backend for owner in owners):
            owners.append(self._backend)

    def _finish(self, *, destroying: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if self.session is not None:
            self.session.close()
        if getattr(self._backend, "poisoned", False):
            self._retain_recovery()
        # QObject.destroyed runs after the derived QDialog has gone away.
        # Its own signals are disconnected by Qt; never access finished then.
        connections = self._connections + (
            [] if destroying else self._lifetime_connections
        )
        for signal, callback in reversed(connections):
            try:
                signal.disconnect(callback)
            except Exception as error:  # noqa: BLE001 - finish disconnecting remaining owners
                self.cleanup_errors.append(repr(error))
        self._connections.clear()
        self._lifetime_connections.clear()
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)

    def event(self, event: Any) -> bool:
        """Disconnect owned slots before deferred deletion reaches native Qt."""
        if event.type() == QtCore.QEvent.DeferredDelete:
            self._finish()
        return QtGui.QDialog.event(self, event)

    def closeEvent(self, event: Any) -> None:
        """Record owned window placement before the native close handler runs."""
        try:
            if not self._closed:
                self.preferences[prefs.WINDOW] = self._geometry()
                self._persist((prefs.WINDOW,))
        except Exception as error:  # noqa: BLE001 - contain errors at the native UI boundary
            self.persistence_error = str(error)
        finally:
            self._finish()
            QtGui.QDialog.closeEvent(self, event)
