"""d20.equipment - 装备系统服务（原 EquipmentMixin 改写）

D&D 5e 风格的武器/护甲/盾牌库。装备护甲/盾牌需满足熟练度（技能）要求并消耗 CP；
护甲提供 AC 加值与最大敏捷上限（D&D 中甲/重甲机制）。挂到 ``ctx.equipment``。
"""
from .context import Service
from .data import EQUIPMENT_LIBRARY, ARMOR_PROFICIENCY, FINESSE_WEAPONS


class EquipmentService(Service):
    """装备相关能力。"""

    EQUIPMENT_LIBRARY = EQUIPMENT_LIBRARY
    ARMOR_PROFICIENCY = ARMOR_PROFICIENCY
    FINESSE_WEAPONS = FINESSE_WEAPONS

    def equip_item(self, item_name: str) -> tuple[bool, str]:
        st = self.ctx.state
        if item_name not in self.EQUIPMENT_LIBRARY:
            return False, "未知装备"
        etype, sub, _armor_b, max_dex, _weight, _desc, cp_cost = self.EQUIPMENT_LIBRARY[item_name]

        # 护甲熟练度检查（山地矮人特性「免中甲熟练」：中甲无需近战攻击技能）
        if etype == "护甲" or etype == "盾牌":
            if st.race == "山地矮人" and sub == "中甲":
                pass  # 免中甲熟练
            else:
                req_skill = self.ARMOR_PROFICIENCY.get(sub)
                if req_skill and st.skills.get(req_skill, 0) < 1:
                    return False, f"需要 {req_skill} 至少1级才能装备{sub}"

        if st.cp < cp_cost:
            return False, f"CP不足，需要 {cp_cost} CP"

        st.cp -= cp_cost
        st.equipment.append(item_name)
        st.purchases += 1
        self._recalc_armor_bonus()
        self.ctx.emit("character/changed", "equipment")
        return True, f"装备了 {item_name}，消耗 {cp_cost} CP"

    def unequip_item(self, item_name: str) -> tuple[bool, str]:
        st = self.ctx.state
        if item_name not in st.equipment:
            return False, "未装备此物品"
        st.equipment.remove(item_name)
        cp_cost = self.EQUIPMENT_LIBRARY[item_name][6]
        st.cp += cp_cost
        self._recalc_armor_bonus()
        return True, f"卸下了 {item_name}，返还 {cp_cost} CP"

    def _recalc_armor_bonus(self):
        """重新计算护甲总加值（含盾牌），并取最严格的敏捷上限。"""
        st = self.ctx.state
        total_armor = 0
        best_max_dex = 99
        for item in st.equipment:
            info = self.EQUIPMENT_LIBRARY.get(item)
            if info and info[0] in ("护甲", "盾牌"):
                total_armor += info[2]
                if info[3] < best_max_dex:
                    best_max_dex = info[3]
        st.armor_bonus = total_armor
        st._armor_max_dex = best_max_dex

    def _get_equipped_weapon(self) -> str:
        """获取当前装备的第一件武器名（徒手则返回 '徒手'）。"""
        st = self.ctx.state
        for item in st.equipment:
            info = self.EQUIPMENT_LIBRARY.get(item)
            if info and info[0] == "武器":
                return item
        return "徒手"

    def has_finesse_weapon(self) -> bool:
        """是否装备了灵巧武器（可用于偷袭判定）。"""
        st = self.ctx.state
        return any(
            w in self.FINESSE_WEAPONS
            for w in st.equipment
            if self.EQUIPMENT_LIBRARY.get(w, (None,))[0] == "武器"
        )
