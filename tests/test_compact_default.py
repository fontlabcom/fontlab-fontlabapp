# this_file: tests/test_compact_default.py
"""Windows are compact by default (issue 253); ``compact=False`` is the one opt-out."""

from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt as _studio_qt
from test_spacing_worksheet import GUI, QtCore, drain

import fontlabapp.qt.widgets as widgets
from fontlabapp.qt import compact as compact_mod

studio_qt = _studio_qt
del _studio_qt


@pytest.fixture
def restore_modules():
    """Put every ``fontlabapp`` module (and parent-package attribute) back as it was after the test."""
    import sys

    saved = {n: m for n, m in sys.modules.items() if n.startswith("fontlabapp")}
    attrs = {}
    for name, module in saved.items():
        parent, _, leaf = name.rpartition(".")
        if parent in saved and hasattr(saved[parent], leaf):
            attrs[name] = getattr(saved[parent], leaf)
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp") and n not in saved]:
        del sys.modules[name]
    sys.modules.update(saved)
    for name, value in attrs.items():
        parent, _, leaf = name.rpartition(".")
        setattr(saved[parent], leaf, value)
    for name in list(sys.modules):
        parent, _, leaf = name.rpartition(".")
        if name.startswith("fontlabapp") and name not in saved and parent in saved and hasattr(saved[parent], leaf):
            delattr(saved[parent], leaf)


def margins(layout):
    m = layout.contentsMargins()
    return (m.left(), m.top(), m.right(), m.bottom())


@pytest.fixture
def binding(monkeypatch):
    qt = NS(QtGui=GUI, QtCore=QtCore)
    monkeypatch.setattr(widgets, "_native", lambda name: qt)
    monkeypatch.setattr(compact_mod, "_qt", lambda: qt)
    yield qt
    drain()


def roomy(content):
    layout = GUI.QVBoxLayout(content)
    layout.setContentsMargins(11, 11, 11, 11)
    layout.setSpacing(6)
    row = GUI.QHBoxLayout()
    layout.addLayout(row)
    return layout, row


def test_owned_when_created_then_root_layout_compact(studio_qt):
    owned = studio_qt.modules.lifecycle.Owned(None)
    studio_qt.owned.append(owned)
    assert margins(owned.layout) == (6, 6, 6, 6)
    assert owned.layout.spacing() == 4


def test_owned_when_compact_false_then_qt_default(studio_qt):
    owned = studio_qt.modules.lifecycle.Owned(None, compact=False)
    studio_qt.owned.append(owned)
    assert margins(owned.layout) != (6, 6, 6, 6)


def test_owned_when_embedded_then_inset_follows_the_host_and_top_level_is_compact(studio_qt):
    lifecycle = studio_qt.modules.lifecycle
    top = lifecycle.Owned(None)
    inner = lifecycle.Owned(top.widget)
    stack = GUI.QStackedWidget()
    in_stack = lifecycle.Owned(stack)
    tabs = GUI.QTabWidget()
    in_tab = lifecycle.Owned(tabs)
    roomy = lifecycle.Owned(top.widget, compact=False)
    studio_qt.owned.extend([top, inner, in_stack, in_tab, roomy])
    assert (margins(top.layout), top.layout.spacing()) == ((6, 6, 6, 6), 4), "top level: panel metrics"
    assert (margins(inner.layout), inner.layout.spacing()) == ((0, 0, 0, 0), 4), "in another Owned: host insets"
    assert (margins(in_stack.layout), in_stack.layout.spacing()) == ((0, 0, 0, 0), 4), "in a stack: host insets"
    assert (margins(in_tab.layout), in_tab.layout.spacing()) == ((6, 6, 6, 6), 4), "a tab page has no inset of its own"
    assert margins(roomy.layout) != (0, 0, 0, 0) and roomy.layout.spacing() != 4, "compact=False opts out"


def test_create_dialog_when_build_makes_roomy_layout_then_compact(binding):
    seen = {}

    def build(content):
        seen["layout"], seen["row"] = roomy(content)

    main = GUI.QMainWindow()
    owned = widgets.create_dialog(main, "T", build)
    assert margins(seen["layout"]) == (6, 6, 6, 6)
    assert seen["layout"].spacing() == 4 and seen["row"].spacing() == 4
    assert margins(seen["row"]) == (0, 0, 0, 0)
    owned.close()


def test_create_dialog_when_compact_false_then_build_metrics_kept(binding):
    seen = {}
    main = GUI.QMainWindow()
    owned = widgets.create_dialog(
        main, "T", lambda c: seen.update(layout=roomy(c)[0]), compact=False
    )
    assert margins(seen["layout"]) == (11, 11, 11, 11)
    owned.close()


@pytest.mark.parametrize("kind", ["panel", "widget"])
def test_panel_and_widget_when_built_then_compact(binding, kind):
    seen = {}
    build = lambda c: seen.update(layout=roomy(c)[0])  # noqa: E731
    if kind == "panel":
        main = GUI.QMainWindow()
        owned = widgets.create_panel(main, "T", build, "right")
    else:
        owned = widgets.create_widget(None, build, show=False)
    assert margins(seen["layout"]) == (6, 6, 6, 6)
    owned.close()


def test_create_dialog_when_tab_page_is_roomy_then_page_margin_capped(binding):
    seen = {}

    def build(content):
        outer = GUI.QVBoxLayout(content)
        tabs = GUI.QTabWidget(content)
        page = GUI.QWidget()
        seen["page"] = GUI.QVBoxLayout(page)
        seen["page"].setContentsMargins(11, 11, 11, 11)
        seen["page"].setSpacing(6)
        tabs.addTab(page, "A")
        outer.addWidget(tabs)
        seen["tabs"] = tabs

    main = GUI.QMainWindow()
    owned = widgets.create_dialog(main, "T", build)
    assert margins(seen["page"]) == (6, 6, 6, 6) and seen["page"].spacing() == 4
    owned.close()


@pytest.fixture
def restore_modules():
    """Put back every fontlabapp module (and package attribute) the test imported or replaced."""
    import sys

    saved = {n: m for n, m in sys.modules.items() if n.startswith("fontlabapp")}
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp") and n not in saved]:
        del sys.modules[name]
    for name, module in saved.items():
        sys.modules[name] = module
        parent, _, leaf = name.rpartition(".")
        if parent in sys.modules:
            setattr(sys.modules[parent], leaf, module)


def _fresh(studio_qt, monkeypatch, *names):
    import importlib
    import sys

    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return [importlib.import_module(name) for name in names]


def test_font_browser_when_created_then_compact_metrics(studio_qt, monkeypatch, restore_modules):
    (fonts,) = _fresh(studio_qt, monkeypatch, "fontlabapp.fontui.fonts")
    window = fonts.FontBrowser((), follow=False)
    studio_qt.owned.append(window)
    assert margins(window.layout) == (6, 6, 6, 6) and window.layout.spacing() == 4


def test_designspace_panel_when_created_then_compact_metrics(studio_qt, monkeypatch, restore_modules):
    (mod,) = _fresh(studio_qt, monkeypatch, "fontlabapp.fontui.designspace")
    space = NS(axes=[], sources=[], instances=[], defaults=lambda: {}, location=lambda *a: None)
    window = mod.DesignspacePanel(space)
    studio_qt.owned.append(window)
    assert margins(window.layout) == (6, 6, 6, 6) and window.layout.spacing() == 4


DEMOS = [  # script, fontui factory, how the demo script makes its model
    ("Designspace Panel Demo", "designspace_panel", lambda n: n["SampleDesignspace"]()),
    ("Font Info Editor Demo", "font_info_editor", lambda n: n["SampleFont"](n["sample_info"]())),
    ("Font Browser Demo", "font_browser", lambda n: [n["sample_ufo"](*f) for f in n["FONTS"]]),
    ("Groups Editor Demo", "groups_editor", lambda n: n["SampleFont"](n["sample_ufo"]())),
    ("FontParts Features Editor Demo", "features_editor", lambda n: n["SampleFont"]()),
    ("FontParts Kerning Editor Demo", "kerning_editor", lambda n: n["SampleFont"](n["sample_ufo"]())),
    ("Glyph Sequence Demo", "glyph_sequence", lambda n: n["sample_ufo"]()),
    ("Glyph Browser Demo", "glyph_browser", lambda n: n["sample_ufo"]()),
    ("Transform Editor Demo", "transform_editor", lambda n: n["sample_ufo"]()),
]


@pytest.mark.parametrize("title,factory,model", DEMOS, ids=[d[0] for d in DEMOS])
def test_editor_demo_when_built_in_real_qt_then_total_outer_inset_is_six(
    restore_modules, binding, studio_qt, monkeypatch, title, factory, model
):
    """Dialog layout 6 px + embedded panel root 0 px (it was 6 + 6 = 12) for each font-editor demo."""
    if factory == "kerning_editor":
        pytest.skip("KerningEditor reads PythonQt's `.text` property, a method in PySide6; see the shape test")
    import importlib
    import sys
    from types import ModuleType

    from _demo_support import run_script, script_path

    keep = {"fontlabapp.fontui", "fontlabapp.fontui.lifecycle", "fontlabapp.fontui.table", "fontlabapp.fontui.appshell"}
    for name in [n for n in sys.modules if n.startswith("fontlabapp.fontui.") and n not in keep]:
        monkeypatch.delitem(sys.modules, name)  # rebind the editors to this test's real Qt
    fly_fontui = ModuleType("fly.ap.fontui")
    real = importlib.import_module("fontlabapp.fontui")
    setattr(fly_fontui, factory, getattr(real, factory))
    monkeypatch.setitem(sys.modules, "fly.ap.fontui", fly_fontui)
    names = run_script(script_path("Font Editors", title), "imported")
    scope = NS(connect=lambda *a, **k: None)
    args = (NS(QtGui=GUI, QtCore=QtCore), lambda sink: scope, model(names))
    demo = names["Demo"](*args)
    main = GUI.QMainWindow()  # keep a reference: the dialog dies with it
    demo.owned = widgets.create_dialog(main, "T", demo.build)
    assert margins(demo.editor.widget.parentWidget().layout()) == (6, 6, 6, 6), "dialog supplies the inset"
    assert margins(demo.editor.layout) == (0, 0, 0, 0), "the panel root adds none"
    demo.owned.close()


def _shaped(factory_name, make_args):
    def build(content):
        import fontlabapp.fontui as fontui

        layout = GUI.QVBoxLayout(content)
        content.editor = getattr(fontui, factory_name)(*make_args(), parent=content)
        layout.addWidget(content.editor.widget)
    return build


SHAPES = [  # the four src windows hand-build `QVBoxLayout(content)` + `factory(parent=content)` like this
    ("features_editor (feature_proof.py:61)", lambda: _shaped("features_editor", lambda: (_FakeFont(),))),
    ("glyph_sequence (feature_proof.py:63, detached_transform.py:255)", lambda: _shaped("glyph_sequence", lambda: (_FakeFont(),))),
    ("transform_editor (batch_recipes.py:39, detached_transform.py:248)", lambda: _shaped("transform_editor", lambda: (None,))),
]


class _FakeFont:
    def __init__(self):
        from _cov_qt import FontModel, ufo_font

        self.__dict__.update(FontModel(ufo_font()).__dict__)

    def keys(self):
        return list(self.ufo.keys())

    def __getitem__(self, name):
        return self.ufo[name]

    def __contains__(self, name):
        return name in self.ufo


@pytest.mark.parametrize("label,builder", SHAPES, ids=[s[0] for s in SHAPES])
def test_src_window_shapes_when_built_in_dialog_then_total_outer_inset_is_six(restore_modules, binding, studio_qt, monkeypatch, label, builder):
    import sys

    keep = {"fontlabapp.fontui", "fontlabapp.fontui.lifecycle", "fontlabapp.fontui.table", "fontlabapp.fontui.appshell"}
    for name in [n for n in sys.modules if n.startswith("fontlabapp.fontui.") and n not in keep]:
        monkeypatch.delitem(sys.modules, name)
    main = GUI.QMainWindow()
    seen = {}
    build = builder()
    owned = widgets.create_dialog(main, "T", lambda content: (build(content), seen.update(editor=content.editor)))
    editor = seen["editor"]
    assert margins(editor.widget.parentWidget().layout()) == (6, 6, 6, 6)
    assert margins(editor.layout) == (0, 0, 0, 0), "the embedded root adds no second inset"
    owned.close()
