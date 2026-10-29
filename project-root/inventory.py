# inventory.py
# 材料库存 —— 魔药晋升所需的非凡材料持有与配方匹配（E1）
from typing import Dict, List


class Inventory:
    """非凡者的材料库存。

    魔药配方（见 pathways_data.get_potion_formula）由主材料 + 若干辅助材料组成；
    Inventory 负责记录持有数量、判断是否满足某配方、并在酿造（晋升）时消耗之。
    纯数据结构，可被 GUIState 直接持有，也便于序列化做存档。
    """

    def __init__(self, materials: Dict[str, int] = None):
        # 材料名 -> 持有数量（>=0 整数）
        self.materials: Dict[str, int] = {k: int(v) for k, v in (materials or {}).items() if v > 0}

    def add(self, name: str, n: int = 1) -> int:
        """增加材料，返回增加后的数量"""
        self.materials[name] = self.materials.get(name, 0) + n
        return self.materials[name]

    def count(self, name: str) -> int:
        return self.materials.get(name, 0)

    def has(self, formula: dict) -> bool:
        """判断是否满足某配方（主材料与每份辅助材料各至少 1 个）"""
        if self.count(formula["main"]) < 1:
            return False
        for m in formula["supplementary"]:
            if self.count(m) < 1:
                return False
        return True

    def missing(self, formula: dict) -> List[str]:
        """返回配方中尚缺的材料名列表"""
        miss = []
        if self.count(formula["main"]) < 1:
            miss.append(formula["main"])
        for m in formula["supplementary"]:
            if self.count(m) < 1:
                miss.append(m)
        return miss

    def consume(self, formula: dict) -> bool:
        """消耗一份配方材料；不满足则返回 False 且不改动"""
        if not self.has(formula):
            return False
        self.materials[formula["main"]] -= 1
        for m in formula["supplementary"]:
            self.materials[m] -= 1
        # 清理数量为 0 的条目
        self.materials = {k: v for k, v in self.materials.items() if v > 0}
        return True

    def total(self) -> int:
        return sum(self.materials.values())

    def to_dict(self) -> dict:
        return {"materials": dict(self.materials)}

    @classmethod
    def from_dict(cls, d: dict) -> "Inventory":
        return cls(d.get("materials", {}) if d else {})

    def __repr__(self):
        if not self.materials:
            return "Inventory(空)"
        items = "、".join(f"{k}×{v}" for k, v in self.materials.items())
        return f"Inventory({items})"
