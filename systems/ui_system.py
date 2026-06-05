"""
UI 系统 — 理智条 + 坐标 HUD + 记忆弹出 + 卡牌 Toast + 游戏结束/胜利画面
============================================================
"""
import pygame
from core.ecs import System
from core.config import COLS, CELL, WINDOW_W
from components.sanity import Sanity
from components.grid_position import GridPosition
from core.utils import _load_font




class UISystem(System):
    """屏幕 UI 渲染：理智条 + 记忆文本弹出 + 卡牌收集提示 + 游戏结束/胜利"""

    FADE_DURATION = 4000
    TOAST_DURATION = 2000

    def __init__(self, screen, event_bus):
        self.screen = screen
        self.bus = event_bus
        self.font_label = _load_font(15)
        self.font_text = _load_font(16)
        self.font_title = _load_font(12)
        self.font_toast = _load_font(14)
        self.font_big = _load_font(32, bold=True)
        self.font_mid = _load_font(18)
        self.font_coord = _load_font(13)      # 坐标 HUD 字体
        self.font_mapname = _load_font(11)    # 地图名 HUD 字体

        # 记忆文本弹出
        self.popup_text = ""
        self.popup_name = ""
        self.popup_elapsed = 0.0
        self.popup_visible = False

        # 卡牌收集 Toast
        self.toast_text = ""
        self.toast_elapsed = 0.0
        self.toast_visible = False

        # 机关触发提示
        self.mechanism_text = ""
        self.mechanism_elapsed = 0.0
        self.mechanism_visible = False

        # 理智恢复提示
        self.recovery_text = ""
        self.recovery_elapsed = 0.0
        self.recovery_visible = False

        # 游戏状态
        self.game_over = False
        self.game_won = False
        self.game_over_reason = ""

        # 坐标 HUD
        self.current_map_name = ""   # 当前地图名（由 MAP_LOADED 更新）
        self.current_mod_id = ""     # 当前 Mod ID（base/dlc_forest/...）

        # 事件订阅
        self.bus.subscribe("MEMORY_TRIGGERED", self._on_memory_triggered)
        self.bus.subscribe("CARD_COLLECTED", self._on_card_collected)
        self.bus.subscribe("SANITY_RECOVER", self._on_sanity_recover)
        self.bus.subscribe("GAME_OVER", self._on_game_over)
        self.bus.subscribe("GAME_WIN", self._on_game_win)
        self.bus.subscribe("MAP_LOADED", self._on_map_loaded)

    def _on_memory_triggered(self, data):
        self.popup_text = data["text"]
        self.popup_name = data.get("name", "")
        self.popup_elapsed = 0.0
        self.popup_visible = True

    def _on_card_collected(self, data):
        self.toast_text = f"获得卡牌：{data['name']} {data['glyph']}"
        self.toast_elapsed = 0.0
        self.toast_visible = True

    def _on_sanity_recover(self, data):
        amount = data.get("amount", 0)
        self.recovery_text = f"理智恢复 +{amount}"
        self.recovery_elapsed = 0.0
        self.recovery_visible = True

    def _on_game_over(self, data):
        self.game_over = True
        self.game_over_reason = data.get("reason", "")

    def _on_game_win(self, data):
        self.game_won = True

    def _on_map_loaded(self, data):
        self.current_map_name = data.get("map_name", "")
        self.current_mod_id = data.get("mod_id", "") or "base"

    def show_mechanism_text(self, text):
        """外部调用 — 显示机关触发提示。"""
        self.mechanism_text = text
        self.mechanism_elapsed = 0.0
        self.mechanism_visible = True

    def show_toast(self, text):
        """外部调用 — 显示通用 Toast 提示（如地图切换）。"""
        self.toast_text = text
        self.toast_elapsed = 0.0
        self.toast_visible = True

    def update(self, world, dt):
        if self.game_over:
            self._render_game_over(dt)
            return
        if self.game_won:
            self._render_game_win(dt)
            return

        self._render_sanity_bar(world)
        self._render_title()
        self._render_coord_hud(world)
        self._render_memory_popup(dt)
        self._render_card_toast(dt)
        self._render_mechanism_popup(dt)
        self._render_recovery_toast(dt)

    # ---- 理智条 ----
    def _render_sanity_bar(self, world):
        player = world.entities.get("player")
        if not player:
            return
        s = player.get(Sanity)
        if not s:
            return

        bar_x, bar_y = 10, 8
        bar_w, bar_h = 140, 16
        ratio = s.value / s.max_value

        bg_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(self.screen, (20, 18, 25), bg_rect)
        pygame.draw.rect(self.screen, (50, 45, 55), bg_rect, 1)

        if ratio > 0.5:
            t = (1.0 - ratio) * 2
            color = (60 + int(t * 200), 200 - int(t * 60), 60 - int(t * 30))
        else:
            t = ratio * 2
            color = (220 - int(t * 60), 140 - int(t * 80), 30 + int(t * 20))

        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            fill_rect = pygame.Rect(bar_x, bar_y, fill_w, bar_h)
            pygame.draw.rect(self.screen, color, fill_rect)

        label = self.font_label.render("理智", True, (180, 175, 165))
        self.screen.blit(label, (bar_x + 2, bar_y))
        val_text = self.font_title.render(f"{s.value}/{s.max_value}", True, (140, 135, 125))
        self.screen.blit(val_text, (bar_x + bar_w + 4, bar_y + 1))

    # ---- 标题 ----
    def _render_title(self):
        title = self.font_title.render(
            "卡瑞玛拉：枯肢之下", True, (100, 95, 110)
        )
        sh = self.screen.get_height()
        self.screen.blit(title, (10, sh - 18))

    # ---- 坐标 HUD ----
    def _render_coord_hud(self, world):
        """在理智条下方显示玩家坐标和当前地图名。"""
        player = world.entities.get("player")
        if not player:
            return
        gp = player.get(GridPosition)
        if not gp:
            return

        # 坐标文本
        coord_text = f"({gp.col}, {gp.row})"
        coord_surf = self.font_coord.render(coord_text, True, (140, 160, 180))

        # 地图名文本
        map_label = self.current_map_name or "???"
        if self.current_mod_id and self.current_mod_id != "base":
            map_label = f"[{self.current_mod_id}] {self.current_map_name or '???'}"
        map_surf = self.font_mapname.render(map_label, True, (110, 120, 130))

        # 背景面板 — 理智条右边
        bar_x, bar_y = 10, 8
        bar_w, bar_h = 140, 16

        # 坐标放在理智条右侧水平
        coord_x = bar_x + bar_w + 70
        coord_y = bar_y
        self.screen.blit(coord_surf, (coord_x, coord_y))

        # 地图名放在理智条左下方
        map_x = bar_x + 2
        map_y = bar_y + bar_h + 2
        self.screen.blit(map_surf, (map_x, map_y))

    # ---- 记忆文本弹出 ----
    def _render_memory_popup(self, dt):
        if not self.popup_visible:
            return
        self.popup_elapsed += dt
        if self.popup_elapsed > self.FADE_DURATION:
            self.popup_visible = False
            return

        progress = self.popup_elapsed / self.FADE_DURATION
        if progress < 0.1:
            alpha = int(255 * progress / 0.1)
        elif progress > 0.7:
            alpha = int(255 * (1.0 - progress) / 0.3)
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))

        sh = self.screen.get_height()
        game_w = COLS * CELL

        lines = self._wrap_text(self.popup_text, self.font_text, game_w - 80)
        name_surf = self.font_title.render(self.popup_name, True, (160, 140, 120))
        text_surfs = [self.font_text.render(line, True, (210, 200, 190)) for line in lines]
        total_h = name_surf.get_height() + sum(s.get_height() + 5 for s in text_surfs)

        panel_w = max(name_surf.get_width(), max(s.get_width() for s in text_surfs)) + 32
        panel_h = total_h + 20
        # 限制弹出窗口高度，避免覆盖底部标题
        max_panel_h = sh - 60  # 给底部标题留 20px + 缓冲
        if panel_h > max_panel_h:
            panel_h = max_panel_h
        panel_x = (game_w - panel_w) // 2
        panel_y = max(10, sh - panel_h - 26)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((12, 10, 8, min(220, alpha)))
        pygame.draw.rect(panel, (50, 40, 35, alpha), panel.get_rect(), 1)
        self.screen.blit(panel, (panel_x, panel_y))

        y_off = panel_y + 10
        ns = name_surf.copy()
        ns.set_alpha(alpha)
        self.screen.blit(ns, (panel_x + 16, y_off))
        y_off += name_surf.get_height() + 6
        for srf in text_surfs:
            s = srf.copy()
            s.set_alpha(alpha)
            self.screen.blit(s, (panel_x + 16, y_off))
            y_off += srf.get_height() + 5

    # ---- 卡牌收集 Toast ----
    def _render_card_toast(self, dt):
        if not self.toast_visible:
            return
        self.toast_elapsed += dt
        if self.toast_elapsed > self.TOAST_DURATION:
            self.toast_visible = False
            return

        progress = self.toast_elapsed / self.TOAST_DURATION
        alpha = int(255 * (1.0 - progress * progress))
        alpha = max(0, min(255, alpha))

        surf = self.font_toast.render(self.toast_text, True, (200, 220, 180))
        surf.set_alpha(alpha)
        sw = COLS * CELL
        self.screen.blit(surf, ((sw - surf.get_width()) // 2, 30))

    # ---- 理智恢复 Toast ----
    def _render_recovery_toast(self, dt):
        if not self.recovery_visible:
            return
        self.recovery_elapsed += dt
        if self.recovery_elapsed > self.TOAST_DURATION:
            self.recovery_visible = False
            return

        progress = self.recovery_elapsed / self.TOAST_DURATION
        alpha = int(255 * (1.0 - progress * progress))
        alpha = max(0, min(255, alpha))

        surf = self.font_toast.render(self.recovery_text, True, (100, 220, 140))
        surf.set_alpha(alpha)
        sw = COLS * CELL
        self.screen.blit(surf, ((sw - surf.get_width()) // 2, 50))

    # ---- 机关触发弹出 ----
    def _render_mechanism_popup(self, dt):
        if not self.mechanism_visible:
            return
        self.mechanism_elapsed += dt
        if self.mechanism_elapsed > self.FADE_DURATION:
            self.mechanism_visible = False
            return

        progress = self.mechanism_elapsed / self.FADE_DURATION
        if progress < 0.1:
            alpha = int(255 * progress / 0.1)
        elif progress > 0.7:
            alpha = int(255 * (1.0 - progress) / 0.3)
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))

        game_w = COLS * CELL
        lines = self._wrap_text(self.mechanism_text, self.font_text, game_w - 80)
        text_surfs = [self.font_text.render(line, True, (255, 220, 140)) for line in lines]
        total_h = sum(s.get_height() + 5 for s in text_surfs)
        panel_w = min(game_w - 40, max(s.get_width() for s in text_surfs) + 32)
        panel_h = total_h + 16
        panel_x = (game_w - panel_w) // 2
        panel_y = 40

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((20, 15, 8, min(200, alpha)))
        pygame.draw.rect(panel, (80, 60, 20, alpha), panel.get_rect(), 1)
        self.screen.blit(panel, (panel_x, panel_y))

        y_off = panel_y + 8
        for srf in text_surfs:
            s = srf.copy()
            s.set_alpha(alpha)
            self.screen.blit(s, (panel_x + 16, y_off))
            y_off += srf.get_height() + 5

    # ---- 游戏结束画面 ----
    def _render_game_over(self, dt):
        sw, sh = self.screen.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((5, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        title = self.font_big.render("理智崩溃", True, (180, 30, 30))
        self.screen.blit(title, ((sw - title.get_width()) // 2, sh // 2 - 60))

        desc = self.font_mid.render(
            "你丧失了最后的一丝清醒，永远迷失在这座宅邸之中……",
            True, (140, 80, 80),
        )
        self.screen.blit(desc, ((sw - desc.get_width()) // 2, sh // 2))

        hint = self.font_text.render("按 R 重新开始  ·  按 Q 退出", True, (100, 90, 90))
        self.screen.blit(hint, ((sw - hint.get_width()) // 2, sh // 2 + 50))

    # ---- 胜利画面 ----
    def _render_game_win(self, dt):
        sw, sh = self.screen.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 5, 15, 200))
        self.screen.blit(overlay, (0, 0))

        title = self.font_big.render("真相大白", True, (220, 200, 140))
        self.screen.blit(title, ((sw - title.get_width()) // 2, sh // 2 - 60))

        desc = self.font_mid.render(
            "你收集了所有卡牌，拼凑出完整的真相。宅邸的低语终于平息。",
            True, (180, 170, 140),
        )
        self.screen.blit(desc, ((sw - desc.get_width()) // 2, sh // 2))

        hint = self.font_text.render("按 R 重新开始  ·  按 Q 退出", True, (100, 100, 90))
        self.screen.blit(hint, ((sw - hint.get_width()) // 2, sh // 2 + 50))

    # ---- 工具方法 ----
    @staticmethod
    def _wrap_text(text, font, max_width):
        lines = []
        current = ""
        for ch in text:
            test = current + ch
            if font.size(test)[0] > max_width:
                lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
        return lines
