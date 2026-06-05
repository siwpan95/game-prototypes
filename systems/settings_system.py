"""
设置系统 — 操控说明 / 音量控制 / 卡牌收藏
=============================================
Tab 键触发全屏设置面板，纯键盘交互。
←→ 切换标签页，↑↓ 导航内容，Escape 关闭面板。
"""
import pygame
from core.ecs import System
from core.config import WINDOW_W, WINDOW_H
from core.utils import _load_font




# ── 稀有度颜色 ──
RARITY_COLORS = {
    "key":    (200, 160, 40),
    "story":  (120, 140, 180),
    "secret": (180, 100, 160),
    "common": (100, 100, 100),
}

# ── 操控说明数据 ──
CONTROLS = [
    ("WASD / 方向键",  "移动"),
    ("空格",           "触碰相邻物件"),
    ("Tab",            "打开 / 关闭设置"),
    ("Escape",         "关闭设置"),
    ("1 / 2 / 3",      "切换设置标签页"),
    ("R",              "重新开始（游戏结束后）"),
    ("Q",              "退出（游戏结束后）"),
]


class SettingsSystem(System):
    """设置面板：操控说明、音量控制、卡牌收藏。Tab 键切换显示。"""

    TAB_NAMES = ["操控说明", "音量控制", "卡牌收藏"]
    VOL_STEP  = 0.05

    def __init__(self, screen, event_bus, card_sys=None, audio_sys=None):
        self.screen    = screen
        self.bus       = event_bus
        self.card_sys  = card_sys
        self.audio_sys = audio_sys

        # 面板状态
        self.open          = False
        self.quit_requested = False  # 设置面板中请求退出游戏
        self.tab           = 0      # 0=操控 1=音量 2=卡牌
        self.vol_row       = 0      # 音量页焦点行 0=BGM 1=SFX
        self.card_selected = 0      # 卡牌列表选中索引
        self.card_scroll   = 0      # 卡牌列表滚动偏移

        # 字体
        self.font_title = _load_font(28, bold=True)
        self.font_tab   = _load_font(16, bold=True)
        self.font_label = _load_font(15)
        self.font_text  = _load_font(14)
        self.font_small = _load_font(12)

    # ── 公开接口 ──────────────────────────────────

    def toggle(self):
        """切换面板开关状态。"""
        self.open = not self.open
        if self.open:
            self.card_scroll   = 0
            self.card_selected = 0
            self.vol_row       = 0

    def handle_event(self, event):
        """处理设置面板内的键盘事件。仅在面板打开时由 main 调用。
        注意：Tab 键的 toggle 由 main.py 直接处理，此处不消费。"""
        if not self.open or event.type != pygame.KEYDOWN:
            return

        key = event.key

        # Escape → 关闭
        if key == pygame.K_ESCAPE:
            self.open = False
            return

        # Backspace → 退出游戏
        if key == pygame.K_BACKSPACE:
            self.quit_requested = True
            self.open = False
            return

        # 数字键 1-3 快速切换标签
        for i, nk in enumerate((pygame.K_1, pygame.K_2, pygame.K_3)):
            if key == nk:
                self.tab = i
                self._reset_nav()
                return

        # Q/W/E 切换标签（左手友好）
        for i, nk in enumerate((pygame.K_q, pygame.K_w, pygame.K_e)):
            if key == nk:
                self.tab = i
                self._reset_nav()
                return

        # ← → 仅用于音量滑块调整（标签页切换用 1/2/3）
        # 各标签页交互
        if self.tab == 1:
            self._handle_volume_event(key)
        elif self.tab == 2:
            self._handle_card_event(key)

    # ── 内部导航 ──────────────────────────────────

    def _reset_nav(self):
        self.card_scroll   = 0
        self.card_selected = 0
        self.vol_row       = 0

    # ── 音量控制交互 ──────────────────────────────

    def _handle_volume_event(self, key):
        if key == pygame.K_UP:
            self.vol_row = max(0, self.vol_row - 1)
        elif key == pygame.K_DOWN:
            self.vol_row = min(1, self.vol_row + 1)
        elif key in (pygame.K_LEFT, pygame.K_MINUS, pygame.K_KP_MINUS):
            self._adjust_volume(-self.VOL_STEP)
        elif key in (pygame.K_RIGHT, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._adjust_volume(self.VOL_STEP)

    def _adjust_volume(self, delta):
        if not self.audio_sys:
            return
        if self.vol_row == 0:
            self.audio_sys.set_bgm_volume(self.audio_sys.master_bgm + delta)
        else:
            self.audio_sys.set_sfx_volume(self.audio_sys.master_sfx + delta)

    # ── 卡牌浏览交互 ──────────────────────────────

    def _handle_card_event(self, key):
        if not self.card_sys:
            return
        total = self.card_sys.total_cards
        if total == 0:
            return
        if key == pygame.K_UP:
            self.card_selected = max(0, self.card_selected - 1)
            self._clamp_scroll()
        elif key == pygame.K_DOWN:
            self.card_selected = min(total - 1, self.card_selected + 1)
            self._clamp_scroll()
        elif key == pygame.K_PAGEUP:
            self.card_selected = max(0, self.card_selected - 8)
            self._clamp_scroll()
        elif key == pygame.K_PAGEDOWN:
            self.card_selected = min(total - 1, self.card_selected + 8)
            self._clamp_scroll()

    def _clamp_scroll(self):
        visible = 10
        if self.card_selected < self.card_scroll:
            self.card_scroll = self.card_selected
        elif self.card_selected >= self.card_scroll + visible:
            self.card_scroll = self.card_selected - visible + 1

    # ── 渲染 ──────────────────────────────────────

    def update(self, world, dt):
        if not self.open:
            return
        self._render_overlay()

    def _render_overlay(self):
        sw, sh = self.screen.get_size()

        # 半透明遮罩
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((5, 3, 8, 210))
        self.screen.blit(overlay, (0, 0))

        # 面板区域
        pw, ph = 680, 500
        px = (sw - pw) // 2
        py = (sh - ph) // 2

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((15, 12, 18, 240))
        pygame.draw.rect(panel, (60, 50, 70), panel.get_rect(), 2)

        # ── 标题 ──
        title = self.font_title.render("设置", True, (220, 210, 190))
        panel.blit(title, ((pw - title.get_width()) // 2, 14))

        # ── 标签栏 ──
        tab_y = 56
        tab_w = pw // len(self.TAB_NAMES)
        for i, name in enumerate(self.TAB_NAMES):
            tx = i * tab_w
            is_active = (i == self.tab)

            if is_active:
                pygame.draw.rect(panel, (35, 30, 45), (tx, tab_y, tab_w, 32))
                pygame.draw.line(
                    panel, (180, 160, 100),
                    (tx + 4, tab_y + 30), (tx + tab_w - 4, tab_y + 30), 2,
                )
                color = (220, 200, 150)
            else:
                color = (100, 95, 110)

            tab_surf = self.font_tab.render(name, True, color)
            panel.blit(tab_surf, (tx + (tab_w - tab_surf.get_width()) // 2, tab_y + 6))

        # 分隔线
        pygame.draw.line(
            panel, (40, 35, 50), (20, tab_y + 34), (pw - 20, tab_y + 34), 1,
        )

        # ── 内容区域 ──
        cy = tab_y + 44
        ch = ph - cy - 40

        if self.tab == 0:
            self._render_controls(panel, 20, cy, pw - 40, ch)
        elif self.tab == 1:
            self._render_volume(panel, 20, cy, pw - 40, ch)
        elif self.tab == 2:
            self._render_cards(panel, 20, cy, pw - 40, ch)

        # ── 底部提示 ──
        hint = self.font_small.render(
            "Tab/Escape 关闭  ·  1/2/3 切换标签  ·  ↑↓ 导航  ·  Backspace 退出游戏", True, (80, 75, 90),
        )
        panel.blit(hint, ((pw - hint.get_width()) // 2, ph - 28))

        self.screen.blit(panel, (px, py))

    # ── 标签页 0：操控说明 ────────────────────────

    def _render_controls(self, surf, x, y, w, h):
        header = self.font_label.render("操控说明", True, (180, 170, 150))
        surf.blit(header, (x, y))
        y += 30

        for key_str, desc in CONTROLS:
            # 键位（金色）
            k = self.font_text.render(key_str, True, (200, 180, 120))
            surf.blit(k, (x + 20, y))
            # 分隔点
            dot = self.font_text.render("·", True, (100, 90, 80))
            surf.blit(dot, (x + 200, y))
            # 描述
            d = self.font_text.render(desc, True, (170, 165, 155))
            surf.blit(d, (x + 220, y))
            y += 28

        y += 20
        tip = self.font_small.render(
            "游戏进行中随时按 Tab 打开设置面板", True, (100, 95, 85),
        )
        surf.blit(tip, (x + 20, y))

    # ── 标签页 1：音量控制 ────────────────────────

    def _render_volume(self, surf, x, y, w, h):
        header = self.font_label.render("音量控制", True, (180, 170, 150))
        surf.blit(header, (x, y))
        y += 30

        bgm_vol = self.audio_sys.master_bgm if self.audio_sys else 0.5
        sfx_vol = self.audio_sys.master_sfx if self.audio_sys else 0.7

        for i, (label, vol) in enumerate([("背景音乐", bgm_vol), ("音    效", sfx_vol)]):
            is_sel = (i == self.vol_row)

            # 行高亮
            if is_sel:
                pygame.draw.rect(surf, (30, 25, 40), (x, y - 2, w, 40))

            # 标签
            lbl_c = (220, 200, 150) if is_sel else (150, 145, 135)
            surf.blit(self.font_text.render(label, True, lbl_c), (x + 20, y + 6))

            # 滑块轨道
            bar_x = x + 120
            bar_w = w - 200
            bar_h = 16
            bar_y = y + 12

            pygame.draw.rect(surf, (30, 28, 35), (bar_x, bar_y, bar_w, bar_h))
            pygame.draw.rect(surf, (50, 45, 55), (bar_x, bar_y, bar_w, bar_h), 1)

            # 填充
            fill_w = int(bar_w * vol)
            if fill_w > 0:
                if vol > 0.5:
                    r = int(60 + (1.0 - vol) * 2 * 180)
                    g = int(180 - (1.0 - vol) * 2 * 60)
                    b = 50
                else:
                    r = int(200 - vol * 2 * 100)
                    g = int(140 + vol * 2 * 40)
                    b = 40
                pygame.draw.rect(surf, (r, g, b), (bar_x, bar_y, fill_w, bar_h))

            # 手柄
            hx = bar_x + fill_w - 3
            hx = max(bar_x, min(hx, bar_x + bar_w - 6))
            pygame.draw.rect(surf, (220, 210, 190), (hx, bar_y - 2, 6, bar_h + 4))

            # 百分比
            pct = self.font_text.render(f"{int(vol * 100)}%", True, (180, 175, 165))
            surf.blit(pct, (bar_x + bar_w + 12, y + 6))

            y += 50

        y += 10
        hint = self.font_small.render(
            "↑↓ 选择  ·  ←→ 或 +/- 调整音量", True, (100, 95, 85),
        )
        surf.blit(hint, (x + 20, y))

    # ── 标签页 2：卡牌收藏 ────────────────────────

    def _render_cards(self, surf, x, y, w, h):
        if not self.card_sys:
            return

        hdr = f"卡牌收藏  {self.card_sys.collected_count}/{self.card_sys.total_cards}"
        surf.blit(self.font_label.render(hdr, True, (180, 170, 150)), (x, y))
        y += 28

        sorted_ids = self.card_sys._sorted_ids
        total = len(sorted_ids)
        if total == 0:
            surf.blit(self.font_text.render("暂无卡牌", True, (100, 95, 85)), (x + 20, y))
            return

        visible = 8
        card_h  = 34
        start   = self.card_scroll
        end     = min(start + visible, total)

        for i in range(start, end):
            cid  = sorted_ids[i]
            cdef = self.card_sys.cards_def[cid]
            collected    = cid in self.card_sys.collected
            is_selected  = (i == self.card_selected)
            cy = y + (i - start) * card_h

            # 选中高亮
            if is_selected:
                pygame.draw.rect(surf, (40, 35, 50), (x, cy, w, card_h - 2))

            # 颜色
            gc = (220, 200, 150) if collected else (60, 55, 65)
            nc = (200, 190, 170) if collected else (55, 50, 60)

            # 字形
            surf.blit(self.font_text.render(cdef.get("glyph", "?"), True, gc), (x + 16, cy + 6))
            # 名称
            surf.blit(self.font_text.render(cdef.get("name", "???"), True, nc), (x + 36, cy + 6))

            # 稀有度圆点
            rc = RARITY_COLORS.get(cdef.get("rarity", "common"), (100, 100, 100))
            pygame.draw.circle(surf, rc, (x + w - 80, cy + 14), 4)

            # 状态
            st_txt  = "已收集" if collected else "未收集"
            st_col  = (120, 180, 100) if collected else (80, 75, 85)
            surf.blit(self.font_small.render(st_txt, True, st_col), (x + w - 65, cy + 8))

        # 选中卡牌描述（确保不超出内容区域）
        desc_y = y + visible * card_h + 8
        if 0 <= self.card_selected < total:
            sel_id  = sorted_ids[self.card_selected]
            sel_def = self.card_sys.cards_def.get(sel_id, {})
            if sel_id in self.card_sys.collected and sel_def:
                # 检查是否有足够空间显示描述
                desc_h = self.font_text.get_height()
                if desc_y + desc_h + 4 < y + h:
                    pygame.draw.line(surf, (40, 35, 50), (x, desc_y - 4), (x + w, desc_y - 4), 1)
                    desc = sel_def.get("desc", "")
                    if len(desc) > 60:
                        desc = desc[:58] + "……"
                    surf.blit(self.font_text.render(desc, True, (160, 150, 140)), (x + 16, desc_y))

        # 滚动提示
        if total > visible:
            scroll_y = y + visible * card_h + 28
            scroll_h = self.font_small.get_height()
            if scroll_y + scroll_h < y + h:
                stxt = f"↑↓ 浏览  ·  {start + 1}-{end}/{total}"
                surf.blit(self.font_small.render(stxt, True, (100, 95, 85)),
                          (x + 20, scroll_y))
