# this_file: tests/test_canvas_palette_literals.py
"""Canvases take their background from the shared palette helper, never a white literal."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src" / "fontlabapp" / "fontui"


@pytest.mark.parametrize("name", ["transform_view.py", "native.py"])
def test_canvas_module_when_painting_then_no_white_literal_and_uses_palette(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    assert 'QColor("white")' not in text, f"{name} paints a hard-coded white canvas"
    assert "_canvas_colors(" in text, f"{name} must take colours from _canvas_palette"
