"""
可堆叠背包 + 装备槽系统 — 从《我的世界》实战沉淀

提供比 Inventory 更灵活的背包系统：
  - 物品堆叠计数（自动合并）
  - 装备槽位（武器/工具/头盔/胸甲/护腿/靴子）
  - 物品数据注册表（ItemRegistry）
  - 快速查询（count_item / has_item）

与 engine 现有 Inventory 的区别：
  - Inventory: 固定容量，每格一件，适合文字冒险RPG
  - StackableInventory: 无容量上限，物品堆叠，适合沙盒/生存类游戏

使用方式：

    from alloy.systems.stackable_inventory import (
        StackableInventory, EquipmentSlots, ItemRegistry
    )

    # 注册物品数据
    registry = ItemRegistry()
    registry.register("wood_log", name="原木", icon="🪵", type="resource")

    # 创建带装备槽的背包
    inv = StackableInventory(registry)
    inv.add_item("wood_log", 10)
    inv.equip_weapon("wooden_sword")

    if inv.has_item("wood_log", 5):
        inv.remove_item("wood_log", 3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
#  ItemRegistry — 物品数据注册表
# ═══════════════════════════════════════════════════════════

class ItemRegistry:
    """物品数据注册表 — 管理所有物品的元数据。

    每个物品通过 register() 注册，通过 get() 查询。
    物品数据可以包含任意字段（name, icon, type, damage, tier, stack 等）。

    使用方式:

        registry = ItemRegistry()
        registry.register("wood", name="木材", icon="🪵", type="resource", stack=64)
        registry.register("sword", name="铁剑", icon="🗡️", type="weapon", damage=10)
        info = registry.get("sword")
    """

    def __init__(self):
        self._items: dict[str, dict[str, Any]] = {}

    def register(self, item_id: str, **kwargs) -> None:
        """注册一个物品。

        参数:
            item_id: 唯一标识符
            **kwargs: 物品属性（name, icon, type, damage, tier, stack, ...）
        """
        self._items[item_id] = {"id": item_id, **kwargs}

    def register_batch(self, items: dict[str, dict[str, Any]]) -> None:
        """批量注册物品。

        参数:
            items: {item_id: {属性...}, ...}
        """
        for item_id, data in items.items():
            self._items[item_id] = {"id": item_id, **data}

    def get(self, item_id: str) -> dict[str, Any]:
        """获取物品元数据。不存在返回空字典。"""
        return self._items.get(item_id, {})

    def has(self, item_id: str) -> bool:
        """检查物品是否已注册。"""
        return item_id in self._items

    def list_by_type(self, item_type: str) -> list[str]:
        """列出指定类型的所有物品 ID。"""
        return [k for k, v in self._items.items() if v.get("type") == item_type]

    @property
    def all_items(self) -> dict[str, dict[str, Any]]:
        """返回所有物品数据（只读）。"""
        return dict(self._items)

    @property
    def count(self) -> int:
        """已注册物品总数。"""
        return len(self._items)


# ═══════════════════════════════════════════════════════════
#  EquipmentSlots — 装备槽管理
# ═══════════════════════════════════════════════════════════

class EquipmentSlots:
    """装备槽管理器 — 管理角色的武器/工具/防具。

    默认槽位: weapon, tool, helmet, chestplate, leggings, boots
    每类装备互斥：装备新武器会自动卸下旧武器放回背包。

    使用方式:

        slots = EquipmentSlots(inventory, registry)
        slots.equip("wooden_sword")          # 装备武器
        slots.equip("iron_pickaxe", "tool")  # 装备工具
        damage = slots.get_weapon_damage()   # 获取当前武器伤害
        tier = slots.get_tool_tier()         # 获取当前工具等级
    """

    DEFAULT_SLOTS = ["weapon", "tool", "helmet", "chestplate", "leggings", "boots"]

    def __init__(self, inventory: "StackableInventory", registry: ItemRegistry):
        """
        参数:
            inventory: 关联的背包实例
            registry: 物品数据注册表
        """
        self._inv = inventory
        self._reg = registry
        self._slots: dict[str, str | None] = {s: None for s in self.DEFAULT_SLOTS}

    def equip(self, item_id: str, slot: str | None = None) -> bool:
        """装备物品。自动推断槽位或指定。

        参数:
            item_id: 物品 ID
            slot: 强制指定槽位（None=自动推断）
        返回:
            是否成功
        """
        info = self._reg.get(item_id)
        if not info:
            return False

        # 自动推断槽位
        if slot is None:
            slot = self._infer_slot(info)

        if slot not in self._slots:
            return False

        # 卸下旧装备
        old = self._slots[slot]
        if old:
            self._inv.add_item(old, 1)

        # 从背包扣除并装备
        if not self._inv.remove_item(item_id, 1):
            return False

        self._slots[slot] = item_id
        return True

    def unequip(self, slot: str) -> bool:
        """卸下指定槽位的装备。"""
        if slot not in self._slots:
            return False
        item_id = self._slots[slot]
        if item_id:
            self._inv.add_item(item_id, 1)
            self._slots[slot] = None
            return True
        return False

    def get(self, slot: str) -> str | None:
        """获取指定槽位的装备 ID。"""
        return self._slots.get(slot)

    def get_info(self, slot: str) -> dict[str, Any]:
        """获取指定槽位装备的完整信息。"""
        item_id = self._slots.get(slot)
        if item_id:
            return self._reg.get(item_id)
        return {}

    @property
    def weapon(self) -> str | None:
        return self._slots.get("weapon")

    @property
    def tool(self) -> str | None:
        return self._slots.get("tool")

    def get_weapon_damage(self) -> int:
        """获取当前武器伤害值（徒手=2）。"""
        item_id = self.weapon
        if item_id:
            return self._reg.get(item_id).get("damage", 2)
        return 2

    def get_tool_tier(self) -> int:
        """获取当前工具等级（0=徒手）。"""
        item_id = self.tool
        if item_id:
            return self._reg.get(item_id).get("tier", 0)
        return 0

    def get_total_defense(self) -> int:
        """计算所有防具的总防御值。"""
        total = 0
        for slot in ("helmet", "chestplate", "leggings", "boots"):
            item_id = self._slots.get(slot)
            if item_id:
                total += self._reg.get(item_id).get("defense", 0)
        return total

    def _infer_slot(self, info: dict) -> str | None:
        """根据物品类型推断装备槽位。"""
        item_type = info.get("type", "")
        item_id = info.get("id", "")

        if item_type == "weapon":
            return "weapon"
        elif item_type == "tool":
            return "tool"
        elif item_type == "armor":
            for slot in ("helmet", "chestplate", "leggings", "boots"):
                if slot in item_id:
                    return slot
            return "chestplate"  # 默认
        return None

    def to_dict(self) -> dict:
        """序列化装备状态。"""
        return {s: v for s, v in self._slots.items() if v is not None}

    def from_dict(self, data: dict) -> None:
        """从字典恢复装备状态。"""
        for slot in self.DEFAULT_SLOTS:
            self._slots[slot] = data.get(slot)


# ═══════════════════════════════════════════════════════════
#  StackableInventory — 可堆叠背包
# ═══════════════════════════════════════════════════════════

class StackableInventory:
    """可堆叠背包 — 支持物品堆叠计数。

    特性:
      - 无固定容量上限
      - 同 ID 物品自动合并
      - 支持堆叠上限（由 ItemRegistry 的 stack 字段控制）
      - 装备槽集成

    使用方式:

        reg = ItemRegistry()
        reg.register("wood", name="木材", stack=64)
        inv = StackableInventory(reg)
        inv.add_item("wood", 30)
        inv.add_item("wood", 40)  # 自动合并，超出 stack 上限自动新开格
        count = inv.count_item("wood")  # 70
    """

    def __init__(self, registry: ItemRegistry):
        """
        参数:
            registry: 物品数据注册表
        """
        self._registry = registry
        self._slots: list[dict] = []  # [{id: str, count: int}, ...]
        self.equipment = EquipmentSlots(self, registry)

    # ── 添加 / 移除 ──

    def add_item(self, item_id: str, count: int = 1) -> int:
        """添加物品到背包。自动合并到已有堆叠。

        参数:
            item_id: 物品 ID
            count: 数量

        返回:
            实际添加的数量（受堆叠上限影响）
        """
        if count <= 0 or not self._registry.has(item_id):
            return 0

        info = self._registry.get(item_id)
        max_stack = info.get("stack", 999)

        remaining = count
        added = 0

        # 先尝试合并到已有堆叠
        for slot in self._slots:
            if slot["id"] == item_id and slot["count"] < max_stack:
                space = max_stack - slot["count"]
                take = min(remaining, space)
                slot["count"] += take
                remaining -= take
                added += take
                if remaining <= 0:
                    break

        # 如果还有剩余，创建新堆叠
        while remaining > 0:
            take = min(remaining, max_stack)
            self._slots.append({"id": item_id, "count": take})
            remaining -= take
            added += take

        return added

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """从背包移除物品。

        参数:
            item_id: 物品 ID
            count: 数量

        返回:
            是否成功移除（数量不足返回 False）
        """
        if self.count_item(item_id) < count:
            return False

        remaining = count
        # 从后往前移除（优先清空末尾的堆叠）
        for i in range(len(self._slots) - 1, -1, -1):
            slot = self._slots[i]
            if slot["id"] == item_id:
                take = min(remaining, slot["count"])
                slot["count"] -= take
                remaining -= take
                if slot["count"] <= 0:
                    self._slots.pop(i)
                if remaining <= 0:
                    break

        return True

    # ── 查询 ──

    def count_item(self, item_id: str) -> int:
        """统计背包中某物品的总数量。"""
        return sum(s["count"] for s in self._slots if s["id"] == item_id)

    def has_item(self, item_id: str, count: int = 1) -> bool:
        """检查背包中是否有至少 count 个某物品。"""
        return self.count_item(item_id) >= count

    def list_items(self) -> list[dict]:
        """列出所有物品（{id, count} 列表）。"""
        return [dict(s) for s in self._slots]

    def list_by_type(self, item_type: str) -> list[dict]:
        """列出指定类型的物品。"""
        return [
            s for s in self._slots
            if self._registry.get(s["id"]).get("type") == item_type
        ]

    def clear(self) -> None:
        """清空背包。"""
        self._slots.clear()

    # ── 属性 ──

    @property
    def total_slots(self) -> int:
        """总堆叠数（非物品总数）。"""
        return len(self._slots)

    @property
    def total_items(self) -> int:
        """物品总数（所有堆叠的 count 之和）。"""
        return sum(s["count"] for s in self._slots)

    @property
    def is_empty(self) -> bool:
        """背包是否为空。"""
        return len(self._slots) == 0

    @property
    def registry(self) -> ItemRegistry:
        """关联的物品注册表。"""
        return self._registry

    # ── 序列化 ──

    def to_dict(self) -> dict:
        """序列化背包状态。"""
        return {
            "items": [dict(s) for s in self._slots],
            "equipment": self.equipment.to_dict(),
        }

    def from_dict(self, data: dict) -> None:
        """从字典恢复背包状态。"""
        self._slots.clear()
        for slot_data in data.get("items", []):
            self._slots.append({"id": slot_data["id"], "count": slot_data["count"]})
        self.equipment.from_dict(data.get("equipment", {}))

    def __repr__(self) -> str:
        return f"StackableInventory({self.total_slots} slots, {self.total_items} items)"
