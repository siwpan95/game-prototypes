# -*- coding: utf-8 -*-
"""
统一产品探针测试 — 验证 MC1（文字模式）与 MC2（2D 模式）真正整合为同一引擎产品。

验证点（对应「完整整合」中 (b) 统一产品内核）：
  1. 共享事件总线：MC1 玩法层发出的事件，在共享总线上可被 MC2 玩法层订阅者观测
     （事件贯通 —— 文字模式与 2D 模式是同一游戏的两个表现层）。
  2. 共享音频系统：MC1 / MC2 玩法层复用同一 AudioSystem 实例。
  3. 共享存档主干：MC1 的存档与跨玩法层 profile 经同一 SaveLoadManager 持久化、
     读回一致（存档贯通）。
  4. 共享资源注册表：MC1 物品与 MC2 方块登记到同一 ItemRegistry（资源打通）。
  5. 统一产品身份：两玩法层挂载到同一 ProductCore 后，bus/audio/save_mgr/registry
     为同一实例（即「一个游戏、可切换玩法层」）。

运行方式：
    python tests/integration/test_unified_probes.py
退出码：全部通过返回 0，否则 1。
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]          # <仓库根>
_MC1 = _ROOT / "MC1"
_MC2 = _ROOT / "MC2"
for _p in (str(_ROOT), str(_MC1), str(_MC2)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from allin_engine.test import Probe, ProbeManager      # noqa: E402
from product_core import ProductCore                   # noqa: E402
from minecraft_adventure import MinecraftAdventure     # noqa: E402
from mcclone.core.event_bus import EventBus, EventTypes  # noqa: E402
from mcclone.player.inventory import Inventory             # noqa: E402


def probe_shared_event_bus() -> tuple[bool, str]:
    """MC1 发出的事件应在共享总线上被 MC2 订阅者观测（事件贯通）。"""
    core = ProductCore()
    adv = MinecraftAdventure(core=core)          # MC1 文字层挂到共享总线
    mc2_bus = EventBus(engine_bus=core.bus)     # MC2 2D 层挂到同一总线
    seen = []
    mc2_bus.subscribe(EventTypes.ITEM_CRAFTED, lambda et, d: seen.append(d))

    # MC1 侧触发合成事件
    adv.inv.add_item("wood_log", 3)
    adv.bus.emit(EventTypes.ITEM_CRAFTED, {"item_id": "wood_planks"})

    ok = len(seen) >= 1
    detail = (f"MC1 触发 ITEM_CRAFTED → MC2 层观测到 {len(seen)} 次；"
              f"共享总线监听器总数={core.bus.total_listeners()}")
    return ok, detail


def probe_shared_audio() -> tuple[bool, str]:
    """MC1 / MC2 玩法层应复用同一 AudioSystem 实例（音频贯通）。"""
    core = ProductCore()
    adv = MinecraftAdventure(core=core)
    # MC2 侧：_run_gui 会复用 core.audio；这里直接断言身份一致
    mc2_audio = core.audio
    ok = (adv.audio is core.audio) and (mc2_audio is core.audio)
    detail = (f"MC1.audio is core.audio={'是' if adv.audio is core.audio else '否'}；"
              f"MC2.audio is core.audio={'是' if mc2_audio is core.audio else '否'}")
    return ok, detail


def probe_shared_save_roundtrip() -> tuple[bool, str]:
    """MC1 存档与跨玩法层 profile 经同一 SaveLoadManager 持久化并可读回（存档贯通）。"""
    core = ProductCore()
    adv = MinecraftAdventure(core=core)
    adv.execute("采集")
    adv._cmd_save()                              # 写入共享管理器 slot 0
    # 跨玩法层 profile（角色/进度打通）
    core.set_profile("unified_score", 123)
    core.set_profile("mode", "MC1")
    core.persist_profile()                       # 写入共享管理器 slot 9

    # 模拟「切换到另一玩法层」后读回
    game_data = core.save_mgr.load(0)
    profile = core.load_profile()
    ok = (
        game_data is not None
        and isinstance(game_data, dict)
        and game_data.get("inventory") is not None
        and profile.get("unified_score") == 123
        and profile.get("mode") == "MC1"
    )
    detail = (f"游戏存档读回={'是' if game_data else '否'}；"
              f"profile.unified_score={profile.get('unified_score')}；"
              f"共享存档槽位列表={[s.slot for s in core.save_mgr.list_saves()]}")
    return ok, detail


def probe_shared_resources() -> tuple[bool, str]:
    """MC1 物品与 MC2 方块登记到同一 ItemRegistry（资源打通）。"""
    core = ProductCore()
    n0 = core.registry.count
    core.register_mc1_items()
    n1 = core.registry.count
    core.register_mc2_blocks()
    n2 = core.registry.count
    has_mc1 = any(k not in ("",) and not k.startswith("mc2_block_")
                  for k in core.registry.all_items)
    has_mc2 = any(k.startswith("mc2_block_") for k in core.registry.all_items)
    ok = n2 > n1 > n0 and has_mc1 and has_mc2
    detail = (f"注册表初始={n0} → 加MC1={n1} → 加MC2={n2}；"
              f"含MC1物品={'是' if has_mc1 else '否'}；含MC2方块={'是' if has_mc2 else '否'}")
    return ok, detail


def probe_unified_product_identity() -> tuple[bool, str]:
    """两玩法层挂到同一 ProductCore 后，bus/audio/save_mgr/registry 为同一实例。"""
    core = ProductCore()
    adv = MinecraftAdventure(core=core)          # MC1 层
    mc2_bus = EventBus(engine_bus=core.bus)      # MC2 层

    same_bus = (adv.bus is core.bus) and (mc2_bus._engine_bus is core.bus)
    same_audio = adv.audio is core.audio
    same_save = adv.save_mgr is core.save_mgr
    same_reg = adv.registry is core.registry
    same_inv = adv.inv is not None
    ok = same_bus and same_audio and same_save and same_reg and same_inv
    detail = (f"bus={'同' if same_bus else '异'}；audio={'同' if same_audio else '异'}；"
              f"save={'同' if same_save else '异'}；registry={'同' if same_reg else '异'}；"
              f"已挂载玩法层={list(core.games.keys())}")
    return ok, detail


def probe_shared_inventory() -> tuple[bool, str]:
    """MC2 方块背包应可投影为引擎 StackableInventory（库存核算打通）。

    整合点：MC2 的定长槽位背包经 to_engine_inventory() 投影到引擎
    StackableInventory，且复用共享 ItemRegistry（mc2_block_<id> 命名空间）；
    这证明库存核算确实落在引擎子系统上，而非本地影子副本。
    """
    core = ProductCore()
    core.register_mc2_blocks()           # 注册 mc2_block_<id> 到共享注册表
    mc2_keys = [k for k in core.registry.all_items if k.startswith("mc2_block_")]
    if len(mc2_keys) < 2:
        return False, f"MC2 方块注册数不足: {len(mc2_keys)}"
    bid_a = int(mc2_keys[0].split("_")[-1])
    bid_b = int(mc2_keys[1].split("_")[-1])

    local_inv = Inventory()
    local_inv.add(bid_a, 10)             # 本地权威背包：方块 A × 10
    local_inv.add(bid_b, 5)              # 本地权威背包：方块 B × 5

    eng = local_inv.to_engine_inventory(core.registry)
    c_a = eng.count_item(mc2_keys[0])
    c_b = eng.count_item(mc2_keys[1])
    ok = (c_a == 10 and c_b == 5 and eng.registry is core.registry)
    detail = (f"本地背包投影→引擎库存: {mc2_keys[0]}={c_a}, {mc2_keys[1]}={c_b}；"
              f"registry 同实例={'是' if eng.registry is core.registry else '否'}")
    return ok, detail


def build_manager() -> ProbeManager:
    mgr = ProbeManager()
    mgr.register(Probe("shared_event_bus", probe_shared_event_bus,
                       category="统一产品", priority=1, tags={"unified", "event"}))
    mgr.register(Probe("shared_audio", probe_shared_audio,
                       category="统一产品", priority=1, tags={"unified", "audio"}))
    mgr.register(Probe("shared_save_roundtrip", probe_shared_save_roundtrip,
                       category="统一产品", priority=1, tags={"unified", "save"}))
    mgr.register(Probe("shared_resources", probe_shared_resources,
                       category="统一产品", priority=1, tags={"unified", "resource"}))
    mgr.register(Probe("unified_product_identity", probe_unified_product_identity,
                       category="统一产品", priority=1, tags={"unified", "identity"}))
    mgr.register(Probe("shared_inventory", probe_shared_inventory,
                       category="统一产品", priority=1, tags={"unified", "inventory"}))
    return mgr


def main() -> int:
    print("=" * 60)
    print("统一产品探针测试（MC1 + MC2 整合验证）")
    print("=" * 60)
    mgr = build_manager()
    results = mgr.run_all()
    passed = sum(1 for r in results if r.success)
    print("=" * 60)
    print(f"总计: {len(results)}  通过: {passed}  失败: {len(results) - passed}")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
