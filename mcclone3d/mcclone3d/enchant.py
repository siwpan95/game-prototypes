# -*- coding: utf-8 -*-
"""附魔：经验（XP）、附魔表、附魔台的报价与生效规则（**纯逻辑，零 GL、零 random**）。

## 为什么单开一个模块

"附魔了什么、效果是多少"是**数值设计**，不该散在内核的 `dig_time`/`_use_tool`/`attack` 里。
内核只问四个问题：

| 内核问 | 这里答 |
| --- | --- |
| 挖这块要多久 | `speed_factor(levels)`（效率） |
| 这一次要不要扣耐久 | `wear_every(levels)`（耐久） |
| 掉几个 | `fortune_extra(levels, roll)`（时运）/ `has_silk(levels)`（精准采集） |
| 打一下多少伤害 | `damage_bonus(levels)`（锋利） |

## 三条设计纪律

1. **一切走"经验点数"，等级是派生的。** `level` 不进存档 —— 它由 `xp` 完全决定
   （与本项目"光照/信号不进档、由布局重算"同一条口径）。花掉等级 = 扣点数，
   `spend_xp()` 保证**等级恰好降 n 级**（有单测钉住这条不变量）。
2. **不用 `random`**。附魔台的报价要能复现（否则同一张台子每次点都不同，截图与回放全废），
   所以走坐标哈希（与掉落数量同一套：`recipes.rand01`）。
3. **每个附魔的效果都写成"给定等级算一个数"的纯函数**，于是可以**逐条穷举对拍**，
   而不是"看起来差不多"。

## 与 MC 的差异（写清楚，不假装一样）

* 不要**青金石**：本仓没有青金石矿，为一件消耗品新开一条矿脉会改动世界生成
  （已有存档的矿脉分布会跟着变），不划算 ⇒ 代价只用**经验等级**。
* 没有**书架增福**、没有**铁砧**（合成/修复）、没有**附魔书**：附魔只作用在**手持工具**上。
* 只有 5 个附魔（效率 / 耐久 / 时运 / 精准采集 / 锋利）—— 每个都能在玩法里**被观测到**，
  不做"只有数值没有效果"的装饰性附魔。
"""
from __future__ import annotations

from math import isqrt

__all__ = [
    'Enchantment', 'ENCHANTS', 'ENCHANT_NAMES', 'ENCHANT_ORDER',
    'applies_to', 'candidates', 'MUTEX', 'mutex_ok',
    'xp_total', 'xp_span', 'level_for', 'level_progress', 'spend_xp',
    'speed_factor', 'damage_bonus', 'wear_every', 'fortune_extra', 'has_silk', 'lv_of',
    'Offer', 'offers', 'describe_levels', 'ROMAN',
    'XP_FOR_BLOCK', 'XP_SMELT', 'XP_FOR_MOB',
    'FORTUNE_BLOCKS', 'SILK_BLOCKS',
]

# ==================================================================== 经验
#: 升到第 L 级所需的**累计**经验点数：`L² + 6L`。
#: 反过来说"从 L-1 升到 L"要 `2L + 5` 点（7 / 9 / 11 / 13 …）—— 与 MC 的手感同量级。
#: 选它的理由是**有闭式反函数**（下面 `level_for` 用整数开方算），
#: 不必查表、也不会出现"表与公式对不上"。
XP_QUAD = 6


def xp_total(level: int) -> int:
    """升到第 `level` 级需要的**累计**经验点数（level ≤ 0 ⇒ 0）。"""
    L = max(0, int(level))
    return L * L + XP_QUAD * L


def xp_span(level: int) -> int:
    """第 `level` 级**本级**的长度（从 L 到 L+1 要多少点）—— 经验条的分母。"""
    return xp_total(level + 1) - xp_total(level)


def level_for(xp: int) -> int:
    """经验点数 → 等级（`xp_total` 的**精确整数反函数**）。

    `L² + 6L = xp` ⇒ `L = (√(4xp + 36) − 6) / 2`，取整数开方即可（不碰浮点，
    所以 `level_for(xp_total(L)) == L` 对任意 L 精确成立 —— 单测直接穷举）。
    """
    x = max(0, int(xp))
    return (isqrt(4 * x + XP_QUAD * XP_QUAD) - XP_QUAD) // 2


def level_progress(xp: int):
    """经验条读数 `(等级, 本级已得, 本级需要)`。"""
    lv = level_for(xp)
    got = max(0, int(xp)) - xp_total(lv)
    return lv, got, xp_span(lv)


def spend_xp(xp: int, n: int):
    """花掉 `n` 级，返回剩余点数；付不起返回 `None`。

    **不变量：等级恰好降 n 级**（有单测穷举）。实现上保留当前级的**进度比例**
    —— 直接减"本级长度"会越界（例如 5 级、本级进度 16 点，减一级后 56 点仍是 5 级），
    那是本批最容易写错的一处。
    """
    xp = max(0, int(xp))
    n = int(n)
    if n <= 0:
        return xp
    lv = level_for(xp)
    if lv < n:
        return None
    keep = xp - xp_total(lv)
    span_old = xp_span(lv)
    span_new = xp_span(lv - n)
    return xp_total(lv - n) + (keep * span_new) // span_old


# ==================================================================== 附魔表
class Enchantment:
    """一个附魔的定义。`applies` 是可以附上去的**工具种类**（`items.TOOL_KINDS`）。"""

    __slots__ = ('name', 'title', 'max_level', 'applies', 'desc')

    def __init__(self, name, title, max_level, applies, desc):
        self.name = name
        self.title = title
        self.max_level = int(max_level)
        self.applies = frozenset(applies)
        self.desc = desc

    def __repr__(self):
        return f'<Enchantment {self.name} I..{ROMAN[self.max_level]}>'


#: 罗马数字（HUD 与 CLI 都这么写）
ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V'}

#: 附魔表。**顺序即展示顺序**（报价里的排序也按它，好让日志可读、可对拍）。
#: 每个附魔的 `applies` 都是"真的说得通"的组合：效率/时运/精准采集给挖掘类，
#: 锋利只给剑，耐久给全部。
ENCHANT_ORDER = ('efficiency', 'unbreaking', 'fortune', 'silk_touch', 'sharpness')

ENCHANTS = {
    'efficiency': Enchantment(
        'efficiency', '效率', 5, ('pickaxe', 'axe', 'shovel'),
        '挖掘速度 ×(1 + 0.30·等级)'),
    'unbreaking': Enchantment(
        'unbreaking', '耐久', 3, ('pickaxe', 'axe', 'shovel', 'sword'),
        '每 (1 + 等级) 次使用才磨损 1 点耐久'),
    'fortune': Enchantment(
        'fortune', '时运', 3, ('pickaxe',),
        '矿石/树叶有概率多掉 1 个（等级越高越多）'),
    'silk_touch': Enchantment(
        'silk_touch', '精准采集', 1, ('pickaxe', 'axe', 'shovel'),
        '挖什么掉什么（玻璃掉玻璃、石头掉石头）'),
    'sharpness': Enchantment(
        'sharpness', '锋利', 5, ('sword',),
        '攻击伤害 +0.5·等级'),
}

ENCHANT_NAMES = tuple(ENCHANT_ORDER)
assert set(ENCHANT_NAMES) == set(ENCHANTS)

#: **互斥**附魔对：精准采集与时运（MC 同款 —— 能同时拿到就同时拿到的话，
#: 两个附魔的效果会互相抵消：精准采集让掉落变成方块本身，时运再多掉几个方块）。
MUTEX = (frozenset(('silk_touch', 'fortune')),)


def mutex_ok(picked) -> bool:
    """这一组附魔能不能**同时**存在（互斥对见 `MUTEX`）。"""
    s = set(picked)
    return not any(pair <= s for pair in MUTEX)


def applies_to(name: str, tool_kind: str | None) -> bool:
    """这个附魔能不能附在某种工具上。"""
    e = ENCHANTS.get(name)
    return e is not None and tool_kind in e.applies


def candidates(tool_kind: str | None):
    """某种工具**可以**附的全部附魔名（按 `ENCHANT_ORDER`）。"""
    return tuple(n for n in ENCHANT_ORDER if applies_to(n, tool_kind))


# ==================================================================== 效果
def lv_of(levels, name: str) -> int:
    """从 `{附魔名: 等级}` 里取某条的等级（没有 ⇒ 0）。"""
    if not levels:
        return 0
    return max(0, int(levels.get(name, 0)))


def speed_factor(levels) -> float:
    """效率：挖掘速度倍率。等级 0 ⇒ 1.0（不改动任何东西）。"""
    return 1.0 + 0.30 * lv_of(levels, 'efficiency')


def damage_bonus(levels) -> float:
    """锋利：攻击伤害的**加法**加成。"""
    return 0.5 * lv_of(levels, 'sharpness')


def wear_every(levels) -> int:
    """耐久：**每几次使用才磨损 1 点**（等级 0 ⇒ 1，即每次都磨损）。

    为什么用"累积计数"而不是"按概率跳过"：概率版要么用 `random`（破坏可复现），
    要么用哈希（同一个工具在不同使用次数上随机）。累积计数是**完全确定**的，
    于是"耐久 III 的 251 耐久镐能挖 1004 下"可以**精确断言**，不是"大约四倍"。
    """
    return 1 + lv_of(levels, 'unbreaking')


def fortune_extra(levels, roll: float) -> int:
    """时运：这一次**多掉几个**（>= 0）。

    `extra = floor(roll × (等级 + 1))`，`roll ∈ [0,1)` ⇒ 取值 `0..等级` 等概率，
    期望 `等级 / 2`（III 级平均多掉 1.5 个）。`roll` 由调用方给（内核用方块坐标的
    确定性哈希）—— 于是这条效果是**纯函数**，可以对任意 roll 穷举对拍。
    """
    lv = lv_of(levels, 'fortune')
    if lv <= 0:
        return 0
    r = 0.0 if roll < 0.0 else (1.0 - 1e-12 if roll >= 1.0 else float(roll))
    return int(r * (lv + 1))


def has_silk(levels) -> bool:
    """精准采集：挖什么掉什么。"""
    return lv_of(levels, 'silk_touch') > 0


#: 时运**能**影响掉落的方块（矿石 + 树叶）。其余方块哪怕附了时运也不多掉 ——
#: 让"挖土多掉土"这种事发生只会让背包爆掉，MC 也不这么做。
FORTUNE_BLOCKS = ('coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore', 'leaves')

#: 精准采集**值得管**的方块：它们的正常掉落"丢了信息"（玻璃→无、石头→圆石）。
#: 其余方块精准采集与普通掉落在本版里等价（如实写明，不假装有区别）。
SILK_BLOCKS = ('glass', 'stone', 'leaves', 'grass', 'coal_ore', 'iron_ore',
               'gold_ore', 'diamond_ore', 'crop')


# ==================================================================== 经验来源
#: 挖掉这些方块给多少经验（**只列矿石**：挖土也给经验的话，经验就变成"挖土刷级"）。
XP_FOR_BLOCK = {
    'coal_ore': 1,
    'iron_ore': 2,
    'gold_ore': 3,
    'diamond_ore': 5,
}

#: 烧炼成功一炉给多少经验。
XP_SMELT = 2

#: 击杀给多少经验（村民 0：打村民刷级不是设计意图）。
XP_FOR_MOB = {'sheep': 2, 'pig': 2, 'zombie': 5, 'villager': 0}

#: 单次给的经验上限（护栏：万一有路径一次给一大笔，不至于直接跳几十级）。
XP_GAIN_CAP = 50

#: 附魔台三档报价的**等级成本**（与 MC 的 1/2/3 同口径）。
OFFER_COSTS = (1, 2, 3)

#: 各档能出到的**最高附魔等级**上限：`min(该附魔上限, 2·档 − 1)`。
#: ⇒ 第 1 档只能出 I 级，第 2 档最多 III，第 3 档才可能出 V
#: （与 MC"低级附魔出不了好属性"一致；不然三档就没区别了）。
def offer_cap(cost: int, enchant_name: str) -> int:
    return min(ENCHANTS[enchant_name].max_level, 2 * int(cost) - 1)


#: "稀有货"保留概率：**唯一等级**的附魔（精准采集）每次报价额外抽一次签。
#: 为什么需要这条：精准采集上限就是 I，于是它无论出现在第几档都只显示"I" ——
#: 第 1 档（花 1 级）和第 2 档（花 2 级）看起来一模一样，报价就退化成"抽到废牌"。
#: 让它在报价里更少见（1/2），台阶感才回得来。（MC 里精准采集本来就是台子抽不到的
#: "宝藏附魔"，放在本版的台子上属于稀有货 —— 取向上是一回事。）
RARE_KEEP = 0.5


class Offer:
    """附魔台的一档报价。`enchants` 是 `{附魔名: 等级}`（**已按互斥筛过**）。"""

    __slots__ = ('slot', 'cost', 'enchants', 'affordable')

    def __init__(self, slot, cost, enchants, affordable):
        self.slot = int(slot)
        self.cost = int(cost)
        self.enchants = dict(enchants)
        self.affordable = bool(affordable)

    def label(self) -> str:
        if not self.enchants:
            return f'第 {self.slot + 1} 档：—（此工具没有可附的属性）'
        body = ' · '.join(f'{ENCHANTS[k].title} {ROMAN.get(v, v)}'
                          for k, v in sorted(self.enchants.items()))
        return f'第 {self.slot + 1} 档（{self.cost} 级）：{body}'

    def __repr__(self):
        return f'<Offer slot={self.slot} cost={self.cost} {self.enchants}>'


def offers(seed: int, x: int, y: int, z: int, item_name: str,
           tool_kind: str | None, player_level: int, rolls=None):
    """附魔台的**三档报价**（确定性：同种子 + 同坐标 + 同物品 + 同等级 ⇒ 同一批）。

    ⚠ 报价**必须**与坐标/物品绑定（不能只看种子）：否则"换个位置再点一下"就能刷出
    想要的属性；同时它又是**幂等**的 —— 反复打开同一张台子看到的是同一批，
    这才符合"这是个报价，不是抽奖机"。

    `rolls` 可注入（单测用来穷举极端取值）；默认由坐标哈希产生。
    """
    if rolls is None:
        rolls = _roll_stream(seed, x, y, z, item_name, player_level)
    get = _Roller(rolls)
    cands = candidates(tool_kind)
    out = []
    for slot in range(3):
        cost = OFFER_COSTS[slot]
        picked = {}
        if cands:
            # 档位越高，条数越多：1 档 1 条；2 档 1~2 条；3 档 2 条
            want = 1 if cost == 1 else (1 if (cost == 2 and get() < 0.5) else 2)
            want = min(want, len(cands))
            order = list(cands)
            # 用报价流做一次 Fisher–Yates（**不用 random**）
            for i in range(len(order) - 1, 0, -1):
                j = int(get() * (i + 1))
                j = 0 if j < 0 else (i if j > i else j)
                order[i], order[j] = order[j], order[i]
            # 稀有货（唯一等级的附魔）额外抽一次签；全被刷掉就保留原序兜底
            order = [n for n in order
                     if ENCHANTS[n].max_level > 1 or get() < RARE_KEEP] or order
            for name in order:
                if len(picked) >= want:
                    break
                if not mutex_ok(list(picked) + [name]):
                    continue
                cap = offer_cap(cost, name)
                picked[name] = 1 + int(get() * cap) if cap > 0 else 1
        out.append(Offer(slot, cost, picked, affordable=int(player_level) >= cost))
    return tuple(out)


#: 报价用的确定性随机序列长度（三档 × 最多 6 次抽取 + 洗牌）
_ROLL_LEN = 24


def _roll_stream(seed, x, y, z, item_name, player_level):
    from .recipes import rand01
    h = 0
    for i, ch in enumerate(str(item_name)):
        h = (h * 131 + ord(ch) * (3 + i)) & 0x7FFFFFFF
    base = (int(seed), int(x), int(y), int(z), h, int(player_level))
    return [rand01(list(base) + [k]) for k in range(_ROLL_LEN)]


class _Roller:
    """把一串数当成"随机流"用；用完了就从头再来（**不允许中途变成随机的**）。"""

    __slots__ = ('_v', '_i')

    def __init__(self, values):
        self._v = list(values) or [0.5]
        self._i = 0

    def __call__(self) -> float:
        v = self._v[self._i % len(self._v)]
        self._i += 1
        return float(v)


def describe_levels(levels) -> str:
    """`{附魔名: 等级}` → 一行中文（HUD / CLI 用）。空 ⇒ `'无附魔'`。"""
    if not levels:
        return '无附魔'
    parts = [f'{ENCHANTS[k].title} {ROMAN.get(int(v), v)}'
             for k, v in sorted(levels.items()) if int(v) > 0]
    return ' · '.join(parts) if parts else '无附魔'
