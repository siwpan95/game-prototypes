"""
日常任务 Mixin — 每日刷新、进度追踪、领取奖励（独立于每日登录连击）。
"""
from datetime import date
from config import DAILY_TASKS


class _DailyTasksMixin:
    """提供给 GameEngine 的日常任务相关方法。"""

    state: object

    def refresh_daily_tasks_if_needed(self):
        today = date.today().isoformat()
        if self.state.daily_tasks_date != today:
            self.state.daily_tasks_date = today
            self.state.daily_clicks = 0
            self.state.daily_upgrades = 0
            self.state.daily_challenges = 0
            self.state.daily_tasks = {t["key"]: False for t in DAILY_TASKS}
            self._check_achievements()

    def _daily_task_progress(self, task: dict) -> int:
        t = task["type"]
        if t == "clicks":
            return self.state.daily_clicks
        if t == "upgrades":
            return self.state.daily_upgrades
        if t == "reach_era":
            return self.state.max_era_index
        if t == "challenges":
            return self.state.daily_challenges
        if t == "equip_count":
            return sum(len(h.get("equipped", {})) for h in self.state.heroes.values())
        if t == "hero_level":
            return max((h.get("level", 0) for h in self.state.heroes.values()), default=0)
        return 0

    def get_daily_tasks(self) -> list:
        result = []
        for t in DAILY_TASKS:
            prog = self._daily_task_progress(t)
            claimed = self.state.daily_tasks.get(t["key"], False)
            done = prog >= t["target"]
            result.append({
                "key": t["key"], "name": t["name"], "desc": t["desc"],
                "target": t["target"], "progress": prog,
                "claimed": claimed, "complete": done,
                "reward": t["reward"],
            })
        return result

    def claim_daily_task(self, key: str) -> dict | str:
        task = None
        for t in DAILY_TASKS:
            if t["key"] == key:
                task = t
                break
        if task is None:
            return "未知任务"
        if self.state.daily_tasks.get(key, False):
            return "已领取"
        if self._daily_task_progress(task) < task["target"]:
            return "尚未完成"
        rw = task["reward"]
        if rw["type"] == "gold":
            self._add_gold(rw["value"])
        elif rw["type"] == "prestige":
            self.state.prestige_points += rw["value"]
        self.state.daily_tasks[key] = True
        self._recalc()
        self._check_achievements()
        return {"name": task["name"], "reward": rw}

    # ---- 计数器 ----
    def _inc_daily_clicks(self, n=1):
        self.state.daily_clicks += n

    def _inc_daily_upgrades(self, n=1):
        self.state.daily_upgrades += n

    def _inc_daily_challenges(self, n=1):
        self.state.daily_challenges += n
