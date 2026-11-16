# this_file: tests/test_demo_scripts_utilities.py
"""Offline runs of the four Scripts/Utilities demos under stubbed natives (Issue 208).

Each demo runs through runpy as ``__main__`` (entry point and arguments are
asserted) and as an imported name (nothing may run). The real ``fontlabapp``
modules stay in use wherever they are host-free; only ``PythonQt``, ``fontlab``,
``fontpr`` and the host-bound ``fontlabapp.core`` modules are replaced.
Offline results are not native FontLab acceptance.
"""

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _demo_support import (
    FakeSignal, Recorder, qt_namespace, run_script, script_path, stub_module,
)

APP_INFO = script_path("Utilities", "Application Info Demo")
HOST_MENUS = script_path("Utilities", "Host Menus Demo")
SIGNALS = script_path("Utilities", "Signals And Hotkeys Demo")
CORE = script_path("Utilities", "Core Utilities Demo")


def install_qt(monkeypatch, **names):
    """Stub PythonQt with message boxes etc.; return its QtGui namespace."""
    qt = qt_namespace(**names)
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    return qt


def shown_report(gui) -> str:
    """The details text of the one message box the demo showed."""
    box = gui.QMessageBox.return_value
    box.show.assert_called_once_with()
    box.setModal.assert_called_once_with(False)
    return box.setDetailedText.call_args[0][0]


def versions():
    return SimpleNamespace(
        app_name="FontLab", app_version="9.0.1", app_arch="arm64", os_full_name="macOS 15",
        os_version="15.1", os_arch="arm64", py_version="3.11.9", qt_version="6.5.0",
    )


def fake_app(tmp_path, pref=None):
    names = ("appFolder", "appDataFolder", "userDataFolder", "sysUserPrefFolder", "tempFolder")
    paths = SimpleNamespace(**{name: tmp_path / name for name in names}, appPrefLibPath=pref or tmp_path / "missing.json")
    return SimpleNamespace(versions=versions(), paths=paths, main="main-window")


# --- Application Info Demo -------------------------------------------------


def test_application_info_when_main_then_builds_read_only_app_and_shows_report(monkeypatch, tmp_path) -> None:
    pref = tmp_path / "pref.json"
    pref.write_text(json.dumps({"b": 1, "a": 2}), encoding="utf-8")
    created = Recorder(fake_app(tmp_path, pref))
    stub_module(monkeypatch, "fontlabapp.core.application.context", Application=created)
    qt = install_qt(monkeypatch)
    run_script(APP_INFO)
    assert created.calls == [((), {"with_ui": False, "with_preflib": False})], "must skip preflib and UI"
    text = shown_report(qt.QtGui)
    assert "Application: FontLab 9.0.1 (arm64)" in text and "Qt: 6.5.0" in text
    assert f"User preferences: {tmp_path / 'sysUserPrefFolder'}" in text and "top-level keys: a, b" in text
    box = qt.QtGui.QMessageBox.return_value
    assert qt.QtGui.QMessageBox.call_args[0] == ("main-window",), "box parents to the main window"
    box.setWindowTitle.assert_called_once_with("Application Info Demo")


def test_application_info_when_imported_then_nothing_runs(monkeypatch) -> None:
    created = Recorder()
    stub_module(monkeypatch, "fontlabapp.core.application.context", Application=created)
    names = run_script(APP_INFO, "imported")
    assert created.calls == [] and callable(names["main"])


class Unreadable:
    def __str__(self) -> str:
        return "unreadable.json"

    def is_file(self) -> bool:
        return True

    def read_text(self, encoding: str) -> str:
        raise OSError("permission denied")


@pytest.mark.parametrize(
    "content,expected",
    [
        (None, "(not created yet)"),
        ("{not json", "(unreadable: "),
        ("[1, 2]", "(not a JSON object)"),
        ("{}", "top-level keys: none"),
    ],
)
def test_preflib_lines_when_file_state_varies_then_describes_it_without_writing(tmp_path, content, expected) -> None:
    path = tmp_path / "pref.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    lines = run_script(APP_INFO, "imported")["preflib_lines"](path)
    assert expected in "\n".join(lines)
    assert path.exists() == (content is not None), "the demo must never create the file"


def test_preflib_lines_when_read_fails_then_reports_error() -> None:
    assert "permission denied" in run_script(APP_INFO, "imported")["preflib_lines"](Unreadable())[0]


# --- Host Menus Demo ---------------------------------------------------------


class FakeAction:
    def __init__(self, shortcut: str = "") -> None:
        self.shortcut = shortcut


class FakeMenu:
    def __init__(self, title: str, children: tuple = ()) -> None:
        self.title, self.children = title, children

    def __iter__(self):
        return iter(self.children)


class FakePanel:
    def __init__(self, label: str, supported: bool, visible: bool = False) -> None:
        self.label, self.supported, self._visible = label, supported, visible

    @property
    def visible(self) -> bool:
        assert self.supported, "visibility of an unsupported panel must not be read"
        return self._visible


def fake_host(actions: dict) -> SimpleNamespace:
    file_menu = FakeMenu("File", (FakeAction("Ctrl+N"), FakeAction(), FakeMenu("Recent", (FakeAction(),))))
    menu_bar = [file_menu, FakeAction("Ctrl+Q"), FakeMenu("Glyph & Metrics")]
    panels = [FakePanel("Preview", True, True), FakePanel("Output", True), FakePanel("Chat", False)]
    return SimpleNamespace(menu=menu_bar, panels=panels, glyph_actions=SimpleNamespace(items=lambda: actions), main="main-window")


def test_host_menus_when_main_then_reads_trees_and_triggers_nothing(monkeypatch) -> None:
    host = fake_host({f"action_{n}": object() for n in range(15)})
    stub_module(monkeypatch, "fontlabapp.core.host", Menu=FakeMenu, live=Recorder(host))
    qt = install_qt(monkeypatch)
    run_script(HOST_MENUS)
    text = shown_report(qt.QtGui)
    assert "File (menu.file): 3 actions, 1 submenus, 1 shortcuts" in text
    assert "Glyph & Metrics (menu.glyph_metrics): 0 actions, 0 submenus, 0 shortcuts" in text
    assert "Preview: visible" in text and "Output: hidden" in text and "Chat: visibility not readable" in text
    assert "15 actions: action_0, " in text and text.rstrip().endswith("action_11, ...")
    assert qt.QtGui.QMessageBox.call_args[0] == ("main-window",)
    assert qt.QtGui.QMessageBox.return_value.setInformativeText.call_args[0][0] == "2 menus and 3 panels read."


def test_host_menus_when_few_actions_then_list_has_no_ellipsis() -> None:
    action_lines = run_script(HOST_MENUS, "imported")["action_lines"]
    assert action_lines(SimpleNamespace(glyph_actions=SimpleNamespace(items=lambda: {"a": 1, "b": 2}))) == ["2 actions: a, b"]


def test_host_menus_when_imported_then_nothing_runs(monkeypatch) -> None:
    live = Recorder()
    stub_module(monkeypatch, "fontlabapp.core.host", Menu=FakeMenu, live=live)
    run_script(HOST_MENUS, "imported")
    assert live.calls == []


# --- Signals And Hotkeys Demo --------------------------------------------------


class Dialog:
    """A QDialog stand-in with the two signals the demo and OwnedWidget use."""

    def __init__(self, parent) -> None:
        self.parent, self.finished, self.destroyed = parent, FakeSignal(), FakeSignal()
        self.flags = MagicMock()

    def __getattr__(self, name: str):  # every other Qt call is recorded and succeeds
        return MagicMock(name=name)


class Label:
    def __init__(self, text: str, parent) -> None:
        self.text = text

    def setText(self, text: str) -> None:
        self.text = text


class Button:
    def __init__(self, text: str, parent) -> None:
        self.text, self.clicked = text, FakeSignal()

    def click(self) -> None:
        self.clicked.emit()


class CheckBox:
    def __init__(self, text: str, parent) -> None:
        self.text, self.toggled = text, FakeSignal()


def signals_qt(monkeypatch, shots, **extra):
    """Install a PythonQt whose single-shot timer stores callbacks for the test to run."""
    widgets = {"QDialog": Dialog, "QLabel": Label, "QPushButton": Button, "QCheckBox": CheckBox, **extra}
    qt = install_qt(monkeypatch, **widgets)
    qt.QtCore.QTimer.singleShot = lambda delay, call: shots.append((delay, call))
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: "main-window")
    return qt


def widgets_of(qt):
    layout = qt.QtGui.QVBoxLayout.return_value
    hotkeys, status, field, click, quiet, check = (call[0][0] for call in layout.addWidget.call_args_list)
    return hotkeys, status, field, click, quiet, check


def test_signals_demo_when_used_then_counts_quietly_and_releases_on_close(monkeypatch) -> None:
    shots = []
    qt = signals_qt(monkeypatch, shots)
    handles = run_script(SIGNALS)["_HANDLES"]
    (demo,) = handles
    hotkeys, status, field, click, quiet, check = widgets_of(qt)
    assert field.placeholder and "Global hotkeys:" in hotkeys.text and "This demo registers no hotkeys" in hotkeys.text
    assert demo.owned.widget.parent == "main-window"
    click.click()
    quiet.click()  # programmatic click under quiet_callbacks: ignored
    assert (demo.state.clicks, demo.state.ignored, demo.state._quiet) == (1, 1, False)
    event = SimpleNamespace(key=lambda: 65, accept=Recorder())
    field.keyPressEvent(event)
    assert field.base_keys == [event] and event.accept.calls == [], "unhandled key goes to the native base once"
    check.toggled.emit(True)
    assert status.text == "Key presses: 1 (last key code 65)\nClicks counted: 1, quiet clicks ignored: 1\nToggles: 1"
    demo.owned.widget.finished.emit(0)
    assert [delay for delay, _ in shots] == [0] and handles == [demo], "release waits for Qt dispatch to return"
    shots[0][1]()
    assert handles == [] and demo.scope.closed and demo.owned.closed
    assert click.clicked.slots == [] and quiet.clicked.slots == [] and check.toggled.slots == []
    click.click()
    assert demo.state.clicks == 1, "a closed scope must ignore clicks"
    demo.release()  # a second release is harmless
    assert demo.problems == []


@pytest.mark.parametrize("failing", ["QDialog", "QCheckBox"])
def test_signals_demo_when_window_creation_fails_then_releases_and_reraises(monkeypatch, failing) -> None:
    """A failing dialog constructor or widget build leaves no retained demo behind."""

    def broken(*args):
        raise RuntimeError("no " + failing)

    signals_qt(monkeypatch, [], **{failing: broken})
    names = run_script(SIGNALS, "imported")
    with pytest.raises(RuntimeError, match="no " + failing):
        names["main"]()
    assert names["_HANDLES"] == []


@pytest.mark.parametrize(
    "platform,spec,expected",
    [
        ("win32", None, "not implemented on Windows"),
        ("linux", None, "no backend for linux"),
        ("darwin", None, "needs pyobjc-framework-Quartz"),
        ("darwin", object(), "macOS backend available"),
    ],
)
def test_hotkey_lines_when_platform_varies_then_reports_availability_only(monkeypatch, platform, spec, expected) -> None:
    hotkey_lines = run_script(SIGNALS, "imported")["hotkey_lines"]
    monkeypatch.setitem(hotkey_lines.__globals__, "find_spec", lambda name: spec)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.delitem(sys.modules, "fontlabapp.core.hotkey.manager", raising=False)
    lines = hotkey_lines()
    assert expected in lines[0] and lines[1] == "This demo registers no hotkeys"
    assert "fontlabapp.core.hotkey.manager" not in sys.modules, "no hotkey manager may be imported"


def test_signals_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    shots = []
    qt = signals_qt(monkeypatch, shots)
    names = run_script(SIGNALS, "imported")
    assert names["_HANDLES"] == [] and qt.QtGui.QVBoxLayout.call_count == 0


# --- Core Utilities Demo -------------------------------------------------------


def core_stubs(monkeypatch, tmp_path, updates=(), package=None, fonts=()):
    created = Recorder(fake_app(tmp_path))
    stub_module(monkeypatch, "fontlabapp.core.application.context", Application=created)
    qt = install_qt(monkeypatch)
    fontlab = stub_module(
        monkeypatch, "fontlab",
        flGlyph=SimpleNamespace(updatedFgGlyphs=lambda: updates),
        flWorkspace=SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=package)),
    )
    called = Recorder({"fonts": list(fonts)})
    stub_module(monkeypatch, "fontpr", call=called)
    return created, qt, fontlab, called


def test_core_utilities_when_main_then_reports_all_sections_read_only(monkeypatch, tmp_path) -> None:
    package = SimpleNamespace(isNull=False, id=3, fgId=77)
    created, qt, _, called = core_stubs(monkeypatch, tmp_path, updates=(4, 5), package=package, fonts=({"name": "Alpha"},))
    run_script(CORE)
    assert created.calls == [((), {"with_ui": False, "with_preflib": False})]
    assert called.calls == [(("list_fonts",), {})], "only the read-only font list is requested"
    text = shown_report(qt.QtGui)
    assert "Open fonts: 1; current font id 77" in text and "{'name': 'Alpha'}" in text
    for name in ("application", "host", "hotkey", "signals", "scripting", "history", "edit_guards",
                 "completion", "controls", "utils", "menu_names", "native_tabs", "legacy", "shimgen"):
        assert f"core.{name} (" in text, name
    for expected in ("menus.Menu -> fontlabapp.core.host", "objects.FontLab -> fontlabapp.core.controls",
                     "qtsafe_api.qt_list -> fontlabapp.qt.safe", "shortcuts.key_press_handler -> fontlabapp.qt.events.key",
                     "signals.Scope -> fontlabapp.core.signals.scope", "menus.OWNED_MENU_TITLE -> a constant"):
        assert expected in text, expected
    assert "unavailable" not in text
    assert "Pending glyph updates: 2" in text and "FontLab had queued updates for 2 glyphs" in text
    assert "snake('Glyph && Metrics...') = 'glyph_and_metrics'" in text and "slugify(" in text
    assert "deepmerge({'a': {'b': 1}}, {'a': {'c': 2}}) = {'a': {'b': 1, 'c': 2}}" in text
    assert "attribdict({'x': 1}).x = 1" in text and "stringify(b'bytes') = 'bytes'" in text


def test_core_utilities_when_no_font_and_no_queue_then_says_so(monkeypatch, tmp_path) -> None:
    _, qt, _, _ = core_stubs(monkeypatch, tmp_path)
    run_script(CORE)
    text = shown_report(qt.QtGui)
    assert "Open fonts: 0; no font open" in text and "Pending glyph updates: 0" in text
    assert "No pending-update note." in text


def test_shim_lines_when_name_cannot_resolve_then_marks_it_unavailable(monkeypatch) -> None:
    names = run_script(CORE, "imported")
    broken = SimpleNamespace(__all__=["missing"], __doc__=None)
    assert names["first_line"](broken) == ""
    monkeypatch.setitem(names["shim_lines"].__globals__, "SHIMS", ("fontlabapp.menus",))
    (line,) = names["shim_lines"](lambda name: broken)
    assert line.startswith("menus.missing -> unavailable (AttributeError: ")


def test_core_utilities_when_imported_then_nothing_runs(monkeypatch, tmp_path) -> None:
    created, _, _, _ = core_stubs(monkeypatch, tmp_path)
    run_script(CORE, "imported")
    assert created.calls == []
