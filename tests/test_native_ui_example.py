# this_file: tests/test_native_ui_example.py
"""Exercise the external example's ownership and errors without native Qt."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def example(monkeypatch):
    remote = ModuleType("fontlab_remopy")
    remote.FontLab = object
    monkeypatch.setitem(sys.modules, "fontlab_remopy", remote)
    path = Path(__file__).resolve().parents[1] / "examples/native_ui.py"
    spec = importlib.util.spec_from_file_location("native_ui_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def host(monkeypatch):
    import fontlabapp

    state = SimpleNamespace(
        events=[], failure=None, closed=0, host=ModuleType("fontlab")
    )

    class Control:
        def __init__(self):
            self.preview = SimpleNamespace(
                draw=lambda paint: self.make("preview", paint)
            )

        def make(self, kind, build):
            state.events.append(kind)
            if state.failure == kind:
                raise RuntimeError(kind)
            build(
                SimpleNamespace(
                    setPen=lambda *a: None,
                    drawLine=lambda *a: None,
                    drawText=lambda *a: None,
                )
            )
            return SimpleNamespace(widget=SimpleNamespace(isVisible=lambda: True))

        def create_panel(self, title, build):
            return self.make("panel", build)

        def create_dialog(self, title, build):
            return self.make("dialog", build)

        def close(self):
            state.closed += 1
            if state.failure == "close":
                raise RuntimeError("close")

    qt = SimpleNamespace(
        QVBoxLayout=lambda widget: SimpleNamespace(
            addWidget=lambda value: state.events.append(value)
        ),
        QLabel=lambda text, widget: text,
        QLineEdit=lambda text, widget: text,
        QColor=lambda value: value,
    )
    monkeypatch.setitem(sys.modules, "fontlab", state.host)
    monkeypatch.setitem(sys.modules, "echopy.fontlab", state.host)
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=qt))
    monkeypatch.setitem(fontlabapp.__dict__, "FontLab", Control)
    for name in ("typerig", "typerig.proxy", "typerig.proxy.fl", "typerig.proxy.fl.gui"):
        package = ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    monkeypatch.setitem(
        sys.modules,
        "typerig.proxy.fl.gui.widgets",
        SimpleNamespace(CustomSpinLabel=lambda *args: ("typerig", args)),
    )
    return state


@pytest.mark.parametrize("typerig", [False, True])
def test_show_ui_when_success_then_waits_externally_and_removes_owned_handles(
    example, host, monkeypatch, typerig
):
    def wait(seconds):
        assert seconds == 2
        assert (
            len([key for key in vars(host.host) if key.startswith("_remopy_ui_")]) == 1
        )
        assert host.closed == 0

    monkeypatch.setattr(example.time, "sleep", wait)
    result = example.show_ui(
        SimpleNamespace(python=lambda fn: fn), seconds=2, typerig=typerig
    )
    assert result == {"panel": True, "dialog": True, "typerig": typerig}
    assert host.closed == 1
    assert not any(key.startswith("_remopy_ui_") for key in vars(host.host))
    assert [x for x in host.events if x in ("panel", "dialog", "preview")] == [
        "panel",
        "dialog",
        "preview",
    ]
    assert (
        any(isinstance(x, tuple) and x[0] == "typerig" for x in host.events)
    ) == typerig
    assert ("Łódź" in host.events) != typerig


@pytest.mark.parametrize("failure", ["panel", "dialog", "preview", "wait"])
def test_show_ui_when_setup_or_wait_fails_then_closes_and_preserves_error(
    example, host, monkeypatch, failure
):
    host.failure = failure

    def wait(seconds):
        raise RuntimeError("wait")

    monkeypatch.setattr(example.time, "sleep", wait)
    with pytest.raises(RuntimeError, match=failure):
        example.show_ui(SimpleNamespace(python=lambda fn: fn), seconds=0)
    assert host.closed == 1
    assert not any(key.startswith("_remopy_ui_") for key in vars(host.host))


def test_show_ui_when_negative_duration_then_refuses_before_remote_calls(example):
    with pytest.raises(ValueError, match="nonnegative"):
        example.show_ui(None, seconds=-1)


def test_show_ui_when_close_fails_then_preserves_error_and_recovery_handle(
    example, host, monkeypatch
):
    host.failure = "close"
    monkeypatch.setattr(example.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="close"):
        example.show_ui(SimpleNamespace(python=lambda fn: fn), seconds=0)
    assert host.closed == 1
    assert len([key for key in vars(host.host) if key.startswith("_remopy_ui_")]) == 1
