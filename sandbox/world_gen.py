"""world_gen.py — 用 procgen 生成地牢，桥接到 alloy 的 MapData 与 ECS 实体。

procgen 负责「世界生成」：
  - generate_dungeon / generate_cave  → 0/1 网格几何
  - NameGenerator(fantasy)            → 怪物名 / 区域名
  - LootTable                         → 宝箱掉落风味文本

alloy 负责「世界承载」：
  - world.map_data.MapData           → 地形字符网格
  - core.ecs.World / Entity          → 怪物实体 + Position/Health/MobBrain 组件
"""
from __future__ import annotations

import random
from collections import Counter

import procgen as pg
from alloy.core.ecs import World
from alloy.world.map_data import MapData

from entities import (
    Position, Health, MobBrain,
    build_catalog, build_mob_library,
    WEAPON_TIERS, ARMOR_TIERS, POTIONS, scale_template,
)
from monster_ai import make_brain, make_boss_brain
import affixes as affix_mod   # 装备稀有度 + 随机词缀系统

WALL = "#"
FLOOR = "."
STAIRS = ">"

# 生物群系 → 区域描述 / 怪物偏好（打通 procgen terrain + noise 模块）
_BIOME_DESC = {
    "水": "幽蓝的水窟，水汽弥漫",
    "滩": "潮湿的滩涂，贝壳散落",
    "草": "葱郁的草原地穴",
    "林": "幽暗密林，藤蔓缠绕",
    "漠": "黄沙漫漫的荒漠遗迹",
    "苔": "寒雾弥漫的苔原",
    "山": "险峻山岳，岩缝藏敌",
    "雪": "冰封雪峰，寒气刺骨",
}
# 每个生物群系额外偏好的怪物（在原 4 种基础上加权）
_MOB_BIAS = {
    "水": ["slime", "wraith"],
    "滩": ["slime", "bat"],
    "草": ["goblin", "bat"],
    "林": ["slime", "wraith", "spider"],       # 毒蛛潜伏密林
    "漠": ["skeleton", "golem"],
    "苔": ["orc", "wraith"],
    "山": ["orc", "golem", "gargoyle"],         # 石魔像镇守山岳
    "雪": ["orc", "skeleton", "wraith", "gargoyle"],
}


# ── 连通分量（BFS），保证起点/楼梯/怪物/物品同属一个可达区域 ──────────
def _components(grid, W, H):
    seen = [[False] * W for _ in range(H)]
    comps = []
    for r in range(H):
        for c in range(W):
            if grid[r][c] == 1 and not seen[r][c]:
                stack = [(c, r)]
                seen[r][c] = True
                cells = []
                while stack:
                    x, y = stack.pop()
                    cells.append((x, y))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < H and not seen[ny][nx] and grid[ny][nx] == 1:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
                comps.append(cells)
    comps.sort(key=len, reverse=True)
    return comps


# 生物群系 → 熔岩陷阱出现概率（其余为尖刺陷阱）。火山/荒漠类地穴更易出现熔岩，
# 呼应「主题楼层」：不同 biome 的灾害质感不同（沉浸感增强）。
_LAVA_BIOMES = {"山": 0.6, "漠": 0.4, "苔": 0.3, "雪": 0.2}


def _place_traps(main, occupied, rng, count: int, biome: str = "") -> dict:
    """在已连通主区域内随机布设陷阱（避开起点/楼梯/已占用格）。

    陷阱是经典 roguelike 危险元素：踩中扣血并解除。返回 坐标→类型 字典
    （"lava" 熔岩 / "spike" 尖刺），类型随生物群系偏置（详见 _LAVA_BIOMES）。
    """
    trap_types: dict = {}
    free = [c for c in main if c not in occupied]
    lava_p = _LAVA_BIOMES.get(biome, 0.0)
    for _ in range(min(count, len(free))):
        pos = rng.choice(free)
        free.remove(pos)
        occupied.add(pos)
        trap_types[pos] = "lava" if (lava_p > 0 and rng.random() < lava_p) else "spike"
    return trap_types


def _pip(verts, px: float, py: float) -> bool:
    """射线法：点 (px,py) 是否在多边形 verts([(x,y),...]) 内。"""
    n = len(verts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if ((yi > py) != (yj > py)) and \
           (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _generate_town_floor(world, seed, fi, total_floors, W, H, rng):
    """用 procgen.generate_town 生成可探索的安全屋（无怪物）。

    把城镇几何栅格化进 MapData 网格：城墙外为墙、城内为可走；
    城堡(centre)作旅馆、广场(plaza)作商店，城门之一作下层出口。
    """
    town = pg.generate_town(seed=fi, n_wards=12, walled=True)
    wall = town["wall"]
    minx, miny, maxx, maxy = town["bounds"]
    sx = (maxx - minx) or 1.0
    sy = (maxy - miny) or 1.0

    def to_grid(px, py):
        c = int((px - minx) / sx * (W - 1))
        r = int((py - miny) / sy * (H - 1))
        return max(0, min(W - 1, c)), max(0, min(H - 1, r))

    wall_verts = [(v.x, v.y) for v in wall["shape"].verts] if wall else None
    rows = []
    for r in range(H):
        row = []
        for c in range(W):
            px = minx + c / (W - 1) * sx
            py = miny + r / (H - 1) * sy
            if wall_verts and not _pip(wall_verts, px, py):
                row.append(WALL)
            else:
                row.append(FLOOR)
        rows.append(row)
    terrain = MapData(grid=rows)

    # 连通分量：取城内最大可走区，保证 start/stairs 彼此连通（避免城门孤岛）
    grid01 = [[1 if rows[r][c] != WALL else 0 for c in range(W)] for r in range(H)]
    comps = _components(grid01, W, H)
    main = comps[0] if comps else [(1, 1), (W - 2, H - 2)]
    start = main[0]
    stairs = max(main, key=lambda p: abs(p[0] - start[0]) + abs(p[1] - start[1]))
    terrain.set(start[0], start[1], FLOOR)
    terrain.set(stairs[0], stairs[1], STAIRS)

    def _snap(pos):
        return pos if pos in main else min(
            main, key=lambda p: (p[0] - pos[0]) ** 2 + (p[1] - pos[1]) ** 2)

    # 设施：城堡=旅馆(H)、广场=商店(¥)，吸附进连通区
    structures = {}
    if town["citadel"] is not None:
        structures["inn"] = _snap(to_grid(town["citadel"].shape.center.x,
                                          town["citadel"].shape.center.y))
    if town["plaza"] is not None:
        structures["shop"] = _snap(to_grid(town["plaza"].shape.center.x,
                                           town["plaza"].shape.center.y))
    if "inn" not in structures:
        structures["inn"] = main[len(main) // 4]
    if "shop" not in structures:
        structures["shop"] = main[3 * len(main) // 4]

    namegen = pg.NameGenerator(style="fantasy", seed=seed + fi, method="syllable")
    town_name = namegen.generate(1)[0]

    return {
        "terrain": terrain,
        "start": start,
        "stairs": stairs,
        "monsters": [],
        "items": [],
        "traps": set(),
        "structures": structures,
        "region": town_name,
        "biome": "镇",
        "biome_desc": "宁静的集镇，可在此休整补给",
        "is_boss": False,
        "is_town": True,
        "floor_index": fi,
        "trap_types": {},
        "loot_flavor": [],
    }


def generate_floor(world: World, seed: int, floor_index: int, total_floors: int,
                   director=None):
    """生成一层地牢，返回该层的全部数据。

    参数：
        world:        ECS 世界（怪物实体会挂在这里）
        seed:         全局种子
        floor_index:  当前层数（1-based）
        total_floors: 总层数
        director:     AI Director（可选）。提供时按玩家表现动态调节刷怪数 /
                      陷阱数 / 掉落质量，并让越深越易出高稀有度装备。
    """
    rng = random.Random(seed * 1000 + floor_index)
    W, H = 44, 32
    is_boss = floor_index == total_floors

    # 镇子安全屋层（打通 procgen generate_town）：每 3 层一个，且非 Boss 层
    is_town = (floor_index > 1) and (floor_index % 3 == 0) and (not is_boss)
    if is_town:
        return _generate_town_floor(world, seed, floor_index, total_floors, W, H, rng)

    # 几何：按层在「房间地牢 / 元胞洞穴 / BSP 二叉分割」三种生成器间轮换，
    # 保证每一层观感与拓扑都不同（程序化生成多样性，roguelike 核心乐趣）。
    # Boss 层固定为房间地牢（结构清晰、便于决战）。
    # 程序化生成参数扰动（Roguetemple「tweak the variables」）：每层在基准上
    # 随机抖动房间数 / 洞穴填充率，提升可重玩性与观感差异。
    room_jitter = rng.randint(-3, 3)
    cave_fill = max(0.38, min(0.52, 0.45 + rng.uniform(-0.07, 0.07)))
    if is_boss:
        d = pg.generate_dungeon(W, H, rooms=6, seed=seed + floor_index)
        gen_kind = "room"
    else:
        kind = floor_index % 3
        if kind == 0:
            d = pg.generate_dungeon(W, H, rooms=max(4, 8 + floor_index + room_jitter),
                                    seed=seed + floor_index)
            gen_kind = "room"
        elif kind == 1:
            d = pg.generate_cave(W, H, seed=seed + floor_index,
                                 fill_prob=cave_fill, iterations=5)
            gen_kind = "cave"
        else:
            # BSP：procgen 已内置但此前未启用的二叉空间分割地牢
            d = pg.generate_dungeon_bsp(W, H, seed=seed + floor_index)
            gen_kind = "bsp"

    grid = d["grid"]
    # 退化保护：万一几乎全墙，强制开一块中央区域
    comps = _components(grid, W, H)
    if not comps or len(comps[0]) < 12:
        for r in range(2, H - 2):
            for c in range(2, W - 2):
                grid[r][c] = 1
        comps = _components(grid, W, H)

    main = comps[0]

    # 地形 MapData（0=墙 1=地）
    rows = [
        [WALL if grid[r][c] == 0 else FLOOR for c in range(W)]
        for r in range(H)
    ]
    terrain = MapData(grid=rows)

    # 起点 & 楼梯（都在最大连通分量内，保证可达）
    start = main[0]
    stairs = max(main, key=lambda p: abs(p[0] - start[0]) + abs(p[1] - start[1]))
    terrain.set(stairs[0], stairs[1], STAIRS)

    # ── 生物群系（procgen terrain/noise）：打通 generate_world + classify_biomes ──
    _biomes = pg.generate_world(W, H, seed=seed + floor_index * 7)["biomes"]
    _biome_code = Counter(_biomes.flatten().tolist()).most_common(1)[0][0]
    biome = pg.BIOME_NAMES[_biome_code]
    biome_desc = _BIOME_DESC.get(biome, "幽深的地牢")

    # 程序化命名
    namegen = pg.NameGenerator(style="fantasy", seed=seed + floor_index, method="syllable")
    region = namegen.generate(1)[0]
    loot_flavor = pg.LootTable(
        [("金币", 50, (1, 10)), ("药水", 10, (1, 3)), ("宝石", 5, (1, 2)),
         ("符文", 3, (1, 1)), ("传说剑", 1, (1, 1))],
        seed=seed + floor_index,
    ).roll(5)

    catalog = build_catalog()
    mob_lib = build_mob_library()
    occupied = {start, stairs}

    # ── 陷阱（经典 roguelike 危险元素，越深越多）──
    # AI Director 调节：玩家吃瘪时减少陷阱（更易喘息）
    trap_mult = director.trap_mult() if director else 1.0
    n_traps = int((2 + floor_index if not is_boss else 3 + floor_index) * trap_mult)
    trap_types = _place_traps(main, occupied, rng, n_traps, biome)
    traps = set(trap_types.keys())   # floor["traps"] 仍为集合（踩中即从集合移除）

    # ── 怪物（按层缩放难度；AI Director 动态调节数量）──
    monsters = []
    # 难度系数：越深怪物越强（每层 +12% HP/伤害），形成可感知的难度爬升
    diff = 1.0 + (floor_index - 1) * 0.12
    if is_boss:
        pool, n = ["dragon"], 1
    else:
        # 按层深「分层」混入新威胁（roguelike 难度爬升共识：威胁随深度递进）：
        #   1-2 层：纯近战，保留温和开局；
        #   3+ 层：远程怪（archer/mage）登场 → 远程攻击 + 群聚 AI；
        #   4+ 层：毒蛛（spider）加入 → 中毒威胁；
        #   5+ 层：石魔像（gargoyle）加入 → 高血量肉盾 + 再生。
        base_pool = ["goblin", "skeleton", "slime", "orc"]
        if floor_index >= 3:
            base_pool += ["archer", "mage"]      # 远程威胁
        if floor_index >= 4:
            base_pool += ["spider"]              # 中毒威胁
        if floor_index >= 5:
            base_pool += ["gargoyle"]           # 高血量肉盾
        base_pool.extend(_MOB_BIAS.get(biome, []))   # 生物群系偏好怪
        # AI Director：吃瘪时少刷怪、碾压时多刷怪（橡皮筋式动态难度）
        mult = director.monster_count_mult() if director else 1.0
        pool, n = base_pool, max(1, int((3 + floor_index) * mult))
    free = [c for c in main if c not in occupied]
    for _ in range(n):
        if not free:
            break
        pos = rng.choice(free)
        free.remove(pos)
        occupied.add(pos)
        tid = rng.choice(pool)
        base = mob_lib.get(tid)
        tmpl = scale_template(base, diff)            # 按层缩放后的实际模板
        tmpl.metadata = dict(base.metadata)          # 保留 ability/range/ranged/onhit
        e = world.create_entity(f"mob_{floor_index}_{len(monsters)}")
        e.add(Position(pos[0], pos[1]))
        e.add(Health(tmpl.hp, tmpl.hp))
        # 从模板元数据读取远程/特殊行为参数（打通「远程攻击 + 群聚」AI）
        brain = MobBrain(
            tmpl, namegen.generate(1)[0], make_brain(),
            ability=tmpl.metadata.get("ability"),
            attack_range=tmpl.metadata.get("range", 1),
            ranged_kind=tmpl.metadata.get("ranged"),
            onhit=tmpl.metadata.get("onhit"),
        )
        if tid == "dragon":   # Boss 用行为树决策（打通 AI 决策范式）
            bt, bb = make_boss_brain()
            brain.bt = bt
            brain.blackboard = bb
        e.add(brain)
        monsters.append(e)

    # ── 物品（按层分档：武器/护甲/药水；武器/护甲掷稀有度+词缀）──
    items = []
    tier = min(floor_index - 1, len(WEAPON_TIERS) - 1)
    # AI Director：吃瘪时略增掉落量，让玩家更快回血/补强
    loot_mult = director.loot_quality_mult() if director else 1.0
    n_items = int((2 + floor_index) * loot_mult) if not is_boss else 3 + floor_index
    luck = director.rarity_luck() if director else 0   # 吃瘪时掉落整体抬一档
    for _ in range(n_items):
        if not free:
            break
        pos = rng.choice(free)
        free.remove(pos)
        occupied.add(pos)
        roll = rng.random()
        if roll < 0.4:
            iid = rng.choice(WEAPON_TIERS[tier])
        elif roll < 0.7:
            iid = rng.choice(ARMOR_TIERS[tier])
        else:
            iid = rng.choice(POTIONS)
        item = catalog[iid]
        # 武器/护甲按层深 + 幸运掷出稀有度与随机词缀（roguelike 构筑感）
        meta = {"rarity": "common", "affixes": []}
        if item.item_type in ("weapon", "armor"):
            meta = affix_mod.make_loot(rng, iid, item.item_type,
                                       floor_index, luck)
        items.append({"pos": pos, "iid": iid, "item": item,
                      "rarity": meta["rarity"], "metadata": meta})

    return {
        "terrain": terrain,
        "start": start,
        "stairs": stairs,
        "monsters": monsters,
        "items": items,
        "traps": traps,               # 集合：踩中即从集合中移除
        "trap_types": trap_types,     # 字典：坐标→"lava"/"spike"
        "gen_kind": gen_kind,
        "region": region,
        "biome": biome,
        "biome_desc": biome_desc,
        "is_boss": is_boss,
        "floor_index": floor_index,
        "loot_flavor": loot_flavor,
    }
