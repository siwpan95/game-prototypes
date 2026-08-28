"""
统计面板 — GitHub 式签到热力图 + 数据统计 + 成就墙
按 S 打开/关闭
"""
from datetime import date, timedelta
import pygame
from .common import draw_rounded_rect, RARITY_COLORS, load_font
from core.achievements import all_milestones


class StatsPanel:
    """签到数据可视化"""

    WEEKS = 20  # 热力图显示最近 20 周

    def __init__(self, qd):
        self.qd = qd
        self.font_lg = load_font(36)
        self.font_md = load_font(24)
        self.font_sm = load_font(18)
        self.font_xs = load_font(14)

    def draw(self, screen, width, height):
        PANEL_BG = (35, 35, 50)
        draw_rounded_rect(screen, PANEL_BG, (20, 20, width - 40, height - 40), 15)

        title = self.font_lg.render("签到统计", True, (255, 255, 255))
        screen.blit(title, (40, 35))

        stats = self.qd.get_stats()

        # ── 顶部数据卡片 ──
        cards = [
            ("总签到", f"{stats['n']}", (120, 200, 255)),
            ("当前连胜", f"{stats['c']}天", (120, 255, 160)),
            ("最长连胜", f"{stats['best_c']}天", (255, 210, 100)),
            ("获奖次数", f"{stats['reward_count']}", (255, 160, 220)),
            ("获奖率", f"{stats['reward_rate']:.0%}", (200, 160, 255)),
            ("冻结卡", f"{stats['freezes']}", (140, 210, 255)),
        ]
        card_w = (width - 80 - 5 * 12) // 6
        cy = 90
        for i, (label, value, color) in enumerate(cards):
            cx0 = 40 + i * (card_w + 12)
            draw_rounded_rect(screen, (45, 45, 62), (cx0, cy, card_w, 68), 10)
            vs = self.font_md.render(value, True, color)
            screen.blit(vs, (cx0 + card_w // 2 - vs.get_width() // 2, cy + 10))
            ls = self.font_xs.render(label, True, (150, 150, 170))
            screen.blit(ls, (cx0 + card_w // 2 - ls.get_width() // 2, cy + 42))

        # ── 热力图 ──
        hy = 185
        hm_title = self.font_sm.render(f"最近 {self.WEEKS} 周签到热力图", True, (180, 180, 200))
        screen.blit(hm_title, (40, hy))
        hy += 30
        self._draw_heatmap(screen, 40, hy, width - 80)

        # ── 稀有度分布 ──
        ry = hy + 7 * 18 + 30
        rd_title = self.font_sm.render("奖励稀有度分布", True, (180, 180, 200))
        screen.blit(rd_title, (40, ry))
        ry += 28
        dist = stats["rarity_dist"]
        total = max(1, sum(dist.values()))
        bx = 40
        for rarity in ("普通", "稀有", "史诗", "传说", "神话"):
            count = dist.get(rarity, 0)
            color = RARITY_COLORS.get(rarity, (180, 180, 180))
            bar_w = int(140 * count / total) if total else 0
            label = self.font_xs.render(f"{rarity} x{count}", True, color)
            screen.blit(label, (bx, ry))
            pygame.draw.rect(screen, (50, 50, 65), (bx, ry + 20, 140, 8), border_radius=4)
            if bar_w > 0:
                pygame.draw.rect(screen, color, (bx, ry + 20, max(4, bar_w), 8), border_radius=4)
            bx += 170

        # ── 成就墙 ──
        ay = ry + 50
        ach_title = self.font_sm.render(
            f"成就 ({stats['milestones_unlocked']}/{len(all_milestones())})",
            True, (180, 180, 200))
        screen.blit(ach_title, (40, ay))
        ay += 28
        ax = 40
        for ms in all_milestones():
            unlocked = ms["id"] in self.qd.milestones
            box_w = 176
            color = (255, 210, 100) if unlocked else (70, 70, 88)
            text_color = (255, 225, 150) if unlocked else (110, 110, 130)
            draw_rounded_rect(screen, (48, 45, 35) if unlocked else (40, 40, 54),
                              (ax, ay, box_w, 44), 8)
            draw_rounded_rect(screen, color, (ax, ay, box_w, 44), 8, 1)
            icon = "★" if unlocked else "☆"
            ts = self.font_xs.render(f"{icon} {ms['title']}", True, text_color)
            screen.blit(ts, (ax + 10, ay + 5))
            ds = self.font_xs.render(ms["desc"][:14], True,
                                     (170, 160, 120) if unlocked else (90, 90, 108))
            screen.blit(ds, (ax + 10, ay + 24))
            ax += box_w + 10
            if ax + box_w > width - 40:
                ax = 40
                ay += 52

        close_hint = self.font_sm.render("S / ESC: 关闭统计", True, (100, 100, 120))
        screen.blit(close_hint, (width // 2 - close_hint.get_width() // 2, height - 45))

    def _draw_heatmap(self, screen, x, y, w):
        """GitHub 式热力图：列=周，行=周一到周日"""
        sign_dates = self.qd.sign_dates()
        # 有奖励的日期（金色高亮）
        reward_dates = set()
        for h in self.qd.history:
            if h.get("reinforced") and len(h.get("time", "")) >= 10:
                reward_dates.add(h["time"][:10])

        today = date.today()
        # 本周一
        this_monday = today - timedelta(days=today.weekday())
        start_monday = this_monday - timedelta(weeks=self.WEEKS - 1)

        cell = 14
        gap = 4
        # 行标签
        for i, wd in enumerate(("一", "三", "五", "日")):
            row = (0, 2, 4, 6)[i]
            ls = self.font_xs.render(wd, True, (110, 110, 130))
            screen.blit(ls, (x, y + row * (cell + gap) - 1))

        gx = x + 24
        month_drawn = set()
        for week in range(self.WEEKS):
            monday = start_monday + timedelta(weeks=week)
            # 月份标签
            if monday.day <= 7 and monday.month not in month_drawn:
                month_drawn.add(monday.month)
                ms = self.font_xs.render(f"{monday.month}月", True, (110, 110, 130))
                screen.blit(ms, (gx + week * (cell + gap), y - 18))
            for wd in range(7):
                d = monday + timedelta(days=wd)
                if d > today:
                    continue
                key = d.isoformat()
                if key in reward_dates:
                    color = (255, 200, 80)      # 有奖励 → 金色
                elif key in sign_dates:
                    color = (80, 200, 120)      # 签到无奖励 → 绿色
                else:
                    color = (48, 48, 62)        # 未签到 → 暗格
                rx = gx + week * (cell + gap)
                ry = y + wd * (cell + gap)
                pygame.draw.rect(screen, color, (rx, ry, cell, cell), border_radius=3)
                if key == today.isoformat():
                    pygame.draw.rect(screen, (255, 255, 255), (rx, ry, cell, cell), 1,
                                     border_radius=3)

        # 图例
        ly = y + 7 * (cell + gap) + 6
        legend = [((48, 48, 62), "未签"), ((80, 200, 120), "已签"), ((255, 200, 80), "获奖")]
        lx = gx
        for color, label in legend:
            pygame.draw.rect(screen, color, (lx, ly, cell, cell), border_radius=3)
            ls = self.font_xs.render(label, True, (140, 140, 160))
            screen.blit(ls, (lx + cell + 5, ly - 1))
            lx += 80
