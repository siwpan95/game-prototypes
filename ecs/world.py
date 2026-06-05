"""
ECS World — 轻量实现，无外部依赖
Entity = int（自增 ID）
组件存储：{entity: {ComponentClass: instance}}
"""

from typing import Any, Callable, Dict, List, Set, Tuple, Type


class World:
    """ECS 世界：管理实体生命周期与组件查询"""

    def __init__(self) -> None:
        self._next_id: int = 1
        # entity -> {ComponentClass: component_instance}
        self._components: Dict[int, Dict[Type[Any], Any]] = {}
        self._entities: Set[int] = set()
        # 系统列表（callable，接收 world, dt）
        self._systems: List[Callable[["World", float], None]] = []

    # ── 实体管理 ──────────────────────────────────────────────

    def create_entity(self) -> int:
        eid = self._next_id
        self._next_id += 1
        self._entities.add(eid)
        self._components[eid] = {}
        return eid

    def destroy_entity(self, eid: int) -> None:
        self._entities.discard(eid)
        self._components.pop(eid, None)

    def entity_exists(self, eid: int) -> bool:
        return eid in self._entities

    # ── 组件管理 ──────────────────────────────────────────────

    def add_component(self, eid: int, component: Any) -> None:
        comp_cls = type(component)
        self._components[eid][comp_cls] = component

    def remove_component(self, eid: int, comp_cls: Type[Any]) -> None:
        self._components[eid].pop(comp_cls, None)

    def get_component(self, eid: int, comp_cls: Type[Any]) -> Any | None:
        return self._components[eid].get(comp_cls)

    def has_component(self, eid: int, comp_cls: Type[Any]) -> bool:
        return comp_cls in self._components[eid]

    # ── 查询（核心操作）──────────────────────────────────────

    def get_components(self, *comp_clses: Type[Any]) -> List[Tuple[int, ...]]:
        """
        返回 [(eid, comp1, comp2, ...), ...]
        仅返回同时拥有所有指定组件的实体
        """
        result: List[Tuple[int, ...]] = []
        for eid in self._entities:
            comps = self._components[eid]
            if all(cls in comps for cls in comp_clses):
                row: List[int | Any] = [eid]
                row.extend(comps[cls] for cls in comp_clses)
                result.append(tuple(row))  # type: ignore[arg-type]
        return result

    def get_entities_with(self, comp_cls: Type[Any]) -> List[int]:
        """返回拥有指定组件的所有实体 ID"""
        return [eid for eid in self._entities
                if comp_cls in self._components[eid]]

    # ── 系统管理 ──────────────────────────────────────────────

    def register_system(self, system_fn: Callable[["World", float], None]) -> None:
        self._systems.append(system_fn)

    def tick(self, dt: float) -> None:
        """驱动所有系统执行一帧"""
        for sys_fn in self._systems:
            sys_fn(self, dt)
