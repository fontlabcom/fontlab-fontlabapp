# this_file: tests/test_wp05_route_behaviour_g14.py
# SPDX-License-Identifier: Apache-2.0
"""Independent behaviour, refusals and installed public helper checks."""

import importlib.util
import inspect
import math
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any
from unittest.mock import create_autospec

import pytest
from _wp05_scriptmix_shim import real_app  # noqa: F401

ROOT = Path(__file__).parents[1]
PATHS = [
    ROOT / "Scripts" / part
    for part in (
        "Contours/Myanmar Medial Ra Maker.py",
        "Features/Nastaliq Connection Editor.py",
    )
]


FAKED_SIGNATURES: list[tuple[str, str, Any, Any]] = []


def patch_api(monkeypatch: Any, module: Any, name: str, implementation: Any) -> Any:
    """Check every fake against the installed function and enforce its call shape."""
    original = getattr(module, name)
    replacement = create_autospec(original, spec_set=True, side_effect=implementation)
    FAKED_SIGNATURES.append(
        (
            module.__name__,
            name,
            inspect.signature(original),
            inspect.signature(replacement),
        )
    )
    assert inspect.signature(replacement) == inspect.signature(original)
    monkeypatch.setattr(module, name, replacement)
    return replacement


def load(index: int) -> Any:
    source = ROOT / "src/fontlabapp/studios/shape_generators/myanmar.py" if index == 0 else PATHS[index]
    spec = importlib.util.spec_from_file_location(f"g14_{index}", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module








@pytest.mark.parametrize(
    "values,count,wanted",
    [
        ([100, 110, 500, 510], 2, [100, 500]),
        ([200, 200], 5, [200]),
        ([123], 1, [120]),
        ([310, 100, 110, 300], 2, [100, 300]),
        ([100, 200, 300], 9, [100, 200, 300]),
    ],
)
def test_width_classes(values: Any, count: Any, wanted: Any) -> None:
    assert load(0).width_classes(values, count) == wanted


@pytest.mark.parametrize(
    "values,count",
    [([], 5), ([0], 1), ([-1], 1), ([math.nan], 1), ([math.inf], 1), ([100], 0)],
)
def test_bad_widths(values: Any, count: Any) -> None:
    with pytest.raises(ValueError):
        load(0).width_classes(values, count)


@pytest.mark.parametrize(
    "variant,indices",
    [
        ("", [0, 1, 2, 3, 4]),
        (".notop", [0, 3, 4]),
        (".notophook", [0, 1, 3, 4]),
        (".nobottom", [0, 1, 2]),
        (".nobottomhook", [0, 1, 2, 3]),
        (".notop.nobottom", [0]),
        (".notophook.nobottom", [0, 1]),
        (".notop.nobottomhook", [0, 3]),
        (".notophook.nobottomhook", [0, 1, 3]),
    ],
)
def test_ra_pieces(variant: Any, indices: Any) -> None:
    assert load(0).piece_indices(variant) == indices


def test_endpoint_stretch_and_hook_shift() -> None:
    m = load(0)
    points = [(0, 0), (10, 20), (30, 40)]
    assert m.piece_points(points, 1, 40) == [(20, 0), (10, 20), (50, 40)]
    assert m.piece_points(points, 2, 40) == [(20, 0), (50, 20), (50, 40)]
    assert m.piece_points(points, 0, 40) == points
    assert m.piece_points(points, 4, 0) == points


















class Matrix:
    """Small native matrix fake; enough for the real contour copier."""

    def __init__(self, *values: Any) -> None:
        self.values = values or (1, 0, 0, 1, 0, 0)

    def map(self, path: Any) -> Any:
        return (path, self.values)


class Node:
    """Optional native constructor arguments must be keywords."""

    def __init__(self, point: Any, *, nodeType: Any = "on") -> None:
        self.x, self.y = point
        self.kind = nodeType
        self.name, self.nodeState = "corner", 0x100 | 0x20

    def isOn(self) -> Any:
        return self.kind == "on"


class Contour:
    """Detached-copy fake deliberately drops raw flags to test the App repair."""

    def __init__(self, points: Any, *, closed: Any = True) -> None:
        self.points = [Node(p) for p in points]
        self.closed = closed

    def nodes(self) -> Any:
        return self.points

    def cloneMapped(self, matrix: Any) -> Any:
        a, b, c, d, dx, dy = matrix.values
        result = Contour(
            [(n.x * a + n.y * c + dx, n.x * b + n.y * d + dy) for n in self.points],
            closed=self.closed,
        )
        for node in result.points:
            node.name, node.nodeState = "", 0
        return result


class Shape:
    def __init__(self, contours: Any = ()) -> None:
        self.contours = list(contours)
        self.isComponent = False
        self.transform = Matrix()

    def addContours(self, contours: Any, closed: Any) -> Any:
        self.contours.extend(contours)


class Layer:
    def __init__(
        self, name: Any = "Regular", contours: Any = (), width: Any = 100
    ) -> None:
        self.name, self.advanceWidth = name, width
        self.shapes = [Shape(contours)] if contours else []
        self.isNull = self.autoLayer = self.isMaskLayer = self.isService = False
        self.recipe, self.anchors = "", []
        self.history = []
        self.boundingBox = NS(x=lambda: 0, width=lambda: 210)

    def checkInitHistoryState(self, index: Any) -> Any:
        self.history.append(index)

    def addShape(self, shape: Any) -> Any:
        self.shapes.append(shape)


class Glyph:
    def __init__(self, name: Any, layer: Any) -> None:
        self.name, self.layers, self.isNull = name, [layer], False
        self.history = []

    def findLayer(self, name: Any) -> Any:
        return next((layer for layer in self.layers if layer.name == name), None)

    def checkInitHistoryState(self, index: Any) -> Any:
        self.history.append(index)


def template(master: str = "Regular", right: float = 200, advance: float = 50) -> Layer:
    def rectangle(
        x: float, y: float, width: float, height: float, rail: bool = False
    ) -> Contour:
        points = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
        if rail:
            points = [points[1], points[0], points[3], points[2]]
        return Contour(points)

    result = Layer(
        name=master,
        contours=[
            rectangle(0, -150, 20, 650),
            rectangle(0, 400, right, 10, True),
            rectangle(right, 300, 10, 150),
            rectangle(0, 0, right, 10, True),
            rectangle(right, -100, 10, 150),
        ],
        width=advance,
    )
    result.boundingBox = NS(x=lambda: 0, width=lambda: right + 10)
    return result


@pytest.fixture
def drawing_environment(monkeypatch: Any) -> Any:
    import fly

    qt = NS(QtGui=NS(QTransform=Matrix))
    monkeypatch.setitem(fly.__dict__, "qt", qt)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)


def test_template_measure_and_copy_preserve_source(drawing_environment: Any) -> None:
    m = load(0)
    layer = template()
    copies, enclosure = m.template_contours(layer)
    assert enclosure == 180
    assert copies[0] is not layer.shapes[0].contours[0]
    assert copies[0].nodes()[0].nodeState == 0x100
    assert copies[0].nodes()[0].name == "corner"
    assert layer.shapes[0].contours[0].nodes()[0].nodeState == 0x120


@pytest.mark.parametrize(
    "damage", ["auto", "open", "count", "endpoint", "vertical", "service", "advance"]
)
def test_bad_template_refused(drawing_environment: Any, damage: Any) -> None:
    layer = template()
    if damage == "auto":
        layer.autoLayer = True
    elif damage == "open":
        layer.shapes[0].contours[0].closed = False
    elif damage == "count":
        layer.shapes[0].contours.pop()
    elif damage == "endpoint":
        layer.shapes[0].contours[1].nodes()[0].x += 1
    elif damage == "vertical":
        layer.shapes[0].contours[0].nodes()[2].x += 1
    elif damage == "advance":
        layer.advanceWidth = math.inf
    else:
        layer.isService = True
    with pytest.raises(ValueError):
        load(0).template_contours(layer)


def package_with_template() -> Any:
    glyphs = {"ra": Glyph("ra", template()), "ka": Glyph("ka", Layer(width=300))}
    package = NS(
        master="Regular", masters=["Regular"], id=11, fgId=987, findName=glyphs.get
    )
    return package, glyphs


def test_ra_survey_and_jobs_keep_existing_continue_others(
    drawing_environment: Any,
) -> None:
    import fly.ap.core.history.glyphs as history

    package, glyphs = package_with_template()
    glyphs["medial-ra.w300"] = Glyph("medial-ra.w300", Layer())
    records = [NS(name="ka", unicodes=[0x1000])]
    rows = load(0).survey(package, "ra", records, 5, history.auto_facts([]), False)
    assert len(rows) == 17
    assert rows[0].target == "medial-ra.w300" and rows[0].note == "kept: name exists"
    jobs = load(0).prepare(rows)
    assert len(jobs) == 16
    assert jobs[0][0] == "medial-ra.w300.notop"
    assert len(jobs[0][1][0][1]) == 3
    assert jobs[0][1][0][2] == 50
    # Final unstretched variants must never inherit the last clustered extension.
    assert jobs[-1][0] == "medial-ra.notophook.nobottomhook"
    assert jobs[-1][1][0][1][1].nodes()[0].x == 200
    assert glyphs["ra"].layers[0].shapes[0].contours[1].nodes()[0].x == 200


def test_ra_auto_candidates_need_consent(drawing_environment: Any) -> None:
    import fly.ap.core.history.glyphs as history

    m = load(0)
    package, glyphs = package_with_template()
    automatic = Layer()
    automatic.autoLayer = True
    glyphs["ka.notop"] = Glyph("ka.notop", automatic)
    facts = history.auto_facts([("ka.notop", True, ())])
    records = [NS(name="ka", unicodes=[0x1000])]
    rows = m.survey(package, "ra", records, 5, facts, False)
    kept = next(row for row in rows if row.target == "medial-ra.notop")
    assert "may rebuild auto ka.notop" in kept.note
    assert kept.rebuild == ("ka.notop",)
    consented = m.survey(package, "ra", records, 5, facts, True)
    assert not next(row for row in consented if row.target == kept.target).note


def test_ra_empty_consonant_set_still_makes_omission_variants(
    drawing_environment: Any,
) -> None:
    import fly.ap.core.history.glyphs as history

    package, _ = package_with_template()
    rows = load(0).survey(package, "ra", [], 5, history.auto_facts([]), False)
    assert len([row for row in rows if not row.note]) == 8
    assert "no consonant widths" in rows[0].note


@pytest.mark.parametrize("write_fails", [False, True])
def test_ra_real_creation_and_geometry_history(
    drawing_environment: Any, monkeypatch: Any, write_fails: bool
) -> None:
    import fly.ap.core.edit_guards as edit_guards  # noqa: PLR0402 - avoid native parent fallback
    import fly.ap.core.history.glyphs as history
    import fly.ap.glyphs.copies as glyph_copies
    import fly.ap.glyphs.creation as glyph_creation

    package, glyphs = package_with_template()
    add_bold_master(package, glyphs)
    notifications, calls = [], []

    class FailingShape(Shape):
        def addContours(self, contours: Any, closed: Any) -> None:
            raise RuntimeError("outline insertion failed")

    native = NS(
        flShape=FailingShape if write_fails else Shape,
        flItems=lambda: NS(
            notifyChangesApplied=lambda title, objects: notifications.append(objects)
        ),
    )

    def add(command: Any, **kwargs: Any) -> Any:
        calls.append((command, kwargs))
        data = kwargs["glyph_data"]
        layers = [
            Layer(name=row["name"], width=row["advanceWidth"]) for row in data["layers"]
        ]
        glyphs[data["name"]] = Glyph(data["name"], layers[0])
        glyphs[data["name"]].layers = layers
        return {"status": "ok", "created": True}

    patch_api(monkeypatch, edit_guards, "pending_updates", lambda *a: ())
    patch_api(monkeypatch, edit_guards, "canvas_glyphs", lambda *a, **k: None)  # Font window active
    patch_api(monkeypatch, glyph_creation, "_native", lambda name: NS(call=add))
    patch_api(monkeypatch, glyph_copies, "_native", lambda name: native)
    patch_api(
        monkeypatch,
        history,
        "_native",
        lambda name: (
            native
            if name == "fontlab"
            else NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: 42)))
        ),
    )
    facts = history.auto_facts([])
    rows = load(0).survey(
        package, "ra", [NS(name="ka", unicodes=[0x1000])], 5, facts, False
    )
    jobs = load(0).prepare(rows)[:2]
    if write_fails:
        with pytest.raises(
            history.PartialWriteError,
            match="Native changes may remain; use Edit > Undo",
        ):
            glyph_copies.create(package, jobs, "Medial ra", facts)
    else:
        result = glyph_copies.create(package, jobs, "Medial ra", facts)
        assert result == {"pending_note": "", "glyphs": 2, "layers": 4, "mismatches": [], "pending_updates": ()}
    assert len(calls) == 2
    for command, kwargs in calls:
        assert command == "set_glyph" and kwargs["create"] is True
        assert kwargs["font_id"] == 987 and kwargs["font_id"] != package.id
        assert kwargs["glyph_data"]["layers"] == [
            {"name": "Regular", "advanceWidth": 50},
            {"name": "Bold", "advanceWidth": 75},
        ]
    made = [glyphs[job[0]] for job in jobs]
    assert notifications == [[*(layer for g in made for layer in g.layers), *made]]
    assert all(not layer.autoLayer for layer in notifications[0][:4])
    assert all(
        g.history == [0] and all(layer.history == [0] for layer in g.layers)
        for g in made
    )










def test_keyword_only_native_fakes() -> None:
    with pytest.raises(TypeError):
        Node((0, 0), "off")
    with pytest.raises(TypeError):
        Contour([], True)


class Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback: Any) -> Any:
        self.callbacks.append(callback)

    def emit(self) -> Any:
        for callback in self.callbacks:
            callback()


class Widget:
    """Reject common QWidget member collisions, as PythonQt does."""

    forbidden = frozenset(
        {"render", "size", "layout", "update", "font", "move", "statusBar"}
    )

    def __init__(self, *args: Any) -> None:
        self.items, self.currentIndex, self.blocked = [], -1, False
        self.currentIndexChanged, self.clicked, self.valueChanged, self.toggled = (
            Signal(),
            Signal(),
            Signal(),
            Signal(),
        )
        self.checked = False
        self.text = args[0] if args else ""
        self.enabled, self.value, self.panels = True, 0, []

    def __setattr__(self, name: Any, value: Any) -> Any:
        if name in self.forbidden:
            raise AttributeError(f"Native member cannot be overwritten: {name}")
        object.__setattr__(self, name, value)

    @property
    def currentText(self) -> Any:
        return (
            self.items[self.currentIndex]
            if 0 <= self.currentIndex < len(self.items)
            else ""
        )

    @property
    def count(self) -> Any:
        return len(self.items)

    def setCurrentIndex(self, index: Any) -> Any:
        self.currentIndex = index
        if not self.blocked:
            self.currentIndexChanged.emit()

    def blockSignals(self, value: Any) -> Any:
        self.blocked = value

    def clear(self) -> Any:
        self.items, self.currentIndex = [], -1

    def addItems(self, values: Any) -> Any:
        self.items.extend(values)
        if self.currentIndex < 0 and self.items:
            self.currentIndex = 0

    def setText(self, text: Any) -> Any:
        self.text = text

    def setPlainText(self, text: Any) -> Any:
        self.text = text

    def setEnabled(self, value: Any) -> Any:
        self.enabled = value

    def setReadOnly(self, value: Any) -> Any:
        self.readonly = value

    def setWordWrap(self, value: bool) -> None:
        self.wrap = value

    def isChecked(self) -> bool:
        return self.checked

    def setChecked(self, value: bool) -> None:
        self.checked = value
        if not self.blocked:
            self.toggled.emit()

    def setMinimumWidth(self, value: Any) -> Any:
        self.minimum_width = value

    def addWidget(self, *args: Any) -> Any:
        pass

    def addLayout(self, *args: Any) -> Any:
        pass

    def set_panels(self, panels: Any) -> Any:
        self.panels = panels

    def setRange(self, minimum: Any, maximum: Any) -> Any:
        self.limits = (minimum, maximum)

    def setValue(self, value: Any) -> Any:
        self.value = value


@pytest.fixture
def connection_panel(monkeypatch: Any) -> Any:
    import fly
    import fly.ap.anchors.writer as anchor_writer
    import fly.ap.core.scripting as scripting  # noqa: PLR0402 - avoid native parent fallback
    import fly.fp.feature_blocks as feature_blocks  # noqa: PLR0402 - avoid native parent fallback

    layer = Layer()
    layer.preview_anchors = {"entry": (100, 200), "exit": (40, 70)}
    glyphs = {
        name: Glyph(name, layer) for name in ("BEm1", "BEm2", "BEm10", "BEi1", "BEf1")
    }
    package = NS(id=11, master="Regular", masters=["Regular"], findName=glyphs.get)
    state = NS(source={"prefix": "# retain\n", "features": []}, active=True, writes=[])

    class Base(Widget):
        def __init__(
            self, parent: Any = None, *, title: str, subtitle: str, key: str
        ) -> None:
            Widget.__init__(self)
            self.package, self.package_id = package, 11
            self.font_data = NS(glyphs=[NS(name=name) for name in glyphs])
            self.apply_button, self.status = Widget(), Widget()
            self.setup()
            self.refresh()

        def prepare(self) -> Any:
            return Widget()

        def _connect(self, signal: Any, callback: Any) -> Any:
            signal.connect(callback)

        def ensure_font(self) -> Any:
            if not state.active:
                raise ValueError("Activate the original font")

        def ensure_preview(self) -> Any:
            self.ensure_font()
            if not self._preview_valid:
                raise ValueError("No valid preview")

    gui = NS(
        **dict.fromkeys(
            (
                "QComboBox",
                "QHBoxLayout",
                "QLabel",
                "QPlainTextEdit",
                "QPushButton",
                "QCheckBox",
            ),
            Widget,
        )
    )
    gui.QTransform = Matrix
    monkeypatch.setitem(fly.__dict__, "qt", NS(QtGui=gui))
    patch_api(monkeypatch, scripting, "features_dialog_type", lambda: Base)
    patch_api(
        monkeypatch, scripting, "anchors_view_types", lambda: NS(AttachmentView=Widget)
    )
    api = scripting.anchors_api()
    patch_api(monkeypatch, api, "glyph_path", lambda layer: "outline")
    patch_api(
        monkeypatch, anchor_writer, "anchor_points", lambda layer: layer.preview_anchors
    )
    patch_api(
        monkeypatch, feature_blocks, "read_feature_blocks", lambda package: state.source
    )

    def write(package: Any, expected: Any, updated: Any, **kwargs: Any) -> Any:
        assert expected == state.source, "Writer must see the exact source snapshot"
        state.writes.append(kwargs)
        state.source = updated
        return {"changed": 1}

    patch_api(monkeypatch, feature_blocks, "write_feature_blocks", write)
    panel_class = load(1).panel_type()
    return panel_class(), panel_class, state, glyphs












@pytest.mark.parametrize("name", sorted(Widget.forbidden))
def test_widget_fake_rejects_native_collisions(name: Any) -> None:
    with pytest.raises(AttributeError):
        setattr(Widget(), name, object())


def test_creation_panel_uses_shared_hooks(
    monkeypatch: Any, drawing_environment: Any
) -> None:
    import fly
    import fly.ap.core.history.glyphs as history
    import fly.ap.glyphs.copies as glyph_copies

    class Base(Widget):
        def add_row(self, *args: Any) -> Any:
            pass

        def watch(self, signal: Any, callback: Any = None) -> Any:
            pass

        def refresh(self) -> None:
            pass

        def font_package(self) -> Any:
            return package

        def consented(self) -> bool:
            return False

        def plan(self) -> list[Any]:
            return self.survey(self.font_package(), history.auto_facts([]), False)

    package, _glyphs = package_with_template()
    patch_api(monkeypatch, glyph_copies, "panel_type", lambda: Base)
    monkeypatch.setitem(
        fly.__dict__,
        "qt",
        NS(QtGui=NS(QSpinBox=Widget, QPushButton=Widget, QTransform=Matrix)),
    )
    monkeypatch.setitem(fly.__dict__, "ap", sys.modules["fontlabapp"])
    monkeypatch.setitem(
        sys.modules["fontlabapp"].__dict__,
        "fontlab",
        NS(CurrentFont=lambda: NS(glyphs=[
            NS(name="ka", unicodes=[0x1000]), NS(name="ra", unicodes=[0x103C])
        ])),
    )
    monkeypatch.setitem(sys.modules, "PythonQt", fly.qt)
    monkeypatch.setitem(sys.modules, "fontlab", sys.modules["fontlabapp"].fontlab)
    ra = load(0).panel_type()()
    ra.names = ["ra"]
    ra.build_controls()
    assert ra.group_count.limits == (1, 5) and ra.group_count.value == 5
    rows = ra.survey(package, history.auto_facts([]), False)
    assert len(ra.jobs(rows)) == 17
    assert "create on 1 masters" in ra.cells(rows[0])[2]
    assert "Regular: +120" in ra.cells(rows[0])[1]
    assert "each" in ra.intro().lower()
    ra.names = ["ra", "ka"]
    assert (
        "select exactly one"
        in ra.plan()[0].note
    )
    assert ra.names == ["ra", "ka"], "Keep an explicit multi-selection for the refusal"
    ra.names = []
    assert len(ra.jobs(ra.plan())) == 17
    assert ra.names == ["ra"], "Only an empty selection uses the encoded template"
    ra.names = ["ra"]
    add_bold_master(package, _glyphs)
    rows = ra.survey(package, history.auto_facts([]), False)
    ra.rows = rows
    assert "Regular: +120; Bold: +280" in ra.cells(rows[0])[1]
    assert "Bold: [0, -150, 530, 500]" in ra.cells(rows[0])[2]
    _glyphs["ka"].layers[0].advanceWidth += 10
    updated = ra.survey(package, history.auto_facts([]), False)
    with pytest.raises(ValueError, match="Press Preview"):
        ra.write(package, updated)
    ra.rows = updated
    facts = history.auto_facts([])
    patch_api(monkeypatch, history, "scan_auto_facts", lambda package: facts)
    writes = []

    def create(
        package: Any, jobs: Any, title: Any, facts: Any, *, allow_rebuild: bool = False
    ) -> dict[str, Any]:
        writes.append((jobs, allow_rebuild))
        return {"glyphs": len(jobs), "layers": len(jobs) * 2, "mismatches": []}

    patch_api(monkeypatch, glyph_copies, "create", create)
    result = ra.write(package, updated)
    assert result["glyphs"] == 17 and result["layers"] == 34
    assert all(
        [master for master, _, _ in layers] == ["Regular", "Bold"]
        for _, layers in writes[0][0]
    )
    assert writes[0][1] is False










def test_membership_stays_attached_to_current_master_groups() -> None:
    groups = load(0).width_groups([("a", 300), ("b", 310), ("c", 600), ("d", 610)], 2)
    assert groups == [(300, ("a", "b")), (600, ("c", "d"))]


def test_swapped_roles_and_wrong_stretch_side_are_refused(
    drawing_environment: Any,
) -> None:
    m = load(0)
    for error in ("swapped", "side"):
        layer = template()
        if error == "swapped":
            pieces = layer.shapes[0].contours
            pieces[1], pieces[2] = pieces[2], pieces[1]
        else:
            nodes = layer.shapes[0].contours[1].points
            layer.shapes[0].contours[1].points = nodes[2:] + nodes[:2]
        with pytest.raises(ValueError, match="piece"):
            m.template_contours(layer)


def add_bold_master(package: Any, glyphs: dict[str, Any]) -> None:
    package.masters.append("Bold")
    glyphs["ra"].layers.append(template("Bold", 240, 75))
    glyphs["ka"].layers.append(Layer("Bold", width=500))


def test_multimaster_same_members_have_own_extension_and_advance(
    drawing_environment: Any,
) -> None:
    import fly.ap.core.history.glyphs as history

    package, glyphs = package_with_template()
    add_bold_master(package, glyphs)
    m = load(0)
    rows = m.survey(
        package,
        "ra",
        [NS(name="ka", unicodes=[0x1000])],
        5,
        history.auto_facts([]),
        False,
    )
    assert not rows[0].note
    assert rows[0].extensions == (("Regular", 120), ("Bold", 280))
    assert rows[0].members == ("ka",)
    job = m.prepare(rows[:1])[0]
    assert [(master, width) for master, _, width in job[1]] == [
        ("Regular", 50),
        ("Bold", 75),
    ]
    regular, bold = job[1][0][1], job[1][1][1]
    assert regular[1].nodes()[0].x == 260
    assert bold[1].nodes()[0].x == 380
    assert rows[0].bounds == (
        ("Regular", (0, -150, 330, 500)),
        ("Bold", (0, -150, 530, 500)),
    )


@pytest.mark.parametrize("damage", ["missing", "swapped", "side"])
def test_bad_master_keeps_every_target_glyph(
    drawing_environment: Any, damage: str
) -> None:
    import fly.ap.core.history.glyphs as history

    package, glyphs = package_with_template()
    add_bold_master(package, glyphs)
    if damage == "missing":
        glyphs["ra"].layers.pop()
    else:
        pieces = glyphs["ra"].layers[1].shapes[0].contours
        if damage == "swapped":
            pieces[1], pieces[2] = pieces[2], pieces[1]
        else:
            pieces[1].points = pieces[1].points[2:] + pieces[1].points[:2]
    m = load(0)
    rows = m.survey(
        package,
        "ra",
        [NS(name="ka", unicodes=[0x1000])],
        5,
        history.auto_facts([]),
        False,
    )
    assert len(rows) == 17 and all(row.target for row in rows)
    assert all(row.note.startswith("kept:") and "Bold" in row.note for row in rows)
    assert m.prepare(rows) == []


def test_small_width_group_is_named_and_kept_not_silently_dropped(
    drawing_environment: Any,
) -> None:
    import fly.ap.core.history.glyphs as history

    package, glyphs = package_with_template()
    glyphs["ka"].layers[0].advanceWidth = 100
    rows = load(0).survey(
        package,
        "ra",
        [NS(name="ka", unicodes=[0x1000])],
        5,
        history.auto_facts([]),
        False,
    )
    assert len(rows) == 17
    assert rows[0].target == "medial-ra.w100"
    assert "w100: not wider than the template enclosure (180)" in rows[0].note
    assert rows[0].extensions == (("Regular", -80),)
    assert len([row for row in rows if not row.note]) == 8


def test_missing_consonant_in_one_master_keeps_group_only(
    drawing_environment: Any,
) -> None:
    import fly.ap.core.history.glyphs as history

    package, glyphs = package_with_template()
    add_bold_master(package, glyphs)
    glyphs["ka"].layers.pop()
    rows = load(0).survey(
        package,
        "ra",
        [NS(name="ka", unicodes=[0x1000])],
        5,
        history.auto_facts([]),
        False,
    )
    assert all("Bold" in row.note and "ka" in row.note for row in rows[:9])
    assert all(not row.note for row in rows[9:])


def test_current_master_membership_is_reused_after_other_master_order_changes(
    drawing_environment: Any,
) -> None:
    import fly.ap.core.history.glyphs as history

    package, glyphs = package_with_template()
    add_bold_master(package, glyphs)
    for name, regular, bold in (
        ("a", 300, 800),
        ("b", 310, 400),
        ("c", 600, 1000),
        ("d", 610, 300),
    ):
        glyph = Glyph(name, Layer("Regular", width=regular))
        glyph.layers.append(Layer("Bold", width=bold))
        glyphs[name] = glyph
    records = [NS(name=name, unicodes=[0x1000 + i]) for i, name in enumerate("abcd")]
    rows = load(0).survey(package, "ra", records, 2, history.auto_facts([]), False)
    assert rows[0].members == ("a", "b")
    assert rows[0].extensions == (("Regular", 125), ("Bold", 380))
    assert rows[9].members == ("c", "d")
    assert rows[9].extensions == (("Regular", 425), ("Bold", 430))


def test_default_source_is_encoded_medial_ra() -> None:
    m = load(0)
    assert m.default_source([NS(name="ra", unicodes=[0x103C])]) == "ra"
    assert m.default_source([NS(name="ka", unicodes=[0x1000])]) == ""


@pytest.mark.parametrize(
    "damage",
    ["short-stem", "top-below-bottom", "hook-left", "hook-inside-rail", "hook-side"],
)
def test_piece_roles_report_named_errors(drawing_environment: Any, damage: str) -> None:
    layer = template()
    pieces = layer.shapes[0].contours
    if damage == "short-stem":
        for node in pieces[0].nodes():
            node.y /= 20
    elif damage == "top-below-bottom":
        pieces[1], pieces[3] = pieces[3], pieces[1]
        pieces[2], pieces[4] = pieces[4], pieces[2]
    elif damage == "hook-left":
        for node in pieces[2].nodes():
            node.x -= 250
    elif damage == "hook-inside-rail":
        for node in pieces[2].nodes():
            node.x -= 95
    else:
        pieces[2].points = pieces[2].points[2:] + pieces[2].points[:2]
    with pytest.raises(ValueError, match="piece"):
        load(0).template_contours(layer)


def test_different_master_node_topology_keeps_targets(drawing_environment: Any) -> None:
    import fly.ap.core.history.glyphs as history

    package, glyphs = package_with_template()
    add_bold_master(package, glyphs)
    glyphs["ra"].layers[1].shapes[0].contours[1].points.insert(2, Node((0, 405)))
    rows = load(0).survey(
        package,
        "ra",
        [NS(name="ka", unicodes=[0x1000])],
        5,
        history.auto_facts([]),
        False,
    )
    assert all(
        "Bold: template node topology differs from Regular" in row.note for row in rows
    )










