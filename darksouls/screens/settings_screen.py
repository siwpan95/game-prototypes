"""SettingsScreen - settings overlay with mouse support and Chinese text."""

from __future__ import annotations

import json
import os

import pygame

from screens.base_screen import BaseScreen
from services.renderer import Renderer


class SettingsScreen(BaseScreen):
    """Settings overlay screen accessible via Escape from any game screen."""

    SETTINGS_FILE = "settings.json"

    def __init__(self) -> None:
        super().__init__()
        self._options = [
            "音乐音量",
            "音效音量",
            "全屏模式",
            "返回游戏",
        ]
        self._music_volume: int = 70
        self._sfx_volume: int = 80
        self._fullscreen: bool = True
        self._adjusting: bool = False
        self._option_rects: list[pygame.Rect] = []
        self._panel_rect: pygame.Rect | None = None
        self._load_settings()

    def _load_settings(self) -> None:
        """Load settings from settings.json."""
        try:
            settings_path = os.path.join(self._get_base_path(), self.SETTINGS_FILE)
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    data = json.load(f)
                self._music_volume = data.get("music_volume", 70)
                self._sfx_volume = data.get("sfx_volume", 80)
                self._fullscreen = data.get("fullscreen", True)
        except (json.JSONDecodeError, IOError):
            pass

    def _save_settings(self) -> None:
        """Save current settings to settings.json."""
        try:
            settings_path = os.path.join(self._get_base_path(), self.SETTINGS_FILE)
            data = {
                "music_volume": self._music_volume,
                "sfx_volume": self._sfx_volume,
                "fullscreen": self._fullscreen,
            }
            with open(settings_path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    def _get_base_path(self) -> str:
        """Get the project base path."""
        if self.game and hasattr(self.game, "_base_path"):
            return self.game._base_path
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def on_enter(self, **kwargs) -> None:
        self._selected_index = 0
        self._adjusting = False

    def on_exit(self) -> None:
        self._save_settings()

    def handle_event(self, event) -> None:
        # Mouse hover
        if event.type == pygame.MOUSEMOTION:
            if not self._adjusting:
                self._check_hover(event.pos)
            return

        # Mouse click
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.game.input_handler.consume_click()
            if self._adjusting:
                # Click outside panel to stop adjusting
                if self._panel_rect and not self._panel_rect.collidepoint(event.pos):
                    self._adjusting = False
                    return
            else:
                self._check_hover(event.pos)
                if event.button == 1:
                    self._confirm()
                elif event.button == 3:
                    self.game.close_settings()
            return

        if event.type != pygame.KEYDOWN:
            return

        if self._adjusting:
            self._handle_adjusting(event)
            return

        if event.key == pygame.K_UP:
            self._selected_index = (self._selected_index - 1) % len(self._options)
        elif event.key == pygame.K_DOWN:
            self._selected_index = (self._selected_index + 1) % len(self._options)
        elif event.key == pygame.K_RETURN:
            self._confirm()
        elif event.key == pygame.K_ESCAPE:
            self.game.close_settings()

    def _check_hover(self, pos: tuple[int, int]) -> None:
        """Check hover over options."""
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos):
                self._selected_index = i
                return

    def _handle_adjusting(self, event) -> None:
        """Handle input while adjusting a setting value."""
        if event.key == pygame.K_LEFT:
            if self._selected_index == 0:
                self._music_volume = max(0, self._music_volume - 10)
            elif self._selected_index == 1:
                self._sfx_volume = max(0, self._sfx_volume - 10)
        elif event.key == pygame.K_RIGHT:
            if self._selected_index == 0:
                self._music_volume = min(100, self._music_volume + 10)
            elif self._selected_index == 1:
                self._sfx_volume = min(100, self._sfx_volume + 10)
        elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self._adjusting = False

    def _confirm(self) -> None:
        """Confirm the selected option."""
        if self._selected_index == 0:
            self._adjusting = True
        elif self._selected_index == 1:
            self._adjusting = True
        elif self._selected_index == 2:
            self._fullscreen = not self._fullscreen
            self._apply_fullscreen()
        elif self._selected_index == 3:
            self.game.close_settings()

    def _apply_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self.game:
            self.game.toggle_fullscreen(self._fullscreen)
        self._save_settings()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        r = self.renderer

        # Semi-transparent overlay
        overlay = pygame.Surface((r.screen_width, r.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, (0, 0))

        # Settings panel
        panel_w = 420
        panel_h = 320
        px = r.center_x(panel_w)
        py = r.center_y(panel_h)

        self._panel_rect = pygame.Rect(px, py, panel_w, panel_h)
        r.draw_rect(px, py, panel_w, panel_h, Renderer.COLOR_PANEL, border_radius=8)
        r.draw_text("游戏设置", px + panel_w // 2, py + 15, 20,
                    Renderer.COLOR_TEXT, center=True)

        # Options
        options_y = py + 60
        spacing = 55
        self._option_rects.clear()

        for i, option in enumerate(self._options):
            y = options_y + i * spacing
            is_selected = (i == self._selected_index)
            color = Renderer.COLOR_GOLD if is_selected else Renderer.COLOR_TEXT
            prefix = "> " if is_selected else "  "

            if i == 0:
                bar_text = f"{prefix}{option}: {self._music_volume}%"
                r.draw_text(bar_text, px + 20, y, 15, color)
                bar_x, bar_y = px + 20, y + 22
                bar_w = panel_w - 40
                r.draw_bar(bar_x, bar_y, bar_w, 10, self._music_volume, 100,
                          Renderer.COLOR_FP_BAR, Renderer.COLOR_FP_BAR_BG)
                if self._adjusting and i == self._selected_index:
                    r.draw_text("[调整中: 左右方向键]", px + panel_w // 2, bar_y + 14, 10,
                                Renderer.COLOR_GOLD, center=True)
                self._option_rects.append(pygame.Rect(px + 10, y - 4, panel_w - 20, 40))

            elif i == 1:
                bar_text = f"{prefix}{option}: {self._sfx_volume}%"
                r.draw_text(bar_text, px + 20, y, 15, color)
                bar_x, bar_y = px + 20, y + 22
                bar_w = panel_w - 40
                r.draw_bar(bar_x, bar_y, bar_w, 10, self._sfx_volume, 100,
                          Renderer.COLOR_GREEN, (20, 40, 20))
                if self._adjusting and i == self._selected_index:
                    r.draw_text("[调整中: 左右方向键]", px + panel_w // 2, bar_y + 14, 10,
                                Renderer.COLOR_GOLD, center=True)
                self._option_rects.append(pygame.Rect(px + 10, y - 4, panel_w - 20, 40))

            elif i == 2:
                state = "开启" if self._fullscreen else "关闭"
                r.draw_text(f"{prefix}{option}: {state}", px + 20, y, 15, color)
                self._option_rects.append(pygame.Rect(px + 10, y - 4, panel_w - 20, 30))

            else:
                r.draw_text(f"{prefix}{option}", px + 20, y, 15, color)
                self._option_rects.append(pygame.Rect(px + 10, y - 4, panel_w - 20, 30))
