# this_file: tests/test_studio_anchor_transfer.py
"""Anchor Transfer (A13): parity with the 5 Scriptmix scripts, dry runs and the one labelled Undo step.

Each write test checks the single ``AppShell.history`` call (label and the
(glyph, master) layers) or, for Between fonts, the one crossfont copy with
this app's label. Pure functions are compared with the Scriptmix originals
by AST; the rest is checked against the reused App backends.
"""

from _demo_support import stub_natives

import ast
import importlib
import sys
from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture
from _widths_anchors_originals import ORIGINALS


def _forget_studio_children():
    import fontlabapp.studios as studios

    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)
        studios.__dict__.pop(name.split(".")[2], None)


@pytest.fixture(autouse=True)
def fresh_studios():
    _forget_studio_children()
    yield
    _forget_studio_children()


class Point:
    def __init__(self, x, y):
        self._x, self._y = float(x), float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class Pin:
    def __init__(self, name, x, y):
        self.name, self.point, self.anchor, self.appearance = name, Point(x, y), True, 0


class Layer:
    def __init__(self, log, glyph, master, width, anchors, *, auto=False):
        self.log, self.glyph, self.master, self.name = log, glyph, master, master
        self.advanceWidth, self.autoLayer, self.isNull = width, auto, False
        self.anchors = [Pin(n, x, y) for n, (x, y) in anchors.items()]
        self.shapes = []
        self.drop = set()  # names FontLab "does not keep" (read-back mismatch)

    def addAnchor(self, pin):  # noqa: N802 - native API
        self.log.append(("add", self.glyph, self.master, pin.name, pin.point.x(), pin.point.y()))
        if pin.name not in self.drop:
            self.anchors.append(pin)

    def removeAnchor(self, pin):  # noqa: N802 - native API
        self.log.append(("remove", self.glyph, self.master, pin.name))
        self.anchors.remove(pin)

    def points(self):
        return {p.name: (p.point.x(), p.point.y()) for p in self.anchors}


class Glyph:
    def __init__(self, name, layers):
        self.name, self.isNull = name, False
        self._layers = {layer.master: layer for layer in layers}

    def findLayer(self, master):  # noqa: N802 - native API
        return self._layers.get(master)


class Package:
    def __init__(self, masters=("Regular", "Bold"), current="Regular", identity=7):
        self.log, self.masters, self.master, self.glyphs, self.id = [], list(masters), current, {}, identity

    def add(self, name, layers, **kwargs):
        """``layers``: master -> (advance, {anchor: (x, y)})."""
        self.glyphs[name] = Glyph(name, [Layer(self.log, name, m, w, a, **kwargs) for m, (w, a) in layers.items()])
        return self.glyphs[name]

    def findName(self, name):  # noqa: N802 - native API
        return self.glyphs.get(name)

    def layer(self, name, master):
        return self.glyphs[name].findLayer(master)


def package():
    pkg = Package()
    pkg.add("n", {"Regular": (500, {"top": (250, 700.4), "bottom": (250, 0)}),
                  "Bold": (600, {"top": (301, 720), "bottom": (300, 0)})})  # fmt: skip
    pkg.add("m", {"Regular": (800, {"ogonek": (700, 0)}), "Bold": (900, {})})
    pkg.add("h", {"Regular": (500, {"top": (250, 700.4)}), "Bold": (600, {})})
    return pkg


class Recorder:
    """``AppShell.history`` stand-in: records one call, runs mutate and read-back."""

    def __init__(self, shell, refuse=None):
        self.shell, self.calls, self.refuse = shell, [], refuse

    def __call__(self, label, glyphs, mutate, *, layers, read_back=None, allow_bases=False):
        self.calls.append((label, [g.name for g in glyphs], [(la.glyph, la.master) for la in layers], allow_bases))
        if self.refuse:
            self.shell.set_status(self.refuse)
            return None
        mutate()
        return SimpleNamespace(mismatches=read_back() if read_back else [], pending_note="")


def native(name):
    if name == "PythonQt":
        return SimpleNamespace(QtCore=SimpleNamespace(QPointF=Point))

    def pin_point(point):
        pin = Pin("", 0, 0)
        pin.point = point
        return pin

    return SimpleNamespace(flPinPoint=pin_point)


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.anchors.writer as writer
    import fontlabapp.core.history.glyphs as history

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return lambda *args: self.calls.append((name, *args))

    monkeypatch.setattr(writer, "_native", native)
    facts = SimpleNamespace(value=history.auto_facts([]))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts.value)

    def open_app(pkg=None, selection=("m", "h"), setup=None):
        studio = importlib.import_module("fontlabapp.studios.anchor_transfer")
        transfer = importlib.import_module("fontlabapp.studios.anchor_transfer.transfer")
        monkeypatch.setattr(transfer, "catalog_names", lambda: list(pkg.glyphs))
        monkeypatch.setattr(transfer, "font_rows", lambda: ())
        if setup:
            setup(transfer)
        pkg = package() if pkg is None else pkg
        chosen = list(selection)
        _kerning = importlib.import_module("fontlabapp.studios._kerning")
        monkeypatch.setattr(_kerning, "names_selected_names", lambda: list(chosen))
        preview = QtPreview()
        shell = studio.show(package=lambda: pkg, font=lambda: "font", preview=lambda shell, tool: preview)
        studio_qt.owned.append(shell)
        tool = shell.anchor_transfer_tool
        recorder = Recorder(shell)
        shell.history = recorder
        panels = {title: view.__self__ for title, view in zip(studio.TAB_TITLES, tool.views, strict=True)}
        return SimpleNamespace(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio,
                               history=recorder, selection=chosen, facts=facts, transfer=transfer)  # fmt: skip

    return open_app


def rows(panel):
    return [(r.glyph_name, r.layer, tuple(r.values)) for r in panel.grid.rows]


def type_source(app, name):
    panel = app.panels["From glyph"]
    panel.source.setText(name)
    return panel


# ---------------------------------------------------------------- shell, registry, parity
def test_show_when_opened_then_five_tabs_tglyph_preview_and_masters(opened):
    app = opened()
    assert [app.shell.tabs.tabText(i) for i in range(app.shell.tabs.count())] == \
        ["From glyph", "Between masters", "Between fonts", "From components", "CSV import", "About"]
    assert app.shell.preview is app.preview
    assert app.tool.app == "Anchor Transfer" and app.tool.masters == ["Regular", "Bold"]


def test_registry_when_imported_then_lazy_and_shared_tool():
    from fontlabapp import studios
    import fontlabapp.studios.anchor_transfer as at

    assert at.register_tabs() == at.TAB_TITLES == at.register_tabs()
    assert [s.title for s in studios.tabs(at.APP)] == list(at.TAB_TITLES)
    shell = SimpleNamespace()
    assert at.tool_for(shell) is at.tool_for(shell) and at.tool_for(shell).app == at.APP
    assert not any(n.endswith(("from_glyph", "fonts", "csv_import")) for n in sys.modules
                   if n.startswith("fontlabapp.studios."))  # fmt: skip


def _functions(source, names):
    tree = ast.parse(source)
    return [ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]


@pytest.mark.parametrize("title", ["Mirror Across Masters", "Derive Anchors From Components", "Add Anchors From File"])
def test_pure_functions_when_compared_then_ast_equal_to_scriptmix(title):
    import inspect

    from fontlabapp.studios.anchor_transfer import transfer

    path, digest, names, source = ORIGINALS[title]
    assert len(digest) == 64 and path.startswith("Scripts/Anchors/")
    ported = "\n\n".join(inspect.getsource(getattr(transfer, n)) for n in names)
    assert _functions(ported, names) and _functions(ported, names) == _functions(source, names)


def test_constants_when_compared_then_original_texts_and_defaults(studio_qt):  # noqa: F811
    from fontlabapp.studios.anchor_transfer import fonts, transfer

    assert transfer.MODES == ["Add and move (keep other anchors)", "Replace (remove anchors the source lacks)"]
    assert transfer.SCALE_LABEL == "Scale x by advance-width ratio"
    assert transfer.ONLY_MISSING == "Only add missing anchors"
    assert transfer.CSV_INFO == "Coordinates round half up to font units."
    assert transfer.ALL_MASTERS == "*All masters*"
    assert transfer.font_options() == transfer.crossfont.model.Options()
    assert (fonts.SOURCE_SCOPES, fonts.ANCHOR_SCOPES, fonts.LOCATIONS, fonts.COLLISIONS, fonts.RENAMES) == (
        ["All glyphs", "Selected glyphs"], ["All anchors", "Specific anchors"], ["Absolute", "Relative"],
        ["Overwrite", "Rename"], ["Incoming", "Destination"])


# ---------------------------------------------------------------- From glyph
def test_from_glyph_when_add_mode_then_original_rounded_read_and_one_labelled_undo(opened):
    app = opened()
    panel = type_source(app, "n")
    assert get_checked(panel.scale) and panel.mode.currentIndex() == 0 and panel.scope.currentIndex() == 0
    # m: ratio 800/500; x = round(250*1.6) = 400. The original reads both layers through
    # anchors.inspect.model.anchor_points (rounded), so y is 700 and h's top already matches.
    assert rows(panel) == [
        ("m", "Regular", ("top", "–", "400, 700")), ("m", "Regular", ("bottom", "–", "400, 0")),
        ("h", "Regular", ("bottom", "–", "250, 0"))]
    assert panel.count.text() == "3 anchor changes from n" and panel.apply_button.isEnabled()
    assert panel.apply()
    assert app.history.calls == [("Anchor Transfer: copy anchors 2 glyphs", ["m", "h"],
                                  [("m", "Regular"), ("h", "Regular")], False)]
    assert app.pkg.layer("m", "Regular").points() == {"ogonek": (700, 0), "top": (400, 700), "bottom": (400, 0)}
    assert "Changed 3 anchors on 2 layers" in app.tool.status


def get_checked(box):
    return box.isChecked()


def test_from_glyph_when_replace_all_masters_then_removals_and_bold(opened):
    app = opened(selection=("m",))
    panel = type_source(app, "n")
    panel.mode.setCurrentIndex(1)
    panel.scope.setCurrentIndex(1)
    assert ("m", "Regular", ("ogonek", "700, 0", "removed")) in rows(panel)
    assert ("m", "Bold", ("top", "–", "452, 720")) in rows(panel)  # round(301 * 1.5)
    panel.apply()
    assert app.history.calls[0][0] == "Anchor Transfer: copy anchors m"
    assert app.history.calls[0][2] == [("m", "Regular"), ("m", "Bold")]
    assert "ogonek" not in app.pkg.layer("m", "Regular").points()


def test_from_glyph_when_no_or_unknown_source_then_original_status_and_no_apply(opened):
    app = opened()
    panel = app.panels["From glyph"]
    assert "Type the source glyph name" in panel.subtitle.text() and not panel.apply_button.isEnabled()
    type_source(app, "zz")
    assert "No glyph named “zz”" in panel.subtitle.text() and rows(panel) == []
    app.selection.clear()
    type_source(app, "n")
    assert panel.subtitle.text() == "Select the glyphs to receive anchors, then press Refresh."


def test_from_glyph_when_source_selected_then_source_skipped(opened):
    app = opened(selection=("n", "h"))
    panel = type_source(app, "n")
    assert {r[0] for r in rows(panel)} == {"h"}


def test_apply_when_anchors_changed_after_dry_run_then_refused_press_refresh(opened):
    app = opened()
    panel = type_source(app, "n")
    app.pkg.layer("m", "Regular").anchors.append(Pin("extra", 1, 1))
    assert not panel.apply()
    assert app.history.calls == [] and "press Refresh" in app.tool.status


def test_apply_when_read_back_mismatch_then_partly_applied_with_rounding_note(opened):
    app = opened(selection=("m",))
    app.pkg.layer("m", "Regular").drop = {"top"}
    panel = type_source(app, "n")
    panel.apply()
    assert app.tool.status.startswith("Partly applied: Anchor Transfer: copy anchors m. m/top")
    assert app.tool.status.endswith("Check Preferences > Rounding.")


def test_apply_when_shell_refuses_then_status_kept_and_false(opened):
    app = opened(selection=("m",))
    app.history.refuse = "Glyph window would undo only part of it"
    panel = type_source(app, "n")
    assert not panel.apply()
    assert app.tool.status == "Glyph window would undo only part of it"


def test_auto_bases_when_dependants_then_refused_until_tick_and_reset_for_other_set(opened):
    import fontlabapp.core.history.glyphs as history

    app = opened()
    app.facts.value = history.AutoFacts(frozenset({"mcomb"}), {"m": frozenset({"mcomb"})})
    panel = type_source(app, "n")
    assert not panel.allow.isChecked() and not panel.apply_button.isEnabled()
    assert panel.count.text().startswith("Refused. FontLab rebuilds auto glyphs mcomb")
    panel.allow.setChecked(True)
    assert panel.apply_button.isEnabled()
    assert panel.apply()
    assert app.history.calls[-1][3] is True
    app.selection[:] = ["h"]
    app.facts.value = history.AutoFacts(frozenset({"hcomb"}), {"h": frozenset({"hcomb"})})
    app.tool.reload()
    assert not panel.allow.isChecked()


def test_auto_owner_and_auto_layer_when_planned_then_refused_or_skipped(opened):
    import fontlabapp.core.history.glyphs as history

    app = opened()
    app.facts.value = history.AutoFacts(frozenset({"m"}), {})
    panel = type_source(app, "n")
    assert panel.count.text().startswith("Refused. FontLab cannot undo edits to these glyphs: m: has auto layers")
    assert not panel.apply_button.isEnabled() and not panel.apply()
    pkg = package()
    pkg.add("k", {"Regular": (500, {})}, auto=True)
    app = opened(pkg, selection=("k", "h"))
    panel = type_source(app, "n")
    assert "1 auto layer skipped" in panel.count.text()
    panel.apply()
    assert app.history.calls[0][2] == [("h", "Regular")]


def test_origin_when_existing_anchor_moved_to_zero_then_refused(opened):
    pkg = package()
    pkg.add("z", {"Regular": (0, {"top": (5, 5)}), "Bold": (0, {})})
    pkg.add("o", {"Regular": (500, {"top": (0, 0)}), "Bold": (500, {})})
    app = opened(pkg, selection=("z",))
    panel = type_source(app, "o")
    panel.scale.setChecked(False)
    assert "0, 0" in panel.count.text() and not panel.apply_button.isEnabled()


def test_row_when_selected_then_tglyph_loads_glyph_on_master(opened):
    app = opened()
    panel = type_source(app, "n")
    panel.row_chosen("m", "Regular")
    assert ("load", "m", "Regular") in app.preview.calls


# ---------------------------------------------------------------- Between masters
def test_mirror_when_defaults_then_current_to_others_half_up_and_one_undo(opened):
    app = opened(selection=("n",))
    panel = app.panels["Between masters"]
    assert panel.source.currentText() == "Regular" and panel.targets.ticked() == [1]
    assert panel.scale.isChecked() and not panel.only_missing.isChecked()
    # ratio 600/500: top x 300, y half_up(700.4) = 700; bottom x 300 (same) -> unchanged, not listed.
    assert rows(panel) == [("n", "Bold", ("top", "301, 720", "300, 700"))]
    panel.apply()
    assert app.history.calls == [("Anchor Transfer: mirror anchors n", ["n"], [("n", "Bold")], False)]
    assert app.pkg.layer("n", "Bold").points()["top"] == (300, 700)


def test_mirror_when_only_missing_or_no_targets_or_one_master_then_original_rules(opened):
    app = opened(selection=("h",))
    panel = app.panels["Between masters"]
    panel.only_missing.setChecked(True)
    assert rows(panel) == [("h", "Bold", ("top", "–", "300, 700"))]
    panel.targets.set_ticked(set())
    assert "Tick the masters to copy into." in panel.subtitle.text()
    one = Package(masters=("Regular",))
    one.add("n", {"Regular": (500, {"top": (1, 2)})})
    app = opened(one, selection=("n",))
    assert "This font has one master. Nothing to mirror into." in app.panels["Between masters"].subtitle.text()


# ---------------------------------------------------------------- From components
def test_components_when_derived_then_all_masters_and_one_undo(opened):
    def setup(transfer):
        transfer.derived_points = lambda package, names, masters, notes: (
            notes.setdefault(("h", "Bold"), []).append(transfer.anchor_writer.Change("components", "", "doubt"))
            or {("m", "Bold"): {"top": (450, 700)}})

    app = opened(setup=setup)
    panel = app.panels["From components"]
    assert ("m", "Bold", ("top", "missing", "(450, 700)")) in rows(panel)
    assert ("h", "Bold", ("components", "", "doubt")) in rows(panel)
    panel.apply()
    assert app.history.calls == [("Anchor Transfer: derive anchors m", ["m"], [("m", "Bold")], False)]


def test_refresh_when_one_tab_fails_then_contained_and_others_refresh(opened):
    def setup(transfer):
        def broken():
            raise RuntimeError("catalog timed out")

        transfer.catalog_names = broken

    app = opened(selection=("n",), setup=setup)
    panel = app.panels["From components"]
    assert panel.subtitle.text() == "Anchor Transfer: catalog timed out" and not panel.apply_button.isEnabled()
    assert rows(app.panels["Between masters"])  # the other tabs refreshed
    assert app.history.calls == []


# ---------------------------------------------------------------- CSV import
def test_csv_when_loaded_then_current_master_half_up_and_one_undo(opened, tmp_path):
    path = tmp_path / "anchors.csv"
    path.write_bytes(b"\xef\xbb\xbfname,top_x,top_y\r\nm,10.5,20.49\r\nh,250,700.4\r\n")
    app = opened()
    panel = app.panels["CSV import"]
    assert panel.subtitle.text() == "Choose an anchor CSV file, then press Load."
    panel.csv_path.setText(str(path))
    app.tool.reload()
    assert panel.csv_info.text() == "Coordinates round half up to font units; BOM removed; CR/CRLF read as LF."
    assert rows(panel) == [("m", "Regular", ("top", "missing", "(11, 20)")),
                           ("h", "Regular", ("top", "(250.0, 700.4)", "(250, 700)"))]
    panel.apply()
    assert app.history.calls == [("Anchor Transfer: import anchors 2 glyphs", ["m", "h"],
                                  [("m", "Regular"), ("h", "Regular")], False)]
    assert app.pkg.layer("m", "Regular").points()["top"] == (11, 20)


def test_csv_when_missing_glyph_or_bad_file_then_original_errors(opened, tmp_path):
    path = tmp_path / "anchors.csv"
    path.write_text("glyph,top_x,top_y\nq,1,2\n")
    app = opened()
    panel = app.panels["CSV import"]
    panel.csv_path.setText(str(path))
    app.tool.reload()
    assert panel.subtitle.text() == "Anchor Transfer: Missing glyphs: q" and rows(panel) == []
    path.write_text("glyph,top_x\nm,1\n")
    app.tool.reload()
    assert "Pair every anchor _x column with an _y column." in panel.subtitle.text()
    panel.csv_path.setText(str(tmp_path / "none.csv"))
    app.tool.reload()
    assert "Cannot read CSV" in panel.subtitle.text()


def test_csv_when_file_changes_after_dry_run_then_refused(opened, tmp_path):
    path = tmp_path / "anchors.csv"
    path.write_text("name,top_x,top_y\nm,1,2\n")
    app = opened()
    panel = app.panels["CSV import"]
    panel.csv_path.setText(str(path))
    app.tool.reload()
    path.write_text("name,top_x,top_y\nm,3,4\n")
    assert not panel.apply() and app.history.calls == [] and "press Refresh" in app.tool.status


def test_csv_when_browse_then_file_dialog_and_load(opened, tmp_path, monkeypatch):
    from PySide6 import QtWidgets

    path = tmp_path / "a.csv"
    path.write_text("name,top_x,top_y\nm,1,2\n")
    app = opened()
    panel = app.panels["CSV import"]
    asked = []
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                        lambda *a: asked.append(a[1:]) or (str(path), ""))  # fmt: skip
    panel.choose_csv()
    assert asked == [("Open Anchor CSV", "", "Anchor table (*.csv)")] and rows(panel)


# ---------------------------------------------------------------- Between fonts
def font(identity, label, masters=("Regular",)):
    return SimpleNamespace(identity=identity, label=label, masters=masters)


def fonts_setup(monkeypatch, snapshot, result=None, error=None):
    from fontlabapp.anchors.crossfont.capture import Layer as CapturedLayer
    from fontlabapp.anchors.crossfont.model import Pin as CapturedPin

    def layer(identity, width, pins, automatic=False):
        return CapturedLayer(identity, width, automatic, 0,
                             tuple(CapturedPin(n_id, n, x, y, (1,) * 7) for n_id, (n, x, y) in enumerate(pins, 10 * identity)))  # fmt: skip

    copies = []

    def setup(transfer):
        transfer.font_rows = lambda: (font(7, "A.vfc"), font(8, "B.vfc"))
        transfer._capture = lambda args: snapshot["value"]

        class Backend:
            def copy(self, *args, title=None):
                copies.append((args, title))
                if error is not None:
                    raise error
                return result

        monkeypatch.setattr(transfer.crossfont.native, "Backend", Backend)

    def snap(automatic=False, skipped=()):
        return SimpleNamespace(
            layers=(("n", "Regular", "Regular", layer(1, 500, [("top", 250, 700)]),
                     layer(2, 600, [], automatic)),),  # fmt: skip
            skipped=tuple(skipped))

    return setup, snap, copies


def test_fonts_when_two_fonts_then_dry_run_and_one_destination_undo(opened, monkeypatch):
    snapshot = {}
    result = {"anchors": 1, "layers": 1, "skipped": (), "zero_advance": ()}
    setup, snap, copies = fonts_setup(monkeypatch, snapshot, result)
    snapshot["value"] = snap()
    app = opened(setup=setup)
    panel = app.panels["Between fonts"]
    assert panel.source_font.currentText() == "A.vfc [#7]" and panel.destination_font.currentText() == "B.vfc [#8]"
    assert panel.source_layer.currentText() == "*All masters*" and panel.collision.currentIndex() == 1
    assert panel.rename_side.currentIndex() == 1 and panel.suffix.text() == ".bak" and panel.angle.value() == 10
    assert rows(panel) == [("n", "Regular", ("Regular → Regular", "add", "top", "250, 700"))]
    assert panel.apply_button.isEnabled() and panel.apply()
    assert copies == [((7, 8, "*All masters*", "*All masters*", False, panel.options()),
                       "Anchor Transfer: copy anchors from A.vfc to n")]
    assert app.history.calls == []
    assert "Copied 1 anchors across 1 layers." in app.tool.status


def test_fonts_when_same_font_or_changed_or_automatic_then_refused(opened, monkeypatch):
    snapshot = {}
    setup, snap, copies = fonts_setup(monkeypatch, snapshot, {})
    snapshot["value"] = snap()
    app = opened(setup=setup)
    panel = app.panels["Between fonts"]
    snapshot["value"] = snap(skipped=("Missing layer: x",))
    assert not panel.apply() and "press Refresh" in app.tool.status and copies == []
    panel.destination_font.setCurrentIndex(0)
    assert "Choose two different fonts" in panel.subtitle.text() and not panel.apply_button.isEnabled()
    panel.destination_font.setCurrentIndex(1)
    snapshot["value"] = snap(automatic=True)
    app.tool.reload()
    assert panel.count.text() == "Refused. Automatic destination layers cannot safely receive copied anchors."
    assert not panel.apply() and copies == []


def test_fonts_when_partial_write_then_partly_applied(opened, monkeypatch):
    from fontlabapp.anchors.crossfont.transaction import PartialWriteError

    snapshot = {}
    setup, snap, copies = fonts_setup(monkeypatch, snapshot, error=PartialWriteError(1, [ValueError("x")]))
    snapshot["value"] = snap()
    app = opened(setup=setup)
    app.panels["Between fonts"].apply()
    assert app.tool.status.startswith("Partly applied: Anchor Transfer: copy anchors from A.vfc to n.")


def test_fonts_when_options_changed_then_passed_unchanged(opened, monkeypatch):
    snapshot = {}
    setup, snap, _ = fonts_setup(monkeypatch, snapshot, {})
    snapshot["value"] = snap()
    app = opened(setup=setup)
    panel = app.panels["Between fonts"]
    panel.which.setCurrentIndex(1)
    panel.anchor_names.setText("top")
    panel.location.setCurrentIndex(1)
    panel.collision.setCurrentIndex(0)
    panel.italic.setChecked(True)
    assert panel.options() == app.transfer.crossfont.model.Options(True, True, 10, False, True, ".bak", "top")


def test_fonts_when_one_or_no_font_then_says_so(opened, monkeypatch):
    app = opened()
    panel = app.panels["Between fonts"]
    assert panel.subtitle.text() == "No open font files found!"
    app.transfer.font_rows = lambda: (font(7, "A.vfc"),)
    app.tool.reload()
    assert panel.subtitle.text() == "Open a second font to copy anchors into."


def test_no_font_when_opened_then_every_tab_says_so(opened):
    app = opened()
    app.shell.package = lambda: None
    app.tool.reload()
    assert app.panels["From glyph"].subtitle.text() == "Open a font first."
    assert app.tool.status == "Open a font first." and app.history.calls == []


# ---------------------------------------------------------------- demo
def test_demo_when_run_then_opens_or_reports_error(monkeypatch):
    import runpy
    from pathlib import Path

    import fontlabapp
    import fontlabapp.qt.dialogs as dialogs
    import fontlabapp.studios.anchor_transfer as at

    path = Path(__file__).resolve().parents[1] / "Scripts" / "Anchors" / "Anchor Transfer Demo.py"
    assert "fontlabapp.studios.anchor_transfer" in path.read_text()
    opened_with = []
    monkeypatch.setattr(at, "show", lambda: opened_with.append(True))
    runpy.run_path(str(path), run_name="__main__")
    assert opened_with == [True]
    said = []
    monkeypatch.setattr(at, "show", lambda: (_ for _ in ()).throw(RuntimeError("no font")))
    monkeypatch.setattr(dialogs, "run_standard_message_box", lambda *a: said.append(a[3]))
    qt = SimpleNamespace(QtGui=SimpleNamespace(QMessageBox=SimpleNamespace(Ok=1)))
    stub_natives(monkeypatch, fontlabapp, lambda name: qt if name == 'PythonQt' else SimpleNamespace(MainWindow=lambda: None))
    runpy.run_path(str(path), run_name="__main__")
    assert said == ["Anchor Transfer did not open: no font"]


# ---------------------------------------------------------------- Derive / CSV rules, original functions
class Transform:
    def __init__(self, dx=0.0, dy=0.0, affine=True, scale=1.0):
        self.values, self.affine = (scale, 0.0, 0.0, scale, dx, dy), affine

    def isAffine(self):  # noqa: N802 - Qt API
        return self.affine

    def m11(self):
        return self.values[0]

    def m12(self):
        return self.values[1]

    def m21(self):
        return self.values[2]

    def m22(self):
        return self.values[3]

    def dx(self):
        return self.values[4]

    def dy(self):
        return self.values[5]


def component(glyph, transform=None, layer=""):
    data = SimpleNamespace(componentGlyph=glyph, componentLayer=layer)
    return SimpleNamespace(isComponent=True, shapeData=data, transform=transform or Transform())


def derive_package():
    pkg = Package()
    pkg.add("a", {"Regular": (500, {"bottom": (250, 0)}), "Bold": (600, {"bottom": (300, 0)})})
    pkg.add("acutecomb", {"Regular": (0, {"_top": (0, 500)}), "Bold": (0, {"_top": (0, 520)})})
    pkg.add("aacute", {"Regular": (500, {}), "Bold": (600, {})})
    return pkg


def test_derived_points_when_mark_on_base_then_half_up_attachment_in_base(monkeypatch):
    from fontlabapp.studios.anchor_transfer import transfer

    pkg = derive_package()
    pkg.layer("aacute", "Regular").shapes = [component("a"), component("acutecomb", Transform(250.5, 200))]
    pkg.layer("aacute", "Bold").shapes = [component("a", Transform(10)), component("acutecomb", Transform(310, 0))]
    notes = {}
    found = transfer.derived_points(pkg, ["aacute"], ["Regular", "Bold"], notes)
    assert found == {("a", "Regular"): {"top": (251, 700)}, ("a", "Bold"): {"top": (300, 520)}} and notes == {}


def test_derived_points_when_doubtful_evidence_then_note_rows_only(monkeypatch):
    from fontlabapp.studios.anchor_transfer import transfer

    pkg = derive_package()
    pkg.add("other", {"Regular": (500, {"_top": (1, 1), "_topx": (2, 2)}), "Bold": (500, {})})
    pkg.add("b", {"Regular": (500, {}), "Bold": (500, {})})
    pkg.layer("aacute", "Regular").shapes = [component("a"), component("acutecomb", Transform(affine=False)),
                                             SimpleNamespace(isComponent=False)]  # fmt: skip
    pkg.layer("aacute", "Bold").shapes = [component("missing"), component("a")]
    pkg.layer("b", "Regular").shapes = [component("a", layer="Light"), component("acutecomb")]
    pkg.layer("b", "Bold").shapes = [component("a"), component("other", layer="Regular")]
    notes = {}
    assert transfer.derived_points(pkg, ["aacute", "b"], ["Regular", "Bold"], notes) == {}
    texts = {owner: [c.new for c in changes] for owner, changes in notes.items()}
    assert texts[("aacute", "Regular")] == ["Perspective components cannot supply an anchor.; layer skipped"]
    assert texts[("aacute", "Bold")] == ["missing: missing or automatic referenced layer, skipped"]
    assert texts[("b", "Regular")] == ["a: missing or automatic referenced layer, skipped"]
    assert texts[("b", "Bold")] == ["other: ambiguous mark, skipped"]


def test_derived_points_when_two_composites_disagree_then_conflict_skipped():
    from fontlabapp.studios.anchor_transfer import transfer

    pkg = derive_package()
    pkg.add("aacute2", {"Regular": (500, {}), "Bold": (600, {})})
    pkg.layer("aacute", "Regular").shapes = [component("a"), component("acutecomb", Transform(250, 200))]
    pkg.layer("aacute2", "Regular").shapes = [component("a"), component("acutecomb", Transform(260, 200))]
    notes = {}
    assert transfer.derived_points(pkg, ["aacute", "aacute2"], ["Regular"], notes) == {("a", "Regular"): {}}
    assert [c.new for c in notes[("a", "Regular")]] == ["conflicting evidence, skipped"]
    with pytest.raises(ValueError, match="finite and invertible"):
        transfer.attachment_in_base((1, 1), (1, 0, 0, 1, 0, 0), (0, 0, 0, 0, 0, 0))


@pytest.mark.parametrize(("text", "error"), [
    ("name,top_x,top_y\nn,1,2\x00\n", "cannot preserve"),
    ("name,top_x,top_y,width\nn,1,2,3\n", "Unknown CSV columns: width"),
    ("top_x,top_y\n1,2\n", "needs a name or glyph column"),
    ("name,top_x,top_y,a_y\nn,1,2,3\n", "_y column has no _x column"),
    ("name,top_x,top_y\nn,1,2\nn,1,2\n", "empty/repeated glyph name"),
    ("name,top_x,top_y\nn,a,2\n", "n/top: enter both numeric coordinates."),
    ("name,top_x,top_y\nn,inf,2\n", "n/top: coordinates must be finite."),
    ("name,top_x,top_y\n", "CSV has no glyph rows."),
])  # fmt: skip
def test_parse_table_when_ambiguous_then_original_errors(text, error):
    from fontlabapp.studios.anchor_transfer import transfer

    with pytest.raises(ValueError, match=error):
        transfer.parse_table(text)
    assert transfer.parse_table("glyph,top_x,top_y\nn,,\nm,0.5,-0.5\n") == {"n": {}, "m": {"top": (1, 0)}}
    with pytest.raises(ValueError, match="Choose an anchor CSV file."):
        transfer.load_table("")


def test_glyph_preview_when_font_then_tglyph_on_current_master_else_none(monkeypatch):
    import fontlabapp.fontui as fontui
    from fontlabapp.studios.anchor_transfer import app as at_app

    made = []
    monkeypatch.setattr(fontui, "glyph_view", lambda *a, **k: made.append((a, k)) or "view")
    shell = SimpleNamespace(package=lambda: Package(current="Bold"), widget="w", hint_check="h")
    assert at_app.glyph_preview(shell, SimpleNamespace(font=lambda: "font")) == "view"
    assert made == [(("font", "w"), {"layer": "Bold", "controls": False, "label_prefix": "Anchor Transfer",
                                    "hint_check": "h"})]  # fmt: skip
    assert at_app.glyph_preview(shell, SimpleNamespace(font=lambda: None)) is None


def test_show_when_assembly_fails_then_shell_closed_and_error_raised(monkeypatch):
    import fontlabapp.fontui as fontui
    from fontlabapp.studios.anchor_transfer import app as at_app

    closed = []
    shell = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: shell)

    def broken(shell, tool):
        raise RuntimeError("no preview")

    with pytest.raises(RuntimeError, match="no preview"):
        at_app.show(package=lambda: None, font=lambda: None, preview=broken)
    assert closed == [True]
