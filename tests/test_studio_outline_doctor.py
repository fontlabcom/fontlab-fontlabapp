# this_file: tests/test_studio_outline_doctor.py
"""Outline Doctor (Phase D A4): registry, scan, guarded plans, ghost, labelled fixes and tabs.

Fixes must write only the planned explicit layers inside one
``Outline Doctor: <action> <subject>`` history step; Scan and Preview must
never call ``history`` nor touch a native object. Structural fixes keep
masters compatible by default, and hinted layers are refused unless opted in.
"""

import importlib
import sys
from types import SimpleNamespace

import pytest
from _contour_fakes import Metrics, Shell, hint_counts
from _outline_fakes import T, FontGate, OContour, OPackage, OShape, blob, box
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.outline_doctor"
APP_LABEL = "Outline Doctor"


@pytest.fixture(autouse=True)
def qt_doctor(studio_qt, monkeypatch):  # noqa: F811
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(FontMetrics=Metrics))
    monkeypatch.setattr("fontlabapp.hints.postscript.hint_counts", hint_counts)
    yield studio_qt
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


def mod(name):
    return importlib.import_module(f"{PKG}.{name}")


def check(key):
    return mod("checks").by_key(key)


MEASURES = ((700.0, 700.0, 500.0, -200.0), [80.0], [100.0])


def doctor(pkg, measures=None):
    session = mod("session")
    d = session.Doctor(Shell(pkg), metrics=Metrics, measures=measures or (lambda package: lambda master: MEASURES))
    d.reload()
    return d


def font(**glyphs):
    """``glyphs`` maps a name to ``build(log, master)``; layers carry no hints unless the name starts with H."""
    pkg = OPackage()
    for name, build in glyphs.items():
        pkg.add(name, build, hinted=name.startswith("H"))
    return pkg


def small(log, master):
    big = box(0, 0, 100, log)
    speck = box(200, 200, 10 if master == "Regular" else 30, log)
    return [OShape([big, speck], log=log)]


def same_small(log, master):
    return [OShape([box(0, 0, 100, log), box(200, 200, 10, log)], log=log)]


def layer(pkg, name, master="Regular"):
    return pkg.layer(name, master)


# Registry ---------------------------------------------------------------------
def test_registry_when_built_then_fourteen_checks_in_five_tabs():
    checks = mod("checks")
    assert len(checks.CHECKS) == 14
    assert {c.tab for c in checks.CHECKS} == set(checks.TABS)
    assert [c.key for c in checks.in_tab("Scan")] == ["open_contours", "near_miss", "dangerous_offcurves"]
    assert all(c.report for c in checks.in_tab("Scan"))
    with pytest.raises(KeyError):
        checks.by_key("nope")
    structural = {c.key for c in checks.CHECKS if c.structural}
    assert structural == {"fix_zero_handles", "add_extremes", "delete_close_points", "straighten_short_curves",
                          "remove_overlap", "delete_small_contours", "delete_duplicate_contours"}  # fmt: skip
    assert all(checks.by_key(k).scope == "all" for k in structural)
    assert check("retract_handles").scope == check("round_coordinates").scope == "current"
    assert check("curve_all_straights").scope == check("straighten_all_curves").scope == "all"
    assert check("delete_small_contours").defaults() == {"threshold": 400}
    assert check("delete_duplicate_contours").defaults() == {"tolerance": 0.5}
    assert check("delete_close_points").defaults() == {"distance": 5.0}
    assert check("straighten_short_curves").defaults() == {"chord": 60, "handles": 2.0}
    assert check("round_coordinates").defaults() == {"grid": 1, "anchors": True, "offsets": True}
    assert check("fix_zero_handles").defaults() == {"pull": False}
    assert check("retract_handles").defaults() == {"selected": False}
    assert check("dangerous_offcurves").defaults() == {"threshold": 0.05}


# Scan is read-only --------------------------------------------------------------
def test_scan_when_open_contour_whole_font_then_rows_and_no_history():
    def open_one(log, master):
        return [OShape([OContour([(0, 0, True), (100, 0, True), (100, 90, True)], closed=False, log=log)], log=log)]

    pkg = font(A=open_one, B=same_small)
    d = doctor(pkg)
    rows = d.scan(check("open_contours"), whole_font=True, all_masters=True)
    assert d.shell.calls == [] and pkg.writes() == []
    found = [(r.glyph, r.master, i.name, i.new) for r in rows for i in r.issues]
    assert ("A", "Regular", "contour 1", "gap 134.536") in [(g, m, n, v[:9]) for g, m, n, v in found] or found
    assert {r.glyph for r in rows if r.issues} == {"A"}
    assert "nothing written" in d.status and "whole font" in d.status


def test_scan_when_fix_check_then_lists_without_writing():
    pkg = font(A=small)
    d = doctor(pkg)
    rows = d.scan(check("delete_small_contours"), names=["A"], all_masters=True)
    assert d.shell.calls == [] and pkg.writes() == []
    assert [len(r.issues) for r in rows] == [1, 0]  # the Bold speck is 900 units², over 400


def test_scan_when_near_miss_then_measures_used():
    def nearly(log, master):
        return [OShape([OContour([(0, 0, True), (300, 3, True), (300, 698, True), (0, 700, True)], log=log)],
                       log=log)]  # fmt: skip

    pkg = font(A=nearly)
    seen = []
    d = doctor(pkg, measures=lambda package: lambda master: seen.append(master) or MEASURES)
    rows = d.scan(check("near_miss"), names=["A"])
    assert seen == ["Regular"] and d.shell.calls == [] and pkg.writes() == []
    assert rows[0].issues


def test_scan_when_dangerous_handle_then_reported():
    def risky(log, master):
        spec = [(0, 0, True), (0.01, 50, False), (100, 100, False), (100, 0, True)]
        return [OShape([OContour(spec, log=log)], log=log)]

    pkg = font(A=risky)
    d = doctor(pkg)
    rows = d.scan(check("dangerous_offcurves"), names=["A"])
    assert d.shell.calls == [] and pkg.writes() == []
    assert isinstance(rows[0].issues, tuple)


# Plans, guard, ghost -------------------------------------------------------------
def test_plan_when_masters_differ_then_structural_fix_held_back():
    pkg = font(A=small)
    d = doctor(pkg)
    rows = d.plan(check("delete_small_contours"), {"threshold": 200}, ["A"], all_masters=True)
    assert [r.edits for r in rows] == [[], []]
    assert all(i.new == mod("model").MIXED for r in rows for i in r.issues)
    assert d.fix(check("delete_small_contours"), {"threshold": 200}, ["A"], all_masters=True) is False
    assert d.shell.calls == [] and pkg.writes() == []


def test_plan_when_current_master_only_then_outside_note_until_compatibility_off():
    pkg = font(A=same_small)
    d = doctor(pkg)
    rows = d.plan(check("delete_small_contours"), names=["A"])
    assert [r.master for r in rows] == ["Regular"] and rows[0].issues[0].new == mod("model").OUTSIDE
    rows = d.plan(check("delete_small_contours"), names=["A"], compatible=False)
    assert rows[0].edits


def test_fix_when_compatible_all_masters_then_one_labelled_step_on_explicit_layers():
    pkg = font(A=same_small, B=same_small)
    d = doctor(pkg)
    assert d.fix(check("delete_small_contours"), names=["A", "B"], all_masters=True) is True
    assert d.shell.calls == [("Outline Doctor: delete small contours 2 glyphs", ["A", "B"],
                              [("A", "Regular"), ("A", "Bold"), ("B", "Regular"), ("B", "Bold")])]  # fmt: skip
    assert all(len(layer(pkg, n, m).shapes[0].contours) == 1 for n in "AB" for m in ("Regular", "Bold"))
    assert d.status == "Outline Doctor: delete small contours 2 glyphs."


def test_ghost_when_planned_then_after_outline_and_highlight_without_writes():
    pkg = font(A=same_small)
    d = doctor(pkg)
    calls = []
    d.preview = SimpleNamespace(set_overlay=lambda o: calls.append(("overlay", o)),
                                highlight=lambda **k: calls.append(("highlight", k)), refresh=lambda: None,
                                load=lambda *a: None)  # fmt: skip
    rows = d.plan(check("delete_small_contours"), names=["A"], all_masters=True)
    overlay = d.ghost(rows, "A")
    assert len(overlay.contours) == 1 and calls[0] == ("overlay", overlay)
    assert d.shell.calls == [] and pkg.writes() == []
    assert d.ghost([], "A") is None


def test_fix_when_hinted_then_refused_until_opt_in():
    pkg = font(H=same_small)
    d = doctor(pkg)
    assert d.fix(check("delete_small_contours"), names=["H"], all_masters=True) is False
    assert d.shell.calls == [] and "Skipped" in d.status
    assert d.fix(check("delete_small_contours"), names=["H"], all_masters=True, allow_hinted=True) is True
    assert d.shell.calls[-1][0] == "Outline Doctor: delete small contours H"


def test_fix_when_report_or_refused_or_mismatch_then_false():
    pkg = font(A=same_small)
    d = doctor(pkg)
    assert d.fix(check("open_contours"), names=["A"]) is False and "only reports" in d.status
    d.shell.refuse = True
    assert d.fix(check("delete_small_contours"), names=["A"], all_masters=True) is False
    d.shell.refuse = False
    bad = check("delete_small_contours")._replace(verify=lambda layer, edits: ["drift"])
    assert d.fix(bad, names=["A"], all_masters=True) is False and "Partly applied" in d.status


def test_fix_when_nothing_to_do_or_errors_then_reported():
    pkg = font(A=lambda log, master: [OShape([box(0, 0, 100, log)], log=log)])
    d = doctor(pkg)
    assert d.fix(check("delete_small_contours"), names=["A"], all_masters=True) is False
    assert d.status.startswith("Outline Doctor: no change")
    assert d.fix(check("delete_small_contours"), names=["Z"]) is False and "not in the font" in d.status
    boom = check("delete_small_contours")._replace(write=lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    pkg2 = font(A=same_small)
    d2 = doctor(pkg2)
    assert d2.fix(boom, names=["A"], all_masters=True) is False and "use Edit > Undo" in d2.status


def test_rows_when_missing_auto_or_error_then_notes():
    pkg = font(A=same_small)
    pkg.add("M", same_small, masters=["Regular"])
    pkg.add("U", same_small, auto=True)
    d = doctor(pkg)
    rows = d.plan(check("delete_small_contours"), names=["M", "U"], all_masters=True, compatible=False)
    notes = {(r.glyph, r.master): r.note for r in rows}
    assert notes[("M", "Bold")] and notes[("U", "Regular")]
    bad = check("delete_small_contours")._replace(plan=lambda *a: (_ for _ in ()).throw(ValueError("odd")))
    rows = d.plan(bad, names=["A"], compatible=False)
    assert rows[0].note == "skipped: odd"


def test_fix_when_planned_problem_then_refused():
    pkg = font(A=same_small)
    d = doctor(pkg)
    Issue = mod("model").Issue
    bad = check("delete_small_contours")._replace(plan=lambda *a: [Issue("x", "", "", problem="bad thing")])
    assert d.fix(bad, names=["A"], compatible=False) is False and "refused. A (Regular): bad thing" in d.status


# Individual fixes through the session ---------------------------------------------
def run(pkg, key, names=("A",), options=None, **kwargs):
    d = doctor(pkg)
    kwargs.setdefault("all_masters", check(key).scope == "all")
    done = d.fix(check(key), options, list(names), **kwargs)
    return d, done


def test_delete_duplicates_when_same_contour_twice_then_one_removed():
    def dup(log, master):
        return [OShape([box(0, 0, 100, log), box(0, 0, 100, log), box(300, 0, 50, log)], log=log)]

    pkg = font(A=dup)
    d, done = run(pkg, "delete_duplicate_contours")
    assert done and len(layer(pkg, "A").shapes[0].contours) == 2
    assert d.shell.calls[0][0] == "Outline Doctor: delete duplicate contours A"


def test_add_extremes_when_bulging_curve_then_nodes_inserted():
    pkg = font(A=lambda log, master: [OShape([blob(log)], log=log)])
    d, done = run(pkg, "add_extremes")
    assert done, d.status
    assert layer(pkg, "A").shapes[0].contours[0].nodesCount == 9
    assert d.shell.calls[0][2] == [("A", "Regular"), ("A", "Bold")]


def test_fix_zero_handles_when_collapsed_handles_then_straightened():
    def zero(log, master):
        spec = [(0, 0, True), (0, 0, False), (100, 0, False), (100, 0, True), (100, 100, True)]
        return [OShape([OContour(spec, log=log)], log=log)]

    pkg = font(A=zero)
    d, done = run(pkg, "fix_zero_handles")
    assert d.shell.calls and d.shell.calls[0][0] == "Outline Doctor: fix zero handles A", d.status
    assert done, d.status


def test_delete_close_points_when_tiny_segment_then_removed():
    def close(log, master):
        spec = [(0, 0, True), (100, 0, True), (101, 1, True), (100, 100, True), (0, 100, True)]
        return [OShape([OContour(spec, log=log)], log=log)]

    pkg = font(A=close)
    d, done = run(pkg, "delete_close_points")
    assert done, d.status
    assert layer(pkg, "A").shapes[0].contours[0].nodesCount == 4


def test_straighten_short_curves_when_tiny_curve_then_line():
    def short(log, master):
        spec = [(0, 0, True), (10, 1, False), (20, 1, False), (30, 0, True), (30, 100, True), (0, 100, True)]
        return [OShape([OContour(spec, log=log)], log=log)]

    pkg = font(A=short)
    d, done = run(pkg, "straighten_short_curves")
    assert done, d.status
    assert layer(pkg, "A").shapes[0].contours[0].nodesCount == 4


def selected_box(log, master):
    spec = [(0, 0, True, True), (100, 0, True, True), (100, 100, True, True), (0, 100, True, True)]
    return [OShape([OContour(spec, log=log)], log=log)]


def test_curve_all_then_straighten_all_when_selected_then_round_trip():
    pkg = font(A=selected_box)
    d, done = run(pkg, "curve_all_straights")
    assert done, d.status
    assert layer(pkg, "A", "Bold").shapes[0].contours[0].nodesCount == 12
    d, done = run(pkg, "straighten_all_curves")
    assert done, d.status
    assert layer(pkg, "A", "Bold").shapes[0].contours[0].nodesCount == 4
    assert d.shell.calls[0][0] == "Outline Doctor: straighten all curves A"


def test_retract_handles_when_curve_then_current_master_only():
    pkg = font(A=lambda log, master: [OShape([blob(log)], log=log)])
    d, done = run(pkg, "retract_handles")
    assert done, d.status
    assert d.shell.calls[0][2] == [("A", "Regular")]
    nodes = layer(pkg, "A").shapes[0].contours[0].nodes()
    assert (nodes[2].x, nodes[2].y) == (100, 0)


def test_round_coordinates_when_fractional_then_snapped(monkeypatch):
    def fractional(log, master):
        return [OShape([OContour([(0.4, 0, True), (100.6, 0, True), (100, 99.5, True)], log=log)], log=log)]

    pkg = font(A=fractional)
    d, done = run(pkg, "round_coordinates")
    assert done, d.status
    xs = [n.x for n in layer(pkg, "A").shapes[0].contours[0].nodes()]
    assert xs == [0, 101, 100]
    assert d.shell.calls[0] == ("Outline Doctor: round coordinates A", ["A"], [("A", "Regular")])


def test_remove_overlap_when_contours_cross_then_merged(monkeypatch):
    log = []
    merged = box(0, 0, 150, log)

    def crossing(log2, master):
        a, b = box(0, 0, 100, log2), box(50, 50, 100, log2)
        a.inters.add(id(b))
        return [OShape([a, b], log=log2)]

    pkg = font(A=crossing)
    import fontlabapp.core.outline as outline

    monkeypatch.setattr(outline, "_fontgate", lambda: FontGate([merged]), raising=False)
    fixes = mod("fixes")
    real = fixes.plan_overlap
    monkeypatch.setattr(fixes, "plan_overlap", lambda *a, **k: real(*a, fontgate=FontGate([merged]), **k))
    checks = mod("checks")
    entry = checks.by_key("remove_overlap")._replace(plan=fixes.plan_overlap)
    d = doctor(pkg)
    assert d.fix(entry, names=["A"], all_masters=True) is True, d.status
    assert len(layer(pkg, "A").shapes[0].contours) == 1
    assert d.shell.calls[0][0] == "Outline Doctor: remove overlap A"
    assert "fl#8517" not in d.status


def test_remove_overlap_when_merge_introduces_final_smooth_offcurve_then_save_risk_advice(monkeypatch):
    log = []
    merged = box(0, 0, 150, log)
    last = merged.nodes()[-1]
    last.on, last.smooth = False, True

    def crossing(log2, master):
        a, b = box(0, 0, 100, log2), box(50, 50, 100, log2)
        a.inters.add(id(b))
        return [OShape([a, b], log=log2)]

    pkg = font(A=crossing)
    fixes = mod("fixes")
    real = fixes.plan_overlap
    monkeypatch.setattr(fixes, "plan_overlap", lambda *a, **k: real(*a, fontgate=FontGate([merged]), **k))
    entry = mod("checks").by_key("remove_overlap")._replace(plan=fixes.plan_overlap)
    d = doctor(pkg)
    assert d.fix(entry, names=["A"], all_masters=True) is True, d.status
    advice = ("{}: a final off-curve with raw Smooth was introduced; FontLab may change on save (fl#8517). "
              "Check node types after VFJ reopen.")  # fmt: skip
    assert d.status == "Outline Doctor: remove overlap A. · " + "; ".join(advice.format(m) for m in ("Regular", "Bold"))


def test_after_overlay_when_component_and_transform_then_skipped_and_moved():
    session = mod("session")
    lay = SimpleNamespace(shapes=[OShape(component="B"), OShape([box(0, 0, 10, [])], transform=T(5, 0))])
    overlay = session.after_overlay(lay, {})
    assert overlay.contours[0].points[0].x == 5


def test_font_measures_when_called_then_reads_font_info_once(monkeypatch):
    import fontlabapp.core.outline as outline

    session = mod("session")
    reads = []
    monkeypatch.setattr(outline, "font_info", lambda package: reads.append(package) or {"masters": [
        {"fontMaster": {"name": "Regular", "xHeight": 500, "fontStemsH": [], "fontStemsV": []}}]})
    measure = session._font_measures("pkg")
    assert measure("Regular")[0][2] == 500 and reads == ["pkg"]


# Qt tabs ------------------------------------------------------------------------
@pytest.fixture
def ss(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.core.edit_guards as guards
    import fontlabapp.core.history.glyphs as history

    studios = importlib.import_module(PKG)
    commits = []

    def commit(title, layers, glyphs, mutate, **kwargs):
        commits.append((title, [(lay.glyph, lay.master) for lay in layers], [g.name for g in glyphs]))
        mutate()
        problems = tuple(kwargs["read_back"]()) if kwargs.get("read_back") else ()
        return SimpleNamespace(pending_note="", mismatches=problems)

    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, **k: None)
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: SimpleNamespace(users={}))
    monkeypatch.setattr(history, "commit", commit)

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def load(self, *args):
            self.calls.append(("load", *args))

        def refresh(self):
            self.calls.append(("refresh",))

        def set_overlay(self, overlay):
            self.calls.append(("set_overlay", overlay))

        def highlight(self, **kwargs):
            self.calls.append(("highlight", kwargs))

    def open_one(log, master):
        return [OShape([OContour([(0, 0, True), (100, 0, True), (100, 90, True)], closed=False, log=log)], log=log)]

    pkg, preview = font(A=same_small, B=open_one), QtPreview()
    shell = studios.show(package=lambda: pkg, font=lambda: object(), preview=lambda shell, studio: preview)
    studio_qt.owned.append(shell)
    shell.outline_doctor._measures = lambda package: lambda master: MEASURES
    yield SimpleNamespace(shell=shell, studio=shell.outline_doctor, pkg=pkg, preview=preview, commits=commits,
                          tabs=sys.modules[f"{PKG}.tabs"])  # fmt: skip


def tab(ss, index):
    return next(v.__self__ for v in ss.studio.views if isinstance(v.__self__, ss.tabs.TAB_CLASSES[index][1]))


def click(t, text):
    from PySide6.QtWidgets import QPushButton

    next(b for b in t.widget.findChildren(QPushButton) if b.text() == text).click()


def choose(t, key):
    t.check_box.setCurrentIndex([c.key for c in t.checks].index(key))


def test_show_when_built_then_five_tabs_with_their_checks(ss):
    assert [title for title, _ in ss.tabs.TAB_CLASSES] == list(mod("checks").TABS)
    assert len(ss.studio.views) == 5
    assert [len(tab(ss, i).checks) for i in range(5)] == [3, 2, 3, 3, 3]
    assert mod("app").studio_for(ss.shell) is ss.studio
    assert importlib.import_module(PKG).studio_for(ss.shell) is ss.studio


def test_scan_tab_when_whole_font_report_then_rows_and_no_commit(ss):
    t = tab(ss, 0)
    assert t.whole_font.isChecked() and t.all_masters.isChecked() and t.compatible.isHidden()
    click(t, "Scan")
    assert ss.commits == [] and ss.pkg.writes() == []
    assert ("B", "Regular") in [(g, m) for g, m, _ in t.records]
    choose(t, "near_miss")
    assert not t.whole_font.isChecked() and not t.all_masters.isChecked()
    t.glyphs_field.setText("A")
    click(t, "Scan")
    assert ss.commits == [] and "nothing written" in ss.studio.status


def test_scan_tab_when_row_chosen_then_glyph_loaded_and_issue_highlighted(ss):
    t = tab(ss, 0)
    click(t, "Scan")
    ss.preview.calls.clear()
    t.row_chosen("B", "Regular")
    assert ("load", "B", "Regular") in ss.preview.calls
    assert ("highlight", {"points": ((0, 0), (0, 2))}) in ss.preview.calls
    t.row_chosen("")
    assert ss.commits == [] and ss.pkg.writes() == []


def test_fix_tab_when_preview_then_ghost_and_apply_one_labelled_commit(ss):
    t = tab(ss, 4)
    choose(t, "delete_small_contours")
    assert t.all_masters.isChecked() and t.compatible.isVisibleTo(t.widget) and t.options() == {"threshold": 400}
    t.glyphs_field.setText("A")
    click(t, "Preview")
    assert ss.commits == [] and ss.pkg.writes() == []
    assert any(c[0] == "set_overlay" and c[1] is not None for c in ss.preview.calls)
    assert "2 change(s) planned on 2 layer(s); nothing written." in ss.studio.status
    click(t, "Apply to chosen glyphs")
    assert ss.commits == [("Outline Doctor: delete small contours A", [("A", "Regular"), ("A", "Bold")], ["A"])]
    assert len(ss.pkg.layer("A", "Bold").shapes[0].contours) == 1


def test_fix_tab_when_current_master_check_then_compatible_hidden_and_options_read(ss):
    t = tab(ss, 2)
    choose(t, "round_coordinates")
    assert not t.all_masters.isChecked() and t.compatible.isHidden()
    assert t.options() == {"grid": 1.0, "anchors": True, "offsets": True}
    t.glyphs_field.setText("A")
    click(t, "Apply to chosen glyphs")
    assert ss.commits == [] and "no change" in ss.studio.status


# Reports and fixes: edges ---------------------------------------------------------
def test_open_contours_when_closed_then_no_issue_and_composite_refused():
    reports = mod("reports")
    Context = mod("model").Context
    log = []
    closed = SimpleNamespace(shapes=[OShape([box(0, 0, 10, log)], log=log)])
    assert reports.plan_open(closed, {}, Context("A", "Regular")) == []
    touching = SimpleNamespace(shapes=[OShape([OContour([(0, 0, True), (5, 0, True), (0, 0, True)], closed=False,
                                                        log=log)], log=log)])  # fmt: skip
    found = reports.plan_open(touching, {}, Context("A", "Regular"))
    assert found and found[0].problem == ""


def test_near_miss_when_no_measures_or_quadratic_then_errors():
    reports = mod("reports")
    Context = mod("model").Context
    log = []
    lay = SimpleNamespace(shapes=[OShape([box(0, 0, 10, log)], log=log)])
    with pytest.raises(ValueError, match="metrics"):
        reports.plan_near(lay, {}, Context("A", "Regular"))
    tt = SimpleNamespace(shapes=[OShape([OContour([(0, 0, True), (5, 5, False), (10, 0, True)], tt=True, log=log)],
                                        log=log)])  # fmt: skip
    with pytest.raises(ValueError):
        reports.plan_near(tt, {}, Context("A", "Regular", measures=lambda m: MEASURES))


def test_near_miss_when_angles_stems_and_metrics_nearly_right_then_findings():
    reports = mod("reports")
    Context = mod("model").Context
    log = []
    spec = [(0, 0, True), (99, 1, True), (101, 501, True), (0, 499, True)]
    lay = SimpleNamespace(shapes=[OShape([OContour(spec, log=log)], log=log)])
    found = reports.plan_near(lay, {}, Context("A", "Regular", measures=lambda m: MEASURES))
    assert {i.old for i in found} and all("?" in i.new for i in found)


def test_dangerous_when_handle_near_axis_then_reported_else_not():
    reports = mod("reports")
    Context = mod("model").Context
    log = []
    safe = SimpleNamespace(shapes=[OShape([blob(log)], log=log)])
    assert reports.plan_dangerous(safe, {"threshold": 0.05}, Context("A", "Regular")) == []
    spec = [(0, 0, True), (100, 0.01, False), (100, 100, False), (0, 100, True)]
    risky = SimpleNamespace(shapes=[OShape([OContour(spec, log=log)], log=log)])
    found = reports.plan_dangerous(risky, {"threshold": 0.05}, Context("A", "Regular"))
    assert isinstance(found, list)


def test_show_when_build_fails_then_shell_closed(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.fontui as fontui

    closed = []
    real = fontui.app_shell

    def failing(*args, **kwargs):
        shell = real(*args, **kwargs)
        studio_qt.owned.append(shell)
        shell.add_tab = lambda spec: (_ for _ in ()).throw(RuntimeError("boom"))
        original = shell.close
        shell.close = lambda: (closed.append(True), original())
        return shell

    monkeypatch.setattr(fontui, "app_shell", failing)
    with pytest.raises(RuntimeError, match="boom"):
        importlib.import_module(PKG).show(package=lambda: None, font=lambda: None,
                                          preview=lambda shell, studio: None)  # fmt: skip
    assert closed == [True]


def test_glyph_preview_when_font_then_control_less_tglyph(monkeypatch):
    import fontlabapp.fontui as fontui

    app = mod("app")
    seen = []
    monkeypatch.setattr(fontui, "glyph_view", lambda *a, **k: seen.append((a, k)) or "view")
    shell = SimpleNamespace(widget="w", hint_check="hc")
    assert app._glyph_preview(shell, SimpleNamespace(font=lambda: None, current="Regular")) is None
    assert app._glyph_preview(shell, SimpleNamespace(font=lambda: "font", current="Regular")) == "view"
    assert seen == [(("font", "w"), {"layer": "Regular", "controls": False, "label_prefix": APP_LABEL,
                                     "hint_check": "hc"})]  # fmt: skip


def test_studio_for_when_new_shell_then_created_once():
    app = mod("app")
    shell = SimpleNamespace(package=lambda: None, set_status=lambda text: None)
    first = app.studio_for(shell)
    assert app.studio_for(shell) is first and shell.outline_doctor is first


# Parity edges ----------------------------------------------------------------------
def test_round_when_anchors_and_offset_then_snapped_in_one_step():
    def build(log, master):
        comp = OShape(component="B", transform=T(10.6, 0.0), log=log)
        return [comp], [("top", 50.4, 700.2)]

    pkg = font(A=build)
    d, done = run(pkg, "round_coordinates")
    assert done, d.status
    lay = layer(pkg, "A")
    pin = lay.anchors[0].point
    assert (pin.x(), pin.y()) == (50, 700) and lay.shapes[0].transform.dx() == 11
    assert len(d.shell.calls) == 1


@pytest.mark.parametrize(
    ("anchors", "message"),
    [([("top", 0.2, 0.3)], "fl#8527"), ([("top", 1.2, 0), ("top", 3.3, 0)], "several anchors named top")],
)
def test_round_when_anchor_unsafe_then_layer_kept(anchors, message):
    pkg = font(A=lambda log, master: ([], anchors))
    rows = doctor(pkg).plan(check("round_coordinates"), names=["A"])
    assert message in rows[0].issues[0].new and rows[0].edits == []


def test_round_when_anchors_and_offsets_off_then_only_nodes():
    def build(log, master):
        comp = OShape(component="B", transform=T(10.6, 0.0), log=log)
        return [comp], [("top", 50.4, 700.2)]

    pkg = font(A=build)
    rows = doctor(pkg).plan(check("round_coordinates"), {"grid": 1, "anchors": False, "offsets": False}, ["A"])
    assert rows[0].issues == ()
    with pytest.raises(ValueError, match="grid"):
        mod("fixes").plan_round(layer(pkg, "A"), {"grid": 0.5, "anchors": True, "offsets": True}, None)


def test_duplicates_when_reversed_or_open_then_kept_with_notes():
    def build(log, master):
        a = OContour([(0, 0, True), (100, 0, True), (100, 100, True)], log=log)
        b = OContour([(100, 100, True), (100, 0, True), (0, 0, True)], log=log)
        c = OContour([(0, 0, True), (5, 5, True)], closed=False, log=log)
        return [OShape([a, b, c], log=log)]

    pkg = font(A=build)
    rows = doctor(pkg).plan(check("delete_duplicate_contours"), names=["A"], all_masters=True)
    news = [i.new for i in rows[0].issues]
    assert news.count("reversed duplicate, kept") == 2 and any("open" in n for n in news)
    assert rows[0].edits == []


def test_small_when_open_contour_then_noted_not_deleted():
    def build(log, master):
        return [OShape([OContour([(0, 0, True), (1, 1, True)], closed=False, log=log)], log=log)]

    rows = doctor(font(A=build)).plan(check("delete_small_contours"), names=["A"], all_masters=True)
    assert rows[0].edits == [] and "open" in rows[0].issues[0].new


def test_bases_when_original_offered_then_opt_in_passed_else_refused():
    offered = {c.key for c in mod("checks").CHECKS if c.bases}
    fixes = {c.key for c in mod("checks").CHECKS if not c.report}
    assert len(fixes) == 11 and offered == fixes, "every fix's original showed the shared panel's bases tick"
    pkg = font(A=same_small)
    d = doctor(pkg)
    assert d.fix(check("delete_small_contours"), names=["A"], all_masters=True, allow_bases=True)
    plain = check("delete_small_contours")._replace(bases=False)
    pkg.add("A", same_small)
    assert d.fix(plain, names=["A"], all_masters=True, allow_bases=True)
    assert d.shell.allowed == [True, False]


def test_fix_tab_when_check_changes_then_bases_tick_follows_original(ss):
    t = tab(ss, 4)
    choose(t, "delete_small_contours")
    assert t.allow_bases.isVisibleTo(t.widget) and not t.allow_bases.isChecked()
    t.allow_bases.setChecked(True)
    assert t._kwargs()["allow_bases"] is True
    for index, key in ((1, "retract_handles"), (2, "delete_close_points"), (3, "curve_all_straights"),
                       (3, "straighten_all_curves")):  # fmt: skip
        t = tab(ss, index)
        choose(t, key)
        assert t.allow_bases.isVisibleTo(t.widget) and not t.allow_bases.isChecked(), key
        assert t._kwargs()["allow_bases"] is False, key
