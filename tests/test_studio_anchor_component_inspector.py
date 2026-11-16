# this_file: tests/test_studio_anchor_component_inspector.py
"""S27 shell assembly preserves the existing inspection and cleanup contract."""

import importlib
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest
import _cov_qt as fq
from test_fontui_glyph_metrics import composition_env, choose, owned_font  # noqa: F401


@pytest.fixture
def studio(composition_env, monkeypatch):  # noqa: F811
    import fontlabapp.fontui as fontui
    from fontlabapp.fontui.lifecycle import Owned

    class Preview(Owned):
        def __init__(self, font, parent, **options):
            super().__init__(parent)
            self.font, self.options, self.loaded = font, options, []

        def load(self, name, layer=None):
            self.loaded.append((name, layer))

    class Table(Owned):
        def __init__(self, columns, parent):
            super().__init__(parent)
            self.columns, self.rows = columns, []

        def set_rows(self, rows):
            self.rows = rows

    class Shell:
        def __init__(self, title, preview, **kwargs):
            self.title, self.preview_kind = title, preview
            self.widget = fq.FakeWidget()
            self.children, self.specs, self.actions = [], [], {}
            self.closed = False

        def set_preview(self, preview):
            self.preview = preview
            self.children.append(preview)

        def add_tab(self, spec):
            self.specs.append(spec)
            panel = spec.build(self)
            return panel

        def set_actions(self, panel, **actions):
            self.actions = actions

        def set_about(self, text):
            self.about = text

        def show(self):
            self.shown = True

        def close(self):
            while self.children:
                self.children[-1].close()
                self.children.pop()
            self.closed = True

    monkeypatch.setitem(sys.modules, "fontlabapp.fontui.appshell", SimpleNamespace(AppShell=Shell))
    monkeypatch.setattr(fontui, "glyph_table", Table)
    monkeypatch.setattr(fontui, "glyph_view", Preview)
    name = "fontlabapp.fontui.anchor_components_studio"
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    yield SimpleNamespace(module=module, env=composition_env, shells=[])
    for shell in tuple(module._HANDLES):
        shell.close()
    module._HANDLES.clear()
    sys.modules.pop(name, None)


def test_studio_selection_preserves_order_and_font_and_uses_read_only_preview(studio):
    from ufoLib2.objects import Anchor

    font = owned_font()
    font["A"].anchors = [Anchor(10, 20, "top"), Anchor(2, 3, "top")]
    before = deepcopy(font)
    app = studio.module.show(font, studio.env.parent)
    owner = app.inspector.controller
    choose(owner.browser, ["A"])
    assert owner.anchor_rows == (("top", 10, 20), ("top", 2, 3))
    assert [row.values for row in owner.anchor_table.rows] == [(10, 20), (2, 3)]
    assert app.preview.loaded[-1][0] == "A"
    assert app.preview.options["read_only"] is True
    assert app.preview_kind == "tglyph" and "Source:" in app.about
    assert "apply" not in app.actions
    app.actions["refresh"]()
    owner.browser.filter("missing")
    assert app.preview.loaded[-1][0] is None
    assert font == before
    app.close()
    assert owner._released and app.closed


def test_studio_no_font_and_foreign_selection_clear_preview(studio):
    app = studio.module.show(None, studio.env.parent)
    app.inspector.controller.selected(owned_font(), ("A",))
    assert app.preview.loaded[-1] == (None, "public.default")
    app.close()


def test_studio_close_refusal_keeps_exact_owner_for_retry(studio, monkeypatch):
    app = studio.module.show(owned_font(), studio.env.parent)
    owner = app.inspector.controller
    close = owner.browser.close
    monkeypatch.setattr(owner.browser, "close", lambda: (_ for _ in ()).throw(RuntimeError("busy")))
    with pytest.raises(RuntimeError, match="inspection cleanup"):
        app.close()
    assert app.inspector.controller is owner and not owner._released
    monkeypatch.setattr(owner.browser, "close", close)
    app.close()
    assert owner._released


def test_studio_construction_failure_closes_shell(studio, monkeypatch):
    import fontlabapp.fontui as fontui

    def fail(*args, **kwargs):
        raise ValueError("preview construction")

    monkeypatch.setattr(fontui, "glyph_view", fail)
    with pytest.raises(ValueError, match="preview construction"):
        studio.module.show(owned_font(), studio.env.parent)
    assert not studio.module._HANDLES


def test_studio_repeated_close_and_late_selection_do_nothing(studio):
    app = studio.module.show(owned_font(), studio.env.parent)
    owner, canvas = app.inspector.controller, app.preview
    app.close()
    loaded = list(canvas.loaded)
    owner.selected(owned_font(), ("A",))
    app.close()
    assert canvas.loaded == loaded


def test_studio_table_close_requires_acknowledgement(studio, monkeypatch):
    app = studio.module.show(owned_font(), studio.env.parent)
    table = app.inspector.tables[-1]
    close = table.close
    monkeypatch.setattr(table, "close", lambda: None)
    with pytest.raises(RuntimeError, match="table cleanup"):
        app.close()
    assert app in studio.module._HANDLES
    monkeypatch.setattr(table, "close", close)
    app.close()
    assert app not in studio.module._HANDLES


def test_studio_failed_constructor_owner_survives_failed_cleanup(studio, monkeypatch):
    import fontlabapp.fontui as fontui
    from fontlabapp.fontui.lifecycle import Owned

    child = Owned(studio.env.parent)
    close = child.close
    monkeypatch.setattr(child, "close", lambda: (_ for _ in ()).throw(RuntimeError("busy")))
    error = ValueError("failed child")
    error.owner = child

    def fail(*args, **kwargs):
        raise ExceptionGroup("construction", [error, error])

    monkeypatch.setattr(fontui, "glyph_view", fail)
    with pytest.raises(ExceptionGroup) as caught:
        studio.module.show(owned_font(), studio.env.parent)
    app = studio.module._HANDLES[-1]
    assert app.children.count(child) == 1
    assert "retained owner" in caught.value.__notes__[0]
    monkeypatch.setattr(child, "close", close)
    app.close()


def test_studio_public_entry_reaches_same_retained_controller(studio):
    from fontlabapp.studios.anchor_component_inspector import show

    font = owned_font()
    app = show(font, studio.env.parent)
    assert app.inspector.controller.font is font
    app.close()


def test_studio_changed_default_layer_refuses_mixed_layer_report(studio):
    from ufoLib2.objects import Anchor

    source = owned_font()
    source["A"].anchors = [Anchor(1, 2, "regular")]
    bold = source.layers.newLayer("Bold")
    bold.newGlyph("A").anchors = [Anchor(100, 200, "bold")]

    class Font:
        defaultLayerName = "public.default"

        def __getitem__(self, name):
            return source.layers[self.defaultLayerName][name]

        def __getattr__(self, name):
            return getattr(source, name)

    font = Font()
    app = studio.module.show(font, studio.env.parent)
    owner = app.inspector.controller
    choose(owner.browser, ["A"])
    assert owner.anchor_rows == (("regular", 1, 2),)
    assert app.preview.loaded[-1] == ("A", "public.default")
    font.defaultLayerName = "Bold"
    owner.selected(font, ("A",))
    assert owner.anchor_rows == owner.component_rows == ()
    assert owner.anchor_table.rows == owner.component_table.rows == []
    assert app.preview.loaded[-1] == (None, "public.default")
    assert "Close and reopen" in owner.status.text
    app.close()
