"""
test/test_systems.py — systems 层单元测试

测试游戏系统（Inventory / PuzzleSystem / SaveLoadManager）。

运行：
    cd D:/allin/allin_engine && python -m test.test_systems
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.systems import Inventory, InventoryItem, Puzzle, PuzzleSystem, SaveLoadManager
from allin_engine.world import GameState


# ══════════════════════════════════════════════════════════
# Inventory 测试
# ══════════════════════════════════════════════════════════


def test_inventory_create():
    """测试背包创建"""
    inv = Inventory(capacity=10)
    assert inv.capacity == 10
    assert inv.item_count == 0


def test_inventory_add_item():
    """测试添加物品（返回 (success, message) 元组）"""
    inv = Inventory(capacity=10)
    item = InventoryItem("sword", "铁剑", item_type="weapon")
    success, msg = inv.add(item)
    assert success is True
    assert inv.item_count == 1


def test_inventory_get_item():
    """测试获取物品"""
    inv = Inventory(capacity=10)
    item = InventoryItem("sword", "铁剑", item_type="weapon")
    inv.add(item)
    retrieved = inv.get("sword")
    assert retrieved is not None
    assert retrieved.name == "铁剑"


def test_inventory_remove_item():
    """测试移除物品（返回 True/False）"""
    inv = Inventory(capacity=10)
    item = InventoryItem("sword", "铁剑", item_type="weapon")
    inv.add(item)
    assert inv.item_count == 1
    result = inv.remove("sword")
    assert result is True
    assert inv.item_count == 0


def test_inventory_has():
    """测试检查物品是否存在"""
    inv = Inventory(capacity=10)
    item = InventoryItem("sword", "铁剑", item_type="weapon")
    inv.add(item)
    assert inv.has("sword") is True
    assert inv.has("nonexistent") is False


def test_inventory_iter():
    """测试遍历物品"""
    inv = Inventory(capacity=10)
    inv.add(InventoryItem("a", "A", item_type="misc"))
    inv.add(InventoryItem("b", "B", item_type="misc"))
    items = list(inv.all_items)
    assert len(items) == 2


def test_inventory_capacity():
    """测试背包容量限制"""
    inv = Inventory(capacity=2)
    inv.add(InventoryItem("a", "A", item_type="misc"))
    inv.add(InventoryItem("b", "B", item_type="misc"))
    assert inv.item_count == 2
    # 容量已满，添加失败
    success, msg = inv.add(InventoryItem("c", "C", item_type="misc"))
    assert success is False
    assert inv.item_count == 2


# ══════════════════════════════════════════════════════════
# Puzzle 测试
# ══════════════════════════════════════════════════════════


def test_puzzle_create():
    """测试谜题创建"""
    puzzle = Puzzle(puzzle_id="door_puzzle", title="开门谜题")
    assert puzzle.puzzle_id == "door_puzzle"
    assert puzzle.title == "开门谜题"
    assert puzzle.attempts_used == 0


def test_puzzle_verify():
    """测试验证答案（verify_answer 返回 dict）"""
    sys = PuzzleSystem()
    puzzle = Puzzle(
        puzzle_id="test",
        title="测试",
        answer=["42", "四十二"],
    )
    sys.register(puzzle)
    
    result = sys.verify_answer("test", "42")
    assert result["success"] is True
    
    result = sys.verify_answer("test", "wrong")
    assert result["success"] is False


# ══════════════════════════════════════════════════════════
# PuzzleSystem 测试
# ══════════════════════════════════════════════════════════


def test_puzzle_system_create():
    """测试谜题系统创建"""
    sys = PuzzleSystem()
    assert sys.total_count == 0


def test_puzzle_system_add():
    """测试添加谜题（使用 register）"""
    sys = PuzzleSystem()
    puzzle = Puzzle(puzzle_id="test", title="测试")
    sys.register(puzzle)
    assert sys.total_count == 1
    assert sys.get_puzzle("test") is puzzle


def test_puzzle_system_get_nonexistent():
    """测试获取不存在的谜题"""
    sys = PuzzleSystem()
    result = sys.get_puzzle("nonexistent")
    assert result is None


# ══════════════════════════════════════════════════════════
# SaveLoadManager 测试
# ══════════════════════════════════════════════════════════


def test_save_load_create():
    """测试存档管理器创建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SaveLoadManager(save_dir=tmpdir)
        assert mgr.save_dir == tmpdir


def test_save_load_save_and_load():
    """测试存档和读档（load 返回 dict，需用 GameState.from_dict 反序列化）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SaveLoadManager(save_dir=tmpdir)

        # 创建测试数据
        state = GameState()
        state.set_flag("test_flag")
        state.set_var("room", "room_001")

        # 存档（无 label 参数）
        result = mgr.save(state, slot=0)
        assert result is True

        # 读档（返回 dict）
        data = mgr.load(0)
        assert data is not None
        # flags 在 player 里
        assert data["player"]["flags"]["test_flag"] is True
        assert data["variables"]["room"] == "room_001"

        # 反序列化为 GameState
        loaded = GameState.from_dict(data)
        assert loaded.has_flag("test_flag")
        assert loaded.get_var("room") == "room_001"


def test_save_load_list_slots():
    """测试列出存档（使用 list_saves）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SaveLoadManager(save_dir=tmpdir)

        # 空列表
        saves = mgr.list_saves()
        assert len(saves) == 0

        # 创建一个存档
        state = GameState()
        mgr.save(state, slot=1)
        saves = mgr.list_saves()
        assert len(saves) == 1
        assert saves[0].slot == 1


# ══════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    from allin_engine.test.runner import TestRunner

    runner = TestRunner(timeout=5.0)

    tests = [
        # Inventory
        test_inventory_create,
        test_inventory_add_item,
        test_inventory_get_item,
        test_inventory_remove_item,
        test_inventory_has,
        test_inventory_iter,
        test_inventory_capacity,
        # Puzzle
        test_puzzle_create,
        test_puzzle_verify,
        # PuzzleSystem
        test_puzzle_system_create,
        test_puzzle_system_add,
        test_puzzle_system_get_nonexistent,
        # SaveLoadManager
        test_save_load_create,
        test_save_load_save_and_load,
        test_save_load_list_slots,
    ]

    print("=" * 50)
    print("  systems 层单元测试")
    print("=" * 50)
    print()

    results = runner.run_tests(tests)

    passed = sum(1 for r in results if r.success)
    print()
    print(f"结果: {passed}/{len(results)} 通过")
