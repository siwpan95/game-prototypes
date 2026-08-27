"""
Combat Engine — 回合制战斗引擎（可选模块）。

从 BorjiginChagatai_zh 等卡牌战斗游戏合并而来。
使用 dataclass CombatState 封装单场战斗状态。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from shared_core.card import Card


# 默认常量（可被 config.py 覆盖）
HAND_SIZE = 5
STARTING_AP_PER_TURN = 3
PLAYER_MAX_HP = 100
PLAYER_MAX_NERVE = 50


@dataclass
class CombatState:
    """单场战斗的完整状态。"""

    # 玩家属性
    player_hp: int
    player_max_hp: int
    player_nerve: int
    player_max_nerve: int
    enemy: object  # EnemyInstance

    # 牌组管理
    draw_pile: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    discard_pile: List[Card] = field(default_factory=list)

    # 回合资源
    ap: int = STARTING_AP_PER_TURN
    player_block: int = 0

    # 状态效果
    blue_ring_active: bool = False
    blue_ring_turns: int = 0
    reveal_intent: bool = False
    vision_flash_turns: int = 0
    player_defense_bonus: int = 0
    zero_cost_turns: int = 0
    ap_penalty_next_turn: int = 0
    stagger_active: bool = False
    enemy_swift: bool = False
    ignore_ring_this_turn: bool = False

    # Boss 追踪
    last_player_card_id: str = ""

    # 日志回调
    _log_callback: Optional[Callable[[str], None]] = field(
        default=None, repr=False, compare=False
    )

    # 标记
    combat_over: bool = False
    player_won: bool = False
    turn_number: int = 1

    def log(self, msg: str) -> None:
        if self._log_callback:
            self._log_callback(msg)

    def shuffle_discard_into_draw(self) -> None:
        random.shuffle(self.discard_pile)
        self.draw_pile.extend(self.discard_pile)
        self.discard_pile.clear()
        self.log("弃牌堆洗入抽牌堆。")

    def draw_one(self) -> None:
        if not self.draw_pile:
            if not self.discard_pile:
                return
            self.shuffle_discard_into_draw()
        if self.draw_pile:
            card = self.draw_pile.pop()
            self.hand.append(card)

    def draw_hand(self) -> None:
        while len(self.hand) < HAND_SIZE:
            if not self.draw_pile and not self.discard_pile:
                break
            self.draw_one()

    def discard_hand(self) -> None:
        self.discard_pile.extend(self.hand)
        self.hand.clear()

    @classmethod
    def new(cls, hp: int, max_hp: int, nerve: int, max_nerve: int,
             enemy, deck: list, log_cb=None) -> "CombatState":
        cs = cls(
            player_hp=hp, player_max_hp=max_hp,
            player_nerve=nerve, player_max_nerve=max_nerve,
            enemy=enemy, _log_callback=log_cb,
        )
        cs.draw_pile = list(deck)
        random.shuffle(cs.draw_pile)
        cs.start_player_turn()
        return cs

    def start_player_turn(self) -> None:
        """开始玩家回合：重置资源、抽牌。"""
        self.player_block = 0
        self.ap = max(1, STARTING_AP_PER_TURN - self.ap_penalty_next_turn)
        self.ap_penalty_next_turn = 0
        self.stagger_active = False
        self.ignore_ring_this_turn = False
        if self.vision_flash_turns > 0:
            self.vision_flash_turns -= 1
            if self.vision_flash_turns == 0:
                self.reveal_intent = False
        if self.blue_ring_active:
            self.blue_ring_turns -= 1
            if self.blue_ring_turns <= 0:
                self.blue_ring_active = False
                self.player_defense_bonus = 0
        self.draw_hand()
        self.log(f"--- 第 {self.turn_number} 回合：你的行动。AP={self.ap} ---")

    def play_card(self, hand_index: int) -> bool:
        if hand_index < 0 or hand_index >= len(self.hand):
            return False
        card = self.hand[hand_index]
        if not getattr(card, 'playable', True):
            self.log(f"'{card.name}' 无法打出。")
            return False
        actual_ap = 0 if self.zero_cost_turns > 0 else getattr(card, 'ap_cost', 1)
        if self.ap < actual_ap:
            return False
        self.ap -= actual_ap
        nerve_cost = getattr(card, 'nerve_cost', 0)
        if self.player_nerve >= nerve_cost:
            self.player_nerve -= nerve_cost
        if self.zero_cost_turns > 0:
            self.zero_cost_turns -= 1
        self.last_player_card_id = card.id
        self.hand.pop(hand_index)
        effect = getattr(card, 'effect', None)
        if effect:
            effect(self)
        self.discard_pile.append(card)
        if hasattr(self.enemy, 'hp') and self.enemy.hp <= 0:
            self.combat_over = True
            self.player_won = True
        return True

    def end_player_turn(self) -> None:
        if self.combat_over:
            return
        self.log("--- 你的回合结束 ---")
        self.discard_hand()
        self._run_enemy_turn()
        if not self.combat_over:
            self.turn_number += 1
            self.start_player_turn()

    def _run_enemy_turn(self) -> None:
        if not hasattr(self.enemy, 'hp') or self.enemy.hp <= 0:
            return
        intent = self.enemy.choose_intent() if hasattr(self.enemy, 'choose_intent') else type('obj', damage=5)
        dmg = getattr(intent, 'damage', 5)
        if self.enemy_swift:
            dmg += 4
            self.enemy_swift = False
        self._apply_damage(dmg)

    def _apply_damage(self, raw_dmg: int) -> None:
        defense = 0 if (self.ignore_ring_this_turn and self.blue_ring_active) else self.player_defense_bonus
        dmg_after_def = max(0, raw_dmg - defense)
        block_val = self.player_block // 2 if self.stagger_active else self.player_block
        dmg_final = max(0, dmg_after_def - block_val)
        self.player_block = max(0, self.player_block - dmg_after_def)
        if dmg_final > 0:
            self.player_hp -= dmg_final
        if self.player_hp <= 0:
            self.player_hp = 0
            self.combat_over = True
            self.player_won = False


class CombatEngine:
    """战斗引擎包装器 — 管理 CombatState 生命周期。"""

    def __init__(self, state: CombatState | None = None):
        self.state = state

    def start_combat(self, player_hp, player_max_hp, player_nerve, player_max_nerve,
                      enemy, deck: list, log_cb=None) -> CombatState:
        self.state = CombatState.new(player_hp, player_max_hp, player_nerve,
                                       player_max_nerve, enemy, deck, log_cb)
        return self.state
