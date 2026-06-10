"""
签到历史面板
"""
import pygame
from .common import draw_rounded_rect, RARITY_COLORS, load_font


class HistoryPanel:
    """签到历史列表"""

    def __init__(self, qd):
        self.qd = qd
        self.scroll = 0
        self.font_lg = load_font(36)
        self.font_sm = load_font(18)
        self.font_xs = load_font(14)

    def draw(self, screen, width, height):
        PANEL_BG = (35, 35, 50)
        draw_rounded_rect(screen, PANEL_BG, (20, 20, width - 40, height - 40), 15)

        title = self.font_lg.render("签到历史", True, (255, 255, 255))
        screen.blit(title, (40, 35))

        headers = ["时间", "第N次", "连续", "概率", "结果", "奖励"]
        col_x = [40, 180, 250, 320, 400, 520]
        hy = 85
        for i, h in enumerate(headers):
            hs = self.font_sm.render(h, True, (150, 150, 170))
            screen.blit(hs, (col_x[i], hy))

        pygame.draw.line(screen, (60, 60, 80), (40, hy + 25), (width - 40, hy + 25), 1)

        y_start = hy + 30
        line_h = 28
        max_lines = (height - 120) // line_h
        history = list(reversed(self.qd.history))
        start_idx = self.scroll // line_h
        visible = min(max_lines, len(history) - start_idx)

        for i in range(visible):
            idx = start_idx + i
            if idx >= len(history):
                break
            h = history[idx]
            ly = y_start + i * line_h

            color = (200, 200, 200) if h.get("reinforced") else (130, 130, 140)
            if h.get("reinforced"):
                rarity = h.get("rarity", "普通")
                color = RARITY_COLORS.get(rarity, (200, 200, 200))

            if i % 2 == 0:
                pygame.draw.rect(screen, (40, 40, 55), (35, ly - 2, width - 70, line_h))

            vals = [
                h.get("time", "")[:16],
                str(h.get("n", "")),
                str(h.get("streak_c", "")),
                h.get("prob", ""),
                h.get("result", ""),
                h.get("reward", ""),
            ]
            for j, v in enumerate(vals):
                vs = self.font_xs.render(v, True, color)
                screen.blit(vs, (col_x[j], ly))

        close_hint = self.font_sm.render("H / ESC: 关闭历史", True, (100, 100, 120))
        screen.blit(close_hint, (width // 2 - close_hint.get_width() // 2, height - 45))

    def handle_scroll(self, y):
        self.scroll = max(0, self.scroll - y * 30)
