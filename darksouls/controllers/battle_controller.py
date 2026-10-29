"""BattleController - orchestrate battle flow."""

from __future__ import annotations

import random

from models.card import Card
from models.player import Player
from models.enemy import Enemy
from models.dice_engine import DiceEngine, DiceResult
from models.keyword_handler import KeywordHandler
from models.deck_manager import DeckManager
from game.event_bus import EventBus


class BattleLog:
    """Simple log of battle events for display."""

    def __init__(self, max_entries: int = 8) -> None:
        self._entries: list[str] = []
        self._max = max_entries

    def add(self, message: str) -> None:
        self._entries.append(message)
        if len(self._entries) > self._max:
            self._entries.pop(0)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def entries(self) -> list[str]:
        return list(self._entries)


class BattleController:
    """Orchestrates the full battle flow."""

    def __init__(
        self,
        player: Player,
        enemy: Enemy,
        event_bus: EventBus,
        data_loader=None,
    ) -> None:
        self.player = player
        self.enemy = enemy
        self.event_bus = event_bus
        self.data_loader = data_loader
        self.log = BattleLog()

        self.player_turn: bool = True
        self.battle_over: bool = False
        self.player_won: bool = False
        self.selected_card_index: int = 0
        self.dice_result: DiceResult | None = None
        self.damage_result: DiceResult | None = None
        self.last_damage_dealt: int = 0
        self._enemy_actions_remaining: int = 0

        self.deck: DeckManager = player.deck

    def start_battle(self) -> None:
        self.log.clear()
        self.battle_over = False
        self.player_won = False
        self.player.reset_block()
        self.player.reset_fp()
        self.enemy.reset_block()
        self.enemy.vulnerable = 0
        self.enemy.stun_count = 0

        self.deck.reset_for_battle()

        self.event_bus.emit("on_battle_start", player=self.player, enemy=self.enemy)
        self._process_relic_effects("on_battle_start")

        self.deck.draw(5)
        self.player.reset_fp()

        self.enemy.set_intent(self._card_lookup)

        self.player_turn = True
        self.selected_card_index = 0
        self.log.add("战斗开始！")

    def _card_lookup(self, card_id: str) -> Card | None:
        if self.data_loader:
            return self.data_loader.create_card(card_id)
        return None

    def _process_relic_effects(self, trigger: str) -> None:
        results = self.event_bus.emit(trigger, player=self.player, enemy=self.enemy)
        for result in results:
            if isinstance(result, dict) and "effect" in result:
                effect = result["effect"]
                self._apply_relic_effect(effect)

    def _apply_relic_effect(self, effect: dict) -> None:
        if "AddMaxHP" in effect:
            self.player.max_hp += effect["AddMaxHP"]
            self.player.hp += effect["AddMaxHP"]
            self.log.add(f"最大生命+{effect['AddMaxHP']}！")
        elif "HealPercent" in effect:
            healed = self.player.heal_percent(effect["HealPercent"])
            self.log.add(f"恢复了 {healed} 生命！")
        elif "AddMaxFP" in effect:
            self.player.max_fp += effect["AddMaxFP"]
            self.log.add(f"最大FP+{effect['AddMaxFP']}！")
        elif "AddFlat" in effect:
            pass

    def play_selected_card(self) -> str | None:
        if not self.player_turn or self.battle_over:
            return None

        hand = self.deck.hand
        if not hand:
            return None

        if self.selected_card_index >= len(hand):
            self.selected_card_index = len(hand) - 1
            return None

        card = hand[self.selected_card_index]

        if card.cost > self.player.fp:
            self.log.add(f"FP不足，无法使用 {card.name}！")
            return "FP不足！"

        self.player.fp -= card.cost

        repeat_count = 1
        if "Repeat" in card.keywords:
            repeat_count += card.keywords["Repeat"]

        total_damage = 0
        for _ in range(repeat_count):
            if card.is_attack() and card.damage != "0":
                dmg_result = self._resolve_attack(card)
                total_damage += self.last_damage_dealt
            elif card.block > 0:
                self._resolve_defense(card)

            self._resolve_keywords(card, total_damage)

        if card.has_keyword("Exhaust"):
            self.deck.exhaust_card(card)
        elif card.has_keyword("Consume"):
            self.deck.consume_card(card)
        else:
            self.deck.discard_card(card)

        self.event_bus.emit("on_card_played", player=self.player, card=card)
        self._process_relic_effects("on_card_played")

        if self.selected_card_index >= len(self.deck.hand):
            self.selected_card_index = max(0, len(self.deck.hand) - 1)

        if self.enemy.is_dead():
            self._on_victory()
            return "敌人已击败！"

        return None

    def _resolve_attack(self, card: Card) -> DiceResult:
        self.dice_result = DiceEngine.roll_d20(self.player.str)

        if self.dice_result.is_mishap:
            self.log.add(f"失误！{card.name} 反噬自身！")
            self.player.take_damage(3)
            self.damage_result = DiceResult(total=0, rolls=[])
            self.last_damage_dealt = 0
            return self.dice_result

        if self.dice_result.total < 6 and not self.dice_result.is_crit:
            self.log.add(f"未命中！{card.name} 未能击中目标。")
            self.damage_result = DiceResult(total=0, rolls=[])
            self.last_damage_dealt = 0
            return self.dice_result

        self.damage_result = DiceEngine.roll_attack_damage(
            card.damage,
            self.dice_result.is_crit,
            self.player.str,
            self.player.dex,
        )

        base_damage = self.damage_result.total
        modified_damage = base_damage

        attack_results = self.event_bus.emit("on_calculate_attack",
                                              player=self.player,
                                              base_damage=base_damage)
        for result in attack_results:
            if isinstance(result, dict) and "effect" in result:
                effect = result["effect"]
                if "MultiplyDamage" in effect:
                    if self.player.hp < self.player.max_hp * 0.3:
                        modified_damage = int(modified_damage * effect["MultiplyDamage"])
                if "AddFlatDamage" in effect:
                    modified_damage += effect["AddFlatDamage"]

        actual_damage = self.enemy.take_damage(modified_damage)
        self.last_damage_dealt = actual_damage

        crit_text = " 暴击！" if self.dice_result.is_crit else ""
        hit_text = f"命中！{card.name} 造成 {actual_damage} 点伤害。{crit_text}"
        self.log.add(hit_text)

        return self.dice_result

    def _resolve_defense(self, card: Card) -> int:
        block_amount = card.block

        defense_results = self.event_bus.emit("on_calculate_defense",
                                              player=self.player,
                                              base_block=block_amount)
        for result in defense_results:
            if isinstance(result, dict) and "effect" in result:
                effect = result["effect"]
                if "AddFlat" in effect:
                    block_amount += effect["AddFlat"]

        self.player.gain_block(block_amount)
        self.log.add(f"获得 {block_amount} 格挡！")
        return block_amount

    def _resolve_keywords(self, card: Card, damage_dealt: int = 0) -> None:
        context = {
            "player": self.player,
            "enemy": self.enemy,
            "deck": self.deck,
            "card": card,
            "damage_dealt": damage_dealt,
            "event_bus": self.event_bus,
        }

        for keyword, value in card.keywords.items():
            if keyword in ("Exhaust", "Consume", "Repeat"):
                continue
            result = KeywordHandler.resolve(keyword, value, context)
            if result and "message" in result:
                self.log.add(result["message"])

    def end_player_turn(self) -> None:
        if not self.player_turn or self.battle_over:
            return

        self.deck.discard_hand()
        self.player.reset_block()

        self.player_turn = False
        self._enemy_actions_remaining = 2 if self.enemy.is_boss else 1
        self.log.add("玩家回合结束。")

    def execute_enemy_turn(self) -> bool:
        if self.player_turn or self.battle_over:
            return True

        if self._enemy_actions_remaining <= 0:
            self._finish_enemy_turn()
            return True

        if self.enemy.is_stunned():
            self.enemy.tick_stun()
            self.log.add(f"{self.enemy.name} 被眩晕了！")
            self._enemy_actions_remaining = 0
            self._finish_enemy_turn()
            return True

        action_card = self._select_enemy_action()
        if action_card:
            self._execute_enemy_action(action_card)

        self._enemy_actions_remaining -= 1

        if self.player.is_dead():
            self.battle_over = True
            self.player_won = False
            self.log.add("你死了……")
            return True

        if self._enemy_actions_remaining > 0:
            return False

        self._finish_enemy_turn()
        return True

    def _select_enemy_action(self) -> Card | None:
        if not self.enemy.card_pool or not self.data_loader:
            return None

        action_types = list(self.enemy.ai.keys())
        weights = list(self.enemy.ai.values())
        chosen_type = random.choices(action_types, weights=weights, k=1)[0]

        matching = []
        for card_id in self.enemy.card_pool:
            card = self.data_loader.create_card(card_id)
            if card is None:
                continue
            if chosen_type == "Attack" and card.is_attack():
                matching.append(card)
            elif chosen_type == "Defend" and card.is_skill() and card.block > 0:
                matching.append(card)
            elif chosen_type == "Special":
                matching.append(card)

        if matching:
            return random.choice(matching)
        elif self.enemy.card_pool:
            return self.data_loader.create_card(random.choice(self.enemy.card_pool))
        return None

    def _execute_enemy_action(self, card: Card) -> None:
        if card.is_attack() and card.damage != "0":
            damage_result = DiceEngine.parse_dice_notation(
                card.damage, self.enemy.str, self.enemy.dex
            )
            actual_damage = self.player.take_damage(damage_result.total)
            self.log.add(f"{self.enemy.name} 攻击造成 {actual_damage} 伤害！")
            self.dice_result = DiceResult(total=damage_result.total, rolls=damage_result.rolls)
            self.damage_result = damage_result

            context = {
                "player": self.player,
                "enemy": self.enemy,
                "deck": self.deck,
                "card": card,
                "damage_dealt": actual_damage,
                "event_bus": self.event_bus,
            }
            for keyword, value in card.keywords.items():
                KeywordHandler.resolve(keyword, value, context)

        elif card.block > 0:
            self.enemy.gain_block(card.block)
            self.log.add(f"{self.enemy.name} 获得 {card.block} 格挡！")

        else:
            context = {
                "player": self.player,
                "enemy": self.enemy,
                "deck": self.deck,
                "card": card,
                "damage_dealt": 0,
                "event_bus": self.event_bus,
            }
            for keyword, value in card.keywords.items():
                result = KeywordHandler.resolve(keyword, value, context)
                if result and "message" in result:
                    self.log.add(f"{self.enemy.name}: {result['message']}")

        self.event_bus.emit("on_enemy_action", player=self.player, enemy=self.enemy)

    def _finish_enemy_turn(self) -> None:
        self.enemy.reset_block()
        self.enemy.tick_vulnerable()

        if self.player.is_dead():
            self.battle_over = True
            self.player_won = False
            self.log.add("你死了……")
            return

        self.player.reset_block()
        self.player.reset_fp()
        self.deck.draw(5)
        self.enemy.set_intent(self._card_lookup)
        self.player_turn = True
        self.selected_card_index = 0
        self.log.add("你的回合！")

    def _on_victory(self) -> None:
        self.battle_over = True
        self.player_won = True
        self.player.souls += self.enemy.souls

        self.event_bus.emit("on_enemy_action", player=self.player, enemy=self.enemy)

        self.log.add(f"胜利！获得 {self.enemy.souls} 灵魂！")

    def select_card(self, direction: int) -> None:
        hand = self.deck.hand
        if not hand:
            return
        self.selected_card_index = (self.selected_card_index + direction) % len(hand)

    def get_souls_reward(self) -> int:
        return self.enemy.souls if self.player_won else 0
