"""TitleScreen - the game's title/start screen, with Chinese UI and mouse support."""

from __future__ import annotations

import pygame

from screens.base_screen import BaseScreen
from services.renderer import Renderer


class TitleScreen(BaseScreen):
    """Title screen with game name and start/options prompts."""

    def __init__(self) -> None:
        super().__init__()
        self._selected_index = 0
        self._options = ["开始游戏", "游戏设置", "退出游戏"]

    def on_enter(self, **kwargs) -> None:
        self._selected_index = 0

    def on_exit(self) -> None:
        pass

    def handle_event(self, event) -> None:
        # Mouse hover
        if event.type == pygame.MOUSEMOTION:
            self._check_hover(event.pos)
            return

        # Mouse click
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._check_hover(event.pos)
            self._confirm()
            self.game.input_handler.consume_click()
            return

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_UP:
            self._selected_index = (self._selected_index - 1) % len(self._options)
        elif event.key == pygame.K_DOWN:
            self._selected_index = (self._selected_index + 1) % len(self._options)
        elif event.key == pygame.K_RETURN:
            self._confirm()
        elif event.key == pygame.K_ESCAPE:
            self._selected_index = len(self._options) - 1  # Select Quit

    def _check_hover(self, pos: tuple[int, int]) -> None:
        """Check if mouse is hovering over an option."""
        options_y = self.screen_height // 2 + 40
        x = self.screen_width // 2 - 80
        for i in range(len(self._options)):
            rect = pygame.Rect(x - 10, options_y + i * 50 - 2, 300, 46)
            if rect.collidepoint(pos):
                self._selected_index = i
                return

    def _confirm(self) -> None:
        if self._selected_index == 0:
            # Start Game
            self.game.start_new_run()
        elif self._selected_index == 1:
            # Settings
            self.game.open_settings()
        elif self._selected_index == 2:
            # Quit
            self.game.quit()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        r = self.renderer
        r.fill_bg()

        # Title
        title_y = r.screen_height // 4
        r.draw_text("黑暗之魂", r.screen_width // 2, title_y, 36,
                    Renderer.COLOR_TEXT, center=True)
        r.draw_text("卡牌编年史", r.screen_width // 2, title_y + 48, 24,
                    Renderer.COLOR_TEXT_DIM, center=True)

        # Subtitle
        r.draw_text("Roguelike 卡牌游戏", r.screen_width // 2, title_y + 90, 14,
                    Renderer.COLOR_TEXT_DIM, center=True)

        # Options
        options_y = r.screen_height // 2 + 40
        self.draw_options(self._options, self._selected_index,
                         r.screen_width // 2 - 80, options_y, 50, 18)

        # Controls hint
        hint_text = "方向键/鼠标: 选择 | 回车/点击: 确认 | Esc: 返回"
        r.draw_text(hint_text, r.screen_width // 2, r.screen_height - 40, 12,
                    Renderer.COLOR_TEXT_DIM, center=True)
