"""标准 144 张麻将牌堆生成。"""
from dataclasses import dataclass
from typing import List

from models.tile import Suit, Tile

# 数字 1..9 -> 中文
_CN_NUM = "零一二三四五六七八九"

# 风牌 / 箭牌 / 季 / 花 的固定列表
_WINDS = ["东", "南", "西", "北"]
_DRAGONS = ["中", "发", "白"]
_SEASONS = ["春", "夏", "秋", "冬"]
_FLOWERS = ["梅", "兰", "菊", "竹"]


@dataclass
class DeckSpec:
    """一套麻将牌的规格说明。"""
    total: int = 144
    suits: tuple = ("筒", "条", "万")
    copies: int = 4            # 数字/风/箭 每种张数
    season_count: int = 4      # 季 (各1张)
    flower_count: int = 4      # 花 (各1张)


def _digit_suit_tile(rank: int, suit: Suit, suit_cn: str) -> Tile:
    name = f"{_CN_NUM[rank]}{suit_cn}"
    short = f"{rank}{suit_cn}"
    return Tile(name=name, short=short, suit=suit, rank=rank)


def build_standard_deck() -> List[Tile]:
    """生成标准 144 张牌 (顺序固定，调用方自行 shuffle)。

    返回 List[Tile]，长度恒为 144。
    """
    deck: List[Tile] = []

    # 筒 / 条 / 万：各 9 种 × 4 张 = 108
    suit_map = [("筒", Suit.DOTS), ("条", Suit.BAMBOO), ("万", Suit.CHAR)]
    for suit_cn, suit in suit_map:
        for rank in range(1, 10):
            t = _digit_suit_tile(rank, suit, suit_cn)
            deck.extend([t] * 4)

    # 风 4×4 = 16
    for i, name in enumerate(_WINDS, start=1):
        deck.extend([Tile(name=name, short=name, suit=Suit.WIND, rank=i)] * 4)

    # 箭 3×4 = 12
    for i, name in enumerate(_DRAGONS, start=1):
        deck.extend([Tile(name=name, short=name, suit=Suit.DRAGON, rank=i)] * 4)

    # 季 各 1 = 4 (group="季"，组内任意互配)
    for i, name in enumerate(_SEASONS, start=1):
        deck.append(Tile(name=name, short=name, suit=Suit.SEASON, rank=i, group="季"))

    # 花 各 1 = 4 (group="花"，组内任意互配)
    for i, name in enumerate(_FLOWERS, start=1):
        deck.append(Tile(name=name, short=name, suit=Suit.FLOWER, rank=i, group="花"))

    assert len(deck) == 144, f"牌堆数量错误: {len(deck)} != 144"
    return deck
