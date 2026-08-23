"""
轻量回合制战斗系统 — 从《我的世界》实战沉淀

提供比 CombatEngine（卡牌体系）更通用的回合制战斗框架：
  - attack / defend / flee 三选一
  - 护甲减免、暴击概率
  - 战利品掉落
  - 与 StackableInventory 无缝集成

与 engine 现有 CombatEngine 的区别：
  - CombatEngine: 卡牌驱动（draw/hand/AP/Buff），适合卡牌 Roguelike
  - SimpleCombat: 三选一回合制（attack/defend/flee），适合生存/RPG 类游戏

使用方式：

    from alloy.systems.simple_combat import SimpleCombat, MobTemplate

    # 定义生物模板
    mob = MobTemplate(
        mob_id="zombie", name="僵尸", hp=20, damage=3,
        drops=[("iron_ingot", 0, 1)]
    )

    # 开始战斗
    combat = SimpleCombat()
    state = combat.start(mob, player_hp=20, armor=0)

    # 玩家回合
    result = combat.attack(state, weapon_damage=5)
    if state.is_over:
        loot = combat.get_loot(state)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
#  MobTemplate — 生物 / 怪物模板
# ═══════════════════════════════════════════════════════════

@dataclass
class MobTemplate:
    """生物 / 怪物模板定义。

    属性:
        mob_id: 唯一标识
        name: 显示名称
        icon: 显示图标（emoji 或单字符）
        mob_type: 类型 — passive / neutral / hostile / boss
        hp: 基础生命值
        damage: 基础伤害值
        drops: 战利品列表 [(item_id, min_count, max_count), ...]
        flee_chance: 逃跑成功率 (0.0-1.0)
        crit_chance: 暴击率 (0.0-1.0)
        metadata: 扩展属性
    """

    mob_id: str
    name: str
    icon: str = "👾"
    mob_type: str = "hostile"
    hp: int = 20
    damage: int = 3
    drops: list[tuple[str, int, int]] = field(default_factory=list)
    flee_chance: float = 0.5
    crit_chance: float = 0.15
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_passive(self) -> bool:
        return self.mob_type == "passive"

    @property
    def is_hostile(self) -> bool:
        return self.mob_type in ("hostile", "boss")

    def to_dict(self) -> dict:
        return {
            "mob_id": self.mob_id,
            "name": self.name,
            "icon": self.icon,
            "mob_type": self.mob_type,
            "hp": self.hp,
            "damage": self.damage,
            "drops": [list(d) for d in self.drops],
            "flee_chance": self.flee_chance,
            "crit_chance": self.crit_chance,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MobTemplate":
        drops = [tuple(d) for d in data.get("drops", [])]
        return cls(
            mob_id=data["mob_id"],
            name=data["name"],
            icon=data.get("icon", "👾"),
            mob_type=data.get("mob_type", "hostile"),
            hp=data.get("hp", 20),
            damage=data.get("damage", 3),
            drops=drops,
            flee_chance=data.get("flee_chance", 0.5),
            crit_chance=data.get("crit_chance", 0.15),
            metadata=data.get("metadata", {}),
        )


# ═══════════════════════════════════════════════════════════
#  CombatResult — 战斗状态
# ═══════════════════════════════════════════════════════════

@dataclass
class CombatResult:
    """单场战斗的运行时状态。

    属性:
        mob: 生物模板引用
        mob_hp: 生物当前HP
        mob_max_hp: 生物最大HP
        player_hp: 玩家当前HP
        player_max_hp: 玩家最大HP
        armor: 玩家护甲
        turn: 当前回合数
        log: 战斗日志
        player_won: 玩家是否获胜
        last_action: 上次行动类型
    """

    mob: MobTemplate
    mob_hp: int
    mob_max_hp: int
    player_hp: int
    player_max_hp: int
    armor: int = 0
    turn: int = 0
    log: list[str] = field(default_factory=list)
    player_won: bool = False
    last_action: str = ""

    @property
    def is_over(self) -> bool:
        """战斗是否结束。"""
        return self.mob_hp <= 0 or self.player_hp <= 0

    @property
    def mob_hp_percent(self) -> float:
        """生物 HP 百分比。"""
        return self.mob_hp / self.mob_max_hp if self.mob_max_hp > 0 else 0.0


# ═══════════════════════════════════════════════════════════
#  SimpleCombat — 轻量回合制战斗引擎
# ═══════════════════════════════════════════════════════════

class SimpleCombat:
    """轻量回合制战斗引擎。

    提供三种行动: attack(攻击) / defend(防御) / flee(逃跑)
    支持护甲减免、暴击率、战利品系统。

    使用方式:

        combat = SimpleCombat()
        state = combat.start(mob, player_hp=20, armor=0)

        # 玩家行动
        msg = combat.attack(state, weapon_damage=5)
        # 或 combat.defend(state) / combat.flee(state)

        if state.is_over and state.player_won:
            drops = combat.generate_drops(state)
    """

    def start(
        self,
        mob: MobTemplate,
        player_hp: int,
        player_max_hp: int | None = None,
        armor: int = 0,
    ) -> CombatResult:
        """开始一场战斗。

        参数:
            mob: 生物模板
            player_hp: 玩家当前HP
            player_max_hp: 玩家最大HP（默认=当前HP）
            armor: 玩家护甲值

        返回:
            CombatResult 战斗状态
        """
        hp_var = random.randint(-2, 2)
        return CombatResult(
            mob=mob,
            mob_hp=max(1, mob.hp + hp_var),
            mob_max_hp=mob.hp,
            player_hp=player_hp,
            player_max_hp=player_max_hp or player_hp,
            armor=armor,
        )

    def attack(self, state: CombatResult, weapon_damage: int = 2) -> str:
        """玩家攻击。

        参数:
            state: 战斗状态
            weapon_damage: 武器基础伤害（徒手=2）

        返回:
            行动描述文本
        """
        crit = random.random() < state.mob.crit_chance
        dmg = weapon_damage * 2 if crit else weapon_damage
        dmg += random.randint(-1, 2)
        dmg = max(1, dmg)

        state.mob_hp -= dmg
        state.turn += 1
        state.last_action = "attack"

        msg = f"⚔️ 你造成 {dmg} 点伤害！"
        if crit:
            msg += " 💥暴击！"
        state.log.append(msg)

        if state.mob_hp <= 0:
            state.player_won = True
            state.last_action = "victory"
            victory_msg = f"💀 {state.mob.name}被击败了！"
            state.log.append(victory_msg)
            return msg + "\n" + victory_msg

        # 生物回击
        return msg + "\n" + self._mob_counter(state)

    def defend(self, state: CombatResult) -> str:
        """玩家防御 — 减半受到的伤害。

        返回:
            行动描述文本
        """
        state.turn += 1
        state.last_action = "defend"
        effective_dmg = max(1, state.mob.damage // 2)
        state.player_hp -= effective_dmg

        msg = f"🛡️ 你举起防御！{state.mob.name}造成 {effective_dmg} 点伤害（减半）"
        state.log.append(msg)

        if state.player_hp <= 0:
            state.last_action = "defeat"
            defeat_msg = f"💀 你被{state.mob.name}击败了……"
            state.log.append(defeat_msg)
            return msg + "\n" + defeat_msg

        return msg

    def flee(self, state: CombatResult) -> str:
        """玩家逃跑。

        返回:
            行动描述文本
        """
        if random.random() < state.mob.flee_chance:
            state.last_action = "fled"
            msg = "🏃 你成功逃跑了！"
            state.log.append(msg)
            # 逃跑视为战斗结束（不判定胜负）
            state.mob_hp = 0  # 特殊标记
            return msg

        # 逃跑失败，生物攻击一次
        state.last_action = "flee_fail"
        msg = "🏃 逃跑失败！\n" + self._mob_counter(state)
        state.log.append(msg)
        return msg

    def _mob_counter(self, state: CombatResult) -> str:
        """生物反击。"""
        dmg = max(1, state.mob.damage + random.randint(-1, 1))
        # 护甲减免
        dmg_after_armor = max(0, dmg - state.armor)
        state.player_hp -= dmg_after_armor

        armor_msg = ""
        if state.armor > 0:
            reduced = min(dmg, state.armor)
            armor_msg = f"（护甲减免 {reduced}）"

        msg = f"👊 {state.mob.name}造成 {dmg_after_armor} 点伤害！{armor_msg}"
        state.log.append(msg)

        if state.player_hp <= 0:
            state.last_action = "defeat"
            defeat_msg = f"💀 你被{state.mob.name}击败了……"
            state.log.append(defeat_msg)
            return msg + "\n" + defeat_msg

        return msg

    def generate_drops(self, state: CombatResult) -> list[tuple[str, int]]:
        """生成战利品掉落。

        参数:
            state: 战斗状态（仅在玩家胜利后调用）

        返回:
            [(item_id, count), ...]
        """
        if not state.player_won:
            return []

        drops = []
        for item_id, min_n, max_n in state.mob.drops:
            if random.random() < 0.7:  # 70% 掉落概率
                count = random.randint(min_n, max_n)
                if count > 0:
                    drops.append((item_id, count))

        return drops

    def get_xp_reward(self, state: CombatResult) -> int:
        """计算经验奖励。"""
        if not state.player_won:
            return 0
        return state.mob.hp // 2

    def get_damage_dealt(self, state: CombatResult) -> int:
        """计算对生物造成的总伤害。"""
        return state.mob_max_hp - state.mob_hp


# ═══════════════════════════════════════════════════════════
#  MobLibrary — 生物模板库
# ═══════════════════════════════════════════════════════════

class MobLibrary:
    """生物模板库 — 管理所有 MobTemplate。

    使用方式:

        lib = MobLibrary()
        lib.register(MobTemplate("zombie", "僵尸", hp=20, damage=3))
        mob = lib.get("zombie")
    """

    def __init__(self):
        self._mobs: dict[str, MobTemplate] = {}

    def register(self, mob: MobTemplate) -> None:
        """注册生物模板。"""
        self._mobs[mob.mob_id] = mob

    def register_batch(self, mobs: list[MobTemplate]) -> None:
        """批量注册。"""
        for mob in mobs:
            self._mobs[mob.mob_id] = mob

    def get(self, mob_id: str) -> Optional[MobTemplate]:
        """获取生物模板。"""
        return self._mobs.get(mob_id)

    def has(self, mob_id: str) -> bool:
        """检查是否存在。"""
        return mob_id in self._mobs

    def list_by_type(self, mob_type: str) -> list[MobTemplate]:
        """按类型筛选。"""
        return [m for m in self._mobs.values() if m.mob_type == mob_type]

    def list_all(self) -> list[MobTemplate]:
        """列出所有生物。"""
        return list(self._mobs.values())

    @property
    def count(self) -> int:
        return len(self._mobs)
