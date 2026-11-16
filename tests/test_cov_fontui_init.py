# this_file: tests/test_cov_fontui_init.py
"""Coverage for ``fontlabapp.fontui``: lazy factories, ``_construct`` cleanup and restored editors."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

fontui = importlib.import_module("fontlabapp.fontui")


class Probe:
    """Records construction arguments; never fails."""

    def __init__(self, *args: Any) -> None:
        self.args = args


def _fake_module(monkeypatch: pytest.MonkeyPatch, name: str, **members: Any) -> None:
    """Install ``fontlabapp.fontui.<name>`` as a stub so no Qt code is imported."""
    module = ModuleType(f"fontlabapp.fontui.{name}")
    for key, value in members.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, module.__name__, module)


# ----------------------------------------------------------- _construct


def test_construct_when_init_succeeds_then_returns_initialised_instance() -> None:
    """The instance is built through ``__new__`` plus ``__init__`` with the arguments."""
    built = fontui._construct(Probe, 1, "two")
    assert isinstance(built, Probe), "the requested class is instantiated"
    assert built.args == (1, "two"), "constructor arguments are passed through"


def test_construct_when_init_fails_after_widget_then_closes_and_reraises() -> None:
    """A half-built owner with a ``widget`` is closed before the error propagates."""
    closed: list[bool] = []

    class Half:
        def __init__(self) -> None:
            self.widget = object()
            raise RuntimeError("boom")

        def close(self) -> None:
            closed.append(True)

    with pytest.raises(RuntimeError, match="boom"):
        fontui._construct(Half)
    assert closed == [True], "close() must run exactly once for a half-built widget"


def test_construct_when_init_fails_before_widget_then_reraises_without_close() -> None:
    """With no widget yet there is nothing to close."""

    class Early:
        def __init__(self) -> None:
            raise ValueError("early")

        def close(self) -> None:
            raise AssertionError("close must not run without a widget")

    with pytest.raises(ValueError, match="early"):
        fontui._construct(Early)


def test_construct_when_interrupted_then_cleans_up_base_exceptions_too() -> None:
    """KeyboardInterrupt is a BaseException; the widget is still closed."""
    closed: list[bool] = []

    class Interrupted:
        def __init__(self) -> None:
            self.widget = object()
            raise KeyboardInterrupt

        def close(self) -> None:
            closed.append(True)

    with pytest.raises(KeyboardInterrupt):
        fontui._construct(Interrupted)
    assert closed == [True], "close() runs once even for a BaseException"


# ------------------------------------------------------------ factories


def test_glyph_browser_when_called_then_builds_native_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """The browser receives font, parent, activation callback and the multiple flag."""
    _fake_module(monkeypatch, "native", Browser=Probe)
    callback = lambda *a: None
    built = fontui.glyph_browser("font", "parent", callback, True)
    assert built.args == ("font", "parent", callback, True), "all four arguments reach the browser"
    assert fontui.glyph_browser("f").args == ("f", None, None, False), "defaults must be None/None/False"


def test_font_browser_when_called_then_builds_font_list_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """The font browser receives fonts, parent and callback; fonts default to empty."""
    _fake_module(monkeypatch, "fonts", FontBrowser=Probe)
    callback = lambda *a: None
    assert fontui.font_browser(["a"], "p", callback).args == (
        ["a"],
        "p",
        callback,
    ), "fonts, parent and callback reach the browser"
    assert fontui.font_browser().args == ((), None, None), "defaults are no fonts, no parent, no callback"


def test_glyph_preview_when_called_then_builds_native_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    """The preview receives font, glyph name and parent."""
    _fake_module(monkeypatch, "native", Preview=Probe)
    assert fontui.glyph_preview("font", "A", "parent").args == (
        "font",
        "A",
        "parent",
    ), "font, glyph name and parent reach the preview"
    assert fontui.glyph_preview("font").args == ("font", None, None), "glyph and parent default to None"


def test_features_editor_when_called_then_builds_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The editor receives font, parent and the apply callback."""
    _fake_module(monkeypatch, "features", FeaturesEditor=Probe)
    callback = lambda font, text: None
    assert fontui.features_editor("font", "parent", callback).args == (
        "font",
        "parent",
        callback,
    ), "font, parent and callback reach the editor"
    assert fontui.features_editor("font").args == ("font", None, None), "parent and callback default to None"


def test_designspace_panel_when_called_then_builds_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    """The panel receives the designspace, parent and location callback."""
    _fake_module(monkeypatch, "designspace", DesignspacePanel=Probe)
    callback = lambda *a: None
    assert fontui.designspace_panel("ds", "parent", callback).args == (
        "ds",
        "parent",
        callback,
    ), "designspace, parent and callback reach the panel"
    assert fontui.designspace_panel("ds").args == ("ds", None, None), "parent and callback default to None"


def test_factory_when_constructor_fails_then_native_widget_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factories route through ``_construct``, so a failed build leaks no widget."""
    closed: list[bool] = []

    class Failing:
        def __init__(self, *args: Any) -> None:
            self.widget = object()
            raise RuntimeError("no font")

        def close(self) -> None:
            closed.append(True)

    _fake_module(monkeypatch, "features", FeaturesEditor=Failing)
    with pytest.raises(RuntimeError, match="no font"):
        fontui.features_editor("font")
    assert closed == [True], "the half-built widget is closed by the factory"


# Restored editors use ordinary module resolution and lazy factories.

@pytest.mark.parametrize("name", ["fontinfo", "groups", "groups_view", "kerning", "kerning_view", "transform", "transform_view", "batch", "batch_worker", "sequence"])
def test_restored_module_when_resolved_then_it_has_a_real_source(name):
    assert importlib.util.find_spec(f"fontlabapp.fontui.{name}") is not None


@pytest.mark.parametrize("name", ["font_info_editor", "groups_editor", "kerning_editor", "transform_editor", "batch_panel", "glyph_sequence"])
def test_restored_factory_when_read_then_it_is_exported(name):
    assert name in fontui.__all__
    assert callable(getattr(fontui, name))


# ------------------------------------------------------- Fontport-bound editors


def test_load_when_fontport_missing_then_import_error_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing ``fontlab_fontport`` becomes a clear ImportError."""
    for name in [n for n in sys.modules if n.startswith("fontlab_fontport")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.groups", raising=False)
    monkeypatch.setitem(sys.modules, "fontlab_fontport", None)  # import raises
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock(), QtCore=Mock()))
    with pytest.raises(ImportError, match=r"fontlab-fontlabapp\[fontport\]") as info:
        fontui._load("groups")
    assert isinstance(info.value.__cause__, ModuleNotFoundError), "keeps the cause"


def test_load_when_other_module_missing_then_original_error_propagates() -> None:
    """Only Fontport gets the hint; any other missing module stays as it was."""
    with pytest.raises(ModuleNotFoundError, match="no_such_module"):
        fontui._load("no_such_module")


def test_fontui_when_imported_then_has_no_tombstone_finder():
    assert not hasattr(fontui, "MOVED")
    assert not any(getattr(f, "_fontlabapp_fontui_tombstone", False) for f in sys.meta_path)


def test_getattr_when_unknown_name_then_attribute_error():
    with pytest.raises(AttributeError, match="nothing_here"):
        fontui.nothing_here


@pytest.mark.parametrize("name", [
    "glyph_browser", "font_browser", "glyph_preview", "features_editor",
    "designspace_panel", "BrowserState", "FontListState", "outline", "viewport",
])
def test_fontui_when_general_name_read_then_it_stays_available(name):
    assert name in fontui.__all__, name
    assert getattr(fontui, name) is not None, name


def test_follow_history_when_called_then_lazy_public_factory_forwards_owned_callback(monkeypatch):
    follow = Mock(return_value=2)
    _fake_module(monkeypatch, "lifecycle", follow_history=follow)
    owner, callback = object(), lambda: None
    assert "follow_history" in fontui.__all__
    assert fontui.follow_history(owner, callback) == 2
    follow.assert_called_once_with(owner, callback)
