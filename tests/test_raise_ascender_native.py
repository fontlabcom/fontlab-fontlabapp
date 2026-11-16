# this_file: tests/test_raise_ascender_native.py
"""Native-shaped adversarial controls; no FontLab invocation or font fixtures."""

from time import monotonic
from types import SimpleNamespace as NS

import pytest

import fontlabapp.contours.raise_ascender._capture as capture
import fontlabapp.contours.raise_ascender._write as write


def clock():
    return monotonic() + 10


class Owner:
    def __init__(self, events, name, fails=()):
        self.events, self.name, self.fails = events, name, fails

    def checkInitHistoryState(self, _):
        self.events.append(self.name + ":history")

    @property
    def lastModified(self):
        return None

    @lastModified.setter
    def lastModified(self, stamp):
        self.events.append(self.name + ":stamp")
        if "stamp" in self.fails:
            raise RuntimeError(self.name + ":date failed")


class Layer(Owner):
    def __init__(self, events, fails=()):
        super().__init__(events, "layer", fails)
        self.shapes = [NS(id=1), NS(id=99)]

    def removeShape(self, old):
        self.events.append("remove")
        self.shapes.remove(old)

    def insertShape(self, index, shape):
        self.events.append("insert")
        if "insert" in self.fails:
            raise RuntimeError("insert failed")
        self.shapes.insert(index, shape)
        return shape

    def changed(self):
        self.events.append("changed")

    def update(self):
        self.events.append("update")
        return "update" not in self.fails


def fixture(fails=(), glyph_fails=()):
    events = []
    layer, glyph = Layer(events, fails), Owner(events, "glyph", glyph_fails)

    def notify(*args):
        events.append(("notify", args))
        if "notify" in fails:
            raise RuntimeError("notify failed")

    native = NS(flItems=lambda: NS(notifyChangesApplied=notify))
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "utc")))
    jobs = ((0, layer.shapes[0], NS(id=2)),)
    return events, layer, glyph, native, qt, jobs


def test_one_notification_includes_layer_glyph_and_dependant_without_updateall():
    events, layer, glyph, native, qt, jobs = fixture()
    dependant = Owner(events, "dependent")
    write.publish(glyph, layer, jobs, (dependant,), native, qt, clock())
    notes = [event for event in events if isinstance(event, tuple)]
    assert len(notes) == 1 and notes[0][1][1] == [layer, glyph, dependant]
    assert [shape.id for shape in layer.shapes] == [2, 99]
    assert events.index("glyph:stamp") < events.index(notes[0])
    assert events[-1] == "dependent:stamp"


@pytest.mark.parametrize(
    "fails,glyph_fails",
    [
        (("insert",), ()),
        (("update",), ()),
        (("notify",), ()),
        ((), ("stamp",)),
        (("notify",), ("stamp",)),
    ],
)
def test_partial_failure_notifies_exactly_once_and_retains_every_error(
    fails, glyph_fails
):
    events, layer, glyph, native, qt, jobs = fixture(fails, glyph_fails)
    with pytest.raises(write.PartialWriteError) as error:
        write.publish(glyph, layer, jobs, (), native, qt, clock())
    assert len([item for item in events if isinstance(item, tuple)]) == 1
    assert events.count("glyph:stamp") == 2
    assert "Undo" in str(error.value)
    assert len(error.value.errors) == (
        3 if fails == ("notify",) and glyph_fails else 2 if glyph_fails else 1
    )


def test_expired_or_stale_prewrite_has_no_notification_or_mutation():
    events, layer, glyph, native, qt, jobs = fixture()
    with pytest.raises(TimeoutError):
        write.publish(glyph, layer, jobs, (), native, qt, 0)
    assert not events
    with pytest.raises(ValueError, match="identity"):
        write.publish(
            glyph, layer, ((0, NS(id=-1), NS(id=2)),), (), native, qt, clock()
        )
    assert not any(item == "remove" or isinstance(item, tuple) for item in events)


def test_stop_after_partial_first_occurrence_and_after_callback_drift():
    events, layer, glyph, native, qt, jobs = fixture(("insert",))
    work = ((glyph, layer, jobs, (), "first", 1),) * 2
    with pytest.raises(write.PartialWriteError):
        write.run(work, lambda expected: None, native, qt, clock())
    assert events.count("remove") == 1
    events, layer, glyph, native, qt, jobs = fixture()

    def drift(expected):
        raise ValueError("callback drift")

    with pytest.raises(write.PartialWriteError, match="1 completed"):
        write.run(
            ((glyph, layer, jobs, (), "expected", 1),), drift, native, qt, clock()
        )


def test_noop_scopes_validate_without_history():
    events, layer, glyph, native, qt, _jobs = fixture()
    checks = []
    result = write.run(
        ((glyph, layer, (), (), "unchanged", 0),), checks.append, native, qt, clock()
    )
    assert result == {"occurrences": 1, "undo_steps": 0, "nodes": 0}
    assert checks == ["unchanged"] and not events


def test_all_action_keeps_first_parent_auxiliary_service_order(monkeypatch):
    package = NS(id=1)
    layers = [
        NS(id=1, isMaskLayer=False),
        NS(id=2, isMaskLayer=True),
        NS(id=3, isMaskLayer=False, isService=True),
    ]
    glyph = NS(isNull=False, package=package, layers=layers)
    package.findName = lambda name: glyph
    document = NS(package=package, context=(1, "Regular", "font"), carriers=())
    package.fgId = 9
    monkeypatch.setattr(capture.selection, "_document", lambda deadline: document)
    monkeypatch.setattr(
        capture.selection, "names_font_window_selection", lambda **kw: ("A", "A")
    )
    _, result = capture.selected(True, clock())
    assert [layer.id for _, layer in result] == [1, 3]


def test_editor_empty_symbol_refuses_selected_but_all_never_reads_active(monkeypatch):
    package = NS(id=1)

    class Glyph:
        isNull = False
        layers = (NS(id=3, isMaskLayer=False),)

        @property
        def activeLayer(self):
            raise AssertionError("initializing getter")

    glyph = Glyph()
    glyph.package = package
    info = NS(isSelected=True, glyph=glyph, symbol=NS(layerName=""))
    block = NS(glyphsCount=lambda: 2, getGlyphAt=lambda i: info)
    document = NS(package=package, context=(1, "Regular", "editor"), blocks=(block,))
    monkeypatch.setattr(capture.selection, "_document", lambda deadline: document)
    with pytest.raises(ValueError, match="explicit layer"):
        capture.selected(False, clock())
    _, result = capture.selected(True, clock())
    assert result == ((glyph, glyph.layers[0]),)


def test_full_dependencies_all_layers_and_exact_font_order(monkeypatch):
    package = NS(id=1, fgId=9)
    component = NS(isComponent=True, shapeData=NS(componentGlyph='base'))
    own = NS(isComponent=False)
    layer = NS(id=4, name='Regular.aux', autoLayer=False, shapes=(component, own))
    glyph = NS(id=2, name='A', isNull=False, layers=(layer,))
    package.findFgId = lambda identity: glyph
    font = NS(id=9, glyphs=(NS(id=3, name='A'),))
    monkeypatch.setattr(capture, '_native', lambda name: NS(CurrentFont=lambda: font))
    assert capture.dependencies(package, clock()) == ((2, 'A', ((4, 'Regular.aux', False, ('base',)),)),)
    font.id = 8
    with pytest.raises(ValueError, match='carrier'):
        capture.dependencies(package, clock())
    font.id = 9
    glyph.name = 'renamed'
    with pytest.raises(ValueError, match='mapping'):
        capture.dependencies(package, clock())


def test_selected_font_occurrences_and_editor_explicit_mapping(monkeypatch):
    package = NS(id=1, fgId=9)
    layer = NS(isNull=False)
    glyph = NS(isNull=False, package=package, findLayer=lambda name: layer)
    package.findName = lambda name: glyph
    document = NS(package=package, context=(1, 'Regular', 'font'))
    monkeypatch.setattr(capture.selection, '_document', lambda deadline: document)
    monkeypatch.setattr(capture.selection, 'names_font_window_selection', lambda **kw: ('A', 'A'))
    assert capture.selected(False, clock())[1] == ((glyph, layer), (glyph, layer))
    info = NS(isSelected=True, glyph=glyph, symbol=NS(layerName='Regular.aux'))
    document.context = (1, 'Regular', 'editor')
    document.blocks = (NS(glyphsCount=lambda: 3, getGlyphAt=lambda i: info if i == 1 else None),)
    assert capture.selected(False, clock())[1] == ((glyph, layer),)
    layer.isNull = True
    with pytest.raises(ValueError, match='disappeared'):
        capture.selected(False, clock())
    layer.isNull = False
    glyph.isNull = True
    with pytest.raises(ValueError, match='owner'):
        capture.selected(False, clock())


def test_empty_first_parent_and_unreadable_mask_role_refuse(monkeypatch):
    package = NS(id=1, fgId=9)
    glyph = NS(isNull=False, package=package, layers=(NS(isMaskLayer=1),))
    package.findName = lambda name: glyph
    document = NS(package=package, context=(1, 'Regular', 'font'))
    monkeypatch.setattr(capture.selection, '_document', lambda deadline: document)
    monkeypatch.setattr(capture.selection, 'names_font_window_selection', lambda **kw: ())
    with pytest.raises(ValueError, match='Select a glyph'):
        capture.selected(True, clock())
    monkeypatch.setattr(capture.selection, 'names_font_window_selection', lambda **kw: ('A',))
    with pytest.raises(ValueError, match='background role'):
        capture.selected(True, clock())


def test_unreadable_master_domain_is_not_current_master_fallback(monkeypatch):
    monkeypatch.setattr(capture, '_native', lambda name: NS(call=lambda *a, **kw: None))
    with pytest.raises(ValueError, match='master domain'):
        capture.masters(NS(id=1, fgId=9, masters=('A',)), clock())
