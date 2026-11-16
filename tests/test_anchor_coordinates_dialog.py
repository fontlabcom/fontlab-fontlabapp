# this_file: tests/test_anchor_coordinates_dialog.py
# SPDX-License-Identifier: Apache-2.0
"""Exercise all three actual dialogs using owned offscreen Qt controls."""

from module_paths import module_name as _module_name
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from test_anchor_edit import (
    owned as owned,  # noqa: PLC0414 - shared native-shaped fixture
)


def _application():
    """Create the owned GUI application before legacy QCoreApplication collection."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


APPLICATION = _application()


@pytest.fixture(scope="session")
def qt_application():
    from PySide6 import QtWidgets

    assert isinstance(APPLICATION, QtWidgets.QApplication), (
        "Run GUI tests before a QCoreApplication-only module; refusing unsafe QWidget creation."
    )
    return APPLICATION


@pytest.fixture
def panels(owned, monkeypatch, qt_application):
    from PySide6 import QtCore, QtGui, QtWidgets

    app = qt_application

    class Properties:
        @property
        def palette(self):
            return QtWidgets.QWidget.palette(self)

        @property
        def font(self):
            return QtWidgets.QWidget.font(self)

    gui = NS(
        **{name: getattr(QtGui, name) for name in ("QColor", "QBrush", "QPalette")}
    )
    widgets = (
        "QDialog",
        "QLabel",
        "QLineEdit",
        "QComboBox",
        "QSlider",
        "QSpinBox",
        "QDoubleSpinBox",
        "QCheckBox",
        "QRadioButton",
        "QGroupBox",
        "QTableWidget",
        "QPushButton",
    )
    for name in widgets:
        base = getattr(QtWidgets, name)
        props = {
            key: property(getattr(base, key))
            for key in ("text", "currentIndex", "value", "rowCount", "columnCount")
            if hasattr(base, key)
        }
        if hasattr(base, "setAlignment"):
            props["setAlignment"] = lambda self, value, base=base: base.setAlignment(
                self, QtCore.Qt.AlignmentFlag(value)
            )
        setattr(gui, name, type(name, (Properties, base), props))
    for name in (
        "QVBoxLayout",
        "QHBoxLayout",
        "QGridLayout",
        "QFormLayout",
        "QButtonGroup",
        "QAbstractItemView",
        "QHeaderView",
        "QTableWidgetItem",
    ):
        setattr(gui, name, getattr(QtWidgets, name))

    class TableItem(QtWidgets.QTableWidgetItem):
        def setTextAlignment(self, value):
            super().setTextAlignment(QtCore.Qt.AlignmentFlag(value))

    gui.QTableWidgetItem = TableItem
    qt = NS(QtCore=QtCore, QtGui=gui)
    import fontlabapp
    import fontlabapp.anchors.coordinates.model as coordinates
    from fontlabapp.masters.inspect import model as masters
    from fontlabapp.core import scripting

    g, layer = owned.glyph(points=(("top", 13.25, 27.75), ("bottom", 18.4, 3.2)))
    state = NS(package=owned.package, members=[g.name], selection=[g], dialogs=[])
    owned.package.italicAngle_value = -10
    owned.native.FontMetrics = lambda p, m: NS(
        xHeight=500 if m == "Regular" else 520,
        capsHeight=700,
        ascender=800,
        descender=-200,
    )
    native = lambda name: qt if name == "PythonQt" else owned.native
    monkeypatch.setattr(fontlabapp, "_native", native)
    monkeypatch.setattr(scripting, "_native", native)
    monkeypatch.setattr(coordinates, "_native", native)
    monkeypatch.setattr(masters, "_native", native)
    monkeypatch.setattr(scripting, "current_package", lambda *args: state.package)
    root = Path(__file__).parents[1] / "src"
    for name in (
        "_names_dialog",
        "_proof_dialog",
        "_masters_dialog",
        "_anchor_coordinates_dialog",
    ):
        spec = importlib.util.spec_from_file_location(
            _module_name(name), root / (_module_name(name).replace(".", "/") + ".py")
        )
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
    api = module
    monkeypatch.setattr(api, "font_glyph_names", lambda: list(state.members))
    monkeypatch.setattr(api, "selected_glyphs", lambda p: list(state.selection))

    def create(kind):
        cls = {
            "center": api.CenterAnchors,
            "round": api.RoundAnchors,
            "metrics": api.SnapAnchors,
        }[kind]
        dialog = cls()
        state.dialogs.append(dialog)
        return dialog

    yield NS(
        create=create,
        state=state,
        owned=owned,
        layer=layer,
        glyph=g,
        api=api,
        qt=qt,
        app=app,
        scripting=scripting,
    )
    for dialog in state.dialogs:
        dialog.close()
    app.processEvents()


@pytest.mark.parametrize(
    "kind,name,action,columns",
    [
        ("center", "CenterAnchors", "Apply", 4),
        ("round", "RoundAnchors", "Round", 5),
        ("metrics", "SnapAnchors", "Snap", 5),
    ],
)
def test_actual_controls_defaults_preview_and_facade(
    panels, kind, name, action, columns
):
    d = panels.create(kind)
    assert type(d).__name__ == name and d._snapshot_valid and not d.last_error, (
        d.last_error
    )
    assert d.close_button.text == "Close" and d.apply_button.text == action
    assert d.table.columnCount == columns and d.chosen_masters() == ["Regular"]
    assert d.scope.itemText(1) == "All masters (2)"
    assert panels.scripting.anchors_coordinate_dialog_type(kind) is type(d)
    assert panels.scripting.anchors_coordinates_api().snap(-15, 10) == -10
    if kind == "center":
        assert d.names.text == "top, bottom" and d.angle.value == -10
        assert d.position.value == 50 and d.position.tickInterval() == 25
        assert d.position_label.text == "50 %"
        assert d.settings() == (["top", "bottom"], "advance", 0.5, -10)
        d.reference.setCurrentIndex(1)
        d.position.setValue(30)
        assert d.position_label.text == "30 %" and d.settings()[1:3] == ("ink", 0.3)
    elif kind == "round":
        assert d.step.value == 10 and d.step.minimum() == 1 and d.step.maximum() == 500
        assert d.do_x.isChecked() and d.do_y.isChecked() and d.names.text == ""
        assert d.settings() == (10, True, True, set())
        assert d.table.item(0, 3).text().startswith("-")
    else:
        assert (
            d.names.text == "top" and d.offset.value == 0 and d.attribute() == "xHeight"
        )
        d.choose_metric("Cap height")
        assert d.attribute() == "capsHeight" and "700" in d.values.text
        d.scope.setCurrentIndex(1)
        d.choose_metric("x-height")
        assert "Regular 500" in d.values.text and "Bold 520" in d.values.text
    assert d.apply_button.isEnabled()
    assert d.table.item(0, columns - 1).font().bold()


@pytest.mark.parametrize("kind", ["center", "round", "metrics"])
def test_apply_uses_actual_point_core_and_preserves_original_results(panels, kind):
    d = panels.create(kind)
    original_y = panels.layer.anchors[0].point.y()
    d.apply()
    assert (
        d.last_result["anchors"] > 0
        and d.last_result["layers"] == 1
        and d.last_result["skipped"] == []
    )
    assert sum(e[0] == "notify" for e in panels.owned.events) == 1
    if kind == "center":
        assert panels.layer.anchors[0].point.y() == original_y
    elif kind == "round":
        assert d.table.rowCount == 0 and not d.apply_button.isEnabled()
    else:
        assert panels.layer.anchors[0].point.x() == 13.25
    d.apply()
    assert (
        d.last_result["anchors"] == 0
        and sum(e[0] == "notify" for e in panels.owned.events) == 1
    )


@pytest.mark.parametrize("kind", ["center", "round", "metrics"])
@pytest.mark.parametrize(
    "change", ["raw", "selection", "membership", "master", "options", "font", "metric"]
)
def test_stale_sources_refuse_then_clear_handles_and_rows(panels, kind, change):
    d = panels.create(kind)
    if change == "raw":
        panels.layer.anchors[0].point = NS(x=lambda: 13.26, y=lambda: 27.75)
    elif change == "selection":
        panels.state.selection = []
    elif change == "membership":
        panels.state.members.append("new")
    elif change == "master":
        panels.owned.package.master = "Bold"
    elif change == "options":
        blocked = d.names.blockSignals(True)
        d.names.setText("bottom")
        d.names.blockSignals(blocked)
    elif change == "font":
        panels.state.package = NS(id=999)
    else:
        panels.owned.native.FontMetrics = lambda p, m: NS(
            xHeight=500.125, capsHeight=700, ascender=800, descender=-200
        )
    with pytest.raises(ValueError):
        d.apply()
    assert (
        not d._snapshot_valid
        and not d.apply_button.isEnabled()
        and d.table.rowCount == 0
    )
    assert (
        d.package is None
        and d.glyphs == []
        and d.rebuilds == []
        and d._prepared is None
    )
    assert not any(e[0] == "notify" for e in panels.owned.events)


def test_failure_keeps_all_controls_and_close_before_initial_read(panels, monkeypatch):
    def fail(*args):
        raise RuntimeError("selection read failed")

    monkeypatch.setattr(panels.api, "selected_glyphs", fail)
    d = panels.create("center")
    assert (
        d.close_button.isEnabled()
        and d.reference.count() == 2
        and d.table.rowCount == 0
    )
    assert "selection read failed" in d.last_error and not d.apply_button.isEnabled()
    d.close_button.click()
    assert not d._connections and d.package is None


@pytest.mark.parametrize("kind", ["center", "round", "metrics"])
def test_no_font_and_no_selection_leave_complete_closable_controls(panels, kind):
    panels.state.package = None
    d = panels.create(kind)
    assert d.subtitle.text == "Open a font first." and not d.apply_button.isEnabled()
    panels.state.package = panels.owned.package
    panels.state.selection = []
    empty = panels.create(kind)
    assert "Select glyphs" in empty.subtitle.text and not empty.apply_button.isEnabled()


def test_origin_refusal_keeps_complete_preview_and_blocks_whole_write(panels):
    panels.layer.anchors[0].point = NS(x=lambda: 1, y=lambda: 2)
    d = panels.create("round")
    assert (
        d.table.rowCount
        and not d.apply_button.isEnabled()
        and "Redo" in d.blocker_label.text
    )
    with pytest.raises(ValueError, match="Redo"):
        d.apply()
    assert not any(e[0].startswith("init") for e in panels.owned.events)


def test_direct_rebuild_preview_is_informational_not_blanket_veto(panels, monkeypatch):
    dependent, layer = panels.owned.glyph("Hacute", auto=True)
    panels.state.members.append(dependent.name)
    shape = NS(
        id=888,
        isComponent=True,
        shapeData=NS(componentGlyph="H"),
        transform=NS(
            **{
                key: lambda key=key: 1 if key in {"m11", "m22"} else 0
                for key in ("m11", "m12", "m21", "m22", "dx", "dy")
            }
        ),
    )
    layer.shapes = [shape]
    d = panels.create("center")
    assert d.rebuild_key == ("H",) and d.rebuilds == ["Hacute"]
    assert "Hacute" in d.rebuild_label.text and d.apply_button.isEnabled()
    d.apply()
    assert dependent.lastModified == "UTC"


def test_rebuild_preview_excludes_auxiliary_only_automatic_edges(panels):
    dependent, regular = panels.owned.glyph("Haux")
    auxiliary = NS(**regular.__dict__)
    auxiliary.id += 1000
    auxiliary.autoLayer = True
    auxiliary.shapes = [
        NS(
            id=888,
            isComponent=True,
            shapeData=NS(componentGlyph="H"),
            transform=NS(
                **{
                    key: lambda key=key: 1 if key in {"m11", "m22"} else 0
                    for key in ("m11", "m12", "m21", "m22", "dx", "dy")
                }
            ),
        )
    ]
    dependent.layers.append(auxiliary)
    panels.state.members.append("Haux")
    d = panels.create("center")
    assert d._snapshot_valid and d.rebuilds == []
    assert [g.name for g in d._prepared.dependants] == ["Haux"]


def test_lazy_facade_does_not_import_native_ui_in_clean_process():
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fontlabapp.core.scripting as s; assert callable(s.anchors_coordinate_dialog_type); assert 'PythonQt' not in sys.modules; assert 'fontlabapp.anchors.coordinates.ui' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", ["center", "round", "metrics"])
def test_automatic_targets_skip_with_original_rows_and_result_counts(panels, kind):
    auto, layer = panels.owned.glyph("auto", auto=True)
    layer.shapes = [
        NS(
            id=888,
            isComponent=True,
            shapeData=NS(componentGlyph="H"),
            transform=NS(
                **{
                    key: lambda key=key: 1 if key in {"m11", "m22"} else 0
                    for key in ("m11", "m12", "m21", "m22", "dx", "dy")
                }
            ),
        )
    ]
    panels.state.members.append("auto")
    panels.state.selection.append(auto)
    d = panels.create(kind)
    assert any(
        d.table.item(row, d.table.columnCount - 1).text() == "auto, skipped"
        for row in range(d.table.rowCount)
    )
    d.scope.setCurrentIndex(1)
    d.apply()
    assert d.last_result["skipped"] == ["auto/Regular"]
    assert layer.anchors[0].point.x() == 13.25 and layer.anchors[0].point.y() == 27.75
    assert "auto layers skipped" in d.status.text


def test_empty_ink_and_disabled_axes_are_true_noop_previews(panels):
    d = panels.create("center")
    panels.layer.boundingBox.width, panels.layer.boundingBox.height = (
        lambda: 0,
        lambda: 0,
    )
    d._snapshot_valid = False
    d.reference.setCurrentIndex(1)
    assert d.table.item(0, 3).text() == "empty" and not d.apply_button.isEnabled()
    rounded = panels.create("round")
    rounded.do_x.setChecked(False)
    rounded.do_y.setChecked(False)
    assert rounded.table.rowCount == 0 and not rounded.apply_button.isEnabled()
    assert not any(e[0].startswith("init") for e in panels.owned.events)


def test_duplicate_rows_keep_preview_but_block_ambiguous_writes(panels):
    pin = NS(**panels.layer.anchors[0].__dict__)
    pin.id += 999
    panels.layer.anchors.append(pin)
    d = panels.create("center")
    assert d.table.rowCount == 3 and not d.apply_button.isEnabled()
    assert "Duplicate" in d.blocker_label.text


def test_affected_explicit_recipe_is_diagnosed_without_losing_preview(panels):
    dependent, layer = panels.owned.glyph("Hacute", auto=True)
    layer.recipe = "H+acute"
    layer.shapes = [
        NS(
            id=888,
            isComponent=True,
            shapeData=NS(componentGlyph="H"),
            transform=NS(
                **{
                    key: lambda key=key: 1 if key in {"m11", "m22"} else 0
                    for key in ("m11", "m12", "m21", "m22", "dx", "dy")
                }
            ),
        )
    ]
    panels.state.members.append(dependent.name)
    d = panels.create("center")
    assert (
        d._snapshot_valid and d.table.rowCount == 2 and not d.apply_button.isEnabled()
    )
    assert "recipe" in d.blocker_label.text and d.close_button.isEnabled()


def test_midpreview_source_drift_and_signal_failures_clear_actionable_state(
    panels, monkeypatch
):
    original = panels.api.api.center_plan

    def drift(*args):
        panels.layer.advanceWidth += 1
        return original(*args)

    monkeypatch.setattr(panels.api.api, "center_plan", drift)
    failed = panels.create("center")
    assert "Source changed during preview" in failed.last_error
    assert (
        failed.table.rowCount == 0
        and failed.glyphs == []
        and failed.close_button.isEnabled()
    )
    monkeypatch.setattr(panels.api.api, "center_plan", original)
    d = panels.create("center")
    panels.layer.advanceWidth += 1
    d.names.setText("bottom")
    assert (
        "Source changed" in d.last_error
        and d.table.rowCount == 0
        and d._prepared is None
    )
