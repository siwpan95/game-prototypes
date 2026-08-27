# -*- coding: utf-8 -*-
"""
core/paths.py — 统一路径解析（含空格路径安全）

使用 pathlib.Path，禁止字符串拼接。项目根目录 G:\\Life Reset Simulator 含空格，
所有上层模块一律从这里取路径，避免 os.path.join 拼接带来的隐患。
本模块零 UI 依赖，禁止 import tkinter / print / input / time.sleep。
"""

from __future__ import annotations

from pathlib import Path

# 项目根目录：本文件位于 <root>/core/paths.py，故向上两级为根目录
ROOT: Path = Path(__file__).resolve().parent.parent

# 内容目录（B3 新增内容落点；删掉它游戏仍能用根目录存量内容游玩，见 R10）
CONTENT_DIR: Path = ROOT / "content"

# 存档目录
SAVES_DIR: Path = ROOT / "saves"

# 全局档案路径
PROFILE_PATH: Path = ROOT / "profile.json"

# 导出目录（人生总结报告 txt 导出）
EXPORTS_DIR: Path = ROOT / "exports"

# 工具目录
TOOLS_DIR: Path = ROOT / "tools"

# 文档目录
DOCS_DIR: Path = ROOT / "docs"

# 存量 JSON 文件名（根目录原地保留，R7/R8/R10）
BACKGROUND_FILE: str = "backgrounds.json"
EVENTS_FILE: str = "events.json"
CARDS_FILE: str = "decision_cards.json"


def ensure_dirs() -> None:
    """确保运行时所需目录存在（幂等）。不抛异常，目录已存在则跳过。"""
    for d in (SAVES_DIR, CONTENT_DIR, EXPORTS_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            # 目录创建失败不应阻断游戏；表现层可忽略
            pass
