"""
成就系统 Mixin — 成就检测、解锁、永久加成累积。
"""
from config import ACHIEVEMENTS
from .state import GameState


class _AchievementsMixin:
    """提供给 GameEngine 的成就相关方法。"""

    state: GameState
    _pending_achievements: list

    # ---- 检测与解锁 ----

    def _check_achievements(self) -> list:
        """检测并解锁已满足条件的成就，返回本次新解锁的名称列表。"""
        newly = []
        ach = self.state.achievements
        for a in ACHIEVEMENTS:
            if ach.get(a["key"]):
                continue
            if self._achievement_condition_met(a):
                ach[a["key"]] = True
                newly.append(a["name"])
        if newly:
            self._pending_achievements.extend(newly)
        return newly

    def _achievement_condition_met(self, a: dict) -> bool:
        c = a["condition"]
        t, v = c["type"], c["value"]
        s = self.state
        if t == "clicks":
            return s.stats["clicks"] >= v
        if t == "total_gold":
            return s.lifetime_gold >= v
        if t == "drops":
            return s.stats["drops"] >= v
        if t == "max_era":
            return s.max_era_index >= v
        if t == "heroes":
            return sum(1 for h in s.heroes.values() if h["level"] > 0) >= v
        if t == "hero_max_level":
            return max((h["level"] for h in s.heroes.values()), default=0) >= v
        if t == "prestiges":
            return s.stats["prestiges"] >= v
        if t == "challenges":
            return s.stats["challenges"] >= v
        if t == "total_upgrades":
            return s.stats["total_upgrades"] >= v
        return False

    # ---- 查询 / 通知 ----

    def get_achievements(self) -> list:
        """返回所有成就及其解锁状态，供 UI 展示。"""
        result = []
        for a in ACHIEVEMENTS:
            unlocked = bool(self.state.achievements.get(a["key"]))
            reward = a["reward"]
            rv = reward["value"]
            rtext = f"产出 +{rv*100:.0f}%" if reward["type"] == "dps_mult" \
                else f"点击 +{rv*100:.0f}%"
            result.append({
                "key": a["key"], "name": a["name"], "desc": a["desc"],
                "icon": a["icon"], "unlocked": unlocked, "reward": rtext,
            })
        return result

    def achievement_progress(self) -> tuple:
        """返回 (已解锁数, 总数)。"""
        total = len(ACHIEVEMENTS)
        done = sum(1 for a in ACHIEVEMENTS if self.state.achievements.get(a["key"]))
        return done, total

    def consume_pending_achievements(self) -> list:
        """取出待弹出的解锁成就名称并清空队列。"""
        pending = list(self._pending_achievements)
        self._pending_achievements.clear()
        return pending
