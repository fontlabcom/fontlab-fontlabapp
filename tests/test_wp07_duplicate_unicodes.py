# this_file: tests/test_wp07_duplicate_unicodes.py
# SPDX-License-Identifier: Apache-2.0
"""WP07 Duplicate Unicodes entry point delegates lazily to the shared editor."""

import sys
import types

from fontlabapp.glyphs.identity_tools.glyph_identity import duplicate_unicodes


def test_main_when_called_then_shows_shared_editor_and_returns_result(monkeypatch) -> None:
    calls = []
    model = types.ModuleType("fontlabapp.glyphs.unicode.duplicates.model")
    model.show = lambda: calls.append("show") or "window"
    monkeypatch.setitem(sys.modules, model.__name__, model)
    assert duplicate_unicodes.main() == "window"
    assert calls == ["show"]
