# this_file: tests/test_qt_properties.py
"""Preserve the existing known-property reader and every App import path."""

from module_paths import module_name as _module_name
import importlib
import inspect
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(
    params=[
        "qt_properties",
        "_calendar_base",
        "_filter_table_controls",
        "_zone_controls",
    ]
)
def reader(request, monkeypatch):
    name = _module_name(request.param)
    if request.param in {"_filter_table_controls", "_zone_controls"}:
        monkeypatch.setitem(
            sys.modules,
            "fontlabapp.glyphs.names.ui",
            SimpleNamespace(QtCore=None, QtGui=None, muted=None),
        )
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    function = module.value
    assert function.__name__ == function.__qualname__ == "value"
    assert function.__module__ == name
    assert tuple(inspect.signature(function).parameters) == (
        ("owner", "name")
        if request.param in {"qt_properties", "_calendar_base"}
        else ("widget", "name")
    )
    return function


@pytest.mark.parametrize("item", [None, False, 0, "", [], {}, object()])
def test_value_when_scalar_then_returns_exact_object(reader, item):
    assert reader(SimpleNamespace(known=item), "known") is item


def test_value_when_descriptor_then_gets_and_calls_exactly_once(reader):
    calls = []
    result = object()

    class Owner:
        @property
        def known(self):
            calls.append("get")

            def getter():
                calls.append("call")
                return result

            return getter

    assert reader(Owner(), "known") is result
    assert calls == ["get", "call"]


def test_value_when_replaced_then_reads_current_value_and_callable(reader):
    owner = SimpleNamespace(known=[])
    assert reader(owner, "known") is owner.known
    owner.known = lambda: 42
    assert reader(owner, "known") == 42
    owner.known = False
    assert reader(owner, "known") is False


def test_value_when_bound_method_or_callable_object_then_invokes_once(reader):
    class Getter:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            return self

        def method(self):
            self.calls += 1
            return self

    getter = Getter()
    assert reader(SimpleNamespace(known=getter), "known") is getter
    assert getter.calls == 1
    assert reader(getter, "method") is getter
    assert getter.calls == 2


@pytest.mark.parametrize("stage", ["get", "call"])
def test_value_when_access_fails_then_preserves_exception_identity(reader, stage):
    error = RuntimeError(stage)

    class Owner:
        @property
        def known(self):
            if stage == "get":
                raise error

            def fail():
                raise error

            return fail

    with pytest.raises(RuntimeError) as caught:
        reader(Owner(), "known")
    assert caught.value is error


def test_value_when_missing_or_wrong_arity_then_propagates(reader):
    with pytest.raises(AttributeError):
        reader(SimpleNamespace(), "known")
    with pytest.raises(TypeError):
        reader(SimpleNamespace(known=lambda required: required), "known")


def test_public_reader_when_cold_imported_then_loads_no_host_or_binding():
    import fontlabapp

    code = "import sys; from fontlabapp.qt.properties import value; assert value(type('O',(),{'x':0})(),'x') == 0; assert not any(n.split('.')[0] in {'PythonQt','fontlab','fontgate','fontpr','fontlab_glyport','fontlab_fontport','PyQt5','PySide6'} for n in sys.modules)"
    source = str(Path(fontlabapp.__file__).resolve().parent.parent)
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            f"import sys; sys.path.insert(0, {source!r}); " + code,
        ],
        check=True,
    )
