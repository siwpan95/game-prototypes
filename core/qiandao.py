"""
签到核心逻辑
从 qiandao.pyw 提取，修复了 c 不增长的 bug，增加持久化和每日签到限制

v2 增强（基于行为设计研究）：
- 软/硬保底系统：借鉴原神抽卡设计 —— 连续无奖励达到软保底阈值后概率显著爬升，
  达到硬保底阈值时 100% 出奖，消除极端坏运气（玩家最容易流失的时刻）
- 连胜冻结（Streak Freeze）：借鉴 Duolingo —— 漏签 1 天可自动消耗冻结卡保住连胜；
  研究表明有冻结机制的产品用户平均连胜时长高 48%
- 最长连胜纪录 & 里程碑成就
"""
import json
import os
import math
import random
from datetime import datetime, date

from .achievements import check_new_milestones


DEFAULT_GLOBAL = {
    "alpha_min": 0.03,
    "alpha_max": 0.35,
    "lam_n": 0.04,
    "gamma_c": 0.025,
    "reward_lam_n": 0.04,
    "reward_gamma_c": 0.02,
}

# ── 保底参数（可被 rewards.json 的 global 覆盖）────────────────
SOFT_PITY_START = 4    # 第 4 次无奖励起，概率开始额外爬升
SOFT_PITY_BOOST = 0.13 # 软保底区每多失败一次，追加的概率
HARD_PITY = 7          # 连续 6 次无奖励后，第 7 次必得奖励

# ── 连胜冻结参数 ──────────────────────────────────────────────
FREEZE_MAX = 2             # 最多持有 2 张（Duolingo 同款上限）
FREEZE_EARN_EVERY = 7      # 每连续签到 7 天奖励 1 张


def reinforcement_prob(n, c, g=None):
    """计算强化概率"""
    g = g or DEFAULT_GLOBAL
    a_min = g.get("alpha_min", 0.03)
    a_max = g.get("alpha_max", 0.35)
    lam = g.get("lam_n", 0.04)
    gam = g.get("gamma_c", 0.025)
    return a_min + (a_max - a_min) * (1 - math.exp(-lam * n)) * (1 - math.exp(-gam * c))


def pity_adjusted_prob(base_p, no_reward_streak, g=None):
    """
    应用软/硬保底后的实际概率。
    no_reward_streak: 本次签到之前已连续无奖励的次数
    返回 (概率, 是否处于软保底区, 是否硬保底)
    """
    g = g or {}
    soft_start = g.get("soft_pity_start", SOFT_PITY_START)
    soft_boost = g.get("soft_pity_boost", SOFT_PITY_BOOST)
    hard_pity = g.get("hard_pity", HARD_PITY)

    fails = no_reward_streak
    if fails >= hard_pity - 1:
        return 1.0, True, True
    if fails >= soft_start - 1:
        boosted = base_p + (fails - soft_start + 2) * soft_boost
        return min(0.95, boosted), True, False
    return base_p, False, False


def choose_reward(n, c, rewards, g=None):
    """根据权重选择奖励"""
    g = g or DEFAULT_GLOBAL
    if not rewards:
        return {"name": "神秘奖励", "base": 1.0, "gamma": 0.02, "delta": 0.04,
                "category": "", "rarity": "普通", "description": "奖励池为空时的兜底奖励"}
    r_lam = g.get("reward_lam_n", 0.04)
    r_gam = g.get("reward_gamma_c", 0.02)
    weights = []
    items = []
    for rw in rewards:
        base = rw["base"]
        gamma = rw.get("gamma", r_gam)
        delta = rw.get("delta", r_lam)
        w = base * (1 - math.exp(-gamma * c)) * (1 - math.exp(-delta * n))
        weights.append(w)
        items.append(rw)
    chosen = random.choices(items, weights=weights, k=1)[0]
    return chosen


def load_rewards_config(qiandao_dir):
    """从签到目录加载奖励配置"""
    json_path = os.path.join(qiandao_dir, "rewards.json")
    g = dict(DEFAULT_GLOBAL)
    rewards = []

    if not os.path.exists(json_path):
        return g, rewards

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        if "global" in data:
            g.update(data["global"])
        raw = data.get("rewards", [])
        if not raw:
            for name, p in data.items():
                if name == "global":
                    continue
                rewards.append({
                    "name": name, "base": p["base"],
                    "gamma": p.get("gamma", g["reward_gamma_c"]),
                    "delta": p.get("delta", g["reward_lam_n"]),
                    "category": "", "rarity": "普通", "description": "",
                })
            return g, rewards
        for rw in raw:
            rewards.append({
                "name": rw["name"], "base": rw["base"],
                "gamma": rw.get("gamma", g["reward_gamma_c"]),
                "delta": rw.get("delta", g["reward_lam_n"]),
                "category": rw.get("category", ""),
                "rarity": rw.get("rarity", "普通"),
                "description": rw.get("description", ""),
            })
    elif isinstance(data, list):
        for rw in data:
            rewards.append({
                "name": rw["name"], "base": rw["base"],
                "gamma": rw.get("gamma", g["reward_gamma_c"]),
                "delta": rw.get("delta", g["reward_lam_n"]),
                "category": rw.get("category", ""),
                "rarity": rw.get("rarity", "普通"),
                "description": rw.get("description", ""),
            })
    return g, rewards


class QiandaoState:
    """签到状态：持久化 n（总次数）、c（连续天数）、历史记录"""

    def __init__(self, qiandao_dir):
        self.qiandao_dir = qiandao_dir
        self.history_path = os.path.join(qiandao_dir, "qiandao_history.json")
        self.state_path = os.path.join(qiandao_dir, "qiandao_state.json")
        self.g, self.rewards = load_rewards_config(qiandao_dir)
        self.n = 0
        self.c = 0
        self.no_reward_streak = 0
        self.last_sign_date = None
        self.history = []
        self.last_result = None
        # v2 新增状态
        self.freezes = 1               # 连胜冻结卡（新玩家送 1 张）
        self.best_c = 0                # 历史最长连胜
        self.milestones = set()        # 已解锁里程碑 id

        self._load_state()
        self._load_history()

    def _load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                self.n = s.get("n", 0)
                self.c = s.get("c", 0)
                self.no_reward_streak = s.get("no_reward_streak", 0)
                self.last_sign_date = s.get("last_sign_date", None)
                self.freezes = s.get("freezes", 1)
                self.best_c = s.get("best_c", self.c)
                self.milestones = set(s.get("milestones", []))
            except Exception:
                pass

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({
                "n": self.n,
                "c": self.c,
                "no_reward_streak": self.no_reward_streak,
                "last_sign_date": self.last_sign_date,
                "freezes": self.freezes,
                "best_c": self.best_c,
                "milestones": sorted(self.milestones),
            }, f, ensure_ascii=False, indent=2)

    def _load_history(self):
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []

    def _save_history(self):
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def _add_history(self, p, reinforced, reward_name, rarity):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not reinforced:
            if self.history and not self.history[-1].get("reinforced", True):
                last = self.history[-1]
                last["n_end"] = self.n
                last["time"] = now
                last["prob"] = f"{p:.2%}"
                last["no_streak"] = last.get("no_streak", 1) + 1
                last["result"] = f"连续{last['no_streak']}次无奖励"
                last["reward"] = ""
                last["rarity"] = ""
            else:
                self.history.append({
                    "time": now, "n": self.n, "n_end": self.n,
                    "streak_c": self.c, "prob": f"{p:.2%}",
                    "result": "1次无奖励", "reward": "", "rarity": "",
                    "reinforced": False, "no_streak": 1,
                })
        else:
            self.history.append({
                "time": now, "n": self.n, "n_end": self.n,
                "streak_c": self.c, "prob": f"{p:.2%}",
                "result": "获得奖励", "reward": reward_name, "rarity": rarity,
                "reinforced": True, "no_streak": 0,
            })
        self._save_history()

    def can_sign_today(self):
        today = date.today().isoformat()
        return self.last_sign_date != today

    @property
    def pity_info(self):
        """当前保底状态：(已失败次数, 硬保底阈值, 是否软保底区)"""
        hard = self.g.get("hard_pity", HARD_PITY)
        soft = self.g.get("soft_pity_start", SOFT_PITY_START)
        return self.no_reward_streak, hard, self.no_reward_streak >= soft - 1

    def current_prob(self):
        """下一次签到的实际概率（含保底加成）"""
        base = reinforcement_prob(self.n, self.c, self.g)
        p, _, _ = pity_adjusted_prob(base, self.no_reward_streak, self.g)
        return p

    def get_stats(self):
        """统计数据（供统计面板使用）"""
        reward_count = sum(1 for h in self.history if h.get("reinforced"))
        no_count = sum(h.get("no_streak", 1) for h in self.history
                       if not h.get("reinforced"))
        rarity_dist = {}
        for h in self.history:
            if h.get("reinforced"):
                r = h.get("rarity", "普通") or "普通"
                rarity_dist[r] = rarity_dist.get(r, 0) + 1
        total_pulls = reward_count + no_count
        return {
            "n": self.n,
            "c": self.c,
            "best_c": max(self.best_c, self.c),
            "reward_count": reward_count,
            "reward_rate": reward_count / total_pulls if total_pulls else 0.0,
            "rarity_dist": rarity_dist,
            "freezes": self.freezes,
            "milestones_unlocked": len(self.milestones),
        }

    def sign_dates(self):
        """所有签到日期集合（'YYYY-MM-DD'），供热力图使用"""
        dates = set()
        for h in self.history:
            t = h.get("time", "")
            if len(t) >= 10:
                dates.add(t[:10])
        if self.last_sign_date:
            dates.add(self.last_sign_date)
        return dates

    def sign(self):
        """执行签到，返回结果 dict"""
        today = date.today().isoformat()
        freeze_used = False

        # ── 连胜判定（含 Duolingo 式冻结保护）──
        if self.last_sign_date:
            last = date.fromisoformat(self.last_sign_date)
            delta = (date.today() - last).days
            if delta == 2 and self.freezes > 0:
                # 恰好漏签 1 天 → 消耗冻结卡保住连胜
                self.freezes -= 1
                freeze_used = True
            elif delta > 1:
                self.c = 0

        self.n += 1
        self.c += 1
        self.last_sign_date = today

        # 更新最长连胜
        if self.c > self.best_c:
            self.best_c = self.c

        # 每连续 7 天奖励 1 张冻结卡（上限 2）
        freeze_earned = False
        if self.c > 0 and self.c % FREEZE_EARN_EVERY == 0 and self.freezes < FREEZE_MAX:
            self.freezes += 1
            freeze_earned = True

        # ── 概率计算（基础曲线 + 软/硬保底）──
        base_p = reinforcement_prob(self.n, self.c, self.g)
        p, in_soft_pity, hard_hit = pity_adjusted_prob(
            base_p, self.no_reward_streak, self.g)

        # ── 里程碑检查 ──
        new_milestones = check_new_milestones(self.n, self.c, self.milestones)

        common = {
            "prob": p,
            "base_prob": base_p,
            "n": self.n,
            "c": self.c,
            "freeze_used": freeze_used,
            "freeze_earned": freeze_earned,
            "pity_triggered": hard_hit,
            "in_soft_pity": in_soft_pity,
            "milestones": new_milestones,
        }

        if random.random() < p:
            self.no_reward_streak = 0
            rw = choose_reward(self.n, self.c, self.rewards, self.g)
            self._add_history(p, True, rw["name"], rw.get("rarity", "普通"))
            self._save_state()
            self.last_result = {
                "reinforced": True, "reward": rw,
                "no_reward_streak": 0, **common,
            }
        else:
            self.no_reward_streak += 1
            self._add_history(p, False, None, "")
            self._save_state()
            self.last_result = {
                "reinforced": False, "reward": None,
                "no_reward_streak": self.no_reward_streak, **common,
            }
        return self.last_result
