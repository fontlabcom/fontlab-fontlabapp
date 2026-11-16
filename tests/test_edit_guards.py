# this_file: tests/test_edit_guards.py
"""Public edit guards and the public glyph-catalogue capture (issue 122, T14b).

The guards delegate to the reviewed private implementations. These tests prove
the delegation, the refusal texts and the lazy imports. They do not prove
native FontLab behaviour.
"""

import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.core.edit_guards as guards
import fontlabapp.glyphs.catalog.model as catalog


def test_require_selection_window_when_called_then_private_guard_gets_package_id(monkeypatch):
    seen = []
    scripting = importlib.import_module("fontlabapp.core.scripting")
    monkeypatch.setattr(scripting, "_require_selection_window", seen.append)
    guards.require_selection_window(41)
    assert seen == [41], seen


def test_require_selection_window_when_no_font_window_then_value_error(monkeypatch):
    scripting = importlib.import_module("fontlabapp.core.scripting")

    def refuse(package_id):
        raise ValueError("Activate the Font window before selecting glyphs.")

    monkeypatch.setattr(scripting, "_require_selection_window", refuse)
    with pytest.raises(ValueError, match="Activate the Font window"):
        guards.require_selection_window(41)


def test_require_no_editors_when_defaults_then_pythonqt_and_two_second_deadline(monkeypatch):
    capture = importlib.import_module("fontlabapp.glyphs.unicode.duplicates.capture")
    seen = []
    qt = NS(QtGui=NS())
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setattr(capture, "require_no_editors", lambda q, d, action: seen.append((q, d, action)))
    monkeypatch.setattr(guards, "monotonic", lambda: 100.0)
    guards.require_no_editors()
    assert seen == [(qt, 102.0, "removing Unicode assignments")], seen


def test_require_no_editors_when_qt_and_deadline_given_then_passed_unchanged(monkeypatch):
    capture = importlib.import_module("fontlabapp.glyphs.unicode.duplicates.capture")
    seen = []
    monkeypatch.setattr(capture, "require_no_editors", lambda q, d, action: seen.append((q, d, action)))
    qt = object()
    guards.require_no_editors(qt=qt, deadline=5.5)
    assert seen == [(qt, 5.5, "removing Unicode assignments")], seen


def test_require_no_editors_when_action_given_then_forwarded_to_implementation(monkeypatch):
    capture = importlib.import_module("fontlabapp.glyphs.unicode.duplicates.capture")
    seen = []
    monkeypatch.setattr(capture, "require_no_editors", lambda q, d, action: seen.append(action))
    guards.require_no_editors(qt=object(), deadline=1.0, action="writing to the font")
    assert seen == ["writing to the font"], seen


def test_require_no_editors_when_glyph_editor_open_then_value_error():
    class Widget:
        def __init__(self, editor):
            self.editor = editor

        def inherits(self, name):
            return self.editor and name == "GlyphWindow"

    qt = NS(QtGui=NS(QApplication=NS(allWidgets=lambda: [Widget(False), Widget(True)])))
    with pytest.raises(ValueError, match="Close all Glyph editors"):
        guards.require_no_editors(qt=qt, deadline=float("inf"))


def test_require_settled_when_updates_pending_then_value_error_and_queue_untouched():
    queue = [7, 8]
    native = NS(flGlyph=NS(updatedFgGlyphs=lambda: tuple(queue)))
    with pytest.raises(ValueError, match="glyph updates are pending"):
        guards.require_settled(native)
    assert queue == [7, 8], "the guard never clears the native queue"


def test_require_settled_when_queue_empty_then_returns_none():
    assert guards.require_settled(NS(flGlyph=NS(updatedFgGlyphs=tuple))) is None


def test_require_settled_when_no_native_given_then_fontlab_module_read(monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlab", NS(flGlyph=NS(updatedFgGlyphs=lambda: (1,))))
    with pytest.raises(ValueError, match="pending"):
        guards.require_settled()


def test_capture_when_called_then_private_capture_runs_with_deadline(monkeypatch):
    native = importlib.import_module("fontlabapp.glyphs.catalog.native")
    seen = []
    monkeypatch.setattr(native, "capture", lambda *, deadline=None: seen.append(deadline) or "T")
    assert catalog.capture() == "T"
    assert catalog.capture(deadline=9.0) == "T"
    assert seen == [None, 9.0], seen


def test_capture_when_no_font_then_private_refusal_text(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "fontlab",
        NS(flWorkspace=NS(instance=lambda: NS(currentPackage=None))),
    )
    with pytest.raises(ValueError, match="Open a font"):
        catalog.capture(deadline=float("inf"))


@pytest.mark.parametrize("module", ["fontlabapp.core.edit_guards", "fontlabapp.glyphs.catalog.model"])
def test_module_when_cold_imported_then_only_stdlib_and_no_private_capture(module):
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = f"""
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import {module}
lazy = {{'fontlabapp.glyphs.catalog.native', 'fontlabapp.core.scripting',
        'fontlabapp.glyphs.unicode.duplicates.capture', 'fontlabapp.qt.tables.filter.model'}}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_pending_updates_when_queued_then_one_read_and_no_clear():
    queue, reads = [4, 9], []
    def read():
        reads.append(True)
        return queue
    assert guards.pending_updates(NS(flGlyph=NS(updatedFgGlyphs=read))) == (4, 9)
    assert reads == [True] and queue == [4, 9]
    assert guards.pending_note(()) == ""
    note = guards.pending_note((4, 9))
    assert "2 glyphs" in note and "modification dates" in note and "8537" in note


def test_append_note_uses_stored_note_once_and_has_no_empty_separator(capsys):
    result = {"pending_updates": (4,), "pending_note": guards.pending_note((4,))}
    shown = guards.append_note("Written", result)
    assert shown == "Written · " + result["pending_note"]
    assert guards.append_note(shown, result) == shown
    assert guards.append_note("Written", {"pending_note": ""}) == "Written"
    target = {}
    guards.disclose(result, target)
    assert target == result and capsys.readouterr().out == ""
    guards.disclose(result)
    assert capsys.readouterr().out.strip() == "Queued glyph ids: (4,) · " + result["pending_note"]
