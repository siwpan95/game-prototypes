"""
统一游戏状态管理。

整合玩家属性（PlayerState）、意象网络（ImageryNetwork）与全局游戏状态（GameState）。
支持 to_dict() / from_dict() 序列化，用于存档。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Chapter(Enum):
    """章节枚举。"""
    PROLOGUE = "prologue"
    CH1 = "chapter_1"
    CH2 = "chapter_2"
    CH3 = "chapter_3"
    CH4 = "chapter_4"
    CH5 = "chapter_5"
    CH6 = "chapter_6"
    CH7 = "chapter_7"
    CH8 = "chapter_8"
    CH9 = "chapter_9"
    CH10 = "chapter_10"
    EPILOGUE = "epilogue"


# ============================================================
# PlayerState — 玩家状态
# ============================================================

@dataclass
class PlayerState:
    """玩家状态数据。

    属性:
        hp: 当前生命值
        max_hp: 最大生命值
        sanity: 当前理智
        max_sanity: 最大理智
        corruption: 腐化值 [0, 100]
        chapter: 当前章节
        items: 物品 ID 列表
        flags: 通用标志位字典
    """

    hp: int = 100
    max_hp: int = 100
    sanity: int = 70
    max_sanity: int = 100
    corruption: int = 0
    chapter: Chapter = Chapter.PROLOGUE
    items: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    total_playtime: float = 0.0

    # --- 属性调整方法 ---

    def adjust_hp(self, delta: int) -> int:
        """调整 HP，返回实际变化量。"""
        old = self.hp
        self.hp = max(0, min(self.max_hp, self.hp + delta))
        return self.hp - old

    def adjust_sanity(self, delta: int) -> int:
        """调整理智值，返回实际变化量。"""
        old = self.sanity
        self.sanity = max(0, min(self.max_sanity, self.sanity + delta))
        return self.sanity - old

    def adjust_corruption(self, delta: int) -> int:
        """调整腐化值，返回实际变化量。"""
        old = self.corruption
        self.corruption = max(0, min(100, self.corruption + delta))
        return self.corruption - old

    # --- 物品管理 ---

    def has_item(self, item_id: str) -> bool:
        """检查是否拥有指定物品。"""
        return item_id in self.items

    def add_item(self, item_id: str) -> bool:
        """添加物品，已存在则返回 False。"""
        if item_id in self.items:
            return False
        self.items.append(item_id)
        return True

    def remove_item(self, item_id: str) -> bool:
        """移除物品，成功返回 True。"""
        try:
            self.items.remove(item_id)
            return True
        except ValueError:
            return False

    # --- 标志位 ---

    def set_flag(self, flag: str, value: Any = True) -> None:
        """设置标志位。"""
        self.flags[flag] = value

    def get_flag(self, flag: str, default: Any = False) -> Any:
        """获取标志位。"""
        return self.flags.get(flag, default)

    def has_flag(self, flag: str) -> bool:
        """检查标志位是否为真。"""
        return bool(self.flags.get(flag, False))

    # --- 计算属性 ---

    @property
    def is_alive(self) -> bool:
        """玩家是否存活。"""
        return self.hp > 0

    @property
    def is_critical(self) -> bool:
        """是否处于危急状态。"""
        return self.sanity <= 10 or self.hp <= 0

    # --- 序列化 ---

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "hp": self.hp,
            "max_hp": self.max_hp,
            "sanity": self.sanity,
            "max_sanity": self.max_sanity,
            "corruption": self.corruption,
            "chapter": self.chapter.value,
            "items": self.items,
            "flags": self.flags,
            "total_playtime": self.total_playtime,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerState":
        """从字典反序列化。"""
        ps = cls(
            hp=data.get("hp", 100),
            max_hp=data.get("max_hp", 100),
            sanity=data.get("sanity", 70),
            max_sanity=data.get("max_sanity", 100),
            corruption=data.get("corruption", 0),
            chapter=Chapter(data.get("chapter", "prologue")),
            items=data.get("items", []),
            total_playtime=data.get("total_playtime", 0.0),
        )
        ps.flags = data.get("flags", {})
        return ps


# ============================================================
# ImageryNetwork — 意象网络（简化版）
# ============================================================

@dataclass
class ImageryNode:
    """意象网络中的一个节点。

    属性:
        id: 节点唯一标识
        name: 节点名称
        description: 节点描述
        discovered: 是否已被发现
        resonance_level: 共鸣度 [0.0, 1.0]
        connections: 连接到其他节点的强度映射
        symbols: 关联符号列表
    """

    id: str
    name: str = ""
    description: str = ""
    discovered: bool = False
    resonance_level: float = 0.0
    connections: dict[str, float] = field(default_factory=dict)
    symbols: list[str] = field(default_factory=list)

    def connect_to(self, other_id: str, strength: float = 0.5) -> None:
        """连接到另一个节点，累加强度（上限 1.0）。"""
        current = self.connections.get(other_id, 0.0)
        self.connections[other_id] = min(1.0, current + strength)

    def resonate(self, amount: float = 0.1) -> None:
        """提升共鸣度（上限 1.0）。"""
        self.resonance_level = min(1.0, self.resonance_level + amount)

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "discovered": self.discovered,
            "resonance_level": self.resonance_level,
            "connections": self.connections,
            "symbols": self.symbols,
        }


@dataclass
class ImageryNetwork:
    """意象网络 — 管理意象节点的发现与共鸣。

    支持节点发现、共鸣检测和跨节点共振传播。
    """

    nodes: dict[str, ImageryNode] = field(default_factory=dict)
    active_resonances: set[tuple[str, str]] = field(default_factory=set)

    def add_node(self, node: ImageryNode) -> None:
        """添加一个意象节点。"""
        self.nodes[node.id] = node

    def get_node(self, node_id: str) -> ImageryNode | None:
        """获取指定节点。"""
        return self.nodes.get(node_id)

    def discover(self, node_id: str) -> bool:
        """发现一个节点并触发共振传播。

        发现时自身共鸣 +0.3，所有连接节点共鸣 +0.05。
        返回是否为新发现。
        """
        node = self.nodes.get(node_id)
        if node and not node.discovered:
            node.discovered = True
            node.resonate(0.3)
            for connected_id in node.connections:
                connected = self.nodes.get(connected_id)
                if connected:
                    connected.resonate(0.05)
            return True
        return False

    def check_resonance(self, node_a: str, node_b: str) -> float:
        """检测两节点间的共鸣强度（双向平均）。"""
        a = self.nodes.get(node_a)
        b = self.nodes.get(node_b)
        if not a or not b:
            return 0.0
        direct = a.connections.get(node_b, 0.0)
        reverse = b.connections.get(node_a, 0.0)
        return (direct + reverse) / 2

    @property
    def discovery_count(self) -> int:
        """已发现节点数。"""
        return sum(1 for n in self.nodes.values() if n.discovered)

    @property
    def total_nodes(self) -> int:
        """总节点数。"""
        return len(self.nodes)

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "active_resonances": [list(r) for r in self.active_resonances],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImageryNetwork":
        """从字典反序列化。"""
        net = cls()
        for nid, nd in data.get("nodes", {}).items():
            node = ImageryNode(
                id=nd["id"],
                name=nd.get("name", ""),
                description=nd.get("description", ""),
                discovered=nd.get("discovered", False),
                resonance_level=nd.get("resonance_level", 0.0),
                connections=nd.get("connections", {}),
                symbols=nd.get("symbols", []),
            )
            net.nodes[nid] = node
        net.active_resonances = {tuple(r) for r in data.get("active_resonances", [])}
        return net


# ============================================================
# GameState — 全局游戏状态
# ============================================================

@dataclass
class GameState:
    """全局游戏状态。

    整合 PlayerState（玩家属性）+ ImageryNetwork（意象网络，可选）
    + 通用变量 + 事件历史。
    """

    player: PlayerState = field(default_factory=PlayerState)
    imagery_network: ImageryNetwork = field(default_factory=ImageryNetwork)
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    _last_tick: float = 0.0  # 内部计时

    # --- 标志位代理 ---

    def set_flag(self, flag: str, value: Any = True) -> None:
        """设置标志位（代理到 PlayerState）。"""
        self.player.set_flag(flag, value)

    def get_flag(self, flag: str, default: Any = False) -> Any:
        """获取标志位。"""
        return self.player.get_flag(flag, default)

    def has_flag(self, flag: str) -> bool:
        """检查标志位是否为真。"""
        return self.player.has_flag(flag)

    # --- 变量管理 ---

    def set_var(self, key: str, value: Any) -> None:
        """设置全局变量。"""
        self.variables[key] = value

    def get_var(self, key: str, default: Any = None) -> Any:
        """获取全局变量。"""
        return self.variables.get(key, default)

    # --- 事件记录 ---

    def record_event(self, event_type: str, detail: str) -> None:
        """记录一条游戏事件。"""
        now = time.time()
        self.history.append({
            "time": now,
            "type": event_type,
            "detail": detail,
            "chapter": self.player.chapter.value,
        })

    # --- 时间推进 ---

    def advance(self) -> None:
        """推进游戏时间（计算游玩时长）。"""
        now = time.time()
        if self._last_tick > 0:
            self.player.total_playtime = self.player.total_playtime + (now - self._last_tick)
        self._last_tick = now

    def tick(self) -> None:
        """便捷方法：标记一次时间帧推进。"""
        self._last_tick = time.time()

    # --- 序列化 ---

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "player": self.player.to_dict(),
            "imagery_network": self.imagery_network.to_dict(),
            "variables": self.variables,
            "history": self.history[-50:],  # 仅保留最近 50 条
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        """从字典反序列化。"""
        state = cls(
            player=PlayerState.from_dict(data.get("player", {})),
            imagery_network=ImageryNetwork.from_dict(
                data.get("imagery_network", {"nodes": {}, "active_resonances": []})
            ),
            variables=data.get("variables", {}),
            history=data.get("history", []),
        )
        return state
