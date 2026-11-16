# this_file: tests/test_demo_scripts_masters.py
"""Offline runs of the Scripts/Masters demos (Issue 208, Task 6).

Each demo runs through runpy as ``__main__`` (entry points and arguments are
asserted) and as an imported name (nothing may run). The real host-free
``fontlabapp`` modules stay in use, so the sample reports are computed by the
real models. ``PythonQt`` and ``fontlab`` are stubbed, and so are the two
painter modules that load Qt classes when imported. Fake fonts answer exactly
the reads the real models make and record every write attempt. Offline results
are not native FontLab acceptance.
"""

from types import SimpleNamespace

import pytest
from _demo_support import FakeSignal, Recorder, qt_namespace, run_script, script_path, stub_module

OK = 1
PACKAGE = SimpleNamespace(isNull=False, id=3, master="Regular", masters=["Regular", "Bold"])

BLEND = script_path("Masters", "Interpolation Blend Demo")
ANGLES = script_path("Masters", "Italic Angles Demo")
INSPECT = script_path("Masters", "Masters Inspect Demo")
SWITCHER = script_path("Masters", "Master Switcher Demo")
LAYERS = script_path("Masters", "Layers Samples Demo")
BACKGROUND = script_path("Masters", "Background Samples Demo")
REPORTS = script_path("Masters", "Master Reports Demo")
TEXT = script_path("Masters", "Master Text Demo")

SAMPLES = [LAYERS, BACKGROUND, REPORTS, TEXT]
WINDOWS = [BLEND, ANGLES]


# --- Host stubs and fake fonts --------------------------------------------------


def install_host(monkeypatch, package=PACKAGE, **fontlab_names):
    """Stub the natives; returns (QtGui, asked) like the other demo tests."""
    import fontlabapp.qt.dialogs as dialogs

    qt = qt_namespace()
    qt.QtGui.QMessageBox.Ok = OK
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(
        monkeypatch,
        "fontlab",
        MainWindow=lambda: "main-window",
        flWorkspace=SimpleNamespace(instance=lambda: SimpleNamespace(currentPackage=package)),
        **fontlab_names,
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


def report(monkeypatch, path, package=None, **fontlab_names) -> tuple[str, str, str]:
    """Run a message-box demo and return its one box (title, text, details)."""
    gui, asked = install_host(monkeypatch, package, **fontlab_names)
    run_script(path)
    assert asked == [], "a message-box demo asks nothing"
    return shown(gui)


def forbid_windows(monkeypatch) -> Recorder:
    """Replace ``show_script_dialog`` with a recorder the test asserts was never called."""
    import fontlabapp.core.scripting as scripting

    recorder = Recorder("window")
    monkeypatch.setattr(scripting, "show_script_dialog", recorder)
    return recorder


class FakeMasterFont:
    """A font with named masters, axis locations and per-master metrics; records setMaster."""

    isNull, id = False, 3

    def __init__(self, masters=("Bold", "Light"), locations=None, current="Bold"):
        self.masters, self.master = list(masters), current
        self.axes = [SimpleNamespace(shortName="wght", tag="wght")]
        self.locations = {"Bold": 700, "Light": 300} if locations is None else locations
        self.switches = []

    def location(self, master):
        return {"wght": self.locations[master]} if master in self.locations else {}

    def setMaster(self, *args):
        self.switches.append(args)


# --- Message-box demos: samples ---------------------------------------------------


def test_layers_demo_when_run_then_every_layer_model_reports_its_sample(monkeypatch) -> None:
    title, text, details = report(monkeypatch, LAYERS)
    assert title == "Layers Samples Demo" and text == "Sample layer reports. Nothing was read or written."
    assert "Glyphs with Bracket Layers (1):\na\n\nAffected Components (1):\naacute\n\nTotal affected glyphs: 2" in details
    assert "A is not compatible\npath 1, node count differ:\n  Light has 3\n  Regular has 4" in details
    assert "anchors differ:\n  Light has top\n  Regular has bottom, top" in details
    compatibility = details.split("Layer compatibility:")[1].split("Highest and lowest layers:")[0]
    assert "Bold" not in compatibility, "Bold matches Regular, so no difference names it"
    assert "highest: 960\nlowest: -240\n\nHighest: Aacute [Bold]\nLowest: g [Light]" in details
    assert "a [Regular]\na [Bold]\n(line break)\nb [Regular]\n(line break)" in details
    assert "lost" not in details, "a group without a parent is skipped"
    assert "next from id1: id1 -> id2" in details and "next from id3: id3 -> id1 (wraps)" in details
    assert "if the source changed before writing: Navigation source changed; capture again" in details


def test_background_demo_when_run_then_transforms_and_both_clearing_scopes_are_planned(monkeypatch) -> None:
    title, text, details = report(monkeypatch, BACKGROUND)
    assert title == "Background Samples Demo" and text == "Sample background results. Nothing was read or written."
    assert "scale 50: nodes ((100.0, 200.0), (400.0, 650.0)) -> ((50.0, 100.0), (200.0, 325.0)); component x 50 -> 50" in details
    assert "shift 30: nodes ((100.0, 200.0), (400.0, 650.0)) -> ((130.0, 200.0), (430.0, 650.0)); component x 50 -> 80" in details
    assert "(repeat=2) to the first node: ((25.0, 50.0),)" in details
    assert "selected_paths((all, some, none, all)) -> (0, 3)" in details
    assert "numeric('12.5') -> 12.5" in details and "numeric('twelve') refused: Enter a finite number." in details
    assert "All layers: A / Regular background (owners [1]), A / trial background (owners [3])" in details
    assert "Masters only: A / Regular background (owners [1])" in details


def test_background_demo_when_plan_finds_nothing_then_says_nothing(monkeypatch) -> None:
    import fontlabapp.masters.background.clear.model as clear

    monkeypatch.setattr(clear, "plan", lambda source, masters: ())
    _, _, details = report(monkeypatch, BACKGROUND)
    assert "All layers: nothing\nMasters only: nothing" in details


def test_reports_demo_when_run_then_node_report_flags_bold_and_point_counter_marks_rows(monkeypatch) -> None:
    title, text, details = report(monkeypatch, REPORTS)
    assert title == "Master Reports Demo" and text == "Sample master reports. Nothing was read or written."
    assert "🔠 Glyph: o" in details and "⭕️ Master: Light\n     • Paths: 2" in details
    assert "Incompatibility in master 'Bold':\n     • Path #1 mismatch → Expected (4, 0), Found (4, 2)" in details
    assert "First difference at node #2: Expected LINE, Found CURVE" in details
    assert "Path #2 → Path missing in tested master." in details
    assert details.count("Incompatibility in master 'Light'") == 0 and "Masters are not compatible with the reference master." in details
    assert "Layer: Light\nTotal: 28 Points - 16 Handles, 12 Nodes, 2 Paths" in details
    assert "Layer: Bold\nTotal: 31 Points - 18 Handles, 13 Nodes, 2 Paths" in details


def test_text_demo_when_run_then_words_become_rows_and_dropped_characters_are_listed(monkeypatch) -> None:
    title, text, details = report(monkeypatch, TEXT)
    assert title == "Master Text Demo" and text == "Sample master text comparison. Nothing was read or written."
    assert "Unicode aliases: [('U+0061', 'a', 'a.alt')]" in details
    assert "analyze('Ha,Hz,xyz', side by side, characters): 2 words, 10 slots" in details
    assert "preview: 'Ha Ha \\nH H \\n'" in details
    assert "dropped: [(1, 1, 'z', 'character'), (2, 0, 'x', 'character'), (2, 1, 'y', 'character'), (2, 2, 'z', 'character')]; empty fields: [2]" in details
    assert "analyze('Ha,Hz,xyz', stacked, characters): 2 words, 6 slots" in details and "preview: 'Ha\\nHa\\n\\nH\\nH\\n\\n'" in details
    assert "(1, 0, '/nope', 'token')" in details and "preview: '/Aacute/a.alt /Aacute/a.alt \\n'" in details
    assert "analyze('xyz') refused: No usable glyphs remain after sanitation; no proof opened." in details
    assert "select_text('Hamburg', presets, 1) -> Hamburg" in details
    assert "select_text('', presets, 1) -> Arrowroot,Barley,Chervil,Dumpl..." in details
    assert "immediate=3) -> 00000,00100" in details


@pytest.mark.parametrize("path", SAMPLES, ids=lambda path: path.stem)
def test_sample_demo_when_main_then_no_window_opens_and_no_font_is_needed(monkeypatch, path) -> None:
    opened = forbid_windows(monkeypatch)
    gui, asked = install_host(monkeypatch, package=None)
    run_script(path)
    assert opened.calls == [] and asked == []
    assert shown(gui)[2], "the details text is not empty"


# --- Masters Inspect Demo ---------------------------------------------------------


def metrics_for(package, master):
    base = {"Bold": 760, "Light": 740}[master]
    return SimpleNamespace(ascender=base, capsHeight=700, xHeight=500.5, descender=-240)


def test_inspect_demo_when_font_open_then_masters_are_listed_in_axis_order_with_metrics(monkeypatch) -> None:
    font = FakeMasterFont()
    title, text, details = report(monkeypatch, INSPECT, font, FontMetrics=metrics_for)
    assert title == "Masters Inspect Demo" and text == "Masters of the open font, with sample helpers. Nothing was written."
    assert details.startswith("Masters of the open font:\nLight (wght 300): Ascender 740, Cap height 700, x-height 500.5, Descender -240\nBold (wght 700): Ascender 760")
    assert font.switches == [], "the demo never switches the current master"


def test_inspect_demo_when_helpers_run_then_samples_use_the_real_functions(monkeypatch) -> None:
    _, _, details = report(monkeypatch, INSPECT)
    assert "No font is open." in details
    assert "nice_ticks(0, 83) -> [0, 20, 40, 60, 80, 100]" in details
    assert "associated_master('Regular@ 2026-10-21') -> Regular" in details and "associated_master('mask.Regular') -> None" in details
    assert "backup_master('Bold backup trial') -> Bold" in details
    assert "backup_layer_name('Regular', taken, 'first') -> Regular backup first (2)" in details
    assert "ink_area(box 400 x 700 with a 200 x 500 counter) -> 180000" in details


@pytest.mark.parametrize("error", [ValueError("two masters share a name"), RuntimeError("native read failed")])
def test_inspect_demo_when_master_read_fails_then_error_line_replaces_masters_and_samples_stay(monkeypatch, error) -> None:
    def failing(package, master):
        raise error

    _, _, details = report(monkeypatch, INSPECT, FakeMasterFont(), FontMetrics=failing)
    assert f"The masters could not be read: {error}" in details and "nice_ticks(0, 83)" in details


# --- Master Switcher Demo ---------------------------------------------------------


def test_switcher_demo_when_font_open_then_buttons_are_listed_and_nothing_is_switched(monkeypatch) -> None:
    font = FakeMasterFont()
    title, text, details = report(monkeypatch, SWITCHER, font)
    assert title == "Master Switcher Demo" and text == "2 master buttons. Nothing was switched or written."
    assert details == "[Light · 300]\n[Bold · 700]  (current master)"
    assert font.switches == []


def test_switcher_demo_when_font_has_no_axes_then_button_has_no_label(monkeypatch) -> None:
    font = FakeMasterFont(masters=("Regular",), current="Regular")
    font.axes = []
    _, _, details = report(monkeypatch, SWITCHER, font)
    assert details == "[Regular]  (current master)"


def test_switcher_demo_when_no_font_then_says_so(monkeypatch) -> None:
    gui, asked = install_host(monkeypatch, package=None)
    run_script(SWITCHER)
    assert gui.QMessageBox.call_count == 1
    assert gui.QMessageBox.return_value.setText.call_args[0][0] == "Master Switcher Demo"
    assert gui.QMessageBox.return_value.setInformativeText.call_args[0][0] == "Open a font first. The demo previews its master buttons."
    assert not gui.QMessageBox.return_value.setDetailedText.called and asked == []


def test_switcher_demo_when_master_names_repeat_then_the_refusal_is_shown(monkeypatch) -> None:
    font = FakeMasterFont(masters=("Bold", "Bold"))
    gui, asked = install_host(monkeypatch, font)
    run_script(SWITCHER)
    assert gui.QMessageBox.return_value.setInformativeText.call_args[0][0] == "The master buttons could not be read: Master names must be unique before switching."
    assert font.switches == []


# --- Interpolation Blend Demo and Italic Angles Demo -------------------------------


class Dialog:
    """A QDialog stand-in with the two signals the demo and OwnedWidget use."""

    def __init__(self, parent) -> None:
        self.parent, self.finished, self.destroyed = parent, FakeSignal(), FakeSignal()

    def __getattr__(self, name: str):  # every other Qt call is recorded and succeeds
        return Recorder()


class Label:
    def __init__(self, text: str, parent) -> None:
        self.text = text

    def setText(self, text: str) -> None:
        self.text = text


class Slider:
    def __init__(self, orientation, parent) -> None:
        self.orientation, self.valueChanged, self.limits, self.value = orientation, FakeSignal(), None, None

    def setRange(self, low: int, high: int) -> None:
        self.limits = (low, high)

    def setValue(self, value: int) -> None:
        self.value = value


class BlendView:
    """The painter: plain attributes the demo fills, and a count of repaints."""

    def __init__(self, parent) -> None:
        self.parent, self.a, self.b, self.mix, self.size, self.repaints = parent, None, None, [], None, 0

    def setMinimumSize(self, width: int, height: int) -> None:
        self.size = (width, height)

    def update(self) -> None:
        self.repaints += 1


class Gauge:
    def __init__(self, parent) -> None:
        self.parent, self.masters, self.angles = parent, None, None

    def set_angles(self, angles) -> None:
        self.angles = angles


def window_host(monkeypatch, shots, package=None, failing=None, **fontlab_names):
    """Stub PythonQt widgets and the two painter modules; ``shots`` collects single-shot calls."""
    gui, _ = install_host(monkeypatch, package, **fontlab_names)
    widgets = {"QDialog": Dialog, "QLabel": Label, "QSlider": Slider}
    for name in failing or ():

        def broken(*args, name=name):
            raise RuntimeError("no " + name)

        widgets[name] = broken
    for name, kind in widgets.items():
        setattr(gui, name, kind)
    sys_qt = __import__("sys").modules["PythonQt"]
    sys_qt.QtCore.QTimer.singleShot = lambda delay, call: shots.append((delay, call))
    stub_module(monkeypatch, "fontlabapp.masters.interpolation.view", BlendView=BlendView)
    stub_module(monkeypatch, "fontlabapp.masters.angles.views", Gauge=Gauge)
    return gui, sys_qt


def widgets_of(gui):
    return [call[0][0] for call in gui.QVBoxLayout.return_value.addWidget.call_args_list]


def node(x, y, on=True):
    return SimpleNamespace(x=x, y=y, isOn=lambda: on)


def fake_layer(*contours, flipped=False):
    """A layer whose shapes hold the given contours; each is a list of (x, y, on)."""
    transform = SimpleNamespace(isIdentity=lambda: True)
    shapes = [
        SimpleNamespace(transform=transform, contours=[SimpleNamespace(nodes=lambda points=points: [node(*point) for point in points])])
        for points in contours
    ]
    return SimpleNamespace(shapes=shapes, isNull=False)


def glyph_font(layers, masters=("Light", "Bold"), names=("A",), missing=False):
    """A package whose glyph ``A`` has the given {master: layer}; ``missing`` makes findName return None."""
    glyph = SimpleNamespace(isNull=False, findLayer=lambda master: layers.get(master))
    return SimpleNamespace(
        isNull=False, id=3, master=masters[0], masters=list(masters), axes=[],
        findName=lambda name: None if missing else glyph,
    )  # fmt: skip


SQUARE = [(0, 0, True), (200, 0, True), (200, 200, True), (0, 200, True)]
BIG_SQUARE = [(0, 0, True), (400, 0, True), (400, 400, True), (0, 400, True)]


def select(monkeypatch, names=("A",), error=None):
    """Make the interpolation model's selection read return ``names`` (or raise ``error``)."""
    import fontlabapp.masters.interpolation.model as model

    def selected():
        if error:
            raise error
        return list(names)

    monkeypatch.setattr(model, "selected_names", selected)


def mix_points(view):
    return [[(round(x, 6), round(y, 6), on) for x, y, on in contour] for contour in view.mix]


def test_blend_demo_when_no_font_then_sample_outlines_blend_with_the_slider(monkeypatch) -> None:
    gui, qt = window_host(monkeypatch, [])
    handles = run_script(BLEND)["_HANDLES"]
    (demo,) = handles
    label, view, slider = widgets_of(gui)
    assert demo.owned.widget.parent == "main-window" and view.parent is demo.owned.content and view.size == (520, 380)
    assert slider.limits == (0, 100) and slider.value == 50 and slider.orientation is qt.QtCore.Qt.Horizontal
    assert label.text == "Sample outlines (No font is open)\nMix: 50% of the way from the first outline to the second"
    assert [p[2] for p in view.a[0]] == [p[2] for p in view.b[0]] and view.a[0][3][:2] == (600, 350)
    assert view.b[0][3][:2] == (100 + 500 * 1.6 + 350 * 0.25, 350), "the second sample is wider and leaning"
    first, second = view.a[0][3], view.b[0][3]
    assert view.mix[0][3][:2] == pytest.approx(((first[0] + second[0]) / 2, 350))
    slider.valueChanged.emit(100)
    assert mix_points(view) == [[(round(x, 6), round(y, 6), on) for x, y, on in view.b[0]]] and view.repaints == 2
    assert label.text.endswith("Mix: 100% of the way from the first outline to the second")
    slider.valueChanged.emit(0)
    assert mix_points(view)[0][3][:2] == (600, 350)


def test_blend_demo_when_glyph_is_selected_then_its_first_and_last_master_are_blended(monkeypatch) -> None:
    font = glyph_font({"Light": fake_layer(SQUARE), "Bold": fake_layer(BIG_SQUARE)})
    gui, _ = window_host(monkeypatch, [], package=font)
    select(monkeypatch)
    run_script(BLEND)
    label, view, slider = widgets_of(gui)
    assert label.text.startswith("A: Light to Bold\nMix: 50%")
    assert view.a == [SQUARE] and view.b == [BIG_SQUARE]
    assert mix_points(view) == [[(0, 0, True), (300, 0, True), (300, 300, True), (0, 300, True)]]


@pytest.mark.parametrize(
    "build,names,reason",
    [
        ("one master", ("A",), "Select a glyph in a font with two or more masters"),
        ("no selection", (), "Select a glyph in a font with two or more masters"),
        ("missing glyph", ("A",), "A is not in the font"),
        ("missing layer", ("A",), "A lacks a layer in Light or Bold"),
        ("incompatible", ("A",), "A cannot interpolate: 1 vs 2 contours"),
    ],
)
def test_blend_demo_when_font_cannot_be_blended_then_samples_are_used_and_the_reason_is_shown(monkeypatch, build, names, reason) -> None:
    layers = {"Light": fake_layer(SQUARE), "Bold": fake_layer(BIG_SQUARE)}
    font = {
        "one master": glyph_font(layers, masters=("Light",)),
        "no selection": glyph_font(layers),
        "missing glyph": glyph_font(layers, missing=True),
        "missing layer": glyph_font({"Light": fake_layer(SQUARE)}),
        "incompatible": glyph_font({"Light": fake_layer(SQUARE), "Bold": fake_layer(BIG_SQUARE, SQUARE)}),
    }[build]
    gui, _ = window_host(monkeypatch, [], package=font)
    select(monkeypatch, names)
    run_script(BLEND)
    label, view, _ = widgets_of(gui)
    assert label.text.startswith(f"Sample outlines ({reason})\n") and len(view.a[0]) == 12


@pytest.mark.parametrize("error", [ValueError("selection unreadable"), RuntimeError("selection unreadable")])
def test_blend_demo_when_the_font_read_fails_then_samples_are_used_and_the_error_is_shown(monkeypatch, error) -> None:
    gui, _ = window_host(monkeypatch, [], package=glyph_font({}))
    select(monkeypatch, error=error)
    run_script(BLEND)
    label, view, _ = widgets_of(gui)
    assert label.text.startswith("Sample outlines (The font could not be read (selection unreadable))\n") and len(view.a[0]) == 12


def test_blend_demo_when_window_finishes_then_releases_on_next_turn_and_closes_the_scope(monkeypatch) -> None:
    shots = []
    gui, _ = window_host(monkeypatch, shots)
    handles = run_script(BLEND)["_HANDLES"]
    (demo,) = handles
    _, view, slider = widgets_of(gui)
    dialog = demo.owned.widget
    dialog.finished.emit(0)
    assert [delay for delay, _ in shots] == [0] and handles == [demo], "release waits for Qt dispatch to return"
    shots[0][1]()
    assert handles == [] and demo.scope.closed and demo.owned.closed
    assert slider.valueChanged.slots == [] and dialog.finished.slots == []
    slider.valueChanged.emit(10)
    assert view.repaints == 1, "a closed scope must ignore the slider"
    demo.release()  # a second release is harmless
    assert demo.problems == []


def test_blend_demo_when_release_fails_then_handle_still_leaves(monkeypatch) -> None:
    window_host(monkeypatch, [])
    handles = run_script(BLEND)["_HANDLES"]
    (demo,) = handles
    demo.scope.finish = Recorder()
    demo.owned.close = Recorder()
    demo.release()
    assert handles == [] and demo.scope.finish.calls == [((), {})] and demo.owned.close.calls == [((), {})]

    def broken():
        raise RuntimeError("scope refused")

    handles.append(demo)
    demo.scope.finish = broken
    with pytest.raises(RuntimeError, match="scope refused"):
        demo.release()
    assert handles == []


@pytest.mark.parametrize("failing", ["QDialog", "QSlider"])
@pytest.mark.parametrize("path", WINDOWS, ids=lambda path: path.stem)
def test_window_demo_when_window_creation_fails_then_releases_and_reraises(monkeypatch, path, failing) -> None:
    window_host(monkeypatch, [], failing=[failing])
    names = run_script(path, "imported")
    with pytest.raises(RuntimeError, match="no " + failing):
        names["main"]()
    assert names["_HANDLES"] == []


def test_angles_demo_when_run_then_gauge_shows_three_masters_leaning_with_the_slider(monkeypatch) -> None:
    from fontlabapp.masters.angles import model

    gui, qt = window_host(monkeypatch, [])
    handles = run_script(ANGLES)["_HANDLES"]
    (demo,) = handles
    label, gauge, slider, notes = widgets_of(gui)
    assert demo.owned.widget.parent == "main-window" and gauge.parent is demo.owned.content
    assert slider.limits == (-45, 45) and slider.value == -12 and slider.orientation is qt.QtCore.Qt.Horizontal
    assert gauge.masters == ["Light", "Regular", "Bold"] and gauge.angles == [("Light", -4.0), ("Regular", -8.0), ("Bold", -12.0)]
    assert label.text == "Italic angle: Light -4°, Regular -8°, Bold -12°"
    slider.valueChanged.emit(30)
    assert gauge.angles == [("Light", 10.0), ("Regular", 20.0), ("Bold", 30.0)] and label.text.endswith("Bold 30°")
    expected = [f"blueScale {value}: Undo keeps it exactly: {model.history_preserves_blue_scale(value)}" for value in (0.039625, 0.04, 0.03333333333)]
    assert notes.text == "\n".join(expected) and "blueScale 0.039625: Undo keeps it exactly: True" in notes.text


def test_angles_demo_when_window_finishes_then_releases_on_next_turn(monkeypatch) -> None:
    shots = []
    gui, _ = window_host(monkeypatch, shots)
    handles = run_script(ANGLES)["_HANDLES"]
    (demo,) = handles
    _, gauge, slider, _ = widgets_of(gui)
    demo.owned.widget.finished.emit(0)
    shots[0][1]()
    assert handles == [] and slider.valueChanged.slots == [] and demo.scope.closed
    slider.valueChanged.emit(5)
    assert gauge.angles == [("Light", -4.0), ("Regular", -8.0), ("Bold", -12.0)], "a closed scope must ignore the slider"


@pytest.mark.parametrize("path", [*SAMPLES, INSPECT, SWITCHER, *WINDOWS], ids=lambda path: path.stem)
def test_demo_when_imported_then_nothing_runs(monkeypatch, path) -> None:
    opened = forbid_windows(monkeypatch)
    gui, _ = window_host(monkeypatch, [])
    names = run_script(path, "imported")
    assert gui.QMessageBox.call_count == 0 and opened.calls == []
    assert names.get("_HANDLES", []) == [] and gui.QVBoxLayout.call_count == 0
