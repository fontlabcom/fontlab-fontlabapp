# this_file: tests/test_filter_table_dialog.py
"""Owned model/view controls; standalone Qt5 and Qt6 run in separate processes."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from fontlabapp.qt.tables.filter.model import Table

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets, sip

    valid = lambda value: not sip.isdeleted(value)
    Proxy = QtCore.QSortFilterProxyModel
    RegExp = QtCore.QRegExp
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import isValid as valid

    class RegExp:
        RegExp, Wildcard, FixedString = range(3)

        def __init__(self, pattern="", case=QtCore.Qt.CaseSensitive, syntax=0):
            self.pattern, self.case = pattern, case
            if syntax == self.Wildcard:
                pattern = QtCore.QRegularExpression.wildcardToRegularExpression(pattern)
            elif syntax == self.FixedString:
                pattern = QtCore.QRegularExpression.escape(pattern)
            options = (
                QtCore.QRegularExpression.DotMatchesEverythingOption
                | QtCore.QRegularExpression.UseUnicodePropertiesOption
            )
            if case == QtCore.Qt.CaseInsensitive:
                options |= QtCore.QRegularExpression.CaseInsensitiveOption
            self.expression = QtCore.QRegularExpression(pattern, options)
            self.match = None

        def indexIn(self, text):
            self.match = self.expression.match(str(text))
            return self.match.capturedStart() if self.match.hasMatch() else -1

        def cap(self, number):
            return self.match.captured(number)

    class Proxy(QtCore.QSortFilterProxyModel):
        def setFilterRegExp(self, value):
            # Test-only Qt6 bridge; actual QRegExp semantics run in Qt5 separately.
            self._legacy_regexp = value
            self.setFilterRegularExpression(value.expression)

        def filterRegExp(self):
            return self._legacy_regexp


APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
ROWS = (
    ("a.alt", "U+0061", "2026-01-01 10:00:00"),
    ("B", "U+0042", "2026-06-01 12:30:00"),
    ("ß", "", "2026-12-31 00:00:00"),
)


@pytest.fixture(params=[False, True], ids=["basic", "custom"])
def panel(monkeypatch, request):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel, gui.QSortFilterProxyModel = Dialog, Label, Proxy
    core = NS(
        **{n: getattr(QtCore, n) for n in dir(QtCore) if n.startswith("Q") or n == "Qt"}
    )
    core.QRegExp = RegExp
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=gui, QtCore=core))
    for name in (
        "_names_dialog",
        "_filter_table_controls",
        "_filter_table_proxy",
        "_filter_table_dialog",
        "_official_filter_proxy",
        "_official_table_filter",
    ):
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.qt.tables.filter.ui")
    state = NS(rows=ROWS, fail=False, calls=0)

    def capture():
        state.calls += 1
        if state.fail:
            raise ValueError("owned capture changed")
        return Table(("Glyph", "Unicode", "Modified"), state.rows)

    w = module.FilterTableDialog(
        None,
        "Owned glyph filters",
        "owned_glyph_filters",
        capture,
        request.param,
        "Owned scalar snapshot",
    )
    yield w, state, request.param
    if valid(w):
        w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_panel_when_built_then_no_control_shadows_a_qt_member(panel):
    # PythonQt refuses to overwrite slots ("Slot 'lower' can not be overwritten").
    w, _, _ = panel
    clashes = [
        name for name in vars(w)
        if hasattr(QtWidgets.QDialog, name)
        and "Signal" not in type(getattr(QtWidgets.QDialog, name)).__name__  # bound signals are fine
    ]
    assert clashes == [], f"rename controls that shadow QDialog members: {clashes}"


def names(w):
    return [str(w.proxy.data(w.proxy.index(i, 0))) for i in range(w.proxy.rowCount())]


def test_panel_when_built_then_readonly_source_proxy_full_rows_and_modes(panel):
    w, state, custom = panel
    assert w.model.rowCount() == 3 and sorted(names(w)) == sorted(r[0] for r in ROWS)
    assert w.source_view.model() is w.model and w.proxy_view.model() is w.proxy
    assert not w.isModal() and not w.model.item(0, 0).isEditable()
    assert w.column.isEnabled() is (not custom)
    assert w.syntax.count() == 3 and state.calls == 1
    w.proxy.sort(0, QtCore.Qt.AscendingOrder)
    w.sort_case.setChecked(True)
    assert names(w) == ["B", "a.alt", "ß"]
    w.sort_case.setChecked(False)
    assert names(w) == ["a.alt", "B", "ß"]


@pytest.mark.parametrize(
    "mode,pattern,expected",
    [
        (0, "a|B", ["a.alt", "B"]),
        (1, "a*", ["a.alt"]),
        (2, ".alt", ["a.alt"]),
        (0, "[", []),
    ],
)
def test_panel_when_modes_changed_then_exact_subset_without_native_recapture(
    panel, mode, pattern, expected
):
    w, state, _ = panel
    w.syntax.setCurrentIndex(mode)
    w.pattern.setText(pattern)
    assert sorted(names(w)) == sorted(expected)
    assert state.calls == 1 and w.model.rowCount() == 3
    w.filter_case.setChecked(True)
    w.syntax.setCurrentIndex(2)
    w.pattern.setText("b")
    assert names(w) == []


def test_panel_when_basic_column_or_custom_dates_then_original_distinct_contracts(
    panel,
):
    w, _, custom = panel
    w.syntax.setCurrentIndex(2)
    w.pattern.setText("0042")
    if custom:
        assert names(w) == ["B"]
        w.pattern.setText("")
        w.limit_dates.setChecked(True)
        w.date_from.setDate(QtCore.QDate(2026, 6, 1))
        w.date_to.setDate(QtCore.QDate(2026, 6, 1))
        assert names(w) == ["B"], "Both date bounds include the full day"
        w.date_from.setDate(QtCore.QDate(2026, 7, 1))
        assert names(w) == []
        w.limit_dates.setChecked(False)
        assert len(names(w)) == 3
    else:
        assert names(w) == []
        w.column.setCurrentIndex(1)
        assert names(w) == ["B"]
        w.column.setCurrentIndex(2)
        w.pattern.setText("2026-12-31")
        assert names(w) == ["ß"]


def test_panel_when_refresh_fails_then_all_rows_detached_and_recovers(panel):
    w, state, _ = panel
    state.fail = True
    w.refresh_button.click()
    assert (
        w.model.rowCount() == 0
        and w.proxy.rowCount() == 0
        and "owned capture changed" in w.status.text()
    )
    state.fail = False
    state.rows = ()
    w.refresh_button.click()
    assert w.model.rowCount() == 0 and "0" in w.status.text()
    state.rows = ROWS
    w.refresh_button.click()
    assert w.model.rowCount() == 3 and len(names(w)) == 3


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_panel_when_completed_then_models_disconnected_callbacks_released_and_late_calls_inert(
    panel, route
):
    w, state, custom = panel
    proxy, model = w.proxy, w.model
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "reject":
        w.reject()
    elif route == "accept":
        w.accept()
    elif route == "done":
        w.done(0)
    elif route == "destroy":
        w.deleteLater()
    else:
        if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
            from PyQt5.QtTest import QTest
        else:
            from PySide6.QtTest import QTest
        QTest.keyClick(w, QtCore.Qt.Key_Escape)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and not w._connections and w._capture is None
    assert w.KEY not in sys._fontlab_samples
    before = state.calls
    w.refresh()
    w.update_filter()
    assert state.calls == before
    assert not valid(proxy) and not valid(model)
    if custom:
        assert proxy.filterAcceptsRow(0, QtCore.QModelIndex()) is False


@pytest.mark.parametrize(
    "failure", ["wrong-result", "closed-in-capture", "render-deadline"]
)
def test_refresh_when_invalid_or_closed_or_expired_then_no_partial_views(
    panel, monkeypatch, failure
):
    w, _state, _ = panel
    if failure == "wrong-result":
        w._capture = lambda: None
    elif failure == "closed-in-capture":

        def capture():
            w.close()
            return Table(("A", "B", "C"), ROWS)

        w._capture = capture
    else:
        module = sys.modules[w.__class__.__module__]
        times = iter([0.0, 0.0, 3.0])
        monkeypatch.setattr(module, "monotonic", lambda: next(times))
    w.refresh()
    assert w.table_data is None and w.model.rowCount() == 0
    assert w.proxy.rowCount() == 0
    if failure == "closed-in-capture":
        assert w._closed and w._capture is None
    else:
        assert "complete immutable" in w.status.text() or "expired" in w.status.text()


def test_custom_proxy_when_virtual_fails_then_error_contained_and_late_calls_inert(
    panel, monkeypatch
):
    w, _, custom = panel
    if not custom:
        return
    proxy = w.proxy
    # Out-of-domain model indexes must not throw across a Qt virtual callback.
    assert proxy.filterAcceptsRow(100, QtCore.QModelIndex()) is False
    assert proxy.error
    wrong = NS(row=lambda: 100, column=lambda: 0)
    assert proxy.lessThan(wrong, wrong) is False and proxy.error
    proxy.deactivate()
    assert proxy.filterAcceptsRow(0, QtCore.QModelIndex()) is False
    assert proxy.lessThan(wrong, wrong) is False
    w.update_filter()
    assert len(names(w)) == 3
    from fontlabapp.qt.tables.filter.model import Query

    def broken(*args):
        raise ValueError("owned matcher failure")

    monkeypatch.setattr(Query, "accepts", broken)
    w.update_filter()
    assert w.table_data is None and "owned matcher failure" in w.status.text()
    assert w.model.rowCount() == w.proxy.rowCount() == 0


def test_parent_destruction_when_owned_then_models_and_callbacks_release_before_child_delete(
    panel,
):
    w, _, custom = panel
    parent = QtWidgets.QDialog()
    child = w.__class__(
        parent,
        "Owned child",
        "owned_child",
        lambda: Table(("A", "B", "C"), ()),
        custom,
        "Empty",
    )
    sys.__dict__.setdefault("_fontlab_samples", {})[child.KEY] = child
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert child._closed and child._capture is None and not child._connections
    assert child.table_data is None and child.KEY not in sys._fontlab_samples


def test_dispose_when_a_disconnect_or_native_child_already_failed_then_other_callbacks_release(
    panel,
):
    w, _, _ = panel

    class BrokenSignal:
        def disconnect(self, slot):
            raise RuntimeError("owned disconnected signal")

    w._connections.append((BrokenSignal(), lambda: None))
    w.model.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    w.close()
    assert w._closed and w._capture is None and not w._connections
    assert w.table_data is None and w._disconnect_errors


def test_refresh_when_capture_closes_then_late_error_does_not_touch_deleted_controls(
    panel,
):
    w, _, _ = panel

    def closed_error():
        w.close()
        raise ValueError("late owned capture error")

    w._capture = closed_error
    w.refresh()
    assert w._closed and w._capture is None and w.table_data is None


def test_source_engines_when_casefold_expands_unicode_then_basic_and_custom_stay_distinct(
    panel,
):
    w, _, custom = panel
    w.syntax.setCurrentIndex(2)
    w.pattern.setText("SS")
    assert names(w) == (["ß"] if custom else []), (
        "Keep Qt basic matching distinct from the source custom casefold"
    )
