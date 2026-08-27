# -*- coding: utf-8 -*-
"""
core/constants.py — 全局常量与枚举（零 UI 依赖）

本模块是 B1 内核地基的一部分。严禁 import tkinter / 调用 print / input / time.sleep。
所有枚举与调参常量集中在此，便于后续批次（B2-B5）复用与统一调参。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Tuple


# ─────────────────────────────────────────────────────────────
# 存档版本
# ─────────────────────────────────────────────────────────────
SCHEMA_VERSION: int = 2
"""当前存档 schema 版本。无该字段的旧存档视为 v1（见 core/savegame.migrate_v1_to_v2）。"""


# ─────────────────────────────────────────────────────────────
# game_mode 归一化（修复 BUG-1）
# ─────────────────────────────────────────────────────────────
CANONICAL_MODES: Tuple[str, ...] = ("traditional", "reigns", "cultivation")
"""合法的 game_mode 取值，只有这三个。power / adventure 是历史遗留别名，永不在写出时出现。"""

MODE_ALIASES: Dict[object, str] = {
    "power": "reigns",        # game_gui.py 历史写法
    "adventure": "traditional",  # game_gui.py 历史写法
    "reigns": "reigns",
    "traditional": "traditional",
    "cultivation": "cultivation",
    "": "traditional",
    None: "traditional",
}


def normalize_mode(mode) -> str:
    """将任意（可能非法的）game_mode 归一化为 canonical 值。

    - 已知别名（power/adventure）映射到 canonical。
    - 未知值（含 None / 空串）一律回退 traditional，绝不抛出异常。
    这是 BUG-1 的修复核心：读档时统一把历史别名收口。
    """
    return MODE_ALIASES.get(mode, "traditional")


# ─────────────────────────────────────────────────────────────
# 枚举
# ─────────────────────────────────────────────────────────────
class Rarity(str, Enum):
    """天赋 / 卡牌稀有度。"""
    COMMON = "common"        # 普通（黑）
    RARE = "rare"            # 稀有（蓝）
    EPIC = "epic"            # 史诗（紫）
    LEGENDARY = "legendary"  # 传说（橙）


class Era(str, Enum):
    """篇章。"""
    DYNASTY = "dynasty"      # 王朝篇
    MODERN = "modern"        # 现代篇
    ANY = "any"              # 两篇通用


# ─────────────────────────────────────────────────────────────
# 调参常量（§3.10 防重复三件套，集中定义便于调参）
# ─────────────────────────────────────────────────────────────
DECAY_FACTOR: float = 0.5
"""被抽中后 decay[id] *= 0.5。"""

DECAY_FLOOR: float = 0.125
"""衰减下限（连续抽中 3 次后触底）。"""

DECAY_RECOVER: float = 0.15
"""每局开始时 decay[id] = min(1.0, decay[id] + 0.15)，恢复满需约 6 局。"""

DEFAULT_COOLDOWN_RUNS: int = 2
"""条目未显式声明 cooldown_runs 时，被抽中后设 2 局冷却。"""

SEEN_SCOPE: str = "run"
"""已见集合的生命周期 = 单局（存档字段 seen_content，随存档走）。"""


# ─────────────────────────────────────────────────────────────
# 维度白名单（RK3 校验用）
# ─────────────────────────────────────────────────────────────
DIMENSIONS: Tuple[str, ...] = (
    "STRENGTH", "INTELLIGENCE", "CHARISMA", "WEALTH", "MORALITY",
    "STABILITY", "CHURCH", "NOBLES", "COMMONERS", "HEALTH", "HAPPINESS",
)
"""11 个王权维度（大写）。min_<dimension> 的后缀只可能是这 11 个之一。"""

VALID_MIN_PREFIX_DIMS: frozenset = frozenset(d.lower() for d in DIMENSIONS)
"""min_ 后缀允许的合法维度小写集合，供校验脚本白名单使用。"""


# ─────────────────────────────────────────────────────────────
# 玩家属性键（小写体系，§7.5）
# ─────────────────────────────────────────────────────────────
PLAYER_STATS: Tuple[str, ...] = (
    "strength", "intelligence", "agility", "charisma", "luck",
    "wealth", "happiness", "health", "EI", "SN", "TF", "JP", "traits",
)


# ─────────────────────────────────────────────────────────────
# 教育链（有序）
# ─────────────────────────────────────────────────────────────
EDUCATION_CHAIN: Tuple[str, ...] = ("none", "high_school", "bachelor", "master", "phd")


# ─────────────────────────────────────────────────────────────
# 年龄段（按 get_age_group 语义，向后兼容，不动它）
# ─────────────────────────────────────────────────────────────
AGE_BANDS: Tuple[str, ...] = ("20s", "30s", "40s", "50s", "60+")


# ─────────────────────────────────────────────────────────────
# 稀有度配色 / 标记（双端共用同一份定义，CLI 用 RARITY_MARKS，GUI 用 RARITY_COLORS）
# ─────────────────────────────────────────────────────────────
RARITY_MARKS: Dict[str, str] = {
    "common": "·",
    "rare": "◆",
    "epic": "★",
    "legendary": "👑",
}

RARITY_COLORS: Dict[str, str] = {
    "common": "#9aa0a6",
    "rare": "#3282b8",
    "epic": "#6c5ce7",
    "legendary": "#f5c518",
}

# 天赋稀有度抽取概率：common / rare / epic / legendary
RARITY_PROBABILITIES: Dict[str, float] = {
    "common": 0.65,
    "rare": 0.26,
    "epic": 0.08,
    "legendary": 0.01,
}


# ─────────────────────────────────────────────────────────────
# 内置兜底内容（4 级降级 L3 用，§3.10）
# ─────────────────────────────────────────────────────────────
FALLBACK_CARD: Dict = {
    "id": "__fallback_card__",
    "title": "平淡的朝政",
    "description": "今天没有什么大事发生，你处理了些日常事务。",
    "left_choice": {
        "text": "按部就班",
        "effects": {},
        "speech": "稳一点总没错。",
    },
    "right_choice": {
        "text": "随意发挥",
        "effects": {},
        "speech": "船到桥头自然直。",
    },
    "conditions": {"required_traits": [], "min_strength": 0},
    "weight": 1.0,
}

FALLBACK_EVENT: Dict = {
    "id": "__fallback_event__",
    "desc": "平淡的一天，什么都没发生。",
    "options": {
        "A": {
            "text": "继续生活",
            "effects": {},
            "feedback": ["又是平凡的一天。", "岁月静好。"],
        }
    },
}
