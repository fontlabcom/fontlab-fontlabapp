# this_file: tests/test_studio_font_audit.py
"""Font Audit (Phase D A8) and the shared ``studios._records`` catalogue read.

One shared fake font serves every test. Its objects fail the test on any
attribute write after construction, and every public ``core.history``
callable fails the test when called, so the studio is proven read-only. The
absorbed scripts' pure functions (``_font_audit_originals``) and the three
Font Info ``glyph_records`` copies (``_font_info_records``) are extracted
verbatim from Scriptmix and run against the same fake: Font Audit must give
the same values.
"""

import hashlib
import importlib
import sys
import unicodedata
from types import SimpleNamespace as NS

import pytest
from _font_audit_originals import ORIGINALS
from _font_info_records import COPIES
from _studio_qt import studio_qt  # noqa: F401 - fixture

TABS = "fontlabapp.studios.font_audit.tabs"
MASTERS = ("Regular", "Bold")


@pytest.fixture(autouse=True)
def drop_studio_modules():
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


@pytest.fixture(autouse=True)
def no_history(monkeypatch):
    """Any history call fails the test (Font Audit never opens a history scope)."""
    from fontlabapp.core import history

    def refuse(*args, **kwargs):
        raise AssertionError("Font Audit touched history")

    for name in [n for n in dir(history) if not n.startswith("_") and callable(getattr(history, n))]:
        monkeypatch.setattr(history, name, refuse)


# The shared fake font ---------------------------------------------------------
class Frozen:
    """Fails the test on any attribute write once built."""

    def freeze(self):
        object.__setattr__(self, "_frozen", True)
        return self

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AssertionError(f"Font Audit wrote {type(self).__name__}.{name}")
        object.__setattr__(self, name, value)


class Layer(Frozen):
    def __init__(self, width, contours, components=()):
        self.advanceWidth = width
        self._contours = contours
        self.shapes = [NS(shapeData=None)] + [NS(shapeData=NS(componentGlyph=b)) for b in components] + [
            NS(shapeData=NS(componentGlyph=""))]
        self.freeze()

    def getContours(self):
        return [object()] * self._contours


class Glyph(Frozen):
    def __init__(self, name, codes, layers, mark=0, note=None):
        self.name = name
        self.unicodes = list(codes)
        self.layers = layers
        self.mark = mark
        self.note = note
        self.fgGlyph = NS(unicodes=list(codes))  # only the original copies read it
        self.freeze()

    def findLayer(self, master):
        return self.layers.get(master)


def L(width, contours, components=()):
    return Layer(width, contours, components)


SPECS = [  # name, codes, {master: layer}, mark, note
    ("A", [0x41], {"Regular": L(600.123, 2), "Bold": L(650, 2)}, 5, " check "),
    ("Aacute", [0xC1], {"Regular": L(600, 0, ("A", "acutecomb")), "Bold": L(650, 0, ("A", "acutecomb"))}, 0, ""),
    ("a", [0x61, 0xFF41], {"Regular": L(500, 2), "Bold": L(520, 2)}, 5, None),
    ("a.sc", [], {"Regular": L(480, 1)}, 1005, None),
    ("b.ss01", [], {"Regular": L(500, 0), "Bold": L(520, 1)}, 400, None),
    ("A.alt", [0x41], {"Regular": L(600, 1), "Bold": L(600, 1, ("acutecomb",))}, 0, None),
    ("space", [0x20], {"Regular": L(250, 0), "Bold": L(250, 0)}, 0, None),
    ("tag", [0xE0041], {"Regular": L(0, 0), "Bold": L(0, 0)}, 0, None),
    ("acutecomb", [0x301], {"Regular": L(0, 1), "Bold": L(0, 1)}, 200, "x"),
]


class Package(Frozen):
    def __init__(self, glyphs, pid=7, skip=("a.sc",)):
        self.id = pid
        self.isNull = False
        self.masters = list(MASTERS)
        self.master = "Bold"
        self.defaultMaster = "Regular"
        self.upm = 1000.0
        self.info = NS(familyName="Fake Sans")
        self.packageLib = {"public.skipExportGlyphs": list(skip)}
        self._glyphs = {g.name: g for g in glyphs}
        self.freeze()

    def findName(self, name):
        return self._glyphs.get(name)

    def kerning(self, master):
        return {("A", "V"): -50, ("V", "A"): -40} if master == "Regular" else {("A", "V"): -60}


class World:
    """The live objects the core accessors read: workspace, CurrentFont, FL.fl."""

    def __init__(self, specs=SPECS, *, legacy=None, missing=(), selected=()):
        glyphs = [Glyph(*spec) for spec in specs]
        self.package = Package([g for g in glyphs if g.name not in missing])
        self.current = self.package
        names = [g.name for g in glyphs] if legacy is None else list(legacy)
        self.legacy = [NS(name=n) for n in names]
        self.selected = set(selected)
        self.selections = []
        self.font = NS(glyphs=[NS(name=g.name, unicodes=list(g.unicodes), mark=g.mark) for g in glyphs])
        world = self

        class FLFont(list):
            pass

        self.fl = NS(font=FLFont(self.legacy), Selected=lambda i: world.legacy[i].name in world.selected)
        self.fontlab = NS(
            CurrentFont=lambda: world.font,
            flWorkspace=NS(instance=lambda: NS(currentPackage=world.current)),
            FontMetrics=lambda package, master: NS(
                ascender=750.0 if master == "Regular" else 760.5, capsHeight=700, xHeight=500.25, descender=-250),
        )

    def native(self, name):
        return {"FL": NS(fl=self.fl), "fontlab": self.fontlab}[name]


@pytest.fixture
def world(monkeypatch):
    from fontlabapp.core import scripting

    w = World()
    monkeypatch.setattr(scripting, "_native", w.native)
    monkeypatch.setitem(sys.modules, "fontlab", w.fontlab)
    return w


def _original(title, **names):
    """Exec one verbatim original with ``fontlab`` faked; return its namespace."""
    _functions, digest, source = ORIGINALS[title]
    assert hashlib.sha256(source.encode()).hexdigest() == digest
    namespace = {"Any": object, "unicodedata": unicodedata, **names}
    exec("import csv, io, pathlib\n" + source, namespace)  # noqa: S102 - verbatim test fixture
    return namespace


def _copy(title, world):
    lineno, digest, source = COPIES[title]
    assert hashlib.sha256(source.encode()).hexdigest() == digest and lineno in (36, 47, 48)
    from fontlabapp.core.scripting import current_package

    namespace = {"Any": object, "ap": NS(FL=NS(fl=world.fl)), "current_package": current_package}
    exec(source, namespace)  # noqa: S102 - verbatim test fixture
    return namespace["glyph_records"]


# _records ---------------------------------------------------------------------
@pytest.mark.parametrize("title", sorted(COPIES))
def test_records_when_same_font_then_equal_to_each_font_info_copy(world, title):
    from fontlabapp.studios import _records

    expected = _copy(title, world)(world.package)
    assert _records.glyph_records(world.package) == expected
    assert ("a", [0x61, 0xFF41]) in expected and ("a.sc", []) in expected


def test_records_copies_when_compared_then_one_body():
    assert len({source for _line, _digest, source in COPIES.values()}) == 1


@pytest.mark.parametrize("title", sorted(COPIES))
def test_records_when_other_font_current_then_same_refusal(world, title):
    from fontlabapp.studios import _records

    world.current = Package([], pid=99)
    with pytest.raises(ValueError, match="Activate the original font") as copy_error:
        _copy(title, world)(world.package)
    with pytest.raises(ValueError) as error:
        _records.glyph_records(world.package)
    assert str(error.value) == str(copy_error.value) == _records.STALE
    world.current = None
    with pytest.raises(ValueError, match="Activate the original font"):
        _records.glyph_records(world.package)


def test_records_when_legacy_order_differs_then_refused(monkeypatch):
    from fontlabapp.core import scripting
    from fontlabapp.studios import _records

    w = World(legacy=[s[0] for s in reversed(SPECS)])
    monkeypatch.setattr(scripting, "_native", w.native)
    with pytest.raises(ValueError, match="encoding order changed"):
        _records.glyph_records(w.package)


def test_records_legacy_names_when_no_font_then_empty(world):
    from fontlabapp.core import scripting

    assert scripting.names_legacy_font() == [s[0] for s in SPECS]
    world.fl.font = None
    assert scripting.names_legacy_font() == []


def test_catalogue_when_read_then_every_fact_without_fgglyph(world):
    from fontlabapp.studios import _records

    for glyph in world.package._glyphs.values():
        object.__setattr__(glyph, "fgGlyph", property(lambda s: (_ for _ in ()).throw(AssertionError)))
    cat = _records.catalogue(world.package)
    assert (cat.package_id, cat.family, cat.upm, cat.master, cat.masters) == (7, "Fake Sans", 1000, "Bold", MASTERS)
    by = cat.by_name()
    assert [r.name for r in cat.records] == [s[0] for s in SPECS]
    assert by["A"].widths == (600.123, 650.0) and by["A"].contours == (2, 2) and by["A"].mark == 5
    assert by["Aacute"].composite and by["Aacute"].components == ("A", "acutecomb")
    assert by["A.alt"].composite and by["A.alt"].components == ("acutecomb",)
    assert by["a.sc"].widths == (480.0, None) and by["a.sc"].current_contours is None and not by["a.sc"].export
    assert by["a"].unicodes == (0x61, 0xFF41) and by["a"].export
    assert by["acutecomb"].note == "x" and by["space"].note == ""


def test_catalogue_when_glyph_missing_then_record_not_found(monkeypatch):
    from fontlabapp.core import scripting
    from fontlabapp.studios import _records

    w = World(missing=("tag",))
    monkeypatch.setattr(scripting, "_native", w.native)
    record = _records.catalogue(w.package).by_name()["tag"]
    assert not record.found and record.unicodes == (0xE0041,) and record.widths == ()


def test_skipped_when_malformed_then_refused():
    from fontlabapp.studios import _records

    assert _records.skipped(NS(packageLib={})) == frozenset()
    with pytest.raises(ValueError, match="must be a list"):
        _records.skipped(NS(packageLib={"public.skipExportGlyphs": "a"}))


# model parity against the verbatim originals ---------------------------------
@pytest.fixture
def cat(world):
    from fontlabapp.studios import _records

    return _records.catalogue(world.package)


def test_overview_when_compared_then_original_cards_and_rows(world, cat):
    from fontlabapp.studios.font_audit import model, session

    original = _original("Font Overview", fontlab=world.fontlab)
    cards, rows = original["overview"](world.package)
    assert model.overview_cards(cat) == cards
    assert list(cards) == ["Glyphs", "Encoded glyphs", "Code points", "Masters", "Composites", "Empty on Bold",
                           "Marked", "With notes"]
    assert cards["Empty on Bold"] == 2 and cards["Composites"] == 2 and cards["With notes"] == 2
    assert session.font_metrics(world.package) == rows
    assert model.metric_text(760.5) == "760.5" and model.metric_text(700) == "700"
    assert model.subtitle(cat) == "Fake Sans · 1000 units per em · current master Bold"


def test_glyph_table_when_compared_then_original_rows_and_csv(world, cat, tmp_path):
    from fontlabapp.studios.font_audit import model

    original = _original("Glyph Table CSV")
    names = [s[0] for s in SPECS] + ["nothere"]
    header, rows = original["table"](world.package, names)
    assert model.table(cat, names) == (header, rows)
    assert header == ["glyph", "unicode", "width Regular", "width Bold", "contours", "components"]
    assert rows[0][2] == 600.12 and rows[3][3] == "" and rows[2][1] == "0061 FF41"
    assert model.to_csv(header, rows) == original["to_csv"](header, rows)
    ours, theirs = tmp_path / "ours.csv", tmp_path / "theirs.csv"
    assert model.write_csv(ours, header, rows) == original["write_csv"](theirs, header, rows)
    data = ours.read_bytes()
    assert data == theirs.read_bytes() and data.startswith(b"\xef\xbb\xbf") and b"\r" not in data
    assert model.table_subtitle(cat, rows).startswith("9 glyphs · widths for 2 masters · contours and components on Bold")


@pytest.mark.parametrize("show_all", [False, True])
def test_unicode_when_compared_then_original_blocks(world, cat, show_all):
    from fontlabapp.studios.font_audit import model
    from fontlabapp.studios.font_audit.blocks import BLOCKS, BLOCKS_TEXT

    original = _original("Unicode Coverage", fontlab=world.fontlab,
                         BLOCKS=[(int(a, 16), int(b, 16), n) for a, b, n in (line.split(" ", 2)
                                 for line in BLOCKS_TEXT.strip().splitlines())])
    assert len(BLOCKS) == 338
    assert hashlib.sha256(BLOCKS_TEXT.encode()).hexdigest() == (
        "e046dc0cb6f462bb99a8e4f39818c18eb9380038012186e0038b27a1dc1f26ce")
    codes = original["font_codes"]()
    assert model.font_codes(cat) == codes and codes[0x41] == "A"
    rows, outside = original["coverage"](list(codes), show_all)
    assert model.coverage(list(codes), show_all) == (rows, outside)
    assert outside == [0xE0041]
    assert model.coverage_status(rows, outside).endswith(" · 1 code points outside planes 0–1")
    assert model.coverage_status(rows, []) == f"{len(rows)} blocks listed"
    assert model.percent(1, 3) == "33%" and model.percent(0, 0) == "–"
    assert model.coverage_subtitle(codes, rows).endswith(
        "complete. Click a block to preview it; use Select block glyphs in Font window to select its glyphs.")
    assert model.coverage_subtitle({}, []) == "Open a font with encoded glyphs first."
    assert model.block_names(codes, 0x0, 0x7F) == ["A", "a", "space"]


@pytest.mark.parametrize("skip", [True, False])
def test_empty_when_compared_then_original_scan(world, cat, skip):
    from fontlabapp.studios.font_audit import model

    original = _original("Empty Glyphs", fontlab=world.fontlab)
    expected = original["scan"](world.package, skip)
    assert model.scan_empty(cat, skip) == expected
    assert ("a.sc", ["Bold"]) in expected and ("Aacute", ["Regular", "Bold"]) in expected
    assert ("space" in dict(expected)) is (not skip)
    assert model.empty_subtitle(expected, MASTERS).endswith("only on some (likely mistakes).")
    assert model.empty_subtitle([("x", ["Regular"])], MASTERS).startswith("1 glyph without")


def test_labels_when_compared_then_original_groups_and_names(world, cat):
    from fontlabapp.studios.font_audit import model

    original = _original("Label Statistics", fontlab=world.fontlab)
    labels = original["font_labels"]()
    assert model.font_labels(cat) == labels
    assert model.statistics(labels) == original["statistics"](labels)
    for mark in (0, 1, 16, 46, 200, 359, 360, 361, 1000, 1005, 1255, 1256, 5000):
        assert model.mark_label(mark) == original["mark_label"](mark)
    for name in ("a", ".notdef", "a.ss01.sc", ""):
        assert model.suffix_of(name) == original["suffix_of"](name)
    assert model.HUES == original["HUES"]
    marks, suffixes = model.statistics(labels)
    assert model.label_subtitle(labels, marks, suffixes).startswith("9 glyphs: 5 marked in 4 colours, 3 with a suffix")
    assert model.label_subtitle([], [], []) == "Open a font first."
    assert model.mark_rgb(0) is None and model.mark_rgb(10) == ("hsl", 9, 200, 150)
    assert model.mark_rgb(1300) == ("rgb", 225, 225, 225)


def test_preview_text_when_names_then_slash_list():
    from fontlabapp.studios.font_audit import model

    assert model.preview_text(["a", "", "b"]) == "/a/b" and model.preview_text([]) == ""
    assert model.plural(1) == "" and model.plural(2) == "s"


# session ----------------------------------------------------------------------
class Shell:
    def __init__(self):
        self.statuses = []

    def set_status(self, text):
        self.statuses.append(text)


class Preview:
    def __init__(self):
        self.calls = []

    def set_text(self, text):
        self.calls.append(("set_text", text))


def _studio(world, **kwargs):
    from fontlabapp.studios.font_audit.session import Studio

    def select(names, *, package_id):
        world.selections.append((list(names), package_id))
        return list(names)

    kwargs.setdefault("select", select)
    studio = Studio(Shell(), font=lambda: "font", **kwargs)
    studio.preview = Preview()
    return studio


def test_session_when_reload_then_catalogue_and_views(world):
    studio = _studio(world)
    seen = []
    studio.views.append(lambda: seen.append(studio.catalogue))
    assert studio.reload().masters == MASTERS and seen and studio.font() == "font"
    studio.show_glyphs(["a", "b"])
    studio.show_glyphs([])
    assert studio.preview.calls == [("set_text", "/a/b")]
    world.current = None
    assert studio.reload() is None


def test_session_when_read_fails_then_status(world):
    def fail(package):
        raise ValueError("nope")

    studio = _studio(world, read=fail)
    assert studio.reload() is None and studio.shell.statuses == ["Font Audit: nope"]


def test_session_check_when_stale_then_original_messages(world):
    from fontlabapp.studios.font_audit import session

    studio = _studio(world)
    with pytest.raises(ValueError, match="Refresh the report before selecting glyphs."):
        studio.check(None)
    with pytest.raises(ValueError, match="stale font: Refresh the report."):
        studio.check(3)
    studio.check(7)
    assert session.REFRESH_FIRST.startswith("Refresh")


def test_session_selected_names_when_error_then_empty_no_current_glyph(world, monkeypatch):
    from fontlabapp.core import scripting
    from fontlabapp.studios.font_audit import session

    world.selected = {"a", "A"}
    assert session.selected_names() == ["A", "a"]

    def broken():
        raise RuntimeError("native")

    monkeypatch.setattr(session, "names_font_window_selection", broken)
    assert session.selected_names() == []
    assert scripting.names_selected_names is not session.selected_names


def test_session_select_when_default_then_core_select_glyphs(world, monkeypatch):
    from fontlabapp.studios.font_audit import session

    calls = []
    monkeypatch.setattr(session, "select_glyphs", lambda names, *, package_id: calls.append((names, package_id)) or names)
    studio = session.Studio(Shell(), font=lambda: None)
    assert studio.select(("a", "b"), 7) == ["a", "b"] and calls == [(["a", "b"], 7)]


def test_backends_when_loaded_then_original_modules():
    from fontlabapp.core.scripting import font_audit_backends

    backends = font_audit_backends()
    assert backends.case_coverage.__name__ == "fontlabapp.glyphs.case_coverage.controller"
    assert backends.smallcaps.__name__ == "fontlabapp.glyphs.smallcaps.capture"
    assert backends.reports.__name__ == "fontlabapp.proof.reports.model"
    assert backends.unreferenced.__name__ == "fontlabapp.glyphs.unreferenced"


# Window and tabs on offscreen Qt ---------------------------------------------
class Backends:
    def __init__(self, world):
        self.world = world
        self.calls = []
        self.rows = [("b.ss01", "alternate"), ("a.sc", "small cap")]
        self.case_coverage = NS(show=lambda metadata, preferred: self.calls.append(("case", metadata, preferred))
                                or "case window")
        self.smallcaps = NS(current_report=lambda: self.calls.append(("capture",)) or {"counts": {}})
        self.reports = NS(show_report=lambda report, *, title, key: self.calls.append(("report", report, title, key))
                          or "report window")
        self.unreferenced = NS(unreferenced=lambda package: list(self.rows))


@pytest.fixture
def fa(studio_qt, world, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, TABS, raising=False)
    studios = importlib.import_module("fontlabapp.studios.font_audit")
    from PySide6.QtWidgets import QWidget

    class QtPreview(QWidget, Preview):
        def __init__(self):
            QWidget.__init__(self)
            Preview.__init__(self)

    preview = QtPreview()
    backends = Backends(world)

    def select(names, *, package_id):
        world.selections.append((list(names), package_id))
        return list(names)

    world.selected = {"A", "a"}
    shell = studios.show(
        package=lambda: world.current, font=lambda: "font", preview=lambda shell, studio: preview,
        select=select, backends=lambda: backends, case_metadata="meta", case_preferred="pref",
    )
    studio_qt.owned.append(shell)
    shell.statuses = []
    set_status = shell.set_status
    shell.set_status = lambda text: (shell.statuses.append(text), set_status(text))
    tabs_module = sys.modules[TABS]
    yield NS(shell=shell, preview=preview, tabs=tabs_module, world=world, backends=backends, qt=studio_qt,
             studio=shell.font_audit)
    sys.modules.pop(TABS, None)


def _tab(fa, title, **kwargs):
    tab = fa.tabs.TAB_CLASSES[title](fa.studio, **kwargs)
    fa.qt.owned.append(NS(close=tab.widget.deleteLater))
    fa.studio.reload()
    return tab


def test_show_when_opened_then_six_tabs_in_order(fa):
    titles = [fa.shell.tabs.tabText(i) for i in range(fa.shell.tabs.count())]
    assert titles == ["Overview", "Glyph table", "Unicode", "Empty", "Case & small caps", "Unreferenced", "About"]
    assert fa.shell.preview is fa.preview
    from fontlabapp.studios import font_audit

    assert font_audit.register_tabs() == tuple(titles[:-1])
    assert len(font_audit.registry.tabs(font_audit.APP)) == 6  # idempotent


def test_overview_tab_when_refreshed_then_cards_metrics_and_labels(fa):
    tab = _tab(fa, "Overview")
    assert tab.cards["Glyphs"] == 9 and "Glyphs: 9" in tab.cards_label.text()
    assert tab.subtitle.text() == "Fake Sans · 1000 units per em · current master Bold"
    assert [r[0] for r in tab.metrics.rows] == ["Regular", "Bold"]
    assert tab.metrics.rows[1][2] == ("760.5", "700", "500.25", "-250", 1)
    assert tab.note.text().startswith("Composites: a component on any master.")
    assert [r[0] for r in tab.marks_table.rows][:2] == ["Unmarked", "Red (hue 4°)"]
    tab.mark_chosen("Red (hue 4°)")
    assert fa.world.selections[-1] == (["A", "a"], 7)
    assert fa.preview.calls[-1] == ("set_text", "/A/a")
    tab.add.setChecked(True)
    fa.world.selected = {"space"}
    tab.suffix_chosen(".sc")
    assert fa.world.selections[-1] == (["space", "a.sc"], 7)
    assert fa.studio.shell.statuses[-1] == "Selected 2 glyphs"
    assert tab.select_group(tab.marks, 99) is None
    fa.world.current = Package([], pid=8)
    tab.suffix_chosen(".sc")
    assert fa.studio.shell.statuses[-1] == "Font Audit: stale font: Refresh the report."


def test_overview_tab_when_no_font_then_dashes(fa):
    fa.world.current = None
    tab = _tab(fa, "Overview")
    assert tab.cards_label.text() == "–" and tab.subtitle.text() == "Open a font first."
    assert tab.note.text() == "No font open." and tab.marks_table.rows == []
    tab.mark_chosen("Unmarked")
    assert "Refresh the report before selecting glyphs." in fa.studio.shell.statuses[-1]


def test_glyph_table_tab_when_selection_then_default_scope_copy_and_export(fa, tmp_path):
    copied = []
    tab = _tab(fa, "Glyph table", clipboard=copied.append)
    assert tab.scope.currentIndex() == 1 and tab.scope.itemText(1) == "Selected glyphs (2)"
    assert [r[0] for r in tab.rows] == ["A", "a"]
    assert tab.view.columns == ("glyph", "unicode", "width Regular", "width Bold", "contours", "components")
    assert not tab.export_button.isEnabled() and tab.copy_button.isEnabled()
    assert fa.studio.shell.statuses[-1] == "Choose a file to export, or copy the CSV."
    tab.copy()
    assert copied[0].startswith("glyph,unicode,width Regular") and fa.studio.shell.statuses[-1] == "Copied 2 rows"
    tab.scope.setCurrentIndex(0)
    assert len(tab.rows) == 9
    path = tmp_path / "out.csv"
    tab.path.setText(str(path))
    assert tab.export_button.isEnabled()
    tab.export()
    assert path.read_bytes().startswith(b"\xef\xbb\xbfglyph,unicode")
    assert tab.last_result["rows"] == 9 and fa.studio.shell.statuses[-1] == "Wrote 9 rows to out.csv"
    tab.row_chosen("a")
    assert fa.preview.calls[-1] == ("set_text", "/a")
    tab.choose()
    assert tab.chooser.defaultSuffix() == "csv" and tab.chooser.windowTitle() == "Export glyph table"
    tab.chooser.fileSelected.emit(str(tmp_path / "x.csv"))
    assert tab.path.text().endswith("x.csv")
    tab.choose()
    tab.chooser.close()


def test_glyph_table_tab_when_one_selected_then_all_glyphs(fa):
    fa.world.selected = {"a"}
    tab = _tab(fa, "Glyph table")
    assert tab.scope.currentIndex() == 0 and tab.scope.itemText(1) == "Selected glyphs (1)"


def test_glyph_table_tab_when_no_font_then_inert(fa):
    fa.world.current = None
    tab = _tab(fa, "Glyph table")
    assert tab.subtitle.text() == "Open a font first." and tab.rows == [] and tab.names() == []
    tab.run(tab.export)
    assert fa.studio.shell.statuses[-1] == "Font Audit: Choose a file to export, or copy the CSV."


def test_unicode_tab_when_block_chosen_then_preview_and_select(fa):
    tab = _tab(fa, "Unicode")
    names = [r[0] for r in tab.view.rows]
    assert names[0] == "Basic Latin" and tab.view.rows[0][2][0] == "0000–007F"
    tab.row_chosen("Basic Latin")
    assert fa.preview.calls[-1] == ("set_text", "/A/a/space")
    assert tab.select_block() == ["A", "a", "space"]
    assert fa.studio.shell.statuses[-1] == "Basic Latin: selected 3 glyphs"
    assert tab.select_block(999) is None
    tab.show_all.setChecked(True)
    assert len(tab.rows) == 338
    assert "outside planes 0–1" in fa.studio.shell.statuses[-1]


def test_unicode_tab_when_no_font_then_refused(fa):
    fa.world.current = None
    tab = _tab(fa, "Unicode")
    assert tab.subtitle.text() == "Open a font first."
    tab.run(tab.select_block)
    assert fa.studio.shell.statuses[-1].endswith("Refresh the report before selecting glyphs.")


def test_empty_tab_when_scanned_then_masters_and_select(fa):
    tab = _tab(fa, "Empty")
    assert tab.skip.isChecked() and tab.view.columns == ("Glyph", "Regular", "Bold")
    names = [r[0] for r in tab.view.rows]
    assert "space" not in names and "a.sc" in names
    assert dict((r[0], r[2]) for r in tab.view.rows)["a.sc"] == ("✓", "empty")
    assert tab.select_button.isEnabled()
    assert fa.studio.shell.statuses[-1] == (
        "Click a row to preview it; use Select in Font window to select it (all rows when none is chosen).")
    assert tab.select_rows() == names  # no row chosen: every row
    tab.row_chosen("a.sc")
    assert fa.preview.calls[-1] == ("set_text", "/a.sc") and tab.select_rows() == ["a.sc"]
    assert tab.select_rows([0, 99]) == [names[0]] and fa.studio.shell.statuses[-1] == "Selected 1 glyph"
    tab.skip.setChecked(False)
    assert "space" in [r[0] for r in tab.view.rows]


def test_empty_tab_when_no_font_then_refused(fa):
    fa.world.current = None
    tab = _tab(fa, "Empty")
    assert tab.subtitle.text() == "Open a font first." and not tab.select_button.isEnabled()
    tab.run(tab.select_rows)
    assert fa.studio.shell.statuses[-1] == "Font Audit: Refresh the report with an open font first."


def test_case_tab_when_buttons_then_original_backends(fa):
    tab = _tab(fa, "Case & small caps")
    assert tab.case_coverage() == "case window"
    assert tab.smallcaps() == "report window"
    assert fa.backends.calls == [("case", "meta", "pref"), ("capture",),
                                 ("report", {"counts": {}}, "Smallcap Consistency", "report_smallcap_consistency")]
    fa.studio.case_metadata = None
    tab.run(tab.case_coverage)
    assert "needs GlyphData" in fa.studio.shell.statuses[-1]


def test_unreferenced_tab_when_apply_then_selects_after_fresh_check(fa):
    tab = _tab(fa, "Unreferenced")
    assert tab.subtitle.text().startswith("Unencoded glyphs not used as components")
    assert fa.studio.shell.statuses[-1] == "2 unreferenced glyphs"
    tab.row_chosen("b.ss01")
    assert fa.preview.calls[-1] == ("set_text", "/b.ss01")
    assert tab.apply() == ["b.ss01", "a.sc"]
    assert fa.studio.shell.statuses[-1] == "Selected 2 glyphs in the Font window for review"
    fa.backends.rows = []
    tab.run(tab.apply)
    assert fa.studio.shell.statuses[-1] == "Font Audit: Unreferenced glyphs changed; refresh this tab."
    fa.studio.reload()
    assert fa.studio.shell.statuses[-1] == "Every glyph is encoded or referenced" and not tab.select_button.isEnabled()


def test_unreferenced_tab_when_backend_refuses_or_no_font_then_status(fa):
    def refuse(package):
        raise ValueError("Glyph source changed; reopen this tool.")

    fa.backends.unreferenced = NS(unreferenced=refuse)
    tab = _tab(fa, "Unreferenced")
    assert fa.studio.shell.statuses[-1] == "Font Audit: Glyph source changed; reopen this tool."
    fa.world.current = None
    fa.studio.reload()
    assert tab.subtitle.text() == "Open a font, then run this script again."


def test_show_when_default_preview_then_read_only_metrics_preview(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios.font_audit.app as app

    calls = []
    monkeypatch.setattr(fontui, "metrics_preview", lambda *a, **k: calls.append((a, k)) or "preview")
    shell = NS(widget="w", hint_check="check")
    assert app._metrics_preview(shell, NS(font=lambda: "font")) == "preview"
    assert calls == [(("font", "w"), {"controls": False, "hint_check": "check", "read_only": True})]
    assert app._metrics_preview(shell, NS(font=lambda: None)) is None


def test_show_when_build_fails_then_shell_closed(monkeypatch):
    from fontlabapp import fontui
    import fontlabapp.studios.font_audit as studios
    import fontlabapp.studios.font_audit.app  # noqa: F401 - bind fontui before patching

    closed = []

    class FakeShell:
        widget = None
        hint_check = None

        def set_preview(self, preview):
            raise RuntimeError("boom")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: FakeShell())
    with pytest.raises(RuntimeError, match="boom"):
        studios.show(font=lambda: None, preview=lambda shell, studio: "p")
    assert closed == [True]


def test_studio_for_when_called_twice_then_same_state(monkeypatch):
    from fontlabapp.studios.font_audit import app

    shell = NS(set_status=lambda text: None)
    assert app.studio_for(shell) is app.studio_for(shell)


def test_package_when_imported_then_lazy():
    import fontlabapp.studios.font_audit as studios

    assert "fontlabapp.studios.font_audit.app" not in sys.modules
    assert callable(studios.show) and callable(studios.studio_for)
