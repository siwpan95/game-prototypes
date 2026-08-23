"""
地图节点图 — 章节/区域间的导航图结构。

用于表示游戏世界中的地点连接关系，支持锁定/解锁、访问追踪和路径查询。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MapNode:
    """地图上的一个节点（位置/区域）。

    属性:
        node_id: 节点唯一标识
        name: 显示名称
        description: 节点描述
        chapter: 解锁所需章节
        is_locked: 是否锁定
        connections: 连接的 node_id 列表
        visited: 是否已访问
        metadata: 扩展元数据
    """

    node_id: str
    name: str = ""
    description: str = ""
    chapter: str = ""
    is_locked: bool = False
    connections: list[str] = field(default_factory=list)
    visited: bool = False
    metadata: dict = field(default_factory=dict)

    def connect_to(self, other_id: str) -> None:
        """添加一条到另一节点的连接。"""
        if other_id not in self.connections:
            self.connections.append(other_id)

    def disconnect_from(self, other_id: str) -> bool:
        """移除一条到另一节点的连接。"""
        try:
            self.connections.remove(other_id)
            return True
        except ValueError:
            return False

    def is_connected_to(self, other_id: str) -> bool:
        """检查是否连接到另一节点。"""
        return other_id in self.connections

    def unlock(self) -> None:
        """解锁节点。"""
        self.is_locked = False

    def lock(self) -> None:
        """锁定节点。"""
        self.is_locked = True

    def visit(self) -> None:
        """标记为已访问。"""
        self.visited = True

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "description": self.description,
            "chapter": self.chapter,
            "is_locked": self.is_locked,
            "connections": self.connections,
            "visited": self.visited,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapNode":
        """从字典反序列化。"""
        return cls(
            node_id=data["node_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            chapter=data.get("chapter", ""),
            is_locked=data.get("is_locked", False),
            connections=data.get("connections", []),
            visited=data.get("visited", False),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        locked = "[锁定]" if self.is_locked else ""
        visited_mark = "[已访问]" if self.visited else ""
        return f"MapNode({self.node_id}{locked}{visited_mark})"


# ============================================================
# MapGraph
# ============================================================

@dataclass
class MapGraph:
    """地图有向图 — 管理节点间的导航与解锁。

    用法:
        graph = MapGraph()
        graph.add_node(MapNode("hub", "大厅", connections=["room_a"]))
        graph.add_node(MapNode("room_a", "房间A", connections=["hub"]))
        ok, reason = graph.can_move_to("room_a")
        if ok:
            graph.move_to("room_a")
    """

    nodes: dict[str, MapNode] = field(default_factory=dict)
    current_node: str | None = None

    # ================================================================
    # 节点管理
    # ================================================================

    def add_node(self, node: MapNode) -> None:
        """添加一个节点。首个添加的节点自动设为当前位置。"""
        self.nodes[node.node_id] = node
        if self.current_node is None:
            self.current_node = node.node_id

    def remove_node(self, node_id: str) -> bool:
        """移除一个节点。同时清理其他节点到该节点的连接。"""
        if node_id not in self.nodes:
            return False
        del self.nodes[node_id]
        # 清理残留引用
        for n in self.nodes.values():
            if node_id in n.connections:
                n.connections.remove(node_id)
        if self.current_node == node_id:
            self.current_node = None
        return True

    def get_node(self, node_id: str) -> MapNode | None:
        """获取指定节点。"""
        return self.nodes.get(node_id)

    # ================================================================
    # 导航
    # ================================================================

    def get_current(self) -> Optional[MapNode]:
        """获取当前节点。"""
        if self.current_node:
            return self.nodes.get(self.current_node)
        return None

    def set_current(self, node_id: str) -> bool:
        """直接设置当前节点（不检查可达性）。"""
        if node_id in self.nodes:
            self.current_node = node_id
            return True
        return False

    def can_move_to(self, target_id: str) -> tuple[bool, str]:
        """检查是否可移动到目标节点。

        返回 (can_move, reason).
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
        """移动到目标节点。成功返回 True。"""
        can_move, _ = self.can_move_to(target_id)
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
        """获取当前节点可达的所有目标节点（排除锁定的）。"""
        current = self.get_current()
        if not current:
            return []
        result: list[MapNode] = []
        for nid in current.connections:
            node = self.nodes.get(nid)
            if node and not node.is_locked:
                result.append(node)
        return result

    def get_all_destinations(self) -> list[MapNode]:
        """获取当前节点的所有连接节点（含锁定的）。"""
        current = self.get_current()
        if not current:
            return []
        result: list[MapNode] = []
        for nid in current.connections:
            node = self.nodes.get(nid)
            if node:
                result.append(node)
        return result

    # ================================================================
    # 锁定/解锁
    # ================================================================

    def unlock_node(self, node_id: str) -> bool:
        """解锁指定节点。"""
        node = self.nodes.get(node_id)
        if node:
            node.unlock()
            return True
        return False

    def lock_node(self, node_id: str) -> bool:
        """锁定指定节点。"""
        node = self.nodes.get(node_id)
        if node:
            node.lock()
            return True
        return False

    def unlock_by_chapter(self, chapter: str) -> int:
        """根据章节解锁所有匹配的节点，返回解锁数量。"""
        count = 0
        for node in self.nodes.values():
            if node.chapter == chapter and node.is_locked:
                node.unlock()
                count += 1
        return count

    # ================================================================
    # 查询
    # ================================================================

    @property
    def visited_nodes(self) -> list[MapNode]:
        """获取所有已访问节点。"""
        return [n for n in self.nodes.values() if n.visited]

    @property
    def locked_nodes(self) -> list[MapNode]:
        """获取所有锁定节点。"""
        return [n for n in self.nodes.values() if n.is_locked]

    @property
    def unlocked_nodes(self) -> list[MapNode]:
        """获取所有已解锁节点。"""
        return [n for n in self.nodes.values() if not n.is_locked]

    # ================================================================
    # 序列化
    # ================================================================

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "current_node": self.current_node,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapGraph":
        """从字典反序列化。"""
        graph = cls()
        for nid, nd in data.get("nodes", {}).items():
            graph.add_node(MapNode.from_dict(nd))
        graph.current_node = data.get("current_node")
        return graph

    def __repr__(self) -> str:
        return f"MapGraph({len(self.nodes)} nodes, current={self.current_node})"
