# this_file: tests/test_teaching_text_tags.py
"""Symbol Tag Search: native tag capture, AND search and the panel, on real offscreen Qt."""

import sys
import threading
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import tags

    return tags


class Native:
    def __init__(self, glyphs):
        self.glyphs = glyphs  # fg id -> NS(name, tags)
        self.package = NS(isNull=False, fgId=4, id=9, findFgId=self.find)
        self.font = NS(id=4, glyphs=[NS(id=i) for i in glyphs])
        self.flWorkspace = NS(instance=lambda: NS(currentPackage=self.package))
        self.CurrentFont = lambda: self.font

    def find(self, fg):
        item = self.glyphs.get(fg)
        return None if item is None else NS(isNull=False, name=item[0], tags=item[1])


GLYPHS = {1: ("A", ("Latin", "upper")), 2: ("a", ("Latin",)), 3: ("alef", ("Hebrew",))}


def test_capture_tags_when_font_open_then_rows_in_order_and_bad_names_skipped(mod):
    native = Native({**GLYPHS, 4: ("bad name", ()), 5: ("", ()), 6: ("x/y", ()), 7: ("t", (1, 2)),
                     8: ("nbsp ", ()), 9: ("none", None)})
    rows, skipped = mod.capture_tags(native)
    assert rows[:3] == (("A", ("Latin", "upper")), ("a", ("Latin",)), ("alef", ("Hebrew",)))
    assert rows[-1] == ("none", ())
    assert len(skipped) == 5 and "Skipped 'bad name': name cannot form a slash proof" in skipped
    assert "Skipped 't': unreadable tags" in skipped


@pytest.mark.parametrize("breaker,message", [
    ("nopackage", "Open a font first"), ("null", "Open a font first"), ("nofont", "Open a font first"),
    ("mismatch", "Open a font first"), ("gone", "disappeared"), ("changed", "font changed"),
])
def test_capture_tags_when_context_wrong_then_refused(mod, breaker, message):
    native = Native(dict(GLYPHS))
    if breaker == "nopackage":
        native.package = None
        native.flWorkspace = NS(instance=lambda: NS(currentPackage=None))
    elif breaker == "null":
        native.package.isNull = True
    elif breaker == "nofont":
        native.CurrentFont = lambda: None
    elif breaker == "mismatch":
        native.font.id = 77
    elif breaker == "gone":
        native.glyphs.pop(2)
        native.font.glyphs.append(NS(id=2))
    elif breaker == "changed":
        reads = []

        class Workspace:
            @property
            def currentPackage(self):
                reads.append(1)
                return native.package if len(reads) == 1 else NS(isNull=False, fgId=4, id=10)

        native.flWorkspace = NS(instance=lambda: Workspace())
    with pytest.raises(ValueError, match=message):
        mod.capture_tags(native)


def test_capture_tags_when_deadline_passes_then_no_partial_result(mod):
    with pytest.raises(TimeoutError, match="expired"):
        mod.capture_tags(Native(dict(GLYPHS)), deadline=0.0)


def test_capture_tags_when_off_main_thread_then_refused(mod):
    errors = []

    def work():
        try:
            mod.capture_tags(Native(dict(GLYPHS)))
        except RuntimeError as error:
            errors.append(str(error))

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    assert errors == ["Read font tags on the main UI thread."]


def test_capture_tags_when_default_native_then_resolved_lazily(mod, monkeypatch):
    import fontlabapp

    native = Native(dict(GLYPHS))
    monkeypatch.setattr(fontlabapp, "_native", lambda name: native, raising=False)
    assert len(mod.capture_tags()[0]) == 3


def test_search_result_when_terms_then_and_match_on_names_and_tags(mod, monkeypatch):
    monkeypatch.setattr(mod, "capture_tags", lambda: ((("A", ("Latin", "upper")), ("a", ("Latin",)), ("alef", ("Hebrew",))), ("Skipped x",)))
    assert mod.search_result(("latin",)) == ("/A/a", ("Skipped x",))
    assert mod.search_result(("LATIN upper",))[0] == "/A"
    assert mod.search_result(("a hebrew",))[0] == "/alef"
    assert mod.search_result(("nothing",))[0] == ""
    assert mod.build_output(("latin",)) == "/A/a"


def test_search_result_when_blank_then_font_never_read(mod, monkeypatch):
    monkeypatch.setattr(mod, "capture_tags", lambda: (_ for _ in ()).throw(AssertionError("read")))
    assert mod.search_result(("  ",)) == ("", ())


@pytest.mark.parametrize("text", ["\0", "a ", " ", " ", "\r"])
def test_checked_when_unsafe_then_refused(mod, text):
    with pytest.raises(ValueError, match="NUL, NBSP"):
        mod.checked(text)
    with pytest.raises(ValueError, match="surrogate"):
        mod.checked("\ud800")
    assert mod.checked("fine é") == "fine é"


@pytest.fixture
def tags(lab, monkeypatch):  # noqa: F811
    module, shown = lab("tags")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    state = NS(rows=(("A", ("Latin",)), ("b", ("Greek",))), skipped=("Skipped 'x'",), error=None)

    def capture():
        if state.error:
            raise state.error
        return state.rows, state.skipped

    monkeypatch.setattr(module, "capture_tags", capture)
    yield module, qt, parent, state
    module._PANELS.clear()
    module.CHOICES.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_blank_then_empty_output_and_when_searched_then_proof_and_skips(tags):
    module, qt, parent, state = tags
    panel = module.show(qt, parent, embedded=True)
    assert panel in module._PANELS and panel.output_box.toPlainText() == ""
    panel.input_boxes[0].setText("latin")
    hooks = []
    panel.lab_refresh_preview = lambda: hooks.append(1)
    click(panel, qt, "Refresh Result")
    assert panel.output_box.toPlainText() == "/A" and hooks == [1]
    assert panel.status_line.text().startswith("Result refreshed.") and "Skipped 'x'" in panel.status_line.text()


def test_panel_when_copy_then_fresh_result_on_clipboard_or_refusal(tags, monkeypatch):
    module, qt, parent, state = tags
    panel = module.show(qt, parent, embedded=True)
    copied = []
    monkeypatch.setattr(qt.QtGui.QApplication, "clipboard", staticmethod(lambda: NS(setText=copied.append)))
    click(panel, qt, "Copy Fresh Result")
    assert panel.status_line.text() == "No matching output to copy." and copied == []
    panel.input_boxes[0].setText("greek")
    click(panel, qt, "Copy Fresh Result")
    assert copied == ["/b"] and panel.status_line.text().startswith("Fresh result copied.")
    state.error = ValueError("Open a font first.")
    click(panel, qt, "Copy Fresh Result")
    assert panel.output_box.toPlainText() == "" and panel.status_line.text() == "Open a font first."
    click(panel, qt, "Refresh Result")
    assert panel.status_line.text() == "Open a font first."


def test_panel_when_choice_field_then_combo_read_by_current_text(tags, monkeypatch):
    module, qt, parent, state = tags
    monkeypatch.setattr(module, "FIELDS", (("Tag", "Latin"),))
    monkeypatch.setitem(module.CHOICES, 0, ("Latin", "Greek"))
    panel = module.show(qt, parent, embedded=True)
    assert panel.output_box.toPlainText() == "/A"
    panel.input_boxes[0].setCurrentIndex(1)
    click(panel, qt, "Refresh Result")
    assert panel.output_box.toPlainText() == "/b"


def test_panel_when_closed_or_destroyed_then_released_or_retained(tags):
    module, qt, parent, state = tags
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.signal_scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.signal_scope.finish
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS
    other = module.show(qt, parent, embedded=True)
    other.release_owner()
    assert other not in module._PANELS
    other.release_owner()


def test_show_when_controls_fail_then_cleaned_up_and_main_build(tags, monkeypatch, capsys):
    module, qt, parent, state = tags
    window = module.show(qt, parent)
    assert window.isVisible()
    window.close()
    module._PANELS.clear()
    with monkeypatch.context() as local:
        local.setattr(qt.QtGui, "QPlainTextEdit", lambda *a: (_ for _ in ()).throw(RuntimeError("no editor")))
        with pytest.raises(RuntimeError, match="no editor"):
            module.show(qt, parent)
    assert module._PANELS == []
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p: seen.append(p))
    module.main()
    assert seen == [parent]
    monkeypatch.setattr(module, "show", lambda q, p: (_ for _ in ()).throw(ValueError("nope")))
    module.main()
    assert capsys.readouterr().out == f"{module.TITLE}: nope\n"


def test_capture_tags_when_package_turns_null_after_scan_then_refused(mod):
    native = Native(dict(GLYPHS))
    reads = []

    class Workspace:
        @property
        def currentPackage(self):
            reads.append(1)
            if len(reads) == 1:
                return native.package
            return NS(isNull=True, fgId=4, id=9)  # same identity, but gone

    native.flWorkspace = NS(instance=lambda: Workspace())
    with pytest.raises(ValueError, match="font changed"):
        mod.capture_tags(native)


def test_capture_tags_when_clock_equals_deadline_at_first_glyph_then_no_partial_result(mod, monkeypatch):
    ticks = iter([5.0, 0.0, 0.0, 0.0])  # only the first loop check reaches the deadline: `>=` refuses, `>` would not
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="expired"):
        mod.capture_tags(Native(dict(GLYPHS)), deadline=5.0)


def test_capture_tags_when_clock_equals_deadline_only_after_scan_then_no_partial_result(mod, monkeypatch):
    ticks = iter([0.0, 0.0, 0.0, 5.0])  # three loop checks pass; the final check equals the deadline
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="expired"):
        mod.capture_tags(Native(dict(GLYPHS)), deadline=5.0)
