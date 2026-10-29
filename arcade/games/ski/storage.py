"""高分持久化 - 按 mode 分别记录历史最高分。

存储格式（JSON）：
{
  "endless_best": 320,
  "slalom_best": 180,
  "freestyle_best": 95,
  "version": 1
}

设计要点：
- 文件不存在或损坏时优雅降级，返回 0，不阻断游戏
- 写入采用临时文件 + 原子替换，避免中途崩溃导致文件损坏
- 仅记录「分数」单一指标；距离/风格分等如需扩展可后续加字段
"""

from __future__ import annotations

import json
import os
import tempfile

from config import HIGHSCORE_FILE, HIGHSCORE_KEY_FORMAT, MODE_ENDLESS, MODE_FREESTYLE, MODE_SLALOM

_ALL_MODES = (MODE_ENDLESS, MODE_SLALOM, MODE_FREESTYLE)
_VERSION = 1


def _resolve_path() -> str:
    """高分文件路径：与引擎同目录。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, HIGHSCORE_FILE)


def load_all() -> dict[str, int]:
    """读取全部模式的高分。失败时返回全 0。"""
    path = _resolve_path()
    if not os.path.exists(path):
        return {HIGHSCORE_KEY_FORMAT.format(mode=m): 0 for m in _ALL_MODES}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {HIGHSCORE_KEY_FORMAT.format(mode=m): 0 for m in _ALL_MODES}
        # 补齐缺失模式
        result = {}
        for m in _ALL_MODES:
            key = HIGHSCORE_KEY_FORMAT.format(mode=m)
            result[key] = int(data.get(key, 0))
        return result
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return {HIGHSCORE_KEY_FORMAT.format(mode=m): 0 for m in _ALL_MODES}


def load_best(mode: str) -> int:
    """读取指定模式的最高分。"""
    return load_all().get(HIGHSCORE_KEY_FORMAT.format(mode=mode), 0)


def save_best(mode: str, score: int) -> tuple[int, bool]:
    """更新指定模式最高分。

    Returns:
        (current_best, is_new_record)
    """
    all_scores = load_all()
    key = HIGHSCORE_KEY_FORMAT.format(mode=mode)
    old_best = all_scores.get(key, 0)
    is_new = score > old_best
    if is_new:
        all_scores[key] = score
        _atomic_write(all_scores)
    return old_best if not is_new else score, is_new


def _atomic_write(data: dict) -> None:
    """原子写入：先写临时文件，再替换目标文件，避免损坏。"""
    path = _resolve_path()
    data_with_version = dict(data)
    data_with_version["version"] = _VERSION
    directory = os.path.dirname(path)
    try:
        # tempfile 保证临时文件与目标在同一卷，os.replace 才能原子
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data_with_version, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError:
        # 写失败不影响游戏，静默吞掉
        pass
