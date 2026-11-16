# this_file: tests/test_master_report_domain.py
"""Actual native-shaped masters reader must never inspect unrelated auxiliaries."""

from types import SimpleNamespace as NS

import fontlabapp.masters.node_report.native as api
import test_layer_compatibility_native as helper

source = helper.source
domain = helper.domain


class UnrelatedAuxiliary:
    """Every access fails: the original report never requests auxiliary data."""

    def __getattr__(self, name):
        raise AssertionError("Unrelated auxiliary read: " + name)


def test_capture_when_unreadable_auxiliary_and_metadata_then_master_paths_only(domain):
    domain.glyph.layers = [domain.bold, UnrelatedAuxiliary(), domain.regular]
    domain.regular.shapes = [helper.shape([helper.path(["on", "curve", "on"], True)])]
    domain.bold.shapes = []
    del domain.regular.anchors
    del domain.bold.anchors
    groups = api.capture()
    assert len(groups) == 1
    assert [layer.name for layer in groups[0].layers] == ["Regular", "Bold"]
    assert groups[0].layers[0].paths == (("offcurve", "curve", "line"),)


def test_capture_when_component_base_unreadable_then_skip_own_path_counts(domain):
    component = NS(id=50, isComponent=True)
    domain.regular.shapes = [component]
    assert api.capture()[0].layers[0].paths == ()


import pytest


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "invalid",
        "foreign",
        "wrongname",
        "role",
        "mask",
        "service",
        "shaperole",
        "generated",
        "masters_empty",
        "masters_bad",
        "masters_duplicate",
        "current_master",
        "duplicate_id",
        "glyphid",
        "layerid",
        "glyphname",
        "layername",
        "glyphpackage",
        "packageid",
        "context",
    ],
)
def test_real_master_reader_when_required_domain_invalid_then_no_partial(domain, fault):
    if fault == "missing":
        domain.glyph.findLayer = lambda name: None
    if fault == "invalid":
        domain.regular.isValid = False
    if fault == "foreign":
        domain.regular.glyph = NS(id=999)
    if fault == "wrongname":
        domain.regular.name = "Other"
    if fault == "role":
        domain.regular.isMasterLayer = False
    if fault == "mask":
        domain.regular.isMaskLayer = True
    if fault == "service":
        domain.regular.isService = True
    if fault == "shaperole":
        domain.regular.shapes = [NS(id=9, isComponent=1)]
    if fault == "generated":
        domain.regular.shapes = [NS(id=9, isComponent=False, isComposite=True)]
    if fault == "masters_empty":
        domain.package.masters = []
    if fault == "masters_bad":
        domain.package.masters = ["Regular", None]
    if fault == "masters_duplicate":
        domain.package.masters = ["Regular", "Regular"]
    if fault == "current_master":
        domain.package.masters = ["Bold"]
    if fault == "duplicate_id":
        domain.bold.id = domain.regular.id
    if fault in [
        "glyphid",
        "layerid",
        "glyphname",
        "layername",
        "glyphpackage",
        "packageid",
        "context",
    ]:
        first = api.selection.capture(float("inf"))
        if fault == "glyphid":
            domain.glyph.id = 999
        if fault == "layerid":
            first.occurrences[0].layer.id = 999
        if fault == "glyphname":
            domain.glyph.name = "changed"
        if fault == "layername":
            first.occurrences[0].layer.name = "changed"
        if fault == "glyphpackage":
            domain.glyph.package = NS(id=999)
        if fault == "packageid":
            domain.package.id = 999
        if fault == "context":
            domain.package.master = "Bold"
        with pytest.raises(ValueError):
            api._read(first, float("inf"))
    else:
        with pytest.raises(ValueError):
            api.capture()


def test_real_master_reader_when_deadline_expired_then_refuse(domain):
    with pytest.raises(TimeoutError):
        api._master(domain.glyph, "Regular", 0)
