"""
ECS Systems — 纯逻辑，操作 Component 数据
所有 system 函数签名：def xxx_system(world: World, dt: float) -> None
"""

import random
from typing import Any, Callable, Dict, List, Optional, Tuple

from .components import (
    AttackComponent,
    BuffComponent,
    EquipmentComponent,
    ExpComponent,
    HPComponent,
    MonsterComponent,
    MonsterTag,
    NameComponent,
    PlayerTag,
    RespawnComponent,
    StatusEffectComponent,
)
from .equipment import roll_equipment_drop
from .monster_affixes import AFFIX_DEFS
from .world import World


# ── 辅助：有效属性计算 ─────────────────────────────────

def _effective_atk(world: World, eid: int) -> float:
    atk_c = world.get_component(eid, AttackComponent)
    if atk_c is None:
        return 10
    base = atk_c.atk_base
    eq_c = world.get_component(eid, EquipmentComponent)
    if eq_c:
        base += eq_c.total_bonus("atk_base")
    buff = world.get_component(eid, BuffComponent)
    if buff and buff.turns_remaining > 0:
        base *= (1.0 + buff.atk_bonus)
    return base


def _effective_dodge(world: World, eid: int) -> float:
    atk_c = world.get_component(eid, AttackComponent)
    dodge = atk_c.dodge_chance if atk_c else 0.08
    eq_c = world.get_component(eid, EquipmentComponent)
    if eq_c:
        dodge += eq_c.total_bonus("dodge_chance")
    buff = world.get_component(eid, BuffComponent)
    if buff:
        dodge = min(1.0, dodge + buff.dodge_bonus)
    return dodge


def _effective_crit(world: World, eid: int) -> float:
    atk_c = world.get_component(eid, AttackComponent)
    crit = atk_c.crit_chance if atk_c else 0.12
    eq_c = world.get_component(eid, EquipmentComponent)
    if eq_c:
        crit += eq_c.total_bonus("crit_chance")
    return crit


def calc_attack_power(level: int) -> int:
    """攻击力 = level² + 2×level + 10"""
    return level * level + 2 * level + 10


# ── 战斗系统：玩家攻击怪物（整合词缀/装备/Buff）───────────────

def combat_system(world: World, dt: float, attacker_eid: int,
                  target_eid: int,
                  log_fn: Callable[[str], None],
                  on_kill: Optional[Callable[[int, str], None]] = None) -> None:
    """
    对 target_eid 执行一次攻击。
    - on_kill(eid, monster_name) 击杀回调（用于装备掉落/事件）
    """
    target_hp = world.get_component(target_eid, HPComponent)
    if target_hp is None or not target_hp.alive:
        if log_fn and target_hp is not None and not target_hp.alive:
            name_c = world.get_component(target_eid, NameComponent)
            name = name_c.name if name_c else "怪物"
            log_fn(f"{name} 已经死了")
        return

    # 幻影词缀：30% 免疫
    mon_c = world.get_component(target_eid, MonsterComponent)
    if mon_c and mon_c.affix == "phantom":
        if random.random() < 0.30:
            name_c = world.get_component(target_eid, NameComponent)
            name = name_c.name if name_c else "怪物"
            log_fn(f"👻 {name} 发动幻影，免疫本次攻击！")
            return

    # 伤害计算（含装备 ATK 加成）
    raw_atk = _effective_atk(world, attacker_eid)
    crit_chance = _effective_crit(world, attacker_eid)
    dmg = random.randint(max(1, int(raw_atk) - 3), int(raw_atk) + 3)

    # 暴击
    is_crit = random.random() < crit_chance
    if is_crit:
        dmg = dmg * 2
        name_c = world.get_component(target_eid, NameComponent)
        name = name_c.name if name_c else "目标"
        log_fn(f"⚡暴击! 对 {name} 造成 {dmg} 伤害 (ATK:{int(raw_atk)})")
    else:
        name_c = world.get_component(target_eid, NameComponent)
        name = name_c.name if name_c else "目标"
        log_fn(f"⚔ 对 {name} 造成 {dmg} 伤害 (ATK:{int(raw_atk)})")

    # 硬化词缀：减伤
    if mon_c and mon_c.affix == "hardened":
        af = AFFIX_DEFS.get("hardened", {})
        dr = af.get("damage_reduction", 0)
        if dr > 0:
            dmg = max(1, dmg - dr)

    target_hp.hp -= dmg

    # 吸血装备
    attacker_hp = world.get_component(attacker_eid, HPComponent)
    eq_c = world.get_component(attacker_eid, EquipmentComponent)
    if attacker_hp and eq_c:
        lifesteal = eq_c.total_bonus("lifesteal")
        if lifesteal > 0:
            heal = int(dmg * lifesteal)
            attacker_hp.hp = min(attacker_hp.max_hp, attacker_hp.hp + heal)

    # 检查目标是否死亡
    if target_hp.hp <= 0:
        _on_monster_death(world, attacker_eid, target_eid, log_fn, on_kill)
    else:
        # 怪物反击（含词缀效果）
        _monster_counter(world, attacker_eid, target_eid, log_fn)


def _on_monster_death(world: World, attacker_eid: int, target_eid: int,
                      log_fn: Callable[[str], None],
                      on_kill: Optional[Callable[[int, str], None]] = None) -> None:
    """怪物死亡结算"""
    target_hp = world.get_component(target_eid, HPComponent)
    mon_c = world.get_component(target_eid, MonsterComponent)
    if target_hp is None:
        return
    target_hp.hp = 0
    target_hp.alive = False

    # 复活倒计时
    resp = world.get_component(target_eid, RespawnComponent)
    if resp:
        resp.respawn_timer = resp.respawn_time

    name_c = world.get_component(target_eid, NameComponent)
    name = name_c.name if name_c else "怪物"

    # 经验结算
    if mon_c:
        reward = mon_c.exp_reward
        player_exp = world.get_component(attacker_eid, ExpComponent)
        if player_exp:
            # 装备 EXP 加成
            eq_c = world.get_component(attacker_eid, EquipmentComponent)
            bonus_mult = eq_c.total_bonus("exp_bonus") if eq_c else 0.0
            reward = int(reward * (1.0 + bonus_mult))
            player_exp.exp += reward
            rt = resp.respawn_time if resp else "?"
            log_fn(f"🎉 {name} 死亡，获得 {reward} 经验，{rt}秒后复活")
            _check_level_up(world, attacker_eid, log_fn)

    # 击杀回调（装备掉落 / 事件）
    if on_kill:
        on_kill(target_eid, mon_c.name if mon_c else name)


def _monster_counter(world: World, player_eid: int, monster_eid: int,
                     log_fn: Callable[[str], None]) -> None:
    """怪物反击玩家（闪避判定 + 伤害 + 词缀效果）"""
    player_hp = world.get_component(player_eid, HPComponent)
    if player_hp is None:
        return

    # 玩家闪避（含装备/暗影步加成）
    dodge = _effective_dodge(world, player_eid)
    if random.random() < dodge:
        mon_name_c = world.get_component(monster_eid, NameComponent)
        mon_name = mon_name_c.name if mon_name_c else "怪物"
        log_fn(f"🌀 你闪避了 {mon_name} 的攻击！")
        # 消耗暗影步等闪避 Buff
        _tick_buffs(world, player_eid, log_fn)
        return

    dmg = random.randint(6, 12)
    player_hp.hp -= dmg
    mon_name_c = world.get_component(monster_eid, NameComponent)
    mon_name = mon_name_c.name if mon_name_c else "怪物"
    log_fn(f"💀 {mon_name} 攻击你，造成 {dmg} 伤害")

    # 燃烧词缀：反击附加灼烧
    mon_c = world.get_component(monster_eid, MonsterComponent)
    if mon_c and mon_c.affix == "burning":
        se = world.get_component(player_eid, StatusEffectComponent)
        if se:
            se.add("burn", damage=4, turns=3, label="🔥灼烧")
            log_fn("🔥 燃烧怪物反击附带灼烧！")

    if player_hp.hp <= 0:
        log_fn("☠ 你已死亡，游戏结束")

    # 消费 Buff 回合
    _tick_buffs(world, player_eid, log_fn)


def _check_level_up(world: World, player_eid: int,
                    log_fn: Callable[[str], None]) -> None:
    """升级时溢出经验流入经验池"""
    exp_c = world.get_component(player_eid, ExpComponent)
    hp_c = world.get_component(player_eid, HPComponent)
    if exp_c is None:
        return
    while exp_c.exp >= exp_c.threshold():
        overflow = exp_c.exp - exp_c.threshold()
        exp_c.level += 1
        exp_c.exp = 0
        exp_c.exp_pool += overflow
        if hp_c:
            hp_c.max_hp += 20
            hp_c.hp = hp_c.max_hp
        log_fn(f"🌟 恭喜升到 Lv.{exp_c.level}")
        if overflow > 0:
            log_fn(f"💧 {overflow} 溢出经验流入经验池（池内 {exp_c.exp_pool}）")


def _tick_buffs(world: World, eid: int,
                log_fn: Optional[Callable[[str], None]] = None) -> None:
    """递减 Buff 回合数"""
    buff = world.get_component(eid, BuffComponent)
    if buff and buff.turns_remaining > 0:
        if buff.tick():
            if log_fn:
                log_fn("🔔 增益效果已过期")


# ── 复活系统 ──────────────────────────────────────────────

def respawn_system(world: World, dt: float,
                   log_fn: Optional[Callable[[str], None]] = None) -> None:
    """每 tick（1秒）调用一次。递减 respawn_timer，到 0 则复活怪物。"""
    for eid, resp, hp_comp, _ in world.get_components(
        RespawnComponent, HPComponent, NameComponent
    ):
        if hp_comp.alive:
            continue
        resp.respawn_timer -= 1
        if resp.respawn_timer <= 0:
            hp_comp.hp = hp_comp.max_hp
            hp_comp.alive = True
            resp.respawn_timer = 0
            name_c = world.get_component(eid, NameComponent)
            if log_fn and name_c:
                log_fn(f"🔄 {name_c.name} 重新出现了！")


# ── 状态效果系统（毒/灼烧等持续伤害）────────────────────────

def status_effect_system(world: World, dt: float,
                         player_eid: int,
                         log_fn: Optional[Callable[[str], None]] = None) -> None:
    """每 tick 处理中毒/灼烧等持续效果"""
    player_hp = world.get_component(player_eid, HPComponent)
    if player_hp is None:
        return

    # 处理怪物身上的状态效果
    for eid, se, hp_c, _ in world.get_components(
        StatusEffectComponent, HPComponent, NameComponent
    ):
        if not hp_c.alive:
            continue
        for ef in se.effects:
            if ef["type"] in ("poison", "burn"):
                hp_c.hp -= ef["damage"]
                name_c = world.get_component(eid, NameComponent)
                nm = name_c.name if name_c else "怪物"
                if log_fn:
                    log_fn(f"{ef['label']} {nm} 受到 {ef['damage']} 持续伤害（HP:{hp_c.hp}）")
        expired = se.tick()
        # 检查怪物是否因持续伤害死亡
        if hp_c.hp <= 0:
            hp_c.hp = 0
            hp_c.alive = False
            resp = world.get_component(eid, RespawnComponent)
            if resp:
                resp.respawn_timer = resp.respawn_time
            if log_fn:
                name_c = world.get_component(eid, NameComponent)
                log_fn(f"🎉 {name_c.name if name_c else '怪物'} 被持续伤害击杀！")


# ── 休息系统 ──────────────────────────────────────────────

def rest_system(world: World, player_eid: int,
                log_fn: Callable[[str], None]) -> bool:
    """玩家休息：消耗 exp_pool 恢复 HP。返回 True 表示成功休息。"""
    hp_c = world.get_component(player_eid, HPComponent)
    exp_c = world.get_component(player_eid, ExpComponent)
    if hp_c is None or exp_c is None:
        return False

    rest_cost = exp_c.rest_cost
    if hp_c.hp >= hp_c.max_hp:
        log_fn("💤 HP 已满，无需休息")
        return False
    if exp_c.exp_pool < rest_cost:
        log_fn(f"💤 经验池不足，休息需要 {rest_cost}（池内 {exp_c.exp_pool}）")
        return False

    exp_c.exp_pool -= rest_cost
    heal = random.randint(18, 35)
    hp_c.hp = min(hp_c.max_hp, hp_c.hp + heal)
    log_fn(f"💤 休息恢复 {heal} HP，消耗经验池 {rest_cost}（池内剩余 {exp_c.exp_pool}）")
    return True


# ── 玩家死亡重置 ──────────────────────────────────────────

def reset_player(world: World, player_eid: int) -> None:
    """玩家死亡后重置到 Lv.1 / HP100 / EXP0"""
    hp_c = world.get_component(player_eid, HPComponent)
    exp_c = world.get_component(player_eid, ExpComponent)
    atk_c = world.get_component(player_eid, AttackComponent)
    eq_c = world.get_component(player_eid, EquipmentComponent)
    if hp_c:
        hp_c.hp = 100
        hp_c.max_hp = 100
        hp_c.alive = True
    if exp_c:
        exp_c.level = 1
        exp_c.exp = 0
        exp_c.exp_pool = 0
    if atk_c:
        atk_c.atk_base = 13
    if eq_c:
        eq_c.equipped.clear()
