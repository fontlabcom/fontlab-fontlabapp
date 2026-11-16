# this_file: tests/test_teaching_painter_outline_svg.py
"""Glyph Outline SVG: capture, frame, SVG text, saving and panel, on real offscreen Qt with a fake host."""

import sys
import types

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import dialog_base, with_properties
from fontlabapp.fontui.teaching_painter import outline_svg as mod


class Layer:
    isNull = False
    id = 7
    advanceWidth = 600.0


class Glyph:
    def __init__(self):
        self.name, self.id, self.layer = "A", 3, Layer()
        self.package = None

    def findLayer(self, master):
        return self.layer


class Pkg:
    def __init__(self):
        self.id, self.fgId, self.master = 1, 11, "Regular"
        self.descender_value, self.ascender_value = -200.0, 800.0
        self.glyph = Glyph()
        self.glyph.package = self


@pytest.fixture
def world(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp
    import fontlabapp.contours.nodes.coordinates as coordinates
    import fontlabapp.core.scripting as scripting
    import fontlabapp.proof.inspectors.model as inspectors
    from PySide6 import QtSvg

    qt = sys.modules["PythonQt"]
    qt.QtSvg = QtSvg
    qt.QtCore.QIODevice.OpenMode = qt.QtCore.QIODevice.OpenModeFlag
    with_properties(qt.QtGui)
    state = types.SimpleNamespace(package=Pkg(), shown=[], glyph="default", source=("src",))
    path = qt.QtGui.QPainterPath()
    path.addRect(10, 20, 500, 700)
    state.path = path
    natives = {"fontlab": types.SimpleNamespace(MainWindow=lambda: None), "PythonQt": qt}
    monkeypatch.setattr(fontlabapp, "_native", lambda name: natives[name], raising=False)
    monkeypatch.setattr(scripting, "current_package", lambda *ident: state.package)
    monkeypatch.setattr(scripting, "names_dialog_type", lambda: dialog_base(qt.QtGui))
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda cls, key: state.shown.append(key) or cls(None)
    )
    monkeypatch.setattr(
        coordinates, "current_glyph",
        lambda package: state.package.glyph if state.glyph == "default" else state.glyph,
    )
    monkeypatch.setattr(inspectors, "outline", lambda layer: state.path)
    monkeypatch.setattr(inspectors, "outline_source", lambda layer: state.source)
    return state


def test_capture_outline_when_ready_then_label_path_and_metrics(world):
    label, path, metrics = mod.capture_outline()
    assert label == "A / Regular" and path is world.path
    assert metrics == (600.0, -200.0, 800.0)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda w: setattr(w, "package", None), "Open a font and a glyph before Capture."),
        (lambda w: setattr(w, "glyph", None), "Open a glyph before Capture."),
        (lambda w: setattr(w.package.glyph.layer, "isNull", True), "The glyph has no current-master layer."),
        (lambda w: setattr(w.package.glyph, "package", types.SimpleNamespace(id=99)),
         "The current glyph belongs to another font."),
        (lambda w: setattr(w, "path", w.path.__class__()), "The current glyph has no drawable outline."),
        (lambda w: setattr(w.package.glyph, "name", "A\x01"),
         "The glyph or master name cannot be transferred exactly."),
        (lambda w: setattr(w.package.glyph, "name", "A "),
         "The glyph or master name cannot be transferred exactly."),
    ],
)
def test_capture_outline_when_context_invalid_then_refused(world, edit, message):
    edit(world)
    with pytest.raises(ValueError) as error:
        mod.capture_outline()
    assert str(error.value) == message


def test_capture_outline_when_source_changes_then_refused(world, monkeypatch):
    import fontlabapp.proof.inspectors.model as inspectors

    calls = []
    monkeypatch.setattr(inspectors, "outline_source", lambda layer: calls.append(1) or (len(calls),))
    with pytest.raises(ValueError, match="Font, glyph, master or outline changed; Capture again."):
        mod.capture_outline()


def test_capture_outline_when_deadline_passes_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 5.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; capture again."):
        mod.capture_outline()


def test_capture_outline_when_deadline_passes_after_reads_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 0.1, 0.2, 5.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; capture again."):
        mod.capture_outline()


def test_font_frame_when_ink_inside_then_metrics_frame(world):
    assert mod.font_frame(world.path, (600.0, -200.0, 800.0)) == (0, -200, 600, 1000)


def test_font_frame_when_overhang_then_rounded_outward(world):
    world.path.addRect(-5.5, -300.5, 1000.2, 1200)
    assert mod.font_frame(world.path, (600.0, -200.0, 800.0)) == (-6, -301, 1001, 1201)


@pytest.mark.parametrize("metrics", [(600.0, 800.0, -200.0), (float("nan"), -200.0, 800.0)])
def test_font_frame_when_metrics_bad_then_refused(world, metrics):
    with pytest.raises(ValueError, match="Use finite outline bounds and ordered font"):
        mod.font_frame(world.path, metrics)


def test_font_frame_when_too_large_then_refused(world):
    with pytest.raises(ValueError, match="outside Qt's document size range"):
        mod.font_frame(world.path, (0.0, -3e9, 3e9))


def test_suggested_svg_path_when_label_has_symbols_then_safe_desktop_name(monkeypatch, tmp_path):
    monkeypatch.setattr(mod.Path, "home", lambda: tmp_path)
    assert mod.suggested_svg_path("A / Regular") == str(tmp_path / "Desktop" / "A_Regular.svg")
    assert mod.suggested_svg_path("///") == str(tmp_path / "Desktop" / "glyph.svg")


def test_svg_text_when_path_then_flipped_filled_svg(world):
    qt = sys.modules["PythonQt"]
    text = mod.svg_text(qt, world.path, "A / Regular", (0, -200, 600, 1000))
    assert "<svg" in text and "</svg>" in text
    assert "A / Regular" in text and "#182a35" in text
    assert 'viewBox="0 -800 600 1000"' in text


def test_svg_text_when_no_generator_then_refused(world):
    qt = types.SimpleNamespace(QtGui=sys.modules["PythonQt"].QtGui, QtCore=sys.modules["PythonQt"].QtCore)
    with pytest.raises(ValueError, match="does not expose QSvgGenerator"):
        mod.svg_text(qt, world.path, "A", (0, 0, 1, 1))


def test_svg_text_when_buffer_will_not_open_then_runtime_error(world, monkeypatch):
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(qt.QtCore.QBuffer, "open", lambda self, mode: False)
    with pytest.raises(RuntimeError, match="Cannot open the SVG output buffer."):
        mod.svg_text(qt, world.path, "A", (0, 0, 1, 1))


def test_svg_text_when_painter_will_not_begin_then_runtime_error(world, monkeypatch):
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(qt.QtGui.QPainter, "begin", lambda self, device: False)
    with pytest.raises(RuntimeError, match="SVG drawing failed: Cannot start the SVG painter."):
        mod.svg_text(qt, world.path, "A", (0, 0, 1, 1))


def test_svg_text_when_output_incomplete_then_refused(world, monkeypatch):
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(qt.QtGui.QPainter, "drawPath", lambda self, path: None)
    monkeypatch.setattr(qt.QtGui.QPainter, "begin", lambda self, device: True)
    monkeypatch.setattr(qt.QtGui.QPainter, "end", lambda self: True)
    with pytest.raises(RuntimeError, match="Qt returned incomplete SVG output."):
        mod.svg_text(qt, world.path, "A", (0, 0, 1, 1))


def test_save_svg_when_new_path_then_written_once(tmp_path):
    target = tmp_path / "a.svg"
    mod.save_svg(str(target), "<svg></svg>")
    assert target.read_text() == "<svg></svg>"
    with pytest.raises(ValueError, match="The output file already exists; choose a new path."):
        mod.save_svg(str(target), "<svg></svg>")


@pytest.mark.parametrize("name", ["rel.svg", "/tmp/x.txt"])
def test_save_svg_when_path_bad_then_refused(name):
    with pytest.raises(ValueError, match="Enter an absolute .svg path and Capture a result first."):
        mod.save_svg(name, "<svg/>")


def test_save_svg_when_text_empty_then_refused(tmp_path):
    with pytest.raises(ValueError, match="Capture a result first"):
        mod.save_svg(str(tmp_path / "a.svg"), "")


def test_save_svg_when_directory_missing_then_os_error_reported(tmp_path):
    with pytest.raises(ValueError, match="Cannot save SVG; a partial file may remain:"):
        mod.save_svg(str(tmp_path / "missing" / "a.svg"), "<svg/>")


@pytest.fixture
def panel(world, monkeypatch, tmp_path):
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(mod.Path, "home", lambda: tmp_path)
    sys._fontlab_samples = {}
    dialog = mod.panel_type(qt)(None)
    yield dialog
    sys._fontlab_samples = {}
    dialog.close()


def click(dialog, text):
    qt = sys.modules["PythonQt"]
    found = [b for b in dialog.findChildren(qt.QtGui.QPushButton) if b.text() == text]
    assert len(found) == 1, text
    found[0].click()


def test_panel_when_update_before_capture_then_asks_for_capture(panel):
    click(panel, "Update Proof")
    assert panel.message.text() == "Capture a glyph before Update Proof."
    assert panel.result == ""


def test_panel_when_captured_then_svg_shown_and_name_suggested(panel, tmp_path):
    click(panel, "Capture")
    assert panel.caption == "A / Regular" and "<svg" in panel.result and "</svg>" in panel.result
    assert panel.output_box.toPlainText() == panel.result
    assert panel.file_entry.text == str(tmp_path / "Desktop" / "A_Regular.svg")
    assert panel.message.text().startswith("A / Regular — snapshot.")


def test_panel_when_capture_fails_then_message_and_no_result(panel, world):
    world.package = None
    click(panel, "Capture")
    assert panel.message.text() == "Open a font and a glyph before Capture."
    assert panel.result == "" and panel.snapshot is None


def test_panel_when_name_edited_then_recapture_keeps_it(panel, tmp_path):
    click(panel, "Capture")
    panel.file_entry.setText(str(tmp_path / "mine.svg"))
    click(panel, "Capture")
    assert panel.file_entry.text == str(tmp_path / "mine.svg")


def test_panel_when_odd_even_chosen_then_proof_uses_fill_rule(panel):
    click(panel, "Capture")
    panel.fill_choice.setCurrentIndex(1)
    assert panel.proof_path().fillRule() == sys.modules["PythonQt"].QtCore.Qt.OddEvenFill
    click(panel, "Update Proof")
    assert 'fill-rule="evenodd"' in panel.result
    panel.fill_choice.setCurrentIndex(0)
    assert panel.proof_path().fillRule() == sys.modules["PythonQt"].QtCore.Qt.WindingFill


def test_panel_when_text_changed_by_qt_then_export_disabled(panel, monkeypatch):
    click(panel, "Capture")
    monkeypatch.setattr(panel.output_box, "toPlainText", lambda: "other")
    click(panel, "Update Proof")
    assert panel.message.text() == "Qt changed the SVG text; export is disabled."
    assert panel.result == ""


def test_panel_when_copy_then_clipboard_holds_svg(panel):
    qt = sys.modules["PythonQt"]
    click(panel, "Copy SVG")
    assert panel.message.text() == "Capture or Update Proof before copying."
    click(panel, "Capture")
    click(panel, "Copy SVG")
    assert qt.QtGui.QApplication.clipboard().text() == panel.result
    assert panel.message.text() == "SVG copied for an external vector editor."


def test_panel_when_save_then_file_written_and_second_save_refused(panel, tmp_path):
    click(panel, "Save SVG")
    assert panel.message.text() == "Enter an absolute .svg path and Capture a result first."
    click(panel, "Capture")
    target = tmp_path / "out.svg"
    panel.file_entry.setText(str(target))
    click(panel, "Save SVG")
    assert target.read_text() == panel.result
    assert panel.message.text() == "SVG saved for an external vector editor; font metadata is not included."
    click(panel, "Save SVG")
    assert panel.message.text() == "The output file already exists; choose a new path."


def test_panel_when_registered_then_release_forgets_only_itself(panel):
    sys._fontlab_samples[mod.KEY] = panel
    panel.release()
    assert mod.KEY not in sys._fontlab_samples
    sys._fontlab_samples[mod.KEY] = object()
    panel.release()
    assert mod.KEY in sys._fontlab_samples


def test_panel_when_destroyed_cleanup_then_snapshot_dropped(panel):
    click(panel, "Capture")
    sys._fontlab_samples[mod.KEY] = panel
    panel.destroyed_cleanup()
    assert panel.snapshot is None and mod.KEY not in sys._fontlab_samples


def test_panel_when_closed_then_snapshot_released(panel):
    click(panel, "Capture")
    panel.close()
    assert panel.snapshot is None


def test_panel_when_scope_will_not_finish_then_close_ignored(panel, monkeypatch):
    click(panel, "Capture")
    monkeypatch.setattr(panel.scope, "finish", lambda **kw: False)
    qt = sys.modules["PythonQt"]
    event = qt.QtGui.QCloseEvent()
    event.accept()
    panel.closeEvent(event)
    assert not event.isAccepted() and panel.snapshot is not None


def test_panel_when_finish_raises_then_close_ignored_with_message(panel, monkeypatch):
    def boom(**kw):
        raise RuntimeError("stuck")

    monkeypatch.setattr(panel.scope, "finish", boom)
    qt = sys.modules["PythonQt"]
    event = qt.QtGui.QCloseEvent()
    event.accept()
    panel.closeEvent(event)
    assert not event.isAccepted() and panel.message.text() == "stuck"


def test_panel_when_close_button_hooked_then_hook_runs(panel):
    calls = []
    panel.lab_close = lambda: calls.append(1)
    click(panel, "Close")
    assert calls == [1]


def test_main_when_ready_then_panel_shown(world):
    assert mod.main() is not None
    assert world.shown == [mod.KEY]


def test_main_when_show_fails_then_warning_box(world, monkeypatch):
    import fontlabapp.core.scripting as scripting
    import fontlabapp.qt.dialogs as dialogs

    seen = []
    monkeypatch.setattr(scripting, "show_script_dialog", lambda cls, key: (_ for _ in ()).throw(ValueError("nope")))
    monkeypatch.setattr(dialogs, "run_standard_message_box", lambda *a: seen.append(a[2:5]))
    assert mod.main() is None
    assert seen == [("Glyph Outline SVG", "nope", "Warning")]


def test_capture_outline_when_clock_reaches_deadline_exactly_at_first_read_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 2.0])  # `>=` at the context check refuses; `>` would accept
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; capture again."):
        mod.capture_outline()


def test_capture_outline_when_clock_reaches_deadline_exactly_after_reads_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 0.1, 0.2, 2.0])  # final check: `>=` refuses, `>` would accept
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; capture again."):
        mod.capture_outline()
