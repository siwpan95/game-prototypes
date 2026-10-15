# -*- coding: utf-8 -*-
"""方块表：id ↔ 定义 ↔ 贴图，以及**面剔除规则**（纯数据 + 纯函数，零 GL）。

设计取舍
--------
* **id 是稳定的公开契约**（存档里存的就是 id）：只追加、不改号 —— 与引擎侧
  「编号是引用契约」同一条纪律。新增方块往 100 号段往后排。
* **贴图按"面"声明**：`Block.tex` 可以是单个名字（六面同图），也可以是
  `{'top':…, 'bottom':…, 'side':…}`。草方块就是典型（顶草、侧草边、底泥土）。
* **剔除规则分三档**（`face_visible`）：不透明邻居全挡；同种透明块互相挡
  （水面之间不产生内部面）；其余透明块不挡。
* 这里**只管数据与规则**；UV 怎么算在 `mesh.py`（走引擎的 `texproj`），
  像素怎么来在 `textures.py`。
"""
from __future__ import annotations

from ._engine import blocks as _b

__all__ = [
    'AIR', 'STONE', 'DIRT', 'GRASS', 'SAND', 'WATER', 'LOG', 'LEAVES',
    'PLANKS', 'GLASS', 'COBBLE', 'BRICK', 'SNOW', 'GRAVEL',
    'CRAFTING_TABLE', 'FURNACE', 'COAL_ORE', 'IRON_ORE', 'GOLD_ORE',
    'DIAMOND_ORE', 'BEDROCK', 'TORCH',
    'BLOCKS', 'BLOCK_NAMES', 'BLOCK_IDS', 'by_id', 'by_name', 'name_of', 'all_blocks',
    'is_solid', 'is_liquid', 'is_transparent', 'tile_for_face',
    'faces_of', 'face_visible', 'DEFAULT_HOTBAR', 'MAX_ID',
]

#: 引擎的 AIR 约定值（=0），我们复用同一套编号语义
AIR = _b.AIR

# ---------------------------------------------------------------- id 常量
#: 0 = 空气（引擎约定）。**只追加不改号**（存档契约）。
STONE = 1
DIRT = 2
GRASS = 3
SAND = 4
WATER = 5
LOG = 6
LEAVES = 7
PLANKS = 8
GLASS = 9
COBBLE = 10
BRICK = 11
SNOW = 12
GRAVEL = 13
CRAFTING_TABLE = 14
FURNACE = 15
COAL_ORE = 16
IRON_ORE = 17
BEDROCK = 18
TORCH = 19
# Phase 2-C 新增（**id 只追加不改号** —— 存档按方块名存，重排 id 会读坏老档）
GOLD_ORE = 20
DIAMOND_ORE = 21

#: 本项目用到的 id 上界（校验 / 数组尺寸用）
MAX_ID = 31


class Block:
    """一个方块的定义。`tex` 为单名或 `{'top'/'bottom'/'side'}` 三向映射。"""

    __slots__ = ('id', 'name', 'title', 'solid', 'opaque', 'liquid',
                 'emissive', 'tex', 'hardness')

    def __init__(self, id, name, title, tex, *, solid=True, opaque=True,
                 liquid=False, emissive=0.0, hardness=1.0):
        self.id = int(id)
        self.name = name
        self.title = title
        self.tex = tex
        self.solid = bool(solid)          # 会挡住行走（物理用）
        self.opaque = bool(opaque)        # 会挡住**视线/面**（网格剔除用）
        self.liquid = bool(liquid)
        self.emissive = float(emissive)
        self.hardness = float(hardness)   # 挖掘耗时系数（Phase 1 工具用）

    def tile(self, face: str) -> str:
        """该面用哪个贴图名。`face` ∈ top/bottom/side（或 w/e/n/s 归一化成 side）。"""
        if isinstance(self.tex, str):
            return self.tex
        key = face if face in self.tex else 'side'
        return self.tex[key]

    def __repr__(self):
        return f'<Block {self.id} {self.name}>'


# ---------------------------------------------------------------- 方块表
def _defs():
    """方块定义表（顺序即 id 顺序，便于人眼核对）。"""
    out = []
    add = out.append
    add(Block(STONE, 'stone', '石头', 'stone'))
    add(Block(DIRT, 'dirt', '泥土', 'dirt'))
    add(Block(GRASS, 'grass', '草方块',
              {'top': 'grass_top', 'side': 'grass_side', 'bottom': 'dirt'}))
    add(Block(SAND, 'sand', '沙子', 'sand'))
    add(Block(WATER, 'water', '水', 'water',
              solid=False, opaque=False, liquid=True))
    add(Block(LOG, 'log', '原木',
              {'top': 'log_top', 'bottom': 'log_top', 'side': 'log_side'}))
    add(Block(LEAVES, 'leaves', '树叶', 'leaves', opaque=False, hardness=0.4))
    add(Block(PLANKS, 'planks', '木板', 'planks'))
    add(Block(GLASS, 'glass', '玻璃', 'glass', opaque=False, hardness=0.5))
    add(Block(COBBLE, 'cobble', '圆石', 'cobble'))
    add(Block(BRICK, 'brick', '砖块', 'brick'))
    add(Block(SNOW, 'snow', '雪', 'snow'))
    add(Block(GRAVEL, 'gravel', '砂砾', 'gravel'))
    add(Block(CRAFTING_TABLE, 'crafting_table', '工作台',
              {'top': 'craft_top', 'side': 'craft_side', 'bottom': 'planks'}))
    add(Block(FURNACE, 'furnace', '熔炉',
              {'top': 'furnace_top', 'side': 'furnace_side', 'bottom': 'furnace_top'}))
    add(Block(COAL_ORE, 'coal_ore', '煤矿石', 'coal_ore'))
    add(Block(IRON_ORE, 'iron_ore', '铁矿石', 'iron_ore'))
    add(Block(GOLD_ORE, 'gold_ore', '金矿石', 'gold_ore', hardness=1.6))
    add(Block(DIAMOND_ORE, 'diamond_ore', '钻石矿石', 'diamond_ore', hardness=2.2))
    add(Block(BEDROCK, 'bedrock', '基岩', 'bedrock', hardness=999.0))
    add(Block(TORCH, 'torch', '火把', 'torch',
              solid=False, opaque=False, emissive=0.9))
    return out


#: id → Block
BLOCKS = {b.id: b for b in _defs()}
#: name → Block（按名字查，用于配置 / 命令 / 存档兼容）
BLOCK_NAMES = {b.name: b for b in BLOCKS.values()}
#: 名字 → id（存档与配置里写名字，避免把 id 烤进人类可读的文件）。
#: ⚠ **空气也要在里面**：挖掉方块留下的就是空气，存档必须能表达"这里被挖空了"。
BLOCK_IDS = {b.name: b.id for b in BLOCKS.values()}
BLOCK_IDS['air'] = AIR

assert AIR not in BLOCKS, '空气不该有定义（它由 0 表示）'


def name_of(block_id: int) -> str:
    """id → 名字（**任何 id 都有名字**，含空气与未知 id）。

    存在的理由是一个真 bug（2026-10-14 实测）：存档 dump 里对"挖掉后的空气"
    调 `by_id(b).name` 会拿到 `None.name` ⇒ AttributeError。
    名字映射必须是**全定义**的 —— 存档路径上不允许出现"某些 id 没有名字"。
    未知 id 返回 `unknown:<id>`，读档时会被当成未知名字**响亮报错**，而不是静默丢格。
    """
    b = BLOCKS.get(int(block_id))
    if b is not None:
        return b.name
    return 'air' if int(block_id) == AIR else f'unknown:{int(block_id)}'


def by_id(block_id: int) -> Block:
    """按 id 取定义；空气/未知返回 None（调用方自己决定怎么处理）。"""
    return BLOCKS.get(int(block_id))


def by_name(name: str) -> Block:
    """按名字取定义；未知抛 KeyError（配置里写错名字要当场爆）。"""
    try:
        return BLOCK_NAMES[name]
    except KeyError:
        raise KeyError(f'未知方块名 {name!r}；合法名字：{sorted(BLOCK_NAMES)}') from None


def all_blocks():
    """全部方块定义（按 id 升序）。"""
    return [BLOCKS[k] for k in sorted(BLOCKS)]


# ---------------------------------------------------------------- 属性判据
def is_solid(block_id: int) -> bool:
    """是否挡住行走（空气与液体不算）。"""
    b = BLOCKS.get(int(block_id))
    return bool(b and b.solid)


def is_liquid(block_id: int) -> bool:
    b = BLOCKS.get(int(block_id))
    return bool(b and b.liquid)


def is_transparent(block_id: int) -> bool:
    """是否透明（空气算透明 —— 它什么都不挡）。"""
    if int(block_id) == AIR:
        return True
    b = BLOCKS.get(int(block_id))
    return True if b is None else (not b.opaque)


# ---------------------------------------------------------------- 面与剔除
#: 六个面 → 法向 + 该面属于哪个贴图槽
FACES = (
    ('+x', (1, 0, 0), 'side'),
    ('-x', (-1, 0, 0), 'side'),
    ('+y', (0, 1, 0), 'top'),
    ('-y', (0, -1, 0), 'bottom'),
    ('+z', (0, 0, 1), 'side'),
    ('-z', (0, 0, -1), 'side'),
)
FACE_NORMAL = {n: d for n, d, _ in FACES}
FACE_SLOT = {n: s for n, _, s in FACES}
FACE_ORDER = tuple(n for n, _, _ in FACES)


def faces_of(block_id: int):
    """该方块要画哪些面（火把这类非立方体先行只画四侧 + 顶）。"""
    if int(block_id) == TORCH:
        return ('+x', '-x', '+z', '-z', '+y')
    return FACE_ORDER


def tile_for_face(block_id: int, face: str) -> str:
    """该方块该面用哪个贴图名（未知方块 ⇒ 空串，调用方跳过）。"""
    b = BLOCKS.get(int(block_id))
    return '' if b is None else b.tile(FACE_SLOT[face])


def face_visible(block_id: int, neighbor_id: int) -> bool:
    """`block_id` 朝向 `neighbor_id` 的那一面**是否需要画**。

    三档规则（与 MC 手感一致，且是**纯函数** ⇒ 单测可穷举）：
    1. 邻居不透明（且不是空气）⇒ 挡死，不画；
    2. 邻居与自己是**同一种透明块**（水挨水、玻璃挨玻璃）⇒ 挡死
       （否则水面内部全是面，面数翻十几倍且混合出脏边）；
    3. 其余（空气、异种透明块）⇒ 画。
    """
    n = int(neighbor_id)
    if n == AIR:
        return True
    if not is_transparent(n):
        return False
    return n != int(block_id)


#: 默认 hotbar（名字形态，配置树与 demo 共用）
DEFAULT_HOTBAR = (
    'grass', 'dirt', 'stone', 'sand', 'log', 'planks', 'glass', 'cobble', 'brick',
)
