"""d20.perks - 优点 / 缺点 / 天赋服务（原 PerksMixin 改写）

参考 GURPS 的优点（Advantages）、缺点（Disadvantages，返还 CP，上限为起始 CP 一半）
与天赋（Talent，对一组相关技能提供加成）。挂到 ``ctx.perks``。
"""
from .context import Service
from .data import (ADVANTAGES_LIBRARY, DISADVANTAGES_LIBRARY, TALENT_BONUS_GROUPS)


class PerksService(Service):
    """优缺点/天赋能力。"""

    ADVANTAGES_LIBRARY = ADVANTAGES_LIBRARY
    DISADVANTAGES_LIBRARY = DISADVANTAGES_LIBRARY
    TALENT_BONUS_GROUPS = TALENT_BONUS_GROUPS

    # ---------- 优点 ----------
    def add_advantage(self, name: str, cost: int) -> tuple[bool, str]:
        st = self.ctx.state
        if st.cp < cost:
            return False, "CP不足"
        st.advantages.append(name)
        st.cp -= cost
        st.purchases += 1
        return True, f"获得优点：{name}，消耗 {cost} CP"

    def add_advantage_by_name(self, name: str) -> tuple[bool, str]:
        if name not in self.ADVANTAGES_LIBRARY:
            return False, f"未知优点: {name}"
        return self.add_advantage(name, self.ADVANTAGES_LIBRARY[name])

    # ---------- 缺点 ----------
    def add_disadvantage(self, name: str, cp_return: int) -> tuple[bool, str]:
        st = self.ctx.state
        total_returned = sum(ret for _, ret in st.disadvantages)
        if total_returned + cp_return > st.max_disadvantage_cp:
            return False, f"缺点返还CP不能超过{st.max_disadvantage_cp}"
        st.disadvantages.append((name, cp_return))
        st.cp += cp_return
        st.purchases += 1
        return True, f"获得缺点：{name}，返还 {cp_return} CP"

    def add_disadvantage_by_name(self, name: str) -> tuple[bool, str]:
        if name not in self.DISADVANTAGES_LIBRARY:
            return False, f"未知缺点: {name}"
        return self.add_disadvantage(name, self.DISADVANTAGES_LIBRARY[name])

    # ---------- 天赋 ----------
    def add_talent(self, talent_name: str, level: int = 1) -> tuple[bool, str]:
        st = self.ctx.state
        if talent_name not in self.TALENT_BONUS_GROUPS:
            return False, f"未知天赋: {talent_name}"
        if not (1 <= level <= 3):
            return False, "天赋等级需在 1-3 之间"
        cost = 5 * level
        if st.cp < cost:
            return False, "CP不足"
        st.talents.append((talent_name, level))
        st.cp -= cost
        st.purchases += 1
        return True, f"获得天赋 {talent_name} Lv.{level}，消耗 {cost} CP"

    def get_talent_bonus(self, skill_name: str) -> int:
        """计算天赋对指定技能的总加成等级。"""
        st = self.ctx.state
        bonus = 0
        for talent_name, level in st.talents:
            group = self.TALENT_BONUS_GROUPS.get(talent_name, [])
            if skill_name in group:
                bonus += level
        return bonus
