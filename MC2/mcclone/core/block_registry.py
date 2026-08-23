"""
block_registry — 方块定义与注册表（无硬依赖）。

提供：
  - BlockDef:     方块数据类（继承 Serializable）
  - BlockRegistry: 方块 id → BlockDef 的注册表

方块 id 约定（与 data/blocks.default.json 一致）：
  0=air(空气)  1=stone(石头) 2=dirt(泥土)
  3=grass(草)  4=water(水)   5=sand(沙)

本模块只依赖纯净版 alloy 的通用能力：
  - alloy.core.serializable.Serializable
  - alloy.utils.json_loader.JSONLoader
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from mcclone._engine import JSONLoader, Serializable
from mcclone.paths import DATA_DIR


# 内置方块 id 常量（供引擎与游戏共享语义）
AIR: int = 0
STONE: int = 1
DIRT: int = 2
GRASS: int = 3
WATER: int = 4
SAND: int = 5


@dataclass
class BlockDef(Serializable):
    """方块定义数据类。

    继承 Serializable，自动获得 to_dict()/from_dict()（基于 dataclass 字段）。
    props 为任意可 JSON 序列化的附加属性字典。
    """

    id: int = 0
    name: str = "air"
    glyph: str = " "
    color: str = "white"
    solid: bool = True
    transparent: bool = False
    props: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 保证 props 始终是独立 dict（避免默认可变对象被共享/被 None 污染）
        if self.props is None:
            self.props = {}


class BlockRegistry:
    """方块注册表：管理 id → BlockDef 的映射。"""

    def __init__(self) -> None:
        self._blocks: Dict[int, BlockDef] = {}

    # ── 注册 ──

    def register(self, block: BlockDef) -> None:
        """注册一个方块定义（按 id 索引，重复 id 会被覆盖）。"""
        self._blocks[block.id] = block

    # ── 查询 ──

    def get(self, block_id: int) -> BlockDef:
        """按 id 获取方块定义，缺失抛 KeyError。"""
        return self._blocks[block_id]

    def get_by_name(self, name: str) -> BlockDef:
        """按名称（精确匹配）获取方块定义，缺失抛 KeyError。"""
        for blk in self._blocks.values():
            if blk.name == name:
                return blk
        raise KeyError(f"未找到名为 {name!r} 的方块")

    def __contains__(self, block_id: int) -> bool:
        """支持 `block_id in registry` 语法。"""
        return block_id in self._blocks

    def ids(self) -> List[int]:
        """返回所有已注册方块 id 列表（升序）。"""
        return sorted(self._blocks.keys())

    # ── 默认方块 ──

    def load_defaults(self) -> None:
        """加载内置 6 个默认方块（air/stone/dirt/grass/water/sand）。"""
        defaults = [
            BlockDef(AIR, "air", " ", "white", solid=False, transparent=True),
            BlockDef(STONE, "stone", "#", "gray", solid=True, transparent=False),
            BlockDef(DIRT, "dirt", ".", "brown", solid=True, transparent=False),
            BlockDef(GRASS, "grass", '"', "green", solid=True, transparent=False),
            BlockDef(WATER, "water", "~", "blue", solid=False, transparent=True),
            BlockDef(SAND, "sand", ":", "yellow", solid=True, transparent=False),
        ]
        for blk in defaults:
            self.register(blk)

    # ── JSON 加载 ──

    @classmethod
    def from_json(cls, path: str | None = None) -> "BlockRegistry":
        """从 JSON 文件加载方块（先加载默认，再用 JSON 条目叠加/覆盖）。

        参数：
            path: JSON 文件路径；为 None 时读取本文件同级 data/blocks.default.json。

        返回：
            填充后的 BlockRegistry
        """
        if path is None:
            path = os.path.join(DATA_DIR, "blocks.default.json")
        loader = JSONLoader()
        data = loader.load_mandatory(path)
        reg = cls()
        reg.load_defaults()  # 先加载默认，便于 JSON 扩展或覆盖默认
        for entry in data:
            reg.register(BlockDef.from_dict(entry))
        return reg
