# this_file: tests/test_ui_graph.py
"""Generic graph data has no foreign layout rules or native dependencies."""

import dataclasses
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fontlabapp.qt.ui_graph import UI_GRAPH_VERSION, Connection, Node, UIGraph


@pytest.mark.parametrize("frame", [None, {}, {"x": 1, "units": "percent"}])
def test_node_when_serialized_then_plain_frame_and_record_fields_round_trip(frame):
    node = Node(
        "n1",
        "Control",
        frame=frame,
        source_id="source",
        properties={"title": "OK"},
        resources={"image": "icon"},
        attribute_name="button",
    )
    data = node.to_json()
    assert data == {
        "node_id": "n1",
        "source_class": "Control",
        "source_id": "source",
        "parent_id": None,
        "frame": frame,
        "properties": {"title": "OK"},
        "resources": {"image": "icon"},
        "attribute_name": "button",
    }
    assert Node.from_json(json.loads(json.dumps(data))) == node
    if frame is not None:
        assert data["frame"] is not frame, (
            "serialization owns the top-level frame dictionary"
        )
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.source_class = "changed"


def test_graph_when_recording_then_order_connections_copies_and_extension_preserved():
    graph = UIGraph()
    properties, resources = {"text": "first"}, {"image": "one"}
    root = graph.add_node("Window")
    child = graph.add_node(
        "Button",
        parent_id=root.node_id,
        frame={"width": 20},
        properties=properties,
        resources=resources,
        source_id="source:1",
        attribute_name="button",
    )
    properties["text"], resources["image"] = "later", "two"
    edge = graph.connect(
        child.node_id, root.node_id, "changed", "callback", {"value": 1}
    )
    assert isinstance(edge, Connection) and edge.argument == {"value": 1}
    assert graph.children(root.node_id) == (child,)
    assert graph.children(child.node_id) == ()
    assert child.properties == {"text": "first"} and child.resources == {"image": "one"}
    data = graph.to_json()
    assert data["version"] == UI_GRAPH_VERSION == 1
    assert [item["node_id"] for item in data["nodes"]] == ["n1", "n2"]
    assert data["connections"] == [
        {
            "owner_id": "n2",
            "target_id": "n1",
            "event": "changed",
            "selector": "callback",
            "argument": {"value": 1},
        }
    ]
    restored = UIGraph.from_json(json.loads(json.dumps(data)))
    assert restored.to_json() == data
    assert restored.add_node("Label").node_id == "n3"


@pytest.mark.parametrize("operation", ["parent", "owner", "target", "children"])
def test_graph_when_reference_missing_then_existing_error(operation):
    graph = UIGraph()
    root = graph.add_node("Window")
    with pytest.raises(ValueError, match="unknown node id 'missing'"):
        if operation == "parent":
            graph.add_node("Button", parent_id="missing")
        elif operation == "owner":
            graph.connect("missing", root.node_id, "event", "action")
        elif operation == "target":
            graph.connect(root.node_id, "missing", "event", "action")
        else:
            graph.children("missing")


@pytest.mark.parametrize("version", [None, 0, 2, "1", True, False])
def test_graph_when_serialized_version_invalid_then_refused(version):
    with pytest.raises(ValueError, match="unsupported UI graph version"):
        UIGraph.from_json({"version": version, "nodes": [], "connections": []})


def test_graph_when_serialized_structure_invalid_then_ids_and_parents_checked():
    node = Node("n2", "Control").to_json()
    with pytest.raises(ValueError, match="breaks the n1, n2 sequence"):
        UIGraph.from_json({"version": 1, "nodes": [node], "connections": []})
    node.update(node_id="n1", parent_id="n2")
    with pytest.raises(ValueError, match="unknown node id"):
        UIGraph.from_json({"version": 1, "nodes": [node], "connections": []})
    with pytest.raises(ValueError, match="unknown node id"):
        UIGraph.from_json(
            {
                "version": 1,
                "nodes": [],
                "connections": [
                    {
                        "owner_id": "n1",
                        "target_id": "n2",
                        "event": "event",
                        "selector": "action",
                    }
                ],
            }
        )


def test_graph_when_empty_then_round_trip_and_first_id():
    empty = {"version": 1, "nodes": [], "connections": []}
    assert UIGraph().to_json() == empty
    assert UIGraph.from_json(empty).add_node("Control").node_id == "n1"


def test_graph_when_adapter_binds_node_type_then_creation_and_decode_use_it():
    class AdapterNode(Node):
        pass

    class AdapterGraph(UIGraph):
        _node_type = AdapterNode

    graph = AdapterGraph()
    assert isinstance(graph.add_node("Control"), AdapterNode)
    restored = AdapterGraph.from_json(graph.to_json())
    assert isinstance(restored, AdapterGraph)
    assert isinstance(restored._nodes["n1"], AdapterNode)


def test_import_when_cold_then_only_stdlib_and_no_foreign_layout_policy():
    import fontlabapp.qt.ui_graph as shared

    script = """
import importlib.abc,sys
class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "org":  # stdlib copy probes Jython and catches ImportError
            raise ModuleNotFoundError(fullname)
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'fontlabapp'}:
            raise AssertionError('Foreign import: ' + fullname)
sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.qt.ui_graph as shared
assert not any(hasattr(shared, name) for name in ('Frame', 'AUTO', 'resolve_frame'))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            script,
            str((Path(__file__).resolve().parents[1] / "src")),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
