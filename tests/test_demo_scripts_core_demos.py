# this_file: tests/test_demo_scripts_core_demos.py
"""Offline runs of the four demos that show App core features (Issue 208, F3).

Shim Generator, Native Tabs, History Preflight and Owned Lifetime demonstrate
``core.shimgen``, ``core.native_tabs``, ``core.history`` and
``core.completion`` plus the ``fontlabapp.ui`` factories. Each demo runs
through runpy as ``__main__`` (and as an imported name, when nothing may run)
against the real ``fontlabapp`` modules; only ``PythonQt`` and ``fontlab`` are
stubbed, with the few host-bound reads of the history demo replaced by plain
records. Offline results are not native FontLab acceptance.
"""

import sys
from types import SimpleNamespace

import pytest
from _demo_support import FakeSignal, Recorder, qt_namespace, run_script, script_path, stub_module

SHIM = script_path("Utilities", "Shim Generator Demo")
TABS = script_path("Proof", "Native Tabs Demo")
HISTORY = script_path("Masters", "History Preflight Demo")
OWNED = script_path("Widgets", "Owned Lifetime Demo")
PACKAGE = SimpleNamespace(isNull=False, id=3)


def install(monkeypatch, shots=None, **fontlab_names):
    """Stub PythonQt and fontlab; return QtGui. ``fontlab_names`` extend the fontlab module."""
    qt = qt_namespace()
    if shots is not None:
        qt.QtCore.QTimer.singleShot = lambda delay, call: shots.append((delay, call))
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    names = {"MainWindow": lambda: "main-window", **fontlab_names}
    stub_module(monkeypatch, "fontlab", **names)
    return qt.QtGui


def modal(gui) -> tuple[str, str]:
    """(message, details) of the one modal message box the demo ran."""
    assert gui.QMessageBox.call_count == 1, "exactly one message box expected"
    assert gui.QMessageBox.call_args[0] == ("main-window",), "box parents to the main window"
    box = gui.QMessageBox.return_value
    box.exec.assert_called_once_with()
    details = box.setDetailedText.call_args[0][0] if box.setDetailedText.called else ""
    return box.setInformativeText.call_args[0][0], details


# --- Shim Generator Demo -------------------------------------------------------


def test_shim_generator_when_main_then_replays_sample_and_shows_generated_stub(monkeypatch, tmp_path) -> None:
    gui = install(monkeypatch)
    monkeypatch.chdir(tmp_path)
    import fontlabapp.core.shimgen as shimgen

    written = Recorder()
    monkeypatch.setattr(shimgen, "write", written)
    names = run_script(SHIM)
    box = gui.QMessageBox.return_value
    assert gui.QMessageBox.call_args[0] == ("main-window",) and box.setModal.call_args[0] == (False,)
    box.show.assert_called_once_with()
    assert names["_BOXES"] == [box], "the modeless box stays referenced"
    details = box.setDetailedText.call_args[0][0]
    assert "menu bar: file, glyph" in details
    assert "action: File > New Font" in details and "action: Glyph > Add Component" in details
    assert "glyph actions: remove_overlap" in details
    assert "this_file: generated/fontlabapp_shim/__init__.pyi" in details
    assert "this_file: generated/fontlabapp_shim/__init__.py" in details
    assert "new_font: Action" in details and "add_component: Action" in details
    assert written.calls == [] and not any(tmp_path.iterdir()), "nothing is written to disk"


def test_shim_generator_when_generated_then_text_matches_real_shimgen_output(monkeypatch) -> None:
    install(monkeypatch)
    from fontlabapp.core import shimgen

    names = run_script(SHIM, "imported")
    sample = names["SAMPLE"]
    lines = names["stub_lines"](shimgen.generate_pyi(sample), shimgen.generate_py(sample))
    assert lines[:3] == shimgen.generate_pyi(sample).splitlines()[:3]
    assert lines[3] == shimgen.generate_py(sample).splitlines()[0]
    assert lines[4].startswith("typed names: ") and "save_font: Action" in lines[4]
    host_lines = names["host_lines"](shimgen.replay(sample))
    assert host_lines[1:4] == ["action: File > New Font", "action: File > Save Font", "action: Glyph > Add Component"]


def test_shim_generator_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui = install(monkeypatch)
    names = run_script(SHIM, "imported")
    assert names["_BOXES"] == [] and gui.QMessageBox.call_count == 0


# --- Native Tabs Demo ----------------------------------------------------------


def info(name):
    return SimpleNamespace(glyph=SimpleNamespace(name=name))


def tabs_host(monkeypatch, *, workspace="default", block=None, canvases=(1, 2), canvas_error=None):
    """Stub fontlab with a workspace of fake canvases and an active text block."""

    def raw_canvases():
        if canvas_error:
            raise canvas_error
        return list(canvases)

    if workspace == "default":
        workspace = SimpleNamespace(
            canvases=raw_canvases,
            getActiveTextBlock=lambda: block,
            getActiveCanvas=lambda: None if block is None else SimpleNamespace(textBlocks=lambda: [block]),
        )
    return install(
        monkeypatch,
        flWorkspace=SimpleNamespace(instance=lambda: workspace),
        flCanvas=lambda raw: f"canvas{raw}",
    )


def block_of(*names):
    return SimpleNamespace(getAllGlyphs=lambda: [info(name) for name in names])


def test_native_tabs_when_block_active_then_reports_canvas_count_and_glyph_names(monkeypatch) -> None:
    gui = tabs_host(monkeypatch, block=block_of("H", "a", "m"))
    run_script(TABS)
    text, details = modal(gui)
    assert text == "Glyph canvases found: 2 (some builds list only the active one)." and details == "Active block: 3 glyphs\nH a m"


def test_native_tabs_when_canvas_list_raises_type_error_then_counts_only_active_canvas(monkeypatch) -> None:
    gui = tabs_host(monkeypatch, block=block_of("A"), canvas_error=TypeError("broken binding"))
    run_script(TABS)
    assert modal(gui)[0] == "Glyph canvases found: 1 (some builds list only the active one)."


def test_native_tabs_when_no_block_then_says_to_open_a_glyph_window(monkeypatch) -> None:
    gui = tabs_host(monkeypatch, block=None, canvases=())
    run_script(TABS)
    text, details = modal(gui)
    assert text == "Glyph canvases found: 0 (some builds list only the active one)." and "No text block is shown" in details


def test_native_tabs_when_block_has_many_glyphs_then_lists_first_forty_and_counts_the_rest(monkeypatch) -> None:
    names = [f"g{i}" for i in range(45)]
    gui = tabs_host(monkeypatch, block=block_of(*names))
    run_script(TABS)
    details = modal(gui)[1]
    assert details.startswith("Active block: 45 glyphs\n") and details.endswith("g39 ... (+5 more)")
    assert "g40" not in details


def test_native_tabs_when_block_reports_no_glyph_list_then_shows_zero_glyphs(monkeypatch) -> None:
    gui = tabs_host(monkeypatch, block=SimpleNamespace(getAllGlyphs=lambda: None))
    run_script(TABS)
    assert modal(gui)[1] == "Active block: 0 glyphs\n"


def test_native_tabs_when_no_workspace_then_one_message_and_no_reads(monkeypatch) -> None:
    gui = tabs_host(monkeypatch, workspace=None)
    run_script(TABS)
    text, details = modal(gui)
    assert text == "FontLab has no workspace to read." and details == ""


def test_native_tabs_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui = tabs_host(monkeypatch, block=block_of("A"))
    run_script(TABS, "imported")
    assert gui.QMessageBox.call_count == 0


# --- History Preflight Demo ----------------------------------------------------

# (glyph, layer is auto, component bases): ``Aacute`` and ``Eacute`` are auto
# glyphs on the bases ``A``, ``E`` and ``acute``; manual ``Ebar`` sits between.
RECORDS = (
    ("A", False, ()),
    ("acute", False, ()),
    ("Aacute", True, ("A", "acute")),
    ("Ebar", False, ("E",)),
    ("Eacute", True, ("Ebar", "acute")),
)


def history_host(monkeypatch, *, package=PACKAGE, records=RECORDS, scan_error=None, window_error=None, canvas=None):
    """Stub fontlab and the three host-bound reads; return (QtGui, writes)."""
    import fontlabapp.core.edit_guards as edit_guards
    import fontlabapp.core.history.glyphs as glyphs
    import fontlabapp.core.history.masters as masters
    import fontlabapp.guides.inspect.model as guide_model

    gui = install(monkeypatch, flWorkspace=SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=package)))

    def dependency_values(given):
        assert given is package, "the scan reads the current font"
        if scan_error:
            raise scan_error
        return records

    def require_selection_window(package_id):
        assert package_id == package.id
        if window_error:
            raise window_error

    writes = Recorder()
    monkeypatch.setattr(guide_model, "dependency_values", dependency_values)
    monkeypatch.setattr(edit_guards, "require_selection_window", require_selection_window)
    monkeypatch.setattr(edit_guards, "canvas_glyphs", lambda native=None, **kw: canvas)
    monkeypatch.setattr(glyphs, "commit", writes)
    monkeypatch.setattr(masters, "commit_masters", writes)
    return gui, writes


def test_history_preflight_when_font_open_then_lists_auto_owners_bases_and_allows_master_write(monkeypatch) -> None:
    gui, writes = history_host(monkeypatch)
    run_script(HISTORY)
    text, details = modal(gui)
    assert text == "A master write would be allowed now."
    assert "Aacute: built from A, acute" in details and "Eacute: built from Ebar, acute" in details
    assert "Changing A rebuilds: Aacute" in details
    assert "Changing E rebuilds: Eacute" in details, "the chain through manual Ebar is followed"
    assert "Changing acute rebuilds: Aacute, Eacute" in details
    assert writes.calls == [], "no history step is committed"


def test_history_preflight_when_font_has_no_auto_layers_then_says_so(monkeypatch) -> None:
    gui, _ = history_host(monkeypatch, records=(("A", False, ()), ("B", False, ("A",))))
    run_script(HISTORY)
    assert modal(gui)[1] == "Auto layers:\nNo glyph owns an auto layer."


def test_history_preflight_when_many_auto_owners_then_lists_twelve(monkeypatch) -> None:
    records = tuple((f"g{i:02d}", True, ("base",)) for i in range(15))
    gui, _ = history_host(monkeypatch, records=records)
    run_script(HISTORY)
    owners = [line for line in modal(gui)[1].splitlines() if "built from" in line]
    assert len(owners) == 12 and owners[0].startswith("g00:") and owners[-1].startswith("g11:")


def test_history_preflight_when_auto_owner_has_no_components_then_says_so(monkeypatch) -> None:
    gui, _ = history_host(monkeypatch, records=(("auto", True, ()),))
    run_script(HISTORY)
    assert "auto: built from no components" in modal(gui)[1]


def test_history_preflight_when_glyph_is_missing_then_scan_error_text_and_window_check_still_run(monkeypatch) -> None:
    gui, _ = history_host(monkeypatch, scan_error=ValueError("Glyph source changed; reopen this tool."))
    run_script(HISTORY)
    text, details = modal(gui)
    assert "Auto layers could not be scanned: Glyph source changed; reopen this tool." in details
    assert text == "A master write would be allowed now."


def test_history_preflight_when_font_window_not_active_then_shows_the_refusal_text(monkeypatch) -> None:
    gui, writes = history_host(monkeypatch, window_error=ValueError("Activate the Font window before selecting glyphs."))
    run_script(HISTORY)
    text = modal(gui)[0]
    assert text == "A master write would be refused now: Activate the Font window before editing font masters."
    assert writes.calls == []


def test_history_preflight_when_glyph_window_is_active_canvas_then_refused(monkeypatch) -> None:
    gui, _ = history_host(monkeypatch, canvas=frozenset({(3, "A")}))
    run_script(HISTORY)
    assert modal(gui)[0].startswith("A master write would be refused now: Activate the Font window")


def test_history_preflight_when_no_font_then_one_message_and_no_checks(monkeypatch) -> None:
    gui, writes = history_host(monkeypatch, package=None)
    run_script(HISTORY)
    text, details = modal(gui)
    assert text == "Open a font first: there is nothing to check." and details == "" and writes.calls == []


def test_history_preflight_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = history_host(monkeypatch)
    run_script(HISTORY, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Owned Lifetime Demo -------------------------------------------------------


class Q:
    """A Qt object stand-in: real-looking signals; every other call is recorded and succeeds."""

    made: list = []

    def __init__(self, *args) -> None:
        self.args = args
        self.finished, self.destroyed = FakeSignal(), FakeSignal()
        self.clicked, self.topLevelChanged = FakeSignal(), FakeSignal()
        Q.made.append(self)

    def __getattr__(self, name: str):
        recorder = Recorder()
        setattr(self, name, recorder)
        return recorder


class Dialog(Q):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.close_events: list = []

    def closeEvent(self, event) -> None:  # Completion calls type(dialog).closeEvent
        self.close_events.append(event)


class Widget(Q):
    pass


class Dock(Q):
    pass


class Label(Q):
    pass


class Button(Q):
    pass


class Layout(Q):
    pass


def owned_host(monkeypatch, shots=None, **replaced):
    """Stub PythonQt with the fake widget classes; return (QtGui, main window)."""
    Q.made = []
    main = Q("main")
    gui = install(
        monkeypatch,
        [] if shots is None else shots,
        MainWindow=lambda: main,
    )
    kinds = dict(QDialog=Dialog, QWidget=Widget, QDockWidget=Dock, QLabel=Label, QPushButton=Button, QVBoxLayout=Layout)
    for name, kind in {**kinds, **replaced}.items():
        setattr(gui, name, kind)
    return gui, main


def made(kind) -> list:
    return [item for item in Q.made if type(item) is kind]


def button(label):
    (found,) = [item for item in made(Button) if item.args[0] == label]
    return found


def status(demo) -> str:
    return demo.status.setText.calls[-1][0][0]


def open_owned(monkeypatch, shots=None):
    gui, main = owned_host(monkeypatch, shots)
    handles = run_script(OWNED)["_HANDLES"]
    (demo,) = handles
    return demo, handles, main


def test_owned_lifetime_when_main_then_creates_one_dialog_widget_panel_and_subject(monkeypatch) -> None:
    demo, handles, main = open_owned(monkeypatch)
    monitor, subject = demo.owned.widget, demo.subject.widget
    assert made(Dialog) == [monitor, subject] and monitor.args == (main,) and subject.args == (main,)
    assert monitor.setWindowTitle.calls == [(("Owned Lifetime Demo",), {})]
    assert subject.setWindowTitle.calls == [(("Completion subject",), {})]
    assert demo.widget.widget.args == (monitor,), "create_widget makes a child of the demo window"
    dock = demo.panel.widget
    assert dock.args == ("Owned Panel Demo", main)
    assert main.addDockWidget.calls == [((sys.modules["PythonQt"].QtCore.Qt.RightDockWidgetArea, dock), {})]
    assert all(item.show.calls for item in (monitor, subject, dock)), "each owned window is shown"
    assert not any(item.closed for item in (demo.owned, demo.widget, demo.panel, demo.subject))
    import fontlabapp.qt.widgets as widgets
    import fontlabapp.ui as ui

    kit = demo.kit
    assert (kit.create_dialog, kit.create_panel, kit.create_widget) == (ui.create_dialog, ui.create_panel, ui.create_widget)
    assert kit.create_dialog is widgets.create_dialog, "the facade hands out the real factory"
    assert isinstance(demo.widget, widgets.OwnedWidget) and ui.OwnedWidget is widgets.OwnedWidget


def test_owned_lifetime_when_main_then_completion_is_installed_on_subject_and_status_shows_it(monkeypatch) -> None:
    demo, _, _ = open_owned(monkeypatch)
    subject = demo.subject.widget
    assert demo.record.key == "owned-lifetime-demo" and demo.record.dialog is subject
    hooked = [callback for _, callback in demo.record.hooks]
    assert len(hooked) == 2 and all(callback in subject.finished.slots + subject.destroyed.slots for callback in hooked)
    assert len(subject.finished.slots) == 1, "finished: the Completion hook"
    assert len(subject.destroyed.slots) == 2, "destroyed: OwnedWidget's observer and the Completion hook"
    assert status(demo).splitlines() == [
        "widget: closed=False, last_error=None",
        "panel: closed=False, last_error=None",
        "subject dialog: closed=False, last_error=None",
        "Completion 'owned-lifetime-demo': closed=False, finishing=False, hooks=2, error='', errors=0",
    ]


def test_owned_lifetime_when_subject_close_clicked_then_record_and_dialog_close(monkeypatch) -> None:
    demo, _, _ = open_owned(monkeypatch)
    subject, record = demo.subject.widget, demo.record
    button("Close").clicked.emit()
    assert record.closed and record.hooks == [] and record.dialog is None
    assert subject.finished.slots == [] and subject.destroyed.slots == [], "stop disconnects the emitter"
    assert demo.subject.closed and subject.close.calls and subject.deleteLater.calls
    lines = status(demo).splitlines()
    assert lines[2] == "subject dialog: closed=True, last_error=None"
    assert lines[3].startswith("Completion 'owned-lifetime-demo': closed=True, finishing=False, hooks=0")


def test_owned_lifetime_when_subject_dialog_finishes_by_itself_then_completion_runs_its_close_path(monkeypatch) -> None:
    demo, _, _ = open_owned(monkeypatch)
    subject, record = demo.subject.widget, demo.record
    subject.finished.emit(0)
    assert len(subject.close.calls) == 1 and len(subject.close_events) == 1
    assert record.error == "" and not record.finishing and not record.closed
    button("Refresh").clicked.emit()
    assert "finishing=False, hooks=2, error=''" in status(demo)


def test_owned_lifetime_when_widget_and_panel_close_clicked_then_each_owned_widget_closes(monkeypatch) -> None:
    demo, _, main = open_owned(monkeypatch)
    dock = demo.panel.widget
    button("Close widget").clicked.emit()
    assert demo.widget.closed and not demo.panel.closed and "widget: closed=True" in status(demo)
    button("Close panel").clicked.emit()
    assert demo.panel.closed and main.removeDockWidget.calls == [((dock,), {})]
    assert "panel: closed=True" in status(demo)
    button("Close panel").clicked.emit()  # closing twice is harmless
    assert len(main.removeDockWidget.calls) == 1


def test_owned_lifetime_when_refresh_clicked_then_status_rereads_record_fields(monkeypatch) -> None:
    demo, _, _ = open_owned(monkeypatch)
    demo.record.error = "RuntimeError('probe')"
    button("Refresh").clicked.emit()
    assert "error=\"RuntimeError('probe')\"" in status(demo)


def test_owned_lifetime_when_window_finishes_then_releases_everything_on_next_turn(monkeypatch) -> None:
    shots = []
    demo, handles, main = open_owned(monkeypatch, shots)
    monitor, subject = demo.owned.widget, demo.subject.widget
    monitor.finished.emit(0)
    assert [delay for delay, _ in shots] == [0] and handles == [demo], "release waits for Qt dispatch to return"
    shots[0][1]()
    assert handles == [] and monitor.finished.slots == [] and demo.hooks == []
    assert all(item.closed for item in (demo.owned, demo.widget, demo.panel, demo.subject))
    assert demo.record.closed and subject.finished.slots == []
    assert len(main.removeDockWidget.calls) == 1 and demo.status is None
    demo.refresh()  # a stale click after release does nothing
    demo.release()  # a second release is harmless


def test_owned_lifetime_when_disconnect_fails_then_windows_still_close_and_handle_leaves(monkeypatch) -> None:
    demo, handles, _ = open_owned(monkeypatch)

    def gone(slot):
        raise RuntimeError("signal destroyed")

    demo.hooks[-1][0].disconnect = gone
    with pytest.raises(RuntimeError, match="signal destroyed"):
        demo.release()
    assert handles == [] and all(item.closed for item in (demo.owned, demo.widget, demo.panel, demo.subject))


def test_owned_lifetime_when_panel_creation_fails_then_widget_is_closed_and_error_reraised(monkeypatch) -> None:
    def broken(*args):
        raise RuntimeError("no dock")

    owned_host(monkeypatch, QDockWidget=broken)
    names = run_script(OWNED, "imported")
    with pytest.raises(RuntimeError, match="no dock"):
        names["main"]()
    assert names["_HANDLES"] == []
    (widget,) = made(Widget)
    assert widget.deleteLater.calls, "the child widget created before the failure was released"


def test_owned_lifetime_when_dialog_creation_fails_then_nothing_stays_retained(monkeypatch) -> None:
    def broken(*args):
        raise RuntimeError("no dialog")

    owned_host(monkeypatch, QDialog=broken)
    names = run_script(OWNED, "imported")
    with pytest.raises(RuntimeError, match="no dialog"):
        names["main"]()
    assert names["_HANDLES"] == [] and made(Widget) == []


def test_owned_lifetime_when_closing_one_fails_then_the_rest_still_close(monkeypatch) -> None:
    owned_host(monkeypatch)
    close_all = run_script(OWNED, "imported")["close_all"]

    class Item:
        def __init__(self, error=None) -> None:
            self.closed, self.error = False, error

        def close(self) -> None:
            self.closed = True
            if self.error:
                raise self.error

    first, second = Item(RuntimeError("stuck")), Item()
    with pytest.raises(RuntimeError, match="stuck"):
        close_all([None, first, second])
    assert first.closed and second.closed


def test_owned_lifetime_when_imported_then_nothing_runs(monkeypatch) -> None:
    owned_host(monkeypatch)
    names = run_script(OWNED, "imported")
    assert names["_HANDLES"] == [] and Q.made[1:] == []
