# -*- coding: utf-8 -*-
"""规则源 —— 战斗 / 陷阱 / 掉落怎么算（**内置 / 超级引擎**两种实现）。

内置源（默认）
--------------
沿用旧版：``random.randint`` 区间随机。怪 3~8 血、玩家伤害 1~attack、
怪物伤害 2~5（防御 -2）、掉落 50% —— **数值与旧版逐项一致**。

超级引擎源
----------
把区间随机换成 an-engine 的**骰系**（`trpg/dice.py`，SRD 5.1 / CC-BY-4.0）：

* 玩家伤害 → ``1d{attack}``（原来是 ``randint(1, attack)``，同为离散均匀分布，
  但走的是骰子语义，未来可平滑换成武器伤害表）；
* 怪物生命 → ``2d4``（3~8 与原区间**一致**）；
* 怪物伤害 → ``1d4+1``（2~5 与原区间**一致**）；
* 命中判定 → ``d20 + 熟练``对抗固定难度，未命中则本次伤害为 0（新增的**检定层**，
  这是内置路径没有的 —— 也是选择接入规则内核的主要收益）。

注意：刻意让骰系区间与内置区间**重合**，这样"换规则源"不会让难度失衡，
便于对照与回归。
"""

from __future__ import annotations

import random
from typing import Any, Optional

from . import engine as _eng

__all__ = ["BuiltinRules", "SuperEngineRules", "make_rules", "HIT_DC"]

#: 命中难度（d20 + 熟练 ≥ 该值算命中）
HIT_DC = 10

MONSTER_NAMES = ["哥布林", "骷髅兵", "史莱姆"]
LOOT_TABLE = ["生命药水", "力量符文", "破旧护符"]


class BuiltinRules:
    """内置规则（默认）：区间随机，与旧版一致。"""

    name = "builtin"

    def monster_hp(self, rng=None) -> int:
        rng = rng or random
        return rng.randint(3, 8)

    def player_damage(self, attack: int, rng=None) -> int:
        rng = rng or random
        return rng.randint(1, attack)

    def monster_damage(self, defending: bool, rng=None) -> int:
        rng = rng or random
        return max(0, rng.randint(2, 5) - (2 if defending else 0))

    def trap_damage(self, rng=None) -> int:
        rng = rng or random
        return rng.randint(5, 10)

    def heal_amount(self, rng=None) -> int:
        rng = rng or random
        return rng.randint(5, 10)

    def drop_chance(self, rng=None) -> bool:
        rng = rng or random
        return rng.random() < 0.5

    def pick(self, seq, rng=None):
        rng = rng or random
        return rng.choice(list(seq))

    def hits(self, proficiency: int = 2, rng=None) -> bool:
        """内置路径无检定层 —— 恒定命中（保持旧版行为）。"""
        return True


class SuperEngineRules:
    """超级引擎规则：an-engine 骰系 + d20 命中检定。"""

    name = "superengine"

    def __init__(self, engine, proficiency: int = 2):
        self.engine = engine
        self.proficiency = proficiency

    def _ae(self):
        return self.engine.anengine()

    def monster_hp(self, rng=None) -> int:
        # 1d6+2 ⇒ 3~8，与内置 randint(3,8) **区间完全一致**
        return self._ae().roll_dice(1, 6) + 2

    def player_damage(self, attack: int, rng=None) -> int:
        return self._ae().roll_dice(1, max(1, int(attack)))

    def monster_damage(self, defending: bool, rng=None) -> int:
        # 1d4+1 ⇒ 2~5，与原区间完全一致
        dmg = self._ae().roll_dice(1, 4) + 1
        return max(0, dmg - (2 if defending else 0))

    def trap_damage(self, rng=None) -> int:
        # 1d6+4 ⇒ 5~10，与原区间一致
        return self._ae().roll_dice(1, 6) + 4

    def heal_amount(self, rng=None) -> int:
        # 1d6+4 ⇒ 5~10，与原区间一致
        return self._ae().roll_dice(1, 6) + 4

    def drop_chance(self, rng=None) -> bool:
        return self._ae().roll_dice(1, 100) <= 50

    def pick(self, seq, rng=None):
        seq = list(seq)
        idx = self._ae().roll_dice(1, len(seq)) - 1
        return seq[idx]

    def hits(self, proficiency: int = None, rng=None) -> bool:
        """d20 + 熟练 vs 难度 —— 内置路径没有的**检定层**。"""
        prof = self.proficiency if proficiency is None else proficiency
        return (self._ae().roll_d20() + prof) >= HIT_DC


def make_rules(kind: str, engine=None, **kw):
    """工厂：按名字造规则源；``kind='super'`` 且引擎不可用时**回退**内置。"""
    if kind == "super" and engine is not None and _eng.ready(engine):
        return SuperEngineRules(engine, **kw)
    return BuiltinRules()
