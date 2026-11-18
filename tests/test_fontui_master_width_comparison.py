# this_file: tests/test_fontui_master_width_comparison.py
"""Real Sequence and owned registered-native boundary fixtures; no host claim."""
import importlib
import importlib.util
import sys

import pytest


@pytest.fixture
def actual_qt(monkeypatch):
    from _feature_source_qt import owned_application, qt_namespace
    from PySide6 import QtCore, QtWidgets
    import shiboken6

    qt = qt_namespace()
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setitem(sys.modules, "fontlab", None)
    names = ["fontlabapp.fontui." + n for n in
             ("master_width_comparison", "sequence", "lifecycle")]
    previous = {n: sys.modules.pop(n, None) for n in names}
    try:
        with owned_application() as app:
            parent = QtWidgets.QWidget()
            yield qt, parent, app
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            if shiboken6.isValid(parent):
                shiboken6.delete(parent)
    finally:
        for n, old in previous.items():
            sys.modules.pop(n, None)
            if old is not None:
                sys.modules[n] = old


def test_show_when_no_registered_font_then_visible_refusal_and_owned_cleanup(actual_qt):
    _, parent, app = actual_qt
    name = "fontlabapp.fontui.master_width_comparison"
    assert importlib.util.find_spec(name) is not None, "Master Width Comparison is absent"
    module = importlib.import_module(name)
    owner = module.show(None, parent=parent)
    try:
        assert owner.rows == ()
        assert "registered FontLab" in owner.diagnostic.text
        assert owner.sequence is None and owner.view is None
    finally:
        owner.release()
        app.processEvents()
        assert owner._released


@pytest.fixture
def native_model(actual_qt, monkeypatch):
    """Owned native API boundary; actual NativeFontBackend/RFont remain intact."""
    from types import SimpleNamespace as NS
    from PySide6 import QtCore, QtGui
    from fontlab_fontport.host import NativeFontBackend
    from fontlab_fontport.live import RFont

    class Events(QtCore.QObject):
        glyphsUpdated = QtCore.Signal(int)
        fontUpdated = QtCore.Signal()

    class Records(dict):
        id = 71
        def __iter__(self):
            return iter(self.values())
        def keys(self):
            return list(super().keys())

    package = NS(id=901, fgId=71, isNull=False, masters=["Bold", "Light", "Middle"],
                 axes=[NS(shortName="wt")], defaultMaster="Light", path="",
                 info=NS(unitsPerEm=1000, ascender=800, descender=-200),
                 lib={"keep": [1, 2]}, name="Same label")
    package.location = lambda name: {"wt": {"Bold": 900, "Light": 100, "Middle": 500}[name]}
    glyphs = {}
    records = Records()
    for number, name in enumerate(("A", "B")):
        glyph = NS(id=100 + number, name=name, package=package, isNull=False,
                   fgGlyphId=200 + number, lib={"keep": [number]}, note="owner note", layers=[])
        records[name] = NS(id=glyph.fgGlyphId, name=name, unicodes=[65 + number])
        for offset, (master, width) in enumerate((("Bold", 750.75), ("Light", 500.25))):
            layer = NS(id=1000 + 10 * number + offset, name=master, glyph=glyph,
                       isNull=False, isValid=True, isMasterLayer=True,
                       isMaskLayer=False, isService=False, advanceWidth=width + number,
                       advanceHeight=1000.5, transform=QtGui.QTransform(), shapes=[],
                       anchors=[], note="", lib={"keep": master})
            glyph.layers.append(layer)
        glyph.findLayer = lambda name, glyph=glyph: next((x for x in glyph.layers if x.name == name), None)
        glyph.activeLayer = glyph.findLayer("Light")
        glyphs[name] = glyph
    records.groups = {}
    package.kerning = lambda *args: NS(groups={}, items=lambda: [])
    package.fgPackage = records
    package.findName = glyphs.get
    registry = {71: package}
    events = Events()
    calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("No native mutation or font close is allowed")
    monkeypatch.setitem(sys.modules, "fontlab", NS(
        flWorkspace=NS(instance=lambda: NS(findPackageId=registry.get)),
        flItems=NS(instance=lambda: NS(qobject=events)),
        CurrentFont=forbidden, Update=forbidden))
    monkeypatch.setitem(sys.modules, "fontgate", NS())
    monkeypatch.setitem(sys.modules, "fontpr", NS(call=forbidden, close_font=forbidden))
    font = RFont(NativeFontBackend(71, owns_document=True))
    before = tuple((g.name, g.id, tuple((x.name, x.id, x.advanceWidth, x.advanceHeight,
                    x.lib.copy()) for x in g.layers), g.lib.copy(), g.note)
                   for g in glyphs.values())
    yield font, package, registry, events
    assert not calls
    assert not font._closed and not font._backend._closed
    # Tests may alter only explicit identity/read controls; the fixture never saves.
    assert tuple((g.name, tuple(x.advanceHeight for x in g.layers), g.lib, g.note)
                 for g in glyphs.values()) == tuple(
                     (name, tuple(x[3] for x in layers), lib, note)
                     for name, _, layers, lib, note in before)


@pytest.fixture
def comparison(actual_qt, native_model):
    _, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    font, package, registry, events = native_model
    owner = module.show(font, parent=parent)
    try:
        yield owner, app, package, registry, events
    finally:
        owner.release()
        app.processEvents()
        if not owner._released:
            owner._release_now()
        assert owner._released, owner.problems


def choose(owner, text="/A /B /A", index=2):
    owner.sequence.mode_control.setCurrentIndex(1)
    owner.sequence.text_control.setText(text)
    assert owner.sequence.run is not None, owner.sequence.diagnostic.text
    owner.sequence._select_occurrence(owner.sequence.run.glyphs[index])


def test_selection_when_repeated_glyph_then_literal_fractional_master_order(comparison):
    owner, _, _, _, _ = comparison
    from fontlabapp.fontui.sequence import Sequence
    assert type(owner.sequence) is Sequence
    assert owner.view is not owner.font and owner.view._backend is not owner.font._backend
    assert not owner.view._backend.owns_document
    choose(owner)
    assert owner.rows == (("Light", 500.25), ("Middle", None), ("Bold", 750.75))
    assert owner.occurrence == (2, "A", "/A")
    assert owner.table.item(0, 1).text() == "500.25"
    assert owner.table.item(1, 1).text() == "Missing layer"
    assert "occurrence 3" in owner.diagnostic.text


def test_notifications_when_owner_has_held_edits_then_only_private_cache_refreshes(comparison):
    owner, app, _, _, events = comparison
    original = owner.font
    glyph = original["A"]
    pen = glyph.getPointPen()
    pen.beginPath()
    pen.addPoint((1.25, 2.5), segmentType="move")
    cache = dict(original._layers)
    choose(owner)
    events.glyphsUpdated.emit(71)
    from PySide6.QtTest import QTest
    QTest.qWait(100)
    app.processEvents()
    assert original._layers == cache and original["A"] is glyph
    assert owner.rows == (("Light", 500.25), ("Middle", None), ("Bold", 750.75))
    assert owner.view is not original
    # The unfinished pen remains owned by the caller; do not end it or flush it.


@pytest.mark.parametrize("change", ["package", "glyph", "layer", "role", "duplicate", "closed"])
def test_update_when_native_identity_changes_then_clears_and_fences(comparison, change):
    from copy import copy
    owner, app, package, registry, _ = comparison
    choose(owner)
    glyph = package.findName("A")
    if change == "package":
        registry[71] = copy(package)
        registry[71].id += 1
    elif change == "glyph":
        glyph.id += 1
    elif change == "layer":
        glyph.layers[0].id += 1
    elif change == "role":
        glyph.layers[0].isMaskLayer = True
    elif change == "duplicate":
        glyph.layers[0].id = glyph.layers[1].id
    else:
        registry.clear()
    owner.update(owner.sequence)
    assert owner.rows == () and owner._closing
    app.processEvents()
    assert owner._released and owner.font is None and owner.view is None


def test_close_when_source_closed_then_deferred_children_and_private_refs_released(comparison):
    import gc
    import weakref
    import shiboken6
    from PySide6 import QtCore
    owner, app, _, registry, _ = comparison
    choose(owner)
    def dispose():
        sequence = owner.sequence
        widget = sequence.widget
        timers = widget.findChildren(QtCore.QTimer)
        assert timers
        references = weakref.ref(owner.view), weakref.ref(sequence)
        registry.clear()
        owner.update(sequence)
        assert owner.rows == () and owner._closing
        app.processEvents()
        assert sequence._close_complete and not sequence.connections
        assert owner._released and owner.sequence is None and owner.view is None
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        assert not shiboken6.isValid(widget)
        assert all(not shiboken6.isValid(t) for t in timers)
        return references
    view_ref, seq_ref = dispose()
    gc.collect()
    assert seq_ref() is None and view_ref() is None


@pytest.mark.parametrize("axis_mode, expected", [
    ("none", (("Bold", 750.75), ("Light", 500.25), ("Middle", None))),
    ("missing", (("Bold", 750.75), ("Light", 500.25), ("Middle", None))),
])
def test_master_order_when_axis_unavailable_then_existing_stable_fallback(comparison, axis_mode, expected):
    owner, _, package, _, _ = comparison
    if axis_mode == "none":
        package.axes = []
    else:
        package.location = lambda name: {}
    choose(owner)
    assert owner.rows == expected


@pytest.mark.parametrize("change", ["empty", "duplicate", "nan", "infinity", "glyph_missing", "foreign_layer"])
def test_read_when_invalid_master_or_geometry_identity_then_no_stale_rows(comparison, change):
    owner, app, package, _, _ = comparison
    choose(owner)
    glyph = package.findName("A")
    if change == "empty":
        package.masters = []
    elif change == "duplicate":
        package.masters.append("Light")
    elif change in ("nan", "infinity"):
        glyph.layers[0].advanceWidth = float("nan" if change == "nan" else "inf")
    elif change == "glyph_missing":
        package.findName = lambda name: None
    else:
        glyph.layers[0].glyph = package.findName("B")
    owner.update(owner.sequence)
    assert owner.rows == () and owner.table.rowCount() == 0 and owner._closing
    assert owner.diagnostic.text
    app.processEvents()
    assert owner._released


def test_show_when_ordinary_ufo_then_refusal_preserves_whole_font(actual_qt):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend
    from ufoLib2 import Font
    _, parent, app = actual_qt
    ufo = Font()
    ufo.newGlyph("A").width = 501.125
    ufo.lib["keep"] = {"x": [1, 2]}
    from copy import deepcopy
    before = deepcopy(ufo)
    font = RFont(UFOBackend(ufo))
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    owner = module.show(font, parent)
    assert owner.sequence is None and owner.view is None and owner.rows == ()
    assert "ordinary UFO" in owner.diagnostic.text
    owner.release()
    app.processEvents()
    assert owner._released and not font._closed and ufo == before


@pytest.mark.parametrize("action", ["close", "nested", "changed_width"])
def test_read_when_reentered_at_actual_reader_return_then_no_publication(comparison, action):
    from fontlabapp.masters.inspect import model
    owner, app, package, _, _ = comparison
    choose(owner)
    sequence = owner.sequence
    observed = []
    previous = sys.getprofile()
    def profile(frame, event, arg):
        if event == "return" and frame.f_code is model.widths.__code__ and not observed:
            observed.append((owner._reading, owner.rows))
            if action == "close":
                owner.release()
                app.processEvents()
                assert not sequence._close_complete and owner.view is not None
            elif action == "nested":
                owner.update(sequence)
            else:
                package.findName("A").layers[0].advanceWidth += .125
    sys.setprofile(profile)
    try:
        owner.update(sequence)
    finally:
        sys.setprofile(previous)
    assert observed == [(True, ())]
    assert owner.rows == () and owner._closing
    app.processEvents()
    assert owner._released and sequence._close_complete


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_release_when_queue_raises_then_primary_identity_and_explicit_retry(comparison, monkeypatch, error_type):
    owner, app, _, _, _ = comparison
    choose(owner)
    error = error_type("owned queue fault")
    def refuse(*args):
        raise error
    with monkeypatch.context() as patch:
        patch.setattr(owner.qt.QtCore.QTimer, "singleShot", refuse)
        with pytest.raises(error_type) as raised:
            owner.release()
        assert raised.value is error and not owner._queued
        assert owner._closing and owner.rows == () and owner.view is not None
    owner.release()
    app.processEvents()
    assert owner._released and owner.release() is True


@pytest.mark.parametrize("peer", ["sequence", "outer"])
@pytest.mark.parametrize("failure", ["false", "exception", "base"])
def test_close_when_owned_peer_refuses_then_keep_owner_and_retry_only_unacked(comparison, monkeypatch, peer, failure):
    owner, app, _, _, _ = comparison
    choose(owner)
    sequence, view = owner.sequence, owner.view
    widget = sequence.widget if peer == "sequence" else owner.owned.widget
    operation = "hide" if peer == "sequence" else "close"
    error = RuntimeError("owned cleanup fault") if failure == "exception" else KeyboardInterrupt("owned cleanup fault")
    def refuse(*args):
        if failure == "false":
            return False
        raise error
    with monkeypatch.context() as patch:
        patch.setattr(widget, operation, refuse)
        owner.release()
        app.processEvents()
        assert not owner._released and owner.view is view
        assert owner in importlib.import_module("fontlabapp.fontui.master_width_comparison")._HANDLES
        assert sequence._close_complete is (peer == "outer")
        if failure != "false":
            assert any(item is error for item in owner.problems)
    owner.release()
    app.processEvents()
    assert owner._released and sequence._close_complete
    assert owner.view is None and owner.sequence is None


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_show_when_actual_outer_show_fails_then_primary_error_and_cleanup(actual_qt, native_model, monkeypatch, error_type):
    qt, parent, app = actual_qt
    font, _, _, _ = native_model
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    before = list(module._HANDLES)
    error = error_type("outer show fault")
    reached = []
    def refuse(widget):
        reached.append(widget)
        raise error
    with monkeypatch.context() as patch:
        patch.setattr(qt.QtGui.QDialog, "show", refuse)
        with pytest.raises(error_type) as raised:
            module.show(font, parent)
        assert raised.value is error
    app.processEvents()
    assert reached and module._HANDLES == before
    assert not font._closed and not font._backend._closed


def test_parent_when_actually_destroyed_then_child_ack_and_reference_release(actual_qt, native_model):
    import gc
    import weakref
    import shiboken6
    from PySide6 import QtCore
    _, parent, app = actual_qt
    font, _, _, _ = native_model
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    owner = module.show(font, parent)
    view_ref, sequence_ref = weakref.ref(owner.view), weakref.ref(owner.sequence)
    widget = owner.sequence.widget
    shiboken6.delete(parent)
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    gc.collect()
    assert owner._released and not shiboken6.isValid(widget), (owner.problems, owner.scope.records, owner._closing, owner._queued, owner.sequence._close_complete if owner.sequence else None)
    assert view_ref() is None and sequence_ref() is None
    assert not font._closed and not font._backend._closed


def test_two_windows_when_one_closes_then_other_remains_live_and_backend_unchanged(actual_qt, native_model):
    from copy import deepcopy
    _, parent, app = actual_qt
    font, package, _, events = native_model
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    def stored():
        return (package.id, package.fgId, tuple(package.masters), package.defaultMaster,
                deepcopy(package.lib), tuple((g.id, g.name, deepcopy(g.lib), g.note,
                tuple((layer.id, layer.name, layer.advanceWidth, layer.advanceHeight, deepcopy(layer.lib),
                layer.note, tuple(layer.shapes), tuple(layer.anchors), layer.transform.m11(), layer.transform.m22())
                for layer in g.layers)) for g in (package.findName("A"), package.findName("B"))))
    before = stored()
    first, second = module.show(font, parent), module.show(font, parent)
    try:
        choose(first)
        choose(second, "/B", 0)
        assert first.view is not second.view and first.font is second.font is font
        first.release()
        app.processEvents()
        assert first._released and not second._closing
        events.glyphsUpdated.emit(71)
        from PySide6.QtTest import QTest
        QTest.qWait(100)
        assert second.rows == (("Light", 501.25), ("Middle", None), ("Bold", 751.75))
        assert stored() == before
    finally:
        first.release()
        second.release()
        app.processEvents()
        assert first._released and second._released
    assert stored() == before and not font._closed and not font._backend._closed


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_constructor_when_real_sequence_canvas_return_raises_then_owned_cleanup(actual_qt, native_model, error_type):
    import gc
    import weakref
    import shiboken6
    from PySide6 import QtCore
    from fontlabapp.fontui.sequence import Sequence
    _, parent, app = actual_qt
    font, _, _, _ = native_model
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    error = error_type("canvas construction boundary")
    observed = []
    previous = sys.getprofile()
    def profile(frame, event, arg):
        if event == "return" and frame.f_code is Sequence._canvas.__code__ and not observed:
            peer = frame.f_locals["self"]
            observed.append((weakref.ref(peer), peer.widget))
            raise error
    sys.setprofile(profile)
    try:
        with pytest.raises(error_type) as raised:
            module.show(font, parent)
        assert raised.value is error
    finally:
        sys.setprofile(previous)
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert observed and not shiboken6.isValid(observed[0][1])
    assert not module._HANDLES and not font._closed
    # The primary traceback intentionally retains its constructor frame until
    # the caller drops the exception; native/Qt teardown must already be done.
    assert observed[0][0]()._close_complete
    del raised
    error = None
    gc.collect()


def test_same_label_fonts_when_other_window_changes_then_identity_stays_captured(actual_qt, native_model):
    from copy import copy, deepcopy
    from fontlab_fontport.live import RFont
    from fontlab_fontport.host import NativeFontBackend
    _, parent, app = actual_qt
    font, package, registry, _ = native_model
    other = copy(package)
    other.id, other.fgId = 902, 72
    other.fgPackage = copy(package.fgPackage)
    other.fgPackage.id = 72
    others = {}
    for name in ("A", "B"):
        glyph = copy(package.findName(name))
        glyph.id += 100
        glyph.package = other
        glyph.layers = [copy(layer) for layer in glyph.layers]
        for layer in glyph.layers:
            layer.id += 1000
            layer.glyph = glyph
            layer.advanceWidth += 100
        glyph.findLayer = lambda master, glyph=glyph: next((layer for layer in glyph.layers if layer.name == master), None)
        glyph.activeLayer = glyph.findLayer("Light")
        others[name] = glyph
    other.findName = others.get
    registry[72] = other
    other_font = RFont(NativeFontBackend(72, owns_document=True))
    module = importlib.import_module("fontlabapp.fontui.master_width_comparison")
    first, second = module.show(font, parent), module.show(other_font, parent)
    try:
        choose(first)
        choose(second)
        assert package.name == other.name
        assert first.rows == (("Light", 500.25), ("Middle", None), ("Bold", 750.75))
        assert second.rows == (("Light", 600.25), ("Middle", None), ("Bold", 850.75))
        before = deepcopy(other.lib)
        first.release()
        app.processEvents()
        second.update(second.sequence)
        assert second.font is other_font and second.font_id == 72
        assert second.rows[0] == ("Light", 600.25) and other.lib == before
    finally:
        first.release()
        second.release()
        app.processEvents()
        assert first._released and second._released
    assert not other_font._closed and not other_font._backend._closed


def test_read_when_actual_reader_exceeds_budget_then_clear_before_publication(comparison):
    import time
    from fontlabapp.masters.inspect import model
    owner, app, _, _, _ = comparison
    choose(owner)
    observed = []
    previous = sys.getprofile()
    def profile(frame, event, arg):
        if event == "return" and frame.f_code is model.widths.__code__ and not observed:
            observed.append(owner.rows)
            time.sleep(.3)
    sys.setprofile(profile)
    try:
        owner.update(owner.sequence)
    finally:
        sys.setprofile(previous)
    assert observed == [()] and owner.rows == () and owner._closing
    app.processEvents()
    assert owner._released


def test_selection_when_occurrence_has_no_glyph_then_notice_keeps_tool_open(comparison):
    owner, app, _, _, _ = comparison
    choose(owner)
    owner.sequence.text_control.setText("/A /nosuchglyph")
    run = owner.sequence.run
    assert run is not None, owner.sequence.diagnostic.text
    missing = [o for o in run.glyphs if o.name is None]
    assert missing, "the sequence must place a missing-glyph occurrence"
    owner.sequence._select_occurrence(missing[0])
    app.processEvents()
    assert owner.diagnostic.text == "The selected occurrence has no glyph"
    assert owner.rows == () and owner.table.rowCount() == 0 and owner.occurrence is None
    assert not owner._closing and not owner._released
    owner.sequence._select_occurrence(run.glyphs[0])
    assert owner.rows == (("Light", 500.25), ("Middle", None), ("Bold", 750.75))


def test_window_when_compact_then_host_margin_is_six_and_embedded_preview_is_zero(comparison):
    owner, _, _, _, _ = comparison
    host = owner.sequence.widget.parentWidget().layout()
    margins = host.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (6, 6, 6, 6), (
        "the preview sits 6 px from the window edge, never against it")
    inner = owner.sequence.widget.layout().contentsMargins()
    assert inner.left() == 0, "the embedded sequence adds no second margin"
