# -*- coding: utf-8 -*-
"""
core/profile.py — 全局档案 profile.json 读写（§3.8）

四级容错（R6 硬性）：
1. 文件不存在        → 静默创建默认档案（不弹窗、不报错，可返回提示信息由表现层决定）
2. JSON 损坏/顶层非dict → 备份为 profile.json.corrupt.<timestamp>，重建默认档案
3. 单字段类型不符     → 该字段回退默认值，其余字段保留
4. 未知字段           → 原样保留写回（前向兼容）

写入原子：先写 profile.json.tmp → os.replace()。
lineage 字段预留（Q3）：不读不写，仅保证不被清空。

本模块零 UI 依赖，禁止 import tkinter / print / input / time.sleep。
需要向表现层提示时，通过返回值 message 字段传递，绝不 print。
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import jsonio


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO8601 字符串。"""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# 默认档案（§3.8 全部字段 + 默认值）
def _default_profile() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "total_runs": 0,
        "unlocked_achievements": [],
        "seen_endings": [],
        "inherited_talent": None,
        "unlocked_talents": [],
        "unlocked_card_pools": [],
        "unlocked_background_options": [],
        "unlocked_modes": [],
        "content_state": {
            "cooldown": {},
            "decay": {},
            "last_seen_run": {},
        },
        "stats": {
            "best_score": 0,
            "longest_life": 0,
            "total_endings": 0,
            "total_achievements": 0,
        },
        "lineage": [],
        # ── 联网调研成果：3 个新留存系统（纯数据层，零破坏）──
        "streaks": {
            "current": 0,
            "last_play_date": None,
            "max_streak": 0,
            "claimed_milestones": [],
            "pending_buff": None,
        },
        "heirlooms_state": {
            "heirlooms": [],
            "generations": 0,
            "history": [],
        },
        "unlocked_challenges": [],
        "completed_challenges": [],
        "active_challenge": None,
    }


# 字段 → 期望类型的约束（用于单字段类型回退）
_FIELD_TYPES: Dict[str, type] = {
    "schema_version": int,
    "total_runs": int,
    "unlocked_achievements": list,
    "seen_endings": list,
    "inherited_talent": (str, type(None)),
    "unlocked_talents": list,
    "unlocked_card_pools": list,
    "unlocked_background_options": list,
    "unlocked_modes": list,
    "content_state": dict,
    "stats": dict,
    "lineage": list,
    "streaks": dict,
    "heirlooms_state": dict,
    "unlocked_challenges": list,
    "completed_challenges": list,
    "active_challenge": (str, type(None)),
}


def _coerce_field(key: str, value: Any) -> Tuple[bool, Any]:
    """按 _FIELD_TYPES 校验单字段类型。返回 (ok, value)。

    - 类型正确 → (True, value)
    - 类型错误 → (False, 默认值)；但未知字段不在此表，调用方需另行保留
    """
    expected = _FIELD_TYPES.get(key)
    if expected is None:
        return True, value
    if isinstance(expected, tuple):
        if isinstance(value, expected):
            return True, value
    elif isinstance(value, expected):
        return True, value
    # 类型不符 → 回退默认值
    default = _default_profile().get(key, None)
    return False, default


class Profile:
    """全局档案。

    用法：
        prof = Profile(PROFILE_PATH).load()   # 容错加载，得到 self.data
        prof.data["total_runs"] += 1
        prof.save()                            # 原子写回
    """

    def __init__(self, path: Any) -> None:
        self.path: Path = Path(path)
        self.data: Dict[str, Any] = _default_profile()
        self.message: str = ""          # 表现层可选提示（损坏重建等），不弹窗
        self.was_corrupt: bool = False

    # ───────────────────────────────────────────────────────
    # 加载（四级容错）
    # ───────────────────────────────────────────────────────
    def load(self) -> "Profile":
        """容错加载 profile.json。永不抛异常。"""
        self.message = ""
        self.was_corrupt = False

        # 级别 1：文件不存在 → 静默创建默认档案
        if not self.path.exists() or not self.path.is_file():
            self.data = _default_profile()
            self._write_atomic(self.data)      # 静默创建
            self.message = "profile.json 不存在，已创建默认档案。"
            return self

        # 读取原始文本
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            self.data = _default_profile()
            self.message = "profile.json 读取失败，已重建默认档案。"
            self._write_atomic(self.data)
            return self

        # 解析
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None

        if not isinstance(parsed, dict):
            # 级别 2：损坏 / 顶层非 dict → 备份 + 重建
            self._backup_corrupt(raw)
            self.data = _default_profile()
            self.was_corrupt = True
            self.message = "profile.json 损坏，已备份并重建默认档案。"
            self._write_atomic(self.data)
            return self

        # 级别 3 + 4：逐字段类型回退 + 未知字段保留
        self.data = self._repair(parsed)
        return self

    def _repair(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """逐字段修复：类型不符单字段回退；未知字段原样保留写回。"""
        default = _default_profile()
        result: Dict[str, Any] = {}

        # 先放已知字段（带类型校验）
        for key in default.keys():
            if key in parsed:
                ok, val = _coerce_field(key, parsed[key])
                result[key] = val if ok else default[key]
            else:
                result[key] = default[key]

        # 未知字段：原样保留（前向兼容，防止旧版本抹掉新版本数据）
        for key, val in parsed.items():
            if key not in result:
                result[key] = val

        # content_state / stats 内部子字段缺失也补默认
        cs = result.get("content_state")
        if not isinstance(cs, dict):
            cs = {}
        cs_default = default["content_state"]
        for k in ("cooldown", "decay", "last_seen_run"):
            if not isinstance(cs.get(k), dict):
                cs[k] = dict(cs_default.get(k, {}))
        result["content_state"] = cs

        st = result.get("stats")
        if not isinstance(st, dict):
            st = {}
        st_default = default["stats"]
        for k, v in st_default.items():
            if k not in st or not isinstance(st[k], (int, float)):
                st[k] = v
        result["stats"] = st

        return result

    def _backup_corrupt(self, raw_text: str) -> None:
        """把损坏内容备份为 profile.json.corrupt.<timestamp>。"""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self.path.with_suffix("")  # 去掉 .json
        backup_name = f"{self.path.stem}.corrupt.{ts}.json"
        backup_path = self.path.parent / backup_name
        try:
            with backup_path.open("w", encoding="utf-8") as f:
                f.write(raw_text)
        except OSError:
            pass

    # ───────────────────────────────────────────────────────
    # 写入（原子）
    # ───────────────────────────────────────────────────────
    def save(self) -> bool:
        """原子写回 profile.json。返回是否成功。"""
        self.data["updated_at"] = _now_iso()
        # 再次确保未知字段不被清空（lineage 等原样保留）
        return self._write_atomic(self.data)

    def _write_atomic(self, data: Dict[str, Any]) -> bool:
        return jsonio.write_json_atomic(self.path, data)

    # ───────────────────────────────────────────────────────
    # 便捷读写
    # ───────────────────────────────────────────────────────
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def is_unlocked(self, key: str) -> bool:
        """判断某解锁物 key 是否已解锁（按前缀分桶查）。"""
        if key.startswith("tal_"):
            return key in (self.data.get("unlocked_talents") or [])
        if key.startswith("pool_"):
            return key in (self.data.get("unlocked_card_pools") or [])
        if key.startswith("bgo_"):
            return key in (self.data.get("unlocked_background_options") or [])
        if key.startswith("mode_"):
            return key in (self.data.get("unlocked_modes") or [])
        return False

    def grant(self, key: str) -> None:
        """解锁某物（按前缀落到对应列表，去重）。"""
        if key.startswith("tal_"):
            lst = self.data.setdefault("unlocked_talents", [])
            if key not in lst:
                lst.append(key)
        elif key.startswith("pool_"):
            lst = self.data.setdefault("unlocked_card_pools", [])
            if key not in lst:
                lst.append(key)
        elif key.startswith("bgo_"):
            lst = self.data.setdefault("unlocked_background_options", [])
            if key not in lst:
                lst.append(key)
        elif key.startswith("mode_"):
            lst = self.data.setdefault("unlocked_modes", [])
            if key not in lst:
                lst.append(key)

    def begin_run(self) -> None:
        """一局开始：content_state 的 decay 每局恢复 +0.15（封顶 1.0）。"""
        cs = self.data.setdefault("content_state", {})
        decay = cs.setdefault("decay", {})
        for k in list(decay.keys()):
            try:
                decay[k] = min(1.0, float(decay[k]) + 0.15)
            except (TypeError, ValueError):
                decay[k] = 1.0

    def end_run(self, result: Optional[Dict[str, Any]] = None) -> None:
        """一局结束：总局数 +1，更新 stats。"""
        self.data["total_runs"] = int(self.data.get("total_runs", 0)) + 1
        stats = self.data.setdefault("stats", {})
        if isinstance(result, dict):
            if "score" in result:
                stats["best_score"] = max(int(stats.get("best_score", 0)), int(result["score"]))
            if "age" in result:
                stats["longest_life"] = max(int(stats.get("longest_life", 0)), int(result["age"]))
            if result.get("is_ending"):
                stats["total_endings"] = int(stats.get("total_endings", 0)) + 1
        self.save()
