# -*- coding: utf-8 -*-
"""crafting — 配方表 + 合成逻辑（M2 生存基底，数据驱动）。

提供：
  - Recipe: 配方结构（id/name/inputs/output，键为 block_id(int)）。
  - Crafting: 配方表管理；can_craft(recipe_id, inv) 判断库存是否充足；
    craft(recipe_id, inv) 先校验再 remove 输入 / add 输出（受 STACK_MAX 限制），
    成功返回 True；from_json(registry, path) 从 JSON 加载配方。

配方文件结构（架构 §7.5）：JSON 数组，每项
  {"id": "...", "name": "...", "inputs": {"<block_id>": n}, "output": {"<block_id>": n}}
键为字符串 block_id，运行时 int() 转为 int。

依赖：仅 json + block_registry（校验 id 是否合法，可选）+ inventory。
headless 可断言。
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

from mcclone.player.inventory import Inventory


class Recipe:
    """合成配方：确定性、数据驱动。"""

    def __init__(self, rid: str, name: str,
                 inputs: Dict[int, int], output: Dict[int, int]) -> None:
        """构造。

        参数：
            rid: 配方唯一 id（与 JSON 的 id 对应）。
            name: 显示名（中文）。
            inputs: {block_id: 需要数量}。
            output: {block_id: 产出数量}。
        """
        self.id: str = rid
        self.name: str = name
        self.inputs: Dict[int, int] = inputs
        self.output: Dict[int, int] = output

    def __repr__(self) -> str:
        return (f"Recipe(id={self.id!r}, name={self.name!r}, "
                f"inputs={self.inputs}, output={self.output})")


class Crafting:
    """合成管理器：持有配方表并对 Inventory 执行合成。"""

    def __init__(self, registry, recipes: List[Recipe]) -> None:
        """构造。

        参数：
            registry: 方块注册表（仅用于校验 id 合法性，可传 None 跳过校验）。
            recipes: Recipe 列表。
        """
        self.registry = registry
        self._recipes: Dict[str, Recipe] = {r.id: r for r in recipes}

    # ── 枚举 / 查询 ──
    @property
    def recipes(self) -> List[Recipe]:
        """返回全部配方（按注册顺序）。"""
        return list(self._recipes.values())

    def get(self, recipe_id: str) -> Recipe | None:
        """按 id 取配方；不存在返回 None。"""
        return self._recipes.get(recipe_id)

    # ── 合成判定 / 执行 ──
    def can_craft(self, recipe_id: str, inv: Inventory) -> bool:
        """库存是否足以合成该配方。"""
        r = self._recipes.get(recipe_id)
        if r is None:
            return False
        for bid, need in r.inputs.items():
            if inv.count(bid) < need:
                return False
        return True

    def craft(self, recipe_id: str, inv: Inventory) -> bool:
        """执行合成：成功返回 True（先 can_craft 校验，再扣输入、加输出）。

        输出受 STACK_MAX 限制（Inventory.add 自动截断 / 跨栈 / 空槽复用）。
        """
        if not self.can_craft(recipe_id, inv):
            return False
        r = self._recipes[recipe_id]
        # 1) 扣除输入
        for bid, need in r.inputs.items():
            inv.remove(bid, need)
        # 2) 增加输出
        for bid, give in r.output.items():
            inv.add(bid, give)
        return True

    # ── JSON 加载 ──
    @classmethod
    def from_json(cls, registry, path: str) -> "Crafting":
        """从 JSON 文件加载配方表。

        参数：
            registry: 方块注册表（用于校验 id，可传 None 跳过）。
            path: recipes JSON 路径。
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        recipes: List[Recipe] = []
        for entry in data:
            rid = entry["id"]
            name = entry.get("name", rid)
            inputs = {int(k): int(v) for k, v in entry.get("inputs", {}).items()}
            output = {int(k): int(v) for k, v in entry.get("output", {}).items()}
            recipes.append(Recipe(rid, name, inputs, output))
        return cls(registry, recipes)
