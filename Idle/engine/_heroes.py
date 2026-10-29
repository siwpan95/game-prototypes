"""
英雄系统 Mixin — 英雄招募、升级、装备、主动技能。
"""
from config import HEROES
from .types import HeroDef, HeroState


class _HeroesMixin:
    """提供给 GameEngine 的英雄相关方法。"""

    state: object
    _hero_skill_cooldowns: dict
    _hero_skill_active: dict
    _hero_skill_effect: dict

    def _init_heroes(self):
        for h in HEROES:
            if h["key"] not in self.state.heroes:
                self.state.heroes[h["key"]] = {"level": 0, "equipped": {}}

    def get_heroes(self) -> list:
        return HEROES

    def get_hero_info(self, key: str) -> HeroDef | None:
        """公开查询英雄定义。"""
        for h in HEROES:
            if h["key"] == key:
                return h
        return None

    def get_hero_state(self, key: str) -> HeroState:
        return self.state.heroes.get(key, {"level": 0, "equipped": {}})

    def unlock_hero(self, key: str) -> str | None:
        hdef = self.get_hero_info(key)
        if not hdef:
            return "未知英雄"
        hstate = self.state.heroes.get(key, {"level": 0, "equipped": {}})
        if hstate["level"] > 0:
            return "已解锁"
        if self.state.gold < hdef["unlock_gold"]:
            return f"需要 {self.fmt_gold(hdef['unlock_gold'])} 金币"
        self.state.gold -= hdef["unlock_gold"]
        self.state.heroes[key] = {"level": 1, "equipped": {}}
        self._recalc()
        return None

    def upgrade_hero(self, key: str) -> str | None:
        hdef = self.get_hero_info(key)
        if not hdef:
            return "未知英雄"
        hstate = self.state.heroes.get(key, {"level": 0, "equipped": {}})
        if hstate["level"] <= 0:
            return "未解锁"
        if hstate["level"] >= hdef["max_level"]:
            return "已达最大等级"
        cost = int(hdef["upgrade_cost"] * (hdef["upgrade_mult"] ** (hstate["level"] - 1)))
        if self.state.gold < cost:
            return f"需要 {self.fmt_gold(cost)} 金币"
        self.state.gold -= cost
        self.state.heroes[key]["level"] = hstate["level"] + 1
        self._recalc()
        return None

    def get_hero_upgrade_cost(self, key: str) -> int:
        hdef = self.get_hero_info(key)
        if not hdef:
            return 0
        hstate = self.state.heroes.get(key, {"level": 0, "equipped": {}})
        if hstate["level"] <= 0:
            return hdef["unlock_gold"]
        return int(hdef["upgrade_cost"] * (hdef["upgrade_mult"] ** (hstate["level"] - 1)))

    # ==================== 主动技能 ====================

    def get_hero_skill_info(self, hero_key: str) -> dict | None:
        hstate = self.state.heroes.get(hero_key)
        if not hstate or hstate["level"] <= 0:
            return None
        hdef = self.get_hero_info(hero_key)
        return hdef.get("active_skill") if hdef else None

    def can_activate_hero_skill(self, hero_key: str) -> bool:
        sk = self.get_hero_skill_info(hero_key)
        if not sk:
            return False
        return self._hero_skill_cooldowns.get(hero_key, 0) <= 0 \
            and self._hero_skill_active.get(hero_key, 0) <= 0

    def get_hero_skill_cooldown(self, hero_key: str) -> float:
        return self._hero_skill_cooldowns.get(hero_key, 0)

    def get_hero_skill_active_remaining(self, hero_key: str) -> float:
        return self._hero_skill_active.get(hero_key, 0)

    def activate_hero_skill(self, hero_key: str) -> str | None:
        sk = self.get_hero_skill_info(hero_key)
        if not sk:
            return "英雄未解锁或无主动技能"
        if self._hero_skill_cooldowns.get(hero_key, 0) > 0:
            return "冷却中"
        if self._hero_skill_active.get(hero_key, 0) > 0:
            return "技能生效中"

        et = sk["effect_type"]
        if et == "instant_dps":
            gain = self.state.dps * sk["value"]
            self._add_gold(gain)
        elif et == "dps_mult":
            self._hero_skill_active[hero_key] = sk.get("duration", 8)
            self._hero_skill_effect[hero_key] = ("dps_mult", sk["value"])
            self._recalc()
        elif et == "click_mult":
            self._hero_skill_active[hero_key] = sk.get("duration", 10)
            self._hero_skill_effect[hero_key] = ("click_mult", sk["value"])
            self._recalc()
        elif et == "summon":
            self._hero_skill_active[hero_key] = sk.get("duration", 15)
            self._hero_skill_effect[hero_key] = ("summon", sk["value"])
            self._recalc()

        self._hero_skill_cooldowns[hero_key] = sk["cooldown"]
        return None

    def _tick_hero_skills(self, dt: float):
        changed = False
        for k in list(self._hero_skill_cooldowns.keys()):
            if self._hero_skill_cooldowns[k] > 0:
                self._hero_skill_cooldowns[k] = max(0, self._hero_skill_cooldowns[k] - dt)
        for k in list(self._hero_skill_active.keys()):
            if self._hero_skill_active[k] > 0:
                self._hero_skill_active[k] -= dt
                if self._hero_skill_active[k] <= 0:
                    self._hero_skill_active[k] = 0
                    self._hero_skill_effect.pop(k, None)
                    changed = True
        if changed:
            self._recalc()

    def _hero_skill_dps_mult(self) -> float:
        m = 1.0
        for k, (stat, val) in self._hero_skill_effect.items():
            if stat == "dps_mult":
                m *= val
        return m

    def _hero_skill_click_mult(self) -> float:
        m = 1.0
        for k, (stat, val) in self._hero_skill_effect.items():
            if stat == "click_mult":
                m *= val
        return m

    def _hero_skill_add_dps(self) -> float:
        add = 0.0
        for k, (stat, val) in self._hero_skill_effect.items():
            if stat == "summon":
                lv = self.state.heroes.get(k, {}).get("level", 0)
                add += val * lv
        return add
