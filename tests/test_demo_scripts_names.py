# this_file: tests/test_demo_scripts_names.py
"""Offline runs of the ten Scripts/Names demos (Issue 208, Task 2).

Each demo runs through runpy as ``__main__`` (entry points and arguments are
asserted) and as an imported name (nothing may run). The real ``fontlabapp``
modules stay in use: window entry points are replaced by recorders on the real
module, and only ``PythonQt`` and ``fontlab`` are stubbed. Offline results are
not native FontLab acceptance.
"""

import importlib
import json
from types import SimpleNamespace

import pytest
from _demo_support import Recorder, qt_namespace, run_script, script_path, stub_module

PACKAGE = SimpleNamespace(isNull=False, id=3, fgId=77)

# (script title, [(module, entry point) in the order the demo calls them])
WINDOWS = [
    ("Glyph Map Demo", [("character_map.model", "show"), ("character_map.model", "show_official")]),
    ("Glyph Tree Demo", [("tree.model", "show_outline"), ("tree.model", "show_tree")]),
    ("Editable Glyph Tree Demo", [("tree.editable.model", "show_outline"), ("tree.editable.model", "show_tree")]),
    ("Glyph Calendar Demo", [("calendar.model", "show"), ("calendar.model", "show_official")]),
    ("Glyph Catalog Demo", [("catalog.model", "show_custom"), ("catalog.model", "show_official_custom")]),
    (
        "Glyph Name Entry Demo",
        [("completion.model", "show"), ("completion.model", "show_official"), ("pattern", "show")],
    ),
]
NAMES = script_path("Names", "Glyph Names Report Demo")
COMMON = script_path("Names", "Common Glyphs Demo")
CASE = script_path("Names", "Case Coverage Demo")
CREATION = script_path("Names", "Glyph Creation Explained Demo")


def install_host(monkeypatch, package=PACKAGE):
    """Stub PythonQt (recorded message boxes) and the fontlab package lookup."""
    qt = qt_namespace()
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(
        monkeypatch,
        "fontlab",
        MainWindow=lambda: "main-window",
        flWorkspace=SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=package)),
    )
    return qt.QtGui


def shown(gui) -> tuple[str, str, str]:
    """(title, text, details) of the one modal message box the demo ran."""
    assert gui.QMessageBox.call_count == 1, "exactly one message box expected"
    assert gui.QMessageBox.call_args[0] == ("main-window",), "box parents to the main window"
    box = gui.QMessageBox.return_value
    box.exec.assert_called_once_with()
    details = box.setDetailedText.call_args[0][0] if box.setDetailedText.called else ""
    return box.setText.call_args[0][0], box.setInformativeText.call_args[0][0], details


def record_entry_points(monkeypatch, entries) -> list[str]:
    """Replace each real entry point with a recorder; return the shared call log."""
    log: list[str] = []
    for module, name in entries:
        target = importlib.import_module(f"fontlabapp.glyphs.{module}")
        monkeypatch.setattr(target, name, lambda module=module, name=name: log.append(f"{module}.{name}"))
    return log


# --- the six window demos --------------------------------------------------------


@pytest.mark.parametrize("title,entries", WINDOWS, ids=[title for title, _ in WINDOWS])
def test_window_demo_when_font_open_then_calls_every_entry_point_in_order(monkeypatch, title, entries) -> None:
    gui = install_host(monkeypatch)
    log = record_entry_points(monkeypatch, entries)
    run_script(script_path("Names", title))
    assert log == [f"{module}.{name}" for module, name in entries]
    assert gui.QMessageBox.call_count == 0, "no message when the font is open"


@pytest.mark.parametrize("title,entries", WINDOWS, ids=[title for title, _ in WINDOWS])
def test_window_demo_when_first_entry_point_raises_then_the_others_still_open_and_the_error_is_shown(
    monkeypatch, title, entries
) -> None:
    gui = install_host(monkeypatch)
    log = record_entry_points(monkeypatch, entries)
    first = importlib.import_module(f"fontlabapp.glyphs.{entries[0][0]}")

    def refuse() -> None:
        raise RuntimeError("no main UI thread")

    monkeypatch.setattr(first, entries[0][1], refuse)
    run_script(script_path("Names", title))
    assert log == [f"{module}.{name}" for module, name in entries[1:]], "later panels must still open"
    text, informative, _ = shown(gui)
    assert (text, informative) == (title, f"{entries[0][1]} did not open: no main UI thread")


@pytest.mark.parametrize("title,entries", WINDOWS, ids=[title for title, _ in WINDOWS])
def test_window_demo_when_no_font_then_opens_nothing_and_says_so(monkeypatch, title, entries) -> None:
    gui = install_host(monkeypatch, package=None)
    log = record_entry_points(monkeypatch, entries)
    run_script(script_path("Names", title))
    assert log == [], "no panel may open without a font"
    assert shown(gui) == (title, "Open a font first. These panels read the current font.", "")


@pytest.mark.parametrize("title,entries", WINDOWS, ids=[title for title, _ in WINDOWS])
def test_window_demo_when_imported_then_nothing_runs(monkeypatch, title, entries) -> None:
    gui = install_host(monkeypatch)
    log = record_entry_points(monkeypatch, entries)
    names = run_script(script_path("Names", title), "imported")
    assert log == [] and gui.QMessageBox.call_count == 0 and callable(names["main"])


def test_notify_when_called_then_sets_no_detail_text(monkeypatch) -> None:
    gui = install_host(monkeypatch)
    run_script(script_path("Names", "Glyph Map Demo"), "imported")["notify"]("T", "body")
    assert gui.QMessageBox.return_value.setDetailedText.called is False
    assert shown(gui) == ("T", "body", "")


# --- Common Glyphs Demo ----------------------------------------------------------


def test_common_glyphs_when_main_then_shows_panel_with_unknown_production_metadata(monkeypatch) -> None:
    from fontlabapp.glyphs.common import controller
    from fontlabapp.glyphs.common.model import Production

    gui = install_host(monkeypatch)
    show = Recorder()
    monkeypatch.setattr(controller, "show", show)
    run_script(COMMON)
    ((args, kwargs),) = show.calls
    assert kwargs == {} and len(args) == 1
    assert args[0]("A", checkpoint=lambda: None) == Production(None, "unknown")
    assert gui.QMessageBox.call_count == 0


@pytest.mark.parametrize("error", [ValueError("Open a font."), TimeoutError("too slow")])
def test_common_glyphs_when_refused_then_message_box_carries_the_reason(monkeypatch, error) -> None:
    from fontlabapp.glyphs.common import controller

    gui = install_host(monkeypatch)

    def refuse(metadata):
        raise error

    monkeypatch.setattr(controller, "show", refuse)
    run_script(COMMON)
    assert shown(gui) == ("Common Glyphs Demo", "The report could not be built: " + str(error), "")


def test_common_glyphs_when_imported_then_nothing_runs(monkeypatch) -> None:
    from fontlabapp.glyphs.common import controller

    show = Recorder()
    monkeypatch.setattr(controller, "show", show)
    assert callable(run_script(COMMON, "imported")["main"]) and show.calls == []


# --- Case Coverage Demo ----------------------------------------------------------


def case_report():
    """A real case-coverage report: B lacks a lowercase partner, A has one."""
    from fontlabapp.glyphs.case_coverage.model import GlyphFact, Options, analyze

    facts = [GlyphFact("A", (65,), True, "Uppercase"), GlyphFact("a", (97,), True, "Lowercase"),
             GlyphFact("B", (66,), True, "Uppercase")]
    return analyze(facts, {}, Options())


def smallcap_report():
    """A real small-cap report with a lowercase glyph that has no small cap."""
    from fontlabapp.glyphs.smallcaps.model import GlyphFact, analyze

    report = analyze([GlyphFact("a", True, "lower", "a"), GlyphFact("A", True, "upper", "A")])
    return {**report, "family": "Demo Sans", "master": "Regular"}


def test_case_coverage_when_main_then_runs_reports_without_proof_and_shows_summary(monkeypatch) -> None:
    from fontlabapp.glyphs.case_coverage import controller
    from fontlabapp.glyphs.case_coverage.capture import FontReport, Snapshot
    from fontlabapp.glyphs.case_coverage.model import Options
    from fontlabapp.glyphs.smallcaps import capture

    gui = install_host(monkeypatch)
    snapshot = Snapshot(3, (FontReport(3, 77, "Demo Sans Regular", "Regular", case_report()),))
    run = Recorder(snapshot)
    monkeypatch.setattr(controller, "run", run)
    monkeypatch.setattr(capture, "current_report", smallcap_report)
    names = run_script(CASE)
    ((args, kwargs),) = run.calls
    assert args == (Options(allFonts=False), names["metadata"], names["preferred"]), "current font only"
    assert list(kwargs) == ["proof"] and kwargs["proof"](snapshot, Options()) is None, "proof views stay closed"
    _, text, details = shown(gui)
    assert text == "Case coverage and small caps read for the current font."
    assert "Case coverage: Demo Sans Regular (Regular)" in details
    assert "matched: 2" in details and "missing: 1" in details and "needs attention: B" in details
    assert "Small caps: Demo Sans (Regular)" in details
    assert "lower: 1" in details and "missing lowercase smallcaps: 1" in details


@pytest.mark.parametrize("error", [ValueError("Open a font."), TimeoutError("too slow")])
def test_case_coverage_when_report_fails_then_message_box_says_why(monkeypatch, error) -> None:
    from fontlabapp.glyphs.case_coverage import controller

    gui = install_host(monkeypatch)

    def refuse(*args, **kwargs):
        raise error

    monkeypatch.setattr(controller, "run", refuse)
    run_script(CASE)
    assert shown(gui) == ("Case Coverage Demo", "The reports could not be built: " + str(error), "")


def test_case_coverage_when_report_is_clear_then_summary_says_all_clear() -> None:
    from fontlabapp.glyphs.case_coverage.model import GlyphFact, Options, analyze

    clear = analyze([GlyphFact("A", (65,), True, "Uppercase"), GlyphFact("a", (97,), True, "Lowercase")], {}, Options())
    assert "all clear" in run_script(CASE, "imported")["case_lines"](clear)


@pytest.mark.parametrize(
    "codes,expected",
    [((), (None, None)), ((65,), ("Uppercase", "A")), ((97,), ("Lowercase", "a")), ((0x2206,), ("Other", "∆"))],
)
def test_case_coverage_metadata_when_codes_vary_then_categorises_first_scalar(codes, expected) -> None:
    names = run_script(CASE, "imported")
    assert names["metadata"]("x", codes) == expected
    assert names["preferred"]("A") is None


def test_case_coverage_when_imported_then_nothing_runs(monkeypatch) -> None:
    from fontlabapp.glyphs.case_coverage import controller

    run = Recorder()
    monkeypatch.setattr(controller, "run", run)
    run_script(CASE, "imported")
    assert run.calls == []


# --- Glyph Names Report Demo -----------------------------------------------------


def entry(glyph_id: int, codes: list[int]):
    """A names.model Entry stand-in: a FontGate record and a FontLab glyph."""
    return SimpleNamespace(record=SimpleNamespace(id=glyph_id, unicodes=codes), glyph=SimpleNamespace(id=glyph_id + 100))


def names_stubs(monkeypatch, *, package=PACKAGE, selected=("A",), free=(), entries=None):
    """Patch the real names, unreferenced and scripting readers; return their recorders."""
    from fontlabapp.core import scripting
    from fontlabapp.glyphs import unreferenced
    from fontlabapp.glyphs.names import model

    gui = install_host(monkeypatch, package=package)
    entries = {"A": entry(1, [65]), "Aalt": entry(2, [65]), "b": entry(3, [])} if entries is None else entries
    scan = Recorder(SimpleNamespace(entries=entries))
    unref = Recorder(list(free))
    monkeypatch.setattr(model, "scan", scan)
    monkeypatch.setattr(unreferenced, "unreferenced", unref)
    monkeypatch.setattr(scripting, "names_selected_names", lambda: list(selected))
    return gui, scan, unref


def test_names_report_when_main_then_reads_four_sections_and_selects_nothing(monkeypatch) -> None:
    gui, scan, unref = names_stubs(monkeypatch, free=[("b", "alternate of a?"), ("c", "")])
    from fontlabapp.core import scripting

    selected_writes = Recorder()
    monkeypatch.setattr(scripting, "select_glyphs", selected_writes)
    selected_writes = selected_writes.calls
    run_script(NAMES)
    assert scan.calls == [((), {})] and unref.calls == [((PACKAGE,), {})]
    _, text, details = shown(gui)
    assert text == "3 glyphs read."
    assert "Glyphs: 3" in details
    assert "U+0041: A, Aalt (keeps A)" in details
    assert "Unreferenced glyphs:\nb (alternate of a?), c" in details
    assert "Current selection:\nA" in details
    assert "the tool would add C, D" in details
    assert selected_writes == [], "the demo must never select glyphs"


def test_names_report_when_nothing_to_report_then_each_section_says_none(monkeypatch) -> None:
    gui, _, _ = names_stubs(monkeypatch, selected=(), entries={"A": entry(1, [65])})
    run_script(NAMES)
    details = shown(gui)[2]
    assert "Duplicate Unicodes:\nnone" in details and "Unreferenced glyphs:\nnone" in details
    assert "Current selection:\nnone" in details


def test_names_report_when_no_font_then_reads_nothing_and_says_so(monkeypatch) -> None:
    gui, scan, unref = names_stubs(monkeypatch, package=None)
    run_script(NAMES)
    assert scan.calls == [] and unref.calls == []
    assert shown(gui) == (
        "Glyph Names Report Demo", "Open a font first. This report reads the current font.", "")


def test_names_report_when_scan_refuses_then_only_the_duplicates_section_errors(monkeypatch) -> None:
    from fontlabapp.glyphs.names import model

    gui, _, unref = names_stubs(monkeypatch, free=[("c", "")])

    def refuse():
        raise ValueError("Native glyph mapping is inconsistent; reload the font.")

    monkeypatch.setattr(model, "scan", refuse)
    run_script(NAMES)
    _, text, details = shown(gui)
    assert text == "The glyph scan failed; the other sections follow."
    assert "Glyphs: unavailable" in details
    assert "Duplicate Unicodes:\nerror: Native glyph mapping is inconsistent; reload the font." in details
    assert "Unreferenced glyphs:\nc" in details and "Current selection:\nA" in details
    assert "the tool would add C, D" in details, "the selection planner still runs"
    assert unref.calls == [((PACKAGE,), {})]


def test_names_report_preview_when_list_is_long_then_counts_the_rest() -> None:
    preview = run_script(NAMES, "imported")["preview"]
    assert preview([]) == "none" and preview(["a", "b"]) == "a, b"
    long = [f"g{n}" for n in range(23)]
    assert preview(long).endswith("g19, ... (3 more)") and "g20" not in preview(long)


def test_names_report_when_imported_then_nothing_runs(monkeypatch) -> None:
    _, scan, _ = names_stubs(monkeypatch)
    run_script(NAMES, "imported")
    assert scan.calls == []


# --- Glyph Creation Explained Demo -----------------------------------------------


def test_creation_demo_when_main_then_explains_sample_plan_and_creates_nothing(monkeypatch) -> None:
    from fontlabapp.glyphs import creation

    gui = install_host(monkeypatch)
    forbidden = Recorder()
    monkeypatch.setattr(creation, "create_glyphs", forbidden)
    run_script(CREATION)
    assert forbidden.calls == [], "the sample plan must never be executed"
    _, text, details = shown(gui)
    assert text == "Sample plan for one new glyph. Nothing was created."
    assert "Master width 450.5 rounds half up to 451" in details
    data = json.loads(details.split("call:\n", 1)[1].split("\n\nDotted", 1)[0])
    assert data == {
        "name": "h.sc",
        "layers": [{"name": "Regular", "advanceWidth": 451, "elements": [
            {"component": {"glyphName": "h"}, "transform": {"xOffset": 0.0, "yOffset": 0.0}}]}],
    }
    assert "Dotted segments of h.sc: sc" in details
    assert creation.UNDO_TEXT in details and creation.CREATE_UNDO_TEXT in details and creation.REBUILD_LABEL in details
    assert "Example note: may rebuild auto eacute.sc, aacute.sc…" in details


def test_creation_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    gui = install_host(monkeypatch)
    run_script(CREATION, "imported")
    assert gui.QMessageBox.call_count == 0


@pytest.mark.parametrize("error", [ValueError("bad features"), TimeoutError("slow")])
def test_names_report_when_one_section_fails_then_keeps_the_others_and_names_the_error(monkeypatch, error) -> None:
    from fontlabapp.glyphs import unreferenced

    gui, _, _ = names_stubs(monkeypatch)

    def fail(package):
        raise error

    monkeypatch.setattr(unreferenced, "unreferenced", fail)
    run_script(NAMES)
    _, text, details = shown(gui)
    assert text == "3 glyphs read."
    assert "Duplicate Unicodes:\nU+0041: A, Aalt (keeps A)" in details, "earlier section kept"
    assert f"Unreferenced glyphs:\nerror: {error}" in details
    assert "Current selection:\nA" in details and "the tool would add C, D" in details, "later sections kept"
