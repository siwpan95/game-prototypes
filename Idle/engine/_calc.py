"""
核心计算 Mixin — 装备加载、DPS/点击力计算、初始化。
P1：词条/套装、英雄主动技能、限时活动、挑战全局乘区、黄金变体。
"""
from config import (
    UPGRADE_DEFS, SKILLS, PRESTIGE_UPGRADES, HEROES, ERAS,
    MILESTONE_STEPS, ACHIEVEMENTS, GOLDEN_BUFF,
)
from .upgrade import UpgradeDef


class _CalcMixin:
    """提供给 GameEngine 的 DPS 计算和装备加载方法。"""

    state: object
    _defs: dict
    _dps_gears: list
    _era_index: int
    _skill_cooldowns: dict
    _skill_active_until: dict
    _active_dps_mult: float
    _active_click_mult: float
    _golden_buff_active: bool
    _golden_buff_remaining: float

    def _load_defs(self):
        for raw in UPGRADE_DEFS:
            d = UpgradeDef(raw)
            self._defs[d.key] = d
            if d.per_second > 0:
                self._dps_gears.append(d)
        for d in self._defs.values():
            if isinstance(d.multiplier, str):
                d.multiplier = self._defs.get(d.multiplier)
            if isinstance(d.synergy_unlocked, str):
                d.synergy_unlocked = self._defs.get(d.synergy_unlocked)
            if isinstance(d.synergy_building, str):
                d.synergy_building = self._defs.get(d.synergy_building)
            if isinstance(d.power_gear, str):
                d.power_gear = self._defs.get(d.power_gear)
            if isinstance(d.empowers, str):
                d.empowers = self._defs.get(d.empowers)

    def _init_state(self):
        for key in self._defs:
            self.state.upgrades.setdefault(key, 0)
            self.state.empowered.setdefault(key, 0)
        for sk in SKILLS:
            self._skill_cooldowns.setdefault(sk["key"], 0.0)
            self._skill_active_until.setdefault(sk["key"], 0.0)
        for pk in PRESTIGE_UPGRADES:
            self.state.prestige_upgrades.setdefault(pk["key"], 0)

    # ==================== 前置条件 ====================
    def check_prerequisite(self, defn: UpgradeDef) -> bool:
        if defn.requires is None:
            return True
        req_key, req_level = defn.requires
        return self.state.upgrades.get(req_key, 0) >= req_level

    def get_prerequisite_text(self, defn: UpgradeDef) -> str:
        if defn.requires is None:
            return ""
        req_key, req_level = defn.requires
        req_name = self._defs[req_key].name if req_key in self._defs else req_key
        if req_level == 0:
            return f"需要解锁: {req_name}"
        return f"需要: {req_name} {req_level}级"

    # ==================== 核心计算 ====================
    def _recalc(self):
        challenge = self._get_challenge()
        restrict_dps = challenge and challenge.get("restrict_dps")

        # ---- 基础 DPS ----
        dps = self._calc_base_dps(restrict_dps)

        # ---- 协同 / 力量联动 / CPS ----
        if not restrict_dps:
            dps = self._apply_synergies(dps)
            dps = self._apply_power_gear(dps)
            dps *= 1.01 ** self.state.upgrades.get("cps_multiplier", 0)

        # ---- 纪元加成 ----
        era = self.get_current_era()
        dps *= era["bonus_dps"]

        # ---- 声望加成 ----
        dps = self._apply_prestige_dps(dps)

        # ---- 技能加成 ----
        dps *= self._active_dps_mult

        # ---- 英雄加成（被动 + 词条 + 套装 + 主动技能）----
        if not restrict_dps:
            dps = self._apply_hero_dps(dps)
            dps *= self._hero_skill_dps_mult()
            dps += self._hero_skill_add_dps()

        # ---- 成就 / 黄金 / 活动 / 挑战 乘区 ----
        dps *= self._achievement_dps_mult()
        dps *= self._golden_dps_mult()
        dps *= self._event_dps_mult()
        dps *= self._challenge_global_dps_mult()

        self.state.dps = dps

        # ---- 点击力 ----
        self.state.click_power = self._calc_click_power(dps, era, challenge)

    def _calc_base_dps(self, restrict_dps: bool) -> float:
        """计算基础 DPS（不含协同/纪元/声望/技能/英雄加成）。"""
        if restrict_dps:
            return 0.0
        base = 0.0
        for d in self._dps_gears:
            qty = self.state.upgrades[d.key]
            if qty <= 0:
                continue
            mult = 2 ** self.state.upgrades.get(d.multiplier.key, 0) if d.multiplier else 1
            emp_pow = self.state.empowered.get(d.key, 0)
            ms = self._milestone_mult(d.key, qty)
            base += d.per_second * qty * mult * (2 ** emp_pow) * ms
        return base

    def _milestone_mult(self, key: str, qty: int) -> float:
        """里程碑倍率：拥有数量达到阈值时放大该建筑的产出。"""
        best = 1.0
        for count, factor in MILESTONE_STEPS:
            if qty >= count and factor > best:
                best = factor
        return best

    def _apply_synergies(self, base_dps: float) -> float:
        """应用协同效应加成。"""
        result = base_dps
        for d in self._defs.values():
            if d.synergy_unlocked and d.synergy_building:
                unlock_qty = self.state.upgrades.get(d.synergy_unlocked.key, 0)
                if unlock_qty > 0:
                    my_qty = self.state.upgrades.get(d.key, 0)
                    partner_qty = self.state.upgrades.get(d.synergy_building.key, 0)
                    result += my_qty * partner_qty * 0.05 * base_dps
        return result

    def _apply_power_gear(self, base_dps: float) -> float:
        """应用力量联动加成。"""
        result = base_dps
        for d in self._defs.values():
            if d.power_gear and d.empowers:
                my_qty = self.state.upgrades.get(d.key, 0)
                if my_qty <= 0:
                    continue
                src_qty = self.state.upgrades.get(d.power_gear.key, 0)
                tgt_qty = self.state.upgrades.get(d.empowers.key, 0)
                if src_qty > 0 and tgt_qty > 0:
                    result += src_qty * tgt_qty * base_dps * 0.05
        return result

    def _apply_prestige_dps(self, dps: float) -> float:
        """应用声望 DPS 加成。"""
        result = dps
        for pdef in PRESTIGE_UPGRADES:
            lv = self.state.prestige_upgrades.get(pdef["key"], 0)
            if lv > 0 and pdef["effect_type"] == "dps_mult":
                result *= 1 + (pdef["effect_per_level"] * lv)
        return result

    def _apply_hero_dps(self, dps: float) -> float:
        """应用英雄 DPS 加成（被动 + 装备词条/套装 + 平铺 bonus）。"""
        result = dps
        for hero_key, hstate in self.state.heroes.items():
            hdef = self.get_hero_info(hero_key)
            if hdef and hstate["level"] > 0:
                bonus = hdef.get("passive_dps_bonus", 0)
                if bonus:
                    result *= 1 + (bonus * hstate["level"])
                # 词条/套装 DPS 乘区
                result *= self._hero_affix_factor(hstate, "dps_pct")
                result *= self._hero_affix_factor(hstate, "all_pct")
                # 平铺 bonus（旧式加成，仍保留）
                for eq in hstate.get("equipped", {}).values():
                    if eq:
                        result += eq.get("bonus", 0)
        return result

    def _calc_click_power(self, dps: float, era: dict, challenge) -> float:
        """计算点击力。"""
        challenge_restrict_click = challenge and challenge.get("restrict_click")
        if challenge_restrict_click:
            return 0

        cp = 1.0
        cp += self.state.upgrades.get("clicker", 0)
        cp += self.state.upgrades.get("mobster", 0) * sum(
            self.state.upgrades[d.key] for d in self._dps_gears
        )
        cp += self.state.upgrades.get("cps_to_click", 0) * 0.01 * dps
        cp *= 2 ** self.state.upgrades.get("click_booster", 0)

        if self._golden_buff_active:
            cp *= GOLDEN_BUFF["strength"]

        cp *= era["bonus_click"]

        for pdef in PRESTIGE_UPGRADES:
            lv = self.state.prestige_upgrades.get(pdef["key"], 0)
            if lv > 0 and pdef["effect_type"] == "click_mult":
                cp *= 1 + (pdef["effect_per_level"] * lv)

        cp *= self._active_click_mult

        for hero_key, hstate in self.state.heroes.items():
            hdef = self.get_hero_info(hero_key)
            if hdef and hstate["level"] > 0:
                bonus = hdef.get("passive_click_bonus", 0)
                if bonus:
                    cp *= 1 + (bonus * hstate["level"])
                cp *= self._hero_affix_factor(hstate, "click_pct")
                cp *= self._hero_affix_factor(hstate, "all_pct")

        # ---- 成就 / 黄金 / 活动 / 挑战 乘区 ----
        cp *= self._achievement_click_mult()
        cp *= self._golden_click_mult()
        cp *= self._hero_skill_click_mult()
        cp *= self._event_click_mult()
        cp *= self._challenge_global_click_mult()

        return int(cp)

    def _achievement_dps_mult(self) -> float:
        m = 1.0
        for a in ACHIEVEMENTS:
            if self.state.achievements.get(a["key"]):
                if a["reward"]["type"] == "dps_mult":
                    m *= (1 + a["reward"]["value"])
        return m

    def _achievement_click_mult(self) -> float:
        m = 1.0
        for a in ACHIEVEMENTS:
            if self.state.achievements.get(a["key"]):
                if a["reward"]["type"] == "click_mult":
                    m *= (1 + a["reward"]["value"])
        return m

    def _golden_dps_mult(self) -> float:
        if not self._golden_buff_active:
            return 1.0
        v = self._golden_variant_def()
        if v and v["effect_type"] == "dps_mult":
            return v["value"] * self._golden_power_factor()
        return 1.0

    def _golden_click_mult(self) -> float:
        if not self._golden_buff_active:
            return 1.0
        v = self._golden_variant_def()
        if v and v["effect_type"] == "click_mult":
            return v["value"] * self._golden_power_factor()
        return 1.0

    def _golden_power_factor(self) -> float:
        lv = self.state.upgrades.get("golden_power", 0)
        return 1 + 0.25 * lv

    def _golden_variant_def(self) -> dict | None:
        return self._golden_variant
