# -*- coding: utf-8 -*-
"""
MC1 探针测试 — 基于 allin_engine.test.Probe / ProbeManager

通过探针验证：
  1. 引擎全部子系统在线（ECS / EventBus / 背包 / 合成 / 战斗 / 存档 / 特效 / 音频 / 行为树 / 状态机）
  2. 采集 → 合成 → 装备 的基础生存闭环
  3. 探索 + 引擎行为树（生物刷新决策）可正常驱动
  4. 引擎简单战斗（SimpleCombat + MobLibrary）可击败普通怪物并掉落
  5. 特效 / 音频 事件总线接线正常
  6. 完整通关流程：集齐末地材料 → 激活末地传送门 → 击败末影龙 → 状态机进入 VICTORY

运行方式：
    python tests/integration/test_mc1_probes.py
退出码：全部探针通过返回 0，否则返回 1。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让 allin_engine 与 MC1 的裸导入（from game_data import ...）可解析
_ROOT = Path(__file__).resolve().parents[2]          # D:/allin/MCclone
_MC1 = _ROOT / "MC1"
for _p in (str(_ROOT), str(_MC1)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from allin_engine.test import Probe, ProbeManager          # noqa: E402
from minecraft_adventure import (                           # noqa: E402
    GamePhase,
    MinecraftAdventure,
    engine_subsystems_snapshot,
)
from game_data import BIOMES, MOBS                          # noqa: E402


def _resolve_combat(g: MinecraftAdventure, mode: str = "攻击", max_turns: int = 300) -> bool:
    """循环战斗直到结束；返回玩家是否获胜。"""
    turns = 0
    while g.combat_state is not None and not g.combat_state.is_over and turns < max_turns:
        g._cmd_combat(mode)
        turns += 1
    return g.combat_state is not None and g.combat_state.player_won


# ============================================================
#  探针 1：引擎全部子系统在线
# ============================================================
def probe_engine_online() -> tuple[bool, str]:
    g = MinecraftAdventure()
    snap = engine_subsystems_snapshot(g)
    required = [
        "ecs_world", "event_bus", "stackable_inventory", "crafting_recipes",
        "mob_library", "particle_system", "audio_system_available",
        "spawn_behavior_tree", "game_flow_fsm", "save_manager",
    ]
    missing = [k for k in required if not snap.get(k)]
    if missing:
        return False, f"缺失子系统: {missing}"
    detail = (f"ECS/事件总线/背包(注册{snap['item_registry_count']}物品)/"
              f"合成({snap['crafting_recipes']}配方)/生物({snap['mob_library']}种)/"
              f"特效/音频/行为树/状态机/存档 全部在线")
    return True, detail


# ============================================================
#  探针 2：采集 → 合成 → 装备 闭环
# ============================================================
def probe_gather_craft_equip() -> tuple[bool, str]:
    g = MinecraftAdventure()
    # 先真实采集若干次（驱动采集子系统），再确保有原木以消随机性
    # （采集产出随机，平原未必每次都出原木；与 fx_audio 探针一致做兜底）。
    for _ in range(4):
        g.execute("采集")
    if g.inv.count_item("wood_log") == 0:
        g.inv.add_item("wood_log", 3)   # 兜底：保证合成闭环可被验证
    before = g.inv.count_item("wood_log")
    # 合成木板（配方：原木 → 木板）
    out = g.execute("合成 木板")
    crafted = "合成成功" in out or "✅" in out
    planks = g.inv.count_item("wood_planks")
    # 装备一把木剑（先放入背包再装备，走引擎 EquipmentSlots）
    g.inv.add_item("wooden_sword", 1)
    equip_out = g.execute("装备 wooden_sword")
    equipped = g.player.weapon == "wooden_sword"
    ok = before > 0 and crafted and planks > 0 and equipped
    detail = (f"采集原木×{before}→合成木板×{planks}{'成功' if crafted else '失败'}"
              f"；装备木剑{'成功' if equipped else '失败'}（{equip_out[:12]}）")
    return ok, detail


# ============================================================
#  探针 3：探索 + 引擎行为树（生物刷新决策）
# ============================================================
def probe_explore_spawn_tree() -> tuple[bool, str]:
    g = MinecraftAdventure()
    # 直接驱动行为树：构造「必定刷新」的黑板
    bb = g.spawn_bt.blackboard
    bb.update({
        "is_hostile_time": True,
        "is_dayish": False,
        "sheltered": False,
        "spawn_rate": 1.0,
        "hostile_candidates": ["zombie", "skeleton", "creeper", "spider", "slime"],
        "passive_candidates": ["pig", "cow", "sheep"],
        "rng": 0.0,
        "rng_passive": 0.0,
    })
    g.spawn_bt.reset()
    g.spawn_bt.tick()
    spawn = bb.get("spawn")
    valid = spawn in ("zombie", "skeleton", "creeper", "spider", "slime")
    # 顺便验证真实移动命令不崩溃
    g.player.hp = g.player.max_hp = 1000  # 防探索中战斗致死
    move_out = g.execute("北")
    moved = "前进" in move_out or "边界" in move_out
    ok = valid and moved
    detail = f"行为树决策刷新={spawn}（合法敌对生物）；移动命令正常（{move_out[:10]}…）"
    return ok, detail


# ============================================================
#  探针 4：引擎战斗击败普通怪物并掉落
# ============================================================
def probe_combat_win() -> tuple[bool, str]:
    g = MinecraftAdventure()
    g.inv.add_item("iron_sword", 1)
    g.execute("装备 iron_sword")
    g.player.hp = g.player.max_hp = 500
    g._enter_combat("zombie")
    in_combat = g.phase == GamePhase.COMBAT
    won = _resolve_combat(g, "攻击")
    killed = g.player.mobs_killed >= 1
    ok = in_combat and won and killed
    detail = (f"进入战斗={'是' if in_combat else '否'}；击败僵尸="
              f"{'是' if won else '否'}；累计击杀={g.player.mobs_killed}；"
              f"当前阶段={g.phase.value}")
    return ok, detail


# ============================================================
#  探针 5：事件总线 → 特效 / 音频 接线
# ============================================================
def probe_fx_audio() -> tuple[bool, str]:
    g = MinecraftAdventure()
    # 直接提供材料以保证合成必定触发（避免采集随机性导致探针抖动）
    g.inv.add_item("wood_log", 5)
    g.execute("合成 木板")          # 触发 item_crafted → 星光特效 + 音效
    audio_ok = g.audio_plays > 0
    fx_ok = len(g.fx_systems) >= 1  # 预设星光粒子系统已挂载

    # 维度切换特效（末地传送门 → 魔法阵）
    g.inv.add_item("obsidian", 10)
    g.inv.add_item("flint_and_steel", 1)
    g.execute("下界")               # 触发 dimension_changed → 魔法阵特效
    dim_fx_ok = len(g.fx_systems) >= 2

    # 推进粒子系统（验证 ParticleSystem 能正常 update，无 AttributeError）
    try:
        n = g.update_fx(0.016)
        tick_ok = isinstance(n, int)
    except Exception as e:  # noqa: BLE001
        return False, f"update_fx 抛错: {type(e).__name__}: {e}"
    ok = audio_ok and fx_ok and dim_fx_ok and tick_ok
    detail = (f"音效播放次数={g.audio_plays}；特效子系统数={len(g.fx_systems)}；"
              f"update_fx 存活粒子={n}")
    return ok, detail


# ============================================================
#  探针 6：完整通关 —— 末地传送门 + 末影龙 + VICTORY
# ============================================================
def probe_full_victory() -> tuple[bool, str]:
    g = MinecraftAdventure()
    # 基础生存：采集 + 合成 + 装备
    for _ in range(6):
        g.execute("采集")
    g.execute("合成 木板")
    g.inv.add_item("diamond_sword", 1)
    g.execute("装备 diamond_sword")

    # 集齐末地材料
    g.inv.add_item("ender_eye", 12)
    g.inv.add_item("ender_pearl", 4)
    portal_out = g.execute("末地")          # 维度切换 → 魔法阵特效
    dim_ok = "末地" in portal_out and g.player.dimension.value == "末地"

    # 强化以应对 Boss：拉满生命保证不被秒；装备铁甲展示引擎护甲减免系统
    g.player.max_hp = 100000
    g.player.hp = 100000
    for _a in ("iron_helmet", "iron_chestplate", "iron_leggings", "iron_boots"):
        g.inv.add_item(_a, 1)
        g.execute(f"装备 {_a}")
    armor = g.player.armor
    g._enter_combat("ender_dragon")
    won = _resolve_combat(g, "攻击")
    victory = g.phase == GamePhase.VICTORY and g.player.defeated_ender_dragon
    ok = dim_ok and won and victory
    detail = (f"末地传送门激活={'是' if dim_ok else '否'}；"
              f"护甲={armor}；"
              f"击败末影龙={'是' if won else '否'}；"
              f"游戏阶段={g.phase.value}；通关标记={g.player.defeated_ender_dragon}")
    return ok, detail


# ============================================================
#  探针 7：生物群系生物全部已登记（防刷怪 KeyError 回归）
# ============================================================
def probe_biome_mobs_registered() -> tuple[bool, str]:
    """所有生物群系列出的被动/中立生物都必须在 MOBS 中登记。

    回归守卫：先前 mountains 等群系列出 goat/fox/turtle/dolphin/bat 却未登记于
    MOBS，移动命令每次 _roll_spawn 都会 KeyError 崩溃。此探针锁定「群系生物全部
    已登记」，防止该崩溃回归。
    """
    missing = []
    for bid, b in BIOMES.items():
        for m in b.get("passive_mobs", []):
            if m not in MOBS:
                missing.append(f"{bid}:{m}")
    ok = not missing
    detail = "群系生物全部登记于 MOBS" if ok else f"未登记: {missing}"
    return ok, detail


# ============================================================
#  探针 8：补全的被动生物（山羊）可被猎杀
# ============================================================
def probe_passive_mob_hunt() -> tuple[bool, str]:
    """补全的被动生物（山羊）应已注册进 MobLibrary 且可被猎杀（验证 MOBS 补全生效）。"""
    g = MinecraftAdventure()
    # 模拟一只山羊出现（mountains 等群系会刷出 goat）
    g._pending_mob = "goat"
    g.player.hp = g.player.max_hp = 200
    g.handle_pending_mob("猎杀")          # 进入战斗（经 MobLibrary 取 goat 模板）
    entered = g.phase == GamePhase.COMBAT
    won = _resolve_combat(g, "攻击")
    killed = g.player.mobs_killed >= 1
    ok = entered and won and killed
    detail = (f"山羊进入战斗={'是' if entered else '否'}；猎杀胜利="
              f"{'是' if won else '否'}；累计击杀={g.player.mobs_killed}")
    return ok, detail


# ============================================================
#  注册并运行
# ============================================================
def build_manager() -> ProbeManager:
    mgr = ProbeManager()
    mgr.register(Probe("engine_subsystems_online", probe_engine_online,
                       category="引擎集成", priority=1, tags={"engine"}))
    mgr.register(Probe("gather_craft_equip", probe_gather_craft_equip,
                       category="生存闭环", priority=1, tags={"survival"}))
    mgr.register(Probe("explore_spawn_tree", probe_explore_spawn_tree,
                       category="探索AI", priority=2, tags={"ai"}))
    mgr.register(Probe("combat_win", probe_combat_win,
                       category="战斗", priority=1, tags={"combat"}))
    mgr.register(Probe("fx_audio_wiring", probe_fx_audio,
                       category="特效音频", priority=2, tags={"fx", "audio"}))
    mgr.register(Probe("full_victory_flow", probe_full_victory,
                       category="通关流程", priority=1, tags={"victory"}))
    mgr.register(Probe("biome_mobs_registered", probe_biome_mobs_registered,
                       category="数据完整", priority=1, tags={"data", "mobs"}))
    mgr.register(Probe("passive_mob_hunt", probe_passive_mob_hunt,
                       category="生物玩法", priority=1, tags={"mobs", "hunt"}))
    return mgr


def main() -> int:
    print("=" * 60)
    print("MC1 探针测试（allin_engine 集成验证）")
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
