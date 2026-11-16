# this_file: tests/test_metrics_panel.py
"""Shared Metrics plan/write model and the MetricsPanel base (issue 122, T14b).

Pure parts run on plain doubles. The panel runs on a small PythonQt double
(widgets with PythonQt-style properties: ``palette``, ``font``, ``value``,
``currentIndex``) and FontLab doubles that log every native call. They prove
the plan arithmetic, refusals, override binding and the one-Undo call shape,
not native FontLab behaviour.
"""

from module_paths import module_file as _module_file
import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.metrics.panel.model as mp

LOG: list = []
STAMP = "UTC"


# ---------------------------------------------------------------- FontLab doubles
class Box:
    def __init__(self, x, w, h=100):
        self._x, self._w, self._h = x, w, h

    def x(self):
        return self._x

    def width(self):
        return self._w

    def height(self):
        return self._h


class Layer:
    isNull = False

    def __init__(self, name, width, left=50, ink=100, *, auto=False, link=""):
        self.name, self._width, self.left, self.ink = name, width, left, ink
        self.autoLayer = auto
        self.metricsLeft, self.metricsRight, self.metricsWidth = link, "", ""
        self.update_result = True
        self.stubborn = False
        self.shapes = []

    @property
    def advanceWidth(self):
        return self._width

    @advanceWidth.setter
    def advanceWidth(self, value):
        LOG.append(("width", self.name, value))
        if not self.stubborn:
            self._width = value

    @property
    def boundingBox(self):
        return Box(self.left, self.ink) if self.ink else Box(0, 0, 0)

    def applyTransform(self, transform):
        LOG.append(("transform", self.name, transform.dx))
        self.left += transform.dx

    def changed(self):
        LOG.append(("changed", self.name))

    def update(self):
        return self.update_result

    def checkInitHistoryState(self, flag):
        LOG.append(("init", self.name))


class Glyph:
    isNull = False

    def __init__(self, name, layers):
        self.name, self.layers = name, list(layers)

    def findLayer(self, master):
        for layer in self.layers:
            if layer.name.split("/")[1] == master:
                return layer
        return None

    def checkInitHistoryState(self, flag):
        LOG.append(("init", self.name))

    @property
    def lastModified(self):
        return None

    @lastModified.setter
    def lastModified(self, value):
        LOG.append(("stamp", self.name))


class Transform:
    def __init__(self, m11, m12, m21, m22, dx, dy):
        self.dx = dx


class Native:
    """The ``fontlab`` double."""

    def __init__(self):
        self.flGlyph = NS(updatedFgGlyphs=tuple)
        self.actions = {}

    def MainWindow(self):
        return NS(findChild=lambda kind, name: self.actions.get(name))

    def flItems(self):
        return self

    def notifyChangesApplied(self, title, items):
        LOG.append(("notify", title, [i.name for i in items]))


def glyph(name, *widths, auto=()):
    layers = [
        Layer(f"{name}/{m}", w, auto=m in auto)
        for m, w in zip(("Regular", "Bold"), widths)
    ]
    return Glyph(name, layers)


def facts(*rows):
    return history.auto_facts(rows)


NO_AUTOS = facts()
GUI = NS(QTransform=Transform)


@pytest.fixture(autouse=True)
def clean_log():
    LOG.clear()
    yield
    LOG.clear()


def widen(by):
    def plan(layer, master):
        return mp.make_plan(layer, 0, layer.advanceWidth + by, (str(layer.advanceWidth),))

    return plan


# ---------------------------------------------------------------- pure parts
@pytest.mark.parametrize(("value", "expected"), [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, 0), (2.4999, 2)])
def test_unit_when_half_then_rounds_up_not_to_even(value, expected):
    assert mp.unit(value) == expected


def test_make_plan_when_nothing_moves_then_not_changed():
    layer = Layer("a/Regular", 500)
    assert mp.make_plan(layer, 0, 500, ("x",)) == mp.LayerPlan(0, 500, ("x",), False)
    assert mp.make_plan(layer, 3, 500, ()).changed and mp.make_plan(layer, 0, 501, ()).changed


def test_ink_edges_when_empty_then_none_else_left_and_right():
    assert mp.ink_edges(Layer("a/Regular", 500, ink=0)) is None
    assert mp.ink_edges(Layer("a/Regular", 500, left=40, ink=120)) == (40, 160)


def test_master_layers_when_some_missing_then_only_present_masters():
    g = glyph("a", 500)
    assert list(mp.master_layers(g, ["Regular", "Bold"])) == ["Regular"]


def test_has_metrics_link_when_any_field_set_then_true():
    assert mp.has_metrics_link(Layer("a/Regular", 1, link="=b"))
    assert not mp.has_metrics_link(Layer("a/Regular", 1))


def test_survey_when_mixed_layers_then_skip_notes_in_policy_order():
    plain = glyph("a", 500, 600)
    owner = glyph("b", 500, 600, auto=("Bold",))
    linked = Glyph("c", [Layer("c/Regular", 500, link="=a")])
    entries = mp.survey([plain, owner, linked], ["Regular", "Bold"], widen(10))
    notes = [(e.glyph.name, e.master, e.note) for e in entries]
    assert notes == [
        ("a", "Regular", ""),
        ("a", "Bold", ""),
        ("b", "Regular", mp.AUTO_GLYPH_NOTE),
        ("b", "Bold", mp.AUTO_LAYER_NOTE),
        ("c", "Regular", mp.LINK_NOTE),
        ("c", "Bold", mp.MISSING_NOTE),
    ]
    assert entries[0].plan.width == 510 and entries[2].plan is None
    assert mp.auto_skipped(entries) == 2


def test_survey_when_planner_returns_text_then_listed_as_skip():
    entries = mp.survey([glyph("a", 500)], ["Regular"], lambda layer, master: "empty glyph")
    assert entries[0].plan is None and entries[0].note == "empty glyph"


def test_pending_when_no_op_and_skips_then_only_changes():
    entries = mp.survey([glyph("a", 500, 600)], ["Regular", "Bold"], widen(0))
    assert mp.pending(entries) == []
    assert len(mp.pending(mp.survey([glyph("a", 500)], ["Regular"], widen(1)))) == 1


def test_shift_and_set_when_dx_then_in_place_transform_changed_and_width():
    layer = Layer("a/Regular", 500)
    mp.shift_and_set(layer, 7, 520, qtgui=GUI)
    assert LOG == [("transform", "a/Regular", 7), ("changed", "a/Regular"), ("width", "a/Regular", 520)]


def test_shift_and_set_when_no_dx_then_width_only():
    mp.shift_and_set(Layer("a/Regular", 500), 0, 480, qtgui=GUI)
    assert LOG == [("width", "a/Regular", 480)]


def test_shift_and_set_when_update_fails_then_runtime_error_before_width():
    layer = Layer("a/Regular", 500)
    layer.update_result = False
    with pytest.raises(RuntimeError, match="could not update"):
        mp.shift_and_set(layer, 5, 520, qtgui=GUI)
    assert ("width", "a/Regular", 520) not in LOG


def test_read_back_when_width_and_edge_differ_then_one_text_each():
    layer = Layer("a/Regular", 500, left=50)
    entry = mp.Entry(glyph("a", 1), "Regular", layer, mp.LayerPlan(10, 510, (), True), "")
    assert mp.read_back(entry, (50, 150)) == [
        "a · Regular: advance 500, planned 510",
        "a · Regular: ink edge 50, planned 60",
    ]
    layer.left, layer._width = 60.4, 510
    assert mp.read_back(entry, (50, 150)) == [], "within READ_BACK_TOLERANCE"


def test_commit_when_pending_then_one_notify_with_layers_then_glyphs():
    a, b = glyph("a", 500, 600), glyph("b", 500, 600, auto=("Bold",))
    entries = mp.survey([a, b], ["Regular", "Bold"], widen(10))
    result = mp.commit("Widen", entries, facts=NO_AUTOS, native=Native(), stamp=STAMP, qtgui=GUI)
    notify = [e for e in LOG if e[0] == "notify"]
    assert notify == [("notify", "Widen", ["a/Regular", "a/Bold", "a"])]
    assert [e for e in LOG if e[0] == "init"] == [("init", "a/Regular"), ("init", "a/Bold"), ("init", "a")]
    assert result == {"pending_note": "", "layers": 2, "glyphs": 1, "auto_skipped": 2, "mismatches": [], "pending_updates": ()}


def test_commit_when_nothing_pending_then_zeros_and_no_history():
    entries = mp.survey([glyph("a", 500)], ["Regular"], widen(0))
    result = mp.commit("Widen", entries, facts=NO_AUTOS, native=Native(), stamp=STAMP, qtgui=GUI)
    assert result == {"layers": 0, "glyphs": 0, "auto_skipped": 0, "mismatches": []}
    assert LOG == []


def test_commit_when_width_not_stored_then_mismatch_reported():
    a = glyph("a", 500)
    a.layers[0].stubborn = True
    entries = mp.survey([a], ["Regular"], widen(10))
    result = mp.commit("Widen", entries, facts=NO_AUTOS, native=Native(), stamp=STAMP, qtgui=GUI)
    assert result["mismatches"] == ["a · Regular: advance 500, planned 510"]


def test_commit_when_base_of_auto_then_refused_unless_allowed():
    rows = facts(("a", False, ()), ("aacute", True, ("a",)))
    entries = mp.survey([glyph("a", 500)], ["Regular"], widen(10))
    with pytest.raises(ValueError, match="a: base of auto aacute"):
        mp.commit("Widen", entries, facts=rows, native=Native(), stamp=STAMP, qtgui=GUI)
    assert LOG == []
    mp.commit("Widen", entries, facts=rows, allow_bases=True, native=Native(), stamp=STAMP, qtgui=GUI)
    assert ("width", "a/Regular", 510) in LOG


def test_commit_when_shift_fails_then_partial_write_error_after_notify():
    a = glyph("a", 500)
    a.layers[0].update_result = False
    entries = mp.survey([a], ["Regular"], lambda layer, m: mp.make_plan(layer, 5, 500, ()))
    with pytest.raises(history.PartialWriteError, match="Edit > Undo"):
        mp.commit("Shift", entries, facts=NO_AUTOS, native=Native(), stamp=STAMP, qtgui=GUI)
    assert ("notify", "Shift", ["a/Regular", "a"]) in LOG


def test_auto_dependants_when_names_overlap_then_sorted_and_names_excluded():
    rows = facts(("a", False, ()), ("aacute", True, ("a",)), ("b", True, ("a",)), ("c", True, ("b",)))
    assert mp.auto_dependants(rows, {"a"}) == ["aacute", "b", "c"]
    assert mp.auto_dependants(rows, {"a", "b"}) == ["aacute", "c"]


def test_rebuild_note_when_many_then_limit_and_more_count():
    assert mp.rebuild_note([]) == ""
    note = mp.rebuild_note([f"g{i}" for i in range(7)])
    assert note.startswith("FontLab rebuilds auto glyphs g0, g1, g2, g3, g4 +2 more;")
    assert "Undo does not restore them" in note


def test_muted_and_make_table_when_pythonqt_given_then_configured(monkeypatch):
    qt = fake_qt()
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    assert mp.muted(Widget()) == "#96000000"
    table = mp.make_table(["Glyph", "Width"])
    assert table.args == (0, 2) and table.labels == ["Glyph", "Width"]
    assert table.min_height == 220


def test_metrics_panel_when_cold_imported_then_only_stdlib():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.metrics.panel.model
lazy = {'fontlabapp.metrics.panel.ui', 'fontlabapp.core.history.glyphs', 'fontlabapp.core.scripting'}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------- PythonQt double
class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class Consts:
    def __getattr__(self, name):
        return sum(map(ord, name)) % 997


class Color:
    HexArgb = 2

    def __init__(self, source=None):
        self.alpha = 255

    def setAlpha(self, alpha):
        self.alpha = alpha

    def name(self, *args):
        return f"#{self.alpha:02x}000000" if args else "#000000"


class Palette:
    def color(self, *args):
        return Color()

    def setColor(self, *args):
        pass


class Font:
    def pointSizeF(self):
        return 10.0

    def __getattr__(self, name):
        return lambda *a, **k: None


class Widget:
    SIGNALS = frozenset({"valueChanged", "currentIndexChanged", "toggled", "clicked", "finished", "destroyed"})

    def __init__(self, *args, **kwargs):
        self.args, self._signals, self._enabled, self._visible = args, {}, True, True
        self.labels, self.min_height = [], 0

    palette = property(lambda self: Palette())
    font = property(lambda self: Font())

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in Widget.SIGNALS:
            return self._signals.setdefault(name, Signal())
        return lambda *a, **k: None

    def setEnabled(self, flag):
        self._enabled = bool(flag)

    def isEnabled(self):
        return self._enabled

    def setVisible(self, flag):
        self._visible = bool(flag)

    def isVisible(self):
        return self._visible

    def setHorizontalHeaderLabels(self, labels):
        self.labels = list(labels)

    def setMinimumHeight(self, height):
        self.min_height = height


class Dialog(Widget):
    def closeEvent(self, event):
        LOG.append(("qt-close",))

    def deleteLater(self):
        LOG.append(("deleteLater",))


class Label(Widget):
    def __init__(self, text="", *a):
        super().__init__()
        self._text = text

    text = property(lambda self: self._text)

    def setText(self, text):
        self._text = text


class Spin(Widget):
    def __init__(self, *a):
        super().__init__()
        self._value = 0

    value = property(lambda self: self._value)

    def setValue(self, value):
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)


class Combo(Widget):
    def __init__(self, *a):
        super().__init__()
        self._index = 0

    currentIndex = property(lambda self: self._index)

    def pick(self, index):
        self._index = index
        self.currentIndexChanged.emit(index)


class Check(Widget):
    def __init__(self, *a):
        super().__init__()
        self._checked = False

    def setChecked(self, flag):
        self._checked = bool(flag)

    def isChecked(self):
        return self._checked

    def tick(self, flag):
        self._checked = flag
        self.toggled.emit(flag)


class Item:
    def __init__(self, text=""):
        self.text, self.bold = text, False

    def font(self):
        return Font()

    def setFont(self, font):
        self.bold = True

    def __getattr__(self, name):
        return lambda *a, **k: None


class Table(Widget):
    def __init__(self, *args):
        super().__init__(*args)
        self.rows, self.cells = 0, {}

    def horizontalHeader(self):
        return Widget()

    def verticalHeader(self):
        return Widget()

    def setRowCount(self, count):
        self.rows = count
        self.cells = {k: v for k, v in self.cells.items() if k[0] < count}

    def clearContents(self):
        self.cells = {}

    def setItem(self, row, column, item):
        self.cells[row, column] = item

    def texts(self, row):
        return [self.cells[row, c].text for c in sorted(c for r, c in self.cells if r == row)]


def fake_qt():
    gui = NS(
        QAction=Widget, QDialog=Dialog, QLabel=Label, QSpinBox=Spin, QComboBox=Combo, QCheckBox=Check,
        QPushButton=Widget, QTableWidget=Table, QTableWidgetItem=Item, QVBoxLayout=Widget,
        QHBoxLayout=Widget, QGridLayout=Widget, QBrush=lambda c: c, QColor=Color,
        QPalette=Consts(), QAbstractItemView=Consts(), QHeaderView=Consts(), QTransform=Transform,
    )
    core = NS(Qt=Consts(), QDateTime=NS(currentDateTimeUtc=lambda: STAMP))
    return NS(QtGui=gui, QtCore=core)


class Package:
    def __init__(self, glyphs, *, master="Regular", masters=("Regular", "Bold"), pid=5):
        self.glyphs = {g.name: g for g in glyphs}
        self.master, self.masters, self.id = master, list(masters), pid

    def findName(self, name):
        return self.glyphs.get(name)


@pytest.fixture
def panel_env(monkeypatch):
    """Load the real ``_metrics_panel`` over the PythonQt and FontLab doubles."""
    monkeypatch.setitem(sys.modules, "PythonQt", fake_qt())
    native = Native()
    monkeypatch.setitem(sys.modules, "fontlab", native)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    monkeypatch.delitem(sys.modules, "fontlabapp.metrics.panel.ui", raising=False)
    module = importlib.import_module("fontlabapp.metrics.panel.ui")
    state = NS(package=None, names=[], facts=NO_AUTOS, scans=0, native=native)

    def scan(package):
        state.scans += 1
        return state.facts

    monkeypatch.setattr(module, "current_package", lambda *a: state.package)
    monkeypatch.setattr(module, "names_selected_names", lambda: list(state.names))
    monkeypatch.setattr(module, "scan_auto_facts", scan)
    yield module, state
    sys.modules.pop("fontlabapp.metrics.panel.ui", None)


def widen_panel(module):
    class Widen(module.MetricsPanel):
        TITLE, KEY, HEADERS, ACCENT = "Widen", "test_widen", ("Width", "New"), (2,)

        def build(self):
            self.step = self.spin(0, 100, 10)
            self.form.addWidget(self.step, 1, 1)

        def subtitle_hint(self):
            return f"Widens by {self.step.value}."

        def planner(self, package, glyphs):
            by = self.step.value
            return lambda layer, master: mp.make_plan(
                layer, 0, layer.advanceWidth + by, (f"{layer.advanceWidth:g}", str(layer.advanceWidth + by))
            )

    return Widen


def test_panel_type_when_called_then_metrics_panel_class(panel_env):
    module, _ = panel_env
    assert mp.panel_type() is module.MetricsPanel


def test_panel_when_no_font_then_reason_shown_and_apply_disabled(panel_env):
    module, _ = panel_env
    panel = widen_panel(module)()
    assert panel.subtitle.text == "Open a font and select glyphs. Then run this script again."
    assert not panel.apply_button.isEnabled()


def test_panel_when_hooks_missing_then_not_implemented(panel_env):
    module, _ = panel_env
    base = module.MetricsPanel.__new__(module.MetricsPanel)
    for hook in ("build", "subtitle_hint"):
        with pytest.raises(NotImplementedError):
            getattr(module.MetricsPanel, hook)(base)
    with pytest.raises(NotImplementedError):
        module.MetricsPanel.planner(base, None, [])


def test_panel_when_selection_then_preview_rows_and_status(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500, 600), glyph("b", 400)]), ["a", "b"]
    panel = widen_panel(module)()
    assert panel.table.texts(0) == ["a · Regular", "500", "510"]
    assert panel.table.texts(1) == ["b · Regular", "400", "410"]
    assert panel.status.text == "2 layers will change" and panel.apply_button.isEnabled()
    assert panel.subtitle.text == "Widens by 10. (a, b)"
    panel.scope.pick(1)
    assert panel.status.text == "3 layers will change"
    assert panel.table.texts(3) == ["b · Bold", mp.MISSING_NOTE]


def test_panel_when_plan_shrinks_to_skip_note_row_then_no_stale_cells(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500, 600)]), ["a"]
    panel = widen_panel(module)()
    assert len(panel.table.texts(0)) == 3
    panel.entries = [mp.Entry(glyph("a", 500), "Regular", None, None, mp.MISSING_NOTE)]
    panel.fill_table()
    assert panel.table.texts(0) == ["a · Regular", mp.MISSING_NOTE], "a reused row keeps no cells from the earlier plan"


def test_panel_when_apply_then_one_undo_step_and_result_status(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500, 600)]), ["a"]
    panel = widen_panel(module)()
    LOG.clear()
    panel.apply_button.clicked.emit(False)
    assert [e for e in LOG if e[0] == "notify"] == [("notify", "Widen", ["a/Regular", "a"])]
    assert panel.last_result["layers"] == 1
    assert panel.status.text.startswith("Changed 1 layer in 1 glyph")
    assert panel.status.text.endswith("after Edit > Undo/Redo press Refresh to update the plan")


def test_panel_when_apply_changes_many_then_status_uses_plurals(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500, 600), glyph("b", 500, 600)]), ["a", "b"]
    panel = widen_panel(module)()
    panel.apply_button.clicked.emit(False)
    assert panel.status.text.startswith("Changed 2 layers in 2 glyphs"), panel.status.text


def test_panel_when_apply_skips_auto_layers_then_status_counts_layers_skipped_auto(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500, 600)]), ["a"]
    panel = widen_panel(module)()
    module.commit = lambda *a, **k: {"layers": 1, "glyphs": 1, "auto_skipped": 3, "mismatches": []}
    panel.apply_button.clicked.emit(False)
    assert "3 layers skipped (auto)" in panel.status.text, panel.status.text
    assert "auto layers skipped" not in panel.status.text


def test_panel_when_apply_skips_one_auto_layer_then_status_uses_singular(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500, 600)]), ["a"]
    panel = widen_panel(module)()
    module.commit = lambda *a, **k: {"layers": 1, "glyphs": 1, "auto_skipped": 1, "mismatches": []}
    panel.apply_button.clicked.emit(False)
    assert "1 layer skipped (auto)" in panel.status.text, panel.status.text
    assert "1 layers skipped" not in panel.status.text


def test_panel_when_base_of_auto_then_apply_blocked_until_tick_for_same_glyphs(panel_env):
    module, state = panel_env
    state.package = Package([glyph("a", 500), glyph("b", 400)])
    state.names = ["a"]
    state.facts = facts(("a", False, ()), ("aacute", True, ("a",)))
    panel = widen_panel(module)()
    assert panel.allow_auto.isVisible() and not panel.apply_button.isEnabled()
    assert panel.status.text.startswith("Refused. FontLab rebuilds auto glyphs aacute")
    panel.allow_auto.tick(True)
    assert panel.apply_button.isEnabled()
    state.names = ["a", "b"]
    panel.selection_button.clicked.emit(False)
    assert not panel.allow_auto.isChecked(), "the tick belonged to another set of glyphs"
    assert not panel.apply_button.isEnabled()
    panel.allow_auto.tick(True)
    LOG.clear()
    panel.apply_button.clicked.emit(False)
    assert ("notify", "Widen", ["a/Regular", "b/Regular", "a", "b"]) in LOG


def test_panel_when_apply_refused_by_fresh_facts_then_nothing_written(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500)]), ["a"]
    panel = widen_panel(module)()
    state.facts = facts(("a", False, ()), ("aacute", True, ("a",)))
    panel._rebuild_cache = {}
    LOG.clear()
    panel.apply_button.clicked.emit(False)
    assert not [e for e in LOG if e[0] in ("init", "notify")]
    assert panel.status.text.startswith("Refused.")


def test_panel_when_font_switched_then_apply_refused(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500)]), ["a"]
    panel = widen_panel(module)()
    state.package = Package([glyph("a", 500)], pid=99)
    LOG.clear()
    panel.apply_button.clicked.emit(False)
    assert panel.status.text == "The font changed. Run this script again."
    assert LOG == []


def test_panel_when_glyph_owns_auto_layer_then_listed_and_skipped(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500, 600, auto=("Bold",))]), ["a"]
    panel = widen_panel(module)()
    assert panel.table.texts(0) == ["a · Regular", mp.AUTO_GLYPH_NOTE]
    assert panel.status.text == "Nothing to change" and not panel.apply_button.isEnabled()


def test_panel_when_closed_then_signals_disconnected_and_deleted(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500)]), ["a"]
    panel = widen_panel(module)()
    assert panel.apply_button.clicked.slots
    LOG.clear()
    panel.closeEvent(NS())
    assert panel.apply_button.clicked.slots == [] and panel._connections == []
    assert LOG == [("qt-close",), ("deleteLater",)]


def test_metrics_panel_class_when_parsed_then_every_method_documented():
    import ast

    source = _module_file("_metrics_panel").read_text(encoding="utf-8")
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
    assert cls.name == "MetricsPanel" and ast.get_docstring(cls)
    missing = [f.name for f in cls.body if isinstance(f, ast.FunctionDef) and not ast.get_docstring(f)]
    assert not missing, missing


@pytest.mark.parametrize("reverse", [False, True])
def test_survey_when_base_and_manual_composite_then_composite_skipped(reverse):
    base = Glyph("n", [Layer("n/L", 500)])
    composite = Glyph("ntilde", [Layer("ntilde/L", 500)])
    composite.layers[0].shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="n"))]
    glyphs = [base, composite] if not reverse else [composite, base]
    rows = mp.survey(glyphs, ["L"], lambda l, m: mp.make_plan(l, 20, 500, ()))
    row = next(r for r in rows if r.glyph is composite)
    assert row.plan is None
    assert row.note == "ntilde: skipped; its base n moves in this step"
    assert len(mp.pending(rows)) == 1


def test_survey_when_manual_composite_alone_then_planned():
    composite = Glyph("ntilde", [Layer("ntilde/L", 500)])
    composite.layers[0].shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="n"))]
    rows = mp.survey([composite], ["L"], lambda l, m: mp.make_plan(l, 20, 500, ()))
    assert len(mp.pending(rows)) == 1 and rows[0].note == ""


def test_survey_when_base_only_changes_width_then_composite_still_planned():
    base = Glyph("n", [Layer("n/L", 500)])
    composite = Glyph("ntilde", [Layer("ntilde/L", 500)])
    composite.layers[0].shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="n"))]
    rows = mp.survey([base, composite], ["L"], lambda l, m: mp.make_plan(l, 0, 600, ()))
    assert len(mp.pending(rows)) == 2


@pytest.mark.parametrize("reverse", [False, True])
def test_survey_when_unselected_intermediate_base_then_transitive_user_skipped(reverse):
    base = Glyph("a", [Layer("a/L", 500)])
    composite = Glyph("aacute.sc", [Layer("aacute.sc/L", 500)])
    composite.layers[0].shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="aacute"))]
    component_facts = facts(("aacute", False, ("a",)), ("aacute.sc", False, ("aacute",)))
    glyphs = [base, composite] if not reverse else [composite, base]
    rows = mp.survey(glyphs, ["L"], lambda l, m: mp.make_plan(l, 20, 500, ()), facts=component_facts)
    row = next(r for r in rows if r.glyph is composite)
    assert row.plan is None and row.note == "aacute.sc: skipped; its base a moves in this step"
    assert len(mp.pending(rows)) == 1


def test_survey_when_dependency_cycle_then_terminates_without_skipping_its_own_base():
    base = Glyph("a", [Layer("a/L", 500)])
    component_facts = facts(("aacute", False, ("a",)), ("a", False, ("aacute",)))
    rows = mp.survey([base], ["L"], lambda l, m: mp.make_plan(l, 20, 500, ()), facts=component_facts)
    assert len(mp.pending(rows)) == 1


def test_metrics_panel_when_transitive_user_selected_then_existing_facts_drive_preview(panel_env):
    module, state = panel_env
    base, composite = glyph("a", 500), glyph("aacute.sc", 500)
    composite.layers[0].shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="aacute"))]
    state.package, state.names = Package([base, composite]), ["a", "aacute.sc"]
    state.facts = facts(("aacute", False, ("a",)), ("aacute.sc", False, ("aacute",)))
    panel = widen_panel(module)()
    # Widen changes only width; use a moving planner and refresh without rescanning.
    panel.planner = lambda package, glyphs: lambda layer, master: mp.make_plan(layer, 20, 500, ())
    scans = state.scans
    panel.refresh()
    row = next(r for r in panel.entries if r.glyph is composite)
    assert row.plan is None and "base a moves" in row.note
    assert state.scans == scans, "reuse component facts across preview controls"


@pytest.mark.parametrize("action", ["actionUndo", "actionRedo"])
def test_panel_when_history_then_refreshes_captured_target_and_facts(panel_env, action):
    module, state = panel_env
    state.native.actions = {name: NS(triggered=Signal()) for name in ("actionUndo", "actionRedo")}
    a, b = glyph("a", 500, 600), glyph("b", 300, 400)
    state.package, state.names = Package([a, b]), ["a"]
    panel = widen_panel(module)()
    panel.step.setValue(25)
    state.names, state.package.master = ["b"], "Bold"
    a.layers[0]._width = 450
    state.facts = facts(("a", False, ()), ("aacute", True, ("a",)))
    state.native.actions[action].triggered.emit(False)
    assert panel.names == ["a"] and panel.package_id == 5 and panel.step.value == 25
    assert panel.table.texts(0) == ["a · Regular", "450", "475"]
    assert panel._facts is state.facts and state.scans == 2
    assert "aacute" in panel.status.text and not panel.apply_button.isEnabled()
    panel.allow_auto.tick(True)
    state.facts = NO_AUTOS
    state.native.actions[action].triggered.emit(False)
    assert panel.apply_button.isEnabled() and not panel.allow_auto.isChecked()
    panel.scope.pick(1)
    assert [entry.master for entry in panel.entries] == ["Regular", "Bold"]
    panel.selection_button.clicked.emit(False)
    panel.scope.pick(0)
    assert panel.names == ["b"] and panel.entries[0].master == "Bold"
    callbacks = [slot for signal, slot in panel._connections if signal is state.native.actions[action].triggered]
    panel.closeEvent(NS())
    assert not state.native.actions[action].triggered.slots
    scans = state.scans
    callbacks[0]()
    assert state.scans == scans, "a queued history callback must not read a closed panel"


@pytest.mark.parametrize("missing", ["font", "different font", "glyph", "master"])
def test_panel_when_refresh_target_missing_then_refuses_without_recapture(panel_env, missing):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500), glyph("b", 300)]), ["a", "b"]
    panel = widen_panel(module)()
    state.names = ["other"]
    if missing == "font":
        state.package = None
    elif missing == "different font":
        state.package = Package([glyph("a", 500)], pid=99)
    elif missing == "glyph":
        del state.package.glyphs["a"]
    else:
        state.package.masters = ["Bold"]
    panel.refresh_button.clicked.emit(False)
    assert not panel.apply_button.isEnabled() and panel.entries == []
    assert panel.names == ["a", "b"] and panel.package_id == 5
    assert panel.subtitle.text


def test_panel_when_history_connection_refused_then_manual_refresh_still_works(panel_env):
    module, state = panel_env
    state.package, state.names = Package([glyph("a", 500)]), ["a"]
    state.native.actions = {"actionUndo": NS(triggered=NS(connect=lambda slot: False))}
    panel = widen_panel(module)()
    assert "Automatic Undo/Redo refresh unavailable" in panel.status.text
    state.package.glyphs["a"].layers[0]._width = 420
    panel.refresh_button.clicked.emit(False)
    assert panel.table.texts(0) == ["a · Regular", "420", "430"]
    assert panel.apply_button.isEnabled() and state.scans == 2


def test_panel_when_real_qt_history_then_preserves_uncommitted_settings_and_disconnects(monkeypatch):
    from _feature_source_qt import owned_application, qt_namespace
    from PySide6 import QtCore, QtGui, QtWidgets

    qt = qt_namespace()

    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(qt.QtGui.QLabel):
        font = property(QtWidgets.QLabel.font)

    class Item(QtWidgets.QTableWidgetItem):
        def setTextAlignment(self, alignment):
            super().setTextAlignment(QtCore.Qt.AlignmentFlag(alignment))

    qt.QtGui.QDialog, qt.QtGui.QLabel, qt.QtGui.QTableWidgetItem = Dialog, Label, Item
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.delitem(sys.modules, "fontlabapp.metrics.panel.ui", raising=False)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.lifecycle", raising=False)
    module = importlib.import_module("fontlabapp.metrics.panel.ui")
    native = Native()
    monkeypatch.setitem(sys.modules, "fontlab", native)
    target = Package([glyph("a", 500, 600), glyph("b", 300, 400)])
    state = NS(facts=NO_AUTOS, scans=0)

    def scan(package):
        state.scans += 1
        return state.facts

    monkeypatch.setattr(module, "current_package", lambda: target)
    monkeypatch.setattr(module, "names_selected_names", lambda: ["a"])
    monkeypatch.setattr(module, "scan_auto_facts", scan)
    with owned_application() as app:
        native.actions = {name: QtGui.QAction(name) for name in ("actionUndo", "actionRedo")}
        # The host's own history handler is connected before the follower.
        native.actions["actionUndo"].triggered.connect(lambda: setattr(target.glyphs["a"].layers[0], "_width", 450))
        native.actions["actionRedo"].triggered.connect(lambda: setattr(target.glyphs["a"].layers[0], "_width", 500))
        panel = widen_panel(module)()
        try:
            panel.step.setKeyboardTracking(False)
            panel.step.lineEdit().setText("27")
            target.master = "Bold"
            monkeypatch.setattr(module, "names_selected_names", lambda: ["b"])
            native.actions["actionUndo"].trigger()
            assert panel.table.item(0, 0).text() == "a · Regular"
            assert panel.table.item(0, 1).text() == "450"
            assert panel.step.lineEdit().text() == "27" and panel.step.value == 10
            state.facts = facts(("a", False, ()), ("aacute", True, ("a",)))
            native.actions["actionRedo"].trigger()
            assert panel.table.item(0, 1).text() == "500"
            assert not panel.apply_button.isEnabled() and panel.allow_auto.isVisibleTo(panel)
            panel.allow_auto.setChecked(True)
            assert panel.apply_button.isEnabled()
            assert "press Use selection" not in panel.status.text
        finally:
            panel.close()
            app.processEvents()
        assert not panel._connections
        scans = state.scans
        native.actions["actionUndo"].trigger()
        assert state.scans == scans
    sys.modules.pop("fontlabapp.metrics.panel.ui", None)
