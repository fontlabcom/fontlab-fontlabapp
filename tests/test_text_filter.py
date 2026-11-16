# this_file: tests/test_text_filter.py
"""Owned text controls; never import or execute a reference script."""

import re

import pytest

import fontlabapp.proof.text_filter.settings as prefs
from fontlabapp.proof.text_filter.model import (
    DEFAULT_CHARACTERS,
    SavedText,
    filter_text,
)


@pytest.mark.parametrize(
    ("text", "characters", "expected"),
    [
        ("a1b2C!", "a-z", "ab"),
        ("a\nb 1", r"\s", "\n "),
        ("A🙂éZ", "🙂é", "🙂é"),
        ("foo /name", "a-z /", "foo /name"),
        ("", "a-z", ""),
        ("Aa0 Zz., space!", DEFAULT_CHARACTERS, "Aa Zz., space"),
        ("abcdef", "^a", "a"),
        ("a]b", "]", "]"),
    ],
)
def test_filter_preserves_source_character_class_semantics(text, characters, expected):
    assert filter_text(text, characters) == expected


@pytest.mark.parametrize("characters", ["", "z-a", "\\"])
def test_invalid_character_class_has_no_partial_result(characters):
    with pytest.raises(re.error):
        filter_text("unchanged", characters)


@pytest.mark.parametrize(
    ("text", "characters"), [(None, "a"), ("a", None), (False, "a")]
)
def test_filter_rejects_nontext_values(text, characters):
    with pytest.raises(TypeError):
        filter_text(text, characters)


class Settings:
    NoError = 0

    def __init__(self):
        self.values, self.error, self.writable = {}, 0, True

    def value(self, key, default):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        pass

    def status(self):
        return self.error

    def isWritable(self):
        return self.writable


def test_saved_defaults_roundtrip_and_reset_preserve_input_and_other_keys():
    settings = Settings()
    assert prefs.load(settings) == SavedText()
    values = SavedText("source", "result", "a-z")
    prefs.save(settings, values)
    settings.values["unrelated"] = "keep"
    assert prefs.load(settings) == values
    prefs.reset(settings)
    assert prefs.load(settings) == SavedText("source")
    assert settings.values == {"input": "source", "unrelated": "keep"}


def test_bad_saved_value_and_sync_failure_are_explicit():
    settings = Settings()
    settings.values["input"] = 42
    with pytest.raises(ValueError):
        prefs.load(settings)
    settings.values.clear()
    settings.error = 1
    with pytest.raises(OSError):
        prefs.load(settings)
    with pytest.raises(OSError):
        prefs.save(settings, SavedText())
    with pytest.raises(OSError):
        prefs.reset(settings)
    settings.error = 0
    settings.writable = False
    with pytest.raises(OSError):
        prefs.save(settings, SavedText())
    with pytest.raises(OSError):
        prefs.reset(settings)
    settings.writable = True
    with pytest.raises(ValueError):
        prefs.save(settings, SavedText(None))


def test_public_show_is_lazy_and_uses_the_owned_registry_key(monkeypatch):
    import sys
    from types import SimpleNamespace

    from fontlabapp.core import scripting
    from fontlabapp.proof.text_filter.model import show

    marker = object()
    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.proof.text_filter.ui",
        SimpleNamespace(TextFilterDialog=marker),
    )
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda factory, key: (factory, key)
    )
    assert show() == (marker, "text_filter")
