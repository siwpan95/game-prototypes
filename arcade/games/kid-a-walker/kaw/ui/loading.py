# -*- coding: utf-8 -*-
"""开始界面 / 加载进度界面。"""
import math

import pygame

# ─────────────────────── 预加载界面 ─────────────────────────
class LoadingScreen:
    """开始界面 + 预加载进度界面"""

    TIPS = [
        "探索无限的世界，发现不同的区域类型...",
        "按 WASD 或方向键移动，Tab 查看大地图",
        "每个区域都有独特的音效氛围",
        "世界是随机生成的，每次都是新旅程",
        "寻找安全的路径，避开死胡同",
    ]

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()
        try:
            self.font_title: pygame.font.Font = pygame.font.SysFont("Courier New", 72, bold=True)
            self.font_sub: pygame.font.Font = pygame.font.SysFont("Courier New", 24, bold=True)
            self.font_tip: pygame.font.Font = pygame.font.SysFont("Courier New", 16)
            self.font_progress: pygame.font.Font = pygame.font.SysFont("Courier New", 18)
        except Exception:
            self.font_title = pygame.font.Font(None, 100)
            self.font_sub = pygame.font.Font(None, 32)
            self.font_tip = pygame.font.Font(None, 22)
            self.font_progress = pygame.font.Font(None, 24)
        self.tip_idx = 0
        self.tip_timer = 0
        self.phase = "start"  # "start" | "loading"
        self.progress = 0.0
        self.status_text = ""
        self._animate = 0.0
        self._bg_parts: list[tuple[int, int, float, float, int]] | None = None

    def update_progress(self, progress: float, status: str = "") -> None:
        """更新加载进度，0.0 ~ 1.0"""
        self.progress = max(0.0, min(1.0, progress))
        self.status_text = status
        self._draw_loading_screen()
        pygame.display.flip()

    def _draw_start_screen(self) -> None:
        W, H = self.screen.get_size()
        self.screen.fill((5, 5, 15))

        # 动态背景粒子效果
        self._draw_bg_particles_start()

        # 标题
        title = self.font_title.render("KID-A WALKER", True, (0, 255, 200))
        title_shadow = self.font_title.render("KID-A WALKER", True, (0, 150, 120))
        tx = W // 2 - title.get_width() // 2
        ty = H // 3 - title.get_height() // 2
        self.screen.blit(title_shadow, (tx + 3, ty + 3))
        self.screen.blit(title, (tx, ty))

        # 副标题
        sub = self.font_sub.render("[ INFINITE WORLD ]", True, (100, 200, 255))
        sx = W // 2 - sub.get_width() // 2
        self.screen.blit(sub, (sx, ty + title.get_height() + 15))

        # 旋转提示（动画）
        pulse = abs(math.sin(self._animate * 2.0))
        hint_col = (int(150 + 105 * pulse), int(200 + 55 * pulse), int(255))
        hint = self.font_sub.render("— PRESS ANY KEY TO START —", True, hint_col)
        hx = W // 2 - hint.get_width() // 2
        hy = H * 2 // 3
        self.screen.blit(hint, (hx, hy))

        # 底部提示
        self.tip_timer += self.clock.get_rawtime()
        if self.tip_timer > 4000:
            self.tip_timer = 0
            self.tip_idx = (self.tip_idx + 1) % len(self.TIPS)
        tip = self.font_tip.render(self.TIPS[self.tip_idx], True, (100, 100, 130))
        tip_x = W // 2 - tip.get_width() // 2
        self.screen.blit(tip, (tip_x, H - 50))

        # 版本信息
        ver = self.font_tip.render("v1.0 | Procedural Exploration", True, (60, 60, 80))
        self.screen.blit(ver, (10, H - 30))

    def _draw_bg_particles_start(self) -> None:
        """开始界面的装饰粒子"""
        import random
        particles = getattr(self, '_bg_parts', None)
        if particles is None:
            self._bg_parts = [
                (random.randint(0, 800), random.randint(0, 600),
                 random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                 random.randint(2, 5))
                for _ in range(40)
            ]
            particles = self._bg_parts

        W, H = self.screen.get_size()
        if particles is None:
            return
        new_parts: list[tuple[int, int, float, float, int]] = []
        for i, (x, y, vx, vy, r) in enumerate(particles):
            x_new = (x + vx) % W
            y_new = (y + vy) % H
            alpha = int(80 + 40 * math.sin(self._animate + i))
            col = (0, 180 + int(75 * math.sin(self._animate * 0.7 + i)), 150)
            pygame.draw.circle(self.screen, col, (int(x_new), int(y_new)), r)
            new_parts.append((int(x_new), int(y_new), vx, vy, r))
        self._bg_parts = new_parts

    def _draw_loading_screen(self) -> None:
        W, H = self.screen.get_size()
        self.screen.fill((5, 5, 15))

        # 顶部装饰线
        for i in range(0, W, 8):
            alpha = int(30 * math.sin(i * 0.02 + self._animate))
            if alpha > 0:
                pygame.draw.line(self.screen, (0, 200, 150, alpha), (i, 0), (i + 4, 0))

        # 标题
        title = self.font_title.render("LOADING", True, (0, 255, 200))
        tx = W // 2 - title.get_width() // 2
        ty = H // 3 - title.get_height() // 2
        self.screen.blit(title, (tx, ty))

        # 进度条背景
        bar_w, bar_h = 500, 24
        bar_x = W // 2 - bar_w // 2
        bar_y = H // 2
        pygame.draw.rect(self.screen, (20, 20, 35), (bar_x, bar_y, bar_w, bar_h), border_radius=4)

        # 进度条填充
        fill_w = int(bar_w * self.progress)
        if fill_w > 0:
            # 渐变效果模拟
            for i in range(fill_w):
                t = i / bar_w
                r = int(0 + 50 * t)
                g = int(200 + 55 * (1 - abs(t - 0.5) * 2))
                b = int(150 + 50 * t)
                pygame.draw.line(self.screen, (r, g, b), (bar_x + i, bar_y + 2), (bar_x + i, bar_y + bar_h - 2))
            pygame.draw.rect(self.screen, (0, 255, 200), (bar_x, bar_y, fill_w, bar_h), 1, border_radius=4)

        # 百分比文字
        pct = self.font_progress.render(f"{int(self.progress * 100)}%", True, (200, 220, 255))
        px = W // 2 - pct.get_width() // 2
        py = bar_y + bar_h + 15
        self.screen.blit(pct, (px, py))

        # 状态文字
        if self.status_text:
            st = self.font_tip.render(self.status_text, True, (120, 150, 180))
            sx = W // 2 - st.get_width() // 2
            sy = py + 30
            self.screen.blit(st, (sx, sy))

        # 底部装饰
        for i in range(0, W, 12):
            alpha = int(20 * math.sin(i * 0.015 + self._animate * 1.5))
            if alpha > 0:
                pygame.draw.line(self.screen, (100, 0, 200, alpha), (i, H - 2), (i + 6, H - 2))

    def draw_complete(self) -> None:
        """显示加载完成画面"""
        W, H = self.screen.get_size()
        self.screen.fill((5, 5, 15))

        title = self.font_title.render("READY!", True, (0, 255, 200))
        tx = W // 2 - title.get_width() // 2
        ty = H // 2 - title.get_height() // 2
        self.screen.blit(title, (tx, ty))

        hint = self.font_sub.render("Entering the world...", True, (150, 200, 255))
        hx = W // 2 - hint.get_width() // 2
        self.screen.blit(hint, (hx, ty + title.get_height() + 20))

        pygame.display.flip()
