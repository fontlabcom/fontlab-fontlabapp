# this_file: tests/test_teaching_writers_node_table.py
"""Node Table: capture, guarded apply, selection sync and panel flows with fake natives."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401

MODULE = "fontlabapp.fontui.teaching_writers.node_table"


@pytest.fixture
def nt():
    return importlib.import_module(MODULE)


class Node:
    def __init__(self, x, y, kind="line", selected=False):
        self.x, self.y, self.type, self.selected = x, y, kind, selected
        self.props = {}

    def getProperty(self, name):
        return self.props.get(name, False)

    def setProperty(self, name, value):
        self.props[name] = value


class Contour:
    def __init__(self, *nodes):
        self._nodes = list(nodes)

    def nodes(self):
        return self._nodes


def shape(sid, *contours, component=False, locked=False, refs=1):
    return NS(id=sid, isComponent=component, contentLocked=locked, contours=list(contours),
              shapeData=NS(referenceCount=refs))


def make_native(shapes, *, package_id=1, font_id=7, auto=False, locked=False, canvas="ok"):
    layer = NS(id=4, isNull=False, shapes=shapes, autoLayer=auto, isLocked=locked, isLockedI=False)
    glyph = NS(id=3, isNull=False, name="A", activeLayer=layer)
    package = NS(id=package_id, fgId=font_id, isNull=False)
    glyph.package = NS(id=package_id)
    package.findFgId = lambda gid: glyph if gid == 99 else None
    canv = NS(isNull=False, refreshed=0)
    canv.refreshAll = lambda: setattr(canv, "refreshed", canv.refreshed + 1)
    native = NS(
        flWorkspace=NS(instance=lambda: NS(currentPackage=package,
                                           getActiveCanvas=lambda: None if canvas is None else canv)),
        CurrentGlyph=lambda: NS(id=99), CurrentFont=lambda: NS(id=font_id),
        package=package, glyph=glyph, layer=layer, canvas=canv,
    )
    return native


@pytest.fixture
def stubs(monkeypatch):
    import fontlabapp.contours.writer as outlines
    import fontlabapp.core.history.glyphs as history

    state = NS(editable=None, reason=None, work=[], facts=object())
    monkeypatch.setattr(outlines, "outline_shapes", lambda layer: (
        [s for s in layer.shapes if state.editable is None or int(s.id) in state.editable], []))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: state.facts)
    monkeypatch.setattr(history, "refusal", lambda facts, name, what: state.reason)
    return state


def test_native_module_when_off_main_thread_then_refused(nt, monkeypatch):
    monkeypatch.setattr(nt, "current_thread", lambda: object())
    with pytest.raises(RuntimeError, match="main UI thread"):
        nt.native_module(NS())
    monkeypatch.undo()
    marker = NS()
    assert nt.native_module(marker) is marker
    monkeypatch.setitem(sys.modules, "fontlab", marker)
    assert nt.native_module() is marker


@pytest.mark.parametrize("mutate,message", [
    (lambda n: setattr(n.package, "isNull", True), "Open a font"),
    (lambda n: setattr(n, "CurrentGlyph", lambda: None), "Open a font"),
    (lambda n: setattr(n, "CurrentFont", lambda: NS(id=8)), "font changed"),
    (lambda n: setattr(n.package, "findFgId", lambda gid: None), "another font"),
    (lambda n: setattr(n.glyph.package, "id", 9), "another font"),
    (lambda n: setattr(n.glyph, "activeLayer", None), "no active layer"),
    (lambda n: setattr(n.layer, "isNull", True), "no active layer"),
])
def test_current_context_when_state_inconsistent_then_refused(nt, mutate, message):
    native = make_native([])
    mutate(native)
    with pytest.raises(ValueError, match=message):
        nt.current_context(native)


def test_current_context_when_consistent_then_ids_and_objects(nt):
    native = make_native([])
    context, package, glyph, layer = nt.current_context(native)
    assert context == (1, 7, 3, 4) and (package, glyph, layer) == (native.package, native.glyph, native.layer)


def test_read_rows_when_mixed_shapes_then_kept_reasons_per_row(nt, stubs):
    stubs.editable = {1}
    shapes = [
        shape(1, Contour(Node(1.0, 2.0, "move", True), Node(float("nan"), 3.0))),
        shape(2, Contour(Node(5.0, 5.0)), refs=3),
        shape(3, Contour(Node(6.0, 6.0)), refs=1),
        shape(4, Contour(Node(7.0, 7.0)), locked=True),
        shape(5, component=True),
    ]
    rows = nt.read_rows(NS(shapes=shapes), float("inf"))
    notes = [(r.key, r.kept) for r in rows]
    assert notes == [
        ((0, 0, 0), ""), ((0, 0, 1), "non-finite coordinates"),
        ((1, 0, 0), "shared outline"), ((2, 0, 0), "scaled or rotated shape"),
        ((3, 0, 0), "locked shape"), ((4, -1, -1), "component; edit its base glyph"),
    ]
    assert rows[0].selected and rows[0].kind == "move" and rows[-1].node is None


def test_read_rows_when_deadline_passed_then_no_partial_table(nt, stubs):
    with pytest.raises(TimeoutError, match="expired"):
        nt.read_rows(NS(shapes=[shape(1, Contour(Node(0.0, 0.0)))]), 0.0)
    with pytest.raises(TimeoutError, match="expired"):
        nt.read_rows(NS(shapes=[]), 0.0)


@pytest.mark.parametrize("flag,expected", [("reason", "history reason"), ("auto", "auto layer"), ("locked", "locked layer")])
def test_capture_nodes_when_layer_refused_then_every_row_kept_with_reason(nt, stubs, flag, expected):
    native = make_native([shape(1, Contour(Node(1.0, 1.0)))], auto=flag == "auto", locked=flag == "locked")
    stubs.reason = "history reason" if flag == "reason" else None
    snapshot = nt.capture_nodes(native)
    assert snapshot.context == (1, 7, 3, 4) and snapshot.facts is stubs.facts
    assert [r.kept for r in snapshot.rows] == [expected]


def test_capture_nodes_when_glyph_changes_during_read_then_refused(nt, stubs, monkeypatch):
    native = make_native([shape(1, Contour(Node(1.0, 1.0)))])
    real = nt.current_context
    calls = []

    def flip(n):
        calls.append(1)
        out = real(n)
        return ((9,) + out[0][1:],) + out[1:] if len(calls) > 1 else out

    monkeypatch.setattr(nt, "current_context", flip)
    with pytest.raises(ValueError, match="changed; refresh"):
        nt.capture_nodes(native)


def test_same_geometry_when_nan_equal_or_moved_then_selection_ignored(nt):
    row = nt.NodeRow((0, 0, 0), float("nan"), 1.0, "line", "", False, None)
    assert nt.same_geometry(row, nt.NodeRow((0, 0, 0), float("nan"), 1.0, "line", "", True, None))
    assert not nt.same_geometry(row, nt.NodeRow((0, 0, 0), float("nan"), 2.0, "line", "", False, None))
    assert not nt.same_geometry(row, nt.NodeRow((0, 0, 1), float("nan"), 1.0, "line", "", False, None))
    comp = nt.NodeRow((1, -1, -1), None, None, "component", "k", False, None)
    assert nt.same_geometry(comp, comp)
    assert not nt.same_geometry(comp, nt.NodeRow((1, -1, -1), None, 1.0, "component", "k", False, None))


def test_apply_edits_when_each_row_kind_then_independent_outcomes(nt, stubs, monkeypatch):
    import fontlabapp.contours.writer as outlines

    stubs.editable = {1}
    nodes = [Node(1.0, 1.0), Node(2.0, 2.0), Node(3.0, 3.0), Node(4.0, 4.0), Node(5.0, 5.0)]
    native = make_native([shape(1, Contour(*nodes)), shape(2, Contour(Node(9.0, 9.0)), refs=2)])
    snapshot = nt.capture_nodes(native)
    log = []

    def apply_work(work, title, facts, editor):
        (glyph, layer, edits), = work
        editor.write(layer, edits)
        assert editor.check([(glyph, edits)]) == []
        log.append((title, [(r.key, x, y) for r, x, y in edits]))
        return {"pending_updates": (7,), "pending_note": "note"}

    monkeypatch.setattr(outlines, "apply_work", apply_work)
    cells = {
        (0, 0, 0): ("1.0", "1.0"),          # unchanged text -> skipped silently
        (0, 0, 1): ("20", "2.0"),           # real edit
        (0, 0, 2): ("x", "3.0"),            # invalid text
        (0, 0, 3): ("inf", "4.0"),          # not finite
        (0, 0, 4): ("5.0", "5.0 "),         # same value after float()
        (1, 0, 0): ("10", "9.0"),           # shared outline kept
        (9, 9, 9): ("1", "1"),              # unknown key
    }
    result = nt.apply_edits(snapshot, cells, native)
    assert result.changed == 1 and result.pending_updates == (7,) and result.pending_note == "note"
    assert log == [("Node Table", [((0, 0, 1), 20.0, 2.0)])]
    assert result.kept == {
        (0, 0, 2): "invalid coordinates: could not convert string to float: 'x'",
        (0, 0, 3): "invalid coordinates: coordinates must be finite",
        (1, 0, 0): "shared outline",
        (9, 9, 9): "node changed since Refresh",
    }


def test_apply_edits_when_node_moved_since_refresh_then_kept_not_written(nt, stubs, monkeypatch):
    import fontlabapp.contours.writer as outlines

    node = Node(1.0, 1.0)
    native = make_native([shape(1, Contour(node))])
    snapshot = nt.capture_nodes(native)
    node.x = 50.0
    monkeypatch.setattr(outlines, "apply_work", lambda *a: pytest.fail("must not write"))
    result = nt.apply_edits(snapshot, {(0, 0, 0): ("2", "2")}, native)
    assert result.changed == 0 and result.kept == {(0, 0, 0): "node changed since Refresh"}


def test_apply_edits_when_context_changed_then_refused(nt, stubs):
    native = make_native([shape(1, Contour(Node(1.0, 1.0)))])
    snapshot = nt.capture_nodes(native)
    native.package.id = 2
    native.glyph.package.id = 2
    with pytest.raises(ValueError, match="refresh before Apply"):
        nt.apply_edits(snapshot, {}, native)


def test_apply_edits_when_editor_check_finds_mismatch_then_names_node(nt, stubs, monkeypatch):
    import fontlabapp.contours.writer as outlines

    node = Node(1.0, 1.0)
    native = make_native([shape(1, Contour(node))])
    snapshot = nt.capture_nodes(native)

    def apply_work(work, title, facts, editor):
        (glyph, layer, edits), = work
        return editor.check([(glyph, edits)])  # nothing was written: the check names the node

    monkeypatch.setattr(outlines, "apply_work", lambda *a: {"pending_updates": (), "pending_note": str(apply_work(*a[:1], *a[1:]))})
    result = nt.apply_edits(snapshot, {(0, 0, 0): ("5", "5")}, native)
    assert "node (0, 0, 0)" in result.pending_note


@pytest.mark.parametrize("message,suffix", [
    ("FontLab did not store 1 change(s)", True), ("other failure", False)])
def test_apply_edits_when_write_not_stored_then_undo_hint_only_for_that_error(nt, stubs, monkeypatch, message, suffix):
    import fontlabapp.contours.writer as outlines

    native = make_native([shape(1, Contour(Node(1.0, 1.0)))])
    snapshot = nt.capture_nodes(native)
    monkeypatch.setattr(outlines, "apply_work", lambda *a: (_ for _ in ()).throw(RuntimeError(message)))
    with pytest.raises(RuntimeError) as info:
        nt.apply_edits(snapshot, {(0, 0, 0): ("5", "5")}, native)
    assert ("Edit > Undo" in str(info.value)) is suffix


def selection_setup(nt, stubs, nodes=None, **kw):
    nodes = nodes or [Node(1.0, 1.0), Node(2.0, 2.0, selected=True)]
    native = make_native([shape(1, Contour(*nodes)), shape(2, component=True)], **kw)
    return native, nodes, nt.capture_nodes(native)


def test_select_nodes_when_synced_then_flags_set_and_smart_cleared(nt, stubs):
    native, nodes, snapshot = selection_setup(nt, stubs)
    nodes[1].props["__smart_selected"] = True
    failures = nt.select_nodes(snapshot, {(0, 0, 0), (1, -1, -1)}, native)
    assert failures == {(1, -1, -1): "component; edit its base glyph"}
    assert nodes[0].selected and not nodes[1].selected and nodes[1].props["__smart_selected"] is False
    assert native.canvas.refreshed == 1


def test_select_nodes_when_table_changed_or_no_canvas_then_refused(nt, stubs):
    native, nodes, snapshot = selection_setup(nt, stubs)
    nodes[0].x = 99.0
    with pytest.raises(ValueError, match="changed; refresh"):
        nt.select_nodes(snapshot, set(), native)
    nodes[0].x = 1.0
    native.flWorkspace = NS(instance=lambda: NS(currentPackage=native.package, getActiveCanvas=lambda: None))
    with pytest.raises(ValueError, match="Activate the Glyph window"):
        nt.select_nodes(snapshot, set(), native)
    other = make_native([shape(1, Contour(Node(1.0, 1.0)))])
    with pytest.raises(ValueError, match="changed; refresh"):
        nt.select_nodes(snapshot, set(), other)


class Stubborn(Node):
    """A node whose native selected flag will not change."""

    @property
    def selected(self):
        return False

    @selected.setter
    def selected(self, value):
        pass


class Exploding(Node):
    @property
    def selected(self):
        raise RuntimeError("native read failed")

    @selected.setter
    def selected(self, value):
        pass


def test_select_nodes_when_flag_will_not_stick_then_failure_named_and_other_nodes_unaffected(nt, stubs):
    stubborn = Stubborn(1.0, 1.0)
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[stubborn, Node(2.0, 2.0)])
    failures = nt.select_nodes(snapshot, {(0, 0, 0)}, native)
    assert "did not retain" in failures[(0, 0, 0)] and (0, 0, 1) not in failures


def test_select_nodes_when_native_read_and_restore_fail_then_partial_noted(nt, stubs):
    class Flaky(Node):
        """Opening read works; after the write every read fails, so restore fails too."""

        written = False
        armed = False

        @property
        def selected(self):
            if Flaky.written:
                raise RuntimeError("native read failed")
            return False

        @selected.setter
        def selected(self, value):
            Flaky.written = Flaky.armed

    Flaky.written = Flaky.armed = False
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[Node(0.0, 0.0), Flaky(1.0, 1.0)])
    Flaky.armed = True
    failures = nt.select_nodes(snapshot, {(0, 0, 1)}, native)
    assert "native read failed" in failures[(0, 0, 1)] and "selection may remain partial" in failures[(0, 0, 1)]


def test_select_nodes_when_flags_change_during_canvas_refresh_then_failure(nt, stubs):
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[Node(1.0, 1.0), Node(2.0, 2.0)])
    native.canvas.refreshAll = lambda: setattr(nodes[0], "selected", False)
    failures = nt.select_nodes(snapshot, {(0, 0, 0)}, native)
    assert "changed during canvas refresh" in failures[(0, 0, 0)]

    class Late(Node):
        armed = False

        @property
        def selected(self):
            if Late.armed:
                raise RuntimeError("late read failed")
            return self._sel

        @selected.setter
        def selected(self, value):
            self._sel = value

    late = Late(1.0, 1.0)
    late._sel = False
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[late, Node(2.0, 2.0)])
    native.canvas.refreshAll = lambda: setattr(Late, "armed", True)
    failures = nt.select_nodes(snapshot, {(0, 0, 0)}, native)
    Late.armed = False
    assert failures[(0, 0, 0)] == "late read failed"


# ----- panel -----

def rows(nt, *specs):
    return tuple(nt.NodeRow((0, 0, i), x, y, "line", note, sel, None if note == "component" else object())
                 for i, (x, y, note, sel) in enumerate(specs))


@pytest.fixture
def panel_env(nt, studio_qt, monkeypatch):  # noqa: F811
    qt = sys.modules["PythonQt"]
    data = rows(nt, (1.0, 2.0, "", False), (3.0, 4.0, "locked shape", True))
    snapshot = NS(rows=data, context=(1, 2, 3, 4), facts="facts")
    env = NS(qt=qt, snapshot=snapshot, writes=[], selects=[], fail=None)
    monkeypatch.setattr(nt, "capture_nodes", lambda native=None, facts=None: (
        (_ for _ in ()).throw(env.fail) if env.fail else env.snapshot))
    monkeypatch.setattr(nt, "select_nodes", lambda snap, keys: env.selects.append(keys) or env.selects_result)
    env.selects_result = {}
    monkeypatch.setattr(nt, "apply_edits", lambda snap, cells: env.writes.append(cells) or env.apply_result)
    env.apply_result = NS(changed=1, kept={(0, 0, 1): "locked shape"}, facts="facts2", pending_note="")
    return env


@pytest.mark.parametrize("embedded", [False, True])
def test_panel_refresh_apply_and_selection_flows(nt, panel_env, embedded):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=embedded)
    assert panel.snapshot_data is env.snapshot and "2 rows" in panel.status_line.text()
    assert panel.node_table.rowCount() == 2
    assert not panel.staged_edits()
    panel.node_table.item(0, 3).setText("7")
    assert panel.staged_edits()
    panel.node_table.item(0, 3).setText("oops")
    assert panel.staged_edits()
    panel.write_cells()
    assert set(env.writes[-1]) == {(0, 0, 0), (0, 0, 1)}
    assert "Changed 1 nodes; kept 1 attempted rows. Apply is recorded as one Undo step." in panel.status_line.text()
    env.apply_result = NS(changed=0, kept={}, facts="f", pending_note="pending")
    panel.write_cells()
    assert "No coordinate write." in panel.status_line.text() and panel.status_line.text().endswith("· pending")
    panel.node_table.selectRow(0)
    assert env.selects[-1] == {(0, 0, 0)} and "synchronized" in panel.status_line.text()
    env.selects_result = {(0, 0, 0): "stuck"}
    panel.write_selection()
    assert "Unsynced row (0, 0, 0): stuck" in panel.status_line.text()
    panel.read_selection()
    panel.close()
    assert panel not in nt._PANELS


@pytest.mark.parametrize("embedded", [False, True])
def test_panel_when_compact_then_actions_share_one_visible_row(nt, panel_env, embedded):
    panel = nt.show(panel_env.qt, None, embedded=embedded)
    try:
        panel.resize(420, 320)
        panel.show()
        panel_env.qt.QtCore.QCoreApplication.processEvents()
        buttons = panel.findChildren(panel_env.qt.QtGui.QPushButton)
        assert [button.text() for button in buttons] == ["Refresh", "Read Canvas Selection", "Apply"]
        rects = [button.geometry() for button in buttons]
        assert len({rect.top() for rect in rects}) == 1
        assert all(left.right() < right.left() for left, right in zip(rects, rects[1:]))
        assert all(panel.rect().contains(rect) for rect in rects)
        assert panel.node_table.geometry().bottom() < rects[0].top()
        assert all(button.fontMetrics().horizontalAdvance(button.text()) <= button.width() for button in buttons)
        for button in buttons:
            button.click()
        assert panel_env.writes and "Changed 1 nodes" in panel.status_line.text()
    finally:
        panel.close()


def test_panel_when_capture_or_apply_fail_then_status_and_cleared_table(nt, panel_env):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=True)
    env.fail = ValueError("Open a font and a glyph first.")
    panel.refresh_nodes()
    assert panel.snapshot_data is None and panel.node_table.rowCount() == 0
    assert panel.status_line.text() == "Open a font and a glyph first."
    panel.write_cells()
    assert panel.status_line.text() == "Refresh the node table first."
    panel.write_selection()  # no snapshot -> silent
    panel.read_selection()
    assert panel.status_line.text() == "Refresh the node table first."
    assert not panel.staged_edits()
    env.fail = None
    panel.refresh_nodes()
    panel.lab_check_target = lambda: (_ for _ in ()).throw(RuntimeError("wrong target"))
    panel.write_cells()
    assert panel.status_line.text() == "wrong target"
    del panel.lab_check_target
    env.fail = ValueError("gone")  # post-Apply refresh fails: write is still reported
    panel.write_cells()
    assert "Changed 1 nodes" in panel.status_line.text() and "Refresh failed: gone" in panel.status_line.text()
    assert panel.snapshot_data is None
    panel.close()


def test_panel_when_glyph_changes_after_apply_then_refresh_failure_reported(nt, panel_env):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=False)
    first = env.snapshot
    env.snapshot = NS(rows=first.rows, context=(9, 9, 9, 9), facts="f")
    panel.write_cells()
    assert "Current glyph changed after Apply" in panel.status_line.text()
    panel.close()


def test_panel_read_selection_when_geometry_changed_then_refused(nt, panel_env):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=True)
    moved = nt.NodeRow((0, 0, 0), 99.0, 2.0, "line", "", False, object())
    env.snapshot = NS(rows=(moved, env.snapshot.rows[1]), context=(1, 2, 3, 4), facts="f")
    panel.read_selection()
    assert "Refresh before reading selection" in panel.status_line.text()
    panel.write_selection_failure = None
    panel.close()


def test_panel_close_when_cleanup_fails_then_retained_and_destroy_releases(nt, panel_env):
    panel = nt.show(panel_env.qt, None, embedded=True)
    panel.signal_scope.finish = lambda destroyed=False: False
    event = NS()
    event.ignore = lambda: setattr(event, "ignored", True)
    event.accept = lambda: setattr(event, "accepted", True)
    panel.closeEvent(event)
    assert event.ignored and panel in nt._PANELS
    del panel.signal_scope.finish
    panel.release_owner()
    assert panel not in nt._PANELS and panel.snapshot_data is None


def test_show_when_setup_fails_then_scope_finished_and_error_reraised(nt, panel_env, monkeypatch):
    qt = panel_env.qt
    monkeypatch.setattr(qt.QtGui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("no screen")))
    before = list(nt._PANELS)
    with pytest.raises(RuntimeError, match="no screen"):
        nt.show(qt, None)
    assert nt._PANELS == before


def test_main_when_show_refuses_then_prints_title_and_reason(nt, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: "window"))
    monkeypatch.setitem(sys.modules, "PythonQt", NS())
    seen = []
    monkeypatch.setattr(nt, "show", lambda qt, parent: seen.append(parent))
    nt.main()
    assert seen == ["window"]
    monkeypatch.setattr(nt, "show", lambda qt, parent: (_ for _ in ()).throw(TimeoutError("slow")))
    nt.main()
    assert capsys.readouterr().out == "Node Table: slow\n"


class SmartStuck(Node):
    """Selected flag works but the smart flag never changes, so verification fails after the write."""

    def setProperty(self, name, value):
        pass


def test_select_nodes_when_write_sticks_but_verification_fails_then_opening_flags_restored(nt, stubs):
    stuck = SmartStuck(1.0, 1.0, selected=True)
    stuck.props["__smart_selected"] = True
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[stuck, Node(2.0, 2.0)])
    failures = nt.select_nodes(snapshot, set(), native)  # deselect: selected True -> False, smart wanted False
    assert failures == {(0, 0, 0): "native selection flags did not retain the requested state"}
    assert stuck.selected is True  # opening flag put back after the failed verification
    assert stuck.props["__smart_selected"] is True


def test_select_nodes_when_only_selected_flag_sticks_then_smart_flag_restored(nt, stubs):
    class SelectedStuck(Node):
        """Smart writes stick but `selected` stays True, so verification fails and the smart flag needs restoring."""

        @property
        def selected(self):
            return True

        @selected.setter
        def selected(self, value):
            pass

    node = SelectedStuck(1.0, 1.0)
    node.props["__smart_selected"] = True
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[node, Node(2.0, 2.0)])
    failures = nt.select_nodes(snapshot, set(), native)  # wants selected False, smart False
    assert failures == {(0, 0, 0): "native selection flags did not retain the requested state"}
    assert node.props["__smart_selected"] is True  # restore wrote the opening smart flag back


def test_select_nodes_when_restore_cannot_hold_then_opening_not_retained_noted(nt, stubs):
    class Drift(SmartStuck):
        """Selected flips freely, but restoring never sticks (setter ignores True)."""

        _flag = True

        @property
        def selected(self):
            return Drift._flag

        @selected.setter
        def selected(self, value):
            if value is False:
                Drift._flag = False

    node = Drift(1.0, 1.0)
    Drift._flag = True  # after construction: Node.__init__ writes selected
    node.props["__smart_selected"] = True
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[node, Node(2.0, 2.0)])
    failures = nt.select_nodes(snapshot, set(), native)
    assert failures[(0, 0, 0)] == (
        "native selection flags did not retain the requested state; selection may remain partial: "
        "opening selection flags were not retained"
    )


@pytest.mark.parametrize(
    ("opening", "smart", "wanted", "expected_smart"),
    [
        (True, True, False, False),   # deselect clears the smart flag
        (True, True, True, True),     # stays selected: smart flag kept
        (False, True, False, True),   # was not selected, stays so: smart flag untouched
        (False, True, True, True),    # newly selected: smart flag untouched
    ],
)
def test_select_nodes_when_smart_flag_then_only_deselect_of_selected_clears_it(
    nt, stubs, opening, smart, wanted, expected_smart
):
    node = Node(1.0, 1.0, selected=opening)
    node.props["__smart_selected"] = smart
    native, nodes, snapshot = selection_setup(nt, stubs, nodes=[node, Node(2.0, 2.0)])
    failures = nt.select_nodes(snapshot, {(0, 0, 0)} if wanted else set(), native)
    assert failures == {}
    assert node.selected is wanted and node.props["__smart_selected"] is expected_smart


def test_apply_edits_when_node_vanished_since_refresh_then_kept_not_written(nt, stubs, monkeypatch):
    import fontlabapp.contours.writer as outlines

    first, second = Node(1.0, 1.0), Node(2.0, 2.0)
    contour = Contour(first, second)
    native = make_native([shape(1, contour)])
    snapshot = nt.capture_nodes(native)
    contour._nodes.pop()  # the second node no longer exists
    monkeypatch.setattr(outlines, "apply_work", lambda *a: pytest.fail("must not write"))
    result = nt.apply_edits(snapshot, {(0, 0, 1): ("9", "9")}, native)
    assert result.changed == 0 and result.kept == {(0, 0, 1): "node changed since Refresh"}


def test_apply_edits_when_node_y_or_kind_changed_since_refresh_then_kept(nt, stubs, monkeypatch):
    import fontlabapp.contours.writer as outlines

    monkeypatch.setattr(outlines, "apply_work", lambda *a: pytest.fail("must not write"))
    for attr, value in (("y", 50.0), ("type", "curve")):
        node = Node(1.0, 1.0)
        native = make_native([shape(1, Contour(node))])
        snapshot = nt.capture_nodes(native)
        setattr(node, attr, value)
        result = nt.apply_edits(snapshot, {(0, 0, 0): ("2", "2")}, native)
        assert result.changed == 0 and result.kept == {(0, 0, 0): "node changed since Refresh"}, attr


@pytest.mark.parametrize("change", ["context", "count", "y", "kind"])
def test_panel_read_selection_when_each_guard_trips_then_refused(nt, panel_env, change):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=True)
    rows = list(env.snapshot.rows)
    context = env.snapshot.context
    if change == "context":
        context = (9, 9, 9, 9)
    elif change == "count":
        rows = rows[:1]
    elif change == "y":
        rows[0] = nt.NodeRow(rows[0].key, rows[0].x, 99.0, rows[0].kind, "", False, object())
    else:
        rows[0] = nt.NodeRow(rows[0].key, rows[0].x, rows[0].y, "curve", "", False, object())
    env.snapshot = NS(rows=tuple(rows), context=context, facts="f")
    panel.read_selection()
    assert panel.status_line.text() == "Node geometry changed; Refresh before reading selection."
    panel.close()


class FakeSignal:
    def __init__(self):
        self.calls = []

    def connect(self, call):
        self.calls.append(call)

    def disconnect(self, call):
        self.calls.remove(call)

    def emit(self, *args):
        for call in list(self.calls):
            call(*args)


@pytest.fixture
def history_items(monkeypatch):
    items = NS(historyIndexChanged=FakeSignal(), historyChanged=FakeSignal(), glyphUpdated=FakeSignal())
    native = NS(flItems=NS(instance=lambda: NS(qobject=items)))
    monkeypatch.setitem(sys.modules, "fontlab", native)
    return items


def test_panel_when_undo_redo_changes_outline_then_table_follows(nt, panel_env, history_items):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=True)
    try:
        assert all(len(signal.calls) == 1 for signal in vars(history_items).values())
        history_items.historyIndexChanged.emit()
        assert panel.history_timer.isActive() and panel.history_timer.isSingleShot()
        panel.history_timer.stop()
        moved = nt.NodeRow((0, 0, 0), 50.0, 2.0, "line", "", False, object())
        env.snapshot = NS(rows=(moved, env.snapshot.rows[1]), context=(1, 2, 3, 4), facts="f")
        panel.follow_change()
        assert panel.snapshot_data is env.snapshot
        assert float(panel.node_table.item(0, 3).text()) == 50.0
        assert "2 rows" in panel.status_line.text()
    finally:
        panel.close()
    assert all(signal.calls == [] for signal in vars(history_items).values())


def test_panel_when_outline_changes_with_staged_cells_then_cells_kept_and_status_says_so(
    nt, panel_env, history_items
):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=False)
    panel.node_table.item(0, 3).setText("7")
    moved = nt.NodeRow((0, 0, 0), 50.0, 2.0, "line", "", False, object())
    shown = panel.snapshot_data
    env.snapshot = NS(rows=(moved, shown.rows[1]), context=(1, 2, 3, 4), facts="f")
    panel.follow_change()
    assert panel.snapshot_data is shown and panel.node_table.item(0, 3).text() == "7"
    assert "Refresh discards your cell edits" in panel.status_line.text()
    panel.close()


def test_panel_when_geometry_same_or_glyph_changed_or_unreadable_then_table_kept(
    nt, panel_env, history_items
):
    env = panel_env
    panel = nt.show(env.qt, None, embedded=False)
    env.apply_result = NS(changed=1, kept={(0, 0, 1): "locked shape"}, facts="f", pending_note="")
    panel.write_cells()
    applied = panel.status_line.text()
    shown = panel.snapshot_data
    env.snapshot = NS(rows=shown.rows, context=(1, 2, 3, 4), facts="f")  # Apply's own signal
    panel.follow_change()
    assert panel.snapshot_data is shown and panel.status_line.text() == applied
    assert panel.node_table.item(1, 6).text() == "Kept: locked shape"
    env.snapshot = NS(rows=shown.rows[:1], context=(9, 9, 9, 9), facts="f")  # another glyph
    panel.follow_change()
    env.fail = ValueError("Open a glyph first.")
    panel.follow_change()
    assert panel.snapshot_data is shown and panel.status_line.text() == applied
    env.fail = None
    panel.snapshot_data = None
    panel.follow_change()
    assert panel.snapshot_data is None
    panel.close()


def test_panel_when_fontlab_missing_or_incomplete_then_no_follow(nt, panel_env, monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlab", NS())
    panel = nt.show(panel_env.qt, None, embedded=True)
    assert not hasattr(panel, "history_timer")
    panel.close()
    monkeypatch.setitem(sys.modules, "fontlab", NS(flItems=NS(instance=lambda: NS(qobject=NS()))))
    panel = nt.show(panel_env.qt, None, embedded=True)
    assert panel.history_timer.interval() == nt._HISTORY_DELAY_MS
    panel.close()
