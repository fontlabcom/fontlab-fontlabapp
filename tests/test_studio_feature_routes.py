# this_file: tests/test_studio_feature_routes.py
"""WP07 studios retain named feature routes and delegate owned shell assembly."""
import importlib
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('studio,title,kind,titles', [
    ('feature_authoring', 'Feature Authoring', 'tmetrics', ['Build Suffix Substitution', 'Classes Browser', 'Feature Code Viewer', 'Generate Random Alternates Feature']),
    ('feature_explorer', 'Feature Explorer', 'tmetrics', ['Alternate Preview', 'Ligature Finder', 'Suffix Report']),
    ('nastaliq_connections', 'Nastaliq Connections', 'tglyph', ['Nastaliq Connection Editor']),
])
def test_show_preserves_all_routes_and_explicit_tab(monkeypatch, studio, title, kind, titles):
    calls = []
    def show(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(tabs=SimpleNamespace(setCurrentIndex=lambda index: calls.append(index)))
    class Route:
        def __init__(self, title, build, **kwargs):
            self.title, self.build, self.options = title, build, kwargs
    monkeypatch.setitem(sys.modules, 'fontlabapp.fontui', SimpleNamespace(identity_route=Route, identity_studio=show, identity_panel=lambda *a, **kw: (a, kw)))
    module = importlib.import_module('fontlabapp.studios.' + studio + '.app')
    module.show(tab=titles[-1])
    args, kwargs = calls[0]
    assert args[0] == title
    assert kwargs['preview'] == kind
    assert [route.title for route in args[1]] == titles
    assert calls[-1] == len(titles)-1
    for route, row in zip(args[1], module.ROUTES, strict=True):
        panel_args, panel_kwargs = route.build('parent')
        assert panel_args == (f"features.identity_tools.{studio}.{row[1]}", row[2], 'parent')
        assert panel_kwargs['factory_type'] == (row[2] == 'panel_type')
    importlib.import_module('fontlabapp.studios.' + studio).show()
    assert len(calls) == 3
    with pytest.raises(ValueError, match='Unknown'):
        module.show(tab='not a route')
