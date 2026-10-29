# -*- coding: utf-8 -*-
"""
core/streaks.py — 连续登录 Streaks 系统（联网调研成果 · BitLife 2025）

设计来源：
    BitLife 2025年11月更新引入 Streaks 机制——跟踪连续游玩天数，连胜达标
    给予奖励。这是品类内最新的低实现成本、高留存收益机制，纯数据层即可落地，
    完美适配 Tkinter 约束。

机制：
    1. 每次游戏启动调用 record_play(today) 记录一次游玩
    2. 若 today 与上次游玩日期相邻（差1天）→ streak += 1
    3. 若差>1天 → streak 重置为1（破连胜）
    4. 同一天多次游玩只算1次（幂等）
    5. 达到里程碑（3/7/14/30/60/100天）时产出 reward，由表现层提示玩家
    6. reward 为下一局的微增益（luck+1 / 起始财富+1 等），写入 profile
    7. 容错：profile 损坏/字段缺失时降级为"未开始连胜"

零 UI 依赖。所有提示通过返回值 message 字段传递，绝不 print。
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple


# 里程碑 → 奖励（借鉴 BitLife "build up your streak enough and something good might happen"）
MILESTONES: Dict[int, Dict[str, Any]] = {
    3:   {"name": "三日之约", "reward": {"next_run_buff": {"luck": 1}},
          "message": "连续玩了3天。下一局运气+1。"},
    7:   {"name": "一周之约", "reward": {"next_run_buff": {"luck": 1, "wealth": 1}},
          "message": "连续玩了7天。下一局运气+1、起始财富+1。"},
    14:  {"name": "半月之交", "reward": {"next_run_buff": {"luck": 2, "wealth": 1, "happiness": 1}},
          "message": "连续玩了14天。下一局运气+2、起始财富+1、起始幸福+1。"},
    30:  {"name": "月度之友", "reward": {"next_run_buff": {"luck": 2, "wealth": 2, "happiness": 2, "health": 5}},
          "message": "连续玩了30天。下一局全属性微增益。并解锁：连续登录专属天赋池。"},
    60:  {"name": "双月之契", "reward": {"next_run_buff": {"luck": 3, "wealth": 3, "happiness": 3, "health": 8},
          "unlock_talent": "tal_streak_devotee"},
          "message": "连续玩了60天。解锁专属天赋：连胜信徒。"},
    100: {"name": "百日不辍", "reward": {"next_run_buff": {"luck": 3, "wealth": 5, "happiness": 5, "health": 10},
          "unlock_talent": "tal_century_soul"},
          "message": "连续玩了100天。解锁专属天赋：百年之魂。这已经不只是游戏了。"},
}


def _today_str() -> str:
    """返回本地日期 YYYY-MM-DD。"""
    return datetime.date.today().isoformat()


def _parse_date(s: str) -> Optional[datetime.date]:
    """容错解析日期字符串。失败返回 None。"""
    if not isinstance(s, str) or not s:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _default_streak_state() -> Dict[str, Any]:
    """默认连胜状态。"""
    return {
        "current": 0,                # 当前连胜天数
        "last_play_date": None,      # 上次游玩日期 YYYY-MM-DD
        "max_streak": 0,             # 历史最长连胜
        "claimed_milestones": [],    # 已领取的里程碑天数
        "pending_buff": None,        # 待生效的下一局增益（dict 或 None）
    }


def ensure_streak_state(profile: Dict[str, Any]) -> Dict[str, Any]:
    """确保 profile 含合法的 streaks 字段（缺失/损坏时重建默认）。

    返回 streaks 子 dict（同时写回 profile）。四级容错遵循 R6。
    """
    s = profile.get("streaks")
    if not isinstance(s, dict):
        s = _default_streak_state()
        profile["streaks"] = s
        return s
    # 单字段类型校验 + 默认回退
    defaults = _default_streak_state()
    for k, default_val in defaults.items():
        if k not in s or s[k] is None:
            s[k] = default_val if not isinstance(default_val, list) else list(default_val)
        elif k == "claimed_milestones" and not isinstance(s[k], list):
            s[k] = []
        elif k == "pending_buff" and not (s[k] is None or isinstance(s[k], dict)):
            s[k] = None
        elif isinstance(default_val, int) and not isinstance(s[k], int):
            s[k] = default_val
    profile["streaks"] = s
    return s


def record_play(profile: Dict[str, Any], today: Optional[str] = None) -> Dict[str, Any]:
    """记录一次游玩，更新连胜状态。

    返回 dict：
        {
          "streak": int,           # 更新后的当前连胜
          "message": str,          # 给表现层的提示（可能为空串）
          "milestone_reward": dict|None,  # 若本次触及里程碑则返回奖励
          "broken": bool,          # 是否破连胜
        }
    """
    today_str = today or _today_str()
    today_date = _parse_date(today_str)
    s = ensure_streak_state(profile)

    result: Dict[str, Any] = {
        "streak": s["current"],
        "message": "",
        "milestone_reward": None,
        "broken": False,
    }

    if today_date is None:
        # 日期解析失败——不动状态，仅提示
        result["message"] = "连胜状态：日期解析失败，本次未记录。"
        return result

    last_date = _parse_date(s.get("last_play_date") or "")
    if last_date is None:
        # 首次记录
        s["current"] = 1
        s["last_play_date"] = today_str
        s["max_streak"] = max(s["max_streak"], 1)
        result["streak"] = 1
        result["message"] = "连胜开始：第1天。"
        return result

    if last_date == today_date:
        # 同一天多次游玩，幂等
        result["message"] = f"今日已记录，连胜维持：第{s['current']}天。"
        return result

    delta = (today_date - last_date).days
    if delta == 1:
        # 连胜延续
        s["current"] += 1
    elif delta > 1:
        # 破连胜
        result["broken"] = True
        result["message"] = f"连胜中断（间隔{delta}天）。重新开始计数。"
        s["current"] = 1
    else:
        # delta <= 0 不应发生（系统时钟回拨），容错：不记录
        result["message"] = "连胜状态：检测到时钟异常，本次未记录。"
        return result

    s["last_play_date"] = today_str
    s["max_streak"] = max(s["max_streak"], s["current"])
    result["streak"] = s["current"]

    # 检查里程碑
    milestone = MILESTONES.get(s["current"])
    if milestone and s["current"] not in s["claimed_milestones"]:
        s["claimed_milestones"].append(s["current"])
        # 累积 pending_buff（多次未领取的里程碑会叠加）
        buff = milestone.get("reward", {}).get("next_run_buff", {})
        if buff:
            if not isinstance(s["pending_buff"], dict):
                s["pending_buff"] = {}
            for k, v in buff.items():
                s["pending_buff"][k] = s["pending_buff"].get(k, 0) + v
        result["milestone_reward"] = milestone
        result["message"] = milestone["message"]
    elif not result["message"]:
        result["message"] = f"连胜：第{s['current']}天。"

    return result


def consume_pending_buff(profile: Dict[str, Any]) -> Dict[str, Any]:
    """消费待生效的连胜增益（在新一局开始时调用，返回 buff 并清空 pending）。

    返回 buff dict（可能为空 dict）。调用方应将 buff 应用到 Player 初始属性。
    """
    s = ensure_streak_state(profile)
    buff = s.get("pending_buff") or {}
    if not isinstance(buff, dict):
        buff = {}
    s["pending_buff"] = None  # 消费后清空
    return buff


def get_streak_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    """返回连胜摘要（供图鉴/设置面板展示）。只读，不改状态。"""
    s = ensure_streak_state(profile)
    return {
        "current": s.get("current", 0),
        "max_streak": s.get("max_streak", 0),
        "last_play_date": s.get("last_play_date"),
        "claimed_milestones": list(s.get("claimed_milestones", [])),
        "next_milestone": _next_milestone(s.get("current", 0)),
        "pending_buff": dict(s.get("pending_buff") or {}),
    }


def _next_milestone(current: int) -> Optional[int]:
    """返回下一个未达成的里程碑天数；全达成返回 None。"""
    for day in sorted(MILESTONES.keys()):
        if day > current:
            return day
    return None
