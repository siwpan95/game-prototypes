"""World 直接序列化 — 补齐 "World 不可直接序列化" 短板。

提供 SerializableWorld(World)，对齐引擎既有 to_dict / from_dict 契约，
可直接交给 SaveLoadManager 存档 / 读档，无需项目侧自行 to_dict。

纯新增模块，不修改 allin_engine.core.ecs 的 World 类。
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Type

from allin_engine.core.ecs import World, Component, System


class SerializableWorld(World):
    """可序列化的 World。

    catalog 注册组件 / 系统类（按 __name__），反序列化时据此重建实例。

    用法：
        world = SerializableWorld(component_catalog={Pos, Health}, system_catalog={MoveSys})
        world.create_entity("player").add(Pos(1, 2)).add(Health(100))
        world.add_system(MoveSys())
        mgr.save(world, slot=0)                         # SaveLoadManager 直接吃
        data = mgr.load(0)
        world2 = SerializableWorld.from_dict(data, component_catalog, system_catalog)
    """

    def __init__(
        self,
        component_catalog: Optional[Dict[str, Type[Component]]] = None,
        system_catalog: Optional[Dict[str, Type[System]]] = None,
    ):
        super().__init__()
        self._comp_catalog: Dict[str, Type[Component]] = dict(component_catalog or {})
        self._sys_catalog: Dict[str, Type[System]] = dict(system_catalog or {})

    # ── 序列化 ──
    def to_dict(self) -> dict:
        entities: List[dict] = []
        for e in self._entities_by_id.values():
            comps: Dict[str, Any] = {}
            for ctype, comp in e.components.items():
                if dataclasses.is_dataclass(comp):
                    comps[ctype.__name__] = dataclasses.asdict(comp)
                else:
                    comps[ctype.__name__] = getattr(comp, "__dict__", comp)
            entities.append({"eid": e.eid, "id": e.id, "components": comps})

        systems: List[dict] = []
        for s in self.systems:
            sname = type(s).__name__
            sstate = s.to_dict() if hasattr(s, "to_dict") else None
            systems.append({"name": sname, "priority": getattr(s, "priority", 100), "state": sstate})

        return {"entities": entities, "systems": systems, "data": self._data}

    # ── 反序列化 ──
    @classmethod
    def from_dict(
        cls,
        data: dict,
        component_catalog: Optional[Dict[str, Type[Component]]] = None,
        system_catalog: Optional[Dict[str, Type[System]]] = None,
    ) -> "SerializableWorld":
        world = cls(component_catalog=component_catalog, system_catalog=system_catalog)
        comp_cat = world._comp_catalog
        sys_cat = world._sys_catalog

        # 重建实体 + 组件
        for ed in data.get("entities", []):
            e = world.create_entity(ed.get("eid"))
            for cname, cval in ed.get("components", {}).items():
                ctype = comp_cat.get(cname)
                if ctype is None:
                    continue
                try:
                    comp = ctype(**cval) if isinstance(cval, dict) else ctype(cval)
                except Exception:
                    comp = ctype(**(cval or {}))
                e.add(comp)

        # 重建系统
        for sd in data.get("systems", []):
            stype = sys_cat.get(sd.get("name"))
            if stype is None:
                continue
            try:
                s = stype() if not sd.get("state") else stype(**(sd.get("state") or {}))
            except Exception:
                s = stype()
            world.add_system(s)

        # 全局数据
        world._data.update(data.get("data", {}) or {})
        return world
