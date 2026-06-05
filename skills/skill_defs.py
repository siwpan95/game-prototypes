"""
技能系统 — 技能定义数据（混合架构之数据层）
数据从 data/game_data.xlsx（skills Sheet）加载。
effect 字段在 Excel 里存函数名字符串，运行时通过 _FN_MAP 绑定到实际函数。
"""

import random
from typing import Any, Callable, Dict, Optional

from ecs.components import (
    AttackComponent,
    BuffComponent,
    ExpComponent,
    HPComponent,
    MonsterComponent,
    NameComponent,
    StatusEffectComponent,
)
from ecs.systems import _check_level_up
from ecs.game_data import get_data

# ── 技能效果函数 ──────────────────────────────────────────

def skill_flame_slash(world: Any, caster_eid: int, target_eid: int,
                      log_fn: Callable[[str], None]) -> None:
    """火焰斩：造成 1.5×攻击力的火焰伤害，无视闪避"""
    atk_c = world.get_component(caster_eid, AttackComponent)
    hp_c = world.get_component(target_eid, HPComponent)
    if atk_c is None or hp_c is None or not hp_c.alive:
        return
    base = _get_effective_atk(world, caster_eid, atk_c)
    dmg = int(base * 1.5)
    hp_c.hp -= dmg
    name_c = world.get_component(target_eid, NameComponent)
    name = name_c.name if name_c else "目标"
    log_fn(f"🔥 火焰斩！对 {name} 造成 {dmg} 火焰伤害（无视闪避）")
    if hp_c.hp <= 0:
        _kill_monster(world, caster_eid, target_eid, name, log_fn)


def skill_heal(world: Any, caster_eid: int, target_eid: int,
               log_fn: Callable[[str], None]) -> None:
    """治疗术：恢复自身 30~50 HP"""
    hp_c = world.get_component(caster_eid, HPComponent)
    if hp_c is None:
        return
    heal = random.randint(30, 50)
    hp_c.hp = min(hp_c.max_hp, hp_c.hp + heal)
    log_fn(f"💚 治疗术！恢复 {heal} HP（当前 {hp_c.hp}/{hp_c.max_hp}）")


def skill_lightning_chain(world: Any, caster_eid: int, target_eid: int,
                         log_fn: Callable[[str], None]) -> None:
    """闪电链：对目标造成伤害，并溅射其他存活怪物 50% 伤害"""
    atk_c = world.get_component(caster_eid, AttackComponent)
    hp_c = world.get_component(target_eid, HPComponent)
    if atk_c is None or hp_c is None or not hp_c.alive:
        return
    base = _get_effective_atk(world, caster_eid, atk_c)
    dmg = random.randint(max(1, int(base * 0.7)), int(base * 1.2))
    hp_c.hp -= dmg
    name_c = world.get_component(target_eid, NameComponent)
    name = name_c.name if name_c else "目标"
    log_fn(f"⚡ 闪电链！对 {name} 造成 {dmg} 伤害")

    from ecs.components import MonsterTag
    for e, hp2, _ in world.get_components(HPComponent, MonsterTag):
        if e == target_eid:
            continue
        if not hp2.alive:
            continue
        splash = max(1, int(dmg * 0.5))
        hp2.hp -= splash
        nm_c = world.get_component(e, NameComponent)
        nm_name = nm_c.name if nm_c else "怪物"
        log_fn(f"   ⚡ 溅射 → {nm_name} 受到 {splash} 伤害")
        if hp2.hp <= 0:
            hp2.hp = 0
            hp2.alive = False
            _kill_monster(world, caster_eid, e, nm_name, log_fn)


def skill_ice_shard(world: Any, caster_eid: int, target_eid: int,
                    log_fn: Callable[[str], None]) -> None:
    """冰锥术：伤害 + 减速（目标复活时间+2s）"""
    atk_c = world.get_component(caster_eid, AttackComponent)
    hp_c = world.get_component(target_eid, HPComponent)
    if atk_c is None or hp_c is None or not hp_c.alive:
        return
    base = _get_effective_atk(world, caster_eid, atk_c)
    dmg = random.randint(int(base * 0.9), int(base * 1.3))
    hp_c.hp -= dmg
    from ecs.components import RespawnComponent
    resp_c = world.get_component(target_eid, RespawnComponent)
    if resp_c:
        resp_c.respawn_timer += 2  # 复活时间+2s（减速效果）
    name_c = world.get_component(target_eid, NameComponent)
    name = name_c.name if name_c else "目标"
    log_fn(f"❄ 冰锥术！对 {name} 造成 {dmg} 伤害，复活时间+2s")
    if hp_c.hp <= 0:
        _kill_monster(world, caster_eid, target_eid, name, log_fn)


def skill_poison_strike(world: Any, caster_eid: int, target_eid: int,
                        log_fn: Callable[[str], None]) -> None:
    """剧毒打击：伤害 + 持续掉血 3 回合"""
    atk_c = world.get_component(caster_eid, AttackComponent)
    hp_c = world.get_component(target_eid, HPComponent)
    if atk_c is None or hp_c is None or not hp_c.alive:
        return
    base = _get_effective_atk(world, caster_eid, atk_c)
    dmg = random.randint(int(base * 0.6), int(base * 1.0))
    hp_c.hp -= dmg
    se = world.get_component(target_eid, StatusEffectComponent)
    if se is not None:
        se.add("poison", damage=5, turns=3, label="☠剧毒")
    name_c = world.get_component(target_eid, NameComponent)
    name = name_c.name if name_c else "目标"
    log_fn(f"☠ 剧毒打击！对 {name} 造成 {dmg} 伤害 + 3回合剧毒")
    if hp_c.hp <= 0:
        _kill_monster(world, caster_eid, target_eid, name, log_fn)


def skill_thunder_clap(world: Any, caster_eid: int, target_eid: int,
                       log_fn: Callable[[str], None]) -> None:
    """雷霆震击：对全体怪物造成 30% ATK 伤害"""
    atk_c = world.get_component(caster_eid, AttackComponent)
    if atk_c is None:
        return
    base = _get_effective_atk(world, caster_eid, atk_c)
    splash = max(1, int(base * 0.3))
    from ecs.components import MonsterTag
    log_fn(f"🌩 雷霆震击！对所有怪物造成 {splash} 伤害")
    for e, hp2, _ in world.get_components(HPComponent, MonsterTag):
        if not hp2.alive:
            continue
        hp2.hp -= splash
        nm_c = world.get_component(e, NameComponent)
        nm_name = nm_c.name if nm_c else "怪物"
        log_fn(f"   ⚡ {nm_name} 受到 {splash} 伤害")
        if hp2.hp <= 0:
            hp2.hp = 0
            hp2.alive = False
            _kill_monster(world, caster_eid, e, nm_name, log_fn)


def skill_shadow_step(world: Any, caster_eid: int, target_eid: int,
                      log_fn: Callable[[str], None]) -> None:
    """暗影步：获得 100% 闪避 1 回合"""
    buff = world.get_component(caster_eid, BuffComponent)
    if buff is None:
        from ecs.components import BuffComponent
        buff = BuffComponent()
        world.add_component(caster_eid, buff)
    buff.dodge_bonus = 1.0
    buff.turns_remaining = 2  # 当前回合 + 下回合
    log_fn(f"🌑 暗影步！获得 100% 闪避，持续 1 回合")


def skill_blood_rage(world: Any, caster_eid: int, target_eid: int,
                      log_fn: Callable[[str], None]) -> None:
    """血怒：损失 20% HP，ATK+50% 持续 3 回合"""
    hp_c = world.get_component(caster_eid, HPComponent)
    if hp_c is None:
        return
    cost_hp = max(1, int(hp_c.max_hp * 0.2))
    hp_c.hp = max(1, hp_c.hp - cost_hp)
    buff = world.get_component(caster_eid, BuffComponent)
    if buff is None:
        from ecs.components import BuffComponent
        buff = BuffComponent()
        world.add_component(caster_eid, buff)
    buff.atk_bonus = 0.5
    buff.turns_remaining = 3
    log_fn(f"💢 血怒！损失 {cost_hp} HP，ATK+50% 持续 3 回合")


# ── 效果函数映射表 ──────────────────────────────────────────

_FN_MAP: Dict[str, Callable] = {
    "skill_flame_slash": skill_flame_slash,
    "skill_heal": skill_heal,
    "skill_lightning_chain": skill_lightning_chain,
    "skill_ice_shard": skill_ice_shard,
    "skill_poison_strike": skill_poison_strike,
    "skill_thunder_clap": skill_thunder_clap,
    "skill_shadow_step": skill_shadow_step,
    "skill_blood_rage": skill_blood_rage,
}


def _resolve_skill_fn(fn_name: str) -> Optional[Callable]:
    return _FN_MAP.get(fn_name)


# ── 辅助函数 ──────────────────────────────────────────────

def _get_effective_atk(world: Any, eid: int, atk_c: Any) -> float:
    """计算有效攻击力 = 基础 ATK + 装备加成 + Buff"""
    base = atk_c.atk_base
    from ecs.components import EquipmentComponent
    eq_c = world.get_component(eid, EquipmentComponent)
    if eq_c:
        base += eq_c.total_bonus("atk_base")
    buff = world.get_component(eid, BuffComponent)
    if buff:
        base *= (1.0 + buff.atk_bonus)
    return base


def _get_effective_dodge(world: Any, eid: int) -> float:
    """计算有效闪避率"""
    atk_c = world.get_component(eid, AttackComponent)
    dodge = atk_c.dodge_chance if atk_c else 0.08
    from ecs.components import EquipmentComponent
    eq_c = world.get_component(eid, EquipmentComponent)
    if eq_c:
        dodge += eq_c.total_bonus("dodge_chance")
    buff = world.get_component(eid, BuffComponent)
    if buff:
        dodge = min(1.0, dodge + buff.dodge_bonus)
    return dodge


def _get_effective_crit(world: Any, eid: int) -> float:
    """计算有效暴击率"""
    atk_c = world.get_component(eid, AttackComponent)
    crit = atk_c.crit_chance if atk_c else 0.12
    from ecs.components import EquipmentComponent
    eq_c = world.get_component(eid, EquipmentComponent)
    if eq_c:
        crit += eq_c.total_bonus("crit_chance")
    return crit


def _get_cd_reduction(world: Any, eid: int) -> int:
    """计算冷却缩短"""
    from ecs.components import EquipmentComponent
    eq_c = world.get_component(eid, EquipmentComponent)
    if eq_c:
        return int(eq_c.total_bonus("cd_reduction"))
    return 0


def _kill_monster(world: Any, caster_eid: int, target_eid: int,
                   name: str, log_fn: Callable[[str], None]) -> None:
    """通用怪物击杀结算"""
    hp_c = world.get_component(target_eid, HPComponent)
    if hp_c:
        hp_c.hp = 0
        hp_c.alive = False
    exp_c = world.get_component(caster_eid, ExpComponent)
    mon_c = world.get_component(target_eid, MonsterComponent)
    if exp_c and mon_c:
        bonus = exp_c.exp + mon_c.exp_reward
        from ecs.components import EquipmentComponent
        eq_c = world.get_component(caster_eid, EquipmentComponent)
        if eq_c:
            bonus = int(bonus * (1.0 + eq_c.total_bonus("exp_bonus")))
        exp_c.exp += bonus
        log_fn(f"🎉 {name} 被击杀！获得 {bonus} 经验")
        _check_level_up(world, caster_eid, log_fn)


# ── 技能数据加载 ──────────────────────────────────────────────

_SKILL_DEFS: Optional[Dict[str, Dict[str, Any]]] = None


def _load_skills() -> Dict[str, Dict[str, Any]]:
    try:
        data = get_data()
        raw = data.get("skills", {})
        result = {}
        for sid, sdef in raw.items():
            sdef = dict(sdef)
            fn_name = sdef.pop("effect_fn", "") or ""
            sdef["effect"] = _resolve_skill_fn(fn_name)
            result[sid] = sdef
        return result
    except Exception:
        # 内置默认（与 Excel 模板一致）
        return {
            "flame_slash": dict(id="flame_slash", name="火焰斩",
                                 desc="造成 1.5×ATK 火焰伤害，无视闪避",
                                 cooldown=3, cost_exp_pool=8,
                                 effect=skill_flame_slash),
            "heal": dict(id="heal", name="治疗术",
                         desc="恢复自身 30~50 HP",
                         cooldown=5, cost_exp_pool=5,
                         effect=skill_heal),
            "lightning_chain": dict(id="lightning_chain", name="闪电链",
                                   desc="造成伤害并溅射其他存活怪物 50% 伤害",
                                   cooldown=6, cost_exp_pool=12,
                                   effect=skill_lightning_chain),
            "ice_shard": dict(id="ice_shard", name="冰锥术",
                              desc="伤害 + 目标复活时间+2s",
                              cooldown=4, cost_exp_pool=7,
                              effect=skill_ice_shard),
            "poison_strike": dict(id="poison_strike", name="剧毒打击",
                                  desc="伤害 + 持续掉血 3 回合",
                                  cooldown=5, cost_exp_pool=10,
                                  effect=skill_poison_strike),
            "thunder_clap": dict(id="thunder_clap", name="雷霆震击",
                                 desc="对全体怪物造成 30% ATK 伤害",
                                 cooldown=8, cost_exp_pool=15,
                                 effect=skill_thunder_clap),
            "shadow_step": dict(id="shadow_step", name="暗影步",
                               desc="获得 100% 闪避 1 回合",
                               cooldown=6, cost_exp_pool=6,
                               effect=skill_shadow_step),
            "blood_rage": dict(id="blood_rage", name="血怒",
                               desc="损失 20% HP，ATK+50% 3 回合",
                               cooldown=10, cost_exp_pool=0,
                               effect=skill_blood_rage),
        }


def get_skill_defs() -> Dict[str, Dict[str, Any]]:
    global _SKILL_DEFS
    if _SKILL_DEFS is None:
        _SKILL_DEFS = _load_skills()
    return _SKILL_DEFS


# 兼容旧代码：公开 SKILL_DEFS
SKILL_DEFS = get_skill_defs()
