"""
技能系统 — ViewModel（混合架构之 MVVM 部分）
绑定技能状态到 UI，提供技能释放命令。
技能获取：开局仅1个基础技能，通过升级/Boss击杀逐步解锁。
"""

import random
from typing import Any, Callable, Dict, List, Optional

from .skill_components import SkillSlotComponent
from .skill_defs import get_skill_defs


# ── 技能解锁表：等级 → 可解锁的技能 ID 列表 ───────────────────
_SKILL_UNLOCK_TABLE: Dict[int, List[str]] = {
    1:  ["flame_slash"],
    3:  ["heal"],
    5:  ["lightning_chain"],
    7:  ["ice_shard"],
    10: ["shadow_step"],
    13: ["poison_strike"],
    16: ["thunder_clap"],
    20: ["blood_rage"],
}

# 全部可解锁技能 ID 的汇总（方便随机）
_ALL_SKILL_IDS = [
    sid for ids in _SKILL_UNLOCK_TABLE.values() for sid in ids
]


class SkillViewModel:
    """
    技能 ViewModel：
    - 操作玩家实体上的 SkillSlotComponent
    - 提供 cmd_use_skill(skill_id, target_eid) 命令
    - 管理技能解锁（升级 / Boss击杀）
    """

    def __init__(self, world: Any, player_eid: int,
                  notify_fn: Optional[Callable[[str], None]] = None) -> None:
        self.world = world
        self.player_eid = player_eid
        self._notify_fn = notify_fn
        # 确保玩家有 SkillSlotComponent
        from .skill_components import SkillSlotComponent
        slot = world.get_component(player_eid, SkillSlotComponent)
        if slot is None:
            slot = SkillSlotComponent(max_slots=8)
            # 开局仅解锁 1 个基础技能
            slot.skill_ids = ["flame_slash"]
            world.add_component(player_eid, slot)

    # ── 技能解锁 ──────────────────────────────────

    def unlock_skill(self, skill_id: str) -> bool:
        """解锁一个技能，返回 True 表示成功"""
        slot = self.world.get_component(self.player_eid,
                                        SkillSlotComponent)
        if slot is None:
            return False
        if skill_id in slot.skill_ids:
            return False  # 已解锁
        if len(slot.skill_ids) >= slot.max_slots:
            return False  # 槽位已满
        skill_defs = get_skill_defs()
        if skill_id not in skill_defs:
            return False
        slot.skill_ids.append(skill_id)
        if self._notify_fn:
            self._notify_fn("skills")
        return True

    def check_level_unlocks(self, new_level: int, log_fn: Callable[[str], None]) -> None:
        """根据玩家新等级自动解锁对应技能"""
        slot = self.world.get_component(self.player_eid,
                                        SkillSlotComponent)
        if slot is None:
            return
        skill_defs = get_skill_defs()
        for lv, ids in sorted(_SKILL_UNLOCK_TABLE.items()):
            if lv <= new_level:
                for sid in ids:
                    if sid not in slot.skill_ids:
                        name = skill_defs.get(sid, {}).get("name", sid)
                        self.unlock_skill(sid)
                        log_fn(f"✨ 解锁新技能：{name}！（Lv.{lv}）")

    def random_unlock(self, log_fn: Callable[[str], None]) -> bool:
        """
        随机解锁一个尚未拥有的技能（Boss掉落等途径）。
        返回 True 表示有技能被解锁。
        """
        slot = self.world.get_component(self.player_eid,
                                        SkillSlotComponent)
        if slot is None:
            return False
        locked = [sid for sid in _ALL_SKILL_IDS
                  if sid not in slot.skill_ids
                  and sid in get_skill_defs()]
        if not locked:
            return False
        chosen = random.choice(locked)
        skill_defs = get_skill_defs()
        name = skill_defs.get(chosen, {}).get("name", chosen)
        if self.unlock_skill(chosen):
            log_fn(f"🎁 Boss 掉落技能书：习得「{name}」！")
            return True
        return False

    def get_locked_skills(self) -> List[str]:
        """返回尚未解锁的技能 ID 列表"""
        slot = self.world.get_component(self.player_eid,
                                        SkillSlotComponent)
        if slot is None:
            return list(_ALL_SKILL_IDS)
        return [sid for sid in _ALL_SKILL_IDS
                if sid not in slot.skill_ids]

    # ── 命令 ──────────────────────────────────

    def cmd_use_skill(self, skill_id: str, target_eid: int,
                      log_fn: Callable[[str], None]) -> bool:
        """
        释放技能。
        返回 True 表示成功释放。
        """
        slot = self.world.get_component(self.player_eid,
                                        SkillSlotComponent)
        if slot is None or skill_id not in slot.skill_ids:
            log_fn(f"❌ 未解锁技能：{skill_id}")
            return False

        # 检查冷却
        if slot.cooldowns.get(skill_id, 0) > 0:
            skill_defs = get_skill_defs()
            log_fn(f"❌ {skill_defs[skill_id]['name']} 还在冷却中（{slot.cooldowns[skill_id]}s）")
            return False

        # 检查经验池消耗
        from ecs.components import ExpComponent
        exp_c = self.world.get_component(self.player_eid, ExpComponent)
        skill_defs = get_skill_defs()
        cost = skill_defs[skill_id].get("cost_exp_pool", 0)
        if exp_c and exp_c.exp_pool < cost:
            log_fn(f"❌ 经验池不足（需要 {cost}，当前 {exp_c.exp_pool}）")
            return False

        # 扣费
        if exp_c:
            exp_c.exp_pool -= cost

        # 执行技能效果
        skill_defs = get_skill_defs()
        effect_fn = skill_defs[skill_id].get("effect")
        if effect_fn is None:
            log_fn(f"❌ 技能 {skill_id} 没有效果函数")
            return False
        effect_fn(self.world, self.player_eid, target_eid, log_fn)

        # 设置冷却（考虑装备 CD 缩减）
        skill_defs = get_skill_defs()
        cd = skill_defs[skill_id].get("cooldown", 0)
        if cd > 0:
            # 装备冷却缩短
            from skills.skill_defs import _get_cd_reduction
            cd = max(1, cd + _get_cd_reduction(self.world, self.player_eid))
            slot.cooldowns[skill_id] = cd

        if self._notify_fn:
            self._notify_fn("skills")
        return True

    def tick_cooldowns(self, dt: int = 1) -> None:
        """每 tick 递减冷却计时器"""
        slot = self.world.get_component(self.player_eid,
                                        SkillSlotComponent)
        if slot is None:
            return
        changed = False
        for sid in list(slot.cooldowns.keys()):
            if slot.cooldowns[sid] > 0:
                slot.cooldowns[sid] -= dt
                changed = True
        if changed and self._notify_fn:
            self._notify_fn("skills")

    # ── 绑定属性（供 View 读取）────────────────

    def get_skill_states(self) -> List[Dict[str, Any]]:
        """返回技能状态列表，供 View 绑定"""
        slot = self.world.get_component(self.player_eid,
                                        SkillSlotComponent)
        if slot is None:
            return []
        result: List[Dict[str, Any]] = []
        skill_defs = get_skill_defs()
        for sid in slot.skill_ids:
            def_ = skill_defs.get(sid)
            if def_ is None:
                continue
            cd = slot.cooldowns.get(sid, 0)
            result.append({
                "id": sid,
                "name": def_["name"],
                "desc": def_["desc"],
                "cooldown": cd,
                "cost": def_.get("cost_exp_pool", 0),
                "ready": cd <= 0,
            })
        return result
