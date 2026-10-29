"""savegame.py — 游戏存档 / 读档（JSON 序列化）。

把当前可玩状态（种子、层数、玩家、背包、已探索区域、陷阱、当前层几何与怪物）
完整写盘，下次可从断点续玩。地牢几何用 alloy 的 MapData.to_dict/from_dict，
怪物用模板 id + 坐标 + 实际 HP/伤害重建，物品用目录 id 重建。
"""
from __future__ import annotations

import json
import os

from alloy.world.map_data import MapData
from alloy.systems.inventory import Inventory
from entities import Position, Health, MobBrain, build_catalog, build_mob_library
from monster_ai import make_brain, make_boss_brain
from progression import compute_perk_mods
from director import Director

DEFAULT_SAVE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "savegame.json"
)


# ──────────────────────────────────────────────────────
#  序列化
# ──────────────────────────────────────────────────────

def _serialize_floor(floor: dict) -> dict:
    t = floor["terrain"]
    monsters_meta = []
    for m in floor.get("monsters", []):
        mb = m.get(MobBrain)
        pos = m.get(Position)
        h = m.get(Health)
        monsters_meta.append({
            "tid": mb.template.mob_id,
            "name": mb.name,
            "x": pos.x, "y": pos.y,
            "hp": h.value, "max_hp": h.max,
            "dmg": mb.template.damage,
            "ability": mb.ability,
            "status": list(mb.status_effects),
            "enraged": mb.enraged,
            "attack_range": mb.attack_range,
            "ranged_kind": mb.ranged_kind,
            "onhit": mb.onhit,
        })
    items = [{"pos": list(it["pos"]), "iid": it["iid"]}
             for it in floor.get("items", [])]
    structs = {k: list(v) for k, v in floor.get("structures", {}).items()}
    return {
        "terrain": t.to_dict(),
        "start": list(floor["start"]),
        "stairs": list(floor["stairs"]),
        "monsters_meta": monsters_meta,
        "items": items,
        "traps": [list(p) for p in floor.get("traps", set())],
        "structures": structs,
        "region": floor["region"],
        "biome": floor.get("biome"),
        "biome_desc": floor.get("biome_desc"),
        "is_boss": floor["is_boss"],
        "is_town": floor.get("is_town", False),
        "gen_kind": floor.get("gen_kind"),
        "loot_flavor": floor.get("loot_flavor", []),
        "floor_index": floor["floor_index"],
    }


def save_game(game, path: str = DEFAULT_SAVE_PATH) -> str:
    """把 game 当前状态写入 path，返回路径。"""
    path = path or DEFAULT_SAVE_PATH
    data = {
        "version": 2,
        "seed": game.seed,
        "total_floors": game.total_floors,
        "floor_index": game.floor_index,
        "player": {"hp": game.ps.hp, "max_hp": game.ps.max_hp},
        "gold": game.gold,
        "equipped_weapon": game.equipped_weapon,
        "equipped_armor": game.equipped_armor,
        "progression": {
            "level": game.progression.level,
            "xp": game.progression.xp,
            "xp_next": game.progression.xp_next,
            "perks": list(game.progression.perks),
        },
        "director": game.director.snapshot(),
        "inventory": game.inv.to_dict(),
        "explored": [list(p) for p in game.explored],
        "status_effects": game.status_effects,
        "floor": _serialize_floor(game.floor),
        "log_tail": game.logs[-12:],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# ──────────────────────────────────────────────────────
#  反序列化
# ──────────────────────────────────────────────────────

def _rebuild_floor(floor_d: dict, world) -> dict:
    """从存档字典重建当前层（几何 + 怪物实体 + 物品）。"""
    catalog = build_catalog()
    mob_lib = build_mob_library()
    terrain = MapData.from_dict(floor_d["terrain"])

    monsters = []
    for meta in floor_d["monsters_meta"]:
        base = mob_lib.get(meta["tid"])
        if base is None:
            continue
        # 重建本层实际缩放后的模板
        from entities import scale_template
        tmpl = scale_template(base, 1.0)
        tmpl.hp = meta["max_hp"]
        tmpl.damage = meta["dmg"]
        tmpl.metadata = dict(base.metadata)
        e = world.create_entity(f"mob_{meta['x']}_{meta['y']}")
        e.add(Position(meta["x"], meta["y"]))
        e.add(Health(meta["hp"], meta["max_hp"]))
        brain = MobBrain(tmpl, meta["name"], make_brain(),
                         ability=meta.get("ability"))
        brain.status_effects = list(meta.get("status", []))
        brain.enraged = meta.get("enraged", False)
        brain.attack_range = meta.get("attack_range", 1)
        brain.ranged_kind = meta.get("ranged_kind")
        brain.onhit = meta.get("onhit")
        if meta["tid"] == "dragon":
            bt, bb = make_boss_brain()
            brain.bt = bt
            brain.blackboard = bb
        e.add(brain)
        monsters.append(e)

    items = []
    for it in floor_d["items"]:
        iid = it["iid"]
        if iid in catalog:
            items.append({"pos": tuple(it["pos"]), "iid": iid,
                          "item": catalog[iid]})

    return {
        "terrain": terrain,
        "start": tuple(floor_d["start"]),
        "stairs": tuple(floor_d["stairs"]),
        "monsters": monsters,
        "items": items,
        "traps": set(tuple(p) for p in floor_d.get("traps", [])),
        "structures": {k: tuple(v) for k, v in floor_d.get("structures", {}).items()},
        "region": floor_d["region"],
        "biome": floor_d.get("biome"),
        "biome_desc": floor_d.get("biome_desc"),
        "is_boss": floor_d["is_boss"],
        "is_town": floor_d.get("is_town", False),
        "gen_kind": floor_d.get("gen_kind"),
        "loot_flavor": floor_d.get("loot_flavor", []),
        "floor_index": floor_d["floor_index"],
    }


def load_game(path: str = DEFAULT_SAVE_PATH):
    """从 path 读档，返回一个已恢复好的 Game 实例。

    调用方需传入 Game 类以避免循环依赖；用 Game(autobuild=False) 构造空壳后回填。
    """
    from game import Game  # 延迟导入，避免与 game 的顶层 import 形成环

    path = path or DEFAULT_SAVE_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    g = Game(seed=data["seed"], floors=data["total_floors"], autobuild=False)

    g.ps.hp = data["player"]["hp"]
    g.ps.max_hp = data["player"]["max_hp"]
    g.gold = data["gold"]
    g.equipped_weapon = data["equipped_weapon"]
    g.equipped_armor = data["equipped_armor"]
    # 成长系统：从已选 perk 重算加成（不重复触发即时效果）
    prog = data.get("progression", {"level": 1, "xp": 0, "xp_next": 18, "perks": []})
    g.progression.level = prog["level"]
    g.progression.xp = prog["xp"]
    g.progression.xp_next = prog["xp_next"]
    g.progression.perks = list(prog.get("perks", []))
    g.perk_mods = compute_perk_mods(g.progression.perks)
    g.director = Director.from_dict(data.get("director", {}))
    g.inv = Inventory.from_dict(data["inventory"])
    g.explored = set(tuple(p) for p in data.get("explored", []))
    g.status_effects = data.get("status_effects", [])

    g.floor = _rebuild_floor(data["floor"], g.world)
    g.floor_index = data["floor_index"]
    sx, sy = g.floor["start"]
    g.px, g.py = sx, sy
    g.player.get(Position).x = sx
    g.player.get(Position).y = sy
    g.monsters = g.floor["monsters"]
    g._reindex()
    g._update_fov()
    g._recompute_mods()
    g.status = "playing"
    g.logs = list(data.get("log_tail", []))
    g.logs.append("—— 读档成功，继续冒险 ——")
    return g
