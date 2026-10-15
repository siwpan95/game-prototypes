# -*- coding: utf-8 -*-
"""掉落规则与合成配方（纯数据 + 纯函数，零 GL）。

## 为什么掉落单独成模块

"挖了这个方块得到什么"是**游戏平衡**的事，不该散落在内核的 `dig()` 里：
内核只问 `drops_for(block, tool)`，规则改了不用碰玩法代码。
Phase 0 的"挖了就进背包"是简化；Phase 1 起"挖"与"得到"分开（中间有掉落物实体）。

## 配方表：**数据**，且带反向自检

`recipes.py` 的每条配方都必须能被它的输入合成出来 —— `cli.py` 里有
「配方可合成性自检」，逐条用假背包验证，防"写了配方但永远做不出来"这种死数据。
"""
from __future__ import annotations

from . import items as I
from .blocks import (BEDROCK, BLOCK_ITEM_ALIAS, BRICK, BUTTON_OFF, BUTTON_ON,
                     COAL_ORE, COBBLE, CRAFTING_TABLE, CROP, DIAMOND_ORE, DIRT,
                     DOOR_LOWER, DOOR_OPEN_LOWER, DOOR_OPEN_UPPER, DOOR_UPPER,
                     ENCHANT_TABLE, FURNACE, GLASS, GOLD_ORE, GRASS, GRAVEL,
                     IRON_ORE, LAMP_OFF, LAMP_ON, LEAVES, LEVER_OFF, LEVER_ON,
                     LOG, PISTON_ARM, PISTON_STATES, PLANKS, REDSTONE_TORCH,
                     REDSTONE_WIRE, REPEATER_OFF, REPEATER_ON, SAND, SNOW, STONE,
                     TORCH, WATER, name_of)

__all__ = ['drops_for', 'Recipe', 'RECIPES', 'recipe_by_id', 'recipes_for',
           'craftable', 'craft', 'consume', 'smelt_recipes', 'craft_recipes',
           'as_item', 'output_item', 'rand01']

# ---------------------------------------------------------------- id 解析
#: 方块名 → 物品（同名规则：`grass` 既是方块名也是物品名）
_BLOCK_ITEM = {it.block_id: it for it in I.all_items() if it.is_block}


def as_item(block_id: int):
    """方块 id → 对应的物品（放下来是方块的那个）。没有对应物品时返回 None。

    Phase 3：**状态 id 会回退到别名**（`lever_on` → `lever`）——
    否则"挖掉开着的拉杆"会什么都不掉（`_BLOCK_ITEM` 里只有关状态的 id）。
    """
    i = int(block_id)
    it = _BLOCK_ITEM.get(i)
    if it is not None:
        return it
    alias = BLOCK_ITEM_ALIAS.get(name_of(i))
    return I.ITEMS_BY_NAME.get(alias) if alias else None


def output_item(block_id: int, fallback_name: str):
    """掉落的物品：优先用同名物品，没有就用 `fallback_name` 指定的材料。"""
    it = as_item(block_id)
    return it if it is not None else I.item_by_name(fallback_name)


# ---------------------------------------------------------------- 掉落
#: 方块 → (物品名, 数量下限, 数量上限)。**名字而不是 id**：与存档口径一致。
DROP_TABLE = {
    GRASS: ('dirt', 1, 1),          # 草方块挖掉掉泥土（MC 同款）
    DIRT: ('dirt', 1, 1),
    SAND: ('sand', 1, 1),
    GRAVEL: ('gravel', 1, 1),
    SNOW: ('snow', 1, 1),
    LOG: ('log', 1, 1),
    PLANKS: ('planks', 1, 1),
    GLASS: (None, 0, 0),            # 玻璃：挖了什么都不掉（MC 同款，只能烧）
    LEAVES: (None, 0, 0),           # 树叶：见下（低概率掉树苗，这里用 'apple' 代替树苗）
    COBBLE: ('cobble', 1, 1),
    BRICK: ('brick', 1, 1),
    STONE: ('cobble', 1, 1),        # 石头挖掉变圆石（**且必须带镐**）
    COAL_ORE: ('coal', 1, 2),
    IRON_ORE: ('raw_iron', 1, 1),
    # Phase 2-C：金/钻石**只掉 1 个**（越深越稀有，掉 2 个会让"深度分层"白做）
    GOLD_ORE: ('raw_gold', 1, 1),
    DIAMOND_ORE: ('diamond', 1, 1),
    CRAFTING_TABLE: ('crafting_table', 1, 1),
    FURNACE: ('furnace', 1, 1),
    # 火把：挖掉掉回自己（它是"放下去的光源"，回收是合理的）
    TORCH: ('torch', 1, 1),
    # 作物：打掉掉小麦（村庄农田的**玩法闭环** —— 收麦 → 3 麦烤 1 面包）
    CROP: ('wheat', 1, 2),
    # ---- Phase 3：红石元件（每种状态都掉回**同一件东西**）----
    REDSTONE_WIRE: ('redstone_wire', 1, 1),
    LEVER_OFF: ('lever', 1, 1), LEVER_ON: ('lever', 1, 1),
    BUTTON_OFF: ('button', 1, 1), BUTTON_ON: ('button', 1, 1),
    REDSTONE_TORCH: ('redstone_torch', 1, 1),
    REPEATER_OFF: ('repeater', 1, 1), REPEATER_ON: ('repeater', 1, 1),
    LAMP_OFF: ('lamp', 1, 1), LAMP_ON: ('lamp', 1, 1),
    DOOR_LOWER: ('door', 1, 1), DOOR_UPPER: ('door', 1, 1),
    DOOR_OPEN_LOWER: ('door', 1, 1), DOOR_OPEN_UPPER: ('door', 1, 1),
    PISTON_ARM: ('piston', 1, 1),
    # Phase 3-E：附魔台挖掉掉回自己（它可以合成，回收是合理的）
    ENCHANT_TABLE: ('enchant_table', 1, 1),
}
#: 活塞的 12 个状态也各掉一个活塞（表是生成的 —— 手写 12 行太容易漏）
for _n, _off, _on in PISTON_STATES:
    DROP_TABLE[_off] = ('piston', 1, 1)
    DROP_TABLE[_on] = ('piston', 1, 1)
del _n, _off, _on

#: 树叶的"偶发掉落"（树叶本身不掉，但有小概率掉苹果 —— 这里当"树苗/果子"用）
LEAVES_RARE = ('apple', 1, 1, 0.25)     # (物品名, 下限, 上限, 概率)


def _rand01(seed_parts):
    """确定性 [0,1)：用**坐标 + 世界种子**做哈希，不用 `random`。

    为什么：掉落数量与概率必须**可复现**（录制/回放/对拍都靠这条），
    `random` 的全局状态会让"同一次挖掘"在不同运行里给出不同结果。
    """
    h = 0
    for i, a in enumerate(seed_parts):
        h = (h * 131 + int(a) * (7 + i * 13)) & 0x7FFFFFFF
    import math
    return (math.sin(h * 0.0001 + 12.9898) * 43758.5453) % 1.0


#: 公开别名。`enchant.offers()` 也要用**同一套**确定性哈希 ——
#: 各写一份的后果是"掉落可复现、附魔报价不可复现"，而且两份迟早会漂开。
rand01 = _rand01


def drops_for(block_id: int, tool=None, *, seed_parts=(0, 0, 0)):
    """挖掉这个方块的掉落列表 `[(item_id, count), ...]`（纯函数，确定性）。

    `tool` 是 `Item`（或 None）；"要不要工具"的判据集中在 `items.harvest_ok`，
    这里只负责"掉什么、掉几个"—— **两个问题分开，改一个不会碰另一个**。
    """
    b = int(block_id)
    if b in (0, WATER, BEDROCK):
        return []
    if not I.harvest_ok(b, tool):
        return []                                   # 工具不对 ⇒ 挖了白挖
    if b == LEAVES:
        name, lo, hi, prob = LEAVES_RARE
        return [(I.item_by_name(name).id, 1)] if _rand01(list(seed_parts) + [b]) < prob else []
    row = DROP_TABLE.get(b)
    if row is None:
        it = as_item(b)
        return [(it.id, 1)] if it is not None else []
    name, lo, hi = row
    if name is None:
        return []
    n = lo if hi <= lo else lo + int(_rand01(list(seed_parts) + [b]) * (hi - lo + 1))
    n = max(lo, min(hi, n))
    return [(I.item_by_name(name).id, n)] if n > 0 else []


# ---------------------------------------------------------------- 配方
class Recipe:
    """一条配方。

    * `kind='craft'`：`inputs` 是 `{物品名: 数量}` ⇒ 无序配方（先做无序，
      有序 3×3 摆放等到有 UI 再做 —— 见 `docs/phase1_设计.md` §五）；
    * `kind='smelt'`：`inputs` 形如 `{'raw_iron': 1, 'coal|charcoal': 1}`，
      后者是**可替换输入**（任一满足即可）；`time` 是烧炼秒数。
    """

    __slots__ = ('id', 'kind', 'inputs', 'output', 'count', 'time', 'note')

    def __init__(self, id, kind, inputs, output, count=1, time=0.0, note=''):
        self.id = id
        self.kind = kind
        self.inputs = dict(inputs)
        self.output = output
        self.count = int(count)
        self.time = float(time)
        self.note = note

    def input_options(self):
        """规范化成 `[(数量, [可接受的物品名...]), ...]`。

        ⚠ `inputs` 的**键**是物品名，`|` 表示可替换（`'coal|charcoal'`）；
        **值**是数量（int）。先前把"键当数量、值当名字"写反了，
        于是 `int.split()` 当场炸 —— 这也是为什么这个函数要有单测直接调。
        """
        out = []
        for name, need in self.inputs.items():
            out.append((int(need), str(name).split('|')))
        return out

    def __repr__(self):
        return f'<Recipe {self.id} {self.kind} {self.inputs} -> {self.output}×{self.count}>'


def _crafts():
    R = []
    add = R.append
    # 木板 ← 原木（1 换 4）
    add(Recipe('planks_from_log', 'craft', {'log': 1}, 'planks', 4))
    # 木棍 ← 木板（2 换 4）
    add(Recipe('sticks_from_planks', 'craft', {'planks': 2}, 'stick', 4))
    # 工作台 ← 木板 ×4
    add(Recipe('crafting_table', 'craft', {'planks': 4}, 'crafting_table', 1))
    # 熔炉 ← 圆石 ×8
    add(Recipe('furnace', 'craft', {'cobble': 8}, 'furnace', 1))
    # 木工具 ← 木板 + 木棍
    for kind, extra in (('pickaxe', 3), ('axe', 3), ('shovel', 1), ('sword', 2)):
        add(Recipe(f'wooden_{kind}', 'craft',
                   {'planks': extra, 'stick': 2}, f'wooden_{kind}', 1,
                   note='需工作台（本版不校验位置，见 §五）'))
    # 石工具 ← 圆石 + 木棍
    for kind, extra in (('pickaxe', 3), ('axe', 3), ('shovel', 1), ('sword', 2)):
        add(Recipe(f'stone_{kind}', 'craft',
                   {'cobble': extra, 'stick': 2}, f'stone_{kind}', 1))
    # 铁工具 ← 铁锭 + 木棍
    for kind, extra in (('pickaxe', 3), ('axe', 3), ('shovel', 1), ('sword', 2)):
        add(Recipe(f'iron_{kind}', 'craft',
                   {'iron_ingot': extra, 'stick': 2}, f'iron_{kind}', 1))
    # Phase 3-E：附魔台 ← 圆石台座 + 木板 + 钻石 ×2
    # 与 MC 的"黑曜石 ×4 + 钻石 ×2 + 书"同量级：**必须下到 y<8 挖钻石**
    # （于是"附魔"与"矿脉分层/洞穴"这两套东西自然咬合，而不是凭空给一台）。
    add(Recipe('enchant_table', 'craft',
               {'cobble': 4, 'planks': 4, 'diamond': 2}, 'enchant_table', 1,
               note='钻石在 y<8（洞底）才有'))
    return R


def _smelts():
    R = []
    add = R.append
    # 燃料：煤炭 / 木炭 / 原木（原木烧得少）
    add(Recipe('iron_ingot', 'smelt', {'raw_iron': 1, 'coal|charcoal': 1},
               'iron_ingot', 1, time=10.0, note='燃料：煤或木炭'))
    add(Recipe('gold_ingot', 'smelt', {'raw_gold': 1, 'coal|charcoal': 1},
               'gold_ingot', 1, time=10.0, note='Phase 2-C：金锭（钻石 Phase 3 再加工）'))
    add(Recipe('charcoal', 'smelt', {'log': 1, 'coal|charcoal': 1},
               'charcoal', 1, time=10.0, note='木炭：烧原木'))
    add(Recipe('glass', 'smelt', {'sand': 1, 'coal|charcoal': 1},
               'glass', 1, time=8.0))
    add(Recipe('cooked_meat', 'smelt', {'rotten_flesh': 1, 'coal|charcoal': 1},
               'cooked_meat', 1, time=6.0, note='腐肉烧熟（MC 里烧不出熟肉，这里给条活路）'))
    add(Recipe('bread', 'smelt', {'wheat': 3, 'coal|charcoal': 1},
               'bread', 1, time=8.0, note='3 麦 → 1 面包'))
    return R


RECIPES = _crafts() + _smelts()
_RECIPE_BY_ID = {r.id: r for r in RECIPES}

assert len(_RECIPE_BY_ID) == len(RECIPES), '配方 id 重复'


def recipe_by_id(rid: str) -> Recipe:
    try:
        return _RECIPE_BY_ID[rid]
    except KeyError:
        raise KeyError(f'未知配方 {rid!r}') from None


def craft_recipes():
    return [r for r in RECIPES if r.kind == 'craft']


def smelt_recipes():
    return [r for r in RECIPES if r.kind == 'smelt']


def recipes_for(item_id: int):
    """能产出该物品的全部配方（UI 的"这个能做什么"用）。"""
    name = I.name_of_item(item_id)
    return [r for r in RECIPES if r.output == name]


def craftable(recipe: Recipe, have) -> bool:
    """`have` 是 `{物品名: 数量}` —— 能否合成。

    可替换输入（`a|b`）任一满足即可；**逐槽判断**（每个槽位独立看"某一种够不够"），
    所以"两个槽位都要同一种物品"的情形由 `craft()` 的真实扣减兜底
    （先判后扣用同一套循环，见 `craft()` 的实现说明）。
    """
    for need, opts in recipe.input_options():
        if not any(int(have.get(o, 0)) >= need for o in opts):
            return False
    return True


def consume(recipe: Recipe, inv) -> bool:
    """**只扣输入、不加产出**。失败时 `inv` 一点不动（要么全扣、要么不动）。

    为什么要单独有它：`craft()` 的语义是"扣输入 **+ 加产出**"，
    而熔炉装料（`kernel.furnace_load`）需要的是"先只扣料，产出等烧完再给"。
    先前内核直接借 `craft()` 当扣料工具用，于是**装炉那一刻产物就到手了**，
    烧完 `furnace_step` 再给一次 ⇒ 一炉发货两次（TEST-SMITH 实测抓出，5 条烧炼配方全中）。
    ⇒ **"扣"与"得"必须是两个入口**，这样"扣"的逻辑仍然只有一处。
    """
    trial = {k: int(v) for k, v in inv.items()}
    for need, opts in recipe.input_options():
        for o in opts:                                 # 可替换输入：按书写顺序优先
            if trial.get(o, 0) >= need:
                trial[o] -= need
                if trial[o] <= 0:
                    del trial[o]
                break
        else:
            return False                               # 这个槽位凑不出来 ⇒ 整条不动
    inv.clear()
    inv.update(trial)
    return True


def craft(recipe: Recipe, inv):
    """在 `inv`（`{物品名: 数量}`，**会被就地扣减并加上产出**）上执行合成。

    = `consume()` + 加产出。判定与扣减**用同一条循环**：
    先前写成"先 `craftable()` 再逐槽扣"，于是当两个槽位要同一种物品、
    而总量只够一个槽位时，会出现"判定说能、扣到第二个槽时不够"（半扣状态）。
    现在扣之前先复制一份试算，试算通过才真正落账 —— **要么全成、要么不动**。
    """
    if not consume(recipe, inv):
        return False
    inv[recipe.output] = int(inv.get(recipe.output, 0)) + recipe.count
    return True
