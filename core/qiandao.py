"""
签到核心逻辑
从 qiandao.pyw 提取，修复了 c 不增长的 bug，增加持久化和每日签到限制
"""
import json
import os
import math
import random
from datetime import datetime, date


DEFAULT_GLOBAL = {
    "alpha_min": 0.03,
    "alpha_max": 0.35,
    "lam_n": 0.04,
    "gamma_c": 0.025,
    "reward_lam_n": 0.04,
    "reward_gamma_c": 0.02,
}


def reinforcement_prob(n, c, g=None):
    """计算强化概率"""
    g = g or DEFAULT_GLOBAL
    a_min = g.get("alpha_min", 0.03)
    a_max = g.get("alpha_max", 0.35)
    lam = g.get("lam_n", 0.04)
    gam = g.get("gamma_c", 0.025)
    return a_min + (a_max - a_min) * (1 - math.exp(-lam * n)) * (1 - math.exp(-gam * c))


def choose_reward(n, c, rewards, g=None):
    """根据权重选择奖励"""
    g = g or DEFAULT_GLOBAL
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
            except Exception:
                pass

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({
                "n": self.n,
                "c": self.c,
                "no_reward_streak": self.no_reward_streak,
                "last_sign_date": self.last_sign_date,
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

    def sign(self):
        """执行签到，返回结果 dict"""
        today = date.today().isoformat()

        if self.last_sign_date:
            last = date.fromisoformat(self.last_sign_date)
            today_date = date.today()
            delta = (today_date - last).days
            if delta > 1:
                self.c = 0
        elif self.last_sign_date is None:
            pass

        self.n += 1
        self.c += 1
        self.last_sign_date = today

        p = reinforcement_prob(self.n, self.c, self.g)

        if random.random() < p:
            self.no_reward_streak = 0
            rw = choose_reward(self.n, self.c, self.rewards, self.g)
            reward_name = rw["name"]
            rarity = rw.get("rarity", "普通")
            self._add_history(p, True, reward_name, rarity)
            self._save_state()
            self.last_result = {
                "reinforced": True,
                "reward": rw,
                "prob": p,
                "n": self.n,
                "c": self.c,
                "no_reward_streak": 0,
            }
            return self.last_result
        else:
            self.no_reward_streak += 1
            self._add_history(p, False, None, "")
            self._save_state()
            self.last_result = {
                "reinforced": False,
                "reward": None,
                "prob": p,
                "n": self.n,
                "c": self.c,
                "no_reward_streak": self.no_reward_streak,
            }
            return self.last_result
