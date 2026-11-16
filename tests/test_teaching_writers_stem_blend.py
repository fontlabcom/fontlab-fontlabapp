# this_file: tests/test_teaching_writers_stem_blend.py
"""Stem Interpolation Lab: context, capture and prepare against fake native objects."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

from test_teaching_writers_stem import make_contour

MOD = "fontlabapp.fontui.teaching_writers.stem_blend"
SQ = [(0.0, 0.0, True), (100.0, 0.0, True), (100.0, 100.0, True), (0.0, 100.0, True)]
STEMS = (10.0, 20.0, 30.0, 40.0)


def mod():
    return importlib.import_module(MOD)


def layer(name, ident, shift=0.0, advance=500.0, **extra):
    points = [(x + shift, y, on) for x, y, on in SQ]
    shape = NS(isComponent=False, transform=NS(isIdentity=lambda: True), contours=[make_contour(points, name="c")])
    return NS(name=name, id=ident, shapes=[shape], isNull=False, autoLayer=False, isLocked=False, advanceWidth=advance, **extra)


class World:
    def __init__(self):
        self.layers = [layer("Light", 1), layer("Bold", 2, 40.0)]
        self.package = NS(id=7, master="Light", masters=["Light", "Bold"], italicAngle_value=-10.0)
        self.glyph = NS(id=3, name="A", package=self.package, layers=self.layers, findLayer=self.find)

    def find(self, name):
        return next((item for item in self.layers if item.name == name), None)


@pytest.fixture
def world(monkeypatch):
    import fontlabapp.contours.nodes.coordinates as coordinates
    import fontlabapp.core.scripting as scripting

    w = World()
    w.current = w.package
    monkeypatch.setattr(scripting, "current_package", lambda: w.current)
    monkeypatch.setattr(coordinates, "current_glyph", lambda package: w.glyph)
    return w


def test_current_context_when_open_then_package_and_glyph(world):
    assert mod().current_context() == (world.package, world.glyph)


def test_current_context_when_no_font_or_glyph_then_value_error(world):
    world.current = None
    with pytest.raises(ValueError, match="font and a glyph"):
        mod().current_context()
    world.current = world.package
    world.glyph.package = NS(id=99)
    with pytest.raises(ValueError, match="current font"):
        mod().current_context()


def test_source_options_when_open_then_layer_names_and_rightward_slant(world):
    assert mod().source_options() == (["Light", "Bold"], 10.0)


def test_capture_pair_when_stable_then_label_and_two_contour_lists(world):
    label, one, two = mod().capture_pair("Light", "Bold")
    assert label == "A" and one[0][1][0][0] == 0.0 and two[0][1][0][0] == 40.0


@pytest.mark.parametrize("missing", ["Nope"])
def test_capture_pair_when_layer_missing_then_value_error(world, missing):
    with pytest.raises(ValueError, match="Both named layers"):
        mod().capture_pair("Light", missing)


def test_capture_pair_when_geometry_changes_between_reads_then_build_again(world, monkeypatch):
    m = mod()
    real = m.read_contours
    calls = []

    def moving(lay, deadline):
        calls.append(1)
        out = real(lay, deadline)
        if len(calls) > 2:
            out[0][1][0] = (out[0][1][0][0] + 1.0, 0.0, True)
        return out

    monkeypatch.setattr(m, "read_contours", moving)
    with pytest.raises(ValueError, match="changed; Build again"):
        m.capture_pair("Light", "Bold")


def test_capture_pair_when_deadline_passed_then_build_again(world, monkeypatch):
    m = mod()
    ticks = iter([0.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0])
    monkeypatch.setattr(m, "monotonic", lambda: next(ticks, 10.0))
    with pytest.raises((ValueError, TimeoutError)):
        m.capture_pair("Light", "Bold")


def test_capture_pair_when_no_font_then_value_error(world):
    world.current = None
    with pytest.raises(ValueError, match="font and a glyph"):
        mod().capture_pair("Light", "Bold")


def test_capture_pair_when_glyph_in_other_font_then_value_error(world):
    world.glyph.package = NS(id=99)
    with pytest.raises(ValueError, match="current font"):
        mod().capture_pair("Light", "Bold")


def test_prepare_blend_when_valid_then_plan_bound_to_context(world):
    plan = mod().prepare_blend("Light", "Bold", STEMS, (15.0, 35.0), (1.0, 1.0), 0.0)
    assert plan["identity"] == (7, 3, "Light") and plan["name"] == "Stem 15x35 (Light)"
    assert plan["advance"] == 500.0 and plan["sources"] == ("Light", "Bold")
    assert plan["contours"][0][1][1][0] == pytest.approx(120.0)


def test_prepare_blend_when_target_layer_exists_then_kept(world):
    world.layers.append(layer("stem 15x35 (light)", 9))
    with pytest.raises(ValueError, match="already exists"):
        mod().prepare_blend("Light", "Bold", STEMS, (15.0, 35.0), (1.0, 1.0), 0.0)


def test_prepare_blend_when_advance_not_finite_then_value_error(world):
    world.layers[0].advanceWidth = float("inf")
    with pytest.raises(ValueError, match="advance must be finite"):
        mod().prepare_blend("Light", "Bold", STEMS, (15.0, 35.0), (1.0, 1.0), 0.0)


def test_prepare_blend_when_master_changes_during_capture_then_build_again(world, monkeypatch):
    m = mod()
    real = m.capture_pair

    def switching(first, second):
        out = real(first, second)
        world.package.master = "Bold"
        return out

    monkeypatch.setattr(m, "capture_pair", switching)
    with pytest.raises(ValueError, match="current master changed"):
        m.prepare_blend("Light", "Bold", STEMS, (15.0, 35.0), (1.0, 1.0), 0.0)


# ------------------------------------------------------------------ create_layer
from test_teaching_writers_stem import make_node  # noqa: E402


class FlShape:
    def __init__(self):
        self.contours = []
        self.isComponent = False
        self.transform = NS(isIdentity=lambda: True)

    def addContour(self, contour, *flags):
        self.contours.append(contour)


class FlLayer:
    def __init__(self):
        self.name, self.advanceWidth, self.shapes = "", 0.0, []
        self.isNull = self.autoLayer = self.isLocked = False
        self.id = 50

    def addShape(self, shape):
        self.shapes.append(shape)


def fl_node(point, nodeType="on"):
    return make_node(point.x, point.y, nodeType == "on")


def fl_contour(nodes, closed=True):
    return make_contour([(n.x, n.y, n.isOn()) for n in nodes], closed)


class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Result(dict):
    """Commit result: subscriptable like the real one, with attribute access."""

    __getattr__ = dict.__getitem__


@pytest.fixture
def native(world, monkeypatch):
    import fontlabapp.core.history.glyphs as history
    import fontlabapp.masters.layers.writer as writer

    monkeypatch.setitem(sys.modules, "fontlab", NS(flLayer=FlLayer, flShape=FlShape, flNode=fl_node, flContour=fl_contour))
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=NS(QPointF=Point)))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: "facts")
    refused = []
    monkeypatch.setattr(history, "refusal", lambda facts, name, operation: refused[0] if refused else "")
    monkeypatch.setattr(writer, "settle", lambda found: None)
    world.glyph.addLayer = world.layers.append
    state = NS(calls=[], refused=refused, mismatches=[])

    def commit(title, layers, glyphs, mutate, **kw):
        state.calls.append((title, kw["operation"]))
        mutate()
        missed = kw["read_back"]()
        mismatches = missed or state.mismatches
        return Result(mismatches=mismatches, pending_note="", pending_updates=())

    monkeypatch.setattr(history, "commit", commit)
    monkeypatch.setattr(history, "unstored_error", lambda mismatches: "|".join(mismatches))
    return state


def plan_for():
    return mod().prepare_blend("Light", "Bold", STEMS, (15.0, 35.0), (1.0, 1.0), 0.0)


def test_create_layer_when_plan_current_then_one_commit_and_note(world, native):
    note = mod().create_layer(plan_for())
    assert len(native.calls) == 1 and native.calls[0][1] == "geometry"
    assert "Stem 15x35 (Light)" in note and "one Undo step" in note
    assert world.find("Stem 15x35 (Light)") is not None


def test_create_layer_when_context_changed_then_build_again(world, native):
    plan = plan_for()
    world.layers[1].advanceWidth = 777.0
    plan["advance"] = 1.0
    with pytest.raises(ValueError, match="Build again"):
        mod().create_layer(plan)
    assert native.calls == []


def test_create_layer_when_name_reserved_then_value_error(world, native):
    plan = plan_for()
    plan["name"] = "Light"
    with pytest.raises(ValueError, match="master name"):
        mod().create_layer(plan)


def test_create_layer_when_dependants_refuse_then_kept(world, native):
    native.refused.append("it has dependants")
    with pytest.raises(ValueError, match="Kept A: it has dependants"):
        mod().create_layer(plan_for())
    assert native.calls == []


def test_create_layer_when_native_add_fails_then_error_names_cause(world, native):
    def boom(layer):
        raise OSError("native refused")

    world.glyph.addLayer = boom
    with pytest.raises(RuntimeError, match="did not add|native refused"):
        mod().create_layer(plan_for())


def test_create_layer_when_readback_mismatches_then_undo_hint(world, native):
    native.mismatches.append("outline differs")
    with pytest.raises(RuntimeError, match="Edit > Undo"):
        mod().create_layer(plan_for())


def test_create_layer_when_stored_outline_differs_then_mismatch_reported(world, native, monkeypatch):
    m = mod()
    monkeypatch.setattr(m, "stored_outline_matches", lambda actual, expected: False)
    with pytest.raises(RuntimeError, match="differs"):
        m.create_layer(plan_for())


# ------------------------------------------------------------------ panel, show and main
class Sig:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class W:
    """PythonQt-style widget: ``text`` is a property, unknown calls are no-ops."""

    def __init__(self, *args):
        self.value = args[0] if args and isinstance(args[0], str) else ""
        self.plain, self.items, self.index, self.deleted = "", [], -1, False
        self.destroyed, self.clicked, self.textChanged, self.currentIndexChanged = Sig(), Sig(), Sig(), Sig()
        self.shown, self.children = 0, []

    def addWidget(self, widget, *rest):
        self.children.append(widget)

    @property
    def text(self):
        return self.value

    def setText(self, value):
        self.value = value

    def setPlainText(self, value):
        self.plain = value

    def clear(self):
        self.items = []

    def addItems(self, items):
        self.items = list(items)

    def setCurrentIndex(self, index):
        self.index = index

    @property
    def currentText(self):
        return self.items[self.index] if 0 <= self.index < len(self.items) else ""

    def show(self):
        self.shown += 1

    def deleteLater(self):
        self.deleted = True

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None


class Clipboard:
    texts = []

    @classmethod
    def clipboard(cls):
        return NS(setText=cls.texts.append)


class Event:
    def __init__(self):
        self.state = None

    def accept(self):
        self.state = "accept"

    def ignore(self):
        self.state = "ignore"


@pytest.fixture
def panel(world, native, monkeypatch):
    gui = NS(QWidget=W, QVBoxLayout=W, QFormLayout=W, QLabel=W, QComboBox=W, QLineEdit=W,
             QPlainTextEdit=W, QPushButton=W, QApplication=Clipboard)
    core = NS(Qt=NS(WindowFlags=lambda value: value, Widget=1, Tool=2, WindowStaysOnTopHint=4, WA_QuitOnClose=5))
    qt = NS(QtGui=gui, QtCore=core)
    Clipboard.texts = []
    shown = mod().show(qt, object())
    yield shown
    mod()._PANELS.clear()


def fill(p, **over):
    values = {2: "10 20", 3: "30 40", 4: "15 35", 5: "1 1", 6: "0"}
    values.update(over)
    for index, text in values.items():
        p.fields[index].setText(text)


def buttons(p):
    return {b.value: b for b in p.box.children}


def test_show_when_opened_then_sources_listed_and_registered(panel):
    assert panel in mod()._PANELS and panel.shown == 1
    assert panel.fields[0].items == ["Light", "Bold"] and panel.fields[0].index == 0
    assert panel.fields[1].index == 1 and panel.fields[6].text == "10"


def test_show_when_embedded_then_not_shown(world, native):
    gui = NS(QWidget=W, QVBoxLayout=W, QFormLayout=W, QLabel=W, QComboBox=W, QLineEdit=W,
             QPlainTextEdit=W, QPushButton=W, QApplication=Clipboard)
    core = NS(Qt=NS(WindowFlags=lambda value: value, Widget=1, Tool=2, WindowStaysOnTopHint=4, WA_QuitOnClose=5))
    p = mod().show(NS(QtGui=gui, QtCore=core), object(), embedded=True)
    assert p.shown == 0
    mod()._PANELS.clear()


def test_panel_when_built_then_svg_and_plan_ready_and_edits_invalidate(panel):
    fill(panel)
    panel.build_result()
    assert panel.content.startswith("<svg") and panel.plan_data["name"].startswith("Stem 15x35")
    assert "New layer" in panel.status_line.text
    panel.fields[2].textChanged.emit("x")
    assert panel.content == "" and panel.plan_data is None and panel.result_field.plain == ""


def test_panel_when_inputs_invalid_then_status_reports_error(panel):
    fill(panel, **{})
    panel.fields[4].setText("a b")
    panel.build_result()
    assert "space-separated" in panel.status_line.text and panel.plan_data is None


def test_panel_when_create_layer_without_build_then_build_first(panel):
    panel.apply_result()
    assert panel.status_line.text == "Build the blend first."


def test_panel_when_create_layer_after_build_then_one_commit_and_plan_cleared(panel, native):
    fill(panel)
    panel.build_result()
    panel.apply_result()
    assert len(native.calls) == 1 and native.calls[0][1] == "geometry"
    assert "one Undo step" in panel.status_line.text and panel.plan_data is None


def test_panel_when_create_layer_refused_then_error_shown(panel, world):
    fill(panel)
    panel.build_result()
    world.layers.append(layer("Stem 15x35 (Light)", 9))
    panel.apply_result()
    assert "already exists" in panel.status_line.text
    assert panel.plan_data is None


def test_panel_when_copy_then_clipboard_only_after_build(panel):
    panel.copy_result()
    assert panel.status_line.text == "Build the blend first." and Clipboard.texts == []
    fill(panel)
    panel.build_result()
    panel.copy_result()
    assert Clipboard.texts == [panel.content] and "SVG copied" in panel.status_line.text


def test_panel_when_export_then_new_file_written_and_overwrite_reported(panel, tmp_path):
    fill(panel)
    panel.build_result()
    panel.fields[7].setText(str(tmp_path / "out.svg"))
    panel.save_result()
    assert (tmp_path / "out.svg").read_text() == panel.content and "SVG exported" in panel.status_line.text
    panel.save_result()
    assert "partial file" in panel.status_line.text


def test_panel_when_button_clicked_then_action_runs(panel):
    fill(panel)
    buttons(panel)["Build Blend"].clicked.emit()
    assert panel.content
    buttons(panel)["Refresh Sources"].clicked.emit()
    assert panel.content == ""


def test_panel_when_refresh_fails_then_status_reports(panel, world):
    world.current = None
    panel.refresh_sources()
    assert "font and a glyph" in panel.status_line.text


def test_panel_when_closed_then_unregistered_and_deleted_else_event_ignored(panel):
    event = Event()
    panel.scope.finish = lambda **kw: False
    panel.closeEvent(event)
    assert event.state == "ignore" and panel in mod()._PANELS
    del panel.scope.finish
    panel.closeEvent(event)
    assert event.state == "accept" and panel not in mod()._PANELS and panel.deleted


def test_panel_when_destroyed_then_owner_released(panel):
    panel.destroyed.emit()
    assert panel not in mod()._PANELS


def test_show_when_panel_show_fails_then_cleaned_up_and_error_raised(world, native, monkeypatch):
    class Bad(W):
        def show(self):
            raise RuntimeError("boom")

    gui = NS(QWidget=Bad, QVBoxLayout=W, QFormLayout=W, QLabel=W, QComboBox=W, QLineEdit=W,
             QPlainTextEdit=W, QPushButton=W, QApplication=Clipboard)
    core = NS(Qt=NS(WindowFlags=lambda value: value, Widget=1, Tool=2, WindowStaysOnTopHint=4, WA_QuitOnClose=5))
    with pytest.raises(RuntimeError, match="boom"):
        mod().show(NS(QtGui=gui, QtCore=core), object())
    assert mod()._PANELS == []


def test_main_when_show_raises_then_message_printed(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: object()))
    monkeypatch.setitem(sys.modules, "PythonQt", NS())
    monkeypatch.setattr(mod(), "show", lambda qt, parent: (_ for _ in ()).throw(ValueError("no font")))
    mod().main()
    assert "Stem Blend: no font" in capsys.readouterr().out
    shown = []
    monkeypatch.setattr(mod(), "show", lambda qt, parent: shown.append(parent))
    mod().main()
    assert len(shown) == 1
