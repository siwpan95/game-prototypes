# director.py — AI Director 动态难度调节器
#
# 设计依据（联网检索）：《死亡细胞》的 AI Director（参考 L4D 的 AI Director）
# 根据玩家近期表现「橡皮筋式」动态调节节奏——玩家吃瘪就放宽（少刷怪、降伤、
# 多掉好货），玩家顺风顺水就加压（多刷怪、增压、略减掉落）。目标不是公平，
# 而是「难但公平，想再来一局」。
#
# 本实现为纯数据 + 轻量调节，不持有游戏对象，便于存档与单测。
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Director:
    # —— 可观测指标 ——
    kills: int = 0
    deaths: int = 0
    floors_cleared: int = 0
    steps: int = 0
    # struggle：玩家「吃瘪指数」，>=0。承伤/死亡拉高，击杀/清层/休息拉低。
    struggle: float = 0.0
    # challenge：玩家「碾压指数」，>=0。击杀多且几乎无伤则升高。
    challenge: float = 0.0

    def on_damage(self, amount: int) -> None:
        self.struggle += max(0, amount) * 0.02
        self.challenge = max(0.0, self.challenge - 0.02)

    def on_kill(self) -> None:
        self.kills += 1
        self.struggle = max(0.0, self.struggle - 0.06)
        self.challenge += 0.04

    def on_floor_cleared(self) -> None:
        self.floors_cleared += 1
        self.struggle = max(0.0, self.struggle - 0.35)
        self.challenge += 0.10

    def on_death(self) -> None:
        self.deaths += 1
        self.struggle += 1.2
        self.challenge = 0.0

    def on_rest(self) -> None:
        self.struggle = max(0.0, self.struggle - 0.25)

    def on_step(self) -> None:
        self.steps += 1
        # 缓慢自然衰减，避免历史包袱无限累积
        self.struggle = max(0.0, self.struggle - 0.002)
        self.challenge = max(0.0, self.challenge - 0.001)

    # ──────────────────────────────────────────────────────
    #  难度调节输出
    # ──────────────────────────────────────────────────────
    def _ease(self) -> float:
        """0..1：玩家越吃瘪，ease 越大（越放宽）。"""
        return min(1.0, self.struggle / 3.0)

    def _pressure(self) -> float:
        """0..1：玩家越碾压，pressure 越大（越加压）。"""
        return min(1.0, self.challenge / 2.0)

    def monster_count_mult(self) -> float:
        e, p = self._ease(), self._pressure()
        return max(0.6, 1.0 - 0.30 * e + 0.25 * p)

    def monster_dmg_mult(self) -> float:
        e, p = self._ease(), self._pressure()
        return max(0.6, 1.0 - 0.25 * e + 0.20 * p)

    def trap_mult(self) -> float:
        e = self._ease()
        return max(0.5, 1.0 - 0.35 * e)

    def loot_quality_mult(self) -> float:
        e = self._ease()
        return 1.0 + 0.6 * e

    def sight_radius(self, base: int = 6) -> int:
        """怪物感知半径：吃瘪时略降（更易喘息），碾压时略升。"""
        e, p = self._ease(), self._pressure()
        return max(3, base - int(2 * e) + int(1 * p))

    def rarity_luck(self) -> int:
        """掉落稀有度幸运加成（吃瘪时 +1 档）。"""
        return 1 if self._ease() > 0.5 else 0

    def snapshot(self) -> dict:
        return {
            "kills": self.kills, "deaths": self.deaths,
            "floors_cleared": self.floors_cleared, "steps": self.steps,
            "struggle": round(self.struggle, 3),
            "challenge": round(self.challenge, 3),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Director":
        return cls(
            kills=d.get("kills", 0), deaths=d.get("deaths", 0),
            floors_cleared=d.get("floors_cleared", 0),
            steps=d.get("steps", 0),
            struggle=d.get("struggle", 0.0),
            challenge=d.get("challenge", 0.0),
        )
