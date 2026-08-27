# -*- coding: utf-8 -*-
"""
core/savegame.py — 单局存档版本化与 game_mode 归一化（§3.12）

职责：
- dump(player, mode) -> Dict：序列化玩家 + schema_version + 归一化后的 game_mode
- load(path) -> (data, migrated, warnings)：读档，v1 自动迁移到 v2，绝不抛异常
- normalize_mode(m) / migrate_v1_to_v2(data)：纯函数

关键约束：
- 不删除 / 不重命名任何现有存档字段（R4）。Player.from_dict 的 hasattr 容错逻辑
  在 main.py / game_gui.py 中一行不改（R2）；新字段靠 Player.__init__ 默认值兜底。
- schema_version 缺失视为 v1（R3）。
- 本模块零 UI 依赖，禁止 import tkinter / print / input / time.sleep；
  错误信息通过返回值传递，绝不 print。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import constants
from core import jsonio


class SaveManager:
    """单局存档管理。"""

    # ───────────────────────────────────────────────────────
    # 序列化
    # ───────────────────────────────────────────────────────
    @staticmethod
    def dump(player: Any, mode: str) -> Dict[str, Any]:
        """把玩家状态序列化为存档 dict。

        - 调用 player.to_dict()（B1 已把 game_mode / schema_version 收敛进 to_dict）
        - game_mode 强制归一化为 canonical，确保双端写出一致（BUG-1 修复）
        """
        data = player.to_dict()
        data["schema_version"] = constants.SCHEMA_VERSION
        data["game_mode"] = constants.normalize_mode(mode)
        return data

    # ───────────────────────────────────────────────────────
    # 读档 + 迁移
    # ───────────────────────────────────────────────────────
    @staticmethod
    def load(path: Any) -> Tuple[Dict[str, Any], bool, List[str]]:
        """读取存档。返回 (data, migrated, warnings)。

        - 文件缺失 / 损坏 → 返回 ({}, False, [错误信息])，绝不抛异常
        - schema_version 缺失或 ==1 → 走 migrate_v1_to_v2()
        - >2（未来版本）→ 尽力加载，缺失字段由 Player.__init__ 默认值兜底
        """
        warnings: List[str] = []
        p = Path(path)
        if not p.exists() or not p.is_file():
            return {}, False, [f"存档不存在: {p}"]
        data = jsonio.read_json(p, default=None)
        if not isinstance(data, dict):
            return {}, False, [f"存档格式损坏: {p}"]

        version = data.get("schema_version", 1)
        migrated = False
        if version in (None, 1):
            data, migrated = SaveManager.migrate_v1_to_v2(data)
            if migrated:
                warnings.append("存档已升级到 v2（game_mode 已归一化）")
        elif isinstance(version, int) and version > constants.SCHEMA_VERSION:
            warnings.append("存档来自更新的版本，已尽力加载（缺失字段用默认值）")

        # 无论版本，读档时都对 game_mode 再归一化一次（防御性，幂等）
        data["game_mode"] = constants.normalize_mode(data.get("game_mode"))
        return data, migrated, warnings

    # ───────────────────────────────────────────────────────
    # 纯函数：迁移 / 归一化
    # ───────────────────────────────────────────────────────
    @staticmethod
    def migrate_v1_to_v2(data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """纯函数迁移 v1 → v2（不写盘）。

        1. 不删除 / 不重命名任何现有键（R4）
        2. game_mode 归一化（BUG-1 修复）
        3. 补 schema_version = 2
        4. 其余新字段不写入，交给 Player.__init__ 默认值兜底（R2 价值所在）
        """
        data = dict(data)  # 不修改入参
        if "game_mode" in data:
            data["game_mode"] = constants.normalize_mode(data["game_mode"])
        else:
            data["game_mode"] = "traditional"
        data["schema_version"] = constants.SCHEMA_VERSION
        return data, True

    @staticmethod
    def normalize_mode(mode: Any) -> str:
        """公开透传，方便表现层直接调用。"""
        return constants.normalize_mode(mode)

    # ───────────────────────────────────────────────────────
    # 存档列表
    # ───────────────────────────────────────────────────────
    @staticmethod
    def list_saves(saves_dir: Any) -> List[Path]:
        """列出 saves/ 下所有 .json 存档（不含损坏备份等）。"""
        d = Path(saves_dir)
        if not d.exists() or not d.is_dir():
            return []
        return sorted(f for f in d.glob("*.json") if f.is_file() and ".corrupt." not in f.name)
