# this_file: tests/_demo_support.py
"""Run an App demo script offline: runpy plus stub modules, all restored.

What: ``stub_module`` registers a stand-in in ``sys.modules`` (restored by
monkeypatch), ``run_script`` runs a ``Scripts/<Category>/<Title>.py`` file with
runpy under any ``__name__``, ``qt_namespace`` builds a PythonQt stand-in whose
unknown names are recorded mocks, and ``Recorder`` captures calls.
Use: a ``tests/test_demo_scripts_<area>.py`` file stubs the native or heavy
``fontlabapp`` modules a demo imports lazily, runs the script as ``__main__``
and asserts the calls, then runs it as ``imported`` and asserts nothing ran.
Why: demos import ``fontlabapp`` lazily inside ``main``, so a stubbed
``sys.modules`` entry replaces exactly one dependency and the real modules stay
under test. ``tests/test_demo_scripts.py`` checks the names the stubs mimic.
"""

import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]


def script_path(category: str, title: str) -> Path:
    """Path of ``Scripts/<category>/<title>.py`` (title without the suffix)."""
    return ROOT / "Scripts" / category / f"{title}.py"


def run_script(path: Path, run_name: str = "__main__") -> dict[str, Any]:
    """Run the file with runpy and return its globals."""
    return runpy.run_path(str(path), run_name=run_name)


def stub_module(monkeypatch: Any, name: str, **attributes: Any) -> ModuleType:
    """Register ``name`` in ``sys.modules`` with ``attributes``; restored on teardown."""
    module = ModuleType(name)
    module.__dict__.update(attributes)
    monkeypatch.setitem(sys.modules, name, module)
    if name == "fontlab":
        monkeypatch.setitem(sys.modules, "echopy.fontlab", module)
    return module


class Recorder:
    """A callable that records ``(args, kwargs)`` and returns a fixed result."""

    def __init__(self, result: Any = None) -> None:
        self.calls: list[tuple[tuple, dict]] = []
        self.result = result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return self.result


class FakeSignal:
    """A Qt signal stand-in: ``connect``/``disconnect`` track slots, ``emit`` calls them."""

    def __init__(self) -> None:
        self.slots: list[Any] = []

    def connect(self, slot: Any) -> None:
        self.slots.append(slot)

    def disconnect(self, slot: Any) -> None:
        self.slots.remove(slot)

    def emit(self, *args: Any) -> None:
        for slot in list(self.slots):
            slot(*args)


class FakeWidget:
    """Base for Qt classes a demo subclasses; keeps a native-like key handler."""

    def __init__(self, *args: Any) -> None:
        self.args = args
        self.base_keys: list[Any] = []
        self.placeholder = None

    def keyPressEvent(self, event: Any) -> None:
        self.base_keys.append(event)

    def setPlaceholderText(self, text: str) -> None:
        self.placeholder = text


def qt_namespace(**names: Any) -> SimpleNamespace:
    """A ``PythonQt`` stand-in: ``QtGui``/``QtCore`` hold ``names`` plus recorded mocks."""
    gui = MagicMock(name="QtGui")
    gui.QLineEdit = FakeWidget
    for name, value in names.items():
        setattr(gui, name, value)
    return SimpleNamespace(QtGui=gui, QtCore=MagicMock(name="QtCore"))


def stub_natives(monkeypatch: Any, app: Any, native: Any) -> None:
    """Supply the same host stand-ins to App internals and real Fly routing."""
    monkeypatch.setattr(app, "_native", native)
    monkeypatch.setitem(sys.modules, "echopy.fontlab", native("fontlab"))
    monkeypatch.setitem(sys.modules, "PythonQt", native("PythonQt"))
