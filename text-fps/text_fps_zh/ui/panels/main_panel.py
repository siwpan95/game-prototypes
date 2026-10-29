"""MainPanel - Main text log area showing game messages."""
from typing import List, Optional, Tuple

try:
    import pygame_ce as pygame
except ImportError:
    import pygame

from ui.panel import Panel
from ui import colors as C
from core.constants import FONT_SIZE_BODY


class MainPanel(Panel):
    """Left-side text log panel that displays game messages."""

    LINE_SPACING = 2

    def __init__(self, rect: pygame.Rect) -> None:
        super().__init__(rect, bg_color=C.BG_PANEL)
        self.scroll_offset: int = 0
        self.max_scroll: int = 0
        self.font: pygame.font.Font = pygame.font.Font(None, FONT_SIZE_BODY)
        # #4: cache wrapped lines so we don't re-measure every log line each frame.
        # Invalidated when the log changes (game_state.dirty) or is replaced.
        self._wrap_cache: Optional[List[Tuple[str, tuple]]] = None
        self._wrap_cache_log: Optional[list] = None

    def set_font(self, font: pygame.font.Font) -> None:
        """Set the font used for rendering text."""
        self.font = font

    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """将文本按像素宽度拆分成多行，支持CJK字符按字符断行。"""
        if not text:
            return [""]
        lines: List[str] = []
        current_line = ""
        for ch in text:
            test = current_line + ch
            if self.font.size(test)[0] > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = ch
            else:
                current_line = test
        if current_line:
            lines.append(current_line)
        return lines if lines else [""]

    def _build_wrapped_lines(self, logs: list) -> List[Tuple[str, tuple]]:
        """将所有日志消息预计算为带颜色的换行列表。"""
        max_text_width = self.rect.width - 20  # 左右各留 8px 边距 + 滚动条预留
        wrapped: List[Tuple[str, tuple]] = []
        for msg in logs:
            color = self._get_line_color(msg)
            for line_text in self._wrap_text(msg, max_text_width):
                wrapped.append((line_text, color))
        return wrapped

    def render(self, surface: pygame.Surface, game_state) -> None:
        """Render the text log with auto-scroll and color coding."""
        super().render(surface, game_state)
        if not game_state:
            return

        logs = game_state.log
        if not logs:
            return

        line_height = self.font.get_height() + self.LINE_SPACING
        visible_lines = (self.rect.height - 8) // line_height

        # 预计算所有换行后的行（带缓存：仅在日志变化或换档时重算）
        if game_state.dirty or self._wrap_cache is None or self._wrap_cache_log is not game_state.log:
            wrapped_lines = self._build_wrapped_lines(logs)
            self._wrap_cache = wrapped_lines
            self._wrap_cache_log = game_state.log
        else:
            wrapped_lines = self._wrap_cache
        total_lines = len(wrapped_lines)
        self.max_scroll = max(0, total_lines - visible_lines)

        # Auto-scroll to bottom unless user has scrolled up
        if self.scroll_offset > self.max_scroll:
            self.scroll_offset = self.max_scroll

        # Determine start index
        start = max(0, total_lines - visible_lines - self.scroll_offset)
        end = min(total_lines, start + visible_lines)

        # Clip rendering to panel rect
        surface.set_clip(self.rect)

        y = self.rect.y + 4
        for i in range(start, end):
            if y + line_height > self.rect.y + self.rect.height:
                break
            line_text, color = wrapped_lines[i]
            text_surf = self.font.render(line_text, True, color)
            surface.blit(text_surf, (self.rect.x + 8, y))
            y += line_height

        surface.set_clip(None)

        # Draw scrollbar if needed
        if self.max_scroll > 0:
            self._draw_scrollbar(surface, visible_lines, total_lines)

    def _get_line_color(self, msg: str) -> tuple:
        """Determine text color based on message content."""
        if msg.startswith("===") or msg.startswith("---"):
            return C.TEXT_PRIMARY

        # 红色关键词 - 伤害、死亡、失败
        red_keywords = ["伤害", "受伤", "死亡", "阵亡", "失败", "错误", "未命中",
                        "GAME OVER", "YOU HAVE FALLEN"]
        for kw in red_keywords:
            if kw in msg:
                return C.HP_RED

        # 黄色关键词 - 警告、提示
        yellow_keywords = ["发现敌人", "警觉", "增援", "陷阱", "小心", "拾取",
                           "ENEMY TURN", "Enemies spotted", "Trap triggered",
                           "Reinforcements arrived", "noise alerted"]
        for kw in yellow_keywords:
            if kw in msg:
                return C.NOISE_YELLOW

        # 绿色关键词 - 成功、积极消息
        green_keywords = ["消灭", "击杀", "完成", "成功", "恢复", "装备",
                          "VICTORY", "LEVEL COMPLETE", "eliminated", "correct"]
        for kw in green_keywords:
            if kw in msg:
                return C.AMMO_GREEN

        # 未命中
        if "miss" in msg.lower():
            return C.TEXT_DIM

        return C.TEXT_WHITE

    def _draw_scrollbar(self, surface: pygame.Surface, visible: int, total: int) -> None:
        """Draw a minimal scrollbar on the right edge."""
        bar_height = max(20, int(self.rect.height * visible / total))
        bar_y = self.rect.y + int(
            (self.rect.height - bar_height) *
            (1.0 - self.scroll_offset / max(1, self.max_scroll))
        )
        bar_rect = pygame.Rect(
            self.rect.x + self.rect.width - 6,
            bar_y,
            4,
            bar_height,
        )
        pygame.draw.rect(surface, C.DIVIDER, bar_rect, border_radius=2)

    def handle_click(self, pos, game_state) -> bool:
        """Consume clicks within the panel area (no action)."""
        if self.rect.collidepoint(pos):
            return True
        return False

    def handle_scroll(self, dy: int) -> None:
        """Handle mouse wheel scroll. dy > 0 = scroll up, dy < 0 = scroll down."""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset - dy))
