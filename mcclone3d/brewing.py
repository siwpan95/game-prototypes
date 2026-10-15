# -*- coding: utf-8 -*-
"""酿造与药水效果（纯数据 + 纯函数，零 GL、零 random）。

## 本仓没有下界 —— 材料表是**重排**的，如实写明

MC 的酿造建在"下界疣 + 烈焰粉 + 恶魂之泪"这套下界材料上，而本仓**没有下界维度**
（世界是一个有限箱体：地表 + 洞穴 + 村庄）。硬造"下界疣"或"烈焰粉"只会让人觉得
材料表是抄来的、且无从获得。

所以本版**用本世界已有的资源重排一套酿造表**，一一对应地保留了 MC 的"直觉"：

| 药水 | 材料 | 为什么这么配 |
| --- | --- | --- |
| 治疗 | 金锭 | 贵重 = 治愈（MC 用闪烁的西瓜） |
| 迅捷 | 糖（麦子熬） | **与 MC 同款**：糖 = 迅捷 |
| 力量 | 煤炭 | 炽热 = 力量（对应 MC 的烈焰粉） |
| 抗性 | 铁锭 | 铁 = 护甲（对应 MC 的护甲/抗性） |
| 剧毒 | 腐肉 | 腐败 = 毒 |

**不做"粗制药水"这一步**：MC 里它只是"必须先把水瓶变成基础药水"的前置点击，
本版没有下界疣，硬插一步只是多一次没有决策量的操作。

## 效果一律写成"给定效果表算一个数"的纯函数

于是每条效果都能**精确断言**（不是"喝了好像快了点"）：
移速倍率、攻击加成、受伤倍率、持续掉血速率 —— 内核只负责在正确的时机取这些数。

## 一条必须写明的规则：抗性**不减饥饿伤害**

`kernel.hurt()` 是所有伤害的唯一入口（生物、摔落、饿死都走它）。受伤倍率如果无脑
乘上去，饥饿就永远杀不死人 —— "饿不死"是个比"抗性太强"更难查的 bug。
所以 `damage_scale()` 只在 `hurt()` 里对**非饥饿**伤害生效（见 `kernel.hurt`）。
"""
from __future__ import annotations

__all__ = [
    'Effect', 'EFFECTS', 'EFFECT_ORDER', 'POTION_OF', 'POTION_NAMES',
    'Brew', 'BREWS', 'BREW_TIME', 'brew_by_ingredient', 'brew_by_output',
    'speed_mult', 'damage_bonus', 'damage_scale', 'dot_rate',
    'instant_heal', 'describe_effects', 'active_order',
    'BOTTLE_FROM_GLASS', 'SUGAR_FROM_WHEAT',
]

# ==================================================================== 效果表
class Effect:
    """一个药水效果。

    * `kind='instant'`：喝下去的瞬间结算（治疗），不留在效果表里；
    * `kind='timed'`：留 `duration` 秒，每帧按 `kernel._potion_step` 递减。

    四个"数值字段"各自独立，都不要就写 0 —— 这样 `speed_mult` 这些查询函数
    只做"取最大值/最小值"，不必知道有哪些效果存在。
    """

    __slots__ = ('name', 'title', 'kind', 'duration', 'heal', 'speed',
                 'damage', 'damage_scale', 'dot', 'color')

    def __init__(self, name, title, kind='timed', *, duration=0.0, heal=0.0,
                 speed=1.0, damage=0.0, damage_scale=1.0, dot=0.0, color=()):
        self.name = name
        self.title = title
        self.kind = kind
        self.duration = float(duration)
        self.heal = float(heal)
        self.speed = float(speed)
        self.damage = float(damage)
        self.damage_scale = float(damage_scale)
        self.dot = float(dot)
        self.color = tuple(color)

    def __repr__(self):
        return f'<Effect {self.name} {self.kind}>'


#: 效果表。顺序即 HUD 里的展示顺序（也让日志可读、可对拍）。
EFFECT_ORDER = ('healing', 'swiftness', 'strength', 'resistance', 'poison')

EFFECTS = {
    'healing': Effect('healing', '治疗', 'instant', heal=6.0,
                      color=(0.94, 0.36, 0.52)),
    'swiftness': Effect('swiftness', '迅捷', duration=30.0, speed=1.4,
                        color=(0.36, 0.86, 0.92)),
    'strength': Effect('strength', '力量', duration=30.0, damage=2.0,
                       color=(0.92, 0.42, 0.24)),
    'resistance': Effect('resistance', '抗性', duration=30.0, damage_scale=0.6,
                         color=(0.42, 0.60, 0.94)),
    'poison': Effect('poison', '剧毒', duration=10.0, dot=1.0,
                     color=(0.42, 0.72, 0.36)),
}

assert set(EFFECT_ORDER) == set(EFFECTS)

#: 药水物品名 → 效果名（药水与效果**一一对应**，不做"一瓶多效"）
POTION_OF = {
    'healing_potion': 'healing',
    'swiftness_potion': 'swiftness',
    'strength_potion': 'strength',
    'resistance_potion': 'resistance',
    'poison_potion': 'poison',
}
POTION_NAMES = tuple(POTION_OF)
assert set(POTION_OF.values()) == set(EFFECTS)

# ==================================================================== 纯函数
def speed_mult(effects) -> float:
    """移动速度倍率（多种效果取**最大**，不叠乘 —— 叠乘会指数爆炸）。"""
    if not effects:
        return 1.0
    return max([EFFECTS[n].speed for n in effects if n in EFFECTS] or [1.0])


def damage_bonus(effects) -> float:
    """攻击伤害的加法加成（取最大）。"""
    if not effects:
        return 0.0
    return max([EFFECTS[n].damage for n in effects if n in EFFECTS] or [0.0])


def damage_scale(effects) -> float:
    """受到的伤害倍率（多种效果取**最小** = 减伤最强的那条）。"""
    if not effects:
        return 1.0
    return min([EFFECTS[n].damage_scale for n in effects if n in EFFECTS] or [1.0])


def dot_rate(effects) -> float:
    """持续掉血速率（点/秒）。多条**相加**（中毒不叠加的模型更复杂，本版不做）。"""
    if not effects:
        return 0.0
    return sum(EFFECTS[n].dot for n in effects if n in EFFECTS)


def instant_heal(effect_name: str) -> float:
    """瞬时治疗量；不是瞬时效果 ⇒ 0。"""
    e = EFFECTS.get(effect_name)
    return 0.0 if e is None or e.kind != 'instant' else e.heal


def active_order(effects, now=0.0):
    """效果表 → 按 `EFFECT_ORDER` 排好的 `(名字, 剩余秒)` 列表（HUD / 日志用）。"""
    if not effects:
        return []
    out = []
    for n in EFFECT_ORDER:
        left = float(effects.get(n, 0.0)) if isinstance(effects, dict) else 0.0
        if left > 0.0:
            out.append((n, left))
    return out


def describe_effects(effects) -> str:
    """`{效果名: 剩余秒}` → 一行中文（HUD / CLI 用）。空 ⇒ `'无'`。"""
    items = active_order(effects)
    if not items:
        return '无'
    return ' · '.join(f'{EFFECTS[n].title} {s:.0f}s' for n, s in items)


# ==================================================================== 酿造
class Brew:
    """一条酿造配方：**水瓶 + 材料 → 药水**（`time` 秒）。"""

    __slots__ = ('id', 'ingredient', 'output', 'count', 'time', 'note')

    def __init__(self, id, ingredient, output, count=1, time=8.0, note=''):
        self.id = id
        self.ingredient = ingredient
        self.output = output
        self.count = int(count)
        self.time = float(time)
        self.note = note

    def __repr__(self):
        return f'<Brew {self.ingredient} -> {self.output}({self.time:.0f}s)>'


#: 一炉的基准耗时（秒）。**统一值**：不同药水用不同耗时只会让"为什么这瓶更慢"
#: 变成没有信息量的差异（材料稀有度已经体现了价值）。
BREW_TIME = 8.0

BREWS = tuple(
    Brew(f'{effect}_potion', ing, f'{effect}_potion', 1, BREW_TIME, note)
    for effect, ing, note in (
        ('healing', 'gold_ingot', '贵重 = 治愈'),
        ('swiftness', 'sugar', '糖 = 迅捷（与 MC 同款）'),
        ('strength', 'coal', '炽热 = 力量（对应 MC 的烈焰粉）'),
        ('resistance', 'iron_ingot', '铁 = 护甲'),
        ('poison', 'rotten_flesh', '腐败 = 毒'),
    )
)
_BY_ING = {b.ingredient: b for b in BREWS}
_BY_OUT = {b.output: b for b in BREWS}
assert len(_BY_ING) == len(BREWS) and len(_BY_OUT) == len(BREWS), '酿造表有重复'


def brew_by_ingredient(name: str):
    """按材料找配方（放进去的东西决定出什么）。"""
    return _BY_ING.get(str(name))


def brew_by_output(name: str):
    """按产出找配方（自检用）。"""
    return _BY_OUT.get(str(name))


#: 玻璃瓶的合成：3 玻璃 → 3 瓶（写在这里是给单测/文档当"数据来源"，
#: 真正的配方登记在 `recipes.py`）
BOTTLE_FROM_GLASS = (3, 3)
#: 糖的合成：1 麦子 → 2 糖（本世界没有甘蔗，用麦子代 —— 如实写明）
SUGAR_FROM_WHEAT = (1, 2)
