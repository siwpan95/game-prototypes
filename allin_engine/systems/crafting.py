"""
通用配方合成系统 — 从《我的世界》实战沉淀

提供数据驱动的配方合成系统：
  - 材料检查 + 自动扣除
  - 合成站检查（工作台/熔炉/无）
  - 多产物支持
  - 与 StackableInventory 无缝集成

使用方式：

    from allin_engine.systems.crafting import CraftingSystem, Recipe

    # 定义配方
    recipes = {
        "wood_planks": Recipe(
            needs=[("wood_log", 1)], yields=4, station="无"
        ),
        "iron_pickaxe": Recipe(
            needs=[("iron_ingot", 3), ("stick", 2)],
            yields=1, station="工作台"
        ),
    }

    # 创建合成系统
    crafting = CraftingSystem(inventory, recipes)

    # 检查 + 合成
    ok, msg = crafting.try_craft("iron_pickaxe")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .stackable_inventory import StackableInventory


# ═══════════════════════════════════════════════════════════
#  Recipe — 配方定义
# ═══════════════════════════════════════════════════════════

@dataclass
class Recipe:
    """一个合成 / 熔炼配方。

    属性:
        needs: 所需材料 [(item_id, count), ...]
        yields: 产物数量
        station: 所需工作台（"无" / "工作台" / "熔炉"）
        station_varies: 是否是原地合成（如背包内合成）
        description: 配方描述
    """

    needs: list[tuple[str, int]]
    yields: int = 1
    station: str = "无"
    station_varies: bool = False
    description: str = ""

    @property
    def station_required(self) -> bool:
        """是否需要放置合成站。"""
        return self.station not in ("无", "")

    def to_dict(self) -> dict:
        return {
            "needs": [list(n) for n in self.needs],
            "yields": self.yields,
            "station": self.station,
            "station_varies": self.station_varies,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recipe":
        needs = [tuple(n) for n in data.get("needs", [])]
        return cls(
            needs=needs,
            yields=data.get("yields", 1),
            station=data.get("station", "无"),
            station_varies=data.get("station_varies", False),
            description=data.get("description", ""),
        )


# ═══════════════════════════════════════════════════════════
#  CraftingSystem — 合成系统引擎
# ═══════════════════════════════════════════════════════════

class CraftingSystem:
    """配方合成系统。

    管理配方注册、材料检查、产物生成。

    使用方式:

        sys = CraftingSystem(inventory, registry)
        sys.register("wood_planks", Recipe(needs=[("wood_log", 1)], yields=4))
        ok, msg = sys.try_craft("wood_planks")
    """

    def __init__(
        self,
        inventory: StackableInventory,
        station_checker: "Callable[[str], bool] | None" = None,
    ):
        """
        参数:
            inventory: 玩家背包（材料来源 + 产物目标）
            station_checker: 合成站检查函数 (station_name) -> bool
                             None 表示不检查合成站
        """
        self._inv = inventory
        self._recipes: dict[str, Recipe] = {}
        self._station_checker = station_checker

    def register(self, result_id: str, recipe: Recipe) -> None:
        """注册配方。"""
        self._recipes[result_id] = recipe

    def register_batch(self, recipes: dict[str, Recipe]) -> None:
        """批量注册配方。"""
        self._recipes.update(recipes)

    def get_recipe(self, result_id: str) -> Optional[Recipe]:
        """获取配方。"""
        return self._recipes.get(result_id)

    def can_craft(self, result_id: str) -> tuple[bool, str]:
        """检查能否合成指定物品。

        返回:
            (是否可合成, 失败原因)
        """
        if result_id not in self._recipes:
            return False, f"未知配方: {result_id}"

        recipe = self._recipes[result_id]

        # 检查合成站
        if recipe.station_required and self._station_checker:
            if not self._station_checker(recipe.station):
                return False, f"需要{recipe.station}！请先放置{recipe.station}。"

        # 检查材料
        for item_id, count in recipe.needs:
            if not self._inv.has_item(item_id, count):
                item_name = self._inv.registry.get(item_id).get("name", item_id)
                return False, f"材料不足: 需要 {item_name} ×{count}"

        return True, ""

    def try_craft(self, result_id: str) -> tuple[bool, str]:
        """尝试合成指定物品。自动消耗材料并生成产物。

        返回:
            (是否成功, 结果消息)

        用法:
            ok, msg = sys.try_craft("wood_planks")
        """
        ok, err = self.can_craft(result_id)
        if not ok:
            return False, err

        recipe = self._recipes[result_id]

        # 消耗材料
        for item_id, count in recipe.needs:
            self._inv.remove_item(item_id, count)

        # 生成产物
        self._inv.add_item(result_id, recipe.yields)

        item_name = self._inv.registry.get(result_id).get("name", result_id)
        station_tag = f"[{recipe.station}]" if recipe.station_required else ""
        return True, f"✅ {station_tag} 合成成功！获得 {item_name} ×{recipe.yields}"

    def list_available(self) -> list[str]:
        """列出当前可合成的所有物品 ID。"""
        available = []
        for result_id in self._recipes:
            ok, _ = self.can_craft(result_id)
            if ok:
                available.append(result_id)
        return available

    def format_recipe(self, result_id: str) -> str:
        """格式化单个配方的可读描述。"""
        recipe = self._recipes.get(result_id)
        if not recipe:
            return f"未知配方: {result_id}"

        reg = self._inv.registry
        result_name = reg.get(result_id).get("name", result_id)
        parts = [f"{reg.get(result_id).get('icon', '📦')} {result_name}"]

        materials = []
        for item_id, count in recipe.needs:
            mat_name = reg.get(item_id).get("name", item_id)
            mat_icon = reg.get(item_id).get("icon", "📦")
            materials.append(f"{mat_icon}{mat_name} ×{count}")

        parts.append(" ← " + " + ".join(materials))

        if recipe.station_required:
            parts.append(f"  [需要{recipe.station}]")

        return "".join(parts)

    @property
    def recipe_count(self) -> int:
        """已注册配方总数。"""
        return len(self._recipes)

    @property
    def recipes(self) -> dict[str, Recipe]:
        """返回所有配方（只读）。"""
        return dict(self._recipes)

    def to_dict(self) -> dict:
        """序列化所有配方。"""
        return {k: v.to_dict() for k, v in self._recipes.items()}

    def from_dict(self, data: dict) -> None:
        """从字典恢复配方。"""
        self._recipes.clear()
        for k, v in data.items():
            self._recipes[k] = Recipe.from_dict(v)
