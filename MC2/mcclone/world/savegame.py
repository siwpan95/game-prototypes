# -*- coding: utf-8 -*-
"""savegame — M5 存档 / 读档（序列化完整游戏状态到 JSON 并可还原）。

设计要点（M5-R1 / M5-R2 / T-M5-*）：
  - 「地基零改动」：本模块不修改 player.py / systems/survival.py /
    daynight.py / inventory.py / block_world.py / creatures/* 等任何源文件。
    所有状态仅通过 PUBLIC 构造器 + 运行时属性赋值（p.hp = ...、
    inventory.add(...) 或必要时直接写 player.inventory._items、
    survival.set_spawn(...) 等）在运行时重建。
  - SaveGame 继承 alloy.core.serializable.Serializable（dataclass），
    字段以原生 dict/list 容器承载各子系统快照，to_dict()/from_dict()
    自动基于 dataclass 字段完成；本模块在存/读时负责把 dict 快照与真实
    对象互相转换。
  - 存档不重新生成世界：直接保存 world.to_dict() 的完整网格（含所有 z 层），
    读档用 BlockWorld.from_dict 还原，保证字节一致。

零 pygame 依赖，可在 headless 下断言。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcclone._engine import Serializable

from mcclone.core.block_world import BlockWorld
from mcclone.core.block_registry import BlockRegistry
from mcclone.core.daynight import DayNight
from mcclone.player.player import Player
from mcclone.systems.survival import SurvivalConfig, SurvivalSystem
from mcclone.creatures.entity import AIState, CreatureConfig, CreatureKind
from mcclone.creatures.system import CreatureSystem


# ─────────────────────────────────────────────────────────────────────────
# SaveGame：存档数据容器（Serializable dataclass）
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class SaveGame(Serializable):
    """存档数据容器。

    字段均为可直接 JSON 序列化的原生容器（dict / list / 标量）。
    world/daynight/player/survival/creatures 为各子系统快照；
    version 用于未来格式迁移；seed 记录世界种子；saved_at 为存档时间戳。
    """

    version: int = 1
    seed: int = 0
    saved_at: str = ""
    world: Dict[str, Any] = field(default_factory=dict)
    daynight: Dict[str, Any] = field(default_factory=dict)
    player: Dict[str, Any] = field(default_factory=dict)
    survival: Dict[str, Any] = field(default_factory=dict)
    creatures: List[Dict[str, Any]] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────
# 生物快照辅助（CreatureSystem 暂走此路径，属性均为公开）
# ─────────────────────────────────────────────────────────────────────────

def _creatures_to_dict(cs: CreatureSystem) -> List[Dict[str, Any]]:
    """把生物系统列表转为可序列化 dict 列表（Enum 存 .name，还原用 Xxx[name]）。"""
    out: List[Dict[str, Any]] = []
    for c in cs.creatures:
        out.append({
            "kind": c.kind.name,           # 如 "COW"
            "x": c.fx,
            "y": c.fy,
            "hp": c.hp,
            "max_hp": c.max_hp,
            "state": c.state.name,         # 如 "IDLE"
        })
    return out


def _creatures_from_dict(d_list: List[Dict[str, Any]], world,
                         registry, event_bus, seed: int) -> CreatureSystem:
    """由快照 dict 列表重建 CreatureSystem 与生物（Enum 用 Xxx[name] 还原）。"""
    cs = CreatureSystem(world, registry, event_bus, CreatureConfig(), seed=seed)
    for c in d_list:
        kind_name = c.get("kind", "COW")
        try:
            kind = CreatureKind[kind_name]
        except KeyError:
            kind = CreatureKind.COW
        cr = cs.spawn(kind, float(c.get("x", 0.0)), float(c.get("y", 0.0)))
        cr.max_hp = float(c.get("max_hp", cr.max_hp))
        cr.hp = float(c.get("hp", cr.max_hp))
        state_name = c.get("state", "IDLE")
        try:
            cr.state = AIState[state_name]
        except KeyError:
            cr.state = AIState.IDLE
    return cs


# ─────────────────────────────────────────────────────────────────────────
# 公开 API
# ─────────────────────────────────────────────────────────────────────────

def _default_timestamp() -> str:
    """headless 下允许固定值；默认用 UTC ISO 时间戳（时区感知）。"""
    return datetime.now(timezone.utc).isoformat()


def build_savegame(*, world, player, survival, daynight, creatures,
                   seed: int, registry: BlockRegistry,
                   saved_at: str | None = None) -> SaveGame:
    """构造 SaveGame 数据容器（引擎 Serializable，自带 to_dict/from_dict）。

    整合：SaveGame 是 alloy.core.serializable.Serializable 的子类，
    可直接交给 alloy.systems.save_load.SaveLoadManager 多槽位持久化。
    """
    return SaveGame(
        version=1,
        seed=int(seed),
        saved_at=saved_at if saved_at is not None else _default_timestamp(),
        world=world.to_dict(),
        daynight=daynight.to_dict(),
        player=player.to_snapshot(),
        survival=survival.to_snapshot(),
        creatures=_creatures_to_dict(creatures),
    )


def save_game(path: str, *, world, player, survival, daynight, creatures,
              seed: int, registry: BlockRegistry,
              saved_at: str | None = None) -> None:
    """把完整游戏状态序列化到 JSON 文件（缩进 2，UTF-8）。

    参数：
        path: 目标 JSON 路径。
        world/player/survival/daynight/creatures: 当前运行期游戏对象。
        seed: 世界种子（用于读档时重建确定性生物系统）。
        registry: 方块注册表（仅用于写入存档的元信息，不修改）。
        saved_at: 可选时间戳；为 None 时用当前 UTC 时间。

    文件缺失的父目录会被自动创建。损坏/缺字段的快照在 load 时容错。
    """
    sg = build_savegame(world=world, player=player, survival=survival,
                        daynight=daynight, creatures=creatures,
                        seed=seed, registry=registry, saved_at=saved_at)
    data = sg.to_dict()
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _build_state(data: Dict[str, Any], registry: BlockRegistry,
                 event_bus=None, src_path: str | None = None) -> Dict[str, Any]:
    """由 SaveGame 字典还原完整运行期状态（供文件读档与引擎存档管理器共用）。

    参数：
        data: SaveGame.to_dict() 产出的字典（含 world/player/survival/...）。
        registry: 用于重建 Player/CreatureSystem 的方块注册表。
        event_bus: 可选事件总线（传给 CreatureSystem）。
        src_path: 可选来源路径（写入 meta，仅文件读档用）。

    返回：
        dict: {"world", "player", "survival", "daynight", "creatures",
               "seed", "meta"}
    """
    # 世界（含所有 z 层，字节一致）
    world = BlockWorld.from_dict(data.get("world", {}))
    # 昼夜
    daynight = DayNight.from_dict(data.get("daynight", {}))
    # 玩家
    player = Player.from_snapshot(data.get("player", {}), registry)
    # 生存系统（写 player 的 hp/hunger/出生点）
    survival = SurvivalSystem.from_snapshot(data.get("survival", {}), player)
    # 种子
    seed = int(data.get("seed", 0))
    # 生物系统
    creatures = _creatures_from_dict(data.get("creatures", []),
                                     world, registry, event_bus, seed)

    meta = {
        "version": int(data.get("version", 1)),
        "seed": seed,
        "saved_at": data.get("saved_at", ""),
        "path": os.path.abspath(src_path) if src_path else "",
    }
    return {
        "world": world,
        "player": player,
        "survival": survival,
        "daynight": daynight,
        "creatures": creatures,
        "seed": seed,
        "meta": meta,
    }


def load_game(path: str, registry: BlockRegistry,
              event_bus=None) -> Dict[str, Any]:
    """从 JSON 文件还原完整游戏状态。

    参数：
        path: 存档 JSON 路径。
        registry: 用于重建 Player/CreatureSystem 的方块注册表。
        event_bus: 可选事件总线（传给 CreatureSystem）。

    返回：
        dict: {
            "world": BlockWorld,
            "player": Player,
            "survival": SurvivalSystem,
            "daynight": DayNight,
            "creatures": CreatureSystem,
            "seed": int,
            "meta": dict(version/saved_at/path),
        }

    容错行为：
        - 文件不存在 -> 抛 FileNotFoundError。
        - JSON 损坏/解析失败 -> 抛 ValueError。
        - 各快照缺可选字段 -> 用子系统默认值兜底（不抛异常）。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"存档文件不存在: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"存档解析失败: {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"存档根节点不是对象: {path}")

    return _build_state(data, registry, event_bus, src_path=path)


def load_game_from_state(state_data: Dict[str, Any], registry: BlockRegistry,
                         event_bus=None) -> Dict[str, Any]:
    """由引擎 SaveLoadManager 读出的 state_data 字典还原完整游戏状态。

    整合：与 load_game 共用 _build_state，使文件读档与「引擎多槽位存档管理器」
    走同一套还原逻辑。state_data 即 SaveGame.to_dict() 的结果。
    """
    if not isinstance(state_data, dict):
        raise ValueError("存档状态不是对象")
    return _build_state(state_data, registry, event_bus)
