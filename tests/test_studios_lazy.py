# this_file: tests/test_studios_lazy.py
"""``fontlabapp.studios``: TabSpec registry and lazy children."""

import sys
import types

import pytest


def test_studios_when_imported_then_no_child_loads():
    import fontlabapp.studios as studios

    children = [name for name in sys.modules if name.startswith("fontlabapp.studios.")]
    assert children == [], children
    assert studios.__all__ == ["TabSpec", "register", "tabs"]


def test_registry_when_specs_registered_then_kept_in_order():
    from fontlabapp import studios

    one = studios.register("Test Studio", studios.TabSpec("One", lambda shell: None))
    two = studios.register("Test Studio", studios.TabSpec("Two", lambda shell: None))
    assert studios.tabs("Test Studio") == [one, two]
    assert studios.tabs("Missing") == []
    studios._REGISTRY.pop("Test Studio")


def test_getattr_when_child_exists_then_loads_on_first_read(monkeypatch):
    from fontlabapp import studios

    child = types.ModuleType("fontlabapp.studios.demo")
    monkeypatch.setitem(sys.modules, "fontlabapp.studios.demo", child)
    assert studios.demo is child


def test_getattr_when_missing_or_private_then_attribute_error():
    from fontlabapp import studios

    with pytest.raises(AttributeError, match="no attribute 'nothing_here'"):
        studios.nothing_here  # noqa: B018
    with pytest.raises(AttributeError):
        studios._hidden  # noqa: B018


def test_getattr_when_child_import_breaks_then_error_propagates(monkeypatch):
    from fontlabapp import studios

    def broken(name):
        raise ModuleNotFoundError("No module named 'other'", name="other")

    monkeypatch.setattr(studios.importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError):
        studios.broken  # noqa: B018
