# this_file: tests/test_layer_writer.py
"""Generic layer writer kernel shared by the Components and Contours scripts (issue 122, T14g).

The FontLab doubles of ``test_component_writer`` log every native call, so
the tests pin the exact one-Undo protocol of ``apply_work``: prepare before
history, init, write, stamp, ONE notify, stamp, read-back. They also pin the
S4/S6 merge points (``Change.key``, ``Plan.refused``/``held``,
``allow_bases``, ``fmt`` places) and the public wording of the kernel. They
do not prove native FontLab Undo/Redo behaviour.
"""

from module_paths import module_file as _module_file
from pathlib import Path

import pytest
import test_component_writer as fld

import fontlabapp.components.writer as cw
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.masters.layers.writer as lw
import fontlabapp.contours.writer as ow

LOG = fld.LOG
native = fld.native  # the FontLab and PythonQt doubles, as a fixture of this module
SHARED = ("EPSILON", "Change", "Editor", "Plan", "Planner", "Work", "apply_work",
          "fmt", "layer_of", "plural", "settle", "shown")  # fmt: skip


class Recorder(lw.Editor):
    """An editor that logs each step; `keep` False makes the read-back fail."""

    def __init__(self, keep: bool = True, retained: tuple = ()) -> None:
        self.keep, self.retained = keep, retained

    def prepare(self, layer, edits):
        LOG.append(("prepare", layer.name))
        return list(edits)

    def write(self, layer, steps):
        LOG.append(("write", layer.name, tuple(steps)))

    def check(self, prepared):
        return [] if self.keep else [f"{layer.name}: {len(steps)}" for layer, steps in prepared]

    def retain(self, steps):
        return list(self.retained)


def work_of(*glyphs, master="L"):
    return [(g, g.by_master[master], [f"edit-{g.name}"]) for g in glyphs]


# ---------------------------------------------------------------- data model
def test_change_when_built_positionally_then_s4_order_and_key_last_default_none():
    row = lw.Change("A", "1", "2", "edit", "bad")
    assert (row.name, row.old, row.new, row.edit, row.problem, row.key) == ("A", "1", "2", "edit", "bad", None)
    assert lw.Change("A", "", "", key=("delete", 3)).key == ("delete", 3)


def test_plan_when_new_then_every_list_empty_and_edits_counts_all_layers():
    plan = lw.Plan()
    assert (plan.work, plan.rows, plan.skipped, plan.refused, plan.held, plan.problems) == ([], [], [], [], [], [])
    plan.work = [(None, None, [1, 2]), (None, None, [3])]
    assert plan.edits == 3


def test_fmt_when_places_given_then_rounds_else_keeps_s4_text():
    assert lw.fmt(700.0) == "700" and lw.fmt(12.254) == "12.254" and lw.fmt(12.5) == "12.5"
    assert lw.fmt(12.254, 2) == "12.25" and lw.fmt(700.0, 2) == "700"
    assert cw.fmt(12.254) == "12.254", "component scripts keep every digit"
    assert ow.fmt(12.254) == "12.25" and ow.PLACES == 2, "outline scripts round to 2 places"


def test_small_helpers_when_called_then_exact_texts():
    assert (lw.plural(1, "layer"), lw.plural(2, "layer")) == ("1 layer", "2 layers")
    assert lw.shown([str(i) for i in range(9)]) == "0, 1, 2, 3, 4, 5, 6, 7 …"
    assert lw.shown(["a", "b"]) == "a, b"
    glyph = fld.Glyph("A", L=[])
    assert lw.layer_of(glyph, "L") is glyph.by_master["L"] and lw.layer_of(glyph, "B") is None


def test_settle_when_update_refused_then_runtime_error_names_layer(native):
    layer = fld.Layer("A", "L")
    lw.settle(layer)
    assert LOG == [("changed", "A/L")]
    layer.update_result = False
    with pytest.raises(RuntimeError, match="could not update layer A/L"):
        lw.settle(layer)


@pytest.mark.parametrize("module", [cw, ow])
def test_family_module_when_imported_then_kernel_names_are_the_layer_writer_objects(module):
    for name in SHARED:
        assert getattr(module, name) is getattr(lw, name) or (module is ow and name == "fmt"), name
        assert name in module.__all__, name


# ---------------------------------------------------------------- apply_work
def test_apply_work_when_nothing_retained_then_two_argument_notify_after_prepare(native):
    a, b = fld.Glyph("A", L=[]), fld.Glyph("B", L=[])
    result = lw.apply_work(work_of(a, b), "Shift", fld.facts(), Recorder())
    assert result == {"pending_note": "", "edits": 2, "layers": 2, "pending_updates": ()}
    assert LOG == [
        ("prepare", "A/L"), ("prepare", "B/L"),
        ("init", "A/L"), ("init", "B/L"), ("init", "A"), ("init", "B"),
        ("write", "A/L", ("edit-A",)), ("changed", "A/L"),
        ("write", "B/L", ("edit-B",)), ("changed", "B/L"),
        ("stamp", "A", fld.STAMP), ("stamp", "B", fld.STAMP),
        ("notify", "Shift", ["A/L", "B/L", "A", "B"], ()),
        ("stamp", "A", fld.STAMP), ("stamp", "B", fld.STAMP),
    ]  # fmt: skip


def test_apply_work_when_editor_retains_then_retained_first_and_deep_history(native):
    a = fld.Glyph("A", L=[])
    kept = fld.Shape("x")
    lw.apply_work(work_of(a), "Cut", fld.facts(), Recorder(retained=(kept,)))
    assert fld.history_events()[3] == ("notify", "Cut", [kept.marker, "A/L", "A"], (True,))


def test_apply_work_when_glyph_is_auto_base_then_refused_unless_allow_bases(native):
    a = fld.Glyph("A", L=[])
    found = fld.facts(("Aacute", True, ("A",)))
    with pytest.raises(ValueError, match="base of auto Aacute"):
        lw.apply_work(work_of(a), "Shift", found, Recorder())
    assert fld.history_events() == [], "refused before history"
    assert lw.apply_work(work_of(a), "Shift", found, Recorder(), allow_bases=True) == {"pending_note": "", "edits": 1, "layers": 1, "pending_updates": ()}
    assert [e[0] for e in fld.history_events()] == ["init", "init", "stamp", "notify", "stamp"]


def test_apply_work_when_font_does_not_keep_edits_then_check_text_without_undo_claim(native):
    a = fld.Glyph("A", L=[])
    with pytest.raises(RuntimeError) as raised:
        lw.apply_work(work_of(a), "Shift", fld.facts(), Recorder(keep=False))
    assert str(raised.value) == "FontLab did not store 1 change(s): A/L: 1. Check those layers before you save."
    assert "Undo" not in str(raised.value)


def test_apply_work_when_write_raises_then_partial_write_error_says_use_undo(native):
    class Broken(Recorder):
        def write(self, layer, steps):
            raise RuntimeError("boom write")

    with pytest.raises(history.PartialWriteError, match="use Edit > Undo"):
        lw.apply_work(work_of(fld.Glyph("A", L=[])), "Shift", fld.facts(), Broken())


def test_apply_work_when_work_is_empty_then_no_history(native):
    assert lw.apply_work([], "Shift", fld.facts(), Recorder()) == {"edits": 0, "layers": 0, "pending_updates": (), "pending_note": ""}
    assert LOG == []


# ---------------------------------------------------------------- public wording (S6 review I4, I5)
WORDED = ("layer_writer", "component_writer", "outline_writer", "outline_panel",
          "_outline_panel", "outline_transform", "_outline_transform")  # fmt: skip


@pytest.mark.parametrize("stem", WORDED)
def test_kernel_text_when_read_then_never_claims_that_undo_restores(stem):
    text = _module_file(stem).read_text(encoding="utf-8")
    for claim in ("Undo restores", "brings back", "bring the component back", "Undo can bring"):
        assert claim not in text, (stem, claim)


def test_apply_work_doc_when_read_then_neutral_about_what_the_write_keeps():
    doc = lw.apply_work.__doc__ or ""
    assert "the write strategy decides what is kept" in doc
    assert "names, notes and node flags stay" not in doc
