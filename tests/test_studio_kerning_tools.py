# this_file: tests/test_studio_kerning_tools.py
"""Kerning Browser (A9) and Kerning Batch (A10): parity with the 12 Scriptmix scripts, writes and dry runs.

Writes go through the real ``fontlabapp.kerning.batch`` pipeline on a native
fake; each test checks the master written and the ``Kerning Browser: …`` /
``Kerning Batch: …`` Undo label (§1.3/§1.4). Read-only tabs are checked to
leave native writes and history empty. Every Batch tab is checked to apply
exactly the dry-run set it displayed, and to refuse after an outside edit.
"""

import ast
import hashlib
import importlib
import inspect
import sys
from types import SimpleNamespace

import pytest
from _kerning_tools_originals import ORIGINALS
from _studio_qt import studio_qt  # noqa: F401 - fixture

HOST = SimpleNamespace(package=None)
GLYPHS = {"A": 65, "Aacute": 0xC1, "V": 86, "W": 87, "O": 79, "T": 84, "a": 97, "o": 111,
          "period": 46, "comma": 44, "period.alt": None, "x": 120}


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
        fl=SimpleNamespace(font=None),  # no Font window: selection reads as empty
    )
    monkeypatch.setattr(scripting, "_native", lambda name: native)
    monkeypatch.setattr(batch, "_native", lambda name: native)
    yield
    HOST.package = None


@pytest.fixture(autouse=True)
def fresh_studios():
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)  # keep "no studio child loaded" contracts order-independent


def _decode(key):
    return tuple(("@" if mode == "groupMode" else "") + name for name, mode in key)


class Kern:
    """``package.kerning(master)``: typed items, native classes, batch setters."""

    def __init__(self, values, groups, writes):
        self.writes, self.values, self.groups = writes, values, groups

    def items(self):
        def side(name):
            group = name.startswith("@")
            return SimpleNamespace(id=name.lstrip("@"), mode="groupMode" if group else "glyphMode")

        return [(SimpleNamespace(left=side(a), right=side(b)), v) for (a, b), v in self.values.items()]

    def set(self, key, value):
        self.writes.append("set")
        if value != 0:  # the native setter drops zero
            self.values[_decode(key)] = value

    def remove(self, key):
        self.writes.append("remove")
        self.values.pop(_decode(key), None)

    def scale(self, factor):
        self.writes.append("scale")
        self.values = {key: amount * factor for key, amount in self.values.items()}


class Package:
    """Native package fake; ``writes`` records setters, ``history`` the Undo steps."""

    def __init__(self, masters, current="Regular"):
        self.writes, self.history = [], []
        self.kerns = {m: Kern(dict(p), dict(g), self.writes) for m, (p, g) in masters.items()}
        self.master, self.id, self.isNull, self.upm = current, 7, False, 1000
        HOST.package = self

    @property
    def masters(self):
        return list(self.kerns)

    def kerning(self, master):
        return self.kerns[master]

    def findName(self, name):  # noqa: N802 - native API
        return SimpleNamespace(isNull=False, name=name) if name in GLYPHS else None

    def findUnicode(self, code):  # noqa: N802 - native API
        return next((SimpleNamespace(name=n) for n, c in GLYPHS.items() if c == code), None)

    def checkInitHistoryState(self, flags):  # noqa: N802 - native API
        pass

    def mastersContainer(self):  # noqa: N802 - native API
        return "masters"

    def kerningContainer(self):  # noqa: N802 - native API
        return "kerning"

    def values(self, master):
        return self.kerns[master].values


GROUPS = {"A": (["A", "Aacute"], "KernLeft"), "V": (["V", "W"], "KernRight"), "O": (["O"], "KernBothSide"),
          "P": (["period", "comma"], "KernRight")}


def package(regular=None, bold=None, groups=GROUPS):
    regular = {("@A", "@V"): -82, ("A", "W"): -43, ("T", "o"): 2, ("A", "O"): 0, ("@A", "@P"): -50} \
        if regular is None else regular
    bold = {("@A", "@V"): -300, ("T", "o"): 150, ("A", "W"): -250, ("O", "O"): 100} if bold is None else bold
    return Package({"Regular": (regular, groups), "Bold": (bold, groups)})


class Font(dict):
    """Fontport stand-in: ``name in font`` and ``font[name].unicodes``."""


FONT = Font({n: SimpleNamespace(unicodes=[c] if c else []) for n, c in GLYPHS.items()})


def labels(pkg):
    """Undo labels; each write opens and closes one checkpoint pair."""
    names = [name for name, _ in pkg.history]
    assert names[::2] == names[1::2]
    return names[::2]


# Studio fixture ----------------------------------------------------------------
@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return lambda *args: self.calls.append((name, *args))

    def open_app(name, pkg=None, font=FONT):
        studio = importlib.import_module(f"fontlabapp.studios.{name}")
        pkg = package() if pkg is None else pkg
        preview = QtPreview()
        shell = studio.show(package=lambda: pkg, font=lambda: font, preview=lambda shell, tool: preview)
        studio_qt.owned.append(shell)
        tool = shell.kerning_tool
        panels = {title: view.__self__ for title, view in zip(studio.TAB_TITLES, tool.views, strict=True)}
        return SimpleNamespace(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio)

    return open_app


def statuses(app):
    return app.tool.status


# Registry and window ---------------------------------------------------------------
def test_show_when_opened_then_six_tabs_preview_and_current_master(opened):
    for name, titles in (("kerning_browser", ["Pairs", "Classes", "Exceptions", "Missing", "Masters", "Energy"]),
                         ("kerning_batch", ["Round", "Scale", "Remove small", "Clamp", "Copy masters", "Punctuation"])):
        app = opened(name)
        assert [app.shell.tabs.tabText(i) for i in range(app.shell.tabs.count())] == titles + ["About"]
        assert app.shell.preview is app.preview and ("set_layer", "Regular") in app.preview.calls
        assert app.tool.current == "Regular" and app.tool.masters == ["Regular", "Bold"]


def test_registry_when_imported_then_lazy_builders_and_shared_tool():
    from fontlabapp import studios
    import fontlabapp.studios.kerning_batch as batch
    import fontlabapp.studios.kerning_browser as browser

    for module in (browser, batch):
        assert module.register_tabs() == module.TAB_TITLES
        assert module.register_tabs() == module.TAB_TITLES  # idempotent
        assert [s.title for s in studios.tabs(module.APP)] == list(module.TAB_TITLES)
        shell = SimpleNamespace()
        assert module.tool_for(shell) is module.tool_for(shell)
        assert module.tool_for(shell).app == module.APP
    assert not any(n.endswith(("pairs", "rounding")) for n in sys.modules if n.startswith("fontlabapp.studios."))


def test_show_when_no_font_then_status_and_no_preview(studio_qt):  # noqa: F811
    import fontlabapp.studios.kerning_batch as batch

    HOST.package = None
    shell = batch.show(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    assert shell.kerning_tool.preview is None
    assert shell.kerning_tool.package is None
    assert not shell.kerning_tool.views[0].__self__.apply_button.isEnabled()


def test_show_when_build_fails_then_shell_closed(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios._kerning_app as assembly

    closed = []
    fake = SimpleNamespace(close=lambda: closed.append(True), hint_check=None, widget=None,
                           add_tab=lambda spec: None, set_about=lambda text: None,
                           package=lambda: None)
    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: fake)

    def boom(shell, tool):
        raise RuntimeError("no preview")

    with pytest.raises(RuntimeError, match="no preview"):
        assembly.show("Kerning Batch", lambda: (), package=lambda: None, font=lambda: None, preview=boom)
    assert closed == [True]


def test_metrics_preview_when_font_then_read_only_tmetrics(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios._kerning_app as assembly

    calls = []
    monkeypatch.setattr(fontui, "metrics_preview", lambda *a, **k: calls.append((a, k)) or "preview")
    shell = SimpleNamespace(widget="w", hint_check="check")
    assert assembly.metrics_preview(shell, SimpleNamespace(font=lambda: "font")) == "preview"
    assert calls == [(("font", "w"), {"controls": False, "hint_check": "check", "read_only": True})]
    assert assembly.metrics_preview(shell, SimpleNamespace(font=lambda: None)) is None


# Kerning Batch: dry run == Apply ----------------------------------------------------
def _grid_rows(panel):
    return [(row.glyph_name, row.layer, tuple(row.values)) for row in panel.grid.rows]


def test_round_when_applied_then_exactly_the_dry_run_set_on_current_master(opened):
    app = opened("kerning_batch")
    panel = app.panels["Round"]
    backend = app.tool.backends().edit.round_plan(app.pkg, ["Regular"], 5, True)
    assert panel.edits == {"Regular": {pair: new for pair, (_old, new) in backend["Regular"].items()}}
    assert panel.edits["Regular"] == {("@A", "@V"): -80, ("A", "W"): -45, ("T", "o"): None, ("A", "O"): None}
    assert len(panel.grid.rows) == 4 and panel.count.text() == "4 pairs change (Regular 4)"
    assert ("A  W", "Regular", ("Regular", -43, -45)) in _grid_rows(panel)
    assert panel.subtitle.text() == "5 pairs in 1 master. Values snap to multiples of 5; halves round away from zero."
    shown = dict(panel.edits)
    bold_before = dict(app.pkg.values("Bold"))
    assert panel.apply_button.isEnabled() and panel.apply()
    assert labels(app.pkg) == ["Kerning Batch: Round kerning on Regular"]
    after = app.pkg.values("Regular")
    assert {pair: after.get(pair) for pair in shown["Regular"]} == shown["Regular"]
    assert app.pkg.values("Bold") == bold_before
    assert statuses(app) == "Changed 4 pairs (Regular 4)"
    assert not panel.apply_button.isEnabled()  # replanned after the write: nothing left


def test_round_when_drop_zero_off_then_explicit_zero_kept(opened):
    app = opened("kerning_batch")
    panel = app.panels["Round"]
    panel.drop_zero.setChecked(False)
    assert panel.edits["Regular"][("T", "o")] == 0 and ("A", "O") not in panel.edits["Regular"]
    assert panel.count.text() == "3 pairs change (Regular 3)"  # explicit 0 rounds to itself


def test_batch_when_outside_edit_after_dry_run_then_stale_refusal_and_no_write(opened):
    app = opened("kerning_batch")
    for title in ("Round", "Scale", "Remove small", "Clamp"):
        panel = app.panels[title]
        if title == "Scale":
            panel.parameter.setValue(50.0)
        if title != "Clamp":
            panel.scope.setCurrentIndex(1)
        assert panel.apply_button.isEnabled(), title
        app.pkg.kerns["Regular"].values[("V", "o")] = -12  # someone edits kerning in FontLab
        assert not panel.apply()
        assert "stale" in statuses(app) and app.pkg.history == []
        del app.pkg.kerns["Regular"].values[("V", "o")]
        app.tool.reload()


def test_batch_when_plan_empty_then_apply_disabled(opened):
    pkg = package(regular={("A", "W"): -40}, bold={("A", "W"): -40})
    app = opened("kerning_batch", pkg)
    assert not app.panels["Round"].apply_button.isEnabled()
    assert app.panels["Round"].count.text() == "Nothing to change"
    assert not app.panels["Clamp"].apply_button.isEnabled()
    assert app.panels["Clamp"].count.text() == "Nothing to clamp"
    assert app.panels["Remove small"].count.text() == "No pairs below the threshold"
    with pytest.raises(ValueError, match="Nothing to apply"):
        app.tool.write("Round", "kerning", {"Regular": {}}, object())
    assert pkg.history == []


def test_scale_when_all_masters_then_existing_zero_kept_and_label(opened):
    app = opened("kerning_batch")
    panel = app.panels["Scale"]
    panel.scope.setCurrentIndex(1)
    panel.parameter.setValue(50.0)
    assert panel.scope.itemText(0) == "Current master (Regular)" and panel.scope.itemText(1) == "All masters (2)"
    assert ("A", "O") not in panel.edits["Regular"]  # explicit zero stays even with drop-zero on
    assert panel.edits["Regular"][("T", "o")] == 1
    assert panel.edits["Bold"][("@A", "@V")] == -150
    assert panel.subtitle.text().endswith("Every value is multiplied by 50 % and rounded to whole units.")
    shown = panel.edits
    assert panel.apply()
    assert labels(app.pkg) == ["Kerning Batch: Scale kerning on Regular, Bold"]
    for master, changes in shown.items():
        assert {p: app.pkg.values(master).get(p) for p in changes} == changes


def test_remove_small_when_threshold_then_listed_pairs_deleted(opened):
    app = opened("kerning_batch")
    panel = app.panels["Remove small"]
    panel.threshold.setValue(5)
    assert panel.edits == {"Regular": {("A", "O"): None, ("T", "o"): None}}
    assert _grid_rows(panel)[0] == ("A  O", "Regular", ("Regular", 0))
    assert panel.count.text() == "2 to remove (Regular 2)"
    assert panel.apply()
    assert labels(app.pkg) == ["Kerning Batch: Remove small kerning on Regular"]
    assert ("A", "O") not in app.pkg.values("Regular") and ("T", "o") not in app.pkg.values("Regular")
    assert statuses(app) == "Removed 2 pairs (Regular 2)"


def test_clamp_when_applied_then_inclusive_range_all_masters_and_absent_never_added(opened):
    app = opened("kerning_batch")
    panel = app.panels["Clamp"]
    g = "glyphMode"
    assert panel.edits == {"Regular": {}, "Bold": {(("A", "groupMode"), ("V", "groupMode")): -250,
                                                  (("T", g), ("o", g)): 100}}
    assert ("@A  @V", "Bold", ("Bold", -300, -250)) in _grid_rows(panel)
    before_keys = {m: set(app.pkg.values(m)) for m in app.pkg.masters}
    assert panel.apply()
    assert labels(app.pkg) == ["Kerning Batch: Clamp kerning on Bold"]
    bold = app.pkg.values("Bold")
    assert bold[("@A", "@V")] == -250 and bold[("T", "o")] == 100
    assert bold[("A", "W")] == -250 and bold[("O", "O")] == 100  # limits are inclusive
    assert {m: set(app.pkg.values(m)) for m in app.pkg.masters} == before_keys
    assert statuses(app) == ("Kerning Cutoff: Regular: 0 pairs changed; inclusive [-250, 100]. "
                             "Kerning Cutoff: Bold: 2 pairs changed; inclusive [-250, 100].")


def test_round_when_untouched_master_out_of_range_then_only_changed_master_checked(opened):
    pkg = package(bold={("A", "W"): 5000})  # beyond twice UPM, but Round only writes Regular
    app = opened("kerning_batch", pkg)
    assert app.panels["Round"].apply()
    assert labels(pkg) == ["Kerning Batch: Round kerning on Regular"]
    assert pkg.values("Bold") == {("A", "W"): 5000}


def test_copy_when_targets_ticked_then_counts_confirm_and_apply_writes_plan(opened):
    app = opened("kerning_batch")
    panel = app.panels["Copy masters"]
    assert panel.source_master() == "Regular"
    assert not panel.apply_button.isEnabled() and panel.count.text() == "Tick at least one target master"
    panel.targets.set_ticked({0})
    assert panel.chosen_targets() == ["Bold"]
    edit = app.tool.backends().edit
    snap = app.tool.backends().batch.snapshot_kerning(app.pkg)
    expected = edit.copy_plan(snap.pairs["Regular"], snap.pairs["Bold"], "replace", 100.0)
    assert panel.edits == {"Bold": expected}
    added, changed, removed = edit.summary(snap.pairs["Bold"], expected)
    assert [panel.targets.text(0, c) for c in range(5)] == ["Bold", "4", str(added), str(changed), str(removed)]
    assert panel.count.text() == f"{added + changed + removed} pair edits in 1 master"
    assert panel.subtitle.text() == "Regular has 5 pairs. Tick the masters that receive them."
    assert panel.apply()
    assert labels(app.pkg) == ["Kerning Batch: Copy kerning from Regular to Bold"]
    after = app.tool.backends().batch.snapshot_kerning(app.pkg).pairs["Bold"]
    assert {p: v for p, v in after.items() if v} == {p: v for p, v in snap.pairs["Regular"].items() if v}
    assert statuses(app) == f"Copied: Bold +{added} ~{changed} −{removed}"


def test_copy_when_scaled_missing_mode_then_kept_pairs_and_explicit_zero(opened):
    app = opened("kerning_batch")
    panel = app.panels["Copy masters"]
    panel.set_targets(["Bold"])
    panel.mode.setCurrentIndex(1)
    panel.percent.setValue(50.0)
    assert panel.mode_key() == "missing"
    assert panel.edits["Bold"] == {("A", "O"): 0, ("@A", "@P"): -25}
    assert [panel.mode.itemText(i) for i in range(3)] == [t for t, _ in importlib.import_module(
        "fontlabapp.studios.kerning_batch.copy_masters").MODES]
    panel.source.setCurrentIndex(1)
    assert panel.source_master() == "Bold" and panel.targets.text(0, 0) == "Regular"


def test_copy_when_outside_edit_then_stale(opened):
    app = opened("kerning_batch")
    panel = app.panels["Copy masters"]
    panel.set_targets(["Bold"])
    app.pkg.kerns["Bold"].values[("V", "o")] = -3
    assert not panel.apply() and "stale" in statuses(app) and app.pkg.history == []


def test_punctuation_when_selection_then_exceptions_added_classes_kept(opened):
    app = opened("kerning_batch")
    panel = app.panels["Punctuation"]
    app.tool.selected_names = lambda: ["period", "A"]
    panel.reselect()
    g = "glyphMode"
    assert panel.scope.itemText(0) == "Current master" and panel.scope.itemText(1) == "All masters"
    assert panel.edits == {"Regular": {(("A", g), ("period", g)): -50, (("Aacute", g), ("period", g)): -50}}
    notes = [row.values[2] for row in panel.grid.rows]
    assert "outside Unicode punctuation, kept" in notes
    assert panel.subtitle.text() == "2 glyphs: period, A"
    assert panel.apply()
    assert labels(app.pkg) == ["Kerning Batch: Add exceptions for 2 glyphs on Regular"]
    assert app.pkg.values("Regular")[("A", "period")] == -50 and ("@A", "@P") in app.pkg.values("Regular")
    assert statuses(app) == "Added 2 exceptions. Classes kept."


def test_punctuation_when_alternate_and_filter_off_then_base_codes_and_any_glyph(opened):
    app = opened("kerning_batch")
    panel = app.panels["Punctuation"]
    mod = sys.modules["fontlabapp.studios.kerning_batch.punctuation"]
    assert mod.glyph_codes(FONT, "period.alt") == [46] and mod.glyph_codes(None, "period") == []
    app.tool.selected_names = lambda: ["W", "missing"]
    panel.reselect()
    notes = [row.values[2] for row in panel.grid.rows]
    assert "missing glyph, kept" in notes and "outside Unicode punctuation, kept" in notes
    panel.punctuation_only.setChecked(False)
    assert (("A", "glyphMode"), ("W", "glyphMode")) not in panel.edits.get("Regular", {})  # explicit pair kept
    assert (("Aacute", "glyphMode"), ("W", "glyphMode")) in panel.edits["Regular"]
    app.tool.selected_names = lambda: []
    panel.reselect()
    assert "Select glyphs in the Font window" in panel.count.text() and not panel.apply_button.isEnabled()


def test_punctuation_when_numeric_problem_anywhere_then_whole_font_kept(opened):
    pkg = package(bold={("A", "W"): 2.5})
    app = opened("kerning_batch", pkg)
    panel = app.panels["Punctuation"]
    app.tool.selected_names = lambda: ["period"]
    panel.reselect()
    assert panel.edits == {}
    assert panel.found[-1].note.startswith("Font-wide numeric history check failed")
    assert not panel.apply_button.isEnabled()


def test_punctuation_when_many_rows_then_first_500_shown(opened, monkeypatch):
    app = opened("kerning_batch")
    panel = app.panels["Punctuation"]
    mod = sys.modules["fontlabapp.studios.kerning_batch.punctuation"]
    monkeypatch.setattr(mod, "MAX_ROWS", 1)
    app.tool.selected_names = lambda: ["period"]
    panel.reselect()
    assert len(panel.grid.rows) == 1 and panel.count.text().endswith("(table shows the first 1)")


def test_batch_row_when_chosen_then_pair_previewed_on_master(opened):
    app = opened("kerning_batch")
    app.panels["Round"].row_chosen("A  W", "Regular")
    assert ("set_text", "/A/W") in app.preview.calls and ("highlight_pair", "A", "W") in app.preview.calls
    app.preview.calls.clear()
    app.panels["Round"].row_chosen("@A  @V", "Bold")
    assert app.preview.calls == [("set_text", "/A/V"), ("set_layer", "Bold")]


# Kerning Browser --------------------------------------------------------------------
def test_browser_read_only_tabs_when_used_then_no_writes_or_history(opened, tmp_path, monkeypatch):
    app = opened("kerning_browser")
    selected = []
    monkeypatch.setitem(app.tool.select.__func__.__globals__, "select_glyphs",
                        lambda names, package_id: selected.append((list(names), package_id)))
    app.tool.selected_names = lambda: ["A", "V", "period"]
    pairs, classes, missing = app.panels["Pairs"], app.panels["Classes"], app.panels["Missing"]
    masters, energy = app.panels["Masters"], app.panels["Energy"]
    app.tool.reload()
    pairs.filter.setText("=A")
    assert [r[:2] for r in pairs.rows] == [("A", "O"), ("A", "W")] and statuses(app) == "2 of 5 pairs"
    pairs.grid.select("A", "Regular")
    assert ("set_text", "/A/O") in app.preview.calls  # the row's own right side, not a row index
    assert pairs.write(tmp_path / "k.csv") == 2
    assert (tmp_path / "k.csv").read_text().splitlines() == ["left,right,value,master", "A,O,0,Regular",
                                                              "A,W,-43,Regular"]
    classes.select_class("A")
    classes.select_members()
    assert selected == [(["A", "Aacute"], 7)]
    missing.left_text.setText("A T")
    missing.right_text.setText("@V o")
    assert missing.missing == [("A", "o"), ("T", "V"), ("T", "W")]
    masters.only_flagged.setChecked(True)
    energy.refresh()
    assert energy.result["master"] == "Regular" and energy.result["glyphs"] == ["A", "V", "period"]
    assert app.pkg.writes == [] and app.pkg.history == []


def test_pairs_tab_when_master_changed_then_subtitle_and_dialog(opened):
    app = opened("kerning_browser")
    pairs = app.panels["Pairs"]
    assert pairs.subtitle.text() == "Regular: 5 pairs, 2 of them with a class side"
    pairs.master.setCurrentIndex(1)
    assert pairs.subtitle.text() == "Bold: 4 pairs, 1 of them with a class side" and statuses(app) == "4 pairs"
    pairs.export()
    assert pairs.dialog is not None
    pairs.dialog.close()


def test_classes_tab_when_filtered_then_items_detail_and_status(opened):
    app = opened("kerning_browser")
    classes = app.panels["Classes"]
    assert classes.subtitle.text() == "4 classes: 1 left, 2 right, 1 both sides. Values are shown for all 2 masters."
    classes.filter.setText("W")
    assert classes.names == ["V"] and classes.list.item(0).text() == "@V   right · 2"
    assert classes.title.text() == "@V · right side" and classes.members.text() == "V W"
    assert classes.pairs.item(0, 0).text() == "@A  @V" and classes.pairs.item(0, 2).text() == "-300"
    assert statuses(app) == "@V: 2 members, used in 1 pairs"
    classes.pair_chosen(0)
    classes.filter.setText("zzz")
    assert classes.title.text() == "No class" and not classes.select_button.isEnabled()


def test_missing_tab_when_zero_pair_then_covered(opened):
    app = opened("kerning_browser")
    missing = app.panels["Missing"]
    missing.left_text.setText("A")
    missing.right_text.setText("O")
    assert missing.missing == []  # ("A", "O") is stored with zero: covered
    missing.right_text.setText("x")
    assert missing.missing == [("A", "x")] and statuses(app) == "1 of 1 combinations unkerned (100 %)"
    missing.grid.select("A", "Regular")
    assert ("set_text", "/A/x") in app.preview.calls
    assert missing.copy() == "A x"


def test_masters_tab_when_flagged_then_rows_and_status(opened):
    app = opened("kerning_browser")
    masters = app.panels["Masters"]
    masters.threshold.setValue(100)
    masters.only_flagged.setChecked(True)
    rows = {pair: reasons for pair, _values, reasons in masters.shown}
    assert rows[("T", "o")] == ["jump"] and rows[("A", "O")] == ["missing"]
    assert masters.grid.horizontalHeaderItem(3).text() == "Flags"
    assert "pairs flagged" in statuses(app)
    masters.search.setText("@A")
    assert all("@A" in pair[0] for pair, *_ in masters.shown)
    masters.pair_chosen(0)


def test_exceptions_tab_when_ticked_then_only_those_removed(opened):
    pkg = package(regular={("@A", "@V"): -80, ("A", "W"): -80, ("Aacute", "@V"): -30})
    app = opened("kerning_browser", pkg)
    tab = app.panels["Exceptions"]
    tab.refresh()
    assert [r[1] for r in tab.rows] == [("A", "W"), ("Aacute", "@V")]
    assert tab.subtitle.text().startswith("2 exceptions, 1 of them redundant")
    assert statuses(app) == "0 of 2 ticked" and not tab.apply_button.isEnabled()
    tab.tick(lambda r: r[2] == r[4])
    assert [tab.rows[n][1] for n in tab.grid.ticked()] == [("A", "W")] and statuses(app) == "1 of 2 ticked"
    assert tab.grid.text(0, 5) == "same" and tab.grid.text(1, 5) == "+50"
    assert pkg.history == [] and pkg.writes == []
    tab.pair_chosen(0)
    assert tab.apply()
    assert labels(pkg) == ["Kerning Browser: Remove 1 exception"]
    assert pkg.values("Regular") == {("@A", "@V"): -80, ("Aacute", "@V"): -30}
    assert statuses(app) == "Removed 1 exceptions"


def test_exceptions_tab_when_stale_then_refused(opened):
    pkg = package(regular={("@A", "@V"): -80, ("A", "W"): -80})
    app = opened("kerning_browser", pkg)
    tab = app.panels["Exceptions"]
    tab.tick(lambda r: True)
    pkg.kerns["Regular"].values[("V", "o")] = -3
    assert not tab.apply() and "stale" in statuses(app) and pkg.history == []


def test_energy_tab_when_no_selection_then_message_and_report_opens(opened, monkeypatch):
    app = opened("kerning_browser")
    energy = app.panels["Energy"]
    app.tool.selected_names = lambda: []
    energy.refresh()
    assert energy.subtitle.text() == "Kerning Energy Report: Select glyphs in the Font window first."
    assert not energy.open_button.isEnabled()
    with pytest.raises(ValueError):
        energy.open_report()
    app.tool.selected_names = lambda: ["A", "W"]
    energy.refresh()
    shown = []
    reports = SimpleNamespace(show_report=lambda report, **kw: shown.append((report, kw)) or "window")
    real = app.tool.backends()
    app.tool._backends = lambda: SimpleNamespace(**{**vars(real), "reports": reports})
    assert energy.open_report() == "window"
    assert shown[0][1] == {"title": "Kerning Energy Report — Read-only", "key": "kerning_energy_report"}
    assert shown[0][0] is energy.result and shown[0][0]["master"] == "Regular"
    assert len(energy.grid.rows) == len(energy.result.get("suggestions", energy.grid.rows))
    energy.row_chosen("A", "Regular")
    assert app.pkg.history == []


# Fix round 1: contained refresh failures, real layers, snapshot plans ----------------
FAILURE = "The original font is no longer current; reopen this tool."


def fail(*args, **kwargs):
    raise RuntimeError(FAILURE)


def test_browser_refresh_when_reads_fail_then_contained_and_later_tabs_refreshed(opened, monkeypatch):
    app = opened("kerning_browser")
    tabs = {name: sys.modules[f"fontlabapp.studios.kerning_browser.{name}"]
            for name in ("pairs", "classes", "missing", "masters")}
    p = app.panels
    assert p["Pairs"].rows and p["Classes"].names and p["Exceptions"].rows and p["Masters"].shown
    monkeypatch.setattr(tabs["pairs"], "kerning_pairs", fail)
    monkeypatch.setattr(tabs["classes"], "kerning_classes", fail)
    monkeypatch.setattr(tabs["missing"], "class_lists", fail)
    monkeypatch.setattr(tabs["masters"], "kerning_pairs", fail)
    real = app.tool.backends()
    app.tool._backends = lambda: SimpleNamespace(**{**vars(real), "selection": SimpleNamespace(find=fail)})
    app.tool.selected_names = lambda: ["A", "V"]
    app.tool.reload()  # must not raise out of the Refresh slot
    text = f"Kerning Browser: {FAILURE}"
    for title in ("Pairs", "Classes", "Exceptions", "Missing", "Masters"):
        assert p[title].subtitle.text() == text, title
    assert p["Pairs"].rows == [] and p["Pairs"].grid.rows == [] and not p["Pairs"].export_button.isEnabled()
    assert p["Classes"].names == [] and p["Classes"].title.text() == "No class"
    assert p["Exceptions"].rows == [] and p["Exceptions"].snapshot is None
    assert not p["Exceptions"].apply_button.isEnabled()
    assert p["Missing"].missing == [] and not p["Missing"].copy_button.isEnabled()
    assert p["Masters"].shown == [] and p["Masters"].grid.rowCount() == 0
    assert p["Energy"].result is not None and p["Energy"].result["glyphs"] == ["A", "V"]  # later tab still refreshed
    p["Pairs"].subtitle.setText("")
    p["Pairs"].filter.setText("A")  # a widget slot is contained too
    assert p["Pairs"].subtitle.text() == text
    assert app.pkg.writes == [] and app.pkg.history == []


def test_tool_reload_when_package_or_view_fails_then_status_and_other_views_run(opened, monkeypatch):
    app = opened("kerning_browser")
    said, seen = [], []
    app.tool.say = said.append
    app.tool.views.insert(0, lambda: fail())
    app.tool.views.append(lambda: seen.append(app.tool.package))
    app.tool.reload()
    assert seen == [app.pkg] and f"Kerning Browser: {FAILURE}" in said
    said.clear()
    monkeypatch.setattr(app.shell, "package", fail)
    app.tool.reload()
    assert app.tool.package is None and app.tool.masters == [] and app.tool.current == ""
    assert said[0] == f"Kerning Browser: {FAILURE}" and seen[-1] is None
    assert app.panels["Pairs"].subtitle.text() == "Open a font first."
    monkeypatch.setattr(app.shell, "package", lambda: None)
    said.clear()
    app.tool.reload()
    assert said[0] == "Open a font first." and app.tool.scope(True) == []


def test_table_rows_when_built_then_layer_is_a_master_not_a_row_index(opened):
    browser = opened("kerning_browser")
    pairs, missing, energy = (browser.panels[t] for t in ("Pairs", "Missing", "Energy"))
    browser.tool.selected_names = lambda: ["A", "W"]
    energy.refresh()
    for table in (pairs.grid, missing.grid, energy.grid):
        assert table.rows and {row.layer for row in table.rows} == {"Regular"}
    pairs.master.setCurrentIndex(1)
    assert {row.layer for row in pairs.grid.rows} == {"Bold"}
    assert pairs.grid.select("T", "Bold") and pairs.grid.current_row().values[0] == "o"
    assert browser.preview.calls[-3:] == [("set_text", "/T/o"), ("set_layer", "Bold"), ("highlight_pair", "T", "o")]
    pairs.grid.set_rows([])
    assert pairs.grid.current_row() is None
    batch = opened("kerning_batch")
    panel = batch.panels["Punctuation"]
    batch.tool.selected_names = lambda: ["period", "A"]
    panel.reselect()
    assert {row.layer for row in panel.grid.rows} <= {"Regular", None}
    assert panel.grid.select("Regular", "Regular")
    row = panel.grid.current_row()
    assert batch.preview.calls[-3][0] == "set_text" and batch.preview.calls[-3][1] == f"/{row.values[0]}/{row.values[1]}"
    panel.row_chosen("All masters", None)  # the font-wide note row previews nothing


def test_value_tabs_when_planned_then_built_from_the_shown_snapshot(opened, monkeypatch):
    app = opened("kerning_batch")
    real = app.tool.backends()
    edit = real.edit
    masters = ["Regular", "Bold"]
    snapshot = sys.modules["fontlabapp.fontui"].kerning_snapshot(app.pkg)
    pairs = {m: snapshot.pairs[m] for m in masters}
    for snap, live, parameter in ((True, edit.round_plan, 5), (False, edit.scale_plan, 50.0)):
        for drop in (True, False):
            assert edit.plan_values(pairs, parameter, drop, snap=snap) == live(app.pkg, masters, parameter, drop)
    assert edit.small_values(pairs, 5) == edit.small_pairs(app.pkg, masters, 5)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        edit.small_values(pairs, -1)
    live_only = SimpleNamespace(**{name: getattr(edit, name) for name in ("plan_values", "small_values")},
                                round_plan=fail, scale_plan=fail, small_pairs=fail)
    app.tool._backends = lambda: SimpleNamespace(**{**vars(real), "edit": live_only})
    for title in ("Round", "Scale", "Remove small"):
        panel = app.panels[title]
        panel.scope.setCurrentIndex(1)
        panel.refresh()
        assert panel.snapshot is not None and FAILURE not in panel.count.text(), title
    rounding = app.panels["Round"]
    expected = edit.plan_values({m: rounding.snapshot.pairs[m] for m in masters}, 5, True, snap=True)
    assert rounding.edits == {m: {pair: new for pair, (_old, new) in items.items()} for m, items in expected.items()}
    small = app.panels["Remove small"]
    assert small.edits == {m: {(a, b): None for a, b, _ in rows}
                           for m, rows in edit.small_values(small.snapshot.pairs, 5).items()}


# Parity with the Scriptmix originals -------------------------------------------------
MODULES = {
    "Pair List Browser": "fontlabapp.studios.kerning_browser.pairs",
    "Classes Browser": "fontlabapp.studios.kerning_browser.classes",
    "Missing Pairs": "fontlabapp.studios.kerning_browser.missing",
    "Compare Masters": "fontlabapp.studios.kerning_browser.masters",
    "Kerning Energy Report": "fontlabapp.studios.kerning_browser.energy",
    "Unbundle Punctuation Kerning": "fontlabapp.studios.kerning_batch.punctuation",
    "Copy Between Masters": "fontlabapp.studios.kerning_batch.copy_masters",
}
#: Bodies whose only change is the import of the same App modules (Fly -> core.scripting accessor).
REWIRED = {"numeric_problem", "master_problem"}


def _qt_free(monkeypatch):
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtCore=SimpleNamespace(), QtGui=SimpleNamespace()))


def _node(source, name):
    for node in ast.parse(source).body:
        found = getattr(node, "name", None) or getattr(getattr(node, "targets", [None])[0], "id", None)
        if found == name:
            return node
    raise AssertionError(name)


@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_ported_bodies_when_compared_then_ast_equal_to_scriptmix(title, monkeypatch):
    names, digest, source = ORIGINALS[title]
    assert hashlib.sha256(source.encode()).hexdigest() == digest
    _qt_free(monkeypatch)
    ported = inspect.getsource(importlib.import_module(MODULES[title]))
    for name in names:
        if name in REWIRED:
            continue
        assert ast.dump(_node(ported, name)) == ast.dump(_node(source, name)), f"{title}: {name}"


def _original(title, **names):
    _functions, _digest, source = ORIGINALS[title]
    namespace = {"__name__": "original"}
    header = ("import csv, io, itertools, pathlib\nfrom collections.abc import Sequence\nfrom dataclasses import "
              "dataclass\nfrom math import isfinite\nfrom typing import Any\nfrom unicodedata import category\n")
    namespace.update(names)
    exec(header + source, namespace)  # noqa: S102 - verbatim test fixture
    return SimpleNamespace(**namespace)


def test_browser_functions_when_run_like_originals_then_same_results(monkeypatch):
    from fontlabapp.core.scripting import kerning_class_lists, kerning_pairs

    _qt_free(monkeypatch)
    pkg = package()
    shared = {"kerning_pairs": kerning_pairs, "class_lists": kerning_class_lists}
    pairs_mod = importlib.import_module(MODULES["Pair List Browser"])
    pairs_orig = _original("Pair List Browser")
    for text in ("", "A", "=A", "@", "zz"):
        assert pairs_mod.filtered(kerning_pairs(pkg, "Regular"), text) == pairs_orig.filtered(
            kerning_pairs(pkg, "Regular"), text)
    classes_mod, classes_orig = importlib.import_module(MODULES["Classes Browser"]), _original("Classes Browser", **shared)
    assert classes_mod.pairs_using(pkg, pkg.masters, "A") == classes_orig.pairs_using(pkg, pkg.masters, "A")
    missing_mod, missing_orig = importlib.import_module(MODULES["Missing Pairs"]), _original("Missing Pairs", **shared)
    _, _, members = kerning_class_lists(pkg, "Regular")
    lefts = missing_orig.parse_glyphs("AT @A", pkg, members)
    assert missing_mod.parse_glyphs("AT @A", pkg, members) == lefts
    assert missing_mod.missing(pkg, "Regular", lefts, ["o", "O", "x"]) == missing_orig.missing(
        pkg, "Regular", lefts, ["o", "O", "x"])
    masters_mod, masters_orig = importlib.import_module(MODULES["Compare Masters"]), _original("Compare Masters", **shared)
    rows = masters_orig.table(pkg, pkg.masters)
    assert masters_mod.table(pkg, pkg.masters) == rows
    assert [masters_mod.flags(v, 40) for v in rows.values()] == [masters_orig.flags(v, 40) for v in rows.values()]


def test_energy_and_punctuation_when_run_like_originals_then_same_results(monkeypatch):
    from fontlabapp.core.scripting import kerning_tool_backends
    from fontlabapp.kerning.batch import snapshot_kerning

    _qt_free(monkeypatch)
    pkg = package(groups={**GROUPS, "A2": (["A"], "KernLeft")})
    snap = snapshot_kerning(pkg, typed=True)
    energy_mod = importlib.import_module(MODULES["Kerning Energy Report"])
    energy_orig = _original("Kerning Energy Report")
    names = ["A", "Aacute", "V", "W", "period"]
    assert energy_mod.analyze(names, snap.pairs["Regular"], snap.groups["Regular"]) == energy_orig.analyze(
        names, snap.pairs["Regular"], snap.groups["Regular"])
    punct = importlib.import_module(MODULES["Unbundle Punctuation Kerning"])
    fly = SimpleNamespace(ap=SimpleNamespace(kerning=SimpleNamespace(
        edit=SimpleNamespace(model=kerning_tool_backends().edit), batch=kerning_tool_backends().batch)))
    for name, module in (("fly", fly), ("fly.ap", fly.ap), ("fly.ap.kerning", fly.ap.kerning),
                         ("fly.ap.kerning.edit", fly.ap.kerning.edit),
                         ("fly.ap.kerning.edit.model", kerning_tool_backends().edit),
                         ("fly.ap.kerning.batch", kerning_tool_backends().batch)):
        monkeypatch.setitem(sys.modules, name, module)
    original = _original("Unbundle Punctuation Kerning")
    groups = snap.groups["Regular"]
    kept_a, kept_b = [], []
    assert punct.expand(snap.pairs["Regular"], groups, {"period", "A"}, kept=kept_a) == original.expand(
        snap.pairs["Regular"], groups, {"period", "A"}, kept=kept_b)
    assert kept_a == kept_b and kept_a  # A is in two left classes: ambiguous partner kept
    for pairs in (snap.pairs["Regular"], {(("A", "glyphMode"), ("W", "glyphMode")): 2.5},
                  {(("A", "glyphMode"), ("W", "glyphMode")): 3000}):
        assert punct.numeric_problem(pkg, "Regular", pairs) == original.numeric_problem(pkg, "Regular", pairs)
    bad = {(("Q", "glyphMode"), ("W", "glyphMode")): -5}
    for pairs in (snap.pairs["Regular"], bad):
        assert punct.master_problem(pkg, "Regular", pairs, groups) == original.master_problem(
            pkg, "Regular", pairs, groups)
    pkg.upm = "x"
    assert punct.numeric_problem(pkg, "Bold", {}) == original.numeric_problem(pkg, "Bold", {}) == \
        "Bold: invalid UPM; master kept"
    assert punct.is_punctuation([46]) and not punct.is_punctuation([65])


def test_snapshot_class_lists_when_compared_then_equal_to_core_scripting():
    from fontlabapp import fontui
    from fontlabapp.core.scripting import kerning_class_lists, kerning_classes

    pkg = package()
    snap = fontui.kerning_snapshot(pkg)
    for master in pkg.masters:
        _left, _right, members = kerning_class_lists(pkg, master)
        assert {name: list(group[0]) for name, group in snap.groups[master].items()} == members
        assert set(kerning_classes(pkg, master)) == set(snap.groups[master])
    typed = fontui.kerning_snapshot(pkg, typed=True)
    assert (("A", "groupMode"), ("V", "groupMode")) in typed.pairs["Regular"]
    assert ("@A", "@V") in snap.pairs["Regular"]


def test_side_name_and_counts_when_formatted_then_original_texts():
    from fontlabapp.studios._kerning import counts, pair_text, side_name

    assert side_name(("A", "groupMode")) == "@A" and side_name(("A", "glyphMode")) == "A" and side_name("@B") == "@B"
    assert counts({"Regular": 2, "Bold": 0}) == "Regular 2 · Bold 0" and pair_text("A", "V") == "A  V"


def test_tool_when_no_package_then_refusals():
    from fontlabapp.studios._kerning import Tool

    shell = SimpleNamespace(package=lambda: None, set_status=lambda text: None)
    tool = Tool(shell, "Kerning Batch", font=lambda: None)
    tool.reload()
    assert tool.status == "Open a font first." and tool.scope(True) == []
    with pytest.raises(ValueError, match="Open a font"):
        tool.select(["A"])
    with pytest.raises(ValueError, match="Open a font"):
        tool.write("Round", "kerning", {"Regular": {("A", "V"): 1}}, None)
    tool.show_pair("A", "V")  # no preview: nothing happens
    assert tool.font() is None


def test_wp03_pair_editor_when_batch_applied_then_exact_masters_zero_delete_and_stale_refusal(opened):
    from fontlabapp.studios.kerning_studio.pairs import PairEditorPanel

    app = opened("kerning_batch")
    panel = PairEditorPanel(app.tool)
    panel.glyph_field.setText("A")
    panel.refresh()
    panel.partner.setText("V")
    panel.add_row()
    panel.set_cell("A", "V", "Regular", "0")
    panel.set_cell("A", "V", "Bold", "-25")
    assert app.pkg.writes == []
    assert panel.apply()
    assert app.pkg.values("Regular")[("A", "V")] == 0
    assert app.pkg.values("Bold")[("A", "V")] == -25
    assert labels(app.pkg) == ["Kerning Batch: Edit pairs staged cells"]
    panel.set_cell("A", "V", "Regular", "")
    panel.set_cell("A", "V", "Bold", "-30")
    app.pkg.kerns["Regular"].values[("A", "W")] = -41
    writes, history = list(app.pkg.writes), list(app.pkg.history)
    drafts, errors = dict(panel.staged), dict(panel.errors)
    assert not panel.apply()
    assert app.pkg.writes == writes and app.pkg.history == history
    assert panel.staged == drafts and panel.errors == errors and not panel.ready()
    panel.revert()
    assert not panel.staged and not panel.errors
    panel.set_cell("A", "V", "Regular", "")
    assert panel.apply()
    assert ("A", "V") not in app.pkg.values("Regular")


def test_wp03_copy_counts_when_resorted_then_keep_target_master_identity(opened):
    from PythonQt import QtCore
    pkg = Package({"Regular": ({("A", "V"): -50}, {}),
                   "Z": ({}, {}), "A": ({("A", "V"): -20}, {})})
    app = opened("kerning_batch", pkg)
    panel = app.panels["Copy masters"]
    panel.set_targets(["A", "Z"])
    panel.targets.view.sortItems(0, QtCore.Qt.AscendingOrder)
    panel.update()
    found = {panel.targets.view.item(row, 0).text(): panel.targets.view.item(row, 1).text()
             for row in range(panel.targets.view.rowCount())}
    assert found == {"A": "1", "Z": "0"}
    actions = app.shell._actions[panel.widget]
    assert actions["ready"]()


def test_exceptions_when_ticked_then_refresh_keeps_accepted_selection(opened):
    pkg = package(regular={("@A", "@V"): -80, ("A", "W"): -80})
    app = opened("kerning_browser", pkg)
    tab = app.panels["Exceptions"]
    tab.tick(lambda row: True)
    accepted = (list(tab.rows), tab.snapshot, tab.ticked())
    tab.refresh()
    assert (tab.rows, tab.snapshot, tab.ticked()) == accepted
    assert 'Ticked exceptions kept' in statuses(app)
    assert not pkg.history and not pkg.writes
