"""
Achievement System for Russian Roulette.
Tracks stats and unlocks achievements.
"""

from typing import Dict, List, Optional


ALL_ACHIEVEMENTS = {
    "first_shot": {
        "name": "初次开火",
        "desc": "发射了第一发子弹",
        "icon": "🔫",
    },
    "first_win": {
        "name": "首胜",
        "desc": "赢得第一场游戏",
        "icon": "🏆",
    },
    "first_death": {
        "name": "初次阵亡",
        "desc": "第一次被击杀",
        "icon": "💀",
    },
    "survivor_3": {
        "name": "幸存者",
        "desc": "在一局中幸存3个回合以上",
        "icon": "🛡️",
    },
    "blank_5": {
        "name": "哑弹之王",
        "desc": "连续打出5发空包弹",
        "icon": "😎",
    },
    "blank_10": {
        "name": "完全无害",
        "desc": "连续打出10发空包弹",
        "icon": "🌿",
    },
    "shots_10": {
        "name": "枪林弹雨",
        "desc": "累计开枪10次",
        "icon": "🔥",
    },
    "shots_50": {
        "name": "弹尽粮绝",
        "desc": "累计开枪50次",
        "icon": "⚔️",
    },
    "opponent_5": {
        "name": "冷血杀手",
        "desc": "朝对手开枪5次",
        "icon": "🎯",
    },
    "self_5": {
        "name": "自残达人",
        "desc": "朝自己开枪5次",
        "icon": "🤕",
    },
    "spinner": {
        "name": "旋转大师",
        "desc": "单局旋转弹巢3次",
        "icon": "🌀",
    },
    "speed_win": {
        "name": "闪电战",
        "desc": "在3回合内获胜",
        "icon": "⚡",
    },
    "explosion_survivor": {
        "name": "炸膛幸存者",
        "desc": "炸膛时对手死亡，你幸存",
        "icon": "🧨",
    },
    "explosion_victim": {
        "name": "自爆狂魔",
        "desc": "因炸膛而死亡",
        "icon": "💥",
    },
    "critical_fail_2": {
        "name": "倒霉蛋",
        "desc": "连续两次大失败",
        "icon": "🍂",
    },
    "critical_success_2": {
        "name": "天选之子",
        "desc": "连续两次大成功",
        "icon": "🌟",
    },
    "perfect_game": {
        "name": "完美游戏",
        "desc": "一枪未开就赢（对手炸膛）",
        "icon": "✨",
    },
    "krieg_mode": {
        "name": "战争之王",
        "desc": "一局游戏开枪超过10次",
        "icon": "💣",
    },
}


class AchievementManager:
    def __init__(self):
        self.unlocked: Dict[str, bool] = {}
        self.newly_unlocked: List[str] = []
        self.stats: Dict[str, int] = {
            "shots_fired": 0,
            "shots_at_opponent": 0,
            "shots_at_self": 0,
            "live_shots_hit_self": 0,
            "live_shots_hit_opponent": 0,
            "blank_shots": 0,
            "consecutive_blanks": 0,
            "max_consecutive_blanks": 0,
            "spins": 0,
            "wins": 0,
            "losses": 0,
            "turns_survived": 0,
            "shots_this_game": 0,
            "crit_fails": 0,
            "crit_successes": 0,
            "consecutive_crit_fails": 0,
            "consecutive_crit_successes": 0,
            "explosions_triggered": 0,
            "games_played": 0,
        }

    def reset_per_game(self):
        """Reset per-game stats (keeps totals)."""
        self.stats["consecutive_blanks"] = 0
        self.stats["spins"] = 0
        self.stats["shots_this_game"] = 0
        self.stats["consecutive_crit_fails"] = 0
        self.stats["consecutive_crit_successes"] = 0
        self.newly_unlocked = []

    def check_all(self, turn_number: int = 0) -> List[str]:
        """Check all achievements. Returns list of newly unlocked."""
        s = self.stats
        u = self.unlocked

        # first_shot
        if s["shots_fired"] >= 1 and not u.get("first_shot"):
            self._unlock("first_shot")

        # first_win
        if s["wins"] >= 1 and not u.get("first_win"):
            self._unlock("first_win")

        # first_death
        if s["losses"] >= 1 and not u.get("first_death"):
            self._unlock("first_death")

        # survivor_3
        if s["turns_survived"] >= 3 and not u.get("survivor_3"):
            self._unlock("survivor_3")

        # blank_5 / blank_10
        if s["max_consecutive_blanks"] >= 5 and not u.get("blank_5"):
            self._unlock("blank_5")
        if s["max_consecutive_blanks"] >= 10 and not u.get("blank_10"):
            self._unlock("blank_10")

        # shots_10 / shots_50
        if s["shots_fired"] >= 10 and not u.get("shots_10"):
            self._unlock("shots_10")
        if s["shots_fired"] >= 50 and not u.get("shots_50"):
            self._unlock("shots_50")

        # opponent_5
        if s["shots_at_opponent"] >= 5 and not u.get("opponent_5"):
            self._unlock("opponent_5")

        # self_5
        if s["shots_at_self"] >= 5 and not u.get("self_5"):
            self._unlock("self_5")

        # spinner (checked from outside with per-game spins)
        if s["spins"] >= 3 and not u.get("spinner"):
            self._unlock("spinner")

        # speed_win
        if s["wins"] >= 1 and turn_number <= 3 and not u.get("speed_win"):
            self._unlock("speed_win")

        # krieg_mode
        if s["shots_this_game"] >= 10 and not u.get("krieg_mode"):
            self._unlock("krieg_mode")

        return self.newly_unlocked

    def _unlock(self, key: str):
        if not self.unlocked.get(key):
            self.unlocked[key] = True
            self.newly_unlocked.append(key)

    def get_newly_unlocked(self) -> List[str]:
        result = self.newly_unlocked[:]
        self.newly_unlocked = []
        return result

    def get_unlocked_list(self) -> List[Dict]:
        return [
            ALL_ACHIEVEMENTS[k]
            for k, v in self.unlocked.items() if v
        ]

    def record_shot(self, bullet_type: str, target: str, died: bool):
        """Record a shot event."""
        s = self.stats
        s["shots_fired"] += 1
        s["shots_this_game"] += 1

        if bullet_type == "blank":
            s["blank_shots"] += 1
            s["consecutive_blanks"] += 1
            s["max_consecutive_blanks"] = max(
                s["max_consecutive_blanks"], s["consecutive_blanks"]
            )
        else:
            s["consecutive_blanks"] = 0

        if target == "opponent":
            s["shots_at_opponent"] += 1
            if bullet_type == "live" and died:
                s["live_shots_hit_opponent"] += 1
        else:
            s["shots_at_self"] += 1
            if bullet_type == "live" and died:
                s["live_shots_hit_self"] += 1

    def record_spin(self):
        self.stats["spins"] += 1

    def record_crit(self, label: str):
        """Record a crit result for tracking consecutive crits."""
        s = self.stats
        if label == "critical_fail":
            s["crit_fails"] += 1
            s["consecutive_crit_fails"] += 1
            s["consecutive_crit_successes"] = 0
            if s["consecutive_crit_fails"] >= 2 and not s.get("critical_fail_2_unlocked"):
                self._unlock("critical_fail_2")
                s["critical_fail_2_unlocked"] = True
        elif label == "critical_success":
            s["crit_successes"] += 1
            s["consecutive_crit_successes"] += 1
            s["consecutive_crit_fails"] = 0
            if s["consecutive_crit_successes"] >= 2 and not s.get("critical_success_2_unlocked"):
                self._unlock("critical_success_2")
                s["critical_success_2_unlocked"] = True
        else:
            s["consecutive_crit_fails"] = 0
            s["consecutive_crit_successes"] = 0

    def record_explosion(self, survived: bool):
        s = self.stats
        s["explosions_triggered"] += 1
        if survived and not s.get("explosion_survivor_unlocked"):
            self._unlock("explosion_survivor")
            s["explosion_survivor_unlocked"] = True
        elif not survived and not s.get("explosion_victim_unlocked"):
            self._unlock("explosion_victim")
            s["explosion_victim_unlocked"] = True

    def record_win(self, turn_number: int):
        s = self.stats
        s["wins"] += 1
        s["games_played"] += 1
        if turn_number <= 3:
            # speed_win checked in check_all
            pass

    def record_loss(self):
        s = self.stats
        s["losses"] += 1
        s["games_played"] += 1

    def record_turn_survived(self):
        self.stats["turns_survived"] += 1
