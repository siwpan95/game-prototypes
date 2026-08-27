"""
Game State — 统一游戏状态管理。

合并三种架构模式的状态需求：
  - 标准模式：PlayerState（sanity/corruption/chapter） + ImageryNetwork
  - 领域驱动模式：current_room + inventory + flags + visited_rooms
  - 通用：variables (key-value) + history log

所有状态支持 to_dict() / from_dict() 序列化，用于存档。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ============================================================
# 枚举定义（各游戏可覆写）
# ============================================================

class Chapter(Enum):
    """章节枚举 — 子类或替换以适配不同游戏。"""
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


class EmotionalState(Enum):
    CONTEMPLATIVE = "contemplative"
    ANXIOUS = "anxious"
    HOPEFUL = "hopeful"
    GRIEVING = "grieving"
    RESIGNED = "resigned"


class BranchPath(Enum):
    MAIN = "main"
    TRANSLATION = "translation"
    DISTANCE = "distance"
    MULTIPLICATION = "multiplication"
    WITNESS = "witness"
    MEMORY = "memory"


class PuzzleType(Enum):
    TEXT_DECRYPT = "text_decrypt"
    IMAGERY_MATCH = "imagery_match"
    MORAL_DILEMMA = "moral_dilemma"
    COMBAT = "combat"
    ITEM_USE = "item_use"


# ============================================================
# Player State
# ============================================================

@dataclass
class PlayerState:
    """
    玩家状态。

    标准模式使用 sanity/corruption/chapter。
    领域驱动模式使用 current_room + inventory。
    两种模式共存，未使用的字段保持默认值即可。
    """
    # --- 标准模式字段 ---
    sanity: int = 70
    max_sanity: int = 100
    corruption: int = 0
    current_chapter: Chapter = Chapter.PROLOGUE
    emotional_state: EmotionalState = EmotionalState.CONTEMPLATIVE

    # --- 探索与收集 ---
    discovered_imagery: set[str] = field(default_factory=set)
    solved_puzzles: list[str] = field(default_factory=list)
    made_choices: dict[str, str] = field(default_factory=dict)
    collected_fragments: list[str] = field(default_factory=list)
    read_entries: set[str] = field(default_factory=set)

    # --- 领域驱动模式字段 ---
    current_room: str = ""
    inventory_items: list[str] = field(default_factory=list)
    visited_rooms: set[str] = field(default_factory=set)
    triggered_narratives: set[str] = field(default_factory=set)

    # --- 卡牌战斗字段 ---
    hp: int = 100
    max_hp: int = 100
    nerve: int = 50
    max_nerve: int = 50

    # --- 统计 ---
    puzzles_attempted: int = 0
    puzzles_solved: int = 0
    hints_used: int = 0
    total_playtime: float = 0.0
    shards_collected: int = 0

    # --- 通用标志位字典（替代硬编码 flags） ---
    flags: dict[str, Any] = field(default_factory=dict)

    def adjust_sanity(self, delta: int) -> int:
        old = self.sanity
        self.sanity = max(0, min(self.max_sanity, self.sanity + delta))
        return self.sanity - old

    def adjust_corruption(self, delta: int) -> int:
        old = self.corruption
        self.corruption = max(0, min(100, self.corruption + delta))
        return self.corruption - old

    def adjust_hp(self, delta: int) -> int:
        old = self.hp
        self.hp = max(0, min(self.max_hp, self.hp + delta))
        return self.hp - old

    def adjust_nerve(self, delta: int) -> int:
        old = self.nerve
        self.nerve = max(0, min(self.max_nerve, self.nerve + delta))
        return self.nerve - old

    def discover_imagery(self, imagery_id: str) -> None:
        self.discovered_imagery.add(imagery_id)

    def record_choice(self, choice_point: str, choice: str) -> None:
        self.made_choices[choice_point] = choice

    def add_fragment(self, fragment_id: str) -> None:
        if fragment_id not in self.collected_fragments:
            self.collected_fragments.append(fragment_id)

    def has_item(self, item_name: str) -> bool:
        return item_name in self.inventory_items

    def add_item(self, item_name: str) -> None:
        if item_name not in self.inventory_items:
            self.inventory_items.append(item_name)

    def remove_item(self, item_name: str) -> bool:
        if item_name in self.inventory_items:
            self.inventory_items.remove(item_name)
            return True
        return False

    def visit_room(self, room_id: str) -> None:
        self.visited_rooms.add(room_id)

    def has_visited(self, room_id: str) -> bool:
        return room_id in self.visited_rooms

    def trigger_narrative(self, narrative_id: str) -> bool:
        if narrative_id in self.triggered_narratives:
            return False
        self.triggered_narratives.add(narrative_id)
        return True

    @property
    def solve_rate(self) -> float:
        if self.puzzles_attempted == 0:
            return 0.0
        return self.puzzles_solved / self.puzzles_attempted

    @property
    def is_critical(self) -> bool:
        return self.sanity <= 10 or self.hp <= 0

    def to_dict(self) -> dict:
        return {
            "sanity": self.sanity,
            "max_sanity": self.max_sanity,
            "corruption": self.corruption,
            "current_chapter": self.current_chapter.value,
            "emotional_state": self.emotional_state.value,
            "discovered_imagery": list(self.discovered_imagery),
            "solved_puzzles": self.solved_puzzles,
            "made_choices": self.made_choices,
            "collected_fragments": self.collected_fragments,
            "read_entries": list(self.read_entries),
            "current_room": self.current_room,
            "inventory_items": self.inventory_items,
            "visited_rooms": list(self.visited_rooms),
            "triggered_narratives": list(self.triggered_narratives),
            "hp": self.hp,
            "max_hp": self.max_hp,
            "nerve": self.nerve,
            "max_nerve": self.max_nerve,
            "puzzles_attempted": self.puzzles_attempted,
            "puzzles_solved": self.puzzles_solved,
            "hints_used": self.hints_used,
            "total_playtime": self.total_playtime,
            "shards_collected": self.shards_collected,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerState":
        ps = cls(
            sanity=data.get("sanity", 70),
            max_sanity=data.get("max_sanity", 100),
            corruption=data.get("corruption", 0),
            current_chapter=Chapter(data.get("current_chapter", "prologue")),
            emotional_state=EmotionalState(data.get("emotional_state", "contemplative")),
            current_room=data.get("current_room", ""),
            hp=data.get("hp", 100),
            max_hp=data.get("max_hp", 100),
            nerve=data.get("nerve", 50),
            max_nerve=data.get("max_nerve", 50),
            puzzles_attempted=data.get("puzzles_attempted", 0),
            puzzles_solved=data.get("puzzles_solved", 0),
            hints_used=data.get("hints_used", 0),
            total_playtime=data.get("total_playtime", 0.0),
            shards_collected=data.get("shards_collected", 0),
        )
        ps.discovered_imagery = set(data.get("discovered_imagery", []))
        ps.solved_puzzles = data.get("solved_puzzles", [])
        ps.made_choices = data.get("made_choices", {})
        ps.collected_fragments = data.get("collected_fragments", [])
        ps.read_entries = set(data.get("read_entries", []))
        ps.inventory_items = data.get("inventory_items", [])
        ps.visited_rooms = set(data.get("visited_rooms", []))
        ps.triggered_narratives = set(data.get("triggered_narratives", []))
        ps.flags = data.get("flags", {})
        return ps


# ============================================================
# Imagery Network (optional, for story-driven games)
# ============================================================

@dataclass
class ImageryNode:
    id: str
    name: str
    description: str
    discovered: bool = False
    resonance_level: float = 0.0
    connections: dict[str, float] = field(default_factory=dict)
    associated_emotions: list = field(default_factory=list)
    story_fragments: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)

    def connect_to(self, other_id: str, strength: float = 0.5) -> None:
        current = self.connections.get(other_id, 0.0)
        self.connections[other_id] = min(1.0, current + strength)

    def resonate(self, amount: float = 0.1) -> None:
        self.resonance_level = min(1.0, self.resonance_level + amount)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "description": self.description, "discovered": self.discovered,
            "resonance_level": self.resonance_level,
            "connections": self.connections,
            "associated_emotions": [e.value if hasattr(e, 'value') else e for e in self.associated_emotions],
            "story_fragments": self.story_fragments, "symbols": self.symbols,
        }


@dataclass
class ImageryNetwork:
    nodes: dict[str, ImageryNode] = field(default_factory=dict)
    active_resonances: set[tuple[str, str]] = field(default_factory=set)

    def add_node(self, node: ImageryNode) -> None:
        self.nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[ImageryNode]:
        return self.nodes.get(node_id)

    def discover(self, node_id: str) -> bool:
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
        a, b = self.nodes.get(node_a), self.nodes.get(node_b)
        if not a or not b:
            return 0.0
        direct = a.connections.get(node_b, 0.0)
        reverse = b.connections.get(node_a, 0.0)
        return (direct + reverse) / 2

    @property
    def discovery_count(self) -> int:
        return sum(1 for n in self.nodes.values() if n.discovered)

    @property
    def total_nodes(self) -> int:
        return len(self.nodes)

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "active_resonances": [list(r) for r in self.active_resonances],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImageryNetwork":
        net = cls()
        for nid, nd in data.get("nodes", {}).items():
            node = ImageryNode(
                id=nd["id"], name=nd["name"],
                description=nd["description"],
                discovered=nd.get("discovered", False),
                resonance_level=nd.get("resonance_level", 0.0),
                connections=nd.get("connections", {}),
                associated_emotions=nd.get("associated_emotions", []),
                story_fragments=nd.get("story_fragments", []),
                symbols=nd.get("symbols", []),
            )
            net.nodes[nid] = node
        net.active_resonances = {tuple(r) for r in data.get("active_resonances", [])}
        return net


# ============================================================
# Global Game State
# ============================================================

@dataclass
class GameState:
    """
    全局游戏状态。

    整合 PlayerState（玩家属性）+ ImageryNetwork（意象网络，可选）
    + 通用 flags / variables / history。
    """
    player: PlayerState = field(default_factory=PlayerState)
    imagery_network: ImageryNetwork = field(default_factory=ImageryNetwork)
    current_branch: BranchPath = BranchPath.MAIN
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    _last_tick: float = 0.0  # internal

    def set_flag(self, flag: str, value: Any = True) -> None:
        self.player.flags[flag] = value

    def get_flag(self, flag: str, default: Any = False) -> Any:
        return self.player.flags.get(flag, default)

    def set_var(self, key: str, value: Any) -> None:
        self.variables[key] = value

    def get_var(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def record_event(self, event_type: str, detail: str) -> None:
        now = time.time()
        self.history.append({
            "time": now, "type": event_type,
            "detail": detail,
            "chapter": self.player.current_chapter.value,
        })

    def advance(self) -> None:
        now = time.time()
        self.player.total_playtime += now - (self._last_tick or now)
        self._last_tick = now

    def to_dict(self) -> dict:
        return {
            "player": self.player.to_dict(),
            "imagery_network": self.imagery_network.to_dict(),
            "current_branch": self.current_branch.value,
            "variables": self.variables,
            "history": self.history[-50:],
            "_content_index": self.variables.get("_content_index", 0),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        # _content_index 从存档恢复，暂存到 variables 里
        # base_engine 会在 start_game() 里读取并赋值给 self._content_index
        saved_index = data.get("_content_index", 0)
        variables = data.get("variables", {})
        variables["_content_index"] = saved_index

        state = cls(
            player=PlayerState.from_dict(data.get("player", {})),
            imagery_network=ImageryNetwork.from_dict(
                data.get("imagery_network", {"nodes": {}, "active_resonances": []})
            ),
            current_branch=BranchPath(data.get("current_branch", "main")),
            variables=variables,
            history=data.get("history", []),
        )
        return state
