# this_file: tests/test_demo_scripts_fonts_features.py
"""Offline runs of the Scripts/Font Info and Scripts/Features demos (Issue 208, Task 6).

Each demo runs through runpy as ``__main__`` (entry points and arguments are
asserted) and as an imported name (nothing may run). The real host-free
``fontlabapp`` modules stay in use, so the sample results are computed by the
real models. ``PythonQt`` and ``fontlab`` are stubbed, and so are the panel
shells that load Qt classes when imported; the fake shells answer the calls the
real shells make and record every write attempt. Offline results are not native
FontLab acceptance.
"""

from types import SimpleNamespace

import pytest
from _demo_support import FakeSignal, Recorder, qt_namespace, run_script, script_path, stub_module

OK = 1
PACKAGE = SimpleNamespace(isNull=False, id=3, master="Regular", masters=["Regular", "Bold"])

INFO = script_path("Font Info", "Font Info Panel Demo")
REVISIONS = script_path("Font Info", "Revisions Demo")
STYLES = script_path("Font Info", "Style Names Demo")
EDITOR = script_path("Features", "Features Editor Demo")
CLASSES = script_path("Features", "Feature Classes Demo")
CATEGORIES = script_path("Features", "Feature Categories Demo")
CODE = script_path("Features", "Feature Code Demo")

SAMPLES = [STYLES, CLASSES, CODE]


# --- Host stubs ------------------------------------------------------------------


def install_host(monkeypatch, package=PACKAGE, font=None, **gui_names):
    """Stub the natives; returns (QtGui, asked) like the other demo tests."""
    import fontlabapp.qt.dialogs as dialogs

    qt = qt_namespace(**gui_names)
    qt.QtGui.QMessageBox.Ok = OK
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(
        monkeypatch,
        "fontlab",
        MainWindow=lambda: "main-window",
        CurrentFont=lambda: font,
        flWorkspace=SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=package)),
    )
    asked = []

    def ask(_qt, parent, title, text, icon, buttons, default=None):
        asked.append((parent, title, text, icon, buttons, default))
        return OK

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


def report(monkeypatch, path) -> tuple[str, str, str]:
    """Run a sample demo with no font open and return its one message box."""
    gui, asked = install_host(monkeypatch, package=None)
    run_script(path)
    assert asked == [], "a sample demo asks nothing"
    return shown(gui)


def capture_dialog(monkeypatch) -> Recorder:
    """Record ``show_script_dialog`` calls instead of opening a window."""
    import fontlabapp.core.scripting as scripting

    recorder = Recorder("window")
    monkeypatch.setattr(scripting, "show_script_dialog", recorder)
    return recorder


# --- Sample demos ----------------------------------------------------------------


def test_style_names_demo_when_run_then_rules_abbreviate_name_and_link_styles(monkeypatch) -> None:
    title, text, details = report(monkeypatch, STYLES)
    assert title == "Style Names Demo" and text == "Sample style names. Nothing was read or written."
    assert "'Bold Italic': ['Bold', 'Italic'] -> BdIt -> SampleSans-BdIt" in details
    assert "'Semi Condensed Light': ['Semi', 'Condensed', 'Light'] -> SmCnLt -> SampleSans-SmCnLt" in details
    assert "'ExtraBold': ['Extra', 'Bold'] -> XBd -> SampleSans-XBd" in details
    assert "'': [] -> Rg -> SampleSans-Rg" in details, "an empty style becomes Rg"
    assert "  duplicate: SampleSans-Rg\n  'Sample' is not a valid PS name\n  SampleSansExtraLongFamily-BoldItalicCondensed is 45 chars (>29)" in details
    assert "'Bold Italic': Link(base='Regular', bold=True, italic=True)" in details
    assert "'Light Italic': Link(base='Light', bold=False, italic=True)" in details
    assert "'Black Italic': None" in details and "'Regular': None" in details


def test_classes_demo_when_run_then_only_classes_with_missing_names_are_rewritten(monkeypatch) -> None:
    title, text, details = report(monkeypatch, CLASSES)
    assert title == "Feature Classes Demo" and text == "Sample Clean Classes plan. Nothing was read or written."
    assert "@UPPER_ACCENTED\nBefore: A Aacute Agrave Aogonek\nAfter: A Aacute" in details
    assert "@Latin\nBefore: A B Cacute Cacute\nAfter: A B" in details
    assert "@lower\nBefore" not in details, "a class that names only existing glyphs is left alone"
    assert details.endswith("2 of 3 classes change.")


def test_code_demo_when_run_then_pairs_become_a_feature_block_and_a_bad_tag_is_refused(monkeypatch) -> None:
    title, text, details = report(monkeypatch, CODE)
    assert title == "Feature Code Demo" and text == "Sample feature code. Nothing was read or written."
    assert "safe_name: 'a.ss01' True, 'f_i' True, '1a' False, 'bad name' False" in details
    assert "suffix_pairs(names, '.ss01') -> [('a', 'a.ss01'), ('b', 'b.ss01'), ('f_i', 'f_i.ss01')]" in details
    assert "feature ss01 {\n    sub a by a.ss01;\n    sub b by b.ss01;\n    sub f_i by f_i.ss01;\n} ss01;" in details
    assert "feature_text('ss1', pairs) refused: Feature tag must contain four ASCII letters or digits." in details


@pytest.mark.parametrize("path", SAMPLES, ids=lambda path: path.stem)
def test_sample_demo_when_main_then_no_window_opens_and_no_font_is_needed(monkeypatch, path) -> None:
    opened = capture_dialog(monkeypatch)
    gui, asked = install_host(monkeypatch, package=None)
    run_script(path)
    assert opened.calls == [] and asked == []
    assert shown(gui)[2], "the details text is not empty"


# --- Fake panel shells -------------------------------------------------------------


class Label:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class Button:
    def __init__(self) -> None:
        self.text, self.enabled = "Apply", True

    def setText(self, text: str) -> None:
        self.text = text

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled


class InfoShell:
    """FontInfoDialog: binds the package, runs setup then refresh inside ``safe``."""

    package_source = None  # replaced per test by a subclass built in info_shell()

    def __init__(self, parent, *, title, subtitle, key) -> None:
        self.parent, self.title, self.subtitle, self.key = parent, title, subtitle, key
        self.package, self.status, self.apply_button = self.package_source, Label(), Button()
        self.table, self.writes = None, []
        self.safe(lambda: (self.setup(), self.refresh()))

    def safe(self, action):
        try:
            return action()
        except Exception as error:  # noqa: BLE001 - mirrors the real shell
            self.status.setText(str(error))
            self.apply_button.setEnabled(False)

    def ensure_font(self) -> None:
        if self.package is None:
            raise ValueError("Activate the original font and reopen this tool.")

    def rows(self, headings, rows) -> None:
        self.table = (headings, rows)


def info_package(**info):
    values = {
        "familyName": "Sample", "styleName": None, "ascender": 800, "descender": -200, "xHeight": 500, "capHeight": 700,
        "openTypeOS2TypoAscender": 800, "openTypeOS2TypoDescender": -200, "openTypeHheaAscender": 900,
        "openTypeHheaDescender": -250, "versionMajor": 1, "versionMinor": 2,
    }  # fmt: skip
    values.update(info)
    writes = []
    package = SimpleNamespace(isNull=False, id=3, master="Bold", info=SimpleNamespace(**values), writes=writes)
    package.setMaster = lambda *args: writes.append(args)
    return package


def open_info(monkeypatch, package):
    """Run the Font Info demo with a fake shell; returns (window, key, asked, opened)."""
    gui, asked = install_host(monkeypatch, package=package)
    shell = type("FontInfoDialog", (InfoShell,), {"package_source": package})
    stub_module(monkeypatch, "fontlabapp.fonts.info.ui", FontInfoDialog=shell)
    opened = capture_dialog(monkeypatch)
    run_script(INFO)
    kind, key = opened.calls[0][0]
    return kind(None), key, asked, opened


# --- Font Info Panel Demo -----------------------------------------------------------


def test_info_demo_when_font_open_then_panel_lists_the_fields_of_the_current_master(monkeypatch) -> None:
    package = info_package()
    window, key, asked, _ = open_info(monkeypatch, package)
    assert key == "font_info_panel_demo" and window.key == key and window.title == "Font Info Panel Demo" and asked == []
    headings, rows = window.table
    assert headings == ("Field", "Value") and len(rows) == 12
    assert rows[0] == ("familyName", "Sample") and rows[1] == ("styleName", ""), "a missing value shows as empty"
    assert rows[8] == ("openTypeHheaAscender", 900) and rows[-1] == ("versionMinor", 2)
    assert window.status.text == "12 fields of master Bold. Nothing changed."
    assert window.apply_button.text == "Apply (demo: no write)" and window.apply_button.enabled is False
    assert package.writes == [], "reading the info never switches the master"


def test_info_demo_when_apply_handler_runs_then_it_only_reports_and_writes_nothing(monkeypatch) -> None:
    import fontlabapp.core.scripting as scripting

    package = info_package()
    window, *_ = open_info(monkeypatch, package)
    monkeypatch.setattr(scripting, "write_font_info", Recorder())
    window.apply()
    assert window.status.text == "Demo only: nothing was written. Close the panel."
    assert scripting.write_font_info.calls == [] and package.writes == []
    assert vars(package.info) == vars(info_package().info), "the info values are unchanged"


def test_info_demo_when_a_field_cannot_be_read_then_the_shell_shows_the_error(monkeypatch) -> None:
    package = info_package()
    del package.info.ascender
    window, *_ = open_info(monkeypatch, package)
    assert "ascender" in window.status.text and window.table is None and window.apply_button.enabled is False


def test_info_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    gui, asked = install_host(monkeypatch, package=None)
    opened = capture_dialog(monkeypatch)
    run_script(INFO)
    assert opened.calls == [] and len(asked) == 1 and asked[0][2] == "Open a font first. The panel lists its Font Info."


@pytest.mark.parametrize("error", [ValueError("busy"), RuntimeError("busy"), TimeoutError("busy")])
def test_info_demo_when_show_fails_then_warning_names_the_error(monkeypatch, error) -> None:
    import fontlabapp.core.scripting as scripting

    gui, asked = install_host(monkeypatch)
    stub_module(monkeypatch, "fontlabapp.fonts.info.ui", FontInfoDialog=InfoShell)
    monkeypatch.setattr(scripting, "show_script_dialog", lambda kind, key: (_ for _ in ()).throw(error))
    run_script(INFO)
    assert len(asked) == 1 and asked[0][3] == "Warning" and asked[0][2] == "The panel did not open: busy"


# --- Revisions Demo ------------------------------------------------------------------


class RevisionPanel:
    KEY = "compare_open_font_revisions"


def test_revisions_demo_when_font_open_then_the_read_only_comparison_panel_opens_under_its_key(monkeypatch) -> None:
    gui, asked = install_host(monkeypatch)
    stub_module(monkeypatch, "fontlabapp.fonts.revisions.ui", RevisionCompareDialog=RevisionPanel)
    opened = capture_dialog(monkeypatch)
    run_script(REVISIONS)
    assert opened.calls == [((RevisionPanel, "compare_open_font_revisions"), {})]
    assert asked == [] and gui.QMessageBox.call_count == 0


def test_revisions_demo_when_no_font_then_the_sample_comparison_is_shown_and_no_panel_opens(monkeypatch) -> None:
    gui, asked = install_host(monkeypatch, package=None)
    opened = capture_dialog(monkeypatch)
    run_script(REVISIONS)
    title, text, details = shown(gui)
    assert opened.calls == [] and asked == []
    assert title == "Revisions Demo" and text == "Open a font first. Sample comparison of two made-up snapshots is in the details."
    assert details == "(font): glyph_order\nb: advance\nc: glyph_presence"


@pytest.mark.parametrize("error", [ValueError("busy"), RuntimeError("busy"), TimeoutError("busy")])
def test_revisions_demo_when_show_fails_then_warning_names_the_error(monkeypatch, error) -> None:
    import fontlabapp.core.scripting as scripting

    gui, asked = install_host(monkeypatch)
    stub_module(monkeypatch, "fontlabapp.fonts.revisions.ui", RevisionCompareDialog=RevisionPanel)
    monkeypatch.setattr(scripting, "show_script_dialog", lambda kind, key: (_ for _ in ()).throw(error))
    run_script(REVISIONS)
    assert len(asked) == 1 and asked[0][3] == "Warning" and asked[0][2] == "The panel did not open: busy"


def test_revisions_demo_when_the_panel_module_fails_to_load_then_warning_names_the_error(monkeypatch) -> None:
    gui, asked = install_host(monkeypatch)

    def no_native(name):
        raise RuntimeError("no native window class")

    stub_module(monkeypatch, "fontlabapp.fonts.revisions.ui", __getattr__=no_native)
    capture_dialog(monkeypatch)
    run_script(REVISIONS)
    assert len(asked) == 1 and asked[0][3] == "Warning" and asked[0][2] == "The panel did not open: no native window class"


# --- Features Categories Demo ---------------------------------------------------------


def categories_font(*glyphs):
    """A font whose glyphs are (name, [unicode values]); the id is the one the capture reads."""
    return SimpleNamespace(id=3, glyphs=[SimpleNamespace(id=index, name=name, unicodes=list(codes)) for index, (name, codes) in enumerate(glyphs)])


def test_categories_demo_when_font_open_then_panel_gets_the_marks_only_policy(monkeypatch) -> None:
    import fontlabapp.features.categories.model as model

    gui, asked = install_host(monkeypatch)
    shows = Recorder()
    monkeypatch.setattr(model, "show", shows)
    run_script(CATEGORIES)
    ((classify,), kwargs), = shows.calls
    assert kwargs == {} and asked == []
    assert classify("A", ["0041"]) == ("Base", None) and classify("g", []) == ("Base", None)
    assert classify("acutecomb", []) == ("Mark", None), "a name ending in comb is a mark"
    assert classify("x", ["0300"]) == ("Mark", None) and classify("x", ["036F"]) == ("Mark", None)
    assert classify("x", ["02FF"]) == ("Base", None) and classify("x", ["0370"]) == ("Base", None)
    assert classify("x", ["0041", "0301"]) == ("Mark", None), "any combining value makes a mark"


def test_categories_demo_when_policy_runs_on_the_real_capture_then_the_fragment_marks_combining_glyphs(monkeypatch) -> None:
    import fontlabapp.features.categories.model as model

    font = categories_font(("A", [65]), ("acutecomb", [0x301]), ("uni0302", [0x302]), (".notdef", []))
    install_host(monkeypatch, font=font)
    captured = []
    monkeypatch.setattr(model, "show", lambda classify: captured.append(model.render(model.capture(classify))))
    run_script(CATEGORIES)
    (fragment,) = captured
    assert "<key>A</key>\n      <string>base</string>" in fragment
    assert "<key>acutecomb</key>\n      <string>mark</string>" in fragment
    assert "<key>uni0302</key>\n      <string>mark</string>" in fragment
    assert "<key>.notdef</key>\n      <string>base</string>" in fragment


def test_categories_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    import fontlabapp.features.categories.model as model

    gui, asked = install_host(monkeypatch, package=None)
    shows = Recorder()
    monkeypatch.setattr(model, "show", shows)
    run_script(CATEGORIES)
    assert shows.calls == [] and len(asked) == 1 and asked[0][2] == "Open a font first. The panel lists its glyph categories."


@pytest.mark.parametrize("error", [ValueError("busy"), RuntimeError("busy"), TimeoutError("busy")])
def test_categories_demo_when_show_fails_then_warning_names_the_error(monkeypatch, error) -> None:
    import fontlabapp.features.categories.model as model

    gui, asked = install_host(monkeypatch)
    monkeypatch.setattr(model, "show", lambda classify: (_ for _ in ()).throw(error))
    run_script(CATEGORIES)
    assert len(asked) == 1 and asked[0][3] == "Warning" and asked[0][2] == "The panel did not open: busy"


# --- Features Editor Demo ---------------------------------------------------------------


class Edit:
    """A QLineEdit stand-in: ``text`` is a plain attribute, as in PythonQt."""

    def __init__(self, text: str = "") -> None:
        self.text, self.textChanged = text, FakeSignal()


class Preview:
    """A QPlainTextEdit stand-in that keeps its text."""

    def __init__(self) -> None:
        self.content, self.read_only = "", False

    def setReadOnly(self, flag: bool) -> None:
        self.read_only = flag

    def setPlainText(self, text: str) -> None:
        self.content = text

    def clear(self) -> None:
        self.content = ""


class FeaturesShell(InfoShell):
    """FeaturesDialog: ``prepare`` reads the glyph names and returns the content layout."""

    def __init__(self, parent, *, title, subtitle, key) -> None:
        self.connections, self.body, self.copied = [], SimpleNamespace(addLayout=Recorder(), addWidget=Recorder()), []
        super().__init__(parent, title=title, subtitle=subtitle, key=key)

    def prepare(self):
        self.names = sorted(self.package_names)
        return self.body

    def _connect(self, signal, slot) -> None:
        signal.connect(lambda *args: self.safe(lambda: slot(*args)))

    def copy_text(self, text: str) -> None:
        self.copied.append(text)


def open_editor(monkeypatch, names=("a", "a.ss01", "b", "b.ss01", "c.ss01"), package=PACKAGE):
    """Run the Features Editor demo with a fake shell; returns (window, key, asked, opened)."""
    gui, asked = install_host(monkeypatch, package=package, QLineEdit=Edit, QPlainTextEdit=Preview, QFormLayout=lambda: SimpleNamespace(rows=[], addRow=lambda label, edit: None))
    shell = type("FeaturesDialog", (FeaturesShell,), {"package_source": package, "package_names": tuple(names)})
    stub_module(monkeypatch, "fontlabapp.features.editor.ui", FeaturesDialog=shell)
    opened = capture_dialog(monkeypatch)
    run_script(EDITOR)
    kind, key = opened.calls[0][0]
    return kind(None), key, asked, opened


def test_editor_demo_when_font_open_then_panel_previews_the_suffix_pairs_of_the_glyph_names(monkeypatch) -> None:
    window, key, asked, _ = open_editor(monkeypatch)
    assert key == "features_editor_demo" and window.key == key and window.title == "Features Editor Demo" and asked == []
    assert window.tag_edit.text == "ss01" and window.suffix_edit.text == ".ss01"
    assert window.preview.read_only and window.preview.content == "feature ss01 {\n    sub a by a.ss01;\n    sub b by b.ss01;\n} ss01;"
    assert window.status.text == "2 suffix pairs among 5 glyphs. Nothing changed."
    assert window.apply_button.text == "Apply (demo: no write)" and window.apply_button.enabled is False


def test_editor_demo_when_tag_or_suffix_is_typed_then_the_preview_follows(monkeypatch) -> None:
    window, *_ = open_editor(monkeypatch)
    window.tag_edit.text = "salt"
    window.tag_edit.textChanged.emit("salt")
    assert window.preview.content.startswith("feature salt {") and window.status.text.startswith("2 suffix pairs")
    window.suffix_edit.text = "ss02"
    window.suffix_edit.textChanged.emit("ss02")
    assert window.preview.content == "feature salt {\n\n} salt;" and window.status.text == "0 suffix pairs among 5 glyphs. Nothing changed."


def test_editor_demo_when_tag_is_bad_then_preview_is_cleared_and_the_error_is_shown(monkeypatch) -> None:
    window, *_ = open_editor(monkeypatch)
    window.tag_edit.text = "ss1"
    window.tag_edit.textChanged.emit("ss1")
    assert window.preview.content == "" and window.status.text == "Feature tag must contain four ASCII letters or digits."
    assert window.apply_button.enabled is False


def test_editor_demo_when_apply_handler_runs_then_it_only_reports_and_never_copies(monkeypatch) -> None:
    window, *_ = open_editor(monkeypatch)
    window.apply()
    assert window.status.text == "Demo only: nothing was written. Close the panel." and window.copied == []


def test_editor_demo_when_no_font_then_says_so_and_opens_nothing(monkeypatch) -> None:
    gui, asked = install_host(monkeypatch, package=None)
    opened = capture_dialog(monkeypatch)
    run_script(EDITOR)
    assert opened.calls == [] and len(asked) == 1 and asked[0][2] == "Open a font first. The panel previews feature code for its glyphs."


@pytest.mark.parametrize("error", [ValueError("busy"), RuntimeError("busy"), TimeoutError("busy")])
def test_editor_demo_when_show_fails_then_warning_names_the_error(monkeypatch, error) -> None:
    import fontlabapp.core.scripting as scripting

    gui, asked = install_host(monkeypatch, QLineEdit=Edit, QPlainTextEdit=Preview)
    stub_module(monkeypatch, "fontlabapp.features.editor.ui", FeaturesDialog=FeaturesShell)
    monkeypatch.setattr(scripting, "show_script_dialog", lambda kind, key: (_ for _ in ()).throw(error))
    run_script(EDITOR)
    assert len(asked) == 1 and asked[0][3] == "Warning" and asked[0][2] == "The panel did not open: busy"


@pytest.mark.parametrize("path", [*SAMPLES, INFO, REVISIONS, EDITOR, CATEGORIES], ids=lambda path: path.stem)
def test_demo_when_imported_then_nothing_runs(monkeypatch, path) -> None:
    opened = capture_dialog(monkeypatch)
    gui, asked = install_host(monkeypatch)
    run_script(path, "imported")
    assert gui.QMessageBox.call_count == 0 and opened.calls == [] and asked == []
