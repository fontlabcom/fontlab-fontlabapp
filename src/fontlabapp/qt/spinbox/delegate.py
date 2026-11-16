# this_file: src/fontlabapp/qt/spinbox/delegate.py
# SPDX-License-Identifier: Apache-2.0
"""Injected native QStyledItemDelegate with owned integer editors.

Keep Qt's event filter, correction, keyboard navigation, drawing and stepping.
Only the four original editing virtuals supply local policy. Errors cannot leave
a PythonQt virtual. Editors remain owned until actual native destruction.
"""

from functools import wraps
from typing import Any

from fontlabapp.core.signals.scope import Scope


def value(obj: Any, name: str) -> Any:
    """Read one declared property/method across PythonQt and reference bindings."""
    result = getattr(obj, name)
    return result() if callable(result) else result


def emit(signal: Any, *args: Any) -> None:
    getattr(signal, "emit", signal)(*args)


def virtual(method: Any) -> Any:
    """Contain native callbacks, including errors in diagnostic rendering."""

    @wraps(method)
    def call(self: Any, *args: Any) -> Any:
        if not self.active:
            return None
        try:
            self.observed.append(method.__name__)
            return method(self, *args)
        except Exception as error:  # noqa: BLE001 - PythonQt virtual boundary
            self.error = str(error)
            try:
                self.failed(error)
            except Exception as report_error:  # noqa: BLE001 - keep diagnostics contained
                self.error += "; diagnostic failed: " + str(report_error)
            return None

    return call


def delegate_type(core: Any, gui: Any) -> type:
    """Construct against the supplied native namespace without importing Qt."""

    class SpinDelegate(gui.QStyledItemDelegate):
        def __init__(
            self, model: Any, parent: Any, official: bool, failed: Any, changed: Any
        ) -> None:
            gui.QStyledItemDelegate.__init__(self, parent)
            self.model, self.official = model, official
            self.failed, self.changed = failed, changed
            self.records: dict[int, list] = {}
            self.active, self.writing = True, False
            self.error, self.observed, self.commits = "", [], 0
            self.scope = Scope(failed)
            self.scope.connect(self.closeEditor, self._closed_editor)

        def _index(self, index: Any, model: Any = None) -> None:
            if model is not None and model != self.model:
                raise ValueError("Foreign worksheet model.")
            if (
                not index.isValid()
                or index.model() != self.model
                or not 0 <= index.row() < 4
                or not 0 <= index.column() < 2
            ):
                raise ValueError("Foreign or stale worksheet index.")

        def _editor(self, editor: Any, index: Any) -> list:
            self._index(index)
            record = self.records.get(id(editor))
            if (
                record is None
                or record[0] is not editor
                or not record[3]
                or record[1] != index
            ):
                raise ValueError("Foreign, closed or stale worksheet editor.")
            return record

        def _destroyed_editor(self, identity: int) -> None:
            record = self.records.pop(identity, None)
            if record is not None:
                record[2].finish(destroyed=True)

        def _closed_editor(self, editor: Any, *args: Any) -> None:
            record = self.records.get(id(editor))
            if record is not None:
                record[3] = False

        def active_editor(self) -> Any:
            return next((r[0] for r in self.records.values() if r[3]), None)

        @virtual
        def createEditor(self, parent: Any, option: Any, index: Any) -> Any:
            self._index(index)
            editor = gui.QSpinBox(parent)
            scope = Scope(self.failed)
            self.records[id(editor)] = [editor, core.QModelIndex(index), scope, True]
            try:
                identity = id(editor)
                scope.connect(
                    editor.destroyed, lambda *args: self._destroyed_editor(identity)
                )
                editor.setRange(0, 100)
                if self.official:
                    editor.setFrame(False)
                return editor
            except Exception:
                self.records[id(editor)][3] = False
                editor.deleteLater()
                raise

        @virtual
        def setEditorData(self, editor: Any, index: Any) -> None:
            self._editor(editor, index)
            source = index.model() if self.official else self.model
            data = source.data(index, core.Qt.EditRole)
            editor.setValue(data if self.official else int(data))

        @virtual
        def setModelData(self, editor: Any, model: Any, index: Any) -> None:
            self._index(index, model)
            self._editor(editor, index)
            if self.writing:
                raise RuntimeError("A worksheet commit is already in progress.")
            self.writing, self.error = True, ""
            try:
                previous = model.data(index, core.Qt.EditRole)
                blocked = model.blockSignals(True)
                try:
                    editor.interpretText()
                    number = value(editor, "value")
                    if type(number) is not int or not 0 <= number <= 100:
                        raise ValueError(
                            "The native editor did not return an integer in 0 to 100."
                        )
                    try:
                        if model.setData(index, number, core.Qt.EditRole) is False:
                            raise RuntimeError("Qt refused the worksheet cell commit.")
                        actual = model.data(index, core.Qt.EditRole)
                        if type(actual) is not int or actual != number:
                            raise RuntimeError(
                                "The worksheet cell did not retain its integer commit."
                            )
                    except Exception:
                        if model.data(index, core.Qt.EditRole) != previous or type(
                            model.data(index, core.Qt.EditRole)
                        ) is not type(previous):
                            restored = model.setData(index, previous, core.Qt.EditRole)
                            if (
                                restored is False
                                or type(model.data(index, core.Qt.EditRole))
                                is not type(previous)
                                or model.data(index, core.Qt.EditRole) != previous
                            ):
                                raise RuntimeError(
                                    "Worksheet rollback failed; close this local draft."
                                )
                        raise
                finally:
                    model.blockSignals(blocked)
            finally:
                self.writing = False
            emit(
                model.dataChanged, index, index, [core.Qt.EditRole, core.Qt.DisplayRole]
            )
            self.changed()
            self.commits += 1

        @virtual
        def updateEditorGeometry(self, editor: Any, option: Any, index: Any) -> None:
            self._editor(editor, index)
            editor.setGeometry(option.rect)

        def finalize(self) -> bool:
            """Commit pending acceptable input through the same virtual before refresh."""
            editor = self.active_editor()
            if editor is None:
                return True
            if not value(editor, "hasAcceptableInput"):
                raise ValueError("Finish or cancel the current cell before refreshing.")
            index = self.records[id(editor)][1]
            before = self.commits
            self.setModelData(editor, self.model, index)
            if self.commits != before + 1:
                raise ValueError(self.error or "The cell commit was refused.")
            emit(self.closeEditor, editor, gui.QAbstractItemDelegate.NoHint)
            return self.active_editor() is None

        def cancel(self) -> None:
            """Cancel pending cells before Reset or Close; queued commits are fenced."""
            for record in list(self.records.values()):
                if record[3]:
                    record[3] = False
                    emit(
                        self.closeEditor,
                        record[0],
                        gui.QAbstractItemDelegate.RevertModelCache,
                    )

        def finish(self, *, destroyed: bool = False) -> bool:
            self.active = False
            if destroyed:
                for identity in list(self.records):
                    self._destroyed_editor(identity)
            return self.scope.finish(destroyed=destroyed)

    return SpinDelegate
