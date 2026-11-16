# this_file: tests/test_direct_notifier_canvas_scope.py
"""Direct writers refuse before history or mutation; doubles are not native proof."""

from module_paths import module_name as _module_name
from importlib import import_module
from time import monotonic
from types import SimpleNamespace as NS
from unittest.mock import Mock

import fontlabapp.core.edit_guards as guards

import pytest

from test_canvas_scope import Item, Native, TEXT, canvas_of
from test_background_clear_native import setup as background_setup


MODULES = (
    "_angularizzle_native_write", "_raise_ascender_write", "anchor_copy",
    "anchor_duplicates_native", "background_clear_native", "guide_rewrite",
    "guides", "perpendicular_guides_native",
)


class Layer(Item):
    def __init__(self, log, name):
        super().__init__(log, name)
        self.shapes = [NS(id=1)]
        self.anchors = [NS(id=2, name="top")]
        self.guidelines = []
        self.mark = 0

    def removeShape(self, shape):
        self.log.append(("remove-shape", self.name))
        self.shapes.remove(shape)

    def insertShape(self, index, shape):
        self.log.append(("insert-shape", self.name))
        self.shapes.insert(index, shape)
        return shape

    def removeAnchor(self, pin):
        self.log.append(("remove-anchor", self.name))
        self.anchors.remove(pin)

    def appendGuidelines(self, values):
        self.log.append(("append-guides", self.name))
        self.guidelines.extend(values)

    def removeGuides(self, *args):
        self.log.append(("remove-guides", self.name))
        self.guidelines.clear()

    def changed(self):
        self.log.append(("changed", self.name))

    def update(self):
        self.log.append(("update", self.name))
        return True


def scenario(monkeypatch, module, canvas):
    api = import_module(_module_name(module))
    if module == "background_clear_native":
        backend, package, glyph, body, mask, aux, log, queue, native = background_setup(monkeypatch)
        glyph.package = package
        native.flWorkspace = NS(instance=lambda: NS(
            getActiveCanvas=lambda: (canvas_of(glyph) if canvas == "all" else canvas_of()) if canvas else None))
        source = backend.capture()
        before = tuple(glyph.layers)
        return (lambda: backend.apply(source, False), log,
                lambda: tuple(glyph.layers) == before and glyph.lastModified == "before")

    log, package = [], NS(id=5)
    glyphs = [Item(log, name, package, ident) for name, ident in (("A", 100), ("B", 101))]
    layers = [Layer(log, "A/Regular"), Layer(log, "B/Regular")]
    shown = glyphs if canvas == "all" else glyphs[:1]
    native = Native(log, canvas_of(*shown) if canvas else None, package)
    native.UpdateAll = lambda: log.append(("refresh",))
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "stamp")))
    if hasattr(api, "_native"):
        monkeypatch.setattr(api, "_native", lambda name: native if name == "fontlab" else qt)
    deadline = monotonic() + 10
    before = [(tuple(layer.shapes), tuple(layer.anchors), tuple(layer.guidelines), layer.mark)
              for layer in layers]

    def unchanged():
        return before == [(tuple(layer.shapes), tuple(layer.anchors), tuple(layer.guidelines), layer.mark)
                          for layer in layers]

    if module == "_angularizzle_native_write":
        for glyph in glyphs:
            glyph.changed = lambda: None
            glyph.update = lambda: True
        jobs = tuple((NS(glyph=g, layer=l), ((0, l.shapes[0], NS(id=3)),), 7, None)
                     for g, l in zip(glyphs, layers))
        call = lambda: api.publish(jobs, native, qt, deadline)
    elif module == "_raise_ascender_write":
        work = tuple((g, l, ((0, l.shapes[0], NS(id=3)),), (), None, 1)
                     for g, l in zip(glyphs, layers))
        call = lambda: api.run(work, lambda expected: None, native, qt, deadline)
    elif module == "anchor_copy":
        work = [(g, l, [(l.anchors[0], None)])
                for g, l in zip(glyphs, layers)]
        call = lambda: api._apply(work, "Copy")
    elif module == "anchor_duplicates_native":
        work = [(g, l, tuple(l.anchors)) for g, l in zip(glyphs, layers)]
        call = lambda: api.remove(work, deadline)
    elif module == "guide_rewrite":
        monkeypatch.setattr(api, "guide_record", lambda guide: (0, 1, 0, ""))
        work = [(g, l, [NS(id=4, isHint=False)]) for g, l in zip(glyphs, layers)]
        call = lambda: api._apply(work, "Guides")
    elif module == "guides":
        monkeypatch.setattr(api, "require_safe_targets", lambda *args: None)
        monkeypatch.setattr(api, "new_guide", lambda values: NS(id=4))
        work = [(g, l, [(1, 2, 0, "")]) for g, l in zip(glyphs, layers)]
        call = lambda: api.add_guides(package, work)
    else:
        target = NS(glyph=glyphs[1], layer=layers[1])
        source = api.Snapshot(((),), (), (), (), target)
        monkeypatch.setattr(api, "capture", lambda deadline: source)
        monkeypatch.setattr(api, "new_guide", lambda values: NS(id=4))
        call = lambda: api.write(source, ((1, 2, 0),), deadline)
    return call, log, unchanged


@pytest.mark.parametrize("module", MODULES)
def test_direct_notifier_when_canvas_omits_owner_then_refuses_before_history_or_mutation(monkeypatch, module):
    guard = Mock(wraps=guards.require_history_scope)
    monkeypatch.setattr(guards, "require_history_scope", guard)
    call, log, unchanged = scenario(monkeypatch, module, True)
    with pytest.raises(ValueError, match=TEXT):
        call()
    assert guard.call_count == 1, f"{module} must preflight once"
    assert log == [], f"{module} must refuse before history or mutation: {log}"
    assert unchanged(), f"{module} changed its native payload on refusal"


@pytest.mark.parametrize("canvas", [False, "all"], ids=["font-window", "canvas-shows-every-owner"])
@pytest.mark.parametrize("module", MODULES)
def test_direct_notifier_when_no_canvas_or_every_owner_shown_then_applies_and_notifies(monkeypatch, module, canvas):
    guard = Mock(wraps=guards.require_history_scope)
    monkeypatch.setattr(guards, "require_history_scope", guard)
    call, log, unchanged = scenario(monkeypatch, module, canvas)
    call()
    assert guard.call_count == 1, f"{module} must preflight once"
    assert guard.call_args.kwargs["native"] is not None, "Use the injected native seam"
    assert any(event[0] == "notify" for event in log), f"{module} did not notify: {log}"
    assert not unchanged(), f"{module} did not mutate its target"


@pytest.mark.parametrize("canvas", [True, False])
def test_raise_ascender_when_notifying_dependant_then_preflights_owner_union(monkeypatch, canvas):
    from test_raise_ascender_native import fixture, clock, Owner

    api = import_module("fontlabapp.contours.raise_ascender._write")
    events, layer, glyph, native, qt, jobs = fixture()
    dependant = Owner(events, "dependent")
    for ident, owner in enumerate((glyph, dependant)):
        owner.package, owner.id, owner.isNull = NS(id=5), ident, False
    native.flWorkspace = NS(instance=lambda: NS(
        getActiveCanvas=lambda: canvas_of(glyph) if canvas else None))
    guard = Mock(wraps=guards.require_history_scope)
    monkeypatch.setattr(guards, "require_history_scope", guard)
    # The no-op occurrence contributes no additional notified owners.
    work = ((glyph, layer, jobs, (dependant,), None, 1),
            (glyph, layer, (), (), None, 0))
    if canvas:
        with pytest.raises(ValueError, match=TEXT):
            api.run(work, lambda expected: None, native, qt, clock())
        assert events == [], "A hidden dependant must refuse before any history"
        assert [shape.id for shape in layer.shapes] == [1, 99], "Refusal changed shapes"
    else:
        assert api.run(work, lambda expected: None, native, qt, clock())["undo_steps"] == 1
        assert [shape.id for shape in layer.shapes] == [2, 99], "No-canvas write did not apply"
    assert guard.call_count == 1, "Check the full union once before the occurrence loop"
    assert guard.call_args.args[0] == [glyph, dependant], "Include all notified dependants"
