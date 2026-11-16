# this_file: tests/test_studio_kerning_studio.py
"""Kerning Studio (Phase D A1): model, session writes and the four tabs on offscreen Qt.

Writes are checked for the master they target and their ``Kerning Studio: …``
Undo label (§1.3/§1.4); read-only paths are checked never to touch native
history or apply kerning.
"""

import importlib
import sys
from types import SimpleNamespace

import pytest
from _cov_qt import FontModel, ufo_font
from _studio_qt import studio_qt  # noqa: F401 - fixture


K1, K2 = "public.kern1.", "public.kern2."
TABS = "fontlabapp.studios.kerning_studio.tabs"
QT_MODULES = (TABS, "fontlabapp.fontui.kerning", "fontlabapp.fontui.kerning_view")


@pytest.fixture(autouse=True)
def qt_kerning(studio_qt, monkeypatch):  # noqa: F811
    """fontui.kerning imports its Qt view; load it (and the tabs) on offscreen Qt, then drop them."""
    for name in QT_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield studio_qt
    for name in QT_MODULES:
        sys.modules.pop(name, None)
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)  # keep later "no studio child loaded" contracts order-independent


def _model():
    return importlib.import_module("fontlabapp.studios.kerning_studio.model")


class _Lazy:
    def __getattr__(self, name):
        return getattr(_model(), name)


model = _Lazy()


def MasterData(*args):  # noqa: N802 - mirrors the model type
    return _model().MasterData(*args)


# Fakes ---------------------------------------------------------------------
# A native package shaped like tests/test_kerning_batch.py's font_double, so the
# studio writes go through the real fontlabapp.kerning.batch pipeline.
HOST = SimpleNamespace(package=None)
GLYPHS = {"A", "Aacute", "V", "W", "O"}


@pytest.fixture(autouse=True)
def native_host(monkeypatch):
    """Route ``_native("fontlab")`` of the batch writer and scripting reader to ``HOST``."""
    import fontlabapp.kerning.batch as batch
    from fontlabapp.core import scripting

    def checkpoint(name, objects):
        pkg = HOST.package
        assert objects == [pkg, "masters", "kerning"], "only package/containers enter history"
        pkg.history.append((name, {m: dict(k.values) for m, k in pkg.kerns.items()}))

    native = SimpleNamespace(
        flWorkspace=SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=HOST.package)),
        flItems=SimpleNamespace(notifyChangesApplied=checkpoint),
    )
    monkeypatch.setattr(scripting, "_native", lambda name: native)
    monkeypatch.setattr(batch, "_native", lambda name: native)
    yield
    HOST.package = None


def _decode(key):
    return tuple(("@" if mode == "groupMode" else "") + name for name, mode in key)


class Kern:
    """``package.kerning(master)``: typed items, native classes, batch setters."""

    def __init__(self, values, groups, writes):
        object.__setattr__(self, "_writes", writes)
        self.values, self.groups = values, groups

    def items(self):
        def side(name):
            group = name.startswith("@")
            return SimpleNamespace(id=name.lstrip("@"), mode="groupMode" if group else "glyphMode")

        return [(SimpleNamespace(left=side(a), right=side(b)), v) for (a, b), v in self.values.items()]

    def set(self, key, value):
        self._writes.append("set")
        if value != 0:  # the native setter drops zero
            self.values[_decode(key)] = value

    def remove(self, key):
        self._writes.append("remove")
        self.values.pop(_decode(key), None)

    def scale(self, factor):
        self._writes.append("scale")
        self.values = {key: amount * factor for key, amount in self.values.items()}

    def __setattr__(self, name, value):
        if "has_history_changes" in name:
            self._writes.append(name)
        object.__setattr__(self, name, value)


class Package:
    """Native package fake; ``writes`` records setters and history flags, ``history`` Undo steps."""

    def __init__(self, masters, current="Regular"):
        object.__setattr__(self, "writes", [])
        object.__setattr__(self, "history", [])
        object.__setattr__(
            self, "kerns", {m: Kern(dict(p), dict(g), self.writes) for m, (p, g) in masters.items()}
        )
        object.__setattr__(self, "master", current)
        object.__setattr__(self, "id", 7)
        object.__setattr__(self, "isNull", False)
        object.__setattr__(self, "upm", 1000)
        HOST.package = self

    @property
    def masters(self):
        return list(self.kerns)

    def kerning(self, master):
        return self.kerns[master]

    def findName(self, name):  # noqa: N802 - native API
        return SimpleNamespace(isNull=False) if name in GLYPHS else None

    def checkInitHistoryState(self, flags):  # noqa: N802 - native API
        pass

    def mastersContainer(self):  # noqa: N802 - native API
        return "masters"

    def kerningContainer(self):  # noqa: N802 - native API
        return "kerning"

    def values(self, master):
        return self.kerns[master].values

    def __setattr__(self, name, value):
        if "has_history_changes" in name:
            self.writes.append(name)
        object.__setattr__(self, name, value)


GROUPS = {"A": (["A", "Aacute"], "KernLeft"), "V": (["V", "W"], "KernRight"), "O": (["O"], "KernBothSide")}


def package():
    regular = ({("@A", "@V"): -80, ("A", "W"): -40}, GROUPS)
    bold = ({("@A", "@V"): -60}, GROUPS)
    return Package({"Regular": regular, "Bold": bold})


def font():
    ufo = ufo_font()
    for name, code in (("Aacute", 0xC1), ("W", 87), ("O", 79)):
        glyph = ufo.newGlyph(name)
        glyph.width, glyph.unicodes = 600, [code]
        pen = glyph.getPen()
        pen.moveTo((0, 0))
        pen.lineTo((300, 700))
        pen.lineTo((600, 0))
        pen.closePath()
    ufo.info.xHeight = 500
    made = FontModel(ufo)
    made.defaultLayerName = "Regular"
    made.glyphOrder = ["A", "Aacute", "V", "W", "O"]
    made.getLayer = lambda name: made  # same outlines on every master
    return made


class Preview:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *args: self.calls.append((name, *args))


class Shell:
    """Status/package stand-in for session-only tests."""

    def __init__(self, pkg):
        self.pkg, self.statuses = pkg, []

    def package(self):
        return self.pkg

    def set_status(self, text):
        self.statuses.append(text)


def session(pkg=None, fnt=None):
    from fontlabapp.studios.kerning_studio.session import Studio

    the_font = fnt if fnt is not None else font()
    studio = Studio(Shell(pkg if pkg is not None else package()), font=lambda: the_font)
    studio.reload()
    return studio, the_font


# Model -----------------------------------------------------------------------
def test_from_native_when_both_side_class_then_kern1_and_kern2_groups():
    data = model.from_native({("@A", "@V"): -5}, {"O": (["O"], "both"), "public.kern1.A": (["A"], "left")})
    assert data.groups == {K1 + "O": ("O",), K2 + "O": ("O",), K1 + "A": ("A",)}
    assert data.pairs == {(K1 + "A", K2 + "V"): -5}


def test_side_text_when_parsed_then_ufo_keys_and_blank_refused():
    assert model.parse_side(" @A ", 0) == K1 + "A"
    assert model.parse_side("V", 1) == "V"
    assert model.display(K2 + "V") == "@V"
    with pytest.raises(ValueError, match="Enter a left"):
        model.parse_side("@", 0)


def test_effective_when_glyph_and_class_records_then_most_specific_wins():
    data = MasterData({(K1 + "A", K2 + "V"): -80, ("A", "W"): -40}, {K1 + "A": ("A",), K2 + "V": ("V", "W")})
    assert model.effective(data, "A", "W") == (-40, ("A", "W"))
    assert model.effective(data, "A", "V") == (-80, (K1 + "A", K2 + "V"))
    assert model.effective(data, "V", "A") == (0, None)
    assert model.class_key(data, "A", "W") == (K1 + "A", K2 + "V")
    assert model.target_key(data, "V", "A") == ("V", "A")
    assert model.overrides(data, (K1 + "A", K2 + "V"), "A", "W") == [(("A", "W"), -40)]
    assert model.candidates(data, K1 + "A", "W") == [(K1 + "A", "W"), (K1 + "A", K2 + "V")]


def test_side_groups_when_two_groups_one_side_then_refused():
    with pytest.raises(ValueError, match="multiple kerning groups"):
        model.side_groups({K1 + "A": ("A",), K1 + "B": ("A",)}, "A")


def test_kern_to_max_and_range_when_values_given_then_original_rules():
    assert model.kern_to_max(600, 301) == -150
    with pytest.raises(ValueError, match="finite"):
        model.kern_to_max(-1, 10)
    model.check_range(2000, 1000, "Regular", ("A", "V"))
    with pytest.raises(ValueError, match="±2000"):
        model.check_range(-2001, 1000, "Regular", (K1 + "A", "V"))
    with pytest.raises(ValueError, match="units per em"):
        model.check_range(1, None, "Regular", ("A", "V"))


def test_text_when_parsed_then_words_and_unique_adjacent_pairs():
    words = model.parse_text("AV /A/W x VA", {65: "A", 86: "V"})
    assert words == [["A", "V"], ["A", "W"], ["V", "A"]]
    assert model.text_pairs([*words, ["A", "V"]]) == [("A", "V"), ("A", "W"), ("V", "A")]


def test_glyph_pairs_and_peers_when_glyph_given_then_records_and_visual_sides():
    data = MasterData({(K1 + "A", K2 + "V"): -80, ("X", "Y"): 1}, {K1 + "A": ("A", "B"), K2 + "A": ("A", "C")})
    assert model.glyph_pairs({"R": data}, "A") == [(K1 + "A", K2 + "V")]
    assert model.group_peers(data.groups, "A", ["C", "B", "A"]) == {"L": ["C"], "R": ["B"]}


def test_extents_when_triangle_then_crossings_and_errors():
    rec = [("moveTo", ((0, 0),)), ("lineTo", ((300, 600),)), ("lineTo", ((600, 0),)), ("closePath", ())]
    assert model.extents(rec, 300, "A", "Regular") == ((150.0, 450.0), 0)
    flat = [("moveTo", ((0, 0),)), ("lineTo", ((10, 0),)), ("lineTo", ((10, 5),)), ("closePath", ())]
    assert model.extents(flat, 0, "F", "R")[0] == (0, 10)
    with pytest.raises(ValueError, match="No closed outline crossing at height 900 in Regular"):
        model.extents(rec + [("moveTo", ((0, 0),)), ("lineTo", ((1, 1),)), ("endPath", ())], 900, "A", "Regular")
    curves = [
        ("moveTo", ((0, 0),)),
        ("curveTo", ((0, 100), (100, 100), (100, 0))),
        ("qCurveTo", ((50, -50), (0, 0))),
        ("closePath", ()),
    ]
    low, high = model.extents(curves, 10, "C", "R")[0]
    assert low < 5 and high > 95
    with pytest.raises(ValueError, match="Unsupported qCurveTo"):
        model.extents([("qCurveTo", ((0, 0), (1, 1), None)), ("closePath", ())], 0, "Q", "R")


def test_steal_value_when_gaps_differ_then_reference_added_and_truncated():
    value, gap1, gap2 = model.steal_value([600, 600, 500, 500], [(0, 600), (0, 600), (100, 400), (100, 400)], -10)
    assert (gap1, gap2) == (0, 200) and value == 190


# Session writes ----------------------------------------------------------------
def test_reload_when_package_then_all_masters_read_without_writes():
    studio, _ = session()
    assert list(studio.masters) == ["Regular", "Bold"] and studio.current == studio.master == "Regular"
    assert studio.value("Bold", "Aacute", "W") == (-60, (K1 + "A", K2 + "V"))
    assert studio.shell.pkg.writes == []


def test_reload_when_no_package_or_bad_read_then_status():
    studio, _ = session()
    studio.shell.pkg = None
    studio.reload()
    assert studio.shell.statuses[-1] == "Open a font first." and studio.masters == {}
    pkg = package()
    HOST.package = None  # the snapshot refuses a package that is no longer current
    studio2, _ = session(pkg=pkg)
    assert studio2.shell.statuses[-1].startswith("Kerning Studio: ") and studio2.masters == {}


def history_labels(pkg):
    """One Undo step per write: batch checkpoints each step twice (before and after)."""
    names = [name for name, _values in pkg.history]
    assert names[0::2] == names[1::2], names
    return names[0::2]


def test_set_pair_when_selected_master_then_one_labelled_write_and_master_named():
    studio, _ = session()
    pkg = studio.shell.pkg
    assert studio.set_pair("A", "W", -55)
    assert studio.last_edits == {"Regular": {("A", "W"): -55}}
    assert pkg.values("Regular")[("A", "W")] == -55 and pkg.values("Bold") == {("@A", "@V"): -60}
    assert history_labels(pkg) == ["Kerning Studio: kerning A W"]
    assert studio.shell.statuses[-1] == "Kerning Studio: kerning A W on Regular."


def test_set_pair_when_unkerned_then_class_record_created():
    studio, _ = session()
    assert studio.set_pair("V", "O", 12)
    assert studio.last_edits == {"Regular": {("V", K2 + "O"): 12}}
    assert studio.shell.pkg.values("Regular")[("V", "@O")] == 12


def test_write_when_other_master_chosen_then_written_there_only():
    studio, _ = session()
    pkg = studio.shell.pkg
    preview = studio.preview = Preview()
    studio.choose_master("Bold")
    assert preview.calls == [("set_layer", "Bold")]
    assert studio.set_pair("A", "V", -1)
    assert studio.last_edits == {"Bold": {(K1 + "A", K2 + "V"): -1}}
    assert pkg.values("Bold")[("@A", "@V")] == -1 and pkg.values("Regular")[("@A", "@V")] == -80
    assert studio.shell.statuses[-1] == "Kerning Studio: kerning A V on Bold."


def test_set_grid_when_values_per_master_then_one_undo_step_for_all():
    studio, _ = session()
    pkg = studio.shell.pkg
    assert studio.set_grid("A", "V", {"Regular": -70, "Bold": None})
    assert studio.last_edits == {"Regular": {(K1 + "A", K2 + "V"): -70}, "Bold": {(K1 + "A", K2 + "V"): None}}
    assert pkg.values("Regular")[("@A", "@V")] == -70 and ("@A", "@V") not in pkg.values("Bold")
    assert history_labels(pkg) == ["Kerning Studio: kerning A V"]
    assert studio.shell.statuses[-1] == "Kerning Studio: kerning A V on Regular, Bold."
    assert not studio.set_grid("A", "V", {"Regular": -70, "Bold": None})
    assert studio.shell.statuses[-1] == "Kerning Studio: no change to A V on Regular."


def test_nudge_and_kern_to_max_when_pair_then_values_and_labels():
    studio, _ = session()
    pkg = studio.shell.pkg
    assert studio.nudge("A", "V", 5)
    assert pkg.values("Regular")[("@A", "@V")] == -75
    assert studio.kern_to_max("A", "W")
    assert studio.last_edits == {"Regular": {("A", "W"): -300}}
    assert history_labels(pkg) == ["Kerning Studio: nudge +5 A V", "Kerning Studio: Kern To Max A W"]
    assert not studio.kern_to_max(K1 + "A", "W")
    assert studio.shell.statuses[-1] == "Kerning Studio: Kern To Max needs two glyphs, not groups."


def test_set_pairs_when_out_of_range_then_refused_before_write():
    studio, _ = session()
    assert not studio.set_pair("A", "V", 5000)
    assert "exceeds FontLab’s save/reopen range" in studio.shell.statuses[-1]
    assert studio.shell.pkg.history == []


def test_write_when_other_master_has_extreme_value_then_changed_master_still_written():
    pkg = package()
    pkg.kerns["Bold"].values[("A", "W")] = -2500  # untouched master outside ±2×UPM
    studio, _ = session(pkg=pkg)
    assert studio.set_pair("A", "W", -50)
    assert pkg.values("Regular")[("A", "W")] == -50


def test_delete_when_class_pair_then_every_master_in_one_undo_step():
    studio, _ = session()
    pkg = studio.shell.pkg
    assert studio.delete([("A", "W")])
    key = (K1 + "A", K2 + "V")
    assert studio.last_edits == {"Regular": {key: None}, "Bold": {key: None}}
    assert ("@A", "@V") not in pkg.values("Regular") and ("@A", "@V") not in pkg.values("Bold")
    assert pkg.values("Regular")[("A", "W")] == -40
    assert history_labels(pkg) == ["Kerning Studio: delete A W"]
    status = studio.shell.statuses[-1]
    assert status.startswith("Kerning Studio: delete A W on Regular, Bold.")
    assert "Exceptions kept: Regular: A W = -40." in status


def test_delete_when_nothing_to_delete_then_status_and_no_write():
    studio, _ = session()
    assert not studio.delete([("V", "A")])
    assert studio.shell.statuses[-1] == "Kerning Studio: No kerning to delete for V A."
    assert studio.shell.pkg.history == []


def test_write_when_no_font_then_status():
    from fontlabapp.studios.kerning_studio.session import Studio

    studio = Studio(Shell(package()), font=lambda: None)
    assert not studio.set_pair("A", "V", 1)
    assert studio.shell.statuses == ["Open a font first."]
    with pytest.raises(ValueError, match="Open a font"):
        studio.steal(["A", "V", "A", "V"], 1)


def test_steal_when_pairs_measured_then_value_written_or_deleted():
    studio, fnt = session()
    value, gap1, gap2 = studio.steal(["A", "W", "A", "V"], 350)
    assert (gap1, gap2) == (300.0, 300.0) and value == -80
    assert studio.apply_steal(["A", "W", "A", "V"], 350)
    assert studio.last_edits == {"Regular": {("A", "W"): -80}}
    assert history_labels(studio.shell.pkg)[-1] == "Kerning Studio: Steal Kerning A W"
    assert studio.apply_steal(["V", "O", "V", "O"], 350) is False  # no record, 0 -> nothing to delete
    assert studio.shell.statuses[-1] == "Kerning Studio: no change to V O on Regular."


def test_steal_when_bad_input_then_clear_status():
    studio, _ = session()
    assert not studio.apply_steal(["A", "V"], 10)
    assert studio.shell.statuses[-1] == "Kerning Studio: Enter four glyph names: the pair to change, then the reference pair."
    assert not studio.apply_steal(["A", "V", "A", "Zed"], 10)
    assert studio.shell.statuses[-1] == "Kerning Studio: Glyph Zed is not in the font."


def test_steal_when_value_nonzero_out_of_range_then_refused():
    studio, _ = session()
    studio.shell.pkg.upm = 10
    assert not studio.apply_steal(["A", "W", "A", "V"], 350)
    assert "exceeds" in studio.shell.statuses[-1]


def test_cmap_and_order_when_font_then_unicode_map_and_glyph_order():
    studio, fnt = session()
    assert studio.cmap(fnt)[65] == "A"
    del fnt.glyphOrder
    assert studio.order(fnt)[0] == "A"


# Tabs on offscreen Qt ---------------------------------------------------------
@pytest.fixture
def ks(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, TABS, raising=False)
    studios = importlib.import_module("fontlabapp.studios.kerning_studio")
    from PySide6.QtWidgets import QWidget

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def set_text(self, *args):
            self.calls.append(("set_text", *args))

        def set_layer(self, *args):
            self.calls.append(("set_layer", *args))

        def highlight_pair(self, *args):
            self.calls.append(("highlight_pair", *args))

    pkg, fnt, preview = package(), font(), QtPreview()
    pkg.live = fnt
    shell = studios.show(package=lambda: pkg, font=lambda: fnt, preview=lambda shell, studio: preview)
    studio_qt.owned.append(shell)
    yield SimpleNamespace(shell=shell, studio=shell.kerning_studio, pkg=pkg, font=fnt, preview=preview,
                          tabs=sys.modules[TABS], qt=studio_qt)
    sys.modules.pop(TABS, None)


def tab(ks, index):
    return next(t for t in _tabs(ks) if isinstance(t, ks.tabs.TAB_CLASSES[index][1]))


def _tabs(ks):
    return [view.__self__ for view in ks.studio.views]


def test_show_when_opened_then_four_tabs_preview_and_current_master(ks):
    assert [ks.shell.tabs.tabText(i) for i in range(ks.shell.tabs.count())] == ["Text pairs", "Glyph pairs", "Groups", "Tighten", "About"]
    assert ks.shell.preview is ks.preview and ("set_layer", "Regular") in ks.preview.calls
    text = tab(ks, 0)
    assert text.write_note.text() == "Writes go to the selected master: Regular."
    assert [text.master_box.itemText(i) for i in range(text.master_box.count())] == ["Regular", "Bold"]


def test_text_tab_when_text_shown_then_pairs_per_master_and_selection_previews(ks):
    text = tab(ks, 0)
    text.text_field.setText("AW VA")
    text.show_text()
    assert ("set_text", "AW VA") in ks.preview.calls
    assert [r.glyph_name for r in text.table.rows] == ["A W", "V A"]
    assert text.table.rows[0].values == (-40, -60, "A W")
    assert text.table.select("A W")
    assert text.value_field.text() == "-40"
    assert ("highlight_pair", "A", "W") in ks.preview.calls
    assert ks.pkg.writes == []


def test_text_tab_when_set_value_nudge_and_all_then_labelled_writes(ks):
    text = tab(ks, 0)
    text.show_text("AW AV")
    text.table.select("A W")
    text.value_field.setText("-20")
    assert text.set_value()
    assert ks.pkg.values("Regular")[("A", "W")] == -20
    text.table.select("A V")
    assert text.nudge(-10)
    assert ks.pkg.values("Regular")[("@A", "@V")] == -90
    text.value_field.setText("-30")
    assert text.set_all()
    assert history_labels(ks.pkg)[-1] == "Kerning Studio: kerning A W, A V"
    assert ks.studio.last_edits == {"Regular": {("A", "W"): -30, (K1 + "A", K2 + "V"): -30}}
    assert ks.pkg.values("Regular")[("A", "W")] == -30 and ks.pkg.values("Regular")[("@A", "@V")] == -30
    assert ks.pkg.values("Bold") == {("@A", "@V"): -60}
    assert ks.shell.status.text() == "Kerning Studio: kerning A W, A V on Regular."
    assert text.table.rows[0].values[0] == -30


def test_text_tab_when_no_selection_or_bad_value_then_status(ks):
    text = tab(ks, 0)
    assert not text.set_all() and ks.shell.status.text() == "Kerning Studio: Enter a number for the kerning value."
    text.value_field.setText("5")
    assert not text.set_value() and ks.shell.status.text() == "Kerning Studio: Choose a pair in the list first."
    assert not text.set_all() and ks.shell.status.text() == "Kerning Studio: Type text with at least one pair first."
    text.show_text("AW")
    text.table.select("A W")
    text.value_field.setText("x")
    assert not text.set_value()
    assert ks.pkg.history == []


def test_text_tab_when_kern_to_max_and_delete_then_written(ks):
    text = tab(ks, 0)
    text.show_text("AW")
    text.table.select("A W")
    assert text.kern_to_max() and ks.pkg.values("Regular")[("A", "W")] == -300
    assert text.delete()  # class record @A @V on every master, as the original script; A W kept
    assert ks.shell.status.text() == (
        "Kerning Studio: delete A W on Regular, Bold. Exceptions kept: Regular: A W = -300."
    )
    assert ks.pkg.values("Regular") == {("A", "W"): -300} and ks.pkg.values("Bold") == {}
    assert history_labels(ks.pkg)[-1] == "Kerning Studio: delete A W"
    assert ks.studio.last_edits == {
        "Regular": {(K1 + "A", K2 + "V"): None}, "Bold": {(K1 + "A", K2 + "V"): None}
    }


def test_text_tab_when_preview_master_changed_then_layer_and_write_target_follow(ks):
    text = tab(ks, 0)
    text.show_text("AV")
    text.master_box.setCurrentIndex(1)
    assert ks.studio.master == "Bold" and ("set_layer", "Bold") in ks.preview.calls
    text.table.select("A V")
    assert text.value_field.text() == "-60"
    assert text.write_note.text() == "Writes go to the selected master: Bold."
    assert text.nudge(1)
    assert ks.pkg.values("Bold")[("@A", "@V")] == -59 and ks.pkg.values("Regular")[("@A", "@V")] == -80
    assert ks.studio.last_edits == {"Bold": {(K1 + "A", K2 + "V"): -59}}
    assert ks.shell.status.text() == "Kerning Studio: nudge +1 A V on Bold."


def test_text_tab_when_masters_change_then_table_rebuilt(ks):
    text = tab(ks, 0)
    old = text.table
    ks.pkg.kerns.pop("Bold")
    ks.studio.reload()
    assert text.table is not old and text.columns == ("Pair", "Regular", "Record")


def test_glyph_tab_when_glyph_shown_then_records_per_master(ks):
    glyph = tab(ks, 1)
    glyph.glyph_field.setText("W")
    glyph.show_glyph()
    assert [r.glyph_name for r in glyph.table.rows] == ["@A @V", "A W"]
    assert glyph.table.rows[1].values == (-40, "", "A W")
    assert glyph.table.select("A W")
    assert ("set_text", "/A/W") in ks.preview.calls
    assert glyph.table.select("@A @V")
    glyph.value_field.setText("-70")
    assert glyph.set_value()
    assert ks.pkg.values("Regular")[("@A", "@V")] == -70


def test_glyph_tab_when_ambiguous_groups_then_status(ks):
    ks.pkg.kerns["Regular"].groups["B"] = (["A"], "KernLeft")
    ks.studio.reload()
    glyph = tab(ks, 1)
    glyph.show_glyph("A")
    assert glyph.table.rows == []
    assert ks.shell.status.text() == "Kerning Studio: Glyph A has multiple kerning groups on one side."


def test_groups_tab_when_glyph_shown_then_read_only_peers(ks):
    groups = tab(ks, 2)
    groups.glyph_field.setText("W")
    groups.show_glyph()
    assert [(r.glyph_name, r.values) for r in groups.table.rows] == [("W L", ("L", "@V", "V"))]
    assert ks.shell.status.text() == "Kerning Studio: W shares kerning groups on Regular (read-only)."
    assert groups.table.select("W L")
    assert ("set_text", "/W/V") in ks.preview.calls
    groups.show_glyph("O")
    assert ks.shell.status.text().startswith("No Kerning Groups:")
    ks.pkg.kerns["Regular"].groups["B"] = (["A"], "KernLeft")
    ks.studio.reload()
    groups.show_glyph("A")
    assert ks.shell.status.text().startswith("Ambiguous Kerning Groups:")
    assert ks.pkg.writes == [] and ks.pkg.history == []


def test_tighten_tab_when_measured_and_applied_then_status_and_write(ks):
    tighten = tab(ks, 3)
    assert tighten.height() == 250
    tighten.glyphs_field.setText("A W /A/V")
    assert tighten.measure() == (-80, pytest.approx(1500 / 7), pytest.approx(1500 / 7))
    assert ks.shell.status.text() == "Unkerned gaps: 214.286 and 214.286 units; matched kerning -80."
    assert tighten.apply()
    assert ks.pkg.values("Regular")[("A", "W")] == -80
    assert history_labels(ks.pkg) == ["Kerning Studio: Steal Kerning A W"]
    tighten.glyphs_field.setText("A W")
    assert tighten.measure() is None
    assert len(ks.pkg.history) == 2


def test_read_paths_when_driven_then_no_history_or_kerning_writes(ks):
    text, glyph, groups = tab(ks, 0), tab(ks, 1), tab(ks, 2)
    text.show_text("AVAW")
    text.table.select("A V")
    glyph.show_glyph("A")
    groups.show_glyph("A")
    tab(ks, 3).glyphs_field.setText("A W A V")
    tab(ks, 3).measure()
    assert ks.pkg.writes == [] and ks.font.kerning.undo_names == []


def test_show_when_no_font_then_no_preview_and_status(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, TABS, raising=False)
    studios = importlib.import_module("fontlabapp.studios.kerning_studio")
    shell = studios.show(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    assert shell.preview is None and shell.status.text() == "Open a font first."
    assert tab(SimpleNamespace(studio=shell.kerning_studio, tabs=sys.modules[TABS]), 0).rows() == []
    sys.modules.pop(TABS, None)


def test_show_when_default_preview_then_metrics_preview_called(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios.kerning_studio.app as studios

    calls = []
    monkeypatch.setattr(fontui, "metrics_preview", lambda *a, **k: calls.append((a, k)) or "preview")
    shell = SimpleNamespace(widget="w", hint_check="check")
    studio = SimpleNamespace(font=lambda: "font")
    assert studios._metrics_preview(shell, studio) == "preview"
    assert calls == [(("font", "w"), {"controls": False, "hint_check": "check", "read_only": True})]
    assert studios._metrics_preview(shell, SimpleNamespace(font=lambda: None)) is None


def test_show_when_build_fails_then_shell_closed(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios.kerning_studio as studios

    import fontlabapp.studios.kerning_studio.app  # noqa: F401 - bind fontui before patching
    closed = []
    fake = SimpleNamespace(close=lambda: closed.append(True), hint_check=None, widget=None)
    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: fake)

    def boom(shell, studio):
        raise RuntimeError("no preview")

    with pytest.raises(RuntimeError, match="no preview"):
        studios.show(package=lambda: None, font=lambda: None, preview=boom)
    assert closed == [True]


def test_registry_when_imported_then_four_lazy_tabs_and_studio_shared():
    from fontlabapp import studios
    import fontlabapp.studios.kerning_studio as ks_mod

    assert [spec.title for spec in studios.tabs(ks_mod.APP)][:4] == list(ks_mod.TAB_TITLES)
    shell = SimpleNamespace()
    assert ks_mod.studio_for(shell) is ks_mod.studio_for(shell)


# fontui exports added for the studio ----------------------------------------
def test_fontui_current_font_and_metrics_preview_when_called_then_tmetrics_used(monkeypatch):
    from fontlabapp import fontui

    made = []

    class TMetrics:
        def __init__(self, *args, **kwargs):
            made.append((args, kwargs))

    class Broken(TMetrics):
        def __init__(self, *args, **kwargs):
            self.widget = "w"
            raise RuntimeError("no qt")

        def close(self):
            made.append("closed")

    fake = SimpleNamespace(_current_font=lambda: "font", TMetrics=TMetrics)
    monkeypatch.setattr(fontui, "_load", lambda name: fake)
    assert fontui.current_font() == "font"
    assert isinstance(fontui.metrics_preview("f", "p", hint_check="h"), TMetrics)
    assert made[0] == (("f", "p", None, None), {"controls": False, "layer": None, "label_prefix": "TMetrics", "hint_check": "h",
                       "read_only": False})
    fake.TMetrics = Broken
    with pytest.raises(RuntimeError, match="no qt"):
        fontui.metrics_preview("f")
    assert made[-1] == "closed"


def test_fontui_kerning_wrappers_when_called_then_batch_snapshot_and_write():
    from fontlabapp import fontui

    pkg = package()
    snap = fontui.kerning_snapshot(pkg)
    assert snap.masters == ("Regular", "Bold") and snap.pairs["Bold"] == {("@A", "@V"): -60}
    assert fontui.write_kerning(pkg, {"Bold": {("@A", "@V"): None}, "Regular": {("A", "W"): -1}}, "x", expected=snap)
    assert pkg.values("Bold") == {} and pkg.values("Regular")[("A", "W")] == -1.0 and history_labels(pkg) == ["x"]
    assert fontui.write_kerning(pkg, {"Regular": {("A", "W"): -1}}, "y") is False
    with pytest.raises(ValueError, match="stale"):
        fontui.write_kerning(pkg, {"Regular": {("A", "W"): -2}}, "z", expected=snap)


def test_pair_tab_grid_when_cells_edited_then_each_master_written_in_one_undo_step(ks):
    text = tab(ks, 0)
    text.show_text("AV")
    text.table.select("A V")
    assert text.grid["Regular"].text() == "-80" and text.grid["Bold"].text() == "-60"
    text.grid["Regular"].setText("-90")
    text.grid["Bold"].setText("")
    assert text.set_grid()
    assert ks.pkg.values("Regular")[("@A", "@V")] == -90 and ks.pkg.values("Bold") == {}
    assert history_labels(ks.pkg) == ["Kerning Studio: kerning A V"]
    assert ks.studio.last_edits == {"Regular": {(K1 + "A", K2 + "V"): -90}, "Bold": {(K1 + "A", K2 + "V"): None}}
    text.grid["Bold"].setText("x")
    assert not text.set_grid()
    assert ks.shell.status.text() == "Kerning Studio: Enter a number or leave blank for Bold."
    text.selected = None
    assert not text.set_grid()


def test_glyph_when_other_master_then_layer_read_or_refused(ks):
    assert ks.studio.glyph("Bold", "A") is not None
    ks.font.getLayer = lambda name: (_ for _ in ()).throw(KeyError(name))
    with pytest.raises(ValueError, match="Cannot read glyphs of Bold"):
        ks.studio.glyph("Bold", "A")


@pytest.fixture
def history_actions(monkeypatch):
    """Native action doubles use the shell's real Owned connection lifecycle."""
    class Signal:
        def __init__(self):
            self.slots = []
            self.refuse_disconnect = False

        def connect(self, slot):
            self.slots.append(slot)

        def disconnect(self, slot):
            if self.refuse_disconnect:
                return False
            self.slots.remove(slot)

        def emit(self):
            for slot in tuple(self.slots):
                slot()

    actions = {name: SimpleNamespace(triggered=Signal()) for name in ("actionUndo", "actionRedo")}
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(
        MainWindow=lambda: SimpleNamespace(findChild=lambda kind, name: actions.get(name))))
    return actions


def open_history_studio(studio_qt, monkeypatch, *, consolidated=False):
    from fontlabapp.studios.kerning_studio.app import show
    from fontlabapp.studios.kerning_studio import pairs

    monkeypatch.setattr(pairs, "current_glyph_name", lambda package: "A")
    pkg, fnt = package(), font()
    current = [pkg]
    shell = show(package=lambda: current[0], font=lambda: fnt, preview=lambda *args: None,
                 consolidated=consolidated)
    studio_qt.owned.append(shell)
    return shell, pkg, current


@pytest.mark.parametrize("consolidated", [False, True])
def test_history_when_pairs_change_then_cache_tables_and_drafts_follow(studio_qt, monkeypatch, history_actions, consolidated):  # noqa: F811
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=consolidated)
    studio = shell.kerning_studio
    panel = next(v.__self__ for v in studio.views if type(v.__self__).__name__ == "GlyphPairsTab")
    panel.show_glyph("A")
    panel.table.select("A W")
    panel.value_field.setText("-123.")
    panel.grid["Bold"].setText("17.")
    studio.choose_master("Bold")
    pkg.master = "Regular"
    for action, value in (("actionUndo", -11), ("actionRedo", -22)):
        pkg.values("Regular")[("A", "W")] = value
        history_actions[action].triggered.emit()
        assert studio.value("Regular", "A", "W")[0] == value
        assert next(row for row in panel.table.rows if row.glyph_name == "A W").values[0] == value
        assert studio.master == "Bold"
        assert panel.value_field.text() == "-123." and panel.grid["Bold"].text() == "17."
        if consolidated:
            assert shell.kerning_tool.current == "Bold"
            editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
            assert editor.rows[("A", "W")]["Regular"] == value
    assert pkg.writes == [] and pkg.history == []


def test_history_when_staged_then_plan_invalidated_and_pair_drafts_reaccepted(studio_qt, monkeypatch, history_actions):  # noqa: F811
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    studio = shell.kerning_studio
    panel = next(v.__self__ for v in studio.views if type(v.__self__).__name__ == "GlyphPairsTab")
    panel.show_glyph("A")
    panel.table.select("A W")
    panel.value_field.setText("-77")
    assert panel.set_value() and studio.ready()
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    editor.set_cell("A", "W", "Regular", "-91")
    old_drafts = dict(editor.staged)
    pkg.values("Regular")[("A", "W")] = -15
    history_actions["actionUndo"].triggered.emit()
    assert studio.accepted is None and not studio.ready()
    assert panel.value_field.text() == "-77"
    assert editor.staged == old_drafts and not editor.ready()
    shell._actions[editor.widget]["preview"]()
    assert editor.ready() and editor.staged == old_drafts
    assert editor.snapshot == studio.snapshot
    assert pkg.writes == []


@pytest.mark.parametrize("problem", ["switched", "closed", "master"])
def test_history_when_target_lost_then_refuses_without_erasing_drafts(studio_qt, monkeypatch, history_actions, problem):  # noqa: F811
    shell, pkg, current = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    studio = shell.kerning_studio
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    editor.set_cell("A", "W", "Regular", "-99")
    before = dict(editor.staged)
    if problem == "switched":
        current[0] = object()
    elif problem == "closed":
        pkg.isNull = True
    else:
        pkg.kerns.pop("Regular")
    history_actions["actionUndo"].triggered.emit()
    assert studio.snapshot is None and not editor.ready()
    assert editor.staged == before
    assert "reopen" in shell.status.text().lower() or "master" in shell.status.text().lower()
    assert pkg.writes == []


def test_history_when_close_retried_then_late_callback_ignored_and_reopen_single(studio_qt, monkeypatch, history_actions):  # noqa: F811
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch)
    signal = history_actions["actionRedo"].triggered
    late = signal.slots[0]
    old = shell.kerning_studio.snapshot
    signal.refuse_disconnect = True
    with pytest.raises(RuntimeError, match="disconnect"):
        shell.close()
    pkg.values("Regular")[("A", "W")] = -12
    late()
    assert shell.kerning_studio.snapshot is old
    signal.refuse_disconnect = False
    shell.close()
    assert all(not action.triggered.slots for action in history_actions.values())
    second, _, _ = open_history_studio(studio_qt, monkeypatch)
    assert all(len(action.triggered.slots) == 1 for action in history_actions.values())
    second.close()


def test_history_when_cell_editor_is_active_then_keeps_uncommitted_text(studio_qt, monkeypatch, history_actions):  # noqa: F811
    from PythonQt import QtGui

    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    row = next(n for n in range(editor.table.rowCount()) if tuple(editor.table.item(n, 0).data(studio_qt.QtCore.Qt.UserRole)) == ("A", "W"))
    item = editor.table.item(row, 1)
    shell.tabs.setCurrentWidget(editor.widget)
    editor.table.setCurrentItem(item)
    editor.table.editItem(item)
    line = editor.table.findChild(QtGui.QLineEdit)
    assert line is not None
    line.setText("-181.")
    assert not editor.staged
    pkg.values("Regular")[("A", "W")] = -19
    history_actions["actionUndo"].triggered.emit()
    assert line.text() == "-181." and not editor.ready()
    assert editor.table.findChild(QtGui.QLineEdit) is line
    shell._actions[editor.widget]["preview"]()
    assert editor.staged[(("A", "W"), "Regular")] == -181
    assert editor.ready() and pkg.writes == []


def test_history_when_callback_fails_then_visible_refusal_and_manual_retry(studio_qt, monkeypatch, history_actions):  # noqa: F811
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch)
    studio = shell.kerning_studio
    original = studio.views[0]
    rows = original.__self__.rows
    def broken():
        raise RuntimeError("table refresh failed")
    # Use the real tab receiver to preserve the callback's ordinary shape.
    monkeypatch.setattr(original.__self__, "rows", broken)
    pkg.values("Regular")[("A", "W")] = -10
    history_actions["actionUndo"].triggered.emit()
    assert studio.snapshot is None and "table refresh failed" in shell.status.text()
    monkeypatch.setattr(original.__self__, "rows", rows)
    shell._run_action("refresh")
    assert studio.snapshot is not None and studio.value("Regular", "A", "W")[0] == -10
    assert pkg.writes == []


def test_history_when_unavailable_or_connection_refused_then_manual_refresh_works(studio_qt, monkeypatch, history_actions):  # noqa: F811
    history_actions["actionRedo"].triggered.connect = lambda slot: False
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch)
    assert shell._history_connections == 1
    assert "use Refresh" in shell.status.text()
    pkg.values("Regular")[("A", "W")] = -21
    shell._run_action("refresh")
    assert shell.kerning_studio.value("Regular", "A", "W")[0] == -21
    shell.close()
    monkeypatch.delitem(sys.modules, "fontlab")
    second, _, _ = open_history_studio(studio_qt, monkeypatch)
    assert second._history_connections == 0 and "use Refresh" in second.about.text()


def test_history_when_secondary_view_fails_then_keeps_refusal_visible(studio_qt, monkeypatch, history_actions):  # noqa: F811
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    panel = shell.kerning_tool.views[-1].__self__
    monkeypatch.setattr(panel, "refresh", lambda: (_ for _ in ()).throw(RuntimeError("secondary view failed")))
    history_actions["actionUndo"].triggered.emit()
    assert shell.kerning_studio.snapshot is None and shell.kerning_tool.package is None
    assert "secondary view failed" in shell.status.text()
    assert pkg.writes == []


def pair_cell_editor(shell, editor, qt, pair, master, text):
    from PythonQt import QtGui

    shell.tabs.setCurrentWidget(editor.widget)
    row = next(n for n in range(editor.table.rowCount())
               if tuple(editor.table.item(n, 0).data(qt.QtCore.Qt.UserRole)) == pair)
    column = next(n for n in range(1, editor.table.columnCount())
                  if editor.table.horizontalHeaderItem(n).text() == master)
    item = editor.table.item(row, column)
    editor.table.setCurrentItem(item)
    editor.table.editItem(item)
    line = editor.table.findChild(QtGui.QLineEdit)
    assert line is not None
    line.setText(text)
    return line, item


@pytest.mark.parametrize("removed_staged", [False, True])
def test_history_preview_when_native_rows_change_then_rebases_cells_and_pair_identity(studio_qt, monkeypatch, history_actions, removed_staged):  # noqa: F811
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    editor.set_cell("A", "W", "Regular", "-91")
    if removed_staged:
        editor.set_cell("@A", "@V", "Regular", "-95")
    editor.partner.setText("A")
    editor.add_row()
    pkg.values("Regular")[("A", "W")] = -15
    pkg.values("Regular")[("A", "O")] = -7
    for master in pkg.masters:
        pkg.values(master).pop(("@A", "@V"))
    history_actions["actionUndo"].triggered.emit()
    shell.tabs.setCurrentWidget(editor.widget)
    shell._run_action("preview")
    assert editor.rows[("A", "W")]["Regular"] == -15
    assert editor.rows[("A", "O")]["Regular"] == -7
    assert ("A", "A") in editor.rows
    assert (("@A", "@V") in editor.rows) == removed_staged
    if removed_staged:
        assert editor.rows[("@A", "@V")] == {}
        assert editor.staged[(("@A", "@V"), "Regular")] == -95
    editor.set_cell("A", "W", "Regular", "-40")
    assert editor.staged[(("A", "W"), "Regular")] == -40
    assert editor.ready() and pkg.writes == []
    for row in range(editor.table.rowCount()):
        pair = tuple(editor.table.item(row, 0).data(studio_qt.QtCore.Qt.UserRole))
        assert pair in editor.rows
        if pair == ("A", "O"):
            assert editor.table.item(row, 1).text() == "-7"


@pytest.mark.parametrize("problem", ["switched", "closed", "reordered", "removed"])
@pytest.mark.parametrize("commit", ["preview", "focus_loss"])
def test_history_target_refusal_when_editor_active_then_preserves_all_drafts_and_columns(studio_qt, monkeypatch, history_actions, problem, commit):  # noqa: F811
    from PythonQt import QtGui

    shell, pkg, current = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    editor.set_cell("A", "W", "Regular", "-91")
    editor.set_cell("@A", "@V", "Regular", "bad")
    staged, errors = dict(editor.staged), dict(editor.errors)
    line, item = pair_cell_editor(shell, editor, studio_qt, ("@A", "@V"), "Bold", "-172.")
    headers = [editor.table.horizontalHeaderItem(n).text() for n in range(editor.table.columnCount())]
    if problem == "switched":
        current[0] = object()
    elif problem == "closed":
        pkg.isNull = True
    elif problem == "reordered":
        pkg.kerns = dict(reversed(list(pkg.kerns.items())))
    else:
        pkg.kerns.pop("Bold")
    history_actions["actionUndo"].triggered.emit()
    if commit == "preview":
        shell._run_action("preview")
        assert editor.table.findChild(QtGui.QLineEdit) is line
        assert line.text() == "-172."
    else:
        editor.table.commitData(line)
        editor.table.closeEditor(line, QtGui.QAbstractItemDelegate.NoHint)
        assert item.text() == "-172."
    assert [editor.table.horizontalHeaderItem(n).text() for n in range(editor.table.columnCount())] == headers
    assert editor.staged == staged and editor.errors == errors
    assert not editor.ready() and pkg.writes == []
    assert "original font" in shell.status.text() or "master" in shell.status.text() or "closed" in shell.status.text()


@pytest.mark.parametrize("hooks", ["missing", "refused"])
def test_manual_preview_when_staged_and_no_history_callback_then_accepts_fresh_baseline(studio_qt, monkeypatch, history_actions, hooks):  # noqa: F811
    if hooks == "missing":
        history_actions.clear()
    else:
        history_actions["actionRedo"].triggered.connect = lambda slot: False
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    editor.set_cell("A", "W", "Regular", "-91")
    staged = dict(editor.staged)
    old_snapshot = editor.snapshot
    pkg.values("Regular")[("A", "W")] = -15
    assert not editor.history_stale
    shell.tabs.setCurrentWidget(editor.widget)
    shell._run_action("refresh")
    assert editor.staged == staged and "discard" in shell.status.text()
    shell._run_action("preview")
    assert editor.snapshot != old_snapshot and editor.snapshot.pairs["Regular"][("A", "W")] == -15
    assert editor.rows[("A", "W")]["Regular"] == -15
    assert editor.staged == staged and editor.ready()
    assert pkg.writes == [] and pkg.history == []


def test_pair_callback_when_pending_drafts_then_failure_keeps_cells_and_requires_preview(studio_qt, monkeypatch, history_actions):  # noqa: F811
    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    editor.set_cell("A", "W", "Regular", "-91")
    editor.set_cell("@A", "@V", "Regular", "bad")
    staged, errors = dict(editor.staged), dict(editor.errors)
    editor.contain(lambda: (_ for _ in ()).throw(ValueError("preview target failed")))()
    assert editor.staged == staged and editor.errors == errors and not editor.ready()
    assert "preview target failed" in shell.status.text() and pkg.writes == []


def test_refused_editor_when_target_returns_and_history_repeats_then_table_only_draft_survives(studio_qt, monkeypatch, history_actions):  # noqa: F811
    from PythonQt import QtGui

    shell, pkg, current = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    line, item = pair_cell_editor(shell, editor, studio_qt, ("A", "W"), "Regular", "-172.")
    assert not editor.staged and not editor.errors
    current[0] = object()
    history_actions["actionUndo"].triggered.emit()
    editor.table.commitData(line)
    editor.table.closeEditor(line, QtGui.QAbstractItemDelegate.NoHint)
    assert item.text() == "-172." and editor.history_stale
    current[0] = pkg
    history_actions["actionRedo"].triggered.emit()
    assert item.text() == "-172." and editor.history_stale
    assert not editor.staged and not editor.errors and not editor.ready()
    assert not shell.apply_button.isEnabled() and pkg.writes == []
    shell._run_action("preview")
    assert editor.staged[(("A", "W"), "Regular")] == -172 and editor.ready()


@pytest.mark.parametrize("problem", ["switched", "closed", "reordered", "removed"])
def test_preview_without_hooks_when_target_refused_then_invalidates_ready_before_reads(studio_qt, monkeypatch, history_actions, problem):  # noqa: F811
    history_actions.clear()
    shell, pkg, current = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    shell.tabs.setCurrentWidget(editor.widget)
    editor.set_cell("A", "W", "Regular", "-91")
    staged, errors = dict(editor.staged), dict(editor.errors)
    assert editor.ready() and shell.apply_button.isEnabled()
    before = [[editor.table.item(r, c).text() for c in range(editor.table.columnCount())]
              for r in range(editor.table.rowCount())]
    if problem == "switched":
        current[0] = object()
    elif problem == "closed":
        pkg.isNull = True
    elif problem == "reordered":
        pkg.kerns = dict(reversed(list(pkg.kerns.items())))
    else:
        pkg.kerns.pop("Bold")
    shell._run_action("preview")
    assert editor.staged == staged and editor.errors == errors
    assert [[editor.table.item(r, c).text() for c in range(editor.table.columnCount())]
            for r in range(editor.table.rowCount())] == before
    assert not editor.ready() and not shell.apply_button.isEnabled()
    assert pkg.writes == [] and pkg.history == []


def test_history_when_pair_read_fails_after_partial_draft_then_apply_stays_disabled(studio_qt, monkeypatch, history_actions):  # noqa: F811
    from fontlabapp.studios.kerning_studio import pairs

    shell, pkg, _ = open_history_studio(studio_qt, monkeypatch, consolidated=True)
    editor = next(v.__self__ for v in shell.kerning_tool.views if type(v.__self__).__name__ == "PairEditorPanel")
    shell.tabs.setCurrentWidget(editor.widget)
    def fail(*args):
        editor.staged[(("A", "W"), "Regular")] = -91
        raise RuntimeError("partial pair read failed")
    monkeypatch.setattr(pairs.model, "involving", fail)
    history_actions["actionUndo"].triggered.emit()
    assert editor.staged == {(("A", "W"), "Regular"): -91} and not editor.ready()
    assert not shell.apply_button.isEnabled() and "partial pair read failed" in shell.status.text()
    assert pkg.writes == [] and pkg.history == []
