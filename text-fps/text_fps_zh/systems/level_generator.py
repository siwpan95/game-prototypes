"""Procedural campaign generator (F4).

Produces a fully-connected, seed-reproducible tactical level: an entrance, a
blob of combat rooms, one treasure vault, and a boss room. Content density
(enemies / items / cover) scales with each room's depth from the entrance,
mirroring the hand-authored levels but generated on the fly so every run is a
fresh layout that a given seed always reconstructs identically.

Algorithm
---------
A bounded random growth over a small lattice (each new cell is adjoined to an
already-selected cell) guarantees the resulting exit graph is *always connected*
and fully reachable from the entrance. The same ``seed`` fed to
``random.Random`` makes the whole layout deterministic.
"""
from typing import Dict, List, Optional, Tuple

import random

from models.level import Level
from models.room import Room
from data.enemies import create_enemy
from data.items import (
    create_medkit,
    create_grenade,
    create_ammo,
    create_armor,
    create_weapon_mod_item,
    create_flashbang,
    create_stim,
    create_heavy_armor,
)


# Direction name -> lattice delta. Symmetric exits keep movement consistent
# with the authored levels (north/south/east/west are just labels here).
DIRS: Dict[str, Tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}

# Cover / destructible vocabulary reused across the campaign for flavour.
_COVER = [
    "水泥柱", "沙袋", "金属货架", "翻倒的柜子", "堆叠的板条箱",
    "钢制办公桌", "文件柜", "管道接头", "弹药箱", "服务器机架",
]
_DESTRUCTIBLES = ["燃料桶", "木箱", "玻璃隔断", "不稳定的货架", "发电机"]

# Enemy archetype pools by role / depth.
_GRUNTS = ["守卫", "士兵"]
_ELITES = ["重装兵", "狙击手"]
_SPECIALS = ["突击兵", "机枪手", "医疗兵", "神射手"]

# Flavour pools.
_FACILITY_NAMES = [
    "废弃化工厂", "地下掩体", "海上钻井平台", "废弃监狱",
    "通讯枢纽", "走私仓库", "科研前哨", "边境检查站",
]
_COMBAT_NAMES = [
    "狭长走廊", "仓库区", "指挥通道", "维修间", "宿舍区",
    "配电室", "车库", "训练场", "消杀通道", "监控室",
]

# Tactical-shooter grounded mod/ammo drops. NOTE: create_weapon_mod_item()
# expects a *mod_type* key, not the Chinese display name — passing the name
# would silently fall back to a silencer mod. So these are the type keys.
_MOD_DROPS = ["silencer", "scope", "extended_mag", "ap_rounds", "hollow_point", "match_grade"]
_TREASURE_MODS = ["scope", "extended_mag", "ap_rounds", "match_grade"]
_BOSS_MODS = ["scope", "extended_mag", "ap_rounds"]
_AMMO_DROPS = ["pistol", "rifle", "shotgun"]


# ----------------------------------------------------------------------
# Room population helpers
# ----------------------------------------------------------------------
def _populate_entrance(rng: random.Random, room: Room) -> None:
    """Entrance room: a lone sentry, light cover, a medkit."""
    room.enemies = [create_enemy("守卫")]
    room.cover_objects = rng.sample(_COVER, 2)
    room.destructibles = []
    room.items = [create_medkit(25)]
    room.traps = []


def _populate_combat(rng: random.Random, room: Room, depth_frac: float) -> None:
    """Combat room: enemy count and elite ratio scale with depth."""
    count = 1 + (1 if rng.random() < depth_frac else 0) + rng.randint(0, 1)
    count = min(count, 4)

    enemies: List = []
    for _ in range(count):
        r = rng.random()
        if depth_frac > 0.5:
            # Deeper rooms lean on elites + special archetypes.
            if r < 0.4:
                enemies.append(create_enemy(rng.choice(_ELITES)))
            elif r < 0.75:
                enemies.append(create_enemy(rng.choice(_SPECIALS)))
            else:
                enemies.append(create_enemy(rng.choice(_GRUNTS)))
        else:
            if r < 0.55:
                enemies.append(create_enemy(rng.choice(_GRUNTS)))
            elif r < 0.85:
                enemies.append(create_enemy(rng.choice(_ELITES)))
            else:
                enemies.append(create_enemy(rng.choice(["突击兵", "机枪手"])))
    room.enemies = enemies

    room.cover_objects = rng.sample(_COVER, rng.randint(2, 3))
    room.destructibles = rng.sample(_DESTRUCTIBLES, rng.randint(1, 2))

    items: List = []
    if rng.random() < 0.7:
        items.append(create_ammo(rng.choice(_AMMO_DROPS), rng.choice([15, 30, 8])))
    if rng.random() < 0.5:
        items.append(create_armor(25))
    if rng.random() < 0.4:
        items.append(create_medkit(25))
    if rng.random() < 0.3:
        items.append(create_grenade(30))
    if rng.random() < 0.3:
        items.append(create_weapon_mod_item(rng.choice(_MOD_DROPS)))
    room.items = items
    room.traps = []


def _populate_treasure(rng: random.Random, room: Room) -> None:
    """Treasure vault: a safe haven with the best loot."""
    room.enemies = []
    room.cover_objects = rng.sample(_COVER, 2)
    room.destructibles = []
    room.items = [
        create_heavy_armor(50),
        create_ammo("rifle", 30),
        create_medkit(50),
        create_weapon_mod_item(rng.choice(_TREASURE_MODS)),
        create_stim(25, 3),
        create_flashbang(2),
    ]
    room.traps = []


def _populate_boss(rng: random.Random, room: Room) -> None:
    """Boss room: the commander + escort, heavy cover, a mod drop."""
    loot = [create_weapon_mod_item(rng.choice(_BOSS_MODS))]
    room.enemies = [
        create_enemy("指挥官", loot=loot),
        create_enemy(rng.choice(["士兵", "重装兵"])),
        create_enemy(rng.choice(["士兵", "重装兵"])),
    ]
    room.cover_objects = rng.sample(_COVER, 3)
    room.destructibles = rng.sample(_DESTRUCTIBLES, 2)
    room.items = [create_medkit(50), create_ammo("rifle", 30)]
    room.traps = []


# ----------------------------------------------------------------------
# Flavour descriptions (deterministic so the level is fully reproducible)
# ----------------------------------------------------------------------
def _desc_entrance(rng: random.Random, facility: str) -> str:
    return (
        f"你潜入{facility}的外围。锈蚀的栅栏门虚掩着，冷风灌进领口。"
        "监控探头早已停止转动，地上一串新鲜的军靴脚印通向内部。"
    )


def _desc_combat(rng: random.Random) -> str:
    frags = [
        "灯光忽明忽暗，墙上的血迹还未干透。",
        "通风管传来低沉的嗡鸣，掩盖了你的脚步声。",
        "散落的弹壳在脚下咯吱作响，空气中弥漫着火药味。",
        "一道应急红光扫过地面，远处有交火的回响。",
        "这里曾发生过激烈交火，墙面上布满弹孔。",
    ]
    return "你进入一处战术区域。" + rng.choice(frags)


def _desc_treasure(rng: random.Random) -> str:
    return (
        "一扇加固的舱门后是一间储藏室。弹药箱、护甲与改装件整齐码放，"
        "显然长时间无人打扰——这里是整座设施最安全的地方。"
    )


def _desc_boss(rng: random.Random, facility: str) -> str:
    return (
        f"{facility}的核心指挥区。巨大的全息沙盘中央，一名指挥官负手而立，"
        "身旁精锐护卫杀气腾腾。这是行动的终点，也是最难啃的硬骨头。"
    )


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def generate_campaign(seed: int) -> Level:
    """Generate a reproducible campaign level for ``seed``.

    Returns a :class:`Level` whose ``start_room`` is the entrance and whose
    ``boss_room`` houses the commander. The layout (rooms, exits, enemy/item
    placement) is fully determined by ``seed``.
    """
    rng = random.Random(seed)

    # --- 1. Grow a connected blob of cells on a 5x5 lattice. ---
    grid_w, grid_h = 5, 5
    target_rooms = rng.randint(5, 8)
    start_cell = (grid_w // 2, grid_h // 2)

    selected: List[Tuple[int, int]] = [start_cell]
    selected_set = {start_cell}

    while len(selected) < target_rooms:
        candidates: List[Tuple[int, int]] = []
        for (sx, sy) in selected:
            for dx, dy in DIRS.values():
                nb = (sx + dx, sy + dy)
                if 0 <= nb[0] < grid_w and 0 <= nb[1] < grid_h and nb not in selected_set:
                    candidates.append(nb)
        if not candidates:
            break  # Lattice saturated (won't happen for target <= 8 on 5x5).
        nxt = rng.choice(candidates)
        selected.append(nxt)
        selected_set.add(nxt)

    # --- 2. Assign deterministic ids and room roles. ---
    ids: Dict[Tuple[int, int], str] = {
        coord: f"room_{i}" for i, coord in enumerate(selected)
    }
    entrance_id = ids[selected[0]]
    boss_id = ids[selected[-1]]
    treasure_id: Optional[str] = None
    if len(selected) >= 4:
        interior = selected[1:-1]
        treasure_id = ids[rng.choice(interior)]

    facility = rng.choice(_FACILITY_NAMES)

    # --- 3. Build rooms with symmetric exits. ---
    rooms: Dict[str, Room] = {}
    for i, coord in enumerate(selected):
        rid = ids[coord]
        exits: Dict[str, str] = {}
        cx, cy = coord
        for dname, (dx, dy) in DIRS.items():
            nb = (cx + dx, cy + dy)
            if nb in selected_set:
                exits[dname] = ids[nb]

        if rid == entrance_id:
            room = Room(
                room_id=rid, name="设施入口",
                description=_desc_entrance(rng, facility), exits=exits,
            )
            _populate_entrance(rng, room)
        elif rid == boss_id:
            room = Room(
                room_id=rid, name="核心指挥区",
                description=_desc_boss(rng, facility), exits=exits,
            )
            _populate_boss(rng, room)
        elif treasure_id is not None and rid == treasure_id:
            room = Room(
                room_id=rid, name="军械储藏室",
                description=_desc_treasure(rng), exits=exits,
            )
            _populate_treasure(rng, room)
        else:
            depth_frac = i / max(1, len(selected) - 1)
            room = Room(
                room_id=rid, name=rng.choice(_COMBAT_NAMES),
                description=_desc_combat(rng), exits=exits,
            )
            _populate_combat(rng, room, depth_frac)

        rooms[rid] = room

    return Level(
        level_id=99,  # Procedural campaign marker (not part of the 1-3 story arc).
        name=facility,
        rooms=rooms,
        start_room=entrance_id,
        boss_room=boss_id,
    )
