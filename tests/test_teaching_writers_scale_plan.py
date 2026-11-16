# this_file: tests/test_teaching_writers_scale_plan.py
"""Scale-with-stem-compensation: survey, make_plan and apply_plan against fake native objects."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

from test_teaching_writers_stem import make_contour

MOD = "fontlabapp.fontui.teaching_writers.scale_with_stem_compensation"
POINTS = [(0.0, 0.0, True), (100.0, 0.0, True), (100.0, 100.0, True), (0.0, 100.0, True)]


def mod():
    return importlib.import_module(MOD)


def layer(name, shift=0.0, **extra):
    points = [(x + shift, y, on) for x, y, on in POINTS]
    shape = NS(isComponent=False, transform=NS(isIdentity=lambda: True), contours=[make_contour(points, name="c")])
    return NS(name=name, shapes=[shape], isNull=False, autoLayer=False, isLocked=False, advanceWidth=500.0, **extra)


class Glyph:
    def __init__(self):
        self.isNull = self.autoLayer = self.isLocked = False
        self.layers = [layer("Light"), layer("Bold", 40.0)]
        self.added = []

    def findLayer(self, name):
        return next((item for item in self.layers if item.name == name), None)

    def addLayer(self, new):
        self.added.append(new)
        self.layers.append(new)


class Package:
    def __init__(self):
        self.masters = ["Light", "Bold"]
        self.glyph = Glyph()
        self.id = 7
        self.fgId = 11
        self.master = "Light"

    def findName(self, name):
        return self.glyph if name in ("A", "B") else None


def config(**kw):
    base = {"master": "Light", "first": "Light", "second": "Bold", "stems": (10.0, 20.0, 30.0, 40.0), "target": (15.0, 35.0), "scales": (1.0, 1.0), "angle": 0.0}
    base.update(kw)
    return base


@pytest.fixture
def history(monkeypatch):
    import fontlabapp.core.history.glyphs as glyphs

    monkeypatch.setattr(glyphs, "refusal", lambda facts, name, operation: "dependant" if name == "B" else "")
    monkeypatch.setattr(glyphs, "scan_auto_facts", lambda package: "facts")
    return glyphs


@pytest.mark.parametrize(
    ("names", "configs", "kw", "text"),
    [
        ([], [config()], {}, "Select glyphs"),
        (["A"], [], {}, "Select glyphs"),
        (["A"], [config(), config()], {}, "each target master once"),
    ],
)
def test_survey_when_selection_invalid_then_value_error(history, names, configs, kw, text):
    with pytest.raises(ValueError, match=text):
        mod().survey(Package(), names, configs, ".s", "facts")


@pytest.mark.parametrize(
    ("kw", "name", "note"),
    [
        ({}, "A", ""),
        ({"error": "enter numbers"}, "A", "enter numbers"),
        ({"master": "Nope"}, "A", "existing master"),
        ({}, "Missing", "disappeared"),
        ({}, "B", "dependant"),
        ({"stems": (10.0, 10.0, 30.0, 40.0)}, "A", "differ"),
    ],
)
def test_survey_when_row_refused_then_note_kept_and_row_retained(history, kw, name, note):
    package = Package()
    package.glyph.isNull = False
    rows = mod().survey(package, [name], [config(**kw)], ".s", "facts")
    assert len(rows) == 1 and rows[0]["target"] == rows[0]["master"] + ".s"
    assert note in rows[0]["note"], rows[0]
    assert (rows[0]["result"] is not None) == (note == "")


def test_survey_when_ready_then_advance_scaled_and_sources_kept(history):
    rows = mod().survey(Package(), ["A"], [config(scales=(2.0, 1.0), target=(30.0, 35.0))], ".s", "facts")
    assert rows[0]["advance"] == 1000.0 and len(rows[0]["sources"][0]) == 1


def test_survey_when_output_layer_exists_then_refused(history):
    package = Package()
    package.glyph.layers.append(layer("Light.s"))
    rows = mod().survey(package, ["A"], [config()], ".s", "facts")
    assert "already exists" in rows[0]["note"]


def test_survey_when_deadline_passed_then_timeout_noted(history, monkeypatch):
    m = mod()
    ticks = iter([0.0] + [1e9] * 50)
    monkeypatch.setattr(m, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="expired"):
        m.survey(Package(), ["A"], [config()], ".s", "facts")


def test_current_font_when_identity_differs_then_value_error(monkeypatch):
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "current_package", lambda: Package())
    assert mod().current_font(11).fgId == 11
    with pytest.raises(ValueError, match="font changed"):
        mod().current_font(12)
    monkeypatch.setattr(scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="font changed"):
        mod().current_font(11)


def test_make_plan_when_font_current_then_rows_recorded(history, monkeypatch):
    import fontlabapp.core.scripting as scripting

    package = Package()
    monkeypatch.setattr(scripting, "current_package", lambda: package)
    plan = mod().make_plan(11, ["A"], [config()], ".s")
    assert plan["identity"] == 11 and plan["suffix"] == ".s" and plan["rows"][0]["note"] == ""


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

    def addShape(self, shape):
        self.shapes.append(shape)


@pytest.fixture
def native(history, monkeypatch):
    import fontlabapp.contours.copy as copies
    import fontlabapp.core.scripting as scripting
    import fontlabapp.masters.layers.writer as writer

    package = Package()
    monkeypatch.setattr(scripting, "current_package", lambda: package)
    monkeypatch.setitem(sys.modules, "fontlab", NS(flShape=FlShape, flLayer=FlLayer))
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=NS(QTransform=lambda: object())))
    copied = []

    def copy_contours(source, transform):
        out = [make_contour(POINTS, name="c") for _ in source.shapes[0].contours]
        copied.extend(out)
        return out

    monkeypatch.setattr(copies, "copy_contours", copy_contours)
    monkeypatch.setattr(writer, "settle", lambda found: None)

    def commit(title, layers, glyphs, mutate, **kw):
        commit.calls.append((title, kw))
        mutate()
        missed = kw["read_back"]()
        return NS(mismatches=missed, pending_note="note", pending_updates=(1,))

    commit.calls = []
    monkeypatch.setattr(history, "commit", commit)
    return NS(package=package, commit=commit, copied=copied)


def test_apply_plan_when_not_confirmed_then_refused_without_writing(native):
    plan = mod().make_plan(11, ["A"], [config()], ".s")
    with pytest.raises(ValueError, match="Preview and confirm"):
        mod().apply_plan(plan, False)
    assert native.commit.calls == [] and native.package.glyph.added == []


def test_apply_plan_when_source_changed_then_preview_again(native):
    plan = mod().make_plan(11, ["A"], [config()], ".s")
    native.package.glyph.layers[0].advanceWidth = 999.0
    with pytest.raises(ValueError, match="Preview again"):
        mod().apply_plan(plan, True)


def test_apply_plan_when_all_rows_refused_then_nothing_changed(native):
    plan = mod().make_plan(11, ["B"], [config()], ".s")
    result = mod().apply_plan(plan, True)
    assert result["changed"] == 0 and result["kept"] == 1 and native.commit.calls == []


def test_apply_plan_when_ready_then_layer_added_in_one_commit_and_read_back(native):
    plan = mod().make_plan(11, ["A"], [config()], ".s")
    result = mod().apply_plan(plan, True)
    assert result["changed"] == 1, result
    assert len(native.commit.calls) == 1
    assert native.commit.calls[0][1]["window"] == 7 and native.package.glyph.added[0].name == "Light.s"


def test_apply_plan_when_layer_stores_blended_outline_then_counts_changed(native, monkeypatch):
    plan = mod().make_plan(11, ["A"], [config()], ".s")
    glyph = native.package.glyph
    original = glyph.addLayer

    def add(new):
        original(new)
        stored = layer("Light.s", 20.0)
        stored.advanceWidth = new.advanceWidth
        glyph.layers[-1] = stored

    glyph.addLayer = add
    result = mod().apply_plan(plan, True)
    assert result["changed"] == 1 and result["kept"] == 0 and result["pending_note"] == "note"


def test_apply_plan_when_attach_fails_then_runtime_error_names_cause(native):
    plan = mod().make_plan(11, ["A"], [config()], ".s")

    def boom(new):
        raise OSError("disk")

    native.package.glyph.addLayer = boom
    with pytest.raises(RuntimeError, match="disk"):
        mod().apply_plan(plan, True)


# ------------------------------------------------------------------ panel and main
@pytest.fixture
def panel(history, monkeypatch):
    import fontlabapp.core.edit_guards as guards
    import fontlabapp.core.scripting as scripting
    import fontlabapp.masters.angles.model as angles

    from _fake_gui import gui

    package = Package()
    shown = []
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=gui()))
    monkeypatch.setattr(scripting, "current_package", lambda: package)
    monkeypatch.setattr(scripting, "names_font_window_selection", lambda **kw: ["A"])
    monkeypatch.setattr(scripting, "connect_guarded", lambda owner, signal, slot: signal.slots.append(slot))
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: shown.append((cls, key)))
    monkeypatch.setattr(scripting, "close_script_dialog", lambda owner, event, key: shown.append(("closed", key)))
    monkeypatch.setattr(guards, "require_selection_window", lambda pid: None)
    monkeypatch.setattr(angles, "capture", lambda pkg: NS(angles={"Light": 0.0, "Bold": 10.0}))
    return NS(package=package, shown=shown, cls=mod().panel_type())


def buttons(widget):
    return {b.args[0]: b for b in widget.stack_box.children if b.args and b.args[0] in ("Use Selection / Reload Masters", "Preview", "Create Layers")}


def test_panel_when_opened_then_one_row_per_master_with_negated_angle_and_selection_status(panel):
    widget = panel.cls()
    table = widget.master_table
    assert table.rowCount == 2
    assert table.cellWidget(0, 0).isChecked() and not table.cellWidget(1, 0).isChecked()
    assert [table.item(1, c).text() for c in (1, 2, 3)] == ["Bold", "Light", "Bold"]
    assert table.item(1, 12).text() == "-10"
    assert widget.status.text.startswith("1 glyphs selected")


def test_panel_when_reloaded_with_changed_masters_then_refused(panel):
    widget = panel.cls()
    panel.package.masters = ["Light", "Bold", "Black"]
    with pytest.raises(ValueError, match="master list changed"):
        widget.reload_selection()


def test_panel_when_no_font_then_open_a_font_first(panel, monkeypatch):
    import fontlabapp.core.scripting as scripting

    widget = panel.cls()
    monkeypatch.setattr(scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Open a font first"):
        widget.reload_selection()


def test_panel_when_cell_not_number_then_configuration_carries_error(panel):
    widget = panel.cls()
    widget.master_table.item(0, 4).setText("x")
    [config] = widget.configurations()
    assert config["master"] == "Light" and "enter numbers" in config["error"]
    widget.master_table.item(0, 4).setText("50")
    [config] = widget.configurations()
    assert config["stems"] == (50.0, 100.0, 50.0, 100.0) and config["scales"] == (1.0, 1.0) and config["angle"] == 0.0


def test_panel_when_preview_then_create_layers_with_confirmation_and_invalidated_by_edit(panel, monkeypatch):
    widget = panel.cls()
    m = mod()
    plan = {"rows": [{"name": "A", "master": "Light", "target": "Light.scaled", "note": "", "advance": 500.0},
                     {"name": "B", "master": "Light", "target": "Light.scaled", "note": "dependant", "advance": None}]}
    seen = []
    monkeypatch.setattr(m, "make_plan", lambda *args: seen.append(args) or plan)
    monkeypatch.setattr(m, "apply_plan", lambda data, confirmed: {"changed": 1, "kept": 1, "pending_note": "n"} if confirmed else None)
    with pytest.raises(ValueError, match="Preview first"):
        widget.create_layers()
    widget.preview_scale()
    assert seen[0][0] == 11 and seen[0][3] == ".scaled"
    assert "A / Light -> Light.scaled: Create; advance 500" in widget.preview_field.plain
    assert "Kept: dependant" in widget.preview_field.plain
    widget.confirm_box.setChecked(True)
    widget.create_layers()
    assert "Created 1 layers; kept 1" in widget.status.text and "n" in widget.status.text
    assert widget.plan_data is None and not widget.confirm_box.isChecked()
    widget.preview_scale()
    widget.suffix_field.textChanged.emit("x")
    assert widget.plan_data is None and widget.preview_field.plain == ""


def test_panel_when_create_refused_then_plan_and_confirmation_cleared(panel, monkeypatch):
    widget = panel.cls()
    m = mod()
    monkeypatch.setattr(m, "make_plan", lambda *args: {"rows": []})

    def refuse(data, confirmed):
        raise ValueError("Preview and confirm the new layers first.")

    monkeypatch.setattr(m, "apply_plan", refuse)
    widget.preview_scale()
    with pytest.raises(ValueError, match="confirm"):
        widget.create_layers()
    assert widget.plan_data is None


def test_panel_when_closed_then_script_dialog_closed_with_key(panel):
    panel.cls().closeEvent(object())
    assert panel.shown == [("closed", "scale_with_stem_compensation")]


def test_main_when_started_then_dialog_shown_and_startup_errors_printed(panel, monkeypatch, capsys):
    import fontlabapp.core.scripting as scripting

    mod().main()
    assert panel.shown[0][1] == "scale_with_stem_compensation"

    def refuse(cls, key):
        raise RuntimeError("no window")

    monkeypatch.setattr(scripting, "show_script_dialog", refuse)
    mod().main()
    assert "no window" in capsys.readouterr().out
