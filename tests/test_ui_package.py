# this_file: tests/test_ui_package.py
"""Lazy `fontlabapp.fontui` facade: cold import and factory construction."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

FACTORIES = (
    "font_info_editor",
    "groups_editor",
    "kerning_editor",
    "transform_editor",
    "batch_panel",
    "glyph_sequence",
    "core_pythonqt_lab",
)
SUBMODULES = ("transform", "transform_view", "batch", "batch_worker", "sequence")


def test_ui_package_when_cold_imported_then_loads_no_qt_and_no_editor_module(tmp_path):
    import fontlabapp.fontui as ui

    code = """
import sys
from pathlib import Path
import fontlabapp.fontui as ui
for name in (
    "font_info_editor", "groups_editor", "kerning_editor",
    "transform_editor", "batch_panel", "glyph_sequence",
    "hint_tools_window", "raise_ascender_tab", "outline_generators_backends",
    "cleanup_failed_window", "show_outline_compatibility", "outline_studio", "show_node_editor", "duplicate_nodes",
    "core_pythonqt_lab", "follow_history",
):
    assert callable(getattr(ui, name)), name
assert Path(ui.__file__).resolve() == Path(sys.argv[1]).resolve(), ui.__file__
assert "PythonQt" not in sys.modules, "importing the facade must not load PythonQt"
assert "fontlab" not in sys.modules, "importing the facade must not load FontLab"
loaded = [m for m in sys.modules if m.startswith("fontlabapp.fontui.") and m != "fontlabapp.fontui.model"]
assert not loaded, loaded
assert "fontlabapp.fontui.lifecycle" not in sys.modules
"""
    # Resolve fontlabapp exactly as this process did, whatever editable install exists.
    env = {**os.environ, "PYTHONPATH": str(Path(ui.__file__).resolve().parents[2])}
    subprocess.run([sys.executable, "-s", "-c", code, ui.__file__], check=True, cwd=tmp_path, env=env)


def test_ui_package_exports_exactly_the_declared_factories_and_services():
    import fontlabapp.fontui as ui

    assert set(ui.__all__) == set(FACTORIES) | {
        "BrowserState", "FontListState", "designspace_panel", "features_editor",
        "font_browser", "glyph_browser", "glyph_preview", "outline", "viewport",
        "app_shell", "glyph_table", "layer_is_hinted",
        "current_font", "follow_history", "kerning_snapshot", "metrics_preview", "write_kerning",
        "metrics_window", "remove_hints", "glyph_view",
        "anchor_component_studio", "category_report", "owned_panel_type",
        "hint_tools_window", "raise_ascender_tab", "outline_generators_backends",
        "cleanup_failed_window", "show_outline_compatibility", "outline_studio", "show_node_editor", "duplicate_nodes",
        "identity_panel", "identity_route", "identity_studio",
    }, (
        "Public names must stay lazy factories"
    )


def test_construct_when_init_fails_with_widget_then_closes_owner_and_reraises():
    import fontlabapp.fontui as ui

    closed = []

    class Failing:
        widget = object()

        def __init__(self, *args):
            raise ValueError("boom")

        def close(self):
            closed.append(True)

    with pytest.raises(ValueError, match="boom"):
        ui._construct(Failing, None, None, None)
    assert closed == [True], "A half-built owner must be closed before the error leaves"


def test_construct_when_init_fails_without_widget_then_does_not_close():
    import fontlabapp.fontui as ui

    class Bare:
        def __init__(self):
            raise RuntimeError("early")

        def close(self):  # pragma: no cover - must stay uncalled
            raise AssertionError("close must not run without a widget")

    with pytest.raises(RuntimeError, match="early"):
        ui._construct(Bare)


@pytest.fixture
def recorded(monkeypatch):
    """Replace ``_construct`` so a factory call shows its class and arguments."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    import fontlabapp.fontui as ui

    for name in SUBMODULES:
        monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{name}", raising=False)
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock(), QtCore=Mock())
    )
    calls = []
    monkeypatch.setattr(ui, "_construct", lambda cls, *a: calls.append((cls, a)))
    yield ui, calls
    for name in SUBMODULES:
        sys.modules.pop(f"fontlabapp.fontui.{name}", None)


def test_transform_editor_when_called_then_builds_transform_editor(recorded):
    ui, calls = recorded
    ui.transform_editor("font", "A", "parent", "on_change")
    ((cls, args),) = calls
    assert cls.__module__ == "fontlabapp.fontui.transform"
    assert cls.__name__ == "TransformEditor"
    assert args == ("font", "A", "parent", "on_change")


def test_batch_panel_when_called_then_passes_explicit_python(recorded):
    ui, calls = recorded
    ui.batch_panel("recipe", "parent", "on_finish", "/opt/py3.11")
    ((cls, args),) = calls
    assert cls.__module__ == "fontlabapp.fontui.batch"
    assert args == ("recipe", "parent", "on_finish", "/opt/py3.11")


def test_batch_panel_when_python_omitted_then_defaults_to_none(recorded):
    ui, calls = recorded
    ui.batch_panel("recipe")
    assert calls[0][1] == ("recipe", None, None, None), (
        "python=None lets the panel fall back to $FONTLABAPP_BATCH_PYTHON"
    )


def test_glyph_sequence_when_called_then_builds_fontport_sequence(recorded):
    ui, calls = recorded
    ui.glyph_sequence("font", "parent", "on_select")
    ((cls, args),) = calls
    assert cls.__module__ == "fontlabapp.fontui.sequence"
    assert cls.__name__ == "Sequence"
    assert args == ("font", "parent", "on_select")


def test_font_transform_example_when_run_then_wires_editor_recipe_into_batch(
    monkeypatch,
):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    path = Path(__file__).resolve().parents[1] / "examples" / "font_transform.py"
    spec = importlib.util.spec_from_file_location("font_transform_example", path)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    shown = []
    widget = SimpleNamespace(resize=lambda *a: None, show=lambda: shown.append(1))
    editor = SimpleNamespace(widget=widget, recipe=lambda: "recipe")
    batch_args = {}

    def fake_batch(recipe, python=None):
        batch_args.update(recipe=recipe, python=python)
        return SimpleNamespace(widget=widget)

    # The example binds the factories at import time: rebind its own names.
    monkeypatch.setattr(example, "transform_editor", lambda font: editor)
    monkeypatch.setattr(example, "batch_panel", fake_batch)
    got_editor, _ = example.transform_tools("font", python="/opt/py")
    assert got_editor is editor
    assert batch_args == {"recipe": editor.recipe, "python": "/opt/py"}
    assert len(shown) == 2, "Both handles must be shown"


@pytest.mark.parametrize(
    "module", ["batch", "fontinfo", "groups", "kerning", "sequence", "transform"]
)
def test_editor_module_when_imported_directly_without_fontport_then_names_the_extra(
    monkeypatch, module
):
    import importlib
    from types import SimpleNamespace
    from unittest.mock import Mock

    for name in [n for n in sys.modules if n.startswith("fontlab_fontport")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "fontlab_fontport", None)  # import raises
    monkeypatch.setitem(
        sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock(), QtCore=Mock())
    )
    monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{module}", raising=False)
    with pytest.raises(ImportError, match=r"fontlab-fontlabapp\[fontport\]"):
        importlib.import_module(f"fontlabapp.fontui.{module}")


def test_factory_when_fontport_missing_then_import_error_names_the_extra(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    import fontlabapp.fontui as ui

    for name in [n for n in sys.modules if n.startswith("fontlab_fontport")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "fontlab_fontport", None)  # import raises
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock(), QtCore=Mock()))
    monkeypatch.delitem(sys.modules, "fontlabapp.fontui.groups", raising=False)
    with pytest.raises(ImportError, match=r"fontlab-fontlabapp\[fontport\]"):
        ui.groups_editor(object())


def test_studio_factories_forward_explicit_context(monkeypatch):
    from types import SimpleNamespace
    import fontlabapp.fontui as ui
    calls = []
    def show(*args, **kwargs):
        calls.append((args, kwargs))
        return 'owned-window'
    modules = {name: SimpleNamespace(show=show) for name in ('outline_compatibility', 'outline_studios')}
    modules['outline_generators'] = SimpleNamespace(backends=lambda: 'services')
    class Raise:
        def __init__(self, studio, backend):
            self.studio, self.backend = studio, backend
    modules['raise_ascender'] = SimpleNamespace(RaiseAscender=Raise)
    monkeypatch.setattr(ui, '_load', modules.__getitem__)
    assert ui.show_outline_compatibility('parent', font='font') == 'owned-window'
    assert ui.outline_studio('Transform Studio', 'parent', package='package') == 'owned-window'
    assert calls == [(('parent',), {'font': 'font'}),
                     (('Transform Studio', 'parent'), {'package': 'package'})]
    assert ui.outline_generators_backends() == 'services'
    owner = ui.raise_ascender_tab('studio', backend='native')
    assert (owner.studio, owner.backend) == ('studio', 'native')


def test_cleanup_service_retains_failed_owner_and_original_error():
    from types import SimpleNamespace
    import fontlabapp.fontui as ui
    opened = ValueError('setup failed')
    closed = []
    owner = SimpleNamespace(close=lambda: closed.append(True))
    ui.cleanup_failed_window(owner, opened)
    assert closed == [True]
    failed = SimpleNamespace(close=lambda: False)
    with pytest.raises(BaseExceptionGroup) as caught:
        ui.cleanup_failed_window(failed, opened)
    assert caught.value.owner is failed
    assert caught.value.exceptions[0] is opened


@pytest.mark.parametrize('factory,module,member', [
    ('glyph_view', 'tglyph', 'TGlyph'),
    ('metrics_preview', 'tmetrics', 'TMetrics'),
])
@pytest.mark.parametrize('built_widget', [False, True])
def test_preview_factory_when_construction_interrupted_then_closes_owned_widget_only(
    monkeypatch, factory, module, member, built_widget,
):
    from types import SimpleNamespace
    import fontlabapp.fontui as ui
    closed = []
    error = KeyboardInterrupt('native construction interrupted')

    class Interrupted:
        def __init__(self, *args, **kwargs):
            if built_widget:
                self.widget = object()
            raise error

        def close(self):
            closed.append(self)

    monkeypatch.setattr(ui, '_load', lambda name: SimpleNamespace(**{member: Interrupted}))
    with pytest.raises(KeyboardInterrupt) as caught:
        getattr(ui, factory)('font', read_only=True)
    assert caught.value is error
    assert len(closed) == int(built_widget)


def test_metrics_preview_when_constructed_then_preserves_read_only_and_native_context(monkeypatch):
    from types import SimpleNamespace
    import fontlabapp.fontui as ui

    class Preview:
        def __init__(self, *args, **kwargs):
            self.args, self.options = args, kwargs

    monkeypatch.setattr(ui, '_load', lambda name: SimpleNamespace(TMetrics=Preview))
    check = object()
    owner = ui.metrics_preview('font', 'parent', text='AV', controls=True, layer='Bold',
                               label_prefix='Proof', hint_check=check, read_only=True)
    assert owner.args == ('font', 'parent', None, 'AV')
    assert owner.options == dict(controls=True, layer='Bold', label_prefix='Proof',
                                 hint_check=check, read_only=True)


def test_node_services_forward_parent_and_exact_duplicate_policy(monkeypatch):
    from types import SimpleNamespace
    import fontlabapp.fontui as ui
    calls = []
    def show(**kwargs):
        calls.append(kwargs)
        return 'editor'
    def duplicate(mode):
        calls.append(mode)
        return 3
    modules = {
        'node_editor': SimpleNamespace(show=show),
        'node_editor.session': SimpleNamespace(native=SimpleNamespace(duplicate_selected_nodes=duplicate)),
    }
    monkeypatch.setattr(ui, '_load', modules.__getitem__)
    assert ui.show_node_editor('parent') == 'editor'
    assert ui.duplicate_nodes('end') == 3
    assert calls == [{'parent': 'parent'}, 'end']
