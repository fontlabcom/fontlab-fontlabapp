# this_file: tests/test_studio_anchor_component_inspector_qt.py
"""Real shell/table integration; glyph rendering stays in TGlyph's own tests."""

import importlib
import sys
from types import SimpleNamespace

from _studio_qt import studio_qt  # noqa: F401
from test_fontui_glyph_metrics import owned_font


def test_real_shell_tables_sort_numerically_and_close_children(studio_qt, monkeypatch):  # noqa: F811
    from ufoLib2.objects import Anchor
    import fontlabapp.fontui as fontui

    Owned = studio_qt.modules.lifecycle.Owned

    class Preview(Owned):
        def __init__(self, font, parent, **options):
            super().__init__(parent)
            self.options, self.loaded = options, []

        def load(self, name, layer):
            self.loaded.append((name, layer))

        def set_glyph(self, name):
            pass

    class Browser(Owned):
        def __init__(self, font, parent, activate, multiple, controls, selected):
            super().__init__(parent)
            self.preview = Preview(font, self.widget)

        def refresh(self):
            pass

        def close(self):
            self._close_with_child(self.preview)

    monkeypatch.setattr(fontui, "glyph_view", Preview)
    monkeypatch.setitem(sys.modules, "fontlabapp.fontui.native", SimpleNamespace(Browser=Browser))
    name = "fontlabapp.fontui.anchor_components_studio"
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    font = owned_font()
    font["A"].anchors = [Anchor(10, 20, "top"), Anchor(2, 3, "top")]
    app = module.show(font)
    studio_qt.owned.append(app)
    owner = app.inspector.controller
    owner.selected(font, ("A",))
    table = owner.anchor_table
    table.view.sortByColumn(1, studio_qt.QtCore.Qt.AscendingOrder)
    assert table.proxy.index(0, 1).data() == 2
    assert table.proxy.index(1, 1).data() == 10
    assert app.splitter.indexOf(app.tabs) == 0
    assert app.splitter.indexOf(app.preview_box) == 1
    assert app.tabs.tabText(0) == "Anchors and Components"
    assert app.tabs.tabText(1) == "About"
    assert app.apply_button.isHidden()
    assert app.refresh_button.isEnabled()
    assert app.preview.loaded[-1] == ("A", "public.default")
    assert app.preview.options["read_only"] is True
    app.close()
    assert owner._released and table._close_complete
    assert app not in module._HANDLES
    sys.modules.pop(name, None)
