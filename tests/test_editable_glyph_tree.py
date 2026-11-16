# this_file: tests/test_editable_glyph_tree.py
"""Lazy public entrypoints route both complete policies through the owned registry."""

import importlib
import sys
from types import SimpleNamespace

import pytest

import fontlabapp.glyphs.tree.editable.model as api


@pytest.mark.parametrize("official", [False, True])
def test_public_show_routes_complete_capture_and_distinct_registry(
    monkeypatch, official
):
    import fontlabapp.glyphs.tree.model as reader

    scripting = importlib.import_module("fontlabapp.core.scripting")

    calls = []
    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.glyphs.tree.editable.ui",
        SimpleNamespace(
            EditableGlyphTreeDialog=lambda parent, capture, **kw: (
                calls.append((parent, capture, kw)) or "owned"
            ),
        ),
    )
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda factory, key: (factory("parent"), key)
    )
    result = (api.show_tree if official else api.show_outline)()
    assert result == (
        "owned",
        "editable_glyph_tree" if official else "editable_glyph_outline",
    )
    assert calls == [("parent", reader.capture, {"official": official})]


def test_background_thread_is_refused_before_native_import(monkeypatch):
    monkeypatch.setattr(api, "current_thread", lambda: object())
    with pytest.raises(RuntimeError, match="main UI thread"):
        api.show_tree()
