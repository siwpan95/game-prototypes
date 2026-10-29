"""d20.sheet - 角色卡渲染服务（原 SheetMixin 改写）

将 Character 的全部状态渲染为可读的纯文本角色卡。挂到 ``ctx.sheet``。
跨子系统数据一律走 ``ctx.<service>`` / ``ctx.state``。
"""
from .context import Service
from .data import ability_mod


class SheetService(Service):
    """角色卡显示。"""

    inject = ["perks", "skills", "equipment", "derived", "slots", "race", "background", "feats", "rest"]

    def show_sheet(self) -> str:
        """渲染完整角色卡。"""
        st = self.ctx.state
        lines = ["=" * 40, "角色卡", "=" * 40]
        lines.append(f"剩余 CP: {st.cp}")
        lines.append("属性: " + ", ".join(f"{a}:{v}" for a, v in st.attributes.items()))
        lines.append("优点: " + (", ".join(st.advantages) if st.advantages else "优点: 无"))
        if st.disadvantages:
            lines.append("缺点: " + ", ".join(f"{n}(+{r})" for n, r in st.disadvantages))
        else:
            lines.append("缺点: 无")
        if st.talents:
            lines.append("天赋: " + ", ".join(f"{n} Lv.{l}" for n, l in st.talents))
        else:
            lines.append("天赋: 无")

        # ---- 扩充子系统 ----
        lines.append("种族: " + (st.race or "无"))
        if st.background:
            lines.append(f"背景: {st.background}（{self.ctx.background.feature()}）")
        else:
            lines.append("背景: 无")
        lines.append("专长: " + (", ".join(st.feats) if st.feats else "无"))
        if st.proficiencies:
            lines.append("熟练(+2): " + ", ".join(st.proficiencies))
        if st.slots:
            parts = [f"{ring}环 {used}/{owned}" for ring, used, owned in self.ctx.slots.slot_table()]
            lines.append("法术位: " + " | ".join(parts))
        else:
            lines.append("法术位: 无")

        lines.append("--- 技能 ---")
        for skill, rank in sorted(st.skills.items(), key=lambda x: x[0]):
            bonus = self.ctx.perks.get_talent_bonus(skill)
            total = rank + bonus
            bonus_str = f"(+{bonus})" if bonus else ""
            lines.append(f"{skill}: {rank}{bonus_str} = {total}")

        unlearned = [s for s in self.ctx.skills.SKILL_LIBRARY
                     if s not in st.skills or st.skills[s] == 0]
        if unlearned:
            lines.append("--- 未学技能（默认值） ---")
            for skill in sorted(unlearned):
                default = self.ctx.skills.effective_skill_rank(skill)
                lines.append(f"{skill}: ~{default} (推算)")

        lines.append("技术: " + (", ".join(st.techniques) if st.techniques else "技术: 无"))

        if st.equipment:
            lines.append("--- 装备 ---")
            for item in st.equipment:
                info = self.ctx.equipment.EQUIPMENT_LIBRARY[item]
                lines.append(f"{item}: {info[5]} (AC+{info[2]})")
        else:
            lines.append("装备: 无")

        cur_hp = self.ctx.rest.current_hp()
        max_hp = self.ctx.derived.hp()
        if cur_hp == max_hp:
            lines.append(f"HP: {max_hp} | AC: {self.ctx.derived.ac}")
        else:
            lines.append(f"HP: {cur_hp}/{max_hp} | AC: {self.ctx.derived.ac}")
        lines.append(f"先攻: +{self.ctx.rest.initiative_bonus()}")
        lines.append(f"近战: +{self.ctx.derived.attack_bonus(True)} | "
                     f"远程: +{self.ctx.derived.attack_bonus(False)}")
        lines.append(f"强韧: +{self.ctx.derived.save_bonus('fort')} | "
                     f"反射: +{self.ctx.derived.save_bonus('ref')} | "
                     f"意志: +{self.ctx.derived.save_bonus('will')}")

        lines.append("--- 属性调整值 ---")
        lines.append(" | ".join(f"{a}:{ability_mod(v):+d}" for a, v in st.attributes.items()))

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """将角色状态导出为字典（便于序列化/保存）。"""
        st = self.ctx.state
        return {
            "cp": st.cp,
            "max_disadvantage_cp": st.max_disadvantage_cp,
            "attributes": dict(st.attributes),
            "advantages": list(st.advantages),
            "disadvantages": list(st.disadvantages),
            "talents": list(st.talents),
            "skills": dict(st.skills),
            "techniques": list(st.techniques),
            "equipment": list(st.equipment),
            "race": st.race,
            "background": st.background,
            "feats": list(st.feats),
            "proficiencies": list(st.proficiencies),
            "slots": dict(st.slots),
            "slots_used": dict(st.slots_used),
            "current_hp": st.current_hp,
        }
