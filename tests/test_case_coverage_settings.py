# this_file: tests/test_case_coverage_settings.py
import pytest
from fontlabapp.glyphs.case_coverage.model import Options
from fontlabapp.glyphs.case_coverage.settings import load, save


class Memory:
    def __init__(self):
        self.data = {}
        self.writable = True
        self.error = 0

    def value(self, key, default):
        return self.data.get(key, default)

    def setValue(self, key, value):
        self.data[key] = value

    def sync(self):
        pass

    def status(self):
        return self.error

    def isWritable(self):
        return self.writable


def test_original_defaults_roundtrip_boolean_strings_and_unrelated_keys():
    store = Memory()
    assert load(store) == Options()
    store.data["owner"] = "untouched"
    save(store, Options(True, False, False, True))
    assert load(store) == Options(True, False, False, True)
    assert store.data["owner"] == "untouched"
    store.data.update(
        excludeMathSymbols="false", allFonts="true", reuseTab=1, showMacroWindow=0
    )
    assert load(store) == Options(False, True, True, False)


def test_corrupt_and_readonly_stores_are_not_silent():
    store = Memory()
    store.data["allFonts"] = "maybe"
    with pytest.raises(ValueError):
        load(store)
    store.data.clear()
    store.error = 1
    with pytest.raises(OSError):
        load(store)
    store.writable = False
    with pytest.raises(OSError):
        save(store, Options())
    with pytest.raises(ValueError):
        Options(allFonts=1)
