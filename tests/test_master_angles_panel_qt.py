# this_file: tests/test_master_angles_panel_qt.py
"""Exercise held angle source with real controls and owned FontLab-boundary doubles."""

import sys

import pytest
from legacy_panel_qt import QtCore, font_host as font_host, legacy_qt as legacy_qt
from shiboken6 import isValid
from test_master_angles import owned as owned


@pytest.fixture
def angle_panel(legacy_qt, font_host, owned):
    package, active = owned
    package.isNull = False
    font_host.package = package
    mod = legacy_qt.modules["_master_angles_dialog"]
    panel = mod.ItalicAngleDialog(None, "Italic Angle", "angles-test")
    legacy_qt.owned.append(panel)
    return panel, mod, package, active, font_host


def test_angles_when_open_then_original_order_range_theme_and_staging_are_retained(
    angle_panel,
):
    panel, _mod, package, _active, _host = angle_panel
    assert not panel.last_error and panel._snapshot_valid, (
        "Open the complete actual panel"
    )
    assert list(panel.spins) == package.masters and panel.table.rowCount() == 3
    assert panel.table.item(1, 0).text() == "Regular  (current)"
    assert (
        panel.scroll_area.widgetResizable() and panel.scroll_area.minimumHeight() == 200
    )
    assert panel.gauge.before_draw is not None and panel.gauge.on_error is not None
    for spin in panel.spins.values():
        assert (spin.minimum(), spin.maximum(), spin.decimals(), spin.suffix()) == (
            -45,
            45,
            1,
            "°",
        )
        assert spin.maximumWidth() == 120 and spin.alignment() == QtCore.Qt.AlignRight
        assert "color:" in spin.styleSheet(), (
            "Use the real palette for native spin readability"
        )
    assert not panel.apply_button.isEnabled() and "Edit an angle" in panel.status.text()
    panel.spins["Thin"].setValue(-12)
    assert panel.edited() == {"Thin": -12, "Regular": -10, "Black": -10}
    assert panel.apply_button.isEnabled() and panel.status.text() == "1 master changed"
    panel.spins["Black"].setValue(12)
    assert panel.status.text() == "2 masters changed"
    assert package.events == [], "Staging and preview must not invoke the held writer"
    assert panel.source_values(cached=True) == panel.source_values()


@pytest.mark.parametrize("drift", ["font", "master", "order", "angle"])
def test_angles_when_source_changes_then_refresh_refuses_and_disconnects_old_spins(
    angle_panel, drift
):
    panel, _mod, package, _active, host = angle_panel
    old = tuple(panel.spins.values())
    if drift == "font":
        host.package = None
    elif drift == "master":
        package.master = "Black"
    elif drift == "order":
        package.masters.reverse()
    else:
        package.values["Thin"] = -9
    with pytest.raises(ValueError, match="current|Masters changed|Source changed"):
        panel.refresh()
    assert not panel.spins and not panel.saved and not panel._spin_connections
    assert not panel._snapshot_valid and panel._angle_snapshot is None
    assert panel.table.rowCount() == 0 and not panel.apply_button.isEnabled()
    assert panel.gauge.angles == [] and panel.gauge.before_draw is None
    assert len(panel._connections) == 2, "Only real Apply and Close callbacks remain"
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert all(not isValid(spin) for spin in old), (
        "Real table destruction retires every old spin"
    )
    assert package.events == [], "Source refusal must precede native writes"


def test_angles_when_apply_clicked_then_real_engine_uses_only_owned_boundary_double(
    angle_panel,
):
    panel, _mod, package, _active, _host = angle_panel
    panel.spins["Thin"].setValue(-12)
    panel.spins["Black"].setValue(8)
    panel.apply_button.click()
    assert panel.last_result == {
        "changed": ["Thin", "Black"],
        "angles": {"Thin": -12, "Regular": -10, "Black": 8},
    }
    assert panel.saved == package.values and panel.package is package
    assert not panel.apply_button.isEnabled() and "2 masters" in panel.status.text()
    assert sum(e[0] == "init" for e in package.events) == 1
    assert package.events[-2][0] == "notify" and package.master == "Regular"


def test_angles_when_unsafe_hinting_then_actual_guard_refuses_before_history(
    angle_panel,
):
    panel, _mod, package, _active, _host = angle_panel
    package.hints["Black"] = 0.363636
    panel.spins["Thin"].setValue(-12)
    panel.apply_button.click()
    assert "blueScale" in panel.slot_error and "refused" in panel.status.text()
    assert not package.events and set(package.values.values()) == {-10}
    assert not panel.spins and panel.last_result is None and not panel._snapshot_valid
    assert panel.close_button.isEnabled(), "A held writer failure remains closable"


@pytest.mark.parametrize("missing", [True, False])
def test_angles_when_initial_source_unavailable_then_visible_close_survives(
    legacy_qt, font_host, owned, missing
):
    package, _active = owned
    package.isNull = False
    package.fail_read = "Black"
    font_host.package = None if missing else package
    mod = legacy_qt.modules["_master_angles_dialog"]
    panel = mod.ItalicAngleDialog(None, "Italic Angle", "failed-angles")
    legacy_qt.owned.append(panel)
    assert panel.close_button.isEnabled() and not panel.apply_button.isEnabled()
    assert panel.spins == {} and panel.table.rowCount() == 0
    assert (
        "Open a font" in panel.subtitle.text()
        if missing
        else "read failed" in panel.last_error
    )
    assert not package.events, "Failed source capture is not a partial edit"


@pytest.mark.parametrize("route", ["close", "reject", "accept", "done"])
def test_angles_when_native_completion_occurs_then_callbacks_and_widgets_are_retired(
    angle_panel, monkeypatch, route
):
    panel, _mod, package, _active, _host = angle_panel
    gauge, life = panel.gauge, panel._completion_lifetime
    monkeypatch.setattr(sys, "_fontlab_samples", {"angles-test": panel}, raising=False)
    if route == "done":
        panel.done(0)
    else:
        getattr(panel, route)()
    assert life.closed and not panel._connections and not panel._spin_connections
    assert gauge.report is gauge.before_draw is gauge.on_error is None
    assert (
        panel.package is None and panel._bound_id is None and not sys._fontlab_samples
    )
    assert not package.events, "Closing never applies pending values"
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(panel) and not isValid(gauge), (
        "Actual Qt resources must be deleted"
    )
