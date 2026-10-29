"""
ECS Entities — 实体工厂函数
用组件组合组装玩家和怪物实体。
支持程序化怪物名称生成 + 词缀附加。
名称池从 data/game_data.xlsx 加载（monsters Sheet）。
"""

import random

from .components import (
    AttackComponent,
    BackpackComponent,
    BuffComponent,
    EquipmentComponent,
    ExpComponent,
    HPComponent,
    MonsterComponent,
    MonsterTag,
    NameComponent,
    PlayerTag,
    RespawnComponent,
    StatusEffectComponent,
)
from .game_data import get_data
from .monster_affixes import get_affix_display, random_affix
from .world import World

# ── 名称池（前缀/后缀独立，随机组合） ────────────────

def _load_name_pools():
    """加载前缀和后缀列表。优先用 prefixes/suffixes 新格式，回退到 monsters 旧格式。"""
    try:
        data = get_data()
        prefixes = data.get("prefixes", [])
        suffixes = data.get("suffixes", [])
        if prefixes and suffixes:
            return prefixes, suffixes
        # 回退：从旧 monsters sheet 拆出前缀后缀
        monsters = data.get("monsters", [])
        if monsters:
            prefs = list(set(row[0] for row in monsters))
            suffs = list(set(row[1] for row in monsters))
            return prefs, suffs
    except Exception as _e:
        import sys
        print(f"[Entities] 加载名称池失败：{_e}", file=sys.stderr)
    # 终极兜底
    _BUILTIN_PREFIXES = ["暗影", "亡灵", "火焰", "冰霜", "剧毒", "岩石", "风暴", "幻影", "熔岩", "雷霆"]
    _BUILTIN_SUFFIXES = ["刺客", "骑士", "恶魔", "巫师", "蜘蛛", "巨人", "领主", "猎豹", "暴君", "战士", "法师"]
    return _BUILTIN_PREFIXES, _BUILTIN_SUFFIXES

_PREFIX_POOL, _SUFFIX_POOL = _load_name_pools()
_COMBO_TOTAL = len(_PREFIX_POOL) * len(_SUFFIX_POOL)


def _random_monster_name() -> str:
    """随机前缀 + 随机后缀 = 无限组合"""
    if not _PREFIX_POOL or not _SUFFIX_POOL:
        return "未知怪物"
    return random.choice(_PREFIX_POOL) + random.choice(_SUFFIX_POOL)


# ── 玩家创建 ──────────────────────────────────────────────

def create_player(world: World) -> int:
    """创建玩家实体，返回 entity ID"""
    eid = world.create_entity()
    world.add_component(eid, PlayerTag())
    world.add_component(eid, NameComponent("玩家"))
    world.add_component(eid, HPComponent(hp=100, max_hp=100))
    world.add_component(eid, AttackComponent(atk_base=13, crit_chance=0.12,
                                             dodge_chance=0.08))
    world.add_component(eid, ExpComponent(level=1, exp=0, exp_pool=0))
    world.add_component(eid, EquipmentComponent(max_slots=4))
    world.add_component(eid, BackpackComponent(max_slots=12))
    world.add_component(eid, StatusEffectComponent())
    world.add_component(eid, BuffComponent())
    return eid


# ── 怪物创建 ──────────────────────────────────────────────

def create_monster(world: World, name: str | None = None,
                    level: int = 1, affix_id: str | None = None) -> int:
    """
    创建怪物实体，返回 entity ID。
    - name: None 则从名称池随机生成
    - level: 用于计算怪物属性（HP/EXP/复活时间）
    - affix_id: None 则随机决定是否附加词缀
    """
    if name is None:
        name = _random_monster_name()
    if affix_id is None:
        affix_id = random_affix()

    # 根据等级计算属性
    hp = 40 + level * 35
    exp_reward = 8 + level * 6
    respawn_time = 3 + level

    eid = world.create_entity()
    world.add_component(eid, MonsterTag())
    display_name = name + get_affix_display(affix_id)
    world.add_component(eid, NameComponent(display_name))

    from .monster_affixes import AFFIX_DEFS
    if affix_id is not None and affix_id in AFFIX_DEFS:
        af = AFFIX_DEFS[affix_id]
        hp = int(hp * af["hp_mult"])
        exp_reward = int(exp_reward * af["exp_mult"])
    world.add_component(eid, MonsterComponent(name, exp_reward, affix=affix_id))
    world.add_component(eid, HPComponent(hp=hp, max_hp=hp))
    world.add_component(eid, RespawnComponent(respawn_time=respawn_time))
    world.add_component(eid, StatusEffectComponent())
    # 储存词缀数据
    if affix_id is not None:
        from .monster_affixes import AFFIX_DEFS
        af_data = AFFIX_DEFS.get(affix_id, {})
        dodge = af_data.get("dodge_bonus", 0.0)
        dr = af_data.get("damage_reduction", 0)
        if dodge > 0 or dr > 0:
            buff = world.get_component(eid, BuffComponent)
            if buff is None:
                buff = BuffComponent()
                world.add_component(eid, buff)
            buff.dodge_bonus = dodge
            buff.damage_reduction = dr
    return eid


def create_boss(world: World, player_level: int) -> int:
    """
    创建 Boss 怪物（3× 属性，必定带词缀）
    """
    name = f"BOSS·{_random_monster_name()}"
    hp = (40 + player_level * 35) * 3
    exp_reward = (8 + player_level * 6) * 4
    respawn_time = 30  # Boss 复活较慢

    eid = world.create_entity()
    world.add_component(eid, MonsterTag())
    affix_id = random_affix() or "elite"  # Boss 必定有词缀
    display_name = "👑 " + name + get_affix_display(affix_id)
    world.add_component(eid, NameComponent(display_name))

    world.add_component(eid, MonsterComponent(name, exp_reward, affix=affix_id))
    world.add_component(eid, HPComponent(hp=hp, max_hp=hp))
    world.add_component(eid, RespawnComponent(respawn_time=respawn_time))
    world.add_component(eid, StatusEffectComponent())
    return eid


def create_all_monsters(world: World, player_level: int = 1) -> list[int]:
    """
    创建怪物群（罐头游戏：基于玩家等级动态生成）。
    返回 [entity_id, ...]
    """
    count = 6
    ids: list[int] = []
    for i in range(count):
        lv = max(1, player_level + i - 3)  # 梯度等级
        eid = create_monster(world, level=lv)
        ids.append(eid)
    return ids
