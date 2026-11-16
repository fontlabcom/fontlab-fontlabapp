# this_file: tests/test_demo_scripts_proof.py
"""Offline runs of the Scripts/Proof and Scripts/Reports demos (Issue 208, Task 3).

Each demo runs through runpy as ``__main__`` (entry points and arguments are
asserted) and as an imported name (nothing may run). The real host-free
``fontlabapp`` modules stay in use; ``PythonQt`` and ``fontlab`` are stubbed,
and so are the few modules that load native classes when imported (panel and
view modules, tab openers). Message boxes that ask a question are answered by a
scripted ``run_standard_message_box``. Offline results are not native FontLab
acceptance.
"""

import json
import random
import sys
import tempfile
from types import SimpleNamespace

import pytest
from _demo_support import FakeSignal, Recorder, qt_namespace, run_script, script_path, stub_module

PACKAGE = SimpleNamespace(isNull=False, id=3, master="Regular")
OK, YES, NO = 1, 2, 4

HOLDER = script_path("Proof", "Text Holder Demo")
FILTER = script_path("Proof", "Text Filter Demo")
PAINTERS = script_path("Proof", "Proof Painters Demo")
TABS = script_path("Proof", "Proof Tabs Demo")
EXTREMA = script_path("Proof", "Extrema Proof Demo")
NUMERIC = script_path("Proof", "Numeric Worksheets Demo")
JSON_REPORT = script_path("Reports", "JSON Report Demo")
FONT_REPORTS = script_path("Reports", "Font Reports Demo")


def install_host(monkeypatch, answers=(), package=PACKAGE):
    """Stub the natives; scripted answers go to ``run_standard_message_box``.

    Returns (QtGui, asked) where ``asked`` collects one tuple per question box
    in the order (parent, title, text, icon, buttons, default).
    """
    import fontlabapp.core.scripting as scripting
    import fontlabapp.qt.dialogs as dialogs

    qt = qt_namespace()
    qt.QtGui.QMessageBox.Ok, qt.QtGui.QMessageBox.Yes, qt.QtGui.QMessageBox.No = OK, YES, NO
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: "main-window")
    asked, replies = [], iter(answers)

    def ask(_qt, parent, title, text, icon, buttons, default=None):
        asked.append((parent, title, text, icon, buttons, default))
        return next(replies, OK)

    monkeypatch.setattr(dialogs, "run_standard_message_box", ask)
    monkeypatch.setattr(scripting, "current_package", lambda expected_id=None: package)
    return qt.QtGui, asked


def shown(gui) -> tuple[str, str, str]:
    """(title, text, details) of the one modal message box the demo ran."""
    assert gui.QMessageBox.call_count == 1, "exactly one message box expected"
    assert gui.QMessageBox.call_args[0] == ("main-window",), "box parents to the main window"
    box = gui.QMessageBox.return_value
    box.exec.assert_called_once_with()
    details = box.setDetailedText.call_args[0][0] if box.setDetailedText.called else ""
    return box.setText.call_args[0][0], box.setInformativeText.call_args[0][0], details


def redirect_temp(monkeypatch, tmp_path):
    """Make the demo's temp folder a pytest folder."""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))


def open_windows(monkeypatch, **windows):
    """Pretend the given registry keys name already-open owned windows."""
    monkeypatch.setattr(sys, "_fontlab_samples", windows, raising=False)


class LiveWindow:
    """A registry entry whose native widget still exists."""

    def isVisible(self) -> bool:
        return True


class DestroyedWindow:
    """A PythonQt wrapper that outlived its QWidget: every call raises ValueError."""

    def isVisible(self) -> bool:
        raise ValueError("Internal C++ object (Pad) already deleted/destroyed")


class UnreadableWindow:
    """A live wrapper whose call fails with a ValueError that is not a destroyed widget."""

    def isVisible(self) -> bool:
        raise ValueError("unexpected state")


# --- Text Holder Demo ----------------------------------------------------------


def holder_show(monkeypatch, error=None):
    import fontlabapp.proof.text_holder.model as model

    recorder = Recorder()

    def show(**kwargs):
        recorder(**kwargs)
        if error:
            raise error

    monkeypatch.setattr(model, "show", show)
    return recorder


def test_text_holder_when_main_then_opens_pad_on_seeded_sample_file(monkeypatch, tmp_path) -> None:
    gui, asked = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch)
    opened = holder_show(monkeypatch)
    names = run_script(HOLDER)
    path = tmp_path / "fontlabapp-demos" / "text-holder" / "Text holder.txt"
    assert opened.calls == [((), {"path": path})]
    assert path.read_text(encoding="utf-8") == names["SAMPLE"]
    assert asked == [] and gui.QMessageBox.call_count == 0


def test_text_holder_when_run_again_then_reuses_one_folder_and_restores_sample(monkeypatch, tmp_path) -> None:
    install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch)
    holder_show(monkeypatch)
    folder = tmp_path / "fontlabapp-demos" / "text-holder"
    folder.mkdir(parents=True)
    (folder / "Text holder.txt").write_text("my edit", encoding="utf-8")
    names = run_script(HOLDER)
    assert (folder / "Text holder.txt").read_text(encoding="utf-8") == names["SAMPLE"]
    assert [p.name for p in tmp_path.iterdir()] == ["fontlabapp-demos"], "no second folder appears"


def test_text_holder_when_window_already_open_then_says_so_and_does_not_open(monkeypatch, tmp_path) -> None:
    _, asked = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch, **{"text-holder": LiveWindow()})
    opened = holder_show(monkeypatch)
    run_script(HOLDER)
    assert opened.calls == [] and not (tmp_path / "fontlabapp-demos").exists()
    assert len(asked) == 1 and "already open" in asked[0][2] and asked[0][3] == "Information"


def test_text_holder_when_stored_window_is_destroyed_then_drops_it_and_opens(monkeypatch, tmp_path) -> None:
    _, asked = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch, **{"text-holder": DestroyedWindow()})
    opened = holder_show(monkeypatch)
    run_script(HOLDER)
    assert len(opened.calls) == 1 and asked == []
    assert "text-holder" not in sys._fontlab_samples, "the dead entry is dropped"


def test_text_holder_when_stored_window_raises_other_value_error_then_keeps_it_and_does_not_open(monkeypatch, tmp_path) -> None:
    _, asked = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch, **{"text-holder": UnreadableWindow()})
    opened = holder_show(monkeypatch)
    run_script(HOLDER)
    assert opened.calls == [] and "text-holder" in sys._fontlab_samples, "only a destroyed widget is dropped"
    assert len(asked) == 1 and "already open" in asked[0][2]


def test_text_holder_when_pad_fails_then_message_names_the_error(monkeypatch, tmp_path) -> None:
    _, asked = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch)
    holder_show(monkeypatch, error=OSError("disk gone"))
    run_script(HOLDER)
    assert len(asked) == 1 and "disk gone" in asked[0][2]


def test_text_holder_when_imported_then_nothing_runs(monkeypatch, tmp_path) -> None:
    _, asked = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    opened = holder_show(monkeypatch)
    run_script(HOLDER, "imported")
    assert opened.calls == [] and asked == [] and not any(tmp_path.iterdir())


# --- Text Filter Demo ----------------------------------------------------------


class FakeSettings:
    """A QSettings stand-in backed by a dict; ``contains`` is the seeding test."""

    IniFormat = 7
    created: list = []

    def __init__(self, path, form) -> None:
        self.path, self.form, self.values = path, form, {}
        FakeSettings.created.append(self)

    def contains(self, key):
        return key in self.values

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def isWritable(self):
        return True

    def sync(self):
        pass

    def status(self):
        return 0


def filter_host(monkeypatch, tmp_path, dialog_error=None):
    """Stub the panel module and the dialog registry; return (gui, opened, dialog class)."""
    import fontlabapp.core.scripting as scripting

    gui, _ = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch)
    FakeSettings.created = []
    sys.modules["PythonQt"].QtCore.QSettings = FakeSettings
    panels = Recorder("panel")
    stub_module(monkeypatch, "fontlabapp.proof.text_filter.ui", TextFilterDialog=panels)
    opened = []

    def show_script_dialog(factory, key):
        if dialog_error:
            raise dialog_error
        opened.append((factory("parent"), key))

    monkeypatch.setattr(scripting, "show_script_dialog", show_script_dialog)
    return gui, opened, panels


def test_text_filter_when_main_then_shows_results_and_opens_panel_on_own_settings(monkeypatch, tmp_path) -> None:
    gui, opened, panels = filter_host(monkeypatch, tmp_path)
    run_script(FILTER)
    title, text, details = shown(gui)
    assert title == "Text Filter Demo" and "4 samples" in text
    lines = details.splitlines()
    assert lines[0].startswith("[a-zA-Z] -> 'Hamburgefonstivnavecafmega'")
    assert lines[1] == "[0-9] -> '2026'"
    assert lines[3].startswith("[z-a] -> re.error:"), "a malformed class reports re.error"
    (store,) = FakeSettings.created
    assert store.path == str(tmp_path / "fontlabapp-demos" / "text-filter" / "Text Simplifier.ini")
    assert store.form == FakeSettings.IniFormat
    assert store.values["input"].startswith("Hamburgefonstiv"), "sample input was seeded"
    (dialog, key), = opened
    assert key == "text_filter" and dialog == "panel"
    assert panels.calls == [(("parent",), {"settings": store})]


def test_text_filter_when_run_again_then_reuses_one_folder_and_resets_input(monkeypatch, tmp_path) -> None:
    gui, opened, _ = filter_host(monkeypatch, tmp_path)
    run_script(FILTER)
    run_script(FILTER)
    assert [p.name for p in tmp_path.iterdir()] == ["fontlabapp-demos"], "no second folder appears"
    assert {s.path for s in FakeSettings.created} == {str(tmp_path / "fontlabapp-demos" / "text-filter" / "Text Simplifier.ini")}
    assert all(s.values["input"].startswith("Hamburgefonstiv") for s in FakeSettings.created)
    assert len(opened) == 2


def test_text_filter_when_panel_already_open_then_one_message_and_no_panel(monkeypatch, tmp_path) -> None:
    _, asked = install_host(monkeypatch)
    redirect_temp(monkeypatch, tmp_path)
    open_windows(monkeypatch, text_filter=LiveWindow())
    stub_module(monkeypatch, "fontlabapp.proof.text_filter.ui", TextFilterDialog=Recorder())
    sys.modules["PythonQt"].QtCore.QSettings = FakeSettings
    FakeSettings.created = []
    run_script(FILTER)
    assert FakeSettings.created == [] and asked == []
    gui = sys.modules["PythonQt"].QtGui
    box = gui.QMessageBox.return_value
    assert "already open" in box.setInformativeText.call_args[0][0]
    assert not box.setDetailedText.called, "no sample results when the panel is not opened"


def test_text_filter_when_stored_panel_is_destroyed_then_drops_it_and_opens(monkeypatch, tmp_path) -> None:
    gui, opened, _ = filter_host(monkeypatch, tmp_path)
    open_windows(monkeypatch, text_filter=DestroyedWindow())
    run_script(FILTER)
    assert len(opened) == 1, "the panel opens"
    assert "already open" not in str(gui.QMessageBox.return_value.setInformativeText.call_args)
    assert "text_filter" not in sys._fontlab_samples, "the dead entry is dropped"


def test_text_filter_when_stored_panel_raises_other_value_error_then_keeps_it_and_does_not_open(monkeypatch, tmp_path) -> None:
    gui, opened, _ = filter_host(monkeypatch, tmp_path)
    open_windows(monkeypatch, text_filter=UnreadableWindow())
    run_script(FILTER)
    assert opened == [] and "text_filter" in sys._fontlab_samples, "only a destroyed widget is dropped"
    assert "already open" in gui.QMessageBox.return_value.setInformativeText.call_args[0][0]


def test_text_filter_when_panel_fails_then_second_message_names_error(monkeypatch, tmp_path) -> None:
    gui, opened, _ = filter_host(monkeypatch, tmp_path, dialog_error=RuntimeError("no parent"))
    run_script(FILTER)
    assert opened == [] and gui.QMessageBox.call_count == 2
    box = gui.QMessageBox.return_value
    assert "no parent" in box.setInformativeText.call_args[0][0]


def test_text_filter_when_imported_then_nothing_runs(monkeypatch, tmp_path) -> None:
    gui, opened, _ = filter_host(monkeypatch, tmp_path)
    run_script(FILTER, "imported")
    assert opened == [] and gui.QMessageBox.call_count == 0 and FakeSettings.created == []


# --- Proof Painters Demo -------------------------------------------------------


class Dialog:
    """A QDialog stand-in with the two signals the demo and OwnedWidget use."""

    def __init__(self, parent) -> None:
        self.parent, self.finished, self.destroyed = parent, FakeSignal(), FakeSignal()
        self.flags = Recorder()

    def __getattr__(self, name: str):  # every other Qt call is recorded and succeeds
        return Recorder()


class View:
    """A painter stand-in recording the content the demo publishes."""

    made: list = []

    def __init__(self) -> None:
        self.content = None
        View.made.append(self)

    def set_content(self, *args) -> None:
        self.content = args


class Grid(View):
    pass


class MasterRows(View):
    pass


class WaterfallView(View):
    pass


class OrderView(View):
    columns = None


def painters_host(monkeypatch, shots, failing_dialog=False):
    """Stub the painter modules and the three panel shells; return QtGui."""
    gui, _ = install_host(monkeypatch)
    View.made = []

    def broken(*args):
        raise RuntimeError("no dialog")

    gui.QDialog = broken if failing_dialog else Dialog
    sys.modules["PythonQt"].QtCore.QTimer.singleShot = lambda delay, call: shots.append((delay, call))
    stub_module(monkeypatch, "fontlabapp.proof.inspect.views", Grid=Grid, MasterRows=MasterRows, WaterfallView=WaterfallView)
    stub_module(
        monkeypatch,
        "fontlabapp.proof.inspectors.views",
        OrderView=OrderView,
        outline_path=lambda contours: ("path", tuple(tuple(points) for points in contours)),
    )
    for module, name in (
        ("proof.inspect", "ProofDialog"),
        ("proof.inspectors", "InspectorsDialog"),
        ("proof.review", "ReviewDialog"),
    ):
        stub_module(monkeypatch, f"fontlabapp.{module}.ui", **{name: type(name, (), {"__module__": f"fontlabapp.{module}.ui"})})
    return gui


def by_type(kind):
    (found,) = [view for view in View.made if type(view) is kind]
    return found


def test_painters_demo_when_main_then_feeds_sample_outlines_to_every_painter(monkeypatch) -> None:
    gui = painters_host(monkeypatch, [])
    (demo,) = run_script(PAINTERS)["_HANDLES"]
    assert demo.owned.widget.parent == "main-window"
    run, sizes, upm, ascender = by_type(WaterfallView).content
    assert [advance for _, advance in run] == [700, 700, 500, 700] and run[2][0] is None
    assert (sizes, upm, ascender) == ((16, 32, 64), 1000, 800)
    rows, size, upm, frame = by_type(MasterRows).content
    assert [(name, width) for name, _, width in rows] == [("Light", 1280), ("Regular", 1400), ("Bold", 1560)]
    assert all(run[2] == (None, 500) for _, run, _ in rows) and (size, upm, frame) == (40, 1000, (-200, 800))
    cells, masters, frame, cell = by_type(Grid).content
    assert [name for name, _ in cells] == ["box", "round", "missing"] and masters == ["Light", "Regular", "Bold"]
    assert [path for _, path, _ in cells[2][1]] == [None, None, None] and (frame, cell) == ((-200, 800), 120)
    columns = by_type(OrderView).columns
    assert [master for master, _ in columns] == masters
    assert [[direction for *_, direction in info] for _, info in columns] == [["ccw", "cw"]] * 3
    info_label = gui.QLabel.call_args_list[0][0][0]
    assert info_label == (
        "Box width by master: [640, 700, 780] (rising).\n"
        "ProofDialog (fontlabapp.proof.inspect.ui)\n"
        "InspectorsDialog (fontlabapp.proof.inspectors.ui)\n"
        "ReviewDialog (fontlabapp.proof.review.ui)"
    )


def test_painters_demo_when_window_finishes_then_releases_on_next_turn(monkeypatch) -> None:
    shots = []
    painters_host(monkeypatch, shots)
    handles = run_script(PAINTERS)["_HANDLES"]
    (demo,) = handles
    dialog = demo.owned.widget
    assert len(dialog.finished.slots) == 1
    dialog.finished.emit(0)
    assert [delay for delay, _ in shots] == [0] and handles == [demo], "release waits for Qt dispatch to return"
    shots[0][1]()
    assert handles == [] and dialog.finished.slots == [] and demo.owned.closed
    demo.release()  # a second release is harmless


def test_painters_demo_when_disconnect_fails_then_handle_still_leaves(monkeypatch) -> None:
    painters_host(monkeypatch, [])
    handles = run_script(PAINTERS)["_HANDLES"]
    (demo,) = handles

    def gone(slot):
        raise RuntimeError("widget destroyed")

    demo.finished.disconnect = gone
    with pytest.raises(RuntimeError, match="widget destroyed"):
        demo.release()
    assert handles == [] and demo.slot is None


def test_painters_demo_when_window_creation_fails_then_releases_and_reraises(monkeypatch) -> None:
    painters_host(monkeypatch, [], failing_dialog=True)
    names = run_script(PAINTERS, "imported")
    with pytest.raises(RuntimeError, match="no dialog"):
        names["main"]()
    assert names["_HANDLES"] == []


def test_painters_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui = painters_host(monkeypatch, [])
    names = run_script(PAINTERS, "imported")
    assert names["_HANDLES"] == [] and View.made == [] and gui.QLabel.call_count == 0


# --- Proof Tabs Demo -----------------------------------------------------------


def tabs_host(monkeypatch, answers, package=PACKAGE, text_error=None, named_error=None):
    gui, asked = install_host(monkeypatch, answers, package)

    def failing(error):
        def opener(*args, **kwargs):
            raise error

        return opener

    text = failing(text_error) if text_error else Recorder()
    named = failing(named_error) if named_error else Recorder()
    stub_module(monkeypatch, "fontlabapp.proof.tabs.text", open_text_tab=text)
    stub_module(monkeypatch, "fontlabapp.proof.tabs.named", open_named_tab=named)
    return gui, asked, text, named


def seeded_text() -> str:
    from fontlabapp.proof.random import generate

    return generate("lowercase-words", rng=random.Random(208))


def test_tabs_demo_when_both_confirmed_then_opens_text_and_named_tabs(monkeypatch) -> None:
    from fontlabapp.proof.context import proof_lines

    gui, asked, text, named = tabs_host(monkeypatch, [YES, YES])
    run_script(TABS)
    title, summary, details = shown(gui)
    assert summary == "Sample proofs are ready."
    assert details.startswith("random lowercase-words: ") and "context HHOHH for n, o: 1 rows" in details
    assert "context lining for H: 3 rows" in details, "a between-mode proof is the line, a blank row and a final blank row"
    assert [(a[1], a[3], a[4], a[5]) for a in asked] == [("Proof Tabs Demo", "Question", YES | NO, NO)] * 2
    assert "seeded random words" in asked[0][2] and "context rows for n and o" in asked[1][2]
    assert text.calls == [((seeded_text(),), {"expected_id": 3})]
    assert named.calls == [((proof_lines("HHOHH", ("n", "o")),), {"expected_id": 3, "master": "Regular"})]


def test_tabs_demo_when_declined_then_no_tab_opens(monkeypatch) -> None:
    gui, asked, text, named = tabs_host(monkeypatch, [NO, NO])
    run_script(TABS)
    assert len(asked) == 2 and text.calls == [] and named.calls == []


def test_tabs_demo_when_only_second_confirmed_then_only_named_tab_opens(monkeypatch) -> None:
    _, _, text, named = tabs_host(monkeypatch, [NO, YES])
    run_script(TABS)
    assert text.calls == [] and len(named.calls) == 1


def test_tabs_demo_when_no_font_then_shows_samples_and_asks_nothing(monkeypatch) -> None:
    gui, asked, text, named = tabs_host(monkeypatch, [], package=None)
    run_script(TABS)
    _, summary, details = shown(gui)
    assert summary == "Open a font to open sample tabs." and details
    assert asked == [] and text.calls == [] and named.calls == []


@pytest.mark.parametrize("error", [ValueError("font closed"), RuntimeError("no window"), TimeoutError("slow"), ExceptionGroup("restore", [ValueError("x")])])
def test_tabs_demo_when_opener_fails_then_warning_and_other_tab_still_offered(monkeypatch, error) -> None:
    # answers in call order: question 1, the warning box (OK), question 2
    _, asked, _, named = tabs_host(monkeypatch, [YES, OK, YES], text_error=error)
    run_script(TABS)
    warnings = [a for a in asked if a[3] == "Warning"]
    assert len(warnings) == 1 and "No tab for the seeded random words" in warnings[0][2]
    assert len(named.calls) == 1, "the second tab is independent of the first failure"


def test_tabs_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, asked, text, named = tabs_host(monkeypatch, [YES, YES])
    run_script(TABS, "imported")
    assert asked == [] and gui.QMessageBox.call_count == 0 and text.calls == [] and named.calls == []


# --- Extrema Proof Demo --------------------------------------------------------


def extrema_host(monkeypatch, answers, package=PACKAGE, error=None):
    gui, asked = install_host(monkeypatch, answers, package)

    def show_all():
        calls.append(1)
        if error:
            raise error

    calls: list = []
    stub_module(monkeypatch, "fontlabapp.proof.extrema.model", show_all=show_all)
    return asked, calls


def test_extrema_demo_when_confirmed_then_opens_panel_once(monkeypatch) -> None:
    asked, calls = extrema_host(monkeypatch, [YES])
    run_script(EXTREMA)
    assert calls == [1] and len(asked) == 1
    assert asked[0][3:] == ("Question", YES | NO, NO) and "new Glyph tab" in asked[0][2]


def test_extrema_demo_when_declined_then_nothing_opens(monkeypatch) -> None:
    asked, calls = extrema_host(monkeypatch, [NO])
    run_script(EXTREMA)
    assert calls == [] and len(asked) == 1


def test_extrema_demo_when_no_font_then_says_so_without_asking_to_scan(monkeypatch) -> None:
    asked, calls = extrema_host(monkeypatch, [YES], package=None)
    run_script(EXTREMA)
    assert calls == [] and [a[3] for a in asked] == ["Information"] and "Open a font" in asked[0][2]


@pytest.mark.parametrize("error", [ValueError("changed"), RuntimeError("no tab"), TimeoutError("slow")])
def test_extrema_demo_when_scan_fails_then_warning_names_error(monkeypatch, error) -> None:
    asked, calls = extrema_host(monkeypatch, [YES], error=error)
    run_script(EXTREMA)
    assert calls == [1] and asked[-1][3] == "Warning" and str(error) in asked[-1][2]


def test_extrema_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    asked, calls = extrema_host(monkeypatch, [YES])
    run_script(EXTREMA, "imported")
    assert asked == [] and calls == []


# --- Numeric Worksheets Demo ---------------------------------------------------


def numeric_host(monkeypatch, shown_error=None, detailed_error=None, package=PACKAGE):
    gui, asked = install_host(monkeypatch, package=package)
    calls: list = []

    def opener(name, error):
        def call():
            calls.append(name)
            if error:
                raise error

        return call

    stub_module(
        monkeypatch,
        "fontlabapp.proof.numeric.launcher",
        show=opener("show", shown_error),
        show_detailed=opener("show_detailed", detailed_error),
    )
    return asked, calls


def test_numeric_demo_when_main_then_opens_both_worksheets_silently(monkeypatch) -> None:
    asked, calls = numeric_host(monkeypatch)
    run_script(NUMERIC)
    assert calls == ["show", "show_detailed"] and asked == []


def test_numeric_demo_when_no_font_then_says_so_and_opens_no_panel(monkeypatch) -> None:
    asked, calls = numeric_host(monkeypatch, package=None)
    run_script(NUMERIC)
    assert calls == [], "no panel may open without a font"
    assert len(asked) == 1 and asked[0][3] == "Information" and "Open a font first" in asked[0][2]


def test_numeric_demo_when_first_fails_then_second_still_opens_and_message_lists_failure(monkeypatch) -> None:
    asked, calls = numeric_host(monkeypatch, shown_error=RuntimeError("main thread only"))
    run_script(NUMERIC)
    assert calls == ["show", "show_detailed"]
    assert len(asked) == 1 and asked[0][2] == "The worksheet did not open: main thread only"


def test_numeric_demo_when_both_fail_then_one_message_lists_both(monkeypatch) -> None:
    asked, _ = numeric_host(monkeypatch, shown_error=RuntimeError("thread"), detailed_error=TimeoutError("slow"))
    run_script(NUMERIC)
    assert asked[0][2].splitlines() == [
        "The worksheet did not open: thread",
        "The detailed worksheet did not open: slow",
    ]


def test_numeric_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    asked, calls = numeric_host(monkeypatch)
    run_script(NUMERIC, "imported")
    assert calls == [] and asked == []


# --- JSON Report Demo ----------------------------------------------------------


def test_json_report_demo_when_main_then_shows_detached_snapshot_and_refusals(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    window = Recorder("window")
    stub_module(monkeypatch, "fontlabapp.proof.reports.ui", show=window)
    names = run_script(JSON_REPORT)
    text = json.dumps(names["REPORT"], ensure_ascii=False, indent=2)
    assert window.calls == [((text, "JSON Report Demo", "json_report_demo"), {})]
    title, summary, details = shown(gui)
    assert summary == "The snapshot window is open."
    lines = details.splitlines()
    assert lines[0].startswith("NaN value: ValueError:") and lines[1].startswith("deadline already passed: TimeoutError:")


def test_json_report_demo_when_report_formats_then_refusal_line_says_formatted() -> None:
    names = run_script(JSON_REPORT, "imported")
    assert names["refusal_lines"](lambda report, **options: "ok") == [
        "NaN value: formatted",
        "deadline already passed: formatted",
    ]


def test_json_report_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    window = Recorder()
    stub_module(monkeypatch, "fontlabapp.proof.reports.ui", show=window)
    run_script(JSON_REPORT, "imported")
    assert window.calls == [] and gui.QMessageBox.call_count == 0


# --- Font Reports Demo ---------------------------------------------------------


class MasterNodeReportDialog:
    KEY = "master_node_report"


class SvgPathCommandsDialog:
    KEY = "svg_path_commands"


def reports_host(monkeypatch, package=PACKAGE, crossfont_error=None, dialog_errors=()):
    import fontlabapp.core.scripting as scripting

    gui, asked = install_host(monkeypatch, package=package)
    opened: list = []

    def show(composites=False):
        opened.append(("crossfont", composites))
        if crossfont_error and not composites:
            raise crossfont_error

    def show_script_dialog(kind, key):
        opened.append((kind.__name__, key))
        if kind.__name__ in dialog_errors:
            raise RuntimeError("no selection")

    stub_module(monkeypatch, "fontlabapp.proof.crossfont.model", show=show)
    stub_module(
        monkeypatch,
        "fontlabapp.proof.reports.specialized_ui",
        MasterNodeReportDialog=MasterNodeReportDialog,
        SvgPathCommandsDialog=SvgPathCommandsDialog,
    )
    monkeypatch.setattr(scripting, "show_script_dialog", show_script_dialog)
    return asked, opened


def test_font_reports_demo_when_font_open_then_opens_all_four_reports(monkeypatch) -> None:
    asked, opened = reports_host(monkeypatch)
    run_script(FONT_REPORTS)
    assert opened == [
        ("crossfont", False),
        ("crossfont", True),
        ("MasterNodeReportDialog", "master_node_report"),
        ("SvgPathCommandsDialog", "svg_path_commands"),
    ]
    assert asked == []


def test_font_reports_demo_when_one_fails_then_others_open_and_message_lists_it(monkeypatch) -> None:
    asked, opened = reports_host(monkeypatch, crossfont_error=ValueError("fonts changed"), dialog_errors=("SvgPathCommandsDialog",))
    run_script(FONT_REPORTS)
    assert len(opened) == 4, "a failing report must not stop the rest"
    assert len(asked) == 1 and asked[0][3] == "Warning"
    assert asked[0][2].splitlines()[1:] == ["glyph set differences: fonts changed", "SVG path commands: no selection"]


def test_font_reports_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    asked, opened = reports_host(monkeypatch, package=None)
    run_script(FONT_REPORTS)
    assert opened == [] and len(asked) == 1 and "Open a font" in asked[0][2]


def test_font_reports_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    asked, opened = reports_host(monkeypatch)
    run_script(FONT_REPORTS, "imported")
    assert opened == [] and asked == []
