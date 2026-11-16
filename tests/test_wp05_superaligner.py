# this_file: tests/test_wp05_superaligner.py
"""Exact cyclic geometry matching is retained by the new Superaligner route."""
import importlib
import sys

import pytest
from _studio_qt import studio_qt  # noqa: F401


def test_superaligner_when_reversed_shifted_or_ambiguous_then_original_contract(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.superaligner', raising=False)
    module = importlib.import_module('fontlabapp.fontui.superaligner')
    points = [(0, 0, True), (80, 10, True), (100, 90, True), (5, 120, True)]
    assert module.alignment(points, points[:1] + points[:0:-1]) == (True, 0)
    assert module.alignment(points, points[2:] + points[:2]) == (False, 2)
    with pytest.raises(ValueError, match='ambiguous'):
        module.alignment([(0, 0, True)] * 3, [(0, 0, True)] * 3)
    with pytest.raises(ValueError, match='counts'):
        module.alignment(points, points[:1])
