"""
test/test_core.py — core 层单元测试

测试核心 ECS 架构和事件总线。

运行：
    cd <fish仓>/tools/allin_engine && python -m test.test_core
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.core import World, Entity, Component, System, EventBus, EventTypes


# ══════════════════════════════════════════════════════════
# 测试辅助
# ══════════════════════════════════════════════════════════


class Position(Component):
    """测试用组件：位置"""

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = x
        self.y = y


class Velocity(Component):
    """测试用组件：速度"""

    def __init__(self, vx: float = 0.0, vy: float = 0.0):
        self.vx = vx
        self.vy = vy


class Renderable(Component):
    """测试用组件：可渲染"""

    def __init__(self, char: str = "@"):
        self.char = char


class MovementSystem(System):
    """测试用系统：根据速度更新位置"""

    def update(self, world: World, dt: float) -> None:
        for entity in world.each_entity():
            pos = entity.get(Position)
            vel = entity.get(Velocity)
            if pos and vel:
                pos.x += vel.vx * dt
                pos.y += vel.vy * dt


# ══════════════════════════════════════════════════════════
# Entity 测试
# ══════════════════════════════════════════════════════════


def test_entity_create():
    """测试实体创建"""
    entity = Entity("player")
    assert entity.eid == "player"
    assert entity.id > 0


def test_entity_add_component():
    """测试实体添加组件"""
    entity = Entity("test")
    entity.add(Position(1, 2))
    pos = entity.get(Position)
    assert pos is not None
    assert pos.x == 1
    assert pos.y == 2


def test_entity_has_component():
    """测试实体检查组件"""
    entity = Entity("test")
    assert not entity.has(Position)
    entity.add(Position(0, 0))
    assert entity.has(Position)


def test_entity_remove_component():
    """测试实体移除组件"""
    entity = Entity("test")
    entity.add(Position(1, 2))
    assert entity.has(Position)
    entity.remove(Position)
    assert not entity.has(Position)


def test_entity_unique_id():
    """测试实体 ID 唯一性"""
    e1 = Entity()
    e2 = Entity()
    assert e1.id != e2.id


# ══════════════════════════════════════════════════════════
# World 测试
# ══════════════════════════════════════════════════════════


def test_world_create_entity():
    """测试 World 创建实体"""
    world = World()
    entity = world.create_entity("player")
    assert entity.eid == "player"
    assert world.get_entity("player") is entity


def test_world_add_system():
    """测试 World 添加系统"""
    world = World()
    sys = MovementSystem()
    world.add_system(sys)
    assert len(world.systems) == 1


def test_world_update():
    """测试 World 更新驱动系统"""
    world = World()
    entity = world.create_entity("player")
    entity.add(Position(0, 0))
    entity.add(Velocity(1, 0))

    world.add_system(MovementSystem())
    world.update(1.0)

    pos = entity.get(Position)
    assert pos.x == 1.0
    assert pos.y == 0.0


def test_world_get_entity_by_eid():
    """测试按 eid 获取实体"""
    world = World()
    entity = world.create_entity("player")
    result = world.get_entity("player")
    assert result is entity


def test_world_get_entity_by_id():
    """测试按 id 获取实体"""
    world = World()
    entity = world.create_entity("player")
    result = world.get_entity(entity.id)
    assert result is entity


def test_world_remove_entity():
    """测试移除实体"""
    world = World()
    entity = world.create_entity("player")
    assert world.get_entity("player") is not None
    removed = world.remove_entity("player")
    assert removed is entity
    assert world.get_entity("player") is None


def test_world_entity_count():
    """测试实体计数"""
    world = World()
    assert world.entity_count() == 0
    world.create_entity("a")
    world.create_entity("b")
    assert world.entity_count() == 2


# ══════════════════════════════════════════════════════════
# EventBus 测试
# ══════════════════════════════════════════════════════════


def test_event_bus_subscribe():
    """测试事件订阅"""
    bus = EventBus()
    events = []

    def handler(data):
        events.append(data)

    bus.subscribe("test_event", handler)
    bus.publish("test_event", value=123)  # data = {"value": 123}

    assert len(events) == 1
    assert events[0] == {"value": 123}


def test_event_bus_emit():
    """测试 emit 直接传数据"""
    bus = EventBus()
    events = []

    def handler(data):
        events.append(data)

    bus.subscribe("test", handler)
    bus.emit("test", "hello")

    assert len(events) == 1
    assert events[0] == "hello"


def test_event_bus_unsubscribe():
    """测试事件取消订阅"""
    bus = EventBus()
    events = []

    def handler(data):
        events.append(data)

    bus.subscribe("test_event", handler)
    bus.publish("test_event", x=1)
    assert len(events) == 1

    bus.unsubscribe("test_event", handler)
    bus.publish("test_event", x=2)
    assert len(events) == 1  # 仍然是 1


def test_event_bus_once():
    """测试一次性事件处理器"""
    bus = EventBus()
    count = [0]

    def handler(data):
        count[0] += 1

    bus.once("test", handler)
    bus.publish("test", x=1)
    bus.publish("test", x=2)

    assert count[0] == 1  # 只执行一次


def test_event_bus_return_count():
    """测试 emit/publish 返回通知数量"""
    bus = EventBus()

    def h1(data):
        pass

    def h2(data):
        pass

    bus.subscribe("test", h1)
    bus.subscribe("test", h2)

    result = bus.emit("test", "data")
    assert result == 2


def test_event_bus_clear():
    """测试清除监听器"""
    bus = EventBus()

    def handler(data):
        pass

    bus.subscribe("test1", handler)
    bus.subscribe("test2", handler)

    assert bus.listener_count("test1") == 1
    bus.clear("test1")
    assert bus.listener_count("test1") == 0
    assert bus.listener_count("test2") == 1


def test_event_bus_has_listeners():
    """测试检查是否有监听器"""
    bus = EventBus()

    def handler(data):
        pass

    assert not bus.has_listeners("test")
    bus.subscribe("test", handler)
    assert bus.has_listeners("test")


# ══════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    from allin_engine.test.runner import TestRunner

    runner = TestRunner(timeout=5.0)

    tests = [
        # Entity
        test_entity_create,
        test_entity_add_component,
        test_entity_has_component,
        test_entity_remove_component,
        test_entity_unique_id,
        # World
        test_world_create_entity,
        test_world_add_system,
        test_world_update,
        test_world_get_entity_by_eid,
        test_world_get_entity_by_id,
        test_world_remove_entity,
        test_world_entity_count,
        # EventBus
        test_event_bus_subscribe,
        test_event_bus_emit,
        test_event_bus_unsubscribe,
        test_event_bus_once,
        test_event_bus_return_count,
        test_event_bus_clear,
        test_event_bus_has_listeners,
    ]

    print("=" * 50)
    print("  core 层单元测试")
    print("=" * 50)
    print()

    results = runner.run_tests(tests)

    passed = sum(1 for r in results if r.success)
    print()
    print(f"结果: {passed}/{len(results)} 通过")
