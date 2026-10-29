"""GameOverScreen - death or victory screen with mouse support and Chinese text."""

from __future__ import annotations

import pygame

from screens.base_screen import BaseScreen
from services.renderer import Renderer


class GameOverScreen(BaseScreen):
    """Game over screen shown when the player dies or completes all acts."""

    def __init__(self) -> None:
        super().__init__()
        self._victory: bool = False
        self._options = ["再来一局", "返回主菜单", "退出游戏"]

    def on_enter(self, **kwargs) -> None:
        self._victory = kwargs.get("victory", False)
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
            self.game.input_handler.consume_click()
            self._check_hover(event.pos)
            self._confirm()
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
            self._selected_index = 1

    def _check_hover(self, pos: tuple[int, int]) -> None:
        """Check hover over options."""
        center_x = self.screen_width // 2
        options_y = self.screen_height - 200
        for i in range(len(self._options)):
            rect = pygame.Rect(center_x - 80, options_y + i * 40 - 2, 160, 36)
            if rect.collidepoint(pos):
                self._selected_index = i
                return

    def _confirm(self) -> None:
        if self._selected_index == 0:
            self.game.start_new_run()
        elif self._selected_index == 1:
            self.game.go_to_title()
        elif self._selected_index == 2:
            self.game.quit()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        r = self.renderer
        r.fill_bg()

        center_x = r.screen_width // 2

        if self._victory:
            r.draw_text("初火永不熄灭", center_x, 100, 32,
                        Renderer.COLOR_GOLD, center=True)
            r.draw_text("你已传承了初始之火。", center_x, 150, 16,
                        Renderer.COLOR_TEXT, center=True)
        else:
            r.draw_text("你死了", center_x, 100, 42,
                        Renderer.COLOR_ATTACK, center=True)
            r.draw_text("黑暗吞噬了一切……", center_x, 150, 16,
                        Renderer.COLOR_TEXT_DIM, center=True)

        # Final stats
        player = self.game.player
        stats_y = 220
        deck = player.deck
        card_count = len(deck.draw_pile) + len(deck.discard_pile) + len(deck.exhaust_pile) + len(deck.hand)
        stats = [
            f"到达关卡: 第{player.current_act}关",
            f"最终等级: {player.level}",
            f"力量:{player.str}  敏捷:{player.dex}  体力:{player.vit}  信仰:{player.fcs}",
            f"获得灵魂: {player.souls}",
            f"遗物数: {len(player.relics.relics)}",
            f"牌库大小: {card_count} 张",
        ]

        for i, stat in enumerate(stats):
            r.draw_text(stat, center_x, stats_y + i * 32, 13,
                        Renderer.COLOR_TEXT_DIM, center=True)

        # Options
        options_y = r.screen_height - 200
        self.draw_options(self._options, self._selected_index,
                         center_x - 80, options_y, 42, 16)

        # Footer
        self.draw_footer("方向键/鼠标: 选择 | 回车/点击: 确认")
