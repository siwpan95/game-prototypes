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
    'DIAMOND_ORE', 'CROP', 'BEDROCK', 'TORCH',
    'REDSTONE_WIRE', 'LEVER_OFF', 'LEVER_ON', 'BUTTON_OFF', 'BUTTON_ON',
    'REDSTONE_TORCH', 'REDSTONE_TORCH_OFF',
    'REPEATER_OFF', 'REPEATER_ON', 'LAMP_OFF', 'LAMP_ON',
    'DOOR_LOWER', 'DOOR_UPPER', 'DOOR_OPEN_LOWER', 'DOOR_OPEN_UPPER',
    'PISTON_ARM', 'PISTON_STATES', 'PISTON_BY_DIR', 'PISTON_DIR_VEC',
    'PISTON_DIR_OF', 'PISTON_TITLES', 'BLOCK_ITEM_ALIAS',
    'REPEATER_STATES', 'REPEATER_BY_DIR', 'REPEATER_DIR_OF',
    'REPEATER_DELAYS', 'REPEATER_EXTRA', 'REPEATER_BY_DIR_DELAY',
    'REPEATER_DELAY_OF', 'REPEATER_ON_OF', 'REPEATER_OFF_OF',
    'repeater_delay', 'repeater_cycle_delay',
    'dir_from_look', 'place_cells', 'piston_on_id', 'piston_off_id',
    'repeater_on_id', 'repeater_off_id',
    'door_other_half', 'door_opened', 'door_closed',
    'BLOCKS', 'BLOCK_NAMES', 'BLOCK_IDS', 'by_id', 'by_name', 'name_of', 'all_blocks',
    'is_solid', 'is_liquid', 'is_transparent', 'OPAQUE_IDS', 'tile_for_face',
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
CROP = 22
# ---- Phase 3：红石（同样只追加）----
#: 红石线：**信号强度不进 id**（不存在 16 个 id），强度由 `redstone.PowerGrid` 重算
REDSTONE_WIRE = 23
#: 拉杆：电源，玩家切换 ⇒ **开/关各一套 id**（状态必须能进存档）
LEVER_OFF = 24
LEVER_ON = 25
#: 按钮：电源，按下后自动回弹（回弹由 `redstone` 的计时器驱动）
BUTTON_OFF = 26
BUTTON_ON = 27
#: 红石火把：常亮电源（与火把同款，"信号源"而非"照明源"）
REDSTONE_TORCH = 28
#: 红石火把的**熄灭**态（Phase 3-B 引入）：火把是**反相器** —— 它脚下的方块被
#: 强充能时自己熄灭。id = 28 是"亮着"，这一条是"灭"。见 `redstone.strongly_powered`。
REDSTONE_TORCH_OFF = 56
#: 中继器：把信号续满 15（红石线 15 格就衰减到 0，长线路靠它）。
#: ⚠ **有向**：背面吃信号、正面吐信号（MC 同款）。
#: 初版做成"无向的放大器"（六邻都吃、六邻都吐）⇒ 它**自己给自己供电**，
#: 一旦点亮就再也灭不掉（断电也亮，实测：拉杆关掉后中继器仍是 `_on`）。
REPEATER_OFF = 29
REPEATER_ON = 30
#: 中继器的其余三个朝向（**id 必须接着 49 往下排**：这条 id 契约有单测钉着
#: "只追加不改号、且不许断号"）。
REPEATER_S_OFF = 50
REPEATER_S_ON = 51
REPEATER_E_OFF = 52
REPEATER_E_ON = 53
REPEATER_W_OFF = 54
REPEATER_W_ON = 55
#: 中继器的**延迟档位**（秒）：MC 的中继器可选 1~4 红石刻（1 红石刻 = 0.1s），
#: 这里同款四档。**档位必须落在 id 里** —— 方块只有 id、没有额外的元数据字段，
#: 而"延迟多久"是玩法本身（不同档位串起来才是时钟/脉冲整形）。
#: ⚠ 代价是 4 方向 × 4 档 × 2 态 = **32 个 id**（档 0 复用上面那 8 个历史 id）。
REPEATER_DELAYS = (0.1, 0.2, 0.3, 0.4)
#: 档 1~3 的 id：**按 `(方向, 档)` 顺序连续排**（id 是契约，显式写出来便于一眼核对）。
#: 档 0 的 id 就是上面那 8 个历史 id，**名字不许改**（存档按名字存）。
REPEATER_EXTRA = {
    ('north', 1): (57, 58), ('north', 2): (59, 60), ('north', 3): (61, 62),
    ('south', 1): (63, 64), ('south', 2): (65, 66), ('south', 3): (67, 68),
    ('east', 1): (69, 70), ('east', 2): (71, 72), ('east', 3): (73, 74),
    ('west', 1): (75, 76), ('west', 2): (77, 78), ('west', 3): (79, 80),
}
#: 红石灯：输出。`LAMP_ON` 的自发光让它同时是**光源** ⇒ 与 Phase 2-A 光照联动
LAMP_OFF = 31
LAMP_ON = 32
#: 铁门（1 格宽 2 格高）：关 / 开各占两格（下半 + 上半）
DOOR_LOWER = 33
DOOR_UPPER = 34
DOOR_OPEN_LOWER = 35
DOOR_OPEN_UPPER = 36
#: 活塞：**6 个方向 × 开/关两种状态 = 12 个 id**。
#: 为什么朝向要进 id：方块只有 id、没有额外的朝向字段，而"朝哪推"是玩法核心。
PISTON_N_OFF = 37
PISTON_N_ON = 38
PISTON_S_OFF = 39
PISTON_S_ON = 40
PISTON_E_OFF = 41
PISTON_E_ON = 42
PISTON_W_OFF = 43
PISTON_W_ON = 44
PISTON_UP_OFF = 45
PISTON_UP_ON = 46
PISTON_DOWN_OFF = 47
PISTON_DOWN_ON = 48
#: 活塞臂（伸出时占据前方那一格）；收回时**只删臂**，被推的方块留在新位置（普通活塞不拉回）
PISTON_ARM = 49

#: 本项目用到的 id 上界（校验 / 数组尺寸用）。Phase 3-B 因中继器调档从 63 提到 80
#: —— ⚠ 有单测钉着"id 必须**连续无空洞**"（`sorted(BLOCKS) == 1..N`），
#: 所以这个数**必须等于当前最大 id**，不能为了"留余量"写大。
MAX_ID = 80

#: 活塞状态表：`(方块名前缀, 关 id, 开 id)` —— 顺序 = north / south / east / west / up / down。
#: 方向名与 `mesh.NORMALS` 同一套：**north = -z、south = +z、east = +x、west = -x**。
PISTON_STATES = (
    ('piston_north', PISTON_N_OFF, PISTON_N_ON),
    ('piston_south', PISTON_S_OFF, PISTON_S_ON),
    ('piston_east', PISTON_E_OFF, PISTON_E_ON),
    ('piston_west', PISTON_W_OFF, PISTON_W_ON),
    ('piston_up', PISTON_UP_OFF, PISTON_UP_ON),
    ('piston_down', PISTON_DOWN_OFF, PISTON_DOWN_ON),
)
#: 方向中文名（HUD / 提示用）
PISTON_TITLES = {'north': '朝北', 'south': '朝南', 'east': '朝东',
                 'west': '朝西', 'up': '朝上', 'down': '朝下'}
#: 方向 → `(关 id, 开 id)`（`redstone` 与放置逻辑都按这个查）
PISTON_BY_DIR = {n[len('piston_'):]: (off, on) for (n, off, on) in PISTON_STATES}

#: 中继器的状态表：`(方向, 档位, 关 id, 开 id)` —— **4 方向 × 4 档 = 16 条**。
#: 方向 = **输出方向**（正面）。只做水平四向（与 MC 的中继器一致），上下视线退化成 north。
REPEATER_STATES = (
    ('north', 0, REPEATER_OFF, REPEATER_ON),
    ('south', 0, REPEATER_S_OFF, REPEATER_S_ON),
    ('east', 0, REPEATER_E_OFF, REPEATER_E_ON),
    ('west', 0, REPEATER_W_OFF, REPEATER_W_ON),
) + tuple(('north', n, REPEATER_EXTRA[('north', n)][0], REPEATER_EXTRA[('north', n)][1])
          for n in (1, 2, 3)) + tuple(
    (d, n, REPEATER_EXTRA[(d, n)][0], REPEATER_EXTRA[(d, n)][1])
    for d in ('south', 'east', 'west') for n in (1, 2, 3))


def _repeater_name(d: str, n: int, on: bool) -> str:
    """中继器的方块名：档 0 是 `repeater_<方向>_<态>`（**沿用历史名**，不许改 ——
    存档按名字存，改名会让老档里的中继器变成未知方块），档 1~3 中间多一段 `_d<n>`。

    ⚠ 别"顺手简化"档 0 的名字：id 29/30 的老名字就是
    `repeater_north_off` / `repeater_north_on`（**不是** `repeater_off`）。
    实测把它简写之后，"别名表里的每个名字都必须是方块名"那条断言当场变红 ——
    它守的正是**存档契约**（老档里的中继器会变成未知方块）。
    """
    suffix = '_on' if on else '_off'
    if n == 0:
        return f'repeater_{d}{suffix}'
    return f'repeater_{d}_d{n}{suffix}'


#: `(方向, 档) -> (关 id, 开 id)`
REPEATER_BY_DIR_DELAY = {(d, n): (off, on) for (d, n, off, on) in REPEATER_STATES}
#: 方向 → 档 0 的 `(关 id, 开 id)`（放置时用；调档由 `use()` 逐个切）
REPEATER_BY_DIR = {d: REPEATER_BY_DIR_DELAY[(d, 0)] for d in ('north', 'south', 'east', 'west')}
#: 状态 id → 方向 / 档位 / 开关
REPEATER_DIR_OF = {}
REPEATER_DELAY_OF = {}
REPEATER_ON_OF = {}
REPEATER_OFF_OF = {}
for _d, _n, _off, _on in REPEATER_STATES:
    for _bid, _is_on in ((_off, False), (_on, True)):
        REPEATER_DIR_OF[_bid] = _d
        REPEATER_DELAY_OF[_bid] = _n
        REPEATER_ON_OF[_bid] = _on
        REPEATER_OFF_OF[_bid] = _off
del _d, _n, _off, _on, _bid, _is_on


def repeater_delay(bid: int) -> float:
    """中继器的延迟（秒）；不是中继器 ⇒ 0.0。"""
    n = REPEATER_DELAY_OF.get(int(bid))
    return 0.0 if n is None else REPEATER_DELAYS[n]


def repeater_cycle_delay(bid: int) -> int:
    """中继器**调档**：返回下一档的"关"状态 id（不是中继器 ⇒ 原样返回）。

    只切档位、**保持开/关不变** —— 玩家右键是"调延迟"，亮/灭由信号决定。
    """
    d = REPEATER_DIR_OF.get(int(bid))
    if d is None:
        return int(bid)
    n = (REPEATER_DELAY_OF[int(bid)] + 1) % len(REPEATER_DELAYS)
    off, on = REPEATER_BY_DIR_DELAY[(d, n)]
    return on if REPEATER_ON_OF[int(bid)] == int(bid) else off
#: 方向 → 单位向量（与 `mesh.NORMALS` 的 +x/-x/+y/-y/+z/-z 同一个坐标系）
PISTON_DIR_VEC = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0),
                  'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}
#: 反向查：`(关 id, 开 id)` → 方向
PISTON_DIR_OF = {}
for _d, (_off, _on) in PISTON_BY_DIR.items():
    PISTON_DIR_OF[_off] = _d
    PISTON_DIR_OF[_on] = _d
del _d, _off, _on

#: 方块名 → **物品名**（多个状态 id 共用一个物品；`recipes.as_item` 查不到同名物品时查它）。
#: 为什么需要：拉杆有 `lever_off`/`lever_on` 两个方块，而玩家手里只有"拉杆"一件东西。
BLOCK_ITEM_ALIAS = {
    'lever_off': 'lever', 'lever_on': 'lever',
    'button_off': 'button', 'button_on': 'button',
    'repeater_north_off': 'repeater', 'repeater_north_on': 'repeater',
    'repeater_south_off': 'repeater', 'repeater_south_on': 'repeater',
    'repeater_east_off': 'repeater', 'repeater_east_on': 'repeater',
    'repeater_west_off': 'repeater', 'repeater_west_on': 'repeater',
    'lamp_off': 'lamp', 'lamp_on': 'lamp',
    'door_lower': 'door', 'door_upper': 'door',
    'door_open_lower': 'door', 'door_open_upper': 'door',
    'piston_arm': 'piston',
}
#: Phase 3-B：中继器的 32 个状态名（4 方向 × 4 档 × 开/关）全归到 `repeater`，
#: 火把的"灭"态归到 `redstone_torch`。**由表生成**：手写 32 行必然漏
#: （漏了不会报错，只会让"挖掉一个 3 档中继器"什么都不掉 —— 最难发现的那种）。
for _d in ('north', 'south', 'east', 'west'):
    for _n in range(len(REPEATER_DELAYS)):
        for _on in (False, True):
            BLOCK_ITEM_ALIAS[_repeater_name(_d, _n, _on)] = 'repeater'
BLOCK_ITEM_ALIAS['redstone_torch_off'] = 'redstone_torch'
del _d, _n, _on
for _n, _off, _on in PISTON_STATES:
    BLOCK_ITEM_ALIAS[f'{_n}_off'] = 'piston'
    BLOCK_ITEM_ALIAS[f'{_n}_on'] = 'piston'
del _n, _off, _on


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
    add(Block(CROP, 'crop', '作物', 'crop',
              solid=False, opaque=False, hardness=0.3))
    add(Block(BEDROCK, 'bedrock', '基岩', 'bedrock', hardness=999.0))
    add(Block(TORCH, 'torch', '火把', 'torch',
              solid=False, opaque=False, emissive=0.9))

    # ---- Phase 3：红石元件 ----
    # 红石线只有 1/16 格高：`solid=False`（能走过去）+ `opaque=False`（不挡邻面），
    # 而**几何**由 `mesh.THIN_BLOCKS` 压扁（画成贴地的线，不是一个整方块）。
    add(Block(REDSTONE_WIRE, 'redstone_wire', '红石线', 'redstone_wire',
              solid=False, opaque=False, hardness=0.2))
    add(Block(LEVER_OFF, 'lever_off', '拉杆', 'lever',
              solid=False, opaque=False, hardness=0.3))
    add(Block(LEVER_ON, 'lever_on', '拉杆（开）', 'lever_on',
              solid=False, opaque=False, hardness=0.3, emissive=0.12))
    add(Block(BUTTON_OFF, 'button_off', '按钮', 'button',
              solid=False, opaque=False, hardness=0.3))
    add(Block(BUTTON_ON, 'button_on', '按钮（按下）', 'button_on',
              solid=False, opaque=False, hardness=0.3, emissive=0.12))
    add(Block(REDSTONE_TORCH, 'redstone_torch', '红石火把', 'redstone_torch',
              solid=False, opaque=False, hardness=0.2, emissive=0.35))
    add(Block(REDSTONE_TORCH_OFF, 'redstone_torch_off', '红石火把（灭）',
              'redstone_torch_off', solid=False, opaque=False, hardness=0.2))
    # 中继器：四个朝向共用两张贴图（朝向与档位的正确性在**功能**里，不靠贴图区分 ——
    # 这一点写进了设计稿的"已知取舍"）
    for (d, n, off_id, on_id) in REPEATER_STATES:
        tag = f'{PISTON_TITLES[d][1:]}·{n + 1}档'
        add(Block(off_id, _repeater_name(d, n, False), f'中继器·{tag}',
                  'repeater', solid=False, opaque=False, hardness=0.3))
        add(Block(on_id, _repeater_name(d, n, True), f'中继器·{tag}（亮）',
                  'repeater_on', solid=False, opaque=False, hardness=0.3,
                  emissive=0.12))
    # 红石灯：**亮的时候是真光源**（emissive=1.0）⇒ 走 Phase 2-A 的光照重算
    add(Block(LAMP_OFF, 'lamp_off', '红石灯', 'lamp_off', hardness=0.6))
    add(Block(LAMP_ON, 'lamp_on', '红石灯（亮）', 'lamp_on',
              hardness=0.6, emissive=1.0))
    # 铁门：关着 `solid=True`（挡人），开了 `solid=False`（能穿过去、看得见门框）
    add(Block(DOOR_LOWER, 'door_lower', '铁门', 'door_lower', hardness=1.2))
    add(Block(DOOR_UPPER, 'door_upper', '铁门（上）', 'door_upper', hardness=1.2))
    add(Block(DOOR_OPEN_LOWER, 'door_open_lower', '铁门（开）', 'door_open_lower',
              solid=False, opaque=False, hardness=1.2))
    add(Block(DOOR_OPEN_UPPER, 'door_open_upper', '铁门（开·上）', 'door_open_upper',
              solid=False, opaque=False, hardness=1.2))
    # 活塞：本体（6 方向 × 开/关）+ 臂
    for (name, off_id, on_id) in PISTON_STATES:
        d = name[len('piston_'):]
        add(Block(off_id, f'{name}_off', f'活塞·{PISTON_TITLES[d]}',
                  'piston_side', hardness=1.0))
        add(Block(on_id, f'{name}_on', f'活塞·{PISTON_TITLES[d]}（推出）',
                  'piston_top', hardness=1.0))
    add(Block(PISTON_ARM, 'piston_arm', '活塞臂', 'piston_arm', hardness=1.0))
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


#: **不透明方块的 id 集合**（由定义表派生，与 `is_transparent` 同一口径）。
#: 网格热路径（面剔除 + 顶点级 AO）用它做集合成员测试：比 `is_transparent()`
#: 少一层字典查找 + 属性访问。这条路径一整世界要跑几百万次，值得单列一个集合。
#: ⚠ 有单测钉着它和 `is_transparent` **逐 id 一致**（两个口径不能漂）。
OPAQUE_IDS = frozenset(b.id for b in BLOCKS.values() if b.opaque)


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


#: 默认 hotbar（名字形态，配置树与 demo 共用）。
#: Phase 3 起把红石元件放进来（demo 的 9 格 hotbar 因此 = 建造 + 红石各占一半）——
#: 活塞/门/中继器**各占一个格子**：它们在放置时按视线或占格自动展开成具体状态 id。
DEFAULT_HOTBAR = (
    'grass', 'planks', 'redstone_wire', 'lever', 'redstone_torch',
    'repeater', 'lamp', 'door', 'piston',
)


# ---------------------------------------------------------------- 放置变体
def dir_from_look(look) -> str:
    """视线向量 → 6 方向名（取**主导分量**，与 MC 的"朝你看的方向"一致）。"""
    dx, dy, dz = (float(v) for v in look[:3])
    ax, ay, az = abs(dx), abs(dy), abs(dz)
    if ay >= ax and ay >= az:
        return 'up' if dy >= 0 else 'down'
    if ax >= az:
        return 'east' if dx >= 0 else 'west'
    return 'south' if dz >= 0 else 'north'


def piston_on_id(bid: int) -> int:
    """这个活塞的"推出"状态 id（不是活塞 ⇒ 原样返回）。"""
    d = PISTON_DIR_OF.get(int(bid))
    return PISTON_BY_DIR[d][1] if d else int(bid)


def piston_off_id(bid: int) -> int:
    """这个活塞的"收回"状态 id（不是活塞 ⇒ 原样返回）。"""
    d = PISTON_DIR_OF.get(int(bid))
    return PISTON_BY_DIR[d][0] if d else int(bid)


def repeater_on_id(bid: int) -> int:
    """这个中继器的"亮"状态 id（**保持同一档位**；不是中继器 ⇒ 原样返回）。

    ⚠ 初版返回的是 `REPEATER_BY_DIR[dir][1]` —— 那是**档 0** 的 id。
    没有档位时看不出问题，加了调档之后就成了真 bug：
    **中继器每翻转一次就掉回 1 档**（实测：3 档时钟第一次延迟 0.3s、
    之后就变成 0.1s，周期从 0.6s 缩到 0.2s）。
    """
    return REPEATER_ON_OF.get(int(bid), int(bid))


def repeater_off_id(bid: int) -> int:
    """这个中继器的"灭"状态 id（**保持同一档位**；不是中继器 ⇒ 原样返回）。"""
    return REPEATER_OFF_OF.get(int(bid), int(bid))


def place_cells(block_id: int, x: int, y: int, z: int, look=(0.0, 0.0, -1.0)):
    """放下这个方块时**实际要写的格子** `[(x, y, z, id), ...]`。

    把"多格方块"与"朝向"这两件麻烦事**收口在一处**（调用方只管逐格检查空位）：
    * 普通方块 ⇒ 一格；
    * 铁门 ⇒ 竖着两格（下半 + 上半）；
    * 活塞 ⇒ 按 `look`（视线）选方向的 `*_off` 状态（⚠ 存的是**关**的状态：
      通电才推出，否则放下就伸出来了）。
    """
    b = int(block_id)
    if b in (DOOR_LOWER, DOOR_UPPER, DOOR_OPEN_LOWER, DOOR_OPEN_UPPER):
        return [(x, y, z, DOOR_LOWER), (x, y + 1, z, DOOR_UPPER)]
    if b in PISTON_DIR_OF:
        off, _on = PISTON_BY_DIR[dir_from_look(look)]
        return [(x, y, z, off)]
    if b in REPEATER_DIR_OF:
        d = dir_from_look(look)
        if d in ('up', 'down'):          # 中继器只做水平四向（与 MC 一致）
            d = 'north'
        off, _on = REPEATER_BY_DIR[d]
        return [(x, y, z, off)]
    return [(x, y, z, b)]


def door_other_half(bid: int):
    """门的那一半（下 ↔ 上）；不是门 ⇒ None。挖门/开关门都要成对处理。"""
    return {DOOR_LOWER: DOOR_UPPER, DOOR_UPPER: DOOR_LOWER,
            DOOR_OPEN_LOWER: DOOR_OPEN_UPPER,
            DOOR_OPEN_UPPER: DOOR_OPEN_LOWER}.get(int(bid))


def door_opened(bid: int) -> int:
    """这扇门的"开"状态 id；不是门 ⇒ 原样返回。"""
    return {DOOR_LOWER: DOOR_OPEN_LOWER, DOOR_UPPER: DOOR_OPEN_UPPER}.get(int(bid), int(bid))


def door_closed(bid: int) -> int:
    """这扇门的"关"状态 id；不是门 ⇒ 原样返回。"""
    return {DOOR_OPEN_LOWER: DOOR_LOWER, DOOR_OPEN_UPPER: DOOR_UPPER}.get(int(bid), int(bid))
