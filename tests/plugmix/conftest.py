# this_file: tests/plugmix/conftest.py
"""Python-only snapshot fixtures for every built-in reporter."""

import pytest

from fontlabapp.plugins import snapshot
from fontlabapp.plugins.snapshot import Anchor, Contour, GlyphSnapshot, Metrics, Node


@pytest.fixture(autouse=True)
def _fresh_snapshot_cache():
    """Isolate the process-wide snapshot cache between tests."""
    snapshot._cache.clear()
    snapshot._reported.clear()
    yield
    snapshot._cache.clear()
    snapshot._reported.clear()


@pytest.fixture
def glyph() -> GlyphSnapshot:
    """A rectangle with two selected on-curves and an external handle."""
    return GlyphSnapshot(
        (
            Contour(
                (
                    Node(0, 0, True, True),
                    Node(30, 120, False, False),
                    Node(100, 0, True, False),
                    Node(100, 100, True, True),
                    Node(0, 100, True, False),
                )
            ),
        ),
        (
            Anchor("top", 50, 110),
            Anchor("top_2", 50.5, 110),
            Anchor("top_3", 50.8, 110),
            Anchor("far", 100, 110),
        ),
        500,
        Metrics(800, -200, 500, 700, 10, 1000),
    )

# Concrete regression fixtures now live in the explicitly selected reference pack.
import importlib
import json
import sys
from pathlib import Path

from fontlabapp.plugins import bundles, registry

_PACK = Path(__file__).resolve().parents[3] / "fontlab-python-plugmix"
for _row in json.loads((_PACK / "tests/bundle-map.json").read_text()):
    if "original" not in _row:
        continue
    _cls = bundles.load_bundle(_PACK / _row["bundle"])
    _name = "fontlabapp.plugins." + _row["original"].removesuffix(".py").replace("/", ".")
    _module = sys.modules[_cls.__module__]
    sys.modules[_name] = _module
    _parent, _, _child = _name.rpartition(".")
    setattr(importlib.import_module(_parent), _child, _module)


@pytest.fixture(autouse=True)
def _reference_extensions(monkeypatch):
    """Select reference bundles explicitly, leaving production discovery portable."""
    monkeypatch.setattr(registry, "DEFAULT_EXTENSIONS", _PACK / "Extensions")
