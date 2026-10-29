"""d20.skills - 技能购买与默认值推算服务（原 SkillsMixin 改写）

技能难度沿用 GURPS 分级（E/A/H/VH），成本按"相对属性等级"查表；默认值（未学习技能
的临时等级）采用 GURPS 的同目/同纲推算思想。挂到 ``ctx.skills``。
"""
from .context import Service
from .data import SKILL_LIBRARY, DIFFICULTY_COST, SKILL_CATEGORIES, PROFICIENCY_BONUS


class SkillsService(Service):
    """技能相关能力。"""

    inject = ["perks", "feats"]

    SKILL_LIBRARY = SKILL_LIBRARY
    DIFFICULTY_COST = DIFFICULTY_COST
    SKILL_CATEGORIES = SKILL_CATEGORIES

    def calc_skill_cost(self, skill_name: str, target_rank: int) -> tuple[int, int]:
        """计算将技能从当前等级提升到 target_rank 所需 CP。

        Returns:
            (总花费, 提升的等级数)
        """
        if skill_name not in self.SKILL_LIBRARY:
            return 0, 0
        attr_name, diff, _ = self.SKILL_LIBRARY[skill_name]
        attr_val = self.ctx.state.attributes[attr_name]
        current_rank = self.ctx.state.skills.get(skill_name, 0)
        if target_rank <= current_rank:
            return 0, 0

        total_cost = 0
        cost_table = self.DIFFICULTY_COST[diff]
        extra_cost = cost_table["extra"]
        numeric_keys = [k for k in cost_table if isinstance(k, int)]
        max_key = max(numeric_keys) if numeric_keys else 0

        for rank in range(current_rank, target_rank):
            rel = rank - attr_val
            if rel in cost_table:
                cost = cost_table[rel]
            else:
                if rel > max_key:
                    base = cost_table[max_key]
                    cost = base + extra_cost * (rel - max_key)
                else:
                    cost = 1
            total_cost += cost
        return total_cost, target_rank - current_rank

    def purchase_skill(self, skill_name: str, target_rank: int) -> tuple[bool, str]:
        """购买技能至目标绝对等级。"""
        if skill_name not in self.SKILL_LIBRARY:
            return False, "未知技能"
        cost, delta = self.calc_skill_cost(skill_name, target_rank)
        if cost == 0:
            return False, "目标等级未提高"
        st = self.ctx.state
        if st.cp < cost:
            return False, f"CP不足，需要 {cost} CP，当前剩余 {st.cp} CP"
        st.cp -= cost
        st.skills[skill_name] = target_rank
        st.purchases += 1
        self.ctx.emit("character/changed", "skills")
        return True, f"{skill_name} 提升至 {target_rank}，消耗 {cost} CP"

    def check_foundations(self) -> list[str]:
        """检查根基科是否至少投入 1 级，返回缺失列表。"""
        st = self.ctx.state
        missing = []
        for name, (_, _, is_found) in self.SKILL_LIBRARY.items():
            if is_found and st.skills.get(name, 0) < 1:
                missing.append(name)
        return missing

    def effective_skill_rank(self, skill_name: str) -> int:
        """获取技能有效等级：已学习返回 实际等级+天赋加成；未学习用同目/同纲推算。
        两类加成叠加：熟练（背景/种族，+2）与专长技能加值（演员/观察力）。
        """
        st = self.ctx.state
        learned = st.skills.get(skill_name, 0)
        if learned > 0:
            base = learned + self.ctx.perks.get_talent_bonus(skill_name)
        elif skill_name not in self.SKILL_LIBRARY:
            base = 0
        else:
            attr_name, _, _ = self.SKILL_LIBRARY[skill_name]
            same_attr_ranks = [
                st.skills[s]
                for s, (a, _, _) in self.SKILL_LIBRARY.items()
                if a == attr_name and st.skills.get(s, 0) > 0 and s != skill_name
            ]
            if same_attr_ranks:
                base = max(sum(same_attr_ranks) // len(same_attr_ranks) - 2, 0)
            else:
                base = 0
                for cat, skills in self.SKILL_CATEGORIES.items():
                    if skill_name in skills:
                        cat_ranks = [
                            st.skills[s]
                            for s in skills
                            if st.skills.get(s, 0) > 0 and s != skill_name
                        ]
                        if cat_ranks:
                            base = max(sum(cat_ranks) // len(cat_ranks) - 3, 0)
                        break
        # 熟练（背景/种族）+2 与专长技能加值
        if skill_name in st.proficiencies:
            base += PROFICIENCY_BONUS
        base += self.ctx.feats.skill_bonus(skill_name)
        return base
