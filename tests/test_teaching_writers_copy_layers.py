# this_file: tests/test_teaching_writers_copy_layers.py
"""Copy Layers From Font: name rules, survey refusals, apply with fake natives and the panel."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

MODULE = "fontlabapp.fontui.teaching_writers.copy_layers_from_font"


@pytest.fixture
def mod():
    return importlib.import_module(MODULE)


class Node:
    def __init__(self, x=0, y=0, on=True, props=None):
        self.x, self.y, self.nodeState, self.name, self._on, self._props = x, y, 0x21, "", on, props or {}

    def isOn(self):
        return self._on

    def getProperties(self):
        return self._props

    def getProperty(self, key):
        return self._props.get(key)


class Contour:
    def __init__(self, nodes=None, props=None):
        self._nodes, self.closed, self.isTT, self.name, self._props = nodes or [Node(), Node(1, 1)], True, False, "c", props or {}

    def nodes(self):
        return list(self._nodes)

    def getProperties(self):
        return self._props


class Tx:
    def __getattr__(self, name):
        if name.startswith("m") and len(name) == 3:
            return lambda: 1.0 if name[1] == name[2] else 0.0
        raise AttributeError(name)


class Shape:
    def __init__(self, contours=None, component=False):
        self.isComponent, self.name, self.transform = component, "s", Tx()
        self.shapeData = NS(name="d", note="n")
        self.contours, self.selected, self.active = contours if contours is not None else [Contour()], True, True

    def clone(self):
        return Shape([Contour() for _ in self.contours])


class Layer:
    def __init__(self, name="Regular", shapes=None, anchors=(), width=500.0, **flags):
        self.name, self.shapes, self.anchors, self.advanceWidth = name, shapes if shapes is not None else [Shape()], list(anchors), width
        self.isNull = self.autoLayer = self.isLocked = self.isService = self.hasHints = self.hasTTH = self.isMasterLayer = False
        self.guidelines, self.metricsLeft, self.metricsRight, self.metricsWidth = [], "", "", ""
        self.mask = None
        self.__dict__.update(flags)

    def getMaskLayer(self, create):
        if self.mask is None and create:
            self.mask = Layer("mask." + self.name, [])
        return self.mask

    def removeShape(self, shape):
        self.shapes.remove(shape)

    def addShape(self, shape):
        self.shapes.append(shape)


def anchor(name, x, y):
    return NS(name=name, point=NS(x=lambda: x, y=lambda: y))


class Glyph:
    isNull = False

    def __init__(self, *layers):
        self.layers = list(layers)

    def findLayer(self, name):
        return next((layer for layer in self.layers if layer.name == name), None)

    def addLayer(self, layer):
        self.layers.append(layer)


class Font:
    def __init__(self, fid, glyphs, upm=1000, masters=("Regular",)):
        self.id = self.fgId = fid
        self._glyphs, self.masters, self.master = glyphs, list(masters), "Regular"
        self.info, self.path = NS(unitsPerEm=upm), f"/f{fid}.vfj"

    def findName(self, name):
        return self._glyphs.get(name)


def test_checked_name_when_reserved_or_blank_then_refused_else_returned(mod):
    assert mod.checked_name("Bold") == "Bold"
    for bad in ("", " ", "a@b", "a#b", "|temp|x", "Mask1", "img.x", "BW.x", "a\x01", "a b"):
        with pytest.raises(ValueError, match="nonempty layer name"):
            mod.checked_name(bad)


def test_collision_when_each_mode_then_names_and_backup(mod):
    assert mod.collision("L", "", "Overwrite", True) == ("L", None)
    assert mod.collision("L", ".c", "Incoming + suffix", False) == ("L.c", None)
    assert mod.collision("L", ".c", "Destination + suffix", True) == ("L", "L.c")
    assert mod.collision("L", ".c", "Destination + suffix", False) == ("L", None)
    with pytest.raises(ValueError, match="listed collision"):
        mod.collision("L", ".c", "Nope", True)
    with pytest.raises(ValueError, match="nonempty suffix"):
        mod.collision("L", "", "Incoming + suffix", True)


def test_registered_fonts_and_resolve_when_states_then_pairs_or_refused(mod, monkeypatch):
    import fontlabapp.core.scripting as scripting

    fonts = {1: Font(1, {}), 2: Font(2, {}), 3: Font(3, {}, upm=2048)}
    fl = NS(
        flPackage=lambda item: item,
        flWorkspace=NS(instance=lambda: NS(packages=lambda: list(fonts.values()))),
        AllFonts=lambda: [NS(id=1, path="/a"), NS(id=2, path=""), NS(id=3, path="/c"), NS(id=9, path="/z")],
    )
    monkeypatch.setitem(sys.modules, "fontlab", fl)
    reg = mod.registered_fonts()
    assert set(reg) == {1, 2, 3} and reg[2][0] == "Font 2" and reg[1][1] is fonts[1]
    monkeypatch.setattr(scripting, "current_package", lambda: fonts[2])
    assert mod.resolve(1, 2) == (fonts[1], fonts[2])
    for pair in ((1, 1), (9, 2), (1, 9), (1, 3)):
        with pytest.raises(ValueError, match="Keep both fonts|units per em"):
            mod.resolve(*pair)
    with pytest.raises(ValueError, match="units per em"):
        monkeypatch.setattr(scripting, "current_package", lambda: fonts[3])
        mod.resolve(1, 3)
    monkeypatch.setattr(scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Keep both fonts"):
        mod.resolve(1, 2)


def test_layer_data_when_normal_then_snapshot_and_when_bad_then_errors(mod):
    data = mod.layer_data(Layer(anchors=[anchor("top", 5, 6), anchor("a", 1, 2)]), float("inf"))
    assert data["width"] == 500.0 and data["anchors"] == (("a", 1.0, 2.0), ("top", 5.0, 6.0))
    assert data["shapes"][0][4][0][3][0] == (0.0, 0.0, True, 1, "")
    with pytest.raises(TimeoutError, match="expired"):
        mod.layer_data(Layer(), 0.0)
    with pytest.raises(ValueError, match="finite"):
        mod.layer_data(Layer(width=float("nan")), float("inf"))


@pytest.mark.parametrize(
    ("layer", "source", "message"),
    [
        (None, True, "missing"),
        (Layer(isNull=True), True, "missing"),
        (Layer(autoLayer=True), True, "automatic"),
        (Layer(isLocked=True), True, "automatic"),
        (Layer(isService=True), True, "automatic"),
        (Layer(hasHints=True), True, "hints"),
        (Layer(hasTTH=True), True, "hints"),
        (Layer(guidelines=[1]), True, "hints"),
        (Layer(metricsLeft="=x"), True, "metric"),
        (Layer(shapes=[Shape(component=True)]), True, "components"),
        (Layer(shapes=[Shape([Contour(props={"k": 1})])]), True, "custom"),
        (Layer(shapes=[Shape([Contour([Node(props={"k": 1})])])]), True, "custom"),
        (Layer(shapes=[Shape([Contour([Node(props={"corner_smooth": 0})])])]), True, "custom"),
        (Layer(anchors=[anchor("a", 0, 0), anchor("a", 1, 1)]), False, "repeated"),
    ],
)
def test_usable_when_unsupported_then_refused(mod, layer, source, message):
    with pytest.raises(ValueError, match=message):
        mod.usable(layer, source=source)


def test_usable_when_clean_then_passes_and_destination_skips_property_scan(mod):
    mod.usable(Layer(), source=True)
    mod.usable(Layer(shapes=[Shape([Contour(props={"k": 1})])]), source=False)


@pytest.fixture
def world(monkeypatch):
    import fontlabapp.anchors.writer as anchors
    import fontlabapp.core.history.glyphs as history

    calls = NS(commit=None, refusal=None)
    monkeypatch.setattr(history, "refusal", lambda facts, name, op: calls.refusal if name == "Locked" else "")
    monkeypatch.setattr(history, "scan_auto_facts", lambda font: "facts")
    monkeypatch.setattr(history, "component_history", lambda shape: ["h"])
    monkeypatch.setattr(anchors, "anchor_points", lambda layer: {a.name: (a.point.x(), a.point.y()) for a in layer.anchors})
    monkeypatch.setattr(anchors, "require_safe", lambda items, facts: None)
    monkeypatch.setattr(anchors, "prepare", lambda stage, edits: [(a, n, p) for a, n, p in edits])
    monkeypatch.setattr(anchors, "write", lambda target, steps: setattr(target, "anchors", [anchor(n, *p) for a, n, p in steps if a == "set"]))
    import fontlabapp.masters.layers.writer as lw

    monkeypatch.setattr(lw, "settle", lambda layer: None)
    src = Font(1, {"A": Glyph(Layer("Light", anchors=[anchor("top", 5, 6)]), Layer("Bad", hasHints=True))})
    dst = Font(2, {"A": Glyph(Layer("Regular", anchors=[anchor("top", 0, 0)]), Layer("Extra")), "Locked": Glyph(Layer("Regular"))})
    src._glyphs["Locked"] = Glyph(Layer("Light"))
    return NS(src=src, dst=dst, calls=calls)


def note(rows, i=0):
    return rows[i]["note"]


def run(mod, world, mappings, mode="Overwrite", suffix=".c", names=("A",)):
    return mod.survey(world.src, world.dst, list(names), mappings, mode, suffix, "facts")


def test_survey_when_inputs_missing_or_duplicate_then_refused(mod, world):
    with pytest.raises(ValueError, match="Select destination"):
        run(mod, world, [], names=("A",))
    with pytest.raises(ValueError, match="Select destination"):
        run(mod, world, [("Light", "Regular")], names=())
    with pytest.raises(ValueError, match="once"):
        run(mod, world, [("Light", "Regular"), ("Bad", "REGULAR")])


def test_survey_when_overwrite_then_row_has_data_and_before(mod, world):
    row = run(mod, world, [("Light", "Regular")])[0]
    assert row["note"] == "" and row["target"] == "Regular" and row["data"]["width"] == 500.0
    assert row["before"]["anchors"] == (("top", 0.0, 0.0),)


def test_survey_when_row_unusable_then_kept_with_reason(mod, world):
    assert "enter a source" in note(run(mod, world, [(" ", "Regular")]))
    assert "glyph missing" in note(run(mod, world, [("Light", "Regular")], names=("Z",)))
    world.calls.refusal = "dependant"
    assert note(run(mod, world, [("Light", "Regular")], names=("Locked",))) == "dependant"
    assert "hints" in note(run(mod, world, [("Bad", "Regular")]))
    assert "layer is missing" in note(run(mod, world, [("Nope", "Regular")]))
    world.dst._glyphs["A"].layers[0].hasHints = True
    assert "hints" in note(run(mod, world, [("Light", "Regular")]))


def test_survey_when_deadline_passed_then_timeout_propagates(mod, world, monkeypatch):
    monkeypatch.setattr(mod, "monotonic", lambda: 1e18)
    with pytest.raises(TimeoutError, match="expired"):
        run(mod, world, [("Light", "Regular")])


def test_survey_when_overwrite_moves_anchor_to_origin_then_refused(mod, world):
    world.src._glyphs["A"].layers[0].anchors = [anchor("top", 0, 0)]
    world.dst._glyphs["A"].layers[0].anchors = [anchor("top", 4, 4)]
    assert "fl#8527" in note(run(mod, world, [("Light", "Regular")]))


def test_survey_when_incoming_suffix_then_new_name_or_existing_refused(mod, world):
    row = run(mod, world, [("Light", "Regular")], "Incoming + suffix", ".c")[0]
    assert row["target"] == "Regular.c" and row["before"] is None and row["note"] == ""
    world.dst._glyphs["A"].layers.append(Layer("Regular.c"))
    assert "already exists" in note(run(mod, world, [("Light", "Regular")], "Incoming + suffix", ".c"))
    assert "nonempty suffix" in note(run(mod, world, [("Light", "Regular")], "Incoming + suffix", ""))


def test_survey_when_incoming_name_clashes_by_case_or_master_then_refused(mod, world):
    world.dst._glyphs["A"].layers.append(Layer("regular.c"))
    assert "case-insensitive" in note(run(mod, world, [("Light", "Regular")], "Incoming + suffix", ".C"))
    world.dst.masters.append("Regular.x")
    assert "master layer is missing" in note(run(mod, world, [("Light", "Regular")], "Incoming + suffix", ".x"))


def test_survey_when_destination_suffix_then_backup_rules(mod, world):
    row = run(mod, world, [("Light", "Regular")], "Destination + suffix", ".b")[0]
    assert row["backup"] == "Regular.b" and row["note"] == ""
    world.dst._glyphs["A"].layers[0].isMasterLayer = True
    assert "cannot rename" in note(run(mod, world, [("Light", "Regular")], "Destination + suffix", ".b"))
    world.dst._glyphs["A"].layers[0].isMasterLayer = False
    world.dst._glyphs["A"].layers.append(Layer("Regular.b"))
    assert "cannot rename" in note(run(mod, world, [("Light", "Regular")], "Destination + suffix", ".b"))
    world.dst._glyphs["A"].layers.pop()
    world.dst.masters.append("regular.b")
    assert "cannot rename" in note(run(mod, world, [("Light", "Regular")], "Destination + suffix", ".b"))


def test_survey_when_mask_then_body_and_mask_rules(mod, world):
    body = world.dst._glyphs["A"].layers[0]
    row = run(mod, world, [("Light", "Regular")], "Mask")[0]
    assert row["mask_name"] == "mask.Regular" and row["note"] == "" and row["before"] is None
    assert "missing, automatic" in note(run(mod, world, [("Light", "Nothing")], "Mask"))
    body.isLocked = True
    assert "missing, automatic" in note(run(mod, world, [("Light", "Regular")], "Mask"))
    body.isLocked = False
    body.mask = Layer("mask.Other")
    assert "another layer" in note(run(mod, world, [("Light", "Regular")], "Mask"))
    body.mask = Layer("mask.Regular", [Shape()])
    world.dst._glyphs["A"].layers.append(body.mask)
    row = run(mod, world, [("Light", "Regular")], "Mask")[0]
    assert row["note"] == "" and row["before"] is not None


def test_make_plan_when_resolved_then_plan_has_rows(mod, world, monkeypatch):
    monkeypatch.setattr(mod, "resolve", lambda s, d: (world.src, world.dst))
    plan = mod.make_plan(1, 2, ["A"], [("Light", "Regular")], "Overwrite", ".c")
    assert plan["source_id"] == 1 and plan["rows"][0]["note"] == "" and plan["suffix"] == ".c"


def test_clone_shapes_when_topology_kept_then_clones_else_refused(mod, monkeypatch):
    import fontlabapp.contours.copy as copies

    repaired = []
    monkeypatch.setattr(copies, "repair_nodes", lambda a, b: repaired.append((a, b)))
    layer = Layer(shapes=[Shape()])
    out = mod.clone_shapes(layer)
    assert len(out) == 1 and out[0].name == "s" and out[0].selected is False and len(repaired) == 1
    bad = Shape()
    bad.clone = lambda: Shape([Contour()]) if False else _flipped()
    with pytest.raises(ValueError, match="topology"):
        mod.clone_shapes(Layer(shapes=[bad]))


def _flipped():
    shape = Shape()
    shape.contours[0].closed = False
    return shape


class Commit:
    def __init__(self, mismatches=(), run_read_back=True):
        self.mismatches, self.pending_note, self.pending_updates = list(mismatches), "note", ("u",)
        self.run_read_back = run_read_back


@pytest.fixture
def applied(mod, world, monkeypatch):
    import fontlabapp.contours.copy as copies
    import fontlabapp.core.history.glyphs as history

    monkeypatch.setattr(copies, "repair_nodes", lambda a, b: None)
    monkeypatch.setattr(mod, "resolve", lambda s, d: (world.src, world.dst))
    monkeypatch.setitem(sys.modules, "fontlab", NS(flLayer=lambda: Layer("", [])))
    seen = NS(missed=None)

    def commit(title, existing, owners, mutate, **kw):
        mutate()
        seen.missed = kw["read_back"]()
        seen.kw = kw
        return Commit()

    monkeypatch.setattr(history, "commit", commit)
    world.seen = seen
    return world


def plan_for(mod, world, mappings, mode="Overwrite", suffix=".c"):
    return {"source_id": 1, "destination_id": 2, "names": ["A"], "mappings": mappings, "mode": mode, "suffix": suffix,
            "rows": mod.survey(world.src, world.dst, ["A"], mappings, mode, suffix, "facts")}


def test_apply_plan_when_unconfirmed_or_changed_then_refused(mod, applied):
    plan = plan_for(mod, applied, [("Light", "Regular")])
    with pytest.raises(ValueError, match="confirm"):
        mod.apply_plan(plan, False)
    applied.src._glyphs["A"].layers[0].advanceWidth = 600.0
    with pytest.raises(ValueError, match="Preview again"):
        mod.apply_plan(plan, True)


def test_apply_plan_when_nothing_plannable_then_kept_counted(mod, applied):
    plan = plan_for(mod, applied, [("Bad", "Regular")])
    assert mod.apply_plan(plan, True) == {"pending_updates": (), "pending_note": "", "changed": 0, "kept": 1}


def test_apply_plan_when_overwrite_then_target_replaced_and_read_back_flags_mismatch(mod, applied):
    plan = plan_for(mod, applied, [("Light", "Regular")])
    result = mod.apply_plan(plan, True)
    assert result["changed"] == 1 and result["kept"] == 0 and result["pending_note"] == "note"
    target = applied.dst._glyphs["A"].findLayer("Regular")
    assert target.advanceWidth == 500.0 and len(target.shapes) == 1
    assert applied.seen.missed == ["A/Regular"] or applied.seen.missed == []


def test_apply_plan_when_incoming_suffix_then_layer_added(mod, applied):
    plan = plan_for(mod, applied, [("Light", "Regular")], "Incoming + suffix", ".new")
    assert mod.apply_plan(plan, True)["changed"] == 1
    assert applied.dst._glyphs["A"].findLayer("Regular.new") is not None


def test_apply_plan_when_destination_suffix_then_body_renamed_and_backup_checked(mod, applied):
    plan = plan_for(mod, applied, [("Light", "Regular")], "Destination + suffix", ".b")
    mod.apply_plan(plan, True)
    glyph = applied.dst._glyphs["A"]
    assert glyph.findLayer("Regular.b") is not None and glyph.findLayer("Regular").advanceWidth == 500.0


def test_apply_plan_when_mask_then_mask_layer_created(mod, applied):
    plan = plan_for(mod, applied, [("Light", "Regular")], "Mask")
    glyph = applied.dst._glyphs["A"]
    body = glyph.layers[0]
    original = body.getMaskLayer

    def attach(create):
        had = body.mask is not None
        layer = original(create)
        if layer is not None and not had:
            glyph.layers.append(layer)
        return layer

    body.getMaskLayer = attach
    mod.apply_plan(plan, True)
    assert applied.dst._glyphs["A"].layers[0].mask.advanceWidth == 500.0


def test_apply_plan_when_write_fails_then_error_reported(mod, applied, monkeypatch):
    import fontlabapp.core.history.glyphs as history

    plan = plan_for(mod, applied, [("Light", "Regular")])
    target = applied.dst._glyphs["A"].layers[0]
    target.addShape = lambda s: (_ for _ in ()).throw(RuntimeError("boom"))

    def commit(title, existing, owners, mutate, **kw):
        mutate()
        with pytest.raises(RuntimeError, match="boom"):
            kw["read_back"]()
        return Commit(["x differs"])

    monkeypatch.setattr(history, "commit", commit)
    with pytest.raises(RuntimeError, match="Edit > Undo. x differs"):
        mod.apply_plan(plan, True)


def test_apply_plan_when_attach_fails_then_error_recorded(mod, applied, monkeypatch):
    import fontlabapp.core.history.glyphs as history

    plan = plan_for(mod, applied, [("Light", "Regular")], "Incoming + suffix", ".z")
    applied.dst._glyphs["A"].addLayer = lambda layer: None
    got = []

    def commit(title, existing, owners, mutate, **kw):
        mutate()
        try:
            kw["read_back"]()
        except RuntimeError as error:
            got.append(str(error))
        return Commit()

    monkeypatch.setattr(history, "commit", commit)
    mod.apply_plan(plan, True)
    assert got and "did not attach" in got[0]


def test_apply_plan_when_read_back_differs_then_missed_listed(mod, applied, monkeypatch):
    import fontlabapp.core.history.glyphs as history

    plan = plan_for(mod, applied, [("Light", "Regular")], "Destination + suffix", ".b")
    out = []

    def commit(title, existing, owners, mutate, **kw):
        mutate()
        applied.dst._glyphs["A"].findLayer("Regular.b").advanceWidth = 1.0
        applied.dst._glyphs["A"].findLayer("Regular").advanceWidth = 2.0
        applied.src._glyphs["A"].findLayer("Light").advanceWidth = 3.0
        out.extend(kw["read_back"]())
        return Commit()

    monkeypatch.setattr(history, "commit", commit)
    mod.apply_plan(plan, True)
    assert "A/Regular" in out and "backup differs: A" in out and "source changed: A" in out


# ---- CopyPanel with fake Qt widgets ----------------------------------------


class _Sig:
    pass


class _Widget:
    def __init__(self, *args, **kwargs):
        self._text = args[0] if args and isinstance(args[0], str) else ""
        self._checked, self._index, self.items = False, -1, []
        self.currentIndexChanged = self.textChanged = self.clicked = self.cellChanged = _Sig()

    def text(self):  # noqa: D102
        return self._text

    def setText(self, text):
        self._text = text

    def setPlainText(self, text):
        self._text = text

    def setReadOnly(self, flag):
        pass

    def setWindowTitle(self, title):
        pass

    def resize(self, *size):
        pass

    def addWidget(self, widget):
        pass

    def addItems(self, items):
        self.items = list(items)

    def addItem(self, item):
        self.items.append(item)
        self._index = max(self._index, 0)

    def clear(self):
        self.items, self._index = [], -1

    @property
    def currentIndex(self):
        return self._index

    @property
    def currentText(self):
        return self.items[self._index] if 0 <= self._index < len(self.items) else ""

    def setCurrentIndex(self, i):
        self._index = i

    def isChecked(self):
        return self._checked

    def setChecked(self, flag):
        self._checked = flag


class _Table(_Widget):
    def __init__(self, rows, cols):
        super().__init__()
        self._rows, self.cells = rows, {}

    @property
    def rowCount(self):
        return self._rows

    def setRowCount(self, n):
        self._rows = n

    def setHorizontalHeaderLabels(self, labels):
        pass

    def setSortingEnabled(self, flag):
        pass

    def setItem(self, row, col, item):
        self.cells[(row, col)] = item

    def item(self, row, col):
        return self.cells.get((row, col))


@pytest.fixture
def panel_world(mod, monkeypatch):
    import fontlabapp.core.edit_guards as guards
    import fontlabapp.core.scripting as scripting

    gui = NS(QDialog=type("QDialog", (_Widget,), {"__init__": lambda self, parent=None: _Widget.__init__(self)}),
             QVBoxLayout=_Widget, QComboBox=_Widget, QLineEdit=_Widget, QLabel=_Widget, QPlainTextEdit=_Widget,
             QCheckBox=_Widget, QPushButton=_Widget, QTableWidget=_Table, QTableWidgetItem=_Widget)
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=gui))
    seen = NS(guarded=[], required=[], closed=[], names=[])
    monkeypatch.setattr(scripting, "connect_guarded", lambda owner, sig, cb: seen.guarded.append(cb))
    package = NS(id=2, fgId=2, master="Regular")
    monkeypatch.setattr(scripting, "current_package", lambda: package)
    monkeypatch.setattr(scripting, "names_font_window_selection", lambda **kw: seen.names.append(kw) or ["A"])
    monkeypatch.setattr(scripting, "close_script_dialog", lambda owner, event, key: seen.closed.append((event, key)))
    monkeypatch.setattr(guards, "require_selection_window", lambda pid: seen.required.append(pid))
    monkeypatch.setattr(mod, "registered_fonts", lambda: {1: ("/src.vfj", None), 2: ("/dst.vfj", None)})
    seen.package = package
    seen.cls = mod.panel_type()
    return seen


def test_panel_when_built_then_fonts_listed_and_mapping_seeded(panel_world):
    panel = panel_world.cls()
    assert panel.source_ids == [1] and panel.source_picker.items == ["/src.vfj [1]"]
    assert panel.destination_id == 2 and panel.names == ["A"] and panel_world.required == [2]
    assert (panel.mapping_table.item(0, 0).text(), panel.mapping_table.item(0, 1).text()) == ("Regular", "Regular")
    assert "1 destination glyphs selected" in panel.status.text()
    assert len(panel_world.guarded) == 8
    panel_world.guarded[0]()  # button callbacks resolve to the bound action
    panel.invalidate()
    assert panel.plan_data is None and panel.preview_field.text() == ""


def test_panel_when_no_package_then_error(panel_world, monkeypatch):
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="destination font"):
        panel_world.cls()


def test_panel_when_preview_inputs_bad_then_refused(panel_world):
    panel = panel_world.cls()
    panel.source_picker.setCurrentIndex(5)
    with pytest.raises(ValueError, match="another open source font"):
        panel.preview_copy()
    panel.source_picker.setCurrentIndex(0)
    panel.add_mapping()
    assert panel.mapping_table.rowCount == 2
    with pytest.raises(ValueError, match="Fill both"):
        panel.preview_copy()


def test_panel_when_preview_then_plan_text_and_copy_applies(panel_world, mod, monkeypatch):
    panel = panel_world.cls()
    panel.mode_picker.addItems(list(mod.MODES))
    panel.mode_picker.setCurrentIndex(0)
    seen = {}
    rows = [{"name": "A", "source": "Light", "target": "Regular", "mask_name": None, "note": ""},
            {"name": "B", "source": "Light", "target": "Regular", "mask_name": "mask.Regular", "note": "locked"}]
    monkeypatch.setattr(mod, "make_plan", lambda *a: seen.setdefault("args", a) and {"rows": rows})
    monkeypatch.setattr(mod, "apply_plan", lambda plan, ok: {"changed": 1, "kept": 1, "pending_note": "later"})
    panel.mapping_table.setItem(0, 0, _Widget("Light"))
    panel.preview_copy()
    assert seen["args"][:4] == (1, 2, ["A"], [("Light", "Regular")])
    assert panel.preview_field.text() == "A / Light -> Regular: Copy\nB / Light -> mask.Regular: Kept: locked"
    panel.confirm_box.setChecked(True)
    panel.copy_rows()
    assert panel.status.text() == "Copied 1 layers; kept 1. One Undo step. · later"
    assert panel.plan_data is None and not panel.confirm_box.isChecked()
    with pytest.raises(ValueError, match="Preview first"):
        panel.copy_rows()


def test_panel_when_copy_fails_then_plan_discarded(panel_world, mod, monkeypatch):
    panel = panel_world.cls()
    panel.plan_data = {"rows": []}
    monkeypatch.setattr(mod, "apply_plan", lambda plan, ok: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(ValueError, match="bad"):
        panel.copy_rows()
    assert panel.plan_data is None


def test_panel_when_lab_hooks_present_then_called(panel_world):
    calls = []

    class Lab(panel_world.cls):
        def lab_refresh_preview(self):
            calls.append("refresh")

        def lab_check_target(self):
            calls.append("check")

    lab = Lab()
    with pytest.raises(ValueError, match="Preview first"):
        lab.copy_rows()
    assert calls == ["refresh", "check"]


def test_panel_when_closed_then_script_dialog_closed(panel_world, mod):
    panel = panel_world.cls()
    panel.closeEvent("evt")
    assert panel_world.closed == [("evt", mod.KEY)]


def test_main_when_show_fails_then_title_printed(mod, monkeypatch, capsys):
    import fontlabapp.core.scripting as scripting

    seen = []
    monkeypatch.setattr(mod, "panel_type", lambda: "panel")
    monkeypatch.setattr(scripting, "show_script_dialog", lambda panel, key: seen.append((panel, key)))
    mod.main()
    assert seen == [("panel", mod.KEY)]
    monkeypatch.setattr(scripting, "show_script_dialog", lambda panel, key: (_ for _ in ()).throw(ValueError("nope")))
    mod.main()
    assert capsys.readouterr().out == f"{mod.TITLE}: nope\n"


def capture_commit(monkeypatch, applied, after=None):
    """Replace history.commit by one that records the Undo layer set and the read-back result."""
    import fontlabapp.core.history.glyphs as history

    seen = NS(existing=None, missed=None, retain=None)

    def commit(title, existing, owners, mutate, **kw):
        seen.existing = list(existing)
        seen.retain = kw.get("retain")
        mutate()
        if after:
            after()
        seen.missed = kw["read_back"]()
        return Commit()

    monkeypatch.setattr(history, "commit", commit)
    return seen


def test_apply_plan_when_new_mask_then_body_in_undo_set_and_read_back_checks_mask(mod, applied, monkeypatch):
    plan = plan_for(mod, applied, [("Light", "Regular")], "Mask")
    glyph = applied.dst._glyphs["A"]
    body = glyph.layers[0]
    original = body.getMaskLayer

    def attach(create):
        had = body.mask is not None
        layer = original(create)
        if layer is not None and not had:
            glyph.layers.append(layer)
        return layer

    body.getMaskLayer = attach
    seen = capture_commit(monkeypatch, applied)
    mod.apply_plan(plan, True)
    assert seen.existing == [body]  # a new mask: the body is what Undo must cover
    assert seen.missed == []  # read-back compared the mask (the body differs from the data)
    assert body.anchors[0].point.x() == 0 and glyph.findLayer("mask.Regular").anchors[0].point.x() == 5


def test_apply_plan_when_mask_exists_then_only_mask_in_undo_set(mod, applied, monkeypatch):
    glyph = applied.dst._glyphs["A"]
    body = glyph.layers[0]
    mask = body.getMaskLayer(True)
    glyph.layers.append(mask)
    plan = plan_for(mod, applied, [("Light", "Regular")], "Mask")
    seen = capture_commit(monkeypatch, applied)
    mod.apply_plan(plan, True)
    assert seen.existing == [mask] and seen.missed == []


def test_apply_plan_when_target_or_backup_becomes_null_then_read_back_names_them(mod, applied, monkeypatch):
    plan = plan_for(mod, applied, [("Light", "Regular")], "Destination + suffix", ".b")
    glyph = applied.dst._glyphs["A"]

    def after():
        glyph.findLayer("Regular").isNull = True
        glyph.findLayer("Regular.b").isNull = True

    seen = capture_commit(monkeypatch, applied, after)
    mod.apply_plan(plan, True)
    assert seen.missed == ["A/Regular", "backup differs: A"]


def test_apply_plan_when_anchors_differ_then_only_changed_set_and_stale_removed(mod, applied, monkeypatch):
    import fontlabapp.anchors.writer as anchors

    glyph = applied.dst._glyphs["A"]
    target = glyph.layers[0]
    target.anchors = [anchor("top", 5, 6), anchor("moved", 1, 1), anchor("stale", 9, 9)]
    applied.src._glyphs["A"].layers[0].anchors = [anchor("top", 5, 6), anchor("moved", 2, 2), anchor("new", 3, 3)]
    plan = plan_for(mod, applied, [("Light", "Regular")])
    edits = []
    real = anchors.prepare
    monkeypatch.setattr(anchors, "prepare", lambda stage, e: edits.extend(e) or real(stage, e))
    mod.apply_plan(plan, True)
    assert sorted(edits) == [("remove", "stale", None), ("set", "moved", (2, 2)), ("set", "new", (3, 3))]


def test_apply_plan_when_anchor_removed_then_its_pin_is_retained_for_undo(mod, applied, monkeypatch):
    glyph = applied.dst._glyphs["A"]
    target = glyph.layers[0]
    target.anchors = [anchor("top", 5, 6), anchor("stale", 9, 9)]
    applied.src._glyphs["A"].layers[0].anchors = [anchor("top", 5, 6)]
    plan = plan_for(mod, applied, [("Light", "Regular")])
    seen = capture_commit(monkeypatch, applied)
    mod.apply_plan(plan, True)
    assert "stale" in seen.retain  # the fake native names a removed pin by its anchor name


def test_apply_plan_when_mask_layer_is_null_then_treated_as_missing_and_recreated(mod, applied, monkeypatch):
    glyph = applied.dst._glyphs["A"]
    body = glyph.layers[0]
    mask = body.getMaskLayer(True)
    glyph.layers.append(mask)
    mask.isNull = True
    plan = plan_for(mod, applied, [("Light", "Regular")], "Mask")
    seen = capture_commit(monkeypatch, applied)
    with pytest.raises(RuntimeError, match="FontLab did not attach the target layer."):
        mod.apply_plan(plan, True)  # fake FontLab keeps the mask null, so creation is reported failed
    assert seen.existing == [body]  # null mask is not in the Undo set; the body is
