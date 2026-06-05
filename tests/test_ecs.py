"""ECS 架构单元测试 — Entity / Component / World / System。"""
import pytest
from core.ecs import Component, Entity, World, System
from components.grid_position import GridPosition
from components.memory import Memory
from components.interactable import Interactable
from components.card_collectible import CardCollectible
from components.sanity import Sanity


# ─── Component ─────────────────────────────────────────


class TestComponent:
    def test_attribute_injection(self):
        c = Component(foo=42, bar="hello")
        assert c.foo == 42
        assert c.bar == "hello"

    def test_default_empty(self):
        c = Component()
        assert c.__dict__ == {}

    def test_type_isolation(self):
        """不同 Component 子类实例互不干扰。"""
        a = GridPosition(col=1, row=2)
        b = Memory(memory_id="test")
        assert a.col == 1
        assert a.row == 2
        assert b.memory_id == "test"
        assert not hasattr(a, "memory_id")


# ─── Entity ────────────────────────────────────────────


class TestEntity:
    def test_eid(self):
        e = Entity("foo")
        assert e.eid == "foo"

    def test_add_component(self):
        e = Entity("e")
        e.add(GridPosition(col=5, row=7))
        assert GridPosition in e.components
        assert e.get(GridPosition).col == 5

    def test_add_same_type_replaces(self):
        e = Entity("e")
        e.add(GridPosition(col=1, row=1))
        e.add(GridPosition(col=2, row=2))
        assert e.get(GridPosition).col == 2  # 后者覆盖前者

    def test_get_by_type(self, player_entity):
        gp = player_entity.get(GridPosition)
        assert gp is not None
        assert gp.col == 19
        assert gp.row == 13

    def test_remove_component(self, player_entity):
        player_entity.remove_component(GridPosition)
        assert GridPosition not in player_entity.components

    def test_remove_nonexistent_no_crash(self, player_entity):
        player_entity.remove_component(type("Fake", (), {}))  # 不存在的类型


# ─── World ─────────────────────────────────────────────


class TestWorld:
    def test_add_entity(self, world, player_entity):
        world.add_entity(player_entity)
        assert world.entities["player"] is player_entity

    def test_add_entity_overwrites_by_eid(self, world):
        e1 = Entity("dup")
        e2 = Entity("dup")
        world.add_entity(e1)
        world.add_entity(e2)
        assert world.entities["dup"] is e2

    def test_add_system(self, world):
        class DummySys(System):
            def update(self, w, dt): pass
        s = DummySys()
        world.add_system(s)
        assert len(world.systems) == 1

    def test_update_calls_all_systems(self, world):
        calls = []
        class SysA(System):
            def update(self, w, dt): calls.append("A")
        class SysB(System):
            def update(self, w, dt): calls.append("B")

        world.add_system(SysA())
        world.add_system(SysB())
        world.update(0.016)
        assert calls == ["A", "B"]


# ─── 多 Component 组合 ─────────────────────────────────


class TestEntityWithMultipleComponents:
    def test_card_collectible_combo(self, card_entity):
        """验证卡牌 Entity 同时持有 GridPosition + CardCollectible + Interactable。"""
        assert GridPosition in card_entity.components
        assert CardCollectible in card_entity.components
        assert Interactable in card_entity.components
        cc = card_entity.get(CardCollectible)
        assert cc.card_id == "test_card"
        assert cc.collected is False

    def test_memory_combo(self, memory_entity):
        """验证记忆 Entity 同时持有 GridPosition + Memory + Interactable。"""
        assert GridPosition in memory_entity.components
        assert Memory in memory_entity.components
        assert Interactable in memory_entity.components
        m = memory_entity.get(Memory)
        assert m.memory_id == "test_memory"
        assert m.discovered is False

    def test_multi_hitbox(self, multi_hitbox_entity):
        """验证多格物件 hitbox 正确存储。"""
        ia = multi_hitbox_entity.get(Interactable)
        assert ia.hitbox_width == 40    # 2 * 20
        assert ia.hitbox_height == 20   # 1 * 20
