"""
Map Graph — 地图节点图（卡牌/探索游戏可选模块）。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MapNode:
    """地图上的一个节点（位置/区域）。"""
    node_id: str
    name: str
    description: str = ""
    chapter: str = ""  # 解锁所需章节
    is_locked: bool = False
    connections: list[str] = field(default_factory=list)  # 连接的 node_id 列表
    metadata: dict = field(default_factory=dict)
    visited: bool = False

    def unlock(self) -> None:
        self.is_locked = False

    def visit(self) -> None:
        self.visited = True

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id, "name": self.name,
            "description": self.description, "chapter": self.chapter,
            "is_locked": self.is_locked,
            "connections": self.connections,
            "metadata": self.metadata, "visited": self.visited,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapNode":
        return cls(
            node_id=data["node_id"], name=data["name"],
            description=data.get("description", ""),
            chapter=data.get("chapter", ""),
            is_locked=data.get("is_locked", False),
            connections=data.get("connections", []),
            metadata=data.get("metadata", {}),
            visited=data.get("visited", False),
        )


class MapGraph:
    """地图有向图。"""

    def __init__(self):
        self.nodes: dict[str, MapNode] = {}
        self.current_node: Optional[str] = None

    def add_node(self, node: MapNode) -> None:
        self.nodes[node.node_id] = node
        if not self.current_node:
            self.current_node = node.node_id

    def get_current(self) -> Optional[MapNode]:
        if self.current_node:
            return self.nodes.get(self.current_node)
        return None

    def can_move_to(self, target_id: str) -> tuple[bool, str]:
        """
        检查是否可移动到目标节点。

        Returns (can_move, reason)。
        """
        current = self.get_current()
        if not current:
            return (False, "没有当前位置")
        target = self.nodes.get(target_id)
        if not target:
            return (False, f"未知地点: {target_id}")
        if target.is_locked:
            return (False, f"{target.name} 尚未解锁")
        if target_id not in current.connections:
            return (False, f"无法从 {current.name} 到达 {target.name}")
        return (True, "")

    def move_to(self, target_id: str) -> bool:
        can_move, reason = self.can_move_to(target_id)
        if not can_move:
            return False
        old = self.get_current()
        if old:
            old.visit()
        self.current_node = target_id
        target = self.nodes[target_id]
        target.visit()
        return True

    def get_available_destinations(self) -> list[MapNode]:
        """获取当前可到达的所有目标。"""
        current = self.get_current()
        if not current:
            return []
        result = []
        for nid in current.connections:
            node = self.nodes.get(nid)
            if node and not node.is_locked:
                result.append(node)
        return result

    def unlock_node(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node:
            node.unlock()
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "nodes": {n.node_id: n.to_dict() for n in self.nodes.values()},
            "current_node": self.current_node,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapGraph":
        graph = cls()
        for nid, nd in data.get("nodes", {}).items():
            graph.add_node(MapNode.from_dict(nd))
        graph.current_node = data.get("current_node")
        return graph
