# this_file: src/fontlabapp/fontui/master_width_comparison.py
# SPDX-License-Identifier: Apache-2.0
"""Select a glyph occurrence and read widths from its registered native masters."""
import math
import time
from typing import Any

__all__ = ["show"]
_HANDLES = []
READ_SECONDS = 0.25


class _SelectionNotice(ValueError):
    """A selection the tool cannot compare; shown without closing the tool."""


class _Comparison:
    def __init__(self, qt: Any, font: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.font = qt, font
        self.problems = []
        self.scope = Scope(self.problems.append)
        self.owned = self.sequence = self.view = self.backend = None
        self.package_id = self.font_id = None
        self.rows = ()
        self.occurrence = self.target = None
        self._closing = self._released = self._queued = self._releasing = False
        self._building = True
        self._reading = False
        self._generation = 0

    def build(self, content: Any) -> None:
        from fontlabapp.fontui import glyph_sequence
        from fontlabapp.fontui.sequence import NativeFontBackend, RFont

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        self.scope.connect(content.finished, self.release, closing=True)
        self.scope.connect(content.destroyed, self._destroyed, closing=True)
        note = gui.QLabel(
            "Compare registered FontLab master widths. This reads stored native "
            "backend state, not unfinished edits held in another scripting wrapper. "
            "Ordinary UFO fonts have no registered FontLab master identity.", content)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.diagnostic = gui.QLabel("", content)
        layout.addWidget(self.diagnostic)
        self.table = gui.QTableWidget(0, 2, content)
        self.table.setHorizontalHeaderLabels(["Master", "Advance width"])
        self.table.setEditTriggers(gui.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)
        try:
            if not isinstance(self.font, RFont) or not isinstance(self.font._backend, NativeFontBackend):
                raise ValueError("An open registered FontLab font is required; ordinary UFO fonts are unsupported")
            self.backend = self.font._backend
            self.font_id = self.backend.font_id
            package = self._package()
            self.package_id = package.id
            self.view = RFont(NativeFontBackend(self.font_id, owns_document=False))
        except Exception as error:
            self.diagnostic.setText(str(error))
            return
        self.sequence = glyph_sequence(self.view, content, self.select)
        if self._closing:
            raise RuntimeError("Master width comparison closed during construction")
        layout.addWidget(self.sequence.widget)
        self.sequence.on_update = self.update
        self.update(self.sequence)

    def _package(self) -> Any:
        if self._closing:
            raise RuntimeError("Master width comparison is closed")
        if self.font._backend is not self.backend:
            raise RuntimeError("The borrowed font backend changed")
        self.font._check()
        package = self.backend._package()
        if package.fgId != self.font_id or (self.package_id is not None and package.id != self.package_id):
            raise RuntimeError("The registered font identity changed")
        return package

    def _snapshot(self, name: str, deadline: float) -> tuple:
        from fontlabapp.masters.inspect.model import master_order, master_layers, widths

        package = self._package()
        masters = master_order(package)
        if not masters or any(not isinstance(m, str) or not m for m in masters) or len(set(masters)) != len(masters):
            raise ValueError("Master identity is missing or ambiguous")
        glyph = package.findName(name)
        if glyph is None or glyph.isNull or glyph.name != name or glyph.package.id != package.id:
            raise ValueError("The selected glyph is missing or belongs to another font")
        found = master_layers(glyph, masters)
        identities = []
        for master in masters:
            if time.monotonic() > deadline or self._closing:
                raise RuntimeError("Master width read was interrupted")
            layer = found.get(master)
            if layer is None:
                identities.append((master, None))
                continue
            if (layer.isNull or not layer.isValid or layer.glyph.id != glyph.id
                    or layer.name != master or layer.isMasterLayer is not True
                    or layer.isMaskLayer is not False or layer.isService is not False):
                raise ValueError("Master layer identity or role is inconsistent")
            identities.append((master, int(layer.id)))
        ids = [identity for _, identity in identities if identity is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("Master layer identities are duplicated")
        values = tuple(widths(glyph, masters))
        if any(value is not None and not math.isfinite(value) for _, value in values):
            raise ValueError("Master width must be finite")
        return (package.id, glyph.id, name, tuple(identities)), values

    def select(self, glyph: Any, index: int) -> None:
        if not self._closing:
            self.update(self.sequence)

    def update(self, sequence: Any) -> None:
        if self._closing:
            return
        self._generation += 1
        generation = self._generation
        self.rows = ()
        self.table.setRowCount(0)
        if self._reading:
            return
        self._reading = True
        try:
            self._package()
            if sequence.closed or sequence.run is None:
                raise ValueError("The glyph sequence has no current preview")
            index = sequence.selected_index
            if index is None:
                self.occurrence = self.target = None
                self.diagnostic.setText("Select a glyph occurrence to compare master widths")
                return
            run = sequence.run
            occurrence = run.glyphs[index]
            if occurrence.name is None:
                raise _SelectionNotice("The selected occurrence has no glyph")
            key = (index, occurrence.name, occurrence.label)
            deadline = time.monotonic() + READ_SECONDS
            identity, values = self._snapshot(occurrence.name, deadline)
            if self.occurrence == key and self.target != identity:
                raise RuntimeError("The selected glyph or master layer identity changed")
            if (identity, values) != self._snapshot(occurrence.name, deadline):
                raise RuntimeError("Master identities or widths changed during the read")
            if (self._closing or generation != self._generation or sequence.closed
                    or sequence.run is not run or sequence.selected_index != index
                    or time.monotonic() > deadline):
                raise RuntimeError("Master width read was interrupted")
            self.occurrence, self.target = key, identity
            self.table.setRowCount(len(values))
            for row, (master, width) in enumerate(values):
                self.table.setItem(row, 0, self.qt.QtGui.QTableWidgetItem(master))
                self.table.setItem(row, 1, self.qt.QtGui.QTableWidgetItem(
                    "Missing layer" if width is None else str(width)))
            if self._closing or generation != self._generation:
                self.table.setRowCount(0)
                return
            self.rows = values
            self.diagnostic.setText(f"{occurrence.name} — occurrence {index + 1}; stored native widths")
        except _SelectionNotice as error:
            self.occurrence = self.target = None
            self.rows = ()
            self.table.setRowCount(0)
            self.diagnostic.setText(str(error))
        except Exception as error:
            self.rows = ()
            self.table.setRowCount(0)
            self.diagnostic.setText(str(error))
            self.release()
        finally:
            self._reading = False
            if self._closing:
                self.release()

    def _fence(self) -> None:
        self._closing = True
        self._generation += 1
        self.rows = ()
        if self.sequence is not None:
            self.sequence.closed = True
            self.sequence.on_select = self.sequence.on_update = None

    def _destroyed(self, *args: Any) -> None:
        self._fence()
        self.scope.finish(destroyed=True)
        if self.sequence is not None:
            self.sequence._parent_destroyed()
            # QObject emits destroyed before deleting its children. Drain their
            # live signal connections now; deferred teardown would be too late.
            try:
                self.close()
            except BaseException as error:
                self.problems.append(error)
        self.release()

    def release(self, *args: Any) -> bool:
        if self._released:
            return True
        self._fence()
        if not self._queued:
            self._queued = True
            try:
                self.qt.QtCore.QTimer.singleShot(0, self._release_queued)
            except BaseException:
                self._queued = False
                raise
        return False

    def _release_queued(self) -> None:
        self._queued = False
        try:
            self._release_now()
        except BaseException as error:
            self.problems.append(error)

    def close(self) -> None:
        if self.sequence is not None and not self.sequence._close_complete:
            self.sequence.close()
            if not self.sequence._close_complete:
                raise RuntimeError("Glyph sequence cleanup is incomplete; owner retained")

    def _release_now(self) -> bool:
        from fontlabapp.qt.widgets import release_owned

        if self._released:
            return True
        self._fence()
        if self._building or self._reading or self._releasing:
            return False
        self._releasing = True
        try:
            complete = release_owned(self.scope, self.owned, self.problems, (self,))
        finally:
            self._releasing = False
        if complete:
            self.sequence = self.view = self.font = self.backend = None
            self.target = self.occurrence = None
            self._released = True
            if self in _HANDLES:
                _HANDLES.remove(self)
        return complete


def show(font: Any, parent: Any = None) -> _Comparison:
    """Borrow one explicit registered font; never switch or close its document."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog, OwnedWidget
    from fontlabapp.fontui.lifecycle import Owned

    qt = _native("PythonQt")
    owner = _Comparison(qt, font)
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Master Width Comparison", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        pending = [error]
        while pending:
            failure = pending.pop()
            peer = getattr(failure, "owner", None)
            if isinstance(peer, OwnedWidget):
                owner.owned = peer
            elif isinstance(peer, Owned):
                owner.sequence = peer
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)
        owner._building = False
        try:
            if not owner._release_now():
                error.add_note("Master width comparison cleanup incomplete; owner retained")
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Master width comparison cleanup interrupted; owner retained")
        raise
    finally:
        owner._building = False
    return owner
