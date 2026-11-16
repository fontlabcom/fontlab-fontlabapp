# this_file: tests/test_teaching_painter_svg_reference.py
"""Glyph SVG Reference: capture, matrices and panel, on real offscreen Qt with a fake host."""

import sys
import types

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import dialog_base, with_properties
from fontlabapp.fontui.teaching_painter import svg_reference as mod

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="200" viewBox="0 0 100 200">'
    '<rect x="10" y="10" width="80" height="180" fill="red"/></svg>'
)
ANIMATED = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
    '<rect width="10" height="10"><animate attributeName="x" from="0" to="50" dur="2s" repeatCount="indefinite"/>'
    "</rect></svg>"
)


class Layer:
    isNull = False
    id = 7


class Glyph:
    def __init__(self):
        self.name, self.id, self.layer = "A", 3, Layer()
        self.package = None

    def findLayer(self, master):
        return self.layer


class Pkg:
    def __init__(self):
        self.id, self.fgId, self.master = 1, 11, "Regular"
        self.glyph = Glyph()
        self.glyph.package = self


@pytest.fixture
def world(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp
    import fontlabapp.contours.nodes.coordinates as coordinates
    import fontlabapp.core.scripting as scripting
    import fontlabapp.proof.inspectors.model as inspectors
    from PySide6 import QtSvg, QtSvgWidgets

    qt = sys.modules["PythonQt"]
    qt.QtSvg = types.SimpleNamespace(QGraphicsSvgItem=QtSvgWidgets.QGraphicsSvgItem, QSvgRenderer=QtSvg.QSvgRenderer)
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


def test_capture_outline_when_ready_then_label_and_path(world):
    label, path = mod.capture_outline()
    assert label == "A / Regular" and path is world.path


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda w: setattr(w, "package", None), "Open a font and a glyph before Compare."),
        (lambda w: setattr(w, "glyph", None), "Open a glyph before Compare."),
        (lambda w: setattr(w.package.glyph.layer, "isNull", True), "The glyph has no current-master layer."),
        (lambda w: setattr(w.package.glyph, "package", types.SimpleNamespace(id=9)),
         "The current glyph belongs to another font."),
        (lambda w: setattr(w.package.glyph, "name", "A "), "The glyph or master name cannot be transferred exactly."),
        (lambda w: setattr(w, "path", types.SimpleNamespace(isEmpty=lambda: True)), "The current glyph has no drawable outline."),
    ],
)
def test_capture_outline_when_context_invalid_then_refused(world, edit, message):
    edit(world)
    with pytest.raises(ValueError) as error:
        mod.capture_outline()
    assert str(error.value) == message


def test_capture_outline_when_outline_changes_then_refused(world, monkeypatch):
    import fontlabapp.proof.inspectors.model as inspectors

    calls = iter([("a",), ("b",)])
    monkeypatch.setattr(inspectors, "outline_source", lambda layer: next(calls))
    with pytest.raises(ValueError, match="Font, glyph, master or outline changed; Compare again."):
        mod.capture_outline()


def test_capture_outline_when_deadline_passes_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 5.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; Compare again."):
        mod.capture_outline()


def test_capture_outline_when_deadline_passes_late_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 0.1, 0.2, 5.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; Compare again."):
        mod.capture_outline()


def test_reference_file_when_valid_then_path(tmp_path):
    f = tmp_path / "a.SVG"
    f.write_text(SVG)
    assert mod.reference_file(str(f)) == f


@pytest.mark.parametrize("name", ["rel.svg", "{tmp}/missing.svg", "{tmp}/a.txt"])
def test_reference_file_when_invalid_then_refused(tmp_path, name):
    (tmp_path / "a.txt").write_text("x")
    with pytest.raises(ValueError, match="Enter an absolute path to an existing .svg file."):
        mod.reference_file(name.format(tmp=tmp_path))


def test_alignment_matrix_when_fitting_then_uniform_centered():
    assert mod.alignment_matrix((0, 0, 100, 50), (0, 0, 200, 200)) == (2.0, 0.0, 0.0, 2.0, 0.0, 50.0)


@pytest.mark.parametrize("source", [(0, 0, 0, 5), (0, 0, float("nan"), 5)])
def test_alignment_matrix_when_degenerate_then_refused(source):
    with pytest.raises(ValueError, match="SVG and glyph bounds must have finite positive dimensions."):
        mod.alignment_matrix(source, (0, 0, 10, 10))


def test_alignment_matrix_when_scale_overflows_then_refused():
    with pytest.raises(ValueError, match="The SVG display scale is outside the finite range."):
        mod.alignment_matrix((0, 0, 1e-320, 1e-320), (0, 0, 1e300, 1e300))


def test_reference_matrix_when_font_units_then_viewbox_mapping():
    assert mod.reference_matrix((0, 0, 50, 100), (10, 20, 100, 200), (0, 0, 1, 1), True) == (
        2.0, 0.0, 0.0, 2.0, 10.0, 20.0)


def test_reference_matrix_when_fit_then_normalized():
    assert mod.reference_matrix((0, 0, 100, 100), (0, 0, 100, 100), (0, 0, 50, 50), False) == (
        0.5, 0.0, 0.0, 0.5, 0.0, 0.0)


def test_reference_matrix_when_degenerate_then_refused():
    with pytest.raises(ValueError, match="SVG bounds and viewBox need finite positive dimensions."):
        mod.reference_matrix((0, 0, 0, 1), (0, 0, 1, 1), (0, 0, 1, 1), True)


def test_reference_matrix_when_overflow_then_refused():
    with pytest.raises(ValueError, match="SVG user-coordinate mapping is outside the finite range."):
        mod.reference_matrix((0, 0, 1e-300, 1e-300), (0, 0, 1e300, 1e300), (0, 0, 1, 1), True)


@pytest.fixture
def panel(world, tmp_path, monkeypatch):
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    dialog = mod.panel_type(qt)(None)
    dialog.svg = tmp_path / "ref.svg"
    dialog.svg.write_text(SVG)
    yield dialog
    dialog.scope.finish(destroyed=True)
    dialog.terminal.finish(destroyed=True)


def click(dialog, text):
    qt = sys.modules["PythonQt"]
    found = [b for b in dialog.findChildren(qt.QtGui.QPushButton) if b.text() == text]
    assert len(found) == 1, text
    found[0].click()


def test_compare_when_valid_then_reference_and_glyph_in_scene(panel):
    panel.source_entry.setText(str(panel.svg))
    click(panel, "Compare")
    assert panel.message.text() == (
        "A / Regular — snapshot. Fit silhouette: normalized display scale; source file unchanged."
    )
    assert panel.reference_item is not None and len(panel.canvas.items()) == 2
    assert panel.view_caption == "A / Regular"


def test_compare_when_mode_switched_then_font_units_caption(panel):
    panel.source_entry.setText(str(panel.svg))
    click(panel, "Compare")
    panel.mode_choice.setCurrentIndex(1)
    assert panel.message.text() == (
        "A / Regular — snapshot. Font units: SVG user unit = font unit; source file unchanged."
    )


def test_compare_when_opacity_changed_then_item_opacity_follows(panel):
    panel.source_entry.setText(str(panel.svg))
    click(panel, "Compare")
    assert panel.reference_item.opacity() == pytest.approx(0.35)
    panel.opacity_control.setValue(0.8)
    assert panel.reference_item.opacity() == pytest.approx(0.8)


def test_change_opacity_when_no_reference_then_nothing(panel):
    panel.opacity_control.setValue(0.5)
    assert panel.reference_item is None


def test_reposition_when_no_reference_then_false(panel):
    assert panel.reposition_reference() is False


def test_compare_when_path_missing_then_message_and_empty_scene(panel):
    panel.source_entry.setText("nope.svg")
    click(panel, "Compare")
    assert panel.message.text() == "Enter an absolute path to an existing .svg file."
    assert panel.canvas.items() == [] and panel.reference_item is None


def test_compare_when_qtsvg_missing_then_refused(panel):
    qt = sys.modules["PythonQt"]
    qt.QtSvg = types.SimpleNamespace()
    click(panel, "Compare")
    assert panel.message.text() == "This FontLab Qt build does not expose QGraphicsSvgItem."


def test_compare_when_svg_invalid_then_refused_and_cleared(panel):
    bad = panel.svg.with_name("bad.svg")
    bad.write_text("not svg")
    panel.source_entry.setText(str(bad))
    click(panel, "Compare")
    assert panel.message.text() == "Qt cannot render this SVG file."
    assert panel.canvas.items() == []


def test_compare_when_svg_animated_then_refused(panel, monkeypatch):
    anim = panel.svg.with_name("anim.svg")
    anim.write_text(ANIMATED)
    from PySide6 import QtSvg

    monkeypatch.setattr(QtSvg.QSvgRenderer, "animated", lambda self: True)
    panel.source_entry.setText(str(anim))
    click(panel, "Compare")
    assert panel.message.text() == "Use a static SVG reference; animated SVG is refused."
    assert panel.canvas.items() == []


def test_compare_when_capture_times_out_then_message(panel, monkeypatch):
    panel.source_entry.setText(str(panel.svg))
    ticks = iter([0.0, 5.0])
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    click(panel, "Compare")
    assert panel.message.text() == "Outline capture expired; Compare again."


def test_compare_when_preview_hook_present_then_called(panel):
    seen = []
    panel.lab_refresh_preview = lambda: seen.append(1)
    panel.source_entry.setText(str(panel.svg))
    click(panel, "Compare")
    assert seen == [1]


def test_reposition_when_boxes_degenerate_then_scene_cleared(panel):
    panel.source_entry.setText(str(panel.svg))
    click(panel, "Compare")
    panel.reference_boxes = ((0, 0, 0, 0), (0, 0, 1, 1), (0, 0, 1, 1))
    assert panel.reposition_reference() is False
    assert panel.message.text() == "SVG bounds and viewBox need finite positive dimensions."
    assert panel.reference_item is None


def test_release_when_registered_then_removed_only_for_self(panel):
    sys._fontlab_samples[mod.KEY] = object()
    panel.release()
    assert mod.KEY in sys._fontlab_samples
    sys._fontlab_samples[mod.KEY] = panel
    panel.release()
    assert mod.KEY not in sys._fontlab_samples


def test_destroyed_cleanup_when_called_then_state_dropped(panel):
    sys._fontlab_samples[mod.KEY] = panel
    panel.destroyed_cleanup()
    assert panel.reference_item is None and mod.KEY not in sys._fontlab_samples


def test_close_when_clicked_then_registry_released(panel):
    sys._fontlab_samples[mod.KEY] = panel
    panel.show()
    click(panel, "Close")
    assert mod.KEY not in sys._fontlab_samples


def test_close_when_scope_refuses_then_ignored(panel, monkeypatch):
    sys._fontlab_samples[mod.KEY] = panel
    monkeypatch.setattr(panel.scope, "finish", lambda **k: False)
    event = types.SimpleNamespace(ignored=False, ignore=lambda: setattr(event, "ignored", True))
    panel.closeEvent(event)
    assert event.ignored and sys._fontlab_samples[mod.KEY] is panel


def test_close_when_cleanup_raises_then_message_and_ignored(panel, monkeypatch):
    def boom(**k):
        raise RuntimeError("stuck")

    event = types.SimpleNamespace(ignored=False, ignore=lambda: setattr(event, "ignored", True))
    with monkeypatch.context() as patch:
        patch.setattr(panel.scope, "finish", boom)
        panel.closeEvent(event)
    assert event.ignored and panel.message.text() == "stuck"


def test_close_when_lab_hook_present_then_hook_used(panel):
    seen = []
    panel.lab_close = lambda: seen.append(1)
    click(panel, "Close")
    assert seen == [1]


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
    assert seen == [("Glyph SVG Reference", "nope", "Warning")]


def test_capture_outline_when_clock_reaches_deadline_exactly_at_first_read_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 2.0])  # `>=` at the context check refuses; `>` would accept
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; Compare again."):
        mod.capture_outline()


def test_capture_outline_when_clock_reaches_deadline_exactly_after_reads_then_timeout(world, monkeypatch):
    ticks = iter([0.0, 0.1, 0.2, 2.0])  # final check: `>=` refuses, `>` would accept
    monkeypatch.setattr(mod, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="Outline capture expired; Compare again."):
        mod.capture_outline()


@pytest.mark.parametrize("item,boxes", [(None, ((0, 0, 1, 1),) * 3), ("loaded", None)])
def test_reposition_when_only_one_cached_piece_present_then_false_without_error(panel, item, boxes):
    panel.reference_item, panel.reference_boxes = item, boxes
    before = panel.message.text()
    assert panel.reposition_reference() is False
    assert panel.message.text() == before
