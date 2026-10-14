# -*- coding: utf-8 -*-
"""物品、工具与挖掘规则（纯数据 + 纯函数，零 GL）。

## 与方块表的关系（**这是本模块最容易搞混的地方**）

Phase 0 把"方块"同时当物品用（`inventory` 是 `{block_id: count}`）。
Phase 1 引入**真正的物品 id 空间**，于是有两套编号并存：

| | 编号空间 | 谁用 | 越界会怎样 |
| --- | --- | --- | --- |
| **方块** | `blocks.py`：1..31 | 世界里的那一格 | 世界读出来必是方块 |
| **物品** | 本文件：**100 起** | 背包 / 掉落物 / 配方 | 100 以下一定是方块，100 以上一定不是 |

**为什么把物品排在 100 起**：这样"一个整数到底是方块还是物品"**只看数值就能判**，
不必再带一个类型标记。存档里两者都按**名字**存，所以重排编号也不会读坏旧档。

## 工具：为什么单独建模

堆叠物品可以写成 `{item: count}`，但**工具带状态**（耐久）——
把耐久压在堆叠计数里就再也表达不了"两把镐各挖了一半"。
所以背包里工具是 `ToolStack(item_id, durability)`（`count` 恒为 1）。

## 挖掘耗时：`break_time()`

```
t = hardness × (5 if 需要工具且手上没有对路工具 else 1) / 工具速度
```

* **对路**（镐挖石头 / 斧砍木头 / 铲挖土 / 剑砍草叶）⇒ 速度按 tier 递增；
* **不对路**（徒手、或用错工具）⇒ 速度 1，且石类**慢 5 倍**（MC 的"徒手挖石头几乎没戏"）；
* 基岩 `hardness=999` ⇒ 任何工具都挖不动（沿用 Phase 0 判据）。

数值口径故意做成**可对拍**：单测直接拿公式算一遍与函数比，而不是"看起来合理"。
"""
from __future__ import annotations

from .blocks import (AIR, BEDROCK, BLOCKS, BRICK, COAL_ORE, COBBLE, CRAFTING_TABLE,
                     DIRT, FURNACE, GLASS, GRASS, GRAVEL, IRON_ORE, LEAVES, LOG,
                     PLANKS, SAND, SNOW, STONE, TORCH, WATER, by_id, by_name, name_of)

__all__ = [
    'ITEM_BASE', 'KIND_BLOCK', 'KIND_MATERIAL', 'KIND_TOOL', 'KIND_FOOD',
    'TOOL_SPEED', 'TOOL_TIER_NAME', 'TOOL_KINDS',
    'Item', 'ITEMS', 'ITEMS_BY_NAME', 'item', 'item_by_name', 'name_of_item',
    'name_of', 'is_item_id', 'is_block_id', 'all_items', 'blocks_as_items',
    'break_time', 'can_break', 'harvest_ok', 'TOOL_DURABILITY',
    'tools_of_tier', 'describe',
]

#: 物品 id 从这里开始（**100 以下一定是方块** —— 判据只看数值）
ITEM_BASE = 100

KIND_BLOCK = 'block'
KIND_MATERIAL = 'material'
KIND_TOOL = 'tool'
KIND_FOOD = 'food'

#: 工具种类（对路的方块类型见 `Item.mines`）
TOOL_KINDS = ('pickaxe', 'axe', 'shovel', 'sword')

#: 等级名（1 木 / 2 石 / 3 铁）
TOOL_TIER_NAME = {1: '木', 2: '石', 3: '铁'}

#: 各等级工具的速度倍率（挖"对路"方块时）
TOOL_SPEED = {0: 1.0, 1: 2.0, 2: 4.0, 3: 6.0}

#: 各等级工具的耐久（与 MC 同量级但不照抄）
TOOL_DURABILITY = {1: 60, 2: 132, 3: 251}

#: "需要工具才能掉落"的方块（徒手能挖但挖了白挖）与"需要工具才挖得快"的倍数
NEEDS_TOOL_PENALTY = 5.0


class Item:
    """一个物品的定义。方块物品（`kind=KIND_BLOCK`）带 `block_id`。"""

    __slots__ = ('id', 'name', 'title', 'kind', 'stack', 'block_id',
                 'tool', 'tier', 'durability', 'mines', 'fuel', 'food', 'heal')

    def __init__(self, id, name, title, kind=KIND_MATERIAL, *, stack=64,
                 block_id=None, tool=None, tier=0, durability=0, mines=(),
                 fuel=0.0, food=0, heal=0.0):
        self.id = int(id)
        self.name = name
        self.title = title
        self.kind = kind
        self.stack = int(stack)
        self.block_id = block_id
        self.tool = tool                 # 'pickaxe' / 'axe' / ... / None
        self.tier = int(tier)
        self.durability = int(durability)
        self.mines = tuple(mines)        # 对路的方块 id（用于"挖得快"与"掉不掉落"）
        self.fuel = float(fuel)          # 熔炉燃料能烧几个（0 = 不是燃料）
        self.food = int(food)            # 吃一口回多少饥饿
        self.heal = float(heal)          # 吃一口回多少血（金苹果这类）

    # ---------------------------------------------------------------- 判据
    @property
    def is_tool(self):
        return self.kind == KIND_TOOL

    @property
    def is_block(self):
        return self.kind == KIND_BLOCK

    @property
    def max_stack(self):
        """工具不可堆叠（它带耐久状态）。"""
        return 1 if self.is_tool else self.stack

    def mines_block(self, block_id: int) -> bool:
        """这个工具是否**对路**于某方块。"""
        return int(block_id) in self.mines

    def __repr__(self):
        return f'<Item {self.id} {self.name}>'


# ---------------------------------------------------------------- 物品表
def _defs():
    out = []
    n = ITEM_BASE

    def add(name, title, kind=KIND_MATERIAL, **kw):
        nonlocal n
        it = Item(n, name, title, kind, **kw)
        out.append(it)
        n += 1
        return it

    # --- 方块物品：Phase 0 的 hotbar 语义继续有效（放下来就是那个方块） ---
    # ⚠ 顺序即 id（只追加不改号）；名字与方块名**故意同名**（`grass` 既是方块名也是物品名），
    # 这样 hotbar / 存档 / 配置里写的东西在两边都能用同一个字符串。
    for b in (GRASS, DIRT, STONE, SAND, LOG, PLANKS, GLASS, COBBLE, BRICK,
              SNOW, GRAVEL, LEAVES, CRAFTING_TABLE, FURNACE, TORCH):
        blk = by_id(b)
        add(blk.name, blk.title, KIND_BLOCK, block_id=b, stack=64)

    # --- 材料（挖出来/烧出来的中间物） ---
    add('stick', '木棍')
    add('coal', '煤炭', fuel=8.0)
    add('charcoal', '木炭', fuel=8.0)
    add('iron_ingot', '铁锭')
    add('raw_iron', '粗铁')
    add('cobble_shard', '碎石')          # 徒手挖石头"挖得动但不掉落"的反例对照物
    add('plank_scrap', '木屑')
    add('wheat', '小麦', food=5)
    add('apple', '苹果', KIND_FOOD, food=4, heal=0.0)
    add('bread', '面包', KIND_FOOD, food=6)
    add('cooked_meat', '熟肉', KIND_FOOD, food=8, heal=1.0)
    add('rotten_flesh', '腐肉', KIND_FOOD, food=2)

    # --- 工具：木/石/铁 三档 × 四类 ---
    # 耐久与速度来自 TOOL_DURABILITY / TOOL_SPEED（表驱动，改数值只改一处）
    pick_mines = (STONE, COBBLE, COAL_ORE, IRON_ORE, BRICK, FURNACE, GLASS)
    axe_mines = (LOG, PLANKS, CRAFTING_TABLE)
    shovel_mines = (DIRT, GRASS, SAND, GRAVEL, SNOW)
    sword_mines = (LEAVES,)
    for tier, mat in ((1, 'wooden'), (2, 'stone'), (3, 'iron')):
        label = TOOL_TIER_NAME[tier]
        dur = TOOL_DURABILITY[tier]
        for kind, mines, noun in ((('pickaxe'), pick_mines, '镐'),
                                  (('axe'), axe_mines, '斧'),
                                  (('shovel'), shovel_mines, '铲'),
                                  (('sword'), sword_mines, '剑')):
            add(f'{mat}_{kind}', f'{label}{noun}', KIND_TOOL, stack=1, tool=kind,
                tier=tier, durability=dur, mines=mines)
    return out


#: id → Item
ITEMS = {it.id: it for it in _defs()}
#: 物品名 → Item
ITEMS_BY_NAME = {it.name: it for it in ITEMS.values()}

assert min(ITEMS) >= ITEM_BASE, '物品 id 不许落到方块编号区间（100 以下留给方块）'
_names = [it.name for it in ITEMS.values()]
assert len(_names) == len(set(_names)), f'物品名重复：{_names}'


def is_item_id(v) -> bool:
    """这个整数是不是**物品** id（判据：≥ ITEM_BASE）。"""
    return isinstance(v, int) and v >= ITEM_BASE


def is_block_id(v) -> bool:
    """这个整数是不是**方块** id（判据：0..ITEM_BASE）。"""
    return isinstance(v, int) and 0 <= v < ITEM_BASE


def item(item_id: int) -> Item:
    """按 id 取物品；未知抛 KeyError（配置/存档写错要当场爆）。"""
    try:
        return ITEMS[int(item_id)]
    except KeyError:
        raise KeyError(f'未知物品 id {item_id!r}') from None


def item_by_name(name: str) -> Item:
    """按名字取物品；未知抛 KeyError。"""
    try:
        return ITEMS_BY_NAME[name]
    except KeyError:
        raise KeyError(f'未知物品名 {name!r}；合法名字见 items.all_items()') from None


def name_of_item(item_id: int) -> str:
    """id → 名字（**全定义**：未知 id 返回 `unknown:<id>`，存档路径上不许出现 None）。"""
    it = ITEMS.get(int(item_id))
    return it.name if it is not None else f'unknown:{int(item_id)}'


#: 简写别名（内核里高频使用；与 `blocks.name_of` 对称）
name_of = name_of_item


def all_items():
    """全部物品（按 id 升序）。"""
    return [ITEMS[k] for k in sorted(ITEMS)]


def blocks_as_items():
    """方块名 → 物品（`grass` 这类两边同名的，取物品那一份）。"""
    return {it.name: it for it in ITEMS.values() if it.is_block}


def tools_of_tier(tier: int):
    """某等级的全部工具（配方自检用）。"""
    return [it for it in all_items() if it.is_tool and it.tier == int(tier)]


def describe(item_id: int) -> str:
    """一行描述（HUD 与 CLI 共用）。"""
    it = ITEMS.get(int(item_id))
    if it is None:
        return name_of_item(item_id)
    if it.is_tool:
        return f'{it.title}（{it.tool}·{TOOL_TIER_NAME.get(it.tier, it.tier)}·耐久 {it.durability}）'
    if it.is_block:
        return f'{it.title}（方块）'
    if it.kind == KIND_FOOD:
        return f'{it.title}（食物 +{it.food}）'
    return it.title


# ---------------------------------------------------------------- 挖掘规则
def harvest_ok(block_id: int, tool: Item | None) -> bool:
    """这个方块**在当前工具下会不会掉落**。

    规则（与 MC 手感一致，且**逐条可穷举**）：
    * 基岩 → 永不掉落（也挖不动）；
    * 水/空气 → 没有掉落概念；
    * 需要工具的方块（石/矿石/砖/熔炉/玻璃）→ 必须**对路工具**（pickaxe）；
    * 其余（土/沙/木/叶…）→ 徒手也掉。
    """
    b = int(block_id)
    if b in (AIR, WATER, BEDROCK):
        return False
    if b in (STONE, COBBLE, COAL_ORE, IRON_ORE, BRICK, FURNACE, GLASS):
        return bool(tool and tool.is_tool and tool.mines_block(b))
    return True


def can_break(block_id: int) -> bool:
    """这个方块能不能被破坏（基岩不能）。"""
    return int(block_id) not in (AIR, WATER, BEDROCK)


def break_time(block_id: int, tool: Item | None = None,
               hardness: float | None = None) -> float:
    """挖掉这个方块要多少秒（**纯函数**，单测按公式逐条对拍）。

    ```
    t = hardness × (5 if 需要工具且手上没有对路工具 else 1) / 工具速度
    ```
    """
    b = int(block_id)
    if b in (AIR, WATER):
        return 0.0
    blk = BLOCKS.get(b)
    h = float(blk.hardness) if hardness is None else float(hardness)
    if b == BEDROCK:
        return float('inf')                    # 挖不动（内核也会拒，这里是第二道闸）
    speed = 1.0
    if tool is not None and tool.is_tool and tool.mines_block(b):
        speed = TOOL_SPEED.get(tool.tier, 1.0)
    elif b in (STONE, COBBLE, COAL_ORE, IRON_ORE, BRICK, FURNACE, GLASS):
        # 石类：没有对路工具 ⇒ 慢 5 倍（MC 的"徒手挖石头几乎没戏"）
        speed = 1.0 / NEEDS_TOOL_PENALTY
    return max(0.0, h / max(1e-6, speed))
