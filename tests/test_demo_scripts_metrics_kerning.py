# this_file: tests/test_demo_scripts_metrics_kerning.py
"""Offline runs of the Scripts/Metrics and Scripts/Kerning demos (Issue 208, Task 4).

Each demo runs through runpy as ``__main__`` (entry points and arguments are
asserted) and as an imported name (nothing may run). The real host-free
``fontlabapp`` modules stay in use; ``PythonQt`` and ``fontlab`` are stubbed,
and so are the few modules that load native classes when imported (panel and
dialog modules). Fake fonts answer exactly the reads the real kerning and
metrics code makes. Message boxes that ask a question are answered by a
scripted ``run_standard_message_box``. Offline results are not native FontLab
acceptance.
"""

from types import SimpleNamespace

import pytest
from _demo_support import FakeWidget, Recorder, qt_namespace, run_script, script_path, stub_module
from unittest.mock import MagicMock

PACKAGE = SimpleNamespace(isNull=False, id=3, master="Regular")
OK, YES, NO = 1, 2, 4

WORKSHEET = script_path("Metrics", "Spacing Worksheet Demo")
OFFSET = script_path("Metrics", "Spacing Offset Demo")
TABULAR = script_path("Metrics", "Tabular Width Demo")
VERTICAL = script_path("Metrics", "Vertical Metrics Demo")
ZONES = script_path("Metrics", "Alignment Zones Demo")
WRITER = script_path("Metrics", "Master Writer Demo")
CANVAS = script_path("Metrics", "Canvas RSB Demo")
PANEL = script_path("Metrics", "Metrics Panel Demo")
PERSISTENCE = script_path("Kerning", "Kerning Persistence Demo")
GROUP_PROOF = script_path("Kerning", "Kerning Group Proof Demo")
PROOFS = script_path("Kerning", "Kerning Proofs Demo")
SELECTION = script_path("Kerning", "Kerning Selection Demo")
SYMMETRY = script_path("Kerning", "Kerning Symmetry Demo")
CUTOFF = script_path("Kerning", "Kerning Cutoff Demo")
BATCH = script_path("Kerning", "Kerning Batch Demo")
IDENTITY = script_path("Kerning", "Kerning Identity Demo")
INSPECT = script_path("Kerning", "Kerning Inspect Demo")
EDITOR = script_path("Kerning", "Kerning Editor Demo")


def install_host(monkeypatch, answers=(), package=PACKAGE, **names):
    """Stub the natives; scripted answers go to ``run_standard_message_box``.

    Returns (QtGui, asked) where ``asked`` collects one tuple per question box
    in the order (parent, title, text, icon, buttons, default).
    """
    import fontlabapp.qt.dialogs as dialogs

    qt = qt_namespace(**names)
    qt.QtGui.QMessageBox.Ok, qt.QtGui.QMessageBox.Yes, qt.QtGui.QMessageBox.No = OK, YES, NO
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    workspace = SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=package))
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: "main-window", flWorkspace=workspace)
    asked, replies = [], iter(answers)

    def ask(_qt, parent, title, text, icon, buttons, default=None):
        asked.append((parent, title, text, icon, buttons, default))
        return next(replies, OK)

    monkeypatch.setattr(dialogs, "run_standard_message_box", ask)
    return qt.QtGui, asked


def shown(gui) -> tuple[str, str, str]:
    """(title, text, details) of the one modal message box the demo ran."""
    assert gui.QMessageBox.call_count == 1, "exactly one message box expected"
    assert gui.QMessageBox.call_args[0] == ("main-window",), "box parents to the main window"
    box = gui.QMessageBox.return_value
    box.exec.assert_called_once_with()
    details = box.setDetailedText.call_args[0][0] if box.setDetailedText.called else ""
    return box.setText.call_args[0][0], box.setInformativeText.call_args[0][0], details


def forbid(monkeypatch, module, *names):
    """Replace writers on ``module`` with recorders; the test asserts they never ran."""
    recorders = {}
    for name in names:
        recorders[name] = Recorder()
        monkeypatch.setattr(module, name, recorders[name])
    return recorders


def capture_dialog(monkeypatch):
    """Record ``show_script_dialog`` calls instead of opening a window."""
    import fontlabapp.core.scripting as scripting

    recorder = Recorder("window")
    monkeypatch.setattr(scripting, "show_script_dialog", recorder)
    return recorder


# --- Fake kerning fonts ----------------------------------------------------------


class FakeGroups:
    def __init__(self, groups):
        self.groups = groups

    def items(self):
        return self.groups.items()

    def asDict(self):
        return dict(self.groups)


class FakeKerning:
    """Answers items(), groups and get() the way the native kerning object does."""

    def __init__(self, pairs, groups):
        self.pairs, self.groups = pairs, FakeGroups(groups)

    @staticmethod
    def side(name):
        return SimpleNamespace(id=name[1:], mode="groupMode") if name.startswith("@") else SimpleNamespace(id=name, mode="glyphMode")

    def items(self):
        return [(SimpleNamespace(left=self.side(left), right=self.side(right)), value) for (left, right), value in self.pairs.items()]

    def get(self, key):
        return self.pairs.get(key)


class FakeFont:
    """A font with two masters; every name in ``glyph_names`` exists."""

    id, isNull = 3, False

    def __init__(self, pairs, groups, masters=("Regular", "Bold"), glyph_names=None):
        self.masters, self.master, self.upm = tuple(masters), masters[0], 1000
        self.pairs, self.groups, self.glyph_names = pairs, groups, glyph_names

    def kerning(self, master):
        return FakeKerning(self.pairs.get(master, {}), self.groups.get(master, {}))

    def glyph(self, name):
        return SimpleNamespace(isNull=False, name=name, id=sum(map(ord, name)))

    def findName(self, name):
        return self.glyph(name) if self.glyph_names is None or name in self.glyph_names else None

    def findUnicode(self, code):
        return self.findName(chr(code))


KERN_PAIRS = {"Regular": {("A", "V"): -80, ("@Aleft", "V"): -60, ("T", "o"): -300}, "Bold": {("A", "V"): -90}}
KERN_GROUPS = {"Regular": {"Aleft": (["A", "Aacute"], "KernLeft")}, "Bold": {}}


def kern_font(**options):
    return FakeFont(KERN_PAIRS, KERN_GROUPS, glyph_names={"A", "Aacute", "V", "T", "o"}, **options)


# --- Spacing Worksheet and Spacing Offset Demos ----------------------------------


@pytest.mark.parametrize("path, module", [(WORKSHEET, "fontlabapp.metrics.worksheet.model"), (OFFSET, "fontlabapp.metrics.offset.model")])
def test_spacing_demos_when_font_open_then_open_the_window_once(monkeypatch, path, module) -> None:
    import importlib

    gui, asked = install_host(monkeypatch)
    show = Recorder()
    monkeypatch.setattr(importlib.import_module(module), "show", show)
    run_script(path)
    assert show.calls == [((), {})]
    assert asked == [] and gui.QMessageBox.call_count == 0


@pytest.mark.parametrize("path, module", [(WORKSHEET, "fontlabapp.metrics.worksheet.model"), (OFFSET, "fontlabapp.metrics.offset.model")])
def test_spacing_demos_when_no_font_then_say_so_and_open_nothing(monkeypatch, path, module) -> None:
    import importlib

    _, asked = install_host(monkeypatch, package=None)
    show = Recorder()
    monkeypatch.setattr(importlib.import_module(module), "show", show)
    run_script(path)
    assert show.calls == [] and len(asked) == 1 and "Open a font" in asked[0][2]


@pytest.mark.parametrize("path, module", [(WORKSHEET, "fontlabapp.metrics.worksheet.model"), (OFFSET, "fontlabapp.metrics.offset.model")])
@pytest.mark.parametrize("error", [ValueError("no selection"), RuntimeError("main thread"), TimeoutError("slow")])
def test_spacing_demos_when_open_fails_then_warning_names_the_error(monkeypatch, path, module, error) -> None:
    import importlib

    _, asked = install_host(monkeypatch)

    def failing():
        raise error

    monkeypatch.setattr(importlib.import_module(module), "show", failing)
    run_script(path)
    assert len(asked) == 1 and asked[0][3] == "Warning" and str(error) in asked[0][2]


@pytest.mark.parametrize("path", [WORKSHEET, OFFSET, TABULAR, VERTICAL, PERSISTENCE, PANEL, INSPECT, EDITOR])
def test_window_demos_when_imported_then_nothing_runs(monkeypatch, path) -> None:
    gui, asked = install_host(monkeypatch)
    shown_windows = capture_dialog(monkeypatch)
    run_script(path, "imported")
    assert asked == [] and shown_windows.calls == [] and gui.QMessageBox.call_count == 0


# --- Tabular Width, Vertical Metrics and Kerning Persistence Demos ---------------


class TabularWidthDialog:
    KEY = "check_tabular_widths"


class VerticalMetricsDialog:
    KEY = "vertical_metrics_reporter"


class KerningPersistenceDialog:
    KEY = "kerning_persistence_audit"


DIALOGS = [
    (TABULAR, "fontlabapp.metrics.tabular_width.ui", TabularWidthDialog),
    (VERTICAL, "fontlabapp.metrics.vertical.ui", VerticalMetricsDialog),
    (PERSISTENCE, "fontlabapp.kerning.persistence.ui", KerningPersistenceDialog),
]


@pytest.mark.parametrize("path, module, dialog", DIALOGS)
def test_report_dialog_demos_when_font_open_then_show_the_owned_dialog_under_its_key(monkeypatch, path, module, dialog) -> None:
    gui, asked = install_host(monkeypatch)
    stub_module(monkeypatch, module, **{dialog.__name__: dialog})
    opened = capture_dialog(monkeypatch)
    run_script(path)
    assert opened.calls == [((dialog, dialog.KEY), {})]
    assert asked == [] and gui.QMessageBox.call_count == 0


@pytest.mark.parametrize("path, module, dialog", DIALOGS)
def test_report_dialog_demos_when_no_font_then_say_so_and_open_nothing(monkeypatch, path, module, dialog) -> None:
    _, asked = install_host(monkeypatch, package=None)
    stub_module(monkeypatch, module, **{dialog.__name__: dialog})
    opened = capture_dialog(monkeypatch)
    run_script(path)
    assert opened.calls == [] and len(asked) == 1 and "Open a font" in asked[0][2]


@pytest.mark.parametrize("path, module, dialog", DIALOGS)
def test_report_dialog_demos_when_open_fails_then_warning_names_the_error(monkeypatch, path, module, dialog) -> None:
    import fontlabapp.core.scripting as scripting

    _, asked = install_host(monkeypatch)
    stub_module(monkeypatch, module, **{dialog.__name__: dialog})

    def failing(kind, key):
        raise RuntimeError("old window will not close")

    monkeypatch.setattr(scripting, "show_script_dialog", failing)
    run_script(path)
    assert len(asked) == 1 and asked[0][3] == "Warning" and "old window will not close" in asked[0][2]


# --- Alignment Zones Demo ----------------------------------------------------------


def test_zones_demo_when_font_open_then_lists_current_master_zones_and_the_sample(monkeypatch) -> None:
    from fontlabapp.metrics.zones import native
    from fontlabapp.metrics.zones.data import Zone, Zones

    gui, _ = install_host(monkeypatch)
    read = Recorder(Zones(top=(Zone(505, 7, "my-top"),), bottom=()))
    monkeypatch.setattr(native, "read_zones", read)
    run_script(ZONES)
    _, text, details = shown(gui)
    assert read.calls == [((PACKAGE,), {})]
    assert text == "Zones of master Regular. Nothing was changed."
    assert "Master Regular\nTop: 'my-top' at 505, width 7\nBottom: none" in details
    assert "Top: 'x-height' at 500, width 10\nTop: 'cap height' at 700, width 12" in details
    assert "Bottom: 'baseline' at 0, width 12" in details, "the sample derives a baseline zone from the o overshoot"


def test_zones_demo_when_no_font_then_shows_only_the_sample_and_reads_nothing(monkeypatch) -> None:
    from fontlabapp.metrics.zones import native

    gui, _ = install_host(monkeypatch, package=None)
    read = forbid(monkeypatch, native, "read_zones")["read_zones"]
    run_script(ZONES)
    _, text, details = shown(gui)
    assert read.calls == [] and text.startswith("Open a font to see its zones")
    assert "Sample suggestion" in details and "Master " not in details


@pytest.mark.parametrize("error", [ValueError("Unreadable native Top zone 'a'."), RuntimeError("native read failed")])
def test_zones_demo_when_zones_unreadable_then_message_names_the_error_and_sample_remains(monkeypatch, error) -> None:
    from fontlabapp.metrics.zones import native

    gui, _ = install_host(monkeypatch)

    def unreadable(package):
        raise error

    monkeypatch.setattr(native, "read_zones", unreadable)
    run_script(ZONES)
    _, text, details = shown(gui)
    assert text == f"The zones could not be read: {error}" and "Sample suggestion" in details


def test_zones_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    run_script(ZONES, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Master Writer Demo ----------------------------------------------------------


def test_writer_demo_when_main_then_explains_checked_sample_and_writes_nothing(monkeypatch) -> None:
    from fontlabapp.metrics import master_writer

    gui, _ = install_host(monkeypatch)
    writers = forbid(monkeypatch, master_writer, "write_master_metrics")
    run_script(WRITER)
    _, text, details = shown(gui)
    assert writers["write_master_metrics"].calls == []
    assert text == "Sample metrics request, checked but never written."
    assert "ascender, descender, xHeight, capsHeight, lineGap" in details
    assert "Checked values: {'Regular': {'ascender': 750.0, 'capsHeight': 700.0}, 'Bold': {'xHeight': 510.5}}" in details


def test_writer_demo_when_main_then_lists_every_refused_request_with_its_reason(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    run_script(WRITER)
    details = shown(gui)[2]
    assert "Unknown metric field 'hhea_line_gap'" in details
    assert "names 'capsHeight' twice ('capHeight' and 'capsHeight')" in details
    assert "ascender must be a finite number" in details
    assert "{} -> No master metric to write." in details


def test_writer_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    run_script(WRITER, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Canvas RSB Demo ---------------------------------------------------------------


def test_canvas_demo_when_main_then_prints_sample_geometry_and_opens_no_panel(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    opened = capture_dialog(monkeypatch)
    run_script(CANVAS)
    _, text, details = shown(gui)
    assert opened.calls == [] and text == "Sample right-sidebearing marker geometry. Nothing was drawn."
    assert "upright, left to right:\n  line from (500.0, 750) to (500.0, -250)" in details
    assert "triangle (240.0, -250.0), (250.0, -240.0), (260.0, -250.0)" in details
    assert "italic 12 degrees, left to right:\n  line from (606.3, 750) to (393.7, -250)" in details
    assert "upright, right to left:\n  line from (0.0, 750) to (0.0, -250)" in details


def test_canvas_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    run_script(CANVAS, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Metrics Panel Demo ------------------------------------------------------------


class FakePanelBase:
    """Stands in for the PythonQt MetricsPanel: the hooks the subclass fills in."""

    def __init__(self, parent=None):
        self.apply_button, self.status = MagicMock(), MagicMock()


def panel_demo(monkeypatch, package=PACKAGE):
    """Run the demo with a fake base; returns (asked, show_script_dialog calls, panel or None)."""
    import fontlabapp.metrics.panel.model as model

    _, asked = install_host(monkeypatch, package=package)
    monkeypatch.setattr(model, "panel_type", lambda: FakePanelBase)
    opened = capture_dialog(monkeypatch)
    run_script(PANEL)
    panel = opened.calls[0][0][0] if opened.calls else None
    return asked, opened, panel


def test_panel_demo_when_font_open_then_shows_the_preview_panel_under_its_key(monkeypatch) -> None:
    asked, opened, panel = panel_demo(monkeypatch)
    assert opened.calls == [((panel, "metrics_panel_demo"), {})] and issubclass(panel, FakePanelBase)
    assert panel.KEY == "metrics_panel_demo" and panel.HEADERS == ("Advance", "Rounded") and asked == []


@pytest.mark.parametrize("width, rounded, changed", [(455, 460, True), (454, 450, True), (450, 450, False), (445.5, 450, True)])
def test_panel_demo_when_planning_a_layer_then_rounds_the_advance_to_ten_and_never_moves_ink(monkeypatch, width, rounded, changed) -> None:
    _, _, panel = panel_demo(monkeypatch)
    plan = panel().planner(None, [])(SimpleNamespace(advanceWidth=width), "Regular")
    assert (plan.dx, plan.width, plan.changed) == (0, rounded, changed)
    assert plan.cells == (f"{width:g}", f"{rounded}")


def test_panel_demo_when_apply_clicked_then_only_a_status_line_changes_and_nothing_is_committed(monkeypatch) -> None:
    import fontlabapp.metrics.panel.model as model

    writers = forbid(monkeypatch, model, "commit", "shift_and_set")
    _, _, panel = panel_demo(monkeypatch)
    window = panel()
    window.build()
    window.apply()
    window.apply_button.setText.assert_called_once_with("Apply (demo: no write)")
    assert window.status.setText.call_args[0][0] == "Demo only: nothing was written. Close the panel."
    assert writers["commit"].calls == [] and writers["shift_and_set"].calls == []
    assert "never writes" in window.subtitle_hint()


def test_panel_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    asked, opened, _ = panel_demo(monkeypatch, package=None)
    assert opened.calls == [] and len(asked) == 1 and "Open a font" in asked[0][2]


def test_panel_demo_when_open_fails_then_warning_names_the_error(monkeypatch) -> None:
    import fontlabapp.core.scripting as scripting

    _, asked = install_host(monkeypatch)
    import fontlabapp.metrics.panel.model as model

    monkeypatch.setattr(model, "panel_type", lambda: FakePanelBase)

    def failing(kind, key):
        raise ValueError("stale window")

    monkeypatch.setattr(scripting, "show_script_dialog", failing)
    run_script(PANEL)
    assert len(asked) == 1 and asked[0][3] == "Warning" and "stale window" in asked[0][2]


# --- Kerning Group Proof Demo ------------------------------------------------------


def group_rows():
    from fontlabapp.kerning.group_proof.model import GlyphGroups

    return (
        GlyphGroups(1, "a", "L_a", "R_a"),
        GlyphGroups(2, "aacute", "L_a", None),
        GlyphGroups(3, "b", "L_b", "R_a"),
        GlyphGroups(4, "agrave", "L_a", "R_a"),
    )


def group_proof_demo(monkeypatch, snapshot=None, error=None):
    from fontlabapp.kerning.group_proof import native

    gui, _ = install_host(monkeypatch)
    calls = []

    def capture(deadline):
        calls.append(deadline)
        if error:
            raise error
        return snapshot

    monkeypatch.setattr(native, "capture", capture)
    opener = forbid(monkeypatch, native, "open_proof")["open_proof"]
    run_script(GROUP_PROOF)
    return gui, calls, opener


def test_group_proof_demo_when_peers_exist_then_lists_both_sides_and_opens_no_tab(monkeypatch) -> None:
    gui, calls, opener = group_proof_demo(monkeypatch, SimpleNamespace(rows=group_rows(), current_id=1))
    title, text, details = shown(gui)
    assert len(calls) == 1 and opener.calls == []
    assert text == "a: 2 left-group and 2 right-group peers. No tab was opened."
    assert details.split("\n") == ["a", "L: aacute agrave", "R: b agrave", ""]


def test_group_proof_demo_when_no_peers_then_says_so(monkeypatch) -> None:
    rows = (group_rows()[0].__class__(1, "a", None, None),)
    gui, _, opener = group_proof_demo(monkeypatch, SimpleNamespace(rows=rows, current_id=1))
    assert shown(gui)[1] == "a has no other left or right kerning-group members." and opener.calls == []


@pytest.mark.parametrize("error", [ValueError("No glyph currently selected."), TimeoutError("late"), RuntimeError("native")])
def test_group_proof_demo_when_capture_fails_then_message_names_the_error(monkeypatch, error) -> None:
    gui, _, opener = group_proof_demo(monkeypatch, error=error)
    assert shown(gui)[1] == str(error) and gui.QMessageBox.call_args[0] == ("main-window",) and opener.calls == []


def test_group_proof_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    run_script(GROUP_PROOF, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Kerning Proofs Demo -----------------------------------------------------------


def proofs_demo(monkeypatch, answers, package=PACKAGE, error=None):
    from fontlabapp.kerning import proofs

    gui, asked = install_host(monkeypatch, answers, package)

    def run(mode):
        run.calls.append(mode)
        if error:
            raise error

    run.calls = []
    monkeypatch.setattr(proofs, "run", run)
    run_script(PROOFS)
    return gui, asked, run


def test_proofs_demo_when_confirmed_then_runs_kernking_after_summarising_all_four(monkeypatch) -> None:
    from fontlabapp.kerning import proofs

    gui, asked, run = proofs_demo(monkeypatch, [YES])
    _, text, details = shown(gui)
    assert text == "The four kerning proofs are ready."
    assert [line.split(":")[0] for line in details.splitlines()] == list(proofs.MODES)
    assert f"kernking: {len(proofs.proof_texts('kernking'))} tab text(s)" in details
    assert [(a[1], a[3], a[4], a[5]) for a in asked] == [("Kerning Proofs Demo", "Question", YES | NO, NO)]
    assert "kernking proof" in asked[0][2] and "on Regular" in asked[0][2]
    assert run.calls == ["kernking"]


def test_proofs_demo_when_declined_then_no_tab_opens(monkeypatch) -> None:
    _, asked, run = proofs_demo(monkeypatch, [NO])
    assert len(asked) == 1 and run.calls == []


def test_proofs_demo_when_no_font_then_shows_summary_and_asks_nothing(monkeypatch) -> None:
    gui, asked, run = proofs_demo(monkeypatch, [], package=None)
    assert shown(gui)[1] == "Open a font to open a proof in tabs." and asked == [] and run.calls == []


@pytest.mark.parametrize("error", [ValueError("font closed"), RuntimeError("no window"), TimeoutError("slow")])
def test_proofs_demo_when_run_fails_then_warning_names_the_error(monkeypatch, error) -> None:
    _, asked, _ = proofs_demo(monkeypatch, [YES, OK], error=error)
    assert len(asked) == 2 and asked[1][3] == "Warning" and str(error) in asked[1][2]


def test_proofs_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, asked = install_host(monkeypatch, [YES])
    run_script(PROOFS, "imported")
    assert asked == [] and gui.QMessageBox.call_count == 0


# --- Kerning Selection Demo --------------------------------------------------------


def test_selection_demo_when_font_open_then_reports_exceptions_and_text_pairs_without_writing(monkeypatch) -> None:
    from fontlabapp.kerning import batch

    gui, _ = install_host(monkeypatch, package=kern_font())
    writers = forbid(monkeypatch, batch, "write_kerning")
    run_script(SELECTION)
    _, text, details = shown(gui)
    assert writers["write_kerning"].calls == []
    assert text == "1 exception(s) in Regular. Nothing was changed."
    lines = details.splitlines()
    assert lines[0] == "Master Regular: 1 exception(s); 1 deletion(s) would be staged."
    assert lines[1] == "  A V = -80 overrides @Aleft V = -60"
    assert "  A V = -80 (explicit)" in lines and "  T o = -300 (explicit)" in lines


def test_selection_demo_when_pair_is_not_explicit_then_marks_it_inherited(monkeypatch) -> None:
    font = kern_font()
    font.pairs = {"Regular": {("A", "V"): -80}, "Bold": {}}
    gui, _ = install_host(monkeypatch, package=font)
    run_script(SELECTION)
    details = shown(gui)[2]
    assert "  A V = -80 (explicit)" in details and "  T o = 0 (inherited or none)" in details


def test_selection_demo_when_no_font_then_says_so(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=None)
    run_script(SELECTION)
    assert shown(gui)[1] == "Open a font first. The report reads its kerning."


def test_selection_demo_when_kerning_unreadable_then_message_names_the_error(monkeypatch) -> None:
    font = kern_font()
    font.pairs = {"Regular": {("@x", "V"): 1}, "Bold": {}}
    font.kerning = lambda master: (_ for _ in ()).throw(ValueError("class table unreadable"))
    gui, _ = install_host(monkeypatch, package=font)
    run_script(SELECTION)
    assert shown(gui)[1] == "The kerning could not be read: class table unreadable"


def test_selection_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=kern_font())
    run_script(SELECTION, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Kerning Symmetry Demo ---------------------------------------------------------


SYMMETRY_TARGETS = {"a.sc", "v.sc", "w.sc", "y.sc", "t.sc", "x.sc", "o.sc", *"AVWYUX80TOovwx:!*|`.-"}


def symmetry_font(targets=SYMMETRY_TARGETS):
    """Every target exists; Regular kerns A V and V A differently; Light Ctr is skipped."""
    pairs = {"Regular": {("A", "V"): -60, ("V", "A"): -40}, "Light Ctr": {("A", "V"): -10}}
    classes = {"L": (["q"], "KernLeft"), "R": (["q"], "KernRight")}
    return FakeFont(pairs, {"Regular": classes, "Light Ctr": classes}, masters=("Regular", "Light Ctr"), glyph_names=targets)


def test_symmetry_demo_when_font_open_then_reports_a_dry_run_and_never_writes(monkeypatch) -> None:
    from fontlabapp.kerning import batch
    from fontlabapp.kerning.symmetry import native

    gui, _ = install_host(monkeypatch, package=symmetry_font())
    writers = forbid(monkeypatch, batch, "write_kerning") | forbid(monkeypatch, native, "write_kerning", "run", "show")
    run_script(SYMMETRY)
    _, text, details = shown(gui)
    assert all(not recorder.calls for recorder in writers.values())
    assert text == "Dry run: 2 key(s) would change. Nothing was written."
    lines = details.splitlines()
    assert lines[0].startswith("Regular: 378 comparisons, 1 mismatches, 2 keys would change.")
    assert any("A / V: before [-60, -40]" in line for line in lines)
    assert lines[-1] == "Skipped masters: Light Ctr"


def test_symmetry_demo_when_a_target_glyph_is_missing_then_message_names_it(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=symmetry_font(SYMMETRY_TARGETS - {"W"}))
    run_script(SYMMETRY)
    assert shown(gui)[1] == "No plan could be made: Missing required symmetry target: W. No targets were omitted."


def test_symmetry_demo_when_capture_times_out_then_message_names_it_and_no_writer_runs(monkeypatch) -> None:
    from fontlabapp.kerning import batch
    import fontlabapp.kerning.symmetry.native as native

    gui, _ = install_host(monkeypatch, package=symmetry_font())
    monkeypatch.setattr(native, "capture", lambda package, check: (_ for _ in ()).throw(TimeoutError("deadline")))
    writers = forbid(monkeypatch, batch, "write_kerning") | forbid(monkeypatch, native, "write_kerning")
    run_script(SYMMETRY)
    assert shown(gui)[1] == "No plan could be made: deadline"
    assert all(not recorder.calls for recorder in writers.values())


def test_symmetry_demo_when_no_font_then_says_so(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=None)
    run_script(SYMMETRY)
    assert shown(gui)[1] == "Open a font first. The dry run reads its kerning."


def test_symmetry_demo_when_check_deadline_passes_then_the_check_raises_timeout(monkeypatch) -> None:
    import fontlabapp.kerning.symmetry.native as native

    gui, _ = install_host(monkeypatch, package=symmetry_font())
    monkeypatch.setattr(native, "capture", lambda package, check: check())
    import itertools
    import time

    clock = itertools.count(0, 100)  # 0, 100, 200, ...: every later call is past the deadline
    monkeypatch.setattr(time, "monotonic", lambda: float(next(clock)))
    run_script(SYMMETRY)
    assert shown(gui)[1] == "No plan could be made: The dry run took too long; nothing was written."


def test_symmetry_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=symmetry_font())
    run_script(SYMMETRY, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Kerning Cutoff Demo -----------------------------------------------------------


def test_cutoff_demo_when_no_font_then_plans_only_the_sample_and_reads_no_kerning(monkeypatch) -> None:
    from fontlabapp.kerning import batch, cutoff

    gui, _ = install_host(monkeypatch, package=None)
    reads = forbid(monkeypatch, batch, "snapshot_kerning", "write_kerning") | forbid(monkeypatch, cutoff, "apply", "run")
    run_script(CUTOFF)
    _, text, details = shown(gui)
    assert all(not recorder.calls for recorder in reads.values())
    assert text == "Sample plan only. Open a font to count its pairs. Nothing was changed."
    assert "Limits: -250 to 100 (inclusive)." in details
    assert "Sample result: {'Regular': {('A', 'V'): -250, ('@O_left', '@O_right'): 100}}" in details
    assert "Regular: 2 of 4 pairs would change" in details


def test_cutoff_demo_when_font_open_then_counts_every_master_from_a_typed_snapshot(monkeypatch) -> None:
    from fontlabapp.kerning import batch, cutoff

    gui, _ = install_host(monkeypatch)
    snapshot = SimpleNamespace(pairs={"Regular": {(("A", "glyphMode"), ("V", "glyphMode")): -400}, "Bold": {(("A", "glyphMode"), ("V", "glyphMode")): -20}})
    read = Recorder(snapshot)
    monkeypatch.setattr(batch, "snapshot_kerning", read)
    writers = forbid(monkeypatch, batch, "write_kerning") | forbid(monkeypatch, cutoff, "apply", "run")
    run_script(CUTOFF)
    _, text, details = shown(gui)
    assert read.calls == [((PACKAGE,), {"typed": True})] and all(not r.calls for r in writers.values())
    assert text == "Planned the cutoff for the current font. Nothing was changed."
    assert details.endswith("Current font:\nRegular: 1 of 1 pairs would change\nBold: 0 of 1 pairs would change")


def test_cutoff_demo_when_font_unreadable_then_message_names_the_error(monkeypatch) -> None:
    from fontlabapp.kerning import batch

    gui, _ = install_host(monkeypatch)

    def failing(package, typed=False):
        raise ValueError("The original font is no longer current; reopen this tool.")

    monkeypatch.setattr(batch, "snapshot_kerning", failing)
    run_script(CUTOFF)
    assert shown(gui)[1] == "The font's kerning could not be read: The original font is no longer current; reopen this tool."


def test_cutoff_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch)
    run_script(CUTOFF, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Kerning Batch Demo ------------------------------------------------------------


def test_batch_demo_when_font_open_then_snapshots_and_checks_pairs_without_writing(monkeypatch) -> None:
    from fontlabapp.kerning import batch

    gui, _ = install_host(monkeypatch, package=kern_font())
    writers = forbid(monkeypatch, batch, "write_kerning")
    run_script(BATCH)
    _, text, details = shown(gui)
    assert writers["write_kerning"].calls == []
    assert text == "Snapshot of 2 master(s). Nothing was written."
    lines = details.splitlines()
    assert lines[:2] == ["Regular: 3 explicit pairs, 1 classes", "Bold: 1 explicit pairs, 0 classes"]
    assert "('A', 'V') -> accepted as (('A', 'glyphMode'), ('V', 'glyphMode'))" in lines
    assert "('no.such.glyph', 'no.such.glyph') -> refused: Unknown glyph: no.such.glyph on Regular" in lines


def test_batch_demo_when_font_has_no_pairs_then_only_the_missing_glyph_check_runs(monkeypatch) -> None:
    font = FakeFont({}, {}, glyph_names=set())
    gui, _ = install_host(monkeypatch, package=font)
    run_script(BATCH)
    lines = shown(gui)[2].splitlines()
    assert lines[:2] == ["Regular: 0 explicit pairs, 0 classes", "Bold: 0 explicit pairs, 0 classes"]
    assert sum("accepted" in line for line in lines) == 0 and sum("refused" in line for line in lines) == 1


def test_batch_demo_when_no_font_then_says_so(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=None)
    run_script(BATCH)
    assert shown(gui)[1] == "Open a font first. The snapshot reads its kerning."


def test_batch_demo_when_kerning_unreadable_then_message_names_the_error(monkeypatch) -> None:
    font = kern_font()
    font.kerning = lambda master: (_ for _ in ()).throw(RuntimeError("native read failed"))
    gui, _ = install_host(monkeypatch, package=font)
    run_script(BATCH)
    assert shown(gui)[1] == "The kerning could not be read: native read failed"


def test_batch_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=kern_font())
    run_script(BATCH, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Kerning Identity Demo ---------------------------------------------------------


def test_identity_demo_when_no_font_then_decodes_samples_in_both_forms(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=None)
    run_script(IDENTITY)
    _, text, details = shown(gui)
    assert text == "Sample pair sides. Open a font to see its pairs too."
    assert "native_side('@O_left') = ('O_left', 'groupMode')" in details
    assert "native_side(('@odd', 'glyphMode')) = ('@odd', 'glyphMode')" in details
    assert "  legacy: ('A', '@O_right')\n  typed: (('A', 'glyphMode'), ('O_right', 'groupMode'))" in details
    assert "legacy: refused: Literal @ glyph names require a typed kerning snapshot" in details
    assert "typed: (('@odd', 'glyphMode'), ('V', 'glyphMode'))" in details


def test_identity_demo_when_font_open_then_lists_its_first_typed_pairs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=kern_font())
    run_script(IDENTITY)
    _, text, details = shown(gui)
    assert text == "Sample pair sides and the pairs of Regular."
    assert "First 5 of 3 explicit pairs of Regular (typed):" in details
    assert "  (('A', 'glyphMode'), ('V', 'glyphMode')) = -80" in details
    assert "  (('Aleft', 'groupMode'), ('V', 'glyphMode')) = -60" in details


def test_identity_demo_when_pairs_unreadable_then_message_names_the_error(monkeypatch) -> None:
    font = kern_font()
    blank = SimpleNamespace(id="", mode="glyphMode")
    font.kerning = lambda master: SimpleNamespace(items=lambda: [(SimpleNamespace(left=blank, right=blank), 1)])
    gui, _ = install_host(monkeypatch, package=font)
    run_script(IDENTITY)
    assert shown(gui)[1] == "The font's pairs could not be read: Kerning pair names must not be blank"


def test_identity_demo_when_native_read_fails_then_message_names_the_error(monkeypatch) -> None:
    font = kern_font()
    font.kerning = lambda master: (_ for _ in ()).throw(RuntimeError("native read failed"))
    gui, _ = install_host(monkeypatch, package=font)
    run_script(IDENTITY)
    assert shown(gui)[1] == "The font's pairs could not be read: native read failed"


def test_identity_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui, _ = install_host(monkeypatch, package=kern_font())
    run_script(IDENTITY, "imported")
    assert gui.QMessageBox.call_count == 0


# --- Kerning Inspect and Kerning Editor Demos ------------------------------------


class FakeCombo:
    def __init__(self):
        self.items, self.currentIndex = [], 0
        self.currentIndexChanged = "master-changed"

    def addItems(self, items):
        self.items += list(items)

    def setCurrentIndex(self, index):
        self.currentIndex = index


class FakeButton:
    def __init__(self, text):
        self.text, self.clicked, self.enabled = text, f"{text}-clicked", True

    def setEnabled(self, enabled):
        self.enabled = enabled


class FakeItem:
    def __init__(self, text):
        self.value, self.flag_calls = text, []

    def text(self):
        return self.value

    def flags(self):
        return 7

    def setFlags(self, flags):
        self.flag_calls.append(flags)


class FakeTable:
    cellChanged = "cell-changed"

    def __init__(self):
        self.rows, self.cells, self.edit_triggers = 0, {}, None

    def setRowCount(self, count):
        self.rows = count

    def setItem(self, row, column, item):
        self.cells[row, column] = item

    def item(self, row, column):
        return self.cells[row, column]

    def setEditTriggers(self, triggers):
        self.edit_triggers = triggers


class FakeShell(FakeWidget):
    """The KerningDialog/KerningEditDialog base: package binding, table, signals."""

    font = None  # each test's shell subclass carries its own font

    def __init__(self, parent, title, key):
        self.parent_arg, self.title, self.key = parent, title, key
        self.package = self.font
        self.masters, self.current_master = list(self.package.masters), self.package.master
        self.subtitle, self.root = MagicMock(), MagicMock()
        self.connections, self.closed, self.invalidated, self.refreshes = [], 0, 0, []

    def make_table(self, headers):
        self.headers = headers
        return FakeTable()

    def _connect(self, signal, slot):
        self.connections.append((signal, slot))

    def close(self):
        self.closed += 1

    def invalidate(self):
        """Like KerningEditDialog.invalidate: disable the mutation buttons."""
        self.invalidated += 1
        for name in ("apply_button", "revert_button", "add_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(False)

    def fire(self, signal, *args):
        for name, slot in self.connections:
            if name == signal:
                slot(*args)


def snapshot_refresh_fake(method):
    """kerning.inspect.ui.snapshot_refresh: invalidate on failure, then re-raise."""

    def wrapped(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception:
            self.invalidate()
            raise

    return wrapped


def editor_refresh_fake(method):
    """kerning.edit.ui.editor_refresh: snapshot before/after; on ANY failure invalidate,
    write the error to the status line and return None (it never re-raises)."""

    def refresh(self, *args, **kwargs):
        from fontlabapp.kerning.batch import ensure_snapshot, snapshot_kerning

        try:
            before = snapshot_kerning(self.package)
            if list(before.masters) != self.masters:
                raise ValueError("Masters changed; reopen this tool.")
            result = method(self, *args, **kwargs)
            ensure_snapshot(self.package, before)
            self._kerning_snapshot, self._snapshot_valid = before, True
            return result
        except Exception as error:  # noqa: BLE001 - mirrors the real decorator
            self.invalidate()
            self.status.setText(f"Error: {error} Use Refresh to scan again.")
            self.slot_error = repr(error)
            return None

    return refresh


def kerning_window_host(monkeypatch, module, base_name, font, package=PACKAGE, shell=FakeShell):
    """Stub the shell module; returns (QtGui, asked, show_script_dialog recorder)."""
    gui, asked = install_host(monkeypatch, package=package, QComboBox=FakeCombo, QPushButton=FakeButton, QTableWidgetItem=FakeItem, QAbstractItemView=SimpleNamespace(DoubleClicked=1, EditKeyPressed=2))
    base = type(base_name, (shell,), {"font": font})
    stub_module(monkeypatch, module, **{base_name: base, "snapshot_refresh": snapshot_refresh_fake, "editor_refresh": editor_refresh_fake})
    return gui, asked, capture_dialog(monkeypatch)


def open_window(monkeypatch, path, module, base_name, font=None):
    gui, asked, opened = kerning_window_host(monkeypatch, module, base_name, font or kern_font())
    run_script(path)
    kind, key = opened.calls[0][0]
    return kind(None), key, gui, asked


def test_inspect_demo_when_font_open_then_shows_the_inspector_under_its_key_with_the_largest_pairs_first(monkeypatch) -> None:
    window, key, gui, asked = open_window(monkeypatch, INSPECT, "fontlabapp.kerning.inspect.ui", "KerningDialog")
    assert key == "kerning_inspect_demo" and window.title == "Kerning Inspect Demo" and asked == []
    assert window.headers == ["Left", "Right", "Value"]
    cells = {key: item.text() for key, item in window.table.cells.items()}
    assert window.table.rows == 3
    assert [cells[row, 0] for row in range(3)] == ["T", "A", "@Aleft"]
    assert [cells[row, 2] for row in range(3)] == ["-300", "-80", "-60"]
    assert window.status.setText.call_args[0][0] == "Regular: 3 explicit pairs, 1 classes; 3 shown. Nothing changed."


def test_inspect_demo_when_master_is_chosen_then_lists_that_master_only(monkeypatch) -> None:
    window, *_ = open_window(monkeypatch, INSPECT, "fontlabapp.kerning.inspect.ui", "KerningDialog")
    assert window.master_box.items == ["Regular", "Bold"] and window.master_box.currentIndex == 0
    window.master_box.currentIndex = 1
    window.fire("master-changed")
    assert window.table.rows == 1 and window.table.item(0, 2).text() == "-90"
    assert window.status.setText.call_args[0][0].startswith("Bold: 1 explicit pairs, 0 classes")


def test_inspect_demo_when_current_master_is_not_first_then_the_box_starts_on_it(monkeypatch) -> None:
    font = kern_font()
    font.master = "Bold"
    window, *_ = open_window(monkeypatch, INSPECT, "fontlabapp.kerning.inspect.ui", "KerningDialog", font)
    assert window.master_box.currentIndex == 1 and window.table.rows == 1


def test_inspect_demo_when_read_fails_then_status_shows_error_and_panel_is_invalidated(monkeypatch) -> None:
    window, *_ = open_window(monkeypatch, INSPECT, "fontlabapp.kerning.inspect.ui", "KerningDialog")
    window.package.kerning = lambda master: (_ for _ in ()).throw(RuntimeError("native read failed"))
    window.fire("master-changed")
    assert window.status.setText.call_args[0][0] == "Error: native read failed" and window.invalidated == 1


def test_inspect_demo_when_buttons_clicked_then_refresh_reads_again_and_close_closes(monkeypatch) -> None:
    window, *_ = open_window(monkeypatch, INSPECT, "fontlabapp.kerning.inspect.ui", "KerningDialog")
    window.package.pairs = {"Regular": {("A", "V"): -10}, "Bold": {}}
    window.fire(window.refresh_button.clicked)
    assert window.table.rows == 1 and window.closed == 0
    window.fire(window.close_button.clicked)
    assert window.closed == 1


def test_inspect_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    gui, asked, opened = kerning_window_host(monkeypatch, "fontlabapp.kerning.inspect.ui", "KerningDialog", kern_font(), package=None)
    run_script(INSPECT)
    assert opened.calls == [] and len(asked) == 1 and "Open a font" in asked[0][2]


def test_inspect_demo_when_show_fails_then_warning_names_the_error(monkeypatch) -> None:
    import fontlabapp.core.scripting as scripting

    gui, asked, _ = kerning_window_host(monkeypatch, "fontlabapp.kerning.inspect.ui", "KerningDialog", kern_font())
    monkeypatch.setattr(scripting, "show_script_dialog", lambda kind, key: (_ for _ in ()).throw(ValueError("busy")))
    run_script(INSPECT)
    assert len(asked) == 1 and asked[0][3] == "Warning" and "busy" in asked[0][2]


class EditorShell(FakeShell):
    """Adds the editor shell's staging API on top of the fake base."""

    def add_refresh(self, footer, callback):
        self.added_refresh = (footer, callback)

    def stage_editor_cell(self, pair, master, text, old):
        from fontlabapp.kerning.edit.model import stage_cell

        if not stage_cell(self.staged, self.errors, (pair, master), text, old):
            return f"“{text}” is not a valid kerning value"
        return None


def open_editor(monkeypatch, font=None):
    gui, asked, opened = kerning_window_host(monkeypatch, "fontlabapp.kerning.edit.ui", "KerningEditDialog", font or kern_font(), shell=EditorShell)
    run_script(EDITOR)
    kind, key = opened.calls[0][0]
    return kind(None), key, asked


def test_editor_demo_when_font_open_then_shows_editor_with_values_editable_and_ids_locked(monkeypatch) -> None:
    window, key, asked = open_editor(monkeypatch)
    assert key == "kerning_editor_demo" and window.title == "Kerning Editor Demo" and asked == []
    assert window.table.edit_triggers == 3
    assert window.table.rows == 3 and window.order == [("T", "o"), ("A", "V"), ("@Aleft", "V")]
    assert window.table.item(0, 0).flag_calls == [6] and window.table.item(0, 1).flag_calls == [6]
    assert window.table.item(0, 2).flag_calls == [], "only the value column stays editable"
    assert window.status.setText.call_args[0][0] == "Regular: 3 explicit pairs; 3 shown. No edits staged."
    assert window.added_refresh[1] is not None


def test_editor_demo_when_value_edited_then_stages_it_and_reports_none_applied(monkeypatch) -> None:
    from fontlabapp.kerning import batch

    writers = forbid(monkeypatch, batch, "write_kerning")
    window, _, _ = open_editor(monkeypatch)
    window.table.item(0, 2).value = "-250"
    window.fire("cell-changed", 0, 2)
    assert window.staged == {(("T", "o"), "Regular"): -250}
    assert window.status.setText.call_args[0][0] == "1 edit(s) staged, none applied. Revert discards them."
    assert writers["write_kerning"].calls == []


def test_editor_demo_when_value_returns_to_original_then_the_edit_is_unstaged(monkeypatch) -> None:
    window, _, _ = open_editor(monkeypatch)
    for text in ("-250", "-300"):
        window.table.item(0, 2).value = text
        window.fire("cell-changed", 0, 2)
    assert window.staged == {}


def test_editor_demo_when_value_is_not_a_number_then_status_shows_the_problem_and_stages_nothing(monkeypatch) -> None:
    window, _, _ = open_editor(monkeypatch)
    window.table.item(1, 2).value = "wide"
    window.fire("cell-changed", 1, 2)
    assert window.staged == {} and window.errors == {(("A", "V"), "Regular"): "wide"}
    assert window.status.setText.call_args[0][0] == "“wide” is not a valid kerning value. 0 edit(s) staged, none applied. Revert discards them."


@pytest.mark.parametrize("row, column", [(0, 0), (0, 1), (99, 2)])
def test_editor_demo_when_other_cell_or_missing_row_changes_then_nothing_is_staged(monkeypatch, row, column) -> None:
    window, _, _ = open_editor(monkeypatch)
    calls = window.status.setText.call_count
    window.fire("cell-changed", row, column)
    assert window.staged == {} and window.status.setText.call_count == calls


def test_editor_demo_when_filling_then_cell_signals_are_ignored(monkeypatch) -> None:
    window, _, _ = open_editor(monkeypatch)
    window.filling = True
    window.table.item(0, 2).value = "-1"
    window.fire("cell-changed", 0, 2)
    assert window.staged == {}


def test_editor_demo_when_reverted_then_staged_edits_are_dropped_and_the_font_is_read_again(monkeypatch) -> None:
    window, _, _ = open_editor(monkeypatch)
    window.table.item(0, 2).value = "-250"
    window.fire("cell-changed", 0, 2)
    window.fire(window.revert_button.clicked)
    assert window.staged == {} and window.table.item(0, 2).text() == "-300"
    assert window.status.setText.call_args[0][0].endswith("No edits staged.")
    assert not hasattr(window, "apply_button"), "the editor offers no Apply control"


def test_editor_demo_when_master_changes_then_lists_that_master_and_drops_staging(monkeypatch) -> None:
    window, _, _ = open_editor(monkeypatch)
    window.master_box.currentIndex = 1
    window.fire("master-changed")
    assert window.order == [("A", "V")] and window.master() == "Bold" and window.staged == {}


def test_editor_demo_when_read_fails_then_status_shows_error_buttons_disable_and_a_good_refresh_recovers(monkeypatch) -> None:
    window, _, _ = open_editor(monkeypatch)
    assert window.revert_button.enabled is True
    window.package.kerning = lambda master: (_ for _ in ()).throw(RuntimeError("native read failed"))
    window.refresh()  # the real editor_refresh never raises
    assert window.invalidated == 1 and window.revert_button.enabled is False
    assert window.status.setText.call_args[0][0] == "Error: native read failed Use Refresh to scan again."
    del window.package.kerning
    window.fire(window.revert_button.clicked)
    assert window.revert_button.enabled is True and window.table.rows == 3
    assert window.status.setText.call_args[0][0].endswith("No edits staged.")


def test_editor_demo_when_close_clicked_then_closes_the_panel(monkeypatch) -> None:
    window, _, _ = open_editor(monkeypatch)
    window.fire(window.close_button.clicked)
    assert window.closed == 1


def test_editor_demo_when_current_master_is_not_first_then_the_box_starts_on_it(monkeypatch) -> None:
    font = kern_font()
    font.master = "Bold"
    window, _, _ = open_editor(monkeypatch, font)
    assert window.master_box.currentIndex == 1 and window.order == [("A", "V")]


def test_editor_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    gui, asked, opened = kerning_window_host(monkeypatch, "fontlabapp.kerning.edit.ui", "KerningEditDialog", kern_font(), package=None)
    run_script(EDITOR)
    assert opened.calls == [] and len(asked) == 1 and "Open a font" in asked[0][2]


def test_editor_demo_when_show_fails_then_warning_names_the_error(monkeypatch) -> None:
    import fontlabapp.core.scripting as scripting

    gui, asked, _ = kerning_window_host(monkeypatch, "fontlabapp.kerning.edit.ui", "KerningEditDialog", kern_font())
    monkeypatch.setattr(scripting, "show_script_dialog", lambda kind, key: (_ for _ in ()).throw(RuntimeError("old window stuck")))
    run_script(EDITOR)
    assert len(asked) == 1 and asked[0][3] == "Warning" and "old window stuck" in asked[0][2]
