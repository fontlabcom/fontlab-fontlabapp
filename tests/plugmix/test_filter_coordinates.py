# this_file: tests/plugmix/test_filter_coordinates.py
"""Coordinate Filter dispatch through the real outline/layer writer kernels."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

import fontlabapp.contours.writer as outlines
import fontlabapp.core.history.glyphs as history
import fontlabapp.plugins.filters.apply as api
from fontlabapp.masters.layers import writer
from fontlabapp.masters.layers.selection import LayerOccurrence, LayerSelection
from fontlabapp.plugins import Filter, LayerEdit, snapshot


class Point:
    def __init__(self, x, y):
        self.values = x, y

    def x(self):
        return self.values[0]

    def y(self):
        return self.values[1]


class NativeNode:
    def __init__(self, i, record):
        self.id = i
        self.position = Point(record.x, record.y)
        self.nodeState = 2 if i == 1 else 1  # retain an actual quadratic kind
        self.selected, self.smooth = record.selected, record.smooth
        self.on = record.on_curve

    def isOn(self):
        return self.on


class Move(Filter):
    name, title = "move", "Move"

    def compute(self, before, values):
        return LayerEdit(
            contours=tuple(
                replace(c, nodes=tuple(replace(n, x=n.x + 10) for n in c.nodes))
                for c in before.contours
            )
        )


@pytest.fixture
def native(glyph, monkeypatch):
    nodes = [NativeNode(i, n) for i, n in enumerate(glyph.contours[0].nodes)]
    contour = NS(id=2, nodes=lambda: nodes, closed=True)
    transform = NS(
        **{
            k: lambda v=v: v
            for k, v in zip(
                ("m11", "m12", "m21", "m22", "dx", "dy"), (1, 0, 0, 1, 0, 0)
            )
        }
    )
    transform.map = lambda p: p
    shape = NS(
        id=3,
        contours=[contour],
        isComponent=False,
        shapeData=NS(referenceCount=1),
        transform=transform,
    )
    shape.removeContour = shape.contours.remove
    layer = NS(
        id=11,
        isValid=True,
        shapes=[shape],
        isNull=False,
        autoLayer=False,
        name="Regular",
        changed=lambda: None,
        update=lambda: True,
    )
    package = NS(id=1, isNull=False, master="Regular", glyphs={})
    package.findName = package.glyphs.get
    owner = NS(
        id=4,
        isNull=False,
        name="a",
        package=package,
        layers=[layer],
        findLayer=lambda master: layer,
    )
    package.glyphs[owner.name] = owner
    layer.glyph = owner
    selected = LayerSelection(
        (1, "Regular", "editor", 9), (LayerOccurrence(package, owner, layer, 0, 0),)
    )
    monkeypatch.setattr(
        snapshot,
        "capture",
        lambda source: replace(
            glyph, contours=snapshot._contours(source.layer, lambda read: list(read()))
        ),
    )
    monkeypatch.setattr(
        history, "scan_auto_facts", lambda package: history.auto_facts([])
    )
    commits = []

    def commit(title, layers, owners, mutate, **kwargs):
        commits.append(kwargs)
        mutate()
        return NS(mismatches=kwargs["read_back"](), pending_note="", pending_updates=())

    monkeypatch.setattr(history, "commit", commit)
    monkeypatch.setattr(api, "_native", lambda name: NS(QtCore=NS(QPointF=Point)))
    return NS(
        nodes=nodes,
        contour=contour,
        shape=shape,
        layer=layer,
        selected=selected,
        commits=commits,
        glyph=glyph,
    )


def run(native, plugin=None):
    return api.apply_filter(
        plugin or Move(),
        {},
        selected=native.selected,
        outlines=outlines,
        writer=writer,
        history=history,
    )


def test_dispatch_preserves_quadratic_kind_and_one_history_step(native):
    flags = [n.nodeState for n in native.nodes]
    plan, result = run(native)
    assert result["layers"] == 1 and len(plan.work) == 1
    assert [n.nodeState for n in native.nodes] == flags
    assert native.nodes[0].position.x() == 10
    assert len(native.commits) == 1
    assert native.commits[0]["retain"] == []
    assert native.commits[0]["operation"] == "geometry"


@pytest.mark.parametrize("edit", [LayerEdit(), "equal"])
def test_noop_never_opens_history(native, edit):
    plugin = Move()
    plugin.compute = lambda before, values: (
        LayerEdit(contours=tuple(replace(c) for c in before.contours))
        if edit == "equal"
        else edit
    )
    assert run(native, plugin)[1] is None
    assert native.commits == []


@pytest.mark.parametrize("kind", ["shared", "scaled", "rotated"])
def test_unsafe_owner_is_refused_without_history(native, kind):
    if kind == "shared":
        native.shape.shapeData.referenceCount = 2
    else:
        setattr(
            native.shape.transform, "m12" if kind == "rotated" else "m11", lambda: 2
        )
    plan, result = run(native)
    assert plan.refused == ["a"] and result is None and native.commits == []
    reason = "shared outline" if kind == "shared" else "scaled or rotated shape"
    assert [change.new for _, change in plan.rows] == [f"{reason}, skipped"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("selected", False),
        ("smooth", True),
        ("on_curve", False),
        ("x", float("nan")),
        ("y", float("inf")),
    ],
)
def test_invalid_node_result_is_rejected_before_history(native, field, value):
    plugin = Move()

    def compute(before, values):
        c = before.contours[0]
        return LayerEdit(
            contours=(
                replace(
                    c, nodes=(replace(c.nodes[0], **{field: value}),) + c.nodes[1:]
                ),
            )
        )

    plugin.compute = compute
    with pytest.raises(ValueError):
        run(native, plugin)
    assert native.commits == []


@pytest.mark.parametrize(
    "edit", ["advance", "anchors", "closed", "count", "mixed", "reorder"]
)
def test_reject_unsupported_results(glyph, edit):
    old = glyph.contours[0]
    before = replace(glyph, contours=(old, replace(old, closed=False)))
    cases = {
        "advance": LayerEdit(advance=glyph.advance),
        "anchors": LayerEdit(anchors=()),
        "closed": LayerEdit(contours=(replace(old, closed=False), before.contours[1])),
        "count": LayerEdit(contours=(replace(old, nodes=()), before.contours[1])),
        "mixed": LayerEdit(contours=(replace(old, nodes=()),)),
        "reorder": LayerEdit(contours=(before.contours[1], replace(old))),
    }
    with pytest.raises(ValueError):
        api._coordinates(before, cases[edit])


@pytest.mark.parametrize("mutation", ["position", "identity", "flags", "ownership"])
def test_prepare_staleness_has_no_writes_or_history(native, mutation):
    plan, facts = api.plan_filter(Move(), {}, native.selected, outlines, history)
    if mutation == "position":
        native.nodes[0].position = Point(90, 0)
    elif mutation == "identity":
        native.contour.id = 900
    elif mutation == "flags":
        native.nodes[0].nodeState = 99
    else:
        native.shape.shapeData.referenceCount = 2
    with pytest.raises(ValueError, match="stale"):
        writer.apply_work(plan.work, "Move", facts, api.LayerEditEditor(outlines))
    assert native.nodes[1].position.x() == 30 and native.commits == []


def test_readback_detects_native_setter_failure(native, monkeypatch):
    monkeypatch.setattr(
        api, "_native", lambda name: NS(QtCore=NS(QPointF=lambda x, y: Point(x + 1, y)))
    )
    with pytest.raises(Exception, match="coordinates or native node state"):
        run(native)
    assert len(native.commits) == 1


def test_deletion_dispatch_still_retains_contour(native):
    plugin = Move()
    plugin.compute = lambda before, values: LayerEdit(contours=())
    assert run(native, plugin)[1]["layers"] == 1
    assert native.shape.contours == []
    assert native.commits[0]["retain"] == [native.contour]


@pytest.fixture
def deletion(native):
    from fontlabapp.plugins.filters.delete_small_paths import DeleteSmallPaths

    def nodes(side, start):
        return [
            NativeNode(start + i, snapshot.Node(x, y, True, False))
            for i, (x, y) in enumerate(((0, 0), (side, 0), (side, side), (0, side)))
        ]

    native.nodes = nodes(10, 10)
    native.contour.nodes = lambda: native.nodes
    large = nodes(100, 20)
    native.large = NS(id=9, nodes=lambda: large, closed=True)
    native.shape.contours.append(native.large)
    native.layer.advanceWidth = 500
    native.layer.anchors = [NS(name="top", point=Point(50, 110))]
    native.plugin = DeleteSmallPaths()
    return native


@pytest.mark.parametrize("mutation", ["reorder", "replacement", "geometry", "flags"])
def test_deletion_stale_target_refuses_before_history_and_preserves_state(deletion, mutation):
    plan, facts = api.plan_filter(deletion.plugin, {}, deletion.selected, outlines, history)
    assert plan.rows[0][1].key == (0,)
    if mutation == "reorder":
        deletion.shape.contours.reverse()
    elif mutation == "replacement":
        deletion.shape.contours[0] = NS(id=90, nodes=deletion.large.nodes, closed=True)
    elif mutation == "geometry":
        deletion.nodes[1].position = Point(1000, 0)
    else:
        deletion.nodes[0].nodeState = 99
    before = api._native_state(deletion.layer)
    contours = tuple(deletion.shape.contours)
    with pytest.raises(ValueError):
        writer.apply_work(plan.work, "Delete", facts, api.LayerEditEditor(outlines))
    assert api._native_state(deletion.layer) == before
    assert tuple(deletion.shape.contours) == contours
    assert deletion.layer.advanceWidth == 500
    assert deletion.layer.anchors[0].point.values == (50, 110)
    assert deletion.commits == []


@pytest.mark.parametrize("mutation", ["reorder", "replacement", "geometry"])
def test_deletion_compute_mutation_refuses_before_history(deletion, mutation):
    plugin = Move()
    state = []

    def compute(before, values):
        edit = deletion.plugin.compute(before, values)
        if mutation == "reorder":
            deletion.shape.contours.reverse()
        elif mutation == "replacement":
            deletion.shape.contours[0] = NS(id=90, nodes=deletion.large.nodes, closed=True)
        else:
            deletion.nodes[1].position = Point(1000, 0)
        state.append(api._native_state(deletion.layer))
        return edit

    plugin.compute = compute
    with pytest.raises(ValueError):
        run(deletion, plugin)
    assert api._native_state(deletion.layer) == state[0]
    assert len(deletion.shape.contours) == 2 and deletion.commits == []


def test_unchanged_deletion_keeps_original_target_and_one_history_step(deletion):
    plan, result = run(deletion, deletion.plugin)
    assert result["layers"] == 1 and plan.rows[0][1].key == (0,)
    assert deletion.shape.contours == [deletion.large]
    assert len(deletion.commits) == 1
    assert deletion.commits[0]["retain"] == [deletion.contour]
    assert deletion.commits[0]["operation"] == "geometry"
    assert deletion.layer.advanceWidth == 500
    assert deletion.layer.anchors[0].point.values == (50, 110)


def test_unfenced_deletion_refuses_before_history(deletion):
    plan, facts = api.plan_filter(deletion.plugin, {}, deletion.selected, outlines, history)
    plan.work[0][2][0] = (0,)
    before = api._native_state(deletion.layer)
    with pytest.raises(ValueError):
        writer.apply_work(plan.work, "Delete", facts, api.LayerEditEditor(outlines))
    assert api._native_state(deletion.layer) == before and deletion.commits == []


def test_deletion_rechecks_target_after_real_history_initialization(deletion, monkeypatch):
    import fontlabapp.core.edit_guards as guards

    real_commit = next(
        value for obj, name, value in monkeypatch._setattr
        if obj is history and name == "commit"
    )
    events, states = [], []

    def initialize(value):
        events.append("layer init")
        deletion.shape.contours.reverse()
        states.append(api._native_state(deletion.layer))

    deletion.layer.checkInitHistoryState = initialize
    owner = deletion.layer.glyph
    owner.checkInitHistoryState = lambda value: events.append("glyph init")
    module = NS(flItems=lambda: NS(
        notifyChangesApplied=lambda *args: events.append("notify")
    ))
    monkeypatch.setattr(guards, "pending_updates", lambda module: ())
    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, native: None)
    monkeypatch.setattr(history, "commit", lambda *args, **kwargs: real_commit(
        *args, native=module, stamp=123, **kwargs
    ))
    with pytest.raises(history.PartialWriteError, match="stale"):
        run(deletion, deletion.plugin)
    assert events == ["layer init", "glyph init", "notify"]
    assert deletion.shape.contours == [deletion.large, deletion.contour]
    assert api._native_state(deletion.layer) == states[0]


def test_duplicate_contours_keep_positional_correspondence(glyph):
    old = glyph.contours[0]
    before = replace(glyph, contours=(old, replace(old)))
    edit = Move().compute(before, {})
    assert api._coordinates(before, edit) == edit.contours
    unchanged = LayerEdit(contours=tuple(replace(c) for c in before.contours))
    assert api._coordinates(before, unchanged) == before.contours


def test_compute_contour_identity_change_refused(native):
    plugin = Move()

    def compute(before, values):
        native.contour.id = 99
        return Move().compute(before, values)

    plugin.compute = compute
    with pytest.raises(ValueError, match="identities changed"):
        run(native, plugin)
    assert native.commits == []


def test_prepare_checks_snapshot_before_any_write(native):
    plan, facts = api.plan_filter(Move(), {}, native.selected, outlines, history)
    change = plan.work[0][2][0]
    plan.work[0][2][0] = replace(change, before=())
    with pytest.raises(ValueError, match="source coordinates"):
        writer.apply_work(plan.work, "Move", facts, api.LayerEditEditor(outlines))
    assert native.nodes[0].position.x() == 0 and native.commits == []


def test_real_history_retains_undo_recovery_after_native_failure(native, monkeypatch):
    import fontlabapp.core.edit_guards as guards

    # Keep the real commit function while replacing only the native boundary.
    real_commit = next(
        value
        for obj, name, value in monkeypatch._setattr
        if obj is history and name == "commit"
    )
    events = []
    native.layer.checkInitHistoryState = lambda value: events.append("layer init")
    owner = native.selected.occurrences[0].glyph
    owner.checkInitHistoryState = lambda value: events.append("glyph init")
    native.layer.update = lambda: False
    module = NS(
        flItems=lambda: NS(notifyChangesApplied=lambda *args: events.append("notify"))
    )
    monkeypatch.setattr(guards, "pending_updates", lambda module: ())
    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, native: None)
    monkeypatch.setattr(
        history,
        "commit",
        lambda *args, **kwargs: real_commit(*args, native=module, stamp=123, **kwargs),
    )
    with pytest.raises(history.PartialWriteError, match="use Edit > Undo"):
        run(native)
    assert events == ["layer init", "glyph init", "notify"]
    assert native.nodes[0].position.x() == 10
    assert owner.lastModified == 123


@pytest.mark.parametrize(
    "bundle,values,expected",
    [
        ("MoveOutlines", {"dx": 10, "dy": -5}, (40, 115)),
        ("RoundOutlineToGrid", {"grid": 50}, (50, 100)),
        ("ScaleOutlines", {"x_percent": 200, "y_percent": 50}, (60, 60)),
        ("SlantOutlines", {"angle": 45}, (150, 120)),
    ],
)
def test_reference_bundle_dispatch_preserves_non_outline_state(
    native, bundle, values, expected
):
    from pathlib import Path

    from fontlabapp.plugins import bundles

    root = Path(__file__).resolve().parents[3] / "fontlab-python-plugmix"
    plugin = bundles.load_bundle(
        root / "Extensions" / "filters" / (bundle + ".fontlabfilter")
    )()
    component = NS(isComponent=True, id=90, contours=())
    native.layer.shapes.append(component)
    native.layer.advanceWidth = 500
    native.layer.anchors = [NS(name="top", point=Point(50, 110))]
    original_nodes = tuple(native.nodes)
    flags = [n.nodeState for n in native.nodes]
    other = NS(shapes=[], name="Bold")
    owner = native.selected.occurrences[0].glyph
    owner.findLayer = lambda master: native.layer if master == "Regular" else other
    plan, result = api.apply_filter(
        plugin,
        values,
        selected=native.selected,
        outlines=outlines,
        writer=writer,
        history=history,
    )
    assert plan.work[0][1] is native.layer and result["layers"] == 1
    assert (
        native.nodes[1].position.x(),
        native.nodes[1].position.y(),
    ) == pytest.approx(expected)
    assert (
        tuple(native.nodes) == original_nodes
        and [n.nodeState for n in native.nodes] == flags
    )
    assert native.layer.shapes[1] is component and other.shapes == []
    assert native.layer.advanceWidth == 500
    assert native.layer.anchors[0].point.values == (50, 110)


def test_move_bundle_accepts_coordinate_collision_with_another_original(native):
    from pathlib import Path

    from fontlabapp.plugins import bundles

    root = Path(__file__).resolve().parents[3] / "fontlab-python-plugmix"
    plugin = bundles.load_bundle(
        root / "Extensions" / "filters" / "MoveOutlines.fontlabfilter"
    )()
    first = native.glyph.contours[0]
    second = [
        NativeNode(i + 10, replace(n, x=n.x + 10)) for i, n in enumerate(first.nodes)
    ]
    native.shape.contours.append(NS(id=22, nodes=lambda: second, closed=True))
    expected_first = tuple((n.position.x(), n.position.y()) for n in second)
    plan, result = api.apply_filter(
        plugin,
        {"dx": 10},
        selected=native.selected,
        outlines=outlines,
        writer=writer,
        history=history,
    )
    assert result["layers"] == 1 and len(plan.work) == 1
    assert (
        tuple((n.position.x(), n.position.y()) for n in native.nodes) == expected_first
    )
    assert tuple((n.position.x(), n.position.y()) for n in second) == tuple(
        (x + 10, y) for x, y in expected_first
    )


@pytest.mark.parametrize(
    "name",
    ["delete_small_paths", "move_outlines", "round_outline_to_grid", "scale_outlines", "slant_outlines"],
)
@pytest.mark.parametrize("auto_owner", [False, True])
def test_all_filters_preserve_automatic_layer_refusal_reason(
    native, monkeypatch, tmp_path, name, auto_owner
):
    from fontlabapp.plugins.registry import Registry

    facts = history.auto_facts(
        [("a", True, ())] if auto_owner else [("aacute", True, ("a",))]
    )
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts)
    plugin = Registry(tmp_path).available("filter")[name]()
    plan, result = run(native, plugin)
    reason = "has auto layers" if auto_owner else "base of auto aacute"
    assert plan.refused == ["a"] and result is None
    assert [(label, change.new) for label, change in plan.rows] == [
        ("a", f"skipped: {reason}")
    ]
    assert native.commits == [] and native.nodes[0].position.x() == 0


def selected(native, *layers):
    return LayerSelection(
        native.selected.context,
        tuple(
            LayerOccurrence(layer.glyph.package, layer.glyph, layer, 0, i)
            for i, layer in enumerate(layers)
        ),
    )


def extra_layer(native, name="Bold", *, other_glyph=False):
    layer = deepcopy(native.layer)
    layer.id, layer.name = 12, name
    owner = native.layer.glyph
    if other_glyph:
        owner = NS(
            id=5,
            name="b",
            isNull=False,
            package=owner.package,
            layers=[],
            findLayer=lambda master: native.layer,
        )
        owner.package.glyphs[owner.name] = owner
    layer.glyph = owner
    owner.layers.append(layer)
    nodes = [
        NativeNode(i, replace(n, x=n.x + 100))
        for i, n in enumerate(native.glyph.contours[0].nodes)
    ]
    layer.shapes[0].contours[0].nodes = lambda: nodes
    layer.shapes[0].removeContour = layer.shapes[0].contours.remove
    return layer


@pytest.mark.parametrize("repeat", [False, True])
def test_selected_layers_keep_explicit_handles_and_order(native, repeat):
    bold = extra_layer(native)
    layers = (bold, native.layer, bold) if repeat else (bold,)
    native.selected = selected(native, *layers)
    native.layer.glyph.findLayer = lambda name: pytest.fail("Must retain the selected layer handle")
    plan, result = run(native)
    expected = (bold, native.layer) if repeat else (bold,)
    assert [layer.id for _, layer, _ in plan.work] == [layer.id for layer in expected]
    assert all(work[1] is layer for work, layer in zip(plan.work, expected))
    assert result["layers"] == len(expected) and len(native.commits) == 1
    assert bold.shapes[0].contours[0].nodes()[0].position.x() == 110
    assert native.nodes[0].position.x() == (10 if repeat else 0)


def test_two_glyphs_keep_their_own_selected_layers(native):
    bold = extra_layer(native, other_glyph=True)
    native.selected = selected(native, bold, native.layer)
    plan, result = run(native)
    assert [(g.name, layer.id) for g, layer, _ in plan.work] == [("b", 12), ("a", 11)]
    assert result["layers"] == 2 and len(native.commits) == 1
    assert bold.shapes[0].contours[0].nodes()[0].position.x() == 110
    assert native.nodes[0].position.x() == 10


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "null",
        "invalid",
        "replaced",
        "foreign_layer",
        "foreign_package",
        "glyph_id",
        "layer_id",
        "glyph_name",
        "layer_name",
        "package_id",
        "context",
        "master",
        "removed_glyph",
        "replaced_glyph",
        "layer_owner_package",
        "missing_handle",
        "null_package",
        "null_glyph",
    ],
)
def test_selected_identity_refuses_before_any_compute_or_history(native, mutation):
    bold = extra_layer(native)
    native.selected = selected(native, native.layer, bold)
    owner, package = bold.glyph, bold.glyph.package
    if mutation == "missing_handle":
        object.__setattr__(native.selected.occurrences[1], "layer", None)
    elif mutation == "null_package":
        package.isNull = True
        package.findName = lambda name: pytest.fail("Null package must not receive lookup")
    elif mutation == "null_glyph":
        owner.isNull = True
    elif mutation == "missing":
        owner.layers.remove(bold)
    elif mutation == "replaced":
        owner.layers[-1] = NS(id=99, name="Bold")
    elif mutation == "foreign_layer":
        bold.glyph = NS(id=99, package=package)
    elif mutation == "foreign_package":
        owner.package = NS(id=99)
    elif mutation == "layer_owner_package":
        bold.glyph = NS(id=owner.id, package=NS(id=99))
    elif mutation == "null":
        bold.isNull = True
    elif mutation == "invalid":
        bold.isValid = False
    elif mutation == "glyph_id":
        owner.id = 99
    elif mutation == "layer_id":
        bold.id = 99
    elif mutation == "glyph_name":
        owner.name = "changed"
    elif mutation == "layer_name":
        bold.name = "changed"
    elif mutation == "package_id":
        package.id = 99
    elif mutation == "master":
        package.master = "Bold"
    elif mutation == "context":
        native.selected = replace(native.selected, context=(99, "Regular", "editor"))
    elif mutation == "removed_glyph":
        package.glyphs.clear()
    else:
        package.glyphs["a"] = NS(id=99, isNull=False)
    calls = []
    plugin = Move()
    plugin.compute = lambda *args: calls.append(args) or LayerEdit()
    with pytest.raises(ValueError, match="selected"):
        run(native, plugin)
    assert calls == [] and native.commits == []
    assert native.nodes[0].position.x() == 0


@pytest.mark.parametrize("unsafe", ["shared", "scaled", "rotated"])
def test_selected_unsafe_layer_keeps_safe_peer(native, unsafe):
    bold = extra_layer(native)
    native.selected = selected(native, bold, native.layer)
    if unsafe == "shared":
        bold.shapes[0].shapeData.referenceCount = 2
    else:
        setattr(
            bold.shapes[0].transform,
            "m12" if unsafe == "rotated" else "m11",
            lambda: 2,
        )
    plan, result = run(native)
    assert plan.refused == ["a"] and [layer.id for _, layer, _ in plan.work] == [11]
    assert result["layers"] == 1 and len(native.commits) == 1
    assert bold.shapes[0].contours[0].nodes()[0].position.x() == 100
    assert native.nodes[0].position.x() == 10


@pytest.mark.parametrize("transitive", [False, True])
def test_whole_glyph_auto_policy_precedes_selected_layer_compute(
    native, monkeypatch, transitive
):
    bold = extra_layer(native)
    bold.autoLayer = True
    records = [("a", False, ()), ("a", True, ())]
    if transitive:
        records = [
            ("a", False, ()),
            ("manual", False, ("a",)),
            ("auto", True, ("manual",)),
        ]
    monkeypatch.setattr(
        history, "scan_auto_facts", lambda package: history.auto_facts(records)
    )
    native.selected = selected(native, native.layer, bold)
    calls = []
    plugin = Move()
    plugin.compute = lambda *args: calls.append(args) or LayerEdit()
    plan, result = run(native, plugin)
    assert plan.refused == ["a"] and result is None
    assert len(plan.rows) == 1 and "skipped:" in plan.rows[0][1].new
    assert calls == [] and native.commits == []


def test_direct_selected_auto_layer_keeps_safe_manual_layer(native):
    bold = extra_layer(native)
    bold.autoLayer = True
    native.selected = selected(native, bold, native.layer)
    plan, result = run(native)
    assert plan.skipped == ["a/Bold"]
    assert [(label, row.new) for label, row in plan.rows][0] == (
        "a · Bold",
        "auto layer, skipped",
    )
    assert result["layers"] == 1 and len(native.commits) == 1
    assert bold.shapes[0].contours[0].nodes()[0].position.x() == 100


def test_duplicate_native_wrappers_edit_same_layer_once(native):
    from copy import copy

    duplicate = copy(native.layer)
    native.selected = selected(native, native.layer, duplicate)
    plan, result = run(native)
    assert len(plan.work) == 1 and plan.work[0][1] is native.layer
    assert result["layers"] == 1 and native.nodes[0].position.x() == 10
    assert len(native.commits) == 1


@pytest.mark.parametrize("empty", [False, True])
def test_exact_selected_noop_and_empty_selection_never_open_history(native, empty):
    bold = extra_layer(native)
    native.selected = selected(
        native, *((bold, native.layer, bold) if not empty else ())
    )
    calls = []
    plugin = Move()
    plugin.compute = lambda before, values: calls.append(before) or LayerEdit()
    plan, result = run(native, plugin)
    assert plan.work == [] and result is None and native.commits == []
    assert len(calls) == (0 if empty else 2)
    assert bold.shapes[0].contours[0].nodes()[0].position.x() == 100
    assert native.nodes[0].position.x() == 0


def translate(shape, dx, dy):
    shape.transform.dx = lambda: dx
    shape.transform.dy = lambda: dy
    shape.transform.map = lambda p: Point(
        p.x() + shape.transform.dx(), p.y() + shape.transform.dy()
    )


@pytest.mark.parametrize("bundle,values,expected", [
    ("MoveOutlines", {"dx": 10, "dy": -5}, (40, 115)),
    ("RoundOutlineToGrid", {"grid": 50}, (37, 107)),
    ("ScaleOutlines", {"x_percent": 200, "y_percent": 50}, (73, 63.5)),
    ("SlantOutlines", {"angle": 45}, (143, 120)),
])
def test_reference_filters_write_translated_shapes_in_local_coordinates(
    native, bundle, values, expected
):
    from pathlib import Path
    from fontlabapp.plugins import bundles

    root = Path(__file__).resolve().parents[3] / "fontlab-python-plugmix"
    plugin = bundles.load_bundle(
        root / "Extensions" / "filters" / (bundle + ".fontlabfilter")
    )()
    translate(native.shape, 13, -7)
    flags = tuple(n.nodeState for n in native.nodes)
    plan, result = api.apply_filter(
        plugin, values, selected=native.selected,
        outlines=outlines, writer=writer, history=history,
    )
    assert result["layers"] == 1 and plan.refused == []
    assert native.nodes[1].position.values == pytest.approx(expected)
    assert tuple(n.nodeState for n in native.nodes) == flags
    assert (native.shape.transform.dx(), native.shape.transform.dy()) == (13, -7)
    assert len(native.commits) == 1


def test_translated_elements_keep_their_distinct_offsets(native):
    translate(native.shape, 13, -7)
    second = [NativeNode(i + 10, n) for i, n in enumerate(native.glyph.contours[0].nodes)]
    shape = deepcopy(native.shape)
    shape.id = 30
    shape.contours = [NS(id=20, nodes=lambda: second, closed=True)]
    translate(shape, -20, 40)
    native.layer.shapes.append(shape)
    plan, result = run(native)
    assert result["layers"] == 1 and plan.refused == []
    assert native.nodes[0].position.values == (10, 0)
    assert second[0].position.values == (10, 0)
    assert len(native.commits) == 1


@pytest.mark.parametrize("compensate", [False, True])
def test_translation_drift_refused_even_with_compensated_node_positions(native, compensate):
    translate(native.shape, 13, -7)
    plan, facts = api.plan_filter(Move(), {}, native.selected, outlines, history)
    translate(native.shape, 14, -7)
    if compensate:
        for node in native.nodes:
            node.position = Point(node.position.x() - 1, node.position.y())
    before = tuple(n.position.values for n in native.nodes)
    with pytest.raises(ValueError, match="stale"):
        writer.apply_work(plan.work, "Move", facts, api.LayerEditEditor(outlines))
    assert tuple(n.position.values for n in native.nodes) == before
    assert native.commits == []


@pytest.mark.parametrize("offset", [float("nan"), float("inf")])
def test_nonfinite_translation_never_opens_history(native, offset):
    translate(native.shape, offset, 0)
    with pytest.raises(ValueError, match="finite"):
        run(native)
    assert native.commits == []


def test_unrepresentable_local_coordinate_never_opens_history(native):
    translate(native.shape, 1e308, 0)
    plugin = Move()
    plugin.compute = lambda before, values: LayerEdit(contours=tuple(
        replace(c, nodes=tuple(replace(n, x=-1e308) for n in c.nodes))
        for c in before.contours
    ))
    with pytest.raises(ValueError, match="represent"):
        run(native, plugin)
    assert native.commits == []


def test_component_base_moves_instead_of_refused(native):
    """A base used by 33 components (referenceCount 34) is moved, not refused."""
    package = native.layer.glyph.package
    for i in range(33):
        user_layer = NS(
            name="Regular",
            shapes=[
                NS(
                    isComponent=True,
                    shapeData=NS(
                        referenceCount=1, componentGlyph="a", componentLayer=""
                    ),
                )
            ],
        )
        package.glyphs[f"a{i}"] = NS(
            name=f"a{i}", findLayer=lambda name, x=user_layer: x
        )
    package.fgPackage = NS(glyphs=[NS(name=n) for n in package.glyphs])
    native.shape.shapeData.referenceCount = 34
    plan, _ = api.plan_filter(Move(), {"dx": 10}, native.selected, outlines, history)
    assert plan.refused == [] and len(plan.work) == 1
