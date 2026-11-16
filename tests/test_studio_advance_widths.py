# this_file: tests/test_studio_advance_widths.py
"""Advance Widths (A11): parity with the 7 Scriptmix scripts, dry runs and the one labelled Undo step.

Each write test checks the single ``AppShell.history`` call (label and the
(glyph, master) layers); read-only tabs are checked to leave history and the
layers untouched. Planners are compared with the Scriptmix originals by AST.
"""

from _demo_support import stub_natives

import ast
import importlib
import sys
from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture
from _widths_anchors_originals import ORIGINALS


def _forget_studio_children():
    """Drop loaded studio children and their package attributes (``from .. import x`` reuses those)."""
    import fontlabapp.studios as studios

    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)
        studios.__dict__.pop(name.split(".")[2], None)


@pytest.fixture(autouse=True)
def fresh_studios():
    _forget_studio_children()
    yield
    _forget_studio_children()


class Box:
    def __init__(self, left, right):
        self.left, self.right = left, right

    def x(self):
        return self.left

    def width(self):
        return self.right - self.left

    def height(self):
        return 0 if self.right == self.left else 700


class Layer:
    def __init__(self, log, glyph, master, left, right, width, *, auto=False, link=""):
        d = object.__setattr__
        d(self, "log", log)
        d(self, "glyph", glyph)
        d(self, "master", master)
        d(self, "left", left)
        d(self, "right", right)
        d(self, "advanceWidth", width)
        d(self, "autoLayer", auto)
        d(self, "isNull", False)
        d(self, "metricsLeft", link)
        d(self, "metricsRight", "")
        d(self, "metricsWidth", "")
        d(self, "shapes", [])
        d(self, "anchors", [])

    @property
    def boundingBox(self):  # noqa: N802 - native API
        return Box(self.left, self.right)

    def applyTransform(self, transform):  # noqa: N802 - native API
        dx = transform.dx()
        self.log.append(("shift", self.glyph, self.master, dx))
        object.__setattr__(self, "left", self.left + dx)
        object.__setattr__(self, "right", self.right + dx)

    def changed(self):
        pass

    def update(self):
        return True

    def __setattr__(self, name, value):
        self.log.append(("set", self.glyph, self.master, name, value))
        object.__setattr__(self, name, value)


class Glyph:
    def __init__(self, name, layers):
        self.name, self.isNull = name, False  # flGlyph has no Unicode binding: it lives on fgPackage
        self._layers = {layer.master: layer for layer in layers}

    @property
    def layers(self):
        return list(self._layers.values())

    def findLayer(self, master):  # noqa: N802 - native API
        return self._layers.get(master)


class Package:
    def __init__(self, masters=("Regular", "Bold"), current="Regular"):
        self.log, self.masters, self.master, self.glyphs, self.id = [], list(masters), current, {}, 7
        self.axes = []
        self.fg, self.no_fontgate = {}, set()

    @property
    def fgPackage(self):  # noqa: N802 - native API
        return self

    def __getitem__(self, name):
        return self.fg.get(name)

    def add(self, name, metrics, unicodes=(), **kwargs):
        """``metrics``: master -> (left ink edge, right ink edge, advance)."""
        layers = [Layer(self.log, name, m, *v, **kwargs) for m, v in metrics.items()]
        self.glyphs[name] = Glyph(name, layers)
        if name not in self.no_fontgate:
            self.fg[name] = SimpleNamespace(unicodes=list(unicodes))
        return self.glyphs[name]

    def findName(self, name):  # noqa: N802 - native API
        return self.glyphs.get(name)


def package():
    pkg = Package()
    pkg.add("H", {"Regular": (50, 550, 603), "Bold": (60, 640, 707)})
    pkg.add("O", {"Regular": (40, 560, 600), "Bold": (45, 655, 698)})
    pkg.add("zero", {"Regular": (30, 470, 500), "Bold": (30, 500, 560)}, (0x30,))
    pkg.add("one", {"Regular": (100, 400, 480), "Bold": (100, 420, 540)}, (0x31,))
    pkg.add("acutecomb", {"Regular": (-120, -20, 0), "Bold": (-130, -20, 0)}, (0x301,))
    pkg.add("gravecmb", {"Regular": (20, 120, 140), "Bold": (20, 130, 150)}, (0x300,))
    pkg.add("dieresis", {"Regular": (20, 180, 200), "Bold": (20, 190, 210)}, (0xA8,))
    pkg.add("V", {"Regular": (5, 595, 600), "Bold": (5, 555, 560)})
    return pkg


class Recorder:
    """``AppShell.history`` stand-in: records one call, runs mutate and read-back."""

    def __init__(self, shell, mismatches=None, refuse=None):
        self.shell, self.calls, self.mismatches, self.refuse = shell, [], mismatches, refuse

    def __call__(self, label, glyphs, mutate, *, layers, read_back=None, allow_bases=False):
        self.calls.append((label, [g.name for g in glyphs], [(layer.glyph, layer.master) for layer in layers],
                           allow_bases))  # fmt: skip
        if self.refuse:
            self.shell.set_status(self.refuse)
            return None
        mutate()
        found = read_back() if read_back else []
        self.shell.set_status(f"{label}. ")
        return SimpleNamespace(mismatches=self.mismatches if self.mismatches is not None else found, pending_note="")


def writes(pkg):
    return [e for e in pkg.log if e[0] == "shift" or (e[0] == "set" and e[3] == "advanceWidth")]


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.core.history.glyphs as history

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return lambda *args: self.calls.append((name, *args))

    facts = SimpleNamespace(value=history.auto_facts([]))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts.value)

    def open_app(pkg=None, selection=("H", "O")):
        studio = importlib.import_module("fontlabapp.studios.advance_widths")
        pkg = package() if pkg is None else pkg
        chosen = list(selection)
        _kerning = importlib.import_module("fontlabapp.studios._kerning")  # not the package attribute: may be stale
        monkeypatch.setattr(_kerning, "names_selected_names", lambda: list(chosen))
        preview = QtPreview()
        shell = studio.show(package=lambda: pkg, font=lambda: "font", preview=lambda shell, tool: preview)
        studio_qt.owned.append(shell)
        tool = shell.kerning_tool
        recorder = Recorder(shell)
        shell.history = recorder
        panels = {title: view.__self__ for title, view in zip(studio.TAB_TITLES, tool.views, strict=True)}
        return SimpleNamespace(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio,
                               history=recorder, selection=chosen, facts=facts)  # fmt: skip

    return open_app


def rows(panel, mode=None):
    grid = panel.grids[mode or panel.mode()]
    return [(r.glyph_name, r.layer, tuple(r.values)) for r in grid.rows]


def reselect(app, *names):
    app.selection[:] = names
    app.tool.reload()


# Registry, window, parity ---------------------------------------------------------
def test_show_when_opened_then_five_tabs_preview_and_current_master(opened):
    app = opened()
    assert [app.shell.tabs.tabText(i) for i in range(app.shell.tabs.count())] == \
        ["Table", "Round & scale", "Tabular", "Marks", "Chart", "About"]
    assert app.shell.preview is app.preview and ("set_layer", "Regular") in app.preview.calls
    assert app.tool.app == "Advance Widths" and app.tool.masters == ["Regular", "Bold"]


def test_registry_when_imported_then_lazy_and_shared_tool():
    from fontlabapp import studios
    import fontlabapp.studios.advance_widths as aw

    assert aw.register_tabs() == aw.TAB_TITLES == aw.register_tabs()
    assert [s.title for s in studios.tabs(aw.APP)] == list(aw.TAB_TITLES)
    shell = SimpleNamespace()
    assert aw.tool_for(shell) is aw.tool_for(shell) and aw.tool_for(shell).app == aw.APP
    assert not any(n.endswith(("rounding", "marks", "chart")) for n in sys.modules if n.startswith("fontlabapp.studios."))


def _functions(source, names):
    tree = ast.parse(source)
    return [ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]


@pytest.mark.parametrize("title", ["Round Advances", "Scale Advances", "Tabular Width", "Zero-Width Marks"])
def test_planners_when_compared_then_ast_equal_to_scriptmix(title):
    import inspect

    from fontlabapp.studios.advance_widths import widths

    path, digest, names, source = ORIGINALS[title]
    assert len(digest) == 64 and path.startswith("Scripts/")
    ported = "\n\n".join(inspect.getsource(getattr(widths, n)) for n in names)
    assert _functions(ported, names) == _functions(source, names)


def test_constants_when_compared_then_scriptmix_options_and_defaults():
    from fontlabapp.studios.advance_widths import widths as w

    assert w.STEP_DEFAULT == 10 and (w.STEP_MIN, w.STEP_MAX) == (1, 100)
    assert w.DIRECTIONS == [("Nearest", "nearest"), ("Up", "up"), ("Down", "down")]
    assert w.SOURCES == ["Selected glyphs", "All glyphs in the font"] and w.PERCENT_DEFAULT == 100.0
    assert [t for t, _ in w.SETS] == ["Figures (zero to nine)", "Figures and currency signs", "Selected glyphs"]
    assert w.WIDTH_MODES == [("Widest in set, per master", "widest"), ("Fixed width", "fixed")]
    assert w.FIXED_DEFAULT == 500 and [k for _, k in w.PLACEMENTS] == ["keep", "hang", "centre"]


# Round (Scriptmix TODO:76) ------------------------------------------------------
def test_rounded_when_step_one_then_whole_units_and_steps_two_to_hundred_unchanged():
    from fontlabapp.studios.advance_widths import widths

    assert [widths.rounded(603.5, 1, d) for d in ("nearest", "up", "down")] == [604, 604, 603]
    assert widths.rounded(603.2, 1, "up") == 604 and widths.rounded(603.0, 1, "down") == 603
    for step in (2, 10, 37, 100):
        for width in (0, 1, 603, 707.5, 1050):
            assert widths.rounded(width, step, "nearest") % step == 0
            assert abs(widths.rounded(width, step, "nearest") - width) <= step / 2
    assert widths.rounded(603, 2, "nearest") == 604 and widths.rounded(605, 10, "nearest") == 610
    assert widths.rounded(649, 100, "down") == 600 and widths.rounded(601, 100, "up") == 700


def test_round_tab_when_step_spin_then_range_one_to_hundred_default_ten(opened):
    p = opened().panels["Round & scale"]
    assert (p.step.minimum(), p.step.maximum(), p.step.value()) == (1, 100, 10)
    assert p.percent.isEnabled() is False and p.step.isEnabled()


def test_round_when_step_one_then_dry_run_and_one_labelled_undo(opened):
    app = opened()
    p = app.panels["Round & scale"]
    p.scope.setCurrentIndex(1)
    p.step.setValue(1)
    assert rows(p) == [] and p.count.text() == "Nothing to change"  # whole units already
    object.__setattr__(app.pkg.glyphs["H"].findLayer("Regular"), "advanceWidth", 603.4)
    app.tool.reload()
    assert rows(p) == [("H", "Regular", ("Regular", "603.4", "603", "-0.4"))]
    assert p.count.text() == "1 layer will change" and p.apply_button.isEnabled()
    assert app.history.calls == []
    assert p.apply()
    assert app.history.calls == [("Advance Widths: round advances H", ["H"], [("H", "Regular")], False)]
    assert writes(app.pkg) == [("set", "H", "Regular", "advanceWidth", 603)]


def test_round_when_step_two_to_hundred_then_unchanged_behaviour(opened):
    app = opened()
    p = app.panels["Round & scale"]
    p.scope.setCurrentIndex(1)
    p.step.setValue(2)
    assert [r[:2] for r in rows(p)] == [("H", "Regular"), ("H", "Bold")]
    p.step.setValue(100)
    assert rows(p) == [("H", "Regular", ("Regular", "603", "600", "-3")), ("H", "Bold", ("Bold", "707", "700", "-7")),
                       ("O", "Bold", ("Bold", "698", "700", "+2"))]  # fmt: skip
    assert p.subtitle.text() == "Rounds 4 layers to multiples of 100. Outlines and left sidebearings stay put. (H, O)"
    p.direction.setCurrentIndex(1)  # Up
    assert [r[2][2] for r in rows(p)] == ["700", "800", "700"]  # O Regular is already 600
    assert p.apply()
    label, names, layers, _ = app.history.calls[0]
    assert label == "Advance Widths: round advances 2 glyphs" and names == ["H", "O"]
    assert layers == [("H", "Regular"), ("H", "Bold"), ("O", "Bold")]
    assert len(app.history.calls) == 1 and not [e for e in app.pkg.log if e[0] == "shift"]


def test_round_when_all_glyphs_source_then_font_glyph_list(opened, monkeypatch):
    from fontlabapp.core import scripting

    app = opened(selection=())
    monkeypatch.setattr(scripting, "names_font_glyphs", lambda: [("V", [86]), ("missing", []), ("H", [72])])
    p = app.panels["Round & scale"]
    assert p.subtitle.text() == "Select glyphs in the Font window, then press Refresh."
    p.source.setCurrentIndex(1)
    assert [r[0] for r in rows(p)] == ["H"]  # V is already a multiple of 10 in Regular


# Scale ------------------------------------------------------------------------------
def test_scale_when_percent_then_split_shift_and_one_undo(opened):
    app = opened(selection=("V",))
    p = app.panels["Round & scale"]
    p.action.setCurrentIndex(1)
    assert (p.percent.minimum(), p.percent.maximum(), p.percent.value(), p.percent.suffix()) == (10.0, 400.0, 100.0, " %")
    assert rows(p) == [] and p.count.text() == "Nothing to change" and not p.apply_button.isEnabled()
    p.percent.setValue(110.0)
    assert rows(p, "scale") == [("V", "Regular", ("Regular", "600", "660", "+30"))]
    assert p.subtitle.text() == "Scales the advance of 1 glyph to 110 %. The change is split between both sidebearings. (V)"
    assert p.apply()
    assert app.history.calls[0][:3] == ("Advance Widths: scale advances V", ["V"], [("V", "Regular")])
    assert writes(app.pkg) == [("shift", "V", "Regular", 30), ("set", "V", "Regular", "advanceWidth", 660)]


# Dry run: stale refusal, partly applied, refusal, auto bases ---------------------------
def test_apply_when_layer_changed_after_dry_run_then_refused_press_refresh(opened):
    app = opened()
    p = app.panels["Round & scale"]
    assert p.work
    object.__setattr__(app.pkg.glyphs["H"].findLayer("Regular"), "advanceWidth", 611)
    assert not p.apply()
    assert app.history.calls == [] and writes(app.pkg) == []
    assert app.tool.status == "Advance Widths: Advance widths changed since the dry run; press Refresh."


def test_apply_when_glyph_removed_after_dry_run_then_refused(opened):
    app = opened()
    p = app.panels["Round & scale"]
    del app.pkg.glyphs["O"]
    p.work = p.work + [w for w in p.entries if w.glyph.name == "O"][:1]
    assert not p.apply() and app.history.calls == []


def test_apply_when_read_back_mismatch_then_partly_applied_with_rounding_note(opened):
    app = opened()
    app.history.mismatches = ["H · Regular: advance 603.2, planned 600"]
    p = app.panels["Round & scale"]
    assert p.apply()
    assert app.tool.status == ("Partly applied: Advance Widths: round advances H. "
                               "H · Regular: advance 603.2, planned 600. Check Preferences > Rounding.")


def test_apply_when_shell_refuses_then_status_kept_and_false(opened):
    app = opened()
    app.history.refuse = "Refused: H is open in a Glyph window."
    assert not app.panels["Round & scale"].apply()
    assert app.tool.status == "Refused: H is open in a Glyph window." and writes(app.pkg) == []


def test_auto_bases_when_rebuild_note_then_refused_until_tick_and_reset_for_other_glyphs(opened):
    import fontlabapp.core.history.glyphs as history

    app = opened()
    app.facts.value = history.auto_facts([("Hbar", True, ("H",)), ("H", False, ())])
    app.tool.reload()
    p = app.panels["Round & scale"]
    assert not p.allow.isChecked() and p.allow.isVisibleTo(p.widget)
    assert p.count.text().startswith("Refused. FontLab rebuilds auto glyphs Hbar")
    assert p.count.text().endswith('Tick "Edit bases of auto glyphs anyway" to go on.') and not p.apply_button.isEnabled()
    p.allow.setChecked(True)
    assert p.apply_button.isEnabled() and "1 layer will change" in p.count.text()
    assert p.apply() and app.history.calls[0][3] is True
    reselect(app, "H", "V")
    p.step.setValue(7)
    assert not p.allow.isChecked()  # another glyph set: the tick resets


def test_apply_when_nothing_planned_then_refused_without_history(opened):
    app = opened(selection=())
    p = app.panels["Round & scale"]
    assert not p.apply_button.isEnabled() and not p.apply() and app.history.calls == []
    assert app.tool.status == "Advance Widths: Nothing to change."


def test_survey_when_auto_or_linked_layer_then_listed_as_skipped(opened):
    pkg = package()
    pkg.add("Hlink", {"Regular": (50, 550, 603)}, link="=H")
    pkg.add("Hauto", {"Regular": (50, 550, 603)}, auto=True)
    app = opened(pkg, selection=("Hlink", "Hauto"))
    p = app.panels["Round & scale"]
    assert rows(p) == [("Hlink", "Regular", ("Regular", "metrics link or expression (skipped)", "", "")),
                       ("Hauto", "Regular", ("Regular", "auto layer (skipped)", "", ""))]  # fmt: skip
    assert p.count.text() == "Nothing to change" and not p.apply_button.isEnabled()


# Tabular ----------------------------------------------------------------------------
def test_tabular_when_widest_then_shared_width_centred_and_one_undo(opened):
    app = opened(selection=())
    p = app.panels["Tabular"]
    assert (p.fixed.minimum(), p.fixed.maximum(), p.fixed.value(), p.fixed.isEnabled()) == (1, 5000, 500, False)
    assert rows(p) == [("one", "Regular", ("Regular", "480", "500", "100", "100"))]
    assert p.subtitle.text() == "2 glyphs get one shared width and centred outlines. (zero, one)"  # all planned, as the original
    assert p.apply()
    assert app.history.calls[0][:3] == ("Advance Widths: set tabular width one", ["one"], [("one", "Regular")])
    assert writes(app.pkg) == [("set", "one", "Regular", "advanceWidth", 500)]


def test_tabular_when_fixed_or_selected_or_empty_then_original_rules(opened):
    pkg = Package()
    pkg.add("H", {"Regular": (50, 550, 603), "Bold": (50, 550, 603)})
    app = opened(pkg, selection=("H",))
    p = app.panels["Tabular"]
    assert p.subtitle.text() == "The font has none of these glyphs. Select your figures and use Selected glyphs."
    p.group.setCurrentIndex(2)
    p.width_mode.setCurrentIndex(1)
    assert p.fixed.isEnabled()
    p.fixed.setValue(700)
    assert rows(p) == [("H", "Regular", ("Regular", "603", "700", "50", "100"))]


def test_check_tabular_when_run_then_read_only_report_and_no_history(opened, monkeypatch):
    from fontlabapp.studios.advance_widths import widths

    app = opened()
    tm = widths._backends.tabular
    report = tm.compare((("zero", 500.0), ("one", 480.0)), "12:00:00")
    monkeypatch.setattr(tm, "capture", lambda: report)
    p = app.panels["Tabular"]
    p.check_button.click()
    assert [(r.glyph_name, r.layer, tuple(r.values)) for r in p.checked.rows] == [
        ("zero", None, ("500.0", "✅ same")), ("one", None, ("480.0", "❌ different"))]
    before = list(app.preview.calls)
    p.checked.row_selected.emit("zero", None)
    assert app.preview.calls == before, "Occurrence-only report must not invent a master for activation"
    assert p.summary.text() == ("Tabular width checker @ 12:00:00: 1 glyphs are on same width. "
                                "1 glyphs are on different width.")
    monkeypatch.setattr(tm, "capture", lambda: (_ for _ in ()).throw(ValueError("Select glyph layers before checking tabular widths.")))
    p.check_button.click()
    assert p.summary.text() == "Select glyph layers before checking tabular widths." and p.checked.rows == []
    assert app.history.calls == [] and writes(app.pkg) == []


# Marks -----------------------------------------------------------------------------
def test_marks_when_filter_and_placement_then_original_plans(opened):
    app = opened(selection=("acutecomb", "gravecmb", "dieresis"))
    p = app.panels["Marks"]
    assert p.only_marks.isChecked() and p.only_marks.text() == "Only combining marks (Mn, Me, or name ending in comb)"
    assert rows(p) == [("gravecmb", "Regular", ("Regular", "140", "0", "+0"))]
    p.placement.setCurrentIndex(1)
    assert rows(p) == [("gravecmb", "Regular", ("Regular", "140", "0", "-140"))]
    p.placement.setCurrentIndex(2)
    assert rows(p) == [("acutecomb", "Regular", ("Regular", "0", "0", "+70")),
                       ("gravecmb", "Regular", ("Regular", "140", "0", "-70"))]  # fmt: skip
    p.only_marks.setChecked(False)
    assert "dieresis" in [r[0] for r in rows(p)]
    assert p.apply()
    assert app.history.calls[0][0] == "Advance Widths: zero mark widths 3 glyphs"


def test_marks_when_glyph_has_no_fontgate_entry_then_named_refusal(opened):
    pkg = package()
    pkg.add("ghost", {"Regular": (10, 90, 100)})
    del pkg.fg["ghost"]
    p = opened(pkg=pkg, selection=("ghost",)).panels["Marks"]
    assert "ghost" in p.subtitle.text() and "no FontGate glyph" in p.subtitle.text()


def test_marks_when_unicodes_live_on_fontgate_then_mark_found_without_glyph_attribute(opened):
    app = opened(selection=("gravecmb",))
    assert not hasattr(app.pkg.glyphs["gravecmb"], "unicodes")
    assert [r[0] for r in rows(app.panels["Marks"])] == ["gravecmb"]


def test_marks_when_no_mark_selected_then_original_message(opened):
    p = opened(selection=("H",)).panels["Marks"]
    assert p.subtitle.text() == "The selection has no combining marks. Select marks, or clear the filter."


# Read-only tabs ------------------------------------------------------------------
def test_table_when_refreshed_then_masters_columns_progression_and_no_writes(opened):
    pkg = package()
    pkg.masters.append("Black")
    app = opened(pkg, selection=("H", "V"))
    p = app.panels["Table"]
    assert list(p.grid.columns) == ["Glyph", "Regular", "Bold", "Black", "Progression"]
    assert [(r.glyph_name, r.layer, tuple(r.values)) for r in p.grid.rows] == [
        ("H", "Regular", (603, 707, "–", "rising")), ("V", "Regular", (600, 560, "–", "falling"))]
    assert p.subtitle.text() == "2 glyphs × 3 masters, masters in font order: Regular → Bold → Black"
    assert p.status.text() == "0 of 2 glyphs with a mixed progression" and not p.select_button.isEnabled()
    pkg.masters.remove("Black")
    app.tool.reload()
    assert list(p.grid.columns) == ["Glyph", "Regular", "Bold", "Progression"]
    assert app.history.calls == [] and pkg.log == []


def test_table_when_mixed_then_flag_filter_and_select(opened):
    pkg = package()
    pkg.masters.append("Black")
    pkg.add("W", {"Regular": (0, 0, 600), "Bold": (0, 0, 700), "Black": (0, 0, 650)})
    app = opened(pkg, selection=("H", "W"))
    p = app.panels["Table"]
    assert p.status.text() == "1 of 2 glyphs with a mixed progression"
    p.only_flagged.setChecked(True)
    assert [(r.glyph_name, tuple(r.values)) for r in p.grid.rows] == [("W", (600, 700, 650, "⚠ mixed"))]
    selected = []
    app.tool.select = lambda names: selected.append(list(names)) or len(selected[-1])
    p.select_button.click()
    assert selected == [["W"]] and p.status.text() == "Selected 1 glyph in the Font window"
    p.grid.row_selected.emit("W", "Regular")
    assert ("set_text", "/W") in app.preview.calls
    assert app.history.calls == [] and pkg.log == []


def test_table_when_selected_glyph_vanished_then_original_refusal_not_dropped(opened):
    app = opened(selection=("H", "missing", "V"))
    p = app.panels["Table"]
    assert p.subtitle.text() == "Advance Widths: Selected glyph source changed; reopen this tool."
    assert p.rows == [] and p.grid.rows == [] and not p.select_button.isEnabled()
    assert app.history.calls == []


def _mixed_table(opened):
    pkg = package()
    pkg.masters.append("Black")
    pkg.add("W", {"Regular": (0, 0, 600), "Bold": (0, 0, 700), "Black": (0, 0, 650)})
    app = opened(pkg, selection=("H", "W"))
    selected = []
    app.tool.select = lambda names: selected.append(list(names)) or len(selected[-1])
    return pkg, app, app.panels["Table"], selected


@pytest.mark.parametrize(("change", "message"), [
    (lambda pkg: object.__setattr__(pkg.glyphs["W"].findLayer("Black"), "advanceWidth", 720),
     "Source changed since preview; refresh this tool."),
    (lambda pkg: object.__setattr__(pkg.glyphs["W"].findLayer("Black"), "advanceWidth", 650.4),
     "Source changed since preview; refresh this tool."),
    (lambda pkg: pkg.masters.remove("Black"), "Masters changed since preview; refresh this tool."),
    (lambda pkg: setattr(pkg, "master", "Bold"), "Masters changed since preview; refresh this tool."),
    (lambda pkg: pkg.glyphs.pop("W"), "Selected glyph source changed; reopen this tool."),
])  # fmt: skip
def test_table_when_source_changed_before_select_flagged_then_preflight_refuses_and_clears(opened, change, message):
    pkg, app, p, selected = _mixed_table(opened)
    assert p.select_button.isEnabled()
    change(pkg)
    p.select_button.click()
    assert selected == [] and app.tool.status == f"Advance Widths: {message}"
    assert p.rows == [] and p.grid.rows == [] and not p.select_button.isEnabled()
    assert app.history.calls == []


def test_table_when_not_refreshed_then_select_flagged_preflight_refuses(opened):
    _, app, p, selected = _mixed_table(opened)
    p.source = None
    p.run(p.select_flagged)
    assert selected == [] and app.tool.status == "Advance Widths: Results are incomplete; refresh or reopen this tool."


def test_table_when_unchanged_then_select_flagged_preflight_passes(opened):
    _, app, p, selected = _mixed_table(opened)
    p.select_button.click()
    p.select_button.click()
    assert selected == [["W"], ["W"]] and p.status.text() == "Selected 1 glyph in the Font window"


def test_chart_when_refreshed_then_series_capped_and_no_writes(opened):
    pkg = package()
    for i in range(13):
        pkg.add(f"g{i}", {"Regular": (0, 10, 100 + i), "Bold": (0, 10, 200 + i)})
    app = opened(pkg, selection=[f"g{i}" for i in range(13)])
    p = app.panels["Chart"]
    assert p.chart.masters == ["Regular", "Bold"] and len(p.chart.series) == 12
    assert p.chart.series[0] == ("g0", [100.0, 200.0])
    assert p.status.text() == "Advance widths across 2 masters · first 12 glyphs shown"
    reselect(app, "H")
    assert p.status.text() == "Advance widths across 2 masters" and p.subtitle.text() == "1 glyph"
    reselect(app)
    assert p.chart.series == [] and p.subtitle.text() == "Select glyphs in the Font window, then press Refresh."
    assert app.history.calls == [] and pkg.log == []


# Containment and no font --------------------------------------------------------
FAILURE = "The original font is no longer current; reopen this tool."


def test_refresh_when_one_tab_read_fails_then_contained_and_other_tabs_refreshed(opened, monkeypatch):
    from fontlabapp.studios.advance_widths import widths

    app = opened()
    monkeypatch.setattr(widths, "width_report", lambda *a: (_ for _ in ()).throw(RuntimeError(FAILURE)))
    app.tool.reload()
    p = app.panels
    assert p["Table"].subtitle.text() == f"Advance Widths: {FAILURE}" and p["Table"].rows == []
    assert p["Round & scale"].work and p["Chart"].chart.series  # later tabs still refreshed
    monkeypatch.setattr(widths, "survey", lambda *a: (_ for _ in ()).throw(KeyError("x")))
    app.tool.reload()
    assert p["Round & scale"].work == [] and not p["Round & scale"].apply_button.isEnabled()
    assert p["Tabular"].subtitle.text() == "Advance Widths: 'x'" and p["Chart"].chart.series


def test_show_when_no_font_then_every_tab_says_open_a_font(studio_qt):  # noqa: F811
    import fontlabapp.studios.advance_widths as aw

    shell = aw.show(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    tool = shell.kerning_tool
    assert tool.preview is None and tool.package is None
    for view in tool.views:
        assert view.__self__.subtitle.text() == "Open a font first."
    assert not tool.views[1].__self__.apply_button.isEnabled()


def test_facade_when_called_then_backend_namespaces():
    from fontlabapp.core import scripting

    a, b = scripting.advance_widths_backends(), scripting.anchor_transfer_backends()
    assert a.panel.__name__ == "fontlabapp.metrics.panel.model" and a.tabular.capture
    assert a.inspectors.report and a.masters.master_order and a.history.scan_auto_facts
    assert b.writer.prepare and b.copy.plan and b.crossfont.native.Backend and b.crossfont.capture.read
    assert b.crossfont.transaction.publish and b.catalog and b.history.auto_facts


def test_demo_when_run_then_opens_or_reports_error(monkeypatch):
    import runpy
    from pathlib import Path

    import fontlabapp.qt.dialogs as dialogs
    import fontlabapp.studios.advance_widths as aw

    path = Path(__file__).resolve().parents[1] / "Scripts" / "Metrics" / "Advance Widths Demo.py"
    opened_with = []
    monkeypatch.setattr(aw, "show", lambda: opened_with.append(True))
    runpy.run_path(str(path), run_name="__main__")
    assert opened_with == [True]
    runpy.run_path(str(path), run_name="imported")
    assert opened_with == [True]
    said = []
    monkeypatch.setattr(aw, "show", lambda: (_ for _ in ()).throw(RuntimeError("no font")))
    monkeypatch.setattr(dialogs, "run_standard_message_box", lambda *a: said.append(a[3]))
    import fontlabapp

    qt = SimpleNamespace(QtGui=SimpleNamespace(QMessageBox=SimpleNamespace(Ok=1)))
    stub_natives(monkeypatch, fontlabapp, lambda name: qt if name == 'PythonQt' else SimpleNamespace(MainWindow=lambda: None))
    runpy.run_path(str(path), run_name="__main__")
    assert said == ["Advance Widths did not open: no font"]


def test_wp03_round_reports_auto_skips_after_successful_write(opened):
    pkg = package()
    pkg.add("automatic", {"Regular": (0, 0, 601), "Bold": (0, 0, 703)}, auto=True)
    app = opened(pkg, selection=("H", "automatic"))
    panel = app.panels["Round & scale"]
    panel.scope.setCurrentIndex(1)
    app.shell.tabs.setCurrentIndex(1)
    app.shell.preview_button.click()
    assert not app.history.calls
    app.shell.apply_button.click()
    assert len(app.history.calls) == 1
    assert "2 layers skipped (auto)" in app.tool.status


def test_wp03_refresh_selection_and_close_buttons_use_actual_shell(opened):
    app = opened(selection=("H",))
    panel = app.panels["Round & scale"]
    app.shell.tabs.setCurrentIndex(1)
    assert {entry.glyph.name for entry in panel.entries} == {"H"}
    app.selection[:] = ["O"]
    app.shell.refresh_button.click()
    assert {entry.glyph.name for entry in panel.entries} == {"O"}
    assert app.shell.widget.isVisible()
    app.shell.close_button.click()
    assert app.shell.closed and app.shell._close_complete
    assert app.shell.connections == []
    assert not app.shell.widget.isVisible()
    assert app.shell._delete_scheduled and app.shell._close_error is None


@pytest.mark.parametrize('during', ['refresh', 'selection'])
def test_table_when_master_domain_changes_during_scan_then_refuse_and_clear(opened, monkeypatch, during):
    from fontlabapp.studios.advance_widths import widths
    pkg, app, panel, selected = _mixed_table(opened)
    original = widths.width_report
    def report(*args):
        rows = original(*args)
        pkg.master = 'Bold'
        return rows
    monkeypatch.setattr(widths, 'width_report', report)
    if during == 'refresh':
        panel.reload_view()
    else:
        panel.select_button.click()
    assert not panel.rows and panel.source is None and panel.domain is None
    assert not panel.select_button.isEnabled() and not selected
    assert 'changed' in app.tool.status


def test_tabular_selected_empty_scope_reports_selection_requirement(opened):
    app = opened(selection=())
    panel = app.panels['Tabular']
    panel.group.setCurrentIndex(2)
    assert panel.entries == [] and not panel.apply_button.isEnabled()
    assert 'Select glyphs' in panel.subtitle.text()


def test_tabular_refresh_during_control_construction_does_not_read_missing_report(monkeypatch, studio_qt):  # noqa: F811
    module = importlib.import_module('fontlabapp.studios.advance_widths.tabular')
    calls = []
    monkeypatch.setattr(module.LayerPanel, 'refresh', lambda panel: calls.append(panel))
    panel = object.__new__(module.TabularPanel)
    panel.refresh()
    assert calls == [panel] and not hasattr(panel, 'report')
