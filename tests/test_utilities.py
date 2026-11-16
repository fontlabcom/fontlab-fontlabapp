# this_file: tests/test_utilities.py
"""Host-free contracts preserved from Fontlabpy and regression fixes."""
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_importing_pure_utilities_does_not_import_host_or_construct_app():
    result = subprocess.run([sys.executable, "-c", "import sys; import fontlabapp.core.utils; assert 'fontlab' not in sys.modules; assert 'PythonQt' not in sys.modules; import fontlabapp; assert 'app' not in vars(fontlabapp)"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_attribdict_preserves_mapping_and_new_attribute_semantics():
    from fontlabapp.core.utils import attribdict
    value = attribdict(answer=42)
    value.answer = 7
    value.new_attribute = 9
    assert value['answer'] == 7
    assert 'new_attribute' not in value and value.new_attribute == 9
    value.nested['key'] = 'value'
    assert value.as_dict()['nested']['key'] == 'value'


def test_deepmerge_extractors_and_json_special_types():
    from fontlabapp.core.utils import deepmerge, dictextractor, json as smartjson
    from fontlabapp.core.utils.merge import Strategy
    assert list(dictextractor.extract({'items': [{'name': 'A'}]}, 'name')) == ['A']
    assert deepmerge({'items': [1]}, {'items': [2]}, strategy=Strategy.ADDITIVE) == {'items': [1, 2]}
    with pytest.raises(TypeError):
        deepmerge({'value': 1}, {'value': '2'}, strategy=Strategy.TYPESAFE)
    assert json.loads(smartjson.dumps({'path': Path('file.txt'), 'time': timedelta(seconds=1)}, cls=smartjson.SmartJSONEncoder)) == {'path': 'file.txt', 'time': '0:00:01'}


def test_slug_and_markdown():
    from fontlabapp.core.utils import slugify, to_pre, to_html
    assert slugify('Café & Test') == 'cafe_test'
    assert '&lt;' in to_pre('<')
    assert '<strong>bold</strong>' in to_html('**bold**', md=True)
    assert 'first' not in to_html('second', md=True)


def test_markdown_keys_use_pymdownx_not_legacy_mdx_steroids():
    from fontlabapp.core.utils import text
    assert 'pymdownx.keys' in text.extensions
    assert not any(name.startswith('mdx_steroids') for name in text.extensions)
    assert '<kbd' in text.to_html('++ctrl+a++', md=True)


def test_pref_library_roundtrip_and_malformed_file_does_not_get_overwritten(tmp_path):
    from fontlabapp.core.application.preflib import PrefLib
    path = tmp_path / 'prefs.json'
    app = SimpleNamespace(paths=SimpleNamespace(appPrefLibPath=path))
    prefs = PrefLib(app)
    value = prefs.getpref(prefs.lib.demo, {'answer': 42})
    value.answer = 7
    prefs.save()
    assert PrefLib(app).lib.demo.answer == 7
    path.write_text('{broken')
    with pytest.raises(json.JSONDecodeError):
        PrefLib(app)
    assert path.read_text() == '{broken', 'malformed user preferences must remain recoverable'


def test_versions_accept_suffixes_and_limit_to_four_fields():
    from fontlabapp.core.application.versions import Versions
    parse = Versions._get_version_info_from_str
    assert tuple(parse(None, '9.0.9780')) == (9, 0, 9780, 0)
    assert tuple(parse(None, '5.15.19-beta')) == (5, 15, 19, 0)
    assert tuple(parse(None, '10.0.26100.1.2')) == (10, 0, 26100, 1)
    with pytest.raises(ValueError):
        parse(None, 'unknown')


def test_utilities_import_without_optional_markdown_or_qt():
    code = r"""import sys
class Reject:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'markdown', 'PythonQt', 'pymdownx'}:
            raise ModuleNotFoundError(fullname, name=fullname)
sys.meta_path.insert(0, Reject())
from fontlabapp.core.utils import slugify, to_html
assert slugify('Hello World') == 'hello_world'
assert to_html('<p>hi</p>') == '<p>hi</p>\n'
try:
    to_html('**bold**', md=True)
except RuntimeError as error:
    assert 'Markdown' in str(error)
else:
    raise AssertionError('missing Markdown accepted')
"""
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_find_widgets_uses_requested_parent_children(monkeypatch):
    import importlib
    import types
    qt = types.ModuleType('PythonQt')
    qt.QtGui = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    ui = importlib.import_module('fontlabapp.core.application.ui').ApplicationUI.__new__(importlib.import_module('fontlabapp.core.application.ui').ApplicationUI)
    children = [object(), object()]
    parent = SimpleNamespace(children=lambda: children)
    assert ui.findWidgets(parent) == children


def test_json_encoder_accepts_empty_bytes_and_preferences_reject_non_objects(tmp_path):
    from fontlabapp.core.utils import json as smartjson
    from fontlabapp.core.application.preflib import PrefLib
    assert smartjson.dumps(b'', cls=smartjson.SmartJSONEncoder) == '""'
    path = tmp_path / 'prefs.json'
    path.write_text('[]')
    with pytest.raises(ValueError, match='JSON object'):
        PrefLib(SimpleNamespace(paths=SimpleNamespace(appPrefLibPath=path)))
    assert path.read_text() == '[]'


def test_update_panels_when_wired_then_brush_and_panels_list_use_their_own_controls(monkeypatch):
    import importlib
    import types
    qt = types.ModuleType('PythonQt')
    qt.QtGui = types.SimpleNamespace(QMenu=object, QAction=object)
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    module = importlib.import_module('fontlabapp.core.application.ui')
    from fontlabapp.core.utils import attribdict
    ui = module.ApplicationUI.__new__(module.ApplicationUI)
    ui.widgets, ui.actions = attribdict(), attribdict()
    ui.main = types.SimpleNamespace(
        actionToolbarPanel=types.SimpleNamespace(trigger=object()),
        actionPanelsPanel=types.SimpleNamespace(trigger=object()),
    )
    ui.panels = ui.buildPanels()
    monkeypatch.setattr(ui, 'getActions', lambda pname=None: attribdict())
    ui.updatePanels()
    buttons = ui.panels.panels.widgets
    assert ui.panels.brush.show is ui.actions.main.brush_panel.trigger
    assert ui.panels.brush.toggle is buttons.buttonBrush.toggle
    assert ui.panels.panels.show is ui.main.actionPanelsPanel.trigger
    assert ui.panels.panels.toggle is ui.main.actionPanelsPanel.trigger
    assert ui.panels.preview.show is not ui.panels.panels.show
