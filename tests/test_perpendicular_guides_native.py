# this_file: tests/test_perpendicular_guides_native.py
"""Writer boundaries and meaningful partial failures on typed native-shaped owners."""

from time import monotonic
from types import SimpleNamespace as NS

import fontlabapp.guides.perpendicular.native as m
import pytest


@pytest.fixture
def host(monkeypatch):
    calls = []

    class Layer:
        autoLayer = False

        def __init__(self):
            self.guidelines = [NS(id=90)]

        def checkInitHistoryState(self, n):
            calls.append(("history-layer", n))

        def appendGuidelines(self, rows):
            calls.append(("append", len(rows)))
            self.guidelines = [*self.guidelines, *rows]

    layer = Layer()
    glyph = NS(
        name="A", checkInitHistoryState=lambda n: calls.append(("history-glyph", n))
    )
    occurrence = NS(layer=layer, glyph=glyph, package=NS())
    source = m.Snapshot(
        ("context", (), False, (), (90,)), ((1, 0, 0), (2, 20, 0)), (), (), occurrence
    )
    native = NS(
        flGlyph=NS(updatedFgGlyphs=lambda: ()),
        flItems=lambda: NS(
            notifyChangesApplied=lambda title, objects: calls.append(
                ("notify", title, objects)
            )
        ),
    )
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "stamp")))
    monkeypatch.setattr(m, "_native", lambda name: native if name == "fontlab" else qt)
    monkeypatch.setattr(m, "capture", lambda deadline: source)
    monkeypatch.setattr(m, "require_main_thread", lambda: None)
    monkeypatch.setattr(m, "new_guide", lambda values: NS(id=100 + len(calls)))
    return NS(calls=calls, layer=layer, glyph=glyph, source=source, native=native)


def test_append_preserves_original_ids_one_notification_no_refresh(host):
    result = m.execute()
    assert result == {"guides": 1, "layers": 1, "messages": (), "pending_updates": (), "pending_note": ""}
    assert host.layer.guidelines[0].id == 90
    assert [row[0] for row in host.calls] == [
        "history-layer",
        "history-glyph",
        "append",
        "notify",
    ]
    assert host.calls[-1][-1] == [host.layer, host.glyph]
    assert host.glyph.lastModified == "stamp"


@pytest.mark.parametrize(
    "auto,deps", [(True, ()), (False, (("A", False, ()), ("B", True, ("A",))))]
)
def test_unsafe_automatic_refused_before_history(host, auto, deps):
    host.layer.autoLayer = auto
    from dataclasses import replace

    with pytest.raises(ValueError):
        m.write(replace(host.source, dependencies=deps), ((1, 2, 0),), monotonic() + 2)
    assert not host.calls


def test_no_selection_diagnosis_has_no_history(host, monkeypatch, capsys):
    from dataclasses import replace

    monkeypatch.setattr(m, "capture", lambda deadline: replace(host.source, nodes=()))
    assert m.execute()["guides"] == 0
    assert "Please select path nodes or components." in capsys.readouterr().out
    assert not host.calls


def test_stale_capture_before_history(host, monkeypatch):
    monkeypatch.setattr(m, "capture", lambda deadline: None)
    with pytest.raises(ValueError):
        m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    assert not host.calls


def test_changed_during_first_double_capture(host, monkeypatch):
    values = iter((host.source, None))
    monkeypatch.setattr(m, "capture", lambda deadline: next(values))
    with pytest.raises(ValueError):
        m.execute()
    assert not host.calls


@pytest.mark.parametrize("partial", [False, True])
def test_failed_append_finalizes_once_and_reports_uncertainty(host, partial):
    def fail(rows):
        host.calls.append(("attempt",))
        if partial:
            host.layer.guidelines = [*host.layer.guidelines, rows[0]]
        raise RuntimeError("injected")

    host.layer.appendGuidelines = fail
    with pytest.raises(RuntimeError, match="Edit > Undo"):
        m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    assert sum(r[0] == "notify" for r in host.calls) == 1


def test_wrong_native_append_order_not_success(host):
    host.layer.appendGuidelines = lambda rows: None
    with pytest.raises(RuntimeError):
        m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    assert host.calls[-1][0] == "notify"


def test_pending_global_updates_are_disclosed_without_refusal(host):
    host.native.flGlyph.updatedFgGlyphs = lambda: (777,)
    result = m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    assert result["pending_updates"] == (777,) and "8537" in result["pending_note"]
    assert host.calls[-1][0] == "notify"


def test_notification_failure_retains_stamp(host):
    def fail(*args):
        raise RuntimeError("notification")

    host.native.flItems = lambda: NS(notifyChangesApplied=fail)
    with pytest.raises(RuntimeError, match="notification"):
        m.execute()
    assert host.glyph.lastModified == "stamp"


def test_capture_uses_true_bounds_and_mapped_own_selected_nodes(monkeypatch):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QTransform

    transform = QTransform()
    transform.translate(7, 9)
    transform.rotate(90)
    nodes = [
        NS(id=1, position=QPointF(10, 0), nodeState=32, selected=True),
        NS(id=2, position=QPointF(20, 0), nodeState=0, selected=False),
    ]
    own = NS(
        id=5,
        transform=transform,
        isComponent=False,
        selected=False,
        contours=[NS(id=44, transform=QTransform(), nodes=lambda: nodes)],
    )
    component = NS(
        id=6,
        transform=QTransform(),
        isComponent=True,
        selected=True,
        getCompositesBounding=lambda: QRectF(-30, -40, 20, 10),
    )
    layer = NS(shapes=[own, component], autoLayer=False, guidelines=[NS(id=50)])
    occurrence = NS(
        layer=layer,
        package=NS(),
        package_id=1,
        glyph_id=2,
        layer_id=3,
        block_id=0,
        index=0,
    )
    monkeypatch.setattr(
        m.layer_selection,
        "capture",
        lambda d: NS(occurrences=[occurrence], context=(1, 2), carriers=()),
    )
    monkeypatch.setattr(m, "dependency_values", lambda p: ())
    def forbidden_queue():
        raise AssertionError("Capture must not read or refuse the native update queue")
    monkeypatch.setattr(
        m, "_native", lambda n: NS(flGlyph=NS(updatedFgGlyphs=forbidden_queue))
    )
    source = m.capture(monotonic() + 2)
    assert source.nodes == ((1, 7, 19),)
    assert source.components == ((6, -30, -40, 20, 10),)
    assert source.facts[-1] == (50,)
    assert source.facts[-2][0][-1][-1][-1] is False
    component.selected = False
    assert not m.capture(monotonic() + 2).components
    monkeypatch.setattr(m.layer_selection, "capture", lambda d: NS(occurrences=[]))
    with pytest.raises(ValueError):
        m.capture(monotonic() + 2)
    monkeypatch.setattr(
        m.layer_selection,
        "capture",
        lambda d: NS(occurrences=[occurrence], context=(1, 2), carriers=()),
    )
    own.transform = NS(isAffine=lambda: False)
    with pytest.raises(ValueError):
        m.capture(monotonic() + 2)


def test_component_success_diagnostics_and_single_node_warning_both_survive(
    host, monkeypatch, capsys
):
    from dataclasses import replace

    source = replace(host.source, nodes=((1, 0, 0),), components=((9, 10, 20, 4, 6),))
    monkeypatch.setattr(m, "capture", lambda deadline: source)
    assert m.execute()["guides"] == 2
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "Please select at least two points.",
        "Added horizontal and vertical guides at center (12.0, 23.0) for component.",
    ]


def test_contour_transform_precedes_shape_in_selected_node_geometry(monkeypatch):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QTransform

    shape_transform = QTransform()
    shape_transform.translate(100, 200)
    contour_transform = QTransform()
    contour_transform.translate(20, 30)
    contour_transform.rotate(90)
    contour = NS(
        id=44,
        transform=contour_transform,
        nodes=lambda: [
            NS(id=1, position=QPointF(0, 0), nodeState=32, selected=True),
            NS(id=2, position=QPointF(10, 0), nodeState=32, selected=True),
        ],
    )
    shape = NS(
        id=5,
        transform=shape_transform,
        isComponent=False,
        selected=False,
        contours=[contour],
    )
    occurrence = NS(
        layer=NS(shapes=[shape], autoLayer=False, guidelines=[]),
        package=NS(),
        package_id=1,
        glyph_id=2,
        layer_id=3,
        block_id=7,
        index=0,
    )
    monkeypatch.setattr(
        m.layer_selection,
        "capture",
        lambda d: NS(occurrences=[occurrence], context=(1, 2), carriers=()),
    )
    monkeypatch.setattr(m, "dependency_values", lambda p: ())
    monkeypatch.setattr(
        m, "_native", lambda n: NS(flGlyph=NS(updatedFgGlyphs=lambda: ()))
    )
    before = m.capture(monotonic() + 2)
    assert before.nodes == ((1, 120, 230), (2, 120, 240))
    import math

    from fontlabapp.guides.perpendicular.model import plan

    assert plan(before.nodes, ())[0] == ((120, 235, math.pi),)


def test_contour_only_transform_change_is_stale_even_when_nodes_coincide(monkeypatch):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QTransform

    contour = NS(
        id=44,
        transform=QTransform(),
        nodes=lambda: [
            NS(id=1, position=QPointF(0, 0), nodeState=32, selected=True),
            NS(id=2, position=QPointF(0, 0), nodeState=32, selected=True),
        ],
    )
    shape = NS(
        id=5,
        transform=QTransform(),
        isComponent=False,
        selected=False,
        contours=[contour],
    )
    occurrence = NS(
        layer=NS(shapes=[shape], autoLayer=False, guidelines=[]),
        package=NS(),
        package_id=1,
        glyph_id=2,
        layer_id=3,
        block_id=7,
        index=0,
    )
    monkeypatch.setattr(
        m.layer_selection,
        "capture",
        lambda d: NS(occurrences=[occurrence], context=(1, 2), carriers=()),
    )
    monkeypatch.setattr(m, "dependency_values", lambda p: ())
    monkeypatch.setattr(
        m, "_native", lambda n: NS(flGlyph=NS(updatedFgGlyphs=lambda: ()))
    )
    before = m.capture(monotonic() + 2)
    contour.transform.rotate(90)
    after = m.capture(monotonic() + 2)
    assert before.nodes == after.nodes
    assert before != after
    before.occurrence.glyph = NS(name="A")
    monkeypatch.setattr(m, "new_guide", lambda values: NS(id=900))
    with pytest.raises(ValueError, match="Source changed before guide history"):
        m.write(before, ((0, 0, 0),), monotonic() + 2)
    contour.transform = NS(isAffine=lambda: False)
    with pytest.raises(ValueError, match="affine contours"):
        m.capture(monotonic() + 2)


def test_snapshot_retains_native_carrier_until_snapshot_release(monkeypatch):
    import gc
    import weakref

    class Carrier:
        pass

    references = []
    occurrence = NS(
        layer=NS(shapes=[], autoLayer=False, guidelines=[]),
        package=NS(),
        package_id=1,
        glyph_id=2,
        layer_id=3,
        block_id=7,
        index=0,
    )

    def selected(deadline):
        carrier = Carrier()
        references.append(weakref.ref(carrier))
        return NS(context=(1, 2), occurrences=[occurrence], carriers=(carrier,))

    monkeypatch.setattr(m.layer_selection, "capture", selected)
    monkeypatch.setattr(m, "dependency_values", lambda p: ())
    monkeypatch.setattr(
        m, "_native", lambda name: NS(flGlyph=NS(updatedFgGlyphs=lambda: ()))
    )
    snapshot = m.capture(monotonic() + 2)
    gc.collect()
    assert references[-1]() is not None
    del snapshot
    gc.collect()
    assert references[-1]() is None


@pytest.mark.parametrize("fail", [False, True])
def test_queue_is_read_once_disclosed_before_append_and_never_cleared(host, capsys, fail):
    reads = []
    def queue():
        reads.append(True)
        assert len(reads) == 1, "Read the queue once, never clear or recheck it"
        return (777, 888)
    host.native.flGlyph.updatedFgGlyphs = queue
    append = host.layer.appendGuidelines
    def append_checked(rows):
        assert capsys.readouterr().out.count("8537") == 1, "Disclose before a possible partial write"
        append(rows)
        if fail:
            raise RuntimeError("partial append")
    host.layer.appendGuidelines = append_checked
    if fail:
        with pytest.raises(RuntimeError, match="Edit > Undo"):
            m.execute()
    else:
        result = m.execute()
        assert result["pending_updates"] == (777, 888)
        assert "8537" in result["pending_note"]
    assert len(reads) == 1 and sum(c[0] == "notify" for c in host.calls) == 1


def test_noop_never_reads_pending_queue_or_warns(host, monkeypatch, capsys):
    from dataclasses import replace
    def forbidden():
        raise AssertionError("No-op does not reach the native queue")
    host.native.flGlyph.updatedFgGlyphs = forbidden
    monkeypatch.setattr(m, "capture", lambda deadline: replace(host.source, nodes=()))
    result = m.execute()
    assert result["pending_updates"] == () and result["pending_note"] == ""
    assert "8537" not in capsys.readouterr().out and not host.calls


@pytest.mark.parametrize("failures", range(1, 16))
def test_all_finalization_errors_are_retained_without_skipping_notification(host, failures):
    from fontlabapp.core.history.glyphs import PartialWriteError
    errors = [RuntimeError(name) for name in ("append", "stamp-before", "notify", "stamp-after")]
    stages = []
    class Glyph(NS):
        def __setattr__(self, name, value):
            if name == "lastModified":
                index = 1 if "stamp-before" not in stages else 3
                stages.append(str(errors[index]))
                if failures & (1 << index):
                    raise errors[index]
            super().__setattr__(name, value)
    glyph = Glyph(name="A", checkInitHistoryState=host.glyph.checkInitHistoryState)
    host.source.occurrence.glyph = glyph
    append = host.layer.appendGuidelines
    def attempt(rows):
        stages.append("append")
        append(rows)
        if failures & 1:
            raise errors[0]
    def notify(*args):
        stages.append("notify")
        if failures & 4:
            raise errors[2]
    host.layer.appendGuidelines = attempt
    host.native.flItems = lambda: NS(notifyChangesApplied=notify)
    with pytest.raises(PartialWriteError) as caught:
        m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    expected = tuple(error for index, error in enumerate(errors) if failures & (1 << index))
    assert caught.value.errors == expected, "Keep every original exception in occurrence order"
    assert caught.value.__cause__ is expected[0]
    assert "Edit > Undo" in str(caught.value)
    assert stages == ["append", "stamp-before", "notify", "stamp-after"], "Final notification must still be attempted once"


def test_deadline_before_append_does_not_stamp_or_notify(host, monkeypatch):
    checks = []
    def expire(deadline):
        checks.append(True)
        if len(checks) == 3:
            raise TimeoutError("before append")
    monkeypatch.setattr(m, "check", expire)
    with pytest.raises(TimeoutError, match="before append"):
        m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    assert [c[0] for c in host.calls] == ["history-layer", "history-glyph"]
    assert not hasattr(host.glyph, "lastModified")
    assert [g.id for g in host.layer.guidelines] == [90]


def test_interruption_after_append_still_finalizes_and_propagates(host):
    interruption = KeyboardInterrupt("cancelled")
    def append(rows):
        host.layer.guidelines.extend(rows)
        raise interruption
    host.layer.appendGuidelines = append
    with pytest.raises(KeyboardInterrupt) as caught:
        m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    assert caught.value is interruption
    assert sum(row[0] == "notify" for row in host.calls) == 1
    assert host.glyph.lastModified == "stamp"


@pytest.mark.parametrize("interrupt_stage", range(4))
def test_interrupt_at_each_stage_retains_cleanup_diagnostics(host, interrupt_stage):
    errors = [RuntimeError(name) for name in ("append", "stamp-before", "notify", "stamp-after")]
    interruption = KeyboardInterrupt("cancelled")
    errors[interrupt_stage] = interruption
    stages = []
    class Glyph(NS):
        def __setattr__(self, name, value):
            if name == "lastModified":
                index = 1 if 1 not in stages else 3
                stages.append(index)
                raise errors[index]
            super().__setattr__(name, value)
    host.source.occurrence.glyph = Glyph(name="A", checkInitHistoryState=host.glyph.checkInitHistoryState)
    def append(rows):
        stages.append(0)
        host.layer.guidelines.extend(rows)
        raise errors[0]
    def notify(*args):
        stages.append(2)
        raise errors[2]
    host.layer.appendGuidelines = append
    host.native.flItems = lambda: NS(notifyChangesApplied=notify)
    with pytest.raises(KeyboardInterrupt) as caught:
        m.write(host.source, ((1, 2, 0),), monotonic() + 2)
    assert caught.value is interruption
    assert stages == [0, 1, 2, 3], "Interruption must not skip remaining cleanup attempts"
    notes = "\n".join(caught.value.__notes__)
    for error in errors:
        if error is not interruption:
            assert str(error) in notes, "Keep diagnostics from each other failed phase"
    assert "Edit > Undo" in notes
