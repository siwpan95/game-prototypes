"""d20.derived - 衍生数值服务（原 DerivedMixin 改写）

由属性、技能、装备、天赋推算出的战斗数值：HP、AC、攻击加值、豁免加值。融合 D&D 的
AC 公式与 GURPS 的活力→HP 思路。挂到 ``ctx.derived``。
"""
from .context import Service
from .data import ability_mod


class DerivedService(Service):
    """衍生数值（属性/方法）。"""

    inject = ["skills", "equipment", "feats", "race"]

    @property
    def max_hp(self) -> float:
        """最大生命值：体质调整 + 活力技能等级（+种族/专长 waterfall 钩子）。"""
        st = self.ctx.state
        con_mod = ability_mod(st.attributes["体质"])
        vit_rank = st.skills.get("活力", 0)
        if vit_rank == 0:
            return 0.0
        base = 6 + con_mod + (vit_rank - 1) * (3.5 + con_mod)
        return self.ctx.waterfall("derived/max_hp", base)

    def hp(self) -> int:
        """当前最大 HP（整数化）。"""
        m = self.max_hp
        return int(m) if m else 0

    @property
    def ac(self) -> int:
        """护甲等级：10 + 敏捷调整(受护甲上限) + 闪避加值 + 护甲加值 + 专长/装备加成。"""
        st = self.ctx.state
        dex_mod = ability_mod(st.attributes["敏捷"])
        max_dex = getattr(st, "_armor_max_dex", 99)
        effective_dex = min(dex_mod, max_dex)
        dodge_rank = st.skills.get("闪避防御", 0)
        dodge_bonus = dodge_rank // 2
        ac = 10 + effective_dex + dodge_bonus + st.armor_bonus
        # 双持大师：双持两把近战武器 +1
        weapons = [e for e in st.equipment
                   if self.ctx.equipment.EQUIPMENT_LIBRARY.get(e, ("",))[0] == "武器"
                   and self.ctx.equipment.EQUIPMENT_LIBRARY[e][1] in ("近战", "近战-轻", "近战-双手")]
        if self.ctx.feats.has_feat("双持大师") and len(weapons) >= 2:
            ac += 1
        # 防御决斗者：装备灵巧武器 +2
        if self.ctx.feats.has_feat("防御决斗者") and self.ctx.equipment.has_finesse_weapon():
            ac += 2
        return ac

    def attack_bonus(self, melee: bool = True) -> int:
        """攻击加值（近战/远程），取对应技能有效等级。"""
        skill = "近战攻击" if melee else "远程攻击"
        return self.ctx.skills.effective_skill_rank(skill)

    def save_bonus(self, save_type: str) -> int:
        """豁免加值：强韧(fort)/反射(ref)/意志(will) = 技能有效等级 + 属性调整 + 种族加成。"""
        mapping = {
            "fort": ("强韧豁免", "体质"),
            "ref": ("反射豁免", "敏捷"),
            "will": ("意志豁免", "感知"),
        }
        if save_type not in mapping:
            raise ValueError(f"未知豁免类型: {save_type}")
        skill, attr = mapping[save_type]
        rank = self.ctx.skills.effective_skill_rank(skill)
        mod = ability_mod(self.ctx.state.attributes[attr])
        return rank + mod + self.ctx.race.save_bonus_adjust(save_type)
