# this_file: tests/test_master_text_panel.py
"""Real owned Qt controls/events verify the complete source UI workflow."""

from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from test_spacing_worksheet import QtCore, GUI, QTest, drain, valid
from test_case_coverage_settings import Memory
from fontlabapp.masters.text.capture import Opening
from fontlabapp.masters.text.ui import panel_type, custom_text


def opening():
    return Opening(
        1,
        2,
        "R",
        ("R", "B"),
        (("a", (97,), 10), ("b", (98,), 11), ("space", (32,), 12)),
    )


def test_original_controls_defaults_selection_run_doubleclick_and_persistence(tmp_path):
    path = tmp_path / "MasterBlaster-presets.txt"
    path.write_text("a\nb\n")
    settings, calls = Memory(), []
    p = panel_type(QtCore, GUI)(
        None,
        opening(),
        lambda *a, **k: calls.append((a, k)),
        settings=settings,
        directory=tmp_path,
    )
    p.show()
    drain()
    actions = (p.load_button, p.run_button, p.close_button)
    rects = tuple(button.geometry() for button in actions)
    assert len({rect.center().y() for rect in rects}) == 1, "Actions share one row"
    assert rects[0].right() < rects[1].left() < rects[1].right() < rects[2].left()
    assert all(p.rect().contains(rect) for rect in rects), "Actions fit the panel"
    assert p.words_edit.toPlainText() == "" and p.arrangement.currentIndex() == 1
    assert p.preset_list.count() == 2 and not p.run_button.isEnabled()
    p.preset_list.setCurrentRow(0)
    p.words_edit.setPlainText("ab?")
    p.run_button.click()
    drain()
    assert calls[-1][0][1].preview == "ab ab \n" and "?" in p.preview.toPlainText()
    assert settings.data == {"inputCustom": "ab?", "layout": 1}
    p.preset_list.setCurrentRow(1)
    assert p.words_edit.toPlainText() == "ab?", (
        "Selection never overwrites custom input"
    )
    item = p.preset_list.item(1)
    rect = p.preset_list.visualItemRect(item)
    QTest.mouseClick(p.preset_list.viewport(), QtCore.Qt.LeftButton, pos=rect.center())
    QTest.mouseDClick(p.preset_list.viewport(), QtCore.Qt.LeftButton, pos=rect.center())
    drain()
    assert calls[-1][0][1].preview == "b b \n", (
        "Actual doubleclick runs that preset despite custom input"
    )
    assert p.words_edit.toPlainText() == "ab?"
    p.arrangement.setCurrentIndex(0)
    p.run_button.click()
    p.resize(620, 540)
    saved_size = p.size()
    assert p.close()
    drain()
    assert not any(s.records for s in p.scopes) and "geometry" in settings.data
    again = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=settings, directory=tmp_path
    )
    assert (
        again.words_edit.toPlainText() == "ab?"
        and again.arrangement.currentIndex() == 0
    )
    assert again.size() == saved_size, (
        "Restore the actual saved geometry, subject to Qt minimum size"
    )
    again.close()
    drain()


def test_fallback_manual_load_missing_file_no_selection_and_failed_proof(tmp_path):
    settings = Memory()
    run = Mock(side_effect=ValueError("native proof binding held"))
    p = panel_type(QtCore, GUI)(
        None, opening(), run, settings=settings, directory=tmp_path
    )
    assert p.preset_list.count() == 4 and "fallback" in p.status.text()
    p.execute()
    assert "select a preset" in p.status.text() and not run.called
    p.words_edit.setPlainText("a?")
    p.run_button.click()
    assert "held" in p.status.text() and "?" in p.preview.toPlainText()
    assert not settings.data, "Failed proof never saves source controls"
    p.words_edit.setPlainText("???")
    p.run_button.click()
    assert "No usable" in p.status.text()
    p.path_edit.setText(str(tmp_path / "missing"))
    p.load_file()
    assert p.preset_list.count() == 4 and "missing" in p.status.text()
    path = tmp_path / "more.txt"
    path.write_text("a,b\n")
    p.path_edit.setText(str(path))
    p.load_file()
    assert p.preset_list.count() == 1 and p.words_edit.toPlainText() == "???"
    p.close()
    drain()
    p.execute()
    p.refresh()
    assert not any(s.records for s in p.scopes)


def test_failed_construction_corrupt_settings_cleanup_and_close_errors(tmp_path):
    settings = Memory()
    settings.data["layout"] = "bad"
    p = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=settings, directory=tmp_path
    )
    assert p.arrangement.currentIndex() == 1 and "invalid" in p.status.text()
    settings.writable = False
    assert not p.close() and "read-only" in p.status.text()
    settings.writable = True
    assert p.close()
    drain()


def test_owned_ini_namespace_unrelated_keys_geometry_registry_and_destroyed(tmp_path):
    import sys

    settings = QtCore.QSettings(str(tmp_path / "owned.ini"), QtCore.QSettings.IniFormat)
    settings.setFallbacksEnabled(False)
    settings.setValue("unrelated", "keep")
    run = Mock()
    p = panel_type(QtCore, GUI)(
        None, opening(), run, settings=settings, directory=tmp_path
    )
    sys.__dict__.setdefault("_fontlab_samples", {})["masters_text_comparison"] = p
    p.words_edit.setPlainText("/a /b")
    p.input_mode.setCurrentIndex(1)
    p.run_button.click()
    assert run.call_args.args[1].words == (("a", "b"),)
    p.busy = True
    p.execute()
    p.load_file()
    p.busy = False
    p.close()
    drain()
    assert sys._fontlab_samples.get("masters_text_comparison") is not p
    assert settings.value("unrelated") == "keep"
    assert set(settings.allKeys()) == {"unrelated", "inputCustom", "layout", "geometry"}


def test_signal_disconnect_failure_preserves_owned_retry_and_construct_error(tmp_path):
    p = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )

    class FailingSignal:
        def disconnect(self, slot):
            return False

    original = p.scopes[0].records[0]
    p.scopes[0].records[0] = (FailingSignal(), original[1], False)
    assert not p.close() and p.closed and p.scopes[0].records
    p.scopes[0].records[0] = original
    assert p.close()
    drain()


def test_custom_input_block_text_preserves_nbsp_ls_nonbmp_and_refuses_truncated_utf16(
    tmp_path,
):
    editor = GUI.QPlainTextEdit()
    editor.setPlainText("a\u00a0\u2028😀")
    assert custom_text(editor, lambda: None) == "a\u00a0\u2028😀", (
        "Never use Qt toPlainText's NBSP/LS folding"
    )
    editor.setPlainText("a\u2029b")
    with pytest.raises(ValueError, match="held"):
        custom_text(editor, lambda: None)
    bad = NS(
        document=lambda: NS(
            blockCount=1, firstBlock=lambda: NS(text="a"), characterCount=5
        )
    )
    with pytest.raises(ValueError, match="UTF16/NUL"):
        custom_text(bad, lambda: None)
    editor.deleteLater()
    drain()


def test_close_deletion_failure_remains_owned_and_retryable(tmp_path, monkeypatch):
    import sys

    p = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )

    def fail_delete(self):
        raise RuntimeError("owned delete failure")

    monkeypatch.setattr(type(p), "deleteLater", fail_delete, raising=False)
    assert not p.close() and "delete failure" in p.status.text()
    retained = sys._fontlab_samples["master_text_failed"]
    assert len(retained) == 1 and retained[id(p)].owner is p
    assert isinstance(retained[id(p)].errors[0], RuntimeError)
    monkeypatch.delattr(type(p), "deleteLater")
    assert p.close()
    drain()
    assert id(p) not in sys._fontlab_samples.get("master_text_failed", {})


def test_external_owned_widget_destruction_releases_signals_and_registry(tmp_path):
    import sys

    p = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )
    sys.__dict__.setdefault("_fontlab_samples", {})["masters_text_comparison"] = p
    p.deleteLater()
    drain()
    assert p.closed and not any(scope.records for scope in p.scopes)
    assert sys._fontlab_samples.get("masters_text_comparison") is not p


def test_opening_absolute_deadline_is_not_restarted_by_panel_constructor(tmp_path):
    with pytest.raises(TimeoutError, match="deadline"):
        panel_type(QtCore, GUI)(
            None, opening(), Mock(), settings=Memory(), directory=tmp_path, deadline=0
        )
    gui = NS(**vars(GUI))
    gui.QListWidget = Mock(side_effect=RuntimeError("owned construction failure"))
    with pytest.raises(RuntimeError, match="construction"):
        panel_type(QtCore, gui)(
            None, opening(), Mock(), settings=Memory(), directory=tmp_path
        )
    drain()


@pytest.mark.parametrize("held", [False, True], ids=["multiline", "restored-held"])
def test_immediate_real_doubleclick_bypasses_unrelated_held_custom_and_preserves_it(
    tmp_path, held
):
    path = tmp_path / "MasterBlaster-presets.txt"
    path.write_text("a\nb\n")
    settings = Memory()
    settings.data["inputCustom"] = "last exact saved custom"
    calls = []
    p = panel_type(QtCore, GUI)(
        None,
        opening(),
        lambda *a, **k: calls.append(a[1]),
        settings=settings,
        directory=tmp_path,
    )
    p.words_edit.setPlainText("a\nb")
    p.custom_held = held
    p.show()
    drain()
    item = p.preset_list.item(1)
    point = p.preset_list.visualItemRect(item).center()
    QTest.mouseClick(p.preset_list.viewport(), QtCore.Qt.LeftButton, pos=point)
    QTest.mouseDClick(p.preset_list.viewport(), QtCore.Qt.LeftButton, pos=point)
    drain()
    assert calls and calls[-1].preview == "b b \n", (
        "Valid preset proof must precede any unrelated custom representation refusal"
    )
    assert (
        p.words_edit.toPlainText() == "a\nb"
        and settings.data["inputCustom"] == "last exact saved custom"
    ), "Do not rewrite the field or last exact custom setting"
    assert settings.data["layout"] == 1 and "custom" in p.status.text().lower()
    before = len(calls)
    p.execute()
    assert len(calls) == before, (
        "Ordinary Run still refuses its held/multiline effective custom route"
    )
    p.close()
    drain()


def test_immediate_preset_delivery_precedes_truncated_getter_and_never_saves_prefix(
    tmp_path, monkeypatch
):
    import fontlabapp.masters.text.ui as panel_module

    settings = Memory()
    settings.data["inputCustom"] = "exact saved text"
    events = []
    p = panel_type(QtCore, GUI)(
        None,
        opening(),
        lambda *a, **k: events.append("proof"),
        settings=settings,
        directory=tmp_path,
    )
    p.words_edit.setPlainText("unrelated custom")

    def truncated(*a):
        events.append("custom getter")
        raise ValueError(
            "Native UTF16/NUL custom getter cannot represent the full input"
        )

    monkeypatch.setattr(panel_module, "custom_text", truncated)
    p.execute(immediate=0)
    assert events[0] == "proof" and settings.data["inputCustom"] == "exact saved text"
    assert (
        p.words_edit.toPlainText() == "unrelated custom"
        and "Opened comparison" in p.status.text()
    )
    p.close()
    drain()


def test_pythonqt_contract_preserves_native_dialog_members_and_cleans_early_initialization(
    tmp_path,
):
    native_names = set(dir(GUI.QDialog))
    made = []
    assigned = {}

    class StrictDialog(GUI.QDialog):
        def __init__(self, parent):
            GUI.QDialog.__init__(self, parent)
            made.append(self)
            assigned[id(self)] = set()

        def __setattr__(self, name, item):
            if name in native_names:
                raise AttributeError(f"Slot '{name}' cannot be overwritten")
            assigned[id(self)].add(name)
            GUI.QDialog.__setattr__(self, name, item)

    gui = NS(**vars(GUI))
    gui.QDialog = StrictDialog
    p = panel_type(QtCore, gui)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )
    assert callable(p.result) and p.result() == 0 and p.comparison_result is None, (
        "QDialog.result must remain the native callable"
    )
    assert assigned[id(p)].isdisjoint(native_names), (
        "Audit actual Python assignments; binding-populated native signal cache entries are not application writes"
    )
    p.close()
    drain()


def test_fallible_initial_state_is_inside_owned_construction_cleanup(tmp_path):
    made = []

    class EarlyFailure(GUI.QDialog):
        def __init__(self, parent):
            GUI.QDialog.__init__(self, parent)
            made.append(self)

        def __setattr__(self, name, item):
            if name == "opening":
                raise RuntimeError("early state assignment failed")
            GUI.QDialog.__setattr__(self, name, item)

    gui = NS(**vars(GUI))
    gui.QDialog = EarlyFailure
    with pytest.raises(RuntimeError, match="early state assignment"):
        panel_type(QtCore, gui)(
            None, opening(), Mock(), settings=Memory(), directory=tmp_path
        )
    assert made[-1].closed and made[-1]._comparison_delete_scheduled, (
        "Even initialization before terminal/signal creation must retire its owned native dialog"
    )
    drain()
    assert not valid(made[-1])


@pytest.mark.parametrize("cleanup_fault", ["disconnect", "deadline"])
def test_incomplete_construction_retains_errors_fences_second_attempt_and_recovers(
    tmp_path, monkeypatch, cleanup_fault
):
    import fontlabapp.masters.text.ui as panel_module
    import fontlabapp.masters.text.controller as controller
    from fontlabapp.masters.text.owners import pending
    from fontlabapp.core.signals.scope import Scope

    made = []

    class TrackedDialog(GUI.QDialog):
        def __init__(self, parent):
            GUI.QDialog.__init__(self, parent)
            made.append(self)

    gui = NS(**vars(GUI))
    gui.QDialog = TrackedDialog
    clock = NS(now=0)

    def construction_error():
        if cleanup_fault == "deadline":
            clock.now = 4
        raise ValueError("original widget construction failed")

    gui.QListWidget = construction_error
    original_finish = Scope.finish
    if cleanup_fault == "disconnect":

        def finish(self, **kwargs):
            self._report(RuntimeError("owned terminal disconnect failed"))
            return False

        monkeypatch.setattr(Scope, "finish", finish)
    monkeypatch.setattr(panel_module, "monotonic", lambda: clock.now)
    try:
        with pytest.raises(ExceptionGroup) as caught:
            panel_type(QtCore, gui)(
                None,
                opening(),
                Mock(),
                settings=Memory(),
                directory=tmp_path,
                deadline=3,
            )
        owner = made[0]
        assert (
            pending()[id(owner)].owner is owner
            and pending()[id(owner)].errors[0] is caught.value
        )
        assert isinstance(
            caught.value.exceptions[0], ValueError
        ) and "original widget" in str(caught.value.exceptions[0])
        assert "cleanup" in str(caught.value.exceptions[1]) or isinstance(
            caught.value.exceptions[1], TimeoutError
        )
        if cleanup_fault == "disconnect":
            assert owner.terminal.records, (
                "Failed exact native signal pairs remain owned"
            )
        capture = Mock(return_value=opening())
        factory = Mock(return_value=panel_type(QtCore, gui))
        monkeypatch.setattr(controller, "read", capture)
        monkeypatch.setattr(controller, "panel_type", factory)
        monkeypatch.setattr(
            controller, "_native", lambda name: NS(QtCore=QtCore, QtGui=gui)
        )
        monkeypatch.setattr(
            controller, "show_script_dialog", lambda build, key: build(None)
        )
        for later_succeeds in (False, True):
            gui.QListWidget = GUI.QListWidget if later_succeeds else construction_error
            with pytest.raises(RuntimeError, match="cleanup"):
                controller.show()
            with pytest.raises(RuntimeError, match="cleanup"):
                panel_type(QtCore, gui)(
                    None,
                    opening(),
                    Mock(),
                    settings=Memory(),
                    directory=tmp_path,
                    deadline=6,
                )
            assert len(made) == 1 and not capture.called and not factory.called
        # Recovery has ONE new caller deadline; never creates a replacement.
        with pytest.raises(TimeoutError):
            controller.recover(deadline=0)
        assert pending()
    finally:
        monkeypatch.setattr(Scope, "finish", original_finish)
        clock.now = 0
        receipts = controller.recover(deadline=controller.monotonic() + 3)
        assert any(record.owner is made[0] for record in receipts) and not pending()
        assert receipts[0].errors, (
            "Original error group remains in the recovery receipt"
        )
        drain()
    gui.QListWidget = GUI.QListWidget
    new_panel = controller.show(settings=Memory(), directory=tmp_path)
    assert new_panel is made[1] and capture.called and factory.called, (
        "A confirmed recovery permits exactly a new owner"
    )
    new_panel.close()
    drain()


def test_distinct_failed_owners_are_retained_cumulatively_and_partial_recovery_never_discards_one(
    tmp_path, monkeypatch
):
    from fontlabapp.masters.text.owners import pending, recover
    import fontlabapp.masters.text.ui as panel_module

    p = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )
    first_type = type(p)

    def fail_delete(self):
        raise RuntimeError("first deletion failed")

    # A second owner already existed before the first failure, as can happen
    # during explicit shared-dialog replacement/independent owned teardown.
    q = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )
    second_type = type(q)
    monkeypatch.setattr(first_type, "deleteLater", fail_delete, raising=False)
    monkeypatch.setattr(second_type, "deleteLater", fail_delete, raising=False)
    try:
        assert not p.close() and not q.close()
        assert {record.owner for record in pending().values()} == {p, q}
        errors = tuple(pending()[id(p)].errors)
        monkeypatch.delattr(first_type, "deleteLater")
        with pytest.raises(ExceptionGroup) as caught:
            recover(deadline=panel_module.monotonic() + 3)
        assert id(p) not in pending() and pending()[id(q)].owner is q
        assert (
            caught.value.recovered[0].owner is p
            and tuple(caught.value.recovered[0].errors) == errors
        )
        assert len(pending()[id(q)].errors) == 2, (
            "Repeated failures append; they never replace prior failure receipts"
        )
    finally:
        monkeypatch.delattr(second_type, "deleteLater")
        recover(deadline=panel_module.monotonic() + 3)
        drain()
        assert not pending()


def test_readable_immediate_custom_saves_after_proof_invalid_preset_reads_no_custom(
    tmp_path, monkeypatch
):
    import fontlabapp.masters.text.ui as module

    (tmp_path / "MasterBlaster-presets.txt").write_text("a\n")
    settings = Memory()
    settings.data["inputCustom"] = "previous"
    calls = []
    p = panel_type(QtCore, GUI)(
        None,
        opening(),
        lambda *a, **k: calls.append(a[1]),
        settings=settings,
        directory=tmp_path,
    )
    p.words_edit.setPlainText("b")
    p.execute(immediate=0)
    assert calls[-1].preview == "a a \n" and settings.data["inputCustom"] == "b"
    getter = Mock(side_effect=ValueError("unrelated getter must not run"))
    monkeypatch.setattr(module, "custom_text", getter)
    before = len(calls)
    p.execute(immediate=9)
    assert (
        len(calls) == before
        and not getter.called
        and "select a preset" in p.status.text()
    )
    p.close()
    drain()


def test_explicit_recovery_cancellation_inside_signal_cleanup_retains_original_and_new_errors(
    tmp_path, monkeypatch
):
    import fontlabapp.masters.text.ui as module
    from fontlabapp.masters.text.owners import pending, recover

    p = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )
    original = p.scopes[0].records[0]
    bad = NS(disconnect=lambda slot: False)
    p.scopes[0].records[0] = (bad, original[1], False)
    assert not p.close()
    first_error = pending()[id(p)].errors[0]
    p.scopes[0].records[0] = original
    steps = []

    def cancel():
        steps.append(1)
        return len(steps) >= 6

    with pytest.raises(ExceptionGroup) as caught:
        recover(deadline=module.monotonic() + 3, cancelled=cancel)
    assert isinstance(caught.value.exceptions[0], InterruptedError)
    assert (
        pending()[id(p)].errors[0] is first_error and len(pending()[id(p)].errors) == 2
    )
    assert any(scope.records for scope in p.scopes), (
        "Cancellation cannot discard still-connected owned pairs"
    )
    receipts = recover(deadline=module.monotonic() + 3)
    assert receipts[0].owner is p and not pending()
    drain()


def test_recovery_delete_overrun_keeps_handle_and_stage_until_new_bounded_recovery(
    tmp_path, monkeypatch
):
    import fontlabapp.masters.text.ui as module
    import fontlabapp.masters.text.owners as owners

    p = panel_type(QtCore, GUI)(
        None, opening(), Mock(), settings=Memory(), directory=tmp_path
    )

    def fail_delete(self):
        raise RuntimeError("initial deletion failure")

    monkeypatch.setattr(type(p), "deleteLater", fail_delete, raising=False)
    assert not p.close()
    clock = NS(now=0)
    monkeypatch.setattr(module, "monotonic", lambda: clock.now)
    monkeypatch.setattr(owners, "monotonic", lambda: clock.now)

    def delayed_delete(self):
        GUI.QDialog.deleteLater(self)
        clock.now = 4

    monkeypatch.setattr(type(p), "deleteLater", delayed_delete)
    with pytest.raises(ExceptionGroup) as caught:
        owners.recover(deadline=3)
    assert (
        isinstance(caught.value.exceptions[0], TimeoutError)
        and owners.pending()[id(p)].owner is p
    )
    assert p._comparison_delete_scheduled, (
        "Keep the completed deferred-delete stage across the timeout"
    )
    clock.now = 0
    receipts = owners.recover(deadline=3)
    assert (
        receipts[0].owner is p and len(receipts[0].errors) == 2 and not owners.pending()
    )
    drain()


@pytest.mark.parametrize("route", ["close", "parent-destroy"])
@pytest.mark.parametrize("reload_presets", [False, True], ids=["initial", "reloaded"])
def test_preset_items_when_owner_deleted_then_retained_wrappers_are_invalid(
    tmp_path, route, reload_presets
):
    path = tmp_path / "MasterBlaster-presets.txt"
    path.write_text("a\nb\n", encoding="utf-8")
    parent, calls, settings = GUI.QWidget(), Mock(), Memory()
    p = panel_type(QtCore, GUI)(
        parent, opening(), calls, settings=settings, directory=tmp_path
    )
    try:
        p.words_edit.setPlainText("ab")
        old_items = tuple(p.preset_list.item(i) for i in range(2))
        assert tuple(item.text() for item in old_items) == ("a", "b")
        if reload_presets:
            path.write_text("b\na\n", encoding="utf-8")
            p.load_button.click()
            assert all(not valid(item) for item in old_items), (
                "Replacing presets destroys every old item wrapper"
            )
        expected = ("b", "a") if reload_presets else ("a", "b")
        items = tuple(p.preset_list.item(i) for i in range(2))
        assert p.presets == expected
        assert tuple(item.text() for item in items) == expected
        assert p.selected == -1 and p.preset_list.currentRow() == -1
        p.preset_list.setCurrentRow(1)
        assert p.selected == 1 and p.words_edit.toPlainText() == "ab"
        assert not calls.called, "Selection and replacement never execute a proof"
        if route == "close":
            assert p.close()
        else:
            parent.deleteLater()
        drain()
        assert not valid(p) and not valid(p.preset_list)
        assert p.closed and p.run is None
        assert not any(scope.records for scope in p.scopes)
        assert not p.terminal.records
        assert all(not valid(item) for item in items), (
            "Native owner deletion must invalidate retained preset wrappers"
        )
    finally:
        if valid(parent):
            parent.deleteLater()
        drain()
