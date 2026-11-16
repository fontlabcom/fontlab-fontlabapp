# this_file: tests/test_teaching_graph_feature_graph.py
"""Glyph Variant Feature Graph on real offscreen Qt with a fake glyph catalog."""

import sys
import types

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import with_properties
from fontlabapp.fontui.teaching_graph import feature_graph as mod

NAMES = ("A", "A.alt", "B", "B.alt", "C.alt", "A.ss01")


def test_check_names_when_valid_then_returned():
    assert mod.check_names(("A", ".notdef")) == ("A", ".notdef")


@pytest.mark.parametrize("names", [("A", "A"), ("",), ("a b",), ("a/b",), ("a\x01",), ("a\ud800",)])
def test_check_names_when_invalid_then_refused(names):
    with pytest.raises(ValueError):
        mod.check_names(names)


def test_variant_edges_when_suffix_matches_then_pairs_in_font_order():
    assert mod.variant_edges(NAMES, "alt") == (("A", "A.alt"), ("B", "B.alt"))


@pytest.mark.parametrize("suffix", ["", ".alt", "1x", "a b"])
def test_variant_edges_when_suffix_invalid_then_refused(suffix):
    with pytest.raises(ValueError, match="ASCII suffix without a dot"):
        mod.variant_edges(NAMES, suffix)


def test_variant_edges_when_only_orphans_then_refused():
    with pytest.raises(ValueError, match="No matching base/variant pairs"):
        mod.variant_edges(("C.alt",), "alt")


def test_feature_draft_when_edges_then_escaped_statements():
    assert mod.feature_draft((("A", "A.alt"), (".notdef", "x"))) == (
        "# Draft only; choose a feature and compile in FontLab.\n"
        "sub \\A by \\A.alt;\nsub \\.notdef by \\x;"
    )


def test_feature_draft_when_name_not_feature_grammar_then_refused():
    with pytest.raises(ValueError, match="cannot be emitted as an OpenType feature name"):
        mod.feature_draft((("A", "1bad"),))


@pytest.fixture
def world(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp
    import fontlabapp.core.scripting as scripting
    import fontlabapp.glyphs.catalog.model as catalog

    qt = sys.modules["PythonQt"]
    with_properties(qt.QtGui)
    state = types.SimpleNamespace(names=NAMES, shown=[])
    monkeypatch.setattr(
        catalog, "capture", lambda deadline: types.SimpleNamespace(rows=[(n,) for n in state.names])
    )
    monkeypatch.setattr(fontlabapp, "_native", lambda name: sys.modules[name], raising=False)
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: state.shown.append(key) or cls(None))
    return state


def test_capture_names_when_ready_then_names(world):
    assert mod.capture_names() == NAMES


def test_capture_names_when_deadline_passes_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 5.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Glyph-name transfer expired"):
        mod.capture_names()


@pytest.fixture
def panel(world):
    qt = sys.modules["PythonQt"]
    dialog = mod.panel_type(qt)(None)
    yield dialog
    dialog.scope.finish(destroyed=True)
    dialog.terminal.finish(destroyed=True)


def click(dialog, text):
    qt = sys.modules["PythonQt"]
    found = [b for b in dialog.findChildren(qt.QtGui.QPushButton) if b.text() == text]
    assert len(found) == 1, text
    found[0].click()


def test_refresh_when_pairs_then_scene_text_and_message(panel):
    assert panel.refresh() is True
    assert panel.message.text() == "First 2 of 2 pairs shown; full draft available. Refresh after font changes."
    assert panel.result.splitlines()[1:] == ["sub \\A by \\A.alt;", "sub \\B by \\B.alt;"]
    assert panel.output_box.toPlainText() == panel.result
    assert len(panel.canvas.items()) == 10  # 2 texts + 3 lines per pair


def test_refresh_when_over_100_pairs_then_scene_capped_draft_full(panel, world):
    world.names = tuple(n for i in range(120) for n in (f"g{i}", f"g{i}.alt"))
    assert panel.refresh() is True
    assert panel.message.text().startswith("First 100 of 120 pairs shown")
    assert panel.result.count("sub ") == 120
    assert len(panel.canvas.items()) == 500


def test_refresh_when_suffix_changed_then_new_pairs(panel):
    panel.suffix_entry.setText("ss01")
    assert panel.refresh() is True
    assert panel.result.endswith("sub \\A by \\A.ss01;")


def test_refresh_when_failure_then_cleared_and_message(panel):
    panel.refresh()
    panel.suffix_entry.setText("zz")
    assert panel.refresh() is False
    assert panel.message.text().startswith("No matching base/variant pairs")
    assert panel.result == "" and panel.canvas.items() == [] and panel.output_box.toPlainText() == ""


def test_refresh_when_preview_hook_present_then_called(panel):
    seen = []
    panel.lab_refresh_preview = lambda: seen.append(1)
    panel.refresh()
    assert seen == [1]


def test_refresh_when_cleanup_also_fails_then_both_reported(panel, monkeypatch):
    panel.suffix_entry.setText("zz")
    calls = []

    def clear():
        calls.append(1)
        if len(calls) > 1:
            raise RuntimeError("stuck")

    monkeypatch.setattr(panel, "clear_result", clear)
    assert panel.refresh() is False
    assert "scene cleanup: stuck" in panel.message.text()


def test_publish_when_qt_changes_text_then_refused(panel, monkeypatch):
    monkeypatch.setattr(panel.output_box, "toPlainText", lambda: "other")
    with pytest.raises(ValueError, match="Qt changed the result text"):
        panel.publish("text")
    assert panel.result == ""


def test_copy_result_when_refreshed_then_clipboard_and_message(panel):
    qt = sys.modules["PythonQt"]
    panel.refresh()
    click(panel, "Copy Result")
    assert qt.QtGui.QApplication.clipboard().text() == panel.result
    assert panel.message.text().startswith("Copied.")


def test_copy_result_when_empty_then_refused(panel):
    with pytest.raises(ValueError, match="Refresh to prepare a result"):
        panel.copy_result()


def test_button_when_action_raises_then_failure_message(panel):
    click(panel, "Copy Result")
    assert panel.message.text() == "Refresh to prepare a result before copying."


def test_release_when_registered_then_removed_only_for_self(panel):
    sys._fontlab_samples = {mod.KEY: object()}
    panel.release()
    assert mod.KEY in sys._fontlab_samples
    sys._fontlab_samples[mod.KEY] = panel
    panel.release()
    assert mod.KEY not in sys._fontlab_samples


def test_destroyed_cleanup_when_called_then_registry_released(panel):
    sys._fontlab_samples = {mod.KEY: panel}
    panel.destroyed_cleanup()
    assert mod.KEY not in sys._fontlab_samples


def test_close_when_clicked_then_released_and_cleared(panel):
    sys._fontlab_samples = {mod.KEY: panel}
    panel.show()
    panel.refresh()
    click(panel, "Close")
    assert mod.KEY not in sys._fontlab_samples and panel.result == ""


def test_close_when_lab_hook_present_then_hook_used(panel):
    seen = []
    panel.lab_close = lambda: seen.append(1)
    click(panel, "Close")
    assert seen == [1]


def _event():
    event = types.SimpleNamespace(ignored=False, accepted=False)
    event.ignore = lambda: setattr(event, "ignored", True)
    event.accept = lambda: setattr(event, "accepted", True)
    return event


def test_close_event_when_scope_refuses_then_ignored(panel, monkeypatch):
    monkeypatch.setattr(panel.scope, "finish", lambda **k: False)
    event = _event()
    panel.closeEvent(event)
    assert event.ignored and not event.accepted


def test_close_event_when_terminal_refuses_then_ignored(panel, monkeypatch):
    monkeypatch.setattr(panel.terminal, "finish", lambda **k: False)
    event = _event()
    panel.closeEvent(event)
    assert event.ignored and not event.accepted


def test_close_event_when_cleanup_raises_then_message_and_ignored(panel, monkeypatch):
    def boom(**k):
        raise RuntimeError("stuck")

    event = _event()
    with monkeypatch.context() as patch:
        patch.setattr(panel.scope, "finish", boom)
        panel.closeEvent(event)
    assert event.ignored and panel.message.text() == "stuck"


def test_main_when_called_then_panel_shown(world):
    assert mod.main() is not None
    assert world.shown == [mod.KEY]


def test_capture_names_when_clock_reaches_deadline_exactly_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 2.0])  # the 2.0 s budget ends here; `>=` refuses, `>` would accept
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Glyph-name transfer expired"):
        mod.capture_names()
