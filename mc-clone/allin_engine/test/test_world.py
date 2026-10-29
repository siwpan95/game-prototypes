"""
test/test_world.py — world 层单元测试

测试世界模型（GameState / PlayerState / Item / Character / Room / MapGraph）。

运行：
    cd <仓库根>/allin_engine && python -m test.test_world
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.world import (
    GameState, PlayerState, Item, Character, Room, MapGraph, MapNode,
    Portal, Mechanism, MechanismAction,
)


# ══════════════════════════════════════════════════════════
# PlayerState 测试
# ══════════════════════════════════════════════════════════


def test_player_state_hp():
    """测试玩家 HP 调整"""
    player = PlayerState()
    assert player.hp == player.max_hp
    delta = player.adjust_hp(-20)
    assert delta == -20
    assert player.hp == player.max_hp - 20


def test_player_state_hp_clamp():
    """测试 HP 边界限制"""
    player = PlayerState()
    player.adjust_hp(-9999)
    assert player.hp == 0
    player.adjust_hp(9999)
    assert player.hp == player.max_hp


def test_player_state_add_item():
    """测试添加物品"""
    player = PlayerState()
    assert not player.has_item("iron_sword")
    result = player.add_item("iron_sword")
    assert result is True
    assert player.has_item("iron_sword")
    # 重复添加返回 False
    result = player.add_item("iron_sword")
    assert result is False


def test_player_state_remove_item():
    """测试移除物品"""
    player = PlayerState()
    player.add_item("iron_sword")
    assert player.has_item("iron_sword")
    result = player.remove_item("iron_sword")
    assert result is True
    assert not player.has_item("iron_sword")


def test_player_state_flags():
    """测试玩家标记"""
    player = PlayerState()
    assert not player.has_flag("door_opened")
    player.set_flag("door_opened")
    assert player.has_flag("door_opened")
    assert player.get_flag("door_opened") is True


def test_player_state_sanity():
    """测试理智值调整"""
    player = PlayerState()
    assert player.sanity == 70
    delta = player.adjust_sanity(-20)
    assert player.sanity == 50


def test_player_state_is_alive():
    """测试存活状态"""
    player = PlayerState()
    assert player.is_alive
    player.adjust_hp(-9999)
    assert not player.is_alive


# ══════════════════════════════════════════════════════════
# GameState 测试
# ══════════════════════════════════════════════════════════


def test_game_state_create():
    """测试 GameState 创建"""
    gs = GameState()
    assert gs.player is not None
    assert gs.variables == {}


def test_game_state_flags():
    """测试全局标记（代理到 PlayerState）"""
    gs = GameState()
    assert not gs.has_flag("boss_defeated")
    gs.set_flag("boss_defeated")
    assert gs.has_flag("boss_defeated")


def test_game_state_vars():
    """测试全局变量"""
    gs = GameState()
    assert gs.get_var("current_room") is None
    gs.set_var("current_room", "room_001")
    assert gs.get_var("current_room") == "room_001"


def test_game_state_serialization():
    """测试序列化/反序列化"""
    gs = GameState()
    gs.player.adjust_hp(-20)
    gs.set_flag("test_flag")
    gs.set_var("room", "room_001")

    data = gs.to_dict()
    assert isinstance(data, dict)

    gs2 = GameState.from_dict(data)
    assert gs2.player.hp == gs.player.hp
    assert gs2.has_flag("test_flag")
    assert gs2.get_var("room") == "room_001"


def test_game_state_record_event():
    """测试记录事件"""
    gs = GameState()
    assert len(gs.history) == 0
    gs.record_event("test", "测试事件")
    assert len(gs.history) == 1
    assert gs.history[0]["type"] == "test"


# ══════════════════════════════════════════════════════════
# Item 测试
# ══════════════════════════════════════════════════════════


def test_item_create():
    """测试物品创建"""
    item = Item(item_id="potion", name="回复药", item_type="consumable")
    assert item.item_id == "potion"
    assert item.name == "回复药"
    assert item.item_type == "consumable"


def test_item_effects():
    """测试物品效果"""
    item = Item(
        item_id="potion",
        name="回复药",
        item_type="consumable",
        usable=True,
        effects={"hp": 20, "sanity": 10},
    )
    assert item.effects["hp"] == 20
    assert item.effects["sanity"] == 10


def test_item_stats():
    """测试物品装备属性"""
    item = Item(
        item_id="iron_sword",
        name="铁剑",
        item_type="weapon",
        equippable=True,
        stats={"attack": 10, "speed": 2},
    )
    assert item.stats["attack"] == 10
    assert item.stats["speed"] == 2


def test_item_is_weapon():
    """测试物品类型判断"""
    sword = Item(item_id="sword", item_type="weapon")
    potion = Item(item_id="potion", item_type="consumable")
    assert sword.is_weapon
    assert not potion.is_weapon


# ══════════════════════════════════════════════════════════
# Character 测试
# ══════════════════════════════════════════════════════════


def test_character_create():
    """测试角色创建"""
    char = Character(char_id="npc_001", name="村长", role="narrator")
    assert char.char_id == "npc_001"
    assert char.name == "村长"


def test_character_stats_dict():
    """测试角色属性字典"""
    char = Character(char_id="enemy_001", name="哥布林", role="enemy")
    char.stats["hp"] = 30
    char.stats["attack"] = 8
    assert char.stats["hp"] == 30
    assert char.stats["attack"] == 8


def test_character_hostile():
    """测试角色敌对状态"""
    ally = Character(char_id="ally", role="ally")
    enemy = Character(char_id="enemy", role="enemy", is_hostile=True)
    assert not ally.is_enemy
    assert enemy.is_enemy


def test_character_hp():
    """测试角色 HP"""
    char = Character(char_id="enemy", hp=30, max_hp=30)
    assert char.hp == 30
    assert char.max_hp == 30


# ══════════════════════════════════════════════════════════
# Room 测试（按实际 API）
# ══════════════════════════════════════════════════════════


def test_room_create():
    """测试房间创建（字段名 room_id）"""
    room = Room(room_id="room_001", name="大厅")
    assert room.room_id == "room_001"
    assert room.name == "大厅"


def test_room_exits():
    """测试房间出口字典"""
    room = Room(room_id="room_001", name="大厅")
    room.set_exit("north", "room_002")
    room.set_exit("east", "room_003")
    assert room.has_exit("north")
    assert room.get_exit("north") == "room_002"
    assert not room.has_exit("south")


def test_room_items():
    """测试房间物品管理"""
    room = Room(room_id="room_001", name="大厅")
    assert not room.has_item("key")
    room.add_item("key")
    assert room.has_item("key")
    result = room.remove_item("key")
    assert result is True
    assert not room.has_item("key")


# ══════════════════════════════════════════════════════════
# MapGraph 测试（按实际 API）
# ══════════════════════════════════════════════════════════


def test_map_graph_create():
    """测试 MapGraph 创建"""
    graph = MapGraph()
    assert len(graph.nodes) == 0
    assert graph.current_node is None


def test_map_graph_add_node():
    """测试添加节点"""
    graph = MapGraph()
    node = MapNode(node_id="room_001", name="大厅")
    graph.add_node(node)
    assert len(graph.nodes) == 1
    assert graph.current_node == "room_001"  # 第一个节点自动设为当前
    assert graph.get_node("room_001") is node


def test_map_graph_navigation():
    """测试导航"""
    graph = MapGraph()
    graph.add_node(MapNode(node_id="hub", name="中心", connections=["room_a"]))
    graph.add_node(MapNode(node_id="room_a", name="房间A", connections=["hub"]))

    current = graph.get_current()
    assert current.node_id == "hub"

    can_move, reason = graph.can_move_to("room_a")
    assert can_move is True

    can_move, reason = graph.can_move_to("nonexistent")
    assert can_move is False


def test_map_node_connections():
    """测试节点连接"""
    node1 = MapNode(node_id="a", name="A")
    node2 = MapNode(node_id="b", name="B")

    node1.connect_to("b")
    node2.connect_to("a")

    assert node1.is_connected_to("b")
    assert node2.is_connected_to("a")

    node1.disconnect_from("b")
    assert not node1.is_connected_to("b")


# ══════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    from allin_engine.test.runner import TestRunner

    runner = TestRunner(timeout=5.0)

    tests = [
        # PlayerState
        test_player_state_hp,
        test_player_state_hp_clamp,
        test_player_state_add_item,
        test_player_state_remove_item,
        test_player_state_flags,
        test_player_state_sanity,
        test_player_state_is_alive,
        # GameState
        test_game_state_create,
        test_game_state_flags,
        test_game_state_vars,
        test_game_state_serialization,
        test_game_state_record_event,
        # Item
        test_item_create,
        test_item_effects,
        test_item_stats,
        test_item_is_weapon,
        # Character
        test_character_create,
        test_character_stats_dict,
        test_character_hostile,
        test_character_hp,
        # Room
        test_room_create,
        test_room_exits,
        test_room_items,
        # MapGraph
        test_map_graph_create,
        test_map_graph_add_node,
        test_map_graph_navigation,
        test_map_node_connections,
    ]

    print("=" * 50)
    print("  world 层单元测试")
    print("=" * 50)
    print()

    results = runner.run_tests(tests)

    passed = sum(1 for r in results if r.success)
    print()
    print(f"结果: {passed}/{len(results)} 通过")
