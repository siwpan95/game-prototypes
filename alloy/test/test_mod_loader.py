"""
test/test_mod_loader.py — ModLoader 数据驱动集成测试

测试 CardLibrary/EnemyLibrary 的 JSON 文件加载，以及
ModManager 的 Mod 发现、地图解析、传送门/机关数据驱动链路。

运行：
    cd D:/allin && python -m alloy.test.test_mod_loader
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from alloy.systems.combat import CardLibrary, EnemyLibrary
from alloy.systems.mod_loader import (
    ModManager, MapManager, MapDef, ModManifest,
    PortalDef, MechanismDef, MechanismAction,
)


# ══════════════════════════════════════════════════════════
# JSON 文件加载测试 — CardLibrary
# ══════════════════════════════════════════════════════════

def test_card_library_load_json_file():
    """测试 CardLibrary 从 JSON 文件加载"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cards_path = os.path.join(tmpdir, "cards.json")
        data = [
            {"id": "slash", "name": "斩击", "damage": 6, "ap_cost": 1},
            {"id": "block", "name": "防御", "block": 5, "ap_cost": 1},
            {"id": "heal", "name": "治疗", "heal": 10, "ap_cost": 2},
        ]
        with open(cards_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        lib = CardLibrary()
        lib.load_from_json(cards_path)
        assert lib.count == 3
        assert lib.has_card("slash")
        assert lib.has_card("block")
        assert lib.has_card("heal")


def test_card_library_load_json_dir():
    """测试 CardLibrary 从目录批量加载"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cards_dir = os.path.join(tmpdir, "cards")
        os.makedirs(cards_dir)

        with open(os.path.join(cards_dir, "attacks.json"), "w", encoding="utf-8") as f:
            json.dump([{"id": "slash", "name": "斩击", "damage": 6}], f, ensure_ascii=False)
        with open(os.path.join(cards_dir, "defense.json"), "w", encoding="utf-8") as f:
            json.dump([{"id": "block", "name": "防御", "block": 5}], f, ensure_ascii=False)

        lib = CardLibrary()
        lib.load_from_json(cards_dir)
        assert lib.count == 2
        assert lib.has_card("slash")
        assert lib.has_card("block")


def test_card_library_load_wrapped_json():
    """测试 CardLibrary 支持 {"cards": [...]} 格式"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cards_path = os.path.join(tmpdir, "cards.json")
        data = {"cards": [
            {"id": "slash", "name": "斩击", "damage": 6},
            {"id": "block", "name": "防御", "block": 5},
        ]}
        with open(cards_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        lib = CardLibrary()
        lib.load_from_json(cards_path)
        assert lib.count == 2


def test_card_library_from_json():
    """测试 CardLibrary.from_json 快捷方法"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cards_path = os.path.join(tmpdir, "cards.json")
        with open(cards_path, "w", encoding="utf-8") as f:
            json.dump([{"id": "slash", "name": "斩击", "damage": 6}], f, ensure_ascii=False)

        lib = CardLibrary.from_json(cards_path)
        assert lib.count == 1
        assert lib.has_card("slash")


# ══════════════════════════════════════════════════════════
# JSON 文件加载测试 — EnemyLibrary
# ══════════════════════════════════════════════════════════

def test_enemy_library_load_json_file():
    """测试 EnemyLibrary 从 JSON 文件加载"""
    with tempfile.TemporaryDirectory() as tmpdir:
        enemies_path = os.path.join(tmpdir, "enemies.json")
        data = [
            {
                "id": "goblin", "name": "哥布林", "hp": 30, "max_hp": 30,
                "intents": [{"name": "爪击", "damage": 5}],
            },
            {
                "id": "dragon", "name": "巨龙", "hp": 200, "max_hp": 200,
                "is_boss": True,
                "intents": [
                    {"name": "龙息", "damage": 20, "effect_tag": "HIGH_PRESS"},
                    {"name": "爪击", "damage": 10},
                ],
            },
        ]
        with open(enemies_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        lib = EnemyLibrary()
        lib.load_from_json(enemies_path)
        assert lib.count == 2
        assert lib.has_enemy("goblin")
        assert lib.has_enemy("dragon")

        dragon = lib.get_enemy("dragon")
        assert dragon.is_boss is True
        assert len(dragon.intents) == 2


def test_enemy_library_load_wrapped_json():
    """测试 EnemyLibrary 支持 {"enemies": [...]} 格式"""
    with tempfile.TemporaryDirectory() as tmpdir:
        enemies_path = os.path.join(tmpdir, "enemies.json")
        data = {"enemies": [
            {"id": "goblin", "name": "哥布林", "hp": 30, "max_hp": 30},
        ]}
        with open(enemies_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        lib = EnemyLibrary()
        lib.load_from_json(enemies_path)
        assert lib.count == 1
        assert lib.has_enemy("goblin")


# ══════════════════════════════════════════════════════════
# 数据类测试
# ══════════════════════════════════════════════════════════

def test_portal_def():
    """测试 PortalDef 数据类"""
    portal = PortalDef(
        col=5, row=3, char="▣",
        target_mod="dungeon", target_map="level_2",
        target_col=1, target_row=1,
    )
    assert portal.col == 5
    assert portal.target_mod == "dungeon"
    assert portal.target_map == "level_2"


def test_mechanism_def():
    """测试 MechanismDef 数据类"""
    mech = MechanismDef(
        mech_id="open_gate",
        trigger_type="ITEM_USED",
        trigger_id="iron_key",
        desc="用铁钥匙打开大门",
        actions=[MechanismAction(type="replace_at", params={"col": 5, "row": 2, "from": "门", "to": " "})],
    )
    assert mech.mech_id == "open_gate"
    assert mech.trigger_type == "ITEM_USED"
    assert len(mech.actions) == 1
    assert mech.actions[0].type == "replace_at"


def test_map_def():
    """测试 MapDef 数据类"""
    md = MapDef(
        map_id="village",
        name="新手村",
        map_file="maps/village.txt",
        player_start=(5, 10),
        portals=[
            PortalDef(col=0, row=5, target_map="forest"),
        ],
        metadata={"theme": "peaceful"},
    )
    assert md.map_id == "village"
    assert md.name == "新手村"
    assert md.player_start == (5, 10)
    assert len(md.portals) == 1


def test_mod_manifest():
    """测试 ModManifest 数据类"""
    manifest = ModManifest(
        mod_id="my_mod",
        name="我的Mod",
        version="1.2",
        description="测试用Mod",
        root_dir=Path("/fake/mods/my_mod"),
        maps={
            "start": MapDef(map_id="start", name="开始"),
        },
        dependencies=["base"],
    )
    assert manifest.mod_id == "my_mod"
    assert manifest.get_map("start") is not None
    assert manifest.has_map("start") is True
    assert manifest.has_map("nonexistent") is False


# ══════════════════════════════════════════════════════════
# ModManager 集成测试
# ══════════════════════════════════════════════════════════

def test_mod_manager_discover():
    """测试 ModManager 发现 Mod"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mods_dir = os.path.join(tmpdir, "mods")
        os.makedirs(mods_dir)

        mod_dir = os.path.join(mods_dir, "test_mod")
        os.makedirs(mod_dir)

        manifest = {
            "mod_id": "test_mod",
            "name": "测试Mod",
            "version": "1.0",
            "maps": [
                {
                    "map_id": "start",
                    "name": "开始地图",
                    "player_start": {"col": 5, "row": 10},
                    "portals": [
                        {"col": 0, "row": 0, "char": "▼", "target_map": "forest"}
                    ],
                    "mechanisms": [
                        {
                            "id": "open_door",
                            "trigger_type": "ITEM_USED",
                            "trigger_id": "key",
                            "desc": "打开门",
                            "actions": [
                                {"type": "replace_at", "col": 5, "row": 2, "from": "门", "to": " "}
                            ],
                        }
                    ],
                }
            ],
        }
        with open(os.path.join(mod_dir, "mod.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)

        mgr = ModManager(mods_dir)
        assert mgr.get_mod("test_mod") is not None

        mod = mgr.get_mod("test_mod")
        assert mod.name == "测试Mod"
        assert mod.version == "1.0"

        # 地图解析
        result = mgr.get_map("test_mod", "start")
        assert result is not None
        _, mdef = result
        assert mdef.map_id == "start"
        assert mdef.name == "开始地图"
        assert mdef.player_start == (5, 10)

        # 传送门
        assert len(mdef.portals) == 1
        portal = mdef.portals[0]
        assert portal.col == 0
        assert portal.row == 0
        assert portal.target_map == "forest"

        # 机关
        assert len(mdef.mechanisms) == 1
        mech = mdef.mechanisms[0]
        assert mech.mech_id == "open_door"
        assert mech.trigger_type == "ITEM_USED"
        assert mech.trigger_id == "key"
        assert len(mech.actions) == 1
        assert mech.actions[0].type == "replace_at"
        assert mech.actions[0].params["from"] == "门"


def test_mod_manager_empty_mods_dir():
    """测试空的 mods 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mods_dir = os.path.join(tmpdir, "mods")
        os.makedirs(mods_dir)
        mgr = ModManager(mods_dir)
        assert len(mgr.list_mods()) == 0


def test_mod_manager_nonexistent_mods_dir():
    """测试不存在的 mods 目录"""
    mgr = ModManager("/tmp/nonexistent_xyz_mods_dir")
    assert len(mgr.list_mods()) == 0


def test_mod_manager_list_maps():
    """测试列出所有地图"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mods_dir = os.path.join(tmpdir, "mods")
        os.makedirs(mods_dir)

        mod_dir = os.path.join(mods_dir, "test_mod")
        os.makedirs(mod_dir)

        manifest = {
            "mod_id": "test_mod",
            "name": "测试Mod",
            "maps": [
                {"map_id": "start", "name": "开始"},
                {"map_id": "forest", "name": "森林"},
            ],
        }
        with open(os.path.join(mod_dir, "mod.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)

        mgr = ModManager(mods_dir)
        maps = mgr.list_maps()
        assert len(maps) == 2


def test_mod_manager_find_data_dirs():
    """测试 find_data_dirs 通用数据查找"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mods_dir = os.path.join(tmpdir, "mods")
        os.makedirs(mods_dir)

        mod_dir = os.path.join(mods_dir, "test_mod")
        # 创建 cards 子目录
        cards_dir = os.path.join(mod_dir, "cards")
        os.makedirs(cards_dir)

        # 写入 mod.json
        manifest = {"mod_id": "test_mod", "name": "测试"}
        with open(os.path.join(mod_dir, "mod.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)

        mgr = ModManager(mods_dir)
        dirs = mgr.find_data_dirs("cards")
        assert len(dirs) == 1
        assert dirs[0].name == "cards"


def test_mod_manager_get_nonexistent_mod():
    """测试获取不存在的 Mod 返回 None"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ModManager(tmpdir)
        assert mgr.get_mod("nonexistent") is None
        assert mgr.get_map("nonexistent", "start") is None
