# this_file: tests/test_top_level_getattr.py
"""In-process tests for fontlabapp.__getattr__ and _native (lazy top-level lookup)."""

from types import SimpleNamespace

import pytest

import fontlabapp


@pytest.fixture
def fake_import(monkeypatch):
    """Replace fontlabapp.import_module with a table of fakes; drop cached names afterwards."""
    before = set(vars(fontlabapp))
    table: dict[str, object] = {}

    def fake(name):
        value = table.get(name)
        if isinstance(value, BaseException):
            raise value
        if value is None:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return value

    monkeypatch.setattr(fontlabapp, "import_module", fake)
    yield table
    for key in set(vars(fontlabapp)) - before:
        delattr(fontlabapp, key)


def test_getattr_when_private_name_then_attribute_error(fake_import):
    with pytest.raises(AttributeError):
        fontlabapp.__getattr__("_hidden")


def test_getattr_when_fontlab_then_controls_class_is_cached(fake_import):
    marker = object()
    fake_import["fontlabapp.core.controls"] = SimpleNamespace(FontLab=marker)
    assert fontlabapp.__getattr__("FontLab") is marker
    assert vars(fontlabapp)["FontLab"] is marker, "resolved names must be cached in module globals"


def test_getattr_when_app_then_application_is_instantiated(fake_import):
    class Application:
        pass

    fake_import["fontlabapp.core.application"] = SimpleNamespace(Application=Application)
    assert isinstance(fontlabapp.__getattr__("app"), Application)


def test_getattr_when_host_name_then_not_cached(fake_import):
    marker = object()
    fake_import["fontlabapp.core.host"] = SimpleNamespace(actions=marker)
    assert fontlabapp.__getattr__("actions") is marker
    assert "actions" not in vars(fontlabapp), "host lookups stay live, never cached"


def test_getattr_when_native_present_then_module_and_qt_member_returned(fake_import):
    pyqt = SimpleNamespace(QtGui="gui")
    fake_import["PythonQt"] = pyqt
    assert fontlabapp.__getattr__("PythonQt") is pyqt
    assert fontlabapp.__getattr__("QtGui") == "gui"


def test_getattr_when_explicit_native_absent_then_runtime_error(fake_import):
    with pytest.raises(RuntimeError, match="fontgate requires the native API"):
        fontlabapp.__getattr__("fontgate")


def test_native_when_inner_dependency_missing_then_original_error_propagates(fake_import):
    fake_import["FL"] = ModuleNotFoundError("No module named 'inner'", name="inner")
    with pytest.raises(ModuleNotFoundError, match="inner"):
        fontlabapp._native("FL")


def test_getattr_when_fallback_found_in_fl_then_value_returned(fake_import):
    fake_import["FL"] = SimpleNamespace(fl="flobj")
    assert fontlabapp.__getattr__("fl") == "flobj"


def test_getattr_when_fallback_found_in_fontlab_first_then_fontlab_wins(fake_import):
    fake_import["fontlab"] = SimpleNamespace(flWorkspace="ws")
    fake_import["FL"] = SimpleNamespace(flWorkspace="other")
    assert fontlabapp.__getattr__("flWorkspace") == "ws"


def test_getattr_when_fallback_absent_everywhere_then_attribute_error(fake_import):
    fake_import["fontlab"] = SimpleNamespace()
    with pytest.raises(AttributeError, match="no_such_name"):
        fontlabapp.__getattr__("no_such_name")


def test_getattr_when_fallback_inner_import_breaks_then_error_propagates(fake_import):
    fake_import["fontlab"] = ModuleNotFoundError("No module named 'fontgate'", name="fontgate")
    with pytest.raises(ModuleNotFoundError, match="fontgate"):
        fontlabapp.__getattr__("anything")
