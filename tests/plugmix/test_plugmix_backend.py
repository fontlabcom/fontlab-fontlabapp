# this_file: tests/plugmix/test_plugmix_backend.py
"""Fake native canvases exercise ownership, orders, transforms and fallback."""

import math
import sys
from types import SimpleNamespace as NS

import pytest

from fontlabapp.plugins import snapshot
from fontlabapp.plugins.backend import EditorBackend, NativeCanvasBackend, select_backend
from fontlabapp.plugins.reporter import Reporter
from paint_safety import Spy, assert_paint_safe, recorder


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Transform:
    def __init__(self, dx, dy):
        self.dx, self.dy = dx, dy

    def map(self, point):
        return Point(point.x() + self.dx, point.y() + self.dy)


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, callback):
        self.slots.append(callback)

    def disconnect(self, callback):
        self.slots.remove(callback)


class Timer:
    def __init__(self):
        self.timeout = Signal()
        self.running = False
        self.deleted = False

    def setInterval(self, value):
        self.interval = value

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def deleteLater(self):
        self.deleted = True

    def setSingleShot(self, value):
        self.single = value

    def isActive(self):
        return self.running


class Widget:
    def deleteLater(self):
        self.deleted = True


class Viewport:
    def __init__(self):
        self.filters, self.installs, self.rect = [], 0, "rect"

    def installEventFilter(self, item):
        self.installs += 1
        self.filters.append(item)

    def removeEventFilter(self, item):
        self.filters.remove(item)


class Canvas:
    UnderOwner, OverOwner = 0, 1

    def __init__(self, identifier):
        self.id = identifier
        self.isNull = False
        self.appended = []
        self.removed = []
        self.blocks = []
        self.remove_result = True
        self.remove_error = None
        self.append_error = None
        self.append_attempts = 0
        self.viewPort = Viewport()
        self.updates = []

    def mousePosition(self):
        return Point(31, 10)

    def updateScreenRect(self, rect):
        self.updates.append(rect)

    def updateViewport(self):
        self.updates.append("updateViewport")

    def appendPythonPainter(self, callback, order):
        self.append_attempts += 1
        if self.append_error is not None:
            raise self.append_error
        token = 100 + len(self.appended)
        self.appended.append((token, callback, order))
        return token

    def removePythonPainter(self, token):
        self.removed.append(token)
        if self.remove_error is not None:
            raise self.remove_error
        return self.remove_result

    def mapToViewportF(self, point):
        return Point(point.x() + 3, point.y() + 4)

    def scale(self):
        return 2

    def textBlocks(self):
        return self.blocks


class Example(Reporter):
    name, title = "example", "Example"

    def compute(self, snapshot):
        return []


class Background(Example):
    name, layer = "background", "background"


def runtime(canvas):
    """Supply only the PythonQt and FontLab pieces the backend touches."""
    workspace = NS(getActiveCanvas=lambda: canvas[0])
    fontlab = NS(flCanvas=Canvas, flWorkspace=NS(instance=lambda: workspace))
    qt = NS(
        QtCore=NS(
            QTimer=Timer,
            QPointF=Point,
            QRectF=lambda rect: rect,
            QEvent=NS(MouseMove=5, HoverMove=129),
        ),
        QtGui=NS(QWidget=Widget),
    )
    return qt, fontlab


def test_native_backend_attaches_both_orders_and_maps_block_position():
    active = [Canvas(1)]
    package = NS(master="Regular")
    layer = NS(isNull=False)
    glyph = NS(isNull=False, package=package, findLayer=lambda master: layer)
    info = NS(
        isActive=True,
        glyph=glyph,
        symbol=NS(layerName=""),
        transform=Transform(10, 0),
    )
    active[0].blocks = [NS(transform=Transform(100, 20), getAllGlyphs=lambda: [info])]
    qt, fontlab = runtime(active)
    errors, observed = [], []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    foreground, background = Example(), Background()
    foreground.paint = lambda context, q, sink: observed.append(context)
    first = backend.register(foreground, qt, lambda e, source: None)
    second = backend.register(background, qt, lambda e, source: None)
    assert [row[2] for row in active[0].appended] == [1, 0]
    assert backend._timer.running and backend._timer.interval == 250
    active[0].scale = lambda: (_ for _ in ()).throw(AssertionError("unused zoom"))
    active[0].appended[0][1](object(), active[0])
    point = observed[0].canvas_to_view.map(observed[0].glyph_to_canvas.map(Point(1, 2)))
    assert (point.x(), point.y()) == (114, 26)
    assert observed[0].layer.package is package
    timer = backend._timer
    active[0].remove_result = False
    backend.remove(first)
    assert active[0].removed == [100], "false means native painter is already gone"
    backend.remove(second)
    assert backend._timer is None and not timer.running and timer.deleted
    assert errors == []


def test_native_backend_reattaches_on_new_canvas_and_removes_all_tokens():
    active = [None]
    qt, fontlab = runtime(active)
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: None, items=lambda get: list(get())
    )
    first = backend.register(Example(), qt, lambda e, source: None)
    assert not backend.canvases, "a missing active canvas is retried by the timer"
    active[0] = Canvas(1)
    backend._poll()
    old = active[0]
    active[0] = Canvas(2)
    backend._poll()
    assert set(backend.canvases) == {1, 2}
    second = backend.register(Background(), qt, lambda e, source: None)
    assert len(old.appended) == len(active[0].appended) == 2
    backend.remove(second)
    assert old.removed == [101] and active[0].removed == [101]
    old.isNull = True
    backend._poll()
    assert set(backend.canvases) == {2}
    backend.close()
    assert active[0].removed == [101, 100]
    assert not backend.canvases
    backend.remove(first)


def test_native_attach_failure_is_reported_once_until_canvas_id_changes():
    active = [Canvas(1)]
    active[0].append_error = TypeError("painter unavailable")
    qt, fontlab = runtime(active)
    errors = []
    backend = NativeCanvasBackend(
        qt,
        fontlab,
        lambda error, source: errors.append(str(error)),
        items=lambda get: list(get()),
    )
    first = backend.register(Example(), qt, lambda error, source: None)
    backend._poll()
    backend.register(Background(), qt, lambda error, source: None)
    assert active[0].append_attempts == 1
    assert errors == ["painter unavailable"]
    active[0].isNull = True
    active[0] = Canvas(1)
    backend._poll()
    assert active[0].append_attempts == 0, "same canvas id remains blocked"
    active[0] = Canvas(2)
    active[0].append_error = ValueError("new canvas failure")
    backend._poll()
    backend._poll()
    assert active[0].append_attempts == 1
    assert errors == ["painter unavailable", "new canvas failure"]
    active[0].isNull = True
    active[0] = Canvas(3)
    backend._poll()
    assert active[0].append_attempts == 2, "new id receives both reporters"
    backend.remove(first)
    backend.close()


def test_native_remove_continues_after_type_error_and_leaked_callback_is_inert():
    active = [Canvas(1)]
    qt, fontlab = runtime(active)
    errors, painted = [], []
    backend = NativeCanvasBackend(
        qt,
        fontlab,
        lambda error, source: errors.append(error),
        items=lambda get: list(get()),
    )
    reporter = Example()
    reporter.paint = lambda context, q, sink: painted.append(context)
    token = backend.register(reporter, qt, lambda error, source: None)
    first = active[0]
    first.blocks = [
        NS(
            transform=Transform(0, 0),
            getAllGlyphs=lambda: [
                NS(
                    isActive=True,
                    glyph=NS(
                        isNull=False,
                        package=NS(master="Regular"),
                        findLayer=lambda m: NS(isNull=False),
                    ),
                    symbol=NS(layerName=""),
                    transform=Transform(0, 0),
                )
            ],
        )
    ]
    callback = first.appended[0][1]
    callback(object(), first)
    assert len(painted) == 1
    first.remove_error = TypeError("stale wrapper")
    active[0] = Canvas(2)
    backend._poll()
    timer = backend._timer
    backend.remove(token)
    assert first.removed == [100] and active[0].removed == [100]
    assert len(errors) == 1 and isinstance(errors[0], TypeError)
    assert timer.deleted and not timer.running
    callback(object(), first)
    assert len(painted) == 1, "a leaked native callback must stop drawing"


def test_native_remove_skips_destroyed_canvas_and_close_stops_timer_on_error():
    active = [Canvas(1)]
    qt, fontlab = runtime(active)
    backend = NativeCanvasBackend(
        qt, fontlab, lambda error, source: None, items=lambda get: list(get())
    )
    token = backend.register(Example(), qt, lambda error, source: None)
    old = active[0]
    old.isNull = True
    backend.remove(token)
    assert old.removed == [], "a destroyed canvas wrapper must not call native removal"

    old.isNull = False
    backend.register(Example(), qt, lambda error, source: None)
    timer = backend._timer
    backend.remove = lambda token: (_ for _ in ()).throw(TypeError("teardown"))
    with pytest.raises(TypeError, match="teardown"):
        backend.close()
    assert timer.deleted and not timer.running
    assert not backend._reporters


def test_native_backend_never_raises_from_callback_or_timer():
    active = [Canvas(1)]
    qt, fontlab = runtime(active)
    errors = []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    info = NS(isActive=True, glyph=NS(isNull=True))
    active[0].blocks = [NS(transform=Transform(0, 0), getAllGlyphs=lambda: [info])]
    backend.register(Example(), qt, lambda e, source: None)
    callback = active[0].appended[0][1]
    callback(object(), active[0])
    active[0].blocks = [NS(transform=Transform(0, 0), getAllGlyphs=lambda: 1 / 0)]
    callback(object(), active[0])
    assert isinstance(errors[0], ZeroDivisionError)
    fontlab.flWorkspace.instance().getActiveCanvas = lambda: 1 / 0
    backend._poll()
    assert len(errors) == 2
    backend.sink = lambda e, source: 1 / 0
    callback(object(), active[0])
    backend._poll()
    backend.close()


def test_backend_selection_prefers_native_and_fallback_logs_once():
    active = [None]
    qt, fontlab = runtime(active)
    errors = []
    native = select_backend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    assert isinstance(native, NativeCanvasBackend)
    native.close()

    class OldCanvas:
        pass

    fontlab.flCanvas = OldCanvas
    calls = []
    painters = NS(
        register=lambda *args, **kw: calls.append((args, kw)) or len(calls),
        remove=lambda token: None,
        close=lambda: None,
    )
    editor = select_backend(
        qt,
        fontlab,
        lambda e, source: errors.append(e),
        editor_factory=lambda *args, **kw: painters,
    )
    assert isinstance(editor, EditorBackend)
    editor.register(Background(), qt, lambda e, source: None)
    editor.register(Background(), qt, lambda e, source: None)
    assert len(errors) == 1
    assert calls[0][0][0] == "after_native_layer"
    assert calls[0][1]["layer_filter"] == "active"
    editor.remove(1)
    editor.close()


class Scale:
    """A uniform scale as a fake block transform."""

    def __init__(self, factor):
        self.factor = factor

    def map(self, point):
        return Point(point.x() * self.factor, point.y() * self.factor)


def painted_contexts(block_transform, canvas, paints=1):
    """Run native paints and return the contexts and reported errors."""
    glyph = NS(
        isNull=False, package=NS(master="M"), findLayer=lambda name: NS(isNull=False)
    )
    info = NS(
        isActive=True, glyph=glyph, symbol=NS(layerName=""), transform=Transform(5, 0)
    )
    canvas.blocks = [NS(transform=block_transform, getAllGlyphs=lambda: [info])]
    qt, fontlab = runtime([canvas])
    errors, observed = [], []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    reporter = Example()
    reporter.paint = lambda context, q, sink: observed.append(context)
    backend.register(reporter, qt, lambda e, source: None)
    for _ in range(paints):
        canvas.appended[0][1](object(), canvas)
    backend.close()
    return observed, errors


def test_native_backend_when_block_scales_then_context_scale_is_px_per_unit():
    observed, errors = painted_contexts(Scale(3), Canvas(1))
    assert observed[0].scale == 3.0, "glyph, block and viewport maps compose"
    assert errors == []


def test_native_backend_when_view_scale_fails_then_paints_without_scale():
    canvas = Canvas(1)
    canvas.mapToViewportF = lambda point: Point(math.nan, point.y())
    observed, errors = painted_contexts(Scale(1), canvas, paints=3)
    assert [c.scale for c in observed] == [None] * 3, "paints go on, without a view"
    assert len(errors) == 1, "a persistent scale failure is reported once per canvas"
    assert isinstance(errors[0], ValueError)


class Seen(Reporter):
    name, title = "seen", "Seen"

    def __init__(self):
        self.snapshots = []

    def compute(self, snapshot):
        self.snapshots.append(snapshot)
        return []


def test_native_paint_path_reads_identity_and_view_without_unsafe_native_calls(
    monkeypatch,
):
    log = []
    record = Spy(log, "record", unicodes=[0x42])
    package = Spy(
        log,
        "package",
        isNull=False,
        fgId=4,
        master="Regular",
        masters=["Regular"],
        italicAngle_value=0,
        upm=1000,
        fgPackage=Spy(log, "fgPackage", items={"B": record}),
        packageLib={},
    )
    layer = Spy(
        log, "layer", isNull=False, name="Alt", shapes=[], anchors=[], advanceWidth=600
    )
    glyph = Spy(
        log,
        "glyph",
        isNull=False,
        id=8,
        lastModified=5,
        package=package,
        findLayer=lambda name: log.append(("glyph", "findLayer", name)) or layer,
        name="B",
        mark=1001,
        tags=[],
    )
    info = Spy(
        log,
        "info",
        isActive=True,
        glyph=glyph,
        symbol=Spy(log, "symbol", layerName="Alt"),
        transform=Transform(0, 0),
    )
    canvas = Canvas(1)
    canvas.blocks = [NS(transform=Scale(2), getAllGlyphs=lambda: [info])]
    metrics = NS(ascender=800, descender=-200, xHeight=500, capsHeight=700)
    monkeypatch.setitem(sys.modules, "fontlab", NS(FontMetrics=lambda p, m: metrics))
    qt, fontlab = runtime([canvas])
    errors = []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    reporter = Seen()
    backend.register(reporter, qt, lambda e, source: errors.append(e))
    canvas.appended[0][1](object(), canvas)
    backend.close()
    assert errors == []
    shot = reporter.snapshots[0]
    assert (shot.identity.name, shot.identity.unicodes) == ("B", (0x42,))
    assert (shot.identity.mark_rgb, shot.identity.exported) == ((128, 128, 128), True)
    assert shot.view.px_per_unit == 2.0
    assert ("glyph", "findLayer", "Alt") in log, "the slot's own layer is painted"
    assert_paint_safe(log)
    assert [e for e in log if e[0] == "fgPackage"] == [("fgPackage", "item", "B")]


def test_native_paint_when_two_reporters_paint_twice_then_identity_read_once(
    monkeypatch,
):
    from fontlabapp.plugins import snapshot

    reads = []
    real = snapshot.read_identity
    monkeypatch.setattr(
        snapshot,
        "read_identity",
        lambda package, glyph: reads.append(glyph.name) or real(package, glyph),
    )
    package = NS(
        isNull=False,
        fgId=4,
        master="Regular",
        italicAngle_value=0,
        upm=1000,
        fgPackage={"C": NS(unicodes=[0x43])},
        packageLib={},
    )
    layer = NS(isNull=False, name="Regular", shapes=[], anchors=[], advanceWidth=1)
    glyph = NS(
        isNull=False,
        id=9,
        lastModified=7,
        package=package,
        findLayer=lambda name: layer,
        name="C",
        mark=0,
        tags=[],
    )
    info = NS(
        isActive=True, glyph=glyph, symbol=NS(layerName=""), transform=Transform(0, 0)
    )
    canvas = Canvas(1)
    canvas.blocks = [NS(transform=Transform(0, 0), getAllGlyphs=lambda: [info])]
    metrics = NS(ascender=800, descender=-200, xHeight=500, capsHeight=700)
    monkeypatch.setitem(sys.modules, "fontlab", NS(FontMetrics=lambda p, m: metrics))
    qt, fontlab = runtime([canvas])
    errors = []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    first, second = Seen(), Seen()
    backend.register(first, qt, lambda e, source: errors.append(e))
    backend.register(second, qt, lambda e, source: errors.append(e))
    for _ in range(2):
        for _token, callback, _order in canvas.appended:
            callback(object(), canvas)
    backend.close()
    assert errors == []
    assert len(first.snapshots) == len(second.snapshots) == 2
    assert {s.identity.name for s in first.snapshots + second.snapshots} == {"C"}
    assert reads == ["C"], "the identity cache is shared across reporters and paints"


class Shift:
    """A translation that also answers QTransform's affine getters."""

    def __init__(self, dx, dy):
        self._dx, self._dy = dx, dy

    def map(self, point):
        return Point(point.x() + self._dx, point.y() + self._dy)

    def dx(self):
        return self._dx

    def dy(self):
        return self._dy

    def isAffine(self):
        return True

    def m11(self):
        return 1

    def m12(self):
        return 0

    def m21(self):
        return 0

    def m22(self):
        return 1


class Wants(Seen):
    name, title = "wants", "Wants"
    needs_components = needs_background = needs_masters = True


def optional_world(log):
    """A Spy glyph ``A`` with a component of ``B``, a mask and two masters."""

    def plain(x):
        node = NS(position=Point(x, 0), isOn=lambda: True, selected=False)
        return NS(
            isComponent=False,
            contours=[NS(nodes=lambda: [node])],
            transform=Shift(0, 0),
        )

    mask = Spy(
        log,
        "mask",
        isNull=False,
        isValid=True,
        autoLayer=False,
        glyph=NS(id=8),
        shapes=[plain(4)],
    )
    shown = Spy(
        log,
        "layer",
        isNull=False,
        name="Regular",
        isMaskLayer=False,
        getMaskLayer=recorder(log, "layer", "getMaskLayer", mask),
        shapes=[
            plain(1),
            NS(
                isComponent=True,
                shapeData=NS(componentGlyph="B", componentLayer=""),
                transform=Shift(100, 0),
            ),
        ],
        anchors=[],
        advanceWidth=600,
    )
    bold = Spy(
        log, "bold", isNull=False, shapes=[plain(2)], anchors=[], advanceWidth=700
    )
    base_layer = Spy(log, "baseLayer", isNull=False, shapes=[plain(7)])
    base = Spy(
        log,
        "base",
        isNull=False,
        lastModified=1,
        findLayer=recorder(log, "base", "findLayer", base_layer),
    )
    layers = {"Regular": shown, "Bold": bold}
    package = Spy(
        log,
        "package",
        isNull=False,
        fgId=4,
        master="Regular",
        masters=["Regular", "Bold"],
        italicAngle_value=0,
        upm=1000,
        fgPackage=Spy(log, "fgPackage", items={"A": NS(unicodes=[0x41])}),
        packageLib={},
        findName=lambda name: (
            log.append(("package", "call", "findName", (name,))) or base
        ),
    )
    glyph = Spy(
        log,
        "glyph",
        isNull=False,
        id=8,
        lastModified=5,
        package=package,
        findLayer=lambda name: (
            log.append(("glyph", "call", "findLayer", (name,))) or layers[name]
        ),
        name="A",
        mark=0,
        tags=[],
    )
    info = NS(
        isActive=True, glyph=glyph, symbol=NS(layerName=""), transform=Transform(0, 0)
    )
    canvas = Canvas(1)
    canvas.blocks = [NS(transform=Transform(0, 0), getAllGlyphs=lambda: [info])]
    return canvas


def paint_reporters(monkeypatch, canvas, reporters, paints):
    metrics = NS(ascender=800, descender=-200, xHeight=500, capsHeight=700)
    monkeypatch.setitem(sys.modules, "fontlab", NS(FontMetrics=lambda p, m: metrics))
    qt, fontlab = runtime([canvas])
    errors = []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    for reporter in reporters:
        backend.register(reporter, qt, lambda e, source: errors.append(e))
    for _ in range(paints):
        for _token, callback, _order in canvas.appended:
            callback(object(), canvas)
    backend.close()
    return errors


def test_native_paint_path_reads_optional_data_once_and_paint_safely(monkeypatch):
    log = []
    wants, plain = Wants(), Seen()
    errors = paint_reporters(monkeypatch, optional_world(log), [wants, plain], 2)
    assert errors == []
    shot = wants.snapshots[0]
    assert [n.x for n in shot.components[0].contours[0].nodes] == [107]
    assert [n.x for n in shot.background[0].nodes] == [4]
    assert [(m.name, m.advance, m.compatible) for m in shot.masters] == [
        ("Regular", 600.0, True),
        ("Bold", 700.0, True),
    ]
    assert wants.snapshots[1] == shot
    assert all(
        (s.components, s.background, s.masters) == ((), None, ())
        for s in plain.snapshots
    ), "a reporter gets only the data it asked for"
    calls = [e for e in log if e[1] == "call"]
    assert calls.count(("layer", "call", "getMaskLayer", (False,))) == 2  # per paint
    assert calls.count(("base", "call", "findLayer", ("Regular",))) == 1
    assert calls.count(("glyph", "call", "findLayer", ("Bold",))) == 1
    assert [e for e in log if e[0] == "bold" and e[2] == "shapes"] == [
        ("bold", "get", "shapes")
    ], "each datum is read once across reporters and paints"
    assert_paint_safe(log, allowed={("layer", "getMaskLayer", (False,))})
    assert not [e for e in log if e[0] == "mask" and e[1] == "call"]


def test_native_paint_when_no_reporter_asks_then_optional_data_is_never_touched(
    monkeypatch,
):
    log = []
    plain = Seen()
    assert paint_reporters(monkeypatch, optional_world(log), [plain], 2) == []
    touched = {e[2] for e in log}
    assert not touched & {"getMaskLayer", "findName", "masters", "isMaskLayer"}
    assert not [e for e in log if e[0] in {"mask", "bold", "base", "baseLayer"}]
    assert_paint_safe(log)


class Kerned(Transform):
    """A slot transform that also answers ``m11``."""

    def __init__(self, dx, scale=2.0):
        super().__init__(dx, 0)
        self.scale = scale

    def map(self, point):
        return Point(point.x() * self.scale + self.dx, point.y() * self.scale)

    def m11(self):
        return self.scale


class Near(Seen):
    name, title = "near", "Near"
    needs_neighbours = needs_kerning = True

    def requested_glyphs(self, identity, kerning_groups=None):
        return ("n", identity.name)


def neighbour_world(log, *, skipped=True, unplaced=False):
    """``T o n`` on one line; ``o`` is active. getAllGlyphs drops ``T``.

    So the active slot is list item 0 but paragraph index 1 (a-src
    getAllGlyphs skips unplaced entries); neighbours must use index 1.
    ``unplaced`` prepends an active slot with line index -1, which
    getAllGlyphs drops; the paragraph scan must skip it too.
    """
    shape = NS(
        isComponent=False,
        contours=[
            NS(
                nodes=lambda: [
                    NS(position=Point(6, 0), isOn=lambda: True, selected=True)
                ]
            )
        ],
        transform=Transform(0, 0),
    )
    other_layer = Spy(log, "otherLayer", isNull=False, name="Regular", shapes=[shape])
    other = Spy(
        log,
        "other",
        isNull=False,
        id=30,
        name="n",
        lastModified=1,
        findLayer=recorder(log, "other", "findLayer", other_layer),
    )
    groups = Spy(
        log,
        "groups",
        items=recorder(
            log,
            "groups",
            "items",
            [("L", (["o"], "KernLeft")), ("R", (["o"], "KernRight"))],
        ),
    )
    kerning = Spy(log, "kerning", groups=groups)
    shown = Spy(
        log,
        "layer",
        isNull=False,
        name="Regular",
        shapes=[],
        anchors=[],
        advanceWidth=500,
    )
    package = Spy(
        log,
        "package",
        isNull=False,
        fgId=4,
        master="Regular",
        masters=["Regular"],
        italicAngle_value=0,
        upm=1000,
        fgPackage=Spy(log, "fgPackage", items={"o": NS(unicodes=[0x6F])}),
        packageLib={},
        kerning=recorder(log, "package", "kerning", kerning),
        findName=lambda name: (
            log.append(("package", "call", "findName", (name,)))
            or {"n": other}.get(name)
        ),
    )

    def glyph(label, name):
        return Spy(
            log,
            label,
            isNull=False,
            id=8,
            lastModified=5,
            package=package,
            findLayer=recorder(log, label, "findLayer", shown),
            name=name,
            mark=0,
            tags=[],
        )

    def slot(label, name, kern, active=False):
        return Spy(
            log,
            label + "Info",
            isActive=active,
            glyph=glyph(label, name),
            symbol=NS(layerName=""),
            transform=Kerned(10),
            kerningOffset=recorder(log, label + "Info", "kerningOffset", kern),
        )

    slots = [slot("T", "T", -80.0), slot("o", "o", 30.0, True), slot("n", "n", 4.0)]
    listed = slots[1:] if skipped else slots
    lines = [0] * len(slots)
    if unplaced:
        slots.insert(0, slot("x", "x", 0.0, True))
        lines.insert(0, -1)
    block = Spy(
        log,
        "block",
        transform=Transform(0, 0),
        getAllGlyphs=lambda: listed,
        glyphsCount=lambda: len(slots),
        getLineIndex=lambda i: lines[i],
        getGlyphAt=lambda i: (
            log.append(("block", "call", "getGlyphAt", (i,))) or slots[i]
        ),
        getPrevGlyphInLine=lambda i: (
            log.append(("block", "call", "getPrevGlyphInLine", (i,)))
            or (slots[i - 1] if i > 0 else None)
        ),
        getNextGlyphInLine=lambda i: (
            log.append(("block", "call", "getNextGlyphInLine", (i,)))
            or (slots[i + 1] if i + 1 < len(slots) else None)
        ),
    )
    canvas = Canvas(1)
    canvas.blocks = [block]
    return canvas


def test_native_paint_path_reads_task3_data_paint_safely_and_never_writes_kerning(
    monkeypatch,
):
    log = []
    near, plain = Near(), Seen()
    errors = paint_reporters(monkeypatch, neighbour_world(log), [near, plain], 2)
    assert errors == []
    shot = near.snapshots[0]
    assert shot.view.neighbours == snapshot.Neighbours(("T", -40.0), ("n", 15.0))
    assert (shot.kerning_groups.left, shot.kerning_groups.right) == ("L", "R")
    assert list(shot.others) == ["n"], "glyph o is not found by findName here"
    assert [n.x for n in shot.others["n"][0].nodes] == [6]
    assert near.snapshots[1] == shot
    assert all(
        (s.kerning_groups, dict(s.others), s.view.neighbours) == (None, {}, None)
        for s in plain.snapshots
    ), "a reporter gets only the Task 3 data it asked for"
    calls = [e for e in log if e[1] == "call"]
    assert calls.count(("block", "call", "getPrevGlyphInLine", (1,))) == 2
    assert calls.count(("block", "call", "getNextGlyphInLine", (1,))) == 2
    assert {e[3] for e in calls if e[2] == "kerningOffset"} == {(True,)}
    assert calls.count(("package", "call", "kerning", ("Regular",))) == 2, (
        "kerning groups are read on every paint, never cached"
    )
    assert calls.count(("other", "call", "findLayer", ("Regular",))) == 2
    assert [e for e in log if e[0] == "otherLayer" and e[2] == "shapes"] == [
        ("otherLayer", "get", "shapes")
    ], "other glyph outlines are read once per its revision"
    assert {e[2] for e in log if e[0] == "kerning"} == {"groups"}
    assert {e[2] for e in log if e[0] == "groups"} == {"items"}
    assert not [
        e for e in log if e[0] in {"T", "n"} and e[2] in {"findLayer", "shapes"}
    ], "neighbour glyphs give only their names"
    assert_paint_safe(log)


def test_native_paint_when_active_glyph_is_unplaced_then_scan_skips_it(monkeypatch):
    log = []
    near = Near()
    errors = paint_reporters(
        monkeypatch, neighbour_world(log, unplaced=True), [near], 1
    )
    assert errors == []
    assert near.snapshots[0].view.neighbours == snapshot.Neighbours(
        ("T", -40.0), ("n", 15.0)
    ), "an unplaced active slot (lineIndex < 0) must not shift the pairing"
    calls = [e for e in log if e[1] == "call"]
    assert ("block", "call", "getPrevGlyphInLine", (2,)) in calls


def test_native_paint_when_one_side_fails_then_other_survives_and_reported_once(
    monkeypatch,
):
    log = []
    canvas = neighbour_world(log)
    first = canvas.blocks[0].getGlyphAt(0)  # the "T" slot, prev of "o"
    object.__getattribute__(first, "_attrs")["kerningOffset"] = lambda on: math.nan
    near = Near()
    errors = paint_reporters(monkeypatch, canvas, [near], 3)
    assert {s.view.neighbours for s in near.snapshots} == {
        snapshot.Neighbours(None, ("n", 15.0))
    }
    assert len(errors) == 1 and isinstance(errors[0], ValueError)


def test_native_close_when_attach_refused_then_same_canvas_can_attach_again():
    canvas = Canvas(1)
    failure = TypeError("painter unavailable")
    canvas.append_error = failure
    qt, fontlab = runtime([canvas])
    errors = []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    first = backend.register(Example(), qt, None)
    poll = backend._timer.timeout.slots[0]
    poll()
    canvas.append_error = None
    poll()
    assert canvas.append_attempts == 1 and errors == [failure]
    backend.close()
    poll()
    assert canvas.append_attempts == 1, "late polling cannot reopen a closed epoch"
    second = backend.register(Example(), qt, None)
    assert second != first and canvas.append_attempts == 2
    assert len(canvas.appended) == 1, "close permits the same canvas ID to attach"
    backend.close()


@pytest.mark.parametrize("remove_fault", ["native", "backend"])
def test_native_close_when_removal_fails_then_resets_real_capture_and_reports(
    monkeypatch, remove_fault
):
    log = []
    canvas = optional_world(log)
    qt, fontlab = runtime([canvas])
    metrics = NS(ascender=800, descender=-200, xHeight=500, capsHeight=700)
    monkeypatch.setitem(sys.modules, "fontlab", NS(FontMetrics=lambda p, m: metrics))
    canvas.mapToViewportF = lambda point: Point(math.nan, point.y())
    reporter, errors = Seen(), []
    reporter.needs_mouse = True
    compute_error = RuntimeError("compute failure")

    def compute(shot):
        reporter.snapshots.append(shot)
        raise compute_error

    reporter.compute = compute
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    first = backend.register(reporter, qt, None)
    painter = canvas.appended[0][1]
    painter(object(), canvas)
    glyph = canvas.blocks[0].getAllGlyphs()[0].glyph
    object.__getattribute__(glyph, "_attrs")["mark"] = 1001
    painter(object(), canvas)
    assert [s.identity.mark for s in reporter.snapshots] == [0, 0]
    assert len(errors) == 2 and isinstance(errors[0], ValueError)
    assert errors[1] is compute_error, "persistent view/compute failures are suppressed"
    timer = backend._timer
    poll = timer.timeout.slots[0]
    item = canvas.viewPort.filters[0]
    item.eventFilter(canvas.viewPort, NS(type=lambda: 5))
    repaint = backend._repaint
    flush = repaint.timeout.slots[0]
    removal_error = TypeError("remove failure")
    original_remove = backend.remove
    if remove_fault == "native":
        canvas.remove_error = removal_error
        backend.close()
        assert errors[-1] is removal_error, "native removal reports and continues"
    else:
        backend.remove = lambda token: (_ for _ in ()).throw(removal_error)
        with pytest.raises(TypeError) as caught:
            backend.close()
        assert caught.value is removal_error, "the original close error propagates"
        backend.remove = original_remove
    for owned in (timer, repaint):
        assert owned.deleted and not owned.running and owned.timeout.slots == []
    assert canvas.viewPort.filters == [] and item.deleted
    backend.close()
    before = len(errors)
    painter(object(), object())
    poll()
    flush()
    item.eventFilter(canvas.viewPort, NS(type=lambda: 5))
    assert canvas.updates == [] and len(reporter.snapshots) == 2
    assert len(errors) == before, "late callbacks neither read nor report"
    canvas.remove_error = None
    second = backend.register(reporter, qt, None)
    assert second != first
    painter(object(), object())
    current_painter = canvas.appended[-1][1]
    current_painter(object(), canvas)
    current_painter(object(), canvas)
    assert [s.identity.mark for s in reporter.snapshots] == [0, 0, 1001, 1001]
    assert reporter.snapshots[-1].identity.mark_rgb == (128, 128, 128)
    assert len(errors) == before + 2 and isinstance(errors[-2], ValueError)
    assert errors[-1] is compute_error, "close resets real report suppression too"
    backend.close()
    assert_paint_safe(log)


class Grid:
    """A full QTransform-like fake (``affine`` reads all six getters)."""

    def __init__(self, scale, shift):
        self.s, self.shift = scale, shift

    def map(self, point):
        return Point(point.x() * self.s + self.shift, point.y() * self.s)

    def m11(self):
        return self.s

    def m12(self):
        return 0.0

    def m21(self):
        return 0.0

    def m22(self):
        return self.s

    def dx(self):
        return self.shift

    def dy(self):
        return 0.0


class Pointer(Seen):
    name, title = "pointer", "Pointer"
    needs_mouse = True


def test_native_paint_path_maps_mouse_paint_safely(monkeypatch):
    log = []
    canvas = neighbour_world(log)
    block = canvas.blocks[0]
    object.__getattribute__(block, "_attrs")["transform"] = Grid(1, 1)
    shown = object.__getattribute__(block, "_attrs")["getAllGlyphs"]()[0]
    object.__getattribute__(shown, "_attrs")["transform"] = Grid(2, 10)
    metrics = NS(ascender=800, descender=-200, xHeight=500, capsHeight=700)
    monkeypatch.setitem(sys.modules, "fontlab", NS(FontMetrics=lambda p, m: metrics))
    qt, fontlab = runtime([canvas])
    errors = []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda e, source: errors.append(e), items=lambda get: list(get())
    )
    pointer = Pointer()
    backend.register(pointer, qt, lambda e, source: errors.append(e))
    assert canvas.viewPort.installs == 1, "installed at register, not in paint"
    for _ in range(2):
        canvas.appended[0][1](object(), canvas)
    assert canvas.viewPort.installs == 1 and canvas.updates == [], (
        "a paint never installs a filter or forces a repaint"
    )
    backend.close()
    assert errors == [] and canvas.viewPort.filters == []
    # canvas = block(glyph(p)) = (2x + 10 + 1, 2y); mouse (31, 10)
    assert [s.view.mouse for s in pointer.snapshots] == [(10.0, 5.0)] * 2
    assert not [
        e for e in log if e[2] in {"getGlyphAt", "getPrevGlyphInLine", "kerning"}
    ], "the mouse needs no neighbour or kerning reads"
    assert_paint_safe(log)


def test_native_paint_when_no_reporter_asks_then_task3_data_is_never_touched(
    monkeypatch,
):
    log = []
    assert paint_reporters(monkeypatch, neighbour_world(log), [Seen()], 2) == []
    touched = {e[2] for e in log}
    assert not touched & {
        "kerning",
        "kerningOffset",
        "findName",
        "getGlyphAt",
        "getPrevGlyphInLine",
        "getNextGlyphInLine",
        "glyphsCount",
    }
    assert_paint_safe(log)


def test_native_paint_when_neighbours_fail_then_reported_once_and_paints_go_on(
    monkeypatch,
):
    log = []
    canvas = neighbour_world(log)
    block = canvas.blocks[0]
    object.__getattribute__(block, "_attrs")["glyphsCount"] = lambda: 0
    near = Near()
    errors = paint_reporters(monkeypatch, canvas, [near], 3)
    assert len(near.snapshots) == 3
    assert {s.view.neighbours for s in near.snapshots} == {None}
    assert len(errors) == 1 and isinstance(errors[0], ValueError)


@pytest.mark.parametrize("completion", ["before_reentry", "after_reentry"])
@pytest.mark.parametrize("transition", ["close", "remove", "reuse", "current"])
def test_painter_when_successful_append_reenters_then_every_handle_remains_owned(
    monkeypatch, completion, transition
):
    candidate, replacement = Canvas(1), Canvas(1)
    active = [None]
    qt, fontlab = runtime(active)
    errors, crossings = [], []
    backend = NativeCanvasBackend(
        qt, fontlab, lambda error, source: errors.append(error),
        items=lambda get: list(get()),
    )
    token = backend.register(Example(), qt, None)
    append = candidate.appendPythonPainter

    def cross():
        crossings.append(transition)
        if transition == "remove":
            backend.remove(token)
        elif transition != "current":
            backend.close()
        if transition == "reuse":
            active[0] = replacement
            backend.register(Example(), qt, None)

    def append_then_return(callback, order):
        monkeypatch.setattr(candidate, "appendPythonPainter", append)
        if completion == "after_reentry":
            cross()
        native = append(callback, order)
        if completion == "before_reentry":
            cross()
        return native

    monkeypatch.setattr(candidate, "appendPythonPainter", append_then_return)
    active[0] = candidate
    backend._timer.timeout.slots[0]()
    assert crossings == [transition]
    assert len(candidate.appended) == 1, "the in-flight native append succeeds"
    if transition == "reuse":
        backend._timer.timeout.slots[0]()
        assert len(replacement.appended) == 1, "current polling does not duplicate painters"
    backend.close()
    assert candidate.removed == [row[0] for row in candidate.appended], (
        "a successful append must be removed even when its reporter disappeared in flight"
    )
    assert replacement.removed == [row[0] for row in replacement.appended]
    assert errors == []


@pytest.mark.parametrize("native_handle", [0, False, 17])
def test_attach_when_only_its_token_is_removed_then_same_timer_survivor_is_owned(
    monkeypatch, native_handle
):
    canvas, active = Canvas(1), [None]
    qt, fontlab = runtime(active)
    errors = []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    target = backend.register(Example(), qt, None)
    survivor = backend.register(Background(), qt, None)
    timer = backend._timer
    append = canvas.appendPythonPainter
    crossings = []

    def complete_after_remove(callback, order):
        monkeypatch.setattr(canvas, "appendPythonPainter", append)
        backend.remove(target)
        crossings.append(backend._timer is timer)
        append(callback, order)
        canvas.appended[-1] = (native_handle, callback, order)
        return native_handle

    monkeypatch.setattr(canvas, "appendPythonPainter", complete_after_remove)
    active[0] = canvas
    timer.timeout.slots[0]()
    assert crossings == [True], "the survivor keeps this exact poll timer"
    assert len(canvas.appended) == 2 and canvas.appended[0][0] is native_handle
    assert errors == []
    backend.remove(survivor)
    assert canvas.removed == [row[0] for row in canvas.appended], (
        "removed token's late handle and surviving reporter's handle both need cleanup"
    )


@pytest.mark.parametrize("native_handle", [0, False])
def test_attach_when_current_native_handle_is_falsy_then_remove_still_disposes_it(
    monkeypatch, native_handle
):
    canvas = Canvas(1)
    append = canvas.appendPythonPainter

    def append_falsy(callback, order):
        append(callback, order)
        canvas.appended[-1] = (native_handle, callback, order)
        return native_handle

    monkeypatch.setattr(canvas, "appendPythonPainter", append_falsy)
    qt, fontlab = runtime([canvas])
    errors = []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    token = backend.register(Example(), qt, None)
    backend.remove(token)
    assert len(canvas.removed) == 1 and canvas.removed[0] is native_handle
    assert errors == []


def test_attach_when_first_of_multiple_reporters_closes_then_stale_tuple_is_inert(
    monkeypatch,
):
    canvas, active = Canvas(1), [None]
    qt, fontlab = runtime(active)
    errors = []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    backend.register(Example(), qt, None)
    backend.register(Background(), qt, None)
    append = canvas.appendPythonPainter
    crossings = []

    def append_then_close(callback, order):
        monkeypatch.setattr(canvas, "appendPythonPainter", append)
        native = append(callback, order)
        backend.close()
        crossings.append("closed")
        return native

    monkeypatch.setattr(canvas, "appendPythonPainter", append_then_close)
    active[0] = canvas
    backend._timer.timeout.slots[0]()
    assert crossings == ["closed"] and len(canvas.appended) == 1
    assert errors == [], "stale second token must not raise a reported KeyError"
    assert canvas.removed == [canvas.appended[0][0]]
    backend.close()


@pytest.mark.parametrize("fault", ["isNull", "removePythonPainter"])
@pytest.mark.parametrize("sink_action", ["collect", "raise", "reuse"])
def test_late_painter_cleanup_when_native_refuses_then_replacement_stays_owned(
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
    qt, fontlab = runtime(active)
    failure = RuntimeError("late painter cleanup")
    errors = []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    backend.register(Example(), qt, None)
    append = old.appendPythonPainter
    crossings = []

    def sink(error, source):
        errors.append(error)
        if sink_action == "reuse":
            backend.close()
            active[0] = latest
            backend.register(Example(), qt, None)
        elif sink_action == "raise":
            raise RuntimeError("sink refused")

    backend.sink = sink

    def append_then_reuse(callback, order):
        monkeypatch.setattr(old, "appendPythonPainter", append)
        native = append(callback, order)
        backend.close()
        active[0] = replacement
        backend.register(Example(), qt, None)
        if fault == "isNull":
            old.failure = failure
        else:
            old.remove_error = failure
        crossings.append(native)
        return native

    monkeypatch.setattr(old, "appendPythonPainter", append_then_reuse)
    active[0] = old
    backend._timer.timeout.slots[0]()
    assert crossings == [100] and errors == [failure]
    current = latest if sink_action == "reuse" else replacement
    backend._timer.timeout.slots[0]()
    assert len(current.appended) == 1
    old.appended[0][1](object(), object())
    assert errors == [failure], "failed-cleanup painter is inert and not automatically retried"
    backend.close()
    assert current.removed == [current.appended[0][0]]
    assert replacement.removed == [row[0] for row in replacement.appended]
    assert old.removed == ([] if fault == "isNull" else [100])


def test_attach_when_obsolete_native_append_fails_then_replacement_is_not_blocked(
    monkeypatch,
):
    old, replacement = Canvas(1), Canvas(1)
    active = [None]
    qt, fontlab = runtime(active)
    errors = []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    backend.register(Example(), qt, None)
    append = old.appendPythonPainter

    def fail_after_reuse(callback, order):
        monkeypatch.setattr(old, "appendPythonPainter", append)
        backend.close()
        active[0] = replacement
        backend.register(Example(), qt, None)
        raise RuntimeError("obsolete append refused")

    monkeypatch.setattr(old, "appendPythonPainter", fail_after_reuse)
    active[0] = old
    backend._timer.timeout.slots[0]()
    backend.register(Background(), qt, None)
    assert len(replacement.appended) == 2 and errors == []
    backend.close()
    assert replacement.removed == [row[0] for row in replacement.appended]


def test_late_painter_cleanup_when_canvas_is_null_then_native_remove_is_skipped(
    monkeypatch,
):
    old, active = Canvas(1), [None]
    qt, fontlab = runtime(active)
    errors = []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    backend.register(Example(), qt, None)
    append = old.appendPythonPainter

    def append_then_destroy(callback, order):
        monkeypatch.setattr(old, "appendPythonPainter", append)
        native = append(callback, order)
        backend.close()
        old.isNull = True
        return native

    monkeypatch.setattr(old, "appendPythonPainter", append_then_destroy)
    active[0] = old
    backend._timer.timeout.slots[0]()
    backend.close()
    assert len(old.appended) == 1 and old.removed == [] and errors == []
    old.appended[0][1](object(), object())
    assert errors == []



def test_late_painter_cleanup_when_native_remove_returns_false_then_no_retry(
    monkeypatch,
):
    old, replacement, active = Canvas(1), Canvas(1), [None]
    old.remove_result = False
    qt, fontlab = runtime(active)
    errors = []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    backend.register(Example(), qt, None)
    append = old.appendPythonPainter

    def append_then_reuse(callback, order):
        monkeypatch.setattr(old, "appendPythonPainter", append)
        native = append(callback, order)
        backend.close()
        active[0] = replacement
        backend.register(Example(), qt, None)
        return native

    monkeypatch.setattr(old, "appendPythonPainter", append_then_reuse)
    active[0] = old
    backend._timer.timeout.slots[0]()
    assert old.removed == [100] and len(replacement.appended) == 1 and errors == []
    backend._timer.timeout.slots[0]()
    backend.close()
    assert old.removed == [100], "False means already gone, not a cleanup retry request"
    assert replacement.removed == [100] and errors == []


@pytest.mark.parametrize("boundary", ["UnderOwner", "OverOwner", "layer"])
@pytest.mark.parametrize("transition", ["close", "remove", "reuse", "current"])
@pytest.mark.parametrize("refuses", [False, True])
def test_order_when_getter_reenters_then_only_current_registration_is_attached(
    monkeypatch, boundary, transition, refuses
):
    class Candidate(Canvas):
        pass

    class Ordered(Example):
        layer = "background" if boundary == "UnderOwner" else "foreground"

    candidate, replacement = Candidate(1), Canvas(1)
    active = [None]
    qt, fontlab = runtime(active)
    errors, crossings = [], []
    backend = NativeCanvasBackend(qt, fontlab, lambda e, source: errors.append(e))
    token = backend.register(Ordered(), qt, None)
    failure = RuntimeError("order refused")

    def order_getter(instance):
        monkeypatch.setattr(Ordered if boundary == "layer" else Candidate, boundary, value)
        crossings.append(transition)
        if transition == "remove":
            backend.remove(token)
        elif transition != "current":
            backend.close()
        if transition == "reuse":
            active[0] = replacement
            backend.register(Example(), qt, None)
        if refuses:
            raise failure
        return value

    value = Ordered.layer if boundary == "layer" else getattr(Canvas, boundary)
    monkeypatch.setattr(
        Ordered if boundary == "layer" else Candidate, boundary, property(order_getter)
    )
    active[0] = candidate
    backend._timer.timeout.slots[0]()
    assert crossings == [transition]
    assert len(candidate.appended) == int(transition == "current" and not refuses)
    assert errors == ([failure] if transition == "current" and refuses else [])
    assert backend._failed_canvas_ids == (
        {1: str(failure)} if transition == "current" and refuses else {}
    )
    if transition == "reuse":
        assert len(replacement.appended) == 1 and backend.canvases[1].canvas is replacement
        backend._timer.timeout.slots[0]()
        assert len(replacement.appended) == 1
    elif transition == "current":
        backend._timer.timeout.slots[0]()
        assert len(candidate.appended) == int(not refuses)
        assert errors == ([failure] if refuses else [])
    else:
        assert backend._timer is None and not backend._reporters and not backend.canvases
    backend.close()
    assert candidate.removed == [row[0] for row in candidate.appended]
    assert replacement.removed == [row[0] for row in replacement.appended]


def test_native_selection_when_constructed_then_no_native_resource_is_started():
    qt, fontlab = runtime([Canvas(1)])
    calls = []
    qt.QtCore.QTimer = lambda: calls.append("timer")
    fontlab.flWorkspace.instance = lambda: calls.append("workspace")
    backend = select_backend(qt, fontlab, lambda e, source: calls.append(e), items=list)
    assert isinstance(backend, NativeCanvasBackend)
    assert backend._timer is None and backend._watch is None and backend._repaint is None
    assert not backend._reporters and not backend.canvases and calls == []
    backend.close()
    assert calls == []
