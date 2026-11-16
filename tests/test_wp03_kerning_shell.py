# this_file: tests/test_wp03_kerning_shell.py
"""WP03 shell routing preserves per-tab staged actions."""
from types import SimpleNamespace

from _studio_qt import studio_qt  # noqa: F401


def test_bind_actions_when_read_and_write_panels_then_route_without_writes(studio_qt):  # noqa: F811
    from fontlabapp.studios._kerning_app import bind_actions

    calls, bindings = [], {}
    shell = SimpleNamespace(set_actions=lambda widget, **actions: bindings.update({widget: actions}))
    tool = SimpleNamespace(reload=lambda: calls.append("reload"), views=[])
    class Panel:
        widget = "writer"
        ACTION = "Round values"
        def refresh(self):
            calls.append("preview")
        def apply(self):
            calls.append("apply")
        def ready(self):
            return True
    panel = Panel()
    tool.views.append(panel.refresh)
    bind_actions(shell, tool)
    assert calls == []
    actions = bindings["writer"]
    actions["refresh"]()
    actions["preview"]()
    assert actions["ready"]()
    actions["apply"]()
    assert actions["apply_label"] == "Round values"
    assert calls == ["reload", "preview", "apply"]
    panel.apply = None
    bind_actions(shell, tool)
    assert bindings["writer"]["apply"] is None


def test_consolidated_browser_when_opened_then_persistence_and_groups(studio_qt):  # noqa: F811
    from fontlabapp.studios.kerning_browser.app import show
    shell = show(package=lambda: None, font=lambda: None, consolidated=True)
    try:
        titles = [shell.tabs.tabText(i) for i in range(shell.tabs.count())]
        assert titles[-3:] == ["Same groups", "Persistence", "About"]
        assert shell.kerning_tool.package is None
        exceptions = next(v.__self__ for v in shell.kerning_tool.views
                          if type(v.__self__).__name__ == "ExceptionsPanel")
        groups = next(v.__self__ for v in shell.kerning_tool.views
                      if type(v.__self__).__name__ == "GroupsPanel")
        groups.clear()
        assert groups.groups.peers == {}
        exceptions.pair_chosen(-1)
        actions = shell._actions[exceptions.widget]
        assert not actions["ready"]() and not actions["dirty"]()
    finally:
        shell.close()


def test_consolidated_batch_when_opened_then_five_mapped_tabs(studio_qt):  # noqa: F811
    from fontlabapp.studios.kerning_batch.app import show
    shell = show(package=lambda: None, font=lambda: None, consolidated=True)
    try:
        assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == [
            "Round", "Scale", "Remove small", "Clamp", "Copy masters", "About"]
    finally:
        shell.close()


def test_consolidated_studio_when_opened_then_mapped_tabs_and_frozen_font(studio_qt):  # noqa: F811
    from fontlabapp.studios.kerning_studio.app import show
    current = [None]
    shell = show(package=lambda: current[0], font=lambda: current[0], consolidated=True)
    try:
        assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == [
            "Glyph pairs", "Tighten", "Kern To Max", "Delete selected pairs", "Steal next pair", "Pair Editor", "Punctuation", "About"]
        current[0] = object()
        import pytest
        with pytest.raises(ValueError, match="original font"):
            shell.package()
        assert shell.kerning_studio.font() is None
        assert shell.kerning_tool.font() is None
    finally:
        shell.close()


def test_browser_when_current_font_changes_then_keeps_original_target(studio_qt):  # noqa: F811
    from fontlabapp.studios.kerning_browser.app import show
    current = [None]
    shell = show(package=lambda: current[0], font=lambda: current[0])
    try:
        current[0] = object()
        shell.kerning_tool.reload()
        import pytest
        with pytest.raises(ValueError, match="original font"):
            shell.package()
        assert shell.kerning_tool.font() is None
    finally:
        shell.close()


def test_pair_editor_when_cells_staged_then_one_batch_and_sorted_identity(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_studio.pairs import PairEditorPanel
    from fontlabapp.studios import _kerning
    from fontlabapp.kerning.edit import model
    from fontlabapp import fontui

    writes = []
    shell = fontui.app_shell("test", package=lambda: tool.package)
    tool = _kerning.Tool(shell, "Kerning Studio", font=lambda: None)
    tool.package = SimpleNamespace(masters=["Regular", "Bold"])
    tool.masters, tool.current = ["Regular", "Bold"], "Regular"
    monkeypatch.setattr(fontui, "kerning_snapshot", lambda package: "snapshot")
    monkeypatch.setattr(model, "involving", lambda *args: {("A", "V"): {"Regular": -50}, ("A", "W"): {"Bold": 0}})
    monkeypatch.setattr(model, "partner_exists", lambda *args: args[-1][1] != "missing")
    monkeypatch.setattr(tool, "write", lambda *args: writes.append(args) or True)
    monkeypatch.setattr(model, "class_sides", lambda *args: (None, None))
    from fontlabapp.studios.kerning_studio import pairs as pairs_module
    monkeypatch.setattr(pairs_module, "current_glyph_name", lambda package: None)
    monkeypatch.setattr(tool.backends().batch, "validate_pair", lambda *args: None)
    panel = PairEditorPanel(tool)
    try:
        panel.glyph_field.setText("A")
        panel.refresh()
        panel.set_cell("A", "V", "Regular", "-75")
        panel.set_cell("A", "W", "Bold", "")
        assert panel.ready()
        panel.partner.setText("missing")
        panel.add_row()
        assert ("A", "missing") not in panel.rows
        panel.partner.setText("@Right")
        panel.add_row()
        panel.set_cell("A", "@Right", "Bold", "0")
        assert writes == []
        panel.table.sortItems(0)
        panel.set_cell("A", "V", "Bold", "-20")
        assert panel.apply()
        assert writes[0][2] == {"Regular": {("A", "V"): -75}, "Bold": {("A", "W"): None, ("A", "@Right"): 0, ("A", "V"): -20}}
        assert writes[0][3] == "snapshot"
    finally:
        shell.close()


def test_check_table_when_resorted_then_ticked_source_identity_is_stable(studio_qt):  # noqa: F811
    from fontlabapp.studios._kerning_ui import CheckTable
    from PythonQt import QtCore, QtGui
    widget = QtGui.QWidget()
    table = CheckTable(widget, QtGui.QVBoxLayout(widget), ["Name", "Value"])
    table.set_rows([("Z", 1), ("A", 2)], [True, False])
    table.view.sortItems(0, QtCore.Qt.AscendingOrder)
    assert table.ticked() == [0]
    assert table.text(0, 0) == "Z"
    table.set_ticked({1})
    assert table.ticked() == [1]
    widget.close()


def test_persistence_when_explicit_zero_risk_and_master_filter_then_exact_rows(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_browser.consolidated import PersistencePanel, model
    from fontlabapp.studios._kerning import Tool
    from fontlabapp import fontui

    snapshot = model.AuditSnapshot(1, ("Regular", "Bold"), "Regular", 1000,
                                  (("Regular", (("A", "V", 0), ("A", "W", -2100))),
                                   ("Bold", (("A", "V", -40),))))
    shell = fontui.app_shell("test", package=lambda: object())
    tool = Tool(shell, "Kerning Browser", font=lambda: None)
    tool.package, tool.masters, tool.current = object(), ["Regular", "Bold"], "Regular"
    seen = []
    monkeypatch.setattr(model, "capture", lambda p: snapshot)
    monkeypatch.setattr(model, "ensure_snapshot", lambda p, s: seen.append(s))
    monkeypatch.setattr(tool, "show_pair", lambda *args: seen.append(args))
    panel = PersistencePanel(tool)
    try:
        panel.refresh()
        assert len(panel.rows) == 2
        assert panel.rows[("A  V", "Regular")].value == 0
        assert panel.rows[("A  W", "Regular")].at_risk
        panel.scope.setCurrentIndex(1)
        assert len(panel.rows) == 3
        panel.search.setText("Bold")
        assert list(panel.rows) == [("A  V", "Bold")]
        panel.row_chosen("A  V", "Bold")
        assert seen[-1] == ("A", "V", "Bold")
        panel.row_chosen("missing", "Bold")
        assert seen[-1] == ("A", "V", "Bold")
        monkeypatch.setattr(model, "capture", lambda p: (_ for _ in ()).throw(ValueError("stale")))
        panel.reload_view()
        assert panel.rows == {} and panel.snapshot is None
    finally:
        shell.close()


def test_pair_editor_when_invalid_stale_or_empty_then_drafts_survive(studio_qt, monkeypatch):  # noqa: F811
    import pytest
    from fontlabapp.studios.kerning_studio.pairs import PairEditorPanel
    from fontlabapp.studios._kerning import Tool
    from fontlabapp.kerning.edit import model
    from fontlabapp import fontui
    shell = fontui.app_shell("test", package=lambda: tool.package)
    tool = Tool(shell, "Kerning Studio", font=lambda: None)
    monkeypatch.setattr(model, "class_sides", lambda *args: (None, None))
    from fontlabapp.studios.kerning_studio import pairs as pairs_module
    monkeypatch.setattr(pairs_module, "current_glyph_name", lambda package: None)
    monkeypatch.setattr(tool.backends().batch, "validate_pair", lambda *args: None)
    panel = PairEditorPanel(tool)
    try:
        panel.refresh()
        panel.add_row()
        assert not panel.apply()
        with pytest.raises(ValueError, match="Add"):
            panel.set_cell("A", "V", "Regular", "1")
        tool.package, tool.masters = SimpleNamespace(masters=["Regular"]), ["Regular"]
        monkeypatch.setattr(fontui, "kerning_snapshot", lambda p: "snap")
        monkeypatch.setattr(model, "involving", lambda *args: {("A", "V"): {"Regular": -5}})
        monkeypatch.setattr(model, "partner_exists", lambda *args: True)
        panel.glyph_field.setText("A")
        panel.refresh()
        panel.set_cell("A", "V", "Regular", "bad")
        assert panel.errors and not panel.ready()
        panel.refresh()
        assert panel.errors
        panel.set_cell("A", "V", "Regular", "-15")
        panel.side.setCurrentIndex(1)
        panel.partner.setText("W")
        panel.add_row()
        assert ("W", "A") in panel.rows
        panel.fill()
        assert panel.staged
        panel.cell_edited(panel.table.item(0, 0))
        panel.row_chosen(-1)
        seen = []
        monkeypatch.setattr(tool, "show_pair", lambda *args: seen.append(args))
        panel.row_chosen(0)
        assert seen
        monkeypatch.setattr(tool, "write", lambda *args: (_ for _ in ()).throw(ValueError("stale")))
        drafts, errors = dict(panel.staged), dict(panel.errors)
        assert not panel.apply()
        assert panel.staged == drafts and panel.errors == errors and not panel.ready()
        panel.revert()
        assert not panel.staged and not panel.errors
    finally:
        shell.close()


def test_staged_studio_when_action_selected_then_preview_before_writer(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_studio.staged import StagedStudio
    from fontlabapp import fontui
    calls = []
    shell = SimpleNamespace(package=lambda: "package", set_status=lambda text: calls.append(text))
    studio = StagedStudio(shell, font=lambda: None)
    studio.snapshot = "snapshot"
    studio.native = {"Regular": {}}
    monkeypatch.setattr(fontui, "write_kerning", lambda *args, **kw: calls.append((args, kw)) or True)
    studio.reload = lambda: calls.append("reload")
    assert studio.write("Set", "A V", lambda: {"Regular": {("A", "V"): 0}})
    assert not any(isinstance(c, tuple) for c in calls)
    assert studio.ready()
    assert studio.preview_changes() == {"Regular": {("A", "V"): 0}}
    assert studio.apply_changes()
    assert calls[-2][0][1] == {"Regular": {("A", "V"): 0}}
    assert calls[-2][1] == {"expected": "snapshot"}
    assert not studio.ready()


def test_staged_studio_when_refused_or_failed_then_no_accepted_write(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_studio.staged import StagedStudio
    from fontlabapp import fontui
    statuses = []
    package = [None]
    shell = SimpleNamespace(package=lambda: package[0], set_status=statuses.append)
    studio = StagedStudio(shell, font=lambda: None)
    assert not studio.ready() and not studio.apply_changes()
    assert studio.preview_changes() == {}
    assert not studio.write("Set", "pair", lambda: {})
    package[0], studio.snapshot, studio.native = object(), "snapshot", {"Regular": {}}
    assert not studio.write("Set", "pair", lambda: {})
    assert not studio.write("Set", "pair", lambda: (_ for _ in ()).throw(ValueError("invalid")))
    assert studio.write("Delete", "pair", lambda: {"Regular": {("A", "V"): None}})
    assert "delete" in statuses[-1]
    monkeypatch.setattr(fontui, "write_kerning", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("partial; use Undo")))
    assert not studio.apply_changes()
    assert "partial; use Undo" in statuses[-1]
    assert not studio.ready()
    studio.reload = lambda: statuses.append("reload")
    assert studio.write("Set", "pair", lambda: {"Regular": {("A", "V"): -20}})
    studio.discard()
    assert not studio.ready() and statuses[-1] == "reload"


def test_source_capture_when_wrappers_change_or_font_closes_then_identity_guard(studio_qt):  # noqa: F811
    import pytest
    from fontlabapp.studios._kerning_app import capture_source
    original = SimpleNamespace(id=1, isNull=False)
    source = [original]
    bound = capture_source(lambda: source[0])
    source[0] = SimpleNamespace(id=1, isNull=False)
    assert bound() is original
    source[0] = None
    with pytest.raises(ValueError, match="original font"):
        bound()
    source[0], original.isNull = original, True
    with pytest.raises(ValueError, match="closed"):
        bound()


def test_sort_item_when_numeric_text_then_numeric_and_text_order(studio_qt):  # noqa: F811
    from fontlabapp.studios._kerning_ui import SortItem
    assert SortItem("-100") < SortItem("-20")
    assert not SortItem("100") < SortItem("20")
    assert SortItem("A") < SortItem("V")


def test_staged_studio_when_controls_change_then_apply_requires_restaging(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_studio.staged import StagedStudio
    from PythonQt import QtGui
    from fontlabapp import fontui
    shell = SimpleNamespace(package=lambda: "package", set_status=lambda text: None)
    studio = StagedStudio(shell, font=lambda: None)
    studio.snapshot, studio.native = "snapshot", {"Regular": {}}
    class Panel:
        def refresh(self):
            return None
    panel = Panel()
    panel.value_field, panel.master_box, panel.height_box = QtGui.QLineEdit("-100"), QtGui.QComboBox(), QtGui.QDoubleSpinBox()
    panel.master_box.addItems(["Regular", "Bold"])
    panel.grid = {"Regular": QtGui.QLineEdit("10")}
    studio.views = [panel.refresh]
    writes = []
    monkeypatch.setattr(fontui, "write_kerning", lambda *a, **k: writes.append(a))
    for change in (lambda: panel.value_field.setText("-200"), lambda: panel.master_box.setCurrentIndex(1),
                   lambda: panel.height_box.setValue(10), lambda: panel.grid["Regular"].setText("20")):
        assert studio.write("Set", "A V", lambda: {"Regular": {("A", "V"): -100}})
        assert studio.ready()
        change()
        assert not studio.ready()
        assert not studio.apply_changes()
    assert writes == []


def test_pair_editor_when_write_completed_but_preview_fails_then_clear_and_report_undo(studio_qt):  # noqa: F811
    from fontlabapp.studios.kerning_studio.pairs import PairEditorPanel
    messages, cleared = [], []
    def fail():
        raise RuntimeError('preview unavailable')
    panel = SimpleNamespace(ready=lambda: True, staged={(('A','V'),'Regular'): -30}, snapshot='snapshot',
                            tool=SimpleNamespace(write=lambda *args: True, say=messages.append,
                                                 preview=SimpleNamespace(refresh=fail)),
                            run=lambda callback: callback(), revert=lambda: None,
                            clear=lambda: cleared.append(True))
    assert not PairEditorPanel.apply(panel)
    assert cleared and 'Kerning was applied; preview failed' in messages[-1]
    assert 'Undo' in messages[-1] and 'Refresh' in messages[-1]


def test_shared_assembly_when_initial_binding_fails_then_complete_window_recovers(studio_qt):  # noqa: F811
    from fontlabapp.studios.advance_widths.app import show
    source = [RuntimeError('initial binding')]
    def package():
        if isinstance(source[0], Exception):
            raise source[0]
        return source[0]
    shell = show(package=package, font=lambda: None, preview=lambda *args: None)
    try:
        assert shell.widget.isVisible() and shell.close_button and shell.refresh_button
        assert 'initial binding' in shell.status.text()
        assert shell.kerning_tool.package is None
        source[0] = None
        shell.refresh_button.click()
        assert 'initial binding' not in shell.status.text()
    finally:
        shell.close_button.click()
    assert shell._delete_scheduled


def test_shared_assembly_when_initial_failure_then_recovery_binds_preview_and_target_together(studio_qt):  # noqa: F811
    from fontlabapp.studios.kerning_browser.app import show
    from PythonQt import QtGui
    state = SimpleNamespace(error=True, package=SimpleNamespace(id=1, masters=[], master='', isNull=False))
    captured = []
    def package():
        if state.error:
            raise RuntimeError('initial binding')
        return state.package
    def preview(shell, tool):
        captured.append(tool.font())
        widget = QtGui.QWidget()
        widget.set_layer = lambda master: None
        return widget
    shell = show(package=package, font=lambda: state.package.id, preview=preview)
    try:
        assert not captured and shell.kerning_tool.preview is None
        state.package = SimpleNamespace(id=2, masters=[], master='', isNull=False)
        state.error = False
        shell.refresh_button.click()
        assert captured == [2] and shell.package().id == 2 and shell.kerning_tool.font() == 2
    finally:
        shell.close()


def test_shared_assembly_when_font_capture_switches_package_then_no_half_bound_proof(studio_qt):  # noqa: F811
    import pytest
    from fontlabapp.studios.kerning_browser.app import show
    source = [SimpleNamespace(id=1, masters=[], master='', isNull=False)]
    published = []
    def font():
        source[0] = SimpleNamespace(id=2, masters=[], master='', isNull=False)
        return 'old font'
    def preview(shell, tool):
        captured = tool.font()
        published.append(captured)
    with pytest.raises(ValueError, match='original font'):
        show(package=lambda: source[0], font=font, preview=preview)
    assert not published
