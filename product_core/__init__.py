# -*- coding: utf-8 -*-
"""product_core — MCclone 统一产品内核。

把 MC1（文字模式）与 MC2（2D 模式）串成「同一个游戏」的两种玩法层：
两者运行在 *同一引擎主干* 之上 ——

  * 事件总线 (EventBus)        两个玩法层触发的事件在共享总线上彼此可见；
  * 音频系统 (AudioSystem)     两个玩法层共用同一音频引擎（无设备时自动降级）；
  * 存档管理器 (SaveLoadManager) 两个玩法层共用同一套多槽位存档；
  * 物品注册表 (ItemRegistry)   两个玩法层的资源定义登记到同一注册表；
  * 共享档案 (profile)          跨玩法层持久化的角色/进度，可在切换模式时贯通。

这是「整合」的核心：不再是两套各自运行的程序，而是一个共享引擎主干、
可切换表现层的统一产品。MC1 / MC2 在启动时把各自的 bus / audio / save_mgr /
registry 接到本内核的同一实例上，事件、音频、存档与资源便在两种玩法层间贯通。

注：本模块仅依赖 alloy，不反向依赖 MC1 / MC2，避免循环导入；
MC1 / MC2 的资源登记通过惰性方法（register_mc1_items / register_mc2_blocks）完成。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from alloy.core.event_bus import EventBus as _EngineEventBus
from alloy.audio.audio_system import AudioSystem
from alloy.systems.save_load import SaveLoadManager
from alloy.systems.stackable_inventory import ItemRegistry, StackableInventory

# ── 共享存档槽位划分（同一 SaveLoadManager / 同一存档目录）──
SLOT_PROFILE = 9     # 跨玩法层的共享角色/进度档案
SLOT_MC1 = 0         # MC1 文字模式游戏存档
SLOT_MC2 = 1         # MC2 2D 模式游戏存档
PROFILE_VERSION = 1


class ProductCore:
    """MCclone 统一产品内核。

    一个实例 = 一个游戏的引擎主干；MC1 与 MC2 作为同一实例上的不同玩法层挂载。
    """

    def __init__(self, save_dir: Optional[str] = None) -> None:
        # 单一引擎事件总线：MC1 / MC2 的所有事件都流经它
        self.bus = _EngineEventBus()
        # 单一引擎音频系统：MC1 / MC2 共用，无设备时自动静音降级
        self.audio = AudioSystem()
        # 单一引擎存档管理器：MC1 / MC2 的多槽位存档都在这里
        self.save_mgr = SaveLoadManager(
            save_dir or self._default_save_dir(), version=PROFILE_VERSION
        )
        # 单一引擎物品注册表：MC1 物品 + MC2 方块都登记到这里
        self.registry = ItemRegistry()
        # 跨玩法层共享档案（角色/进度），切换模式时贯通
        self.profile: dict[str, Any] = {}
        # 已挂载的玩法层：名称 -> 说明
        self.games: dict[str, str] = {}

    # ── 路径 ──
    @staticmethod
    def _default_save_dir() -> str:
        return str(Path(__file__).resolve().parent.parent / "saves")

    # ── 玩法层挂载 ──
    def mount(self, layer_name: str, description: str = "") -> None:
        """登记一个玩法层（如 "MC1-文字" / "MC2-2D"）。"""
        self.games[layer_name] = description

    # ── 共享资源注册（惰性，避免循环导入）──
    def register_mc1_items(self) -> int:
        """把 MC1 物品登记进共享 ItemRegistry（字符串 id）。"""
        try:
            from game_data import ITEMS
        except Exception:
            return self.registry.count
        self.registry.register_batch({k: dict(v) for k, v in ITEMS.items()})
        return self.registry.count

    def register_mc2_blocks(self) -> int:
        """把 MC2 方块登记进共享 ItemRegistry（id 形如 "mc2_block_<n>"）。"""
        try:
            from mcclone.core.block_registry import BlockRegistry
        except Exception:
            return self.registry.count
        reg = BlockRegistry()
        reg.load_defaults()
        for bid in reg.ids():
            info = reg.get(bid)
            name = getattr(info, "name", None) or f"方块{bid}"
            self.registry.register(
                f"mc2_block_{bid}",
                name=name,
                icon="🧱",
                type="block",
                block_id=bid,
            )
        return self.registry.count

    def merged_registry_count(self) -> int:
        """共享注册表当前物品总数（用于断言跨游戏资源打通）。"""
        return self.registry.count

    # ── 跨玩法层共享档案（角色/进度打通）──
    def set_profile(self, key: str, value: Any) -> None:
        self.profile[key] = value

    def get_profile(self, key: str, default: Any = None) -> Any:
        return self.profile.get(key, default)

    def persist_profile(self) -> bool:
        """把共享档案写入共享存档（槽位 SLOT_PROFILE）。"""
        return self.save_mgr.save(self.profile, slot=SLOT_PROFILE)

    def load_profile(self) -> dict[str, Any]:
        """从共享存档读回共享档案（槽位 SLOT_PROFILE）。"""
        data = self.save_mgr.load(slot=SLOT_PROFILE)
        if isinstance(data, dict):
            self.profile = data
        return self.profile

    # ── 快照（供探针/调试）──
    def snapshot(self) -> dict:
        return {
            "event_bus": self.bus is not None,
            "audio_available": getattr(self.audio, "is_available", False),
            "save_manager": self.save_mgr is not None,
            "registry_count": self.registry.count,
            "mounted_layers": list(self.games.keys()),
            "profile_keys": list(self.profile.keys()),
        }


__all__ = ["ProductCore", "SLOT_PROFILE", "SLOT_MC1", "SLOT_MC2", "PROFILE_VERSION"]
