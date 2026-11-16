# this_file: tests/test_readonly_facade.py
# SPDX-License-Identifier: Apache-2.0
"""Resolve the two original read-only tools without touching native state."""

import importlib
import sys
from types import ModuleType

import pytest

scripting = importlib.import_module("fontlabapp.core.scripting")


@pytest.mark.parametrize(
    "factory,module_name,class_name",
    [
        ("kerning_persistence_api", "fontlabapp.kerning.persistence.model", None),
        (
            "kerning_persistence_dialog_type",
            "fontlabapp.kerning.persistence.ui",
            "KerningPersistenceDialog",
        ),
        ("revision_compare_api", "fontlabapp.fonts.revisions.model", None),
        (
            "revision_compare_dialog_type",
            "fontlabapp.fonts.revisions.ui",
            "RevisionCompareDialog",
        ),
    ],
)
def test_facade_resolves_requested_module_without_native_access_or_construction(
    monkeypatch, factory, module_name, class_name
):
    module = ModuleType(module_name)

    class Dialog:
        def __init__(self):
            pytest.fail("A lazy type factory must not construct a dialog")

    if class_name is not None:
        setattr(module, class_name, Dialog)
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: pytest.fail("Native access during facade resolution"),
    )
    expected = module if class_name is None else Dialog
    assert getattr(scripting, factory)() is expected


@pytest.mark.parametrize(
    "factory,module_name",
    [
        ("kerning_persistence_api", "fontlabapp.kerning.persistence.model"),
        ("revision_compare_api", "fontlabapp.fonts.revisions.model"),
    ],
)
def test_api_facade_returns_actual_host_free_shared_module(
    monkeypatch, factory, module_name
):
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: pytest.fail("API import must remain host-free"),
    )
    expected = importlib.import_module(module_name)
    assert getattr(scripting, factory)() is expected
    assert callable(expected.capture)
