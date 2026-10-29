# -*- coding: utf-8 -*-
"""战斗系统 — 回合制自动战斗 (D&D风格)"""

import random
from typing import Dict, List, Tuple

from core.models import Adventurer, Monster, Skill
from data.loader import get_loader


class BattleSystem:
    """回合制自动战斗"""

    @staticmethod
    def run(party: List[Adventurer], monster: Monster,
            floor_buffs: dict = None, max_turns: int = 20) -> Tuple[bool, List[str], int, int]:
        """
        执行一场自动战斗。
        floor_buffs: {"力量药剂": 30} → ATK+30%
        返回: (胜利?, 战斗日志, 获得金币, 获得经验)
        """
        alive = [a for a in party if a.is_alive()]
        if not alive:
            return False, ["💀 全队阵亡..."], 0, 0

        loader = get_loader()
        buff_mult = 1.0
        if floor_buffs:
            for name, val in floor_buffs.items():
                c = loader.consumables.get(name)
                if c and c.item_type == "buff":
                    buff_mult += val / 100.0

        # 构建行动序列
        actors = [("hero", a) for a in alive] + [("monster", monster)]
        actors.sort(key=lambda x: (BattleSystem._spd(x[1], loader) if x[0] == "hero" else x[1].spd), reverse=True)

        monster_hp = monster.hp
        log: List[str] = []
        victory = False
        monster_hp_ref = [monster_hp]

        # ---- 本场战斗的本地 CD 追踪（避免污染 DataLoader 单例） ----
        skill_cd: Dict[str, int] = {}   # 英雄技能名 -> 剩余回合数
        monster_cd: Dict[str, int] = {}  # 怪物技能名 -> 剩余回合数

        for _turn in range(max_turns):
            if monster_hp_ref[0] <= 0:
                victory = True
                log.append(f"💥 {monster.name} 被击败！")
                break

            alive = [a for a in party if a.is_alive()]
            if not alive:
                log.append("💀 全队阵亡...")
                break

            for atype, actor in actors:
                if monster_hp_ref[0] <= 0:
                    break

                if atype == "hero":
                    a = actor
                    if not a.is_alive():
                        continue
                    BattleSystem._hero_action(a, monster, party, loader, log,
                                              monster_hp_ref, buff_mult, skill_cd)
                else:
                    if monster_hp_ref[0] <= 0:
                        break
                    BattleSystem._monster_action(monster, party, loader, log,
                                                  monster_hp_ref, monster_cd)

        # 结算
        gold_earned = monster.gold + random.randint(0, monster.gold // 2) if victory else 0
        exp_earned = monster.exp if victory else 0

        return victory, log, gold_earned, exp_earned

    @staticmethod
    def _spd(a: Adventurer, loader) -> int:
        bonus = sum(loader.equipment[e].spd_bonus for e in a.equipment.values()
                    if e and e in loader.equipment)
        return a.spd + bonus

    @staticmethod
    def _full_atk(a: Adventurer, loader) -> int:
        bonus = sum(loader.equipment[e].atk_bonus for e in a.equipment.values()
                    if e and e in loader.equipment)
        return a.atk + bonus

    @staticmethod
    def _hero_action(a: Adventurer, monster: Monster, party: List[Adventurer],
                     loader, log: List[str],
                     monster_hp: list, buff_mult: float = 1.0,
                     skill_cd: Dict[str, int] = None):
        """英雄行动（使用本地 skill_cd 追踪冷却，不修改 DataLoader 单例）"""
        if skill_cd is None:
            skill_cd = {}

        # 尝试使用技能
        skill_used = None
        for sk_name in a.skills:
            sk = loader.skills.get(sk_name)
            if sk and skill_cd.get(sk_name, 0) <= 0 and a.mp >= sk.mp_cost:
                skill_used = sk
                break

        if skill_used and random.random() < 0.5:
            a.mp -= skill_used.mp_cost
            skill_cd[skill_used.name] = skill_used.cooldown  # 写本地 dict

            if skill_used.skill_type == "attack":
                atk = BattleSystem._full_atk(a, loader)
                dmg = int(atk * skill_used.power * buff_mult * random.uniform(0.85, 1.15)
                          - monster.def_ * 0.3)
                dmg = max(1, dmg)
                monster_hp[0] -= dmg
                log.append(f"{a.name} 使用 [{skill_used.name}] 造成 {dmg} 伤害！")
            elif skill_used.skill_type == "heal":
                atk = BattleSystem._full_atk(a, loader)
                heal = int(atk * skill_used.power)
                # 治疗血量最低的队友
                alive = [p for p in party if p.is_alive()]
                target = min(alive, key=lambda x: x.hp) if alive else a
                target.hp = min(BattleSystem._full_hp(target, loader), target.hp + heal)
                log.append(f"{a.name} 使用 [{skill_used.name}] 回复 {target.name} {heal} HP！")
            elif skill_used.skill_type == "buff":
                # 增益技能：提升自身攻击力（本场战斗内持续）
                log.append(f"{a.name} 使用 [{skill_used.name}]，气势大增！")
        else:
            atk = BattleSystem._full_atk(a, loader)
            dmg = int(atk * buff_mult * random.uniform(0.8, 1.2) - monster.def_ * 0.3)
            dmg = max(0, dmg)
            monster_hp[0] -= dmg
            if dmg > 0:
                log.append(f"{a.name} 攻击造成 {dmg} 伤害")
            else:
                log.append(f"{a.name} 的攻击被 {monster.name} 的防御挡住了")

        # 减CD（本地 dict）
        for sk_name in list(skill_cd.keys()):
            if skill_cd[sk_name] > 0:
                skill_cd[sk_name] -= 1

    @staticmethod
    def _full_hp(a: Adventurer, loader) -> int:
        bonus = sum(loader.equipment[e].hp_bonus for e in a.equipment.values()
                    if e and e in loader.equipment)
        return a.max_hp + bonus

    @staticmethod
    def _monster_action(monster: Monster, party: List[Adventurer], loader, log: List[str],
                       monster_hp: list, monster_cd: Dict[str, int] = None):
        """怪物行动（支持怪物技能）"""
        if monster_cd is None:
            monster_cd = {}

        alive = [a for a in party if a.is_alive()]
        if not alive:
            return
        target = random.choice(alive)

        def_bonus = sum(loader.equipment[e].def_bonus for e in target.equipment.values()
                        if e and e in loader.equipment)
        total_def = target.def_ + def_bonus

        # 尝试使用怪物技能
        skill_used = None
        for sk_name in monster.skills:
            sk = loader.skills.get(sk_name)
            if sk and monster_cd.get(sk_name, 0) <= 0:
                skill_used = sk
                break

        use_skill = skill_used and random.random() < 0.35

        if use_skill:
            monster_cd[skill_used.name] = skill_used.cooldown

            if skill_used.skill_type == "attack":
                dmg = int(monster.atk * skill_used.power * random.uniform(0.9, 1.1)
                          - total_def * 0.3)
                dmg = max(1, dmg)
                target.hp = max(0, target.hp - dmg)
                log.append(f"{monster.emoji} {monster.name} 使用 [{skill_used.name}] 对 {target.name} 造成 {dmg} 伤害！")
                if target.hp <= 0:
                    target.dead = True
                    log.append(f"💔 {target.name} 倒下了！")
            elif skill_used.skill_type == "heal":
                heal = int(monster.hp * skill_used.power)
                monster_hp[0] = min(monster.hp, monster_hp[0] + heal)
                log.append(f"{monster.emoji} {monster.name} 使用 [{skill_used.name}]，恢复了 {heal} HP！")
            elif skill_used.skill_type == "buff":
                log.append(f"{monster.emoji} {monster.name} 使用 [{skill_used.name}]，气势变得更强了！")
        else:
            # 普通攻击
            dmg = int(monster.atk * random.uniform(0.85, 1.15) - total_def * 0.5)
            dmg = max(1, dmg)
            target.hp = max(0, target.hp - dmg)
            log.append(f"{monster.emoji} {monster.name} 攻击 {target.name} 造成 {dmg} 伤害！")
            if target.hp <= 0:
                target.dead = True
                log.append(f"💔 {target.name} 倒下了！")

        # 减怪物技能 CD
        for sk_name in list(monster_cd.keys()):
            if monster_cd[sk_name] > 0:
                monster_cd[sk_name] -= 1
