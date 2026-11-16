# this_file: tests/test_studio_vertical_metrics.py
"""Vertical Metrics & Zones (A12): parity with the 8 Scriptmix scripts, dry runs and one labelled Undo step.

The app writes master and font-info values, not glyph layers, so each Apply
goes through the original's route-A writer with the app label; the tests
record that one writer call (label, masters, fields) and check that
``AppShell.history`` is never called. Read-only parts (Diagram, Nodes Near
Zones, Reporter) are checked to call no writer and set no font attribute.
Ported functions are compared with the Scriptmix originals by AST.
"""

from _demo_support import stub_natives

import ast
import importlib
import inspect
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture
from _vertical_metrics_originals import ORIGINALS

PKG = "fontlabapp.studios.vertical_metrics"
FIELDS8 = [
    "openTypeOS2TypoAscender",
    "openTypeOS2TypoDescender",
    "openTypeOS2TypoLineGap",
    "openTypeHheaAscender",
    "openTypeHheaDescender",
    "openTypeHheaLineGap",
    "openTypeOS2WinAscent",
    "openTypeOS2WinDescent",
]


def _forget_studio_children():
    import fontlabapp.studios as studios

    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)
        studios.__dict__.pop(name.split(".")[2], None)


@pytest.fixture(autouse=True)
def fresh_studios():
    _forget_studio_children()
    yield
    _forget_studio_children()


# Fakes ---------------------------------------------------------------------------
class Box:
    def __init__(self, low, high):
        self.low, self.high = low, high

    def y(self):
        return self.low

    def height(self):
        return self.high - self.low

    def width(self):
        return 0 if self.high == self.low else 500


class Node:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def isOn(self):  # noqa: N802 - FontLab name
        return True


class Contour:
    def __init__(self, points):
        self.points = points

    def nodes(self):
        return [Node(x, y) for x, y in self.points]

    def path(self):
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.moveTo(*self.points[0])
        for point in self.points[1:]:
            path.lineTo(*point)
        path.closeSubpath()
        return path


class Shape:
    def __init__(self, points, component=None):
        from PySide6.QtGui import QTransform

        self.contour = Contour(points)
        self.transform = QTransform()
        self.shapeData = NS(componentGlyph=component) if component else None

    def getContours(self):  # noqa: N802 - FontLab name
        return [self.contour]


class Layer:
    def __init__(self, low, high, *, points=None, null=False):
        self.boundingBox = Box(low, high)
        self.span = (low, high) if high != low else None
        self.isNull = null
        self.advanceWidth = 500
        pts = (
            points
            if points is not None
            else [(0, low), (400, low), (400, high), (0, high)]
        )
        self.shapes = [Shape(pts)] if high != low else []


class Glyph:
    def __init__(self, name, layers):
        self.name, self.layers, self.isNull = name, layers, False

    def findLayer(self, master):  # noqa: N802 - FontLab name
        return self.layers.get(master)


def glyph_set():
    """H, O, x, o, b and p in two masters; O/o overshoot by 12/10, Bold H has a node 3 units above 700."""

    def two(low, high, **kw):
        return {"Regular": Layer(low, high, **kw), "Bold": Layer(low, high, **kw)}

    glyphs = {
        "H": two(0, 700),
        "O": two(-12, 712),
        "x": two(0, 500),
        "o": two(-10, 510),
        "b": two(0, 760),
        "p": two(-240, 500),
        "space": two(0, 0),
    }
    glyphs["H"]["Bold"] = Layer(0, 703, points=[(0, 0), (400, 0), (400, 703), (0, 700)])
    return {name: Glyph(name, layers) for name, layers in glyphs.items()}


class Package:
    """Two masters; per-master metric values and font info; every font attribute write is logged."""

    def __init__(self, log):
        d = object.__setattr__
        d(self, "log", log)
        d(self, "id", 7)
        d(self, "masters", ["Regular", "Bold"])
        d(self, "master", "Regular")
        d(self, "values", {
            "Regular": {"ascender_value": 750.0, "descender_value": -250.0, "xHeight_value": 500.0,
                        "capsHeight_value": 700.0, "lineGap_value": 0.0},
            "Bold": {"ascender_value": 760.0, "descender_value": -240.0, "xHeight_value": 510.0,
                     "capsHeight_value": 710.0, "lineGap_value": 0.0},
        })  # fmt: skip
        d(
            self,
            "font_info",
            {m: dict.fromkeys(FIELDS8, 0) for m in ("Regular", "Bold")},
        )
        d(self, "glyphs", glyph_set())
        d(self, "zones", {})
        d(self, "angles", {"Regular": 0.0, "Bold": -12.0})

    def __getattr__(self, name):
        if name.endswith("_value"):
            return self.values[self.master][name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        self.log.append(("set", name, value))
        object.__setattr__(self, name, value)

    def setMaster(self, master, notify=True):  # noqa: N802 - FontLab name
        object.__setattr__(self, "master", master)

    @property
    def info(self):
        return NS(**self.font_info[self.master])

    def findName(self, name):  # noqa: N802 - FontLab name
        return self.glyphs.get(name)


def zone_data():
    from fontlabapp.metrics.zones import data

    return data


def initial_zones(pkg):
    d = zone_data()
    origin = d.Origin("x-height", b"tags-and-lock")
    for master in pkg.masters:
        pkg.zones[master] = d.Zones(top=(d.Zone(500.0, 8.0, "x-height", origin),),
                                    bottom=(d.Zone(0.0, 12.0, "baseline"),))  # fmt: skip


class ZoneNative:
    """``metrics.zones.native`` as the Zones tab calls it; ``apply`` writes the fake package."""

    class RowRefusal(ValueError):
        pass

    def __init__(self, pkg, writes):
        self.pkg, self.writes, self.fail = pkg, writes, None

    def capture(self, package_id):
        d = zone_data()
        assert package_id == self.pkg.id
        return d.Snapshot(self.pkg.id, "Regular", tuple(
            d.Master(m, self.pkg.values[m]["xHeight_value"], self.pkg.values[m]["capsHeight_value"], self.pkg.zones[m])
            for m in self.pkg.masters))  # fmt: skip

    def bounds(self, snapshot, master):
        return (-10.0, 520.0), (-12.0, 724.0)

    def backend(self, package_id, *, title):
        return NS(apply=lambda before, changes: self.apply(before, changes, title))

    def apply(self, before, changes, title):
        if self.fail is not None:
            raise self.fail
        self.writes.append(
            ("zones", title, [c.master for c in changes], [c.after for c in changes])
        )
        for change in changes:
            self.pkg.zones[change.master] = change.after
        return self.capture(self.pkg.id)


class Angles:
    MIN_ANGLE, MAX_ANGLE = -45.0, 45.0

    def __init__(self, pkg, writes):
        self.pkg, self.writes = pkg, writes

    def capture(self, package):
        return NS(
            package_id=package.id,
            current_master="Regular",
            angles=tuple(self.pkg.angles.items()),
        )

    def apply(self, snapshot, proposed, *, undo_name):
        if snapshot != self.capture(self.pkg):
            raise ValueError("Source angles or masters changed; refresh this tool.")
        changed = [m for m, old in snapshot.angles if proposed[m] != old]
        self.writes.append(("angles", undo_name, {m: proposed[m] for m in changed}))
        self.pkg.angles.update({m: proposed[m] for m in changed})
        return changed


def fake_backends(pkg, writes):
    from fontlabapp.core.history import masters as font_history
    from fontlabapp.metrics import master_writer
    from fontlabapp.metrics.zones import editor, model, rows

    def write_master_metrics(package, request, title):
        writes.append(("master metrics", title, request))
        for master, fields in request.items():
            for field, value in fields.items():
                pkg.values[master][
                    master_writer.FIELDS[master_writer.ALIASES.get(field, field)]
                ] = value
        return NS(pending_updates=0, pending_note="")

    history = NS(require_font_window=lambda package: writes.append(("font window", package.id)) and None,
                 RolledBackError=font_history.RolledBackError, THREAD_TEXT=font_history.THREAD_TEXT,
                 WINDOW_TEXT=font_history.WINDOW_TEXT)  # fmt: skip
    reports = NS(fonts=2, rows=[("A", "Regular"), ("B", "Regular"), ("B", "Bold")])
    return NS(
        master_metrics=NS(FIELDS=master_writer.FIELDS, ALIASES=master_writer.ALIASES,
                          write_master_metrics=write_master_metrics),
        font_history=history,
        zones=model, zone_rows=rows, zone_data=zone_data(), zone_editor=editor,
        zone_native=ZoneNative(pkg, writes),
        extent=NS(vertical_extent=lambda layer: layer.span),
        angles=Angles(pkg, writes),
        reporter=NS(native=NS(capture=lambda: reports), model=NS(render=lambda report: "typoAscender 750 …")),
        panel=NS(muted=lambda widget: "#888888"),
    )  # fmt: skip


class Recorder:
    """Stands in for ``AppShell.history``: this app must never call it."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return lambda *args: self.calls.append((name, *args))

    class Gauge(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.angles, self.masters = None, []

        def set_angles(self, angles):
            self.angles = list(angles)

    def open_app(selection=("H", "O"), zones=True):
        log, writes = [], []
        pkg = Package(log)
        if zones:
            initial_zones(pkg)
        found = fake_backends(pkg, writes)
        legacy = [NS(name=n) for n in pkg.glyphs]
        selected = {i for i, g in enumerate(legacy) if g.name in selection}
        fontlab = NS(FontMetrics=lambda package, master: NS(**{k[:-6]: v for k, v in pkg.values[master].items()}),
                     CurrentFont=lambda: NS(glyphs=legacy))  # fmt: skip
        monkeypatch.setitem(sys.modules, "fontlab", fontlab)
        monkeypatch.setitem(
            sys.modules, "FL", NS(fl=NS(font=legacy, Selected=lambda i: i in selected))
        )
        for g in pkg.glyphs.values():
            g.fgGlyph = NS(unicodes=[ord(g.name)] if len(g.name) == 1 else [])
        shared = importlib.import_module(f"{PKG}._shared")
        monkeypatch.setattr(shared, "backends", lambda: found)
        calculate = importlib.import_module(f"{PKG}.calculate")
        monkeypatch.setattr(calculate, "current_package", lambda expected=None: pkg)
        info = []

        def write_font_info(package, changes, *, undo_name):
            info.append((undo_name, list(changes)))
            writes.append(
                ("font info", undo_name, [(m, k, v) for m, k, _old, v in changes])
            )
            for master, key, _old, value in changes:
                pkg.font_info[master][key] = value
            return {"changed": sum(1 for c in changes if c[2] != c[3])}

        monkeypatch.setattr(calculate, "write_font_info", write_font_info)
        diagram = importlib.import_module(f"{PKG}.diagram")
        chosen = []
        monkeypatch.setattr(diagram, "current_package", lambda expected=None: pkg)
        monkeypatch.setattr(
            diagram,
            "select_glyphs",
            lambda names, package_id: chosen.append((names, package_id)) or names,
        )
        angle = importlib.import_module(f"{PKG}.angle")
        monkeypatch.setattr(angle, "vertical_metrics_views", lambda: NS(Gauge=Gauge))
        _kerning = importlib.import_module("fontlabapp.studios._kerning")
        monkeypatch.setattr(_kerning, "names_selected_names", lambda: list(selection))
        studio = importlib.import_module(PKG)
        # Patch the Tool class the shell really builds (another test may have loaded a second _kerning copy).
        tool_type = importlib.import_module("fontlabapp.studios._kerning_app").Tool
        monkeypatch.setattr(sys.modules[tool_type.__module__], "names_selected_names", lambda: list(selection))
        preview = QtPreview()
        shell = studio.show(
            package=lambda: pkg,
            font=lambda: "font",
            preview=lambda shell, tool: preview,
        )
        studio_qt.owned.append(shell)
        recorder = Recorder()
        shell.history = recorder
        tool = shell.kerning_tool
        panels = {
            title: view.__self__
            for title, view in zip(studio.TAB_TITLES, tool.views, strict=True)
        }
        return NS(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio, log=log,
                  writes=writes, history=recorder, found=found, selected=chosen, info=info)  # fmt: skip

    return open_app


def table_rows(table):
    return [
        tuple(table.cell(r, c) for c in range(table.view.columnCount()))
        for r in range(table.count())
    ]


def font_writes(app):
    """Font attribute writes other than switching the master (reads restore it with setMaster)."""
    return [entry for entry in app.log if entry[1] != "master"]


# Shell, registry, lazy loading ---------------------------------------------------------
def test_show_when_opened_then_five_tabs_tmetrics_preview_and_masters(opened):
    app = opened()
    assert [app.shell.tabs.tabText(i) for i in range(app.shell.tabs.count())] == [
        "Metrics table", "Calculate", "Zones", "Italic angle", "Diagram", "About"]  # fmt: skip
    assert (
        app.shell.preview is app.preview
        and ("set_layer", "Regular") in app.preview.calls
    )
    assert app.tool.app == "Vertical Metrics & Zones" and app.tool.masters == [
        "Regular",
        "Bold",
    ]
    assert app.writes == [] and font_writes(app) == [] and app.history.calls == []


def test_registry_when_imported_then_lazy_and_shared_tool():
    from fontlabapp import studios
    import fontlabapp.studios.vertical_metrics as vm

    assert vm.register_tabs() == vm.TAB_TITLES == vm.register_tabs()
    assert [s.title for s in studios.tabs(vm.APP)] == list(vm.TAB_TITLES)
    shell = NS()
    assert vm.tool_for(shell) is vm.tool_for(shell) and vm.tool_for(shell).app == vm.APP
    assert not any(
        n.endswith(("zones", "angle", "diagram"))
        for n in sys.modules
        if n.startswith("fontlabapp.studios.")
    )


def test_backends_when_loaded_then_reuse_the_route_a_writers():
    from fontlabapp.core import scripting

    found = scripting.vertical_metrics_backends()
    assert (
        found.master_metrics.write_master_metrics
        and found.font_history.require_font_window
    )
    assert (
        found.zone_native.backend and found.zone_native.capture and found.zones.Editor
    )
    assert (
        found.angles.apply
        and found.reporter.native.capture
        and found.reporter.model.render
    )
    assert found.extent.vertical_extent and found.panel.muted and found.zone_data.Zones


def test_views_helper_when_called_then_angle_gauge_module(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.core import scripting

    monkeypatch.delitem(sys.modules, "fontlabapp.masters.angles.views", raising=False)
    assert scripting.vertical_metrics_views().Gauge
    sys.modules.pop("fontlabapp.masters.angles.views", None)


def test_label_when_built_then_app_prefix_and_unique_masters(studio_qt):  # noqa: F811
    from fontlabapp.studios.vertical_metrics import _shared

    assert (
        _shared.label("set zones", ["Bold", "Regular", "Bold"])
        == "Vertical Metrics: set zones of Bold, Regular"
    )
    assert (
        _shared.plural(1, "zone") == "1 zone" and _shared.plural(2, "zone") == "2 zones"
    )


def test_native_module_when_dunder_then_attribute_error(studio_qt):  # noqa: F811
    from fontlabapp.studios.vertical_metrics import _shared, zones

    with pytest.raises(AttributeError):
        _shared.fontlab.__wrapped__  # noqa: B018
    with pytest.raises(AttributeError):
        zones.outline_extent.__wrapped__  # noqa: B018


# Parity -------------------------------------------------------------------------------
def _definitions(source, names):
    tree = ast.parse(source)
    kinds = (ast.FunctionDef, ast.ClassDef)
    return [ast.dump(n) for n in tree.body if isinstance(n, kinds) and n.name in names]


PORTS = {
    "Calculate Vertical Metrics": "calculate",
    "Master Metrics Table": "table",
    "Suggest Zones From Overshoots": "zones",
    "Vertical Metrics Diagram": "diagram",
    "Nodes Near Zones": "diagram",
}


@pytest.mark.parametrize("title", sorted(PORTS))
def test_ported_code_when_compared_then_ast_equal_to_scriptmix(studio_qt, title):  # noqa: F811
    module = importlib.import_module(f"{PKG}.{PORTS[title]}")
    path, digest, names, source = ORIGINALS[title]
    assert len(digest) == 64 and path.startswith("Scripts/") and names
    ported = "\n\n".join(inspect.getsource(getattr(module, n)) for n in names)
    assert _definitions(ported, names) == _definitions(source, names), title


def test_originals_when_listed_then_all_eight_a12_scripts_are_pinned():
    assert sorted(ORIGINALS) == sorted(
        [*PORTS, "Italic Angle", "Alignment Zones", "Vertical Metrics Reporter"]
    )


def test_constants_when_compared_then_scriptmix_options_and_defaults(studio_qt):  # noqa: F811
    calculate = importlib.import_module(f"{PKG}.calculate")
    zones = importlib.import_module(f"{PKG}.zones")
    diagram = importlib.import_module(f"{PKG}.diagram")
    table = importlib.import_module(f"{PKG}.table")
    assert calculate.METRIC_FIELDS == FIELDS8 and [g[1] for g in calculate.GROUPS] == [
        FIELDS8[:3],
        FIELDS8[3:6],
        FIELDS8[6:],
    ]
    assert zones.GLYPHS == ("H", "O", "x", "o") and [r[0] for r in zones.RULES] == [
        "baseline",
        "x-height",
        "caps",
    ]
    assert diagram.TOLERANCE == (1, 30, 4) and diagram.SAMPLE == ("H", "x", "b", "p")
    assert table.MASTER_FIELDS == ["ascender", "descender", "xHeight", "capHeight"]


# Metrics table --------------------------------------------------------------------------
def test_metrics_table_when_edited_then_dry_run_and_one_labelled_write(opened):
    app = opened()
    panel = app.panels["Metrics table"]
    assert table_rows(panel.grid) == [
        ("Regular", "750", "-250", "500", "700"),
        ("Bold", "760", "-240", "510", "710"),
    ]
    assert not panel.apply_button.isEnabled()
    panel.grid.set_cell(1, 4, "720")
    assert table_rows(panel.dry) == [("Bold · Cap height", "710", "720")]
    assert panel.changes == [("Bold", "capHeight", 710.0, 720.0)]
    panel.apply_button.click()
    assert app.writes == [("font window", 7), ("master metrics", "Vertical Metrics: set metrics of Bold",
                                                 {"Bold": {"capHeight": 720.0}})]  # fmt: skip
    assert (
        app.pkg.values["Bold"]["capsHeight_value"] == 720.0 and app.history.calls == []
    )
    assert app.tool.status.startswith(
        "Vertical Metrics: set metrics of Bold. Changed 1 metric field"
    )
    assert table_rows(panel.dry) == []


def test_metrics_table_when_invalid_or_stale_then_refused_and_nothing_written(opened):
    app = opened()
    panel = app.panels["Metrics table"]
    panel.grid.set_cell(0, 3, "900")  # x-height above cap height
    assert (
        "Expected descender ≤ 0 ≤ x-height ≤ cap-height ≤ ascender." in app.tool.status
    )
    assert table_rows(panel.grid)[0][0] == "Regular" and panel.changes == []
    panel.grid.set_cell(0, 3, "abc")
    assert "Regular: enter numbers only." in app.tool.status
    panel.grid.set_cell(0, 3, "490")
    app.pkg.values["Regular"]["xHeight_value"] = 480.0  # changed under the tool
    panel.apply_button.click()
    assert "Regular xHeight changed since preview; refresh the tool." in app.tool.status
    assert [w for w in app.writes if w[0] == "master metrics"] == []


def test_metrics_table_when_row_selected_then_preview_shows_master(opened):
    app = opened()
    panel = app.panels["Metrics table"]
    panel.grid.select(1)
    assert app.preview.calls[-1] == ("set_layer", "Bold")


def test_metrics_table_when_nothing_to_change_or_no_font_then_refused(opened):
    app = opened()
    panel = app.panels["Metrics table"]
    panel.run(panel.apply)
    assert "Nothing to change." in app.tool.status
    table = importlib.import_module(f"{PKG}.table")
    assert table.write_changes(app.pkg, [("Bold", "ascender", 760.0, 760.0)], "t") == {
        "changed": 0
    }
    app.shell.package = lambda: None
    app.tool.reload()
    assert panel.grid.count() == 0 and panel.subtitle.text() == "Open a font first."
    panel.clear()
    assert panel.values == []


# Calculate and Reporter -----------------------------------------------------------------
def test_calculate_when_opened_then_typo_off_hhea_win_on_current_master(opened):
    app = opened()
    panel = app.panels["Calculate"]
    assert [c.isChecked() for c in panel.group_checks] == [False, True, True]
    assert (
        panel.scope.currentIndex() == 0
        and panel.padding.value() == 0
        and panel.gap.value() == 0
    )
    assert panel.bounds == {"Regular": (-240, 760, 6), "Bold": (-240, 760, 6)}
    assert [r[0] for r in table_rows(panel.grid)] == [
        "Regular · hhea ascender", "Regular · hhea descender", "Regular · hhea line gap",
        "Regular · Win ascent", "Regular · Win descent"]  # fmt: skip
    assert [r[2] for r in table_rows(panel.grid)] == ["760", "-240", "0", "760", "240"]


def test_calculate_when_all_masters_padding_and_typo_then_one_labelled_font_info_write(
    opened,
):
    app = opened()
    panel = app.panels["Calculate"]
    panel.scope.setCurrentIndex(1)
    panel.padding.setValue(10)
    panel.group_checks[0].setChecked(True)
    assert len(panel.plan) == 16 and panel.plan[0] == (
        "Regular",
        "openTypeOS2TypoAscender",
        0,
        770,
    )
    panel.apply_button.click()
    label, plan = app.info[0]
    assert (
        label == "Vertical Metrics: calculate metrics of Regular, Bold"
        and len(plan) == 16
    )
    assert (
        app.pkg.font_info["Bold"]["openTypeOS2WinDescent"] == 250
        and app.history.calls == []
    )
    assert (
        app.tool.status == f"{label}. Applied 12 metric fields"
    )  # the 4 line gaps stay 0


def test_calculate_when_bounds_exceed_limits_then_refused_and_kept(opened):
    app = opened()
    panel = app.panels["Calculate"]
    panel.padding.setValue(2000)
    assert panel.plan and panel.plan[0][3] == 2760
    panel.bounds = {"Regular": (-32000.0, 760.0, 1)}
    panel.show_plan_slot = None
    panel.padding.setValue(1999)
    assert "Bounds exceed signed 16-bit typo/hhea limits." in app.tool.status
    assert panel.bounds  # the refusal keeps the captured bounds
    panel.bounds = {}
    panel.run(panel.apply)
    assert "Nothing to change." in app.tool.status and app.info == []


def test_calculate_when_another_font_is_current_then_glyph_records_refuses(
    opened, monkeypatch
):
    app = opened()
    calculate = importlib.import_module(f"{PKG}.calculate")
    monkeypatch.setattr(calculate, "current_package", lambda expected=None: NS(id=99))
    app.tool.reload()
    assert (
        "Activate the original font and reopen this tool."
        in app.panels["Calculate"].subtitle.text()
    )


def test_reporter_when_compared_then_reads_every_open_font_and_writes_nothing(opened):
    app = opened()
    panel = app.panels["Calculate"]
    buttons = [
        b
        for b in panel.widget.findChildren(type(panel.apply_button))
        if b.text() == "Compare open fonts"
    ]
    buttons[0].click()
    assert panel.report.toPlainText() == "typoAscender 750 …"
    assert (
        panel.report_status.text()
        == "Snapshot: 2 fonts, 3 masters. Refresh after changes."
    )
    assert app.writes == [] and font_writes(app) == [] and app.history.calls == []


def test_calculate_when_no_font_then_says_so(opened):
    app = opened()
    app.shell.package = lambda: None
    app.tool.reload()
    panel = app.panels["Calculate"]
    assert panel.status.text() == "Open a font first." and panel.plan == []
    panel.clear()
    assert panel.bounds == {}


# Zones ---------------------------------------------------------------------------------
def test_zones_when_opened_then_current_master_zones_and_nothing_pending(opened):
    app = opened()
    panel = app.panels["Zones"]
    assert table_rows(panel.grid) == [
        ("Top", "500", "8", "x-height"),
        ("Bottom", "0", "12", "baseline"),
    ]
    assert (
        panel.status.text() == "Regular: 2 zones" and not panel.apply_button.isEnabled()
    )


def test_zones_when_overshoots_all_masters_then_staged_listed_and_one_labelled_write(
    opened,
):
    app = opened()
    panel = app.panels["Zones"]
    panel.scope.setCurrentIndex(1)
    panel.overshoots()
    rows = table_rows(panel.suggested)
    assert rows[0] == ("Regular", "baseline", "0", "-12", "baseline at 0, width 12")
    assert rows[1] == ("Regular", "x-height", "500", "+10", "x-height at 500, width 8")
    assert rows[2] == ("Regular", "caps", "700", "+12", "nothing: added")
    assert (
        rows[5][4] == "nothing: added" and rows[5][2] == "703"
    )  # Bold H tops out at 703
    assert app.tool.status == "6 suggested zones"
    assert panel.editor.pending() == ("Regular", "Bold")
    panel.apply_button.click()
    kind, title, masters, after = app.writes[-1]
    assert (kind, title, masters) == (
        "zones",
        "Vertical Metrics: set zones of Regular, Bold",
        ["Regular", "Bold"],
    )
    xheight = next(z for z in after[0].top if z.name == "x-height")
    assert (xheight.width, xheight.origin.metadata) == (
        10,
        b"tags-and-lock",
    )  # tags and lock kept
    assert app.history.calls == [] and "Wrote 6 zones in 2 masters" in app.tool.status
    assert panel.editor.pending() == ()


def test_zones_when_glyph_changed_after_preview_then_refused(opened):
    app = opened()
    panel = app.panels["Zones"]
    panel.overshoots()
    app.pkg.glyphs["o"].layers["Regular"].span = (-11, 511)
    panel.apply_button.click()
    assert "H, O, x or o changed since the preview; press Refresh." in app.tool.status
    assert [w for w in app.writes if w[0] == "zones"] == [] and not panel.locked


def test_zones_when_already_matching_or_unmeasured_then_said(opened):
    app = opened()
    panel = app.panels["Zones"]
    panel.overshoots()
    panel.apply_button.click()
    panel.overshoots()
    assert app.tool.status == "3 suggested zones · the zones already match"
    del app.pkg.glyphs["o"]
    app.pkg.glyphs["O"].layers["Regular"].span = "broken"
    panel.extent_error = None
    app.found.extent.vertical_extent = lambda layer: (_ for _ in ()).throw(ValueError("bad topology")) \
        if layer.span == "broken" else layer.span  # fmt: skip
    panel.overshoots()
    assert "not measured: O in Regular (bad topology), baseline in Regular, x-height in Regular, caps in Regular" \
        in app.tool.status  # fmt: skip


def test_zones_when_row_refused_then_stages_kept_and_unlocked(opened):
    app = opened()
    panel = app.panels["Zones"]
    panel.add("Top")
    assert panel.editor.pending() == ("Regular",) and panel.grid.count() == 3
    app.found.zone_native.fail = app.found.zone_native.RowRefusal(
        "Give every zone a name."
    )
    panel.apply_button.click()
    assert "Give every zone a name." in app.tool.status and not panel.locked
    assert panel.editor.pending() == ("Regular",)
    app.found.zone_native.fail = ValueError(app.found.font_history.WINDOW_TEXT)
    panel.apply_button.click()
    assert not panel.locked


def test_zones_when_write_fails_unknown_then_locked_until_reopen(opened):
    app = opened()
    panel = app.panels["Zones"]
    panel.add("Bottom")
    app.found.zone_native.fail = RuntimeError("native write failed")
    panel.apply_button.click()
    assert panel.locked and "native write failed" in app.tool.status
    app.tool.reload()
    assert (
        "Zones may be partly written" in panel.subtitle.text() and panel.editor is None
    )
    panel.run(panel.add_top if hasattr(panel, "add_top") else lambda: panel.add("Top"))
    assert "Zones may be partly written" in app.tool.status


def test_zones_when_other_value_error_then_locked(opened):
    app = opened()
    panel = app.panels["Zones"]
    panel.add("Top")
    app.found.zone_native.fail = ValueError("Read-back differs")
    panel.apply_button.click()
    assert panel.locked


def test_zones_when_result_differs_then_locked(opened, monkeypatch):
    app = opened()
    panel = app.panels["Zones"]
    panel.add("Top")
    monkeypatch.setattr(
        app.found.zone_native, "apply", lambda before, changes, title: before
    )
    panel.apply_button.click()
    assert panel.locked and "differs from the complete plan" in app.tool.status


def test_zones_when_cells_edited_switched_removed_and_suggested_then_staged_per_master(
    opened,
):
    app = opened()
    panel = app.panels["Zones"]
    panel.grid.set_cell(0, 2, "abc")
    assert not panel.apply_button.isEnabled() and app.tool.status.startswith(
        "Vertical Metrics & Zones:"
    )
    assert panel.editor.rows("Regular")[0][2] == 8.0  # previous stage kept
    panel.grid.set_cell(0, 2, "14")
    assert panel.editor.pending() == ("Regular",)
    panel.master.setCurrentIndex(1)
    assert panel.current == "Bold" and panel.status.text().startswith(
        "Bold: 2 zones · unsaved: Regular"
    )
    panel.grid.select(0)
    panel.remove()
    assert panel.grid.count() == 1
    panel.suggest()
    assert panel.editor.pending() == ("Regular", "Bold")
    panel.master.setCurrentIndex(0)
    assert panel.grid.cell(0, 2) == "14"


def test_zones_when_no_font_then_cleared_and_refused(opened):
    app = opened()
    app.shell.package = lambda: None
    app.tool.reload()
    panel = app.panels["Zones"]
    assert panel.grid.count() == 0 and panel.editor is None
    panel.run(panel.apply)
    assert "Open a font first." in app.tool.status
    panel.editor = panel.editor  # still None
    with pytest.raises(ValueError, match="Open a font first."):
        panel.chosen_masters()


def test_zones_when_plan_empty_then_nothing_to_change(opened):
    app = opened()
    panel = app.panels["Zones"]
    panel.run(panel.apply)
    assert "Nothing to change." in app.tool.status and app.writes == []


def test_unchanged_when_refusal_kinds_then_classified(studio_qt):  # noqa: F811
    zones = importlib.import_module(f"{PKG}.zones")
    found = fake_backends(Package([]), [])
    assert zones.unchanged(found.zone_native.RowRefusal("x"), found)
    assert zones.unchanged(
        found.font_history.RolledBackError("t", RuntimeError("x")), found
    )
    assert zones.unchanged(ValueError(found.font_history.THREAD_TEXT), found)
    assert not zones.unchanged(ValueError("other"), found)


# Italic angle ---------------------------------------------------------------------------
def test_angle_when_edited_then_gauge_status_and_one_labelled_write(opened):
    app = opened()
    panel = app.panels["Italic angle"]
    assert (
        panel.view.item(0, 0).text() == "Regular  (current)"
        and panel.view.item(1, 0).text() == "Bold"
    )
    assert (
        panel.status.text() == "Edit an angle to change it"
        and not panel.apply_button.isEnabled()
    )
    box = panel.spins["Regular"]
    assert (box.minimum(), box.maximum(), box.decimals(), box.suffix()) == (
        -45.0,
        45.0,
        1,
        "°",
    )
    box.setValue(-8.5)
    assert panel.status.text() == "1 master changed" and panel.gauge.angles == [
        ("Regular", -8.5),
        ("Bold", -12.0),
    ]
    panel.apply_button.click()
    assert app.writes == [
        ("angles", "Vertical Metrics: set italic angle of Regular", {"Regular": -8.5})
    ]
    assert app.history.calls == [] and app.pkg.angles["Regular"] == -8.5
    assert app.tool.status.endswith("Set the italic angle of 1 master")


def test_angle_when_stale_or_nothing_then_refused(opened):
    app = opened()
    panel = app.panels["Italic angle"]
    panel.run(panel.apply)
    assert "Nothing to change." in app.tool.status
    panel.spins["Bold"].setValue(-10)
    app.pkg.angles["Bold"] = -11.0
    panel.apply_button.click()
    assert (
        "Source angles or masters changed; refresh this tool." in app.tool.status
        and app.writes == []
    )


def test_angle_when_no_font_then_cleared(opened):
    app = opened()
    app.shell.package = lambda: None
    app.tool.reload()
    panel = app.panels["Italic angle"]
    assert (
        panel.view.rowCount() == 0
        and panel.pending() == []
        and panel.gauge.angles == []
    )


# Diagram and Nodes Near Zones ------------------------------------------------------------
def test_diagram_when_painted_then_reads_every_master_and_writes_nothing(opened):
    app = opened()
    panel = app.panels["Diagram"]
    assert (
        sorted(panel.metrics) == ["Bold", "Regular"]
        and panel.metrics["Bold"]["capsHeight"] == 710.0
    )
    assert [s[0] for s in panel.samples["Regular"]] == [
        "H",
        "x",
        "b",
        "p",
    ] and panel.sample_width == 2000
    panel.diagram.resize(600, 300)
    panel.diagram.grab()  # PySide6 getters are methods: the verbatim PythonQt paint fails, contained
    assert panel.diagram.paint_error.startswith("TypeError")
    diagram = importlib.import_module(f"{PKG}.diagram")
    pythonqt = type("PythonQtDiagram", (diagram.Diagram,), {"width": property(lambda s: 600),
                                                           "height": property(lambda s: 300),
                                                           "palette": property(lambda s: s.__class__.__mro__[2].palette(s))})  # fmt: skip
    view = pythonqt(panel)
    view.resize(600, 300)
    view.grab()
    assert view.paint_error == ""
    assert "4 of 4 sample glyphs" in panel.subtitle.text()
    assert app.writes == [] and font_writes(app) == [] and app.history.calls == []


def test_diagram_when_sample_missing_then_noted(opened):
    app = opened()
    app.pkg.glyphs["b"].isNull = True
    app.pkg.glyphs["p"].layers.pop("Bold")
    app.tool.reload()
    panel = app.panels["Diagram"]
    assert panel.notes.text() == "b: not in this font · p: no layer in Bold"
    assert "3 of 4 sample glyphs" in panel.subtitle.text()


def test_nodes_when_scanned_then_near_misses_default_tolerance_and_preview(opened):
    app = opened(selection=())
    panel = app.panels["Diagram"]
    assert panel.scope.currentIndex() == 1  # nothing selected: All glyphs
    assert panel.tolerance.value() == 4 and panel.tolerance.suffix() == " units"
    assert table_rows(panel.grid) == [("O · Bold", "cap height 710", "400, 712", "712", "+2"),
                                      ("O · Bold", "cap height 710", "0, 712", "712", "+2")]  # fmt: skip
    assert app.writes == [] and font_writes(app) == [] and app.history.calls == []
    panel.grid.select(0)
    assert app.preview.calls[-2:] == [("set_text", "/O"), ("set_layer", "Bold")]


def test_nodes_when_tolerance_and_selection_change_then_rescanned_and_selected(opened):
    app = opened(selection=("x",))
    panel = app.panels["Diagram"]
    assert panel.scope.currentIndex() == 0 and panel.grid.count() == 0
    assert panel.status.text().startswith("1 glyphs × 2 masters checked")
    panel.scope.setCurrentIndex(1)
    panel.tolerance.setValue(1)
    assert panel.status.text().endswith("0 near misses in 0 glyphs")
    panel.tolerance.setValue(10)
    assert panel.grid.count() >= 1
    panel.select_button.click()
    names = list(dict.fromkeys(r[0] for r in panel.rows))
    assert (
        app.selected == [(names, 7)]
        and len(names) > 1
        and app.tool.status == f"Selected {len(names)} glyphs"
    )
    panel.grid.select(0)
    panel.select_button.click()
    assert app.selected[-1] == ([panel.rows[0][0]], 7)
    assert app.writes == [] and font_writes(app) == []


def test_nodes_when_font_switched_then_select_refused(opened, monkeypatch):
    app = opened(selection=())
    panel = app.panels["Diagram"]
    diagram = importlib.import_module(f"{PKG}.diagram")
    monkeypatch.setattr(diagram, "current_package", lambda expected=None: NS(id=8))
    panel.select_button.click()
    assert "stale font: Refresh the report." in app.tool.status and app.selected == []
    panel.package_id = None
    panel.run(panel.select_rows)
    assert "Refresh the report before selecting glyphs." in app.tool.status


def test_nodes_when_component_shape_then_skipped(studio_qt):  # noqa: F811
    diagram = importlib.import_module(f"{PKG}.diagram")
    layer = NS(shapes=[Shape([(0, 3)], component="acute"), Shape([(1, 2)])])
    assert diagram.on_curve_points(layer) == [(1.0, 2.0)]


def test_diagram_when_no_font_then_cleared(opened):
    app = opened()
    app.shell.package = lambda: None
    app.tool.reload()
    panel = app.panels["Diagram"]
    assert (
        panel.masters == []
        and panel.grid.count() == 0
        and not panel.select_button.isEnabled()
    )
    panel.rescan()
    assert panel.rows == []


# Demo ---------------------------------------------------------------------------------
def test_demo_when_run_then_opens_or_reports_error(monkeypatch):
    import runpy
    from pathlib import Path

    import fontlabapp
    import fontlabapp.qt.dialogs as dialogs
    import fontlabapp.studios.vertical_metrics as vm

    path = (
        Path(__file__).resolve().parents[1]
        / "Scripts"
        / "Metrics"
        / "Vertical Metrics & Zones Demo.py"
    )
    opened_with = []
    monkeypatch.setattr(vm, "show", lambda: opened_with.append(True))
    runpy.run_path(str(path), run_name="__main__")
    runpy.run_path(str(path), run_name="imported")
    assert opened_with == [True]
    said = []
    monkeypatch.setattr(
        vm, "show", lambda: (_ for _ in ()).throw(RuntimeError("no font"))
    )
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *a: said.append(a[3])
    )
    qt = NS(QtGui=NS(QMessageBox=NS(Ok=1)))
    stub_natives(monkeypatch, fontlabapp, lambda name: qt if name == 'PythonQt' else NS(MainWindow=lambda: None))
    runpy.run_path(str(path), run_name="__main__")
    assert said == ["Vertical Metrics & Zones did not open: no font"]


@pytest.mark.parametrize("entry,title,titles", [
    ("show_font_metrics", "Font Metrics", ("Metrics table", "Calculate", "About")),
    ("show_vertical_metrics", "Vertical Metrics", ("Zones", "Diagram", "About")),
])
def test_wp03_profiles_when_opened_then_only_mapped_tabs(studio_qt, entry, title, titles):  # noqa: F811 - imported fixture
    app = importlib.import_module("fontlabapp.studios.vertical_metrics.app")
    shell = getattr(app, entry)(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    assert shell.title == title
    assert tuple(shell.tabs.tabText(i) for i in range(shell.tabs.count())) == titles


def test_wp03_master_table_sort_keeps_edit_and_selection_identity(studio_qt):  # noqa: F811 - imported fixture
    from PythonQt import QtCore, QtGui
    shared = importlib.import_module("fontlabapp.studios.vertical_metrics._shared")
    owner = QtGui.QWidget()
    chosen = []
    grid = shared.MasterTable(owner, QtGui.QVBoxLayout(owner), ["Master", "Value"], editable=(1,), chosen=chosen.append)
    grid.set_rows([("Regular", "900"), ("Bold", "1000")])
    assert grid.view.isSortingEnabled()
    grid.view.sortItems(1, QtCore.Qt.DescendingOrder)
    assert grid.view.item(0, 0).text() == "Bold"
    grid.view.item(0, 1).setText("1100")
    assert grid.cell(1, 1) == "1100" and grid.cell(0, 1) == "900"
    grid.select(1)
    assert grid.selected() == [1] and chosen[-1] == "Bold"
    grid.set_rows([("Regular", "900"), ("Bold", "1100")])
    assert grid.selected() == [1]
    owner.close()


@pytest.mark.parametrize("module,class_name,plan_name,write_name,plan", [
    ("table", "MetricsTablePanel", "changes", "write_changes", [("Regular", "ascender", 800, 810)]),
    ("calculate", "CalculatePanel", "plan", "write_font_info", [("Regular", "openTypeHheaAscender", 800, 810)]),
])
def test_wp03_successful_write_disclosed_after_refresh_failure(studio_qt, monkeypatch, module, class_name, plan_name, write_name, plan):  # noqa: F811 - imported fixture
    loaded = importlib.import_module("fontlabapp.studios.vertical_metrics." + module)
    messages = []
    panel = object.__new__(getattr(loaded, class_name))
    setattr(panel, plan_name, plan)
    def fail():
        raise ValueError("reopen original font")
    panel.tool = NS(package=NS(master="Regular"), current="Regular", reload=fail, say=messages.append)
    monkeypatch.setattr(loaded, write_name, lambda *args, **kwargs: {"changed": 1, "pending_note": "Queued updates"})
    panel.apply()
    assert "1 metric field" in messages[-1]
    assert "reopen original font" in messages[-1] and "Queued updates" in messages[-1]


def test_wp03_metrics_bottom_preview_retains_invalid_draft(studio_qt, monkeypatch):  # noqa: F811 - imported fixture
    app = importlib.import_module("fontlabapp.studios.vertical_metrics.app")
    shell = app.show_font_metrics(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    panel = shell.kerning_tool.views[0].__self__
    panel.values = [("Regular", [800, -200, 500, 700])]
    panel.grid.set_rows([("Regular", "800", "-200", "500", "700")])
    panel.grid.set_cell(0, 1, "bad")
    shell.refresh_button.click()
    assert "discard staged edits" in shell.status.text()
    shell.preview_button.click()
    assert "enter numbers only" in shell.status.text()
    assert panel.grid.cell(0, 1) == "bad"


def test_wp03_metrics_bottom_apply_uses_sorted_master_identity(opened):
    from PythonQt import QtCore

    app = opened()
    panel = app.panels["Metrics table"]
    app.shell.tabs.setCurrentIndex(0)
    panel.grid.view.sortItems(0, QtCore.Qt.AscendingOrder)
    assert panel.grid.view.item(0, 0).text() == "Bold"
    panel.grid.view.item(0, 4).setText("720")
    assert app.shell.apply_button.isEnabled()
    app.shell.preview_button.click()
    assert app.writes == []
    app.shell.apply_button.click()
    assert app.writes[-1] == ("master metrics", "Vertical Metrics: set metrics of Bold", {"Bold": {"capHeight": 720.0}})


def test_wp03_master_table_duplicate_keys_keep_occurrence_selection(studio_qt):  # noqa: F811 - imported fixture
    from PythonQt import QtCore, QtGui
    shared = importlib.import_module("fontlabapp.studios.vertical_metrics._shared")
    owner = QtGui.QWidget()
    grid = shared.MasterTable(owner, QtGui.QVBoxLayout(owner), ["Kind", "Value"])
    grid.set_rows([("Top", "700"), ("Top", "500")])
    grid.view.sortItems(1, QtCore.Qt.AscendingOrder)
    grid.select(0)
    grid.set_rows([("Top", "700"), ("Top", "500")])
    assert grid.selected() == [0]
    owner.close()


def test_wp03_metrics_selected_diagram_preserves_labels_cleanup_and_errors(opened, monkeypatch):
    from unittest.mock import MagicMock
    app = opened()
    panel = app.panels['Metrics table']
    painter = MagicMock()
    module = importlib.import_module(f'{PKG}.diagram')
    monkeypatch.setattr(module.QtGui, 'QPainter', lambda *args: painter)
    panel.grid.select(1)
    panel.diagram.paintEvent(None)
    texts = [call.args[-1] for call in painter.drawText.call_args_list]
    assert 'Ascender 760' in texts and 'Baseline 0' in texts and 'Bold master' in texts
    assert painter.drawLine.call_count == 5 and painter.fillRect.call_count == 1
    painter.end.assert_called_once()
    assert panel.diagram.paint_error == ''
    panel.grid.set_cell(1, 1, 'bad')
    panel.diagram.paintEvent(None)
    assert 'ValueError' in panel.diagram.paint_error
    assert panel.status.text() == panel.diagram.paint_error
    assert painter.end.call_count == 2
    panel.clear()
    painter.reset_mock()
    panel.diagram.paintEvent(None)
    assert not painter.drawText.called
    painter.end.assert_called_once()


def test_wp03_calculate_changed_master_refuses_before_writer(opened):
    app = opened()
    panel = app.panels['Calculate']
    assert panel.plan
    app.pkg.master = 'Bold'
    with pytest.raises(ValueError, match='Master changed'):
        panel.apply()
    assert not panel.plan and not panel.apply_button.isEnabled()
    assert font_writes(app) == []


def test_wp03_vertical_profile_diagram_refresh_and_owned_close(studio_qt):  # noqa: F811 - imported fixture
    app = importlib.import_module(f'{PKG}.app')
    shell = app.show_vertical_metrics(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    shell.tabs.setCurrentIndex(1)
    panel = next(view.__self__ for view in shell.kerning_tool.views
                 if view.__self__.__class__.__name__ == 'DiagramPanel')
    panel.subtitle.setText('Stale preview')
    shell.refresh_button.click()
    assert panel.subtitle.text() == 'Open a font first.'
    assert shell.connections
    shell.close_button.click()
    assert shell._close_complete and shell._delete_scheduled
    assert shell.connections == [] and not shell.widget.isVisible()
