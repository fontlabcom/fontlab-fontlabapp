# this_file: tests/test_qtsafe.py
"""Native widget conversion must not run the cyclic garbage collector."""

import gc
import importlib
import subprocess
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from fontlabapp.qt.views import GlyphWindow, Preview


@pytest.fixture(params=[True, False], ids=["gc-enabled", "gc-disabled"])
def gc_state(request):
    previous = gc.isenabled()
    (gc.enable if request.param else gc.disable)()
    try:
        yield request.param
    finally:
        (gc.enable if previous else gc.disable)()


@pytest.mark.parametrize("fail", [False, True], ids=["success", "error"])
@pytest.mark.parametrize("path", ["all", "top", "top-filtered", "children", "preview", "canvas"])
def test_widget_lookup_when_enumerating_then_gc_disabled_and_restored(
    monkeypatch, gc_state, fail, path
):
    qt = SimpleNamespace(QtGui=SimpleNamespace(QWidget=object))
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    ui_type = importlib.import_module("fontlabapp.core.application.ui").ApplicationUI
    ui = ui_type.__new__(ui_type)
    widget = SimpleNamespace(
        statusTip="@previewpanel.PreviewPanel",
        className=lambda: "FontPreviewWidget",
        objectName="widgetPreview",
    )
    states = []

    def enumerate_widgets(*args):
        states.append(gc.isenabled())
        if fail:
            raise RuntimeError("enumeration failed")
        return [widget]

    if path == "all":
        ui.qapp = SimpleNamespace(allWidgets=enumerate_widgets)
        lookup = ui.buildWidgetsDict
    elif path in {"top", "top-filtered"}:
        parent = SimpleNamespace(topLevelWidgets=enumerate_widgets)
        lookup = lambda: ui.findWidgets(parent, "FontPreviewWidget" if path == "top-filtered" else None)
    elif path == "children":
        parent = SimpleNamespace(findChildren=enumerate_widgets)
        lookup = lambda: ui.findWidgets(parent, "FontPreviewWidget")
    elif path == "preview":
        parent = SimpleNamespace(findChildren=enumerate_widgets)
        lookup = lambda: Preview(parent)
    else:
        parent = SimpleNamespace(findChildren=enumerate_widgets)
        glyph = GlyphWindow(
            SimpleNamespace(widgetViewport=parent),
            SimpleNamespace(getCanvasForViewport=lambda w: widget if w is widget else None),
        )
        lookup = lambda: glyph.canvas

    if fail:
        with pytest.raises(RuntimeError, match="enumeration failed"):
            lookup()
    else:
        result = lookup()
        if path == "all":
            assert result.previewpanel.PreviewPanel is widget
        elif path == "preview":
            assert result.widget is widget
        elif path == "canvas":
            assert result is widget
        else:
            assert result == [widget]
    assert states and not any(states), "native conversion must run with GC disabled"
    assert gc.isenabled() is gc_state, "lookup must restore the caller's GC state"


@pytest.mark.parametrize("fail", [False, True], ids=["success", "error"])
def test_qt_list_when_iterating_then_gc_disabled_and_restored(gc_state, fail):
    from fontlabapp.qt.safe import qt_list

    states = []
    widget = object()

    def convert():
        states.append(gc.isenabled())

        def items():
            states.append(gc.isenabled())
            if fail:
                raise RuntimeError("conversion failed")
            yield widget

        return items()

    if fail:
        with pytest.raises(RuntimeError, match="conversion failed"):
            qt_list(convert)
    else:
        assert qt_list(convert) == [widget]
    assert states == [False, False], "both the native call and iteration need the guard"
    assert gc.isenabled() is gc_state, "conversion must restore the caller's GC state"


def test_public_qtsafe_when_cold_imported_then_only_stdlib_dependencies_load():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root != 'fontlabapp' and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
from fontlabapp.qt.safe import qt_list
import fontlabapp.qt.safe as q
assert q.main_window
assert qt_list(lambda: (1, 2)) == [1, 2]
assert not any(name.split('.')[0] in {
    'PythonQt', 'fontlab', 'fontgate', 'FL', 'fontpr',
    'fontport', 'fontlab_fontport', 'glyport', 'fontlab_glyport',
} for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("stage", ["call", "iteration"])
@pytest.mark.parametrize("fail", [False, True], ids=["success", "error"])
@pytest.mark.parametrize("toggle", [gc.enable, gc.disable], ids=["enable", "disable"])
def test_qt_list_when_callback_toggles_gc_then_original_state_restored(
    gc_state, stage, fail, toggle
):
    qt_list = importlib.import_module("fontlabapp.qt.safe").qt_list
    argument = object()
    calls = []

    def run_stage():
        toggle()
        if fail:
            raise RuntimeError("callback failed")

    def convert(value):
        assert value is argument, "qt_list must forward positional arguments"
        calls.append(gc.isenabled())
        if stage == "call":
            run_stage()

        def items():
            if stage == "iteration":
                run_stage()
            yield value

        return items()

    if fail:
        with pytest.raises(RuntimeError, match="callback failed"):
            qt_list(convert, argument)
    else:
        assert qt_list(convert, argument) == [argument], "conversion must retain items"
    assert calls == [False], "the callable must start with cyclic GC disabled"
    assert gc.isenabled() is gc_state, "callback changes must not escape the guard"


def test_qt_list_when_called_off_the_gui_thread_then_runtime_error_and_gc_untouched():
    import threading

    from fontlabapp.qt.safe import qt_list

    errors, calls = [], []

    def worker():
        try:
            qt_list(lambda: calls.append(1) or [])
        except RuntimeError as error:
            errors.append(str(error))

    before = gc.isenabled()
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(5)
    assert errors == ["qt_list must run on the GUI thread"]
    assert calls == [], "the native call must not run off the GUI thread"
    assert gc.isenabled() is before, "a refused call must not touch GC state"


def test_legacy_private_module_when_looked_up_then_gone():
    with pytest.raises(ImportError):
        importlib.import_module("fontlabapp._qtsafe")


class _Window:
    def __init__(self, name):
        self.name = name

    def className(self):
        return self.name


def test_main_window_when_fontlab_returns_one_then_used_without_scan():
    from fontlabapp.qt.safe import main_window

    window = object()
    fontlab = SimpleNamespace(MainWindow=lambda: window)
    qt = SimpleNamespace(QtGui=SimpleNamespace(QApplication=None))
    assert main_window(fontlab, qt) is window


def test_main_window_when_fontlab_has_none_then_scans_top_levels_with_gc_off():
    from fontlabapp.qt.safe import main_window

    states = []
    wanted = _Window("MainWindow")

    def top_level():
        states.append(gc.isenabled())
        return [_Window("QDialog"), wanted, _Window("MainWindow")]

    qt = SimpleNamespace(
        QtGui=SimpleNamespace(QApplication=SimpleNamespace(topLevelWidgets=top_level))
    )
    for fontlab in (SimpleNamespace(MainWindow=lambda: None), SimpleNamespace()):
        assert main_window(fontlab, qt) is wanted, "first MainWindow wins"
    assert states == [False, False], "scan must run with cyclic GC off"


def test_main_window_when_nothing_found_then_runtime_error():
    from fontlabapp.qt.safe import main_window

    qt = SimpleNamespace(
        QtGui=SimpleNamespace(
            QApplication=SimpleNamespace(topLevelWidgets=lambda: [_Window("QDialog")])
        )
    )
    with pytest.raises(RuntimeError, match="main window"):
        main_window(SimpleNamespace(MainWindow=lambda: None), qt)


# --- MainWindowNotFound (issue 122, T14) ---------------------------------------


def _no_main_window_qt():
    return SimpleNamespace(
        QtGui=SimpleNamespace(
            QApplication=SimpleNamespace(topLevelWidgets=lambda: [_Window("QDialog")])
        )
    )


def test_main_window_when_nothing_found_then_typed_error_keeps_old_text():
    from fontlabapp.qt.safe import MainWindowNotFound, main_window

    assert issubclass(MainWindowNotFound, RuntimeError), "old except-RuntimeError callers"
    with pytest.raises(MainWindowNotFound) as info:
        main_window(SimpleNamespace(MainWindow=lambda: None), _no_main_window_qt())
    assert "main window not found" in str(info.value), "text-matching callers keep working"


def test_qt_list_when_refused_off_thread_then_plain_runtime_error_not_missing_window():
    import threading

    from fontlabapp.qt.safe import MainWindowNotFound, qt_list

    caught = []

    def worker():
        try:
            qt_list(list)
        except RuntimeError as error:
            caught.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(5)
    assert len(caught) == 1, caught
    assert not isinstance(caught[0], MainWindowNotFound), "thread refusal is no missing host"
