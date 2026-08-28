"""d20.combat - 战斗宏服务

融合 D&D 的战技/法术与 GURPS 的战斗机动（Maneuver）。所有宏返回可读字符串。挂到
ctx.combat。跨子系统调用一律走 ctx.<service>。
法术宏经 ctx.slots 消耗法术位并支持上环施法（upcast）；战斗骰经 ctx.dice.d20_roll()
统一入口（幸运/半身人重掷钩子生效）。
"""
from .context import Service
from .data import TECHNIQUES, SPELL_RINGS
import random


class CombatService(Service):
    """战斗宏能力。"""

    inject = ["derived", "equipment", "dice", "techniques", "skills", "slots", "feats", "rest"]

    TECHNIQUES = TECHNIQUES

    def combat_macro(self, macro_name: str, **kwargs) -> str:
        """执行预设战斗宏，自动计算技术加成。"""
        macros = {
            "melee_attack": self._macro_melee_attack,
            "ranged_attack": self._macro_ranged_attack,
            "sneak_attack": self._macro_sneak_attack,
            "power_attack": self._macro_power_attack,
            "whirlwind": self._macro_whirlwind,
            "fireball": self._macro_fireball,
            "magic_missile": self._macro_magic_missile,
            "healing_word": self._macro_healing_word,
            "fire_bolt": self._macro_fire_bolt,
            "ray_of_frost": self._macro_ray_of_frost,
            "scorching_ray": self._macro_scorching_ray,
            "lightning_bolt": self._macro_lightning_bolt,
            "cone_of_cold": self._macro_cone_of_cold,
            "meteor_swarm": self._macro_meteor_swarm,
            "dragon_breath": self._macro_dragon_breath,
            "deceptive_attack": self._macro_deceptive_attack,
            "rapid_strike": self._macro_rapid_strike,
            "allout_strong": self._macro_allout_strong,
            "allout_determined": self._macro_allout_determined,
        }
        handler = macros.get(macro_name)
        if not handler:
            return f"未知战斗宏: {macro_name}"
        return handler(**kwargs)

    # ====================================================================
    #  辅助
    # ====================================================================
    def _dmg_rolls(self, num: int, die: int, element: str = "") -> list[int]:
        """掷伤害骰；元素亲和（对应元素）时 1 视为 2。"""
        rolls = [random.randint(1, die) for _ in range(num)]
        if element and self.ctx.feats.element_picked() == element:
            rolls = [2 if r == 1 else r for r in rolls]
        return rolls

    def _str_mod(self) -> int:
        return max((self.ctx.state.attributes["力量"] - 10) // 2, 0)

    def _weapon_hit(self, weapon: str, str_mod: int) -> str:
        dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
        total = sum(dmg_rolls) + str_mod
        return f"  ✓ 命中！伤害: {dmg_desc}+{str_mod} = {total}"

    def _spend(self, ring: int) -> tuple[bool, str]:
        return self.ctx.slots.spend_slot(ring)

    # ====================================================================
    #  D&D 风格战技 / 法术
    # ====================================================================
    def _macro_melee_attack(self, dc: int = 10, target_ac: int = 10, gwm: bool = False) -> str:
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        penalty = -5 if (gwm and self.ctx.feats.has_feat("巨武宗师")) else 0
        bonus_dmg = 10 if penalty else 0
        roll = self.ctx.dice.d20_roll()
        total = roll + atk_bonus + penalty
        hit = total >= target_ac
        tag = " [巨武宗师]" if penalty else ""
        lines = [f"⚔ 近战攻击: d20+{atk_bonus}{penalty}{tag} = {roll}+{atk_bonus + penalty} = {total} vs AC {target_ac}"]
        if hit:
            weapon = self.ctx.equipment._get_equipped_weapon()
            dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
            total_dmg = sum(dmg_rolls) + self._str_mod() + bonus_dmg
            lines.append(f"  ✓ 命中！伤害: {dmg_desc}+{self._str_mod()}(力量)" +
                         (f"+{bonus_dmg}(巨武)" if bonus_dmg else "") + f" = {total_dmg}")
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _macro_ranged_attack(self, dc: int = 10, target_ac: int = 10, sharpshooter: bool = False) -> str:
        atk_bonus = self.ctx.derived.attack_bonus(melee=False)
        penalty = -5 if (sharpshooter and self.ctx.feats.has_feat("神射手")) else 0
        bonus_dmg = 10 if penalty else 0
        roll = self.ctx.dice.d20_roll()
        total = roll + atk_bonus + penalty
        hit = total >= target_ac
        tag = " [神射手]" if penalty else ""
        lines = [f"🏹 远程攻击: d20+{atk_bonus}{penalty}{tag} = {roll}+{atk_bonus + penalty} = {total} vs AC {target_ac}"]
        if hit:
            weapon = self.ctx.equipment._get_equipped_weapon()
            dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
            total_dmg = sum(dmg_rolls) + bonus_dmg
            lines.append(f"  ✓ 命中！伤害: {dmg_desc}" +
                         (f"+{bonus_dmg}(神射)" if bonus_dmg else "") + f" = {total_dmg}")
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _sneak_attack_dice(self) -> int:
        """偷袭精准伤害骰数（D&D 风格：随近战攻击等级成长）。需装备灵巧武器。"""
        if not self.ctx.equipment.has_finesse_weapon():
            return 0
        rank = self.ctx.derived.attack_bonus(melee=True)
        dice = max(0, (rank - 4) // 2 + 1)
        return min(dice, 10)

    def _macro_sneak_attack(self, dc: int = 10, target_ac: int = 10,
                            flat_footed: bool = True) -> str:
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        roll = self.ctx.dice.d20_roll()
        total = roll + atk_bonus
        hit = total >= target_ac
        has_tech = self.ctx.techniques.has_technique("偷袭要害打击")
        lines = [f"🗡 偷袭攻击: d20+{atk_bonus} = {roll}+{atk_bonus} = {total} vs AC {target_ac}"]

        if has_tech:
            penalty = self.TECHNIQUES["偷袭要害打击"][3]
            if penalty:
                lines.append(f"  技术修正: 攻击{penalty}")
            adjusted_total = total + penalty
            hit = adjusted_total >= target_ac
            lines.append(f"  调整后: {adjusted_total} vs AC {target_ac}")

        if hit:
            weapon = self.ctx.equipment._get_equipped_weapon()
            dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
            total_dmg = sum(dmg_rolls) + self._str_mod()
            lines.append(f"  ✓ 命中！基础伤害: {dmg_desc}+{self._str_mod()}(力量) = {sum(dmg_rolls)}+{self._str_mod()} = {total_dmg}")
            if has_tech and flat_footed:
                dice = self._sneak_attack_dice()
                if dice > 0:
                    sneak_dmg = [random.randint(1, 6) for _ in range(dice)]
                    lines.append(f"  💀 偷袭精准伤害: {dice}d6 = {sneak_dmg} = {sum(sneak_dmg)}")
                    lines.append(f"  总伤害: {total_dmg + sum(sneak_dmg)}")
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _macro_power_attack(self, target_ac: int = 10, two_handed: bool = False) -> str:
        if not self.ctx.techniques.has_technique("猛力攻击"):
            return "未学会「猛力攻击」技术"
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        power_penalty = -1
        power_bonus = 3 if two_handed else 2
        roll = self.ctx.dice.d20_roll()
        total = roll + atk_bonus + power_penalty
        hit = total >= target_ac
        lines = [f"💥 猛力攻击: d20+{atk_bonus}{power_penalty} = {roll}+{atk_bonus+power_penalty} = {total} vs AC {target_ac}"]
        if hit:
            weapon = self.ctx.equipment._get_equipped_weapon()
            dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
            str_mod = self._str_mod()
            if two_handed:
                str_mod = int(str_mod * 1.5)
            total_dmg = sum(dmg_rolls) + str_mod + power_bonus
            lines.append(f"  ✓ 命中！伤害: {dmg_desc}+{str_mod}(力量)+{power_bonus}(猛力) = {total_dmg}")
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _macro_whirlwind(self, num_targets: int = 2, target_ac: int = 10) -> str:
        if not self.ctx.techniques.has_technique("旋风切割"):
            return "未学会「旋风切割」技术"
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        penalty = self.TECHNIQUES["旋风切割"][3]
        lines = [f"🌀 旋风切割 (惩罚{penalty}):"]
        for i in range(num_targets):
            roll = self.ctx.dice.d20_roll()
            total = roll + atk_bonus + penalty
            hit = total >= target_ac
            if hit:
                weapon = self.ctx.equipment._get_equipped_weapon()
                dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
                total_dmg = sum(dmg_rolls) + self._str_mod()
                lines.append(f"  目标{i+1}: d20={roll} 总={total} ✓ 命中 伤害={total_dmg}")
            else:
                lines.append(f"  目标{i+1}: d20={roll} 总={total} ✗ 未命中")
        return "\n".join(lines)

    # ---------- 法术宏（消耗法术位 + 上环） ----------
    def _macro_fireball(self, dc: int = 15, num_targets: int = 1, upcast: int | None = None) -> str:
        if not self.ctx.techniques.has_technique("火球术"):
            return "未学会「火球术」技术"
        ring = upcast or SPELL_RINGS["火球术"]
        if ring < SPELL_RINGS["火球术"]:
            ring = SPELL_RINGS["火球术"]
        ok, msg = self._spend(ring)
        if not ok:
            return f"施法失败：{msg}"
        cast_bonus = self.ctx.skills.effective_skill_rank("施法攻击")
        roll = self.ctx.dice.d20_roll()
        total = roll + cast_bonus
        penalty = self.TECHNIQUES["火球术"][3]
        up = ring - SPELL_RINGS["火球术"]
        lines = [f"🔥 火球术({ring}环): 施法检定 d20+{cast_bonus} = {roll}+{cast_bonus} = {total} vs DC {dc}"]
        if total + penalty >= dc:
            dmg = self._dmg_rolls(8 + up, 6, "火")
            lines.append(f"  伤害: {8 + up}d6 = {dmg} = {sum(dmg)} 火焰")
            if num_targets > 1:
                lines.append(f"  命中 {num_targets} 个目标！每个目标受到 {sum(dmg)} 火焰伤害")
        else:
            lines.append("  ✗ 施法失败")
        return "\n".join(lines)

    def _macro_magic_missile(self, num_targets: int = 1, upcast: int | None = None) -> str:
        if not self.ctx.techniques.has_technique("魔法飞弹"):
            return "未学会「魔法飞弹」技术"
        ring = max(upcast or 1, SPELL_RINGS["魔法飞弹"])
        ok, msg = self._spend(ring)
        if not ok:
            return f"施法失败：{msg}"
        missiles = 3 + (ring - 1)
        lines = [f"✨ 魔法飞弹({ring}环，{missiles}发，自动命中):"]
        total = 0
        for i in range(missiles):
            d = random.randint(1, 4) + 1
            total += d
            lines.append(f"  第{i+1}发: 1d4+1 = {d}")
        if num_targets > 1:
            lines.append(f"  分散打击 {min(num_targets, missiles)} 个目标，共造成 {total} 力场伤害")
        else:
            lines.append(f"  单目标共造成 {total} 力场伤害")
        return "\n".join(lines)

    def _macro_healing_word(self, upcast: int | None = None) -> str:
        if not self.ctx.techniques.has_technique("治疗言灵"):
            return "未学会「治疗言灵」技术"
        ring = max(upcast or 1, SPELL_RINGS["治疗言灵"])
        ok, msg = self._spend(ring)
        if not ok:
            return f"施法失败：{msg}"
        cast_mod = (self.ctx.state.attributes["智力"] - 10) // 2
        dice = 1 + (ring - 1)
        heal = sum(random.randint(1, 4) for _ in range(dice)) + max(cast_mod, 1)
        self.ctx.rest.heal(heal)
        return f"💚 治疗言灵({ring}环): {dice}d4+{max(cast_mod,1)} = {heal} 生命恢复"

    def _macro_fire_bolt(self, target_ac: int = 10) -> str:
        if not self.ctx.techniques.has_technique("火焰箭"):
            return "未学会「火焰箭」戏法"
        cast_bonus = self.ctx.skills.effective_skill_rank("施法攻击")
        roll = self.ctx.dice.d20_roll()
        total = roll + cast_bonus
        hit = total >= target_ac
        lines = [f"🔥 火焰箭(戏法): 施法检定 d20+{cast_bonus} = {total} vs AC {target_ac}"]
        if hit:
            dmg = self._dmg_rolls(1, 10, "火")
            lines.append(f"  ✓ 命中！伤害: 1d10 = {dmg[0]} 火焰")
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _macro_ray_of_frost(self, target_ac: int = 10) -> str:
        if not self.ctx.techniques.has_technique("霜冻射线"):
            return "未学会「霜冻射线」戏法"
        cast_bonus = self.ctx.skills.effective_skill_rank("施法攻击")
        roll = self.ctx.dice.d20_roll()
        total = roll + cast_bonus
        hit = total >= target_ac
        lines = [f"❄ 霜冻射线(戏法): 施法检定 d20+{cast_bonus} = {total} vs AC {target_ac}"]
        if hit:
            dmg = self._dmg_rolls(1, 8, "寒")
            lines.append(f"  ✓ 命中！伤害: 1d8 = {dmg[0]} 寒冷")
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _macro_scorching_ray(self, target_ac: int = 10, upcast: int | None = None) -> str:
        if not self.ctx.techniques.has_technique("灼热射线"):
            return "未学会「灼热射线」技术"
        ring = max(upcast or 2, SPELL_RINGS["灼热射线"])
        ok, msg = self._spend(ring)
        if not ok:
            return f"施法失败：{msg}"
        rays = 3 + (ring - 2)
        cast_bonus = self.ctx.skills.effective_skill_rank("施法攻击")
        lines = [f"☀ 灼热射线({ring}环，{rays}道):"]
        total = 0
        for i in range(rays):
            roll = self.ctx.dice.d20_roll()
            if roll + cast_bonus >= target_ac:
                dmg = self._dmg_rolls(2, 6, "火")
                total += sum(dmg)
                lines.append(f"  第{i+1}道: d20+{cast_bonus}={roll + cast_bonus} ✓ 命中 2d6={dmg} 火焰")
            else:
                lines.append(f"  第{i+1}道: d20+{cast_bonus}={roll + cast_bonus} ✗ 未命中")
        lines.append(f"  共造成 {total} 火焰伤害")
        return "\n".join(lines)

    def _macro_lightning_bolt(self, dc: int = 15, upcast: int | None = None) -> str:
        if not self.ctx.techniques.has_technique("闪电束"):
            return "未学会「闪电束」技术"
        ring = max(upcast or 3, SPELL_RINGS["闪电束"])
        ok, msg = self._spend(ring)
        if not ok:
            return f"施法失败：{msg}"
        cast_bonus = self.ctx.skills.effective_skill_rank("施法攻击")
        roll = self.ctx.dice.d20_roll()
        total = roll + cast_bonus
        penalty = self.TECHNIQUES["闪电束"][3]
        up = ring - 3
        lines = [f"⚡ 闪电束({ring}环): 施法检定 d20+{cast_bonus} = {total} vs DC {dc}"]
        if total + penalty >= dc:
            dmg = self._dmg_rolls(8 + up, 6, "电")
            lines.append(f"  伤害: {8 + up}d6 = {dmg} = {sum(dmg)} 闪电")
        else:
            lines.append("  ✗ 施法失败")
        return "\n".join(lines)

    def _macro_cone_of_cold(self, dc: int = 17, upcast: int | None = None) -> str:
        if not self.ctx.techniques.has_technique("寒冰锥"):
            return "未学会「寒冰锥」技术"
        ring = max(upcast or 5, SPELL_RINGS["寒冰锥"])
        ok, msg = self._spend(ring)
        if not ok:
            return f"施法失败：{msg}"
        cast_bonus = self.ctx.skills.effective_skill_rank("施法攻击")
        roll = self.ctx.dice.d20_roll()
        total = roll + cast_bonus
        penalty = self.TECHNIQUES["寒冰锥"][3]
        up = ring - 5
        lines = [f"❄ 寒冰锥({ring}环): 施法检定 d20+{cast_bonus} = {total} vs DC {dc}"]
        if total + penalty >= dc:
            dmg = self._dmg_rolls(8 + up, 8, "寒")
            lines.append(f"  伤害: {8 + up}d8 = {dmg} = {sum(dmg)} 寒冷")
        else:
            lines.append("  ✗ 施法失败")
        return "\n".join(lines)

    def _macro_meteor_swarm(self, dc: int = 20, upcast: int | None = None) -> str:
        if not self.ctx.techniques.has_technique("陨石雨"):
            return "未学会「陨石雨」技术"
        ring = max(upcast or 9, SPELL_RINGS["陨石雨"])
        ok, msg = self._spend(ring)
        if not ok:
            return f"施法失败：{msg}"
        cast_bonus = self.ctx.skills.effective_skill_rank("施法攻击")
        roll = self.ctx.dice.d20_roll()
        total = roll + cast_bonus
        penalty = self.TECHNIQUES["陨石雨"][3]
        lines = [f"☄ 陨石雨(9环): 施法检定 d20+{cast_bonus} = {total} vs DC {dc}"]
        if total + penalty >= dc:
            dmg = self._dmg_rolls(40, 6, "火")
            lines.append(f"  伤害: 40d6 = {sum(dmg)} 火焰+钝击（范围毁灭）")
        else:
            lines.append("  ✗ 施法失败")
        return "\n".join(lines)

    def _macro_dragon_breath(self, dc: int = 13) -> str:
        if self.ctx.state.race != "龙裔":
            return "非龙裔种族，无法使用龙息"
        st = self.ctx.state
        if st.breath_used:
            return "龙息已使用（短休后充能）"
        elem = self.ctx.race.elemental()
        dmg = self._dmg_rolls(2, 6, elem)
        st.breath_used = True
        return f"🐉 龙息({elem}): 2d6 = {dmg} = {sum(dmg)} {elem}伤害（范围喷吐）"

    # ====================================================================
    #  GURPS 风格战技（Maneuver / Technique）
    # ====================================================================
    def _macro_deceptive_attack(self, target_ac: int = 10, target_def_penalty: int = 0) -> str:
        if not self.ctx.techniques.has_technique("欺诈攻击"):
            return "未学会「欺诈攻击」技术"
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        penalty = -2
        if atk_bonus + penalty < 10:
            return "技能有效等级不足（欺诈攻击不可使技能低于10）"
        foe_def_pen = abs(penalty) // 2
        roll = self.ctx.dice.d20_roll()
        total = roll + atk_bonus + penalty
        effective_ac = max(target_ac - foe_def_pen, 5)
        hit = total >= effective_ac
        lines = [f"🎭 欺诈攻击: d20+{atk_bonus}{penalty} = {total} "
                 f"(敌方AC{target_ac}-{foe_def_pen}={effective_ac})"]
        if hit:
            lines.append(self._weapon_hit(self.ctx.equipment._get_equipped_weapon(), self._str_mod()))
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _macro_rapid_strike(self, target_ac: int = 10) -> str:
        if not self.ctx.techniques.has_technique("连环打击"):
            return "未学会「连环打击」技术"
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        penalty = self.TECHNIQUES["连环打击"][3]
        lines = [f"⚡ 连环打击 (各{penalty}):"]
        for i in range(2):
            roll = self.ctx.dice.d20_roll()
            total = roll + atk_bonus + penalty
            hit = total >= target_ac
            if hit:
                weapon = self.ctx.equipment._get_equipped_weapon()
                dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
                total_dmg = sum(dmg_rolls) + self._str_mod()
                lines.append(f"  第{i+1}击: d20={roll} 总={total} ✓ 命中 伤害={total_dmg}")
            else:
                lines.append(f"  第{i+1}击: d20={roll} 总={total} ✗ 未命中")
        return "\n".join(lines)

    def _macro_allout_strong(self, target_ac: int = 10, two_handed: bool = False) -> str:
        if not self.ctx.techniques.has_technique("全力强击"):
            return "未学会「全力强击」技术"
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        roll = self.ctx.dice.d20_roll()
        total = roll + atk_bonus
        hit = total >= target_ac
        lines = [f"💪 全力强击: d20+{atk_bonus} = {total} vs AC {target_ac} (本回合无法防御！)"]
        if hit:
            weapon = self.ctx.equipment._get_equipped_weapon()
            dmg_rolls, dmg_desc = self.ctx.dice._roll_weapon_damage(weapon)
            str_mod = self._str_mod()
            if two_handed:
                str_mod = int(str_mod * 1.5)
            total_dmg = sum(dmg_rolls) + str_mod + 2
            lines.append(f"  ✓ 命中！伤害: {dmg_desc}+{str_mod}(力量)+2(全力) = {total_dmg}")
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)

    def _macro_allout_determined(self, target_ac: int = 10) -> str:
        if not self.ctx.techniques.has_technique("精准突击"):
            return "未学会「精准突击」技术"
        atk_bonus = self.ctx.derived.attack_bonus(melee=True)
        roll = self.ctx.dice.d20_roll()
        total = roll + atk_bonus + 4
        hit = total >= target_ac
        lines = [f"🎯 精准突击: d20+{atk_bonus}+4 = {total} vs AC {target_ac} (本回合无法防御！)"]
        if hit:
            lines.append(self._weapon_hit(self.ctx.equipment._get_equipped_weapon(), self._str_mod()))
        else:
            lines.append("  ✗ 未命中")
        return "\n".join(lines)
