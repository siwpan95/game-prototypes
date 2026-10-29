"""
技能系统 Mixin — 技能查询、激活、冷却管理。
"""
from config import SKILLS
from .types import SkillDef


class _SkillsMixin:
    """提供给 GameEngine 的技能相关方法。"""

    state: object
    _skill_cooldowns: dict
    _skill_active_until: dict
    _crit_charges: int
    _crit_mult: float
    _auto_click_remaining: float
    _auto_click_rate: float
    _active_dps_mult: float
    _active_click_mult: float

    def get_skills(self) -> list:
        return SKILLS

    def get_skill_info(self, key: str) -> SkillDef | None:
        """公开查询技能定义。"""
        for sk in SKILLS:
            if sk["key"] == key:
                return sk
        return None

    def can_activate_skill(self, skill_key: str) -> bool:
        sk = self.get_skill_info(skill_key)
        if not sk:
            return False
        if not self.is_era_unlocked(sk["era"]):
            return False
        return self._skill_cooldowns.get(skill_key, 0) <= 0

    def get_skill_cooldown(self, skill_key: str) -> float:
        return self._skill_cooldowns.get(skill_key, 0)

    def get_skill_active_remaining(self, skill_key: str) -> float:
        return self._skill_active_until.get(skill_key, 0)

    def activate_skill(self, skill_key: str) -> str | None:
        sk = self.get_skill_info(skill_key)
        if not sk:
            return "未知技能"
        if not self.is_era_unlocked(sk["era"]):
            return "纪元未解锁"
        if self._skill_cooldowns.get(skill_key, 0) > 0:
            return "冷却中"
        if self._skill_active_until.get(skill_key, 0) > 0:
            return "技能仍在生效"

        et = sk["effect_type"]
        if et == "instant_dps":
            gain = self.state.dps * sk["effect_value"]
            self.state.gold += gain
            self.state.total_gold += gain
            self.state.lifetime_gold += gain
        elif et == "dps_mult":
            self._active_dps_mult = sk["effect_value"]
            self._skill_active_until[skill_key] = sk.get("duration", 10)
            self._recalc()
        elif et == "crit_clicks":
            self._crit_charges = sk["charges"]
            self._crit_mult = sk["effect_value"]
            self._skill_active_until[skill_key] = 999
        elif et == "auto_click":
            self._auto_click_rate = sk["effect_value"]
            self._auto_click_remaining = sk.get("duration", 10)
            self._skill_active_until[skill_key] = sk.get("duration", 10)
        elif et == "combo":
            self._active_click_mult = sk["click_mult"]
            self._active_dps_mult = sk["dps_mult"]
            self._skill_active_until[skill_key] = sk.get("duration", 10)
            self._recalc()

        cd = sk["cooldown"]
        cd_lv = self.state.prestige_upgrades.get("p_cooldown", 0)
        cd *= (1 - 0.1 * cd_lv)
        self._skill_cooldowns[skill_key] = cd

        return None

    def _deactivate_skill(self, skill_key: str):
        sk = self.get_skill_info(skill_key)
        if not sk:
            return
        et = sk["effect_type"]
        if et == "dps_mult":
            self._active_dps_mult = 1.0
            self._recalc()
        elif et == "crit_clicks":
            self._crit_charges = 0
            self._crit_mult = 1.0
        elif et == "auto_click":
            self._auto_click_remaining = 0
            self._auto_click_rate = 0.0
        elif et == "combo":
            self._active_click_mult = 1.0
            self._active_dps_mult = 1.0
            self._recalc()
