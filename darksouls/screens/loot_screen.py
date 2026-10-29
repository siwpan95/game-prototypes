"""LootScreen - card selection UI with mouse support and Chinese text."""

from __future__ import annotations

import random

import pygame

from screens.base_screen import BaseScreen
from services.renderer import Renderer
from models.card import Card


class LootScreen(BaseScreen):
    """Loot selection screen shown after winning a battle."""

    def __init__(self) -> None:
        super().__init__()
        self._loot_cards: list[Card] = []
        self._selected_index: int = 0
        self._souls_reward: int = 0
        self._card_rects: list[pygame.Rect] = []

    def on_enter(self, **kwargs) -> None:
        self._souls_reward = kwargs.get("souls_reward", 0)
        self._selected_index = 0

        self._loot_cards.clear()
        all_player_cards = self.game.data_loader.get_loot_cards()
        if all_player_cards:
            sample_size = min(3, len(all_player_cards))
            sampled = random.sample(all_player_cards, sample_size)
            for card_data in sampled:
                card = self.game.data_loader.create_card(card_data["id"])
                if card:
                    self._loot_cards.append(card)

        if not self._loot_cards:
            self._loot_cards = []

    def on_exit(self) -> None:
        self._loot_cards.clear()

    def handle_event(self, event) -> None:
        if not self._loot_cards:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.game.input_handler.consume_click()
                self.game.return_to_map()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self.game.return_to_map()
            return

        # Mouse hover
        if event.type == pygame.MOUSEMOTION:
            self._check_card_hover(event.pos)
            return

        # Mouse click
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.game.input_handler.consume_click()
            self._check_card_hover(event.pos)
            self._pick_card()
            return

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_LEFT:
            self._selected_index = (self._selected_index - 1) % len(self._loot_cards)
        elif event.key == pygame.K_RIGHT:
            self._selected_index = (self._selected_index + 1) % len(self._loot_cards)
        elif event.key == pygame.K_RETURN:
            self._pick_card()
        elif event.key == pygame.K_ESCAPE:
            self.game.return_to_map()

    def _check_card_hover(self, pos: tuple[int, int]) -> None:
        """Check hover over cards."""
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos):
                self._selected_index = i
                return

    def _pick_card(self) -> None:
        """Add the selected card to the player's deck."""
        if self._selected_index < len(self._loot_cards):
            card = self._loot_cards[self._selected_index]
            self.game.player.deck.add_card(card)
        self.game.return_to_map()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        r = self.renderer
        r.fill_bg()

        # Header
        self.draw_header("胜利！选择一张卡牌")

        # Souls reward
        r.draw_text(f"+{self._souls_reward} 灵魂", r.screen_width // 2, 65, 18,
                    Renderer.COLOR_GOLD, center=True)

        # Loot cards
        self._card_rects.clear()
        if self._loot_cards:
            card_w = 160
            card_h = 200
            spacing = 30
            total_w = len(self._loot_cards) * (card_w + spacing) - spacing
            start_x = r.center_x(total_w)
            card_y = 120

            for i, card in enumerate(self._loot_cards):
                x = start_x + i * (card_w + spacing)
                is_selected = (i == self._selected_index)
                r.draw_card(x, card_y, card_w, card_h, card, selected=is_selected)
                self._card_rects.append(pygame.Rect(x, card_y, card_w, card_h))

                if is_selected:
                    r.draw_text("[已选中]", x + card_w // 2, card_y + card_h + 10, 12,
                                Renderer.COLOR_GOLD, center=True)
        else:
            r.draw_text("没有可用的卡牌", r.screen_width // 2, 150, 16,
                        Renderer.COLOR_TEXT_DIM, center=True)

        # Instructions
        r.draw_text("左右键/鼠标: 浏览 | 回车/点击: 拾取 | Esc: 跳过",
                    r.screen_width // 2, r.screen_height - 60, 12,
                    Renderer.COLOR_TEXT_DIM, center=True)

        # Current deck size
        deck = self.game.player.deck
        card_count = deck.draw_pile_size + deck.discard_pile_size + deck.exhaust_pile_size + deck.hand_size
        r.draw_text(f"牌库: {card_count} 张卡牌",
                    r.screen_width // 2, r.screen_height - 40, 12,
                    Renderer.COLOR_TEXT_DIM, center=True)
