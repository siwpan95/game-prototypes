import json
from pathlib import Path

import pygame
from core.ecs import System
from core.config import CELL, COLS, ROWS
from core.utils import _load_font
from components.grid_position import GridPosition
from components.text_glyph import TextGlyph
from components.memory import Memory
from components.card_collectible import CardCollectible
from components.interactable import Interactable
from core.paths import ROOT


# ── 调色板（昏暗、有层次，"文字即画面"氛围）──
CHAR_COLORS = {
    "wall":       (110,  90,  70),   # 墙壁 — 暖棕石色
    "floor":      (22,   20,  28),   # 地板 — 极暗蓝灰
    "door":       (150, 125,  80),   # 门   — 暖木色
    "door_open":  (65,   55,  40),   # 已开门
    "label":      (75,   70,  95),   # 区域标签
    "interact":   (210, 180, 120),   # 可交互物件 — 暖金
    "adjacent":   (255, 225, 130),   # 玩家相邻 — 亮金
    "discovered": (120, 105,  80),   # 已发现物件
    "question":   (170, 130,  80),   # 记忆问题 ◈
    "dark":       (12,   10,  16),   # 暗 — 接近纯黑
    "card_hint":  (90,  150,  90),   # 卡牌提示
    "player":     (255, 235, 190),   # 玩家"我"
    "glow_strong":(255, 200, 100),   # 强辉光
    "glow_soft":  (100,  85,  50),   # 柔辉光
}

WALL_CHARS = set("墙")
FLOOR_CHARS = set("░")
DARK_CHARS = set("暗")
DOOR_CHARS = set("门")
LABEL_CHARS = set("阁楼卧室书房走廊地下室深渊")


class TextWorldRenderer(System):
    """文字网格渲染：mansion_map.txt 即世界。
    强化"文字即画面"的 ASCII 艺术质感——
    辉光、扫描线、暗角、背景纹理。
    """

    def __init__(self, screen, map_data=None):
        self.screen = screen
        self.font = _load_font(16)
        self.font_bold = _load_font(16, bold=True)
        self.font_icon = _load_font(14)
        self._map_data = map_data
        self._fallback_grid = None
        if not map_data:
            self._load_fallback_map()
        self._load_objects()

    @property
    def map_grid(self):
        """始终从 MapData 获取最新网格（支持地图切换）。"""
        if self._map_data:
            return self._map_data.grid
        return self._fallback_grid

    # ─────────────────────────────────────────────
    #  Map / object loading
    # ─────────────────────────────────────────────

    def _load_fallback_map(self):
        map_path = ROOT / "data" / "mansion_map.txt"
        with open(map_path, encoding="utf-8") as f:
            raw = f.read()
        lines = raw.strip("\n").split("\n")
        self._fallback_grid = []
        for row_idx, line in enumerate(lines):
            if row_idx >= ROWS:
                break
            row_chars = []
            for col_idx, ch in enumerate(line):
                if col_idx >= COLS:
                    break
                row_chars.append(ch)
            while len(row_chars) < COLS:
                row_chars.append(" ")
            self._fallback_grid.append(row_chars)
        while len(self._fallback_grid) < ROWS:
            self._fallback_grid.append([" "] * COLS)

    def _load_objects(self):
        obj_path = ROOT / "data" / "mansion_objects.json"
        with open(obj_path, encoding="utf-8") as f:
            self.obj_data = json.load(f)

    # ─────────────────────────────────────────────
    #  Main update / render
    # ─────────────────────────────────────────────

    def update(self, world, dt):
        # ── 背景纹理（替代纯黑填充）──
        self._draw_bg_texture()

        # ── 构建实体查找表 ──
        entity_at = {}
        for e in world.entities.values():
            gp = e.get(GridPosition)
            if gp is None:
                continue
            entity_at[(gp.col, gp.row)] = e

        interact_positions = set()
        for obj in self.obj_data.get("interactives", []):
            interact_positions.add((obj["col"], obj["row"]))
        for q in self.obj_data.get("memory_questions", []):
            interact_positions.add((q["col"], q["row"]))

        adjacent_set = self._get_adjacent(world, entity_at)

        # ── 脉冲参数 ──
        tick = pygame.time.get_ticks()
        pulse      = 0.5 + 0.5 * abs((tick % 2000) / 1000.0 - 1.0)
        pulse_strong = 0.6 + 0.4 * abs((tick % 800)  / 400.0  - 1.0)

        # ── 第一遍：地图字符 ──
        for row in range(ROWS):
            for col in range(COLS):
                ch = self.map_grid[row][col]
                if ch == " ":
                    continue
                px = col * CELL
                py = row * CELL
                pos = (col, row)

                color = self._char_color(
                    ch, pos, entity_at, interact_positions,
                    adjacent_set, pulse, pulse_strong,
                )

                # 墙壁字符使用辉光渲染
                if ch in WALL_CHARS:
                    self._render_char_glow(
                        self.screen, ch, px, py,
                        color, CHAR_COLORS["glow_soft"],
                        self.font, CELL, glow_radius=2,
                    )
                else:
                    glyph = self.font.render(ch, True, color)
                    gx = px + (CELL - glyph.get_width()) // 2
                    gy = py + (CELL - glyph.get_height()) // 2
                    self.screen.blit(glyph, (gx, gy))

        # ── 第二遍：卡牌提示 ✧（带辉光）──
        for e in world.entities.values():
            cc = e.get(CardCollectible)
            gp = e.get(GridPosition)
            if not cc or not gp:
                continue
            pos = (gp.col, gp.row)
            if pos in interact_positions:
                continue
            if cc.collected:
                continue
            px = gp.col * CELL
            py = gp.row * CELL
            alpha = int(60 + 100 * pulse)
            self._render_char_glow(
                self.screen, "✧", px, py,
                CHAR_COLORS["card_hint"], CHAR_COLORS["glow_soft"],
                self.font, CELL, glow_radius=1, base_alpha=alpha,
            )

        # ── 第三遍：相邻物件触碰提示 ⏎ ──
        for ac, ar in adjacent_set:
            px = ac * CELL
            py = ar * CELL
            self._render_char_glow(
                self.screen, "⏎", px, py - 10,
                (255, 255, 255), CHAR_COLORS["glow_strong"],
                self.font_icon, CELL, glow_radius=1,
            )

        # ── 第四遍：玩家"我"（强辉光）──
        for e in world.entities.values():
            gp = e.get(GridPosition)
            tg = e.get(TextGlyph)
            if gp and tg and e.eid == "player":
                px = gp.col * CELL
                py = gp.row * CELL
                self._render_char_glow(
                    self.screen, tg.char, px, py,
                    CHAR_COLORS["player"], CHAR_COLORS["glow_strong"],
                    self.font_bold, CELL, glow_radius=2,
                )

        # ── 后处理效果 ──
        self._draw_scanlines()
        self._draw_vignette()

    # ─────────────────────────────────────────────
    #  Color resolution
    # ─────────────────────────────────────────────

    def _char_color(self, ch, pos, entity_at, interact_positions,
                        adjacent_set, pulse, pulse_strong):
        col, row = pos

        if ch in WALL_CHARS:
            return CHAR_COLORS["wall"]
        if ch in DARK_CHARS:
            return CHAR_COLORS["dark"]
        if ch in DOOR_CHARS:
            e = entity_at.get(pos)
            if e:
                cc = e.get(CardCollectible)
                if cc and cc.collected:
                    return CHAR_COLORS["door_open"]
            return CHAR_COLORS["door"]
        if ch in FLOOR_CHARS:
            return CHAR_COLORS["floor"]
        if ch == "◈":
            return CHAR_COLORS["question"]
        if ch in LABEL_CHARS:
            return CHAR_COLORS["label"]

        if pos in interact_positions:
            e = entity_at.get(pos)
            memory = e.get(Memory) if e else None
            cc = e.get(CardCollectible) if e else None
            discovered = (memory and memory.discovered) or (cc and cc.collected)

            if discovered:
                return CHAR_COLORS["discovered"]

            if pos in adjacent_set:
                a = 0.7 + 0.3 * pulse_strong
                r, g, b = CHAR_COLORS["adjacent"]
                return (int(r * a), int(g * a), int(b * a))
            else:
                a = 0.5 + 0.5 * pulse
                r, g, b = CHAR_COLORS["interact"]
                return (int(r * a), int(g * a), int(b * a))

        return CHAR_COLORS["floor"]

    # ─────────────────────────────────────────────
    #  Adjacent detection（支持多格物件）
    # ─────────────────────────────────────────────

    def _get_adjacent(self, world, entity_at):
        player = world.entities.get("player")
        if not player:
            return set()
        gp = player.get(GridPosition)
        if not gp:
            return set()

        adjacent = set()
        for dc, dr in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nc, nr = gp.col + dc, gp.row + dr
            e = entity_at.get((nc, nr))
            if e is None:
                for pos_key, entity in entity_at.items():
                    ia = entity.get(Interactable)
                    if not ia:
                        continue
                    hw = max(ia.hitbox_width  // 20, 1)
                    hh = max(ia.hitbox_height // 20, 1)
                    if hw <= 1 and hh <= 1:
                        continue
                    if (pos_key[0] <= nc < pos_key[0] + hw and
                            pos_key[1] <= nr < pos_key[1] + hh):
                        e = entity
                        break
            if e is None:
                continue
            memory = e.get(Memory)
            ia = e.get(Interactable)
            cc = e.get(CardCollectible)
            if (ia and memory and not memory.discovered) or (cc and not cc.collected):
                adjacent.add((nc, nr))
        return adjacent

    # ─────────────────────────────────────────────
    #  Visual effects
    # ─────────────────────────────────────────────

    def _render_char_glow(self, screen, ch, px, py,
                              color, glow_color, font, cell_size,
                              glow_radius=1, base_alpha=255):
        """渲染带辉光的字符。
        先在偏移位置用 glow_color + 低 alpha 绘制多层，
        再在主位置用完整颜色绘制顶层字符。
        """
        cx = px + (cell_size - font.size(ch)[0]) // 2
        cy = py + (cell_size - font.get_height()) // 2

        # 预定义偏移列表（曼哈顿距离 ≤ glow_radius）
        if glow_radius <= 1:
            offsets = [
                (-1, 0), (1, 0), (0, -1), (0, 1),
                (-1,-1), (1,-1), (-1, 1), (1, 1),
            ]
        else:
            offsets = []
            for dy in range(-glow_radius, glow_radius + 1):
                for dx in range(-glow_radius, glow_radius + 1):
                    if dx == 0 and dy == 0:
                        continue
                    if abs(dx) + abs(dy) > glow_radius:
                        continue
                    offsets.append((dx, dy))
            if len(offsets) > 8:
                offsets = offsets[:8]

        ga = max(25, base_alpha // 4)
        for dx, dy in offsets:
            g = font.render(ch, True, glow_color)
            g.set_alpha(ga)
            screen.blit(g, (cx + dx, cy + dy))

        # 主字符层
        main = font.render(ch, True, color)
        if base_alpha < 255:
            main.set_alpha(base_alpha)
        screen.blit(main, (cx, cy))

    def _draw_bg_texture(self):
        """用极暗的网格点纹理替代纯黑填充。"""
        self.screen.fill((8, 6, 10))
        dot_color = (15, 12, 18)
        for row in range(0, ROWS, 2):
            for col in range(0, COLS, 2):
                px = col * CELL + CELL // 2
                py = row * CELL + CELL // 2
                pygame.draw.circle(self.screen, dot_color, (px, py), 1)

    def _draw_scanlines(self):
        """扫描线效果 —— 经典 ASCII 游戏视觉氛围。"""
        sw, sh = self.screen.get_size()
        scan_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for y in range(0, sh, 3):
            pygame.draw.line(scan_surf, (0, 0, 0, 40), (0, y), (sw, y), 1)
        self.screen.blit(scan_surf, (0, 0))

    def _draw_vignette(self):
        """暗角效果 —— 画面边缘逐渐变暗，引导视线到中心。"""
        sw, sh = self.screen.get_size()
        vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
        cs = 200  # 暗角尺寸
        rects = [
            (0,        0,       cs, cs),  # 左上
            (sw - cs, 0,       cs, cs),  # 右上
            (0,        sh - cs, cs, cs),  # 左下
            (sw - cs, sh - cs, cs, cs),  # 右下
        ]
        for (x, y, w, h) in rects:
            pygame.draw.rect(vignette, (0, 0, 0, 55), (x, y, w, h))
        self.screen.blit(vignette, (0, 0))

    # ─────────────────────────────────────────────
    #  Picking
    # ─────────────────────────────────────────────

    def get_cell_at(self, px, py):
        col = px // CELL
        row = py // CELL
        if 0 <= col < COLS and 0 <= row < ROWS:
            return col, row
        return None
