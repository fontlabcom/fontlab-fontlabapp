# this_file: tests/test_character_map_capture.py
"""Full-font metadata capture rejects drift, partial domains and unsafe getters."""

from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from types import SimpleNamespace as NS
from unittest.mock import Mock

import fontlabapp.glyphs.character_map.capture as api
import pytest


class NativeGlyph:
    def __init__(self, ident, name, codes):
        self.id, self.name, self.unicodes = ident, name, codes

    def __getattr__(self, key):
        raise AssertionError("Unrelated native glyph getter: " + key)


@pytest.fixture
def context(monkeypatch):
    font = NS(
        glyphs=[
            NativeGlyph(1, "A", [65, 0x1F600]),
            NativeGlyph(2, "A.alt", [65]),
            NativeGlyph(3, "space", []),
        ]
    )
    state = NS(font=font, context=(7, 70, "Regular"))
    mock = Mock(side_effect=lambda deadline: (state.context, object(), state.font))
    monkeypatch.setattr(api, "_context", mock)
    state.mock = mock
    return state


def test_complete_real_shaped_metadata_without_other_native_reads(context):
    facts = api.capture()
    assert facts.context == (7, 70, "Regular")
    assert [(g.name, g.unicodes) for g in facts.rows] == [
        ("A", (65, 0x1F600)),
        ("A.alt", (65,)),
        ("space", ()),
    ]
    assert context.mock.call_count == 3
    context.font.glyphs = []
    assert api.capture().rows == ()


@pytest.mark.parametrize(
    "bad",
    [
        "id",
        "name",
        "empty",
        "duplicate-id",
        "duplicate-name",
        "negative-code",
        "large-code",
        "bool-code",
        "string-code",
    ],
)
def test_invalid_metadata_never_publishes_partial(context, bad):
    g = context.font.glyphs[1]
    if bad == "id":
        g.id = True
    elif bad == "name":
        g.name = None
    elif bad == "empty":
        g.name = ""
    elif bad == "duplicate-id":
        g.id = 1
    elif bad == "duplicate-name":
        g.name = "A"
    else:
        g.unicodes = [
            {
                "negative-code": -1,
                "large-code": 0x110000,
                "bool-code": True,
                "string-code": "65",
            }[bad]
        ]
    with pytest.raises(ValueError):
        api.capture()


def test_context_and_second_pass_drift_are_atomic(context):
    calls = 0

    def switched(deadline):
        nonlocal calls
        calls += 1
        return (
            ((7, 70, "Other") if calls == 2 else context.context),
            object(),
            context.font,
        )

    context.mock.side_effect = switched
    with pytest.raises(ValueError, match="changed"):
        api.capture()
    calls = 0

    def modified(deadline):
        nonlocal calls
        calls += 1
        if calls == 2:
            context.font.glyphs[0].unicodes = [66]
        return context.context, object(), context.font

    context.mock.side_effect = modified
    with pytest.raises(ValueError, match="changed"):
        api.capture()


def test_main_thread_deadline_and_getter_failures(context, monkeypatch):
    with ThreadPoolExecutor(1) as pool, pytest.raises(RuntimeError):
        pool.submit(api.capture).result()
    with pytest.raises(TimeoutError):
        api.read(context.font, monotonic() - 1)
    monkeypatch.setattr(api, "monotonic", Mock(side_effect=[0, 3]))
    with pytest.raises(TimeoutError):
        api.capture()
    monkeypatch.setattr(api, "monotonic", monotonic)
    context.mock.side_effect = RuntimeError("unreadable current font")
    with pytest.raises(RuntimeError, match="unreadable"):
        api.capture()
