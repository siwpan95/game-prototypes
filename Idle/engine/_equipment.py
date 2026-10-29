"""
装备系统 Mixin — 部位(插槽) / 随机词条 / 套装 / 掉落 / 装备到英雄。
"""
import random
from config import (
    EQUIP_TIERS, EQUIP_NAMES, BACKPACK_LIMIT,
    EQUIPMENT_SLOTS, EQUIPMENT_AFFIXES, EQUIPMENT_SETS,
    EQUIPMENT_AFFIX_RARITY_MULT, EQUIPMENT_AFFIX_COUNT, EQUIPMENT_SET_CHANCE,
)


class _EquipmentMixin:
    """提供给 GameEngine 的装备相关方法。"""

    state: object

    # ==================== 掉落 ====================

    def _try_equip_drop(self):
        drop_mult = self._affix_drop_mult() * self._golden_drop_mult() * self._event_drop_mult()
        if len(self.state.equipment_inventory) >= BACKPACK_LIMIT:
            return
        for tier in EQUIP_TIERS:
            if random.random() < tier["drop_per_tick"] * drop_mult:
                item = self._roll_equipment(tier)
                self.state.equipment_inventory.append(item)
                self.state.stats["drops"] += 1
                self._check_achievements()
                break

    def _roll_equipment(self, tier: dict) -> dict:
        rarity = tier["rarity"]
        names = EQUIP_NAMES.get(rarity, ["未知装备"])
        name = random.choice(names)
        bonus = random.randint(tier["bonus_min"], tier["bonus_max"])

        # 部位
        slot = random.choice(EQUIPMENT_SLOTS)["key"]

        # 词条
        affixes = []
        n = EQUIPMENT_AFFIX_COUNT.get(rarity, 1)
        rmult = EQUIPMENT_AFFIX_RARITY_MULT.get(rarity, 1.0)
        pool = [(a, a.get("weight", 1)) for a in EQUIPMENT_AFFIXES]
        for _ in range(n):
            a = random.choices(pool, weights=[w for _, w in pool], k=1)[0][0]
            val = round(random.uniform(a["min"], a["max"]) * rmult, 4)
            affixes.append({
                "key": a["key"], "name": a["name"],
                "stat": a["stat"], "value": val,
            })

        # 套装
        set_id = None
        set_name = ""
        if random.random() < EQUIPMENT_SET_CHANCE and EQUIPMENT_SETS:
            s = random.choice(EQUIPMENT_SETS)
            set_id = s["id"]
            set_name = s["name"]

        return {
            "name": name, "rarity": rarity, "bonus": bonus,
            "color": tier["color"], "slot": slot,
            "affixes": affixes, "set_id": set_id, "set_name": set_name,
        }

    # ==================== 装备 / 卸下 ====================

    def equip_to_hero(self, eq_index: int, hero_key: str) -> str | None:
        if eq_index < 0 or eq_index >= len(self.state.equipment_inventory):
            return "无效装备"
        hstate = self.state.heroes.get(hero_key)
        if not hstate or hstate["level"] <= 0:
            return "英雄未解锁"
        eq = self.state.equipment_inventory.pop(eq_index)
        slot = eq.get("slot", "weapon")
        old = hstate["equipped"].get(slot)
        hstate["equipped"][slot] = eq
        if old:
            self.state.equipment_inventory.append(old)
        self._recalc()
        return None

    def unequip_from_hero(self, hero_key: str, slot: str) -> str | None:
        hstate = self.state.heroes.get(hero_key)
        if not hstate:
            return "未知英雄"
        eq = hstate["equipped"].get(slot)
        if not eq:
            return "该部位无装备"
        del hstate["equipped"][slot]
        self.state.equipment_inventory.append(eq)
        self._recalc()
        return None

    # ==================== 查询 ====================

    def get_equipment(self) -> list:
        return self.state.equipment_inventory

    def get_hero_slots(self, hero_key: str) -> dict:
        hstate = self.state.heroes.get(hero_key, {"equipped": {}})
        return hstate.get("equipped", {})

    # ==================== 词条 / 套装 加成 ====================

    def _hero_affix_factor(self, hstate: dict, stat: str) -> float:
        """返回该英雄装备提供的某乘区因子（1 + Σ value），仅统计 dps_pct/all_pct/click_pct。

        套装加成按「每个套装只计一次」处理，避免每件装备重复叠加。
        """
        total = 0.0
        equipped = hstate.get("equipped", {})
        set_counts: dict = {}
        for slot, eq in equipped.items():
            if not eq:
                continue
            for af in eq.get("affixes", []):
                if af["stat"] == stat:
                    total += af["value"]
            sid = eq.get("set_id")
            if sid and sid not in set_counts:
                set_counts[sid] = self._count_set_pieces(hstate, sid)
        for sid, cnt in set_counts.items():
            sdef = self._get_set(sid)
            for b in sdef.get("bonuses", []):
                if cnt >= b["count"] and b["stat"] == stat:
                    total += b["value"]
        return 1.0 + total

    def _affix_additive(self, stat: str) -> float:
        """跨全部英雄，累加某加性词条（crit_chance/gold_pct/drop_pct）。套装只计一次。"""
        total = 0.0
        for hv in self.state.heroes.values():
            equipped = hv.get("equipped", {})
            set_counts: dict = {}
            for slot, eq in equipped.items():
                if not eq:
                    continue
                for af in eq.get("affixes", []):
                    if af["stat"] == stat:
                        total += af["value"]
                sid = eq.get("set_id")
                if sid and sid not in set_counts:
                    set_counts[sid] = self._count_set_pieces(hv, sid)
            for sid, cnt in set_counts.items():
                sdef = self._get_set(sid)
                for b in sdef.get("bonuses", []):
                    if cnt >= b["count"] and b["stat"] == stat:
                        total += b["value"]
        return total

    def _affix_gold_mult(self) -> float:
        return 1.0 + self._affix_additive("gold_pct")

    def _affix_drop_mult(self) -> float:
        return 1.0 + self._affix_additive("drop_pct")

    def _affix_crit_chance(self) -> float:
        chance = self._affix_additive("crit_chance")
        # 游侠被动暴击 10%
        for hk, hv in self.state.heroes.items():
            hd = self.get_hero_info(hk)
            if hd and hv["level"] > 0 and hd.get("crit_chance"):
                chance += hd["crit_chance"]
        return min(chance, 1.0)

    def _count_set_pieces(self, hstate: dict, set_id: str) -> int:
        return sum(
            1 for eq in hstate.get("equipped", {}).values()
            if eq and eq.get("set_id") == set_id
        )

    def _get_set(self, set_id: str) -> dict:
        for s in EQUIPMENT_SETS:
            if s["id"] == set_id:
                return s
        return {"bonuses": []}
