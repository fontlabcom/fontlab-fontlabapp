# this_file: tests/test_canvas_scope.py
"""Glyph-window history scope (FontLab issue 8573) in ``edit_guards`` and ``history.commit``.

With a Glyph window as the active canvas, FontLab attaches the Undo step only to
the glyphs that the canvas shows (measured on 9790). These fakes model the
workspace, the canvas text blocks and glyph identity. They prove the refusal
order (before any history call) and the rules, not native FontLab behaviour.
"""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.core.edit_guards as guards
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__


STAMP = "2026-10-22T12:00:00Z"
FACTS = history.auto_facts((("A", False, ()), ("B", False, ())))
TEXT = "Switch to the Font window first"


class Item:
    """A layer or glyph double that logs history calls."""

    def __init__(self, log, name, package=None, ident=0):
        self.log, self.name, self.autoLayer = log, name, False
        self.package, self.id, self.isNull = package, ident, False

    def checkInitHistoryState(self, flag):
        self.log.append(("init", self.name))

    @property
    def lastModified(self):
        return None

    @lastModified.setter
    def lastModified(self, value):
        self.log.append(("stamp", self.name))


class Native:
    """The ``fontlab`` double: notify, queue, workspace with a canvas, current glyph."""

    def __init__(self, log, canvas, package, current="A"):
        self.log = log
        self.flGlyph = NS(updatedFgGlyphs=lambda: ())
        self.flWorkspace = NS(instance=lambda: NS(getActiveCanvas=lambda: canvas, currentPackage=package))
        self.CurrentGlyph = lambda: NS(name=current)

    def flItems(self):
        return self

    def notifyChangesApplied(self, title, items, *flags):
        self.log.append(("notify", [i.name for i in items]))


def canvas_of(*glyphs):
    """A canvas double: one text block that shows ``glyphs``, then one empty slot."""
    slots = [NS(glyph=g) for g in glyphs] + [None]
    block = NS(glyphsCount=lambda: len(slots), getGlyphAt=lambda i: slots[i])
    return NS(isNull=False, textBlocks=lambda: [block])


def world(shown_names=None, *, canvas=None, current="A"):
    """Return log, layers, glyphs A and B of font 5, and the native double.

    ``shown_names``: the glyphs in the Glyph window; ``None`` with no ``canvas``
    means the Font window is active.
    """
    log, package = [], NS(id=5)
    glyphs = [Item(log, "A", package, 100), Item(log, "B", package, 101)]
    layers = [Item(log, "A/Regular"), Item(log, "B/Regular")]
    if canvas is None and shown_names is not None:
        canvas = canvas_of(*(g for g in glyphs if g.name in shown_names))
    return log, layers, glyphs, Native(log, canvas, package, current)


def commit(layers, glyphs, native, **kw):
    return history.commit(
        "Edit", layers, glyphs, lambda: None, operation="geometry", facts=FACTS,
        native=native, stamp=STAMP, **kw,
    )  # fmt: skip


def test_commit_when_font_window_active_then_multi_glyph_write_allowed():
    log, layers, glyphs, native = world()
    commit(layers, glyphs, native)
    assert ("notify", ["A/Regular", "B/Regular", "A", "B"]) in log, log


def test_commit_when_glyph_window_and_other_owner_then_refused_before_any_history_call():
    log, layers, glyphs, native = world({"A"})
    with pytest.raises(ValueError, match=TEXT):
        commit(layers, glyphs, native)
    assert log == [], f"refused before init, mutate and notify: {log}"


def test_commit_when_glyph_window_shows_the_only_owner_then_allowed():
    log, layers, glyphs, native = world({"A"})
    commit(layers[:1], glyphs[:1], native)
    assert ("notify", ["A/Regular", "A"]) in log, log


def test_commit_when_glyph_window_shows_every_owner_then_allowed():
    log, layers, glyphs, native = world({"A", "B"})
    commit(layers, glyphs, native)
    assert ("notify", ["A/Regular", "B/Regular", "A", "B"]) in log, log


def test_commit_when_canvas_shows_owner_under_other_id_then_allowed():
    """``CurrentGlyph().id`` and the canvas slot id differ natively (412 against 531175085312)."""
    log, layers, glyphs, native = world(canvas=canvas_of(NS(package=NS(id=5), id=531175085312, name="A", isNull=False)))
    commit(layers[:1], glyphs[:1], native)
    assert ("notify", ["A/Regular", "A"]) in log, log


def test_commit_when_same_glyph_name_shown_from_other_font_then_refused():
    other = NS(package=NS(id=6), id=100, name="A", isNull=False)
    log, layers, glyphs, native = world(canvas=canvas_of(other))
    with pytest.raises(ValueError, match=TEXT):
        commit(layers[:1], glyphs[:1], native)
    assert log == [], log


def test_commit_when_canvas_unreadable_then_only_the_current_single_owner_allowed():
    class Broken:
        isNull = False

        @property
        def textBlocks(self):
            raise RuntimeError("text blocks unreadable")

    log, layers, glyphs, native = world(canvas=Broken(), current="A")
    commit(layers[:1], glyphs[:1], native)  # A is the current glyph
    guards.require_history_scope((), native=native)  # no owner: as with a readable canvas
    guards.require_history_scope(glyphs[:1] * 2, native=native)  # a repeated owner is one owner
    del log[:]
    for owners in (slice(1, 2), slice(0, 2)):  # B alone; A and B
        with pytest.raises(ValueError, match=TEXT):
            commit(layers[owners], glyphs[owners], native)
    assert log == [], f"refused before any history call: {log}"


def test_require_history_scope_when_off_the_gui_thread_then_refused():
    from threading import Thread

    errors = []

    def run():
        try:
            guards.require_history_scope((), native=world()[3])
        except ValueError as error:
            errors.append(str(error))

    worker = Thread(target=run)
    worker.start()
    worker.join()
    assert errors and TEXT in errors[0], errors


def test_commit_when_glyph_window_ok_given_then_scope_check_skipped():
    log, layers, glyphs, native = world({"A"})
    commit(layers, glyphs, native, glyph_window_ok=True)
    assert ("notify", ["A/Regular", "B/Regular", "A", "B"]) in log, log


def test_canvas_glyphs_when_no_active_canvas_then_none():
    assert guards.canvas_glyphs(world()[3]) is None
    assert guards.canvas_glyphs(world(canvas=NS(isNull=True))[3]) is None


def test_canvas_glyphs_when_glyph_window_then_package_ids_and_names_without_empty_slots():
    native = world({"B"})[3]
    assert guards.canvas_glyphs(native) == frozenset({(5, "B")})


def test_canvas_glyphs_when_deadline_passed_then_timeout_error():
    native = world({"A"})[3]
    with pytest.raises(TimeoutError, match="deadline"):
        guards.canvas_glyphs(native, deadline=0.0)


def test_require_history_scope_when_creating_from_glyph_window_then_refused():
    native = world(set())[3]
    with pytest.raises(ValueError, match=TEXT):
        guards.require_history_scope((), creates=True, native=native)
    guards.require_history_scope((), native=native)  # no owner and nothing new


def test_require_history_scope_when_font_window_then_creation_allowed():
    guards.require_history_scope((), creates=True, native=world()[3])


def test_require_history_scope_when_owner_identity_unreadable_then_refused():
    native = world({"A"})[3]
    with pytest.raises(ValueError, match=TEXT):
        guards.require_history_scope((NS(name="A"),), native=native)  # no package
