"""
ECS 架构核心 — 类型安全版本
====================================
使用 dataclass 实现类型安全的 Component，添加组件查询和系统优先级控制。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional, Set, Type, TypeVar

T = TypeVar("T")


# ─── Component ─────────────────────────────────────────

class Component(ABC):
    """
    所有组件的抽象基类。

    使用 dataclass 继承可获得类型安全的组件：

        @dataclass
        class Sanity(Component):
            value: int = 100
            max_value: int = 100
    """
    pass


def is_component(obj: Any) -> bool:
    """检查对象是否是 Component 实例。"""
    return isinstance(obj, Component)


# ─── Entity ────────────────────────────────────────────

class Entity:
    """
    实体 — 组件的容器。

    使用组件类型（class）作为键存取组件，
    支持类型安全的组件查询。
    """

    __slots__ = ("eid", "components", "_portal_data")

    def __init__(self, eid: str) -> None:
        self.eid = eid
        self.components: Dict[Type[Component], Component] = {}

    def add(self, comp: Component) -> "Entity":
        """添加组件，返回 self 支持链式调用。"""
        self.components[type(comp)] = comp
        return self

    def get(self, comp_type: Type[T]) -> Optional[T]:
        """获取组件，类型安全。"""
        return self.components.get(comp_type)

    def has(self, comp_type: Type[Component]) -> bool:
        """检查是否拥有指定组件。"""
        return comp_type in self.components

    def remove(self, comp_type: Type[Component]) -> Optional[Component]:
        """移除组件，返回被移除的组件或 None。"""
        return self.components.pop(comp_type, None)

    def __repr__(self) -> str:
        comp_names = ", ".join(c.__name__ for c in self.components)
        return f"Entity({self.eid!r}, [{comp_names}])"


# ─── System ────────────────────────────────────────────

class System(ABC):
    """
    系统基类 — 处理拥有特定组件的实体。

    子类需要实现 update() 方法。
    可选实现 priority 类属性来控制执行顺序（数值越小越先执行）。
    """

    priority: int = 100  # 默认优先级

    @abstractmethod
    def update(self, world: "World", dt: float) -> None:
        """系统更新逻辑。由 World.update() 调用。"""
        ...

    def enabled(self, world: "World") -> bool:
        """可选：控制系统是否启用。默认始终启用。"""
        return True


# ─── World ─────────────────────────────────────────────

class World:
    """
    游戏世界 — 管理所有实体和系统。

    提供类型安全的组件查询、系统优先级排序。
    """

    def __init__(self) -> None:
        self.entities: Dict[str, Entity] = {}
        self.systems: List[System] = []
        self._systems_sorted: bool = True  # 标记是否需要重新排序

    # ── 实体管理 ──────────────────────────────────────

    def add_entity(self, entity: Entity) -> Entity:
        """添加实体（同名 eid 会被覆盖）。返回实体支持链式调用。"""
        self.entities[entity.eid] = entity
        return entity

    def get_entity(self, eid: str) -> Optional[Entity]:
        """按 eid 获取实体。"""
        return self.entities.get(eid)

    def remove_entity(self, eid: str) -> Optional[Entity]:
        """移除并返回实体。"""
        return self.entities.pop(eid, None)

    def entity_count(self) -> int:
        """当前实体数量（属性访问风格）。"""
        return len(self.entities)

    # ── 系统管理 ──────────────────────────────────────

    def add_system(self, system: System) -> "World":
        """添加系统，标记需要重新排序。"""
        self.systems.append(system)
        self._systems_sorted = False
        return self

    def remove_system(self, system_type: Type[System]) -> None:
        """按类型移除系统。"""
        self.systems = [s for s in self.systems if not isinstance(s, system_type)]
        self._systems_sorted = False

    def get_system(self, system_type: Type[T]) -> Optional[T]:
        """按类型获取系统。"""
        for s in self.systems:
            if isinstance(s, system_type):
                return s  # type: ignore
        return None

    def _ensure_systems_sorted(self) -> None:
        """确保系统按优先级排序。"""
        if not self._systems_sorted:
            self.systems.sort(key=lambda s: s.priority)
            self._systems_sorted = True

    # ── 组件查询（核心功能）────────────────────────

    def get_entities_with_components(self, *comp_types: Type[Component]) -> List[Entity]:
        """
        返回同时拥有所有指定组件的实体列表。

        示例：
            # 获取所有可交互且可碰撞的实体
            world.get_entities_with_components(GridPosition, Interactable)
        """
        result = []
        for entity in self.entities.values():
            if all(e.has(t) for t in comp_types):
                result.append(entity)
        return result

    def get_first_with_components(self, *comp_types: Type[Component]) -> Optional[Entity]:
        """返回第一个匹配所有组件的实体，或 None。"""
        for entity in self.entities.values():
            if all(e.has(t) for t in comp_types):
                return entity
        return None

    def each(self, *comp_types: Type[Component]):
        """
        生成器：遍历所有拥有指定组件的实体。

        用法：
            for entity in world.each(GridPosition, Interactable):
                pos = entity.get(GridPosition)
                ...
        """
        for entity in self.entities.values():
            if all(entity.has(t) for t in comp_types):
                yield entity

    # ── 世界更新 ──────────────────────────────────────

    def update(self, dt: float) -> None:
        """
        按优先级顺序更新所有启用的系统。

        参数：
            dt: 帧间隔（毫秒）
        """
        self._ensure_systems_sorted()
        for system in self.systems:
            if system.enabled(self):
                system.update(self, dt)

    # ── 调试辅助 ──────────────────────────────────────

    def debug_print(self) -> None:
        """打印世界状态（调试用）。"""
        print(f"[World] {len(self.entities)} entities, {len(self.systems)} systems")
        for eid, entity in self.entities.items():
            print(f"  {entity}")
        for system in self.systems:
            print(f"  System: {system.__class__.__name__} (priority={system.priority})")
