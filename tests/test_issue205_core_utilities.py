# this_file: tests/test_issue205_core_utilities.py
"""Nested utility values, merge ownership and serialization error contracts."""

from collections import Counter
from datetime import datetime, timedelta
import hashlib
import importlib
from pathlib import Path, PureWindowsPath

import pytest

collections = importlib.import_module("fontlabapp.core.utils.collections")
merge = importlib.import_module("fontlabapp.core.utils.merge")
json = importlib.import_module("fontlabapp.core.utils.json")
text = importlib.import_module("fontlabapp.core.utils.text")


def test_nested_queries_when_mixed_values_then_order_types_and_membership_preserved():
    values = {
        "tree": [{"name": "A", "width": 0}, {"name": 3}, {"nested": {"name": "B"}}],
        "empty": [],
    }
    query = collections.dictextractor
    assert list(query.extract(values, "name")) == ["A", 3, "B"]
    assert list(query.find(values, "name", str)) == [
        {"name": "A", "width": 0},
        {"name": "B"},
    ]
    assert len(list(query.find(values, "name"))) == 3
    assert list(query.where(values, "B")) == [{"name": "B"}]
    assert list(query.where(values, 0, "width")) == [{"name": "A", "width": 0}]
    assert list(query.where(values, "A", "other")) == []
    assert query.contains(values, "nam", str)
    assert query.contains(values, "nam")
    assert not query.contains(values, "nam", list)
    assert not query.contains(values, "absent")
    assert list(query.extract((), "name")) == []


def test_attribdict_when_mutated_then_mapping_attributes_factories_and_hashes_are_exact(
    capsys,
):
    value = collections.attribdict(name="A", nested=collections.attribdict(width=0))
    value.name = "B"
    value.extra = "attribute"
    assert value["name"] == "B" and "extra" not in value
    assert value.extra == "attribute"
    del value.extra
    del value.name
    del value.absent
    assert "name" not in value
    assert value.as_dict() == {"nested": {"width": 0}}
    assert repr(value) == "attribdict({'nested': {'width': 0}})"
    assert list(value.extract("width")) == [0]
    assert list(value.find("width", int)) == [{"width": 0}]
    assert list(value.where(0, "width")) == [{"width": 0}]
    assert value.contains("wid", int)
    value.dir()
    assert "nested" in capsys.readouterr().out
    value.factory(list)
    assert value.new == []
    value.lock()
    with pytest.raises(AttributeError):
        _ = value.no_such_key
    with pytest.raises(KeyError):
        _ = value["no_such_key"]
    assert hash(collections.attribdict(a=[1, 2], b={"x": (3,)})) == hash(
        collections.attribdict(b={"x": (3,)}, a=[1, 2])
    )


@pytest.mark.parametrize(
    "strategy", [merge.Strategy.ADDITIVE, merge.Strategy.TYPESAFE_ADDITIVE]
)
def test_merge_when_additive_then_collections_combine_and_sources_stay_owned(strategy):
    source = {
        "list": [2],
        "tuple": (2,),
        "set": {2},
        "counter": Counter(A=2),
        "scalar": 2,
    }
    destination = {
        "list": [1],
        "tuple": (1,),
        "set": {1},
        "counter": Counter(A=1),
        "scalar": 1,
    }
    assert merge.deepmerge(destination, source, strategy=strategy) is destination
    assert destination == {
        "list": [1, 2],
        "tuple": (1, 2),
        "set": {1, 2},
        "counter": Counter(A=3),
        "scalar": 2,
    }
    destination["list"].append(3)
    assert source["list"] == [2]


def test_merge_when_replacing_nested_or_identical_values_then_exact_copy_and_refusal():
    shared = [1]
    source = {"nested": {"new": [2]}, "counter": Counter(B=2), "shared": shared}
    result = merge.deepmerge(
        {"nested": {"old": 1}, "counter": Counter(A=1), "shared": shared}, source
    )
    assert result == {
        "nested": {"old": 1, "new": [2]},
        "counter": Counter(A=1, B=2),
        "shared": [1],
    }
    assert result["shared"] is shared
    result["nested"]["new"].append(3)
    assert source["nested"]["new"] == [2]
    with pytest.raises(TypeError, match="differs from source type"):
        merge.deepmerge(
            {"x": 1}, {"x": "bad"}, strategy=merge.Strategy.TYPESAFE_REPLACE
        )
    assert merge.deepmerge(
        {"x": [1]}, {"x": (2,)}, strategy=merge.Strategy.ADDITIVE
    ) == {"x": (2,)}


def test_json_when_special_values_then_roundtrip_or_original_type_error(monkeypatch):
    monkeypatch.setattr(json, "WindowsPath", PureWindowsPath)
    digest = hashlib.sha256(b"owned")
    values = [
        b"A\xff",
        "text",
        Path("owned/file"),
        PureWindowsPath("C:/owned"),
        datetime(2026, 1, 2),
        timedelta(seconds=3),
        digest,
    ]
    expected = [
        "A",
        "text",
        "owned/file",
        "C:\\owned",
        "2026-01-02T00:00:00",
        "0:00:03",
        digest.hexdigest(),
    ]
    assert [json.stringify(v) for v in values] == expected
    assert json.loads(json.dumps(values, cls=json.SmartJSONEncoder)) == expected
    assert json.stringify(object()) is None
    with pytest.raises(TypeError, match="not JSON serializable"):
        json.dumps(object(), cls=json.SmartJSONEncoder)


def test_markdown_when_qt_backend_then_body_only_and_single_paragraph_unwrapped(
    monkeypatch,
):
    from types import SimpleNamespace as NS

    calls = []
    editor = NS(
        setMarkdown=calls.append,
        toHtml=lambda: "<html><body><p><b>A</b></p></body></html>",
    )
    monkeypatch.setattr(text, "pymd", None)
    monkeypatch.setattr(text, "qtmd", editor)
    assert text.to_html("**A**", md=True) == "<b>A</b>\n"
    assert text.to_html("A\nB", md=True) == "<p><b>A</b></p>\n"
    assert calls == ["**A**", "A\nB"]
    assert text.style_html("<b>A</b>", styled=False) == "<b>A</b>"
    assert len(text.timestamp()) == 13


def test_lazy_utility_exports_when_requested_then_star_import_and_unknown_names_are_exact():
    package = importlib.import_module("fontlabapp.core.utils")
    scope = {}
    exec("from fontlabapp.core.utils import *", scope)
    assert scope["attribdict"] is collections.attribdict
    assert scope["deepmerge"] is merge.deepmerge and scope["to_html"] is text.to_html
    assert package.__getattr__("json") is json
    for name in ("__not_exported__", "not_a_utility"):
        with pytest.raises(AttributeError, match=name):
            package.__getattr__(name)
