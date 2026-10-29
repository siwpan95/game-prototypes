# -*- coding: utf-8 -*-
"""名人堂 — 本地战绩榜（致敬 Progress Quest 的 Hall of Fame）

硬核肉鸽：角色阵亡即结算一条生涯记录，跨重开累积：
- 生涯总览：总轮数 / 总死亡 / 最高等级 / 最高击杀 / 最高金币 / 最长存活
- 最近 N 条生涯记录
数据保存在存档同目录的 hall_of_fame.json（独立于 save.json，不破坏存档 schema）。
"""
from __future__ import annotations
import json
import os
from typing import Dict, List, Optional


class HallOfFame:
    """本地战绩榜服务（零依赖，纯文件读写，失败静默降级）"""

    MAX_HISTORY = 20  # 最多保留最近 20 条生涯

    def __init__(self, path: str = None):
        self.path = path
        self.records: Dict = {
            "total_runs": 0,
            "total_deaths": 0,
            "best_level": 0,
            "best_kills": 0,
            "best_gold": 0,
            "best_survival": 0.0,
            "history": [],
        }
        self._load()

    # ── 持久化 ──

    def _load(self):
        if not self.path or not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in self.records:
                if key in data:
                    self.records[key] = data[key]
        except Exception:
            pass  # 榜单损坏不影响游戏

    def _save(self):
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 结算 ──

    def submit(self, run: dict) -> List[str]:
        """结算一条生涯（阵亡时调用），返回破纪录播报列表。

        run: {name, race, char_class, level, kills, gold, survival_seconds}
        """
        msgs: List[str] = []
        self.records["total_runs"] += 1
        self.records["total_deaths"] += 1

        level = int(run.get("level", 0))
        kills = int(run.get("kills", 0))
        gold = int(run.get("gold", 0))
        survival = float(run.get("survival_seconds", 0.0))

        if level > self.records["best_level"]:
            self.records["best_level"] = level
            msgs.append(f"[名人堂] 新纪录！最高等级 Lv.{level}（{run.get('name', '?')}）")
        if kills > self.records["best_kills"]:
            self.records["best_kills"] = kills
            msgs.append(f"[名人堂] 新纪录！单局最高击杀 {kills}")
        if gold > self.records["best_gold"]:
            self.records["best_gold"] = gold
            msgs.append(f"[名人堂] 新纪录！单局最高金币 {gold}G")
        if survival > self.records["best_survival"]:
            self.records["best_survival"] = round(survival, 1)
            msgs.append(f"[名人堂] 新纪录！最长存活 {self._fmt_duration(survival)}")

        history = self.records["history"]
        history.append({
            "name": run.get("name", "?"),
            "race": run.get("race", ""),
            "char_class": run.get("char_class", ""),
            "level": level,
            "kills": kills,
            "gold": gold,
            "survival_seconds": round(survival, 1),
        })
        while len(history) > self.MAX_HISTORY:
            history.pop(0)
        self._save()
        return msgs

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        seconds = int(seconds)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        if h > 0:
            return f"{h}小时{m:02d}分{s:02d}秒"
        if m > 0:
            return f"{m}分{s:02d}秒"
        return f"{s}秒"

    def summary_line(self) -> Optional[str]:
        """生成榜单摘要（用于 UI/日志展示）"""
        r = self.records
        if r["total_runs"] == 0:
            return None
        return (
            f"[名人堂] 共{r['total_runs']}世 | 最高 Lv.{r['best_level']} | "
            f"击杀 {r['best_kills']} | 金币 {r['best_gold']} | "
            f"最长存活 {self._fmt_duration(r['best_survival'])}"
        )
