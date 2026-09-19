"""Tile - 麻将牌的不可变数据模型。

标准 144 张配比：
  筒/条/万 各 9 种 × 4 = 108
  风 东南西北 × 4 = 16
  箭 中发白 × 4 = 12
  季 春夏秋冬 × 1 = 4   (组内任意互配)
  花 梅兰菊竹 × 1 = 4   (组内任意互配)
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from allin_engine.core import Component


class Suit(Enum):
    DOTS = "筒"        # 筒子 / 饼
    BAMBOO = "条"      # 条子 / 索
    CHAR = "万"        # 万子 / 字
    WIND = "风"        # 风牌
    DRAGON = "箭"      # 三元牌
    SEASON = "季"      # 季节牌 (特殊配对组)
    FLOWER = "花"      # 花牌   (特殊配对组)


@dataclass(frozen=True)
class Tile(Component):
    """一张麻将牌 —— 同时是引擎 ECS 的 Component（牌面即组件数据）。

    name : 显示用主文字，如 "一万"、"东风"、"春"
    short: 渲染用紧凑文字 (单字符或两字)，如 "1万"、"东"、"春"
    suit : 花色
    rank : 序号 1..9 (数字牌) / 1..4 (风/季/花) / 1..3 (箭)
    group: 配对组名。非空时同组任意两张可互配 (仅季/花使用)
    """
    name: str
    short: str
    suit: Suit
    rank: int = 0
    group: str = ""

    # ---- 配对判定 -------------------------------------------------
    def matches(self, other: "Tile") -> bool:
        """两张牌是否可配对消除。
        同名同牌 -> True；同配对组(季/花) -> True；否则 False。
        """
        if self.name == other.name:
            return True
        if self.group and self.group == other.group:
            return True
        return False

    # ---- 颜色 (渲染参考) -----------------------------------------
    @property
    def color(self) -> str:
        if self.suit == Suit.DRAGON:
            return {"中": "#c00", "发": "#080", "白": "#888"}.get(self.short, "#000")
        if self.suit == Suit.WIND:
            return "#c00"
        if self.suit == Suit.SEASON or self.suit == Suit.FLOWER:
            return "#c60"
        if self.suit == Suit.CHAR:
            return "#000"
        return "#000"

    def __repr__(self) -> str:
        return f"<Tile {self.name}>"
