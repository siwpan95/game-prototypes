"""
战斗引擎 — 回合制卡牌战斗系统。

封装单场战斗完整状态：HP/神经/AP/格挡/牌堆/Buff/Debuff。
支持战斗生命周期管理、战斗日志、经验/金币奖励。

使用方式:

    engine = CombatEngine()
    state = engine.start_combat(
        player_hp=100, player_max_hp=100,
        player_nerve=50, player_max_nerve=50,
        enemy=enemy_instance, deck=deck,
        log_callback=print,
    )
    state.play_card(0)
    state.end_player_turn()
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional

from .card import Card
from .enemy import EnemyInstance


# ---------------------------------------------------------------
# 常量
# ---------------------------------------------------------------

HAND_SIZE: int = 5
"""每回合手牌上限。"""

STARTING_AP_PER_TURN: int = 3
"""每回合初始行动点数。"""

PLAYER_MAX_HP: int = 100
"""玩家默认最大生命值。"""

PLAYER_MAX_NERVE: int = 50
"""玩家默认最大神经值。"""


# ---------------------------------------------------------------
# Buff 类型
# ---------------------------------------------------------------

class BuffType(Enum):
    """战斗 Buff / Debuff 类型。"""

    # 正面 Buff
    BLUE_RING = auto()          # 蓝环：下次受击减伤
    ZERO_COST = auto()          # 零费：卡牌 AP 消耗为 0
    STRENGTH_UP = auto()        # 力量提升
    REGENERATION = auto()       # 回复
    THORNS = auto()             # 荆棘：反伤
    INVULNERABLE = auto()       # 无敌

    # 负面 Debuff
    VULNERABLE = auto()         # 易伤：受到更多伤害
    WEAK = auto()               # 虚弱：造成更少伤害
    STAGGER = auto()            # 踉跄：格挡减半
    AP_PENALTY = auto()         # AP 惩罚：下回合 AP 减少
    SWIFT = auto()              # 迅捷：敌人额外伤害
    BLEEDING = auto()           # 流血：每回合掉血


# ---------------------------------------------------------------
# CombatState
# ---------------------------------------------------------------

@dataclass
class CombatState:
    """单场战斗的完整状态。

    管理玩家属性、牌堆、回合资源、Buff/Debuff 状态。
    """

    # 玩家属性
    player_hp: int
    player_max_hp: int
    player_nerve: int
    player_max_nerve: int

    # 敌人实例
    enemy: EnemyInstance

    # 牌组管理
    draw_pile: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    discard_pile: list[Card] = field(default_factory=list)

    # 回合资源
    ap: int = STARTING_AP_PER_TURN
    player_block: int = 0

    # --- Buff / Debuff 状态 ---
    blue_ring_active: bool = False
    blue_ring_turns: int = 0
    reveal_intent: bool = False
    vision_flash_turns: int = 0
    player_defense_bonus: int = 0
    zero_cost_turns: int = 0
    ap_penalty_next_turn: int = 0
    stagger_active: bool = False
    strength_bonus: int = 0
    vulnerable_turns: int = 0
    regeneration_turns: int = 0
    bleeding_turns: int = 0

    # 敌人特殊属性
    enemy_swift: bool = False
    ignore_ring_this_turn: bool = False

    # Boss 追踪
    last_player_card_id: str = ""

    # 战斗日志
    combat_log: list[str] = field(default_factory=list)
    _log_callback: Optional[Callable[[str], None]] = field(
        default=None, repr=False, compare=False,
    )

    # 奖励
    exp_reward: int = 0
    gold_reward: int = 0

    # 战斗状态标记
    combat_over: bool = False
    player_won: bool = False
    turn_number: int = 1

    # ---- 日志 ----

    def log(self, msg: str) -> None:
        """记录日志（回调 + 内置列表）。"""
        self.combat_log.append(msg)
        if self._log_callback:
            self._log_callback(msg)

    # ---- 牌堆操作 ----

    def shuffle_discard_into_draw(self) -> None:
        """洗入弃牌堆到抽牌堆。"""
        random.shuffle(self.discard_pile)
        self.draw_pile.extend(self.discard_pile)
        self.discard_pile.clear()
        self.log("弃牌堆洗入抽牌堆。")

    def draw_one(self) -> None:
        """抽一张牌。"""
        if not self.draw_pile:
            if not self.discard_pile:
                return
            self.shuffle_discard_into_draw()
        if self.draw_pile:
            card = self.draw_pile.pop()
            self.hand.append(card)

    def draw_hand(self) -> None:
        """补满手牌至 HAND_SIZE。"""
        while len(self.hand) < HAND_SIZE:
            if not self.draw_pile and not self.discard_pile:
                break
            self.draw_one()

    def discard_hand(self) -> None:
        """弃掉所有手牌。"""
        self.discard_pile.extend(self.hand)
        self.hand.clear()

    # ---- 回合流程 ----

    def start_player_turn(self) -> None:
        """开始玩家回合：重置资源、处理 Buff 衰减、抽牌。"""
        self.player_block = 0
        self.ap = max(1, STARTING_AP_PER_TURN - self.ap_penalty_next_turn)
        self.ap_penalty_next_turn = 0
        self.stagger_active = False
        self.ignore_ring_this_turn = False

        # Buff/Debuff 衰减
        self._tick_buffs()

        # 流血伤害
        if self.bleeding_turns > 0:
            bleed_dmg = 3
            self.player_hp -= bleed_dmg
            self.log(f"流血造成 {bleed_dmg} 点伤害！")

        # 回复
        if self.regeneration_turns > 0:
            regen = 3
            self.player_hp = min(self.player_max_hp, self.player_hp + regen)
            self.log(f"回复了 {regen} 点生命。")

        self.draw_hand()
        self.log(f"--- 第 {self.turn_number} 回合：你的行动。AP={self.ap} ---")

    def _tick_buffs(self) -> None:
        """回合开始时 Buff/Debuff 计时衰减。"""
        if self.vision_flash_turns > 0:
            self.vision_flash_turns -= 1
            if self.vision_flash_turns == 0:
                self.reveal_intent = False

        if self.blue_ring_active:
            self.blue_ring_turns -= 1
            if self.blue_ring_turns <= 0:
                self.blue_ring_active = False
                self.player_defense_bonus = 0

        if self.vulnerable_turns > 0:
            self.vulnerable_turns -= 1

        if self.regeneration_turns > 0:
            self.regeneration_turns -= 1

        if self.bleeding_turns > 0:
            self.bleeding_turns -= 1

        if self.strength_bonus > 0:
            self.strength_bonus = max(0, self.strength_bonus - 1)

    # ---- 出牌 ----

    def play_card(self, hand_index: int) -> bool:
        """打出手牌。

        :param hand_index: 手牌索引
        :returns: 是否成功打出
        """
        if hand_index < 0 or hand_index >= len(self.hand):
            self.log("无效的手牌索引。")
            return False

        card = self.hand[hand_index]

        if not getattr(card, 'playable', True):
            self.log(f"'{card.name}' 无法打出。")
            return False

        # 计算 AP 消耗
        actual_ap = 0 if self.zero_cost_turns > 0 else getattr(card, 'ap_cost', 1)
        if self.ap < actual_ap:
            self.log(f"AP 不足！需要 {actual_ap}，当前 {self.ap}。")
            return False

        self.ap -= actual_ap

        # 神经消耗
        nerve_cost = getattr(card, 'nerve_cost', 0)
        if self.player_nerve >= nerve_cost:
            self.player_nerve -= nerve_cost

        if self.zero_cost_turns > 0:
            self.zero_cost_turns -= 1

        self.last_player_card_id = card.id
        self.hand.pop(hand_index)

        # 力量和脆弱
        effective_damage = getattr(card, 'damage', 0) + self.strength_bonus
        if self.vulnerable_turns > 0:
            effective_damage = int(effective_damage * 1.5)

        # 执行卡牌效果
        effect = getattr(card, 'effect', None)
        if effect:
            effect(self)

        # 执行基础效果（伤害/格挡/治疗）
        if effective_damage > 0 and hasattr(self.enemy, 'hp'):
            self.enemy.hp -= effective_damage
            self.log(f"对 {self.enemy.name} 造成 {effective_damage} 点伤害！")

        block_val = getattr(card, 'block', 0)
        if block_val > 0:
            self.player_block += block_val
            self.log(f"获得 {block_val} 点格挡。")

        heal_val = getattr(card, 'heal', 0)
        if heal_val > 0:
            self.player_hp = min(self.player_max_hp, self.player_hp + heal_val)
            self.log(f"回复了 {heal_val} 点生命。")

        # 弃牌
        self.discard_pile.append(card)

        # 检查敌人是否死亡
        if hasattr(self.enemy, 'hp') and self.enemy.hp <= 0:
            self.combat_over = True
            self.player_won = True
            self._on_victory()

        return True

    def end_player_turn(self) -> bool:
        """结束玩家回合，开始敌人回合。

        :returns: 是否成功（战斗未结束时返回 True）
        """
        if self.combat_over:
            return True

        self.log("--- 你的回合结束 ---")
        self.discard_hand()
        self._run_enemy_turn()

        if not self.combat_over:
            self.turn_number += 1
            self.start_player_turn()

        return True

    # ---- 敌人回合 ----

    def _run_enemy_turn(self) -> None:
        """执行敌人回合。"""
        if not hasattr(self.enemy, 'hp') or self.enemy.hp <= 0:
            return

        # 选择意图
        intent_name = "default"
        intent_dmg = 5

        if hasattr(self.enemy, 'choose_intent'):
            intent = self.enemy.choose_intent()
            intent_dmg = getattr(intent, 'damage', 5)
            intent_name = getattr(intent, 'name', '攻击')

            # 特殊效果
            effect_tag = getattr(intent, 'effect_tag', '')
            if effect_tag == 'SWIFT':
                self.enemy_swift = True
            elif effect_tag == 'STAGGER':
                self.stagger_active = True
            elif effect_tag == 'IGNORE_RING':
                self.ignore_ring_this_turn = True
            elif effect_tag == 'HIGH_PRESS':
                self.ap_penalty_next_turn = max(self.ap_penalty_next_turn, 1)

            self.log(f"{self.enemy.name} 的意图: {intent_name}（伤害 {intent_dmg}）")
        else:
            self.log(f"{self.enemy.name} 进行攻击。")

        # 敌人特殊加成
        if self.enemy_swift:
            intent_dmg += 4
            self.enemy_swift = False

        self._apply_damage(intent_dmg)

    def _apply_damage(self, raw_dmg: int) -> None:
        """对玩家造成伤害（考虑防御/格挡/踉跄/蓝环）。"""
        # 防御奖励
        defense = 0
        if not (self.ignore_ring_this_turn and self.blue_ring_active):
            defense = self.player_defense_bonus

        dmg_after_def = max(0, raw_dmg - defense)

        # 格挡（踉跄时减半）
        block_val = self.player_block // 2 if self.stagger_active else self.player_block
        dmg_final = max(0, dmg_after_def - block_val)
        self.player_block = max(0, self.player_block - dmg_after_def)

        if dmg_final > 0:
            self.player_hp -= dmg_final
            self.log(f"受到 {dmg_final} 点伤害！剩余 HP: {self.player_hp}")

        if self.player_hp <= 0:
            self.player_hp = 0
            self.combat_over = True
            self.player_won = False
            self._on_defeat()

    # ---- 胜负判定与奖励 ----

    def check_victory(self) -> bool:
        """检查是否胜利。"""
        return self.combat_over and self.player_won

    def check_defeat(self) -> bool:
        """检查是否失败。"""
        return self.combat_over and not self.player_won

    def _on_victory(self) -> None:
        """胜利回调：计算奖励。"""
        self.log(f"--- 恭喜！你击败了 {self.enemy.name}！---")

        # 经验奖励（基于敌人 HP）
        self.exp_reward = getattr(self.enemy, "max_hp", 50)
        self.log(f"获得 {self.exp_reward} 经验值。")

        # 金币奖励
        self.gold_reward = random.randint(10, 30)
        if getattr(self.enemy, 'is_boss', False):
            self.gold_reward = random.randint(50, 100)
        self.log(f"获得 {self.gold_reward} 金币。")

    def _on_defeat(self) -> None:
        """失败回调。"""
        self.log(f"--- 你被 {self.enemy.name} 击败了…… ---")

    # ---- 构造 ----

    @classmethod
    def new(
        cls,
        hp: int,
        max_hp: int,
        nerve: int,
        max_nerve: int,
        enemy: EnemyInstance,
        deck: list[Card],
        log_cb: Optional[Callable[[str], None]] = None,
    ) -> "CombatState":
        """创建并初始化一场新战斗。

        :param hp: 玩家当前 HP
        :param max_hp: 玩家最大 HP
        :param nerve: 玩家当前神经值
        :param max_nerve: 玩家最大神经值
        :param enemy: 敌人实例
        :param deck: 玩家卡组列表
        :param log_cb: 日志回调
        """
        cs = cls(
            player_hp=hp,
            player_max_hp=max_hp,
            player_nerve=nerve,
            player_max_nerve=max_nerve,
            enemy=enemy,
            _log_callback=log_cb,
        )
        cs.draw_pile = list(deck)
        random.shuffle(cs.draw_pile)
        cs.start_player_turn()
        return cs


# ---------------------------------------------------------------
# CombatEngine
# ---------------------------------------------------------------

class CombatEngine:
    """战斗引擎包装器 — 管理 CombatState 的生命周期。

    使用方式:

        engine = CombatEngine()
        state = engine.start_combat(100, 100, 50, 50, enemy, deck)
        state.play_card(0)
        state.end_player_turn()
        if state.check_victory():
            print("战斗胜利！")
    """

    def __init__(self, state: Optional[CombatState] = None):
        self.state: Optional[CombatState] = state
        self._battle_history: list[CombatState] = []

    def start_combat(
        self,
        player_hp: int,
        player_max_hp: int,
        player_nerve: int,
        player_max_nerve: int,
        enemy: EnemyInstance,
        deck: list[Card],
        log_cb: Optional[Callable[[str], None]] = None,
    ) -> CombatState:
        """开始一场新的战斗。

        :returns: CombatState 实例
        """
        self.state = CombatState.new(
            hp=player_hp,
            max_hp=player_max_hp,
            nerve=player_nerve,
            max_nerve=player_max_nerve,
            enemy=enemy,
            deck=deck,
            log_cb=log_cb,
        )
        return self.state

    def play_card(self, hand_index: int) -> bool:
        """打出指定手牌。"""
        if self.state is None:
            return False
        return self.state.play_card(hand_index)

    def end_player_turn(self) -> bool:
        """结束玩家回合。"""
        if self.state is None:
            return False
        return self.state.end_player_turn()

    def check_victory(self) -> bool:
        """检查是否胜利。"""
        return self.state is not None and self.state.check_victory()

    def check_defeat(self) -> bool:
        """检查是否失败。"""
        return self.state is not None and self.state.check_defeat()

    def end_combat(self) -> Optional[CombatState]:
        """结束战斗并归档到历史。"""
        if self.state is None:
            return None
        self._battle_history.append(self.state)
        result = self.state
        self.state = None
        return result

    @property
    def battle_history(self) -> list[CombatState]:
        """返回战斗历史。"""
        return list(self._battle_history)

    @property
    def total_battles(self) -> int:
        """总战斗次数。"""
        return len(self._battle_history)

    @property
    def victories(self) -> int:
        """胜利次数。"""
        return sum(1 for s in self._battle_history if s.player_won)
