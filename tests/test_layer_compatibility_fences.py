# this_file: tests/test_layer_compatibility_fences.py
"""Content/selection/context drift and bounded whole-call refusal controls."""

from types import SimpleNamespace as NS

import pytest
import test_layer_compatibility_native as fixtures

domain, source, path, shape = (
    fixtures.domain,
    fixtures.source,
    fixtures.path,
    fixtures.shape,
)
import fontlabapp.masters.layers.compatibility._records as records
import fontlabapp.masters.layers.compatibility.native as api


@pytest.mark.parametrize(
    "field",
    [
        "glyph_id",
        "glyph_name",
        "glyph_null",
        "layer_id",
        "layer_name",
        "layer_null",
        "package",
        "master",
    ],
)
def test_read_when_captured_occurrence_stale_then_refuse(domain, field):
    selected = api.selection.capture(float("inf"))
    if field == "glyph_id":
        domain.glyph.id = 999
    elif field == "glyph_name":
        domain.glyph.name = "Changed"
    elif field == "glyph_null":
        domain.glyph.isNull = True
    elif field == "layer_id":
        domain.regular.id = 999
    elif field == "layer_name":
        domain.regular.name = "Changed"
    elif field == "layer_null":
        domain.regular.isNull = True
    elif field == "package":
        domain.glyph.package = NS(id=999)
    else:
        domain.package.master = "Bold"
    with pytest.raises(ValueError, match="changed"):
        api._read(selected, float("inf"))


@pytest.mark.parametrize(
    "change", ["selection", "node", "anchor", "component", "domain", "final_context"]
)
def test_capture_when_source_changes_between_reads_then_no_partial_report(
    domain, monkeypatch, change
):
    domain.regular.shapes = [shape([path(["on", "curve", "on"])])]
    domain.regular.anchors = [NS(id=80, name="top")]
    original = api.selection.capture
    calls = []

    def capture(deadline):
        calls.append(1)
        if len(calls) == 2:
            if change == "selection":
                domain.legacy.Selected = lambda i: False
            elif change == "node":
                domain.regular.shapes = [shape([path(["on", "on"])])]
            elif change == "anchor":
                domain.regular.anchors[0].id = 81
            elif change == "component":
                domain.regular.shapes.append(shape(base="x"))
            elif change == "domain":
                domain.package.masters = ["Bold", "Regular"]
        return original(deadline)

    monkeypatch.setattr(api.selection, "capture", capture)
    if change == "final_context":
        monkeypatch.setattr(
            api.selection, "document_context", lambda d: (999, "Regular")
        )
    with pytest.raises(ValueError, match="changed"):
        api.capture()


@pytest.mark.parametrize("bad", ["topology", "ambiguous", "nonbool"])
def test_node_records_when_topology_unknown_then_refuse(bad):
    p = path(["on"])
    if bad == "topology":
        p.closed = 1
    else:
        node = p.nodes()[0]
        p.nodes = lambda: [node]
        if bad == "ambiguous":
            node.isOff = lambda: True
        else:
            node.isOn = lambda: 1
    with pytest.raises(ValueError):
        records.nodes(p, float("inf"))


def test_native_deadline_when_expired_then_no_prefix(domain, monkeypatch):
    selected = api.selection.capture(float("inf"))
    monkeypatch.setattr(api.selection, "capture", lambda d: selected)
    monkeypatch.setattr(api, "monotonic", lambda: 0.0)
    monkeypatch.setattr(records, "monotonic", lambda: 3.0)
    with pytest.raises(TimeoutError, match="expired"):
        api.capture()
