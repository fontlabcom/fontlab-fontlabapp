# this_file: src/fontlabapp/fontui/node_counts_masters.py
# SPDX-License-Identifier: Apache-2.0
"""Browse stored native point counts against an explicitly chosen master."""

from time import monotonic
from typing import Any

from .glyph_metrics import MetricsInspector

_HANDLES = []

__all__ = ("show",)


def _package(font: Any) -> Any:
    """Require the caller's live registered font without changing its master."""
    font._check()
    package = font._backend._package()
    if package.isNull or package.fgId != font._backend.font_id:
        raise ValueError("The registered font identity changed")
    return package


def counts(font: Any, name: str, masters: tuple[str, ...]) -> tuple:
    """Double-read identities and own-contour counters under one deadline."""
    from fontlabapp.contours.point_counts.native import _check, _layer

    deadline = monotonic() + 0.5

    def snapshot() -> tuple:
        package = _package(font)
        if tuple(package.masters) != masters:
            raise ValueError("Masters changed; reopen the browser")
        glyph = package.findName(name)
        if (glyph is None or glyph.isNull or glyph.name != name
                or glyph.package.id != package.id):
            raise ValueError("Selected glyph is unavailable")
        rows = []
        for master in masters:
            _check(deadline)
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                rows.append((master, None, None, None))
                continue
            if (not layer.isValid or layer.isMasterLayer is not True
                    or layer.isMaskLayer or layer.isService or layer.autoLayer
                    or layer.glyph.id != glyph.id or layer.name != master):
                raise ValueError("Master layer role or identity is unsupported")
            count, shapes = _layer(layer, deadline)
            rows.append((master, int(layer.id), count, shapes))
        _check(deadline)
        return package.id, glyph.id, tuple(rows)

    first = snapshot()
    if first != snapshot():
        raise ValueError("Master layers or points changed during the read")
    return tuple((master, count) for master, _, count, _ in first[2])


class NodeCounts(MetricsInspector):
    """Reuse browser preview and retryable ownership from the metrics inspector."""

    def build(self, content: Any) -> None:
        from . import _construct
        from .native import Browser

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        details = gui.QWidget(content)
        detail_layout = gui.QVBoxLayout(details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.comparison, self.status = gui.QLabel(details), gui.QLabel(details)
        self.comparison.setWordWrap(True)
        self.status.setWordWrap(True)
        self.table = gui.QTreeWidget(details)
        self.table.setRootIsDecorated(False)
        self.table.setHeaderLabels(["Master", "Points", "Handles", "Nodes", "Paths", "Δ"])
        self.chooser = gui.QComboBox(content)
        self.chooser.setAccessibleName("Reference master")
        self.masters = ()
        self.reference = None
        self._busy = False
        self._generation = 0
        try:
            self.masters = tuple(_package(self.font).masters)
            if (not self.masters or any(not isinstance(m, str) or not m for m in self.masters)
                    or len(set(self.masters)) != len(self.masters)):
                raise ValueError("Master names are missing or ambiguous")
            self.reference = self.masters[0]
            self.chooser.addItems(list(self.masters))
        except Exception as error:
            self.masters = ()
            self.status.setText(f"A registered FontLab font is required: {error}")
        reference_row = gui.QHBoxLayout()
        reference_row.addWidget(self.chooser)
        reference_row.addWidget(self.comparison)
        detail_layout.addLayout(reference_row)
        detail_layout.addWidget(self.table)
        self._wire(content)
        self.scope.connect(self.chooser.currentIndexChanged, self.choose_master)
        self.browser = _construct(Browser, self.font, content, None, False, False, self.selected)
        self.browser.selection_layout.addWidget(details, 2)
        self.browser.layout.addWidget(self.status)
        layout.addWidget(self.browser.widget)

    def choose_master(self, index: int) -> None:
        if self._closing:
            return
        self.reference = self.masters[index] if 0 <= index < len(self.masters) else None
        self.selected(self.font, tuple(self.browser.state.selected))

    def selected(self, font: Any, names: tuple[str, ...]) -> None:
        from fontlabapp.masters.point_counts.model import render

        if self._closing:
            return
        self._generation += 1
        generation = self._generation
        self.rows = ()
        self.comparison.setText("")
        self.comparison.setToolTip("")
        self._fill(self.table, ())
        if self._busy:
            return
        self._busy = True
        try:
            if font is not self.font:
                raise ValueError("Selection belongs to another font")
            if not self.masters:
                return
            if not names:
                self.status.setText("Select a glyph to compare stored own-contour points")
                return
            if self.reference is None:
                raise ValueError("Select a reference master")
            rows = counts(font, names[0], self.masters)
            reference = dict(rows)[self.reference]
            if reference is None:
                raise ValueError("The reference master layer is missing")
            text = render(tuple(row for _, row in rows if row is not None))
            deltas = "\n".join(
                f"{master}: Missing layer" if row is None else
                f"{master}: {row.counts.points - reference.counts.points:+d} points"
                for master, row in rows
            )
            if not self._closing and generation == self._generation:
                self.rows = rows
                self._fill(self.table, tuple(
                    (master, "Missing layer", "—", "—", "—", "—") if row is None else
                    (master, row.counts.points, row.counts.handles,
                     row.counts.lines + row.counts.curves, row.counts.paths,
                     f"{row.counts.points - reference.counts.points:+d}")
                    for master, row in rows
                ))
                self.comparison.setText("Differences from " + self.reference)
                self.comparison.setToolTip(text + "\nDifferences from " + self.reference + "\n" + deltas)
                self.status.setText(f"{names[0]} — own contours only; components are not decomposed")
        except Exception as error:
            if not self._closing and generation == self._generation:
                self._clear_preview()
                self.status.setText(str(error))
        finally:
            self._busy = False

    def release(self) -> bool:
        if self._busy:
            self._queued = False
            self._finished()
            return False
        complete = super().release()
        if complete and self in _HANDLES:
            _HANDLES.remove(self)
        return complete


def show(font: Any, parent: Any = None) -> NodeCounts:
    """Borrow a registered font; never write, switch masters or close its document."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog, OwnedWidget
    from .lifecycle import Owned

    qt = _native("PythonQt")
    owner = NodeCounts(qt, font)
    owner._busy = False
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Node Counts Across Masters", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        pending = [error]
        while pending:
            failure = pending.pop()
            failed = getattr(failure, "owner", None)
            if isinstance(failed, OwnedWidget):
                owner.owned = failed
            elif isinstance(failed, Owned):
                owner._failed_owners.append(failed)
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)
        try:
            if not owner.release():
                error.add_note("Node count cleanup incomplete; owner retained")
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Node count cleanup interrupted; owner retained")
        raise
    return owner
