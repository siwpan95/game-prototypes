"""alloy.trpg.preset - TRPG 规则内核装配（D20 composition.yml → alloy 代码预设）

D20 原装配为纯 YAML 组合（composition.yml + d20.loader 拓扑排序 + 极简 YAML
解析器）。并入 alloy 后改为 alloy 风格的代码预设：按依赖拓扑固定顺序挂载
14 个 Service；inject 校验仍由 TrpgContext.mount 装配期把关（缺依赖直接报错，
misconfiguration fails loud）。D20 侧的 YAML loader 留在 D20 仓库，不再进入引擎。

挂载顺序（与 D20 composition.yml 的拓扑排序一致）：
    attributes, equipment, perks, techniques, race, background, feats,
    skills, dice, derived, slots, rest, combat, sheet

幂等：宿主 Context 已有存活的 'trpg' 服务即复用。
"""

from __future__ import annotations

import importlib
from typing import Any, Optional

from alloy.core.context import Context

__all__ = ["preset_trpg", "mount_trpg_services", "MOUNT_ORDER"]

#: 与 D20 composition.yml 一致的拓扑挂载顺序（inject 依赖前置）。
MOUNT_ORDER: tuple[str, ...] = (
    "attributes", "equipment", "perks", "techniques", "race", "background",
    "feats", "skills", "dice", "derived", "slots", "rest", "combat", "sheet",
)

#: 服务 id → 类点分路径（与 D20 composition.yml 的 service 字段一一对应）。
_SERVICE_CLASSES: dict[str, str] = {
    "attributes": "alloy.trpg.attributes.AttributesService",
    "equipment": "alloy.trpg.equipment.EquipmentService",
    "perks": "alloy.trpg.perks.PerksService",
    "techniques": "alloy.trpg.techniques.TechniquesService",
    "race": "alloy.trpg.race.RaceService",
    "background": "alloy.trpg.background.BackgroundService",
    "feats": "alloy.trpg.feats.FeatsService",
    "skills": "alloy.trpg.skills.SkillsService",
    "dice": "alloy.trpg.dice.DiceService",
    "derived": "alloy.trpg.derived.DerivedService",
    "slots": "alloy.trpg.slots.SpellSlotsService",
    "rest": "alloy.trpg.rest.RestService",
    "combat": "alloy.trpg.combat.CombatService",
    "sheet": "alloy.trpg.sheet.SheetService",
}


def _resolve(path: str) -> type:
    module_path, _, cls_name = path.rpartition(".")
    return getattr(importlib.import_module(module_path), cls_name)


def mount_trpg_services(trpg: Any) -> Any:
    """把 14 个 Service 按拓扑顺序挂到 TrpgContext。幂等：已挂则复用。"""
    if trpg.has("attributes") and trpg.has("sheet"):
        return trpg
    for sid in MOUNT_ORDER:
        if not trpg.has(sid):
            trpg.mount(_resolve(_SERVICE_CLASSES[sid]), {}, name=sid)
    return trpg


def preset_trpg(ctx: Context) -> Context:
    """TRPG 规则内核预设：在宿主 alloy Context 上装配 D20 规则内核。

    - 宿主已提供 'bus' 服务则事件骑共享总线，否则提供独立 EventBus；
    - 'trpg' 服务 = TrpgContext 适配器，其 effect 栈挂宿主（注册即回滚，
      宿主 dispose 时自动回收全部服务与事件订阅）；
    - 幂等：已装且存活则复用；适配器已被 dispose 则卸载后重建。

    多角色共享一个宿主：每角色独立装配用 fork（fork 销毁即整体回收）：:

        root = Context()
        root.provide("bus", EventBus())
        fork = root.fork("char1")
        preset_trpg(fork)
        char = Character(ctx=fork)
    """
    from alloy.trpg.context import TrpgContext

    if ctx.has("trpg") and getattr(ctx.get("trpg"), "live", False):
        return ctx
    if ctx.has("trpg"):
        ctx.unload("trpg")
    adapter = TrpgContext(ctx)
    ctx.provide("trpg", adapter)
    mount_trpg_services(adapter)
    return ctx
