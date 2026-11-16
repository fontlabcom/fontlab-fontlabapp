# this_file: tests/test_editor_painters.py
"""EditorPainters over FontLab-shaped Qt doubles (native proof is a separate gate)."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import fontlabapp.contours.affine as affine  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.qt.painting.editor as ep
from fontlabapp.qt.painting.editor import EditorPainters, PaintContext


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)


class QPointF:
    def __init__(self, x, y):
        self._x, self._y = float(x), float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class QTransform:
    def __init__(self, *m):
        self.m = tuple(float(v) for v in m) if m else (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def m11(self):
        return self.m[0]

    def m12(self):
        return self.m[1]

    def m21(self):
        return self.m[2]

    def m22(self):
        return self.m[3]

    def dx(self):
        return self.m[4]

    def dy(self):
        return self.m[5]


class Painter:
    """Records save/restore/end order; one instance per QPainter(overlay) call."""

    def __init__(self, device=None):
        self.calls = []
        self.device = device

    def save(self):
        self.calls.append("save")

    def restore(self):
        self.calls.append("restore")

    def end(self):
        self.calls.append("end")


class Widget:
    def __init__(self, parent=None, name="QWidget", visible=True):
        self._name, self.parent, self.filters = name, parent, []
        self.attrs, self.visible, self.deleted, self.updates = {}, False, False, 0
        self._shown = visible
        self.destroyed = Signal()
        self.rect = (0, 0, 800, 600)

    def className(self):
        return self._name

    def isVisible(self):
        return self._shown

    def findChildren(self, cls):
        return [w for w in WIDGETS if w.parent is self]

    def installEventFilter(self, f):
        self.filters.append(f)

    def removeEventFilter(self, f):
        self.filters.remove(f)

    def setAttribute(self, a, on):
        self.attrs[a] = on

    def setGeometry(self, *args):
        self.geometry = args

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def raise_(self):
        pass

    def update(self):
        self.updates += 1

    def setParent(self, p):
        self.parent = p

    def deleteLater(self):
        self.deleted = True

    def devicePixelRatioF(self):
        return 2.0


WIDGETS: list = []


class Timer:
    def __init__(self):
        self.timeout, self.running, self.deleted = Signal(), False, False

    def setInterval(self, ms):
        self.ms = ms

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def deleteLater(self):
        self.deleted = True


class Info:
    def __init__(self, dx, active):
        self.transform = QTransform(0.1, 0, 0, -0.1, dx, 100)
        self.isActive, self.id = active, dx


class Canvas:
    def __init__(self, infos):
        self.block = SimpleNamespace(
            transform=QTransform(),
            getAllGlyphs=lambda: infos,
            package=SimpleNamespace(id=7),
        )

    def textBlocks(self):
        return [self.block]

    def mapToViewportF(self, p):
        return QPointF(p.x() * 4 + 10, p.y() * 4 + 20)


def _setup(infos, *, layer_resolver=None, visible=True):
    WIDGETS.clear()
    window = Widget(name="GlyphWindow", visible=visible)
    viewport = Widget(window)
    WIDGETS.extend([window, viewport])
    canvas = Canvas(infos)
    workspace = SimpleNamespace(
        getCanvasForViewport=lambda w: canvas if w is viewport else None
    )
    painter_log = []

    def make_painter(device):
        painter = Painter(device)
        painter_log.append(painter)
        return painter

    gui = SimpleNamespace(
        QWidget=Widget,
        QApplication=SimpleNamespace(allWidgets=lambda: list(WIDGETS)),
        QPainter=make_painter,
        QTransform=QTransform,
    )
    core = SimpleNamespace(
        QTimer=Timer,
        QPointF=QPointF,
        QEvent=SimpleNamespace(Resize=14),
        Qt=SimpleNamespace(WA_TransparentForMouseEvents=1, WA_NoSystemBackground=2),
    )
    fl = SimpleNamespace(flWorkspace=SimpleNamespace(instance=lambda: workspace))
    errors = []
    painters = EditorPainters(
        SimpleNamespace(QtGui=gui, QtCore=core),
        fl,
        error_sink=lambda e, s: errors.append((e, s)),
        layer_resolver=layer_resolver,
    )
    painters.painter_log = painter_log
    return painters, viewport, errors


def _overlay(painters):
    return next(iter(painters.overlays.values()))[0]


def test_register_when_before_native_layer_then_value_error_and_nothing_started():
    painters, _, _ = _setup([])
    with pytest.raises(ValueError, match="before_native_layer"):
        painters.register("before_native_layer", lambda c: None)
    assert painters.overlays == {} and painters._timer is None
    assert painters.painters == {}


@pytest.mark.parametrize(
    ("phase", "layer_filter"),
    [("sideways", "active"), ("after_native_layer", "bogus")],
)
def test_register_when_bad_phase_or_filter_then_value_error(phase, layer_filter):
    painters, _, _ = _setup([])
    with pytest.raises(ValueError):
        painters.register(phase, lambda c: None, layer_filter)
    assert painters._timer is None


def test_register_when_glyph_window_then_overlay_and_glyph_contexts():
    painters, viewport, errors = _setup([Info(0, True), Info(60, False)])
    seen = []
    painters.register("after_native_layer", seen.append, layer_filter="all")
    overlay = _overlay(painters)
    assert overlay.parent is viewport and overlay in viewport.filters
    assert overlay.attrs == {1: True, 2: True} and overlay.visible
    overlay.paintEvent(SimpleNamespace(rect=lambda: "clip"))
    assert [c.is_active_layer for c in seen] == [True, False]
    first, second = seen
    assert isinstance(first, PaintContext) and first.phase == "after_native_layer"
    full = affine.concat(
        affine.from_qtransform(first.glyph_to_canvas),
        affine.from_qtransform(first.canvas_to_view),
    )
    assert affine.apply(full, 0, 0) == (10.0, 420.0)
    assert first.scale == pytest.approx(0.4)
    assert affine.from_qtransform(second.glyph_to_canvas)[4] == 60.0
    assert (first.document_id, first.clip, first.device_pixel_ratio) == (7, "clip", 2.0)
    assert errors == []


def test_poll_when_started_then_timer_runs_and_second_poll_adds_no_overlay():
    painters, _, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    timer = painters._timer
    assert timer.running and timer.ms == ep.POLL_MS
    assert timer.timeout.slots == [painters._attach_all]
    timer.timeout.slots[0]()
    timer.timeout.slots[0]()
    assert len(painters.overlays) == 1, "one overlay per viewport"
    painters.register("after_native_layer", lambda c: None)
    assert painters._timer is timer and len(painters.overlays) == 1


def test_poll_when_window_hidden_then_no_overlay_until_shown():
    painters, _, _ = _setup([Info(0, True)], visible=False)
    painters.register("after_native_layer", lambda c: None)
    assert painters.overlays == {}
    WIDGETS[0]._shown = True
    painters._timer.timeout.slots[0]()
    assert len(painters.overlays) == 1


def test_poll_when_native_lookup_fails_then_error_goes_to_sink_not_timer():
    painters, _, errors = _setup([Info(0, True)])
    painters.fl.flWorkspace = SimpleNamespace(
        instance=lambda: (_ for _ in ()).throw(KeyError("workspace"))
    )
    painters.register("after_native_layer", lambda c: None)
    assert [type(e) for e, _ in errors] == [KeyError]


def test_poll_when_lookup_and_sink_both_fail_then_nothing_escapes_the_timer():
    painters, _, errors = _setup([Info(0, True)])
    painters.fl.flWorkspace = SimpleNamespace(
        instance=lambda: (_ for _ in ()).throw(KeyError("workspace"))
    )
    painters.register("after_native_layer", lambda c: None)
    painters.sink = lambda e, s: (_ for _ in ()).throw(RuntimeError("sink broke"))
    painters._attach_all()  # timer slot: must not raise into Qt
    assert [type(e) for e, _ in errors] == [KeyError]


def test_paint_when_callback_raises_then_sink_gets_it_and_painter_restored():
    painters, _, errors = _setup([Info(0, True), Info(60, True)])
    calls = []

    def bad(context):
        calls.append(context.glyph_item_id)
        raise ValueError("plugin broke")

    painters.register("after_native_layer", bad)
    _overlay(painters).paintEvent(None)
    assert calls == [0, 60], "one failure does not stop later glyphs"
    assert [str(e) for e, _ in errors] == ["plugin broke"] * 2
    assert all(source is bad for _, source in errors)
    log = painters.painter_log[-1].calls
    assert log == ["save", "restore", "save", "restore", "end"]


def test_paint_when_two_painters_then_each_gets_own_save_restore():
    painters, _, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    painters.register("after_native_layer", lambda c: None)
    _overlay(painters).paintEvent(None)
    assert painters.painter_log[-1].calls == [
        "save", "restore", "save", "restore", "end",
    ]


def test_paint_when_context_build_fails_then_sink_and_painter_still_ended():
    painters, viewport, errors = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    overlay = _overlay(painters)
    painters.overlays[id(viewport)][2].textBlocks = lambda: 1 / 0
    overlay.paintEvent(None)
    assert [type(e) for e, _ in errors] == [ZeroDivisionError]
    assert painters.painter_log[-1].calls == ["end"]


def test_paint_when_painter_cannot_be_created_then_sink_not_paint_event():
    painters, _, errors = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)

    def fail(device):
        raise RuntimeError("no painter")

    painters.qt.QtGui.QPainter = fail
    _overlay(painters).paintEvent(None)
    assert [str(e) for e, _ in errors] == ["no painter"]


def test_paint_when_filter_active_then_inactive_glyph_skipped():
    painters, _, _ = _setup([Info(0, True), Info(60, False)])
    active, inactive = [], []
    painters.register("after_native_layer", active.append)
    painters.register("after_native_layer", inactive.append, "inactive")
    _overlay(painters).paintEvent(None)
    assert [c.glyph_item_id for c in active] == [0]
    assert [c.glyph_item_id for c in inactive] == [60]


def test_document_id_when_given_then_only_that_document_painted():
    painters, _, _ = _setup([Info(0, True)])
    mine, other = [], []
    painters.register("after_native_layer", mine.append, document_id=7)
    painters.register("after_native_layer", other.append, document_id=8)
    _overlay(painters).paintEvent(None)
    assert len(mine) == 1 and other == []


def test_layer_resolver_when_given_then_layer_in_context():
    painters, _, _ = _setup([Info(5, True)], layer_resolver=lambda info: ("layer", info.id))
    seen = []
    painters.register("after_native_layer", seen.append)
    _overlay(painters).paintEvent(None)
    assert seen[0].layer == ("layer", 5)


def test_resize_when_viewport_resizes_then_overlay_follows_and_never_consumes():
    painters, viewport, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    overlay = _overlay(painters)
    viewport.rect = (0, 0, 10, 20)
    resize = SimpleNamespace(type=lambda: 14)
    other = SimpleNamespace(type=lambda: 1)
    assert overlay.eventFilter(viewport, resize) is False
    assert overlay.geometry == ((0, 0, 10, 20),)
    overlay.geometry = None
    assert overlay.eventFilter(viewport, other) is False
    assert overlay.geometry is None


def test_remove_when_last_painter_then_overlays_and_timer_torn_down():
    painters, viewport, _ = _setup([Info(0, True)])
    token = painters.register("after_native_layer", lambda c: None)
    overlay, timer = _overlay(painters), painters._timer
    painters.remove(token)
    painters.remove(token)
    assert painters.overlays == {} and painters._timer is None
    assert timer.timeout.slots == [] and not timer.running and timer.deleted
    assert overlay.deleted and overlay not in viewport.filters
    assert overlay._owner is None
    assert viewport.destroyed.slots == [], "disconnected before deleteLater"


def test_remove_when_other_painters_remain_then_polling_continues():
    painters, _, _ = _setup([Info(0, True)])
    first = painters.register("after_native_layer", lambda c: None)
    painters.register("after_native_layer", lambda c: None)
    timer, overlay = painters._timer, _overlay(painters)
    before = overlay.updates
    painters.remove(first)
    assert painters._timer is timer and timer.running and len(painters.overlays) == 1
    assert overlay.updates == before + 1, "the remaining painters repaint at once"


def test_detach_when_overlay_removed_then_destroyed_disconnected_before_delete():
    painters, viewport, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    overlay = _overlay(painters)
    slots_at_delete = []
    original = overlay.deleteLater
    overlay.deleteLater = lambda: (slots_at_delete.append(list(viewport.destroyed.slots)), original())
    painters.close()
    assert slots_at_delete == [[]], "signal disconnected before deleteLater"


def test_timer_teardown_when_stopped_then_disconnect_before_delete_later():
    painters, _, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    timer = painters._timer
    slots_at_delete = []
    timer.deleteLater = lambda: slots_at_delete.append(list(timer.timeout.slots))
    painters.close()
    assert slots_at_delete == [[]]


def test_viewport_destroyed_when_window_closes_then_overlay_forgotten():
    painters, viewport, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    viewport.destroyed.slots[0]()
    assert painters.overlays == {}


def test_close_when_painters_registered_then_registrations_dropped_and_reusable():
    painters, _, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    painters.close()
    assert painters.painters == {} and painters.overlays == {}
    seen = []
    painters.register("after_native_layer", seen.append)
    _overlay(painters).paintEvent(None)
    assert len(seen) == 1 and len(painters.painters) == 1


def test_close_when_one_detach_fails_then_others_detached_and_first_error_raised():
    painters, viewport, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    extra = Widget(name="GlyphWindow")
    extra_view = Widget(extra)
    painters._attach(object(), extra_view)
    viewport.removeEventFilter = lambda f: (_ for _ in ()).throw(OSError("boom"))
    with pytest.raises(OSError, match="boom"):
        painters.close()
    assert painters.overlays == {} and painters._timer is None


def test_qt_list_when_off_main_thread_then_runtime_error_reaches_sink():
    import threading

    painters, _, errors = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    errors.clear()
    thread = threading.Thread(target=painters._attach_all)
    thread.start()
    thread.join()
    assert [type(e) for e, _ in errors] == [RuntimeError]


def test_editor_painters_when_cold_imported_then_no_native_or_heavy_modules_load():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        # 'org' is the Jython probe in stdlib copy.py; it handles its own failure.
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.qt.painting.editor as m
assert m.AFTER_NATIVE_LAYER == 'after_native_layer'
banned = {'PythonQt', 'fontlab', 'fontgate', 'FL', 'fontpr', 'PySide2',
          'PySide6', 'fontport', 'fontlab_fontport', 'glyport',
          'fontlab_glyport', 'fontTools', 'fontParts'}
loaded = {n.split('.')[0] for n in sys.modules} & banned
assert not loaded, loaded
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_when_listed_then_every_name_exists():
    assert all(hasattr(ep, name) for name in ep.__all__)


# --- issue 122 T14: typed entries and fail-safe teardown/paint ---------------


def test_entries_when_registered_then_typed_named_fields():
    painters, viewport, _ = _setup([Info(0, True)])

    def callback(context):
        return None

    token = painters.register("after_native_layer", callback, "all", document_id=7)
    entry = painters.painters[token]
    assert isinstance(entry, ep.PainterEntry), type(entry)
    assert (entry.callback, entry.layer_filter, entry.document_id) == (callback, "all", 7)
    attached = painters.overlays[id(viewport)]
    assert isinstance(attached, ep.OverlayEntry), type(attached)
    assert attached.viewport is viewport and attached.overlay.parent is viewport
    assert attached.canvas is painters._viewports()[0][0]
    assert attached[0] is attached.overlay, "tuple indexing stays for older callers"
    assert attached.destroyed in viewport.destroyed.slots


def test_close_when_timer_disconnect_fails_then_overlays_still_detached_and_raised():
    painters, viewport, _ = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    timer, overlay = painters._timer, _overlay(painters)

    def refuse(slot):
        raise OSError("disconnect refused")

    timer.timeout.disconnect = refuse
    with pytest.raises(OSError, match="disconnect refused"):
        painters.close()
    assert painters.overlays == {} and overlay.deleted, "overlay detach is not skipped"
    assert viewport.destroyed.slots == [] and overlay not in viewport.filters
    assert not timer.running, "a timer with a live slot must not keep polling"
    assert not timer.deleted, "never delete a timer whose slot is still connected"
    assert timer in painters._kept_timers, "the wrapper stays alive with its live slot"
    assert painters._timer is None
    painters.register("after_native_layer", lambda c: None)
    assert painters._timer is not timer and painters._timer.running, "fresh poll timer"


def test_close_when_timer_stop_fails_then_kept_timer_tick_attaches_nothing():
    painters, viewport, errors = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    timer = painters._timer

    def refuse():
        raise OSError("stop refused")

    timer.stop = refuse
    with pytest.raises(OSError, match="stop refused"):
        painters.close()
    assert timer in painters._kept_timers and timer.running, "still polling, still connected"
    assert painters.overlays == {}
    timer.timeout.slots[0]()  # the native timer fires again after close
    assert painters.overlays == {}, "a closed registry attaches no overlay"
    assert viewport.destroyed.slots == [] and errors == []


def test_paint_when_painter_end_raises_then_both_errors_reach_sink_not_paint_event():
    painters, _, errors = _setup([Info(0, True)])
    painters.register("after_native_layer", lambda c: None)
    painters.overlays[next(iter(painters.overlays))][2].textBlocks = lambda: 1 / 0

    def ending_fails(device):
        painter = Painter(device)
        painter.end = lambda: (_ for _ in ()).throw(OSError("end failed"))
        return painter

    painters.qt.QtGui.QPainter = ending_fails
    _overlay(painters).paintEvent(None)  # must not raise
    assert [type(e) for e, _ in errors] == [ZeroDivisionError, OSError], errors
