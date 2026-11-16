# this_file: tests/plugmix/test_plugmix_reporter.py
"""Render font-unit marks with stable view-pixel styles and safe errors."""

from types import SimpleNamespace as NS

import pytest

from fontlabapp.plugins import snapshot
from fontlabapp.plugins.reporter import Mark, Reporter, render_marks


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Rect:
    def __init__(self, x, y, w, h):
        self.xywh = (x, y, w, h)


class Pen:
    def __init__(self, color=None):
        self.color = color
        self.width = 0

    def setWidthF(self, value):
        self.width = value


class Font:
    def setPixelSize(self, value):
        self.pixels = value


class Painter:
    def __init__(self):
        self.calls = []
        self.pen = "original pen"
        self.brush = "original brush"
        self.saved = []

    def save(self):
        self.saved.append((self.pen, self.brush))
        self.calls.append(("save",))

    def restore(self):
        self.pen, self.brush = self.saved.pop()
        self.calls.append(("restore",))

    def setPen(self, value):
        self.pen = value
        self.calls.append(("pen", getattr(value, "width", value)))

    def setBrush(self, value):
        self.brush = value
        self.calls.append(("brush", value))

    def setFont(self, value):
        self.calls.append(("font", value.pixels))

    def drawLine(self, a, b):
        self.calls.append(("line", (a.x(), a.y()), (b.x(), b.y())))

    def drawEllipse(self, rect):
        self.calls.append(("ellipse", rect.xywh))

    def drawText(self, point, value):
        self.calls.append(("text", (point.x(), point.y()), value))

    def drawPolygon(self, points):
        self.calls.append(
            ("polygon", tuple((point.x(), point.y()) for point in points))
        )


def scene():
    """Two sequential transforms: glyph*2, then view+3."""
    qt = NS(
        QtCore=NS(QPointF=Point, QRectF=Rect, Qt=NS(NoPen="no-pen")),
        QtGui=NS(
            QPen=Pen,
            QColor=lambda *rgba: rgba,
            QBrush=object,
            QFont=Font,
            QPolygonF=tuple,
        ),
    )
    context = NS(
        painter=Painter(),
        layer=object(),
        glyph_to_canvas=NS(map=lambda p: Point(p.x() * 2, p.y() * 2)),
        canvas_to_view=NS(map=lambda p: Point(p.x() + 3, p.y() + 3)),
    )
    return qt, context


def test_render_marks_maps_geometry_but_keeps_pixel_styles():
    qt, context = scene()
    marks = [
        Mark("line", ((1, 2), (3, 4)), stroke_px=4),
        Mark("polyline", ((0, 0), (1, 1), (2, 1))),
        Mark("ring", ((1, 2),), diameter_px=16),
        Mark("text", ((1, 2),), text="x", text_px=14),
    ]
    render_marks(marks, context, qt)
    calls = context.painter.calls
    assert ("line", (5, 7), (9, 11)) in calls
    assert ("ellipse", (-3, -1, 16, 16)) in calls
    assert ("font", 14) in calls
    assert ("pen", 4) in calls
    assert sum(call[0] == "line" for call in calls) == 3


def test_render_marks_fills_translucent_polygon_in_view_coordinates():
    qt, context = scene()
    before = (context.painter.pen, context.painter.brush)
    render_marks(
        [Mark("polygon", ((0, 0), (10, 0), (10, 20), (0, 20)), fill=(40, 40, 40, 70))],
        context,
        qt,
    )
    assert ("pen", "no-pen") in context.painter.calls
    assert ("brush", (40, 40, 40, 70)) in context.painter.calls
    assert ("polygon", ((3, 3), (23, 3), (23, 43), (3, 43))) in context.painter.calls
    assert (context.painter.pen, context.painter.brush) == before
    assert context.painter.calls[-1] == ("restore",)


def test_render_marks_ignores_short_polygons_and_resets_state_after_draw_error():
    qt, context = scene()
    before = (context.painter.pen, context.painter.brush)
    render_marks([Mark("polygon", ((0, 0), (1, 1)), fill=(1, 2, 3, 4))], context, qt)
    assert context.painter.calls == []
    context.painter.drawPolygon = lambda points: (_ for _ in ()).throw(
        ValueError("paint")
    )
    with pytest.raises(ValueError, match="paint"):
        render_marks(
            [Mark("polygon", ((0, 0), (1, 0), (1, 1)), fill=(1, 2, 3, 4))], context, qt
        )
    assert (context.painter.pen, context.painter.brush) == before
    assert context.painter.calls[-1] == ("restore",)


class Example(Reporter):
    name, title = "example", "Example"

    def compute(self, snapshot):
        return [Mark("text", ((2, 2),), text=str(snapshot))]


def test_reporter_paint_catches_compute_render_and_sink_failures():
    qt, context = scene()
    errors = []
    plugin = Example()
    plugin.paint(context, qt, lambda e, p: errors.append(e), capture=lambda layer: "ok")
    assert ("text", (7, 7), "ok") in context.painter.calls
    context.layer = None
    plugin.paint(context, qt, lambda e, p: errors.append(e), capture=lambda layer: 1)
    assert errors == []
    context.layer = object()
    plugin.paint(
        context, qt, lambda e, p: errors.append(e), capture=lambda layer: 1 / 0
    )
    assert isinstance(errors[0], ZeroDivisionError)
    bad = Example()
    bad.compute = lambda snapshot: [Mark("unknown", ((0, 0),))]
    bad.paint(context, qt, lambda e, p: 1 / 0, capture=lambda layer: "ok")


def test_reporter_bind_passes_itself_to_selected_backend():
    observed = []
    painters = NS(register=lambda *args, **kwargs: observed.append((args, kwargs)) or 7)
    reporter = Example()
    assert reporter.bind(painters, object(), lambda e, p: None) == 7
    assert observed[0][0][0] is reporter


def test_reporter_requests_zones_only_when_declared(monkeypatch):
    qt, context = scene()
    calls = []
    monkeypatch.setattr(
        snapshot,
        "capture",
        lambda source, report, requested, **flags: calls.append(flags) or "data",
    )
    Example().paint(context, qt, lambda error, source: None)
    plugin = Example()
    plugin.needs_zones, plugin.needs_bounds = True, True
    plugin.paint(context, qt, lambda error, source: None)
    plugin.needs_zones = plugin.needs_bounds = False
    plugin.needs_components = plugin.needs_background = plugin.needs_masters = True
    plugin.needs_kerning = True
    plugin.paint(context, qt, lambda error, source: None)
    names = ("zones", "bounds", "components", "background", "masters", "kerning")
    assert calls == [
        {f"include_{name}": False for name in names},
        {f"include_{name}": name in {"zones", "bounds"} for name in names},
        {f"include_{name}": name not in {"zones", "bounds"} for name in names},
    ]
    assert not (Reporter.needs_components or Reporter.needs_background)
    assert Reporter.needs_masters is False
    assert not (Reporter.needs_kerning or Reporter.needs_neighbours)
    assert Reporter.needs_mouse is False
    assert Reporter().requested_glyphs(None) == ()


class Recorder(Reporter):
    name, title = "recorder", "Recorder"

    def __init__(self):
        self.seen = []

    def compute(self, snapshot):
        self.seen.append(snapshot)
        return []


def plain():
    return snapshot.GlyphSnapshot((), (), 500, snapshot.Metrics(0, 0, 0, 0, 0, 1000))


def test_reporter_paint_when_context_has_scale_then_view_carries_px_per_unit():
    qt, context = scene()
    context.scale = 4
    plugin = Recorder()
    plugin.paint(context, qt, lambda e, p: None, capture=lambda layer: plain())
    assert plugin.seen[0].view == snapshot.ViewState(4.0)
    assert plugin.seen[0].advance == 500, "view is attached after capture"
    context.scale = None
    plugin.paint(context, qt, lambda e, p: None, capture=lambda layer: plain())
    assert plugin.seen[1].view is None, "unknown scale degrades to no view"
    for bad in (float("inf"), float("nan")):
        context.scale = bad
        plugin.paint(context, qt, lambda e, p: None, capture=lambda layer: plain())
        assert plugin.seen[-1].view is None, f"non-finite scale {bad} gives no view"


def test_reporter_paint_when_capture_reports_then_sink_gets_it_and_compute_runs(
    monkeypatch,
):
    qt, context = scene()
    failure = AttributeError("tags")

    def degraded(source, report, **flags):
        report(failure)
        return plain()

    monkeypatch.setattr(snapshot, "capture", degraded)
    plugin, errors = Recorder(), []
    plugin.paint(context, qt, lambda error, source: errors.append((error, source)))
    assert errors == [(failure, plugin)]
    assert len(plugin.seen) == 1, "optional data failure never blocks compute"
    plugin.paint(context, qt, lambda error, source: 1 / 0)
    assert len(plugin.seen) == 2, "a failing sink must not unwind the paint"


class Asking(Recorder):
    name, title = "asking", "Asking"

    def __init__(self, names):
        super().__init__()
        self.names = names

    def requested_glyphs(self, identity, kerning_groups=None):
        if isinstance(self.names, Exception):
            raise self.names
        return self.names


def asked_names(monkeypatch, plugin, paints=2):
    """Paint with a fake capture that asks the reporter for its glyph names."""
    qt, context = scene()
    passed, errors = [], []

    def fake(source, report, requested, **flags):
        passed.append(requested("identity"))
        return plain()

    monkeypatch.setattr(snapshot, "capture", fake)
    for _ in range(paints):
        plugin.paint(context, qt, lambda error, source: errors.append(error))
    return passed, errors


def test_requested_glyphs_when_over_cap_then_first_32_unique_and_reported_once(
    monkeypatch,
):
    names = tuple(f"g{i}" for i in range(40))
    plugin = Asking(("g0", *names))
    passed, errors = asked_names(monkeypatch, plugin)
    assert passed[0] == names[:32] == passed[1], "deduplicated, then capped"
    assert len(errors) == 1 and "32" in str(errors[0])
    assert len(plugin.seen) == 2
    other = Asking(names)
    _, errors = asked_names(monkeypatch, other, paints=1)
    assert len(errors) == 1, "the cap is reported once per reporter instance"


@pytest.mark.parametrize("bad", [RuntimeError("boom"), ("A", 3), "AB"])
def test_requested_glyphs_when_raising_or_malformed_then_reported_and_compute_runs(
    monkeypatch, bad
):
    plugin = Asking(bad)
    passed, errors = asked_names(monkeypatch, plugin, paints=1)
    assert passed == [()], "a bad request asks for nothing"
    assert len(errors) == 1 and len(plugin.seen) == 1


class Failing(Recorder):
    name, title = "failing", "Failing"
    message = "boom"

    def compute(self, snapshot):
        raise RuntimeError(self.message)


@pytest.mark.parametrize("backend_kind", ["editor", "native"])
def test_reporter_errors_when_repeated_each_paint_then_reported_once_until_close(
    backend_kind,
):
    from fontlabapp.plugins.backend import EditorBackend, NativeCanvasBackend

    qt, context = scene()
    plugin, errors = Failing(), []

    def paint():
        sink = lambda error, source: errors.append(error)
        plugin.paint(context, qt, sink, capture=lambda layer: plain())

    for _ in range(3):
        paint()
    assert [str(e) for e in errors] == ["boom"]
    first = errors[0]
    plugin.message = "bang"
    paint()
    # Issue 211 succeeds the old message-based policy: text does not reopen it.
    assert errors == [first], "one report per stable source and exception class"
    if backend_kind == "editor":
        backend = EditorBackend(NS(close=lambda: None), lambda e, s: None)
    else:
        backend = NativeCanvasBackend(NS(), NS(), lambda e, s: None, items=lambda f: [])
    backend.close()
    paint()
    assert [str(e) for e in errors] == ["boom", "bang"], "close() resets"
    assert errors[0] is first, "the original first exception is delivered unchanged"
    backend.close()


@pytest.mark.parametrize("backend_kind", ["editor", "native"])
def test_reporter_when_backend_closes_then_same_error_reports_again(backend_kind):
    from fontlabapp.plugins.backend import EditorBackend, NativeCanvasBackend

    qt, context = scene()
    plugin, errors = Failing(), []
    if backend_kind == "editor":
        backend = EditorBackend(NS(close=lambda: None), lambda e, s: None)
    else:
        backend = NativeCanvasBackend(NS(), NS(), lambda e, s: None, items=lambda f: [])
    for _ in range(2):
        plugin.paint(context, qt, lambda e, p: errors.append(e), capture=lambda l: plain())
    assert len(errors) == 1
    backend.close()
    plugin.paint(context, qt, lambda e, p: errors.append(e), capture=lambda l: plain())
    assert [str(e) for e in errors] == ["boom", "boom"]
    backend.close()


def test_requested_glyphs_when_error_text_changes_then_first_error_only(monkeypatch):
    class Changing(Recorder):
        name = "changing-request"

        def __init__(self):
            super().__init__()
            self.failures = []

        def requested_glyphs(self, identity, kerning_groups=None):
            error = RuntimeError(f"request {len(self.failures) + 1}")
            self.failures.append(error)
            raise error

    plugin = Changing()
    passed, errors = asked_names(monkeypatch, plugin, paints=3)
    assert passed == [(), (), ()]
    assert len(plugin.seen) == 3, "compute still runs on every failed request"
    assert errors == [plugin.failures[0]], "changing text must not reopen the key"


@pytest.mark.parametrize("source_name", ["source-a", ""])
def test_reporter_when_source_names_differ_then_independent_retained_keys(source_name):
    qt, context = scene()
    first, other, replacement = Failing(), Failing(), Failing()
    first.name = replacement.name = source_name
    other.name = "source-b"
    errors = []
    for plugin in (first, first, other, other, replacement):
        plugin.paint(
            context, qt, lambda e, p: errors.append((e, p)), capture=lambda l: plain()
        )
    assert len(errors) == 2, "replacement instances share the stable name/fallback"
    assert errors[0][1] is first and errors[1][1] is other


def test_reporter_when_exception_classes_differ_then_first_of_each_class():
    qt, context = scene()
    plugin, errors = Recorder(), []
    failures = [RuntimeError("first"), RuntimeError("second"), ValueError("a"), ValueError("b")]
    pending = iter(failures)

    def fail(data):
        raise next(pending)

    plugin.compute = fail
    for _ in failures:
        plugin.paint(context, qt, lambda e, p: errors.append(e), capture=lambda l: plain())
    assert errors == [failures[0], failures[2]]


def test_reporter_when_exception_class_names_match_then_actual_classes_stay_distinct():
    qt, context = scene()
    first_type = type("SameName", (Exception,), {})
    second_type = type("SameName", (Exception,), {})
    first, second = first_type("same"), second_type("same")
    plugin, errors = Recorder(), []
    pending = iter((first, second, first, second))

    def fail(data):
        raise next(pending)

    plugin.compute = fail
    for _ in range(4):
        plugin.paint(context, qt, lambda e, p: errors.append(e), capture=lambda l: plain())
    assert errors == [first, second]
    assert type(errors[0]) is first_type and type(errors[1]) is second_type


def test_requested_glyphs_when_one_argument_override_then_one_type_error(
    monkeypatch,
):
    class Old(Recorder):
        name, title = "old", "Old"

        def requested_glyphs(self, identity):
            return ("B",)

    plugin = Old()
    passed, errors = asked_names(monkeypatch, plugin, paints=3)
    assert passed == [(), (), ()], "the bad override asks for nothing"
    assert len(errors) == 1 and isinstance(errors[0], TypeError), errors
    assert len(plugin.seen) == 3, "compute still runs every paint"


def test_reporter_paint_when_context_has_neighbours_then_view_carries_them():
    qt, context = scene()
    near = snapshot.Neighbours(("T", -40.0), None)
    context.scale, context.neighbours = 2, near
    plugin = Recorder()
    plugin.paint(context, qt, lambda e, p: None, capture=lambda layer: plain())
    assert plugin.seen[0].view == snapshot.ViewState(2.0, neighbours=near)
    context.scale = None
    plugin.paint(context, qt, lambda e, p: None, capture=lambda layer: plain())
    assert plugin.seen[1].view is None, "no usable scale, no view, no neighbours"


def test_reporter_paint_when_context_has_mouse_then_view_carries_it():
    qt, context = scene()
    context.scale, context.mouse = 2, (10.0, 4.0)
    plugin = Recorder()
    plugin.paint(context, qt, lambda e, p: None, capture=lambda layer: plain())
    assert plugin.seen[0].view == snapshot.ViewState(2.0, mouse=(10.0, 4.0))
    del context.mouse
    plugin.paint(context, qt, lambda e, p: None, capture=lambda layer: plain())
    assert plugin.seen[1].view.mouse is None, "EditorPainters contexts have no mouse"


class GroupAsking(Recorder):
    name, title = "group_asking", "Group asking"

    def requested_glyphs(self, identity, kerning_groups=None):
        self.groups = kerning_groups
        return ("x",)


def test_requested_glyphs_when_groups_given_then_override_receives_them(monkeypatch):
    plugin = GroupAsking()
    qt, context = scene()
    got = []

    def fake(source, report, requested, **flags):
        got.append(requested("identity", "GROUPS"))
        return plain()

    monkeypatch.setattr(snapshot, "capture", fake)
    plugin.paint(context, qt, lambda error, source: got.append(error))
    assert got == [("x",)] and plugin.groups == "GROUPS"
    assert plugin._requested("identity", print) == ("x",)
    assert plugin.groups is None, "None unless the capture read groups"


def test_requested_glyphs_when_base_class_then_accepts_groups_and_asks_nothing():
    plugin = Asking(("a", "b"))
    assert plugin._requested("identity", print, "GROUPS") == ("a", "b")
    assert Reporter().requested_glyphs(None, "GROUPS") == ()
