# this_file: src/fontlabapp/qt/ui_graph.py
"""Versioned host-free UI records, ordered node trees and event connections.

Frame dictionaries are opaque data. Layout resolution and foreign UI APIs are
caller policy; the shared graph neither imports a host nor interprets them.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

UI_GRAPH_VERSION = 1


@dataclass(frozen=True)
class Connection:
    """An event wired from an owner node to a target node's selector."""

    owner_id: str
    target_id: str
    event: str
    selector: str
    argument: Any = None


@dataclass(frozen=True)
class Node:
    """One source UI object; properties and resources hold plain JSON values."""

    node_id: str
    source_class: str
    source_id: str | None = None
    parent_id: str | None = None
    frame: Mapping[str, Any] | None = None
    properties: Mapping[str, Any] = field(default_factory=dict)
    resources: Mapping[str, Any] = field(default_factory=dict)
    attribute_name: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "source_class": self.source_class,
            "source_id": self.source_id,
            "parent_id": self.parent_id,
            "frame": self._frame_json(),
            "properties": dict(self.properties),
            "resources": dict(self.resources),
            "attribute_name": self.attribute_name,
        }

    def _frame_json(self) -> dict[str, Any] | None:
        """Copy plain frame facts; a compatibility adapter may encode its own type."""
        return dict(self.frame) if self.frame is not None else None

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Node":
        return cls(**data)


class UIGraph:
    """Mutable builder: nodes keep insertion order, ids are n1, n2, ..."""

    _node_type = Node

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._connections: list[Connection] = []

    def add_node(
        self,
        source_class: str,
        *,
        parent_id: str | None = None,
        frame: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        resources: Mapping[str, Any] | None = None,
        source_id: str | None = None,
        attribute_name: str | None = None,
    ) -> Node:
        self._require(parent_id)
        node = self._node_type(
            node_id=f"n{len(self._nodes) + 1}",
            source_class=source_class,
            source_id=source_id,
            parent_id=parent_id,
            frame=frame,
            properties=dict(properties or {}),
            resources=dict(resources or {}),
            attribute_name=attribute_name,
        )
        self._nodes[node.node_id] = node
        return node

    def connect(
        self,
        owner_id: str,
        target_id: str,
        event: str,
        selector: str,
        argument: Any = None,
    ) -> Connection:
        self._require(owner_id)
        self._require(target_id)
        connection = Connection(owner_id, target_id, event, selector, argument)
        self._connections.append(connection)
        return connection

    def children(self, node_id: str) -> tuple[Node, ...]:
        self._require(node_id)
        return tuple(n for n in self._nodes.values() if n.parent_id == node_id)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": UI_GRAPH_VERSION,
            "nodes": [n.to_json() for n in self._nodes.values()],
            "connections": [vars(c).copy() for c in self._connections],
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "UIGraph":
        version = data.get("version")
        if version != UI_GRAPH_VERSION or isinstance(version, bool):
            raise ValueError(
                f"unsupported UI graph version {version!r}; expected {UI_GRAPH_VERSION}"
            )
        graph = cls()
        for raw in data["nodes"]:
            node = graph._node_type.from_json(raw)
            if node.node_id != f"n{len(graph._nodes) + 1}":
                raise ValueError(f"node id {node.node_id!r} breaks the n1, n2 sequence")
            graph._require(node.parent_id)
            graph._nodes[node.node_id] = node
        for raw in data["connections"]:
            graph.connect(**raw)
        return graph

    def _require(self, node_id: str | None) -> None:
        if node_id is not None and node_id not in self._nodes:
            raise ValueError(f"unknown node id {node_id!r}")
