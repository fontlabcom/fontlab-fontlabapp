# this_file: tests/test_renderer_palettes_qt.py
"""Real contours and Qt pixels across independent chrome/canvas palettes."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from _studio_qt import APP, gui_namespace
from _tglyph_fakes import layered_font

MODULES = ("_canvas_palette", "tglyph", "tmetrics", "lifecycle")


@pytest.fixture
def renderers(monkeypatch):
    gui = gui_namespace()
    # Expose the same known properties as FontLab's PythonQt binding.
    gui.QWidget = type("Widget", (QtWidgets.QWidget,), {
        name: property(getattr(QtWidgets.QWidget, name)) for name in ("width", "height", "rect", "palette")
    })
    for name, properties in {
        "QLineEdit": {"text": "text"},
        "QComboBox": {"currentIndex": "currentIndex", "count": "count"},
        "QCheckBox": {"checked": "isChecked"},
        "QSpinBox": {"value": "value"},
        "QLabel": {"text": "text"},
    }.items():
        base = getattr(QtWidgets, name)
        setattr(gui, name, type(name, (base,), {
            prop: property(getattr(base, method)) for prop, method in properties.items()
        }))

    class Scroll(QtWidgets.QScrollArea):
        def viewport(self):
            return NS(width=super().viewport().width())

        def horizontalScrollBar(self):
            bar = super().horizontalScrollBar()
            return NS(value=bar.value(), setValue=bar.setValue)

        def verticalScrollBar(self):
            bar = super().verticalScrollBar()
            return NS(value=bar.value(), setValue=bar.setValue)

    gui.QScrollArea = Scroll
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in MODULES:
        monkeypatch.delitem(sys.modules, "fontlabapp.fontui." + name, raising=False)
    tg = importlib.import_module("fontlabapp.fontui.tglyph")
    tm = importlib.import_module("fontlabapp.fontui.tmetrics")
    yield tg, tm
    for name in MODULES:
        sys.modules.pop("fontlabapp.fontui." + name, None)


def palette(dark):
    result = QtGui.QPalette()
    for role, color in ((QtGui.QPalette.Base, "#202124" if dark else "#ffffff"),
                        (QtGui.QPalette.Text, "#eeeeee" if dark else "#202124"),
                        (QtGui.QPalette.Window, "#202124" if dark else "#ffffff"),
                        (QtGui.QPalette.WindowText, "#eeeeee" if dark else "#202124"),
                        (QtGui.QPalette.Highlight, "#315984" if dark else "#c4ddf8"),
                        (QtGui.QPalette.HighlightedText, "#ffffff" if dark else "#101820")):
        result.setColor(role, QtGui.QColor(color))
    return result


def owner_for(module, metrics):
    font = layered_font()
    errors = []
    if metrics:
        model = module.TMetricsModel(font, layer=font.defaultLayerName)
        model.settings = model.settings.__class__(text="/a /a", size=160)
        model.reshape()
        model.select(0)
        owner = NS(model=model, layout_geometry=model.geometry(640),
                   outlines={"a": module._outline(model, "a")})
        assert owner.outlines["a"].recording
    else:
        model = module.TGlyphModel(font, layer=font.defaultLayerName)
        model.load("a")
        model.fit(640, 480)
        model.selection = {(0, 1)}
        owner = NS(model=model, overlay=model.data, highlights={"points": frozenset({(0, 0)}),
                   "segments": frozenset(), "anchors": frozenset({"top"})},
                   fit=lambda: model.fit(640, 480), editor=NS(band=(30, 30, 70, 70), pending=model.data.contours[0].points[0]), closed=False)
        assert model.data.contours
    owner.fail = errors.append
    return owner, errors


@pytest.mark.parametrize("metrics", [False, True], ids=["glyph", "metrics"])
@pytest.mark.parametrize("chrome_dark,canvas_dark", [(False, False), (True, False), (True, True), (False, True)])
def test_real_contours_when_palette_changes_then_pixels_and_state_follow(renderers, metrics, chrome_dark, canvas_dark):
    module = renderers[int(metrics)]
    owner, errors = owner_for(module, metrics)
    root = QtWidgets.QWidget()
    root.setPalette(palette(chrome_dark))
    canvas = module.create_canvas(owner, root)
    canvas.resize(640, 480)
    root.resize(640, 480)
    root.show()
    original_colors = module.COLORS.copy()
    state = repr(owner.model)
    try:
        for dark in (canvas_dark, not canvas_dark, canvas_dark):
            canvas.setPalette(palette(dark))
            canvas.update()
            APP.processEvents()
            image = canvas.grab().toImage()
            assert not errors, errors
            assert image.pixelColor(639, 479).lightness() < 128 if dark else image.pixelColor(639, 479).lightness() > 128
            colors = {image.pixelColor(x, y).name() for x in range(0, 640, 2) for y in range(0, 480, 2)}
            assert len(colors) > (5 if metrics else 12), "real geometry and semantic marks must be visible"
            if metrics:
                x, baseline = owner.layout_geometry.origins[0]
                inside = image.pixelColor(int(x + 50 * owner.layout_geometry.scale), int(baseline - 100 * owner.layout_geometry.scale))
                outside = image.pixelColor(int(x + 350 * owner.layout_geometry.scale), int(baseline - 100 * owner.layout_geometry.scale))
            else:
                inside = image.pixelColor(*map(int, owner.model.view.to_screen(50, 100)))
                outside = image.pixelColor(*map(int, owner.model.view.to_screen(350, 100)))
            assert abs(inside.lightness() - outside.lightness()) > 15, "filled glyph must contrast with its canvas/selected box"
        assert module.COLORS == original_colors
        assert repr(owner.model) == state
    finally:
        canvas.close()
        root.close()
        canvas.deleteLater()
        root.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("native_dark,canvas_dark,expected", [(False, True, False), (True, False, False), (True, True, True)])
def test_native_policy_when_no_owned_palette_then_reads_boolean_pair_only(renderers, monkeypatch, native_dark, canvas_dark, expected):
    helper = importlib.import_module("fontlabapp.fontui._canvas_palette")
    class Preferences:
        __slots__ = ()
        isDark = native_dark
        generalDarkGlyph = canvas_dark
    monkeypatch.setitem(sys.modules, "fontlab", NS(flPreferences=lambda: Preferences()))
    widget = QtWidgets.QWidget()
    colors = helper._canvas_colors(widget, renderers[0].COLORS)
    assert (QtGui.QColor(colors["background"]).lightness() < 128) is expected
    widget.deleteLater()


@pytest.mark.parametrize("metrics", [False, True], ids=["glyph", "metrics"])
@pytest.mark.parametrize("controls", [False, True])
def test_real_window_when_embedded_then_compact_readable_and_owned_cleanup(renderers, metrics, controls):
    module = renderers[int(metrics)]
    font = layered_font()
    callbacks = []
    host = NS(subscribe=lambda owner, callback, fonts, text_callback=None: callbacks.append(callback))
    owner = (module.TMetrics(font, text="/a /a", controls=controls, read_only=True, host=host)
             if metrics else module.TGlyph(font, "a", controls=controls, read_only=True, host=host))
    try:
        owner.widget.resize(640, 480)
        owner.widget.show()
        APP.processEvents()
        margins = owner.layout.contentsMargins()
        if not controls:
            assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
            assert owner.layout.spacing() == 0
            if metrics:
                assert owner.scroll.frameShape() == QtWidgets.QFrame.NoFrame
        else:
            assert margins.left() > 0
        assert owner.diagnostic.isVisible() and owner.readout.isVisible()
        assert not owner.diagnostic.text.startswith("Error:"), owner.diagnostic.text
        assert owner.canvas.grab().toImage().width() > 100
        assert owner.model.cells if metrics else owner.model.data.contours
    finally:
        owner.close()
        assert owner.closed and owner._close_complete and not owner.connections
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("metrics", [False, True], ids=["glyph", "metrics"])
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_semantic_palette_when_disabled_or_native_unavailable_then_complete_and_readable(renderers, monkeypatch, metrics, dark, enabled):
    helper = importlib.import_module("fontlabapp.fontui._canvas_palette")
    module = renderers[int(metrics)]
    monkeypatch.setitem(sys.modules, "fontlab", NS())
    widget = QtWidgets.QWidget()
    widget.setPalette(palette(dark))
    widget.setEnabled(enabled)
    colors = helper._canvas_colors(widget, module.COLORS)
    assert set(module.COLORS) <= colors.keys()
    assert all(QtGui.QColor(color).isValid() for color in colors.values())
    background = QtGui.QColor(colors["background"]).lightness()
    assert all(abs(QtGui.QColor(colors[key]).lightness() - background) > 30
               for key in ("guide", "baseline", "bearing", "missing") if key in colors)
    assert abs(QtGui.QColor(colors["selection_background"]).lightness() - QtGui.QColor(colors["selection_foreground"]).lightness()) > 80
    widget.deleteLater()


@pytest.mark.parametrize("bad", [None, 0, 1, "false"])
def test_native_policy_when_non_bool_then_inherited_palette_fallback(renderers, monkeypatch, bad):
    helper = importlib.import_module("fontlabapp.fontui._canvas_palette")
    monkeypatch.setitem(sys.modules, "fontlab", NS(flPreferences=lambda: NS(isDark=True, generalDarkGlyph=bad)))
    parent = QtWidgets.QWidget()
    parent.setPalette(palette(True))
    widget = QtWidgets.QWidget(parent)
    assert not widget.testAttribute(QtCore.Qt.WA_SetPalette)
    colors = helper._canvas_colors(widget, renderers[0].COLORS)
    assert colors["background"] == "#202124"
    parent.deleteLater()


def test_owned_palette_when_native_exists_then_no_native_access(renderers, monkeypatch):
    helper = importlib.import_module("fontlabapp.fontui._canvas_palette")
    def forbidden():
        raise AssertionError("explicit owned palette must not read native preferences")
    monkeypatch.setitem(sys.modules, "fontlab", NS(flPreferences=forbidden))
    widget = QtWidgets.QWidget()
    widget.setPalette(palette(True))
    assert helper._canvas_colors(widget, renderers[0].COLORS)["background"] == "#202124"
    widget.deleteLater()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("kern", [-80, 80])
def test_real_kerning_when_signed_then_semantic_pixels_survive_palette(renderers, dark, kern):
    module = renderers[1]
    owner, errors = owner_for(module, True)
    owner.model.font.kerning[("a", "a")] = kern
    owner.model.reshape()
    owner.layout_geometry = owner.model.geometry(640)
    assert owner.model.cells[0].kern == kern
    canvas = module.create_canvas(owner, None)
    canvas.resize(640, 480)
    canvas.setPalette(palette(dark))
    try:
        image = canvas.grab().toImage()
        assert not errors
        geometry = owner.layout_geometry
        cell = owner.model.cells[0]
        x, baseline = geometry.origins[0]
        probe = image.pixelColor(int(x + cell.width * geometry.scale + kern * geometry.scale / 2), int(baseline + 2))
        assert probe.red() > probe.green() if kern < 0 else probe.green() > probe.red()
    finally:
        canvas.close()
        canvas.deleteLater()


@pytest.mark.parametrize("dark", [False, True])
def test_real_component_when_composite_then_contour_pixels_are_visible(renderers, dark):
    module = renderers[0]
    owner, errors = owner_for(module, False)
    owner.model.load("b")
    owner.model.fit(640, 480)
    owner.overlay = None
    canvas = module.create_canvas(owner, None)
    canvas.resize(640, 480)
    canvas.setPalette(palette(dark))
    try:
        image = canvas.grab().toImage()
        assert not errors
        component = image.pixelColor(*map(int, owner.model.view.to_screen(60, 120)))
        outside = image.pixelColor(*map(int, owner.model.view.to_screen(350, 120)))
        assert abs(component.lightness() - outside.lightness()) > 30
    finally:
        canvas.close()
        canvas.deleteLater()


@pytest.mark.parametrize("metrics", [False, True], ids=["glyph", "metrics"])
@pytest.mark.parametrize("dark_canvas", [False, True])
def test_native_policy_when_chrome_dark_then_actual_canvas_pixels_use_native_flags(renderers, monkeypatch, metrics, dark_canvas):
    module = renderers[int(metrics)]
    accesses = []
    class Preferences:
        __slots__ = ()
        def __getattribute__(self, name):
            accesses.append(name)
            if name == "isDark":
                return True
            if name == "generalDarkGlyph":
                return dark_canvas
            raise AssertionError(f"unexpected preference access {name}")
        def __setattr__(self, name, value):
            raise AssertionError(f"preference write {name}")
    monkeypatch.setitem(sys.modules, "fontlab", NS(flPreferences=lambda: Preferences()))
    owner, errors = owner_for(module, metrics)
    root = QtWidgets.QWidget()
    root.setPalette(palette(True))
    canvas = module.create_canvas(owner, root)
    canvas.resize(640, 480)
    try:
        assert not canvas.testAttribute(QtCore.Qt.WA_SetPalette)
        image = canvas.grab().toImage()
        assert not errors, errors
        assert (image.pixelColor(639, 479).lightness() < 128) is dark_canvas
        assert set(accesses) == {"isDark", "generalDarkGlyph"}
    finally:
        canvas.close()
        root.close()
        root.deleteLater()
