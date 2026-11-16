# this_file: tests/test_names_edit.py
"""Shared Names-editor snapshot, refusals and commit (issue 122, T14b).

FontLab doubles log every history call. The tests prove the whole-font scan,
the identity fences, the per-operation refusals and the one-Undo call shape,
not native FontLab behaviour.
"""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.glyphs.names.model as ne

STAMP = "UTC"


class Shape:
    def __init__(self, base=None):
        self.isComponent = base is not None
        self.shapeData = NS(componentGlyph=base)


class Layer:
    def __init__(self, log, name, *, auto=False, bases=()):
        self.log, self.name, self.autoLayer = log, name, auto
        self.shapes = [Shape(b) for b in bases] or [Shape()]

    def checkInitHistoryState(self, flag):
        self.log.append(("init", self.name))


class Glyph:
    isNull = False

    def __init__(self, log, name, fg_id, layers):
        self.log, self.name, self.fgGlyphId, self.layers = log, name, fg_id, layers

    def checkInitHistoryState(self, flag):
        self.log.append(("init", self.name))

    @property
    def lastModified(self):
        return None

    @lastModified.setter
    def lastModified(self, value):
        self.log.append(("stamp", self.name))

    @property
    def fgGlyph(self):
        raise AssertionError("never read flGlyph.fgGlyph (note mirror loss)")


class Native:
    """The ``fontlab`` double: one font with font-owned records."""

    def __init__(self, glyphs, *, package_id=3, pending=()):
        self.log = glyphs[0].log if glyphs else []
        self.by_id = {g.fgGlyphId: g for g in glyphs}
        self.records = [NS(id=g.fgGlyphId, name=g.name) for g in glyphs]
        self.package = NS(id=package_id, isNull=False, findFgId=self.by_id.get)
        self.pending = list(pending)
        self.flWorkspace = NS(instance=lambda: NS(currentPackage=self.package))
        self.flGlyph = NS(updatedFgGlyphs=lambda: tuple(self.pending))

    def CurrentFont(self):
        return NS(glyphs=self.records)

    def flItems(self):
        return self

    def notifyChangesApplied(self, title, items):
        self.log.append(("notify", title, [i.name for i in items]))


def font(log=None):
    log = [] if log is None else log
    return Native(
        [
            Glyph(log, "A", 1, [Layer(log, "A/Regular"), Layer(log, "A/Bold")]),
            Glyph(log, "Aacute", 2, [Layer(log, "Aacute/Regular", auto=True, bases=("A", "acute"))]),
            Glyph(log, "acute", 3, [Layer(log, "acute/Regular")]),
            Glyph(log, "B", 4, [Layer(log, "B/Regular")]),
            Glyph(log, "empty", 5, []),
        ]
    )


def test_scan_when_font_open_then_entries_and_auto_facts():
    facts = ne.scan(font())
    assert list(facts.entries) == ["A", "Aacute", "acute", "B", "empty"]
    assert facts.package_id == 3
    assert facts.autos.autos == frozenset({"Aacute"})
    assert facts.autos.dependants("A") == ("Aacute",)
    entry = facts.entries["A"]
    assert entry.name == "A" and entry.record.id == 1 and entry.glyph.fgGlyphId == 1


def test_scan_when_no_font_then_value_error():
    native = font()
    native.package = None
    with pytest.raises(ValueError, match="Open a font first"):
        ne.scan(native)


def test_scan_when_identity_mapping_differs_then_value_error():
    native = font()
    native.by_id[4].name = "renamed"
    with pytest.raises(ValueError, match="mapping is inconsistent"):
        ne.scan(native)


def test_scan_when_no_native_given_then_fontlab_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlab", font())
    assert "A" in ne.scan().entries


@pytest.mark.parametrize(
    ("name", "operation", "reason"),
    [
        ("missing", "rename", "not in font"),
        ("empty", "metadata", "has no layers"),
        ("Aacute", "metadata", "has auto layers"),
        ("A", "rename", "base of auto Aacute"),
        ("A", "unicode", "base of auto Aacute"),
        ("A", "metadata", ""),
        ("B", "rename", ""),
    ],
)
def test_refusal_when_operation_then_policy_reason(name, operation, reason):
    assert ne.refusal(ne.scan(font()), name, operation) == reason


def test_editable_when_names_mixed_then_split_in_order():
    ok, refused = ne.editable(ne.scan(font()), ["B", "A", "Aacute", "acute"], "rename")
    assert ok == ["B"]
    assert refused == {"A": "base of auto Aacute", "Aacute": "has auto layers", "acute": "base of auto Aacute"}


def test_fresh_facts_when_same_font_and_settled_then_new_scan():
    native = font()
    assert ne.fresh_facts(3, native=native).package_id == 3


def test_fresh_facts_when_font_switched_then_value_error():
    with pytest.raises(ValueError, match="no longer current"):
        ne.fresh_facts(9, native=font())


def test_fresh_facts_when_updates_pending_then_disclosed_and_queue_kept():
    native = font()
    native.pending = [2]
    facts = ne.fresh_facts(3, native=native)
    assert not hasattr(facts, "pending_updates"), "Only commit captures the pre-write queue"
    assert native.pending == [2]


def test_commit_when_entries_then_all_layers_inited_one_notify_layers_then_glyphs():
    native = font()
    facts = ne.scan(native)
    log = native.log
    entries = [facts.entries["B"], facts.entries["A"]]
    ne.commit("Notes", entries, lambda: log.append(("mutate",)), operation="metadata", facts=facts, native=native, stamp=STAMP)
    assert log == [
        ("init", "B/Regular"),
        ("init", "A/Regular"),
        ("init", "A/Bold"),
        ("init", "B"),
        ("init", "A"),
        ("mutate",),
        ("stamp", "B"),
        ("stamp", "A"),
        ("notify", "Notes", ["B/Regular", "A/Regular", "A/Bold", "B", "A"]),
        ("stamp", "B"),
        ("stamp", "A"),
    ]


def test_commit_when_rename_base_of_auto_then_refused_before_history():
    native = font()
    facts = ne.scan(native)
    with pytest.raises(ValueError, match="A: base of auto Aacute"):
        ne.commit("Rename", [facts.entries["A"]], lambda: None, operation="rename", facts=facts, native=native, stamp=STAMP)
    assert native.log == []


def test_commit_when_auto_owner_then_refused_even_for_metadata():
    native = font()
    facts = ne.scan(native)
    with pytest.raises(ValueError, match="has auto layers|auto layer"):
        ne.commit("Tags", [facts.entries["Aacute"]], lambda: None, operation="metadata", facts=facts, native=native, stamp=STAMP)
    assert native.log == []


def test_commit_when_mutate_fails_then_partial_write_error_with_undo_text():
    native = font()
    facts = ne.scan(native)

    def mutate():
        raise OSError("name setter refused")

    with pytest.raises(history.PartialWriteError, match="Native changes may remain; use Edit > Undo"):
        ne.commit("Rename", [facts.entries["B"]], mutate, operation="rename", facts=facts, native=native, stamp=STAMP)
    assert ("notify", "Rename", ["B/Regular", "B"]) in native.log


def test_commit_when_unicode_window_given_then_guards_run(monkeypatch):
    import fontlabapp.core.edit_guards as guards

    native = font()
    facts = ne.scan(native)
    seen = []
    monkeypatch.setattr(guards, "require_selection_window", seen.append)
    monkeypatch.setattr(guards, "require_no_editors", lambda **_: seen.append("editors"))
    ne.commit("Unicode", [facts.entries["B"]], lambda: None, operation="unicode", facts=facts, native=native, stamp=STAMP, window=3)
    assert seen == [3, "editors"]


def test_commit_when_read_back_given_then_mismatches_returned():
    native = font()
    facts = ne.scan(native)
    result = ne.commit(
        "Notes", [facts.entries["B"]], lambda: None, operation="metadata", facts=facts,
        native=native, stamp=STAMP, read_back=lambda: ["B: note not stored"],
    )
    assert result.mismatches == ("B: note not stored",)


def test_names_edit_when_cold_imported_then_only_stdlib():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.glyphs.names.model
assert 'fontlabapp.core.scripting' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
