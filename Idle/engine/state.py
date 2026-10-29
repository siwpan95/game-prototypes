"""
游戏状态 — dataclass，可序列化/反序列化，存档兼容。
"""

import time
from dataclasses import dataclass, field


@dataclass
class GameState:
    gold: float = 0.0
    total_gold: float = 0.0
    dps: float = 0.0
    click_power: float = 1.0
    upgrades: dict = field(default_factory=dict)
    empowered: dict = field(default_factory=dict)
    last_tick: float = 0.0
    prestige_points: int = 0
    prestige_upgrades: dict = field(default_factory=dict)
    active_challenge: str | None = None
    challenge_start_time: float = 0.0
    challenge_completed: bool = False
    heroes: dict = field(default_factory=dict)
    equipment_inventory: list = field(default_factory=list)

    # ---- P0 新增：永久/累积字段（转生时保留）----
    lifetime_gold: float = 0.0          # 有史以来累计获得金币（用于金币类成就）
    max_era_index: int = 0              # 抵达过的最高纪元下标
    achievements: dict = field(default_factory=dict)  # key -> 解锁时间
    stats: dict = field(default_factory=lambda: {
        "clicks": 0, "drops": 0, "prestiges": 0,
        "challenges": 0, "total_upgrades": 0,
    })
    daily_last_date: str = ""           # 上次领取每日奖励的日期
    daily_streak: int = 0               # 当前连续登录天数
    daily_claimed_date: str = ""        # 今天是否已领取（按日期去重）
    last_save_ts: float = 0.0           # 上次存档的墙上时钟（离线收益用）

    # ---- P1：日常任务（独立于每日登录连击）----
    daily_tasks: dict = field(default_factory=dict)   # task_key -> 是否已领取
    daily_tasks_date: str = ""          # 当前任务集所属日期
    daily_clicks: int = 0               # 今日点击次数
    daily_upgrades: int = 0             # 今日购买升级次数
    daily_challenges: int = 0           # 今日完成挑战次数

    # ---- P1：限时活动（调度状态，持久化以便恢复）----
    event_key: str | None = None        # 当前活动 key
    event_remaining: float = 0.0        # 当前活动剩余时间
    event_gap: float = 0.0              # 距下一活动的时间

    # ---- P2：统计页面（持久化）----
    play_time: float = 0.0              # 累计游戏时长（秒）
    era_first_times: dict = field(default_factory=dict)  # 纪元下标 -> 首次达成时间戳

    def to_dict(self) -> dict:
        return {
            "gold": self.gold,
            "total_gold": self.total_gold,
            "dps": self.dps,
            "click_power": self.click_power,
            "upgrades": dict(self.upgrades),
            "empowered": dict(self.empowered),
            "prestige_points": self.prestige_points,
            "prestige_upgrades": dict(self.prestige_upgrades),
            "active_challenge": self.active_challenge,
            "challenge_start_time": self.challenge_start_time,
            "challenge_completed": self.challenge_completed,
            "heroes": dict(self.heroes),
            "equipment_inventory": list(self.equipment_inventory),
            "lifetime_gold": self.lifetime_gold,
            "max_era_index": self.max_era_index,
            "achievements": dict(self.achievements),
            "stats": dict(self.stats),
            "daily_last_date": self.daily_last_date,
            "daily_streak": self.daily_streak,
            "daily_claimed_date": self.daily_claimed_date,
            "daily_tasks": dict(self.daily_tasks),
            "daily_tasks_date": self.daily_tasks_date,
            "daily_clicks": self.daily_clicks,
            "daily_upgrades": self.daily_upgrades,
            "daily_challenges": self.daily_challenges,
            "event_key": self.event_key,
            "event_remaining": self.event_remaining,
            "event_gap": self.event_gap,
            "play_time": self.play_time,
            "era_first_times": dict(self.era_first_times),
            "ts": time.time(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        s = cls()
        s.gold = d.get("gold", 0)
        s.total_gold = d.get("total_gold", 0)
        s.dps = d.get("dps", 0)
        s.click_power = d.get("click_power", 1)
        s.upgrades = d.get("upgrades", {})
        s.empowered = d.get("empowered", {})
        s.prestige_points = d.get("prestige_points", 0)
        s.prestige_upgrades = d.get("prestige_upgrades", {})
        s.active_challenge = d.get("active_challenge")
        s.challenge_start_time = d.get("challenge_start_time", 0)
        s.challenge_completed = d.get("challenge_completed", False)
        s.heroes = d.get("heroes", {})
        s.equipment_inventory = d.get("equipment_inventory", [])
        s.lifetime_gold = d.get("lifetime_gold", 0.0)
        s.max_era_index = d.get("max_era_index", 0)
        s.achievements = d.get("achievements", {})
        s.stats = d.get("stats", {})
        # 补齐 stats 中可能缺失的键（向后兼容旧存档）
        for k in ("clicks", "drops", "prestiges", "challenges", "total_upgrades"):
            s.stats.setdefault(k, 0)
        s.daily_last_date = d.get("daily_last_date", "")
        s.daily_streak = d.get("daily_streak", 0)
        s.daily_claimed_date = d.get("daily_claimed_date", "")
        s.last_save_ts = d.get("ts", 0.0)
        # ---- P1 日常任务 ----
        s.daily_tasks = d.get("daily_tasks", {})
        s.daily_tasks_date = d.get("daily_tasks_date", "")
        s.daily_clicks = d.get("daily_clicks", 0)
        s.daily_upgrades = d.get("daily_upgrades", 0)
        s.daily_challenges = d.get("daily_challenges", 0)
        # ---- P1 限时活动 ----
        s.event_key = d.get("event_key")
        s.event_remaining = d.get("event_remaining", 0.0)
        s.event_gap = d.get("event_gap", 0.0)
        # ---- P2 统计 ----
        s.play_time = d.get("play_time", 0.0)
        s.era_first_times = d.get("era_first_times", {})
        # ---- P1 装备：英雄 equipped 由单件迁移为 {slot: item} 字典 ----
        for hk, hv in s.heroes.items():
            hv["equipped"] = GameState._normalize_equipped(hv.get("equipped"))
        return s

    @staticmethod
    def _normalize_equipped(eq):
        """将旧档的「单件装备」或 None 统一为 {slot: item|None} 字典。"""
        if eq is None:
            return {}
        if isinstance(eq, dict) and ("name" not in eq):
            # 已经是 slot 字典（每个值可能是 item 或 None）
            return {k: v for k, v in eq.items() if v is not None or k in ("weapon",)}
        if isinstance(eq, dict) and "name" in eq:
            # 旧档单件装备 → 放入武器槽
            return {"weapon": eq}
        return {}
