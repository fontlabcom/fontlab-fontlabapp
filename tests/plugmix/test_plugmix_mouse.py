# this_file: tests/plugmix/test_plugmix_mouse.py
"""G003 Task 4: mouse position for ``needs_mouse`` reporters, with fakes.

The native backend watches the active canvas viewport with one event filter
while an enabled reporter asks for the mouse. Moves start one single-shot
repaint timer; the timer fires one ``updateScreenRect``. Paints map
``canvas.mousePosition()`` into glyph units per occurrence.
"""

import math
from types import SimpleNamespace as NS

import pytest

from fontlabapp.plugins import backend as backend_module
from fontlabapp.plugins.backend import NativeCanvasBackend
from fontlabapp.plugins.reporter import Reporter

MOVE, HOVER, PAINT = 5, 129, 12


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Affine:
    """A QTransform-like fake: scale, then translate."""

    def __init__(self, scale=1.0, dx=0.0, dy=0.0):
        self.s, self._dx, self._dy = scale, dx, dy

    def map(self, point):
        return Point(point.x() * self.s + self._dx, point.y() * self.s + self._dy)

    def m11(self):
        return self.s

    def m12(self):
        return 0.0

    def m21(self):
        return 0.0

    def m22(self):
        return self.s

    def dx(self):
        return self._dx

    def dy(self):
        return self._dy


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)


class Timer:
    made = []

    def __init__(self):
        self.timeout = Signal()
        self.running = self.single = self.deleted = False
        self.interval = None
        self.starts = 0
        Timer.made.append(self)

    def setInterval(self, value):
        self.interval = value

    def setSingleShot(self, value):
        self.single = value

    def isActive(self):
        return self.running

    def start(self):
        self.running = True
        self.starts += 1

    def stop(self):
        self.running = False

    def deleteLater(self):
        self.deleted = True

    def fire(self):
        if self.single:
            self.running = False
        for slot in list(self.timeout.slots):
            slot()


class Widget:
    """Stands in for ``QtGui.QWidget``; counts instances."""

    count = 0

    def __init__(self):
        Widget.count += 1
        self.deleted = False

    def deleteLater(self):
        self.deleted = True


class Viewport:
    def __init__(self):
        self.filters, self.removed = [], []
        self.rect = "viewport-rect"

    def installEventFilter(self, item):
        self.filters.append(item)

    def removeEventFilter(self, item):
        self.removed.append(item)
        self.filters.remove(item)


class Event:
    def __init__(self, kind):
        self.kind = kind

    def type(self):
        return self.kind


class Canvas:
    UnderOwner, OverOwner = 0, 1

    def __init__(self, identifier, mouse=(30.0, 8.0)):
        self.id = identifier
        self.isNull = False
        self.viewPort = Viewport()
        self.appended, self.updates, self.blocks = [], [], []
        self.calls = []
        self.mouse = mouse
        self.mouse_reads = 0

    def appendPythonPainter(self, callback, order):
        self.appended.append((100 + len(self.appended), callback, order))
        return self.appended[-1][0]

    def removePythonPainter(self, token):
        return True

    def mapToViewportF(self, point):
        return Point(point.x(), point.y())

    def textBlocks(self):
        return self.blocks

    def mousePosition(self):
        self.mouse_reads += 1
        return Point(*self.mouse)

    def updateScreenRect(self, rect):
        self.updates.append(rect)
        self.calls.append("updateScreenRect")

    def updateViewport(self):
        self.calls.append("updateViewport")


class Example(Reporter):
    name, title = "example", "Example"

    def __init__(self):
        self.views = []

    def compute(self, snapshot):
        self.views.append(snapshot.view)
        return []


class Mouse(Example):
    name, title = "mouse", "Mouse"
    needs_mouse = True


def world(active):
    """A backend whose active canvas is ``active[0]``; errors are collected."""
    Timer.made.clear()
    Widget.count = 0
    workspace = NS(getActiveCanvas=lambda: active[0])
    fontlab = NS(flWorkspace=NS(instance=lambda: workspace))
    qt = NS(
        QtCore=NS(
            QTimer=Timer,
            QPointF=Point,
            QRectF=lambda rect: ("QRectF", rect),
            QEvent=NS(MouseMove=MOVE, HoverMove=HOVER),
        ),
        QtGui=NS(QWidget=Widget),
    )
    errors = []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    return backend, qt, errors


def watched(canvas):
    return list(canvas.viewPort.filters)


def repaint_timers():
    return [t for t in Timer.made if t.single]


def test_filter_installed_only_while_a_needs_mouse_reporter_is_enabled():
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    plain = backend.register(Example(), qt, None)
    assert watched(canvas) == [] and Widget.count == 0, "no mouse reporter, no filter"
    first = backend.register(Mouse(), qt, None)
    second = backend.register(Mouse(), qt, None)
    assert len(watched(canvas)) == 1, "one filter however many reporters ask"
    backend.remove(first)
    assert len(watched(canvas)) == 1, "another needs_mouse reporter remains"
    (item,) = watched(canvas)
    backend.remove(second)
    assert watched(canvas) == [] and canvas.viewPort.removed == [item]
    assert item.deleted and item._owner is None
    backend._poll()
    assert watched(canvas) == [], "the plain reporter keeps polling, unwatched"
    backend.remove(plain)
    assert errors == []


def test_close_removes_filter_and_repaint_timer_like_uninstall():
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)
    item.eventFilter(canvas.viewPort, Event(MOVE))
    (timer,) = repaint_timers()
    backend.close()
    assert watched(canvas) == [] and item.deleted
    assert timer.deleted and timer.timeout.slots == [] and not timer.running
    backend.close()
    assert errors == []


def test_moves_are_throttled_to_one_trailing_update_per_timer_window():
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)
    for kind in (MOVE, HOVER, MOVE, MOVE):
        assert item.eventFilter(canvas.viewPort, Event(kind)) is False
    (timer,) = repaint_timers()
    assert timer.interval == backend_module.REPAINT_MS <= 16
    assert timer.starts == 1 and canvas.updates == [], "no update before the fire"
    timer.fire()
    assert canvas.updates == [("QRectF", "viewport-rect")], "one trailing update"
    assert canvas.calls == ["updateScreenRect", "updateViewport"], "rect, then repaint"
    item.eventFilter(canvas.viewPort, Event(PAINT))
    assert timer.starts == 1, "only moves schedule a repaint"
    item.eventFilter(canvas.viewPort, Event(MOVE))
    assert timer.starts == 2, "a move after the fire restarts the window"
    timer.fire()
    assert len(canvas.updates) == 2 and errors == []


def test_canvas_swap_moves_the_filter_and_close_of_canvas_drops_it():
    one, two = Canvas(1), Canvas(2)
    active = [one]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    (first,) = watched(one)
    backend._poll()
    assert watched(one) == [first], "same canvas: nothing reinstalled"
    active[0] = two
    backend._poll()
    assert watched(one) == [] and first.deleted
    assert len(watched(two)) == 1
    (second,) = watched(two)
    two.isNull = True
    active[0] = None
    backend._poll()
    assert two.viewPort.removed == [], "a destroyed viewport is not touched"
    assert second.deleted and second._owner is None
    first.eventFilter(one.viewPort, Event(MOVE))
    assert repaint_timers() == [], "an old filter is inert"
    assert errors == []


def test_pending_repaint_after_unwatch_does_nothing():
    canvas = Canvas(1)
    active = [canvas]
    backend, qt, errors = world(active)
    token = backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)
    item.eventFilter(canvas.viewPort, Event(MOVE))
    (timer,) = repaint_timers()
    backend.remove(token)
    assert timer.deleted and not timer.running
    timer.fire()  # a late native fire after teardown
    assert canvas.updates == [] and errors == []


def test_pending_repaint_when_canvas_closed_before_poll_then_no_native_call():
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)
    item.eventFilter(canvas.viewPort, Event(MOVE))
    canvas.isNull = True  # closed within the 16 ms window
    canvas.updateScreenRect = lambda rect: pytest.fail("called on a null canvas")
    repaint_timers()[0].fire()
    assert errors == []


def test_filter_exceptions_never_escape_and_are_reported_once():
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)

    class Broken:
        def type(self):
            raise RuntimeError("stale event")

    for _ in range(3):
        assert item.eventFilter(canvas.viewPort, Broken()) is False
    assert [str(e) for e in errors] == ["stale event"]
    canvas.updateScreenRect = lambda rect: (_ for _ in ()).throw(OSError("gone"))
    for _ in range(2):
        item.eventFilter(canvas.viewPort, Event(MOVE))
        repaint_timers()[0].fire()
    assert [str(e) for e in errors] == ["stale event", "gone"], "once per kind"
    backend.close()
    errors.clear()
    backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)
    qt.QtCore.QTimer = lambda: (_ for _ in ()).throw(TypeError("no timer"))
    assert item.eventFilter(canvas.viewPort, Event(MOVE)) is False
    assert [str(e) for e in errors] == ["no timer"]


def test_filter_survives_failing_sink():
    canvas = Canvas(1)
    backend, qt, _ = world([canvas])

    def sink(error, source):
        raise RuntimeError("sink")

    backend.sink = sink
    backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)
    assert item.eventFilter(canvas.viewPort, NS(type=None)) is False


def test_install_failure_is_reported_once_and_not_retried_each_poll():
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])

    def refuse(item):
        raise RuntimeError("no filter")

    canvas.viewPort.installEventFilter = refuse
    backend.register(Mouse(), qt, None)
    made = Widget.count
    for _ in range(3):
        backend._poll()
    assert [str(e) for e in errors] == ["no filter"]
    assert Widget.count == made, "a refused canvas is not retried every poll"


def test_teardown_failure_keeps_filter_alive_and_is_reported():
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    token = backend.register(Mouse(), qt, None)
    (item,) = watched(canvas)

    def refuse(other):
        raise RuntimeError("busy")

    canvas.viewPort.removeEventFilter = refuse
    backend.remove(token)
    assert item._owner is None and item in backend._kept_filters
    assert [str(e) for e in errors] == ["busy"]


def paint(canvas, reporter, info_transform, block_transform=None, paints=1):
    """Run native paints for one active slot; return the backend errors."""
    glyph = NS(
        isNull=False,
        id=8,
        name="o",
        package=NS(master="M"),
        findLayer=lambda name: NS(isNull=False),
    )
    info = NS(
        isActive=True, glyph=glyph, symbol=NS(layerName=""), transform=info_transform
    )
    canvas.blocks = [
        NS(transform=block_transform or Affine(), getAllGlyphs=lambda: [info])
    ]
    backend, qt, errors = world([canvas])
    seen = []
    reporter.paint = lambda context, q, sink: seen.append(context)
    backend.register(reporter, qt, None)
    for _ in range(paints):
        canvas.appended[0][1](object(), canvas)
    backend.close()
    return seen, errors


def test_paint_maps_mouse_through_inverted_glyph_and_block_transforms():
    canvas = Canvas(1, mouse=(31.0, 10.0))
    seen, errors = paint(canvas, Mouse(), Affine(2, 10, 0), Affine(1, 1, 2), paints=2)
    assert [c.mouse for c in seen] == [(10.0, 4.0)] * 2
    assert canvas.mouse_reads == 2, "one mousePosition read per paint callback"
    assert canvas.updates == [], "paint never schedules or forces a repaint"
    assert canvas.calls == [], "paint never calls updateViewport either"
    assert errors == []


def test_paint_when_transform_not_invertible_then_mouse_none_reported_once():
    canvas = Canvas(1)
    seen, errors = paint(canvas, Mouse(), Affine(0, 10, 0), paints=3)
    assert [c.mouse for c in seen] == [None] * 3
    assert len(errors) == 1 and "not invertible" in str(errors[0])


def test_paint_when_mouse_position_fails_then_none_and_reported_once():
    canvas = Canvas(1)
    canvas.mousePosition = lambda: (_ for _ in ()).throw(RuntimeError("no mouse"))
    seen, errors = paint(canvas, Mouse(), Affine(1), paints=2)
    assert [c.mouse for c in seen] == [None, None]
    assert [str(e) for e in errors] == ["no mouse"]


def test_paint_when_no_reporter_asks_then_mouse_is_never_read():
    canvas = Canvas(1)
    seen, errors = paint(canvas, Example(), Affine(1), paints=2)
    assert [c.mouse for c in seen] == [None, None]
    assert canvas.mouse_reads == 0 and Widget.count == 0 and errors == []


def test_paint_on_an_unwatched_canvas_gives_no_mouse():
    one, two = Canvas(1), Canvas(2)
    paint(one, Mouse(), Affine(1))  # gives ``one`` its blocks
    two.blocks = one.blocks
    active = [one]
    backend, qt, errors = world(active)
    found = []
    reporter = Mouse()
    reporter.paint = lambda context, q, sink: found.append((context.mouse))
    backend.register(reporter, qt, None)
    active[0] = two
    backend._poll()
    one.mouse_reads = 0
    one.appended[-1][1](object(), one)
    two.appended[0][1](object(), two)
    assert found == [None, (30.0, 8.0)], "only the watched canvas has a live cursor"
    assert one.mouse_reads == 0 and errors == []


def test_paint_when_scale_unusable_then_no_mouse():
    canvas = Canvas(1)
    canvas.mapToViewportF = lambda point: Point(math.nan, 0)
    seen, errors = paint(canvas, Mouse(), Affine(1), paints=1)
    assert seen[0].mouse is None and seen[0].scale is None


@pytest.mark.parametrize("timer_fault", ["stop", "disconnect", "deleteLater"])
@pytest.mark.parametrize("sink_fails", [False, True])
def test_close_when_timer_and_filter_teardown_fail_then_late_callbacks_are_inert(
    monkeypatch, timer_fault, sink_fails
):
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    backend.register(Mouse(), qt, None)
    painter = canvas.appended[0][1]
    item = watched(canvas)[0]
    item.eventFilter(canvas.viewPort, Event(MOVE))
    poll_timer = next(t for t in Timer.made if not t.single)
    repaint = repaint_timers()[0]
    poll, flush = poll_timer.timeout.slots[0], repaint.timeout.slots[0]
    failure = RuntimeError("teardown")

    def refuse(*args):
        raise failure

    for timer in (poll_timer, repaint):
        target = timer.timeout if timer_fault == "disconnect" else timer
        monkeypatch.setattr(target, timer_fault, refuse)
    monkeypatch.setattr(canvas.viewPort, "removeEventFilter", refuse)
    if sink_fails:
        backend.sink = refuse
    backend.close()
    assert watched(canvas) == [item] and not item.deleted
    assert item._owner is None and item in backend._kept_filters
    assert backend._kept_timers == [repaint, poll_timer]
    assert all(not t.deleted for t in (poll_timer, repaint))
    assert [t.running for t in (poll_timer, repaint)] == [timer_fault == "stop"] * 2
    assert errors == ([] if sink_fails else [failure] * 3)
    before = len(errors)
    made = len(Timer.made)
    starts = [t.starts for t in Timer.made]
    monkeypatch.setattr(canvas, "textBlocks", lambda: pytest.fail("late glyph read"))
    workspace = backend.fl.flWorkspace.instance()
    monkeypatch.setattr(workspace, "getActiveCanvas", lambda: pytest.fail("late poll"))
    monkeypatch.setattr(canvas, "updateViewport", lambda: pytest.fail("late repaint"))
    for _ in range(2):
        painter(object(), canvas)
        poll()
        flush()
        assert item.eventFilter(canvas.viewPort, Event(MOVE)) is False
        backend.close()
    assert canvas.updates == [] and canvas.mouse_reads == 0
    assert len(Timer.made) == made and [t.starts for t in Timer.made] == starts
    assert len(errors) == before, "retained wrappers remain inert after double close"


@pytest.mark.parametrize("teardown", ["close", "remove"])
@pytest.mark.parametrize("timer_fault", [None, "stop", "disconnect", "deleteLater"])
@pytest.mark.parametrize("sink_fails", [False, True])
def test_poll_when_backend_reused_then_old_registered_slot_cannot_read_new_epoch(
    monkeypatch, teardown, timer_fault, sink_fails
):
    active = [Canvas(1)]
    backend, qt, errors = world(active)
    reads, stale = [], []
    workspace = backend.fl.flWorkspace.instance()
    monkeypatch.setattr(
        workspace, "getActiveCanvas", lambda: reads.append(active[0]) or active[0]
    )
    failure = RuntimeError("poll teardown")

    def refuse(*args):
        raise failure

    if sink_fails:
        backend.sink = refuse
    for epoch in range(2):
        token = backend.register(Example(), qt, None)
        timer = backend._timer
        slot = timer.timeout.slots[0]
        stale.append(slot)
        disconnect = timer.timeout.disconnect
        disconnected = []

        def disconnect_exact(callback):
            disconnected.append(callback)
            if timer_fault == "disconnect":
                raise failure
            disconnect(callback)

        monkeypatch.setattr(timer.timeout, "disconnect", disconnect_exact)
        if timer_fault in ("stop", "deleteLater"):
            monkeypatch.setattr(timer, timer_fault, refuse)
        backend.close() if teardown == "close" else backend.remove(token)
        assert timer.deleted is (timer_fault is None)
        assert (timer in backend._kept_timers) is (timer_fault is not None)
        assert errors == ([] if sink_fails else [failure] * (epoch + 1) * bool(timer_fault))
        active[0] = Canvas(10 + epoch)
        current = backend.register(Example(), qt, None)
        current_slot = backend._timer.timeout.slots[0]
        next_canvas = Canvas(20 + epoch)
        active[0] = next_canvas
        before = len(reads), len(errors), len(Timer.made), [t.starts for t in Timer.made]
        for old in stale:
            old()
        assert (len(reads), len(errors), len(Timer.made), [t.starts for t in Timer.made]) == before
        assert next_canvas.appended == [], "stale polling cannot attach current reporters"
        current_slot()
        assert reads[-1] is next_canvas and len(next_canvas.appended) == 1
        assert disconnected == [] if timer_fault == "stop" else (
            len(disconnected) == 1 and disconnected[0] is slot
        ), "disconnect must receive the exact connected callable"
        backend.remove(current)
    backend.close()


@pytest.mark.parametrize("teardown", ["close", "remove", "watch"])
@pytest.mark.parametrize("timer_fault", [None, "stop", "disconnect", "deleteLater"])
@pytest.mark.parametrize("sink_fails", [False, True])
def test_repaint_when_backend_or_watch_reused_then_old_slot_cannot_repaint(
    monkeypatch, teardown, timer_fault, sink_fails
):
    active = [Canvas(1)]
    backend, qt, errors = world(active)
    stale = []
    failure = RuntimeError("repaint teardown")

    def refuse(*args):
        raise failure

    if sink_fails:
        backend.sink = refuse
    token = backend.register(Mouse(), qt, None)
    for epoch in range(2):
        old_canvas = active[0]
        item = watched(old_canvas)[-1]
        item.eventFilter(old_canvas.viewPort, Event(MOVE))
        timer = backend._repaint
        slot = timer.timeout.slots[0]
        stale.append(slot)
        disconnect = timer.timeout.disconnect
        disconnected = []

        def disconnect_exact(callback):
            disconnected.append(callback)
            if timer_fault == "disconnect":
                raise failure
            disconnect(callback)

        monkeypatch.setattr(timer.timeout, "disconnect", disconnect_exact)
        if timer_fault in ("stop", "deleteLater"):
            monkeypatch.setattr(timer, timer_fault, refuse)
        active[0] = Canvas(10 + epoch)
        if teardown == "watch":
            backend._timer.timeout.slots[0]()
        else:
            backend.close() if teardown == "close" else backend.remove(token)
            token = backend.register(Mouse(), qt, None)
        assert timer.deleted is (timer_fault is None)
        assert (timer in backend._kept_timers) is (timer_fault is not None)
        assert item._owner is None and item.deleted
        assert errors == ([] if sink_fails else [failure] * (epoch + 1) * bool(timer_fault))
        canvas = active[0]
        current_filter = watched(canvas)[-1]
        current_filter.eventFilter(canvas.viewPort, Event(MOVE))
        current_timer = backend._repaint
        before = len(errors), len(Timer.made), [t.starts for t in Timer.made]
        for old in stale:
            old()
        item.eventFilter(old_canvas.viewPort, Event(MOVE))
        assert canvas.calls == [] and canvas.updates == []
        assert old_canvas.calls == [] and old_canvas.updates == []
        assert (len(errors), len(Timer.made), [t.starts for t in Timer.made]) == before
        current_timer.fire()
        assert canvas.calls == ["updateScreenRect", "updateViewport"]
        assert canvas.updates == [("QRectF", "viewport-rect")]
        assert disconnected == [] if timer_fault == "stop" else (
            len(disconnected) == 1 and disconnected[0] is slot
        ), "disconnect must receive the exact connected callable"
        canvas.calls.clear()
        canvas.updates.clear()
    backend.close()


@pytest.mark.parametrize("timer_fault", ["stop", "disconnect", "deleteLater"])
@pytest.mark.parametrize("sink_fails", [False, True])
def test_unwatch_when_teardown_reports_then_old_filter_cannot_restart_repaint(
    monkeypatch, timer_fault, sink_fails
):
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    token = backend.register(Mouse(), qt, None)
    item = watched(canvas)[0]
    item.eventFilter(canvas.viewPort, Event(MOVE))
    timer = backend._repaint
    failure = RuntimeError("repaint teardown")

    def refuse(*args):
        raise failure

    def sink(error, source):
        errors.append(error)
        item.eventFilter(canvas.viewPort, Event(MOVE))
        if sink_fails:
            raise RuntimeError("sink")

    backend.sink = sink
    target = timer.timeout if timer_fault == "disconnect" else timer
    monkeypatch.setattr(target, timer_fault, refuse)
    before = len(Timer.made), [t.starts for t in Timer.made]
    backend.remove(token)
    assert (len(Timer.made), [t.starts for t in Timer.made]) == before
    assert backend._repaint is None and item._owner is None
    assert timer in backend._kept_timers and not timer.deleted
    assert errors == [failure] and canvas.calls == []


def test_poll_when_timer_start_fails_then_old_connected_slot_stays_inert_on_retry(
    monkeypatch,
):
    active = [Canvas(1)]
    backend, qt, errors = world(active)
    failure = RuntimeError("start refused")
    failed_timer = Timer()
    connected = []
    connect = failed_timer.timeout.connect
    monkeypatch.setattr(
        failed_timer.timeout, "connect", lambda slot: connected.append(slot) or connect(slot)
    )

    def refuse():
        raise failure

    monkeypatch.setattr(failed_timer, "start", refuse)
    monkeypatch.setattr(qt.QtCore, "QTimer", lambda: failed_timer)
    with pytest.raises(RuntimeError) as caught:
        backend.register(Example(), qt, None)
    assert caught.value is failure
    old = connected[0]
    monkeypatch.setattr(qt.QtCore, "QTimer", Timer)
    backend.register(Example(), qt, None)
    reads = []
    workspace = backend.fl.flWorkspace.instance()
    monkeypatch.setattr(
        workspace, "getActiveCanvas", lambda: reads.append(active[0]) or active[0]
    )
    active[0] = Canvas(2)
    old()
    assert reads == [] and active[0].appended == []
    backend._timer.timeout.slots[0]()
    assert reads == active and len(active[0].appended) == 1 and errors == []
    backend.close()


@pytest.mark.parametrize("transition", ["close", "reuse", "current"])
def test_poll_when_active_getter_reenters_then_obsolete_canvas_is_not_attached(
    monkeypatch, transition
):
    old, candidate, replacement = Canvas(1), Canvas(2), Canvas(3)
    active = [old]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    poll = backend._timer.timeout.slots[0]
    workspace = backend.fl.flWorkspace.instance()
    getter = workspace.getActiveCanvas
    crossings = []

    def get_active():
        monkeypatch.setattr(workspace, "getActiveCanvas", getter)
        crossings.append(transition)
        if transition != "current":
            backend.close()
        if transition == "reuse":
            active[0] = replacement
            backend.register(Mouse(), qt, None)
        return candidate

    monkeypatch.setattr(workspace, "getActiveCanvas", get_active)
    poll()
    assert crossings == [transition]
    assert len(candidate.appended) == (1 if transition == "current" else 0), (
        "an already-running old poll must not attach a current reporter to its old result"
    )
    assert len(watched(candidate)) == (1 if transition == "current" else 0)
    if transition == "reuse":
        assert len(replacement.appended) == len(watched(replacement)) == 1
        assert backend._watch.canvas is replacement
    assert errors == []
    backend.close()


@pytest.mark.parametrize("transition", ["close", "reuse", "current"])
def test_poll_when_error_sink_reenters_then_replacement_painter_is_not_lost(
    monkeypatch, transition,
):
    class FaultCanvas(Canvas):
        fault = None

        @property
        def isNull(self):
            failure, self.fault = self.fault, None
            if failure is not None:
                raise failure
            return self.null

        @isNull.setter
        def isNull(self, value):
            self.null = value

    old, replacement = FaultCanvas(1), Canvas(1)
    removed = []
    monkeypatch.setattr(
        replacement, "removePythonPainter", lambda token: removed.append(token) or True
    )
    active = [old]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    poll = backend._timer.timeout.slots[0]
    failure = RuntimeError("old canvas became unavailable")
    crossings = []

    def sink(error, source):
        errors.append(error)
        if error is failure:
            crossings.append(transition)
            if transition != "current":
                backend.close()
            active[0] = None if transition == "close" else replacement
            if transition == "reuse":
                backend.register(Mouse(), qt, None)

    backend.sink = sink
    old.fault = failure
    poll()
    if transition != "close":
        backend._timer.timeout.slots[0]()
    backend.close()
    assert crossings == [transition]
    assert errors == [failure], "a resumed old deletion must not report a new KeyError"
    assert len(replacement.appended) == (0 if transition == "close" else 1), (
        "a resumed old deletion must not orphan and duplicate the new native painter"
    )
    assert removed == [row[0] for row in replacement.appended], (
        "close must remove every replacement painter, including after a current poll"
    )


@pytest.mark.parametrize("boundary", ["isNull", "rect", "updateScreenRect"])
@pytest.mark.parametrize("transition", ["close", "reuse", "current"])
def test_flush_when_native_boundary_reenters_then_old_repaint_stops(
    monkeypatch, boundary, transition
):
    class HookCanvas(Canvas):
        hook = None

        @property
        def isNull(self):
            hook, self.hook = self.hook, None
            if hook is not None:
                hook()
            return self.null

        @isNull.setter
        def isNull(self, value):
            self.null = value

    class HookViewport(Viewport):
        hook = None

        @property
        def rect(self):
            hook, self.hook = self.hook, None
            if hook is not None:
                hook()
            return self.rectangle

        @rect.setter
        def rect(self, value):
            self.rectangle = value

    old, replacement = HookCanvas(1), Canvas(2)
    old.viewPort = HookViewport()
    active = [old]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    item = watched(old)[0]
    item.eventFilter(old.viewPort, Event(MOVE))
    flush = backend._repaint.timeout.slots[0]
    crossings = []

    def cross():
        crossings.append(transition)
        if transition != "current":
            backend.close()
        if transition == "reuse":
            active[0] = replacement
            backend.register(Mouse(), qt, None)

    if boundary == "isNull":
        old.hook = cross
    elif boundary == "rect":
        old.viewPort.hook = cross
    else:
        update = old.updateScreenRect

        def update_then_cross(rect):
            update(rect)
            cross()

        monkeypatch.setattr(old, "updateScreenRect", update_then_cross)
    flush()
    assert crossings == [transition]
    expected = ["updateScreenRect", "updateViewport"] if transition == "current" else (
        ["updateScreenRect"] if boundary == "updateScreenRect" else []
    )
    assert old.calls == expected, "no further old native repaint after ownership changed"
    assert errors == []
    if transition == "reuse":
        assert replacement.calls == []
        current = watched(replacement)[0]
        current.eventFilter(replacement.viewPort, Event(MOVE))
        backend._repaint.timeout.slots[0]()
        assert replacement.calls == ["updateScreenRect", "updateViewport"]
    backend.close()


@pytest.mark.parametrize("transition", ["close", "reuse"])
def test_flush_when_old_rect_fails_after_reentry_then_current_failure_is_reported(
    monkeypatch, transition
):
    class FailingViewport(Viewport):
        hook = None

        @property
        def rect(self):
            hook, self.hook = self.hook, None
            if hook is not None:
                hook()
                raise old_failure
            return self.rectangle

        @rect.setter
        def rect(self, value):
            self.rectangle = value

    old, replacement = Canvas(1), Canvas(2)
    old.viewPort = FailingViewport()
    active = [old]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    watched(old)[0].eventFilter(old.viewPort, Event(MOVE))
    flush = backend._repaint.timeout.slots[0]
    old_failure = RuntimeError("obsolete viewport rectangle")
    current_failure = RuntimeError("current viewport update")
    crossings = []

    def cross():
        crossings.append(transition)
        backend.close()
        if transition == "reuse":
            active[0] = replacement
            backend.register(Mouse(), qt, None)

    old.viewPort.hook = cross
    flush()
    if transition == "reuse":
        def fail_update(rect):
            raise current_failure

        monkeypatch.setattr(replacement, "updateScreenRect", fail_update)
        watched(replacement)[0].eventFilter(replacement.viewPort, Event(MOVE))
        backend._repaint.timeout.slots[0]()
    assert crossings == [transition]
    assert errors == ([current_failure] if transition == "reuse" else []), (
        "an obsolete flush must not report against or suppress its replacement watch"
    )
    backend.close()


@pytest.mark.parametrize("transition", ["close", "reuse", "current"])
def test_register_when_immediate_poll_reenters_then_original_token_is_not_reattached(
    monkeypatch, transition
):
    candidate, replacement = Canvas(1), Canvas(2)
    active = [candidate]
    backend, qt, errors = world(active)
    workspace = backend.fl.flWorkspace.instance()
    getter = workspace.getActiveCanvas
    crossings, replacement_tokens = [], []

    def get_active():
        monkeypatch.setattr(workspace, "getActiveCanvas", getter)
        crossings.append(transition)
        if transition != "current":
            backend.close()
        if transition == "reuse":
            active[0] = replacement
            replacement_tokens.append(backend.register(Mouse(), qt, None))
        return candidate

    monkeypatch.setattr(workspace, "getActiveCanvas", get_active)
    original_token = backend.register(Mouse(), qt, None)
    assert crossings == [transition]
    assert len(candidate.appended) == (1 if transition == "current" else 0)
    if transition == "reuse":
        assert replacement_tokens != [original_token]
        assert len(replacement.appended) == len(watched(replacement)) == 1
        backend._timer.timeout.slots[0]()
        assert len(replacement.appended) == 1
    assert errors == []
    backend.close()


@pytest.mark.parametrize("boundary", ["viewPort", "installEventFilter"])
@pytest.mark.parametrize("transition", ["close", "remove", "reuse", "current"])
def test_watch_when_successful_attachment_reenters_then_no_filter_is_orphaned(
    monkeypatch, boundary, transition
):
    class HookCanvas(Canvas):
        hook = None

        @property
        def viewPort(self):
            hook, self.hook = self.hook, None
            if hook is not None:
                hook()
            return self.viewport

        @viewPort.setter
        def viewPort(self, value):
            self.viewport = value

    candidate, replacement = HookCanvas(1), Canvas(1)
    active = [None]
    backend, qt, errors = world(active)
    token = backend.register(Mouse(), qt, None)
    viewport = candidate.viewPort
    crossings, installed = [], []
    install = viewport.installEventFilter

    def cross():
        crossings.append(transition)
        if transition == "remove":
            backend.remove(token)
        elif transition != "current":
            backend.close()
        if transition == "reuse":
            active[0] = replacement
            backend.register(Mouse(), qt, None)

    def install_then_cross(item):
        monkeypatch.setattr(viewport, "installEventFilter", install)
        install(item)
        installed.append(item)
        cross()

    if boundary == "viewPort":
        candidate.hook = cross
    else:
        monkeypatch.setattr(viewport, "installEventFilter", install_then_cross)
    active[0] = candidate
    backend._timer.timeout.slots[0]()
    assert crossings == [transition]
    if boundary == "installEventFilter":
        assert len(installed) == 1, "the native install completed before reentry"
    if transition != "current":
        assert viewport.filters == [], "an obsolete install cannot leave an active filter"
    if transition == "reuse":
        assert backend._watch.canvas is replacement
        assert len(replacement.viewPort.filters) == 1
        item = replacement.viewPort.filters[0]
        item.eventFilter(replacement.viewPort, Event(MOVE))
        backend._repaint.timeout.slots[0]()
        assert replacement.calls == ["updateScreenRect", "updateViewport"]
    elif transition == "current":
        assert len(viewport.filters) == 1 and backend._watch.canvas is candidate
    backend.close()
    assert viewport.filters == replacement.viewPort.filters == []
    assert all(item.deleted and item._owner is None for item in installed)
    assert errors == []


@pytest.mark.parametrize("id_read", [1, 2])
@pytest.mark.parametrize("transition", ["close", "remove", "reuse", "current"])
def test_poll_when_later_canvas_id_reenters_then_replacement_attaches_to_its_canvas(
    id_read, transition
):
    class HookCanvas(Canvas):
        hook = None
        reads = 0

        @property
        def id(self):
            self.reads += 1
            hook = self.hook if self.reads == id_read else None
            if hook is not None:
                self.hook = None
                hook()
            return self.identifier

        @id.setter
        def id(self, value):
            self.identifier = value

    candidate, replacement = HookCanvas(1), Canvas(1)
    active = [None]
    backend, qt, errors = world(active)
    token = backend.register(Mouse(), qt, None)
    crossings = []

    def cross():
        crossings.append(transition)
        if transition == "remove":
            backend.remove(token)
        elif transition != "current":
            backend.close()
        if transition == "reuse":
            active[0] = replacement
            backend.register(Mouse(), qt, None)

    candidate.hook = cross
    active[0] = candidate
    backend._timer.timeout.slots[0]()
    assert crossings == [transition]
    if transition in ("close", "remove"):
        active[0] = replacement
        backend.register(Mouse(), qt, None)
    if transition != "current":
        backend._timer.timeout.slots[0]()
        assert candidate.appended == [], "new reporter must not attach to obsolete ID result"
        assert len(replacement.appended) == len(replacement.viewPort.filters) == 1
        assert candidate.viewPort.filters == [], "the old ID read must not orphan a filter"
        assert backend._watch.canvas is replacement
    else:
        assert len(candidate.appended) == len(candidate.viewPort.filters) == 1
        assert replacement.appended == []
    backend.close()
    assert candidate.viewPort.filters == replacement.viewPort.filters == []
    assert errors == []


@pytest.mark.parametrize("boundary", ["id", "viewPort", "installEventFilter"])
def test_watch_when_only_mouse_reporter_is_removed_then_same_timer_stays_unwatched(
    monkeypatch, boundary
):
    class HookCanvas(Canvas):
        id_hook = viewport_hook = None

        @property
        def id(self):
            hook, self.id_hook = self.id_hook, None
            if hook is not None:
                hook()
            return self.identifier

        @id.setter
        def id(self, value):
            self.identifier = value

        @property
        def viewPort(self):
            hook, self.viewport_hook = self.viewport_hook, None
            if hook is not None:
                hook()
            return self.viewport

        @viewPort.setter
        def viewPort(self, value):
            self.viewport = value

    canvas, active = HookCanvas(1), [None]
    backend, qt, errors = world(active)
    mouse = backend.register(Mouse(), qt, None)
    plain = backend.register(Example(), qt, None)
    timer, crossings = backend._timer, []
    viewport = canvas.viewPort

    def remove_mouse():
        backend.remove(mouse)
        crossings.append(backend._timer is timer)

    if boundary == "id":
        canvas.id_hook = remove_mouse
    elif boundary == "viewPort":
        canvas.viewport_hook = remove_mouse
    else:
        install = viewport.installEventFilter

        def install_then_remove(item):
            monkeypatch.setattr(viewport, "installEventFilter", install)
            install(item)
            remove_mouse()

        monkeypatch.setattr(viewport, "installEventFilter", install_then_remove)
    active[0] = canvas
    timer.timeout.slots[0]()
    assert crossings == [True] and backend._timer is timer
    assert len(canvas.appended) == 1, "the ordinary reporter remains attached"
    assert viewport.filters == [], "surviving ordinary reporter does not authorize mouse watch"
    assert backend._watch is None and errors == []
    backend.remove(plain)


@pytest.mark.parametrize("fault", ["isNull", "removeEventFilter", "deleteLater"])
@pytest.mark.parametrize("sink_action", ["collect", "raise", "reuse"])
def test_late_filter_cleanup_when_native_refuses_then_replacement_watch_survives(
    monkeypatch, fault, sink_action
):
    class HookCanvas(Canvas):
        failure = None

        @property
        def isNull(self):
            failure, self.failure = self.failure, None
            if failure is not None:
                raise failure
            return self.null

        @isNull.setter
        def isNull(self, value):
            self.null = value

    old, replacement, latest = HookCanvas(1), Canvas(1), Canvas(1)
    active = [None]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    viewport = old.viewPort
    install = viewport.installEventFilter
    failure = RuntimeError("late filter cleanup")
    candidates = []

    def refuse(*args):
        raise failure

    def sink(error, source):
        errors.append(error)
        if sink_action == "reuse":
            backend.close()
            active[0] = latest
            backend.register(Mouse(), qt, None)
        elif sink_action == "raise":
            raise RuntimeError("sink refused")

    backend.sink = sink

    def install_then_reuse(item):
        monkeypatch.setattr(viewport, "installEventFilter", install)
        install(item)
        candidates.append(item)
        backend.close()
        active[0] = replacement
        backend.register(Mouse(), qt, None)
        replacement.viewPort.filters[0].eventFilter(replacement.viewPort, Event(MOVE))
        if fault == "isNull":
            old.failure = failure
        elif fault == "removeEventFilter":
            monkeypatch.setattr(viewport, "removeEventFilter", refuse)
        else:
            monkeypatch.setattr(item, "deleteLater", refuse)

    monkeypatch.setattr(viewport, "installEventFilter", install_then_reuse)
    active[0] = old
    backend._timer.timeout.slots[0]()
    (item,) = candidates
    assert errors == [failure] and item._owner is None
    assert item in backend._kept_filters and not item.deleted
    assert viewport.filters == ([] if fault == "deleteLater" else [item])
    current = latest if sink_action == "reuse" else replacement
    assert backend._watch.canvas is current and len(current.viewPort.filters) == 1
    made = len(Timer.made)
    item.eventFilter(viewport, Event(MOVE))
    assert len(Timer.made) == made, "the retained old filter cannot start a repaint"
    current.viewPort.filters[0].eventFilter(current.viewPort, Event(MOVE))
    backend._repaint.timeout.slots[0]()
    assert current.calls == ["updateScreenRect", "updateViewport"]
    backend.close()
    assert current.viewPort.filters == replacement.viewPort.filters == []
    assert errors == [failure]


def test_watch_when_obsolete_native_install_fails_then_same_id_can_be_watched_again(
    monkeypatch,
):
    old, replacement, elsewhere, again = Canvas(1), Canvas(1), Canvas(2), Canvas(1)
    active = [None]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    viewport = old.viewPort
    install = viewport.installEventFilter
    candidates = []

    def fail_after_reuse(item):
        monkeypatch.setattr(viewport, "installEventFilter", install)
        candidates.append(item)
        backend.close()
        active[0] = replacement
        backend.register(Mouse(), qt, None)
        raise RuntimeError("obsolete filter refused")

    monkeypatch.setattr(viewport, "installEventFilter", fail_after_reuse)
    active[0] = old
    backend._timer.timeout.slots[0]()
    active[0] = elsewhere
    backend._timer.timeout.slots[0]()
    active[0] = again
    backend._timer.timeout.slots[0]()
    assert len(again.viewPort.filters) == 1 and backend._watch.canvas is again
    assert candidates[0]._owner is None and candidates[0] in backend._kept_filters
    assert errors == []
    backend.close()
    assert again.viewPort.filters == []


def test_late_filter_cleanup_when_canvas_is_null_then_native_remove_is_skipped(
    monkeypatch,
):
    old, active = Canvas(1), [None]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    viewport = old.viewPort
    install, candidates = viewport.installEventFilter, []

    def install_then_destroy(item):
        monkeypatch.setattr(viewport, "installEventFilter", install)
        install(item)
        candidates.append(item)
        backend.close()
        old.isNull = True

    monkeypatch.setattr(viewport, "installEventFilter", install_then_destroy)
    active[0] = old
    backend._timer.timeout.slots[0]()
    (item,) = candidates
    assert item._owner is None and item.deleted
    assert viewport.removed == [] and backend._kept_filters == [] and errors == []
    item.eventFilter(viewport, Event(MOVE))
    assert repaint_timers() == []
    backend.close()


@pytest.mark.parametrize("sink_raises", [False, True])
def test_late_filter_cleanup_when_reporting_then_existing_pending_repaint_survives(
    monkeypatch, sink_raises
):
    old, replacement, active = Canvas(1), Canvas(1), [None]
    backend, qt, errors = world(active)
    backend.register(Mouse(), qt, None)
    viewport = old.viewPort
    install, pending = viewport.installEventFilter, []
    failure = RuntimeError("old filter removal refused")

    def sink(error, source):
        errors.append(error)
        if sink_raises:
            raise RuntimeError("sink refused")

    def refuse(item):
        raise failure

    backend.sink = sink

    def install_then_reuse(item):
        monkeypatch.setattr(viewport, "installEventFilter", install)
        install(item)
        backend.close()
        active[0] = replacement
        backend.register(Mouse(), qt, None)
        replacement.viewPort.filters[0].eventFilter(replacement.viewPort, Event(MOVE))
        pending.append((backend._watch, backend._repaint))
        monkeypatch.setattr(viewport, "removeEventFilter", refuse)

    monkeypatch.setattr(viewport, "installEventFilter", install_then_reuse)
    active[0] = old
    backend._timer.timeout.slots[0]()
    (watch, timer), = pending
    assert backend._watch is watch and backend._repaint is timer
    assert timer.running and timer.starts == 1 and not timer.deleted
    timer.fire()
    assert replacement.calls == ["updateScreenRect", "updateViewport"]
    assert timer.starts == 1 and errors == [failure], "no second MOVE primes this repaint"
    backend.close()
    assert timer.deleted and replacement.viewPort.filters == []


@pytest.mark.parametrize("boundary", ["constructor", "setInterval", "connect", "start"])
def test_register_when_timer_setup_refuses_then_exact_error_and_retry_are_preserved(
    monkeypatch, boundary
):
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    failure = RuntimeError("poll timer refused")
    failed = Timer()

    def refuse(*args):
        raise failure

    if boundary == "constructor":
        monkeypatch.setattr(qt.QtCore, "QTimer", refuse)
    else:
        monkeypatch.setattr(qt.QtCore, "QTimer", lambda: failed)
        target = failed.timeout if boundary == "connect" else failed
        monkeypatch.setattr(target, boundary, refuse)
    with pytest.raises(RuntimeError) as caught:
        backend.register(Mouse(), qt, None)
    assert caught.value is failure
    assert backend._reporters == {} and backend._timer is None
    assert canvas.appended == [] and watched(canvas) == [] and errors == []
    monkeypatch.setattr(qt.QtCore, "QTimer", Timer)
    token = backend.register(Mouse(), qt, None)
    timer = backend._timer
    failed.fire()
    assert backend._timer is timer and token in backend._reporters
    assert len(canvas.appended) == len(watched(canvas)) == 1
    backend.close()
    assert timer.deleted and watched(canvas) == [] and errors == []


@pytest.mark.parametrize(
    "boundary", ["constructor", "setSingleShot", "setInterval", "connect", "isActive", "start"]
)
def test_mouse_move_when_timer_setup_refuses_then_filter_boundary_allows_retry(
    monkeypatch, boundary
):
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    backend.register(Mouse(), qt, None)
    watch = backend._watch
    failure = RuntimeError("repaint timer refused")
    failed = Timer()

    def refuse(*args):
        raise failure

    with monkeypatch.context() as patch:
        if boundary == "constructor":
            patch.setattr(qt.QtCore, "QTimer", refuse)
        else:
            patch.setattr(qt.QtCore, "QTimer", lambda: failed)
            target = failed.timeout if boundary == "connect" else failed
            patch.setattr(target, boundary, refuse)
        assert watch.filter.eventFilter(watch.viewport, Event(MOVE)) is False
        assert watch.filter.eventFilter(watch.viewport, Event(MOVE)) is False
    assert errors == [failure] and canvas.calls == []
    assert backend._watch is watch and watched(canvas) == [watch.filter]
    assert watch.filter.eventFilter(watch.viewport, Event(MOVE)) is False
    timer = backend._repaint
    assert timer.running and timer.starts == 1
    timer.fire()
    assert canvas.calls == ["updateScreenRect", "updateViewport"] and errors == [failure]
    backend.close()
    assert timer.deleted and watched(canvas) == []


@pytest.mark.parametrize("sink_raises", [False, True])
def test_watch_when_widget_constructor_refuses_then_current_painter_and_retry_survive(
    monkeypatch, sink_raises
):
    canvas = Canvas(1)
    backend, qt, errors = world([canvas])
    failure = RuntimeError("widget constructor refused")
    attempts = []
    refusing = [True]

    class RefusedWidget(Widget):
        def __init__(self):
            attempts.append(self._owner)
            if refusing[0]:
                raise failure
            super().__init__()

    def sink(error, source):
        errors.append(error)
        if sink_raises:
            raise RuntimeError("sink refused")

    backend.sink = sink
    monkeypatch.setattr(qt.QtGui, "QWidget", RefusedWidget)
    backend.register(Mouse(), qt, None)
    backend._timer.timeout.slots[0]()
    assert attempts == [None], "the filter constructor has no published backend owner"
    assert errors == [failure] and len(canvas.appended) == 1
    assert backend._watch is None and watched(canvas) == []
    assert backend._kept_filters == []
    backend.close()
    refusing[0] = False
    backend.register(Mouse(), qt, None)
    assert len(watched(canvas)) == 1 and errors == [failure]
    backend.close()
