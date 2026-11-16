"""Oracle for the ``isolated_studio_modules`` fixture in ``tests/_studio_qt.py``."""

import importlib
import sys

import pytest

from tests._studio_qt import isolated_studio_modules  # noqa: F401  (fixture)

PARENT = "fontlabapp.studios"
LEAF = "wp03_isolation_probe"
NAME = f"{PARENT}.{LEAF}"


def test_isolated_studio_modules_when_test_ends_then_previous_modules_and_attrs_restored():
    parent = importlib.import_module(PARENT)
    sentinel = type(sys)(NAME)
    sys.modules[NAME] = sentinel
    setattr(parent, LEAF, sentinel)
    gen = isolated_studio_modules.__wrapped__() if hasattr(isolated_studio_modules, "__wrapped__") else None
    assert gen is not None, "fixture function not reachable"
    try:
        next(gen)
        assert NAME not in sys.modules, "cached studio module must be removed for the test"
        fresh = type(sys)(f"{PARENT}.wp03_fresh")
        sys.modules[fresh.__name__] = fresh
        setattr(parent, "wp03_fresh", fresh)
        with pytest.raises(StopIteration):
            next(gen)
        assert sys.modules[NAME] is sentinel
        assert getattr(parent, LEAF) is sentinel
        assert fresh.__name__ not in sys.modules, "modules imported by the test must be dropped"
        assert not hasattr(parent, "wp03_fresh"), "parent attribute of a dropped module must go"
    finally:
        sys.modules.pop(NAME, None)
        sys.modules.pop(f"{PARENT}.wp03_fresh", None)
        for leaf in (LEAF, "wp03_fresh"):
            if hasattr(parent, leaf):
                delattr(parent, leaf)
