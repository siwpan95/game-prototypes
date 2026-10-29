"""d20.rest - 先攻 / 休整服务（决策 E：引入 current_hp）

D&D 5e SRD：先攻 = d20 + 敏捷调整（+战斗反射/警觉/木精灵加成，waterfall）；
短休花 1 个生命骰（d6+体质调整，快速回复×2，顽强保底 2×体质调整）；
长休回满 HP、恢复法术位、回一半生命骰、重置每日能力。
挂到 ctx.rest。
"""
from .context import Service
from .data import ability_mod
from .dice import roll_d20, roll_d6


class RestService(Service):
    """先攻与休整能力。"""

    inject = ["derived", "dice", "slots", "feats", "race"]

    # ---------- 当前 HP ----------
    def current_hp(self) -> int:
        st = self.ctx.state
        if st.current_hp is None:
            return self.ctx.derived.hp()
        return st.current_hp

    def take_damage(self, amount: int, damage_type: str = "") -> str:
        """受到伤害。damage_type 为 火/寒/电/酸 时，抗性种族减半。"""
        st = self.ctx.state
        n = int(amount)
        if damage_type:
            elem = self.ctx.race.elemental()
            resist = (
                (st.race == "提夫林" and damage_type == "火")
                or (self.ctx.race.has_trait("龙息") and damage_type == elem)
            )
            if resist:
                n = max(n // 2, 1)
        new_hp = max(self.current_hp() - n, 0)
        note = ""
        # 半兽人 濒死不屈：每日一次免于倒地（HP 保持 1）
        if new_hp == 0 and st.race == "半兽人" and not st.relentless_used:
            st.relentless_used = True
            new_hp = 1
            note = "（濒死不屈：HP 保持 1）"
        st.current_hp = new_hp
        self.ctx.emit("character/changed", "rest")
        return f"受到 {n} 点伤害，HP {self.current_hp()}/{self.ctx.derived.hp()}{note}"

    def heal(self, amount: int) -> str:
        """治疗。"""
        st = self.ctx.state
        n = max(int(amount), 0)
        st.current_hp = min(self.current_hp() + n, self.ctx.derived.hp())
        self.ctx.emit("character/changed", "rest")
        return f"恢复 {n} 点生命，HP {self.current_hp()}/{self.ctx.derived.hp()}"

    # ---------- 先攻 ----------
    def initiative_bonus(self) -> int:
        st = self.ctx.state
        base = ability_mod(st.attributes["敏捷"])
        if "战斗反射" in st.advantages:
            base += 1
        return self.ctx.waterfall("derived/initiative", base)

    def roll_initiative(self) -> str:
        bonus = self.initiative_bonus()
        roll = roll_d20()
        return f"先攻: d20+{bonus} = {roll}+{bonus} = {roll + bonus}"

    # ---------- 休整 ----------
    def short_rest(self) -> str:
        """短休：花 1 个生命骰回复 HP（生命骰数 = 活力等级），龙息充能。"""
        st = self.ctx.state
        max_hd = st.skills.get("活力", 0)
        if st.hit_dice_used >= max_hd:
            return "无可用生命骰"
        con_mod = ability_mod(st.attributes["体质"])
        _, total = roll_d6(1, con_mod)
        if "快速回复" in st.advantages:
            total *= 2
        if self.ctx.feats.has_feat("顽强"):
            total = max(total, 2 * con_mod)
        st.hit_dice_used += 1
        st.breath_used = False
        self.heal(total)
        return (f"短休：掷生命骰 1d6+{con_mod} 回复 {total} 点，"
                f"HP {self.current_hp()}/{self.ctx.derived.hp()}，"
                f"已用生命骰 {st.hit_dice_used}/{max_hd}")

    def long_rest(self) -> str:
        """长休：回满 HP、恢复全部法术位、回一半生命骰、重置每日能力。"""
        st = self.ctx.state
        st.current_hp = self.ctx.derived.hp()
        max_hd = st.skills.get("活力", 0)
        st.hit_dice_used = max(0, st.hit_dice_used - max(max_hd // 2, 1))
        st.lucky_used = 0
        st.breath_used = False
        st.relentless_used = False
        self.ctx.slots.recover_all()
        self.ctx.emit("character/changed", "rest")
        return (f"长休：HP 回满 {self.current_hp()}/{self.ctx.derived.hp()}，"
                f"法术位恢复，生命骰恢复一半（剩余已用 {st.hit_dice_used}），每日能力重置")
